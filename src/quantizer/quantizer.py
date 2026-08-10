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
            index = int(star.x / section_width)
            index = min(index, len(durations) - 1)

            subdivision = durations[index]

            star.duration = self.tempo.beat_duration / subdivision
            print(star.duration)

    def _get_possible_durations(self) -> list:
        """
            Returns a list with the all the time divisions based on the BPM given to the program.
        """
        durations = []

        value = self.tempo.subdivision

        while value >= 1:
            durations.append(value)
            value /= 2

        return durations
