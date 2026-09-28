"""Corpus-level analysis report (consumes Parquet only; never re-runs poker).

The statistical unit is the block. Hand counts are used only to translate
effects between BB/100 and the block scale:

    k_eff = mean over blocks of (hands_a + hands_b) / 2      (candidate hands per side)

which equals the player count for single-hand protocols. For the Nit Game
(variable round length) BB/100 figures use this mean and are therefore a ratio
approximation; the block-level quantities are exact.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from fhr3.analysis.stats import (
    DEFAULT_DELTAS_BB100,
    bb100_to_block,
    bootstrap_ci,
    describe,
    location_shift_power,
    power_table,
)
from fhr3.io.store import read_blocks

ESTIMATOR_COLUMNS = ("allin_ev_D", "mivat_D", "aivat_D")


def _single(table: pa.Table, col: str) -> Any:
    vals = pc.unique(table.column(col)).to_pylist()
    if len(vals) != 1:
        raise ValueError(f"column {col!r} is not constant within a pairing: {vals[:5]}")
    return vals[0]


def _col(table: pa.Table, name: str) -> np.ndarray | None:
    if name not in table.column_names:
        return None
    arr = table.column(name).to_numpy(zero_copy_only=False)
    if arr.dtype == object and all(v is None for v in arr):
        return None
    return np.asarray(arr, dtype=float)


def _files(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for p in map(Path, paths):
        out += [p] if p.is_file() else sorted(p.rglob("blocks_*.parquet"))
    return out


def k_effective(t: pa.Table) -> float:
    ha, hb = _col(t, "hands_a"), _col(t, "hands_b")
    if ha is not None and hb is not None and not np.isnan(ha).any() and not np.isnan(hb).any():
        return float(np.mean((ha + hb) / 2.0))
    return float(_single(t, "player_count"))


def deal_layout(t: pa.Table) -> str:
    """Stored layout (v2) or the layout v1 rows implied (v1 was NLHE only)."""
    if "deal_layout" in t.column_names:
        vals = [v for v in pc.unique(t.column("deal_layout")).to_pylist() if v]
        if len(vals) == 1:
            return vals[0]
    return f"board-h2-k{_single(t, 'player_count')}"


def estimator_comparison(t: pa.Table, D: np.ndarray, k: float) -> dict[str, Any]:
    """Same-estimand check and variance reduction for every populated estimator."""
    out: dict[str, Any] = {}
    for name in ESTIMATOR_COLUMNS:
        E = _col(t, name)
        if E is None or np.isnan(E).any():
            continue
        diff = E - D
        n = D.size
        se_diff = float(diff.std(ddof=1) / np.sqrt(n)) if n > 1 else float("nan")
        sd_e, sd_d = float(E.std(ddof=1)), float(D.std(ddof=1))
        out[name] = {
            "mean": float(E.mean()),
            "mean_bb100": 100.0 * float(E.mean()) / k,
            "sd": sd_e,
            "variance_ratio_vs_raw": (sd_e / sd_d) ** 2 if sd_d > 0 else None,
            "corr_with_raw": float(np.corrcoef(E, D)[0, 1]) if sd_e > 0 and sd_d > 0 else None,
            # E[est - raw] must be 0 (same estimand); z is a diagnostic, not a proof
            "mean_diff_vs_raw": float(diff.mean()),
            "mean_diff_z": float(diff.mean() / se_diff) if se_diff and se_diff > 0 else None,
        }
    return out


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
        valid_mask = t.column("valid")
        tv = t.filter(valid_mask)
        n_invalid = t.num_rows - tv.num_rows
        D = np.asarray(tv.column("D").to_numpy(zero_copy_only=False), dtype=float)
        block_ids = np.sort(t.column("block_id").to_numpy())
        k = k_effective(tv) if tv.num_rows else float(_single(t, "player_count"))
        entry: dict[str, Any] = {
            "config_hash": chash,
            "experiment_id": _single(t, "experiment_id"),
            "pairing_id": pid,
            "variant": _single(t, "variant"),
            "player_count": int(_single(t, "player_count")),
            "stack_bb": _single(t, "stack_bb"),
            "deal_layout": deal_layout(t),
            "protocol": _single(t, "matched_protocol_version"),
            "candidate_hands_per_side": k,
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
        entry["estimators"] = estimator_comparison(tv, D, k)
        played = tv.column("played_hands").to_numpy()
        rt = tv.column("runtime_ms").to_numpy()
        ag = tv.column("agent_ms").to_numpy()
        es = _col(tv, "estimator_ms")
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
            "estimator_time_share": float(np.nansum(es) / rt.sum()) if es is not None and rt.sum() > 0 else None,
            "note": "per-process timings; aggregate throughput ~= this x worker count",
        }
        out[f"{chash}/{pid}"] = entry
    return out


def _seat_corr(seat_D: np.ndarray) -> float | None:
    """Mean pairwise correlation of seat-level D_s (within-block dependence)."""
    if seat_D.ndim != 2 or seat_D.shape[0] < 3:
        return None
    with np.errstate(divide="ignore", invalid="ignore"):
        c = np.corrcoef(seat_D, rowvar=False)
    if c.ndim != 2:
        return None
    m = ~np.eye(c.shape[0], dtype=bool)
    v = c[m]
    v = v[np.isfinite(v)]
    return float(v.mean()) if v.size else None


def storage_by_pairing(paths: list[Path]) -> dict[tuple[str, str], float]:
    """Bytes on disk per block, per (config_hash, pairing_id)."""
    sizes: dict[tuple[str, str], list[int]] = {}
    for f in _files(paths):
        t = pq.read_table(f, columns=["config_hash", "pairing_id"])
        if t.num_rows == 0:
            continue
        key = (t.column("config_hash")[0].as_py(), t.column("pairing_id")[0].as_py())
        acc = sizes.setdefault(key, [0, 0])
        acc[0] += f.stat().st_size
        acc[1] += t.num_rows
    return {k: v[0] / v[1] for k, v in sizes.items() if v[1]}


def analyze_paths(paths: list[Path], **kw: Any) -> dict[str, Any]:
    table = read_blocks(paths)
    report = analyze_table(table, **kw)
    per = storage_by_pairing(paths)
    for e in report.values():
        e["storage_bytes_per_block"] = per.get((e["config_hash"], e["pairing_id"]))
    nbytes = sum(f.stat().st_size for f in _files(paths))
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
        k = entry["candidate_hands_per_side"]
        if D.size < 2:
            continue
        res = location_shift_power(D, [bb100_to_block(d, k) for d in deltas_bb100], ns, reps, alpha, seed)
        for r in res:
            r["delta_bb100"] = r["delta_block"] * 100.0 / k
            r["played_hands"] = round(r["n_blocks"] * 2 * k)
        out[key] = {
            "pairing_id": pid,
            "experiment_id": entry["experiment_id"],
            "source_blocks": int(D.size),
            "sd_D": float(D.std(ddof=1)),
            "results": res,
        }
    return out


def write_ecdf_csv(paths: list[Path], out_dir: Path) -> list[Path]:
    """Histogram/ECDF-ready exports: one CSV per (experiment, pairing) with sorted D."""
    table = read_blocks(paths, columns=["experiment_id", "config_hash", "pairing_id", "block_id", "valid", "D"])
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    keys = sorted(set(zip(table.column("experiment_id").to_pylist(), table.column("pairing_id").to_pylist(), strict=True)))
    for exp, pid in keys:
        m = pc.and_(pc.and_(pc.equal(table.column("experiment_id"), exp), pc.equal(table.column("pairing_id"), pid)), table.column("valid"))
        D = np.sort(np.asarray(table.filter(m).column("D").to_numpy(zero_copy_only=False), dtype=float))
        p = out_dir / f"ecdf_{exp}_{pid}.csv"
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
        lines.append(
            f"== {e['pairing_id']}  ({e['variant']} {e['player_count']}-max {e['stack_bb']}bb, {e['protocol']}, "
            f"config {e['config_hash']}, experiment {e['experiment_id']})"
        )
        lines.append(f"   A = {e['candidate_a']}")
        lines.append(f"   B = {e['candidate_b']}")
        lines.append(f"   ref = {e['reference_population']}   coupling = {e['coupling']}")
        lines.append(f"   blocks: {e['blocks_total']} total, {e['blocks_invalid']} INVALID {e['invalid_error_codes'] or ''}  ids {e['block_id_range']} contiguous={e['block_ids_contiguous']}")
        if "paired" not in e:
            lines.append(f"   {e.get('warning')}")
            continue
        p, k = e["paired"], e["candidate_hands_per_side"]
        approx = "" if float(k).is_integer() else " (BB/100 via mean hands/side: ratio approximation)"
        if e["protocol"].startswith("fhr3-nit"):
            approx += " [Nit: D and BB/100 include nit-penalty transfers]"
        lines.append(f"   candidate hands per side per block: {k:.2f}{approx}; played hands/block {e['diagnostics']['played_hands_per_block']:.1f}")
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
        conc = "  ".join(f"top {float(f) * 100:g}%: {v:.2f}" for f, v in p["concentration"].items() if v is not None)
        lines.append(f"   variance concentration (share of squared deviation): {conc}")
        dg = e["diagnostics"]
        lines.append(
            f"   per hand: showdown {dg['showdown_rate_per_hand']:.3f}  all-in {dg['allin_rate_per_hand']:.4f}  mean pot {dg['mean_pot_bb']:.2f}bb"
            f"  max pot {dg['max_pot_bb']:.0f}bb  decisions/block {dg['decisions_per_block']:.1f}"
        )
        tp = e["throughput_single_core"]
        est_share = f"  estimator share {tp['estimator_time_share']:.2f}" if tp.get("estimator_time_share") else ""
        lines.append(
            f"   throughput/core: {tp['blocks_per_s']:.1f} blocks/s  {tp['played_hands_per_s']:.0f} hands/s  "
            f"{tp['decisions_per_s']:.0f} decisions/s  agent share {tp['agent_time_share']:.2f}{est_share}"
            + (f"   storage {e['storage_bytes_per_block']:.0f} B/block" if e.get("storage_bytes_per_block") else "")
        )
        for name, es in e.get("estimators", {}).items():
            vr = f"{es['variance_ratio_vs_raw']:.3f}" if es["variance_ratio_vs_raw"] is not None else "n/a"
            z = f"{es['mean_diff_z']:+.2f}" if es["mean_diff_z"] is not None else "n/a"
            lines.append(f"   estimator {name}: mean {es['mean']:+.4f}  sd {es['sd']:.4f}  var ratio vs raw {vr}  mean(est-raw) z {z}")
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
