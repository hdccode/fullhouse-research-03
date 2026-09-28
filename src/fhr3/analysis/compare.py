"""Cross-configuration comparison (formats, stack depths, player counts).

Built on ``analyze_table`` so every figure matches ``fhr3 analyze``. Reports,
per (experiment, pairing): hands/block, sigma_D, mean D, zeros, skew, kurtosis,
key quantiles, variance concentration, all-in/showdown rates, pots, required
blocks/hands for target BB/100 effects, BB/100 at fixed standardized d,
throughput and storage.

Relations between two configs (computed on common block ids):

  paired                       same variant, same deal layout, same block seeds:
                               identical cards and rules family; D values are
                               paired observations (e.g. a stack-depth series)
  shared cards, different game same deal layout and seeds, different variant
                               (e.g. NLHE vs bomb pot): not a paired design
  shared seed material only    same seeds, but a different deal layout or block
                               protocol (e.g. 4-max vs 6-max, NLHE vs PLO, NLHE vs
                               Nit Game whose hands use per-hand chance keys)
  independent                  different seeds

The observed correlation of D is reported in every case. Sharing a root seed is
never, by itself, reported as pairing.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from fhr3.analysis.report import analyze_table, storage_by_pairing
from fhr3.analysis.stats import DEFAULT_DELTAS_BB100, bb100_to_block, required_blocks
from fhr3.io.store import read_blocks

FIXED_D = (0.005, 0.01, 0.02)


def relation(a: dict[str, Any], b: dict[str, Any], same_seeds: bool) -> str:
    if not same_seeds:
        return "independent"
    if a["deal_layout"] != b["deal_layout"] or a["protocol"] != b["protocol"]:
        return "shared seed material only"
    if a["variant"] != b["variant"]:
        return "shared cards, different game"
    return "paired"


def _series(table: pa.Table, chash: str, pid: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    m = pc.and_(pc.and_(pc.equal(table.column("config_hash"), chash), pc.equal(table.column("pairing_id"), pid)), table.column("valid"))
    t = table.filter(m)
    return (t.column("block_id").to_numpy(), t.column("seed").to_numpy(),
            np.asarray(t.column("D").to_numpy(zero_copy_only=False), dtype=float))


def summarize_entry(e: dict[str, Any], deltas: tuple[float, ...], power: float, alpha: float) -> dict[str, Any]:
    p, dg, tp = e["paired"], e["diagnostics"], e["throughput_single_core"]
    k, sd = e["candidate_hands_per_side"], p["sd_D"]
    row: dict[str, Any] = {
        "experiment_id": e["experiment_id"],
        "pairing_id": e["pairing_id"],
        # p1/p2/p3/c0: pairings are aligned across formats by role, not by id
        # (ids differ where a format needs a different perturbation)
        "role": e["pairing_id"].split("-", 1)[0],
        "variant": e["variant"],
        "player_count": e["player_count"],
        "stack_bb": e["stack_bb"],
        "label": f"{e['variant']}/{e['player_count']}max/{e['stack_bb']:g}bb",
        "deal_layout": e["deal_layout"],
        "protocol": e["protocol"],
        "n_blocks": p["n_blocks"],
        "hands_per_block": dg["played_hands_per_block"],
        "candidate_hands_per_side": k,
        "mean_D": p["mean_D"],
        "mean_bb100": p["mean_bb100"],
        "sd_D": sd,
        "frac_zero": p["frac_zero"],
        "skew": p["skew"],
        "excess_kurtosis": p["excess_kurtosis"],
        "q001": p["quantiles"]["0.001"], "q01": p["quantiles"]["0.01"],
        "q99": p["quantiles"]["0.99"], "q999": p["quantiles"]["0.999"],
        "concentration": p["concentration"],
        "allin_rate_per_hand": dg["allin_rate_per_hand"],
        "showdown_rate_per_hand": dg["showdown_rate_per_hand"],
        "mean_pot_bb": dg["mean_pot_bb"],
        "max_pot_bb": dg["max_pot_bb"],
        "blocks_per_s_core": tp["blocks_per_s"],
        "hands_per_s_core": tp["played_hands_per_s"],
        "storage_bytes_per_block": e.get("storage_bytes_per_block"),
        "targets": {},
        "bb100_at_fixed_d": {str(fd): 100.0 * fd * sd / k for fd in FIXED_D} if sd > 0 else None,
    }
    for dl in deltas:
        n = required_blocks(sd, bb100_to_block(dl, k), alpha, power)
        row["targets"][f"{dl:g}"] = (
            {"blocks": math.ceil(n), "played_hands": round(math.ceil(n) * row["hands_per_block"])} if math.isfinite(n) else None
        )
    return row


def compare_paths(
    paths: list[Path],
    deltas_bb100: tuple[float, ...] = DEFAULT_DELTAS_BB100,
    power: float = 0.8,
    alpha: float = 0.05,
) -> dict[str, Any]:
    table = pa.concat_tables([read_blocks(p) for p in paths], promote_options="default")
    entries = [e for e in analyze_table(table, n_boot=0, deltas_bb100=deltas_bb100, alpha=alpha).values() if "paired" in e]
    per: dict[tuple[str, str], float] = {}
    for p in paths:
        per |= storage_by_pairing([p])
    for e in entries:
        e["storage_bytes_per_block"] = per.get((e["config_hash"], e["pairing_id"]))
    rows = sorted((summarize_entry(e, deltas_bb100, power, alpha) | {"config_hash": e["config_hash"]} for e in entries),
                  key=lambda r: (r["pairing_id"], r["variant"], r["player_count"], r["stack_bb"]))
    by_pid: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_pid.setdefault(r["pairing_id"], []).append(r)
    relations = []
    for pid, group in by_pid.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                ba, sa, Da = _series(table, a["config_hash"], pid)
                bb, sb, Db = _series(table, b["config_hash"], pid)
                common, ia, ib = np.intersect1d(ba, bb, return_indices=True)
                if common.size < 3:
                    continue
                same_seeds = bool(np.all(sa[ia] == sb[ib]))
                with np.errstate(divide="ignore", invalid="ignore"):
                    r = float(np.corrcoef(Da[ia], Db[ib])[0, 1])
                relations.append({
                    "pairing_id": pid, "a": a["label"], "b": b["label"],
                    "a_experiment": a["experiment_id"], "b_experiment": b["experiment_id"],
                    "common_blocks": int(common.size), "relation": relation(a, b, same_seeds),
                    "corr_D": r if math.isfinite(r) else None,
                })
    blocks_at_d = {str(fd): math.ceil(required_blocks(1.0, fd, alpha, power)) for fd in FIXED_D}
    return {"deltas_bb100": list(deltas_bb100), "power": power, "alpha": alpha, "rows": rows,
            "relations": relations, "blocks_at_fixed_d": blocks_at_d}


def _fmt(v: Any, spec: str) -> str:
    return f"{v:{spec}}" if v is not None and v == v else "n/a"


def format_compare(rep: dict[str, Any]) -> str:
    lines = [f"required samples at {rep['power']:.0%} power, two-sided alpha {rep['alpha']} (normal approx); "
             f"blocks at fixed d (every config): " + ", ".join(f"d={k}: {v:,}" for k, v in rep["blocks_at_fixed_d"].items())]
    cur = None
    for r in rep["rows"]:
        if r["pairing_id"] != cur:
            cur = r["pairing_id"]
            lines += ["", f"== {cur}",
                      f"   {'config':<26} {'blocks':>7} {'h/blk':>6} {'BB/100':>7} {'sigma_D':>8} {'D=0':>5} {'skew':>6} {'exkurt':>7}"
                      f" {'top1%':>6} {'top.1%':>6} {'allin/h':>7} {'sd/h':>6} {'pot':>6} {'blk/s':>6} {'B/blk':>6}"]
        c = r["concentration"]
        lines.append(
            f"   {r['label']:<26} {r['n_blocks']:>7} {r['hands_per_block']:>6.1f} {r['mean_bb100']:>+7.2f} {r['sd_D']:>8.3f}"
            f" {r['frac_zero']:>5.2f} {_fmt(r['skew'], '+6.2f'):>6} {_fmt(r['excess_kurtosis'], '7.1f'):>7}"
            f" {_fmt(c.get('0.01'), '6.2f'):>6} {_fmt(c.get('0.001'), '6.2f'):>6} {r['allin_rate_per_hand']:>7.4f}"
            f" {r['showdown_rate_per_hand']:>6.3f} {r['mean_pot_bb']:>6.1f} {_fmt(r['blocks_per_s_core'], '6.1f'):>6}"
            f" {_fmt(r['storage_bytes_per_block'], '6.0f'):>6}"
        )
        if r["sd_D"] > 0:
            tg = "  ".join(
                f"{d}: {t['blocks']:,} blk / {t['played_hands']:,} h" if t else f"{d}: n/a" for d, t in r["targets"].items()
            )
            lines.append(f"      targets (BB/100 -> blocks / played hands): {tg}")
            lines.append("      BB/100 at fixed d " + ", ".join(f"{k}: {v:.2f}" for k, v in r["bb100_at_fixed_d"].items()))
        else:
            lines.append("      sigma_D = 0 (identical play)")
    if rep["relations"]:
        lines += ["", "relations between configs (same pairing id, common block ids; controls omitted):"]
        for x in rep["relations"]:
            if x["pairing_id"].startswith("c0-"):
                continue
            val = f"{x['corr_D']:+.3f}" if x["corr_D"] is not None else "n/a"
            lines.append(f"   {x['pairing_id']}: {x['a']} vs {x['b']}: {x['relation']}; corr(D) {val} on {x['common_blocks']} blocks")
    return "\n".join(lines)
