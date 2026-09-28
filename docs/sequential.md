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
