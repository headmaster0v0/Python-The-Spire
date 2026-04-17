from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import CARD_DEFS_BY_CHARACTER, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestDefectEnergyOrbResourceFoundation:
    def test_cards_instantiate_with_expected_metadata(self):
        turbo = CardInstance("Turbo")
        double_energy = CardInstance("DoubleEnergy")
        fission = CardInstance("Fission")
        multicast = CardInstance("MultiCast")
        recycle = CardInstance("Recycle")

        assert turbo.rarity == CardRarity.COMMON
        assert turbo.card_type == CardType.SKILL
        assert turbo.cost == 0
        assert turbo.magic_number == 2

        assert double_energy.rarity == CardRarity.UNCOMMON
        assert double_energy.card_type == CardType.SKILL
        assert double_energy.cost == 1
        assert double_energy.exhaust is True

        assert fission.rarity == CardRarity.RARE
        assert fission.card_type == CardType.SKILL
        assert fission.cost == 0
        assert fission.exhaust is True

        assert multicast.rarity == CardRarity.RARE
        assert multicast.card_type == CardType.SKILL
        assert multicast.cost == -1

        assert recycle.rarity == CardRarity.UNCOMMON
        assert recycle.card_type == CardType.SKILL
        assert recycle.cost == 1

    def test_upgraded_entries_and_aliases_work(self):
        assert CardInstance("Turbo", upgraded=True).magic_number == 3
        assert CardInstance("DoubleEnergy", upgraded=True).cost == 0
        assert CardInstance("Fission", upgraded=True).exhaust is True
        assert CardInstance("Multi-Cast").card_id == "MultiCast"
        assert CardInstance("Recycle", upgraded=True).cost == 0

    def test_reward_pools_include_energy_orb_resource_cards(self):
        pools = build_reward_pools("DEFECT")
        common_ids = {card.id for card in pools[CardRarity.COMMON]}
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}
        rare_ids = {card.id for card in pools[CardRarity.RARE]}

        assert {"Turbo"} <= common_ids
        assert {"DoubleEnergy", "Tempest", "Recycle", "Fusion", "Capacitor", "ReinforcedBody"} <= uncommon_ids
        assert {"Fission", "MultiCast", "MeteorStrike"} <= rare_ids

    def test_reward_generation_can_surface_energy_orb_resource_cards(self):
        engine = RunEngine.create("DEFECTRESOURCE", ascension=0, character_class="DEFECT")
        targets = {"Turbo", "DoubleEnergy", "Fission", "MultiCast", "Recycle", "Fusion", "Capacitor", "ReinforcedBody", "MeteorStrike"}
        seen = False
        for _ in range(80):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in CARD_DEFS_BY_CHARACTER["DEFECT"] for card_id in engine.state.pending_card_reward_cards)
