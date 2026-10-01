# FHR3B fields

## Principle

No bot has a "skill" label. FHR3B builds a **candidate pool**, measures long-run balanced
performance and play style **empirically**, and selects fields from those measurements with
deterministic rules:

```text
candidate pool -> balanced calibration -> behaviour audit (exact replay) -> deterministic selection -> frozen manifest
```

Publication modes: **AoF4, NLHE4, NLHE6**. PLO is not part of FHR3B; `plo6` pool files remain
only as generic engine support.

## Candidate pools (`configs/fhr3b/fields/<mode>/pool.json`, 96 bots per mode, frozen)

A pool crosses:

* **archetypes** (8):
  * NLHE: `neutral, tight, loose, aggressive, nit, station, maniac, trapper`;
  * AoF: four heuristic styles, `shover`, `caller`, the production policy v2 (`policy`), and a
    loose-blended policy;
* **perturbation scale** `e0..e3` (ε = 0, 0.10, 0.25, 0.45): multiplicative or additive
  perturbations of every parameter, bounded to valid ranges;
* **agent seeds**: 1 / 3 / 4 / 4 per scale, from
  `KeyedStream("fhr3b-agent-construction", seed_family, family, archetype, scale, seed, param)`.

**NLHE agent family: `fhr3b_heuristic`** (`src/fhr3/tournament/agents.py`). This is the FHR3A
`heuristic` policy with corrected heads-up blind roles: the button/SB acts first and opens with
the small-blind range, and the BB defends with `bb_defend_pct`. Multiway decisions are
identical to FHR3A's (tested), and FHR3A code is untouched. The previous FHR3A-heuristic NLHE
pools, calibrations and fields are retired (`configs/fhr3b/fields/retired/hu-role-bug/`).

**NLHE4 and NLHE6 share their 96 parameter vectors (decision D4, locked).** This is
intentional: the same candidate policies are calibrated independently in 4-max and 6-max,
which gives a clean controlled format comparison. NLHE4 reuses no NLHE6 calibration or field.

Archetype labels are construction labels. **At e2/e3 many bots drift out of their archetype's
play style** (measured). Selection therefore balances *observed* style, with archetype as a
secondary constraint.

## Balanced calibration (`calibration.py`)

A calibration round is a keyed random partition of the pool into tables of the mode's size.
Every table plays one match under the research match rule (400 hands; NLHE carried stacks;
AoF 8 BB reset).

* `mu_field(i)`: mean chip delta per match at a random table. For selection its SE is the
  analytic `sd / sqrt(matches)`, which does not depend on bootstrap draws.
* Presence-effect matchup flow: `M[i,j] = E[delta_i | j at table] − mu_i`. It is used only for
  *measurement* (split-half reliability, archetype cycle test).

Stages:

1. **Pool calibration.** Namespace `pool-calibration`, 2,000 rounds.
2. **Field reference.** Namespace `field-reference`, inside each frozen field. Matched (k-lane
   duplicate) play at 3,000 ordinary-equivalent rounds: 750 × 4 lanes (AoF4/NLHE4), 500 × 6 lanes
   (NLHE6). Reported `mu_field = mean(lane_sum) / k` (ordinary-match scale; raw
   `mu_field_lane_sum` kept). Primary SE analytic; joint round-group bootstrap (10-round groups)
   for ranking/gap robustness only. Per-lane outcomes persisted and validated. All field
   references share one seed (common random numbers): cross-field estimates are correlated.
   Plan: `FIELD_REFERENCE_PLAN.md`.

## Behaviour audit (`behaviour.py`, `fhr3b behaviour-audit`)

The first 20 calibration rounds are replayed exactly, with logging proxies around the agents.
Every replayed match must equal the stored deltas. Recorded per bot:

* VPIP, PFR and 3-bet;
* fold-to-bet and aggression;
* all-in propensity and the hand strength of all-ins;
* VPIP by position and by stack depth;
* AoF shove and call rates;
* winnings: showdown vs uncontested.

**Style classes** use the classic four-way taxonomy, with thresholds at the pool medians:

| mode | axes | classes |
|---|---|---|
| NLHE | VPIP × PFR/VPIP | TA / LA / TP / LP |
| AoF | call-vs-shove × open-shove | tight/loose caller × frequent/selective shover |

