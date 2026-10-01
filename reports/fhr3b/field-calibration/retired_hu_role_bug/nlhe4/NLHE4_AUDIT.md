# NLHE4 field audit (2026-10-01)

Inputs:

* pool calibration `nlhe4.nlhe4-pool.H400.pool-calibration.698094ac`: 2,000 rounds, engine
  `9c28d93c20d45ab4`, pool `e1d187eb0b4551c2`, digest `b0710cc6…`;
* behaviour replay of 20 rounds (1,920 bot-match results, identical to the stored deltas);
* selection v2 candidates.

No new simulation was run beyond a 5-round diagnostic replay per NLHE mode, used for the
heads-up finding (§3).

## 1. crowded_cutoff `289e4bdb8c9f99bc`: ranks 1–15

| rk | bot | EV (BB) | SE | style | archetype | VPIP | PFR | 3-bet | fold-to-bet |
|---|---|---|---|---|---|---|---|---|---|
| 1 | maniac-e2-s2 | 55.5 | 3.6 | LA | maniac | .53 | .47 | .27 | .62 |
| 2 | station-e2-s2 | 40.2 | 3.2 | LP | station | .38 | .29 | .05 | .50 |
| 3 | trapper-e3-s3 | 31.4 | 2.9 | LA | trapper | .48 | .39 | .09 | .55 |
| 4 | aggressive-e3-s0 | 9.6 | 2.9 | LP | aggressive | .32 | .25 | .06 | .37 |
| 5 | neutral-e1-s1 | 9.5 | 2.8 | TA | neutral | .24 | .19 | .04 | .51 |
| 6 | maniac-e3-s2 | 9.0 | 2.9 | TA | maniac | .27 | .24 | .03 | .60 |
| 7 | aggressive-e2-s0 | 9.0 | 2.8 | TP | aggressive | .25 | .19 | .04 | .47 |
| 8 | station-e3-s0 | 8.9 | 3.3 | LP | station | .52 | .32 | .04 | .67 |
| 9 | neutral-e1-s2 | 8.1 | 2.7 | LA | neutral | .29 | .23 | .05 | .42 |
| 10 | tight-e2-s3 | 8.0 | 2.7 | TA | tight | .28 | .24 | .06 | .40 |
| 11 | maniac-e0 | 7.6 | 3.2 | LA | maniac | .40 | .35 | .17 | .38 |
| 12 | station-e0 | 6.4 | 2.9 | LP | station | .31 | .23 | .04 | .26 |
| 13 | loose-e2-s0 | 6.3 | 2.8 | LP | loose | .39 | .29 | .09 | .34 |
| 14 | maniac-e3-s0 | 6.1 | 3.3 | LA | maniac | .48 | .43 | .17 | .43 |
| 15 | maniac-e1-s0 | 6.1 | 3.2 | LA | maniac | .38 | .32 | .11 | .41 |

All bot ids carry the `nlhe4-` prefix.

* **Rank-6/7 gap:** 0.07 BB = 0.02 SE. The gap from rank 3 to rank 4 is 21.8 BB.
* **Near-duplicate pairs in ranks 1–15:** one, `maniac-e0` / `maniac-e1-s0` (distance 0.097).
  It is also the only one inside ranks 4–15: 1 of 66 pairs.
* **Ranks 4–15:**
  * styles: LP 4, LA 4, TA 3, TP 1;
  * archetypes: maniac 4, aggressive 2, neutral 2, station 2, tight 1, loose 1;
  * median parameter distance 0.42;
  * behaviour spans VPIP .24–.52, PFR .19–.43, 3-bet .03–.17, fold-to-bet .26–.67.
* **Maniac labels drift.** The four maniac-labelled bots in the cluster play differently:
  `maniac-e3-s2` is tight-aggressive at 27% VPIP; the other three are loose-aggressive at
  38–48% VPIP with 11–17% 3-bets.
* **Leaders:** distinct strategies (pairwise distances 0.42–0.59: LAG, station-like, trapper).
* **Cluster tightness:** EV range 3.5 BB; true SD after removing noise ≈ 0. On held-out halves
  the range is 10.9 / 8.1 BB, against a pure-noise expectation of about 13.7 BB, so the tightness
  is genuine.
* **Matchup structure:** the field's cyclic split-half r is 0.07.

**On the selector's own criteria, the field is sound.** The cluster holds genuinely different
strategies of indistinguishable strength, and the leaders are distinct.

## 2. NLHE4 vs NLHE6 (same 96 parameter vectors)

