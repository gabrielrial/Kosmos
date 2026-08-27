from dataclasses import dataclass


@dataclass
class Color:
    """Represents a dominant color inside a Nebula."""

    hue: float
    saturation: float
    brightness: float
    weight: float = 1.0
