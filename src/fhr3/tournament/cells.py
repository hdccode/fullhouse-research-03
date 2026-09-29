"""A *cell*: one experimental condition, run as a resumable batch of tournaments.

Kinds
-----
``adaptive``         independent Swiss tournaments (baseline, sweeps, references)
``frozen_replay``    replay j of source tournament s's complete table schedule with
                     fresh poker randomness (research-only counterfactual)
``adaptive_replay``  replay j of source tournament s as a normal adaptive Swiss event
                     starting from the same round-1 tables, with the same fresh
                     randomness as frozen replay j (paired contrast)

For replay kinds, replicate ``r`` means source ``s = r // J`` and replay ``j = r % J``,
``J = replays_per_source`` (part of the identity); adding sources is resumable.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Any

from fhr3.agents import build_agent
from fhr3.tournament.fields import FieldManifest, Mode, field_from_dict, game_from_dict
from fhr3.tournament.match import MATCH_ENGINE_VERSION, PokerMatchPlayer
from fhr3.tournament.manifests import (
    cell_identity,
    identity_hash,
    replay_seeds,
    tournament_seeds,
)
from fhr3.tournament.protocol import TournamentProtocol, protocol_from_dict
from fhr3.tournament.runner import TournamentSpec

KINDS = ("adaptive", "frozen_replay", "adaptive_replay")
MAX_TABLE_SIZE = 10  # FHR3 GameConfig limit (the 2026 engine allowed 9)


@dataclass(frozen=True)
class Cell:
    kind: str
    mode: Mode
    protocol: TournamentProtocol
    field: FieldManifest
    seed_family: str
    namespace: str
    source: Cell | None = None
    replays_per_source: int = 0
    synthetic: dict[str, Any] | None = None  # tests only: SyntheticMatchPlayer params

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"cell kind must be one of {KINDS}")
        if self.kind != "adaptive":
            if self.source is None or self.source.kind != "adaptive" or self.replays_per_source < 1:
                raise ValueError("replay cells need an adaptive source cell and replays_per_source >= 1")
            if self.source.protocol != self.protocol or self.source.field.field_hash != self.field.field_hash:
                raise ValueError("replay cells use the source's protocol and field")
        self.protocol.check_variant(self.mode.game.variant)
        if self.protocol.table_size != self.mode.table_size and self.protocol.status == "research":
            raise ValueError("research protocols use the mode's natural table size")

    @cached_property
    def identity(self) -> dict[str, Any]:
        extra: dict[str, Any] = {"match_engine_version": MATCH_ENGINE_VERSION}
        if self.source is not None:
            extra |= {"source_cell": self.source.identity_hash, "replays_per_source": self.replays_per_source}
        if self.synthetic is not None:
            extra["synthetic"] = self.synthetic
        return cell_identity(kind=self.kind, mode=self.mode.to_dict(), protocol=self.protocol.to_dict(),
                             field_hash=self.field.field_hash, seed_family=self.seed_family,
                             namespace=self.namespace, extra=extra)

    @cached_property
    def identity_hash(self) -> str:
        return identity_hash(self.identity)

    @property
    def cell_id(self) -> str:
        p = self.protocol
        kind = {"adaptive": "swiss", "frozen_replay": "frozen", "adaptive_replay": "adaptrep"}[self.kind]
        return (f"{self.mode.mode}.{self.field.field_id}.{p.name}.R{p.rounds}H{p.hands_per_match}K{p.qualify_top_k}"
                f".{kind}.{self.namespace}.{self.identity_hash[:8]}")

    def source_index(self, replicate: int) -> tuple[int, int]:
        return divmod(replicate, self.replays_per_source)

    def tournament_spec(self, replicate: int, frozen_schedule: Any = None) -> TournamentSpec:
        if self.kind == "adaptive":
            seeds = tournament_seeds(self.seed_family, self.namespace, replicate)
        else:
            assert self.source is not None
            s, j = self.source_index(replicate)
            src = tournament_seeds(self.source.seed_family, self.source.namespace, s)
            seeds = replay_seeds(self.seed_family, self.namespace, s, j, src)
        if self.kind == "frozen_replay" and frozen_schedule is None:
            raise ValueError("frozen replays need the source tournament's schedule")
        frozen = None
        if self.kind == "frozen_replay":
            frozen = tuple(tuple(tuple(t) for t in r) for r in frozen_schedule)
        return TournamentSpec(
            tournament_id=f"{self.cell_id}/t{replicate:06d}", cell_id=self.cell_id, replicate=replicate,
            protocol=self.protocol, bot_ids=tuple(sorted(self.field.bot_ids)), seeds=seeds,
            max_table_size=MAX_TABLE_SIZE, frozen_schedule=frozen,
        )

    def make_player(self) -> Any:
        if self.synthetic is not None:
            from fhr3.tournament.match import SyntheticMatchPlayer

            return SyntheticMatchPlayer(self.synthetic["strength"], self.synthetic.get("noise_sd", 100.0),
                                        self.synthetic.get("edge"))
        agents = {b: build_agent(spec) for b, spec in self.field.specs().items()}
        return PokerMatchPlayer(self.mode.game, self.protocol.stack_policy, agents)

    # ------------------------------------------------------------ (de)serialisation for workers/locks
    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "mode": self.mode.to_dict() | {"primary": self.mode.primary},
            "protocol": self.protocol.to_dict() | {"notes": list(self.protocol.notes)},
            "field": self.field.to_dict(),
            "seed_family": self.seed_family,
            "namespace": self.namespace,
            "source": self.source.to_dict() if self.source else None,
            "replays_per_source": self.replays_per_source,
            "synthetic": self.synthetic,
        }


def cell_from_dict(d: dict[str, Any]) -> Cell:
    m = d["mode"]
    mode = Mode(m["mode"], game_from_dict(m["game"]), int(m["table_size"]), m["stack_policy"],
                m["agent_family"], bool(m.get("primary", False)))
    return Cell(
        kind=d["kind"], mode=mode, protocol=protocol_from_dict(d["protocol"]), field=field_from_dict(d["field"]),
        seed_family=d["seed_family"], namespace=d["namespace"],
        source=cell_from_dict(d["source"]) if d.get("source") else None,
        replays_per_source=int(d.get("replays_per_source", 0)), synthetic=d.get("synthetic"),
    )
