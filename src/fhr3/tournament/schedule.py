"""Table schedules: adaptive Swiss (the baseline) and frozen (research-only diagnostic).

A schedule is, per round, the list of tables, each a tuple of bot ids in seat order.

* ``AdaptiveSchedule`` recomputes each round's tables from the current standings with
  the reconstructed 2026 Swiss pairing (the competition rule).
* ``FrozenSchedule`` replays the complete table assignment of a source tournament.
  Later results cannot change later opponents. This counterfactual exists only to
  measure path dependence (Experiment C); it is **not** a proposed competition format.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Protocol

from fhr3.tournament.swiss import Standing, swiss_pairing, table_sizes_legal

Tables = list[list[str]]


class Schedule(Protocol):
    kind: str

    def tables(self, round_: int, standings: Sequence[Standing]) -> Tables: ...


class AdaptiveSchedule:
    kind = "adaptive"

    def __init__(self, table_size: int) -> None:
        self.table_size = table_size

    def tables(self, round_: int, standings: Sequence[Standing]) -> Tables:
        return swiss_pairing(standings, self.table_size)


class FrozenSchedule:
    kind = "frozen"

    def __init__(self, rounds: Sequence[Sequence[Sequence[str]]]) -> None:
        self.rounds = [[list(t) for t in r] for r in rounds]

    def tables(self, round_: int, standings: Sequence[Standing]) -> Tables:
        if round_ > len(self.rounds):
            raise ValueError(f"frozen schedule has {len(self.rounds)} rounds, asked for round {round_}")
        return [list(t) for t in self.rounds[round_ - 1]]


def schedule_from_rows(rows: Iterable[Mapping[str, Any]]) -> list[list[list[str]]]:
    """Rebuild the per-round table list from stored table rows."""
    by: dict[int, dict[int, list[tuple[int, str]]]] = {}
    for r in rows:
        by.setdefault(int(r["round"]), {}).setdefault(int(r["table_index"]), []).append((int(r["seat"]), r["bot_id"]))
    out = []
    for rnd in sorted(by):
        if rnd != len(out) + 1:
            raise ValueError("schedule rounds are not contiguous from 1")
        tables = by[rnd]
        out.append([[b for _, b in sorted(tables[t])] for t in sorted(tables)])
    return out


class ScheduleViolation(AssertionError):
    pass


def validate_assignment(tables: Sequence[Sequence[str]], bot_ids: Sequence[str], table_size: int,
                        max_table_size: int, enforce_swiss_sizes: bool = True) -> None:
    """Every active bot exactly once, nobody twice at a table, legal table sizes."""
    seen: list[str] = [b for t in tables for b in t]
    if sorted(seen) != sorted(bot_ids):
        missing = sorted(set(bot_ids) - set(seen))
        extra = sorted(set(seen) - set(bot_ids))
        dup = sorted({b for b in seen if seen.count(b) > 1})
        raise ScheduleViolation(f"assignment mismatch: missing={missing} extra={extra} duplicated={dup}")
    for t in tables:
        if len(t) < 2:
            raise ScheduleViolation(f"table with {len(t)} bots")
        if len(t) > max_table_size:
            raise ScheduleViolation(
                f"table of {len(t)} bots exceeds the mode's maximum {max_table_size} "
                "(the 2026 straggler rule is undefined here)")
    if enforce_swiss_sizes and not table_sizes_legal(tables, table_size, len(bot_ids)):
        raise ScheduleViolation(f"table sizes {[len(t) for t in tables]} not producible by the Swiss rule")
    keys = [tuple(t) for t in tables]
    if len(set(keys)) != len(keys):
        raise ScheduleViolation("duplicated table assignment")
