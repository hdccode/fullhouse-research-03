"""Experiment runner: planning, sharding, resume, multiprocessing.

Unit of work: ``(pairing_id, [start, end))`` on a fixed chunk grid
(``chunk_size``). Every block is a pure function of (config, pairing, block_id),
so any partition of work across shards/processes yields identical rows.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from multiprocessing import get_context
from pathlib import Path
from typing import Any

from fhr3.agents import Agent, build_agent
from fhr3.configs.experiment import ExperimentConfig, Pairing, config_from_dict
from fhr3.eval.matched import MatchedBlockResult, MatchedBlockSpec, run_matched_block
from fhr3.games import GameAdapter, make_adapter
from fhr3.io.schema import result_to_row, rows_to_table
from fhr3.io.store import chunk_path, existing_chunks, write_chunk
from fhr3.io.traces import should_trace, trace_dir, write_traces


@dataclass(frozen=True, order=True)
class WorkUnit:
    pairing_id: str
    start: int
    end: int


def parse_range(text: str) -> tuple[int, int]:
    a, _, b = text.partition(":")
    start, end = int(a or 0), int(b)
    if not 0 <= start < end:
        raise ValueError(f"bad block range {text!r}")
    return start, end


def parse_shard(text: str) -> tuple[int, int]:
    """``i/n`` with 0 <= i < n (zero-based)."""
    a, _, b = text.partition("/")
    i, n = int(a), int(b)
    if not 0 <= i < n:
        raise ValueError(f"shard must be i/n with 0 <= i < n, got {text!r}")
    return i, n


def plan_work(
    pairing_ids: Iterable[str], start: int, end: int, chunk_size: int
) -> list[WorkUnit]:
    units = []
    for pid in pairing_ids:
        c = (start // chunk_size) * chunk_size
        while c < end:
            units.append(WorkUnit(pid, max(start, c), min(end, c + chunk_size)))
            c += chunk_size
    return sorted(units)


def shard_units(units: list[WorkUnit], shard: tuple[int, int] | None) -> list[WorkUnit]:
    if shard is None:
        return units
    i, n = shard
    return [u for k, u in enumerate(units) if k % n == i]


def filter_resume(
    units: list[WorkUnit], results_root: Path, cfg: ExperimentConfig
) -> tuple[list[WorkUnit], list[WorkUnit]]:
    """Split into (todo, already_done). Overlapping-but-different chunks abort."""
    todo, done = [], []
    by_pairing: dict[str, list[tuple[int, int]]] = {}
    for u in units:
        have = by_pairing.setdefault(u.pairing_id, existing_chunks(results_root, cfg, u.pairing_id))
        if (u.start, u.end) in have:
            done.append(u)
            continue
        clash = [(a, b) for a, b in have if a < u.end and u.start < b]
        if clash:
            raise RuntimeError(
                f"{u} overlaps existing chunk(s) {clash} with different boundaries; "
                "re-run with the original --blocks grid / chunk_size"
            )
        todo.append(u)
    return todo, done


class BlockSimulator:
    """Holds the adapter and agent instances for one (config, pairing)."""

    def __init__(self, cfg: ExperimentConfig, pairing: Pairing) -> None:
        self.cfg, self.pairing = cfg, pairing
        self.adapter: GameAdapter = make_adapter(cfg.game)
        self.a: Agent = build_agent(pairing.candidate_a)
        self.b: Agent = build_agent(pairing.candidate_b)
        self.refs: list[Agent] = [build_agent(s) for s in pairing.reference_seats]
        self.versions = {"A": self.a.version, "B": self.b.version}
        from fhr3.estimators import build_estimators

        self.estimators = build_estimators(cfg.estimators, self.adapter, cfg.root_seed)

    def spec(self, block_id: int) -> MatchedBlockSpec:
        c = self.cfg
        return MatchedBlockSpec(
            experiment_id=c.experiment_id,
            config_hash=c.config_hash,
            pairing_id=self.pairing.pairing_id,
            pairing_hash=self.pairing.pairing_hash,
            root_seed=c.root_seed,
            block_id=block_id,
            rng=c.rng,
        )

    def run(self, block_id: int, trace: bool = False) -> MatchedBlockResult:
        return run_matched_block(
            self.spec(block_id), self.adapter, self.a, self.b, self.refs, trace, self.estimators
        )

    def row(self, result: MatchedBlockResult, run_id: str, traced: bool) -> dict[str, Any]:
        return result_to_row(
            self.cfg, self.pairing, self.versions, result, run_id, traced, self.adapter.deal_layout
        )


def run_unit(
    cfg: ExperimentConfig,
    unit: WorkUnit,
    results_root: Path,
    traces_root: Path | None,
    run_id: str,
    sim_cache: dict[str, BlockSimulator] | None = None,
    write: bool = True,
) -> dict[str, Any]:
    cache = sim_cache if sim_cache is not None else {}
    sim = cache.get(unit.pairing_id)
    if sim is None:
        sim = cache[unit.pairing_id] = BlockSimulator(cfg, cfg.pairing(unit.pairing_id))
    rows, invalid, traced_n = [], 0, 0
    t0 = time.perf_counter()
    for b in range(unit.start, unit.end):
        spec = sim.spec(b)
        want_trace = traces_root is not None and should_trace(cfg.trace, b, spec.seed)
        res = sim.run(b, trace=want_trace)
        if not res.valid:
            invalid += 1
            if traces_root is not None and cfg.trace.include_invalid and not want_trace:
                res_t = sim.run(b, trace=True)  # deterministic re-run, now with traces
                res.traces = res_t.traces
                want_trace = True
        if want_trace and res.traces and traces_root is not None:
            write_traces(trace_dir(traces_root, cfg.experiment_id, unit.pairing_id, b), res.traces)
            traced_n += 1
        rows.append(sim.row(res, run_id, traced=want_trace))
    sim_s = time.perf_counter() - t0
    t_w = time.perf_counter()
    table = rows_to_table(rows)
    if write:
        write_chunk(chunk_path(results_root, cfg, unit.pairing_id, unit.start, unit.end), table)
    write_s = time.perf_counter() - t_w
    return {
        "unit": [unit.pairing_id, unit.start, unit.end],
        "blocks": len(rows),
        "invalid": invalid,
        "traced": traced_n,
        "wall_s": time.perf_counter() - t0,
        "simulate_s": sim_s,
        "serialize_s": write_s,
        "runtime_ms_sum": sum(r["runtime_ms"] for r in rows),
        "agent_ms_sum": sum(r["agent_ms"] for r in rows),
        "estimator_ms_sum": sum(r["estimator_ms"] or 0.0 for r in rows),
        "rows": None if write else rows,
    }


# ------------------------------------------------------------------ multiprocessing
_WORKER_STATE: dict[str, Any] = {}


def _worker_init(raw_config: Mapping[str, Any]) -> None:
    _WORKER_STATE["cfg"] = config_from_dict(raw_config)
    _WORKER_STATE["sims"] = {}


def _worker_run(
    unit: WorkUnit, results_root: str, traces_root: str | None, run_id: str, write: bool
) -> dict[str, Any]:
    return run_unit(
        _WORKER_STATE["cfg"], unit, Path(results_root),
        Path(traces_root) if traces_root else None, run_id, _WORKER_STATE["sims"], write,
    )


def execute(
    cfg: ExperimentConfig,
    units: list[WorkUnit],
    results_root: Path,
    traces_root: Path | None,
    run_id: str,
    workers: int = 1,
    write: bool = True,
    progress: Callable[[dict[str, Any], int, int], None] | None = None,
) -> list[dict[str, Any]]:
    """Run units serially (workers=1) or in a spawn-based process pool."""
    out: list[dict[str, Any]] = []
    if workers <= 1:
        cache: dict[str, BlockSimulator] = {}
        for i, u in enumerate(units):
            r = run_unit(cfg, u, results_root, traces_root, run_id, cache, write)
            out.append(r)
            if progress:
                progress(r, i + 1, len(units))
        return out
    ctx = get_context("spawn")
    with ProcessPoolExecutor(
        max_workers=workers, mp_context=ctx, initializer=_worker_init, initargs=(dict(cfg.raw),)
    ) as pool:
        futs = [
            pool.submit(_worker_run, u, str(results_root), str(traces_root) if traces_root else None, run_id, write)
            for u in units
        ]
        for i, f in enumerate(as_completed(futs)):
            r = f.result()
            out.append(r)
            if progress:
                progress(r, i + 1, len(units))
    return sorted(out, key=lambda r: tuple(r["unit"]))
