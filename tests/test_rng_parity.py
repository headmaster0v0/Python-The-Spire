from __future__ import annotations

from sts_py.engine.core.rng import RNG


def test_rng_matches_java_wrapper_semantics_smoke():
    # Smoke test for stability: same seed yields same sequence.
    r1 = RNG.from_seed(123)
    r2 = RNG.from_seed(123)

    for _ in range(100):
        r1, a = r1.random_int(999)
        r2, b = r2.random_int(999)
        assert a == b


def test_rng_counter_increments():
    r = RNG.from_seed(1)
    assert r.counter == 0
    r, _ = r.random_int(10)
    assert r.counter == 1
    r, _ = r.random_boolean()
    assert r.counter == 2
