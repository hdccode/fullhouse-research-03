# Sequential inference (RQ7)

Downstream of block results only (`analysis/sequential.py`); the simulator is
unaware of it. The stream is D in `block_id` order.

| method | what it is | valid under optional stopping |
|---|---|---|
| `asymp` | asymptotic confidence sequence, Waudby-Smith, Arbour, Sinha, Kennedy & Ramdas, *Time-uniform central limit theory and asymptotic confidence sequences*, Annals of Statistics (2024); two-sided normal mixture with plug-in variance, tuned at `t*` | yes (asymptotically, finite variance) |
| `fixed` | Student-t interval at one pre-registered n | no (single look only) |
| `peek` | the fixed-N interval recomputed at every look — **invalid comparator** | no |

Half-width at time t with running SD σ̂_t:

    σ̂_t · sqrt( 2 (t ρ² + 1) / (t² ρ²) · log( sqrt(t ρ² + 1) / α ) ),
    ρ² = ( −2 log α + log(−2 log α + 1) ) / t*

Stopping rule (`fhr3 sequential`): after `--min-n` blocks, stop when the interval
excludes 0 (decision A>B or B>A) or, optionally, when its width falls below
`--width-bb100`; otherwise run to the end of the data. Reports stopping time
(blocks and played hands), reason, decision, interval (BB/block and BB/100),
method and version (`fhr3-asympcs-v1`).

Dependency status: `confseq==0.0.11` is pinned as the optional `sequential`
extra. It has no wheels for Python ≥ 3.11 and its build needs Boost (and CMake),
so it is not a hard dependency. The boundary above is the closed-form normal
mixture; `tests/test_sequential.py` cross-checks it against
`confseq.boundaries.normal_mixture_bound` when confseq is installed (the exact
confseq call signature in that test has not been exercised on this machine).
To enable: `brew install boost cmake && uv pip install -e ".[sequential]"`.

Validation: synthetic coverage (`fhr3 cs-coverage`) on normal, t3 (heavy tailed)
and bootstrap-from-corpus streams. Report time-uniform miscoverage (misses the
true mean at any n ≥ min_n), final-n miscoverage, stopping-time quantiles,
decisions and wrong-sign rate. Tests use small runs; large coverage studies are
user-run (see workflow.md).

## RQ7 experiment engine (`fhr3.analysis.rq7`, `fhr3 rq7-cell`)

Three procedures, kept distinct and evaluated on the **same stream** in every replicate:

| method | definition | claim |
|---|---|---|
| `fixed` | Student-t interval at ONE pre-committed n (`--fixed-n`) | nominal at that single look |
| `peek` | the same t-interval recomputed after every block from `min_n`; stop at first exclusion of 0 | none (the invalid comparator) |
| `asymp` | the asymptotic CS above | time-uniform coverage *asymptotically* under finite variance; **not** a finite-sample guarantee |

* **Samplers** draw whole matched blocks: `normal`, `t3` (unit SD, infinite kurtosis),
  `bootstrap:<pairing dir>` (IID resampling of one frozen pairing's centred residuals;
  pooled experiment directories are refused), and `permutation:<pairing dir>` (a random
  ordering of the corpus; true mean = corpus mean). A location shift (`--true-mean` or
  `--effect-d`, i.e. d·σ) moves the residuals without changing their distribution.
* **Seeds:** replicate r uses `SeedSequence(seed, spawn_key=(r,))`. Results do not depend
  on workers, chunking or order. One seed across cells makes min-N and method
  comparisons paired.
* **Per replicate and method:**
  * `ever_miss_true_mean` (any n in [min_n, n_max]; for `fixed`, its single look) and
    `final_miss_true_mean`;
  * `first_miss_time`, `decision_time` (first exclusion of 0) and `decision_sign`;
  * `first_correct_sign_time`, `wrong_decision` (under the null, any decision) and `censored`;
  * interval widths at checkpoints.
* **Summaries** give miscoverage with a Wilson 95% CI and MC SE, decision/censoring/wrong
  rates, and decision-time quantiles. `scripts/analyze_rq7.py` builds the canonical
  tables; `scripts/freeze_rq_manifest.py rq7` pins them.
* **External oracle:** the boundary equals confseq's `normal_mixture_bound` to machine
  precision (committed fixture, `tests/test_rq7.py`; see `docs/external_references.md`).
