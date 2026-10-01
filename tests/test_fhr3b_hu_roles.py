"""FHR3B-local heuristic family: correct heads-up blind roles, multiway behaviour unchanged."""

from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path

import pytest
import yaml

from fhr3.agents import AgentSpec
from fhr3.agents import build_agent as fhr3a_build_agent
from fhr3.agents.heuristic import HeuristicAgent
from fhr3.games import make_adapter
from fhr3.games.base import STANDARD_DECK, ActionKind, GameConfig
from fhr3.rng import KeyedStream
from fhr3.tournament.agents import FHR3BHeuristicAgent, blind_roles, build_agent
from fhr3.tournament.experiments import FieldNotFrozenError, load_profile
from fhr3.tournament.fields import FHR3B_CONFIGS, load_field, load_mode
from fhr3.tournament.match import MatchKey, PokerMatchPlayer

REPO = Path(__file__).resolve().parents[1]
RETIRED = FHR3B_CONFIGS / "fields/retired/hu-role-bug"


def _hu_hand(seed: int = 1):
    a = make_adapter(GameConfig("nlhe", 2, 100.0))
    return a.new_hand(a.deal_from_deck(KeyedStream("hu", seed).shuffle(STANDARD_DECK)))


def _dist(agent, obs, legal):
    return {(a.kind, a.amount): p for a, p in agent.action_distribution(obs, legal)}


def test_blind_roles():
    assert blind_roles(1, 2) == (True, False)  # heads-up: seat 1 = button = SB
    assert blind_roles(0, 2) == (False, True)  # heads-up: seat 0 = BB
    for k in (3, 4, 6):
        assert blind_roles(0, k) == (True, False) and blind_roles(1, k) == (False, True)
        assert blind_roles(k - 1, k) == (False, False)


def test_engine_heads_up_convention_matches_roles():
    h = _hu_hand()
    obs = h.observation(h.actor())
    assert h.actor() == 1 and obs.bets == (100, 50)  # button/SB (seat 1) posts 50 and acts first
    assert blind_roles(1, 2)[0]


def test_hu_button_uses_small_blind_open_logic():
    agent = FHR3BHeuristicAgent("b", style="neutral")
    for seed in range(30):
        h = _hu_hand(seed)
        obs, legal = h.observation(1), h.legal_actions()
        p = agent.p
        expected_raise = agent._in_range(agent.preflop_strength(obs), p.sb_open_pct * p.looseness,
                                         p.preflop_temperature)
        d = _dist(agent, obs, legal)
        p_raise = sum(v for (k, _), v in d.items() if k is ActionKind.BET_RAISE)
        assert p_raise == pytest.approx(expected_raise)
        bug = HeuristicAgent("b", style="neutral")  # FHR3A: BB-vs-limp iso range for the button
        bug_raise = sum(v for (k, _), v in _dist(bug, obs, legal).items() if k is ActionKind.BET_RAISE)
        assert bug_raise == pytest.approx(bug._in_range(bug.preflop_strength(obs), p.threebet_pct * 2 * p.looseness,
                                                        p.preflop_temperature))


def test_hu_big_blind_uses_bb_defence_facing_a_raise():
    from fhr3.games.base import Action

    agent = FHR3BHeuristicAgent("b", style="neutral")
    p = agent.p
    checked = 0
    for seed in range(40):
        h = _hu_hand(seed)
        h.apply(Action.raise_to(250))  # button opens
        if h.is_terminal() or h.actor() != 0:
            continue
        obs, legal = h.observation(0), h.legal_actions()
        s = agent.preflop_strength(obs)
        cont = agent._in_range(s, max(p.bb_defend_pct, p.threebet_pct * p.aggression) * p.looseness,
                               p.preflop_temperature)
        d = _dist(agent, obs, legal)
        assert 1 - d.get((ActionKind.FOLD, None), 0.0) == pytest.approx(min(cont, 1.0))
        checked += 1
    assert checked > 30


def test_multiway_decisions_identical_to_fhr3a():
    """3+ handed: every decision distribution equals FHR3A's (same params), across many real states."""
    pool = load_field(FHR3B_CONFIGS / "fields/nlhe6/pool.json")
    specs = pool.specs()
    ids = sorted(specs)[::16][:6]
    compared = Counter()

    class Cmp:
        def __init__(self, spec):
            self.new = build_agent(spec)
            self.old = fhr3a_build_agent(AgentSpec(spec.agent_id, "heuristic", spec.params))
            self.agent_id, self.version = self.new.agent_id, self.new.version

        def act(self, obs, legal, rng):
            if obs.player_count > 2:
                assert self.new.action_distribution(obs, legal) == self.old.action_distribution(obs, legal)
                compared["multiway"] += 1
            return self.new.act(obs, legal, rng)

    m = load_mode("nlhe6")
    PokerMatchPlayer(m.game, m.stack_policy, {b: Cmp(specs[b]) for b in ids}).play(MatchKey(3, 3, 1, 0), ids, 150)
    assert compared["multiway"] > 1000


