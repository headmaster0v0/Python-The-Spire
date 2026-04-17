from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import SILENT_ALL_DEFS, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestSilentUtilitySetupFoundation:
    def test_utility_setup_cards_instantiate_with_expected_metadata(self):
        distraction = CardInstance("Distraction")
        escape_plan = CardInstance("EscapePlan")
        setup = CardInstance("Setup")
        nightmare = CardInstance("Nightmare")
        doppelganger = CardInstance("Doppelganger")

        assert distraction.rarity == CardRarity.UNCOMMON
        assert distraction.card_type == CardType.SKILL
        assert distraction.cost == 1
        assert distraction.exhaust is True

        assert escape_plan.rarity == CardRarity.UNCOMMON
        assert escape_plan.card_type == CardType.SKILL
        assert escape_plan.cost == 0
        assert escape_plan.block == 3

        assert setup.rarity == CardRarity.UNCOMMON
        assert setup.card_type == CardType.SKILL
        assert setup.cost == 1

        assert nightmare.rarity == CardRarity.RARE
        assert nightmare.card_type == CardType.SKILL
        assert nightmare.cost == 3
        assert nightmare.magic_number == 3
        assert nightmare.exhaust is True

        assert doppelganger.rarity == CardRarity.RARE
        assert doppelganger.card_type == CardType.SKILL
        assert doppelganger.cost == -1
        assert doppelganger.exhaust is True

    def test_utility_setup_upgrade_entries_and_aliases_work(self):
        assert CardInstance("Distraction+").cost == 0
        assert CardInstance("EscapePlan+").block == 5
        assert CardInstance("Setup+").cost == 0
        assert CardInstance("Nightmare+").cost == 2

        assert CardInstance("Escape Plan").card_id == "EscapePlan"
        assert CardInstance("Night Terror").card_id == "Nightmare"

    def test_reward_pools_include_utility_setup_cards(self):
        pools = build_reward_pools("SILENT")
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}
        rare_ids = {card.id for card in pools[CardRarity.RARE]}

        assert {"Distraction", "EscapePlan", "Setup"} <= uncommon_ids
        assert {"Nightmare", "Doppelganger"} <= rare_ids

    def test_reward_generation_can_surface_utility_setup_cards(self):
        engine = RunEngine.create("SILENTUTILITYSETUP", ascension=0, character_class="SILENT")
        targets = {"Distraction", "EscapePlan", "Setup", "Nightmare", "Doppelganger"}
        seen = False
        for _ in range(100):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in SILENT_ALL_DEFS for card_id in engine.state.pending_card_reward_cards)
