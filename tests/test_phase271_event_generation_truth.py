from __future__ import annotations

from sts_py.engine.run.events import (
    ACT1_EVENT_KEYS,
    ACT2_EVENT_KEYS,
    ACT3_EVENT_KEYS,
    SHRINE_EVENT_KEYS,
    SPECIAL_ONE_TIME_EVENT_KEYS,
)
from sts_py.engine.run.run_engine import RoomType, RunEngine, RunPhase


def test_phase271_initial_event_pools_match_java_truth() -> None:
    engine = RunEngine.create("PHASE271EVENTPOOLS", ascension=0)

    assert engine.state.event_list == ACT1_EVENT_KEYS
    assert engine.state.shrine_list == SHRINE_EVENT_KEYS
    assert engine.state.special_one_time_event_list == SPECIAL_ONE_TIME_EVENT_KEYS

    engine.transition_to_act_for_replay(2, floor=18)
    assert engine.state.event_list == ACT2_EVENT_KEYS
    assert engine.state.shrine_list == SHRINE_EVENT_KEYS

    engine.transition_to_act_for_replay(3, floor=35)
    assert engine.state.event_list == ACT3_EVENT_KEYS
    assert engine.state.shrine_list == SHRINE_EVENT_KEYS


def test_phase271_note_for_yourself_removed_at_ascension_15() -> None:
    engine = RunEngine.create("PHASE271NOSELFNOTE", ascension=15)

    assert "NoteForYourself" not in engine.state.special_one_time_event_list


def test_phase271_question_room_roll_uses_java_weighted_monster_and_juzu_redirect(monkeypatch) -> None:
    engine = RunEngine.create("PHASE271JUZU", ascension=0)
    engine.state.relics.append("JuzuBracelet")

    rolls = iter([0.05, 0.9])
    monkeypatch.setattr(engine.state.rng.event_rng, "random_float", lambda: next(rolls))
    monkeypatch.setattr(engine.state.rng.event_rng, "random_int", lambda upper: 0)

    engine._enter_question_room(3)

    assert engine.state.phase == RunPhase.EVENT
    assert engine.get_current_event() is not None
    assert engine.get_current_event().event_key == "Big Fish"
    assert engine.state.question_room_last_encounter == "event"


def test_phase271_question_room_roll_respects_shop_suppression(monkeypatch) -> None:
    engine = RunEngine.create("PHASE271SHOPSUPPRESS", ascension=0)
    engine.state.previous_room_type_for_event_roll = RoomType.SHOP.value
    engine.state.question_room_monster_chance = 0.0
    engine.state.question_room_shop_chance = 1.0
    engine.state.question_room_treasure_chance = 0.0

    rolls = iter([0.20, 0.90])
    monkeypatch.setattr(engine.state.rng.event_rng, "random_float", lambda: next(rolls))
    monkeypatch.setattr(engine.state.rng.event_rng, "random_int", lambda upper: 0)

    engine._enter_question_room(8)

    assert engine.state.phase == RunPhase.EVENT
    assert engine.get_current_event() is not None
    assert engine.get_current_event().event_key == "Big Fish"


def test_phase271_question_room_roll_respects_tiny_chest(monkeypatch) -> None:
    engine = RunEngine.create("PHASE271TINYCHEST", ascension=0)
    engine.state.relics.append("TinyChest")
    engine.state.relic_counters["TinyChest"] = 3
    monkeypatch.setattr(engine.state.rng.event_rng, "random_float", lambda: 0.0)

    engine._enter_question_room(9)

    assert engine.state.phase == RunPhase.TREASURE
    assert engine.state.relic_counters["TinyChest"] == 0


def test_phase271_secret_portal_gating_uses_playtime_seconds(monkeypatch) -> None:
    engine = RunEngine.create("PHASE271PORTALGATE", ascension=0)
    engine.transition_to_act_for_replay(3, floor=40)
    engine.state.event_list = []
    engine.state.shrine_list = []
    engine.state.special_one_time_event_list = ["SecretPortal"]
    monkeypatch.setattr(engine.state.rng.event_rng, "random_float", lambda: 0.0)
    monkeypatch.setattr(engine.state.rng.event_rng, "random_int", lambda upper: 0)

    engine.state.playtime_seconds = 799.0
    assert engine._generate_event_key() is None

    engine.state.special_one_time_event_list = ["SecretPortal"]
    engine.state.playtime_seconds = 800.0
    assert engine._generate_event_key() == "SecretPortal"


def test_phase271_special_one_time_event_does_not_revive_across_acts(monkeypatch) -> None:
    engine = RunEngine.create("PHASE271SPECIALONCE", ascension=0)
    engine.transition_to_act_for_replay(2, floor=20)
    engine.state.event_list = []
    engine.state.shrine_list = []
    engine.state.special_one_time_event_list = ["Designer"]
    monkeypatch.setattr(engine.state.rng.event_rng, "random_float", lambda: 0.0)
    monkeypatch.setattr(engine.state.rng.event_rng, "random_int", lambda upper: 0)

    engine._enter_event()

    assert engine.get_current_event() is not None
    assert engine.get_current_event().event_key == "Designer"
    assert "Designer" not in engine.state.special_one_time_event_list

    engine.transition_to_act_for_replay(3, floor=36)
    assert "Designer" not in engine.state.special_one_time_event_list
