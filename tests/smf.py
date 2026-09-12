"""A tiny Standard MIDI File reader, for tests only.

Independent of mido on purpose: if the writer and the checker shared a
library, a bug in how we use that library would pass unnoticed. This parses
the bytes according to the SMF spec.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass
class FileEvent:
    tick: int
    type: str
    channel: int = 0
    note: int = 0
    velocity: int = 0
    control: int = 0
    value: int = 0
    tempo: int = 0
    name: str = ""


def _varint(data: bytes, index: int) -> tuple[int, int]:
    value = 0
    while True:
        byte = data[index]
        index += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, index


def read(path) -> tuple[int, list[list[FileEvent]]]:
    """Return ``(ticks_per_beat, tracks)`` with absolute ticks per event."""

    with open(path, "rb") as handle:
        data = handle.read()

    assert data[:4] == b"MThd", "not a MIDI file"
    length, fmt, ntracks, division = struct.unpack(">IHHH", data[4:14])
    assert length == 6
    index = 8 + length

    tracks: list[list[FileEvent]] = []
    for _ in range(ntracks):
        assert data[index : index + 4] == b"MTrk", "bad track header"
        track_length = struct.unpack(">I", data[index + 4 : index + 8])[0]
        index += 8
        end = index + track_length
        events: list[FileEvent] = []
        tick = 0
        status = 0

        while index < end:
            delta, index = _varint(data, index)
            tick += delta
            byte = data[index]

            if byte == 0xFF:                                   # meta
                index += 1
                meta_type = data[index]
                index += 1
                meta_length, index = _varint(data, index)
                payload = data[index : index + meta_length]
                index += meta_length
                if meta_type == 0x51:
                    events.append(
                        FileEvent(
                            tick=tick,
                            type="set_tempo",
                            tempo=int.from_bytes(payload, "big"),
                        )
                    )
                elif meta_type == 0x03:
                    events.append(
                        FileEvent(
                            tick=tick,
                            type="track_name",
                            name=payload.decode("latin-1"),
                        )
                    )
                elif meta_type == 0x2F:
                    events.append(FileEvent(tick=tick, type="end_of_track"))
                continue

            if byte & 0x80:
                status = byte
                index += 1
            command, channel = status & 0xF0, status & 0x0F

            if command in (0x80, 0x90):
                note, velocity = data[index], data[index + 1]
                index += 2
                kind = "note_off" if command == 0x80 or velocity == 0 else "note_on"
                events.append(
                    FileEvent(
                        tick=tick,
                        type=kind,
                        channel=channel,
                        note=note,
                        velocity=velocity,
                    )
                )
            elif command == 0xB0:
                control, value = data[index], data[index + 1]
                index += 2
                events.append(
                    FileEvent(
                        tick=tick,
                        type="control_change",
                        channel=channel,
                        control=control,
                        value=value,
                    )
                )
            elif command in (0xC0, 0xD0):
                index += 1
            else:
                index += 2

        tracks.append(events)
        index = end

    return division, tracks
