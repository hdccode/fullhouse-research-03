"""Exact replay and independent validation of stored tournaments.

``validate_tournament_rows`` re-derives every invariant from the stored Parquet rows
without trusting the runner: each round's seating, zero-sum tables, score updates,
standings and ranks (recomputed with the Swiss standings rule), the adaptive Swiss
assignment (recomputed from the pre-round standings; round 1 from the seeded
order), the final leaderboard, the top-K cut and the digest.

``replay_tournament`` re-runs a tournament from its cell definition and replicate
index and compares digests (exact replay). ``replay_match_hands`` regenerates the
hand-level record of one table match: hand logs are never stored permanently.
``verify_prefix`` re-runs a shorter-R cell and checks it equals the R-prefix of the
stored R0 tournaments (the identity behind the derived round sweep).
"""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fhr3.tournament.batch import _schedule_for, run_cell
from fhr3.tournament.cells import Cell
from fhr3.tournament.match import MatchKey
from fhr3.tournament.runner import TournamentResult, initial_order, rows_digest, run_tournament
from fhr3.tournament.schedule import schedule_from_rows, validate_assignment
from fhr3.tournament.store import read_tournament_rows
from fhr3.tournament.swiss import compute_standings, initial_standings, positional_ranks, swiss_pairing


class ValidationError(AssertionError):
    pass


def _fail(msg: str) -> None:
    raise ValidationError(msg)


def validate_tournament_rows(cell: Cell, replicate: int, tables: Sequence[dict], final: Sequence[dict],
                             manifest: dict[str, Any], source_schedule: Any = None) -> None:
    p = cell.protocol
    bots = sorted(cell.field.bot_ids)
    spec = cell.tournament_spec(replicate, source_schedule if cell.kind == "frozen_replay" else None)
    if rows_digest(tables, final) != manifest["digest"]:
        _fail("digest mismatch")
    rounds = sorted({r["round"] for r in tables})
    if rounds != list(range(1, p.rounds + 1)):
        _fail(f"round count {len(rounds)} != R={p.rounds}")
    standings = initial_standings(initial_order(spec))
    results: list[tuple[str, int]] = []
    schedule = schedule_from_rows(tables)
    if cell.kind == "frozen_replay" and schedule != [[list(t) for t in r] for r in source_schedule]:
        _fail("frozen replay schedule differs from its source schedule")
    for rnd in rounds:
        rows = [r for r in tables if r["round"] == rnd]
        tabs = schedule[rnd - 1]
        validate_assignment(tabs, bots, p.table_size, 10)
        if cell.kind != "frozen_replay" and tabs != swiss_pairing(standings, p.table_size):
            _fail(f"round {rnd}: stored tables != Swiss rule on pre-round standings")
        pre_rank = {s.bot_id: i + 1 for i, s in enumerate(standings)}
        pre_score = {s.bot_id: s.cumulative_delta for s in standings}
        by_table: dict[int, int] = {}
        for r in rows:
            if r["pre_rank"] != pre_rank[r["bot_id"]] or r["pre_score"] != pre_score[r["bot_id"]]:
                _fail(f"round {rnd}: stored pre-round standing wrong for {r['bot_id']}")
            if r["match_seed"] != MatchKey(spec.seeds.chance_seed, spec.seeds.decision_seed, rnd,
                                           r["table_index"]).match_seed:
                _fail(f"round {rnd}: match seed mismatch")
            by_table[r["table_index"]] = by_table.get(r["table_index"], 0) + r["chip_delta"]
            results.append((r["bot_id"], r["chip_delta"]))
        if any(v != 0 for v in by_table.values()):
            _fail(f"round {rnd}: a table is not zero-sum")
        standings = compute_standings(results)
        ranks = positional_ranks(standings)
        post = {s.bot_id: s for s in standings}
        for r in rows:
            if r["post_score"] != post[r["bot_id"]].cumulative_delta or r["post_rank"] != ranks[r["bot_id"]]:
                _fail(f"round {rnd}: post-round standing wrong for {r['bot_id']}")
        if sum(s.cumulative_delta for s in standings) != 0:
            _fail(f"round {rnd}: tournament-wide conservation violated")
    ranks = positional_ranks(standings)
    fin = {r["bot_id"]: r for r in final}
    if sorted(fin) != bots:
        _fail("final table does not list every bot once")
    for s in standings:
        f = fin[s.bot_id]
        if f["final_score"] != s.cumulative_delta or f["final_rank"] != ranks[s.bot_id]:
            _fail(f"final standing wrong for {s.bot_id}")
        if f["qualified"] != (ranks[s.bot_id] <= p.qualify_top_k):
            _fail(f"qualification flag wrong for {s.bot_id}")
    if manifest["qualified"] != [s.bot_id for s in standings[: p.qualify_top_k]]:
        _fail("manifest qualifiers != top-K of recomputed standings")


