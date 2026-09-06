"""Musical chord model used by the MIDI layer."""

from dataclasses import dataclass
from typing import Iterable

from models.star import Star


@dataclass(frozen=True, slots=True)
class Chord:
    """A group of MIDI notes that should sound at the same time.

    Notes are normalized to unique MIDI note numbers and stored in ascending
    order. A chord may be created directly from notes or from detected stars.
    """

    notes: tuple[int, ...]
    duration: float = 0.0
    velocity: int = 100
    channel: int = 0
    pan: int = 64

    def __post_init__(self) -> None:
        notes = tuple(sorted(set(self.notes)))
        if not notes:
            raise ValueError("A chord must contain at least one note")
        if any(not isinstance(note, int) or not 0 <= note <= 127 for note in notes):
            raise ValueError("Chord notes must be MIDI integers between 0 and 127")
        if self.duration < 0:
            raise ValueError("Chord duration cannot be negative")
        if not 1 <= self.velocity <= 127:
            raise ValueError("Chord velocity must be between 1 and 127")
        if not 0 <= self.channel <= 15:
            raise ValueError("Chord channel must be between 0 and 15")
        if not 0 <= self.pan <= 127:
            raise ValueError("Chord pan must be between 0 and 127")

        object.__setattr__(self, "notes", notes)

    @classmethod
    def from_stars(
        cls,
        stars: Iterable[Star],
        *,
        duration: float = 0.0,
        velocity: int | None = None,
        channel: int = 0,
        pan: int | None = None,
    ) -> "Chord":
        """Create a chord from the notes represented by detected stars."""

        stars = tuple(stars)
        if not stars:
            raise ValueError("At least one star is required to create a chord")

        average_velocity = round(sum(star.velocity for star in stars) / len(stars))
        average_pan = round(sum(star.pan for star in stars) / len(stars))
        return cls(
            notes=tuple(star.note for star in stars),
            duration=duration,
            velocity=average_velocity if velocity is None else velocity,
            channel=channel,
            pan=average_pan if pan is None else pan,
        )

    @property
    def root(self) -> int:
        """Return the lowest note in the chord."""

        return self.notes[0]

    def contains(self, note: int) -> bool:
        """Return whether the chord contains a MIDI note."""

        return note in self.notes

    def transposed(self, semitones: int) -> "Chord":
        """Return a copy transposed by the requested number of semitones."""

        return Chord(
            notes=tuple(note + semitones for note in self.notes),
            duration=self.duration,
            velocity=self.velocity,
            channel=self.channel,
            pan=self.pan,
        )
