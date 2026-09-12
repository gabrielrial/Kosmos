from __future__ import annotations

from typing import Any

from config.config import Config
from midi.device import MidiDevice
from models.tempo import Tempo


class MidiSetup:
    """Opens the virtual MIDI ports and holds the tempo.

    The clock itself lives in ``midi.transport`` now, because it has to share
    one time origin with the sequencer; a clock that keeps its own schedule is
    exactly what caused the layers to drift apart.
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.midi_devices: MidiDevice
        self.tempo: Tempo
        self.outport: dict[str, Any] = {}

    def init(self) -> "MidiSetup":
        self.tempo = Tempo(self.config.tempo)
        self.midi_devices = MidiDevice()
        print(f"[MIDI] ports open: {list(self.midi_devices.ports)}")
        return self
