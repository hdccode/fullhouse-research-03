"""RQ7 experiment engine: coverage and stopping of three inference procedures on the SAME
block streams.

Methods (kept strictly distinct):

``fixed``  Student-t interval evaluated ONCE, at the pre-committed n = ``fixed_n``.
           Valid (exactly for Gaussian D, approximately otherwise) at that single look.
``peek``   The same fixed-n t-interval recomputed after every block from ``min_n`` on,
           stopping at the first exclusion of 0. Invalid under optional stopping; it is
           the comparator that shows what naive monitoring does.
``asymp``  The asymptotic confidence sequence of ``fhr3.analysis.sequential``
           (Waudby-Smith et al. 2024, two-sided normal mixture with plug-in variance,
           tuned at ``t_star``). Time-uniform coverage holds ASYMPTOTICALLY under finite
           variance; it is not a finite-sample guarantee.

Samplers draw whole matched blocks (never hands):

``normal``, ``t3``            synthetic IID, SD = ``scale``
``bootstrap:<pairing dir>``   IID resampling of the centred block residuals D_i - mean(D)
                              of ONE frozen pairing corpus
``permutation:<pairing dir>`` a uniformly random ordering of the corpus itself (without
                              replacement); the true mean is the corpus mean exactly

A known location shift ``true_mean`` is added to centred residuals (bootstrap / synthetic),
so the residual distribution is unchanged. ``effect_d`` sets ``true_mean = d * sigma``.

Replicate r uses ``np.random.default_rng(SeedSequence(seed, spawn_key=(r,)))``: results
do not depend on batch size, worker count or order, and the same seed gives the same
streams for every method and for every min_n (paired comparisons across cells).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
from scipy import stats as sps

from fhr3.analysis.sequential import METHOD_VERSION as ASYMP_VERSION
from fhr3.analysis.sequential import asymp_radius, running_mean_sd

ENGINE_VERSION = "fhr3-rq7-engine-1"
METHODS = ("fixed", "peek", "asymp")
DEFAULT_CHECKPOINTS = (1_000, 10_000, 25_000, 100_000, 250_000)


# ------------------------------------------------------------------ samplers
class Sampler:
    name: str
    sigma: float  # SD of one block under this sampler (for effect sizes)
    true_mean: float
    max_n: int | None = None  # permutation streams cannot exceed the corpus size

    def draw(self, rng: np.random.Generator, n: int) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError

    def with_true_mean(self, mu: float) -> Sampler:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class SyntheticSampler(Sampler):
    kind: str  # "normal" | "t3"
    scale: float = 1.0
    true_mean: float = 0.0

    @property
    def name(self) -> str:  # type: ignore[override]
        return self.kind

    @property
    def sigma(self) -> float:  # type: ignore[override]
        return self.scale

    def draw(self, rng: np.random.Generator, n: int) -> np.ndarray:
        if self.kind == "normal":
            z = rng.standard_normal(n)
        else:  # Student t, 3 d.o.f., rescaled to unit variance (finite variance, infinite kurtosis)
            z = rng.standard_t(3, n) / math.sqrt(3.0)
        return self.true_mean + self.scale * z

    def with_true_mean(self, mu: float) -> SyntheticSampler:
        return SyntheticSampler(self.kind, self.scale, mu)


def load_pairing_d(path: str) -> np.ndarray:
    """Valid block D of ONE pairing directory, in block-id order (refuses pooled pairings)."""
    import pyarrow.compute as pc

    from fhr3.io.store import read_blocks

    t = read_blocks(path, columns=["config_hash", "pairing_id", "block_id", "valid", "D"])
    pids = set(t.column("pairing_id").to_pylist())
    if len(pids) != 1:
        raise ValueError(f"{path}: expected one pairing directory, found pairings {sorted(pids)}")
    t = t.filter(t.column("valid"))
    order = np.argsort(np.asarray(t.column("block_id").to_numpy()))
    del pc
    return np.asarray(t.column("D").to_numpy(zero_copy_only=False), dtype=float)[order]


@dataclass
class BootstrapSampler(Sampler):
    source: str
    residuals: np.ndarray = field(repr=False)
    sigma_: float = 0.0
    true_mean: float = 0.0

    @classmethod
    def from_path(cls, path: str) -> BootstrapSampler:
        d = load_pairing_d(path)
        return cls(path, d - d.mean(), float(d.std(ddof=1)))

    @property
    def name(self) -> str:  # type: ignore[override]
        return f"bootstrap:{self.source}"

    @property
    def sigma(self) -> float:  # type: ignore[override]
        return self.sigma_

    def draw(self, rng: np.random.Generator, n: int) -> np.ndarray:
        return self.true_mean + self.residuals[rng.integers(0, self.residuals.size, n)]

    def with_true_mean(self, mu: float) -> BootstrapSampler:
        return BootstrapSampler(self.source, self.residuals, self.sigma_, mu)


@dataclass
class PermutationSampler(Sampler):
    source: str
    d: np.ndarray = field(repr=False)

    @classmethod
    def from_path(cls, path: str) -> PermutationSampler:
        return cls(path, load_pairing_d(path))

    @property
    def name(self) -> str:  # type: ignore[override]
        return f"permutation:{self.source}"

    @property
    def sigma(self) -> float:  # type: ignore[override]
        return float(self.d.std(ddof=1))

    @property
    def true_mean(self) -> float:  # type: ignore[override]
        return float(self.d.mean())

    @property
    def max_n(self) -> int:  # type: ignore[override]
        return int(self.d.size)

    def draw(self, rng: np.random.Generator, n: int) -> np.ndarray:
        if n > self.d.size:
            raise ValueError(f"permutation stream of {n} blocks from a corpus of {self.d.size}")
        return self.d[rng.permutation(self.d.size)[:n]]

    def with_true_mean(self, mu: float) -> PermutationSampler:
        raise ValueError("a permutation stream has a fixed true mean (the corpus mean)")


def make_sampler(spec: str, scale: float = 1.0) -> Sampler:
    if spec in ("normal", "t3"):
        return SyntheticSampler(spec, scale)
    if spec.startswith("bootstrap:"):
        return BootstrapSampler.from_path(spec.split(":", 1)[1])
    if spec.startswith("permutation:"):
        return PermutationSampler.from_path(spec.split(":", 1)[1])
    raise ValueError(f"unknown sampler {spec!r} (normal | t3 | bootstrap:<pairing dir> | permutation:<pairing dir>)")


# ------------------------------------------------------------------ design + evaluation
@dataclass(frozen=True)
class Design:
    sampler: str
    true_mean: float
    effect_d: float | None
    sigma: float
    reps: int
    n_max: int
    t_star: float
    min_n: int
    fixed_n: int
    alpha: float
    seed: int
    checkpoints: tuple[int, ...]
    engine_version: str = ENGINE_VERSION
    asymp_method_version: str = ASYMP_VERSION

    def hash(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:16]


def replicate_rng(seed: int, r: int) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(r,)))


def _first(mask: np.ndarray) -> np.ndarray:
    """Index of the first True along axis 1, -1 if none."""
    any_ = mask.any(axis=1)
    return np.where(any_, mask.argmax(axis=1), -1)


def evaluate(x: np.ndarray, design: Design) -> list[dict[str, Any]]:
    """Per-replicate outcomes for every method on the same streams ``x`` (reps x n_max)."""
    m, n = x.shape
    mu, a, lo_i = design.true_mean, design.alpha, design.min_n - 1
    t, mean, sd = running_mean_sd(x)
    t_rad = sps.t.ppf(1 - a / 2, np.maximum(t - 1, 1)) * sd / np.sqrt(t)
    radii = {"peek": t_rad, "asymp": asymp_radius(t, sd, a, design.t_star)}
    sign_mu = float(np.sign(mu))
    cps = [c for c in design.checkpoints if c <= n]
    rows: list[dict[str, Any]] = [dict() for _ in range(m * len(METHODS))]
    out = []
    for method in METHODS:
        rec: dict[str, np.ndarray] = {}
        if method == "fixed":
            j = design.fixed_n - 1
            rad, mj = t_rad[:, j], mean[:, j]
            miss = np.abs(mj - mu) > rad
            excl = np.abs(mj) > rad
            rec["ever_miss"] = miss  # a single look: "ever" == at fixed_n
            rec["final_miss"] = miss
            rec["decision_time"] = np.where(excl, design.fixed_n, -1)
            rec["decision_sign"] = np.where(excl, np.sign(mj), 0.0)
            rec["first_correct_sign_time"] = np.where(excl & (np.sign(mj) == sign_mu) & (sign_mu != 0), design.fixed_n, -1)
            rec["first_miss_time"] = np.where(miss, design.fixed_n, -1)
            widths = {c: (2 * t_rad[:, c - 1] if c == design.fixed_n else np.full(m, np.nan)) for c in cps}
        else:
            rad = radii[method][:, lo_i:]
            mm = mean[:, lo_i:]
            miss = np.abs(mm - mu) > rad
            excl = np.abs(mm) > rad
            fm, fd = _first(miss), _first(excl)
            correct = excl & (np.sign(mm) == sign_mu) if sign_mu != 0 else np.zeros_like(excl)
            fc = _first(correct)
            rows_idx = np.arange(m)
            rec["ever_miss"] = fm >= 0
            rec["final_miss"] = miss[:, -1]
            rec["first_miss_time"] = np.where(fm >= 0, fm + design.min_n, -1)
            rec["decision_time"] = np.where(fd >= 0, fd + design.min_n, -1)
            rec["decision_sign"] = np.where(fd >= 0, np.sign(mm[rows_idx, np.maximum(fd, 0)]), 0.0)
            rec["first_correct_sign_time"] = np.where(fc >= 0, fc + design.min_n, -1)
            widths = {c: 2 * radii[method][:, c - 1] for c in cps}
        for i in range(m):
            r = {"method": method,
                 "ever_miss_true_mean": bool(rec["ever_miss"][i]), "final_miss_true_mean": bool(rec["final_miss"][i]),
                 "first_miss_time": int(rec["first_miss_time"][i]),
                 "decision_time": int(rec["decision_time"][i]), "decision_sign": int(rec["decision_sign"][i]),
                 "first_correct_sign_time": int(rec["first_correct_sign_time"][i]),
                 "censored": bool(rec["decision_time"][i] < 0)}
            # a decision is wrong if it excludes 0 on the side opposite to the true mean;
            # under the null (mu = 0) every decision is an error of the "wrong-sign/false" kind
            r["wrong_decision"] = bool(r["decision_sign"] != 0 and (sign_mu == 0 or r["decision_sign"] != sign_mu))
            for c, w in widths.items():
                r[f"width_at_{c}"] = float(w[i])
            out.append(r)
    del rows
    return out


def _run_chunk(args: tuple[Design, Any, list[int]]) -> list[dict[str, Any]]:
    design, sampler, reps = args
    x = np.stack([sampler.draw(replicate_rng(design.seed, r), design.n_max) for r in reps])
    res = evaluate(x, design)
    m = len(reps)
    for k, row in enumerate(res):
        row["rep"] = reps[k % m]
    return res


def run_cell(design: Design, sampler: Sampler, workers: int = 1, chunk: int = 8) -> list[dict[str, Any]]:
    if design.min_n < 2 or design.min_n > design.n_max or not (design.min_n <= design.fixed_n <= design.n_max):
        raise ValueError("need 2 <= min_n <= fixed_n <= n_max")
    if sampler.max_n is not None and design.n_max > sampler.max_n:
        raise ValueError(f"n_max {design.n_max} exceeds the source corpus ({sampler.max_n} blocks)")
    jobs = [(design, sampler, list(range(s, min(s + chunk, design.reps)))) for s in range(0, design.reps, chunk)]
    if workers <= 1:
        parts = [_run_chunk(j) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            parts = list(ex.map(_run_chunk, jobs))
    rows = [r for p in parts for r in p]
    rows.sort(key=lambda r: (METHODS.index(r["method"]), r["rep"]))
    return rows


# ------------------------------------------------------------------ summaries
def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return c - h, c + h


def summarize(rows: Sequence[dict[str, Any]], design: Design) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for method in METHODS:
        rs = [r for r in rows if r["method"] == method]
        n = len(rs)
        miss = sum(r["ever_miss_true_mean"] for r in rs)
        fmiss = sum(r["final_miss_true_mean"] for r in rs)
        dec = [r for r in rs if not r["censored"]]
        wrong = sum(r["wrong_decision"] for r in rs)
        st = np.array([r["decision_time"] for r in dec], dtype=float)
        ct = np.array([r["first_correct_sign_time"] for r in rs if r["first_correct_sign_time"] > 0], dtype=float)
        q = (lambda a: {str(p): float(np.quantile(a, p)) for p in (0.1, 0.25, 0.5, 0.75, 0.9)} if a.size else {})
        s: dict[str, Any] = {
            "reps": n,
            # time-uniform for peek/asymp (any n in [min_n, n_max]); the single look for fixed
            "miscoverage": miss / n, "miscoverage_wilson95": wilson(miss, n),
            "miscoverage_mc_se": math.sqrt(max(miss / n * (1 - miss / n), 1e-12) / n),
            "final_n_miscoverage": fmiss / n,
            "decision_rate": len(dec) / n, "decision_rate_wilson95": wilson(len(dec), n),
            "censored_rate": 1 - len(dec) / n,
            "wrong_decision_rate": wrong / n, "wrong_decision_wilson95": wilson(wrong, n),
            "decision_time_quantiles": q(st),
            "first_correct_sign_time_quantiles": q(ct),
            "correct_sign_rate": ct.size / n,
        }
        for c in design.checkpoints:
            w = np.array([r.get(f"width_at_{c}", np.nan) for r in rs], dtype=float)
            if np.isfinite(w).any():
                s[f"median_width_at_{c}"] = float(np.nanmedian(w))
        out[method] = s
    return out
