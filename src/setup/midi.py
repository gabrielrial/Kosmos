from models.tempo import Tempo
from midi.device import MidiDevice
from config.config import Config
from midi.clock import MidiClockGenerator
from typing import Self, Any
from config.config import TempoConfig


class MidiSetup:

    def __init__(self, config: Config):

        print("[PROCESS] MidiSetup")

        self.midi_devices: MidiDevice
        self.clock: MidiClockGenerator

        self.config = config
        self.outport: dict[str, Any] = {}
        self.tempo: Tempo

    def init(self) -> Self:
        self.tempo = Tempo(self.config.tempo)
        self.midi_devices = MidiDevice()
        self.clock = MidiClockGenerator(self.midi_devices.get_port("kosmos_clock"), self.tempo)
        return self
