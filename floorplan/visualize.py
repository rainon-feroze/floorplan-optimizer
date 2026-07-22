import matplotlib.pyplot as plt
import matplotlib.patches as patches

from .program import ENVELOPE
from .genome import decode

CMAP = plt.get_cmap("tab20")


def _draw_layout(ax, genome, title):
    placed = decode(genome)
    ex0, ey0, ex1, ey1 = ENVELOPE.bounds

    ax.set_xlim(ex0 - 2, ex1 + 2)
    ax.set_ylim(ey0 - 2, ey1 + 2)
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=12)

    # envelope outline
    ax.add_patch(patches.Rectangle((ex0, ey0), ex1 - ex0, ey1 - ey0,
                                    fill=False, edgecolor="black", linewidth=2))

    for i, (name, p) in enumerate(placed.items()):
        color = CMAP(i % 20)
        ax.add_patch(patches.Rectangle((p.x, p.y), p.w, p.h,
                                        facecolor=color, edgecolor="black",
                                        alpha=0.75, linewidth=1))
        ax.text(p.x + p.w / 2, p.y + p.h / 2, f"{name}\n{p.room.area:.0f}sf",
                ha="center", va="center", fontsize=7)

    ax.set_xticks([])
    ax.set_yticks([])


def plot_before_after(genome_before, genome_after, out_path, score_before=None, score_after=None):
    fig, axes = plt.subplots(1, 2, figsize=(13, 6.5))
    t1 = "Generation 0 (random)" + (f"  |  score={score_before:.1f}" if score_before is not None else "")
    t2 = "Final (evolved)" + (f"  |  score={score_after:.1f}" if score_after is not None else "")
    _draw_layout(axes[0], genome_before, t1)
    _draw_layout(axes[1], genome_after, t2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_convergence(logbook, out_path):
    gens = logbook.select("gen")
    mins = logbook.select("min")
    avgs = logbook.select("avg")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(gens, mins, label="best (min penalty)", linewidth=2)
    ax.plot(gens, avgs, label="population avg", linewidth=1, alpha=0.7)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Fitness (penalty score, lower = better)")
    ax.set_title("GA Convergence")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
