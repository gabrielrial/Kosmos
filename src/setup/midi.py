from midi.tempo import Tempo
from midi.device import MidiDevice
from config.config import Config
from midi.clock import MidiClockGenerator
from typing import Self, Any


class MidiSetup:

    def __init__(self, config: Config):

        self.config = config

        self.midi_devices: MidiDevice | None = None
        self.clock: MidiClockGenerator | None = None
        self.outport: dict[str, Any] = {}
        self.tempo: Tempo | None = None

    def init(self) -> Self:
        self.tempo = Tempo(self.config.tempo)
        self.midi_devices = MidiDevice()
        self.outport = self.midi_devices.create_instrument_outputs()
        return self
