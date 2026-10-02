"""FullHouse Research #4 core publication scope: NLHE6 x three frozen fields, six unique cells each.

Publicly this is FullHouse Research #4; internal identifiers stay ``fhr3b``. The scope is the
``core_fhr4`` block of ``configs/fhr3b/matrix.yaml``; nothing else is read by the core commands.

Experiments A-D are views onto *unique* tournament cells. Cells are deduplicated by identity
hash, so a cell shared by several experiments is simulated once:

    cell                  serves
    baseline              A (prefixes 5/10/20/30/40), B (40x400), C (adaptive arm), D (ordinary arm)
    budget_half_rounds    B   (20 x 800)
    budget_quarter_rounds B   (10 x 1600)
    frozen_schedule       C   (frozen replay J = 1: replicate r replays baseline tournament r)
    dup_fewer_rounds      D   (6 lanes, 7 x 400: +5.0% scheduled work, reported, not hidden)
    dup_shorter_matches   D   (6 lanes, 40 x 67: +0.5% scheduled work)

Replication counts are not part of any identity, so extending a cell (``--range 50:100
--extend``) appends tournaments 50..99 and never recomputes 0..49. The same holds for the
matched ``mu_field`` reference: rounds are not part of the calibration identity, and an
extension 250 -> 500 appends chunks 250..499.

``build_plan`` reports what a launch would run (cells, counts, scheduled and expected played
hands, output paths, wall-time estimate, initial vs extension) without simulating anything.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fhr3.tournament.cells import Cell
from fhr3.tournament.experiments import Profile, load_matrix

CORE_KEY = "core_fhr4"
CORE_CELL_KEYS = ("baseline", "budget_half_rounds", "budget_quarter_rounds", "frozen_schedule", "dup_fewer_rounds",
                  "dup_shorter_matches")
BUDGET_KEYS = {"baseline": "baseline", "half_rounds_2x_hands": "budget_half_rounds",
               "quarter_rounds_4x_hands": "budget_quarter_rounds"}
EXPERIMENT_NAMES = {"A": "rounds-to-reliability", "B": "fixed total poker budget",
                    "C": "adaptive Swiss vs frozen schedule", "D": "ordinary vs duplicate"}
BB = 100.0


class CoreScopeError(RuntimeError):
    pass


def core_config(prof: Profile) -> dict[str, Any]:
    return load_matrix(prof.config_root)[CORE_KEY]


def check_scope(prof: Profile, cfg: dict[str, Any] | None = None) -> None:
    """The core scope is exactly NLHE6 x the three frozen fields, six cells, matching the matrix defaults."""
    cfg = cfg or core_config(prof)
    mx = load_matrix(prof.config_root)
    if list(cfg["modes"]) != ["nlhe6"]:
        raise CoreScopeError(f"core scope must be NLHE6 only, got {cfg['modes']}")
    if tuple(cfg["cells"]) != CORE_CELL_KEYS:
        raise CoreScopeError(f"core cells must be {CORE_CELL_KEYS}, got {cfg['cells']}")
    if sorted(cfg["fields"]) != sorted(("spread", "crowded_cutoff", "style_diverse")):
        raise CoreScopeError(f"core fields must be the three research fields, got {sorted(cfg['fields'])}")
    if "matched_rounds" in mx["calibration"]["field_reference"] or "rounds" in mx["calibration"]["field_reference"]:
        raise CoreScopeError("calibration.field_reference must not carry a global round count; the core scopes its "
                             "own (core_fhr4.field_reference.matched_rounds_initial)")
    if int(mx["presets"]["core"]) != int(cfg["replicates_initial"]):
        raise CoreScopeError("presets.core != core replicates_initial")
    if int(mx["presets"]["swiss_reference"]) != int(cfg["swiss_reference"]["replicates_initial"]):
        raise CoreScopeError("presets.swiss_reference != core swiss_reference.replicates_initial")
    if prof.name != "publication":
        return
    if list(prof.fields) != list(cfg["fields"]):
        raise CoreScopeError(f"publication fields {prof.fields} != core fields {list(cfg['fields'])}")
    for mode in cfg["modes"]:
        for field, want in cfg["fields"].items():
            have = prof.frozen_hash(mode, field)
            if have != want:
                raise CoreScopeError(f"{mode}/{field}: FROZEN.yaml has {have}, core scope pins {want}")
            prof.field(mode, field)  # frozen + not revoked + manifest hash matches


def core_field_rounds(prof: Profile) -> int:
    """mu_field matched rounds for the core: the core-scoped 250 (publication) or the profile's own (smoke)."""
    if prof.name == "publication":
        return int(core_config(prof)["field_reference"]["matched_rounds_initial"])
    return prof.calibration_rounds("field", core_config(prof)["modes"][0])


