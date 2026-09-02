from dataclasses import dataclass, field
from typing import List

from models.chords import Chord
from models.color import Color


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

    filter_curve: List[float] = field(default_factory=list)
    note: List[int] = field(default_factory=list)
    chords: List[Chord] = field(default_factory=list)
    duration: List[int] = field(default_factory=list)
    dominant_colors: List[Color] = field(default_factory=list)
    start_offset: float = 0.0

@dataclass
class NebulaMidi:
    notes: List[int] = field(default_factory=list)
    chords: List[Chord] = field(default_factory=list)
    duration: List[int] = field(default_factory=list)
    filter_curve: List[float] = field(default_factory=list)
    start_offset: float = 0.0
