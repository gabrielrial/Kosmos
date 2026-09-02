from typing import List
from models.nebula import NebulaMidi, Nebula
from midi.midi_composer import MidiFactory

class NebulasMidiFactory:
    def __init__(self, nebulas_midi: list[NebulaMidi], nebulas: list[Nebula]):
        self.nebulas: list[Nebula] = nebulas
        self.midi_factory = MidiFactory()


    def process(self):
        for nb in self.nebulas:
            nebula = NebulaMidi()
            for i in nb.dominant_colors:
                print(i)