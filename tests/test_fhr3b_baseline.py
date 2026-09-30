"""FHR3B research baseline vs historical 2026 provenance: kept apart, neither blocks the other."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from fhr3.tournament.experiments import load_profile
from fhr3.tournament.fields import FHR3B_CONFIGS, load_mode
from fhr3.tournament.historical import HistoricalRecordIncomplete, load_historical
from fhr3.tournament.protocol import load_protocol

REPO = Path(__file__).resolve().parents[1]
PRIMARY = ("aof4", "nlhe4", "nlhe6")


def test_historical_qualifier_rounds_and_other_facts_remain_unknown():
    rec = load_historical(FHR3B_CONFIGS)
    assert rec.name == "historical_2026_reconstruction"
    assert rec.required["qualifier_rounds"] is None
    assert set(rec.missing()) == {"qualifier_rounds", "field_size", "qualifier_structure", "round_one_order",
                                  "remainder_handling", "standings_statistic", "production_swiss_code"}
    assert rec.raw["production_equivalence"] == "UNVERIFIED"
    assert rec.raw["source"]["commit"] == "a80b26957db5f5515d9273a15d1b73aadf8985db"
    assert (rec.raw["recovered"]["hands_per_match"], rec.raw["recovered"]["qualify_top_k"]) == (400, 64)
    assert "rounds" not in rec.raw["recovered"]


def test_historical_record_cannot_become_a_protocol_while_incomplete():
    with pytest.raises(HistoricalRecordIncomplete, match="BLOCKED"):
        load_historical(FHR3B_CONFIGS).to_protocol()


def test_research_baseline_parameters_are_frozen():
    prof = load_profile("publication")
    assert prof.base.name == "fhr3b_baseline" and prof.base.status == "research"
    assert (prof.r0, prof.h0, prof.k, prof.field_size, prof.lab_name) == (40, 400, 6, 60, "lab60_top6")
    assert prof.rounds_sweep() == [5, 10, 20, 30, 40]
    assert [(a.rounds, a.hands_per_match, a.budget) for a in prof.allocations()] == [
        (10, 1600, 16000), (20, 800, 16000), (40, 400, 16000)]
    assert all(a.exact for a in prof.allocations())
    for mode in PRIMARY:
        p = prof.protocol(load_mode(mode))
        assert (p.name, p.rounds, p.hands_per_match, p.qualify_top_k) == ("fhr3b_baseline", 40, 400, 6)
        assert p.initial_order == "seeded_shuffle" and p.scoring == "cumulative_chip_delta"
    assert prof.protocol(load_mode("nlhe6")).table_size == 6 and prof.protocol(load_mode("aof4")).table_size == 4


def test_historical_and_research_hashes_differ():
    rec = load_historical(FHR3B_CONFIGS)
    base = load_protocol(FHR3B_CONFIGS / "protocols/fhr3b_baseline.yaml")
    assert rec.record_hash != base.protocol_hash
    assert rec.name != base.name


def test_controlled_publication_experiments_are_not_blocked():
    """Every research cell builds from fhr3b_baseline without touching the historical record."""
    prof = load_profile("publication")
    for mode in PRIMARY:
        cell = prof.cell(mode, "provisional60")
        assert cell.protocol.name == "fhr3b_baseline" and cell.namespace == "publication"
        assert ".fhr3b_baseline.R40H400K6." in cell.cell_id
        assert [c.protocol.rounds for _, c in prof.budget_cells(mode, "provisional60")] == [10, 20, 40]
        src, frozen, adapt, j = prof.schedule_cells(mode, "provisional60")
        assert frozen.source is src and adapt.protocol == src.protocol
        assert prof.swiss_reference_cell(mode, "provisional60").namespace == "swiss-reference"
        assert prof.calibration_spec(mode, "pool").hands_per_match == 400


def test_operational_validation_stays_blocked():
    from fhr3.tournament.cli import main

    with pytest.raises(SystemExit) as e:
        main(["run", "--experiment", "operational-2026", "--replicates", "1"])
    msg = str(e.value)
    assert "BLOCKED" in msg and "qualifier_rounds" in msg and "not affected" in msg


# Text files that describe FHR3B. No line may present R0 = 40 as a 2026 fact.
SCANNED = [*sorted((REPO / "docs/fhr3b").glob("*.md")), REPO / "paper/FHR3B_SCOPE.md",
           *sorted((FHR3B_CONFIGS / "protocols").glob("*.yaml")), FHR3B_CONFIGS / "lab/lab60_top6.yaml",
           FHR3B_CONFIGS / "matrix.yaml", *sorted((REPO / "src/fhr3/tournament").glob("*.py")),
           REPO / "scripts/run_fhr3b.sh"]
FORBIDDEN = [r"reconstructed_2026", r"exact_2026", r"provisional\W+R0", r"R0\W+(is\W+)?provisional",
             r"2026 baseline", r"production baseline"]
NEGATIONS = ("not", "NOT", "UNKNOWN", "unknown", "never", "no ", "design choice", "research")


def test_no_file_presents_r40_as_historical():
    bad = []
    for f in SCANNED:
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if any(re.search(p, line, re.I) for p in FORBIDDEN):
                bad.append(f"{f.name}:{i}: {line.strip()}")
            mentions_40 = re.search(r"\b(R0?\s*=\s*40|40 (Swiss )?rounds|rounds: 40)\b", line)
            historical = re.search(r"2026|qualifier|historical|production", line, re.I)
            if mentions_40 and historical and not any(n in line for n in NEGATIONS):
                bad.append(f"{f.name}:{i}: {line.strip()}")
    assert not bad, "\n".join(bad)


def test_prefix_identity_remains_exact(tmp_path):
    from fhr3.tournament.batch import run_cell
    from fhr3.tournament.replay import verify_prefix

    prof = load_profile("smoke", tmp_path)
    cell = prof.cell("nlhe6", "smoke12")
    run_cell(cell, tmp_path, range(2), progress=False)
    for r in prof.rounds_sweep()[:-1]:
        verify_prefix(tmp_path, cell, r, [0, 1])
