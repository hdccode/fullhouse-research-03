# Variant definitions (research benchmark rules)

These are FHR3 research benchmarks. They are **not** declarations of FullHouse
2027 competition modes.

Common to all formats: cash-game reset (every hand starts from the configured
stack for every seat), no rake, fixed button unless stated (seat 0 = SB, seat k−1
= button), PokerKit resolves betting, pots, side pots and showdowns. Split pots
give odd chips to the first winner in seat order (PokerKit rule). Folding when a
check is free is illegal in every format.

| format | variant | config | deal layout | protocol | trace |
|---|---|---|---|---|---|
| 4-max AoF 8BB | `aof` | `configs/aof_4max_8bb.yaml` | board-h2-k4 | fhr3-matched-v1 | PHH |
| 4-max NLHE 100BB | `nlhe` | `configs/nlhe_4max_100bb.yaml` | board-h2-k4 | fhr3-matched-v1 | PHH |
| 6-max NLHE 100BB | `nlhe` | `configs/nlhe_6max_100bb.yaml` (+20/50BB) | board-h2-k6 | fhr3-matched-v1 | PHH |
| 6-max Crazy Pineapple | `crazy_pineapple` | `configs/cp_6max_100bb.yaml` | board-h3-k6 | fhr3-matched-v1 | JSON |
| 6-max PLO 100BB | `plo` | `configs/plo_6max_100bb.yaml` | board-h4-k6 | fhr3-matched-v1 | PHH |
| 6-max NLHE Bomb Pot | `bomb_pot` | `configs/bomb_6max_100bb.yaml` | board-h2-k6 | fhr3-matched-v1 | JSON |
| 6-max Nit Game | `nit_game` | `configs/nit_6max_100bb.yaml` | board-h2-k6 | fhr3-nit-round-v1 | PHH per hand |

Deal layout `board-h{h}-k{k}`: seat p receives `deck[h·p : h·(p+1)]`, then the
runout burn, flop×3, burn, turn, burn, river.

## NLHE (`nlhe`)
PokerKit `NoLimitTexasHoldem`, blinds 0.5/1 BB (50/100 chips), min bet 1 BB.

## Pot-Limit Omaha (`plo`)
PokerKit `PotLimitOmahaHoldem`: 4 hole cards, pot-limit betting (raise-to maximum
= pot limit, e.g. 3.5 BB for the first raise preflop), showdown with exactly two
hole cards and exactly three board cards.

## Crazy Pineapple (`crazy_pineapple`)
3 hole cards; normal NLHE preflop and flop betting. **Discard point: after the
flop betting round ends (or is skipped because players are all-in), before the
turn burn.** Every live (non-folded) player, including all-in players, discards
exactly one hole card, in seat order starting from seat 0 (SB). Folded players do
not discard; a hand that ends before the discard point has no discards. From the
turn on, players hold two cards and showdown is ordinary Hold'em.

Implementation: the discard is an FHR3 `ActionKind.DISCARD` decision issued by
the adapter (agents see `LegalDiscards`); PokerKit's own draw mechanism is not
used because it always deals replacement cards. A per-hand PokerKit hand type
evaluates the kept two cards at showdown (a showdown before a registered discard
raises). Validated by a sequencing oracle and a showdown oracle
(`tests/test_crazy_pineapple.py`).

External check (go_trumpcards, `internal/domain/Pineapple.go` at commit
`26642803`): its Crazy Pineapple agrees on 3 hole cards, normal preflop betting,
flop dealt, flop betting completed, then one discard phase in which folded
players are skipped and every other player (all-in players included) discards
down to 2, followed by Hold'em-style showdown. **Divergence:** when at most one
player still has chips after *preflop* betting, go_trumpcards deals the flop and
runs straight to showdown without its discard phase, evaluating all 3 hole cards.
We treat that as an implementation edge case (its own discard phase explicitly
includes all-in players, and its plain-Pineapple path discards after a preflop
all-in), not a rule: FHR3 always holds the discard after the flop, including when
everyone is all-in (`test_preflop_all_in_still_discards_and_showdown_uses_kept_cards`).
In the CP pilot this situation arises in ~0.25% of hands.

