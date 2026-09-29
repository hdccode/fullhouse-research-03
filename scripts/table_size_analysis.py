"""FHR3A table-size sweep: NLHE 100BB at 3 / 4 / 6 / 8 seats (reads Parquet + locks only; never
re-runs poker). Design, population rule and caveats: docs/table_size.md.

Usage (repo root):
  .venv/bin/python scripts/table_size_analysis.py                  # analyse + write reports/table-size/
  .venv/bin/python scripts/table_size_analysis.py --freeze         # ... and write reports/table-size/MANIFEST.json
  .venv/bin/python scripts/table_size_analysis.py --verify         # recompute; exit 1 if outputs/corpora drifted
  .venv/bin/python scripts/table_size_analysis.py --allow-partial --new-results DIR --out DIR2
                                                                   # smoke/dev only: provisional, never frozen

Sources
  3-max  results/fhr3-nlhe3-100bb-v1          (new; integrity-checked here)
  4-max  results/fhr3-nlhe4-100bb-v2          (frozen; Parquet fingerprint must equal
  6-max  results/fhr3-nlhe6-100bb-pilot-v1     reports/final-analysis/MANIFEST.json)
  8-max  results/fhr3-nlhe8-100bb-v1          (new)
For 4- and 6-max every recomputed number is also asserted equal to the frozen
reports/final-analysis outputs (ranking.json, allin.csv, core/pilot_table.csv), so the sweep
uses exactly the published definitions. Nothing under reports/final-analysis is written.

Outputs (reports/table-size/)
  summary.csv       one row per table size x pairing (p1-p3): the 13 metrics + ratios vs 6-max
  summary.json      the same, plus per-table-size medians over p1-p3, ratio-of-medians CIs,
                    table-size elasticities, invariant checks and provenance
  figure_data.csv   long format for the table-size figure (pairing rows + median rows)
  MANIFEST.json     (--freeze) corpus fingerprints, output sha256s, git SHA, commands

Definitions (identical to scripts/final_analysis.py)
  D = X_A - X_B per matched block (BB); k = candidate hands per side = seats; 2k played hands.
  blocks_required = ceil(((z_.975 + z_.8) * sigma_D / (1 BB/100 * k / 100))^2)
  hands_required  = blocks_required * played hands per block
  Per-played-hand invariance <=> sigma_D^2 proportional to k <=> hands_required flat in k.
  elasticity of hands_required in k = d log(hands) / d log(k) = (d log var / d log k) - 1.
The unit of inference is always the block. p1/p2/p3 are kept separate throughout; medians are
over the three pairings. Bootstrap CIs resample blocks within each corpus (corpora independent).
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pyarrow.compute as pc
import pyarrow.parquet as pq
from scipy import stats as sps

from fhr3.analysis.stats import required_blocks, variance_concentration
from fhr3.configs.experiment import load_config
from fhr3.io.store import read_blocks

SWEEP = [  # (seats, config, experiment id, frozen corpus reused from the final core analysis)
    (3, "configs/nlhe_3max_100bb.yaml", "fhr3-nlhe3-100bb-v1", False),
    (4, "configs/nlhe_4max_100bb_v2.yaml", "fhr3-nlhe4-100bb-v2", True),
    (6, "configs/nlhe_6max_100bb.yaml", "fhr3-nlhe6-100bb-pilot-v1", True),
    (8, "configs/nlhe_8max_100bb.yaml", "fhr3-nlhe8-100bb-v1", False),
]
BASE_K = 6
TARGET_BLOCKS = {"p1": 30000, "p2": 30000, "p3": 30000, "c0": 10000}  # new corpora only
ROLES = ("p1", "p2", "p3")
FROZEN_LABEL = {4: "nlhe/4max/100bb", 6: "nlhe/6max/100bb"}
FA = Path("reports/final-analysis")
OUT = Path("reports/table-size")
OUTPUTS = ["summary.csv", "summary.json", "figure_data.csv"]
Z80 = sps.norm.ppf(0.975) + sps.norm.ppf(0.8)
COLS = ["config_hash", "pairing_id", "pairing_hash", "block_id", "valid", "D", "played_hands",
        "candidate_hands_per_side", "allin_hands", "pot_bb_max", "stack_bb"]
COMMANDS = [
    ".venv/bin/python scripts/table_size_analysis.py --boot 1000 --freeze",
    ".venv/bin/python scripts/table_size_analysis.py --boot 1000 --verify",
]


class CheckFailed(AssertionError):
    pass


CHECKS: list[str] = []


def check(ok: bool, msg: str) -> None:
    if not ok:
        raise CheckFailed(msg)
    CHECKS.append(msg)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fingerprint(exp_dir: Path) -> dict:
    """Same fingerprint as scripts/freeze_manifest.py (sha256 over sorted chunk name:sha lines)."""
    lock = json.loads((exp_dir / "experiment.lock.json").read_text())
    pairings = {}
    for pdir in sorted(p for p in exp_dir.iterdir() if (p / "pairing.lock.json").exists()):
        files = sorted((pdir / "blocks").glob("blocks_*.parquet"))
        h, rows = hashlib.sha256(), 0
        for f in files:
            h.update(f"{f.name}:{sha256(f)}\n".encode())
            rows += pq.ParquetFile(f).metadata.num_rows
        pairings[pdir.name] = {"pairing_hash": json.loads((pdir / "pairing.lock.json").read_text())["pairing_hash"],
                               "rows": rows, "chunks": len(files), "parquet_sha256": h.hexdigest()}
    runs = sorted(json.loads(f.read_text())["run_id"] for f in (exp_dir / "runs").glob("*.json"))
    return {"config_hash": lock["config_hash"], "schema_version": lock["schema_version"], "pairings": pairings,
            "run_ids": runs}


def throughput(exp_dir: Path) -> float:
    """Blocks/s of the experiment's own simulate runs (block-weighted), as in analyze_pilots.py."""
    blocks = secs = 0.0
    for f in glob.glob(f"{exp_dir}/runs/*.json"):
        s = json.load(open(f))["summary"]
        if s.get("blocks") and s.get("wall_s"):
            blocks += s["blocks"]
            secs += s["wall_s"]
    return blocks / secs if secs else float("nan")


