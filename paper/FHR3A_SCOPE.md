# FHR3A: scope and framing (supersedes any "competition-ranking" framing)

This file is a research handoff note, not manuscript prose. The manuscript has not been
rewritten, and F1–F6, RQ6 and RQ7 are unchanged.

## What FHR3A is

> FHR3A is a controlled empirical study of how poker format, table size, stack depth and
> betting structure affect the concentration, magnitude and removability of evaluation
> variance.

The controlled axes, with their status:

| axis | evidence | status |
|---|---|---|
| poker format (AoF, NLHE, Crazy Pineapple, PLO, Bomb Pot, Nit Game) | core corpus, C1–C3 | frozen |
| stack depth (NLHE 6-max 20/50/100BB, paired) | `stack.json`, C5 | frozen |
| variance concentration / big pots | `allin.csv`, `pilot_table.csv`, C2 | frozen |
| chance-variance removability (all-in EV, MIVAT, AIVAT) | RQ6, C6 | frozen |
| candidate/reference population sensitivity | the p1/p2/p3 spread, C7 | frozen |
| **table size** (NLHE 100BB at 3/4/6/8 seats, one controlled opponent population) | `reports/table-size/ANALYSIS.md`, `claims.json` (TS1–TS6) | **complete; analysed; frozen** |

## What must be stated explicitly

1. **The synthetic agents are controlled experimental populations.** They are instruments that
   vary one environment factor at a time. They are not claimed to represent a real competition
   field or strong play.
2. **Absolute sample-complexity numbers are conditional on those populations.** Hands, blocks
   and wall-clock hold for these candidates, references and pairings. The mechanisms and the
   within-design comparisons are the transferable findings (L1, L2).
3. **The table-size experiment tests whether the 4-max/6-max per-played-hand similarity (C10,
   1.04 [0.98, 1.11]) generalises** to 3 and 8 seats, or whether it bends at small or large
   tables.
   * **Why 4-max and 6-max are rerun.** The original 4/6 comparison changed reference
     composition with table size (4-max: tight, loose, aggressive; 6-max: those plus two
     neutral seats). The dedicated table-size experiment standardizes the marginal opponent
     population to isolate table size more cleanly.
   * **The common population.** All four table sizes (3/4/6/8) run new corpora under one
     deterministic reference schedule. Every relative opponent slot is exactly 40% neutral,
     20% tight, 20% loose and 20% aggressive.
   * **The frozen 4/6 corpora** are untouched. They are reported only as a separate historical
     comparison, never in the primary curve.
   * **Result:** per-hand burden rises modestly with table size (required hands ∝ k^0.37
     [0.25, 0.50]; ×1.47 from 3 to 8 seats), consistently across p1–p3. Standardizing the
     population changed almost nothing at fixed table size. The historical 4-vs-6
     near-invariance was correct for those two sizes but underpowered as a general claim.
     See `../reports/table-size/ANALYSIS.md`.
4. **This work is NOT the FullHouse Swiss ranking experiment.** Every result is a pairwise
   comparison against a fixed reference environment.
5. **Tournament-level Swiss ranking reliability is a separate, next research direction.** It
   covers field ranking, pairing schedules and rank stability, and it is not addressed here.

## Pointers

* Frozen evidence: `CLAIMS.md`, `NUMBERS.md`, `EVIDENCE_MAP.md` and `LIMITATIONS.md` (L13 is
  the table-size caveat).
* Table-size design, runbook and caveats: `../docs/table_size.md`.
* Table-size outputs, after the runs: `../reports/table-size/{summary.csv,summary.json,figure_data.csv,MANIFEST.json}`.
