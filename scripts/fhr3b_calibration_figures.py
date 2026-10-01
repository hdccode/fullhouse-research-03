"""FHR3B field-calibration figures (selection v2; reads the review tables; plots only).

    .venv-figures/bin/python scripts/fhr3b_calibration_figures.py

Inputs:
* reports/fhr3b/field-calibration/review/{boundary.csv, bot_strengths.csv, review.json};
* reports/fhr3b/field-calibration/<mode>/behaviour.csv.

Outputs: reports/fhr3b/field-calibration/figures/fig_c{1..4}_*.{pdf,svg,png} + SHA256SUMS.json

Values are pool-calibration balanced field EV in big blinds per 400-hand match under the
fhr3b_baseline research protocol (research design choices, not 2026 FullHouse settings).
Styling reuses the FHR3 design module (paper/figures/style.py, read-only import).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "paper/figures"))
import style as S  # noqa: E402

FC = REPO / "reports/fhr3b/field-calibration"
REV = FC / "review"
OUT = FC / "figures"
MODE_LABEL = {"aof4": "AoF 4-max 8BB", "nlhe4": "NLHE 4-max 100BB", "nlhe6": "NLHE 6-max 100BB"}
FIELDS = ("spread", "crowded_cutoff", "style_diverse")
FIELD_COLOR = {"spread": S.PALETTE[0], "crowded_cutoff": S.PALETTE[1], "style_diverse": S.PALETTE[2]}
FIELD_MARKER = {"spread": "o", "crowded_cutoff": "s", "style_diverse": "^"}
STYLES = ("TA", "LA", "TP", "LP")
# validated (dataviz validate_palette.js, --pairs all, light): contrast WARN -> shapes + legend as relief
STYLE_COLOR = {"TA": "#4a3aa7", "LA": "#e87ba4", "TP": "#008300", "LP": "#eda100"}
STYLE_MARKER = {"TA": "o", "LA": "D", "TP": "s", "LP": "v"}
STYLE_NAME = {"nlhe": {"TA": "tight-aggressive", "LA": "loose-aggressive", "TP": "tight-passive", "LP": "loose-passive"},
              "aof": {"TA": "tight caller, frequent shover", "LA": "loose caller, frequent shover",
                      "TP": "tight caller, selective shover", "LP": "loose caller, selective shover"}}
DIVERGING = LinearSegmentedColormap.from_list("bgr", ["#2a78d6", "#f0efec", "#e34948"])
SEQ = LinearSegmentedColormap.from_list("seq", ["#f4f3f0", "#9cc2ef", "#2a78d6", "#123f7a"])
K = 6


def save(fig, stem: str) -> dict[str, str]:
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"Creator": "FHR3B scripts/fhr3b_calibration_figures.py (matplotlib)"}
    fig.savefig(OUT / f"{stem}.svg", format="svg", metadata={**meta, "Date": None})
    fig.savefig(OUT / f"{stem}.pdf", format="pdf", metadata={**meta, "CreationDate": None, "ModDate": None})
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=600, facecolor="white")
    (OUT / f"{stem}.png").write_bytes(buf.getvalue())
    plt.close(fig)
    return {e: hashlib.sha256((OUT / f"{stem}.{e}").read_bytes()).hexdigest() for e in ("svg", "pdf", "png")}


def rows(path: Path) -> list[dict]:
    with path.open() as fh:
        return list(csv.DictReader(fh))


def fnum(x: str) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def minus_fmt(ax, axis="y"):
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(plt.FuncFormatter(lambda v, _: S.minus(f"{v:g}")))


def fig1(b, review, modes):
    fig, axes = plt.subplots(1, len(modes), figsize=(S.WIDTH * (0.34 * len(modes) + 0.02), 2.6),
                             gridspec_kw={"wspace": 0.28}, squeeze=False)
    for j, (ax, mode) in enumerate(zip(axes[0], modes, strict=True)):
        for f in FIELDS:
            d = np.array([(int(r["rank"]), fnum(r["mu_bb"])) for r in b[(mode, f)]])
            ax.plot(d[:, 0], d[:, 1], color=FIELD_COLOR[f], lw=S.LW_THIN, zorder=2)
            ax.plot(d[:, 0], d[:, 1], ls="none", marker=FIELD_MARKER[f], ms=S.MS * 0.62, mfc=FIELD_COLOR[f],
                    mec="white", mew=0.3, zorder=3)
        S.ref_line(ax, K + 0.5, "x", color=S.INK3)
        ax.axhline(0, color=S.RULE, lw=S.LW_THIN, zorder=0)
        ax.set_xlim(0, 61)
        ax.set_xticks([1, 6, 20, 40, 60])
        ax.set_xlabel("rank within field")
        if j == 0:
            ax.set_ylabel("balanced field EV (BB / 400-hand match)")
        ax.text(K + 1.2, ax.get_ylim()[1], "top-6 cut", fontsize=S.TINY, color=S.INK2, va="top")
        minus_fmt(ax)
        S.panel_title(ax, "abc"[j], MODE_LABEL[mode], right=f"calib. SE ≈ {review['modes'][mode]['median_se_bb']:.1f} BB")
    handles = [Line2D([], [], color=FIELD_COLOR[f], lw=S.LW_THIN, marker=FIELD_MARKER[f], ms=S.MS * 0.7,
                      mfc=FIELD_COLOR[f], mec="white", mew=0.3, label=f) for f in FIELDS]
    fig.legend(handles=handles, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 0.995), handlelength=2.2)
    fig.subplots_adjust(left=0.1, right=0.98, bottom=0.17, top=0.78)
    return save(fig, "fig_c1_field_structure")


def fig2(b, review, modes):
    fig, axes = plt.subplots(len(modes), 3, figsize=(S.WIDTH, 1.65 * len(modes) + 0.5), sharex=True,
                             gridspec_kw={"wspace": 0.2, "hspace": 0.55}, squeeze=False)
    for i, mode in enumerate(modes):
        info = review["modes"][mode]
        tse = info["tournament_se_mean_per_match_bb"]
        data = {f: np.array([(int(r["rank"]), fnum(r["mu_bb"]), fnum(r["se_bb"])) for r in b[(mode, f)]])[:12]
                for f in FIELDS}
        lo = min(d[:, 1].min() - 1.96 * d[:, 2].max() for d in data.values())
        hi = max(d[:, 1].max() + 1.96 * d[:, 2].max() for d in data.values())
        pad = 0.08 * (hi - lo)
        for j, f in enumerate(FIELDS):
            ax = axes[i, j]
            d = data[f]
            fi = info["fields"][f]
            cut = (d[5, 1] + d[6, 1]) / 2
            ax.axhspan(cut - tse, cut + tse, color=S.RULE, alpha=0.35, lw=0, zorder=0)
            ax.errorbar(d[:, 0], d[:, 1], yerr=1.96 * d[:, 2], fmt="none", ecolor=FIELD_COLOR[f],
                        elinewidth=S.LW_THIN, capsize=0, zorder=2)
            ax.plot(d[:, 0], d[:, 1], ls="none", marker=FIELD_MARKER[f], ms=S.MS * 0.8, mfc=FIELD_COLOR[f],
                    mec="white", mew=0.35, zorder=3)
            S.ref_line(ax, K + 0.5, "x", color=S.INK3)
            ax.set_ylim(lo - pad, hi + pad)
            ax.set_xlim(0.3, 12.7)
            ax.set_xticks([1, 3, 6, 7, 9, 12])
            minus_fmt(ax)
            ax.text(0.98, 0.95, f"gap r6–r7 {fi['gap_k_k1_bb']:.1f} BB ({fi['gap_k_k1_se']:.2f} SE)\n"
                                f"{fi['n_within_5bb_of_cut']} bots within ±5 BB of cut",
                    transform=ax.transAxes, ha="right", va="top", fontsize=S.TINY, color=S.INK2, linespacing=1.25)
            if j == 0:
                ax.set_ylabel(f"{MODE_LABEL[mode]}\nBB / match", fontsize=S.BASE)
            if i == 0:
                ax.set_title(f, color=S.INK)
            if i == len(modes) - 1:
                ax.set_xlabel("rank within field")
    fig.text(0.99, 0.005, "Bars: 95% calibration CI (2,000 matches/bot). Grey band: cut ± 1 SE of one bot's mean per "
             "match over one 40-round tournament (initial research horizon).", ha="right", va="bottom",
             fontsize=S.TINY, color=S.INK2)
    fig.subplots_adjust(left=0.1, right=0.99, bottom=0.14 if len(modes) < 3 else 0.1, top=0.9)
    return save(fig, "fig_c2_boundary_zoom")


def fig3(review, strengths):
    """Realism: recognisable play styles, busting vs strength, stack sensitivity, AoF styles and cycle."""
    fig = plt.figure(figsize=(S.WIDTH, 5.1))
    gs = fig.add_gridspec(2, 3, hspace=0.62, wspace=0.42, left=0.07, right=0.985, top=0.92, bottom=0.2)
    nl = [r for r in strengths if r["mode"] == "nlhe6"]
    beh = {r["bot_id"]: r for r in rows(FC / "nlhe6/behaviour.csv")}
    top = sorted(nl, key=lambda r: -fnum(r["mu_bb"]))[:3]

    ax = fig.add_subplot(gs[0, 0])
    for st in STYLES:
        pts = [r for r in nl if r["style"] == st]
        ax.plot([fnum(r["vpip"]) for r in pts], [fnum(r["pfr"]) for r in pts], ls="none", marker=STYLE_MARKER[st],
                ms=S.MS * 0.75, mfc=STYLE_COLOR[st], mec="white", mew=0.3, label=STYLE_NAME["nlhe"][st])
    for r in top:
        ax.annotate(r["bot_id"].replace("nlhe6-", ""), (fnum(r["vpip"]), fnum(r["pfr"])), xytext=(4, -9),
                    textcoords="offset points", fontsize=S.TINY, color=S.INK2)
    ax.plot([0, 0.65], [0, 0.65], color=S.RULE, lw=S.LW_THIN, zorder=0)
    ax.set_xlim(0, 0.66)
    ax.set_ylim(0, 0.55)
    ax.set_xlabel("VPIP")
    ax.set_ylabel("PFR")
    S.panel_title(ax, "a", "NLHE6 pool: observed styles", y=1.07)
    ax.legend(loc="upper left", fontsize=S.TINY, handletextpad=0.2, borderaxespad=0.2, labelspacing=0.25)

    ax = fig.add_subplot(gs[0, 1])
    for st in STYLES:
        pts = [r for r in nl if r["style"] == st]
        ax.plot([fnum(r["bust_rate"]) for r in pts], [fnum(r["mu_bb"]) for r in pts], ls="none",
                marker=STYLE_MARKER[st], ms=S.MS * 0.75, mfc=STYLE_COLOR[st], mec="white", mew=0.3)
    info = review["modes"]["nlhe6"]
    ax.axhline(0, color=S.RULE, lw=S.LW_THIN, zorder=0)
    ax.set_xlabel("P(bust) per 400-hand match")
    ax.set_ylabel("balanced EV (BB / match)")
    minus_fmt(ax)
    S.panel_title(ax, "b", "NLHE6: strength vs busting", y=1.07)
    ax.text(0.98, 0.97, S.minus(f"Spearman {info['spearman_mu_vs_bust']:+.2f}"), transform=ax.transAxes, ha="right",
            va="top", fontsize=S.TINY, color=S.INK2)

    ax = fig.add_subplot(gs[0, 2])
    labels = ["<40", "40–80", "80–150", ">150"]
    vp = np.array([[fnum(beh[r["bot_id"]][f"vpip_stack{i}"]) for i in range(4)] for r in nl])
    ai = np.array([[fnum(beh[r["bot_id"]][f"allin_stack{i}"]) for i in range(4)] for r in nl])
    share = np.array([sum(fnum(beh[r["bot_id"]][f"hands_stack{i}"]) for r in nl) for i in range(4)])
    share = share / share.sum()
    x = np.arange(4)
    for arr, c, mk, lab in ((vp, S.INK, "o", "VPIP"), (ai * 10, S.PALETTE[1], "s", "preflop all-in rate × 10")):
        q = np.nanquantile(arr, [0.25, 0.5, 0.75], axis=0)
        ax.fill_between(x, q[0], q[2], color=c, alpha=S.RIBBON_ALPHA, lw=0)
        ax.plot(x, q[1], color=c, lw=S.LW_DATA, marker=mk, ms=S.MS * 0.8, mec="white", mew=0.3, label=lab)
    for xi, sh in zip(x, share, strict=True):
        ax.text(xi, 0.555, f"{sh:.0%}", ha="center", fontsize=S.TINY, color=S.INK3)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlabel("own stack (BB); top: share of hands")
    ax.set_ylim(0, 0.6)
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 0.93), fontsize=S.TINY)
    S.panel_title(ax, "c", "NLHE6: stack sensitivity (pool median, IQR)", y=1.07)

    ax = fig.add_subplot(gs[1, 0])
    af = [r for r in strengths if r["mode"] == "aof4"]
    for st in STYLES:
        pts = [r for r in af if r["style"] == st]
        ax.plot([fnum(r["call_vs_raise"]) for r in pts], [fnum(r["open_raise"]) for r in pts], ls="none",
                marker=STYLE_MARKER[st], ms=S.MS * 0.75, mfc=STYLE_COLOR[st], mec="white", mew=0.3,
                label=STYLE_NAME["aof"][st])
    pol = [r for r in af if r["archetype"].startswith("policy")]
    ax.plot([fnum(r["call_vs_raise"]) for r in pol], [fnum(r["open_raise"]) for r in pol], ls="none", marker="o",
            ms=S.MS * 1.35, mfc="none", mec=S.INK, mew=0.5, label="production-policy family")
    ax.set_xlabel("call rate vs a shove")
    ax.set_ylabel("shove rate, unopened")
    S.panel_title(ax, "d", "AoF4 pool: observed styles", y=1.07)
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.2), ncol=2, fontsize=S.TINY - 0.3, handletextpad=0.2,
              labelspacing=0.25, columnspacing=0.8, borderaxespad=0.0)

    a = review["modes"]["aof4"]["archetype_cycle"]
    m = np.array(a["cyclic_matrix_bb"])
    ax = fig.add_subplot(gs[1, 1:])
    lim = float(np.abs(m).max())
    im = ax.imshow(m, cmap=DIVERGING, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
    names = [n.replace("policy_blend_loose", "policy blend") for n in a["archetypes"]]
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=25, ha="right")
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names)
    for (r, c), v in np.ndenumerate(m):
        if r != c:
            ax.text(c, r, S.minus(f"{v:+.1f}"), ha="center", va="center", fontsize=S.TINY - 0.5,
                    color=S.INK if abs(v) < 0.6 * lim else "white")
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(length=0)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.015)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=S.TINY, length=1.5)
    cb.set_label("cyclic flow, row vs column (BB / match)", fontsize=S.TINY)
    p = "p < 0.005" if a["perm_p"] == 0 else f"p = {a['perm_p']:.2f}"
    S.panel_title(ax, "e", f"AoF4 archetype matchups, cyclic part (measured; split-half r = {a['r_cyclic']:.2f}, "
                  f"{p}; NLHE6 r = {review['modes']['nlhe6']['archetype_cycle']['r_cyclic']:.2f}, n.s.)", y=1.07)
    return save(fig, "fig_c3_realism")


def fig4(strengths, boundary, modes):
    """Style x strength-stratum composition of each field (5 pool-strength quintiles)."""
    fig, axes = plt.subplots(len(modes), 3, figsize=(S.WIDTH, 1.55 * len(modes) + 0.5),
                             gridspec_kw={"wspace": 0.12, "hspace": 0.55}, squeeze=False)
    vmax = 0
    mats = {}
    for mode in modes:
        pool = sorted((r for r in strengths if r["mode"] == mode), key=lambda r: -fnum(r["mu_bb"]))
        edges = [round(i * len(pool) / 5) for i in range(6)]
        stratum = {r["bot_id"]: next(s for s in range(5) if edges[s] <= i < edges[s + 1]) for i, r in enumerate(pool)}
        style = {r["bot_id"]: r["style"] for r in pool}
        for f in FIELDS:
            mat = np.zeros((4, 5), int)
            for r in boundary:
                if r["mode"] == mode and r["field"] == f:
                    mat[STYLES.index(style[r["bot_id"]]), stratum[r["bot_id"]]] += 1
            mats[(mode, f)] = mat
            vmax = max(vmax, mat.max())
    for i, mode in enumerate(modes):
        fam = "aof" if mode.startswith("aof") else "nlhe"
        for j, f in enumerate(FIELDS):
            ax = axes[i, j]
            mat = mats[(mode, f)]
            ax.imshow(mat, cmap=SEQ, vmin=0, vmax=vmax, aspect="auto")
            for (r, c), v in np.ndenumerate(mat):
                ax.text(c, r, str(v), ha="center", va="center", fontsize=S.TINY,
                        color="white" if v > 0.55 * vmax else S.INK)
            ax.set_xticks(range(5))
            ax.set_xticklabels(["Q1\nstrongest", "Q2", "Q3", "Q4", "Q5\nweakest"] if i == len(modes) - 1 else [])
            ax.set_yticks(range(4))
            ax.set_yticklabels([STYLE_NAME[fam][s] for s in STYLES] if j == 0 else [], fontsize=S.TINY)
            ax.tick_params(length=0)
            for sp in ax.spines.values():
                sp.set_visible(False)
            if i == 0:
                ax.set_title(f, color=S.INK)
            if j == 0:
                ax.text(-0.02, 1.08, MODE_LABEL[mode], transform=ax.transAxes, fontsize=S.BASE, ha="right", color=S.INK)
    fig.text(0.99, 0.005, "Cells: number of field bots by observed style (exact replay) and pool-strength quintile.",
             ha="right", va="bottom", fontsize=S.TINY, color=S.INK2)
    fig.subplots_adjust(left=0.2, right=0.99, bottom=0.14, top=0.9)
    return save(fig, "fig_c4_field_composition")


def main() -> None:
    S.setup()
    review = json.loads((REV / "review.json").read_text())
    modes = list(review["modes"])
    boundary = rows(REV / "boundary.csv")
    b: dict = {}
    for r in boundary:
        b.setdefault((r["mode"], r["field"]), []).append(r)
    strengths = rows(REV / "bot_strengths.csv")
    for stale in OUT.glob("fig_c3_matchup_evidence.*"):
        stale.unlink()
    hashes = {"fig_c1_field_structure": fig1(b, review, modes), "fig_c2_boundary_zoom": fig2(b, review, modes),
              "fig_c4_field_composition": fig4(strengths, boundary, modes)}
    if {"aof4", "nlhe6"} <= set(modes):  # realism panel needs both (NLHE awaits re-calibration)
        hashes["fig_c3_realism"] = fig3(review, strengths)
    (OUT / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: v["png"][:12] for k, v in hashes.items()}))


if __name__ == "__main__":
    main()
