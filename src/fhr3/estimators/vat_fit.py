"""Fit a frozen linear value function for MIVAT/AIVAT on *training* data.

Training blocks are simulated under a different root seed than the evaluation
experiment (enforced), so the fitted parameters never see evaluation blocks.
The output JSON is pinned by sha256 in the evaluation config.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from fhr3.configs.experiment import ExperimentConfig, config_from_dict
from fhr3.estimators.provenance import VAT_METHOD_VERSION, pvat_version
from fhr3.estimators.vat import FEATURE_VERSION, FEATURES, VATEstimator, fit_theta
from fhr3.eval.matched import HandContext
from fhr3.eval.runner import BlockSimulator
from fhr3.io.manifest import git_info, now_iso


class _Collector:
    name, needs_decision_log = "vat_fit_collect", True

    def __init__(self, est: VATEstimator) -> None:
        self.est = est
        self.terms: list[Any] = []

    def estimate(self, ctx: HandContext) -> float:
        self.terms.append(self.est.terminal(ctx))
        return float(ctx.outcome.payoffs_chips[ctx.candidate_position])


def fit_value_function(
    cfg: ExperimentConfig, pairing_ids: list[str], start: int, end: int, training_root_seed: int,
    kind: str, flop_samples: int, out: Path,
) -> dict[str, Any]:
    if training_root_seed == cfg.root_seed:
        raise ValueError("training root seed must differ from the evaluation root seed")
    raw = copy.deepcopy(dict(cfg.raw))
    raw["root_seed"] = training_root_seed
    raw["experiment_id"] = f"{cfg.experiment_id}--vat-training"
    raw.pop("estimators", None)
    train = config_from_dict(raw)
    est = VATEstimator(kind, np.zeros(len(FEATURES)), flop_samples)
    col = _Collector(est)
    for pid in pairing_ids:
        sim = BlockSimulator(train, train.pairing(pid))
        sim.estimators = [col]
        for b in range(start, end):
            r = sim.run(b)
            if not r.valid:
                raise RuntimeError(f"invalid training block {pid}/{b}: {r.error_detail}")
    theta = fit_theta(est, col.terms)
    raw_var = float(np.var([t.t.realized_bb for t in col.terms]))
    fit_var = float(np.var([t.t.realized_bb + theta @ est.correction_features(t) for t in col.terms]))
    meta = {
        "feature_version": FEATURE_VERSION,
        "features": list(FEATURES),
        "theta": theta.tolist(),
        "kind_fitted": kind,
        "flop_samples": flop_samples,
        "training_root_seed": training_root_seed,
        "training_config_hash": train.config_hash,
        "evaluation_config_hash": cfg.config_hash,
        "pairings": pairing_ids,
        "blocks": [start, end],
        "n_hand_histories": len(col.terms),
        "in_sample_per_hand_variance": {"raw": raw_var, "fitted": fit_var},
        "method_version": VAT_METHOD_VERSION,
        "pvat_version": pvat_version(),
        "git": git_info(),
    }
    # the pinned artifact is a deterministic function of (code, config, training seed,
    # blocks): refitting reproduces the same bytes and sha256. The wall-clock timestamp
    # lives in a sidecar that is not pinned.
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(meta, indent=1, sort_keys=True))
    meta["sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
    out.with_suffix(".created.json").write_text(json.dumps({"artifact": out.name, "sha256": meta["sha256"],
                                                            "created_at": now_iso()}, indent=1))
    return meta
