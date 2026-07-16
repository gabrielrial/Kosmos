from PIL import Image

from image.image_procesing import ImageProcessor
from src.detection import StarDetector, DetectionUtils


class ImageUtils:

    def  detection(self):

        utils = DetectionUtils(
            white_threshold_v=self.pipeline.config.star_detector.white_threshold_v,
            white_threshold_s=self.pipeline.config.star_detector.white_threshold_s,
            ring_radius=self.pipeline.config.star_detector.ring_radius,
            contrast_threshold=self.pipeline.config.star_detector.contrast_threshold,
            brightness_threshold=self.pipeline.config.star_detector.brightness_threshold,
        )

        detector = StarDetector(
            utils,
            save_previews=True,
            preview_dir=str(self.pipeline.output_dir)
        )

        (
            self.pipeline.small_stars,
            self.pipeline.big_stars
        ) = detector.detect(
            simplified_img,
            color_source_image=saturated_img
        )

        self.pipeline.dominant_colors = dominant


    def magic_wand(
        self,
        output_path: str = "magic_wand.png",
        tolerance: int = 30,
        ) -> None:
        """
        Groups pixels of similar colors and replaces with average color.
        
        Simulates Photoshop's "magic wand": finds connected regions
        of similar colors and paints them with the average color of the region.
        
        Args:
            output_path: Path to save processed image
            tolerance: Maximum color distance to group (0-255)
        """
        img = self.img.copy()
        w, h = img.size
        pixels = img.load()
        visited = np.zeros((w, h), dtype=bool)
        
        def color_distance(c1: Tuple, c2: Tuple) -> int:
            """Calculates Euclidean distance between two RGB colors."""
            return sum(abs(a - b) for a, b in zip(c1, c2))
        
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
                    visited[cx, cy] = True
                    cur_color = pixels[cx, cy]
                    
                    # Add to region if color is similar
                    if color_distance(orig_color, cur_color) <= tolerance:
                        region.append((cx, cy))
                        
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
        self.magic_wand_img = img
        print(f"[OK] Magic wand saved at: {output_path}")
    
    def saturate_image(
        output_path: str = "saturated.png",
        saturation_boost: float = 1.5,
    ) -> Image.Image:
        """
        Creates a saturated version of the original image.
        
        Increases saturation to get more vibrant and varied colors.
        
        Args:
            output_path: Path to save saturated image
            saturation_boost: Saturation factor (1.0 = original, 2.0 = very saturated)
        
        Returns:
            Saturated image
        """
        from PIL import ImageEnhance
        
        # Increase saturation
        enhancer = ImageEnhance.Color(self.img)
        saturated = enhancer.enhance(saturation_boost)
        
        # Save
        self.saturated_img = saturated
        self.saturated_img.save
        
        saturated.save(output_path)
        print(f"[OK] Saturated image saved at: {output_path}")
        
        return saturated
    
    # ========================================================================
    # ANALYSIS OF DOMINANT COLORS
    # ========================================================================
    
    def dominant_colors(
        self,
        image_path: str,
        min_percentage: float = 0.02,
    ) -> List[Tuple[Tuple[int, int, int], float]]:
        """
        Extracts the dominant colors from a processed image.
        
        Args:
            image_path: Path to image (typically after magic_wand)
            min_percentage: Minimum percentage to consider a dominant color
        
        Returns:
            List of tuples (rgb_color, percentage) sorted by prevalence
        """
        img = Image.open(image_path).convert("RGB")
        data = list(img.getdata())
        total_pixels = len(data)
        
        counter = Counter(data)
        
        dominant = []
        for color, count in counter.items():
            pct = count / total_pixels
            if pct >= min_percentage:
                dominant.append((color, pct))
        
        # Sort from highest to lowest percentage
        dominant.sort(key=lambda x: x[1], reverse=True)
        
        return dominant
    
    # ========================================================================
    # REDUCTION TO DOMINANT COLORS
    # ========================================================================
    
    def _reduce_to_dominant_colors(
        self,
        grouped_image_path: str,
        dominant_colors: List[Tuple[Tuple[int, int, int], float]],
        output_path: str = "resultado_simplificado.png",
    ) -> None:
        """
        Replaces all pixels with their closest dominant color.
        
        Simplifies the image to the set of detected dominant colors.
        
        Args:
            grouped_image_path: Path to image after magic_wand
            dominant_colors: List of (rgb, percentage) of dominant colors
            output_path: Path to save simplified image
        """
        img = Image.open(grouped_image_path).convert("RGB")
        w, h = img.size
        pixels = img.load()
        
        # Extract only RGB colors
        colors_only = [c for c, pct in dominant_colors]
        
        def color_distance(c1: Tuple, c2: Tuple) -> int:
            """Euclidean distance between colors."""
            return sum(abs(a - b) for a, b in zip(c1, c2))
        
        # Replace each pixel with the closest dominant color
        for y in range(h):
            for x in range(w):
                original = pixels[x, y]
                closest = min(
                    colors_only,
                    key=lambda dc: color_distance(dc, original)
                )
                pixels[x, y] = closest
        
        img.save(output_path)
        print(f"[OK] Simplified image saved at: {output_path}")
    
    # ========================================================================
    # VISUALIZATION
    # ========================================================================
    
    def save_color_bar(
        self,
        colors: List[Tuple[Tuple[int, int, int], float]],
        output_path: str = "color_bar.png",
        bar_width: int = 100,
        bar_height: int = 400,
    ) -> None:
        """
        Creates a visual bar of dominant colors with their percentages.
        
        Args:
            colors: List of (rgb, percentage)
            output_path: Path to save the bar
            bar_width: Width of the bar in pixels
            bar_height: Height of the bar in pixels
        """
        img = Image.new("RGB", (bar_width, bar_height), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        current_y = 0
        for i, (color, pct) in enumerate(colors):
            segment_height = int(bar_height * pct)
            
            # Adjust last segment so there's no gap
            if i == len(colors) - 1:
                segment_height = bar_height - current_y
            
            draw.rectangle(
                [0, current_y, bar_width, current_y + segment_height],
                fill=color
            )
            current_y += segment_height
        
        img.save(output_path)
        print(f"[OK] Color bar saved at: {output_path}")
    
    @staticmethod
    def visualize_stars(
        image: Image.Image,
        stars: List,
        output_path: str = "stars_visualization.png",
        center_color: Tuple = (255, 0, 0),
        ring_color: Tuple = (0, 0, 255),
        ring_radius: int = 2,
    ) -> None:
        """
        Visualizes detected stars over the image.
        
        Args:
            image: PIL image to draw on
            stars: List of Star objects (with x, y, area)
            output_path: Path to save visualization
            center_color: RGB color to mark center
            ring_color: RGB color to mark ring
            ring_radius: Radius of ring to visualize
        """
        img_copy = image.copy()
        draw = ImageDraw.Draw(img_copy)
        
        for star in stars:
            x, y = star.x, star.y
            
            # Mark center
            draw.point((x, y), fill=center_color)
            
            # Mark ring
            R = ring_radius
            for dx in range(-R, R + 1):
                for dy in range(-R, R + 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < img_copy.width and 0 <= ny < img_copy.height:
                        draw.point((nx, ny), fill=ring_color)
        
        img_copy.save(output_path)
        print(f"[OK] Visualization saved at: {output_path}")



