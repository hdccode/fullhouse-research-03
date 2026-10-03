"""``fhr3b``: FHR3B Swiss tournament reliability experiments (publicly FullHouse Research #4).

Every simulation command is resumable: completed, digest-verified tournaments (and
calibration chunks) are skipped, and results from a different configuration are
refused. See docs/fhr3b/RUNBOOK.md for the order of operations.

The core publication study is ``fhr3b core {plan,field-reference,matrix,swiss-reference}``
(NLHE6 only; configs/fhr3b/matrix.yaml: core_fhr4). Under the publication profile every
simulation command refuses work outside the core scope unless asked explicitly:
non-core modes need ``--allow-noncore`` (and, for a field reference, an explicit
``--rounds``: the FHR #4 budget is never inherited); more than the initial replicates
(50 per cell, 100 per field for mu_swiss) or matched rounds (250), or a horizon beyond
R0, need ``--extend``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

from fhr3.tournament import experiments as ex
from fhr3.tournament.fields import (
    FHR3B_CONFIGS,
    all_modes,
    load_mode,
    pool_manifest,
    provisional_field,
    smoke_field,
    write_field_immutable,
)

DEFAULT_ROOT = Path("results/fhr3b")
DEFAULT_REPORTS = Path("reports/fhr3b")
EXPERIMENTS = ("smoke", "pilot", "core", "baseline", "round-sweep", "budget-sweep", "frozen-schedule",
               "schedule-diagnostic", "duplicate-play", "swiss-reference", "operational-2026")


def _p(obj: Any) -> None:
    print(json.dumps(obj, indent=1, sort_keys=True, default=str))


def _replicates(args: argparse.Namespace, default: int) -> range:
    if args.range:
        a, _, b = args.range.partition(":")
        return range(int(a or 0), int(b))
    n = args.replicates if args.replicates is not None else (
        ex.preset_replicates(args.preset) if getattr(args, "preset", None) else default)
    return range(n)


def _profile_for(args: argparse.Namespace) -> ex.Profile:
    name = args.profile or {"smoke": "smoke", "pilot": "pilot"}.get(args.experiment, "publication")
    return ex.load_profile(name, Path(args.root))


def cells_for(args: argparse.Namespace) -> list[tuple[str, Any]]:
    """(label, cell) pairs an experiment runs, in dependency order."""
    mx = ex.load_matrix()
    E = mx["experiments"]
    prof = _profile_for(args)
    exp = args.experiment
    if exp == "operational-2026":
        # Only this historical experiment depends on the 2026 record; the research experiments never do.
        from fhr3.tournament.historical import load_historical

        rec = load_historical(FHR3B_CONFIGS)
        miss = rec.missing()
        if miss:
            raise SystemExit(
                f"operational-2026 is BLOCKED / PENDING: {rec.name} lacks required historical values "
                f"(UNKNOWN: {', '.join(miss)}).\nUnresolved facts:\n  - " + "\n  - ".join(rec.unknowns)
                + "\nThe controlled FHR3B experiments (fhr3b_baseline) are not affected. "
                "See docs/fhr3b/2026_protocol_audit.md.")
        raise SystemExit(f"historical values supplied ({rec.to_protocol().protocol_hash}); an operational field "
                         f"of N={rec.required['field_size']} bots must be built before this experiment can run.")
    if exp == "round-sweep":
        raise SystemExit("round-sweep is derived from the baseline cells (exact R-prefixes): run `baseline`, then "
                         "`validate --experiment baseline --prefix N` and `analyse`.")
    if exp == "core":
        from fhr3.tournament import core

        if args.modes and list(args.modes) != list(mx["core_fhr4"]["modes"]):
            raise SystemExit(f"core is {mx['core_fhr4']['modes']} only; got --modes {args.modes}")
        try:
            return [(cc.label, cc.cell) for cc in core.core_cells(prof, args.fields, getattr(args, "cells", None))]
        except core.CoreScopeError as e:
            raise SystemExit(str(e)) from e
    key = exp.replace("-", "_")
    modes = args.modes or E.get(key, {}).get("modes") or mx["primary_modes"]
    fields = args.fields or (list(prof.fields) if exp in ("baseline", "swiss-reference") else
                             E.get(key, {}).get("fields", list(prof.fields)))
    if not args.fields and prof.name == "publication":  # default: active fields only (held fields skipped)
        from fhr3.tournament.core import held_fields

        held = held_fields(prof)
        fields = [f for f in fields if f not in held]
    out = []
    for mode in modes:
        for field in fields:
            if exp == "smoke":
                out.append((f"smoke {mode}", prof.cell(mode, field if args.fields else "smoke12", "baseline")))
            elif exp in ("pilot", "baseline"):
                out.append((f"{exp} {mode}/{field}", prof.cell(mode, field, "baseline", getattr(args, "horizon", None))))
            elif exp == "swiss-reference":
                out.append((f"swiss-reference {mode}/{field}",
                            prof.cell(mode, field, "swiss_reference", getattr(args, "horizon", None))))
            elif exp == "budget-sweep":
                for alloc, c in prof.budget_cells(mode, field):
                    out.append((f"budget {mode}/{field} {alloc.label} R{alloc.rounds}xH{alloc.hands_per_match}", c))
            elif exp == "duplicate-play":
                out += [(f"duplicate {mode}/{field} {label}", c) for label, c in prof.duplicate_cells(mode, field)]
            elif exp == "frozen-schedule":  # core C: adaptive baseline vs frozen replay (J = 1)
                src, frozen, _, _ = prof.schedule_cells(mode, field, int(E["frozen_schedule"]["replays_per_source"]))
                out += [(f"baseline {mode}/{field}", src), (f"frozen {mode}/{field}", frozen)]
            elif exp == "schedule-diagnostic":
                src, frozen, adapt, j = prof.schedule_cells(mode, field)
                out += [(f"schedule-source {mode}/{field}", src), (f"frozen {mode}/{field}", frozen),
                        (f"adaptive-replay {mode}/{field}", adapt)]
            else:
                raise SystemExit(f"unknown experiment {exp}")
    return out


# ------------------------------------------------------------------ publication guards
def _core_cfg() -> dict[str, Any]:
    return ex.load_matrix()["core_fhr4"]


def _guard_modes(args: argparse.Namespace, prof: ex.Profile, modes: list[str]) -> None:
    core_modes = _core_cfg()["modes"]
    extra = sorted(set(modes) - set(core_modes))
    if prof.name == "publication" and extra and not getattr(args, "allow_noncore", False):
        raise SystemExit(f"{extra} are outside the FHR #4 core scope ({core_modes}); their fields stay frozen for "
                         "provenance. Pass --allow-noncore only for a deliberate, separately planned study.")


def _guard_replicates(args: argparse.Namespace, prof: ex.Profile, reps: range) -> None:
    if prof.name != "publication":
        return
    cfg = _core_cfg()
    init = int(cfg["swiss_reference"]["replicates_initial"] if getattr(args, "experiment", None) == "swiss-reference"
               else cfg["replicates_initial"])
    if reps.stop > init and not getattr(args, "extend", False):
        raise SystemExit(f"replicates {reps.start}..{reps.stop - 1} go beyond the initial {init} per cell. Extensions "
                         f"are per cell and append-only: e.g. --range {init}:{2 * init} --extend (tournaments "
                         f"0..{init - 1} are verified and skipped, never recomputed).")


def _guard_horizon(args: argparse.Namespace, prof: ex.Profile) -> None:
    h = getattr(args, "horizon", None)
    if prof.name == "publication" and h is not None and h > prof.r0 and not getattr(args, "extend", False):
        hz = _core_cfg()["horizon_extensions"]
        raise SystemExit(f"--horizon {h} is a long-horizon extension ({hz['horizons']}), disabled by default "
                         f"(enabled: {hz['enabled']}). Run it only if the qualification metrics have not "
                         "stabilised at 40 rounds, with --extend.")


def _guard_held(prof: ex.Profile, field_hashes: list[str]) -> None:
    """Publication runs never simulate a field on HOLD (FROZEN.yaml ``held``)."""
    import yaml

    reg = prof.config_root / "fields" / "FROZEN.yaml"
    held = (yaml.safe_load(reg.read_text()).get("held") or {}) if reg.exists() else {}
    bad = sorted({h for h in field_hashes if h in held})
    if prof.name == "publication" and bad:
        r = held[bad[0]]
        raise SystemExit(f"field {r['mode']}/{r['field']} ({bad[0]}) is on HOLD [{r['status']}]: no further "
                         f"simulation. See {r['provenance']}.")


def _guard_swiss_reference(prof: ex.Profile) -> None:
    sw = _core_cfg()["swiss_reference"]
    if prof.name == "publication" and not sw.get("enabled", False):
        raise SystemExit("mu_swiss (swiss-reference) publication execution is DISABLED pending its initial budget "
                         f"(options {sw['replicate_options']} reps/field; see `fhr3b core plan`). Set "
                         "core_fhr4.swiss_reference.enabled: true in configs/fhr3b/matrix.yaml to enable it.")


def _field_rounds(args: argparse.Namespace, prof: ex.Profile, mode: str) -> int:
    """Matched rounds for a field reference: explicit --rounds, else the core-scoped budget for core modes.

    Non-core modes (AoF4, NLHE4, ...) never inherit the FHR #4 budget: they must pass --rounds.
    """
    if args.rounds:
        return int(args.rounds)
    if prof.name != "publication":
        return prof.calibration_rounds("field", mode)
    if mode in _core_cfg()["modes"]:
        return int(_core_cfg()["field_reference"]["matched_rounds_initial"])
    raise SystemExit(f"{mode} is outside the FHR #4 core: its field-reference budget is not defaulted. Pass the "
                     "matched rounds explicitly with --rounds (a separately designed study).")


def _guard_field_rounds(args: argparse.Namespace, prof: ex.Profile, rounds: int, mode: str = "nlhe6") -> None:
    if prof.name != "publication":
        return
    chunk = int(prof.calibration["field_reference"]["chunk_rounds"])
    if rounds % chunk:
        raise SystemExit(f"field-reference rounds must be a multiple of chunk_rounds={chunk} so later extensions "
                         "append whole chunks")
    if mode not in _core_cfg()["modes"]:
        return  # explicit, separately planned non-core budget (already behind --allow-noncore)
    init = int(_core_cfg()["field_reference"]["matched_rounds_initial"])
    if rounds > init and not getattr(args, "extend", False):
        raise SystemExit(f"{rounds} matched rounds go beyond the initial {init} per field; an extension appends "
                         f"rounds {init}..{rounds - 1} (the first {init} are never repeated). Pass --extend.")


# ------------------------------------------------------------------ commands
def cmd_audit(args: argparse.Namespace) -> int:
    from fhr3.tournament.historical import load_historical
    from fhr3.tournament.protocol import load_protocol

    ref = Path(__file__).resolve().parents[3] / "tests/data/fhr3b/fullhouse_engine_a80b269"
    prov = json.loads((ref / "PROVENANCE.json").read_text())
    got = hashlib.sha256((ref / "reference_tournament.py").read_bytes()).hexdigest()
    want = prov["files"]["engine/tournament.py"]["sha256"]
    rec = load_historical(FHR3B_CONFIGS)
    base = load_protocol(FHR3B_CONFIGS / "protocols/fhr3b_baseline.yaml")
    _p({"audit_doc": "docs/fhr3b/2026_protocol_audit.md",
        "historical_provenance": {"record": rec.name, "record_hash": rec.record_hash,
                                  "reference_repository": prov["repository"], "reference_commit": prov["commit"],
                                  "vendored_reference_sha256_ok": got == want,
                                  "production_equivalence": rec.raw["production_equivalence"],
                                  "unknown_required_values": rec.missing(),
                                  "operational_validation": "BLOCKED" if rec.missing() else "unblocked"},
        "research_baseline": base.to_dict() | {"protocol_hash": base.protocol_hash, "notes": list(base.notes),
                                               "meaning": "predeclared research design choices; not 2026 settings"},
        "golden_test": "tests/test_fhr3b_swiss.py::test_port_matches_vendored_reference"})
    return 0 if got == want else 1


def cmd_pools(args: argparse.Namespace) -> int:
    out = {}
    for m in args.modes or all_modes():
        mode = load_mode(m)
        pool = pool_manifest(mode)
        d = FHR3B_CONFIGS / "fields" / m
        for fm in (pool, smoke_field(pool), provisional_field(pool)):
            name = {"pool": "pool", "smoke": "smoke12", "provisional": "provisional60"}[fm.kind]
            write_field_immutable(fm, d / f"{name}.json")
            out[f"{m}/{name}"] = {"n": fm.n, "field_hash": fm.field_hash}
    _p(out)
    return 0


def cmd_calibrate(args: argparse.Namespace) -> int:
    from fhr3.tournament.calibration import run_calibration

    prof = ex.load_profile(args.profile or "publication", Path(args.root))
    if args.stage == "field":
        _guard_modes(args, prof, args.modes)
    for m in args.modes:
        fields = args.fields if args.stage == "field" else [None]
        for f in fields:
            spec = prof.calibration_spec(m, args.stage, f)
            if args.stage == "field":
                _guard_held(prof, [spec.field.field_hash])
                rounds = _field_rounds(args, prof, m)
                _guard_field_rounds(args, prof, rounds, m)
            else:
                rounds = args.rounds or prof.calibration_rounds(args.stage, m)
            _p(run_calibration(spec, Path(args.root), rounds, args.workers, args.allow_source_change))
    return 0


def cmd_select(args: argparse.Namespace) -> int:
    from fhr3.tournament.selection import select_fields

    prof = ex.load_profile(args.profile or "publication", Path(args.root))
    reports = Path(args.reports) if args.reports else _reports_for(args)
    for m in args.modes:
        s = select_fields(Path(args.root), prof, m, reports, n_boot=args.boot)
        _p({"mode": m, "fields": {k: {"field_hash": v["field_hash"], "gap_k_k1_se": round(v["gap_k_k1_se"], 2),
                                      "near_duplicate_pairs": v["near_duplicate_pairs"],
                                      "style_counts": v["style_counts"]} for k, v in s["fields"].items()}})
    return 0


def cmd_behaviour_audit(args: argparse.Namespace) -> int:
    from fhr3.tournament.behaviour import run_behaviour_audit

    reports = Path(args.reports) if args.reports else _reports_for(args)
    rounds = args.rounds or int(ex.load_matrix()["calibration"]["behaviour_audit"]["rounds"])
    for m in args.modes:
        _p(run_behaviour_audit(Path(args.root), args.profile or "publication", m, reports, rounds, args.workers))
    return 0


def cmd_field_reference(args: argparse.Namespace) -> int:
    from fhr3.tournament.selection import field_reference_report

    prof = ex.load_profile(args.profile or "publication", Path(args.root))
    reports = Path(args.reports) if args.reports else _reports_for(args)
    for m in args.modes:
        for f in args.fields or list(prof.fields):
            _p(field_reference_report(Path(args.root), prof, m, f, reports, n_boot=args.boot))
    return 0


def _reports_for(args: argparse.Namespace) -> Path:
    return Path(args.root) / "smoke-reports" if getattr(args, "profile", None) == "smoke" else DEFAULT_REPORTS


def cmd_plan(args: argparse.Namespace) -> int:
    from fhr3.tournament.store import cell_dir, completed_replicates

    rows = []
    for label, c in cells_for(args):
        p = c.protocol
        done = completed_replicates(Path(args.root), c, verify=False) if cell_dir(Path(args.root), c).exists() else []
        tables_per_round = c.field.n // p.table_size
        rows.append({"label": label, "cell_id": c.cell_id, "identity_hash": c.identity_hash,
                     "protocol_hash": p.protocol_hash, "field_hash": c.field.field_hash,
                     "game_hash": c.mode.game_hash, "R": p.rounds, "H": p.hands_per_match, "K": p.qualify_top_k,
                     "N": c.field.n, "hands_per_tournament_max": p.rounds * tables_per_round * p.hands_per_match,
                     "completed": len(done)})
    _p(rows)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from fhr3.tournament.batch import run_cell

    mx = ex.load_matrix()
    if args.experiment == "smoke":
        reps = _replicates(args, int(mx["experiments"]["smoke"]["replicates"]))
    elif args.experiment == "pilot":
        reps = _replicates(args, ex.preset_replicates("pilot"))
    elif not (args.preset or args.replicates is not None or args.range):
        raise SystemExit("publication-scale experiments need an explicit --preset, --replicates or --range")
    else:
        reps = _replicates(args, 0)
    root = Path(args.root)
    prof = _profile_for(args)
    if args.experiment == "swiss-reference":
        _guard_swiss_reference(prof)
    _guard_horizon(args, prof)
    if args.modes:  # refuse non-core modes before resolving any field of those modes
        _guard_modes(args, prof, list(args.modes))
    cells = cells_for(args)
    _guard_modes(args, prof, sorted({c.mode.mode for _, c in cells}))
    _guard_held(prof, [c.field.field_hash for _, c in cells])
    if args.experiment != "schedule-diagnostic":
        _guard_replicates(args, prof, reps)
    run_ids = {c.identity_hash for _, c in cells}
    for label, c in cells:  # frozen replicate r replays source tournament r: it must exist or run first
        if c.kind == "frozen_replay" and c.source is not None and c.source.identity_hash not in run_ids:
            from fhr3.tournament.store import completed_replicates

            src_done = set(completed_replicates(root, c.source, verify=False))
            srcs = set(reps) if args.experiment in ("core", "frozen-schedule") else {c.source_index(r)[0] for r in reps}
            need = srcs - src_done
            if need:
                raise SystemExit(f"[{label}] needs source tournaments {sorted(need)[:5]}... of {c.source.cell_id}; "
                                 "run the baseline cell first")
    for label, c in cells:
        this = reps
        if c.kind == "frozen_replay" and args.experiment in ("core", "frozen-schedule"):
            # reps = SOURCE tournaments; the frozen cell holds J replays of each (J = 1 in the initial core)
            this = range(reps.start * c.replays_per_source, reps.stop * c.replays_per_source)
        if args.experiment == "schedule-diagnostic":
            # reps = tournaments per replay sub-cell; sources are the independent units
            j = int(prof.selection["replays_per_source"])
            src = range(reps.start // j, math.ceil(reps.stop / j))
            this = src if c.kind == "adaptive" else range(src.start * j, src.stop * j)
        print(f"[{label}] {c.cell_id}: replicates {this.start}..{this.stop - 1}", flush=True)
        run = run_cell(c, root, this, args.workers, args.allow_source_change, progress=not args.quiet)
        print(f"[{label}] ran {run['ran']} (skipped {run['skipped_completed']}) in {run['wall_s']}s", flush=True)
    return 0


def _core_args(args: argparse.Namespace, **kw: Any) -> argparse.Namespace:
    base = dict(root=args.root, profile=args.profile, modes=None, fields=args.fields, experiment="core",
                horizon=None, cells=getattr(args, "cells", None), workers=args.workers,
                allow_source_change=args.allow_source_change, quiet=args.quiet, extend=args.extend,
                allow_noncore=False, preset=None, replicates=args.replicates, range=args.range)
    return argparse.Namespace(**(base | kw))


def cmd_core(args: argparse.Namespace) -> int:
    """FullHouse Research #4 core study: plan (no simulation), field-reference, matrix, swiss-reference."""
    from fhr3.tournament import core

    prof = ex.load_profile(args.profile or "publication", Path(args.root))
    cfg = core.core_config(prof)
    try:
        core.check_scope(prof, cfg)
    except core.CoreScopeError as e:
        raise SystemExit(f"core scope check failed: {e}") from e
    reps = _replicates(args, int(cfg["replicates_initial"]))
    if args.action == "plan":
        sw = range(*map(int, args.swiss_range.split(":"))) if args.swiss_range else None
        plan = core.build_plan(prof, Path(args.root), workers=args.workers, rate=args.rate, replicates=reps,
                               mu_field_rounds=args.rounds, fields=args.fields, keys=args.cells, swiss_replicates=sw,
                               reports=Path(args.reports) if args.reports else _reports_for(args))
        if args.json:
            Path(args.json).parent.mkdir(parents=True, exist_ok=True)
            Path(args.json).write_text(json.dumps(plan, indent=1, sort_keys=True, default=str) + "\n")
        print(core.format_plan(plan))
        if args.json:
            print(f"\nplan written to {args.json}")
        return 0
    if args.action == "field-reference":
        from fhr3.tournament.calibration import run_calibration
        from fhr3.tournament.selection import field_reference_report

        rounds = args.rounds or core.core_field_rounds(prof)  # publication: the core-scoped 250
        _guard_field_rounds(args, prof, rounds)
        reports = Path(args.reports) if args.reports else _reports_for(args)
        try:
            fields = core.resolve_fields(prof, args.fields) if prof.name == "publication" else (
                args.fields or list(cfg["fields"]))
        except core.CoreScopeError as e:
            raise SystemExit(str(e)) from e
        held = core.held_fields(prof)
        if held and not args.fields:
            print(f"HOLD (skipped): {', '.join(f'{f} [{r['status']}]' for f, r in held.items())}")
        for m in cfg["modes"]:
            for f in fields:
                _guard_held(prof, [prof.calibration_spec(m, "field", f).field.field_hash])
                spec = prof.calibration_spec(m, "field", f)
                print(f"[mu_field {m}/{f}] {spec.calib_id}: matched rounds 0..{rounds - 1}", flush=True)
                _p(run_calibration(spec, Path(args.root), rounds, args.workers, args.allow_source_change,
                                   progress=not args.quiet))
                if not args.no_report:
                    _p(field_reference_report(Path(args.root), prof, m, f, reports, n_boot=args.boot))
        return 0
    if args.action == "field-diversity":
        from fhr3.tournament.field_diversity import field_diversity, write_field_diversity

        reports = Path(args.reports) if args.reports else _reports_for(args)
        res = field_diversity(prof, cfg["modes"][0], args.fields or list(cfg["fields"]), reports)  # read-only
        _p({k: str(v) for k, v in write_field_diversity(res, reports).items()})
        return 0
    if args.action == "spread-v2":
        from fhr3.tournament import spread_v2

        reports = Path(args.reports) if args.reports else _reports_for(args)
        if args.stage in (None, "select"):
            r = spread_v2.select(Path(args.root), prof, reports)
            _p({k: r[k] for k in ("protocol_hash", "candidate", "separation_se_used", "selection_gap_bb", "leaders",
                                  "non_leaders", "leader_checks")})
        else:
            _p({k: v for k, v in spread_v2.validate(Path(args.root), prof, reports).items()
                if k not in ("top10_val", "nonleaders_p_top6_above_zero")})
        return 0
    if args.action == "separated-control":
        from fhr3.tournament import separated_control as sc

        reports = Path(args.reports) if args.reports else _reports_for(args)
        if args.stage == "construct":
            r = sc.construct(Path(args.root), prof, reports)
            _p({k: r[k] for k in ("candidate", "leaders", "construction_rank6", "construction_rank7",
                                  "construction_gap_bb", "construction_gap_se", "field_styles", "field_archetypes",
                                  "leader_near_duplicate_pairs", "leader_max_per_archetype", "filler_mu_range_bb")})
        elif args.stage == "bind":
            _p(sc.bind(prof, reports))
        elif args.stage == "simulate":
            _p(sc.simulate(Path(args.root), prof, reports, args.workers))
        elif args.stage == "evaluate":
            _p({k: v for k, v in sc.evaluate(Path(args.root), prof, reports).items()
                if k not in ("top12_val", "nonleaders_p_top6_above_zero")})
        else:
            raise SystemExit("separated-control stages: construct | bind | simulate | evaluate")
        return 0
    if args.action == "matrix":
        return cmd_run(_core_args(args, range=args.range or f"{reps.start}:{reps.stop}", replicates=None))
    if args.action == "swiss-reference":
        _guard_swiss_reference(prof)
        sw = _replicates(args, core.swiss_initial(prof))  # default: the initial 100 per field
        return cmd_run(_core_args(args, experiment="swiss-reference", modes=list(cfg["modes"]),
                                  fields=args.fields or core.resolve_fields(prof, None), cells=None,
                                  range=f"{sw.start}:{sw.stop}", replicates=None))
    raise SystemExit(f"unknown core action {args.action}")


