from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import CARD_DEFS_BY_CHARACTER, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestDefectOrbPayoffControlFoundation:
    def test_cards_instantiate_with_expected_metadata(self):
        barrage = CardInstance("Barrage")
        darkness = CardInstance("Darkness")
        loop = CardInstance("Loop")
        consume = CardInstance("Consume")
        buffer = CardInstance("Buffer")

        assert barrage.rarity == CardRarity.COMMON
        assert barrage.card_type == CardType.ATTACK
        assert barrage.cost == 1
        assert barrage.damage == 4

        assert darkness.rarity == CardRarity.UNCOMMON
        assert darkness.card_type == CardType.SKILL
        assert darkness.cost == 1

        assert loop.rarity == CardRarity.UNCOMMON
        assert loop.card_type == CardType.POWER
        assert loop.cost == 1
        assert loop.magic_number == 1

        assert consume.rarity == CardRarity.UNCOMMON
        assert consume.card_type == CardType.SKILL
        assert consume.cost == 2
        assert consume.magic_number == 2

        assert buffer.rarity == CardRarity.RARE
        assert buffer.card_type == CardType.POWER
        assert buffer.cost == 2
        assert buffer.magic_number == 1

    def test_upgraded_entries_work(self):
        assert CardInstance("Barrage+").damage == 6
        assert CardInstance("Loop+").magic_number == 2
        assert CardInstance("Consume+").magic_number == 3
        assert CardInstance("Buffer+").magic_number == 2

    def test_reward_pools_include_payoff_control_cards(self):
        pools = build_reward_pools("DEFECT")
        common_ids = {card.id for card in pools[CardRarity.COMMON]}
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}
        rare_ids = {card.id for card in pools[CardRarity.RARE]}

        assert {"Barrage"} <= common_ids
        assert {"Darkness", "Loop", "Consume"} <= uncommon_ids
        assert {"Buffer"} <= rare_ids

    def test_reward_generation_can_surface_payoff_control_cards(self):
        engine = RunEngine.create("DEFECTORBPAYOFF", ascension=0, character_class="DEFECT")
        targets = {"Barrage", "Darkness", "Loop", "Consume", "Buffer"}
        seen = False
        for _ in range(80):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in CARD_DEFS_BY_CHARACTER["DEFECT"] for card_id in engine.state.pending_card_reward_cards)
