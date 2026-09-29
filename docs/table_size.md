# FHR3A table-size sweep: NLHE 100BB at 3 / 4 / 6 / 8 seats

Status: **set up, not run** (2026-09-29). The two new corpora are researcher-run
(`scripts/run_table_size.sh`). The 4- and 6-max points reuse the frozen core corpora; they are
only read.

## Question

The frozen result C10 says NLHE 4-max and 6-max cost about the same per played hand
(6-max / 4-max required hands 1.04 [0.98, 1.11]). The sweep tests whether that per-hand
similarity holds outside 4 vs 6.

Per-played-hand invariance means σ_D² ∝ k. Under that, required played hands are flat in k,
and required blocks scale as 1/k. The analysis reports:
* σ_D relative to 6-max;
* required blocks;
* required **played hands** at 1 BB/100, α = .05 two-sided, 80% power;
* the elasticity d log(hands) / d log(k), where 0 means invariance.

These are reported per pairing and as the median over p1–p3.

## Experiments

| seats | experiment_id | config | config_hash | role | blocks p1–p3 | control |
|---|---|---|---|---|---|---|
| 3 | `fhr3-nlhe3-100bb-v1` | `configs/nlhe_3max_100bb.yaml` | `579e143783d086c7` | **new** | 30,000 | 10,000 |
| 4 | `fhr3-nlhe4-100bb-v2` | `configs/nlhe_4max_100bb_v2.yaml` | `ab7e279f1720c074` | frozen, reused | 100,000 | 10,000 |
| 6 | `fhr3-nlhe6-100bb-pilot-v1` | `configs/nlhe_6max_100bb.yaml` | `5f8886e193bc5489` | frozen, reused | 250,000 | 10,000 |
| 8 | `fhr3-nlhe8-100bb-v1` | `configs/nlhe_8max_100bb.yaml` | `389507f11e1692ab` | **new** | 30,000 | 10,000 |

Pairing hashes:

| pairing | 3-max | 8-max |
|---|---|---|
| p1-neutral-vs-loose10 | `977da395648b8e30` | `84167055446c4ef7` |
| p2-neutral-vs-tight | `c02f9e38f144a4f6` | `dd624a8e514a67f0` |
| p3-aggressive-vs-neutral | `8ecc36ca1bbd9992` | `4d3c9a4892e0fa58` |
| c0-selfplay-control | `81adff0361fb903b` | `aafedcc07d3b7d4d` |

All eight 3-/8-max hashes and the 4-/6-max lock hashes are pinned in
`tests/test_table_size.py`.

**What is identical across the sweep:**
* variant `nlhe`, 100BB, blinds 50/100, no ante;
* root seed 20260928;
* RNG coupling (shared/shared) and salts;
* seed derivation `fhr3-seed-v1` and matched protocol `fhr3-matched-v1`;
* candidate specs and implementation versions (`heuristic-1.0.0`);
* pairing definitions p1/p2/p3/c0.

**What differs:** only `player_count`, `experiment_id` and the reference population, which
must have k − 1 seats. A test enforces this.

## Matched-block construction

The design is the same as `docs/matched_blocks.md`, which was already general in k. No engine
or agent code changed for this sweep.

1. `block_seed = derive_seed("fhr3-block", root_seed, block_id)`. One deck is shuffled from
   the chance stream. Hole cards are bound to **seats** (`deck[2p:2p+2]` → seat p), followed
   by a fixed runout of 8 cards (burn, flop, burn, turn, burn, river). The deal uses 2k + 8
   cards: 14 at 3-max, 24 at 8-max.
2. Fixed-button table: seat 0 = SB, seat 1 = BB, seat k−1 = button. Preflop action starts at
   seat 2; postflop action starts at the SB.
3. **Candidate seat rotation.** For every seat s = 0..k−1 and side X ∈ {A, B}, one hand is
   played on the same deal with candidate X in seat s. Reference j sits in seat
   (s + 1 + j) mod k, so the reference line-up relative to the candidate is identical in
   every hand.
4. `D = Σ_s (X_{A,s} − X_{B,s})` in BB. The block is the only independent unit.

