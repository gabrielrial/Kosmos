"""Diffuse-region extraction by scale separation.

Stars and nebulosity are not separated by brightness, they are separated by
spatial frequency: a star is small and sharp, a nebula is large and soft, and
the sky gradient is larger and softer still. Thresholding brightness cannot
tell them apart, which is why a single threshold either finds nothing or
swallows the whole frame.

So the image is split into three bands:

    high     L - blur(small)              point sources -> the star detector
    mid      blur(small) - blur(large)    diffuse structure -> nebulae
    low      blur(large)                  sky, vignetting, gradient -> ignored

Both radii are fractions of the image size, which makes the result
independent of the resolution the file happens to have: measured across three
resolutions of the same image, the detected area stayed within 2%.

Three details matter more than they look:

Blurring does not remove a star, it spreads it. A bright star has a halo and
diffraction spikes reaching tens of pixels, which land in the same frequency
band as a small nebula and then act as perfectly good seeds. Measured on a
real image, the halo of the brightest stars sat above the seed threshold out
to a 12-pixel radius. So stars are suppressed with a median filter first: a
median ignores outliers, which is exactly what a star is against its
surroundings, while an extended edge survives it.


The large radius has to be clearly bigger than the biggest structure you want
to keep. If a nebula fills the frame and the radius is small, the nebula ends
up inside its own background estimate, subtracts itself, and only its
filaments survive. That is why this defaults to a quarter of the image rather
than a few percent.

And the threshold is a pair, not a number. A nebula has no edge, it fades out,
so one threshold cuts through the halo and leaves disconnected bright cores.
Hysteresis grows each seed outwards to a much lower threshold and keeps only
what stays connected, so the faint halo comes along and stray faint noise
does not.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from config.config import NebulaDetectorConfig
from detection.labeling import label_components, region_areas, region_bounds
from detection.star_detector import luminance, robust_noise
from models.color import Color
from models.images import Images
from models.nebula import Nebula

_CURVE_POINTS = 32
_COLOR_SAMPLE_LIMIT = 200_000


class NebulaDetector:
    """Finds extended regions in the mid-frequency band of an image."""

    def __init__(
        self,
        images: Images,
        config: NebulaDetectorConfig,
        output_dir: str = ".",
        save_previews: bool = True,
        star_mask: np.ndarray | None = None,
    ) -> None:
        self.images = images
        self.config = config
        self.star_mask = star_mask
        self.output_dir = output_dir
        self.save_previews = save_previews
        self.suppression_size = 0

    def detect(self) -> list[Nebula]:
        image = self.images.original_img
        width, height = image.size
        longest_side = max(width, height)
        frame_area = float(width * height)

        rgb = np.asarray(image, dtype=np.float32)
        signal = luminance(rgb)
        source = self._suppress_stars(signal, longest_side)

        small_radius = max(1.0, self.config.small_radius_frac * longest_side)
        large_radius = max(
            small_radius * 2.0, self.config.large_radius_frac * longest_side
        )
        small = np.asarray(
            source.filter(ImageFilter.GaussianBlur(small_radius)), dtype=np.float32
        )
        large = np.asarray(
            source.filter(ImageFilter.GaussianBlur(large_radius)), dtype=np.float32
        )
        band = small - large

        median, noise = robust_noise(band)
        chroma = None
        if self.config.saturation_threshold > 0:
            chroma = (rgb.max(axis=2) - rgb.min(axis=2)) / 255.0

        mask, labels, count, seed_level, grow_level = self._hysteresis(
            band, median, noise, chroma
        )
        print(
            f"[Nebulae] star suppression {self.suppression_size}px, "
            f"band-pass radii {small_radius:.1f}/{large_radius:.1f} px, "
            f"noise={noise:.2f}, seed>={seed_level:.2f}, "
            f"grow>={grow_level:.2f} ({self.config.grow_mode}), "
            f"mask covers {100 * mask.mean():.1f}% of the frame in {count} regions"
        )
        if count == 0:
            if self.save_previews:
                self._save_previews(mask, [])
            return []

        regions, star_like = self._collect(
            labels, count, band, rgb, frame_area, signal
        )
        if star_like:
            print(
                f"[Nebulae] discarded {star_like} regions whose light comes"
                f" mostly from point sources"
            )
        regions.sort(key=lambda nebula: nebula.area, reverse=True)
        print(
            f"[Nebulae] kept {len(regions)} regions covering "
            f"{100 * sum(n.area_frac for n in regions):.1f}% of the frame"
        )
        for index, nebula in enumerate(regions, start=1):
            print(
                f"  {index}. at ({nebula.x},{nebula.y}) "
                f"{nebula.area_frac * 100:.2f}% of frame, "
                f"hue={nebula.hue * 360:.0f}deg sat={nebula.saturation:.2f} "
                f"bright={nebula.brightness:.2f} elong={nebula.elongation:.2f} "
                f"colours={len(nebula.dominant_colors)}"
            )
        if self.save_previews:
            self._save_previews(mask, regions)
        return regions

    # ------------------------------------------------------------------
    def _suppress_stars(self, signal: np.ndarray, longest_side: int) -> Image.Image:
        """Replace point sources with their surroundings, before the band.

        A median filter is the right tool here: it reports the middle value of
        its window, so a star that occupies a minority of the window vanishes
        entirely, while the edge of an extended region — where most of the
        window is still region — is left where it is. A Gaussian would average
        the star into its neighbours instead, which is what spread the halo in
        the first place.
        """

        grey = Image.fromarray(np.clip(signal, 0, 255).astype(np.uint8), mode="L")
        if self.config.star_suppression_frac <= 0:
            return grey

        size = int(round(self.config.star_suppression_frac * longest_side))
        size = max(3, size | 1)          # MedianFilter needs an odd size >= 3
        self.suppression_size = size
        return grey.filter(ImageFilter.MedianFilter(size=size))

    def _hysteresis(
        self,
        band: np.ndarray,
        median: float,
        noise: float,
        chroma: np.ndarray | None,
    ) -> tuple[np.ndarray, np.ndarray, int, float, float]:
        """Grow every seed region out to the low threshold.

        Implemented by labelling the *low* mask once and keeping whichever
        labels contain at least one seed pixel. That is equivalent to flood
        filling from every seed, and it is a couple of array operations
        instead of a per-pixel walk.
        """

        seed_level = median + self.config.seed_sigma * noise
        grow_level = self._grow_level(band, median, noise)

        seeds = band >= seed_level
        if chroma is not None:
            seeds &= chroma >= self.config.saturation_threshold
        if not seeds.any():
            empty = np.zeros_like(seeds)
            return empty, np.zeros(band.shape, dtype=np.int32), 0, seed_level, grow_level

        grown = band >= grow_level
        labels, count = label_components(grown)
        if count == 0:
            return grown, labels, 0, seed_level, grow_level

        # A region survives only if a seed pixel falls inside it.
        seeded = np.zeros(count + 1, dtype=bool)
        seeded[np.unique(labels[seeds])] = True
        seeded[0] = False

        keep = seeded[labels]
        renumber = np.zeros(count + 1, dtype=np.int32)
        surviving = np.nonzero(seeded)[0]
        renumber[surviving] = np.arange(1, len(surviving) + 1, dtype=np.int32)
        return keep, renumber[labels], len(surviving), seed_level, grow_level

    def _grow_level(self, band: np.ndarray, median: float, noise: float) -> float:
        """The low threshold, and the guard that stops it eating the frame."""

        if self.config.grow_mode == "percentile":
            level = float(np.percentile(band, self.config.grow_percentile))
        else:
            level = median + self.config.grow_sigma * noise

        # Never let the halo threshold rise above the seed threshold.
        level = min(level, median + self.config.seed_sigma * noise)

        # If this would mask more than max_cover_frac of the image, raise it
        # until it fits. A strong sky gradient can otherwise clear a low
        # threshold everywhere and merge the whole picture into one region.
        cover = float((band >= level).mean())
        if cover > self.config.max_cover_frac:
            level = float(
                np.percentile(band, 100.0 * (1.0 - self.config.max_cover_frac))
            )
            print(
                f"[Nebulae] grow threshold raised to {level:.2f}: "
                f"the requested level covered {100 * cover:.0f}% of the frame, "
                f"above the {100 * self.config.max_cover_frac:.0f}% limit"
            )
        return level

    def _collect(
        self,
        labels: np.ndarray,
        count: int,
        band: np.ndarray,
        rgb: np.ndarray,
        frame_area: float,
        signal: np.ndarray,
    ) -> tuple[list[Nebula], int]:
        areas = region_areas(labels, count)
        bounds = region_bounds(labels, count)
        minimum = self.config.min_area_frac * frame_area
        maximum = self.config.max_area_frac * frame_area

        hsv = np.asarray(
            Image.fromarray(rgb.astype(np.uint8), "RGB").convert("HSV"),
            dtype=np.float32,
        ) / 255.0

        star_signal = self._star_signal(signal)
        regions: list[Nebula] = []
        star_like = 0
        for index in range(1, count + 1):
            area = int(areas[index])
            if area < minimum:
                continue
            if maximum > 0 and area > maximum:
                continue

            region_mask = labels == index
            ys, xs = np.nonzero(region_mask)

            # How much of this region's light is point-source light? A nebula
            # is diffuse, so most of its signal is spread out; a star's halo
            # keeps most of its signal in the few pixels of the star itself.
            if star_signal is not None and self.config.max_star_flux_share < 1.0:
                total = float(np.maximum(signal[ys, xs], 0.0).sum())
                from_stars = float(star_signal[ys, xs].sum())
                if total > 0 and from_stars / total >= self.config.max_star_flux_share:
                    star_like += 1
                    continue
            y0, y1, x0, x1 = (int(value) for value in bounds[index])

            weights = np.maximum(band[ys, xs], 1e-3)
            centre_x = float(np.average(xs, weights=weights))
            centre_y = float(np.average(ys, weights=weights))
            box_width = x1 - x0 + 1
            box_height = y1 - y0 + 1

            region_hsv = hsv[ys, xs]
            regions.append(
                Nebula(
                    x=int(round(centre_x)),
                    y=int(round(centre_y)),
                    width=box_width,
                    height=box_height,
                    area=area,
                    area_frac=area / frame_area,
                    density=area / float(box_width * box_height),
                    elongation=box_width / float(box_height),
                    brightness=float(region_hsv[:, 2].mean()),
                    hue=float(region_hsv[:, 0].mean()),
                    saturation=float(region_hsv[:, 1].mean()),
                    contrast=float(band[ys, xs].mean()),
                    dominant_colors=self._dominant_colors(rgb[ys, xs]),
                    filter_curve=self._filter_curve(region_mask[y0 : y1 + 1, x0 : x1 + 1]),
                )
            )
        return regions, star_like

    def _star_signal(self, signal: np.ndarray) -> np.ndarray | None:
        """Per-pixel light attributable to point sources.

        Built from the same high-pass the star detector uses, so the two
        stages agree on what a star is. Passed in by the caller when the star
        detector already ran, to avoid computing it twice.
        """

        if self.star_mask is not None:
            return np.where(self.star_mask, np.maximum(signal, 0.0), 0.0)

        longest_side = max(signal.shape)
        grey = Image.fromarray(np.clip(signal, 0, 255).astype(np.uint8), mode="L")
        background = np.asarray(
            grey.filter(ImageFilter.GaussianBlur(max(1.0, 0.0035 * longest_side))),
            dtype=np.float32,
        )
        high_pass = signal - background
        median, noise = robust_noise(high_pass)
        mask = high_pass >= median + 8.0 * noise
        return np.where(mask, np.maximum(signal, 0.0), 0.0)

    def _dominant_colors(self, pixels: np.ndarray) -> list[Color]:
        """Reduce a region to a few weighted representative colours."""

        limit = self.config.dominant_colors
        if len(pixels) == 0 or limit <= 0:
            return []

        if len(pixels) > _COLOR_SAMPLE_LIMIT:
            # Deterministic subsample: quantising millions of pixels is slow
            # and the palette barely moves.
            rng = np.random.default_rng(len(pixels))
            pixels = pixels[rng.choice(len(pixels), _COLOR_SAMPLE_LIMIT, replace=False)]

        strip = Image.fromarray(
            pixels.astype(np.uint8).reshape(1, len(pixels), 3), mode="RGB"
        )
        quantised = strip.quantize(colors=limit, method=Image.Quantize.MEDIANCUT)
        palette = quantised.getpalette() or []
        counts = quantised.getcolors() or []
        total = sum(count for count, _ in counts) or 1

        colors: list[Color] = []
        for count, entry in sorted(counts, reverse=True):
            red, green, blue = palette[entry * 3 : entry * 3 + 3]
            hsv = np.asarray(
                Image.new("RGB", (1, 1), (red, green, blue)).convert("HSV")
            )[0, 0]
            colors.append(
                Color(
                    hue=float(hsv[0]) / 255.0,
                    saturation=float(hsv[1]) / 255.0,
                    brightness=float(hsv[2]) / 255.0,
                    weight=count / total,
                )
            )
        return colors

    @staticmethod
    def _filter_curve(region: np.ndarray) -> list[float]:
        """Vertical thickness of the region along x, normalised to 0-1.

        A shape descriptor the mapping layer can use as a modulation curve
        across the phrase.
        """

        if region.size == 0:
            return []

        rows = np.arange(region.shape[0])[:, None]
        top = np.where(region, rows, region.shape[0]).min(axis=0)
        bottom = np.where(region, rows, -1).max(axis=0)
        heights = np.where(region.any(axis=0), bottom - top + 1, 0).astype(np.float32)

        highest = heights.max()
        if highest <= 0:
            return [0.0] * _CURVE_POINTS
        heights /= highest

        if len(heights) != _CURVE_POINTS:
            heights = np.interp(
                np.linspace(0.0, 1.0, _CURVE_POINTS),
                np.linspace(0.0, 1.0, len(heights)),
                heights,
            )
        if len(heights) >= 3:
            smoothed = heights.copy()
            smoothed[1:-1] = (heights[:-2] + heights[1:-1] + heights[2:]) / 3.0
            heights = smoothed
        return [float(value) for value in heights]

    # ------------------------------------------------------------------
    def _save_previews(self, mask: np.ndarray, regions: list[Nebula]) -> None:
        base = self.output_dir.rstrip("/")
        Image.fromarray((mask.astype(np.uint8) * 255), mode="L").save(
            f"{base}/nebulas.png"
        )

        preview = self.images.original_img.convert("RGB").copy()
        draw = ImageDraw.Draw(preview)
        for index, nebula in enumerate(regions, start=1):
            left, top = nebula.left, nebula.top
            draw.rectangle(
                (left, top, left + nebula.width, top + nebula.height),
                outline=(255, 60, 60),
                width=2,
            )
            draw.text(
                (left, max(0, top - 12)),
                f"{index}: {nebula.area_frac * 100:.2f}%",
                fill=(255, 60, 60),
            )
        preview.save(f"{base}/nebula_debug.png")
        print(f"[Nebulae] previews saved: {base}/nebulas.png, {base}/nebula_debug.png")
