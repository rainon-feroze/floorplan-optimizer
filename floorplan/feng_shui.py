"""
Feng shui rules, encoded as geometry.

These are traditional design principles, not empirical performance criteria --
they're included because "the client wants feng shui compliance" is a real
constraint an architect gets handed, and because the rules turn out to be
unusually well suited to this kind of solver: almost all of them reduce to
adjacency, orientation, or sightline conditions the fitness function can
already express.

Everything here is optional. With feng shui disabled the layout scoring is
byte-for-byte identical to before, so the two rule sets can be compared
directly on the same room program.

Implemented rules
-----------------
1. chi_straight_shot   No unobstructed run from the front door across the
                       house -- "chi" (and, less mystically, conditioned air,
                       sound, and sightlines into private space) shouldn't
                       shoot straight through.
2. bathroom_at_entry   Bathroom shouldn't be the first thing facing the door.
3. kitchen_bath_clash  Kitchen and bathroom shouldn't share a wall
                       (the fire/water clash).
4. bathroom_center     Nothing wet in the tai chi -- the center of the plan.
5. bedroom_command     Bedrooms out of the door's direct line of travel.
6. bagua_zones         Preferred and disfavored octants for key rooms,
                       oriented to the entry wall.

The bagua grid used is the Black Sect (BTB) form, which orients to the front
door rather than to magnetic compass north. That choice matters: it makes the
rules a function of the plan itself, so they stay meaningful without knowing
which way the lot faces.
"""
import math
from typing import Dict, Optional, Tuple

from shapely.geometry import LineString, box
from shapely.ops import unary_union

from .program import ENVELOPE

# Weights. Deliberately modest relative to the physical constraints in
# fitness.py -- feng shui should shape a layout, not override whether the
# rooms physically fit.
W_CHI_SHOT = 3.0
W_BATH_ENTRY = 2.5
W_KITCHEN_BATH = 2.0
W_BATH_CENTER = 3.0
W_BEDROOM_COMMAND = 1.5
W_BAGUA = 2.0

# Rooms are matched by name prefix so "bathroom1"/"bathroom2" both count.
BATHROOM_PREFIX = "bath"
KITCHEN_PREFIX = "kitchen"
BEDROOM_PREFIX = "bedroom"


# ---------------------------------------------------------------------------
# Orientation: which wall is the front door on?
# ---------------------------------------------------------------------------

def entry_wall(placed) -> Optional[str]:
    """Which exterior wall the entry sits on: 'S', 'N', 'W', or 'E'.

    'S' is y=0 by convention -- the bottom of the drawing. Returns None if
    there's no entry room (shouldn't happen; the spec parser requires one).
    """
    entries = [p for p in placed.values() if p.room.is_entry]
    if not entries:
        return None
    e = entries[0]
    ex0, ey0, ex1, ey1 = ENVELOPE.bounds

    dists = {
        "S": e.y - ey0,
        "N": ey1 - (e.y + e.h),
        "W": e.x - ex0,
        "E": ex1 - (e.x + e.w),
    }
    return min(dists, key=dists.get)


def _inward_normal(wall: str) -> Tuple[float, float]:
    return {"S": (0.0, 1.0), "N": (0.0, -1.0),
            "W": (1.0, 0.0), "E": (-1.0, 0.0)}[wall]


# ---------------------------------------------------------------------------
# Rule 1: chi shouldn't shoot straight through the house
# ---------------------------------------------------------------------------

