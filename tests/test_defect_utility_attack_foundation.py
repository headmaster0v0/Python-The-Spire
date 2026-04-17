from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import CARD_DEFS_BY_CHARACTER, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestDefectUtilityAttackFoundation:
    def test_cards_instantiate_with_expected_metadata(self):
        compile_driver = CardInstance("CompileDriver")
        hologram = CardInstance("Hologram")
        rebound = CardInstance("Rebound")
        streamline = CardInstance("Streamline")
        leap = CardInstance("Leap")
        glacier = CardInstance("Glacier")

        assert compile_driver.rarity == CardRarity.COMMON
        assert compile_driver.card_type == CardType.ATTACK
        assert compile_driver.cost == 1
        assert compile_driver.damage == 7
        assert compile_driver.magic_number == 1

        assert hologram.rarity == CardRarity.COMMON
        assert hologram.card_type == CardType.SKILL
        assert hologram.cost == 1
        assert hologram.block == 3
        assert hologram.exhaust is True

        assert rebound.rarity == CardRarity.COMMON
        assert rebound.card_type == CardType.ATTACK
        assert rebound.cost == 1
        assert rebound.damage == 9

        assert streamline.rarity == CardRarity.COMMON
        assert streamline.card_type == CardType.ATTACK
        assert streamline.cost == 2
        assert streamline.damage == 15
        assert streamline.magic_number == 1

        assert leap.rarity == CardRarity.COMMON
        assert leap.card_type == CardType.SKILL
        assert leap.cost == 1
        assert leap.block == 9

        assert glacier.rarity == CardRarity.UNCOMMON
        assert glacier.card_type == CardType.SKILL
        assert glacier.cost == 2
        assert glacier.block == 7
        assert glacier.magic_number == 2

    def test_upgraded_entries_work(self):
        assert CardInstance("CompileDriver+").damage == 10
        assert CardInstance("Hologram+").block == 5
        assert CardInstance("Hologram+").exhaust is False
        assert CardInstance("Rebound+").damage == 12
        assert CardInstance("Streamline+").damage == 20
        assert CardInstance("Leap+").block == 12
        assert CardInstance("Glacier+").block == 10

    def test_reward_pools_include_utility_attack_cards(self):
        pools = build_reward_pools("DEFECT")
        common_ids = {card.id for card in pools[CardRarity.COMMON]}
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}

        assert {"CompileDriver", "Hologram", "Rebound", "Streamline", "Leap"} <= common_ids
        assert {"Glacier"} <= uncommon_ids

    def test_reward_generation_can_surface_utility_attack_cards(self):
        engine = RunEngine.create("DEFECTUTILITYATTACK", ascension=0, character_class="DEFECT")
        targets = {"CompileDriver", "Hologram", "Rebound", "Streamline", "Leap", "Glacier"}
        seen = False
        for _ in range(80):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in CARD_DEFS_BY_CHARACTER["DEFECT"] for card_id in engine.state.pending_card_reward_cards)
