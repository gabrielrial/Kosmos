"""Musical chord model used by the MIDI layer."""

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class Chord:
    """A group of MIDI notes that should sound at the same time.

    Notes are normalized to unique MIDI note numbers and stored in ascending
    order. A chord may be created directly from notes or from detected stars.
    """

    notes: tuple[int, ...] = ()
    root: int | None = None
    chord_type: object | None = None
    inversion: int = 0
    duration: float = 0.0
    velocity: int = 100
    channel: int = 0
    pan: int = 64

    def __post_init__(self) -> None:
        if self.root is not None and not 0 <= self.root <= 127:
            raise ValueError("Chord root must be between 0 and 127")
        notes = tuple(sorted(set(self.notes)))
        if not notes and self.root is None:
            raise ValueError("A chord must contain notes or a root")
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

        if self.root is None:
            object.__setattr__(self, "root", notes[0])
        else:
            object.__setattr__(self, "root", int(self.root))
        object.__setattr__(self, "notes", notes)

    def contains(self, note: int) -> bool:
        """Return whether the chord contains a MIDI note."""

        return note in self.notes

    def chord_maker(self) -> list[int]:
        """Build chord tones from the configured chord type and inversion.

        An inversion lifts the lowest notes an octave: the first inversion of
        C-E-G is E-G-C. Same chord, same harmonic function, different shape
        and a different bass note — which is what makes a repeated chord sound
        like a move rather than a stall.
        """

        if self.notes:
            return list(self.notes)
        intervals = getattr(self.chord_type, "value", (0, 4, 7))
        notes = [self.root + interval for interval in intervals]

        if self.inversion:
            for position in range(self.inversion % len(notes)):
                notes[position] += 12
            notes.sort()

        if any(note > 127 or note < 0 for note in notes):
            raise ValueError("Chord tones exceed MIDI note range")
        return notes

    def transposed(self, semitones: int) -> "Chord":
        """Return a copy transposed by the requested number of semitones."""

        return Chord(
            notes=tuple(note + semitones for note in self.chord_maker()),
            root=self.root + semitones,
            chord_type=self.chord_type,
            inversion=self.inversion,
            duration=self.duration,
            velocity=self.velocity,
            channel=self.channel,
            pan=self.pan,
        )
