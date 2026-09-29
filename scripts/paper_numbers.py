"""Extract every paper number from the FROZEN outputs, with its source path and field.

Usage: .venv/bin/python scripts/paper_numbers.py   ->  paper/numbers.json, paper/NUMBERS.md

Reads only reports/final-analysis (core), reports/rq6 (RQ6) and reports/rq7 (RQ7), all
pinned by their MANIFEST.json files. Nothing is simulated. NUMBERS.md is generated, so the
cheat sheet cannot drift from the data.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

FA, R6, R7 = Path("reports/final-analysis"), Path("reports/rq6"), Path("reports/rq7")
HEAD100 = ("nlhe/4max/100bb", "nlhe/6max/100bb", "cp/6max/100bb", "plo/6max/100bb", "bomb/6max/100bb")
ROLES = ("p1", "p2", "p3")
N: list[dict] = []


def rows(p: Path) -> list[dict]:
    with p.open() as fh:
        return list(csv.DictReader(fh))


def add(section: str, key: str, value, display: str, source: str, field: str, note: str = "") -> None:
    N.append({"section": section, "key": key, "value": value, "display": display, "source": source,
              "field": field, "note": note})


def rng(vals, fmt="{:.2f}", mult=1.0):
    return f"{fmt.format(min(vals) * mult)}–{fmt.format(max(vals) * mult)}"


def core() -> None:
    rk = json.loads((FA / "ranking.json").read_text())
    h = rk["metric"]["hands"]
    for f in h["order"]:
        x = h["formats"][f]
        add("core", f"hands_1bb100_median/{f}", x["median"], f"{x['median'] / 1e6:.2f}M [p1–p3 {x['min'] / 1e6:.2f}–{x['max'] / 1e6:.2f}M]",
            "reports/final-analysis/ranking.json", f"metric.hands.formats['{f}'].median|min|max",
            "played hands, 1 BB/100, 80% power, two-sided alpha 0.05; median over p1-p3")
    add("core", "hands_spread_full", h["largest_over_smallest_median"], f"{h['largest_over_smallest_median']:.0f}×",
        "reports/final-analysis/ranking.json", "metric.hands.largest_over_smallest_median", "Bomb / AoF medians")
    add("core", "hands_spread_100bb", h["largest_over_smallest_median_100bb_excl_nit"], f"{h['largest_over_smallest_median_100bb_excl_nit']:.1f}×",
        "reports/final-analysis/ranking.json", "metric.hands.largest_over_smallest_median_100bb_excl_nit", "NLHE4, NLHE6, CP, PLO, Bomb")
    lo, hi = h["within_format_spread_100bb_excl_nit"]
    add("core", "pairing_spread_100bb", [lo, hi], f"{lo:.1f}–{hi:.1f}×", "reports/final-analysis/ranking.json",
        "metric.hands.within_format_spread_100bb_excl_nit", "max/min required hands over p1-p3 within a format")
    b = rk["metric"]["blocks"]
    add("core", "blocks_spread_full", b["largest_over_smallest_median"], f"{b['largest_over_smallest_median']:.0f}×",
        "reports/final-analysis/ranking.json", "metric.blocks.largest_over_smallest_median")
    w = rk["metric"]["wall_h"]
    add("core", "wallclock_spread_full", w["largest_over_smallest_median"], f"{w['largest_over_smallest_median']:.0f}×",
        "reports/final-analysis/ranking.json", "metric.wall_h.largest_over_smallest_median", "implementation- and machine-specific (8 workers)")
    for f in w["order"]:
        add("core", f"wallclock_h_median/{f}", w["formats"][f]["median"], f"{w['formats'][f]['median']:.3g} h",
            "reports/final-analysis/ranking.json", f"metric.wall_h.formats['{f}'].median")
    p = h["pairs"]["nlhe/4max/100bb < nlhe/6max/100bb"]
    add("core", "nlhe6_over_nlhe4_hands", p["ratio_of_medians"], f"{p['ratio_of_medians']:.2f} [{p['ratio_ci'][0]:.2f}, {p['ratio_ci'][1]:.2f}]",
        "reports/final-analysis/ranking.json", "metric.hands.pairs['nlhe/4max/100bb < nlhe/6max/100bb'].ratio_of_medians|ratio_ci",
        "bootstrap CI holds pairings fixed (sampling uncertainty only)")
    pb = rk["metric"]["blocks"]["pairs"]["nlhe/6max/100bb < nlhe/4max/100bb"]
    add("core", "nlhe4_over_nlhe6_blocks", pb["ratio_of_medians"], f"{pb['ratio_of_medians']:.2f} [{pb['ratio_ci'][0]:.2f}, {pb['ratio_ci'][1]:.2f}]",
        "reports/final-analysis/ranking.json", "metric.blocks.pairs['nlhe/6max/100bb < nlhe/4max/100bb']")
    al = [r for r in rows(FA / "allin.csv") if r["format"] in HEAD100 and r["pairing_id"][:2] in ROLES]
    big = [float(r["share_pot_ge_1stack"]) for r in al]
    add("core", "bigpot_share_100bb", [min(big), max(big)], rng(big, "{:.0f}", 100) + "%", "reports/final-analysis/allin.csv",
        "share_pot_ge_1stack (100BB formats, p1-p3)", "share of total squared deviation in blocks with a pot >= one starting stack")
    dec = [float(r["frac_blocks_big_decisive"]) for r in al]
    add("core", "bigpot_decisive_block_frac_100bb", [min(dec), max(dec)], rng(dec, "{:.1f}", 100) + "% of all blocks",
        "reports/final-analysis/allin.csv", "frac_blocks_big_decisive", "blocks that are big-pot AND have D != 0, as a share of ALL blocks")
    ai = [float(r["share_allin"]) for r in al]
    add("core", "allin_share_100bb", [min(ai), max(ai)], rng(ai, "{:.0f}", 100) + "%", "reports/final-analysis/allin.csv", "share_allin")
    plo = [r for r in al if r["format"] == "plo/6max/100bb"]
    add("core", "plo_bigpot_vs_allin", None,
        f"big-pot {rng([float(r['share_pot_ge_1stack']) for r in plo], '{:.0f}', 100)}% vs all-in {rng([float(r['share_allin']) for r in plo], '{:.0f}', 100)}%; "
        f"big-pot-without-all-in blocks {rng([float(r['frac_blocks_big_not_allin']) for r in plo], '{:.1f}', 100)}% carry {rng([float(r['share_big_not_allin']) for r in plo], '{:.0f}', 100)}%",
        "reports/final-analysis/allin.csv", "share_pot_ge_1stack, share_allin, frac_blocks_big_not_allin, share_big_not_allin (plo)")
    ct = [r for r in rows(FA / "core" / "pilot_table.csv") if r["format"] in HEAD100 and r["pairing_id"][:2] in ROLES]
    t1 = [float(r["conc_top0.01"]) for r in ct]
    add("core", "top1pct_share_100bb", [min(t1), max(t1)], rng(t1, "{:.0f}", 100) + "%", "reports/final-analysis/core/pilot_table.csv", "conc_top0.01")
    reg = json.loads((FA / "allin_regression.json").read_text())
    d = reg["log_var_decomposition_100bb_big_pot"]
    add("core", "freq_mag_decomp_100bb", d, f"frequency {d['frequency_term']:.0%}, magnitude {d['magnitude_term']:.0%} of cross-pairing log-variance",
        "reports/final-analysis/allin_regression.json", "log_var_decomposition_100bb_big_pot", "exploratory, 15 pairings, not causal")
    st = json.loads((FA / "stack.json").read_text())
    r20 = [1 / st[r]["nlhe/6max/20bb"]["sample_ratio_vs_100_common"] for r in ROLES]
    r50 = [1 / st[r]["nlhe/6max/50bb"]["sample_ratio_vs_100_common"] for r in ROLES]
    ci20 = [[1 / st[r]["nlhe/6max/20bb"]["sample_ratio_ci"][1], 1 / st[r]["nlhe/6max/20bb"]["sample_ratio_ci"][0]] for r in ROLES]
    ci50 = [[1 / st[r]["nlhe/6max/50bb"]["sample_ratio_ci"][1], 1 / st[r]["nlhe/6max/50bb"]["sample_ratio_ci"][0]] for r in ROLES]
    add("core", "stack_100_vs_20", r20, " / ".join(f"{x:.1f}×" for x in r20) + f" (CIs {min(c[0] for c in ci20):.1f}–{max(c[1] for c in ci20):.1f})",
        "reports/final-analysis/stack.json", "[role]['nlhe/6max/20bb'].sample_ratio_vs_100_common (inverted) + sample_ratio_ci",
        "paired, common blocks 0..9,999; p1/p2/p3")
    add("core", "stack_100_vs_50", r50, " / ".join(f"{x:.1f}×" for x in r50) + f" (CIs {min(c[0] for c in ci50):.1f}–{max(c[1] for c in ci50):.1f})",
        "reports/final-analysis/stack.json", "[role]['nlhe/6max/50bb'].sample_ratio_vs_100_common (inverted)")
    ah = {r["format"]: r for r in rows(FA / "allin.csv") if r["pairing_id"].startswith("p2")}
    add("core", "stack_mechanism_p2", None,
        f"all-in block freq {float(ah['nlhe/6max/100bb']['frac_blocks_allin']):.2f} → {float(ah['nlhe/6max/50bb']['frac_blocks_allin']):.2f} → {float(ah['nlhe/6max/20bb']['frac_blocks_allin']):.2f}; "
        f"sq. dev per all-in block {float(ah['nlhe/6max/100bb']['mean_dev2_allin']):.0f} → {float(ah['nlhe/6max/50bb']['mean_dev2_allin']):.0f} → {float(ah['nlhe/6max/20bb']['mean_dev2_allin']):.0f} (100→50→20BB)",
        "reports/final-analysis/allin.csv", "frac_blocks_allin, mean_dev2_allin (p2)")
    dc = [r for r in rows(FA / "d_collapse.csv") if r["pairing_id"][:2] in ROLES]
    pw = [float(r["empirical_power"]) for r in dc]
    nu = [float(r["null_rejection"]) for r in dc]
    add("core", "fixedN_power_at_analytic_N", [min(pw), max(pw)], rng(pw, "{:.3f}"), "reports/final-analysis/d_collapse.csv",
        "empirical_power (n = 500, 2k, 10k; 27 pairings; 4,000 resamples)", "target 0.80; MC SE 0.006")
    add("core", "fixedN_null_rejection", [min(nu), max(nu)], rng(nu, "{:.3f}"), "reports/final-analysis/d_collapse.csv", "null_rejection")
    cv = [r for r in rows(FA / "convergence.csv") if r["pilot_n"] == "10000"]
    hr = [float(r["hands_ratio_prefix"]) for r in cv]
    wmin = min(float(r["window_hands_ratio_min"]) for r in cv)
    wmax = max(float(r["window_hands_ratio_max"]) for r in cv)
    add("core", "pilot10k_hands_ratio", [min(hr), max(hr)], f"prefix {rng(hr)}×; disjoint windows {wmin:.2f}–{wmax:.2f}×",
        "reports/final-analysis/convergence.csv", "hands_ratio_prefix, window_hands_ratio_min/max (pilot_n = 10000; 18 extended pairings)")
    add("core", "pilot_rule", None, "n ≈ 384(κ+2) blocks for σ within ±5% at 95% (≈ 100(κ+2) at 1 SE)",
        "reports/final-analysis/convergence.csv", "pilot_n_5pct_95 = 1.96²(κ+2)/(4·0.05²)", "delta-method relative SE √((κ+2)/4n); observed/predicted window SD median 1.00")
    nit = json.loads((FA / "nit.json").read_text())
    add("core", "nit_decomposition", None, "; ".join(
        f"{p[:2]} total {v['total']['mean_bb100']:+.1f}, chip {v['chip']['mean_bb100']:+.1f} [{v['chip']['ci_bb100'][0]:+.1f},{v['chip']['ci_bb100'][1]:+.1f}] BB/100"
        for p, v in nit.items()), "reports/final-analysis/nit.json", "[pairing].total|chip.mean_bb100, ci_bb100")


def rq6() -> None:
    s = rows(R6 / "rq6_summary.csv")
    for setting, est in (("nlhe6-100bb", "allin_ev"), ("nlhe6-100bb", "mivat"), ("nlhe6-100bb", "aivat"),
                         ("nlhe6-20bb", "allin_ev"), ("aof4-8bb", "allin_ev")):
        rs = sorted((r for r in s if r["setting"] == setting and r["estimator"] == est), key=lambda r: r["pairing_id"])
        v = sorted(float(r["var_ratio_vs_raw"]) for r in rs)
        med = v[1]
        add("rq6", f"var_ratio/{setting}/{est}", v, f"median {med:.3f} (p1–p3 {v[0]:.3f}–{v[2]:.3f}); gain {1 / med:.2f}×; "
            + "; ".join(f"{r['pairing_id'][:2]} {float(r['var_ratio_vs_raw']):.3f} [{float(r['var_ratio_ci_lo']):.3f},{float(r['var_ratio_ci_hi']):.3f}]" for r in rs),
            "reports/rq6/rq6_summary.csv", f"var_ratio_vs_raw, var_ratio_ci_lo/hi (setting={setting}, estimator={est})",
            "Var(estimator D)/Var(raw D) on the same blocks; paired bootstrap 95% CI; gain = 1/ratio")
        sv = sorted(float(r["pct_hands_saved_1bb100"]) for r in rs)
        add("rq6", f"hands_saved_pct/{setting}/{est}", sv, f"{sv[1]:.1f}% (p1–p3 {sv[0]:.1f}–{sv[2]:.1f}%)",
            "reports/rq6/rq6_summary.csv", "pct_hands_saved_1bb100")
    dj = json.loads((R6 / "deep" / "rq6_deep.json").read_text())
    dr = dj["allin_ev_dose_response"]
    add("rq6", "allin_removed_dose_response", None,
        f"100BB {dr['nlhe6-100bb']['fraction_removed_median']:.0%}, 20BB {dr['nlhe6-20bb']['fraction_removed_median']:.0%}, AoF {dr['aof4-8bb']['fraction_removed_median']:.0%}; "
        f"100BB−20BB median ratio {dr['median_ratio_100bb_minus_20bb']['point']:.2f} [{dr['median_ratio_100bb_minus_20bb']['ci'][0]:.2f}, {dr['median_ratio_100bb_minus_20bb']['ci'][1]:.2f}]",
        "reports/rq6/deep/rq6_deep.json", "allin_ev_dose_response")
    pw = rows(R6 / "deep" / "rq6_pairwise.csv")
    for a, b in (("mivat", "allin_ev"), ("aivat", "mivat")):
        rs = [r for r in pw if r["numerator"] == a and r["denominator"] == b]
        add("rq6", f"increment/{a}_over_{b}", None, "; ".join(
            f"{r['pairing_id'][:2]} {float(r['var_ratio']):.2f} [{float(r['ci_lo']):.2f},{float(r['ci_hi']):.2f}]" for r in rs),
            "reports/rq6/deep/rq6_pairwise.csv", f"var_ratio, ci_lo/hi (numerator={a}, denominator={b})")
    tl = rows(R6 / "deep" / "rq6_tails.csv")
    t100 = [r for r in tl if r["setting"] == "nlhe6-100bb"]
    bs = [float(r["share_sq_dev_in_big_pot_blocks"]) for r in t100 if r["estimator"] != "raw"]
    add("rq6", "tails_100bb_bigpot_share_after_correction", [min(bs), max(bs)], rng(bs, "{:.0f}", 100) + "%",
        "reports/rq6/deep/rq6_tails.csv", "share_sq_dev_in_big_pot_blocks (nlhe6-100bb, corrected estimators)")
    p1 = {r["estimator"]: r for r in t100 if r["pairing_id"].startswith("p1")}
    add("rq6", "tails_100bb_p1_kurtosis", None, " / ".join(f"{e} {float(p1[e]['excess_kurtosis']):.0f}" for e in ("raw", "allin_ev", "mivat", "aivat")),
        "reports/rq6/deep/rq6_tails.csv", "excess_kurtosis (nlhe6-100bb p1)")
    add("rq6", "tails_100bb_p1_top1", None, " / ".join(f"{e} {float(p1[e]['top1pct_share']):.2f}" for e in ("raw", "allin_ev", "mivat", "aivat")),
        "reports/rq6/deep/rq6_tails.csv", "top1pct_share (nlhe6-100bb p1)")
    pr = dj["settings"]["aof4-8bb"]["pairings"]["p1-prodv2-vs-blend10"]["precision"]
    add("rq6", "aof_p1", pr, f"raw {pr['raw']['mean_bb100']:+.2f} [{pr['raw']['ci95_bb100'][0]:+.2f}, {pr['raw']['ci95_bb100'][1]:+.2f}] z={pr['raw']['z']:.2f}; "
        f"all-in EV {pr['allin_ev']['mean_bb100']:+.2f} [{pr['allin_ev']['ci95_bb100'][0]:+.2f}, {pr['allin_ev']['ci95_bb100'][1]:+.2f}] z={pr['allin_ev']['z']:.2f}; "
        f"raw blocks for same SE ≈ {pr['allin_ev']['raw_blocks_for_same_se'] / 1e3:.0f}k (vs 50k)",
        "reports/rq6/deep/rq6_deep.json", "settings['aof4-8bb'].pairings['p1-prodv2-vs-blend10'].precision")
    aofz = [r for r in s if r["setting"] == "aof4-8bb" and r["pairing_id"].startswith("p1") and r["estimator"] == "allin_ev"][0]
    add("rq6", "aof_p1_est_minus_raw_z", float(aofz["mean_diff_z"]), f"{float(aofz['mean_diff_z']):+.2f}", "reports/rq6/rq6_summary.csv",
        "mean_diff_z (aof4-8bb p1 allin_ev)", "the point-estimate shift is within sampling noise")
    bz = max(abs(float(r["mean_diff_z"])) for r in s)
    add("rq6", "max_abs_bias_z", bz, f"{bz:.2f}", "reports/rq6/rq6_summary.csv", "max |mean_diff_z| over all rows", "gate |z| <= 3")
    for k, v in dj["estimator_bench"].items():
        add("rq6", f"slowdown/{k}", v["slowdown"], f"{v['slowdown']:.2f}×", "reports/rq6/deep/rq6_deep.json", f"estimator_bench['{k}'].slowdown",
            "single-process bench, 3 runs x 150-200 blocks")
    ef = rows(R6 / "deep" / "rq6_efficiency.csv")
    for setting, est in (("nlhe6-100bb", "allin_ev"), ("nlhe6-100bb", "mivat"), ("nlhe6-100bb", "aivat"), ("nlhe6-20bb", "allin_ev"), ("aof4-8bb", "allin_ev")):
        v = [float(r["net_wallclock_efficiency"]) for r in ef if r["setting"] == setting and r["estimator"] == est]
        add("rq6", f"net_wallclock/{setting}/{est}", v, rng(v), "reports/rq6/deep/rq6_efficiency.csv", "net_wallclock_efficiency = ESS / slowdown")
    vf = json.loads((R6 / "MANIFEST.json").read_text())["experiments"]["fhr3-nlhe6-100bb-rq6-v1-fittedvf"]["estimator_experiment"]["value_functions"]["aivat"]
    add("rq6", "value_function", vf, f"sha256 {vf['sha256'][:12]}…, training seed {vf['training_root_seed']}, {vf['n_hand_histories']:,} training hands",
        "reports/rq6/MANIFEST.json", "experiments[...fittedvf].estimator_experiment.value_functions.aivat")


def rq7() -> None:
    cov = rows(R7 / "coverage.csv")
    for m in ("fixed", "peek", "asymp"):
        v = {r["distribution"]: r for r in cov if r["method"] == m}
        vals = [float(r["miscoverage"]) for r in v.values()]
        add("rq7", f"null_{m}", vals, rng(vals, "{:.1f}", 100) + "% ; " + "; ".join(
            f"{d} {float(r['miscoverage']) * 100:.2f}% [{float(r['wilson_lo']) * 100:.1f},{float(r['wilson_hi']) * 100:.1f}]" for d, r in v.items()),
            "reports/rq7/coverage.csv", f"miscoverage, wilson_lo/hi (method={m}, min_n=200, 2,000 reps)")
    mn = [r for r in rows(R7 / "min_n_sensitivity.csv") if r["method"] == "peek" and r["min_n"] == "5000"]
    add("rq7", "peek_min5000", [float(r["miscoverage"]) for r in mn], rng([float(r["miscoverage"]) for r in mn], "{:.1f}", 100) + "%",
        "reports/rq7/min_n_sensitivity.csv", "miscoverage (method=peek, min_n=5000)")
    ma = [r for r in rows(R7 / "min_n_sensitivity.csv") if r["method"] == "asymp"]
    add("rq7", "asymp_min_n_invariance", None, "; ".join(sorted({f"{r['distribution']} {float(r['miscoverage']) * 100:.2f}% at min_n {r['min_n']}" for r in ma})),
        "reports/rq7/min_n_sensitivity.csv", "miscoverage (method=asymp)")
    nt = {(r["cell"], r["method"]): r for r in rows(R7 / "deep" / "null_timing.csv")}
    hp = nt[("null-heavy-min200", "peek")]
    add("rq7", "peek_timing_heavy", None,
        f"false-stopped by 1k {float(hp['share_of_reps_first_miss_le_1000']):.0%}, 10k {float(hp['share_of_reps_first_miss_le_10000']):.0%}, "
        f"100k {float(hp['share_of_reps_first_miss_le_100000']):.0%}, 250k {float(hp['share_of_reps_first_miss_le_250000']):.0%}; median first false stop {float(hp['q0.5']):,.0f} blocks",
        "reports/rq7/deep/null_timing.csv", "cell=null-heavy-min200, method=peek")
    med = [float(r["q0.5"]) for (c, m), r in nt.items() if m == "peek" and c.endswith("min200")]
    add("rq7", "peek_median_first_false_stop", med, f"{min(med):,.0f}–{max(med):,.0f} blocks", "reports/rq7/deep/null_timing.csv", "q0.5 (peek, min_n=200 cells)")
    ea = [int(r["earliest_miss"]) for (c, m), r in nt.items() if m == "asymp" and not c.endswith("min50")]
    add("rq7", "asymp_earliest_null_miss", min(ea), f"{min(ea):,} blocks (min_n ≥ 200)", "reports/rq7/deep/null_timing.csv", "earliest_miss (asymp)")
    ws = json.loads((R7 / "deep" / "wrong_sign.json").read_text())
    for m in ("peek", "asymp", "fixed"):
        x = ws[m]
        add("rq7", f"wrong_sign/{m}", x, f"{x['wrong_sign']:,} / {x['decisions']:,} = {x['rate']:.1%} (one-sided 95% upper {x['upper95_one_sided']:.3%})",
            "reports/rq7/deep/wrong_sign.json", m, "pooled over the 10 non-null cells")
    stp = rows(R7 / "stopping.csv")
    pk = [float(r["wrong_decision_rate"]) for r in stp if r["method"] == "peek"]
    add("rq7", "peek_wrong_sign_max_cell", max(pk), f"up to {max(pk):.1%}", "reports/rq7/stopping.csv", "wrong_decision_rate (method=peek)")
    sc = rows(R7 / "deep" / "stopping_cost.csv")
    for tag, nm in (("n25k", "strong (N80 = 25k)"), ("n100k", "weak (N80 = 100k)")):
        cs = [r for r in sc if r["cell"].endswith(tag)]
        pm = [float(r["power_matched_ratio"]) for r in cs]
        md = [float(r["cs_median_over_fixed_n"]) for r in cs]
        bn = [float(r["cs_decision_rate_by_fixed_n"]) for r in cs]
        add("rq7", f"cs_cost/{tag}", None, f"{nm}: power-matched {rng(pm)}× N80; median stop {rng(md)}× N80; CS decided by N80 {rng(bn, '{:.0f}', 100)}%",
            "reports/rq7/deep/stopping_cost.csv", f"power_matched_ratio, cs_median_over_fixed_n, cs_decision_rate_by_fixed_n (cells *{tag})")
    wi = {int(r["checkpoint"]): float(r["inflation"]) for r in rows(R7 / "deep" / "width_inflation.csv") if r["cell"] == "null-heavy-min200"}
    add("rq7", "width_inflation", wi, ", ".join(f"{k // 1000}k {v:.2f}×" for k, v in sorted(wi.items())),
        "reports/rq7/deep/width_inflation.csv", "inflation (identical for every distribution: σ̂ cancels)")
    pe = {r["method"]: r for r in rows(R7 / "real_permutations.csv")}
    add("rq7", "permutations", None,
        f"peek {float(pe['peek']['miscoverage']):.1%} [{float(pe['peek']['wilson_lo']):.1%},{float(pe['peek']['wilson_hi']):.1%}], wrong direction {float(pe['peek']['wrong_decision_rate']):.1%}; "
        f"CS {float(pe['asymp']['miscoverage']):.1%} [{float(pe['asymp']['wilson_lo']):.1%},{float(pe['asymp']['wilson_hi']):.1%}], decisions {float(pe['asymp']['decision_rate']):.1%} (all correct); "
        f"fixed-N at 100k {float(pe['fixed']['miscoverage']):.1%}",
        "reports/rq7/real_permutations.csv", "miscoverage, wilson_lo/hi, wrong_decision_rate, decision_rate", "without replacement: conservative by construction")
    ro = rows(R7 / "deep" / "real_orderings_sign.csv")
    add("rq7", "real_orderings", None,
        f"{len(ro)} streams: peek stopped {sum(1 for r in ro if r['peek_stop'])}, contradicted full-corpus sign {sum(r['peek_contradicts_full_mean_sign'] == 'True' for r in ro)}; "
        f"CS stopped {sum(1 for r in ro if r['asymp_stop'])}, contradicted 0",
        "reports/rq7/deep/real_orderings_sign.csv", "peek_stop, asymp_stop, *_contradicts_full_mean_sign")
    tr = rows(R7 / "deep" / "trajectory_nlhe6_p2.csv")
    at = lambda n: min(tr, key=lambda r: abs(int(r["blocks"]) - n))  # noqa: E731
    seq = {r["method"]: r for r in rows(R7 / "real_orderings.csv") if r["experiment_id"] == "fhr3-nlhe6-100bb-pilot-v1" and r["pairing_id"].startswith("p2")}
    end = at(250000)
    pint = json.loads(seq["peek"]["interval_bb100"])
    add("rq7", "trajectory_nlhe6_p2", None,
        f"peek stops at block {seq['peek']['stopping_time']} ({seq['peek']['decision']}): {sum(pint) / 2:+.1f} BB/100 [{pint[0]:+.1f}, {pint[1]:+.1f}]; "
        f"full 250k: {float(end['mean_bb100']):+.2f} [{float(end['t_lo']):+.2f}, {float(end['t_hi']):+.2f}]; CS final [{float(end['cs_lo']):+.2f}, {float(end['cs_hi']):+.2f}] (never excludes 0)",
        "reports/rq7/real_orderings.csv + reports/rq7/deep/trajectory_nlhe6_p2.csv", "fhr3-nlhe6-100bb-pilot-v1 p2 (peek, asymp); trajectory at 250,000")


def main() -> None:
    core()
    rq6()
    rq7()
    Path("paper").mkdir(exist_ok=True)
    Path("paper/numbers.json").write_text(json.dumps(N, indent=1, default=float) + "\n")
    md = ["# NUMBERS: final values for drafting (generated)", "",
          "Generated by `scripts/paper_numbers.py` from the frozen outputs only. Do not edit by hand;",
          "re-run the script. Verify the sources with `scripts/freeze_manifest.py --verify` and",
          "`scripts/freeze_rq_manifest.py rq6|rq7 --verify`.", ""]
    for sec, title in (("core", "Core"), ("rq6", "RQ6: variance reduction"), ("rq7", "RQ7: sequential inference")):
        md += [f"## {title}", "", "| key | value | source | field | note |", "|---|---|---|---|---|"]
        md += [f"| `{n['key']}` | {n['display']} | `{n['source']}` | {n['field']} | {n['note']} |" for n in N if n["section"] == sec]
        md.append("")
    Path("paper/NUMBERS.md").write_text("\n".join(md))
    print(f"wrote paper/numbers.json and paper/NUMBERS.md ({len(N)} numbers)")


if __name__ == "__main__":
    main()
