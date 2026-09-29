"""RQ7 engine: method definitions, stream sharing, determinism, samplers, and the external
confseq oracle for the confidence-sequence boundary. All runs are tiny."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from fhr3.analysis.rq7 import (
    BootstrapSampler,
    Design,
    PermutationSampler,
    SyntheticSampler,
    evaluate,
    replicate_rng,
    run_cell,
    summarize,
)
from fhr3.analysis.sequential import asymp_radius


def design(**kw):
    base = dict(sampler="normal", true_mean=0.0, effect_d=None, sigma=1.0, reps=200, n_max=400, t_star=400.0,
                min_n=20, fixed_n=400, alpha=0.05, seed=5, checkpoints=(100, 400))
    base.update(kw)
    return Design(**base)


def by_method(rows, m):
    return [r for r in rows if r["method"] == m]


def test_fixed_single_look_is_nominal_and_peeking_inflates_it():
    d = design(reps=600)
    rows = run_cell(d, SyntheticSampler("normal"), workers=1)
    s = summarize(rows, d)
    assert 0.025 <= s["fixed"]["miscoverage"] <= 0.08  # one pre-committed look: ~alpha
    assert s["peek"]["miscoverage"] > s["fixed"]["miscoverage"] + 0.1  # repeated looks inflate it
    assert s["asymp"]["miscoverage"] <= 0.08  # time-uniform (asymptotic) coverage


def test_same_stream_for_all_methods_and_fixed_look_is_the_peek_interval_at_n():
    d = design(reps=150, true_mean=0.08)
    rows = run_cell(d, SyntheticSampler("normal", true_mean=0.08), workers=1)
    fixed, peek = {r["rep"]: r for r in by_method(rows, "fixed")}, {r["rep"]: r for r in by_method(rows, "peek")}
    for rep, f in fixed.items():
        if not f["censored"]:  # the peek interval at n = fixed_n is the fixed interval: it had decided by then
            assert 0 < peek[rep]["decision_time"] <= d.fixed_n
        assert f["width_at_400"] == pytest.approx(peek[rep]["width_at_400"])


def test_min_n_and_horizon_respected_and_censoring():
    d = design(reps=100, min_n=150, true_mean=0.3)
    rows = run_cell(d, SyntheticSampler("normal", true_mean=0.3), workers=1)
    for r in rows:
        if r["method"] == "fixed":
            assert r["decision_time"] in (-1, d.fixed_n)
        elif not r["censored"]:
            assert d.min_n <= r["decision_time"] <= d.n_max
        assert r["censored"] == (r["decision_time"] < 0)
    with pytest.raises(ValueError):
        run_cell(design(min_n=1), SyntheticSampler("normal"))
    with pytest.raises(ValueError):
        run_cell(design(fixed_n=500), SyntheticSampler("normal"))


def test_constant_zero_stream_always_contains_zero():
    d = design(reps=3)
    for r in evaluate(np.zeros((3, d.n_max)), d):
        assert not r["ever_miss_true_mean"] and r["censored"] and not r["wrong_decision"]


def test_deterministic_and_independent_of_workers_and_chunking():
    d = design(reps=40, sampler="t3")
    a = run_cell(d, SyntheticSampler("t3"), workers=1, chunk=7)
    b = run_cell(d, SyntheticSampler("t3"), workers=2, chunk=3)
    assert json.dumps(a) == json.dumps(b)  # NaN-safe exact comparison
    assert np.array_equal(replicate_rng(9, 4).standard_normal(5), replicate_rng(9, 4).standard_normal(5))
    assert not np.array_equal(replicate_rng(9, 4).standard_normal(5), replicate_rng(10, 4).standard_normal(5))
    c = run_cell(design(reps=40, sampler="t3", seed=6), SyntheticSampler("t3"), workers=1)
    assert json.dumps(a) != json.dumps(c)


def test_location_shift_preserves_centred_residuals():
    rng = np.random.default_rng(0)
    d = rng.standard_t(3, 5000) * 7 + 2.5
    s = BootstrapSampler("x", d - d.mean(), float(d.std(ddof=1)))
    shifted = s.with_true_mean(1.25)
    x0, x1 = s.draw(replicate_rng(1, 0), 1000), shifted.draw(replicate_rng(1, 0), 1000)
    assert np.allclose(x1 - x0, 1.25)  # same residual draws, only the location moves
    assert shifted.sigma == s.sigma and abs(s.residuals.mean()) < 1e-12
    syn = SyntheticSampler("normal", 2.0).with_true_mean(0.5)
    assert np.allclose(syn.draw(replicate_rng(3, 0), 10) - 0.5, SyntheticSampler("normal", 2.0).draw(replicate_rng(3, 0), 10))


def test_permutation_sampler_has_exact_true_mean_and_no_replacement():
    d = np.arange(100, dtype=float) - 20.0
    p = PermutationSampler("x", d)
    x = p.draw(replicate_rng(2, 0), 100)
    assert np.array_equal(np.sort(x), d) and p.true_mean == d.mean()
    with pytest.raises(ValueError):
        p.draw(replicate_rng(2, 0), 101)
    with pytest.raises(ValueError):
        p.with_true_mean(0.0)
    with pytest.raises(ValueError):
        run_cell(design(n_max=101, fixed_n=101), p)


def test_wrong_sign_accounting_under_non_null():
    d = design(reps=200, true_mean=0.15, min_n=20)
    rows = run_cell(d, SyntheticSampler("normal", true_mean=0.15), workers=1)
    for r in rows:
        assert r["wrong_decision"] == (r["decision_sign"] == -1)
        if r["decision_sign"] == 1 and r["method"] != "fixed":
            assert r["first_correct_sign_time"] == r["decision_time"]


def test_asymptotic_cs_boundary_matches_external_confseq_reference():
    """confseq (gostevehoward/confseq 0.0.9 wheel, isolated Python 3.10 venv) computed these
    two-sided normal-mixture bounds; see scripts/external/confseq_reference.py."""
    ref = json.loads((Path(__file__).parent / "data" / "confseq_normal_mixture_reference.json").read_text())
    assert ref["cases"]
    for c in ref["cases"]:
        ours = asymp_radius(np.array([c["v"]]), np.array([1.0]), c["alpha"], c["v_opt"])[0] * c["v"]
        assert ours == pytest.approx(c["bound"], rel=1e-9)
