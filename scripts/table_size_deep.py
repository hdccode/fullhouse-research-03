"""FHR3A controlled table-size suite: deep analysis of the completed 3/4/6/8-max corpora (reads
Parquet + the frozen reports/table-size outputs; never re-runs poker; never writes the primary
outputs). Scientific write-up: reports/table-size/ANALYSIS.md.

Usage: .venv/bin/python scripts/table_size_deep.py [--boot 1000]  ->  reports/table-size/deep/

Before computing anything new it re-derives the primary per-pairing sigma_D / required hands and
the median-series elasticity with the primary script's own bootstrap seeds and asserts they equal
reports/table-size/summary.json.

Outputs (reports/table-size/deep/)
  power_laws.csv          y ~ k^beta (log-log OLS over k = 3,4,6,8) for sigma_D, var, blocks, hands,
                          per pairing + median series; bootstrap CI; P(beta_hands > 0); curvature
  heterogeneity.csv       pairwise differences of the hands elasticity between pairings (bootstrap)
  mechanism.csv           per k x pairing: seat-level decomposition var(D) = k*vbar + covariance,
                          per-candidate-hand divergence rate and conditional magnitude, big-pot /
                          all-in frequency (per block and per played hand), magnitude and variance
                          contributions of big-pot vs other blocks
  mechanism_scaling.csv   beta of each mechanism quantity in k (per pairing + median)
  seat_position.csv       var(D_s) by candidate position (appendix)
  prefix.csv              10k / 20k / 30k prefixes and three disjoint 10k windows: medians, ratios,
                          elasticity (point + CI)
  endpoints.csv           8-max / 3-max ratios of sigma, blocks, hands (per pairing + median, bootstrap CI)
  historical.csv          controlled vs historical 4/6: paired population effect at fixed k and the
                          reconciliation of the historical 6/4 ratio with the controlled one
  deep.json               everything above + consistency checks + git SHA
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import subprocess
from pathlib import Path

import numpy as np
import pyarrow.compute as pc
from scipy import stats as sps

from fhr3.io.store import read_blocks

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tsa", ROOT / "scripts" / "table_size_analysis.py")
tsa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tsa)

SEATS = tsa.SEATS
ROLES = tsa.ROLES
Z80 = tsa.Z80
TS = ROOT / "reports" / "table-size"
OUT = TS / "deep"
LK = np.log(np.array(SEATS, float))
XC = LK - LK.mean()
COLS = ["pairing_id", "block_id", "D", "seat_D", "allin_hands", "pot_bb_max", "played_hands", "decision_count",
        "showdown_hands"]


def slope(y: np.ndarray) -> np.ndarray | float:
    """OLS slope of y on log k; y has len(SEATS) rows (and optionally a bootstrap axis)."""
    if y.ndim == 2:
        return (XC[:, None] * (y - y.mean(axis=0))).sum(axis=0) / (XC ** 2).sum()
    return float((XC * (y - y.mean())).sum() / (XC ** 2).sum())


def curvature(y: np.ndarray) -> np.ndarray | float:
    """Quadratic coefficient c in y = a + b log k + c (log k)^2 (4 points; descriptive only)."""
    X = np.column_stack([np.ones_like(LK), LK, LK ** 2])
    coef = np.linalg.lstsq(X, y, rcond=None)[0]
    return coef[2] if y.ndim == 2 else float(coef[2])


def q(x) -> list[float]:
    return [float(np.quantile(x, 0.025)), float(np.quantile(x, 0.975))]


def load() -> dict:
    data = {}
    for k in SEATS:
        _, exp = tsa.SUITE[k]
        t = read_blocks(ROOT / "results" / exp, columns=COLS)
        for role in ROLES:
            pid = next(p for p in set(t.column("pairing_id").to_pylist()) if p.startswith(role + "-"))
            tp = t.filter(pc.equal(t.column("pairing_id"), pid))
            o = np.argsort(tp.column("block_id").to_numpy())
            col = lambda c: np.asarray(tp.column(c).to_numpy(zero_copy_only=False))[o]  # noqa: E731
            seat = np.array(tp.column("seat_D").to_pylist(), float)[o]
            data[(k, role)] = {"pid": pid, "D": col("D").astype(float), "seat": seat, "allin": col("allin_hands"),
                               "potmax": col("pot_bb_max").astype(float), "played": col("played_hands").astype(float),
                               "decisions": col("decision_count").astype(float),
                               "showdown": col("showdown_hands").astype(float)}
    return data


def hist_load() -> dict:
    out = {}
    for k, (_, exp, _) in tsa.HISTORICAL.items():
        t = read_blocks(ROOT / "results" / exp, columns=["pairing_id", "block_id", "D"])
        for role in ROLES:
            pid = next(p for p in set(t.column("pairing_id").to_pylist()) if p.startswith(role + "-"))
            tp = t.filter(pc.equal(t.column("pairing_id"), pid))
            o = np.argsort(tp.column("block_id").to_numpy())
            out[(k, role)] = np.asarray(tp.column("D").to_numpy(zero_copy_only=False), float)[o]
    return out


# ------------------------------------------------------------------ consistency with the frozen primary outputs
def primary_boot(data: dict, reps: int) -> dict:
    """Bootstrap SDs with the primary script's seeds (identical draws)."""
    return {(k, r): tsa.boot_sds(d["D"], reps, (20261101, k, ROLES.index(r))) for (k, r), d in data.items()}