| | 3-max | 8-max |
|---|---|---|
| seats (positions) | 0 SB, 1 BB, 2 BTN | 0 SB, 1 BB, 2 UTG, 3 UTG+1, 4 LJ, 5 HJ, 6 CO, 7 BTN |
| candidate hands per side (k) | 3 | 8 |
| **played hands per matched block** | **6** | **16** |
| hands per block, compare | 4-max: 8; 6-max: 12 | |

**3-max reference fill** (population `mixed2-v1` = [ref_tight, ref_loose]):

| candidate seat s | ref_tight (j=0) | ref_loose (j=1) |
|---|---|---|
| 0 SB | 1 BB | 2 BTN |
| 1 BB | 2 BTN | 0 SB |
| 2 BTN | 0 SB | 1 BB |

**8-max reference fill** (population `mixed7-v1`): reference j sits in seat (s + 1 + j) mod 8,
where j runs over [ref_tight, ref_neutral_1, ref_loose, ref_aggressive, ref_neutral_2,
ref_neutral_3, ref_neutral_4]. For example:
* with the candidate on the button (s = 7), ref_tight is SB and ref_neutral_4 is CO;
* with the candidate in the SB (s = 0), ref_tight is BB and ref_neutral_4 is BTN.

**RNG streams** are unchanged: chance, candidate and reference streams are keyed separately.
* The A- and B-hands of a seat share candidate draws by ordinal and reference draws by
  seat/ordinal (common random numbers).
* Self-play therefore gives D = 0 exactly, and an A/B swap negates D exactly.
* Both properties are tested at 3 and 8 seats.

**Cross-table-size matching.** Blocks are not paired across table sizes. The deal layouts
differ (`board-h2-k3`, `-k4`, `-k6`, `-k8`), so the same block id deals different hands. The
controlled intervention is the shared rules, stack, agent family, pairings and method. This is
the same as the existing 4 vs 6 comparison, which has corr(D) ≈ 0. Ratio CIs therefore
resample each corpus independently.

## Pairings and the positional generalisation

p1/p2/p3/c0 use byte-identical candidate specs at every table size:
* p1: neutral vs neutral with looseness 1.10 (small perturbation);
* p2: neutral vs tight (moderate style gap);
* p3: aggressive vs neutral (larger gap);
* c0: neutral vs neutral copy.

No pairing was invented or tuned for the new sizes.

**Seat-count audit of `HeuristicAgent` and the engine.** Nothing was hard-coded to 4 or 6
seats. Nothing was fixed, because nothing was broken, and no agent or engine code changed.

| checked | finding |
|---|---|
| position naming/ordering | seat index = position for any k (`games/base.py`); no position names in agent logic |
| preflop open ranges | indexed by **seats behind the button**: `open_pct_by_seats_behind = (0.45, 0.28, 0.20, 0.16, 0.14, 0.12, 0.11, 0.10)` (8 entries, so no clipping up to 10-max); SB uses `sb_open_pct`; BB iso-raises vs limps |
| blind handling | PokerKit blinds tuple `(SB, BB, 0, …)` built from `player_count`; tested at 3 and 8 |
| facing-raise / 3-bet / 4-bet ranges | depend only on "am I the BB" and the number of raises |
| number of opponents | postflop equity penalty uses `n_active` (live players), so it scales with table size |
| seat rotation | `reference_seats(k, s)` is generic |
| player-count limits | `GameConfig` allows 2–10; the deck needs 2k + 8 ≤ 52 |
| reference population | the loader enforces exactly k − 1 seats |
| hard-coded 4/6 lookups | only in the frozen core-analysis scripts (`final_analysis.py`, `paper_numbers.py` format labels). They are not touched; the sweep has its own script. |

The resulting unopened-pot open ranges (before looseness) are:

| seats behind BTN | 5 | 4 | 3 | 2 | 1 | 0 | SB |
|---|---|---|---|---|---|---|---|
| 3-max | | | | | | BTN 45% | 36% |
| 4-max | | | | | CO 28% | BTN 45% | 36% |
| 6-max | | | UTG 16% | HJ 20% | CO 28% | BTN 45% | 36% |
| 8-max | UTG 12% | UTG+1 14% | LJ 16% | HJ 20% | CO 28% | BTN 45% | 36% |

