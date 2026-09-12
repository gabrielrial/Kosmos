"""
    Responsible for building the whole midi nebula:
        - Sets the root note of each color from the nebula
        - Builds the chord 
        - Finds t
"""
import random
from pathlib import Path

from models.nebula import NebulaMidi, Nebula
from midi.midi_composer import MidiFactory
from models.chord import Chord
from models.chords import ChordType
from midi.chord_progression import ChordProgression


class NebulasMidiFactory:

    def __init__(
        self,
        nebulas_midi: list[NebulaMidi],
        nebulas: list[Nebula],
        total_duration_beats: float = 64.0,
        transition_duration_beats: float = 4.0,
        low_note: int = 48,
        high_note: int = 72,
        octave_offset: int = 0,
        min_chord_beats: float = 0.0,
        output_dir: str = ".",
    ):
        self.nebulas: list[Nebula] = nebulas
        self.midi_factory = MidiFactory()
        self.nebulas_midi: list[NebulaMidi] = nebulas_midi
        self.chord_progression = ChordProgression()
        self.total_duration_beats = total_duration_beats
        self.transition_duration_beats = transition_duration_beats
        self.low_note = low_note
        self.high_note = high_note
        self.octave_offset = octave_offset
        self.min_chord_beats = min_chord_beats
        self.output_dir = output_dir
        # Voice leading carries across nebulae: the boundary between two of
        # them is a chord change like any other, and resetting here would put
        # an octave leap at every seam.
        self._previous_root: int | None = None
        self._passing: dict[int, list[bool]] = {}

    def process(self):
        report: list[str] = []
        for nebula in self.nebulas:
            midi_nebula, original_chords, original_durations = self._build_nebula(nebula)
            self.nebulas_midi.append(midi_nebula)
            report.append(
                self._format_report(
                    nebula, original_chords, original_durations, midi_nebula
                )
            )
        self._write_report(report)
        return self.nebulas_midi

    def _build_nebula(
        self, nebula: Nebula
    ) -> tuple[NebulaMidi, list[Chord], list[float]]:
        colors = list(nebula.dominant_colors[:5])
        seed = f"{nebula.x}:{nebula.y}:{nebula.area}"
        random.Random(seed).shuffle(colors)
        midi_nebula = NebulaMidi()
        for color in colors:
            note = self.midi_factory.color_to_note(color)
            mode = self.midi_factory.brightness_to_mode(color)
            chord = Chord(root=note, chord_type=mode)
            midi_nebula.notes.append(note)
            midi_nebula.mode.append(mode)
            midi_nebula.chords.append(chord)
        midi_nebula.duration = self._durations(colors)
        original_chords = list(midi_nebula.chords)
        original_durations = list(midi_nebula.duration)
        self._apply_progression(midi_nebula)
        return midi_nebula, original_chords, original_durations

    def _durations(self, colors) -> list[float]:
        total_weight = sum(max(color.weight, 0.0) for color in colors) or 1.0
        return [
            self.total_duration_beats * max(color.weight, 0.0) / total_weight
            for color in colors
        ]

    def _format_report(
        self,
        nebula: Nebula,
        original_chords: list[Chord],
        original_durations: list[float],
        midi_nebula: NebulaMidi,
    ) -> str:
        lines = [
            f"Nebula at ({nebula.x}, {nebula.y})  "
            f"{nebula.area_frac * 100:.2f}% of frame",
            f"  From {len(original_chords)} dominant colours "
            f"(pitch classes, before placement):",
        ]
        for index, (chord, duration) in enumerate(
            zip(original_chords, original_durations), start=1
        ):
            name = self.midi_factory.note_to_name(chord.root)
            quality = getattr(chord.chord_type, "name", "?")
            lines.append(
                f"    {index}. {name:2} {quality:6} "
                f"({duration:.2f} beats from colour weight)"
            )

        lines.append("")
        lines.append("Progression as played:")
        flags = self._passing.get(id(midi_nebula), [])
        start = 0.0
        for index, (chord, duration) in enumerate(
            zip(midi_nebula.chords, midi_nebula.duration), start=1
        ):
            is_passing = flags[index - 1] if index - 1 < len(flags) else False
            kind = "passing" if is_passing else "nebula "
            lines.append(
                f"  {index:2}. [{kind}] beat {start:7.2f} -> {start + duration:7.2f} "
                f"({duration:5.2f})  {self._format_chord(chord)}"
            )
            start += duration
        lines.append(f"  Total: {sum(midi_nebula.duration):.2f} beats")
        return "\n".join(lines)

    def _format_chord(self, chord: Chord) -> str:
        root = getattr(chord, "root", None)
        chord_type = getattr(chord, "chord_type", None)
        root_name = (
            self.midi_factory.note_to_name(root)
            if isinstance(root, int)
            else "unknown"
        )
        type_name = getattr(chord_type, "name", str(chord_type))
        try:
            notes = chord.chord_maker()
        except AttributeError:
            notes = list(getattr(chord, "notes", ()))

        inversion = getattr(chord, "inversion", 0)
        shape = ("root", "1st inv", "2nd inv", "3rd inv")
        position = shape[inversion] if inversion < len(shape) else f"inv {inversion}"

        # Note names alongside the numbers: the numbers are what MIDI carries,
        # the names are what you check against an instrument.
        spelled = " ".join(
            f"{self.midi_factory.note_to_name(note)}{note // 12 - 2}({note})"
            for note in notes
        )
        return f"{root_name:2} {type_name:6} {position:7}  {spelled}"

    def _write_report(self, reports: list[str]) -> None:
        path = Path(self.output_dir) / "nebula_chords.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        header = (
            "KOSMOS - chord report\n"
            "\n"
            "Every chord that sounds, in order, with its MIDI note numbers.\n"
            "Note names use the convention where middle C (MIDI 60) is C3,\n"
            "the same as Ableton Live.\n"
            "\n"
            "  nebula   a chord derived from one of the region's colours\n"
            "  passing  inserted to connect two chords that cannot follow\n"
            "           each other directly\n"
            "\n"
            "The 'as played' list is what reaches the MIDI port: chords are\n"
            "raised into the audible register and a repeat is rotated to the\n"
            "next inversion, so the numbers here differ from the raw chords\n"
            "above them.\n"
        )
        path.write_text(
            header
            + "\n"
            + "\n\n".join(reports)
            + ("\n" if reports else "\nNo nebulas detected.\n"),
            encoding="utf-8",
        )
        print(f"[OK] Chord report saved: {path}")

    def _apply_progression(self, nebula: NebulaMidi) -> None:
        if not nebula.chords:
            return
        output_chords = [nebula.chords[0]]
        output_durations = [nebula.duration[0]]
        # Recorded while building, because afterwards there is no way to tell:
        # _place() rebuilds every chord, so comparing object identity marks
        # all of them as passing chords.
        passing = [False]
        for index in range(1, len(nebula.chords)):
            source = output_chords[-1]
            destination = nebula.chords[index]
            path = self.chord_progression.chord_connection(source, destination)
            path = path if isinstance(path, list) else [destination]
            intermediates = path[1:-1]
            available = output_durations[-1]
            transition_total = min(
                available, self.transition_duration_beats * len(intermediates)
            )
            output_durations[-1] = available - transition_total
            for intermediate in intermediates:
                output_chords.append(intermediate)
                passing.append(True)
                output_durations.append(
                    transition_total / len(intermediates)
                    if intermediates
                    else 0.0
                )
            output_chords.append(destination)
            passing.append(False)
            output_durations.append(nebula.duration[index])
        nebula.chords = self._place(output_chords)
        nebula.duration = self._enforce_minimum(output_durations)
        self._passing[id(nebula)] = passing
        nebula.notes = [chord.root for chord in nebula.chords]
        nebula.mode = [chord.chord_type for chord in nebula.chords]

    def _enforce_minimum(self, durations: list[float]) -> list[float]:
        """Give every chord at least min_chord_beats.

        Two things upstream can leave a chord too short to be heard as
        harmony: weights are proportional to colour share, so a minor colour
        gets a sliver of the phrase, and inserting passing chords borrows time
        from the chord before them, which can take almost all of it.

        The phrase total gives way rather than the minimum — a nebula whose
        chords need more than its budget simply runs longer. Keeping the total
        would mean squeezing some other chord below the floor, which is the
        problem this exists to solve.
        """

        if self.min_chord_beats <= 0:
            return durations
        return [max(duration, self.min_chord_beats) for duration in durations]

    def _place(self, chords: list[Chord]) -> list[Chord]:
        """Lift pitch classes into the audible chord bed.

        A root arrives as a pitch class, 0 to 11, which as a MIDI note sounds
        below the range of hearing. Each one is raised into the configured
        register.

        Which octave is chosen matters as much as that it is raised: each
        chord takes the octave whose root sits closest to the previous chord's
        root. Otherwise the progression leaps by up to an octave between
        neighbours, and the smooth connections that ChordProgression works to
        find are thrown away at the last step.

        Applied after the passing chords are inserted, so they are placed by
        the same rule rather than being left behind in the bottom octave.
        """

        placed: list[Chord] = []

        for chord in chords:
            repeated = (
                placed
                and placed[-1].root % 12 == chord.root % 12
                and placed[-1].chord_type == chord.chord_type
            )

            pitch_class = chord.root % 12
            candidates = [
                note
                for note in range(self.low_note, self.high_note + 1)
                if note % 12 == pitch_class
            ]
            if not candidates:
                # The bed is narrower than an octave; fall back to the bottom.
                candidates = [self.low_note + ((pitch_class - self.low_note) % 12)]

            if self._previous_root is None:
                # Start near the middle, leaving room to move either way.
                target = (self.low_note + self.high_note) // 2
            else:
                target = self._previous_root
            root = min(candidates, key=lambda note: (abs(note - target), note))

            shifted = root + self.octave_offset * 12
            root = max(0, min(shifted, 127))
            # A chord repeating itself is a stall: same notes, same bass,
            # nothing moves. Rotating to the next inversion keeps the harmony
            # and changes the shape and the bass note, so the repeat reads as
            # a move instead.
            # Cycle through the chord's inversions rather than counting up
            # forever: past the last one the shape returns to root position,
            # and an unbounded counter makes that wrap invisible here.
            positions = len(getattr(chord.chord_type, "value", (0, 4, 7)))
            inversion = ((placed[-1].inversion + 1) % positions) if repeated else 0
            candidate = Chord(
                root=root, chord_type=chord.chord_type, inversion=inversion
            )

            # An inversion raises notes by an octave, which can push the top
            # of the chord past the bed. Drop the whole chord an octave when
            # that happens, if there is room below: the inversion is kept, the
            # register is not overshot.
            if inversion and max(candidate.chord_maker()) > self.high_note:
                if root - 12 >= self.low_note:
                    root -= 12
                    candidate = Chord(
                        root=root, chord_type=chord.chord_type, inversion=inversion
                    )
                else:
                    candidate = Chord(root=root, chord_type=chord.chord_type)

            self._previous_root = root
            placed.append(candidate)

        return placed

    def find_note_and_mode_for_nebulas(self):
        """Compatibility helper for callers using the former staged API."""
        for nb in self.nebulas:
            nebula = NebulaMidi()
            for i in nb.dominant_colors:
                nebula.notes.append(self.midi_factory.color_to_note(i))
                nebula.mode.append(self.midi_factory.brightness_to_mode(i))
                print(f"Chords: {self.midi_factory.note_to_name(nebula.notes[-1])}")
                print(f"Mode: {self.midi_factory.brightness_to_mode(i)}")
            self.nebulas_midi.append(nebula)

    def build_chords(self):
        for nb in self.nebulas_midi:
            for note, mode in zip(nb.notes, nb.mode):
                nb.chords.append(Chord(chord_type=mode, root=note))

                print(f"Chord: {nb.chords[-1]}")

    def harmonic_path(self):
        for nebula in self.nebulas_midi:
            self._apply_progression(nebula)