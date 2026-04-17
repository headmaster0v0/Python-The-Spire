from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import SILENT_ALL_DEFS, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestSilentDefensiveUtilityFoundation:
    def test_defensive_utility_cards_instantiate_with_static_metadata(self):
        footwork = CardInstance("Footwork")
        leg_sweep = CardInstance("LegSweep")
        piercing_wail = CardInstance("PiercingWail")
        terror = CardInstance("Terror")
        malaise = CardInstance("Malaise")

        assert footwork.rarity == CardRarity.UNCOMMON
        assert footwork.card_type == CardType.POWER
        assert footwork.cost == 1
        assert footwork.magic_number == 2

        assert leg_sweep.rarity == CardRarity.UNCOMMON
        assert leg_sweep.card_type == CardType.SKILL
        assert leg_sweep.cost == 2
        assert leg_sweep.block == 11
        assert leg_sweep.magic_number == 2

        assert piercing_wail.rarity == CardRarity.COMMON
        assert piercing_wail.card_type == CardType.SKILL
        assert piercing_wail.cost == 1
        assert piercing_wail.magic_number == 6
        assert piercing_wail.exhaust is True

        assert terror.rarity == CardRarity.UNCOMMON
        assert terror.card_type == CardType.SKILL
        assert terror.cost == 1
        assert terror.magic_number == 99
        assert terror.exhaust is True

        assert malaise.rarity == CardRarity.RARE
        assert malaise.card_type == CardType.SKILL
        assert malaise.cost == -1
        assert malaise.magic_number == 0
        assert malaise.exhaust is True

    def test_defensive_utility_upgrade_entries_work(self):
        assert CardInstance("Footwork+").magic_number == 3
        assert CardInstance("LegSweep+").block == 14
        assert CardInstance("PiercingWail+").magic_number == 8
        assert CardInstance("Terror+").cost == 0
        assert CardInstance("Malaise+").magic_number == 1

    def test_silent_reward_pools_include_defensive_utility_cards(self):
        pools = build_reward_pools("SILENT")
        common_ids = {card.id for card in pools[CardRarity.COMMON]}
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}
        rare_ids = {card.id for card in pools[CardRarity.RARE]}

        assert {"PiercingWail"} <= common_ids
        assert {"Footwork", "LegSweep", "Terror"} <= uncommon_ids
        assert {"Malaise"} <= rare_ids

    def test_reward_generation_can_surface_defensive_utility_cards(self):
        engine = RunEngine.create("SILENTDEFENSIVEUTILITY", ascension=0, character_class="SILENT")
        targets = {"Footwork", "LegSweep", "PiercingWail", "Terror", "Malaise"}
        seen = False
        for _ in range(40):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in SILENT_ALL_DEFS for card_id in engine.state.pending_card_reward_cards)
