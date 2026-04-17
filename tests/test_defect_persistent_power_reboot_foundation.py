from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import CARD_DEFS_BY_CHARACTER, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestDefectPersistentPowerRebootFoundation:
    def test_cards_instantiate_with_expected_metadata(self):
        storm = CardInstance("Storm")
        heatsinks = CardInstance("Heatsinks")
        machine_learning = CardInstance("MachineLearning")
        self_repair = CardInstance("SelfRepair")
        reboot = CardInstance("Reboot")

        assert storm.rarity == CardRarity.UNCOMMON
        assert storm.card_type == CardType.POWER
        assert storm.cost == 1
        assert storm.magic_number == 1

        assert heatsinks.rarity == CardRarity.UNCOMMON
        assert heatsinks.card_type == CardType.POWER
        assert heatsinks.cost == 1
        assert heatsinks.magic_number == 1

        assert machine_learning.rarity == CardRarity.RARE
        assert machine_learning.card_type == CardType.POWER
        assert machine_learning.cost == 1
        assert machine_learning.magic_number == 1

        assert self_repair.rarity == CardRarity.UNCOMMON
        assert self_repair.card_type == CardType.POWER
        assert self_repair.cost == 1
        assert self_repair.magic_number == 7

        assert reboot.rarity == CardRarity.RARE
        assert reboot.card_type == CardType.SKILL
        assert reboot.cost == 0
        assert reboot.magic_number == 4
        assert reboot.exhaust is True

    def test_upgraded_entries_and_aliases_work(self):
        assert CardInstance("Storm", upgraded=True).is_innate is True
        assert CardInstance("Heatsinks", upgraded=True).magic_number == 2
        assert CardInstance("MachineLearning", upgraded=True).is_innate is True
        assert CardInstance("SelfRepair", upgraded=True).magic_number == 10
        assert CardInstance("Reboot", upgraded=True).magic_number == 6
        assert CardInstance("Machine Learning").card_id == "MachineLearning"
        assert CardInstance("Self Repair").card_id == "SelfRepair"

    def test_reward_pools_include_persistent_power_reboot_cards(self):
        pools = build_reward_pools("DEFECT")
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}
        rare_ids = {card.id for card in pools[CardRarity.RARE]}

        assert {"Storm", "Heatsinks", "SelfRepair"} <= uncommon_ids
        assert {"MachineLearning", "Reboot"} <= rare_ids

    def test_reward_generation_can_surface_persistent_power_reboot_cards(self):
        engine = RunEngine.create("DEFECTPERSISTENT", ascension=0, character_class="DEFECT")
        targets = {"Storm", "Heatsinks", "MachineLearning", "SelfRepair", "Reboot"}
        seen = False
        for _ in range(80):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in CARD_DEFS_BY_CHARACTER["DEFECT"] for card_id in engine.state.pending_card_reward_cards)
