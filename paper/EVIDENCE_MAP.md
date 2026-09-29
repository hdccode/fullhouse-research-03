# EVIDENCE MAP: research handoff for completing the FHR3 manuscript

The companion files are:
* `CLAIMS.md`: frozen claims C1–C14 with sources and status;
* `NUMBERS.md`: every number with its source field, generated;
* `FIGURES.md`: figure and table specifications;
* `LIMITATIONS.md` and `REFERENCES.md`;
* `DRAFT_REVISION_NOTES.md`.

This file gives the argument, the section map, the transitions, the reconciliations and
the guidance. It is not prose for the paper.

---

## 1. Integrated synthesis: four questions, one causal chain

**Q1. How many hands?**
Against a fixed reference population, with matched blocks, detecting a 1 BB/100 edge at
80% power needs from 0.34M played hands (8BB All-in-or-Fold) to 20.5M (Bomb Pot): 61× (C1).
* Even among 100BB formats the spread is 4.8×. The three candidate pairings inside a single
  format move the requirement 2.8–8.5× (C7).
* NLHE 4-max and 6-max are indistinguishable per played hand (C10).
* Standard fixed-N normal-theory power calculations remain accurate on these heavy-tailed
  streams (C8), so the *numbers* are trustworthy. What varies is the block-level variance
  σ_D².

**Q2. Where does the uncertainty come from?**
σ_D² is dominated by rare decisive big pots.
* Blocks containing a pot of at least one starting stack carry 79–97% of squared deviation
  in 100BB formats, though only 0.6–22% of all blocks are both big-pot and decisive (C2).
* Formats differ mainly in *how often* such pots happen. Pairings differ in *how much* a big
  pot moves D (C2b).
* Stack depth trades these off: shallow stacks create more all-ins, each far smaller, so
  100BB needs ~7× the blocks of 20BB (C3).
* Block construction can hide the mechanism without removing it (Nit, C11).

**Q3. How much of it can be removed?**
If big pots were mainly luck, conditioning on chance would collapse the burden. It does,
but only at shallow stacks.
* Exact all-in EV removes 90% of variance in 8BB AoF, 28% at 20BB and 12% at 100BB (C3, C6).
* At 100BB, broader chance correction (fitted MIVAT) takes it to 38% removed. Correcting
  known agent actions (AIVAT) adds only a little more (42%).
* The tail and the big-pot concentration survive correction (C6). So deep-stack evaluation
  burden is mostly strategic divergence plus chance variation the fitted value model does
  not capture: not simple runout luck.
* Where chance does dominate, the payoff is dramatic: the same 50k AoF blocks go from an
  unresolved comparison to z = 7.4 (C6b).
* Estimator cost matters: all-in EV is nearly free in NLHE, while AIVAT's statistical gain
  is a net wall-clock loss in simulation (C12).

**Q4. How should evaluation stop?**
Because the remaining uncertainty is large and lumpy, evaluations are long, and people
watch them.
* Re-checking an ordinary 95% interval and stopping on significance produces a false
  winner in 58–64% of null streams. It names the wrong agent in 8.5% of real-effect stops.
  It does so in 45% of reorderings of the same real corpus (C4).
* An asymptotic confidence sequence keeps empirical time-uniform coverage on every tested
  stream, the heaviest included. It never picked the wrong sign, and it costs about
  1.6–1.7× the fixed-N sample for equal power (C5).
* In real order, the flagship NLHE comparison shows the failure concretely (C14).

**The chain:** sample burden is σ_D² (Q1). σ_D² is concentrated in decisive big pots (Q2).
Stack depth sets how much of that concentration is removable chance (Q3). What remains is
large enough that the stopping rule itself becomes part of the design (Q4).

---

## 2. Section-by-section map

The draft is not in the repository (see `DRAFT_REVISION_NOTES.md`), so this follows the
planned structure. Map it onto the draft's own headings rather than restructuring.

### §1 Introduction (≈1 page)
* **Purpose:** frame poker-agent evaluation as a sample-complexity problem, and state the
  four questions.
* **Claims:** C1 (61×, 4.8×), C2 (79–97% of squared deviation in rare big pots), C3/C6
  (removable chance: 90% → 28% → 12% as stacks deepen), C4 (58–64% false winners under
  naive monitoring), C5 (the CS works at 1.6–1.7× cost).