| | NLHE4 | NLHE6 |
|---|---|---|
| EV SD / median SE / split-half r | 18.6 / 2.8 / 0.967 | 20.8 / 3.4 / 0.953 |
| VPIP range (median) | 10–53% (28.8%) | 9–61% (29.1%) |
| VPIP by position | SB 24, BB 30, **first-in 33.5, BTN 29.8** (inverted) | SB 22, BB 30, EP 21, MP 28, BTN 34 |
| PFR / 3-bet / postflop aggression (medians) | 22.9% / 4.8% / 1.96 | 21.8% / 4.7% / 1.94 |
| preflop all-in rate (mean hand percentile) | 0.17% (93rd) | 0.20% (94th) |
| VPIP by stack <40 / 40–80 / 80–150 / >150 BB | 32 / 33 / 33 / 25% | 29 / 28 / 28 / 30% |
| all-in rate when <40 BB vs deeper | 1.9% vs ≤0.1% | 2.1% vs ≤0.1% |
| median match bust rate | 0.475 | 0.577 |
| matches ending with one survivor | 11.9% | 5.5% |
| Spearman(strength, bust) | −0.07 | −0.22 |
| bots with a clipped parameter; Spearman(strength, #clipped) | 51/96; −0.23 | 51/96; −0.30 |
| hands played heads-up / share of chips moved heads-up | **52.8% / 17.9%** | 23.3% / 4.5% |

* **Strength rankings agree closely:** Spearman 0.933, Kendall 0.779, Pearson 0.936. The two
  top 6s share 4 bots (maniac-e2-s2, station-e2-s2, trapper-e3-s3, aggressive-e3-s3).
* **Material format shifts:** 9 bots have |z| > 3, but only 1 moves more than 30 ranks.
  * Maniacs gain in 4-max (archetype mean +2.1 vs −4.8 BB; `maniac-e3-s1` +22.7 BB,
    `maniac-e3-s0` +17.8 BB).
  * Stations gain (+2.7 vs −0.6).
  * Tight and nit bots lose (−5.2 vs +0.4; −19.0 vs −14.0).
  * `neutral-e1-s2` and `neutral-e2-s3` lose about 10 BB each.

  These directions are plausible: wider and more aggressive play pays at shorter tables.
* **Strongest bots are plausible.**
  * `maniac-e2-s2` leads both formats (55.5 / 55.0 BB) with the same LAG profile and no clipping.
  * The other leaders are recognisable strategies.
  * Clipping goes with weaker bots in both formats.
* **19 of 96 bots change observed style class between formats.** Style is partly
  format-dependent.

## 3. Genuine bug: heuristic agents play heads-up with the wrong roles

* **The bug.** `HeuristicAgent._preflop` (FHR3A `src/fhr3/agents/heuristic.py`) assumes seat 0 = SB
  and seat 1 = BB. In FHR3/PokerKit heads-up, seat 1 is the button/small blind and acts first,
  and seat 0 is the big blind.
  * The heads-up button therefore takes the "BB vs limps" branch: it raises about 2 × the 3-bet
    percentage, with zero call probability, and fold is legal facing the completion.
  * The real big blind uses `call_open_pct` instead of `bb_defend_pct`.
* **Measured** in a 5-round replay:

| role | fold | raise | call |
|---|---|---|---|
| heads-up button | 88% | 12% | — |
| heads-up big blind facing a raise | 87% | 6–7% | 6–7% |

* **Why it matters now.** FHR3A never had heads-up tables (its minimum is 3 seats). Persistent-stack
  busts make heads-up common: 53% of NLHE4 hands and 23% of NLHE6 hands.
* **Consequences:**
  * heads-up endgames become low-information blind exchanges;
  * they inflate the hand count without discriminating between bots;
  * they invert 4-max positional widening;
  * they distort exactly the persistent-stack endgame skill the design targets.
* **Scope.** All heuristic-family NLHE pools (NLHE4, NLHE6). AoF4 always plays 4-handed and is
  unaffected.

## 4. Recommendation

* **NLHE4 crowded_cutoff: REVISE.** The selection itself passes every check; the problem is
  upstream. The NLHE4 pool calibration, and therefore all NLHE4 fields, contains the heads-up bug.
  The same applies to the NLHE4 spread and style_diverse candidates, and it reaches the frozen
  NLHE6 fields too, through their calibration.
* **Suggested fix** (Henry's decision; nothing applied):
  * add an FHR3B-local, heads-up-role-correct heuristic family. It must not touch FHR3A's
    `heuristic.py`, which would alter FHR3A agent versions and hashes;
  * map heads-up seat 1 to SB/button (open with `sb_open_pct`) and seat 0 to BB (defend with
    `bb_defend_pct`);
  * regenerate the NLHE pools on it (new agent versions, hence new pool and field hashes);
  * re-run NLHE4 and NLHE6 pool calibration (≈ 1–1.5 h and ≈ 1–3.4 h at 8 workers), behaviour
    audit and selection, then re-freeze.
* **AoF4 fields stay frozen.**
* **The alternative** is to accept the bug as a documented synthetic-environment property. I
  advise against it, because heads-up play is the majority of NLHE4 hands.
