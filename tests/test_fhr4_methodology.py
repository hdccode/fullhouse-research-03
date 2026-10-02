"""FHR #4 pre-registered analysis plan: bootstrap unit, qualification regret, reference uncertainty,
extension rules, wording and the field-diversity table. All cheap (no publication simulation)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pytest

from fhr3.tournament import metrics as mt
from fhr3.tournament.calibration import CalibrationSpec, run_calibration
from fhr3.tournament.diagnostics import reference_rank_diagnostics
from fhr3.tournament.experiments import load_matrix, load_profile
from fhr3.tournament.fields import FHR3B_CONFIGS, load_field, load_mode
from fhr3.tournament.reference import (
    estimate_field_reference,
    mu_field_extension_rule,
    mu_swiss_extension_rule,
    split_by_round,
    wilson_half_width_max,
)

REPO = Path(__file__).resolve().parents[1]
RULES = load_matrix()["core_fhr4"]["extension_rules"]


# ------------------------------------------------------------------ 1. bootstrap unit = one matched round
@pytest.fixture(scope="module")
def dup_calibration(tmp_path_factory):
    """6 matched rounds stored in chunks of 3 (storage unit != bootstrap unit)."""
    root = tmp_path_factory.mktemp("dupcal")
    six = load_mode("nlhe6")
    spec = CalibrationSpec(six, load_field(FHR3B_CONFIGS / "fields/nlhe6/smoke12.json"), 8, six.stack_policy,
                           "fam", "test", chunk_rounds=3, match_format="duplicate")
    run_calibration(spec, root, 6, progress=False)
    return root, spec


def test_one_round_is_the_bootstrap_unit(dup_calibration):
    from fhr3.tournament.calibration import load_calibration

    root, spec = dup_calibration
    chunks = load_calibration(root, spec)
    assert len(chunks) == 2
    rounds = split_by_round(chunks)
    assert [sorted(set(t.column("round").to_pylist())) for t in rounds] == [[r] for r in range(6)]
    res = estimate_field_reference(root, spec, k=2, n_boot=40, seed=7)
    assert res["bootstrap_units"] == 6 and res["rounds_groups"] == 6  # 6 rounds, not 2 chunks
    assert res["bootstrap_unit"].startswith("one complete matched round")


def test_all_bots_share_the_same_round_weights(dup_calibration):
    root, spec = dup_calibration
    res = estimate_field_reference(root, spec, k=2, n_boot=40, seed=7)
    bots = res["bots"]
    s = np.stack([g.s for g in res["groups"]])  # (rounds, bots) lane-summed deltas
    n = np.stack([g.n for g in res["groups"]])
    w = np.random.Generator(np.random.PCG64(7)).multinomial(6, np.full(6, 1 / 6), size=40).astype(float)
    expect = (w @ s) / (w @ n) / spec.lanes  # ONE weight vector over rounds, applied to every bot
    assert np.allclose(res["boot_mu"], expect)
    assert res["boot_mu"].shape == (40, len(bots))


def test_joint_round_resampling_preserves_zero_sum(dup_calibration):
    root, spec = dup_calibration
    res = estimate_field_reference(root, spec, k=2, n_boot=60, seed=3)
    n = np.stack([g.n for g in res["groups"]])
    assert (n == n[:, :1]).all()  # 12 bots, 2 six-max tables: every bot plays every round
    assert np.allclose(res["boot_mu"].sum(1), 0.0, atol=1e-6)  # zero-sum survives every resample
    assert abs(res["mu"].sum()) < 1e-6


def test_rank_diagnostics_come_from_the_joint_vector(dup_calibration):
    root, spec = dup_calibration
    res = estimate_field_reference(root, spec, k=2, n_boot=60, seed=3)
    want = reference_rank_diagnostics(res["mu"], res["boot_mu"], 2)
    assert res["diag"]["p_same_top_k_set"] == want["p_same_top_k_set"]
    assert res["diag"]["per_bot"]["p_top_k"] == want["per_bot"]["p_top_k"]
    assert res["se"] == pytest.approx(res["sd"] / np.sqrt(res["n_matches"]))  # analytic SE stays primary


def test_no_core_doc_describes_a_grouped_mu_field_bootstrap():
    for doc in ("docs/fhr3b/FHR4_CORE.md", "paper/FHR3B_SCOPE.md", "docs/fhr3b/FIELD_REFERENCE_PLAN.md"):
        text = " ".join((REPO / doc).read_text().split())
        assert "one complete matched round" in text, doc
        assert not re.search(r"10-round (grouped|group) (joint )?bootstrap", text), doc


# ------------------------------------------------------------------ 2. qualification regret
def test_equal_strength_swap_has_zero_regret():
    ref = np.array([5.0, 4.0, 3.0, 3.0, 1.0])
    q = np.array([[1, 1, 1, 0, 0], [1, 1, 0, 1, 0]], bool)  # bots 2 and 3 are exactly equal
    assert mt.qualification_regret(q, ref, 3) == pytest.approx([0, 0])
    assert mt.boundary_strength_loss(q, ref) == pytest.approx([0, 0])


def test_strong_weak_swap_has_positive_regret():
    ref = np.array([5.0, 4.0, 3.0, 2.9, -6.0])
    q = np.array([[1, 1, 0, 0, 1]], bool)  # strong bot 2 omitted, weak bot 4 selected
    assert mt.qualification_regret(q, ref, 3)[0] == pytest.approx(9.0)
    assert mt.boundary_strength_loss(q, ref)[0] == pytest.approx(3.0 - (-6.0))


def test_same_changed_count_different_regret():
    ref = np.array([10.0, 9.0, 8.0, 7.9, -5.0, -6.0])
    harmless = np.array([[1, 1, 0, 1, 0, 0]], bool)  # one changed qualifier: near-equal swap
    harmful = np.array([[1, 1, 0, 0, 1, 0]], bool)  # one changed qualifier: weak bot qualifies
    for q in (harmless, harmful):
        assert mt.reference_qualification(q, ref, 3, b=10)["reference_changed"].value == 1
    r_ok = mt.qualification_regret(harmless, ref, 3)[0]
    r_bad = mt.qualification_regret(harmful, ref, 3)[0]
    assert r_ok == pytest.approx(0.1) and r_bad == pytest.approx(13.0) and r_bad > 100 * r_ok


def test_reference_uncertainty_propagation():
    rng = np.random.default_rng(0)
    ref = np.array([10.0, 9.0, 5.0, 4.95, 0.0, -1.0])
    boot = ref + rng.normal(0, 0.5, (400, 6))  # bots 2/3 reorder; the rest is clear
    p_top = reference_rank_diagnostics(ref, boot, 3)["per_bot"]["p_top_k"]
    q = np.array([[1, 1, 0, 1, 0, 0]] * 4 + [[1, 1, 1, 0, 0, 0]] * 4, bool)
    est = mt.reference_qualification(q, ref, 3, b=400, boot_reference=boot, p_ref_top_k=p_top)
    # point-reference metric vs reference-propagated interval: same point value, wider interval
    assert est["qualification_regret_ref_propagated"].value == est["qualification_regret"].value
    width = lambda e: e.hi - e.lo  # noqa: E731
    assert width(est["qualification_regret_ref_propagated"]) > width(est["qualification_regret"])
    assert est["reference_self_regret"].value > 0  # the reference's own top 3 is not settled
    # swaps inside the reference-ambiguous set are not "clear" errors
    assert est["clear_misqualifications"].value == 0 and est["clear_omissions"].value == 0
    assert est["reference_changed"].value == 0.5


# ------------------------------------------------------------------ 10. pre-registered extension rules
def _diag(p_top, same=1.0, rev=0.0):
    return {"per_bot": {"p_top_k": list(p_top)}, "p_same_top_k_set": same, "p_cutoff_pair_order_reversed": rev}


def test_rules_are_preregistered_in_config():
    r = RULES
    assert r["mu_field"]["spread"] == {"p_same_top_k_set_below": 0.95, "p_rank6_rank7_reversal_above": 0.05}
    assert r["mu_field"]["crowded_cutoff"] == {"leader_p_top_k_below": 0.95, "outside_p_top_k_above": 0.10}
    assert r["mu_field"]["style_diverse"] == {"top_ranks": 4, "top_p_top_k_below": 0.90, "low_rank_from": 10,
                                              "low_p_top_k_above": 0.10}
    assert r["matrix"]["qualifier_half_width_above"] == 0.30 and r["matrix"]["contrast_inconclusive_span"] == 0.25
    assert r["mu_swiss"]["p_qualify_band"] == [0.10, 0.90] and r["mu_swiss"]["half_width_above"] == 0.08
    assert r["matrix"]["regret"] == "report_only"  # regret never independently triggers an extension


def test_spread_rule():
    bots = [f"b{i}" for i in range(10)]
    mu = np.arange(10, 0, -1.0)
    rule = RULES["mu_field"]
    assert not mu_field_extension_rule("spread", bots, mu, _diag([1] * 6 + [0] * 4, 0.97, 0.01), {}, rule)["extend"]
    assert mu_field_extension_rule("spread", bots, mu, _diag([1] * 10, 0.90, 0.01), {}, rule)["extend"]
    assert mu_field_extension_rule("spread", bots, mu, _diag([1] * 10, 0.99, 0.06), {}, rule)["extend"]


def test_crowded_rule_ignores_reordering_inside_the_crowd():
    leaders = ["L0", "L1", "L2"]
    crowd = [f"c{i}" for i in range(12)]
    rest = [f"r{i}" for i in range(5)]
    bots = leaders + crowd + rest
    mu = np.linspace(20, 0, len(bots))
    con = {"top_ids": leaders, "crowd_ids": crowd}
    rule = RULES["mu_field"]
    p = [0.99] * 3 + [0.25] * 12 + [0.0] * 5  # top-6 identity totally unstable inside the crowd
    assert not mu_field_extension_rule("crowded_cutoff", bots, mu, _diag(p, same=0.0, rev=0.5), con, rule)["extend"]
    p_leak = [0.99] * 3 + [0.25] * 12 + [0.2, 0, 0, 0, 0]  # uncertainty leaks outside the cluster
    assert mu_field_extension_rule("crowded_cutoff", bots, mu, _diag(p_leak), con, rule)["extend"]
    p_leader = [0.90, 0.99, 0.99] + [0.25] * 12 + [0.0] * 5
    assert mu_field_extension_rule("crowded_cutoff", bots, mu, _diag(p_leader), con, rule)["extend"]
    # "outside" = neither designed leaders nor designed crowd (manifest sets, not numeric ranks 4-15):
    # leaders with P(top-6) ~ 1 are never counted as outside
    out = mu_field_extension_rule("crowded_cutoff", bots, mu, _diag(p), con, rule)
    assert out["criteria"]["outside_leaders_and_crowd_above"]["n_outside"] == len(rest)
    assert not set(leaders) & set(out["criteria"]["outside_leaders_and_crowd_above"]["bots"])


def test_style_diverse_rule():
    bots = [f"b{i}" for i in range(12)]
    mu = np.arange(12, 0, -1.0)
    rule = RULES["mu_field"]
    ok = [0.99, 0.95, 0.95, 0.91, 0.6, 0.5, 0.5, 0.3, 0.2, 0.05, 0.02, 0.0]  # local boundary noise only
    assert not mu_field_extension_rule("style_diverse", bots, mu, _diag(ok), {}, rule)["extend"]
    top_weak = list(ok)
    top_weak[3] = 0.85
    assert mu_field_extension_rule("style_diverse", bots, mu, _diag(top_weak), {}, rule)["extend"]
    low_leak = list(ok)
    low_leak[10] = 0.15
    assert mu_field_extension_rule("style_diverse", bots, mu, _diag(low_leak), {}, rule)["extend"]


def _swiss_row(b, p, n):
    lo, hi = mt.wilson_interval(np.array([round(p * n)]), n)
    return {"bot_id": b, "p_qualify": p, "p_qualify_wilson_lo": float(lo[0]), "p_qualify_wilson_hi": float(hi[0])}


def test_mu_swiss_rule_is_operational_at_n100():
    rule = RULES["mu_swiss"]
    assert wilson_half_width_max(100) == pytest.approx(0.0962, abs=1e-4)
    assert wilson_half_width_max(100) > rule["half_width_above"] > wilson_half_width_max(200)
    # n = 100: fires for estimated P(qualify) in [0.22, 0.78], not near the band edges
    for p, fires in ((0.10, False), (0.15, False), (0.21, False), (0.22, True), (0.50, True), (0.78, True),
                     (0.79, False), (0.90, False)):
        out = mu_swiss_extension_rule([_swiss_row("a", p, 100)], 100, "spread", {}, rule)
        assert out["extend"] is fires, p
        assert out["rule_can_trigger_at_n"] is True
    out = mu_swiss_extension_rule([_swiss_row("a", 0.5, 100), _swiss_row("b", 1.0, 100)], 100, "spread", {}, rule)
    assert out["decision_relevant_boundary_bots"] == ["a"] and out["extend"]
    # no forced extension for probabilities already close to 0 or 1 (outside the band)
    assert not mu_swiss_extension_rule([_swiss_row("x", 0.05, 100)], 100, "spread", {}, rule)["extend"]
    # n = 200 (the approved ceiling): cannot fire again
    out200 = mu_swiss_extension_rule([_swiss_row("a", 0.5, 200)], 200, "spread", {}, rule)
    assert not out200["extend"] and out200["rule_can_trigger_at_n"] is False


def test_mu_swiss_rule_keeps_crowded_exclusion():
    rule = RULES["mu_swiss"]
    crowd = mu_swiss_extension_rule([_swiss_row("c", 0.5, 100), _swiss_row("o", 0.95, 100)], 100, "crowded_cutoff",
                                    {"crowd_ids": ["c"]}, rule)
    assert not crowd["extend"] and crowd["excluded_designed_crowd"] == ["c"]
    assert crowd["decision_relevant_boundary_bots"] == []
    other = mu_swiss_extension_rule([_swiss_row("c", 0.5, 100), _swiss_row("d", 0.5, 100)], 100, "crowded_cutoff",
                                    {"crowd_ids": ["c"]}, rule)
    assert other["extend"] and list(other["flagged"]) == ["d"]  # a non-crowd boundary bot still counts


def test_matrix_rule_flags_cells_not_everything():
    from fhr3.tournament.analysis import matrix_extension_flags

    def row(cid, field, hw, **extra):
        return {"cell_id": cid, "field_id": field, "changed_qualifiers_ci_lo": 1 - hw, "changed_qualifiers_ci_hi": 1 + hw,
                "topk_overlap_ci_lo": 5 - 0.1, "topk_overlap_ci_hi": 5 + 0.1} | extra

    base = [row("base_s", "spread", 0.1), row("base_c", "crowded", 0.1)]
    budget = [row("b20_s", "spread", 0.35, allocation="half_rounds_2x_hands"),
              row("b20_c", "crowded", 0.1, allocation="half_rounds_2x_hands")]
    contrasts = [{"experiment": "D", "field": "crowded", "baseline_cell": "base_c", "arm_cell": "dup_c",
                  "metric": "changed_qualifiers", "diff_ci_lo": -0.3, "diff_ci_hi": 0.4, "inconclusive_span": True}]
    out = matrix_extension_flags(base, budget, [], [], contrasts, RULES["matrix"])["cells"]
    assert {c for c, v in out.items() if v["extend"]} == {"b20_s", "base_c", "dup_c"}
    assert not out["base_s"]["extend"] and not out["b20_c"]["extend"]


# ------------------------------------------------------------------ 4-8. wording, estimands, limitation
CORE_DOCS = ("paper/FHR3B_SCOPE.md", "docs/fhr3b/FHR4_CORE.md", "docs/fhr3b/RUNBOOK.md", "docs/fhr3b/ARCHITECTURE.md",
             "configs/fhr3b/matrix.yaml", "src/fhr3/tournament/core.py", "src/fhr3/tournament/analysis.py")


def _text(path: str) -> str:
    lines = [re.sub(r"^\s*>\s?", "", ln) for ln in (REPO / path).read_text().splitlines()]  # drop blockquote marks
    return " ".join(" ".join(lines).split())


def test_no_compute_equality_or_truth_language():
    bad = re.compile(r"(fixed|equal) (simulator )?compute|true skill|ground[- ]truth|true ranking|true top[- ]?6"
                     r"|causal effect of (swiss|duplicat)", re.I)
    for doc in CORE_DOCS:
        hits = [m.group(0) for m in bad.finditer(_text(doc))
                if not re.search(r"(not|never|no|neither|nor)\W+(\w+\W+){0,4}" + re.escape(m.group(0)),
                                 _text(doc), re.I)]
        assert not hits, (doc, hits)


def test_experiment_wording():
    scope = _text("paper/FHR3B_SCOPE.md")
    assert "fixed scheduled hand budget" in scope.lower()
    assert "Given the same maximum scheduled poker budget, should simulation be allocated across more Swiss " \
           "opponents or longer matches?" in scope
    assert "exogenous replay of schedules generated by the adaptive process" in scope
    assert "targeted counterfactual comparison, not a complete causal decomposition" in scope
    assert "operational comparison between alternative equal-ish-budget evaluation packages" in scope
    assert "Does whole-match duplicate evaluation provide better qualifier reliability per simulator work under " \
           "practical budget-preserving redesigns?" in scope


def test_reference_estimands_and_limitation():
    scope = _text("paper/FHR3B_SCOPE.md")
    assert "long-run expected performance against random partitions of the controlled field under the " \
           "specified match semantics" in scope
    assert "long-run expected outcome under the specified adaptive Swiss mechanism" in scope
    assert "not independent normative fairness" in scope
    assert "one frozen field per constructed regime" in scope and "CONDITIONAL" in scope
    from fhr3.tournament.analysis import ANALYSIS_NOTES

    assert any("not independent replications of a field regime" in n for n in ANALYSIS_NOTES)
    assert "one frozen field per constructed regime" in _text("docs/fhr3b/FHR4_CORE.md")


# ------------------------------------------------------------------ 9. field-diversity table
def test_field_diversity_table(tmp_path):
    from fhr3.tournament.field_diversity import field_diversity

    prof = load_profile("publication")
    res = field_diversity(prof, "nlhe6", ["spread", "crowded_cutoff", "style_diverse"], REPO / "reports/fhr3b")
    f = res["fields"]
    for name in f:
        assert f[name]["n"] == 60 and f[name]["n_distinct_parameter_vectors"] == 60
        assert f[name]["n_archetypes"] >= 7 and len(f[name]["styles"]) == 4
    c = f["crowded_cutoff"]
    assert c["designed_crowd"]["same_as_ranks_4_15"]
    b = c["boundary_ranks_4_15"]
    assert b["near_duplicate_pairs"] == 3 and b["bots_in_near_duplicate_pairs"] == 4  # not clone-driven
    assert b["n_archetypes"] == 7 and len(b["styles"]) == 4
    assert f["spread"]["near_duplicate_pairs"] == 0 and f["style_diverse"]["near_duplicate_pairs"] == 0
    committed = json.loads((REPO / "reports/fhr3b/field-calibration/nlhe6/field_diversity.json").read_text())
    assert json.loads(json.dumps(res, sort_keys=True)) == committed  # committed table is reproducible
