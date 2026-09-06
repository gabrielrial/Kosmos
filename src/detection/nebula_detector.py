"""Detection of diffuse, extended emission regions."""

from collections import deque

import numpy as np
from PIL import Image, ImageFilter

from config.config import StarDetectorConfig
from models.images import Images
from models.nebula import Nebula, Nebulas


class NebulaDetector:
    """Finds large regions that differ from their local background."""

    def __init__(
        self, images: Images, nebulas: Nebulas, config: StarDetectorConfig
    ) -> None:
        self.images = images
        self.nebulas = nebulas
        self.config = config

    def detect(self) -> None:
        image = self.images.original_img
        rgb = np.asarray(image, dtype=np.float32)
        luminance = (
            0.2126 * rgb[:, :, 0]
            + 0.7152 * rgb[:, :, 1]
            + 0.0722 * rgb[:, :, 2]
        )
        chroma = rgb.max(axis=2) - rgb.min(axis=2)

        background_image = image.filter(
            ImageFilter.GaussianBlur(self.config.nebula_blur_radius)
        )
        background = np.asarray(background_image, dtype=np.float32)
        background_luminance = (
            0.2126 * background[:, :, 0]
            + 0.7152 * background[:, :, 1]
            + 0.0722 * background[:, :, 2]
        )

        local_contrast = luminance - background_luminance
        mask = (
            (local_contrast >= self.config.nebula_contrast_threshold)
            | (chroma >= self.config.nebula_saturation_threshold)
        ) & (luminance >= self.config.nebula_brightness_threshold)

        self._collect_regions(mask, rgb, local_contrast)

    def _collect_regions(
        self, mask: np.ndarray, rgb: np.ndarray, local_contrast: np.ndarray
    ) -> None:
        height, width = mask.shape
        visited = np.zeros_like(mask, dtype=bool)

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
            values = local_contrast[coordinates[:, 0], coordinates[:, 1]]
            weights = np.maximum(values, 1.0)
            center_y = float(
                np.average(coordinates[:, 0], weights=weights)
            )
            center_x = float(
                np.average(coordinates[:, 1], weights=weights)
            )
            mean_color = tuple(
                int(round(value))
                for value in rgb[coordinates[:, 0], coordinates[:, 1]].mean(axis=0)
            )
            min_x, min_y = coordinates[:, 1].min(), coordinates[:, 0].min()
            max_x, max_y = coordinates[:, 1].max(), coordinates[:, 0].max()

            self.nebulas.regions.append(
                Nebula(
                    x=center_x,
                    y=center_y,
                    area=area,
                    bbox=(int(min_x), int(min_y), int(max_x), int(max_y)),
                    rgb_color=mean_color,
                    contrast=float(values.mean()),
                )
            )
