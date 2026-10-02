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
| Sziklai, Biró & Csató (2022), *The efficacy of tournament designs*, Computers & Operations Research, doi:10.1016/j.cor.2022.105821 | Tournament design as the allocation of limited comparison resources under noisy outcomes, judged by how well a design recovers the underlying ranking. **Experiment B** is the poker analogue: given the same maximum scheduled poker budget, should simulation be allocated across more Swiss opponents or longer matches? | That their pairwise-comparison findings transfer automatically to six-player poker tables with persistent stacks. |
| Hua, C. (May 2017), *The Swiss Tournament Model*, Wharton Research Scholars undergraduate thesis, The Wharton School, University of Pennsylvania | Motivation for judging a Swiss event by **partial-ranking / top-k recovery**, not only by whole-ranking correlation. Our competition-specific top-k metrics are top-6 overlap, expected changed qualifiers and P(qualify). | Novelty of top-k evaluation. |
| The Annual Computer Poker Competition literature, e.g. Bard, N., Hawkin, J., Rubin, J. & Zinkevich, M. (2013), *The Annual Computer Poker Competition*, AI Magazine 34(2), 112–114, doi:10.1609/aimag.v34i2.2474 | **Duplicate poker** is established computer-poker methodology, including multiplayer events that duplicate cards with cyclic seat rotation. **Experiment D** asks a different question: whether *whole persistent-match* duplication improves *qualifier reliability per unit of actual simulator work*. | That duplicate poker, or multiplayer seat/card duplication, is new. |
| Davidson, Archibald & Bowling (2013), *Baseline: Practical Control Variates for Agent Evaluation in Zero-Sum Domains*, AAMAS 2013 | Together with AIVAT, the general problem of extracting more information per simulated hand. | — |
| Burch, Schmid, Moravčík, Morrill & Bowling (2018), *AIVAT: A New Variance Reduction Technique for Agent Evaluation in Imperfect Information Games*, AAAI 32(1), doi:10.1609/aaai.v32i1.11481 | FHR #3 studied estimator-level variance reduction. FHR #4 asks whether better *evaluation design* improves the competition's actual *selection outcome*. | — |

## Reference rankings (estimated diagnostics, never scores)

Both references are **finite-sample estimates**, not oracle labels. Neither is universal poker
skill.

* **`mu_field`**: long-run expected performance against random partitions of the controlled
  field under the specified match semantics.
  * Estimated by matched evaluation: six whole-match duplicate lanes, 400 hands per lane,
    cyclic seats and common chance streams.
  * Tables are random field partitions, independent of Swiss standings.
  * Reported on the ordinary-match-equivalent scale (lane sum / 6).
  * **Analytic SE is primary** (sd / √rounds per bot).
  * **Bootstrap unit: one complete matched round.** All 250 rounds are resampled jointly across
    the whole 60-bot vector, with one weight vector per resample, which keeps within-round
    covariance and the zero-sum structure. That gives 250 units rather than 25 blocks. Rounds
    are independent by construction (keyed partitions, decks and decisions; stateless agents;
    fresh stacks). The 2,000-round NLHE6 pool calibration shows no serial dependence:
    * lag-1 autocorrelation 0.004, inside the ±0.0046 band;
    * 10-round block variance ratio 1.00.

    The 10-round chunk is a storage unit only.
  * The joint resamples feed the ranking, gap, top-6 and reference-uncertainty diagnostics.
  * Common random numbers couple the three field references; they are not independent
    replications.
  * 250 matched rounds per field initially, extendable to 500 without repeating the first 250.
* **`mu_swiss`**: long-run expected outcome under the specified adaptive Swiss mechanism,
  estimated from **100 complete tournaments per field** in the separate `swiss-reference`
  namespace. Extending a field to 200 appends tournaments 100–199. Primary reference outputs:
  * per-bot P(qualify) with Wilson intervals;
  * expected final score, total and per match, with SE;
  * expected top-6 overlap against `mu_field` (and, flagged as in-sample, against `mu_swiss`);
  * rank and top-6 uncertainty: a joint tournament bootstrap giving rank intervals,
    P(in the `mu_swiss` top 6) and P(same top-6 set);
  * the boundary bots whose qualification remains materially ambiguous.

  In `crowded_cutoff` and `style_diverse` the rank-6/rank-7 ordering is not expected to become
  clean. That ambiguity is part of the experimental object.

