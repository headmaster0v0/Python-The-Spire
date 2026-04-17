"""Unit tests for Power system.

Tests cover:
- Power creation and stacking
- Damage/block modifiers
- Turn-based power decay
- PowerContainer management
"""
from __future__ import annotations

import pytest

from sts_py.engine.combat.powers import (
    PowerType,
    StrengthPower, DexterityPower, VulnerablePower, WeakPower,
    CurlUpPower, RitualPower,
    create_power, power_from_dict,
)
from sts_py.engine.combat.power_container import PowerContainer


class TestStrengthPower:
    def test_creation(self):
        power = StrengthPower(amount=3, owner="player")
        assert power.id == "Strength"
        assert power.amount == 3
        assert power.power_type == PowerType.BUFF
        assert not power.is_turn_based
        assert power.can_go_negative

    def test_negative_strength_is_debuff(self):
        power = StrengthPower(amount=-2, owner="player")
        assert power.power_type == PowerType.DEBUFF

    def test_damage_modification(self):
        power = StrengthPower(amount=4, owner="player")
        assert power.at_damage_give(10.0) == 14.0
        assert power.at_damage_give(10.0, "THORNS") == 10.0

    def test_negative_strength_reduces_damage(self):
        power = StrengthPower(amount=-3, owner="player")
        assert power.at_damage_give(10.0) == 7.0

    def test_stacking(self):
        power = StrengthPower(amount=2, owner="player")
        power.stack_power(3)
        assert power.amount == 5
        power.stack_power(-7)
        assert power.amount == -2
        assert power.power_type == PowerType.DEBUFF


class TestDexterityPower:
    def test_creation(self):
        power = DexterityPower(amount=2, owner="player")
        assert power.id == "Dexterity"
        assert power.amount == 2
        assert power.power_type == PowerType.BUFF

    def test_block_modification(self):
        power = DexterityPower(amount=3, owner="player")
        assert power.modify_block(5.0) == 8.0
        assert power.modify_block(0.0) == 3.0

    def test_negative_dexterity_reduces_block(self):
        power = DexterityPower(amount=-2, owner="player")
        assert power.modify_block(5.0) == 3.0

    def test_block_floor_at_zero(self):
        power = DexterityPower(amount=-10, owner="player")
        assert power.modify_block(5.0) == 0.0


class TestVulnerablePower:
    def test_creation(self):
        power = VulnerablePower(amount=2, owner="monster_0")
        assert power.id == "Vulnerable"
        assert power.amount == 2
        assert power.power_type == PowerType.DEBUFF
        assert power.is_turn_based

    def test_damage_receive_modification(self):
        power = VulnerablePower(amount=1, owner="monster_0")
        assert power.at_damage_receive(10.0) == 15.0
        assert power.at_damage_receive(10.0, "THORNS") == 10.0

    def test_end_of_round_decay(self):
        power = VulnerablePower(amount=2, owner="monster_0")
        should_remove = power.at_end_of_round()
        assert not should_remove
        assert power.amount == 1

        should_remove = power.at_end_of_round()
        assert should_remove
        assert power.amount == 0

    def test_stacking(self):
        power = VulnerablePower(amount=1, owner="monster_0")
        power.stack_power(2)
        assert power.amount == 3


class TestWeakPower:
    def test_creation(self):
        power = WeakPower(amount=1, owner="monster_0")
        assert power.id == "Weak"
        assert power.amount == 1
        assert power.power_type == PowerType.DEBUFF
        assert power.is_turn_based

    def test_damage_give_modification(self):
        power = WeakPower(amount=1, owner="monster_0")
        assert power.at_damage_give(10.0) == 7.5
        assert power.at_damage_give(10.0, "THORNS") == 10.0

    def test_end_of_round_decay(self):
        power = WeakPower(amount=2, owner="monster_0")
        should_remove = power.at_end_of_round()
        assert not should_remove
        assert power.amount == 2

        should_remove = power.at_end_of_round()
        assert not should_remove
        assert power.amount == 1

        should_remove = power.at_end_of_round()
        assert should_remove
        assert power.amount == 0


class TestCurlUpPower:
    def test_creation(self):
        power = CurlUpPower(amount=4, owner="monster_0")
        assert power.id == "Curl Up"
        assert power.amount == 4
        assert power.power_type == PowerType.BUFF

    def test_on_attacked_triggers_once(self):
        power = CurlUpPower(amount=5, owner="monster_0")
        assert power.on_attacked(5) == 5
        assert power.on_attacked(3) == 0
        assert power.on_attacked(10) == 0

    def test_no_trigger_on_zero_damage(self):
        power = CurlUpPower(amount=5, owner="monster_0")
        assert power.on_attacked(0) == 0
        assert power.on_attacked(5) == 5


