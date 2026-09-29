"""Figure 3: where the squared deviation lives (concentration curves, small multiples)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator

import sources
import style as S


def pct(v, _=None) -> str:
    return f"{v * 100:g}%"


def draw() -> dict:
    cur, gauss, top1 = sources.f3()
    fig, axes = plt.subplots(2, 4, figsize=(S.WIDTH, 92 * S.MM), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.075, right=0.99, bottom=0.12, top=0.93, wspace=0.12, hspace=0.42)
    flat = axes.ravel()
    g1 = float(np.interp(-2, np.log10(gauss.top_fraction), gauss.cumulative_share_sq_dev))
    for ax, fmt in zip(flat, S.FORMATS, strict=False):
        d = cur[cur.format == fmt]
        c = S.FORMAT_COLOR[fmt]
        ax.plot(gauss.top_fraction, gauss.cumulative_share_sq_dev, color=S.INK3, lw=0.8, dashes=(2.2, 1.6), zorder=1)
        ax.fill_between(d.top_fraction, d.lo, d.hi, color=c, alpha=0.22, lw=0, zorder=2)
        ax.plot(d.top_fraction, d["median"], color=c, lw=1.3, zorder=3)
        ax.axvline(0.01, color=S.RULE, lw=S.LW_THIN, zorder=0)
        t1 = top1[fmt]  # exact frozen statistic (core conc_top0.01, median over pairings)
        ax.plot(0.01, t1, "o", ms=2.8, mfc=c, mec="white", mew=0.5, zorder=4)
        ax.text(0.0125, t1 - 0.05, f"top 1%: {t1 * 100:.0f}%", fontsize=S.SMALL, ha="left", va="top",
                color=S.INK, zorder=5, bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none", alpha=0.85))
        ax.set_title(S.FORMAT_SHORT[fmt], fontsize=S.BASE, loc="left", pad=3, color=S.INK)
        ax.set_xscale("log")
        ax.xaxis.set_major_locator(FixedLocator([1e-4, 1e-3, 1e-2, 1e-1, 1]))
        ax.tick_params(axis="x", labelbottom=ax in (axes[1, 0], axes[1, 1], axes[1, 2], axes[0, 3]))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _=None: "" if v in (1e-4,) else pct(v)))
        ax.xaxis.set_minor_locator(NullLocator())
        ax.set_xlim(1e-4, 1)
        ax.set_ylim(0, 1.02)
        ax.yaxis.set_major_locator(FixedLocator([0, 0.25, 0.5, 0.75, 1.0]))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _=None: f"{v * 100:.0f}%"))
    # spare slot: legend and how to read
    lg = flat[-1]
    lg.axis("off")
    handles = [plt.Line2D([], [], color=S.INK2, lw=1.3, label="median over pairings p1–p3"),
               plt.Rectangle((0, 0), 1, 1, fc=S.INK2, alpha=0.22, label="range over pairings"),
               plt.Line2D([], [], color=S.INK3, lw=0.8, dashes=(2.2, 1.6), label=f"Gaussian reference\n(top 1% carries {g1 * 100:.1f}%)")]
    lg.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, 1.05), fontsize=S.SMALL, handlelength=1.8, labelspacing=0.7)
    lg.text(0.0, 0.18, "Blocks are ranked by |D − mean|,\nlargest first. A curve reaching 1.0\nat 10% means 90% of blocks add\nnothing (D = 0).",
            transform=lg.transAxes, fontsize=S.TINY, color=S.INK2, va="bottom", linespacing=1.25)
    fig.supxlabel("share of matched blocks, most extreme first (log scale)", fontsize=S.BASE, y=0.02)
    fig.supylabel("cumulative share of squared deviation", fontsize=S.BASE, x=0.012)
    return S.save(fig, "figure3_variance_concentration")