**Interpretation.**

* **Disagreement between the references** is scientifically interesting: multiplayer,
  non-transitive games need not admit one context-free scalar ranking.
* **Accuracy against `mu_swiss`** measures convergence, repeatability and how well a finite
  tournament approximates the Swiss mechanism; it is not independent normative fairness.

### Reference uncertainty

The paper keeps two things apart: **disagreement with a reference point estimate**, and
**uncertainty in the reference itself**.

* **Operational summaries** use the point-estimate ranking.
* **Reference-propagated intervals.** Every reference-based metric also has a
  `*_ref_propagated` interval. Bootstrap draw b pairs tournament weights b with joint reference
  resample b, so the interval includes the reference's own uncertainty.
* **Reference-uncertainty summaries.** Per field and reference, the analysis reports:
  * P(same top-6 set);
  * P(rank-6/7 reversal);
  * the **reference-ambiguous set**: bots with 5% < P(reference top 6) < 95%;
  * `reference_self_regret`: the regret of the reference's own point top 6 under its resamples,
    i.e. the regret floor due to reference uncertainty alone.
* **`crowded_cutoff`.** No unique "true top 6" is manufactured. Swaps inside the
  reference-ambiguous set are separated from **clear** errors:
  * `clear_misqualifications`: qualifiers the reference excludes with P > 95%;
  * `clear_omissions`: bots the reference includes with P > 95% that did not qualify.

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

### A. Rounds to reliability

Reliability at 5, 10, 20, 30 and 40 rounds, read as exact prefixes of the same 40-round
trajectories.

### B. Fixed scheduled hand budget

10 × 1600, 20 × 800 and 40 × 400 hands per bot have an **equal maximum (scheduled) hand
budget**. They do **not** have equal actual simulator compute: longer matches end early more
often (busts), and hands cost different amounts as tables shrink. The question is:

> Given the same maximum scheduled poker budget, should simulation be allocated across more
> Swiss opponents or longer matches?

Reported for each allocation:

1. reliability at the scheduled hand budget (primary);
2. actual hands played per tournament;
3. recorded simulator wall-clock per tournament;
4. reliability relative to actual simulated work, as a secondary efficiency view.

Actual compute is not claimed to be held fixed.

### C. Adaptive Swiss vs exogenous replay of its schedules

* An adaptive source tournament (baseline replicate r) generates a realised schedule.
* That schedule is replayed **exogenously** with fresh poker randomness (new cards and
  decisions).
* Replay outcomes cannot feed back into later pairings.

The adaptive/frozen comparison therefore compares adaptive Swiss against exogenous replay of
schedules generated by the adaptive process. Three things limit what it can show:

* fresh poker randomness contributes noise to the paired contrast;
* each frozen schedule was itself generated by an adaptive source trajectory;
* it is not an identical-randomness pair.

So this is a targeted counterfactual comparison, not a complete causal decomposition, and it
does not cleanly identify an effect of Swiss feedback. The frozen schedule is not a proposed
format.

**Pairing and replays.** The initial core uses **J = 1**, and the analysis pairs each adaptive
baseline tournament with its frozen replay by source tournament. J > 1 is a later precision
extension (a new cell); uncertainty is then clustered by source tournament, so several replays
of one source are never treated as independent observations.

### D. Alternative evaluation packages: ordinary vs whole-match duplicate

Experiment D is an operational comparison between alternative equal-ish-budget evaluation
packages:

* ordinary 40 × 400;
* duplicate 7 × 400 × 6, with fewer Swiss rounds;
* duplicate 40 × 67 × 6, with shorter matches.

It uses the existing whole-match duplicate implementation:

* six lanes;
* the same initial stacks and chance stream in every lane;
* cyclic seats;
* independent stacks and bot state per lane;
* aggregation only after all lanes finish.

Each duplicate arm also changes either the number of Swiss rounds or the match length. The
contrast is therefore not the isolated effect of turning duplicate play on. The question is:

> Does whole-match duplicate evaluation provide better qualifier reliability per simulator
> work under practical budget-preserving redesigns?

