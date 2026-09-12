"""Detected point sources.

These models carry measurements only. Notes, velocities and pan are decided
by the mapping layer (``mapping/``), never by the detector, so that changing
how the music sounds never means editing a detector.
"""

from dataclasses import dataclass, field


@dataclass
class Star:
    """One point source extracted from an image.

    x, y            position of the brightest pixel, in working-image pixels
    area            pixels above the detection threshold
    flux            sum of background-subtracted signal over those pixels;
                    this is aperture photometry, the closest thing here to a
                    real magnitude, and it is the value used to rank stars
    peak            brightest single pixel above the local background
    fill            area divided by bounding-box area. A sparse, ragged
                    shape scores low; a filled one scores high
    elongation      longer side of the bounding box over the shorter one. A
                    star is about 1.0. Needed alongside fill because a solid
                    bar fills its box completely and would otherwise pass
    rgb             mean colour over a small aperture around the centre
    color_index     (B - R) / (B + R). Positive is blue and hot, negative is
                    red and cool. Stays meaningful on near-white stars, where
                    HSV hue does not
    saturation      0-1, how much colour the source actually has. Below about
                    0.15 the hue of this star is noise
    """

    x: int
    y: int
    area: int
    flux: float
    peak: float
    fill: float
    elongation: float
    rgb: tuple[int, int, int]
    color_index: float
    saturation: float

    @property
    def magnitude(self) -> float:
        """Instrumental magnitude. Lower is brighter, as in astronomy."""

        from math import log10

        return -2.5 * log10(max(self.flux, 1e-6))


class SmallStar(Star):
    """A source below the flux split. The fast, dense layer."""


class BigStar(Star):
    """A source above the flux split. The sparse, low layer."""


@dataclass
class Stars:
    """Every source found in one image, split into the two playing layers."""

    small_stars: list[SmallStar] = field(default_factory=list)
    big_stars: list[BigStar] = field(default_factory=list)
    rejected: list[Star] = field(default_factory=list)
    flux_split: float = 0.0

    def __len__(self) -> int:
        return len(self.small_stars) + len(self.big_stars)

    @property
    def all(self) -> list[Star]:
        return [*self.small_stars, *self.big_stars]