## Near-duplicates

A near-duplicate pair is one whose RMS distance between resolved, normalised parameter vectors
is **< 0.15** (log scale for positive parameters). That threshold is the ε = 0.10 sibling scale:
e0–e1 median 0.09–0.10, e1–e1 median 0.12–0.13.

## Selection v2 (`selection.py`; parameters in `configs/fhr3b/matrix.yaml`)

### spread

1. **Leaders.** Walk down the ranking; accept a bot only if it is not a near-duplicate of an
   accepted leader and at most 3 leaders share its archetype. Stop at K = 6.
2. **Gap constraint.** Every non-leader b must satisfy
   `mu_b ≤ mu_6 − g·sqrt(se_6² + se_b²)`. The selector seeks a 3 SE qualification gap subject to diversity and coverage constraints, relaxing the threshold only when the stronger requirement would materially degrade field diversity.
3. **Fill.** The other 54 bots come from 6 equal-count strength strata below the gap, with
   equal quotas. Each pick favours the least-represented style, then the least-represented
   archetype, then the largest parameter distance to bots already chosen. No near-duplicates;
   at most 10 per archetype.
4. **Relaxation.** If the whole constrained construction (zero near-duplicates, archetype cap,
   strata) is infeasible, g drops in 0.25 steps. The value used and the achieved gap are
   recorded.

3 SE is a target, not an absolute requirement. D1 accepted NLHE6 spread at 2.34 SE (12.2 BB; zero
near-duplicates; 0 bots within ±5 BB of the cut) rather than degrade diversity.

### crowded_cutoff

The rule is unchanged: 3 leaders, then the tightest 12-bot window straddling the cut (field
ranks 4–15), then evenly spaced fill. `selection.json → crowded_cutoff_diversity_audit`
records the strategic diversity of the leaders and of the cutoff cluster.

### style_diverse

Replaces `matchup_sensitive` permanently.

* Cells are observed style (4) × pool-strength quintile (5).
* An integer program (scipy/HiGHS, deterministic) fixes every stratum total at 12 and every
  style total at 15, minimising `Σ |x − 3|` subject to what the pool can supply.
* Within each cell the pick balances archetype and parameter distance, with no near-duplicates.
* If a cell is blocked, a documented fallback takes the nearest-strength eligible substitute.
* Style–strength association is reported (η²).

## Frozen fields (2026-09-30)

`configs/fhr3b/fields/FROZEN.yaml` is the authority. Publication and pilot runs refuse any
spread / crowded_cutoff / style_diverse manifest that is not listed there with a matching hash.

| mode | spread | crowded_cutoff | style_diverse |
|---|---|---|---|
| AoF4 | `db5912d65a47b215` | `b9709c10c5aef403` | `195ceda2edb24052` |
| NLHE6 | **pending re-calibration** (pool `a867bd18d6033233`) | pending | pending |
| NLHE4 | **pending re-calibration** (pool `c9b0ffb56855a62d`) | pending | pending |

The earlier NLHE6 freeze (`16df070d…`, `a845c2fc…`, `5c83ad42…`) and the NLHE4 candidates are
**revoked** because of the heads-up-role bug. They are listed under `revoked:` in `FROZEN.yaml`
and refused by publication and pilot runs even if someone re-lists them.

Caveats:

* **AoF4 style_diverse:** style and strength are partly confounded; the strongest pool quintile
  has no tight-aggressive bots.
* **AoF4 crowded_cutoff** (and the spread top six): the leaders are near-identical
  production-policy variants (D2 accepted). The cutoff cluster itself is strategically diverse.
* **NLHE6:** high bust rates are a property of the persistent-stack match rule, not pathology.

## Retired

* The `matchup_sensitive` field.
* Greedy cyclic-share selection (`calibration.select_matchup`, `subset_share_ci`: kept in the
  module for provenance, unused).
* The `matchup_gate`. Its "debiased cyclic share" could exceed 1, and the selected subsets did
  not replicate out of sample.

v1 candidates are kept under `reports/fhr3b/field-calibration/<mode>/retired_v1/`.
