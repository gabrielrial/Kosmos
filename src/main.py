from utils.parse_arg import get_and_validate_args
from pipeline.pipeline import ImageToMidi
import time

def main():


    start = time.perf_counter()

    # Proceso que quieres medir


    args = get_and_validate_args()

    print(f"Processing image: {args.image}")
    print(f"Configuration: {args.config}")
    print(f"Output: {args.output}")
    print()

    ImageToMidi(args.config, args.image, args.output).process()
    end = time.perf_counter()

    print(f"Tiempo: {end - start} segundos")

if __name__ == "__main__":
    main()