def chi_straight_shot(placed) -> float:
    """Cast a ray inward from the front door. Penalize how far it travels
    before hitting a room -- a clear run all the way across is the worst case.

    The traditional objection is that chi enters and immediately escapes. The
    practical objection is identical in shape: an unobstructed axis from the
    front door means no privacy buffer and nothing to slow air or sound.
    """
    wall = entry_wall(placed)
    if wall is None:
        return 0.0

    entries = [p for p in placed.values() if p.room.is_entry]
    ex, ey = entries[0].center
    dx, dy = _inward_normal(wall)

    ax0, ay0, ax1, ay1 = ENVELOPE.bounds
    span = math.hypot(ax1 - ax0, ay1 - ay0)
    ray = LineString([(ex, ey), (ex + dx * span, ey + dy * span)])

    others = [box(*p.bounds) for p in placed.values() if not p.room.is_entry]
    if not others:
        return 0.0

    blocked = ray.intersection(unary_union(others))
    if blocked.is_empty:
        # nothing in the way at all -- full-length penalty
        clear_run = ray.length
    else:
        # distance from the door to the first thing the ray touches
        start = ray.interpolate(0.0)
        clear_run = start.distance(blocked)

    # Only penalize runs long enough to matter (a few feet of clearance in
    # front of the door is desirable -- the "bright hall").
    return max(clear_run - 8.0, 0.0)


# ---------------------------------------------------------------------------
# Rule 2: bathroom shouldn't face the front door
# ---------------------------------------------------------------------------

def bathroom_at_entry(placed) -> float:
    entries = [p for p in placed.values() if p.room.is_entry]
    if not entries:
        return 0.0
    ex, ey = entries[0].center

    target = 18.0  # ft of separation considered adequate
    total = 0.0
    for p in placed.values():
        if not p.name.lower().startswith(BATHROOM_PREFIX):
            continue
        d = math.hypot(p.center[0] - ex, p.center[1] - ey)
        total += max(target - d, 0.0)
    return total


# ---------------------------------------------------------------------------
# Rule 3: kitchen and bathroom shouldn't share a wall
# ---------------------------------------------------------------------------

def _shared_wall_length(a, b, tol: float = 0.25) -> float:
    """Length of wall two rectangles hold in common. Zero if they don't touch."""
    ax0, ay0, ax1, ay1 = a.bounds
    bx0, by0, bx1, by1 = b.bounds

    # vertical shared wall
    if abs(ax1 - bx0) < tol or abs(bx1 - ax0) < tol:
        overlap = min(ay1, by1) - max(ay0, by0)
        if overlap > 0:
            return overlap
    # horizontal shared wall
    if abs(ay1 - by0) < tol or abs(by1 - ay0) < tol:
        overlap = min(ax1, bx1) - max(ax0, bx0)
        if overlap > 0:
            return overlap
    return 0.0


def kitchen_bath_clash(placed) -> float:
    kitchens = [p for p in placed.values()
                if p.name.lower().startswith(KITCHEN_PREFIX)]
    baths = [p for p in placed.values()
             if p.name.lower().startswith(BATHROOM_PREFIX)]

    total = 0.0
    for k in kitchens:
        for b in baths:
            total += _shared_wall_length(k, b)
    return total


# ---------------------------------------------------------------------------
# Rule 4: nothing wet in the tai chi (center of the plan)
# ---------------------------------------------------------------------------

def bathroom_center(placed) -> float:
    """Fraction of each bathroom's area sitting in the middle ninth of the
    plan, summed. Normalized rather than raw square feet so the weight means
    the same thing on a 1,300 sf cottage and a 6,000 sf house."""
    ax0, ay0, ax1, ay1 = ENVELOPE.bounds
    w, h = ax1 - ax0, ay1 - ay0

    center_cell = box(ax0 + w / 3, ay0 + h / 3, ax0 + 2 * w / 3, ay0 + 2 * h / 3)

    total = 0.0
    for p in placed.values():
        if not p.name.lower().startswith(BATHROOM_PREFIX):
            continue
        area = p.w * p.h
        if area <= 0:
            continue
        overlap = box(*p.bounds).intersection(center_cell)
        if not overlap.is_empty:
            total += overlap.area / area   # 0..1 per bathroom
    return total * 25.0   # scale into the same range as the other terms


# ---------------------------------------------------------------------------
# Rule 5: bedrooms out of the door's line of travel
# ---------------------------------------------------------------------------

