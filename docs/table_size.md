# FHR3A controlled table-size suite: NLHE 100BB at 3 / 4 / 6 / 8 seats

Status: **complete** (2026-09-29). All four corpora have been run, validated and frozen
(`reports/table-size/MANIFEST.json`). The scientific analysis is in
`reports/table-size/ANALYSIS.md`, with claims in `claims.json` and figure and paper plans in
`figure_plan.md`; derived tables are in `reports/table-size/deep/` (`scripts/table_size_deep.py`).

## Why 4-max and 6-max are rerun

The original 4/6 comparison changed the reference composition along with table size:
* frozen 4-max `mixed3-v1`: tight, loose, aggressive;
* frozen 6-max `mixed5-v1`: tight, neutral, loose, aggressive, neutral.

The dedicated table-size experiment standardizes the marginal opponent population to isolate
table size more cleanly. The frozen 4/6-max corpora and their manifests are untouched. They
appear only in a separate historical comparison and are never mixed into the primary
3/4/6/8 curve.

## Question

Frozen C10 found 6-max / 4-max required played hands of 1.04 [0.98, 1.11], under different
populations. The question here: with the opponent population held fixed, does per-hand
resolving difficulty stay flat in table size, or does it bend at small or large tables?

Per-played-hand invariance means σ_D² ∝ k. Then required played hands are flat in k, and
required blocks scale as 1/k. The analysis reports:
* σ_D relative to controlled 6-max;
* required blocks;
* required played hands at 1 BB/100, α = .05 two-sided, 80% power;
* the elasticity d log(hands) / d log(k), where 0 means invariance.

These are reported per pairing and as the median over p1–p3.

## Experiments

| seats | experiment_id | config | config_hash | p1–p3 | control |
|---|---|---|---|---|---|
| 3 | `fhr3a-nlhe3-100bb-tablesize-v1` | `configs/tablesize/nlhe_3max_100bb.yaml` | `c9937b916d1bb80f` | 30,000 | 10,000 |
| 4 | `fhr3a-nlhe4-100bb-tablesize-v1` | `configs/tablesize/nlhe_4max_100bb.yaml` | `56dcbd13a8614cbb` | 30,000 | 10,000 |
| 6 | `fhr3a-nlhe6-100bb-tablesize-v1` | `configs/tablesize/nlhe_6max_100bb.yaml` | `e02ffdc936b79e3f` | 30,000 | 10,000 |
| 8 | `fhr3a-nlhe8-100bb-tablesize-v1` | `configs/tablesize/nlhe_8max_100bb.yaml` | `1bbb0bcb3b465ed8` | 30,000 | 10,000 |

Pairing hashes are **identical at every table size**, because the pairing (candidates plus
reference schedule) is the same object:

| pairing | hash |
|---|---|
| p1-neutral-vs-loose10 | `673af4685c2af5bd` |
| p2-neutral-vs-tight | `ae7864c08a103e25` |
| p3-aggressive-vs-neutral | `23aee34fa30d77a6` |
| c0-selfplay-control | `6b579ec93d864457` |

The reference version is `e945702f6e`. Table size lives only in `config_hash`. All values are
pinned in `tests/test_table_size.py`.

**Identical across the suite:**
* variant `nlhe`, 100BB, blinds 50/100, no ante;
* root seed 20260928;
* RNG coupling (shared/shared) and salts;
* seed derivation `fhr3-seed-v1` and matched protocol `fhr3-matched-v1`;
* candidate specs (`heuristic-1.0.0`), byte-identical to every frozen NLHE config;
* p1/p2/p3/c0;
* the reference schedule.

**Differs:** only `player_count` and `experiment_id`.

## The common reference population: a deterministic balanced schedule

```
cycle = [neutral, neutral, tight, loose, aggressive]          # 40 / 20 / 20 / 20 %
reference in relative slot j of block b = cycle[(b + j) mod 5]
```

Slot j = 0 sits immediately after the candidate, and slot j occupies seat (s + 1 + j) mod k
when the candidate is in seat s. The lineup is ordered relative to the candidate, as in the
existing matched design. Consequences:

* **Exact mixture per slot.** Over any 5 consecutive blocks, aligned or not, every relative
  slot sees neutral twice and tight, loose and aggressive once each, at every table size.
  30,000 and 10,000 are multiples of 5, so each slot's corpus mixture is exactly 40/20/20/20.
* **No population noise.** The lineup is a deterministic function of the block id; no random
  draw is involved.
* **A and B face the same lineup.** The lineup is chosen once per block, before any hand is
  played, and every hand of that block (all k seats, both sides) uses it.
* **Per-block composition** is a window of the cycle:
  * at 6-max (5 slots) every block has exactly two neutral seats and one each of tight, loose
    and aggressive, in rotated order;
  * at 3-, 4- and 8-max the per-block composition varies by block, but the per-slot marginal
    is exact;
  * at 8-max, slots j and j + 5 hold the same cycle entry.
