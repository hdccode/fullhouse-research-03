"""FHR3B tournaments: invariants, exact replay, resume, workers, frozen schedule, R-prefix."""

from __future__ import annotations

import filecmp
import shutil
from pathlib import Path

import numpy as np
import pytest

from fhr3.tournament.batch import run_cell
from fhr3.tournament.cells import Cell
from fhr3.tournament.fields import FieldManifest, load_mode
from fhr3.tournament.match import MatchResult
from fhr3.tournament.manifests import tournament_seeds
from fhr3.tournament.protocol import TournamentProtocol
from fhr3.tournament.replay import (
    ValidationError,
    check_replay,
    replay_match_hands,
    validate_cell,
    validate_tournament_rows,
    verify_prefix,
)
from fhr3.tournament.runner import TournamentInvariantError, TournamentSpec, run_tournament
from fhr3.tournament.schedule import schedule_from_rows
from fhr3.tournament.store import completed_replicates, load_cell_arrays, read_tournament_rows, tournament_dir

BOTS = [f"bot{i:02d}" for i in range(24)]


def synthetic_field(n=24):
    bots = tuple({"bot_id": b, "kind": "checkcall", "params": {}, "version": "checkcall", "meta": {}} for b in BOTS[:n])
    return FieldManifest(f"synth{n}", "nlhe6", "smoke", bots, {"method": "test"})


def synth_cell(rounds=5, hands=50, noise=200.0, kind="adaptive", source=None, j=0, strength=None, k=3):
    mode = load_mode("nlhe6")
    proto = TournamentProtocol("test", "smoke", 6, hands, rounds, k)
    strength = strength or {b: (i - 12) * 0.5 for i, b in enumerate(BOTS)}
    return Cell(kind, mode, proto, synthetic_field(), "fhr3b-test", "test", source, j,
                synthetic={"strength": strength, "noise_sd": noise})


def test_round_invariants_and_final_consistency(tmp_path):
    cell = synth_cell()
    run_cell(cell, tmp_path, range(3), progress=False)
    reps = completed_replicates(tmp_path, cell)
    assert reps == [0, 1, 2]
    assert validate_cell(tmp_path, cell, reps)["validated"] == 3
    tables, final, man = read_tournament_rows(tmp_path, cell, 0)
    for rnd in range(1, 6):
        rows = [r for r in tables if r["round"] == rnd]
        assert sorted(r["bot_id"] for r in rows) == sorted(BOTS)
        assert {r["table_size"] for r in rows} == {6}
    assert sum(r["final_score"] for r in final) == 0
    assert man["qualified"] == [r["bot_id"] for r in sorted(final, key=lambda r: r["final_rank"])][:3]


def test_exact_replay_and_tamper_detection(tmp_path):
    cell = synth_cell()
    run_cell(cell, tmp_path, range(2), progress=False)
    assert check_replay(tmp_path, cell, [0, 1])["replayed_exactly"] == 2
    tables, final, man = read_tournament_rows(tmp_path, cell, 1)
    tables[5]["chip_delta"] += 1
    with pytest.raises(ValidationError):
        validate_tournament_rows(cell, 1, tables, final, man)


def test_resume_after_crash_is_identical(tmp_path):
    cell = synth_cell()
    full, part = tmp_path / "full", tmp_path / "part"
    run_cell(cell, full, range(4), progress=False)
    run_cell(cell, part, range(2), progress=False)
    (tournament_dir(part, cell, 1) / "manifest.json").unlink()  # interrupted before commit marker
    run = run_cell(cell, part, range(4), progress=False)
    assert run["ran"] == 3 and run["skipped_completed"] == 1
    for r in range(4):
        for f in ("tables.parquet", "final.parquet"):
            assert filecmp.cmp(tournament_dir(full, cell, r) / f, tournament_dir(part, cell, r) / f, shallow=False)


def test_worker_count_does_not_change_results(tmp_path):
    cell = synth_cell()
    run_cell(cell, tmp_path / "w1", range(4), workers=1, progress=False)
    run_cell(cell, tmp_path / "w2", range(4), workers=2, progress=False)
    for r in range(4):
        for f in ("tables.parquet", "final.parquet"):
            assert filecmp.cmp(tournament_dir(tmp_path / "w1", cell, r) / f,
                               tournament_dir(tmp_path / "w2", cell, r) / f, shallow=False)


def test_replication_count_is_not_part_of_identity(tmp_path):
    cell = synth_cell()
    run_cell(cell, tmp_path, range(2), progress=False)
    run = run_cell(synth_cell(), tmp_path, range(5), progress=False)
    assert run["skipped_completed"] == 2 and run["ran"] == 3


