"""Test ACT transition after defeating BOSS"""
from __future__ import annotations

import pytest
from sts_py.engine.run.run_engine import RunEngine, RoomType, RunPhase


class TestActTransition:
    def test_boss_at_last_row(self):
        """BOSS should be at row 14 (last row)"""
        engine = RunEngine.create("TESTACT123", ascension=0)

        boss_nodes = [n for n in engine.state.map_nodes if n.room_type == RoomType.BOSS]
        assert len(boss_nodes) > 0, "Should have at least one BOSS"

        for boss in boss_nodes:
            assert boss.y == 14, f"BOSS should be at row 14, got row {boss.y}"

    def test_rest_not_after_boss(self):
        """REST should not be at row 14 (after BOSS)"""
        engine = RunEngine.create("TESTACT456", ascension=0)

        rest_at_row_14 = [n for n in engine.state.map_nodes
                          if n.room_type == RoomType.REST and n.y == 14]
        assert len(rest_at_row_14) == 0, "REST should not be at row 14 (BOSS is there)"

    def test_rest_at_row_13(self):
        """REST should be at row 13 (before BOSS)"""
        engine = RunEngine.create("TESTACT789", ascension=0)

        rest_at_row_13 = [n for n in engine.state.map_nodes
                         if n.room_type == RoomType.REST and n.y == 13]
        assert len(rest_at_row_13) > 0, "Should have REST at row 13"

    def test_transition_to_next_act_restores_hp(self):
        """transition_to_next_act should restore player to full HP"""
        engine = RunEngine.create("TESTTRANS1", ascension=0)

        original_max_hp = engine.state.player_max_hp
        engine.state.player_hp = original_max_hp - 10
        engine.state.phase = RunPhase.VICTORY

        engine.transition_to_next_act()

        assert engine.state.act == 2, f"Should be in ACT 2, got ACT {engine.state.act}"
        assert engine.state.player_hp == original_max_hp, (
            f"HP should be restored to max ({original_max_hp}), got {engine.state.player_hp}"
        )

    def test_transition_to_next_act_resets_state(self):
        """transition_to_next_act should reset floor for new act (but keep continuous numbering)

        Wiki: Act 1 spans F01-F17, Act 2 spans F18-F34, etc.
        When transitioning to Act 2, floor should be 17 (Act 1 has 17 floors).
        """
        engine = RunEngine.create("TESTTRANS2", ascension=0)

        engine.state.floor = 15
        engine.state.path_taken = ["M", "M", "E"]
        engine.state.combat_history = [{"floor": 10, "damage": 5}]
        engine.state.phase = RunPhase.VICTORY

        engine.transition_to_next_act()

        assert engine.state.floor == 17, f"Floor should be 17 (Act 1 ends at F17), got {engine.state.floor}"
        assert len(engine.state.path_taken) == 0, "path_taken should be reset"
        assert len(engine.state.combat_history) == 0, "combat_history should be reset"

    def test_transition_generates_new_map(self):
        """transition_to_next_act should generate a new map for ACT 2"""
        engine = RunEngine.create("TESTMAP1", ascension=0)

        act1_map_hash = hash(tuple(sorted((n.x, n.y, n.room_type) for n in engine.state.map_nodes)))

        engine.state.phase = RunPhase.VICTORY
        engine.transition_to_next_act()

        act2_map_hash = hash(tuple(sorted((n.x, n.y, n.room_type) for n in engine.state.map_nodes)))
        assert act2_map_hash != act1_map_hash, "ACT 2 map should be different from ACT 1 map"

    def test_third_act_victory_ends_game_without_keys(self):
        """After defeating ACT 3 BOSS without all keys, transition_to_next_act should do nothing"""
        engine = RunEngine.create("TESTFINAL", ascension=0)

        engine.state.act = 3
        engine.state.phase = RunPhase.VICTORY

        engine.transition_to_next_act()

        assert engine.state.act == 3, "ACT should still be 3"
        assert engine.state.phase == RunPhase.VICTORY, "Should still be VICTORY"

    def test_third_act_victory_with_keys_enters_act4(self):
        engine = RunEngine.create("TESTACT4", ascension=0)

        engine.state.act = 3
        engine.state.phase = RunPhase.VICTORY
        engine.state.ruby_key_obtained = True
        engine.state.emerald_key_obtained = True
        engine.state.sapphire_key_obtained = True

        engine.transition_to_next_act()

        assert engine.state.act == 4
        assert engine.state.phase == RunPhase.MAP
        assert [node.room_type for node in engine.state.map_nodes] == [
            RoomType.REST,
            RoomType.SHOP,
            RoomType.ELITE,
            RoomType.BOSS,
        ]
        assert [node.floor for node in engine.state.map_nodes] == [52, 53, 54, 55]

    def test_transition_changes_phase_to_map(self):
        """transition_to_next_act should set phase to MAP"""
        engine = RunEngine.create("TESTPHASE", ascension=0)

        engine.state.phase = RunPhase.VICTORY
        engine.transition_to_next_act()

        assert engine.state.phase == RunPhase.MAP, f"Should be MAP, got {engine.state.phase}"
