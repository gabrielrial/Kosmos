import numpy as np
from models.nebula import Nebula

class CloudUtils:

    def __init__(self):
        pass

    def _get_filter_curve(mask, nebula: Nebula, num_points=32):
        """
        Generate a normalized filter curve from the vertical
        height of a nebula along the X axis.

        Returns values between 0.0 and 1.0.
        """

        # Bounding box of the nebula
        left = nebula.x - nebula.width // 2
        right = left + nebula.width

        # Keep coordinates inside the image
        left = max(0, left)
        right = min(mask.shape[1], right)

        width = right - left

        if width <= 0:
            return []

        # ---------------------------------------------------------
        # Measure vertical height for every X
        # ---------------------------------------------------------

        heights = []

        for x in range(left, right):

            ys = np.where(mask[:, x])[0]

            # No nebula at this X
            if len(ys) == 0:
                heights.append(0)
                continue

            top = ys.min()
            bottom = ys.max()

            height = bottom - top + 1

            heights.append(height)

        heights = np.array(heights, dtype=np.float32)

        # ---------------------------------------------------------
        # Normalize height to 0..1
        # ---------------------------------------------------------

        max_height = heights.max()

        if max_height == 0:
            return [0.0] * num_points

        heights /= max_height

        # ---------------------------------------------------------
        # Reduce the curve to a fixed number of points
        # ---------------------------------------------------------

        if len(heights) > num_points:

            x_original = np.linspace(0, 1, len(heights))

            x_target = np.linspace(0, 1, num_points)

            curve = np.interp(x_target, x_original, heights)

        else:
            curve = heights

        # ---------------------------------------------------------
        # Smooth the curve
        # ---------------------------------------------------------

        if len(curve) >= 3:

            smoothed = np.copy(curve)

            for i in range(1, len(curve) - 1):
                smoothed[i] = (curve[i - 1] + curve[i] + curve[i + 1]) / 3

            curve = smoothed

        return curve.tolist()
