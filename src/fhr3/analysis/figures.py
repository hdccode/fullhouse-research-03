"""Figure-ready data products (CSV) from block corpora. No plotting aesthetics.

Every file is long-format CSV with explicit columns, produced only from Parquet
results (and optionally ``power-sim`` / ``sequential`` JSON outputs):

  sigma_by_format_pairing.csv   one row per (experiment, pairing)
  hands_vs_effect.csv           required blocks/hands vs BB/100 effect (log grid)
  blocks_vs_d.csv               required blocks (and hands per config) vs standardized d
  empirical_power.csv           power-sim results with the analytic power alongside
  stack_sensitivity.csv         same variant/player count at several stack depths
  variance_concentration.csv    cumulative share of squared deviation vs top fraction
  variance_reduction.csv        raw vs all-in EV / MIVAT / AIVAT (when populated)
  cost_translation.csv          hands -> CPU hours -> wall-clock hours at W workers
  relations.csv                 pairing/correlation labels between configs
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from fhr3.analysis.compare import compare_paths
from fhr3.analysis.report import analyze_table
from fhr3.analysis.stats import (
    DEFAULT_DELTAS_BB100,
    analytic_power,
    bb100_to_block,
    concentration_curve,
    required_blocks,
)
from fhr3.io.store import read_blocks

EFFECT_GRID = [round(float(x), 4) for x in np.logspace(np.log10(0.1), np.log10(20), 40)]
D_GRID = [float(x) for x in np.logspace(-3, -1, 30)]


def measured_aggregate_throughput(paths: list[Path], experiment_id: str) -> float | None:
    """Block-weighted aggregate blocks/s of the experiment's simulate manifests."""
    for p in map(Path, paths):
        runs = p / "runs" if p.name == experiment_id else p.parent / "runs"
        if (p.name == experiment_id or p.parent.name == experiment_id) and runs.exists():
            blocks = secs = 0.0
            for f in runs.glob("*.json"):
                s = json.loads(f.read_text()).get("summary") or {}
                if s.get("blocks") and s.get("wall_s"):
                    blocks += s["blocks"]
                    secs += s["wall_s"]
            return blocks / secs if secs else None
    return None


