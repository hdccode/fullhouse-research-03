# FullHouse 2026 protocol audit (FHR3B hard gate)

Audit date: 2026-09-29. Outcome: **the exact production tournament code was not found.**
FHR3B therefore implements `reconstructed_2026`, not `exact_2026`. This document records
what each protocol fact rests on.

## Classification

| class | meaning |
|---|---|
| VERIFIED_FROM_CODE | read in the public canonical engine source at the pinned commit |
| VERIFIED_FROM_EVENT_CONFIG | event configuration in the same repo (DB schema defaults, launch-prep commits) |
| VERIFIED_FROM_DOCUMENTATION | organiser documentation (engine README, fullhousehackathon.com captures) |
| UNKNOWN | not recoverable, or only third-party/participant reports, or sources conflict |

Participant reports are never enough to verify a fact. They are listed as evidence under UNKNOWN.

## Search record (in the prescribed order)

1. **This repository and its history** (`fullhouse-research-03`). There is no tournament code.
   FHR3A docs say Swiss ranking is out of scope (`paper/FHR3A_SCOPE.md`).
2. **Local sibling repositories.**
   * `~/fullhouse-website`: site source, its git history (53 commits), and captured
     pages in `evidence/`. Documentation only.
   * `~/aof-ml`: AoF solver, no tournament code.
   * `~/fullhouse-contact-finder`, `~/FishKiller-mannyv4`: unrelated.
   * No local engine checkout exists.
3. **Git remotes and history.** The `hdccode` GitHub account (the owner of this repo) has
   no engine repository.
4. **Other local FullHouse material** (`~/Downloads`, `~/Documents`). Only keyword
   searches were run. Nothing about the tournament format was found. Unrelated business
   documents were not used.
5. **Public source.** Participants' repositories cite `github.com/uzlez/fullhouse-engine`
   as the official engine. GitHub now redirects that name to **`github.com/mbatv/fullhouse-engine`**.
   The API resolves `uzlez/fullhouse-engine` to `mbatv/fullhouse-engine`, and all commits
   come from the organiser account (`uzlez` / "Misha B" / "MB"). Four public copies
   (`kosunghun317`, `MatusGib`, `TobyCoad`, `Pav1602`) share the root commit `f5247a9`.
   * The copies that contain `a80b269` have identical `engine/tournament.py`,
     `engine/game.py`, `sandbox/match.py` and `db/schema.sql`, apart from participant
     edits made after the event.
   * No copy has a later organiser commit.

### Authoritative source pinned

| item | value |
|---|---|
| repository | https://github.com/mbatv/fullhouse-engine (formerly `uzlez/fullhouse-engine`) |
| commit | `a80b26957db5f5515d9273a15d1b73aadf8985db` (2026-05-24, last organiser commit before the 1 June qualifier) |
| `engine/tournament.py` | sha256 `9759284729099b98d7e784824fc7ff8705c1fa846c6b8ebede848832e4a2325a` (vendored byte-identically, MIT, `tests/data/fhr3b/fullhouse_engine_a80b269/`) |
| `sandbox/match.py` | sha256 `527ce69a451e825f680ad3b8aa92176d795534e87b01e387211d86074de760d3` |
| `engine/game.py` | sha256 `95c87ade625041f7cc6221d6cc36eac11f89f3f452753b20a402126c31f7e9c2` |
| `db/schema.sql` | sha256 `9aa015a405f89ec31ad218286c560fc69a42346c6486963781b08f386681b73f` |
| `README.md` | sha256 `d63a0a5c6560e979e7a52eba159469f58fdd4b1821732e1d2de631cf3b71a5f8` |

**Why this is not `exact_2026`.** The docstring of `engine/tournament.py` says:

> "The production match queue (BullMQ workers) ships its own copy in the private ops
> repo; this module is the canonical reference for participants."

That private ops repository is not available. The production worker may have changed the
rules, added randomness or handled edge cases differently, and none of that can be checked.
Every manifest records `production_equivalence: UNVERIFIED`.

## Protocol facts

