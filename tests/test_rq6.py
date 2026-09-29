"""RQ6 correctness gates: all-in EV edge cases, estimator isolation from the game, toy-game
oracles for PVAT's MIVAT/AIVAT, value-function fitting guards, and estimator provenance.

Toy-game oracle: PVAT's own tests are stubs, so its MIVAT/AIVAT classes are checked here
against an independent, hand-written implementation of the AIVAT formula (Burch et al.
2018; the same decomposition NoRegrets' src/aivat.rs uses: realized payoff plus one
zero-mean correction per known-distribution event) on a small fully enumerable game.
"""

from __future__ import annotations

import hashlib
import json
from itertools import combinations
from types import SimpleNamespace

import numpy as np
import pytest
from pvat import AIVAT, MIVAT

from fhr3.agents.heuristic import HeuristicAgent
from fhr3.configs.experiment import RNGConfig, load_config
from fhr3.estimators.allin_ev import AllInEVEstimator, expected_payoff
from fhr3.estimators.vat import FEATURES
from fhr3.eval.matched import MatchedBlockSpec, run_matched_block
from fhr3.eval.runner import BlockSimulator
from fhr3.games.base import STANDARD_DECK, Action

from conftest import adapter, make_cfg


# ------------------------------------------------------------------ all-in EV edge cases
def _hand(holes, stacks, script, runout):
    """Play a scripted hand; ``runout`` = [burn, f1, f2, f3, burn, turn, burn, river]."""
    ad = adapter(len(holes))
    hole = [h[i:i + 2] for h in holes for i in (0, 2)]
    rest = [c for c in STANDARD_DECK if c not in set(hole) | set(runout)]
    h = ad.new_hand(ad.deal_from_deck(hole + list(runout) + rest), starting_stacks=stacks)
    for a in script:
        h.apply(a)
    assert h.is_terminal()
    return h.outcome()


def _check_flop_allin_against_pokerkit(holes, stacks, script, flop, burn1="2d"):
    """Exact all-in EV (turn + river to come) == average of PokerKit-played payoffs over
    every turn/river completion, for every seat (side pots, uncalled bets, odd chips)."""
    base = [burn1, *flop]
    filler = [c for c in STANDARD_DECK if c not in {c for h in holes for c in (h[:2], h[2:])} | set(base)]
    snap = _hand(holes, stacks, script, base + [filler[0], filler[1], filler[2], filler[3]]).allin_snapshot
    assert snap is not None and snap.board == tuple(flop)
    pool = [c for c in STANDARD_DECK if c not in snap.dead]
    completions = list(combinations(pool, 2))
    totals = np.zeros(len(holes))
    for turn, river in completions:
        burns = [c for c in pool if c not in (turn, river)][:2]
        o = _hand(holes, stacks, script, base + [burns[0], turn, burns[1], river])
        totals += o.payoffs_chips
    for seat in range(len(holes)):
        ev, method = expected_payoff(snap, seat, "holdem", 10_000, 1, None)
        assert method == "exact"
        assert ev == pytest.approx(totals[seat] / len(completions), abs=1e-9)
    return snap


def test_allin_ev_multiway_nested_side_pots_and_uncalled_bet_on_flop():
    # 4-max, stacks 100/60/30/10 BB. Preflop limped; flop: SB jams, everyone calls
    # all-in -> main pot + two side pots, and 40 BB of SB's jam is uncalled.
    holes = ["AsKs", "QhQd", "JcTc", "7h7d"]
    stacks = (10_000, 6_000, 3_000, 1_000)
    script = [Action.check_call()] * 4 + [Action.raise_to(9_900)] + [Action.check_call()] * 3
    snap = _check_flop_allin_against_pokerkit(holes, stacks, script, ("9c", "8d", "2h"))
    assert len(snap.pots) >= 3 and all(snap.live)


def test_allin_ev_folded_dead_money_odd_pot_and_chops():
    # 3-max: BTN raises to 3.01 BB (odd chips), both blinds call; flop: BB bets, BTN folds
    # (dead money), SB jams, BB calls. AK vs AK chops often -> odd-chip split rule.
    holes = ["AsKd", "AhKc", "7s2d"]
    stacks = (10_000, 10_000, 10_000)
    script = [Action.raise_to(301), Action.check_call(), Action.check_call(),
              Action.check_call(), Action.raise_to(500), Action.fold(), Action.raise_to(9_699), Action.check_call()]
    snap = _check_flop_allin_against_pokerkit(holes, stacks, script, ("Qc", "Jd", "3h"))
    assert snap.live == (True, True, False) and sum(snap.contributed) % 2 == 1


