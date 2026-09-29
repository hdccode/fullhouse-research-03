"""RQ6 analysis: paired variance reduction of estimators on the same matched blocks.

Usage:
  .venv/bin/python scripts/analyze_rq6.py [--out reports/rq6] [--boot 2000] \\
      [--setting LABEL=RQ6_EXPERIMENT_DIR:REFERENCE_EXPERIMENT_DIR ...]

Defaults are the three frozen RQ6 settings (NLHE6 100BB fitted, NLHE6 20BB all-in EV,
AoF all-in EV) against their frozen raw reference corpora.

Every comparison is paired: the estimator and raw D are computed on the SAME blocks
(identical deals and actions), so variance ratios use a joint block bootstrap,
never independent-sample formulas. The unit is always the matched block.

Per setting x pairing x estimator: n, mean, SE, sigma, variance, variance ratio vs raw
with bootstrap 95% CI, SD ratio, effective-sample-size multiplier (1 / ratio), blocks and
played hands for 0.25..5 BB/100 at 80% power, % hands saved, corr with raw, mean
(estimator - raw) with its paired z, z of the mean itself (does the gap resolve?), and
estimator compute share. Checks (blockers => exit 1): raw D reproduces the frozen
reference block-by-block; self-play control exactly 0 for every estimator; |z(est-raw)| <= 3.
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

from fhr3.analysis.stats import required_blocks
from fhr3.io.store import read_blocks

DEFAULT_SETTINGS = [
    ("nlhe6-100bb", "results/fhr3-nlhe6-100bb-rq6-v1-fittedvf", "results/fhr3-nlhe6-100bb-pilot-v1"),
    ("nlhe6-20bb", "results/fhr3-nlhe6-20bb-rq6-allin-v1", "results/fhr3-nlhe6-20bb-v1"),
    ("aof4-8bb", "results/fhr3-aof4-8bb-rq6-allin-v1", "results/fhr3-aof4-8bb-pilot-v1"),
]
ESTIMATORS = ("allin_ev", "mivat", "aivat")
DELTAS = (0.25, 0.5, 1.0, 2.0, 5.0)
COLS = ["config_hash", "pairing_id", "block_id", "valid", "D", "played_hands", "hands_a", "hands_b",
        "runtime_ms", "estimator_ms", "estimator_config_hash", "raw_estimator_D", "allin_ev_D", "mivat_D", "aivat_D"]


def _col(t, name):
    return np.asarray(t.column(name).to_numpy(zero_copy_only=False))


def paired_ratio_ci(raw: np.ndarray, est: np.ndarray, reps: int, rng: np.random.Generator, batch: int = 50):
    """Percentile CI of var(est)/var(raw) resampling whole blocks jointly (paired)."""
    n, out = raw.size, []
    for s in range(0, reps, batch):
        idx = rng.integers(0, n, size=(min(batch, reps - s), n))
        vr = raw[idx].var(axis=1, ddof=1)
        out.append(est[idx].var(axis=1, ddof=1)[vr > 0] / vr[vr > 0])  # drop degenerate resamples
    r = np.concatenate(out)
    if r.size == 0:
        return float("nan"), float("nan")
    return float(np.quantile(r, 0.025)), float(np.quantile(r, 0.975))


def _blocks_needed(sd: float, delta_block: float) -> int | None:
    n = required_blocks(sd, delta_block, 0.05, 0.8)
    return math.ceil(n) if math.isfinite(n) else None


def throughput(exp_dir: Path) -> float | None:
    blocks = secs = 0.0
    for f in glob.glob(str(exp_dir / "runs" / "*.json")):
        s = json.load(open(f)).get("summary") or {}
        if s.get("blocks") and s.get("wall_s"):
            blocks, secs = blocks + s["blocks"], secs + s["wall_s"]
    return blocks / secs if secs else None


def analyze_setting(label: str, exp: Path, ref: Path, reps: int, rng: np.random.Generator) -> tuple[list[dict], dict]:
    t = read_blocks(exp, columns=COLS)
    tr = read_blocks(ref, columns=["config_hash", "pairing_id", "block_id", "valid", "D"])
    rows, checks = [], {"setting": label, "experiment": str(exp), "reference": str(ref), "pairings": {}}
    bps = throughput(exp)
    for pid in sorted(set(t.column("pairing_id").to_pylist())):
        tp = t.filter(pc.and_(pc.equal(t.column("pairing_id"), pid), t.column("valid")))
        o = np.argsort(_col(tp, "block_id"))
        bid = _col(tp, "block_id")[o]
        raw = _col(tp, "D").astype(float)[o]
        est = {e: _col(tp, f"{e}_D")[o] for e in ESTIMATORS}
        est = {e: v.astype(float) for e, v in est.items() if not any(x is None for x in v) and not np.isnan(v.astype(float)).any()}
        ck: dict = {"n": int(raw.size), "estimators": sorted(est),
                    "estimator_config_hashes": sorted(set(tp.column("estimator_config_hash").to_pylist()))}
        # raw reproduction vs the frozen reference corpus (same seeds => identical D)
        rp = tr.filter(pc.equal(tr.column("pairing_id"), pid))
        ref_d = dict(zip(_col(rp, "block_id").tolist(), _col(rp, "D").astype(float).tolist(), strict=True))
        common = [i for i, b in enumerate(bid) if int(b) in ref_d]
        mism = int(sum(raw[i] != ref_d[int(bid[i])] for i in common))
        ck["raw_reproduction"] = {"common_blocks": len(common), "mismatches": mism,
                                  "ok": bool(common) and mism == 0}
        rawcol = _col(tp, "raw_estimator_D")[o]
        ck["raw_estimator_column_equals_D"] = bool(all(x is not None for x in rawcol) and np.array_equal(rawcol.astype(float), raw))
        if pid.startswith("c0-"):
            ck["selfplay_exact_zero"] = bool(np.all(raw == 0) and all(np.all(v == 0) for v in est.values()))
            checks["pairings"][pid] = ck
            continue
        k = float(np.mean((_col(tp, "hands_a").astype(float) + _col(tp, "hands_b").astype(float)) / 2))
        hpb = float(_col(tp, "played_hands").astype(float).mean())
        est_share = float(_col(tp, "estimator_ms").astype(float).sum() / _col(tp, "runtime_ms").astype(float).sum())
        vraw = raw.var(ddof=1)
        for name, x in [("raw", raw), *sorted(est.items())]:
            n = x.size
            sd, mean = float(x.std(ddof=1)), float(x.mean())
            se = sd / math.sqrt(n)
            ratio = float(x.var(ddof=1) / vraw) if vraw > 0 else float("nan")  # nan: degenerate (all D equal)
            lo, hi = (1.0, 1.0) if name == "raw" else paired_ratio_ci(raw, x, reps, rng)
            diff = x - raw
            dse = float(diff.std(ddof=1) / math.sqrt(n)) if n > 1 else float("nan")
            r = {"setting": label, "pairing_id": pid, "estimator": name, "n_blocks": n,
                 "hands_per_block": hpb, "candidate_hands_per_side": k,
                 "mean_D": mean, "se_mean": se, "mean_bb100": 100 * mean / k, "z_mean": mean / se if se > 0 else float("nan"),
                 "sd_D": sd, "var_D": sd * sd, "var_ratio_vs_raw": ratio, "var_ratio_ci_lo": lo, "var_ratio_ci_hi": hi,
                 "sd_ratio_vs_raw": math.sqrt(ratio), "ess_multiplier": 1 / ratio if ratio > 0 else float("inf"),
                 "corr_with_raw": 1.0 if name == "raw" else float(np.corrcoef(raw, x)[0, 1]),
                 "mean_diff_vs_raw": float(diff.mean()), "mean_diff_se": dse,
                 # identical on every block (e.g. no hand where the candidate is live in an all-in): z = 0
                 "mean_diff_z": 0.0 if name == "raw" or not np.any(diff) else float(diff.mean()) / dse,
                 "estimator_time_share": est_share, "blocks_per_s_measured": bps}
            for dl in DELTAS:
                nb = _blocks_needed(sd, dl * k / 100)
                nb_raw = _blocks_needed(float(raw.std(ddof=1)), dl * k / 100)
                r[f"blocks_{dl:g}bb100_p80"] = nb
                r[f"hands_{dl:g}bb100_p80"] = round(nb * hpb) if nb is not None else None
                r[f"pct_hands_saved_{dl:g}bb100"] = 100 * (1 - nb / nb_raw) if nb is not None and nb_raw else None
            r["flag_main_text_candidate"] = bool(name != "raw" and hi < 1 and ratio <= 0.5)
            r["flag_weak_reduction"] = bool(name != "raw" and ratio >= 0.8)
            r["flag_variance_increase"] = bool(name != "raw" and lo > 1)
            r["flag_bias_blocker"] = bool(name != "raw" and abs(r["mean_diff_z"]) > 3)
            rows.append(r)
        checks["pairings"][pid] = ck
    return rows, checks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/rq6")
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--setting", action="append", help="LABEL=RQ6_DIR:REFERENCE_DIR (repeatable)")
    a = ap.parse_args()
    settings = DEFAULT_SETTINGS
    if a.setting:
        settings = [(s.split("=", 1)[0], *s.split("=", 1)[1].split(":", 1)) for s in a.setting]
    out = Path(a.out)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261006)
    rows, checks = [], []
    for label, exp, ref in settings:
        r, c = analyze_setting(label, Path(exp), Path(ref), a.boot, rng)
        rows += r
        checks.append(c)
    with (out / "rq6_summary.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    fig = ["setting", "pairing_id", "estimator", "n_blocks", "var_ratio_vs_raw", "var_ratio_ci_lo", "var_ratio_ci_hi",
           "sd_ratio_vs_raw", "ess_multiplier", "pct_hands_saved_1bb100", "hands_1bb100_p80", "corr_with_raw",
           "mean_diff_z", "mean_bb100", "z_mean", "estimator_time_share"]
    with (out / "figures" / "variance_reduction.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(fig)
        w.writerows([[r[c] for c in fig] for r in rows])
    blockers = []
    for c in checks:
        for pid, ck in c["pairings"].items():
            if not ck["raw_reproduction"]["ok"]:
                blockers.append(f"{c['setting']}/{pid}: raw D does not reproduce the reference")
            if not ck["raw_estimator_column_equals_D"]:
                blockers.append(f"{c['setting']}/{pid}: raw_estimator_D != D")
            if ck.get("selfplay_exact_zero") is False:
                blockers.append(f"{c['setting']}/{pid}: self-play control not exactly zero")
    blockers += [f"{r['setting']}/{r['pairing_id']}/{r['estimator']}: |z(est-raw)| = {abs(r['mean_diff_z']):.2f} > 3"
                 for r in rows if r["flag_bias_blocker"]]
    summary = {"checks": checks, "blockers": blockers, "bootstrap_reps": a.boot, "unit": "matched block (paired)",
               "main_text_candidates": [f"{r['setting']}/{r['pairing_id']}/{r['estimator']}" for r in rows if r["flag_main_text_candidate"]]}
    (out / "rq6_summary.json").write_text(json.dumps(summary, indent=1, default=float) + "\n")
    for r in rows:
        print(f"{r['setting']:<12} {r['pairing_id'][:24]:<25} {r['estimator']:<9} n={r['n_blocks']:>6} "
              f"var ratio {r['var_ratio_vs_raw']:.3f} [{r['var_ratio_ci_lo']:.3f}, {r['var_ratio_ci_hi']:.3f}] "
              f"hands@1 {r['hands_1bb100_p80'] or 0:>11,} saved {r['pct_hands_saved_1bb100'] or 0:5.1f}% "
              f"z(est-raw) {r['mean_diff_z']:+.2f}  BB/100 {r['mean_bb100']:+.2f} (z {r['z_mean']:+.2f})")
    print("BLOCKERS:" if blockers else "checks passed (raw reproduction, raw column, self-play, |z| <= 3)")
    for b in blockers:
        print("  " + b)
    print(f"wrote {out}/rq6_summary.csv, rq6_summary.json, figures/variance_reduction.csv")
    raise SystemExit(1 if blockers else 0)


if __name__ == "__main__":
    main()
