"""Deterministic field selection from a frozen pool calibration.

Given the pool calibration chunks (identified by ``calibration_digest``), the three
controlled fields are pure functions of the calibration result and the selection
parameters in configs/fhr3b/matrix.yaml:

* ``spread``          evenly spaced positions along the calibrated mu_field ranking;
* ``crowded_cutoff``  the ``n_top`` strongest bots, then the tightest window of
                      ``crowd`` consecutive bots (smallest mu range) placed to
                      straddle the top-K cut, then evenly spaced fill from below;
* matchup field       greedy backward elimination maximising the debiased cyclic
                      (non-transitive) share of the presence-effect flow. It is
                      labelled ``matchup_sensitive`` only if the 95% bootstrap lower
                      bound of that share clears the frozen gate; otherwise
                      ``style_diverse``.

Manifests are written once (immutable) and carry the calibration identity/digest.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from fhr3.tournament.calibration import (
    analyse_calibration,
    bot_rows,
    calibration_digest,
    cyclic_triads,
    load_calibration,
    matchup_rows,
    select_matchup,
    subset_hodge,
    subset_share_ci,
)
from fhr3.tournament.experiments import Profile
from fhr3.tournament.fields import select_crowded, select_spread, subset, write_field_immutable
from fhr3.tournament.manifests import identity_hash

SELECTION_VERSION = "fhr3b-selection-v1"


def _csv(path: Path, rows: list[dict[str, Any]]) -> None:
    from fhr3.tournament.analysis import _write_csv

    _write_csv(path, rows)


def select_fields(root: Path, prof: Profile, mode: str, reports: Path, n_boot: int = 300) -> dict[str, Any]:
    spec = prof.calibration_spec(mode, "pool")
    tabs = load_calibration(root, spec)
    if not tabs:
        raise FileNotFoundError(f"no pool calibration for {mode}; run `fhr3b calibrate --stage pool` first")
    pool = spec.field
    bots = sorted(pool.bot_ids)
    res = analyse_calibration(tabs, bots, n_boot=n_boot)
    mu = {b: float(res["mu"][i]) for i, b in enumerate(bots)}
    ranked = sorted(bots, key=lambda b: (-mu[b], b))
    sel = prof.selection
    n, k = int(sel["n"]), prof.k
    digest = calibration_digest(root, spec)
    common = {"selection_version": SELECTION_VERSION, "calibration_id": spec.calib_id,
              "calibration_identity_hash": identity_hash(spec.identity), "calibration_digest": digest,
              "calibration_round_groups": res["rounds_groups"]}

    spread_ids = select_spread(ranked, n)
    crowd_ids, crowd_info = select_crowded(ranked, mu, n, k, **sel["crowded"])
    match_ids = select_matchup(res, bots, n)
    share, lo, hi = subset_share_ci(res, match_ids, n_boot=n_boot)
    gate = float(sel["matchup_gate"]["min_ci_lower_cyclic_share"])
    passed = bool(np.isfinite(lo) and lo >= gate)
    label = "matchup_sensitive" if passed else "style_diverse"
    match_ix = [bots.index(b) for b in match_ids]
    sub_a = res["M"][np.ix_(match_ix, match_ix)]
    triads = cyclic_triads(sub_a - sub_a.T)

    out_dir = prof.fields_dir / mode
    fields = {
        "spread": subset(pool, f"{mode}-spread", "spread", spread_ids,
                         common | {"method": "evenly spaced mu_field ranks", "n": n}),
        "crowded_cutoff": subset(pool, f"{mode}-crowded_cutoff", "crowded_cutoff", crowd_ids,
                                 common | {"method": "top + tightest window straddling top-K + spread fill",
                                           "n": n, "K": k} | crowd_info),
        label: subset(pool, f"{mode}-{label}", label, match_ids,
                      common | {"method": "greedy max debiased cyclic share", "n": n,
                                "gate": {"statistic": "debiased cyclic share (95% bootstrap lower bound)",
                                         "threshold": gate, "value": share, "ci": [lo, hi], "passed": passed},
                                "cyclic_triads": triads}),
    }
    written = {name: str(write_field_immutable(fm, out_dir / f"{name}.json")) for name, fm in fields.items()}

    rep = reports / "field-calibration" / mode
    _csv(rep / "pool_bots.csv", bot_rows(res, pool))
    _csv(rep / "pool_matchup_matrix.csv", list(matchup_rows(res)))
    summary = {
        "mode": mode, "pool_hash": pool.field_hash, **common,
        "pool_hodge": res["hodge"],
        "fields": {name: {"field_id": fm.field_id, "field_hash": fm.field_hash, "path": written[name],
                          "hodge_on_pool_data": subset_hodge(res, fm.bot_ids)}
                   for name, fm in fields.items()},
        "matchup_label": label,
        "matchup_gate": {"threshold": gate, "value": share, "ci": [lo, hi], "passed": passed},
    }
    (rep / "selection.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=float) + "\n")
    return summary


def field_reference_report(root: Path, prof: Profile, mode: str, field: str, reports: Path,
                           n_boot: int = 300) -> dict[str, Any]:
    """mu_field inside a frozen field + confirmation of its construction property."""
    spec = prof.calibration_spec(mode, "field", field)
    tabs = load_calibration(root, spec)
    if not tabs:
        raise FileNotFoundError(f"no field-reference calibration for {mode}/{field}")
    fm = spec.field
    bots = sorted(fm.bot_ids)
    res = analyse_calibration(tabs, bots, n_boot=n_boot)
    rep = reports / "field-calibration" / mode / fm.field_id
    _csv(rep / "reference_bots.csv", bot_rows(res, fm))
    _csv(rep / "reference_matchup_matrix.csv", list(matchup_rows(res)))
    order = np.argsort(-res["mu"], kind="stable")
    k = prof.k
    mu_sorted = res["mu"][order]
    out = {"mode": mode, "field_id": fm.field_id, "field_hash": fm.field_hash, "calib_id": spec.calib_id,
           "calibration_digest": calibration_digest(root, spec), "hodge": res["hodge"],
           "gap_at_cutoff": float(mu_sorted[k - 1] - mu_sorted[k]) if len(bots) > k else None,
           "median_se": float(np.median(res["se"]))}
    if fm.kind == "crowded_cutoff":
        c = fm.construction
        lo_r, hi_r = int(c["n_top"]), int(c["n_top"]) + int(c["crowd"])
        out["crowd_mu_range_in_field_reference"] = float(mu_sorted[lo_r] - mu_sorted[hi_r - 1])
    (rep / "reference.json").write_text(json.dumps(out, indent=1, sort_keys=True, default=float) + "\n")
    return out
