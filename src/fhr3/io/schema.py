"""Block-level Parquet schema (one row per matched block).

Units: all payoff columns are in big blinds. ``D`` is the block total
``sum_s (X_A,s - X_B,s)`` over the k candidate seats (see eval/matched.py).

v2 (this version) = v1 + ``hands_a``, ``hands_b``, ``deal_layout``,
``estimator_config_hash``, ``estimator_ms``, ``allin_ev_hands``,
``variant_json``. v1 files remain readable (missing columns read as null) and
v1 rows can be replayed against current code (``validation.corpus``).

``NONDETERMINISTIC_COLUMNS`` are excluded from replay/serial-vs-parallel
equality checks; every other column must be bit-identical on re-run.
"""

from __future__ import annotations

import json
from typing import Any

import pyarrow as pa

from fhr3.configs.experiment import ExperimentConfig, Pairing
from fhr3.eval.matched import MatchedBlockResult
from fhr3.rng import SEED_DERIVATION_VERSION

SCHEMA_VERSION = "fhr3-block-v2"
COMPATIBLE_SCHEMA_VERSIONS = ("fhr3-block-v1", "fhr3-block-v2")

_f64, _i64, _i32, _str, _bool = pa.float64(), pa.int64(), pa.int32(), pa.string(), pa.bool_()

BLOCK_SCHEMA = pa.schema(
    [
        ("experiment_id", _str),
        ("run_id", _str),
        ("block_id", _i64),
        ("variant", _str),
        ("config_hash", _str),
        ("pairing_id", _str),
        ("pairing_hash", _str),
        ("seed", _i64),
        ("stack_bb", _f64),
        ("player_count", _i32),
        ("candidate_a", _str),
        ("candidate_a_version", _str),
        ("candidate_b", _str),
        ("candidate_b_version", _str),
        ("reference_population", _str),
        ("reference_version", _str),
        ("candidate_coupling", _str),
        ("reference_coupling", _str),
        ("block_payoff_a", _f64),
        ("block_payoff_b", _f64),
        ("D", _f64),
        ("played_hands", _i32),
        ("candidate_hands_per_side", _i32),
        ("decision_count", _i32),
        ("runtime_ms", _f64),
        ("agent_ms", _f64),
        ("valid", _bool),
        ("error_code", _str),
        ("error_detail", _str),
        ("raw_estimator_D", _f64),
        ("allin_ev_D", _f64),
        ("mivat_D", _f64),
        ("aivat_D", _f64),
        # Seat-level diagnostics (index = candidate seat; seat 0 = SB).
        ("seat_payoff_a", pa.list_(_f64)),
        ("seat_payoff_b", pa.list_(_f64)),
        ("seat_D", pa.list_(_f64)),
        # Hand-level diagnostics aggregated over the 2k hands of the block.
        ("showdown_hands", _i32),
        ("allin_hands", _i32),
        ("pot_bb_sum", _f64),
        ("pot_bb_max", _f64),
        ("traced", _bool),
        # v2 additions
        ("hands_a", _i32),  # candidate hands actually played, side A (k unless Nit Game)
        ("hands_b", _i32),
        ("deal_layout", _str),  # equal layout + equal seeds => same cards per block id
        ("estimator_config_hash", _str),
        ("estimator_ms", _f64),
        ("allin_ev_hands", _i32),  # hands with an all-in runout (EV replaced the realized payoff)
        ("variant_json", _str),  # variant-specific diagnostics (e.g. nit rounds)
        ("matched_protocol_version", _str),
        ("seed_derivation_version", _str),
        ("schema_version", _str),
    ]
)

NONDETERMINISTIC_COLUMNS = frozenset({"run_id", "runtime_ms", "agent_ms", "estimator_ms", "traced"})


def result_to_row(
    cfg: ExperimentConfig,
    pairing: Pairing,
    versions: dict[str, str],
    result: MatchedBlockResult,
    run_id: str,
    traced: bool,
    deal_layout: str | None = None,
) -> dict[str, Any]:
    hands = result.hands if result.valid else []
    has_allin = "allin_ev" in result.seat_estimates
    return {
        "experiment_id": cfg.experiment_id,
        "run_id": run_id,
        "block_id": result.block_id,
        "variant": cfg.game.variant,
        "config_hash": cfg.config_hash,
        "pairing_id": pairing.pairing_id,
        "pairing_hash": pairing.pairing_hash,
        "seed": result.seed,
        "stack_bb": cfg.game.stack_bb,
        "player_count": cfg.game.player_count,
        "candidate_a": pairing.candidate_a.agent_id,
        "candidate_a_version": versions["A"],
        "candidate_b": pairing.candidate_b.agent_id,
        "candidate_b_version": versions["B"],
        "reference_population": pairing.reference_population,
        "reference_version": pairing.reference_version,
        "candidate_coupling": cfg.rng.candidate_coupling,
        "reference_coupling": cfg.rng.reference_coupling,
        "block_payoff_a": result.block_payoff_a,
        "block_payoff_b": result.block_payoff_b,
        "D": result.D,
        "played_hands": result.played_hands,
        "candidate_hands_per_side": cfg.game.player_count,
        "decision_count": result.decision_count,
        "runtime_ms": result.runtime_ms,
        "agent_ms": result.agent_ms,
        "valid": result.valid,
        "error_code": result.error_code,
        "error_detail": result.error_detail,
        "raw_estimator_D": result.D,
        "allin_ev_D": result.estimator_D("allin_ev"),
        "mivat_D": result.estimator_D("mivat"),
        "aivat_D": result.estimator_D("aivat"),
        "seat_payoff_a": result.seat_payoff_a,
        "seat_payoff_b": result.seat_payoff_b,
        "seat_D": result.seat_D if result.valid else [],
        "showdown_hands": sum(h.showdown for h in hands),
        "allin_hands": sum(h.all_in for h in hands),
        "pot_bb_sum": sum(h.pot_bb for h in hands),
        "pot_bb_max": max((h.pot_bb for h in hands), default=0.0),
        "traced": traced,
        "hands_a": result.hands_for("A") if result.valid else None,
        "hands_b": result.hands_for("B") if result.valid else None,
        "deal_layout": deal_layout,
        "estimator_config_hash": cfg.estimator_config_hash,
        "estimator_ms": result.estimator_ms,
        "allin_ev_hands": sum(h.allin_runout for h in hands) if has_allin and result.valid else None,
        "variant_json": json.dumps(result.variant_info, sort_keys=True) if result.variant_info else None,
        "matched_protocol_version": result.protocol,
        "seed_derivation_version": SEED_DERIVATION_VERSION,
        "schema_version": SCHEMA_VERSION,
    }


def rows_to_table(rows: list[dict[str, Any]]) -> pa.Table:
    return pa.Table.from_pylist(rows, schema=BLOCK_SCHEMA)
