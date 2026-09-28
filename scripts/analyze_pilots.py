"""Cross-format pilot analysis (reads Parquet + manifests only; never re-runs poker).

Usage: .venv/bin/python scripts/analyze_pilots.py [--out reports/pilot-analysis]

Produces, per (experiment, pairing):
  * block-level moments, tails, all seven variance-concentration levels
  * sample requirements (blocks / played hands) for 0.25..5 BB/100 at 80% and 95%
    power and for fixed standardized d, plus CPU and wall-clock at the measured
    aggregate throughput of that experiment's own simulate run(s)
  * sigma_D uncertainty: block bootstrap CI and delta-method relative SE
    sqrt((kappa + 2) / (4 n)); subsample convergence (first n blocks)
  * share of the total squared deviation carried by blocks containing >= 1 all-in
    hand and by blocks whose largest pot exceeds 100 BB (targets for RQ6)
The unit is always the block. Hand counts are used only to translate costs.
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

from fhr3.analysis.stats import CONCENTRATION_FRACTIONS, required_blocks, variance_concentration
from fhr3.io.store import read_blocks

def _first_existing(*experiment_ids: str) -> str:
    """The first experiment with results on disk (newest listed first)."""
    return next((e for e in experiment_ids if (Path("results") / e).is_dir()), experiment_ids[-1])


EXPERIMENTS = [
    ("aof/4max/8bb", "fhr3-aof4-8bb-pilot-v1"),
    # the v1 4-max corpus cannot be extended by v2 code; its 100k extension is a v2 re-run
    ("nlhe/4max/100bb", _first_existing("fhr3-nlhe4-100bb-v2", "fhr3-nlhe4-100bb-pilot-v1")),
    ("nlhe/6max/20bb", "fhr3-nlhe6-20bb-v1"),
    ("nlhe/6max/50bb", "fhr3-nlhe6-50bb-v1"),
    ("nlhe/6max/100bb", "fhr3-nlhe6-100bb-pilot-v1"),
    ("cp/6max/100bb", "fhr3-cp6-100bb-pilot-v1"),
    ("plo/6max/100bb", "fhr3-plo6-100bb-pilot-v1"),
    ("bomb/6max/100bb", "fhr3-bomb6-100bb-pilot-v1"),
    ("nit/6max/100bb", "fhr3-nit6-100bb-pilot-v1"),
]
DELTAS = (0.25, 0.5, 1.0, 2.0, 5.0)
FIXED_D = (0.005, 0.01, 0.02)
QS = (0.0001, 0.001, 0.01, 0.99, 0.999, 0.9999)


def role(pid: str) -> str:
    return pid.split("-", 1)[0]


def aggregate_throughput(exp: str) -> float:
    """Blocks/s of the experiment's own simulate runs (block-weighted)."""
    blocks = secs = 0.0
    for f in glob.glob(f"results/{exp}/runs/*.json"):
        s = json.load(open(f))["summary"]
        if s.get("blocks") and s.get("wall_s"):
            blocks += s["blocks"]
            secs += s["wall_s"]
    return blocks / secs if secs else float("nan")


def boot_sd(D: np.ndarray, reps: int, rng: np.random.Generator) -> tuple[float, float]:
    out = np.empty(reps)
    n = D.size
    for i in range(reps):
        out[i] = D[rng.integers(0, n, n)].std(ddof=1)
    return float(np.quantile(out, 0.025)), float(np.quantile(out, 0.975))


