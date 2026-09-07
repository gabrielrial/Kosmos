"""
Star detector in processed images.

Detects bright regions and classifies them as small or large stars.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from models.images import Images
from models.star import Stars, SmallStar, BigStar
from config.config import StarDetectorConfig


class StarDetector:
    """Detects and classifies stars in images."""

    # Add config file

    def __init__(self, images: Images, stars: Stars, config: StarDetectorConfig):
        self.images = images
        self.config = config
        self.stars = stars

    def detect(self) -> None:
        """
        Detects stars in a processed image.

        Iterates through each pixel looking for white/bright pixels in the detection image.
        For each one, searches for the brightest connected region and classifies it by area.

        RGB colors are obtained from color_source_image (or from image if not provided).

        Classification criteria:
        - SmallStar: 0 < area < 10 pixels
        - BigStar: 10 <= area < 20 pixels

        Args:
            image: Image to detect bright pixels (typically simplified)
            color_source_image: Image to get RGB colors from (optional, defaults to 'image')
                                  Useful for getting colors from saturated original image

        Returns:
            Tuple (small_stars, big_stars)
        """

        width, height = self.images.width, self.images.height
        color_source_image = self.images.original_img
        if self.images.saturated_img is not None:
            color_source_image = self.images.saturated_img
        original = np.asarray(self.images.original_img, dtype=np.float32)
        luminance = (
            0.2126 * original[:, :, 0]
            + 0.7152 * original[:, :, 1]
            + 0.0722 * original[:, :, 2]
        )
        background = np.asarray(
            self.images.original_img.filter(
                ImageFilter.GaussianBlur(self.config.local_background_radius)
            ),
            dtype=np.float32,
        )
        background_luminance = (
            0.2126 * background[:, :, 0]
            + 0.7152 * background[:, :, 1]
            + 0.0722 * background[:, :, 2]
        )
        response = luminance - background_luminance
        threshold = self._adaptive_threshold(response)
        peaks = self._find_peaks(response, luminance, threshold)
        color_pixels = color_source_image.load()

        for bx, by in peaks:
            area = self._measure_area(response, bx, by, threshold)
            if area < self.config.minimum_area:
                continue

            rgb = color_pixels[bx, by]
            brightness = sum(rgb) / 3
            note = int(brightness * 35 / 255) + 36
            velocity = int(max(50, min(brightness, 255)) * 60 / 205) + 40
            star_data = dict(
                x=bx,
                y=by,
                note=note,
                velocity=velocity,
                pan=(bx * 127) / width,
                area=area,
                rgb_color=rgb,
            )
            if area <= self.config.small_star_max_area:
                self.stars.small_stars.append(SmallStar(**star_data))
            else:
                self.stars.big_stars.append(BigStar(**star_data))

        # Guardar imagen con estrellas sobre fondo negro
        print(f"Stars detected: {len(self.stars.big_stars) + len(self.stars.small_stars)}")
        self._save_stars_image()

    def _adaptive_threshold(self, response: np.ndarray) -> float:
        """Estimate a robust threshold from the image's local-background noise."""

        median = float(np.median(response))
        mad = float(np.median(np.abs(response - median)))
        noise = max(1.4826 * mad, 1.0)
        return max(
            self.config.minimum_contrast,
            median + self.config.detection_sigma * noise,
        )

    def _find_peaks(
        self, response: np.ndarray, luminance: np.ndarray, threshold: float
    ) -> list[tuple[int, int]]:
        """Find local maxima and suppress neighboring detections."""

        radius = max(1, self.config.minimum_distance)
        height, width = response.shape
        local_max = np.ones_like(response, dtype=bool)
        padded = np.pad(response, radius, mode="edge")
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx == 0 and dy == 0:
                    continue
                local_max &= response >= padded[
                    radius + dy : radius + dy + height,
                    radius + dx : radius + dx + width,
                ]

        candidate_y, candidate_x = np.nonzero(
            local_max
            & (response >= threshold)
            & (luminance >= self.config.minimum_brightness)
        )
        candidates = sorted(
            zip(candidate_x.tolist(), candidate_y.tolist()),
            key=lambda point: response[point[1], point[0]],
            reverse=True,
        )
        accepted: list[tuple[int, int]] = []
        min_distance_squared = radius * radius
        for point in candidates:
            if all(
                (point[0] - other[0]) ** 2 + (point[1] - other[1]) ** 2
                >= min_distance_squared
                for other in accepted
            ):
                accepted.append(point)
        return accepted

    def _measure_area(self, response: np.ndarray, x: int, y: int, threshold: float) -> int:
        radius = max(1, self.config.measurement_radius)
        y0, y1 = max(0, y - radius), min(response.shape[0], y + radius + 1)
        x0, x1 = max(0, x - radius), min(response.shape[1], x + radius + 1)
        patch = response[y0:y1, x0:x1]
        yy, xx = np.ogrid[y0:y1, x0:x1]
        disk = (xx - x) ** 2 + (yy - y) ** 2 <= radius * radius
        return int(np.count_nonzero(disk & (patch >= threshold * 0.35)))

    def _save_star_preview(
        self,
        image,
        bx: int,
        by: int,
        is_big_star: bool = False,
        preview_size: int = 25,
    ) -> None:
        """
        Saves a preview of a detected star.

        Args:
            image: PIL Image object
            bx, by: Coordinates of the brightest pixel
            is_big_star: Whether it is a big star
            preview_size: Crop radius around the center
        """

        width, height = image.size
        left = max(0, bx - preview_size)
        top = max(0, by - preview_size)
        right = min(width, bx + preview_size)
        bottom = min(height, by + preview_size)

        star_img = image.crop((left, top, right, bottom)).convert("RGB")

        # Mark the center in red
        cx = (right - left) // 2
        cy = (bottom - top) // 2
        star_img.putpixel((cx, cy), (255, 0, 0))

        # Save with descriptive name
        count = len(self.stars.small_stars)
        filename = f"small_{count}.png"
        star_img.save(filename)

    def _save_stars_image(self) -> None:
        """
        Creates an image with black background and draws all stars with their colors.

        Args:
            original_image: Original image (for size reference)
            width: Image width
            height: Image height
        """
        # Create black image
        img_copy = self.images.original_img.copy()
        draw = ImageDraw.Draw(img_copy)

        # Draw all stars with their original RGB color

        for star in self.stars.small_stars + self.stars.big_stars:
            x, y = star.x, star.y
            rgb = (
                star.rgb_color if star.rgb_color else (255, 255, 255)
            )  # White by default

            # Draw the pixel in the original color
            draw.point((x, y), fill=rgb)

            # Draw a small circle around for better visibility
            radius = 5 if star.area < 30 else 10
            left = max(0, x - radius)
            top = max(0, y - radius)
            right = min(self.images.width, x + radius)
            bottom = min(self.images.height, y + radius)

            draw.ellipse([left, top, right, bottom], outline=rgb)

        # Save image
        output_path = "stars_detected.png"
        img_copy.save(output_path)
        print(f"[OK] Stars image saved to: {output_path}")
