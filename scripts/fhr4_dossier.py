"""FHR4 research dossier (read-only; NO simulation; no figure or definition changes).

    .venv/bin/python scripts/fhr4_dossier.py

Every number in the dossier is read from the frozen analysis outputs (freeze commit db45b56,
publication package e222c9a). Nothing is typed in by hand except labels and verbal qualifiers.
Writes paper/fhr4/dossier/:

* RESEARCH_DOSSIER.md: the single structured dossier (not manuscript text).
* data/results_sheet.{csv,json}: canonical long-format results sheet (baseline, A, B, C, D, mu_swiss).
* data/claims_ledger.{csv,json}, data/provenance_timeline.{csv,json}, data/limitations.csv,
  data/figure_index.csv, data/table_index.csv, data/evidence_cards.json, data/field_profiles.json,
  data/reference_analysis.json, data/derived_checks.json.
* tables/table4_final_references.csv, tables/tableA1_per_bot_qualification.csv (full 180 rows).
* MANIFEST.json: SHA-256 of every input read and every output written.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics as st
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
A = REPO / "reports/fhr3b/analysis-fhr4-core"
FC = REPO / "reports/fhr3b/field-calibration/nlhe6"
PAPER = REPO / "paper/fhr4"
OUT = PAPER / "dossier"
FIELDS = ("separated_control", "crowded_cutoff", "style_diverse")
FL = {"separated_control": "Separated control", "crowded_cutoff": "Crowded cutoff", "style_diverse": "Style diverse"}
FREEZE, PACKAGE, ENGINE = "db45b56", "e222c9a", "4647ee69857e7c9b"
FIELD_HASH = {"separated_control": "0b30004f650324e5", "crowded_cutoff": "afbffedfc3706d84",
              "style_diverse": "ad7d6596ef1c8c3e"}
MINUS = "−"
INPUTS: set[Path] = set()

# ----------------------------------------------------------------------------------------------- io


def rows(p: Path) -> list[dict]:
    INPUTS.add(p)
    with p.open() as fh:
        return list(csv.DictReader(fh))


def jload(p: Path):
    INPUTS.add(p)
    return json.loads(p.read_text())


def fshort(fid: str) -> str:
    return fid.split("nlhe6-", 1)[-1] if fid.startswith("nlhe6-") else fid.split("/")[-1]


def num(x) -> float:
    return float(x)


def sgn(v: float, d: int) -> str:
    s = f"{v:.{d}f}"
    if s.startswith("-"):
        s = MINUS + s[1:]
    if s in (MINUS + f"{0:.{d}f}",):
        s = f"{0:.{d}f}"
    return s


def ci(v, lo, hi, d=2) -> str:
    return f"{sgn(v, d)} [{sgn(lo, d)}, {sgn(hi, d)}]"


def est(r: dict, m: str) -> tuple[float, float, float]:
    return num(r[m + "_value"]), num(r[m + "_ci_lo"]), num(r[m + "_ci_hi"])


def cif(r: dict, m: str, d=2) -> str:
    return ci(*est(r, m), d)


def selfreg(D, f: str, ref: str = "mu_field") -> tuple[float, float, float]:
    """reference_self_regret reported as bootstrap MEDIAN with the 2.5/97.5 percentile interval."""
    r = D["selfreg"][(f, ref)]
    return num(r["median_bb"]), num(r["ci_lo_bb"]), num(r["ci_hi_bb"])


def SR(D, f: str, ref: str = "mu_field") -> str:
    return ci(*selfreg(D, f, ref), 1)


def excludes_zero(lo: float, hi: float) -> bool:
    return lo > 0 or hi < 0


def write_csv(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for r in data:
        keys += [k for k in r if k not in keys]
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(data)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n")


def md_table(head: list[str], body: list[list], align: str | None = None) -> str:
    al = align or ("|" + "|".join("---" for _ in head) + "|")
    return "\n".join(["| " + " | ".join(head) + " |", al] + ["| " + " | ".join(str(c) for c in r) + " |" for r in body])


# --------------------------------------------------------------------------------------------- load

CELL_KEY = {"quarter_rounds_4x_hands": "R10H1600", "half_rounds_2x_hands": "R20H800", "baseline": "R40H400",
            "ordinary": "R40H400", "dup_fewer_rounds": "R7H400x6", "dup_shorter_matches": "R40H67x6",
            "frozen_schedule": "R40H400 frozen"}


def ckey(s: str) -> str:
    return s.split()[0] if s else s


def load() -> dict:
    D: dict = {}
    D["base"] = {fshort(r["field_id"]): r for r in rows(A / "baseline_reliability.csv")}
    D["sweep"] = {(fshort(r["field_id"]), int(r["R_prefix"])): r for r in rows(A / "round_sweep.csv")}
    D["budget"] = {(fshort(r["field_id"]), r["allocation"]): r for r in rows(A / "budget_allocation.csv")}
    D["dup"] = {(fshort(r["field_id"]), ckey(r["variant"])): r for r in rows(A / "duplicate_play.csv")}
    D["frozen"] = {(fshort(r["field_id"]), r["metric"]): r for r in rows(A / "frozen_schedule.csv")}
    D["contrasts"] = rows(A / "contrasts.csv")
    D["refacc"] = {(fshort(r["field_id"]), r["reference"]): r for r in rows(A / "reference_accuracy.csv")}
    D["fref"] = rows(A / "field_references.csv")
    D["sbots"] = rows(A / "swiss_reference_bots.csv")
    D["summary"] = jload(A / "summary.json")
    D["extra"] = jload(A / "audit_extra.json")
    D["integrity"] = jload(A / "audit_integrity.json")
    D["errors"] = rows(A / "exports/tournament_errors.csv")
    D["pq_all"] = rows(A / "exports/qualification_probabilities_all_cells.csv")
    D["selfreg"] = {(r["field"], r["reference"]): r for r in rows(A / "exports/reference_self_regret.csv")}
    D["refjson"] = {f: jload(FC / f"nlhe6-{f}/reference.json") for f in FIELDS}
    D["sc_val"] = jload(FC / "separated_control/validation.json")
    D["sc_con"] = jload(FC / "separated_control/construction.json")
    D["sv2_val"] = jload(FC / "spread_v2/validation.json")
    D["diversity"] = {r["field"]: r for r in rows(FC / "field_diversity.csv")} if (FC / "field_diversity.csv").exists() else {}
    sw = D["summary"]["sections"]["swiss_reference"]
    D["swiss"] = {fshort(v["field_id"]): v for v in sw.values()}
    D["refs"] = {fshort(k): v for k, v in D["summary"]["sections"]["references"].items()}
    D["ext"] = D["summary"]["extension_rules"]
    for name in ("table1_design.csv", "table2_baseline_reliability.csv", "table3_primary_contrasts.csv"):
        INPUTS.add(PAPER / "tables" / name)
    for p in sorted((PAPER / "figures/data").glob("*.csv")):
        INPUTS.add(p)
    return D


def contrast(D, exp: str, field: str, metric: str, arm: str, comparator: str) -> dict:
    hits = [r for r in D["contrasts"] if r["experiment"] == exp and r["field"] == field and r["metric"] == metric
            and ckey(r["arm"]) == arm and ckey(r["comparator"]) == comparator]
    assert len(hits) == 1, (exp, field, metric, arm, comparator, len(hits))
    return hits[0]


def cdiff(r: dict) -> tuple[float, float, float]:
    return num(r["diff_value"]), num(r["diff_ci_lo"]), num(r["diff_ci_hi"])


# ------------------------------------------------------------------------------------ results sheet

SHEET: list[dict] = []


def put(section, field, condition, metric, v, lo=None, hi=None, se=None, n=None, interval="", source="", note=""):
    SHEET.append({"section": section, "field": field, "condition": condition, "metric": metric,
                  "value": None if v is None else round(float(v), 6),
                  "ci_lo": None if lo is None else round(float(lo), 6),
                  "ci_hi": None if hi is None else round(float(hi), 6),
                  "se": None if se in (None, "") else round(float(se), 6),
                  "n": None if n in (None, "") else int(float(n)), "interval": interval, "source": source, "note": note})


BOOT = "95% tournament bootstrap"
SELF_NOTE = ("reported statistic: bootstrap median with 2.5/97.5 percentile interval over the reference's own "
             "1,000 joint resamples (independent of tournaments). The stored analysis value is the bootstrap mean "
             "(row *_mean), kept for traceability; it is not paired with the percentile interval.")
PAIRED = "95% paired bootstrap (shared replicate ids)"
BASE_METRICS = ["changed_qualifiers", "topk_overlap", "spearman_rho", "kendall_tau", "mean_abs_rank_diff",
                "n_ambiguous_bots", "p_same_winner", "mu_field_reference_changed", "mu_field_qualification_regret",
                "mu_field_boundary_strength_loss", "mu_field_reference_changed_ref_propagated",
                "mu_field_qualification_regret_ref_propagated", "mu_field_boundary_strength_loss_ref_propagated",
                "mu_field_clear_misqualifications", "mu_field_clear_omissions",
                "mu_swiss_reference_changed", "mu_swiss_qualification_regret", "mu_swiss_boundary_strength_loss",
                ]
LEVEL_METRICS = ["changed_qualifiers", "topk_overlap", "spearman_rho", "kendall_tau", "mu_field_reference_changed",
                 "mu_field_qualification_regret", "mu_field_boundary_strength_loss"]


def put_row(section, field, condition, r, metrics, source, interval=BOOT):
    for m in metrics:
        if r.get(m + "_value") in (None, ""):
            continue
        put(section, field, condition, m, *est(r, m), se=r.get(m + "_se"), n=r.get(m + "_n_tournaments"),
            interval=interval if "ref_propagated" not in m else "95% joint tournament + reference bootstrap",
            source=source)


def build_sheet(D) -> None:
    for f in FIELDS:
        put_row("baseline", f, "R40H400 adaptive", D["base"][f], BASE_METRICS, "baseline_reliability.csv")
        for ref in ("mu_field", "mu_swiss"):
            r = D["selfreg"][(f, ref)]
            put("baseline", f, "R40H400 adaptive", f"{ref}_reference_self_regret_median", *selfreg(D, f, ref),
                n=r["n_resamples"], interval="2.5/97.5 percentile of reference bootstrap",
                source="exports/reference_self_regret.csv", note=SELF_NOTE)
            put("baseline", f, "R40H400 adaptive", f"{ref}_reference_self_regret_mean", r["mean_bb"], n=r["n_resamples"],
                interval="none (point summary only)", source="baseline_reliability.csv; exports/reference_self_regret.csv",
                note=f"bootstrap mean as stored by the frozen analysis; share of resamples at zero {num(r['share_zero']):.3f}")
    for f in FIELDS:
        for R in (5, 10, 20, 30, 40):
            r = D["sweep"][(f, R)]
            put_row("A_rounds", f, f"prefix R{R}", r, LEVEL_METRICS, "round_sweep.csv")
    for f in FIELDS:
        for alloc in ("quarter_rounds_4x_hands", "half_rounds_2x_hands", "baseline"):
            r = D["budget"][(f, alloc)]
            c = CELL_KEY[alloc]
            put_row("B_levels", f, c, r, LEVEL_METRICS, "budget_allocation.csv")
            put("B_work", f, c, "scheduled_hand_budget_per_bot", r["scheduled_hand_budget_per_bot"], source="budget_allocation.csv")
            put("B_work", f, c, "hands_scheduled_per_tournament", r["hands_scheduled_per_tournament"], source="budget_allocation.csv")
            put("B_work", f, c, "hands_played_per_tournament", r["hands_played_per_tournament"], source="budget_allocation.csv")
            put("B_work", f, c, "played_fraction_of_scheduled",
                num(r["hands_played_per_tournament"]) / num(r["hands_scheduled_per_tournament"]), source="budget_allocation.csv")
            put("B_work", f, c, "hands_played_ratio_vs_R40H400", r["hands_played_ratio_vs_40x400"], source="budget_allocation.csv")
            put("B_work", f, c, "runtime_ratio_vs_R40H400", r["runtime_ratio_vs_40x400"], source="budget_allocation.csv",
                note="indicative only (machine throttling/sleep)")
        for arm, comp in (("quarter_rounds_4x_hands", "baseline"), ("half_rounds_2x_hands", "baseline"),
                          ("quarter_rounds_4x_hands", "half_rounds_2x_hands")):
            for m in ("changed_qualifiers", "topk_overlap", "mu_field_reference_changed", "mu_field_qualification_regret",
                      "mu_swiss_reference_changed"):
                r = contrast(D, "B", f, m, arm, comp)
                put("B_contrasts", f, f"{CELL_KEY[arm]} minus {CELL_KEY[comp]}", m, *cdiff(r), se=r["diff_se"],
                    n=r["n_common_replicates"], interval=PAIRED, source="contrasts.csv")
        for key, lab in (("budget_quarter_rounds_vs_R40prefix_matched_played", "R10H1600"),
                         ("budget_half_rounds_vs_R40prefix_matched_played", "R20H800")):
            x = D["extra"][f][key]
            cond = f"{lab} minus R40H400 prefix R{x['prefix_R']} (matched played hands)"
            put("B_matched_played", f, cond, "hands_played_arm", x["played"], source="audit_extra.json")
            put("B_matched_played", f, cond, "hands_played_prefix", x["prefix_played"], source="audit_extra.json")
            for k, m in (("chg", "changed_qualifiers"), ("refchg", "mu_field_reference_changed"),
                         ("regret", "mu_field_qualification_regret")):
                put("B_matched_played", f, cond, m, *x[k], interval=PAIRED, source="audit_extra.json",
                    note="descriptive post-hoc analysis (not pre-registered)")
    for f in FIELDS:
        for m in ("changed_qualifiers", "topk_overlap", "spearman_rho", "kendall_tau", "mean_abs_rank_diff",
                  "mu_field_reference_changed", "mu_field_qualification_regret", "mu_field_boundary_strength_loss",
                  "mu_swiss_reference_changed", "mu_swiss_qualification_regret"):
            r = D["frozen"][(f, m)]
            put("C_frozen", f, "adaptive R40H400", m, num(r["adaptive_value"]), num(r["adaptive_ci_lo"]),
                num(r["adaptive_ci_hi"]), n=r["adaptive_n_tournaments"], interval=BOOT, source="frozen_schedule.csv")
            put("C_frozen", f, "frozen replay R40H400", m, num(r["frozen_value"]), num(r["frozen_ci_lo"]),
                num(r["frozen_ci_hi"]), n=r["frozen_n_tournaments"], interval=BOOT, source="frozen_schedule.csv")
            put("C_contrast", f, "adaptive minus frozen", m, num(r["adaptive_minus_frozen_value"]),
                num(r["adaptive_minus_frozen_ci_lo"]), num(r["adaptive_minus_frozen_ci_hi"]),
                se=r["adaptive_minus_frozen_se"], n=r["n_sources"],
                interval="95% bootstrap paired by source tournament", source="frozen_schedule.csv")
    for f in FIELDS:
        for v in ("ordinary", "dup_fewer_rounds", "dup_shorter_matches"):
            r = D["dup"][(f, v)]
            c = CELL_KEY[v]
            put_row("D_levels", f, c, r, LEVEL_METRICS, "duplicate_play.csv")
            put("D_work", f, c, "scheduled_work_ratio_vs_ordinary", r["scheduled_work_ratio_vs_ordinary"], source="duplicate_play.csv")
            put("D_work", f, c, "played_hands_ratio_vs_ordinary", r["work_ratio_vs_ordinary"], source="duplicate_play.csv")
            put("D_work", f, c, "runtime_ratio_vs_ordinary", r["runtime_ratio_vs_ordinary"], source="duplicate_play.csv",
                note="indicative only (machine throttling/sleep)")
        for arm, comp in (("dup_shorter_matches", "ordinary"), ("dup_fewer_rounds", "ordinary"),
                          ("dup_shorter_matches", "dup_fewer_rounds")):
            for m in ("changed_qualifiers", "topk_overlap", "mu_field_reference_changed", "mu_field_qualification_regret",
                      "mu_swiss_reference_changed"):
                r = contrast(D, "D", f, m, arm, comp)
                put("D_contrasts", f, f"{CELL_KEY[arm]} minus {CELL_KEY[comp]}", m, *cdiff(r), se=r["diff_se"],
                    n=r["n_common_replicates"], interval=PAIRED, source="contrasts.csv")
    for f in FIELDS:
        s = D["swiss"][f]
        rs, se_ = s["rerun_stability"], s["strength_error_vs_mu_field"]
        for m in ("changed_qualifiers", "topk_overlap", "spearman_rho", "kendall_tau", "n_ambiguous_bots", "mean_abs_rank_diff"):
            put("mu_swiss", f, "mu_swiss reference (200 tournaments)", m, *est(rs, m), se=rs[m + "_se"],
                n=rs[m + "_n_tournaments"], interval=BOOT, source="summary.json:swiss_reference.rerun_stability")
        for m in ("mu_field_reference_changed", "mu_field_qualification_regret", "mu_field_boundary_strength_loss",
                  "mu_field_reference_changed_ref_propagated", "mu_field_qualification_regret_ref_propagated",
                  "mu_field_boundary_strength_loss_ref_propagated",
                  "mu_field_clear_misqualifications", "mu_field_clear_omissions"):
            put("mu_swiss", f, "mu_swiss reference (200 tournaments)", m, *est(se_, m), se=se_[m + "_se"],
                n=se_[m + "_n_tournaments"],
                interval="95% joint tournament + reference bootstrap" if "propagated" in m else BOOT,
                source="summary.json:swiss_reference.strength_error_vs_mu_field")
        rr = s["ranking_robustness"]
        put("mu_swiss", f, "mu_swiss reference (200 tournaments)", "p_same_top6_set", rr["p_same_top_k_set"],
            source="summary.json:swiss_reference.ranking_robustness", interval="bootstrap probability")
        put("mu_swiss", f, "mu_swiss reference (200 tournaments)", "p_cutoff_pair_order_reversed",
            rr["p_cutoff_pair_order_reversed"], source="summary.json:swiss_reference.ranking_robustness",
            interval="bootstrap probability")
        put("mu_swiss", f, "mu_swiss reference (200 tournaments)", "max_possible_wilson_half_width",
            s["extension_rule"]["max_possible_wilson_half_width_at_n"], source="summary.json:swiss_reference.extension_rule")
        for r in pq(D, f, "mu_swiss"):
            if int(r["mu_field_rank"]) <= 12 or num(r["p_qualify"]) >= 0.15:
                put("mu_swiss_p_qualify", f, r["bot_id"].replace("nlhe6-", ""), "p_qualify", r["p_qualify"],
                    r["wilson_lo"], r["wilson_hi"], n=r["n_tournaments"], interval="Wilson 95%",
                    source="exports/qualification_probabilities_all_cells.csv",
                    note=f"mu_field rank {r['mu_field_rank']}; P(reference top 6) {num(r['p_reference_top6']):.3f}")


def pq(D, f, cell) -> list[dict]:
    out = [r for r in D["pq_all"] if r["field"] == f and r["cell"] == cell]
    return sorted(out, key=lambda r: int(r["mu_field_rank"]))


# ------------------------------------------------------------------------------------ derived checks


def derived(D) -> dict:
    out: dict = {"note": "descriptive, computed in this dossier from stored outputs; not pre-registered"}
    for f in FIELDS:
        e = [r for r in D["errors"] if r["field"] == f and r["cell"] in ("baseline", "mu_swiss")]
        w = [int(r["wrong_vs_mu_field"]) for r in e]
        reg = [num(r["qualification_regret_bb"]) for r in e]
        amb = sum(int(r["wrong_in_reference_ambiguous_set"]) for r in e)
        clear = sum(int(r["wrong_clearly_outside"]) for r in e)
        sb = [r for r in D["sbots"] if fshort(r["field_id"]) == f]
        noise = st.median(num(r["mu_swiss_per_match_se_bb"]) * math.sqrt(int(r["n_tournaments"])) for r in sb)
        spread_swiss = st.pstdev([num(r["mu_swiss_per_match_bb"]) for r in sb])
        mu = [num(r["mu_field"]) / 100 for r in D["fref"] if r["field"] == f]
        fr = {r["bot_id"]: r for r in D["fref"] if r["field"] == f}
        disp = sorted(((abs(int(r["mu_field_rank"]) - int(r["mu_swiss_rank"])), r["bot_id"], int(r["mu_field_rank"]),
                        int(r["mu_swiss_rank"])) for r in fr.values() if int(r["mu_field_rank"]) <= 12), reverse=True)
        ref_top = {b for b, r in fr.items() if int(r["mu_field_rank"]) <= 6}
        sw_top = {b for b, r in fr.items() if int(r["mu_swiss_rank"]) <= 6}
        nb = [r for r in pq(D, f, "mu_swiss") if 7 <= int(r["mu_field_rank"]) <= 30]
        slope, icpt = st.linear_regression([num(r["mu_field_bb"]) for r in nb], [num(r["p_qualify"]) for r in nb])
        resid: dict = {}
        for r in nb:
            resid.setdefault(r["bot_id"].split("-")[1], []).append(num(r["p_qualify"]) - (icpt + slope * num(r["mu_field_bb"])))
        weakest_top = min(num(x["p_qualify"]) for x in pq(D, f, "mu_swiss") if int(x["mu_field_rank"]) <= 6)
        nonmono = [r for r in pq(D, f, "mu_swiss") if int(r["mu_field_rank"]) > 6 and num(r["p_qualify"]) > weakest_top]
        out[f] = {
            "p_qualify_residual_by_archetype_ranks_7_30": {k: {"mean": round(st.mean(v), 3), "n": len(v)} for k, v in sorted(resid.items())},
            "weakest_reference_top6_p_qualify": weakest_top,
            "non_top6_bots_qualifying_more_often_than_weakest_reference_top6": [
                {"bot": r["bot_id"].replace("nlhe6-", ""), "mu_field_rank": int(r["mu_field_rank"]), "p_qualify": num(r["p_qualify"])} for r in nonmono],
            "tournaments_pooled": len(e), "pooled_cells": ["baseline (50)", "mu_swiss (200)"],
            "exact_reference_top6_selected": sum(v == 0 for v in w),
            "wrong_qualifiers_total": sum(w), "wrong_in_reference_ambiguous_set": amb, "wrong_clearly_outside": clear,
            "share_wrong_clearly_outside": round(clear / sum(w), 4),
            "mean_regret_per_wrong_qualifier_bb": round(sum(reg) / sum(w), 2),
            "corr_wrong_count_vs_regret": round(st.correlation(w, reg), 4),
            "per_bot_tournament_sd_of_mean_per_match_score_bb_median": round(noise, 2),
            "sd_of_mu_swiss_per_match_across_bots_bb": round(spread_swiss, 2),
            "sd_of_mu_field_across_bots_bb": round(st.pstdev(mu), 2),
            "signal_share_within_swiss": round(spread_swiss ** 2 / (spread_swiss ** 2 + noise ** 2), 3),
            "point_top6_overlap_mu_field_vs_mu_swiss": len(ref_top & sw_top),
            "largest_rank_displacements_top12": [{"bot": b.replace("nlhe6-", ""), "mu_field_rank": a, "mu_swiss_rank": c,
                                                   "abs_diff": d} for d, b, a, c in disp[:3]],
        }
    return out


# ---------------------------------------------------------------------------------------- dossier


def V(D, X) -> dict:
    """Formatted values used in the dossier text (each key resolves to stored numbers)."""
    v: dict = {}
    b = D["base"]
    for f in FIELDS:
        r = b[f]
        v[f"{f}.chg"] = cif(r, "changed_qualifiers")
        v[f"{f}.ovl"] = cif(r, "topk_overlap")
        v[f"{f}.rho"] = cif(r, "spearman_rho")
        v[f"{f}.wrong"] = cif(r, "mu_field_reference_changed")
        v[f"{f}.regret"] = cif(r, "mu_field_qualification_regret", 1)
        v[f"{f}.loss"] = cif(r, "mu_field_boundary_strength_loss", 1)
        v[f"{f}.regret_prop"] = cif(r, "mu_field_qualification_regret_ref_propagated", 1)
        v[f"{f}.self"] = SR(D, f)
        v[f"{f}.clearmis"] = f"{num(r['mu_field_clear_misqualifications_value']):.2f}"
        v[f"{f}.clearom"] = f"{num(r['mu_field_clear_omissions_value']):.2f}"
    return v


def rng(vals: list[float], d=2) -> str:
    return f"{min(vals):.{d}f} to {max(vals):.{d}f}"


def build_md(D, X) -> tuple[str, dict]:
    b, sw, refs = D["base"], D["swiss"], D["refs"]
    L: list[str] = []
    add = L.append
    bv = lambda f, m: num(b[f][m + "_value"])  # noqa: E731
    chg_rng = rng([bv(f, "changed_qualifiers") for f in FIELDS])
    wrong_rng = rng([bv(f, "mu_field_reference_changed") for f in FIELDS])
    rho_rng = rng([bv(f, "spearman_rho") for f in FIELDS])
    sw_chg = {f: est(sw[f]["rerun_stability"], "changed_qualifiers") for f in FIELDS}
    sw_wrong = {f: est(sw[f]["strength_error_vs_mu_field"], "mu_field_reference_changed") for f in FIELDS}
    leaders = pq(D, "separated_control", "mu_swiss")[:6]
    lead_p = [num(r["p_qualify"]) for r in leaders]
    exact = X["separated_control"]["exact_reference_top6_selected"]
    n_pool = X["separated_control"]["tournaments_pooled"]
    gap = {f: D["refjson"][f]["gap_at_cutoff_bb"] for f in FIELDS}
    psame = {f: refs[f]["field_reference"]["uncertainty"]["p_same_top_k_set"] for f in FIELDS}
    prev = {f: refs[f]["field_reference"]["uncertainty"]["p_cutoff_pair_order_reversed"] for f in FIELDS}
    agree = {f: refs[f]["ordering_agreement"] for f in FIELDS}
    budget = D["budget"]
    pf = {(f, a): num(budget[(f, a)]["hands_played_per_tournament"]) / num(budget[(f, a)]["hands_scheduled_per_tournament"])
          for f in FIELDS for a in ("quarter_rounds_4x_hands", "half_rounds_2x_hands", "baseline")}
    pf_mean = {a: st.mean(pf[(f, a)] for f in FIELDS) for a in ("quarter_rounds_4x_hands", "half_rounds_2x_hands", "baseline")}

    def C(exp, f, m, arm, comp, d=2):
        return ci(*cdiff(contrast(D, exp, f, m, arm, comp)), d)

    def Craw(exp, f, m, arm, comp):
        return cdiff(contrast(D, exp, f, m, arm, comp))

    def FZ(f, m, d=2):
        r = D["frozen"][(f, m)]
        return ci(num(r["adaptive_minus_frozen_value"]), num(r["adaptive_minus_frozen_ci_lo"]),
                  num(r["adaptive_minus_frozen_ci_hi"]), d)

    def FZraw(f, m):
        r = D["frozen"][(f, m)]
        return num(r["adaptive_minus_frozen_value"]), num(r["adaptive_minus_frozen_ci_lo"]), num(r["adaptive_minus_frozen_ci_hi"])

    def MP(f, which, k, d=2):
        x = D["extra"][f][f"budget_{which}_rounds_vs_R40prefix_matched_played"][k]
        return ci(*x, d)

    def sweep_mono(f, m, decreasing=True):
        vals = [num(D["sweep"][(f, R)][m + "_value"]) for R in (5, 10, 20, 30, 40)]
        return all((a > c) if decreasing else (a < c) for a, c in zip(vals, vals[1:]))

    mono_all = all(sweep_mono(f, m, dec) for f in FIELDS for m, dec in (
        ("changed_qualifiers", True), ("mu_field_reference_changed", True), ("mu_field_qualification_regret", True),
        ("spearman_rho", False)))
    assert mono_all, "round-sweep monotonicity claim does not hold"
    last_step = {f: (num(D["sweep"][(f, 30)]["mu_field_qualification_regret_value"]),
                     num(D["sweep"][(f, 40)]["mu_field_qualification_regret_value"])) for f in FIELDS}

    # ---- header
    add("# FHR #4 research dossier (frozen evidence)")
    add("")
    add("**Status.** Analysis, verification and packaging only. This is not manuscript text: no title, abstract, "
        "introduction or results prose. Simulation frozen at `" + FREEZE + "`; publication package `" + PACKAGE +
        "`; engine source hash `" + ENGINE + "`. No simulation was run to produce this dossier, and no figure, "
        "field, threshold, reference or experimental definition was changed.")
    add("")
    add("**Generation.** `scripts/fhr4_dossier.py` reads every number from the stored outputs listed in "
        "`MANIFEST.json` (SHA-256 of each input). Machine-readable copies are in `data/` and `tables/`. "
        "`tests/test_fhr4_dossier.py` checks the numbers against the analysis outputs and the wording rules.")
    add("")
    add("**Reading conventions.**")
    add("")
    add("* NLHE 6-max, N = 60 bots per field, top K = 6 qualify, Swiss rounds of persistent-stack matches.")
    add("* Intervals are 95%: tournament bootstrap for levels; paired bootstrap on shared replicate ids for "
        "contrasts (paired by source tournament in C); Wilson for P(qualify); `ref_propagated` intervals add the "
        "joint mu_field reference bootstrap. `reference_self_regret` is reported as the bootstrap median with its "
        "2.5/97.5 percentile interval (see Section 6).")
    add("* Regret and boundary strength loss are in BB per ordinary-equivalent 400-hand match against the mu_field "
        "reference point estimate unless labelled mu_swiss.")
    add("* \"Rerun\" metrics compare independent tournaments of the same cell. \"Wrong vs mu_field\" counts selected "
        "bots outside the mu_field reference point top 6.")
    add("* Contrasts are first condition minus second. For error metrics, positive means the first is worse.")
    add("* Required terms: mu_field reference, mu_swiss reference, in these controlled fields, within the "
        "preregistered 40-round horizon, equal scheduled hand budget, source-schedule counterfactual, operational "
        "package comparison, engineered separated control.")
    add("")
    add("**Map to the request.** Sections 1 to 8 follow the requested order. Section 9 is the prioritised "
        "limitation set (request item 11). Section 10 is the closing pack: executive, methods and results "
        "summaries, figure/table index, claims ledger (request item 10) and provenance timeline (request item 9).")
    add("")
    add("## Contents")
    add("")
    for i, t in enumerate(["Research question and experimental plan", "Canonical results sheet", "Evidence cards",
                           "Results that need nuanced interpretation", "Field profiles", "Reference analysis",
                           "Figures", "Tables", "Remaining limitations (prioritised)",
                           "Closing pack: summaries, index, claims ledger, provenance timeline"], 1):
        add(f"{i}. {t}")
    add("")

    # ---- 1
    add("## 1. Research question and experimental plan")
    add("")
    add("### 1.1 Central research question")
    add("")
    add("How should a finite poker-bot simulation budget be allocated so that a Swiss tournament reliably "
        "identifies the strongest agents? Operationally: how often do independent runs of the same tournament, "
        "and the tournament against independent reference strengths, agree on the qualifying top 6 of 60, and how "
        "does that change with rounds, match length, adaptive pairing and duplicate play?")
    add("")
    add("### 1.2 Tournament setting")
    add("")
    add(md_table(["Item", "Value"], [
        ["Game", "No-limit hold'em, 6-max tables (NLHE6)"],
        ["Field size / qualifiers", "N = 60 synthetic bots; top K = 6 qualify"],
        ["Baseline format", "40 adaptive Swiss rounds (R0 = 40) of 400-hand persistent-stack matches (H0 = 400)"],
        ["Scoring", "raw chip delta per match, summed over rounds; public tiebreaks"],
        ["Semantics", "public-2026-style research semantics; research choices, not historical production settings"],
        ["Agents", "synthetic, stateless rule-based policy families (8 archetypes)"],
        ["Engine", f"source hash `{ENGINE}` for every stored tournament and reference"],
    ]))
    add("")
    add("### 1.3 Final controlled fields (one frozen field per scenario)")
    add("")
    body = []
    roles = {"separated_control": "Engineered separated control: six independently validated leaders, large rank-6/7 gap",
             "crowded_cutoff": "Qualification-boundary stress test: designed near-equal crowd at the cutoff",
             "style_diverse": "Strategically heterogeneous field: style x strength balanced, no near-duplicate bots"}
    for f in FIELDS:
        rj = D["refjson"][f]
        body.append([FL[f], f"`{FIELD_HASH[f]}`", roles[f], rj["matched_rounds"], f"{gap[f]:.2f}",
                     f"{psame[f]:.3f}", f"{prev[f]:.3f}"])
    add(md_table(["Field", "Hash", "Role", "mu_field matched rounds", "Rank-6/7 gap (BB)", "P(same top 6)",
                  "P(6/7 reversal)"], body))
    add("")
    add("Retired and not used: `spread` (`ff0f2b07fc210f62`, retired for selection bias) and the `spread_v2` "
        "candidate (failed held-out validation). See Section 10.6.")
    add("")
    add("### 1.4 Reference estimands")
    add("")
    add("* **mu_field reference.** Long-run expected performance against random partitions of the controlled field "
        "under the match semantics. Estimated by matched 6-lane whole-match duplicate play (cyclic seats, common "
        "chance streams, independent seed family), scaled to one ordinary 400-hand match. Primary SE analytic; "
        "uncertainty by joint bootstrap with one complete matched round as the unit.")
    add("* **mu_swiss reference.** Long-run expected outcome under the specified adaptive Swiss mechanism "
        "(40 x 400): mean final score over 200 complete tournaments per field in the `swiss-reference` namespace.")
    add("* Both are finite-sample estimates of mechanism-specific estimands. Neither is a context-free ranking; "
        "they can disagree in multiplayer, non-transitive games. Accuracy against mu_swiss measures convergence to "
        "the Swiss mechanism, not normative fairness.")
    add("")
    add("### 1.5 Experiments")
    add("")
    add(md_table(["Exp.", "Question", "Cells (per field, 50 tournaments each)", "Comparison", "Interpretation scope"], [
        ["Baseline", "How reliable is 40 x 400 selection?", "R40H400 adaptive", "rerun and vs references", "-"],
        ["A", "How does reliability change with rounds?", "exact prefixes R5/R10/R20/R30/R40 of the baseline (no extra simulation)",
         "level by prefix", "within the preregistered 40-round horizon"],
        ["B", "Rounds or match length?", "R10H1600, R20H800, R40H400", "paired contrasts",
         "equal scheduled hand budget (16,000 hands per bot); played hands differ"],
        ["C", "Does adaptive pairing matter?", "R40H400 frozen replay (J = 1) of each baseline schedule, fresh poker randomness",
         "adaptive minus frozen, paired by source", "source-schedule counterfactual"],
        ["D", "Do duplicate packages help?", "R7H400x6 and R40H67x6 six-lane whole-match duplicate",
         "paired contrasts vs ordinary R40H400", "operational package comparison"],
    ]))
    add("")
    add("### 1.6 Metrics")
    add("")
    add("* **Primary identity metric:** rerun changed qualifiers (expected qualifiers that differ between two "
        "independent tournaments; 6 minus top-6 overlap). Governs the matrix extension rule.")
    add("* **Primary reference metrics:** wrong qualifiers vs the mu_field reference point top 6; qualification "
        "regret (summed mu_field of the reference-optimal six minus that of the selected six).")
    add("* **Supporting:** top-6 overlap, Jaccard, rerun Spearman and Kendall, mean absolute rank difference, "
        "number of ambiguous bots (P(qualify) in [0.1, 0.9]), P(same winner), boundary strength loss, the same metrics "
        "against the mu_swiss reference, `*_ref_propagated` intervals, `reference_self_regret` (regret floor from "
        "reference uncertainty alone), clear misqualifications / clear omissions (ignoring swaps inside the "
        "reference-ambiguous set), per-bot P(qualify).")
    add("")
    add("### 1.7 Preregistered extension rules and outcomes")
    add("")
    mr = D["ext"]["matrix"]["rule"]
    n_cells = len(D["ext"]["matrix"]["cells"])
    n_ext = sum(c["extend"] for c in D["ext"]["matrix"]["cells"].values())
    n_broad = sum(c.get("extend_broad_sensitivity", False) for c in D["ext"]["matrix"]["cells"].values())
    whw = {f: sw[f]["extension_rule"]["max_possible_wilson_half_width_at_n"] for f in FIELDS}
    add(md_table(["Component", "Rule (preregistered)", "Outcome"], [
        ["mu_field, separated_control", "extend 250 to 500 if P(same top 6) < 0.95 or P(6/7 reversal) > 0.05",
         f"P(same) {psame['separated_control']:.3f}, P(rev) {prev['separated_control']:.3f}: locked at 250"],
        ["mu_field, crowded_cutoff", "extend if a designed leader has P(top 6) < 0.95, or a bot outside leaders and crowd has P(top 6) > 0.10; ceiling 500",
         "fired at 250; extended to 500; still fires at 500 (loose-e2-s1, 0.208); ceiling reached, carried as reference uncertainty"],
        ["mu_field, style_diverse", "extend if a point rank 1 to 4 bot has P(top 6) < 0.90, or a rank >= 10 bot has P(top 6) > 0.10; ceiling 500",
         "fired at 250 (rank 10, 0.106); extended to 500; does not fire at 500: locked"],
        ["Matrix (18 cells)", f"extend 50 to 100 if CI half-width of changed qualifiers or overlap > {mr['qualifier_half_width_above']}, or a pair-specific rerun changed-qualifier contrast CI spans +/-{mr['contrast_inconclusive_span']}; regret report-only",
         f"{n_cells - n_ext} / {n_cells} LOCK_AT_50. Under the broad reading (wrong-vs-reference contrasts also trigger), {n_broad} cells would have extended (sensitivity only; see 10.6)"],
        ["mu_swiss", "extend 100 to 200 if any decision-relevant bot with P(qualify) in [0.10, 0.90] has Wilson half-width > 0.08 (crowded designed crowd excluded); ceiling 200",
         f"fired in all three fields at 100 (half-widths 0.080 to 0.096); ran to 200; at 200 max possible half-width {whw['crowded_cutoff']:.3f} < 0.08, cannot fire"],
    ]))
    add("")
    add("### 1.8 Final simulation inventory")
    add("")
    integ = D["integrity"]
    sched_tot = sum(r["sched"] for r in integ)
    played_tot = sum(r["played"] for r in integ)
    inv = [["Matrix (6 cells x 3 fields)", f"{len(integ)} cells x 50 = {sum(r['verified'] for r in integ)} tournaments",
            f"{sched_tot / 1e6:.2f}M scheduled / {played_tot / 1e6:.2f}M played hands", "all digests verified; zero-sum; seating; exact replays"]]
    for f in FIELDS:
        rj = D["refjson"][f]
        inv.append([f"mu_field reference, {f}", f"{rj['matched_rounds']} matched rounds",
                    f"{rj['matched_rounds'] * 24000 / 1e6:.0f}M scheduled hands", f"`{rj['calib_id'].split('.')[-1]}`, {rj['lane_chunks_verified']} lane chunks verified"])
    inv.append(["mu_swiss reference", "3 fields x 200 tournaments", f"{3 * 200 * 160000 / 1e6:.0f}M scheduled hands", "200/200 digests per field; exact replays"])
    inv.append(["separated_control validation", f"{D['sc_val']['binding']['validation_rounds']:,} fresh pool-style rounds",
                "pool context (96-bot pool)", f"seed family `{D['sc_val']['binding']['validation_seed_family']}`, one shot"])
    add(md_table(["Component", "Units", "Work", "Integrity"], inv))
    add("")
    add("### 1.9 Deliberately not run")
    add("")
    add("* 60/80/120-round horizons (Experiment A horizon is 5 to 40 rounds; longer horizons are future work).")
    add("* Matrix 50 to 100 extensions (rule did not fire).")
    add("* mu_field beyond 250 (separated_control) or 500 (crowded_cutoff, style_diverse); mu_swiss beyond 200.")
    add("* Any second spread_v2 attempt; any re-selection of separated_control.")
    add("* Other table sizes, game modes or fields; any statement about future competition formats.")
    add("")

    # ---- 2
    add("## 2. Canonical results sheet")
    add("")
    add("Full long-format sheet: `data/results_sheet.csv` (and `.json`), one row per field x condition x metric with "
        "value, interval, SE, n and source file.")
    add("")
    add("### 2.1 Baseline R40H400 (50 tournaments per field)")
    add("")
    add(md_table(["Metric", *[FL[f] for f in FIELDS]], [
        ["Rerun changed qualifiers", *[v_(b[f], "changed_qualifiers") for f in FIELDS]],
        ["Rerun top-6 overlap", *[v_(b[f], "topk_overlap") for f in FIELDS]],
        ["Rerun Spearman", *[v_(b[f], "spearman_rho") for f in FIELDS]],
        ["Rerun Kendall", *[v_(b[f], "kendall_tau") for f in FIELDS]],
        ["Ambiguous bots (P(qualify) in [0.1, 0.9])", *[v_(b[f], "n_ambiguous_bots", 0) for f in FIELDS]],
        ["Wrong vs mu_field", *[v_(b[f], "mu_field_reference_changed") for f in FIELDS]],
        ["Wrong vs mu_swiss", *[v_(b[f], "mu_swiss_reference_changed") for f in FIELDS]],
        ["Clear misqualifications / clear omissions", *[f"{num(b[f]['mu_field_clear_misqualifications_value']):.2f} / {num(b[f]['mu_field_clear_omissions_value']):.2f}" for f in FIELDS]],
        ["Qualification regret (BB)", *[v_(b[f], "mu_field_qualification_regret", 1) for f in FIELDS]],
        ["  with reference uncertainty propagated", *[v_(b[f], "mu_field_qualification_regret_ref_propagated", 1) for f in FIELDS]],
        ["Reference self-regret (BB; bootstrap median [2.5, 97.5 percentile])", *[SR(D, f) for f in FIELDS]],
        ["Boundary strength loss (BB)", *[v_(b[f], "mu_field_boundary_strength_loss", 1) for f in FIELDS]],
    ]))
    add("")
    add("### 2.2 Experiment A: round prefixes")
    add("")
    for m, lab, d in (("mu_field_reference_changed", "Wrong vs mu_field", 2), ("mu_field_qualification_regret", "Qualification regret (BB)", 1),
                      ("spearman_rho", "Rerun Spearman", 2), ("changed_qualifiers", "Rerun changed qualifiers", 2)):
        add(f"**{lab}**")
        add("")
        add(md_table(["Field", *[f"R{R}" for R in (5, 10, 20, 30, 40)]],
                     [[FL[f], *[v_(D["sweep"][(f, R)], m, d) for R in (5, 10, 20, 30, 40)]] for f in FIELDS]))
        add("")
    add("Every metric improves at every step from 5 to 40 rounds in every field (checked by the generator).")
    add("")
    add("### 2.3 Experiment B: equal scheduled hand budget (16,000 hands per bot)")
    add("")
    add("**Levels**")
    add("")
    body = []
    for f in FIELDS:
        for a in ("quarter_rounds_4x_hands", "half_rounds_2x_hands", "baseline"):
            r = budget[(f, a)]
            body.append([FL[f], CELL_KEY[a], f"{num(r['hands_scheduled_per_tournament']):,.0f}",
                         f"{num(r['hands_played_per_tournament']):,.0f}", f"{pf[(f, a)]:.3f}",
                         v_(r, "changed_qualifiers"), v_(r, "spearman_rho"), v_(r, "mu_field_reference_changed"),
                         v_(r, "mu_field_qualification_regret", 1)])
    add(md_table(["Field", "Allocation", "Scheduled hands / tournament", "Played hands / tournament", "Played / scheduled",
                  "Rerun changed qualifiers", "Rerun Spearman", "Wrong vs mu_field", "Regret (BB)"], body))
    add("")
    add("**Paired contrasts (first minus second; positive = first worse)**")
    add("")
    body = []
    for arm, comp in (("quarter_rounds_4x_hands", "baseline"), ("half_rounds_2x_hands", "baseline"),
                      ("quarter_rounds_4x_hands", "half_rounds_2x_hands")):
        for f in FIELDS:
            body.append([f"{CELL_KEY[arm]} vs {CELL_KEY[comp]}", FL[f], C("B", f, "changed_qualifiers", arm, comp),
                         C("B", f, "mu_field_reference_changed", arm, comp),
                         C("B", f, "mu_field_qualification_regret", arm, comp, 1)])
    add(md_table(["Contrast", "Field", "Rerun changed qualifiers", "Wrong vs mu_field", "Regret (BB)"], body))
    add("")
    add("**Matched played hands (descriptive, post hoc).** Each B allocation compared with the R40H400 prefix that "
        "played about the same number of hands.")
    add("")
    body = []
    for which, lab in (("quarter", "R10H1600"), ("half", "R20H800")):
        for f in FIELDS:
            x = D["extra"][f][f"budget_{which}_rounds_vs_R40prefix_matched_played"]
            body.append([f"{lab} vs R40 prefix R{x['prefix_R']}", FL[f], f"{x['played']:,} / {x['prefix_played']:,}",
                         MP(f, which, "chg"), MP(f, which, "refchg"), MP(f, which, "regret", 1)])
    add(md_table(["Comparison", "Field", "Played hands (arm / prefix)", "Rerun changed qualifiers", "Wrong vs mu_field",
                  "Regret (BB)"], body))
    add("")
    add("### 2.4 Experiment C: adaptive minus frozen (source-schedule counterfactual)")
    add("")
    body = []
    for f in FIELDS:
        body.append([FL[f], FZ(f, "changed_qualifiers"), FZ(f, "spearman_rho"), FZ(f, "kendall_tau"),
                     FZ(f, "mu_field_reference_changed"), FZ(f, "mu_field_qualification_regret", 1),
                     FZ(f, "mu_swiss_qualification_regret", 1)])
    add(md_table(["Field", "Rerun changed qualifiers", "Rerun Spearman", "Rerun Kendall", "Wrong vs mu_field",
                  "Regret vs mu_field (BB)", "Regret vs mu_swiss (BB)"], body))
    add("")
    add("Negative error contrasts and positive rank-correlation contrasts favour adaptive pairing. 50 source "
        "tournaments per field, one frozen replay each.")
    add("")
    add("### 2.5 Experiment D: duplicate packages (operational package comparison)")
    add("")
    body = []
    for f in FIELDS:
        for v in ("ordinary", "dup_fewer_rounds", "dup_shorter_matches"):
            r = D["dup"][(f, v)]
            body.append([FL[f], CELL_KEY[v], f"{num(r['scheduled_work_ratio_vs_ordinary']):.3f}",
                         f"{num(r['work_ratio_vs_ordinary']):.3f}", v_(r, "changed_qualifiers"), v_(r, "spearman_rho"),
                         v_(r, "mu_field_reference_changed"), v_(r, "mu_field_qualification_regret", 1)])
    add(md_table(["Field", "Package", "Scheduled work ratio", "Played hands ratio", "Rerun changed qualifiers",
                  "Rerun Spearman", "Wrong vs mu_field", "Regret (BB)"], body))
    add("")
    body = []
    for arm, comp in (("dup_shorter_matches", "ordinary"), ("dup_fewer_rounds", "ordinary"),
                      ("dup_shorter_matches", "dup_fewer_rounds")):
        for f in FIELDS:
            body.append([f"{CELL_KEY[arm]} vs {CELL_KEY[comp]}", FL[f], C("D", f, "changed_qualifiers", arm, comp),
                         C("D", f, "mu_field_reference_changed", arm, comp),
                         C("D", f, "mu_field_qualification_regret", arm, comp, 1)])
    add(md_table(["Contrast", "Field", "Rerun changed qualifiers", "Wrong vs mu_field", "Regret (BB)"], body))
    add("")
    add("Runtime ratios are stored in the sheet but are indicative only (machine throttling and sleep).")
    add("")
    add("### 2.6 mu_swiss reference (200 tournaments per field)")
    add("")
    add(md_table(["Metric", *[FL[f] for f in FIELDS]], [
        ["Rerun changed qualifiers", *[v_(sw[f]["rerun_stability"], "changed_qualifiers") for f in FIELDS]],
        ["Rerun top-6 overlap", *[v_(sw[f]["rerun_stability"], "topk_overlap") for f in FIELDS]],
        ["Rerun Spearman", *[v_(sw[f]["rerun_stability"], "spearman_rho") for f in FIELDS]],
        ["Rerun Kendall", *[v_(sw[f]["rerun_stability"], "kendall_tau") for f in FIELDS]],
        ["Ambiguous bots", *[f"{num(sw[f]['n_ambiguous_bots']):.0f}" for f in FIELDS]],
        ["Wrong vs mu_field", *[v_(sw[f]["strength_error_vs_mu_field"], "mu_field_reference_changed") for f in FIELDS]],
        ["Regret vs mu_field (BB)", *[v_(sw[f]["strength_error_vs_mu_field"], "mu_field_qualification_regret", 1) for f in FIELDS]],
        ["  with reference uncertainty propagated", *[v_(sw[f]["strength_error_vs_mu_field"], "mu_field_qualification_regret_ref_propagated", 1) for f in FIELDS]],
        ["Boundary strength loss (BB)", *[v_(sw[f]["strength_error_vs_mu_field"], "mu_field_boundary_strength_loss", 1) for f in FIELDS]],
        ["P(same top 6) / P(6/7 reversal) of mu_swiss", *[f"{sw[f]['ranking_robustness']['p_same_top_k_set']:.3f} / {sw[f]['ranking_robustness']['p_cutoff_pair_order_reversed']:.3f}" for f in FIELDS]],
    ]))
    add("")
    add("**P(qualify) near the cutoff** (mu_swiss 200 with Wilson 95%; baseline 50 for comparison; mu_field ranks "
        "1 to 10). Full 180-bot table: Table A1.")
    add("")
    for f in FIELDS:
        add(f"*{FL[f]}*")
        add("")
        base_pq = {r["bot_id"]: r for r in pq(D, f, "baseline")}
        body = [[r["mu_field_rank"], r["bot_id"].replace("nlhe6-", ""), f"{num(r['mu_field_bb']):.1f}",
                 f"{num(r['p_reference_top6']):.3f}", ci(num(r["p_qualify"]), num(r["wilson_lo"]), num(r["wilson_hi"])),
                 f"{num(base_pq[r['bot_id']]['p_qualify']):.2f}"] for r in pq(D, f, "mu_swiss")[:10]]
        add(md_table(["mu_field rank", "Bot", "mu_field (BB)", "P(reference top 6)", "P(qualify), mu_swiss 200",
                      "P(qualify), baseline 50"], body))
        add("")

    # ---- 3 evidence cards
    add("## 3. Evidence cards")
    add("")
    add("Format per card: support, uncertainty, fields, identity vs strength agreement, consistency, defensible "
        "wording, overclaim (avoid). Machine-readable: `data/evidence_cards.json`.")
    add("")
    cards = evidence_cards(D, X, C, Craw, FZ, FZraw, MP, pf_mean, last_step, chg_rng, wrong_rng, rho_rng, sw_chg,
                           sw_wrong, lead_p, exact, n_pool, agree)
    for i, c in enumerate(cards, 1):
        add(f"### Card {i}. {c['finding']}")
        add("")
        for k, lab in (("support", "Support"), ("uncertainty", "Uncertainty"), ("fields", "Fields"),
                       ("identity_vs_strength", "Identity vs strength"), ("consistency", "Consistency"),
                       ("defensible", "Defensible wording"), ("overclaim", "Overclaim (avoid)")):
            val = c[k]
            if isinstance(val, list):
                add(f"* **{lab}:**")
                for x in val:
                    add(f"  * {x}")
            else:
                add(f"* **{lab}:** {val}")
        add("")

    # ---- 4 nuanced
    add("## 4. Results that need nuanced interpretation")
    add("")
    for i, (t, items) in enumerate(nuanced(D, X, C, Craw, MP, FZ, FZraw, gap), 1):
        add(f"### 4.{i} {t}")
        add("")
        for x in items:
            add(f"* {x}")
        add("")

    # ---- 5 profiles
    add("## 5. Field profiles")
    add("")
    add("One frozen field per scenario: each profile describes that field only. No regime-level claims.")
    add("")
    profiles = field_profiles(D, X, gap, psame, prev)
    for f in FIELDS:
        p = profiles[f]
        add(f"### 5.{FIELDS.index(f) + 1} {FL[f]} (`{FIELD_HASH[f]}`)")
        add("")
        for k, lab in (("purpose", "Purpose"), ("reference_gap", "Reference gap"), ("validation", "Validation evidence"),
                       ("baseline", "Baseline selection reliability"), ("p_qualify", "Important P(qualify) values"),
                       ("shows", "What it shows"), ("does_not_show", "What it does not show")):
            add(f"* **{lab}:** {p[k]}")
        add("")

    # ---- 6 reference analysis
    add("## 6. Reference analysis")
    add("")
    ref = reference_analysis(D, X)
    body = []
    for f in FIELDS:
        r = ref[f]
        body.append([FL[f], f"{r['spearman_mu_field_vs_mu_swiss']:.3f}", f"{r['kendall_mu_field_vs_mu_swiss']:.3f}",
                     r["significant_discordant_pairs"], f"{r['point_top6_overlap']} / 6",
                     ", ".join(f"{x['bot']} ({x['mu_field_rank']} vs {x['mu_swiss_rank']})" for x in r["largest_rank_displacements_top12"])])
    add(md_table(["Field", "Spearman", "Kendall", "Significant discordant pairs", "Point top-6 overlap",
                  "Largest rank displacements in mu_field top 12 (mu_field vs mu_swiss rank)"], body))
    add("")
    body = []
    for f in FIELDS:
        r = ref[f]
        body.append([FL[f], r["mu_field_matched_rounds"], f"{r['mu_field_median_se_bb']:.2f}",
                     f"{r['splithalf_r_mu']:.3f}", f"{r['mu_field_p_same_top6']:.3f}",
                     f"{r['mu_swiss_p_same_top6']:.3f}", r["mu_field_ambiguous_bots"],
                     SR(D, f),
                     f"{v_(D['base'][f], 'mu_field_qualification_regret', 1)} / {v_(D['base'][f], 'mu_field_qualification_regret_ref_propagated', 1)}"])
    add(md_table(["Field", "mu_field rounds", "Median SE (BB)", "Split-half r", "mu_field P(same top 6)",
                  "mu_swiss P(same top 6)", "Reference-ambiguous bots", "Reference self-regret (BB; median [2.5, 97.5])",
                  "Baseline regret: tournament CI / propagated CI"], body))
    add("")
    for x in ref["points"]:
        add(f"* {x}")
    add("")

    # ---- 7 figures
    add("## 7. Figures")
    add("")
    add("No figure was redesigned. The plotted values in each figure data CSV were re-checked against the analysis outputs "
        "(`tests/test_fhr4_dossier.py`) and the caption numbers against this dossier; no error was found.")
    add("")
    for fig in figure_entries(D, X, C, FZ, pf_mean, lead_p, exact, n_pool):
        add(f"### {fig['figure']} ({fig['placement']})")
        add("")
        add(f"* **Question:** {fig['question']}")
        add(f"* **Source CSV:** `{fig['source_csv']}` (built from {fig['built_from']})")
        add(f"* **Plotted metrics:** {fig['metrics']}")
        add(f"* **Principal takeaway:** {fig['takeaway']}")
        add(f"* **Caption caveat:** {fig['caveat']}")
        add("")

    # ---- 8 tables
    add("## 8. Tables")
    add("")
    add("Tables 1 to 3 are the frozen publication tables (`paper/fhr4/tables/`, `paper/fhr4/TABLES.md`), "
        "reproduced unchanged. Table 4 and Table A1 are new and generated here.")
    add("")
    for name, title in (("table1_design.csv", "Table 1. Final experimental design"),
                        ("table2_baseline_reliability.csv", "Table 2. Baseline reliability (R40H400, 50 tournaments per field)"),
                        ("table3_primary_contrasts.csv", "Table 3. Primary paired contrasts (first minus second; positive = first worse)")):
        t = rows(PAPER / "tables" / name)
        add(f"### {title}")
        add("")
        add(md_table(list(t[0]), [list(r.values()) for r in t]))
        add("")
    t4 = table4(D, X)
    add("### Table 4. Final references")
    add("")
    add(md_table(list(t4[0]), [list(r.values()) for r in t4]))
    add("")
    add("Note: mu_field reference ranks are the operational point ranking; membership inside the reference-ambiguous set "
        "is not resolved. The crowded-cutoff rule still fires at its 500-round ceiling.")
    add("")
    a1 = tableA1(D)
    add("### Table A1. Per-bot qualification probability (appendix; excerpt: mu_field ranks 1 to 12)")
    add("")
    add("Full 180 rows: `tables/tableA1_per_bot_qualification.csv`.")
    add("")
    add(md_table(["Field", "mu_field rank", "Bot", "mu_field (BB) [SE]", "P(ref top 6)", "mu_swiss rank",
                  "P(qualify) mu_swiss 200 [Wilson]", "P(qualify) baseline 50 [Wilson]"],
                 [[FL[r["field"]], r["mu_field_rank"], r["bot"], f"{r['mu_field_bb']:.1f} [{r['mu_field_se_bb']:.1f}]",
                   f"{r['p_reference_top6']:.3f}", r["mu_swiss_rank"],
                   ci(r["p_qualify_mu_swiss"], r["mu_swiss_wilson_lo"], r["mu_swiss_wilson_hi"]),
                   ci(r["p_qualify_baseline"], r["baseline_wilson_lo"], r["baseline_wilson_hi"])]
                  for r in a1 if r["mu_field_rank"] <= 12]))
    add("")

    # ---- 9 limitations
    add("## 9. Remaining limitations (prioritised)")
    add("")
    lims = limitations(D, X)
    add(md_table(["#", "Limitation", "Why it matters", "What the study did", "How to state it"],
                 [[r["priority"], r["limitation"], r["impact"], r["mitigation"], r["statement"]] for r in lims]))
    add("")

    # ---- 10 closing pack
    add("## 10. Closing pack")
    add("")
    add("### 10.1 Executive research summary (one page)")
    add("")
    for x in executive(D, X, chg_rng, wrong_rng, lead_p, exact, n_pool, C, FZ, agree, pf_mean):
        add(f"* {x}")
    add("")
    add("### 10.2 Methods summary (one page)")
    add("")
    for x in methods_summary(D, whw):
        add(f"* {x}")
    add("")
    add("### 10.3 Results summary (one page)")
    add("")
    for x in results_summary(D, X, C, FZ, MP, sw_chg, sw_wrong, lead_p, exact, n_pool, last_step, agree):
        add(f"* {x}")
    add("")
    add("### 10.4 Figure and table index")
    add("")
    fidx, tidx = figure_index(), table_index()
    add(md_table(["Item", "Placement", "File(s)", "Source data", "Evidence card(s)"],
                 [[r["item"], r["placement"], r["files"], r["source"], r["cards"]] for r in fidx + tidx]))
    add("")
    add("### 10.5 Claims ledger")
    add("")
    ledger = claims(D, X, C, Craw, FZ, FZraw, MP, chg_rng, wrong_rng, sw_chg, sw_wrong, lead_p, exact, n_pool, agree, pf_mean)
    for tier, lab in (("strong", "Strongly supported (can be stated in Results)"),
                      ("qualified", "Supported with qualification (needs scope or wording)"),
                      ("avoid", "Unsupported / avoid")):
        add(f"**{lab}**")
        add("")
        add(md_table(["ID", "Tier", "Claim", "Reason", "Evidence"],
                     [[r["id"], r["tier"], r["claim"], r["reason"], r["evidence"]] for r in ledger if r["tier"] == tier]))
        add("")
    add("### 10.6 Provenance timeline")
    add("")
    add("Classification per change: bug fix; protocol clarification; descriptive analysis; genuinely "
        "pre-registered decision. Two field-replacement decisions fit none of these honestly and are labelled "
        "**post-hoc design decision** (each was pre-registered before its own new data). `Data seen` records "
        "whether outcome data relevant to the decision existed when it was made.")
    add("")
    tl = timeline(D)
    add(md_table(["Date", "Commit", "Event", "Classification", "Data seen", "Effect on results", "Record"],
                 [[r["date"], f"`{r['commit']}`" if r["commit"] else "-", r["event"], r["classification"], r["data_seen"],
                   r["effect"], r["record"]] for r in tl]))
    add("")
    add("**Researcher degrees of freedom, in one place.**")
    add("")
    for x in dof_points(D):
        add(f"* {x}")
    add("")
    return "\n".join(L) + "\n", {"cards": cards, "profiles": profiles, "reference": ref, "limitations": lims,
                                 "ledger": ledger, "timeline": tl, "fig_index": fidx, "tab_index": tidx,
                                 "figures": figure_entries(D, X, C, FZ, pf_mean, lead_p, exact, n_pool),
                                 "table4": t4, "tableA1": a1}


def v_(r: dict, m: str, d: int = 2) -> str:
    return cif(r, m, d)


# ----------------------------------------------------------------------------------- evidence cards


def evidence_cards(D, X, C, Craw, FZ, FZraw, MP, pf_mean, last_step, chg_rng, wrong_rng, rho_rng, sw_chg, sw_wrong,
                   lead_p, exact, n_pool, agree):
    b = D["base"]
    sw = D["swiss"]
    cards = []
    # 1 baseline
    cards.append({
        "id": "F1", "finding": "Baseline tournament reliability (R40H400)",
        "support": [
            f"Rerun changed qualifiers: {FL['separated_control']} {v_(b['separated_control'], 'changed_qualifiers')}, "
            f"{FL['crowded_cutoff']} {v_(b['crowded_cutoff'], 'changed_qualifiers')}, {FL['style_diverse']} {v_(b['style_diverse'], 'changed_qualifiers')} of 6.",
            f"Wrong vs mu_field: {', '.join(FL[f] + ' ' + v_(b[f], 'mu_field_reference_changed') for f in FIELDS)}.",
            f"Rerun Spearman over all 60 bots: {rho_rng}.",
            f"Replicated in the independent 200-tournament mu_swiss reference: rerun changed qualifiers "
            f"{', '.join(ci(*sw_chg[f]) for f in FIELDS)}; wrong vs mu_field {', '.join(ci(*sw_wrong[f]) for f in FIELDS)}.",
            f"Engineered separated control: the six validated leaders qualify with P = {min(lead_p):.2f} to {max(lead_p):.2f} "
            f"(mu_swiss 200); the exact mu_field top 6 was selected in {exact} of {n_pool} tournaments.",
        ],
        "uncertainty": "Tournament bootstrap half-widths about 0.2 qualifiers at n = 50 and about 0.1 at n = 200; "
                       "conditional on one frozen field per scenario.",
        "fields": "All three.",
        "identity_vs_strength": "Agree: high rerun disagreement, many wrong qualifiers, and large regret "
                                f"({', '.join(v_(b[f], 'mu_field_qualification_regret', 1) for f in FIELDS)} BB).",
        "consistency": "Consistent across all three fields and across both references; the two independent tournament "
                       "samples (50 matrix, 200 mu_swiss) agree within intervals.",
        "defensible": "In these controlled fields, 40 rounds of 400-hand matches selected the top 6 with substantial "
                      f"poker-variance error: independent reruns disagreed on {chg_rng} of 6 qualifiers, and {wrong_rng} "
                      "selected bots were outside the mu_field reference top 6.",
        "overclaim": ["Avoid: \"Swiss is unreliable in general\" or \"40 rounds are insufficient in general\".",
                      "Avoid: \"the tournament fails to find the true skill ranking\" (references are estimands, not a true skill ranking)."],
    })
    # 2 rounds
    sweep = D["sweep"]
    cards.append({
        "id": "F2", "finding": "Improvement with rounds (Experiment A)",
        "support": [f"{FL[f]}: wrong vs mu_field {v_(sweep[(f, 5)], 'mu_field_reference_changed')} at R5 to "
                    f"{v_(sweep[(f, 40)], 'mu_field_reference_changed')} at R40; regret "
                    f"{v_(sweep[(f, 5)], 'mu_field_qualification_regret', 1)} to {v_(sweep[(f, 40)], 'mu_field_qualification_regret', 1)} BB; "
                    f"rerun Spearman {v_(sweep[(f, 5)], 'spearman_rho')} to {v_(sweep[(f, 40)], 'spearman_rho')}."
                    for f in FIELDS] + [
            "Every metric improves at every step 5, 10, 20, 30, 40 in every field (generator check).",
            "Last step R30 to R40 regret: " + ", ".join(f"{FL[f]} {a:.1f} to {c:.1f}" for f, (a, c) in last_step.items()) + " BB."],
        "uncertainty": "Prefixes are nested in the same 50 tournaments, so successive points are strongly correlated; "
                       "adjacent-step differences are not separately tested. Endpoints (R5 vs R40) are far outside each other's intervals.",
        "fields": "All three.",
        "identity_vs_strength": "Agree (wrong qualifiers, regret, boundary loss, rerun rank correlation all improve).",
        "consistency": "Consistent across all three fields.",
        "defensible": "Reliability improved continuously with rounds in all three controlled fields, with no evidence of "
                      "a plateau within the preregistered 40-round horizon.",
        "overclaim": ["Avoid: any rounds-needed extrapolation beyond 40 rounds, or \"reliability plateaus at N rounds\".",
                      "Avoid: \"40 rounds are insufficient in general\"."],
    })
    # 3 rounds vs length
    q = ("quarter_rounds_4x_hands", "baseline")
    h = ("half_rounds_2x_hands", "baseline")
    cards.append({
        "id": "F3", "finding": "Rounds versus match length at an equal scheduled hand budget (Experiment B)",
        "support": [
            "R10H1600 minus R40H400, rerun changed qualifiers: " + ", ".join(f"{FL[f]} {C('B', f, 'changed_qualifiers', *q)}" for f in FIELDS) + ".",
            "Same, regret (BB): " + ", ".join(f"{FL[f]} {C('B', f, 'mu_field_qualification_regret', *q, 1)}" for f in FIELDS) + ".",
            "R20H800 minus R40H400, rerun changed qualifiers: " + ", ".join(f"{FL[f]} {C('B', f, 'changed_qualifiers', *h)}" for f in FIELDS) + "; regret: "
            + ", ".join(f"{FL[f]} {C('B', f, 'mu_field_qualification_regret', *h, 1)}" for f in FIELDS) + ".",
            f"Played / scheduled hands (mean over fields): R10H1600 {pf_mean['quarter_rounds_4x_hands']:.2f}, "
            f"R20H800 {pf_mean['half_rounds_2x_hands']:.2f}, R40H400 {pf_mean['baseline']:.2f}.",
            "R10H1600 vs the R40 prefix with matched played hands, regret (BB): " + ", ".join(f"{FL[f]} {MP(f, 'quarter', 'regret', 1)}" for f in FIELDS)
            + "; rerun changed qualifiers: " + ", ".join(f"{FL[f]} {MP(f, 'quarter', 'chg')}" for f in FIELDS) + ".",
        ],
        "uncertainty": "Paired bootstrap on 50 shared replicate ids. The matched-played-hands comparison is post hoc and "
                       "descriptive, and uses prefixes of the baseline tournaments.",
        "fields": "R10 worse: all three on both metrics. R20 vs R40: no clear difference except style_diverse changed qualifiers. "
                  "Matched played hands: separated_control (both metrics), style_diverse (regret and wrong vs mu_field), not crowded_cutoff.",
        "identity_vs_strength": "Agree for R10 vs R40 in all fields. For R20 vs R40 in style_diverse the identity contrast "
                                "excludes zero while regret does not.",
        "consistency": "R10 disadvantage consistent across fields; the size of R20 vs R40 and the matched-played result vary by field.",
        "defensible": "At an equal scheduled hand budget, ten 1,600-hand rounds selected less reliably than forty 400-hand "
                      "rounds in all three controlled fields; twenty 800-hand rounds were close to forty 400-hand rounds. Part "
                      "of the R10 deficit remained at matched played hands in two of the three fields.",
        "overclaim": ["Avoid: \"compute was held fixed\" (scheduled hands were fixed; played hands and runtime were not).",
                      "Avoid: \"R10 is worse at equal played hands everywhere\" or \"R20 is equivalent to R40\".",
                      "Avoid: \"longer matches are always worse\"."],
    })
    # 4 adaptive vs frozen
    cards.append({
        "id": "F4", "finding": "Adaptive versus frozen schedule (Experiment C)",
        "support": [
            "Adaptive minus frozen, rerun changed qualifiers: " + ", ".join(f"{FL[f]} {FZ(f, 'changed_qualifiers')}" for f in FIELDS) + ".",
            "Rerun Spearman: " + ", ".join(f"{FL[f]} {FZ(f, 'spearman_rho')}" for f in FIELDS) + ".",
            "Regret vs mu_field (BB): " + ", ".join(f"{FL[f]} {FZ(f, 'mu_field_qualification_regret', 1)}" for f in FIELDS) + ".",
            "Wrong vs mu_field: " + ", ".join(f"{FL[f]} {FZ(f, 'mu_field_reference_changed')}" for f in FIELDS) + ".",
        ],
        "uncertainty": "Bootstrap paired by source tournament (50 sources, J = 1 replay each). The frozen arm adds fresh "
                       "poker randomness, so the contrast includes that noise.",
        "fields": "Identity and rank-correlation contrasts favour adaptive in all three. Regret clear in separated_control and "
                  "crowded_cutoff; style_diverse regret and wrong-vs-mu_field intervals include zero.",
        "identity_vs_strength": "Rerun identity metrics agree in all fields; reference-based metrics agree in two of three.",
        "consistency": "Direction consistent in all three fields on every metric; strength of evidence varies by field.",
        "defensible": "In a source-schedule counterfactual, adaptive Swiss selected more consistently than a frozen replay "
                      "of its own realised schedule in all three controlled fields.",
        "overclaim": ["Avoid: \"adaptive Swiss causally improves selection\" or a clean causal estimate of adaptation.",
                      "Avoid: \"adaptive pairing reduces regret in every field\"."],
    })
    # 5 duplicate
    s_, f_ = ("dup_shorter_matches", "ordinary"), ("dup_fewer_rounds", "ordinary")
    dd = D["dup"]
    cards.append({
        "id": "F5", "finding": "Duplicate packages (Experiment D)",
        "support": [
            "Rerun Spearman, ordinary vs R40H67x6: " + ", ".join(f"{FL[f]} {v_(dd[(f, 'ordinary')], 'spearman_rho')} vs {v_(dd[(f, 'dup_shorter_matches')], 'spearman_rho')}" for f in FIELDS) + " (intervals do not overlap in any field).",
            "R40H67x6 minus ordinary, rerun changed qualifiers: " + ", ".join(f"{FL[f]} {C('D', f, 'changed_qualifiers', *s_)}" for f in FIELDS) + "; regret (BB): "
            + ", ".join(f"{FL[f]} {C('D', f, 'mu_field_qualification_regret', *s_, 1)}" for f in FIELDS) + ".",
            "R7H400x6 minus ordinary, rerun changed qualifiers: " + ", ".join(f"{FL[f]} {C('D', f, 'changed_qualifiers', *f_)}" for f in FIELDS) + "; regret (BB): "
            + ", ".join(f"{FL[f]} {C('D', f, 'mu_field_qualification_regret', *f_, 1)}" for f in FIELDS) + ".",
            "Scheduled work 1.050 (R7H400x6) and 1.005 (R40H67x6) of ordinary; played hands about 1.05 and 1.06 to 1.07.",
        ],
        "uncertainty": "Paired bootstrap on 50 shared replicate ids. Spearman is compared on levels (no paired Spearman contrast stored for D).",
        "fields": "R40H67x6: Spearman higher in all three; changed qualifiers clear only in separated_control (crowded_cutoff upper bound "
                  f"{Craw('D', 'crowded_cutoff', 'changed_qualifiers', *s_)[2]:+.4f}, includes zero). "
                  "R7H400x6: clear improvement only in crowded_cutoff.",
        "identity_vs_strength": "R40H67x6: identity and regret both negative in all fields, regret clear only in separated_control. "
                                "R7H400x6: agree in crowded_cutoff; mixed elsewhere.",
        "consistency": "Directionally consistent for R40H67x6; not consistent for R7H400x6.",
        "defensible": "In an operational package comparison, the short-match six-lane duplicate package gave higher rerun rank "
                      "correlation than ordinary play in all three controlled fields, with consistently negative but mostly "
                      "inconclusive qualifier and regret contrasts; the fewer-rounds duplicate package helped only in the crowded-cutoff field.",
        "overclaim": ["Avoid: \"duplication causally reduces variance\" (both packages also change rounds or match length).",
                      "Avoid: \"short duplication significantly improves selection in every field\"."],
    })
    # 6 error severity
    cards.append({
        "id": "F6", "finding": "Error severity: wrong qualifiers are mostly clearly weaker entrants",
        "support": [
            "Share of wrong qualifiers outside the mu_field reference-ambiguous set (baseline + mu_swiss, 250 tournaments): "
            + ", ".join(f"{FL[f]} {X[f]['share_wrong_clearly_outside']:.2f}" for f in FIELDS) + ".",
            "Mean regret per wrong qualifier (BB per match): " + ", ".join(f"{FL[f]} {X[f]['mean_regret_per_wrong_qualifier_bb']:.1f}" for f in FIELDS) + ".",
            "Correlation of wrong-qualifier count with regret across tournaments: " + ", ".join(f"{FL[f]} {X[f]['corr_wrong_count_vs_regret']:.2f}" for f in FIELDS) + ".",
            "Baseline clear misqualifications vs wrong qualifiers: " + ", ".join(f"{FL[f]} {num(D['base'][f]['mu_field_clear_misqualifications_value']):.2f} of {num(D['base'][f]['mu_field_reference_changed_value']):.2f}" for f in FIELDS) + ".",
        ],
        "uncertainty": "Pooled descriptive shares (no interval computed). The ambiguous set uses 5% < P(reference top 6) < 95%; "
                       "a different band would move borderline bots.",
        "fields": "All three; strongest in separated_control (no ambiguous bots).",
        "identity_vs_strength": "This card is the bridge: identity errors carry large strength costs.",
        "consistency": "Consistent: roughly four in five wrong qualifiers are clearly weaker in the two fields with reference ambiguity.",
        "defensible": "Most selection errors in these controlled fields admitted bots the mu_field reference clearly places outside "
                      "the top 6, rather than swaps among near-equals.",
        "overclaim": ["Avoid: \"errors are only near-equal swaps\" (opposite of the data) and \"every error is costly\" (some are ambiguous swaps)."],
    })
    # 7 reference uncertainty
    b = D["base"]
    cards.append({
        "id": "F7", "finding": "Reference uncertainty is small relative to tournament noise; references agree",
        "support": [
            "Reference self-regret (BB; bootstrap median [2.5, 97.5 percentile]): " + ", ".join(f"{FL[f]} {SR(D, f)}" for f in FIELDS)
            + " vs tournament regret " + ", ".join(v_(b[f], 'mu_field_qualification_regret', 1) for f in FIELDS) + ".",
            "Regret interval with reference uncertainty propagated: " + ", ".join(f"{FL[f]} {v_(b[f], 'mu_field_qualification_regret_ref_propagated', 1)}" for f in FIELDS) + ".",
            "mu_field vs mu_swiss ordering: Spearman " + ", ".join(f"{agree[f]['spearman_rho']:.3f}" for f in FIELDS)
            + "; Kendall " + ", ".join(f"{agree[f]['kendall_tau']:.3f}" for f in FIELDS) + "; no significant discordant pairs.",
            "Wrong vs mu_field and wrong vs mu_swiss baseline counts are equal or nearly equal: "
            + ", ".join(f"{FL[f]} {num(b[f]['mu_field_reference_changed_value']):.2f} / {num(b[f]['mu_swiss_reference_changed_value']):.2f}" for f in FIELDS) + ".",
        ],
        "uncertainty": "crowded_cutoff mu_field reference still fires its rule at the 500-round ceiling (one bot outside the designed sets, P(top 6) 0.208); "
                       f"reference P(same top 6) {D['refs']['crowded_cutoff']['field_reference']['uncertainty']['p_same_top_k_set']:.3f} (crowded) "
                       f"and {D['refs']['style_diverse']['field_reference']['uncertainty']['p_same_top_k_set']:.3f} (style).",
        "fields": "All three; least reference uncertainty in separated_control.",
        "identity_vs_strength": "Agree: wrong-qualifier counts barely change between references; regret intervals widen modestly.",
        "consistency": "Consistent.",
        "defensible": "Finite reference uncertainty was small relative to tournament noise, and the mu_field and mu_swiss "
                      "references ordered the bots almost identically in all three controlled fields.",
        "overclaim": ["Avoid: \"the references are the true skill ranking\" or \"the crowded-cutoff reference top 6 is settled\"."],
    })
    return cards


# ------------------------------------------------------------------------------------- nuanced items


def nuanced(D, X, C, Craw, MP, FZ, FZraw, gap):
    b = D["base"]
    sc, cc, sd = "separated_control", "crowded_cutoff", "style_diverse"
    q, h = ("quarter_rounds_4x_hands", "baseline"), ("half_rounds_2x_hands", "baseline")
    s_ = ("dup_shorter_matches", "ordinary")
    items = []
    items.append(("Separated control: highest regret despite the fewest misses", [
        f"Wrong vs mu_field: {FL[sc]} {v_(b[sc], 'mu_field_reference_changed')} (fewest) but regret {v_(b[sc], 'mu_field_qualification_regret', 1)} BB (highest).",
        f"Each miss costs about {X[sc]['mean_regret_per_wrong_qualifier_bb']:.0f} BB per match there vs about "
        f"{X[cc]['mean_regret_per_wrong_qualifier_bb']:.0f} BB in the other two fields, because a miss replaces a leader "
        f"{gap[sc]:.1f} BB above the next bot.",
        "Read counts (wrong qualifiers, changed qualifiers) for frequency and regret for cost; do not rank fields by regret alone.",
    ]))
    items.append(("R20 vs R40 is much closer than R10 vs R40", [
        "R10H1600 minus R40H400 regret (BB): " + ", ".join(f"{FL[f]} {C('B', f, 'mu_field_qualification_regret', *q, 1)}" for f in FIELDS) + ".",
        "R20H800 minus R40H400 regret (BB): " + ", ".join(f"{FL[f]} {C('B', f, 'mu_field_qualification_regret', *h, 1)}" for f in FIELDS) + ".",
        f"Only style_diverse R20 changed qualifiers excludes zero ({C('B', sd, 'changed_qualifiers', *h)}).",
        "Do not read an absent R20 difference as equivalence; intervals are about +/-0.3 qualifiers and +/-17 BB.",
    ]))
    items.append(("Matched-played-hands result is not uniform across fields", [
        "R10H1600 vs the R40 prefix with matched played hands:",
        *[f"{FL[f]}: changed qualifiers {MP(f, 'quarter', 'chg')}, wrong vs mu_field {MP(f, 'quarter', 'refchg')}, regret {MP(f, 'quarter', 'regret', 1)} BB." for f in FIELDS],
        "Clear on both metrics in separated_control; regret and wrong-vs-mu_field (not changed qualifiers) in style_diverse; inconclusive in crowded_cutoff.",
        "Post hoc and descriptive; prefixes of baseline tournaments are not independent tournaments with fewer rounds scheduled.",
    ]))
    items.append(("Short duplication: directionally consistent, not individually significant everywhere", [
        "R40H67x6 minus ordinary, rerun changed qualifiers: " + ", ".join(f"{FL[f]} {C('D', f, 'changed_qualifiers', *s_)}" for f in FIELDS) + ".",
        "Regret (BB): " + ", ".join(f"{FL[f]} {C('D', f, 'mu_field_qualification_regret', *s_, 1)}" for f in FIELDS) + ".",
        "The consistent evidence is direction in all three fields plus higher rerun Spearman in all three. Only separated_control "
        "excludes zero on changed qualifiers and regret. Figure 4 panel b (Spearman) was chosen after the results were seen; "
        "report the changed-qualifier contrasts alongside it.",
        "In crowded_cutoff the R7H400x6 package has the largest single improvement "
        f"({C('D', cc, 'changed_qualifiers', 'dup_fewer_rounds', 'ordinary')} qualifiers).",
    ]))
    items.append(("Crowded cutoff is not dominated by cheap near-equal swaps", [
        f"Share of wrong qualifiers clearly outside the reference-ambiguous set: {X[cc]['share_wrong_clearly_outside']:.2f}; "
        f"mean cost {X[cc]['mean_regret_per_wrong_qualifier_bb']:.1f} BB per wrong qualifier.",
        f"Baseline clear misqualifications {num(b[cc]['mu_field_clear_misqualifications_value']):.2f} of "
        f"{num(b[cc]['mu_field_reference_changed_value']):.2f} wrong; clear omissions only "
        f"{num(b[cc]['mu_field_clear_omissions_value']):.2f}, because several reference top-6 members are themselves ambiguous.",
        "The designed crowd makes the reference boundary uncertain, but the tournament mostly errs by admitting clearly weaker bots, not by swapping crowd members.",
    ]))
    items.append(("Regret is not directly comparable across fields", [
        "Regret is BB per match summed over six qualifiers; its scale depends on each field's strength spread "
        f"(mu_field SD across bots: {', '.join(f'{FL[f]} {X[f]["sd_of_mu_field_across_bots_bb"]:.1f}' for f in FIELDS)} BB; "
        f"rank-6/7 gap {', '.join(f'{FL[f]} {gap[f]:.1f}' for f in FIELDS)} BB).",
        "Compare regret within a field across conditions; compare fields with identity metrics.",
        "mu_swiss regret is on a compressed scale (adaptive pairing): baseline regret vs mu_swiss "
        + ", ".join(f"{FL[f]} {v_(b[f], 'mu_swiss_qualification_regret', 1)}" for f in FIELDS) + " BB; do not mix with mu_field regret.",
    ]))
    items.append(("Experiment C is not a clean causal estimate", [
        "The frozen schedules were produced by adaptive trajectories, so the frozen arm inherits pairings informed by the source tournament's poker outcomes.",
        "Fresh poker randomness in the replay adds variance to the paired contrast; J = 1 replay per source.",
        f"style_diverse regret {FZ(sd, 'mu_field_qualification_regret', 1)} BB and wrong vs mu_field {FZ(sd, 'mu_field_reference_changed')} include zero.",
        "Use \"source-schedule counterfactual\"; do not decompose into an effect of adaptation.",
    ]))
    items.append(("Experiment D is an operational package comparison", [
        "R7H400x6 changes rounds (40 to 7) and R40H67x6 changes match length (400 to 67) as well as adding duplication.",
        "Scheduled work is 1.050 and 1.005 of ordinary; played hands are about 5 to 7% higher.",
        "Mechanism (descriptive diagnostic, not tested): in 400-hand persistent matches about 60% of bot-lanes bust and duplicate "
        "trajectories diverge early, so little card luck cancels; in 67-hand lanes busts are rare and lanes stay coupled.",
    ]))
    items.append(("Baseline vs mu_swiss per-bot differences are within noise", [
        "Baseline P(qualify) uses 50 tournaments (Wilson half-widths up to about 0.14); mu_swiss uses 200 (up to about 0.07).",
        "Example: nit-e3-s1 in separated_control, " + _pq_pair(D, sc, "nlhe6-nit-e3-s1") + ".",
    ]))
    nm = X
    items.append(("P(qualify) is not monotone in mu_field below the cutoff", [
        "Bots outside the reference top 6 that qualify more often than the weakest reference top-6 bot (mu_swiss 200): "
        + "; ".join(f"{FL[f]} (weakest top-6 P = {nm[f]['weakest_reference_top6_p_qualify']:.3f}): "
                    + (", ".join(f"{x['bot']} (rank {x['mu_field_rank']}) {x['p_qualify']:.3f}"
                                 for x in nm[f]["non_top6_bots_qualifying_more_often_than_weakest_reference_top6"]) or "none")
                    for f in FIELDS) + ".",
        "In the flat 0.15 to 0.25 band, mu_field rank predicts P(qualify) weakly; differences of a few points are within Wilson intervals (about +/-0.06).",
        "Archetype residuals (ranks 7 to 30, vs a linear fit on mu_field) are small and inconsistent: maniac "
        + ", ".join(f"{nm[f]['p_qualify_residual_by_archetype_ranks_7_30'].get('maniac', {}).get('mean', float('nan')):+.3f}".replace("-", MINUS) for f in FIELDS)
        + " across the three fields. No claim that high-variance styles systematically over-qualify.",
    ]))
    items.append(("Noise vs spread consistency check (descriptive)", [
        "Median per-bot tournament-to-tournament SD of the mean per-match score (mu_swiss 200): "
        + ", ".join(f"{FL[f]} {X[f]['per_bot_tournament_sd_of_mean_per_match_score_bb_median']:.1f}" for f in FIELDS) + " BB.",
        "SD of mu_swiss per-match score across bots: " + ", ".join(f"{FL[f]} {X[f]['sd_of_mu_swiss_per_match_across_bots_bb']:.1f}" for f in FIELDS) + " BB.",
        "Noise is about as large as the between-bot spread inside the Swiss mechanism; the implied signal share "
        + ", ".join(f"{X[f]['signal_share_within_swiss']:.2f}" for f in FIELDS)
        + " is in line with rerun Spearman " + ", ".join(f"{num(D['base'][f]['spearman_rho_value']):.2f}" for f in FIELDS) + ".",
        "Approximate (score correlation vs rank correlation; Swiss pairing compresses spread). Supporting context, not a result.",
    ]))
    return items


def _pq_pair(D, f, bot) -> str:
    m = {r["cell"]: r for r in D["pq_all"] if r["field"] == f and r["bot_id"] == bot}
    s, b = m["mu_swiss"], m["baseline"]
    return (f"mu_swiss {ci(num(s['p_qualify']), num(s['wilson_lo']), num(s['wilson_hi']))} vs baseline "
            f"{ci(num(b['p_qualify']), num(b['wilson_lo']), num(b['wilson_hi']))}")


# ----------------------------------------------------------------------------------- field profiles


def field_profiles(D, X, gap, psame, prev):
    b = D["base"]
    out = {}
    val, con, sv2 = D["sc_val"], D["sc_con"], D["sv2_val"]

    def pq_list(f, n):
        return ", ".join(f"{r['bot_id'].replace('nlhe6-', '')} {num(r['p_qualify']):.2f}" for r in pq(D, f, "mu_swiss")[:n])

    def best_nonref(f, n=2):
        rs = [r for r in pq(D, f, "mu_swiss") if int(r["mu_field_rank"]) > 6]
        rs.sort(key=lambda r: -num(r["p_qualify"]))
        return ", ".join(f"{r['bot_id'].replace('nlhe6-', '')} (rank {r['mu_field_rank']}) {num(r['p_qualify']):.2f}" for r in rs[:n])

    def often(f):
        hi = [r for r in pq(D, f, "mu_swiss") if num(r["p_qualify"]) >= 0.35]
        rest = max(num(r["p_qualify"]) for r in pq(D, f, "mu_swiss") if num(r["p_qualify"]) < 0.35)
        names = ", ".join(r["bot_id"].replace("nlhe6-", "") + " (rank " + r["mu_field_rank"] + ")" for r in hi)
        return (f"Only {len(hi)} bots qualify with P >= 0.35 ({names}); every other bot is at or below {rest:.2f}, "
                "on both sides of the reference boundary.")

    def base_line(f):
        return (f"rerun changed qualifiers {v_(b[f], 'changed_qualifiers')}; wrong vs mu_field {v_(b[f], 'mu_field_reference_changed')}; "
                f"regret {v_(b[f], 'mu_field_qualification_regret', 1)} BB; rerun Spearman {v_(b[f], 'spearman_rho')}; "
                f"mu_swiss 200: changed {ci(*est(D['swiss'][f]['rerun_stability'], 'changed_qualifiers'))}, "
                f"wrong {ci(*est(D['swiss'][f]['strength_error_vs_mu_field'], 'mu_field_reference_changed'))}")

    sc = "separated_control"
    crit = val["criteria"]
    out[sc] = {
        "purpose": "Engineered easy-selection control: if selection fails here, the cause is tournament noise, not reference ambiguity at the cutoff.",
        "reference_gap": f"mu_field rank-6/7 gap {gap[sc]:.1f} BB; P(same top 6) {psame[sc]:.3f}; P(6/7 reversal) {prev[sc]:.3f}; no reference-ambiguous bots.",
        "validation": (f"Built once from the 2,000 existing pool rounds (construction gap {con['construction_gap_bb']:.1f} BB) and bound before validation; "
                       f"one-shot validation on {val['binding']['validation_rounds']:,} fresh pool-style rounds (seed family `{val['binding']['validation_seed_family']}`): "
                       f"P(leaders are the top 6) {crit['p_leaders_are_top6']['value']:.3f} (required >= 0.95), max non-leader P(top 6) "
                       f"{crit['max_nonleader_p_top6']['value']:.4f}, gap {val['gap_point_bb']:.2f} BB (one-sided 95% LCB {val['gap_lcb95_one_sided_bb']:.2f}). "
                       "Field-relative mu_field reference generated independently afterwards."),
        "baseline": base_line(sc) + ".",
        "p_qualify": f"Leaders (mu_swiss 200): {pq_list(sc, 6)}. Best non-leaders: {best_nonref(sc)} (P(qualify) is not monotone in mu_field below the gap). Exact reference top 6 selected in "
                     f"{X[sc]['exact_reference_top6_selected']} of {X[sc]['tournaments_pooled']} tournaments.",
        "shows": "Even with six independently validated leaders far above the rest, 40 x 400 adaptive Swiss misses about half of them per tournament; "
                 "every wrong qualifier is clearly weaker.",
        "does_not_show": "It is engineered (strongest defensible six plus the 54 weakest pool bots); it is not representative of any natural field. "
                         "Its validation ran in pool context; the field-relative reference confirmed the separation.",
    }
    cc = "crowded_cutoff"
    rj = D["refjson"][cc]
    out[cc] = {
        "purpose": "Qualification-boundary stress test: three designed leaders and a designed near-equal crowd at ranks 4 to about 15.",
        "reference_gap": f"mu_field rank-6/7 gap {gap[cc]:.2f} BB at {rj['matched_rounds']} matched rounds; P(same top 6) {psame[cc]:.3f}; "
                         f"P(6/7 reversal) {prev[cc]:.3f}; {len(D['refs'][cc]['field_reference']['uncertainty']['reference_ambiguous_bots'])} reference-ambiguous bots.",
        "validation": "Pre-registered mu_field rule fired at 250 and again at the 500-round ceiling (loose-e2-s1, outside the designed sets, P(top 6) 0.208). "
                      "Carried as residual reference uncertainty. Designed leaders all have P(top 6) >= 0.95.",
        "baseline": base_line(cc) + ".",
        "p_qualify": f"Top mu_field ranks (mu_swiss 200): {pq_list(cc, 8)}. {often(cc)} Best bots outside the reference top 6: {best_nonref(cc, 3)}.",
        "shows": f"Selection noise dominates even where the reference boundary is uncertain: {X[cc]['share_wrong_clearly_outside']:.0%} of wrong qualifiers are clearly outside the ambiguous set.",
        "does_not_show": "Nothing about crowded fields as a class (one field). The reference top 6 below the three leaders is not settled.",
    }
    sd = "style_diverse"
    rj = D["refjson"][sd]
    div = D["diversity"].get(sd, {})
    out[sd] = {
        "purpose": "Strategically heterogeneous field (style x strength balanced; no near-duplicate parameter vectors).",
        "reference_gap": f"mu_field rank-6/7 gap {gap[sd]:.2f} BB at {rj['matched_rounds']} matched rounds; P(same top 6) {psame[sd]:.3f}; "
                         f"P(6/7 reversal) {prev[sd]:.3f}; {len(D['refs'][sd]['field_reference']['uncertainty']['reference_ambiguous_bots'])} reference-ambiguous bots; rule does not fire at 500 (locked).",
        "validation": "Diversity audit: 8 archetypes, 60/60 distinct parameter vectors, 0 near-duplicate pairs" + (f" (styles {div.get('styles')})" if div.get("styles") else "") + ".",
        "baseline": base_line(sd) + ".",
        "p_qualify": f"Top mu_field ranks (mu_swiss 200): {pq_list(sd, 8)}. {often(sd)} Best bots outside the reference top 6: {best_nonref(sd, 3)}.",
        "shows": "Results from the other two fields are not an artefact of near-duplicate agents: reliability is similar with strategically distinct bots.",
        "does_not_show": "Nothing about style mixes in general; one field, synthetic stateless agents.",
    }
    return out


# ---------------------------------------------------------------------------------- reference analysis


def reference_analysis(D, X):
    out: dict = {}
    for f in FIELDS:
        r = D["refs"][f]
        rj = D["refjson"][f]
        out[f] = {
            "spearman_mu_field_vs_mu_swiss": r["ordering_agreement"]["spearman_rho"],
            "kendall_mu_field_vs_mu_swiss": r["ordering_agreement"]["kendall_tau"],
            "significant_discordant_pairs": len(r["ordering_agreement"]["significant_discordant_pairs"]),
            "point_top6_overlap": X[f]["point_top6_overlap_mu_field_vs_mu_swiss"],
            "largest_rank_displacements_top12": X[f]["largest_rank_displacements_top12"],
            "mu_field_matched_rounds": rj["matched_rounds"], "mu_field_median_se_bb": rj["median_se_bb"],
            "splithalf_r_mu": rj["splithalf"]["r_mu"],
            "mu_field_p_same_top6": r["field_reference"]["uncertainty"]["p_same_top_k_set"],
            "mu_swiss_p_same_top6": r["swiss_reference"]["uncertainty"]["p_same_top_k_set"],
            "mu_field_ambiguous_bots": len(r["field_reference"]["uncertainty"]["reference_ambiguous_bots"]),
            "self_regret_median_ci_bb": selfreg(D, f),
            "self_regret_mean_bb_stored": num(D["selfreg"][(f, "mu_field")]["mean_bb"]),
            "self_regret_share_zero": num(D["selfreg"][(f, "mu_field")]["share_zero"]),
            "baseline_regret_bb": est(D["base"][f], "mu_field_qualification_regret"),
            "baseline_regret_ref_propagated_bb": est(D["base"][f], "mu_field_qualification_regret_ref_propagated"),
        }
    b = D["base"]
    out["points"] = [
        "mu_field and mu_swiss are different estimands (random-partition play vs the adaptive Swiss mechanism); their near-identical orderings are evidence that the conclusions do not depend on the choice of reference, not that either is a context-free ranking.",
        "Discordance is confined to near-equal bots: no pair is significantly discordant in any field, and the largest top-12 rank displacements are listed above.",
        "Reference self-regret (regret of the reference's own point top 6 under its bootstrap; median [2.5, 97.5 percentile]) is "
        + ", ".join(f"{FL[f]} {SR(D, f)}" for f in FIELDS)
        + " BB, against tournament regret of " + ", ".join(v_(b[f], 'mu_field_qualification_regret', 1) for f in FIELDS) + " BB.",
        "Propagating reference uncertainty widens regret intervals modestly and leaves wrong-qualifier intervals nearly unchanged (Section 2.1).",
        "Why tournament noise dominates: per-bot SE of mu_field is about 3 to 4 BB per match after 250 to 500 matched duplicate rounds, while one tournament gives each bot 40 single-lane matches whose mean varies by about 18 BB between tournaments (Section 4.11).",
        "mu_swiss vs mu_field selection metrics differ in scale (Swiss pairing compresses spread), so compare regret only within one reference.",
        "**Reporting change (dossier cleanup).** The frozen analysis stores `reference_self_regret` as the bootstrap MEAN "
        "paired with a 2.5/97.5 PERCENTILE interval. In the separated control "
        f"{num(D['selfreg'][('separated_control', 'mu_field')]['share_zero']) * 1000:.0f} of 1,000 resamples give zero, so the mean "
        f"({num(D['selfreg'][('separated_control', 'mu_field')]['mean_bb']):.6f} BB) lies above a [0, 0] interval. The dossier now reports "
        "the bootstrap MEDIAN with the same percentile interval in every field and table, recomputed read-only by "
        "`scripts/fhr4_export_self_regret.py` from the same resamples (the recomputed means reproduce the stored values; "
        "`exports/reference_self_regret.csv`). Stored analysis outputs are unchanged; the means remain in the results sheet as "
        "`*_reference_self_regret_mean` rows without an interval.",
    ]
    return out


# ------------------------------------------------------------------------------------------ figures


def figure_entries(D, X, C, FZ, pf_mean, lead_p, exact, n_pool):
    b, sw = D["base"], D["sweep"]
    q = ("quarter_rounds_4x_hands", "baseline")
    s_ = ("dup_shorter_matches", "ordinary")
    dd = D["dup"]
    return [
        {"figure": "Figure 1. Reliability vs rounds", "placement": "main text", "cards": "F2",
         "question": "How do wrong qualifiers and regret change as Swiss rounds accumulate (5 to 40)?",
         "source_csv": "paper/fhr4/figures/data/fig1_reliability_vs_rounds.csv", "built_from": "round_sweep.csv",
         "metrics": "(a) wrong vs mu_field; (b) qualification regret (BB); by prefix and field, 95% bootstrap.",
         "takeaway": "; ".join(f"{FL[f]} wrong {num(sw[(f, 5)]['mu_field_reference_changed_value']):.2f} to {num(sw[(f, 40)]['mu_field_reference_changed_value']):.2f}" for f in FIELDS) + "; monotone, no plateau within 40 rounds.",
         "caveat": "Prefixes of the same tournaments (correlated points); separated control has the highest regret because each miss is costlier, not because it has more misses; nothing implied beyond 40 rounds."},
        {"figure": "Figure 2. Rounds vs match length", "placement": "main text", "cards": "F3",
         "question": "At an equal scheduled hand budget, is it better to play more rounds or longer matches?",
         "source_csv": "paper/fhr4/figures/data/fig2_allocation_equal_scheduled_budget.csv", "built_from": "budget_allocation.csv, contrasts.csv, audit_extra.json",
         "metrics": "(a) rerun changed qualifiers; (b) regret; (c, d) paired contrasts incl. the matched-played-hands row.",
         "takeaway": "R10H1600 worse than R40H400 in all fields (changed qualifiers " + ", ".join(C('B', f, 'changed_qualifiers', *q) for f in FIELDS) + "); R20H800 close to R40H400.",
         "caveat": f"Only scheduled hands are equal (played {pf_mean['quarter_rounds_4x_hands']:.0%}, {pf_mean['half_rounds_2x_hands']:.0%}, {pf_mean['baseline']:.0%}); matched-played row differs by field and metric."},
        {"figure": "Figure 3. Adaptive vs frozen schedule", "placement": "main text", "cards": "F4",
         "question": "Does adaptive Swiss select more reliably than a frozen replay of its own realised schedule?",
         "source_csv": "paper/fhr4/figures/data/fig3_adaptive_vs_frozen.csv", "built_from": "frozen_schedule.csv",
         "metrics": "Adaptive minus frozen: (a) rerun changed qualifiers; (b) regret; paired by source.",
         "takeaway": "Changed qualifiers " + ", ".join(f"{FL[f]} {FZ(f, 'changed_qualifiers')}" for f in FIELDS) + ".",
         "caveat": "Source-schedule counterfactual, not a causal estimate; style_diverse regret interval includes zero."},
        {"figure": "Figure 4. Duplicate packages", "placement": "main text", "cards": "F5",
         "question": "Do six-lane duplicate packages of about equal scheduled work select more consistently than ordinary play?",
         "source_csv": "paper/fhr4/figures/data/fig4_duplicate_packages.csv", "built_from": "duplicate_play.csv, contrasts.csv",
         "metrics": "(a) rerun changed qualifiers; (b) rerun Spearman; (c, d) paired contrasts for changed qualifiers and regret.",
         "takeaway": "R40H67x6 Spearman " + ", ".join(f"{num(dd[(f, 'dup_shorter_matches')]['spearman_rho_value']):.2f} vs {num(dd[(f, 'ordinary')]['spearman_rho_value']):.2f}" for f in FIELDS) + " (dup vs ordinary).",
         "caveat": "Operational package comparison; changed-qualifier contrasts individually clear only in separated control; panel b metric chosen after results were seen."},
        {"figure": "Figure 5. Qualification probability at the cutoff", "placement": "main text", "cards": "F1, F6",
         "question": "How likely is each bot near the reference boundary to qualify under 40 x 400 adaptive Swiss?",
         "source_csv": "paper/fhr4/figures/data/fig5_qualification_probability_at_cutoff.csv", "built_from": "exports/qualification_probabilities_all_cells.csv",
         "metrics": "P(qualify) from mu_swiss 200 (Wilson 95%) with baseline-50 diamonds, ordered by mu_field rank.",
         "takeaway": f"Separated control leaders {min(lead_p):.2f} to {max(lead_p):.2f}; exact top 6 in {exact} of {n_pool}; flat 0.15 to 0.25 band after the top two or three bots in the other fields.",
         "caveat": "Baseline diamonds have intervals about twice as wide; individual baseline deviations are within noise."},
        {"figure": "Figure S1. Identity vs strength errors", "placement": "supplement", "cards": "F6",
         "question": "Are wrong qualifiers near-equal swaps or clearly weaker bots, and how does regret scale with wrong count?",
         "source_csv": "paper/fhr4/figures/data/figS1_identity_vs_strength_error.csv", "built_from": "exports/tournament_errors.csv",
         "metrics": "(a to c) regret vs wrong count per tournament; (d) share of wrong qualifiers clearly outside the reference-ambiguous set.",
         "takeaway": "Clearly-outside share " + ", ".join(f"{FL[f]} {X[f]['share_wrong_clearly_outside']:.2f}" for f in FIELDS) + "; correlation " + ", ".join(f"{X[f]['corr_wrong_count_vs_regret']:.2f}" for f in FIELDS) + ".",
         "caveat": "Pooled descriptive (baseline 50 + mu_swiss 200); ambiguous band 5% to 95%."},
    ]


def figure_index():
    return [
        {"item": "Figure 1", "placement": "main", "files": "figures/fig1_reliability_vs_rounds.{pdf,svg,png}", "source": "figures/data/fig1_reliability_vs_rounds.csv", "cards": "F2"},
        {"item": "Figure 2", "placement": "main", "files": "figures/fig2_allocation_equal_scheduled_budget.{pdf,svg,png}", "source": "figures/data/fig2_allocation_equal_scheduled_budget.csv", "cards": "F3"},
        {"item": "Figure 3", "placement": "main", "files": "figures/fig3_adaptive_vs_frozen.{pdf,svg,png}", "source": "figures/data/fig3_adaptive_vs_frozen.csv", "cards": "F4"},
        {"item": "Figure 4", "placement": "main", "files": "figures/fig4_duplicate_packages.{pdf,svg,png}", "source": "figures/data/fig4_duplicate_packages.csv", "cards": "F5"},
        {"item": "Figure 5", "placement": "main", "files": "figures/fig5_qualification_probability_at_cutoff.{pdf,svg,png}", "source": "figures/data/fig5_qualification_probability_at_cutoff.csv", "cards": "F1, F6"},
        {"item": "Figure S1", "placement": "supplement", "files": "figures/figS1_identity_vs_strength_error.{pdf,svg,png}", "source": "figures/data/figS1_identity_vs_strength_error.csv", "cards": "F6"},
    ]


def table_index():
    return [
        {"item": "Table 1", "placement": "main", "files": "tables/table1_design.csv", "source": "field references, config", "cards": "-"},
        {"item": "Table 2", "placement": "main", "files": "tables/table2_baseline_reliability.csv", "source": "baseline_reliability.csv", "cards": "F1"},
        {"item": "Table 3", "placement": "main", "files": "tables/table3_primary_contrasts.csv", "source": "contrasts.csv, frozen_schedule.csv", "cards": "F3, F4, F5"},
        {"item": "Table 4", "placement": "main or methods", "files": "dossier/tables/table4_final_references.csv", "source": "reference.json, summary.json", "cards": "F7"},
        {"item": "Table A1", "placement": "appendix", "files": "dossier/tables/tableA1_per_bot_qualification.csv", "source": "exports/qualification_probabilities_all_cells.csv, field_references.csv", "cards": "F1, F6"},
    ]


# ------------------------------------------------------------------------------------------- tables


def table4(D, X) -> list[dict]:
    out = []
    for f in FIELDS:
        rj, r, s = D["refjson"][f], D["refs"][f], D["swiss"][f]
        out.append({
            "Field": FL[f], "mu_field matched rounds": rj["matched_rounds"],
            "mu_field calibration": rj["calib_id"].split(".")[-1], "mu_field digest": rj["calibration_digest"][:8],
            "Median SE (BB)": f"{rj['median_se_bb']:.2f}", "Split-half r": f"{rj['splithalf']['r_mu']:.3f}",
            "Rank-6/7 gap (BB)": f"{rj['gap_at_cutoff_bb']:.2f}",
            "mu_field P(same top 6)": f"{r['field_reference']['uncertainty']['p_same_top_k_set']:.3f}",
            "mu_field P(6/7 reversal)": f"{r['field_reference']['uncertainty']['p_cutoff_pair_order_reversed']:.3f}",
            "Reference-ambiguous bots": len(r["field_reference"]["uncertainty"]["reference_ambiguous_bots"]),
            "mu_field rule at final rounds": "fires (ceiling; carried as uncertainty)" if rj["extension_rule"]["extend"] else "does not fire (locked)",
            "mu_swiss tournaments": s["n_tournaments"],
            "mu_swiss P(same top 6)": f"{s['ranking_robustness']['p_same_top_k_set']:.3f}",
            "mu_swiss max Wilson half-width": f"{s['extension_rule']['max_possible_wilson_half_width_at_n']:.3f}",
            "Spearman mu_field vs mu_swiss": f"{r['ordering_agreement']['spearman_rho']:.3f}",
            "Kendall mu_field vs mu_swiss": f"{r['ordering_agreement']['kendall_tau']:.3f}",
            "Point top-6 overlap": X[f]["point_top6_overlap_mu_field_vs_mu_swiss"],
        })
    return out


def tableA1(D) -> list[dict]:
    fr = {(r["field"], r["bot_id"]): r for r in D["fref"]}
    out = []
    for f in FIELDS:
        base = {r["bot_id"]: r for r in pq(D, f, "baseline")}
        for r in pq(D, f, "mu_swiss"):
            x, bb = fr[(f, r["bot_id"])], base[r["bot_id"]]
            out.append({"field": f, "bot": r["bot_id"].replace("nlhe6-", ""), "mu_field_rank": int(r["mu_field_rank"]),
                        "mu_field_bb": round(num(r["mu_field_bb"]), 3), "mu_field_se_bb": round(num(x["mu_field_se"]) / 100, 3),
                        "p_reference_top6": num(r["p_reference_top6"]), "mu_swiss_rank": int(x["mu_swiss_rank"]),
                        "p_qualify_mu_swiss": num(r["p_qualify"]), "mu_swiss_wilson_lo": num(r["wilson_lo"]),
                        "mu_swiss_wilson_hi": num(r["wilson_hi"]), "n_mu_swiss": int(r["n_tournaments"]),
                        "p_qualify_baseline": num(bb["p_qualify"]), "baseline_wilson_lo": num(bb["wilson_lo"]),
                        "baseline_wilson_hi": num(bb["wilson_hi"]), "n_baseline": int(bb["n_tournaments"])})
    return out


# -------------------------------------------------------------------------------------- limitations


def limitations(D, X):
    n_broad = sum(c.get("extend_broad_sensitivity", False) for c in D["ext"]["matrix"]["cells"].values())
    L = [
        ("One field per scenario", "Tournament reruns are conditional on one frozen field per scenario; no regime-level inference.",
         "Three deliberately different fields; results stated per field.", "Results hold in these controlled fields; no claim about classes of fields."),
        ("Synthetic, stateless agents", "Rule-based policy families without within-match opponent modelling may under- or over-state luck vs skill in real bot fields.",
         "Diversity audit (8 archetypes; style_diverse has no near-duplicates).", "Agents are synthetic stateless policies; transfer to adaptive agents is untested."),
        ("Engineered separated control", "Built from the strongest defensible six plus the 54 weakest pool bots; not a natural field.",
         "One-shot independent validation (P = 0.998) and an independent field-relative reference.", "Use \"engineered separated control\"; never call it representative."),
        ("40-round horizon only", "Reliability had not plateaued at 40 rounds; how much more rounds would help is unknown.",
         "Horizon fixed at 5 to 40 by preregistration; 60/80/120 explicitly not run.", "\"within the preregistered 40-round horizon\"; no extrapolation."),
        ("Experiment C interpretation", "Frozen schedules come from adaptive trajectories; replay adds fresh randomness; J = 1.",
         "Paired by source tournament; termed a counterfactual from the start.", "\"source-schedule counterfactual\"; not a causal effect of adaptation."),
        ("Experiment D interpretation", "Duplicate packages also change rounds or match length; work ratios not exactly 1.",
         "Reported scheduled and played work ratios; mechanism given only as a diagnostic.", "\"operational package comparison\"; no isolated duplication effect."),
        ("Residual crowded-cutoff reference ambiguity", "Reference top 6 below the three leaders is unsettled; a bot outside the designed sets has P(reference top 6) 0.208 at the 500-round ceiling.",
         "Propagated reference uncertainty, clear-error counts, and agreement with mu_swiss.", "Treat the crowded-cutoff reference boundary as uncertain; rely on rerun metrics and clear errors there."),
        ("Post-hoc clarification of matrix clause 2", f"Decided after matrix data were seen; under the broad reading {n_broad} of 18 cells would have extended 50 to 100.",
         "Decision recorded before any extension ran; broad-reading verdicts reported as a sensitivity.", "Disclose in methods with the sensitivity verdict."),
        ("Research semantics", "Public-2026-style research semantics are not exact historical production settings, nor any future FullHouse rules.",
         "Semantics fixed and documented; historical provenance separated from the research baseline.", "No statement about historical results or future competition formats."),
        ("Runtime measurement", "Wall-clock and CPU ratios are distorted by machine throttling and sleep.",
         "Work measured in scheduled and played hands.", "Report hands; CPU ratios indicative only."),
    ]
    return [{"priority": i, "limitation": a, "impact": b, "mitigation": c, "statement": d} for i, (a, b, c, d) in enumerate(L, 1)]


# ---------------------------------------------------------------------------------------- summaries


def executive(D, X, chg_rng, wrong_rng, lead_p, exact, n_pool, C, FZ, agree, pf_mean):
    q = ("quarter_rounds_4x_hands", "baseline")
    return [
        "**Question.** How should a finite simulation budget be allocated so that a Swiss tournament reliably identifies the strongest poker bots (top 6 of 60, NLHE6)?",
        "**Design.** Three controlled fields (engineered separated control, crowded cutoff, style diverse); two independent references (mu_field reference from matched duplicate random partitions; mu_swiss reference from 200 adaptive tournaments); four experiments (A rounds, B equal scheduled hand budget, C source-schedule counterfactual, D operational package comparison); 900 matrix tournaments; preregistered extension rules applied, with one post-hoc clarification disclosed (matrix clause 2); simulation frozen.",
        f"**Baseline.** At 40 x 400, independent reruns disagreed on {chg_rng} of 6 qualifiers and {wrong_rng} selected bots were outside the mu_field reference top 6. In the engineered separated control, validated leaders qualified with probability {min(lead_p):.2f} to {max(lead_p):.2f}; the exact top 6 was selected in {exact} of {n_pool} tournaments.",
        "**Rounds.** Every reliability metric improved at every step from 5 to 40 rounds in all three fields, with no evidence of a plateau within the preregistered 40-round horizon.",
        "**Rounds vs match length.** At an equal scheduled hand budget, ten 1,600-hand rounds were worse than forty 400-hand rounds in all three fields (changed qualifiers " + ", ".join(C('B', f, 'changed_qualifiers', *q) for f in FIELDS) + "); twenty 800-hand rounds were close to forty.",
        "**Adaptive pairing.** Adaptive Swiss beat a frozen replay of its own schedule on rerun changed qualifiers in all three fields (" + ", ".join(FZ(f, 'changed_qualifiers') for f in FIELDS) + ").",
        "**Duplicate packages.** The short-match duplicate package raised rerun rank correlation in all three fields; qualifier contrasts were consistently negative but individually clear only in the separated control. The fewer-rounds package helped only in the crowded cutoff.",
        f"**Errors and references.** Most wrong qualifiers were clearly weaker bots ({', '.join(f'{X[f]['share_wrong_clearly_outside']:.0%}' for f in FIELDS)}). Reference uncertainty was small next to tournament noise, and the two references agreed (Spearman {min(a['spearman_rho'] for a in agree.values()):.2f} to {max(a['spearman_rho'] for a in agree.values()):.2f}).",
        "**Scope.** One frozen field per scenario, synthetic stateless agents, research semantics, 40-round horizon; no regime-level or future-format claims.",
    ]


def methods_summary(D, whw):
    return [
        "**Mechanism.** NLHE6, N = 60, K = 6, adaptive Swiss, persistent-stack matches scored by raw chip delta, public tiebreaks; public-2026-style research semantics; engine `" + ENGINE + "`.",
        "**Fields.** separated_control `0b30004f650324e5` (engineered; one-shot validation on 4,000 fresh pool rounds), crowded_cutoff `afbffedfc3706d84`, style_diverse `ad7d6596ef1c8c3e`; one frozen field per scenario.",
        "**mu_field reference.** Matched 6-lane whole-match duplicate random partitions, cyclic seats, common chance streams, independent seed family; 250 / 500 / 500 matched rounds; analytic SE; joint round bootstrap (unit = one matched round).",
        "**mu_swiss reference.** 200 complete 40 x 400 adaptive tournaments per field in a separate namespace.",
        "**Matrix.** Six unique cells per field x 50 tournaments: R40H400 adaptive (baseline; A prefixes 5/10/20/30/40), R20H800 and R10H1600 (B), frozen replay J = 1 (C), R7H400x6 and R40H67x6 duplicate (D).",
        "**Metrics.** Primary: rerun changed qualifiers; wrong qualifiers and qualification regret vs the mu_field reference. Supporting: overlap, rank correlations, boundary strength loss, mu_swiss-based metrics, reference-propagated intervals, self-regret, clear errors, per-bot P(qualify).",
        "**Inference.** Tournament bootstrap for levels; paired bootstrap on shared replicate ids for contrasts (by source tournament in C); Wilson for proportions; 95% throughout.",
        f"**Extension rules (preregistered).** mu_field per field kind (250 to 500 ceiling); matrix half-width > 0.30 or pair-specific rerun changed-qualifier contrast spanning +/-0.25 (regret report-only); mu_swiss Wilson half-width > 0.08 in [0.10, 0.90] (100 to 200 ceiling; at 200 max possible {whw['crowded_cutoff']:.3f}).",
        "**Integrity.** Identity hashes, append-only resumable runs, digest verification, zero-sum and seating checks, exact replays, HOLD and simulation-freeze guards.",
        "**Not run.** Horizons beyond 40 rounds; matrix 50 to 100; references beyond their ceilings; second field-construction attempts.",
    ]


def results_summary(D, X, C, FZ, MP, sw_chg, sw_wrong, lead_p, exact, n_pool, last_step, agree):
    b = D["base"]
    q, h = ("quarter_rounds_4x_hands", "baseline"), ("half_rounds_2x_hands", "baseline")
    s_ = ("dup_shorter_matches", "ordinary")
    return [
        "**Baseline (rerun changed / wrong vs mu_field / regret BB):** " + "; ".join(f"{FL[f]} {v_(b[f], 'changed_qualifiers')} / {v_(b[f], 'mu_field_reference_changed')} / {v_(b[f], 'mu_field_qualification_regret', 1)}" for f in FIELDS) + ".",
        "**mu_swiss 200 replication (changed / wrong):** " + "; ".join(f"{FL[f]} {ci(*sw_chg[f])} / {ci(*sw_wrong[f])}" for f in FIELDS) + ".",
        f"**Separated control leaders:** P(qualify) {min(lead_p):.2f} to {max(lead_p):.2f}; exact top 6 in {exact}/{n_pool}.",
        "**A (wrong vs mu_field, R5 to R40):** " + "; ".join(f"{FL[f]} {num(D['sweep'][(f, 5)]['mu_field_reference_changed_value']):.2f} to {num(D['sweep'][(f, 40)]['mu_field_reference_changed_value']):.2f}" for f in FIELDS) + "; monotone in every metric.",
        "**B R10H1600 minus R40H400 (changed / regret):** " + "; ".join(f"{FL[f]} {C('B', f, 'changed_qualifiers', *q)} / {C('B', f, 'mu_field_qualification_regret', *q, 1)}" for f in FIELDS) + ".",
        "**B R20H800 minus R40H400 (changed / regret):** " + "; ".join(f"{FL[f]} {C('B', f, 'changed_qualifiers', *h)} / {C('B', f, 'mu_field_qualification_regret', *h, 1)}" for f in FIELDS) + ".",
        "**B matched played hands, R10 regret:** " + "; ".join(f"{FL[f]} {MP(f, 'quarter', 'regret', 1)}" for f in FIELDS) + " (post hoc).",
        "**C adaptive minus frozen (changed / regret):** " + "; ".join(f"{FL[f]} {FZ(f, 'changed_qualifiers')} / {FZ(f, 'mu_field_qualification_regret', 1)}" for f in FIELDS) + ".",
        "**D R40H67x6 minus ordinary (changed / regret):** " + "; ".join(f"{FL[f]} {C('D', f, 'changed_qualifiers', *s_)} / {C('D', f, 'mu_field_qualification_regret', *s_, 1)}" for f in FIELDS) + ".",
        "**D R7H400x6 minus ordinary (changed):** " + "; ".join(f"{FL[f]} {C('D', f, 'changed_qualifiers', 'dup_fewer_rounds', 'ordinary')}" for f in FIELDS) + ".",
        "**Error severity:** clearly-outside share " + ", ".join(f"{X[f]['share_wrong_clearly_outside']:.2f}" for f in FIELDS) + "; cost per wrong qualifier " + ", ".join(f"{X[f]['mean_regret_per_wrong_qualifier_bb']:.1f}" for f in FIELDS) + " BB.",
        "**References:** Spearman mu_field vs mu_swiss " + ", ".join(f"{agree[f]['spearman_rho']:.3f}" for f in FIELDS) + "; self-regret (median [2.5, 97.5]) " + ", ".join(SR(D, f) for f in FIELDS) + " BB.",
    ]


# -------------------------------------------------------------------------------------- claims ledger


def claims(D, X, C, Craw, FZ, FZraw, MP, chg_rng, wrong_rng, sw_chg, sw_wrong, lead_p, exact, n_pool, agree, pf_mean):
    b = D["base"]
    q, h = ("quarter_rounds_4x_hands", "baseline"), ("half_rounds_2x_hands", "baseline")
    s_ = ("dup_shorter_matches", "ordinary")
    # guards: each strong claim's premise is checked against the data
    assert all(Craw("B", f, m, *q)[1] > 0 for f in FIELDS for m in ("changed_qualifiers", "mu_field_qualification_regret"))
    assert all(FZraw(f, "changed_qualifiers")[2] < 0 and FZraw(f, "spearman_rho")[1] > 0 for f in FIELDS)
    assert all(X[f]["share_wrong_clearly_outside"] >= 0.75 for f in FIELDS)
    assert all(a["spearman_rho"] > 0.95 and not a["significant_discordant_pairs"] for a in agree.values())
    R = []

    def add(tier, claim, reason, evidence):
        R.append({"id": f"{tier[0].upper()}{sum(r['tier'] == tier for r in R) + 1}", "tier": tier, "claim": claim,
                  "reason": reason, "evidence": evidence})

    add("strong", f"At R40H400, independent reruns disagree on {chg_rng} of 6 qualifiers in these controlled fields.",
        "Tight intervals in all three fields; replicated by the independent 200-tournament mu_swiss sample.", "Table 2; 2.1; 2.6; Card F1")
    add("strong", f"{wrong_rng} of the selected six are outside the mu_field reference top 6 at R40H400.",
        "All fields; consistent against mu_swiss reference; robust to reference propagation.", "Table 2; Card F1, F7")
    add("strong", f"In the engineered separated control, each validated leader qualifies with probability {min(lead_p):.2f} to {max(lead_p):.2f}, and the exact top 6 was selected in {exact} of {n_pool} tournaments.",
        "Wilson intervals from 200 tournaments; leaders independently validated.", "Figure 5a; Table A1; Card F1")
    add("strong", "Reliability improves continuously with rounds, with no evidence of a plateau within the preregistered 40-round horizon.",
        "Monotone at every step on every metric in every field.", "Figure 1; 2.2; Card F2")
    add("strong", "At an equal scheduled hand budget, ten 1,600-hand rounds select less reliably than forty 400-hand rounds in all three controlled fields.",
        "Paired contrasts exclude zero on rerun changed qualifiers and regret in every field.", "Figure 2; Table 3; Card F3")
    add("strong", "In the source-schedule counterfactual, adaptive Swiss is more consistent than a frozen replay of its own schedule in all three controlled fields.",
        "Changed-qualifier and rerun rank-correlation contrasts exclude zero in every field.", "Figure 3; Table 3; Card F4")
    add("strong", "Most wrong qualifiers are bots the mu_field reference clearly places outside the top 6.",
        "Shares " + ", ".join(f"{X[f]['share_wrong_clearly_outside']:.2f}" for f in FIELDS) + "; regret tracks wrong count (r " + ", ".join(f"{X[f]['corr_wrong_count_vs_regret']:.2f}" for f in FIELDS) + ").",
        "Figure S1; Card F6")
    add("strong", "Reference uncertainty is small relative to tournament noise, and the mu_field and mu_swiss references order the bots almost identically.",
        "Self-regret median <= " + f"{max(selfreg(D, f)[0] for f in FIELDS):.1f}" + " BB (97.5 percentile <= " + f"{max(selfreg(D, f)[2] for f in FIELDS):.1f}" + ") vs tournament regret >= " + f"{min(num(b[f]['mu_field_qualification_regret_value']) for f in FIELDS):.0f}" + " BB; Spearman >= " + f"{min(a['spearman_rho'] for a in agree.values()):.2f}" + "; no significant discordant pairs.",
        "Section 6; Table 4; Card F7")
    add("qualified", "Twenty 800-hand rounds perform close to forty 400-hand rounds.",
        "Intervals include zero except style_diverse changed qualifiers (" + C("B", "style_diverse", "changed_qualifiers", *h) + "); absence of difference is not equivalence.", "Table 3; 4.2")
    add("qualified", "Part of the R10H1600 deficit persists at matched played hands.",
        "Holds in separated_control (both metrics) and style_diverse (regret, wrong vs mu_field); inconclusive in crowded_cutoff; post hoc descriptive.", "2.3; 4.3; Figure 2 last rows")
    add("qualified", "Adaptive pairing reduces regret relative to the frozen replay.",
        "Clear in separated_control and crowded_cutoff; style_diverse regret " + FZ("style_diverse", "mu_field_qualification_regret", 1) + " includes zero.", "Figure 3b; 4.7")
    add("qualified", "The short-match six-lane duplicate package is more consistent than ordinary play.",
        "Rerun Spearman higher in all three fields; changed-qualifier and regret contrasts negative everywhere but individually clear only in separated_control; package comparison.", "Figure 4; 4.4")
    add("qualified", "The fewer-rounds six-lane duplicate package helps in the crowded-cutoff field.",
        "Only that field (" + C("D", "crowded_cutoff", "changed_qualifiers", "dup_fewer_rounds", "ordinary") + "); not in the other two.", "Table 3; Figure 4")
    add("qualified", "Duplication helps only when lanes stay coupled (short matches).",
        "Mechanistic reading consistent with bust rates and played-hand ratios; not tested directly.", "4.8; Figure 4 caption")
    add("qualified", "Tournament noise per bot is about as large as the between-bot strength spread inside Swiss.",
        "Descriptive approximation in this dossier (Section 4.11); not a preregistered analysis.", "derived_checks.json")
    add("qualified", "The separated control has the costliest errors.",
        "True for regret per wrong qualifier, but driven by its engineered gap; regret is not comparable across fields.", "4.1; 4.6")
    add("avoid", "Swiss is unreliable in general.", "One frozen field per scenario; synthetic agents; research semantics.", "Limitations 1, 2, 9")
    add("avoid", "40 rounds are insufficient in general.", "Only these fields; no external target reliability; no horizon beyond 40.", "Limitations 1, 4")
    add("avoid", "The tournament fails to recover true skill.", "References are mechanism-specific estimands; no true skill ranking exists in the design.", "1.4; Section 6")
    add("avoid", "Compute was held fixed in Experiment B.", f"Only scheduled hands were equal; played fractions {pf_mean['quarter_rounds_4x_hands']:.2f} / {pf_mean['half_rounds_2x_hands']:.2f} / {pf_mean['baseline']:.2f}; runtime throttled.", "2.3; Limitation 10")
    add("avoid", "Adaptive Swiss causally improves selection.", "Experiment C is a source-schedule counterfactual with inherited adaptive schedules and fresh randomness.", "4.7; Limitation 5")
    add("avoid", "Duplication causally reduces variance.", "Experiment D packages also change rounds or match length.", "4.8; Limitation 6")
    add("avoid", "The separated control is representative.", "Engineered from the strongest six plus the 54 weakest pool bots.", "5.1; Limitation 3")
    add("avoid", "R10 is worse at equal played hands everywhere.", "Inconclusive in crowded_cutoff; identity metric inconclusive in style_diverse.", "4.3")
    add("avoid", "Reliability plateaus at some number of rounds, or N more rounds would reach a target.", "No plateau observed and no data beyond 40 rounds.", "Figure 1; Limitation 4")
    add("avoid", "Selection errors are mainly near-equal swaps at the cutoff.", "About four in five (all, in the separated control) are clearly weaker bots.", "Figure S1; 4.5")
    add("avoid", "Crowded fields (or diverse fields) require X rounds.", "No regime-level inference from one field per scenario.", "Limitation 1")
    add("avoid", "Results describe historical FullHouse events or any future competition format.", "Research semantics only; no future-format statements.", "Limitation 9")
    add("avoid", "High-variance styles systematically over-qualify relative to their strength.",
        "Archetype residuals are small and change sign across fields; not analysed as a hypothesis.", "4.10; derived_checks.json")
    add("avoid", "Short duplication significantly improves selection in every field.", "Individually clear only in separated_control on qualifier and regret contrasts.", "4.4")
    return R


# ----------------------------------------------------------------------------------------- timeline


def timeline(D):
    n_broad = sum(c.get("extend_broad_sensitivity", False) for c in D["ext"]["matrix"]["cells"].values())
    sv2 = D["sv2_val"]["criteria"]["p_leaders_are_top6"]["value"]
    scv = D["sc_val"]["criteria"]["p_leaders_are_top6"]["value"]
    PR, BF, PC, DA, PH = ("genuinely pre-registered decision", "bug fix", "protocol clarification", "descriptive analysis",
                          "post-hoc design decision")
    T = [
        ("2026-09-30", "75408be", "Fields and duplicate evaluation protocol frozen; original `spread` field selected from the 96-bot pool calibration for a large rank-6/7 gap (16.8 BB, 2.89 SE).", PR, "pool calibration only", "Defined the original third field.", "configs/fhr3b/fields/retired/spread-selection-bias/README.md"),
        ("2026-10-01", "fec0aed", "Heads-up heuristic role bug fixed; affected NLHE fields revoked and re-frozen (2291f5c).", BF, "no core data", "Fields used in FHR4 are the corrected ones.", "git history"),
        ("2026-10-01", "1e35878", "mu_field estimator fixed before launch: normalised scale, analytic SE, joint round bootstrap, per-lane persistence.", PR, "no reference data", "Defines the mu_field reference.", "docs/fhr3b/FIELD_REFERENCE_PLAN.md"),
        ("2026-10-01", "3226137", "Scope fixed to NLHE6 core: 3 fields, 6 unique cells, 50 tournaments per cell, mu_field 250.", PR, "no core data", "Defines the study.", "paper/FHR3B_SCOPE.md"),
        ("2026-10-01", "c488026", "Methodology hardening: analysis plan, metrics (incl. regret), reference uncertainty, B/C/D wording, extension rules.", PR, "no core data", "Defines metrics and rules.", "docs/fhr3b/FHR4_CORE.md"),
        ("2026-10-01", "28c4207", "Pre-launch rule correction: mu_swiss threshold 0.08; regret never triggers an extension; crowded \"outside\" = outside both designed sets.", PC, "no core data", "Rules as applied.", "configs/fhr3b/matrix.yaml"),
        ("2026-10-02", "b872c16", "mu_field references at 250 rounds; the preregistered rule fires in spread, crowded_cutoff and style_diverse (EXTEND_TO_500).", PR, "yes (reference data)", "Crowded and style extended to 500.", "reports/fhr3b/field-calibration/nlhe6/MU_FIELD_AUDIT.md"),
        ("2026-10-02", "b872c16", "Selection bias discovered: spread's 16.8 BB pool gap measured 0.71 BB by the field-relative mu_field reference (regression to the mean from selecting on noisy estimates).", DA, "yes", "Spread placed on HOLD.", "MU_FIELD_AUDIT.md; retired README"),
        ("2026-10-02", "c425a5f", "spread retired (held, provenance kept); spread_v2 split-sample protocol pre-registered (select on even pool rounds, validate once on odd rounds, no second attempt).", PH, "yes (spread reference)", "Replaced the third field.", "configs/fhr3b/fields/retired/; SPREAD_V2_REPORT.md"),
        ("2026-10-02", "d01d551", "spread_v2 candidate selected on the selection half only (not frozen).", PR, "selection half only", "-", "spread_v2/selection.json"),
        ("2026-10-02", "9e321ca", f"spread_v2 held-out validation FAILED (P(leaders are top 6) {sv2:.3f} vs 0.95 required); stopped, no re-selection.", PR, "held-out half", "No spread-type field from this split.", "spread_v2/validation.json"),
        ("2026-10-02", "64a90e6", "separated_control construction and one-shot validation protocol pre-registered.", PH, "yes (2,000 pool rounds used for construction)", "Defined the replacement field.", "docs/fhr3b/FHR4_CORE.md"),
        ("2026-10-02", "d7568e8", "separated_control candidate `0b30004f650324e5` built once and bound to the validation protocol before any validation round.", PR, "construction data only", "-", "separated_control/construction.json, binding.json"),
        ("2026-10-03", "bd732e3", f"One-shot validation on 4,000 fresh pool-style rounds PASSED (P(leaders are top 6) {scv:.3f}).", PR, "fresh data", "Field frozen.", "separated_control/validation.json"),
        ("2026-10-03", "9171b2c", "separated_control frozen into the core; crowded_cutoff and style_diverse mu_field references extended to 500; crowded still fires at the ceiling (carried as uncertainty), style locks.", PR, "yes", "Final references for two fields.", "FHR4_CORE.md section 6c"),
        ("2026-10-04", "d7db218", "Independent separated_control mu_field reference (250 matched rounds; seed family `fhr3b-2026-spread-v2`, prepared for a spread_v2 reference that was never run, assigned in the protocol before validation); rule does not fire; locked.", PR, "yes", "Final reference for separated control.", "nlhe6-separated_control/reference.json"),
        ("2026-10-05", "dce170d", "Matrix complete: 18 cells x 50 = 900 tournaments verified; audit, including matched-played-hands comparison (descriptive).", PR, "yes", "All A to D results.", "MATRIX_AUDIT.md; audit_extra.json"),
        ("2026-10-05", "931d942", "Extension contrasts paired per pair of cells (previously over the intersection of all three cells); all three pairs within B and D now reported.", BF, "yes", "Changed some contrast intervals; definitions unchanged.", "MATRIX_AUDIT.md"),
        ("2026-10-05", "931d942", f"Clause 2 clarified: rerun changed qualifiers govern the matrix rule; wrong-vs-reference contrasts become a sensitivity. Under the broad reading {n_broad} cells would have extended 50 to 100.", PC, "yes (matrix results)", "Original audit (dce170d) said EXTEND_TO_100 for these 4 cells; final verdict 18/18 LOCK_AT_50.", "MATRIX_AUDIT.md; summary.json extension_rules"),
        ("2026-10-05", "931d942", "Horizon confirmed: Experiment A stays at 5 to 40 rounds; 60/80/120 dropped from FHR4 (future, separately preregistered).", PC, "yes", "No horizon extension.", "configs/fhr3b/matrix.yaml"),
        ("2026-10-05", "9f72e79", "mu_swiss 100-tournament report; preregistered rule fires in all three fields (half-widths 0.080 to 0.096).", PR, "yes", "mu_swiss extended to 200.", "git 9f72e79"),
        ("2026-10-05", FREEZE, "mu_swiss complete at 200 per field (ceiling); audited; SIMULATION FREEZE (publication commands refuse to run).", PR, "yes", "Final inventory.", "MU_SWISS_AUDIT.md; matrix.yaml simulation_freeze"),
        ("2026-10-05", PACKAGE, "Publication package: per-tournament error export (clear-outside shares, cost per wrong qualifier); Figure 2 played-hand labels corrected; Figure 4 panel b set to rerun Spearman after results were seen.", DA, "yes", "Presentation and descriptive analyses only.", "paper/fhr4/"),
        ("2026-10-05", "", "This dossier: noise-vs-spread consistency check, rank displacement between references, Table 4 and Table A1.", DA, "yes", "Descriptive only.", "paper/fhr4/dossier/"),
        ("2026-10-05", "", "Dossier cleanup: reference_self_regret reported as bootstrap median with its percentile interval (was bootstrap mean with a percentile interval, incoherent in separated_control); recomputed read-only from the same resamples.", BF, "yes", "Reporting only; stored analysis outputs and all other numbers unchanged.", "scripts/fhr4_export_self_regret.py; exports/reference_self_regret.csv"),
    ]
    return [{"date": a, "commit": b, "event": c, "classification": d, "data_seen": e, "effect": f, "record": g}
            for a, b, c, d, e, f, g in T]


def dof_points(D):
    n_broad = sum(c.get("extend_broad_sensitivity", False) for c in D["ext"]["matrix"]["cells"].values())
    return [
        "Field replacement (spread to separated_control) was decided after reference data showed selection bias; the replacement was constructed once and validated once on fresh data under a never-used seed family before inclusion.",
        "The spread_v2 attempt failed and was not retried; no further field searches were made.",
        f"Clause 2 was clarified after matrix data were seen; the broad reading would have extended {n_broad} cells (sensitivity verdict reported).",
        "The pair-specific pairing change is a correctness fix; it changed some contrast intervals, not metric definitions.",
        "Figure 4 panel b (Spearman) and the matched-played-hands comparison were chosen or added after results were seen; both are presented as descriptive with the primary contrasts alongside.",
        "All extension rules for references were applied mechanically; ceilings (500 rounds, 200 tournaments) were preregistered and respected.",
        "No simulation outcome was discarded: every stored tournament in the 18 matrix cells and 3 mu_swiss cells is analysed; the retired spread reference is kept unchanged for provenance.",
    ]


# --------------------------------------------------------------------------------------------- main


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(out: Path = OUT) -> dict:
    SHEET.clear()
    INPUTS.clear()
    D = load()
    X = derived(D)
    build_sheet(D)
    text, parts = build_md(D, X)
    out.mkdir(parents=True, exist_ok=True)
    data, tabs = out / "data", out / "tables"
    (out / "RESEARCH_DOSSIER.md").write_text(text)
    write_csv(data / "results_sheet.csv", SHEET)
    write_json(data / "results_sheet.json", SHEET)
    write_csv(data / "claims_ledger.csv", parts["ledger"])
    write_json(data / "claims_ledger.json", parts["ledger"])
    write_csv(data / "provenance_timeline.csv", parts["timeline"])
    write_json(data / "provenance_timeline.json", parts["timeline"])
    write_csv(data / "limitations.csv", parts["limitations"])
    write_csv(data / "figure_index.csv", [dict(r, **{k: v for k, v in e.items() if k not in r})
                                          for r, e in zip(parts["fig_index"], parts["figures"])])
    write_csv(data / "table_index.csv", parts["tab_index"])
    write_json(data / "evidence_cards.json", parts["cards"])
    write_json(data / "field_profiles.json", parts["profiles"])
    write_json(data / "reference_analysis.json", parts["reference"])
    write_json(data / "derived_checks.json", X)
    write_csv(tabs / "table4_final_references.csv", parts["table4"])
    write_csv(tabs / "tableA1_per_bot_qualification.csv", parts["tableA1"])
    outputs = sorted(p for p in out.rglob("*") if p.is_file() and p.name != "MANIFEST.json")
    manifest = {"generator": "scripts/fhr4_dossier.py", "freeze_commit": FREEZE, "package_commit": PACKAGE,
                "engine_source_hash": ENGINE, "simulation_run": False,
                "inputs": {str(p.relative_to(REPO)): sha(p) for p in sorted(INPUTS)},
                "outputs": {str(p.relative_to(out)): sha(p) for p in outputs}}
    write_json(out / "MANIFEST.json", manifest)
    print(f"{out / 'RESEARCH_DOSSIER.md'}: {len(text.splitlines())} lines; sheet {len(SHEET)} rows; "
          f"ledger {len(parts['ledger'])}; timeline {len(parts['timeline'])}")
    return {"text": text, "sheet": SHEET, **parts, "derived": X}


if __name__ == "__main__":
    main()
