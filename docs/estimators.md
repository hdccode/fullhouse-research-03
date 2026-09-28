# Estimators (RQ6)

Every estimator targets the same estimand: E[D] for the matched block (see
`matched_blocks.md`). Estimators change variance, never the expectation.
Columns: `raw_estimator_D` (= D), `allin_ev_D`, `mivat_D`, `aivat_D`; null when
an estimator is not enabled. Estimator settings live under `estimators:` in the
config; they are excluded from `config_hash` (raw D is unaffected) but included
in `estimator_config_hash` and the experiment lock.

```yaml
estimators:
  allin_ev: {mc_samples: 200, exact_max_combos: 1200}
  mivat: {value_function: prior, flop_samples: 16}
  aivat: {value_function: prior, flop_samples: 16}
```

All estimator randomness uses keyed streams that do **not** include the side
(A/B), so identical A/B hands receive identical estimates (self-play stays exactly
0 and swapping A/B negates every estimator exactly).

## All-in EV (`allin_ev`)
At the first point where no strategic decision remains but board cards are still
to come (at most one live player has chips; in Crazy Pineapple also all discards
made), the candidate's realized payoff is replaced by its expectation over the
remaining runout, drawn uniformly from undealt cards (all hole cards incl. folded
and discarded, board and burned cards excluded). It never re-evaluates the
all-in decision itself. Exact enumeration when the number of runouts ≤
`exact_max_combos`, else `mc_samples` Monte Carlo runouts. Split pots replicate
PokerKit's odd-chip rule exactly.

Tests: exact EV equals the average of PokerKit-played outcomes over every river
(NLHE side pots, PLO, bomb pot, Crazy Pineapple kept cards); MC agrees with exact;
hands without an all-in runout are unchanged; block-level mean preservation.

## MIVAT / AIVAT (`mivat`, `aivat`) — PVAT-backed
Implemented with PVAT (`pvat==0.0.0.dev2`, uoftcprg): each hand is a PVAT
history over chance events (flop sampled i.i.d. `flop_samples` times; turn and
river enumerated exactly) and agent decisions (policies known for every
`DistributionAgent`). MIVAT corrects chance only; AIVAT corrects chance and all
known-policy actions (full information in simulation, so mapped histories are
the history itself). For any fixed value function the corrections have zero
conditional mean.

Value function: linear in candidate-centric features (`FEATURES` in
`estimators/vat.py`): chips contributed, pot × current-lead indicator per street,
pot / live players, pot when alone. `value_function: prior` uses the documented
`PRIOR_THETA`; otherwise a JSON from `fhr3 vat-fit`, pinned by sha256.

Freezing and separation:
* `fhr3 vat-fit` simulates **training** blocks under `--training-root-seed`, which
  must differ from the evaluation `root_seed` (enforced), and fits θ with PVAT's
  `LinearValueFunction.learn` (variance-minimising least squares).
* The evaluation config references the file and its sha256; a mismatch, or a file
  trained on the evaluation root seed, is refused.
* The PVAT package's own tests are empty stubs; FHR3's tests
  (`tests/test_vat.py`) check zero-θ identity, the chance outcome sets, policy
  support, exact zero-mean river corrections, statistical mean preservation for
  the prior and a random θ, self-play zero, swap negation and pinning refusals.

PVAT interface notes: PVAT returns the integer 0 (not a vector) when a history
has no corrected prefix; FHR3 computes θ · (feature-space correction sum)
explicitly, which is identical to PVAT's linear path otherwise.

Early observation (60-block smoke, not evidence): the prior θ increased AIVAT
variance for one pairing; a value function fitted on separate data is required
before AIVAT results are interpreted.

## Adding an estimator
Implement `HandEstimator` (`name`, `needs_decision_log`, `estimate(ctx)` returning
the candidate's estimated payoff in chips), register it in
`estimators/__init__.py`, add a Parquet column (schema bump) and a
mean-preservation test before populating it.
