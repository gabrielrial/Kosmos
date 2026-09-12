"""Writing the timeline to a Standard MIDI File.

The same event list that the sequencer plays live is what gets written here,
so the file and the live performance are the same piece by construction
rather than by two code paths agreeing.

Why bother, when Kosmos can already play live: a file dragged into a DAW has
no timing error at all. Live playback is limited by how precisely a general
purpose operating system can wake a thread — a few milliseconds of jitter
that no amount of Python can remove. In a file the events are numbers on a
grid, and the DAW's own real-time engine plays them. Live playback is for
exploring; the file is for producing.

One track per MIDI channel, because that is what a DAW splits into separate
instrument tracks on import.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterable, Sequence

from midi.messages import (
    encode_end_of_track,
    encode_event,
    encode_meta_name,
    encode_meta_tempo,
    write_midi_file,
)
from midi.transport import TimedEvent

DEFAULT_TICKS_PER_BEAT = 960

_TRACK_NAMES = {
    0: "Kosmos Nebulae",
    3: "Kosmos Small Stars",
    5: "Kosmos Big Stars",
}


class MidiSheet:
    """Renders a beat-positioned timeline to a .mid file."""

    def __init__(
        self,
        ticks_per_beat: int = DEFAULT_TICKS_PER_BEAT,
        bpm: float = 90.0,
        track_names: dict[int, str] | None = None,
    ) -> None:
        self.ticks_per_beat = ticks_per_beat
        self.bpm = bpm
        self.track_names = track_names or _TRACK_NAMES
        self.note_count = 0
        self.track_count = 0

    # ------------------------------------------------------------------
    def build(self, timeline: Sequence[TimedEvent]) -> list[bytes]:
        """Encode the timeline as SMF track payloads."""

        # Track 0 carries tempo only, which is the convention a DAW expects.
        tempo_track = encode_meta_name("Kosmos") + encode_meta_tempo(
            int(round(60_000_000 / self.bpm))
        ) + encode_end_of_track()
        tracks = [tempo_track]

        by_channel: dict[int, list[TimedEvent]] = defaultdict(list)
        for event in timeline:
            if event.message is None:
                continue
            by_channel[int(getattr(event.message, "channel", 0))].append(event)

        for channel in sorted(by_channel):
            tracks.append(self._track(channel, by_channel[channel]))
        self.note_count = sum(
            1
            for events in by_channel.values()
            for event in events
            if event.message.type == "note_on"
        )
        self.track_count = len(by_channel)
        return tracks

    def _track(self, channel: int, events: Sequence[TimedEvent]) -> bytes:
        payload = encode_meta_name(
            self.track_names.get(channel, f"Kosmos ch{channel}")
        )

        # A MIDI file stores the gap since the previous message, not an
        # absolute position, so beat positions are converted to ticks first
        # and only then differenced. Rounding each gap on its own would let
        # the error accumulate down the track.
        previous_tick = 0
        for event in sorted(events, key=lambda item: (item.beat, item.order)):
            tick = int(round(event.beat * self.ticks_per_beat))
            delta = max(0, tick - previous_tick)
            previous_tick = tick
            payload += encode_event(event.message, delta)

        return payload + encode_end_of_track()

    # ------------------------------------------------------------------
    def save(self, timeline: Sequence[TimedEvent], path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_midi_file(path, self.ticks_per_beat, self.build(timeline))

        length = timeline[-1].beat if timeline else 0.0
        print(
            f"[File] {path}: {self.track_count} tracks, {self.note_count} notes, "
            f"{length:.1f} beats ({length * 60.0 / self.bpm:.0f}s at {self.bpm:g} BPM)"
        )
        return path
