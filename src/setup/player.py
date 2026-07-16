from src.midi.clock import MidiClockGenerator
from src.midi.star_player import StarMidiPlayer
from src.midi.color_bass_player import ColorBassPlayer


class PlayerFactory:

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def run(self):

        self._create_clock()
        self._create_star_player()
        self._create_bass_player()

    def _create_clock(self):

        clock_port = self.pipeline.ports["kosmos_clock"]

        self.pipeline.clock_gen = MidiClockGenerator(
            clock_port,
            self.pipeline.tempo
        )

    def _create_star_player(self):

        stars = (
            self.pipeline.small_stars +
            self.pipeline.big_stars
        )

        if not stars:
            return

        self.pipeline.star_player = StarMidiPlayer(
            stars=stars,
            outport=self.pipeline.ports["kosmos_stars"],
            channel_base=3,
            speed_beats=self.pipeline.config.instrument.stars_speed_beats,
            tempo=self.pipeline.tempo,
            shuffle=True
        )

    def _create_bass_player(self):

        if not self.pipeline.dominant_colors:
            return

        self.pipeline.bass_player = ColorBassPlayer(
            dominant_colors=self.pipeline.dominant_colors,
            outport=self.pipeline.ports["kosmos_bass"],
            channel_base=0,
            speed_beats=0.4,
            max_note_duration_beats=self.pipeline.config.instrument.bass_max_note_duration_beats,
            tempo=self.pipeline.tempo
        )