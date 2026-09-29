"""Tournament protocol: the frozen, hashed definition of one Swiss competition format.

A protocol fixes everything that decides who plays whom and how a bot is scored:
table size, hands per table match (H), Swiss rounds (R), the stack rule inside a
match, pairing algorithm, straggler rule, round-1 order, scoring, tiebreaks and the
qualification cut (K). Changing any of these changes ``protocol_hash`` and therefore
the experiment identity. Replication counts, workers and output paths are not part
of the protocol.

Sweep generators derive the round sweep (Experiment A) and fixed-budget allocations
(Experiment B) from the baseline (R0, H0) instead of hard-coding values.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

from fhr3.configs.experiment import canonical_hash
from fhr3.tournament.swiss import PAIRING_ALGORITHM, PAIRING_VERSION, TIEBREAKS

STACK_POLICIES = ("persistent_no_rebuy", "reset_each_hand")
INITIAL_ORDERS = ("seeded_shuffle", "field_order")
# research: FHR3B controlled protocols; smoke: correctness only; historical: built from a
# *complete* historical record (fhr3.tournament.historical), never from research choices.
STATUSES = ("research", "smoke", "historical")
# Variants whose match can carry stacks across hands (see match.py)
PERSISTENT_OK = frozenset({"nlhe", "plo", "crazy_pineapple"})


@dataclass(frozen=True)
class TournamentProtocol:
    name: str
    status: str
    table_size: int
    hands_per_match: int  # H
    rounds: int  # R
    qualify_top_k: int  # K
    stack_policy: str = "persistent_no_rebuy"
    initial_order: str = "seeded_shuffle"
    scoring: str = "cumulative_chip_delta"
    pairing: str = PAIRING_ALGORITHM
    pairing_version: str = PAIRING_VERSION
    straggler_rule: str = "fold_into_last_table"
    tiebreaks: tuple[str, ...] = TIEBREAKS
    seat_order: str = "standings_order"
    dealer_rule: str = "fh2026_dealer_counter"
    source: Mapping[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        if self.stack_policy not in STACK_POLICIES:
            raise ValueError(f"stack_policy must be one of {STACK_POLICIES}")
        if self.initial_order not in INITIAL_ORDERS:
            raise ValueError(f"initial_order must be one of {INITIAL_ORDERS}")
        if self.scoring != "cumulative_chip_delta":
            raise ValueError("FHR3B baseline scoring is raw cumulative chip delta only")
        if self.pairing != PAIRING_ALGORITHM:
            raise ValueError(f"only {PAIRING_ALGORITHM!r} pairing is implemented")
        for name in ("table_size", "hands_per_match", "rounds", "qualify_top_k"):
            if int(getattr(self, name)) < 1:
                raise ValueError(f"{name} must be positive")
        if self.table_size < 2:
            raise ValueError("table_size must be >= 2")

    # Hash covers every result-relevant field; ``notes`` are documentation only.
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["tiebreaks"] = list(self.tiebreaks)
        d["source"] = dict(self.source)
        d.pop("notes")
        return d

    @property
    def protocol_hash(self) -> str:
        return canonical_hash(self.to_dict())[:16]

    @property
    def hand_budget_per_bot(self) -> int:
        return self.rounds * self.hands_per_match

    def with_(self, **changes: Any) -> TournamentProtocol:
        return replace(self, **changes)

    def check_variant(self, variant: str) -> None:
        if self.stack_policy == "persistent_no_rebuy" and variant not in PERSISTENT_OK:
            raise ValueError(
                f"stack_policy persistent_no_rebuy is only defined for {sorted(PERSISTENT_OK)}; "
                f"{variant!r} uses reset_each_hand"
            )


def protocol_from_dict(raw: Mapping[str, Any]) -> TournamentProtocol:
    d = dict(raw)
    d["tiebreaks"] = tuple(d.get("tiebreaks", TIEBREAKS))
    d["notes"] = tuple(d.get("notes", ()))
    d["source"] = dict(d.get("source", {}) or {})
    for k in ("unknowns", "facts"):
        d.pop(k, None)  # audit annotations in the YAML, not protocol fields
    return TournamentProtocol(**d)


def load_protocol(path: str | Path) -> TournamentProtocol:
    with open(path) as fh:
        return protocol_from_dict(yaml.safe_load(fh))


# ------------------------------------------------------------------ sweep generators
ROUND_FRACTIONS = (1 / 8, 1 / 4, 1 / 2, 3 / 4, 1.0)


def round_sweep(r0: int, fractions: tuple[float, ...] = ROUND_FRACTIONS) -> list[int]:
    """Approximately R0/8, R0/4, R0/2, 3R0/4, R0 as distinct integers >= 1; R0 always included."""
    if r0 < 1:
        raise ValueError("R0 must be >= 1")
    vals = {max(1, round(r0 * f)) for f in fractions}
    vals.add(r0)
    return sorted(vals)


@dataclass(frozen=True)
class BudgetAllocation:
    rounds: int
    hands_per_match: int
    label: str
    exact: bool  # rounds * hands == R0 * H0 exactly

    @property
    def budget(self) -> int:
        return self.rounds * self.hands_per_match


def budget_allocations(r0: int, h0: int, divisors: tuple[int, ...] = (4, 2, 1)) -> list[BudgetAllocation]:
    """Fixed hand budget B = R0*H0 re-allocated: R0/d rounds of d*H0 hands.

    Exact whenever d divides R0; otherwise R = round(R0/d) and H = round(B/R),
    flagged ``exact=False`` (the budget deviation is then |R*H - B|).
    """
    out = []
    budget = r0 * h0
    for d in divisors:
        label = {1: "baseline", 2: "half_rounds_2x_hands", 4: "quarter_rounds_4x_hands"}.get(d, f"rounds_div{d}")
        if r0 % d == 0:
            out.append(BudgetAllocation(r0 // d, h0 * d, label, True))
        else:
            r = max(1, round(r0 / d))
            h = round(budget / r)
            out.append(BudgetAllocation(r, h, label, r * h == budget))
    return out
