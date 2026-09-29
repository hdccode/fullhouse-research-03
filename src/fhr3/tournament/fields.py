"""Modes, candidate agent pools and immutable field manifests.

No agent carries a "skill" label. A pool crosses

* strategic *archetypes* already expressible in each FHR3 agent family (styles plus
  documented ``overrides``), with
* a deterministic *perturbation scale* (0 = the archetype itself; larger scales draw
  bigger multiplicative/additive parameter perturbations), and
* several deterministic *agent seeds* per scale,

and long-run strength is then measured empirically (``calibration.py``). Fields are
selected from the frozen calibration by deterministic rules; the result is written
as an immutable manifest whose hash covers every bot's exact spec and resolved
implementation version.

Seed namespace: perturbations are drawn from
``KeyedStream("fhr3b-agent-construction", seed_family, family, archetype, scale, seed, param)``,
disjoint from calibration and tournament streams.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields as dc_fields
from pathlib import Path
from typing import Any

import yaml

from fhr3.agents import AgentSpec, build_agent
from fhr3.agents.aof import AOF_STYLES, AoFStyle
from fhr3.agents.heuristic import STYLES, StyleParams
from fhr3.agents.plo import PLO_STYLES
from fhr3.configs.experiment import canonical_hash
from fhr3.games.base import GameConfig
from fhr3.rng import KeyedStream

REPO_ROOT = Path(__file__).resolve().parents[3]
FHR3B_CONFIGS = REPO_ROOT / "configs" / "fhr3b"
POOL_VERSION = "fhr3b-pool-v1"
DEFAULT_SEED_FAMILY = "fhr3b-2026"


# ------------------------------------------------------------------ modes
@dataclass(frozen=True)
class Mode:
    mode: str
    game: GameConfig
    table_size: int
    stack_policy: str
    agent_family: str
    primary: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "game": self.game.to_dict(),
            "table_size": self.table_size,
            "stack_policy": self.stack_policy,
            "agent_family": self.agent_family,
        }

    @property
    def game_hash(self) -> str:
        return canonical_hash(self.game.to_dict())[:16]


def game_from_dict(g: Mapping[str, Any]) -> GameConfig:
    g = dict(g)
    return GameConfig(
        variant=g.pop("variant"),
        player_count=int(g.pop("player_count")),
        stack_bb=float(g.pop("stack_bb")),
        bb_chips=int(g.pop("bb_chips", 100)),
        sb_chips=int(g.pop("sb_chips", 50)),
        ante_chips=int(g.pop("ante_chips", 0)),
        options=g.pop("options", {}) or {},
    )


def load_mode(name: str, root: Path = FHR3B_CONFIGS) -> Mode:
    raw = yaml.safe_load((root / "modes" / f"{name}.yaml").read_text())
    return Mode(
        mode=raw["mode"],
        game=game_from_dict(raw["game"]),
        table_size=int(raw["table_size"]),
        stack_policy=str(raw["stack_policy"]),
        agent_family=str(raw["agent_family"]),
        primary=bool(raw.get("primary", False)),
    )


def all_modes(root: Path = FHR3B_CONFIGS) -> list[str]:
    return sorted(p.stem for p in (root / "modes").glob("*.yaml"))


# ------------------------------------------------------------------ archetypes
# (base style, absolute overrides). Styles are the families' own; overrides use
# documented StyleParams / AoFStyle fields. These describe *strategy*, not quality.
HEURISTIC_ARCHETYPES: dict[str, tuple[str, dict[str, float]]] = {
    "neutral": ("neutral", {}),
    "tight": ("tight", {}),
    "loose": ("loose", {}),
    "aggressive": ("aggressive", {}),
    "nit": ("tight", {"looseness": 0.55, "aggression": 0.8, "call_margin": 0.06, "bluff_freq": 0.04}),
    "station": ("loose", {"looseness": 1.3, "aggression": 0.6, "call_margin": -0.08,
                          "bluff_freq": 0.02, "semibluff_freq": 0.2}),
    "maniac": ("aggressive", {"looseness": 1.6, "aggression": 1.9, "bluff_freq": 0.28,
                              "semibluff_freq": 0.8, "bet_fraction": 0.9}),
    "trapper": ("neutral", {"aggression": 0.7, "value_threshold": 0.7, "raise_threshold": 0.92,
                            "bluff_freq": 0.04, "call_margin": -0.02}),
}
AOF_ARCHETYPES: dict[str, tuple[str, dict[str, Any]]] = {
    "neutral": ("aof_heuristic", {"style": "neutral"}),
    "tight": ("aof_heuristic", {"style": "tight"}),
    "loose": ("aof_heuristic", {"style": "loose"}),
    "aggressive": ("aof_heuristic", {"style": "aggressive"}),
    "shover": ("aof_heuristic", {"style": "neutral", "overrides": {"shove_scale": 1.5, "call_scale": 0.8}}),
    "caller": ("aof_heuristic", {"style": "neutral", "overrides": {"shove_scale": 0.8, "call_scale": 1.5}}),
    # production policy v2 (pure at scale 0) and a loose-blended variant
    "policy": ("aof_policy", {"blend_style": "tight", "base_blend": 0.0}),
    "policy_blend_loose": ("aof_policy", {"blend_style": "loose", "base_blend": 0.1}),
}
FAMILY_KIND = {
    "heuristic": "heuristic",
    "plo_heuristic": "plo_heuristic",
    "cp_heuristic": "cp_heuristic",
    "nit_heuristic": "nit_heuristic",
    "aof": None,  # per-archetype
}
# scale index -> (epsilon, number of agent seeds). Index 0 is the archetype itself.
PERTURBATION_SCALES: tuple[tuple[float, int], ...] = ((0.0, 1), (0.10, 3), (0.25, 4), (0.45, 4))

ADDITIVE = {"call_margin": 0.05, "nit_call_shift": 0.03}
BOUNDS: dict[str, tuple[float, float]] = {
    "looseness": (0.3, 2.5), "aggression": (0.2, 3.0), "preflop_temperature": (0.003, 0.1),
    "postflop_temperature": (0.01, 0.2), "open_size_bb": (2.0, 5.0), "threebet_mult": (2.2, 5.0),
    "fourbet_mult": (1.8, 4.0), "bet_fraction": (0.25, 1.5), "raise_pot_fraction": (0.4, 1.5),
    "multiway_exponent": (0.0, 2.0), "allin_commit_fraction": (0.2, 0.9), "call_margin": (-0.2, 0.2),
    "shove_scale": (0.3, 2.5), "call_scale": (0.3, 2.5), "temperature": (0.003, 0.1),
    "nit_looseness": (1.0, 2.0), "nit_call_shift": (0.0, 0.15),
}
FRACTION_BOUNDS = (0.001, 0.95)


def _normal(stream: KeyedStream) -> float:
    u1 = max(stream.random(), 1e-300)
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * stream.random())


def _bounded(name: str, v: float) -> float:
    lo, hi = BOUNDS.get(name, FRACTION_BOUNDS if any(t in name for t in ("pct", "freq", "threshold")) else (-1e9, 1e9))
    return round(min(hi, max(lo, v)), 5)


def _perturb_value(name: str, v: Any, eps: float, key: tuple[Any, ...]) -> Any:
    if isinstance(v, tuple):  # tuple params: shape-preserving (StyleParams) / elementwise (AoF)
        if name == "open_pct_by_seats_behind":
            f = math.exp(eps * _normal(KeyedStream(*key, name)))
            return [_bounded("pct", x * f) for x in v]
        return [_bounded("pct", x * math.exp(eps * _normal(KeyedStream(*key, name, i)))) for i, x in enumerate(v)]
    z = _normal(KeyedStream(*key, name))
    if name in ADDITIVE:
        return _bounded(name, v + eps * ADDITIVE[name] / 0.25 * z)
    return _bounded(name, v * math.exp(eps * z))


def _style_table(family: str) -> dict[str, StyleParams]:
    return PLO_STYLES if family == "plo_heuristic" else STYLES


def _perturbed_overrides(base: Any, overrides: Mapping[str, Any], eps: float, key: tuple[Any, ...],
                         skip: set[str] = frozenset()) -> dict[str, Any]:
    out = dict(overrides)
    if eps <= 0:
        return out
    for f in dc_fields(base):
        if f.name in skip:
            continue
        v = overrides.get(f.name, getattr(base, f.name))
        if isinstance(v, list):
            v = tuple(v)
        out[f.name] = _perturb_value(f.name, v, eps, key)
    return out


@dataclass(frozen=True)
class PoolBot:
    bot_id: str
    spec: AgentSpec
    archetype: str
    scale_index: int
    epsilon: float
    agent_seed: int

    def entry(self) -> dict[str, Any]:
        return {
            "bot_id": self.bot_id,
            "kind": self.spec.kind,
            "params": _jsonable(self.spec.params),
            "version": build_agent(self.spec).version,
            "meta": {"archetype": self.archetype, "scale_index": self.scale_index,
                     "epsilon": self.epsilon, "agent_seed": self.agent_seed},
        }


def _jsonable(x: Any) -> Any:
    return json.loads(json.dumps(x, sort_keys=True, default=list))


def _spec_for(mode: Mode, bot_id: str, archetype: str, eps: float, key: tuple[Any, ...]) -> AgentSpec:
    fam = mode.agent_family
    if fam == "aof":
        kind, params = AOF_ARCHETYPES[archetype]
        params = dict(params)
        if kind == "aof_heuristic":
            base = AOF_STYLES[params["style"]]
            ov = _perturbed_overrides(base, params.get("overrides", {}), eps, key)
            if ov:
                params["overrides"] = ov
            return AgentSpec(bot_id, kind, params)
        # production policy v2 blended with a heuristic: blend grows with the scale
        u = KeyedStream(*key, "blend").random()
        blend = params["base_blend"] + (0.0 if eps <= 0 else eps * (0.75 + 0.5 * u))
        params = {"policy": "production-v2", "blend": _bounded("blend_pct", min(0.9, blend)),
                  "blend_style": params["blend_style"]}
        return AgentSpec(bot_id, kind, params)
    style, ov = HEURISTIC_ARCHETYPES[archetype]
    base = _style_table(fam)[style]
    params: dict[str, Any] = {"style": style}
    overrides = _perturbed_overrides(base, ov, eps, key)
    if fam == "nit_heuristic" and eps > 0:
        params["nit_looseness"] = _perturb_value("nit_looseness", 1.3, eps, key)
        params["nit_call_shift"] = _perturb_value("nit_call_shift", 0.04, eps, key)
    if overrides:
        params["overrides"] = overrides
    return AgentSpec(bot_id, FAMILY_KIND[fam], params)


def generate_pool(mode: Mode, seed_family: str = DEFAULT_SEED_FAMILY) -> list[PoolBot]:
    archetypes = AOF_ARCHETYPES if mode.agent_family == "aof" else HEURISTIC_ARCHETYPES
    out = []
    for arch in archetypes:
        for si, (eps, n_seeds) in enumerate(PERTURBATION_SCALES):
            for seed in range(n_seeds):
                bot_id = f"{mode.mode}-{arch}-e{si}" + (f"-s{seed}" if eps > 0 else "")
                key = ("fhr3b-agent-construction", seed_family, mode.agent_family, arch, si, seed)
                out.append(PoolBot(bot_id, _spec_for(mode, bot_id, arch, eps, key), arch, si, eps, seed))
    versions = [build_agent(b.spec).version for b in out]
    if len(set(versions)) != len(versions):
        raise ValueError("pool contains behaviourally identical bots")
    return out


# ------------------------------------------------------------------ field manifests
@dataclass(frozen=True)
class FieldManifest:
    field_id: str
    mode: str
    kind: str  # pool | smoke | provisional | spread | crowded_cutoff | matchup_sensitive | style_diverse
    bots: tuple[Mapping[str, Any], ...]
    construction: Mapping[str, Any]

    @property
    def bot_ids(self) -> list[str]:
        return [b["bot_id"] for b in self.bots]

    @property
    def n(self) -> int:
        return len(self.bots)

    def specs(self) -> dict[str, AgentSpec]:
        return {b["bot_id"]: AgentSpec(b["bot_id"], b["kind"], b["params"]) for b in self.bots}

    def hashed_content(self) -> dict[str, Any]:
        return {"mode": self.mode, "bots": sorted(
            ({k: b[k] for k in ("bot_id", "kind", "params", "version")} for b in self.bots),
            key=lambda b: b["bot_id"])}

    @property
    def field_hash(self) -> str:
        return canonical_hash(self.hashed_content())[:16]

    def to_dict(self) -> dict[str, Any]:
        return {"field_id": self.field_id, "mode": self.mode, "kind": self.kind,
                "field_hash": self.field_hash, "n": self.n, "construction": dict(self.construction),
                "bots": [dict(b) for b in self.bots]}

    def validate(self) -> None:
        ids = self.bot_ids
        if len(set(ids)) != len(ids):
            raise ValueError(f"field {self.field_id}: duplicate bot ids")
        for b in self.bots:
            v = build_agent(AgentSpec(b["bot_id"], b["kind"], b["params"])).version
            if v != b["version"]:
                raise ValueError(f"field {self.field_id}: {b['bot_id']} version {v} != manifest {b['version']}")


def field_from_dict(d: Mapping[str, Any]) -> FieldManifest:
    fm = FieldManifest(d["field_id"], d["mode"], d["kind"], tuple(d["bots"]), d.get("construction", {}))
    if "field_hash" in d and d["field_hash"] != fm.field_hash:
        raise ValueError(f"field {fm.field_id}: stored hash {d['field_hash']} != recomputed {fm.field_hash}")
    return fm


def load_field(path: str | Path) -> FieldManifest:
    return field_from_dict(json.loads(Path(path).read_text()))


def write_field_immutable(fm: FieldManifest, path: Path) -> Path:
    """Write once; an existing manifest must be identical (fields are frozen)."""
    fm.validate()
    text = json.dumps(fm.to_dict(), indent=1, sort_keys=True) + "\n"
    if path.exists():
        old = load_field(path)
        if old.field_hash != fm.field_hash:
            raise ValueError(f"refusing to overwrite frozen field {path} ({old.field_hash} != {fm.field_hash})")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def pool_manifest(mode: Mode, seed_family: str = DEFAULT_SEED_FAMILY) -> FieldManifest:
    pool = generate_pool(mode, seed_family)
    return FieldManifest(f"{mode.mode}-pool", mode.mode, "pool", tuple(b.entry() for b in pool),
                         {"method": POOL_VERSION, "seed_family": seed_family,
                          "perturbation_scales": [list(s) for s in PERTURBATION_SCALES],
                          "archetypes": list(AOF_ARCHETYPES if mode.agent_family == "aof" else HEURISTIC_ARCHETYPES)})


def subset(pool: FieldManifest, field_id: str, kind: str, bot_ids: Sequence[str],
           construction: Mapping[str, Any]) -> FieldManifest:
    by_id = {b["bot_id"]: b for b in pool.bots}
    missing = [b for b in bot_ids if b not in by_id]
    if missing:
        raise KeyError(f"not in pool: {missing}")
    return FieldManifest(field_id, pool.mode, kind, tuple(by_id[b] for b in sorted(bot_ids)),
                         {"pool_hash": pool.field_hash} | dict(construction))


def stratified_sample(pool: FieldManifest, n: int, key: str) -> list[str]:
    """Round-robin over archetypes, each archetype in a keyed shuffled order (pre-calibration fields)."""
    by_arch: dict[str, list[str]] = {}
    for b in pool.bots:
        by_arch.setdefault(b["meta"]["archetype"], []).append(b["bot_id"])
    queues = {a: KeyedStream("fhr3b-field-sample", key, a).shuffle(sorted(ids)) for a, ids in sorted(by_arch.items())}
    out: list[str] = []
    while len(out) < n:
        progressed = False
        for a in sorted(queues):
            if queues[a] and len(out) < n:
                out.append(queues[a].pop(0))
                progressed = True
        if not progressed:
            raise ValueError(f"pool has fewer than {n} bots")
    return out


def smoke_field(pool: FieldManifest, n: int = 12) -> FieldManifest:
    ids = stratified_sample(pool, n, f"{pool.mode}-smoke{n}")
    return subset(pool, f"{pool.mode}-smoke{n}", "smoke", ids, {"method": "stratified_sample", "n": n,
                                                              "purpose": "correctness only"})


def provisional_field(pool: FieldManifest, n: int = 60) -> FieldManifest:
    ids = stratified_sample(pool, n, f"{pool.mode}-provisional{n}")
    return subset(pool, f"{pool.mode}-provisional{n}", "provisional", ids,
                  {"method": "stratified_sample", "n": n,
                   "purpose": "runtime pilot before calibration; not a publication field"})


# ------------------------------------------------------------------ selection from calibration
def select_spread(ranked_ids: Sequence[str], n: int) -> list[str]:
    """Evenly spaced positions along the calibrated ranking (strongest first)."""
    p = len(ranked_ids)
    if p < n:
        raise ValueError("pool smaller than field")
    idx = sorted({round(k * (p - 1) / (n - 1)) for k in range(n)})
    if len(idx) != n:
        raise ValueError("spread selection produced duplicates")
    return [ranked_ids[i] for i in idx]


def select_crowded(ranked_ids: Sequence[str], mu: Mapping[str, float], n: int, k_cut: int,
                   n_top: int = 3, crowd: int = 12) -> tuple[list[str], dict[str, Any]]:
    """``n_top`` strongest bots, then the tightest window of ``crowd`` consecutive bots
    (smallest mu range) below them, then evenly spaced fill from below the window.

    The crowd occupies field ranks n_top+1 .. n_top+crowd, straddling the top-K cut
    (requires n_top < k_cut < n_top + crowd).
    """
    if not n_top < k_cut < n_top + crowd:
        raise ValueError("crowd must straddle the cutoff")
    top = list(ranked_ids[:n_top])
    rest = list(ranked_ids[n_top:])
    need_below = n - n_top - crowd
    best = None
    for s in range(0, len(rest) - crowd - need_below + 1):
        window = rest[s : s + crowd]
        width = mu[window[0]] - mu[window[-1]]
        if best is None or width < best[0] - 1e-12:
            best = (width, s)
    if best is None:
        raise ValueError("pool too small for crowded selection")
    width, s = best
    window = rest[s : s + crowd]
    below = rest[s + crowd :]
    fill = select_spread(below, need_below) if need_below > 1 else below[:need_below]
    info = {"n_top": n_top, "crowd": crowd, "window_start_rank": n_top + s + 1,
            "crowd_mu_width": width, "top_ids": top, "crowd_ids": window}
    return top + window + fill, info
