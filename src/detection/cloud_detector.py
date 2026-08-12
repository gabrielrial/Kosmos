from config.config import Config
from models.images import Images
from models.star import Stars, SmallStar, BigStar
from PIL import ImageDraw

class CloudDetector:

    def __init__(self, images: Images, stars: Stars, config: Config):
        self.config = config
        self.images = images
        self.stars = stars


    def detect(self):
        self._remove_stars()
        


    def _remove_stars(self):
        img_copy = self.images.original_img.copy()
        img_blurred = self.images.blurred_img
        draw = ImageDraw.Draw(img_copy)

        for star in self.stars.small_stars:
            x, y = star.x,star.y
            draw.circle([x, y], star.area/4, (0,0,0))

        img_copy.save("cloud.png")
        print(f"[OK] Stars image saved to: cloud")

        

    

    

    