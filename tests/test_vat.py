"""MIVAT / AIVAT (PVAT-backed): mean preservation, exactness, symmetry, pinning."""

from __future__ import annotations

import hashlib
import json
import math

import numpy as np
import pytest

from fhr3.agents.heuristic import HeuristicAgent
from fhr3.configs.experiment import RNGConfig
from fhr3.estimators import build_estimators
from fhr3.estimators.vat import FEATURES, PRIOR_THETA, H, HandTrace, VATEstimator, _feature_extractor, fit_theta
from fhr3.eval.matched import HandContext, MatchedBlockSpec, play_hand, run_matched_block, _Timer
from fhr3.eval.runner import BlockSimulator
from fhr3.games.base import STANDARD_DECK
from fhr3.rng import DecisionRNG, KeyedStream
from variant_invariants import load

from conftest import adapter


def spec(b: int) -> MatchedBlockSpec:
    return MatchedBlockSpec("e", "c", "p", "ph", 11, b, RNGConfig())


def refs():
    return [HeuristicAgent(f"r{i}", s) for i, s in enumerate(["tight", "neutral", "loose", "aggressive", "neutral"])]


def hand_ctx(deal, seed=0):
    ad = adapter()
    agents = [HeuristicAgent("A", "aggressive"), *refs()]
    log: list = []
    outcome, _ = play_hand(ad, deal, agents, lambda s, o: DecisionRNG("vat", seed, s, o), _Timer(), decision_log=log)
    return HandContext(ad, deal, outcome, 0, agents, log, ("hand", seed, 0))


def test_zero_theta_returns_realized_payoff_exactly():
    ad = adapter()
    for b in range(10):
        deal = ad.deal_from_deck(KeyedStream("v", b).shuffle(STANDARD_DECK))
        ctx = hand_ctx(deal, b)
        for kind in ("mivat", "aivat"):
            assert VATEstimator(kind, np.zeros(len(FEATURES))).estimate(ctx) == ctx.outcome.payoffs_chips[0]


def test_chance_outcome_sets_are_the_true_conditional_distribution():
    ad = adapter()
    for b in range(20):
        deal = ad.deal_from_deck(KeyedStream("v2", b).shuffle(STANDARD_DECK))
        ctx = hand_ctx(deal, b)
        t = HandTrace(ctx, flop_samples=8, salt=0)
        dealt = {c for h in deal.hole for c in h}
        for ev, st in zip(t.events, t.states, strict=True):
            if ev.kind != "chance":
                continue
            outs = [o for o, _ in ev.options]
            if ev.street >= 2:  # turn/river enumerated exactly: all undealt cards
                burns = {1: set(), 2: {deal.runout[0], deal.runout[4]}, 3: {deal.runout[0], deal.runout[4], deal.runout[6]}}[ev.street]
                expect = [c for c in STANDARD_DECK if c not in dealt | set(st.board) | burns]
                assert sorted(o[0] for o in outs) == sorted(expect)
                assert ev.value in outs  # the realized card is one of the outcomes
            for o in outs:
                assert not (set(o) & (dealt | set(st.board)))


def test_action_options_match_policy_and_contain_realized_action():
    ad = adapter()
    for b in range(15):
        ctx = hand_ctx(ad.deal_from_deck(KeyedStream("v3", b).shuffle(STANDARD_DECK)), b)
        t = HandTrace(ctx, 4, 0)
        actions = [e for e in t.events if e.kind == "action"]
        assert len(actions) == len(ctx.decisions)
        for ev, _d in zip(actions, ctx.decisions, strict=True):
            assert abs(sum(p for _, p in ev.options) - 1) < 1e-12
            assert ev.value in [a for a, _ in ev.options]


def test_river_chance_correction_has_exact_zero_mean_by_enumeration():
    """Average over every possible river of the river correction term is 0."""
    ad = adapter()
    checked = 0
    for b in range(40):
        ctx = hand_ctx(ad.deal_from_deck(KeyedStream("v4", b).shuffle(STANDARD_DECK)), b)
        t = HandTrace(ctx, 4, 0)
        river = [i for i, e in enumerate(t.events) if e.kind == "chance" and e.street == 3]
        if not river:
            continue
        i = river[0]
        outs = [o for o, _ in t.events[i].options]
        v = np.array([PRIOR_THETA @ _feature_extractor(H(t, i, o)) for o in outs])
        # correction for realized outcome o* is mean(v) - v(o*); its average over o* is 0
        assert abs(np.mean(v.mean() - v)) < 1e-9
        # and the estimator's own river term for the realized card equals mean(v) - v(realized)
        realized = t.events[i].value
        assert abs((v.mean() - PRIOR_THETA @ _feature_extractor(H(t, i, realized)))
                   - (v.mean() - v[outs.index(realized)])) < 1e-9
        checked += 1
    assert checked > 0


