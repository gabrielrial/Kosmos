"""Typed configuration loaded from a JSON file.

Every value the detectors use is declared here as a dataclass field. Keys that
appear in the JSON but match no field are reported rather than ignored, so a
typo in ``conf.json`` is visible instead of silently falling back to a default.

Lengths are expressed as fractions of the image's longest side, not pixels.
That way ``images.working_size`` can change without recalibrating every radius.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Optional, TypeVar

from error.errors import ERR_FILE_NOT_FOUND

T = TypeVar("T")


@dataclass
class ImageConfig:
    """Image preparation.

    working_size        the longest side is resized to this before analysis,
                        so the result no longer depends on which resolution of
                        a file you happen to have. 0 disables resizing.
    saturation_boost    saturation multiplier used for colour sampling
    """

    working_size: int = 1600
    saturation_boost: float = 1.5


@dataclass
class StarDetectorConfig:
    """Point-source extraction.

    background_radius_frac    blur scale used to estimate the local sky. Must
                              be larger than a star and smaller than the
                              structures you want to keep out of the stars
    detection_sigma           threshold in units of MAD noise above the sky
    minimum_contrast          absolute floor for that threshold
    minimum_brightness        absolute luminance floor, 0-255
    minimum_area_px           regions smaller than this are noise
    max_area_frac             regions larger than this fraction of the frame
                              are not point sources
    roundness_min             minimum area / bounding-box ratio, which
                              rejects sparse ragged shapes
    max_elongation            maximum bounding-box aspect ratio, which rejects
                              solid but stretched shapes. Both are needed: a
                              bar passes the fill test, a wisp passes the
                              aspect test, and neither is a star
    roundness_area_px         only test roundness above this area, since a
                              three-pixel source is trivially round
    big_star_flux_percentile  the split between the two layers, as a
                              percentile of this image's own flux
                              distribution. 98 means the brightest 2% play the
                              low layer
    aperture_radius_px        radius of the colour-sampling aperture
    """

    background_radius_frac: float = 0.0035
    detection_sigma: float = 8.0
    minimum_contrast: float = 4.0
    minimum_brightness: float = 10.0
    minimum_area_px: int = 2
    max_area_frac: float = 0.0005
    roundness_min: float = 0.55
    max_elongation: float = 2.0
    roundness_area_px: int = 12
    big_star_flux_percentile: float = 98.0
    aperture_radius_px: int = 1


@dataclass
class NebulaDetectorConfig:
    """Diffuse-region extraction from the mid-frequency band.

    Detection uses hysteresis: two thresholds instead of one. The high
    threshold decides where there is definitely nebulosity (the seeds); the
    low threshold decides how far each one reaches, and a pixel is kept only
    if it clears the low threshold *and* connects back to a seed. A nebula has
    no edge, it fades out, so a single threshold cuts the halo off and leaves
    disconnected bright cores instead of one cloud.

    star_suppression_frac  radius of a median filter applied before the band,
                           as a fraction of the longest side. A median ignores
                           outliers, so a star smaller than the window is
                           replaced by its surroundings while a nebula edge
                           survives. 0 disables it. Needed because blurring
                           does not remove a bright star, it only spreads it:
                           measured on a real image, the halo of the brightest
                           stars stayed above the seed threshold out to a
                           radius of 12 px
    small_radius_frac      upper edge of the band; large enough to erase stars
    large_radius_frac      lower edge; must be clearly larger than the biggest
                           structure you want to keep, or a nebula filling the
                           frame subtracts itself and only its filaments
                           survive
    seed_sigma             high threshold, in units of MAD noise. Where a
                           region is allowed to start
    grow_mode              "sigma" grows to ``grow_sigma`` above the noise;
                           "percentile" grows to ``grow_percentile`` of this
                           image's own band signal, which adapts between very
                           different photographs
    grow_sigma             low threshold for grow_mode "sigma"
    grow_percentile        low threshold for grow_mode "percentile", as a
                           percentile of the band. 70 keeps the brightest 30%
    max_cover_frac         safety stop: if growing would mask more than this
                           share of the frame, the low threshold is raised
                           until it fits. Stops a strong sky gradient from
                           swallowing the picture
    max_star_flux_share    a region is discarded when this share or more of
                           its signal comes from point sources. Suppression
                           removes a star's core but not always its outer
                           halo, so this is the second line of defence: it
                           asks where the light actually came from rather than
                           what the region looks like. 1.0 disables it
    min_area_frac          smallest region worth a musical phrase
    max_area_frac          0 disables the upper limit
    saturation_threshold   0 accepts colourless structure
    dominant_colors        how many representative colours per region
    """

    star_suppression_frac: float = 0.010
    small_radius_frac: float = 0.004
    large_radius_frac: float = 0.25
    seed_sigma: float = 3.0
    grow_mode: str = "sigma"
    grow_sigma: float = 0.5
    grow_percentile: float = 70.0
    max_cover_frac: float = 0.45
    max_star_flux_share: float = 0.25
    min_area_frac: float = 0.002
    max_area_frac: float = 0.0
    saturation_threshold: float = 0.0
    dominant_colors: int = 5


@dataclass
class StarsConfig:
    """How the two star layers are voiced and sent.

    Note ranges are MIDI numbers: 60 is middle C. The two layers overlap by
    design at the top of the big range so they sound like one instrument
    family rather than two disconnected registers.

    pan_cc is the controller used for stereo position. 10 is the MIDI standard
    and works with no setup; 7 is nominally volume but works if it is mapped
    by hand in the DAW.
    """

    pan_cc: int = 7
    shuffle: bool = True
    small_low_note: int = 67
    small_high_note: int = 91
    small_duration_beats: float = 0.5
    small_channel: int = 3
    big_low_note: int = 48
    big_high_note: int = 67
    big_duration_beats: float = 2.0
    big_channel: int = 5
    chord_channel: int = 0


@dataclass
class TransportConfig:
    """Clock and grid.

    send_clock          emit MIDI beat clock so a DAW can follow Kosmos. In
                        Ableton Live: Preferences > Link/Tempo/MIDI, set Sync
                        On for the Kosmos clock port, then put the transport
                        in EXT
    send_song_position  send a song-position pointer of 0 before start, so the
                        DAW begins from the top rather than wherever it was
    grid_subdivision    the rhythmic grid, in divisions of a beat. 4 is
                        sixteenth notes
    quantise_strength   how far star notes are pulled onto that grid. 1.0
                        snaps exactly, 0.0 leaves them where the image put
                        them, and values between keep some of the original
                        irregularity while still letting a pulse be felt
    fit_stars_to_chord  move each star note to the nearest pitch of the chord
                        sounding under it. Without this stars are only
                        restricted to the union of every chord in the piece,
                        which with several nebulae is all twelve pitch classes
                        and therefore no restriction at all
    count_in_beats      silence before the first event, so a DAW locking to
                        the clock has time to catch up
    notes_per_slice     how many star notes may start in one grid slice. This
                        is the density control, and it is the one that decides
                        whether the piece sounds like music or like a cloud.
                        A slice keeps its loudest notes and drops the rest, so
                        thinning removes the faint ones first and a sparse
                        region of the image stays sparse instead of being
                        padded. 0 keeps everything
    star_duration_scale multiplies both layers' note lengths. Raise it to make
                        notes ring into each other, lower it for a drier sound
    """

    send_clock: bool = True
    send_song_position: bool = True
    grid_subdivision: int = 4
    quantise_strength: float = 1.0
    fit_stars_to_chord: bool = True
    count_in_beats: float = 4.0
    notes_per_slice: int = 1
    star_duration_scale: float = 1.0


@dataclass
class TempoConfig:
    bpm: int = 90
    subdivision: int = 16


@dataclass
class HarmonyConfig:
    """Harmony.

    nebula_total_duration_beats  phrase length given to each nebula
    chord_low_note               bottom of the chord bed, as a MIDI note.
                                 48 is C3
    chord_high_note              top of the bed. 72 is C5
    octave_offset                whole-octave shift applied after placement

    The bed exists because a chord root arrives as a pitch class, 0 to 11.
    Used directly as a MIDI note that is the octave below the lowest note on
    a piano — between 8 and 23 Hz, which is felt rather than heard. Every
    chord has to be lifted into a register that speaks.
    """

    nebula_total_duration_beats: float = 64.0
    chord_low_note: int = 48
    chord_high_note: int = 72
    octave_offset: int = 0


@dataclass
class Config:
    images: ImageConfig
    star_detector: StarDetectorConfig
    nebula_detector: NebulaDetectorConfig
    stars: StarsConfig
    transport: TransportConfig
    tempo: TempoConfig
    harmony: HarmonyConfig

    image_path: Optional[str] = None
    output_dir: Optional[str] = None

    _SECTIONS = {
        "images": ImageConfig,
        "star_detector": StarDetectorConfig,
        "nebula_detector": NebulaDetectorConfig,
        "stars": StarsConfig,
        "transport": TransportConfig,
        "tempo": TempoConfig,
        "harmony": HarmonyConfig,
    }

    @classmethod
    def from_json(cls, config_path: str) -> "Config":
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"{ERR_FILE_NOT_FOUND}: {config_path}")

        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        sections: dict[str, Any] = {}
        unknown: list[str] = []
        for name, section_type in cls._SECTIONS.items():
            section, extra = _build(section_type, data.get(name, {}))
            sections[name] = section
            unknown.extend(f"{name}.{key}" for key in extra)

        for key in data:
            if key not in cls._SECTIONS and key not in ("image_path", "output_dir"):
                unknown.append(key)
        if unknown:
            print(f"[Config] ignored unknown keys: {', '.join(sorted(unknown))}")

        return cls(
            image_path=data.get("image_path"),
            output_dir=data.get("output_dir"),
            **sections,
        )

    def validate(self) -> None:
        """Raise ValueError listing everything that is out of range."""

        errors: list[str] = []

        def check(condition: bool, message: str) -> None:
            if not condition:
                errors.append(message)

        check(self.images.working_size >= 0, "images.working_size cannot be negative")
        check(
            self.images.saturation_boost >= 0,
            "images.saturation_boost cannot be negative",
        )

        star = self.star_detector
        check(star.background_radius_frac > 0, "background_radius_frac must be positive")
        check(star.detection_sigma > 0, "detection_sigma must be positive")
        check(star.minimum_contrast >= 0, "minimum_contrast cannot be negative")
        check(
            0 <= star.minimum_brightness <= 255,
            "minimum_brightness must be between 0 and 255",
        )
        check(star.minimum_area_px >= 1, "minimum_area_px must be at least 1")
        check(star.max_area_frac >= 0, "max_area_frac cannot be negative")
        check(0 <= star.roundness_min <= 1, "roundness_min must be between 0 and 1")
        check(star.max_elongation >= 1, "max_elongation must be at least 1")
        check(
            0 < star.big_star_flux_percentile < 100,
            "big_star_flux_percentile must be between 0 and 100 exclusive",
        )
        check(star.aperture_radius_px >= 0, "aperture_radius_px cannot be negative")

        nebula = self.nebula_detector
        check(
            nebula.star_suppression_frac >= 0,
            "star_suppression_frac cannot be negative",
        )
        check(nebula.small_radius_frac > 0, "small_radius_frac must be positive")
        check(
            nebula.large_radius_frac > nebula.small_radius_frac,
            "large_radius_frac must be larger than small_radius_frac",
        )
        check(nebula.seed_sigma > 0, "nebula seed_sigma must be positive")
        check(
            nebula.grow_mode in ("sigma", "percentile"),
            'nebula grow_mode must be "sigma" or "percentile"',
        )
        check(
            nebula.grow_sigma <= nebula.seed_sigma,
            "grow_sigma must not exceed seed_sigma (the halo threshold is the "
            "lower of the two)",
        )
        check(
            0 < nebula.grow_percentile < 100,
            "grow_percentile must be between 0 and 100 exclusive",
        )
        check(
            0 < nebula.max_cover_frac <= 1,
            "max_cover_frac must be between 0 and 1",
        )
        check(
            0 < nebula.max_star_flux_share <= 1,
            "max_star_flux_share must be between 0 and 1",
        )
        check(nebula.min_area_frac > 0, "min_area_frac must be positive")
        check(nebula.max_area_frac >= 0, "max_area_frac cannot be negative")
        check(
            0 <= nebula.saturation_threshold <= 1,
            "nebula saturation_threshold must be between 0 and 1",
        )
        check(nebula.dominant_colors >= 1, "dominant_colors must be at least 1")

        stars = self.stars
        check(0 <= stars.pan_cc <= 127, "stars.pan_cc must be 0-127")
        for prefix in ("small", "big"):
            low = getattr(stars, f"{prefix}_low_note")
            high = getattr(stars, f"{prefix}_high_note")
            check(0 <= low <= 127, f"stars.{prefix}_low_note must be 0-127")
            check(0 <= high <= 127, f"stars.{prefix}_high_note must be 0-127")
            check(high > low, f"stars.{prefix}_high_note must be above {prefix}_low_note")
            check(
                getattr(stars, f"{prefix}_duration_beats") > 0,
                f"stars.{prefix}_duration_beats must be positive",
            )
            check(
                0 <= getattr(stars, f"{prefix}_channel") <= 15,
                f"stars.{prefix}_channel must be 0-15",
            )
        check(
            len({stars.small_channel, stars.big_channel, stars.chord_channel}) == 3,
            "star layers and chords must use three different MIDI channels",
        )

        transport = self.transport
        check(
            transport.grid_subdivision >= 1,
            "transport.grid_subdivision must be at least 1",
        )
        check(
            0 <= transport.quantise_strength <= 1,
            "transport.quantise_strength must be between 0 and 1",
        )
        check(
            transport.count_in_beats >= 0,
            "transport.count_in_beats cannot be negative",
        )
        check(
            transport.notes_per_slice >= 0,
            "transport.notes_per_slice cannot be negative",
        )
        check(
            transport.star_duration_scale > 0,
            "transport.star_duration_scale must be positive",
        )

        check(self.tempo.bpm > 0, "tempo.bpm must be positive")
        check(self.tempo.subdivision > 0, "tempo.subdivision must be positive")

        check(
            self.harmony.nebula_total_duration_beats > 0,
            "nebula_total_duration_beats must be positive",
        )
        check(
            0 <= self.harmony.chord_low_note <= 127,
            "harmony.chord_low_note must be 0-127",
        )
        check(
            0 <= self.harmony.chord_high_note <= 127,
            "harmony.chord_high_note must be 0-127",
        )
        check(
            self.harmony.chord_high_note - self.harmony.chord_low_note >= 12,
            "the chord bed needs at least one octave between "
            "chord_low_note and chord_high_note",
        )

        if errors:
            raise ValueError(
                "Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
            )


def _build(section_type: type[T], data: dict[str, Any]) -> tuple[T, list[str]]:
    """Instantiate a config dataclass from a dict, reporting unknown keys."""

    known = {field.name for field in fields(section_type)}
    accepted = {key: value for key, value in (data or {}).items() if key in known}
    unknown = [key for key in (data or {}) if key not in known]
    return section_type(**accepted), unknown


class ConfigLoader:
    @staticmethod
    def load(config_path: str) -> Config:
        config = Config.from_json(config_path)
        config.validate()
        print(f"[Config] loaded and validated: {config_path}")
        return config
