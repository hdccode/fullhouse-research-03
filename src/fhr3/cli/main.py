"""``fhr3`` command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from fhr3.configs.experiment import ExperimentConfig, load_config


def _cfg(args: argparse.Namespace) -> ExperimentConfig:
    return load_config(args.config)


def _pairings(cfg: ExperimentConfig, names: list[str] | None) -> list[str]:
    if not names:
        return [p.pairing_id for p in cfg.pairings]
    for n in names:
        cfg.pairing(n)
    return names


def _dump(obj: Any, path: str | None) -> None:
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(obj, indent=2, default=str))
        print(f"wrote {path}", file=sys.stderr)


# ------------------------------------------------------------------ simulate
def cmd_simulate(args: argparse.Namespace) -> int:
    from fhr3.eval.runner import execute, filter_resume, parse_range, parse_shard, plan_work, shard_units
    from fhr3.io.manifest import RunManifest, new_run_id, now_iso
    from fhr3.io.store import _write_json_atomic, ensure_locks, experiment_dir

    cfg = _cfg(args)
    start, end = parse_range(args.blocks) if args.blocks else (0, cfg.blocks)
    shard = parse_shard(args.shard) if args.shard else None
    pids = _pairings(cfg, args.pairing)
    chunk = args.chunk_size or cfg.chunk_size
    results_root = Path(args.out)
    traces_root = None if args.no_traces else Path(args.traces)
    units = shard_units(plan_work(pids, start, end, chunk), shard)
    todo, done = filter_resume(units, results_root, cfg)
    k = cfg.game.player_count
    n_blocks = sum(u.end - u.start for u in todo)

    plan = {
        "experiment_id": cfg.experiment_id,
        "config_hash": cfg.config_hash,
        "pairings": {p: cfg.pairing(p).pairing_hash for p in pids},
        "blocks": [start, end],
        "chunk_size": chunk,
        "shard": args.shard,
        "units_total": len(units),
        "units_todo": len(todo),
        "units_already_done": len(done),
        "blocks_todo": n_blocks,
        "played_hands_todo": n_blocks * 2 * k,
        "results_dir": str(experiment_dir(results_root, cfg)),
        "traces_dir": str(traces_root / cfg.experiment_id) if traces_root else None,
        "workers": args.workers,
    }
    if args.dry_run:
        print(json.dumps({"plan": plan, "environment": cfg.environment(),
                          "pairings_resolved": [cfg.pairing(p).resolved() for p in pids]}, indent=2, default=str))
        return 0

    ensure_locks(results_root, cfg, [cfg.pairing(p) for p in pids])
    run_id = new_run_id()
    manifest = RunManifest(
        run_id=run_id,
        command=sys.argv,
        config_path=str(args.config),
        config=dict(cfg.raw),
        config_hash=cfg.config_hash,
        pairing_hashes={p: cfg.pairing(p).pairing_hash for p in pids},
        work=plan,
    )
    mpath = experiment_dir(results_root, cfg) / "runs" / f"{run_id}.json"
    _write_json_atomic(mpath, manifest.to_dict())
    print(f"run {run_id}: {len(todo)} chunks / {n_blocks} blocks to do ({len(done)} chunks already present)", file=sys.stderr)

    t0 = time.perf_counter()
    blocks_done = 0

    def progress(r: dict[str, Any], i: int, n: int) -> None:
        nonlocal blocks_done
        blocks_done += r["blocks"]
        el = time.perf_counter() - t0
        rate = blocks_done / el if el > 0 else 0.0
        eta = (n_blocks - blocks_done) / rate if rate > 0 else float("nan")
        flag = f"  INVALID={r['invalid']}" if r["invalid"] else ""
        print(f"[{i}/{n}] {r['unit'][0]} {r['unit'][1]}:{r['unit'][2]}  {rate:.1f} blocks/s  eta {eta / 60:.1f} min{flag}", file=sys.stderr)

    results = execute(cfg, todo, results_root, traces_root, run_id, args.workers, True, progress)
    wall = time.perf_counter() - t0
    manifest.finished_at = now_iso()
    manifest.summary = {
        "wall_s": wall,
        "blocks": blocks_done,
        "invalid": sum(r["invalid"] for r in results),
        "traced": sum(r["traced"] for r in results),
        "blocks_per_s_aggregate": blocks_done / wall if wall > 0 else None,
    }
    _write_json_atomic(mpath, manifest.to_dict())
    print(json.dumps(manifest.summary, indent=2), file=sys.stderr)
    print(f"manifest: {mpath}", file=sys.stderr)
    return 1 if manifest.summary["invalid"] else 0


# ------------------------------------------------------------------ replay
def cmd_replay(args: argparse.Namespace) -> int:
    from fhr3.eval.runner import BlockSimulator
    from fhr3.io.store import pairing_dir, read_blocks
    from fhr3.io.traces import write_traces
    from fhr3.validation.corpus import rows_equal

    cfg = _cfg(args)
    sim = BlockSimulator(cfg, cfg.pairing(args.pairing))
    res = sim.run(args.block, trace=bool(args.trace_dir))
    print(f"block {args.block} seed {res.seed} valid={res.valid} {res.error_code or ''} {res.error_detail or ''}")
    if res.valid:
        print("seat  X_A      X_B      D_s")
        for s, (a, b) in enumerate(zip(res.seat_payoff_a, res.seat_payoff_b, strict=True)):
            print(f"{s:>4}  {a:+8.2f} {b:+8.2f} {a - b:+8.2f}")
        print(f"D = {res.D:+.4f}   played hands {res.played_hands}   decisions {res.decision_count}")
    if args.trace_dir:
        for p in write_traces(Path(args.trace_dir), res.traces):
            print(f"trace: {p}")
    if args.compare:
        table = read_blocks(pairing_dir(Path(args.compare), cfg, args.pairing))
        stored = [r for r in table.to_pylist() if r["block_id"] == args.block]
        if not stored:
            print("no stored row for this block")
            return 1
        diff = rows_equal(sim.row(res, stored[0]["run_id"], stored[0]["traced"]), stored[0])
        print("replay matches stored row exactly" if not diff else f"MISMATCH in {diff}")
        return 1 if diff else 0
    return 0


# ------------------------------------------------------------------ validate
def cmd_validate(args: argparse.Namespace) -> int:
    from fhr3.eval.runner import parse_range
    from fhr3.validation.corpus import validate_pairing

    cfg = _cfg(args)
    expected = parse_range(args.blocks) if args.blocks else None
    reports = [validate_pairing(cfg, Path(args.out), p, expected, args.replay) for p in _pairings(cfg, args.pairing)]
    for r in reports:
        status = "OK" if r["ok"] else "FAIL"
        print(f"[{status}] {r['pairing_id']}: {r['rows']} rows, {r['invalid']} invalid, replayed {len(r['replayed_blocks'])} blocks exactly")
        for p in r["problems"]:
            print(f"    - {p}")
    _dump(reports, args.json)
    return 0 if all(r["ok"] for r in reports) else 1


# ------------------------------------------------------------------ analyze
def cmd_analyze(args: argparse.Namespace) -> int:
    from fhr3.analysis.report import analyze_paths, format_report, write_ecdf_csv

    paths = [Path(p) for p in args.paths]
    deltas = tuple(float(x) for x in args.deltas.split(","))
    report = analyze_paths(paths, n_boot=args.bootstrap, deltas_bb100=deltas, alpha=args.alpha, seed=args.seed)
    print(format_report(report))
    _dump(report, args.json)
    if args.ecdf_dir:
        for p in write_ecdf_csv(paths, Path(args.ecdf_dir)):
            print(f"ecdf: {p}", file=sys.stderr)
    return 0


def cmd_power_sim(args: argparse.Namespace) -> int:
    from fhr3.analysis.report import power_sim_paths

    ns = [int(x) for x in args.n.split(",")]
    deltas = [float(x) for x in args.deltas.split(",")]
    out = power_sim_paths([Path(p) for p in args.paths], ns, deltas, args.reps, args.seed, args.alpha)
    for key, e in out.items():
        print(f"== {key}  (source blocks {e['source_blocks']}, sd_D {e['sd_D']:.3f})  [synthetic location shifts]")
        print("   n_blocks  Delta BB/100  power(2-sided)  P(select stronger)")
        for r in e["results"]:
            print(f"   {r['n_blocks']:>8}  {r['delta_bb100']:>12}  {r['power_two_sided']:>14.3f}  {r['p_select_stronger']:>18.3f}")
    _dump(out, args.json)
    return 0


# ------------------------------------------------------------------ bench
def cmd_bench(args: argparse.Namespace) -> int:
    import cProfile
    import pstats

    from fhr3.eval.runner import BlockSimulator

    cfg = _cfg(args)
    sim = BlockSimulator(cfg, cfg.pairing(_pairings(cfg, args.pairing)[0]))
    prof = cProfile.Profile() if args.profile else None
    t0 = time.perf_counter()
    if prof:
        prof.enable()
    res = [sim.run(b) for b in range(args.blocks)]
    if prof:
        prof.disable()
    wall = time.perf_counter() - t0
    hands = sum(r.played_hands for r in res)
    decs = sum(r.decision_count for r in res)
    agent = sum(r.agent_ms for r in res) / 1000
    print(f"{args.blocks} blocks in {wall:.2f}s: {args.blocks / wall:.1f} blocks/s, {hands / wall:.0f} hands/s, "
          f"{decs / wall:.0f} decisions/s; agent share {agent / wall:.2f} (single process)")
    if prof:
        pstats.Stats(prof).sort_stats("cumulative").print_stats(args.profile_top)
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="fhr3", description="FullHouse Research #3 matched-evaluation framework")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("simulate", help="simulate matched blocks to Parquet (resumable)")
    s.add_argument("--config", required=True)
    s.add_argument("--blocks", help="half-open block range start:end (default 0:<config blocks>)")
    s.add_argument("--pairing", action="append", help="pairing id (repeatable; default all)")
    s.add_argument("--shard", help="i/n, zero-based: run every n-th chunk starting at i")
    s.add_argument("--workers", type=int, default=1)
    s.add_argument("--chunk-size", type=int, help="override config chunk_size (must match earlier runs)")
    s.add_argument("--out", default="results")
    s.add_argument("--traces", default="traces")
    s.add_argument("--no-traces", action="store_true")
    s.add_argument("--dry-run", action="store_true", help="print the resolved plan and exit")
    s.set_defaults(func=cmd_simulate)

    r = sub.add_parser("replay", help="recompute one block exactly (optionally trace / compare)")
    r.add_argument("--config", required=True)
    r.add_argument("--pairing", required=True)
    r.add_argument("--block", type=int, required=True)
    r.add_argument("--trace-dir")
    r.add_argument("--compare", metavar="RESULTS_ROOT")
    r.set_defaults(func=cmd_replay)

    v = sub.add_parser("validate", help="structural checks + exact replay of sampled blocks")
    v.add_argument("--config", required=True)
    v.add_argument("--out", default="results")
    v.add_argument("--pairing", action="append")
    v.add_argument("--blocks", help="expected complete range start:end")
    v.add_argument("--replay", type=int, default=10)
    v.add_argument("--json")
    v.set_defaults(func=cmd_validate)

    a = sub.add_parser("analyze", help="block-level statistics and sample-size tables")
    a.add_argument("paths", nargs="+", help="experiment/pairing directories or parquet files")
    a.add_argument("--bootstrap", type=int, default=2000)
    a.add_argument("--deltas", default="0.25,0.5,1,2,5", help="effect sizes in BB/100")
    a.add_argument("--alpha", type=float, default=0.05)
    a.add_argument("--seed", type=int, default=0)
    a.add_argument("--json")
    a.add_argument("--ecdf-dir")
    a.set_defaults(func=cmd_analyze)

    p = sub.add_parser("power-sim", help="empirical power via synthetic location shifts of block residuals")
    p.add_argument("paths", nargs="+")
    p.add_argument("--n", default="1000,5000,10000,50000,100000", help="block counts")
    p.add_argument("--deltas", default="0.5,1,2,5", help="BB/100")
    p.add_argument("--reps", type=int, default=2000)
    p.add_argument("--alpha", type=float, default=0.05)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--json")
    p.set_defaults(func=cmd_power_sim)

    b = sub.add_parser("bench", help="small single-process throughput/profile run (no output files)")
    b.add_argument("--config", required=True)
    b.add_argument("--pairing", action="append")
    b.add_argument("--blocks", type=int, default=50)
    b.add_argument("--profile", action="store_true")
    b.add_argument("--profile-top", type=int, default=25)
    b.set_defaults(func=cmd_bench)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
