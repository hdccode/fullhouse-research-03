# REFERENCES — citation handoff

**Status column:**
* **V** = venue, pages and identifier checked by web search on 2026-09-29;
* **M** = from memory, not verified this session (check before submission);
* **S** = software, cite by repository and pinned version/commit
  (`docs/external_references.md`).

## Original methods (cite where the method is used)

| # | reference | supports | status |
|---|---|---|---|
| R1 | Burch, N., Schmid, M., Moravčík, M., Morrill, D., Bowling, M. (2018). *AIVAT: A New Variance Reduction Technique for Agent Evaluation in Imperfect Information Games.* Proc. AAAI 32(1). arXiv:1612.06915. | AIVAT (C6, F5) | V |
| R2 | White, M., Bowling, M. (2009). *Learning a Value Analysis Tool for Agent Evaluation.* Proc. IJCAI 2009, pp. 1976–1981. | MIVAT; fitted value function (C6) | V |
| R3 | Zinkevich, M., Bowling, M., Bard, N., Kan, M., Billings, D. (2006). *Optimal Unbiased Estimators for Evaluating Agent Performance.* Proc. AAAI 2006, pp. 573–578. | advantage-sum / DIVAT framework; zero-mean corrections | V |
| R4 | Billings, D., Kan, M. (2006). *A Tool for the Direct Assessment of Poker Decisions.* ICGA Journal 29(3). | DIVAT origin (background) | M |
| R5 | Bowling, M., Johanson, M., Burch, N., Szafron, D. (2008). *Strategy Evaluation in Extensive Games with Importance Sampling.* Proc. ICML 2008. | imaginary observations / importance sampling (background) | M |
| R6 | Waudby-Smith, I., Arbour, D., Sinha, R., Kennedy, E. H., Ramdas, A. (2024). *Time-uniform central limit theory and asymptotic confidence sequences.* Annals of Statistics 52(6), 2613–2640. doi:10.1214/24-AOS2408. arXiv:2103.06476. | the asymptotic CS used in RQ7 (C5, F6) | V |
| R7 | Howard, S. R., Ramdas, A., McAuliffe, J., Sekhon, J. (2021). *Time-uniform, nonparametric, nonasymptotic confidence sequences.* Annals of Statistics 49(2). doi:10.1214/20-AOS1991. arXiv:1810.08240. | the normal-mixture boundary (the confseq oracle), CS background | V |
| R8 | Robbins, H. (1970). *Statistical methods related to the law of the iterated logarithm.* Annals of Mathematical Statistics 41(5). | origin of the normal-mixture boundary (optional) | M |

## Directly related work (must cite and discuss)

| # | reference | why | status |
|---|---|---|---|
| R9 | Li, B., Chen, Y., Huang, L. (2026). *AV-AIVAT: 74x Cheaper Agent Evaluation with Certified Anytime-Valid Stopping in Imperfect-Information Games.* arXiv:2608.06362. | the closest prior work: AIVAT plus confidence sequences for heads-up NLHE with LLM agents. It constrains our novelty wording (EVIDENCE_MAP §5) and needs a like-for-like comparison with our 1.72× (EVIDENCE_MAP §4 item 9). | V (abstract only; read in full) |
| R10 | Johari, R., Koomen, P., Pekelis, L., Walsh, D. (2017). *Peeking at A/B Tests: Why it matters, and what to do about it.* Proc. KDD 2017, pp. 1517–1525. doi:10.1145/3097983.3097992. | peeking failure in practice; always-valid inference (C4) | V |
| R11 | Johari, R., Koomen, P., Pekelis, L., Walsh, D. (2022). *Always Valid Inference: Continuous Monitoring of A/B Tests.* Operations Research 70(3). doi:10.1287/opre.2021.2135. | journal version of R10 (cite one) | V (listing) |
| R12 | Armitage, P., McPherson, C. K., Rowe, B. C. (1969). *Repeated significance tests on accumulating data.* JRSS A 132(2). | classic result that repeated testing inflates Type I error | M |

## Software (implementation citations)

| # | reference | use | status |
|---|---|---|---|
| R13 | Kim, J. (2025). *PokerKit: A Comprehensive Python Library for Fine-Grained Multivariant Poker Game Simulations.* IEEE Transactions on Games 17(1), 32–39. arXiv:2308.07327. Software `pokerkit==0.7.5`. | game engine for all formats | V + S |
| R14 | PVAT, uoftcprg/pvat (MIT), `pvat==0.0.0.dev2`; upstream commit `500800be`. | MIVAT/AIVAT implementation (with FHR3 adapter and tests) | S |
| R15 | confseq, gostevehoward/confseq (MIT), wheel 0.0.9. | external boundary oracle (tests only) | S (optional) |
| R16 | aof-ml production policy v2 (FullHouse internal) | AoF candidate policy | S (internal) |

## Background (cite only if the draft discusses it)

| # | reference | status |
|---|---|---|
| R17 | Bard, N., Hawkin, J., Rubin, J., Zinkevich, M. (2013). *The Annual Computer Poker Competition.* AI Magazine 34(2). Duplicate-match evaluation. | M |
| R18 | Moravčík, M., et al. (2017). *DeepStack: Expert-level artificial intelligence in heads-up no-limit poker.* Science 356. AIVAT in practice. | M |
| R19 | Brown, N., Sandholm, T. (2019). *Superhuman AI for multiplayer poker.* Science 365. Variance-reduced evaluation in 6-max. | M |

Do not pad: R4, R5, R8, R12 and R17–R19 are optional. The GPL-3 `expectation` repository
was inspected only and does not need a citation.
