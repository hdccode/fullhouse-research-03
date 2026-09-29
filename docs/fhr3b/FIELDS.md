# FHR3B fields

## Principle

No bot has a "skill" label. The FHR3 agent families have transparent parameters, but they
have no credible scalar quality control. So FHR3B builds a **candidate pool**, measures long-run
balanced performance **empirically**, and selects fields from that measurement with
deterministic rules:

```text
candidate pool -> balanced calibration -> empirical mu_field -> deterministic selection -> frozen manifest
```

## Candidate pools (`configs/fhr3b/fields/<mode>/pool.json`, 96 bots per mode, frozen)

A pool crosses three things:

* **archetypes** (8): strategic styles expressible in each family.
  * NLHE / PLO / CP / Nit / bomb pot: `neutral, tight, loose, aggressive`, plus four
    override archetypes: `nit`, `station`, `maniac`, `trapper`.
  * AoF: four heuristic styles, `shover`, `caller`, the production policy v2 (`policy`), and
    a loose-blended policy.
* **perturbation scale** `e0..e3` with ε = 0, 0.10, 0.25, 0.45. e0 is the archetype itself.
  Larger ε draws larger multiplicative (or additive, for `call_margin`) perturbations of
  every parameter, bounded to valid ranges. For AoF policy bots, ε sets the heuristic blend.
* **agent seeds**: 1 / 3 / 4 / 4 per scale, drawn from
  `KeyedStream("fhr3b-agent-construction", seed_family, family, archetype, scale, seed, param)`.

That gives 8 × 12 = 96 behaviourally distinct bots (checked: unique resolved versions).
Larger ε tends to move bots away from a tuned archetype, but that is **not** assumed to mean
"weaker". Strength is measured.

Each manifest entry contains:

* `bot_id, kind, params` (the exact overrides);
* `version`: implementation + params hash;
* `meta`: `archetype, scale_index, epsilon, agent_seed`.

The field hash covers the result-relevant part. `validate()` rebuilds every agent and
checks its version.

Pre-calibration fields (frozen, not for publication inference):

* `smoke12`: stratified by archetype; correctness only.
* `provisional60`: stratified; for the runtime pilot only.

## Balanced calibration (`calibration.py`)

A calibration round is a keyed uniformly random partition of the bots into tables of the
mode's size (the remainder sits out). Each table plays one match under the same match rules
as the research-baseline tournament (H = H0 hands, the mode's stack rule, the public engine's
dealer rotation). Then:

* `mu_field(i)` = mean chip delta per match at a uniformly random table. Its SE comes from a
  bootstrap over groups of rounds.
* Matchup: `M[i,j] = E[delta_i | j at the table] − mu_i` (presence effect), and
  `A = M − Mᵀ`.
* Hodge split on the complete graph: gradient `r_i − r_j` (transitive strength) plus a cyclic
  remainder. The expected noise energy in each subspace is subtracted using the per-pair
  sampling variances. The result is the **debiased cyclic share**, with a round-group
  bootstrap CI. The count of cyclic sign triads is also reported.

There are two stages, with disjoint namespaces:

1. **Pool calibration** (`pool-calibration`, 2000 rounds by default), used to select fields.
2. **Field reference** (`field-reference`, 3000 rounds by default). This re-measures
   mu_field inside each frozen field, because EV is field-relative. It is the balanced
   reference for the analysis, and it confirms the construction property.

## Field selection (`selection.py`, deterministic given the frozen calibration)

| field | rule | purpose |
|---|---|---|
| `spread` | 60 bots at evenly spaced positions of the pool's mu_field ranking | easy to rank |
| `crowded_cutoff` | the 3 strongest bots, then the tightest window of 12 consecutive bots (smallest mu range) below them, then 45 evenly spaced from below the window. The crowd occupies field ranks 4–15 and straddles the top-6 cut. | a hard qualification boundary |
| matchup field | greedy backward elimination from the pool, maximising the debiased cyclic share | test the adversarial property |

The matchup field is labelled **`matchup_sensitive`** only if the 95% bootstrap lower bound
of its debiased cyclic share is ≥ 0.05 (`matrix.yaml: matchup_gate`). Otherwise it is written
as **`style_diverse`** and must not be called non-transitive.

Every selected manifest records:

* the calibration id, identity hash and **calibration digest** (sha256 over the chunk files);
* the selection parameters;
* for the matchup field, the gate result.

Selection writes each manifest once and refuses to overwrite a frozen field with different
content.

Crowding and the matchup property are properties of the pool calibration. The field-reference
report (`reference.json`) records:

* the crowd's mu range inside the field;
* the gap at the cutoff;
* the Hodge share inside the field.

If these contradict the construction, report it. Do not re-select silently.
