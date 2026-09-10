"""
Main pipeline: Converts images to MIDI music.

Orchestrates the entire workflow:
1. Load configuration
2. Process image
3. Detect stars
4. Analyze colors
5. Generate MIDI
"""

from typing import Tuple, List, Optional

from config.config import ConfigLoader
from quantizer.quantizer import Quantizer
from setup.midi import MidiSetup
from image.img_pipeline import ImagePipeLine
from midi.device import MidiDevice
from models.tempo import Tempo
from models.images import Images
from detection.star_detector import StarDetector
from detection.nebula_detector import NebulaDetector
from music.orchestrator import MusicOrchestrator, StarEvent
from music.star_mapper import StarNoteMapper
from models.star import Stars
from models.nebula import Nebulas
from midi.clock import MidiClockGenerator
from midi.star_player import StarMidiPlayer
from midi.midi_creator import MidiSheet
from midi.realtime_player import (
    NebulaChordRealtimeMidiPlayer,
    NebulaRealtimeMidiPlayer,
    StarRealtimeMidiPlayer,
)
from midi.midi_nebulas import NebulasMidiFactory
from models.nebula import NebulaMidi

class ImageToMidi:

    def __init__(
        self, config_path: str, image_path: str, output_dir: Optional[str] = None
    ):

        # Load configuration and validate
        self.config = ConfigLoader.load(config_path)

        # Paths
        self.image_path = image_path
        self.output_path = output_dir

        # Components (initialized during process())
        self.device: MidiDevice
        self.outport = None
        self.ports = (
            {}
        )  # Dictionary with 3 ports: kosmos_stars, kosmos_bass, kosmos_clock

        ## Images

        self.images: Images | None
        #
        ## Players
        self.midi: MidiSetup
        self.small_star_player: StarMidiPlayer | None
        self.big_star_player: StarMidiPlayer | None
        # self.bass_player: ColorBassPlayer | None
        #
        ## Data
        self.stars: Stars = Stars()
        self.nebulosas: list[NebulaMidi] = []
        # self.dominant_colors: List = []
        #
        ## Status
        # self._processed = False
        # self._started = False

        self.midi_track = MidiSheet()

        print(f"[Pipeline] Initialized")
        print(f"  Config: {config_path}")
        print(f"  Imagen: {image_path}")
        print(f"  Output: {output_dir}")
        print()

    def process(self):

        #
        self.midi = MidiSetup(self.config).init()

        self.images = ImagePipeLine(self.image_path, self.config.images).process()
        StarDetector(self.images, self.stars, self.config.star_detector).detect()
        nebulas = NebulaDetector(
            self.images, self.stars, self.config.star_detector
        ).detect()
        quantizer = Quantizer(self.stars, self.midi.tempo, self.images.width)
        neb_midi = NebulasMidiFactory(
            self.nebulosas,
            nebulas,
            total_duration_beats=self.config.harmony.nebula_total_duration_beats,
        ).process()
        print(
            f"[Harmony] Built {sum(len(nebula.chords) for nebula in neb_midi)} chords "
            f"across {len(neb_midi)} nebulas"
        )
        self._fit_stars_to_harmony(neb_midi)
        self._setup_midi()
        nebulas_player = NebulaChordRealtimeMidiPlayer(
            neb_midi,
            self.midi.midi_devices.get_port("kosmos_nebula"),
            self.config.tempo.bpm,
        )
        self.realtime_players = (
            self.small_star_player,
            self.big_star_player,
            nebulas_player,
        )
        print("[MIDI] Starting stars and nebulas simultaneously")
        for player in self.realtime_players:
            player.start()
        try:
            for player in self.realtime_players:
                player.join()
        except KeyboardInterrupt:
            print("[MIDI] Stopping stars and nebulas")
            for player in self.realtime_players:
                player.stop()
            for player in self.realtime_players:
                player.join()



        #orchestrator = MusicOrchestrator(
        #    tempo_bpm=self.config.tempo.bpm,
        #    nebula_total_duration_beats=self.config.harmony.nebula_total_duration_beats,
        #    subdivision=self.config.tempo.subdivision,
        #    octave_offset=self.config.harmony.octave_offset,
        #)
        #result = orchestrator.orchestrate(
        #    nebulas=nebulas,
        #    stars_obj=self.stars,
        #    images=self.images,
        #    quant=quantizer,
        #)
        """
        timeline = result["timeline"]
        mapped = result["mapped_star_notes"]
        loop_beats = max(
            (item.end_beat for item in timeline),
            default=self.config.harmony.nebula_total_duration_beats,
        )
        print(
            f"[ORCHESTRATOR] Generated timeline items: {len(timeline)}, "
            f"mapped star notes: {len(mapped)}"
        )
        for i, item in enumerate(timeline[:10]):
            root = getattr(item.chord, "note", getattr(item.chord, "root", None))
            print(
                f"  T{i}: {item.start_beat:.2f} -> "
                f"{item.end_beat:.2f} root={root}"
            )

        stars_player = StarRealtimeMidiPlayer(
            mapped,
            self.midi.outport["kosmos_stars"],
            self.config.tempo.bpm,
            loop_beats,
        )
        nebulas_player = NebulaRealtimeMidiPlayer(
            timeline,
            self.midi.outport["kosmos_bass"],
            self.config.tempo.bpm,
            loop_beats,
        )
        self.realtime_players = (stars_player, nebulas_player)
        print("[MIDI] Starting stars and nebulas in separate real-time threads")
        stars_player.start()
        nebulas_player.start()
        try:
            stars_player.join()
            nebulas_player.join()
        except KeyboardInterrupt:
            print("[MIDI] Stopping real-time playback")
            for player in self.realtime_players:
                player.stop()
            for player in self.realtime_players:
                player.join()

        """
        #self.midi.clock.run()



    def _setup_midi(self):
        stars_port = self.midi.midi_devices.get_port("kosmos_stars")
        if stars_port is None:
            raise RuntimeError("MIDI port 'kosmos_stars' is not available")
        print("[MIDI] Stars output: kosmos_stars")

        self.small_star_player = StarMidiPlayer(
            stars=self.stars.small_stars,
            outport=stars_port,
            channel_base=self.config.instrument.stars_small_midi_channel,
            speed_beats=self.config.instrument.stars_speed_beats,
            distance_scale=self.config.instrument.stars_distance_scale,
            min_duration_beats=self.config.instrument.stars_min_duration_beats,
            max_duration_beats=self.config.instrument.stars_max_duration_beats,
            tempo=self.midi.tempo,
            shuffle=True,
        )

        self.big_star_player = StarMidiPlayer(
            stars=self.stars.big_stars,
            outport=stars_port,
            channel_base=self.config.instrument.stars_big_midi_channel,
            speed_beats=self.config.instrument.stars_speed_beats,
            distance_scale=self.config.instrument.stars_distance_scale,
            min_duration_beats=self.config.instrument.stars_min_duration_beats,
            max_duration_beats=self.config.instrument.stars_max_duration_beats,
            tempo=self.midi.tempo,
            shuffle=True,
        )

    def _start_playback(self):

        self.small_star_player.start()
        self.big_star_player.start()

    def _fit_stars_to_harmony(self, nebulas: list[NebulaMidi]) -> None:
        allowed_pitch_classes = {
            note % 12
            for nebula in nebulas
            for chord in nebula.chords
            for note in chord.chord_maker()
        }
        if not allowed_pitch_classes:
            return

        for star in self.stars.small_stars + self.stars.big_stars:
            original_note = star.note
            allowed_notes = [
                note for note in range(128) if note % 12 in allowed_pitch_classes
            ]
            star.note = min(
                allowed_notes,
                key=lambda note: (abs(note - original_note), note),
            )
        print(
            "[Harmony] Star pitch classes: "
            + ", ".join(str(pitch) for pitch in sorted(allowed_pitch_classes))
        )