class TestRitualPower:
    def test_creation(self):
        power = RitualPower(amount=3, owner="monster_0")
        assert power.id == "Ritual"
        assert power.amount == 3
        assert power.power_type == PowerType.BUFF

    def test_strength_gain_skip_first(self):
        power = RitualPower(amount=4, owner="monster_0")
        assert power.skip_first == True
        assert power.get_strength_gain() == 0

    def test_strength_gain_after_skip(self):
        power = RitualPower(amount=4, owner="monster_0")
        power.skip_first = False
        assert power.get_strength_gain() == 4

    def test_strength_gain_for_player(self):
        power = RitualPower(amount=4, owner="player", on_player=True)
        power.skip_first = True
        assert power.get_strength_gain() == 4


class TestPowerContainer:
    def test_add_power(self):
        container = PowerContainer()
        power = StrengthPower(amount=2, owner="player")
        container.add_power(power)
        assert len(container) == 1
        assert container.has_power("Strength")

    def test_add_power_stacks(self):
        container = PowerContainer()
        container.add_power(StrengthPower(amount=2, owner="player"))
        container.add_power(StrengthPower(amount=3, owner="player"))
        assert len(container) == 1
        assert container.get_power_amount("Strength") == 5

    def test_remove_power(self):
        container = PowerContainer()
        container.add_power(StrengthPower(amount=2, owner="player"))
        removed = container.remove_power("Strength")
        assert removed is not None
        assert removed.amount == 2
        assert not container.has_power("Strength")

    def test_get_power_amount_missing(self):
        container = PowerContainer()
        assert container.get_power_amount("Strength") == 0

    def test_apply_damage_modifiers(self):
        container = PowerContainer()
        container.add_power(StrengthPower(amount=3, owner="player"))
        container.add_power(WeakPower(amount=1, owner="player"))
        damage = container.apply_damage_modifiers(10.0)
        assert damage == 9.75

    def test_apply_damage_receive_modifiers(self):
        container = PowerContainer()
        container.add_power(VulnerablePower(amount=1, owner="player"))
        damage = container.apply_damage_receive_modifiers(10.0)
        assert damage == 15.0

    def test_apply_block_modifiers(self):
        container = PowerContainer()
        container.add_power(DexterityPower(amount=2, owner="player"))
        block = container.apply_block_modifiers(5.0)
        assert block == 7.0

    def test_end_of_round_removes_expired_powers(self):
        container = PowerContainer()
        power = VulnerablePower(amount=1, owner="player")
        power.at_end_of_round()
        container.add_power(power)
        removed = container.at_end_of_round()
        assert "Vulnerable" in removed
        assert not container.has_power("Vulnerable")

    def test_serialization(self):
        container = PowerContainer()
        container.add_power(StrengthPower(amount=3, owner="player"))
        container.add_power(VulnerablePower(amount=2, owner="player"))
        
        data = container.to_dict()
        restored = PowerContainer.from_dict(data)
        
        assert len(restored) == 2
        assert restored.get_power_amount("Strength") == 3
        assert restored.get_power_amount("Vulnerable") == 2


class TestPowerFactory:
    def test_create_power(self):
        power = create_power("Strength", 5, "player")
        assert power.id == "Strength"
        assert power.amount == 5
        assert power.owner == "player"

    def test_create_unknown_power(self):
        with pytest.raises(ValueError):
            create_power("UnknownPower", 1, "player")

    def test_power_from_dict(self):
        data = {"id": "Vulnerable", "amount": 3, "owner": "monster_0"}
        power = power_from_dict(data)
        assert power.id == "Vulnerable"
        assert power.amount == 3
        assert power.owner == "monster_0"


class TestPowerIntegration:
    def test_strength_and_weak_interaction(self):
        container = PowerContainer()
        container.add_power(StrengthPower(amount=4, owner="monster_0"))
        container.add_power(WeakPower(amount=1, owner="monster_0"))
        
        base_damage = 10.0
        damage = container.apply_damage_modifiers(base_damage)
        assert damage == 10.5

    def test_vulnerable_stacks_duration(self):
        container = PowerContainer()
        container.add_power(VulnerablePower(amount=3, owner="monster_0"))
        
        assert container.get_vulnerable() == 3
        
        container.at_end_of_round()
        assert container.get_vulnerable() == 2
        
        container.at_end_of_round()
        assert container.get_vulnerable() == 1
        
        container.at_end_of_round()
        assert container.get_vulnerable() == 0
        assert not container.has_power("Vulnerable")

    def test_multiple_damage_modifiers(self):
        container = PowerContainer()
        container.add_power(StrengthPower(amount=2, owner="player"))
        container.add_power(StrengthPower(amount=3, owner="player"))
        
        assert container.get_strength() == 5
        assert container.apply_damage_modifiers(10.0) == 15.0
