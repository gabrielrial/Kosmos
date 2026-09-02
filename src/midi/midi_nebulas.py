from typing import List
from models.nebula import NebulaMidi, Nebula
from midi.midi_composer import MidiFactory
from models.chords import Chord


class NebulasMidiFactory:
    def __init__(self, nebulas_midi: list[NebulaMidi], nebulas: list[Nebula]):
        self.nebulas: list[Nebula] = nebulas
        self.midi_factory = MidiFactory()
        self.nebulas_midi: list[NebulaMidi] = nebulas_midi

    def process(self):
        self.find_note_and_mode_for_nebulas()
        self.build_chords()
        


    def find_note_and_mode_for_nebulas(self):
        for nb in self.nebulas:
            nebula = NebulaMidi()
            for i in nb.dominant_colors:
                nebula.notes.append(self.midi_factory.color_to_note(i))
                nebula.mode.append(self.midi_factory.brightness_to_mode(i))
                print(f"Chords: {self.midi_factory.note_to_name(nebula.notes[-1])}")
                print(f"Mode: {self.midi_factory.brightness_to_mode(i)}")
            self.nebulas_midi.append(nebula)

    def build_chords(self):
        for nb in self.nebulas_midi:
            for note, mode in zip(nb.notes, nb.mode):
                chord = Chord(
                    chord_type=mode,
                    inversion=0,
                    root=note
                )

                nb.chords.append(chord.chord_maker())

                print(f"Chord: {nb.chords[-1]}")