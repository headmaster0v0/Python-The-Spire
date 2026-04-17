from __future__ import annotations

from sts_py.engine.run.run_rng import RunRngState, SettingsSeed


def test_generate_seeds_all_streams_start_identical():
    seed = SettingsSeed.from_seed_string("1B40C4J3IIYDA")
    assert seed.seed_set
    assert seed.seed_long is not None

    rr = RunRngState.generate_seeds(seed.seed_long)

    a = rr.monster_rng.random_int(999)
    b = rr.event_rng.random_int(999)
    assert a == b
    
    c = rr.merchant_rng.random_int(999)
    assert a == c
