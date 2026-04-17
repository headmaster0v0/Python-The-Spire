from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import CARD_ID_ALIASES, DEFECT_ALL_DEFS, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestDefectReprogramFoundation:
    def test_reprogram_instantiates_with_expected_metadata(self):
        reprogram = CardInstance("Reprogram")

        assert reprogram.rarity == CardRarity.UNCOMMON
        assert reprogram.card_type == CardType.SKILL
        assert reprogram.cost == 1
        assert reprogram.magic_number == 1

    def test_reprogram_upgrade_metadata(self):
        upgraded = CardInstance("Reprogram", upgraded=True)
        assert upgraded.magic_number == 2

    def test_defect_reward_pools_include_reprogram(self):
        pools = build_reward_pools("DEFECT")
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}
        assert "Reprogram" in uncommon_ids

    def test_reward_generation_can_surface_reprogram(self):
        engine = RunEngine.create("DEFECTREPROGRAM", ascension=0, character_class="DEFECT")
        seen = False
        for _ in range(100):
            engine._add_card_reward()
            if "Reprogram" in engine.state.pending_card_reward_cards:
                seen = True
                break
        assert seen is True
        assert all(card_id in DEFECT_ALL_DEFS for card_id in engine.state.pending_card_reward_cards)

    def test_alias_cleanup_covers_remaining_legacy_names(self):
        assert CardInstance("Strike_Green").card_id == "Strike"
        assert CardInstance("Defend_Green").card_id == "Defend"
        assert CARD_ID_ALIASES["Strike_Red"] == "Strike"
        assert CARD_ID_ALIASES["Defend_Red"] == "Defend"
        assert CARD_ID_ALIASES["BloodForBlood"] == "BloodforBlood"
        assert CARD_ID_ALIASES["ThunderClap"] == "Thunderclap"
