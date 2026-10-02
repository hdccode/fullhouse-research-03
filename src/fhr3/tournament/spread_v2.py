"""Corrected NLHE6 spread selection: split-sample selection and validation (analysis only).

The retired spread field (``retired_spread_selection_bias``) chose its leaders, excluded the band
near the cut and measured the rank-6/7 gap on the SAME noisy pool estimates. The gap regressed
from 16.8 BB to 0.71 BB under the independent reference. This module separates the steps
(protocol: ``configs/fhr3b/matrix.yaml: core_fhr4.spread_v2``, pre-registered before the
validation half was read):

1. **Split.** The existing pool calibration (2,000 independent rounds; every bot plays one match
   per round) is split by round parity: even rounds select, odd rounds validate.
2. **Select** on the selection half only:
   * leaders: the six best by selection-half mu, with no near-duplicate leaders and at most 3
     per archetype;
   * eligible non-leaders: mu_b <= mu_L6 - m * sqrt(se_L6^2 + se_b^2), with m relaxed in logged
     steps only if fewer than 54 qualify;
   * thinning: the eligible surplus is removed by redundancy (smallest minimum parameter
     distance first), never removing the last non-leader of a style or archetype.
3. **Validate** on the held-out half only, once. It is pass/fail and never optimised. A joint
   round-level bootstrap over the candidate's 60 bots gives:
   * P(the six leaders are the top 6), required >= 0.95. This equals a one-sided 95% lower
     bound > 0 on G = min(leaders) - max(non-leaders).
   * The point top 6 must equal the leaders.
   * No non-leader may have P(top 6) > 0.05.

Validation uses pool-context estimates, because opponents come from the 96-bot pool. The
definitive check is a fresh, independent field-relative mu_field reference under the
pre-registered spread rule.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from fhr3.configs.experiment import canonical_hash
from fhr3.tournament.calibration import analyse_calibration, calibration_digest, load_calibration
from fhr3.tournament.diagnostics import param_distance, param_vectors, reference_rank_diagnostics
from fhr3.tournament.experiments import Profile, load_matrix
from fhr3.tournament.fields import subset
from fhr3.tournament.reference import split_by_round

BB = 100.0


def protocol(prof: Profile) -> dict[str, Any]:
    return load_matrix(prof.config_root)["core_fhr4"]["spread_v2"]


def protocol_hash(prof: Profile) -> str:
    return canonical_hash(protocol(prof))[:16]


def out_dir(reports: Path, mode: str = "nlhe6") -> Path:
    return reports / "field-calibration" / mode / "spread_v2"


def _halves(root: Path, prof: Profile, mode: str) -> tuple[Any, list, list]:
    spec = prof.calibration_spec(mode, "pool")
    p = protocol(prof)
    if spec.calib_id != p["pool_calibration"]:
        raise ValueError(f"pool calibration {spec.calib_id} != protocol {p['pool_calibration']}")
    if p["split"]["rule"] != "round_parity":
        raise ValueError("only the round_parity split is implemented")
    rounds = split_by_round(load_calibration(root, spec))
    sel = [t for t in rounds if int(t.column("round")[0].as_py()) % 2 == 0]
    val = [t for t in rounds if int(t.column("round")[0].as_py()) % 2 == 1]
    return spec, sel, val


def _estimates(tables: list, bots: list[str], n_boot: int = 0, seed: int = 0) -> dict[str, Any]:
    res = analyse_calibration(tables, bots, n_boot=n_boot, seed=seed)
    return {"mu": {b: float(res["mu"][i]) for i, b in enumerate(bots)},
            "se": {b: float(res["se"][i]) for i, b in enumerate(bots)},
            "n_matches": int(res["n_matches"].min()), "rounds": len(tables), "boot_mu": res["boot_mu"]}


def select(root: Path, prof: Profile, reports: Path, mode: str = "nlhe6") -> dict[str, Any]:
    """Selection on the SELECTION half only. Writes selection.json + candidate_manifest.json."""
    from fhr3.tournament.behaviour import load_behaviour

    p = protocol(prof)
    sp = p["selection"]
    spec, sel, _ = _halves(root, prof, mode)
    pool = spec.field
    bots = sorted(pool.bot_ids)
    est = _estimates(sel, bots)
    mu, se = est["mu"], est["se"]
    arch = {b["bot_id"]: b["meta"]["archetype"] for b in pool.bots}
    style = {r["bot_id"]: r["style"] for r in load_behaviour(reports, mode)}
    vecs = param_vectors(pool.bots)
    ranked = sorted(bots, key=lambda b: (-mu[b], b))
    log: list[dict[str, Any]] = []

    leaders: list[str] = []
    for b in ranked:
        if len(leaders) == int(sp["k"]):
            break
        why = None
        if sum(arch[x] == arch[b] for x in leaders) >= int(sp["leader_archetype_cap"]):
            why = "leader archetype cap"
        elif any(param_distance(vecs, b, x) < float(sp["leader_near_dup"]) for x in leaders):
            why = "near-duplicate of a leader"
        log.append({"step": "leader", "bot": b, "mu_sel_bb": mu[b] / BB, "accepted": why is None, "reason": why})
        if why is None:
            leaders.append(b)
    last = min(leaders, key=lambda b: mu[b])
    quota = int(sp["n"]) - int(sp["k"])

    m = float(sp["separation_se"])
    while True:
        eligible = [b for b in ranked if b not in leaders and mu[b] <= mu[last] - m * math.hypot(se[last], se[b])]
        ok = len(eligible) >= quota
        log.append({"step": "separation", "separation_se": m, "eligible": len(eligible), "feasible": ok})
        if ok or m - float(sp["relax_step"]) < float(sp["relax_floor"]) - 1e-9:
            break
        m -= float(sp["relax_step"])
    if len(eligible) < quota:
        raise ValueError("spread_v2 selection infeasible at the relaxation floor")

    keep = list(eligible)
    while len(keep) > quota:
        sty = Counter(style[b] for b in keep)
        arc = Counter(arch[b] for b in keep)
        removable = [b for b in keep if sty[style[b]] > 1 and arc[arch[b]] > 1]

        def redundancy(b: str) -> tuple[float, str]:
            return (min(param_distance(vecs, b, c) for c in keep + leaders if c != b), b)

        drop = min(removable, key=redundancy)
        log.append({"step": "thin", "bot": drop, "min_param_distance": redundancy(drop)[0], "mu_sel_bb": mu[drop] / BB})
        keep.remove(drop)
    field_ids = sorted(leaders + keep)
    best_non = max(keep, key=lambda b: mu[b])
    nd = [(a, b) for i, a in enumerate(keep) for b in keep[i + 1:] if param_distance(vecs, a, b) < sp["leader_near_dup"]]
    construction = {
        "method": "split-sample spread (spread_v2): select on even pool rounds, validate on odd rounds",
        "protocol_hash": protocol_hash(prof), "pool_calibration_id": spec.calib_id,
        "pool_calibration_digest": calibration_digest(root, spec), "selection_rounds": "even (1000)",
        "leaders": leaders, "separation_se_used": m, "separation_se_target": float(sp["separation_se"]),
        "selection_gap_bb": (mu[last] - mu[best_non]) / BB, "replaces": p["replaces"], "K": int(sp["k"])}
    fm = subset(pool, f"{mode}-{p['field_name']}", "spread", field_ids, construction)
    non_sel = [mu[b] / BB for b in keep]
    summary = {
        "protocol": p, "protocol_hash": protocol_hash(prof), "data": {
            "pool_calibration": spec.calib_id, "selection_rounds": est["rounds"],
            "selection_matches_per_bot": est["n_matches"], "median_se_bb": float(np.median(list(se.values()))) / BB},
        "leaders": [{"bot": b, "archetype": arch[b], "style": style[b], "mu_sel_bb": mu[b] / BB, "se_sel_bb": se[b] / BB}
                    for b in leaders],
        "separation_se_used": m, "selection_gap_bb": (mu[last] - mu[best_non]) / BB,
        "best_non_leader_sel": {"bot": best_non, "mu_sel_bb": mu[best_non] / BB},
        "excluded_above_band": [b for b in ranked if b not in leaders and b not in eligible],
        "thinned": [x["bot"] for x in log if x["step"] == "thin"],
        "non_leaders": {"n": len(keep), "styles": dict(Counter(style[b] for b in keep)),
                        "archetypes": dict(Counter(arch[b] for b in keep)),
                        "mu_sel_range_bb": [min(non_sel), max(non_sel)], "near_duplicate_pairs": len(nd)},
        "leader_checks": {"near_duplicate_pairs": sum(param_distance(vecs, a, b) < sp["leader_near_dup"]
                                                      for i, a in enumerate(leaders) for b in leaders[i + 1:]),
                          "max_per_archetype": max(Counter(arch[b] for b in leaders).values())},
        "candidate": {"field_id": fm.field_id, "field_hash": fm.field_hash, "n": fm.n, "frozen": False},
        "log": log}
    d = out_dir(reports, mode)
    d.mkdir(parents=True, exist_ok=True)
    (d / "selection.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=float) + "\n")
    (d / "candidate_manifest.json").write_text(json.dumps(fm.to_dict(), indent=1, sort_keys=True) + "\n")
    return summary


def validate(root: Path, prof: Profile, reports: Path, mode: str = "nlhe6", force: bool = False) -> dict[str, Any]:
    """Validation on the HELD-OUT half only, once (attempts: 1). Writes validation.json."""
    p = protocol(prof)
    vp = p["validation"]
    d = out_dir(reports, mode)
    sel = json.loads((d / "selection.json").read_text())
    if sel["protocol_hash"] != protocol_hash(prof):
        raise ValueError("selection.json was produced under a different protocol; re-run selection first")
    if (d / "validation.json").exists() and not force:
        raise ValueError(f"{d / 'validation.json'} exists: the protocol allows one validation attempt")
    cand = json.loads((d / "candidate_manifest.json").read_text())
    ids = sorted(b["bot_id"] for b in cand["bots"])
    leaders = [x["bot"] for x in sel["leaders"]]
    spec, _, val = _halves(root, prof, mode)
    allbots = sorted(spec.field.bot_ids)
    est = _estimates(val, allbots, n_boot=int(vp["resamples"]), seed=int(vp["seed"]))
    ix = [allbots.index(b) for b in ids]
    mu = np.array([est["mu"][b] for b in ids]) / BB
    boot = est["boot_mu"][:, ix] / BB
    lmask = np.array([b in leaders for b in ids])
    g_point = float(mu[lmask].min() - mu[~lmask].max())
    g_boot = boot[:, lmask].min(1) - boot[:, ~lmask].max(1)
    diag = reference_rank_diagnostics(mu, boot, int(p["selection"]["k"]))
    p_top = np.asarray(diag["per_bot"]["p_top_k"])
    order = np.argsort(-mu, kind="stable")
    nonl = sorted(((ids[i], float(p_top[i]), float(mu[i])) for i in range(len(ids)) if not lmask[i]),
                  key=lambda x: -x[1])
    crit = {
        "point_top6_equals_leaders": {"value": bool(g_point > 0), "required": bool(vp["require_point_top6_equals_leaders"])},
        "p_leaders_are_top6": {"value": float((g_boot > 0).mean()), "at_least": float(vp["p_leaders_are_top6_at_least"])},
        "max_nonleader_p_top6": {"value": nonl[0][1], "bot": nonl[0][0], "at_most": float(vp["nonleader_p_top6_at_most"])},
    }
    passed = ((not crit["point_top6_equals_leaders"]["required"] or crit["point_top6_equals_leaders"]["value"])
              and crit["p_leaders_are_top6"]["value"] >= crit["p_leaders_are_top6"]["at_least"]
              and crit["max_nonleader_p_top6"]["value"] <= crit["max_nonleader_p_top6"]["at_most"])
    out = {"protocol_hash": protocol_hash(prof), "candidate_field_hash": cand_hash(cand), "validation_rounds": est["rounds"],
           "validation_matches_per_bot": est["n_matches"], "context": vp["context_note"],
           "gap_point_bb": g_point, "gap_lcb95_one_sided_bb": float(np.quantile(g_boot, 0.05)),
           "gap_boot_quantiles_bb": [float(np.quantile(g_boot, q)) for q in (0.05, 0.25, 0.5, 0.75, 0.95)],
           "p_same_top6_set": diag["p_same_top_k_set"], "p_rank6_rank7_reversal": diag["p_cutoff_pair_order_reversed"],
           "leaders_val": [{"bot": b, "mu_val_bb": float(mu[ids.index(b)]), "p_top6": float(p_top[ids.index(b)])}
                           for b in leaders],
           "top10_val": [{"rank": r + 1, "bot": ids[i], "leader": bool(lmask[i]), "mu_val_bb": float(mu[i]),
                          "p_top6": float(p_top[i])} for r, i in enumerate(order[:10])],
           "nonleaders_p_top6_above_zero": [{"bot": b, "p_top6": pt, "mu_val_bb": m_} for b, pt, m_ in nonl if pt > 0],
           "criteria": crit, "passed": bool(passed),
           "decision": "CANDIDATE PASSES held-out validation (not frozen; human decision)" if passed else
                       "CANDIDATE FAILS held-out validation: stop (attempts: 1); no re-selection on this split"}
    (d / "validation.json").write_text(json.dumps(out, indent=1, sort_keys=True, default=float) + "\n")
    return out


def cand_hash(cand: dict[str, Any]) -> str:
    return cand.get("field_hash") or hashlib.sha256(json.dumps(cand, sort_keys=True).encode()).hexdigest()[:16]
