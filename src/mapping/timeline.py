"""Builds the single event list that the sequencer plays.

Everything is positioned in beats from zero, before a note is sent. That is
what makes the layers agree: they are not two players started at the same
moment, they are one list.

Three things happen here that could not happen with separate players:

Density is capped per slice of the grid rather than globally. A detector that
finds six thousand stars would otherwise produce six thousand notes, which at
any usable tempo is a continuous texture and not a piece: measured on one
image, 1,815 notes over 324 beats came out at 8.4 notes per second with 914 of
them landing on the same instants. Keeping the loudest few per slice thins the
crowded parts while leaving quiet parts of the image quiet, so the music keeps
the image's own distribution instead of being flattened.

Star notes are fitted to the chord that is actually sounding underneath them,
not to the union of every chord in the piece. With ten nebulae that union was
all twelve pitch classes, so the old harmonic constraint constrained nothing.

And note lengths are clipped at the chord change, so a star never holds
through into a chord it does not belong to.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from midi.messages import Message

from mapping.star_mapper import NoteEvent
from midi.transport import TimedEvent
from models.nebula import NebulaMidi


@dataclass
class ChordSpan:
    """One chord occupying a stretch of the timeline."""

    start_beat: float
    end_beat: float
    notes: tuple[int, ...]
    root: int
    channel: int = 0
    velocity: int = 72

    @property
    def pitch_classes(self) -> set[int]:
        return {note % 12 for note in self.notes}


def chord_spans(
    nebulas: Sequence[NebulaMidi], channel: int = 0, velocity: int = 72
) -> list[ChordSpan]:
    """Lay every nebula's chords end to end on the beat grid."""

    spans: list[ChordSpan] = []
    cursor = 0.0
    for nebula in nebulas:
        for chord, duration in zip(nebula.chords, nebula.duration):
            length = float(duration)
            if length <= 0:
                continue
            spans.append(
                ChordSpan(
                    start_beat=cursor,
                    end_beat=cursor + length,
                    notes=tuple(chord.chord_maker()),
                    root=int(chord.root),
                    channel=channel,
                    velocity=velocity,
                )
            )
            cursor += length
    return spans


def quantise(beat: float, grid: float, strength: float = 1.0) -> float:
    """Pull a beat position towards the nearest grid line.

    ``strength`` 1.0 snaps exactly, 0.0 leaves it alone, and values between
    move it part of the way, which keeps some of the image's own irregularity
    while still letting a pulse be felt.
    """

    if grid <= 0 or strength <= 0:
        return beat
    snapped = round(beat / grid) * grid
    return beat + (snapped - beat) * min(strength, 1.0)


def _active_span(spans: Sequence[ChordSpan], beat: float) -> ChordSpan | None:
    for span in spans:
        if span.start_beat <= beat < span.end_beat:
            return span
    return spans[-1] if spans and beat >= spans[-1].end_beat else None


def fit_to_chord(note: int, allowed: set[int], low: int, high: int) -> int:
    """Move a note to the nearest pitch of the chord sounding under it."""

    if not allowed:
        return note
    candidates = [value for value in range(low, high + 1) if value % 12 in allowed]
    if not candidates:
        return note
    return min(candidates, key=lambda value: (abs(value - note), value))