* **Figures:** none, or a teaser of F1.
* **Do not claim:** that any format is "harder"; that we invented AIVAT, MIVAT, confidence
  sequences or matched dealing; or intrinsic properties of poker variants.

### §2 Evaluation framework (≈1.5 pages)
* **Purpose:** matched blocks and a fixed reference population; formats; agents; pairings;
  estimand D; block as the independent unit.
* **Evidence:**
  * Table 1;
  * integrity: 0 invalid blocks, exact replay, self-play controls exactly 0, manifests;
  * candidate hands per side: seat count for single-hand protocols, ~47.5 for Nit.
* **Caveats:**
  * benchmark agents are heuristic families; AoF's production policy is the one external
    anchor;
  * Bomb Pot is a stress case whose agents are not credible multiway players;
  * Nit uses its own block protocol.
* **Do not claim:** that heuristic agents represent strong play.

### §3 How many hands? (≈2 pages)
* **Claims:** C1, C7, C10, and C8 as one validating sentence.
* **Evidence:**
  * the seven medians;
  * 61× / 4.8× (hands), 41× (blocks), 475× (wall-clock);
  * pairing spread 2.8–8.5×;
  * NLHE 6-max / 4-max 1.04 [0.98, 1.11].
* **Figures:** F1, F2.
* **Caveats:**
  * comparing effect sizes across formats is a choice: a 1 BB/100 edge differs in meaning;
  * the wall-clock figure is implementation-specific;
  * only three pairings;
  * neighbouring orderings that are not robust: NLHE4 ≈ NLHE6, Crazy Pineapple ≈ Nit (1.09),
    and PLO vs Bomb (1.25, 2/3 roles).
* **Do not claim:** a global difficulty ranking; that player count matters.

### §4 Where does the uncertainty come from? (≈2 pages)
* **Claims:** C2, C2b, C3 (amount), C11 (Nit paragraph).
* **Evidence:**
  * 79–97%; 0.6–22% of all blocks; top-1% 33–95% vs Gaussian ≈ 8.5%;
  * PLO big-pot vs all-in (93–94% vs 82–83%);
  * frequency 0.078/0.078/0.083 within NLHE6;
  * decomposition ≈ 73% frequency (exploratory);
  * stack 7× / 2× with CIs; mechanism 0.08 → 0.29 frequency, 1,869 → 87 magnitude;
  * Nit totals vs chip components.
* **Figures:** F3, F4.
* **Caveats:** exploratory decomposition; agents are not stack-aware.
* **Do not claim:** that all-ins cause the variance; that stack depth causes it
  independently of the agents.

### §5 How much can variance reduction remove? (≈1–1.5 pages)
* **Claims:** C3 (kind), C6, C6b, C12.
* **Evidence:**
  * variance ratios 0.878 / 0.616 / 0.580 (100BB), 0.716 (20BB), 0.098 (AoF), with CIs;
  * increments MIVAT/all-in 0.70–0.72 and AIVAT/MIVAT 0.89–0.97;
  * tail survival (82–87%; κ unchanged or higher);
  * AoF p1 unresolved → resolved;
  * slowdowns 1.06 / 1.42 / 1.86; net wall-clock efficiency.
* **Figure:** F5.
* **Caveats:**
  * a fitted linear value function sets a lower bound on removable chance;
  * max bias |z| = 1.29 is a sanity check, not a proof.
* **Do not claim:** "AIVAT removes 42% of strategic variance"; "the remaining 58% is
  strategic"; that all-in EV "corrects" the AoF estimate.

### §6 How should evaluation stop? (≈1–1.5 pages)
* **Claims:** C4, C5, C14.
* **Evidence:**
  * fixed-N 4.45–4.95%; peeking 58.0–63.9%; CS 2.4–3.4%;
  * timing 16% / 36% / 52% / 58%;
  * wrong sign 8.5% vs 0/9,768;
  * power-matched 1.6–1.7×; width 1.55× at t*;
  * permutations 44.8% vs 0.9%;
  * block 204.
* **Figure:** F6.
* **Caveats:**
  * CS coverage is asymptotic and empirical over the tested horizon and distributions;
  * permutations are conservative;
  * the CS is conservative (2.4–3.4%).
* **Do not claim:** finite-sample exactness; that the CS "wins" on stopping time; that
  peeking's earlier stops are efficiency.

### §7 Practical guidance and limitations (≈1 page)
* Recommendations (§6 below), C9 (pilot rule) and `LIMITATIONS.md`.

