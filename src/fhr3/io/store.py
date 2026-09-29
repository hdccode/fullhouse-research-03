"""On-disk layout, compatibility locks and chunked Parquet I/O.

    <results_root>/<experiment_id>/
        experiment.lock.json            environment + config_hash (immutable)
        runs/<run_id>.json              one RunManifest per CLI invocation
        <pairing_id>/pairing.lock.json  resolved pairing + pairing_hash (immutable)
        <pairing_id>/blocks/blocks_<start>_<end>.parquet   half-open [start, end)

A lock that disagrees with the current config aborts the run: results are never
silently overwritten or mixed with incompatible ones. Chunk files are written
atomically (temp file + rename), so an interrupted run leaves no partial chunk
and ``--resume`` semantics are simply "skip chunks whose file exists".
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from fhr3.configs.experiment import ExperimentConfig, Pairing
from fhr3.eval.matched import MATCHED_PROTOCOL_VERSION
from fhr3.io.schema import BLOCK_SCHEMA, SCHEMA_VERSION

CHUNK_RE = re.compile(r"blocks_(\d{9})_(\d{9})\.parquet$")


class IncompatibleResultsError(RuntimeError):
    pass


def experiment_dir(root: Path, cfg: ExperimentConfig) -> Path:
    return Path(root) / cfg.experiment_id


def pairing_dir(root: Path, cfg: ExperimentConfig, pairing_id: str) -> Path:
    return experiment_dir(root, cfg) / pairing_id


def chunk_path(root: Path, cfg: ExperimentConfig, pairing_id: str, start: int, end: int) -> Path:
    return pairing_dir(root, cfg, pairing_id) / "blocks" / f"blocks_{start:09d}_{end:09d}.parquet"


def _write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str))
    os.replace(tmp, path)


def _check_or_create_lock(path: Path, expected: dict[str, Any], what: str) -> None:
    if path.exists():
        existing = json.loads(path.read_text())
        if existing != json.loads(json.dumps(expected, default=str)):
            diff = sorted(
                k for k in set(existing) | set(expected) if existing.get(k) != expected.get(k)
            )
            hint = (
                " Results written by an older schema can still be read, analysed and"
                " replay-validated, but not extended; write new blocks under a new"
                " experiment_id."
                if "schema_version" in diff
                else ""
            )
            raise IncompatibleResultsError(
                f"{what} at {path} was produced by a different configuration "
                f"(differs in: {diff}). Use a new experiment_id / pairing_id or a "
                f"different --out directory; refusing to mix results.{hint}"
            )
    else:
        _write_json_atomic(path, expected)


def ensure_locks(root: Path, cfg: ExperimentConfig, pairings: list[Pairing]) -> None:
    lock: dict[str, Any] = {
        "config_hash": cfg.config_hash,
        "environment": cfg.environment(),
        "schema_version": SCHEMA_VERSION,
        "matched_protocol_version": MATCHED_PROTOCOL_VERSION,
        "estimators": dict(cfg.estimators),
    }
    if cfg.estimators:  # raw-only locks are unchanged; estimator runs also pin versions + RNG derivation
        lock["estimator_provenance"] = cfg.estimator_provenance
        lock["estimator_config_hash"] = cfg.estimator_config_hash
    _check_or_create_lock(experiment_dir(root, cfg) / "experiment.lock.json", lock, "experiment lock")
    for p in pairings:
        _check_or_create_lock(
            pairing_dir(root, cfg, p.pairing_id) / "pairing.lock.json",
            {"pairing_hash": p.pairing_hash, "resolved": p.resolved()},
            "pairing lock",
        )


def existing_chunks(root: Path, cfg: ExperimentConfig, pairing_id: str) -> list[tuple[int, int]]:
    d = pairing_dir(root, cfg, pairing_id) / "blocks"
    if not d.exists():
        return []
    out = []
    for f in d.iterdir():
        m = CHUNK_RE.search(f.name)
        if m:
            out.append((int(m.group(1)), int(m.group(2))))
    return sorted(out)


def write_chunk(path: Path, table: pa.Table) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".parquet.tmp{os.getpid()}")
    pq.write_table(table, tmp, compression="zstd")
    os.replace(tmp, path)


def read_blocks(paths: list[Path] | Path, columns: list[str] | None = None) -> pa.Table:
    """Read one or more pairing/experiment directories or files into one table.

    Raises if any (pairing_id, block_id) appears twice: duplicated blocks would
    silently over-weight part of the sample.
    """
    if isinstance(paths, (str, Path)):
        paths = [Path(paths)]
    files: list[Path] = []
    for p in map(Path, paths):
        if p.is_file():
            files.append(p)
        else:
            files.extend(sorted(p.rglob("blocks_*.parquet")))
    if not files:
        raise FileNotFoundError(f"no block files under {paths}")
    tables = [pq.read_table(f, columns=columns, schema=None) for f in files]
    table = pa.concat_tables(tables, promote_options="default") if len(tables) > 1 else tables[0]
    if columns is None or {"pairing_id", "block_id", "config_hash"} <= set(columns):
        keys = list(
            zip(
                table.column("config_hash").to_pylist(),
                table.column("pairing_id").to_pylist(),
                table.column("block_id").to_pylist(),
                strict=True,
            )
        )
        if len(keys) != len(set(keys)):
            raise IncompatibleResultsError("duplicate (config_hash, pairing_id, block_id) rows")
    return table


def schema_matches(table: pa.Table) -> bool:
    return table.schema.equals(BLOCK_SCHEMA, check_metadata=False)
