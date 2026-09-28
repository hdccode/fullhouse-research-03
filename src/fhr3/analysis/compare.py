"""Cross-configuration comparison (stack sensitivity, 4-max vs 6-max).

For each pairing id present in several configurations, reports paired variance,
tails, all-in frequency, pot size and sample complexity side by side, both at a
fixed effect in BB/100 and at a fixed standardized effect d = Delta_block/sigma_D.

At fixed d the required number of blocks is the same for every config by
definition; what differs is the BB/100 gap that d corresponds to. Both views are
reported because they answer different questions.

Configs sharing a root seed use identical decks per block id (verified here via
the ``seed`` column), so their D sequences are *paired*; the cross-config
correlation of D on common block ids is reported for that reason.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from fhr3.analysis.stats import bb100_to_block, describe, required_blocks
from fhr3.io.store import read_blocks

FIXED_D = (0.005, 0.01, 0.02)


def _pairing_rows(table: pa.Table, chash: str, pid: str) -> pa.Table:
    mask = pc.and_(pc.equal(table.column("config_hash"), chash), pc.equal(table.column("pairing_id"), pid))
    return table.filter(pc.and_(mask, table.column("valid")))


def compare_paths(
    paths: list[Path], delta_bb100: float = 1.0, power: float = 0.8, alpha: float = 0.05
) -> dict[str, Any]:
    table = pa.concat_tables([read_blocks(p) for p in paths], promote_options="default")
    keys = sorted(set(zip(table.column("pairing_id").to_pylist(), table.column("config_hash").to_pylist(), strict=True)))
    out: dict[str, Any] = {}
    for pid in sorted({k[0] for k in keys}):
        entries = []
        series: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        for _, chash in (k for k in keys if k[0] == pid):
            t = _pairing_rows(table, chash, pid)
            if t.num_rows < 2:
                continue
            k = int(t.column("player_count")[0].as_py())
            D = np.asarray(t.column("D").to_numpy(zero_copy_only=False), dtype=float)
            d = describe(D, k, alpha)
            played = t.column("played_hands").to_numpy().sum()
            sd = d["sd_D"]
            n_fixed = required_blocks(sd, bb100_to_block(delta_bb100, k), alpha, power)
            e = {
                "config_hash": chash,
                "experiment_id": t.column("experiment_id")[0].as_py(),
                "player_count": k,
                "stack_bb": t.column("stack_bb")[0].as_py(),
                "n_blocks": int(D.size),
                "mean_bb100": d["mean_bb100"],
                "ci_bb100": d["ci_bb100"],
                "sd_D": sd,
                "frac_zero": d["frac_zero"],
                "excess_kurtosis": d["excess_kurtosis"],
                "var_share_top1pct": d["var_share_top1pct"],
                "allin_rate_per_hand": float(t.column("allin_hands").to_numpy().sum() / played),
                "showdown_rate_per_hand": float(t.column("showdown_hands").to_numpy().sum() / played),
                "mean_pot_bb": float(t.column("pot_bb_sum").to_numpy().sum() / played),
                f"blocks_for_{delta_bb100:g}bb100": math.ceil(n_fixed) if math.isfinite(n_fixed) else None,
                f"played_hands_for_{delta_bb100:g}bb100": math.ceil(n_fixed) * 2 * k if math.isfinite(n_fixed) else None,
                "bb100_at_fixed_d": {str(fd): 100.0 * fd * sd / k for fd in FIXED_D},
            }
            entries.append(e)
            e["label"] = f"{k}max/{e['stack_bb']:g}bb"
            series[chash] = (
                t.column("block_id").to_numpy(),
                t.column("seed").to_numpy(),
                D,
            )
        corr = []
        entries.sort(key=lambda e: (e["player_count"], e["stack_bb"]))
        hashes = [e["config_hash"] for e in entries]
        info = {e["config_hash"]: e for e in entries}
        for i in range(len(hashes)):
            for j in range(i + 1, len(hashes)):
                bi, si, Di = series[hashes[i]]
                bj, sj, Dj = series[hashes[j]]
                common, ii, jj = np.intersect1d(bi, bj, return_indices=True)
                if common.size < 3:
                    continue
                same_seeds = bool(np.all(si[ii] == sj[jj]))
                # Same seed => same shuffled deck, but the deal layout depends on
                # player count, so only equal-k configs share hole cards and boards.
                same_k = info[hashes[i]]["player_count"] == info[hashes[j]]["player_count"]
                pairing_kind = ("same deals" if same_k else "same seeds, different deal layout") if same_seeds else "unpaired"
                with np.errstate(divide="ignore", invalid="ignore"):
                    r = float(np.corrcoef(Di[ii], Dj[jj])[0, 1])
                corr.append({"a": info[hashes[i]]["label"], "b": info[hashes[j]]["label"],
                             "a_hash": hashes[i], "b_hash": hashes[j], "common_blocks": int(common.size),
                             "pairing": pairing_kind, "corr_D": r if math.isfinite(r) else None})
        n_fixed_d = {str(fd): math.ceil(required_blocks(1.0, fd, alpha, power)) for fd in FIXED_D}
        out[pid] = {"configs": entries,
                    "cross_config_correlation": corr, "blocks_at_fixed_d": n_fixed_d}
    return {"delta_bb100": delta_bb100, "power": power, "alpha": alpha, "pairings": out}


def format_compare(rep: dict[str, Any]) -> str:
    dl = f"{rep['delta_bb100']:g}"
    lines = [f"fixed effect: {dl} BB/100 at {rep['power']:.0%} power, two-sided alpha {rep['alpha']}"]
    for pid, e in rep["pairings"].items():
        lines += ["", f"== {pid}"]
        lines.append("   configs: " + ", ".join(f"{c['label']}={c['experiment_id']}" for c in e["configs"]))
        lines.append(
            f"   {'k':>2} {'stack':>6} {'blocks':>7} {'BB/100':>8} {'sigma_D':>8} {'D=0':>5} {'exkurt':>7} {'top1%':>6}"
            f" {'allin/h':>8} {'pot':>6} {'blocks@' + dl:>12} {'hands@' + dl:>13}  BB/100 at d=" + ",".join(e["blocks_at_fixed_d"])
        )
        for c in e["configs"]:
            nb = c[f"blocks_for_{dl}bb100"]
            nh = c[f"played_hands_for_{dl}bb100"]
            fd = ", ".join(f"{v:.2f}" for v in c["bb100_at_fixed_d"].values())
            if nb is None:
                lines.append(f"   {c['player_count']:>2} {c['stack_bb']:>6g} {c['n_blocks']:>7}   sigma_D = 0 (identical play)")
                continue
            lines.append(
                f"   {c['player_count']:>2} {c['stack_bb']:>6g} {c['n_blocks']:>7} {c['mean_bb100']:>+8.2f} {c['sd_D']:>8.3f}"
                f" {c['frac_zero']:>5.2f} {c['excess_kurtosis']:>7.1f} {c['var_share_top1pct']:>6.2f} {c['allin_rate_per_hand']:>8.4f}"
                f" {c['mean_pot_bb']:>6.2f} {nb:>12,} {nh:>13,}  {fd}"
            )
        lines.append("   blocks needed at fixed d (all configs): " + ", ".join(f"d={k}: {v:,}" for k, v in e["blocks_at_fixed_d"].items()))
        for r in e["cross_config_correlation"]:
            val = f"{r['corr_D']:+.3f}" if r["corr_D"] is not None else "n/a"
            lines.append(f"   corr(D) {r['a']} vs {r['b']}: {val} on {r['common_blocks']} common blocks ({r['pairing']})")
    return "\n".join(lines)
