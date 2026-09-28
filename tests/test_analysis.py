"""Block-level statistics, power, resampling."""

import math

import numpy as np
import pytest
from scipy import stats as sps

from fhr3.analysis.stats import (
    analytic_power,
    bb100_to_block,
    bootstrap_ci,
    describe,
    location_shift_power,
    power_table,
    required_blocks,
)


def test_unit_conversion():
    assert bb100_to_block(1.0, 6) == pytest.approx(0.06)


def test_required_blocks_textbook():
    # (1.959964 + 0.841621)^2 = 7.8489 for alpha .05, power .8, d = 1
    assert required_blocks(1.0, 1.0) == pytest.approx(7.84887, rel=1e-4)
    assert required_blocks(2.0, 0.5, power=0.95) == pytest.approx(((1.959964 + 1.644854) * 4) ** 2, rel=1e-5)
    n = required_blocks(3.0, 0.1)
    assert analytic_power(3.0, 0.1, math.ceil(n)) == pytest.approx(0.8, abs=2e-3)
    assert math.isnan(required_blocks(0.0, 0.1))


def test_power_table_hands_translation():
    row = power_table(10.0, 6, deltas_bb100=[1.0])[0]
    assert row["delta_block"] == pytest.approx(0.06)
    assert row["played_hands_power80"] == row["blocks_power80"] * 12
    assert row["standardized_d"] == pytest.approx(0.006)


def test_describe_matches_scipy():
    rng = np.random.default_rng(1)
    D = rng.standard_t(3, size=5000)
    d = describe(D, 6)
    assert d["sd_D"] == pytest.approx(D.std(ddof=1))
    lo, hi = sps.t.interval(0.95, D.size - 1, loc=D.mean(), scale=sps.sem(D))
    assert d["ci_mean"] == pytest.approx([lo, hi])
    assert d["mean_bb100"] == pytest.approx(100 * D.mean() / 6)


def test_bootstrap_ci_covers_and_is_deterministic():
    D = np.random.default_rng(2).normal(0.3, 2.0, 4000)
    a = bootstrap_ci(D, n_boot=500, seed=5)
    assert a == bootstrap_ci(D, n_boot=500, seed=5)
    assert a["mean"][0] < D.mean() < a["mean"][1]
    assert a["sd"][0] < D.std(ddof=1) < a["sd"][1]


def test_location_shift_power_matches_analytic_and_null_size():
    D = np.random.default_rng(3).normal(5.0, 2.0, 20000)  # mean is removed by centering
    res = location_shift_power(D, [0.0, 0.2], [400], reps=4000, seed=1)
    null = next(r for r in res if r["delta_block"] == 0.0)
    alt = next(r for r in res if r["delta_block"] == 0.2)
    assert null["power_two_sided"] == pytest.approx(0.05, abs=0.015)
    assert alt["power_two_sided"] == pytest.approx(analytic_power(2.0, 0.2, 400), abs=0.03)
    assert alt["p_select_stronger"] > 0.9
    assert all(r["kind"] == "synthetic_location_shift" for r in res)
