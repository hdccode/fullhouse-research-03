"""Figure 2: the same evaluations measured in three units (1 BB/100, 80% power)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

import sources
import style as S

PANELS = [("independent blocks", "a", "independent matched blocks", [1e4, 1e5, 1e6, 1e7], S.fmt_count),
          ("played hands", "b", "played hands", [1e5, 1e6, 1e7, 1e8], S.fmt_count),
          ("wall-clock hours (8 workers, measured)", "c", "measured wall-clock, 8 workers",
           [1 / 360, 1 / 60, 1 / 6, 1, 10, 100], S.fmt_hours)]


def draw() -> dict:
    df, ratios = sources.f2()
    order = (df[(df.metric == "played hands") & (df.role == "median")].sort_values("value").format.tolist())
    ypos = {f: i for i, f in enumerate(order)}  # smallest burden at the bottom, as in Fig. 1
    fig, axes = plt.subplots(1, 3, figsize=(S.WIDTH, 62 * S.MM), sharey=True)
    fig.subplots_adjust(left=0.118, right=0.985, bottom=0.25, top=0.88, wspace=0.14)
    for ax, (metric, letter, title, ticks, fmt) in zip(axes, PANELS, strict=True):
        g = df[df.metric == metric]
        for f in order:
            h = g[g.format == f]
            pts = h[h.role != "median"].set_index("role").value
            med = float(h[h.role == "median"].value.iloc[0])
            y, c = ypos[f], S.FORMAT_COLOR[f]
            ax.plot([pts.min(), pts.max()], [y, y], color=c, lw=0.9, alpha=0.55, solid_capstyle="butt", zorder=1)
            ax.plot([med, med], [y - 0.28, y + 0.28], color=S.INK, lw=1.1, solid_capstyle="butt", zorder=2)
            for r in S.ROLES:
                ax.plot(pts[r], y, S.ROLE_MARKER[r], ms=S.ROLE_MS[r], mfc=c, mec="white", mew=0.45, zorder=3)
        S.log_axis(ax, "x", ticks, formatter=fmt)
        lo, hi = g.value.min(), g.value.max()
        ax.set_xlim(lo / 1.9, hi * 1.9)
        ax.set_ylim(-1.45, len(order) - 0.3)  # strip below the AoF row for the ratio note
        ax.spines["left"].set_visible(ax is axes[0])
        ax.tick_params(axis="y", length=0)
        S.panel_title(ax, letter, title)
        # the AoF row sits far left in every panel, so the lower-right corner is free
        ax.text(0.985, 0.015, f"largest / smallest median: {ratios[metric]:.0f}×", transform=ax.transAxes,
                ha="right", va="bottom", fontsize=S.SMALL, color=S.INK2)
        ax.set_xlabel({"a": "blocks for 80% power (log scale)", "b": "hands for 80% power (log scale)",
                       "c": "time for 80% power (log scale;\nimplementation-specific)"}[letter], linespacing=1.1)
    axes[0].set_yticks(range(len(order)), [S.FORMAT_SHORT[f] for f in order])
    handles = S.role_handles() + [plt.Line2D([], [], color=S.INK, lw=1.1, marker="|", ls="none", ms=6, mew=1.1,
                                             label="median over pairings")]
    fig.legend(handles=handles, loc="lower center", ncol=4, bbox_to_anchor=(0.55, 0.0), fontsize=S.SMALL,
               handletextpad=0.3, columnspacing=1.4)
    return S.save(fig, "figure2_cost_metrics")
