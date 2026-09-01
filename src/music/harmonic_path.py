"""Harmony generation helpers.

This module keeps the rule for distributing a phrase across a Nebula
separate from the UI / pipeline / MIDI logic.
"""

from __future__ import annotations

import random
from typing import Iterable, List, Sequence

from models.chords import Chord, ChordType


def compute_color_expression_level(colors: Iterable[object]) -> int:
    """Compute a 4-level expression score from the dominant colors of a nebula.

    The idea is intentionally simple and future-proof:
    - similar colors -> low expression / calmer harmonic motion
    - very different colors -> high expression / more dramatic movement

    We score the color set by combining the main visual differences:
      - hue distance
      - saturation distance
      - brightness distance
      - weight diversity

    The result is clamped to the range 0..3, which maps to four levels:
    0 = calm, 1 = moderate, 2 = expressive, 3 = dramatic.
    """
    colors = list(colors)
    if not colors:
        return 0

    def hue_distance(a: float, b: float) -> float:
        diff = abs(a - b) % 1.0
        return min(diff, 1.0 - diff)

    # Base score using differences between the dominant colors.
    hue_values = [float(getattr(c, 'hue', 0.0)) for c in colors]
    sat_values = [float(getattr(c, 'saturation', 0.0)) for c in colors]
    bright_values = [float(getattr(c, 'brightness', 0.0)) for c in colors]
    weight_values = [float(getattr(c, 'weight', 0.0)) for c in colors]

    # Average pairwise differences.
    hue_score = 0.0
    sat_score = 0.0
    bright_score = 0.0
    pair_count = 0
    for i in range(len(colors)):
        for j in range(i + 1, len(colors)):
            pair_count += 1
            hue_score += hue_distance(hue_values[i], hue_values[j])
            sat_score += abs(sat_values[i] - sat_values[j])
            bright_score += abs(bright_values[i] - bright_values[j])

    if pair_count:
        hue_score /= pair_count
        sat_score /= pair_count
        bright_score /= pair_count
    else:
        hue_score = sat_score = bright_score = 0.0

    # Weight diversity: if the weight distribution is balanced, there is more
    # harmonic richness; if a single color dominates too much, expression is lower.
    weight_total = sum(weight_values) or 1.0
    normalized_weights = [w / weight_total for w in weight_values]
    weight_entropy = -sum(p * __import__('math').log2(p) for p in normalized_weights if p > 0)
    # Normalize entropy to the max possible for the set size. This is a rough but
    # useful proxy for color diversity in the nebulas distribution.
    max_entropy = __import__('math').log2(max(len(normalized_weights), 2))
    weight_diversity = weight_entropy / max_entropy if max_entropy > 0 else 0.0

    # Combine factors. This intentionally emphasizes hue and brightness because
    # they are the most relevant for harmonic contrast in the current model.
    score = (
        0.55 * hue_score
        + 0.25 * sat_score
        + 0.15 * bright_score
        + 0.05 * weight_diversity
    )

    # Map to 4 levels: 0..3.
    if score < 0.18:
        return 0
    if score < 0.35:
        return 1
    if score < 0.55:
        return 2
    return 3


class HarmonicScale:
    """Represents a circular harmonic root lattice.

    Each group is a row of 4 roots. The same index across rows is offset by one
    semitone, which creates the harmonic motion described by the project:
    B -> C -> Db -> ... while the structure remains a cyclic frame. This class is
    intentionally small and can later grow to 7 groups when needed.
    """

    DEFAULT_GROUPS: Sequence[Sequence[int]] = (
        (71, 62, 65, 68),  # B, D, F, Ab
        (72, 63, 66, 69),  # C, Eb, F#, A
        (73, 64, 67, 70),  # Db, E, G, Bb
        (74, 65, 68, 71),  # D, F, Ab, B
        (75, 66, 69, 72),  # Eb, F#, A, C
    )

    def __init__(self, groups: Sequence[Sequence[int]] | None = None, octave_offset: int = 0):
        self.groups = tuple(tuple(group) for group in (groups or self.DEFAULT_GROUPS))
        self.octave_offset = int(octave_offset)

    def get_root(self, group_index: int, slot_index: int) -> int:
        group = self.groups[group_index % len(self.groups)]
        root = group[slot_index % len(group)]
        midi_value = root + (self.octave_offset * 12)
        return max(0, min(127, midi_value))


class HarmonicPath:
    """Builds a chord sequence from a nebulas dominant colors.

    The main rule is: all chords for a nebula share one phrase budget
    (`total_beats`), and each chord duration is proportional to the weight
    of its dominant color.
    """

    def __init__(self, nebula=None, octave_offset: int = 0):
        self.nebula = nebula
        self.octave_offset = int(octave_offset)
        self.scale = HarmonicScale(octave_offset=self.octave_offset)

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
        for idx, color in enumerate(dominant_colors):
            group_index = idx % len(self.scale.groups)
            slot_index = idx % 4
            root = self.scale.get_root(group_index, slot_index)
            chord_type = ChordType.MAJOR if getattr(color, 'brightness', 0.5) > 0.5 else ChordType.MINOR
            # Generate root-position chords for now; inversion can be reintroduced later.
            chord = Chord(root=root, chord_type=chord_type)
            chord.duration = durations[idx]
            chords.append(chord)

        self.nebula.chords = chords
        return chords
