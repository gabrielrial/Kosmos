
from models.color import Color

def note_to_name(note: int) -> str:
    notes = [
        "C", "C#", "D", "D#", "E", "F",
        "F#", "G", "G#", "A", "A#", "B"
    ]

    return notes[note % 12]

def brightness_to_mode(brightness: float) -> bool:
    if brightness > 0.5:
        return True
    else:
        return False

def color_to_note(color: Color) -> int:
    '''
        Return a value between 0 - 11, corresponding to each note from C - B
    '''
    return round(color.hue / 30) % 12


