from utils.parse_arg import get_and_validate_args
from pipeline.pipeline import ImageToMidi

def main():
    print("Main")
    args = get_and_validate_args()

    # Create and run pipeline
    print(f"Processing image: {args.image}")
    print(f"Configuration: {args.config}")
    print(f"Output: {args.output}")
    print()

    ImageToMidi(args.config, args.image, args.output).process()

        
if __name__ == "__main__":
    main()