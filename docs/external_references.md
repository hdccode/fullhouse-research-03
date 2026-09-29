# External references (RQ6 / RQ7)

Inspected 2026-09-29 (shallow clones, read-only). Nothing below is vendored into
`src/`; FHR3 depends at runtime only on the pinned PyPI packages `pvat` and `pokerkit`.

| repository | commit | license | role in FHR3 |
|---|---|---|---|
| [uoftcprg/pvat](https://github.com/uoftcprg/pvat) | `500800be5b82f1980a296feeb0ae6994aabedff2` | MIT | runtime dependency (`pvat==0.0.0.dev2`) |
| [conorarmstrong/noregrets](https://github.com/conorarmstrong/noregrets) | `757f7692738069522195d2b486eec60a8b010c0c` | MIT | design and test reference |
| [JakubPetriska/poker-agent-kit](https://github.com/JakubPetriska/poker-agent-kit) | `12c28711c91447c708719454d1fbd224fa03189e` | MIT | conceptual reference |
| [gostevehoward/confseq](https://github.com/gostevehoward/confseq) | `5ffe733ca2447a2e28c2c91f3b00086173f2ab2c` (PyPI wheel 0.0.9 used) | MIT | external oracle, offline |
| [jakorostami/expectation](https://github.com/jakorostami/expectation) | `cc580f7f2753fb8e9069260122519cb9dbb05e4d` | **GPL-3.0** | organization only; no code used |
| [uoftcprg/pokerkit](https://github.com/uoftcprg/pokerkit) | pinned `pokerkit==0.7.5` | MIT | game engine (unchanged) |

## PVAT

`pvat/estimators.py` in the installed 0.0.0.dev2 is byte-identical to upstream HEAD.
`utilities.py` differs only by one added docstring. FHR3 calls PVAT's own `MIVAT` and
`AIVAT` classes; its `base term + sum of zero-mean corrections` decomposition is used
as-is.

The FHR3 layer (`src/fhr3/estimators/vat.py`) is a history adapter only:
* it turns a finished PokerKit hand into PVAT histories (`HandTrace`, `H`);
* it supplies chance outcome sets and known agent policies;
* it evaluates θ·(correction sum in feature space). This is needed because PVAT
  returns the integer 0 for histories without corrections, which its linear path rejects.

The audit found no duplicated estimator logic worth removing.

PVAT's upstream tests are empty stubs (`def test_call(self): pass`). PVAT is therefore
treated as an implementation, not an oracle. `tests/test_rq6.py` checks PVAT MIVAT/AIVAT
against an independent hand-written implementation of the AIVAT formula on an
enumerable Kuhn-style game. The checks cover:
* exact equality per terminal;
* exact unbiasedness with exact, poor and zero value functions;
* zero variance with the exact value function under AIVAT;
* zero correction at deterministic actions;
* the linear-θ path.

## NoRegrets (`src/aivat.rs`)

Rust AIVAT with the same decomposition: realized payoff plus one correction per
known-distribution event. Its corrections cover the hero's hole deal, each board reveal,
and known-policy decisions. Chance alternatives come from deterministic replay with a
separate RNG, and the value function is exact on the river.

Adopted as invariants and tests, not code:
* estimator mean equals raw mean;
* value-function quality affects variance, never bias;
* deterministic actions contribute exactly zero;
* estimator randomness uses its own stream. FHR3 uses keyed streams `"allin-ev"` and
  `"vat"`, independent of dealing and policy streams; see
  `test_estimator_settings_do_not_change_cards_actions_or_raw_d`.

Not adopted: the hero hole-card correction. In FHR3's matched blocks the A and B hands
share the deal, and the pre-decision state is identical on both sides. A hole-card
correction would therefore be identical on both sides and cancel exactly in D.

## poker-agent-kit (`utility_estimation/aivat.py`)

A two-player ACPC implementation: imaginary observations, an equilibrium-strategy exact
value function obtained by full tree traversal, and Kuhn/Leduc-sized games. It needs the
kit's ACPC game-tree tooling and strategy files, so it is not run as an oracle.

What transferred is the pattern: on a small enumerable game the exact value function
makes AIVAT variance vanish. FHR3's toy-game tests implement that directly.

## confseq

The FHR3 asymptotic confidence sequence (`fhr3.analysis.sequential.asymp_radius`) uses
the two-sided normal-mixture boundary of Waudby-Smith et al. with a plug-in variance.

confseq's `normal_mixture_bound(v, alpha, v_opt, alpha_opt, is_one_sided=False)` is the
same boundary for a known variance process V_t:
* confseq's guarantee is finite-sample for sub-Gaussian increments;
* ours is asymptotic, with plug-in σ̂_t, for finite-variance increments.

The oracle therefore checks the *boundary formula*, not coverage.

Installation: confseq has no wheels for Python ≥ 3.11, and its source build needs
Boost + CMake plus an old pybind11. A prebuilt `confseq==0.0.9` cp310 universal2 wheel
installs cleanly in an isolated venv:

```bash
uv venv --python 3.10 /tmp/cs310
VIRTUAL_ENV=/tmp/cs310 uv pip install "confseq==0.0.9" "numpy<2"
/tmp/cs310/bin/python scripts/external/confseq_reference.py > tests/data/confseq_normal_mixture_reference.json
```

The generated fixture covers 28 cases (α ∈ {0.05, 0.01}, t* ∈ {1k, 100k},
v ∈ 50…1M). It is committed, and `tests/test_rq7.py` checks our boundary against it
(maximum relative error 2e-16), so the main suite needs no confseq install. The older
in-environment cross-check (`tests/test_sequential.py`) stays optional and skipped.
confseq is not a dependency of RQ7.

## expectation (GPL-3.0)

Its organization was inspected for ideas only: a sampler/method separation, and many
replicates run in parallel with independent per-replicate seeds. No code was copied,
vendored or adapted; FHR3's `rq7` engine is an independent implementation. Using any
of its source would require a deliberate licensing decision, which is out of scope.
