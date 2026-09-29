"""RQ7 deep analysis of the completed cells (read-only on reports/rq7 and the frozen corpora).

Usage: .venv/bin/python scripts/rq7_deep_analysis.py [--out reports/rq7/deep]

Outputs (outside the patterns frozen by reports/rq7/MANIFEST.json; own SHA256SUMS):
  invariants.json          same-stream invariant per cell + recomputation of 40 replicates of
                           two cells with a different worker count / chunking (tiny, synthetic)
  null_timing.csv          null cells: first false exclusion time quantiles and the share of
                           false stops by block-count bucket (peek, asymp)
  width_inflation.csv      median CS width / median t-interval width at each checkpoint
  stopping_cost.csv        non-null: CS decision probability at the fixed N, CS blocks needed to
                           reach the fixed test's decision rate (power-matched), median ratios
  wrong_sign.json          pooled wrong-sign counts and exact one-sided 95% upper bounds
  real_orderings_sign.csv  each frozen corpus in block order: peek / CS decision vs full-corpus sign
  trajectory_nlhe6_p2.csv  running mean, t-interval and CS (BB/100) for the illustrative stream
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import stats as sps

from fhr3.analysis.rq7 import Design, make_sampler, run_cell
from fhr3.analysis.sequential import asymp_radius, running_mean_sd

CELLS = Path("reports/rq7/cells")
BUCKETS = (1_000, 10_000, 100_000, 250_000)


def rows_of(name: str) -> list[dict]:
    with (CELLS / f"{name}.csv").open() as fh:
        return list(csv.DictReader(fh))


def cells() -> dict:
    return {json.loads(Path(f).read_text())["name"]: json.loads(Path(f).read_text()) for f in sorted(glob.glob(str(CELLS / "*.json")))}


def invariants(cs: dict) -> dict:
    out = {}
    for name, c in cs.items():
        d = c["design"]
        rows = rows_of(name)
        fixed = {r["rep"]: r for r in rows if r["method"] == "fixed"}
        peek = {r["rep"]: r for r in rows if r["method"] == "peek"}
        viol = 0
        for rep, f in fixed.items():
            if f["censored"] == "False" and not (0 < int(peek[rep]["decision_time"]) <= d["fixed_n"]):
                viol += 1
            fw = f.get(f"width_at_{d['fixed_n']}")
            if fw not in (None, "", "nan") and abs(float(fw) - float(peek[rep][f"width_at_{d['fixed_n']}"])) > 1e-9:
                viol += 1
        out[name] = {"same_stream_violations": viol}
    # recompute replicates 0..39 of two cells with 3 workers / chunk 5 and compare exactly
    recompute = {}
    for name in ("null-heavy-min200", "alt-t3-n25k"):
        c = cs[name]
        d = dict(c["design"])
        d["reps"] = 40
        d["checkpoints"] = tuple(d["checkpoints"])
        design = Design(**d)
        smp = make_sampler(d["sampler"])
        if not d["sampler"].startswith("permutation:"):
            smp = smp.with_true_mean(d["true_mean"])
        new = run_cell(design, smp, workers=3, chunk=5)
        old = [r for r in rows_of(name) if int(r["rep"]) < 40]
        keys = ["ever_miss_true_mean", "decision_time", "decision_sign", "first_miss_time"]
        norm = lambda r: tuple(str(r[k]) for k in ["method", "rep", *keys])  # noqa: E731
        recompute[name] = {"replicates": 40, "identical": sorted(map(norm, new)) == sorted(map(norm, old))}
    return {"cells": out, "recompute_different_workers_chunking": recompute}


def null_timing(cs: dict) -> list[dict]:
    out = []
    for name, c in cs.items():
        d = c["design"]
        if d["true_mean"] != 0 or d["sampler"].startswith("permutation:"):
            continue
        rows = rows_of(name)
        for m in ("peek", "asymp"):
            t = np.array([int(r["first_miss_time"]) for r in rows if r["method"] == m and r["ever_miss_true_mean"] == "True"])
            n = sum(1 for r in rows if r["method"] == m)
            row = {"cell": name, "method": m, "min_n": d["min_n"], "reps": n, "false_exclusions": int(t.size)}
            for q in (0.1, 0.25, 0.5, 0.75, 0.9):
                row[f"q{q}"] = float(np.quantile(t, q)) if t.size else None
            prev = 0
            for b in BUCKETS:
                row[f"share_of_reps_first_miss_le_{b}"] = float(np.sum(t <= b) / n)
                row[f"new_in_({prev},{b}]"] = int(np.sum((t > prev) & (t <= b)))
                prev = b
            row["earliest_miss"] = int(t.min()) if t.size else None
            out.append(row)
    return out


def width_inflation(cs: dict) -> list[dict]:
    out = []
    for name, c in cs.items():
        d = c["design"]
        if d["true_mean"] != 0 or d["min_n"] != 200 or d["sampler"].startswith("permutation:"):
            continue
        rows = rows_of(name)
        for cp in d["checkpoints"]:
            wp = np.array([float(r[f"width_at_{cp}"]) for r in rows if r["method"] == "peek"])
            wa = np.array([float(r[f"width_at_{cp}"]) for r in rows if r["method"] == "asymp"])
            out.append({"cell": name, "checkpoint": cp, "median_t_width": float(np.median(wp)),
                        "median_cs_width": float(np.median(wa)), "inflation": float(np.median(wa) / np.median(wp)),
                        "blocks_ratio_for_equal_width": float((np.median(wa) / np.median(wp)) ** 2)})
    return out


def stopping_cost(cs: dict) -> list[dict]:
    out = []
    for name, c in cs.items():
        d = c["design"]
        if d["true_mean"] == 0 or d["sampler"].startswith("permutation:"):
            continue
        rows = rows_of(name)
        fixed_rate = np.mean([r["censored"] == "False" for r in rows if r["method"] == "fixed"])
        t = np.array([int(r["decision_time"]) if r["censored"] == "False" else np.inf for r in rows if r["method"] == "asymp"])
        n80 = d["fixed_n"]
        q_match = float(np.quantile(t, fixed_rate)) if np.mean(np.isfinite(t)) >= fixed_rate else None
        out.append({"cell": name, "effect_d": d["effect_d"], "fixed_n": n80, "fixed_decision_rate": float(fixed_rate),
                    "cs_decision_rate_by_fixed_n": float(np.mean(t <= n80)), "cs_decision_rate_by_horizon": float(np.mean(np.isfinite(t))),
                    "cs_median_decision": float(np.median(t)), "cs_median_over_fixed_n": float(np.median(t) / n80),
                    "cs_blocks_to_match_fixed_power": q_match,
                    "power_matched_ratio": (q_match / n80) if q_match else None,
                    "cs_q90_over_fixed_n": float(np.quantile(t, 0.9) / n80) if np.isfinite(np.quantile(t, 0.9)) else None})
    return out


def wrong_sign(cs: dict) -> dict:
    out = {}
    for m in ("fixed", "peek", "asymp"):
        dec = wrong = 0
        for name, c in cs.items():
            d = c["design"]
            if d["true_mean"] == 0 or d["sampler"].startswith("permutation:"):
                continue
            for r in rows_of(name):
                if r["method"] == m and r["censored"] == "False":
                    dec += 1
                    wrong += r["wrong_decision"] == "True"
        ub = float(sps.beta.ppf(0.95, wrong + 1, dec - wrong)) if dec else None  # exact one-sided 95% upper bound
        out[m] = {"decisions": dec, "wrong_sign": wrong, "rate": wrong / dec if dec else None, "upper95_one_sided": ub}
    return out


def real_orderings() -> list[dict]:
    from fhr3.io.store import read_blocks

    out = []
    for f in sorted(glob.glob("reports/rq7/sequential-*.json")):
        res = json.loads(Path(f).read_text())
        exp = res[0]["experiment_id"]
        t = read_blocks(f"results/{exp}", columns=["config_hash", "pairing_id", "block_id", "valid", "D"])
        for pid in sorted({r["pairing_id"] for r in res}):
            import pyarrow.compute as pc

            D = np.asarray(t.filter(pc.equal(t.column("pairing_id"), pid)).column("D").to_numpy(zero_copy_only=False), float)
            n, m, se = D.size, D.mean(), D.std(ddof=1) / np.sqrt(D.size)
            full_sign = int(np.sign(m)) if abs(m / se) > 1.96 else 0
            row = {"experiment_id": exp, "pairing_id": pid, "n": n, "full_mean_block": float(m), "full_z": float(m / se),
                   "full_fixed_sign_if_significant": full_sign}
            for r in res:
                if r["pairing_id"] != pid:
                    continue
                s = {"A>B": 1, "B>A": -1, "none": 0}[r["decision"]]
                row[f"{r['method']}_stop"] = r["stopping_time"] if r["reason"] == "excludes_zero" else None
                row[f"{r['method']}_sign"] = s
                row[f"{r['method']}_contradicts_full_mean_sign"] = bool(s != 0 and np.sign(m) != 0 and s != np.sign(m))
            out.append(row)
    return out


def trajectory(exp: str = "fhr3-nlhe6-100bb-pilot-v1", pid: str = "p2-neutral-vs-tight") -> list[dict]:
    from fhr3.analysis.rq7 import load_pairing_d

    D = load_pairing_d(f"results/{exp}/{pid}")
    t, mean, sd = running_mean_sd(D)
    k = 6.0  # candidate hands per side per 6-max block
    tr = sps.t.ppf(0.975, np.maximum(t - 1, 1)) * sd / np.sqrt(t)
    cs = asymp_radius(t, sd, 0.05, 100_000)
    idx = np.unique(np.clip(np.round(np.logspace(np.log10(200), np.log10(D.size), 300)).astype(int), 200, D.size)) - 1
    return [{"blocks": int(i + 1), "mean_bb100": float(100 * mean[i] / k),
             "t_lo": float(100 * (mean[i] - tr[i]) / k), "t_hi": float(100 * (mean[i] + tr[i]) / k),
             "cs_lo": float(100 * (mean[i] - cs[i]) / k), "cs_hi": float(100 * (mean[i] + cs[i]) / k)} for i in idx]


def _w(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/rq7/deep")
    out = Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    cs = cells()
    (out / "invariants.json").write_text(json.dumps(invariants(cs), indent=1) + "\n")
    _w(out / "null_timing.csv", null_timing(cs))
    _w(out / "width_inflation.csv", width_inflation(cs))
    _w(out / "stopping_cost.csv", stopping_cost(cs))
    (out / "wrong_sign.json").write_text(json.dumps(wrong_sign(cs), indent=1) + "\n")
    _w(out / "real_orderings_sign.csv", real_orderings())
    _w(out / "trajectory_nlhe6_p2.csv", trajectory())
    names = ["invariants.json", "null_timing.csv", "width_inflation.csv", "stopping_cost.csv", "wrong_sign.json",
             "real_orderings_sign.csv", "trajectory_nlhe6_p2.csv"]
    (out / "SHA256SUMS").write_text("".join(f"{hashlib.sha256((out / n).read_bytes()).hexdigest()}  {n}\n" for n in names))
    print(f"wrote {out}/{{{','.join(names)}}} + SHA256SUMS")


if __name__ == "__main__":
    main()
