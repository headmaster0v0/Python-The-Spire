"""Run flow tests for headless STS simulation.

Tests the complete run state machine including:
- Map navigation
- Combat transitions
- Card rewards
- HP tracking
"""
from __future__ import annotations

import pytest

from sts_py.engine.run.run_engine import RunEngine, RunPhase, RoomType


SEED_STRING = "1B40C4J3IIYDA"


def _choose_first_available_path(engine: RunEngine) -> int:
    paths = engine.get_available_paths()
    assert len(paths) >= 1
    return paths[0].node_id


class TestRunEngineCreation:
    def test_create_run_engine(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        assert engine.state.seed_string == SEED_STRING
        assert engine.state.phase == RunPhase.NEOW
        assert engine.state.floor == 0

    def test_initial_deck(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        assert len(engine.state.deck) == 10
        assert "Strike" in engine.state.deck
        assert "Defend" in engine.state.deck
        assert "Bash" in engine.state.deck

    def test_initial_relics(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        assert "BurningBlood" in engine.state.relics

    def test_initial_hp(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        assert engine.state.player_hp == 80
        assert engine.state.player_max_hp == 80


class TestMapNavigation:
    def test_get_available_paths_initial(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        paths = engine.get_available_paths()
        assert len(paths) >= 1
        assert all(path.floor == 1 for path in paths)

    def test_choose_path_first_floor(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        node_id = _choose_first_available_path(engine)

        success = engine.choose_path(node_id)
        assert success
        assert engine.state.floor == 1
        assert len(engine.state.path_taken) == 1

    def test_path_taken_records_room_type(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        paths = engine.get_available_paths()
        chosen = paths[0]
        engine.choose_path(chosen.node_id)
        assert engine.state.path_taken[-1] == chosen.room_type.value

    def test_path_trace_records_coordinates(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        chosen = engine.get_available_paths()[0]
        engine.choose_path(chosen.node_id)
        trace = engine.state.path_trace[-1]
        assert trace["floor"] == chosen.floor
        assert trace["x"] == chosen.x
        assert trace["y"] == chosen.y
        assert trace["room_type"] == chosen.room_type.value


class TestCombatTransition:
    def test_enter_monster_room_starts_combat(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        monster_path = next(path for path in engine.get_available_paths() if path.room_type == RoomType.MONSTER)
        engine.choose_path(monster_path.node_id)

        assert engine.state.phase == RunPhase.COMBAT
        assert engine.state.combat is not None

    def test_combat_engine_created(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        monster_path = next(path for path in engine.get_available_paths() if path.room_type == RoomType.MONSTER)
        engine.choose_path(monster_path.node_id)

        assert engine.state.combat is not None
        assert len(engine.state.combat.state.monsters) == 1

    def test_combat_actions(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        monster_path = next(path for path in engine.get_available_paths() if path.room_type == RoomType.MONSTER)
        engine.choose_path(monster_path.node_id)

        monster = engine.state.combat.state.monsters[0]
        initial_hp = monster.hp

        engine.combat_attack(0, 10)
        assert monster.hp < initial_hp


class TestCombatResolution:
    def test_win_combat_transitions_to_reward(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        monster_path = next(path for path in engine.get_available_paths() if path.room_type == RoomType.MONSTER)
        engine.choose_path(monster_path.node_id)

        while not engine.is_combat_over():
            engine.combat_attack(0, 20)
            engine.combat_end_turn()

        engine.end_combat()
        assert engine.state.phase == RunPhase.REWARD

    def test_damage_tracked(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        monster_path = next(path for path in engine.get_available_paths() if path.room_type == RoomType.MONSTER)
        engine.choose_path(monster_path.node_id)

        initial_hp = engine.state.player_hp

        while not engine.is_combat_over():
            engine.combat_attack(0, 20)
            engine.combat_end_turn()

        engine.end_combat()

        assert engine.state.player_hp <= initial_hp
        assert len(engine.state.combat_history) == 1


class TestCardRewards:
    def test_choose_card_adds_to_deck(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        monster_path = next(path for path in engine.get_available_paths() if path.room_type == RoomType.MONSTER)
        engine.choose_path(monster_path.node_id)

        while not engine.is_combat_over():
            engine.combat_attack(0, 20)
            engine.combat_end_turn()

        engine.end_combat()

        initial_deck_size = len(engine.state.deck)
        engine.choose_card_reward("Anger", ["Clash", "Cleave"])

        assert len(engine.state.deck) == initial_deck_size + 1
        assert "Anger" in engine.state.deck

    def test_card_choice_recorded(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        monster_path = next(path for path in engine.get_available_paths() if path.room_type == RoomType.MONSTER)
        engine.choose_path(monster_path.node_id)

        while not engine.is_combat_over():
            engine.combat_attack(0, 20)
            engine.combat_end_turn()

        engine.end_combat()

        engine.choose_card_reward("Anger", ["Clash", "Cleave"])

        assert len(engine.state.card_choices) == 1
        assert engine.state.card_choices[0]["picked"] == "Anger"


class TestRestSiteCardRewards:
    def test_dream_catcher_rest_enters_reward_phase(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.phase = RunPhase.REST
        engine.state.floor = 6
        engine.state.relics.append("DreamCatcher")

        engine.rest()

        assert engine.state.phase == RunPhase.REWARD
        assert len(engine.state.pending_card_reward_cards) == 3

    def test_choose_rest_card_reward_clears_pending_candidates(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.phase = RunPhase.REST
        engine.state.floor = 6
        engine.state.relics.append("DreamCatcher")

        engine.rest()
        pending = list(engine.state.pending_card_reward_cards)
        picked = pending[0]

        engine.choose_card_reward(picked, [])

        assert engine.state.phase == RunPhase.MAP
        assert engine.state.pending_card_reward_cards == []
        assert engine.state.card_choices[-1]["picked"] == picked
        assert sorted(engine.state.card_choices[-1]["not_picked"]) == sorted(pending[1:])

    def test_non_card_rest_relics_still_return_to_map(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.phase = RunPhase.REST
        engine.state.relics.append("AncientTeaSet")

        engine.rest()

        assert engine.state.phase == RunPhase.MAP
        assert engine.state.player_pending_tea_energy == 2
        assert engine.state.pending_card_reward_cards == []


class TestMultipleFloors:
    def test_progress_through_floors(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)

        for expected_floor in range(1, 4):
            paths = engine.get_available_paths()
            if not paths:
                break

            chosen = paths[0]
            engine.choose_path(chosen.node_id)

            if engine.state.phase == RunPhase.COMBAT:
                while not engine.is_combat_over():
                    engine.combat_attack(0, 30)
                    engine.combat_end_turn()
                engine.end_combat()
                engine.choose_card_reward("Anger", ["Clash", "Cleave"])
            elif engine.state.phase in (RunPhase.EVENT, RunPhase.SHOP, RunPhase.REST, RunPhase.TREASURE):
                engine.state.phase = RunPhase.MAP

            assert engine.state.floor == expected_floor


class TestRunDeterminism:
    def test_same_seed_same_path(self):
        engine1 = RunEngine.create(SEED_STRING, ascension=0)
        engine2 = RunEngine.create(SEED_STRING, ascension=0)

        paths1 = engine1.get_available_paths()
        paths2 = engine2.get_available_paths()

        assert len(paths1) == len(paths2)
        assert [path.room_type for path in paths1] == [path.room_type for path in paths2]
        assert [(path.x, path.y) for path in paths1] == [(path.x, path.y) for path in paths2]

    def test_same_seed_same_combat(self):
        engine1 = RunEngine.create(SEED_STRING, ascension=0)
        engine2 = RunEngine.create(SEED_STRING, ascension=0)

        monster_path1 = next(path for path in engine1.get_available_paths() if path.room_type == RoomType.MONSTER)
        monster_path2 = next(path for path in engine2.get_available_paths() if path.room_type == RoomType.MONSTER and path.x == monster_path1.x and path.y == monster_path1.y)
        engine1.choose_path(monster_path1.node_id)
        engine2.choose_path(monster_path2.node_id)

        m1 = engine1.state.combat.state.monsters[0]
        m2 = engine2.state.combat.state.monsters[0]

        assert m1.id == m2.id
        assert m1.hp == m2.hp


class TestStateHash:
    def test_state_hash_is_consistent(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        hash1 = engine.get_state_hash()
        hash2 = engine.get_state_hash()
        assert hash1 == hash2

    def test_state_hash_changes_on_action(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        hash_before = engine.get_state_hash()

        engine.choose_path(_choose_first_available_path(engine))
        hash_after = engine.get_state_hash()

        assert hash_before != hash_after
