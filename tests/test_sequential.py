"""RQ7 sequential layer: formula checks, coverage on synthetic streams, stopping."""

from __future__ import annotations

import math

import numpy as np
import pytest

from fhr3.analysis.sequential import (
    asymp_radius,
    coverage_experiment,
    make_sampler,
    rho_for,
    run_sequential,
)


def test_radius_formula_and_scaling():
    a, ts = 0.05, 100_000
    r2 = rho_for(ts, a) ** 2
    t = 5000.0
    expect = math.sqrt(2 * (t * r2 + 1) / (t * t * r2) * math.log(math.sqrt(t * r2 + 1) / a))
    assert asymp_radius(np.array([t]), np.array([1.0]), a, ts)[0] == pytest.approx(expect)
    r = asymp_radius(np.array([1e3, 1e4, 1e5, 1e6]), np.ones(4), a, ts)
    assert np.all(np.diff(r) < 0)  # shrinks with t
    # wider than the fixed-n z interval at every t (the price of anytime validity)
    assert np.all(r > 1.96 / np.sqrt([1e3, 1e4, 1e5, 1e6]))


def test_asymptotic_cs_time_uniform_coverage_normal_and_heavy_tailed():
    for spec in ("normal", "t3"):
        res = coverage_experiment(make_sampler(spec, 0.3), 0.3, n_max=4000, reps=300, method="asymp",
                                  t_star=2000, min_n=100, seed=1)
        assert res["time_uniform_miscoverage"] <= 0.05 + 0.03, (spec, res)


def test_naive_peeking_inflates_error_and_fixed_n_is_nominal():
    peek = coverage_experiment(make_sampler("normal", 0.0), 0.0, n_max=4000, reps=300, method="peek", min_n=100, seed=2)
    fixed = coverage_experiment(make_sampler("normal", 0.0), 0.0, n_max=4000, reps=300, method="fixed", min_n=100, seed=2)
    assert peek["time_uniform_miscoverage"] > 0.15  # repeated looks: far above 5%
    assert abs(fixed["final_n_miscoverage"] - 0.05) < 0.04
    assert fixed["time_uniform_miscoverage"] is None
    assert sum(fixed["decisions"].values()) == 300 and fixed["stopping_time_quantiles"][0.1] == 4000


def test_stopping_rule_and_decisions():
    rng = np.random.default_rng(3)
    x = 0.5 + rng.standard_normal(20_000)
    res = run_sequential(x, "asymp", t_star=5000, min_n=100)
    assert res["reason"] == "excludes_zero" and res["decision"] == "A>B" and res["stopping_time"] < 20_000
    assert run_sequential(-x, "asymp", t_star=5000, min_n=100)["decision"] == "B>A"
    null = run_sequential(rng.standard_normal(3000), "asymp", t_star=3000, min_n=100)
    assert null["decision"] == "none" and null["reason"] == "budget_exhausted"
    w = run_sequential(rng.standard_normal(50_000) * 0.1, "asymp", t_star=5000, min_n=100, width_threshold=0.02)
    assert w["reason"] == "width_below_threshold"
    fixed = run_sequential(x, "fixed")
    assert fixed["stopping_time"] == x.size and not fixed["valid_for_optional_stopping"]


def test_matches_confseq_normal_mixture_when_installed():
    confseq = pytest.importorskip("confseq")
    from confseq import boundaries

    a, ts, t = 0.05, 10_000, np.array([100.0, 1000.0, 10_000.0, 100_000.0])
    # normal mixture two-sided bound on S_t with intrinsic time V_t = t (unit variance)
    ours = asymp_radius(t, np.ones_like(t), a, ts) * t
    ref = np.array([boundaries.normal_mixture_bound(v, a, ts, a, False) for v in t])
    assert np.allclose(ours, ref, rtol=1e-3)
    del confseq