**Work accounting.** Scheduled work ratio, actual hands played, recorded simulator wall-clock,
qualification reliability and qualification regret are all reported.

**Measured duplicate diagnostic** (the `mu_field` reference, 2026-10-02;
`reports/fhr3b/field-calibration/nlhe6/MU_FIELD_AUDIT.md`). This is a scientific diagnostic, not
an implementation failure:

* six-lane duplicate precision is about 0.98 of six independent ordinary matches;
* all comparable lanes share identical boards, as intended;
* about 60% of bot-lanes bust;
* trajectories diverge within the first few hands, so little card-luck variance cancels.

Experiment D tests whether this carries through to qualifier reliability under practical
tournament redesigns.

**The fewer-rounds arm.** It is deliberately **7 × 400 × 6**, which is +5% scheduled work and
flagged as a 1.05 ratio. It is not 7 × 381, because the arm keeps the standard 400-hand match
object. Any per-compute comparison is made explicit from the recorded work.

## Metrics

**Primary (qualification; these dominate).** Every primary tournament analysis reports both
kinds of error.

* **Identity error:**
  * expected number of changed qualifiers between reruns;
  * expected top-6 overlap;
  * per-bot P(qualify);
  * number of bots with ambiguous qualification (P(qualify) in [0.1, 0.9]);
  * changed qualifiers against the reference point top 6.
* **Strength error** (against `mu_field`, and against `mu_swiss` where available; in BB per
  ordinary-equivalent 400-hand match):
  * **qualification regret** = Σ_{i ∈ Q*} μ_i − Σ_{i ∈ Q} μ_i, where Q* is the reference-optimal
    set of 6;
  * **boundary strength loss** = max(0, max_{j ∉ Q} μ_j − min_{i ∈ Q} μ_i), the reference-strength
    advantage of the strongest omitted bot over the weakest qualifier.

  Strength error separates harmless swaps among nearly equivalent agents (regret ≈ 0) from
  materially weak qualification mistakes.

**Supporting:**

* rank-6/rank-7 gap and inversion uncertainty;
* Kendall tau;
* Spearman correlation;
* mean absolute rank displacement;
* pairwise inversion against the reference strength gap.

**Paired contrasts** (B, C, D against the adaptive 40 × 400 baseline, `contrasts.csv`) report
arm-minus-baseline differences with shared bootstrap weights. All uncertainty is computed over
tournaments (C: over source tournaments). Hands, matches and rounds are never replicates.

## Adaptive compute policy and pre-registered extension rules

This is **precision-driven compute allocation**, not "run everything until significance".

* **Initial budgets:** every unique cell starts at 50 complete tournaments, every field reference
  at 250 matched rounds, and `mu_swiss` at 100 tournaments per field.
* **Long horizons** (60/80/120 rounds) run only for fields whose qualification metrics have not
  stabilised by 40 rounds.
* **Extensions** are explicit, logged and append-only. No preset launches 100, 200 or 500
  tournaments.

The extension rules below were **pre-registered on 2026-10-01**, before any publication result
existed. They live in `configs/fhr3b/matrix.yaml: core_fhr4.extension_rules`, are evaluated
automatically into `reference.json` and `summary.json → extension_rules`, and are never executed
automatically.

**`mu_field` 250 → 500 rounds.** The criteria come from the joint round bootstrap.

| field | extend to 500 if either holds |
|---|---|
| `spread` | P(same top-6 set) < 0.95, or P(rank-6/7 reversal) > 0.05 |
| `crowded_cutoff` | any of the 3 designed leaders (manifest `top_ids`) has P(top-6) < 0.95, or any bot in **neither** the designed leaders **nor** the designed ranks-4–15 crowd (manifest `crowd_ids`) has P(top-6) > 0.10 |
| `style_diverse` | any point-rank 1–4 bot has P(top-6) < 0.90, or any point-rank ≥ 10 bot has P(top-6) > 0.10 |

The `crowded_cutoff` rule is defined on the manifest structure, not on numeric ranks. "Outside"
means outside both designed sets; a literal "outside ranks 4–15" would wrongly include the three
leaders. Reordering inside the designed crowd, or an unstable top-6 identity, is never a reason to
extend.

