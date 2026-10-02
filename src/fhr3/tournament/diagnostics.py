"""Field diagnostics used by field selection and calibration review (analysis only).

Nothing here can change a tournament or calibration row; the module is deliberately
outside the engine source hash (manifests.RESULT_SOURCES).

* ``param_vectors`` / ``param_distance``: every bot's *resolved* policy parameters as a
  normalised vector (log scale for positive parameters, scaled additive parameters),
  and the RMS distance between two bots of the same agent kind (inf across kinds).
  Used to detect near-duplicates.
* ``SplitHalf``: calibration sufficient statistics over chunk groups, split into
  independent halves. Cross-half inner products estimate true signal energy without a
  noise model, and split-half correlations measure reliability. This is the only
  supported way to *measure* matchup / non-transitive structure; it is never a field
  selection criterion.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, fields as dc_fields
from typing import Any

import numpy as np

from fhr3.agents import AgentSpec
from fhr3.tournament.agents import build_agent

ADDITIVE_SCALE = {"call_margin": 0.05, "nit_call_shift": 0.03}


def _resolved(spec: AgentSpec) -> tuple[str, dict[str, Any]]:
    """(kind-family, resolved parameter dict) of a built agent."""
    a = build_agent(spec)
    if hasattr(a, "p"):  # HeuristicAgent family (NLHE, PLO, CP)
        return "style", asdict(a.p)
    if hasattr(a, "base") and hasattr(a, "nit_looseness"):  # Nit
        return "style", asdict(a.base.p) | {"nit_looseness": a.nit_looseness, "nit_call_shift": a.nit_call_shift}
    if hasattr(a, "s"):  # AoF heuristic
        return "aof_style", asdict(a.s)
    if hasattr(a, "blend"):  # AoF production policy (+ blend)
        return f"aof_policy:{getattr(a, 'heur', None) and a.heur.s}", {"blend": a.blend}
    return spec.kind, {}


def _flatten(d: Mapping[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for k, v in d.items():
        if isinstance(v, (list, tuple)):
            for i, x in enumerate(v):
                out[f"{k}[{i}]"] = float(x)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = float(v)
    return out


def _transform(name: str, v: float) -> float:
    base = name.split("[")[0]
    if base in ADDITIVE_SCALE:
        return v / (ADDITIVE_SCALE[base] / 0.25)  # same units as a log-scale perturbation
    if base == "blend":
        return v / 0.25
    return math.log(max(v, 1e-6))


def param_vectors(bots: Sequence[Mapping[str, Any]]) -> dict[str, tuple[str, np.ndarray, list[str]]]:
    """bot_id -> (kind family, normalised vector, parameter names)."""
    out = {}
    for b in bots:
        fam, d = _resolved(AgentSpec(b["bot_id"], b["kind"], b["params"]))
        flat = _flatten(d)
        names = sorted(flat)
        out[b["bot_id"]] = (fam, np.array([_transform(n, flat[n]) for n in names]), names)
    return out


def param_distance(vecs: Mapping[str, tuple[str, np.ndarray, list[str]]], a: str, b: str) -> float:
    fa, va, na = vecs[a]
    fb, vb, nb = vecs[b]
    if fa != fb or na != nb:
        return math.inf
    return float(np.sqrt(np.mean((va - vb) ** 2)))


def distance_matrix(vecs: Mapping[str, tuple[str, np.ndarray, list[str]]], ids: Sequence[str]) -> np.ndarray:
    n = len(ids)
    d = np.full((n, n), 0.0)
    for i in range(n):
        for j in range(i + 1, n):
            d[i, j] = d[j, i] = param_distance(vecs, ids[i], ids[j])
    return d


# ------------------------------------------------------------------ split-half calibration statistics
class SplitHalf:
    """Calibration sufficient statistics stacked over chunk groups (see calibration.GroupStats)."""

    def __init__(self, groups: Sequence[Any]) -> None:
        self.arr = {f: np.stack([getattr(g, f) for g in groups]) for f in ("n", "s", "ss", "pn", "ps", "pss")}
        self.g = len(groups)

    def stats(self, ix: Sequence[int], w: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
        w = np.ones(self.g) if w is None else w
        n, s = w @ self.arr["n"][:, ix], w @ self.arr["s"][:, ix]
        sub = np.ix_(range(self.g), ix, ix)
        pn = np.tensordot(w, self.arr["pn"][sub], 1)
        ps = np.tensordot(w, self.arr["ps"][sub], 1)
        with np.errstate(invalid="ignore", divide="ignore"):
            mu = s / n
            m = ps / pn - mu[:, None]
        np.fill_diagonal(m, 0.0)
        return mu, m


def flow_components(a: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(gradient part, cyclic part) over i<j, plus the full cyclic matrix, of an antisymmetric flow."""
    iu = np.triu_indices(a.shape[0], 1)
    r = a.mean(1)
    g = r[:, None] - r[None, :]
    return g[iu], (a - g)[iu], a - g


def crosshalf(a: SplitHalf, b: SplitHalf, ix: Sequence[int]) -> dict[str, float]:
    """Split-half reliability of strength and of the cyclic (non-transitive) presence-effect flow."""
    mu_a, m_a = a.stats(ix)
    mu_b, m_b = b.stats(ix)
    ga, ca, _ = flow_components(m_a - m_a.T)
    gb, cb, _ = flow_components(m_b - m_b.T)
    npairs = len(ca)
    return {"r_mu": float(np.corrcoef(mu_a, mu_b)[0, 1]), "r_cyclic": float(np.corrcoef(ca, cb)[0, 1]),
            "r_gradient": float(np.corrcoef(ga, gb)[0, 1]),
            "cyc_energy_per_pair": float(ca @ cb) / npairs, "grad_energy_per_pair": float(ga @ gb) / npairs,
            "r_null_se": 1 / math.sqrt(npairs - len(ix) + 1)}


