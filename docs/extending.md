# Extending FHR3

## A new variant

Recommended order after 6-max NLHE: 4-max NLHE → 4-max AoF → 6-max PLO →
6-max Crazy Pineapple → 6-max NLHE Bomb Pot → 6-max Nit Game.

1. Implement `GameAdapter` + `Hand` in `games/<name>.py` (only this module may import
   PokerKit). The adapter must deal **only** from the `Deal` it is given
   (`deal_from_deck` defines the card layout; bump nothing else).
2. Register it in `games/__init__.py::make_adapter`.
3. Put variant options in `GameConfig.options` (they are hashed).
4. Add adapter tests (legality, conservation fuzz, variant-specific rules) and run
   `tests/test_matched.py`'s invariants against the new adapter (parametrize).
5. Add a config under `configs/`, dry-run, smoke-test, then hand the pilot command
   to the researcher.

Variant notes:
* **4-max NLHE**: config only (`player_count: 4`).
* **AoF**: restrict legal actions to fold / all-in in the adapter (a wrapper around
  the NLHE hand), keep PokerKit for pots/showdown.
* **PLO**: `pk.PotLimitOmahaHoldem`; 4 hole cards; test exact-two-card use.
* **Crazy Pineapple**: 3 hole cards, one discard after the flop. Express the discard as
  `ActionKind.DISCARD` through the normal `act`; validate sequencing against an
  independent implementation.
* **Bomb Pot**: a wrapper that posts the forced antes and starts at the flop (no
  preflop betting), not a new engine.
* **Nit Game**: persistent nit/button metadata lives outside the Hold'em engine.
  This is the one variant where hands are *not* exchangeable within a block, so the
  block protocol needs an explicit extension (document it before implementing).

## A new agent

Implement `Agent` (or subclass `DistributionAgent` and implement
`action_distribution`, which is preferred for CRN and later AIVAT), give it an
`IMPL_VERSION`, and register a `kind` in `agents/__init__.py::build_agent`. Run the
legality test pattern in `tests/test_agents.py` over it.

## A new estimator (RQ6)

Implement `Estimator` in `estimators/`, populate its Parquet column, and add a
**mean-preservation** test: on simulated blocks where the true mean is known (or
via large paired samples), E[estimator] must equal E[D]. Any fitted value
function is trained on blocks disjoint from evaluation blocks (use a different
`root_seed`), frozen, and its hash recorded in the manifest. Start from PVAT for
MIVAT/AIVAT and use NoRegrets / RoboPoker / poker-agent-kit as test oracles
rather than runtime dependencies.

## Sequential inference (RQ7)

A separate layer consumes `D_1, D_2, …` from Parquet (ordered by block_id) and
uses `confseq`. The simulator stays unaware of it. Validate coverage on synthetic
streams first (researcher-run).
