class Tempo:
    """Manages the global tempo of playback in BPM."""

    def __init__(self, bpm: float):
        print("Init Tempo")
        """Tempo initializer."""
        if bpm <= 0:
            raise ValueError(f"BPM must be > 0, BPM received: {bpm}")

        self.bpm = float(bpm)
        self.beat_duration = 60.0 / self.bpm
        print(f"BPM:  {self.bpm}")
        print(f"Beat Duration:  {self.beat_duration}")

    def beats_to_seconds(self, beats: float) -> float:
        """Converts beats to seconds."""
        return beats * self.beat_duration

    def seconds_to_beats(self, seconds: float) -> float:
        """Converts seconds to beats."""
        return seconds / self.beat_duration

    def __repr__(self) -> str:
        return f"Tempo(bpm={self.bpm}, beat_duration={self.beat_duration:.4f}s)"

    def __str__(self) -> str:
        return f"{self.bpm} BPM ({self.beat_duration:.3f}s per beat)"
