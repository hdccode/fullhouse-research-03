"""FHR3B analysis pipeline: stored tournaments -> machine-readable reports.

Reads only stored results (never re-runs poker). Every uncertainty is computed over
complete tournaments (or, for the schedule diagnostic, over independent source
schedules). Paired comparisons (R sweep, budget sweep) share bootstrap weights over
the same tournament/replicate indices. Sections without data are written with a
header only and marked ``"status": "no data"`` in summary.json.

Outputs (``<out>/``): baseline_reliability.csv, qualification_probabilities.csv,
rank_stability.csv, round_sweep.csv, budget_allocation.csv, schedule_diagnostic.csv,
pairwise_inversions.csv, pairwise_inversions_binned.csv, field_references.csv,
figure_data/*.csv, summary.json, MANIFEST.json.
"""

from __future__ import annotations

import csv
import hashlib
import json
import time
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from fhr3.tournament import experiments as ex
from fhr3.tournament import metrics as mt
from fhr3.tournament.calibration import analyse_calibration, calib_dir, load_calibration
from fhr3.tournament.cells import Cell
from fhr3.tournament.manifests import ANALYSIS_VERSION
from fhr3.tournament.store import cell_dir, completed_replicates, load_cell_arrays

CELL_COLS = ["experiment", "mode", "field_id", "field_kind", "field_hash", "cell_id", "identity_hash", "R", "H", "K",
             "N", "namespace"]
MC_TARGETS = {"topk_overlap": 0.10, "changed_qualifiers": 0.10, "kendall_tau": 0.01, "spearman_rho": 0.01,
              "mean_abs_rank_diff": 0.10}


def _cell_info(experiment: str, cell: Cell) -> dict[str, Any]:
    p = cell.protocol
    return {"experiment": experiment, "mode": cell.mode.mode, "field_id": cell.field.field_id,
            "field_kind": cell.field.kind, "field_hash": cell.field.field_hash, "cell_id": cell.cell_id,
            "identity_hash": cell.identity_hash, "R": p.rounds, "H": p.hands_per_match, "K": p.qualify_top_k,
            "N": cell.field.n, "namespace": cell.namespace}


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], header: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = list(header or (rows[0].keys() if rows else []))
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: _fmt(r.get(k)) for k in cols})


def _fmt(v: Any) -> Any:
    if isinstance(v, float):
        return "" if not np.isfinite(v) else f"{v:.6g}"
    if isinstance(v, (np.floating, np.integer)):
        return _fmt(v.item())
    if isinstance(v, (list, tuple)):
        return json.dumps(v)
    return v


def _existing(root: Path, cell: Cell) -> list[int]:
    return completed_replicates(root, cell, verify=False) if cell_dir(root, cell).exists() else []


def _try(fn: Any, *a: Any, **k: Any) -> Any:
    try:
        return fn(*a, **k)
    except (FileNotFoundError, ValueError):
        return None


# ------------------------------------------------------------------ references
def field_reference(root: Path, prof: ex.Profile, mode: str, field: str) -> dict[str, Any] | None:
    """mu_field from the field-reference calibration (if run)."""
    spec = _try(prof.calibration_spec, mode, "field", field)
    if spec is None or not (calib_dir(root, spec) / "chunks").exists():
        return None
    tabs = load_calibration(root, spec)
    if not tabs:
        return None
    res = analyse_calibration(tabs, sorted(spec.field.bot_ids), n_boot=200)
    return {"bots": res["bots"], "mu": res["mu"], "se": res["se"], "calib_id": spec.calib_id,
            "hodge": res["hodge"], "n_groups": res["rounds_groups"]}


def swiss_reference(root: Path, prof: ex.Profile, mode: str, field: str) -> dict[str, Any] | None:
    cell = _try(prof.swiss_reference_cell, mode, field)
    if cell is None:
        return None
    reps = _existing(root, cell)
    if len(reps) < 2:
        return None
    a = load_cell_arrays(root, cell, reps)
    sc = a["final_score"].astype(float)
    return {"bots": a["bots"], "mu": sc.mean(0), "se": sc.std(0, ddof=1) / np.sqrt(len(reps)),
            "mean_rank": a["final_rank"].mean(0), "p_qualify": a["qualified"].mean(0), "cell_id": cell.cell_id,
            "n": len(reps)}


def pick_reference(fr: dict | None, sr: dict | None, bots: Sequence[str]) -> tuple[str, np.ndarray, np.ndarray] | None:
    for name, ref in (("mu_field", fr), ("mu_swiss", sr)):
        if ref is not None and list(ref["bots"]) == list(bots):
            return name, np.asarray(ref["mu"], float), np.asarray(ref["se"], float)
    return None


