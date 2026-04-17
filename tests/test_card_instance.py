"""Unit tests for CardInstance system.

Tests cover:
- Card creation and initialization
- Upgrade mechanics
- Damage/block calculation with powers
- Card effects execution
- Serialization/deserialization
"""
from __future__ import annotations

import pytest
import uuid

from sts_py.engine.content.card_instance import CardInstance, create_starter_deck
from sts_py.engine.content.cards_min import CardRarity, CardType
from sts_py.engine.combat.combat_state import Player, CombatState
from sts_py.engine.combat.card_effects import (
    DealDamageEffect, GainBlockEffect, ApplyPowerEffect,
    get_card_effects, execute_card,
)


class TestCardInstanceCreation:
    def test_strike_creation(self):
        card = CardInstance(card_id="Strike")
        assert card.card_id == "Strike"
        assert card.cost == 1
        assert card.base_damage == 6
        assert card.damage == 6
        assert card.rarity == CardRarity.BASIC
        assert card.card_type == CardType.ATTACK
        assert card.is_attack()
        assert not card.is_skill()
        assert card.is_starter_strike()

    def test_defend_creation(self):
        card = CardInstance(card_id="Defend")
        assert card.card_id == "Defend"
        assert card.cost == 1
        assert card.base_block == 5
        assert card.block == 5
        assert card.rarity == CardRarity.BASIC
        assert card.card_type == CardType.SKILL
        assert card.is_skill()
        assert not card.is_attack()
        assert card.is_starter_defend()

    def test_bash_creation(self):
        card = CardInstance(card_id="Bash")
        assert card.card_id == "Bash"
        assert card.cost == 2
        assert card.base_damage == 8
        assert card.base_magic_number == 2
        assert card.magic_number == 2
        assert card.rarity == CardRarity.BASIC
        assert card.card_type == CardType.ATTACK

    def test_unique_uuid(self):
        card1 = CardInstance(card_id="Strike")
        card2 = CardInstance(card_id="Strike")
        assert card1.uuid != card2.uuid
        assert card1 != card2

    def test_starter_deck(self):
        deck = create_starter_deck()
        assert len(deck) == 10
        
        strikes = [c for c in deck if c.card_id == "Strike"]
        defends = [c for c in deck if c.card_id == "Defend"]
        bashes = [c for c in deck if c.card_id == "Bash"]
        
        assert len(strikes) == 5
        assert len(defends) == 4
        assert len(bashes) == 1


class TestCardUpgrade:
    def test_strike_upgrade(self):
        card = CardInstance(card_id="Strike")
        assert not card.upgraded
        assert card.base_damage == 6
        
        card.upgrade()
        
        assert card.upgraded
        assert card.times_upgraded == 1
        assert card.base_damage == 9
        assert card.damage == 9

    def test_defend_upgrade(self):
        card = CardInstance(card_id="Defend")
        assert not card.upgraded
        assert card.base_block == 5
        
        card.upgrade()
        
        assert card.upgraded
        assert card.base_block == 8
        assert card.block == 8

    def test_bash_upgrade(self):
        card = CardInstance(card_id="Bash")
        assert not card.upgraded
        assert card.base_damage == 8
        assert card.base_magic_number == 2
        
        card.upgrade()
        
        assert card.upgraded
        assert card.base_damage == 10
        assert card.base_magic_number == 3
        assert card.magic_number == 3

    def test_double_upgrade_ignored(self):
        card = CardInstance(card_id="Strike")
        card.upgrade()
        first_damage = card.base_damage
        
        card.upgrade()
        
        assert card.times_upgraded == 1
        assert card.base_damage == first_damage

    def test_flex_upgrade(self):
        card = CardInstance(card_id="Flex")
        assert card.cost == 0
        assert card.base_magic_number == 2
        
        card.upgrade()
        
        assert card.base_magic_number == 4


class TestCardDamageCalculation:
    def test_base_damage_no_powers(self):
        card = CardInstance(card_id="Strike")
        player = Player(hp=80, max_hp=80)
        combat_state = CombatState(player=player)
        
        card.apply_powers(combat_state)
        
        assert card.damage == 6
        assert not card.is_damage_modified

    def test_damage_with_strength(self):
        card = CardInstance(card_id="Strike")
        player = Player(hp=80, max_hp=80, strength=3)
        combat_state = CombatState(player=player)
        
        card.apply_powers(combat_state)
        
        assert card.damage == 9
        assert card.is_damage_modified

    def test_damage_negative_strength_floor(self):
        card = CardInstance(card_id="Strike")
        player = Player(hp=80, max_hp=80, strength=-10)
        combat_state = CombatState(player=player)
        
        card.apply_powers(combat_state)
        
        assert card.damage == 0

    def test_block_with_dexterity(self):
        card = CardInstance(card_id="Defend")
        player = Player(hp=80, max_hp=80, dexterity=2)
        combat_state = CombatState(player=player)
        
        card.apply_powers(combat_state)
        
        assert card.block == 7
        assert card.is_block_modified