def test_river_allin_has_no_runout_and_estimate_is_realized():
    holes, stacks = ["AsKd", "QcQh"], (10_000, 10_000)
    # heads-up: SB(0) is the button; preflop SB calls, BB checks; flop/turn checked; river jam + call
    script = [Action.check_call(), Action.check_call()] + [Action.check_call()] * 4 + [Action.raise_to(9_900), Action.check_call()]
    o = _hand(holes, stacks, script, ["2d", "9c", "8d", "2h", "3d", "4c", "5d", "Td"])
    assert o.allin_snapshot is None  # no board cards left: nothing to integrate out
    ctx = SimpleNamespace(outcome=o, candidate_position=0, key=("hand", 1, 0))
    assert AllInEVEstimator("holdem").estimate(ctx) == float(o.payoffs_chips[0])


# ------------------------------------------------------------------ isolation from the game
def _spec(b):
    return MatchedBlockSpec("e", "c", "p", "ph", 23, b, RNGConfig())


def _refs():
    return [HeuristicAgent(f"r{i}", s) for i, s in enumerate(["tight", "neutral", "loose", "aggressive", "neutral"])]


def test_estimator_settings_do_not_change_cards_actions_or_raw_d():
    """Estimator RNG is a separate keyed stream: MC sample counts (or disabling the
    estimator) leave deals, actions and raw D bit-identical."""
    ad = adapter(6, 20)
    runs = {}
    for label, est in (("none", []), ("mc20", [AllInEVEstimator("holdem", mc_samples=20)]),
                       ("mc300", [AllInEVEstimator("holdem", mc_samples=300)]),
                       ("salt", [AllInEVEstimator("holdem", mc_samples=20, salt=9)])):
        runs[label] = [run_matched_block(_spec(b), ad, HeuristicAgent("A", "aggressive"),
                                         HeuristicAgent("B", "loose"), _refs(), estimators=est) for b in range(30)]
    base = runs["none"]
    for label, rs in runs.items():
        for r0, r in zip(base, rs, strict=True):
            assert r.D == r0.D and r.decision_count == r0.decision_count
            assert [(h.payoff_bb, h.allin_runout) for h in r.hands] == [(h.payoff_bb, h.allin_runout) for h in r0.hands]
    # the estimator itself did change (preflop all-ins use Monte Carlo runouts)
    assert any(h.estimates_bb["allin_ev"] != g.estimates_bb["allin_ev"]
               for r, q in zip(runs["mc20"], runs["mc300"], strict=True)
               for h, g in zip(r.hands, q.hands, strict=True))


def test_rq6_configs_reproduce_raw_d_of_their_reference_configs():
    """Same game / agents / seed: an estimator config's raw D equals the reference config's D."""
    pairs = [("configs/rq6/nlhe_6max_20bb_allin.yaml", "configs/nlhe_6max_20bb.yaml", "p2-neutral-vs-tight"),
             ("configs/rq6/aof_4max_8bb_allin.yaml", "configs/aof_4max_8bb.yaml", "p1-prodv2-vs-blend10")]
    for est_path, ref_path, pid in pairs:
        ce, cr = load_config(est_path), load_config(ref_path)
        assert ce.root_seed == cr.root_seed and ce.game == cr.game and ce.rng == cr.rng
        se, sr = BlockSimulator(ce, ce.pairing(pid)), BlockSimulator(cr, cr.pairing(pid))
        assert se.pairing.pairing_hash == sr.pairing.pairing_hash
        for b in (0, 1, 2):
            re_, rr = se.run(b), sr.run(b)
            assert re_.D == rr.D and re_.estimator_D("allin_ev") is not None


# ------------------------------------------------------------------ toy-game oracle for PVAT
# Kuhn-like game: chance deals hero card c in {0,1,2}; chance deals villain card o != c;
# hero bets (b) or checks (k) with a known policy; after a bet villain calls (c) or folds (f)
# with a known policy. Showdown: higher card wins 1 (check) or 2 (bet-call); fold: hero +1.
HERO_BET = {0: 0.3, 1: 0.5, 2: 0.9}
VILL_CALL = {0: 0.0, 1: 0.5, 2: 1.0}  # card 0 always folds, card 2 always calls: deterministic nodes


