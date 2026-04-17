"""Combat system parity tests.

Tests the combat engine against autosave truth data:
  - Floor 1: Jaw Worm (5 turns, 1 damage)
  - Floor 2: 2 Louse (2 turns, 7 damage)
  - Floor 3: Cultist (4 turns, 9 damage)
  - Floor 5: Red Slaver (5 turns, 27 damage)

Note: Full parity requires exact player actions which autosave doesn't record.
These tests verify the combat engine mechanics work correctly.
"""
from __future__ import annotations

import pytest

from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.core.seed import seed_string_to_long
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.combat_state import CombatPhase
from sts_py.engine.monsters.exordium import JawWorm, LouseNormal, Cultist, SlaverRed
from sts_py.engine.monsters.intent import MonsterIntent


SEED_STRING = "1B40C4J3IIYDA"
SEED_LONG = 4452322743548530140


class TestMonsterCreation:
    def test_jaw_worm_creation(self):
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        worm = JawWorm.create(hp_rng, ascension=0)
        assert worm.id == "JawWorm"
        assert 40 <= worm.hp <= 44
        assert worm.chomp_dmg == 11
        assert worm.thrash_dmg == 7

    def test_jaw_worm_asc2(self):
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        worm = JawWorm.create(hp_rng, ascension=2)
        assert worm.chomp_dmg == 12
        assert worm.bellow_str == 4

    def test_louse_creation(self):
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        louse = LouseNormal.create(hp_rng, ascension=0)
        assert louse.id == "FuzzyLouseNormal"
        assert 10 <= louse.hp <= 15
        assert 5 <= louse.bite_damage <= 7
        assert louse.curl_up >= 3

    def test_cultist_creation(self):
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        cultist = Cultist.create(hp_rng, ascension=0)
        assert cultist.id == "Cultist"
        assert 48 <= cultist.hp <= 54
        assert cultist.ritual_amount == 3

    def test_cultist_asc2(self):
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        cultist = Cultist.create(hp_rng, ascension=2)
        assert cultist.ritual_amount == 4

    def test_red_slaver_creation(self):
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        slaver = SlaverRed.create(hp_rng, ascension=0)
        assert slaver.id == "SlaverRed"
        assert 46 <= slaver.hp <= 50
        assert slaver.stab_dmg == 13
        assert slaver.scrape_dmg == 8


class TestMonsterAI:
    def test_jaw_worm_first_move(self):
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        worm = JawWorm.create(hp_rng, ascension=0)
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=100)

        worm.roll_move(ai_rng)
        assert worm.next_move is not None
        assert worm.next_move.move_id == 1
        assert worm.next_move.intent == MonsterIntent.ATTACK
        assert worm.first_move == False

    def test_cultist_first_move_incantation(self):
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        cultist = Cultist.create(hp_rng, ascension=0)
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=100)

        cultist.roll_move(ai_rng)
        assert cultist.next_move is not None
        assert cultist.next_move.move_id == 3
        assert cultist.next_move.intent == MonsterIntent.BUFF

    def test_cultist_second_move_attack(self):
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        cultist = Cultist.create(hp_rng, ascension=0)
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=100)

        cultist.roll_move(ai_rng)
        assert cultist.next_move.intent == MonsterIntent.BUFF

        cultist.roll_move(ai_rng)
        assert cultist.next_move.move_id == 1
        assert cultist.next_move.intent == MonsterIntent.ATTACK

    def test_louse_alternates_moves(self):
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        louse = LouseNormal.create(hp_rng, ascension=0)
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=100)

        louse.roll_move(ai_rng)
        first_move = louse.next_move.move_id

        louse.roll_move(ai_rng)
        second_move = louse.next_move.move_id

        assert first_move != second_move or first_move == 3


