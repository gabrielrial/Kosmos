"""Tests for detection and mapping.

Synthetic images with known contents, so a failure points at the algorithm
rather than at a judgement call about a photograph.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config.config import (  # noqa: E402
    NebulaDetectorConfig,
    StarDetectorConfig,
)
from detection.labeling import _label_fallback, label_components  # noqa: E402
from detection.nebula_detector import NebulaDetector  # noqa: E402
from detection.star_detector import StarDetector  # noqa: E402
from mapping.star_mapper import LayerSpec, StarMapper  # noqa: E402
from models.images import Images  # noqa: E402
from models.star import Star, Stars  # noqa: E402


def blank(width=400, height=400, level=8):
    return np.full((height, width, 3), level, dtype=np.float32)


def add_star(canvas, x, y, amplitude, sigma=1.6):
    height, width = canvas.shape[:2]
    ys, xs = np.ogrid[:height, :width]
    blob = amplitude * np.exp(-(((xs - x) ** 2 + (ys - y) ** 2) / (2 * sigma**2)))
    canvas += blob[:, :, None]


def to_images(canvas):
    image = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8), "RGB")
    return Images(
        original_img=image,
        width=image.size[0],
        height=image.size[1],
        source_size=image.size,
    )


class LabellingTest(unittest.TestCase):
    def test_fallback_matches_scipy_when_available(self):
        rng = np.random.default_rng(7)
        mask = rng.random((120, 90)) > 0.7
        fallback_labels, fallback_count = _label_fallback(mask)
        labels, count = label_components(mask)
        self.assertEqual(count, fallback_count)
        # Label numbering may differ; the partition must not.
        self.assertEqual(
            {frozenset(zip(*np.nonzero(labels == i))) for i in range(1, count + 1)},
            {
                frozenset(zip(*np.nonzero(fallback_labels == i)))
                for i in range(1, fallback_count + 1)
            },
        )

    def test_diagonal_pixels_are_one_region(self):
        mask = np.zeros((5, 5), dtype=bool)
        mask[1, 1] = mask[2, 2] = True
        _, count = label_components(mask)
        self.assertEqual(count, 1, "8-connectivity should join diagonal neighbours")


class StarDetectorTest(unittest.TestCase):
    def setUp(self):
        self.config = StarDetectorConfig(
            detection_sigma=5.0,
            minimum_contrast=4.0,
            minimum_brightness=10.0,
            minimum_area_px=2,
            big_star_flux_percentile=80.0,
        )

    def test_finds_planted_stars_at_the_right_places(self):
        canvas = blank()
        planted = [(80, 60), (200, 150), (320, 300), (120, 330)]
        for x, y in planted:
            add_star(canvas, x, y, 180)
        stars = StarDetector(to_images(canvas), self.config, save_previews=False).detect()

        self.assertEqual(len(stars), len(planted))
        found = sorted((star.x, star.y) for star in stars.all)
        for (want_x, want_y), (got_x, got_y) in zip(sorted(planted), found):
            self.assertLessEqual(abs(want_x - got_x), 1)
            self.assertLessEqual(abs(want_y - got_y), 1)

    def test_brightest_star_lands_in_the_big_layer(self):
        canvas = blank()
        for x in range(60, 340, 60):
            add_star(canvas, x, 200, 90)
        add_star(canvas, 200, 90, 240, sigma=2.4)
        stars = StarDetector(to_images(canvas), self.config, save_previews=False).detect()

        self.assertEqual(len(stars.big_stars), 1)
        self.assertEqual((stars.big_stars[0].x, stars.big_stars[0].y), (200, 90))
        self.assertGreater(stars.big_stars[0].flux, max(s.flux for s in stars.small_stars))

    def test_elongated_source_is_rejected_as_not_a_star(self):
        canvas = blank()
        canvas[200:206, 100:260] += 200.0        # a bright bar, not a star
        add_star(canvas, 320, 320, 180)
        stars = StarDetector(to_images(canvas), self.config, save_previews=False).detect()

        self.assertEqual(len(stars), 1, "only the round source should be kept")
        self.assertEqual(len(stars.rejected), 1)
        self.assertGreater(
            stars.rejected[0].elongation, self.config.max_elongation
        )
        self.assertLess(stars.all[0].elongation, self.config.max_elongation)

    def test_colour_index_separates_blue_from_red(self):
        def one_star(blue_gain: float, red_gain: float) -> float:
            canvas = blank()
            add_star(canvas, 120, 120, 170)
            canvas[:, :, 2] *= blue_gain
            canvas[:, :, 0] *= red_gain
            stars = StarDetector(
                to_images(canvas), self.config, save_previews=False
            ).detect()
            return stars.all[0].color_index

        blue_star = one_star(blue_gain=1.0, red_gain=0.4)
        red_star = one_star(blue_gain=0.4, red_gain=1.0)
        self.assertGreater(blue_star, 0.0, "a blue star should read positive")
        self.assertLess(red_star, 0.0, "a red star should read negative")
        self.assertGreater(blue_star, red_star)

    def test_layer_split_respects_the_configured_share(self):
        canvas = blank(600, 600)
        for index, x in enumerate(range(40, 580, 27)):
            add_star(canvas, x, 300, 80 + index * 6)
        config = StarDetectorConfig(
            detection_sigma=5.0, minimum_contrast=4.0, big_star_flux_percentile=90.0
        )
        stars = StarDetector(to_images(canvas), config, save_previews=False).detect()
        expected = round(len(stars) * 0.10)
        self.assertEqual(len(stars.big_stars), expected)
        self.assertGreater(
            min(star.flux for star in stars.big_stars),
            max(star.flux for star in stars.small_stars),
        )

    def test_empty_sky_detects_nothing_and_does_not_crash(self):
        stars = StarDetector(
            to_images(blank()), self.config, save_previews=False
        ).detect()
        self.assertEqual(len(stars), 0)
        self.assertEqual(stars.all, [])


class NebulaDetectorTest(unittest.TestCase):
    def test_finds_a_diffuse_patch_and_ignores_stars(self):
        canvas = blank(600, 600, level=10)
        ys, xs = np.ogrid[:600, :600]
        patch = 60 * np.exp(-(((xs - 300) ** 2 + (ys - 300) ** 2) / (2 * 55.0**2)))
        canvas += patch[:, :, None]
        for x in range(60, 560, 40):             # a field of stars on top
            add_star(canvas, x, 100, 200)

        config = NebulaDetectorConfig(
            min_area_frac=0.001, seed_sigma=3.0, grow_sigma=0.5
        )
        regions = NebulaDetector(
            to_images(canvas), config, save_previews=False
        ).detect()

        self.assertGreaterEqual(len(regions), 1)
        biggest = max(regions, key=lambda nebula: nebula.area)
        self.assertLess(abs(biggest.x - 300), 25)
        self.assertLess(abs(biggest.y - 300), 25)
        self.assertGreater(biggest.area_frac, 0.001)
        self.assertEqual(len(biggest.filter_curve), 32)
        self.assertTrue(all(0.0 <= value <= 1.0 for value in biggest.filter_curve))

    def test_hysteresis_keeps_the_faint_halo_with_its_core(self):
        """A bright core inside a wide faint halo must come out as one region.

        The point of two thresholds: the seed level decides where a region is
        allowed to start, and the grow level decides how far it reaches. Only
        the grow level changes below, so any difference in size is the halo
        being included or cut off.
        """

        rng = np.random.default_rng(3)
        canvas = blank(600, 600, level=25)
        ys, xs = np.ogrid[:600, :600]
        canvas += (
            18 * np.exp(-(((xs - 300) ** 2 + (ys - 300) ** 2) / (2 * 95.0**2)))
        )[:, :, None]                                    # wide faint halo
        canvas += (
            90 * np.exp(-(((xs - 300) ** 2 + (ys - 300) ** 2) / (2 * 20.0**2)))
        )[:, :, None]                                    # bright core
        canvas += rng.normal(0, 6.0, canvas.shape).astype(np.float32)
        canvas = np.clip(canvas, 0, 255)
        images = to_images(canvas)

        def core_area(grow_sigma: float) -> float:
            regions = NebulaDetector(
                images,
                NebulaDetectorConfig(
                    min_area_frac=0.0005,
                    seed_sigma=4.0,
                    grow_sigma=grow_sigma,
                    star_suppression_frac=0.0,
                    max_star_flux_share=1.0,
                    max_cover_frac=0.60,
                ),
                save_previews=False,
            ).detect()
            near = [
                nebula
                for nebula in regions
                if abs(nebula.x - 300) < 60 and abs(nebula.y - 300) < 60
            ]
            self.assertTrue(near, "the core should be found at any grow level")
            return max(near, key=lambda nebula: nebula.area).area_frac

        tight = core_area(4.0)      # no growth: stops at the seed level
        loose = core_area(0.3)      # grown far into the halo
        self.assertGreater(
            loose,
            tight * 1.5,
            "growing to a lower threshold should reach further into the halo",
        )

    def test_growth_never_exceeds_the_cover_limit(self):
        """A strong gradient must not let one region swallow the frame."""

        canvas = blank(400, 400, level=10)
        ramp = np.linspace(0, 120, 400, dtype=np.float32)
        canvas += ramp[None, :, None]
        regions = NebulaDetector(
            to_images(canvas),
            NebulaDetectorConfig(
                min_area_frac=0.001, seed_sigma=3.0, grow_sigma=0.1, max_cover_frac=0.30
            ),
            save_previews=False,
        ).detect()
        self.assertLessEqual(sum(n.area_frac for n in regions), 0.31)

    def test_percentile_mode_also_produces_regions(self):
        canvas = blank(600, 600, level=10)
        ys, xs = np.ogrid[:600, :600]
        canvas += (60 * np.exp(-(((xs - 300) ** 2 + (ys - 300) ** 2) / (2 * 60.0**2))))[
            :, :, None
        ]
        regions = NebulaDetector(
            to_images(canvas),
            NebulaDetectorConfig(
                min_area_frac=0.001,
                seed_sigma=3.0,
                grow_mode="percentile",
                grow_percentile=70.0,
            ),
            save_previews=False,
        ).detect()
        self.assertTrue(regions)
        self.assertLess(abs(max(regions, key=lambda n: n.area).x - 300), 30)

    def test_a_bright_star_is_not_reported_as_a_nebula(self):
        """The whole point: a star with a wide halo must not become a region.

        Blurring spreads a bright star instead of removing it, so its halo
        lands in the nebula band. Measured on a real image, the halo of the
        brightest stars stayed above the seed threshold out to 12 pixels.
        """

        rng = np.random.default_rng(11)
        canvas = blank(600, 600, level=10)
        # A very bright, very compact source: a star, not a cloud.
        add_star(canvas, 300, 300, 240, sigma=6.0)
        canvas += rng.normal(0, 1.5, canvas.shape).astype(np.float32)
        canvas = np.clip(canvas, 0, 255)

        config = NebulaDetectorConfig(
            min_area_frac=0.0005,
            seed_sigma=3.0,
            grow_sigma=0.5,
            star_suppression_frac=0.010,
            max_star_flux_share=0.25,
        )
        regions = NebulaDetector(
            to_images(canvas), config, save_previews=False
        ).detect()
        self.assertEqual(
            regions, [], "a lone bright star should produce no nebula regions"
        )

    def test_a_real_cloud_survives_the_star_filter(self):
        """The same settings must still keep genuinely diffuse emission."""

        rng = np.random.default_rng(12)
        canvas = blank(600, 600, level=10)
        ys, xs = np.ogrid[:600, :600]
        canvas += (
            45 * np.exp(-(((xs - 300) ** 2 + (ys - 300) ** 2) / (2 * 110.0**2)))
        )[:, :, None]
        for x in range(80, 560, 70):                     # stars on top of it
            add_star(canvas, x, 150, 150)
        canvas += rng.normal(0, 1.5, canvas.shape).astype(np.float32)
        canvas = np.clip(canvas, 0, 255)

        config = NebulaDetectorConfig(
            min_area_frac=0.0005,
            seed_sigma=3.0,
            grow_sigma=0.5,
            star_suppression_frac=0.010,
            max_star_flux_share=0.25,
        )
        regions = NebulaDetector(
            to_images(canvas), config, save_previews=False
        ).detect()
        self.assertTrue(regions, "a diffuse cloud must survive the star filter")
        biggest = max(regions, key=lambda nebula: nebula.area)
        self.assertLess(abs(biggest.x - 300), 60)
        self.assertLess(abs(biggest.y - 300), 60)

    def test_dominant_colour_weights_sum_to_one(self):
        canvas = blank(400, 400, level=10)
        ys, xs = np.ogrid[:400, :400]
        falloff = np.exp(-(((xs - 200) ** 2 + (ys - 200) ** 2) / (2 * 70.0**2)))
        canvas += falloff[:, :, None] * np.array([70, 20, 30], dtype=np.float32)
        config = NebulaDetectorConfig(
            min_area_frac=0.001,
            seed_sigma=3.0,
            grow_sigma=0.5,
            star_suppression_frac=0.0,
            max_star_flux_share=1.0,
        )
        regions = NebulaDetector(
            to_images(canvas), config, save_previews=False
        ).detect()
        self.assertTrue(regions)
        for nebula in regions:
            if nebula.dominant_colors:
                total = sum(colour.weight for colour in nebula.dominant_colors)
                self.assertAlmostEqual(total, 1.0, places=5)
                for colour in nebula.dominant_colors:
                    self.assertTrue(0.0 <= colour.hue <= 1.0)
                    self.assertTrue(0.0 <= colour.brightness <= 1.0)


class StarMapperTest(unittest.TestCase):
    def make_stars(self, colour_indices):
        stars = Stars()
        for index, colour in enumerate(colour_indices):
            stars.small_stars.append(
                Star(
                    x=index * 10,
                    y=0,
                    area=3,
                    flux=100.0 + index,
                    peak=50.0,
                    fill=0.8,
                    elongation=1.0,
                    rgb=(100, 100, 100),
                    color_index=colour,
                    saturation=0.3,
                )
            )
        return stars

    def test_notes_stay_inside_the_layer_and_the_scale(self):
        stars = self.make_stars(np.linspace(-0.5, 0.5, 40).tolist())
        mapper = StarMapper(
            small=LayerSpec(67, 91, 0.5, 3),
            big=LayerSpec(48, 67, 2.0, 5),
            pitch_classes={0, 4, 7},
        )
        small, _ = mapper.map(stars, image_width=400)

        self.assertEqual(len(small), 40)
        for event in small:
            self.assertTrue(67 <= event.note <= 91)
            self.assertIn(event.note % 12, {0, 4, 7})
            self.assertTrue(0 <= event.pan <= 127)
            self.assertTrue(1 <= event.velocity <= 127)
            self.assertEqual(event.channel, 3)

    def test_bluer_stars_play_higher(self):
        stars = self.make_stars([-0.4, 0.0, 0.4])
        mapper = StarMapper(
            small=LayerSpec(60, 84, 0.5, 3), big=LayerSpec(48, 60, 2.0, 5)
        )
        small, _ = mapper.map(stars, image_width=100)
        notes = [event.note for event in small]
        self.assertEqual(notes, sorted(notes))
        self.assertLess(notes[0], notes[-1])

    def test_pan_spans_the_full_stereo_field(self):
        stars = self.make_stars([0.0, 0.0, 0.0])
        stars.small_stars[0].x = 0
        stars.small_stars[1].x = 199
        stars.small_stars[2].x = 399
        mapper = StarMapper(
            small=LayerSpec(60, 84, 0.5, 3), big=LayerSpec(48, 60, 2.0, 5)
        )
        small, _ = mapper.map(stars, image_width=400)
        pans = [event.pan for event in small]
        self.assertEqual(pans[0], 0)
        self.assertEqual(pans[-1], 127)
        self.assertGreater(pans[1], 50)

    def test_no_stars_is_not_an_error(self):
        mapper = StarMapper(
            small=LayerSpec(60, 84, 0.5, 3), big=LayerSpec(48, 60, 2.0, 5)
        )
        self.assertEqual(mapper.map(Stars(), image_width=100), ([], []))


if __name__ == "__main__":
    unittest.main(verbosity=2)
