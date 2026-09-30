"""Leaderboard / qualification reliability metrics. Tournaments are the only unit.

Inputs are per-tournament arrays over a fixed bot order: ``rank`` (M, N) positional
final ranks (1 = best, no ties) and ``qualified`` (M, N) booleans. Repeatability
metrics compare *independent reruns* of the same cell: every metric is a U-statistic
over all unordered pairs of distinct tournaments, e.g. expected top-K overlap between
two independent reruns. Uncertainty comes from a tournament-level bootstrap
(multinomial weights over tournaments; pairs of copies of the same tournament are
excluded). Hands, matches and rounds are never resampled.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

Z95 = 1.959963984540054


# ------------------------------------------------------------------ binomial
def wilson_interval(k: int | np.ndarray, n: int, z: float = Z95) -> tuple[np.ndarray, np.ndarray]:
    k = np.asarray(k, dtype=float)
    if n <= 0:
        nan = np.full_like(k, np.nan)
        return nan, nan
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return np.clip(centre - half, 0, 1), np.clip(centre + half, 0, 1)


# ------------------------------------------------------------------ pairwise rerun matrices (M x M)
def overlap_matrix(qualified: np.ndarray) -> np.ndarray:
    q = qualified.astype(np.int32)
    return q @ q.T


def spearman_matrix(rank: np.ndarray) -> np.ndarray:
    n = rank.shape[1]
    r = rank.astype(np.float64)
    sq = (r * r).sum(1)
    d2 = sq[:, None] + sq[None, :] - 2 * (r @ r.T)
    return 1 - 6 * d2 / (n * (n * n - 1))


def kendall_matrix(rank: np.ndarray) -> np.ndarray:
    n = rank.shape[1]
    i, j = np.triu_indices(n, 1)
    s = np.sign(rank[:, i].astype(np.int64) - rank[:, j]).astype(np.float64)
    return (s @ s.T) / len(i)


def mean_abs_rank_diff_matrix(rank: np.ndarray, chunk: int = 256) -> np.ndarray:
    m = rank.shape[0]
    out = np.zeros((m, m))
    r = rank.astype(np.int32)
    for a in range(0, m, chunk):
        out[a : a + chunk] = np.abs(r[a : a + chunk, None, :] - r[None, :, :]).mean(axis=2)
    return out


def pair_mean(mat: np.ndarray, w: np.ndarray | None = None) -> float:
    """Mean over unordered pairs of distinct tournaments (weighted by bootstrap counts)."""
    m = mat.shape[0]
    if w is None:
        if m < 2:
            return float("nan")
        return float((mat.sum() - np.trace(mat)) / (m * (m - 1)))
    num = w @ mat @ w - (w * w * np.diag(mat)).sum()
    den = w.sum() ** 2 - (w * w).sum()
    return float(num / den) if den > 0 else float("nan")


# ------------------------------------------------------------------ bootstrap
@dataclass(frozen=True)
class Estimate:
    value: float
    se: float
    lo: float
    hi: float
    n_units: int

    def to_dict(self, prefix: str = "") -> dict[str, float]:
        return {f"{prefix}value": self.value, f"{prefix}se": self.se, f"{prefix}ci_lo": self.lo,
                f"{prefix}ci_hi": self.hi, f"{prefix}n_tournaments": self.n_units}


def bootstrap_weights(m: int, b: int, seed: int) -> np.ndarray:
    rng = np.random.Generator(np.random.PCG64(seed))
    return rng.multinomial(m, np.full(m, 1.0 / m), size=b).astype(np.float64)


def bootstrap(stat: Callable[[np.ndarray | None], float], m: int, b: int = 1000, seed: int = 20260929,
              weights: np.ndarray | None = None) -> Estimate:
    """``stat(w)`` with ``w=None`` is the point estimate; percentile 95% interval."""
    point = stat(None)
    ws = weights if weights is not None else bootstrap_weights(m, b, seed)
    reps = np.array([stat(w) for w in ws])
    reps = reps[np.isfinite(reps)]
    if len(reps) == 0:
        return Estimate(point, float("nan"), float("nan"), float("nan"), m)
    return Estimate(point, float(reps.std(ddof=1)), float(np.quantile(reps, 0.025)),
                    float(np.quantile(reps, 0.975)), m)


# ------------------------------------------------------------------ cell-level metrics
def qualification_table(qualified: np.ndarray, bots: Sequence[str]) -> list[dict[str, Any]]:
    m = qualified.shape[0]
    k = qualified.sum(0)
    lo, hi = wilson_interval(k, m)
    return [{"bot_id": b, "n_tournaments": m, "n_qualified": int(k[i]), "p_qualify": k[i] / m if m else np.nan,
             "wilson_lo": float(lo[i]), "wilson_hi": float(hi[i])} for i, b in enumerate(bots)]


def rerun_stability(rank: np.ndarray, qualified: np.ndarray, k_cut: int, b: int = 1000, seed: int = 20260929,
                    ambiguous_band: tuple[float, float] = (0.1, 0.9),
                    weights: np.ndarray | None = None) -> dict[str, Estimate]:
    """Expected agreement between two independent reruns of the same field and protocol."""
    m = rank.shape[0]
    ov = overlap_matrix(qualified).astype(np.float64)
    jac = ov / (2 * k_cut - ov)
    mats = {
        "topk_overlap": ov,
        "changed_qualifiers": k_cut - ov,
        "jaccard": jac,
        "kendall_tau": kendall_matrix(rank),
        "spearman_rho": spearman_matrix(rank),
        "mean_abs_rank_diff": mean_abs_rank_diff_matrix(rank),
    }
    ws = weights if weights is not None else bootstrap_weights(m, b, seed)
    out = {name: bootstrap(lambda w, _m=mat: pair_mean(_m, w), m, weights=ws) for name, mat in mats.items()}
    q = qualified.astype(np.float64)
    lo_b, hi_b = ambiguous_band

    def ambiguous(w: np.ndarray | None) -> float:
        p = q.mean(0) if w is None else (w @ q) / w.sum()
        return float(((p >= lo_b) & (p <= hi_b)).sum())

    def p_top1_same(w: np.ndarray | None) -> float:
        winners = (rank == 1).astype(np.float64)
        return pair_mean(winners @ winners.T, w)

    out["n_ambiguous_bots"] = bootstrap(ambiguous, m, weights=ws)
    out["p_same_winner"] = bootstrap(p_top1_same, m, weights=ws)
    return out


def estimates_to_row(est: Mapping[str, Estimate]) -> dict[str, float]:
    row: dict[str, float] = {}
    for name, e in est.items():
        row |= e.to_dict(prefix=f"{name}_")
    return row


def cutoff_curve(qualified: np.ndarray, reference: np.ndarray, bots: Sequence[str]) -> list[dict[str, Any]]:
    """P(qualify) by long-run reference rank (1 = best reference value)."""
    order = np.argsort(-reference, kind="stable")
    m = qualified.shape[0]
    k = qualified.sum(0)
    lo, hi = wilson_interval(k, m)
    return [{"reference_rank": r + 1, "bot_id": bots[i], "reference_value": float(reference[i]),
             "p_qualify": float(k[i] / m), "wilson_lo": float(lo[i]), "wilson_hi": float(hi[i]),
             "n_tournaments": m} for r, i in enumerate(order)]


def pairwise_inversions(rank: np.ndarray, reference: np.ndarray, reference_se: np.ndarray | None,
                        bots: Sequence[str]) -> list[dict[str, Any]]:
    """For every pair with reference_i > reference_j: P(Swiss ranks j above i)."""
    m, n = rank.shape
    rows = []
    for a in range(n):
        for c in range(n):
            if reference[a] <= reference[c]:
                continue
            inv = int((rank[:, c] < rank[:, a]).sum())
            lo, hi = wilson_interval(inv, m)
            gap_se = (float(np.hypot(reference_se[a], reference_se[c])) if reference_se is not None else float("nan"))
            rows.append({"better_bot": bots[a], "worse_bot": bots[c], "reference_gap": float(reference[a] - reference[c]),
                         "reference_gap_se": gap_se, "p_inversion": inv / m, "wilson_lo": float(lo),
                         "wilson_hi": float(hi), "n_tournaments": m})
    return rows


def binned_inversions(rank: np.ndarray, reference: np.ndarray, edges: Sequence[float], b: int = 500,
                      seed: int = 20260929) -> list[dict[str, Any]]:
    """Mean inversion probability per reference-gap bin, bootstrap over tournaments."""
    m, n = rank.shape
    a_idx, c_idx = np.where(reference[:, None] > reference[None, :])
    gaps = reference[a_idx] - reference[c_idx]
    inv = (rank[:, c_idx] < rank[:, a_idx]).astype(np.float64)  # (M, pairs)
    ws = bootstrap_weights(m, b, seed)
    rows = []
    for lo_e, hi_e in zip(edges[:-1], edges[1:], strict=True):
        sel = (gaps >= lo_e) & (gaps < hi_e)
        if not sel.any():
            continue
        x = inv[:, sel].mean(1)
        est = bootstrap(lambda w, _x=x: float(_x.mean() if w is None else (w @ _x) / w.sum()), m, weights=ws)
        rows.append({"gap_lo": lo_e, "gap_hi": hi_e, "n_pairs": int(sel.sum())} | est.to_dict("p_inversion_"))
    return rows


def rank_agreement(a: np.ndarray, b: np.ndarray) -> dict[str, float]:
    """Kendall tau / Spearman between two reference orderings (values, higher = better)."""
    ra = (-a).argsort(kind="stable").argsort() + 1
    rb = (-b).argsort(kind="stable").argsort() + 1
    both = np.vstack([ra, rb])
    return {"kendall_tau": float(kendall_matrix(both)[0, 1]), "spearman_rho": float(spearman_matrix(both)[0, 1])}


def monte_carlo_advice(est: Estimate, target_half_width: float) -> dict[str, Any]:
    half = (est.hi - est.lo) / 2 if math.isfinite(est.hi) else float("nan")
    need = est.n_units * (half / target_half_width) ** 2 if half > 0 and math.isfinite(half) else float("nan")
    return {"ci_half_width": half, "target_half_width": target_half_width,
            "extension_needed": bool(half > target_half_width) if math.isfinite(half) else True,
            "approx_tournaments_for_target": math.ceil(need) if math.isfinite(need) else None}


def accuracy_vs_reference(rank: np.ndarray, reference: np.ndarray, k_cut: int,
                          weights: np.ndarray | None = None, b: int = 1000, seed: int = 20260929) -> dict[str, Estimate]:
    """Accuracy of finite tournaments against a long-run reference (mu_field or mu_swiss).

    ``reference_topk_overlap``: expected |finite top-K intersect reference top-K|;
    ``reference_changed``: K minus that; ``reference_kendall_tau``: rank agreement with the
    reference ordering. Tournaments are the bootstrap units.
    """
    m = rank.shape[0]
    ref_rank = (-reference).argsort(kind="stable").argsort() + 1
    ref_top = ref_rank <= k_cut
    overlap = ((rank <= k_cut) & ref_top[None, :]).sum(1).astype(float)
    tau = kendall_matrix(np.vstack([ref_rank[None, :], rank]))[0, 1:]
    ws = weights if weights is not None else bootstrap_weights(m, b, seed)

    def mean(x: np.ndarray):
        return lambda w: float(x.mean() if w is None else (w @ x) / w.sum())

    return {"reference_topk_overlap": bootstrap(mean(overlap), m, weights=ws),
            "reference_changed": bootstrap(mean(k_cut - overlap), m, weights=ws),
            "reference_kendall_tau": bootstrap(mean(tau), m, weights=ws)}
