"""Deterministic field selection from a frozen pool calibration (selection v2).

Inputs (all frozen, recorded in every manifest):

* the pool calibration chunks (``calibration_digest``). Balanced field EV ``mu`` and its
  group-bootstrap SE come from these;
* the behaviour audit (``behaviour.csv``, sha256 recorded). It is an exact replay of
  calibration rounds and gives each bot's observed style class (TA / LA / TP / LP);
* the pool manifest. It gives archetypes and resolved parameters for near-duplicate
  detection (parameter distance < ``near_dup``).

Fields (N, K and the thresholds come from configs/fhr3b/matrix.yaml):

``spread``
    1. Leaders: walk down the calibrated ranking, accepting bots that are not near-duplicates
       of an accepted leader and whose archetype has fewer than ``leader_archetype_cap``
       leaders, until there are K.
    2. The qualification gap is a *constraint*: every non-leader b must satisfy
       mu_b <= mu_K - gap_se * sqrt(se_K^2 + se_b^2). Bots inside that band are excluded.
    3. The other N - K bots are drawn from the eligible pool in ``strata`` equal-count strength
       strata with equal quotas. Within a stratum the pick is greedy: the least-represented
       style first, then the least-represented archetype, then the largest parameter distance
       to bots already chosen. Never a near-duplicate; archetype cap ``archetype_cap``.
    4. The selector seeks a 3 SE qualification gap subject to diversity and coverage
       constraints, relaxing the threshold only when the stronger requirement would materially
       degrade field diversity: if the whole constrained construction (gap + strata + zero
       near-duplicates + archetype cap) is infeasible, gap_se is lowered in 0.25 steps. The
       constraint actually used and the achieved gap are recorded (D1, 2026-09-30).

``crowded_cutoff``
    Unchanged rule (fields.select_crowded). The selection report adds a strategic-diversity
    audit of the leaders and the cutoff cluster.

``style_diverse``
    Balances observed style x strength. Strength strata are equal-count quantiles of pool mu.
    An integer program (scipy HiGHS, deterministic) chooses cell counts x[style, stratum] with
    every stratum total N / S and every style total N / C (relaxed by one when infeasible),
    minimising sum |x - N / (S C)|. Within each cell the pick is greedy: least-represented
    archetype, then largest parameter distance, then closeness to the cell's median strength.
    No near-duplicates.

    Non-transitive / matchup structure is **not** a selection criterion; it is measured
    afterwards (diagnostics.archetype_cycle_test). The former ``matchup_sensitive`` field and
    its gate are retired: the gate's "debiased cyclic share" could exceed 1 and did not
    replicate out of sample (reports/fhr3b/field-calibration/FIELD_CALIBRATION_REVIEW.md).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from fhr3.tournament.behaviour import STYLE_NAMES, behaviour_path, load_behaviour
from fhr3.tournament.calibration import (
    analyse_calibration,
    bot_rows,
    calibration_digest,
    load_calibration,
    matchup_rows,
)
from fhr3.tournament.diagnostics import SplitHalf, archetype_cycle_test, crosshalf, param_distance, param_vectors
from fhr3.tournament.experiments import Profile
from fhr3.tournament.fields import FieldManifest, select_crowded, subset, write_field_immutable
from fhr3.tournament.manifests import identity_hash

SELECTION_VERSION = "fhr3b-selection-v2"
BB = 100
FIELD_NAMES = ("spread", "crowded_cutoff", "style_diverse")


def _csv(path: Path, rows: list[dict[str, Any]]) -> None:
    from fhr3.tournament.analysis import _write_csv

    _write_csv(path, rows)


class Inputs:
    """Everything a selector may use, with provenance."""

    def __init__(self, root: Path, prof: Profile, mode: str, reports: Path, n_boot: int = 300,
                 require_behaviour: bool = True) -> None:
        self.spec = prof.calibration_spec(mode, "pool")
        tabs = load_calibration(root, self.spec)
        if not tabs:
            raise FileNotFoundError(f"no pool calibration for {mode}; run `fhr3b calibrate --stage pool` first")
        self.pool = self.spec.field
        self.bots = sorted(self.pool.bot_ids)
        self.res = analyse_calibration(tabs, self.bots, n_boot=n_boot)
        self.groups = self.res["groups"]
        self.mu = {b: float(self.res["mu"][i]) for i, b in enumerate(self.bots)}
        # Analytic SE (sd / sqrt(matches)): a bot's matches in independent calibration rounds are
        # independent, and unlike the bootstrap SE it does not depend on resampling draws.
        self.se = {b: float(self.res["sd"][i] / np.sqrt(self.res["n_matches"][i])) for i, b in enumerate(self.bots)}
        self.ranked = sorted(self.bots, key=lambda b: (-self.mu[b], b))
        self.meta = {b["bot_id"]: b["meta"] for b in self.pool.bots}
        self.arch = {b: self.meta[b]["archetype"] for b in self.bots}
        self.vecs = param_vectors(self.pool.bots)
        self.family = "aof" if self.spec.mode.agent_family == "aof" else "nlhe"
        bpath = behaviour_path(reports, mode)
        if bpath.exists():
            rows = load_behaviour(reports, mode)
            self.style = {r["bot_id"]: r["style"] for r in rows}
            self.style_source = {"source": "behaviour audit (exact replay)", "path": str(bpath),
                                 "sha256": hashlib.sha256(bpath.read_bytes()).hexdigest()}
        elif require_behaviour:
            raise FileNotFoundError(f"{bpath} missing: run `fhr3b behaviour-audit --modes {mode}` first")
        else:
            self.style = dict(self.arch)
            self.style_source = {"source": "archetype labels (behaviour audit unavailable; smoke only)"}
        self.digest = calibration_digest(root, self.spec)
        self.provenance = {"selection_version": SELECTION_VERSION, "calibration_id": self.spec.calib_id,
                           "calibration_identity_hash": identity_hash(self.spec.identity),
                           "calibration_digest": self.digest, "style_classes": self.style_source,
                           "calibration_round_groups": len(self.groups)}

    def near_dup(self, a: str, b: str, thr: float) -> bool:
        return param_distance(self.vecs, a, b) < thr

    def min_dist(self, b: str, chosen: list[str]) -> float:
        return min((param_distance(self.vecs, b, c) for c in chosen), default=math.inf)


def _pick_diverse(inp: Inputs, candidates: list[str], k: int, chosen: list[str], params: dict[str, Any],
                  centre: float | None = None) -> list[str]:
    """Greedy diverse pick of k from candidates; returns the picks (may be fewer if constrained)."""
    thr, cap = float(params["near_dup"]), int(params["archetype_cap"])
    picks: list[str] = []
    for _ in range(k):
        cur = chosen + picks
        sc, ac = Counter(inp.style[b] for b in cur), Counter(inp.arch[b] for b in cur)
        ok = [b for b in candidates if b not in cur and ac[inp.arch[b]] < cap
              and not any(inp.near_dup(b, c, thr) for c in cur)]
        if not ok:
            break
        best = min(ok, key=lambda b: (sc[inp.style[b]], ac[inp.arch[b]], -min(inp.min_dist(b, cur), 9.0),
                                      abs(inp.mu[b] - centre) if centre is not None else 0.0, inp.ranked.index(b)))
        picks.append(best)
    return picks


def _strata(ids: list[str], s: int) -> list[list[str]]:
    """Equal-count consecutive strata of an already strength-ordered list."""
    edges = [round(i * len(ids) / s) for i in range(s + 1)]
    return [ids[edges[i]:edges[i + 1]] for i in range(s)]


def select_spread(inp: Inputs, n: int, k: int, params: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    thr = float(params["near_dup"])
    leaders: list[str] = []
    for b in inp.ranked:
        if len(leaders) == k:
            break
        if sum(inp.arch[x] == inp.arch[b] for x in leaders) >= int(params["leader_archetype_cap"]):
            continue
        if any(inp.near_dup(b, x, thr) for x in leaders):
            continue
        leaders.append(b)
    last = min(leaders, key=lambda b: inp.mu[b])
    quota = n - k

    def attempt(gap_se: float) -> tuple[list[str], list[str]] | None:
        eligible = [b for b in inp.ranked if b not in leaders
                    and inp.mu[b] <= inp.mu[last] - gap_se * math.hypot(inp.se[last], inp.se[b])]
        if len(eligible) < quota:
            return None
        chosen = list(leaders)
        strata = _strata(eligible, int(params["strata"]))
        base, extra = divmod(quota, len(strata))
        deficit = 0
        for i, st in enumerate(strata):
            want = base + (1 if i < extra else 0) + deficit
            centre = float(np.median([inp.mu[b] for b in st])) if st else None
            got = _pick_diverse(inp, st, want, chosen, params, centre)
            chosen += got
            deficit = want - len(got)
        if deficit:  # carry any residual to the nearest-strength eligible bots
            chosen += _pick_diverse(inp, eligible, deficit, chosen, params)
        return (chosen, eligible) if len(chosen) == n else None

    gap_se = float(params["gap_se"])
    found = attempt(gap_se)
    while found is None and gap_se > 1.0:
        gap_se -= 0.25
        found = attempt(gap_se)
    if found is None:
        raise ValueError("spread selection infeasible even at a 1 SE gap constraint")
    chosen, eligible = found
    seventh = max((b for b in chosen if b not in leaders), key=lambda b: inp.mu[b])
    info = {"leaders": leaders, "gap_se_target": float(params["gap_se"]), "gap_se_constraint": gap_se, "excluded_band": [
        b for b in inp.ranked if b not in leaders and b not in eligible and inp.mu[b] >= inp.mu[seventh]],
        "achieved_gap_bb": (inp.mu[last] - inp.mu[seventh]) / BB,
        "achieved_gap_se": (inp.mu[last] - inp.mu[seventh]) / math.hypot(inp.se[last], inp.se[seventh]),
        "strata_below_cut": int(params["strata"])}
    return chosen, info


def select_style_diverse(inp: Inputs, n: int, params: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    from scipy.optimize import Bounds, LinearConstraint, milp

    styles = sorted(set(inp.style.values()))
    strata = _strata(inp.ranked, int(params["strata"]))
    c_n, s_n = len(styles), len(strata)
    avail = np.array([[sum(inp.style[b] == st for b in stratum) for stratum in strata] for st in styles])
    target = n / (c_n * s_n)
    nv = c_n * s_n
    for slack in range(0, 4):
        # variables: x (nv), d (nv) with d >= |x - target|
        cost = np.r_[np.zeros(nv), np.ones(nv)]
        rows, lo, hi = [], [], []
        for j in range(s_n):  # stratum totals
            r = np.zeros(2 * nv)
            r[[i * s_n + j for i in range(c_n)]] = 1
            rows.append(r); lo.append(n / s_n); hi.append(n / s_n)
        for i in range(c_n):  # style totals
            r = np.zeros(2 * nv)
            r[i * s_n:(i + 1) * s_n] = 1
            rows.append(r); lo.append(math.floor(n / c_n) - slack); hi.append(math.ceil(n / c_n) + slack)
        for v in range(nv):  # d >= x - t ; d >= t - x
            r = np.zeros(2 * nv); r[v] = -1; r[nv + v] = 1
            rows.append(r); lo.append(-target); hi.append(np.inf)
            r = np.zeros(2 * nv); r[v] = 1; r[nv + v] = 1
            rows.append(r); lo.append(target); hi.append(np.inf)
        res = milp(cost, constraints=LinearConstraint(np.array(rows), lo, hi),
                   integrality=np.r_[np.ones(nv), np.zeros(nv)],
                   bounds=Bounds(np.zeros(2 * nv), np.r_[avail.ravel(), np.full(nv, np.inf)]))
        if res.status == 0:
            break
    else:
        raise ValueError("style_diverse cell allocation infeasible")
    x = np.round(res.x[:nv]).astype(int).reshape(c_n, s_n)
    chosen: list[str] = []
    substitutions: list[dict[str, Any]] = []
    for j, stratum in enumerate(strata):
        for i, st in enumerate(styles):
            cell = [b for b in stratum if inp.style[b] == st]
            centre = float(np.median([inp.mu[b] for b in cell])) if cell else None
            got = _pick_diverse(inp, cell, int(x[i, j]), chosen, params, centre)
            chosen += got
            short = int(x[i, j]) - len(got)
            if short:  # near-dup / cap blocked: same stratum first, then nearest strength anywhere
                sub = _pick_diverse(inp, stratum, short, chosen, params, centre)
                if len(sub) < short:
                    ctr = centre if centre is not None else float(np.median([inp.mu[b] for b in stratum]))
                    thr, cap = float(params["near_dup"]), int(params["archetype_cap"])
                    for cand in sorted((b for b in inp.ranked if b not in chosen + sub),
                                       key=lambda b: (abs(inp.mu[b] - ctr), b)):
                        if len(sub) == short:
                            break
                        cur = chosen + sub
                        if (sum(inp.arch[c] == inp.arch[cand] for c in cur) < cap
                                and not any(inp.near_dup(cand, c, thr) for c in cur)):
                            sub.append(cand)
                chosen += sub
                substitutions.append({"style": st, "stratum": j, "short": short, "substitutes": sub})
    if len(chosen) != n:
        raise ValueError(f"style_diverse produced {len(chosen)} bots, wanted {n}")
    info = {"styles": styles, "style_names": STYLE_NAMES[inp.family], "strata": s_n, "style_slack": slack,
            "allocation": {st: x[i].tolist() for i, st in enumerate(styles)},
            "pool_availability": {st: avail[i].tolist() for i, st in enumerate(styles)},
            "substitutions": substitutions}
    return chosen, info


# ------------------------------------------------------------------ diagnostics of a selected field
def field_diagnostics(inp: Inputs, ids: list[str], k: int, near_dup: float) -> dict[str, Any]:
    ordered = sorted(ids, key=lambda b: (-inp.mu[b], b))
    mu = np.array([inp.mu[b] for b in ordered]) / BB
    se = np.array([inp.se[b] for b in ordered]) / BB
    cut = (mu[k - 1] + mu[k]) / 2
    pairs = [(a, b) for i, a in enumerate(ordered) for b in ordered[i + 1:] if inp.near_dup(a, b, near_dup)]
    styles = [inp.style[b] for b in ordered]
    grand = mu.mean()
    ss_between = sum(len(g) * (np.mean(g) - grand) ** 2 for g in
                     ([mu[i] for i, s in enumerate(styles) if s == st] for st in set(styles)))
    eta2 = float(ss_between / ((mu - grand) ** 2).sum())
    return {"n": len(ids), "mu_max_bb": float(mu[0]), "mu_min_bb": float(mu[-1]), "mu_sd_bb": float(mu.std()),
            "gap_k_k1_bb": float(mu[k - 1] - mu[k]), "gap_k_k1_se": float((mu[k - 1] - mu[k]) / np.hypot(se[k - 1], se[k])),
            "n_within_5bb_of_cut": int((np.abs(mu - cut) < 5).sum()),
            "style_counts": dict(Counter(styles)), "archetype_counts": dict(Counter(inp.arch[b] for b in ordered)),
            "near_duplicate_pairs": len(pairs), "style_strength_eta2": eta2,
            "top_k": ordered[:k]}


def cluster_diversity(inp: Inputs, ids: list[str], near_dup: float) -> dict[str, Any]:
    pairs = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]]
    d = [param_distance(inp.vecs, a, b) for a, b in pairs]
    fin = [x for x in d if math.isfinite(x)]
    return {"ids": ids, "styles": dict(Counter(inp.style[b] for b in ids)),
            "archetypes": dict(Counter(inp.arch[b] for b in ids)),
            "near_duplicate_pairs": int(sum(x < near_dup for x in d)), "pairs": len(pairs),
            "median_param_distance": float(np.median(fin)) if fin else None}


def select_fields(root: Path, prof: Profile, mode: str, reports: Path, n_boot: int = 300) -> dict[str, Any]:
    inp = Inputs(root, prof, mode, reports, n_boot, require_behaviour=prof.name == "publication")
    sel = prof.selection
    n, k = int(sel["n"]), prof.k
    nd = float(sel["near_dup"])
    spread_ids, spread_info = select_spread(inp, n, k, sel["spread"] | {"near_dup": nd})
    crowd_ids, crowd_info = select_crowded(inp.ranked, inp.mu, n, k, **sel["crowded"])
    style_ids, style_info = select_style_diverse(inp, n, sel["style_diverse"] | {"near_dup": nd})
    crowd_info["diversity_audit"] = {"leaders": cluster_diversity(inp, crowd_info["top_ids"], nd),
                                     "cutoff_cluster": cluster_diversity(inp, crowd_info["crowd_ids"], nd)}
    common = inp.provenance | {"near_dup_threshold": nd}
    fields = {
        "spread": subset(inp.pool, f"{mode}-spread", "spread", spread_ids,
                         common | {"method": "leaders + gap constraint + stratified diverse fill", "n": n, "K": k,
                                   "params": sel["spread"]} | spread_info),
        "crowded_cutoff": subset(inp.pool, f"{mode}-crowded_cutoff", "crowded_cutoff", crowd_ids,
                                 common | {"method": "top + tightest window straddling top-K + spread fill",
                                           "n": n, "K": k} | crowd_info),
        "style_diverse": subset(inp.pool, f"{mode}-style_diverse", "style_diverse", style_ids,
                                common | {"method": "style x strength-stratum integer allocation + diverse fill",
                                          "n": n, "params": sel["style_diverse"]} | style_info),
    }
    out_dir = prof.fields_dir / mode
    written = {name: str(write_field_immutable(fm, out_dir / f"{name}.json")) for name, fm in fields.items()}
    rep = reports / "field-calibration" / mode
    _csv(rep / "pool_bots.csv", [r | {"style": inp.style[r["bot_id"]]} for r in bot_rows(inp.res, inp.pool)])
    _csv(rep / "pool_matchup_matrix.csv", list(matchup_rows(inp.res)))
    summary = {"mode": mode, "pool_hash": inp.pool.field_hash, **common,
               "fields": {name: {"field_id": fm.field_id, "field_hash": fm.field_hash, "path": written[name]}
                          | field_diagnostics(inp, list(fm.bot_ids), k, nd) for name, fm in fields.items()},
               "crowded_cutoff_diversity_audit": crowd_info["diversity_audit"],
               "measured_not_selected": {
                   "archetype_cycle": archetype_cycle_test(inp.groups, [inp.arch[b] for b in inp.bots],
                                                           np.random.Generator(np.random.PCG64(20260930))),
                   "pool_splithalf": crosshalf(SplitHalf(inp.groups[0::2]), SplitHalf(inp.groups[1::2]),
                                               list(range(len(inp.bots))))}}
    (rep / "selection.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=float) + "\n")
    return summary


def field_reference_report(root: Path, prof: Profile, mode: str, field: str, reports: Path,
                           n_boot: int = 300) -> dict[str, Any]:
    """mu_field inside a frozen field + split-half reliability (no selection statistics)."""
    spec = prof.calibration_spec(mode, "field", field)
    tabs = load_calibration(root, spec)
    if not tabs:
        raise FileNotFoundError(f"no field-reference calibration for {mode}/{field}")
    fm: FieldManifest = spec.field
    bots = sorted(fm.bot_ids)
    res = analyse_calibration(tabs, bots, n_boot=n_boot)
    rep = reports / "field-calibration" / mode / fm.field_id
    _csv(rep / "reference_bots.csv", bot_rows(res, fm))
    order = np.argsort(-res["mu"], kind="stable")
    mu_sorted = res["mu"][order]
    k = prof.k
    groups = res["groups"]
    out = {"mode": mode, "field_id": fm.field_id, "field_hash": fm.field_hash, "calib_id": spec.calib_id,
           "calibration_digest": calibration_digest(root, spec),
           "gap_at_cutoff_bb": float(mu_sorted[k - 1] - mu_sorted[k]) / BB if len(bots) > k else None,
           "median_se_bb": float(np.median(res["se"])) / BB,
           "splithalf": crosshalf(SplitHalf(groups[0::2]), SplitHalf(groups[1::2]), list(range(len(bots)))),
           "archetype_cycle": archetype_cycle_test(groups, [m["archetype"] for m in
                                                            (dict((b["bot_id"], b["meta"]) for b in fm.bots)[x]
                                                             for x in bots)],
                                                   np.random.Generator(np.random.PCG64(20260930)))}
    if fm.kind == "crowded_cutoff":
        c = fm.construction
        lo_r, hi_r = int(c["n_top"]), int(c["n_top"]) + int(c["crowd"])
        out["crowd_mu_range_in_field_reference_bb"] = float(mu_sorted[lo_r] - mu_sorted[hi_r - 1]) / BB
    (rep / "reference.json").write_text(json.dumps(out, indent=1, sort_keys=True, default=float) + "\n")
    return out