* **Recorded and verified.** Each row stores its lineup in `variant_json.reference_lineup`
  (agent ids and styles). Exact replay therefore re-checks it, and the analysis verifies the
  rule and the exact mixture from the stored data.
* **Stratification.** D is independent across blocks, but blocks cycle deterministically
  through 5 lineup patterns. σ_D is the marginal SD under the mixed population, which is the
  intended estimand. Because the design is balanced by stratum, the naive SE of the mean is
  slightly conservative.

**Implementation.**
* `Pairing.reference_cycle` and `Pairing.reference_specs(block_id, k)` in
  `configs/experiment.py`.
* `BlockSimulator.references(block_id)` in `eval/runner.py`.
* A scheduled population is written in YAML as `{cycle: [agent ids]}`.

Fixed populations are unaffected: the schedule key is absent from their pairing hash, and the
frozen 4/6-max lock hashes are pinned in the tests.

## Matched-block construction

This is unchanged (`docs/matched_blocks.md`); nothing needed changing for any table size.

1. **Deal.** `block_seed = derive_seed("fhr3-block", root_seed, block_id)` gives one deck,
   with hole cards bound to seats and an 8-card runout (2k + 8 cards).
2. **Seats.** Fixed-button table: seat 0 = SB, 1 = BB, k−1 = BTN. Preflop action starts at
   seat 2; postflop action starts at the SB.
3. **Rotation.** The candidate occupies every seat s for side A and for side B on the same
   deal. The block's reference lineup fills seats (s + 1 + j) mod k.
4. **Block difference.** `D = Σ_s (X_{A,s} − X_{B,s})`; the block is the only independent unit.

| seats | positions | played hands / block |
|---|---|---|
| 3 | SB, BB, BTN | **6** |
| 4 | SB, BB, CO, BTN | **8** |
| 6 | SB, BB, UTG, HJ, CO, BTN | **12** |
| 8 | SB, BB, UTG, UTG+1, LJ, HJ, CO, BTN | **16** |

**Cross-table-size matching.** Blocks are not paired across table sizes, because the deal
layouts (`board-h2-k3` to `-k8`) differ. Ratio CIs resample each corpus independently.

The suite shares the frozen corpora's root seed and deal layout at 4 and 6 seats. Controlled
block b therefore deals exactly the same cards as historical block b. The analysis uses this
for a **paired** controlled-vs-historical σ comparison at fixed table size, where only the
population differs.

## Agents and positional handling

The seat-count audit found nothing hard-coded to 4 or 6 seats, so no agent or engine logic
changed.
* `HeuristicAgent` opens by seats behind the button:
  `open_pct_by_seats_behind = (0.45, 0.28, 0.20, 0.16, 0.14, 0.12, 0.11, 0.10)`. There is no
  clipping up to 10-max. The SB uses `sb_open_pct`, and the BB iso-raises vs limps.
* Blinds come from `player_count`.
* The multiway penalty uses live players (`n_active`).
* Rotation uses `reference_seats(k, s)`.
* 4/6 labels appear only in the frozen core-analysis scripts, which are untouched.

| seats behind BTN | 5 | 4 | 3 | 2 | 1 | 0 | SB |
|---|---|---|---|---|---|---|---|
| 3-max | | | | | | BTN 45% | 36% |
| 4-max | | | | | CO 28% | BTN 45% | 36% |
| 6-max | | | UTG 16% | HJ 20% | CO 28% | BTN 45% | 36% |
| 8-max | UTG 12% | UTG+1 14% | LJ 16% | HJ 20% | CO 28% | BTN 45% | 36% |

These are the ranges before looseness. The 14% and 12% entries are part of the original
`heuristic-1.0.0`, and nothing was tuned for this suite.

## Analysis (`scripts/table_size_analysis.py`)

**Primary: the publication curve.** It uses only the four controlled corpora. Per table size
and per p1/p2/p3:
1. σ_D, with a bootstrap CI;
2. σ_D², plus σ_D²/k;
3. hands per block;
4. N80 blocks at 1 BB/100;
5. N80 played hands, with a CI;
6. P(D = 0);
7. excess kurtosis;
8. top-1% (and top-0.1%) share of squared deviation;
9. big-pot (≥ one starting stack) frequency and share;
10. all-in block frequency and share;
11. σ, σ², blocks and hands relative to controlled 6-max, per pairing with CIs, and as ratios
    of medians with CIs;
12. elasticity of required hands in k: overall log-log and per segment 3→4, 4→6, 6→8;
13. wall-clock (secondary).

**Historical: separate.** The frozen 4/6-max corpora are reported with the same metrics:
* their fingerprints must equal the core MANIFEST;
* every number must equal the frozen `ranking.json`, `allin.csv` and `pilot_table.csv`;
* same-n (first 30k) columns are included.

A third section gives the paired controlled-vs-historical σ ratio at 4 and 6 seats. None of
this enters the primary curve.

