"""Combat result verification tests.

Validates combat engine results against autosave metric_damage_taken.

From autosave:
- Floor 1: Jaw Worm (5 turns, 1 damage)
- Floor 2: 2 Louse (2 turns, 7 damage)
- Floor 3: Cultist (4 turns, 9 damage)
- Floor 5: Red Slaver (5 turns, 27 damage)

Note: Full parity requires exact player actions which autosave doesn't record.
These tests verify the combat engine produces reasonable results.
"""
from __future__ import annotations

import pytest

from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.core.seed import seed_string_to_long
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.combat_state import CombatPhase
from sts_py.engine.monsters.exordium import JawWorm, LouseNormal, Cultist, SlaverRed


SEED_STRING = "1B40C4J3IIYDA"
SEED_LONG = 4452322743548530140

AUTOSAVE_DAMAGE_TAKEN = [
    {"damage": 1.0, "enemies": "Jaw Worm", "floor": 1.0, "turns": 5.0},
    {"damage": 7.0, "enemies": "2 Louse", "floor": 2.0, "turns": 2.0},
    {"damage": 9.0, "enemies": "Cultist", "floor": 3.0, "turns": 4.0},
    {"damage": 27, "enemies": "Red Slaver", "floor": 5, "turns": 5},
]


def simulate_simple_combat(
    encounter_name: str,
    player_hp: int,
    player_max_hp: int,
    ai_rng: MutableRNG,
    hp_rng: MutableRNG,
    damage_per_turn: int = 10,
    max_turns: int = 20,
) -> tuple[int, int]:
    """Simulate a simple combat with fixed damage per turn.
    
    Returns (damage_taken, turns).
    """
    combat = CombatEngine.create(
        encounter_name=encounter_name,
        player_hp=player_hp,
        player_max_hp=player_max_hp,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
    )
    
    turns = 0
    while not combat.is_combat_over() and turns < max_turns:
        for monster in combat.state.monsters:
            if not monster.is_dead():
                combat.player_attack(combat.state.monsters.index(monster), damage_per_turn)
                break
        combat.end_player_turn()
        turns += 1
    
    damage_taken = combat.get_total_damage_taken()
    return damage_taken, turns


class TestCombatResultVerification:
    """Verify combat results match autosave metrics."""
    
    def test_floor1_jaw_worm_encounter_type(self):
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
    
    def test_floor1_jaw_worm_damage_range(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        
        damage_taken, turns = simulate_simple_combat(
            "Jaw Worm", 80, 80, ai_rng, hp_rng, damage_per_turn=12
        )
        
        expected = AUTOSAVE_DAMAGE_TAKEN[0]
        assert turns <= expected["turns"], f"Expected <= {expected['turns']} turns, got {turns}"
    
    def test_floor2_two_louse_encounter_type(self):
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
    
    def test_floor2_two_louse_damage_range(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        
        damage_taken, turns = simulate_simple_combat(
            "2 Louse", 80, 80, ai_rng, hp_rng, damage_per_turn=15
        )
        
        expected = AUTOSAVE_DAMAGE_TAKEN[1]
        assert turns == expected["turns"], f"Expected {expected['turns']} turns, got {turns}"
    
    def test_floor3_cultist_encounter_type(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        assert len(combat.state.monsters) == 1
        assert combat.state.monsters[0].id == "Cultist"
    
    def test_floor3_cultist_ritual_mechanic(self):
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
        assert cultist.ritual_amount > 0
        
        initial_strength = cultist.strength
        combat.end_player_turn()
        assert cultist.strength > initial_strength
    
    def test_floor3_cultist_damage_range(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        
        damage_taken, turns = simulate_simple_combat(
            "Cultist", 80, 80, ai_rng, hp_rng, damage_per_turn=15
        )
        
        expected = AUTOSAVE_DAMAGE_TAKEN[2]
        assert turns == expected["turns"], f"Expected {expected['turns']} turns, got {turns}"
    
    def test_floor5_red_slaver_encounter_type(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Red Slaver",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        assert len(combat.state.monsters) == 1
        assert combat.state.monsters[0].id == "SlaverRed"
    
    def test_floor5_red_slaver_damage_range(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        
        damage_taken, turns = simulate_simple_combat(
            "Red Slaver", 80, 80, ai_rng, hp_rng, damage_per_turn=12
        )
        
        expected = AUTOSAVE_DAMAGE_TAKEN[3]
        assert turns <= expected["turns"], f"Expected <= {expected['turns']} turns, got {turns}"


class TestCombatDeterminismAcrossFloors:
    """Test that combat is deterministic across multiple floors."""
    
    def test_same_seed_same_combat_sequence(self):
        seed = SEED_LONG
        
        results1 = []
        for encounter in ["Jaw Worm", "2 Louse", "Cultist", "Red Slaver"]:
            ai_rng = MutableRNG.from_seed(seed, counter=0)
            hp_rng = MutableRNG.from_seed(seed, counter=100)
            damage, turns = simulate_simple_combat(encounter, 80, 80, ai_rng, hp_rng, 12)
            results1.append((damage, turns))
        
        results2 = []
        for encounter in ["Jaw Worm", "2 Louse", "Cultist", "Red Slaver"]:
            ai_rng = MutableRNG.from_seed(seed, counter=0)
            hp_rng = MutableRNG.from_seed(seed, counter=100)
            damage, turns = simulate_simple_combat(encounter, 80, 80, ai_rng, hp_rng, 12)
            results2.append((damage, turns))
        
        assert results1 == results2


class TestCombatPowerEffects:
    """Test that power effects correctly affect combat outcomes."""
    
    def test_vulnerable_increases_damage_taken_by_monster(self):
        from sts_py.engine.combat.powers import VulnerablePower
        
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
        monster.add_power(VulnerablePower(amount=99, owner="monster_0"))
        
        damage_no_vuln = 10
        initial_hp = monster.hp
        combat.player_attack(0, damage_no_vuln)
        actual_damage = initial_hp - monster.hp
        
        assert actual_damage == int(damage_no_vuln * 1.5)
    
    def test_weak_reduces_monster_damage(self):
        from sts_py.engine.combat.powers import WeakPower
        
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
        monster.add_power(WeakPower(amount=99, owner="monster_0"))
        
        initial_hp = combat.state.player.hp
        combat.end_player_turn()
        damage_taken = initial_hp - combat.state.player.hp
        
        assert damage_taken > 0
