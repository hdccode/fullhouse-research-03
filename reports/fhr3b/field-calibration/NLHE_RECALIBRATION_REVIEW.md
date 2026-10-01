# NLHE re-calibration review: corrected heads-up roles (2026-10-01)

Status: **review package; nothing frozen; `FROZEN.yaml` unchanged.**

Sources:

* the corrected pool calibrations;
* the behaviour replays;
* the selection-v2 candidates;
* the retired heads-up-role-bug calibrations, for the before/after comparison.

All numbers come from `scripts/fhr3b_nlhe_recalibration_review.py` →
`review/nlhe_recalibration.json`. Units are balanced field EV in BB per 400-hand match.

## 1. Field selections

| mode | field | hash | gap r6–r7 (BB) | gap (SE) | near-duplicate pairs (total) | in ranks 4–15 | styles TA/LA/TP/LP | style–strength η² |
|---|---|---|---|---|---|---|---|---|
| NLHE4 | spread | `9321903d179be927` | **15.1** | **3.08** | 0 | 0 | 15/17/19/9 | 0.25 |
| NLHE4 | crowded_cutoff | `b08787fc63ec0aeb` | 0.21 | 0.05 | 29 | 1 | 15/14/24/7 | 0.25 |
| NLHE4 | style_diverse | `c673f69cff5facc5` | 0.06 | 0.01 | 0 | 0 | 14/16/15/15 | 0.26 |
| NLHE6 | spread | `ff0f2b07fc210f62` | **16.8** | **3.06** | 0 | 0 | 13/17/18/12 | 0.03 |
| NLHE6 | crowded_cutoff | `afbffedfc3706d84` | 0.09 | 0.02 | 22 | 3 | 15/15/20/10 | 0.02 |
| NLHE6 | style_diverse | `ad7d6596ef1c8c3e` | 2.87 | 0.48 | 0 | 0 | 13/17/17/13 | 0.03 |

* **Spread now meets the full 3 SE target in both modes,** with zero near-duplicates and 0 bots
  within ±5 BB of the cut. No relaxation was needed; the bugged NLHE6 spread had reached only
  2.34 SE.
* **Archetype composition.**
  * spread: 5–10 per archetype;
  * style_diverse: 7–8 per archetype in NLHE4 and 6–9 in NLHE6;
  * crowded_cutoff: up to 12 maniac-labelled bots in both modes, because the evenly spaced fill
    below the crowd is not diversity-constrained (unchanged rule).
* **NLHE4 style confounding is a pool property.** In 4-max, observed style strongly tracks
  strength: the pool's η² is **0.28**, with tight-passive averaging −17.3 BB and loose-passive
  +15.5 BB. The pool has no loose-passive bots in its fourth quintile and only one tight-passive
  bot in each of the top two. `style_diverse` reaches the best balance the pool allows (η² 0.26,
  allocation in the manifest; 6 substitutions). This is a genuine 4-max finding, comparable to the
  AoF caveat. NLHE6 is essentially unconfounded (pool η² 0.04).

## 2. crowded_cutoff quality

### NLHE4 (`b08787fc63ec0aeb`)

All bot ids carry the `nlhe4-` prefix.

| rk | bot | EV (BB) | style | archetype | VPIP / PFR / 3-bet |
|---|---|---|---|---|---|
| 1 | maniac-e2-s2 | 62.2 ± 3.9 | LA | maniac | .65 / .56 / .27 |
| 2 | station-e2-s2 | 53.1 ± 3.7 | LP | station | .53 / .40 / .05 |
| 3 | tight-e3-s2 | 40.0 ± 3.8 | LP | tight (drifted) | .60 / .40 / .03 |
| 4 | tight-e2-s3 | 11.6 | TA | tight | .35 / .30 / .06 |
| 5 | neutral-e1-s2 | 10.3 | TP | neutral | .34 / .26 / .05 |
| 6 | neutral-e1-s1 | 9.2 | TA | neutral | .28 / .23 / .04 |
| 7 | station-e1-s0 | 9.0 | LP | station | .39 / .27 / .04 |
| 8 | station-e0 | 9.0 | LP | station | .39 / .28 / .04 |
| 9 | maniac-e2-s3 | 9.0 | TA | maniac | .35 / .31 / .11 |
| 10 | maniac-e3-s2 | 8.8 | TA | maniac | .35 / .30 / .03 |
| 11 | maniac-e1-s0 | 8.7 | LA | maniac | .46 / .37 / .10 |
| 12 | trapper-e1-s1 | 8.3 | TP | trapper | .30 / .23 / .03 |
| 13 | loose-e2-s3 | 7.6 | LA | loose | .40 / .32 / .06 |
| 14 | neutral-e2-s3 | 7.2 | TA | neutral | .30 / .24 / .04 |
| 15 | maniac-e3-s0 | 7.1 | LA | maniac | .64 / .55 / .17 |

