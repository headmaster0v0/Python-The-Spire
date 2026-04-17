from __future__ import annotations

from sts_py.tools.compare_logs import JavaGameLog, RngState


def test_parse_java_log(real_java_log: JavaGameLog) -> None:
    log = real_java_log

    assert len(log.seed_string) > 0
    assert log.character == "IRONCLAD"
    assert log.end_floor > 0
    assert len(log.battles) > 0
    assert len(log.path_taken) > 0
    assert len(log.rng_calls) > 0
    assert isinstance(log.map_nodes, list)

def test_floor_1_battle_monsters(real_java_log: JavaGameLog) -> None:
    log = real_java_log
    battle = log.battles[0]

    assert battle.floor == 1
    assert battle.room_type == "MonsterRoom"
    assert len([monster.id for monster in battle.monsters]) > 0
    assert all(monster.starting_hp > 0 for monster in battle.monsters)
    assert battle.player_end_hp > 0
    assert battle.turn_count > 0

def test_floor_1_rng_state(real_java_log: JavaGameLog) -> None:
    log = real_java_log
    rng = log.battles[0].rng_state_end

    assert isinstance(rng, RngState)
    assert rng.card_rng_counter >= 0
    assert rng.monster_rng_counter >= 0
    assert rng.ai_rng_counter >= 0

def test_path_taken_structure(real_java_log: JavaGameLog) -> None:
    log = real_java_log

    assert len(log.path_taken) > 0
    assert log.path_taken[0].floor == 1
    assert log.path_taken[0].act == 1
    assert hasattr(log.path_taken[0], 'x')
    assert hasattr(log.path_taken[0], 'y')
    assert hasattr(log.path_taken[0], 'room_type')

def test_card_rewards(real_java_log: JavaGameLog) -> None:
    log = real_java_log

    assert len(log.card_rewards) > 0
    assert log.card_rewards[0].floor == 1
    assert len(log.card_rewards[0].card_id) > 0
    assert isinstance(log.card_rewards[0].upgraded, bool)
    assert isinstance(log.card_rewards[0].skipped, bool)

def test_rng_snapshots_dungeon_init(real_java_log: JavaGameLog) -> None:
    log = real_java_log
    snapshot = log.rng_snapshots[0]
    state = RngState.from_dict(snapshot["state"])

    assert snapshot["label"] == "dungeon_init"
    assert snapshot["floor"] == 0
    assert isinstance(state, RngState)

def test_neow_event(real_java_log: JavaGameLog) -> None:
    log = real_java_log

    assert len(log.event_choices) > 0
    neow = log.event_choices[1]
    assert neow.event_id == "NeowEvent"
    assert neow.choice_index >= 0
    assert len(neow.choice_text) > 0
