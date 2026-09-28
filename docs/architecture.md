# Architecture

```text
src/fhr3/
  rng.py                 keyed BLAKE2b streams, derive_seed, DecisionRNG
  games/base.py          GameConfig, Action, LegalActions, Observation, Deal,
                         HandOutcome, Hand / GameAdapter protocols
  games/pokerkit_holdem  the only module importing PokerKit (NLHE)
  games/__init__.py      make_adapter(): variant registry
  agents/base.py         Agent protocol, DistributionAgent, AgentSpec
  agents/heuristic.py    parameterized stochastic policy family (+ STYLES)
  agents/features.py     preflop percentiles, made-hand/draw features
  agents/simple.py       CheckCall / RandomLegal (tests, fuzzing)
  configs/experiment.py  ExperimentConfig, Pairing, RNGConfig, TracePolicy, hashes
  eval/matched.py        MatchedBlockSpec, run_matched_block, MatchedBlockResult
  eval/runner.py         work planning, sharding, resume, process pool
  estimators/base.py     Estimator protocol, RawMatchedEstimator
  io/schema.py           Parquet schema (one row per block)
  io/store.py            layout, compatibility locks, atomic chunk writes, reads
  io/manifest.py         RunManifest (provenance)
  io/traces.py           deterministic sparse PHH tracing
  analysis/stats.py      describe, power, bootstrap, location-shift power
  analysis/report.py     corpus report, ECDF export
  analysis/compare.py    cross-config comparison (stack depth, player count)
  validation/corpus.py   output validation + exact replay
  cli/main.py            `fhr3` entry point
```

Dependency direction: `games` ← `agents` ← `configs` ← `eval` ← `io` ← `analysis/validation` ← `cli`.
`analysis` reads Parquet only and imports nothing from `games`/`agents`/`eval`.

## Key interfaces

```python
class GameAdapter(Protocol):
    config: GameConfig
    def deal_from_deck(self, deck) -> Deal: ...
    def new_hand(self, deal, starting_stacks=None) -> Hand: ...

class Hand(Protocol):
    def is_terminal(self) -> bool; def actor(self) -> int
    def observation(self, seat) -> Observation; def legal_actions(self) -> LegalActions
    def apply(self, action) -> None          # raises IllegalActionError, never coerces
    def outcome(self) -> HandOutcome; def to_phh(self, players, extra) -> str

class Agent(Protocol):
    agent_id: str; version: str
    def act(self, observation, legal_actions, rng: DecisionRNG) -> Action
```

Discards (Crazy Pineapple) are reserved as `ActionKind.DISCARD` with
`Action.cards`, so the same `act` signature covers them.

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
