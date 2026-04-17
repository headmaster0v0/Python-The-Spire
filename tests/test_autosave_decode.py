from __future__ import annotations

from sts_py.tools.autosave_decode import load_autosave_json, SaveSeedCounters


def test_load_autosave_extracts_seed_and_counters():
    # This test is intentionally light and does not depend on local machine paths.
    # We just validate the dataclass mapping logic.
    d = {
        "seed": 123,
        "seed_set": True,
        "monster_seed_count": 1,
        "event_seed_count": 2,
        "merchant_seed_count": 3,
        "card_seed_count": 4,
        "treasure_seed_count": 5,
        "relic_seed_count": 6,
        "potion_seed_count": 7,
        "ai_seed_count": 8,
        "shuffle_seed_count": 9,
        "card_random_seed_count": 10,
        "card_random_seed_randomizer": 11,
    }
    c = SaveSeedCounters.from_save(d)
    assert c.seed == 123
    assert c.seed_set is True
    assert c.monster_seed_count == 1
    assert c.card_random_seed_randomizer == 11