# ------------------------------------------------------------------ load + integrity
def load(new_root: Path, allow_partial: bool) -> tuple[dict, dict]:
    frozen_manifest = json.loads((FA / "MANIFEST.json").read_text())
    data, prov = {}, {}
    for k, cfg_path, exp, frozen in SWEEP:
        root = Path("results") if frozen else new_root
        d = root / exp
        if not d.exists():
            raise CheckFailed(f"{k}-max corpus missing: {d} (run scripts/run_table_size.sh first)")
        cfg = load_config(cfg_path)
        fp = fingerprint(d)
        check(fp["config_hash"] == cfg.config_hash, f"{k}-max experiment lock config_hash = {cfg_path}")
        if frozen:
            ref = frozen_manifest["corpora"][exp]
            check(fp["config_hash"] == ref["config_hash"], f"{k}-max config_hash = frozen MANIFEST")
            for pid, v in ref["pairings"].items():
                got = fp["pairings"][pid]
                check(got["parquet_sha256"] == v["parquet_sha256"] and got["rows"] == v["rows"],
                      f"{k}-max {pid} Parquet fingerprint = frozen MANIFEST ({v['rows']} rows)")
        t = read_blocks(d, columns=COLS)  # raises on duplicate block ids
        check(set(t.column("config_hash").to_pylist()) == {cfg.config_hash}, f"{k}-max rows carry config_hash {cfg.config_hash}")
        for p in cfg.pairings:
            pid, role = p.pairing_id, p.pairing_id.split("-", 1)[0]
            tp = t.filter(pc.equal(t.column("pairing_id"), pid))
            check(tp.num_rows > 0, f"{k}-max {pid} present")
            check(set(tp.column("pairing_hash").to_pylist()) == {p.pairing_hash}, f"{k}-max {pid} pairing_hash = config")
            b = np.sort(tp.column("block_id").to_numpy())
            check(b[0] == 0 and b[-1] + 1 == b.size and np.unique(b).size == b.size,
                  f"{k}-max {pid} block ids contiguous 0..{b.size - 1}")
            if not frozen and not allow_partial:
                check(b.size >= TARGET_BLOCKS[role], f"{k}-max {pid} has >= {TARGET_BLOCKS[role]} blocks ({b.size})")
            valid = tp.column("valid").to_numpy(zero_copy_only=False)
            check(bool(valid.all()), f"{k}-max {pid} no invalid blocks")
            o = np.argsort(tp.column("block_id").to_numpy())
            col = lambda c: np.asarray(tp.column(c).to_numpy(zero_copy_only=False))[o]  # noqa: E731
            D = col("D").astype(float)
            check(bool(np.isfinite(D).all()), f"{k}-max {pid} no NaN/inf D")
            played = col("played_hands").astype(float)
            check(bool((played == 2 * k).all()) and bool((col("candidate_hands_per_side") == k).all()),
                  f"{k}-max {pid} every block = {2 * k} played hands, k = {k}")
            if role == "c0":
                check(bool((D == 0).all()), f"{k}-max {pid} self-play control D == 0 exactly ({D.size} blocks)")
                continue
            data[(k, role)] = {"exp": exp, "pairing_id": pid, "D": D, "played": played, "k": float(k),
                               "allin": col("allin_hands"), "potmax": col("pot_bb_max").astype(float),
                               "stack": float(col("stack_bb")[0])}
        bps = throughput(d)
        for role in ROLES:
            data[(k, role)]["bps"] = bps
        prov[k] = {"experiment_id": exp, "config": cfg_path, "config_hash": cfg.config_hash, "frozen_corpus": frozen,
                   "results_dir": str(d), "fingerprint": fp, "blocks_per_s_8_workers": bps}
    return data, prov


