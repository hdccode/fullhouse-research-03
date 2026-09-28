# Extending FHR3

## A new variant

All seven headline formats are implemented (docs/variants.md). For another
PokerKit community-card game, subclass `PokerKitBoardAdapter` /
`PokerKitBoardHand` in `games/pokerkit_board.py` and register it in `ADAPTERS`.

1. Implement `GameAdapter` + `Hand` in `games/<name>.py` (only this module may import
   PokerKit). The adapter must deal **only** from the `Deal` it is given
   (`deal_from_deck` defines the card layout; bump nothing else).
2. Register it in `games/__init__.py::make_adapter`.
3. Put variant options in `GameConfig.options` (they are hashed).
4. Add adapter tests (legality, conservation fuzz, variant-specific rules) and run
   the shared invariants in `tests/variant_invariants.py`
   (`check_core_invariants`, `check_serial_parallel_parquet`).
5. Add a config under `configs/`, dry-run, smoke-test, then hand the pilot command
   to the researcher.

Multi-hand formats: implement a block protocol in `eval/matched.py` (see
`NitRoundProtocol`) and keep every block's initial state explicit and fresh.

## A new agent

Implement `Agent` (or subclass `DistributionAgent` and implement
`action_distribution`, which is preferred for CRN and later AIVAT), give it an
`IMPL_VERSION`, and register a `kind` in `agents/__init__.py::build_agent`. Run the
legality test pattern in `tests/test_agents.py` over it.

## A new estimator (RQ6)

See docs/estimators.md. Implement `HandEstimator` in `estimators/`, populate its
Parquet column, and add a **mean-preservation** test: on simulated blocks where the true mean is known (or
via large paired samples), E[estimator] must equal E[D]. Any fitted value
function is trained on blocks disjoint from evaluation blocks (use a different
`root_seed`), frozen, and its hash recorded in the manifest. Start from PVAT for
MIVAT/AIVAT and use NoRegrets / RoboPoker / poker-agent-kit as test oracles
rather than runtime dependencies.

## Sequential inference (RQ7)

Implemented in `analysis/sequential.py` (docs/sequential.md). Add methods there;
validate coverage with `fhr3 cs-coverage` before interpreting stopping times.
