"""
Main pipeline: Converts images to MIDI music.

Orchestrates the entire workflow:
1. Load configuration
2. Process image
3. Detect stars
4. Analyze colors
5. Generate MIDI
"""

from typing import Optional

from config.config import ConfigLoader
from quantizer.quantizer import Quantizer

from image.img_pipeline import ImagePipeLine

from models.images import Images
from detection.star_detector import StarDetector

from models.star import Stars

from midi.midi_creator import MidiSheet


class ImageToMidi:

    def __init__(
        self, config_path: str, image_path: str, output_dir: Optional[str] = None
    ):

        # Load configuration and validate
        self.config = ConfigLoader.load(config_path)

        # Paths
        self.image_path = image_path
        self.output_path = output_dir


        self.images: Images | None

        self.stars: Stars = Stars()

        self.midi_track = MidiSheet()

        print(f"[Pipeline] Initialized")
        print(f"  Config: {config_path}")
        print(f"  Imagen: {image_path}")
        print(f"  Output: {output_dir}")
        print()

    def process(self):

        print(self.config.small_stars.contrast)
        print(self.config.star_detector.brightness_threshold)

        self.images = ImagePipeLine(self.image_path, self.config.images).process()

        StarDetector(self.images, self.stars, self.config.star_detector).detect()

        Quantizer(self.stars, self.images.width)
        self.midi_track.add_instrument(self.stars.small_stars, 0)
        self.midi_track.save("kosmos2.mid")
