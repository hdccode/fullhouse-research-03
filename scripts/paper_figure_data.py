"""Figure-ready data for the six main-text figures, derived only from frozen outputs.

Usage: .venv/bin/python scripts/paper_figure_data.py  ->  paper/figures/data/F*.csv + SHA256SUMS

Plot specifications are in paper/FIGURES.md. No simulation; each file records its source.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats as sps

FA, R6, R7 = Path("reports/final-analysis"), Path("reports/rq6"), Path("reports/rq7")
OUT = Path("paper/figures/data")
HEADLINE = {"fhr3-aof4-8bb-pilot-v1": "AoF 4-max 8BB", "fhr3-nlhe4-100bb-v2": "NLHE 4-max", "fhr3-nlhe6-100bb-pilot-v1": "NLHE 6-max",
            "fhr3-cp6-100bb-pilot-v1": "Crazy Pineapple", "fhr3-nit6-100bb-pilot-v1": "Nit Game", "fhr3-plo6-100bb-pilot-v1": "PLO",
            "fhr3-bomb6-100bb-pilot-v1": "Bomb Pot"}
BY_LABEL = {"aof/4max/8bb": "AoF 4-max 8BB", "nlhe/4max/100bb": "NLHE 4-max", "nlhe/6max/100bb": "NLHE 6-max", "cp/6max/100bb": "Crazy Pineapple",
            "nit/6max/100bb": "Nit Game", "plo/6max/100bb": "PLO", "bomb/6max/100bb": "Bomb Pot",
            "nlhe/6max/20bb": "NLHE 6-max 20BB", "nlhe/6max/50bb": "NLHE 6-max 50BB"}
ROLES = ("p1", "p2", "p3")


def rows(p: Path) -> list[dict]:
    with p.open() as fh:
        return list(csv.DictReader(fh))


def write(name: str, data: list[dict], source: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open("w", newline="") as fh:
        fh.write(f"# source: {source}\n")
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in data for k in r)))
        w.writeheader()
        w.writerows(data)


def f1() -> None:
    g = defaultdict(list)
    for r in rows(FA / "figures" / "hands_vs_effect.csv"):
        if r["experiment_id"] in HEADLINE and r["pairing_id"][:2] in ROLES:
            g[(HEADLINE[r["experiment_id"]], float(r["delta_bb100"]))].append(int(r["played_hands_power80"]))
    out = [{"format": f, "delta_bb100": d, "median_played_hands": float(np.median(v)), "min_played_hands": min(v),
            "max_played_hands": max(v), "n_pairings": len(v)} for (f, d), v in sorted(g.items())]
    write("F1_hands_vs_effect.csv", out, "reports/final-analysis/figures/hands_vs_effect.csv (played_hands_power80; p1-p3; 7 headline formats)")


def f2() -> None:
    out = []
    for r in rows(FA / "core" / "pilot_table.csv"):
        if r["format"] not in BY_LABEL or r["format"] in ("nlhe/6max/20bb", "nlhe/6max/50bb") or r["pairing_id"][:2] not in ROLES:
            continue
        for metric, col in (("independent blocks", "blocks_1bb100_p80"), ("played hands", "hands_1bb100_p80"),
                                ("wall-clock hours (8 workers, measured)", "wall_h_8w_1bb100_p80")):
                out.append({"format": BY_LABEL[r["format"]], "role": r["pairing_id"][:2], "pairing_id": r["pairing_id"],
                            "metric": metric, "value": float(r[col])})
    rk = json.loads((FA / "ranking.json").read_text())
    for metric, key in (("independent blocks", "blocks"), ("played hands", "hands"), ("wall-clock hours (8 workers, measured)", "wall_h")):
        for f, x in rk["metric"][key]["formats"].items():
            out.append({"format": BY_LABEL[f], "role": "median", "pairing_id": "", "metric": metric, "value": x["median"]})
    write("F2_cost_by_metric.csv", out, "reports/final-analysis/core/pilot_table.csv + reports/final-analysis/ranking.json (1 BB/100, 80% power)")


def f3() -> None:
    out = [{"format": HEADLINE[r["experiment_id"]], "role": r["pairing_id"][:2], "top_fraction": float(r["top_fraction"]),
            "cumulative_share_sq_dev": float(r["cumulative_share_sq_dev"])}
           for r in rows(FA / "figures" / "variance_concentration.csv")
           if r["experiment_id"] in HEADLINE and r["pairing_id"][:2] in ROLES]
    for f in np.logspace(-5, 0, 60):  # Gaussian reference: share of E[z^2] in the top-f |z| tail = f + 2 q phi(q)
        q = sps.norm.isf(f / 2)
        out.append({"format": "Gaussian reference", "role": "", "top_fraction": float(f),
                    "cumulative_share_sq_dev": float(min(1.0, f + 2 * q * sps.norm.pdf(q)))})
    write("F3_variance_concentration.csv", out, "reports/final-analysis/figures/variance_concentration.csv; Gaussian reference analytic")


def f4() -> None:
    out = []
    for r in rows(FA / "allin.csv"):
        if r["format"] in BY_LABEL and r["pairing_id"][:2] in ROLES and not r["format"].startswith("nit"):
            fr = float(r["frac_blocks_pot_ge_1stack"])
            out.append({"format": BY_LABEL[r["format"]], "role": r["pairing_id"][:2],
                        "stack_series": r["format"].startswith("nlhe/6max/"),
                        "frac_blocks_big_pot": fr, "share_sq_dev_big_pot": float(r["share_pot_ge_1stack"]),
                        "mean_sq_dev_per_big_pot_block": float(r["var"]) * float(r["share_pot_ge_1stack"]) / fr if fr > 0 else None,
                        "block_variance": float(r["var"])})
    write("F4a_bigpot_frequency_magnitude.csv", out, "reports/final-analysis/allin.csv (share_pot_ge_1stack, frac_blocks_pot_ge_1stack, var); AoF big pot = >= 8BB")
    st = json.loads((FA / "stack.json").read_text())
    out = []
    for role in ROLES:
        out.append({"role": role, "stack_bb": 100, "sd_ratio_vs_100": 1.0, "ci_lo": 1.0, "ci_hi": 1.0, "blocks_needed_vs_100": 1.0})
        for lab, sb in (("nlhe/6max/50bb", 50), ("nlhe/6max/20bb", 20)):
            x = st[role][lab]
            out.append({"role": role, "stack_bb": sb, "sd_ratio_vs_100": x["sd_ratio_vs_100_common"], "ci_lo": x["sd_ratio_ci"][0],
                        "ci_hi": x["sd_ratio_ci"][1], "blocks_needed_vs_100": x["sample_ratio_vs_100_common"]})
    write("F4b_stack_depth.csv", out, "reports/final-analysis/stack.json (paired, common blocks 0..9,999; bootstrap CIs)")


def f5() -> None:
    lab = {("aof4-8bb", "allin_ev"): "AoF 8BB: all-in EV", ("nlhe6-20bb", "allin_ev"): "NLHE 20BB: all-in EV",
           ("nlhe6-100bb", "allin_ev"): "NLHE 100BB: all-in EV", ("nlhe6-100bb", "mivat"): "NLHE 100BB: MIVAT",
           ("nlhe6-100bb", "aivat"): "NLHE 100BB: AIVAT"}
    out = [{"row": lab[(r["setting"], r["estimator"])], "order": list(lab).index((r["setting"], r["estimator"])), "role": r["pairing_id"][:2],
            "var_ratio": float(r["var_ratio_vs_raw"]), "ci_lo": float(r["var_ratio_ci_lo"]), "ci_hi": float(r["var_ratio_ci_hi"]),
            "sample_efficiency_gain": float(r["ess_multiplier"])}
           for r in rows(R6 / "figures" / "variance_reduction.csv") if (r["setting"], r["estimator"]) in lab]
    write("F5_variance_reduction.csv", sorted(out, key=lambda r: (r["order"], r["role"])), "reports/rq6/figures/variance_reduction.csv")
    pr = json.loads((R6 / "deep" / "rq6_deep.json").read_text())["settings"]["aof4-8bb"]["pairings"]["p1-prodv2-vs-blend10"]["precision"]
    write("F5_inset_aof_p1.csv", [{"estimator": e, "mean_bb100": pr[e]["mean_bb100"], "ci_lo": pr[e]["ci95_bb100"][0], "ci_hi": pr[e]["ci95_bb100"][1],
                                   "z": pr[e]["z"], "n_blocks": 50000} for e in ("raw", "allin_ev")],
          "reports/rq6/deep/rq6_deep.json settings['aof4-8bb'].pairings['p1-prodv2-vs-blend10'].precision")


def f6() -> None:
    names = {"heavy": "NLHE 6-max p1 (heavy)", "moderate": "Crazy Pineapple p2", "mild": "PLO p3", "normal": "Normal", "t3": "Student t3"}
    meth = {"fixed": "fixed-N (one look)", "peek": "naive peeking", "asymp": "confidence sequence"}
    out = [{"group": names[r["distribution"]], "method": meth[r["method"]], "rate": float(r["miscoverage"]),
            "wilson_lo": float(r["wilson_lo"]), "wilson_hi": float(r["wilson_hi"]), "stream": "IID null (2,000 reps)"}
           for r in rows(R7 / "coverage.csv")]
    out += [{"group": "Real orderings of NLHE 6-max p1", "method": meth[r["method"]], "rate": float(r["miscoverage"]),
             "wilson_lo": float(r["wilson_lo"]), "wilson_hi": float(r["wilson_hi"]), "stream": "1,000 permutations (true mean = corpus mean)"}
            for r in rows(R7 / "real_permutations.csv")]
    write("F6a_false_exclusion.csv", out, "reports/rq7/coverage.csv + reports/rq7/real_permutations.csv")
    tr = rows(R7 / "deep" / "trajectory_nlhe6_p2.csv")
    write("F6b_trajectory_nlhe6_p2.csv", [{k: float(v) for k, v in r.items()} for r in tr],
          "reports/rq7/deep/trajectory_nlhe6_p2.csv (BB/100; running mean, t-interval, CS; t*=100k)")
    seq = {r["method"]: r for r in rows(R7 / "real_orderings.csv") if r["experiment_id"] == "fhr3-nlhe6-100bb-pilot-v1" and r["pairing_id"].startswith("p2")}
    pint = json.loads(seq["peek"]["interval_bb100"])
    end = tr[-1]
    write("F6b_markers.csv", [
        {"marker": "naive peeking stop", "blocks": int(seq["peek"]["stopping_time"]), "mean_bb100": sum(pint) / 2, "lo": pint[0], "hi": pint[1]},
        {"marker": "fixed-N single look at 250k", "blocks": 250000, "mean_bb100": float(end["mean_bb100"]), "lo": float(end["t_lo"]), "hi": float(end["t_hi"])},
        {"marker": "confidence sequence at 250k", "blocks": 250000, "mean_bb100": float(end["mean_bb100"]), "lo": float(end["cs_lo"]), "hi": float(end["cs_hi"])},
    ], "reports/rq7/real_orderings.csv (fhr3-nlhe6-100bb-pilot-v1 p2) + trajectory endpoint")


def main() -> None:
    for f in (f1, f2, f3, f4, f5, f6):
        f()
    names = sorted(p.name for p in OUT.glob("F*.csv"))
    (OUT / "SHA256SUMS").write_text("".join(f"{hashlib.sha256((OUT / n).read_bytes()).hexdigest()}  {n}\n" for n in names))
    print(f"wrote {len(names)} files to {OUT}: {', '.join(names)}")


if __name__ == "__main__":
    main()
