"""NLHE re-calibration review (heads-up-role fix): numbers behind NLHE_RECALIBRATION_REVIEW.md.

Analysis only. Reads the corrected NLHE4/NLHE6 pool calibrations, behaviour audits and
selection candidates, and the retired (heads-up-role bug) calibrations. Heads-up statistics
come from an exact replay of 5 calibration rounds per calibration; every replayed match must
reproduce the stored deltas. Output: reports/fhr3b/field-calibration/review/nlhe_recalibration.json
"""

from __future__ import annotations

import csv
import itertools
from dataclasses import replace
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from scipy.stats import kendalltau, spearmanr

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from fhr3.agents import build_agent as fhr3a_build_agent  # noqa: E402
from fhr3.games.base import ActionKind  # noqa: E402
from fhr3.rng import derive_seed  # noqa: E402
from fhr3.tournament.agents import build_agent  # noqa: E402
from fhr3.tournament.calibration import CalibrationSpec, group_stats, load_calibration  # noqa: E402
from fhr3.tournament.diagnostics import SplitHalf, param_distance, param_vectors  # noqa: E402
from fhr3.tournament.experiments import load_profile  # noqa: E402
from fhr3.tournament.fields import FHR3B_CONFIGS, load_field, load_mode  # noqa: E402
from fhr3.tournament.match import MatchKey, PokerMatchPlayer  # noqa: E402

ROOT = REPO / "results/fhr3b"
FC = REPO / "reports/fhr3b/field-calibration"
RETIRED_CAL = {"nlhe4": "nlhe4.nlhe4-pool.H400.pool-calibration.698094ac",
               "nlhe6": "nlhe6.nlhe6-pool.H400.pool-calibration.4d3e14b6"}
BB, STACK = 100, 10000
FIELDS = ("spread", "crowded_cutoff", "style_diverse")


def rows(p: Path) -> list[dict]:
    with p.open() as fh:
        return list(csv.DictReader(fh))


def chunk_stats(cal_dir: Path) -> dict:
    """Per-bot mean delta (BB), analytic SE, bust rate; early-ended match share."""
    d: dict[str, list[int]] = {}
    early = total = 0
    for f in sorted((cal_dir / "chunks").glob("c_*.parquet")):
        t = pq.read_table(f).to_pydict()
        seen = {}
        for r, ti, b, x, hp in zip(t["round"], t["table_index"], t["bot_id"], t["chip_delta"], t["hands_played"],
                                   strict=True):
            d.setdefault(b, []).append(x)
            seen[(r, ti)] = hp
        total += len(seen)
        early += sum(hp < 400 for hp in seen.values())
    out = {}
    for b, v in d.items():
        a = np.array(v, float)
        out[b.split("-", 1)[1]] = {"mu": a.mean() / BB, "se": a.std(ddof=1) / np.sqrt(len(a)) / BB,
                                   "bust": float((a == -STACK).mean())}
    return {"bots": out, "early": early / total}


def hu_replay(spec: CalibrationSpec, cal_dir: Path, builder, rounds: int = 5) -> dict:
    stored = {}
    for f in sorted((cal_dir / "chunks").glob("c_*.parquet")):
        t = pq.read_table(f).to_pydict()
        for r, ti, b, x in zip(t["round"], t["table_index"], t["bot_id"], t["chip_delta"], strict=True):
            if r < rounds:
                stored[(r, ti, b)] = x
    btn, bb = Counter(), Counter()
    hands = Counter()

    class Rec:
        def __init__(self, a):
            self.a, self.agent_id, self.version = a, a.agent_id, a.version

        def act(self, o, legal, rng):
            a = self.a.act(o, legal, rng)
            if o.player_count == 2 and o.street == 0:
                if o.seat == 1 and not o.history:
                    btn[a.kind.value] += 1
                if o.seat == 0 and sum(h.kind is ActionKind.BET_RAISE for h in o.history) == 1:
                    bb[a.kind.value] += 1
            return a

    mp = PokerMatchPlayer(spec.mode.game, spec.stack_policy, {b: Rec(builder(s)) for b, s in spec.field.specs().items()})
    ch, de = derive_seed("fhr3b-calibration-chance", spec.seed), derive_seed("fhr3b-calibration-decision", spec.seed)
    replayed = {}
    for r in range(rounds):
        for t, seats in enumerate(spec.partition(r)):
            log: list[dict] = []
            res = mp.play(MatchKey(ch, de, r, t), seats, spec.hands_per_match, hand_log=log)
            replayed |= {(r, t, b): x for b, x in res.deltas.items()}
            for h in log:
                hands[len(h["positions"])] += 1
    assert replayed == stored, "replay does not reproduce the stored calibration"
    n = sum(hands.values())
    frac = lambda c: {k: v / sum(c.values()) for k, v in c.items()}  # noqa: E731
    return {"hu_hand_share": hands[2] / n, "hands_by_players": {k: v / n for k, v in sorted(hands.items())},
            "hu_button_first_in": frac(btn), "hu_bb_vs_raise": frac(bb), "n_button": sum(btn.values()),
            "n_bb": sum(bb.values()), "replayed_bot_matches": len(replayed)}