def test_changed_protocol_is_a_new_cell():
    assert synth_cell(rounds=5).cell_id != synth_cell(rounds=6).cell_id
    assert synth_cell(hands=50).identity_hash != synth_cell(hands=60).identity_hash
    assert synth_cell(k=3).identity_hash != synth_cell(k=4).identity_hash


def test_r_prefix_identity(tmp_path):
    cell = synth_cell(rounds=5)
    run_cell(cell, tmp_path, range(2), progress=False)
    for r in (1, 2, 4):
        verify_prefix(tmp_path, cell, r, [0, 1])
    a = load_cell_arrays(tmp_path, cell, with_rounds=True)
    assert np.array_equal(a["round_rank"][:, -1, :], a["final_rank"])


def test_frozen_schedule_ignores_outcomes_and_adaptive_reacts(tmp_path):
    src = synth_cell()
    run_cell(src, tmp_path, range(2), progress=False)
    rev = {b: -s for b, s in src.synthetic["strength"].items()}  # opposite outcomes
    frozen = Cell("frozen_replay", src.mode, src.protocol, src.field, src.seed_family, src.namespace, src, 2,
                  synthetic={"strength": rev, "noise_sd": 200.0})
    src_rev = Cell("adaptive", src.mode, src.protocol, src.field, src.seed_family, src.namespace,
                   synthetic={"strength": rev, "noise_sd": 200.0})
    run_cell(frozen, tmp_path, range(4), progress=False)
    src_sched = schedule_from_rows(read_tournament_rows(tmp_path, src, 0)[0])
    for rep in (0, 1):  # replays of source 0 with reversed strengths: identical tables
        assert schedule_from_rows(read_tournament_rows(tmp_path, frozen, rep)[0]) == src_sched
    assert validate_cell(tmp_path, frozen, [0, 1, 2, 3])["validated"] == 4
    # the adaptive rule with reversed outcomes re-pairs differently after round 1
    run_cell(src_rev, tmp_path, range(1), progress=False)
    rev_sched = schedule_from_rows(read_tournament_rows(tmp_path, src_rev, 0)[0])
    assert rev_sched[0] == src_sched[0] and rev_sched[1:] != src_sched[1:]


def test_adaptive_and_frozen_replays_share_round_one_and_randomness(tmp_path):
    src = synth_cell()
    run_cell(src, tmp_path, range(1), progress=False)
    frozen = Cell("frozen_replay", src.mode, src.protocol, src.field, src.seed_family, src.namespace, src, 2,
                  synthetic=src.synthetic)
    adapt = Cell("adaptive_replay", src.mode, src.protocol, src.field, src.seed_family, src.namespace, src, 2,
                 synthetic=src.synthetic)
    run_cell(frozen, tmp_path, range(2), progress=False)
    run_cell(adapt, tmp_path, range(2), progress=False)
    f = read_tournament_rows(tmp_path, frozen, 0)[0]
    a = read_tournament_rows(tmp_path, adapt, 0)[0]
    s = read_tournament_rows(tmp_path, src, 0)[0]
    r1 = lambda rows: [(r["table_index"], r["bot_id"], r["chip_delta"]) for r in rows if r["round"] == 1]
    assert r1(f) == r1(a)  # same round-1 tables and same fresh randomness
    assert r1(f) != r1(s)  # but not the source's randomness
    assert frozen.tournament_spec(0, [[]]).seeds.order_seed == tournament_seeds("fhr3b-test", "test", 0).order_seed


class _Leaky:
    zero_sum = True

    def play(self, key, seat_order, hands):
        d = {b: 0 for b in seat_order}
        d[seat_order[0]] = 1
        return MatchResult(d, hands, {})


def test_invariant_gate_rejects_non_zero_sum_tables():
    cell = synth_cell()
    spec = cell.tournament_spec(0)
    with pytest.raises(TournamentInvariantError):
        run_tournament(spec, _Leaky())


def test_poker_tournament_replays_exactly_with_hand_logs(tmp_path):
    from fhr3.tournament.experiments import load_profile

    prof = load_profile("smoke", tmp_path)
    cell = prof.cell("nlhe6", "smoke12")
    run_cell(cell, tmp_path, range(1), progress=False)
    assert check_replay(tmp_path, cell, [0])["replayed_exactly"] == 1
    log = replay_match_hands(tmp_path, cell, 0, 2, 1)
    assert 1 <= len(log) <= cell.protocol.hands_per_match
    assert all(sum(h["payoffs"]) == 0 for h in log)
