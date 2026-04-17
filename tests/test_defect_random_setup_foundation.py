from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import CARD_DEFS_BY_CHARACTER, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestDefectRandomSetupFoundation:
    def test_cards_instantiate_with_expected_metadata(self):
        white_noise = CardInstance("WhiteNoise")
        chaos = CardInstance("Chaos")
        overclock = CardInstance("Overclock")
        creative_ai = CardInstance("CreativeAI")

        assert white_noise.rarity == CardRarity.UNCOMMON
        assert white_noise.card_type == CardType.SKILL
        assert white_noise.cost == 1
        assert white_noise.exhaust is True

        assert chaos.rarity == CardRarity.UNCOMMON
        assert chaos.card_type == CardType.SKILL
        assert chaos.cost == 1
        assert chaos.magic_number == 1

        assert overclock.rarity == CardRarity.UNCOMMON
        assert overclock.card_type == CardType.SKILL
        assert overclock.cost == 0
        assert overclock.magic_number == 2

        assert creative_ai.rarity == CardRarity.RARE
        assert creative_ai.card_type == CardType.POWER
        assert creative_ai.cost == 3
        assert creative_ai.magic_number == 1

    def test_upgrade_entries_and_aliases_work(self):
        assert CardInstance("WhiteNoise+").cost == 0
        assert CardInstance("Chaos+").magic_number == 2
        assert CardInstance("Overclock+").magic_number == 3
        assert CardInstance("CreativeAI+").cost == 2

        old = CardInstance("Steam Power")
        assert old.card_id == "Overclock"

    def test_reward_pools_include_random_setup_cards(self):
        pools = build_reward_pools("DEFECT")
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}
        rare_ids = {card.id for card in pools[CardRarity.RARE]}

        assert {"WhiteNoise", "Chaos", "Overclock"} <= uncommon_ids
        assert {"CreativeAI"} <= rare_ids

    def test_reward_generation_can_surface_random_setup_cards(self):
        engine = RunEngine.create("DEFECTRANDOMSETUP", ascension=0, character_class="DEFECT")
        targets = {"WhiteNoise", "Chaos", "Overclock", "CreativeAI"}
        seen = False
        for _ in range(80):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in CARD_DEFS_BY_CHARACTER["DEFECT"] for card_id in engine.state.pending_card_reward_cards)
