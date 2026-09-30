# FHR3B field-calibration review, selection v2 (locked design)

Status: **review package; nothing committed; no field frozen.** Date: 2026-09-30. Supersedes the
v1 review; v1 candidates are under `<mode>/retired_v1/`.

All values are balanced field EV in BB per 400-hand match. They come from the pool calibration
under `fhr3b_baseline`, whose N = 60, K = 6, H0 = 400 and 40-round *initial* horizon are research
design choices, not 2026 FullHouse settings. Publication modes are AoF4, NLHE4 and NLHE6; PLO is
out of FHR3B. NLHE4 is **not yet calibrated**, and no conclusion here concerns it.

## Decisions locked by Henry (2026-09-30)

| decision | outcome |
|---|---|
| D1 | NLHE6 spread **accepted and frozen** at 2.34 SE / 12.2 BB with zero near-duplicates. The selector seeks a 3 SE qualification gap subject to diversity and coverage constraints, relaxing the threshold only when the stronger requirement would materially degrade field diversity. |
| D2 | AoF top tier (production-policy variants) **accepted**; no new AoF bots; the style–strength confounding caveat is kept. |
| D3 | Duplicate lanes **implemented before field-reference**; `mu_field` uses matched k-lane evaluation. |
| D4 | NLHE4 keeps the same 96 parameter vectors as NLHE6 and is calibrated independently. |
| D5 | Stateless agents accepted as a limitation. The runner now exposes rolling within-match history (public 2026 semantics). |

All six AoF4 and NLHE6 fields are **FROZEN** (`configs/fhr3b/fields/FROZEN.yaml`). The verdicts
below are the pre-decision review, kept for the record. The contradictions in §5 are updated at
the end of this document.

## Verdicts (pre-decision review)

| field | AoF4 | NLHE6 |
|---|---|---|
| `spread` | **FREEZE**: gap 2.89 SE / 6.6 BB (target 3), zero near-duplicates | **REVISE (decision)**: best gap without near-duplicates is 2.34 SE / 12.2 BB; see D1 |
| `crowded_cutoff` | **FREEZE**: cutoff cluster spans 4 styles and 6 archetypes; leaders are 3 production-policy variants (pool property) | **FREEZE**: cutoff cluster 3/3/3/3 across the four styles |
| `style_diverse` | **FREEZE**, with caveat: the top quintile supplies no tight-aggressive (TA) bots; 7 near-duplicate substitutions | **FREEZE**: styles 16/15/13/16, style–strength η² = 0.03 |

"Freeze" means the candidate manifest is ready to commit. `field-reference` must still confirm each
construction property in field context.

## 1. What was analysed (provenance)

| mode | calibration id | identity | chunk digest | engine hash at run |
|---|---|---|---|---|
| aof4 | `aof4.aof4-pool.H400.pool-calibration.351766c0` | `351766c02ad1bcaa` | `59e52dd9…` | `389451b27c2264d2` |
| nlhe6 | `nlhe6.nlhe6-pool.H400.pool-calibration.4d3e14b6` | `4d3e14b653e156fb` | `4159e79f…` | `389451b27c2264d2` |

* **Scale.** 2,000 rounds, 2,000 matches per bot, 96 bots, namespace `pool-calibration`.
* **Engine hash.** The current engine source hash equals the lock's (`389451b27c2264d2`). All
  code changes in this task are in analysis-only modules.
* **Protocol.** The calibration spec is rebuilt from `fhr3b_baseline` (research status, hash
  `ca1cccabac0c8c23`); the historical record is not read.
* **Behaviour audit.** An exact replay of calibration rounds 0–19 for each mode: 1,920 bot-match
  results per mode, all **identical to the stored deltas**.
  * `aof4/behaviour.csv` sha256 `db041834…`
  * `nlhe6/behaviour.csv` sha256 `6f7b46c9…`
* **Candidate field hashes:**

| mode | spread | crowded_cutoff | style_diverse |
|---|---|---|---|
| aof4 | `db5912d65a47b215` | `b9709c10c5aef403` | `195ceda2edb24052` |
| nlhe6 | `16df070db91a53bd` | `a845c2fcf1b2ed33` | `5c83ad4268c37bdc` |

  The crowded fields are the same bots as v1; only their manifest provenance was re-issued.
