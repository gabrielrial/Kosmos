import PIL
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
from models.images import Images
from config.config import ImageConfig
from collections import deque


class ImagePipeLine:

    def __init__(self, image_path: str, config: ImageConfig):

        self.image_path = image_path

        self.images = Images()

        self.config = config

    def process(self) -> Images:
        """ImageFilter
        Processes the image: magic wand, detection, and color analysis.
        ImageFilter
        4. Detects starts on simplified image, and takes color from staruated image
        5. Extracts dominants colors for bass.
        """

        self._loads_img()
        self._blurs_img()
        self._saturate_img()
        self.magic_wand()

        return self.images

    def _loads_img(self) -> None:
        """
        Loads the original image as Image PIL class, ang gets its attributes.
        """
        self.images.original_img = Image.open(self.image_path).convert("RGB")
        self.images.width, self.images.height = self.images.original_img.size

    def _blurs_img(self) -> None:
        self.images.blurred_img = self.images.original_img.filter(
            ImageFilter.BoxBlur(self.config.blur)
        )
        self.images.blurred_img.save("saturated_img.png")

    def _saturate_img(self) -> None:

        sturate = PIL.ImageEnhance.Color(self.images.original_img)
        self.images.saturated_img = sturate.enhance(self.config.saturation_boost)
        self.images.saturated_img.save("saturated_img.png")

    def magic_wand(
        self,
        output_path: str = "magic_wand.png",
        tolerance: int = 150,
    ) -> None:
        """
        Groups pixels of similar colors and replaces with average color.

        Simulates Photoshop's "magic wand": finds connected regions
        of similar colors and paints them with the average color of the region.

        Args:
            output_path: Path to save processed image
            tolerance: Maximum color distance to group (0-255)
        """
        img = self.images.original_img.copy()
        w, h = self.images.width, self.images.height
        pixels = img.load()
        visited = np.zeros((w, h), dtype=bool)

        def color_distance(c1, c2):
            return (c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2 + (c1[2] - c2[2]) ** 2

        # Iterate through each unvisited pixel
        for y in range(h):
            for x in range(w):
                if visited[x, y]:
                    continue

                orig_color = pixels[x, y]
                queue = deque([(x, y)])
                region = []

                # Flood fill to find connected region
                while queue:
                    cx, cy = queue.popleft()
                    if visited[cx, cy]:
                        continue
                    cur_color = pixels[cx, cy]

                    # Add to region if color is similar
                    if color_distance(orig_color, cur_color) <= tolerance * tolerance:
                        region.append((cx, cy))

                    visited[cx, cy] = True

                    # Add unvisited neighbors
                    for nx, ny in [
                        (cx + 1, cy),
                        (cx - 1, cy),
                        (cx, cy + 1),
                        (cx, cy - 1),
                    ]:
                        if 0 <= nx < w and 0 <= ny < h and not visited[nx, ny]:
                            queue.append((nx, ny))

                # Replace region with average color
                if region:
                    avg_r = int(np.mean([pixels[px, py][0] for px, py in region]))
                    avg_g = int(np.mean([pixels[px, py][1] for px, py in region]))
                    avg_b = int(np.mean([pixels[px, py][2] for px, py in region]))

                    for px, py in region:
                        pixels[px, py] = (avg_r, avg_g, avg_b)

        img.save(output_path)
        self.images.main_colors_img = img
        print(f"[OK] Magic wand saved at: {output_path}")


"""
        
        print("\n[Image Processing]")

        processor = ImageProcessor(self.image_path)
        
        # 1. Saturate original image (for more vibrant colors)
        print("  - Saturating original image...")
        saturated_path = str(self.output_dir / "saturated.png")
        saturated_imgblur_img = processor.save_saturated_image(
            saturated_path,
            saturation_boost=1.5  # 50% more saturation
        )
    
         #2. Magic Wand: group similar colors
        print("  - Magic Wand (grouping colors)...")
        magic_wand_path = str(self.output_dir / "magic_wand.png")
        processor.save_magic_wand_colors(
            magic_wand_path,
            tolerance=self.config.predominant_color.tolerance
        )
        
        # 3. Reduce to dominant colors
        print("  - Analyzing dominant colors...")
        dominant = processor.get_dominant_colors(magic_wand_path)
        
        simplified_path = str(self.output_dir / "resultado_simplificado.png")
        print("  - Reducing to dominant colors...")
        processor.reduce_to_dominant_colors(
            magic_wand_path,
            dominant,
            simplified_path
        )
        

  
        
        # 4. Detect stars in simplified image (but extract colors from saturated original)
        print("  - Detecting stars...")
        simplified_img = Image.open(simplified_path).convert("RGB")
        
        # Create detector with configuration parameters
        utils = DetectionUtils(
            white_threshold_v=self.config.star_detector.white_threshold_v,
            
		# Opens a image in RGB mode
		im = Image.open(r"geek.jpg")

		# Blurring the image
		im1 = im.filter(ImageFilter.BoxBlur(4))

		# Shows the image in image viewer
		im1.show()white_threshold_s=self.config.star_detector.white_threshold_s,
            ring_radius=self.config.star_detector.ring_radius,
            contrast_threshold=self.config.star_detector.contrast_threshold,
            brightness_threshold=self.config.star_detector.brightness_threshold,
        )
        
        detector = StarDetector(utils, save_previews=True, preview_dir=str(self.output_dir))
        # Detectar en imagen simplificada, pero tomar colores de imagen original saturada
        self.small_stars, self.big_stars = detector.detect(
            simplified_img,
            color_source_image=saturated_img
        )
        
        print(f"    ✓ {len(self.small_stars)} small stars")
        print(f"    ✓ {len(self.big_stars)} large stars")
        
        # 5. Extract dominant colors for the bass
        print("  - Preparing colors for bass...")
        self.dominant_colors = dominant
		"""
