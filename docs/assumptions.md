# Assumptions that could affect the paper

1. **Cash-game reset.** Every hand starts at the configured stack for every seat;
   no stack carry-over, no rake. Results are per-hand BB, not tournament equity.
2. **Fixed button, rotating candidate.** Positions are seats (0 = SB … k−1 = BTN).
   The candidate rotates through all k seats on one deck. The reference line-up
   is fixed *relative to the candidate* (reference j always sits j+1 seats to
   the candidate's left). A different reference placement rule changes which
   reference agent the candidate faces in each position, and therefore the
   estimand, if the references are heterogeneous.
3. **One deck per block.** All 2k hands use the same Deal: seat s's cards go to
   whoever sits in seat s. Across candidate seats, the k hands of one side are
   correlated (shared board), which is why only D (not D_s) is the unit.
4. **Common random numbers are a design choice.** Shared coupling of candidate
   and reference draws reduces Var(D) without changing either policy's
   marginals. Reported σ_D values are for the stated coupling mode and are not
   comparable across modes.
5. **Chance is shared across pairings and stack depths** (same root seed ⇒ same
   decks). Pairing-level estimates are therefore correlated; comparisons across
   pairings or stacks should use paired methods or account for this.
6. **Estimand is conditional** on game config, stacks, reference population and
   agents. σ_D is not a property of "6-max NLHE".
7. **Baseline agents are heuristics.** Tail behaviour (all-in frequency, pot
   sizes) is shaped by their sizing rules. Sample-complexity conclusions should
   be checked against at least one stronger/validation agent pairing.
8. **Folding when checking is free is illegal** (PokerKit cash-game mode would
   allow it with a warning).
9. **Power calculations** use the normal approximation, n = ((z₁₋α/₂ + z_power)
   σ/Δ)². With the observed extreme kurtosis, empirical power from
   `power-sim` (block-residual resampling) is the reference for small n.
10. **Invalid blocks** are excluded from statistics but always reported; any
    non-zero count is a blocking bug, not a data-cleaning step.
11. **Agents are not re-tuned per stack depth or player count.** Preflop ranges
    are identical at 20/50/100BB (only the all-in commitment rule depends on
    stack), and 4-max uses the same seats-behind open table. Stack-depth and
    format effects on σ_D therefore include "these heuristics are more or less
    appropriate at this depth", not only the game itself.
12. **4-max reference population** `mixed3-v1` = tight, loose, aggressive (no
    neutral seat). This is a choice, not a derivation from `mixed5-v1`.
13. **Cross-format comparisons are not paired.** Configs sharing a root seed but
    with a different deal layout or block protocol (4-max vs 6-max, NLHE vs PLO /
    Crazy Pineapple, NLHE vs Nit Game) share seed material only. Observed
    corr(D) between 4-max and 6-max NLHE is ≈ 0 (−0.009 to +0.000 on 10k blocks);
    an earlier 200-block smoke estimate of 0.3–0.6 was noise and is withdrawn.
    Only same-variant, same-layout, same-protocol configs (the 20/50/100BB
    series) are paired (corr 0.69–0.85). NLHE vs bomb pot share cards but are
    different games; `fhr3 compare` labels all of this explicitly.
14. **Stack-depth results describe this benchmark population.** Paired variance
    rises strongly with stack depth *under fixed, stack-unaware heuristic
    preflop ranges*; it is not a claim about deep-stack poker in general.
15. **Format-specific rule choices** (docs/variants.md) are research definitions:
    bomb pot ante 2 BB, single board, flop-first action from the SB seat; Crazy
    Pineapple discard after the flop betting round in seat order; Nit Game penalty
    5 BB per opponent, button on positive net result, 60-hand cap, fresh state per
    block, rotating dealer; AoF 8 BB equal stacks, blinds 0.5/1.
16. **Agent families differ by format** (NLHE heuristic, PLO heuristic, CP
    heuristic, nit-aware heuristic, AoF production policy v2 + AoF heuristics).
    They share a philosophy (soft thresholds, explicit distributions), not
    strategic equivalence; σ_D across formats compares benchmark environments,
    not games in the abstract.
    **Bomb Pot is scientifically caveated.** With the NLHE family the 10k pilot
    shows ~69% showdowns, ~28% of hands with an all-in and ~80 BB mean pots, and
    very large genuine gaps: tight beats neutral by 25 BB/100 (z −5.4) and
    aggressive loses 17 BB/100 (z −2.8). The NLHE heuristic was not designed for
    six-way flops (multiway discount, 45%-of-stack commit rule), so these are
    partly agent artefacts. Bomb Pot results hold "under this benchmark family"
    only; a multiway-aware robustness pairing is needed before calling it the
    hardest format.
17. **Nit Game BB/100** uses the mean candidate hands per side (round lengths
    differ between A and B); block-level results are exact, BB/100 is a ratio
    approximation. Nit D and BB/100 **include nit-penalty transfers**, which
    account for almost all of the large mean gaps (docs/variants.md).
21. **Crazy Pineapple preflop all-ins:** FHR3 always discards after the flop,
    including all-in players; go_trumpcards skips the discard when no betting is
    possible after preflop (treated as its edge case, see docs/variants.md).
18. **AoF production policy** is the aof-ml v2 range table vendored with
    provenance; its validation status is aof-ml's (best estimate from finite
    training, with the documented mixed stress-cell result).
19. **Variance-reduced estimators** are unbiased for any fixed value function;
    their value functions must be fitted on a separate root seed and frozen
    (sha256-pinned) before evaluation. MC components (all-in preflop runouts,
    AIVAT flop samples) add a little variance but no bias.
20. **Sequential inference** uses an asymptotic CS (finite-variance, asymptotic
    time-uniform validity); coverage must be checked by simulation on streams
    resembling the observed heavy-tailed D before interpreting stopping times.
