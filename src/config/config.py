from dataclasses import dataclass

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any, Dict

from error.errors import ERR_FILE_NOT_FOUND

@dataclass
class ImageConfig:
    """Configuration for images"""
    saturation_boost: float = 1.5
    tolerance: int = 100
    blur: float = 1

@dataclass
class StarDetectorConfig:
    """Configuration for the star detector"""

    white_threshold_v: float = 0.7
    white_threshold_s: float = 0.5
    brightness_threshold: int = 1000
    ring_radius: int = 2
    contrast_threshold: int = 60


@dataclass
class SmallStarsConfig:
    """Configuration specific for small stars"""

    contrast: int = 60


@dataclass
class TempoConfig:
    """Configuration for global tempo"""

    bpm: int = 120
    subdivision: int = 16


@dataclass
class InstrumentConfig:
    """Configuration for MIDI instruments"""

    bass_speed_beats: float = 0.4
    bass_max_note_duration_beats: float = 4.0
    stars_speed_beats: float = 80

@dataclass
class InstrumentNames:
    """Name for MIDI instruments"""

    instrument_small: str = "synth_big"
    instrument_big: str = "synth_big"
    instrument_bass: str = "bass"
    instrument_pad: str = "pad"
    

@dataclass
class Config:
    star_detector: StarDetectorConfig
    small_stars: SmallStarsConfig
    tempo: TempoConfig
    instrument: InstrumentConfig
    images: ImageConfig
    instruments_name: InstrumentNames

    # Paths (optional, for easier testing)
    image_path: Optional[str] = None
    output_dir: Optional[str] = None

    @classmethod
    def from_json(cls, config_path: str) -> "Config":
        """
        Load configuration from a JSON file.

        Args:
            config_path: Path to the JSON configuration file

        Returns:
            Config: Configuration instance

        Raises:
            FileNotFoundError: If the file does not exist
            json.JSONDecodeError: If the JSON is invalid
            ValueError: If required fields are missing
        """
        path = Path(config_path)

        if not path.exists():
            raise FileNotFoundError(ERR_FILE_NOT_FOUND, f" {config_path}")

        try:
            with open(path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Invalid JSON in {config_path}: {e}", e.doc, e.pos
            )

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Creates a Config instance from a dictionary."""

        return cls(
            star_detector=StarDetectorConfig(
                white_threshold_v=data.get("star_detector", {})
                .get("white_threshold", {})
                .get("v", 0.65),
                white_threshold_s=data.get("star_detector", {})
                .get("white_threshold", {})
                .get("s", 0.2),
                brightness_threshold=data.get("star_detector", {}).get(
                    "brightness_threshold", 180
                ),
                ring_radius=data.get("star_detector", {}).get("ring_radius", 2),
                contrast_threshold=data.get("star_detector", {})
                .get("small_stars", {})
                .get("contrast", 60),
            ),
            small_stars=SmallStarsConfig(
                contrast=data.get("star_detector", {})
                .get("small_stars", {})
                .get("contrast", 60),
            ),
            tempo=TempoConfig(
                bpm=data.get("tempo", {}).get("bpm", 120),
                subdivision=data.get("tempo", {}).get("subdivision", 16),
            ),
            instrument=InstrumentConfig(
                bass_speed_beats=data.get("instrument", {}).get(
                    "bass_speed_beats", 0.4
                ),
                bass_max_note_duration_beats=data.get("instrument", {}).get(
                    "bass_max_note_duration_beats", 4.0
                ),
                stars_speed_beats=data.get("instrument", {}).get(
                    "stars_speed_beats", 0.5
                ),
            ),
            images = ImageConfig(
                saturation_boost=data.get("saturation", {}).get("saturation_boost", 2),
                tolerance=data.get("tolerance", {}).get("tolerance", 1.5),
                blur=data.get("blur", {}).get("blur", 0)
            ),
            instruments_name = InstrumentNames(
                instrument_small=data.get("instrument_name", {}).get("small_stars", "Synth Small"),
                instrument_big=data.get("instrument_name", {}).get("big_stars", "Synth Big"),
                instrument_bass=data.get("instrument_name", {}).get("bass", "Bass"),
                instrument_pad=data.get("instrument_name", {}).get("pad", "Pad")
            ),
            
            image_path=data.get("image_path"),
            output_dir=data.get("output_dir"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the configuration to a dictionary (useful for debugging)."""
        return {
            "star_detector": {
                "white_threshold": {
                    "v": self.star_detector.white_threshold_v,
                    "s": self.star_detector.white_threshold_s,
                },
                "brightness_threshold": self.star_detector.brightness_threshold,
                "ring_radius": self.star_detector.ring_radius,
                "small_stars": {
                    "contrast": self.small_stars.contrast,
                },
            },
            "image": {
                "saturation_boost": self.images.saturation_boost,
                "tolerance": self.images.tolerance,
                "blur": self.images.blur,
            },
            "tempo": {
                "bpm": self.tempo.bpm,
                "subdivision": self.tempo.subdivision
            },
            "instrument": {
                "bass_speed_beats": self.instrument.bass_speed_beats,
                "bass_max_note_duration_beats": self.instrument.bass_max_note_duration_beats,
                "stars_speed_beats": self.instrument.stars_speed_beats,
            },
        }

    def validate(self) -> bool:

        errors = []

        # Validate BPM
        if self.tempo.bpm <= 0:
            errors.append(f"BPM must be positive, received: {self.tempo.bpm}")
        if self.tempo.division <= 0:
            errors.append(f"Division must be positive, received: {self.tempo.division}")

        # Validate thresholds (0-1)
        if not (0 <= self.star_detector.white_threshold_v <= 1):
            errors.append(f"white_threshold_v must be between 0 and 1")
        if not (0 <= self.star_detector.white_threshold_s <= 1):
            errors.append(f"white_threshold_s must be between 0 and 1")

        # Validate brightness (0-255)
        if not (0 <= self.star_detector.brightness_threshold <= 255):
            errors.append(f"brightness_threshold must be between 0 and 255")

        # Validate contrast
        if self.small_stars.contrast < 0:
            errors.append(f"contrast cannot be negative")

        # Validate tolerance
        if self.images.blur < 0:
            errors.append(f"value cannot be negative")
        if self.images.saturation_boost < 0:
            errors.append(f"value cannot be negative")
        if not self.images.tolerance > 0:
            errors.append(f"value cannot be negative")

        # Validate beats
        if self.instrument.bass_speed_beats <= 0:
            errors.append(f"bass_speed_beats must be positive")
        if self.instrument.bass_max_note_duration_beats <= 0:
            errors.append(f"bass_max_note_duration_beats must be positive")
        if self.instrument.stars_speed_beats <= 0:
            errors.append(f"stars_speed_beats must be positive")

        if errors:
            raise ValueError(
                "Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
            )

        return True
    
class ConfigLoader:
    

    @staticmethod
    def load(config_path: str) -> Config:
        
        print("Config Loader")
        config = Config.from_json(config_path)
        if not config.validate():
            print("Validaton failed")
        else:
            print("Validaton passed")
        print(config.to_dict())
        return config