## NLHE Bomb Pot (`bomb_pot`, single board)
Every seat posts `options.ante_bb` (default 2 BB) as an ante; no blinds; **no
preflop betting**: street 0 of the custom PokerKit game deals hole cards, burns,
and deals the flop. The first strategic decision is on the flop, seat 0 (SB seat)
first to act, then turn and river as in NLHE; min bet 1 BB. Stacks are
`stack_bb − ante_bb` behind at the first decision. Double-board bomb pots are
not implemented (appendix-only if ever needed).

## Nit Game (`nit_game`)
NLHE hands inside a **nit round** (block protocol `fhr3-nit-round-v1`):
* At the start of every round nobody holds a nit button (fresh state in every
  block, so blocks remain independent).
* After each hand every player whose net chip result in that hand is positive
  receives a button (kept for the rest of the round).
* When at most one player lacks a button the round ends. If exactly one lacks it,
  that player (the nit) pays `options.nit_penalty_bb` (default 5 BB) to every
  other player. If the last buttons are won simultaneously, nobody pays.
* If `options.max_hands` (default 60) is reached first, the round ends with no
  payment (`truncated`).
* The dealer button rotates one seat per hand (table seat t sits in position
  (t − h) mod k in hand h). Stacks reset every hand; only buttons persist.
* Buttons are public (`Observation.extra["nit_buttons"]`, by position).

In a block each seat/side plays one full round; hand h of the A-round and the
B-round use the same deal (per-hand chance key), so they are matched hand by hand
while both last. Round lengths can differ between A and B; BB/100 figures for the
Nit Game therefore use the mean candidate hands per side (a ratio
approximation), while block-level quantities are exact.

**D and BB/100 include nit-penalty transfers.** In the 10k pilot the large mean
gaps (+10 to +30 BB/100) are almost entirely transfers (e.g. p2: +14.97 of +14.50
BB/block; chip-play gap −1.0 BB/100, z −1.0), while chip play carries ~75–85% of
var(D). Report the transfer/chip split (`variant_json` per block) alongside Nit
effects.

## All-in or Fold (`aof`)
NLHE engine with legal actions restricted to fold and all-in (open shove or
all-in call); 4-max, 8 BB equal stacks, blinds 0.5/1, no ante. Payoffs are
verified hand-by-hand against aof-ml's own `AoFSimulator` (same odd-chip order
SB, BB, CO, BTN).

Known convention difference, found by the randomized oracle test (seed 80397):
* When a split pot leaves a remainder of 2 or more chips (e.g. a three-way chop),
  PokerKit, the FHR3 engine, gives the whole remainder to the first winner in seat
  order. aof-ml instead hands the chips out one at a time.
* Winners and totals are identical, and the difference is at most (winners − 1)
  chips, ≤ 0.02 BB, on rare hands.
* It is identical on the A and B sides of a matched block, so D is unaffected. The
  all-in EV estimator deliberately replicates PokerKit's rule.
* The frozen corpora use PokerKit's rule. The oracle test accepts exactly this
  redistribution and nothing else.

## Agent families per format

| format | kind | notes |
|---|---|---|
| NLHE, bomb pot | `heuristic` | bomb pots use only its postflop logic |
| PLO | `plo_heuristic` | Omaha preflop score, 2+3 postflop features |
| Crazy Pineapple | `cp_heuristic` | 3-card preflop percentile, discard keeps best pair |
| Nit Game | `nit_heuristic` | hungrier without a button; `nit_looseness=1, nit_call_shift=0` = nit-unaware |
| AoF | `aof_policy`, `aof_heuristic` | production policy v2 (vendored), transparent heuristics |

Pairings per format: `p1` small perturbation, `p2` moderate style gap, `p3`
larger gap, `c0` self-play control (must give D = 0). Bomb pot `p1` perturbs
postflop aggression (looseness only affects preflop, which bomb pots skip). Nit
Game adds `p4` nit-aware vs nit-unaware. AoF: `p1` production v2 vs a 10% blend
with a loose heuristic, `p2` production v2 vs heuristic, `p3` heuristic styles.