# ------------------------------------------------------------------ main
def analyse(root: Path, out: Path, modes: Iterable[str] | None = None, n_boot: int = 1000,
            min_tournaments: int = 2, profile: str = "publication") -> dict[str, Any]:
    root, out = Path(root), Path(out)
    prof = ex.load_profile(profile, root)
    mx = ex.load_matrix(prof.config_root)
    E = mx["experiments"]
    modes = list(modes or mx["primary_modes"])
    summary: dict[str, Any] = {"analysis_version": ANALYSIS_VERSION, "profile": profile, "results_root": str(root),
                               "sections": {}, "pairing": ex.PAIRED_NOTE,
                               "lab": {"name": prof.lab_name, "R0": prof.r0, "H0": prof.h0, "K": prof.k,
                                       "round_sweep": prof.rounds_sweep(),
                                       "allocations": [a.__dict__ | {"budget": a.budget} for a in prof.allocations()]}}
    inputs: list[dict[str, Any]] = []
    base_rows, q_rows, rank_rows, sweep_rows, fig2_rows, inv_rows, inv_bin_rows = [], [], [], [], [], [], []
    budget_rows, sched_rows, ref_rows = [], [], []
    fields = list(prof.fields)

    for mode in modes:
        for field in fields:
            fr = field_reference(root, prof, mode, field)
            sr = swiss_reference(root, prof, mode, field)
            ref_rows.extend(_reference_rows(mode, field, fr, sr, summary))
            cell = _try(prof.cell, mode, field, "baseline")
            if cell is None:
                continue
            reps = _existing(root, cell)
            if len(reps) < min_tournaments:
                continue
            inputs.append(_input(root, cell, reps, "baseline"))
            a = load_cell_arrays(root, cell, reps, with_rounds=True)
            info = _cell_info("baseline", cell)
            ws = mt.bootstrap_weights(len(reps), n_boot, seed=20260929)
            est = mt.rerun_stability(a["final_rank"], a["qualified"], a["K"], weights=ws)
            base_rows.append(info | mt.estimates_to_row(est))
            summary["sections"].setdefault("baseline", {})[cell.cell_id] = {
                "n_tournaments": len(reps),
                "headline": {k: est[k].value for k in ("topk_overlap", "changed_qualifiers", "kendall_tau",
                                                       "n_ambiguous_bots")},
                "monte_carlo": {k: mt.monte_carlo_advice(est[k], t) for k, t in MC_TARGETS.items()}}
            ref = pick_reference(fr, sr, a["bots"])
            for row in mt.qualification_table(a["qualified"], a["bots"]):
                q_rows.append(info | row)
            for i, b in enumerate(a["bots"]):
                r = a["final_rank"][:, i]
                rank_rows.append(info | {"bot_id": b, "mean_rank": r.mean(), "sd_rank": r.std(ddof=1),
                                         "q05_rank": np.quantile(r, 0.05), "median_rank": np.median(r),
                                         "q95_rank": np.quantile(r, 0.95),
                                         "mean_final_score": a["final_score"][:, i].mean()})
            # A: round sweep from exact R-prefixes, paired (shared weights)
            for rr in prof.rounds_sweep():
                if rr > cell.protocol.rounds:
                    continue
                rk = a["round_rank"][:, rr - 1, :]
                qual = rk <= a["K"]
                est_r = mt.rerun_stability(rk, qual, a["K"], weights=ws)
                sweep_rows.append(info | {"R_prefix": rr, "hands_per_bot": rr * cell.protocol.hands_per_match}
                                  | mt.estimates_to_row(est_r))
                if ref is not None:
                    for row in mt.cutoff_curve(qual, ref[1], a["bots"]):
                        fig2_rows.append(info | {"R_prefix": rr, "reference": ref[0]} | row)
            if ref is not None:
                name, mu, se = ref
                for row in mt.pairwise_inversions(a["final_rank"], mu, se, a["bots"]):
                    inv_rows.append(info | {"reference": name} | row)
                gaps = np.abs(mu[:, None] - mu[None, :])[np.triu_indices(len(mu), 1)]
                edges = list(np.quantile(gaps, np.linspace(0, 1, 11)))
                edges[-1] += 1e-9
                for row in mt.binned_inversions(a["final_rank"], mu, edges, b=min(n_boot, 500)):
                    inv_bin_rows.append(info | {"reference": name} | row)

        # B: fixed-budget allocations (paired by replicate index)
        for field in E["budget_sweep"]["fields"]:
            cells = _try(prof.budget_cells, mode, field)
            if not cells:
                continue
            reps_by = {a.label: set(_existing(root, c)) for a, c in cells}
            common = sorted(set.intersection(*reps_by.values())) if reps_by else []
            if len(common) < min_tournaments:
                continue
            ws = mt.bootstrap_weights(len(common), n_boot, seed=20260930)
            for alloc, c in cells:
                inputs.append(_input(root, c, common, "budget_sweep"))
                a = load_cell_arrays(root, c, common)
                est = mt.rerun_stability(a["final_rank"], a["qualified"], a["K"], weights=ws)
                budget_rows.append(_cell_info("budget_sweep", c) | {
                    "allocation": alloc.label, "budget_hands_per_bot": alloc.budget, "budget_exact": alloc.exact,
                    "n_common_replicates": len(common)} | mt.estimates_to_row(est))

        # C: schedule diagnostic
        if mode in E["schedule_diagnostic"]["modes"]:
            for field in E["schedule_diagnostic"]["fields"]:
                sd = _try(prof.schedule_cells, mode, field)
                if sd is None:
                    continue
                rows = _schedule_diagnostic(root, *sd, n_boot=n_boot)
                if rows:
                    sched_rows.extend(rows)
                    inputs.extend(_input(root, c, _existing(root, c), "schedule_diagnostic") for c in sd[1:3])

    out.mkdir(parents=True, exist_ok=True)
    files = {
        "baseline_reliability.csv": (base_rows, CELL_COLS),
        "qualification_probabilities.csv": (q_rows, CELL_COLS),
        "rank_stability.csv": (rank_rows, CELL_COLS),
        "round_sweep.csv": (sweep_rows, CELL_COLS),
        "budget_allocation.csv": (budget_rows, CELL_COLS),
        "schedule_diagnostic.csv": (sched_rows, None),
        "pairwise_inversions.csv": (inv_rows, CELL_COLS),
        "pairwise_inversions_binned.csv": (inv_bin_rows, CELL_COLS),
        "field_references.csv": (ref_rows, None),
        "figure_data/fig1_round_sweep.csv": (sweep_rows, CELL_COLS),
        "figure_data/fig2_cutoff_p_qualify_by_R.csv": (fig2_rows, CELL_COLS),
        "figure_data/fig3_budget_allocation.csv": (budget_rows, CELL_COLS),
        "figure_data/fig4_schedule_diagnostic.csv": (sched_rows, None),
        "figure_data/fig5_modes_baseline.csv": (base_rows, CELL_COLS),
    }
    for name, (rows, header) in files.items():
        _write_csv(out / name, rows, header)
        summary["sections"].setdefault("status", {})[name] = "ok" if rows else "no data"
    summary["inputs"] = inputs
    summary["created"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=_json_default) + "\n")
    _write_manifest(out, inputs)
    return summary


