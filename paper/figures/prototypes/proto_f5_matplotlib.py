"""Architecture spike: F5 in bespoke Matplotlib at final size (183 mm wide)."""

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).parent
DATA = HERE.parent.parent / "figures" / "data"
mpl.rcParams.update({
    "font.family": "Arial", "font.size": 6.5, "axes.linewidth": 0.5, "xtick.major.width": 0.5,
    "ytick.major.width": 0.5, "xtick.major.size": 2.5, "ytick.major.size": 0, "axes.spines.top": False,
    "axes.spines.right": False, "svg.fonttype": "none", "pdf.fonttype": 42,
})
d = pd.read_csv(DATA / "F5_variance_reduction.csv", comment="#")
ins = pd.read_csv(DATA / "F5_inset_aof_p1.csv", comment="#")
COL = {"AoF 8BB": "#2a78d6", "NLHE": "#1baf7a"}
MK = {"p1": "o", "p2": "s", "p3": "^"}
rows = list(dict.fromkeys(d.sort_values("order")["row"]))
fig = plt.figure(figsize=(7.2, 2.3))
ax = fig.add_axes([0.2, 0.2, 0.5, 0.72])
axb = fig.add_axes([0.8, 0.2, 0.17, 0.72])
for i, r in enumerate(rows):
    y = len(rows) - 1 - i
    g = d[d.row == r]
    c = COL["AoF 8BB"] if r.startswith("AoF") else COL["NLHE"]
    for j, (_, x) in enumerate(g.sort_values("role").iterrows()):
        yy = y + (j - 1) * 0.2
        ax.plot([x.ci_lo, x.ci_hi], [yy, yy], color=c, lw=0.8, solid_capstyle="butt")
        ax.plot(x.var_ratio, yy, MK[x.role], color=c, ms=3.6, mec="white", mew=0.5)
    med = g.var_ratio.median()
    ax.plot([med, med], [y - 0.36, y + 0.36], color="#0b0b0b", lw=1.1)
    ax.text(1.07, y, f"{med:.2f}", va="center", fontsize=6, color="#52514e")
ax.axvline(1, color="#0b0b0b", lw=0.6)
ax.axvline(0.5, color="#9a9994", lw=0.5, ls=(0, (2, 2)))
ax.set_yticks(range(len(rows))[::-1], rows)
ax.set_xlim(0, 1.13)
ax.set_xlabel("variance ratio  Var(estimator D) / Var(raw D)")
ax.text(1.0, len(rows) - 0.35, "no reduction", ha="right", fontsize=5.5, color="#52514e")
ax.text(0.5, len(rows) - 0.35, "2× efficiency", ha="right", fontsize=5.5, color="#52514e")
ax.set_ylim(-0.6, len(rows) - 0.2)
for k, (_, x) in enumerate(ins.iterrows()):
    axb.plot([x.ci_lo, x.ci_hi], [1 - k, 1 - k], color="#2a78d6", lw=1)
    axb.plot(x.mean_bb100, 1 - k, "o", color="#2a78d6", ms=3.6, mec="white", mew=0.5)
axb.axvline(0, color="#0b0b0b", lw=0.6)
axb.set_yticks([1, 0], ["raw", "all-in EV"])
axb.set_ylim(-0.6, 1.6)
axb.set_xlabel("AoF p1 edge (BB/100)")
fig.text(0.01, 0.95, "a", weight="bold", fontsize=8)
fig.text(0.735, 0.95, "b", weight="bold", fontsize=8)
for ext in ("svg", "pdf", "png"):
    fig.savefig(HERE / f"proto_f5_matplotlib.{ext}", dpi=600, metadata={"Date": None} if ext != "png" else None)
print("ok")
