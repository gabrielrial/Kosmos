"""Star note mapper skeleton.

Defines StarNoteMapper interface and a simple 'nearest_chord_tone' policy
implementation that maps an incoming StarEvent to the nearest chord tone in
HarmonicContext.

This module intentionally keeps mapping policies modular so new strategies
can be added later.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

from music.orchestrator import HarmonicContext, MappedStarNote, StarEvent


class StarNoteMapper:
    """Maps StarEvent -> MappedStarNote according to a policy.

    Policy examples:
    - 'nearest_chord_tone' (default)
    - 'diatonic_scale'
    - 'voice_leading'
    """

    def __init__(self, policy: str = "nearest_chord_tone", snap_grid: Optional[float] = None):
        self.policy = policy
        # snap_grid: optional grid in beats to snap timestamps to (e.g., 0.25 for 16th)
        self.snap_grid = snap_grid

    def _snap_time(self, beat: float) -> float:
        if self.snap_grid is None:
            return beat
        return round(beat / self.snap_grid) * self.snap_grid

    def map(self, star_event: StarEvent, harmonic_context: HarmonicContext) -> MappedStarNote:
        """Map a single StarEvent into the current harmonic context.

        Returns a MappedStarNote. The default implementation is conservative:
        - find the primary chord at the star's timestamp
        - if none found, return the original note unchanged
        - otherwise map to the nearest chord tone from the chord's chord notes
        """
        beat = star_event.timestamp_beat
        if self.snap_grid:
            beat = self._snap_time(beat)

        primary = harmonic_context.get_primary_chord(beat)

        # No chord active: preserve note
        if primary is None:
            return MappedStarNote(
                mapped_note=star_event.original_note,
                timestamp_beat=beat,
                duration_beat=star_event.duration_beat,
                velocity=star_event.velocity,
                pan=star_event.pan,
                mapped_to=None,
            )

        # Get chord tones from context
        chord_notes = harmonic_context.get_scale_notes(primary)

        if not chord_notes:
            # fallback: preserve original
            return MappedStarNote(
                mapped_note=star_event.original_note,
                timestamp_beat=beat,
                duration_beat=star_event.duration_beat,
                velocity=star_event.velocity,
                pan=star_event.pan,
                mapped_to=primary,
            )

        # Choose nearest chord tone to original note (min abs diff)
        orig = star_event.original_note
        best = min(chord_notes, key=lambda n: abs(n - orig))

        return MappedStarNote(
            mapped_note=best,
            timestamp_beat=beat,
            duration_beat=star_event.duration_beat,
            velocity=star_event.velocity,
            pan=star_event.pan,
            mapped_to=primary,
        )