def _json_default(o: Any) -> Any:
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def _input(root: Path, cell: Cell, reps: Sequence[int], experiment: str) -> dict[str, Any]:
    lp = cell_dir(root, cell) / "cell.lock.json"
    src_hash = json.loads(lp.read_text())["engine_source_hash"] if lp.exists() else None
    return {"experiment": experiment, "cell_id": cell.cell_id, "identity_hash": cell.identity_hash,
            "protocol_hash": cell.protocol.protocol_hash, "field_hash": cell.field.field_hash,
            "game_hash": cell.mode.game_hash, "n_tournaments": len(reps),
            "replicates": [int(min(reps)), int(max(reps))] if reps else None,
            "engine_source_hash": src_hash}


def _write_manifest(out: Path, inputs: list[dict[str, Any]]) -> None:
    files = {}
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "MANIFEST.json":
            files[str(p.relative_to(out))] = hashlib.sha256(p.read_bytes()).hexdigest()
    (out / "MANIFEST.json").write_text(json.dumps(
        {"analysis_version": ANALYSIS_VERSION, "inputs": inputs, "outputs_sha256": files}, indent=1,
        sort_keys=True) + "\n")


def _reference_rows(mode: str, field: str, fr: dict | None, sr: dict | None, summary: dict) -> list[dict]:
    if fr is None and sr is None:
        return []
    bots = (fr or sr)["bots"]
    rows = []
    fr_rank = sr_rank = None
    if fr is not None:
        fr_rank = (-np.asarray(fr["mu"])).argsort(kind="stable").argsort() + 1
    if sr is not None:
        sr_rank = (-np.asarray(sr["mu"])).argsort(kind="stable").argsort() + 1
    for i, b in enumerate(bots):
        row: dict[str, Any] = {"mode": mode, "field": field, "bot_id": b}
        if fr is not None:
            row |= {"mu_field": fr["mu"][i], "mu_field_se": fr["se"][i], "mu_field_rank": int(fr_rank[i])}
        if sr is not None:
            row |= {"mu_swiss": sr["mu"][i], "mu_swiss_se": sr["se"][i], "mu_swiss_rank": int(sr_rank[i]),
                    "swiss_mean_rank": sr["mean_rank"][i], "swiss_p_qualify": sr["p_qualify"][i]}
        rows.append(row)
    key = f"{mode}/{field}"
    sec = summary["sections"].setdefault("references", {})
    sec[key] = {"field_reference": fr and {"calib_id": fr["calib_id"], "hodge": fr["hodge"]},
                "swiss_reference": sr and {"cell_id": sr["cell_id"], "n_tournaments": sr["n"]}}
    if fr is not None and sr is not None and list(fr["bots"]) == list(sr["bots"]):
        mu_f, mu_s = np.asarray(fr["mu"]), np.asarray(sr["mu"])
        with np.errstate(divide="ignore", invalid="ignore"):
            z_f = (mu_f[:, None] - mu_f[None, :]) / np.hypot(fr["se"][:, None], fr["se"][None, :])
            z_s = (mu_s[:, None] - mu_s[None, :]) / np.hypot(sr["se"][:, None], sr["se"][None, :])
        disc = [(bots[i], bots[j]) for i in range(len(bots)) for j in range(len(bots))
                if i != j and z_f[i, j] > 2 and z_s[i, j] < -2]
        sec[key]["ordering_agreement"] = mt.rank_agreement(mu_f, mu_s) | {
            "significant_discordant_pairs": disc,
            "note": "mu_field and mu_swiss are different estimands; neither is 'the true ranking'"}
    return rows


