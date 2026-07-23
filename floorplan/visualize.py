import matplotlib.pyplot as plt
import matplotlib.patches as patches

from .program import ENVELOPE, FENG_SHUI
from .genome import decode

CMAP = plt.get_cmap("tab20")


def _draw_bagua(ax, placed):
    """Faint 3x3 bagua grid, oriented to the entry wall, drawn under the
    rooms so it reads as a reference overlay rather than architecture."""
    from . import feng_shui as fs

    wall = fs.entry_wall(placed)
    if wall is None:
        return

    ex0, ey0, ex1, ey1 = ENVELOPE.bounds
    w, h = ex1 - ex0, ey1 - ey0

    for i in (1, 2):
        ax.plot([ex0 + w * i / 3] * 2, [ey0, ey1],
                color="0.75", lw=0.8, ls=(0, (4, 4)), zorder=0)
        ax.plot([ex0, ex1], [ey0 + h * i / 3] * 2,
                color="0.75", lw=0.8, ls=(0, (4, 4)), zorder=0)

    for row in range(3):
        for col in range(3):
            # find the absolute cell whose (row, col) matches, given orientation
            for ar in range(3):
                for ac in range(3):
                    px = ex0 + w * (ac + 0.5) / 3
                    py = ey0 + h * (ar + 0.5) / 3
                    if fs._zone_of(px, py, wall) == (row, col):
                        ax.text(px, ey0 + h * (ar + 0.92) / 3,
                                fs.BAGUA_NAMES[(row, col)],
                                ha="center", va="top", fontsize=6,
                                color="0.6", style="italic", zorder=0)


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


def plot_final_plan(genome, out_path, title="Floor Plan", subtitle=None):
    """A clean drawing of one finished layout, with each room's actual
    dimensions labeled. This is the deliverable -- distinct from the
    before/after comparison, which exists to show the GA working."""
    placed = decode(genome)
    ex0, ey0, ex1, ey1 = ENVELOPE.bounds
    ew, eh = ex1 - ex0, ey1 - ey0

    scale = 0.32
    fig, ax = plt.subplots(figsize=(max(ew * scale, 7), max(eh * scale, 5.5)))
    fig.patch.set_facecolor("white")

    ax.set_xlim(ex0 - 3, ex1 + 3)
    ax.set_ylim(ey0 - 3, ey1 + 5)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    # building envelope
    ax.add_patch(patches.Rectangle((ex0, ey0), ew, eh,
                                    fill=False, edgecolor="black", linewidth=3))

    if FENG_SHUI:
        _draw_bagua(ax, placed)

    for i, (name, p) in enumerate(placed.items()):
        ax.add_patch(patches.Rectangle(
            (p.x, p.y), p.w, p.h,
            facecolor=CMAP(i % 20), edgecolor="black",
            alpha=0.8, linewidth=1.4))

        cx, cy = p.x + p.w / 2, p.y + p.h / 2

        # Scale text to the room so small rooms don't overflow. The limiting
        # factor is width for the name and height for the stacked detail line.
        name_size = max(5.5, min(10.0, p.w * 0.9, p.h * 1.6))
        detail_size = name_size * 0.78
        # Only draw the dimension/area line if there's vertical room for it.
        show_detail = p.h > 5.0 and p.w > 4.5

        if show_detail:
            ax.text(cx, cy + p.h * 0.11, name, ha="center", va="center",
                    fontsize=name_size, weight="bold")
            ax.text(cx, cy - p.h * 0.15,
                    f"{p.w:.1f}′ × {p.h:.1f}′\n{p.w * p.h:.0f} sf",
                    ha="center", va="center", fontsize=detail_size,
                    linespacing=1.4)
        else:
            ax.text(cx, cy, name, ha="center", va="center",
                    fontsize=name_size, weight="bold")

    # overall lot dimensions along the bottom and left edges
    ax.annotate("", xy=(ex0, ey0 - 1.6), xytext=(ex1, ey0 - 1.6),
                arrowprops=dict(arrowstyle="<->", lw=1, color="dimgray"))
    ax.text((ex0 + ex1) / 2, ey0 - 2.6, f"{ew:.0f}′",
            ha="center", va="top", fontsize=9, color="dimgray")

    ax.annotate("", xy=(ex0 - 1.6, ey0), xytext=(ex0 - 1.6, ey1),
                arrowprops=dict(arrowstyle="<->", lw=1, color="dimgray"))
    ax.text(ex0 - 2.6, (ey0 + ey1) / 2, f"{eh:.0f}′",
            ha="right", va="center", fontsize=9, color="dimgray", rotation=90)

    full_title = title
    if subtitle:
        full_title += f"\n{subtitle}"
    ax.set_title(full_title, fontsize=13, pad=14)

    fig.tight_layout()
    fig.savefig(out_path, dpi=160, facecolor="white")
    plt.close(fig)
    return out_path


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
