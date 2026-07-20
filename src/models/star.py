from dataclasses import dataclass, field


@dataclass
class Star:
    """
        Definition of a star.
    """
    x: int
    y: int
    note: int
    velocity: int
    pan: int
    area: float
    duration: float = 0.0
    rgb_color: tuple[int, int, int] | None = None

    def __post_init__(self):
        self.velocity = max(1, min(127, int(self.velocity)))


class SmallStar(Star):
    pass


class BigStar(Star):
    pass


@dataclass
class Stars:
    """
        Constelation of big and small stars.

        small_stars: []
        big_stars: []
    """
    small_stars: list[SmallStar] = field(default_factory=list)
    big_stars: list[BigStar] = field(default_factory=list)