from config.config import Config
from models.images import Images
from models.star import Stars

class CloudDetector:

    def __init__(self, config: Config, images: Images, stars: Stars ):
        self.config = config
        self.images = images
        self.stars = stars

    

    