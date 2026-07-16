from midi.tempo import Tempo
from midi.device import MidiDevice


class MidiSetup:

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def init(self):
        self._setup_tempo()
        self._setup_device()

    def _setup_tempo(self):

        self.pipeline.tempo = Tempo(
            self.pipeline.config.tempo.bpm
        )

    def _setup_device(self):

        self.pipeline.device = MidiDevice()

        self.pipeline.ports = (
            self.pipeline.device.create_instrument_outputs()
        )