class TestCardEffects:
    def test_strike_effects(self):
        card = CardInstance(card_id="Strike")
        effects = get_card_effects(card, target_idx=0)
        
        assert len(effects) == 1
        assert isinstance(effects[0], DealDamageEffect)
        assert effects[0].damage == 6

    def test_defend_effects(self):
        card = CardInstance(card_id="Defend")
        effects = get_card_effects(card)
        
        assert len(effects) == 1
        assert isinstance(effects[0], GainBlockEffect)
        assert effects[0].amount == 5

    def test_bash_effects(self):
        card = CardInstance(card_id="Bash")
        effects = get_card_effects(card, target_idx=0)
        
        assert len(effects) == 2
        assert isinstance(effects[0], DealDamageEffect)
        assert isinstance(effects[1], ApplyPowerEffect)
        assert effects[1].power_type == "Vulnerable"
        assert effects[1].amount == 2

    def test_twin_strike_double_damage(self):
        card = CardInstance(card_id="TwinStrike")
        effects = get_card_effects(card, target_idx=0)
        
        assert len(effects) == 2
        assert all(isinstance(e, DealDamageEffect) for e in effects)

    def test_thunderclap_aoe_with_vulnerable(self):
        card = CardInstance(card_id="Thunderclap")
        effects = get_card_effects(card)
        
        assert len(effects) == 2
        assert any(isinstance(e, DealDamageEffect) or hasattr(e, 'damage') for e in effects)


class TestCardCopy:
    def test_make_copy_new_uuid(self):
        card = CardInstance(card_id="Strike")
        copy = card.make_copy()
        
        assert copy.card_id == card.card_id
        assert copy.uuid != card.uuid

    def test_make_stat_equivalent_copy(self):
        card = CardInstance(card_id="Strike")
        card.upgrade()
        
        copy = card.make_stat_equivalent_copy()
        
        assert copy.card_id == card.card_id
        assert copy.upgraded == card.upgraded
        assert copy.times_upgraded == card.times_upgraded
        assert copy.base_damage == card.base_damage
        assert copy.uuid != card.uuid

    def test_make_same_instance(self):
        card = CardInstance(card_id="Strike")
        card.upgrade()
        
        copy = card.make_same_instance()
        
        assert copy.uuid == card.uuid


class TestCardSerialization:
    def test_to_dict_and_from_dict(self):
        card = CardInstance(card_id="Strike")
        card.upgrade()
        
        data = card.to_dict()
        restored = CardInstance.from_dict(data)
        
        assert restored.card_id == card.card_id
        assert restored.upgraded == card.upgraded
        assert restored.base_damage == card.base_damage
        assert str(restored.uuid) == str(card.uuid)

    def test_serialization_preserves_magic_number(self):
        card = CardInstance(card_id="Bash")
        card.upgrade()
        
        data = card.to_dict()
        restored = CardInstance.from_dict(data)
        
        assert restored.magic_number == 3


class TestCardComparison:
    def test_card_sorting_by_id(self):
        cards = [
            CardInstance(card_id="Defend"),
            CardInstance(card_id="Strike"),
            CardInstance(card_id="Bash"),
        ]
        
        sorted_cards = sorted(cards)
        
        assert sorted_cards[0].card_id == "Bash"
        assert sorted_cards[1].card_id == "Defend"
        assert sorted_cards[2].card_id == "Strike"

    def test_card_hash_by_uuid(self):
        card = CardInstance(card_id="Strike")
        card_dict = {card: "test"}
        
        assert card_dict[card] == "test"


class TestCardTurnState:
    def test_reset_for_turn(self):
        card = CardInstance(card_id="Strike")
        card.cost_for_turn = 0
        card.free_to_play_once = True
        
        card.reset_for_turn()
        
        assert card.cost_for_turn == card.cost
        assert not card.free_to_play_once

    def test_can_use_with_energy(self):
        card = CardInstance(card_id="Strike")
        
        assert card.can_use(energy=1)
        assert card.can_use(energy=2)
        assert not card.can_use(energy=0)

    def test_x_cost_card(self):
        card = CardInstance(card_id="Whirlwind")
        assert card.cost == -1
        
        assert card.can_use(energy=0)
        assert card.can_use(energy=3)


class TestCardRepr:
    def test_repr_unupgraded(self):
        card = CardInstance(card_id="Strike")
        assert "Strike" in repr(card)
        assert "+" not in repr(card)

    def test_repr_upgraded(self):
        card = CardInstance(card_id="Strike")
        card.upgrade()
        assert "Strike+" in repr(card)
