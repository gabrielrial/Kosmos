"""
x = int
y = int
note = int
velocity = [0 - 127]
pan = [0 - 127]
rgb_color = tuple (r,g,b)
duration = float
"""


class SmallStar:
    def __init__(self, x, y, color, brightness, pan, area, duration=0, rgb_color=None):
        self.x = x
        self.y = y
        self.note = color  # enhanced color (MIDI note)
        self.velocity = max(1, min(127, int(brightness)))[0 - 127]
        self.pan = pan  # int - midi [0 - 127]
        self.area = area
        self.rgb_color = rgb_color  # tuple (r, g, b) with original color
        self.duration = duration


class BigStar:
    def __init__(self, x, y, color, brightness, pan, area, duration=0, rgb_color=None):
        self.x = x  # normalize to 0-1 if desired for position (?)
        self.y = y
        self.note = color  # enhanced color (MIDI note)
        self.velocity = max(1, min(127, int(brightness)))
        self.pan = pan  # int - midi [0 - 127]
        self.area = area
        self.rgb_color = rgb_color  # tuple (r, g, b) with original color
        self.duration = duration
