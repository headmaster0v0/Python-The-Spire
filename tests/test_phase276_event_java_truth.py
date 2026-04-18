from __future__ import annotations

import re
from pathlib import Path

from sts_py.engine.run.events import build_event
from sts_py.engine.run.run_engine import RunEngine, RunPhase
from sts_py.tools.wiki_audit import (
    _generic_cn_page_candidates,
    _generic_en_page_candidates,
    build_cli_raw_snapshot,
)


def _extract_first_number(text: str) -> int:
    match = re.search(r"(\d+)", text)
    assert match is not None
    return int(match.group(1))


def test_phase276_event_snapshot_uses_independent_java_truth_records() -> None:
    snapshot = build_cli_raw_snapshot(Path.cwd(), enable_network=False)

    dead_adventurer = next(
        item for item in snapshot["records"]
        if item["entity_type"] == "event" and item["entity_id"] == "Dead Adventurer"
    )
    neow = next(
        item for item in snapshot["records"]
        if item["entity_type"] == "neow" and item["entity_id"] == "NeowEvent"
    )

    assert dead_adventurer["runtime_facts"]["source_kind"] == "python_run_source"
    assert dead_adventurer["java_facts"]["source_kind"] == "decompiled_event_source"
    assert dead_adventurer["java_facts"]["java_class"] == "DeadAdventurer"
    assert dead_adventurer["java_facts"]["initial_option_count"] == 2
    assert neow["runtime_facts"]["source_kind"] == "python_run_source"
    assert neow["java_facts"]["source_kind"] == "official_neow_source"


def test_phase276_event_wiki_alias_candidates_cover_known_live_page_gaps() -> None:
    assert "Designer In-Spire" in _generic_en_page_candidates("event", "Designer", "Designer In-Spire")
    assert "Match and Keep" in _generic_en_page_candidates("event", "Match and Keep!", "Match and Keep!")
    assert "Hypnotizing Colored Mushrooms" in _generic_en_page_candidates("event", "Mushrooms", "Mushrooms")
    assert "Corrupt Heart" in _generic_en_page_candidates("event", "SpireHeart", "Spire Heart")
    assert "尖端设计师" in _generic_cn_page_candidates("event", "Designer", "“尖端”设计师", "Designer In-Spire")
    assert "高塔之心" in _generic_cn_page_candidates("event", "SpireHeart", "高塔之心", "Corrupt Heart")


def test_phase276_dead_adventurer_runtime_uses_java_a15_chance_and_lagavulin_branch(monkeypatch) -> None:
    engine = RunEngine.create("PHASE276DEAD", ascension=15)
    engine.state.floor = 10
    engine.state.phase = RunPhase.EVENT
    engine.state.dead_adventurer_state = {
        "searches_done": 0,
        "rewards_given": {"gold": False, "nothing": False, "relic": False},
        "encounter_triggered": False,
        "monster_type": None,
        "enemy_index": 2,
        "continuation_mode": False,
    }
    monkeypatch.setattr(engine.state.rng.misc_rng, "random_int", lambda upper: 0)

    engine._set_current_event(build_event("Dead Adventurer", engine.state.rng.event_rng))
    event = engine.get_current_event()

    assert event is not None
    assert len(event.choices) == 2
    assert "35" in event.choices[0].description

    result = engine.choose_event_option(0)

    assert result["action"] == "encounter"
    assert result["monster"] == "Lagavulin Event"


def test_phase276_world_of_goop_runtime_keeps_java_a15_gold_loss_roll() -> None:
    engine = RunEngine.create("PHASE276GOOP", ascension=15)
    engine.state.floor = 10
    engine.state.phase = RunPhase.EVENT
    engine._set_current_event(build_event("World of Goop"))

    event = engine.get_current_event()
    assert event is not None
    choice_text = event.choices[1].description
    shown_loss = _extract_first_number(choice_text)

    result = engine.choose_event_option(1)

    assert 35 <= shown_loss <= 75
    assert result["gold_lost"] == shown_loss


def test_phase276_scrap_ooze_runtime_uses_java_a15_damage_progression(monkeypatch) -> None:
    engine = RunEngine.create("PHASE276SCRAP", ascension=15)
    engine.state.floor = 10
    engine.state.phase = RunPhase.EVENT
    engine._set_current_event(build_event("Scrap Ooze"))

    event = engine.get_current_event()
    assert event is not None
    assert "5" in event.choices[0].description

    monkeypatch.setattr(engine.state.rng.misc_rng, "random_int", lambda upper: 99)
    result = engine.choose_event_option(0)

    assert result["action"] == "continue"
    assert result["damage_taken"] == 5

    updated = engine.get_current_event()
    assert updated is not None
    assert "6" in updated.choices[0].description


def test_phase276_shining_light_runtime_rounds_a15_damage_like_java() -> None:
    engine = RunEngine.create("PHASE276LIGHT", ascension=15)
    engine.state.floor = 10
    engine.state.phase = RunPhase.EVENT
    engine.state.player_max_hp = 73
    engine.state.player_hp = 73
    engine.state.deck = ["Bash", "Strike"]
    engine._set_current_event(build_event("Shining Light"))

    event = engine.get_current_event()
    assert event is not None
    assert "22" in event.choices[0].description

    result = engine.choose_event_option(0)

    assert result["action"] == "upgraded"
    assert result["hp_lost"] == 22


def test_phase276_golden_idol_trap_uses_java_a15_penalties() -> None:
    engine = RunEngine.create("PHASE276IDOL", ascension=15)
    engine.state.floor = 10
    engine.state.phase = RunPhase.EVENT
    engine._set_current_event(build_event("Golden Idol"))

    first = engine.choose_event_option(0)
    trapped = engine.get_current_event()

    assert first["action"] == "trap_triggered"
    assert trapped is not None
    assert trapped.event_id == "Golden Shrine Trap"
    assert "35" in trapped.choices[1].description
    assert "10" in trapped.choices[2].description
