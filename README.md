# Generative Floor Plan Optimizer

A genetic algorithm that evolves 2D room layouts inside a fixed building
envelope, scored against adjacency, daylighting, circulation, egress, and
code-minimum room dimension objectives.

This implements the "simplest viable version" + steps 1-3 of the suggested
build order from the project brief (steps 1-2: rectangle packing + GA loop;
step 3: constraint checking baked into the fitness function).

![Before and after layout](layout_before_after.png)

Left: best of a random generation-0 population (rooms overlapping, no
structure). Right: the evolved layout after ~400 generations — zero overlap,
kitchen beside dining, bedrooms on the perimeter for daylight and away from
the entry, a compact circulation core.

![GA convergence](ga_convergence.png)

Total penalty score drops from ~62,000 (random) to ~590 (evolved).

## Structure

```
floorplan/
  program.py    # Step 1: the lot envelope + room program (hardcode your house here)
  genome.py     # Genome encoding: 3 genes/room (x, y, aspect ratio) -> placed rectangles
  fitness.py    # Step 3: multi-objective fitness (weighted-sum penalties)
  ga.py         # Step 2: DEAP genetic algorithm loop
  visualize.py  # matplotlib rendering (before/after, convergence curve)
main.py         # Runs everything, saves layout_before_after.png + ga_convergence.png
```

## Running it

```bash
pip install deap shapely matplotlib
python3 main.py
```

Prints an itemized fitness breakdown (overlap, adjacency, daylight, etc.) for
generation 0 vs. the final evolved layout, and saves two PNGs.

## How the genome works

Each room has 3 genes, all floats in `[0, 1]`:
- `x, y` — position of the room's corner, as a fraction of the envelope's
  usable width/height (so genes stay well-scaled regardless of house size)
- `aspect` — maps (log-uniform) to a width/height ratio in `[0.4, 2.5]`

Room **area** is fixed from the program (e.g. "bedroom1: 180 sqft"), so given
the aspect ratio, width and height are both determined:
`w = sqrt(area * ratio)`, `h = sqrt(area / ratio)`.

This means the GA can never "cheat" by shrinking a room to dodge overlap
penalties — area is a hard constraint baked into decoding, not something the
GA controls.

## Fitness terms (all penalties, lower = better)

| Term | What it measures |
|---|---|
| `overlap` | Total intersection area between any two rooms (shapely) |
| `out_of_bounds` | Room area falling outside the envelope |
| `min_dim` | Rooms thinner than their code-minimum width/height |
| `adjacency` | Distance between room-pairs that should be close (kitchen↔dining, etc.) |
| `separation` | Rooms that should be apart but aren't (bedrooms↔entry) |
| `daylight` | Exterior-facing rooms (bedrooms, living, kitchen) that don't touch an outside wall |
| `circulation` | Uncovered floor area inside the envelope (beyond the dedicated hallway room) |
| `egress` | Straight-line distance from each room to the entry, penalized past 40 ft |

Weights live at the top of `fitness.py` — turning `W_ADJACENCY` up relative to
`W_DAYLIGHT`, for instance, will visibly shift what kind of layouts the GA
prefers. That's a good thing to demo live in an interview.

## Tuning knobs that mattered

- **Overlap/bounds weight vs. generations**: with the initial weights
  (50x) and 150 generations, the GA converged to ~300 sqft of residual
  overlap — visually a few rooms clipping into each other. Bumping
  `W_OVERLAP`/`W_OUT_OF_BOUNDS` to 150 and running longer (300-400
  generations) with a smaller mutation step (`sigma=0.10`) drove overlap to
  exactly zero. This is the classic GA lesson: a penalty term that isn't
  weighted heavily enough relative to others just gets "negotiated away" by
  the softer objectives.
- **Elitism**: without carrying the single best individual through
  unchanged each generation, the best score occasionally regressed between
  generations due to crossover/mutation noise. One elite slot fixed that.

## Extending toward the "resume-strong" version

1. **Egress as a real path, not straight-line distance** — right now
   `_egress_penalty` uses Euclidean distance to the entry. A more honest
   version would build a graph of room-adjacency-through-doorways and run
   shortest-path, or rasterize the floor plan and do a grid-based BFS/A*
   around walls.
2. **True multi-objective (Pareto) optimization** — swap `ga.py`'s
   weighted-sum DEAP setup for `pymoo`'s NSGA-II, and have `fitness.py`
   return the itemized tuple from `score_breakdown()` instead of a single
   sum. Then you can show a **Pareto front** (daylight vs. circulation
   tradeoff curve) instead of one blended number — this is the single
   biggest upgrade for "demonstrates understanding of real design
   tradeoffs" from the brief.
3. **Doors/openings** — currently rooms are sealed rectangles with no
   connectivity model. Adding a doorway graph (which walls are shared and
   where a door sits) would let adjacency scoring reward *actual* access,
   not just proximity, and would make the egress penalty in (1) meaningful.
4. **Diffusion model stretch goal** — train on RPLAN. The genome/decode
   split here should make that swap relatively contained: replace
   `ga.run()` with a diffusion sampler that outputs the same
   `List[float]` genome format, and `visualize.py`/`fitness.py` need no
   changes.
5. **Non-rectangular lots** — `ENVELOPE` is currently an axis-aligned
   rectangle. A polygon envelope (via Shapely) with a rotated/irregular lot
   shape would demo the "real zoning constraints" angle harder.
