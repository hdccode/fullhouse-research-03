"""Experiment configuration (YAML) and its stable hashes.

Two hashes are persisted with every result row:

* ``config_hash``  – the *environment*: experiment id, root seed, game config,
  RNG coupling/salts, seed-derivation version. Changing any of these changes
  every block.
* ``pairing_hash`` – one pairing: candidate A/B specs, the reference population
  specs, and the resolved agent implementation versions.

Operational settings (block count, chunk size, trace policy, workers, output
paths) are deliberately *not* hashed: they cannot change any block's result.

Estimator settings (``estimators:``) are hashed separately into
``estimator_config_hash``: they never change the raw D, only the
variance-reduced columns, and they are part of the experiment lock.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from fhr3.agents import AgentSpec, build_agent
from fhr3.games.base import GameConfig
from fhr3.rng import SEED_DERIVATION_VERSION

Coupling = Literal["shared", "independent"]


def canonical_hash(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


@dataclass(frozen=True)
class RNGConfig:
    """Random-stream coupling between the A-hand and B-hand of each seat.

    candidate_coupling:
      shared      – A and B read the same uniforms at their n-th decision in the
                    matched hand (common random numbers). Marginals unchanged.
      independent – separate streams for the A slot and the B slot.
    reference_coupling:
      shared      – each reference seat reads the same uniforms in the A-hand
                    and the B-hand (keyed by seat and decision ordinal).
      independent – separate reference streams per slot.
    salts: integer perturbation per stream (``chance``, ``candidate``,
      ``reference``); changing one salt re-randomizes only that source.
    """

    candidate_coupling: Coupling = "shared"
    reference_coupling: Coupling = "shared"
    salts: Mapping[str, int] = field(
        default_factory=lambda: {"chance": 0, "candidate": 0, "reference": 0}
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_coupling": self.candidate_coupling,
            "reference_coupling": self.reference_coupling,
            "salts": dict(self.salts),
        }


@dataclass(frozen=True)
class TracePolicy:
    rate: float = 0.001
    include_invalid: bool = True
    block_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class Pairing:
    pairing_id: str
    candidate_a: AgentSpec
    candidate_b: AgentSpec
    reference_population: str
    reference_seats: tuple[AgentSpec, ...]

    def resolved(self) -> dict[str, Any]:
        """Specs plus implementation versions (what the pairing hash covers)."""

        def one(spec: AgentSpec) -> dict[str, Any]:
            return spec.to_dict() | {"version": build_agent(spec).version}

        return {
            "pairing_id": self.pairing_id,
            "candidate_a": one(self.candidate_a),
            "candidate_b": one(self.candidate_b),
            "reference_population": self.reference_population,
            "reference_seats": [one(s) for s in self.reference_seats],
        }

    @property
    def pairing_hash(self) -> str:
        return canonical_hash(self.resolved())[:16]

    @property
    def reference_version(self) -> str:
        return canonical_hash(self.resolved()["reference_seats"])[:10]


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_id: str
    root_seed: int
    game: GameConfig
    rng: RNGConfig
    pairings: tuple[Pairing, ...]
    blocks: int = 1000
    chunk_size: int = 250
    trace: TracePolicy = TracePolicy()
    estimators: Mapping[str, Any] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(default_factory=dict)

    @property
    def estimator_provenance(self) -> dict[str, Any] | None:
        """Settings + method/library versions + RNG derivation of every enabled estimator."""
        if not self.estimators:
            return None
        from fhr3.estimators.provenance import estimator_provenance

        return estimator_provenance(self.estimators)

    @property
    def estimator_config_hash(self) -> str | None:
        prov = self.estimator_provenance
        return canonical_hash(prov)[:16] if prov else None

    def environment(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "root_seed": self.root_seed,
            "game": self.game.to_dict(),
            "rng": self.rng.to_dict(),
            "seed_derivation_version": SEED_DERIVATION_VERSION,
        }

    @property
    def config_hash(self) -> str:
        return canonical_hash(self.environment())[:16]

    def pairing(self, pairing_id: str) -> Pairing:
        for p in self.pairings:
            if p.pairing_id == pairing_id:
                return p
        raise KeyError(f"no pairing {pairing_id!r}; have {[p.pairing_id for p in self.pairings]}")


def _agent_spec(agent_id: str, d: Mapping[str, Any]) -> AgentSpec:
    d = dict(d)
    kind = d.pop("kind")
    return AgentSpec(agent_id=agent_id, kind=kind, params=d)


def config_from_dict(raw: Mapping[str, Any]) -> ExperimentConfig:
    g = dict(raw["game"])
    game = GameConfig(
        variant=g.pop("variant"),
        player_count=int(g.pop("player_count")),
        stack_bb=float(g.pop("stack_bb")),
        bb_chips=int(g.pop("bb_chips", 100)),
        sb_chips=int(g.pop("sb_chips", 50)),
        ante_chips=int(g.pop("ante_chips", 0)),
        options=g.pop("options", {}) or {},
    )
    if g:
        raise ValueError(f"unknown game keys: {sorted(g)}")

    r = dict(raw.get("rng", {}) or {})
    salts = {"chance": 0, "candidate": 0, "reference": 0} | dict(r.get("salts", {}) or {})
    rng = RNGConfig(
        candidate_coupling=r.get("candidate_coupling", "shared"),
        reference_coupling=r.get("reference_coupling", "shared"),
        salts=salts,
    )
    for name in ("candidate_coupling", "reference_coupling"):
        if getattr(rng, name) not in ("shared", "independent"):
            raise ValueError(f"rng.{name} must be 'shared' or 'independent'")

    agents = {aid: _agent_spec(aid, spec) for aid, spec in raw["agents"].items()}
    pops = raw["reference_populations"]
    pairings = []
    for p in raw["pairings"]:
        pop_id = p["reference_population"]
        seats = tuple(agents[a] for a in pops[pop_id])
        if len(seats) != game.player_count - 1:
            raise ValueError(
                f"reference population {pop_id!r} has {len(seats)} seats; "
                f"need player_count-1 = {game.player_count - 1}"
            )
        pairings.append(
            Pairing(
                pairing_id=p["pairing_id"],
                candidate_a=agents[p["candidate_a"]],
                candidate_b=agents[p["candidate_b"]],
                reference_population=pop_id,
                reference_seats=seats,
            )
        )
    ids = [p.pairing_id for p in pairings]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate pairing_id")

    t = raw.get("trace", {}) or {}
    trace = TracePolicy(
        rate=float(t.get("rate", 0.001)),
        include_invalid=bool(t.get("include_invalid", True)),
        block_ids=tuple(int(b) for b in t.get("block_ids", ()) or ()),
    )
    return ExperimentConfig(
        experiment_id=str(raw["experiment_id"]),
        root_seed=int(raw["root_seed"]),
        game=game,
        rng=rng,
        pairings=tuple(pairings),
        blocks=int(raw.get("blocks", 1000)),
        chunk_size=int(raw.get("chunk_size", 250)),
        trace=trace,
        estimators=dict(raw.get("estimators", {}) or {}),
        raw=raw,
    )


def load_config(path: str | Path) -> ExperimentConfig:
    with open(path) as fh:
        return config_from_dict(yaml.safe_load(fh))
