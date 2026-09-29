"""Frozen-source loaders with invariant checks. Every plotted number comes from here.

Sources: paper/figures/data/*.csv (generated from frozen outputs by scripts/paper_figure_data.py)
and the canonical report trees reports/final-analysis, reports/rq6, reports/rq7, and (F7) the
FHR3A controlled table-size suite reports/table-size (frozen by its MANIFEST.json) and its
derived deep/deep.json. Each loader
cross-checks its values against the canonical report it was derived from, and raises if a
source changed.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "paper" / "figures" / "data"
FA, R6, R7 = ROOT / "reports" / "final-analysis", ROOT / "reports" / "rq6", ROOT / "reports" / "rq7"
TS = ROOT / "reports" / "table-size"
SEATS = (3, 4, 6, 8)
CORE_LABEL = {"aof/4max/8bb": "AoF 4-max 8BB", "nlhe/4max/100bb": "NLHE 4-max", "nlhe/6max/100bb": "NLHE 6-max",
              "cp/6max/100bb": "Crazy Pineapple", "nit/6max/100bb": "Nit Game", "plo/6max/100bb": "PLO",
              "bomb/6max/100bb": "Bomb Pot"}
DELTAS = (0.25, 0.5, 1.0, 2.0, 5.0)
CHECKS: list[str] = []


def check(cond: bool, what: str) -> None:
    if not cond:
        raise AssertionError(f"frozen-source invariant failed: {what}")
    CHECKS.append(what)


def close(a: float, b: float, rel: float = 1e-6) -> bool:  # hands are stored rounded to whole hands
    return math.isclose(a, b, rel_tol=rel, abs_tol=1e-12)


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / name, comment="#")


def ranking() -> dict:
    return json.loads((FA / "ranking.json").read_text())


# ------------------------------------------------------------------ F1
def f1() -> tuple[pd.DataFrame, dict]:
    """Played hands at the five canonical effects, per format x role, from the core table."""
    rows = []
    with (FA / "core" / "pilot_table.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["format"] in CORE_LABEL and r["pairing_id"][:2] in ("p1", "p2", "p3"):
                for dl in DELTAS:
                    rows.append({"format": CORE_LABEL[r["format"]], "role": r["pairing_id"][:2], "delta": dl,
                                 "hands": float(r[f"hands_{dl:g}bb100_p80"])})
    df = pd.DataFrame(rows)
    rk = ranking()["metric"]["hands"]
    inv = {v: k for k, v in CORE_LABEL.items()}
    for f, g in df[df.delta == 1.0].groupby("format"):
        check(close(g.hands.median(), rk["formats"][inv[f]]["median"]), f"F1 median hands at 1 BB/100 = ranking.json ({f})")
    spread = {"full": rk["largest_over_smallest_median"], "100bb": rk["largest_over_smallest_median_100bb_excl_nit"]}
    med = df[df.delta == 1.0].groupby("format").hands.median()
    check(close(med.max() / med.min(), spread["full"]), "F1 full-suite spread recomputed = ranking.json")
    m100 = med[["NLHE 4-max", "NLHE 6-max", "Crazy Pineapple", "PLO", "Bomb Pot"]]
    check(close(m100.max() / m100.min(), spread["100bb"]), "F1 100BB spread recomputed = ranking.json")
    return df, spread


# ------------------------------------------------------------------ F2
def f2() -> tuple[pd.DataFrame, dict]:
    df = read("F2_cost_by_metric.csv")
    rk = ranking()["metric"]
    inv = {v: k for k, v in CORE_LABEL.items()}
    key = {"independent blocks": "blocks", "played hands": "hands", "wall-clock hours (8 workers, measured)": "wall_h"}
    for (fmt, metric), g in df.groupby(["format", "metric"]):
        pts = g[g.role != "median"].value
        med = float(g[g.role == "median"].value.iloc[0])
        check(close(np.median(pts), med), f"F2 median = median of pairings ({fmt}, {metric})")
        check(close(med, rk[key[metric]]["formats"][inv[fmt]]["median"]), f"F2 median = ranking.json ({fmt}, {metric})")
    ratios = {m: rk[key[m]]["largest_over_smallest_median"] for m in key}
    return df, ratios


# ------------------------------------------------------------------ F3
def f3(grid_n: int = 160) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Median and min/max over pairings of the concentration curve on a common log grid."""
    df = read("F3_variance_concentration.csv")
    gauss = df[df.format == "Gaussian reference"].sort_values("top_fraction")
    df = df[df.format != "Gaussian reference"]
    grid = np.logspace(-4, 0, grid_n)  # every corpus has >= 10k blocks, so 1e-4 is the first common point
    out = []
    for fmt, g in df.groupby("format"):
        curves = []
        for role, h in g.groupby("role"):
            h = h.sort_values("top_fraction")
            check(h.cumulative_share_sq_dev.is_monotonic_increasing, f"F3 curve monotone ({fmt} {role})")
            curves.append(np.interp(np.log10(grid), np.log10(h.top_fraction), h.cumulative_share_sq_dev))
        c = np.vstack(curves)
        for x, lo, md, hi in zip(grid, c.min(0), np.median(c, 0), c.max(0), strict=True):
            out.append({"format": fmt, "top_fraction": x, "lo": lo, "median": md, "hi": hi})
    res = pd.DataFrame(out)
    # the plotted top-1% values must agree with the frozen core concentration statistic
    core = pd.read_csv(FA / "core" / "pilot_table.csv")
    top1 = {}
    for fmt, lab in {v: k for k, v in CORE_LABEL.items()}.items():
        vals = core[(core.format == lab) & core.pairing_id.str[:2].isin(["p1", "p2", "p3"])]["conc_top0.01"]
        top1[fmt] = float(np.median(vals))  # the exact frozen statistic, used for the labels
        at = res[(res.format == fmt)].iloc[(res[res.format == fmt].top_fraction - 0.01).abs().argsort().iloc[0]]
        check(abs(at["median"] - top1[fmt]) < 0.03, f"F3 interpolated curve at 1% agrees with core conc_top0.01 ({fmt})")
    return res, gauss, top1