def _schedule_diagnostic(root: Path, src: Cell, frozen: Cell, adapt: Cell, j: int, n_boot: int) -> list[dict]:
    """Within-source rerun agreement: frozen schedule vs adaptive (same round-1 tables and randomness)."""
    f_reps, a_reps = set(_existing(root, frozen)), set(_existing(root, adapt))
    sources = sorted({r // j for r in f_reps} & {r // j for r in a_reps})
    sources = [s for s in sources if all(s * j + x in f_reps and s * j + x in a_reps for x in range(j))]
    if len(sources) < 2:
        return []
    reps = [s * j + x for s in sources for x in range(j)]
    fa = load_cell_arrays(root, frozen, reps)
    aa = load_cell_arrays(root, adapt, reps)
    k = fa["K"]
    names = ("topk_overlap", "kendall_tau", "spearman_rho", "mean_abs_rank_diff")

    def per_source(arr: dict) -> np.ndarray:
        out = np.zeros((len(sources), len(names)))
        for si in range(len(sources)):
            sl = slice(si * j, (si + 1) * j)
            rank, qual = arr["final_rank"][sl], arr["qualified"][sl]
            mats = [mt.overlap_matrix(qual).astype(float), mt.kendall_matrix(rank), mt.spearman_matrix(rank),
                    mt.mean_abs_rank_diff_matrix(rank)]
            out[si] = [mt.pair_mean(m) for m in mats]
        return out

    fs, as_ = per_source(fa), per_source(aa)
    ws = mt.bootstrap_weights(len(sources), n_boot, seed=20261001)
    rows = []
    base = {"mode": src.mode.mode, "field_id": src.field.field_id, "source_cell": src.cell_id,
            "frozen_cell": frozen.cell_id, "adaptive_cell": adapt.cell_id, "n_sources": len(sources),
            "replays_per_source": j, "R": src.protocol.rounds, "H": src.protocol.hands_per_match, "K": k,
            "unit": "source schedule (cluster bootstrap)",
            "interpretation": "diagnostic contrast only; not an additive variance decomposition"}
    for c, name in enumerate(names):
        def m_of(x: np.ndarray, w: np.ndarray | None, _c: int = c) -> float:
            return float(x[:, _c].mean() if w is None else (w @ x[:, _c]) / w.sum())
        ef = mt.bootstrap(lambda w: m_of(fs, w), len(sources), weights=ws)
        ea = mt.bootstrap(lambda w: m_of(as_, w), len(sources), weights=ws)
        ed = mt.bootstrap(lambda w: m_of(as_, w) - m_of(fs, w), len(sources), weights=ws)
        rows.append(base | {"metric": name} | ef.to_dict("frozen_") | ea.to_dict("adaptive_")
                    | ed.to_dict("adaptive_minus_frozen_"))
    return rows
