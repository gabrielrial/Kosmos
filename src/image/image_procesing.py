"""
Image processing for star detection.

Provides utilities for:
- Grouping similar colors (magic wand)
- Reducing to dominant colors
- Analyzing color distribution
- Visualizing results
"""

from collections import deque, Counter
from typing import List, Tuple
from PIL import Image, ImageDraw
import numpy as np
from models.images import Images

from setup.image import ImageUtils


class ImageProcessor:
    """

    Processes image and returns and image class, which will contain all the different images that will be use
    in the detector procces.

    """
    
    def __init__(self, image_path):
        """
        Initializes the processor with an image.
        
        Args:
            image_path: Path to the JPEG image file
        """

        self.img = Image.open(image_path).convert("RGB")
        self.width, self.height = self.img.size

        self.images: Images | None

    
    # def image_processor_pipeline(self):
    #     ImageUtils.saturate_image(self.pipeline.image_pathm, self.pipeline.)
    #     self._magic_wand(self.pipeline.image_path)
    #     self._reduce_to_dominant_colors(self.pipeline.image_path)
