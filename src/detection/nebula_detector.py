"""Detection of diffuse, extended emission regions."""

from collections import deque

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from config.config import StarDetectorConfig
from models.images import Images
from detection.cloud_utils import CloudUtils
from models.color import Color
from models.nebula import Nebula


class NebulaDetector:
    """Finds large regions that differ from their local background."""

    def __init__(
        self, images: Images, stars, config
    ) -> None:
        self.images = images
        self.stars = stars
        self.config = config

    def detect(self) -> list[Nebula]:
        #image = self._remove_stars()
        rgb = np.asarray(self.images.original_img, dtype=np.float32)
        luminance = (
            0.2126 * rgb[:, :, 0]
            + 0.7152 * rgb[:, :, 1]
            + 0.0722 * rgb[:, :, 2]
        )
        chroma = rgb.max(axis=2) - rgb.min(axis=2)

        background_image = self.images.original_img.filter(
            ImageFilter.GaussianBlur(self.config.nebula_blur_radius)
        )
        #background_image = self.images.original_img.filter(
        #            ImageFilter.GaussianBlur(self.config.nebula_blur_radius)
        #        )
        background = np.asarray(background_image, dtype=np.float32)
        background_luminance = (
            0.2126 * background[:, :, 0]
            + 0.7152 * background[:, :, 1]
            + 0.0722 * background[:, :, 2]
        )

        local_contrast = luminance
        mask = (
            (local_contrast >= self.config.nebula_contrast_threshold)
            & (luminance >= self.config.nebula_brightness_threshold)
        ) | (
            (chroma >= self.config.nebula_saturation_threshold)
            & (luminance >= self.config.nebula_brightness_threshold)
            & (local_contrast >= self.config.nebula_contrast_threshold / 2)
        )

        regions, accepted_mask = self._collect_regions(mask, rgb, local_contrast)
        self._save_previews(regions, accepted_mask)
        return regions

    def _remove_stars(self) -> Image.Image:
        """Replace detected point sources with the blurred local background."""

        result = self.images.original_img.copy()
        blurred = self.images.blurred_img
        width, height = result.size
        for star in self.stars.small_stars + self.stars.big_stars:
            radius = max(3, int(np.sqrt(max(star.area, 1)) * 2))
            box = (
                max(0, star.x - radius),
                max(0, star.y - radius),
                min(width, star.x + radius + 1),
                min(height, star.y + radius + 1),
            )
            result.paste(blurred.crop(box), box[:2])
        return result

    def _collect_regions(
        self, mask: np.ndarray, rgb: np.ndarray, local_contrast: np.ndarray
    ) -> tuple[list[Nebula], np.ndarray]:
        height, width = mask.shape
        visited = np.zeros_like(mask, dtype=bool)
        regions: list[Nebula] = []
        accepted_mask = np.zeros_like(mask, dtype=bool)
        labels = np.zeros_like(mask, dtype=np.int32)
        hsv = np.asarray(Image.fromarray(rgb.astype(np.uint8), "RGB").convert("HSV"))
        label = 0

        for y, x in zip(*np.nonzero(mask)):
            if visited[y, x]:
                continue

            queue = deque([(int(x), int(y))])
            visited[y, x] = True
            points: list[tuple[int, int]] = []

            while queue:
                cx, cy = queue.pop()
                points.append((cx, cy))
                for nx in range(max(0, cx - 1), min(width, cx + 2)):
                    for ny in range(max(0, cy - 1), min(height, cy + 2)):
                        if not visited[ny, nx] and mask[ny, nx]:
                            visited[ny, nx] = True
                            queue.append((nx, ny))

            area = len(points)
            if area < self.config.nebula_min_area:
                continue
            if (
                self.config.nebula_max_area > 0
                and area > self.config.nebula_max_area
            ):
                continue
            coordinates = np.asarray([(py, px) for px, py in points])
            label += 1
            labels[coordinates[:, 0], coordinates[:, 1]] = label
            accepted_mask[coordinates[:, 0], coordinates[:, 1]] = True
            values = local_contrast[coordinates[:, 0], coordinates[:, 1]]
            weights = np.maximum(values, 1.0)
            center_y = float(
                np.average(coordinates[:, 0], weights=weights)
            )
            center_x = float(
                np.average(coordinates[:, 1], weights=weights)
            )
            min_x, min_y = coordinates[:, 1].min(), coordinates[:, 0].min()
            max_x, max_y = coordinates[:, 1].max(), coordinates[:, 0].max()

            hsv_values = hsv[coordinates[:, 0], coordinates[:, 1]]
            hue = float(np.mean(hsv_values[:, 0]) / 255)
            saturation = float(np.mean(hsv_values[:, 1]) / 255)
            brightness = float(np.mean(hsv_values[:, 2]) / 255)
            rgb_values = rgb[coordinates[:, 0], coordinates[:, 1]]
            dominant_colors = self._dominant_colors(rgb_values)
            nebula = Nebula(
                x=int(round(center_x)),
                y=int(round(center_y)),
                width=int(max_x - min_x + 1),
                height=int(max_y - min_y + 1),
                area=area,
                density=area / max(1, (max_x - min_x + 1) * (max_y - min_y + 1)),
                brightness=brightness,
                hue=hue,
                saturation=saturation,
                dominant_colors=dominant_colors,
            )
            nebula.filter_curve = CloudUtils._get_filter_curve(labels == label, nebula)
            regions.append(nebula)

        return regions, accepted_mask

    @staticmethod
    def _dominant_colors(rgb_values: np.ndarray, limit: int = 5) -> list[Color]:
        """Reduce a nebula to up to five weighted representative colors."""

        if len(rgb_values) == 0:
            return []
        pixels = Image.fromarray(
            rgb_values.astype(np.uint8).reshape(1, len(rgb_values), 3), mode="RGB"
        )
        quantized = pixels.quantize(colors=limit, method=Image.Quantize.MEDIANCUT)
        palette = quantized.getpalette()
        counts = quantized.getcolors() or []
        total = sum(count for count, _ in counts) or 1
        colors: list[Color] = []
        for count, index in counts:
            r, g, b = palette[index * 3 : index * 3 + 3]
            color_hsv = np.asarray(
                Image.new("RGB", (1, 1), (r, g, b)).convert("HSV")
            )[0, 0]
            hue, saturation, brightness = (float(channel) for channel in color_hsv)
            colors.append(
                Color(
                    hue=hue * 360 / 255,
                    saturation=saturation * 100 / 255,
                    brightness=brightness * 100 / 255,
                    weight=count / total,
                )
            )
        return colors

    def _save_previews(self, regions: list[Nebula], mask: np.ndarray) -> None:
        """Save the detected nebula regions for visual verification."""

        mask_image = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
        mask_image.save("nebulas.png")

        preview = self.images.original_img.convert("RGB").copy()
        draw = ImageDraw.Draw(preview)
        for index, nebula in enumerate(regions, start=1):
            left = nebula.x - nebula.width // 2
            top = nebula.y - nebula.height // 2
            right = left + nebula.width
            bottom = top + nebula.height
            draw.rectangle((left, top, right, bottom), outline=(255, 0, 0), width=2)
            draw.text((left, max(0, top - 14)), f"Nebula {index}", fill=(255, 0, 0))

        preview.save("nebula_debug.png")
        print("[OK] Nebula previews saved: nebulas.png, nebula_debug.png")
