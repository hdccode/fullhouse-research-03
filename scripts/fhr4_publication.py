"""FHR4 publication figures and tables (stored analysis outputs only; NO simulation).

    .venv/bin/python scripts/fhr4_export_tournament_errors.py   # read-only per-tournament export (once)
    .venv-figures/bin/python scripts/fhr4_publication.py

Inputs: reports/fhr3b/analysis-fhr4-core/{round_sweep,budget_allocation,duplicate_play,frozen_schedule,
contrasts,baseline_reliability,swiss_reference_bots,qualification_probabilities}.csv, audit_extra.json,
exports/*.csv, and reports/fhr3b/field-calibration/nlhe6/nlhe6-*/reference.json.

Outputs (paper/fhr4/):
  figures/fig{1..5}_*.{pdf,svg,png}, figures/figS1_*.{pdf,svg,png}
  figures/data/<figure>.csv   exact plotted values
  figures/CAPTIONS.md         draft captions
  tables/table{1,2,3}.csv + TABLES.md
  figures/SHA256SUMS.json

Styling reuses the FHR3 design module (paper/figures/style.py, read-only import). Regret and
strength values are in big blinds per ordinary-equivalent 400-hand match against the mu_field
reference point estimate (summed over the six qualifiers for regret).
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
from matplotlib.lines import Line2D  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "paper/figures"))
import style as S  # noqa: E402

A = REPO / "reports/fhr3b/analysis-fhr4-core"
FC = REPO / "reports/fhr3b/field-calibration/nlhe6"
PAPER = REPO / "paper/fhr4"
FIG = PAPER / "figures"
DATA = FIG / "data"
TAB = PAPER / "tables"
FIELDS = ("separated_control", "crowded_cutoff", "style_diverse")
FIELD_LABEL = {"separated_control": "Separated control", "crowded_cutoff": "Crowded cutoff",
               "style_diverse": "Style diverse"}
FIELD_COLOR = {"separated_control": S.PALETTE[0], "crowded_cutoff": S.PALETTE[1], "style_diverse": S.PALETTE[2]}
FIELD_MARKER = {"separated_control": "o", "crowded_cutoff": "s", "style_diverse": "^"}
FIELD_OFFSET = {"separated_control": -0.18, "crowded_cutoff": 0.0, "style_diverse": 0.18}
H_ROW = 62 * S.MM


# ------------------------------------------------------------------ io
def rows(path: Path) -> list[dict]:
    with path.open() as fh:
        return list(csv.DictReader(fh))


def fid(r: dict) -> str:
    return (r.get("field_id") or r.get("field")).replace("nlhe6-", "")


def est(r: dict, m: str, prefix: str = "") -> tuple[float, float, float]:
    return float(r[f"{prefix}{m}_value"]), float(r[f"{prefix}{m}_ci_lo"]), float(r[f"{prefix}{m}_ci_hi"])


def write_csv(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols: list[str] = []
    for r in data:
        cols += [k for k in r if k not in cols]
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, restval="")
        w.writeheader()
        w.writerows(data)


SUMS: dict[str, dict[str, str]] = {}


def save(fig, stem: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    meta = {"Creator": "FHR4 scripts/fhr4_publication.py (matplotlib)"}
    fig.savefig(FIG / f"{stem}.svg", format="svg", metadata={**meta, "Date": None})
    fig.savefig(FIG / f"{stem}.pdf", format="pdf", metadata={**meta, "CreationDate": None, "ModDate": None})
    from PIL import Image

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=600)
    buf.seek(0)
    rgba = Image.open(buf)
    rgb = Image.new("RGB", rgba.size, "white")
    rgb.paste(rgba, mask=rgba.split()[3])
    rgb.save(FIG / f"{stem}.png", format="PNG", dpi=(600, 600))
    plt.close(fig)
    SUMS[stem] = {e: hashlib.sha256((FIG / f"{stem}.{e}").read_bytes()).hexdigest() for e in ("svg", "pdf", "png")}


def field_legend(ax, loc: str = "upper right") -> None:
    hs = [Line2D([], [], color=FIELD_COLOR[f], marker=FIELD_MARKER[f], ms=S.MS, lw=S.LW_DATA, mec="white", mew=0.4,
                 label=FIELD_LABEL[f]) for f in FIELDS]
    ax.legend(handles=hs, loc=loc, handlelength=1.6, borderaxespad=0.2)


def dot_ci(ax, x, v, lo, hi, f, open_=False, ms=None):
    ax.errorbar([x], [v], yerr=[[v - lo], [hi - v]], fmt="none", ecolor=FIELD_COLOR[f], elinewidth=S.LW_THIN,
                capsize=0, zorder=2)
    ax.plot([x], [v], marker=FIELD_MARKER[f], ms=ms or S.MS, mfc="white" if open_ else FIELD_COLOR[f],
            mec=FIELD_COLOR[f] if open_ else "white", mew=0.6 if open_ else 0.4, ls="none", zorder=3)


def forest(ax, items: list[tuple[str, str, float, float, float]], xlabel: str, grouped: bool = True):
    """items: (field, short row label, value, lo, hi), top to bottom, grouped by field with a coloured
    field header per group; solid zero line."""
    ax.axvline(0, color=S.INK, lw=S.LW_AXIS * 1.4, zorder=1)
    ys, y, prev, heads = [], 0.0, None, []
    for f, *_ in items:
        if grouped and f != prev:
            if prev is not None:
                y += 0.7
            heads.append((f, y - 0.75))
            y += 0.35 if grouped else 0
            prev = f
        ys.append(y)
        y += 1
    ys = -np.array(ys)
    for yy, (f, _lab, v, lo, hi) in zip(ys, items, strict=True):
        ax.plot([lo, hi], [yy, yy], color=FIELD_COLOR[f], lw=S.LW_DATA, solid_capstyle="butt", zorder=2)
        ax.plot([v], [yy], marker=FIELD_MARKER[f], ms=S.MS, mfc=FIELD_COLOR[f], mec="white", mew=0.4, zorder=3)
    ax.set_yticks(ys)
    ax.set_yticklabels([lab for _, lab, *_ in items])
    if grouped:
        for f, hy in heads:
            ax.text(-0.02, -hy - 0.1, FIELD_LABEL[f], transform=ax.get_yaxis_transform(), ha="right", va="center",
                    fontsize=S.SMALL, fontweight="bold", color=FIELD_COLOR[f])
    ax.set_ylim(ys.min() - 0.7, ys.max() + (1.2 if grouped else 0.7))
    ax.set_xlabel(xlabel)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    return ys


def sym_xlim(ax, vals, pad=0.12):
    m = max(abs(v) for v in vals) * (1 + pad)
    ax.set_xlim(-m, m)


# ------------------------------------------------------------------ Figure 1: rounds
def fig1() -> str:
    sweep = rows(A / "round_sweep.csv")
    data = []
    fig, axs = plt.subplots(1, 2, figsize=(S.WIDTH, H_ROW), constrained_layout=True)
    specs = [("mu_field_reference_changed", "Wrong qualifiers vs mu_field reference (of 6)", (0, 6)),
             ("mu_field_qualification_regret", "Qualification regret (BB per 400-hand match)", (0, 250))]
    for ax, (m, ylab, ylim), letter, title in zip(axs, specs, "ab",
                                                 ("Wrong qualifiers", "Qualification regret"), strict=True):
        for f in FIELDS:
            rs = sorted((r for r in sweep if fid(r) == f), key=lambda r: int(r["R_prefix"]))
            x = np.array([int(r["R_prefix"]) for r in rs])
            v, lo, hi = (np.array(t) for t in zip(*(est(r, m) for r in rs), strict=True))
            ax.fill_between(x, lo, hi, color=FIELD_COLOR[f], alpha=S.RIBBON_ALPHA, lw=0, zorder=1)
            ax.plot(x, v, color=FIELD_COLOR[f], marker=FIELD_MARKER[f], ms=S.MS, mec="white", mew=0.4, zorder=3)
            for xi, a, b, c in zip(x, v, lo, hi, strict=True):
                data.append({"panel": letter, "metric": m, "field": f, "rounds": int(xi), "value": a, "ci_lo": b,
                             "ci_hi": c})
        ax.set_xticks([5, 10, 20, 30, 40])
        ax.set_xlim(2, 43)
        ax.set_ylim(*ylim)
        ax.set_xlabel("Swiss rounds completed (prefix of the 40-round tournaments)")
        ax.set_ylabel(ylab)
        S.panel_title(ax, letter, title, right="95% intervals; 50 tournaments per field")
    field_legend(axs[0], "lower left")
    save(fig, "fig1_reliability_vs_rounds")
    write_csv(DATA / "fig1_reliability_vs_rounds.csv", data)
    return "fig1_reliability_vs_rounds"


# ------------------------------------------------------------------ Figure 2: allocation
ALLOC = [("quarter_rounds_4x_hands", "R10 x H1600"), ("half_rounds_2x_hands", "R20 x H800"), ("baseline", "R40 x H400")]


def fig2() -> str:
    bud = rows(A / "budget_allocation.csv")
    con = [r for r in rows(A / "contrasts.csv") if r["experiment"] == "B"]
    extra = json.loads((A / "audit_extra.json").read_text())
    data = []
    fig = plt.figure(figsize=(S.WIDTH, 2 * H_ROW), layout="constrained")
    top, bot = fig.subfigures(2, 1, height_ratios=[1, 1.15])
    axs = [top.subplots(1, 2), bot.subplots(1, 2)]
    for ax, (m, ylab, ylim), letter, title in zip(
            axs[0], [("changed_qualifiers", "Changed qualifiers between reruns (of 6)", (0, 6)),
                     ("mu_field_qualification_regret", "Qualification regret (BB per 400-hand match)", (0, 220))],
            "ab", ("Rerun changed qualifiers", "Qualification regret vs mu_field"), strict=True):
        for f in FIELDS:
            xs, vs = [], []
            for i, (lab, _) in enumerate(ALLOC):
                r = next(r for r in bud if fid(r) == f and r["allocation"] == lab)
                v, lo, hi = est(r, m)
                x = i + FIELD_OFFSET[f]
                dot_ci(ax, x, v, lo, hi, f)
                xs.append(x)
                vs.append(v)
                data.append({"panel": letter, "metric": m, "field": f, "allocation": dict(ALLOC)[lab], "value": v,
                             "ci_lo": lo, "ci_hi": hi, "hands_played_ratio_vs_R40": float(r["hands_played_ratio_vs_40x400"])})
            ax.plot(xs, vs, color=FIELD_COLOR[f], lw=S.LW_THIN, alpha=0.6, zorder=1)
        played = {lab: np.mean([float(r["hands_played_per_tournament"]) / float(r["hands_scheduled_per_tournament"])
                                for r in bud if r["allocation"] == lab]) for lab, _ in ALLOC}
        ax.set_xticks(range(3))
        ax.set_xticklabels([f"{name}\n{played[lab]:.0%} of scheduled\nhands played" for lab, name in ALLOC])
        ax.set_xlim(-0.5, 2.5)
        ax.set_ylim(*ylim)
        ax.set_ylabel(ylab)
        S.panel_title(ax, letter, title)
        ax.set_xlabel("Allocation (16,000 scheduled hands per bot in each)")
    field_legend(axs[0][0], "lower left")
    pairs = [("quarter_rounds_4x_hands - baseline", "R10 minus R40"), ("half_rounds_2x_hands - baseline", "R20 minus R40"),
             ("quarter_rounds_4x_hands - half_rounds_2x_hands", "R10 minus R20")]
    for ax, (m, xm, xlab), letter, title in zip(
            axs[1], [("changed_qualifiers", "chg", "Difference in rerun changed qualifiers"),
                     ("mu_field_qualification_regret", "regret", "Difference in qualification regret (BB)")],
            "cd", ("Paired contrasts, changed qualifiers", "Paired contrasts, regret"), strict=True):
        items = []
        for f in FIELDS:
            for pr, name in pairs:
                r = next(r for r in con if r["field"] == f and r["pair"] == pr and r["metric"] == m)
                v, lo, hi = float(r["diff_value"]), float(r["diff_ci_lo"]), float(r["diff_ci_hi"])
                items.append((f, name, v, lo, hi))
                data.append({"panel": letter, "metric": m, "field": f, "contrast": name, "value": v, "ci_lo": lo,
                             "ci_hi": hi, "pairing": "same replicate ids (pair-specific)"})
            mh = extra[f]["budget_quarter_rounds_vs_R40prefix_matched_played"]
            v, lo, hi = mh[xm]
            items.append((f, f"R10 minus R40 prefix R{mh['prefix_R']} (equal played hands)", v, lo, hi))
            data.append({"panel": letter, "metric": m, "field": f,
                         "contrast": f"R10 vs R40 prefix R={mh['prefix_R']} (matched played hands)", "value": v,
                         "ci_lo": lo, "ci_hi": hi, "pairing": "same replicate ids; played hands matched"})
        forest(ax, items, xlab)
        sym_xlim(ax, [x for it in items for x in it[2:]])
        ax.tick_params(axis="y", labelsize=S.TINY)
        S.panel_title(ax, letter, title)
        ax.set_xlabel(xlab + "\n(positive = first allocation worse; 95% interval)")
    save(fig, "fig2_allocation_equal_scheduled_budget")
    write_csv(DATA / "fig2_allocation_equal_scheduled_budget.csv", data)
    return "fig2_allocation_equal_scheduled_budget"


# ------------------------------------------------------------------ Figure 3: adaptive vs frozen
def fig3() -> str:
    fz = rows(A / "frozen_schedule.csv")
    data = []
    fig, axs = plt.subplots(1, 2, figsize=(S.WIDTH, 0.62 * H_ROW), constrained_layout=True)
    for ax, (m, xlab), letter, title in zip(
            axs, [("changed_qualifiers", "Adaptive minus frozen: rerun changed qualifiers"),
                  ("mu_field_qualification_regret", "Adaptive minus frozen: qualification regret (BB)")],
            "ab", ("Changed qualifiers", "Qualification regret"), strict=True):
        items = []
        for f in FIELDS:
            r = next(r for r in fz if fid(r) == f and r["metric"] == m)
            v, lo, hi = (float(r["adaptive_minus_frozen_value"]), float(r["adaptive_minus_frozen_ci_lo"]),
                         float(r["adaptive_minus_frozen_ci_hi"]))
            items.append((f, FIELD_LABEL[f], v, lo, hi))
            data.append({"panel": letter, "metric": m, "field": f, "adaptive": float(r["adaptive_value"]),
                         "frozen": float(r["frozen_value"]), "adaptive_minus_frozen": v, "ci_lo": lo, "ci_hi": hi,
                         "n_source_tournaments": int(r["n_sources"])})
        forest(ax, items, xlab + "\n(negative = adaptive better; paired by source tournament; 95% interval)",
               grouped=False)
        sym_xlim(ax, [x for it in items for x in it[2:]])
        S.panel_title(ax, letter, title)
    save(fig, "fig3_adaptive_vs_frozen")
    write_csv(DATA / "fig3_adaptive_vs_frozen.csv", data)
    return "fig3_adaptive_vs_frozen"


# ------------------------------------------------------------------ Figure 4: duplicate packages
PKG = [("ordinary", "Ordinary\nR40 x H400"), ("dup_fewer_rounds", "Duplicate x6\nR7 x H400"),
       ("dup_shorter_matches", "Duplicate x6\nR40 x H67")]


def fig4() -> str:
    dup = rows(A / "duplicate_play.csv")
    con = [r for r in rows(A / "contrasts.csv") if r["experiment"] == "D"]
    data = []

    def pick(f, key):
        return next(r for r in dup if fid(r) == f and r["variant"].startswith(key))

    fig = plt.figure(figsize=(S.WIDTH, 2 * H_ROW), layout="constrained")
    top, bot = fig.subfigures(2, 1, height_ratios=[1, 1.15])
    axs = [top.subplots(1, 2), bot.subplots(1, 2)]
    for ax, (m, ylab, ylim), letter, title in zip(
            axs[0], [("changed_qualifiers", "Changed qualifiers between reruns (of 6)", (0, 6)),
                     ("spearman_rho", "Rank correlation between reruns (Spearman)", (0, 0.7))],
            "ab", ("Rerun changed qualifiers", "Whole-ranking stability between reruns"), strict=True):
        for f in FIELDS:
            xs, vs = [], []
            for i, (key, _) in enumerate(PKG):
                r = pick(f, key)
                v, lo, hi = est(r, m)
                x = i + FIELD_OFFSET[f]
                dot_ci(ax, x, v, lo, hi, f)
                xs.append(x)
                vs.append(v)
                data.append({"panel": letter, "metric": m, "field": f, "package": key, "value": v, "ci_lo": lo,
                             "ci_hi": hi, "scheduled_work_ratio": float(r["scheduled_work_ratio_vs_ordinary"]),
                             "played_hands_ratio": float(r["work_ratio_vs_ordinary"])})
            ax.plot(xs, vs, color=FIELD_COLOR[f], lw=S.LW_THIN, alpha=0.6, zorder=1)
        ratios = {key: float(pick("separated_control", key)["scheduled_work_ratio_vs_ordinary"]) for key, _ in PKG}
        ax.set_xticks(range(3))
        ax.set_xticklabels([f"{name}\n{ratios[key]:.3f}x scheduled work" for key, name in PKG])
        ax.set_xlim(-0.5, 2.5)
        ax.set_ylim(*ylim)
        ax.set_ylabel(ylab)
        S.panel_title(ax, letter, title)
        ax.set_xlabel("Tournament package (operational comparison)")
    field_legend(axs[0][0], "lower left")
    pairs = [("dup_fewer_rounds", "ordinary", "Dup R7xH400 minus ordinary"),
             ("dup_shorter_matches", "ordinary", "Dup R40xH67 minus ordinary"),
             ("dup_shorter_matches", "dup_fewer_rounds", "Dup R40xH67 minus dup R7xH400")]
    for ax, (m, xlab), letter, title in zip(
            axs[1], [("changed_qualifiers", "Difference in rerun changed qualifiers"),
                     ("mu_field_qualification_regret", "Difference in qualification regret (BB)")],
            "cd", ("Paired contrasts, changed qualifiers", "Paired contrasts, regret"), strict=True):
        items = []
        for f in FIELDS:
            for arm, comp, name in pairs:
                r = next(r for r in con if r["field"] == f and r["metric"] == m and r["arm"].startswith(arm)
                         and r["comparator"].startswith(comp))
                v, lo, hi = float(r["diff_value"]), float(r["diff_ci_lo"]), float(r["diff_ci_hi"])
                items.append((f, name, v, lo, hi))
                data.append({"panel": letter, "metric": m, "field": f, "contrast": name, "value": v, "ci_lo": lo,
                             "ci_hi": hi})
        forest(ax, items, xlab)
        sym_xlim(ax, [x for it in items for x in it[2:]])
        ax.tick_params(axis="y", labelsize=S.TINY)
        S.panel_title(ax, letter, title)
        ax.set_xlabel(xlab + "\n(negative = first package better; 95% interval)")
    save(fig, "fig4_duplicate_packages")
    write_csv(DATA / "fig4_duplicate_packages.csv", data)
    return "fig4_duplicate_packages"


# ------------------------------------------------------------------ Figure 5: P(qualify) at the cutoff
def fig5(n_show: int = 12) -> str:
    sw = rows(A / "swiss_reference_bots.csv")
    pq = rows(A / "exports/qualification_probabilities_all_cells.csv")
    data = []
    fig, axs = plt.subplots(1, 3, figsize=(S.WIDTH, 1.25 * H_ROW), layout="constrained", sharey=True)
    for ax, f, letter in zip(axs, FIELDS, "abc", strict=True):
        ref = sorted((r for r in pq if r["field"] == f and r["cell"] == "mu_swiss"), key=lambda r: int(r["mu_field_rank"]))
        base = {r["bot_id"]: r for r in pq if r["field"] == f and r["cell"] == "baseline"}
        swb = {r["bot_id"]: r for r in sw if fid(r) == f}
        ax.axhline(0.1, color=S.INK3, lw=S.LW_THIN, dashes=(2.2, 1.6), zorder=0.5)
        ax.axvline(6.5, color=S.RULE, lw=S.LW_THIN, zorder=0.5)
        for r in ref[:n_show]:
            x = int(r["mu_field_rank"])
            v, lo, hi = float(r["p_qualify"]), float(r["wilson_lo"]), float(r["wilson_hi"])
            dot_ci(ax, x, v, lo, hi, f, open_=x > 6)
            b = base[r["bot_id"]]
            ax.plot([x + 0.28], [float(b["p_qualify"])], marker="D", ms=S.MS * 0.6, mfc=S.INK3, mec="white", mew=0.3,
                    ls="none", zorder=2)
            data.append({"panel": letter, "field": f, "bot_id": r["bot_id"], "mu_field_rank": x,
                         "mu_field_bb": float(r["mu_field_bb"]), "p_reference_top6": float(r["p_reference_top6"]),
                         "mu_swiss_rank": int(swb[r["bot_id"]]["mu_swiss_rank"]),
                         "p_qualify_mu_swiss_200": v, "wilson_lo": lo, "wilson_hi": hi,
                         "p_qualify_baseline_50": float(b["p_qualify"])})
        ax.set_xticks(range(1, n_show + 1))
        ax.set_xticklabels([r["bot_id"].replace("nlhe6-", "") for r in ref[:n_show]], rotation=90, fontsize=S.TINY)
        ax.set_xlim(0.4, n_show + 0.7)
        ax.set_ylim(0, 1)
        ax.set_xlabel("Bot, ordered by mu_field reference rank")
        lead = "six validated leaders left of the rule" if f == "separated_control" else "reference top 6 left of the rule"
        S.panel_title(ax, letter, FIELD_LABEL[f], right=lead)
    axs[0].set_ylabel("P(qualify) in a 40-round Swiss tournament")
    hs = [Line2D([], [], ls="none", marker="o", ms=S.MS, mfc=S.INK2, mec="white", label="mu_swiss reference, 200 tournaments (Wilson 95%)"),
          Line2D([], [], ls="none", marker="o", ms=S.MS, mfc="white", mec=S.INK2, label="outside the mu_field reference top 6"),
          Line2D([], [], ls="none", marker="D", ms=S.MS * 0.6, mfc=S.INK3, mec="white", label="matrix baseline, 50 tournaments"),
          Line2D([], [], color=S.INK3, lw=S.LW_THIN, dashes=(2.2, 1.6), label="6 of 60 (uniform share)")]
    fig.legend(handles=hs, loc="outside lower center", ncol=4, fontsize=S.SMALL)
    save(fig, "fig5_qualification_probability_at_cutoff")
    write_csv(DATA / "fig5_qualification_probability_at_cutoff.csv", data)
    return "fig5_qualification_probability_at_cutoff"


# ------------------------------------------------------------------ Supplementary S1: identity vs strength error
def figS1() -> str:
    er = [r for r in rows(A / "exports/tournament_errors.csv") if r["cell"] in ("baseline", "mu_swiss")]
    rng = np.random.default_rng(20261006)
    data = []
    fig, axs = plt.subplots(1, 4, figsize=(S.WIDTH, 0.95 * H_ROW), constrained_layout=True,
                            gridspec_kw={"width_ratios": [1, 1, 1, 0.8]})
    for ax, f, letter in zip(axs[:3], FIELDS, "abc", strict=True):
        rs = [r for r in er if r["field"] == f]
        w = np.array([int(r["wrong_vs_mu_field"]) for r in rs])
        g = np.array([float(r["qualification_regret_bb"]) for r in rs])
        ax.scatter(w + rng.uniform(-0.18, 0.18, w.size), g, s=4, color=FIELD_COLOR[f], alpha=0.45, lw=0, zorder=2)
        for k in sorted(set(w)):
            sel = g[w == k]
            ax.plot([k - 0.3, k + 0.3], [sel.mean()] * 2, color=S.INK, lw=S.LW_DATA, zorder=3)
            data.append({"panel": letter, "field": f, "wrong_vs_mu_field": int(k), "n_tournaments": int(sel.size),
                         "mean_regret_bb": float(sel.mean())})
        ax.set_xticks(range(0, 7))
        ax.set_xlim(-0.6, 6.6)
        ax.set_ylim(0, max(320, g.max() * 1.05))
        ax.set_xlabel("Wrong qualifiers vs mu_field (of 6)")
        if f == FIELDS[0]:
            ax.set_ylabel("Qualification regret (BB per 400-hand match)")
        S.panel_title(ax, letter, FIELD_LABEL[f], right=f"{len(rs)} tournaments")
    ax = axs[3]
    for i, f in enumerate(FIELDS):
        rs = [r for r in er if r["field"] == f]
        amb = sum(int(r["wrong_in_reference_ambiguous_set"]) for r in rs)
        tot = sum(int(r["wrong_vs_mu_field"]) for r in rs)
        share = 1 - amb / tot
        ax.barh([2 - i], [share], color=FIELD_COLOR[f], height=0.55)
        ax.text(share + 0.02, 2 - i, f"{share:.0%}", va="center", fontsize=S.SMALL)
        data.append({"panel": "d", "field": f, "wrong_qualifiers": tot, "wrong_in_reference_ambiguous_set": amb,
                     "share_clearly_outside": share})
    ax.set_yticks([2, 1, 0])
    ax.set_yticklabels([FIELD_LABEL[f] for f in FIELDS])
    ax.set_xlim(0, 1.15)
    ax.set_xticks([0, 0.5, 1])
    ax.set_xticklabels(["0%", "50%", "100%"])
    ax.set_xlabel("Wrong qualifiers clearly outside\nthe reference-ambiguous set")
    S.panel_title(ax, "d", "Error type")
    save(fig, "figS1_identity_vs_strength_error")
    write_csv(DATA / "figS1_identity_vs_strength_error.csv", data)
    return "figS1_identity_vs_strength_error"


# ------------------------------------------------------------------ tables
def fmt(v, lo, hi, d=2):
    return f"{v:.{d}f} [{lo:.{d}f}, {hi:.{d}f}]".replace("-", "−")


def tables() -> str:
    TAB.mkdir(parents=True, exist_ok=True)
    ref = {f: json.loads((FC / f"nlhe6-{f}/reference.json").read_text()) for f in FIELDS}
    role = {"separated_control": "Engineered easy-selection control (six independently validated leaders)",
            "crowded_cutoff": "Qualification-boundary stress test (designed near-equal crowd)",
            "style_diverse": "Strategically heterogeneous field (style x strength balanced)"}
    t1 = []
    for f in FIELDS:
        rr = ref[f]["ranking_robustness"]
        t1.append({"Field": FIELD_LABEL[f], "Role": role[f], "mu_field matched rounds": ref[f]["matched_rounds"],
                   "Matrix tournaments per cell": 50, "mu_swiss tournaments": 200,
                   "Reference rank-6/7 gap (BB)": f"{rr['gap_at_cutoff_bb']:.1f}",
                   "Reference P(same top 6)": f"{rr['p_same_top_k_set']:.3f}"})
    base = {fid(r): r for r in rows(A / "baseline_reliability.csv")}
    t2 = []
    for f in FIELDS:
        r = base[f]
        t2.append({"Field": FIELD_LABEL[f],
                   "Rerun changed qualifiers": fmt(*est(r, "changed_qualifiers")),
                   "Rerun top-6 overlap": fmt(*est(r, "topk_overlap")),
                   "Rerun Spearman": fmt(*est(r, "spearman_rho")),
                   "Wrong vs mu_field": fmt(*est(r, "mu_field_reference_changed")),
                   "Qualification regret (BB)": fmt(*est(r, "mu_field_qualification_regret"), d=1),
                   "Boundary strength loss (BB)": fmt(*est(r, "mu_field_boundary_strength_loss"), d=1)})
    con = rows(A / "contrasts.csv")
    fz = rows(A / "frozen_schedule.csv")
    spec = [("B", "quarter_rounds_4x_hands - baseline", "R10 x H1600 vs R40 x H400"),
            ("B", "half_rounds_2x_hands - baseline", "R20 x H800 vs R40 x H400"),
            ("C", None, "Adaptive vs frozen schedule (R40 x H400)"),
            ("D", "dup_shorter", "Duplicate R40 x H67 x6 vs ordinary"),
            ("D", "dup_fewer", "Duplicate R7 x H400 x6 vs ordinary")]
    t3 = []
    for exp, key, name in spec:
        for f in FIELDS:
            row = {"Contrast": name, "Field": FIELD_LABEL[f]}
            for m, col in (("changed_qualifiers", "Rerun changed qualifiers"),
                           ("mu_field_qualification_regret", "Qualification regret (BB)")):
                if exp == "C":
                    r = next(r for r in fz if fid(r) == f and r["metric"] == m)
                    v, lo, hi = (float(r[f"adaptive_minus_frozen_{k}"]) for k in ("value", "ci_lo", "ci_hi"))
                elif exp == "B":
                    r = next(r for r in con if r["experiment"] == "B" and r["field"] == f and r["pair"] == key
                             and r["metric"] == m)
                    v, lo, hi = float(r["diff_value"]), float(r["diff_ci_lo"]), float(r["diff_ci_hi"])
                else:
                    r = next(r for r in con if r["experiment"] == "D" and r["field"] == f and r["metric"] == m
                             and r["arm"].startswith(key) and r["comparator"] == "ordinary")
                    v, lo, hi = float(r["diff_value"]), float(r["diff_ci_lo"]), float(r["diff_ci_hi"])
                row[col] = fmt(v, lo, hi, 2 if m == "changed_qualifiers" else 1)
            t3.append(row)
    for name, t in (("table1_design", t1), ("table2_baseline_reliability", t2), ("table3_primary_contrasts", t3)):
        write_csv(TAB / f"{name}.csv", t)

    def md(t):
        cols = list(t[0])
        return "\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
                         + ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in t])

    text = (
        "# FHR #4 main-paper tables (generated by scripts/fhr4_publication.py from stored analysis outputs)\n\n"
        "## Table 1. Final experimental design\n\nNLHE 6-max, 60 bots per field, top 6 qualify, Swiss rounds of "
        "400-hand persistent-stack matches. One frozen field per scenario.\n\n" + md(t1) + "\n\n"
        "## Table 2. Baseline reliability (adaptive Swiss, 40 rounds x 400 hands, 50 tournaments per field)\n\n"
        "Rerun metrics compare independent tournaments. Wrong qualifiers, regret and boundary strength loss are "
        "against the mu_field reference point estimate (BB per 400-hand match). 95% tournament bootstrap "
        "intervals.\n\n" + md(t2) + "\n\n"
        "## Table 3. Primary paired contrasts (first condition minus second; positive = first condition worse)\n\n"
        "B compares allocations at an equal scheduled hand budget; C is a source-schedule counterfactual "
        "(paired by source tournament); D compares operational duplicate packages. Each contrast is paired on the "
        "replicate ids shared by its two cells. 95% intervals.\n\n" + md(t3) + "\n")
    (PAPER / "TABLES.md").write_text(text)
    return "tables"


def main() -> None:
    S.setup()
    out = [fig1(), fig2(), fig3(), fig4(), fig5(), figS1(), tables()]
    (FIG / "SHA256SUMS.json").write_text(json.dumps(SUMS, indent=1, sort_keys=True) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
