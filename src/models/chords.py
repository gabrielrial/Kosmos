from typing import Sequence, Optional, List
from enum import Enum


from models.chord import Chord


class ChordType(Enum):
    MAJOR = (0, 4, 7)
    MINOR = (0, 3, 7)
    MAJOR_7 = (0, 4, 7, 11)
    MINOR_7 = (0, 3, 7, 10)
    DOMINANT_7 = (0, 4, 7, 10)
    DIMINISHED_7 = (0, 3, 6, 9)
    HALF_DIMINISHED_7 = (0, 3, 6, 10)
    MINOR_MAJOR_7 = (0, 3, 7, 11)

class Filmscoring:

    DEFAULT_GROUPS: Sequence[Sequence[int]] = (
        (11, 2, 5, 8),   # B, D, F, Ab
        (0, 3, 6, 9),    # C, Eb, F#, A
        (1, 4, 7, 10),   # Db, E, G, Bb
    )

    def possible_connections(self, src: int, dest: int) -> int:
        if src == dest:
            return 1
        if (src + 3) % 12 == dest:
            return 2

        if (src - 3) % 12 == dest:
            return 3

        if (src + 4) % 12 == dest or (src - 4) % 12 == dest:
            return 4

        if (src + 6) % 12 == dest or (src - 6) % 12 == dest:
            return 5

        if (src + 1) % 12 == dest:
            return 6

        if (src - 1) % 12 == dest:
            return 7

        return 0

    def valid_chord_connection(
        self,
        connection: int,
        src: Chord,
        dest: Chord,
    ) -> bool:

        if connection == 1:
            return True

        if connection == 2:
            # +3 semitones
            if src.chord_type == ChordType.MAJOR:
                return True

            if src.chord_type == ChordType.MINOR:
                return dest.chord_type == ChordType.MINOR

        elif connection == 3:
            # -3 semitones
            if src.chord_type == ChordType.MINOR:
                return True

            if src.chord_type == ChordType.MAJOR:
                return dest.chord_type == ChordType.MAJOR

        elif connection == 4:
            # ±4 semitones
            return (
                src.chord_type == ChordType.MAJOR
                and dest.chord_type == ChordType.MAJOR
            )

        elif connection == 5:
            # ±6 semitones
            return True

        elif connection == 6:
            # +1 semitone
            return (
                src.chord_type == ChordType.MAJOR
                and dest.chord_type == ChordType.MINOR
            )

        elif connection == 7:
            # -1 semitone
            return (
                src.chord_type == ChordType.MAJOR
                and dest.chord_type == ChordType.MAJOR
            )

        return False

    def possible_intermediate_chords(
        self,
        src: Chord,
        dest: Chord,
    ) -> List[Chord]:

        candidates = []

        for root in range(12):

            if root == src.root:
                continue

            connection = self.possible_connections(
                src.root,
                root,
            )

            if connection == 0:
                continue

            for chord_type in (
                ChordType.MAJOR,
                ChordType.MINOR,
            ):
                candidate = Chord(
                    root=root,
                    chord_type=chord_type,
                )

                if self.valid_chord_connection(
                    connection,
                    src,
                    candidate,
                ):
                    candidates.append(candidate)

        return candidates

    def find_chord_path(
        self,
        src: Chord,
        dest: Chord,
        path: Optional[List[Chord]] = None,
        max_depth: int = 6,
    ) -> Optional[List[Chord]]:

        if path is None:
            path = [src]

        # Evitar caminos infinitos
        if len(path) > max_depth:
            return None

        # ¿Podemos llegar directamente al destino?
        connection = self.possible_connections(
            src.root,
            dest.root,
        )

        if self.valid_chord_connection(
            connection,
            src,
            dest,
        ):
            return path + [dest]

        # Buscar acordes intermedios
        for next_chord in self.possible_intermediate_chords(
            src,
            dest,
        ):

            result = self.find_chord_path(
                src=next_chord,
                dest=dest,
                path=path + [next_chord],
                max_depth=max_depth,
            )

            if result is not None:
                return result

        return None

    def chord_connection(
        self,
        src: Chord,
        dest: Chord,
    ) -> Optional[List[Chord]]:

        connection = self.possible_connections(
            src.root,
            dest.root,
        )

        if self.valid_chord_connection(
            connection,
            src,
            dest,
        ):
            print(f"Chords: {src} and {dest} are valid")
            return [src, dest]

        print(f"Chords: {src} and {dest} are not valid")

        return self.find_chord_path(
            src=src,
            dest=dest,
        )