def main() -> None:
    prof = load_profile("publication")
    out: dict = {"modes": {}}
    new_mu: dict = {}
    for mode in ("nlhe4", "nlhe6"):
        spec = prof.calibration_spec(mode, "pool")
        cal = ROOT / "calibration" / spec.calib_id
        sel = json.loads((FC / f"{mode}/selection.json").read_text())
        beh = {r["bot_id"]: r for r in rows(FC / f"{mode}/behaviour.csv")}
        st = {r["bot_id"]: r for r in rows(FC / "review/bot_strengths.csv") if r["mode"] == mode}
        vecs = param_vectors(spec.field.bots)
        info: dict = {"calib_id": spec.calib_id, "pool_hash": spec.field.field_hash, "fields": {}}
        for f in FIELDS:
            fm = load_field(FHR3B_CONFIGS / f"fields/{mode}/{f}.json")
            ids = sorted(fm.bot_ids, key=lambda b: -float(st[b]["mu_bb"]))
            nd = [(a, b) for a, b in itertools.combinations(ids, 2) if param_distance(vecs, a, b) < 0.15]
            band = set(ids[3:15])
            d = sel["fields"][f]
            info["fields"][f] = {
                "field_hash": fm.field_hash, "gap_bb": d["gap_k_k1_bb"], "gap_se": d["gap_k_k1_se"],
                "near_dup_total": len(nd), "near_dup_ranks_4_15": sum(a in band and b in band for a, b in nd),
                "styles": d["style_counts"], "archetypes": d["archetype_counts"], "eta2": d["style_strength_eta2"],
                "within_5bb": d["n_within_5bb_of_cut"], "mu_range": [d["mu_min_bb"], d["mu_max_bb"]],
                "construction": {k: v for k, v in fm.construction.items()
                                 if k in ("gap_se_constraint", "gap_se_target", "achieved_gap_se", "style_slack")}}
            if f == "crowded_cutoff":
                top15 = [{"rank": i + 1, "bot": b, "mu": float(st[b]["mu_bb"]), "se": float(st[b]["se_bb"]),
                          "style": st[b]["style"], "archetype": st[b]["archetype"], "vpip": float(beh[b]["vpip"]),
                          "pfr": float(beh[b]["pfr"]), "threebet": float(beh[b]["threebet"]),
                          "fold_to_bet": float(beh[b]["post_fold_to_bet"])} for i, b in enumerate(ids[:15])]
                cl = ids[3:15]
                mus = np.array([float(st[b]["mu_bb"]) for b in cl])
                ses = np.array([float(st[b]["se_bb"]) for b in cl])
                bots = sorted(spec.field.bot_ids)
                groups = [group_stats(t, bots) for t in load_calibration(ROOT, spec)]
                ix = [bots.index(b) for b in cl]
                halves = [float(np.ptp(SplitHalf(g).stats(list(range(96)))[0][ix]) / BB)
                          for g in (groups[0::2], groups[1::2])]
                info["crowded"] = {
                    "top15": top15, "leaders": ids[:3],
                    "leader_distances": [round(param_distance(vecs, a, b), 3) for a, b in itertools.combinations(ids[:3], 2)],
                    "cluster_range_bb": float(np.ptp(mus)), "cluster_sd_bb": float(mus.std(ddof=1)),
                    "cluster_mean_se_bb": float(np.sqrt(np.mean(ses ** 2))),
                    "cluster_true_sd_bb": float(np.sqrt(max(mus.var(ddof=1) - np.mean(ses ** 2), 0))),
                    "heldout_half_ranges_bb": halves,
                    "pure_noise_range_expectation_bb": float(3.26 * np.sqrt(np.mean(ses ** 2)) * np.sqrt(2)),
                    "cluster_styles": dict(Counter(st[b]["style"] for b in cl)),
                    "cluster_archetypes": dict(Counter(st[b]["archetype"] for b in cl)),
                    "cluster_median_param_distance": float(np.median([param_distance(vecs, a, b)
                                                                       for a, b in itertools.combinations(cl, 2)])),
                    "cluster_ranges": {k: [min(float(beh[b][k]) for b in cl), max(float(beh[b][k]) for b in cl)]
                                       for k in ("vpip", "pfr", "threebet", "post_fold_to_bet")},
                    "near_dup_pairs_1_15": [(a, b, round(param_distance(vecs, a, b), 3))
                                            for a, b in itertools.combinations(ids[:15], 2)
                                            if param_distance(vecs, a, b) < 0.15]}
        # realism
        f = lambda k: np.array([float(beh[b][k]) for b in sorted(beh)])  # noqa: E731
        ns = chunk_stats(cal)
        keys = sorted(ns["bots"])
        mu = np.array([ns["bots"][k]["mu"] for k in keys])
        bust = np.array([ns["bots"][k]["bust"] for k in keys])
        pos = {p: float(np.nanmedian(f(f"vpip_{p}"))) for p in ("SB", "BB", "EP", "MP", "BTN")
               if not np.all(np.isnan(f(f"vpip_{p}")))}
        rev = json.loads((FC / "review/review.json").read_text())["modes"][mode]
        info["realism"] = {
            "vpip_range": [float(f("vpip").min()), float(f("vpip").max())], "vpip_median": float(np.median(f("vpip"))),
            "vpip_by_position": pos, "pfr_median": float(np.median(f("pfr"))),
            "threebet_median": float(np.median(f("threebet"))),
            "postflop_aggression_median": float(np.nanmedian(f("post_aggression"))),
            "fold_to_bet_median": float(np.nanmedian(f("post_fold_to_bet"))),
            "preflop_allin_rate_median": float(np.median(f("preflop_allin_rate"))),
            "preflop_allin_hand_pct_median": float(np.nanmedian(f("preflop_allin_mean_pct"))),
            "vpip_by_stack": [float(np.nanmedian(f(f"vpip_stack{i}"))) for i in range(4)],
            "allin_by_stack": [float(np.nanmedian(f(f"allin_stack{i}"))) for i in range(4)],
            "median_bust": float(np.median(bust)), "spearman_mu_bust": float(spearmanr(mu, bust)[0]),
            "early_ended": ns["early"], "clipped_bots": rev["bots_with_clipped_params"],
            "spearman_mu_clipped": rev["spearman_mu_vs_n_clipped"], "split_half_r_mu": rev["split_half_r_mu"],
            "median_se_bb": rev["median_se_bb"], "pool_sd_bb": rev["pool_mu_sd_bb"],
            "top5": [{"bot": k, "mu": float(ns["bots"][k]["mu"]), "bust": ns["bots"][k]["bust"],
                      "vpip": float(beh[f"{mode}-{k}"]["vpip"]), "pfr": float(beh[f"{mode}-{k}"]["pfr"]),
                      "threebet": float(beh[f"{mode}-{k}"]["threebet"]),
                      "uncontested_bb100": float(beh[f"{mode}-{k}"]["uncontested_bb_per_100"]),
                      "showdown_bb100": float(beh[f"{mode}-{k}"]["showdown_bb_per_100"]),
                      "style": beh[f"{mode}-{k}"]["style"],
                      "clipped": json.loads(st[f"{mode}-{k}"]["clipped"])}
                     for k in sorted(keys, key=lambda k: -ns["bots"][k]["mu"])[:5]]}
        info["hu_new"] = hu_replay(spec, cal, build_agent)
        # before vs after
        old_mode = replace(spec.mode, agent_family="heuristic")  # identity of the retired run
        old_spec = CalibrationSpec(old_mode, load_field(FHR3B_CONFIGS / f"fields/retired/hu-role-bug/{mode}/pool.json"),
                                   400, spec.stack_policy, spec.seed_family, "pool-calibration", spec.chunk_rounds)
        old_dir = ROOT / "calibration" / RETIRED_CAL[mode]
        assert old_spec.calib_id == RETIRED_CAL[mode]
        info["hu_old"] = hu_replay(old_spec, old_dir, fhr3a_build_agent)
        os_ = chunk_stats(old_dir)
        omu = np.array([os_["bots"][k]["mu"] for k in keys])
        obust = np.array([os_["bots"][k]["bust"] for k in keys])
        nr, orr = (-mu).argsort().argsort() + 1, (-omu).argsort().argsort() + 1
        top_new, top_old = {keys[i] for i in range(96) if nr[i] <= 6}, {keys[i] for i in range(96) if orr[i] <= 6}
        z = (mu - omu) / np.hypot([ns["bots"][k]["se"] for k in keys], [os_["bots"][k]["se"] for k in keys])
        oldbeh = {r["bot_id"].split("-", 1)[1]: r for r in rows(FC / f"retired_hu_role_bug/{mode}/behaviour.csv")}
        newst = {k: beh[f"{mode}-{k}"]["style"] for k in keys}
        arch = {k: spec.field.bots[[b["bot_id"] for b in spec.field.bots].index(f"{mode}-{k}")]["meta"]["archetype"]
                for k in keys}
        delta_by = lambda lab: {a: float(np.mean([mu[i] - omu[i] for i in range(96) if lab[keys[i]] == a]))  # noqa: E731
                                for a in sorted(set(lab.values()))}
        info["before_after"] = {
            "spearman": float(spearmanr(mu, omu)[0]), "kendall": float(kendalltau(mu, omu)[0]),
            "top6_overlap": len(top_new & top_old), "top6_new": sorted(top_new), "top6_old": sorted(top_old),
            "largest_rank_changes": [(keys[i], int(orr[i]), int(nr[i])) for i in np.argsort(-np.abs(nr - orr))[:5]],
            "largest_ev_gains": [(keys[i], round(float(omu[i]), 1), round(float(mu[i]), 1)) for i in np.argsort(omu - mu)[:5]],
            "largest_ev_losses": [(keys[i], round(float(omu[i]), 1), round(float(mu[i]), 1)) for i in np.argsort(mu - omu)[:5]],
            "n_abs_z_gt_3": int((np.abs(z) > 3).sum()),
            "ev_change_by_archetype": delta_by(arch), "ev_change_by_new_style": delta_by(newst),
            "median_bust_old": float(np.median(obust)), "median_bust_new": float(np.median(bust)),
            "early_ended_old": os_["early"], "early_ended_new": ns["early"],
            "style_changes": sum(oldbeh[k]["style"] != newst[k] for k in keys),
            "pool_sd_old": float(omu.std()), "pool_sd_new": float(mu.std())}
        new_mu[mode] = (keys, mu, newst)
        out["modes"][mode] = info
        print(mode, "done", flush=True)
    k4, m4, s4 = new_mu["nlhe4"]
    k6, m6, s6 = new_mu["nlhe6"]
    assert k4 == k6
    r4, r6 = (-m4).argsort().argsort() + 1, (-m6).argsort().argsort() + 1
    out["cross_format"] = {
        "spearman": float(spearmanr(m4, m6)[0]), "kendall": float(kendalltau(m4, m6)[0]),
        "top6_overlap": len({k4[i] for i in range(96) if r4[i] <= 6} & {k4[i] for i in range(96) if r6[i] <= 6}),
        "top6_nlhe4": sorted(k4[i] for i in range(96) if r4[i] <= 6),
        "top6_nlhe6": sorted(k4[i] for i in range(96) if r6[i] <= 6),
        "largest_4max_gains": [(k4[i], round(float(m4[i]), 1), round(float(m6[i]), 1), int(r4[i]), int(r6[i]))
                               for i in np.argsort(m6 - m4)[:5]],
        "largest_4max_losses": [(k4[i], round(float(m4[i]), 1), round(float(m6[i]), 1), int(r4[i]), int(r6[i]))
                                for i in np.argsort(m4 - m6)[:5]],
        "rank_change_gt_30": int((np.abs(r4 - r6) > 30).sum()),
        "style_changes": sum(s4[k] != s6[k] for k in k4)}
    p = FC / "review/nlhe_recalibration.json"
    p.write_text(json.dumps(out, indent=1, default=float) + "\n")
    print("wrote", p)


if __name__ == "__main__":
    main()