* **Reproduction.** `fhr3b behaviour-audit` → `fhr3b select-fields` →
  `scripts/fhr3b_calibration_review.py` → `scripts/fhr3b_calibration_figures.py`. A test
  re-derives the candidate fields from the stored chunks.

## 2. Realism and pathology audit

Figures: `fig_c3_realism`, `fig_c4_field_composition`. Tables: `review/*.csv`, `<mode>/behaviour.csv`.

### Strength distribution

| | AoF4 | NLHE6 |
|---|---|---|
| pool SD of EV | 12.6 BB | 20.8 BB |
| median SE | 1.7 BB | 3.4 BB |
| split-half r of EV | 0.97 | 0.95 |
| one-tournament SE of a bot's mean per match (40 rounds) | 11.8 BB | 24.2 BB |

Strengths are measured reliably. Within a single 40-round tournament, however, every field is
noisy near the cut. That is exactly what Experiment A measures.

### NLHE6 play looks like recognisable poker

* **Frequencies.** VPIP 9–61% (median 29%), PFR 6–49% (22%), 3-bet median 4.7%, fold-to-bet 39%.
* **Styles.** All four classic styles occur: TA 19, LA 29, TP 29, LP 19.
* **Position awareness.** VPIP is 21% early, 28% middle, 34% button, 22% SB and 30% BB (defending).
* **All-ins.** Preflop all-ins are rare (0.2% of hands) and strong (mean 94th hand percentile).
  Busts come from postflop stack-offs in deep pots, not from reckless shoving.
* **Stacks.** Persistent stacks create real variety: 6% of decisions at under 40 BB, 14% at 40–80,
  42% at 80–150 and 38% deeper than 150 BB.

### Busting reflects the format more than the bot

* The median bot busts in **58%** of NLHE6 matches, and 5.5% of matches end with one survivor.
* Busting is only weakly related to strength (Spearman −0.22): the strongest bots still bust
  49–60% of the time.
* The replay shows the strong bots winning pots through plausible poker, not through exploits,
  so this is not pathological. It does mean match outcomes are heavy-tailed and partly
  winner-take-most.
* It is the combination of the locked 2026 match rule and the FHR3 heuristic family, so a
  write-up must state it.

### Stack sensitivity is weak (a realism limitation)

* Preflop VPIP is **flat across stack depth**: 29% / 28% / 28% / 30% from short to very deep.
  Only all-in propensity rises when short (2.1% of hands under 40 BB, against 0.1% deeper).
* The agents therefore express stack skill mainly through commitment thresholds and pot odds.
  They do not change ranges with depth. Dynamic stack management, part of the target skill, is
  present but under-expressed.

### Clipped parameters are not an exploit

* **51 of 96** NLHE6 bots have at least one parameter at a bound, almost all at ε = 0.45. In AoF4
  it is 2 of 96.
* More clipping goes with **weaker** bots (Spearman −0.30 NLHE6, −0.25 AoF4).
* Clipping in field leaders is mostly extreme 3-bet/4-bet sizing multipliers or raise thresholds.
  These are extreme strategies, not simulator exploits.
* The engine rejects illegal actions outright; nothing coerces them.

### `nlhe6-maniac-e2-s2`, the top NLHE6 performer (+55.0 BB, 7 BB above #2)

* **Parameters (no bound hits).** A *tamer* maniac than its archetype:
  * all-in commitment threshold 0.73 (archetype 0.45);
  * bluff frequency 0.21 (0.28) and semi-bluff 0.54 (0.80);
  * smaller 3-bet sizing (2.3× vs 3.2×);
  * stronger multiway discounting (0.76 vs 0.5).
* **Behaviour.** VPIP 54 / PFR 49 / 3-bet 27%, aggression factor 3.4. It makes +36.6 BB/100 in
  uncontested pots and loses −25.6 BB/100 at showdown: a loose-aggressive player exploiting a
  field that folds too often.