def validate_cell(root: Path, cell: Cell, replicates: Sequence[int]) -> dict[str, Any]:
    checked = 0
    for rep in replicates:
        tables, final, man = read_tournament_rows(root, cell, rep)
        validate_tournament_rows(cell, rep, tables, final, man, _schedule_for(cell, Path(root), rep))
        checked += 1
    return {"cell_id": cell.cell_id, "validated": checked}


def replay_tournament(root: Path, cell: Cell, replicate: int, player: Any = None) -> TournamentResult:
    spec = cell.tournament_spec(replicate, _schedule_for(cell, Path(root), replicate))
    return run_tournament(spec, player or cell.make_player())


def check_replay(root: Path, cell: Cell, replicates: Sequence[int]) -> dict[str, Any]:
    player = cell.make_player()
    for rep in replicates:
        _, _, man = read_tournament_rows(root, cell, rep)
        res = replay_tournament(root, cell, rep, player)
        if res.digest != man["digest"]:
            _fail(f"replay of t{rep:06d} differs: {res.digest} != {man['digest']}")
    return {"cell_id": cell.cell_id, "replayed_exactly": len(replicates)}


def replay_match_hands(root: Path, cell: Cell, replicate: int, round_: int, table: int) -> list[dict[str, Any]]:
    """Regenerate the hand-by-hand record of one stored table match and check it."""
    tables, _, _ = read_tournament_rows(root, cell, replicate)
    rows = sorted((r for r in tables if r["round"] == round_ and r["table_index"] == table), key=lambda r: r["seat"])
    if not rows:
        raise KeyError(f"no table {table} in round {round_}")
    spec = cell.tournament_spec(replicate, _schedule_for(cell, Path(root), replicate))
    key = MatchKey(spec.seeds.chance_seed, spec.seeds.decision_seed, round_, table)
    log: list[dict[str, Any]] = []
    res = cell.make_player().play(key, [r["bot_id"] for r in rows], cell.protocol.hands_per_match, hand_log=log)
    if any(res.deltas[r["bot_id"]] != r["chip_delta"] for r in rows):
        _fail("regenerated match does not reproduce the stored chip deltas")
    return log


def verify_prefix(root: Path, base: Cell, rounds: int, replicates: Sequence[int]) -> dict[str, Any]:
    """Run the R=``rounds`` cell afresh (temp dir) and compare with the stored R0 prefix."""
    short = Cell(base.kind, base.mode, base.protocol.with_(rounds=rounds), base.field, base.seed_family,
                 base.namespace, synthetic=base.synthetic)
    with tempfile.TemporaryDirectory() as tmp:
        run_cell(short, Path(tmp), replicates, workers=1, progress=False)
        for rep in replicates:
            t_short, f_short, _ = read_tournament_rows(Path(tmp), short, rep)
            t_base, _, _ = read_tournament_rows(root, base, rep)
            strip = ("tournament_id",)
            a = [{k: v for k, v in r.items() if k not in strip} for r in t_short]
            b = [{k: v for k, v in r.items() if k not in strip} for r in t_base if r["round"] <= rounds]
            if a != b:
                _fail(f"R={rounds} tournament {rep} is not the R-prefix of the R0 tournament")
            last = {r["bot_id"]: r["post_rank"] for r in t_base if r["round"] == rounds}
            if any(f["final_rank"] != last[f["bot_id"]] for f in f_short):
                _fail(f"R={rounds} final ranks != R0 post-round-{rounds} ranks (t{rep})")
    return {"base": base.cell_id, "rounds": rounds, "replicates_checked": len(replicates)}
