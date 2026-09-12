"""Minimal stand-in for mido.Message used when mido is not installed.

The timeline is pure data until something sends it, so building and testing
it must not require a MIDI backend. When mido is present it is used directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:  # pragma: no cover - depends on the environment
    import mido as _mido
except ImportError:  # pragma: no cover
    _mido = None


if _mido is not None:
    Message = _mido.Message
    HAVE_MIDO = True
else:
    HAVE_MIDO = False

    @dataclass
    class Message:  # type: ignore[no-redef]
        """Same constructor shape as mido.Message, enough to build a timeline."""

        type: str
        note: int = 0
        velocity: int = 0
        channel: int = 0
        control: int = 0
        value: int = 0
        pos: int = 0
        time: float = 0.0

        def __init__(self, type: str, **kwargs: Any) -> None:
            self.type = type
            self.note = kwargs.get("note", 0)
            self.velocity = kwargs.get("velocity", 0)
            self.channel = kwargs.get("channel", 0)
            self.control = kwargs.get("control", 0)
            self.value = kwargs.get("value", 0)
            self.pos = kwargs.get("pos", 0)
            self.time = kwargs.get("time", 0.0)

        def __repr__(self) -> str:
            return (
                f"Message({self.type!r}, note={self.note}, "
                f"velocity={self.velocity}, channel={self.channel})"
            )


# ---------------------------------------------------------------------------
# Standard MIDI File writing
# ---------------------------------------------------------------------------
# mido writes these too, but the timeline has to be renderable to a file
# without a MIDI backend installed — the file path is the one that does not
# need any hardware, so requiring a hardware library for it would be odd.

import struct
from typing import Sequence


def _varint(value: int) -> bytes:
    """SMF variable-length quantity: seven bits per byte, high bit continues."""

    if value < 0:
        raise ValueError("delta times cannot be negative")
    chunks = [value & 0x7F]
    value >>= 7
    while value:
        chunks.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(chunks))


def _track_chunk(payload: bytes) -> bytes:
    return b"MTrk" + struct.pack(">I", len(payload)) + payload


def encode_event(message, delta: int) -> bytes:
    """One channel message with its delta time."""

    head = _varint(delta)
    channel = int(getattr(message, "channel", 0)) & 0x0F
    if message.type == "note_on":
        return head + bytes((0x90 | channel, int(message.note) & 0x7F,
                             int(message.velocity) & 0x7F))
    if message.type == "note_off":
        return head + bytes((0x80 | channel, int(message.note) & 0x7F,
                             int(message.velocity) & 0x7F))
    if message.type == "control_change":
        return head + bytes((0xB0 | channel, int(message.control) & 0x7F,
                             int(message.value) & 0x7F))
    raise ValueError(f"cannot write {message.type} to a MIDI file")


def encode_meta_tempo(microseconds_per_beat: int, delta: int = 0) -> bytes:
    return (
        _varint(delta)
        + b"\xff\x51\x03"
        + struct.pack(">I", int(microseconds_per_beat))[1:]
    )


def encode_meta_name(name: str, delta: int = 0) -> bytes:
    data = name.encode("latin-1", "replace")
    return _varint(delta) + b"\xff\x03" + _varint(len(data)) + data


def encode_end_of_track(delta: int = 0) -> bytes:
    return _varint(delta) + b"\xff\x2f\x00"


def write_midi_file(path, ticks_per_beat: int, tracks: Sequence[bytes]) -> None:
    """Write a type-1 file from already-encoded track payloads."""

    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), ticks_per_beat)
    with open(path, "wb") as handle:
        handle.write(header)
        for payload in tracks:
            handle.write(_track_chunk(payload))
