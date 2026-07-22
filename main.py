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
from floorplan.visualize import plot_before_after, plot_convergence

# Seed can be overridden via env var (used by the regenerate-figures workflow).
SEED = int(os.environ.get("FLOORPLAN_SEED", "42"))


def main():
    best_gen0, best_final, logbook = ga.run(
        pop_size=300,
        n_generations=400,
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

    plot_before_after(best_gen0, best_final, "layout_before_after.png",
                       score_before=score0, score_after=score1)
    plot_convergence(logbook, "ga_convergence.png")
    print("\nSaved layout_before_after.png and ga_convergence.png")


if __name__ == "__main__":
    main()
