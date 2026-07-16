from image_procesing import ImageProcessor
from src.detection import StarDetector, DetectionUtils
from PIL import Image
from models.images import Images

class ImagePipeLine:

    self.images = Images | None

    def __int__(self, image_path: str):

        self.img = Image.open(image_path).convert("RGB")
        self.width, self.height = self.img.size

        self.images = Images
        
    def _process_image(self) -> Images:
        """
        Processes the image: magic wand, detection, and color analysis.
        
        4. Detects starts on simplified image, and takes color from staruated image
        5. Extracts dominants colors for bass.
        """
        
        print("\n[Image Processing]")

        processor = ImageProcessor(self.image_path)
        
        # 1. Saturate original image (for more vibrant colors)
        print("  - Saturating original image...")
        saturated_path = str(self.output_dir / "saturated.png")
        saturated_img = processor.save_saturated_image(
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
            white_threshold_s=self.config.star_detector.white_threshold_s,
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