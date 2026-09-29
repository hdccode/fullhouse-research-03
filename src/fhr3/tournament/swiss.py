"""FullHouse-style Swiss pairing, standings and qualification cut (public 2026 engine rule).

Line-for-line port of the public canonical reference

    github.com/mbatv/fullhouse-engine  (formerly uzlez/fullhouse-engine)
    commit a80b26957db5f5515d9273a15d1b73aadf8985db, engine/tournament.py
    sha256 9759284729099b98d7e784824fc7ff8705c1fa846c6b8ebede848832e4a2325a

vendored byte-identically under ``tests/data/fhr3b/fullhouse_engine_a80b269/`` and
checked by a golden test. It is the architectural provenance of the FHR3B research
baseline (``fhr3b_baseline``). The 2026 production queue shipped "its own copy in the
private ops repo", which is not available, so this is not a verified copy of production
(docs/fhr3b/2026_protocol_audit.md).

Reference semantics kept exactly:

* pairing sorts by ``-cumulative_delta`` only, with a *stable* sort, so equal scores keep
  the order of the input list (the tiebreak-sorted standings, or the initial order
  before any match);
* tables are consecutive slices of ``table_size``; a remainder smaller than
  ``table_size`` is folded into the last table ("stragglers"); a field smaller than one
  table is a single table;
* standings: cumulative chip delta DESC, matches played ASC, best single-match delta
  DESC, bot_id ASC;
* the qualification cut is the first ``n`` standings.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

PAIRING_ALGORITHM = "fh2026-reference-swiss"
PAIRING_VERSION = "fh2026-reference-swiss-v1"
TIEBREAKS = (
    "cumulative_delta DESC",
    "matches_played ASC",
    "best_match_delta DESC",
    "bot_id ASC",
)
REFERENCE_SOURCE = {
    "repository": "https://github.com/mbatv/fullhouse-engine",
    "former_name": "uzlez/fullhouse-engine",
    "commit": "a80b26957db5f5515d9273a15d1b73aadf8985db",
    "file": "engine/tournament.py",
    "sha256": "9759284729099b98d7e784824fc7ff8705c1fa846c6b8ebede848832e4a2325a",
    "production_equivalence": "UNVERIFIED (production queue used a private ops-repo copy)",
}


@dataclass(frozen=True)
class Standing:
    bot_id: str
    cumulative_delta: int = 0
    matches_played: int = 0
    best_match_delta: int | None = None  # None before the bot's first match

    def sort_key(self) -> tuple[int, int, int, str]:
        best = self.best_match_delta if self.best_match_delta is not None else 0
        return (-self.cumulative_delta, self.matches_played, -best, self.bot_id)


def initial_standings(order: Sequence[str]) -> list[Standing]:
    """Standings before round 1: every bot at zero, in the given (unsorted) order.

    The reference demo pairs round 1 from the raw bot list; its order therefore
    decides the round-1 tables. The FHR3B protocol makes that order explicit
    (``initial_order``).
    """
    if len(set(order)) != len(order):
        raise ValueError("duplicate bot ids in initial order")
    return [Standing(b) for b in order]


def compute_standings(results: Iterable[tuple[str, int]]) -> list[Standing]:
    """``results``: (bot_id, chip_delta) per completed match, in any order.

    Only bots with at least one result appear (as in the reference).
    """
    totals: dict[str, list[int]] = {}
    for bot_id, delta in results:
        delta = int(delta)
        t = totals.get(bot_id)
        if t is None:
            totals[bot_id] = [delta, 1, delta]
        else:
            t[0] += delta
            t[1] += 1
            if delta > t[2]:
                t[2] = delta
    out = [Standing(b, c, m, best) for b, (c, m, best) in totals.items()]
    return sorted(out, key=Standing.sort_key)


def swiss_pairing(standings: Sequence[Standing], table_size: int) -> list[list[str]]:
    """Tables for the next round, each a list of bot ids in seat order."""
    if table_size < 2:
        raise ValueError("table_size must be >= 2")
    ordered = sorted(standings, key=lambda s: -s.cumulative_delta)  # stable, as the reference
    ids = [s.bot_id for s in ordered]
    tables: list[list[str]] = []
    i = 0
    while i < len(ids):
        remaining = len(ids) - i
        if remaining < table_size and tables:
            tables[-1].extend(ids[i:])
            break
        tables.append(ids[i : i + table_size])
        i += table_size
    return tables


def select_finalists(standings: Sequence[Standing], n: int) -> list[Standing]:
    return list(standings[:n])


def positional_ranks(standings: Sequence[Standing]) -> dict[str, int]:
    """1-based rank by full tiebreak order (what the qualification cut uses)."""
    return {s.bot_id: i + 1 for i, s in enumerate(standings)}


def dense_ranks(standings: Sequence[Standing]) -> dict[str, int]:
    """Leaderboard display rank of the reference DB (dense_rank over cumulative delta)."""
    out: dict[str, int] = {}
    rank, prev = 0, None
    for s in sorted(standings, key=Standing.sort_key):
        if s.cumulative_delta != prev:
            rank += 1
            prev = s.cumulative_delta
        out[s.bot_id] = rank
    return out


def table_sizes_legal(tables: Sequence[Sequence[str]], table_size: int, n_bots: int) -> bool:
    """Table sizes that ``swiss_pairing`` can produce for ``n_bots``."""
    if n_bots < table_size:
        return len(tables) == 1 and len(tables[0]) == n_bots
    full, rem = divmod(n_bots, table_size)
    expected = [table_size] * full
    expected[-1] += rem
    return [len(t) for t in tables] == expected