def consistency(data: dict, sds: dict, checks: list[str]) -> None:
    summ = json.loads((TS / "summary.json").read_text())["primary_controlled"]
    rows = {(r["seats"], r["role"]): r for r in summ["per_pairing"]}
    for (k, role), d in data.items():
        sd = float(d["D"].std(ddof=1))
        assert math.isclose(sd, rows[(k, role)]["sigma_D"], rel_tol=1e-12), (k, role)
        assert tsa.blocks_needed(sd, k) * 2 * k == rows[(k, role)]["hands_required_1bb100"]
    checks.append("sigma_D and required hands of all 12 pairings = summary.json")
    hands_b = np.stack([np.median(np.stack([(Z80 * sds[(k, r)] / (k / 100)) ** 2 * 2 * k for r in ROLES]), axis=0)
                        for k in SEATS])
    pt = np.log([np.median([rows[(k, r)]["hands_required_1bb100"] for r in ROLES]) for k in SEATS])
    e_ref = summ["elasticity_hands_vs_seats"]["median"]
    assert math.isclose(slope(pt), e_ref["overall"], rel_tol=1e-9)
    assert np.allclose(q(slope(np.log(hands_b))), e_ref["overall_ci"], rtol=1e-9)
    checks.append(f"median elasticity {e_ref['overall']:+.3f} and CI reproduced from the primary bootstrap draws")


# ------------------------------------------------------------------ power laws, heterogeneity
def power_laws(data: dict, sds: dict) -> tuple[list[dict], list[dict], dict]:
    rows, draws = [], {}
    for name in [*ROLES, "median"]:
        if name == "median":
            sd_pt = np.array([np.median([data[(k, r)]["D"].std(ddof=1) for r in ROLES]) for k in SEATS])
            sd_b = np.stack([np.median(np.stack([sds[(k, r)] for r in ROLES]), axis=0) for k in SEATS])
        else:
            sd_pt = np.array([data[(k, name)]["D"].std(ddof=1) for k in SEATS])
            sd_b = np.stack([sds[(k, name)] for k in SEATS])
        kk = np.array(SEATS, float)[:, None]
        quantities = {  # continuous forms: blocks = (Z sd / (k/100))^2, hands = 2k * blocks
            "sigma_D": (sd_pt, sd_b),
            "var_D": (sd_pt ** 2, sd_b ** 2),
            "blocks_required": ((Z80 * sd_pt / (kk[:, 0] / 100)) ** 2, (Z80 * sd_b / (kk / 100)) ** 2),
            "hands_required": (2 * kk[:, 0] * (Z80 * sd_pt / (kk[:, 0] / 100)) ** 2, 2 * kk * (Z80 * sd_b / (kk / 100)) ** 2),
            "hands_per_block": (2 * kk[:, 0], None),
        }
        for qn, (pt, b) in quantities.items():
            r = {"series": name, "quantity": qn, "beta": slope(np.log(pt))}
            if b is not None:
                bb = slope(np.log(b))
                r |= {"beta_ci": q(bb), "p_beta_gt_0": float(np.mean(bb > 0)),
                      "curvature": curvature(np.log(pt)), "curvature_ci": q(curvature(np.log(b)))}
                if qn == "hands_required":
                    draws[name] = bb
            else:
                r |= {"beta_ci": [r["beta"], r["beta"]], "p_beta_gt_0": 1.0, "curvature": 0.0, "curvature_ci": [0.0, 0.0]}
            rows.append(r)
    het = []
    for i, a in enumerate(ROLES):
        for b in ROLES[i + 1:]:
            d = draws[a] - draws[b]
            het.append({"a": a, "b": b, "diff_beta_hands": float(np.median(d)), "ci": q(d),
                        "p_abs_diff_gt_0.25": float(np.mean(np.abs(d) > 0.25))})
    return rows, het, draws


