from models.color import Color

from models.chords import ChordType

class MidiFactory:
    def __init__(self):
        pass

    def note_to_name(self, note: int) -> str:
        notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

        return notes[note % 12]

    def brightness_to_mode(self, color: Color) -> ChordType:
        # Color.brightness is now normalised 0-1 like every other colour field.
        if color.brightness > 0.5:
            return ChordType.MAJOR
        else:
            return ChordType.MINOR

    def color_to_note(self, color: Color) -> int:
        """
        Return a value between 0 - 11, corresponding to each note from C - B
        """
        # Color.hue is 0-1 around the wheel, so 12 steps span an octave.
        return round(color.hue * 12) % 12

    def nebula_chord_composer(self):

        colors = list(getattr(self.nebula, "dominant_colors", []) or [])
        print(colors)
        for nb in self.nebulae:

            for color in nb.dominant_colors:

                note = self.color_to_note(color)
                nb.note.append(note)

                print(f"Valor de nota: {note} : {self.note_to_name(note)}")