| # | fact | recovered value | class | evidence |
|---|---|---|---|---|
| 1 | game | No-Limit Hold'em, 2–9 seats per table | VERIFIED_FROM_CODE | `engine/game.py` (`MAX_PLAYERS = 9`) |
| 2 | blinds / starting stack | 50 / 100, 10,000 chips (100 BB) | VERIFIED_FROM_CODE | `SMALL_BLIND`, `BIG_BLIND`, `STARTING_STACK` |
| 3 | table size | 6 | VERIFIED_FROM_CODE + DOCUMENTATION | `swiss_pairing(table_size=6)`; README "6-bot tables"; website "4-6-player tables" |
| 4 | hands per table match (H) | **400** | VERIFIED_FROM_CODE + EVENT_CONFIG + DOCUMENTATION | `run_match(n_hands=400)`; `matches.n_hands default 400`. Commit `8863542` (2026-05-05) raised it from 200 to 400, and `28b6d7e` says "Verify before launch ... match rows use n_hands=400". README: "400 hands per match". |
| 5 | match stack rule | stacks carry over between hands; no rebuy; busted bots sit out; the match ends when fewer than 2 bots have chips | VERIFIED_FROM_CODE | `sandbox/match.py` `run_match` |
| 6 | match score | `final_stack − 10,000`, floor −10,000 (and at most +50,000 at 6 seats) | VERIFIED_FROM_CODE | `chip_delta`; commit `8863542` message |
| 7 | dealer rotation | a counter goes up by one per hand; dealer = `alive[counter mod len(alive)]`; SB and BB follow; heads-up the dealer is SB | VERIFIED_FROM_CODE | `run_match`, `PokerEngine._sb_seat` |
| 8 | seat order | seats follow the table's list order, which is standings order | VERIFIED_FROM_CODE (reference/demo) | `demo.py` passes table order to `run_match` |
| 9 | Swiss pairing | sort by `-cumulative_delta` (stable), then consecutive slices of `table_size` | VERIFIED_FROM_CODE | `swiss_pairing` |
| 10 | incomplete tables | a remainder smaller than `table_size` is folded into the last table; a field smaller than one table plays as one table | VERIFIED_FROM_CODE | `swiss_pairing` |
| 11 | byes | none | VERIFIED_FROM_CODE | no bye concept anywhere |
| 12 | standings score | raw cumulative chip delta, not normalised | VERIFIED_FROM_CODE | `compute_standings`; `record_match_result` upserts `cumulative_delta` |
| 13 | tiebreaks | cumulative delta DESC, matches played ASC, best single-match delta DESC, `bot_id` ASC | VERIFIED_FROM_CODE | `compute_standings` (commit `eb61c4b` "tiebreakers") |
| 14 | display rank | `dense_rank()` over cumulative delta | VERIFIED_FROM_CODE | `db/schema.sql` |
| 15 | randomisation within equal standings | none (stable sort) | VERIFIED_FROM_CODE | `swiss_pairing` |
| 16 | round-1 order | reference: the order of the input bot list | VERIFIED_FROM_CODE (reference); **production UNKNOWN** | `demo.py` |
| 17 | advancement cut | top 64 in full tiebreak order | VERIFIED_FROM_CODE + EVENT_CONFIG + DOCUMENTATION | `select_finalists(n=64)`; `n_finalists default 64` (`28b6d7e`); README "Top 64 advance"; website "top 64 bots advance by chip EV" and "64 finalists" |
| 18 | card seeding | `random.Random(seed*1000003 + hand_num)`, or unseeded when `seed=None` | VERIFIED_FROM_CODE; production seed UNKNOWN | `run_match`, `_build_deck` |
| 19 | invalid action / timeout / crash | treated as a fold; the bot stays in the tournament | VERIFIED_FROM_CODE + DOCUMENTATION | `_validate`, README rules |
| 20 | disqualification | stated in the rules (collusion, network use, ...) | VERIFIED_FROM_DOCUMENTATION; enforcement UNKNOWN | README |
| 21 | **number of Swiss rounds (R)** | **UNKNOWN** | UNKNOWN | see "Round count" below |
| 22 | field size N | **UNKNOWN** | UNKNOWN | website "300+ bots", "400+ participants" (2026 page), "600+ entrants" (later copy); participant repos "~300 entrants", "500+ entrants"; entrants ≠ bots |
| 23 | qualifier structure | README: one online qualifier on 1 June, a patch window on 2 June (one bot replacement, "your bot ID stays the same"), finals on 5 June | VERIFIED_FROM_DOCUMENTATION (pre-event) | README; participants describe "Qualifier 1" and "Qualifier 2", so how they were combined is **UNKNOWN** |
| 24 | handling when N mod 6 ∈ {4, 5} | the reference folding creates a 10–11 seat table, which `run_match` rejects (`2 <= n <= 9`) | **UNKNOWN** (the reference is inconsistent here) | `swiss_pairing` vs `run_match` assert |
| 25 | finals logic | README (pre-event): top-64 single-elimination bracket. Website: "Bracket elimination — best of 200 hands per match". A participant describes finals Phase 1 "~40 Swiss-paired 6-max matches, 800 hands each, cumulative chips" and then a final table. | **UNKNOWN / conflicting** | FHR3B models the qualifier only |
| 26 | information available to bots | the last 200 actions of the current match (`match_action_log`) | VERIFIED_FROM_CODE | `sandbox/match.py` |