def bedroom_command(placed) -> float:
    """Penalize bedrooms sitting directly in the corridor projected inward
    from the front door. The traditional framing is the "command position";
    the practical one is that you don't want the front door opening onto a
    sightline into a bedroom.
    """
    wall = entry_wall(placed)
    if wall is None:
        return 0.0

    entries = [p for p in placed.values() if p.room.is_entry]
    entry = entries[0]
    ex, ey = entry.center

    # A corridor as wide as the entry, projected straight in.
    horizontal = wall in ("S", "N")
    half_width = (entry.w if horizontal else entry.h) / 2

    total = 0.0
    for p in placed.values():
        if not p.name.lower().startswith(BEDROOM_PREFIX):
            continue
        cx, cy = p.center
        offset = abs(cx - ex) if horizontal else abs(cy - ey)
        if offset < half_width:
            total += half_width - offset
    return total


# ---------------------------------------------------------------------------
# Rule 6: bagua zones
# ---------------------------------------------------------------------------

# Grid positions are (row, col) with row 0 nearest the entry wall and col 0
# on the left as you stand in the doorway looking in.
BAGUA_NAMES = {
    (0, 0): "knowledge", (0, 1): "career",  (0, 2): "helpful people",
    (1, 0): "family",    (1, 1): "tai chi", (1, 2): "children",
    (2, 0): "wealth",    (2, 1): "fame",    (2, 2): "relationships",
}

# (room prefix, zone, weight). Negative weight = favored placement.
BAGUA_RULES = [
    ("bathroom", "wealth",        1.0),   # wealth draining away
    ("bathroom", "tai chi",       1.0),
    ("kitchen",  "tai chi",       0.8),
    ("kitchen",  "career",        0.6),   # stove facing the door
    ("bedroom1", "relationships", -0.8),  # master bedroom favored here
    ("living",   "family",        -0.4),
]


def _zone_of(px: float, py: float, wall: str) -> Tuple[int, int]:
    """Map an absolute point to a (row, col) bagua cell, oriented to the
    entry wall so row 0 is always the front of the house."""
    ax0, ay0, ax1, ay1 = ENVELOPE.bounds
    u = (px - ax0) / (ax1 - ax0)   # 0..1 across width
    v = (py - ay0) / (ay1 - ay0)   # 0..1 across depth

    if wall == "S":
        depth, across = v, u
    elif wall == "N":
        depth, across = 1 - v, 1 - u
    elif wall == "W":
        depth, across = u, 1 - v
    else:  # "E"
        depth, across = 1 - u, v

    row = min(int(depth * 3), 2)
    col = min(int(across * 3), 2)
    return row, col


def bagua_zones(placed) -> float:
    wall = entry_wall(placed)
    if wall is None:
        return 0.0

    zone_lookup = {v: k for k, v in BAGUA_NAMES.items()}
    total = 0.0

    for prefix, zone_name, weight in BAGUA_RULES:
        target_cell = zone_lookup.get(zone_name)
        if target_cell is None:
            continue
        for p in placed.values():
            if not p.name.lower().startswith(prefix):
                continue
            cell = _zone_of(p.center[0], p.center[1], wall)
            if cell == target_cell:
                # weight is a penalty; negative weights reward the placement
                total += weight * 10.0
    return total


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

RULES = [
    ("chi_straight_shot",  chi_straight_shot,  W_CHI_SHOT),
    ("bathroom_at_entry",  bathroom_at_entry,  W_BATH_ENTRY),
    ("kitchen_bath_clash", kitchen_bath_clash, W_KITCHEN_BATH),
    ("bathroom_center",    bathroom_center,    W_BATH_CENTER),
    ("bedroom_command",    bedroom_command,    W_BEDROOM_COMMAND),
    ("bagua_zones",        bagua_zones,        W_BAGUA),
]


def penalty(placed) -> float:
    return sum(w * fn(placed) for _, fn, w in RULES)


def breakdown(placed) -> Dict[str, float]:
    return {name: w * fn(placed) for name, fn, w in RULES}
