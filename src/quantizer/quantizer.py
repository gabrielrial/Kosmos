from models.star import Stars
from midi.tempo import Tempo


class Quantizer:

    def __init__(self, stars: Stars, tempo: Tempo, width: int):
        self.stars: Stars = stars
        self.width: int = width
        self.tempo: Tempo = tempo

        self._set_duration()

    # def __quantization(self):

    def _set_duration(self):

        durations = self._get_possible_durations()

        section_width = self.width / len(durations)

        for star in self.stars.small_stars:
            print(f"Star: {star.note}")

            index = int(star.x / section_width)
            index = min(index, len(durations) - 1)

            subdivision = durations[index]

            star.duration = self.tempo.beat_duration / subdivision

    def _get_possible_durations(self) -> list:
        durations = []

        value = self.tempo.subdivision

        while value >= 1:
            durations.append(value)
            value /= 2

        return durations