### §8 Conclusion (≈0.3 page)
* The four answers, one line each.

---

## 3. Narrative transitions (reasoning bridges only)

* **§2 → §3:** Once the unit (matched block) and estimand (D) are fixed, sample size is
  governed by one number per comparison, σ_D. §3 measures how much it varies.
* **§3 → §4:** A 61× spread in hands means large differences in block-level variance, and
  pairing matters as much as format. The next question is where inside a block that
  variance sits.
* **§4 → §5:** If rare big pots dominate uncertainty, conditioning away the chance in them
  should show how much of the burden is removable, and stack depth should change the
  answer.
* **§5 → §6:** Even after the best estimator, deep-stack evaluation needs millions of hands
  and moves in jumps. Such evaluations get watched while they run, so the stopping rule
  becomes part of the statistical design.
* **§6 → §7:** Each result maps to a design decision: the reference population, pilot size,
  estimator, and stopping rule.

---

## 4. Reconciling apparent tensions

1. **"Big pots dominate uncertainty" but AIVAT removes only ~42%.**
   These are compatible. Concentration says *where* the variance is; RQ6 says how much of
   it is chance the estimator can condition on. Most decisive big pots at 100BB arise
   because A and B *played differently* (strategic divergence), or from chance the linear
   value function does not model. Correction shrinks big-pot and other blocks roughly
   proportionally (big-pot squared deviation −9% to −43%), so the concentration stays at
   82–87%. At 8BB, where divergence resolves in a single all-in, exact all-in EV removes
   ~90%.
2. **Heavy tails (κ up to ~300), yet fixed-N normal power works.**
   At the N that matters (thousands to hundreds of thousands of blocks), the mean of D is
   close to normal even when D is not. Resampled power at the analytic N is 0.78–0.82, and
   fixed-look null rejection is 4.45–4.95%. The limits: this is empirical, from resampling
   observed blocks (unseen tails cannot appear), and the test is slightly conservative for
   the heaviest pairing at n = 500. Put it in the appendix, with one sentence in §3.
3. **CS median stop ≈ N80, yet the power-matched cost is 1.6–1.7×.**
   The fixed test decides in only ~80% of runs, at exactly N80. The CS decides in 95–100%
   of runs eventually, at varying times. A median over a different decision set is not a
   like-for-like comparison. Power-matched means "blocks until the CS has decided as often
   as the fixed test does at N80": 1.60–1.73×. By N80 the CS has decided in only 40–58% of
   runs.
4. **Width inflation (1.55× at t*) vs power-matched cost (1.6–1.7×).**
   Equal width would need 1.55² ≈ 2.4× the blocks. Continuous monitoring recovers part of
   that, because the CS stops at the first crossing, not at a fixed time. Width ratios are
   the same for every distribution by construction (both scale with σ̂). Only coverage and
   stopping are empirical.
5. **The AoF corrected point estimate (+0.41) differs from raw (+0.27).**
   Both are unbiased for the same estimand. On a finite sample they differ, and the
   difference (z = +0.79) is well within noise. The corrected estimate is simply ~3× more
   precise. Report both.
6. **Pairing drives burden, but not the variance-reduction ratio.**
   The agent contrast sets the raw scale of D (how often and how much A and B diverge). The
   format and stack set what fraction of D's variance is chance. Hence ratios are tight
   within a setting (100BB AIVAT 0.571–0.590; AoF 0.093–0.131), while raw burdens differ
   2.8–8.5×.
7. **AIVAT removes zero inflation (D = 0 goes from 87% of blocks to 0%).**
   AIVAT's action corrections depend on each candidate's policy, so they differ between the
   A and B sides even when payoffs match. This is expected and unbiased. Mention it only if
   D = 0 rates are discussed.
8. **Peeking's false rate is *lower* on the heavy poker stream (58%) than on Normal (64%),
   and the CS is most conservative there (2.4%).**
   With many exact zeros and rare large jumps, the running interval moves in steps. Do not
   read this as "heavy tails help". The finding is simply that heavy tails did not hurt
   either method's relative behaviour here.

9. **Our 1.72× AIVAT gain vs AV-AIVAT's reported median 54×.**
   Do not treat these as contradictory before reading Li et al. The settings differ:
   heads-up vs 6-max with a 5-seat reference population; LLM agents vs heuristic
   families; our fitted 7-feature linear value function; and our matched-block design,
   which already cancels the chance shared by both sides before any estimator is applied.
   Our ratios are measured on top of duplicate matching. State this explicitly and
   compare like with like.

