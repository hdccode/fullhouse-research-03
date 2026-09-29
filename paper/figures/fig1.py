"""Figure 1: played hands needed vs the true edge.

Design notes
* Required hands scale exactly as Δ⁻² for a fixed pairing, so each format is a straight line of
  slope −2 and every ratio between formats is the same at every edge. The spreads (61×, 4.8×)
  are therefore annotated once, on brackets in the right gutter, spanning the line ends.
* Per-pairing ranges are shown in Figure 2b at 1 BB/100. Seven translucent p1–p3 envelopes
  stacked into an unreadable wash here, because the curves are parallel (see ARCHITECTURE.md).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

import sources
import style as S


def draw() -> dict:
    df, spread = sources.f1()
    fig = plt.figure(figsize=(S.WIDTH, 78 * S.MM))
    ax = fig.add_axes([0.085, 0.14, 0.60, 0.83])
    xs = np.array(sources.DELTAS)
    for y in (1e4, 1e5, 1e6, 1e7, 1e8, 1e9):
        ax.axhline(y, color="#ecebe7", lw=0.4, zorder=0)
    S.ref_line(ax, 1.0, "x", color=S.RULE, dashed=False, lw=S.LW_THIN)
    ends = {}
    for fmt in S.FORMATS:
        med = df[df.format == fmt].groupby("delta").hands.median().loc[xs]
        ax.plot(xs, med, color=S.FORMAT_COLOR[fmt], lw=1.4, zorder=3)
        ax.plot(1.0, med.loc[1.0], "o", ms=2.8, mfc=S.FORMAT_COLOR[fmt], mec="white", mew=0.5, zorder=4)
        ends[fmt] = med.iloc[-1]
    S.log_axis(ax, "x", xs, formatter=lambda v, _=None: f"{v:g}")
    S.log_axis(ax, "y", [1e4, 1e5, 1e6, 1e7, 1e8, 1e9])
    ax.set_xlim(0.235, 5.3)
    ax.set_ylim(8e3, 1.6e9)
    ax.set_xlabel("true edge between the two candidates (BB/100, log scale)")
    ax.set_ylabel("played hands for 80% power (log scale)")
    ax.text(1.0, 1.3e9, "1 BB/100 ", fontsize=S.TINY, color=S.INK2, ha="right", va="top")

    # direct labels with leader lines (deterministic 1-D spacing in log10 units)
    y0 = np.log10([ends[f] for f in S.FORMATS])
    ylab = S.spread_labels(y0, min_gap=0.165)
    for f, ya, yl in zip(S.FORMATS, y0, ylab, strict=True):
        ax.plot([5.0, 5.5, 5.95], [10 ** ya, 10 ** ya, 10 ** yl], color=S.FORMAT_COLOR[f], lw=0.6, clip_on=False, zorder=2)
        ax.text(6.15, 10 ** yl, S.FORMAT_SHORT[f], va="center", ha="left", fontsize=S.BASE, color=S.INK, clip_on=False)

    # spreads: brackets in the gutter spanning the true line ends (ratios identical at every edge)
    ends_s = {f: ends[f] for f in S.FORMATS}
    all_lo, all_hi = min(ends_s.values()), max(ends_s.values())
    h100 = [ends_s[f] for f in ("NLHE 4-max", "NLHE 6-max", "Crazy Pineapple", "PLO", "Bomb Pot")]
    inner = (10.6, min(h100), max(h100), f"{spread['100bb']:.1f}×", "among 100BB formats")
    outer = (13.6, all_lo, all_hi, f"{spread['full']:.0f}×", "across all formats")
    xl = 15.0
    for x, lo, hi, big, small in (inner, outer):
        for seg in (([x, x], [lo, hi]), ([x / 1.04, x], [lo, lo]), ([x / 1.04, x], [hi, hi])):
            ax.plot(*seg, color=S.INK, lw=0.7, clip_on=False, solid_capstyle="butt", zorder=5)
        ym = np.sqrt(lo * hi)
        if x == inner[0]:  # leader from the inner bracket, across the outer one, to its label
            ax.plot([x, xl * 0.985], [ym, ym], color=S.INK2, lw=0.45, clip_on=False, zorder=4)
        ax.text(xl, ym, big, ha="left", va="bottom", fontsize=S.BASE + 1, fontweight="bold", clip_on=False)
        ax.text(xl, ym / 1.06, small, ha="left", va="top", fontsize=S.TINY, color=S.INK2, clip_on=False)
    ax.legend(handles=[plt.Line2D([], [], color=S.INK2, lw=1.4, label="median over pairings p1–p3\n(per-pairing values: Fig. 2)")],
              loc="lower left", fontsize=S.SMALL, handlelength=1.6, borderaxespad=0.4)
    return S.save(fig, "figure1_sample_complexity")
