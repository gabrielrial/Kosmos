from models.star import Stars
from models.tempo import Tempo


class Quantizer:

    def __init__(
        self,
        stars: Stars,
        tempo: Tempo,
        width: int,
        ticks_per_beat: int = 960,
    ):
        self.stars: Stars = stars
        self.width: int = width
        self.tempo: Tempo = tempo
        self.ticks_per_beat: int = ticks_per_beat

        self._set_duration()

    def _set_duration(self):

        durations = self._get_possible_durations()

        section_width = self.width / len(durations)

        for star in self.stars.small_stars:
            index = int(star.x / section_width)
            index = min(index, len(durations) - 1)

            subdivision = durations[index]

            star.duration = int(self.ticks_per_beat / subdivision)

    def _get_possible_durations(self) -> list:
        """
        Returns all possible rhythmic subdivisions based on the tempo.
        """
        durations = []

        value = self.tempo.subdivision

        while value >= 1:
            durations.append(value)
            value /= 2

        return durations