* **Leaders** are distinct (parameter distances 0.58–0.68), with a 28 BB drop to rank 4.
* **Ranks 4–15:**
  * styles: TA 5, LA 3, TP 2, LP 2; six archetypes; median parameter distance 0.38;
  * behaviour spans VPIP .28–.64, 3-bet .03–.17, fold-to-bet .24–.58;
  * one near-duplicate pair, station-e1-s0 / station-e0 (0.091).
* **Tightness is genuine:** EV range 4.5 BB, noise-adjusted true SD ≈ 0. Held-out half ranges are
  12.4 and 9.9 BB, against a pure-noise expectation of 15.1 BB.
* **Verdict:** distinct strategies of indistinguishable strength, not clone compression.

### NLHE6 (`afbffedfc3706d84`)

All bot ids carry the `nlhe6-` prefix.

| rk | bot | EV (BB) | style | archetype | VPIP / PFR / 3-bet |
|---|---|---|---|---|---|
| 1 | maniac-e2-s2 | 54.2 ± 4.7 | LA | maniac | .57 / .51 / .27 |
| 2 | station-e2-s2 | 52.7 ± 4.5 | LP | station | .49 / .37 / .05 |
| 3 | trapper-e3-s3 | 38.5 ± 4.0 | LA | trapper | .48 / .38 / .09 |
| 4 | maniac-e2-s3 | 12.4 | LA | maniac | .33 / .30 / .11 |
| 5 | neutral-e1-s1 | 12.4 | TP | neutral | .24 / .18 / .05 |
| 6 | aggressive-e2-s0 | 12.0 | TP | aggressive | .31 / .23 / .05 |
| 7 | loose-e3-s2 | 11.9 | LP | loose | .60 / .45 / .10 |
| 8 | aggressive-e1-s0 | 11.8 | TA | aggressive | .26 / .21 / .06 |
| 9 | loose-e3-s1 | 11.7 | LA | loose | .54 / .51 / .29 |
| 10 | tight-e2-s3 | 11.5 | TA | tight | .27 / .21 / .04 |
| 11 | aggressive-e1-s1 | 10.6 | TA | aggressive | .30 / .23 / .07 |
| 12 | trapper-e0 | 10.2 | TP | trapper | .26 / .19 / .03 |
| 13 | tight-e1-s2 | 9.9 | TA | tight | .22 / .17 / .03 |
| 14 | station-e1-s2 | 9.6 | TP | station | .31 / .22 / .03 |
| 15 | maniac-e3-s2 | 9.6 | TA | maniac | .31 / .26 / .04 |

* **Leaders** are distinct (0.42–0.59), with a 26 BB drop to rank 4.
* **Ranks 4–15:**
  * styles: TA 5, TP 4, LA 2, LP 1; seven archetypes; median parameter distance 0.42;
  * behaviour spans VPIP .22–.60, 3-bet .03–.29, fold-to-bet .26–.61.
* **Near-duplicates.** Three pairs (distances 0.128–0.147). All of them are e1 tight-aggressive
  siblings (neutral-e1-s1, tight-e1-s2, aggressive-e1-s0, aggressive-e1-s1): 4 of the 12 bots form
  a small TAG cluster. The other 8 are spread across all four styles.
* **Tightness is genuine:** EV range 2.9 BB, true SD ≈ 0. Held-out half ranges are 8.1 and 11.1 BB,
  against a pure-noise expectation of 17.5 BB.
* **Verdict:** genuinely diverse, with one minor TAG sub-cluster (fewer near-duplicate pairs than
  the previously approved bugged NLHE6 crowd, which had 7).

## 3. Corrected realism

