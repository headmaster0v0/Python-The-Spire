from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import SILENT_ALL_DEFS, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestSilentTurnControlFoundation:
    def test_turn_control_cards_instantiate_with_expected_metadata(self):
        burst = CardInstance("Burst")
        expertise = CardInstance("Expertise")
        outmaneuver = CardInstance("Outmaneuver")
        tools = CardInstance("ToolsOfTheTrade")
        plans = CardInstance("WellLaidPlans")
        wraith_form = CardInstance("WraithForm")

        assert burst.rarity == CardRarity.RARE
        assert burst.card_type == CardType.SKILL
        assert burst.cost == 1
        assert burst.magic_number == 1

        assert expertise.rarity == CardRarity.UNCOMMON
        assert expertise.card_type == CardType.SKILL
        assert expertise.cost == 1
        assert expertise.magic_number == 6

        assert outmaneuver.rarity == CardRarity.COMMON
        assert outmaneuver.card_type == CardType.SKILL
        assert outmaneuver.cost == 1
        assert outmaneuver.magic_number == 2

        assert tools.rarity == CardRarity.RARE
        assert tools.card_type == CardType.POWER
        assert tools.cost == 1
        assert tools.magic_number == 1

        assert plans.rarity == CardRarity.UNCOMMON
        assert plans.card_type == CardType.POWER
        assert plans.cost == 1
        assert plans.magic_number == 1

        assert wraith_form.rarity == CardRarity.RARE
        assert wraith_form.card_type == CardType.POWER
        assert wraith_form.cost == 3
        assert wraith_form.magic_number == 2

    def test_turn_control_upgrade_entries_and_aliases_work(self):
        assert CardInstance("Burst+").magic_number == 2
        assert CardInstance("Expertise+").magic_number == 7
        assert CardInstance("Outmaneuver+").magic_number == 3
        assert CardInstance("ToolsOfTheTrade+").cost == 0
        assert CardInstance("WellLaidPlans+").magic_number == 2
        assert CardInstance("WraithForm+").magic_number == 3

        assert CardInstance("Tools of the Trade").card_id == "ToolsOfTheTrade"
        assert CardInstance("Well Laid Plans").card_id == "WellLaidPlans"
        assert CardInstance("Wraith Form v2").card_id == "WraithForm"

    def test_reward_pools_include_turn_control_cards(self):
        pools = build_reward_pools("SILENT")
        common_ids = {card.id for card in pools[CardRarity.COMMON]}
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}
        rare_ids = {card.id for card in pools[CardRarity.RARE]}

        assert {"Outmaneuver"} <= common_ids
        assert {"Expertise", "WellLaidPlans"} <= uncommon_ids
        assert {"Burst", "ToolsOfTheTrade", "WraithForm"} <= rare_ids

    def test_reward_generation_can_surface_turn_control_cards(self):
        engine = RunEngine.create("SILENTTURNCONTROL", ascension=0, character_class="SILENT")
        targets = {"Burst", "Expertise", "Outmaneuver", "ToolsOfTheTrade", "WellLaidPlans", "WraithForm"}
        seen = False
        for _ in range(80):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in SILENT_ALL_DEFS for card_id in engine.state.pending_card_reward_cards)
