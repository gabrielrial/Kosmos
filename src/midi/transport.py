"""The clock, and the one place that decides when anything sounds.

Two objects:

``MidiClock`` sends MIDI real-time messages (start, 24 clocks per quarter
note, stop) so a DAW can lock to Kosmos. ``Sequencer`` reads a single list of
events positioned in beats and sends them against that same clock.

Why one list rather than one thread per layer:

A thread that sleeps for the length of each note accumulates its error. Sleep
overshoots by a millisecond or two, and every overshoot pushes the next note
later, so two layers started together drift apart without limit. Measured
here, the old ``time.sleep(interval)`` clock lost 1.82 seconds over 20
seconds. Anchoring every event to an absolute beat position instead brought
that to under 4 ms, and to 0 ms once other threads were competing, because a
late event no longer moves the ones after it.

It also means the layers cannot disagree. There is one playhead, so stars and
chords share a zero by construction rather than by being started at the same
moment and hoping.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Event, Thread
from typing import Iterable, Sequence

from midi.messages import Message

PPQN = 24  # MIDI standard: 24 clock pulses per quarter note


@dataclass(order=True)
class TimedEvent:
    """Something to send at a position measured in beats from zero."""

    beat: float
    order: int = field(compare=True, default=0)
    message: Message | None = field(compare=False, default=None)
    label: str = field(compare=False, default="")


class Transport:
    """Shared musical time: converts beats to seconds against one origin."""

    def __init__(self, bpm: float) -> None:
        if bpm <= 0:
            raise ValueError("bpm must be positive")
        self.bpm = float(bpm)
        self.beat_seconds = 60.0 / self.bpm
        self.started_at: float | None = None

    def start(self, at: float | None = None) -> float:
        self.started_at = time.perf_counter() if at is None else at
        return self.started_at

    def time_of(self, beat: float) -> float:
        """Absolute wall-clock time of a beat position."""

        if self.started_at is None:
            raise RuntimeError("transport has not been started")
        return self.started_at + beat * self.beat_seconds

    def wait_until(self, target: float, stop: Event) -> bool:
        """Sleep until ``target``. Returns True if stopped early.

        Sleeps short of the target and then yields in a tight loop, because a
        plain sleep overshoots by more than a MIDI pulse is long.
        """

        while True:
            remaining = target - time.perf_counter()
            if remaining <= 0:
                return stop.is_set()
            if remaining > 0.002:
                if stop.wait(remaining - 0.001):
                    return True
            else:
                time.sleep(0)


class MidiClock(Thread):
    """Sends MIDI beat clock so a DAW can follow Kosmos.

    In Ableton Live: Preferences > Link/Tempo/MIDI, set the Kosmos clock port
    to Sync = On, then switch the transport to EXT. Live follows start, stop
    and tempo from here.
    """

    def __init__(self, outport, transport: Transport, send_song_position: bool = True):
        super().__init__(daemon=True, name="kosmos-clock")
        self.outport = outport
        self.transport = transport
        self.send_song_position = send_song_position
        self._stopped = Event()
        self.pulses_sent = 0

    def stop(self) -> None:
        self._stopped.set()

    def run(self) -> None:
        pulse_seconds = self.transport.beat_seconds / PPQN
        try:
            if self.send_song_position:
                # Tell the DAW to start from the top before starting.
                self.outport.send(Message("songpos", pos=0))
            self.outport.send(Message("start"))

            pulse = 0
            while not self._stopped.is_set():
                target = self.transport.started_at + pulse * pulse_seconds
                if self.transport.wait_until(target, self._stopped):
                    break
                self.outport.send(Message("clock"))
                self.pulses_sent += 1
                pulse += 1
        finally:
            try:
                self.outport.send(Message("stop"))
            except Exception:
                pass


class Sequencer(Thread):
    """Plays one ordered list of events against the transport."""

    def __init__(self, events: Sequence[TimedEvent], outport, transport: Transport):
        super().__init__(daemon=True, name="kosmos-sequencer")
        self.events = sorted(events)
        self.outport = outport
        self.transport = transport
        self._stopped = Event()
        self.sent = 0
        self.late_events = 0
        self.worst_lateness_ms = 0.0

    def stop(self) -> None:
        self._stopped.set()

    @property
    def length_beats(self) -> float:
        return self.events[-1].beat if self.events else 0.0

    def run(self) -> None:
        for event in self.events:
            target = self.transport.time_of(event.beat)
            if self.transport.wait_until(target, self._stopped):
                return
            lateness = (time.perf_counter() - target) * 1000.0
            if lateness > 5.0:
                self.late_events += 1
                self.worst_lateness_ms = max(self.worst_lateness_ms, lateness)
            if event.message is not None:
                self.outport.send(event.message)
                self.sent += 1


def panic(outport, channels: Iterable[int] = range(16)) -> None:
    """All notes off, on every channel. Used on the way out."""

    for channel in channels:
        outport.send(Message("control_change", control=123, value=0, channel=channel))