def test_hu_pathology_disappears():
    """Behavioural smoke: the heads-up button no longer folds ~88% preflop."""
    m = load_mode("nlhe4")
    new_specs = load_field(FHR3B_CONFIGS / "fields/nlhe4/pool.json").specs()
    old_specs = load_field(RETIRED / "nlhe4/pool.json").specs()
    rates = {}
    for label, specs, builder in (("old", old_specs, fhr3a_build_agent), ("new", new_specs, build_agent)):
        acts = Counter()

        class Rec:
            def __init__(self, a):
                self.a, self.agent_id, self.version = a, a.agent_id, a.version

            def act(self, obs, legal, rng):
                a = self.a.act(obs, legal, rng)
                if obs.player_count == 2 and obs.street == 0 and obs.seat == 1 and not obs.history:
                    acts[a.kind] += 1
                return a

        ids = sorted(specs)
        for t in range(4):
            seats = ids[t * 4:(t + 1) * 4]
            PokerMatchPlayer(m.game, m.stack_policy, {b: Rec(builder(specs[b])) for b in seats}).play(
                MatchKey(5, 5, 1, t), seats, 400)
        n = sum(acts.values())
        rates[label] = (acts[ActionKind.FOLD] / n, n)
    assert rates["old"][0] > 0.8  # the bug, reproduced on the retired agents
    assert rates["new"][0] < rates["old"][0] - 0.15  # gone with corrected roles
    assert rates["new"][1] > 50


def test_pools_keep_the_same_96_parameter_vectors():
    for mode in ("nlhe4", "nlhe6"):
        old = {b["bot_id"]: b for b in load_field(RETIRED / f"{mode}/pool.json").bots}
        new = {b["bot_id"]: b for b in load_field(FHR3B_CONFIGS / f"fields/{mode}/pool.json").bots}
        assert old.keys() == new.keys() and len(new) == 96
        assert all(old[k]["params"] == new[k]["params"] and old[k]["meta"] == new[k]["meta"] for k in old)
        assert {b["kind"] for b in new.values()} == {"fhr3b_heuristic"}
        assert all(b["version"].startswith("fhr3b-heuristic-1.0.0+") for b in new.values())
    a4 = {b["params"]["style"] if "style" in b["params"] else None for b in
          load_field(FHR3B_CONFIGS / "fields/nlhe4/pool.json").bots}
    assert a4  # same archetype construction


def test_old_nlhe_freezes_revoked_and_aof_untouched(tmp_path):
    prof = load_profile("publication")
    rev = prof.revoked_hashes()
    for h in ("16df070db91a53bd", "a845c2fcf1b2ed33", "5c83ad4268c37bdc", "479125f8aa79e5a6",
              "e95024951ef40186", "289e4bdb8c9f99bc", "0a9914d3f074b147", "e1d187eb0b4551c2"):
        assert h in rev
    frozen = yaml.safe_load((FHR3B_CONFIGS / "fields/FROZEN.yaml").read_text())["fields"]
    assert set(frozen) == {"aof4"}
    assert frozen["aof4"] == {"spread": "db5912d65a47b215", "crowded_cutoff": "b9709c10c5aef403",
                              "style_diverse": "195ceda2edb24052"}
    # even a deliberate re-listing of a revoked field is refused
    root = tmp_path / "cfg"
    shutil.copytree(FHR3B_CONFIGS, root)
    shutil.copy(RETIRED / "nlhe6/spread.json", root / "fields/nlhe6/spread.json")
    reg = yaml.safe_load((root / "fields/FROZEN.yaml").read_text())
    reg["fields"]["nlhe6"] = {"spread": "16df070db91a53bd"}
    (root / "fields/FROZEN.yaml").write_text(yaml.safe_dump(reg))
    p2 = load_profile("publication", config_root=root)
    with pytest.raises(FieldNotFrozenError, match="REVOKED"):
        p2.field("nlhe6", "spread")


def test_hu_tournament_replays_exactly(tmp_path):
    from fhr3.tournament.batch import run_cell
    from fhr3.tournament.replay import check_replay, validate_cell

    prof = load_profile("smoke", tmp_path)
    cell = prof.cell("nlhe4", "smoke12")
    run_cell(cell, tmp_path, range(2), progress=False)
    assert validate_cell(tmp_path, cell, [0, 1])["validated"] == 2
    assert check_replay(tmp_path, cell, [0, 1])["replayed_exactly"] == 2
    assert {b["kind"] for b in cell.field.bots} == {"fhr3b_heuristic"}


def test_retired_calibrations_marked():
    for d in (REPO / "results/fhr3b/calibration").glob("nlhe*-pool.H400.pool-calibration.*"):
        if d.name.endswith(("698094ac", "4d3e14b6")):
            assert (d / "RETIRED.txt").exists()
    assert json.loads((RETIRED / "nlhe6/spread.json").read_text())["field_hash"] == "16df070db91a53bd"