def cmd_validate(args: argparse.Namespace) -> int:
    from fhr3.tournament.replay import check_replay, validate_cell, verify_prefix
    from fhr3.tournament.store import cell_dir, completed_replicates

    root = Path(args.root)
    prof = _profile_for(args)
    ok = True
    for label, c in cells_for(args):
        if not cell_dir(root, c).exists():
            print(f"[{label}] no results")
            continue
        reps = completed_replicates(root, c, verify=True)
        res: dict[str, Any] = {"label": label, "complete_verified": len(reps)}
        res |= validate_cell(root, c, reps)
        if args.replay:
            res |= check_replay(root, c, reps[: args.replay])
        if args.prefix and c.kind == "adaptive" and label.split()[0] in ("baseline", "pilot", "smoke"):
            res["prefix"] = [verify_prefix(root, c, r, reps[: args.prefix])
                             for r in prof.checkpoints_for(c.protocol.rounds) if r < c.protocol.rounds]
        _p(res)
    return 0 if ok else 1


def cmd_status(args: argparse.Namespace) -> int:
    return cmd_plan(args)


def cmd_analyse(args: argparse.Namespace) -> int:
    from fhr3.tournament.analysis import analyse

    profile = args.profile or "publication"
    out = Path(args.out) if args.out else (
        Path(args.root) / "smoke-reports" / "analysis" if profile == "smoke" else DEFAULT_REPORTS / f"analysis-{profile}")
    s = analyse(Path(args.root), out, args.modes, n_boot=args.boot, profile=profile, horizon=args.horizon)
    _p({"out": str(out), "status": s["sections"].get("status"), "inputs": len(s["inputs"])})
    return 0


