"""
Star detector in processed images.

Detects bright regions and classifies them as small or large stars.
"""

from PIL import Image, ImageDraw
from detection.utils import DetectionUtils
from models.star import SmallStar, BigStar
from models.images import Images
from models.star import Stars, SmallStar, BigStar
from config.config import StarDetectorConfig


class StarDetector:
    """Detects and classifies stars in images."""

    # Add config file

    def __init__(self, images: Images, stars: Stars, config: StarDetectorConfig):
        self.images = images
        self.utils = DetectionUtils(config)
        self.stars = stars

    def detect(self) -> None:
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

        visited = set()
        pixels = self.images.original_img.load()
        width, height = self.images.width, self.images.height

        color_source_image = self.images.original_img

        if self.images.saturated_img is not None:
            color_source_image = self.images.saturated_img

        color_pixels = color_source_image.load()

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

                 #Verificar contraste
                if not self.utils.has_sufficient_contrast(
                    pixels, bx, by, width, height, area
                 ):
                    continue

                # Get pixel data (color from color_source_image)

                pan = self.utils.get_pan(width, bx)

                note, velocity = self.utils.color_to_note_and_velocity(
                    bx, by, self.images.saturated_img
                )

                # Classify by area
                if 2 < area < 30:
                    star = SmallStar(
                        x=bx,
                        y=by,
                        note=note,
                        velocity=velocity,
                        pan=pan,
                        area=area,
                        rgb_color=color_pixels[bx, by],  # Guardar color original
                    )
                    self.stars.small_stars.append(star)

                    # Guardar preview cada 4 estrellas
                    # if self.save_previews and len(self.small_stars) % 100 == 0:
                    #    self._save_star_preview(image, bx, by, is_big_star=False)

                elif 30 <= area < 100:
                    star = BigStar(
                        x=bx,
                        y=by,
                        note=note,
                        velocity=velocity,
                        pan=pan,
                        area=area,
                        rgb_color=color_pixels[bx, by],  # Guardar color original
                    )
                    self.stars.big_stars.append(star)

                    # Guardar preview cada 75 estrellas
                #if len(self.stars.small_stars) % 10 == 0:
                #    self._save_star_preview(
                #        self.images.original_img, bx, by, is_big_star=True
                #    )

        # Guardar imagen con estrellas sobre fondo negro
        print(f"Stars detected: {len(self.stars.big_stars) + len(self.stars.small_stars)}")
        self._save_stars_image()

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
        count = len(self.stars.small_stars)
        filename = f"small_{count}.png"
        star_img.save(filename)

    def _save_stars_image(self) -> None:
        """
        Creates an image with black background and draws all stars with their colors.

        Args:
            original_image: Original image (for size reference)
            width: Image width
            height: Image height
        """
        # Create black image
        img_copy = self.images.original_img.copy()
        draw = ImageDraw.Draw(img_copy)

        # Draw all stars with their original RGB color

        for star in self.stars.small_stars + self.stars.big_stars:
            x, y = star.x, star.y
            rgb = (
                star.rgb_color if star.rgb_color else (255, 255, 255)
            )  # White by default

            # Draw the pixel in the original color
            draw.point((x, y), fill=rgb)

            # Draw a small circle around for better visibility
            radius = 5 if star.area < 30 else 10
            left = max(0, x - radius)
            top = max(0, y - radius)
            right = min(self.images.width, x + radius)
            bottom = min(self.images.height, y + radius)

            draw.ellipse([left, top, right, bottom], outline=rgb)

        # Save image
        output_path = "stars_detected.png"
        img_copy.save(output_path)
        print(f"[OK] Stars image saved to: {output_path}")