def swiss_initial(prof: Profile) -> int:
    return int(core_config(prof)["swiss_reference"]["replicates_initial"])


@dataclass(frozen=True)
class CoreCell:
    key: str
    mode: str
    field: str
    cell: Cell
    experiments: tuple[str, ...]

    @property
    def label(self) -> str:
        return f"{self.key} {self.mode}/{self.field} [{','.join(self.experiments)}]"

    @property
    def depends_on(self) -> Cell | None:
        """Frozen replicate r needs source (baseline) tournament r on disk."""
        return self.cell.source if self.cell.kind == "frozen_replay" else None


def _experiment_cells(prof: Profile, mode: str, field: str, j: int) -> list[tuple[str, str, Cell]]:
    """(experiment, cell key, cell) for A-D before deduplication."""
    out: list[tuple[str, str, Cell]] = [("A", "baseline", prof.cell(mode, field, "baseline"))]
    for alloc, c in prof.budget_cells(mode, field):
        out.append(("B", BUDGET_KEYS[alloc.label], c))
    src, frozen, _adaptive_replay, _ = prof.schedule_cells(mode, field, j)
    out += [("C", "baseline", src), ("C", "frozen_schedule", frozen)]
    for label, c in prof.duplicate_cells(mode, field):
        out.append(("D", "baseline" if label == "ordinary" else label.split()[0], c))
    return out


def core_cells(prof: Profile, fields: list[str] | None = None, keys: list[str] | None = None) -> list[CoreCell]:
    """The deduplicated core cells, ordered by cell key then field (all baselines run first)."""
    cfg = core_config(prof)
    mx = load_matrix(prof.config_root)
    j = int(mx["experiments"]["frozen_schedule"]["replays_per_source"])
    fields = list(fields or cfg["fields"])
    by_field: dict[tuple[str, str], dict[str, CoreCell]] = {}
    for mode in cfg["modes"]:
        for field in fields:
            seen: dict[str, tuple[str, Cell, list[str]]] = {}
            for exp, key, c in _experiment_cells(prof, mode, field, j):
                h = c.identity_hash
                if h in seen:
                    if seen[h][0] != key:
                        raise CoreScopeError(f"{mode}/{field}: cell {h} is both {seen[h][0]} and {key}")
                    if exp not in seen[h][2]:
                        seen[h][2].append(exp)
                else:
                    seen[h] = (key, c, [exp])
            got = {key: CoreCell(key, mode, field, c, tuple(exps)) for key, c, exps in seen.values()}
            if len(got) != len(seen) or tuple(sorted(got)) != tuple(sorted(CORE_CELL_KEYS)):
                raise CoreScopeError(f"{mode}/{field}: expected unique cells {CORE_CELL_KEYS}, got {sorted(got)}")
            by_field[(mode, field)] = got
    want = list(keys or CORE_CELL_KEYS)
    bad = sorted(set(want) - set(CORE_CELL_KEYS))
    if bad:
        raise CoreScopeError(f"unknown core cells {bad}; have {CORE_CELL_KEYS}")
    return [by_field[mf][k] for k in CORE_CELL_KEYS if k in want for mf in by_field]


# ------------------------------------------------------------------ work accounting
def lanes(cell: Cell) -> int:
    return cell.protocol.table_size if cell.protocol.match_format == "duplicate" else 1


