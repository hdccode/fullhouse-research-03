# Retired: NLHE manifests invalidated by the heads-up-role bug (2026-10-01)

The FHR3A `heuristic` agent family interprets heads-up blind roles incorrectly. It assumes
seat 1 = BB, but in FHR3/PokerKit heads-up seat 1 is the button / small blind. Every NLHE pool,
calibration, field and selection built on it is invalid for FHR3B publication work. Evidence:
`reports/fhr3b/field-calibration/retired_hu_role_bug/nlhe4/NLHE4_AUDIT.md`, section 3.

Retired here, kept for provenance only; never active:

| mode | file | hash | status at retirement |
|---|---|---|---|
| nlhe6 | pool.json | `479125f8aa79e5a6` | frozen pool (heuristic kind) |
| nlhe6 | spread / crowded_cutoff / style_diverse | `16df070db91a53bd` / `a845c2fcf1b2ed33` / `5c83ad4268c37bdc` | **were frozen; freeze revoked** |
| nlhe4 | pool.json | `e1d187eb0b4551c2` | frozen pool (heuristic kind) |
| nlhe4 | spread / crowded_cutoff / style_diverse | `e95024951ef40186` / `289e4bdb8c9f99bc` / `0a9914d3f074b147` | candidates, never frozen |
| both | smoke12 / provisional60 | — | pre-calibration fields |

Replacements use the FHR3B-local `fhr3b_heuristic` family (`src/fhr3/tournament/agents.py`),
which has identical parameter vectors and corrected heads-up roles. All of these hashes are
listed under `revoked:` in `configs/fhr3b/fields/FROZEN.yaml`; publication and pilot runs
refuse them.