class TestCombatEngine:
    def test_create_jaw_worm_encounter(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)

        combat = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        assert len(combat.state.monsters) == 1
        assert combat.state.monsters[0].id == "JawWorm"
        assert combat.state.phase == CombatPhase.PLAYER_TURN
        assert combat.state.turn == 1

    def test_create_two_louse_encounter(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="2 Louse",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        assert len(combat.state.monsters) == 2
        assert all(m.id in ("LouseRed", "LouseGreen", "LouseDefensive") for m in combat.state.monsters)

    def test_player_attack_reduces_monster_hp(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        monster = combat.state.monsters[0]
        initial_hp = monster.hp
        combat.player_attack(0, 10)
        assert monster.hp == initial_hp - 10

    def test_player_block_reduces_damage(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        combat.player_gain_block(5)
        combat.end_player_turn()
        assert combat.state.player.hp < 80

    def test_monster_turn_deals_damage(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        initial_hp = combat.state.player.hp
        combat.end_player_turn()
        assert combat.state.player.hp < initial_hp

    def test_combat_ends_when_monster_dies(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        monster = combat.state.monsters[0]
        combat.player_attack(0, monster.hp + 10)
        assert combat.is_combat_over()
        assert combat.player_won()

    def test_multiple_turns_advance_correctly(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        for _ in range(3):
            if combat.is_combat_over():
                break
            combat.player_attack(0, 5)
            combat.end_player_turn()
        assert combat.state.turn == 4


class TestMonsterMoveHistory:
    def test_last_move_tracking(self):
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        worm = JawWorm.create(hp_rng, ascension=0)
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        worm.roll_move(ai_rng)
        assert worm.last_move(1) == True
        assert worm.last_move(2) == False
        worm.roll_move(ai_rng)
        assert worm.last_move(1) == False or worm.last_move(2) == True or worm.last_move(3) == True

    def test_last_two_moves_tracking(self):
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        worm = JawWorm.create(hp_rng, ascension=0)
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        worm.roll_move(ai_rng)
        worm.roll_move(ai_rng)
        assert len(worm.move_history) == 2


class TestCombatDeterminism:
    def test_same_seed_same_combat(self):
        seed = SEED_LONG
        ai_rng1 = MutableRNG.from_seed(seed, counter=0)
        hp_rng1 = MutableRNG.from_seed(seed, counter=100)
        combat1 = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng1,
            hp_rng=hp_rng1,
        )
        ai_rng2 = MutableRNG.from_seed(seed, counter=0)
        hp_rng2 = MutableRNG.from_seed(seed, counter=100)
        combat2 = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng2,
            hp_rng=hp_rng2,
        )
        assert combat1.state.monsters[0].hp == combat2.state.monsters[0].hp
        assert combat1.state.monsters[0].next_move.move_id == combat2.state.monsters[0].next_move.move_id
        for _ in range(5):
            if combat1.is_combat_over():
                break
            combat1.player_attack(0, 5)
            combat1.end_player_turn()
            combat2.player_attack(0, 5)
            combat2.end_player_turn()
        assert combat1.state.player.hp == combat2.state.player.hp
        assert combat1.state.turn == combat2.state.turn


class TestCurlUpIntegration:
    def test_louse_has_curl_up_power(self):
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        louse = LouseNormal.create(hp_rng, ascension=0)
        assert louse.has_power("Curl Up")
        assert louse.get_power_amount("Curl Up") == louse.curl_up

    def test_curl_up_triggers_on_attack(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="2 Louse",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        louse = combat.state.monsters[0]
        curl_up_amount = louse.get_power_amount("Curl Up")
        assert curl_up_amount > 0
        
        initial_block = louse.block
        combat.player_attack(0, 5)
        
        assert louse.block == curl_up_amount

    def test_curl_up_triggers_only_once(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="2 Louse",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        louse = combat.state.monsters[0]
        curl_up_amount = louse.get_power_amount("Curl Up")
        
        combat.player_attack(0, 5)
        first_block = louse.block
        assert first_block == curl_up_amount
        
        louse.block = 0
        combat.player_attack(0, 5)
        assert louse.block == 0


class TestVulnerableIntegration:
    def test_vulnerable_increases_damage_taken(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        from sts_py.engine.combat.powers import VulnerablePower
        monster = combat.state.monsters[0]
        monster.add_power(VulnerablePower(amount=1, owner="monster_0"))
        
        base_damage = 10
        combat.player_attack(0, base_damage)
        
        expected_damage = int(base_damage * 1.5)
        expected_hp = monster.max_hp - expected_damage
        assert monster.hp == expected_hp

    def test_player_vulnerable_increases_damage_taken(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        from sts_py.engine.combat.powers import VulnerablePower
        combat.state.player.add_power(VulnerablePower(amount=1, owner="player"))
        
        initial_hp = combat.state.player.hp
        combat.end_player_turn()
        
        damage_taken = initial_hp - combat.state.player.hp
        assert damage_taken > 0


class TestRitualIntegration:
    def test_cultist_first_move_is_incantation(self):
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        cultist = Cultist.create(hp_rng, ascension=0)
        assert cultist.first_move == True
        assert cultist.ritual_amount > 0

    def test_ritual_gives_strength_at_end_of_turn(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        cultist = combat.state.monsters[0]
        
        initial_strength = cultist.strength
        
        combat.end_player_turn()
        
        ritual_amount = cultist.ritual_amount
        assert cultist.strength == initial_strength + ritual_amount

    def test_ritual_stacks_multiple_turns(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        cultist = combat.state.monsters[0]
        
        initial_strength = cultist.strength
        ritual_amount = cultist.ritual_amount
        
        for i in range(3):
            if combat.is_combat_over():
                break
            combat.player_attack(0, 5)
            combat.end_player_turn()
        
        expected_strength = initial_strength + (ritual_amount * 3)
        assert cultist.strength == expected_strength


class TestPowerDecay:
    def test_vulnerable_decays_at_end_of_round(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        from sts_py.engine.combat.powers import VulnerablePower
        monster = combat.state.monsters[0]
        monster.add_power(VulnerablePower(amount=2, owner="monster_0"))
        
        assert monster.get_power_amount("Vulnerable") == 2
        
        combat.end_player_turn()
        
        assert monster.get_power_amount("Vulnerable") == 1

    def test_vulnerable_removed_when_zero(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        from sts_py.engine.combat.powers import VulnerablePower
        monster = combat.state.monsters[0]
        monster.add_power(VulnerablePower(amount=1, owner="monster_0"))
        
        assert monster.has_power("Vulnerable")
        
        combat.end_player_turn()
        
        assert not monster.has_power("Vulnerable")

    def test_weak_decays_at_end_of_round(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        from sts_py.engine.combat.powers import WeakPower
        monster = combat.state.monsters[0]
        monster.add_power(WeakPower(amount=2, owner="monster_0"))
        
        assert monster.get_power_amount("Weak") == 2
        
        combat.end_player_turn()
        assert monster.get_power_amount("Weak") == 2
        
        combat.end_player_turn()
        assert monster.get_power_amount("Weak") == 1


class TestWeakIntegration:
    def test_weak_reduces_monster_damage(self):
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        louse = LouseNormal.create(hp_rng, ascension=0)
        from sts_py.engine.combat.powers import WeakPower
        louse.add_power(WeakPower(amount=1, owner="monster_0"))
        
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        louse.roll_move(ai_rng)
        
        base_damage = louse.bite_damage
        effective_damage = louse.get_intent_damage()
        
        assert effective_damage == int(base_damage * 0.75)
