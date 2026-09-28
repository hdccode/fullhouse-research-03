"""RQ7: anytime-valid inference on the block sequence D_1, D_2, ... (downstream only).

The simulator knows nothing about this module. Methods:

``asymp``  Asymptotic confidence sequence (Waudby-Smith, Arbour, Sinha, Kennedy &
           Ramdas, "Time-uniform central limit theory and asymptotic confidence
           sequences", Annals of Statistics 2024, two-sided Robbins normal-mixture
           form with plug-in variance):

               mu_t  +/-  sigma_t * sqrt( 2 (t rho^2 + 1) / (t^2 rho^2) * log( sqrt(t rho^2 + 1) / alpha ) )

           rho is tuned to minimise the width at a target sample size t*:
               rho^2 = ( -2 log alpha + log(-2 log alpha + 1) ) / t*
           Valid asymptotically, time-uniformly, under finite variance (no bound
           on |D| needed), which suits heavy-tailed block differences.

``fixed``  Fixed-N Student-t interval, valid only at a single pre-registered n.
``peek``   The *invalid* comparator: the fixed-N t-interval recomputed at every
           look. Reported only to show the inflated error of naive peeking.

confseq (gostevehoward/confseq, pinned 0.0.11 as the optional ``sequential``
extra) provides the same normal-mixture boundary; it is used to cross-check this
implementation when installed (tests/test_sequential.py). On Python >= 3.11 it
has no wheels and needs Boost to build, which is why it is not a hard dependency.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
from scipy import stats as sps

METHOD_VERSION = "fhr3-asympcs-v1"
METHODS = ("asymp", "fixed", "peek")


def rho_for(t_star: float, alpha: float) -> float:
    la = -2.0 * math.log(alpha)
    return math.sqrt((la + math.log(la + 1.0)) / t_star)


def asymp_radius(t: np.ndarray, sd: np.ndarray, alpha: float, t_star: float) -> np.ndarray:
    """Half-width of the two-sided asymptotic CS at times t (vectorised)."""
    r2 = rho_for(t_star, alpha) ** 2
    t = np.asarray(t, dtype=float)
    return sd * np.sqrt(2.0 * (t * r2 + 1.0) / (t * t * r2) * np.log(np.sqrt(t * r2 + 1.0) / alpha))


def running_mean_sd(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(t, running mean, running sample SD) along the last axis."""
    n = x.shape[-1]
    t = np.arange(1, n + 1, dtype=float)
    s1 = np.cumsum(x, axis=-1)
    s2 = np.cumsum(x * x, axis=-1)
    mean = s1 / t
    with np.errstate(invalid="ignore", divide="ignore"):
        var = (s2 - t * mean * mean) / np.maximum(t - 1.0, 1.0)
    return t, mean, np.sqrt(np.maximum(var, 0.0))


def interval_path(x: np.ndarray, method: str, alpha: float, t_star: float) -> tuple[np.ndarray, np.ndarray]:
    """Lower/upper bounds after each observation (along the last axis)."""
    t, mean, sd = running_mean_sd(x)
    if method == "asymp":
        rad = asymp_radius(t, sd, alpha, t_star)
    elif method in ("fixed", "peek"):
        rad = sps.t.ppf(1 - alpha / 2, np.maximum(t - 1, 1)) * sd / np.sqrt(t)
    else:
        raise ValueError(f"unknown method {method!r}")
    return mean - rad, mean + rad


def run_sequential(
    D: Sequence[float],
    method: str = "asymp",
    alpha: float = 0.05,
    t_star: float = 100_000,
    min_n: int = 200,
    width_threshold: float | None = None,
) -> dict[str, Any]:
    """Stop at the first n >= min_n where the interval excludes 0 (or its full
    width drops below ``width_threshold``); otherwise at the end of the data.

    For ``fixed`` there is no stopping: the interval is evaluated once at the
    final n (the pre-registered budget).
    """
    x = np.asarray(D, dtype=float)
    lo, hi = interval_path(x, method, alpha, t_star)
    n = x.size
    stop, reason = n, "budget_exhausted"
    if method != "fixed":
        for i in range(min_n - 1, n):
            if lo[i] > 0 or hi[i] < 0:
                stop, reason = i + 1, "excludes_zero"
                break
            if width_threshold is not None and hi[i] - lo[i] < width_threshold:
                stop, reason = i + 1, "width_below_threshold"
                break
    i = stop - 1
    decision = "A>B" if lo[i] > 0 else "B>A" if hi[i] < 0 else "none"
    return {
        "method": method,
        "method_version": METHOD_VERSION,
        "alpha": alpha,
        "t_star": t_star if method == "asymp" else None,
        "min_n": min_n,
        "width_threshold": width_threshold,
        "stopping_time": int(stop),
        "reason": reason,
        "decision": decision,
        "interval": [float(lo[i]), float(hi[i])],
        "mean": float(x[:stop].mean()),
        "n_available": int(n),
        "valid_for_optional_stopping": method == "asymp",
    }


