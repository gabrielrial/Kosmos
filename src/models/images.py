"""Images produced by the preparation stage."""

from dataclasses import dataclass
from typing import Optional

from PIL import Image


@dataclass
class Images:
    """The working image and its size.

    ``original_img`` is the image after resizing to the configured working
    size, so every measurement downstream is in working-image pixels.
    ``source_size`` keeps the original file's size for reporting.
    """

    original_img: Optional[Image.Image] = None
    saturated_img: Optional[Image.Image] = None
    width: int = 0
    height: int = 0
    source_size: tuple[int, int] = (0, 0)
    scale: float = 1.0

    @property
    def longest_side(self) -> int:
        return max(self.width, self.height)
