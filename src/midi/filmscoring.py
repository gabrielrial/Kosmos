from typing import Iterable, List, Sequence


class Filmscoring:

    DEFAULT_GROUPS: Sequence[Sequence[int]] = (
        (11, 2, 5, 8),  # B, D, F, Ab
        (0, 3, 6, 9),  # C, Eb, F#, A
        (1, 4, 7, 10),  # Db, E, G, Bb
    )

    def possible_connections(self, src: int, dest: int):
        src 
