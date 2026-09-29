"""Historical provenance record of the 2026 FullHouse qualifier (``historical_2026_reconstruction``).

This is *provenance*, not the FHR3B research baseline. The record keeps the facts the
public 2026 engine supports (``recovered``) and the historical values that are unknown
(``required``, null = UNKNOWN). Unknown values are never filled with research choices.

``to_protocol`` refuses while any required value is missing, which blocks only the
historical operational-validation experiment. Nothing in the controlled research
experiments (``fhr3b_baseline``) depends on this record.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from fhr3.configs.experiment import canonical_hash
from fhr3.tournament.protocol import TournamentProtocol

HISTORICAL_FILE = "protocols/historical_2026_reconstruction.yaml"


class HistoricalRecordIncomplete(RuntimeError):
    pass


@dataclass(frozen=True)
class HistoricalRecord:
    raw: dict[str, Any]

    @property
    def name(self) -> str:
        return self.raw["name"]

    @property
    def record_hash(self) -> str:
        """Hash of the whole historical record (audit provenance, not an experiment identity)."""
        return canonical_hash(self.raw)[:16]

    @property
    def required(self) -> dict[str, Any]:
        return dict(self.raw.get("required", {}))

    def missing(self) -> list[str]:
        return [k for k, v in self.required.items() if v is None]

    @property
    def unknowns(self) -> list[str]:
        return list(self.raw.get("unknowns", []))

    def to_protocol(self) -> TournamentProtocol:
        """Runnable historical protocol; only once every required value is supplied."""
        miss = self.missing()
        if miss:
            raise HistoricalRecordIncomplete(
                f"{self.name}: historical operational validation is BLOCKED (PENDING); UNKNOWN: {miss}")
        rec, req = self.raw["recovered"], self.required
        return TournamentProtocol(
            name=self.name, status="historical", table_size=int(rec["table_size"]),
            hands_per_match=int(rec["hands_per_match"]), rounds=int(req["qualifier_rounds"]),
            qualify_top_k=int(rec["qualify_top_k"]), stack_policy=rec["stack_policy"],
            initial_order=req["round_one_order"], tiebreaks=tuple(rec["tiebreaks"]),
            source=dict(self.raw["source"]),
        )


def load_historical(root: Path) -> HistoricalRecord:
    raw = yaml.safe_load((Path(root) / HISTORICAL_FILE).read_text())
    if raw.get("kind") != "historical_reconstruction":
        raise ValueError(f"{HISTORICAL_FILE} is not a historical reconstruction record")
    return HistoricalRecord(raw)
