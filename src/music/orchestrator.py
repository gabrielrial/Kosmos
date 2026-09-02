"""Music orchestration layer skeleton.

Defines:
- TimelineItem: container for a chord occurrence on a timeline (start/end in beats)
- StarEvent: representation of a star-origin note event (timestamp in beats)
- MappedStarNote: result of mapping a StarEvent to harmonic context
- HarmonicContext: queryable view over a harmonic timeline
- MusicOrchestrator: coordinates nebula chord progressions + star events

This file implements safe, minimal functionality so other modules can
use the interfaces and tests can be written. Detailed policies and
optimizations are left for later iterations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Iterable, Tuple

from models.nebula import Nebula
from models.chords import Chord


@dataclass
class TimelineItem:
    """Represents an occurrence of a chord on the global timeline.

    start_beat and end_beat are expressed in beats (floating point).
    """

    start_beat: float
    end_beat: float
    chord: Chord
    source_nebula: Optional[Nebula] = None
    weight: float = 1.0


@dataclass
class StarEvent:
    """Represents a single note event produced by a star.

    original_note: MIDI note number
    velocity: int
    timestamp_beat: float
    duration_beat: float
    pan: Optional[float] = None
    source_star: Optional[object] = None
    """

    original_note: int
    velocity: int
    timestamp_beat: float
    duration_beat: float
    pan: Optional[float] = None
    source_star: Optional[object] = None


@dataclass
class MappedStarNote:
    """Star note mapped to harmonic context.

    - mapped_note: MIDI note number after mapping/quantization
    - timestamp_beat / duration_beat: scheduled timing in beats
    - velocity, pan
    - mapped_to: TimelineItem (the chord item it was mapped to) or None
    """

    mapped_note: int
    timestamp_beat: float
    duration_beat: float
    velocity: int
    pan: Optional[float] = None
    mapped_to: Optional[TimelineItem] = None


class HarmonicContext:
    """Provides query functions over a harmonic timeline.

    The internal timeline is expected to be a list of TimelineItem sorted
    by start_beat. This skeleton implements linear/binary searching for
    active chords and a simple primary-chord policy.
    """

    def __init__(self, timeline: Iterable[TimelineItem]):
        # Ensure sorted timeline
        self.timeline: List[TimelineItem] = sorted(timeline, key=lambda t: t.start_beat)

    def get_active_chords(self, beat: float) -> List[TimelineItem]:
        """Return all timeline items active at the given beat."""
        active = [ti for ti in self.timeline if ti.start_beat <= beat < ti.end_beat]
        return active

    def get_primary_chord(self, beat: float) -> Optional[TimelineItem]:
        """Resolve a single primary chord active at `beat`.

        Default policy: choose the active chord with highest weight. If none,
        return None.
        """
        active = self.get_active_chords(beat)
        if not active:
            return None
        primary = max(active, key=lambda ti: ti.weight)
        return primary

    def get_scale_notes(self, chord_item: TimelineItem) -> List[int]:
        """Return a list of MIDI notes representing the scale/notes permissible
        for the chord. For the skeleton we return the chord tones (triad) in
        the octave of the chord.root.
        """
        # Attempt to use chord.chord_notes() or chord.chord_maker()
        chord = chord_item.chord
        notes: List[int] = []
        try:
            notes = chord.chord_notes()
        except Exception:
            try:
                notes = chord.chord_maker()
            except Exception:
                notes = []
        return notes

    def is_chord_change(self, beat: float) -> bool:
        """Return True if there is a chord boundary exactly at `beat`.

        (Useful to decide whether to re-quantize or re-arm voice-leading)
        """
        for ti in self.timeline:
            if abs(ti.start_beat - beat) < 1e-9:
                return True
            if abs(ti.end_beat - beat) < 1e-9:
                return True
        return False

    def get_next_chord_change(self, beat: float) -> Optional[float]:
        """Return the next beat strictly greater than `beat` where a chord change occurs.
        Returns None if no change ahead.
        """
        candidates = [ti.start_beat for ti in self.timeline if ti.start_beat > beat]
        candidates += [ti.end_beat for ti in self.timeline if ti.end_beat > beat]
        return min(candidates) if candidates else None


class MusicOrchestrator:
    """Coordinates nebulas (harmonic progressions) and star events (melody).

    Responsibilities (skeleton):
    - accept nebulae (each with .chords list)
    - accept star events
    - build a unified harmonic timeline
    - expose HarmonicContext and allow mapping star events via an external mapper
    """

    def __init__(
        self,
        tempo_bpm: float = 120.0,
        overlap_policy: str = "priority",
        nebula_total_duration_beats: float = 32.0,
        subdivision: int = 16,
        octave_offset: int = 0,
    ):
        self.tempo_bpm = tempo_bpm
        self.nebulae: List[Nebula] = []
        self.star_events: List[StarEvent] = []
        self.timeline: List[TimelineItem] = []
        self.overlap_policy = overlap_policy
        self.nebula_total_duration_beats = float(nebula_total_duration_beats)
        self.subdivision = int(subdivision)
        self.octave_offset = int(octave_offset)

    # --- registration API -------------------------------------------------
    def register_nebulae(self, nebulae: Iterable[Nebula]) -> None:
        self.nebulae = list(nebulae)

    def register_star_events(self, star_events: Iterable[StarEvent]) -> None:
        self.star_events = list(star_events)

    # --- timeline construction --------------------------------------------
    def build_harmonic_timeline(self) -> List[TimelineItem]:
        """Convert each Nebula.chords sequence into TimelineItem entries.

        Assumptions:
        - nebula.chords is an ordered iterable of chord-like objects with a
          duration attribute (in beats). If duration not present defaults to 1.0.
        - Nebula may optionally provide a start_offset attribute (beats). If not
          present, start at 0 for that nebula.
        """
        timeline_raw: List[TimelineItem] = []

        for neb in self.nebulae:
            start_offset = getattr(neb, "start_offset", 0.0)
            cum = start_offset

            # weight heuristic: prefer explicit weight or area
            neb_weight = getattr(neb, "area", 1.0)

            chords = list(getattr(neb, "chords", []) or [])
            if (
                not chords
                and hasattr(neb, "dominant_colors")
                and getattr(neb, "dominant_colors")
            ):
                from music.harmonic_path import HarmonicPath

                chords = HarmonicPath(neb).generate(
                    total_beats=self.nebula_total_duration_beats,
                    subdivision=self.subdivision,
                )
                print(
                    f"[HARMONY DEBUG] Nebula {getattr(neb, 'x', 'n')} -> Generated {len(chords)} chords "
                    f"from dominant colors total_duration={self.nebula_total_duration_beats}"
                )
                for j, ch in enumerate(chords):
                    root_val = getattr(ch, "note", getattr(ch, "root", None))
                    print(
                        f"    {j}: root={root_val} type={ch.chord_type.name} "
                        f"duration={getattr(ch, 'duration', 0)} notes={ch.chord_maker()}"
                    )
            elif chords and any(getattr(ch, "duration", None) is None for ch in chords):
                # If the chords do not have explicit duration, distribute the whole
                # nebula phrase across the colors by their relative weight.
                if hasattr(neb, "dominant_colors") and getattr(neb, "dominant_colors"):
                    from music.harmonic_path import HarmonicPath

                    generated = HarmonicPath(
                        neb, octave_offset=self.octave_offset
                    ).generate(
                        total_beats=self.nebula_total_duration_beats,
                        subdivision=self.subdivision,
                    )
                    chords = generated
                else:
                    # Fallback: equal duration across chord list with phrase size budget.
                    step = float(self.nebula_total_duration_beats) / max(len(chords), 1)
                    for ch in chords:
                        ch.duration = step

            for ch in chords:
                duration = getattr(ch, "duration", None)
                if duration is None:
                    duration = self.nebula_total_duration_beats / max(len(chords), 1)
                duration = float(duration)
                if duration <= 0:
                    duration = self.nebula_total_duration_beats / max(len(chords), 1)

                # Ensure each chord in a nebula does not overlap with the next by
                # placing them sequentially using the cumulative cursor `cum`.
                ti = TimelineItem(
                    start_beat=cum,
                    end_beat=cum + float(duration),
                    chord=ch,
                    source_nebula=neb,
                    weight=float(neb_weight),
                )
                timeline_raw.append(ti)
                cum += float(duration)

        # sort raw timeline
        timeline_raw = sorted(timeline_raw, key=lambda t: t.start_beat)

        # Resolve overlaps globally so that at any time at most one chord is active.
        timeline_resolved = self._resolve_overlaps(timeline_raw)

        # store both raw and resolved timelines
        self.timeline_raw = timeline_raw
        self.timeline = timeline_resolved
        # Keep the phrase coherent: the total beat budget should be respected by
        # the generated chord durations. This is especially important for the
        # harmonic path generation used in nebulas.
        return self.timeline

    def _resolve_overlaps(self, timeline: List[TimelineItem]) -> List[TimelineItem]:
        """Resolve overlapping TimelineItem entries so only one chord is active at a time.

        Policy: sweep-line; for each contiguous time segment choose the active
        TimelineItem with highest weight. Adjacent segments with the same chord
        are merged.
        """
        if not timeline:
            return []

        # Create event points
        events: List[Tuple[float, str, TimelineItem]] = []  # (time, type, item)
        for item in timeline:
            events.append((item.start_beat, "start", item))
            events.append((item.end_beat, "end", item))

        # Sort events: by time, then start before end to prefer newly started at same time
        events.sort(key=lambda e: (e[0], 0 if e[1] == "start" else 1))

        active: List[TimelineItem] = []
        resolved: List[TimelineItem] = []

        # Iterate through event times, keeping track of current active set
        for idx in range(len(events) - 1):
            time, typ, item = events[idx]
            # Apply event
            if typ == "start":
                active.append(item)
            else:
                # remove matching item if present
                try:
                    active.remove(item)
                except ValueError:
                    pass

            next_time = events[idx + 1][0]
            if next_time <= time:
                continue

            if not active:
                # no chord active in this segment
                continue

            # choose primary by max weight
            primary = max(active, key=lambda t: t.weight)

            # create segment primary from time -> next_time
            seg = TimelineItem(
                start_beat=time,
                end_beat=next_time,
                chord=primary.chord,
                source_nebula=primary.source_nebula,
                weight=primary.weight,
            )

            # merge with previous if same chord and contiguous
            if (
                resolved
                and resolved[-1].chord == seg.chord
                and abs(resolved[-1].end_beat - seg.start_beat) < 1e-9
                and resolved[-1].source_nebula == seg.source_nebula
            ):
                resolved[-1].end_beat = seg.end_beat
            else:
                resolved.append(seg)

        return resolved

    def get_harmonic_context(self) -> HarmonicContext:
        return HarmonicContext(self.timeline)

    def map_star_events(self, mapper) -> List[MappedStarNote]:
        """Map registered star events using the provided mapper.

        The mapper is expected to implement a `map(star_event, harmonic_context)`
        method returning a MappedStarNote.
        """
        ctx = self.get_harmonic_context()
        mapped: List[MappedStarNote] = []
        for se in self.star_events:
            mapped_note = mapper.map(se, ctx)
            mapped.append(mapped_note)
        return mapped

    def orchestrate(
        self, nebulas: Iterable[Nebula], stars_obj, images=None, quant=None, mapper=None
    ) -> dict:
        """High-level orchestration convenience method.

        - nebulas: iterable of Nebula objects (each with .chords)
        - stars_obj: Stars container with .small_stars and .big_stars
        - images: Images container (for width mapping, optional)
        - quant: optional quantizer instance (used to obtain ticks_per_beat)
        - mapper: optional StarNoteMapper instance; if None a default nearest tone mapper will be used

        Returns a dict with 'timeline' and 'mapped_star_notes'.
        """
        # Register nebulas
        self.register_nebulae(nebulas)

        # Determine note based on the color
        self.nebula_chord_composer()

        # Build timeline
        timeline = self.build_harmonic_timeline()

        # Determine timeline length
        timeline_end = max((t.end_beat for t in timeline), default=16.0)

        # Collect stars
        all_stars = []
        try:
            # stars_obj may be the Stars container or a simple iterable
            all_stars = list(getattr(stars_obj, "small_stars", [])) + list(
                getattr(stars_obj, "big_stars", [])
            )
        except Exception:
            try:
                all_stars = list(stars_obj)
            except Exception:
                all_stars = []

        # ticks per beat from quantizer
        ticks_per_beat = (
            getattr(quant, "ticks_per_beat", 960) if quant is not None else 960
        )

        # Build StarEvent instances from star models
        star_events: List[StarEvent] = []
        for st in all_stars:
            if images is not None and getattr(images, "width", 0) and timeline_end > 0:
                ts = (st.x / float(images.width)) * timeline_end
            else:
                ts = 0.0

            # duration conversion from ticks to beats if duration present
            if getattr(st, "duration", 0):
                dur_beats = float(st.duration) / float(ticks_per_beat)
            else:
                dur_beats = 1.0

            se = StarEvent(
                original_note=getattr(st, "note", 60),
                velocity=getattr(st, "velocity", 100),
                timestamp_beat=ts,
                duration_beat=dur_beats,
                pan=getattr(st, "pan", None),
                source_star=st,
            )
            star_events.append(se)

        # register star events
        self.register_star_events(star_events)

        # mapping
        if mapper is None:
            # lazy import to avoid circular imports
            from music.star_mapper import StarNoteMapper

            mapper = StarNoteMapper()

        mapped = self.map_star_events(mapper)

        return {
            "timeline": timeline,
            "mapped_star_notes": mapped,
        }

    def export_sequences(self) -> dict:
        """Return a dictionary with timeline and star events (mapped not included).

        Consumers (e.g., MidiCreator) can use this structure.
        """
        return {
            "harmonic_timeline": self.timeline,
            "star_events": self.star_events,
        }

    def clear(self) -> None:
        self.nebulae = []
        self.star_events = []
        self.timeline = []

