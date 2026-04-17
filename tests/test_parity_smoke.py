from sts_py.engine.run.run_engine import RunEngine, RoomType
from sts_py.tools.compare_logs import JavaGameLog


def test_initial_deck_matches_ground_truth(real_java_log: JavaGameLog) -> None:
    log = real_java_log
    engine = RunEngine.create(log.seed_string, ascension=0)

    actual = [cid.replace("_R", "") for cid in engine.state.deck]
    expected = [card.card_id.replace("_R", "") for card in log.initial_deck]
    assert actual == expected

def test_initial_relics_match_ground_truth(real_java_log: JavaGameLog) -> None:
    log = real_java_log
    engine = RunEngine.create(log.seed_string, ascension=0)

    actual = [r.replace(" ", "") for r in engine.state.relics]
    expected = [r.replace(" ", "") for r in log.initial_relics]
    assert actual == expected


def test_floor_1_ground_truth_path_is_available(real_java_log: JavaGameLog) -> None:
    log = real_java_log
    engine = RunEngine.create(log.seed_string, ascension=0)

    first_step = log.path_taken[0]
    available = engine.get_available_paths()

    assert any(node.x == first_step.x and node.y == first_step.y for node in available)


def test_choose_ground_truth_floor_1_path_enters_monster_room(real_java_log: JavaGameLog) -> None:
    log = real_java_log
    engine = RunEngine.create(log.seed_string, ascension=0)

    first_step = log.path_taken[0]
    chosen = next(node for node in engine.get_available_paths() if node.x == first_step.x and node.y == first_step.y)

    assert chosen.room_type == RoomType.MONSTER
    assert engine.choose_path(chosen.node_id)
    assert engine.state.floor == 1
    assert engine.state.phase.value == "combat"
    assert engine.state.path_trace[0]["x"] == first_step.x
    assert engine.state.path_trace[0]["y"] == first_step.y
    assert engine.state.path_trace[0]["room_type"] == RoomType.MONSTER.value