8-max is the first NLHE corpus to use the 14% and 12% entries. These values have been part of
`heuristic-1.0.0` since its creation and were not chosen for this experiment.
`test_heuristic_positional_mapping_generalises` checks the rule at every unopened seat.

## Reference populations: the smallest principled generalisation

The existing populations follow one rule: **tight, loose and aggressive reference seats
appear once each, and the remaining seats are neutral.**
* 4-max `mixed3-v1` = [tight, loose, aggressive];
* 6-max `mixed5-v1` = [tight, neutral, loose, aggressive, neutral].

The sweep extends the rule by nesting:

| seats | population | styles (j = 0 sits immediately after the candidate) | neutral share |
|---|---|---|---|
| 3 | `mixed2-v1` | tight, loose | 0% |
| 4 | `mixed3-v1` | tight, loose, aggressive | 0% |
| 6 | `mixed5-v1` | tight, neutral, loose, aggressive, neutral | 40% |
| 8 | `mixed7-v1` | tight, neutral, loose, aggressive, neutral, neutral, neutral | 57% |

* **8-max** is the 6-max population with two neutral seats appended. The five seats nearest the
  candidate's left are exactly the 6-max line-up.
* **3-max** cannot seat three non-neutral styles in two seats, so an exact mapping is
  impossible. It takes the first two seats of `mixed3-v1` (a prefix rule), fixed before any
  data. It drops the aggressive reference.

Mean reference looseness and aggression by table size:

| seats | looseness | aggression |
|---|---|---|
| 3 | 1.05 | 0.95 |
| 4 | 1.08 | 1.10 |
| 6 | 1.05 | 1.06 |
| 8 | 1.04 | 1.04 |

The populations were not tuned. See caveat 1.

## Metrics (`scripts/table_size_analysis.py`)

The definitions are identical to `scripts/final_analysis.py`. For 4-/6-max, every number is
asserted equal to the frozen `ranking.json`, `allin.csv` and `core/pilot_table.csv`. The
13 metrics, per table size and per p1/p2/p3:

1. σ_D, with a block-bootstrap CI;
2. σ_D², plus σ_D²/k;
3. played hands per block (2k);
4. required blocks: ⌈((z.975 + z.8) σ_D / (k/100))²⌉;
5. required played hands (blocks × 2k), with a CI;
6. P(D = 0);
7. excess kurtosis (Fisher, as in the core);
8. top-1% share of squared deviation (and top-0.1%);
9. share of blocks with a pot ≥ one starting stack;
10. share of squared deviation in those blocks;
11. all-in block frequency;
12. all-in block share of squared deviation;
13. blocks/s and wall-clock hours required at 8 workers. This is secondary and
    implementation-specific.

**Derived quantities:**
* σ, σ², blocks and hands ratios vs 6-max, per pairing (with CIs) and as ratio of medians
  (with CIs);
* elasticity of required hands in k: overall log-log OLS and per segment (3→4, 4→6, 6→8), per
  pairing and for the median series;
* same-n sensitivity: σ_D and required hands of the 4-/6-max corpora on their first 30,000
  blocks.

**Outputs:**

| file | contents |
|---|---|
| `reports/table-size/summary.csv` | one row per seats × pairing |
| `reports/table-size/summary.json` | per-pairing rows, medians, elasticities, invariant checks, sources |
| `reports/table-size/figure_data.csv` | pairing rows and median rows; for Panel A (σ vs 6-max) and Panel B (required hands, absolute and vs 6-max), with hands per block as an annotation |
| `reports/table-size/MANIFEST.json` | written by `--freeze`; checked by `--verify` |
| `reports/table-size/validate/` | validation reports |

**Guards.** The script refuses to run if any of the following fails:
* a frozen 4-/6-max Parquet fingerprint differs from `reports/final-analysis/MANIFEST.json`;
* a new corpus is short of target, non-contiguous, has invalid or NaN rows, or carries the
  wrong config or pairing hash;
* played hands ≠ 2k;
* the control is not exactly 0.

`--allow-partial` exists for smoke runs only. Its output is marked provisional and cannot be
written to `reports/table-size` or frozen.