### Round count

There is no organiser source for the qualifier's round count:

* The DB default is `total_rounds = 3`. Commit `28b6d7e` aligned *other* defaults with the
  "documented qualifier rules" and left this one alone.
* The 3-round demo, and the README's "full tournament simulation (3 Swiss rounds)", describe
  the local demo.
* The README's event format says only "multiple rounds".
* One participant reports "15 more games played" in qualifier 2.
* Another describes ~40 Swiss matches of 800 hands, but for the **finals** "Bubble" phase.

**Decision.** The lab baseline uses **R0 = 40**, labelled *provisional*
(`configs/fhr3b/protocols/reconstructed_2026.yaml`, `notes`). It matches the scale of the
only multi-round report and gives the intended sweep 5/10/20/30/40. Changing R0 is a
one-line change, and the sweep and budget generators derive everything from it. Every R
value gets its own protocol hash. **Confirm R0 with the organisers before publication.**

## What `reconstructed_2026` implements

| aspect | implementation | relation to the facts above |
|---|---|---|
| pairing, standings, tiebreaks, cut | line-for-line port (`src/fhr3/tournament/swiss.py`) | a golden test compares it with the vendored reference on 40 random histories |
| match | `persistent_no_rebuy`: carried stacks, bust-out, early end, the 2026 dealer counter, heads-up dealer = SB | facts 5–7 |
| score | raw cumulative chip delta | fact 12 |
| H | 400 | fact 4 |
| table size | 6 in the NLHE production mode | fact 3 |
| cut | K = 64 for the 2026 protocol; the lab uses K = 6 (see below) | fact 17 |
| R | 40, **provisional** | fact 21 |
| round-1 order | **seeded shuffle** of the field (reconstruction choice) | fact 16: the reference uses input order and the production order is unknown. A fixed arbitrary manifest order would build structure into round 1 (for example, a strength-sorted manifest would seat the strongest bots together). |
| poker rules | FHR3's PokerKit NLHE, not the 2026 eval7 engine | these are not rule-identical in edge cases (min-raise snapping, auto-fold of invalid actions, odd-chip splits); FHR3 agents always act legally |
| card randomness | FHR3 keyed BLAKE2b streams | deliberately not the production card sequence |
| bots | FHR3 stateless synthetic agents | real 2026 bots could model opponents within a match (fact 26) |

## Operational 2026 validation (Experiment D): PENDING

`configs/fhr3b/protocols/operational_2026_pending.yaml` has `status: pending`. The runner
refuses it and prints the missing facts:

* N per qualifier;
* R per qualifier;
* how Q1 and Q2 were combined;
* the table rule for N mod 6 ∈ {4, 5};
* production round-1 order;
* whether standings were cumulative or averaged;
* incidents: timeouts, disqualifications, withdrawals;
* whether the production worker's Swiss code equals the reference.

K = 64 is the only verified operational fact. No operational configuration was invented.

## 2026 real bots (optional validation)

No archived 2026 submissions exist locally. Public participant repositories do exist, for
example:

* `advitrocks9/fullhouse-bot` (qualified 12th, 15th in the final);
* `ZealousEar/PokerBot`, which pins its finals artifact `v_final.zip` by sha256;
* `txnujk09/fullhouse-poker-bot`, `luv-barnwal/crimsonbot-fullhouse-poker-bot`,
  `gonfdcg/fullhouse-poker-bots`.

They implement the 2026 `decide(game_state) -> dict` interface on eval7. Many draw
Monte Carlo samples without a seed, and many keep opponent models across hands. A
reproducible adapter would need all of the following:

* an FHR3 `Observation` to 2026 `game_state` translator, including `match_action_log`;
* sandboxed subprocess execution with the 2026 time and memory limits;
* control of each bot's RNG, which is impossible for bots that seed from time or
  `os.urandom`.

No adapter was built. FHR3B does not depend on these bots.
