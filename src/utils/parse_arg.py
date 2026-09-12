"""Command line for Kosmos."""

from __future__ import annotations

import argparse
from pathlib import Path

EPILOG = """examples:
  python src/main.py conf.json img/space.jpg
      analyse, play live, and write output/space.mid

  python src/main.py conf.json img/space.jpg --mode file -o renders
      write renders/space.mid without opening any MIDI port

  python src/main.py conf.json img/space.jpg --mode live
      play live only

Live playback sends MIDI clock on the kosmos_clock port. In Ableton Live:
Preferences > Link/Tempo/MIDI, set Sync On for that port, then put the
transport in EXT. For sample-accurate timing instead, use --mode file and drag
the .mid into a clip.
"""


def get_and_validate_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="kosmos",
        description="Kosmos - turns astronomical images into MIDI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    parser.add_argument("config", help="JSON configuration file")
    parser.add_argument("image", help="image file to process")
    parser.add_argument(
        "-o",
        "--output",
        default="output",
        help="directory for the .mid and the preview images (default: output)",
    )
    parser.add_argument(
        "--mode",
        choices=("both", "live", "file"),
        default="both",
        help=(
            "both: play live and write the file (default). "
            "live: real time only, for exploring. "
            "file: write the .mid only, no MIDI ports opened"
        ),
    )
    parser.add_argument(
        "--midi-name",
        default=None,
        help="name for the .mid file (default: the image's name)",
    )

    args = parser.parse_args()

    if not Path(args.config).is_file():
        parser.error(f"configuration file not found: {args.config}")
    if not Path(args.image).is_file():
        parser.error(f"image file not found: {args.image}")
    Path(args.output).mkdir(parents=True, exist_ok=True)

    return args
