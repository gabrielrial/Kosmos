from config.config import Config
from models.images import Images
from models.star import Stars, SmallStar, BigStar
from PIL import ImageDraw, Image, ImageFilter


class CloudDetector:

    def __init__(self, images: Images, stars: Stars, config: Config):
        self.config = config
        self.images = images
        self.stars = stars

    def detect(self):
        self._remove_stars()

    def _remove_stars(self):

        img = self.images.original_img.copy()
        blurred = self.images.blurred_img

        for star in self.stars.small_stars + self.stars.big_stars:
            box = self._get_star_box(star)
            blurred_region = blurred.crop(box)
            img.paste(blurred_region, box[:2])

        img.save("cloud.png")

        no_stars = img.filter(ImageFilter.BoxBlur(12))
        no_stars.save("blurred_img2.png")

        print("[OK] Stars removed and image saved to: cloud.png")

    def _get_star_box(self, star):
        half = 6

        return (
            int(star.x - half),
            int(star.y - half),
            int(star.x + half),
            int(star.y + half),
        )