---

## 5. Contribution statements (defensible)

**Closest prior work:** Li, Chen & Huang (2026), *AV-AIVAT* (arXiv:2608.06362). They
combine AIVAT with continuously monitored confidence sequences for heads-up NLHE and report
a median 54× variance reduction across 15 LLM-agent configurations (from their abstract).
FHR3 therefore must not claim to be the first to pair poker variance reduction with
anytime-valid stopping. The writer must read the paper, cite it in related work, and
explain how the settings differ before finalizing these statements (see §4, item 9).

1. A matched-block evaluation framework applied uniformly to seven poker formats and three
   stack depths against a fixed reference population, with self-play controls, exact
   replay, frozen manifests and one estimand throughout.
2. A quantitative comparison of evaluation burden across poker variants, in three units
   (independent blocks, played hands, wall-clock). It shows a 61× spread in played hands,
   and that candidate/reference pairing is as consequential as format among 100BB games.
3. Identification of rare decisive big pots as the concentration mechanism of evaluation
   variance (79–97% of squared deviation), with all-in status as a format-dependent proxy.
4. An empirical decomposition, across stack depth, of how much evaluation variance existing
   estimators can remove on identical blocks. Removable chance falls from ~90% (8BB AoF) to
   12–42% (6-max 100BB NLHE), and heavy tails survive correction at deep stacks.
5. A sequential-monitoring study on multi-format, heavy-tailed poker block streams. It
   quantifies naive-peeking failure (58–64% false winners, 8.5% wrong-sign stops, 45% false
   exclusions under reorderings of a real corpus) and the empirical coverage and cost
   (~1.6–1.7×) of an existing asymptotic confidence sequence.
6. Evidence-based evaluation guidance: pilot sizing from kurtosis, estimator choice under
   compute constraints, and stopping rules.

Avoid "first", "novel estimator" and "new confidence sequence". AIVAT, MIVAT, all-in EV,
confidence sequences, duplicate/matched dealing and PokerKit are prior work and must be
cited as such.

## 6. Practical recommendations (each tied to evidence)

| recommendation | motivating result |
|---|---|
| Define and freeze a reference population; report results as "vs this population". | The estimand and σ_D depend on the opponents (C1, C7). |
| Use matched blocks (duplicate deals, shared randomness) and treat the block as the unit. | The whole study; controls are exactly 0. Never treat hands as independent. |
| Never quote a universal hand count; size each evaluation from a block-level pilot. | 61× across formats, 2.8–8.5× across pairings (C1, C7). |
| Pilot until σ_D is stable: n ≈ 384(κ+2) blocks for ±5% σ; a 10k pilot is good to ~30% in required sample. | C9. |
| Keep raw outcomes auditable and the estimand fixed; report estimators alongside raw. | C6b, C13 (estimators change precision, not the estimand). |
| Always report all-in EV. It is exact, model-free and nearly free in NLHE, and transformative when all-ins are frequent. | C3/C6 (10× in AoF; 1.4× at 20BB; 1.14× at 100BB), C12. |
| Use MIVAT (fitted value function, separate training data) for deep-stack NLHE when compute allows. Use AIVAT when hands are expensive (live/human play) and policies are known. | C6 (1.62× / 1.72×), C12 (AIVAT net 0.91–0.94× in simulation). |
| If the budget is fixed, precommit N and look once. | C8, C5 (fixed-N 4.45–4.95%). |
| If results are monitored, use a confidence sequence with a predeclared α and t* near the planned budget, min-N ≥ 200, and budget ~1.7× N80 (~2× at the 90th percentile). | C5. |
| Never stop because a repeatedly viewed ordinary 95% CI excludes zero. If neither design is possible, make no formal significance claim. | C4 (58–64% false winners; 8.5% wrong sign). |

---

## 7. Terminology

**Use:**
* matched block;
* played hands; independent (matched) blocks;
* reference population; candidate/reference pairing;
* block difference D;
* squared deviation (share of);
* decisive big pot (a pot of at least one starting stack in a block with D ≠ 0);
* variance ratio (Var(estimator D)/Var(raw D)); sample efficiency (1/variance ratio);
  wall-clock efficiency (sample efficiency / slowdown);
