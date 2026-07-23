"""
Lot envelope + room program definition.

A room can be specified two ways:

  AREA MODE       "living 280"      -> 280 sqft, the GA chooses the proportions
  DIMENSION MODE  "living 14x20"    -> exactly 14 ft by 20 ft, size is locked

In dimension mode the GA can still rotate the room 90 degrees (so 14x20 may be
placed as 20x14), but it cannot resize it. Use this when you know the room
dimensions you want; use area mode when you only care about square footage and
want the optimizer to work out the shape.

The program is read from a text spec -- see house.txt. Point the
FLOORPLAN_SPEC environment variable at a different file to use another house
without touching any code.
"""
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class Room:
    name: str
    area: float                          # required floor area, sq ft
    min_dim: float = 7.0                 # code-minimum room width/height
    wants_exterior: bool = False         # benefits from an exterior wall (daylight)
    is_entry: bool = False
    fixed_w: Optional[float] = None      # set in dimension mode
    fixed_h: Optional[float] = None

    @property
    def has_fixed_dims(self) -> bool:
        return self.fixed_w is not None and self.fixed_h is not None


@dataclass
class Envelope:
    """Rectangular buildable envelope (already net of setbacks)."""
    width: float   # ft, x-direction
    depth: float   # ft, y-direction

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        return (0.0, 0.0, self.width, self.depth)


# ---------------------------------------------------------------------------
# Spec parsing
# ---------------------------------------------------------------------------

DEFAULT_SPEC = """
lot 42 x 32

entry      60   exterior entry min=6
living     280  exterior min=12
kitchen    160  exterior min=10
dining     140  min=10
bedroom1   180  exterior min=11
bedroom2   140  exterior min=10
bedroom3   120  exterior min=10
bathroom1  60   min=6
bathroom2  45   min=5
hallway    90   min=4
"""


def _parse_size(token: str) -> Tuple[float, Optional[float], Optional[float]]:
    """Returns (area, fixed_w, fixed_h). Accepts '280' or '14x20'."""
    token = token.lower().replace(" ", "")
    if "x" in token:
        left, right = token.split("x", 1)
        w, h = float(left), float(right)
        if w <= 0 or h <= 0:
            raise ValueError(f"dimensions must be positive, got '{token}'")
        return w * h, w, h
    area = float(token)
    if area <= 0:
        raise ValueError(f"area must be positive, got '{token}'")
    return area, None, None


