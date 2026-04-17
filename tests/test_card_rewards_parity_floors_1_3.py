"""Card reward parity and deterministic regression tests.

There are two complementary checks here:
1. A deterministic synthetic seed regression that locks the current full-pool
   ordering for Ironclad reward generation.
2. Exact offer-set parity against the current primary Java recorder log front.
"""
from __future__ import annotations

import pytest

from sts_py.tools.compare_logs import JavaGameLog
from sts_py.engine.core.rng import RNG
from sts_py.engine.core.seed import seed_string_to_long
from sts_py.engine.content.cards_min import CardRarity
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.rewards.card_rewards_min import (
    RewardGenState,
    character_pools,
    get_reward_cards,
)


SEED_STRING = "1B40C4J3IIYDA"
SEED_LONG = 4452322743548530140

EXPECTED_FLOORS = [
    {"FlameBarrier", "BattleTrance", "IronWave"},
    {"GhostlyArmor", "Clash", "Havoc"},
    {"HeavyBlade", "Havoc", "SearingBlow"},
]


def _simulate_floors_1_3(pools: dict[CardRarity, list]) -> list[set[str]]:
    """Simulate 3 consecutive combat reward generations from seed start.

    At the very start of a run, cardRng counter = 0 and
    cardBlizzRandomizer = 5 (default).
    """
    seed = seed_string_to_long(SEED_STRING)
    assert seed == SEED_LONG

    card_rng = RNG.from_seed(seed, counter=0)
    st = RewardGenState()

    results: list[set[str]] = []
    for _ in range(3):
        card_rng, st, cards = get_reward_cards(card_rng, st, pools, n=3)
        results.append({c.id for c in cards})
    return results


class TestCardRewardParityFloors1to3:
    """Parity tests against autosave truth data."""

    def test_seed_conversion(self):
        assert seed_string_to_long(SEED_STRING) == SEED_LONG

    def test_floors_1_3_exact_set_parity(self):
        """Verify the synthetic seed still reproduces the pinned full-pool sets."""
        pools = build_reward_pools()
        results = _simulate_floors_1_3(pools)
        assert results == EXPECTED_FLOORS

    def test_rng_counter_advances_correctly(self):
        """Verify RNG counter advances as expected across 3 floors.

        Per floor (no dupes, upgraded_chance=0):
          - 1 call for rollRarity (random_int(99))
          - 1 call for pick_card (random_int(pool_size-1))
          x3 cards = 6 calls per floor
          + 3 calls for upgrade check (randomBoolean for non-rare)
          = 9 calls per floor (if no rare rolled and no dupes)
        """
        seed = seed_string_to_long(SEED_STRING)
        card_rng = RNG.from_seed(seed, counter=0)
        st = RewardGenState()
        pools = build_reward_pools()

        counters = [card_rng.counter]
        for _ in range(3):
            card_rng, st, _ = get_reward_cards(card_rng, st, pools, n=3)
            counters.append(card_rng.counter)

        for i in range(3):
            assert counters[i+1] > counters[i], (
                f"Floor {i+1}: counter didn't advance "
                f"({counters[i]} -> {counters[i+1]})"
            )

    def test_pool_sizes(self):
        """Verify pool sizes match expected counts."""
        pools = build_reward_pools()
        assert len(pools[CardRarity.COMMON]) == 20, f"Common pool: {len(pools[CardRarity.COMMON])}"
        assert len(pools[CardRarity.UNCOMMON]) == 36, f"Uncommon pool: {len(pools[CardRarity.UNCOMMON])}"
        assert len(pools[CardRarity.RARE]) == 16, f"Rare pool: {len(pools[CardRarity.RARE])}"

    def test_primary_log_frontier_exact_offer_sets(self, real_java_log: JavaGameLog):
        """Verify the current primary Java log front is reproduced exactly."""
        rng = RNG.from_seed(real_java_log.seed, counter=0)
        st = RewardGenState()
        pools = character_pools(real_java_log.character)

        for idx, reward in enumerate(real_java_log.card_rewards[:3], start=1):
            rng, st, cards = get_reward_cards(rng, st, pools, n=3)
            actual = {card.id for card in cards}
            expected = {
                reward.card_id.replace(" ", ""),
                *(card_id.replace(" ", "") for card_id in reward.not_picked_card_ids),
            }
            assert actual == expected, f"Floor {idx}: {actual} != {expected}"


def _dump_rng_trace():
    """Not a test — run manually to debug pool order.

    Usage: python -c "from tests.test_card_rewards_parity_floors_1_3 import _dump_rng_trace; _dump_rng_trace()"
    """
    seed = seed_string_to_long(SEED_STRING)
    rng = RNG.from_seed(seed, counter=0)
    pools = build_reward_pools()

    print(f"Seed: {SEED_STRING} = {seed}")
    print(f"Common pool ({len(pools[CardRarity.COMMON])}): "
          f"{[c.id for c in pools[CardRarity.COMMON]]}")
    print(f"Uncommon pool ({len(pools[CardRarity.UNCOMMON])}): "
          f"{[c.id for c in pools[CardRarity.UNCOMMON]]}")
    print(f"Rare pool ({len(pools[CardRarity.RARE])}): "
          f"{[c.id for c in pools[CardRarity.RARE]]}")
    print()

    st = RewardGenState()
    for floor in range(1, 4):
        print(f"--- Floor {floor} (counter={rng.counter}, blizz={st.card_blizz_randomizer}) ---")
        rng, st, cards = get_reward_cards(rng, st, pools, n=3)
        offered = {c.id for c in cards}
        expected = EXPECTED_FLOORS[floor - 1]
        match = "MATCH" if offered == expected else "MISMATCH"
        print(f"  Offered: {[c.id for c in cards]}")
        print(f"  Expected: {expected}")
        print(f"  {match}")
        print(f"  Counter after: {rng.counter}, blizz after: {st.card_blizz_randomizer}")
        print()
