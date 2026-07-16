import argparse
from pathlib import Path
from error.errors import ERROR_100


def get_and_validate_args():
    parser = argparse.ArgumentParser(
        description="Kosmos - Converts images to MIDI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="ERROR_100",
    )

    parser.add_argument(
        "config",
        help="JSON configuration file",
    )

    parser.add_argument(
        "image",
        help="Image file to process",
    )

    parser.add_argument(
        "-o",
        "--output",
        default=".",
        help="Output directory (default: current)",
    )

    args = parser.parse_args()

    config_path = Path(args.config)
    image_path = Path(args.image)
    output_path = Path(args.output) 

    if not config_path.is_file():
        parser.error(f"Configuration file not found: {config_path}")

    if not image_path.is_file():
        parser.error(f"Image file not found: {image_path}")

    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)

    return args