def parse_spec(text: str) -> Tuple[Envelope, List[Room]]:
    envelope = None
    rooms: List[Room] = []

    # Build the list of logical lines. Comments are stripped FIRST, then
    # semicolons are treated as line breaks -- doing it the other way round
    # lets a semicolon inside a comment leak the rest of that comment out as
    # a bogus line.
    logical_lines: List[Tuple[int, str]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        without_comment = raw.split("#", 1)[0]
        for piece in without_comment.split(";"):
            piece = piece.strip()
            if piece:
                logical_lines.append((lineno, piece))

    for lineno, line in logical_lines:
        parts = line.split()

        try:
            if parts[0].lower() == "lot":
                rest = "".join(parts[1:])
                w, d = rest.lower().split("x", 1)
                envelope = Envelope(width=float(w), depth=float(d))
                continue

            name = parts[0]
            if len(parts) < 2:
                raise ValueError("missing size")

            area, fw, fh = _parse_size(parts[1])

            min_dim = 7.0
            wants_exterior = False
            is_entry = False
            for flag in parts[2:]:
                f = flag.lower()
                if f == "exterior":
                    wants_exterior = True
                elif f == "entry":
                    is_entry = True
                elif f.startswith("min="):
                    min_dim = float(f[4:])
                else:
                    raise ValueError(f"unknown flag '{flag}'")

            rooms.append(Room(
                name=name, area=area, min_dim=min_dim,
                wants_exterior=wants_exterior, is_entry=is_entry,
                fixed_w=fw, fixed_h=fh,
            ))

        except ValueError as e:
            raise ValueError(f"line {lineno}: {line!r} -- {e}") from e

    if envelope is None:
        raise ValueError("spec is missing a 'lot WIDTH x DEPTH' line")
    if not rooms:
        raise ValueError("spec contains no rooms")

    total = sum(r.area for r in rooms)
    lot_area = envelope.width * envelope.depth
    if total > lot_area:
        raise ValueError(
            f"rooms total {total:.0f} sqft but the lot is only {lot_area:.0f} sqft. "
            f"Shrink the rooms or enlarge the lot."
        )

    n_entry = sum(1 for r in rooms if r.is_entry)
    if n_entry != 1:
        raise ValueError(
            f"exactly one room must be flagged 'entry' (found {n_entry})"
        )

    # Locked-dimension rooms can't be squeezed into leftover gaps, so a tight
    # program becomes an unsolvable packing problem. Warn rather than fail --
    # the optimizer will still return its best attempt.
    n_fixed = sum(1 for r in rooms if r.has_fixed_dims)
    coverage = total / lot_area
    if n_fixed and coverage > 0.85:
        import warnings
        warnings.warn(
            f"\n  Rooms fill {coverage:.0%} of the lot and {n_fixed} of them have "
            f"locked dimensions.\n"
            f"  Fixed-size rooms need slack to pack cleanly -- above about 85% "
            f"coverage they\n"
            f"  usually can't fit without overlapping. Consider a larger lot "
            f"(currently\n"
            f"  {envelope.width:g}x{envelope.depth:g} ft) or smaller rooms.\n",
            stacklevel=2,
        )

    for r in rooms:
        if r.has_fixed_dims:
            longest = max(r.fixed_w, r.fixed_h)
            shortest = min(r.fixed_w, r.fixed_h)
            lot_long = max(envelope.width, envelope.depth)
            lot_short = min(envelope.width, envelope.depth)
            if longest > lot_long or shortest > lot_short:
                raise ValueError(
                    f"room '{r.name}' ({r.fixed_w:g}x{r.fixed_h:g} ft) does not fit "
                    f"in a {envelope.width:g}x{envelope.depth:g} ft lot"
                )

    return envelope, rooms


def _load_spec_text() -> str:
    """Spec source, in priority order:
       1. FLOORPLAN_SPEC_TEXT env var (raw text -- used by the workflow form)
       2. FLOORPLAN_SPEC env var (path to a file)
       3. house.txt at the repo root
       4. the built-in DEFAULT_SPEC
    """
    inline = os.environ.get("FLOORPLAN_SPEC_TEXT")
    if inline and inline.strip():
        return inline

    path = os.environ.get("FLOORPLAN_SPEC")
    if path:
        with open(path) as f:
            return f.read()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_file = os.path.join(repo_root, "house.txt")
    if os.path.exists(default_file):
        with open(default_file) as f:
            return f.read()

    return DEFAULT_SPEC


# ---------------------------------------------------------------------------
# Module-level program (what the rest of the codebase reads)
# ---------------------------------------------------------------------------

ENVELOPE, ROOMS = parse_spec(_load_spec_text())

ROOM_NAMES = [r.name for r in ROOMS]
ROOM_BY_NAME = {r.name: r for r in ROOMS}

TOTAL_ROOM_AREA = sum(r.area for r in ROOMS)
ENVELOPE_AREA = ENVELOPE.width * ENVELOPE.depth

# Adjacency preferences: (room_a, room_b, weight). Pairs referencing rooms that
# don't exist in the current program are skipped by the fitness function, so
# these stay valid across different house specs.
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

SEPARATION_PREFS: List[Tuple[str, str, float]] = [
    ("bedroom1", "entry", 0.6),
    ("bedroom2", "entry", 0.6),
    ("bedroom3", "entry", 0.6),
    ("bedroom1", "kitchen", 0.3),
]


if __name__ == "__main__":
    print(f"Lot: {ENVELOPE.width:g} x {ENVELOPE.depth:g} ft "
          f"({ENVELOPE_AREA:.0f} sqft)")
    print(f"{len(ROOMS)} rooms, {TOTAL_ROOM_AREA:.0f} sqft total "
          f"({TOTAL_ROOM_AREA / ENVELOPE_AREA:.0%} coverage)\n")
    for r in ROOMS:
        if r.has_fixed_dims:
            size = f"{r.fixed_w:g} x {r.fixed_h:g} ft (locked)"
        else:
            size = f"{r.area:.0f} sqft (shape free)"
        tags = []
        if r.wants_exterior:
            tags.append("exterior")
        if r.is_entry:
            tags.append("entry")
        print(f"  {r.name:12s} {size:26s} {' '.join(tags)}")
