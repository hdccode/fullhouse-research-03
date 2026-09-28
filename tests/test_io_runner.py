"""Parquet/manifest I/O, locks, resume, sharding, serial-vs-parallel equality."""

from __future__ import annotations

import json

import pyarrow.parquet as pq
import pytest

from fhr3.eval.runner import (
    WorkUnit,
    execute,
    filter_resume,
    parse_shard,
    plan_work,
    shard_units,
)
from fhr3.io.schema import BLOCK_SCHEMA, NONDETERMINISTIC_COLUMNS
from fhr3.io.store import IncompatibleResultsError, chunk_path, ensure_locks, read_blocks
from fhr3.validation.corpus import validate_pairing

from conftest import make_cfg


def strip(rows):
    return [{k: v for k, v in r.items() if k not in NONDETERMINISTIC_COLUMNS} for r in rows]


def test_plan_and_shards_partition_work():
    units = plan_work(["a", "b"], 3, 21, 5)
    assert units[0] == WorkUnit("a", 3, 5) and WorkUnit("a", 20, 21) in units
    covered = sorted(b for u in units if u.pairing_id == "a" for b in range(u.start, u.end))
    assert covered == list(range(3, 21))
    shards = [shard_units(units, (i, 3)) for i in range(3)]
    assert sorted(u for s in shards for u in s) == units
    assert all(not set(shards[i]) & set(shards[j]) for i in range(3) for j in range(i))
    with pytest.raises(ValueError):
        parse_shard("3/3")


def test_parquet_roundtrip_and_schema(tmp_path, tiny_cfg):
    units = plan_work(["ab"], 0, 4, 4)
    ensure_locks(tmp_path, tiny_cfg, [tiny_cfg.pairing("ab")])
    res = execute(tiny_cfg, units, tmp_path, None, "run-1", workers=1, write=False)
    rows = res[0]["rows"]
    execute(tiny_cfg, units, tmp_path, None, "run-1", workers=1, write=True)
    table = pq.read_table(chunk_path(tmp_path, tiny_cfg, "ab", 0, 4))
    assert table.schema.equals(BLOCK_SCHEMA, check_metadata=False)
    back = table.to_pylist()
    assert strip(back) == strip(rows)
    r0 = back[0]
    assert r0["raw_estimator_D"] == r0["D"] and r0["aivat_D"] is None
    assert r0["played_hands"] == 12 and len(r0["seat_D"]) == 6
    assert r0["config_hash"] == tiny_cfg.config_hash


def test_serial_and_parallel_are_identical(tmp_path, tiny_cfg):
    units = plan_work(["ab", "self"], 0, 8, 4)
    serial = execute(tiny_cfg, units, tmp_path, None, "r", workers=1, write=False)
    parallel = execute(tiny_cfg, units, tmp_path, None, "r", workers=2, write=False)
    flat = lambda res: strip([row for r in res for row in r["rows"]])  # noqa: E731
    assert flat(serial) == flat(parallel)
    # and sharded execution reproduces the same rows
    sharded = [execute(tiny_cfg, shard_units(units, (i, 3)), tmp_path, None, "r", write=False) for i in range(3)]
    rows = sorted(flat([r for s in sharded for r in s]), key=lambda r: (r["pairing_id"], r["block_id"]))
    assert rows == sorted(flat(serial), key=lambda r: (r["pairing_id"], r["block_id"]))


def test_locks_refuse_incompatible_config(tmp_path, tiny_cfg):
    ensure_locks(tmp_path, tiny_cfg, list(tiny_cfg.pairings))
    ensure_locks(tmp_path, tiny_cfg, list(tiny_cfg.pairings))  # idempotent
    other = make_cfg(root_seed=1)
    with pytest.raises(IncompatibleResultsError):
        ensure_locks(tmp_path, other, list(other.pairings))
    changed_agent = make_cfg(**{"agents.tight": {"kind": "heuristic", "style": "tight", "overrides": {"looseness": 0.7}}})
    assert changed_agent.config_hash == tiny_cfg.config_hash
    with pytest.raises(IncompatibleResultsError):
        ensure_locks(tmp_path, changed_agent, [changed_agent.pairing("ab")])


def test_operational_fields_do_not_change_hash():
    assert make_cfg(blocks=5).config_hash == make_cfg(chunk_size=99).config_hash == make_cfg().config_hash
    assert make_cfg(**{"rng.candidate_coupling": "independent"}).config_hash != make_cfg().config_hash


def test_resume_skips_done_and_rejects_misaligned(tmp_path, tiny_cfg):
    units = plan_work(["ab"], 0, 8, 4)
    execute(tiny_cfg, units[:1], tmp_path, None, "r1")
    todo, done = filter_resume(units, tmp_path, tiny_cfg)
    assert done == units[:1] and todo == units[1:]
    with pytest.raises(RuntimeError):
        filter_resume(plan_work(["ab"], 0, 8, 3), tmp_path, tiny_cfg)


def test_duplicate_blocks_rejected_on_read(tmp_path, tiny_cfg):
    execute(tiny_cfg, plan_work(["ab"], 0, 4, 4), tmp_path, None, "r1")
    src = chunk_path(tmp_path, tiny_cfg, "ab", 0, 4)
    dup = src.parent / "copy" / src.name
    dup.parent.mkdir()
    dup.write_bytes(src.read_bytes())
    with pytest.raises(IncompatibleResultsError):
        read_blocks(src.parent)


def test_validate_passes_and_detects_tampering(tmp_path, tiny_cfg):
    ensure_locks(tmp_path, tiny_cfg, list(tiny_cfg.pairings))
    execute(tiny_cfg, plan_work(["ab"], 0, 8, 4), tmp_path, None, "r1")
    rep = validate_pairing(tiny_cfg, tmp_path, "ab", (0, 8), replay=8)
    assert rep["ok"], rep["problems"]
    # tamper one D value -> consistency + replay checks must fail
    p = chunk_path(tmp_path, tiny_cfg, "ab", 0, 4)
    t = pq.read_table(p).to_pylist()
    t[0]["D"] = t[0]["D"] + 1.0
    import pyarrow as pa
    pq.write_table(pa.Table.from_pylist(t, schema=BLOCK_SCHEMA), p)
    rep = validate_pairing(tiny_cfg, tmp_path, "ab", (0, 8), replay=8)
    assert not rep["ok"]
    assert validate_pairing(tiny_cfg, tmp_path, "ab", (0, 12), replay=0)["problems"]


def test_traces_written_for_requested_blocks(tmp_path, tiny_cfg):
    execute(tiny_cfg, plan_work(["ab"], 0, 4, 4), tmp_path / "res", tmp_path / "tr", "r1")
    files = sorted((tmp_path / "tr" / "test-exp" / "ab" / "block_000000001").glob("*.phh"))
    assert len(files) == 12  # 6 seats x A/B
    assert "_fhr3_block_id = 1" in files[0].read_text()
    rows = read_blocks(tmp_path / "res").to_pylist()
    assert [r["traced"] for r in sorted(rows, key=lambda r: r["block_id"])] == [False, True, False, False]


def test_manifest_contents(tmp_path):
    from fhr3.io.manifest import RunManifest

    m = RunManifest(run_id="x", command=["fhr3"], config_path=None, config={}, config_hash="h", pairing_hashes={})
    d = json.loads(json.dumps(m.to_dict(), default=str))
    for key in ("python", "git", "dependencies", "machine", "seed_derivation_version", "schema_version", "started_at"):
        assert key in d
    assert d["dependencies"]["pokerkit"] == "0.7.5"
