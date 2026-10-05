"""FHR4 research dossier: reproducible from stored outputs, consistent with the analysis, wording rules held."""

from __future__ import annotations

import csv
import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
A = REPO / "reports/fhr3b/analysis-fhr4-core"
P = REPO / "paper/fhr4"
DOS = P / "dossier"
FIELDS = ("separated_control", "crowded_cutoff", "style_diverse")
pytestmark = pytest.mark.skipif(not (A / "exports/tournament_errors.csv").exists(), reason="analysis outputs not present")

FORBIDDEN = ("true skill", "swiss is unreliable in general", "40 rounds are insufficient in general",
             "compute was held fixed", "adaptive swiss causally improves selection",
             "duplication causally reduces variance", "the separated control is representative")
REQUIRED_TERMS = ("mu_field reference", "mu_swiss reference", "in these controlled fields",
                  "within the preregistered 40-round horizon", "equal scheduled hand budget",
                  "source-schedule counterfactual", "operational package comparison", "engineered separated control")
CLASSES = {"bug fix", "protocol clarification", "descriptive analysis", "genuinely pre-registered decision",
           "post-hoc design decision"}


def rows(p: Path) -> list[dict]:
    return list(csv.DictReader(p.open()))


@pytest.fixture(scope="module")
def gen(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("fhr4_dossier", REPO / "scripts/fhr4_dossier.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = tmp_path_factory.mktemp("dossier")
    return out, mod.main(out)


def test_committed_dossier_is_reproducible(gen):
    out, _ = gen
    for rel in ("RESEARCH_DOSSIER.md", "data/results_sheet.csv", "data/claims_ledger.csv",
                "data/provenance_timeline.csv", "tables/table4_final_references.csv",
                "tables/tableA1_per_bot_qualification.csv"):
        assert (out / rel).read_text() == (DOS / rel).read_text(), rel
    m = json.loads((DOS / "MANIFEST.json").read_text())
    assert m["simulation_run"] is False and m["engine_source_hash"] == "4647ee69857e7c9b"
    assert all(Path(REPO / k).exists() for k in m["inputs"])


def test_generator_is_read_only():
    src = (REPO / "scripts/fhr4_dossier.py").read_text()
    assert "import fhr3" not in src and "from fhr3" not in src and "subprocess" not in src


def test_results_sheet_matches_analysis(gen):
    _, g = gen
    sheet = {(r["section"], r["field"], r["condition"], r["metric"]): r for r in g["sheet"]}
    base = {r["field_id"].replace("nlhe6-", ""): r for r in rows(A / "baseline_reliability.csv")}
    for f in FIELDS:
        for m in ("changed_qualifiers", "topk_overlap", "spearman_rho", "mu_field_reference_changed",
                  "mu_field_qualification_regret", "mu_field_boundary_strength_loss"):
            r = sheet[("baseline", f, "R40H400 adaptive", m)]
            assert r["value"] == pytest.approx(float(base[f][m + "_value"]), rel=1e-6)
            assert r["ci_lo"] == pytest.approx(float(base[f][m + "_ci_lo"]), rel=1e-6)
            assert r["ci_hi"] == pytest.approx(float(base[f][m + "_ci_hi"]), rel=1e-6)
    sections = {r["section"] for r in g["sheet"]}
    assert {"baseline", "A_rounds", "B_levels", "B_contrasts", "B_matched_played", "B_work", "C_frozen", "C_contrast",
            "D_levels", "D_contrasts", "D_work", "mu_swiss", "mu_swiss_p_qualify"} <= sections
    for r in g["sheet"]:
        if r["ci_lo"] is not None:
            assert r["ci_lo"] <= r["value"] + 1e-9 <= r["ci_hi"] + 2e-9, r


def test_remaining_figure_data_match_analysis():
    lab = {"R10 x H1600": "quarter_rounds_4x_hands", "R20 x H800": "half_rounds_2x_hands", "R40 x H400": "baseline"}
    bud = {(r["field_id"].replace("nlhe6-", ""), r["allocation"]): r for r in rows(A / "budget_allocation.csv")}
    for d in rows(P / "figures/data/fig2_allocation_equal_scheduled_budget.csv"):
        if d["panel"] in ("a", "b"):
            r = bud[(d["field"], lab[d["allocation"]])]
            assert float(d["value"]) == pytest.approx(float(r[d["metric"] + "_value"]), rel=1e-5)
            assert float(d["hands_played_ratio_vs_R40"]) == pytest.approx(float(r["hands_played_ratio_vs_40x400"]), rel=1e-5)
    dup = {(r["field_id"].replace("nlhe6-", ""), r["variant"].split()[0]): r for r in rows(A / "duplicate_play.csv")}
    for d in rows(P / "figures/data/fig4_duplicate_packages.csv"):
        if d["panel"] in ("a", "b"):
            r = dup[(d["field"], d["package"])]
            assert float(d["value"]) == pytest.approx(float(r[d["metric"] + "_value"]), rel=1e-5)
            assert float(d["ci_hi"]) == pytest.approx(float(r[d["metric"] + "_ci_hi"]), rel=1e-5)
    ex = [r for r in rows(A / "exports/tournament_errors.csv") if r["cell"] in ("baseline", "mu_swiss")]
    for d in rows(P / "figures/data/figS1_identity_vs_strength_error.csv"):
        if d["panel"] == "d":
            x = [r for r in ex if r["field"] == d["field"]]
            wrong = sum(int(r["wrong_vs_mu_field"]) for r in x)
            clear = sum(int(r["wrong_clearly_outside"]) for r in x)
            assert float(d["share_clearly_outside"]) == pytest.approx(clear / wrong)


def test_publication_tables_reproduced_unchanged():
    text = (DOS / "RESEARCH_DOSSIER.md").read_text()
    for name in ("table1_design.csv", "table2_baseline_reliability.csv", "table3_primary_contrasts.csv"):
        for r in rows(P / "tables" / name):
            assert "| " + " | ".join(r.values()) + " |" in text, (name, r)


def test_derived_checks(gen):
    _, g = gen
    x = g["derived"]
    assert x["separated_control"]["exact_reference_top6_selected"] == 2
    assert x["separated_control"]["tournaments_pooled"] == 250
    assert x["separated_control"]["share_wrong_clearly_outside"] == 1.0
    for f in FIELDS:
        assert 0.75 <= x[f]["share_wrong_clearly_outside"] <= 1.0


def test_structure_ledger_timeline_limitations(gen):
    _, g = gen
    assert len(g["cards"]) == 7
    for c in g["cards"]:
        assert {"support", "uncertainty", "fields", "identity_vs_strength", "consistency", "defensible",
                "overclaim"} <= set(c)
    tiers = {r["tier"] for r in g["ledger"]}
    assert tiers == {"strong", "qualified", "avoid"}
    assert {r["classification"] for r in g["timeline"]} <= CLASSES
    dates = [r["date"] for r in g["timeline"]]
    assert dates == sorted(dates)
    lim = [r["limitation"] for r in g["limitations"]]
    assert len(lim) == 10 and lim[0] == "One field per scenario"
    assert len(g["tableA1"]) == 180 and len(g["table4"]) == 3
    text = (DOS / "RESEARCH_DOSSIER.md").read_text()
    for head in ("Executive research summary", "Methods summary", "Results summary", "Figure and table index",
                 "Claims ledger", "Provenance timeline"):
        assert f"### 10." in text and head in text
    assert text.index("### 10.1 Executive") < text.index("### 10.5 Claims ledger") < text.index("### 10.6 Provenance")


def _strings(obj, allowed: bool = False):
    """Strings that are NOT inside an explicitly marked avoid context (an avoid-tier record or an overclaim field)."""
    if isinstance(obj, dict):
        allowed = allowed or obj.get("tier") == "avoid"
        for k, v in obj.items():
            yield from _strings(v, allowed or k == "overclaim")
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v, allowed)
    elif isinstance(obj, str) and not allowed:
        yield obj


def test_wording_rules():
    for p in [DOS / "RESEARCH_DOSSIER.md", *sorted((DOS / "data").glob("*")), *sorted((DOS / "tables").glob("*"))]:
        text = p.read_text()
        assert "—" not in text, f"em dash in {p}"
        assert not re.search(r"(?<![\d.])2027(?![\d.])", text), p
        if p.suffix == ".json":
            for s in _strings(json.loads(text)):
                assert not any(ph in s.lower() for ph in FORBIDDEN), (p.name, s[:120])
            continue
        for line in text.splitlines():
            low = line.lower()
            for phrase in FORBIDDEN:
                if phrase in low:
                    assert "avoid" in low, (p.name, phrase, line[:120])
    text = (DOS / "RESEARCH_DOSSIER.md").read_text()
    low = text.lower()
    for term in REQUIRED_TERMS:
        assert term in low, term
    assert not re.search(r"^#+ .*(title|abstract|introduction)", text, flags=re.I | re.M)


def test_self_regret_reporting_is_coherent(gen):
    _, g = gen
    base = {r["field_id"].replace("nlhe6-", ""): r for r in rows(A / "baseline_reliability.csv")}
    sr = {(r["field"], r["reference"]): r for r in rows(A / "exports/reference_self_regret.csv")}
    assert len(sr) == 6
    for (f, ref), r in sr.items():
        assert float(r["ci_lo_bb"]) <= float(r["median_bb"]) <= float(r["ci_hi_bb"])
        assert float(r["mean_bb"]) == pytest.approx(float(base[f][f"{ref}_reference_self_regret_value"]), rel=1e-4, abs=1e-6)
    metrics = {r["metric"] for r in g["sheet"]}
    assert "mu_field_reference_self_regret" not in metrics  # the mean is never paired with the percentile interval
    for r in g["sheet"]:
        if r["metric"].endswith("self_regret_mean"):
            assert r["ci_lo"] is None and r["ci_hi"] is None
    assert sr[("separated_control", "mu_field")]["median_bb"] in ("0.0", "0")


def test_transparency_items_preserved():
    text = (DOS / "RESEARCH_DOSSIER.md").read_text()
    tl = (DOS / "data/provenance_timeline.csv").read_text()
    lim = (DOS / "data/limitations.csv").read_text()
    assert "EXTEND_TO_100 for these 4 cells" in tl and "18/18 LOCK_AT_50" in tl
    assert "4 of 18 cells would have extended" in lim
    assert "broad reading would have extended 4 cells (sensitivity verdict reported)" in text
    assert "+0.0009, includes zero" in text
    assert "Descriptive approximation" in text and "not a preregistered analysis" in text
    assert "High-variance styles systematically over-qualify relative to their strength. | Archetype" in text
    assert "Short duplication significantly improves selection in every field." in text
    assert "No claim that high-variance styles systematically over-qualify." in text


def test_outline_has_no_title_options_and_keeps_scaffold():
    o = (P / "OUTLINE.md").read_text()
    assert "Title options" not in o and "Subtitle" not in o
    assert "## Results-grounded abstract scaffold" in o
    assert "writer-owned" in o
    assert "\u2014" not in o
