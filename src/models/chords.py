from enum import Enum
from typing import Optional


class ChordType(Enum):
    MAJOR = (0, 4, 7)
    MINOR = (0, 3, 7)
    MAJOR_7 = (0, 4, 7, 11)
    MINOR_7 = (0, 3, 7, 10)
    DOMINANT_7 = (0, 4, 7, 10)
    DIMINISHED_7 = (0, 3, 6, 9)
    HALF_DIMINISHED_7 = (0, 3, 6, 10)
    MINOR_MAJOR_7 = (0, 3, 7, 11)


class Chord:
    def __init__(
        self,
        note: Optional[int] = None,
        chord_type: Optional[ChordType] = None,
        inversion: int = 0,
        root: Optional[int] = None,
        duration: Optional[float] = None,
    ):
        if root is not None:
            if note is not None and note != root:
                raise ValueError("Pass either note or root, not both with different values")
            note = root

        if note is None:
            raise ValueError("Chord requires a note/root value")
        if chord_type is None:
            chord_type = ChordType.MAJOR

        self.note = note
        self.root = note
        self.chord_type = chord_type
        self.inversion = inversion
        self.duration = duration

    @property
    def root_note(self):
        return self.root

    @root_note.setter
    def root_note(self, value):
        self.root = value
        self.note = value

    def chord_maker(self):
        notes = [
            self.root + interval
            for interval in self.chord_type.value
        ]

        for _ in range(self.inversion):
            notes.append(notes.pop(0) + 12)

        return notes

    def chord_notes(self):
        return self.chord_maker()
