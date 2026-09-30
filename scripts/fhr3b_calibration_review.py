"""FHR3B field-calibration review (selection v2): numbers behind FIELD_CALIBRATION_REVIEW.md.

Analysis only. Reads:
* the pool-calibration chunks;
* the behaviour audit (``fhr3b behaviour-audit``);
* ``selection.json`` and the candidate field manifests (``fhr3b select-fields``).

It never plays poker.

Modes: every primary mode with a completed pool calibration (AoF4 and NLHE6 now; NLHE4 once
its calibration has run). PLO is not part of FHR3B.

Matchup / non-transitive structure is measured, never selected on:
* split-half reliability of the cyclic presence-effect flow for each field, against 300
  random 60-bot subsets;
* the archetype-level cycle test, with a label-permutation null.

Output: reports/fhr3b/field-calibration/review/{bot_strengths,boundary,field_summary,
random_subsets,realism}.csv and review.json.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from fhr3.tournament.behaviour import load_behaviour  # noqa: E402
from fhr3.tournament.calibration import calib_dir, calibration_digest, group_stats, load_calibration  # noqa: E402
from fhr3.tournament.diagnostics import SplitHalf, crosshalf  # noqa: E402
from fhr3.tournament.experiments import load_matrix, load_profile  # noqa: E402
from fhr3.tournament.fields import BOUNDS, FRACTION_BOUNDS, load_field  # noqa: E402
from fhr3.tournament.manifests import engine_source_hash, identity_hash  # noqa: E402

ROOT = REPO / "results/fhr3b"
REPORTS = REPO / "reports/fhr3b"
OUT = REPORTS / "field-calibration/review"
FIELDS = ("spread", "crowded_cutoff", "style_diverse")
BB = 100
SEED = 20260930
N_RANDOM = 300


def clipped(params: dict) -> list[str]:
    hits = []
    for k, v in (params.get("overrides") or {}).items():
        if isinstance(v, list):
            continue
        lo, hi = BOUNDS.get(k, FRACTION_BOUNDS if any(t in k for t in ("pct", "freq", "threshold")) else (-1e9, 1e9))
        if abs(v - lo) < 1e-9 or abs(v - hi) < 1e-9:
            hits.append(k)
    return hits


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols: list[str] = []
    for r in rows:
        cols += [k for k in r if k not in cols]
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.6g}" if isinstance(v, float) else json.dumps(v) if isinstance(v, (list, dict)) else v)
                        for k, v in r.items()})


def main() -> None:
    prof = load_profile("publication")
    rng = np.random.Generator(np.random.PCG64(SEED))
    review = {"script": "scripts/fhr3b_calibration_review.py", "seed": SEED, "n_random_subsets": N_RANDOM,
              "engine_source_hash_now": engine_source_hash(),
              "protocol": {"name": prof.base.name, "status": prof.base.status, "protocol_hash": prof.base.protocol_hash,
                           "R0": prof.r0, "R0_status": "initial research horizon, not assumed sufficient",
                           "H0": prof.h0, "K": prof.k, "N": prof.field_size,
                           "meaning": "predeclared research design choices, not 2026 FullHouse settings"},
              "modes": {}, "not_calibrated": []}
    strengths, boundary, fsum, rnd_rows, realism = [], [], [], [], []
    for mode in load_matrix()["primary_modes"]:
        spec = prof.calibration_spec(mode, "pool")
        d = calib_dir(ROOT, spec)
        if not (d / "chunks").exists():
            review["not_calibrated"].append(mode)
            continue
        lock = json.loads((d / "calibration.lock.json").read_text())
        assert lock["calib_id"] == spec.calib_id and lock["identity_hash"] == identity_hash(spec.identity), mode
        sel = json.loads((REPORTS / f"field-calibration/{mode}/selection.json").read_text())
        tabs = load_calibration(ROOT, spec)
        bots = sorted(spec.field.bot_ids)
        idx = {b: i for i, b in enumerate(bots)}
        groups = [group_stats(t, bots) for t in tabs]
        full, a, b = SplitHalf(groups), SplitHalf(groups[0::2]), SplitHalf(groups[1::2])
        mu, _ = full.stats(list(range(len(bots))))
        meta = {x["bot_id"]: x for x in spec.field.bots}
        beh = {r["bot_id"]: r for r in load_behaviour(REPORTS, mode)}
        deltas = {x: [] for x in bots}
        early = total = 0
        for t in tabs:
            x = t.to_pydict()
            for bid, dlt in zip(x["bot_id"], x["chip_delta"], strict=True):
                deltas[bid].append(dlt)
            seen = {}
            for r_, ti, hp in zip(x["round"], x["table_index"], x["hands_played"], strict=True):
                seen[(r_, ti)] = hp
            total += len(seen)
            early += sum(hp < spec.hands_per_match for hp in seen.values())
        stack = spec.mode.game.starting_stack_chips
        persistent = spec.stack_policy == "persistent_no_rebuy"
        rows = []
        for bt in bots:
            v = np.array(deltas[bt], float)
            p = meta[bt]["params"]
            rows.append({"mode": mode, "bot_id": bt, "archetype": meta[bt]["meta"]["archetype"],
                         "scale_index": meta[bt]["meta"]["scale_index"], "style": beh[bt]["style"],
                         "mu_bb": mu[idx[bt]] / BB, "se_bb": v.std(ddof=1) / np.sqrt(len(v)) / BB,
                         "sd_per_match_bb": v.std(ddof=1) / BB,
                         "bust_rate": float((v == -stack).mean()) if persistent else 0.0,
                         "n_clipped_params": len(clipped(p)), "clipped": clipped(p),
                         "vpip": float(beh[bt]["vpip"]), "pfr": float(beh[bt]["pfr"]),
                         "open_raise": float(beh[bt]["open_raise"]), "call_vs_raise": float(beh[bt]["call_vs_raise"]),
                         "post_fold_to_bet": float(beh[bt]["post_fold_to_bet"]),
                         "preflop_allin_rate": float(beh[bt]["preflop_allin_rate"]),
                         "uncontested_bb_per_100": float(beh[bt]["uncontested_bb_per_100"]),
                         "showdown_bb_per_100": float(beh[bt]["showdown_bb_per_100"])})
        strengths += rows
        mus = np.array([r["mu_bb"] for r in rows])
        info = {"calib_id": spec.calib_id, "calibration_identity_hash": lock["identity_hash"],
                "calibration_digest": calibration_digest(ROOT, spec),
                "digest_matches_selection": calibration_digest(ROOT, spec) == sel["calibration_digest"],
                "engine_source_hash_at_run": lock["engine_source_hash"],
                "engine_source_hash_matches_now": lock["engine_source_hash"] == review["engine_source_hash_now"],
                "spec": {k: lock["spec"][k] for k in ("hands_per_match", "stack_policy", "seed_family", "namespace",
                                                     "chunk_rounds")},
                "pool_hash": spec.field.field_hash, "rounds": 25 * len(tabs), "matches_per_bot": len(deltas[bots[0]]),
                "pool_mu_sd_bb": float(mus.std()), "median_se_bb": float(np.median([r["se_bb"] for r in rows])),
                "split_half_r_mu": crosshalf(a, b, list(range(len(bots))))["r_mu"],
                "tournament_se_mean_per_match_bb": float(np.median([r["sd_per_match_bb"] for r in rows])
                                                         / np.sqrt(prof.r0)),
                "matches_ending_early": early / total,
                "median_bust_rate": float(np.median([r["bust_rate"] for r in rows])),
                "spearman_mu_vs_bust": float(spearmanr(mus, [r["bust_rate"] for r in rows])[0]) if persistent else None,
                "bots_with_clipped_params": int(sum(r["n_clipped_params"] > 0 for r in rows)),
                "spearman_mu_vs_n_clipped": float(spearmanr(mus, [r["n_clipped_params"] for r in rows])[0]),
                "archetype_cycle": sel["measured_not_selected"]["archetype_cycle"],
                "crowded_cutoff_diversity_audit": sel["crowded_cutoff_diversity_audit"], "fields": {}}
        realism.append({"mode": mode} | {k: info[k] for k in ("median_bust_rate", "spearman_mu_vs_bust",
                                                               "matches_ending_early", "bots_with_clipped_params",
                                                               "spearman_mu_vs_n_clipped")})
        rnd = [crosshalf(a, b, sorted(rng.choice(len(bots), 60, replace=False).tolist()))["r_cyclic"]
               for _ in range(N_RANDOM)]
        info["random_subset_r_cyclic"] = {"q025": float(np.quantile(rnd, 0.025)), "mean": float(np.mean(rnd)),
                                          "q975": float(np.quantile(rnd, 0.975))}
        rnd_rows += [{"mode": mode, "r_cyclic": x} for x in rnd]
        by = {r["bot_id"]: r for r in rows}
        for f in FIELDS:
            fm = load_field(REPO / f"configs/fhr3b/fields/{mode}/{f}.json")
            ch = crosshalf(a, b, [idx[x] for x in fm.bot_ids])
            fd = sel["fields"][f]
            order = sorted(fm.bot_ids, key=lambda x: (-by[x]["mu_bb"], x))
            for rank, x in enumerate(order, 1):
                boundary.append({"mode": mode, "field": f, "rank": rank, "bot_id": x, "mu_bb": by[x]["mu_bb"],
                                 "se_bb": by[x]["se_bb"], "style": by[x]["style"], "archetype": by[x]["archetype"]})
            info["fields"][f] = {k: fd[k] for k in fd if k != "path"} | {
                "measured_r_cyclic": ch["r_cyclic"], "measured_r_cyclic_null_se": ch["r_null_se"],
                "leaders_mean_bust_rate": float(np.mean([by[x]["bust_rate"] for x in order[:prof.k]])),
                "leaders_clipped": {x: by[x]["clipped"] for x in order[:prof.k] if by[x]["clipped"]}}
            fsum.append({"mode": mode, "field": f} | {k: v for k, v in info["fields"][f].items()
                                                     if not isinstance(v, (dict, list))})
        review["modes"][mode] = info
        print(mode, "done", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*"):
        if stale.is_file():
            stale.unlink()
    write_csv(OUT / "bot_strengths.csv", strengths)
    write_csv(OUT / "boundary.csv", boundary)
    write_csv(OUT / "field_summary.csv", fsum)
    write_csv(OUT / "random_subsets.csv", rnd_rows)
    write_csv(OUT / "realism.csv", realism)
    (OUT / "review.json").write_text(json.dumps(review, indent=1, sort_keys=True, default=float) + "\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