def scheduled_hands(cell: Cell) -> int:
    """Scheduled table-hands per tournament: R x tables/round x H x lanes (before early match ends)."""
    p = cell.protocol
    if cell.field.n % p.table_size:
        raise CoreScopeError(f"{cell.field.field_id}: N={cell.field.n} does not divide into {p.table_size}-max tables")
    return p.rounds * (cell.field.n // p.table_size) * p.hands_per_match * lanes(cell)


def played_ratio(hands_per_match: int, ratios: dict[str, float]) -> float | None:
    r = {int(k): float(v) for k, v in ratios.items()}
    return r.get(hands_per_match)


def field_reference_scheduled(prof: Profile, mode: str, field: str, rounds: int) -> int:
    spec = prof.calibration_spec(mode, "field", field)
    k = spec.mode.table_size
    return rounds * (spec.field.n // k) * spec.lanes * spec.hands_per_match


def _wall_h(played_per_unit: float | None, units: int, workers: int, rate: float) -> dict[str, float | None]:
    """Ideal (total / rate) and wave-quantised (ceil(units / workers) waves of equal tasks) hours."""
    if played_per_unit is None or units == 0:
        return {"ideal": 0.0 if units == 0 else None, "waves": 0.0 if units == 0 else None}
    per_task_s = played_per_unit / (rate / workers)
    return {"ideal": units * played_per_unit / rate / 3600, "waves": math.ceil(units / workers) * per_task_s / 3600}


def _completed(root: Path, cell: Cell) -> set[int]:
    from fhr3.tournament.store import cell_dir, completed_replicates

    return set(completed_replicates(root, cell, verify=False)) if cell_dir(root, cell).exists() else set()


def _rounds_on_disk(root: Path, spec: Any) -> int:
    from fhr3.tournament.calibration import calib_dir

    d = calib_dir(root, spec) / "chunks"
    if not d.exists():
        return 0
    spans = sorted((int(f.stem.split("_")[1]), int(f.stem.split("_")[2])) for f in d.glob("c_*.parquet"))
    n = 0
    for a, b in spans:  # contiguous prefix only
        if a != n:
            break
        n = b
    return n


# ------------------------------------------------------------------ mu_swiss precision (cheap, from pool data)
def swiss_reference_precision(prof: Profile, reports: Path, fields: list[str], options: list[int]) -> dict[str, Any]:
    """Approximate per-bot mu_swiss precision for each replicate option, from existing variance data.

    Uses the corrected NLHE6 pool calibration's per-match sd (ordinary 400-hand matches at random
    tables) of each field's bots and the pool-estimated rank-6/rank-7 gap. A bot's final score is
    the sum of R0 match deltas, so per match SE(n) ~ sd / sqrt(R0 n). Swiss opponent selection
    changes the sd, so this is a planning approximation, not a guarantee.
    """
    import json

    mode = "nlhe6"
    pb = reports / "field-calibration" / mode / "pool_bots.csv"
    sel = reports / "field-calibration" / mode / "selection.json"
    if not pb.exists() or not sel.exists():
        return {"available": False, "reason": f"missing {pb} or {sel}"}
    sd = {r["bot_id"]: float(r["sd_per_match"]) for r in csv.DictReader(pb.open())}
    gaps = json.loads(sel.read_text())["fields"]
    r0 = prof.r0
    mu_rounds = int(core_config(prof)["field_reference"]["matched_rounds_initial"])
    out: dict[str, Any] = {"available": True, "r0": r0, "basis": str(pb), "fields": {}}
    for field in fields:
        fm = prof.field(mode, field)
        s = sorted(sd[b] for b in fm.bot_ids)
        med = s[len(s) // 2] / BB
        gap = float(gaps[field]["gap_k_k1_bb"])
        rows = {}
        for n in options:
            se = med / math.sqrt(r0 * n)
            rows[str(n)] = {"se_bot_bb_per_match": se, "se_pair_diff_bb": math.sqrt(2) * se,
                            "cutoff_gap_over_pair_se": gap / (math.sqrt(2) * se)}
        k = prof.calibration_spec(mode, "field", field).lanes
        se_field_nored = med / math.sqrt(mu_rounds * k)
        out["fields"][field] = {"median_sd_per_match_bb": med, "pool_cutoff_gap_bb": gap, "options": rows,
                                "mu_field_250_se_bot_bb_if_no_duplicate_variance_reduction": se_field_nored}
    return out


# ------------------------------------------------------------------ plan
def build_plan(prof: Profile, root: Path, *, workers: int = 8, rate: float | None = None,
               replicates: range | None = None, mu_field_rounds: int | None = None,
               fields: list[str] | None = None, keys: list[str] | None = None,
               reports: Path | None = None, swiss_replicates: range | None = None) -> dict[str, Any]:
    """Everything a core launch would run; reads only configs and what is already on disk.

    ``replicates`` are tournaments per cell (for the frozen cell: source tournaments, each replayed
    J times); ``swiss_replicates`` are mu_swiss tournaments per field.
    """
    cfg = core_config(prof)
    check_scope(prof, cfg)
    tp = cfg["throughput"]
    rate = float(rate or tp["nlhe6_hands_per_s_8_workers"])
    slow_rate = float(tp["nlhe6_hands_per_s_8_workers_slow"])
    ratios = tp["played_ratio"]
    init_reps = int(cfg["replicates_initial"])
    reps = replicates if replicates is not None else range(init_reps)
    mu_init = core_field_rounds(prof)
    mu_rounds = int(mu_field_rounds or mu_init)
    fields = list(fields or cfg["fields"])
    root = Path(root)

    # mu_field (matched field reference)
    fr_rows = []
    for mode in cfg["modes"]:
        for field in fields:
            spec = prof.calibration_spec(mode, "field", field)
            done = _rounds_on_disk(root, spec)
            todo_rounds = max(0, mu_rounds - done)
            chunk = spec.chunk_rounds
            per_chunk = field_reference_scheduled(prof, mode, field, chunk)
            ratio = played_ratio(spec.hands_per_match, ratios)
            chunks = math.ceil(todo_rounds / chunk)
            fr_rows.append({
                "mode": mode, "field": field, "field_hash": spec.field.field_hash, "calib_id": spec.calib_id,
                "path": str(root / "calibration" / spec.calib_id),
                "report": f"reports/fhr3b/field-calibration/{mode}/{spec.field.field_id}/",
                "lanes": spec.lanes, "hands_per_lane": spec.hands_per_match,
                "tables_per_round": spec.field.n // spec.mode.table_size, "chunk_rounds": chunk,
                "matched_rounds_target": mu_rounds, "matched_rounds_on_disk": done, "matched_rounds_to_run": todo_rounds,
                "stage": "initial" if mu_rounds <= mu_init else "extension",
                "scheduled_hands_target": field_reference_scheduled(prof, mode, field, mu_rounds),
                "scheduled_hands_to_run": field_reference_scheduled(prof, mode, field, todo_rounds),
                "expected_played_to_run": (field_reference_scheduled(prof, mode, field, todo_rounds) * ratio
                                           if ratio is not None else None),
                "chunks_to_run": chunks,
                "wall_h": _wall_h(per_chunk * ratio if ratio is not None else None, chunks, workers, rate)})

    # tournament matrix (18 unique cells)
    rows = []
    baseline_sched = {}
    for cc in core_cells(prof, fields, keys if keys else None):
        c, p = cc.cell, cc.cell.protocol
        sched = scheduled_hands(c)
        if cc.key == "baseline":
            baseline_sched[cc.field] = sched
        ratio = played_ratio(p.hands_per_match, ratios)
        played = sched * ratio if ratio is not None else None
        have = _completed(root, c)
        j = c.replays_per_source if c.kind == "frozen_replay" else 1
        cell_reps = range(reps.start * j, reps.stop * j)  # frozen: J replays of each source tournament
        todo = [r for r in cell_reps if r not in have]
        dep_missing: list[int] = []
        if cc.depends_on is not None:
            base_have = _completed(root, cc.depends_on)
            base_will = set(reps) if (keys is None or "baseline" in keys) else set()
            dep_missing = sorted({c.source_index(r)[0] for r in todo} - base_have - base_will)
        rows.append({
            "cell": cc.key, "experiments": list(cc.experiments), "mode": cc.mode, "field": cc.field,
            "field_hash": c.field.field_hash, "kind": c.kind, "match_format": p.match_format, "R": p.rounds,
            "H": p.hands_per_match, "lanes": lanes(c), "K": p.qualify_top_k, "N": c.field.n,
            "cell_id": c.cell_id, "identity_hash": c.identity_hash, "path": str(root / c.cell_id),
            "source_cell": c.source.cell_id if c.source is not None else None,
            "scheduled_hands_per_tournament": sched, "expected_played_per_tournament": played,
            "replicates": [cell_reps.start, cell_reps.stop], "replays_per_source": j if j > 1 or c.source else None,
            "completed": len(have), "to_run": len(todo),
            "stage": "initial" if reps.stop <= init_reps else "extension",
            "scheduled_hands_to_run": sched * len(todo),
            "expected_played_to_run": played * len(todo) if played is not None else None,
            "missing_source_tournaments": dep_missing,
            "wall_h": _wall_h(played, len(todo), workers, rate)})
    for r in rows:
        b = baseline_sched.get(r["field"])
        r["scheduled_work_ratio_vs_baseline"] = r["scheduled_hands_per_tournament"] / b if b else None
        r["exact_equal_scheduled_work"] = (r["scheduled_hands_per_tournament"] == b) if b else None

    def tot(rs: list[dict], k: str) -> float:
        return float(sum(x[k] or 0 for x in rs))

    def tot_wall(rs: list[dict], k: str) -> float:
        return float(sum(x["wall_h"][k] or 0 for x in rs))

    swiss_opts = [int(n) for n in cfg["swiss_reference"]["replicate_options"]]
    sw_init = swiss_initial(prof)
    sw_reps = swiss_replicates if swiss_replicates is not None else range(sw_init)
    sw_sched = scheduled_hands(prof.cell("nlhe6", fields[0], "swiss_reference"))
    sw_ratio = played_ratio(prof.h0, ratios) or 1.0
    bytes_t = int(tp["bytes_per_tournament"]["ordinary_R40"])
    sw_rows = []
    for mode in cfg["modes"]:
        for field in fields:
            c = prof.swiss_reference_cell(mode, field)
            have = _completed(root, c)
            todo = [r for r in sw_reps if r not in have]
            sw_rows.append({
                "mode": mode, "field": field, "field_hash": c.field.field_hash, "cell_id": c.cell_id,
                "identity_hash": c.identity_hash, "path": str(root / c.cell_id), "namespace": c.namespace,
                "R": c.protocol.rounds, "H": c.protocol.hands_per_match,
                "replicates": [sw_reps.start, sw_reps.stop], "completed": len(have), "to_run": len(todo),
                "stage": "initial" if sw_reps.stop <= sw_init else "extension",
                "scheduled_hands_per_tournament": sw_sched, "scheduled_hands_to_run": sw_sched * len(todo),
                "expected_played_to_run": sw_sched * sw_ratio * len(todo),
                "wall_h": _wall_h(sw_sched * sw_ratio, len(todo), workers, rate)})
    swiss = {"enabled": bool(cfg["swiss_reference"]["enabled"]), "namespace": prof.namespaces["swiss_reference"],
             "replicates_initial": sw_init, "replicates_extension": int(cfg["swiss_reference"]["replicates_extension"]),
             "cells": {f: prof.swiss_reference_cell("nlhe6", f).cell_id for f in fields}, "rows": sw_rows,
             "options": {str(n): {"tournaments": n * len(fields), "scheduled_hands": n * len(fields) * sw_sched,
                                  "expected_played": n * len(fields) * sw_sched * sw_ratio,
                                  "wall_h": {"ideal": n * len(fields) * sw_sched * sw_ratio / rate / 3600,
                                             "waves": len(fields) * _wall_h(sw_sched * sw_ratio, n, workers,
                                                                             rate)["waves"]},
                                  "storage_mb": n * len(fields) * bytes_t / 1e6} for n in swiss_opts}}
    if reports is not None:
        swiss["precision"] = swiss_reference_precision(prof, Path(reports), fields, swiss_opts)

    totals = {
        "mu_field": {"scheduled_hands": tot(fr_rows, "scheduled_hands_to_run"),
                     "expected_played": tot(fr_rows, "expected_played_to_run"),
                     "wall_h_ideal": tot_wall(fr_rows, "ideal"), "wall_h_waves": tot_wall(fr_rows, "waves")},
        "matrix": {"tournaments": sum(r["to_run"] for r in rows), "scheduled_hands": tot(rows, "scheduled_hands_to_run"),
                   "expected_played": tot(rows, "expected_played_to_run"),
                   "wall_h_ideal": tot_wall(rows, "ideal"), "wall_h_waves": tot_wall(rows, "waves"),
                   "storage_mb": sum(r["to_run"] for r in rows) * bytes_t / 1e6},
    }
    totals["mu_swiss"] = {"tournaments": sum(r["to_run"] for r in sw_rows),
                          "scheduled_hands": tot(sw_rows, "scheduled_hands_to_run"),
                          "expected_played": tot(sw_rows, "expected_played_to_run"),
                          "wall_h_ideal": tot_wall(sw_rows, "ideal"), "wall_h_waves": tot_wall(sw_rows, "waves"),
                          "storage_mb": sum(r["to_run"] for r in sw_rows) * bytes_t / 1e6}
    keys4 = ("scheduled_hands", "expected_played", "wall_h_ideal", "wall_h_waves")
    totals["mu_field_plus_matrix"] = {k: totals["mu_field"][k] + totals["matrix"][k] for k in keys4}
    totals["programme"] = {k: totals["mu_field_plus_matrix"][k] + totals["mu_swiss"][k] for k in keys4}
    for t in totals.values():  # the same work at the slow, end-to-end observed rate
        t["slow_rate_wall_h_ideal"] = t["wall_h_ideal"] * rate / slow_rate
        t["slow_rate_wall_h_waves"] = t["wall_h_waves"] * rate / slow_rate
    return {
        "study": cfg["public_name"], "profile": prof.name, "results_root": str(root),
        "scope": {"modes": list(cfg["modes"]), "fields": {f: cfg["fields"].get(f) for f in fields},
                  "unique_cells_per_field": list(CORE_CELL_KEYS), "round_prefixes": list(cfg["round_prefixes"]),
                  "R0": prof.r0, "H0": prof.h0, "K": prof.k, "N": prof.field_size,
                  "horizon_extensions": cfg["horizon_extensions"], "out_of_scope": list(cfg["out_of_scope"])},
        "assumptions": {"workers": workers, "hands_per_s": rate, "hands_per_s_slow": slow_rate, "played_ratio": ratios,
                        "wall_note": "ideal = total played / rate; waves = cells run one after another, each in "
                                     "ceil(tasks / workers) waves of equal tasks (resume-safe, the actual runner)"},
        "field_reference": fr_rows, "matrix": rows, "swiss_reference": swiss, "totals": totals,
        "simulates": False,
    }


def format_plan(plan: dict[str, Any]) -> str:
    """Compact terminal summary of ``build_plan``."""
    def m(x: float | None) -> str:
        return "-" if x is None else f"{x / 1e6:.2f}M"

    def h(x: float | None) -> str:
        return "-" if x is None else f"{x:.2f}h"

    sc, a, t = plan["scope"], plan["assumptions"], plan["totals"]
    out = [f"{plan['study']} core plan (profile {plan['profile']}; root {plan['results_root']}) -- NO simulation",
           f"modes {sc['modes']}  fields {sc['fields']}",
           f"R0={sc['R0']} H0={sc['H0']} K={sc['K']} N={sc['N']}  A prefixes {sc['round_prefixes']}  "
           f"horizon extensions enabled={sc['horizon_extensions']['enabled']}",
           f"throughput {a['hands_per_s']:.0f} hands/s on {a['workers']} workers",
           "", "mu_field (matched duplicate field reference)",
           f"  {'field':15s} {'calib_id':58s} {'stage':9s} {'rounds':>13s} {'lanes':>5s} {'sched':>8s} "
           f"{'played~':>8s} {'wall':>6s}"]
    for r in plan["field_reference"]:
        out.append(f"  {r['field']:15s} {r['calib_id']:58s} {r['stage']:9s} "
                   f"{r['matched_rounds_on_disk']:>4d}->{r['matched_rounds_target']:<4d}({r['matched_rounds_to_run']:>3d}) "
                   f"{r['lanes']:>5d} {m(r['scheduled_hands_to_run']):>8s} {m(r['expected_played_to_run']):>8s} "
                   f"{h(r['wall_h']['waves']):>6s}")
    out += ["", "tournament matrix (unique cells; experiments served in brackets)",
            f"  {'cell':21s} {'field':15s} {'exp':8s} {'RxH':9s} {'lanes':>5s} {'work':>6s} {'reps':>9s} "
            f"{'done':>4s} {'run':>4s} {'stage':9s} {'sched':>8s} {'played~':>8s} {'wall':>6s}  cell_id"]
    for r in plan["matrix"]:
        out.append(f"  {r['cell']:21s} {r['field']:15s} {','.join(r['experiments']):8s} "
                   f"{str(r['R']) + 'x' + str(r['H']):9s} {r['lanes']:>5d} {r['scheduled_work_ratio_vs_baseline']:>6.3f} "
                   f"{str(r['replicates'][0]) + ':' + str(r['replicates'][1]):>9s} {r['completed']:>4d} {r['to_run']:>4d} "
                   f"{r['stage']:9s} {m(r['scheduled_hands_to_run']):>8s} {m(r['expected_played_to_run']):>8s} "
                   f"{h(r['wall_h']['waves']):>6s}  {r['cell_id']}")
        if r["missing_source_tournaments"]:
            out.append(f"    !! frozen replicates need baseline tournaments {r['missing_source_tournaments'][:5]}...")
    sw = plan["swiss_reference"]
    out += ["", f"mu_swiss (swiss-reference, adaptive {sc['R0']}x{sc['H0']}): "
                f"{'ENABLED' if sw['enabled'] else 'DISABLED'}; initial {sw['replicates_initial']} reps/field, "
                f"extension to {sw['replicates_extension']} per field with --extend",
            f"  {'field':15s} {'reps':>9s} {'done':>4s} {'run':>4s} {'stage':9s} {'sched':>8s} {'played~':>8s} "
            f"{'wall':>6s}  cell_id"]
    for r in sw["rows"]:
        out.append(f"  {r['field']:15s} {str(r['replicates'][0]) + ':' + str(r['replicates'][1]):>9s} "
                   f"{r['completed']:>4d} {r['to_run']:>4d} {r['stage']:9s} {m(r['scheduled_hands_to_run']):>8s} "
                   f"{m(r['expected_played_to_run']):>8s} {h(r['wall_h']['waves']):>6s}  {r['cell_id']}")
    prec = sw.get("precision", {})
    if prec.get("available"):
        out.append("  approx. pair-difference SE (BB/match) by reps/field: " + "; ".join(
            f"{n}: " + ", ".join(f"{f} {v['options'][n]['se_pair_diff_bb']:.1f}" for f, v in prec["fields"].items())
            for n in sw["options"]))

    def line(name: str, d: dict) -> str:
        return (f"  {name:22s} {m(d['scheduled_hands']):>9s} {m(d['expected_played']):>9s} "
                f"{h(d['wall_h_waves']):>8s} ({h(d['wall_h_ideal'])})  {h(d['slow_rate_wall_h_waves']):>8s} "
                f"({h(d['slow_rate_wall_h_ideal'])})")

    out += ["", f"totals (to run)          {'scheduled':>9s} {'played~':>9s}  wall @{a['hands_per_s']:.0f} h/s"
                f" (ideal)  wall @{a['hands_per_s_slow']:.0f} h/s (ideal)",
            line("mu_field", t["mu_field"]),
            line(f"matrix ({t['matrix']['tournaments']} tourn.)", t["matrix"]),
            line(f"mu_swiss ({t['mu_swiss']['tournaments']} tourn.)", t["mu_swiss"]),
            line("mu_field + matrix", t["mu_field_plus_matrix"]),
            line("PROGRAMME TOTAL", t["programme"]),
            f"  storage: matrix ~{t['matrix']['storage_mb']:.0f} MB, mu_swiss ~{t['mu_swiss']['storage_mb']:.0f} MB"]
    return "\n".join(out)