* fixed-N (single precommitted look); naive peeking;
* confidence sequence (asymptotic, time-uniform);
* all-in EV, MIVAT, AIVAT (fitted value function).

**Avoid:**
* intrinsic variance; the true variance of a game; hardest/easiest poker format;
* unqualified "noise";
* "AIVAT removes 42% of strategic variance";
* "the remaining variance is strategic" (say instead: "strategic divergence plus chance
  variation not captured by the fitted value model");
* calling the CS exact or finite-sample valid;
* "0.6–22% of decisive blocks" (it is a share of all blocks);
* "significant" for peeking stops.

**Be careful with variance ratio vs SD ratio.** An SD ratio of 0.76 is a variance ratio of
0.58, i.e. 1.72× sample efficiency.

---

## 8. Appendix package, and why each item is appendix

| item | source | why appendix |
|---|---|---|
| full per-format × pairing tables (A1–A2) | `final_tables.md` | the detail behind F1/F2; too dense for the main text |
| standardized-d / empirical power (A4) | `d_collapse.csv` | validates a method; true in blocks by construction |
| pilot convergence and the κ rule derivation (A3) | `convergence.csv` | practical guidance; the main text needs one sentence |
| format implementation (rules, CP discard edge case ≤ 0.29% of hands, Bomb ante, Nit protocol, AoF odd-chip convention) | `docs/variants.md` | reproducibility, not argument |
| Bomb stability (10k-window σ variation 1.6–4.7%) and agent-credibility diagnostics | `windows.csv`, `docs/final_status.md` | supports the stress-case framing |
| Nit decomposition (A6) | `nit.json` | a case study; one paragraph suffices in the main text |
| RQ6 tails and big-pot decomposition (A8) | `rq6_tails.csv` | supports C6; the main text needs 82–87% and κ only |
| RQ6 bias diagnostics and raw reproduction (C13) | `rq6_summary.*` | correctness evidence |
| RQ6 compute and net wall-clock (A9) | `rq6_efficiency.csv` | one sentence in the main text |
| RQ7 min-N sensitivity (A10) | `min_n_sensitivity.csv` | it does not change the recommendation |
| RQ7 stopping distributions (A11) | `stopping.csv`, `stopping_cost.csv` | the main text needs the 1.6–1.7× summary |
| RQ7 width inflation (A12) | `width_inflation.csv` | a deterministic property; used in the tension explanation |
| RQ7 all 28 real orderings (A13) | `real_orderings.csv` | the main text shows one trajectory |
| integrity/reproducibility (A14) | manifests | standard |

---

## 9. Reproducibility handoff

* **Code/results SHAs:**
  * core runs: `0ccfc14`, `7be008e`, `d3b8ded`, `a86909d`, `6e88819` (per-run manifests in
    `results/*/runs/`);
  * RQ6 and RQ7 runs: `ac3cd5f`;
  * result commits: `f493579` (core freeze), `5057893` (RQ6), `f53e3ba` (RQ7), `ac2bade`
    (docs); synthesis commit: see git log.
* **Manifests:** `reports/final-analysis/MANIFEST.json` (`scripts/freeze_manifest.py
  --verify`), `reports/rq6/MANIFEST.json` and `reports/rq7/MANIFEST.json`
  (`scripts/freeze_rq_manifest.py rq6|rq7 --verify`). Deep-analysis outputs have
  `SHA256SUMS`.
* **Seeds:**
  * root seed 20260928 for all corpora and RQ6 evaluation;
  * value-function training seed 90210;
  * RQ7 seed 20261007 (per-replicate `SeedSequence`);
  * bootstrap seeds are fixed in the scripts.
* **Corpus sizes:** see Table 1.
* **Estimator artifact:** `configs/rq6/vf/nlhe6-100bb-vf.json`, sha256 `acb224b9…`, pinned in
  `configs/rq6/nlhe_6max_100bb_fitted.yaml`.
* **Pinning:**
  * every corpus is fingerprinted by rows, config/pairing hashes and a sha256 over its
    Parquet chunks;
  * every output by sha256;
  * estimator provenance (method/PVAT versions, RNG derivation, settings) sits in the
    experiment locks.
* **Not committed but regenerable:**
  * raw Parquet corpora and traces (`results/`, `traces/`, git-ignored, hundreds of MB),
    regenerated by the commands in `docs/workflow.md`; their hashes are in the manifests;
  * RQ7 per-replicate CSVs (14 MB, deterministic, ~6 min).
