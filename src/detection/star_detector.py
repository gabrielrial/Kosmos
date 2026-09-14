"""Point-source extraction.

The method is standard source extraction, in four steps:

1. High-pass the image. A star is a small bright thing sitting on a smoothly
   varying sky, so subtracting a blurred copy of the image leaves the stars
   and removes gradients, vignetting and large-scale nebulosity.
2. Threshold at a robust noise level. The noise is estimated with the median
   absolute deviation, which ignores the stars themselves, so the threshold
   adapts to a noisy JPEG without being dragged up by bright sources.
3. Label connected regions. Each region above the threshold is one source,
   which is why there is no peak-suppression pass: a star cannot be counted
   twice if it is a single region.
4. Measure each region: area, integrated flux, shape and colour.

Sources that are not point-like are rejected rather than played. Without that
gate the brightest "stars" in an image are often fragments of a nebula.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from config.config import StarDetectorConfig
from detection.labeling import (
    label_components,
    region_areas,
    region_bounds,
    region_sums,
)
from models.images import Images
from models.star import BigStar, SmallStar, Star, Stars

_LUMA = (0.2126, 0.7152, 0.0722)


def luminance(rgb: np.ndarray) -> np.ndarray:
    """Rec. 709 luminance of a float RGB array."""

    return _LUMA[0] * rgb[:, :, 0] + _LUMA[1] * rgb[:, :, 1] + _LUMA[2] * rgb[:, :, 2]


def robust_noise(values: np.ndarray) -> tuple[float, float]:
    """Return ``(median, sigma)`` estimated with the median absolute deviation.

    The MAD is used instead of the standard deviation because a starfield is
    mostly sky with a few very bright outliers, and the standard deviation
    would be dominated by the outliers we are trying to detect.
    """

    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    return median, max(1.4826 * mad, 1e-6)


class StarDetector:
    """Extracts point sources and splits them into two playing layers."""

    def __init__(
        self,
        images: Images,
        config: StarDetectorConfig,
        output_dir: str = ".",
        save_previews: bool = True,
    ) -> None:
        self.images = images
        self.config = config
        self.output_dir = output_dir
        self.save_previews = save_previews
        self.threshold: float = 0.0
        self.noise: float = 0.0

    # ------------------------------------------------------------------
    # detection
    # ------------------------------------------------------------------
    def detect(self) -> Stars:
        image = self.images.original_img
        width, height = image.size
        longest_side = max(width, height)
        frame_area = float(width * height)

        rgb = np.asarray(image, dtype=np.float32)
        signal = luminance(rgb)

        radius = max(1.0, self.config.background_radius_frac * longest_side)
        background = luminance(
            np.asarray(image.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32)
        )
        response = signal - background

        median, self.noise = robust_noise(response)
        self.threshold = max(
            self.config.minimum_contrast,
            median + self.config.detection_sigma * self.noise,
        )

        mask = (response >= self.threshold) & (signal >= self.config.minimum_brightness)
        labels, count = label_components(mask)
        if count == 0:
            print("[Stars] no sources above the detection threshold")
            return Stars()

        areas = region_areas(labels, count)
        fluxes = region_sums(labels, count, np.maximum(response, 0.0))
        bounds = region_bounds(labels, count)
        peaks_y, peaks_x, peak_values = self._region_peaks(labels, response)

        max_area = self.config.max_area_frac * frame_area
        stars: list[Star] = []
        rejected: list[Star] = []

        for index in range(1, count + 1):
            area = int(areas[index])
            if area < self.config.minimum_area_px:
                continue

            y0, y1, x0, x1 = bounds[index]
            box_height = float(y1 - y0 + 1)
            box_width = float(x1 - x0 + 1)
            box_area = box_width * box_height
            fill = area / box_area if box_area > 0 else 0.0
            elongation = max(box_width, box_height) / max(
                min(box_width, box_height), 1.0
            )

            star = self._measure(
                rgb,
                x=int(peaks_x[index]),
                y=int(peaks_y[index]),
                area=area,
                flux=float(fluxes[index]),
                peak=float(peak_values[index]),
                fill=fill,
                elongation=elongation,
            )

            too_large = max_area > 0 and area > max_area
            # Two shape gates, because either one alone lets something
            # through: a solid bar fills its box perfectly, and a ragged wisp
            # can still be roughly square.
            not_round = area >= self.config.roundness_area_px and (
                fill < self.config.roundness_min
                or elongation > self.config.max_elongation
            )
            if too_large or not_round:
                rejected.append(star)
                continue
            stars.append(star)

        result = self._split(stars, rejected)
        result.density_per_megapixel = len(result) / max(frame_area / 1e6, 1e-9)
        self._report(result, count)
        if self.save_previews:
            self._save_preview(result)
        return result

    # ------------------------------------------------------------------
    # measurement
    # ------------------------------------------------------------------
    def _region_peaks(
        self, labels: np.ndarray, response: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Brightest pixel of every labelled region."""

        count = int(labels.max())
        ys, xs = np.nonzero(labels)
        region = labels[ys, xs]
        values = response[ys, xs]

        # Sort by region, then by descending response, so the first row of
        # each region block is its brightest pixel.
        order = np.lexsort((-values, region))
        region, ys, xs, values = region[order], ys[order], xs[order], values[order]
        first = np.searchsorted(region, np.arange(1, count + 1), side="left")

        peak_y = np.zeros(count + 1, dtype=np.int32)
        peak_x = np.zeros(count + 1, dtype=np.int32)
        peak_value = np.zeros(count + 1, dtype=np.float32)
        valid = first < len(region)
        indices = np.nonzero(valid)[0]
        peak_y[indices + 1] = ys[first[indices]]
        peak_x[indices + 1] = xs[first[indices]]
        peak_value[indices + 1] = values[first[indices]]
        return peak_y, peak_x, peak_value

    def _measure(
        self,
        rgb: np.ndarray,
        *,
        x: int,
        y: int,
        area: int,
        flux: float,
        peak: float,
        fill: float,
        elongation: float,
    ) -> Star:
        """Aperture colour photometry around one source."""

        radius = self.config.aperture_radius_px
        height, width = rgb.shape[:2]
        y0, y1 = max(0, y - radius), min(height, y + radius + 1)
        x0, x1 = max(0, x - radius), min(width, x + radius + 1)
        patch = rgb[y0:y1, x0:x1].reshape(-1, 3)
        red, green, blue = (float(channel) for channel in patch.mean(axis=0))

        highest = max(red, green, blue)
        lowest = min(red, green, blue)
        saturation = (highest - lowest) / highest if highest > 0 else 0.0
        colour_sum = blue + red
        color_index = (blue - red) / colour_sum if colour_sum > 0 else 0.0

        return Star(
            x=x,
            y=y,
            area=area,
            flux=flux,
            peak=peak,
            fill=fill,
            elongation=elongation,
            rgb=(round(red), round(green), round(blue)),
            color_index=color_index,
            saturation=saturation,
        )

    def _split(self, stars: list[Star], rejected: list[Star]) -> Stars:
        """Divide sources into the small and big layers by integrated flux.

        The split is a percentile of this image's own flux distribution rather
        than an absolute size, because an absolute threshold produces wildly
        different layer balances from one image to the next: measured across
        the sample set, one fixed area cut gave anywhere from 1% to 31% big
        stars. A percentile gives the same musical balance every time.
        """

        result = Stars(rejected=rejected)
        if not stars:
            return result

        # Rank rather than a percentile value, so that ties do not push
        # every source into one layer: taking the brightest N guarantees the
        # requested balance whatever the flux distribution looks like.
        share = (100.0 - self.config.big_star_flux_percentile) / 100.0
        big_count = max(0, min(int(round(len(stars) * share)), len(stars)))
        order = sorted(range(len(stars)), key=lambda i: stars[i].flux, reverse=True)
        big_indices = set(order[:big_count])
        result.flux_split = (
            stars[order[big_count - 1]].flux if big_count else float("inf")
        )

        for position, star in enumerate(stars):
            if position in big_indices:
                result.big_stars.append(
                    BigStar(**{key: getattr(star, key) for key in _STAR_FIELDS})
                )
            else:
                result.small_stars.append(
                    SmallStar(**{key: getattr(star, key) for key in _STAR_FIELDS})
                )
        return result

    # ------------------------------------------------------------------
    # reporting
    # ------------------------------------------------------------------
    def _report(self, stars: Stars, regions: int) -> None:
        print(
            f"[Stars] {regions} regions above threshold "
            f"(sigma={self.config.detection_sigma}, noise={self.noise:.2f}, "
            f"threshold={self.threshold:.1f})"
        )
        print(
            f"[Stars] kept {len(stars)} sources: "
            f"{len(stars.small_stars)} small, {len(stars.big_stars)} big "
            f"(flux split at {stars.flux_split:.0f}); "
            f"rejected {len(stars.rejected)} as not point-like"
        )
        print(
            f"[Stars] density {stars.density_per_megapixel:.0f} sources per megapixel"
        )
        if stars.big_stars:
            colours = [star.color_index for star in stars.all]
            faint = sum(1 for star in stars.all if star.saturation < 0.15)
            print(
                f"[Stars] colour index {min(colours):+.3f}..{max(colours):+.3f}; "
                f"{100 * faint / max(len(stars), 1):.0f}% of sources are "
                f"effectively colourless"
            )

    def _save_preview(self, stars: Stars) -> None:
        """Draw what the detector decided, so it can be checked by eye."""

        preview = self.images.original_img.convert("RGB").copy()
        draw = ImageDraw.Draw(preview)
        palette = (
            (stars.rejected, (255, 80, 80), 2),
            (stars.small_stars, (120, 200, 255), 1),
            (stars.big_stars, (255, 220, 120), 2),
        )
        for group, colour, thickness in palette:
            for star in group:
                radius = max(3, int(np.sqrt(max(star.area, 1)) * 2.2))
                draw.ellipse(
                    [star.x - radius, star.y - radius, star.x + radius, star.y + radius],
                    outline=colour,
                    width=thickness,
                )
        path = f"{self.output_dir.rstrip('/')}/stars_detected.png"
        preview.save(path)
        print(f"[Stars] preview saved: {path} (blue small, gold big, red rejected)")


_STAR_FIELDS = (
    "x",
    "y",
    "area",
    "flux",
    "peak",
    "fill",
    "elongation",
    "rgb",
    "color_index",
    "saturation",
)
