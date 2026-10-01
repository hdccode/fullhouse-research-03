# FullHouse Research #4 scope (locked design; internal id `fhr3b`)

Publicly this study is **FullHouse Research #4**. Internal identifiers (`fhr3b`, package
`fhr3.tournament`, namespaces, cell ids) keep the `fhr3b` name to avoid churn.

**Question.** How should FullHouse spend a finite simulation budget so that a Swiss-style
poker-bot competition reliably identifies the strongest agents?

The object of study is the whole tournament mechanism. One independent observation is one
complete tournament replication:

```text
field -> tables -> poker outcomes -> cumulative standings -> standings-dependent Swiss reassignment
      -> further rounds -> final leaderboard -> top-6 qualification set
```

The lower-level question of pairwise evaluation variance belongs to FHR #3 (FHR3A), which is a
separate note; this study does not change its manuscript, figures F1–F6, claims or corpora.

## Core publication scope: NLHE6 only

| item | core study |
|---|---|
| game | 6-max NLHE 100 BB, persistent stacks within a match, no rebuys |
| field size | 60 bots |
| fields | three frozen regimes: `spread` (`ff0f2b07fc210f62`), `crowded_cutoff` (`afbffedfc3706d84`), `style_diverse` (`ad7d6596ef1c8c3e`) |
| unique tournament cells | six per field, 18 in total (below) |
| tournaments per cell | **50 initially**; extended per cell only where needed |
| `mu_field` | **250 matched duplicate rounds per field initially** (a core-scoped budget, not a global default); extendable to 500 |
| `mu_swiss` | **100 complete tournaments per field initially**; extendable per field to 200 after review |

**Not part of the core matrix.**

* **AoF4 and NLHE4.** Their fields stay frozen, provenance-supported and valid in the general
  system (`configs/fhr3b/fields/FROZEN.yaml`), but they are not run here.
* **AoF4 and Crazy Pineapple ranking budgets.** FullHouse needs approximate ranking durations
  for these formats. They will come from later, separate *operational ranking-budget studies*,
  which are neither part of this paper nor set up yet.
* **PLO** is removed. Retired and revoked fields are never used.

**Public 2026 engine.** Its semantics (the Swiss pairing rule, raw chip-delta scoring,
tiebreaks, the 400-hand persistent-stack match) are a *research reference*. They are not a
declaration of the 2027 competition format, which this study neither knows nor describes.

## Research baseline (`fhr3b_baseline`, `lab60_top6`)

| parameter | value | status |
|---|---|---|
| field size N | 60 bots | research design choice |
| qualifiers K | top 6 (~10%) | research design choice |
| rounds | **40 is the initial horizon**; checkpoints 5, 10, 20, 30, 40 | a starting point, **not** an assumption that 40 rounds suffice. 60/80/120-round extensions exist but are disabled by default; a field is extended only if its qualification metrics have not stabilised |
| hands per match | 400 | retained from the public 2026 engine |
| round 1 | deterministic seeded shuffle | research design choice |
| later rounds | standings-dependent Swiss assignment | public 2026 engine rule |
| score | raw cumulative chip delta; public 2026 tiebreaks | public 2026 engine rule |
| publication mode | **NLHE6 only** | AoF4/NLHE4 frozen for provenance; PLO is removed |

The historical record, with its unknowns, is `historical_2026_reconstruction`
(`docs/fhr3b/2026_protocol_audit.md`). The historical operational validation stays blocked
until its missing values are supplied.

## Literature positioning

**Narrow novelty claim.** Prior work studies either tournament designs that recover latent
rankings under noisy pairwise outcomes, or variance reduction for evaluating poker agents.
FullHouse Research #4 studies the intersection: top-6 selection reliability in an adaptive,
six-player poker-bot Swiss tournament under a fixed simulation budget.

We do **not** claim that the Swiss system, top-k metrics, common random numbers or duplicate
poker are novel.

