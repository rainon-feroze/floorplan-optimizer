"""
Run the generative floor plan optimizer end-to-end:
  1. build a random initial population (generation 0)
  2. evolve it with a genetic algorithm
  3. print an itemized fitness breakdown for best gen-0 vs best final
  4. save before/after layout image + convergence plot
"""
import os

from floorplan import ga
from floorplan.fitness import evaluate, score_breakdown
from floorplan.program import ENVELOPE, ROOMS, TOTAL_ROOM_AREA, ENVELOPE_AREA
from floorplan.visualize import plot_before_after, plot_convergence, plot_final_plan

# Both can be overridden via env vars, which is how the workflow forms pass
# their inputs in without any code editing.
SEED = int(os.environ.get("FLOORPLAN_SEED", "42"))
GENERATIONS = int(os.environ.get("FLOORPLAN_GENERATIONS", "400"))


def main():
    best_gen0, best_final, logbook = ga.run(
        pop_size=300,
        n_generations=GENERATIONS,
        seed=SEED,
    )

    score0 = evaluate(best_gen0)[0]
    score1 = evaluate(best_final)[0]

    print("\n=== Best genome, generation 0 ===")
    print(f"Total score: {score0:.2f}")
    for k, v in score_breakdown(best_gen0).items():
        print(f"  {k:14s} {v:8.2f}")

    print("\n=== Best genome, final generation ===")
    print(f"Total score: {score1:.2f}")
    for k, v in score_breakdown(best_final).items():
        print(f"  {k:14s} {v:8.2f}")

    # Also write the breakdown to a file so the workflow can show it on the
    # run summary page without re-parsing the log.
    with open("score.txt", "w") as f:
        f.write(f"{'total':16s}{score1:10,.0f}\n")
        f.write("-" * 26 + "\n")
        for k, v in score_breakdown(best_final).items():
            f.write(f"{k:16s}{v:10,.0f}\n")

    plot_final_plan(
        best_final, "floorplan.png",
        title=f"{ENVELOPE.width:g}′ × {ENVELOPE.depth:g}′ lot  ·  {len(ROOMS)} rooms",
        subtitle=f"{TOTAL_ROOM_AREA:.0f} sf of {ENVELOPE_AREA:.0f} sf "
                 f"({TOTAL_ROOM_AREA / ENVELOPE_AREA:.0%} coverage)  ·  "
                 f"score {score1:,.0f}",
    )
    plot_before_after(best_gen0, best_final, "layout_before_after.png",
                       score_before=score0, score_after=score1)
    plot_convergence(logbook, "ga_convergence.png")
    print("\nSaved floorplan.png, layout_before_after.png and ga_convergence.png")


if __name__ == "__main__":
    main()
