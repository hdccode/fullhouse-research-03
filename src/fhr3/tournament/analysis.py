"""FHR3B analysis pipeline: stored tournaments -> machine-readable reports.

Reads only stored results (never re-runs poker). Every uncertainty is computed over
complete tournaments (or, for the schedule diagnostic, over independent source
schedules). Paired comparisons (R sweep, budget sweep) share bootstrap weights over
the same tournament/replicate indices. Sections without data are written with a
header only and marked ``"status": "no data"`` in summary.json.

Outputs (``<out>/``): baseline_reliability.csv, qualification_probabilities.csv,
rank_stability.csv, round_sweep.csv, budget_allocation.csv, frozen_schedule.csv (core C),
swiss_reference_bots.csv (mu_swiss; per-field summaries in summary.json),
schedule_diagnostic.csv (supplementary C), duplicate_play.csv, pairwise_inversions.csv,
pairwise_inversions_binned.csv, field_references.csv, figure_data/*.csv, summary.json,
MANIFEST.json.
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
from fhr3.tournament.calibration import analyse_calibration, calib_dir, load_calibration, verify_calibration_lanes
from fhr3.tournament.cells import Cell
from fhr3.tournament.core import scheduled_hands
from fhr3.tournament.manifests import ANALYSIS_VERSION
from fhr3.tournament.store import cell_dir, completed_replicates, load_cell_arrays

CELL_COLS = ["experiment", "mode", "field_id", "field_kind", "field_hash", "cell_id", "identity_hash", "R", "H", "K",
             "N", "namespace"]
BB_CHIPS = 100.0
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
    verify_calibration_lanes(root, spec)
    # normalised to the ordinary-match scale (lane sum / k); rankings, comparisons and accuracy use this
    res = analyse_calibration(tabs, sorted(spec.field.bot_ids), n_boot=200, lanes=spec.lanes)
    return {"bots": res["bots"], "mu": res["mu"], "se": res["se"], "mu_lane_sum": res["mu_lane_sum"],
            "lanes": res["lanes"], "calib_id": spec.calib_id, "n_groups": res["rounds_groups"]}


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
            min_tournaments: int = 2, profile: str = "publication", horizon: int | None = None) -> dict[str, Any]:
    root, out = Path(root), Path(out)
    prof = ex.load_profile(profile, root)
    mx = ex.load_matrix(prof.config_root)
    E = mx["experiments"]
    modes = list(modes or mx["primary_modes"])
    summary: dict[str, Any] = {"analysis_version": ANALYSIS_VERSION, "profile": profile, "results_root": str(root),
                               "sections": {}, "pairing": ex.PAIRED_NOTE,
                               "lab": {"environment": prof.lab_name, "protocol": prof.base.name,
                                       "protocol_hash": prof.base.protocol_hash,
                                       "design_status": "predeclared research design choices; not 2026 FullHouse "
                                                        "settings (see paper/FHR3B_SCOPE.md)",
                                       "R0": prof.r0, "H0": prof.h0, "K": prof.k,
                                       "round_sweep": prof.checkpoints_for(horizon or prof.r0),
                                       "horizon": horizon or prof.r0,
                                       "horizon_status": "initial research horizon; not assumed sufficient",
                                       "allocations": [a.__dict__ | {"budget": a.budget} for a in prof.allocations()]}}
    inputs: list[dict[str, Any]] = []
    base_rows, q_rows, rank_rows, sweep_rows, fig2_rows, inv_rows, inv_bin_rows = [], [], [], [], [], [], []
    budget_rows, sched_rows, ref_rows, acc_rows, dup_rows, frozen_rows = [], [], [], [], [], []
    swiss_bot_rows: list[dict[str, Any]] = []
    fields = list(prof.fields)

    for mode in modes:
        for field in fields:
            fr = field_reference(root, prof, mode, field)
            sr = swiss_reference(root, prof, mode, field)
            ref_rows.extend(_reference_rows(mode, field, fr, sr, summary))
            cell = _try(prof.cell, mode, field, "baseline", horizon)
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
            for rr in prof.checkpoints_for(cell.protocol.rounds):
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
                for rname, rref in (("mu_field", fr), ("mu_swiss", sr)):  # accuracy against BOTH references
                    if rref is not None and list(rref["bots"]) == list(a["bots"]):
                        acc = mt.accuracy_vs_reference(a["final_rank"], np.asarray(rref["mu"], float), a["K"],
                                                       weights=ws)
                        acc_rows.append(info | {"reference": rname} | mt.estimates_to_row(acc))
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

        # D: ordinary vs duplicate play at (approximately) equal simulator work, paired by replicate
        if mode in E.get("duplicate_play", {}).get("modes", []):
            for field in E["duplicate_play"]["fields"]:
                cells = _try(prof.duplicate_cells, mode, field)
                if not cells:
                    continue
                reps_by = {lab: set(_existing(root, c)) for lab, c in cells}
                common = sorted(set.intersection(*reps_by.values())) if reps_by else []
                if len(common) < min_tournaments:
                    continue
                ws = mt.bootstrap_weights(len(common), n_boot, seed=20261002)
                work0 = sched0 = None
                for lab, c in cells:
                    inputs.append(_input(root, c, common, "duplicate_play"))
                    a = load_cell_arrays(root, c, common)
                    work = float(np.mean([_hands(root, c, r) for r in common]))
                    sched = scheduled_hands(c)
                    work0, sched0 = work0 or work, sched0 or sched
                    est = mt.rerun_stability(a["final_rank"], a["qualified"], a["K"], weights=ws)
                    dup_rows.append(_cell_info("duplicate_play", c) | {
                        "variant": lab, "match_format": c.protocol.match_format,
                        "lanes": c.protocol.table_size if c.protocol.match_format == "duplicate" else 1,
                        "hands_scheduled_per_tournament": sched, "scheduled_work_ratio_vs_ordinary": sched / sched0,
                        "hands_simulated_per_tournament": work, "work_ratio_vs_ordinary": work / work0,
                        "n_common_replicates": len(common)} | mt.estimates_to_row(est))

        # mu_swiss reference outputs (per field)
        for field in fields:
            sc_cell = _try(prof.swiss_reference_cell, mode, field)
            if sc_cell is None:
                continue
            rep_ = swiss_reference_report(root, sc_cell, field_reference(root, prof, mode, field), n_boot=n_boot)
            if rep_ is not None:
                info = _cell_info("swiss_reference", sc_cell)
                swiss_bot_rows.extend(info | r for r in rep_[0])
                summary["sections"].setdefault("swiss_reference", {})[sc_cell.cell_id] = rep_[1]
                inputs.append(_input(root, sc_cell, _existing(root, sc_cell), "swiss_reference"))

        # C (core): adaptive baseline vs frozen replay of each baseline schedule, paired by source
        if mode in E.get("frozen_schedule", {}).get("modes", []):
            for field in E["frozen_schedule"]["fields"]:
                sd = _try(prof.schedule_cells, mode, field, int(E["frozen_schedule"]["replays_per_source"]))
                if sd is None:
                    continue
                fr = field_reference(root, prof, mode, field)
                rows = _frozen_schedule(root, sd[0], sd[1], n_boot, fr)
                if rows:
                    frozen_rows.extend(rows)
                    inputs.append(_input(root, sd[1], _existing(root, sd[1]), "frozen_schedule"))

        # C (supplementary): within-source schedule diagnostic (J replays per source)
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
        "duplicate_play.csv": (dup_rows, CELL_COLS),
        "frozen_schedule.csv": (frozen_rows, None),
        "swiss_reference_bots.csv": (swiss_bot_rows, CELL_COLS),
        "schedule_diagnostic.csv": (sched_rows, None),
        "pairwise_inversions.csv": (inv_rows, CELL_COLS),
        "pairwise_inversions_binned.csv": (inv_bin_rows, CELL_COLS),
        "field_references.csv": (ref_rows, None),
        "reference_accuracy.csv": (acc_rows, CELL_COLS),
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


def _hands(root: Path, cell: Cell, rep: int) -> int:
    from fhr3.tournament.store import tournament_dir

    return int(json.loads((tournament_dir(root, cell, rep) / "manifest.json").read_text())["hands_played"])


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
            row |= {"mu_field": fr["mu"][i], "mu_field_se": fr["se"][i], "mu_field_rank": int(fr_rank[i]),
                    "mu_field_lane_sum": fr["mu_lane_sum"][i], "mu_field_lanes": fr["lanes"]}
        if sr is not None:
            row |= {"mu_swiss": sr["mu"][i], "mu_swiss_se": sr["se"][i], "mu_swiss_rank": int(sr_rank[i]),
                    "swiss_mean_rank": sr["mean_rank"][i], "swiss_p_qualify": sr["p_qualify"][i]}
        rows.append(row)
    key = f"{mode}/{field}"
    sec = summary["sections"].setdefault("references", {})
    sec[key] = {"field_reference": fr and {"calib_id": fr["calib_id"], "n_groups": fr["n_groups"],
                                           "lanes": fr["lanes"], "scale": "lane_sum / lanes (ordinary-match)",
                                           "coupling": "common random numbers across fields (not independent)"},
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


def _cluster_pair_mean(mat: np.ndarray, cluster: np.ndarray, w: np.ndarray | None) -> float:
    """Mean of ``mat`` over pairs of tournaments from DIFFERENT clusters (source tournaments).

    ``w`` are bootstrap counts per cluster (None = point estimate); each tournament inherits its
    cluster's weight. With one tournament per cluster this is ``metrics.pair_mean``.
    """
    wt = np.ones(len(cluster)) if w is None else np.asarray(w, float)[cluster]
    other = cluster[:, None] != cluster[None, :]
    ww = np.outer(wt, wt) * other
    den = ww.sum()
    return float((ww * mat).sum() / den) if den > 0 else float("nan")


def _frozen_schedule(root: Path, src: Cell, frozen: Cell, n_boot: int, fr: dict | None) -> list[dict]:
    """Core C: the adaptive baseline vs source-schedule counterfactual replays, paired by source.

    Estimand. Source adaptive tournament s (a baseline replicate) generates a realised Swiss
    schedule. Frozen replay j of s plays exactly that schedule with FRESH poker randomness (new
    cards and decisions); its own results cannot change its later pairings. The frozen arm
    therefore removes within-run result -> future-pairing feedback while keeping realistic Swiss
    schedule structure. It is not an identical-randomness causal pair of the source run.

    Both arms are summarised by the same between-tournament reliability metrics (pairs of
    tournaments from different sources) and accuracy against mu_field. The bootstrap resamples
    SOURCE tournaments; a source carries its baseline tournament and all its J frozen replays, so
    replays of one source are never treated as independent observations (J = 1 in the initial core;
    J > 1 is a later precision extension).
    """
    j = frozen.replays_per_source
    a_have, f_have = set(_existing(root, src)), set(_existing(root, frozen))
    sources = sorted(s for s in a_have if all(s * j + x in f_have for x in range(j)))
    if len(sources) < 2:
        return []
    a = load_cell_arrays(root, src, sources)
    f = load_cell_arrays(root, frozen, [s * j + x for s in sources for x in range(j)])
    k = a["K"]
    a_cl = np.arange(len(sources))
    f_cl = np.repeat(np.arange(len(sources)), j)
    ws = mt.bootstrap_weights(len(sources), n_boot, seed=20261003)

    def mats(arr: dict) -> dict[str, np.ndarray]:
        ov = mt.overlap_matrix(arr["qualified"]).astype(float)
        return {"changed_qualifiers": k - ov, "topk_overlap": ov, "kendall_tau": mt.kendall_matrix(arr["final_rank"]),
                "spearman_rho": mt.spearman_matrix(arr["final_rank"]),
                "mean_abs_rank_diff": mt.mean_abs_rank_diff_matrix(arr["final_rank"])}

    def wmean(x: np.ndarray, cl: np.ndarray, w: np.ndarray | None) -> np.ndarray:
        wt = np.ones(len(cl)) if w is None else np.asarray(w, float)[cl]
        return (wt @ x) / wt.sum()

    def ambiguous(arr: dict, cl: np.ndarray, w: np.ndarray | None) -> float:
        p = wmean(arr["qualified"].astype(float), cl, w)
        return float(((p >= 0.1) & (p <= 0.9)).sum())

    ma, mf = mats(a), mats(f)
    stats: dict[str, tuple[Any, Any]] = {
        name: ((lambda w, _m=ma[name]: _cluster_pair_mean(_m, a_cl, w)),
               (lambda w, _m=mf[name]: _cluster_pair_mean(_m, f_cl, w))) for name in ma}
    stats["n_ambiguous_bots"] = ((lambda w: ambiguous(a, a_cl, w)), (lambda w: ambiguous(f, f_cl, w)))
    if fr is not None and list(fr["bots"]) == list(a["bots"]):
        mu = np.asarray(fr["mu"], float)
        ref_top = ((-mu).argsort(kind="stable").argsort() + 1) <= k
        rc_a = (k - ((a["final_rank"] <= k) & ref_top[None, :]).sum(1)).astype(float)
        rc_f = (k - ((f["final_rank"] <= k) & ref_top[None, :]).sum(1)).astype(float)
        stats["reference_changed_vs_mu_field"] = ((lambda w: float(wmean(rc_a, a_cl, w))),
                                                  (lambda w: float(wmean(rc_f, f_cl, w))))
    base = {"mode": src.mode.mode, "field_id": src.field.field_id, "adaptive_cell": src.cell_id,
            "frozen_cell": frozen.cell_id, "n_sources": len(sources), "replays_per_source": j,
            "R": src.protocol.rounds, "H": src.protocol.hands_per_match, "K": k,
            "unit": "source adaptive tournament (cluster bootstrap; replays of one source never independent)",
            "estimand": "source-schedule counterfactual: realised Swiss schedule of the source, fresh poker "
                        "randomness, no result -> future-pairing feedback; not an identical-randomness pair",
            "interpretation": "diagnostic of Swiss feedback; not an additive variance decomposition"}
    rows = []
    for name, (sa, sf) in stats.items():
        ea = mt.bootstrap(sa, len(sources), weights=ws)
        ef = mt.bootstrap(sf, len(sources), weights=ws)
        ed = mt.bootstrap(lambda w, _a=sa, _f=sf: _a(w) - _f(w), len(sources), weights=ws)
        rows.append(base | {"metric": name} | ea.to_dict("adaptive_") | ef.to_dict("frozen_")
                    | ed.to_dict("adaptive_minus_frozen_"))
    return rows


def swiss_reference_report(root: Path, cell: Cell, fr: dict | None, n_boot: int = 1000,
                           ambiguous_band: tuple[float, float] = (0.1, 0.9)) -> tuple[list[dict], dict] | None:
    """mu_swiss reference outputs: per-bot P(qualify), expected final performance, rank / top-K
    uncertainty, boundary bots, and expected top-K overlap against mu_field and mu_swiss.

    Unit = complete tournament; the bootstrap resamples tournaments jointly for every bot. In
    crowded_cutoff / style_diverse the rank-6/7 ordering is expected to stay ambiguous: that
    ambiguity is part of the experimental object, not a precision failure.
    """
    from fhr3.tournament.diagnostics import reference_rank_diagnostics

    reps = _existing(root, cell)
    if len(reps) < 2:
        return None
    a = load_cell_arrays(root, cell, reps)
    m, k, r_ = len(reps), a["K"], cell.protocol.rounds
    sc = a["final_score"].astype(float)
    ws = mt.bootstrap_weights(m, n_boot, seed=20261004)
    mu = sc.mean(0)
    boot_mu = (ws @ sc) / ws.sum(1, keepdims=True)
    diag = reference_rank_diagnostics(mu, boot_mu, k)
    q = mt.qualification_table(a["qualified"], a["bots"])
    rank = a["final_rank"]
    mu_rank = (-mu).argsort(kind="stable").argsort() + 1
    lo_b, hi_b = ambiguous_band
    bots = []
    for i, b in enumerate(a["bots"]):
        pq_ = q[i]["p_qualify"]
        bots.append({"bot_id": b, "n_tournaments": m, "mu_swiss_final_score": mu[i],
                     "mu_swiss_final_score_se": sc[:, i].std(ddof=1) / np.sqrt(m),
                     "mu_swiss_per_match_bb": mu[i] / r_ / BB_CHIPS,
                     "mu_swiss_per_match_se_bb": sc[:, i].std(ddof=1) / np.sqrt(m) / r_ / BB_CHIPS,
                     "mu_swiss_rank": int(mu_rank[i]), "mu_swiss_rank_lo95": diag["per_bot"]["rank_lo95"][i],
                     "mu_swiss_rank_hi95": diag["per_bot"]["rank_hi95"][i],
                     "p_in_mu_swiss_top_k": diag["per_bot"]["p_top_k"][i],
                     "p_qualify": pq_, "p_qualify_wilson_lo": q[i]["wilson_lo"], "p_qualify_wilson_hi": q[i]["wilson_hi"],
                     "mean_final_rank": rank[:, i].mean(), "sd_final_rank": rank[:, i].std(ddof=1),
                     "q05_final_rank": np.quantile(rank[:, i], 0.05), "q95_final_rank": np.quantile(rank[:, i], 0.95),
                     "ambiguous_qualification": bool(lo_b <= pq_ <= hi_b)})
    stab = mt.rerun_stability(rank, a["qualified"], k, weights=ws)
    acc = {}
    if fr is not None and list(fr["bots"]) == list(a["bots"]):
        acc["vs_mu_field"] = mt.estimates_to_row(mt.accuracy_vs_reference(rank, np.asarray(fr["mu"], float), k,
                                                                          weights=ws))
    acc["vs_mu_swiss_in_sample"] = mt.estimates_to_row(mt.accuracy_vs_reference(rank, mu, k, weights=ws))
    summary = {"cell_id": cell.cell_id, "field_id": cell.field.field_id, "n_tournaments": m,
               "replicates": [int(min(reps)), int(max(reps))], "K": k, "R": r_,
               "expected_topk_overlap": acc,
               "rerun_stability": mt.estimates_to_row(stab),
               "n_ambiguous_bots": int(sum(x["ambiguous_qualification"] for x in bots)),
               "boundary_bots": [x["bot_id"] for x in sorted(bots, key=lambda x: x["mu_swiss_rank"])
                                 if x["ambiguous_qualification"] or 0.05 < x["p_in_mu_swiss_top_k"] < 0.95],
               "ranking_robustness": {kk: v for kk, v in diag.items() if kk != "per_bot"},
               "notes": ["vs_mu_swiss_in_sample uses the same tournaments that define mu_swiss (optimistic)",
                         "ambiguity near the cutoff is part of the experimental object in crowded_cutoff and "
                         "style_diverse; it is not expected to resolve into a clean rank-6/rank-7 order"]}
    return bots, summary


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
