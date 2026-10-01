# FHR3B scope (locked design)

**Question.** How should FullHouse spend a finite simulation budget so that a Swiss-style
poker-bot competition reliably identifies the strongest agents?

The object of study is the whole tournament mechanism. One independent observation is one
complete tournament replication:

```text
field -> tables -> poker outcomes -> cumulative standings -> standings-dependent Swiss reassignment
      -> further rounds -> final leaderboard -> top-6 qualification set
```

FHR3B is about the reliability of that mechanism. The lower-level question of pairwise
evaluation variance belongs to FHR3A, which is a separate note; FHR3B does not change its
manuscript, figures F1–F6, claims or corpora.

## Research baseline (`fhr3b_baseline`, `lab60_top6`)

| parameter | value | status |
|---|---|---|
| field size N | 60 bots | research design choice |
| qualifiers K | top 6 (~10%) | research design choice |
| rounds | **40 is the initial horizon**; checkpoints 5, 10, 20, 30, 40 | a starting point, **not** an assumption that 40 rounds suffice. If reliability is still improving at 40, the experiment extends to 60, 80, 120 or further (`fhr3b run --horizon R`) |
| hands per match | 400 | retained from the public 2026 engine |
| round 1 | deterministic seeded shuffle | research design choice |
| later rounds | standings-dependent Swiss assignment | public 2026 engine rule |
| score | raw cumulative chip delta; public 2026 tiebreaks | public 2026 engine rule |
| publication modes | **AoF4, NLHE4, NLHE6** | PLO is removed from FHR3B |

The public 2026 FullHouse engine is architectural provenance only. N, K, the 40-round
horizon and the round-1 order are research choices, not 2026 settings. The historical record,
with its unknowns, is `historical_2026_reconstruction`
(`docs/fhr3b/2026_protocol_audit.md`). The historical operational validation (H) stays
blocked until its missing values are supplied.

## Match semantics

**NLHE4 and NLHE6** follow the public 2026 match rule:

* every Swiss match starts every bot at 100 BB;
* stacks persist between hands within the match, with no rebuys;
* a bot at zero is out for the rest of the match, and survivors play on with their actual
  stacks, including short, deep and asymmetric effective stacks;
* each new Swiss round is a new match, starting again at 100 BB;
* the standing is the cumulative chip delta over matches.

Dynamic stack management is therefore part of the measured skill. Busting is not treated as a
defect in itself.

**AoF4** keeps its format rule: every hand at 8 BB (reset each hand).

## Reference rankings (diagnostics, never scores)

* **`mu_field`**: long-run expected performance against the controlled field, estimated by
  matched k-lane duplicate evaluation. It gives the static strength hierarchy.
* **`mu_swiss`**: long-run expected performance under the Swiss process itself, estimated from
  many complete tournaments.

Neither is "true poker skill". Finite tournaments are assessed for **accuracy** against each
reference and for **repeatability** across independent replications. Disagreement between the
two references is a finding in its own right.

## Experiments

* **A. Rounds to reliability.** Qualification and ranking reliability at 5, 10, 20, 30 and 40
  rounds. These are exact prefixes of the same tournaments, extended beyond 40 if needed.
* **B. Fixed total poker budget.** 10 × 1600, 20 × 800 and 40 × 400 hands per bot. Is compute
  better spent on more Swiss opponents or on more precision within each match?
* **C. Adaptive Swiss vs frozen schedule.** A diagnostic of how early poker noise is amplified
  through result → standings → future opponents → future results. It is not an additive
  variance decomposition, and not necessarily a proposed format.
* **D. Ordinary vs duplicate play at equal simulator cost.** A k-player table becomes k
  duplicate lanes:
  * the same initial stacks and the same chance stream;
  * bots rotated cyclically so each occupies every seat once;
  * independent stack trajectories and bot state in every lane, with no information passing
    between lanes;
  * per-bot chip deltas aggregated only after the whole match.

  The comparison normalises by played work. The question is whether FullHouse should spend
  compute on duplicate trajectories or on more ordinary poker, not whether duplication reduces
  variance in isolation. **Status: implemented (not yet run).** The same construction provides
  the matched `mu_field`.

## Metrics

* **Primary (qualification):**
  * expected number of changed qualifiers;
  * expected top-6 overlap;
  * per-bot P(qualify);
  * number of bots with ambiguous qualification.
* **Supporting:**
  * Kendall tau;
  * Spearman correlation;
  * mean absolute rank displacement;
  * pairwise inversion probability against the reference strength gap;
  * top-6 overlap with the reference top 6 (accuracy).

All uncertainty is computed over tournaments. Hands, matches and rounds are never replicates.

## Controlled fields

| field | purpose |
|---|---|
| `spread` | broad strength distribution with a separated rank-6/rank-7 boundary |
| `crowded_cutoff` | several genuinely similar bots, of different strategies, straddling the boundary |
| `style_diverse` | deliberate balance of observed style across strength strata |

Non-transitive (matchup) structure is **measured, never selected on**. The former
`matchup_sensitive` field and its gate are retired.

The bots are synthetic experimental instruments: transparent, stateless FHR3 policy families.
For NLHE, FHR3B uses `fhr3b_heuristic`, the FHR3A heuristic with correct heads-up blind roles. The
FHR3A family misread heads-up roles, which persistent-stack busts make common (23–53% of hands).
They are not models of human professionals. Selection rules and the realism audit are in
`docs/fhr3b/FIELDS.md` and `reports/fhr3b/field-calibration/FIELD_CALIBRATION_REVIEW.md`.

## Caveats every write-up must state

* **Stateless agents (D5).** Within-match opponent modelling is under-represented. The match
  runner exposes the rolling previous-hand history, as the public 2026 engine does, but the
  shipped FHR3 agents condition only on the current hand's observation (including all stacks).
* **Weak stack-depth adaptation.** In the replay audit, NLHE preflop VPIP is flat across stack
  depth; only all-in propensity rises when short. Stack skill is expressed mainly through
  commitment thresholds and pot odds.
* **Rule differences across modes.** AoF resets stacks every hand; NLHE carries them.
  Cross-mode contrasts compare whole formats.
* **Conditional results.** Every result is conditional on the constructed fields and on the
  research protocol. None of it describes the 2026 event directly.
