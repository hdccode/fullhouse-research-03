"""Experiment matrix -> concrete cells (no hand-written per-cell YAML).

``configs/fhr3b/matrix.yaml`` names experiments, modes, fields, presets and
profiles; this module resolves them into ``Cell`` objects.

Profiles
--------
``publication``  the FHR3B research baseline ``fhr3b_baseline`` (initial horizon R0=40,
                 H0=400, K=6; predeclared research design choices, not 2026 settings) in the
                 ``lab60_top6`` environment (N=60), frozen fields in
                 configs/fhr3b/fields/<mode>/.
``pilot``        same protocol, ``provisional60`` fields, namespace ``pilot``
                 (runtime + Monte Carlo calibration only).
``smoke``        tiny protocol (configs/fhr3b/protocols/smoke.yaml), 12-bot fields,
                 namespace ``smoke``; selected smoke fields are written under the
                 results root, never into configs. Correctness only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from fhr3.tournament.calibration import CalibrationSpec
from fhr3.tournament.cells import Cell
from fhr3.tournament.fields import FHR3B_CONFIGS, FieldManifest, Mode, load_field, load_mode
from fhr3.tournament.protocol import (
    BudgetAllocation,
    TournamentProtocol,
    budget_allocations,
    duplicate_allocations,
    load_protocol,
    round_sweep,
)

RESEARCH_FIELDS = ("spread", "crowded_cutoff", "style_diverse")


class FieldNotFrozenError(RuntimeError):
    pass


PAIRED_NOTE = {
    "round_sweep": "paired: checkpoint leaderboards are exact round prefixes of the same horizon tournaments",
    "budget_sweep": "paired by replicate index: shared tournament seeds, identical round-1 tables and a shared "
                    "hand-prefix of round-1 chance; tables diverge after round 1",
    "schedule_diagnostic": "paired by (source, replay): frozen and adaptive replay j share card/decision seeds and "
                           "round-1 tables; sources are independent",
    "baseline": "independent across fields and modes (different fields/games); shared seed family",
    "frozen_schedule": "paired by replicate: frozen replicate r replays the complete table schedule of baseline "
                       "tournament r with fresh cards/decisions (same round-1 tables); replicates are independent",
    "duplicate_play": "paired by replicate index: shared tournament seeds (round-1 tables); work is reported as "
                      "scheduled and actually played hands, never assumed equal",
    "swiss_reference": "separate namespace from every finite-budget cell",
}


def load_matrix(root: Path = FHR3B_CONFIGS) -> dict[str, Any]:
    return yaml.safe_load((root / "matrix.yaml").read_text())


def _lab_raw(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / load_matrix(root)["lab"]).read_text())


@dataclass(frozen=True)
class Profile:
    name: str
    base: TournamentProtocol
    lab_name: str
    field_size: int | None
    k: int
    seed_family: str
    namespaces: dict[str, str]
    fields: tuple[str, ...]
    fields_dir: Path
    selection: dict[str, Any]
    calibration: dict[str, Any]
    config_root: Path = FHR3B_CONFIGS
    round_checkpoints: tuple[int, ...] = ()

    @property
    def r0(self) -> int:
        return self.base.rounds

    @property
    def h0(self) -> int:
        return self.base.hands_per_match

    def protocol(self, mode: Mode, rounds: int | None = None, hands: int | None = None) -> TournamentProtocol:
        """The profile's protocol instantiated for a mode (natural table size and stack rule)."""
        return self.base.with_(
            table_size=mode.table_size, qualify_top_k=self.k, stack_policy=mode.stack_policy,
            rounds=rounds or self.r0, hands_per_match=hands or self.h0,
            notes=self.base.notes + (f"environment {self.lab_name}; controlled research design, not a competition format",),
        )

    # ------------------------------------------------------------ fields
    def field_path(self, mode: str, field: str) -> Path:
        dirs = [self.fields_dir / mode, self.config_root / "fields" / mode]
        names = (field,)
        for d in dirs:
            for n in names:
                if (d / f"{n}.json").exists():
                    return d / f"{n}.json"
        return dirs[0] / f"{names[0]}.json"

    def revoked_hashes(self) -> dict[str, str]:
        reg = self.config_root / "fields" / "FROZEN.yaml"
        if not reg.exists():
            return {}
        return dict(((yaml.safe_load(reg.read_text()).get("revoked") or {}).get("hashes") or {}))

    def frozen_hash(self, mode: str, field: str) -> str | None:
        reg = self.config_root / "fields" / "FROZEN.yaml"
        if not reg.exists():
            return None
        return (yaml.safe_load(reg.read_text()).get("fields") or {}).get(mode, {}).get(field)

    def field(self, mode: str, field: str) -> FieldManifest:
        p = self.field_path(mode, field)
        if not p.exists():
            raise FileNotFoundError(f"field {field!r} for {mode} is not frozen yet ({p}); run `fhr3b pools` "
                                    "(pool/smoke/provisional) or `fhr3b calibrate` + `fhr3b select-fields`")
        fm = load_field(p)
        if fm.mode != mode:
            raise ValueError(f"{p}: field is for mode {fm.mode}")
        if self.field_size is not None and fm.kind not in ("pool",) and fm.n != self.field_size:
            raise ValueError(f"{self.name} profile expects N={self.field_size}; {fm.field_id} has {fm.n}")
        if self.name in ("publication", "pilot") and fm.field_hash in self.revoked_hashes():
            raise FieldNotFrozenError(f"{p}: field_hash {fm.field_hash} is REVOKED "
                                      f"({self.revoked_hashes()[fm.field_hash]}); see FROZEN.yaml")
        if self.name in ("publication", "pilot") and field in RESEARCH_FIELDS:
            want = self.frozen_hash(mode, field)
            if want is None:
                raise FieldNotFrozenError(f"{mode}/{field} is a candidate, not frozen: review it and add its hash "
                                          "to configs/fhr3b/fields/FROZEN.yaml")
            if want != fm.field_hash:
                raise FieldNotFrozenError(f"{p}: field_hash {fm.field_hash} != frozen {want}")
        return fm

    # ------------------------------------------------------------ cells
    def cell(self, mode: str, field: str, experiment: str = "baseline", rounds: int | None = None,
             hands: int | None = None) -> Cell:
        m = load_mode(mode, self.config_root)
        return Cell("adaptive", m, self.protocol(m, rounds, hands), self.field(mode, field), self.seed_family,
                    self.namespaces[experiment])

    def rounds_sweep(self) -> list[int]:
        """Initial-horizon checkpoints derived from R0 (5/10/20/30/40 for R0 = 40)."""
        return round_sweep(self.r0)

    def checkpoints_for(self, horizon: int) -> list[int]:
        """Prefix checkpoints read from a tournament cell with ``horizon`` rounds.

        R0 is an initial horizon, not a sufficient length: longer horizons add the configured
        extension checkpoints (60 / 80 / 120) up to the cell's own length.
        """
        base = [r for r in self.rounds_sweep() if r <= horizon]
        ext = [r for r in self.round_checkpoints if self.r0 < r <= horizon]
        return sorted(set(base + ext + [horizon]))

    def allocations(self) -> list[BudgetAllocation]:
        return budget_allocations(self.r0, self.h0)

    def budget_cells(self, mode: str, field: str) -> list[tuple[BudgetAllocation, Cell]]:
        return [(a, self.cell(mode, field, "budget_sweep", a.rounds, a.hands_per_match)) for a in self.allocations()]

    def schedule_cells(self, mode: str, field: str, j: int | None = None) -> tuple[Cell, Cell, Cell, int]:
        """(source, frozen replay, adaptive replay, J). The source is the baseline cell (same namespace)."""
        j = int(j if j is not None else self.selection.get("replays_per_source", 4))
        src = self.cell(mode, field, "schedule_diagnostic")
        frozen = Cell("frozen_replay", src.mode, src.protocol, src.field, src.seed_family, src.namespace, src, j)
        adapt = Cell("adaptive_replay", src.mode, src.protocol, src.field, src.seed_family, src.namespace, src, j)
        return src, frozen, adapt, j

    def swiss_reference_cell(self, mode: str, field: str) -> Cell:
        return self.cell(mode, field, "swiss_reference")

    def calibration_spec(self, mode: str, stage: str, field: str | None = None) -> CalibrationSpec:
        m = load_mode(mode, self.config_root)
        if stage == "pool":
            fm = load_field(self.field_path(mode, self.calibration["pool_field"]))
            if self.name in ("publication", "pilot") and fm.field_hash in self.revoked_hashes():
                raise FieldNotFrozenError(f"{mode} pool {fm.field_hash} is REVOKED; see FROZEN.yaml")
            c, ns = self.calibration["pool"], self.namespaces["pool_calibration"]
        elif stage == "field":
            if field is None:
                raise ValueError("field-reference calibration needs a field")
            fm = self.field(mode, field)
            c, ns = self.calibration["field_reference"], self.namespaces["field_reference"]
        else:
            raise ValueError("stage must be 'pool' or 'field'")
        return CalibrationSpec(m, fm, self.h0, m.stack_policy, self.seed_family, ns, int(c["chunk_rounds"]),
                               match_format=str(c.get("match_format", "ordinary")))

    def calibration_rounds(self, stage: str, mode: str | None = None) -> int:
        """Configured rounds. ``matched_rounds`` is taken as is; an ordinary-equivalent ``rounds`` for a
        duplicate calibration is divided by the lane count (equal scheduled work).

        The publication field reference has NO default: the FHR #4 core scopes its own budget
        (``core_fhr4.field_reference``, see core.core_field_rounds) and every other caller must pass
        the matched rounds explicitly.
        """
        c = self.calibration["pool" if stage == "pool" else "field_reference"]
        if "matched_rounds" in c:
            return int(c["matched_rounds"])
        if "rounds" not in c:
            raise ValueError(f"{self.name}: no default {stage} calibration rounds; pass the matched rounds "
                             "explicitly (--rounds) or use the scoped `fhr3b core field-reference`")
        rounds = int(c["rounds"])
        if c.get("match_format", "ordinary") == "duplicate" and mode is not None:
            rounds = max(1, rounds // load_mode(mode, self.config_root).table_size)
        return rounds

    def duplicate_cells(self, mode: str, field: str) -> list[tuple[str, Cell]]:
        """Experiment D: ordinary (R0, H0) vs duplicate packages at ~equal scheduled work (paired seeds).

        Each package also changes the rounds or the match length: an operational comparison, not the
        isolated effect of duplication."""
        m = load_mode(mode, self.config_root)
        out = [("ordinary", self.cell(mode, field, "duplicate_play"))]
        for a in duplicate_allocations(self.r0, self.h0, m.table_size):
            proto = self.protocol(m, a.rounds, a.hands_per_lane).with_(match_format="duplicate")
            out.append((f"{a.label} R{a.rounds}xH{a.hands_per_lane}x{a.lanes}lanes"
                        f"{'' if a.exact else ' (approx. equal scheduled work)'}",
                        Cell("adaptive", m, proto, self.field(mode, field), self.seed_family,
                             self.namespaces["duplicate_play"])))
        return out


def load_profile(name: str = "publication", results_root: Path | None = None,
                 config_root: Path = FHR3B_CONFIGS) -> Profile:
    mx = load_matrix(config_root)
    lab = _lab_raw(config_root)
    base = load_protocol(config_root / lab["protocol"])
    if base.status != "research":
        raise ValueError(f"{lab['protocol']}: the controlled environment needs a research protocol")
    sel = dict(mx["calibration"]["selection"]) | {
        "replays_per_source": mx["experiments"]["schedule_diagnostic"]["replays_per_source"]}
    cal = {"pool": mx["calibration"]["pool"], "field_reference": mx["calibration"]["field_reference"],
           "pool_field": "pool"}
    pub_ns = {"baseline": "publication", "round_sweep": "publication", "budget_sweep": "publication",
              "schedule_diagnostic": "publication", "frozen_schedule": "publication", "duplicate_play": "publication",
              "swiss_reference": "swiss-reference",
              "pool_calibration": "pool-calibration", "field_reference": "field-reference"}
    fields_dir = config_root / "fields"
    if name == "publication":
        return Profile(name, base, lab["name"], int(lab["field_size"]), base.qualify_top_k,
                       lab["seed_family"], pub_ns, tuple(mx["experiments"]["baseline"]["fields"]), fields_dir,
                       sel, cal, config_root, tuple(mx.get("round_checkpoints", ())))
    if name == "pilot":
        ns = {k: "pilot" for k in pub_ns}
        return Profile(name, base, lab["name"], int(lab["field_size"]), base.qualify_top_k,
                       lab["seed_family"], ns, tuple(mx["experiments"]["pilot"]["fields"]), fields_dir,
                       sel, cal, config_root, tuple(mx.get("round_checkpoints", ())))
    if name == "smoke":
        sm = mx["smoke_profile"]
        proto = load_protocol(config_root / mx["experiments"]["smoke"]["protocol"])
        ns = {k: "smoke" for k in pub_ns} | {"swiss_reference": "test", "field_reference": "test"}
        sdir = Path(results_root or ".") / "smoke-fields"
        return Profile(name, proto, "smoke", None, proto.qualify_top_k, lab["seed_family"], ns,
                       tuple(sm["fields"]), sdir, dict(sm["selection"]), dict(sm["calibration"]), config_root)
    raise ValueError(f"unknown profile {name!r}")


def preset_replicates(preset: str, config_root: Path = FHR3B_CONFIGS) -> int:
    return int(load_matrix(config_root)["presets"][preset])
