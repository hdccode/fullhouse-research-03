"""4-max AoF: legal actions, production-policy fidelity, aof-ml oracle, invariants.

The aof-ml tests (external oracle) run when ``AOF_ML_ROOT`` (default ~/aof-ml)
contains the aof-ml source; otherwise they are skipped.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from fhr3.agents.aof import (
    POSITIONS_4MAX,
    AoFPolicyAgent,
    allin_action,
    hand_class,
    load_policy,
    prior_actions,
)
from fhr3.games import make_adapter
from fhr3.games.base import STANDARD_DECK, Action, GameConfig, IllegalActionError
from fhr3.rng import KeyedStream
from variant_invariants import check_core_invariants, check_serial_parallel_parquet, load

AOF_ROOT = Path(os.environ.get("AOF_ML_ROOT", Path.home() / "aof-ml"))
POLICY_SRC = AOF_ROOT / "results/reference-diagnostics/aof-4max-reference-policy-4m-v2.json"


def aof():
    return make_adapter(GameConfig("aof", 4, 8))


def test_legal_actions_are_fold_or_all_in():
    ad = aof()
    h = ad.new_hand(ad.deal_from_deck(STANDARD_DECK))
    assert h.actor() == 2  # CO first
    la = h.legal_actions()
    assert la.can_fold and not la.can_check_call and la.raise_min == la.raise_max == 800
    with pytest.raises(IllegalActionError):
        h.apply(Action.check_call())  # no limping
    with pytest.raises(IllegalActionError):
        h.apply(Action.raise_to(300))  # no small raises
    h.apply(Action.raise_to(800))
    la = h.legal_actions()  # BTN facing a shove: fold or call all-in
    assert la.can_fold and la.can_check_call and la.raise_min is None and la.call_amount == 800
    h.apply(Action.check_call())
    h.apply(Action.fold())
    h.apply(Action.fold())
    assert h.is_terminal() and h.outcome().allin_snapshot is not None


def test_folded_around_bb_wins_blinds_without_acting():
    ad = aof()
    h = ad.new_hand(ad.deal_from_deck(STANDARD_DECK))
    for _ in range(3):
        h.apply(Action.fold())
    assert h.is_terminal() and h.outcome().payoffs_chips == (-50, 50, 0, 0)


def test_hand_class_and_policy_spot_checks():
    assert hand_class(("Ks", "As")) == "AKs" and hand_class(("2c", "7d")) == "72o" and hand_class(("Td", "Th")) == "TT"
    pol = load_policy("production-v2")
    assert len(pol["nodes"]) == 14 and all(len(n["p"]) == 169 for n in pol["nodes"].values())
    assert pol["by_key"][("CO", ())]["p"]["AA"] == 1.0
    assert pol["by_key"][("CO", ())]["p"]["72o"] == 0.0
    keys = set(pol["by_key"])
    # every reachable decision history exists in the policy
    for co in "FA":
        for btn in "FA":
            assert ("SB", (co, btn)) in keys
            for sb in "FA":
                if (co, btn, sb).count("A"):
                    assert ("BB", (co, btn, sb)) in keys


@pytest.mark.skipif(not POLICY_SRC.exists(), reason="aof-ml not available")
def test_vendored_policy_matches_aof_ml_source_exactly():
    raw = POLICY_SRC.read_bytes()
    pol = load_policy("production-v2")
    assert pol["provenance"]["source_file_sha256"] == hashlib.sha256(raw).hexdigest()
    src = json.loads(raw)
    nonfold = {n["decision_node_id"]: [a for a in n["legal_actions"] if a != "fold"][0] for n in src["nodes"]}
    for r in src["rows"]:
        assert pol["nodes"][r["decision_node_id"]]["p"][r["hand"]] == r["action_probabilities"][nonfold[r["decision_node_id"]]]


def _plan(position: str, prior: tuple[str, ...], hole: tuple[str, str], seed: int) -> bool:
    """Deterministic pseudo-random shove/call plan shared by both engines."""
    return KeyedStream("aof-plan", seed, position, "".join(prior), hand_class(hole)).random() < 0.45


@pytest.mark.skipif(not (AOF_ROOT / "src/aof_ml").exists(), reason="aof-ml not available")
@settings(max_examples=150, deadline=None)
@given(seed=st.integers(0, 2**31))
@example(seed=80397)  # three-way chop with 2 odd chips: engines differ only in odd-chip placement
def test_payoffs_match_aof_ml_simulator(seed):
    sys.path.insert(0, str(AOF_ROOT / "src"))
    from aof_ml.config import ProjectConfig
    from aof_ml.rules import Action as AofAction
    from aof_ml.simulator import AoFSimulator

    D = KeyedStream("aof-oracle-deck", seed).shuffle(STANDARD_DECK)

    class Plan:
        def act(self, observation, rng):
            prior = tuple("F" if d.action is AofAction.FOLD else "A" for d in observation.prior_decisions)
            return AofAction.ALL_IN if _plan(observation.position, prior, observation.hole_cards, seed) else AofAction.FOLD

    ref = AoFSimulator(ProjectConfig()).play_hand([Plan()] * 4, seed=1, deck=D)
    # aof-ml deals one card at a time from the SB; map into FHR3's per-seat layout
    ours_deck = [D[0], D[4], D[1], D[5], D[2], D[6], D[3], D[7], *D[8:]]
    ad = aof()
    h = ad.new_hand(ad.deal_from_deck(ours_deck))
    while not h.is_terminal():
        obs, la = h.observation(h.actor()), h.legal_actions()
        shove = _plan(POSITIONS_4MAX[obs.seat], prior_actions(obs), obs.hole_cards, seed)
        h.apply(allin_action(la) if shove or not la.can_fold else Action.fold())
    o = h.outcome()
    aof_by_name = dict(zip(("CO", "BTN", "SB", "BB"), ref.net_utility, strict=True))
    theirs = tuple(aof_by_name[POSITIONS_4MAX[s]] for s in range(4))
    if o.payoffs_chips != theirs:
        # Documented convention difference (docs/variants.md, AoF): in a split pot PokerKit
        # (FHR3's engine; replicated by the all-in EV estimator) gives the whole divmod
        # remainder to the first winner in seat order, aof-ml hands it out one chip at a time
        # along its odd_chip_order. Anything beyond redistributing < n_winners odd chips
        # among the same winners is a real mismatch.
        diff = [a - b for a, b in zip(o.payoffs_chips, theirs, strict=True)]
        winners = [s for s in range(4) if o.payoffs_chips[s] > -o.starting_stacks[s] and o.payoffs_chips[s] >= 0]
        assert sum(diff) == 0, (o.payoffs_chips, theirs)
        assert len(winners) >= 2 and all(diff[s] == 0 for s in range(4) if s not in winners), (o.payoffs_chips, theirs)
        assert max(abs(x) for x in diff) < len(winners), (o.payoffs_chips, theirs)


def test_policy_agent_rejects_wrong_game():
    ad = make_adapter(GameConfig("aof", 4, 10))
    h = ad.new_hand(ad.deal_from_deck(STANDARD_DECK))
    with pytest.raises(ValueError):
        AoFPolicyAgent("x").action_distribution(h.observation(h.actor()), h.legal_actions())


def test_aof_matched_invariants():
    check_core_invariants(load("aof_4max_8bb.yaml"), range(40))


def test_aof_serial_parallel_and_parquet(tmp_path):
    check_serial_parallel_parquet(load("aof_4max_8bb.yaml"), tmp_path)
