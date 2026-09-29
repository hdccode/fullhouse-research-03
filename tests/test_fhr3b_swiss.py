"""FHR3B: reconstructed 2026 Swiss pairing, standings, cut; protocol + sweep generators."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import random
from pathlib import Path

import pytest

from fhr3.tournament.protocol import (
    TournamentProtocol,
    budget_allocations,
    load_protocol,
    round_sweep,
)
from fhr3.tournament.swiss import (
    Standing,
    compute_standings,
    dense_ranks,
    initial_standings,
    positional_ranks,
    select_finalists,
    swiss_pairing,
    table_sizes_legal,
)

REF_DIR = Path(__file__).parent / "data/fhr3b/fullhouse_engine_a80b269"
CONFIGS = Path(__file__).resolve().parents[1] / "configs/fhr3b"


def _reference():
    spec = importlib.util.spec_from_file_location("fh2026_reference", REF_DIR / "reference_tournament.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_vendored_reference_is_byte_identical_to_pinned_hash():
    prov = json.loads((REF_DIR / "PROVENANCE.json").read_text())
    got = hashlib.sha256((REF_DIR / "reference_tournament.py").read_bytes()).hexdigest()
    assert got == prov["files"]["engine/tournament.py"]["sha256"]
    assert prov["commit"] == "a80b26957db5f5515d9273a15d1b73aadf8985db"


@pytest.mark.parametrize("seed", range(40))
def test_port_matches_vendored_reference(seed):
    """Golden test: standings, pairing and cut agree with the 2026 reference on random histories."""
    ref = _reference()
    rng = random.Random(seed)
    n = rng.randint(2, 40)
    table = rng.choice([2, 4, 6])
    bots = [f"b{i:02d}" for i in range(n)]
    results = []
    for _ in range(rng.randint(1, 5)):
        for b in bots:
            # coarse values force exact ties in cumulative delta and best match
            results.append({"bot_id": b, "chip_delta": rng.choice([-10000, -500, 0, 0, 500, 2000])})
    ref_st = ref.compute_standings(results)
    ours = compute_standings([(r["bot_id"], r["chip_delta"]) for r in results])
    assert [s["bot_id"] for s in ref_st] == [s.bot_id for s in ours]
    for a, b in zip(ref_st, ours, strict=True):
        assert (a["cumulative_delta"], a["matches_played"], a["best_match_delta"]) == (
            b.cumulative_delta, b.matches_played, b.best_match_delta)
    ref_tables = ref.swiss_pairing(ref_st, table_size=table)
    assert [[x["bot_id"] for x in t] for t in ref_tables] == swiss_pairing(ours, table)
    k = rng.randint(1, n)
    assert [x["bot_id"] for x in ref.select_finalists(ref_st, n=k)] == [s.bot_id for s in select_finalists(ours, k)]


def test_round_one_pairing_uses_input_order_like_reference():
    ref = _reference()
    order = ["e", "a", "d", "c", "b", "f", "g"]
    ref_tables = ref.swiss_pairing([{"bot_id": b, "cumulative_delta": 0} for b in order], table_size=3)
    assert [[x["bot_id"] for x in t] for t in ref_tables] == swiss_pairing(initial_standings(order), 3)
    assert swiss_pairing(initial_standings(order), 3) == [["e", "a", "d"], ["c", "b", "f", "g"]]


def test_stragglers_fold_into_last_table_and_small_field_is_one_table():
    st = initial_standings([f"b{i}" for i in range(15)])
    assert [len(t) for t in swiss_pairing(st, 6)] == [6, 9]
    assert [len(t) for t in swiss_pairing(initial_standings(["a", "b", "c"]), 6)] == [3]
    assert [len(t) for t in swiss_pairing(initial_standings([f"b{i}" for i in range(60)]), 6)] == [6] * 10
    assert [len(t) for t in swiss_pairing(initial_standings([f"b{i}" for i in range(60)]), 4)] == [4] * 15
    assert table_sizes_legal([[1] * 6, [1] * 9], 6, 15)
    assert not table_sizes_legal([[1] * 7, [1] * 8], 6, 15)


def test_tiebreak_order():
    results = [("a", 100), ("a", -100), ("b", 0), ("c", 50), ("c", -50), ("d", 0), ("e", -10), ("e", 10)]
    st = compute_standings(results)
    # all totals 0; b and d played 1 match (fewer = better); then best match desc (c 50 > e 10), then id
    assert [s.bot_id for s in st] == ["b", "d", "a", "c", "e"]
    assert positional_ranks(st) == {"b": 1, "d": 2, "a": 3, "c": 4, "e": 5}
    assert set(dense_ranks(st).values()) == {1}


def test_pairing_is_stable_for_equal_scores_after_tiebreak_sort():
    st = [Standing("z", 10, 1, 10), Standing("a", 10, 1, 5), Standing("m", 0, 1, 0)]
    assert swiss_pairing(st, 2) == [["z", "a", "m"]]


# ------------------------------------------------------------------ protocol
def _proto(**kw):
    base = dict(name="t", status="lab", table_size=6, hands_per_match=400, rounds=40, qualify_top_k=6)
    return TournamentProtocol(**(base | kw))


def test_reconstructed_protocol_file_is_reconstructed_not_exact():
    p = load_protocol(CONFIGS / "protocols/reconstructed_2026.yaml")
    assert p.status == "reconstructed" and p.name == "reconstructed_2026"
    assert (p.table_size, p.hands_per_match, p.qualify_top_k) == (6, 400, 64)
    assert p.stack_policy == "persistent_no_rebuy"
    assert p.source["commit"] == "a80b26957db5f5515d9273a15d1b73aadf8985db"


@pytest.mark.parametrize("field,value", [("rounds", 39), ("hands_per_match", 800), ("qualify_top_k", 7),
                                         ("table_size", 4), ("stack_policy", "reset_each_hand"),
                                         ("initial_order", "field_order")])
def test_protocol_hash_changes_with_every_result_relevant_field(field, value):
    assert _proto().protocol_hash != _proto(**{field: value}).protocol_hash


def test_protocol_notes_do_not_change_hash():
    assert _proto().protocol_hash == _proto(notes=("x",)).protocol_hash


def test_protocol_rejects_alternative_scoring_and_bad_values():
    with pytest.raises(ValueError):
        _proto(scoring="opponent_adjusted")
    with pytest.raises(ValueError):
        _proto(rounds=0)
    with pytest.raises(ValueError):
        _proto(stack_policy="rebuy")
    with pytest.raises(ValueError):
        _proto().check_variant("bomb_pot")  # persistent stacks undefined for bomb pots
    _proto(stack_policy="reset_each_hand").check_variant("bomb_pot")


def test_round_sweep():
    assert round_sweep(40) == [5, 10, 20, 30, 40]
    for r0 in (1, 3, 7, 12, 37, 64):
        s = round_sweep(r0)
        assert r0 in s and s == sorted(set(s)) and all(1 <= r <= r0 for r in s)


def test_budget_allocations_exact_for_40x400_and_flagged_when_inexact():
    al = budget_allocations(40, 400)
    assert [(a.rounds, a.hands_per_match, a.exact) for a in al] == [(10, 1600, True), (20, 800, True),
                                                                   (40, 400, True)]
    assert all(a.budget == 16000 for a in al)
    odd = budget_allocations(37, 400)
    assert odd[-1].exact and odd[-1].rounds == 37
    assert any(not a.exact for a in odd)
    for a in odd:
        assert abs(a.budget - 37 * 400) <= a.rounds  # within rounding of H
