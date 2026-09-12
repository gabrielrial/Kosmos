"""Tests for the clock and the shared timeline.

The point of these is drift: two layers that agree at the start and disagree
a minute later is the failure mode that a listening test catches too late.
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from threading import Event

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mapping.star_mapper import NoteEvent  # noqa: E402
from mapping.timeline import (  # noqa: E402
    ChordSpan,
    TimelineBuilder,
    chord_spans,
    fit_to_chord,
    quantise,
)
from midi.transport import PPQN, Sequencer, TimedEvent, Transport  # noqa: E402
from models.chord import Chord  # noqa: E402
from models.chords import ChordType  # noqa: E402
from models.nebula import NebulaMidi  # noqa: E402


class FakePort:
    """Records what was sent and when."""

    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append((time.perf_counter(), message))


class TransportTest(unittest.TestCase):
    def test_beat_positions_are_absolute_not_cumulative(self):
        """The property that stops drift: beat N is always N beats from zero."""

        transport = Transport(bpm=120)
        transport.start(at=1000.0)
        self.assertAlmostEqual(transport.time_of(0), 1000.0)
        self.assertAlmostEqual(transport.time_of(1), 1000.5)
        self.assertAlmostEqual(transport.time_of(64), 1032.0)
        # Asking for a late beat does not depend on any earlier beat.
        self.assertAlmostEqual(
            transport.time_of(128) - transport.time_of(64), 32.0, places=9
        )

    def test_rejects_a_nonsense_tempo(self):
        with self.assertRaises(ValueError):
            Transport(bpm=0)

    def test_wait_until_returns_immediately_for_a_past_target(self):
        transport = Transport(bpm=120)
        transport.start()
        stop = Event()
        began = time.perf_counter()
        transport.wait_until(began - 1.0, stop)
        self.assertLess(time.perf_counter() - began, 0.05)


class SequencerTest(unittest.TestCase):
    def test_events_fire_close_to_their_beat_and_do_not_accumulate_error(self):
        bpm = 600.0                       # fast, to keep the test short
        transport = Transport(bpm=bpm)
        beat_seconds = 60.0 / bpm
        events = [
            TimedEvent(beat=index * 0.5, order=index, message=None, label="tick")
            for index in range(24)
        ]
        port = FakePort()
        sequencer = Sequencer(events, port, transport)

        transport.start()
        sequencer.start()
        sequencer.join(timeout=10)

        self.assertFalse(sequencer.is_alive())
        # Drift is what matters: the last event must still be on time.
        self.assertEqual(sequencer.worst_lateness_ms < 25.0, True)

    def test_events_are_played_in_beat_order_whatever_order_they_arrive(self):
        transport = Transport(bpm=600)
        events = [
            TimedEvent(beat=2.0, order=2, message=None, label="c"),
            TimedEvent(beat=0.0, order=0, message=None, label="a"),
            TimedEvent(beat=1.0, order=1, message=None, label="b"),
        ]
        sequencer = Sequencer(events, FakePort(), transport)
        self.assertEqual([e.label for e in sequencer.events], ["a", "b", "c"])

    def test_stop_flag_does_not_shadow_threads_internals(self):
        """Thread uses self._stop() internally; shadowing it breaks join()."""

        transport = Transport(bpm=600)
        sequencer = Sequencer([], FakePort(), transport)
        self.assertTrue(
            callable(getattr(sequencer, "_stop", None)),
            "Thread._stop must stay a method, or join() raises TypeError",
        )

    def test_stopping_ends_the_run_without_playing_the_rest(self):
        transport = Transport(bpm=60)
        events = [
            TimedEvent(beat=float(index), order=index, message=None, label="x")
            for index in range(100)
        ]
        port = FakePort()
        sequencer = Sequencer(events, port, transport)
        transport.start()
        sequencer.start()
        time.sleep(0.05)
        sequencer.stop()
        sequencer.join(timeout=2)
        self.assertFalse(sequencer.is_alive())


class QuantiseTest(unittest.TestCase):
    def test_full_strength_snaps_to_the_grid(self):
        self.assertAlmostEqual(quantise(0.30, 0.25, 1.0), 0.25)
        self.assertAlmostEqual(quantise(0.40, 0.25, 1.0), 0.50)
        self.assertAlmostEqual(quantise(1.99, 0.25, 1.0), 2.00)

    def test_zero_strength_leaves_the_position_alone(self):
        self.assertAlmostEqual(quantise(0.31, 0.25, 0.0), 0.31)

    def test_partial_strength_moves_part_of_the_way(self):
        moved = quantise(0.30, 0.25, 0.5)
        self.assertGreater(moved, 0.25)
        self.assertLess(moved, 0.30)


class FitToChordTest(unittest.TestCase):
    def test_picks_the_nearest_chord_tone_in_range(self):
        self.assertEqual(fit_to_chord(61, {0, 4, 7}, 48, 84), 60)
        self.assertEqual(fit_to_chord(66, {0, 4, 7}, 48, 84), 67)

    def test_stays_inside_the_layer_range(self):
        for note in range(0, 128, 7):
            fitted = fit_to_chord(note, {2, 5, 9}, 60, 72)
            self.assertTrue(60 <= fitted <= 72)

    def test_empty_chord_leaves_the_note_alone(self):
        self.assertEqual(fit_to_chord(61, set(), 48, 84), 61)


class TimelineTest(unittest.TestCase):
    def make_nebula(self, roots, durations):
        nebula = NebulaMidi()
        for root, duration in zip(roots, durations):
            nebula.chords.append(Chord(root=root, chord_type=ChordType.MAJOR))
            nebula.duration.append(duration)
        return nebula

    def test_chord_spans_are_laid_end_to_end_without_gaps(self):
        spans = chord_spans([self.make_nebula([60, 62, 64], [4.0, 8.0, 4.0])])
        self.assertEqual(len(spans), 3)
        self.assertEqual(spans[0].start_beat, 0.0)
        for earlier, later in zip(spans, spans[1:]):
            self.assertAlmostEqual(earlier.end_beat, later.start_beat)
        self.assertAlmostEqual(spans[-1].end_beat, 16.0)

    def build(self, **kwargs):
        spans = chord_spans([self.make_nebula([60, 65], [8.0, 8.0])])
        stars = [
            NoteEvent(
                x=index * 10,
                y=index * 100,
                note=70,
                velocity=90,
                pan=64,
                duration=0.5,
                channel=3,
                pan_cc=7,
            )
            for index in range(10)
        ]
        builder = TimelineBuilder(total_beats=16.0, **kwargs)
        timeline = builder.build(spans, [("small", stars, 60, 84)], image_height=1000)
        return spans, timeline

    def test_every_note_on_has_a_matching_note_off(self):
        _, timeline = self.build()
        self.assertEqual(
            TimelineBuilder.check(timeline),
            {"hanging_notes": 0, "unmatched_note_offs": 0},
        )

    def test_star_notes_belong_to_the_chord_sounding_under_them(self):
        spans, timeline = self.build(fit_stars_to_chord=True)

        def active(beat):
            for span in spans:
                if span.start_beat <= beat < span.end_beat:
                    return span
            return spans[-1]

        checked = 0
        for event in timeline:
            if event.label != "star_on":
                continue
            checked += 1
            self.assertIn(event.message.note % 12, active(event.beat).pitch_classes)
        self.assertGreater(checked, 0)

    def test_a_star_never_holds_through_a_chord_change(self):
        spans, timeline = self.build()
        boundaries = [span.end_beat for span in spans[:-1]]
        starts = {}
        for event in timeline:
            if event.label == "star_on":
                starts[(event.message.channel, event.message.note)] = event.beat
            elif event.label == "star_off":
                key = (event.message.channel, event.message.note)
                if key in starts:
                    for boundary in boundaries:
                        self.assertFalse(
                            starts[key] < boundary < event.beat,
                            "a star note crossed a chord change",
                        )
                    del starts[key]

    def test_timeline_is_sorted_by_beat(self):
        _, timeline = self.build()
        beats = [event.beat for event in timeline]
        self.assertEqual(beats, sorted(beats))

    def test_check_notices_a_hanging_note(self):
        from midi.messages import Message

        broken = [
            TimedEvent(beat=0.0, order=0, message=Message("note_on", note=60), label="x")
        ]
        self.assertEqual(TimelineBuilder.check(broken)["hanging_notes"], 1)


class DensityTest(unittest.TestCase):
    """The thinning that decides whether the piece breathes or churns."""

    def make(self, count, **kwargs):
        spans = chord_spans([self._nebula()])
        stars = [
            NoteEvent(
                x=0,
                y=index,
                note=70,
                velocity=1 + (index % 100),
                pan=64,
                duration=0.5,
                channel=3,
                pan_cc=7,
            )
            for index in range(count)
        ]
        builder = TimelineBuilder(total_beats=16.0, grid=0.25, **kwargs)
        timeline = builder.build(
            spans, [("small", stars, 60, 84)], image_height=count
        )
        return builder, timeline

    @staticmethod
    def _nebula():
        nebula = NebulaMidi()
        nebula.chords.append(Chord(root=60, chord_type=ChordType.MAJOR))
        nebula.duration.append(16.0)
        return nebula

    def test_no_budget_keeps_every_note(self):
        _, timeline = self.make(200, notes_per_slice=0)
        self.assertEqual(sum(1 for e in timeline if e.label == "star_on"), 200)

    def test_budget_caps_notes_per_slice(self):
        builder, timeline = self.make(400, notes_per_slice=1)
        starts = [e.beat for e in timeline if e.label == "star_on"]
        counts = {}
        for beat in starts:
            counts[round(beat / 0.25)] = counts.get(round(beat / 0.25), 0) + 1
        self.assertTrue(all(count <= 1 for count in counts.values()))
        self.assertGreater(builder.dropped, 0)
        self.assertEqual(len(starts) + builder.dropped, 400)

    def test_thinning_keeps_the_loudest_note_of_each_slice(self):
        """Dropping the quiet ones is what makes thinning musical."""

        spans = chord_spans([self._nebula()])
        stars = [
            NoteEvent(
                x=0, y=0, note=70, velocity=velocity, pan=64,
                duration=0.5, channel=3, pan_cc=7,
            )
            for velocity in (30, 120, 60)
        ]
        builder = TimelineBuilder(total_beats=16.0, grid=0.25, notes_per_slice=1)
        timeline = builder.build(spans, [("small", stars, 60, 84)], image_height=1)
        kept = [e for e in timeline if e.label == "star_on"]
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].message.velocity, 120)

    def test_a_sparse_image_is_not_thinned_at_all(self):
        """Quiet parts of an image must stay quiet, not be padded or cut."""

        builder, timeline = self.make(8, notes_per_slice=2)
        self.assertEqual(builder.dropped, 0)
        self.assertEqual(sum(1 for e in timeline if e.label == "star_on"), 8)

    def test_duration_scale_lengthens_notes(self):
        _, short = self.make(20, notes_per_slice=0, duration_scale=1.0)
        _, long = self.make(20, notes_per_slice=0, duration_scale=3.0)

        def span_of(timeline):
            starts = {}
            lengths = []
            for event in timeline:
                if event.label == "star_on":
                    starts[event.message.note] = event.beat
                elif event.label == "star_off" and event.message.note in starts:
                    lengths.append(event.beat - starts.pop(event.message.note))
            return max(lengths)

        self.assertGreater(span_of(long), span_of(short))


class ClockTest(unittest.TestCase):
    def test_pulse_rate_is_the_midi_standard(self):
        self.assertEqual(PPQN, 24)

    def test_clock_sends_start_then_pulses_then_stop(self):
        from midi.transport import MidiClock

        transport = Transport(bpm=600)
        port = FakePort()
        clock = MidiClock(port, transport, send_song_position=True)
        transport.start()
        clock.start()
        time.sleep(0.25)
        clock.stop()
        clock.join(timeout=2)

        types = [message.type for _, message in port.messages]
        self.assertEqual(types[0], "songpos")
        self.assertEqual(types[1], "start")
        self.assertEqual(types[-1], "stop")
        self.assertGreater(types.count("clock"), 10)

    def test_clock_stays_on_tempo(self):
        """24 pulses per quarter note, measured against the wall clock."""

        from midi.transport import MidiClock

        bpm = 300.0
        transport = Transport(bpm=bpm)
        port = FakePort()
        clock = MidiClock(port, transport, send_song_position=False)
        transport.start()
        clock.start()
        time.sleep(1.0)
        clock.stop()
        clock.join(timeout=2)

        pulses = [t for t, m in port.messages if m.type == "clock"]
        self.assertGreater(len(pulses), 40)
        expected = 60.0 / bpm / PPQN
        elapsed = pulses[-1] - pulses[0]
        measured = elapsed / (len(pulses) - 1)
        # Within 5% of the target interval over the whole run.
        self.assertLess(abs(measured - expected) / expected, 0.05)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class ChordRegisterTest(unittest.TestCase):
    """Chords must land where they can be heard.

    A root arrives as a pitch class, 0-11. Used directly as a MIDI note that
    is 8 to 23 Hz — below the range of hearing, so the whole harmonic layer
    was inaudible while every star was being carefully fitted to it.
    """

    def factory(self, roots, low=48, high=72, octave_offset=0):
        from midi.midi_nebulas import NebulasMidiFactory
        from models.nebula import Nebula

        factory = NebulasMidiFactory(
            [], [], low_note=low, high_note=high, octave_offset=octave_offset
        )
        chords = [Chord(root=root, chord_type=ChordType.MAJOR) for root in roots]
        return factory, factory._place(chords)

    def test_pitch_classes_are_lifted_into_the_bed(self):
        _, placed = self.factory([0, 5, 11, 3])
        for chord in placed:
            self.assertTrue(
                48 <= chord.root <= 72,
                f"root {chord.root} is outside the configured bed",
            )

    def test_pitch_class_is_preserved(self):
        """Raising the octave must not change which note it is."""

        roots = [0, 1, 5, 7, 11]
        _, placed = self.factory(roots)
        self.assertEqual([chord.root % 12 for chord in placed], roots)

    def test_chords_are_audible(self):
        """Every tone of every chord above the bottom of hearing."""

        _, placed = self.factory([0, 4, 9])
        for chord in placed:
            for note in chord.chord_maker():
                self.assertGreater(note, 40, "chord tone is still subsonic")

    def test_voice_leading_takes_the_nearest_octave(self):
        """C then B should fall a semitone, not leap up eleven."""

        _, placed = self.factory([0, 11])
        self.assertEqual(abs(placed[1].root - placed[0].root), 1)

    def test_voice_leading_continues_across_calls(self):
        """A nebula boundary is a chord change, not a reason to jump."""

        factory, first = self.factory([0])
        second = factory._place([Chord(root=11, chord_type=ChordType.MAJOR)])
        self.assertEqual(abs(second[0].root - first[0].root), 1)

    def test_a_change_of_chord_never_leaps_more_than_a_tritone(self):
        """Voice leading is judged on changes of chord.

        A repeat is excluded because rotating through inversions moves the
        bass on purpose, and the last rotation drops back to root position.
        That movement is the feature; what must stay close is the step from
        one chord to a different one.
        """

        import random

        roots = [random.Random(4).randrange(12) for _ in range(40)]
        _, placed = self.factory(roots)
        changes = [
            (earlier, later)
            for earlier, later in zip(placed, placed[1:])
            if earlier.root % 12 != later.root % 12
        ]
        for earlier, later in changes:
            self.assertLessEqual(
                abs(min(later.chord_maker()) - min(earlier.chord_maker())),
                6,
                "voice leading should always find a closer octave",
            )

    def test_octave_offset_shifts_the_whole_bed(self):
        _, normal = self.factory([0, 5])
        _, raised = self.factory([0, 5], octave_offset=1)
        for plain, shifted in zip(normal, raised):
            self.assertEqual(shifted.root - plain.root, 12)

    def test_notes_stay_in_midi_range(self):
        _, placed = self.factory([0, 6, 11], low=110, high=127, octave_offset=2)
        for chord in placed:
            self.assertTrue(0 <= chord.root <= 127)


class ChordInversionTest(unittest.TestCase):
    """A chord repeating itself unchanged is a stall, not a progression."""

    def place(self, roots, types=None, low=48, high=72):
        from midi.midi_nebulas import NebulasMidiFactory

        types = types or [ChordType.MAJOR] * len(roots)
        factory = NebulasMidiFactory([], [], low_note=low, high_note=high)
        chords = [
            Chord(root=root, chord_type=kind) for root, kind in zip(roots, types)
        ]
        return factory._place(chords)

    def test_chord_tones_follow_the_inversion(self):
        base = Chord(root=60, chord_type=ChordType.MAJOR).chord_maker()
        first = Chord(root=60, chord_type=ChordType.MAJOR, inversion=1).chord_maker()
        second = Chord(root=60, chord_type=ChordType.MAJOR, inversion=2).chord_maker()
        self.assertEqual(base, [60, 64, 67])
        self.assertEqual(first, [64, 67, 72])
        self.assertEqual(second, [67, 72, 76])

    def test_inversion_keeps_the_same_pitch_classes(self):
        """Same harmony, different shape — that is the whole point."""

        plain = Chord(root=60, chord_type=ChordType.MINOR).chord_maker()
        turned = Chord(root=60, chord_type=ChordType.MINOR, inversion=2).chord_maker()
        self.assertEqual({n % 12 for n in plain}, {n % 12 for n in turned})

    def test_inversion_wraps_round(self):
        triad = Chord(root=60, chord_type=ChordType.MAJOR, inversion=3).chord_maker()
        self.assertEqual(triad, Chord(root=60, chord_type=ChordType.MAJOR).chord_maker())

    def test_a_repeated_chord_gets_a_new_inversion(self):
        placed = self.place([0, 0, 0])
        self.assertEqual([chord.inversion for chord in placed], [0, 1, 2])
        shapes = [tuple(chord.chord_maker()) for chord in placed]
        self.assertEqual(len(set(shapes)), 3, "three repeats, three shapes")

    def test_a_different_chord_resets_to_root_position(self):
        placed = self.place([0, 0, 5])
        self.assertEqual(placed[-1].inversion, 0)

    def test_same_root_but_different_quality_is_not_a_repeat(self):
        placed = self.place([0, 0], [ChordType.MAJOR, ChordType.MINOR])
        self.assertEqual(placed[1].inversion, 0)

    def test_inversions_never_push_past_the_ceiling(self):
        """Raising a note an octave must not escape the configured bed."""

        placed = self.place([0] * 6, low=48, high=72)
        for chord in placed:
            for note in chord.chord_maker():
                self.assertLessEqual(note, 72)
                self.assertGreaterEqual(note, 48)

    def test_no_two_consecutive_chords_sound_identical(self):
        placed = self.place([0, 0, 0, 0, 7, 7, 7])
        shapes = [tuple(chord.chord_maker()) for chord in placed]
        for earlier, later in zip(shapes, shapes[1:]):
            self.assertNotEqual(earlier, later)


class MinimumChordDurationTest(unittest.TestCase):
    """No chord should pass by too quickly to be heard as harmony."""

    def factory(self, minimum=4.0):
        from midi.midi_nebulas import NebulasMidiFactory

        return NebulasMidiFactory([], [], min_chord_beats=minimum)

    def test_short_durations_are_raised_to_the_floor(self):
        raised = self.factory(4.0)._enforce_minimum([0.5, 12.0, 1.9, 8.0])
        self.assertEqual(raised, [4.0, 12.0, 4.0, 8.0])

    def test_durations_already_long_enough_are_untouched(self):
        original = [8.0, 16.0, 4.0]
        self.assertEqual(self.factory(4.0)._enforce_minimum(original), original)

    def test_the_phrase_total_gives_way_to_the_minimum(self):
        """Overrunning the budget is the accepted cost of an audible chord."""

        raised = self.factory(4.0)._enforce_minimum([1.0] * 8)
        self.assertEqual(sum(raised), 32.0)
        self.assertGreater(sum(raised), 8.0)

    def test_a_zero_minimum_disables_the_floor(self):
        original = [0.1, 0.2]
        self.assertEqual(self.factory(0.0)._enforce_minimum(original), original)

    def test_every_chord_of_a_real_progression_clears_the_floor(self):
        from mapping.timeline import chord_spans
        from models.nebula import NebulaMidi

        nebula = NebulaMidi()
        for root, duration in ((60, 0.5), (65, 20.0), (67, 1.2), (60, 3.0)):
            nebula.chords.append(Chord(root=root, chord_type=ChordType.MAJOR))
            nebula.duration.append(duration)
        nebula.duration = self.factory(4.0)._enforce_minimum(nebula.duration)

        for span in chord_spans([nebula]):
            self.assertGreaterEqual(span.end_beat - span.start_beat, 4.0)


class ChordReportTest(unittest.TestCase):
    """The report has to describe what actually plays."""

    def build(self, directory):
        from midi.midi_nebulas import NebulasMidiFactory
        from models.color import Color
        from models.nebula import Nebula

        nebula = Nebula(
            x=100, y=200, width=50, height=50, area=2500, area_frac=0.05,
            density=0.8, elongation=1.0, brightness=0.6, hue=0.1,
            saturation=0.5, contrast=20.0,
            dominant_colors=[
                Color(hue=h, saturation=0.5, brightness=b, weight=w)
                for h, b, w in ((0.0, 0.7, 0.4), (0.25, 0.3, 0.3), (0.0, 0.7, 0.3))
            ],
        )
        factory = NebulasMidiFactory(
            [], [nebula], total_duration_beats=64.0, low_note=48, high_note=72,
            min_chord_beats=4.0, output_dir=str(directory),
        )
        factory.process()
        return (directory / "nebula_chords.txt").read_text()

    def test_report_is_written_to_the_output_directory(self):
        import tempfile

        with tempfile.TemporaryDirectory() as name:
            directory = Path(name) / "nested"
            text = self.build(directory)
            self.assertTrue((directory / "nebula_chords.txt").is_file())
            self.assertIn("KOSMOS", text)

    def test_every_played_chord_lists_its_midi_numbers(self):
        import re
        import tempfile

        with tempfile.TemporaryDirectory() as name:
            text = self.build(Path(name))

        played = [line for line in text.splitlines() if "beat " in line]
        self.assertTrue(played, "the report should list the chords as played")
        for line in played:
            numbers = [int(n) for n in re.findall(r"\((\d+)\)", line)]
            self.assertGreaterEqual(len(numbers), 3, f"no note numbers in: {line}")
            for note in numbers:
                self.assertTrue(
                    48 <= note <= 72,
                    f"{note} is outside the configured bed, in: {line}",
                )

    def test_report_names_the_inversion(self):
        import tempfile

        with tempfile.TemporaryDirectory() as name:
            text = self.build(Path(name))
        self.assertIn("root", text)

    def test_report_distinguishes_nebula_chords_from_passing_ones(self):
        """Marking used to compare object identity, so everything read as
        passing once the chords were rebuilt during placement."""

        import tempfile

        with tempfile.TemporaryDirectory() as name:
            text = self.build(Path(name))
        self.assertIn("[nebula ]", text)


class NoteSpacingTest(unittest.TestCase):
    """Quantising alone makes every gap identical; spacing breaks that up."""

    def build(self, count=40, min_spacing=2.0, variation=1.5, ranks=None,
              phrase=64.0):
        """Notes are laid across ``phrase`` beats, so a high ``count`` packs
        them closer than the minimum and spacing actually has work to do."""

        nebula = NebulaMidi()
        nebula.chords.append(Chord(root=60, chord_type=ChordType.MAJOR))
        nebula.duration.append(phrase)
        spans = chord_spans([nebula])

        stars = [
            NoteEvent(
                x=0, y=index, note=70, velocity=90, pan=64, duration=0.5,
                channel=3, pan_cc=7,
                brightness_rank=(ranks[index] if ranks else index / max(count - 1, 1)),
            )
            for index in range(count)
        ]
        builder = TimelineBuilder(
            total_beats=phrase, grid=0.25, notes_per_slice=0,
            min_spacing=min_spacing, spacing_variation=variation,
        )
        timeline = builder.build(spans, [("small", stars, 60, 84)], image_height=count)
        starts = sorted(e.beat for e in timeline if e.label == "star_on")
        return builder, starts

    def test_consecutive_notes_respect_the_minimum(self):
        _, starts = self.build(min_spacing=2.0, variation=0.0)
        for earlier, later in zip(starts, starts[1:]):
            self.assertGreaterEqual(round(later - earlier, 6), 2.0)

    def test_brightness_widens_the_gap(self):
        """The variation has to come from the image, not from chance."""

        _, dim = self.build(count=60, ranks=[0.0] * 60)
        _, bright = self.build(count=60, ranks=[1.0] * 60)
        dim_gaps = [b - a for a, b in zip(dim, dim[1:])]
        bright_gaps = [b - a for a, b in zip(bright, bright[1:])]
        self.assertGreater(min(bright_gaps), max(dim_gaps))

    def test_gaps_are_not_all_the_same(self):
        _, starts = self.build(count=40)
        gaps = {round(b - a, 4) for a, b in zip(starts, starts[1:])}
        self.assertGreater(len(gaps), 2, "spacing should produce varied gaps")

    def test_the_same_input_always_gives_the_same_rhythm(self):
        """Derived from flux, so it is reproducible — unlike random jitter."""

        _, first = self.build(count=30)
        _, second = self.build(count=30)
        self.assertEqual(first, second)

    def test_notes_keep_their_order(self):
        _, starts = self.build(count=30)
        self.assertEqual(starts, sorted(starts))

    def test_notes_pushed_past_the_phrase_are_dropped_not_stretched(self):
        """Spacing must not let a dense layer run past the harmony."""

        builder, starts = self.build(count=400, min_spacing=2.0, variation=1.5)
        self.assertTrue(starts)
        self.assertLess(max(starts), 64.0)
        self.assertGreater(builder.dropped, 0)

    def test_zero_spacing_leaves_the_timing_alone(self):
        _, packed = self.build(count=200, min_spacing=0.0, variation=0.0)
        _, spread = self.build(count=200, min_spacing=2.0, variation=0.0)
        self.assertGreater(
            len(packed), len(spread), "without spacing every note is kept"
        )

    def test_note_length_is_not_shortened_by_spacing(self):
        """A note pushed past the last chord must keep its full length."""

        nebula = NebulaMidi()
        nebula.chords.append(Chord(root=60, chord_type=ChordType.MAJOR))
        nebula.duration.append(40.0)
        spans = chord_spans([nebula])
        stars = [
            NoteEvent(
                x=0, y=index, note=70, velocity=90, pan=64, duration=0.5,
                channel=3, pan_cc=7, brightness_rank=0.5,
            )
            for index in range(6)
        ]
        builder = TimelineBuilder(
            total_beats=40.0, grid=0.25, notes_per_slice=0,
            min_spacing=2.0, spacing_variation=1.0,
        )
        timeline = builder.build(spans, [("small", stars, 60, 84)], image_height=6)

        starts = {}
        lengths = []
        for event in timeline:
            if event.label == "star_on":
                starts[event.message.note] = event.beat
            elif event.label == "star_off" and event.message.note in starts:
                lengths.append(event.beat - starts.pop(event.message.note))
        self.assertTrue(lengths)
        for length in lengths:
            self.assertAlmostEqual(length, 0.5, places=6)
