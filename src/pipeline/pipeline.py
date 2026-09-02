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
from detection.cloud_detector import CloudDetector
from music.orchestrator import MusicOrchestrator, StarEvent
from music.star_mapper import StarNoteMapper
from models.star import Stars
from midi.clock import MidiClockGenerator
from midi.star_player import StarMidiPlayer
from midi.midi_creator import MidiSheet
from midi.realtime_player import NebulaRealtimeMidiPlayer, StarRealtimeMidiPlayer
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
        self.nebulosas: NebulaMidi = NebulaMidi()
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
        nebulas = CloudDetector(self.images, self.stars, self.config).detect()
        quantizer = Quantizer(self.stars, self.midi.tempo, self.images.width)
        neb_midi = NebulasMidiFactory(self.nebulosas, nebulas).process()



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
        self.small_star_player = StarMidiPlayer(
            stars=self.stars.small_stars,
            outport=self.midi.outport["kosmos_stars"],
            channel_base=3,
            speed_beats=self.config.instrument.stars_speed_beats,
            tempo=self.midi.tempo,
            shuffle=True,
        )

        self.big_star_player = StarMidiPlayer(
            stars=self.stars.big_stars,
            outport=self.midi.outport["kosmos_stars"],
            channel_base=5,
            speed_beats=self.config.instrument.stars_speed_beats,
            tempo=self.midi.tempo,
            shuffle=True,
        )

    def _start_playback(self):

        self.small_star_player.start()
        self.big_star_player.start()