def cmd_replay_hands(args: argparse.Namespace) -> int:
    from fhr3.tournament.replay import replay_match_hands

    args.modes, args.fields = [args.mode], [args.field]
    (label, c), = [x for x in cells_for(args) if x[1].kind == "adaptive"][:1]
    log = replay_match_hands(Path(args.root), c, args.replicate, args.round, args.table)
    _p({"cell_id": c.cell_id, "replicate": args.replicate, "round": args.round, "table": args.table,
        "hands": log if args.full else log[:5], "n_hands": len(log)})
    return 0


# ------------------------------------------------------------------ parser
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="fhr3b", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser, experiment: bool = True) -> None:
        p.add_argument("--root", default=str(DEFAULT_ROOT), help="results root (default results/fhr3b)")
        p.add_argument("--profile", choices=("publication", "pilot", "smoke"), default=None)
        p.add_argument("--modes", nargs="+")
        p.add_argument("--fields", nargs="+")
        if experiment:
            p.add_argument("--experiment", required=True, choices=EXPERIMENTS)
            p.add_argument("--horizon", type=int, default=None,
                           help="rounds for baseline/swiss-reference cells (default R0 = 40, the initial horizon)")

    p = sub.add_parser("audit", help="verify the vendored 2026 reference and print the protocol")
    p.set_defaults(fn=cmd_audit)
    p = sub.add_parser("pools", help="write pool / smoke12 / provisional60 field manifests (immutable)")
    p.add_argument("--modes", nargs="+")
    p.set_defaults(fn=cmd_pools)
    p = sub.add_parser("calibrate", help="balanced field EV calibration (resumable)")
    common(p, experiment=False)
    p.add_argument("--stage", choices=("pool", "field"), required=True)
    p.add_argument("--rounds", type=int)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--allow-source-change", action="store_true")
    p.add_argument("--extend", action="store_true", help="allow field-reference rounds beyond the initial stage")
    p.add_argument("--allow-noncore", action="store_true", help="allow modes outside the FHR #4 core scope")
    p.set_defaults(fn=cmd_calibrate)
    p = sub.add_parser("behaviour-audit", help="exact replay of calibration rounds -> behaviour + style classes")
    common(p, experiment=False)
    p.add_argument("--reports")
    p.add_argument("--rounds", type=int)
    p.add_argument("--workers", type=int, default=8)
    p.set_defaults(fn=cmd_behaviour_audit)
    for name, fn in (("select-fields", cmd_select), ("field-reference", cmd_field_reference)):
        p = sub.add_parser(name)
        common(p, experiment=False)
        p.add_argument("--reports")
        p.add_argument("--boot", type=int, default=1000 if name == "field-reference" else 300)
        p.set_defaults(fn=fn)
    for name, fn in (("plan", cmd_plan), ("status", cmd_status)):
        p = sub.add_parser(name)
        common(p)
        p.set_defaults(fn=fn)
    p = sub.add_parser("run", help="run an experiment's tournaments (resumable)")
    common(p)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--preset", choices=("pilot", "core", "swiss_reference"))
    g.add_argument("--replicates", type=int)
    g.add_argument("--range", help="replicate range a:b")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--allow-source-change", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--extend", action="store_true", help="allow replicates / horizon beyond the core initial stage")
    p.add_argument("--allow-noncore", action="store_true", help="allow modes outside the FHR #4 core scope")
    p.add_argument("--cells", nargs="+", help="core cells only (experiment core)")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("core", help="FullHouse Research #4 core study (NLHE6): plan | field-reference | matrix | "
                                    "swiss-reference | field-diversity (no simulation)")
    p.add_argument("action", choices=("plan", "field-reference", "matrix", "swiss-reference", "field-diversity",
                                      "spread-v2", "separated-control"))
    p.add_argument("--stage", choices=("select", "validate", "construct", "bind", "simulate", "evaluate"),
                   default=None, help="spread-v2: select | validate; separated-control: construct | bind | "
                                      "simulate | evaluate (one shot)")
    p.add_argument("--root", default=str(DEFAULT_ROOT), help="results root (default results/fhr3b)")
    p.add_argument("--profile", choices=("publication", "smoke"), default=None)
    p.add_argument("--fields", nargs="+", help="subset of the core fields (default: all three)")
    p.add_argument("--cells", nargs="+", help="subset of the six core cells (e.g. baseline frozen_schedule)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--replicates", type=int, help="tournaments per cell: 0..N-1 (default: core replicates_initial)")
    g.add_argument("--range", help="replicate range a:b (extensions: e.g. 50:100 with --extend)")
    p.add_argument("--rounds", type=int, help="mu_field matched rounds per field (default: core initial, 250)")
    p.add_argument("--extend", action="store_true", help="allow work beyond the initial stage (append-only)")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--rate", type=float, default=None, help="plan: hands/s on --workers (default: measured)")
    p.add_argument("--json", help="plan: also write the machine-readable plan here")
    p.add_argument("--swiss-range", help="plan: mu_swiss replicate range a:b (default 0:100)")
    p.add_argument("--reports")
    p.add_argument("--boot", type=int, default=1000)
    p.add_argument("--no-report", action="store_true", help="field-reference: skip the (cheap) report step")
    p.add_argument("--allow-source-change", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(fn=cmd_core)
    p = sub.add_parser("validate", help="independent invariant checks, exact replay, R-prefix identity")
    common(p)
    p.add_argument("--replay", type=int, default=0, help="replay the first N tournaments exactly")
    p.add_argument("--prefix", type=int, default=0, help="verify R-sweep prefix identity on N tournaments")
    p.set_defaults(fn=cmd_validate)
    p = sub.add_parser("analyse", help="write reports (CSV/JSON + MANIFEST)")
    p.add_argument("--root", default=str(DEFAULT_ROOT))
    p.add_argument("--profile", choices=("publication", "pilot", "smoke"), default="publication")
    p.add_argument("--modes", nargs="+")
    p.add_argument("--out")
    p.add_argument("--boot", type=int, default=1000)
    p.add_argument("--horizon", type=int, default=None)
    p.set_defaults(fn=cmd_analyse)
    p = sub.add_parser("replay-hands", help="regenerate hand-level records of one stored table match")
    p.add_argument("--root", default=str(DEFAULT_ROOT))
    p.add_argument("--profile", choices=("publication", "pilot", "smoke"), default=None)
    p.add_argument("--experiment", required=True, choices=EXPERIMENTS)
    p.add_argument("--mode", required=True)
    p.add_argument("--field", required=True)
    p.add_argument("--replicate", type=int, required=True)
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--table", type=int, required=True)
    p.add_argument("--full", action="store_true")
    p.set_defaults(fn=cmd_replay_hands)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
