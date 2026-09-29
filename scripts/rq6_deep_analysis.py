"""RQ6 deep analysis (read-only on Parquet): estimator-vs-estimator paired ratios, tails and
the big-pot decomposition after correction, hands at 80%/95% power, the AoF p1 precision
comparison, the 100BB-vs-20BB dose-response, and net wall-clock efficiency.

Usage: .venv/bin/python scripts/rq6_deep_analysis.py [--out reports/rq6/deep] [--boot 2000]

Every comparison is paired on the same matched blocks (joint block bootstrap). Outputs in
<out>: rq6_pairwise.csv, rq6_tails.csv, rq6_hands.csv, rq6_efficiency.csv, rq6_deep.json and
SHA256SUMS (kept outside the patterns frozen by reports/rq6/MANIFEST.json).

Compute cost: per-estimator slowdowns come from ESTIMATOR_BENCH below. These are
single-process ``fhr3 bench`` measurements (3 runs x 150-200 blocks per configuration,
2026-09-29, same machine as the runs; configs differ only in the ``estimators:`` block).
They are cross-checked against the measured 8-worker aggregate throughput of the actual
runs (the all-estimator NLHE100 run and the AoF all-in EV run).
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
from pathlib import Path

import numpy as np
import pyarrow.compute as pc
from scipy import stats as sps

from fhr3.analysis.stats import required_blocks, variance_concentration
from fhr3.io.store import read_blocks

SETTINGS = [
    ("nlhe6-100bb", "results/fhr3-nlhe6-100bb-rq6-v1-fittedvf", "results/fhr3-nlhe6-100bb-pilot-v1", 100.0),
    ("nlhe6-20bb", "results/fhr3-nlhe6-20bb-rq6-allin-v1", "results/fhr3-nlhe6-20bb-v1", 20.0),
    ("aof4-8bb", "results/fhr3-aof4-8bb-rq6-allin-v1", "results/fhr3-aof4-8bb-pilot-v1", 8.0),
]
ESTS = ("raw", "allin_ev", "mivat", "aivat")
PAIRWISE = [("allin_ev", "raw"), ("mivat", "raw"), ("aivat", "raw"), ("mivat", "allin_ev"),
            ("aivat", "allin_ev"), ("aivat", "mivat")]
DELTAS = (0.25, 0.5, 1.0, 2.0, 5.0)
# single-process blocks/s: (raw, estimator-only) means of 3 bench runs; see module docstring
ESTIMATOR_BENCH = {
    ("nlhe6-100bb", "allin_ev"): (110.9, 104.4), ("nlhe6-100bb", "mivat"): (110.9, 78.3),
    ("nlhe6-100bb", "aivat"): (110.9, 59.5), ("nlhe6-100bb", "all_three"): (110.9, 49.9),
    ("nlhe6-20bb", "allin_ev"): (114.5, 113.7), ("aof4-8bb", "allin_ev"): (202.5, 119.0),
}


def col(t, c):
    return np.asarray(t.column(c).to_numpy(zero_copy_only=False))


def load(exp: str) -> dict:
    cols = ["config_hash", "pairing_id", "block_id", "valid", "D", "played_hands", "hands_a", "hands_b",
            "pot_bb_max", "allin_hands", "allin_ev_D", "mivat_D", "aivat_D"]
    t = read_blocks(exp, columns=cols)
    out = {}
    for pid in sorted(set(t.column("pairing_id").to_pylist())):
        if pid.startswith("c0-"):
            continue
        tp = t.filter(pc.and_(pc.equal(t.column("pairing_id"), pid), t.column("valid")))
        o = np.argsort(col(tp, "block_id"))
        d = {"raw": col(tp, "D").astype(float)[o]}
        for e in ("allin_ev", "mivat", "aivat"):
            v = col(tp, f"{e}_D")[o]
            if not any(x is None for x in v) and not np.isnan(v.astype(float)).any():  # disabled -> null/NaN
                d[e] = v.astype(float)
        d["k"] = float(np.mean((col(tp, "hands_a").astype(float) + col(tp, "hands_b").astype(float)) / 2))
        d["hpb"] = float(col(tp, "played_hands").astype(float).mean())
        d["potmax"] = col(tp, "pot_bb_max").astype(float)[o]
        d["allin"] = col(tp, "allin_hands")[o] > 0
        out[pid] = d
    return out


def boot_ratios(d: dict, pairs, reps: int, rng) -> dict:
    n = d["raw"].size
    acc = {p: [] for p in pairs}
    for s in range(0, reps, 50):
        idx = rng.integers(0, n, size=(min(50, reps - s), n))
        var = {e: d[e][idx].var(axis=1, ddof=1) for e in {x for p in pairs for x in p}}
        for a, b in pairs:
            acc[(a, b)].append(var[a] / var[b])
    return {p: np.concatenate(v) for p, v in acc.items()}


def tails(x: np.ndarray) -> dict:
    vc = variance_concentration(x, (0.01, 0.001))
    q = np.quantile(x, (0.0001, 0.001, 0.999, 0.9999))
    return {"excess_kurtosis": float(sps.kurtosis(x)), "skew": float(sps.skew(x)), "top1pct_share": vc["0.01"],
            "top0p1pct_share": vc["0.001"], "q0.0001": float(q[0]), "q0.001": float(q[1]), "q0.999": float(q[2]),
            "q0.9999": float(q[3]), "max_abs": float(np.abs(x - x.mean()).max()), "frac_zero": float(np.mean(x == 0))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/rq6/deep")
    ap.add_argument("--boot", type=int, default=2000)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261008)
    pw, tl, hd, ef = [], [], [], []
    deep: dict = {"settings": {}}
    boot_store: dict = {}
    for label, exp, ref, stack in SETTINGS:
        data = load(exp)
        bps_run = sum(json.load(open(f))["summary"]["blocks"] for f in glob.glob(f"{exp}/runs/*.json")) / \
            sum(json.load(open(f))["summary"]["wall_s"] for f in glob.glob(f"{exp}/runs/*.json"))
        bps_ref = sum(json.load(open(f))["summary"]["blocks"] for f in glob.glob(f"{ref}/runs/*.json")) / \
            sum(json.load(open(f))["summary"]["wall_s"] for f in glob.glob(f"{ref}/runs/*.json"))
        deep["settings"][label] = {"measured_blocks_per_s_8w_estimator_run": bps_run,
                                   "measured_blocks_per_s_8w_raw_reference_runs": bps_ref,
                                   "measured_aggregate_slowdown": bps_ref / bps_run, "pairings": {}}
        for pid, d in data.items():
            ests = [e for e in ESTS if e in d]
            pairs = [p for p in PAIRWISE if p[0] in d and p[1] in d]
            bs = boot_ratios(d, pairs, a.boot, rng)
            boot_store[(label, pid)] = bs
            for (x, y), b in bs.items():
                pw.append({"setting": label, "pairing_id": pid, "numerator": x, "denominator": y,
                           "var_ratio": float(d[x].var(ddof=1) / d[y].var(ddof=1)),
                           "ci_lo": float(np.quantile(b, 0.025)), "ci_hi": float(np.quantile(b, 0.975)),
                           "p_ratio_below_1": float(np.mean(b < 1))})
            big = d["potmax"] >= stack - 1e-9
            raw_dev2 = (d["raw"] - d["raw"].mean()) ** 2
            for e in ests:
                x = d[e]
                dev2 = (x - x.mean()) ** 2
                row = {"setting": label, "pairing_id": pid, "estimator": e, **tails(x),
                       "frac_blocks_big_pot": float(big.mean()),
                       "share_sq_dev_in_big_pot_blocks": float(dev2[big].sum() / dev2.sum()),
                       # squared deviation remaining in big-pot / other blocks relative to raw's
                       "big_pot_sq_dev_vs_raw": float(dev2[big].sum() / raw_dev2[big].sum()),
                       "other_sq_dev_vs_raw": float(dev2[~big].sum() / raw_dev2[~big].sum()) if raw_dev2[~big].sum() > 0 else float("nan"),
                       "share_sq_dev_in_allin_blocks": float(dev2[d["allin"]].sum() / dev2.sum())}
                tl.append(row)
                sd, k, hpb = float(x.std(ddof=1)), d["k"], d["hpb"]
                for power in (0.8, 0.95):
                    for dl in DELTAS:
                        nb = math.ceil(required_blocks(sd, dl * k / 100, 0.05, power))
                        nr = math.ceil(required_blocks(float(d["raw"].std(ddof=1)), dl * k / 100, 0.05, power))
                        hd.append({"setting": label, "pairing_id": pid, "estimator": e, "power": power, "delta_bb100": dl,
                                   "blocks": nb, "hands": round(nb * hpb), "raw_hands": round(nr * hpb),
                                   "hands_saved": round((nr - nb) * hpb), "pct_reduction": 100 * (1 - nb / nr),
                                   "speedup": nr / nb})
                if e != "raw":
                    key = (label, e)
                    if key in ESTIMATOR_BENCH:
                        r0, r1 = ESTIMATOR_BENCH[key]
                        slow = r0 / r1
                        ess = float(d["raw"].var(ddof=1) / x.var(ddof=1))
                        ef.append({"setting": label, "pairing_id": pid, "estimator": e, "ess_multiplier": ess,
                                   "compute_slowdown_single_process": slow, "net_wallclock_efficiency": ess / slow,
                                   "raw_blocks_per_s_1core": r0, "estimator_blocks_per_s_1core": r1})
            # precision of the mean, raw vs each estimator, on the same blocks
            prec = {}
            for e in ests:
                x = d[e]
                se = x.std(ddof=1) / math.sqrt(x.size)
                m = x.mean()
                prec[e] = {"mean_bb100": 100 * m / d["k"], "ci95_bb100": [100 * (m - 1.96 * se) / d["k"], 100 * (m + 1.96 * se) / d["k"]],
                           "z": m / se, "p_two_sided": float(2 * sps.norm.sf(abs(m / se))), "se_bb100": 100 * se / d["k"]}
                if e != "raw":
                    # blocks raw would need for the same SE as the estimator achieves on n blocks
                    prec[e]["raw_blocks_for_same_se"] = float(x.size * d["raw"].var(ddof=1) / x.var(ddof=1))
            deep["settings"][label]["pairings"][pid] = {"n_blocks": int(d["raw"].size), "precision": prec}
    # dose-response: median over pairings of the all-in EV variance ratio, bootstrap CI and 100BB - 20BB difference
    med = {}
    for label in ("nlhe6-100bb", "nlhe6-20bb", "aof4-8bb"):
        stacks = [boot_store[k][("allin_ev", "raw")] for k in boot_store if k[0] == label]
        pt = [r["var_ratio"] for r in pw if r["setting"] == label and r["numerator"] == "allin_ev" and r["denominator"] == "raw"]
        med[label] = np.median(np.stack(stacks), axis=0)
        deep.setdefault("allin_ev_dose_response", {})[label] = {
            "median_var_ratio": float(np.median(pt)), "median_ci": [float(np.quantile(med[label], 0.025)), float(np.quantile(med[label], 0.975))],
            "fraction_removed_median": 1 - float(np.median(pt))}
    diff = med["nlhe6-100bb"] - med["nlhe6-20bb"]
    deep["allin_ev_dose_response"]["median_ratio_100bb_minus_20bb"] = {
        "point": deep["allin_ev_dose_response"]["nlhe6-100bb"]["median_var_ratio"] - deep["allin_ev_dose_response"]["nlhe6-20bb"]["median_var_ratio"],
        "ci": [float(np.quantile(diff, 0.025)), float(np.quantile(diff, 0.975))], "p_diff_gt_0": float(np.mean(diff > 0))}
    for name, rows in (("rq6_pairwise.csv", pw), ("rq6_tails.csv", tl), ("rq6_hands.csv", hd), ("rq6_efficiency.csv", ef)):
        with (out / name).open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    deep["estimator_bench"] = {f"{k[0]}/{k[1]}": {"raw_bps": v[0], "estimator_bps": v[1], "slowdown": v[0] / v[1]}
                               for k, v in ESTIMATOR_BENCH.items()}
    (out / "rq6_deep.json").write_text(json.dumps(deep, indent=1, default=float) + "\n")
    import hashlib

    names = ["rq6_pairwise.csv", "rq6_tails.csv", "rq6_hands.csv", "rq6_efficiency.csv", "rq6_deep.json"]
    (out / "SHA256SUMS").write_text("".join(f"{hashlib.sha256((out / n).read_bytes()).hexdigest()}  {n}\n" for n in names))
    print(f"wrote {out}/rq6_pairwise.csv, rq6_tails.csv, rq6_hands.csv, rq6_efficiency.csv, rq6_deep.json")


if __name__ == "__main__":
    main()
