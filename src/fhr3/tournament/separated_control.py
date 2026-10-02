"""Engineered separated-control field: construction and one-shot independent validation.

``separated_control`` is a sanity-check / easy-selection environment, NOT a representative
field sample. Six genuinely stronger agents must be independently verified to be separated from
the remaining 54. The protocol is ``configs/fhr3b/matrix.yaml: core_fhr4.separated_control``,
frozen before the candidate was built and before any validation round existed.

1. **construct.** Uses all 2,000 existing NLHE6 pool-calibration rounds and nothing else.
   * Leaders: the strongest defensible six, with no near-duplicate leaders and at most 3 per
     archetype.
   * Fill: the 54 weakest non-leaders.
   * Coverage repair: a deterministic swap, logged, only if a style or archetype would be
     missing.
   * The manifest is written immutably under configs/fhr3b/fields/nlhe6/separated_control.json.
     It is NOT frozen: publication runs refuse it until FROZEN.yaml lists its hash.
2. **bind.** Records candidate hash + protocol hash + the fresh validation calibration id
   (reports/.../separated_control/binding.json). It must be committed before ``simulate``.
3. **simulate.** Runs 4,000 NEW pool-style rounds under a never-used seed family (resumable;
   the data do not depend on the candidate).
4. **evaluate.** ONE SHOT. A joint round-level bootstrap over the validation rounds, restricted
   to the candidate's 60 bots. It passes only if all of the following hold:
   * the point top 6 equals the leaders;
   * P(leaders are the top 6) >= 0.95;
   * no non-leader has P(top 6) > 0.05;
   * the one-sided 95% LCB of G = min(leaders) - max(non-leaders) is > 0.

   A second evaluation is refused.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from fhr3.configs.experiment import canonical_hash
from fhr3.tournament.calibration import (
    CalibrationSpec,
    analyse_calibration,
    calib_dir,
    calibration_digest,
    load_calibration,
    run_calibration,
)
from fhr3.tournament.diagnostics import param_distance, param_vectors, reference_rank_diagnostics
from fhr3.tournament.experiments import Profile, load_matrix
from fhr3.tournament.fields import FHR3B_CONFIGS, load_field, subset, write_field_immutable
from fhr3.tournament.reference import split_by_round

BB = 100.0
MODE = "nlhe6"


def protocol(prof: Profile) -> dict[str, Any]:
    return load_matrix(prof.config_root)["core_fhr4"]["separated_control"]


def protocol_hash(prof: Profile) -> str:
    return canonical_hash(protocol(prof))[:16]


def out_dir(reports: Path) -> Path:
    return reports / "field-calibration" / MODE / "separated_control"


def manifest_path(prof: Profile) -> Path:
    return prof.config_root / "fields" / MODE / f"{protocol(prof)['field_name']}.json"


def validation_spec(prof: Profile) -> CalibrationSpec:
    """Pool-style calibration of the 96-bot pool under the fresh validation seed family."""
    v = protocol(prof)["validation"]
    pool = prof.calibration_spec(MODE, "pool")
    return CalibrationSpec(pool.mode, pool.field, pool.hands_per_match, pool.stack_policy, str(v["seed_family"]),
                           str(v["namespace"]), int(v["chunk_rounds"]))


# ------------------------------------------------------------------ 1. construction (existing data only)
def construct(root: Path, prof: Profile, reports: Path) -> dict[str, Any]:
    from fhr3.tournament.behaviour import load_behaviour

    p = protocol(prof)
    c = p["construction"]
    spec = prof.calibration_spec(MODE, "pool")
    if spec.calib_id != c["pool_calibration"]:
        raise ValueError(f"pool calibration {spec.calib_id} != protocol {c['pool_calibration']}")
    rounds = split_by_round(load_calibration(root, spec))
    if len(rounds) != 2000:
        raise ValueError(f"expected the 2,000 existing pool rounds, found {len(rounds)}")
    pool = spec.field
    bots = sorted(pool.bot_ids)
    res = analyse_calibration(rounds, bots, n_boot=0)
    mu = {b: float(res["mu"][i]) / BB for i, b in enumerate(bots)}
    se = {b: float(res["se"][i]) / BB for i, b in enumerate(bots)}
    arch = {b["bot_id"]: b["meta"]["archetype"] for b in pool.bots}
    style = {r["bot_id"]: r["style"] for r in load_behaviour(reports, MODE)}
    vecs = param_vectors(pool.bots)
    ranked = sorted(bots, key=lambda b: (-mu[b], b))
    rank = {b: i + 1 for i, b in enumerate(ranked)}
    log: list[dict[str, Any]] = []

    leaders: list[str] = []
    for b in ranked:
        if len(leaders) == int(c["k"]):
            break
        why = None
        if sum(arch[x] == arch[b] for x in leaders) >= int(c["leader_archetype_cap"]):
            why = "leader archetype cap"
        elif any(param_distance(vecs, b, x) < float(c["leader_near_dup"]) for x in leaders):
            why = "near-duplicate of a leader"
        log.append({"step": "leader", "bot": b, "pool_rank": rank[b], "mu_bb": mu[b], "accepted": why is None,
                    "reason": why})
        if why is None:
            leaders.append(b)

    if c["fill"] != "weakest":
        raise ValueError("only fill: weakest is defined")
    quota = int(c["n"]) - int(c["k"])
    non = sorted((b for b in bots if b not in leaders), key=lambda b: (mu[b], b))  # weakest first
    fill, excluded = non[:quota], non[quota:]
    need_styles = set(c["require_styles"])
    need_arch = set(arch.values()) if c["require_archetypes"] == "all" else set(c["require_archetypes"])
    while True:
        chosen = leaders + fill
        miss_s = sorted(need_styles - {style[b] for b in chosen})
        miss_a = sorted(need_arch - {arch[b] for b in chosen})
        if not miss_s and not miss_a:
            break
        want = (lambda b: style[b] == miss_s[0]) if miss_s else (lambda b: arch[b] == miss_a[0])
        cands = [b for b in excluded if want(b)]  # excluded is strongest-last; take the weakest of the class
        if not cands:
            raise ValueError(f"coverage repair impossible for {miss_s or miss_a}")
        add = cands[0]
        drop = max(fill, key=lambda b: (mu[b], b))
        fill.remove(drop)
        fill.append(add)
        excluded.remove(add)
        excluded.append(drop)
        log.append({"step": "coverage_swap", "missing": miss_s or miss_a, "in": add, "out": drop})
    fill.sort(key=lambda b: (mu[b], b))
    ids = sorted(leaders + fill)
    l6 = min(leaders, key=lambda b: mu[b])
    best = max(fill, key=lambda b: mu[b])
    gap = mu[l6] - mu[best]
    lead_d = {f"{a}|{b}": param_distance(vecs, a, b) for i, a in enumerate(leaders) for b in leaders[i + 1:]}
    nd_fill = [[a, b] for i, a in enumerate(fill) for b in fill[i + 1:] if param_distance(vecs, a, b) < c["leader_near_dup"]]
    construction = {
        "method": "engineered separated control: strongest defensible six leaders + 54 weakest pool bots",
        "representative": False, "protocol_hash": protocol_hash(prof), "pool_calibration_id": spec.calib_id,
        "pool_calibration_digest": calibration_digest(root, spec), "construction_rounds": 2000,
        "leaders": leaders, "K": int(c["k"]), "construction_gap_bb": gap,
        "construction_gap_se": gap / math.hypot(se[l6], se[best])}
    fm = subset(pool, f"{MODE}-{p['field_name']}", p["field_name"], ids, construction)
    members = [{"bot": b, "role": "leader" if b in leaders else "filler", "pool_rank": rank[b], "mu_bb": mu[b],
                "se_bb": se[b], "archetype": arch[b], "style": style[b],
                "min_param_distance_in_field": min(param_distance(vecs, b, x) for x in ids if x != b)}
               for b in sorted(ids, key=lambda b: rank[b])]
    summary = {
        "protocol_hash": protocol_hash(prof), "framing": "engineered easy-selection control; NOT a representative "
                                                          "field sample",
        "candidate": {"field_id": fm.field_id, "field_hash": fm.field_hash, "n": fm.n, "frozen": False,
                      "manifest": str(manifest_path(prof).relative_to(FHR3B_CONFIGS.parents[1]))},
        "leaders": leaders, "construction_rank6": {"bot": l6, "mu_bb": mu[l6], "se_bb": se[l6]},
        "construction_rank7": {"bot": best, "mu_bb": mu[best], "se_bb": se[best], "pool_rank": rank[best]},
        "construction_gap_bb": gap, "construction_gap_se": construction["construction_gap_se"],
        "excluded_non_leaders": len(excluded), "leader_param_distances": lead_d,
        "leader_near_duplicate_pairs": sum(d < c["leader_near_dup"] for d in lead_d.values()),
        "leader_max_per_archetype": max(Counter(arch[b] for b in leaders).values()),
        "field_styles": dict(Counter(style[b] for b in ids)), "field_archetypes": dict(Counter(arch[b] for b in ids)),
        "filler_mu_range_bb": [mu[fill[0]], mu[fill[-1]]], "filler_near_duplicate_pairs": nd_fill,
        "members": members, "log": log}
    write_field_immutable(fm, manifest_path(prof))
    d = out_dir(reports)
    d.mkdir(parents=True, exist_ok=True)
    (d / "construction.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=float) + "\n")
    return summary


# ------------------------------------------------------------------ 2. binding, 3. simulation
def bind(prof: Profile, reports: Path) -> dict[str, Any]:
    fm = load_field(manifest_path(prof))
    vs = validation_spec(prof)
    b = {"protocol_hash": protocol_hash(prof), "candidate_field_hash": fm.field_hash,
         "validation_calib_id": vs.calib_id, "validation_seed_family": vs.seed_family,
         "validation_namespace": vs.namespace, "validation_seed": vs.seed,
         "validation_rounds": int(protocol(prof)["validation"]["rounds"]),
         "note": "commit this file BEFORE `simulate`; evaluation refuses a different candidate or protocol"}
    (out_dir(reports) / "binding.json").write_text(json.dumps(b, indent=1, sort_keys=True) + "\n")
    return b


def _check_binding(prof: Profile, reports: Path) -> dict[str, Any]:
    b = json.loads((out_dir(reports) / "binding.json").read_text())
    fm = load_field(manifest_path(prof))
    if b["protocol_hash"] != protocol_hash(prof) or b["candidate_field_hash"] != fm.field_hash:
        raise ValueError("binding.json does not match the current protocol / candidate")
    if b["validation_calib_id"] != validation_spec(prof).calib_id:
        raise ValueError("binding.json names a different validation calibration")
    return b


def simulate(root: Path, prof: Profile, reports: Path, workers: int) -> dict[str, Any]:
    _check_binding(prof, reports)
    return run_calibration(validation_spec(prof), root, int(protocol(prof)["validation"]["rounds"]), workers)


# ------------------------------------------------------------------ 4. one-shot evaluation
def evaluate(root: Path, prof: Profile, reports: Path) -> dict[str, Any]:
    b = _check_binding(prof, reports)
    d = out_dir(reports)
    if (d / "validation.json").exists():
        raise ValueError(f"{d / 'validation.json'} exists: the validation is one shot")
    v = protocol(prof)["validation"]
    vs = validation_spec(prof)
    rounds = split_by_round(load_calibration(root, vs))
    if [int(t.column("round")[0].as_py()) for t in rounds] != list(range(int(v["rounds"]))):
        raise ValueError(f"validation incomplete: {len(rounds)} of {v['rounds']} rounds")
    fm = load_field(manifest_path(prof))
    leaders = list(fm.construction["leaders"])
    allbots = sorted(vs.field.bot_ids)
    res = analyse_calibration(rounds, allbots, n_boot=int(v["resamples"]), seed=int(v["seed"]))
    ids = sorted(fm.bot_ids)
    ix = [allbots.index(x) for x in ids]
    mu = res["mu"][ix] / BB
    se = res["se"][ix] / BB
    boot = res["boot_mu"][:, ix] / BB
    lm = np.array([x in leaders for x in ids])
    g = float(mu[lm].min() - mu[~lm].max())
    gb = boot[:, lm].min(1) - boot[:, ~lm].max(1)
    diag = reference_rank_diagnostics(mu, boot, int(fm.construction["K"]))
    pt = np.asarray(diag["per_bot"]["p_top_k"])
    order = np.argsort(-mu, kind="stable")
    nonl = sorted(((ids[i], float(pt[i]), float(mu[i])) for i in range(len(ids)) if not lm[i]), key=lambda x: -x[1])
    lcb = float(np.quantile(gb, 0.05))
    crit = {
        "point_top6_equals_leaders": {"value": bool(g > 0), "required": True},
        "p_leaders_are_top6": {"value": float((gb > 0).mean()), "at_least": float(v["p_leaders_are_top6_at_least"])},
        "max_nonleader_p_top6": {"value": nonl[0][1], "bot": nonl[0][0], "at_most": float(v["nonleader_p_top6_at_most"])},
        "gap_lcb95_one_sided_bb": {"value": lcb, "above": float(v["gap_lcb95_one_sided_above_bb"])}}
    passed = (crit["point_top6_equals_leaders"]["value"]
              and crit["p_leaders_are_top6"]["value"] >= crit["p_leaders_are_top6"]["at_least"]
              and crit["max_nonleader_p_top6"]["value"] <= crit["max_nonleader_p_top6"]["at_most"]
              and lcb > crit["gap_lcb95_one_sided_bb"]["above"])
    i6, i7 = int(order[5]), int(order[6])
    out = {"binding": b, "validation_calib_id": vs.calib_id, "validation_digest": calibration_digest(root, vs),
           "validation_rounds": len(rounds), "matches_per_bot": int(res["n_matches"].min()),
           "median_se_bb": float(np.median(se)), "context": "pool-style (96-bot pool opponents)",
           "gap_point_bb": g, "gap_lcb95_one_sided_bb": lcb,
           "gap_boot_quantiles_bb": {str(q): float(np.quantile(gb, q)) for q in (0.025, 0.05, 0.5, 0.95, 0.975)},
           "point_rank6": {"bot": ids[i6], "mu_bb": float(mu[i6]), "se_bb": float(se[i6]), "leader": bool(lm[i6])},
           "point_rank7": {"bot": ids[i7], "mu_bb": float(mu[i7]), "se_bb": float(se[i7]), "leader": bool(lm[i7])},
           "rank6_rank7_pair_gap_ci95_bb": diag["gap_at_cutoff_pair_ci95"],
           "p_rank6_rank7_reversal": diag["p_cutoff_pair_order_reversed"], "p_same_top6_set": diag["p_same_top_k_set"],
           "leaders_val": [{"bot": x, "mu_bb": float(mu[ids.index(x)]), "se_bb": float(se[ids.index(x)]),
                            "p_top6": float(pt[ids.index(x)])} for x in leaders],
           "top12_val": [{"rank": r + 1, "bot": ids[i], "leader": bool(lm[i]), "mu_bb": float(mu[i]),
                          "se_bb": float(se[i]), "p_top6": float(pt[i])} for r, i in enumerate(order[:12])],
           "nonleaders_p_top6_above_zero": [{"bot": x, "p_top6": p_, "mu_bb": m_} for x, p_, m_ in nonl if p_ > 0],
           "criteria": crit, "passed": bool(passed),
           "decision": "PASS: freeze as a new field and add to the FHR4 core scope" if passed else
                       "FAIL: retire the candidate; no second candidate; proceed with crowded_cutoff + style_diverse"}
    (d / "validation.json").write_text(json.dumps(out, indent=1, sort_keys=True, default=float) + "\n")
    return out
