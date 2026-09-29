"""Analysis scripts used for the final-corpus synthesis (scripts/final_analysis.py)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import analyze_pilots  # noqa: E402
import final_analysis as fa  # noqa: E402
import integrity_check  # noqa: E402


def _entry(D, allin, potmax=None, stack=100.0, k=6.0, played=12.0, vj=None):
    n = len(D)
    return {"exp": "x", "D": np.asarray(D, float), "block_id": np.arange(n), "played": np.full(n, played),
            "k": np.full(n, k), "allin": np.asarray(allin), "potmax": np.asarray(potmax if potmax is not None else np.zeros(n), float),
            "stack": stack, "bps": 100.0, "vj": vj}


def test_first_existing_prefers_newest_on_disk(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "results" / "old").mkdir(parents=True)
    assert analyze_pilots._first_existing("new", "old") == "old"
    (tmp_path / "results" / "new").mkdir()
    assert analyze_pilots._first_existing("new", "old") == "new"
    assert analyze_pilots._first_existing("a", "b") == "b"  # nothing on disk: last listed


def test_allin_shares_and_decisive_blocks():
    rng = np.random.default_rng(0)
    data = {}
    for i, fmt in enumerate(["f1/6max/100bb", "f2/6max/100bb", "f3/6max/100bb"]):
        for role in ("p1", "p2", "p3"):
            n = 4000
            a = rng.random(n) < 0.05 * (i + 1)
            D = np.where(a, rng.normal(0, 20 + 5 * i, n), rng.normal(0, 1, n))
            D[rng.random(n) < 0.6] = 0.0
            data[(fmt, f"{role}-x")] = _entry(D, a.astype(int), potmax=np.where(a, 200.0, 10.0))
    rows, reg = fa.allin(data)
    r = rows[0]
    e = data[(r["format"], r["pairing_id"])]
    dev2 = (e["D"] - e["D"].mean()) ** 2
    a = e["allin"] > 0
    assert r["share_allin"] == pytest.approx(dev2[a].sum() / dev2.sum())
    assert r["frac_blocks_allin_decisive"] == pytest.approx(np.mean(a & (e["D"] != 0)))
    assert r["share_pot_ge_1stack"] == pytest.approx(r["share_allin"])  # all-in blocks are exactly the 200 BB pots here
    # identity: var = p * m_allin + (1 - p) * m_no_allin
    assert r["var"] == pytest.approx(r["frac_blocks_allin"] * r["mean_dev2_allin"]
                                     + (1 - r["frac_blocks_allin"]) * r["mean_dev2_no_allin"])
    big = e["potmax"] >= e["stack"]
    assert r["share_big_decisive"] == pytest.approx(dev2[big & (e["D"] != 0)].sum() / dev2.sum())
    assert r["share_big_not_allin"] == 0.0 and r["share_allin_not_big"] == 0.0
    assert 0 < r["share_top0.01_by_pot"] <= r["share_top0.05_by_pot"] <= r["share_top0.1_by_pot"] <= 1
    assert set(reg["log_var_decomposition_100bb_big_pot"]) >= {"frequency_term", "magnitude_term"}
    d = reg["log_var_decomposition"]
    assert d["frequency_term"] + d["magnitude_term"] + d["non_allin_term"] == pytest.approx(1.0)


def test_nit_decomposition_sums_to_total():
    rng = np.random.default_rng(1)
    n = 500
    ta = rng.choice([5.0, -25.0, 0.0], size=(n, 6))
    tb = rng.choice([5.0, -25.0, 0.0], size=(n, 6))
    chip = rng.normal(0, 30, n)
    D = chip + ta.sum(1) - tb.sum(1)
    vj = np.array([json.dumps({"nit": {"candidate_transfer_bb": {"A": list(x), "B": list(y)},
                                       "truncated": {"A": 0, "B": 1}}}) for x, y in zip(ta, tb, strict=True)])
    out = fa.nit({("nit/6max/100bb", "p2-x"): _entry(D, np.zeros(n), k=47.5, played=95.0, vj=vj)})["p2-x"]
    assert out["chip"]["mean_block"] + out["transfer"]["mean_block"] == pytest.approx(out["total"]["mean_block"])
    assert out["chip"]["sd"] == pytest.approx(chip.std(ddof=1))
    assert out["truncated_rounds"] == n
    assert out["total"]["mean_bb100"] == pytest.approx(100 * D.mean() / 47.5)


def test_convergence_prefix_is_the_leading_blocks():
    rng = np.random.default_rng(2)
    D = rng.standard_t(4, 60000)
    rows = fa.convergence({("f/6max/100bb", "p1-x"): _entry(D, np.zeros(D.size))})
    r10 = next(r for r in rows if r["pilot_n"] == 10000)
    assert r10["sd_prefix"] == pytest.approx(D[:10000].std(ddof=1))
    assert r10["windows"] == 6
    assert r10["hands_ratio_prefix"] == pytest.approx(r10["hands_1bb100_prefix"] / r10["hands_1bb100_full"])


def _write_corpus(root: Path, exp: str, pid: str, D: list[float]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    d = root / "results" / exp / pid / "blocks"
    d.mkdir(parents=True)
    pq.write_table(pa.table({"config_hash": [exp] * len(D), "pairing_id": [pid] * len(D),
                             "block_id": list(range(len(D))), "D": D}), d / f"blocks_000000000_{len(D):09d}.parquet")


def test_reproduction_check_requires_exact_equality(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_corpus(tmp_path, "old", "p1-x", [0.0, 1.5, -2.0])
    _write_corpus(tmp_path, "new", "p1-x", [0.0, 1.5, -2.0, 7.0])
    (r,) = integrity_check.check_reproduction("new", "old")
    assert r["ok"] and r["common_blocks"] == 3 and r["mismatches"] == 0
    _write_corpus(tmp_path, "bad", "p1-x", [0.0, 1.5 + 1e-12, -2.0])
    (r,) = integrity_check.check_reproduction("bad", "old")
    assert not r["ok"] and r["mismatches"] == 1