## Runbook

These are the exact commands. They are also bundled as `scripts/run_table_size.sh
[sim3|sim8|validate|analyse|all]`. Every `simulate` is resumable: re-running skips finished
250-block chunks.

```bash
# 1. 3-max publication corpus
.venv/bin/fhr3 simulate --config configs/nlhe_3max_100bb.yaml --blocks 0:10000 --pairing c0-selfplay-control --workers 8
.venv/bin/fhr3 simulate --config configs/nlhe_3max_100bb.yaml --blocks 0:30000 \
    --pairing p1-neutral-vs-loose10 --pairing p2-neutral-vs-tight --pairing p3-aggressive-vs-neutral --workers 8
# 2. 8-max publication corpus
.venv/bin/fhr3 simulate --config configs/nlhe_8max_100bb.yaml --blocks 0:10000 --pairing c0-selfplay-control --workers 8
.venv/bin/fhr3 simulate --config configs/nlhe_8max_100bb.yaml --blocks 0:30000 \
    --pairing p1-neutral-vs-loose10 --pairing p2-neutral-vs-tight --pairing p3-aggressive-vs-neutral --workers 8
# 3. validation / integrity (and proof the frozen research is untouched)
scripts/run_table_size.sh validate
# 4 + 5. table-size analysis + figure data, frozen and re-verified
scripts/run_table_size.sh analyse
```

**Runtime estimate.** This is an **estimate, not a measurement**. It comes from the frozen
runs' throughput on the same Apple M1 at 8 workers:
* 4-max: 674 blocks/s, about 5.4k hands/s;
* 6-max: 352 blocks/s, about 4.2k hands/s;
* a 200-block smoke run gave 8-max ≈ 207 blocks/s, including start-up.

Per-hand speed falls as the table grows. Each new corpus is 100,000 blocks (3 × 30k + 10k).

| step | expected time |
|---|---|
| 3-max, at ~1,000 blocks/s | ≈ 2–4 min |
| 8-max, at ~190–220 blocks/s | ≈ 8–12 min |
| validation (replays, integrity, three manifest verifies) | ≈ 1–2 min |
| analysis with 1,000 bootstrap reps | ≈ 1–2 min |
| **total** | **≈ 15–20 min** |

## Caveats: things that could make the 3/4/6/8 comparison invalid

1. **Table size is confounded with reference-population composition.** k − 1 reference seats
   cannot hold a fixed population:
   * 3-max has no aggressive reference;
   * 4-max has no neutral seat;
   * 6- and 8-max are 40% and 57% neutral.

   This was already true of the frozen 4 vs 6 comparison (C10). The sweep measures "table size
   under this nested population rule". A bend at 3-max, in particular, may reflect the missing
   aggressive seat. A population-matched design (for example, all-neutral references) would be
   a separate experiment.
2. **Agents are not re-tuned per table size.** Positional adaptation comes only from the
   seats-behind open table and the `n_active` multiway penalty. A table-size effect on σ_D
   includes how appropriate these heuristics are at 3 or 8 seats (assumption 11).
3. **Unequal and modest n.** The new corpora have 30k blocks, against 100k/250k for the frozen
   ones. The relative SE of σ_D is √((κ + 2)/(4n)), and NLHE 100BB kurtosis is large, so
   30k blocks give roughly ±10–25% on required hands at 95%. Small bends may not be
   resolvable.

   The same-n prefix columns show the frozen points at 30k. Extending is resumable: rerun
   with `--blocks 0:60000`. A second freeze is then required.
4. **Not paired across table sizes.** CIs are independent-sample, with pairings held fixed.
   Pairing-to-pairing variation is shown by keeping p1/p2/p3 separate, not by the CI.
5. **Effect-size meaning.** 1 BB/100 of candidate hands is held fixed across k. Realistic edges
   may differ by table size, the same caveat as L3.
6. **Schema.** The new corpora use the current block schema. The 6-max corpus is
   `fhr3-block-v1`. Every column used exists in both, and the frozen cross-checks prove the
   definitions agree.
7. **Wall-clock** is secondary and specific to the implementation and machine (L9).
