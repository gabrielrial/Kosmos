from typing import List

@dataclass
class NebulaMidi:
    notes: List[int] = field(default_factory=list)
    chords: List[Chord] = field(default_factory=list)
    duration: List[int] = field(default_factory=list)
    filter_curve: List[float] = field(default_factory=list)
    start_offset: float = 0.0