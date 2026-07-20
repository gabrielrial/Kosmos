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
from setup.midi import MidiSetup
from image.img_pipeline import ImagePipeLine
from midi.device import MidiDevice
from midi.tempo import Tempo
from models.images import Images
from detection.star_detector import StarDetector
from models.star import Stars




class ImageToMidi:
    
    def __init__(
        self,  
        config_path: str,
        image_path: str,
        output_dir: Optional[str] = None
        ):
        
        # Load configuration and validate
        self.config = ConfigLoader.load(config_path)
        
        # Paths 
        self.image_path = image_path
        self.output_path = output_dir

        #Components (initialized during process())
        self.tempo: Tempo | None
        self.device: MidiDevice | None
        self.outport = None
        self.ports = {}  # Dictionary with 3 ports: kosmos_stars, kosmos_bass, kosmos_clock
        
        ## Images

        self.images: Images | None
        #
        ## Players
        #self.clock_gen: MidiClockGenerator | None
        #self.star_player: StarMidiPlayer | None
        #self.bass_player: ColorBassPlayer | None
        #
        ## Data
        self.stars: list[Stars] = []
        #self.dominant_colors: List = []
        #
        ## Status
        #self._processed = False
        #self._started = False
        
        print(f"[Pipeline] Initialized")
        print(f"  Config: {config_path}")
        print(f"  Imagen: {image_path}")
        print(f"  Output: {output_dir}")
        print()


    def process(self):


            MidiSetup(self).init()

            # Image Processor
            ## Check and capture exception if it is requiere
            self.images =  ImagePipeLine(self.image_path)._process_image()


            # Start Detector
            StarDetector(self.images, self.stars, self.config)
 
            

'''
            PlayerFactory(self).run()

            self._start_playback()

            self._processed = True
            return self

        except Exception:
            self.cleanup()
            raise

    
    def _start_playback(self):
        """Stars all instruments."""
        print("\n[Starting Playback]")
        
        # Iniciar clock
        self.clock_gen.start()
        print("  → Clock initialized")
        
        # Iniciar players
        if self.star_player:
            self.star_player.start()
            print("  → Star player iniciado")
        
        if self.bass_player:
            self.bass_player.start()
            print("  → Bass player iniciado")
        
        self._started = True
    
    def wait(self):
        """
        Espera a que todos los players terminen de ejecutarse.
        
        Must be called after process().
        """
        if not self._started:
            print("[WARN] Pipeline has not been started yet")
            return
        
        print("\n[Waiting for playback...]")
        
        try:
            if self.star_player:
                self.star_player.join()
            if self.bass_player:
                self.bass_player.join()
            
            print("[OK] Playback completed")
        
        except KeyboardInterrupt:
            print("\n[OK] Playback interrupted by user")
            self.stop()
    
    def stop(self):
        """Detiene todos los players de forma segura."""
        if self.clock_gen:
            self.clock_gen.stop()
        if self.star_player:
            self.star_player.stop()
        if self.bass_player:
            self.bass_player.stop()
        
        print("[OK] All players where stopped")
    
    def cleanup(self):
        """Resource cleaning: closes all MIDI ports, etc."""
        print("\n[Limpieza]")
        
        # Stop if running
        if self._started:
            self.stop()
        
        # Cerrar puertos MIDI
        if self.device:
            self.device.close_all()
            print("  ✓ MIDI ports closed")
        
        print("[OK] Pipeline clear")
    
    def summary(self) -> dict:
        """
        Retorna un resumen del procesamiento realizado.
        
        Returns:
            Dict with pipeline statistics
        """
        return {
            "config_file": self.config,
            "image_path": str(self.image_path),
            "tempo_bpm": self.tempo.bpm if self.tempo else None,
            "small_stars_count": len(self.small_stars),
            "big_stars_count": len(self.big_stars),
            "dominant_colors_count": len(self.dominant_colors),
            "processed": self._processed,
            "started": self._started,
        }
    
    def __enter__(self):
        """Context manager: entrada."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager: automatic cleanup."""
        self.cleanup()
    
    def __repr__(self) -> str:
        status = "running" if self._started else "idle"
        return (
            f"ImageToMidiPipeline("
            f"image={Path(self.image_path).name}, "
            f"bpm={self.config.tempo.bpm}, "
            f"status={status})"
        )
'''