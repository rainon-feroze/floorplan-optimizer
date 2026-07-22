"""
Genome <-> layout conversion.

Each room gets 3 genes: (x, y, aspect).
  - x, y     : position of the room's bottom-left corner, as a FRACTION (0-1)
               of the envelope width/height. Keeping genes in [0,1] makes
               crossover/mutation well-behaved regardless of envelope size.
  - aspect   : log-aspect-ratio in [-1, 1], mapped to width/height ratio in
               [0.4, 2.5]. Room AREA is fixed (from the program), so aspect
               alone determines width and height:
                   w = sqrt(area * ratio)
                   h = sqrt(area / ratio)

So genome length = 3 * num_rooms, all floats in [0, 1] (aspect remapped
internally). This keeps every gene the same type/range, which plays nicely
with DEAP's built-in blend crossover and gaussian mutation.
"""
import math
from dataclasses import dataclass
from typing import Dict, List

from .program import ROOMS, ENVELOPE, Room

GENES_PER_ROOM = 3
MIN_RATIO, MAX_RATIO = 0.4, 2.5


@dataclass
class PlacedRoom:
    name: str
    x: float
    y: float
    w: float
    h: float
    room: Room

    @property
    def bounds(self):
        return (self.x, self.y, self.x + self.w, self.y + self.h)

    @property
    def center(self):
        return (self.x + self.w / 2, self.y + self.h / 2)


def genome_length() -> int:
    return GENES_PER_ROOM * len(ROOMS)


def random_gene() -> float:
    import random
    return random.random()


def _aspect_ratio(gene_val: float) -> float:
    # gene_val in [0,1] -> log-uniform ratio in [MIN_RATIO, MAX_RATIO]
    log_min, log_max = math.log(MIN_RATIO), math.log(MAX_RATIO)
    return math.exp(log_min + gene_val * (log_max - log_min))


def decode(genome: List[float]) -> Dict[str, PlacedRoom]:
    """Turn a flat genome into a dict of name -> PlacedRoom (absolute ft coords)."""
    ex0, ey0, ex1, ey1 = ENVELOPE.bounds
    ew, eh = ex1 - ex0, ey1 - ey0

    placed = {}
    for i, room in enumerate(ROOMS):
        gx, gy, ga = genome[i * GENES_PER_ROOM: i * GENES_PER_ROOM + GENES_PER_ROOM]
        ratio = _aspect_ratio(ga)
        w = math.sqrt(room.area * ratio)
        h = math.sqrt(room.area / ratio)

        # clamp so the room (at this size) fits inside the envelope
        max_x = max(ew - w, 0.0)
        max_y = max(eh - h, 0.0)
        x = ex0 + gx * max_x
        y = ey0 + gy * max_y

        placed[room.name] = PlacedRoom(room.name, x, y, w, h, room)
    return placed