**Checks.** The script refuses to produce output unless all of the following hold:
* every controlled corpus has exactly 30,000 (p1–p3) or 10,000 (control) contiguous blocks,
  with no invalid rows or NaNs, the right config and pairing hashes, and exactly 2k hands per
  block;
* the control is exactly 0;
* every block's recorded lineup equals the rule;
* **every relative slot of every table size and pairing is exactly 40/20/20/20.**

**Outputs.**

| file | contents |
|---|---|
| `reports/table-size/summary.csv` | primary: one row per table size × pairing |
| `reports/table-size/figure_data.csv` | primary: pairing and median rows for panel A (σ vs 6-max) and panel B (hands: absolute and vs 6-max; hands per block for annotation) |
| `reports/table-size/historical.csv` | the frozen 4/6-max rows |
| `reports/table-size/summary.json` | all three sections, checks and sources |
| `reports/table-size/MANIFEST.json` | written by `--freeze`, checked by `--verify` |
| `reports/table-size/validate/` | validation reports |

`--allow-partial` is for smoke runs only: the output is provisional and cannot go to
`reports/table-size` or be frozen.

## Runbook (resumable: re-running skips finished 250-block chunks)

```bash
# p1-p3 publication corpora, 30,000 blocks each
.venv/bin/fhr3 simulate --config configs/tablesize/nlhe_3max_100bb.yaml --blocks 0:30000 --pairing p1-neutral-vs-loose10 --pairing p2-neutral-vs-tight --pairing p3-aggressive-vs-neutral --workers 8
.venv/bin/fhr3 simulate --config configs/tablesize/nlhe_4max_100bb.yaml --blocks 0:30000 --pairing p1-neutral-vs-loose10 --pairing p2-neutral-vs-tight --pairing p3-aggressive-vs-neutral --workers 8
.venv/bin/fhr3 simulate --config configs/tablesize/nlhe_6max_100bb.yaml --blocks 0:30000 --pairing p1-neutral-vs-loose10 --pairing p2-neutral-vs-tight --pairing p3-aggressive-vs-neutral --workers 8
.venv/bin/fhr3 simulate --config configs/tablesize/nlhe_8max_100bb.yaml --blocks 0:30000 --pairing p1-neutral-vs-loose10 --pairing p2-neutral-vs-tight --pairing p3-aggressive-vs-neutral --workers 8
# self-play controls, 10,000 blocks each
for k in 3 4 6 8; do .venv/bin/fhr3 simulate --config configs/tablesize/nlhe_${k}max_100bb.yaml --blocks 0:10000 --pairing c0-selfplay-control --workers 8; done
# validation: replay, integrity, frozen manifests verify
scripts/run_table_size.sh validate
# combined table-size analysis + figure data (freeze, then re-verify)
scripts/run_table_size.sh analyse
```

The same steps are available as `scripts/run_table_size.sh
[sim3|sim4|sim6|sim8|controls|validate|analyse|all]`.

**Runtime.** These figures are an **estimate**, based on the frozen runs' sustained
throughput on this M1 at 8 workers: 4-max 674 blocks/s, 6-max 352 blocks/s. 3-max (~1,000/s)
and 8-max (~200/s) are extrapolated from hands/s. Each table size is 100,000 blocks.

| step | expected time |
|---|---|
| 3-max | ≈ 2 min |
| 4-max | ≈ 3 min |
| 6-max | ≈ 5 min |
| 8-max | ≈ 8–10 min |
| validation and analysis | ≈ 3–5 min |
| **total** | **≈ 20–25 min** |

The balanced population contains more aggressive and loose seats than some of the frozen
lineups, so hands may run slightly longer.

## Caveats

1. **Composition is controlled per slot, not per block.** The marginal opponent population is
   identical across table sizes. However, the number of opponents grows with k, so a larger
   table has more opponents in total, and more of every style. That is part of what "table
   size" means.

   At 3/4/8-max, per-block compositions vary around the marginal. At 6-max each block has the
   exact composition.

   Slot position relative to the candidate is also a table-size feature. For example, at
   3-max slot 1 is always the seat on the candidate's right; at 8-max it is a middle seat.
2. **Agents are not re-tuned per table size** (assumption 11). The effect includes how
   appropriate these heuristics are at 3 and 8 seats.
3. **30k blocks is modest for heavy tails.** Required hands carry roughly ±10–25% at 95%, so
   small bends may not be resolvable. Extending is resumable (`--blocks 0:60000`) and needs a
   new freeze.
4. **Not paired across table sizes.** CIs are independent-sample, with pairings held fixed.
   Pairing variation is shown by keeping p1/p2/p3 separate.
5. **Effect-size meaning.** 1 BB/100 of candidate hands is held fixed across k (L3).
6. **The historical 4/6 corpora use different populations** (and 6-max uses schema v1). They
   answer a different question and are reported only separately.
7. **Wall-clock is secondary** and specific to this implementation and machine (L9).
