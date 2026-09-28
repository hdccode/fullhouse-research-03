"""Corpus-level analysis report (consumes Parquet only; never re-runs poker)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from fhr3.analysis.stats import (
    DEFAULT_DELTAS_BB100,
    bb100_to_block,
    bootstrap_ci,
    describe,
    location_shift_power,
    power_table,
)
from fhr3.io.store import read_blocks


def _single(table: pa.Table, col: str) -> Any:
    vals = pc.unique(table.column(col)).to_pylist()
    if len(vals) != 1:
        raise ValueError(f"column {col!r} is not constant within a pairing: {vals[:5]}")
    return vals[0]


def _dir_bytes(paths: list[Path]) -> int:
    total = 0
    for p in paths:
        p = Path(p)
        files = [p] if p.is_file() else list(p.rglob("blocks_*.parquet"))
        total += sum(f.stat().st_size for f in files)
    return total


def analyze_table(
    table: pa.Table,
    n_boot: int = 2000,
    deltas_bb100: tuple[float, ...] = DEFAULT_DELTAS_BB100,
    alpha: float = 0.05,
    seed: int = 0,
) -> dict[str, Any]:
    """One report entry per (config_hash, pairing_id)."""
    out: dict[str, Any] = {}
    keys = sorted(set(zip(table.column("config_hash").to_pylist(), table.column("pairing_id").to_pylist(), strict=True)))
    for chash, pid in keys:
        mask = pc.and_(pc.equal(table.column("config_hash"), chash), pc.equal(table.column("pairing_id"), pid))
        t = table.filter(mask)
        k = int(_single(t, "player_count"))
        valid_mask = t.column("valid")
        tv = t.filter(valid_mask)
        n_invalid = t.num_rows - tv.num_rows
        D = np.asarray(tv.column("D").to_numpy(zero_copy_only=False), dtype=float)
        block_ids = np.sort(t.column("block_id").to_numpy())
        entry: dict[str, Any] = {
            "config_hash": chash,
            "pairing_id": pid,
            "variant": _single(t, "variant"),
            "stack_bb": _single(t, "stack_bb"),
            "candidate_a": f"{_single(t, 'candidate_a')} [{_single(t, 'candidate_a_version')}]",
            "candidate_b": f"{_single(t, 'candidate_b')} [{_single(t, 'candidate_b_version')}]",
            "reference_population": f"{_single(t, 'reference_population')} [{_single(t, 'reference_version')}]",
            "coupling": {"candidate": _single(t, "candidate_coupling"), "reference": _single(t, "reference_coupling")},
            "blocks_total": t.num_rows,
            "blocks_invalid": n_invalid,
            "invalid_error_codes": sorted(set(x for x in t.filter(pc.invert(valid_mask)).column("error_code").to_pylist() if x)),
            "block_id_range": [int(block_ids[0]), int(block_ids[-1])] if block_ids.size else None,
            "block_ids_contiguous": bool(block_ids.size and block_ids[-1] - block_ids[0] + 1 == block_ids.size),
        }
        if D.size < 2:
            entry["warning"] = "fewer than 2 valid blocks"
            out[f"{chash}/{pid}"] = entry
            continue
        d = describe(D, k, alpha)
        entry["paired"] = d
        entry["bootstrap_ci"] = bootstrap_ci(D, n_boot=n_boot, alpha=alpha, seed=seed) if n_boot else None
        entry["power"] = power_table(d["sd_D"], k, deltas_bb100, alpha=alpha)
        played = tv.column("played_hands").to_numpy()
        rt = tv.column("runtime_ms").to_numpy()
        ag = tv.column("agent_ms").to_numpy()
        dec = tv.column("decision_count").to_numpy()
        seat_D = np.array(tv.column("seat_D").to_pylist(), dtype=float)
        entry["diagnostics"] = {
            "played_hands_per_block": float(played.mean()),
            "decisions_per_block": float(dec.mean()),
            "showdown_rate_per_hand": float(tv.column("showdown_hands").to_numpy().sum() / played.sum()),
            "allin_rate_per_hand": float(tv.column("allin_hands").to_numpy().sum() / played.sum()),
            "mean_pot_bb": float(tv.column("pot_bb_sum").to_numpy().sum() / played.sum()),
            "max_pot_bb": float(tv.column("pot_bb_max").to_numpy().max()),
            "seat_D_mean": seat_D.mean(axis=0).tolist(),
            "seat_D_sd": seat_D.std(axis=0, ddof=1).tolist(),
            "seat_D_corr_offdiag_mean": _seat_corr(seat_D),
        }
        mean_rt = float(rt.mean())
        entry["throughput_single_core"] = {
            "mean_block_ms": mean_rt,
            "blocks_per_s": 1000.0 / mean_rt if mean_rt > 0 else None,
            "played_hands_per_s": 1000.0 * float(played.mean()) / mean_rt if mean_rt > 0 else None,
            "decisions_per_s": 1000.0 * float(dec.mean()) / mean_rt if mean_rt > 0 else None,
            "agent_time_share": float(ag.sum() / rt.sum()) if rt.sum() > 0 else None,
            "note": "per-process timings; aggregate throughput ~= this x worker count",
        }
        out[f"{chash}/{pid}"] = entry
    return out


def _seat_corr(seat_D: np.ndarray) -> float | None:
    """Mean pairwise correlation of seat-level D_s (within-block dependence)."""
    if seat_D.shape[0] < 3:
        return None
    with np.errstate(divide="ignore", invalid="ignore"):
        c = np.corrcoef(seat_D, rowvar=False)
    if c.ndim != 2:
        return None
    m = ~np.eye(c.shape[0], dtype=bool)
    v = c[m]
    v = v[np.isfinite(v)]
    return float(v.mean()) if v.size else None


def analyze_paths(paths: list[Path], **kw: Any) -> dict[str, Any]:
    table = read_blocks(paths)
    report = analyze_table(table, **kw)
    nbytes = _dir_bytes(paths)
    report_meta = {"bytes_on_disk": nbytes, "rows": table.num_rows, "bytes_per_block": nbytes / max(table.num_rows, 1)}
    return {"corpus": report_meta, "pairings": report}


def power_sim_paths(
    paths: list[Path], ns: list[int], deltas_bb100: list[float], reps: int, seed: int, alpha: float = 0.05
) -> dict[str, Any]:
    table = read_blocks(paths)
    out: dict[str, Any] = {}
    for key, entry in analyze_table(table, n_boot=0).items():
        chash, pid = key.split("/", 1)
        mask = pc.and_(
            pc.and_(pc.equal(table.column("config_hash"), chash), pc.equal(table.column("pairing_id"), pid)),
            table.column("valid"),
        )
        D = np.asarray(table.filter(mask).column("D").to_numpy(zero_copy_only=False), dtype=float)
        k = int(entry["paired"]["k"]) if "paired" in entry else 0
        if D.size < 2:
            continue
        res = location_shift_power(D, [bb100_to_block(d, k) for d in deltas_bb100], ns, reps, alpha, seed)
        for r in res:
            r["delta_bb100"] = r["delta_block"] * 100.0 / k
            r["played_hands"] = r["n_blocks"] * 2 * k
        out[key] = {"source_blocks": int(D.size), "sd_D": float(D.std(ddof=1)), "results": res}
    return out


def write_ecdf_csv(paths: list[Path], out_dir: Path) -> list[Path]:
    """Histogram/ECDF-ready exports: one CSV per pairing with sorted D."""
    table = read_blocks(paths, columns=["config_hash", "pairing_id", "block_id", "valid", "D"])
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for pid in sorted(set(table.column("pairing_id").to_pylist())):
        t = table.filter(pc.and_(pc.equal(table.column("pairing_id"), pid), table.column("valid")))
        D = np.sort(np.asarray(t.column("D").to_numpy(zero_copy_only=False), dtype=float))
        p = out_dir / f"ecdf_{pid}.csv"
        with p.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["D", "ecdf"])
            n = D.size
            for i, v in enumerate(D):
                w.writerow([repr(float(v)), (i + 1) / n])
        written.append(p)
    return written


def format_report(report: dict[str, Any]) -> str:
    lines = []
    c = report["corpus"]
    lines.append(f"corpus: {c['rows']} rows, {c['bytes_on_disk'] / 1e6:.2f} MB, {c['bytes_per_block']:.0f} B/block")
    for e in report["pairings"].values():
        lines.append("")
        lines.append(f"== {e['pairing_id']}  ({e['variant']} {e['stack_bb']}bb, config {e['config_hash']})")
        lines.append(f"   A = {e['candidate_a']}")
        lines.append(f"   B = {e['candidate_b']}")
        lines.append(f"   ref = {e['reference_population']}   coupling = {e['coupling']}")
        lines.append(f"   blocks: {e['blocks_total']} total, {e['blocks_invalid']} INVALID {e['invalid_error_codes'] or ''}  ids {e['block_id_range']} contiguous={e['block_ids_contiguous']}")
        if "paired" not in e:
            lines.append(f"   {e.get('warning')}")
            continue
        p = e["paired"]
        lines.append(
            f"   mean D = {p['mean_D']:+.4f} BB/block  95% CI [{p['ci_mean'][0]:+.4f}, {p['ci_mean'][1]:+.4f}]"
            f"  = {p['mean_bb100']:+.2f} BB/100 [{p['ci_bb100'][0]:+.2f}, {p['ci_bb100'][1]:+.2f}]"
        )
        lines.append(f"   sigma_D = {p['sd_D']:.4f} BB/block   SE = {p['se_mean']:.4f}   frac D==0: {p['frac_zero']:.3f}")
        if e.get("bootstrap_ci"):
            b = e["bootstrap_ci"]
            lines.append(f"   bootstrap 95%: mean [{b['mean'][0]:+.4f}, {b['mean'][1]:+.4f}]  sd [{b['sd'][0]:.4f}, {b['sd'][1]:.4f}]")
        q = p["quantiles"]
        lines.append(
            f"   tails: skew {p['skew']:+.2f}  ex.kurt {p['excess_kurtosis']:.1f}  q.001 {q['0.001']:+.1f}  q.01 {q['0.01']:+.1f}"
            f"  q.99 {q['0.99']:+.1f}  q.999 {q['0.999']:+.1f}  min {p['min']:+.1f}  max {p['max']:+.1f}"
        )
        lines.append(f"   variance share: top 1% blocks {p['var_share_top1pct']:.2f}, top 0.1% {p['var_share_top0p1pct']:.2f}")
        dg = e["diagnostics"]
        lines.append(
            f"   per hand: showdown {dg['showdown_rate_per_hand']:.3f}  all-in {dg['allin_rate_per_hand']:.4f}  mean pot {dg['mean_pot_bb']:.2f}bb"
            f"  max pot {dg['max_pot_bb']:.0f}bb  decisions/block {dg['decisions_per_block']:.1f}"
        )
        tp = e["throughput_single_core"]
        lines.append(
            f"   throughput/core: {tp['blocks_per_s']:.1f} blocks/s  {tp['played_hands_per_s']:.0f} hands/s  "
            f"{tp['decisions_per_s']:.0f} decisions/s  agent share {tp['agent_time_share']:.2f}"
        )
        if not p["sd_D"] > 0:
            lines.append("   sigma_D = 0: A and B played identically in every block; no power table")
            continue
        lines.append("   required sample (two-sided alpha=0.05, normal approx):")
        lines.append("     Delta BB/100 |     d     | blocks@80%  played hands@80% | blocks@95%  played hands@95%")
        for r in e["power"]:
            lines.append(
                f"     {r['delta_bb100']:>12} | {r['standardized_d']:9.5f} | {r['blocks_power80']:>10,} {r['played_hands_power80']:>17,} |"
                f" {r['blocks_power95']:>10,} {r['played_hands_power95']:>17,}"
            )
    return "\n".join(lines)
