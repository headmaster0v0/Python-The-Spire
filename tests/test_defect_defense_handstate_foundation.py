from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import CARD_DEFS_BY_CHARACTER, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestDefectDefenseHandstateFoundation:
    def test_cards_instantiate_with_expected_metadata(self):
        conserve_battery = CardInstance("ConserveBattery")
        equilibrium = CardInstance("Equilibrium")
        force_field = CardInstance("ForceField")
        stack = CardInstance("Stack")
        steam_barrier = CardInstance("SteamBarrier")

        assert conserve_battery.rarity == CardRarity.COMMON
        assert conserve_battery.card_type == CardType.SKILL
        assert conserve_battery.cost == 1
        assert conserve_battery.block == 7

        assert equilibrium.rarity == CardRarity.UNCOMMON
        assert equilibrium.card_type == CardType.SKILL
        assert equilibrium.cost == 2
        assert equilibrium.block == 13
        assert equilibrium.magic_number == 1

        assert force_field.rarity == CardRarity.UNCOMMON
        assert force_field.card_type == CardType.SKILL
        assert force_field.cost == 4
        assert force_field.block == 12

        assert stack.rarity == CardRarity.COMMON
        assert stack.card_type == CardType.SKILL
        assert stack.cost == 1

        assert steam_barrier.rarity == CardRarity.COMMON
        assert steam_barrier.card_type == CardType.SKILL
        assert steam_barrier.cost == 0
        assert steam_barrier.block == 6

    def test_upgraded_entries_and_aliases_work(self):
        assert CardInstance("ConserveBattery", upgraded=True).block == 10
        assert CardInstance("Equilibrium", upgraded=True).block == 16
        assert CardInstance("ForceField", upgraded=True).block == 16
        assert CardInstance("Stack", upgraded=True).base_block == 3
        assert CardInstance("SteamBarrier", upgraded=True).block == 8
        assert CardInstance("Conserve Battery").card_id == "ConserveBattery"
        assert CardInstance("Undo").card_id == "Equilibrium"
        assert CardInstance("Force Field").card_id == "ForceField"
        assert CardInstance("Steam").card_id == "SteamBarrier"

    def test_reward_pools_include_defense_handstate_cards(self):
        pools = build_reward_pools("DEFECT")
        common_ids = {card.id for card in pools[CardRarity.COMMON]}
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}

        assert {"ConserveBattery", "Stack", "SteamBarrier"} <= common_ids
        assert {"Equilibrium", "ForceField"} <= uncommon_ids

    def test_reward_generation_can_surface_defense_handstate_cards(self):
        engine = RunEngine.create("DEFECTDEFENSEHANDSTATE", ascension=0, character_class="DEFECT")
        targets = {"ConserveBattery", "Equilibrium", "ForceField", "Stack", "SteamBarrier"}
        seen = False
        for _ in range(80):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in CARD_DEFS_BY_CHARACTER["DEFECT"] for card_id in engine.state.pending_card_reward_cards)
