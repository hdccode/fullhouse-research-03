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

## Provenance and freezing (RQ6)

* `ExperimentConfig.estimator_provenance` expands `estimators:` into settings, method
  version (`allin-ev-1`, `fhr3-vat-pvat-1` + `vat-features-1`), PVAT version and the RNG
  stream derivation. `estimator_config_hash` (on every block) hashes this record, and the
  experiment lock stores it, so a silent change of estimator code, library version, MC
  sample counts or value-function artifact under the same experiment_id is refused.
  Raw-only configs keep their historical lock and config hash.
* Estimator randomness is isolated: all-in EV uses `KeyedStream('allin-ev', version, salt,
  hand_key)` and VAT flop sampling uses `KeyedStream('vat', salt, hand_key)`. Dealing and
  agent policies use different streams, so estimator settings never change cards,
  actions or raw D (tested).
* `vat-fit` writes a byte-deterministic artifact. It contains features, θ, training root
  seed and blocks, training/evaluation config hashes, method and PVAT versions, and git SHA.
  The wall-clock timestamp goes to an unpinned `*.created.json` sidecar. The derived
  evaluation config pins the artifact's sha256.
* Refusals: a training seed equal to the evaluation seed (at fit and at load), and an
  artifact whose bytes differ from the pinned sha256. `scripts/verify_value_function.py`
  runs these checks before simulating.
* Training and evaluation are separated by root seed, not block id. Training blocks
  0..999 under seed 90210 are different deals from evaluation blocks under 20260928.
* Unbiasedness vs variance reduction: every estimator has E[estimator − raw] = 0 for ANY
  value function (exactly verified on the toy game; statistically on poker blocks).
  Value-function quality only changes variance. A poorly fitted value function can
  *increase* variance and still be unbiased, so the RQ6 analysis reports variance ratios
  with CIs and flags ratio > 1.

## RQ6 correctness gates (tests/test_rq6.py, test_allin_ev.py, test_vat.py)

* all-in EV equals the PokerKit-played average over every runout for:
  * turn all-in with side pots;
  * flop all-in, multiway, with nested side pots and an uncalled bet;
  * folded dead money with an odd pot and chops (odd-chip rule).

  A river all-in has no runout, and the estimate equals the realized payoff.
* The toy oracle checks PVAT MIVAT/AIVAT against an independent implementation, covering:
  * exact unbiasedness;
  * exact-value-function variance collapse;
  * a poor value function that stays unbiased;
  * zero correction at deterministic actions.
* Self-play is exactly 0 and A/B swap negates every estimator. RQ6 configs reproduce the
  reference configs' raw D.
* `scripts/analyze_rq6.py` blocks publication on any of:
  * raw D ≠ frozen reference;
  * `raw_estimator_D` ≠ D;
  * nonzero self-play;
  * |z(mean(estimator − raw))| > 3.
