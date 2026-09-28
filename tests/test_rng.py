from fhr3.rng import DecisionRNG, KeyedStream, derive_seed, key_digest


def test_derive_seed_is_stable_across_processes():
    # Golden values: changing these means every persisted result changes.
    # Bump SEED_DERIVATION_VERSION if this test has to be updated.
    assert derive_seed("fhr3-block", 20260928, 0) == GOLDEN_BLOCK0
    assert KeyedStream("chance", 1, 0).random() == GOLDEN_U


def test_key_encoding_is_unambiguous():
    assert key_digest("ab", "c") != key_digest("a", "bc")
    assert key_digest(1, 2) != key_digest(12)
    assert key_digest(1) != key_digest("1")


def test_stream_draws_do_not_depend_on_other_streams():
    a1 = [KeyedStream("x", 1).random() for _ in range(3)]
    s = KeyedStream("x", 1)
    other = KeyedStream("y", 1)
    a2 = []
    for _ in range(3):
        other.random()
        a2.append(s.random())
    assert len(set(a1)) == 1  # fresh stream each time -> first draw repeated
    assert a2[0] == a1[0]


def test_shuffle_is_a_permutation_and_deterministic():
    items = list(range(52))
    p1 = KeyedStream("chance", 7).shuffle(items)
    p2 = KeyedStream("chance", 7).shuffle(items)
    assert p1 == p2 and sorted(p1) == items and p1 != items


def test_randbelow_range_and_rough_uniformity():
    s = KeyedStream("u", 3)
    counts = [0] * 6
    for _ in range(6000):
        counts[s.randbelow(6)] += 1
    assert all(900 < c < 1100 for c in counts)


def test_uniform_range():
    s = DecisionRNG("d", 1)
    xs = [s.random() for _ in range(2000)]
    assert all(0.0 <= x < 1.0 for x in xs)
    assert 0.45 < sum(xs) / len(xs) < 0.55


GOLDEN_BLOCK0 = 3837676063973491089
GOLDEN_U = 0.024386100734386518
