from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import SILENT_ALL_DEFS, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestSilentShivCardPlayPayoffFoundation:
    def test_payoff_cards_instantiate_with_static_metadata(self):
        accuracy = CardInstance("Accuracy")
        finisher = CardInstance("Finisher")
        thousand_cuts = CardInstance("ThousandCuts")
        after_image = CardInstance("AfterImage")

        assert accuracy.rarity == CardRarity.UNCOMMON
        assert accuracy.card_type == CardType.POWER
        assert accuracy.cost == 1
        assert accuracy.magic_number == 4

        assert finisher.rarity == CardRarity.UNCOMMON
        assert finisher.card_type == CardType.ATTACK
        assert finisher.cost == 1
        assert finisher.damage == 6

        assert thousand_cuts.rarity == CardRarity.RARE
        assert thousand_cuts.card_type == CardType.POWER
        assert thousand_cuts.cost == 2
        assert thousand_cuts.magic_number == 1

        assert after_image.rarity == CardRarity.RARE
        assert after_image.card_type == CardType.POWER
        assert after_image.cost == 1
        assert after_image.magic_number == 1

    def test_payoff_upgrade_entries_work(self):
        assert CardInstance("Accuracy+").magic_number == 6
        assert CardInstance("Finisher+").damage == 8
        assert CardInstance("ThousandCuts+").magic_number == 2
        assert CardInstance("AfterImage+").cost == 1
        assert CardInstance("AfterImage+").is_innate is True

    def test_silent_reward_pools_include_payoff_cards(self):
        pools = build_reward_pools("SILENT")
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}
        rare_ids = {card.id for card in pools[CardRarity.RARE]}

        assert {"Accuracy", "Finisher"} <= uncommon_ids
        assert {"ThousandCuts", "AfterImage"} <= rare_ids

    def test_reward_generation_can_surface_payoff_cards(self):
        engine = RunEngine.create("SILENTCARDPLAYPAYOFF", ascension=0, character_class="SILENT")
        targets = {"Accuracy", "Finisher", "ThousandCuts", "AfterImage"}
        seen = False
        for _ in range(30):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in SILENT_ALL_DEFS for card_id in engine.state.pending_card_reward_cards)
