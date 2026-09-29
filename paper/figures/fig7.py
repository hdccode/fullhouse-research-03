"""Figure 7: table size changes the cost and character of evaluation (FHR3A controlled suite).

Design notes
* a: one dimensionless axis (ratio to controlled 6-max) carries both opposing series, so no
  second y-axis is needed. Required played hands (solid ink, the result) rise; required matched
  blocks (dashed, the contrast) fall. Pairings p1-p3 are subordinate grey markers with CIs.
* b: per-candidate-seat quantities as indices relative to 3-max on a log axis, so that a
  halving and a doubling look symmetric and differently scaled quantities share one axis.
  Bands span p1-p3; lines are medians. Direct labels, no legend.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator

import sources
import style as S

SEATS = sources.SEATS
DODGE = {"p1": -0.16, "p2": 0.0, "p3": 0.16}
PAIR = "#9a9994"  # pairing markers / CIs: visible but subordinate to the ink median
BLK = S.INK2
MECH = {  # quantity: (label, colour, marker, linestyle, lw)
    "seat_dev2_given_diverge": ("size of the difference\nwhen A and B differ", "#eb6834", "D", "-", 1.1),
    "seat_var_mean": ("per-seat variance", S.INK, "o", "-", 1.7),
    "p_seat_diverges": ("chance that A and B\ndiffer at a seat", "#2a78d6", "v", "-", 1.1),
    "big_blocks_per_played_hand": ("big-pot blocks\nper played hand", S.INK3, None, (0, (3.0, 1.8)), 0.9),
}


def _seat_axis(ax, left: float = 2.45) -> None:
    ax.set_xlim(left, 8.55)
    ax.set_xticks(SEATS, [str(k) for k in SEATS])
    ax.tick_params(axis="x", length=2.5)
    ax.set_xlabel("seats at the table", labelpad=9)


def draw() -> dict:
    a, b, info = sources.f7()
    fig = plt.figure(figsize=(S.WIDTH, 68 * S.MM))
    axa = fig.add_axes([0.095, 0.2, 0.39, 0.7])
    axb = fig.add_axes([0.615, 0.2, 0.215, 0.7])

    # ---------------- a: required hands and blocks relative to 6-max
    med = a[a.series == "median"].sort_values("seats")
    axa.axhline(1.0, color=S.RULE, lw=S.LW_THIN, zorder=0.5)
    axa.plot(med.seats, med.blocks_rel_6max, color=BLK, lw=1.2, dashes=(3.2, 1.8), zorder=3)
    axa.plot(med.seats, med.blocks_rel_6max, "o", ms=S.MS * 0.8, mfc="white", mec=BLK, mew=0.8, zorder=4)
    for role in S.ROLES:
        g = a[a.series == role].sort_values("seats")
        x = g.seats + DODGE[role]
        axa.plot(x, g.hands_rel_6max, color=PAIR, lw=0.5, zorder=2)
        for xi, (_, r) in zip(x, g.iterrows()):
            if r.seats != 6:
                axa.plot([xi, xi], [r.hands_rel_6max_lo, r.hands_rel_6max_hi], color=PAIR, lw=0.7,
                         solid_capstyle="butt", zorder=2)
        axa.plot(x, g.hands_rel_6max, S.ROLE_MARKER[role], ms=S.ROLE_MS[role] * 0.95, mfc=PAIR, mec="white", mew=0.4,
                 ls="none", zorder=6)
    axa.fill_between(med.seats, med.hands_rel_6max_lo, med.hands_rel_6max_hi, color=S.INK, alpha=0.08, lw=0, zorder=1)
    # median as a heavy line only: at some sizes the median IS one pairing, whose marker must stay visible
    axa.plot(med.seats, med.hands_rel_6max, color=S.INK, lw=1.8, zorder=2.5)
    # direct labels: series names at the right end, end values at both ends
    m3, m8 = med.iloc[0], med.iloc[-1]
    axa.text(8.3, m8.hands_rel_6max, "played hands", color=S.INK, fontsize=S.SMALL, fontweight="bold", va="center")
    axa.text(8.3, m8.blocks_rel_6max, "matched blocks", color=BLK, fontsize=S.SMALL, va="center")
    axa.text(2.68, m3.hands_rel_6max, f"{m3.hands_rel_6max:.2f}", ha="right", va="center", fontsize=S.SMALL, color=S.INK)
    axa.text(2.68, m3.blocks_rel_6max, f"{m3.blocks_rel_6max:.2f}", ha="right", va="center", fontsize=S.SMALL, color=BLK)
    axa.text(8.3, m8.hands_rel_6max - 0.075, f"{m8.hands_rel_6max:.2f}", ha="left", va="center", fontsize=S.SMALL, color=S.INK)
    axa.text(8.3, m8.blocks_rel_6max - 0.075, f"{m8.blocks_rel_6max:.2f}", ha="left", va="center", fontsize=S.SMALL, color=BLK)
    lo, hi = info["elasticity_ci"]
    axa.text(0.98, 0.04, f"elasticity of played hands in seats {info['elasticity']:+.2f} [{lo:.2f}, {hi:.2f}]",
             transform=axa.transAxes, ha="right", va="bottom", fontsize=S.SMALL, color=S.INK)
    axa.set_ylim(0.55, 1.95)
    axa.set_yticks([0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8])
    axa.set_ylabel("required at 1 BB/100, 80% power\n(ratio to 6-max)", linespacing=1.2)
    _seat_axis(axa, left=2.3)
    for k, r in zip(SEATS, med.itertuples()):
        axa.text(k, -0.085, f"{int(r.hands_per_block)}", transform=axa.get_xaxis_transform(), ha="center",
                 va="top", fontsize=S.TINY, color=S.INK2)
    axa.text(-0.01, -0.085, "hands/block", transform=axa.transAxes, ha="right", va="top", fontsize=S.TINY,
             color=S.INK2)
    handles = S.role_handles(PAIR) + [plt.Line2D([], [], color=S.INK, lw=1.8, label="median, 95% CI band")]
    axa.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.56, 1.0), fontsize=S.SMALL, handletextpad=0.4,
               labelspacing=0.3, title="played hands (bars: 95% CI)", title_fontsize=S.TINY, alignment="left")
    S.panel_title(axa, "a", "larger tables need fewer matched blocks but more played hands", y=1.05)

    # ---------------- b: what changes per candidate seat (index, 3-max = 1)
    axb.set_yscale("log")
    axb.axhline(1.0, color=S.RULE, lw=S.LW_THIN, zorder=0.5)
    ends = {}
    for q, (label, color, marker, ls, lw) in MECH.items():
        m = b[b.series == "median"].sort_values("seats")
        pairs = np.stack([b[b.series == r].sort_values("seats")[f"{q}_index"].to_numpy() for r in S.ROLES])
        if marker is not None:
            axb.fill_between(SEATS, pairs.min(axis=0), pairs.max(axis=0), color=color, alpha=0.13, lw=0, zorder=1)
        axb.plot(m.seats, m[f"{q}_index"], color=color, lw=lw, ls=ls, zorder=3 if q != "seat_var_mean" else 4)
        if marker is not None:
            axb.plot(m.seats, m[f"{q}_index"], marker, ms=S.MS * 0.85, mfc=color, mec="white", mew=0.45, ls="none",
                     zorder=5)
        ends[q] = float(m[f"{q}_index"].iloc[-1])
    ly = np.exp(S.spread_labels(np.log([ends[q] for q in MECH]), min_gap=0.2))
    for (q, (label, color, *_)), y in zip(MECH.items(), ly):
        axb.text(8.45, y, f"{label} ×{ends[q]:.2f}", color=S.INK2 if color == S.INK3 else color, fontsize=S.SMALL,
                 va="center", ha="left", linespacing=1.1, fontweight="bold" if q == "seat_var_mean" else "normal",
                 transform=axb.transData, clip_on=False)
    axb.set_ylim(0.55, 2.6)
    axb.yaxis.set_major_locator(FixedLocator([0.6, 0.8, 1.0, 1.5, 2.0, 2.5]))
    axb.yaxis.set_major_formatter(FuncFormatter(lambda v, _=None: f"{v:g}"))
    axb.yaxis.set_minor_locator(NullLocator())
    axb.set_ylabel("index (3-max = 1)")
    axb.text(0.04, 0.04, "lines: median over p1–p3\nbands: range over p1–p3", transform=axb.transAxes, ha="left",
             va="bottom", fontsize=S.TINY, color=S.INK2, linespacing=1.2)
    _seat_axis(axb)
    S.panel_title(axb, "b", "rarer differences, larger when they occur", y=1.05)
    return S.save(fig, "figure7_table_size")
