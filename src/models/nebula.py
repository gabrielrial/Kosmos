from dataclasses import dataclass
from models.chords import Chord

@dataclass
class Nebula:
    x: int
    y: int
    width: int
    height: int
    area: int
    density: float

    # Average visual properties
    brightness: float
    hue: float
    saturation: float
    filter_curve: list[float] = None
    note: list [int] = 0
    chords: list [Chord] = 0
    duration: list [int] = 0
