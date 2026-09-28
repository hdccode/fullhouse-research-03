# Agents

## Versioning

`version = "<impl-version>+<params-hash>"`, e.g. `heuristic-1.0.0+29fb750a9a`.
Bump the implementation version (`IMPL_VERSION` in the module) whenever decision
logic changes, and the pairing hash (and therefore the pairing lock) changes too,
which prevents mixing results from different agent code.

Agents must be stateless across hands: `act` is a pure function of
`(observation, legal actions, rng draws)`.

## `heuristic` — `HeuristicAgent` (`heuristic-1.0.0`)

A transparent stochastic policy. Every decision produces an explicit distribution
over at most {fold, check/call, one raise size}; one uniform picks the action
(inverse CDF). Soft thresholds are logistic in the relevant feature, so small
parameter changes cause small behaviour changes.

Preflop (feature: Chen-formula percentile over all 1326 combos, mid-rank):
* unopened: open-raise top `open_pct_by_seats_behind[·] × looseness` (SB:
  `sb_open_pct`) to `open_size_bb` (+1 BB per limper);
* facing 1 raise: 3-bet top `threebet_pct × aggression`, continue with top
  `call_open_pct` (BB: `bb_defend_pct`); 3-bet size `threebet_mult ×` current bet;
* facing 2 raises: 4-bet / call with `fourbet_pct`, `call_3bet_pct`; 3+ raises:
  jam / call with small ranges;
* raises committing ≥ `allin_commit_fraction` of the stack become all-in.

Postflop (features: made-hand class relative to the board, whether the hole cards
improve on the board, pair class (overpair/top/second/weak), kicker, flush/straight
draws, flushy/straighty/paired board):
* heuristic strength vs one random hand, discounted for opponents
  (`s^(1 + multiway_exponent·(n−1))`) plus draw equity (rule of 4/2);
* not facing a bet: value-bet `σ((eq − value_threshold)/T)`, plus semi-bluffs
  with draws and occasional heads-up bluffs; size `bet_fraction × pot`;
* facing a bet: raise `σ((eq − raise_threshold)/T)`, continue if eq exceeds pot
  odds + `call_margin`; raise size `raise_pot_fraction × (pot + call)`.

Styles (`STYLES`): `neutral`, `tight` (looseness 0.75), `loose` (1.35, lighter
calls), `aggressive` (looseness 1.15, aggression 1.4, more bluffs). Any
`StyleParams` field can be overridden per agent in the config (`overrides:`),
which is how small A/B perturbations are made.

Measured at 6-max 100BB among copies of itself: VPIP ≈ 20–30%, PFR ≈ 15–25%,
~30% of hands see a flop.

These agents are baselines for measuring sample complexity. They are not claims
about strong play. Strong or learned agents are validation agents for later.

## Test agents

`checkcall` (deterministic calling station) and `random` (uniform legal action,
extreme raise sizes over-weighted). Used for invariants and fuzzing, not as
experimental candidates.

## Planned

* FullHouse 4-max AoF production policy (`~/aof-ml`, v2) behind the same
  interface, via an adapter that maps `Observation` to its shove/call lookup.