# ------------------------------------------------------------------ F4
def f4() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    a = read("F4a_bigpot_frequency_magnitude.csv")
    al = pd.read_csv(FA / "allin.csv")
    back = {v: k for k, v in CORE_LABEL.items()} | {"NLHE 6-max 20BB": "nlhe/6max/20bb", "NLHE 6-max 50BB": "nlhe/6max/50bb"}
    for _, r in a.iterrows():
        src = al[(al.format == back[r.format]) & (al.pairing_id.str[:2] == r.role)].iloc[0]
        check(close(r.share_sq_dev_big_pot, src.share_pot_ge_1stack) and close(r.frac_blocks_big_pot, src.frac_blocks_pot_ge_1stack),
              f"F4a = allin.csv ({r.format} {r.role})")
    b = read("F4b_stack_depth.csv")
    st = json.loads((FA / "stack.json").read_text())
    for _, r in b[b.stack_bb != 100].iterrows():
        lab = f"nlhe/6max/{int(r.stack_bb)}bb"
        check(close(r.sd_ratio_vs_100, st[r.role][lab]["sd_ratio_vs_100_common"]), f"F4b sd ratio = stack.json ({r.role} {lab})")
    mult = {sb: sorted(1 / b[(b.stack_bb == sb)].blocks_needed_vs_100) for sb in (20, 50)}
    return a, b, mult


# ------------------------------------------------------------------ F5
def f5() -> tuple[pd.DataFrame, pd.DataFrame, float]:
    d = read("F5_variance_reduction.csv")
    s = pd.read_csv(R6 / "rq6_summary.csv")
    lab = {"AoF 8BB: all-in EV": ("aof4-8bb", "allin_ev"), "NLHE 20BB: all-in EV": ("nlhe6-20bb", "allin_ev"),
           "NLHE 100BB: all-in EV": ("nlhe6-100bb", "allin_ev"), "NLHE 100BB: MIVAT": ("nlhe6-100bb", "mivat"),
           "NLHE 100BB: AIVAT": ("nlhe6-100bb", "aivat")}
    for _, r in d.iterrows():
        st, est = lab[r.row]
        src = s[(s.setting == st) & (s.estimator == est) & (s.pairing_id.str[:2] == r.role)].iloc[0]
        check(close(r.var_ratio, src.var_ratio_vs_raw) and close(r.ci_lo, src.var_ratio_ci_lo) and close(r.ci_hi, src.var_ratio_ci_hi),
              f"F5 ratio + CI = rq6_summary.csv ({r.row} {r.role})")
    ins = read("F5_inset_aof_p1.csv")
    deep = json.loads((R6 / "deep" / "rq6_deep.json").read_text())["settings"]["aof4-8bb"]["pairings"]["p1-prodv2-vs-blend10"]["precision"]
    for _, r in ins.iterrows():
        check(close(r.mean_bb100, deep[r.estimator]["mean_bb100"]) and close(r.ci_lo, deep[r.estimator]["ci95_bb100"][0]),
              f"F5 inset = rq6_deep.json ({r.estimator})")
    return d, ins, float(deep["allin_ev"]["raw_blocks_for_same_se"])


