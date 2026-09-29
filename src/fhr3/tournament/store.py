"""On-disk layout for FHR3B tournament cells (chunked per tournament, resumable).

    <root>/<cell_id>/
        cell.lock.json                   identity, identity hash, full cell definition,
                                         engine source hash (immutable)
        runs/<run_id>.json               one manifest per invocation (timing, workers)
        tournaments/t<rep:06d>/
            tables.parquet               one row per (round, table, seat)
            final.parquet                one row per bot
            manifest.json                commit marker: seeds, hashes, ranking, digest

``manifest.json`` is written last (atomically), so a tournament directory without it
is incomplete and is recomputed. A completed tournament is *verified* on resume by
recomputing its digest from the Parquet rows.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from fhr3.tournament.cells import Cell
from fhr3.tournament.manifests import engine_source_hash
from fhr3.tournament.runner import FINAL_COLUMNS, TABLE_COLUMNS, TournamentResult, rows_digest

STORE_VERSION = "fhr3b-store-v1"
TABLE_SCHEMA = pa.schema([
    ("tournament_id", pa.string()), ("replicate", pa.int32()), ("round", pa.int16()),
    ("table_index", pa.int16()), ("seat", pa.int8()), ("table_size", pa.int8()), ("bot_id", pa.string()),
    ("pre_score", pa.int64()), ("pre_rank", pa.int16()), ("match_seed", pa.int64()), ("chip_delta", pa.int64()),
    ("hands_played", pa.int32()), ("bust_hand", pa.int32()), ("post_score", pa.int64()), ("post_rank", pa.int16()),
    ("post_best_match_delta", pa.int64()),
])
FINAL_SCHEMA = pa.schema([
    ("tournament_id", pa.string()), ("replicate", pa.int32()), ("bot_id", pa.string()),
    ("final_score", pa.int64()), ("final_rank", pa.int16()), ("qualified", pa.bool_()),
    ("matches_played", pa.int16()), ("best_match_delta", pa.int64()), ("dense_rank", pa.int16()),
])
assert tuple(TABLE_SCHEMA.names) == TABLE_COLUMNS and tuple(FINAL_SCHEMA.names) == FINAL_COLUMNS


class IncompatibleCellError(RuntimeError):
    pass


def cell_dir(root: Path, cell: Cell) -> Path:
    return Path(root) / cell.cell_id


def tournament_dir(root: Path, cell: Cell, replicate: int) -> Path:
    return cell_dir(root, cell) / "tournaments" / f"t{replicate:06d}"


def write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n")
    os.replace(tmp, path)


def _write_parquet_atomic(path: Path, table: pa.Table) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".parquet.tmp{os.getpid()}")
    pq.write_table(table, tmp, compression="zstd")
    os.replace(tmp, path)


def lock_payload(cell: Cell) -> dict[str, Any]:
    return {
        "store_version": STORE_VERSION,
        "cell_id": cell.cell_id,
        "identity_hash": cell.identity_hash,
        "identity": cell.identity,
        "cell": cell.to_dict(),
        "engine_source_hash": engine_source_hash(),
    }


def ensure_lock(root: Path, cell: Cell, allow_source_change: bool = False) -> dict[str, Any]:
    path = cell_dir(root, cell) / "cell.lock.json"
    want = json.loads(json.dumps(lock_payload(cell), default=str))
    if not path.exists():
        write_json_atomic(path, want)
        return want
    have = json.loads(path.read_text())
    if have["identity_hash"] != want["identity_hash"] or have["identity"] != want["identity"]:
        raise IncompatibleCellError(f"{path}: cell identity differs; refusing to mix results")
    if have["engine_source_hash"] != want["engine_source_hash"] and not allow_source_change:
        raise IncompatibleCellError(
            f"{path}: result-relevant source changed ({have['engine_source_hash']} -> "
            f"{want['engine_source_hash']}). Re-run with --allow-source-change only if the change "
            "cannot alter results (validate --replay then checks that old tournaments replay exactly)."
        )
    return have


def write_tournament(root: Path, cell: Cell, res: TournamentResult) -> dict[str, Any]:
    d = tournament_dir(root, cell, res.spec.replicate)
    t_tab = pa.Table.from_pylist(res.table_rows, schema=TABLE_SCHEMA)
    f_tab = pa.Table.from_pylist(res.final_rows, schema=FINAL_SCHEMA)
    _write_parquet_atomic(d / "tables.parquet", t_tab)
    _write_parquet_atomic(d / "final.parquet", f_tab)
    man = res.manifest() | {"identity_hash": cell.identity_hash, "store_version": STORE_VERSION}
    write_json_atomic(d / "manifest.json", man)
    return man


def read_tournament_rows(root: Path, cell: Cell, replicate: int) -> tuple[list[dict], list[dict], dict]:
    d = tournament_dir(root, cell, replicate)
    tables = pq.read_table(d / "tables.parquet").to_pylist()
    final = pq.read_table(d / "final.parquet").to_pylist()
    man = json.loads((d / "manifest.json").read_text())
    return tables, final, man


def verified_complete(root: Path, cell: Cell, replicate: int) -> bool:
    d = tournament_dir(root, cell, replicate)
    if not (d / "manifest.json").exists():
        return False
    try:
        tables, final, man = read_tournament_rows(root, cell, replicate)
    except Exception:
        return False
    return man.get("identity_hash") == cell.identity_hash and rows_digest(tables, final) == man["digest"]


def completed_replicates(root: Path, cell: Cell, verify: bool = True) -> list[int]:
    base = cell_dir(root, cell) / "tournaments"
    if not base.exists():
        return []
    reps = sorted(int(p.name[1:]) for p in base.iterdir() if p.name.startswith("t") and (p / "manifest.json").exists())
    return [r for r in reps if verified_complete(root, cell, r)] if verify else reps


# ------------------------------------------------------------------ analysis loading
def load_cell_arrays(root: Path, cell: Cell, replicates: Iterable[int] | None = None,
                     with_rounds: bool = False) -> dict[str, Any]:
    """Arrays over completed tournaments (bots in sorted id order).

    ``final_rank`` / ``final_score`` / ``qualified``: (M, N). With ``with_rounds``,
    ``round_rank`` / ``round_score``: (M, R, N) standings after each round (the
    R-prefix leaderboards used by the round sweep).
    """
    reps = list(replicates) if replicates is not None else completed_replicates(root, cell, verify=False)
    bots = sorted(cell.field.bot_ids)
    col = {b: i for i, b in enumerate(bots)}
    m, n, r = len(reps), len(bots), cell.protocol.rounds
    rank = np.zeros((m, n), dtype=np.int32)
    score = np.zeros((m, n), dtype=np.int64)
    rrank = np.zeros((m, r, n), dtype=np.int32) if with_rounds else None
    rscore = np.zeros((m, r, n), dtype=np.int64) if with_rounds else None
    for i, rep in enumerate(reps):
        d = tournament_dir(root, cell, rep)
        f = pq.read_table(d / "final.parquet", columns=["bot_id", "final_rank", "final_score"]).to_pydict()
        for b, rk, sc in zip(f["bot_id"], f["final_rank"], f["final_score"], strict=True):
            rank[i, col[b]] = rk
            score[i, col[b]] = sc
        if with_rounds:
            t = pq.read_table(d / "tables.parquet", columns=["round", "bot_id", "post_rank", "post_score"]).to_pydict()
            for rd, b, rk, sc in zip(t["round"], t["bot_id"], t["post_rank"], t["post_score"], strict=True):
                rrank[i, rd - 1, col[b]] = rk
                rscore[i, rd - 1, col[b]] = sc
    k = cell.protocol.qualify_top_k
    return {"replicates": reps, "bots": bots, "final_rank": rank, "final_score": score,
            "qualified": rank <= k, "round_rank": rrank, "round_score": rscore, "K": k}
