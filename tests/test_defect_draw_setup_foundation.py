from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import CARD_DEFS_BY_CHARACTER, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestDefectDrawSetupFoundation:
    def test_cards_instantiate_with_expected_metadata(self):
        skim = CardInstance("Skim")
        seek = CardInstance("Seek")
        aggregate = CardInstance("Aggregate")
        auto_shields = CardInstance("AutoShields")
        boot_sequence = CardInstance("BootSequence")

        assert skim.rarity == CardRarity.UNCOMMON
        assert skim.card_type == CardType.SKILL
        assert skim.cost == 1
        assert skim.magic_number == 3

        assert seek.rarity == CardRarity.RARE
        assert seek.card_type == CardType.SKILL
        assert seek.cost == 0
        assert seek.magic_number == 1
        assert seek.exhaust is True

        assert aggregate.rarity == CardRarity.UNCOMMON
        assert aggregate.card_type == CardType.SKILL
        assert aggregate.cost == 1
        assert aggregate.magic_number == 4

        assert auto_shields.rarity == CardRarity.UNCOMMON
        assert auto_shields.card_type == CardType.SKILL
        assert auto_shields.cost == 1
        assert auto_shields.block == 11

        assert boot_sequence.rarity == CardRarity.UNCOMMON
        assert boot_sequence.card_type == CardType.SKILL
        assert boot_sequence.cost == 0
        assert boot_sequence.block == 10
        assert boot_sequence.is_innate is True
        assert boot_sequence.exhaust is True

    def test_upgraded_entries_work(self):
        assert CardInstance("Skim+").magic_number == 4
        assert CardInstance("Seek+").magic_number == 2
        assert CardInstance("Aggregate+").magic_number == 3
        assert CardInstance("AutoShields+").block == 15
        assert CardInstance("BootSequence+").block == 13

    def test_reward_pools_include_draw_setup_cards(self):
        pools = build_reward_pools("DEFECT")
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}
        rare_ids = {card.id for card in pools[CardRarity.RARE]}

        assert {"Skim", "Aggregate", "AutoShields", "BootSequence"} <= uncommon_ids
        assert {"Seek"} <= rare_ids

    def test_reward_generation_can_surface_draw_setup_cards(self):
        engine = RunEngine.create("DEFECTDRAWSETUP", ascension=0, character_class="DEFECT")
        targets = {"Skim", "Seek", "Aggregate", "AutoShields", "BootSequence"}
        seen = False
        for _ in range(80):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in CARD_DEFS_BY_CHARACTER["DEFECT"] for card_id in engine.state.pending_card_reward_cards)