def analyze(out_dir: Path, boot_reps: int) -> list[dict]:
    rng = np.random.default_rng(20260929)
    rows = []
    for label, exp in EXPERIMENTS:
        t = read_blocks(Path("results") / exp)
        agg_bps = aggregate_throughput(exp)
        for pid in sorted(set(t.column("pairing_id").to_pylist())):
            if pid.startswith("c0-"):
                continue
            tp = t.filter(pc.and_(pc.equal(t.column("pairing_id"), pid), t.column("valid")))
            order = np.argsort(tp.column("block_id").to_numpy())
            D = np.asarray(tp.column("D").to_numpy(zero_copy_only=False), dtype=float)[order]
            played = tp.column("played_hands").to_numpy()[order].astype(float)
            ha = tp.column("hands_a").to_numpy(zero_copy_only=False) if "hands_a" in tp.column_names else None
            if ha is not None and not any(v is None for v in ha):
                hb = tp.column("hands_b").to_numpy(zero_copy_only=False)
                k = float(np.mean((np.asarray(ha, float) + np.asarray(hb, float)) / 2))
            else:
                k = float(tp.column("player_count")[0].as_py())
            n, hpb = D.size, float(played.mean())
            mean, sd = float(D.mean()), float(D.std(ddof=1))
            se = sd / math.sqrt(n)
            kurt = float(sps.kurtosis(D))
            allin = tp.column("allin_hands").to_numpy()[order]
            potmax = tp.column("pot_bb_max").to_numpy()[order]
            dev2 = (D - mean) ** 2
            rt_ms = float(np.mean(tp.column("runtime_ms").to_numpy()))
            r = {
                "format": label, "experiment_id": exp, "pairing_id": pid, "role": role(pid),
                "player_count": int(tp.column("player_count")[0].as_py()), "stack_bb": float(tp.column("stack_bb")[0].as_py()),
                "n_blocks": n, "hands_per_block": hpb, "cand_hands_per_side": k,
                "mean_D": mean, "se_mean": se, "mean_bb100": 100 * mean / k,
                "ci_bb100_lo": 100 * (mean - 1.96 * se) / k, "ci_bb100_hi": 100 * (mean + 1.96 * se) / k,
                "z_mean": mean / se if se > 0 else float("nan"),
                "sd_D": sd, "frac_zero": float(np.mean(D == 0)), "skew": float(sps.skew(D)), "excess_kurtosis": kurt,
                "sd_rel_se_delta": math.sqrt((kurt + 2) / (4 * n)),
                "showdown_rate": float(tp.column("showdown_hands").to_numpy().sum() / played.sum()),
                "allin_rate": float(allin.sum() / played.sum()),
                "mean_pot_bb": float(tp.column("pot_bb_sum").to_numpy().sum() / played.sum()),
                "max_pot_bb": float(potmax.max()),
                "var_share_blocks_with_allin": float(dev2[allin > 0].sum() / dev2.sum()),
                "frac_blocks_with_allin": float(np.mean(allin > 0)),
                "var_share_pot_gt100": float(dev2[potmax > 100].sum() / dev2.sum()),
                "frac_blocks_pot_gt100": float(np.mean(potmax > 100)),
                "core_blocks_per_s": 1000 / rt_ms, "agg_blocks_per_s_8w": agg_bps,
                "bytes_per_block": sum(Path(f).stat().st_size for f in glob.glob(f"results/{exp}/{pid}/blocks/*.parquet")) / n,
            }
            for q, v in zip(QS, np.quantile(D, QS), strict=True):
                r[f"q{q:g}"] = float(v)
            for f, v in variance_concentration(D, CONCENTRATION_FRACTIONS).items():
                r[f"conc_top{f}"] = v
            for dl in DELTAS:
                db = dl * k / 100
                for pw in (0.8, 0.95):
                    nb = math.ceil(required_blocks(sd, db, 0.05, pw))
                    tag = f"{dl:g}bb100_p{int(pw * 100)}"
                    r[f"blocks_{tag}"] = nb
                    r[f"hands_{tag}"] = round(nb * hpb)
                    if pw == 0.8:
                        r[f"wall_h_8w_{tag}"] = nb / agg_bps / 3600
                        r[f"cpu_h_{tag}"] = nb * rt_ms / 1000 / 3600
            for d in FIXED_D:
                nb = math.ceil(required_blocks(1.0, d, 0.05, 0.8))
                r[f"blocks_d{d:g}"] = nb
                r[f"hands_d{d:g}"] = round(nb * hpb)
                r[f"bb100_at_d{d:g}"] = 100 * d * sd / k
            reps = boot_reps if n <= 50000 else min(boot_reps, 300)  # full-sample bootstrap, fewer reps for large n
            lo, hi = boot_sd(D, reps, rng) if boot_reps else (np.nan, np.nan)
            r["sd_boot_lo"], r["sd_boot_hi"], r["sd_boot_reps"] = lo, hi, reps
            conv = {}
            for m in (2500, 5000, 10000, 25000, 50000, 100000, 250000):
                if m <= n:
                    sub = D[:m]
                    conv[m] = {"sd": float(sub.std(ddof=1)), "kurt": float(sps.kurtosis(sub)),
                               "top1": variance_concentration(sub, (0.01,))["0.01"],
                               "top01": variance_concentration(sub, (0.001,))["0.001"]}
            r["convergence"] = conv
            rows.append(r)
    out_dir.mkdir(parents=True, exist_ok=True)
    flat = [{k: v for k, v in r.items() if k != "convergence"} for r in rows]
    with (out_dir / "pilot_table.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(flat[0].keys()))
        w.writeheader()
        w.writerows(flat)
    (out_dir / "pilot_analysis.json").write_text(json.dumps(rows, indent=1, default=float))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/pilot-analysis")
    ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args()
    rows = analyze(Path(a.out), a.boot)
    print(f"wrote {a.out}/pilot_table.csv and pilot_analysis.json ({len(rows)} pairings)")


if __name__ == "__main__":
    main()
