"""Kosmos entry point."""

import time

from pipeline.pipeline import ImageToMidi
from utils.parse_arg import get_and_validate_args


def main() -> None:
    args = get_and_validate_args()
    started = time.perf_counter()

    print(f"Image:  {args.image}")
    print(f"Config: {args.config}")
    print(f"Output: {args.output}")
    print(f"Mode:   {args.mode}")
    print()

    ImageToMidi(args.config, args.image, args.output).process(
        mode=args.mode, midi_name=args.midi_name
    )

    print(f"\nDone in {time.perf_counter() - started:.1f}s")


if __name__ == "__main__":
    main()
