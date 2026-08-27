from enum import Enum

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
        note: int,
        chord_type: ChordType,
        inversion: int = 0
    ):
        self.note = note
        self.chord_type = chord_type
        self.inversion = inversion

    def chord_maker(self):
        notes = [
            self.note + interval
            for interval in self.chord_type.value
        ]

        for _ in range(self.inversion):
            notes.append(notes.pop(0) + 12)

        return notes
