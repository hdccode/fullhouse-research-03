"""Output validation: structural checks + exact replay of a sample of blocks."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pyarrow.compute as pc

from fhr3.configs.experiment import ExperimentConfig
from fhr3.eval.runner import BlockSimulator
from fhr3.io.schema import COMPATIBLE_SCHEMA_VERSIONS, NONDETERMINISTIC_COLUMNS, SCHEMA_VERSION
from fhr3.io.store import pairing_dir, read_blocks, schema_matches
from fhr3.rng import KeyedStream


def rows_equal(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    """Deterministic columns that differ between a fresh row ``a`` and a stored row ``b``.

    Only columns present in both rows are compared. When the stored row comes
    from an older compatible schema, ``schema_version`` itself is skipped: the
    check then proves the current code reproduces every column the old corpus
    recorded (cross-schema replay).
    """
    diffs = []
    cross_schema = a.get("schema_version") != b.get("schema_version") and b.get(
        "schema_version"
    ) in COMPATIBLE_SCHEMA_VERSIONS
    for k in a:
        if k in NONDETERMINISTIC_COLUMNS or k not in b:
            continue
        if cross_schema and k in ("schema_version", "estimator_config_hash"):
            continue
        va, vb = a[k], b.get(k)
        if isinstance(va, float) and isinstance(vb, float) and math.isnan(va) and math.isnan(vb):
            continue
        if va != vb:
            diffs.append(k)
    return diffs


def validate_pairing(
    cfg: ExperimentConfig,
    results_root: Path,
    pairing_id: str,
    expected: tuple[int, int] | None = None,
    replay: int = 10,
) -> dict[str, Any]:
    problems: list[str] = []
    table = read_blocks(pairing_dir(results_root, cfg, pairing_id))  # raises on duplicates
    if not schema_matches(table) and set(table.column("schema_version").to_pylist()) == {SCHEMA_VERSION}:
        problems.append("schema mismatch vs BLOCK_SCHEMA")
    pairing = cfg.pairing(pairing_id)
    for col, want in (
        ("config_hash", cfg.config_hash),
        ("pairing_hash", pairing.pairing_hash),
    ):
        got = set(table.column(col).to_pylist())
        if got != {want}:
            problems.append(f"{col}: expected {want!r}, found {sorted(got)}")
    versions = set(table.column("schema_version").to_pylist())
    notes: list[str] = []
    if not versions <= set(COMPATIBLE_SCHEMA_VERSIONS):
        problems.append(f"unknown schema_version(s): {sorted(versions)}")
    elif versions != {SCHEMA_VERSION}:
        notes.append(f"stored schema {sorted(versions)}; replay compares shared columns (cross-schema)")
    ids = sorted(table.column("block_id").to_pylist())
    if expected is not None:
        missing = sorted(set(range(*expected)) - set(ids))
        if missing:
            problems.append(f"{len(missing)} missing block ids in {expected} (first: {missing[:5]})")
    n_invalid = table.num_rows - pc.sum(table.column("valid")).as_py()
    if n_invalid:
        problems.append(f"{n_invalid} invalid blocks")

    rows = table.to_pylist()
    k = cfg.game.player_count
    for r in rows:
        if not r["valid"]:
            continue
        bad = []
        if len(r["seat_D"]) != k or len(r["seat_payoff_a"]) != k:
            bad.append("seat vector length")
        hands_a, hands_b = r.get("hands_a") or k, r.get("hands_b") or k
        if r["played_hands"] != hands_a + hands_b or (r.get("matched_protocol_version", "").endswith("matched-v1") and r["played_hands"] != 2 * k):
            bad.append("played_hands")
        if abs(sum(r["seat_payoff_a"]) - r["block_payoff_a"]) > 1e-9 or abs(sum(r["seat_payoff_b"]) - r["block_payoff_b"]) > 1e-9:
            bad.append("seat sums")
        if abs((r["block_payoff_a"] - r["block_payoff_b"]) - r["D"]) > 1e-9 or r["raw_estimator_D"] != r["D"]:
            bad.append("D consistency")
        if not math.isfinite(r["D"]):
            bad.append("non-finite D")
        if bad:
            problems.append(f"block {r['block_id']}: {bad}")
            if len(problems) > 50:
                break

    # Exact replay of a deterministic sample of blocks.
    replayed, mismatched = [], []
    if replay and rows:
        pick = KeyedStream("validate-replay", cfg.config_hash, pairing_id).shuffle(range(len(rows)))[:replay]
        sim = BlockSimulator(cfg, pairing)
        for i in sorted(pick):
            stored = rows[i]
            fresh = sim.row(sim.run(stored["block_id"]), stored["run_id"], stored["traced"])
            diff = rows_equal(fresh, stored)
            replayed.append(stored["block_id"])
            if diff:
                mismatched.append({"block_id": stored["block_id"], "columns": diff})
        if mismatched:
            problems.append(f"replay mismatch in {len(mismatched)} blocks: {mismatched[:3]}")
    return {
        "pairing_id": pairing_id,
        "rows": table.num_rows,
        "invalid": n_invalid,
        "replayed_blocks": replayed,
        "ok": not problems,
        "problems": problems,
        "notes": notes,
    }