def _children(h):
    """(player, [(action, prob)]) at history h, or None if terminal."""
    if len(h) == 0:
        return "chance", [(c, 1 / 3) for c in range(3)]
    if len(h) == 1:
        return "chance", [(o, 1 / 2) for o in range(3) if o != h[0]]
    if len(h) == 2:
        p = HERO_BET[h[0]]
        return "hero", [("b", p), ("k", 1 - p)]
    if len(h) == 3 and h[2] == "b":
        p = VILL_CALL[h[1]]
        return "villain", [("c", p), ("f", 1 - p)]
    return None


def _utility(h):
    win = 1 if h[0] > h[1] else -1
    if h[2] == "k":
        return win
    return 1 if h[3] == "f" else 2 * win


def _terminals(h=()):
    """Every realizable terminal history with its probability (zero-probability paths excluded)."""
    node = _children(h)
    if node is None:
        return [(h, 1.0)]
    out = []
    for a, p in node[1]:
        if p > 0:
            out += [(t, p * q) for t, q in _terminals(h + (a,))]
    return out


def _exact_value(h):
    node = _children(h)
    return _utility(h) if node is None else sum(p * _exact_value(h + (a,)) for a, p in node[1])


def _prob(h):
    return dict(_children(h[:-1])[1])[h[-1]]


PVAT_FUNCS = dict(
    terminal_value_function=_utility,
    actions_function=lambda h: [a for a, _ in _children(h)[1]],
    probability_function=_prob,
    made_function=lambda h, a: h + (a,),
    prefixes_function=lambda z: [(z[:i], z[i]) for i in range(len(z))],
    player_function=lambda h: _children(h)[0],
)


def _pvat(kind):
    if kind == "mivat":
        return MIVAT(chance="chance", **PVAT_FUNCS)
    return AIVAT(mapped_terminal_histories_function=lambda z: [z], terminal_probability_function=lambda z: 1.0,
                 corrected_players={"chance", "hero", "villain"}, mapped_histories_function=lambda h: [h], **PVAT_FUNCS)


def _reference(kind, v, z):
    """Independent implementation: u(z) + sum over corrected prefixes of E_a[v(ha)] - v(h a_z)."""
    corrected = {"chance"} if kind == "mivat" else {"chance", "hero", "villain"}
    est = _utility(z)
    for i in range(len(z)):
        player, opts = _children(z[:i])
        if player in corrected:
            est += sum(p * v(z[:i] + (a,)) for a, p in opts) - v(z[:i + 1])
    return est


def _poor_v(h):  # deliberately bad value function: deterministic noise
    return (int(hashlib.sha256(repr(h).encode()).hexdigest()[:8], 16) % 1000) / 100.0 - 5.0


@pytest.mark.parametrize("kind", ["mivat", "aivat"])
@pytest.mark.parametrize("v", [_exact_value, _poor_v, lambda h: 0.0], ids=["exact", "poor", "zero"])
def test_pvat_matches_independent_reference_and_is_exactly_unbiased(kind, v):
    est = _pvat(kind)
    zs = _terminals()
    assert sum(p for _, p in zs) == pytest.approx(1.0)
    true = sum(p * _utility(z) for z, p in zs)
    vals = []
    for z, p in zs:
        e = float(est(v, z))
        assert e == pytest.approx(_reference(kind, v, z), abs=1e-12)
        vals.append((e, p))
    assert sum(e * p for e, p in vals) == pytest.approx(true, abs=1e-12)  # exact mean preservation


def test_exact_value_function_collapses_variance_and_poor_one_inflates_it():
    zs = _terminals()

    def var(kind, v):
        vals = [(float(_pvat(kind)(v, z)), p) for z, p in zs]
        m = sum(e * p for e, p in vals)
        return sum(p * (e - m) ** 2 for e, p in vals)

    raw = var("mivat", lambda h: 0.0)
    assert var("aivat", _exact_value) == pytest.approx(0.0, abs=1e-20)  # every event corrected
    assert 0 < var("mivat", _exact_value) < raw  # chance only: action variance remains
    assert var("aivat", _poor_v) > raw  # a bad value function costs variance, never bias