# ------------------------------------------------------------------ F6
def f6() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    a = read("F6a_false_exclusion.csv")
    cov = pd.read_csv(R7 / "coverage.csv")
    per = pd.read_csv(R7 / "real_permutations.csv")
    mname = {"fixed": "fixed-N (one look)", "peek": "naive peeking", "asymp": "confidence sequence"}
    dname = {"heavy": "NLHE 6-max p1 (heavy)", "moderate": "Crazy Pineapple p2", "mild": "PLO p3", "normal": "Normal", "t3": "Student t3"}
    for _, r in cov.iterrows():
        row = a[(a.group == dname[r.distribution]) & (a.method == mname[r.method])].iloc[0]
        check(close(row.rate, r.miscoverage) and close(row.wilson_lo, r.wilson_lo), f"F6a = coverage.csv ({r.distribution} {r.method})")
    for _, r in per.iterrows():
        row = a[(a.group == "Real orderings of NLHE 6-max p1") & (a.method == mname[r.method])].iloc[0]
        check(close(row.rate, r.miscoverage), f"F6a = real_permutations.csv ({r.method})")
    tr = read("F6b_trajectory_nlhe6_p2.csv")
    mk = read("F6b_markers.csv")
    ro = pd.read_csv(R7 / "deep" / "real_orderings_sign.csv")
    full = ro[(ro.experiment_id == "fhr3-nlhe6-100bb-pilot-v1") & (ro.pairing_id == "p2-neutral-vs-tight")].iloc[0]
    end = tr.iloc[-1]
    check(int(end.blocks) == 250000, "F6b trajectory ends at the full 250k corpus")
    check(close(end.mean_bb100, 100 * full.full_mean_block / 6), "F6b final running mean = full-corpus mean (real_orderings_sign)")
    seq = pd.read_csv(R7 / "real_orderings.csv")
    pk = seq[(seq.experiment_id == "fhr3-nlhe6-100bb-pilot-v1") & (seq.pairing_id == "p2-neutral-vs-tight") & (seq.method == "peek")].iloc[0]
    stop = mk[mk.marker == "naive peeking stop"].iloc[0]
    check(int(stop.blocks) == int(pk.stopping_time) == 204, "F6b naive stop at block 204 (real_orderings.csv)")
    lo, hi = json.loads(pk.interval_bb100)
    check(close(stop.lo, lo) and close(stop.hi, hi), "F6b naive-stop interval = real_orderings.csv")
    return a, tr, mk, {"full_z": float(full.full_z)}


# ------------------------------------------------------------------ F7 (FHR3A controlled table-size suite)
def _sha(p: Path) -> str:
    import hashlib

    return hashlib.sha256(p.read_bytes()).hexdigest()


def _ci(cell: str) -> list[float]:
    return [float(x) for x in str(cell).split(";")]