**Main matrix 50 → 100 tournaments, per unique cell.** Flag a cell if either holds:

* the 95% Monte Carlo CI half-width of expected changed qualifiers or expected top-6 overlap is
  above 0.30;
* a paired contrast it takes part in has a CI spanning both −0.25 and +0.25 qualifiers.

Qualification regret stays a primary reported, strength-sensitive diagnostic and may affect
interpretation. It never independently triggers a compute extension: no common absolute BB/match
tolerance is defensible across `spread`, `crowded_cutoff` and `style_diverse`. Only the
flagged cells are extended, never every cell. Extensions append replicates 50–99 and leave the
first 50 byte-for-byte unchanged.

**`mu_swiss` 100 → 200 tournaments, per field.** Extend a field if either holds:

* a decision-relevant boundary bot (P(qualify) in [0.10, 0.90]) has a 95% Wilson half-width
  above **0.08**. In `crowded_cutoff`, the designed near-equal crowd is not decision-relevant for
  this rule.
* reference uncertainty prevents interpretation of the main results. This is a reviewed
  judgement, and its reason is recorded.

**Threshold correction.** The threshold was corrected from 0.10 to 0.08 on 2026-10-01, before
any run. At n = 100 the largest possible Wilson half-width is 0.096, so 0.10 could never fire.

* At 0.08 the clause fires for estimated P(qualify) in about [0.22, 0.78].
* It does not force extension for probabilities already near 0 or 1.
* At n = 200 (maximum 0.069) it cannot fire again.

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
| `spread` | broad strength distribution with a separated rank-6/rank-7 boundary. The 2026-10-01 field (`ff0f2b07fc210f62`) is **retired** (`retired_spread_selection_bias`) and on HOLD at 250 rounds: its 16.8 BB pool gap was 0.71 BB under the independent reference. A replacement is selected and validated on disjoint halves of the pool calibration (`core_fhr4.spread_v2`); see `docs/fhr3b/FHR4_CORE.md` |
| `crowded_cutoff` | several genuinely similar bots, of different strategies, straddling the boundary |
| `style_diverse` | deliberate balance of observed style across strength strata |

**Strategic diversity.** `reports/fhr3b/field-calibration/nlhe6/field_diversity.md` comes from the
frozen manifests, the behaviour audit and the pool ranking, with no simulation. Every field has
60 distinct parameter vectors, 8 archetypes and all four observed styles.

* `spread` and `style_diverse` have no near-duplicate pairs.
* `crowded_cutoff` has 22 near-duplicate pairs overall, but its ranks 4–15 (exactly the designed
  crowd) span 7 archetypes and all four styles, with only 3 near-duplicate pairs among 4 of the
  12 bots. The boundary is not clone-driven.

The synthetic agents are strategically heterogeneous, but not all 60 are qualitatively unique.

Non-transitive (matchup) structure is **measured, never selected on**. The former
`matchup_sensitive` field and its gate are retired.

The bots are synthetic experimental instruments: transparent, stateless FHR3 policy families.
For NLHE, the study uses `fhr3b_heuristic`, the FHR3A heuristic with correct heads-up blind
roles. The FHR3A family misread heads-up roles, which persistent-stack busts make common
(23–53% of hands). The bots are not models of human professionals. Selection rules and the
realism audit are in `docs/fhr3b/FIELDS.md` and
`reports/fhr3b/field-calibration/FIELD_CALIBRATION_REVIEW.md`.

## Limitations and caveats every write-up must state

* **One field per regime.** There is one frozen field per constructed regime: one `spread`, one
  `crowded_cutoff` and one `style_diverse`.
  * Tournament repetitions are repeated stochastic runs **CONDITIONAL** on those fields. They are
    not independent replications of the field regime.
  * No regime-level inferential test treats 50 tournaments as 50 independent crowded fields.
  * No universal claim (e.g. "crowded fields require X rounds"). Use wording such as "in our
    constructed crowded-cutoff stress test …" or "across the three controlled field scenarios …".
* **Estimated references.** `mu_field` and `mu_swiss` are estimated quantities (see "Reference
  uncertainty"), not oracle labels.

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
