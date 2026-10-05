"""FHR4 publication package: figures and tables reproduce the stored analysis exactly; wording rules."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
P = REPO / "paper/fhr4"
A = REPO / "reports/fhr3b/analysis-fhr4-core"
STEMS = ("fig1_reliability_vs_rounds", "fig2_allocation_equal_scheduled_budget", "fig3_adaptive_vs_frozen",
         "fig4_duplicate_packages", "fig5_qualification_probability_at_cutoff", "figS1_identity_vs_strength_error")
FIELDS = ("separated_control", "crowded_cutoff", "style_diverse")
pytestmark = pytest.mark.skipif(not (P / "figures/SHA256SUMS.json").exists(), reason="publication package not built")


def rows(p: Path) -> list[dict]:
    return list(csv.DictReader(p.open()))


def test_every_figure_has_vector_raster_data_and_checksum():
    sums = json.loads((P / "figures/SHA256SUMS.json").read_text())
    assert set(sums) == set(STEMS)
    for s in STEMS:
        for ext in ("pdf", "svg", "png"):
            f = P / "figures" / f"{s}.{ext}"
            assert hashlib.sha256(f.read_bytes()).hexdigest() == sums[s][ext], f
        assert (P / "figures/data" / f"{s}.csv").exists()
        assert f"## Figure {s[3]}" in (P / "figures/CAPTIONS.md").read_text() or s.startswith("figS1")


def test_figure_data_equal_the_stored_analysis():
    sweep = {(r["field_id"].replace("nlhe6-", ""), int(r["R_prefix"])): r for r in rows(A / "round_sweep.csv")}
    for d in rows(P / "figures/data/fig1_reliability_vs_rounds.csv"):
        r = sweep[(d["field"], int(d["rounds"]))]
        assert float(d["value"]) == pytest.approx(float(r[d["metric"] + "_value"]))
        assert float(d["ci_lo"]) == pytest.approx(float(r[d["metric"] + "_ci_lo"]))
    fz = {(r["field_id"].replace("nlhe6-", ""), r["metric"]): r for r in rows(A / "frozen_schedule.csv")}
    for d in rows(P / "figures/data/fig3_adaptive_vs_frozen.csv"):
        r = fz[(d["field"], d["metric"])]
        assert float(d["adaptive_minus_frozen"]) == pytest.approx(float(r["adaptive_minus_frozen_value"]))
        assert float(d["ci_hi"]) == pytest.approx(float(r["adaptive_minus_frozen_ci_hi"]))
    sw = {(r["field_id"].replace("nlhe6-", ""), r["bot_id"]): r for r in rows(A / "swiss_reference_bots.csv")}
    for d in rows(P / "figures/data/fig5_qualification_probability_at_cutoff.csv"):
        r = sw[(d["field"], d["bot_id"])]
        assert float(d["p_qualify_mu_swiss_200"]) == pytest.approx(float(r["p_qualify"]), abs=1e-4)
        assert int(r["n_tournaments"]) == 200


def test_tables_and_export_agree_with_the_analysis():
    base = {r["field_id"].replace("nlhe6-", ""): r for r in rows(A / "baseline_reliability.csv")}
    t2 = {r["Field"]: r for r in rows(P / "tables/table2_baseline_reliability.csv")}
    lab = {"separated_control": "Separated control", "crowded_cutoff": "Crowded cutoff", "style_diverse": "Style diverse"}
    ex = rows(A / "exports/tournament_errors.csv")
    assert len(ex) == 18 * 50 + 3 * 200
    for f in FIELDS:
        v = float(base[f]["mu_field_reference_changed_value"])
        assert t2[lab[f]]["Wrong vs mu_field"].startswith(f"{v:.2f}")
        b = [r for r in ex if r["field"] == f and r["cell"] == "baseline"]
        assert len(b) == 50
        assert sum(int(r["wrong_vs_mu_field"]) for r in b) / 50 == pytest.approx(v)
        assert sum(float(r["qualification_regret_bb"]) for r in b) / 50 == pytest.approx(
            float(base[f]["mu_field_qualification_regret_value"]), rel=1e-5)  # CSV stores 6 sig. figures


BANNED = ["true skill", "swiss is unreliable in general", "40 rounds are insufficient in general",
          "compute was held fixed", "adaptive swiss causally improves selection",
          "duplication causally reduces variance", "the separated control is representative"]


def test_manuscript_wording_discipline():
    for f in [*P.glob("*.md"), *(P / "figures").glob("*.md")]:
        text = f.read_text()
        assert "—" not in text, f"em dash in {f}"
        low = " ".join(text.lower().split())
        for b in BANNED:
            assert b not in low, (f, b)
        assert not re.search(r"\bcausal(ly)? (effect|improv)", low) or "not a clean causal" in low, f
