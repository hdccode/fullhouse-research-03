# FullHouse Research #4: manuscript skeleton (frozen evidence, `db45b56`)

Status: outline only, not full prose. All numbers come from stored analysis outputs
(`reports/fhr3b/analysis-fhr4-core/`). No simulation has run since the freeze. Figures and tables:
`paper/fhr4/figures/`, `paper/fhr4/TABLES.md`.

**Ownership note.**

* The final title and introduction are writer-owned; this file proposes no title and contains no introduction text.
* The abstract scaffold below is retained because it summarises the frozen study design and principal results, but it
  is not final manuscript prose.

**Research question.** How should a finite poker-bot simulation budget be allocated so that a Swiss
tournament reliably identifies the strongest agents?

## Results-grounded abstract scaffold

Not final manuscript prose: a structured summary of the frozen design and principal results for the writer to work from.

* **Setting.** Six-player no-limit hold'em Swiss tournaments for synthetic poker bots: 60 bots, top 6
  qualify, persistent-stack 400-hand matches. There are three controlled fields:
  * an engineered separated control;
  * a crowded-cutoff stress test;
  * a style-diverse field.

  Selection is scored against a mu_field reference (random-partition duplicate matches, independent
  seeds) and a mu_swiss reference (200 adaptive tournaments).
* **Main result.** At 40 rounds of 400 hands, top-6 selection is dominated by poker variance in these
  controlled fields:
  * independent reruns disagree on 3.8 to 4.4 of 6 qualifiers;
  * 2.7 to 3.8 qualifiers are outside the mu_field reference top 6;
  * in the separated control, each of six independently validated leaders qualifies with probability
    0.31 to 0.76, and the exact top 6 was selected in 2 of 250 tournaments.
* **Rounds.** Reliability improves continuously with rounds, with no evidence of a plateau within the
  preregistered 40-round horizon.
* **Budget allocation.** At an equal scheduled hand budget, more rounds beat longer matches. Ten
  1,600-hand rounds are worse than forty 400-hand rounds in all three fields, partly beyond the
  difference in hands actually played.
* **Adaptation and duplication.** Adaptive Swiss outperforms a frozen replay of its own realised schedule
  (a source-schedule counterfactual). Whole-match duplication helps consistently only in the short-match
  package, consistent with duplicate lanes staying coupled when busts are rare.
* **Error type and references.** Most selection errors are genuinely weaker entrants, not swaps among
  near-equals. Reference uncertainty is small next to tournament noise, and the mu_field and mu_swiss
  references agree (Spearman 0.97 to 0.98).

## Section structure

1. **Introduction.**
   * Selection reliability as a budget-allocation problem.
   * Top-k recovery rather than whole-ranking correlation.
   * Narrow novelty claim: the intersection of tournament design and poker-agent evaluation.
2. **Related work.**
   * Tournament design as allocation of comparison resources under noise (Sziklai, Biró and Csató 2022).
   * Swiss tournaments and partial-ranking recovery (Hua 2017).
   * Duplicate evaluation in the Annual Computer Poker Competition (Bard et al. 2013).
   * Variance reduction for agent evaluation (Davidson et al. 2013; Burch et al. 2018).
   * We do not claim novelty for Swiss pairing, top-k metrics, common random numbers or duplicate poker.
3. **Setting and design.**
   1. Tournament mechanism: public-2026-style research semantics, persistent stacks, raw chip-delta
      scoring, public tiebreaks. These are research choices: N = 60, K = 6, 40 rounds x 400 hands.
   2. Controlled fields and agents (Table 1; field-diversity appendix table).
   3. Reference strengths:
      * mu_field: matched duplicate random partitions, joint round bootstrap;
      * mu_swiss: 200 adaptive tournaments;
      * reference uncertainty and its propagation.
   4. Experiments:
      * A: round prefixes;
      * B: allocation at an equal scheduled hand budget;
      * C: source-schedule counterfactual;
      * D: operational duplicate packages.
   5. Metrics. Identity error: rerun changed qualifiers, top-6 overlap, wrong qualifiers vs reference.
      Strength error: qualification regret, boundary strength loss.
   6. Preregistration, extension rules, the simulation freeze, and the replicate counts actually used.