| work | what we take from it | what we do not claim |
|---|---|---|
| Sziklai, Biró & Csató (2022), *The efficacy of tournament designs*, Computers & Operations Research, doi:10.1016/j.cor.2022.105821 | Tournament design as the allocation of limited comparison resources under noisy outcomes, judged by how well a design recovers the underlying ranking. **Experiment B** is the poker analogue: at fixed simulator work, is compute better spent on more opponents (Swiss rounds) or on longer matches? | That their pairwise-comparison findings transfer automatically to six-player poker tables with persistent stacks. |
| Hua, C. (May 2017), *The Swiss Tournament Model*, Wharton Research Scholars undergraduate thesis, The Wharton School, University of Pennsylvania | Motivation for judging a Swiss event by **partial-ranking / top-k recovery**, not only by whole-ranking correlation. Our competition-specific top-k metrics are top-6 overlap, expected changed qualifiers and P(qualify). | Novelty of top-k evaluation. |
| The Annual Computer Poker Competition literature, e.g. Bard, N., Hawkin, J., Rubin, J. & Zinkevich, M. (2013), *The Annual Computer Poker Competition*, AI Magazine 34(2), 112–114, doi:10.1609/aimag.v34i2.2474 | **Duplicate poker** is established computer-poker methodology, including multiplayer events that duplicate cards with cyclic seat rotation. **Experiment D** asks a different question: whether *whole persistent-match* duplication improves *qualifier reliability per unit of actual simulator work*. | That duplicate poker, or multiplayer seat/card duplication, is new. |
| Davidson, Archibald & Bowling (2013), *Baseline: Practical Control Variates for Agent Evaluation in Zero-Sum Domains*, AAMAS 2013 | Together with AIVAT, the general problem of extracting more information per simulated hand. | — |
| Burch, Schmid, Moravčík, Morrill & Bowling (2018), *AIVAT: A New Variance Reduction Technique for Agent Evaluation in Imperfect Information Games*, AAAI 32(1), doi:10.1609/aaai.v32i1.11481 | FHR #3 studied estimator-level variance reduction. FHR #4 asks whether better *evaluation design* improves the competition's actual *selection outcome*. | — |

## Reference rankings (diagnostics, never scores)

* **`mu_field`**: long-run expected performance against the controlled field.
  * Estimated by matched evaluation: six whole-match duplicate lanes, 400 hands per lane,
    cyclic seats and common chance streams.
  * Tables are random field partitions, independent of Swiss standings.
  * Reported on the ordinary-match scale (lane sum / 6).
  * Analytic SE is primary; a 10-round grouped joint bootstrap feeds the ranking and gap
    diagnostics.
  * Common random numbers couple the three field references; they are not independent
    replications.
  * 250 matched rounds per field initially, extendable to 500 without repeating the first 250.
* **`mu_swiss`**: long-run expected final performance under adaptive Swiss, estimated from
  **100 complete tournaments per field** in the separate `swiss-reference` namespace. After that
  run, each field is judged separately for whether 200 is warranted; an extension appends
  tournaments 100–199 without recomputing the first 100. Primary reference outputs:
  * per-bot P(qualify) with Wilson intervals;
  * expected final score, total and per match, with SE;
  * expected top-6 overlap against `mu_field` (and, flagged as in-sample, against `mu_swiss`);
  * rank and top-6 uncertainty: a joint tournament bootstrap giving rank intervals,
    P(in the `mu_swiss` top 6) and P(same top-6 set);
  * the boundary bots whose qualification remains materially ambiguous.

  In `crowded_cutoff` and `style_diverse` the rank-6/rank-7 ordering is not expected to become
  clean. That ambiguity is part of the experimental object.

Neither is "true poker skill". Finite tournaments are assessed for **accuracy** against each
reference and for **repeatability** across independent replications. Disagreement between the
two references is a finding in its own right.

## Experiments and the six unique cells per field

| # | cell | experiments served |
|---|---|---|
| 1 | adaptive ordinary 40 × 400 (baseline) | A (prefixes 5/10/20/30/40), B, C (adaptive arm), D (ordinary arm) |
| 2 | adaptive ordinary 20 × 800 | B |
| 3 | adaptive ordinary 10 × 1600 | B |
| 4 | frozen-schedule ordinary 40 × 400 | C |
| 5 | duplicate, fewer rounds: 7 × 400 × 6 lanes (+5.0% scheduled work) | D |
| 6 | duplicate, shorter matches: 40 × 67 × 6 lanes (+0.5% scheduled work) | D |

Shared cells have one identity hash and are simulated once (pinned by `tests/test_fhr4_core.py`).

* **A. Rounds to reliability.** Reliability at 5, 10, 20, 30 and 40 rounds, read as exact
  prefixes of the same 40-round trajectories.
* **B. Fixed total poker budget.** 10 × 1600, 20 × 800 and 40 × 400 hands per bot. The 40 × 400
  cell is the baseline.
* **C. Adaptive Swiss vs frozen schedule.** The estimand is a **source-schedule
  counterfactual**:
  * the source adaptive tournament (baseline replicate r) generates a realised Swiss schedule;
  * the frozen replay plays exactly that realised schedule with **fresh** poker randomness
    (new cards and decisions);
  * the replay's own results cannot affect its future pairings.

  This removes within-run result → future-pairing feedback while preserving realistic Swiss
  schedule structure. It is *not* an identical-randomness causal pair of the source run.

  The initial core uses **J = 1** (one replay per source), and the analysis pairs the adaptive
  baseline and its frozen replay by source tournament. J > 1 is supported as a later precision
  extension (a new cell); uncertainty is then clustered by source tournament, so several replays
  of one source are never treated as independent observations. The contrast is a diagnostic,
  not an additive variance decomposition, and the frozen schedule is not a proposed format.