def test_deterministic_known_policy_action_generates_zero_correction():
    est = _pvat("aivat")
    for v in (_exact_value, _poor_v):
        for z, _ in _terminals():
            if len(z) == 4 and z[1] in (0, 2):  # villain's card 0 / 2: fold / call with probability 1
                h = z[:3]
                corr = sum(p * v(h + (a,)) for a, p in _children(h)[1] if p > 0) - v(z)
                assert corr == pytest.approx(0.0, abs=1e-12)
                # and PVAT's full sum equals the reference without that node
                assert float(est(v, z)) == pytest.approx(_reference("aivat", v, z), abs=1e-12)


def test_linear_value_function_path_equals_scalar_path():
    """FHR3 evaluates theta . (PVAT correction sum in feature space); for a linear v this
    must equal PVAT's scalar correction sum with v = theta . phi."""
    rng = np.random.default_rng(3)
    theta = rng.normal(size=3)

    def phi(h):
        x = np.array([len(h), _exact_value(h), _poor_v(h)], dtype=float)
        return x

    est = _pvat("aivat")
    for z, _ in _terminals():
        feat = est.get_correction_term_sum(phi, z)
        scalar = est.get_correction_term_sum(lambda h: float(theta @ phi(h)), z)
        assert float(theta @ np.asarray(feat)) == pytest.approx(float(scalar), abs=1e-9)


# ------------------------------------------------------------------ value-function fitting guards
def _fit(tmp_path, name, seed=77, blocks=(0, 2)):
    from fhr3.estimators.vat_fit import fit_value_function

    cfg = make_cfg()
    return fit_value_function(cfg, ["ab"], blocks[0], blocks[1], seed, "aivat", 4, tmp_path / name)


def test_vat_fit_is_deterministic_and_rejects_evaluation_seed(tmp_path):
    m1, m2 = _fit(tmp_path, "a.json"), _fit(tmp_path, "b.json")
    assert m1["theta"] == m2["theta"] and m1["sha256"] == m2["sha256"]  # byte-identical artifact
    assert (tmp_path / "a.created.json").exists()  # timestamp kept outside the pinned bytes
    meta = json.loads((tmp_path / "a.json").read_text())
    assert meta["training_root_seed"] == 77 and meta["features"] == list(FEATURES)
    assert meta["method_version"] and meta["pvat_version"]
    with pytest.raises(ValueError, match="differ"):
        _fit(tmp_path, "c.json", seed=make_cfg().root_seed)


def test_modified_artifact_under_old_hash_is_refused(tmp_path):
    from fhr3.estimators import build_estimators

    m = _fit(tmp_path, "vf.json")
    path = tmp_path / "vf.json"
    opts = {"aivat": {"value_function": str(path), "value_function_sha256": m["sha256"]}}
    assert build_estimators(opts, adapter(), root_seed=make_cfg().root_seed)  # pinned + different seed: accepted
    meta = json.loads(path.read_text())
    meta["theta"][0] += 1e-9
    path.write_text(json.dumps(meta, indent=1, sort_keys=True))
    with pytest.raises(ValueError, match="sha256"):
        build_estimators(opts, adapter(), root_seed=make_cfg().root_seed)


# ------------------------------------------------------------------ provenance
def test_estimator_provenance_pins_settings_versions_and_refuses_silent_change(tmp_path):
    from fhr3.io.store import IncompatibleResultsError, ensure_locks

    base = make_cfg(estimators={"allin_ev": {"mc_samples": 50}})
    prov = base.estimator_provenance["estimators"]["allin_ev"]
    assert prov["method_version"] and prov["settings"]["mc_samples"] == 50 and "rng_stream" in prov
    assert make_cfg(estimators={"allin_ev": {"mc_samples": 60}}).estimator_config_hash != base.estimator_config_hash
    assert make_cfg().estimator_config_hash is None and make_cfg().config_hash == base.config_hash  # raw D unaffected
    ensure_locks(tmp_path, base, [base.pairing("ab")])
    lock = json.loads(next(tmp_path.rglob("experiment.lock.json")).read_text())
    assert lock["estimator_config_hash"] == base.estimator_config_hash
    with pytest.raises(IncompatibleResultsError):
        changed = make_cfg(estimators={"allin_ev": {"mc_samples": 60}})
        ensure_locks(tmp_path, changed, [changed.pairing("ab")])
    raw = make_cfg(experiment_id="raw-exp")
    ensure_locks(tmp_path, raw, [raw.pairing("ab")])
    raw_lock = json.loads((tmp_path / "raw-exp" / "experiment.lock.json").read_text())
    assert "estimator_provenance" not in raw_lock  # raw-only locks keep their historical shape
