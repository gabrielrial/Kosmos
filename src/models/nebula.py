from dataclasses import dataclass, field


@dataclass
class Nebula:
    """Diffuse emission region detected in an astronomical image."""

    x: float
    y: float
    area: int
    bbox: tuple[int, int, int, int]
    rgb_color: tuple[int, int, int]
    contrast: float


@dataclass
class Nebulas:
    regions: list[Nebula] = field(default_factory=list)
