from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import CARD_DEFS_BY_CHARACTER, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestDefectFinalCompletionFoundation:
    def test_cards_instantiate_with_expected_metadata(self):
        all_for_one = CardInstance("AllForOne")
        amplify = CardInstance("Amplify")
        blizzard = CardInstance("Blizzard")
        echo_form = CardInstance("EchoForm")
        static_discharge = CardInstance("StaticDischarge")

        assert all_for_one.rarity == CardRarity.RARE
        assert all_for_one.card_type == CardType.ATTACK
        assert all_for_one.cost == 2
        assert all_for_one.damage == 10

        assert amplify.rarity == CardRarity.RARE
        assert amplify.card_type == CardType.SKILL
        assert amplify.cost == 1
        assert amplify.magic_number == 1
        assert amplify.exhaust is False

        assert blizzard.rarity == CardRarity.UNCOMMON
        assert blizzard.card_type == CardType.ATTACK
        assert blizzard.cost == 1
        assert blizzard.damage == 0
        assert blizzard.magic_number == 2

        assert echo_form.rarity == CardRarity.RARE
        assert echo_form.card_type == CardType.POWER
        assert echo_form.cost == 3
        assert echo_form.is_ethereal is True

        assert static_discharge.rarity == CardRarity.UNCOMMON
        assert static_discharge.card_type == CardType.POWER
        assert static_discharge.cost == 1
        assert static_discharge.magic_number == 1

    def test_upgraded_entries_and_aliases_work(self):
        assert CardInstance("AllForOne", upgraded=True).damage == 14
        assert CardInstance("Amplify", upgraded=True).magic_number == 2
        assert CardInstance("Blizzard", upgraded=True).magic_number == 3
        assert CardInstance("EchoForm", upgraded=True).is_ethereal is False
        assert CardInstance("StaticDischarge", upgraded=True).magic_number == 2

        assert CardInstance("All For One").card_id == "AllForOne"
        assert CardInstance("Echo Form").card_id == "EchoForm"
        assert CardInstance("Static Discharge").card_id == "StaticDischarge"

    def test_reward_pools_include_final_completion_cards(self):
        pools = build_reward_pools("DEFECT")
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}
        rare_ids = {card.id for card in pools[CardRarity.RARE]}

        assert {"Blizzard", "StaticDischarge"} <= uncommon_ids
        assert {"AllForOne", "Amplify", "EchoForm"} <= rare_ids

    def test_reward_generation_can_surface_final_completion_cards(self):
        engine = RunEngine.create("DEFECTFINALCOMPLETION", ascension=0, character_class="DEFECT")
        targets = {"AllForOne", "Amplify", "Blizzard", "EchoForm", "StaticDischarge"}
        seen = False
        for _ in range(120):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in CARD_DEFS_BY_CHARACTER["DEFECT"] for card_id in engine.state.pending_card_reward_cards)
