"""
Utilities for star detection.

Provides methods for pixel analysis, contrast calculation,
and color → MIDI note conversions.
"""

from typing import Tuple, List, Set
from PIL import Image
from config.config import StarDetectorConfig


class DetectionUtils:
    """Utilities for detecting and analyzing stars in images."""

    def __init__(self, config: StarDetectorConfig):
        self.config = config

    # ========================================================================
    # DETECTION OF WHITE/BRIGHT PIXELS
    # ========================================================================

    def is_white_pixel(self, rgb: Tuple[int, int, int]) -> bool:
        """
        Detects if a pixel is white or bright.

        A pixel is considered white/bright if:
        1. Its absolute brightness >= brightness_threshold, OR
        2. It is desaturated white (v >= white_threshold_v AND s <= white_threshold_s)

        Args:
            rgb: Tuple (r, g, b) with values 0-255

        Returns:
            True if the pixel is white/bright
        """
        brightness = sum(rgb) / 3

        # Criterio 1: Brillo absoluto
        if brightness >= self.config.brightness_threshold:
            return True

    # ========================================================================
    # NEIGHBORHOOD ANALYSIS (RING)
    # ========================================================================

    def get_neighbors_8(
        self, x: int, y: int, width: int, height: int) -> List[Tuple[int, int]]:
        """
        Returns the 8 neighbors of a pixel (3x3 without the center).

        Args:
            x, y: Pixel coordinates
            width, height: Image dimensions

        Yields:
            Tuples (nx, ny) of valid neighboring pixels
        """
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    yield nx, ny

    def get_ring_colors(
        self,
        pixels,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> List[Tuple[int, int, int]]:
        """
        Returns all colors in the ring around a pixel.

        The ring is a square of radius self.ring_radius around the pixel.

        Args:
            pixels: PIL.ImageDraw object with pixel data (pixels[x, y])
            x, y: Ring center
            width, height: Image dimensions

        Returns:
            List of (r, g, b) tuples
        """
        ring = []
        R = self.config.ring_radius
        for dx in range(-R, R + 1):
            for dy in range(-R, R + 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    ring.append(pixels[nx, ny])
        return ring

    def calculate_ring_brightness(
        self,
        pixels,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> float:
        """
        Calculates the average brightness of the ring around a pixel.

        Args:
            pixels: PIL object with pixel data
            x, y: Ring center
            width, height: Dimensions

        Returns:
            Average brightness (0-255)
        """
        ring = self.get_ring_colors(pixels, x, y, width, height)
        if not ring:
            return 0
        avg_brightness = sum(sum(pixel) / 3 for pixel in ring) / len(ring)
        return avg_brightness

    def has_sufficient_contrast(
        self,
        pixels,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> bool:
        """
        Verifies if there is sufficient contrast between center and ring.

        Contrast is defined as: center_brightness - ring_brightness

        Args:
            pixels: PIL object with data
            x, y: Pixel to verify
            width, height: Dimensions

        Returns:
            True if contrast >= contrast_threshold
        """
        center_brightness = sum(pixels[x, y]) / 3
        ring_brightness = self.calculate_ring_brightness(pixels, x, y, width, height)
        contrast = center_brightness - ring_brightness
        return contrast >= self.config.contrast_threshold

    # ========================================================================
    # FLOOD-FILL SEARCH
    # ========================================================================

    def find_brightest_from(
        self,
        pixels,
        x: int,
        y: int,
        width: int,
        height: int,
        visited: Set[Tuple[int, int]],
    ) -> Tuple[Tuple[int, int], int]:
        """
        Searches for the brightest pixel in a connected region of white pixels.

        Uses flood-fill to find all connected white pixels,
        marks the brightest one and returns its position and total area.

        Args:
            pixels: PIL object with data
            x, y: Starting point
            width, height: Dimensions
            visited: Set of already visited pixels (modified)

        Returns:
            Tuple ((bx, by), area):
                - (bx, by): Coordinates of the brightest pixel
                - area: Number of pixels in the region
        """
        stack = [(x, y)]
        brightest = (x, y)
        max_brightness = sum(pixels[x, y]) / 3
        area = 0

        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in visited:
                continue
            visited.add((cx, cy))
            area += 1

            brightness = sum(pixels[cx, cy]) / 3
            if brightness > max_brightness:
                brightest = (cx, cy)
                max_brightness = brightness

            # Agregar vecinos blancos al stack
            for nx, ny in self.get_neighbors_8(cx, cy, width, height):
                if (nx, ny) not in visited and self.is_white_pixel(pixels[nx, ny]):
                    stack.append((nx, ny))

        return brightest, area

    # ========================================================================
    # COLOR/POSITION → MIDI CONVERSIONS
    # ========================================================================

    def get_pan(self, width: int, x: int) -> float:
        """
        Convierte coordenada X a paneo MIDI (0-127).

        Args:
            width: Ancho de la imagen
            x: X position of the pixel

        Returns:
            Paneo MIDI (0.0-127.0)
        """
        return (x * 127) / width

    def color_to_note_and_velocity(self, bx: int, by: int, saturated_img: Image) -> Tuple[int, int]:
        """
        Converts an RGB color to a MIDI note and velocity.

        Args:
            rgb: (r, g, b) tuple.

        Returns:
            A tuple containing:
                - MIDI note (36-71) -> C2 - B5
                - MIDI velocity (40-100)
        """
        r,g,b = saturated_img.getpixel([bx, by])

        # Average brightness (0-255)
        brightness = (r + g + b) / 3

        # Map brightness to note (0-255 -> 36-71)
        note = int(brightness * 35 / 255) + 36

        # Clamp brightness so that anything darker than (50, 50, 50)
        # is treated as the minimum velocity.
        brightness = max(50, min(brightness, 255))

        # Map brightness (50-255) -> velocity (40-100)
        velocity = int((brightness - 50) * 60 / (255 - 50)) + 40

        return note, velocity

    def color_to_note(self, rgb: Tuple[int, int, int]) -> int:
        """
        Converts an RGB color to a MIDI note.

        Args:
            rgb: (r, g, b) tuple.

        Returns:
            MIDI note (36-71) -> C2 - B5.
        """
        r, g, b = rgb

        brightness = (r + g + b) / 3

        note = int(brightness * 35 / 255) + 36

        return note

    def brightness_to_velocity(self, rgb: Tuple[int, int, int]) -> int:
        """
        Convierte brillo RGB a velocidad MIDI.

        Delega a src.models.color.brightness_to_velocity()

        Args:
            rgb: Tupla (r, g, b)

        Returns:
            Velocidad MIDI (40-127)
        """
        r, g, b = rgb

        brightness = (r + g + b) / 3

        velocity = int(brightness * 87 / 255) + 40

        return velocity