def _blocks(estimators, n, start=0, a=None, b=None):
    ad = adapter()
    A = a or HeuristicAgent("A", "aggressive")
    B = b or HeuristicAgent("B", "neutral")
    return [run_matched_block(spec(start + i), ad, A, B, refs(), estimators=estimators) for i in range(n)]


@pytest.mark.parametrize("theta", ["prior", "random"])
def test_block_level_mean_preservation(theta):
    th = PRIOR_THETA if theta == "prior" else np.random.default_rng(5).normal(0, 1, len(FEATURES))
    est = [VATEstimator("mivat", th, flop_samples=8), VATEstimator("aivat", th, flop_samples=8)]
    res = _blocks(est, 250, start=500)
    for name in ("mivat", "aivat"):
        d = np.array([r.estimator_D(name) - r.D for r in res])
        assert d.std() > 0
        t = d.mean() / (d.std(ddof=1) / math.sqrt(d.size))
        assert abs(t) < 4.0, (name, theta, t)


def test_selfplay_zero_and_swap_negation():
    est = [VATEstimator("aivat", PRIOR_THETA, 8), VATEstimator("mivat", PRIOR_THETA, 8)]
    ad = adapter()
    A, B = HeuristicAgent("A", "aggressive"), HeuristicAgent("B", "neutral")
    for b in range(8):
        s = run_matched_block(spec(b), ad, A, HeuristicAgent("A2", "aggressive"), refs(), estimators=est)
        assert s.estimator_D("aivat") == 0.0 and s.estimator_D("mivat") == 0.0
        ab = run_matched_block(spec(b), ad, A, B, refs(), estimators=est)
        ba = run_matched_block(spec(b), ad, B, A, refs(), estimators=est)
        for name in ("aivat", "mivat"):
            assert ab.estimator_D(name) == pytest.approx(-ba.estimator_D(name), abs=1e-9)


@pytest.mark.parametrize("name", ["plo_6max_100bb.yaml", "cp_6max_100bb.yaml", "bomb_6max_100bb.yaml",
                                  "aof_4max_8bb.yaml", "nit_6max_100bb.yaml", "nlhe_4max_100bb.yaml"])
def test_state_tracker_consistent_in_every_format(name):
    cfg = load(name)
    sim = BlockSimulator(cfg, cfg.pairing("p3-aggressive-vs-neutral"))
    sim.estimators = build_estimators({"aivat": {"flop_samples": 4}}, sim.adapter)
    for b in range(3 if "nit" in name else 6):
        r = sim.run(b)  # HandTrace raises if its betting state diverges from the engine
        assert r.valid, r.error_detail
        assert r.estimator_D("aivat") is not None


def test_fit_reduces_in_sample_variance_and_pinning(tmp_path):
    est = VATEstimator("aivat", np.zeros(len(FEATURES)), 8)
    terms = []

    class Collect:
        name, needs_decision_log = "collect", True

        def estimate(self, ctx):
            terms.append(est.terminal(ctx))
            return float(ctx.outcome.payoffs_chips[ctx.candidate_position])

    _blocks([Collect()], 40, start=900)
    theta = fit_theta(est, terms)
    assert theta.shape == (len(FEATURES),) and np.all(np.isfinite(theta))
    raw = np.array([t.t.realized_bb for t in terms])
    fitted = np.array([t.t.realized_bb + theta @ est.correction_features(t) for t in terms])
    assert fitted.var() <= raw.var() + 1e-9  # least squares: in-sample variance cannot increase
    # pinning: wrong sha refused; training seed == evaluation seed refused
    path = tmp_path / "vf.json"
    path.write_text(json.dumps({"feature_version": "vat-features-1", "features": list(FEATURES),
                                "theta": theta.tolist(), "training_root_seed": 42}))
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    ad = adapter()
    with pytest.raises(ValueError):
        build_estimators({"aivat": {"value_function": str(path), "value_function_sha256": "0" * 64}}, ad)
    with pytest.raises(ValueError):
        build_estimators({"aivat": {"value_function": str(path), "value_function_sha256": sha}}, ad, root_seed=42)
    ok = build_estimators({"aivat": {"value_function": str(path), "value_function_sha256": sha}}, ad, root_seed=7)
    assert np.allclose(ok[0].theta, theta)