def f7() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """a: required hands / blocks relative to controlled 6-max; b: mechanism indices vs 3-max."""
    man = json.loads((TS / "MANIFEST.json").read_text())
    for name, h in man["outputs"].items():
        check(_sha(TS / name) == h, f"F7 reports/table-size/{name} sha256 = table-size MANIFEST")
    deep = json.loads((TS / "deep" / "deep.json").read_text())
    check(deep["primary_manifest_sha256"] == _sha(TS / "MANIFEST.json"), "F7 deep.json derived from this table-size MANIFEST")
    series = ["p1", "p2", "p3", "median"]

    a = read("F7a_table_size_burden.csv")
    check(a.notna().all().all(), "F7a no NaN")
    check(sorted(a.seats.unique()) == list(SEATS) and set(a.series) == set(series) and len(a) == 16
          and not a.duplicated(["seats", "series"]).any(), "F7a all 4 table sizes x p1/p2/p3/median, no duplicates")
    six = a[a.seats == 6]
    check(bool((six[["hands_rel_6max", "hands_rel_6max_lo", "hands_rel_6max_hi", "blocks_rel_6max",
                     "blocks_rel_6max_lo", "blocks_rel_6max_hi"]] == 1.0).all().all()), "F7a 6-max ratios exactly 1")
    fd = pd.read_csv(TS / "figure_data.csv")
    sm = pd.read_csv(TS / "summary.csv")
    summ = json.loads((TS / "summary.json").read_text())["primary_controlled"]
    for _, r in a.iterrows():
        f = fd[(fd.seats == r.seats) & (fd.series == r.series)].iloc[0]
        check(close(r.hands_rel_6max, f.hands_rel_6max, 1e-9) and close(r.hands_rel_6max_lo, f.hands_rel_6max_lo, 1e-9)
              and close(r.hands_rel_6max_hi, f.hands_rel_6max_hi, 1e-9) and r.hands_required == f.hands_required,
              f"F7a {r.seats}-max {r.series} hands ratio + CI = reports/table-size/figure_data.csv")
        if r.series == "median":
            m = summ["medians"][str(r.seats)]
            check(close(r.hands_rel_6max, m["hands_required_1bb100_rel_base"], 1e-9)
                  and np.allclose([r.hands_rel_6max_lo, r.hands_rel_6max_hi], m["hands_required_1bb100_rel_base_ci"], rtol=1e-9)
                  and close(r.blocks_rel_6max, m["blocks_required_1bb100_rel_base"], 1e-9)
                  and np.allclose([r.blocks_rel_6max_lo, r.blocks_rel_6max_hi], m["blocks_required_1bb100_rel_base_ci"], rtol=1e-9)
                  and r.hands_required == m["hands_required_1bb100"],
                  f"F7a {r.seats}-max median hands/blocks ratios + CIs = summary.json")
        else:
            s_ = sm[(sm.seats == r.seats) & (sm.role == r.series)].iloc[0]
            check(close(r.blocks_rel_6max, s_.blocks_required_1bb100_rel_6max, 1e-9)
                  and np.allclose([r.blocks_rel_6max_lo, r.blocks_rel_6max_hi], _ci(s_.blocks_required_1bb100_rel_6max_ci), rtol=1e-9),
                  f"F7a {r.seats}-max {r.series} blocks ratio + CI = summary.csv")
            # hands = 2k x blocks  =>  hands ratio = blocks ratio x k / 6
            check(close(r.hands_rel_6max, r.blocks_rel_6max * r.seats / 6, 1e-9), f"F7a {r.seats}-max {r.series} hands = blocks x k/6")
        check(r.hands_per_block == 2 * r.seats, f"F7a {r.seats}-max {r.series} 2k hands per block")
    el = summ["elasticity_hands_vs_seats"]["median"]
    info = {"elasticity": el["overall"], "elasticity_ci": el["overall_ci"]}
    claims = json.loads((TS / "claims.json").read_text())["claims"]
    ts1 = next(c for c in claims if c["id"] == "TS1")["values"]["elasticity_median"]
    check(round(el["overall"], 3) == ts1[0] and [round(x, 3) for x in el["overall_ci"]] == ts1[1], "F7a elasticity = claims.json TS1")

    b = read("F7b_table_size_mechanism.csv")
    q = ["p_seat_diverges", "seat_dev2_given_diverge", "seat_var_mean", "big_blocks_per_played_hand"]
    check(b.notna().all().all() and len(b) == 16 and not b.duplicated(["seats", "series"]).any(), "F7b complete, no NaN, no duplicates")
    check(bool((b[b.seats == 3][[f"{x}_index" for x in q]] == 1.0).all().all()), "F7b 3-max indices exactly 1")
    mech = {(r["seats"], r["role"]): r for r in deep["mechanism"]}
    mcsv = pd.read_csv(TS / "deep" / "mechanism.csv")
    for _, r in b[b.series != "median"].iterrows():
        mc = mcsv[(mcsv.seats == r.seats) & (mcsv.role == r.series)].iloc[0]
        for x in q:
            check(close(r[x], mech[(r.seats, r.series)][x], 1e-12) and close(r[x], mc[x], 1e-5),
                  f"F7b {r.seats}-max {r.series} {x} = deep.json / mechanism.csv")
    ms = pd.read_csv(TS / "deep" / "mechanism_scaling.csv")
    for x in q:
        row = ms[(ms.quantity == x) & (ms.series == "median")].iloc[0]
        med8 = b[(b.seats == 8) & (b.series == "median")].iloc[0]
        check(close(med8[f"{x}_index"], row.ratio_8_over_3, 1e-5), f"F7b median {x} 8/3 index = mechanism_scaling.csv")
    return a, b, info
