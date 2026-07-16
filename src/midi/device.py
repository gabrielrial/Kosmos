"""
MIDI device and port manager.
Centralizes the creation and management of MIDI connections.
"""

import mido
from typing import Optional, List


class MidiDevice:
    """
    MIDI device manager.

    Provides methods for:
    - Listing available MIDI ports
    - Creating virtual ports
    - Managing MIDI connections

    """
    
    def __init__(self):
        """Initializes the MIDI device manager."""

        self.ports = {}  # Dictionary of open ports
        self.virtual_outputs = []  # Virtual output ports created
    
    def get_or_create_output(
        self, 
        name: str = "kosmos",
        virtual: bool = True
    ):
        """
        Gets or creates a MIDI output port.
        
        Args:
            name: Port name
            
        Returns:
            MIDI output port
        """

        # If it already exists, return it
        if name in self.ports:
            return self.ports[name]
        
        # Create new port
        try:
            outport = mido.open_output(name, virtual=True)
            self.ports[name] = outport
            
            self.virtual_outputs.append(name)
            
            print(f"[MIDI] Output port '{name}'")
            return outport

        except Exception as e:
            print(f"[ERROR] Could not create MIDI port '{name}': {e}")
            raise
    
    def close_port(self, port, name: Optional[str] = None):
        """
        Closes a MIDI port.
        
        Args:
            port: Port to close
            name: Port name (optional, for logging)
        """
        try:
            if port:
                port.close()
            if name and name in self.ports:
                del self.ports[name]
            
            if name:
                print(f"[MIDI] Port '{name}' closed")
        except Exception as e:
            print(f"[ERROR] Error closing port: {e}")
    
    def close_all(self):
        """Closes all ports."""
        for name, port in list(self.ports.items()):
            self.close_port(port, name)
        
        self.ports.clear()
        self.virtual_inputs.clear()
        self.virtual_outputs.clear()
        print("[MIDI] All ports were closed")

    def get_port(self, name: str):
        """
        Gets an open port by name.
        
        Args:
            name: Port name
            
        Returns:
            MIDI port or None if it doesn't exist
        """
        return self.ports.get(name)
    
    def create_instrument_outputs(self, names: list = None) -> dict:
        """
        Creates 3 MIDI ports, one for each instrument.
        
        Args:
            names: List of 3 names for the instruments
                   Default: ["kosmos_stars", "kosmos_bass", "kosmos_clock"]
        
        Returns:
            Dictionary with the 3 ports: {name: port, ...}
        
        Example:
            >>> device = MidiDevice()
            >>> ports = device.create_instrument_outputs()
            >>> # ports = {
            >>>     "kosmos_stars": outport1,
            >>>     "kosmos_bass": outport2,
            >>>     "kosmos_clock": outport3
            >>> # }
        """
        if names is None:
            names = ["kosmos_stars", "kosmos_bass", "kosmos_clock"]
        
        if len(names) != 3:
            raise ValueError("Exactly 3 instrument names are required.")
        
        output_ports = {}
        
        for name in names:
            try:
                outport = self.get_or_create_output(name, virtual=True)
                output_ports[name] = outport
                print(f"[MIDI] {name}: ✓ Created")
            except Exception as e:
                print(f"[MIDI] {name}: ❌ Error - {e}")
                raise
        
        return output_ports
    
    def __enter__(self):
        """Allows using MidiDevice as a context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Closes all ports when exiting the context."""
        self.close_all()
    
    def __repr__(self) -> str:
        return (
            f"MidiDevice(open_ports={len(self.ports)}, "
            f"virtual_outputs={len(self.virtual_outputs)}, "
            f"virtual_inputs={len(self.virtual_inputs)})"
        )