def archetype_flow(half: SplitHalf, n_bots: int, lab: np.ndarray, k: int) -> np.ndarray:
    _, m = half.stats(list(range(n_bots)))
    a = m - m.T
    f = np.zeros((k, k))
    for x in range(k):
        for y in range(k):
            blk = a[np.ix_(lab == x, lab == y)]
            f[x, y] = blk[~np.eye(*blk.shape, dtype=bool)].mean() if x == y else blk.mean()
    return f


def archetype_cycle_test(groups: Sequence[Any], archetype_of: Sequence[str], rng: np.random.Generator,
                         n_perm: int = 200, scale: float = 1.0) -> dict[str, Any]:
    """Style-level non-transitivity: split-half r of the archetype cyclic flow vs a label-permutation null.

    Computed once from completed data (descriptive). ``scale`` converts stored deltas to the
    reported scale (1/k for matched lane sums); correlations are scale-free.
    """
    archs = sorted(set(archetype_of))
    lab = np.array([archs.index(x) for x in archetype_of])
    k, n = len(archs), len(archetype_of)
    a, b = SplitHalf(groups[0::2]), SplitHalf(groups[1::2])
    ga, ca, _ = flow_components(archetype_flow(a, n, lab, k))
    gb, cb, _ = flow_components(archetype_flow(b, n, lab, k))
    r = float(np.corrcoef(ca, cb)[0, 1])
    null = []
    for _ in range(n_perm):
        pl = rng.permutation(lab)
        null.append(float(np.corrcoef(flow_components(archetype_flow(a, n, pl, k))[1],
                                      flow_components(archetype_flow(b, n, pl, k))[1])[0, 1]))
    _, _, cyc_full = flow_components(archetype_flow(SplitHalf(groups), n, lab, k))
    npairs = len(ca)
    return {"archetypes": archs, "r_cyclic": r, "r_gradient": float(np.corrcoef(ga, gb)[0, 1]),
            "perm_null_q95": float(np.quantile(null, 0.95)), "perm_p": float(np.mean(np.array(null) >= r)),
            "cyc_rms_bb": scale * math.sqrt(max(float(ca @ cb) / npairs, 0)) / 100,
            "grad_rms_bb": scale * math.sqrt(max(float(ga @ gb) / npairs, 0)) / 100,
            "cyclic_matrix_bb": (scale * cyc_full / 100).round(3).tolist(),
            "role": "measured outcome; never a field-selection criterion"}


# ------------------------------------------------------------------ reference ranking robustness
def reference_rank_diagnostics(mu: np.ndarray, boot_mu: np.ndarray, k: int,
                               unit: str = "round-level joint bootstrap") -> dict[str, Any]:
    """Ranking / cutoff robustness of a reference from a JOINT bootstrap.

    ``boot_mu`` (B x P) must come from resampling independent units (mu_field: one matched round;
    mu_swiss: one tournament) with one weight vector for
    the whole bot vector (cross-bot covariance kept). Per-bot rank intervals and top-k
    probabilities are diagnostics of the ordering, not independent per-bot inferences.
    """
    mu = np.asarray(mu, float)
    boot_mu = np.asarray(boot_mu, float)
    b, p = boot_mu.shape
    order = np.argsort(-mu, kind="stable")
    top = set(order[:k].tolist())
    ranks = np.argsort(np.argsort(-boot_mu, axis=1, kind="stable"), axis=1, kind="stable") + 1
    in_top = ranks <= k
    same_top = float(np.mean([set(np.flatnonzero(row).tolist()) == top for row in in_top]))
    i_k, i_k1 = int(order[k - 1]), int(order[k])  # point-estimate k-th and (k+1)-th bots
    pair_gap = boot_mu[:, i_k] - boot_mu[:, i_k1]
    srt = -np.sort(-boot_mu, axis=1)
    os_gap = srt[:, k - 1] - srt[:, k]
    rho = [float(np.corrcoef(np.argsort(np.argsort(-mu)), np.argsort(np.argsort(-row)))[0, 1]) for row in boot_mu]
    return {
        "bootstrap_resamples": b, "k": k,
        "p_same_top_k_set": same_top,
        "gap_at_cutoff": float(mu[i_k] - mu[i_k1]),
        "gap_at_cutoff_pair_ci95": [float(np.quantile(pair_gap, 0.025)), float(np.quantile(pair_gap, 0.975))],
        "p_cutoff_pair_order_reversed": float(np.mean(pair_gap < 0)),
        "gap_order_statistic_ci95": [float(np.quantile(os_gap, 0.025)), float(np.quantile(os_gap, 0.975))],
        "spearman_point_vs_bootstrap_median": float(np.median(rho)),
        "per_bot": {"rank_lo95": np.quantile(ranks, 0.025, axis=0).tolist(),
                    "rank_hi95": np.quantile(ranks, 0.975, axis=0).tolist(),
                    "p_top_k": in_top.mean(0).tolist()},
        "role": f"ranking/gap robustness from a {unit}; primary per-bot SE is analytic",
    }
