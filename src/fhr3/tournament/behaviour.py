"""Behaviour audit: action-level play recovered by exact replay of pool-calibration matches.

Analysis only (outside the engine source hash). Pool calibration stores one row per bot per
match; action frequencies are recovered by replaying a sample of calibration rounds with
every agent wrapped in a transparent logging proxy (same RNG, same actions). **Every
replayed match must reproduce the stored chip deltas exactly** (asserted), so the audit sees
the calibration's actual play.

Outputs, in ``<reports>/field-calibration/<mode>/``:
* ``behaviour.csv``: per-bot VPIP, PFR, 3-bet, fold-to-bet, aggression, all-in propensity,
  VPIP by position and by stack depth, AoF shove/call rates, and winnings by showdown,
  uncontested and big pots;
* ``behaviour_audit.json``: replay provenance;
* ``focus_<bot>.csv``: every all-in decision of the inspected bots.

``style_classes`` maps behaviour onto the classic four-way taxonomy used for style balance
in field selection:
* NLHE: VPIP (tight/loose) x PFR/VPIP (passive/aggressive);
* AoF: call-vs-shove (tight/loose) x open-shove (passive/aggressive).

Thresholds are the pool medians.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from fhr3.tournament.agents import build_agent
from fhr3.agents.features import preflop_percentile
from fhr3.games.base import ActionKind, LegalActions
from fhr3.rng import derive_seed
from fhr3.tournament.calibration import calib_dir
from fhr3.tournament.experiments import load_profile
from fhr3.tournament.match import MatchKey, PokerMatchPlayer

BB = 100
FOCUS = {"nlhe6": ["nlhe6-maniac-e2-s2", "nlhe6-station-e2-s2", "nlhe6-trapper-e3-s3", "nlhe6-neutral-e1-s0"],
         "aof4": ["aof4-policy-e0"]}
STACK_BUCKETS = [(0, 40), (40, 80), (80, 150), (150, 10**9)]


def position_name(seat: int, m: int) -> str:
    if seat == m - 1:
        return "BTN"
    return {0: "SB", 1: "BB"}.get(seat, "EP" if seat == 2 and m >= 5 else "MP")


class Recorder:
    """Per-bot counters; one instance per worker."""

    def __init__(self, focus: set[str]) -> None:
        self.c: dict[str, defaultdict] = defaultdict(lambda: defaultdict(float))
        self.hand_state: dict[str, dict] = {}
        self.focus_rows: list[dict] = []
        self.focus = focus

    def decision(self, bot: str, obs, legal, action) -> None:
        c = self.c[bot]
        if not isinstance(legal, LegalActions):
            return
        m, seat = obs.player_count, obs.seat
        stack_bb = (obs.stacks[seat] + obs.bets[seat]) / BB
        to_call = obs.to_call
        allin = (action.kind is ActionKind.BET_RAISE and legal.raise_max is not None and action.amount == legal.raise_max) \
            or (action.kind is ActionKind.CHECK_CALL and to_call > 0 and to_call >= obs.stacks[seat])
        c["decisions"] += 1
        c["allin_decisions"] += allin
        if obs.street == 0:
            first = not any(h.seat == seat and h.street == 0 for h in obs.history)
            raises_before = sum(1 for h in obs.history if h.street == 0 and h.kind is ActionKind.BET_RAISE)
            if first:
                c["hands"] += 1
                pos = position_name(seat, m)
                c[f"hands_{pos}"] += 1
                bucket = next(i for i, (lo, hi) in enumerate(STACK_BUCKETS) if lo <= stack_bb < hi)
                c[f"hands_stack{bucket}"] += 1
                self.hand_state[bot] = {"vpip": False, "pfr": False, "pos": pos, "bucket": bucket, "allin": False}
                if raises_before == 0 and action.kind is not ActionKind.FOLD:
                    c["unopened_voluntary"] += action.kind is ActionKind.BET_RAISE
                if raises_before == 0:
                    c["unopened_opps"] += 1
                if raises_before >= 1:
                    c["facing_raise_opps"] += 1
                    c["threebet"] += action.kind is ActionKind.BET_RAISE
                    c["call_vs_raise"] += action.kind is ActionKind.CHECK_CALL
            hs = self.hand_state.get(bot)
            if hs is not None:
                voluntary = action.kind is ActionKind.BET_RAISE or (action.kind is ActionKind.CHECK_CALL and to_call > 0)
                if voluntary and not hs["vpip"]:
                    hs["vpip"] = True
                    c["vpip"] += 1
                    c[f"vpip_{hs['pos']}"] += 1
                    c[f"vpip_stack{hs['bucket']}"] += 1
                if action.kind is ActionKind.BET_RAISE and not hs["pfr"]:
                    hs["pfr"] = True
                    c["pfr"] += 1
                if allin and not hs["allin"]:
                    hs["allin"] = True
                    c["preflop_allin_hands"] += 1
                    c[f"allin_stack{hs['bucket']}"] += 1
                    c["preflop_allin_pct_sum"] += preflop_percentile(obs.hole_cards)
        else:
            if to_call > 0:
                c["post_facing_bet"] += 1
                c["post_fold_to_bet"] += action.kind is ActionKind.FOLD
                c["post_call"] += action.kind is ActionKind.CHECK_CALL
            c["post_raise"] += action.kind is ActionKind.BET_RAISE
        if bot in self.focus and allin:
            self.focus_rows.append({"bot": bot, "street": obs.street, "position": position_name(seat, m),
                                    "players": m, "hole": " ".join(obs.hole_cards), "board": " ".join(obs.board),
                                    "preflop_pct": round(preflop_percentile(obs.hole_cards), 3),
                                    "stack_bb": round(stack_bb, 1), "to_call_bb": to_call / BB,
                                    "pot_bb": obs.pot / BB, "action": action.kind.value})


class Logged:
    """Transparent proxy: same ``act`` result, same RNG consumption."""

    def __init__(self, inner, rec: Recorder) -> None:
        self.inner, self.rec = inner, rec
        self.agent_id, self.version = inner.agent_id, inner.version

    def act(self, observation, legal_actions, rng):
        a = self.inner.act(observation, legal_actions, rng)
        self.rec.decision(self.agent_id, observation, legal_actions, a)
        return a


def replay_round(args):
    mode, r, profile, root = args
    prof = load_profile(profile, Path(root))
    spec = prof.calibration_spec(mode, "pool")
    rec = Recorder(set(FOCUS.get(mode, [])))
    agents = {b: Logged(build_agent(s), rec) for b, s in spec.field.specs().items()}
    player = PokerMatchPlayer(spec.mode.game, spec.stack_policy, agents)
    chance = derive_seed("fhr3b-calibration-chance", spec.seed)
    decision = derive_seed("fhr3b-calibration-decision", spec.seed)
    deltas, wins = {}, defaultdict(lambda: defaultdict(float))
    for t, seats in enumerate(spec.partition(r)):
        log: list[dict] = []
        res = player.play(MatchKey(chance, decision, r, t), seats, spec.hands_per_match, hand_log=log)
        for b, d in res.deltas.items():
            deltas[(r, t, b)] = d
        for h in log:
            big = h["pot"] >= 100 * BB
            for p, b in enumerate(h["positions"]):
                pay = h["payoffs"][p]
                w = wins[b]
                w["showdown" if h["showdown"] else "uncontested"] += pay
                if big:
                    w["big_pot_net"] += pay
                w["hands_played"] += 1
    counters = {b: dict(v) for b, v in rec.c.items()}
    return deltas, counters, {b: dict(v) for b, v in wins.items()}, rec.focus_rows


def rate(c, num, den):
    return c.get(num, 0.0) / c[den] if c.get(den, 0) else float("nan")



def style_classes(rows: list[dict], agent_family: str) -> dict[str, str]:
    """bot_id -> style code (TA / LA / TP / LP) from behaviour, thresholds at pool medians."""
    def val(r, k):
        v = float(r[k])
        return v if np.isfinite(v) else 0.0
    if agent_family == "aof":
        x = {r["bot_id"]: val(r, "call_vs_raise") for r in rows}
        y = {r["bot_id"]: val(r, "open_raise") for r in rows}
    else:
        x = {r["bot_id"]: val(r, "vpip") for r in rows}
        y = {r["bot_id"]: val(r, "pfr") / max(val(r, "vpip"), 1e-9) for r in rows}
    mx, my = float(np.median(list(x.values()))), float(np.median(list(y.values())))
    return {b: ("L" if x[b] > mx else "T") + ("A" if y[b] > my else "P") for b in x}


STYLE_NAMES = {
    "nlhe": {"TA": "tight-aggressive", "LA": "loose-aggressive", "TP": "tight-passive", "LP": "loose-passive"},
    "aof": {"TA": "tight caller / frequent shover", "LA": "loose caller / frequent shover",
            "TP": "tight caller / selective shover", "LP": "loose caller / selective shover"},
}


def behaviour_path(reports: Path, mode: str) -> Path:
    return Path(reports) / "field-calibration" / mode / "behaviour.csv"


def load_behaviour(reports: Path, mode: str) -> list[dict]:
    with behaviour_path(reports, mode).open() as fh:
        return list(csv.DictReader(fh))


def run_behaviour_audit(root: Path, profile: str, mode: str, reports: Path, rounds: int = 20,
                        workers: int = 8) -> dict:
    prof = load_profile(profile, Path(root))
    spec = prof.calibration_spec(mode, "pool")
    stored = {}
    for f in sorted((calib_dir(root, spec) / "chunks").glob("c_*.parquet")):
        t = pq.read_table(f).to_pydict()
        for r, ti, bid, d in zip(t["round"], t["table_index"], t["bot_id"], t["chip_delta"], strict=True):
            stored[(r, ti, bid)] = d
    available = sorted({k[0] for k in stored})
    if not available:
        raise FileNotFoundError(f"no pool calibration for {mode}")
    rounds = min(rounds, len(available))
    use = available[:rounds]
    stored = {k: v for k, v in stored.items() if k[0] in set(use)}
    args = [(mode, r, profile, str(root)) for r in use]
    if workers <= 1:
        results = [replay_round(a) for a in args]
    else:
        with ProcessPoolExecutor(workers, mp_context=get_context("spawn")) as ex:
            results = list(ex.map(replay_round, args))
    replayed = {}
    C: dict[str, defaultdict] = defaultdict(lambda: defaultdict(float))
    W: dict[str, defaultdict] = defaultdict(lambda: defaultdict(float))
    focus = []
    for deltas, counters, wins, frows in results:
        replayed |= deltas
        for b, c in counters.items():
            for k, v in c.items():
                C[b][k] += v
        for b, w in wins.items():
            for k, v in w.items():
                W[b][k] += v
        focus += frows
    mismatches = sum(1 for k, v in replayed.items() if stored.get(k) != v)
    if len(replayed) != len(stored) or mismatches:
        raise AssertionError(f"{mode}: replay does not reproduce stored calibration ({mismatches} mismatches)")
    meta = {b["bot_id"]: b["meta"] for b in spec.field.bots}
    rows = []
    for b in sorted(C):
        c, w = C[b], W[b]
        hp = max(w["hands_played"], 1)
        row = {"bot_id": b, "archetype": meta[b]["archetype"], "scale_index": meta[b]["scale_index"],
               "hands_with_decision": int(c["hands"]), "vpip": rate(c, "vpip", "hands"),
               "pfr": rate(c, "pfr", "hands"), "open_raise": rate(c, "unopened_voluntary", "unopened_opps"),
               "threebet": rate(c, "threebet", "facing_raise_opps"),
               "call_vs_raise": rate(c, "call_vs_raise", "facing_raise_opps"),
               "post_fold_to_bet": rate(c, "post_fold_to_bet", "post_facing_bet"),
               "post_aggression": (c["post_raise"] / c["post_call"]) if c.get("post_call") else float("nan"),
               "allin_decision_rate": rate(c, "allin_decisions", "decisions"),
               "preflop_allin_rate": rate(c, "preflop_allin_hands", "hands"),
               "preflop_allin_mean_pct": rate(c, "preflop_allin_pct_sum", "preflop_allin_hands"),
               "showdown_bb_per_100": 100 * w["showdown"] / BB / hp,
               "uncontested_bb_per_100": 100 * w["uncontested"] / BB / hp,
               "big_pot_bb_per_100": 100 * w["big_pot_net"] / BB / hp}
        for pos in ("SB", "BB", "EP", "MP", "BTN"):
            row[f"vpip_{pos}"] = rate(c, f"vpip_{pos}", f"hands_{pos}")
        for i in range(len(STACK_BUCKETS)):
            row[f"vpip_stack{i}"] = rate(c, f"vpip_stack{i}", f"hands_stack{i}")
            row[f"allin_stack{i}"] = rate(c, f"allin_stack{i}", f"hands_stack{i}")
            row[f"hands_stack{i}"] = int(c.get(f"hands_stack{i}", 0))
        rows.append(row)
    styles = style_classes(rows, spec.mode.agent_family)
    for r in rows:
        r["style"] = styles[r["bot_id"]]
    out = behaviour_path(reports, mode)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        wri = csv.DictWriter(fh, fieldnames=list(rows[0]))
        wri.writeheader()
        for r in rows:
            wri.writerow({k: (f"{v:.5g}" if isinstance(v, float) else v) for k, v in r.items()})
    for b in FOCUS.get(mode, []):
        fr = [x for x in focus if x["bot"] == b]
        if fr:
            with (out.parent / f"focus_{b}.csv").open("w", newline="") as fh:
                wri = csv.DictWriter(fh, fieldnames=list(fr[0]))
                wri.writeheader()
                wri.writerows(fr)
    info = {"mode": mode, "profile": profile, "calib_id": spec.calib_id, "rounds_replayed": use,
            "matches_replayed": len({(k[0], k[1]) for k in replayed}), "bot_match_results_verified": len(replayed),
            "replay_matches_stored_deltas": True,
            "behaviour_csv_sha256": hashlib.sha256(out.read_bytes()).hexdigest()}
    (out.parent / "behaviour_audit.json").write_text(json.dumps(info, indent=1) + "\n")
    return info
