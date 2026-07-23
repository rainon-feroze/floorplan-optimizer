"""
Fast smoke test -- verifies the whole pipeline runs end to end without
actually doing a full-length optimization.

Run locally with:   python3 smoke_test.py
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


def test_spec_parsing():
    print("\n[spec parsing]")
    from floorplan.program import parse_spec

    # area mode
    env, rooms = parse_spec("lot 40x30; living 300 exterior; entry 50 entry")
    check("area mode: lot parsed", env.width == 40 and env.depth == 30)
    check("area mode: area set, dims free",
          rooms[0].area == 300 and not rooms[0].has_fixed_dims)

    # dimension mode
    env, rooms = parse_spec("lot 40x30; living 12x20 exterior; entry 5x10 entry")
    living = rooms[0]
    check("dimension mode: dims locked", living.has_fixed_dims)
    check("dimension mode: area derived from dims", living.area == 240)
    check("dimension mode: width/height preserved",
          living.fixed_w == 12 and living.fixed_h == 20)

    # flags
    check("exterior flag parsed", living.wants_exterior)
    check("entry flag parsed", rooms[1].is_entry)
    _, r = parse_spec("lot 40x30; hall 4x20 min=3 entry")
    check("min= flag parsed", r[0].min_dim == 3)

    # comments and blank lines ignored
    _, r = parse_spec("lot 40x30\n# a comment\n\nliving 200 entry  # trailing\n")
    check("comments and blanks ignored", len(r) == 1 and r[0].area == 200)

    # regression: a semicolon inside a comment must not leak a bogus line
    _, r = parse_spec("# note: works well; but watch coverage\n"
                      "lot 40x30\nliving 200 entry\n")
    check("semicolon inside a comment is ignored", len(r) == 1)

    # semicolons still separate real entries
    _, r = parse_spec("lot 40x30; living 200 entry; den 100")
    check("semicolon separates entries", len(r) == 2)

    # errors
    def expect_error(label, spec):
        try:
            parse_spec(spec)
            check(label, False, "(expected an error, got none)")
        except ValueError:
            check(label, True)

    expect_error("rejects missing lot line", "living 200 entry")
    expect_error("rejects no rooms", "lot 40x30")
    expect_error("rejects zero entry rooms", "lot 40x30; living 200")
    expect_error("rejects two entry rooms",
                 "lot 40x30; living 200 entry; den 100 entry")
    expect_error("rejects rooms bigger than the lot",
                 "lot 20x20; living 900 entry")
    expect_error("rejects a room too large to fit",
                 "lot 20x20; living 30x5 entry")
    expect_error("rejects negative size", "lot 40x30; living -50 entry")
    expect_error("rejects unknown flag", "lot 40x30; living 200 entry sparkly")


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
    test_spec_parsing()
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
