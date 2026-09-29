"""Figure 6: sequential monitoring (RQ7): false conclusions under the null, and one real stream.

Design notes
* Panel a keeps one linear percent scale for all methods (no broken axis) and adds a zoomed
  strip underneath for the two valid methods, whose rates (2.4-5%) would otherwise sit on the
  floor next to naive peeking's 45-64%.
* Panel b clips the y range: the confidence sequence is wider than ±60 BB/100 before ~1k blocks.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

import sources
import style as S

GROUPS = ["NLHE 6-max p1 (heavy)", "Crazy Pineapple p2", "PLO p3", "Normal", "Student t3", "Real orderings of NLHE 6-max p1"]
GROUP_LABEL = ["NLHE\n6-max p1", "Crazy\nPineapple p2", "PLO p3", "Normal", "Student t3", "1,000 real\norderings"]
GROUP_KIND = ["heavy", "moderate", "mild", "", "", ""]
XPOS = [0, 1, 2, 3, 4, 5.45]  # visual gap before the real-ordering group
DODGE = {"fixed-N (one look)": -0.24, "naive peeking": 0.0, "confidence sequence": 0.24}
PEEK = S.METHOD_COLOR["naive peeking"]
CS = S.METHOD_COLOR["confidence sequence"]
FIX = S.METHOD_COLOR["fixed-N (one look)"]


def _points(ax, a, methods) -> None:
    for gi, grp in enumerate(GROUPS):
        for m in methods:
            r = a[(a.group == grp) & (a.method == m)].iloc[0]
            x = XPOS[gi] + DODGE[m]
            ax.plot([x, x], [r.wilson_lo, r.wilson_hi], color=S.METHOD_COLOR[m], lw=0.9, solid_capstyle="butt", zorder=2)
            ax.plot(x, r.rate, S.METHOD_MARKER[m], ms=S.METHOD_MS[m], mfc=S.METHOD_COLOR[m], mec="white", mew=0.45, zorder=3)


def draw() -> dict:
    a, tr, mk, info = sources.f6()
    fig = plt.figure(figsize=(S.WIDTH, 82 * S.MM))
    ax_top = fig.add_axes([0.07, 0.43, 0.40, 0.49])
    ax_zoom = fig.add_axes([0.07, 0.17, 0.40, 0.19], sharex=ax_top)
    axb = fig.add_axes([0.575, 0.17, 0.405, 0.75])
    pct = FuncFormatter(lambda v, _=None: f"{v * 100:g}%")

    # ---------------- a (top): all three methods, one linear scale
    _points(ax_top, a, S.METHODS)
    S.ref_line(ax_top, 0.05, "y", color=S.INK3, lw=0.6)
    ax_top.set_ylim(0, 0.72)
    ax_top.set_yticks([0, 0.2, 0.4, 0.6])
    ax_top.yaxis.set_major_formatter(pct)
    ax_top.tick_params(axis="x", labelbottom=False, length=0)
    ax_top.set_ylabel("streams with a false\nconclusion (ever)", linespacing=1.15)
    peek = a[a.method == "naive peeking"]
    iid = peek[peek.group != GROUPS[-1]].rate
    ax_top.text(2.0, 0.705, f"naive peeking: {iid.min() * 100:.0f}–{iid.max() * 100:.0f}% of null streams",
                ha="center", va="top", fontsize=S.SMALL, color=S.INK)
    S.panel_title(ax_top, "a", "false conclusions when the true edge is zero", y=1.05)
    # ---------------- a (zoom): the two valid methods
    _points(ax_zoom, a, ["fixed-N (one look)", "confidence sequence"])
    S.ref_line(ax_zoom, 0.05, "y", color=S.INK3, lw=0.6)
    ax_zoom.text(5.95, 0.051, "5%", fontsize=S.TINY, color=S.INK2, va="bottom", ha="right")
    ax_zoom.set_ylim(0, 0.07)
    ax_zoom.set_yticks([0, 0.05])
    ax_zoom.yaxis.set_major_formatter(pct)
    ax_zoom.set_ylabel("zoom", fontsize=S.SMALL, color=S.INK2)
    ax_zoom.set_xticks(XPOS, GROUP_LABEL, fontsize=S.TINY, linespacing=1.05)
    ax_zoom.tick_params(axis="x", length=0, pad=2)
    ax_zoom.set_xlim(-0.55, 6.0)
    for axx in (ax_top, ax_zoom):
        axx.axvline(4.73, color=S.RULE, lw=0.5, zorder=0)
    ax_top.text(2.0, -0.02, "IID resampled / synthetic streams, 2,000 each", transform=ax_top.get_xaxis_transform(),
                fontsize=S.TINY, color=S.INK2, ha="center", va="top")
    handles = [plt.Line2D([], [], ls="none", marker=S.METHOD_MARKER[m], ms=S.METHOD_MS[m], mfc=S.METHOD_COLOR[m], mec="white",
                          mew=0.4, label=m) for m in S.METHODS]
    ax_top.legend(handles=handles, loc="center left", bbox_to_anchor=(0.0, 0.52), fontsize=S.SMALL, handletextpad=0.3,
                  labelspacing=0.35, title="bars: Wilson 95% CI", title_fontsize=S.TINY, alignment="left")

    # ---------------- b: the flagship comparison read in its real order
    x = tr.blocks.to_numpy()
    lim = 60
    axb.axhline(0, color=S.INK, lw=0.6, zorder=1)
    axb.fill_between(x, np.clip(tr.cs_lo, -lim * 3, None), np.clip(tr.cs_hi, None, lim * 3), color="#d9d8d3", lw=0, zorder=2,
                     label="confidence sequence (valid at every look)")
    axb.fill_between(x, tr.t_lo, tr.t_hi, color=PEEK, alpha=0.22, lw=0, zorder=3, label="ordinary 95% CI (valid at one look)")
    axb.plot(x, tr.mean_bb100, color=S.INK, lw=1.0, zorder=4, label="running estimate")
    stop = mk[mk.marker == "naive peeking stop"].iloc[0]
    axb.plot([stop.blocks, stop.blocks], [stop.lo, stop.hi], color=PEEK, lw=1.1, zorder=5, solid_capstyle="butt")
    axb.plot(stop.blocks, stop.mean_bb100, S.METHOD_MARKER["naive peeking"], ms=S.METHOD_MS["naive peeking"] * 1.2, mfc=PEEK,
             mec="white", mew=0.5, zorder=6)
    axb.annotate(S.minus(f"naive peeking stops at block {int(stop.blocks)}:\n{stop.mean_bb100:+.1f} BB/100 [{stop.lo:+.1f}, {stop.hi:+.1f}]\n")
                 + "declares the wrong agent better", xy=(stop.blocks * 1.08, stop.mean_bb100), xytext=(330, -47),
                 fontsize=S.SMALL, color=S.INK, va="center", ha="left", linespacing=1.15, zorder=8,
                 arrowprops=dict(arrowstyle="-", color=S.INK2, lw=0.5, shrinkA=1, shrinkB=2))
    fx = mk[mk.marker == "fixed-N single look at 250k"].iloc[0]
    cs = mk[mk.marker == "confidence sequence at 250k"].iloc[0]
    # zoom inset on the final stretch, placed in the empty lower-right region of the panel
    ins = axb.inset_axes([0.60, 0.07, 0.37, 0.36])
    tail = tr[tr.blocks >= 30000]
    ins.fill_between(tail.blocks, tail.cs_lo, tail.cs_hi, color="#d9d8d3", lw=0, zorder=1)
    ins.fill_between(tail.blocks, tail.t_lo, tail.t_hi, color=PEEK, alpha=0.22, lw=0, zorder=2)
    ins.plot(tail.blocks, tail.mean_bb100, color=S.INK, lw=0.9, zorder=3)
    ins.axhline(0, color=S.INK, lw=0.5, zorder=0)
    xe_fix, xe_cs = 250000 * 1.10, 250000 * 1.24
    for xe, row, m in ((xe_fix, fx, "fixed-N (one look)"), (xe_cs, cs, "confidence sequence")):
        ins.plot([xe, xe], [row.lo, row.hi], color=S.METHOD_COLOR[m], lw=1.2, solid_capstyle="butt", clip_on=False, zorder=4)
        ins.plot(xe, row.mean_bb100, S.METHOD_MARKER[m], ms=S.METHOD_MS[m], mfc=S.METHOD_COLOR[m], mec="white", mew=0.4,
                 clip_on=False, zorder=5)
    S.log_axis(ins, "x", [30000, 100000, 250000], formatter=S.fmt_count)
    ins.set_xlim(30000, 250000)
    ins.set_ylim(-2.5, 4.5)
    ins.set_yticks([0, 2, 4])
    ins.tick_params(labelsize=S.TINY, length=1.8, pad=1)
    ins.set_facecolor("white")
    ins.set_title("last 220k blocks (zoom)", fontsize=S.TINY, color=S.INK2, pad=2)
    axb.text(0.985, 0.60, S.minus(f"one look at all 250k blocks: {fx.mean_bb100:+.2f} [{fx.lo:+.2f}, {fx.hi:+.2f}]\n"
             f"confidence sequence at 250k: [{cs.lo:+.2f}, {cs.hi:+.2f}]"), transform=axb.transAxes, fontsize=S.TINY,
             color=S.INK, ha="right", va="center", linespacing=1.25, zorder=8,
             bbox=dict(boxstyle="square,pad=0.25", fc="white", ec="none", alpha=0.9))
    S.log_axis(axb, "x", [200, 1000, 10000, 100000], formatter=S.fmt_count)
    axb.set_xlim(175, 250000)  # a little room so the block-204 bar clears the axis
    axb.set_ylim(-lim, lim)
    axb.set_xlabel("matched blocks observed (log scale)")
    axb.set_ylabel("estimated edge of neutral over tight (BB/100)")
    axb.text(190, lim * 0.97, "confidence sequence extends beyond ±60 before ~1k blocks", fontsize=S.TINY, color=S.INK2,
             va="top", ha="left")
    axb.legend(loc="upper right", bbox_to_anchor=(1.0, 0.93), fontsize=S.SMALL, handlelength=1.5, borderaxespad=0.3,
               labelspacing=0.35)
    S.panel_title(axb, "b", "NLHE 6-max p2, blocks in their real order", y=1.02)
    return S.save(fig, "figure6_sequential")
