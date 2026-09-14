"""Image to MIDI.

The stages are kept separate on purpose:

    analyse()   file -> measurements          no MIDI, no musical decisions
    compose()   measurements -> note events   pure, testable, no ports
    play()      note events -> MIDI           dumb, just sends bytes

``analyse`` is what the calibration tool in ``tools/survey.py`` calls, which
is why detection can be measured without opening a MIDI port.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from config.config import ConfigLoader
from detection.nebula_detector import NebulaDetector
from detection.star_detector import StarDetector
from image.img_pipeline import ImagePipeLine
from mapping.star_mapper import LayerSpec, NoteEvent, StarMapper
from mapping.timeline import TimelineBuilder, chord_spans
from midi.midi_creator import MidiSheet
from midi.midi_nebulas import NebulasMidiFactory
from midi.messages import Message
from midi.transport import MidiClock, Sequencer, TimedEvent, Transport, panic
from models.images import Images
from models.nebula import Nebula, NebulaMidi
from models.star import Stars


class ImageToMidi:
    def __init__(
        self, config_path: str, image_path: str, output_dir: Optional[str] = None
    ) -> None:
        self.config = ConfigLoader.load(config_path)
        self.image_path = image_path
        self.output_dir = output_dir or "."

        self.images: Images | None = None
        self.stars: Stars = Stars()
        self.nebulas: list[Nebula] = []
        self.nebulas_midi: list[NebulaMidi] = []
        self.spans: list = []
        self.timeline: list[TimedEvent] = []

    # ------------------------------------------------------------------
    def analyse(self) -> tuple[Images, Stars, list[Nebula]]:
        """Everything that reads the image. No MIDI is touched here."""

        self.images = ImagePipeLine(self.image_path, self.config.images).process()
        self.stars = StarDetector(
            self.images, self.config.star_detector, self.output_dir
        ).detect()
        self.nebulas = NebulaDetector(
            self.images, self.config.nebula_detector, self.output_dir
        ).detect()
        return self.images, self.stars, self.nebulas

    def _cycle(self, index: int) -> tuple[list[TimedEvent], float, int, int]:
        """Build one pass over the image.

        ``index`` reaches the colour shuffle, so every pass deals the same
        dominant colours in a different order and produces a different chord
        progression. The stars keep their rhythm but are re-fitted to whatever
        chord now sounds beneath them, so the texture is recognisable while
        the harmony never repeats.
        """

        stars_config = self.config.stars
        transport_config = self.config.transport

        nebulas_midi = NebulasMidiFactory(
            [],
            self.nebulas,
            total_duration_beats=self.config.harmony.nebula_total_duration_beats,
            low_note=self.config.harmony.chord_low_note,
            high_note=self.config.harmony.chord_high_note,
            octave_offset=self.config.harmony.octave_offset,
            min_chord_beats=self.config.harmony.min_chord_beats,
            output_dir=self.output_dir,
            cycle=index,
        ).process(write_report=(index == 0))

        mapper = StarMapper(
            small=LayerSpec(
                low_note=stars_config.small_low_note,
                high_note=stars_config.small_high_note,
                duration_beats=stars_config.small_duration_beats,
                channel=stars_config.small_channel,
                pan_cc=stars_config.pan_cc,
            ),
            big=LayerSpec(
                low_note=stars_config.big_low_note,
                high_note=stars_config.big_high_note,
                duration_beats=stars_config.big_duration_beats,
                channel=stars_config.big_channel,
                pan_cc=stars_config.pan_cc,
            ),
        )
        small, big = mapper.map(self.stars, self.images.width)

        spans = chord_spans(nebulas_midi, channel=stars_config.chord_channel)
        builder = TimelineBuilder(
            total_beats=self.config.harmony.nebula_total_duration_beats,
            grid=1.0 / transport_config.grid_subdivision,
            quantise_strength=transport_config.quantise_strength,
            fit_stars_to_chord=transport_config.fit_stars_to_chord,
            notes_per_slice=transport_config.notes_per_slice,
            duration_scale=transport_config.star_duration_scale,
            min_spacing=transport_config.min_note_spacing_beats,
            spacing_variation=transport_config.spacing_variation_beats,
            chord_roll=self._chord_roll(),
        )
        timeline = builder.build(
            spans,
            [
                ("small", small, stars_config.small_low_note, stars_config.small_high_note),
                ("big", big, stars_config.big_low_note, stars_config.big_high_note),
            ],
            image_height=self.images.height,
        )
        if index == 0:
            self.nebulas_midi = nebulas_midi
            self.spans = spans
        length = spans[-1].end_beat if spans else 0.0
        return timeline, length, len(small) + len(big), len(spans)

    def _chord_roll(self) -> float:
        """How far apart to strike the notes of a chord, from the image.

        Star density is the widest signal the image gives — 26 to 2,690
        sources per megapixel across the sample set. A crowded sky plays
        tighter, an empty one lets the chord spread out, so the same setting
        produces a different touch for a different photograph.

        The scale is logarithmic because density is: the step from 26 to 260
        is as meaningful as the one from 260 to 2,600.
        """

        import math

        transport = self.config.transport
        if transport.chord_roll_beats <= 0:
            return 0.0

        density = max(self.stars.density_per_megapixel, 1.0)
        # 30 to 3,000 covers the measured range; outside it the value clamps.
        position = (math.log10(density) - math.log10(30.0)) / (
            math.log10(3000.0) - math.log10(30.0)
        )
        position = min(max(position, 0.0), 1.0)
        loose, tight = 1.0, transport.chord_roll_dense
        roll = transport.chord_roll_beats * (loose + position * (tight - loose))
        print(
            f"[Compose] chord roll {roll:.3f} beats "
            f"({density:.0f} sources/Mpx)"
        )
        return roll

    def compose(self) -> list[TimedEvent]:
        """Measurements to one ordered timeline. Pure: no ports, no threads."""

        transport_config = self.config.transport
        beats_per_minute = self.config.tempo.bpm
        target_beats = transport_config.target_minutes * beats_per_minute

        timeline: list[TimedEvent] = []
        cursor = float(transport_config.count_in_beats)
        cycles = 0
        mapped = 0
        spans = 0

        while True:
            events, length, notes, span_count = self._cycle(cycles)
            if length <= 0:
                break
            for event in events:
                event.beat += cursor
            timeline.extend(events)
            cursor += length
            cycles += 1
            mapped += notes
            spans += span_count
            if cursor >= target_beats:
                break
            if cycles > 500:                  # a stop, in case length is tiny
                break

        # The last cycle usually overshoots; cut it at the target rather than
        # leaving a partial phrase, and drop any note left hanging by the cut.
        if target_beats > 0 and cursor > target_beats:
            timeline = self._truncate(timeline, target_beats)

        timeline.sort()
        self.timeline = timeline

        length = timeline[-1].beat if timeline else 0.0
        kept = sum(1 for event in timeline if event.label == "star_on")
        print(
            f"[Compose] {cycles} cycle(s), {spans} chord spans, "
            f"{mapped} star notes mapped, {kept} kept"
        )
        print(
            f"[Compose] timeline: {len(timeline)} events over {length:.1f} beats "
            f"({length * 60.0 / beats_per_minute / 60:.1f} min at {beats_per_minute} BPM)"
        )
        checks = TimelineBuilder.check(timeline)
        if checks["hanging_notes"] or checks["unmatched_note_offs"]:
            raise RuntimeError(f"timeline is not balanced: {checks}")
        print("[Compose] every note_on has a matching note_off")
        return timeline

    @staticmethod
    def _truncate(timeline: list[TimedEvent], limit: float) -> list[TimedEvent]:
        """Cut the timeline at ``limit``, keeping every note balanced.

        A note that starts before the cut and ends after it would otherwise
        lose its note_off and sound forever, so those are released exactly at
        the limit; notes starting after the cut are dropped with their offs.
        """

        kept: list[TimedEvent] = []
        open_notes: dict[tuple[int, int], int] = {}
        for event in sorted(timeline):
            message = event.message
            if event.beat >= limit:
                break
            kept.append(event)
            if message is None or message.type not in ("note_on", "note_off"):
                continue
            key = (message.channel, message.note)
            if message.type == "note_on":
                # Count, not set: the same pitch can be struck again on the
                # same channel before the first one is released — two big
                # stars an octave apart resolve to the same note, and their
                # two-beat lengths overlap. Each one still needs its own off.
                open_notes[key] = open_notes.get(key, 0) + 1
            elif open_notes.get(key):
                open_notes[key] -= 1

        order = max((event.order for event in kept), default=0)
        for (channel, note), count in open_notes.items():
            for _ in range(count):
                order += 1
                kept.append(
                    TimedEvent(
                        beat=limit,
                        order=order,
                        message=Message(
                            "note_off", note=note, velocity=0, channel=channel
                        ),
                        label="truncated_off",
                    )
                )
        return kept

    def play(self, timeline: list[TimedEvent]) -> None:
        # Imported here, not at module scope: --mode file writes a .mid
        # without touching a port, and should not require a MIDI backend to
        # be installed at all.
        from setup.midi import MidiSetup

        midi = MidiSetup(self.config).init()
        stars_port = midi.midi_devices.get_port("kosmos_stars")
        nebula_port = midi.midi_devices.get_port("kosmos_nebula")
        clock_port = midi.midi_devices.get_port("kosmos_clock")
        if stars_port is None or nebula_port is None or clock_port is None:
            raise RuntimeError("MIDI ports are not available")

        transport = Transport(self.config.tempo.bpm)
        chord_channel = self.config.stars.chord_channel

        # One port per layer, chosen by the channel the event carries.
        def route(event: TimedEvent):
            message = event.message
            if message is None:
                return stars_port
            channel = getattr(message, "channel", 0)
            return nebula_port if channel == chord_channel else stars_port

        class RoutedPort:
            def send(self, message):
                port = (
                    nebula_port
                    if getattr(message, "channel", 0) == chord_channel
                    else stars_port
                )
                port.send(message)

        sequencer = Sequencer(timeline, RoutedPort(), transport)
        clock = (
            MidiClock(
                clock_port,
                transport,
                send_song_position=self.config.transport.send_song_position,
            )
            if self.config.transport.send_clock
            else None
        )

        print(
            f"[MIDI] starting at {self.config.tempo.bpm} BPM"
            + (" with MIDI clock on kosmos_clock" if clock else " (clock disabled)")
        )
        if clock:
            print(
                "[MIDI] in Ableton Live: Preferences > Link/Tempo/MIDI, set Sync On "
                "for kosmos_clock, then put the transport in EXT"
            )

        transport.start()
        try:
            if clock:
                clock.start()
            sequencer.start()
            sequencer.join()
        except KeyboardInterrupt:
            print("\n[MIDI] stopping")
        finally:
            sequencer.stop()
            if clock:
                clock.stop()
                clock.join(timeout=1.0)
            sequencer.join(timeout=1.0)
            panic(stars_port)
            panic(nebula_port)
            if clock:
                print(f"[MIDI] {clock.pulses_sent} clock pulses sent")
            if sequencer.late_events:
                print(
                    f"[MIDI] {sequencer.late_events} events ran late, "
                    f"worst {sequencer.worst_lateness_ms:.1f} ms"
                )
            else:
                print("[MIDI] no event ran more than 5 ms late")
            midi.midi_devices.close()
            print("[MIDI] ports closed")

    def export(self, timeline: list[TimedEvent], name: str | None = None) -> Path:
        """Write the timeline to a .mid file.

        Same events as the live performance. A file has no timing error at
        all, because the DAW's own engine places the notes instead of a
        Python thread waking up on time.
        """

        stem = name or Path(self.image_path).stem
        return MidiSheet(bpm=self.config.tempo.bpm).save(
            timeline, Path(self.output_dir) / f"{stem}.mid"
        )

    def process(self, mode: str = "both", midi_name: str | None = None) -> None:
        self.analyse()
        timeline = self.compose()

        if mode in ("file", "both"):
            self.export(timeline, midi_name)
        if mode in ("live", "both"):
            self.play(timeline)
