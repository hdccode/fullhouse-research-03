"""FHR3A controlled table-size suite: NLHE 100BB at 3 / 4 / 6 / 8 seats under one scheduled
reference population (reads Parquet + locks only; never re-runs poker). Design and caveats:
docs/table_size.md.

Usage (repo root):
  .venv/bin/python scripts/table_size_analysis.py                  # analyse + write reports/table-size/
  .venv/bin/python scripts/table_size_analysis.py --freeze         # ... and write reports/table-size/MANIFEST.json
  .venv/bin/python scripts/table_size_analysis.py --verify         # recompute; exit 1 if outputs/corpora drifted
  .venv/bin/python scripts/table_size_analysis.py --allow-partial --suite-results DIR --out DIR2
                                                                   # smoke/dev only: provisional, never frozen

PRIMARY (the publication 3/4/6/8 curve): ONLY the four controlled corpora
  results/fhr3a-nlhe{3,4,6,8}-100bb-tablesize-v1   configs/tablesize/nlhe_{k}max_100bb.yaml
  Every relative reference slot follows cycle[(block + j) mod 5] with
  cycle = [neutral, neutral, tight, loose, aggressive]; the analysis re-checks from the lineup
  recorded in each row that every slot of every table size is exactly 40/20/20/20.
HISTORICAL (reported separately, never mixed into the primary curve): the frozen core corpora
  fhr3-nlhe4-100bb-v2 and fhr3-nlhe6-100bb-pilot-v1, whose fixed reference populations change
  with table size. Their Parquet fingerprints must equal reports/final-analysis/MANIFEST.json,
  and every recomputed number must equal the frozen ranking.json / allin.csv / pilot_table.csv.
  Because the controlled suite shares their root seed and deal layout, the 4- and 6-max
  controlled blocks are chance-matched to the historical blocks with the same id: the
  controlled-vs-historical sigma ratio at fixed table size is a paired population comparison.
Nothing under reports/final-analysis is written.

Outputs (reports/table-size/)
  summary.csv       PRIMARY: one row per table size x pairing (p1-p3): metrics + ratios vs controlled 6-max
  figure_data.csv   PRIMARY: long format for the table-size figure (pairing rows + median rows)
  historical.csv    frozen 4/6-max rows (same metric definitions), incl. same-n (first 30k) columns
  summary.json      primary + historical + controlled-vs-historical sections, mixture checks,
                    invariant checks and provenance
  MANIFEST.json     (--freeze) corpus fingerprints, output sha256s, git SHA, commands

Definitions (identical to scripts/final_analysis.py)
  D = X_A - X_B per matched block (BB); k = candidate hands per side = seats; 2k played hands.
  blocks_required = ceil(((z_.975 + z_.8) * sigma_D / (1 BB/100 * k / 100))^2)
  hands_required  = blocks_required * played hands per block
  Per-played-hand invariance <=> sigma_D^2 proportional to k <=> hands_required flat in k.
  elasticity of hands_required in k = d log(hands) / d log(k) = (d log var / d log k) - 1.
The unit of inference is always the block. p1/p2/p3 are kept separate throughout; medians are
over the three pairings. Bootstrap CIs resample blocks within each corpus (corpora of different
table sizes are independent: different deal layouts).
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
from collections import Counter
from pathlib import Path

import numpy as np
import pyarrow.compute as pc
import pyarrow.parquet as pq
from scipy import stats as sps

from fhr3.analysis.stats import required_blocks, variance_concentration
from fhr3.configs.experiment import load_config
from fhr3.io.store import read_blocks

SEATS = (3, 4, 6, 8)
SUITE = {k: (f"configs/tablesize/nlhe_{k}max_100bb.yaml", f"fhr3a-nlhe{k}-100bb-tablesize-v1") for k in SEATS}
HISTORICAL = {4: ("configs/nlhe_4max_100bb_v2.yaml", "fhr3-nlhe4-100bb-v2", "nlhe/4max/100bb"),
              6: ("configs/nlhe_6max_100bb.yaml", "fhr3-nlhe6-100bb-pilot-v1", "nlhe/6max/100bb")}
BASE_K = 6
TARGET_BLOCKS = {"p1": 30000, "p2": 30000, "p3": 30000, "c0": 10000}
ROLES = ("p1", "p2", "p3")
MIXTURE = {"neutral": 0.4, "tight": 0.2, "loose": 0.2, "aggressive": 0.2}
FA = Path("reports/final-analysis")
OUT = Path("reports/table-size")
OUTPUTS = ["summary.csv", "figure_data.csv", "historical.csv", "summary.json"]
Z80 = sps.norm.ppf(0.975) + sps.norm.ppf(0.8)
COLS = ["config_hash", "pairing_id", "pairing_hash", "block_id", "valid", "D", "played_hands",
        "candidate_hands_per_side", "allin_hands", "pot_bb_max", "stack_bb"]
COMMANDS = [
    ".venv/bin/python scripts/table_size_analysis.py --boot 1000 --freeze",
    ".venv/bin/python scripts/table_size_analysis.py --boot 1000 --verify",
]
RATIO_METRICS = (("sigma_D", "sd"), ("var_D", "var"), ("blocks_required_1bb100", "blocks"),
                 ("hands_required_1bb100", "hands"))


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
def load_corpus(k: int, cfg_path: str, d: Path, *, frozen: bool, allow_partial: bool) -> tuple[dict, dict]:
    tag = f"{'historical' if frozen else 'controlled'} {k}-max"
    if not d.exists():
        raise CheckFailed(f"{tag} corpus missing: {d} (run scripts/run_table_size.sh first)")
    cfg = load_config(cfg_path)
    fp = fingerprint(d)
    check(fp["config_hash"] == cfg.config_hash, f"{tag} experiment lock config_hash = {cfg_path}")
    if frozen:
        ref = json.loads((FA / "MANIFEST.json").read_text())["corpora"][cfg.experiment_id]
        check(fp["config_hash"] == ref["config_hash"], f"{tag} config_hash = frozen MANIFEST")
        for pid, v in ref["pairings"].items():
            got = fp["pairings"][pid]
            check(got["parquet_sha256"] == v["parquet_sha256"] and got["rows"] == v["rows"],
                  f"{tag} {pid} Parquet fingerprint = frozen MANIFEST ({v['rows']} rows)")
    cols = COLS + ([] if frozen else ["variant_json"])
    t = read_blocks(d, columns=cols)  # raises on duplicate block ids
    check(set(t.column("config_hash").to_pylist()) == {cfg.config_hash}, f"{tag} rows carry config_hash {cfg.config_hash}")
    out, bps = {}, throughput(d)
    for p in cfg.pairings:
        pid, role = p.pairing_id, p.pairing_id.split("-", 1)[0]
        tp = t.filter(pc.equal(t.column("pairing_id"), pid))
        check(tp.num_rows > 0, f"{tag} {pid} present")
        check(set(tp.column("pairing_hash").to_pylist()) == {p.pairing_hash}, f"{tag} {pid} pairing_hash = config")
        o = np.argsort(tp.column("block_id").to_numpy())
        col = lambda c: np.asarray(tp.column(c).to_numpy(zero_copy_only=False))[o]  # noqa: E731
        b = col("block_id")
        check(b[0] == 0 and b[-1] + 1 == b.size and np.unique(b).size == b.size, f"{tag} {pid} block ids contiguous 0..{b.size - 1}")
        if not frozen and not allow_partial:
            check(b.size == TARGET_BLOCKS[role], f"{tag} {pid} has exactly {TARGET_BLOCKS[role]} blocks ({b.size})")
        check(bool(col("valid").all()), f"{tag} {pid} no invalid blocks")
        D = col("D").astype(float)
        check(bool(np.isfinite(D).all()), f"{tag} {pid} no NaN/inf D")
        played = col("played_hands").astype(float)
        check(bool((played == 2 * k).all()) and bool((col("candidate_hands_per_side") == k).all()),
              f"{tag} {pid} every block = {2 * k} played hands, k = {k}")
        if not frozen:
            check_mixture(tag, p, k, b, col("variant_json"), allow_partial)
        if role == "c0":
            check(bool((D == 0).all()), f"{tag} {pid} self-play control D == 0 exactly ({D.size} blocks)")
            continue
        out[role] = {"exp": cfg.experiment_id, "pairing_id": pid, "D": D, "block_id": b, "played": played,
                     "k": float(k), "allin": col("allin_hands"), "potmax": col("pot_bb_max").astype(float),
                     "stack": float(col("stack_bb")[0]), "bps": bps}
    prov = {"experiment_id": cfg.experiment_id, "config": cfg_path, "config_hash": cfg.config_hash,
            "frozen_core_corpus": frozen, "results_dir": str(d), "fingerprint": fp, "blocks_per_s_8_workers": bps}
    return out, prov


def check_mixture(tag: str, pairing, k: int, block_ids: np.ndarray, vj: np.ndarray, allow_partial: bool) -> None:
    """From the lineup recorded in each row: every block follows the schedule, and every relative
    slot has exactly the 40/20/20/20 style mixture over the corpus."""
    styles = [json.loads(s)["reference_lineup"]["styles"] for s in vj]
    rule_ok = all(st == [str(x.params["style"]) for x in pairing.reference_specs(int(b), k)]
                  for b, st in zip(block_ids, styles))
    check(rule_ok, f"{tag} {pairing.pairing_id} every block's recorded lineup = cycle[(b + j) mod 5]")
    n = len(styles)
    if allow_partial and n % 5:
        return
    check(n % 5 == 0, f"{tag} {pairing.pairing_id} block count is a multiple of 5 ({n})")
    for j in range(k - 1):
        c = Counter(st[j] for st in styles)
        want = {s: round(f * n) for s, f in MIXTURE.items()}
        check(dict(c) == want, f"{tag} {pairing.pairing_id} slot {j} mixture exactly 40/20/20/20 over {n} blocks")


# ------------------------------------------------------------------ metrics
def blocks_needed(sd: float, k: float) -> int:
    return math.ceil(required_blocks(sd, 1.0 * k / 100, 0.05, 0.8))


def metrics(d: dict, n_first: int | None = None) -> dict:
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
    if n_first is not None:  # same-n sensitivity for the larger historical corpora
        sdp = float(D[:n_first].std(ddof=1))
        r |= {"n_first": n_first, "sigma_D_first_n": sdp, "hands_required_1bb100_first_n": blocks_needed(sdp, k) * hpb}
    return r


def boot_sds(D: np.ndarray, reps: int, seed: tuple[int, ...]) -> np.ndarray:
    rng = np.random.default_rng(list(seed))
    n, out = D.size, np.empty(reps)
    for i in range(reps):
        out[i] = D[rng.integers(0, n, n)].std(ddof=1)
    return out


def q(x: np.ndarray) -> list[float]:
    return [float(np.quantile(x, 0.025)), float(np.quantile(x, 0.975))]


def analyse(data: dict, reps: int, base_k: int = BASE_K, seed: int = 20261101, n_first: int | None = None) -> dict:
    """data: {(seats, role): corpus}. Pairing rows, ratios vs the base table size (same pairing),
    medians over p1-p3 with ratio-of-medians CIs, and elasticities of required hands in seats."""
    seats = sorted({k for k, _ in data})
    rows, boot = {}, {}
    for (k, role), d in sorted(data.items()):
        r = metrics(d, n_first)
        r["role"] = role
        sds = boot_sds(d["D"], reps, (seed, k, ROLES.index(role)))
        b = (Z80 * sds / (k / 100)) ** 2  # continuous required blocks per bootstrap draw
        boot[(k, role)] = {"sd": sds, "var": sds ** 2, "blocks": b, "hands": b * r["hands_per_block"]}
        r["sigma_D_ci"] = q(sds)
        r["hands_required_ci"] = q(boot[(k, role)]["hands"])
        rows[(k, role)] = r
    for (k, role), r in rows.items():
        base, bb = rows[(base_k, role)], boot[(base_k, role)]
        for m, bm in RATIO_METRICS:
            r[f"{m}_rel_base"] = r[m] / base[m]
            r[f"{m}_rel_base_ci"] = q(boot[(k, role)][bm] / bb[bm]) if k != base_k else [1.0, 1.0]
    med, mb = {}, {}
    for k in seats:
        e = {"seats": k, "hands_per_block": rows[(k, "p1")]["hands_per_block"]}
        for m, bm in RATIO_METRICS:
            vals = [rows[(k, r)][m] for r in ROLES]
            e[m] = float(np.median(vals))
            e[f"{m}_pairing_range"] = [float(min(vals)), float(max(vals))]
            mb[(k, bm)] = np.median(np.stack([boot[(k, r)][bm] for r in ROLES]), axis=0)
            e[f"{m}_median_ci"] = q(mb[(k, bm)])
        for m in ("p_D_zero", "excess_kurtosis", "top1pct_share", "frac_blocks_pot_ge_1stack", "share_pot_ge_1stack",
                  "frac_blocks_allin", "share_allin", "var_D_per_candidate_hand", "wall_h_required_8_workers"):
            vals = [rows[(k, r)][m] for r in ROLES]
            e[m] = float(np.median(vals))
            e[f"{m}_pairing_range"] = [float(min(vals)), float(max(vals))]
        med[k] = e
    for k in seats:
        for m, bm in RATIO_METRICS:
            med[k][f"{m}_rel_base"] = med[k][m] / med[base_k][m]
            med[k][f"{m}_rel_base_ci"] = q(mb[(k, bm)] / mb[(base_k, bm)]) if k != base_k else [1.0, 1.0]
            med[k][f"{m}_rel_base_roles_below_1"] = int(sum(rows[(k, r)][f"{m}_rel_base"] < 1 for r in ROLES))
    lk = np.log(seats)
    xc = lk - lk.mean()

    def slope(y: np.ndarray):
        if y.ndim == 2:
            return (xc[:, None] * (y - y.mean(axis=0))).sum(axis=0) / (xc ** 2).sum()
        return float((xc * (y - y.mean())).sum() / (xc ** 2).sum())

    series = {r: ([rows[(k, r)]["hands_required_1bb100"] for k in seats], np.stack([boot[(k, r)]["hands"] for k in seats]))
              for r in ROLES}
    series["median"] = ([med[k]["hands_required_1bb100"] for k in seats], np.stack([mb[(k, "hands")] for k in seats]))
    elast = {}
    for name, (pt, bs) in series.items():
        lp, lb = np.log(pt), np.log(bs)
        e = {"overall": slope(lp), "overall_ci": q(slope(lb)), "segments": {}}
        for i in range(len(seats) - 1):
            dx = lk[i + 1] - lk[i]
            e["segments"][f"{seats[i]}->{seats[i + 1]}"] = {"elasticity": float((lp[i + 1] - lp[i]) / dx),
                                                             "ci": q((lb[i + 1] - lb[i]) / dx)}
        elast[name] = e
    return {"rows": rows, "medians": med, "elasticity_hands_vs_seats": elast, "base_seats": base_k,
            "bootstrap_reps": reps}


def controlled_vs_historical(ctrl: dict, hist: dict, reps: int) -> dict:
    """At 4 and 6 seats: same root seed and deal layout, so block b deals the same cards in both
    corpora. sigma ratio controlled/historical on the common blocks, paired bootstrap."""
    out = {}
    for k in HISTORICAL:
        for role in ROLES:
            c, h = ctrl[(k, role)], hist[(k, role)]
            n = min(c["D"].size, h["D"].size)
            check(bool(np.array_equal(c["block_id"][:n], h["block_id"][:n])), f"controlled/historical {k}-max {role} common block ids 0..{n - 1}")
            x, y = c["D"][:n], h["D"][:n]
            rng = np.random.default_rng([20261102, k, ROLES.index(role)])
            idx = (rng.integers(0, n, n) for _ in range(reps))
            b = np.array([x[i].std(ddof=1) / y[i].std(ddof=1) for i in idx])
            r = float(x.std(ddof=1) / y.std(ddof=1))
            out[f"{k}|{role}"] = {"seats": k, "role": role, "common_blocks": n, "sigma_ratio_controlled_over_historical": r,
                                  "sigma_ratio_ci": q(b), "hands_ratio_controlled_over_historical": r ** 2,
                                  "hands_ratio_ci": [v ** 2 for v in q(b)], "corr_D": float(np.corrcoef(x, y)[0, 1])}
    return out


# ------------------------------------------------------------------ cross-check historical vs frozen outputs
def close(a: float, b: float, rel: float = 1e-9) -> bool:
    return math.isclose(float(a), float(b), rel_tol=rel, abs_tol=1e-12)


def crosscheck_frozen(hist_rows: dict) -> None:
    rk = json.loads((FA / "ranking.json").read_text())["per_pairing"]
    allin = {(r["format"], r["pairing_id"]): r for r in csv.DictReader(open(FA / "allin.csv"))}
    pilot = {(r["format"], r["pairing_id"]): r for r in csv.DictReader(open(FA / "core" / "pilot_table.csv"))}
    for k, (_, _, label) in HISTORICAL.items():
        for role in ROLES:
            r = hist_rows[(k, role)]
            f = rk[f"{label}|{role}"]
            tag = f"historical {k}-max {role}"
            check(f["pairing_id"] == r["pairing_id"] and f["n"] == r["n_blocks"], f"{tag} n = ranking.json")
            check(close(f["sd"], r["sigma_D"]), f"{tag} sigma_D = ranking.json")
            check(f["blocks"] == r["blocks_required_1bb100"], f"{tag} blocks required = ranking.json")
            check(close(f["hands"], r["hands_required_1bb100"]), f"{tag} hands required = ranking.json")
            a = allin[(label, r["pairing_id"])]
            for mine, theirs in (("p_D_zero", "frac_zero"), ("frac_blocks_allin", "frac_blocks_allin"),
                                 ("share_allin", "share_allin"), ("frac_blocks_pot_ge_1stack", "frac_blocks_pot_ge_1stack"),
                                 ("share_pot_ge_1stack", "share_pot_ge_1stack")):
                check(close(a[theirs], r[mine]), f"{tag} {mine} = allin.csv {theirs}")
            p = pilot[(label, r["pairing_id"])]
            if int(p["n_blocks"]) == r["n_blocks"]:
                check(close(p["excess_kurtosis"], r["excess_kurtosis"]), f"{tag} excess kurtosis = pilot_table.csv")
                check(close(p["conc_top0.01"], r["top1pct_share"]), f"{tag} top-1% share = pilot_table.csv")


# ------------------------------------------------------------------ outputs
BASE_COLS = [
    "seats", "role", "pairing_id", "experiment_id", "n_blocks", "hands_per_block", "candidate_hands_per_side",
    "mean_bb100", "sigma_D", "sigma_D_ci", "var_D", "var_D_per_candidate_hand", "blocks_required_1bb100",
    "hands_required_1bb100", "hands_required_ci", "p_D_zero", "excess_kurtosis", "top1pct_share", "top01pct_share",
    "frac_blocks_pot_ge_1stack", "share_pot_ge_1stack", "frac_blocks_allin", "share_allin",
    "sigma_D_rel_se_delta", "blocks_per_s_8_workers", "wall_h_required_8_workers",
]
REL_COLS = [f"{m}_rel_base{s}" for m, _ in RATIO_METRICS for s in ("", "_ci")]


def _cell(v):
    if isinstance(v, list):
        return ";".join(f"{x:.10g}" for x in v)
    if isinstance(v, float):
        return f"{v:.10g}"
    return v


def _write_rows(path: Path, rows: list[dict], cols: list[str], rename: dict[str, str]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow([rename.get(c, c) for c in cols])
        for r in rows:
            w.writerow([_cell(r[c]) for c in cols])


def write_outputs(res: dict, hist: dict, cvh: dict, prov: dict, out: Path, provisional: bool) -> None:
    out.mkdir(parents=True, exist_ok=True)
    to6 = {c: c.replace("_rel_base", "_rel_6max") for c in REL_COLS}
    rows = [res["rows"][key] for key in sorted(res["rows"])]
    _write_rows(out / "summary.csv", rows, BASE_COLS + REL_COLS, to6)
    hrows = [hist["rows"][key] for key in sorted(hist["rows"])]
    _write_rows(out / "historical.csv", hrows,
                BASE_COLS + REL_COLS + ["n_first", "sigma_D_first_n", "hands_required_1bb100_first_n"], to6)
    fig = []
    for r in rows:
        fig.append({"seats": r["seats"], "series": r["role"], "pairing_id": r["pairing_id"],
                    "hands_per_block": r["hands_per_block"], "n_blocks": r["n_blocks"],
                    "sigma_D": r["sigma_D"], "sigma_D_lo": r["sigma_D_ci"][0], "sigma_D_hi": r["sigma_D_ci"][1],
                    "sigma_rel_6max": r["sigma_D_rel_base"], "sigma_rel_6max_lo": r["sigma_D_rel_base_ci"][0],
                    "sigma_rel_6max_hi": r["sigma_D_rel_base_ci"][1],
                    "blocks_required": r["blocks_required_1bb100"],
                    "hands_required": r["hands_required_1bb100"], "hands_required_lo": r["hands_required_ci"][0],
                    "hands_required_hi": r["hands_required_ci"][1],
                    "hands_rel_6max": r["hands_required_1bb100_rel_base"],
                    "hands_rel_6max_lo": r["hands_required_1bb100_rel_base_ci"][0],
                    "hands_rel_6max_hi": r["hands_required_1bb100_rel_base_ci"][1]})
    for k, e in sorted(res["medians"].items()):
        fig.append({"seats": k, "series": "median", "pairing_id": "", "hands_per_block": e["hands_per_block"], "n_blocks": "",
                    "sigma_D": e["sigma_D"], "sigma_D_lo": e["sigma_D_median_ci"][0], "sigma_D_hi": e["sigma_D_median_ci"][1],
                    "sigma_rel_6max": e["sigma_D_rel_base"], "sigma_rel_6max_lo": e["sigma_D_rel_base_ci"][0],
                    "sigma_rel_6max_hi": e["sigma_D_rel_base_ci"][1],
                    "blocks_required": e["blocks_required_1bb100"],
                    "hands_required": e["hands_required_1bb100"], "hands_required_lo": e["hands_required_1bb100_median_ci"][0],
                    "hands_required_hi": e["hands_required_1bb100_median_ci"][1],
                    "hands_rel_6max": e["hands_required_1bb100_rel_base"],
                    "hands_rel_6max_lo": e["hands_required_1bb100_rel_base_ci"][0],
                    "hands_rel_6max_hi": e["hands_required_1bb100_rel_base_ci"][1]})
    with (out / "figure_data.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fig[0]), lineterminator="\n")
        w.writeheader()
        w.writerows([{k: _cell(v) for k, v in r.items()} for r in fig])

    def section(r: dict, note: str) -> dict:
        return {"note": note, "base_seats": r["base_seats"], "bootstrap_reps": r["bootstrap_reps"],
                "per_pairing": [r["rows"][key] for key in sorted(r["rows"])],
                "medians": {str(k): v for k, v in sorted(r["medians"].items())},
                "elasticity_hands_vs_seats": r["elasticity_hands_vs_seats"]}

    summary = {
        "description": "FHR3A controlled table-size suite, NLHE 100BB at 3/4/6/8 seats, one scheduled reference "
                       "population (per-slot 40% neutral / 20% tight / 20% loose / 20% aggressive). Target: 1 BB/100 "
                       "of candidate hands, two-sided alpha 0.05, 80% power. Medians over pairings p1-p3. Ratios "
                       "('_rel_base') are relative to the controlled 6-max corpus.",
        "provisional": provisional,
        "question": "Does required played hands (per-hand resolving difficulty) stay flat in table size?",
        "primary_controlled": section(res, "The publication 3/4/6/8 curve: controlled corpora only."),
        "historical_frozen": section(hist, "Frozen core corpora with table-size-dependent fixed populations "
                                           "(4-max mixed3-v1, 6-max mixed5-v1). NOT part of the primary curve. "
                                           "'_rel_base' is relative to historical 6-max; '*_first_n' = first 30k blocks."),
        "controlled_vs_historical": {"note": "Same table size, same deals (paired on block id); only the reference "
                                             "population differs. sigma ratio controlled / historical, paired bootstrap.",
                                     "pairs": cvh},
        "sources": {"controlled": {str(k): {kk: vv for kk, vv in v.items() if kk != "fingerprint"}
                                   for k, v in prov["controlled"].items()},
                    "historical": {str(k): {kk: vv for kk, vv in v.items() if kk != "fingerprint"}
                                   for k, v in prov["historical"].items()}},
        "invariant_checks_passed": CHECKS,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=float) + "\n")


def git_sha() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def manifest(prov: dict, out: Path) -> dict:
    corpora = {}
    for group, items in prov.items():
        for k, v in sorted(items.items()):
            corpora[v["experiment_id"]] = v["fingerprint"] | {"seats": k, "config": v["config"], "role": group}
    return {
        "description": "FHR3A controlled table-size suite (NLHE 100BB 3/4/6/8-max, scheduled 40/20/20/20 reference "
                       "population). Historical frozen 4/6-max corpora are read-only and reported separately.",
        "analysis_code_git_sha": git_sha(),
        "commands": COMMANDS,
        "corpora": corpora,
        "outputs": {name: sha256(out / name) for name in OUTPUTS},
        "n_invariant_checks": len(CHECKS),
    }


def run(suite_root: Path, allow_partial: bool, reps: int) -> tuple[dict, dict, dict, dict]:
    ctrl, hist, prov = {}, {}, {"controlled": {}, "historical": {}}
    for k in SEATS:
        cfg_path, exp = SUITE[k]
        data, prov["controlled"][k] = load_corpus(k, cfg_path, suite_root / exp, frozen=False, allow_partial=allow_partial)
        ctrl |= {(k, r): v for r, v in data.items()}
    for k, (cfg_path, exp, _) in HISTORICAL.items():
        data, prov["historical"][k] = load_corpus(k, cfg_path, Path("results") / exp, frozen=True, allow_partial=False)
        hist |= {(k, r): v for r, v in data.items()}
    res = analyse(ctrl, reps)
    n_ctrl = min(v["D"].size for v in ctrl.values())
    hres = analyse(hist, reps, seed=20261103, n_first=n_ctrl)
    crosscheck_frozen(hres["rows"])
    cvh = controlled_vs_historical(ctrl, hist, reps)
    return res, hres, cvh, prov


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--suite-results", default="results", help="root holding the four controlled corpora")
    ap.add_argument("--allow-partial", action="store_true", help="smoke/dev: accept < target blocks (provisional)")
    ap.add_argument("--freeze", action="store_true", help="write MANIFEST.json")
    ap.add_argument("--verify", action="store_true", help="recompute and compare with MANIFEST.json")
    a = ap.parse_args()
    out = Path(a.out)
    if a.allow_partial and (out.resolve() == OUT.resolve() or a.freeze):
        sys.exit("--allow-partial output is provisional: use a different --out and no --freeze")
    try:
        res, hres, cvh, prov = run(Path(a.suite_results), a.allow_partial, a.boot)
    except CheckFailed as exc:
        sys.exit(f"CHECK FAILED: {exc}")
    if a.verify:
        old = json.loads((out / "MANIFEST.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            write_outputs(res, hres, cvh, prov, Path(tmp), provisional=False)
            new = manifest(prov, Path(tmp))
        bad = [f for f in OUTPUTS if old["outputs"].get(f) != new["outputs"][f]]
        bad += [f"corpus {e}" for e in old["corpora"] if old["corpora"][e] != new["corpora"].get(e)]
        print("table-size MANIFEST verified" if not bad else f"DRIFT: {bad}")
        sys.exit(1 if bad else 0)
    write_outputs(res, hres, cvh, prov, out, provisional=a.allow_partial)
    print(f"{len(CHECKS)} invariant checks passed; wrote {out}/{{{','.join(OUTPUTS)}}}")
    print("PRIMARY (controlled suite):")
    for k, e in sorted(res["medians"].items()):
        print(f"  {k}-max: {e['hands_per_block']:.0f} hands/block  sigma_D {e['sigma_D']:.2f}  "
              f"blocks {e['blocks_required_1bb100']:,.0f}  hands {e['hands_required_1bb100'] / 1e6:.2f}M  "
              f"hands vs 6-max {e['hands_required_1bb100_rel_base']:.2f} "
              f"[{e['hands_required_1bb100_rel_base_ci'][0]:.2f}, {e['hands_required_1bb100_rel_base_ci'][1]:.2f}]")
    el = res["elasticity_hands_vs_seats"]["median"]
    print(f"  elasticity of required hands in seats (median series): {el['overall']:+.3f} "
          f"[{el['overall_ci'][0]:+.3f}, {el['overall_ci'][1]:+.3f}]  (0 = per-hand invariance)")
    print("HISTORICAL (frozen, separate): " + ", ".join(
        f"{k}-max {e['hands_required_1bb100'] / 1e6:.2f}M" for k, e in sorted(hres["medians"].items())))
    if a.freeze:
        (out / "MANIFEST.json").write_text(json.dumps(manifest(prov, out), indent=1) + "\n")
        print(f"wrote {out}/MANIFEST.json")


if __name__ == "__main__":
    main()
