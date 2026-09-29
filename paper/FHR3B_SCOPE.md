# FHR3B scope

FHR3B studies the reliability of a FullHouse-style adversarial Swiss evaluation system.

The public 2026 FullHouse engine provides the architectural provenance for the tournament
design. Incomplete production records make an exact historical reconstruction impossible.
The primary experiments therefore use a frozen, controlled research protocol,
**`fhr3b_baseline`**:

* 60 agents;
* top 6 qualify;
* 40 Swiss rounds;
* 400-hand matches;
* raw cumulative chip-delta scoring.

These parameters are research design choices. They are not claims about undocumented 2026
production settings.

## Three separate things

| | what it is | where |
|---|---|---|
| **Historical provenance** | `historical_2026_reconstruction`: what the public 2026 engine (`mbatv/fullhouse-engine@a80b269`) establishes, with every unknown left unknown. The 2026 qualifier's round count and field size are UNKNOWN. | `docs/fhr3b/2026_protocol_audit.md`, `configs/fhr3b/protocols/historical_2026_reconstruction.yaml` |
| **Controlled research experiment** | `fhr3b_baseline` in the `lab60_top6` environment. All primary results (A, B, C, `mu_field`, `mu_swiss`) come from it. | `configs/fhr3b/protocols/fhr3b_baseline.yaml`, `configs/fhr3b/lab/lab60_top6.yaml` |
| **Optional historical operational validation** | Experiment D. Blocked until the missing historical values are supplied from records; never filled with research choices. | `fhr3b run --experiment operational-2026` |

## Research question and experiments

The primary question: **how quickly does a FullHouse-style Swiss leaderboard, and especially
its qualification boundary, stabilise as more play is added?** It is not "how many rounds
did FullHouse 2026 need?".

* **A. Rounds.** Standings after 5, 10, 20, 30 and 40 rounds. These are exact prefixes of the
  40-round research-baseline tournaments.
* **B. Fixed poker volume.** Each bot plays the same number of hands, allocated as 10 × 1600,
  20 × 800 or 40 × 400. Is evaluation more reliable when that volume is spread over more
  Swiss opponents, or spent measuring each matchup more precisely?
* **C. Path dependence.** Adaptive Swiss against a research-only frozen-schedule
  counterfactual. This is a diagnostic of feedback amplification, not an additive variance
  decomposition and not a proposed format.

## Commitments

1. **Object of study.** Whole-field Swiss ranking reliability: bots at tables, raw outcomes,
   cumulative standings, standings-dependent pairing, final leaderboard, top-K cut. It is not
   a pairwise candidate-versus-reference benchmark.
2. **Unit.** One independent observation is one complete tournament. Hands, matches and
   rounds are never replicates. All uncertainty is computed over tournaments; for C it is
   computed over independent source schedules.
3. **Primary reliability notion: repeatability.** How similar are the leaderboard and the
   qualifying set when the same field replays the same protocol under fresh randomness? The
   measures are:
   * top-K overlap and changed qualifiers;
   * per-bot P(qualify);
   * rank correlations and mean absolute rank change;
   * cutoff curves;
   * pairwise inversions.

   No "true ranking" is required.
4. **References are diagnostics.** Balanced field EV (`mu_field`) and expected Swiss
   performance (`mu_swiss`) are research references, never production scores. Neither is
   assumed to be the true ranking. A difference between their orderings is reported as a
   finding.
5. **Scoring.** Raw cumulative chip delta with the public engine's tiebreaks is the only
   ranking rule.
6. **Not implemented:**
   * opponent-strength adjustment, Elo or latent-strength ranking;
   * variance-reduced scoring (all-in EV, MIVAT, AIVAT);
   * confidence-aware qualification;
   * a fixed-reference replacement for Swiss.
7. **`lab60_top6` is a controlled research environment,** not a proposed FullHouse format.
   N = 60 divides into 4-max and 6-max tables, so no remainder tables arise. K = 6 gives a
   ~10% qualification boundary.
8. **Why R0 = 40:**
   * clean prefixes at 5 / 10 / 20 / 30 / 40;
   * enough opponent exposure for the reliability curve;
   * a meaningful high-budget reference point;
   * the exact budget allocations of B;
   * computationally manageable.

   H0 = 400 retains the public engine's match length.
9. **FHR3A stays separate.** FHR3A is an empirical note on the anatomy of evaluation noise in
   matched pairwise comparisons. FHR3B changes none of its manuscript, figures F1–F6, claims
   or corpora.

## Caveats any write-up must state

* The bots are synthetic, stateless FHR3 agents. Real 2026 bots could adapt to opponents
  within a match.
* Poker uses FHR3's PokerKit adapters, not the 2026 engine. Rules differ in rare edge cases.
* Match rules differ by mode group: carried stacks for NLHE, PLO and CP; per-hand reset for
  AoF, bomb pot and Nit. Cross-mode results compare whole formats.
* All numbers are conditional on the constructed fields and on the research protocol.
  They say nothing directly about the 2026 event's reliability.
