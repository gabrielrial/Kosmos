from pathlib import Path

from mido import MidiFile, MidiTrack, Message


class MidiSheet:

    def __init__(self, ticks_per_beat: int = 960):
        self.midi_file = MidiFile(ticks_per_beat=ticks_per_beat)
        self.next_channel = 0

    def add_instrument(self, notes, program: int):
        channel = self.next_channel
        self.next_channel += 1

        track = MidiTrack()
        self.midi_file.tracks.append(track)

        track.append(
            Message(
                "program_change",
                channel=channel,
                program=program,
                time=0,
            )
        )

        for note in notes:
            track.append(
                Message(
                    "note_on",
                    channel=channel,
                    note=note.note,
                    velocity=note.velocity,
                    time=0,
                )
            )

            track.append(
                Message(
                    "note_off",
                    channel=channel,
                    note=note.note,
                    velocity=note.velocity,
                    time=note.duration,
                )
            )

    def save(self, output_path: Path):
        self.midi_file.save(output_path)
