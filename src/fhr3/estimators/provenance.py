"""Estimator provenance: everything that determines an estimator column besides the raw game.

``estimator_provenance(settings)`` expands the ``estimators:`` config into an
explicit record per enabled estimator:

* the settings as configured (MC sample counts, flop samples, salts, value-function
  path + pinned sha256);
* the method version of the implementation (bumped whenever its output could change);
* the RNG stream derivation (estimator streams are separate keyed streams, never the
  dealing / policy streams, so estimator settings cannot change cards, actions or raw D);
* the PVAT version for MIVAT/AIVAT.

The record is hashed into ``estimator_config_hash`` (stored on every block) and written
into the experiment lock, so a silent change of estimator code, library version or
value-function artifact under the same experiment_id is refused rather than mixed.
"""

from __future__ import annotations

import importlib.metadata
from collections.abc import Mapping
from typing import Any

from fhr3.estimators.allin_ev import VERSION as ALLIN_EV_VERSION

VAT_METHOD_VERSION = "fhr3-vat-pvat-1"
PROVENANCE_VERSION = "fhr3-estimator-provenance-1"


def pvat_version() -> str:
    try:
        return importlib.metadata.version("pvat")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover - pinned dependency
        return "not-installed"


def estimator_provenance(settings: Mapping[str, Any]) -> dict[str, Any]:
    from fhr3.estimators.vat import FEATURE_VERSION

    out: dict[str, Any] = {"provenance_version": PROVENANCE_VERSION, "estimators": {}}
    for name, opts in sorted(settings.items()):
        opts = dict(opts or {})
        if not opts.get("enabled", True):
            continue
        if name == "allin_ev":
            rec = {"method_version": ALLIN_EV_VERSION,
                   "rng_stream": "KeyedStream('allin-ev', method_version, salt, *hand_key)",
                   "settings": {"mc_samples": opts.get("mc_samples", 200),
                                "exact_max_combos": opts.get("exact_max_combos", 1200),
                                "salt": opts.get("salt", 0)}}
        elif name in ("mivat", "aivat"):
            rec = {"method_version": VAT_METHOD_VERSION, "feature_version": FEATURE_VERSION,
                   "pvat_version": pvat_version(),
                   "rng_stream": "KeyedStream('vat', salt, *hand_key)",
                   "settings": {"flop_samples": opts.get("flop_samples", 16), "salt": opts.get("salt", 0),
                                "value_function": str(opts.get("value_function", "prior")),
                                "value_function_sha256": opts.get("value_function_sha256")}}
        else:
            rec = {"settings": opts}  # unknown names are rejected by build_estimators
        out["estimators"][name] = rec
    return out


__all__ = ["PROVENANCE_VERSION", "VAT_METHOD_VERSION", "estimator_provenance", "pvat_version"]
