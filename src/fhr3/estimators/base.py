"""Estimator abstraction.

Every estimator maps one matched block to a scalar estimate of the *same*
estimand: E[D] = E[sum_s (X_A,s - X_B,s)] under the matched protocol. Variance
reduction (all-in EV, MIVAT, AIVAT) may change the variance but must never
change that expectation; each estimator must ship with a mean-preservation test
(``tests/test_estimators.py``) before its column is populated.

Any fitted/learned component (e.g. a value function for AIVAT) must be fitted on
data disjoint from the evaluation blocks and frozen before evaluation.
"""

from __future__ import annotations

from typing import Protocol

from fhr3.eval.matched import MatchedBlockResult


class Estimator(Protocol):
    name: str
    column: str  # Parquet column populated by this estimator

    def estimate(self, result: MatchedBlockResult) -> float | None: ...


class RawMatchedEstimator:
    """Unadjusted matched difference: the realized D. Column ``raw_estimator_D``."""

    name = "raw"
    column = "raw_estimator_D"

    def estimate(self, result: MatchedBlockResult) -> float | None:
        return result.D


# Planned (RQ6), deliberately unimplemented until raw matched evaluation is trusted:
#   AllInEVEstimator -> allin_ev_D   (needs per-hand all-in equity from the adapter)
#   MIVATEstimator   -> mivat_D      (adapt PVAT; frozen value function)
#   AIVATEstimator   -> aivat_D      (adapt PVAT; needs DistributionAgent.action_distribution)
ESTIMATORS: dict[str, Estimator] = {"raw": RawMatchedEstimator()}
