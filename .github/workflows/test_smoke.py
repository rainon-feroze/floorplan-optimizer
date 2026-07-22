"""
Fast smoke test -- verifies the whole pipeline runs end to end without
actually doing a full-length optimization.

Run locally with:   python3 -m tests.test_smoke
CI runs this on every push (see .github/workflows/ci.yml).
"""
import os
import sys
import tempfile

from floorplan.program import ROOMS, ENVELOPE, ENVELOPE_AREA, TOTAL_ROOM_AREA
from floorplan.genome import genome_length, decode, GENES_PER_ROOM
from floorplan.fitness import evaluate, score_breakdown
from floorplan import ga
from floorplan.visualize import plot_before_after, plot_convergence

FAILURES = []


def check(label, condition, detail=""):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label} {detail}")
        FAILURES.append(label)


def test_program():
    print("\n[program]")
    check("rooms defined", len(ROOMS) > 0)
    check("envelope has positive area", ENVELOPE_AREA > 0)
    check("room program fits in envelope",
          TOTAL_ROOM_AREA <= ENVELOPE_AREA,
          f"({TOTAL_ROOM_AREA:.0f} sqft of rooms vs {ENVELOPE_AREA:.0f} sqft envelope)")
    check("exactly one entry room",
          sum(1 for r in ROOMS if r.is_entry) == 1)


def test_genome():
    print("\n[genome]")
    n = genome_length()
    check("genome length is 3 per room", n == GENES_PER_ROOM * len(ROOMS))

    mid = [0.5] * n
    placed = decode(mid)
    check("decode returns one rect per room", len(placed) == len(ROOMS))

    # decoded rectangles must preserve the programmed area
    areas_ok = all(
        abs(p.w * p.h - p.room.area) < 1e-6 for p in placed.values()
    )
    check("decoded rects preserve programmed area", areas_ok)

    # extreme genomes must still land inside the envelope
    for label, g in [("all-zeros", [0.0] * n), ("all-ones", [1.0] * n)]:
        placed = decode(g)
        inside = all(
            p.x >= -1e-6 and p.y >= -1e-6
            and p.x + p.w <= ENVELOPE.width + 1e-6
            and p.y + p.h <= ENVELOPE.depth + 1e-6
            for p in placed.values()
        )
        check(f"{label} genome stays in envelope", inside)


def test_fitness():
    print("\n[fitness]")
    n = genome_length()
    score = evaluate([0.5] * n)
    check("evaluate returns a 1-tuple", isinstance(score, tuple) and len(score) == 1)
    check("score is finite and non-negative", score[0] >= 0)

    parts = score_breakdown([0.5] * n)
    total = sum(parts.values())
    check("breakdown sums to total score",
          abs(total - score[0]) < 1e-6,
          f"(sum={total:.4f} vs total={score[0]:.4f})")

    # a fully-stacked layout (every room at the same corner) must score worse
    # than the spread-out midpoint layout -- sanity check that overlap hurts
    stacked = evaluate([0.0] * n)[0]
    check("overlapping layout scores worse than spread layout",
          stacked > score[0],
          f"(stacked={stacked:.0f}, spread={score[0]:.0f})")


def test_ga_short_run():
    print("\n[ga]")
    best0, best_final, logbook = ga.run(
        pop_size=30, n_generations=15, seed=1, verbose=False
    )
    s0, s1 = evaluate(best0)[0], evaluate(best_final)[0]
    check("GA returns genomes of correct length",
          len(best0) == genome_length() and len(best_final) == genome_length())
    check("all genes stay within [0, 1]",
          all(0.0 <= g <= 1.0 for g in best_final))
    check("logbook recorded every generation", len(logbook) == 16)
    check("evolution improved the score", s1 < s0, f"({s0:.0f} -> {s1:.0f})")
    return best0, best_final, logbook


def test_visualization(best0, best_final, logbook):
    print("\n[visualize]")
    with tempfile.TemporaryDirectory() as tmp:
        p1 = os.path.join(tmp, "layout.png")
        p2 = os.path.join(tmp, "conv.png")
        plot_before_after(best0, best_final, p1)
        plot_convergence(logbook, p2)
        check("layout image written", os.path.exists(p1) and os.path.getsize(p1) > 0)
        check("convergence image written", os.path.exists(p2) and os.path.getsize(p2) > 0)


def main():
    print("Running floor plan optimizer smoke tests...")
    test_program()
    test_genome()
    test_fitness()
    best0, best_final, logbook = test_ga_short_run()
    test_visualization(best0, best_final, logbook)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED: {', '.join(FAILURES)}")
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
