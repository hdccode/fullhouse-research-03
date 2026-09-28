# Architecture

```text
src/fhr3/
  rng.py                 keyed BLAKE2b streams, derive_seed, DecisionRNG
  games/base.py          GameConfig, Action, LegalActions, Observation, Deal,
                         HandOutcome, Hand / GameAdapter protocols
  games/pokerkit_board   the only module importing PokerKit: NLHE, PLO, AoF,
                         bomb pot, Crazy Pineapple adapters/hands
  games/nit.py           Nit Game adapter (NLHE + options; state in the protocol)
  games/evaluator.py     fast Hold'em/Omaha evaluator for estimators (not rules)
  games/__init__.py      make_adapter(): variant registry
  agents/base.py         Agent protocol, DistributionAgent, AgentSpec
  agents/heuristic.py    parameterized stochastic policy family (+ STYLES)
  agents/features.py     preflop percentiles, made-hand/draw features
  agents/plo.py, omaha_features.py   PLO heuristic family
  agents/pineapple.py    Crazy Pineapple family (incl. discard)
  agents/nit.py          nit-aware NLHE family
  agents/aof.py, data/   AoF production policy v2 (vendored) + AoF heuristics
  agents/simple.py       CheckCall / RandomLegal (tests, fuzzing)
  configs/experiment.py  ExperimentConfig, Pairing, RNGConfig, TracePolicy, hashes
  eval/matched.py        MatchedBlockSpec, block protocols (single hand, nit round),
                         run_matched_block, estimator hook
  eval/runner.py         work planning, sharding, resume, process pool
  estimators/allin_ev.py all-in EV estimator
  estimators/vat.py      MIVAT/AIVAT via PVAT; vat_fit.py frozen value functions
  io/schema.py           Parquet schema (one row per block)
  io/store.py            layout, compatibility locks, atomic chunk writes, reads
  io/manifest.py         RunManifest (provenance)
  io/traces.py           deterministic sparse PHH tracing
  analysis/stats.py      describe, power, bootstrap, location-shift power
  analysis/report.py     corpus report, ECDF export
  analysis/compare.py    cross-format/-stack comparison with strict relation labels
  analysis/figures.py    figure-ready CSV products
  analysis/sequential.py RQ7 confidence sequences, coverage experiments
  validation/corpus.py   output validation + exact replay
  cli/main.py            `fhr3` entry point
```

Dependency direction: `games` ← `agents` ← `configs` ← `eval` ← `io` ← `analysis/validation` ← `cli`.
`analysis` reads Parquet only (the estimator/VAT code lives in `estimators`).

## Key interfaces

```python
class GameAdapter(Protocol):
    config: GameConfig
    def deal_from_deck(self, deck) -> Deal: ...
    def new_hand(self, deal, starting_stacks=None) -> Hand: ...

class Hand(Protocol):
    def is_terminal(self) -> bool; def actor(self) -> int
    def observation(self, seat) -> Observation   # .extra carries public variant state
    def legal_actions(self) -> LegalActions | LegalDiscards
    def apply(self, action) -> None          # raises IllegalActionError, never coerces
    def outcome(self) -> HandOutcome         # incl. allin_snapshot for all-in EV
    def to_trace(self, players, extra) -> str  # PHH or FHR3 JSON

class Agent(Protocol):
    agent_id: str; version: str
    def act(self, observation, legal_actions, rng: DecisionRNG) -> Action
```

Discards (Crazy Pineapple) are `ActionKind.DISCARD` actions answering a
`LegalDiscards` legal set, so the same `act` signature covers them. Multi-hand
blocks (Nit Game) are a block *protocol*, not an adapter concern.

## Why these choices

* **Adapter owns chance.** PokerKit's deck is overwritten and all cards are dealt
  explicitly from our `Deal`, so replaying one Deal across 2k hands is trivial and
  PokerKit's module-level `random.shuffle` cannot leak in.
* **Keyed randomness, not sequential streams.** Every draw is a pure function of
  its semantic key, which gives exact CRN, order independence, and
  serial ≡ parallel ≡ sharded by construction.
* **Chunked immutable Parquet + locks.** Resume = skip existing chunks; mixing
  results across configs is structurally impossible.
* **Illegal actions are errors.** The adapter never "fixes" an agent's action;
  an illegal action invalidates the block (`error_code = ILLEGAL_ACTION`) and the
  block is traced.
