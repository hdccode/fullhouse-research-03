"""Seed namespaces, source hashes and experiment (cell) identity.

Identity rule
-------------
A *cell* is one experimental condition: mode (game), field, protocol (incl. R, H, K,
stack rule, pairing), schedule kind, seed family and seed namespace. Its identity
hash covers all of these plus the engine version constants. Changing any of them
creates a new cell. The number of tournament replications is *not* part of the
identity: extending a cell from 200 to 1000 tournaments reuses the same cell and
skips completed tournaments.

Seeds deliberately do not depend on R, H or K. Cells in one seed family and
namespace therefore share tournament seeds (common random numbers): replicate i of
the R=10 cell is exactly the first 10 rounds of replicate i of the R=40 cell, and
round-1 hands are shared across match lengths (see docs/fhr3b/ARCHITECTURE.md).

Namespaces (disjoint by construction, every draw is keyed by its namespace):

    agent-construction   pool perturbations (fields.py)
    pool-calibration     balanced EV of candidate pools (field construction)
    field-reference      balanced field EV mu_field inside a frozen field
    swiss-reference      expected Swiss performance mu_swiss
    publication          finite-budget reliability tournaments (A/B/C/D)
    pilot, smoke         runtime / correctness only
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fhr3.configs.experiment import canonical_hash
from fhr3.rng import SEED_DERIVATION_VERSION, derive_seed

NAMESPACES = ("agent-construction", "pool-calibration", "field-reference", "swiss-reference",
              "publication", "pilot", "smoke", "test")
TOURNAMENT_ENGINE_VERSION = "fhr3b-tournament-v1"
ANALYSIS_VERSION = "fhr3b-analysis-v1"
SRC = Path(__file__).resolve().parents[1]  # src/fhr3
# Everything that can change a tournament's rows. Analysis/CLI modules are excluded
# on purpose (they cannot change results) and are versioned by ANALYSIS_VERSION.
RESULT_SOURCES = (
    "rng.py", "eval/matched.py", "games/*.py", "agents/*.py", "agents/data/*.json",
    "tournament/swiss.py", "tournament/protocol.py", "tournament/match.py",
    "tournament/runner.py", "tournament/schedule.py", "tournament/fields.py",
    "tournament/calibration.py", "tournament/manifests.py", "tournament/cells.py", "tournament/agents.py",
)


def engine_source_hash() -> str:
    h = hashlib.sha256()
    files = sorted({p for pat in RESULT_SOURCES for p in SRC.glob(pat)})
    for f in files:
        h.update(str(f.relative_to(SRC)).encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()[:16]


def check_namespace(ns: str) -> str:
    if ns not in NAMESPACES:
        raise ValueError(f"unknown seed namespace {ns!r}; have {NAMESPACES}")
    return ns


@dataclass(frozen=True)
class TournamentSeeds:
    tournament_seed: int
    order_seed: int  # round-1 order
    chance_seed: int  # cards
    decision_seed: int  # agent mixing

    def to_dict(self) -> dict[str, int]:
        return {"tournament_seed": self.tournament_seed, "order_seed": self.order_seed,
                "chance_seed": self.chance_seed, "decision_seed": self.decision_seed}


def tournament_seeds(seed_family: str, namespace: str, replicate: int) -> TournamentSeeds:
    t = derive_seed("fhr3b-tournament", seed_family, check_namespace(namespace), replicate)
    return TournamentSeeds(t, derive_seed("fhr3b-order", t), derive_seed("fhr3b-chance-root", t),
                           derive_seed("fhr3b-decision-root", t))


def replay_seeds(seed_family: str, namespace: str, source_replicate: int, replay: int,
                 source: TournamentSeeds) -> TournamentSeeds:
    """Fresh poker randomness for replay ``replay`` of source tournament ``source_replicate``.

    The round-1 order is the source's (so an adaptive replay starts from the same
    round-1 tables as the frozen schedule); cards and decisions are new and shared
    between the frozen and adaptive replay with the same index (CRN).
    """
    r = derive_seed("fhr3b-replay", seed_family, check_namespace(namespace), source_replicate, replay)
    return TournamentSeeds(r, source.order_seed, derive_seed("fhr3b-chance-root", r),
                           derive_seed("fhr3b-decision-root", r))


def cell_identity(*, kind: str, mode: dict[str, Any], protocol: dict[str, Any], field_hash: str,
                  seed_family: str, namespace: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "tournament_engine_version": TOURNAMENT_ENGINE_VERSION,
        "seed_derivation_version": SEED_DERIVATION_VERSION,
        "kind": kind,
        "mode": mode,
        "protocol": protocol,
        "field_hash": field_hash,
        "seed_family": seed_family,
        "namespace": check_namespace(namespace),
        "extra": extra or {},
    }


def identity_hash(identity: dict[str, Any]) -> str:
    return canonical_hash(identity)[:16]
