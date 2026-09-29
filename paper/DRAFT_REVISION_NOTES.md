# DRAFT REVISION NOTES

**The preliminary manuscript is not in this repository.** A search on 2026-09-29 covered the
repo, `~/Documents`, `~/Desktop`, `~/Downloads`, the FullHouse website source (research
notes 01 and 02 only) and Spotlight for the title. It found no FHR3 draft. Section-by-section
notes on the draft itself therefore cannot be written yet.

Until then, use this checklist. It covers every result that changed during the project; a
draft written before the final freeze is likely to contain the old versions. Search the
draft for each string and apply the fix. Keep the draft's own structure; `EVIDENCE_MAP.md`
§2 says where each result belongs.

## Search-and-fix checklist

| search the draft for | likely stale content | replace with (source) |
|---|---|---|
| "±7", "7.3%", "pilot" | 10k pilot estimates σ within ±7% | required sample within ≈ 30% (0.86–1.28×); rule n ≈ 384(κ+2) (C9) |
| "60×", "~60", "570" | earlier spreads | 61× hands, 4.8× 100BB, 41× blocks, 475× wall-clock (C1) |
| "4-max", "player count" | unresolved or a player-count effect | 1.04 [0.98, 1.11] per played hand; no player-count claim (C10) |
| "77", "82–97", "all-in blocks carry" | all-in as the mechanism | pot ≥ one stack: 79–97%; all-in 81–97% as a proxy; PLO case (C2) |
| "of decisive blocks" | "0.6–22% of decisive blocks" | 0.6–22% of **all** blocks (big-pot AND decisive) (C2) |
| "hardest", "easiest", "most difficult format", "Bomb Pot requires the most" | format ranking | no global ranking; Bomb is a stress case (C1, L4) |
| "pairing" | "pairing matters as much as format" without scope | scoped to 100BB formats: 2.8–8.5× within vs 4.8× between (C7) |
| "7×", "20BB" | the stack effect without the caveat | 6.8–7.2× (CIs 5.7–8.6) and 2.0–2.1×; stack-unaware agents (C3, L5) |
| "chance", "luck", "noise", "should remove" | expectation that variance reduction collapses the burden | 12% (100BB) / 28% (20BB) / 90% (AoF) removed by all-in EV; best 100BB 42% (AIVAT) (C3, C6) |
| "strategic variance", "remaining variance is strategic" | overclaim | "strategic divergence plus chance variation not captured by the fitted value model" (C6) |
| "AIVAT" + "best" / "recommend" | AIVAT recommended unconditionally | best sample efficiency (1.72×), but a net wall-clock loss in simulation (0.91–0.94); all-in EV is the default (C12) |
| "0.27", "production", "blend" | "AoF gap unresolved" | resolved under all-in EV: +0.41 [+0.30, +0.52], z = 7.38, same blocks; report both (C6b) |
| "47%", "62.5", "peeking" | provisional peeking rates | 58.0–63.9% (IID null); 44.8% (real orderings); 8.5% wrong sign (C4) |
| "confidence sequence", "anytime", "valid at any time" | exactness claims | asymptotic; empirical miscoverage 2.4–3.4% on tested streams (C5, L7) |
| "block 204", "-27.8", "53.7" | old example values | −27.9 BB/100 [−54.0, −1.8] at block 204; full corpus +1.28 [+0.43, +2.13]; CS [−0.06, +2.61] (C14) |
| "first", "novel", "we propose" | novelty wording | see EVIDENCE_MAP §5; cite AV-AIVAT (R9) and prior methods (R1–R7) |
| "hands" used as the independent unit | inference on hands | the matched block is the unit; hands are cost translation only |
| "intrinsic", "true variance of", "variance of the game" | property of the variant | variance of D for this reference population and pairing |
| "SD" / "standard deviation" reductions quoted as sample savings | SD vs variance confusion | sample saving = 1 − variance ratio (e.g. SD ratio 0.76 = variance ratio 0.58) |

## Results a pre-freeze draft probably lacks entirely
* RQ6: every estimator number (F5, C3-kind, C6, C6b, C12).
* RQ7: every final number (F6, C4, C5, C14), including wrong-sign rates, the
  power-matched cost and the width inflation.
* Tail survival after correction (82–87%).
* The AV-AIVAT related-work discussion.

## Material to cut or move to the appendix, if present
* standardized-d collapse as a main result → appendix (true in blocks by construction);
* detailed min-N sensitivity → appendix;
* any per-pairing tables in the main text → appendix A1/A7;
* the Crazy Pineapple rule divergence, the Bomb diagnostics and the AoF odd-chip convention →
  appendix.

Once the draft is in the repo (suggested location: `paper/draft/`), these notes can be
rewritten section by section against its actual text.
