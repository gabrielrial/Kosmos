from typing import Sequence, Optional, List

from models.chord import Chord
from models.chords import ChordType


class ChordProgression:

    DEFAULT_GROUPS: Sequence[Sequence[int]] = (
        (11, 2, 5, 8),  # B, D, F, Ab
        (0, 3, 6, 9),  # C, Eb, F#, A
        (1, 4, 7, 10),  # Db, E, G, Bb
    )

    def chord_connection(self, src: Chord, dest: Chord) -> Chord:
        """
        Returns dest if the connection is valid.

        Otherwise, searches for a passing chord.
        """

        connection = self.possible_connections(
            src.root,
            dest.root,
        )

        if self.valid_chord_connection(connection, src, dest):
            print(f"Chords: {src} and {dest} are valid")
            return dest

        print(f"Chords: {src} and {dest} are not valid")
        return self.find_chord_path(src=src, dest=dest)

    def possible_connections(self, src: int, dest: int) -> int:
        """
        Determines the type of connection between two root notes.

        Returns:
            0: same note
            1: +3 semitones
            2: -3 semitones
            3: ±4 semitones
            4: ±6 semitones
            5: +1 semitone
            6: -1 semitone
        """

        if (src + 3) % 12 == dest:
            return 1

        if (src - 3) % 12 == dest:
            return 2

        if (src + 4) % 12 == dest or (src - 4) % 12 == dest:
            return 3

        if (src + 6) % 12 == dest or (src - 6) % 12 == dest:
            return 4

        if (src + 1) % 12 == dest:
            return 5

        if (src - 1) % 12 == dest:
            return 6

        return 0

    def valid_chord_connection(
        self,
        connection: int,
        src: Chord,
        dest: Chord,
    ) -> bool:
        """
        Determines whether two chords can connect directly
        according to the connection type.
        """

        if connection == 1:
            # +3 semitones
            if src.chord_type == ChordType.MAJOR:
                return True

            if src.chord_type == ChordType.MINOR:
                return dest.chord_type == ChordType.MINOR

        elif connection == 2:
            # -3 semitones
            if src.chord_type == ChordType.MINOR:
                return True

            if src.chord_type == ChordType.MAJOR:
                return dest.chord_type == ChordType.MAJOR

        elif connection == 3:
            # ±4 semitones
            return (
                src.chord_type == ChordType.MAJOR and dest.chord_type == ChordType.MAJOR
            )

        elif connection == 4:
            return True

        elif connection == 5:
            # +1 semitone
            return (
                src.chord_type == ChordType.MAJOR and dest.chord_type == ChordType.MINOR
            )

        elif connection == 6:
            # -1 semitone
            return (
                src.chord_type == ChordType.MAJOR and dest.chord_type == ChordType.MAJOR
            )

        return False

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

        # Conexión directa
        connection = self.possible_connections(
            src.root,
            dest.root,
        )

        if self.valid_chord_connection(connection, src, dest):
            return path + [dest]

        # Explorar candidatos
        for next_chord in self.possible_intermediate_chords(src, dest):

            result = self.find_chord_path(
                next_chord,
                dest,
                path + [next_chord],
                max_depth,
            )

            if result is not None:
                return result

        return None

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
