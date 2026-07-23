"""
Multi-objective fitness function, collapsed to a single weighted score
(simplest viable version uses weighted-sum GA rather than true Pareto NSGA-II;
see ga.py docstring for how to upgrade to pymoo/NSGA-II later).

All terms are penalties (lower is better); DEAP is configured to MINIMIZE.
"""
import math
from itertools import combinations
from typing import Dict, List, Tuple

from shapely.geometry import box, Point
from shapely.ops import unary_union

from .program import (ENVELOPE, ADJACENCY_PREFS, SEPARATION_PREFS,
                      ROOM_BY_NAME, FENG_SHUI)
from .genome import PlacedRoom, decode
from . import feng_shui

# Weights: tune these to shift what the GA prioritizes.
W_OVERLAP = 150.0       # rooms must not overlap -- heavily penalized
W_OUT_OF_BOUNDS = 150.0 # rooms must stay inside the envelope
W_MIN_DIM = 20.0        # rooms must respect minimum width/height (egress code proxy)
W_ADJACENCY = 3.0
W_SEPARATION = 2.0
W_DAYLIGHT = 4.0
W_CIRCULATION = 1.5
W_EGRESS = 2.0

MAX_EGRESS_DIST = 40.0  # ft -- rough single-story travel-distance-to-exit proxy


def _room_polygons(placed: Dict[str, PlacedRoom]):
    return {name: box(*p.bounds) for name, p in placed.items()}


def _overlap_penalty(polys) -> float:
    total = 0.0
    for a, b in combinations(polys.values(), 2):
        inter = a.intersection(b)
        if not inter.is_empty:
            total += inter.area
    return total


def _out_of_bounds_penalty(polys) -> float:
    envelope_poly = box(*ENVELOPE.bounds)
    total = 0.0
    for poly in polys.values():
        outside = poly.difference(envelope_poly)
        total += outside.area
    return total


def _min_dim_penalty(placed: Dict[str, PlacedRoom]) -> float:
    """Penalize rooms thinner than their code minimum.

    Rooms given explicit dimensions are exempt -- if you asked for 4x20, the
    optimizer shouldn't second-guess you. The minimum only constrains rooms
    whose shape the GA is free to choose.
    """
    total = 0.0
    for p in placed.values():
        if p.room.has_fixed_dims:
            continue
        deficit_w = max(p.room.min_dim - p.w, 0.0)
        deficit_h = max(p.room.min_dim - p.h, 0.0)
        total += deficit_w + deficit_h
    return total


def _center_dist(a: PlacedRoom, b: PlacedRoom) -> float:
    (ax, ay), (bx, by) = a.center, b.center
    return math.hypot(ax - bx, ay - by)


def _adjacency_penalty(placed: Dict[str, PlacedRoom]) -> float:
    total = 0.0
    for name_a, name_b, weight in ADJACENCY_PREFS:
        if name_a not in placed or name_b not in placed:
            continue
        d = _center_dist(placed[name_a], placed[name_b])
        total += weight * d
    return total


def _separation_penalty(placed: Dict[str, PlacedRoom]) -> float:
    total = 0.0
    for name_a, name_b, weight in SEPARATION_PREFS:
        if name_a not in placed or name_b not in placed:
            continue
        d = _center_dist(placed[name_a], placed[name_b])
        # reward is negative penalty: farther apart = lower penalty, floor at 0
        target = 15.0
        total += weight * max(target - d, 0.0)
    return total


def _daylight_penalty(placed: Dict[str, PlacedRoom]) -> float:
    """Proxy: fraction of a room's perimeter that touches the envelope's
    exterior wall. Rooms that "want_exterior" but sit fully interior are
    penalized."""
    ex0, ey0, ex1, ey1 = ENVELOPE.bounds
    tol = 0.05
    total = 0.0
    for p in placed.values():
        if not p.room.wants_exterior:
            continue
        x0, y0, x1, y1 = p.bounds
        touches = (
            abs(x0 - ex0) < tol or abs(x1 - ex1) < tol or
            abs(y0 - ey0) < tol or abs(y1 - ey1) < tol
        )
        if not touches:
            # penalize by distance to nearest exterior wall
            dist_to_wall = min(x0 - ex0, ex1 - x1, y0 - ey0, ey1 - y1)
            total += max(dist_to_wall, 0.0)
    return total


def _circulation_penalty(polys) -> float:
    """Circulation efficiency proxy: uncovered floor area inside the envelope
    (this is 'wasted'/unassigned space -- some is needed for halls, but the
    program already includes a hallway room, so excess beyond that is
    penalized as inefficient layout)."""
    envelope_poly = box(*ENVELOPE.bounds)
    covered = unary_union(list(polys.values()))
    uncovered = envelope_poly.difference(covered)
    return uncovered.area


def _egress_penalty(placed: Dict[str, PlacedRoom]) -> float:
    entry_rooms = [p for p in placed.values() if p.room.is_entry]
    if not entry_rooms:
        return 0.0
    entry_center = entry_rooms[0].center
    total = 0.0
    for p in placed.values():
        if p.room.is_entry:
            continue
        d = math.hypot(p.center[0] - entry_center[0], p.center[1] - entry_center[1])
        total += max(d - MAX_EGRESS_DIST, 0.0)
    return total


def evaluate(genome: List[float]) -> Tuple[float]:
    placed = decode(genome)
    polys = _room_polygons(placed)

    score = 0.0
    score += W_OVERLAP * _overlap_penalty(polys)
    score += W_OUT_OF_BOUNDS * _out_of_bounds_penalty(polys)
    score += W_MIN_DIM * _min_dim_penalty(placed)
    score += W_ADJACENCY * _adjacency_penalty(placed)
    score += W_SEPARATION * _separation_penalty(placed)
    score += W_DAYLIGHT * _daylight_penalty(placed)
    score += W_CIRCULATION * _circulation_penalty(polys)
    score += W_EGRESS * _egress_penalty(placed)

    if FENG_SHUI:
        score += feng_shui.penalty(placed)

    return (score,)  # DEAP expects a tuple


def score_breakdown(genome: List[float]) -> Dict[str, float]:
    """Same terms as evaluate(), but itemized -- useful for debugging /
    reporting which objective is dominating the score."""
    placed = decode(genome)
    polys = _room_polygons(placed)
    parts = {
        "overlap": W_OVERLAP * _overlap_penalty(polys),
        "out_of_bounds": W_OUT_OF_BOUNDS * _out_of_bounds_penalty(polys),
        "min_dim": W_MIN_DIM * _min_dim_penalty(placed),
        "adjacency": W_ADJACENCY * _adjacency_penalty(placed),
        "separation": W_SEPARATION * _separation_penalty(placed),
        "daylight": W_DAYLIGHT * _daylight_penalty(placed),
        "circulation": W_CIRCULATION * _circulation_penalty(polys),
        "egress": W_EGRESS * _egress_penalty(placed),
    }
    if FENG_SHUI:
        parts.update(feng_shui.breakdown(placed))
    return parts
