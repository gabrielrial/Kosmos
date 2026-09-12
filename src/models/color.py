from dataclasses import dataclass


@dataclass(frozen=True)
class Color:
    """A representative colour of a detected region.

    All three components are normalised to 0.0-1.0. ``hue`` is a position on
    the colour wheel where 0.0 and 1.0 are both red; multiply by 360 for
    degrees. ``weight`` is this colour's share of the region's pixels, so the
    weights of one region's colours sum to 1.0.
    """

    hue: float
    saturation: float
    brightness: float
    weight: float = 1.0

    @property
    def hue_degrees(self) -> float:
        return self.hue * 360.0
