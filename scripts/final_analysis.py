"""Final-corpus synthesis (reads Parquet + manifests only; never re-runs poker).

Usage: .venv/bin/python scripts/final_analysis.py [--out reports/final-analysis] [--boot 400]

Complements scripts/analyze_pilots.py (per-pairing table) with:
  convergence.csv      pilot-size windows vs the full corpus: sigma_D, kurtosis,
                       top-1% / top-0.1% concentration and required hands, for the
                       prefix 0..n (the actual pilot when n = 10k) and for every
                       disjoint n-block window (the spread a pilot of that size has)
  ranking.json         median p1-p3 burden per format in blocks / played hands /
                       wall-clock, bootstrap CI of each median, pairing range, and
                       pairwise P(format A needs less than format B)
  allin.csv            per pairing: variance decomposition into blocks with and
                       without an all-in hand (frequency x magnitude), pot-threshold
                       shares, and the D = 0 share
  allin_regression.json  across-pairing log-variance vs log all-in frequency / magnitude
  stack.json           20/50/100BB sigma ratios with paired-bootstrap CIs on the
                       common block ids, implied sample-size ratios, corr(D)
  nit.json             Nit D decomposition: chip-play vs penalty-transfer component
  windows.csv          sigma_D in consecutive 10k windows (stability; Bomb review)
The unit is always the block. Headline summaries use p1-p3; Nit p4 is excluded.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import sys
from pathlib import Path

import numpy as np
import pyarrow.compute as pc
from scipy import stats as sps

from fhr3.analysis.stats import required_blocks, variance_concentration
from fhr3.io.store import read_blocks

sys.path.insert(0, str(Path(__file__).parent))
from analyze_pilots import EXPERIMENTS, aggregate_throughput  # noqa: E402

HEADLINE = ["aof/4max/8bb", "nlhe/4max/100bb", "nlhe/6max/100bb", "cp/6max/100bb", "plo/6max/100bb",
            "bomb/6max/100bb", "nit/6max/100bb"]
STACKS = ["nlhe/6max/20bb", "nlhe/6max/50bb", "nlhe/6max/100bb"]
ROLES = ("p1", "p2", "p3")
Z80 = sps.norm.ppf(0.975) + sps.norm.ppf(0.8)
V1_EXPERIMENTS = {"fhr3-nlhe4-100bb-pilot-v1", "fhr3-nlhe6-20bb-v1", "fhr3-nlhe6-50bb-v1", "fhr3-nlhe6-100bb-pilot-v1"}
COLS = ["config_hash", "pairing_id", "block_id", "valid", "D", "played_hands", "candidate_hands_per_side",
        "allin_hands", "pot_bb_max", "stack_bb"]


def load() -> dict[tuple[str, str], dict]:
    data = {}
    for label, exp in EXPERIMENTS:
        v2 = exp not in V1_EXPERIMENTS
        extra = (["hands_a", "hands_b"] if v2 else []) + (["variant_json"] if label.startswith("nit") else [])
        t = read_blocks(Path("results") / exp, columns=COLS + extra)
        bps = aggregate_throughput(exp)
        for pid in sorted(set(t.column("pairing_id").to_pylist())):
            if pid.startswith("c0-"):
                continue
            tp = t.filter(pc.and_(pc.equal(t.column("pairing_id"), pid), t.column("valid")))
            o = np.argsort(tp.column("block_id").to_numpy())
            col = lambda c: np.asarray(tp.column(c).to_numpy(zero_copy_only=False))[o]  # noqa: E731
            data[(label, pid)] = {
                "exp": exp, "D": col("D").astype(float), "block_id": col("block_id"),
                "played": col("played_hands").astype(float),
                # candidate hands per side: (hands_a + hands_b) / 2, which differs from the seat
                # count only for the Nit Game (variable-length rounds); v1 files lack hands_a/b
                "k": (col("hands_a").astype(float) + col("hands_b").astype(float)) / 2 if v2
                else col("candidate_hands_per_side").astype(float),
                "allin": col("allin_hands"), "potmax": col("pot_bb_max").astype(float),
                "stack": float(tp.column("stack_bb")[0].as_py()), "bps": bps,
                "vj": col("variant_json") if label.startswith("nit") else None,
            }
    return data


def hands_needed(sd: float, k: float, hpb: float, bb100: float = 1.0) -> float:
    return math.ceil(required_blocks(sd, bb100 * k / 100, 0.05, 0.8)) * hpb


def stats_of(D: np.ndarray, k: float, hpb: float) -> dict:
    sd = float(D.std(ddof=1))
    vc = variance_concentration(D, (0.01, 0.001))
    return {"sd": sd, "kurt": float(sps.kurtosis(D)), "top1": vc["0.01"], "top01": vc["0.001"],
            "hands_1bb100": hands_needed(sd, k, hpb)}


def convergence(data: dict) -> list[dict]:
    rows = []
    for (label, pid), d in data.items():
        D, n = d["D"], d["D"].size
        if n < 50000:
            continue
        k, hpb = float(d["k"].mean()), float(d["played"].mean())
        full = stats_of(D, k, hpb)
        for m in (2500, 5000, 10000, 25000):
            pre = stats_of(D[:m], k, hpb)
            w = np.array([D[i:i + m].std(ddof=1) for i in range(0, n - m + 1, m)])
            ratio = (w / full["sd"]) ** 2  # required-sample ratio of a window-sized pilot vs final
            rows.append({
                "format": label, "pairing_id": pid, "n_full": n, "pilot_n": m,
                "sd_full": full["sd"], "sd_prefix": pre["sd"], "sd_prefix_rel_err": pre["sd"] / full["sd"] - 1,
                "kurt_full": full["kurt"], "kurt_prefix": pre["kurt"],
                "top1_full": full["top1"], "top1_prefix": pre["top1"],
                "top01_full": full["top01"], "top01_prefix": pre["top01"],
                "hands_1bb100_full": full["hands_1bb100"], "hands_1bb100_prefix": pre["hands_1bb100"],
                "hands_ratio_prefix": pre["hands_1bb100"] / full["hands_1bb100"],
                "windows": w.size, "window_hands_ratio_min": float(ratio.min()),
                "window_hands_ratio_median": float(np.median(ratio)), "window_hands_ratio_max": float(ratio.max()),
                "window_frac_within_20pct": float(np.mean(np.abs(ratio - 1) <= 0.2)),
                "window_sd_rel_sd": float(w.std(ddof=1) / full["sd"]) if w.size > 1 else float("nan"),
                "delta_method_rel_se": math.sqrt((full["kurt"] + 2) / (4 * m)),
                # blocks for sigma within +-5%: rel SE = sqrt((kappa+2)/(4n)); 1 SE and 95% versions
                "pilot_n_5pct_1se": math.ceil((full["kurt"] + 2) / (4 * 0.05 ** 2)),
                "pilot_n_5pct_95": math.ceil(1.96 ** 2 * (full["kurt"] + 2) / (4 * 0.05 ** 2)),
            })
    return rows


def boot_sds(D: np.ndarray, reps: int, rng: np.random.Generator) -> np.ndarray:
    n, out = D.size, np.empty(reps)
    for i in range(reps):
        out[i] = D[rng.integers(0, n, n)].std(ddof=1)
    return out


def ranking(data: dict, reps: int) -> dict:
    rng = np.random.default_rng(20260930)
    per, boot = {}, {}
    for label in HEADLINE:
        for role in ROLES:
            key = next((kk for kk in data if kk[0] == label and kk[1].startswith(role + "-")), None)
            if key is None:
                continue
            d = data[key]
            k, hpb = float(d["k"].mean()), float(d["played"].mean())
            sd = float(d["D"].std(ddof=1))
            blocks = math.ceil(required_blocks(sd, k / 100, 0.05, 0.8))
            per[(label, role)] = {"pairing_id": key[1], "sd": sd, "blocks": blocks, "hands": blocks * hpb,
                                  "wall_h": blocks / d["bps"] / 3600, "n": int(d["D"].size)}
            sds = boot_sds(d["D"], reps, rng)
            b = (Z80 * sds / (k / 100)) ** 2
            boot[(label, role)] = {"blocks": b, "hands": b * hpb, "wall_h": b / d["bps"] / 3600}
    out = {"metric": {}, "per_pairing": {f"{a}|{r}": v for (a, r), v in per.items()}}
    for metric in ("blocks", "hands", "wall_h"):
        fm = {}
        for label in HEADLINE:
            vals = [per[(label, r)][metric] for r in ROLES if (label, r) in per]
            bm = np.median(np.stack([boot[(label, r)][metric] for r in ROLES if (label, r) in per]), axis=0)
            fm[label] = {"median": float(np.median(vals)), "min": float(min(vals)), "max": float(max(vals)),
                         "pairing_spread": float(max(vals) / min(vals)),
                         "median_ci": [float(np.quantile(bm, 0.025)), float(np.quantile(bm, 0.975))], "_b": bm}
        order = sorted(fm, key=lambda x: fm[x]["median"])
        pairs = {}
        for i, a in enumerate(order):
            for b in order[i + 1:]:
                ra, rb = (fm[a]["min"], fm[a]["max"]), (fm[b]["min"], fm[b]["max"])
                rb_ = fm[b]["_b"] / fm[a]["_b"]
                pairs[f"{a} < {b}"] = {
                    "ratio_of_medians": fm[b]["median"] / fm[a]["median"],
                    # sampling uncertainty only (pairings held fixed)
                    "ratio_ci": [float(np.quantile(rb_, 0.025)), float(np.quantile(rb_, 0.975))],
                    "p_boot": float(np.mean(fm[a]["_b"] < fm[b]["_b"])),
                    "pairing_ranges_overlap": bool(ra[1] >= rb[0]),
                    # same-role ordering consistency (p1 vs p1, ...): identical IDs are not
                    # identical perturbations across formats, so this is descriptive only
                    "roles_agreeing": int(sum(per[(a, r)][metric] < per[(b, r)][metric] for r in ROLES
                                              if (a, r) in per and (b, r) in per)),
                }
        for v in fm.values():
            v.pop("_b")
        meds = [fm[x]["median"] for x in order]
        m100 = [fm[x]["median"] for x in order if x.endswith("/100bb") and not x.startswith("nit")]
        m100n = [fm[x]["median"] for x in order if x.endswith("/100bb")]
        s100 = [fm[x]["pairing_spread"] for x in order if x.endswith("/100bb") and not x.startswith("nit")]
        out["metric"][metric] = {"order": order, "formats": fm, "pairs": pairs,
                                 "largest_over_smallest_median": meds[-1] / meds[0],
                                 "largest_over_smallest_median_100bb_excl_nit": max(m100) / min(m100),
                                 "largest_over_smallest_median_100bb_incl_nit": max(m100n) / min(m100n),
                                 "within_format_spread_100bb_excl_nit": [min(s100), max(s100)],
                                 "max_within_format_spread": max(v["pairing_spread"] for v in fm.values()),
                                 "median_within_format_spread": float(np.median([v["pairing_spread"] for v in fm.values()]))}
    return out


def allin(data: dict) -> tuple[list[dict], dict]:
    rows = []
    for (label, pid), d in data.items():
        D, a, pm, stack = d["D"], d["allin"] > 0, d["potmax"], d["stack"]
        dev2 = (D - D.mean()) ** 2
        tot, n = dev2.sum(), D.size
        p = float(a.mean())
        r = {"format": label, "pairing_id": pid, "n": n, "var": float(dev2.mean()),
             "frac_blocks_allin": p, "share_allin": float(dev2[a].sum() / tot),
             "mean_dev2_allin": float(dev2[a].mean()) if a.any() else float("nan"),
             "mean_dev2_no_allin": float(dev2[~a].mean()) if (~a).any() else float("nan"),
             "frac_zero": float(np.mean(D == 0)), "frac_zero_allin_blocks": float(np.mean(D[a] == 0)) if a.any() else float("nan"),
             "allin_hands_per_hand": float(d["allin"].sum() / d["played"].sum()),
             "mean_abs_D_nonzero": float(np.abs(D[D != 0]).mean()) if (D != 0).any() else float("nan"),
             "rms_D_nonzero": float(np.sqrt((D[D != 0] ** 2).mean())) if (D != 0).any() else float("nan")}
        dec = a & (D != 0)
        r["frac_blocks_allin_decisive"] = float(dec.mean())
        r["share_allin_decisive"] = float(dev2[dec].sum() / tot)
        # top-1% blocks: how many contain an all-in hand
        top = np.argsort(dev2)[::-1][: max(1, n // 100)]
        r["top1pct_blocks_with_allin"] = float(a[top].mean())
        big = pm > stack - 1e-9  # a pot of at least one starting stack
        r["frac_blocks_big_decisive"] = float(np.mean(big & (D != 0)))
        r["share_big_decisive"] = float(dev2[big & (D != 0)].sum() / tot)
        r["frac_blocks_big_not_allin"] = float(np.mean(big & ~a))
        r["share_big_not_allin"] = float(dev2[big & ~a].sum() / tot)
        r["frac_blocks_allin_not_big"] = float(np.mean(a & ~big))
        r["share_allin_not_big"] = float(dev2[a & ~big].sum() / tot)
        r["mean_dev2_big"] = float(dev2[big].mean()) if big.any() else float("nan")
        # format-agnostic: share carried by the top-f blocks ranked by largest pot (ties random)
        order = np.lexsort((np.random.default_rng(0).random(n), -pm))
        cum = np.cumsum(dev2[order]) / tot
        for f in (0.01, 0.05, 0.10):
            r[f"share_top{f:g}_by_pot"] = float(cum[max(1, int(f * n)) - 1])
        for name, thr in (("pot_ge_1stack", stack), ("pot_ge_2stack", 2 * stack), ("pot_gt_100bb", 100.0),
                          ("pot_gt_50bb", 50.0)):
            m = pm > thr - 1e-9 if name.endswith("stack") else pm > thr
            r[f"frac_blocks_{name}"] = float(m.mean())
            r[f"share_{name}"] = float(dev2[m].sum() / tot)
        rows.append(r)
    # exploratory across-pairing regression, headline p1-p3 + stack series; not causal
    sel = [r for r in rows if r["pairing_id"][:2] in ROLES and not r["format"].startswith("nit")]
    y = np.log([r["var"] for r in sel])
    X = {"log_frac_blocks_allin": np.log([r["frac_blocks_allin"] for r in sel]),
         "log_mean_dev2_allin": np.log([r["mean_dev2_allin"] for r in sel]),
         "log_rms_D_nonzero": np.log([r["rms_D_nonzero"] for r in sel]),
         "log_frac_nonzero": np.log([1 - r["frac_zero"] for r in sel]),
         "log_allin_per_hand": np.log([r["allin_hands_per_hand"] for r in sel])}
    reg = {"n_pairings": len(sel), "note": "exploratory; excludes Nit (block = ~95 hands); log var_D on each regressor",
           "univariate_r2": {k: float(np.corrcoef(v, y)[0, 1] ** 2) for k, v in X.items()}}
    # identity: var = p*m_allin + (1-p)*m_no; share of cross-pairing log-var variance from each factor
    A = np.column_stack([np.ones(len(sel)), X["log_frac_blocks_allin"], X["log_mean_dev2_allin"]])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    reg["two_factor_fit"] = {"coef": dict(zip(["const", "log_frac_blocks_allin", "log_mean_dev2_allin"], map(float, coef))),
                             "r2": float(1 - ((y - A @ coef) ** 2).sum() / ((y - y.mean()) ** 2).sum())}
    # log var = log p + log m_allin - log share_allin (identity); decompose the across-pairing
    # variance of log var into the frequency and magnitude terms (covariances split evenly)
    lp, lm, ls = X["log_frac_blocks_allin"], X["log_mean_dev2_allin"], -np.log([r["share_allin"] for r in sel])
    tot = np.var(y)
    reg["log_var_decomposition"] = {
        "var_log_var": float(tot),
        "frequency_term": float((np.var(lp) + np.cov(lp, lm, ddof=0)[0, 1] + np.cov(lp, ls, ddof=0)[0, 1]) / tot),
        "magnitude_term": float((np.var(lm) + np.cov(lp, lm, ddof=0)[0, 1] + np.cov(lm, ls, ddof=0)[0, 1]) / tot),
        "non_allin_term": float((np.var(ls) + np.cov(lp, ls, ddof=0)[0, 1] + np.cov(lm, ls, ddof=0)[0, 1]) / tot),
        "corr_log_freq_log_magnitude": float(np.corrcoef(lp, lm)[0, 1]),
    }
    # same decomposition within the 100BB formats only (no stack confound), for all-in and big-pot blocks
    s100 = [r for r in sel if r["format"].endswith("/100bb")]
    y1 = np.log([r["var"] for r in s100])
    for tag, pk, mk, sk in (("allin", "frac_blocks_allin", "mean_dev2_allin", "share_allin"),
                            ("big_pot", "frac_blocks_pot_ge_1stack", "mean_dev2_big", "share_pot_ge_1stack")):
        lp1, lm1 = np.log([r[pk] for r in s100]), np.log([r[mk] for r in s100])
        ls1 = -np.log([r[sk] for r in s100])
        t1 = np.var(y1)
        c = lambda u, v: np.cov(u, v, ddof=0)[0, 1]  # noqa: E731
        reg[f"log_var_decomposition_100bb_{tag}"] = {
            "n_pairings": len(s100),
            "frequency_term": float((np.var(lp1) + c(lp1, lm1) + c(lp1, ls1)) / t1),
            "magnitude_term": float((np.var(lm1) + c(lp1, lm1) + c(lm1, ls1)) / t1),
            "residual_term": float((np.var(ls1) + c(lp1, ls1) + c(lm1, ls1)) / t1),
            "r2_frequency": float(np.corrcoef(lp1, y1)[0, 1] ** 2), "r2_magnitude": float(np.corrcoef(lm1, y1)[0, 1] ** 2)}
    return rows, reg


def stack(data: dict, reps: int) -> dict:
    rng = np.random.default_rng(20261001)
    out = {}
    for role in ROLES:
        ser = {lab: data[next(kk for kk in data if kk[0] == lab and kk[1].startswith(role + "-"))] for lab in STACKS}
        n = min(s["D"].size for s in ser.values())
        base = ser["nlhe/6max/100bb"]
        common = {lab: s["D"][:n] for lab, s in ser.items()}  # same block ids 0..n-1, same seeds
        assert all(np.array_equal(s["block_id"][:n], base["block_id"][:n]) for s in ser.values())
        res = {"common_blocks": n, "sd_100bb_full": float(base["D"].std(ddof=1))}
        idx = [rng.integers(0, n, n) for _ in range(reps)]
        for lab in ("nlhe/6max/20bb", "nlhe/6max/50bb"):
            x, y = common[lab], common["nlhe/6max/100bb"]
            r = x.std(ddof=1) / y.std(ddof=1)
            b = np.array([x[i].std(ddof=1) / y[i].std(ddof=1) for i in idx])
            res[lab] = {"sd": float(x.std(ddof=1)), "sd_ratio_vs_100_common": float(r),
                        "sd_ratio_ci": [float(np.quantile(b, 0.025)), float(np.quantile(b, 0.975))],
                        "sd_ratio_vs_100_full": float(x.std(ddof=1) / res["sd_100bb_full"]),
                        "sample_ratio_vs_100_common": float(r ** 2),
                        "sample_ratio_ci": [float(np.quantile(b, 0.025) ** 2), float(np.quantile(b, 0.975) ** 2)],
                        "corr_D_with_100": float(np.corrcoef(x, y)[0, 1]),
                        "kurt": float(sps.kurtosis(x)), "frac_blocks_allin": float(np.mean(ser[lab]["allin"][:n] > 0)),
                        "mean_potmax": float(ser[lab]["potmax"][:n].mean())}
        res["nlhe/6max/100bb"] = {"sd_common": float(common["nlhe/6max/100bb"].std(ddof=1)),
                                  "kurt_common": float(sps.kurtosis(common["nlhe/6max/100bb"])),
                                  "frac_blocks_allin_common": float(np.mean(base["allin"][:n] > 0)),
                                  "mean_potmax_common": float(base["potmax"][:n].mean())}
        x, y = common["nlhe/6max/20bb"], common["nlhe/6max/50bb"]
        res["corr_20_50"] = float(np.corrcoef(x, y)[0, 1])
        out[role] = res
    return out


def nit(data: dict) -> dict:
    out = {}
    for (label, pid), d in data.items():
        if not label.startswith("nit"):
            continue
        tr = np.empty(d["D"].size)
        trunc = 0
        for i, s in enumerate(d["vj"]):
            v = json.loads(s)["nit"]
            tr[i] = sum(v["candidate_transfer_bb"]["A"]) - sum(v["candidate_transfer_bb"]["B"])
            trunc += v["truncated"]["A"] + v["truncated"]["B"]
        D = d["D"]
        chip = D - tr
        k = float(d["k"].mean())
        n = D.size
        f = lambda x: {"mean_block": float(x.mean()), "mean_bb100": float(100 * x.mean() / k),  # noqa: E731
                       "ci_bb100": [float(100 * (x.mean() - 1.96 * x.std(ddof=1) / math.sqrt(n)) / k),
                                    float(100 * (x.mean() + 1.96 * x.std(ddof=1) / math.sqrt(n)) / k)],
                       "sd": float(x.std(ddof=1)), "kurt": float(sps.kurtosis(x))}
        out[pid] = {"n": n, "k_candidate_hands_per_side": k, "hands_per_block": float(d["played"].mean()),
                    "total": f(D), "chip": f(chip), "transfer": f(tr),
                    "corr_chip_transfer": float(np.corrcoef(chip, tr)[0, 1]),
                    "var_share_transfer": float(tr.var() / D.var()), "var_share_chip": float(chip.var() / D.var()),
                    "truncated_rounds": int(trunc)}
    return out


def windows(data: dict, m: int = 10000) -> list[dict]:
    rows = []
    for (label, pid), d in data.items():
        D = d["D"]
        k = float(d["k"].mean())
        for w, i in enumerate(range(0, D.size - m + 1, m)):
            x = D[i:i + m]
            rows.append({"format": label, "pairing_id": pid, "window": w, "start": i, "sd": float(x.std(ddof=1)),
                         "mean_bb100": float(100 * x.mean() / k), "kurt": float(sps.kurtosis(x)),
                         "top1": variance_concentration(x, (0.01,))["0.01"], "max_abs_D": float(np.abs(x).max())})
    return rows


def _csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/final-analysis")
    ap.add_argument("--boot", type=int, default=400)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    data = load()
    _csv(out / "convergence.csv", convergence(data))
    (out / "ranking.json").write_text(json.dumps(ranking(data, a.boot), indent=1))
    rows, reg = allin(data)
    _csv(out / "allin.csv", rows)
    (out / "allin_regression.json").write_text(json.dumps(reg, indent=1))
    (out / "stack.json").write_text(json.dumps(stack(data, a.boot), indent=1))
    (out / "nit.json").write_text(json.dumps(nit(data), indent=1))
    _csv(out / "windows.csv", windows(data))
    print(f"wrote {out}/{{convergence.csv,ranking.json,allin.csv,allin_regression.json,stack.json,nit.json,windows.csv}}")


if __name__ == "__main__":
    main()
