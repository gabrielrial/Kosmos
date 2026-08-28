"""Real-time MIDI playback for the orchestrated musical parts."""

from __future__ import annotations

import time
from threading import Thread
from typing import Iterable

import mido

from music.orchestrator import MappedStarNote, TimelineItem


class RealtimeMidiPlayer(Thread):
    """Base thread for sending one musical part to one MIDI port."""

    def __init__(self, outport, bpm: float):
        super().__init__()
        if bpm <= 0:
            raise ValueError("bpm must be positive")
        self.outport = outport
        self.beat_seconds = 60.0 / bpm

    def _wait_until(self, start_time: float, beat: float) -> None:
        target = start_time + beat * self.beat_seconds
        remaining = target - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)


class StarRealtimeMidiPlayer(RealtimeMidiPlayer):
    """Sends mapped star notes in timestamp order."""

    def __init__(
        self,
        notes: Iterable[MappedStarNote],
        outport,
        bpm: float,
    ):
        super().__init__(outport, bpm)
        self.notes = sorted(notes, key=lambda note: note.timestamp_beat)

    def run(self) -> None:
        start_time = time.monotonic()
        for note in self.notes:
            self._wait_until(start_time, note.timestamp_beat)
            channel = 0 if note.pan is None else max(0, min(15, round(note.pan / 8)))
            self.outport.send(
                mido.Message(
                    "note_on",
                    channel=channel,
                    note=note.mapped_note,
                    velocity=note.velocity,
                )
            )
            duration_seconds = max(0.0, note.duration_beat * self.beat_seconds)
            time.sleep(duration_seconds)
            self.outport.send(
                mido.Message(
                    "note_off",
                    channel=channel,
                    note=note.mapped_note,
                    velocity=0,
                )
            )


class NebulaRealtimeMidiPlayer(RealtimeMidiPlayer):
    """Sends each harmonic timeline chord as a single chord event."""

    def __init__(
        self,
        timeline: Iterable[TimelineItem],
        outport,
        bpm: float,
    ):
        super().__init__(outport, bpm)
        self.timeline = sorted(timeline, key=lambda item: item.start_beat)

    def run(self) -> None:
        start_time = time.monotonic()
        for item in self.timeline:
            self._wait_until(start_time, item.start_beat)
            notes = item.chord.chord_maker()
            for note in notes:
                self.outport.send(
                    mido.Message("note_on", channel=0, note=note, velocity=72)
                )

            duration_seconds = max(
                0.0,
                (item.end_beat - item.start_beat) * self.beat_seconds,
            )
            time.sleep(duration_seconds)
            for note in notes:
                self.outport.send(
                    mido.Message("note_off", channel=0, note=note, velocity=0)
                )


class MidiOutputMode:
    """Output mode names reserved for future file rendering support."""

    REALTIME = "realtime"
    FILE = "file"