# ------------------------------------------------------------------ metrics
def blocks_needed(sd: float, k: float) -> int:
    return math.ceil(required_blocks(sd, 1.0 * k / 100, 0.05, 0.8))


def metrics(d: dict, n_first: int | None) -> dict:
    D, k, hpb = d["D"], d["k"], float(d["played"].mean())
    n, sd = D.size, float(D.std(ddof=1))
    kurt = float(sps.kurtosis(D))
    blocks = blocks_needed(sd, k)
    dev2 = (D - D.mean()) ** 2
    tot = dev2.sum()
    big = d["potmax"] > d["stack"] - 1e-9  # a pot of at least one starting stack
    allin = d["allin"] > 0
    vc = variance_concentration(D, (0.01, 0.001))
    r = {
        "seats": int(k), "role": None, "pairing_id": d["pairing_id"], "experiment_id": d["exp"], "n_blocks": int(n),
        "hands_per_block": hpb, "candidate_hands_per_side": k,
        "mean_bb100": float(100 * D.mean() / k), "sigma_D": sd, "var_D": sd ** 2,
        "var_D_per_candidate_hand": sd ** 2 / k,
        "blocks_required_1bb100": blocks, "hands_required_1bb100": blocks * hpb,
        "p_D_zero": float(np.mean(D == 0)), "excess_kurtosis": kurt,
        "top1pct_share": vc["0.01"], "top01pct_share": vc["0.001"],
        "frac_blocks_pot_ge_1stack": float(big.mean()), "share_pot_ge_1stack": float(dev2[big].sum() / tot),
        "frac_blocks_allin": float(allin.mean()), "share_allin": float(dev2[allin].sum() / tot),
        "sigma_D_rel_se_delta": math.sqrt((kurt + 2) / (4 * n)),
        "blocks_per_s_8_workers": d["bps"], "wall_h_required_8_workers": blocks / d["bps"] / 3600,
    }
    if n_first is not None and n > n_first:  # same-n sensitivity for the larger frozen corpora
        sdp = float(D[:n_first].std(ddof=1))
        r |= {"n_first": n_first, "sigma_D_first_n": sdp, "hands_required_1bb100_first_n": blocks_needed(sdp, k) * hpb}
    else:
        r |= {"n_first": int(n), "sigma_D_first_n": sd, "hands_required_1bb100_first_n": blocks * hpb}
    return r


