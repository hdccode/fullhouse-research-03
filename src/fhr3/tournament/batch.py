"""Resumable, multiprocess execution of a cell's tournaments.

Unit of work: one tournament replicate. Completed and verified replicates are
skipped; incomplete ones are recomputed from scratch. Results are identical for any
worker count, order or interruption point because each tournament is a pure function
of (cell, replicate).
"""

from __future__ import annotations

import os
import platform
import time
import uuid
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import get_context
from pathlib import Path
from typing import Any

from fhr3.tournament.cells import Cell, cell_from_dict
from fhr3.tournament.runner import run_tournament
from fhr3.tournament.schedule import schedule_from_rows
from fhr3.tournament.store import (
    cell_dir,
    completed_replicates,
    ensure_lock,
    read_tournament_rows,
    tournament_dir,
    write_json_atomic,
    write_tournament,
)

_W: dict[str, Any] = {}


def _init(cell_dict: dict[str, Any], root: str) -> None:
    cell = cell_from_dict(cell_dict)
    _W.update(cell=cell, root=Path(root), player=cell.make_player())


def _schedule_for(cell: Cell, root: Path, replicate: int) -> Any:
    if cell.kind != "frozen_replay":
        return None
    assert cell.source is not None
    s, _ = cell.source_index(replicate)
    if not (tournament_dir(root, cell.source, s) / "manifest.json").exists():
        raise FileNotFoundError(f"source tournament {s} of {cell.source.cell_id} is not complete")
    rows, _, _ = read_tournament_rows(root, cell.source, s)
    return schedule_from_rows(rows)


def run_one(cell: Cell, root: Path, replicate: int, player: Any) -> dict[str, Any]:
    spec = cell.tournament_spec(replicate, _schedule_for(cell, root, replicate))
    res = run_tournament(spec, player)
    if cell.kind == "frozen_replay":
        res.extra["source_schedule_digest"] = res.manifest()["schedule_digest"]
    return write_tournament(root, cell, res)


def _work(replicate: int) -> dict[str, Any]:
    t0 = time.perf_counter()
    man = run_one(_W["cell"], _W["root"], replicate, _W["player"])
    return {"replicate": replicate, "wall_s": time.perf_counter() - t0, "hands": man["hands_played"]}


def run_cell(cell: Cell, root: Path, replicates: Iterable[int], workers: int = 1,
             allow_source_change: bool = False, progress: bool = True) -> dict[str, Any]:
    root = Path(root)
    ensure_lock(root, cell, allow_source_change)
    if cell.source is not None:
        ensure_lock(root, cell.source, allow_source_change)
    wanted = sorted(set(replicates))
    done = set(completed_replicates(root, cell, verify=True))
    todo = [r for r in wanted if r not in done]
    t0 = time.perf_counter()
    stats: list[dict[str, Any]] = []
    if todo:
        if workers <= 1:
            _init(cell.to_dict(), str(root))
            for r in todo:
                stats.append(_work(r))
                if progress:
                    print(f"  {cell.cell_id} t{r:06d} {stats[-1]['wall_s']:.1f}s", flush=True)
        else:
            ctx = get_context("spawn")
            with ProcessPoolExecutor(workers, mp_context=ctx, initializer=_init,
                                     initargs=(cell.to_dict(), str(root))) as ex:
                futs = {ex.submit(_work, r): r for r in todo}
                for i, f in enumerate(as_completed(futs), 1):
                    stats.append(f.result())
                    if progress:
                        print(f"  {cell.cell_id} {i}/{len(todo)} t{stats[-1]['replicate']:06d} "
                              f"{stats[-1]['wall_s']:.1f}s", flush=True)
    wall = time.perf_counter() - t0
    run = {
        "run_id": time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6],
        "cell_id": cell.cell_id,
        "requested": [wanted[0], wanted[-1] + 1] if wanted else None,
        "skipped_completed": len(wanted) - len(todo),
        "ran": len(todo),
        "workers": workers,
        "wall_s": round(wall, 2),
        "tournament_wall_s": [round(s["wall_s"], 3) for s in stats],
        "hands": sum(s["hands"] for s in stats),
        "host": {"machine": platform.machine(), "python": platform.python_version(), "cpus": os.cpu_count()},
    }
    if todo:
        write_json_atomic(cell_dir(root, cell) / "runs" / f"{run['run_id']}.json", run)
    return run
