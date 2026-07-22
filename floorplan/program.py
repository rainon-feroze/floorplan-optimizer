"""
Lot envelope + room program definition.

This is step 1 of the build order: a hardcoded lot and room program.
Everything downstream (genome, fitness, GA) reads from this module, so
swapping in a different house is just a matter of editing the lists below.
"""
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Room:
    name: str
    area: float           # required floor area, sq ft
    min_dim: float = 7.0  # minimum width/height allowed (crude "egress code" min room dimension)
    wants_exterior: bool = False  # daylighting: room benefits from touching an exterior wall
    is_entry: bool = False


@dataclass
class Envelope:
    """Rectangular buildable envelope (already net of setbacks)."""
    width: float   # ft, x-direction
    depth: float   # ft, y-direction

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        # (xmin, ymin, xmax, ymax)
        return (0.0, 0.0, self.width, self.depth)


# ---------------------------------------------------------------------------
# Hardcoded example: a small single-story 3-bed / 2-bath house
# ---------------------------------------------------------------------------

ENVELOPE = Envelope(width=42.0, depth=32.0)  # 42' x 32' buildable footprint, ~1344 sqft

ROOMS: List[Room] = [
    Room("entry",     area=60,  min_dim=6, wants_exterior=True,  is_entry=True),
    Room("living",    area=280, min_dim=12, wants_exterior=True),
    Room("kitchen",   area=160, min_dim=10, wants_exterior=True),
    Room("dining",    area=140, min_dim=10, wants_exterior=False),
    Room("bedroom1",  area=180, min_dim=11, wants_exterior=True),
    Room("bedroom2",  area=140, min_dim=10, wants_exterior=True),
    Room("bedroom3",  area=120, min_dim=10, wants_exterior=True),
    Room("bathroom1", area=60,  min_dim=6,  wants_exterior=False),
    Room("bathroom2", area=45,  min_dim=5,  wants_exterior=False),
    Room("hallway",   area=90,  min_dim=4,  wants_exterior=False),
]

ROOM_NAMES = [r.name for r in ROOMS]
ROOM_BY_NAME = {r.name: r for r in ROOMS}

TOTAL_ROOM_AREA = sum(r.area for r in ROOMS)
ENVELOPE_AREA = ENVELOPE.width * ENVELOPE.depth

# Adjacency preferences: (room_a, room_b, weight). Higher weight = stronger pull.
ADJACENCY_PREFS: List[Tuple[str, str, float]] = [
    ("kitchen", "dining", 1.0),
    ("dining", "living", 0.8),
    ("entry", "living", 0.6),
    ("entry", "hallway", 0.8),
    ("hallway", "bedroom1", 0.8),
    ("hallway", "bedroom2", 0.8),
    ("hallway", "bedroom3", 0.8),
    ("hallway", "bathroom1", 0.6),
    ("bedroom1", "bathroom1", 0.5),
    ("bathroom2", "hallway", 0.4),
]

# Separation preferences: (room_a, room_b, weight). Rooms pushed apart.
SEPARATION_PREFS: List[Tuple[str, str, float]] = [
    ("bedroom1", "entry", 0.6),
    ("bedroom2", "entry", 0.6),
    ("bedroom3", "entry", 0.6),
    ("bedroom1", "kitchen", 0.3),
]

if __name__ == "__main__":
    print(f"Envelope area: {ENVELOPE_AREA:.0f} sqft")
    print(f"Total room area: {TOTAL_ROOM_AREA:.0f} sqft "
          f"({TOTAL_ROOM_AREA / ENVELOPE_AREA:.0%} coverage)")