| | NLHE4 | NLHE6 |
|---|---|---|
| VPIP range (median) | 11–75% (36.2%) | 10–71% (32.4%) |
| VPIP by position | SB 27, BB 30, first-in 34, **BTN 46** (fixed; was inverted) | SB 23, BB 30, EP 21, MP 28, BTN 42 |
| HU button first in | **raise 42%, fold 58%** (was 12 / 88) | **raise 43%, fold 57%** (was 12 / 88) |
| HU BB facing a raise | fold 65%, call 29%, 3-bet 7% (was fold 87%) | fold 65%, call 28%, 3-bet 7% (was fold 88%) |
| hands played heads-up | 45.3% (was 52.8%) | 20.3% (was 23.3%) |
| PFR / 3-bet / postflop aggression | 28.2% / 4.9% / 1.89 | 23.6% / 4.7% / 1.89 |
| preflop all-in rate (hand percentile) | 0.16% (92nd) | 0.20% (94th) |
| median bust rate | 0.546 (was 0.476) | 0.596 (was 0.577) |
| matches ending with one survivor | **40.1%** (was 11.9%) | 18.9% (was 5.5%) |
| Spearman(strength, bust) | −0.16 | −0.22 |
| VPIP by stack <40 / 40–80 / 80–150 / >150 BB | 36 / 35 / 36 / 39% | 30 / 30 / 29 / 35% |
| all-in rate when <40 BB vs deeper | 1.9% vs ≤0.1% | 2.1% vs ≤0.1% |
| clipped bots; Spearman(strength, #clipped) | 51/96; −0.23 | 51/96; −0.29 |
| split-half r of EV; pool SD | 0.972; 23.5 BB | 0.953; 22.6 BB |

### Strongest bots: plausible strategies

* **NLHE4:**
  * `maniac-e2-s2`: LAG, wins uncontested pots (+33 BB/100);
  * `station-e2-s2`: calling station, wins at showdown (+16);
  * `tight-e3-s2`: a drifted loose-passive player who steals well;
  * `trapper-e3-s3`: wins at showdown (+25);
  * `trapper-e2-s2`: hyper-loose, steals.
* **NLHE6:** the same leaders, plus `nit-e3-s1` and `neutral-e1-s0`.
* **Not a sizing exploit.** The heuristic's defence ranges ignore bet size, so I checked whether
  oversized opens are rewarded. They are not: Spearman(open size, strength) = −0.16 (−0.15 NLHE6),
  the same as before the fix, and `tight-e3-s2` opens at the *minimum* clipped size of 2.0 BB.

### Remaining issues (limitations, not bugs)

* **Heads-up opening is tight by human standards.** The button opens ~42%, from the intended
  small-blind range, against ~80% in human heads-up play. The BB defends ~35%. This is
  parameterisation, not a role error.
* **Stack-depth adaptation is still weak.** VPIP is flat across depths, and all-in propensity
  rises only when short.
* **Defence ignores raise size** in all formats (FHR3A design). The test above shows no
  exploitation of it.
* **4-max matches are now much more decisive.** 40% end with a single survivor. That is a direct
  consequence of heads-up endgames now being played rather than folded. It is not pathology, but
  NLHE4 matches are shorter-lived and closer to winner-take-all.

## 4. Before vs after the heads-up-role fix

| | NLHE4 | NLHE6 |
|---|---|---|
| Spearman (Kendall) of strength | 0.976 (0.877) | 0.991 (0.932) |
| top-6 overlap | 5/6: `tight-e3-s2` in, `aggressive-e3-s3` out | 5/6: `station-e2-s3` in, `aggressive-e3-s3` out |
| bots with |ΔEV| > 3 SE | 10 | 0 |
| pool SD | 18.6 → 23.5 BB | 20.8 → 22.6 BB |
| observed-style changes | 20 / 96 | 4 / 96 |

**Largest rank and EV changes:**

* **NLHE4 gainers:**

| bot | rank | EV (BB) |
|---|---|---|
| tight-e3-s2 | 22 → 3 | +14.3 → +40.0 |
| aggressive-e3-s0 | 32 → 14 | +9.6 → +24.9 |
| neutral-e3-s3 | 31 → 15 | +10.4 → +24.9 |

* **NLHE4 losers:** trapper-e3-s1 (−14.9 → −29.7), maniac-e3-s1, loose-e3-s0 and station-e3-s3
  (each about −14 BB).
* **NLHE6:** every change is ≤ 12 ranks and ≤ 7 BB. The largest is station-e2-s3, +24.8 → +31.8.

**Who gained and who lost.** Loose-passive (LP) bots gained most (+3.6 BB in NLHE4) and
tight-passive (TP) bots lost most (−3.7 BB). By archetype, aggressive gained (+3.1) while nit
(−4.0) and maniac (−2.5) lost. Heads-up is now real poker, which rewards loose play and punishes
passivity.

**Heads-up frequency and busting.** Heads-up share fell from 52.8% to 45.3% (NLHE4) and from
23.3% to 20.3% (NLHE6). Median bust rose (0.476 → 0.546; 0.577 → 0.596), and single-survivor
matches roughly tripled to quadrupled.

**Do conclusions change?** The overall strength landscape and the identity of the leaders are
essentially unchanged: correlation ≥ 0.98 and maniac-e2-s2, station-e2-s2 and trapper-e3-s3 still
lead.

* **What changed materially:**
  * NLHE4 match dynamics: more decisive, more busts, and a wider strength range;
  * NLHE4 4-max positional realism, which is now correct;
  * NLHE4 style confounding, which is stronger after the fix.
* **What survives:** "busting is not pathology"; "clipping does not create winners"; "the
  strongest bots play recognisable strategies"; "NLHE4 and NLHE6 rank the same policies similarly".
* **Superseded:** every number in the earlier NLHE review (now retired).

## 5. Corrected NLHE4 vs corrected NLHE6 (same 96 parameter vectors)

* **Strength agreement:** Spearman 0.948, Kendall 0.801. No bot moves more than 30 ranks.
* **Top-6 overlap: 3/6.**
  * shared: maniac-e2-s2, station-e2-s2, trapper-e3-s3;
  * 4-max only: tight-e3-s2, trapper-e2-s2, loose-e1-s1;
  * 6-max only: nit-e3-s1, neutral-e1-s0, station-e2-s3.
* **Largest cross-format movers:**

| direction | bot | EV 4-max vs 6-max (BB) | rank 4-max vs 6-max |
|---|---|---|---|
| better in 4-max | tight-e3-s2 | +40.0 vs +14.7 | 3 vs 25 |
| better in 4-max | station-e3-s0 | +17.1 vs −1.5 | 25 vs 55 |
| better in 4-max | maniac-e3-s0 | +7.1 vs −12.7 | — |
| better in 6-max | tight-e1-s0 | −11.8 vs +6.1 | — |
| better in 6-max | nit-e2-s2 | −36.5 vs −20.3 | — |
| better in 6-max | nit-e2-s3 | −42.0 vs −30.1 | — |

* **Style is partly format-dependent:** 21 of 96 bots change observed style class.
* **Table size changes the landscape coherently.** Shorter tables reward loose and loose-passive
  play and punish tight-passive and nit play: in 4-max the pool's style η² is 0.28 against 0.04
  in 6-max. Agreement on the leaders and the broad ordering stays high.

## 6. Integrity

| check | result |
|---|---|
| commit | `fec0aed69d6c0eede56bc6ec494e97921ca31f0e`; the new candidates and reports are uncommitted |
| engine source hash | `5f5019c69316d098`, matching both new calibration locks |
| NLHE4 calibration | `nlhe4.nlhe4-pool.H400.pool-calibration.9880eebd` (pool `c9b0ffb56855a62d`, 80 chunks, digest `719f0ad8…`) |
| NLHE6 calibration | `nlhe6.nlhe6-pool.H400.pool-calibration.aadd073b` (pool `a867bd18d6033233`, 80 chunks, digest `ddafa095…`) |
| behaviour replays | 1,920 / 1,920 bot-match results identical to stored, per mode; the 5-round heads-up replays (new and retired) are identical too |
| tests | **405 passed, 1 skipped** (the long-standing optional `confseq` test) |
| reproduction tests | **active and passing** for AoF4, NLHE4 and NLHE6: each candidate field is re-derived exactly from its calibration |
| AoF4 frozen fields | unchanged (`db5912d6…`, `b9709c10…`, `195ceda2…`); `FROZEN.yaml` unchanged since HEAD |
| revoked hashes | all 8 still revoked; NLHE4 and NLHE6 fields refused as not frozen |

## 7. Recommendation

| mode | field | verdict | reason |
|---|---|---|---|
| NLHE4 | spread | **FREEZE** | gap 15.1 BB = 3.08 SE (full target); zero near-duplicates; 0 bots within ±5 BB; balanced archetypes. Style confounding (η² 0.25) is inherited from the 4-max pool. |
| NLHE4 | crowded_cutoff | **FREEZE** | 3 distinct leaders; cluster of 12 at true SD ≈ 0 (confirmed held out) across all 4 styles and 6 archetypes; 1 near-duplicate pair in ranks 4–15 |
| NLHE4 | style_diverse | **FREEZE (caveat)** | styles 14/16/15/15; archetypes 7–8; zero near-duplicates. Caveat: 4-max style is strongly tied to strength (pool η² 0.28) and cannot be balanced further. |
| NLHE6 | spread | **FREEZE** | gap 16.8 BB = 3.06 SE (now meets the target); zero near-duplicates; 0 bots within ±5 BB |
| NLHE6 | crowded_cutoff | **FREEZE** | 3 distinct leaders; cluster at true SD ≈ 0 (held out) across 4 styles and 7 archetypes; 3 near-duplicate pairs, all within one 4-bot TAG sub-cluster (noted) |
| NLHE6 | style_diverse | **FREEZE** | styles 13/17/17/13; archetypes 6–9; zero near-duplicates; η² 0.03 |

**No new bug or methodological problem was found.** The checks for oversized-open exploitation
and for selector failure on style confounding both came back clean.
