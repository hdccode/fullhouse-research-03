"""Estimator contract.

Every estimator maps one hand (``HandContext``) to the candidate's estimated
payoff with the *same expectation* as the realized payoff, so the block-level
estimator D (sum over seats of A-minus-B estimates) targets the same estimand as
the raw D. Implementations: ``allin_ev.AllInEVEstimator``,
``vat.VATEstimator`` (MIVAT/AIVAT via PVAT). See docs/estimators.md.

Any fitted component must be fitted on data disjoint from evaluation blocks and
frozen (sha256-pinned) before evaluation.
"""

from __future__ import annotations

from fhr3.eval.matched import HandContext, HandEstimator


class RawMatchedEstimator:
    """The realized payoff (identity estimator; column ``raw_estimator_D`` = D)."""

    name = "raw"
    needs_decision_log = False

    def estimate(self, ctx: HandContext) -> float:
        return float(ctx.outcome.payoffs_chips[ctx.candidate_position])


__all__ = ["HandContext", "HandEstimator", "RawMatchedEstimator"]