* **All-ins.** 48 all-ins in the replay sample, 13 of them preflop (AA, KK, AK, JJ, 99, …).
* **Edge.** Its presence effects by opponent style are all near zero (−2.5 to +2.0 BB against
  a per-pair SE of about 20 BB). It does not farm one exploitable style.
* **Verdict.** Plausible, if extreme, poker. Other NLHE6 leaders also play recognisable
  strategies:
  * `station-e2-s2`: 42/31, wins at showdown;
  * `trapper-e3-s3`: 46/37, wins big pots;
  * `nit-e3-s1`: a drifted archetype, 28% VPIP, aggressive postflop.

### Archetype labels drift

At e2/e3 many bots leave their archetype's behavioural class; for example, `nit-e3-s1` plays 28%
VPIP. Style balance therefore uses observed style classes from the replay, not archetype labels.

### AoF4

* Overall all-in (VPIP) rates run 14–60% and call-vs-shove 5–60%.
* The pool's strong tier is **one strategy family**: the production policy v2 and its blends, all
  with near-identical behaviour (VPIP about 31%, open-shove about 37–38%).
* There is a reproducible **style-level cycle**, reported as an empirical observation and never
  used to select: caller beats shover (+6.0), shover beats policy (+1.6), policy beats caller
  (+4.3). Split-half r = 0.72, label-permutation p < 0.005, cyclic RMS 2.0 BB against a
  transitive RMS of 4.5 BB.
* NLHE6 shows no such cycle (r = −0.26).

### Measured matchup structure of the fields (outcome, not a selection property)

Split-half cyclic r for each field against 300 random 60-bot subsets:

| mode | spread | crowded | style_diverse | random 95% range |
|---|---|---|---|---|
| AoF4 | 0.10 | 0.06 | 0.10 | −0.01 … 0.09 |
| NLHE6 | 0.03 | 0.03 | 0.01 | −0.04 … 0.03 |

No field is specially matchup-sensitive. AoF4's slight excess comes from its archetype mix
(the cycle above).

## 3. Field assessments

Figures: `fig_c1_field_structure` (all fields), `fig_c2_boundary_zoom` (ranks 1–12 with CIs),
`fig_c4_field_composition` (style × strength quintile).

### spread (selection v2)

| | AoF4 | NLHE6 |
|---|---|---|
| gap rank 6 → 7 | **6.6 BB = 2.89 SE** | **12.2 BB = 2.34 SE** |
| gap constraint used (target 3.0) | 2.75 | 2.25 |
| bots within ±5 BB of the cut (v1) | 5 (13) | 0 (7) |
| near-duplicate pairs | 0 | 0 |
| styles (TA/LA/TP/LP) | 15/14/15/16 | 13/16/17/14 |
| max per archetype | 10 | 9 |
| style–strength η² | 0.13 | 0.03 |
| EV SD | 12.6 | 21.0 |

* **Leaders.**
  * AoF4: `policy-e0` plus five policy-family variants. Any clear AoF top 6 is policy-family,
    because nothing else is that strong.
  * NLHE6: `maniac-e2-s2`, `station-e2-s2`, `trapper-e3-s3`, `neutral-e1-s0`, `nit-e3-s1` and
    `aggressive-e3-s3`, five archetypes over three styles.
* **Why not 3 SE.** The pool's upper tier is sparse. Measured alternatives:
  * allow near-duplicates: NLHE6 reaches 3.37 SE / 17.5 BB, but with 23 near-duplicate pairs;
  * near-duplicate threshold 0.10: 2.75 SE, 16 pairs;
  * archetype caps and strata do not bind.

  With zero near-duplicates, 2.34 SE is the maximum for NLHE6.
* **Realism cost of the gap.** 18–20 pool bots in the band just below the leaders are excluded.
  This leaves an intentional hole under the cut, which is what "easy boundary" means. Breadth and
  style balance are preserved.

### crowded_cutoff (rule unchanged; diversity audited)