def endpoints(data: dict, sds: dict) -> list[dict]:
    """8-max / 3-max ratios with the primary bootstrap draws (corpora independent)."""
    out = []
    for name in [*ROLES, "median"]:
        def sd(k):
            if name == "median":
                return (np.median([data[(k, r)]["D"].std(ddof=1) for r in ROLES]),
                        np.median(np.stack([sds[(k, r)] for r in ROLES]), axis=0))
            return data[(k, name)]["D"].std(ddof=1), sds[(k, name)]
        (s3, b3), (s8, b8) = sd(3), sd(8)
        row = {"series": name}
        for qn, f in (("sigma", 1.0), ("blocks", (3 / 8) ** 2), ("hands", (3 / 8) ** 2 * 8 / 3)):
            p = 1 if qn == "sigma" else 2
            row[f"{qn}_8_over_3"] = float((s8 / s3) ** p * f)
            row[f"{qn}_8_over_3_ci"] = q((b8 / b3) ** p * f)
        out.append(row)
    return out


# ------------------------------------------------------------------ mechanism
def mechanism(data: dict) -> tuple[list[dict], list[dict]]:
    rows, pos = [], []
    for (k, role), d in sorted(data.items()):
        D, S = d["D"], d["seat"]
        n = D.size
        var = D.var(ddof=1)
        cov = np.cov(S, rowvar=False)
        vbar = float(np.mean(np.diag(cov)))            # mean per-seat variance (one candidate seat, A-B)
        cov_sum = float(cov.sum() - np.trace(cov))     # sum of cross-seat covariances
        nz = S != 0
        dev2 = (D - D.mean()) ** 2
        big = d["potmax"] > 100 - 1e-9
        allin = d["allin"] > 0
        r = {
            "seats": k, "role": role, "pairing_id": d["pid"], "n_blocks": n, "hands_per_block": 2 * k,
            "var_D": float(var), "var_per_candidate_hand": float(var / k),
            "seat_var_mean": vbar, "seat_var_sum": float(np.trace(cov)), "seat_cov_sum": cov_sum,
            "cov_share_of_var": cov_sum / float(cov.sum()),
            "p_seat_diverges": float(nz.mean()),                           # P(D_s != 0) per candidate seat-hand pair
            "seat_dev2_given_diverge": float((S[nz] ** 2).mean()),         # E[D_s^2 | D_s != 0]
            "p_block_D_zero": float(np.mean(D == 0)),
            "excess_kurtosis": float(sps.kurtosis(D)),
            "top1pct_share": tsa.variance_concentration(D, (0.01,))["0.01"],
            "frac_blocks_big": float(big.mean()), "share_big": float(dev2[big].sum() / dev2.sum()),
            "mean_dev2_big_block": float(dev2[big].mean()), "mean_dev2_other_block": float(dev2[~big].mean()),
            "var_contrib_big": float(dev2[big].sum() / (n - 1)), "var_contrib_other": float(dev2[~big].sum() / (n - 1)),
            "frac_blocks_allin": float(allin.mean()), "share_allin": float(dev2[allin].sum() / dev2.sum()),
            "allin_hands_per_played_hand": float(d["allin"].sum() / d["played"].sum()),
            "big_blocks_per_played_hand": float(big.mean() / (2 * k)),
            "decisions_per_played_hand": float(d["decisions"].sum() / d["played"].sum()),
            "showdowns_per_played_hand": float(d["showdown"].sum() / d["played"].sum()),
        }
        rows.append(r)
        names = {3: ["SB", "BB", "BTN"], 4: ["SB", "BB", "CO", "BTN"], 6: ["SB", "BB", "UTG", "HJ", "CO", "BTN"],
                 8: ["SB", "BB", "UTG", "UTG+1", "LJ", "HJ", "CO", "BTN"]}[k]
        for s in range(k):
            pos.append({"seats": k, "role": role, "seat": s, "position": names[s], "var_D_s": float(cov[s, s]),
                        "share_of_seat_var_sum": float(cov[s, s] / np.trace(cov)), "p_diverge": float(nz[:, s].mean())})
    return rows, pos


