"""Block-level statistics, power and resampling.

Everything here consumes a 1-D array of *block* differences D_1..D_n. Nothing
resamples hands within a block. Effect sizes are specified in BB/100 candidate
hands and converted to the block scale via

    Delta_block = Delta_bb100 * k / 100      (k candidate hands per side per block)

Played hands per block are 2k (both A- and B-hands are dealt).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
from scipy import stats as sps

DEFAULT_DELTAS_BB100 = (0.25, 0.5, 1.0, 2.0, 5.0)
DEFAULT_POWERS = (0.80, 0.95)
CONCENTRATION_FRACTIONS = (0.10, 0.05, 0.01, 0.005, 0.001, 0.0005, 0.0001)


def variance_concentration(D: np.ndarray, fractions: Sequence[float] = CONCENTRATION_FRACTIONS) -> dict[str, Any]:
    """Share of the total squared deviation contributed by the top-f fraction of
    blocks (ranked by |D - mean|). ``None`` where f*n < 1 block.

    A Gaussian-like sample has the top 1% contributing ~ 10% of the variance;
    values near 1 mean sigma_D is driven by rare extreme blocks.
    """
    n = D.size
    dev2 = np.sort((D - D.mean()) ** 2)[::-1]
    total = float(dev2.sum())
    out: dict[str, Any] = {}
    for f in fractions:
        m = int(np.floor(f * n))
        out[f"{f:g}"] = (float(dev2[:m].sum() / total) if total > 0 else None) if m >= 1 else None
    return out


def concentration_curve(D: np.ndarray, points: int = 200) -> list[tuple[float, float]]:
    """Figure data: (top fraction of blocks, cumulative share of squared deviation)
    on a log-spaced grid from 1/n to 1."""
    n = D.size
    if n < 2:
        return []
    dev2 = np.sort((D - D.mean()) ** 2)[::-1]
    total = float(dev2.sum())
    if total <= 0:
        return []
    cum = np.cumsum(dev2) / total
    ms = np.unique(np.clip(np.round(np.logspace(0, np.log10(n), points)).astype(int), 1, n))
    return [(float(m / n), float(cum[m - 1])) for m in ms]


def bb100_to_block(delta_bb100: float, k: float) -> float:
    """``k`` = candidate hands per side per block (exactly the player count for
    single-hand protocols; the mean round length x seats for the Nit Game)."""
    return delta_bb100 * k / 100.0


def block_to_bb100(delta_block: float, k: float) -> float:
    return 100.0 * delta_block / k


def describe(D: np.ndarray, k: float, alpha: float = 0.05) -> dict[str, Any]:
    n = int(D.size)
    mean = float(D.mean())
    sd = float(D.std(ddof=1)) if n > 1 else float("nan")
    se = sd / math.sqrt(n) if n > 1 else float("nan")
    tcrit = float(sps.t.ppf(1 - alpha / 2, n - 1)) if n > 1 else float("nan")
    qs = (0.001, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 0.999)
    q = np.quantile(D, qs) if n else np.full(len(qs), np.nan)
    absD = np.abs(D - mean)
    top = np.sort(absD)[::-1]
    ss = float(np.sum((D - mean) ** 2)) or float("nan")
    return {
        "n_blocks": n,
        "k": k,
        "mean_D": mean,
        "sd_D": sd,
        "se_mean": se,
        "ci_mean": [mean - tcrit * se, mean + tcrit * se],
        "mean_bb100": block_to_bb100(mean, k),
        "ci_bb100": [block_to_bb100(mean - tcrit * se, k), block_to_bb100(mean + tcrit * se, k)],
        "sd_bb100_per_block": block_to_bb100(sd, k),
        "skew": float(sps.skew(D)) if n > 2 else float("nan"),
        "excess_kurtosis": float(sps.kurtosis(D)) if n > 3 else float("nan"),
        "quantiles": {str(a): float(v) for a, v in zip(qs, q, strict=True)},
        "min": float(D.min()) if n else float("nan"),
        "max": float(D.max()) if n else float("nan"),
        "frac_zero": float(np.mean(D == 0)) if n else float("nan"),
        "frac_beyond_4sd": float(np.mean(absD > 4 * sd)) if n > 1 else float("nan"),
        # Share of total squared deviation contributed by the largest 1% / 0.1% of
        # blocks: a direct measure of how much sigma_D is driven by rare big pots.
        "var_share_top1pct": float(np.sum(top[: max(1, n // 100)] ** 2) / ss) if n else float("nan"),
        "var_share_top0p1pct": float(np.sum(top[: max(1, n // 1000)] ** 2) / ss) if n else float("nan"),
        "concentration": variance_concentration(D) if n > 1 else {},
    }


def required_blocks(sigma: float, delta_block: float, alpha: float = 0.05, power: float = 0.8) -> float:
    """Two-sided z-test sample size: n = ((z_{1-a/2} + z_{power}) * sigma / delta)^2."""
    if delta_block <= 0 or not math.isfinite(sigma) or sigma <= 0:
        return float("nan")
    z = sps.norm.ppf(1 - alpha / 2) + sps.norm.ppf(power)
    return float((z * sigma / delta_block) ** 2)


def analytic_power(sigma: float, delta_block: float, n: int, alpha: float = 0.05) -> float:
    """Two-sided z-test power at n blocks (normal approximation)."""
    if n <= 0 or sigma <= 0:
        return float("nan")
    z = sps.norm.ppf(1 - alpha / 2)
    shift = delta_block * math.sqrt(n) / sigma
    return float(sps.norm.cdf(shift - z) + sps.norm.cdf(-shift - z))


def power_table(
    sigma: float,
    k: float,
    deltas_bb100: Sequence[float] = DEFAULT_DELTAS_BB100,
    powers: Sequence[float] = DEFAULT_POWERS,
    alpha: float = 0.05,
) -> list[dict[str, Any]]:
    out = []
    for d in deltas_bb100:
        db = bb100_to_block(d, k)
        row: dict[str, Any] = {
            "delta_bb100": d,
            "delta_block": db,
            "standardized_d": db / sigma if sigma > 0 else float("nan"),
        }
        for p in powers:
            n = required_blocks(sigma, db, alpha, p)
            tag = f"{int(round(p * 100))}"
            row[f"blocks_power{tag}"] = math.ceil(n) if math.isfinite(n) else None
            row[f"played_hands_power{tag}"] = round(math.ceil(n) * 2 * k) if math.isfinite(n) else None
            row[f"candidate_hands_power{tag}"] = round(math.ceil(n) * k) if math.isfinite(n) else None
        out.append(row)
    return out


def bootstrap_ci(
    D: np.ndarray, n_boot: int = 2000, alpha: float = 0.05, seed: int = 0, batch: int = 200
) -> dict[str, list[float]]:
    """Percentile bootstrap (resampling whole blocks) for mean and SD."""
    rng = np.random.default_rng(seed)
    n = D.size
    means, sds = [], []
    for start in range(0, n_boot, batch):
        m = min(batch, n_boot - start)
        idx = rng.integers(0, n, size=(m, n))
        s = D[idx]
        means.append(s.mean(axis=1))
        sds.append(s.std(axis=1, ddof=1))
    mean_arr, sd_arr = np.concatenate(means), np.concatenate(sds)
    lo, hi = alpha / 2, 1 - alpha / 2
    return {
        "mean": [float(np.quantile(mean_arr, lo)), float(np.quantile(mean_arr, hi))],
        "sd": [float(np.quantile(sd_arr, lo)), float(np.quantile(sd_arr, hi))],
    }


def location_shift_power(
    D: np.ndarray,
    deltas_block: Sequence[float],
    ns: Sequence[int],
    reps: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
    max_cells: int = 20_000_000,
) -> list[dict[str, Any]]:
    """Empirical power from *synthetic* location shifts of the centred residuals.

    residuals r_i = D_i - mean(D); a hypothetical true gap Delta is imposed as
    r + Delta, and n blocks are resampled with replacement. This measures power
    under the observed block-level distribution shape; it is a statistical
    experiment, not a genuine agent matchup, and is labelled as such in output.

    Reports the two-sided t-test rejection rate and the probability that the
    sample mean has the correct sign ("selects the stronger agent").
    """
    rng = np.random.default_rng(seed)
    r = D - D.mean()
    out = []
    for n in ns:
        rows_per_batch = max(1, min(reps, max_cells // max(n, 1)))
        means = np.empty(reps)
        sds = np.empty(reps)
        done = 0
        while done < reps:
            m = min(rows_per_batch, reps - done)
            s = r[rng.integers(0, r.size, size=(m, n))]
            means[done : done + m] = s.mean(axis=1)
            sds[done : done + m] = s.std(axis=1, ddof=1) if n > 1 else np.nan
            done += m
        se = sds / math.sqrt(n)
        tcrit = sps.t.ppf(1 - alpha / 2, max(n - 1, 1))
        for delta in deltas_block:
            shifted = means + delta  # same resamples reused across Delta (CRN)
            with np.errstate(divide="ignore", invalid="ignore"):
                reject = np.abs(shifted / se) > tcrit
                correct_reject = reject & (np.sign(shifted) == np.sign(delta))
            out.append(
                {
                    "kind": "synthetic_location_shift",
                    "n_blocks": int(n),
                    "delta_block": float(delta),
                    "reps": reps,
                    "power_two_sided": float(np.mean(reject)),
                    "power_correct_sign": float(np.mean(correct_reject)),
                    "p_select_stronger": float(np.mean(np.sign(shifted) == np.sign(delta)))
                    if delta != 0
                    else float("nan"),
                }
            )
    return out
