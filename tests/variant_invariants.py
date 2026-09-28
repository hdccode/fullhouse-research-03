"""Shared matched-block invariant checks, reused by every variant's test module."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from fhr3.configs.experiment import ExperimentConfig, load_config
from fhr3.eval.runner import BlockSimulator, execute, plan_work
from fhr3.io.schema import BLOCK_SCHEMA, NONDETERMINISTIC_COLUMNS
from fhr3.io.store import chunk_path
from fhr3.validation.corpus import rows_equal

CONFIGS = Path(__file__).resolve().parents[1] / "configs"


def strip(rows):
    return [{k: v for k, v in r.items() if k not in NONDETERMINISTIC_COLUMNS} for r in rows]


def check_core_invariants(cfg: ExperimentConfig, blocks: range, allin_expected: bool = True) -> dict:
    """Replay, self-play zero, A/B swap negation, validity. Returns diagnostics."""
    k = cfg.game.player_count
    control = BlockSimulator(cfg, cfg.pairing("c0-selfplay-control"))
    ab = BlockSimulator(cfg, cfg.pairing("p3-aggressive-vs-neutral"))
    ab2 = BlockSimulator(cfg, cfg.pairing("p3-aggressive-vs-neutral"))  # fresh objects
    ba = BlockSimulator(cfg, cfg.pairing("p3-aggressive-vs-neutral"))
    ba.a, ba.b = ab.b, ab.a
    nonzero = allins = hands = 0
    for b in blocks:
        c = control.run(b)
        assert c.valid, c.error_detail
        assert c.D == 0.0 and all(x == 0.0 for x in c.seat_D)
        r, r2, s = ab.run(b), ab2.run(b), ba.run(b)
        assert r.valid and s.valid, (r.error_detail, s.error_detail)
        assert rows_equal(ab.row(r, "x", False), ab2.row(r2, "x", False)) == []  # exact replay
        assert r.D == -s.D and r.seat_D == [-x for x in s.seat_D]
        assert r.played_hands == r.hands_for("A") + r.hands_for("B")
        nonzero += r.D != 0
        allins += sum(h.all_in for h in r.hands)
        hands += r.played_hands
    assert nonzero > 0
    if allin_expected:
        assert allins > 0
    return {"nonzero": nonzero, "allins": allins, "hands": hands, "k": k}


def check_serial_parallel_parquet(cfg: ExperimentConfig, tmp_path: Path, n: int = 4) -> None:
    units = plan_work(["p1-neutral-vs-loose10", "c0-selfplay-control"], 0, n, 2)
    serial = execute(cfg, units, tmp_path, None, "r", workers=1, write=False)
    parallel = execute(cfg, units, tmp_path, None, "r", workers=2, write=False)
    flat = lambda res: strip([row for r in res for row in r["rows"]])  # noqa: E731
    assert flat(serial) == flat(parallel)
    execute(cfg, units[:1], tmp_path, None, "r", workers=1, write=True)
    u = units[0]
    table = pq.read_table(chunk_path(tmp_path, cfg, u.pairing_id, u.start, u.end))
    assert table.schema.equals(BLOCK_SCHEMA, check_metadata=False)
    assert strip(table.to_pylist()) == flat(serial)[: u.end - u.start]


def load(name: str) -> ExperimentConfig:
    return load_config(CONFIGS / name)