def _write(path: Path, header: list[str], rows: list[list[Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return path


def write_figure_data(
    paths: list[Path],
    out_dir: Path,
    powersim_json: list[Path] | None = None,
    workers: int = 8,
    alpha: float = 0.05,
) -> list[Path]:
    out_dir = Path(out_dir)
    cmp = compare_paths(paths, DEFAULT_DELTAS_BB100, 0.8, alpha)
    rows = [r for r in cmp["rows"] if r["sd_D"] > 0]
    written = []

    written.append(_write(out_dir / "sigma_by_format_pairing.csv", [
        "experiment_id", "pairing_id", "role", "variant", "player_count", "stack_bb", "label", "n_blocks",
        "hands_per_block", "candidate_hands_per_side", "mean_D", "mean_bb100", "sd_D", "frac_zero", "skew",
        "excess_kurtosis", "q001", "q01", "q99", "q999", "conc_top1pct", "conc_top0p1pct", "allin_rate_per_hand",
        "showdown_rate_per_hand", "mean_pot_bb", "max_pot_bb", "blocks_per_s_core", "storage_bytes_per_block"],
        [[r["experiment_id"], r["pairing_id"], r["role"], r["variant"], r["player_count"], r["stack_bb"], r["label"], r["n_blocks"],
          r["hands_per_block"], r["candidate_hands_per_side"], r["mean_D"], r["mean_bb100"], r["sd_D"], r["frac_zero"],
          r["skew"], r["excess_kurtosis"], r["q001"], r["q01"], r["q99"], r["q999"], r["concentration"].get("0.01"),
          r["concentration"].get("0.001"), r["allin_rate_per_hand"], r["showdown_rate_per_hand"], r["mean_pot_bb"],
          r["max_pot_bb"], r["blocks_per_s_core"], r["storage_bytes_per_block"]] for r in rows]))

    hv = []
    for r in rows:
        for dl in EFFECT_GRID:
            db = bb100_to_block(dl, r["candidate_hands_per_side"])
            n80, n95 = required_blocks(r["sd_D"], db, alpha, 0.8), required_blocks(r["sd_D"], db, alpha, 0.95)
            hv.append([r["experiment_id"], r["pairing_id"], r["label"], dl, db / r["sd_D"], math.ceil(n80),
                       round(math.ceil(n80) * r["hands_per_block"]), math.ceil(n95), round(math.ceil(n95) * r["hands_per_block"])])
    written.append(_write(out_dir / "hands_vs_effect.csv", [
        "experiment_id", "pairing_id", "label", "delta_bb100", "standardized_d", "blocks_power80",
        "played_hands_power80", "blocks_power95", "played_hands_power95"], hv))

    bd = []
    for d in D_GRID:
        n80, n95 = math.ceil(required_blocks(1.0, d, alpha, 0.8)), math.ceil(required_blocks(1.0, d, alpha, 0.95))
        for r in rows:
            bd.append([d, n80, n95, r["experiment_id"], r["pairing_id"], r["label"], round(n80 * r["hands_per_block"]),
                       100.0 * d * r["sd_D"] / r["candidate_hands_per_side"]])
    written.append(_write(out_dir / "blocks_vs_d.csv", [
        "standardized_d", "blocks_power80", "blocks_power95", "experiment_id", "pairing_id", "label",
        "played_hands_power80", "delta_bb100_equivalent"], bd))

    ep = []
    for pj in powersim_json or []:
        data = json.loads(Path(pj).read_text())
        for key, e in data.items():
            for x in e["results"]:
                ap = analytic_power(e["sd_D"], x["delta_block"], x["n_blocks"], alpha) if x["delta_block"] else alpha
                ep.append([e.get("experiment_id"), e.get("pairing_id", key.split("/", 1)[-1]), x["kind"], x["n_blocks"],
                           x.get("played_hands"), x["delta_bb100"], x["delta_block"], x["reps"], x["power_two_sided"],
                           x["power_correct_sign"], x["p_select_stronger"], ap])
    written.append(_write(out_dir / "empirical_power.csv", [
        "experiment_id", "pairing_id", "kind", "n_blocks", "played_hands", "delta_bb100", "delta_block", "reps",
        "power_two_sided", "power_correct_sign", "p_select_stronger", "analytic_power_two_sided"], ep))

    groups: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for r in rows:
        groups.setdefault((r["variant"], r["player_count"], r["pairing_id"]), []).append(r)
    ss = []
    for (variant, k, pid), g in sorted(groups.items()):
        if len({r["stack_bb"] for r in g}) < 2:
            continue
        for r in sorted(g, key=lambda r: r["stack_bb"]):
            t1 = r["targets"].get("1")
            ss.append([variant, k, pid, r["stack_bb"], r["n_blocks"], r["sd_D"], r["excess_kurtosis"],
                       r["concentration"].get("0.01"), r["allin_rate_per_hand"], r["mean_pot_bb"],
                       t1["blocks"] if t1 else None, t1["played_hands"] if t1 else None])
    written.append(_write(out_dir / "stack_sensitivity.csv", [
        "variant", "player_count", "pairing_id", "stack_bb", "n_blocks", "sd_D", "excess_kurtosis", "conc_top1pct",
        "allin_rate_per_hand", "mean_pot_bb", "blocks_1bb100_power80", "played_hands_1bb100_power80"], ss))

    table = pa.concat_tables([read_blocks(p) for p in paths], promote_options="default")
    vc, vr = [], []
    entries = analyze_table(table, n_boot=0)
    for e in entries.values():
        if "paired" not in e or not e["paired"]["sd_D"] > 0:
            continue
        m = pc.and_(pc.and_(pc.equal(table.column("config_hash"), e["config_hash"]),
                            pc.equal(table.column("pairing_id"), e["pairing_id"])), table.column("valid"))
        D = np.asarray(table.filter(m).column("D").to_numpy(zero_copy_only=False), dtype=float)
        label = f"{e['variant']}/{e['player_count']}max/{e['stack_bb']:g}bb"
        for frac, share in concentration_curve(D):
            vc.append([e["experiment_id"], e["pairing_id"], label, frac, share])
        k, sd = e["candidate_hands_per_side"], e["paired"]["sd_D"]
        base_n = required_blocks(sd, bb100_to_block(1.0, k), alpha, 0.8)
        vr.append([e["experiment_id"], e["pairing_id"], label, "raw", e["paired"]["mean_D"], sd, 1.0, 1.0, 0.0, None, math.ceil(base_n)])
        for name, es in e.get("estimators", {}).items():
            n_e = required_blocks(es["sd"], bb100_to_block(1.0, k), alpha, 0.8)
            vr.append([e["experiment_id"], e["pairing_id"], label, name, es["mean"], es["sd"], es["variance_ratio_vs_raw"],
                       es["corr_with_raw"], es["mean_diff_vs_raw"], es["mean_diff_z"], math.ceil(n_e) if math.isfinite(n_e) else None])
    written.append(_write(out_dir / "variance_concentration.csv", [
        "experiment_id", "pairing_id", "label", "top_fraction", "cumulative_share_sq_dev"], vc))
    written.append(_write(out_dir / "variance_reduction.csv", [
        "experiment_id", "pairing_id", "label", "estimator", "mean_D", "sd_D", "variance_ratio_vs_raw",
        "corr_with_raw", "mean_diff_vs_raw", "mean_diff_z", "blocks_1bb100_power80"], vr))

    ct = []
    for r in rows:
        agg = measured_aggregate_throughput(paths, r["experiment_id"])
        for dl, t in r["targets"].items():
            if not t or not r["blocks_per_s_core"]:
                continue
            cpu_h = t["blocks"] / r["blocks_per_s_core"] / 3600.0
            ct.append([r["experiment_id"], r["pairing_id"], r["label"], float(dl), t["blocks"], t["played_hands"],
                       r["blocks_per_s_core"], cpu_h, cpu_h / workers, workers,
                       agg, t["blocks"] / agg / 3600.0 if agg else None,
                       (r["storage_bytes_per_block"] or 0) * t["blocks"] / 1e6])
    written.append(_write(out_dir / "cost_translation.csv", [
        "experiment_id", "pairing_id", "label", "delta_bb100", "blocks_power80", "played_hands_power80",
        # per-worker speed measured under load; wall_hours_at_workers assumes perfect scaling
        "blocks_per_s_per_worker", "cpu_hours", "wall_hours_at_workers", "workers",
        # wall-clock at the aggregate throughput actually measured by that experiment's runs
        "measured_aggregate_blocks_per_s", "wall_hours_measured_aggregate", "storage_mb"], ct))

    written.append(_write(out_dir / "relations.csv", [
        "pairing_id", "a", "b", "a_experiment", "b_experiment", "relation", "corr_D", "common_blocks"],
        [[x["pairing_id"], x["a"], x["b"], x["a_experiment"], x["b_experiment"], x["relation"], x["corr_D"],
          x["common_blocks"]] for x in cmp["relations"]]))
    return written
