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
| **table size** (NLHE 100BB at 3/4/6/8 seats) | `docs/table_size.md`, `reports/table-size/` | **set up; 3-/8-max runs pending** |

## What must be stated explicitly

1. **The synthetic agents are controlled experimental populations.** They are instruments that
   vary one environment factor at a time. They are not claimed to represent a real competition
   field or strong play.
2. **Absolute sample-complexity numbers are conditional on those populations.** Hands, blocks
   and wall-clock hold for these candidates, references and pairings. The mechanisms and the
   within-design comparisons are the transferable findings (L1, L2).
3. **The table-size experiment tests whether the 4-max/6-max per-played-hand similarity (C10,
   1.04 [0.98, 1.11]) generalises** to 3 and 8 seats, or whether it bends at small or large
   tables. Until the runs are analysed, C10 stays a 4-vs-6 statement and no general
   player-count claim is made. Table size is confounded with reference-population composition
   (`docs/table_size.md`, caveat 1).
4. **This work is NOT the FullHouse Swiss ranking experiment.** Every result is a pairwise
   comparison against a fixed reference environment.
5. **Tournament-level Swiss ranking reliability is a separate, next research direction.** It
   covers field ranking, pairing schedules and rank stability, and it is not addressed here.

## Pointers

* Frozen evidence: `CLAIMS.md`, `NUMBERS.md`, `EVIDENCE_MAP.md` and `LIMITATIONS.md` (L13 is
  the table-size caveat).
* Table-size design, runbook and caveats: `../docs/table_size.md`.
* Table-size outputs, after the runs: `../reports/table-size/{summary.csv,summary.json,figure_data.csv,MANIFEST.json}`.
