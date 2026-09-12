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
