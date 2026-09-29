"""FHR3B reliability metrics on synthetic tournament fixtures with exactly known answers."""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from fhr3.tournament import metrics as mt

N, K = 8, 3


def ranks_from_orders(orders):
    out = np.zeros((len(orders), N), dtype=np.int32)
    for i, o in enumerate(orders):
        for pos, b in enumerate(o):
            out[i, b] = pos + 1
    return out


def test_perfectly_stable_rankings():
    rank = ranks_from_orders([list(range(N))] * 5)
    est = mt.rerun_stability(rank, rank <= K, K, b=50)
    assert est["topk_overlap"].value == K
    assert est["changed_qualifiers"].value == 0
    assert est["jaccard"].value == 1
    assert est["kendall_tau"].value == pytest.approx(1)
    assert est["spearman_rho"].value == pytest.approx(1)
    assert est["mean_abs_rank_diff"].value == 0
    assert est["n_ambiguous_bots"].value == 0
    assert est["p_same_winner"].value == 1
    assert est["topk_overlap"].se == 0


def test_only_cutoff_bots_swap():
    a = list(range(N))
    b = [0, 1, 3, 2, 4, 5, 6, 7]  # ranks 3 and 4 swap -> one changed qualifier
    rank = ranks_from_orders([a, b])
    est = mt.rerun_stability(rank, rank <= K, K, b=20)
    assert est["topk_overlap"].value == K - 1
    assert est["changed_qualifiers"].value == 1
    assert est["jaccard"].value == pytest.approx((K - 1) / (K + 1))
    assert est["kendall_tau"].value == pytest.approx(1 - 2 * 1 / (N * (N - 1) / 2))
    assert est["mean_abs_rank_diff"].value == pytest.approx(2 / N)
    q = mt.qualification_table(rank <= K, [f"b{i}" for i in range(N)])
    assert [r["p_qualify"] for r in q] == [1, 1, 0.5, 0.5, 0, 0, 0, 0]


def test_random_qualification_matches_exact_u_statistic():
    rng = np.random.default_rng(1)
    orders = [list(rng.permutation(N)) for _ in range(40)]
    rank = ranks_from_orders(orders)
    qual = rank <= K
    est = mt.rerun_stability(rank, qual, K, b=20)
    m = len(orders)
    c = qual.sum(0)
    # E[overlap of two independent reruns] = sum_i P(i qualifies)^2, unbiased U-statistic form
    assert est["topk_overlap"].value == pytest.approx((c * (c - 1)).sum() / (m * (m - 1)))
    explicit = np.mean([(qual[i] & qual[j]).sum() for i, j in itertools.combinations(range(m), 2)])
    assert est["topk_overlap"].value == pytest.approx(explicit)


def test_pair_mean_weights_exclude_same_tournament_pairs():
    rng = np.random.default_rng(2)
    mat = rng.normal(size=(5, 5))
    mat = (mat + mat.T) / 2
    w = np.array([2.0, 0, 1, 0, 1])
    # expand the resample explicitly: indices [0, 0, 2, 4]
    idx = [0, 0, 2, 4]
    pairs = [(a, b) for a, b in itertools.permutations(range(len(idx)), 2) if idx[a] != idx[b]]
    explicit = np.mean([mat[idx[a], idx[b]] for a, b in pairs])
    assert mt.pair_mean(mat, w) == pytest.approx(explicit)


def test_known_rank_inversions():
    ref = np.array([8.0, 7, 6, 5, 4, 3, 2, 1])  # bot 0 best
    orders = [list(range(N)), [1, 0, 2, 3, 4, 5, 6, 7], [1, 0, 2, 3, 4, 5, 7, 6], list(range(N))]
    rank = ranks_from_orders(orders)
    rows = {(r["better_bot"], r["worse_bot"]): r for r in mt.pairwise_inversions(rank, ref, None, list(range(N)))}
    assert rows[(0, 1)]["p_inversion"] == 0.5
    assert rows[(6, 7)]["p_inversion"] == 0.25
    assert rows[(0, 7)]["p_inversion"] == 0
    assert len(rows) == N * (N - 1) // 2
    binned = mt.binned_inversions(rank, ref, [0.5, 1.5, 100], b=20)
    # gap-1 pairs: 7 adjacent pairs, inversions (0,1) x2 + (6,7) x1 over 4 tournaments
    assert binned[0]["n_pairs"] == 7 and binned[0]["p_inversion_value"] == pytest.approx(3 / (7 * 4))


def test_cutoff_curve_orders_by_reference():
    ref = np.array([1.0, 3.0, 2.0])
    qual = np.array([[False, True, True], [True, True, False]])
    rows = mt.cutoff_curve(qual, ref, ["a", "b", "c"])
    assert [r["bot_id"] for r in rows] == ["b", "c", "a"]
    assert [r["p_qualify"] for r in rows] == [1.0, 0.5, 0.5]


def test_wilson_interval():
    lo, hi = mt.wilson_interval(np.array([0, 5, 10]), 10)
    assert lo[0] == 0 and hi[2] == pytest.approx(1)
    assert lo[1] == pytest.approx(0.2366, abs=1e-3) and hi[1] == pytest.approx(0.7634, abs=1e-3)


def test_rank_agreement_and_mc_advice():
    assert mt.rank_agreement(np.array([3.0, 2, 1]), np.array([30.0, 20, 10]))["kendall_tau"] == pytest.approx(1)
    assert mt.rank_agreement(np.array([3.0, 2, 1]), np.array([1.0, 2, 3]))["kendall_tau"] == pytest.approx(-1)
    adv = mt.monte_carlo_advice(mt.Estimate(0.5, 0.05, 0.4, 0.6, 100), 0.05)
    assert adv["extension_needed"] and adv["approx_tournaments_for_target"] == 400
