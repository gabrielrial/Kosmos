#!/usr/bin/env python3
"""Calibration tool: measure detection across a set of images.

Runs the real detectors — the same code the pipeline uses — but stops before
any MIDI, and prints one row per image. Use it to choose the values in
conf.json from data, and to check that a change to a detector improved things
rather than guessing by ear.

    python tools/survey.py conf.json img/*.jpg
    python tools/survey.py conf.json img/*.jpg --set star_detector.detection_sigma=6

The --set flag overrides config values for this run only, so a threshold can
be swept without editing conf.json.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config.config import ConfigLoader  # noqa: E402
from detection.nebula_detector import NebulaDetector  # noqa: E402
from detection.star_detector import StarDetector  # noqa: E402
from image.img_pipeline import ImagePipeLine  # noqa: E402

HEADER = (
    f"{'image':26} {'working px':>11} {'stars':>6} {'small':>6} {'big':>5} {'rej':>4} "
    f"{'area p50':>8} {'p99':>6} {'flux p50':>9} {'p99':>9} {'no col':>7} "
    f"{'colour index':>17} {'neb':>4} {'neb %':>6}"
)


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(values, q)) if values else 0.0


def survey(path: Path, config, quiet: bool = True) -> str:
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink if quiet else sys.stdout):
        images = ImagePipeLine(str(path), config.images).process()
        stars = StarDetector(
            images, config.star_detector, save_previews=False
        ).detect()
        nebulae = NebulaDetector(
            images, config.nebula_detector, save_previews=False
        ).detect()

    every = stars.all
    areas = [float(star.area) for star in every]
    fluxes = [star.flux for star in every]
    colours = [star.color_index for star in every]
    colourless = (
        100 * sum(1 for star in every if star.saturation < 0.15) / len(every)
        if every
        else 0.0
    )
    nebula_cover = 100 * sum(nebula.area_frac for nebula in nebulae)

    return (
        f"{path.name[:26]:26} {images.width}x{images.height:<6} {len(every):>6} "
        f"{len(stars.small_stars):>6} {len(stars.big_stars):>5} "
        f"{len(stars.rejected):>4} "
        f"{percentile(areas, 50):>8.0f} {percentile(areas, 99):>6.0f} "
        f"{percentile(fluxes, 50):>9.0f} {percentile(fluxes, 99):>9.0f} "
        f"{colourless:>6.0f}% "
        f"{percentile(colours, 2):>+8.3f}..{percentile(colours, 98):<+8.3f} "
        f"{len(nebulae):>4} {nebula_cover:>5.1f}%"
    )


def apply_overrides(config, overrides: list[str]) -> None:
    for override in overrides:
        path, _, raw = override.partition("=")
        section_name, _, field = path.partition(".")
        section = getattr(config, section_name, None)
        if section is None or not hasattr(section, field):
            raise SystemExit(f"unknown config path: {path}")
        current = getattr(section, field)
        value = type(current)(raw) if not isinstance(current, bool) else raw == "true"
        setattr(section, field, value)
        print(f"[Override] {path} = {value}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", help="JSON configuration file")
    parser.add_argument("images", nargs="+", help="images to measure")
    parser.add_argument(
        "--set",
        dest="overrides",
        action="append",
        default=[],
        metavar="section.field=value",
        help="override a config value for this run only",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="show each detector's own output"
    )
    args = parser.parse_args()

    config = ConfigLoader.load(args.config)
    apply_overrides(config, args.overrides)
    config.validate()

    print()
    print(HEADER)
    print("-" * len(HEADER))
    for name in args.images:
        path = Path(name)
        if not path.is_file():
            continue
        try:
            print(survey(path, config, quiet=not args.verbose))
        except Exception as error:  # keep going through a batch
            print(f"{path.name[:26]:26} FAILED: {type(error).__name__}: {error}")

    print()
    print(
        "area/flux are per star: p50 is the median, p99 the brightest 1%.\n"
        "'no col' is the share of stars with saturation under 0.15 — their hue\n"
        "is noise, which is why pitch comes from the colour index instead.\n"
        "'rej' is sources rejected as not point-like; a high count means the\n"
        "bright things in that image are extended, not stars."
    )


if __name__ == "__main__":
    main()