def boot_sds(D: np.ndarray, reps: int, seed: tuple[int, ...]) -> np.ndarray:
    rng = np.random.default_rng(list(seed))
    n, out = D.size, np.empty(reps)
    for i in range(reps):
        out[i] = D[rng.integers(0, n, n)].std(ddof=1)
    return out


def q(x: np.ndarray) -> list[float]:
    return [float(np.quantile(x, 0.025)), float(np.quantile(x, 0.975))]


def analyse(data: dict, reps: int) -> dict:
    seats = sorted({k for k, _ in data})
    frozen = {s[0]: s[3] for s in SWEEP}
    n_new = min(data[(k, r)]["D"].size for k in seats for r in ROLES if not frozen[k])
    rows, boot = {}, {}
    for (k, role), d in sorted(data.items()):
        r = metrics(d, n_new if frozen[k] else None)
        r["role"] = role
        sds = boot_sds(d["D"], reps, (20261101, k, ROLES.index(role)))
        b = (Z80 * sds / (k / 100)) ** 2  # continuous required blocks per bootstrap draw
        boot[(k, role)] = {"sd": sds, "var": sds ** 2, "blocks": b, "hands": b * r["hands_per_block"]}
        r["sigma_D_ci"] = q(sds)
        r["hands_required_ci"] = q(boot[(k, role)]["hands"])
        rows[(k, role)] = r
    # ratios vs 6-max, same pairing (pairing-level; corpora independent)
    for (k, role), r in rows.items():
        base, bb = rows[(BASE_K, role)], boot[(BASE_K, role)]
        for m, bm in (("sigma_D", "sd"), ("var_D", "var"), ("blocks_required_1bb100", "blocks"),
                      ("hands_required_1bb100", "hands")):
            r[f"{m}_rel_6max"] = r[m] / base[m]
            r[f"{m}_rel_6max_ci"] = q(boot[(k, role)][bm] / bb[bm]) if k != BASE_K else [1.0, 1.0]
    # medians over p1-p3 per table size, ratio of medians vs 6-max with CI
    med = {}
    for k in seats:
        e = {"seats": k, "hands_per_block": rows[(k, "p1")]["hands_per_block"]}
        for m, bm in (("sigma_D", "sd"), ("var_D", "var"), ("blocks_required_1bb100", "blocks"),
                      ("hands_required_1bb100", "hands")):
            vals = [rows[(k, r)][m] for r in ROLES]
            e[m] = float(np.median(vals))
            e[f"{m}_pairing_range"] = [float(min(vals)), float(max(vals))]
            e[f"_b_{bm}"] = np.median(np.stack([boot[(k, r)][bm] for r in ROLES]), axis=0)
            e[f"{m}_median_ci"] = q(e[f"_b_{bm}"])
        for m in ("p_D_zero", "excess_kurtosis", "top1pct_share", "frac_blocks_pot_ge_1stack", "share_pot_ge_1stack",
                  "frac_blocks_allin", "share_allin", "var_D_per_candidate_hand", "wall_h_required_8_workers"):
            vals = [rows[(k, r)][m] for r in ROLES]
            e[m] = float(np.median(vals))
            e[f"{m}_pairing_range"] = [float(min(vals)), float(max(vals))]
        med[k] = e
    for k in seats:
        for m, bm in (("sigma_D", "sd"), ("var_D", "var"), ("blocks_required_1bb100", "blocks"),
                      ("hands_required_1bb100", "hands")):
            med[k][f"{m}_rel_6max"] = med[k][m] / med[BASE_K][m]
            med[k][f"{m}_rel_6max_ci"] = q(med[k][f"_b_{bm}"] / med[BASE_K][f"_b_{bm}"]) if k != BASE_K else [1.0, 1.0]
            med[k][f"{m}_rel_6max_roles_below_1"] = int(sum(rows[(k, r)][f"{m}_rel_6max"] < 1 for r in ROLES))
    # elasticity of required played hands in table size: overall (OLS on log-log over all seats)
    # and per adjacent segment; per pairing and for the median series, with bootstrap CIs
    lk = np.log(seats)

    def slope(y: np.ndarray) -> np.ndarray:  # y: (len(seats), reps) or (len(seats),)
        xc = lk - lk.mean()
        return (xc[:, None] * (y - y.mean(axis=0))).sum(axis=0) / (xc ** 2).sum() if y.ndim == 2 else \
            float((xc * (y - y.mean())).sum() / (xc ** 2).sum())

    elast = {}
    series = {r: ([rows[(k, r)]["hands_required_1bb100"] for k in seats],
                  np.stack([boot[(k, r)]["hands"] for k in seats])) for r in ROLES}
    series["median"] = ([med[k]["hands_required_1bb100"] for k in seats], np.stack([med[k]["_b_hands"] for k in seats]))
    for name, (pt, bs) in series.items():
        lp, lb = np.log(pt), np.log(bs)
        e = {"overall": slope(lp), "overall_ci": q(slope(lb)), "segments": {}}
        for (k1, k2), i in zip(zip(seats, seats[1:]), range(len(seats) - 1)):
            s = (lp[i + 1] - lp[i]) / (lk[i + 1] - lk[i])
            sb = (lb[i + 1] - lb[i]) / (lk[i + 1] - lk[i])
            e["segments"][f"{k1}->{k2}"] = {"elasticity": float(s), "ci": q(sb)}
        elast[name] = e
    for e in med.values():
        for key in [x for x in e if x.startswith("_b_")]:
            e.pop(key)
    return {"rows": rows, "medians": med, "elasticity_hands_vs_seats": elast, "n_first_for_frozen": n_new,
            "bootstrap_reps": reps}


