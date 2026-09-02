from models.color import Color


class MidiFactory:
    def __init__(self):
        pass

    def note_to_name(note: int) -> str:
        notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

        return notes[note % 12]

    def brightness_to_mode(brightness: float) -> bool:
        if brightness > 0.5:
            return True
        else:
            return False

    def color_to_note(color: Color) -> int:
        """
        Return a value between 0 - 11, corresponding to each note from C - B
        """
        return round(color.hue / 30) % 12

    def nebula_chord_composer(self):

        colors = list(getattr(self.nebula, "dominant_colors", []) or [])
        print(colors)
        for nb in self.nebulae:

            for color in nb.dominant_colors:

                note = self.color_to_note(color)
                nb.note.append(note)

                print(f"Valor de nota: {note} : {self.note_to_name(note)}")