* **D. Ordinary vs duplicate.** Uses the existing whole-match duplicate implementation:
  * six lanes;
  * the same initial stacks and chance stream in every lane;
  * cyclic seats;
  * independent stacks and bot state per lane;
  * aggregation only after all lanes finish.

  Work is reported as both scheduled and actually played hands. The integer-constrained variants
  are approximately, not exactly, equal in work.

  The fewer-rounds arm is deliberately **7 × 400 × 6**, which is +5% scheduled work and flagged
  as a 1.05 work ratio. It is not 7 × 381: the arm isolates *fewer Swiss rounds plus duplicate
  play* while keeping the standard 400-hand match object. Any per-compute comparison is made
  explicit using the recorded scheduled and actual work.

## Metrics

* **Primary (qualification; these dominate):**
  * expected number of changed qualifiers;
  * expected top-6 overlap;
  * per-bot P(qualify);
  * number of bots with ambiguous qualification.
* **Supporting:**
  * rank-6/rank-7 gap and inversion uncertainty;
  * Kendall tau;
  * Spearman correlation;
  * mean absolute rank displacement;
  * pairwise inversion against the reference strength gap.

All uncertainty is computed over tournaments. Hands, matches and rounds are never replicates.

## Adaptive compute policy

This is **precision-driven compute allocation**, not "run everything until significance".

* Every unique cell starts at 50 complete tournaments, every field reference at 250 matched
  rounds, and `mu_swiss` at 100 tournaments per field.
* A cell is extended (append-only: e.g. tournaments 50–99) only where uncertainty in the
  **primary qualification metrics** is still consequential for a conclusion.
* Field references extend from 250 to 500 rounds only where the reference ordering near the
  cutoff is too uncertain to judge accuracy. `mu_swiss` extends from 100 to 200 per field only
  where that is warranted after the 100-tournament run. Intrinsic ambiguity in `crowded_cutoff`
  and `style_diverse` is not by itself a reason to extend.
* Long horizons (60/80/120 rounds) are run only for fields whose qualification metrics have not
  stabilised by 40 rounds.
* Every extension is an explicit, logged command. No preset launches 100, 200 or 500
  tournaments.

## Match semantics

**NLHE6** follows the public 2026 match rule:

* every Swiss match starts every bot at 100 BB;
* stacks persist between hands within the match, with no rebuys;
* a bot at zero is out for the rest of the match, and survivors play on with their actual
  stacks, including short, deep and asymmetric effective stacks;
* each new Swiss round is a new match, starting again at 100 BB;
* the standing is the cumulative chip delta over matches.

Dynamic stack management is therefore part of the measured skill. Busting is not treated as a
defect in itself.

## Controlled fields

| field | purpose |
|---|---|
| `spread` | broad strength distribution with a separated rank-6/rank-7 boundary |
| `crowded_cutoff` | several genuinely similar bots, of different strategies, straddling the boundary |
| `style_diverse` | deliberate balance of observed style across strength strata |

Non-transitive (matchup) structure is **measured, never selected on**. The former
`matchup_sensitive` field and its gate are retired.

The bots are synthetic experimental instruments: transparent, stateless FHR3 policy families.
For NLHE, the study uses `fhr3b_heuristic`, the FHR3A heuristic with correct heads-up blind
roles. The FHR3A family misread heads-up roles, which persistent-stack busts make common
(23–53% of hands). The bots are not models of human professionals. Selection rules and the
realism audit are in `docs/fhr3b/FIELDS.md` and
`reports/fhr3b/field-calibration/FIELD_CALIBRATION_REVIEW.md`.

## Caveats every write-up must state

* **Stateless agents (D5).** Within-match opponent modelling is under-represented. The match
  runner exposes the rolling previous-hand history, as the public 2026 engine does, but the
  shipped FHR3 agents condition only on the current hand's observation (including all stacks).
* **Weak stack-depth adaptation.** In the replay audit, NLHE preflop VPIP is flat across stack
  depth; only all-in propensity rises when short. Stack skill is expressed mainly through
  commitment thresholds and pot odds.
* **One game.** The core results are for NLHE6. They do not establish ranking budgets for AoF4,
  Crazy Pineapple or any other format.
* **Conditional results.** Every result is conditional on the constructed fields and on the
  research protocol. None of it describes the 2026 event directly or the 2027 competition at
  all.