| | AoF4 | NLHE6 |
|---|---|---|
| gap rank 3 → 4 | 16.6 BB | 24.2 BB |
| bots within ±5 BB of the cut | 19 | 20 |
| cutoff cluster (ranks 4–15): styles | LA 5, LP 4, TA 2, TP 1 | **TA 3, LA 3, TP 3, LP 3** |
| cutoff cluster: archetypes | 6 | 5 |
| cutoff cluster: near-duplicate pairs / 66 | 3 | 7 |
| cutoff cluster: median parameter distance | 0.27 | 0.42 |
| leaders | 3 production-policy variants (1 near-duplicate pair) | maniac / station / trapper (distinct) |

* **The cluster holds meaningfully different strategies of genuinely similar strength.**
  * NLHE6: VPIP 21–52%, fold-to-bet 0.29–0.49; tight-aggressive through station-like play.
  * AoF4: open-shove 0.31–0.66, call-vs-shove 0.16–0.32.
* It is not a set of parameter clones, so it is preserved.
* The 29–35 near-duplicate pairs in the *whole* field come from the unchanged evenly spaced fill
  below the crowd, which does not touch the boundary.

### style_diverse (replaces matchup_sensitive)

| | AoF4 | NLHE6 |
|---|---|---|
| styles (TA/LA/TP/LP) | 15/18/13/14 | 13/16/16/15 |
| archetypes | 6–9 each | 7–8 each |
| near-duplicate pairs | 0 | 0 |
| style–strength η² | 0.11 | 0.03 |
| cell allocation (every stratum = 12) | slack 0 | slack 0 |
| substitutions | 7 (policy-family near-duplicates in the top two quintiles) | 4 |

AoF caveat: in the pool, tight-aggressive (TA) bots are entirely absent from the strongest
quintile, and the policy family is LP/LA. Some style–strength association is inherent to the AoF
pool and cannot be removed by selection.

## 4. Selector definitions (deterministic)

The code is in `src/fhr3/tournament/selection.py` and the parameters in `configs/fhr3b/matrix.yaml`
(`calibration.selection`).

Common rules:

* SEs are analytic `sd / sqrt(matches)`, so selection does not depend on bootstrap draws.
* Near-duplicate = resolved-parameter RMS distance < 0.15.
* Styles come from the behaviour audit.

**spread**

1. Leaders: walk the ranking; skip near-duplicates of accepted leaders; at most 3 leaders per
   archetype; stop at 6.
2. Exclude every non-leader with `mu ≥ mu_6 − g·sqrt(se_6² + se_b²)`, target g = 3.
3. Fill 54 bots from 6 equal-count strata below the gap with equal quotas. Picks favour the least
   used style, then the least used archetype, then the maximum parameter distance. No
   near-duplicates; at most 10 per archetype.
4. If the whole construction is infeasible, lower g in 0.25 steps. Record g and the achieved gap.

**crowded_cutoff**

The unchanged v1 rule (3 leaders; the tightest 12-bot window straddling the cut; evenly spaced
fill), plus the diversity audit.

**style_diverse**

1. Cells are style (4) × pool-strength quintile (5).
2. A HiGHS integer program fixes every stratum total at 12 and every style total at 15, with
   slack only if infeasible, minimising `Σ |x − 3|`.
3. Within each cell, pick diverse bots (archetype balance, then parameter distance, then
   closeness to the cell median). No near-duplicates.
4. A blocked cell takes a same-stratum substitute, then the nearest-strength eligible bot.

**Retired:** `matchup_sensitive`, `matchup_gate` and greedy cyclic-share selection.

## 5. Contradictions between the implementation and the locked protocol

1. **Experiment D (duplicate play) is not implemented.** The design is in
   `docs/fhr3b/ARCHITECTURE.md`; `fhr3b run --experiment duplicate-play` refuses.
2. **Bots cannot use earlier hands of a match.** The locked semantics allow it. FHR3 agents are
   stateless: they see all current stacks and the current hand, not match history. No opponent
   modelling or tilt-free adaptation across hands exists.
3. **Stack adaptation is weak** (measured, §2). The agents do not widen or narrow ranges with depth.
4. **`mu_field` is not yet "controlled/matched".** Field-reference currently uses unmatched
   random-table calibration. Matched `mu_field` needs the duplicate-lane match of item 1.
5. **NLHE4 and NLHE6 pools share parameter vectors.** The construction key is the agent family.
   This is defensible (same policies, format-specific calibration), but it is a choice.
