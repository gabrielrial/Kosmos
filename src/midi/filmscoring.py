from typing import Sequence
from models.chords import Chord, ChordType

class Filmscoring:

    DEFAULT_GROUPS: Sequence[Sequence[int]] = (
        (11, 2, 5, 8),   # B, D, F, Ab
        (0, 3, 6, 9),    # C, Eb, F#, A
        (1, 4, 7, 10),   # Db, E, G, Bb
    )

    def possible_connections(self, src: int, dest: int) -> int:
        if (src + 3) % 12 == dest:
            return 1
        elif (src - 3) % 12 == dest:
            return 2
        elif (src + 4) % 12 == dest or (src - 4) % 12 == dest:
            return 2
        elif (src + 6) % 12 == dest or (src - 6) % 12 == dest:
            return 3
        elif (src + 1) % 12 == dest or (src - 1) % 12 == dest:
            return 4
        else:
            return 0

    def chord_connection(self, src: Chord, dest: Chord) -> Chord:

        if self.possible_connections == 1:
            if src.chord_type == ChordType.MAJOR:
                return
            if src.chord_type == ChordType.MINOR:
                if dest.chord_type == ChordType.MINOR:
                    return
                else:
                    # Buscar un acorde de paso
        elif self.possible_connections == 2:
            if src.chord_type == ChordType.MINOR:
                return
            if src.chord_type == ChordType.MAJOR:
                # Buscar un acorde de paso