# ------------------------------------------------------------------ cross-check frozen outputs
def close(a: float, b: float, rel: float = 1e-9) -> bool:
    return math.isclose(float(a), float(b), rel_tol=rel, abs_tol=1e-12)


def crosscheck_frozen(res: dict) -> None:
    rk = json.loads((FA / "ranking.json").read_text())["per_pairing"]
    allin = {(r["format"], r["pairing_id"]): r for r in csv.DictReader(open(FA / "allin.csv"))}
    pilot = {(r["format"], r["pairing_id"]): r for r in csv.DictReader(open(FA / "core" / "pilot_table.csv"))}
    for k, label in FROZEN_LABEL.items():
        for role in ROLES:
            r = res["rows"][(k, role)]
            f = rk[f"{label}|{role}"]
            check(f["pairing_id"] == r["pairing_id"] and f["n"] == r["n_blocks"], f"{k}-max {role} n = ranking.json")
            check(close(f["sd"], r["sigma_D"]), f"{k}-max {role} sigma_D = ranking.json")
            check(f["blocks"] == r["blocks_required_1bb100"], f"{k}-max {role} blocks required = ranking.json")
            check(close(f["hands"], r["hands_required_1bb100"]), f"{k}-max {role} hands required = ranking.json")
            a = allin[(label, r["pairing_id"])]
            for mine, theirs in (("p_D_zero", "frac_zero"), ("frac_blocks_allin", "frac_blocks_allin"),
                                 ("share_allin", "share_allin"), ("frac_blocks_pot_ge_1stack", "frac_blocks_pot_ge_1stack"),
                                 ("share_pot_ge_1stack", "share_pot_ge_1stack")):
                check(close(a[theirs], r[mine]), f"{k}-max {role} {mine} = allin.csv {theirs}")
            p = pilot[(label, r["pairing_id"])]
            if int(p["n_blocks"]) == r["n_blocks"]:
                check(close(p["excess_kurtosis"], r["excess_kurtosis"]), f"{k}-max {role} excess kurtosis = pilot_table.csv")
                check(close(p["conc_top0.01"], r["top1pct_share"]), f"{k}-max {role} top-1% share = pilot_table.csv")


