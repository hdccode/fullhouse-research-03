"""Figure 4: the big-pot mechanism (frequency × magnitude) and what stack depth does to it."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

import sources
import style as S

NLHE6 = S.FORMAT_COLOR["NLHE 6-max"]


def draw() -> dict:
    a, b, mult = sources.f4()
    fig = plt.figure(figsize=(S.WIDTH, 74 * S.MM))
    axa = fig.add_axes([0.075, 0.15, 0.50, 0.74])
    axb = fig.add_axes([0.68, 0.15, 0.30, 0.74])

    # ---------------- a: frequency x magnitude of big-pot blocks
    xlim, ylim = (0.02, 1.0), (2.0, 8000)
    xx = np.logspace(np.log10(xlim[0]), 0, 50)
    for k in (1, 10, 100, 1000):  # iso-contribution: frequency x magnitude = big-pot share of block variance
        axa.plot(xx, k / xx, color="#ecebe7", lw=0.6, zorder=0)
        xk = min(max(k / ylim[1] * 1.6, xlim[0] * 1.15), 0.62)
        axa.text(xk, k / xk * 1.12, f"{k:g}", fontsize=S.TINY, color=S.INK3, ha="left", va="bottom", rotation=0)
    axa.text(0.022, 3.2, "iso-lines: squared deviation\nfrom big-pot blocks (BB², per block)", fontsize=S.TINY,
             color=S.INK3, va="bottom", linespacing=1.15)
    pts_x, pts_y, labels = [], [], []
    main = a[~a.stack_series | (a.format == "NLHE 6-max")]
    for fmt in [f for f in S.FORMATS if f != "Nit Game"]:
        g = main[main.format == fmt]
        for _, r in g.iterrows():
            axa.plot(r.frac_blocks_big_pot, r.mean_sq_dev_per_big_pot_block, S.ROLE_MARKER[r.role], ms=S.ROLE_MS[r.role] * 1.1,
                     mfc=S.FORMAT_COLOR[fmt], mec="white", mew=0.45, zorder=4)
        pts_x += list(g.frac_blocks_big_pot)
        pts_y += list(g.mean_sq_dev_per_big_pot_block)
        labels.append((fmt, float(np.exp(np.log(g.frac_blocks_big_pot).mean())), float(np.exp(np.log(g.mean_sq_dev_per_big_pot_block).mean()))))
    # stack series: NLHE 6-max 20BB and 50BB (open markers) linked to 100BB, per pairing
    for r in S.ROLES:
        ser = [a[(a.format == f) & (a.role == r)].iloc[0] for f in ("NLHE 6-max 20BB", "NLHE 6-max 50BB", "NLHE 6-max")]
        axa.plot([s.frac_blocks_big_pot for s in ser], [s.mean_sq_dev_per_big_pot_block for s in ser], color=NLHE6, lw=0.6,
                 alpha=0.7, zorder=2)
        for s in ser[:2]:
            axa.plot(s.frac_blocks_big_pot, s.mean_sq_dev_per_big_pot_block, S.ROLE_MARKER[r], ms=S.ROLE_MS[r] * 1.1, mfc="white",
                     mec=NLHE6, mew=0.8, zorder=4)
            pts_x.append(s.frac_blocks_big_pot)
            pts_y.append(s.mean_sq_dev_per_big_pot_block)
    for f, tag in (("NLHE 6-max 20BB", "20BB"), ("NLHE 6-max 50BB", "50BB")):
        g = a[a.format == f]
        axa.text(g.frac_blocks_big_pot.max() * 1.1, np.exp(np.log(g.mean_sq_dev_per_big_pot_block).mean()), tag, fontsize=S.SMALL,
                 color=S.INK2, va="center", ha="left")
    # format labels: deterministic offsets in log space chosen to clear the points (checked visually)
    # each label sits on the free side of its own cluster, anchored to the cluster's p1 point
    # (multiplicative offsets in log space; placements checked visually at final size)
    anchor = {"AoF 4-max 8BB": (0.86, 1.0, "right", "center"), "NLHE 4-max": (1.0, 4.4, "center", "bottom"),
              "NLHE 6-max": (0.83, 0.62, "right", "top"), "Crazy Pineapple": (1.0, 3.7, "center", "bottom"),
              "PLO": (1.0, 0.62, "center", "top"), "Bomb Pot": (1.13, 1.0, "left", "center")}
    for fmt, _cx, _cy in labels:
        p1 = main[(main.format == fmt) & (main.role == "p1")].iloc[0]
        mx, my, ha, va = anchor[fmt]
        name = "NLHE 6-max 100BB" if fmt == "NLHE 6-max" else S.FORMAT_SHORT[fmt]
        axa.text(p1.frac_blocks_big_pot * mx, p1.mean_sq_dev_per_big_pot_block * my, name, fontsize=S.SMALL, color=S.INK,
                 ha=ha, va=va, zorder=6, bbox=dict(boxstyle="square,pad=0.08", fc="white", ec="none", alpha=0.85))
    S.log_axis(axa, "x", [0.02, 0.05, 0.1, 0.2, 0.5, 1.0], formatter=lambda v, _=None: f"{v * 100:g}%")
    S.log_axis(axa, "y", [3, 10, 30, 100, 300, 1000, 3000], formatter=lambda v, _=None: f"{v:g}")
    axa.set_xlim(*xlim)
    axa.set_ylim(*ylim)
    axa.set_xlabel("share of blocks with a pot ≥ one starting stack (log scale)")
    axa.set_ylabel("mean squared deviation per such block (BB², log scale)")
    S.panel_title(axa, "a", "big-pot blocks: how often × how much", y=1.04)

    # ---------------- b: stack depth (paired, identical cards)
    xs = {20: 0, 50: 1, 100: 2}
    jit = {"p1": -0.09, "p2": 0.0, "p3": 0.09}
    for r in S.ROLES:
        g = b[b.role == r].sort_values("stack_bb")
        x = [xs[int(v)] + jit[r] for v in g.stack_bb]
        axb.plot(x, g.sd_ratio_vs_100, color=NLHE6, lw=0.8, alpha=0.8, zorder=2)
        for xi, (_, row) in zip(x, g.iterrows(), strict=True):
            if row.stack_bb != 100:
                axb.plot([xi, xi], [row.ci_lo, row.ci_hi], color=NLHE6, lw=0.8, zorder=3, solid_capstyle="butt")
            axb.plot(xi, row.sd_ratio_vs_100, S.ROLE_MARKER[r], ms=S.ROLE_MS[r] * 1.1, mfc=NLHE6, mec="white", mew=0.45, zorder=4)
    axb.set_xticks([0, 1, 2], ["20BB", "50BB", "100BB"])
    axb.set_xlim(-0.45, 2.45)
    axb.set_ylim(0, 1.12)
    axb.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    axb.set_xlabel("starting stack (NLHE 6-max, same cards and agents)")
    axb.set_ylabel("block-level σ relative to 100BB")
    lo20, hi20 = mult[20][0], mult[20][-1]
    lo50, hi50 = mult[50][0], mult[50][-1]
    axb.text(0.0, 0.27, f"100BB needs\n{lo20:.1f}–{hi20:.1f}× the\nblocks of 20BB", fontsize=S.SMALL, ha="center", va="top",
             color=S.INK, linespacing=1.15)
    axb.text(1.22, 0.62, f"and {lo50:.1f}–{hi50:.1f}× the\nblocks of 50BB", fontsize=S.SMALL, ha="left", va="top", color=S.INK,
             linespacing=1.15)
    S.panel_title(axb, "b", "stack depth", y=1.04)
    axb.legend(handles=S.role_handles(NLHE6), loc="upper left", fontsize=S.SMALL, handletextpad=0.2, borderaxespad=0.2,
               labelspacing=0.3)
    return S.save(fig, "figure4_big_pots_stack_depth")