4. **Results.**
   * 4.1 Baseline reliability (Table 2, Figure 5).
   * 4.2 Rounds to reliability (Figure 1).
   * 4.3 Rounds versus match length (Figure 2, Table 3).
   * 4.4 Adaptive versus frozen schedules (Figure 3).
   * 4.5 Duplicate packages (Figure 4).
   * 4.6 Error type and reference robustness (Figure S1; reference agreement).
5. **Discussion.**
   * Implications for running competitions in these controlled fields.
   * What would and would not transfer to other fields.
   * Why duplication helps only when lanes stay coupled.
6. **Limitations.**
7. **Conclusion.**

Appendices:

* A. Field construction and validation history.
* B. Reference-estimation details and integrity checks.
* C. Extension rules and their outcomes.
* D. Field-diversity table.
* E. Per-bot qualification probabilities.

## Methods and provenance notes (appendix material, not headline results)

* **Original `spread` field.** Selected for a large rank-6/7 gap (16.8 BB) using the same noisy
  pool-calibration estimates that measured the gap. Under the independent field-relative mu_field
  reference the gap was 0.71 BB. This is regression to the mean from selection bias, not an estimator
  failure. The field was retired with provenance kept.
* **`spread_v2`.** A split-sample replacement, selected on even pool rounds and validated once on odd
  rounds. It failed its held-out validation: P(leaders are the top 6) 0.208, against 0.95 required. No
  second attempt was made on that split.
* **`separated_control`.**
  * Construction: built once from the 2,000 existing pool rounds (the strongest defensible six plus the
    54 weakest bots), and frozen before any validation data existed.
  * Validation: passed a one-shot independent validation on 4,000 fresh pool-style rounds, under a seed
    family never used elsewhere. P(leaders are the top 6) was 0.998; the gap was 12.4 BB, with a
    one-sided 95% lower bound of 4.4 BB.
  * Reference: its mu_field reference was generated independently afterwards (250 matched rounds; the
    pre-registered rule did not fire).
* **Field scope.** One frozen field per scenario. Results are conditional on these three controlled
  fields: no regime-level inference.
* **Agents.** Synthetic, stateless rule-based policy families. Within-match opponent modelling is
  under-represented.
* **Semantics.** Public-2026-style research semantics, not exact production historical settings. The
  paper makes no statement about any future (2027) competition format.
* **Pre-registered rule clarifications.** The decisions were made before any extension ran:
  * matrix clause 2 is governed by rerun changed qualifiers, with wrong-vs-reference contrasts reported
    as a sensitivity;
  * contrasts are paired per pair of cells;
  * longer horizons (60/80/120 rounds) are future work.

## Limitations to state

* One field per scenario. The engineered separated control is not representative of any natural field.
* Synthetic stateless agents.
* Validation of the separated control in pool context (it was later confirmed field-relative).
* Experiment C is a targeted counterfactual, not a causal decomposition. Experiment D compares packages,
  not an isolated effect of duplication.
* CPU-time ratios are indicative only (machine throttling). Work is measured in scheduled and played
  hands.
* The crowded-cutoff reference ambiguity extends past the designed crowd (one bot outside it has
  P(reference top 6) = 0.21 at the 500-round ceiling).
* Within-tournament budget only. Nothing beyond 40 rounds is inferred.

## Visualisation cautions (keep in captions and text)

* **Figure 1(b).** The separated control has the highest regret despite the fewest wrong qualifiers.
  Each of its misses costs more because its leaders are far stronger. Read panel (a) for counts.
* **Figure 2.** The matched-played-hands rows differ by metric: R10 is clearly worse in the separated
  control on both metrics, in the style-diverse field on regret only (its changed-qualifier interval
  just includes zero), and inconclusive in the crowded-cutoff field. Do not summarise this as "R10 is
  worse at equal played hands everywhere".
* **Figure 4.** The "short duplicate is more consistent" reading rests on direction across all three
  fields and on rerun rank correlation (panel b). Changed-qualifier contrasts are individually clear only
  in the separated control. In the crowded-cutoff field the long-lane duplicate has the largest single
  improvement.
* **Figure 5.** The 50-tournament baseline diamonds have intervals about twice as wide as the mu_swiss
  points. Individual baseline deviations (for example nit-e3-s1 in the separated control: 0.38 vs 0.59)
  are within that noise.
* **Regret across fields.** Regret is in BB per 400-hand match summed over six qualifiers. It is
  comparable within a field across conditions, but between fields it also reflects each field's strength
  spread.
