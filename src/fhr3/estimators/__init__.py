"""Estimators of the matched-block estimand (see base.py for the contract)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fhr3.eval.matched import HandEstimator

KNOWN = ("allin_ev", "mivat", "aivat")


def build_estimators(settings: Mapping[str, Any], adapter: Any, root_seed: int | None = None) -> list[HandEstimator]:
    """Instantiate the per-hand estimators enabled in ``estimators:`` config."""
    out: list[HandEstimator] = []
    unknown = set(settings) - set(KNOWN)
    if unknown:
        raise ValueError(f"unknown estimators {sorted(unknown)}; known {KNOWN}")
    for name, opts in settings.items():
        opts = dict(opts or {})
        if not opts.pop("enabled", True):
            continue
        if name == "allin_ev":
            from fhr3.estimators.allin_ev import AllInEVEstimator

            out.append(AllInEVEstimator(adapter.showdown, **opts))
        else:
            from fhr3.estimators.vat import build_vat_estimator

            out.append(build_vat_estimator(name, adapter, opts, root_seed))
    return out
