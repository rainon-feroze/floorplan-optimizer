"""
Records the best layout at intervals during evolution and renders an
animated GIF showing the plan organizing itself over time.

Run:  python make_animation.py
Out:  evolution.gif
"""
import os
import random

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.animation import FuncAnimation, PillowWriter
from deap import tools

from floorplan import ga
from floorplan.genome import decode
from floorplan.program import ENVELOPE
from floorplan.fitness import evaluate

SNAPSHOT_EVERY = 4      # record best individual every N generations
N_GENERATIONS = 400
POP_SIZE = 300
SEED = 7
HOLD_FRAMES = 12        # freeze on the final layout at the end

CMAP = plt.get_cmap("tab20")


def evolve_with_snapshots():
    """Same GA as ga.run(), but records the best genome periodically."""
    random.seed(SEED)
    toolbox = ga.toolbox
    pop = toolbox.population(n=POP_SIZE)

    for ind, fit in zip(pop, map(toolbox.evaluate, pop)):
        ind.fitness.values = fit

    snapshots = [(0, list(tools.selBest(pop, 1)[0]))]

    for gen in range(1, N_GENERATIONS + 1):
        offspring = list(map(toolbox.clone, toolbox.select(pop, len(pop))))

        for c1, c2 in zip(offspring[::2], offspring[1::2]):
            if random.random() < 0.6:
                toolbox.mate(c1, c2)
                ga._clip(c1)
                ga._clip(c2)
                del c1.fitness.values
                del c2.fitness.values

        for mutant in offspring:
            if random.random() < 0.3:
                toolbox.mutate(mutant)
                ga._clip(mutant)
                del mutant.fitness.values

        invalid = [ind for ind in offspring if not ind.fitness.valid]
        for ind, fit in zip(invalid, map(toolbox.evaluate, invalid)):
            ind.fitness.values = fit

        offspring[0] = toolbox.clone(tools.selBest(pop, 1)[0])
        pop[:] = offspring

        if gen % SNAPSHOT_EVERY == 0 or gen == N_GENERATIONS:
            snapshots.append((gen, list(tools.selBest(pop, 1)[0])))

    return snapshots


def render(snapshots, out_path="evolution.gif"):
    ex0, ey0, ex1, ey1 = ENVELOPE.bounds

    fig, ax = plt.subplots(figsize=(7, 5.6))
    fig.patch.set_facecolor("white")

    # stable color per room name
    first_layout = decode(snapshots[0][1])
    colors = {name: CMAP(i % 20) for i, name in enumerate(first_layout)}

    frames = snapshots + [snapshots[-1]] * HOLD_FRAMES

    def draw(frame_idx):
        gen, genome = frames[frame_idx]
        ax.clear()
        ax.set_xlim(ex0 - 2, ex1 + 2)
        ax.set_ylim(ey0 - 2, ey1 + 4)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

        ax.add_patch(patches.Rectangle((ex0, ey0), ex1 - ex0, ey1 - ey0,
                                        fill=False, edgecolor="black", linewidth=2.5))

        placed = decode(genome)
        for name, p in placed.items():
            ax.add_patch(patches.Rectangle(
                (p.x, p.y), p.w, p.h,
                facecolor=colors[name], edgecolor="black",
                alpha=0.8, linewidth=1.2))
            ax.text(p.x + p.w / 2, p.y + p.h / 2, name,
                    ha="center", va="center", fontsize=6.5)

        score = evaluate(genome)[0]
        ax.set_title(f"Generation {gen}     penalty score: {score:,.0f}",
                     fontsize=13, pad=12, family="monospace")

    anim = FuncAnimation(fig, draw, frames=len(frames), interval=120)
    anim.save(out_path, writer=PillowWriter(fps=8))
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    print("Evolving and recording snapshots...")
    snaps = evolve_with_snapshots()
    print(f"Captured {len(snaps)} snapshots. Rendering GIF...")
    path = render(snaps)
    size_mb = os.path.getsize(path) / 1e6
    print(f"Saved {path} ({size_mb:.1f} MB)")
