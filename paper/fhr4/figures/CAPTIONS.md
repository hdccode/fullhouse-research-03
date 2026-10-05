# FHR #4 figure captions (draft)

These captions are shared by every figure:

* **Setting:** NLHE 6-max, 60 synthetic bots per field, top 6 qualify. Each Swiss round is one
  persistent-stack match per table.
* **Units:** qualification regret and boundary strength loss are in big blinds (BB) per
  ordinary-equivalent 400-hand match, against the mu_field reference point estimate.
* **Intervals:** all are 95% tournament-level bootstrap intervals unless stated otherwise.
* **Source data:** each figure's exact plotted values are in `figures/data/<figure>.csv`.

## Figure 1. Reliability of top-6 selection as Swiss rounds accumulate

Each field contributes 50 adaptive Swiss tournaments (40 rounds of 400-hand matches), evaluated after
5, 10, 20, 30 and 40 rounds as exact prefixes of the same tournaments.

* **(a)** Qualifiers outside the mu_field reference top 6.
* **(b)** Qualification regret: the summed mu_field strength of the reference-optimal six minus that
  of the selected six.

Reliability improved continuously through 40 rounds in all three controlled fields, with no evidence of
a plateau within the preregistered 40-round horizon. Nothing is implied beyond 40 rounds. Regret is
highest in the engineered separated control because each miss there replaces a validated leader with a
much weaker bot, not because that field has more misses (panel a).

## Figure 2. Rounds versus match length at an equal scheduled hand budget

Three allocations give every bot the same 16,000 scheduled hands: 10 rounds of 1,600 hands, 20 rounds of
800, and 40 rounds of 400. Stacks persist within a match, so longer matches end earlier more often. The
allocations played 57%, 80% and 94% of their scheduled hands, so only the scheduled (maximum) hand
budget is equal.

* **(a, b)** Rerun changed qualifiers (between independent tournaments) and qualification regret, with
  50 tournaments per allocation and field.
* **(c, d)** Paired contrasts on the replicate ids shared by the two cells compared. Positive values mean
  the first allocation is worse. The last row in each field compares the 10-round allocation with the
  prefix of the 40-round tournaments that played the same number of hands (25 rounds; 23 in the
  style-diverse field).

**Results:**

* Ten long matches did worse than forty standard matches in all three controlled fields, on both
  metrics.
* Twenty rounds of 800 hands were close to forty rounds of 400. The exception is the style-diverse
  field, which was slightly worse on changed qualifiers.
* At equal played hands, the 10-round allocation remained worse:
  * in the separated control on both metrics;
  * in the style-diverse field on regret (its changed-qualifier interval just includes zero);
  * in the crowded-cutoff field the matched comparison is inconclusive.

## Figure 3. Adaptive Swiss versus a frozen replay of its realised schedule

Each of the 50 adaptive 40-round tournaments per field generated a realised table schedule. That schedule
was then replayed once with fresh poker randomness and without result feedback, so replay outcomes could
not change later pairings. The values shown are adaptive minus frozen, paired by source tournament, for
rerun changed qualifiers (a) and qualification regret (b). Negative values favour adaptive pairing.

In this source-schedule counterfactual, adaptive Swiss selected more reliably in all three controlled
fields. The regret interval for the style-diverse field just includes zero.

This is not a clean causal estimate of the effect of Swiss adaptation:

* the frozen schedules were themselves produced by adaptive trajectories;
* the fresh poker randomness adds noise to the paired contrast.

## Figure 4. Duplicate tournament packages

This is an operational package comparison of:

* ordinary 40-round tournaments of 400-hand matches;
* six-lane whole-match duplicate tournaments with fewer rounds (7 rounds of 400 hands);
* six-lane whole-match duplicate tournaments with shorter matches (40 rounds of 67 hands).

Scheduled work is 1.000, 1.050 and 1.005 times the ordinary package. The duplicate packages played
about 1.05 and 1.07 times the ordinary package's actual hands.

* **(a)** Rerun changed qualifiers.
* **(b)** Rank correlation between independent reruns (Spearman).
* **(c, d)** Paired contrasts for changed qualifiers and regret. Negative values mean the first package
  is better.

**Results:**

* The short-match duplicate package gave the highest rerun rank correlation in every field. Its
  changed-qualifier contrasts against ordinary play are all negative, and individually clear in the
  separated control.
* The long-lane duplicate package helped only in the crowded-cutoff field.

**Mechanism.** In 400-hand persistent matches, about 60% of bot-lanes bust and duplicate trajectories
diverge within the first hands, so little card luck cancels. In 67-hand lanes busts are rare (played hands
equal scheduled hands), so lanes stay coupled.

These are comparisons of practical packages that also change rounds or match length. They do not identify
a pure effect of duplication.

## Figure 5. Qualification probability at the cutoff

Each point is the probability of qualifying in a 40-round adaptive Swiss tournament of 400-hand matches,
from the 200-tournament mu_swiss reference, with Wilson 95% intervals. Grey diamonds show the 50-tournament
matrix baseline, an independent replication; its own intervals are about twice as wide. Bots are ordered by
mu_field reference rank. Filled markers are the mu_field reference top 6, and the dotted line is the uniform
share of 6 in 60.

* **(a)** The engineered separated control has six independently validated leaders, 23.8 BB per match
  above the next bot under the mu_field reference. Each leader still qualifies with probability only
  0.31 to 0.76. In 250 adaptive tournaments of this field (matrix baseline and mu_swiss), the selected six
  matched the reference six only twice.
* **(b, c)** After the strongest two or three bots, qualification probability is flat at about 0.15 to
  0.25 across many bots, on both sides of the reference boundary.

## Supplementary Figure S1. Identity errors versus strength errors

Data: 250 adaptive tournaments per field (40 rounds of 400 hands; the 50-tournament matrix baseline plus
the 200-tournament mu_swiss reference).

* **(a to c)** Qualification regret against the number of wrong qualifiers relative to the mu_field
  reference, one point per tournament with horizontal jitter. Black bars are means.
* **(d)** Share of wrong qualifiers outside the mu_field reference-ambiguous set (bots whose reference top-6
  membership is settled: probability below 5% or above 95%).

Regret grows with the number of wrong qualifiers in every field (correlation 0.79 to 0.90). Each wrong
qualifier costs on average about 44 BB per match in the separated control and about 25 BB in the other two
fields. About 80% of wrong qualifiers in the crowded-cutoff and style-diverse fields, and all of them in the
separated control, are bots the reference clearly places outside the top 6. Most selection errors are
therefore genuinely weaker entrants rather than swaps among near-equals.
