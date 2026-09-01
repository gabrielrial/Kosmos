import mido


class MidiDevice:
    """
    Creates and manages the MIDI output ports used by Kosmos.
    """

    def __init__(self):
        self.ports = {}

        self._create_ports()

    def _create_ports(self):
        """Create all MIDI output ports used by Kosmos."""

        names = [
            "kosmos_stars",
            "kosmos_bass",
            "kosmos_clock",
            "kosmos_nebula",
        ]

        for name in names:
            self.ports[name] = mido.open_output(
                name,
                virtual=True
            )

    def get_port(self, name: str):
        """Return a MIDI port by name."""
        return self.ports.get(name)

    def close(self):
        """Close all MIDI ports."""

        for port in self.ports.values():
            port.close()

        self.ports.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __repr__(self):
        return f"MidiDevice(ports={list(self.ports.keys())})"