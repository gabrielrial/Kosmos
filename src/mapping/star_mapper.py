"""Turning measurements into notes.

This is the only place that decides how a star sounds. The detector produces
measurements; this module produces MIDI values. Keeping them apart means a new
mapping never requires editing a detector, and the mapping can be tested
without opening a MIDI port.

Provisional: the register bands and durations here are a starting point, not
a result. They are the values to argue with.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from models.star import Star, Stars


@dataclass
class NoteEvent:
    """One note ready to be sent. Field names match what the player reads."""

    x: int
    y: int
    note: int
    velocity: int
    pan: int
    duration: float
    channel: int
    pan_cc: int = 7


@dataclass
class LayerSpec:
    """How one layer of stars is voiced."""

    low_note: int
    high_note: int
    duration_beats: float
    channel: int
    pan_cc: int = 7


class StarMapper:
    """Maps detected sources onto notes.

    Pitch comes from the colour index rather than from HSV hue. On this image
    set, between 21% and 73% of detected sources have a saturation below 0.15,
    and for those the hue is numerically unstable: their hue-derived pitch
    classes came out at 3.15-3.53 bits of entropy against a 3.58-bit maximum,
    which is to say indistinguishable from random. The colour index
    (B-R)/(B+R) is a ratio rather than an angle, so it stays meaningful on a
    near-white star, and it carries real meaning: positive is a hot blue star,
    negative a cool red one.
    """

    def __init__(
        self,
        small: LayerSpec,
        big: LayerSpec,
        pitch_classes: set[int] | None = None,
        velocity_range: tuple[int, int] = (45, 115),
    ) -> None:
        self.small = small
        self.big = big
        self.pitch_classes = pitch_classes or set(range(12))
        self.velocity_range = velocity_range

    def map(self, stars: Stars, image_width: int) -> tuple[list[NoteEvent], list[NoteEvent]]:
        """Return ``(small_events, big_events)``."""

        colours = np.array([star.color_index for star in stars.all], dtype=np.float64)
        if len(colours) == 0:
            return [], []

        # Normalise the colour axis against this image, so a monochrome image
        # still uses the whole register instead of collapsing onto one note.
        low, high = np.percentile(colours, 2), np.percentile(colours, 98)
        span = max(high - low, 1e-6)

        return (
            self._layer(stars.small_stars, self.small, low, span, image_width),
            self._layer(stars.big_stars, self.big, low, span, image_width),
        )

    def _layer(
        self,
        stars: list[Star],
        spec: LayerSpec,
        low: float,
        span: float,
        image_width: int,
    ) -> list[NoteEvent]:
        if not stars:
            return []

        allowed = self._allowed_notes(spec)
        fluxes = np.array([star.flux for star in stars], dtype=np.float64)
        # Rank rather than raw flux: a single very bright source would
        # otherwise push every other note to the bottom of the velocity range.
        ranks = fluxes.argsort().argsort() / max(len(fluxes) - 1, 1)
        velocity_low, velocity_high = self.velocity_range

        events: list[NoteEvent] = []
        for star, rank in zip(stars, ranks):
            position = float(np.clip((star.color_index - low) / span, 0.0, 1.0))
            note = allowed[min(int(position * len(allowed)), len(allowed) - 1)]
            events.append(
                NoteEvent(
                    x=star.x,
                    y=star.y,
                    note=note,
                    velocity=int(
                        round(velocity_low + rank * (velocity_high - velocity_low))
                    ),
                    pan=int(round(np.clip(star.x / max(image_width - 1, 1), 0, 1) * 127)),
                    duration=spec.duration_beats,
                    channel=spec.channel,
                    pan_cc=spec.pan_cc,
                )
            )
        return events

    def _allowed_notes(self, spec: LayerSpec) -> list[int]:
        notes = [
            note
            for note in range(spec.low_note, spec.high_note + 1)
            if note % 12 in self.pitch_classes
        ]
        return notes or list(range(spec.low_note, spec.high_note + 1))
