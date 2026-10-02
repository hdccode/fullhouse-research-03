"""mu_field reference estimation for analysis (outside the engine source hash).

Bootstrap unit: ONE complete matched round. Field-reference rounds are independent by
construction: partitions, decks and decisions are keyed by round, agents are stateless and
every match starts from fresh stacks. Measured on the 2,000-round NLHE6 pool calibration:

* pooled lag-1 autocorrelation of per-bot deltas = 0.004, inside the +/-0.0046 noise band;
* variance ratio of 10-round block means to single rounds = 1.00.

So no blocking is justified. Every resample draws one multinomial weight vector over rounds and
applies it to the whole bot vector: within-round covariance and the zero-sum structure are kept.
The analytic sd / sqrt(matches) stays the primary per-bot SE. The joint resamples feed only
ranking, gap, top-k and reference-uncertainty diagnostics.

Stored chunks (``chunk_rounds`` = 10, part of the calibration identity) are a storage unit
only: they are split into rounds here, so identities and stored data are unchanged.

``mu_field`` is long-run expected performance against random partitions of the controlled
field under the specified match semantics (chips per ordinary-equivalent 400-hand match).
It is an estimate, not an oracle label and not universal poker skill.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa

from fhr3.tournament.calibration import (
    CalibrationSpec,
    analyse_calibration,
    load_calibration,
    verify_calibration_lanes,
)
from fhr3.tournament.diagnostics import reference_rank_diagnostics

BOOTSTRAP_UNIT = "one complete matched round (joint across all bots)"


def split_by_round(tables: Sequence[pa.Table]) -> list[pa.Table]:
    """One table per calibration round, in round order (the bootstrap unit)."""
    out: list[tuple[int, pa.Table]] = []
    for t in tables:
        r = np.asarray(t.column("round"))
        for v in np.unique(r):
            out.append((int(v), t.filter(pa.array(r == v))))
    out.sort(key=lambda x: x[0])
    rounds = [r for r, _ in out]
    if len(set(rounds)) != len(rounds):
        raise ValueError("a calibration round appears in more than one chunk")
    return [t for _, t in out]


def estimate_field_reference(root: Path, spec: CalibrationSpec, k: int, n_boot: int = 1000,
                             seed: int = 20260929) -> dict[str, Any] | None:
    """mu_field + joint round-bootstrap diagnostics, or None if nothing is stored."""
    chunks = load_calibration(root, spec)
    if not chunks:
        return None
    n_lane_chunks = verify_calibration_lanes(root, spec)
    rounds = split_by_round(chunks)
    bots = sorted(spec.field.bot_ids)
    res = analyse_calibration(rounds, bots, n_boot=n_boot, seed=seed, lanes=spec.lanes)
    res["diag"] = reference_rank_diagnostics(res["mu"], res["boot_mu"], k)
    res["bootstrap_unit"] = BOOTSTRAP_UNIT
    res["bootstrap_units"] = len(rounds)
    res["lane_chunks_verified"] = n_lane_chunks
    return res


# ------------------------------------------------------------------ pre-registered extension rule
def mu_field_extension_rule(field_kind: str, bots: Sequence[str], mu: np.ndarray, diag: dict[str, Any],
                            construction: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    """Pre-registered 250 -> 500 rule for one field (configs: core_fhr4.extension_rules.mu_field).

    Uses only the joint round-bootstrap diagnostics. Returns the evaluated criteria and
    ``extend``; it never runs anything. crowded_cutoff is defined on the manifest structure:
    "outside" = every bot in NEITHER the designed leaders (top_ids) NOR the designed ranks-4-15
    crowd (crowd_ids), so the leaders are never counted as outside.
    """
    p_top = np.asarray(diag["per_bot"]["p_top_k"], float)
    order = np.argsort(-np.asarray(mu, float), kind="stable")
    rank = np.empty(len(bots), int)
    rank[order] = np.arange(1, len(bots) + 1)
    ix = {b: i for i, b in enumerate(bots)}
    r = rules[field_kind]
    crit: dict[str, Any] = {}
    if field_kind in ("spread", "separated_control"):
        crit["p_same_top_k_set"] = {"value": diag["p_same_top_k_set"], "trigger_below": r["p_same_top_k_set_below"]}
        crit["p_cutoff_pair_order_reversed"] = {"value": diag["p_cutoff_pair_order_reversed"],
                                                "trigger_above": r["p_rank6_rank7_reversal_above"]}
        trig = [diag["p_same_top_k_set"] < r["p_same_top_k_set_below"],
                diag["p_cutoff_pair_order_reversed"] > r["p_rank6_rank7_reversal_above"]]
    elif field_kind == "crowded_cutoff":
        leaders = list(construction["top_ids"])
        crowd = set(construction["crowd_ids"])
        outside = [b for b in bots if b not in crowd and b not in leaders]
        weak_leaders = {b: float(p_top[ix[b]]) for b in leaders if p_top[ix[b]] < r["leader_p_top_k_below"]}
        leaking = {b: float(p_top[ix[b]]) for b in outside if p_top[ix[b]] > r["outside_p_top_k_above"]}
        crit["designed_leaders_below"] = {"bots": weak_leaders, "threshold": r["leader_p_top_k_below"],
                                          "leaders": leaders}
        crit["outside_leaders_and_crowd_above"] = {"bots": leaking, "threshold": r["outside_p_top_k_above"],
                                                   "n_outside": len(outside)}
        trig = [bool(weak_leaders), bool(leaking)]
    elif field_kind == "style_diverse":
        top = {b: float(p_top[ix[b]]) for b in bots
               if rank[ix[b]] <= r["top_ranks"] and p_top[ix[b]] < r["top_p_top_k_below"]}
        low = {b: float(p_top[ix[b]]) for b in bots
               if rank[ix[b]] >= r["low_rank_from"] and p_top[ix[b]] > r["low_p_top_k_above"]}
        crit["point_ranks_1_to_4_below"] = {"bots": top, "threshold": r["top_p_top_k_below"]}
        crit["point_ranks_10_plus_above"] = {"bots": low, "threshold": r["low_p_top_k_above"]}
        trig = [bool(top), bool(low)]
    else:
        return {"field_kind": field_kind, "rule": "none (not a core field)", "extend": False}
    return {"field_kind": field_kind, "criteria": crit, "triggered": trig, "extend": bool(any(trig)),
            "action": "extend to 500 matched rounds (append-only)" if any(trig) else "keep 250 matched rounds",
            "note": "pre-registered rule; applied mechanically, never executed automatically"}


def wilson_half_width_max(n: int, z: float = 1.959963984540054) -> float:
    """Largest possible 95% Wilson half-width with n tournaments (at p = 0.5)."""
    return z * math.sqrt(0.25 / n + z * z / (4 * n * n)) / (1 + z * z / n)


def mu_swiss_extension_rule(bots: Sequence[dict[str, Any]], n: int, field_kind: str, construction: dict[str, Any],
                            rules: dict[str, Any]) -> dict[str, Any]:
    """Pre-registered 100 -> 200 rule for one field (configs: core_fhr4.extension_rules.mu_swiss).

    Extend if a DECISION-RELEVANT boundary bot (P(qualify) in [band]) has a 95% Wilson half-width
    above ``half_width_above``. In crowded_cutoff the designed near-equal crowd is excluded: its
    ambiguity is the object of study. The second clause ("reference uncertainty prevents
    interpretation of the main results") is a reviewed judgement, recorded as ``manual_clause``.
    """
    lo_b, hi_b = rules["p_qualify_band"]
    thr = float(rules["half_width_above"])
    excluded = set(construction.get("crowd_ids", [])) if field_kind == "crowded_cutoff" else set()
    relevant, flagged = [], {}
    for b in bots:
        if lo_b <= b["p_qualify"] <= hi_b and b["bot_id"] not in excluded:
            relevant.append(b["bot_id"])
            hw = (b["p_qualify_wilson_hi"] - b["p_qualify_wilson_lo"]) / 2
            if hw > thr:
                flagged[b["bot_id"]] = hw
    cap = wilson_half_width_max(n)
    return {"field_kind": field_kind, "n_tournaments": n, "decision_relevant_boundary_bots": relevant,
            "excluded_designed_crowd": sorted(excluded), "flagged": flagged, "threshold": thr,
            "max_possible_wilson_half_width_at_n": cap,
            "rule_can_trigger_at_n": bool(cap > thr),
            "manual_clause": "extend also if reference uncertainty prevents interpretation of the main results "
                             "(reviewed judgement, record the reason)",
            "extend": bool(flagged), "note": "pre-registered rule; evaluated, never executed"}
