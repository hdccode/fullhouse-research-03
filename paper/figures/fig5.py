"""Figure 5: how much variance the estimators remove (RQ6), and one comparison it resolves."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

import sources
import style as S

ROW_COLOR = {"AoF": S.FORMAT_COLOR["AoF 4-max 8BB"], "NLHE": S.FORMAT_COLOR["NLHE 6-max"]}


def draw() -> dict:
    d, ins, raw_equiv = sources.f5()
    rows = list(dict.fromkeys(d.sort_values("order")["row"]))
    fig = plt.figure(figsize=(S.WIDTH, 64 * S.MM))
    ax = fig.add_axes([0.155, 0.14, 0.50, 0.75])
    axb = fig.add_axes([0.795, 0.14, 0.19, 0.75])

    # ---------------- a: forest plot of variance ratios
    n = len(rows)
    dy = {"p1": 0.2, "p2": 0.0, "p3": -0.2}
    for i, row in enumerate(rows):
        y = n - 1 - i
        g = d[d.row == row]
        c = ROW_COLOR["AoF" if row.startswith("AoF") else "NLHE"]
        if i % 2 == 0:
            ax.axhspan(y - 0.5, y + 0.5, color="#f6f6f4", lw=0, zorder=0)
        for _, r in g.iterrows():
            yy = y + dy[r.role]
            ax.plot([r.ci_lo, r.ci_hi], [yy, yy], color=c, lw=0.9, solid_capstyle="butt", zorder=2)
            ax.plot(r.var_ratio, yy, S.ROLE_MARKER[r.role], ms=S.ROLE_MS[r.role], mfc=c, mec="white", mew=0.45, zorder=3)
        med = float(np.median(g.var_ratio))
        ax.plot([med, med], [y - 0.36, y + 0.36], color=S.INK, lw=1.2, solid_capstyle="butt", zorder=4)
        ax.text(1.085, y, f"{med:.2f}", va="center", ha="left", fontsize=S.SMALL, color=S.INK)
        ax.text(1.2, y, f"{1 / med:.1f}×", va="center", ha="left", fontsize=S.SMALL, color=S.INK2)
    ax.text(1.085, n - 0.35, "median", fontsize=S.TINY, color=S.INK2, ha="left", va="bottom")
    ax.text(1.2, n - 0.35, "efficiency", fontsize=S.TINY, color=S.INK2, ha="left", va="bottom")
    ax.axvline(1.0, color=S.INK, lw=0.7, zorder=1)
    S.ref_line(ax, 0.5, "x", color=S.INK3, lw=0.6)
    ax.text(0.995, -0.62, "raw (no reduction)", fontsize=S.TINY, color=S.INK2, ha="right", va="top")
    ax.text(0.495, -0.62, "2× sample efficiency", fontsize=S.TINY, color=S.INK2, ha="right", va="top")
    ax.set_yticks(range(n)[::-1], rows)
    ax.tick_params(axis="y", length=0)
    ax.set_ylim(-0.95, n - 0.35)
    ax.set_xlim(0, 1.03)
    ax.spines["left"].set_visible(False)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xlabel("variance ratio  Var(estimator D) / Var(raw D)   (lower = fewer blocks needed)")
    S.panel_title(ax, "a", "variance left after each estimator, on the same matched blocks", y=1.03)
    # the region left of 0.5 on the NLHE rows is empty: legend goes there
    ax.legend(handles=S.role_handles() + [plt.Line2D([], [], color=S.INK, lw=1.2, marker="|", ls="none", ms=6, mew=1.2,
                                                     label="median over pairings")],
              loc="center left", bbox_to_anchor=(0.03, 0.42), fontsize=S.SMALL, handletextpad=0.3, labelspacing=0.35,
              title="error bars: paired bootstrap 95% CI", title_fontsize=S.TINY, alignment="left")

    # ---------------- b: AoF p1, same 50k blocks
    c = ROW_COLOR["AoF"]
    lab = {"raw": "raw outcome", "allin_ev": "all-in EV"}
    for k, (_, r) in enumerate(ins.iterrows()):
        y = 1.1 - 1.0 * k
        axb.plot([r.ci_lo, r.ci_hi], [y, y], color=c, lw=1.2, solid_capstyle="butt", zorder=2)
        axb.plot(r.mean_bb100, y, "o", ms=S.MS * 1.1, mfc=c, mec="white", mew=0.5, zorder=3)
        axb.text(-0.17, y + 0.2, lab[r.estimator], ha="left", va="bottom", fontsize=S.SMALL, color=S.INK, zorder=4,
                 bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none"))
        axb.text(0.72, y + 0.2, S.minus(f"{r.mean_bb100:+.2f} [{r.ci_lo:+.2f}, {r.ci_hi:+.2f}]"), ha="right", va="bottom",
                 fontsize=S.TINY, color=S.INK2)
    axb.plot([0, 0], [-0.25, 1.62], color=S.INK, lw=0.7, zorder=1)  # zero line stops above the note
    axb.set_yticks([])
    axb.spines["left"].set_visible(False)
    axb.set_ylim(-0.95, 1.65)
    axb.set_xlim(-0.2, 0.75)
    axb.set_xticks([0, 0.25, 0.5])
    axb.set_xlabel("edge, BB/100 (95% CI)")
    S.panel_title(axb, "b", "AoF production v2 vs 10% blend", y=1.03)
    axb.text(-0.17, -0.62, f"same 50k blocks; raw outcomes would\nneed ≈{raw_equiv / 1e3:.0f}k blocks for this precision",
             fontsize=S.TINY, color=S.INK2, ha="left", va="center", linespacing=1.2)
    return S.save(fig, "figure5_variance_reduction")
