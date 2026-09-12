"""Sends one layer of star notes to a MIDI port.

Deliberately dumb: it reads events and sends bytes. Every decision about
pitch, velocity, pan and length was already made by the mapping layer.

Two guarantees it did not have before: it can be stopped, and every note_on
is matched by a note_off even when it is stopped mid-note.
"""

from __future__ import annotations

import random
from threading import Event, Thread
from typing import Iterable

import mido

from mapping.star_mapper import NoteEvent


class StarMidiPlayer(Thread):
    def __init__(
        self,
        events: Iterable[NoteEvent],
        outport,
        tempo,
        pan_cc: int = 7,
        shuffle: bool = True,
        seed: int | None = None,
    ) -> None:
        super().__init__(daemon=True)
        self.events = list(events)
        self.outport = outport
        self.tempo = tempo
        self.pan_cc = pan_cc
        self._stop = Event()
        self._sounding: set[tuple[int, int]] = set()

        if shuffle:
            # Seeded so two runs of the same image give the same piece.
            random.Random(seed).shuffle(self.events)

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        beat_seconds = self.tempo.beat_duration if self.tempo else 1.0
        try:
            for event in self.events:
                if self._stop.is_set():
                    return
                self._send_pan(event)
                self._note_on(event)
                if self._stop.wait(max(0.0, event.duration * beat_seconds)):
                    return
                self._note_off(event)
        finally:
            self._all_notes_off()

    # ------------------------------------------------------------------
    def _send_pan(self, event: NoteEvent) -> None:
        """Stereo position, on the same channel as the note.

        The previous version divided the position by 12 before sending it, so
        the controller only ever moved between 0 and 10 of its 128 steps and
        every star sounded from nearly the same place.
        """

        self.outport.send(
            mido.Message(
                "control_change",
                control=self.pan_cc,
                value=max(0, min(int(event.pan), 127)),
                channel=event.channel,
            )
        )

    def _note_on(self, event: NoteEvent) -> None:
        self._sounding.add((event.channel, event.note))
        self.outport.send(
            mido.Message(
                "note_on",
                note=event.note,
                velocity=max(1, min(int(event.velocity), 127)),
                channel=event.channel,
            )
        )

    def _note_off(self, event: NoteEvent) -> None:
        self._sounding.discard((event.channel, event.note))
        self.outport.send(
            mido.Message("note_off", note=event.note, velocity=0, channel=event.channel)
        )

    def _all_notes_off(self) -> None:
        for channel, note in list(self._sounding):
            self.outport.send(
                mido.Message("note_off", note=note, velocity=0, channel=channel)
            )
        self._sounding.clear()
