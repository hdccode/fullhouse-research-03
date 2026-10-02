"""Strategic heterogeneity of the frozen core fields (analysis only; no simulation).

Inputs are existing, frozen artefacts:

* the field manifests (archetype, resolved parameters);
* the behaviour audit (``behaviour.csv``: an exact replay of calibration rounds);
* the pool calibration ranking (``pool_bots.csv``), which orders bots inside each field.

Message: the synthetic agents are strategically heterogeneous, but not all 60 are
qualitatively unique. Ranks are the pool-calibration point ranking restricted to the field,
which is the ranking the fields were constructed from (the ``mu_field`` reference is not run yet).
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from fhr3.tournament.diagnostics import param_distance, param_vectors
from fhr3.tournament.experiments import Profile

BEHAVIOUR = (("vpip", "VPIP"), ("pfr", "PFR"), ("threebet", "3-bet"), ("post_aggression", "postflop aggression"),
             ("allin_decision_rate", "all-in decision rate"))
BOUNDARY = (4, 15)  # ranks 4..15: the crowded_cutoff design window (3 leaders + 12-bot crowd)


def _pairs(ids: list[str], vecs: dict[str, Any]) -> list[float]:
    return [param_distance(vecs, a, b) for i, a in enumerate(ids) for b in ids[i + 1:]]


def _summ(ids: list[str], arch: dict[str, str], style: dict[str, str], vecs: dict[str, Any],
          thr: float) -> dict[str, Any]:
    d = _pairs(ids, vecs)
    fin = [x for x in d if math.isfinite(x)]
    dup_pairs = [(a, c) for i, a in enumerate(ids) for c in ids[i + 1:] if param_distance(vecs, a, c) < thr]
    return {"n": len(ids), "n_archetypes": len({arch[b] for b in ids}),
            "archetypes": dict(sorted(Counter(arch[b] for b in ids).items())),
            "styles": dict(sorted(Counter(style[b] for b in ids).items())),
            "near_duplicate_pairs": int(sum(x < thr for x in d)), "pairs": len(d),
            "bots_in_near_duplicate_pairs": len({x for pr in dup_pairs for x in pr}),
            "near_duplicate_pair_ids": [list(pr) for pr in dup_pairs],
            "median_param_distance": float(np.median(fin)) if fin else None,
            "min_param_distance": float(min(fin)) if fin else None}


def field_diversity(prof: Profile, mode: str, fields: list[str], reports: Path) -> dict[str, Any]:
    from fhr3.tournament.experiments import load_matrix

    thr = float(load_matrix(prof.config_root)["calibration"]["selection"]["near_dup"])
    base = reports / "field-calibration" / mode
    beh = {r["bot_id"]: r for r in csv.DictReader((base / "behaviour.csv").open())}
    pool_mu = {r["bot_id"]: float(r["mu_field"]) for r in csv.DictReader((base / "pool_bots.csv").open())}
    out: dict[str, Any] = {"mode": mode, "near_dup_threshold": thr,
                           "rank_basis": "pool-calibration point ranking within the field (construction ranking)",
                           "sources": {"behaviour": f"<reports>/field-calibration/{mode}/behaviour.csv",
                                       "pool": f"<reports>/field-calibration/{mode}/pool_bots.csv"},
                           "fields": {}}
    for field in fields:
        fm = prof.field(mode, field)
        bots = [b for b in fm.bots]
        ids = sorted((b["bot_id"] for b in bots), key=lambda b: -pool_mu[b])
        arch = {b["bot_id"]: b["meta"]["archetype"] for b in bots}
        style = {b: beh[b]["style"] for b in ids}
        vecs = param_vectors(bots)
        lo, hi = BOUNDARY
        row = {"field": field, "field_hash": fm.field_hash} | _summ(ids, arch, style, vecs, thr)
        row["boundary_ranks_4_15"] = _summ(ids[lo - 1:hi], arch, style, vecs, thr)
        row["n_distinct_parameter_vectors"] = len({tuple(np.round(vecs[b][1], 9)) for b in ids})
        for key, _ in BEHAVIOUR:
            x = np.array([float(beh[b][key]) for b in ids])
            row[f"{key}_min"], row[f"{key}_max"] = float(x.min()), float(x.max())
            row[f"{key}_q25"], row[f"{key}_q75"] = float(np.quantile(x, 0.25)), float(np.quantile(x, 0.75))
        if fm.kind == "crowded_cutoff":
            c = fm.construction
            crowd = list(c["crowd_ids"])
            row["designed_crowd"] = _summ(crowd, arch, style, vecs, thr) | {
                "same_as_ranks_4_15": sorted(crowd) == sorted(ids[lo - 1:hi])}
        out["fields"][field] = row
    return out


def write_field_diversity(res: dict[str, Any], reports: Path) -> dict[str, Path]:
    base = reports / "field-calibration" / res["mode"]
    js = base / "field_diversity.json"
    js.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    rows = []
    for f, r in res["fields"].items():
        b = r["boundary_ranks_4_15"]
        rows.append({"field": f, "n_bots": r["n"], "archetypes": r["n_archetypes"],
                     "styles": " ".join(f"{k}:{v}" for k, v in r["styles"].items()),
                     "distinct_param_vectors": r["n_distinct_parameter_vectors"],
                     "near_dup_pairs": r["near_duplicate_pairs"], "near_dup_pairs_ranks_4_15": b["near_duplicate_pairs"],
                     "bots_in_near_dup_pairs": r["bots_in_near_duplicate_pairs"],
                     "bots_in_near_dup_pairs_ranks_4_15": b["bots_in_near_duplicate_pairs"],
                     "archetypes_ranks_4_15": b["n_archetypes"],
                     "styles_ranks_4_15": " ".join(f"{k}:{v}" for k, v in b["styles"].items()),
                     "median_param_distance": round(r["median_param_distance"], 3),
                     "median_param_distance_ranks_4_15": round(b["median_param_distance"], 3),
                     "vpip_range": f"{r['vpip_min']:.2f}-{r['vpip_max']:.2f}",
                     "pfr_range": f"{r['pfr_min']:.2f}-{r['pfr_max']:.2f}",
                     "threebet_range": f"{r['threebet_min']:.3f}-{r['threebet_max']:.3f}",
                     "post_aggression_range": f"{r['post_aggression_min']:.2f}-{r['post_aggression_max']:.2f}",
                     "allin_rate_range": f"{r['allin_decision_rate_min']:.4f}-{r['allin_decision_rate_max']:.4f}"})
    cp = base / "field_diversity.csv"
    with cp.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    md = base / "field_diversity.md"
    head = ["field", "archetypes (all / ranks 4-15)", "styles", "distinct param vectors",
            "near-dup pairs (all / ranks 4-15)", "bots in near-dup pairs (all / ranks 4-15)",
            "median param distance (all / 4-15)", "VPIP", "PFR", "3-bet", "postflop aggr."]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        lines.append(f"| {r['field']} | {r['archetypes']} / {r['archetypes_ranks_4_15']} | {r['styles']} "
                     f"| {r['distinct_param_vectors']}/{r['n_bots']} "
                     f"| {r['near_dup_pairs']} / {r['near_dup_pairs_ranks_4_15']} "
                     f"| {r['bots_in_near_dup_pairs']} / {r['bots_in_near_dup_pairs_ranks_4_15']} "
                     f"| {r['median_param_distance']} / {r['median_param_distance_ranks_4_15']} "
                     f"| {r['vpip_range']} | {r['pfr_range']} | {r['threebet_range']} | {r['post_aggression_range']} |")
    md.write_text("# Strategic diversity of the FHR #4 core NLHE6 fields\n\n"
                  "Generated by `fhr3b core field-diversity` from the frozen manifests, the behaviour audit and the "
                  f"pool calibration (no simulation). Near-duplicate: resolved-parameter RMS distance < "
                  f"{res['near_dup_threshold']}. Ranks 4-15 use the pool-calibration ranking inside each field.\n\n"
                  + "\n".join(lines) + "\n\nThe synthetic agents are strategically heterogeneous, but not all 60 "
                  "are qualitatively unique.\n")
    return {"json": js, "csv": cp, "md": md}
