"""Run one complete Swiss tournament (the FHR3B statistical unit).

    field -> round-1 order -> [tables -> matches -> chip deltas -> standings] x R
          -> final leaderboard -> top-K qualification

``run_tournament`` is a pure function of (protocol, field, seeds, schedule kind):
every draw is keyed (match.py), so a tournament replays exactly from its manifest
and the result does not depend on worker count or execution order.

Hard gates (raise on violation): each round every bot sits exactly once, nobody
twice at a table, legal table sizes, no duplicated table, one score update per bot,
zero-sum tables, tournament-wide conservation, final scores equal the sum of round
deltas, standings reproducible from scores, and the adaptive assignment equals the
Swiss rule applied to the pre-round standings.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from fhr3.rng import KeyedStream
from fhr3.tournament.match import MatchKey, MatchPlayer
from fhr3.tournament.manifests import TournamentSeeds
from fhr3.tournament.protocol import TournamentProtocol
from fhr3.tournament.schedule import AdaptiveSchedule, FrozenSchedule, Schedule, validate_assignment
from fhr3.tournament.swiss import (
    Standing,
    compute_standings,
    dense_ranks,
    initial_standings,
    positional_ranks,
    swiss_pairing,
)

TABLE_COLUMNS = (
    "tournament_id", "replicate", "round", "table_index", "seat", "table_size", "bot_id",
    "pre_score", "pre_rank", "match_seed", "chip_delta", "hands_played", "bust_hand",
    "post_score", "post_rank", "post_best_match_delta",
)
FINAL_COLUMNS = (
    "tournament_id", "replicate", "bot_id", "final_score", "final_rank", "qualified",
    "matches_played", "best_match_delta", "dense_rank",
)


class TournamentInvariantError(AssertionError):
    pass


@dataclass(frozen=True)
class TournamentSpec:
    tournament_id: str
    cell_id: str
    replicate: int
    protocol: TournamentProtocol
    bot_ids: tuple[str, ...]
    seeds: TournamentSeeds
    max_table_size: int = 10
    frozen_schedule: tuple[tuple[tuple[str, ...], ...], ...] | None = None

    @property
    def schedule_kind(self) -> str:
        return "frozen" if self.frozen_schedule is not None else "adaptive"


@dataclass
class TournamentResult:
    spec: TournamentSpec
    table_rows: list[dict[str, Any]]
    final_rows: list[dict[str, Any]]
    schedule: list[list[list[str]]]
    hands_played: int
    runtime_s: float
    digest: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def final_ranking(self) -> list[str]:
        return [r["bot_id"] for r in sorted(self.final_rows, key=lambda r: r["final_rank"])]

    @property
    def qualified(self) -> list[str]:
        return [r["bot_id"] for r in sorted(self.final_rows, key=lambda r: r["final_rank"]) if r["qualified"]]

    def manifest(self) -> dict[str, Any]:
        s = self.spec
        p = s.protocol
        return {
            "tournament_id": s.tournament_id,
            "cell_id": s.cell_id,
            "replicate": s.replicate,
            "schedule_kind": s.schedule_kind,
            "seeds": s.seeds.to_dict(),
            "protocol_hash": p.protocol_hash,
            "R": p.rounds, "H": p.hands_per_match, "N": len(s.bot_ids), "K": p.qualify_top_k,
            "final_ranking": self.final_ranking,
            "qualified": self.qualified,
            "digest": self.digest,
            "schedule_digest": schedule_digest(self.schedule),
            "hands_played": self.hands_played,
            "runtime_s": round(self.runtime_s, 3),
        } | self.extra


def rows_digest(table_rows: Sequence[dict[str, Any]], final_rows: Sequence[dict[str, Any]]) -> str:
    """Hash of the analytical content (row values only; runtime/metadata excluded)."""
    h = hashlib.sha256()
    for rows, cols in ((table_rows, TABLE_COLUMNS), (final_rows, FINAL_COLUMNS)):
        for r in rows:
            h.update(json.dumps([r[c] for c in cols], separators=(",", ":")).encode())
            h.update(b"\n")
        h.update(b"|")
    return h.hexdigest()[:32]


def schedule_digest(schedule: Sequence[Sequence[Sequence[str]]]) -> str:
    return hashlib.sha256(json.dumps(schedule, separators=(",", ":")).encode()).hexdigest()[:32]


def initial_order(spec: TournamentSpec) -> list[str]:
    ids = sorted(spec.bot_ids)
    if spec.protocol.initial_order == "seeded_shuffle":
        return KeyedStream("fhr3b-initial-order", spec.seeds.order_seed).shuffle(ids)
    return list(spec.bot_ids)


def run_tournament(spec: TournamentSpec, player: MatchPlayer) -> TournamentResult:
    t0 = time.perf_counter()
    p = spec.protocol
    bots = list(spec.bot_ids)
    n = len(bots)
    if len(set(bots)) != n:
        raise TournamentInvariantError("duplicate bot ids in field")
    if p.qualify_top_k > n:
        raise ValueError(f"K={p.qualify_top_k} exceeds field size {n}")
    schedule: Schedule
    if spec.frozen_schedule is not None:
        schedule = FrozenSchedule(spec.frozen_schedule)
    else:
        schedule = AdaptiveSchedule(p.table_size)

    standings: list[Standing] = initial_standings(initial_order(spec))
    all_results: list[tuple[str, int]] = []
    table_rows: list[dict[str, Any]] = []
    used_schedule: list[list[list[str]]] = []
    hands_total = 0
    for rnd in range(1, p.rounds + 1):
        tables = schedule.tables(rnd, standings)
        validate_assignment(tables, bots, p.table_size, spec.max_table_size,
                            enforce_swiss_sizes=True)
        if schedule.kind == "adaptive" and tables != swiss_pairing(standings, p.table_size):
            raise TournamentInvariantError(f"round {rnd}: assignment differs from the Swiss rule")
        pre_score = {s.bot_id: s.cumulative_delta for s in standings}
        pre_rank = {s.bot_id: i + 1 for i, s in enumerate(standings)}
        round_delta: dict[str, int] = {}
        round_rows = []
        for t_idx, seat_order in enumerate(tables):
            key = MatchKey(spec.seeds.chance_seed, spec.seeds.decision_seed, rnd, t_idx)
            res = player.play(key, seat_order, p.hands_per_match)
            if sorted(res.deltas) != sorted(seat_order):
                raise TournamentInvariantError(f"round {rnd} table {t_idx}: result bots != seated bots")
            if player.zero_sum and sum(res.deltas.values()) != 0:
                raise TournamentInvariantError(f"round {rnd} table {t_idx}: chip deltas do not sum to zero")
            hands_total += res.hands_played
            for seat, b in enumerate(seat_order):
                if b in round_delta:
                    raise TournamentInvariantError(f"round {rnd}: {b} scored twice")
                d = int(res.deltas[b])
                round_delta[b] = d
                all_results.append((b, d))
                round_rows.append({
                    "tournament_id": spec.tournament_id, "replicate": spec.replicate, "round": rnd,
                    "table_index": t_idx, "seat": seat, "table_size": len(seat_order), "bot_id": b,
                    "pre_score": pre_score[b], "pre_rank": pre_rank[b], "match_seed": key.match_seed,
                    "chip_delta": d, "hands_played": res.hands_played,
                    "bust_hand": int(res.bust_hand.get(b, -1)),
                })
        if len(round_delta) != n:
            raise TournamentInvariantError(f"round {rnd}: {n - len(round_delta)} bots without a result")
        standings = compute_standings(all_results)
        post_rank = positional_ranks(standings)
        post = {s.bot_id: s for s in standings}
        for r in round_rows:
            s = post[r["bot_id"]]
            if s.cumulative_delta != r["pre_score"] + r["chip_delta"]:
                raise TournamentInvariantError(f"round {rnd}: score update mismatch for {r['bot_id']}")
            r["post_score"] = s.cumulative_delta
            r["post_rank"] = post_rank[r["bot_id"]]
            r["post_best_match_delta"] = s.best_match_delta
        if player.zero_sum and sum(s.cumulative_delta for s in standings) != 0:
            raise TournamentInvariantError(f"round {rnd}: tournament-wide chips not conserved")
        table_rows.extend(round_rows)
        used_schedule.append([list(t) for t in tables])

    # Final leaderboard and top-K cut.
    final_ranks = positional_ranks(standings)
    dense = dense_ranks(standings)
    totals: dict[str, int] = {}
    for b, d in all_results:
        totals[b] = totals.get(b, 0) + d
    final_rows = []
    for s in standings:
        if totals[s.bot_id] != s.cumulative_delta or s.matches_played != p.rounds:
            raise TournamentInvariantError(f"final score for {s.bot_id} != sum of round deltas")
        rank = final_ranks[s.bot_id]
        final_rows.append({
            "tournament_id": spec.tournament_id, "replicate": spec.replicate, "bot_id": s.bot_id,
            "final_score": s.cumulative_delta, "final_rank": rank, "qualified": rank <= p.qualify_top_k,
            "matches_played": s.matches_played, "best_match_delta": s.best_match_delta,
            "dense_rank": dense[s.bot_id],
        })
    if compute_standings(all_results) != standings:
        raise TournamentInvariantError("final standings not reproducible from scores")
    res = TournamentResult(spec, table_rows, final_rows, used_schedule, hands_total,
                           time.perf_counter() - t0)
    res.digest = rows_digest(table_rows, final_rows)
    return res