# ------------------------------------------------------------------ outputs
SUMMARY_COLS = [
    "seats", "role", "pairing_id", "experiment_id", "n_blocks", "hands_per_block", "candidate_hands_per_side",
    "mean_bb100", "sigma_D", "sigma_D_ci", "var_D", "var_D_per_candidate_hand", "blocks_required_1bb100",
    "hands_required_1bb100", "hands_required_ci", "p_D_zero", "excess_kurtosis", "top1pct_share", "top01pct_share",
    "frac_blocks_pot_ge_1stack", "share_pot_ge_1stack", "frac_blocks_allin", "share_allin",
    "sigma_D_rel_6max", "sigma_D_rel_6max_ci", "var_D_rel_6max", "var_D_rel_6max_ci",
    "blocks_required_1bb100_rel_6max", "blocks_required_1bb100_rel_6max_ci",
    "hands_required_1bb100_rel_6max", "hands_required_1bb100_rel_6max_ci",
    "sigma_D_rel_se_delta", "n_first", "sigma_D_first_n", "hands_required_1bb100_first_n",
    "blocks_per_s_8_workers", "wall_h_required_8_workers",
]


def _cell(v):
    if isinstance(v, list):
        return ";".join(f"{x:.10g}" for x in v)
    if isinstance(v, float):
        return f"{v:.10g}"
    return v