def mechanism_scaling(mech: list[dict]) -> list[dict]:
    qs = ["var_D", "var_per_candidate_hand", "seat_var_mean", "seat_cov_sum", "cov_share_of_var", "p_seat_diverges",
          "seat_dev2_given_diverge", "p_block_D_zero", "excess_kurtosis", "top1pct_share", "frac_blocks_big", "share_big",
          "mean_dev2_big_block", "mean_dev2_other_block", "var_contrib_big", "var_contrib_other", "frac_blocks_allin",
          "share_allin", "allin_hands_per_played_hand", "big_blocks_per_played_hand", "decisions_per_played_hand",
          "showdowns_per_played_hand"]
    by = {(r["seats"], r["role"]): r for r in mech}
    out = []
    for qn in qs:
        for name in [*ROLES, "median"]:
            vals = np.array([by[(k, name)][qn] if name != "median" else np.median([by[(k, r)][qn] for r in ROLES])
                             for k in SEATS])
            row = {"quantity": qn, "series": name, **{f"k{k}": float(v) for k, v in zip(SEATS, vals)}}
            row["beta"] = slope(np.log(vals)) if np.all(vals > 0) else float("nan")
            row["ratio_8_over_3"] = float(vals[-1] / vals[0]) if vals[0] else float("nan")
            out.append(row)
    return out


# ------------------------------------------------------------------ prefixes and windows
def prefixes(data: dict, reps: int) -> list[dict]:
    out = []
    specs = [("prefix", 0, 10000), ("prefix", 0, 20000), ("prefix", 0, 30000),
             ("window", 0, 10000), ("window", 10000, 20000), ("window", 20000, 30000)]
    for kind, a, b in specs:
        pts, bs = {}, {}
        for (k, r), d in data.items():
            x = d["D"][a:b]
            pts[(k, r)] = (Z80 * x.std(ddof=1) / (k / 100)) ** 2 * 2 * k
            bs[(k, r)] = (Z80 * tsa.boot_sds(x, reps, (20261104, k, ROLES.index(r), a, b)) / (k / 100)) ** 2 * 2 * k
        med = {k: np.median([pts[(k, r)] for r in ROLES]) for k in SEATS}
        medb = np.stack([np.median(np.stack([bs[(k, r)] for r in ROLES]), axis=0) for k in SEATS])
        row = {"kind": kind, "blocks": f"{a}:{b}", "n": b - a,
               **{f"hands_M_k{k}": float(med[k] / 1e6) for k in SEATS},
               **{f"hands_rel6_k{k}": float(med[k] / med[6]) for k in SEATS},
               "elasticity_median": slope(np.log([med[k] for k in SEATS])),
               "elasticity_median_ci": q(slope(np.log(medb)))}
        for r in ROLES:
            row[f"elasticity_{r}"] = slope(np.log([pts[(k, r)] for k in SEATS]))
        out.append(row)
    return out


