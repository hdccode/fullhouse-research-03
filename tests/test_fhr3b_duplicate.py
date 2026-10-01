"""FHR3B duplicate lanes (Experiment D / matched mu_field) and within-match history exposure."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from fhr3.tournament.agents import build_agent
from fhr3.tournament.batch import run_cell
from fhr3.tournament.calibration import CalibrationSpec, play_rounds
from fhr3.tournament.cells import Cell
from fhr3.tournament.experiments import FieldNotFrozenError, load_profile
from fhr3.tournament.fields import FHR3B_CONFIGS, load_field, load_mode
from fhr3.tournament.match import (
    MATCH_HISTORY_MAX_ENTRIES,
    DuplicateMatchPlayer,
    MatchKey,
    PokerMatchPlayer,
    lane_orders,
)
from fhr3.tournament.protocol import TournamentProtocol, duplicate_allocations
from fhr3.tournament.replay import check_replay, validate_cell

GOLDEN = Path(__file__).parent / "data/fhr3b/golden_ordinary_matches.json"


def _pool(mode):
    m = load_mode(mode)
    specs = load_field(FHR3B_CONFIGS / f"fields/{mode}/pool.json").specs()
    return m, specs


class Spy:
    """Transparent agent wrapper recording what one instance observes."""

    instances: list = []

    def __init__(self, inner) -> None:
        self.inner, self.agent_id, self.version = inner, inner.agent_id, inner.version
        self.calls, self.history_hands, self.by_hand = 0, set(), {}
        Spy.instances.append(self)

    def act(self, obs, legal, rng):
        self.calls += 1
        assert not any("lane" in k for k in obs.extra)  # lane identity is never bot-visible
        for e in obs.extra["match_history"]:  # a rolling log of ONE match: entries never change
            self.by_hand.setdefault(e[0], set()).add(e)
        self.history_hands |= {e[0] for e in obs.extra["match_history"]}
        assert all(e[0] < obs.extra["match_hand_index"] for e in obs.extra["match_history"])
        assert obs.extra["seat_bot_ids"][obs.seat] == self.agent_id
        return self.inner.act(obs, legal, rng)


def _dup(mode, n_seats=None, spy=False):
    m, specs = _pool(mode)
    ids = sorted(specs)[10:10 + (n_seats or m.table_size)]
    wrap = Spy if spy else (lambda a: a)
    player = DuplicateMatchPlayer(m.game, m.stack_policy, lambda: {b: wrap(build_agent(specs[b])) for b in ids})
    return m, ids, player


# ------------------------------------------------------------------ duplicate lanes
@pytest.mark.parametrize("k", [4, 6])
def test_lane_seat_balance_and_base_variation(k):
    ids = [f"b{i}" for i in range(k)]
    orders = lane_orders(MatchKey(1, 2, 3, 4), ids)
    assert len(orders) == k
    for seat in range(k):
        assert sorted(o[seat] for o in orders) == sorted(ids)  # every bot in every seat exactly once
    for o in orders:
        assert sorted(o) == sorted(ids)
    bases = {tuple(lane_orders(MatchKey(1, 2, r, t), ids)[0]) for r in range(5) for t in range(3)}
    assert len(bases) > 3  # base seating varies between matches
    assert lane_orders(MatchKey(1, 2, 3, 4), list(reversed(ids))) == orders  # independent of input order


@pytest.mark.parametrize("mode,lanes", [("aof4", 4), ("nlhe4", 4), ("nlhe6", 6)])
def test_lane_count_by_mode_and_aggregation(mode, lanes):
    m, ids, player = _dup(mode)
    res = player.play(MatchKey(5, 6, 1, 0), ids, 25)
    info = res.info["duplicate_lanes"]
    assert len(info) == lanes == m.table_size
    for lane in info:  # chip conservation inside every lane
        assert sum(lane["deltas"].values()) == 0
        if m.stack_policy == "persistent_no_rebuy":
            assert all(d >= -m.game.starting_stack_chips for d in lane["deltas"].values())
    assert res.deltas == {b: sum(lane["deltas"][b] for lane in info) for b in ids}  # aggregate after lanes
    assert res.hands_played == sum(lane["hands_played"] for lane in info)
    assert sum(res.deltas.values()) == 0


def test_duplicate_is_deterministic_and_lanes_share_the_deck():
    m, ids, player = _dup("nlhe6")
    log_a, log_b = [], []
    a = player.play(MatchKey(7, 8, 2, 1), ids, 12, hand_log=log_a)
    b = player.play(MatchKey(7, 8, 2, 1), ids, 12, hand_log=log_b)
    assert a.deltas == b.deltas and a.info == b.info and log_a == log_b
    for hand in range(3):  # same chance stream: every lane's board is a prefix of one shared runout
        boards = [tuple(h["board"]) for h in log_a if h["hand"] == hand]
        longest = max(boards, key=len)
        assert len(boards) == 6 and all(bd == longest[:len(bd)] for bd in boards)


def test_no_cross_lane_state_or_history_leakage():
    Spy.instances = []
    m, ids, player = _dup("nlhe4", spy=True)
    k = len(ids)
    res = player.play(MatchKey(9, 9, 1, 0), ids, 40)
    owner = {id(a): lane for lane, lp in enumerate(player.lanes) for a in lp.agents.values()}
    used = [s for s in Spy.instances if s.calls]
    assert len(owner) == len(Spy.instances)  # every agent instance belongs to exactly one lane player
    assert sorted({owner[id(s)] for s in used}) == list(range(k))  # the k lanes each used their own instances
    assert Counter(owner[id(s)] for s in used) == {lane: k for lane in range(k)}
    lane_hist = {}
    for s in used:  # every instance of a lane saw the same (lane-private) history; lanes differ
        lane_hist.setdefault(owner[id(s)], {}).update({h: frozenset(v) for h, v in s.by_hand.items()})
    for lane, hist in lane_hist.items():
        for s in used:
            if owner[id(s)] == lane:
                assert all(frozenset(v) == hist[h] for h, v in s.by_hand.items())
    assert len({tuple(sorted((h, v) for h, v in hist.items())) for hist in lane_hist.values()}) > 1
    assert len({tuple(sorted(li["deltas"].items())) for li in res.info["duplicate_lanes"]}) > 1


def test_lane_identity_not_exposed_in_corresponding_states():
    """Same seating, lane 0 vs lane 1: the first action request of every hand-0 decision is identical."""
    m, specs = _pool("nlhe6")
    ids = sorted(specs)[30:36]
    seen: dict[int, list] = {0: [], 1: []}

    class Rec:
        def __init__(self, inner, lane):
            self.inner, self.lane, self.agent_id, self.version = inner, lane, inner.agent_id, inner.version

        def act(self, obs, legal, rng):
            seen[self.lane].append((obs, legal))
            return self.inner.act(obs, legal, rng)

    for lane in (0, 1):
        PokerMatchPlayer(m.game, m.stack_policy, {b: Rec(build_agent(specs[b]), lane) for b in ids}).play(
            MatchKey(4, 4, 1, 0), ids, 1, lane=lane)
    # the first decision of the match is reached identically in both lanes (no decision randomness before it)
    (o0, l0), (o1, l1) = seen[0][0], seen[1][0]
    assert o0 == o1 and l0 == l1
    for obs, _ in seen[0] + seen[1]:
        assert not any("lane" in key for key in obs.extra)
        assert all(len(e) == 5 for e in obs.extra["match_history"])


def test_a_bot_can_bust_in_one_lane_and_survive_in_another():
    m, specs = _pool("nlhe6")
    for start in range(0, 60, 6):
        ids = sorted(specs)[start:start + 6]
        player = DuplicateMatchPlayer(m.game, m.stack_policy, lambda: {b: build_agent(specs[b]) for b in ids})
        info = player.play(MatchKey(3, 4, 1, start), ids, 200).info["duplicate_lanes"]
        for b in ids:
            busted = [li["bust_hand"][b] >= 0 for li in info]
            if any(busted) and not all(busted):
                return
    pytest.fail("no bot busted in some lanes but not others")


def test_duplicate_protocol_hash_and_allocations():
    base = dict(name="t", status="research", table_size=6, hands_per_match=400, rounds=40, qualify_top_k=6)
    ordinary, dup = TournamentProtocol(**base), TournamentProtocol(**base, match_format="duplicate")
    assert "match_format" not in ordinary.to_dict() and ordinary.protocol_hash != dup.protocol_hash
    assert load_profile("publication").base.protocol_hash == "ca1cccabac0c8c23"  # unchanged by the new field
    four = duplicate_allocations(40, 400, 4)
    assert all(a.exact and a.work_per_table == 16000 for a in four)
    six = duplicate_allocations(40, 400, 6)
    assert not any(a.exact for a in six) and all(abs(a.work_per_table / 16000 - 1) < 0.06 for a in six)


def test_duplicate_tournament_persists_lanes_validates_and_replays(tmp_path):
    from fhr3.tournament.replay import ValidationError, validate_tournament_rows
    from fhr3.tournament.store import read_lane_rows, read_tournament_rows, tournament_dir

    prof = load_profile("smoke", tmp_path)
    c = prof.cell("nlhe6", "smoke12")
    dup = Cell("adaptive", c.mode, c.protocol.with_(match_format="duplicate", rounds=2), c.field, c.seed_family,
               c.namespace)
    assert "dup" in dup.cell_id
    run_cell(dup, tmp_path, range(2), progress=False)
    assert validate_cell(tmp_path, dup, [0, 1])["validated"] == 2
    assert check_replay(tmp_path, dup, [0, 1])["replayed_exactly"] == 2
    tables, final, man = read_tournament_rows(tmp_path, dup, 0)
    lanes = read_lane_rows(tmp_path, dup, 0)
    assert len(lanes) == 2 * 2 * 6 * 6  # rounds x tables x lanes x bots
    for r in tables:  # the lane-summed delta IS the scoring quantity
        assert r["chip_delta"] == sum(ln["chip_delta"] for ln in lanes if (ln["round"], ln["table_index"],
                                      ln["bot_id"]) == (r["round"], r["table_index"], r["bot_id"]))
    assert all(ln["busted"] == (ln["bust_hand"] >= 0) for ln in lanes)
    assert {ln["lane"] for ln in lanes} == set(range(6))
    lanes[0]["chip_delta"] += 1  # tampering with a lane row is detected
    with pytest.raises(ValidationError):
        validate_tournament_rows(dup, 0, tables, final, man, None, lanes)
    ordinary = prof.cell("nlhe6", "smoke12")
    run_cell(ordinary, tmp_path, range(1), progress=False)
    assert not (tournament_dir(tmp_path, ordinary, 0) / "lanes.parquet").exists()
    assert validate_cell(tmp_path, ordinary, [0])["validated"] == 1


def test_matched_calibration_rounds_and_ids():
    prof = load_profile("publication")
    spec = prof.calibration_spec("aof4", "field", "crowded_cutoff")  # frozen field
    assert spec.match_format == "duplicate" and ".dup." in spec.calib_id
    assert prof.calibration_rounds("field", "nlhe6") == 500 and prof.calibration_rounds("field", "aof4") == 750
    assert prof.calibration_spec("aof4", "pool").calib_id == "aof4.aof4-pool.H400.pool-calibration.351766c0"
    six = load_mode("nlhe6")
    small = CalibrationSpec(six, load_field(FHR3B_CONFIGS / "fields/nlhe6/smoke12.json"), 8,
                            six.stack_policy, "fam", "test", match_format="duplicate")
    rows = play_rounds(small, 0, 1, small.make_player())
    assert len(rows) == 12 and sum(r["chip_delta"] for r in rows) == 0
    assert all(r["hands_played"] <= 8 * 6 for r in rows)


# ------------------------------------------------------------------ within-match history
@pytest.mark.parametrize("mode", ["aof4", "nlhe6"])
def test_rolling_match_history_is_exposed(mode):
    Spy.instances = []
    m, specs = _pool(mode)
    ids = sorted(specs)[20:20 + m.table_size]
    player = PokerMatchPlayer(m.game, m.stack_policy, {b: Spy(build_agent(specs[b])) for b in ids})
    player.play(MatchKey(1, 1, 1, 0), ids, 120)
    assert any(s.history_hands for s in Spy.instances)  # earlier hands are visible to later decisions
    assert all(s.calls for s in Spy.instances)


def test_history_window_is_capped():
    m, specs = _pool("aof4")
    ids = sorted(specs)[:4]
    seen = []

    class Len:
        def __init__(self, inner):
            self.inner, self.agent_id, self.version = inner, inner.agent_id, inner.version

        def act(self, obs, legal, rng):
            seen.append(len(obs.extra["match_history"]))
            return self.inner.act(obs, legal, rng)

    PokerMatchPlayer(m.game, m.stack_policy, {b: Len(build_agent(specs[b])) for b in ids}).play(
        MatchKey(2, 2, 1, 0), ids, 300)
    assert max(seen) == MATCH_HISTORY_MAX_ENTRIES


def test_history_exposure_is_result_neutral():
    """Golden ordinary matches captured from the pre-history engine (commit ff746c4).

    They were captured with the FHR3A heuristic NLHE pools, now retired (heads-up-role bug),
    so the retired pool specs are used for NLHE.
    """
    from fhr3.agents import build_agent as fhr3a_build_agent

    golden = json.loads(GOLDEN.read_text())
    retired = FHR3B_CONFIGS / "fields/retired/hu-role-bug"
    for mode, g in golden.items():
        m = load_mode(mode)
        if (retired / mode / "pool.json").exists():
            specs = load_field(retired / mode / "pool.json").specs()
            res = PokerMatchPlayer(m.game, m.stack_policy, {b: fhr3a_build_agent(specs[b]) for b in g["seats"]}).play(
                MatchKey(11, 22, 3, 1), g["seats"], 60)
            assert res.deltas == g["deltas"] and res.hands_played == g["hands"], mode
            continue
        _, specs = _pool(mode)
        res = PokerMatchPlayer(m.game, m.stack_policy, {b: build_agent(specs[b]) for b in g["seats"]}).play(
            MatchKey(11, 22, 3, 1), g["seats"], 60)
        assert res.deltas == g["deltas"] and res.hands_played == g["hands"], mode


# ------------------------------------------------------------------ frozen fields
def test_frozen_fields_enforced():
    prof = load_profile("publication")
    for mode in ("aof4",):
        for f in ("spread", "crowded_cutoff", "style_diverse"):
            assert prof.field(mode, f).field_hash == prof.frozen_hash(mode, f)
    for mode in ("nlhe4", "nlhe6"):  # NLHE fields await re-calibration on fhr3b_heuristic
        with pytest.raises((FieldNotFrozenError, FileNotFoundError)):
            prof.field(mode, "spread")