def write_outputs(res: dict, prov: dict, out: Path, provisional: bool) -> None:
    out.mkdir(parents=True, exist_ok=True)
    rows = [res["rows"][key] for key in sorted(res["rows"])]
    with (out / "summary.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(SUMMARY_COLS)
        for r in rows:
            w.writerow([_cell(r[c]) for c in SUMMARY_COLS])
    fig = []
    for r in rows:
        fig.append({"seats": r["seats"], "series": r["role"], "pairing_id": r["pairing_id"],
                    "hands_per_block": r["hands_per_block"], "n_blocks": r["n_blocks"],
                    "sigma_D": r["sigma_D"], "sigma_D_lo": r["sigma_D_ci"][0], "sigma_D_hi": r["sigma_D_ci"][1],
                    "sigma_rel_6max": r["sigma_D_rel_6max"], "sigma_rel_6max_lo": r["sigma_D_rel_6max_ci"][0],
                    "sigma_rel_6max_hi": r["sigma_D_rel_6max_ci"][1],
                    "hands_required": r["hands_required_1bb100"], "hands_required_lo": r["hands_required_ci"][0],
                    "hands_required_hi": r["hands_required_ci"][1],
                    "hands_rel_6max": r["hands_required_1bb100_rel_6max"],
                    "hands_rel_6max_lo": r["hands_required_1bb100_rel_6max_ci"][0],
                    "hands_rel_6max_hi": r["hands_required_1bb100_rel_6max_ci"][1],
                    "blocks_required": r["blocks_required_1bb100"]})
    for k, e in sorted(res["medians"].items()):
        fig.append({"seats": k, "series": "median", "pairing_id": "", "hands_per_block": e["hands_per_block"], "n_blocks": "",
                    "sigma_D": e["sigma_D"], "sigma_D_lo": e["sigma_D_median_ci"][0], "sigma_D_hi": e["sigma_D_median_ci"][1],
                    "sigma_rel_6max": e["sigma_D_rel_6max"], "sigma_rel_6max_lo": e["sigma_D_rel_6max_ci"][0],
                    "sigma_rel_6max_hi": e["sigma_D_rel_6max_ci"][1],
                    "hands_required": e["hands_required_1bb100"], "hands_required_lo": e["hands_required_1bb100_median_ci"][0],
                    "hands_required_hi": e["hands_required_1bb100_median_ci"][1],
                    "hands_rel_6max": e["hands_required_1bb100_rel_6max"],
                    "hands_rel_6max_lo": e["hands_required_1bb100_rel_6max_ci"][0],
                    "hands_rel_6max_hi": e["hands_required_1bb100_rel_6max_ci"][1],
                    "blocks_required": e["blocks_required_1bb100"]})
    with (out / "figure_data.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fig[0]), lineterminator="\n")
        w.writeheader()
        w.writerows([{k: _cell(v) for k, v in r.items()} for r in fig])
    summary = {
        "description": "FHR3A table-size sweep, NLHE 100BB at 3/4/6/8 seats. Target: 1 BB/100 of candidate hands, "
                       "two-sided alpha 0.05, 80% power. Medians over pairings p1-p3.",
        "provisional": provisional,
        "question": "Does required played hands (per-hand resolving difficulty) stay flat in table size?",
        "per_pairing": [{k: v for k, v in r.items()} for r in rows],
        "medians": {str(k): v for k, v in sorted(res["medians"].items())},
        "elasticity_hands_vs_seats": res["elasticity_hands_vs_seats"],
        "n_first_for_frozen": res["n_first_for_frozen"],
        "bootstrap_reps": res["bootstrap_reps"],
        "sources": {str(k): {kk: vv for kk, vv in v.items() if kk != "fingerprint"} for k, v in prov.items()},
        "invariant_checks_passed": CHECKS,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=float) + "\n")


def git_sha() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def manifest(prov: dict, out: Path) -> dict:
    return {
        "description": "FHR3A table-size sweep (NLHE 100BB 3/4/6/8-max). 4- and 6-max reuse frozen core corpora "
                       "(fingerprints equal reports/final-analysis/MANIFEST.json); 3- and 8-max are new.",
        "analysis_code_git_sha": git_sha(),
        "commands": COMMANDS,
        "corpora": {prov[k]["experiment_id"]: prov[k]["fingerprint"] | {"seats": k, "config": prov[k]["config"],
                                                                        "frozen_core_corpus": prov[k]["frozen_corpus"]}
                    for k in sorted(prov)},
        "outputs": {name: sha256(out / name) for name in OUTPUTS},
        "n_invariant_checks": len(CHECKS),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--new-results", default="results", help="root holding the new 3-/8-max corpora")
    ap.add_argument("--allow-partial", action="store_true", help="smoke/dev: accept < target blocks (provisional)")
    ap.add_argument("--freeze", action="store_true", help="write MANIFEST.json")
    ap.add_argument("--verify", action="store_true", help="recompute and compare with MANIFEST.json")
    a = ap.parse_args()
    out = Path(a.out)
    if a.allow_partial and (out.resolve() == OUT.resolve() or a.freeze):
        sys.exit("--allow-partial output is provisional: use a different --out and no --freeze")
    try:
        data, prov = load(Path(a.new_results), a.allow_partial)
        res = analyse(data, a.boot)
        crosscheck_frozen(res)
    except CheckFailed as exc:
        sys.exit(f"CHECK FAILED: {exc}")
    if a.verify:
        old = json.loads((out / "MANIFEST.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            write_outputs(res, prov, Path(tmp), provisional=False)
            new = manifest(prov, Path(tmp))
        bad = [f for f in OUTPUTS if old["outputs"].get(f) != new["outputs"][f]]
        bad += [f"corpus {e}" for e in old["corpora"] if old["corpora"][e] != {**new["corpora"].get(e, {})}]
        print("table-size MANIFEST verified" if not bad else f"DRIFT: {bad}")
        sys.exit(1 if bad else 0)
    write_outputs(res, prov, out, provisional=a.allow_partial)
    print(f"{len(CHECKS)} invariant checks passed; wrote {out}/{{{','.join(OUTPUTS)}}}")
    for k, e in sorted(res["medians"].items()):
        print(f"  {k}-max: {e['hands_per_block']:.0f} hands/block  sigma_D {e['sigma_D']:.2f}  "
              f"blocks {e['blocks_required_1bb100']:,.0f}  hands {e['hands_required_1bb100'] / 1e6:.2f}M  "
              f"hands vs 6-max {e['hands_required_1bb100_rel_6max']:.2f} "
              f"[{e['hands_required_1bb100_rel_6max_ci'][0]:.2f}, {e['hands_required_1bb100_rel_6max_ci'][1]:.2f}]")
    el = res["elasticity_hands_vs_seats"]["median"]
    print(f"  elasticity of required hands in seats (median series): {el['overall']:+.3f} "
          f"[{el['overall_ci'][0]:+.3f}, {el['overall_ci'][1]:+.3f}]  (0 = per-hand invariance)")
    if a.freeze:
        (out / "MANIFEST.json").write_text(json.dumps(manifest(prov, out), indent=1) + "\n")
        print(f"wrote {out}/MANIFEST.json")


if __name__ == "__main__":
    main()
