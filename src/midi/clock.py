import threading
import time
import mido

from models.tempo import Tempo


class MidiClockGenerator(threading.Thread):
    """
    Generates MIDI Clock for synchronization with external equipment/software.

    MIDI Clock sends 24 clock pulses per quarter note (beat).
    This allows DAWs like Ableton Live to synchronize with Kosmos.

    Features:
    - Sends START when the clock starts
    - Sends CLOCK continuously (24 per beat)
    - Sends STOP when stopping
    - Runs in a daemon thread

    Example:
        >>> tempo = Tempo(120)
        >>> clock = MidiClockGenerator(outport, tempo)
        >>> clock.start()
        >>> # Rest of the code can continue
        >>> clock.stop()
    """

    # MIDI standard: 24 clocks per quarter note
    PPQN = 24

    def __init__(self, outport, tempo: Tempo):
        """
        Initializes the MIDI Clock generator.

        Args:
            outport: MIDI output port
            tempo: Tempo object with BPM information
        """
        super().__init__(daemon=True)

        self.outport = outport
        self.tempo = tempo
        self.running = False

    def run(self):
        """
        Generates MIDI Clock continuously.

        """
        clock_interval = (
                    self.tempo.beat_duration / self.PPQN
                )
        print(
            f"BPM: {self.tempo.bpm}, "
            f"beat_duration: {self.tempo.beat_duration}, "
            f"clock_interval: {clock_interval}"
            )
        if self.tempo is None:
            raise ValueError("Tempo is required")

        self.running = True

        try:
            self._send_start()

            while self.running:
                clock_interval = (
                    self.tempo.beat_duration / self.PPQN
                )

                self._send_clock()
                time.sleep(clock_interval)

        except KeyboardInterrupt:
            pass

        finally:
            self._send_stop()

    def stop(self):
        """Stops the MIDI Clock generation."""
        self.running = False

    def _send_start(self):
        """Sends MIDI START message."""
        self.outport.send(mido.Message("start"))
        self._log("START", f"BPM={self.tempo.bpm}")

    def _send_clock(self):
        now = time.perf_counter()

        if hasattr(self, "_last_clock"):
            interval = now - self._last_clock
            print(f"Clock interval: {interval * 1000:.3f} ms")
    
        self._last_clock = now
    
        self.outport.send(mido.Message("clock"))

    def _send_stop(self):
        """Sends MIDI STOP message."""
        self.outport.send(mido.Message("stop"))
        self._log("STOP", "Clock generator stopped")

    def _log(self, event: str, details: str = ""):
        """Clock event logging."""
        msg = f"[MIDI Clock] {event}"

        if details:
            msg += f" - {details}"

        print(msg)

    def __repr__(self) -> str:
        return (
            f"MidiClockGenerator("
            f"BPM={self.tempo.bpm}, "
            f"PPQN={self.PPQN})"
        )