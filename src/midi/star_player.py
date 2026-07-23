"""
Player for playing detected stars as MIDI notes.
"""

import time
import random
import mido, math
from typing import List, Optional
from models.star import Star, Stars
from threading import Thread


class StarMidiPlayer(Thread):
    """
    Plays stars detected in images as MIDI notes.

    Features:
    - Each star is converted to a MIDI note
    - Channels are assigned based on horizontal position (pan)
    - Durations and velocities are based on star properties
    - Supports synchronization with global tempo

    Example:
        >>> from src.config import ConfigLoader
        >>> stars = detector.detect_small_stars(image)
        >>> player = StarMidiPlayer(outport, stars, tempo=tempo)
        >>> player.start()  # Starts in thread
        >>> player.join()   # Wait for completion
    """

    def __init__(
        self,
        stars: Stars,
        outport,
        channel_base: int = 3,
        speed_beats: float = 800000,
        tempo=None,
        shuffle: bool = True,
    ):
        """
        Initializes the star player.

        Args:
            stars: List of detected Star objects
            outport: MIDI output port
            channel_base: Base MIDI channel (0-15)
            speed_beats: Duration of each note in beats
            tempo: Tempo object for synchronization (optional)
            shuffle: If True, plays stars in random order
        """
        self.stars = stars
        self.speed_beats = speed_beats
        self.tempo = tempo
        self.shuffle = shuffle
        self.channel_base = channel_base
        self.outport = outport
        super().__init__()

        # Calcular velocidad en segundos si hay tempo

    def run(self):
        """
        Plays all stars as a MIDI sequence.
        Runs in a separate thread.
        """
        # Shuffle if enabled

        for star in self.stars:
            # if not self.running:
            #    break

            # Determine channel based on X position (pan)

            cc = int(self._get_chain_index(star.pan))

            # Log
            self._log_star(star, 1)

            # Enviar nota
            self._send_note_on(star, self.channel_base, cc)
            time.sleep(star.duration)
            self._send_note_off(star, self.channel_base)
            time.sleep(star.duration * 4)

    def _get_chain_index(self, pan: float) -> int:
        pan = max(0, min(int(pan), 127))

        return pan // 12

    def _send_note_on(self, star, channel: int, pan: int):

        pan = max(0, min(int(pan), 127))
        print(f"Midi Chain list: {pan}")

        # CC SIEMPRE en canal fijo (0)
        self.outport.send(mido.Message("control_change", control=7, value=pan))

        # Note also on fixed channel (0 or base, but consistent)
        self.outport.send(
            mido.Message(
                "note_on", note=star.note, velocity=star.velocity, channel=channel
            )
        )

    def _send_note_off(self, star, channel: int):
        """Sends a MIDI note_off message."""
        self.outport.send(
            mido.Message(
                "note_off", note=star.note, velocity=star.velocity, channel=channel
            )
        )

    def _log_star(self, star, channel: int):
        """Log star information (for debugging)."""
        print(
            f"Star: pos({star.x}, {star.y}) "
            f"area={star.area} "
            f"note={star.note} "
            f"velocity={star.velocity} "
            f"pan={star.pan} "
            f"channel={channel}"
        )
