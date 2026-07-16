"""
Star detector in processed images.

Detects bright regions and classifies them as small or large stars.
"""

from typing import Tuple, List
from PIL import Image, ImageDraw
from src.detection.utils import DetectionUtils
from src.models.star import SmallStar, BigStar
from src.image.image_procesing import ImageProcessor


class StarDetector:
    """Detects and classifies stars in images."""
    
    def __init__(
        self,
        utils: DetectionUtils = None,
        save_previews: bool = False,
        preview_dir: str = ".",

    ):
        """
        Initializes the star detector.
        
        Args:
            utils: DetectionUtils instance (default is created)
            save_previews: Whether to save preview images of detected stars
            preview_dir: Directory to save previews
        """
        self.images: ImageProcessor # estaba aca

        self.utils = utils or DetectionUtils()
        self.save_previews = save_previews
        self.preview_dir = preview_dir
        self.small_stars: List[SmallStar] = []
        self.big_stars: List[BigStar] = []
    
    def _save_star_preview(
        self,
        image,
        bx: int,
        by: int,
        is_big_star: bool = False,
        preview_size: int = 25,
    ) -> None:
        """
        Saves a preview of a detected star.
        
        Args:
            image: PIL Image object
            bx, by: Coordinates of the brightest pixel
            is_big_star: Whether it is a big star
            preview_size: Crop radius around the center
        """
        if not self.save_previews:
            return
        
        width, height = image.size
        left = max(0, bx - preview_size)
        top = max(0, by - preview_size)
        right = min(width, bx + preview_size)
        bottom = min(height, by + preview_size)
        
        star_img = image.crop((left, top, right, bottom)).convert("RGB")
        
        # Mark the center in red
        cx = (right - left) // 2
        cy = (bottom - top) // 2
        star_img.putpixel((cx, cy), (255, 0, 0))
        
        # Save with descriptive name
        prefix = "bigstar" if is_big_star else "star"
        count = len(self.big_stars) if is_big_star else len(self.small_stars)
        filename = f"{self.preview_dir}/{prefix}_{count}.png"
        star_img.save(filename)
    
    def _save_stars_image(self, original_image, width: int, height: int) -> None:
        """
        Creates an image with black background and draws all stars with their colors.
        
        Args:
            original_image: Original image (for size reference)
            width: Image width
            height: Image height
        """
        # Create black image
        img_black = Image.new("RGB", (width, height), color=(0, 0, 0))
        draw = ImageDraw.Draw(img_black)
        
        # Draw all stars with their original RGB color
        all_stars = self.small_stars + self.big_stars
        
        for star in all_stars:
            x, y = star.x, star.y
            rgb = star.rgb_color if star.rgb_color else (255, 255, 255)  # White by default
            
            # Draw the pixel in the original color
            draw.point((x, y), fill=rgb)
            
            # Draw a small circle around for better visibility
            radius = 5 if star.area < 30 else 10
            left = max(0, x - radius)
            top = max(0, y - radius)
            right = min(width, x + radius)
            bottom = min(height, y + radius)
            
            draw.ellipse([left, top, right, bottom], outline=rgb)
        
        # Save image
        output_path = f"{self.preview_dir}/stars_detected.png"
        img_black.save(output_path)
        print(f"[OK] Stars image saved to: {output_path}")
    
    def detect(self, image, color_source_image=None) -> Tuple[List[SmallStar], List[BigStar]]:
        """
        Detects stars in a processed image.
        
        Iterates through each pixel looking for white/bright pixels in the detection image.
        For each one, searches for the brightest connected region and classifies it by area.
        
        RGB colors are obtained from color_source_image (or from image if not provided).
        
        Classification criteria:
        - SmallStar: 0 < area < 10 pixels
        - BigStar: 10 <= area < 20 pixels
        
        Args:
            image: Image to detect bright pixels (typically simplified)
            color_source_image: Image to get RGB colors from (optional, defaults to 'image')
                                  Useful for getting colors from saturated original image
        
        Returns:
            Tuple (small_stars, big_stars)
        """
        self.small_stars = []
        self.big_stars = []
        visited = set()
        pixels = image.load()
        width, height = image.size
        
        # If no color image is provided, use the same as for detection
        if color_source_image is None:
            color_source_image = image
        
        color_pixels = color_source_image.load()
        color_width, color_height = color_source_image.size
        
        # Iterate through each pixel
        for y in range(height):
            for x in range(width):
                if (x, y) in visited:
                    continue
                if not self.utils.is_white_pixel(pixels[x, y]):
                    continue
                
                # Find the brightest connected region
                (bx, by), area = self.utils.find_brightest_from(
                    pixels, x, y, width, height, visited
                )
                
                # Verificar contraste
                if not self.utils.has_sufficient_contrast(
                    pixels, bx, by, width, height
                ):
                    continue
                
                # Get pixel data (color from color_source_image)
                rgb = color_pixels[bx, by]  # Tomar color de la imagen de colores
                note = self.utils.color_to_note(
                    self.utils.intensify_color(rgb)
                )
                velocity = self.utils.brightness_to_velocity(rgb)
                pan = self.utils.get_pan(width, bx)
                
                # Classify by area
                if 3 < area < 30:
                    star = SmallStar(
                        x=bx,
                        y=by,
                        color=note,
                        brightness=velocity,
                        pan=pan,
                        area=area,
                        rgb_color=rgb,  # Guardar color original
                    )
                    self.small_stars.append(star)
                    
                    # Guardar preview cada 4 estrellas
                    #if self.save_previews and len(self.small_stars) % 100 == 0:
                    #    self._save_star_preview(image, bx, by, is_big_star=False)
                
                elif 30 <= area < 70:
                    star = BigStar(
                        x=bx,
                        y=by,
                        color=note,
                        brightness=velocity,
                        pan=pan,
                        area=area,
                        rgb_color=rgb,  # Guardar color original
                    )
                    self.big_stars.append(star)
                
                    
                    # Guardar preview cada 75 estrellas
                    #if self.save_previews and len(self.big_stars) % 75 == 0:
                    #    self._save_star_preview(image, bx, by, is_big_star=True)
        
        # Guardar imagen con estrellas sobre fondo negro
        #self._save_stars_image(image, width, height)
        
        return self.small_stars, self.big_stars
    
    def summary(self) -> dict:
        """
        Returns a summary of the detection.
        
        Returns:
            Dict with star counts and statistics
        """
        total_small = len(self.small_stars)
        total_big = len(self.big_stars)
        
        avg_area_small = (
            sum(s.area for s in self.small_stars) / total_small
            if total_small > 0
            else 0
        )
        avg_area_big = (
            sum(s.area for s in self.big_stars) / total_big
            if total_big > 0
            else 0
        )
        
        return {
            "small_stars": total_small,
            "big_stars": total_big,
            "total_stars": total_small + total_big,
            "avg_area_small": avg_area_small,
            "avg_area_big": avg_area_big,
        }
