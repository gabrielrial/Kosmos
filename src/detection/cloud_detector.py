from config.config import Config
from models.images import Images
from models.star import Stars
from models.nebula import Nebula
from models.color import Color
from detection.cloud_utils import CloudUtils
from PIL import Image, ImageDraw
import numpy as np
from scipy import ndimage


class CloudDetector:

    def __init__(self, images: Images, stars: Stars, config: Config):
        self.config = config
        self.images = images
        self.stars = stars
        self.utils = CloudUtils

    def detect(self):
        no_stars = self._remove_stars()

        nebulas = self._detect_nebulas(no_stars)

        print(f"[OK] Detected {len(nebulas)} nebulas")

        for i, nebula in enumerate(nebulas):
            print(
                f"Nebula {i + 1}: "
                f"position=({nebula.x}, {nebula.y}), "
                f"size={nebula.width}x{nebula.height}, "
                f"area={nebula.area}, "
                f"density={nebula.density:.2f}, "
                f"brightness={nebula.brightness:.2f}, "
                f"hue={nebula.hue:.2f}, "
                f"saturation={nebula.saturation:.2f}"
            )

        return nebulas

    def _remove_stars(self):
        """
        Remove detected stars from the image.
        """

        img = self.images.original_img.copy()
        blurred = self.images.blurred_img

        for star in self.stars.small_stars + self.stars.big_stars:
            box = self._get_star_box(star)

            blurred_region = blurred.crop(box)

            img.paste(blurred_region, box[:2])

        # img.save("cloud.png")

        print("[OK] Stars removed and image saved to: cloud.png")

        return img

    def _detect_nebulas(self, img):
        """
        Detect extended colored regions.

        The detection is based primarily on:
        - darkness of the background
        - color saturation
        - connected regions
        - minimum area
        """

        # Convert image to HSV.
        #
        # H = Hue
        # S = Saturation
        # V = Brightness
        hsv = np.array(img.convert("HSV"))

        # Array with each h, s and b
        hue = hsv[:, :, 0].astype(np.float32)
        saturation = hsv[:, :, 1].astype(np.float32)
        brightness = hsv[:, :, 2].astype(np.float32)

        # Normalize to 0..1
        hue /= 255.0
        saturation /= 255.0
        brightness /= 255.0

        # ---------------------------------------------------------
        # Detection parameters
        # ---------------------------------------------------------

        # Pixels darker than this are considered background.
        min_brightness = 0.2

        # Pixels below this saturation are considered too gray.
        min_saturation = 0.3

        # ---------------------------------------------------------
        # Create candidate mask
        # ---------------------------------------------------------

        not_background = brightness > min_brightness
        has_color = saturation > min_saturation

        mask = not_background & has_color

        # ---------------------------------------------------------
        # Clean the mask
        # ---------------------------------------------------------

        # Remove very small isolated pixels/groups.
        mask = ndimage.binary_opening(mask, structure=np.ones((3, 3)))

        # Connect nearby pixels belonging to the same structure.
        mask = ndimage.binary_closing(mask, structure=np.ones((5, 5)))

        # ---------------------------------------------------------
        # Find connected regions
        # ---------------------------------------------------------

        labeled, num_features = ndimage.label(mask)

        print(f"[DEBUG] Candidate regions: {num_features}")

        # Final mask containing only accepted nebulas
        nebula_mask = np.zeros_like(mask, dtype=bool)

        nebulas = []

        # ---------------------------------------------------------
        # Analyze every region
        # ---------------------------------------------------------

        for label in range(1, num_features + 1):

            ys, xs = np.where(labeled == label)

            if len(xs) == 0:
                continue

            area = len(xs)

            # Ignore small regions.
            #
            # This is important because stars, noise and small
            # colored artifacts can otherwise become nebulas.
            min_area = 10000

            if area < min_area:
                continue

            # Bounding box
            min_x = xs.min()
            max_x = xs.max()

            min_y = ys.min()
            max_y = ys.max()

            width = max_x - min_x + 1
            height = max_y - min_y + 1

            # How much of the bounding box is actually occupied?
            density = area / (width * height)

            # -----------------------------------------------------
            # Average properties of this region
            # -----------------------------------------------------

            region_brightness = brightness[ys, xs]
            region_saturation = saturation[ys, xs]
            region_hue = hue[ys, xs]

            average_brightness = float(np.mean(region_brightness))

            average_saturation = float(np.mean(region_saturation))

            # Hue is circular.
            #
            # We calculate the average using vectors instead
            # of simply using np.mean().
            #
            # This avoids problems when hue wraps around
            # from 1.0 back to 0.0.
            angles = region_hue * 2 * np.pi

            hue_x = np.mean(np.cos(angles))
            hue_y = np.mean(np.sin(angles))

            average_hue = np.arctan2(hue_y, hue_x) / (2 * np.pi)

            if average_hue < 0:
                average_hue += 1

            # Center of the region
            center_x = int(np.mean(xs))
            center_y = int(np.mean(ys))

            # Keep this region in the final mask
            nebula_mask[labeled == label] = True

            nebulas.append(
                Nebula(
                    x=center_x,
                    y=center_y,
                    width=width,
                    height=height,
                    area=area,
                    density=density,
                    brightness=average_brightness,
                    hue=float(average_hue),
                    saturation=average_saturation,
                )
            )

        # ---------------------------------------------------------
        # Save debug images
        # ---------------------------------------------------------

        self._save_nebula_mask(nebula_mask)

        self._save_debug_image(self.images.original_img, nebulas)

        self._save_dominant_colors(img, labeled, nebulas)

        for i, nebula in enumerate(nebulas):

            curve = self.utils._get_filter_curve(nebula_mask, nebula)

            print(f"Nebula {i + 1} filter curve:")

            print([round(value, 2) for value in curve])

        return nebulas

    def _save_nebula_mask(self, mask):
        """
        Save detected nebulas as a black/white image.
        """

        mask_img = Image.fromarray((mask.astype(np.uint8) * 255))

        mask_img.save("nebulas.png")

        print("[OK] Nebula mask saved to: nebulas.png")

    def _save_debug_image(self, original_img, nebulas):
        """
        Save the original image with detected nebulas
        highlighted by red bounding boxes.
        """

        debug = original_img.convert("RGB").copy()

        draw = ImageDraw.Draw(debug)

        for i, nebula in enumerate(nebulas):

            left = nebula.x - nebula.width // 2
            top = nebula.y - nebula.height // 2

            right = left + nebula.width
            bottom = top + nebula.height

            # Bounding box
            draw.rectangle((left, top, right, bottom), outline=(255, 0, 0), width=2)

            # Label
            text = f"Nebula {i + 1}"

            draw.text((left, top - 15), text, fill=(255, 0, 0))

        debug.save("nebula_debug.png")

        print("[OK] Debug image saved to: nebula_debug.png")

    def _get_star_box(self, star):
        half = 6

        return (
            int(star.x - half),
            int(star.y - half),
            int(star.x + half),
            int(star.y + half),
        )

    def _save_dominant_colors(self, img, labeled, nebulas):
        """
        Create a 100x100 color palette image for each nebula.

        Each color occupies a portion of the image proportional
        to how frequently it appears in the nebula.
        """

        rgb = np.array(img.convert("RGB"))

        for i, nebula in enumerate(nebulas):

            # Get the label corresponding to this nebula.
            #
            # Nebula objects are created in the same order as
            # the accepted labels.
            #
            # We therefore find the label by looking for the
            # region around the nebula center.
            center_label = labeled[nebula.y, nebula.x]

            if center_label == 0:
                continue

            # Pixels belonging to this nebula
            ys, xs = np.where(labeled == center_label)

            if len(xs) == 0:
                continue

            # RGB values of all pixels in this nebula
            pixels = rgb[ys, xs]

            # ---------------------------------------------------------
            # Reduce the number of colors
            # ---------------------------------------------------------

            # Convert the pixels to a small palette.
            #
            # Pillow's quantize() is useful here because astronomical
            # images can contain thousands of slightly different RGB
            # values.
            pixel_img = Image.fromarray(
                pixels.reshape(1, len(pixels), 3).astype(np.uint8), "RGB"
            )

            quantized = pixel_img.quantize(colors=5, method=Image.Quantize.MEDIANCUT)

            palette = quantized.getpalette()
            color_counts = quantized.getcolors()

            if color_counts is None:
                continue

            # ---------------------------------------------------------
            # Extract dominant colors
            # ---------------------------------------------------------

            dominant_colors = []

            for count, color_index in color_counts:

                r = palette[color_index * 3]
                g = palette[color_index * 3 + 1]
                b = palette[color_index * 3 + 2]

                dominant_colors.append((count, (r, g, b)))

            # Sort from most common to least common
            dominant_colors.sort(key=lambda x: x[0], reverse=True)

            # ---------------------------------------------------------
            # Create 100x100 image
            # ---------------------------------------------------------

            palette_img = Image.new("RGB", (100, 100))

            draw = ImageDraw.Draw(palette_img)

            total_pixels = sum(count for count, _ in dominant_colors)

            current_x = 0

            for count, color in dominant_colors:

                proportion = count / total_pixels

                width = int(proportion * 100)

                # Make sure the last color reaches the edge.
                if (count, color) == dominant_colors[-1]:
                    width = 100 - current_x

                draw.rectangle((current_x, 0, current_x + width, 100), fill=color)

                current_x += width

            filename = f"nebula_{i + 1}_colors.png"

            palette_img.save(filename)

            print(f"[OK] Dominant colors saved to: {filename}")

            for count, color in dominant_colors:

                percentage = (count / total_pixels) * 100

                print(f"    RGB={color} " f"{percentage:.1f}%")

            # ---------------------------------------------------------
            # Keep the detector focused on extraction only.
            # The actual harmonic phrase is generated by HarmonicPath +
            # MusicOrchestrator, which is the single source of truth.
            # ---------------------------------------------------------
            try:
                import colorsys

                nebula.dominant_colors = []
                for count, (r, g, b) in dominant_colors:
                    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
                    weight = count / total_pixels if total_pixels > 0 else 0
                    nebula.dominant_colors.append(
                        Color(
                            hue=float(h),
                            saturation=float(s),
                            brightness=float(v),
                            weight=float(weight),
                        )
                    )

                print(
                    f"[HARMONY DEBUG] Nebula {i + 1}: extracted {len(nebula.dominant_colors)} dominant colors "
                    f"(weights will be used by HarmonicPath / MusicOrchestrator)"
                )
                for idx, color in enumerate(nebula.dominant_colors[:5]):
                    print(
                        f"    {idx}: hue={color.hue:.3f} sat={color.saturation:.3f} "
                        f"bright={color.brightness:.3f} weight={color.weight:.4f}"
                    )

            except Exception as e:
                print(f"[HARMONY DEBUG] Could not store dominant colors for nebula {i + 1}: {e}")