def coverage_experiment(
    sampler: Any,
    true_mean: float,
    n_max: int,
    reps: int,
    method: str,
    alpha: float = 0.05,
    t_star: float = 100_000,
    min_n: int = 200,
    seed: int = 0,
    batch: int = 64,
) -> dict[str, Any]:
    """Synthetic IID streams with known mean.

    Reports time-uniform miscoverage (the interval misses the true mean at *any*
    n in [min_n, n_max]), final-n miscoverage, and the stopping-time / decision
    distribution of the exclude-zero rule. ``sampler(rng, shape)`` draws blocks.
    """
    rng = np.random.default_rng(seed)
    ever_miss = final_miss = 0
    stops: list[int] = []
    decisions = {"A>B": 0, "B>A": 0, "none": 0}
    for start in range(0, reps, batch):
        m = min(batch, reps - start)
        x = sampler(rng, (m, n_max))
        lo, hi = interval_path(x, method, alpha, t_star)
        lo, hi = lo[:, min_n - 1 :], hi[:, min_n - 1 :]
        miss = (lo > true_mean) | (hi < true_mean)
        ever_miss += int(miss.any(axis=1).sum())
        final_miss += int(miss[:, -1].sum())
        excl = (lo > 0) | (hi < 0)
        if method == "fixed":  # evaluated once, at the pre-registered final n
            excl = np.zeros_like(excl)
            excl[:, -1] = (lo[:, -1] > 0) | (hi[:, -1] < 0)
        first = np.where(excl.any(axis=1), excl.argmax(axis=1), -1)
        for j in range(m):
            if first[j] < 0:
                stops.append(n_max)
                decisions["none"] += 1
            else:
                stops.append(int(first[j]) + min_n)
                decisions["A>B" if lo[j, first[j]] > 0 else "B>A"] += 1
    s = np.array(stops)
    return {
        "method": method,
        "method_version": METHOD_VERSION,
        "alpha": alpha,
        "t_star": t_star,
        "min_n": min_n,
        "n_max": n_max,
        "reps": reps,
        "true_mean": true_mean,
        # not defined for a fixed-N interval (it makes no claim before n_max)
        "time_uniform_miscoverage": None if method == "fixed" else ever_miss / reps,
        "final_n_miscoverage": final_miss / reps,
        "stopping_time_quantiles": {q: float(np.quantile(s, q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)},
        "decisions": decisions,
        "wrong_sign_rate": (decisions["B>A"] if true_mean > 0 else decisions["A>B"] if true_mean < 0
                            else decisions["A>B"] + decisions["B>A"]) / reps,
    }


def make_sampler(spec: str, true_mean: float, scale: float = 1.0) -> Any:
    """``normal``, ``t3`` (heavy tails, finite variance) or ``bootstrap:<path>``
    (centred block residuals from a Parquet corpus, shifted to ``true_mean``)."""
    if spec == "normal":
        return lambda rng, shape: true_mean + scale * rng.standard_normal(shape)
    if spec == "t3":
        return lambda rng, shape: true_mean + scale * rng.standard_t(3, shape) / math.sqrt(3.0)
    if spec.startswith("bootstrap:"):
        from fhr3.io.store import read_blocks

        t = read_blocks(spec.split(":", 1)[1], columns=["config_hash", "pairing_id", "block_id", "valid", "D"])
        D = np.asarray(t.filter(t.column("valid")).column("D").to_numpy(zero_copy_only=False), dtype=float)
        r = D - D.mean()
        return lambda rng, shape: true_mean + r[rng.integers(0, r.size, size=shape)]
    raise ValueError(f"unknown sampler {spec!r}")
