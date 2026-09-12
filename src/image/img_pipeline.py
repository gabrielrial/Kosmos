"""Image preparation.

One job: load the file and bring it to the configured working size, so that
everything downstream measures the same thing regardless of which resolution
of an image you happen to have.

This matters more than it looks. Measured on one image at 450, 900 and 1800
pixels, the old detector found 142, 961 and 4,121 stars — 29 times more stars
for 16 times more pixels. Fixing the working size makes the number of notes a
decision instead of an accident.
"""

from __future__ import annotations

from PIL import Image, ImageEnhance

from config.config import ImageConfig
from models.images import Images


class ImagePipeLine:
    def __init__(self, image_path: str, config: ImageConfig) -> None:
        self.image_path = image_path
        self.config = config
        self.images = Images()

    def process(self) -> Images:
        self._load()
        return self.images

    def _load(self) -> None:
        image = Image.open(self.image_path).convert("RGB")
        source_size = image.size
        scale = 1.0

        target = self.config.working_size
        if target > 0 and max(source_size) > target:
            scale = target / max(source_size)
            image = image.resize(
                (
                    max(1, round(source_size[0] * scale)),
                    max(1, round(source_size[1] * scale)),
                ),
                Image.LANCZOS,
            )

        self.images.original_img = image
        self.images.width, self.images.height = image.size
        self.images.source_size = source_size
        self.images.scale = scale

        if scale < 1.0:
            print(
                f"[Image] {source_size[0]}x{source_size[1]} resized to "
                f"{image.size[0]}x{image.size[1]} (working size {target})"
            )
        else:
            print(f"[Image] {image.size[0]}x{image.size[1]}, no resize needed")

    def saturate(self) -> Image.Image:
        """Saturated copy, for colour sampling. Not part of the default path."""

        enhancer = ImageEnhance.Color(self.images.original_img)
        self.images.saturated_img = enhancer.enhance(self.config.saturation_boost)
        return self.images.saturated_img
