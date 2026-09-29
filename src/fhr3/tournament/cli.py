"""``fhr3b``: FHR3B Swiss tournament reliability experiments.

Every simulation command is resumable: completed, digest-verified tournaments (and
calibration chunks) are skipped, and results from a different configuration are
refused. See docs/fhr3b/RUNBOOK.md for the order of operations.
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
EXPERIMENTS = ("smoke", "pilot", "baseline", "round-sweep", "budget-sweep", "schedule-diagnostic",
               "swiss-reference", "operational-2026")


def _p(obj: Any) -> None:
    print(json.dumps(obj, indent=1, sort_keys=True, default=str))


def _replicates(args: argparse.Namespace, default: int) -> range:
    if args.range:
        a, _, b = args.range.partition(":")
        return range(int(a or 0), int(b))
    n = args.replicates if args.replicates is not None else (
        ex.preset_replicates(args.preset) if args.preset else default)
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
        from fhr3.tournament.protocol import load_protocol
        import yaml

        path = FHR3B_CONFIGS / E["operational_2026"]["protocol"]
        raw = yaml.safe_load(path.read_text())
        proto = load_protocol(path)
        raise SystemExit(f"operational-2026 is PENDING ({proto.name}, status={proto.status}); unresolved facts:\n  - "
                         + "\n  - ".join(raw.get("unknowns", [])) + "\nSee docs/fhr3b/2026_protocol_audit.md.")
    if exp == "round-sweep":
        raise SystemExit("round-sweep is derived from the baseline cells (exact R-prefixes): run `baseline`, then "
                         "`validate --experiment baseline --prefix N` and `analyse`.")
    key = exp.replace("-", "_")
    modes = args.modes or E.get(key, {}).get("modes") or mx["primary_modes"]
    fields = args.fields or (list(prof.fields) if exp in ("baseline", "swiss-reference") else
                             E.get(key, {}).get("fields", list(prof.fields)))
    out = []
    for mode in modes:
        for field in fields:
            if exp == "smoke":
                out.append((f"smoke {mode}", prof.cell(mode, field if args.fields else "smoke12", "baseline")))
            elif exp in ("pilot", "baseline"):
                out.append((f"{exp} {mode}/{field}", prof.cell(mode, field, "baseline")))
            elif exp == "swiss-reference":
                out.append((f"swiss-reference {mode}/{field}", prof.swiss_reference_cell(mode, field)))
            elif exp == "budget-sweep":
                for alloc, c in prof.budget_cells(mode, field):
                    out.append((f"budget {mode}/{field} {alloc.label} R{alloc.rounds}xH{alloc.hands_per_match}", c))
            elif exp == "schedule-diagnostic":
                src, frozen, adapt, j = prof.schedule_cells(mode, field)
                out += [(f"schedule-source {mode}/{field}", src), (f"frozen {mode}/{field}", frozen),
                        (f"adaptive-replay {mode}/{field}", adapt)]
            else:
                raise SystemExit(f"unknown experiment {exp}")
    return out


# ------------------------------------------------------------------ commands
def cmd_audit(args: argparse.Namespace) -> int:
    from fhr3.tournament.protocol import load_protocol

    ref = Path(__file__).resolve().parents[3] / "tests/data/fhr3b/fullhouse_engine_a80b269"
    prov = json.loads((ref / "PROVENANCE.json").read_text())
    got = hashlib.sha256((ref / "reference_tournament.py").read_bytes()).hexdigest()
    want = prov["files"]["engine/tournament.py"]["sha256"]
    proto = load_protocol(FHR3B_CONFIGS / "protocols/reconstructed_2026.yaml")
    _p({"audit_doc": "docs/fhr3b/2026_protocol_audit.md", "reference_repository": prov["repository"],
        "reference_commit": prov["commit"], "vendored_reference_sha256_ok": got == want,
        "protocol": proto.to_dict() | {"protocol_hash": proto.protocol_hash}, "notes": list(proto.notes),
        "exact_2026_available": False,
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

    prof = ex.load_profile(args.profile, Path(args.root))
    for m in args.modes:
        fields = args.fields if args.stage == "field" else [None]
        for f in fields:
            spec = prof.calibration_spec(m, args.stage, f)
            rounds = args.rounds or prof.calibration_rounds(args.stage)
            _p(run_calibration(spec, Path(args.root), rounds, args.workers, args.allow_source_change))
    return 0


def cmd_select(args: argparse.Namespace) -> int:
    from fhr3.tournament.selection import select_fields

    prof = ex.load_profile(args.profile, Path(args.root))
    reports = Path(args.reports) if args.reports else _reports_for(args)
    for m in args.modes:
        s = select_fields(Path(args.root), prof, m, reports, n_boot=args.boot)
        _p({"mode": m, "fields": {k: v["field_hash"] for k, v in s["fields"].items()},
            "matchup_label": s["matchup_label"], "gate": s["matchup_gate"]})
    return 0


def cmd_field_reference(args: argparse.Namespace) -> int:
    from fhr3.tournament.selection import field_reference_report

    prof = ex.load_profile(args.profile, Path(args.root))
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
    for label, c in cells_for(args):
        this = reps
        if args.experiment == "schedule-diagnostic":
            # reps = tournaments per replay sub-cell; sources are the independent units
            j = int(prof.selection["replays_per_source"])
            src = range(reps.start // j, math.ceil(reps.stop / j))
            this = src if c.kind == "adaptive" else range(src.start * j, src.stop * j)
        print(f"[{label}] {c.cell_id}: replicates {this.start}..{this.stop - 1}", flush=True)
        run = run_cell(c, root, this, args.workers, args.allow_source_change, progress=not args.quiet)
        print(f"[{label}] ran {run['ran']} (skipped {run['skipped_completed']}) in {run['wall_s']}s", flush=True)
    return 0


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
                             for r in prof.rounds_sweep() if r < c.protocol.rounds]
        _p(res)
    return 0 if ok else 1


def cmd_status(args: argparse.Namespace) -> int:
    return cmd_plan(args)


def cmd_analyse(args: argparse.Namespace) -> int:
    from fhr3.tournament.analysis import analyse

    profile = args.profile or "publication"
    out = Path(args.out) if args.out else (
        Path(args.root) / "smoke-reports" / "analysis" if profile == "smoke" else DEFAULT_REPORTS / f"analysis-{profile}")
    s = analyse(Path(args.root), out, args.modes, n_boot=args.boot, profile=profile)
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
    p.set_defaults(fn=cmd_calibrate)
    for name, fn in (("select-fields", cmd_select), ("field-reference", cmd_field_reference)):
        p = sub.add_parser(name)
        common(p, experiment=False)
        p.add_argument("--reports")
        p.add_argument("--boot", type=int, default=300)
        p.set_defaults(fn=fn)
    for name, fn in (("plan", cmd_plan), ("status", cmd_status)):
        p = sub.add_parser(name)
        common(p)
        p.set_defaults(fn=fn)
    p = sub.add_parser("run", help="run an experiment's tournaments (resumable)")
    common(p)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--preset", choices=("pilot", "broad", "flagship"))
    g.add_argument("--replicates", type=int)
    g.add_argument("--range", help="replicate range a:b")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--allow-source-change", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(fn=cmd_run)
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
