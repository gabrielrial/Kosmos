from config.config import TempoConfig


class Tempo:
    """Manages the global tempo of playback in BPM."""

    def __init__(self, tempo_config: TempoConfig):
        print("Init Tempo")
        """Tempo initializer."""
        if tempo_config.bpm <= 0:
            raise ValueError(f"BPM must be > 0, BPM received: {tempo_config.bpm}")

        self.bpm = tempo_config.bpm
        self.subdivision = tempo_config.subdivision
        self.beat_duration = 60.0 / self.bpm

    def beats_to_seconds(self, beats: float) -> float:
        """Converts beats to seconds."""
        return beats * self.beat_duration

    def subdivision_to_second(self, division: int) -> float:
        """Converts a subdivision index to seconds."""
        subdivision_duration = self.beat_duration / self.subdivision
        return division * subdivision_duration

    def __repr__(self) -> str:
        return f"Tempo(bpm={self.bpm}, beat_duration={self.beat_duration:.4f}s)"

    def __str__(self) -> str:
        return f"{self.bpm} BPM ({self.beat_duration:.3f}s per beat)"
