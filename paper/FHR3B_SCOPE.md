# FHR3B scope

**Research question.** How much play does a Swiss-style adversarial poker competition need
before its leaderboard, and especially its qualification boundary, becomes reliable?

1. **Object of study.** FHR3B studies the reliability of whole-field Swiss rankings: bots play
   at tables, raw outcomes build cumulative standings, standings decide the next pairings, and
   the final leaderboard decides a top-K qualification cut. It is not a pairwise
   candidate-versus-reference benchmark.
2. **Unit.** One independent observation is one complete tournament replication. Hands, table
   matches and rounds are never treated as independent replicates. All uncertainty is
   computed over tournaments (or, for the schedule diagnostic, over independent source
   schedules).
3. **Primary notion of reliability: repeatability.** If the same field replayed the same
   protocol under fresh randomness, how similar would the leaderboard and the qualifying set
   be? The measures are:
   * expected top-K overlap and changed qualifiers between independent reruns;
   * per-bot P(qualify);
   * rank correlations and mean absolute rank change;
   * cutoff curves;
   * pairwise inversion rates.

   No "true ranking" is needed for the primary result.
4. **Diagnostics, not production scores.** FHR3B reports two long-run references:
   * balanced field EV (`mu_field`);
   * expected Swiss performance (`mu_swiss`).

   Neither is a production score, and neither is assumed to be "the true ranking". If their
   orderings differ, the Swiss system rewards field, path or matchup structure beyond
   balanced EV, and that difference is reported as a finding.
5. **Baseline scoring.** Raw FullHouse tournament scoring (cumulative chip delta with the 2026
   tiebreaks) remains the baseline and the only ranking rule.
6. **Out of scope:**
   * opponent-strength-adjusted scoring, and Elo-type or latent-strength ranking;
   * variance-reduced tournament scoring (all-in EV, MIVAT, AIVAT);
   * confidence-aware qualification rules;
   * replacing Swiss with a fixed-reference benchmark.
7. **Frozen schedule is research-only.** The frozen-schedule replay is a counterfactual
   diagnostic of path dependence. It is not a proposed competition format, and its contrast
   with adaptive Swiss is not an additive variance decomposition.
8. **The 60-bot / top-6 lab is a controlled environment.** `lab60_top6` is not a proposed or
   future FullHouse rule. It was chosen because 60 divides into 4-max and 6-max tables and
   top 6 is a 10% cut.
9. **2026 operational validation is separate, and pending.** The exact 2026 production code
   was not recoverable. The baseline is `reconstructed_2026` from the public canonical engine
   (`mbatv/fullhouse-engine@a80b269`); see `docs/fhr3b/2026_protocol_audit.md`. The actual
   2026 field size, round count and qualifier structure are unverified, so the operational
   configuration is pending and is not run.
10. **FHR3A stays separate.** FHR3A is a separate empirical note about the anatomy of
    evaluation noise in matched pairwise comparisons. FHR3B does not change FHR3A's
    manuscript, figures F1–F6, claims or publication corpora.

**Caveats that must be stated in any write-up:**

* The bots are synthetic, stateless FHR3 agents. Real 2026 bots could adapt to opponents
  within a match.
* Match rules differ between the mode groups (persistent stacks for NLHE, PLO and CP; per-hand
  reset for AoF, bomb pot and Nit). Cross-mode results compare whole formats.
* R0 = 40 is provisional until the organisers confirm it.
* Numbers are conditional on the constructed fields.
