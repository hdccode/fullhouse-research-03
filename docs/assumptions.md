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