class TimelineBuilder:
    """Turns chords and star notes into one ordered list of MIDI events."""

    def __init__(
        self,
        *,
        total_beats: float,
        grid: float = 0.25,
        quantise_strength: float = 1.0,
        fit_stars_to_chord: bool = True,
        notes_per_slice: int = 0,
        duration_scale: float = 1.0,
    ) -> None:
        self.total_beats = total_beats
        self.grid = grid
        self.quantise_strength = quantise_strength
        self.fit_stars_to_chord = fit_stars_to_chord
        self.notes_per_slice = notes_per_slice
        self.duration_scale = duration_scale
        self.spans: list[ChordSpan] = []
        self.dropped = 0

    # ------------------------------------------------------------------
    def build(
        self,
        spans: Sequence[ChordSpan],
        star_layers: Iterable[tuple[str, Sequence[NoteEvent], int, int]],
        image_height: int,
    ) -> list[TimedEvent]:
        """Assemble the timeline.

        ``star_layers`` is a sequence of ``(name, events, low_note, high_note)``.
        Star timing comes from y position: the playhead is a horizontal line
        sweeping down the image, so everything on that line sounds together and
        the horizontal axis is left free for stereo position.
        """

        self.spans = list(spans)
        timeline: list[TimedEvent] = []
        order = 0

        for span in self.spans:
            for note in span.notes:
                timeline.append(
                    TimedEvent(
                        beat=span.start_beat,
                        order=order,
                        message=Message(
                            "note_on",
                            note=note,
                            velocity=span.velocity,
                            channel=span.channel,
                        ),
                        label="chord_on",
                    )
                )
                order += 1
                timeline.append(
                    TimedEvent(
                        beat=span.end_beat,
                        order=order,
                        message=Message(
                            "note_off", note=note, velocity=0, channel=span.channel
                        ),
                        label="chord_off",
                    )
                )
                order += 1

        span_end = self.spans[-1].end_beat if self.spans else self.total_beats
        self.dropped = 0
        for _, events, low, high in star_layers:
            placed = [
                (
                    quantise(
                        (event.y / max(image_height - 1, 1)) * span_end,
                        self.grid,
                        self.quantise_strength,
                    ),
                    event,
                )
                for event in events
            ]
            placed = self._thin(placed)
            for beat, event in placed:
                span = _active_span(self.spans, beat)
                note = event.note
                if span is not None and self.fit_stars_to_chord:
                    note = fit_to_chord(note, span.pitch_classes, low, high)

                end = beat + event.duration * self.duration_scale
                if span is not None:
                    # Never hold a note through into the next chord.
                    end = min(end, span.end_beat)
                if end <= beat:
                    end = beat + self.grid

                timeline.append(
                    TimedEvent(
                        beat=beat,
                        order=order,
                        message=Message(
                            "control_change",
                            control=event.pan_cc,
                            value=max(0, min(int(event.pan), 127)),
                            channel=event.channel,
                        ),
                        label="pan",
                    )
                )
                order += 1
                timeline.append(
                    TimedEvent(
                        beat=beat,
                        order=order,
                        message=Message(
                            "note_on",
                            note=note,
                            velocity=max(1, min(int(event.velocity), 127)),
                            channel=event.channel,
                        ),
                        label="star_on",
                    )
                )
                order += 1
                timeline.append(
                    TimedEvent(
                        beat=end,
                        order=order,
                        message=Message(
                            "note_off", note=note, velocity=0, channel=event.channel
                        ),
                        label="star_off",
                    )
                )
                order += 1

        timeline.sort()
        return timeline

    # ------------------------------------------------------------------
    def _thin(self, placed):
        """Keep at most ``notes_per_slice`` notes per grid slice.

        Which ones to keep is decided by velocity, which comes from the star's
        flux: the brightest star in a slice is the one that survives. That
        makes thinning a musical decision rather than an arbitrary one, and it
        keeps the result stable — the same image always drops the same notes.
        """

        if self.notes_per_slice <= 0:
            return placed

        by_slice: dict[float, list] = {}
        for beat, event in placed:
            key = round(beat / self.grid) if self.grid > 0 else beat
            by_slice.setdefault(key, []).append((beat, event))

        kept = []
        for group in by_slice.values():
            group.sort(key=lambda item: item[1].velocity, reverse=True)
            kept.extend(group[: self.notes_per_slice])
            self.dropped += max(0, len(group) - self.notes_per_slice)
        kept.sort(key=lambda item: item[0])
        return kept

    @staticmethod
    def check(timeline: Sequence[TimedEvent]) -> dict[str, int]:
        """Every note_on must have a matching note_off. Cheap and worth it."""

        open_notes: dict[tuple[int, int], int] = {}
        unmatched_off = 0
        for event in timeline:
            message = event.message
            if message is None or message.type not in ("note_on", "note_off"):
                continue
            key = (message.channel, message.note)
            if message.type == "note_on":
                open_notes[key] = open_notes.get(key, 0) + 1
            else:
                if open_notes.get(key, 0) == 0:
                    unmatched_off += 1
                else:
                    open_notes[key] -= 1
        return {
            "hanging_notes": sum(open_notes.values()),
            "unmatched_note_offs": unmatched_off,
        }
