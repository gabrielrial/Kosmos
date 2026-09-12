"""Tests for the .mid export.

Checked with an independent SMF parser (tests/smf.py) rather than the library
that wrote the file, so a mistake in how we encode bytes cannot hide behind a
matching mistake in how we read them back.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import smf  # noqa: E402
from mapping.star_mapper import NoteEvent  # noqa: E402
from mapping.timeline import TimelineBuilder, chord_spans  # noqa: E402
from midi.messages import Message, _varint  # noqa: E402
from midi.midi_creator import MidiSheet  # noqa: E402
from midi.transport import TimedEvent  # noqa: E402
from models.chord import Chord  # noqa: E402
from models.chords import ChordType  # noqa: E402
from models.nebula import NebulaMidi  # noqa: E402


class VarintTest(unittest.TestCase):
    def test_matches_the_smf_specification(self):
        # The examples given in the Standard MIDI File spec.
        self.assertEqual(_varint(0), b"\x00")
        self.assertEqual(_varint(0x40), b"\x40")
        self.assertEqual(_varint(0x7F), b"\x7f")
        self.assertEqual(_varint(0x80), b"\x81\x00")
        self.assertEqual(_varint(0x2000), b"\xc0\x00")
        self.assertEqual(_varint(0x3FFF), b"\xff\x7f")
        self.assertEqual(_varint(0x100000), b"\xc0\x80\x00")
        self.assertEqual(_varint(0x0FFFFFFF), b"\xff\xff\xff\x7f")

    def test_rejects_a_negative_delta(self):
        with self.assertRaises(ValueError):
            _varint(-1)


def simple_timeline():
    """Two chords and four star notes, at positions chosen to be checkable."""

    nebula = NebulaMidi()
    for root, duration in ((60, 4.0), (65, 4.0)):
        nebula.chords.append(Chord(root=root, chord_type=ChordType.MAJOR))
        nebula.duration.append(duration)
    spans = chord_spans([nebula], channel=0)

    stars = [
        NoteEvent(
            x=index * 10,
            y=index * 250,
            note=72,
            velocity=80 + index,
            pan=index * 40,
            duration=0.5,
            channel=3,
            pan_cc=7,
        )
        for index in range(4)
    ]
    builder = TimelineBuilder(total_beats=8.0, grid=0.25)
    return spans, builder.build(spans, [("small", stars, 60, 84)], image_height=1000)


class MidiFileTest(unittest.TestCase):
    def setUp(self):
        self.spans, self.timeline = simple_timeline()
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "test.mid"

    def tearDown(self):
        self.directory.cleanup()

    def write(self, bpm=90.0, ticks=960):
        MidiSheet(ticks_per_beat=ticks, bpm=bpm).save(self.timeline, self.path)
        return smf.read(self.path)

    def test_file_parses_and_has_a_track_per_channel(self):
        division, tracks = self.write()
        self.assertEqual(division, 960)
        channels = {
            event.channel
            for track in tracks
            for event in track
            if event.type in ("note_on", "note_off")
        }
        # One tempo track plus one per channel used.
        self.assertEqual(len(tracks), len(channels) + 1)

    def test_tempo_matches_the_configured_bpm(self):
        _, tracks = self.write(bpm=90.0)
        tempos = [e for track in tracks for e in track if e.type == "set_tempo"]
        self.assertEqual(len(tempos), 1)
        self.assertAlmostEqual(60_000_000 / tempos[0].tempo, 90.0, places=3)

    def test_beat_positions_survive_the_round_trip(self):
        """The whole point: a note written at beat N is read back at beat N.

        Compared in ticks, not in beats. A beat position is a float and a tick
        is an integer, so comparing the floats asks for exact equality that
        binary floating point cannot give — the real question is whether both
        land on the same tick.
        """

        division, tracks = self.write(ticks=960)
        written = sorted(
            (event.tick, event.channel, event.note)
            for track in tracks
            for event in track
            if event.type == "note_on"
        )
        expected = sorted(
            (
                round(event.beat * division),
                event.message.channel,
                event.message.note,
            )
            for event in self.timeline
            if event.message is not None and event.message.type == "note_on"
        )
        self.assertEqual(written, expected)

    def test_delta_times_do_not_accumulate_rounding_error(self):
        """A long timeline of awkward positions must not drift down the track."""

        events = [
            TimedEvent(
                beat=index / 3.0,                     # never lands on a tick exactly
                order=index,
                message=Message("note_on", note=60, velocity=64, channel=1),
                label="n",
            )
            for index in range(400)
        ]
        events += [
            TimedEvent(
                beat=index / 3.0 + 0.1,
                order=1000 + index,
                message=Message("note_off", note=60, velocity=0, channel=1),
                label="f",
            )
            for index in range(400)
        ]
        MidiSheet(ticks_per_beat=960, bpm=120).save(sorted(events), self.path)
        division, tracks = smf.read(self.path)

        last = max(
            event.tick
            for track in tracks
            for event in track
            if event.type in ("note_on", "note_off")
        )
        expected_tick = round((399 / 3.0 + 0.1) * division)
        self.assertEqual(last, expected_tick, "delta times drifted")

    def test_note_ons_and_note_offs_are_balanced_in_the_file(self):
        _, tracks = self.write()
        open_notes: dict[tuple[int, int], int] = {}
        for track in tracks:
            for event in track:
                key = (event.channel, event.note)
                if event.type == "note_on":
                    open_notes[key] = open_notes.get(key, 0) + 1
                elif event.type == "note_off":
                    open_notes[key] = open_notes.get(key, 0) - 1
        self.assertTrue(
            all(count == 0 for count in open_notes.values()),
            f"unbalanced notes in the file: {open_notes}",
        )

    def test_pan_controllers_are_written(self):
        _, tracks = self.write()
        controls = [
            event
            for track in tracks
            for event in track
            if event.type == "control_change"
        ]
        self.assertTrue(controls)
        for event in controls:
            self.assertEqual(event.control, 7)
            self.assertTrue(0 <= event.value <= 127)

    def test_velocities_are_preserved(self):
        _, tracks = self.write()
        written = sorted(
            event.velocity
            for track in tracks
            for event in track
            if event.type == "note_on" and event.channel == 3
        )
        expected = sorted(
            event.message.velocity
            for event in self.timeline
            if event.message is not None
            and event.message.type == "note_on"
            and event.message.channel == 3
        )
        self.assertEqual(written, expected)

    def test_tracks_are_named(self):
        _, tracks = self.write()
        names = [
            event.name
            for track in tracks
            for event in track
            if event.type == "track_name"
        ]
        self.assertIn("Kosmos", names)
        self.assertIn("Kosmos Nebulae", names)
        self.assertIn("Kosmos Small Stars", names)

    def test_empty_timeline_still_writes_a_valid_file(self):
        MidiSheet(bpm=90).save([], self.path)
        division, tracks = smf.read(self.path)
        self.assertEqual(division, 960)
        self.assertEqual(len(tracks), 1)

    def test_file_and_live_play_the_same_events(self):
        """The file must be the same piece the sequencer would play."""

        division, tracks = self.write()
        from_file = sorted(
            (e.tick, e.channel, e.note, e.velocity)
            for track in tracks
            for e in track
            if e.type == "note_on"
        )
        from_timeline = sorted(
            (
                round(e.beat * division),
                e.message.channel,
                e.message.note,
                e.message.velocity,
            )
            for e in self.timeline
            if e.message is not None and e.message.type == "note_on"
        )
        self.assertEqual(from_file, from_timeline)


if __name__ == "__main__":
    unittest.main(verbosity=2)
