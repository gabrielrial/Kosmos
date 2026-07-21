"""
MIDI Clock generator for external synchronization.
Allows synchronization with DAWs like Ableton Live.
"""

import time
import mido
from typing import Optional


class MidiClockGenerator():
    """
    Generates MIDI Clock for synchronization with external equipment/software.
    
    MIDI Clock is a standard that sends 24 pulses per beat.
    This allows DAWs like Ableton Live to synchronize with Kosmos.
    
    Features:
    - Sends START on initialization
    - Sends CLOCK continuously (24 per beat)
    - Sends STOP when stopping
    - Daemon thread to not block program exit
    
    Example:
        >>> tempo = Tempo(120)  # 120 BPM
        >>> clock = MidiClockGenerator(outport, tempo)
        >>> clock.start()  # Starts in daemon thread
        >>> # Rest of the code can continue
        >>> clock.stop()   # Stop when necessary
    """
    
    # MIDI standard: 24 clocks per beat
    PPQN = 24  # Pulses Per Quarter Note
    
    def __init__(self, outport, tempo=None):
        """
        Initializes the MIDI Clock generator.
        
        Args:
            outport: MIDI output port
            tempo: Tempo object with BPM information
        """
        super().__init__(outport, channel_base=0)
        self.tempo = tempo
        self.daemon = True  # Daemon thread (doesn't block program exit)
    
    def run(self):
        """
        Generates MIDI Clock continuously.
        
        Runs in a daemon thread.
        """
        try:
            # Send START
            self._send_start()
            
            # Generate clocks continuously
            while self.running:
                if not self.tempo:
                    break
                
                # Calculate interval between clocks
                # clock_interval = beat_duration / PPQN
                clock_interval = self.tempo.beat_duration / self.PPQN
                
                # Send MIDI clock
                self._send_clock()
                time.sleep(clock_interval)
        
        except KeyboardInterrupt:
            pass
        finally:
            # Enviar STOP
            self._send_stop()
    
    def stop(self):
        """Stops the MIDI Clock generation."""
        self.running = False
        # Give time for the last loop to finish
        time.sleep(1)
    
    def _send_start(self):
        """Sends MIDI START message."""
        self.outport.send(mido.Message('start'))
        self._log("START", f"BPM={self.tempo.bpm if self.tempo else 'unknown'}")
    
    def _send_clock(self):
        """Sends a MIDI CLOCK pulse."""
        self.outport.send(mido.Message('clock'))
    
    def _send_stop(self):
        """Sends MIDI STOP message."""
        self.outport.send(mido.Message('stop'))
        self._log("STOP", "Clock generator stopped")
    
    def _log(self, event: str, details: str = ""):
        """Clock event logging."""
        msg = f"[MIDI Clock] {event}"
        if details:
            msg += f" - {details}"
        print(msg)
    
    def __repr__(self) -> str:
        bpm = self.tempo.bpm if self.tempo else "unknown"
        return f"MidiClockGenerator(BPM={bpm}, PPQN={self.PPQN})"