6. **Retired code kept on purpose.**
   * A comment in `fields.py` still lists `matchup_sensitive`.
   * `calibration.py` keeps the unused `select_matchup` / `subset_share_ci` / `hodge`.

   Both files are under the engine source hash. Editing them would change the hash recorded in
   the completed calibrations. They are no longer called by selection or analysis.
7. **Spread cannot reach 3 SE in NLHE6** without admitting near-duplicates (§3).
8. **Accuracy vs `mu_swiss`.** Fixed in this task: analysis now reports accuracy against both
   `mu_field` and `mu_swiss` (`reference_accuracy.csv`).

## 6. Decisions needed from Henry

* **D1 (NLHE6 spread).** Choose one:
  * (a) accept 2.34 SE / 12.2 BB with zero near-duplicates (**recommended**; it is the maximum
    diversity-preserving gap, with 0 bots within ±5 BB of the cut);
  * (b) admit near-duplicates to reach 3.37 SE;
  * (c) enlarge the pool, which needs a new calibration.

  Under (a), declare the rule as "target 3 SE, relaxed to the largest feasible with zero
  near-duplicates, floor 2 SE", as implemented.
* **D2 (AoF top tier).** Accept that AoF leaders and cutoff boundaries are dominated by the
  production-policy family, since no other AoF strategy is that strong? The alternative is to add
  stronger non-policy AoF candidates, which means new pool bots and a new calibration.
* **D3 (matched `mu_field`).** Implement duplicate-lane matches (Experiment D) *before*
  field-reference, so `mu_field` is matched as the locked design asks? Recommended. The cost is
  the same compute per lane-hand.
* **D4 (NLHE4 pool).** Keep identical parameter vectors to NLHE6 (current; same policies across
  formats)? The alternative is mode-specific perturbation draws: a `fields.py` change, which alters
  the engine hash for new work only.
* **D5 (stateful agents).** Accept stateless agents for the publication design (state it as a
  limitation), or add a match-history-aware family before running tournaments?

## 7. NLHE4 readiness (NOT run)

What is prepared:

* `configs/fhr3b/modes/nlhe4.yaml`: 4-max, 100 BB, `persistent_no_rebuy`.
* A frozen 96-bot pool (`fields/nlhe4/pool.json`, hash `e1d187eb0b4551c2`).
* A calibration spec: id prefix `nlhe4.nlhe4-pool.H400.pool-calibration.`, namespace
  `pool-calibration`, 24 tables per round.
* Behaviour-audit and selection plumbing.
* Unit tests, plus a smoke run through calibration, audit, selection and analysis at toy scale.

Command:

```bash
MODES=nlhe4 scripts/run_fhr3b.sh calibrate-pool
```

Cost (estimate): 19.2M hands at 1,470 hands/s/core ≈ 3.6 core-hours, which is **≈ 1–1.5 h wall**
at 8 workers (AoF4's equal-size run took 68 min) and up to ≈ 3 h on a shared machine. Then run
`behaviour-audit`, `select-fields` and the review scripts (minutes).

## Status of the §5 contradictions after implementation (2026-09-30)

1. **Duplicate play:** implemented (`DuplicateMatchPlayer`), tested and wired into Experiment D and
   the matched field-reference. Not yet run.
2. **Match history:** rolling previous-hand history is now exposed (`Observation.extra`), and the
   exposure is result-neutral. The agents remain stateless (D5, accepted limitation).
3. **Weak stack adaptation:** unchanged. It is a property of the agent family (limitation).
4. **Matched `mu_field`:** resolved by configuration (`field_reference.match_format: duplicate`).
5. **Shared NLHE4/NLHE6 parameter vectors:** intentional (D4).
6. **Retired code:** the matchup code is still present but unused. The engine hash changed anyway
   (`389451b27c2264d2` → `9c28d93c20d45ab4`) because `match.py`, `calibration.py`,
   `protocol.py` and `cells.py` gained history / duplicate support; neutrality is proven by exact
   replay. Removing the dead code is optional.
7. **NLHE6 spread below 3 SE:** accepted (D1).
8. **Accuracy against both references:** fixed.