# ------------------------------------------------------------------ controlled vs historical
def historical(data: dict, hist: dict, reps: int) -> list[dict]:
    out = []
    rng = np.random.default_rng(20261105)
    n = 30000
    idx = [rng.integers(0, n, n) for _ in range(reps)]
    stat = {}
    for k in (4, 6):
        for r in ROLES:
            c, h = data[(k, r)]["D"][:n], hist[(k, r)][:n]
            stat[(k, r)] = {"c": c.std(ddof=1), "h": h.std(ddof=1), "hfull": hist[(k, r)].std(ddof=1),
                            "cb": np.array([c[i].std(ddof=1) for i in idx]), "hb": np.array([h[i].std(ddof=1) for i in idx])}
    # paired population effect at fixed k (same deals), and the 6/4 hands ratio under each population
    for r in [*ROLES, "median"]:
        def get(k, key):
            if r == "median":
                return np.median(np.stack([np.atleast_1d(stat[(k, x)][key]) for x in ROLES]), axis=0)
            return np.atleast_1d(stat[(k, r)][key])
        row = {"series": r}
        for k in (4, 6):
            pe = (get(k, "c") / get(k, "h")) ** 2
            peb = (get(k, "cb") / get(k, "hb")) ** 2
            row[f"hands_ratio_controlled_over_historical_k{k}"] = float(pe[0])
            row[f"hands_ratio_controlled_over_historical_k{k}_ci"] = q(peb)
        # hands 6/4 = (sd6/sd4)^2 * 6/4 ... hands = 2k (Z sd / (k/100))^2  ->  hands6/hands4 = (sd6/sd4)^2 * (4/6)
        c64 = (get(6, "c") / get(4, "c")) ** 2 * 4 / 6
        h64 = (get(6, "h") / get(4, "h")) ** 2 * 4 / 6
        hfull64 = (get(6, "hfull") / get(4, "hfull")) ** 2 * 4 / 6
        c64b = (get(6, "cb") / get(4, "cb")) ** 2 * 4 / 6
        h64b = (get(6, "hb") / get(4, "hb")) ** 2 * 4 / 6
        row |= {"hands_6_over_4_controlled_30k": float(c64[0]), "hands_6_over_4_controlled_30k_ci": q(c64b),
                "hands_6_over_4_historical_first30k": float(h64[0]), "hands_6_over_4_historical_first30k_ci": q(h64b),
                "hands_6_over_4_historical_full": float(hfull64[0]),
                # the population term: how much of controlled-vs-historical 6/4 is the population change
                "population_term_ratio": float(c64[0] / h64[0]), "population_term_ratio_ci": q(c64b / h64b)}
        out.append(row)
    return out


def _cell(v):
    if isinstance(v, list):
        return ";".join(f"{x:.6g}" for x in v)
    if isinstance(v, float):
        return f"{v:.6g}"
    return v


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows([{k: _cell(v) for k, v in r.items()} for r in rows])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    checks: list[str] = []
    data = load()
    sds = primary_boot(data, a.boot)
    consistency(data, sds, checks)
    pl, het, _ = power_laws(data, sds)
    mech, pos = mechanism(data)
    for r in mech:  # seat identity: var(D) = sum of seat variances + covariances
        assert math.isclose(r["seat_var_sum"] + r["seat_cov_sum"], r["var_D"], rel_tol=1e-9)
    checks.append("var(D) = sum var(D_s) + sum cov(D_s, D_t) for all 12 pairings")
    ms = mechanism_scaling(mech)
    pre = prefixes(data, max(200, a.boot // 2))
    hi = historical(data, hist_load(), a.boot)
    files = {"power_laws.csv": pl, "heterogeneity.csv": het, "endpoints.csv": endpoints(data, sds), "mechanism.csv": mech, "mechanism_scaling.csv": ms,
             "seat_position.csv": pos, "prefix.csv": pre, "historical.csv": hi}
    for name, rows in files.items():
        write_csv(OUT / name, rows)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    deep = {"description": "Deep analysis of the controlled table-size suite (derived; primary outputs untouched).",
            "analysis_code_git_sha": sha, "bootstrap_reps": a.boot, "checks": checks,
            "primary_manifest_sha256": hashlib.sha256((TS / "MANIFEST.json").read_bytes()).hexdigest(),
            **{k.removesuffix(".csv"): v for k, v in files.items()}}
    (OUT / "deep.json").write_text(json.dumps(deep, indent=1, default=float) + "\n")
    print(f"checks: {checks}\nwrote {OUT}/{{{','.join(files)},deep.json}}")


if __name__ == "__main__":
    main()
