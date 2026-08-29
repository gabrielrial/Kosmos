"""Harmony generation helpers.

This module keeps the rule for distributing a phrase across a Nebula
separate from the UI / pipeline / MIDI logic.
"""

from __future__ import annotations

import random
from typing import Iterable, List

from models.chords import Chord, ChordType


class HarmonicPath:
    """Builds a chord sequence from a nebulas dominant colors.

    The main rule is: all chords for a nebula share one phrase budget
    (`total_beats`), and each chord duration is proportional to the weight
    of its dominant color.
    """

    def __init__(self, nebula=None):
        self.nebula = nebula

    @staticmethod
    def distribute_chords_by_weight(colors: Iterable[object], total_beats: float, subdivision: int = 16) -> List[float]:
        """Return a list of duration values in beats whose sum is `total_beats`.

        The duration of each chord is proportional to the color weight. The
        final list is quantized to the grid defined by `subdivision` so the
        phrase stays musical and aligned to the beat grid.
        """
        color_list = list(colors)
        if not color_list:
            return []

        # Normalize weights; if missing, use equal distribution.
        weights = []
        for c in color_list:
            w = getattr(c, 'weight', None)
            if w is None or float(w) <= 0:
                w = 1.0
            weights.append(float(w))

        total_weight = sum(weights)
        if total_weight <= 0:
            totals = [1.0 / len(color_list)] * len(color_list)
        else:
            totals = [w / total_weight for w in weights]

        raw = [total_beats * w for w in totals]
        step = 1.0 / float(subdivision)
        quantized = []
        for d in raw:
            q = round(d / step) * step
            if q <= 0:
                q = step
            quantized.append(float(q))

        current_total = sum(quantized)
        diff = total_beats - current_total
        # Adjust the largest chord(s) so the total equals the phrase budget.
        idxs = list(range(len(quantized)))
        while abs(diff) > 1e-9:
            if diff > 0:
                idx = max(idxs, key=lambda i: quantized[i])
                quantized[idx] += step
            else:
                idx = max(idxs, key=lambda i: quantized[i])
                quantized[idx] = max(step, quantized[idx] - step)
            diff = total_beats - sum(quantized)

        return quantized

    def generate(self, total_beats: float = 32.0, subdivision: int = 16) -> List[Chord]:
        """Generate a phrase of chords for the Nebula based on dominant color weights."""
        if self.nebula is None:
            return []

        colors = list(getattr(self.nebula, 'dominant_colors', []) or [])
        if not colors:
            chords = list(getattr(self.nebula, 'chords', []) or [])
            if not chords:
                return []
            weights = [1.0 / len(chords)] * len(chords)
            durations = self.distribute_chords_by_weight(weights, total_beats, subdivision=subdivision)
            for ch, dur in zip(chords, durations):
                ch.duration = dur
            return chords

        dominant_colors = sorted(
            colors,
            key=lambda c: getattr(c, 'weight', 0.0),
            reverse=True,
        )[:5]
        random.shuffle(dominant_colors)
        durations = self.distribute_chords_by_weight(
            dominant_colors,
            total_beats,
            subdivision=subdivision,
        )

        chords = []
        root_cycle = [71, 62, 65, 68]  # B, D, F, Ab
        for idx, color in enumerate(dominant_colors):
            root = root_cycle[idx % len(root_cycle)]
            chord_type = ChordType.MAJOR if getattr(color, 'brightness', 0.5) > 0.5 else ChordType.MINOR
            # Generate root-position chords for now; inversion can be reintroduced later.
            chord = Chord(root=root, chord_type=chord_type)
            chord.duration = durations[idx]
            chords.append(chord)

        self.nebula.chords = chords
        return chords
