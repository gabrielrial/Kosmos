"""Detected diffuse regions."""

from dataclasses import dataclass, field
from typing import List

from models.chord import Chord
from models.color import Color


@dataclass
class Nebula:
    """One diffuse region extracted from the mid-frequency band.

    x, y            intensity-weighted centroid, in working-image pixels
    width, height   bounding-box size
    area            pixels in the region
    area_frac       area as a fraction of the whole frame; this is the
                    scale-invariant size, and the one worth mapping
    density         area divided by bounding-box area
    elongation      bounding-box width divided by height
    brightness      mean brightness of the region, 0-1
    hue             mean hue, 0-1
    saturation      mean saturation, 0-1
    contrast        mean band-pass signal; how strongly it stands out from
                    the sky rather than how bright it is in absolute terms
    """

    x: int
    y: int
    width: int
    height: int
    area: int
    area_frac: float
    density: float
    elongation: float
    brightness: float
    hue: float
    saturation: float
    contrast: float

    filter_curve: List[float] = field(default_factory=list)
    dominant_colors: List[Color] = field(default_factory=list)

    @property
    def left(self) -> int:
        return self.x - self.width // 2

    @property
    def top(self) -> int:
        return self.y - self.height // 2


@dataclass
class NebulaMidi:
    notes: List[int] = field(default_factory=list)
    mode: List[object] = field(default_factory=list)
    chords: List[Chord] = field(default_factory=list)
    duration: List[float] = field(default_factory=list)
    filter_curve: List[float] = field(default_factory=list)
    start_offset: float = 0.0


@dataclass
class Nebulas:
    """Collection of diffuse regions detected in one image."""

    regions: list[Nebula] = field(default_factory=list)
