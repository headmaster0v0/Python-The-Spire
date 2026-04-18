from __future__ import annotations

import json

import sts_py.engine.run.run_engine as run_engine_module
from sts_py.engine.run.events import build_event
from sts_py.engine.run.run_engine import RunEngine, RunPhase
from sts_py.tools.wiki_audit import _generic_en_page_candidates, build_event_source_facts


def _win_current_combat(engine: RunEngine) -> None:
    assert engine.state.combat is not None
    for monster in engine.state.combat.state.monsters:
        monster.hp = 0
        monster.is_dying = True
    engine.end_combat()


def test_phase273_colosseum_reopens_after_slavers_and_only_grants_custom_rewards() -> None:
    engine = RunEngine.create("PHASE273COLOSSEUM", ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine._set_current_event(build_event("Colosseum"))

    first = engine.choose_event_option(0)
    second = engine.choose_event_option(0)

    assert first["event_continues"] is True
    assert second["action"] == "combat"
    _win_current_combat(engine)

    reopened = engine.get_current_event()
    assert reopened is not None
    assert engine.state.phase == RunPhase.EVENT
    assert [choice.description for choice in reopened.choices] == ["[COWARDICE] Escape.", "[VICTORY] A powerful fight with many rewards."]
    assert engine.get_pending_reward_state() == {"cards": [], "gold": 0, "potion": None, "relic": None, "relics": []}

    third = engine.choose_event_option(0)

    assert third["action"] == "combat"
    _win_current_combat(engine)

    pending = engine.get_pending_reward_state()
    assert engine.state.phase == RunPhase.REWARD
    assert pending["cards"] == []
    assert pending["gold"] == 100
    assert len(pending["relics"]) == 2


def test_phase273_cursed_tome_progression_tracks_page_damage_and_book_reward() -> None:
    engine = RunEngine.create("PHASE273TOME", ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine._set_current_event(build_event("Cursed Tome"))

    assert engine.choose_event_option(0)["event_continues"] is True
    assert engine.choose_event_option(0)["event_continues"] is True
    assert engine.choose_event_option(0)["event_continues"] is True
    assert engine.choose_event_option(0)["event_continues"] is True
    final = engine.choose_event_option(0)

    assert final["event_continues"] is True
    assert engine.state.player_hp == 64
    assert engine.get_pending_reward_state()["relic"] in {"Necronomicon", "Enchiridion", "NilrysCodex", "Circlet"}


def test_phase273_note_for_yourself_uses_engine_owned_prefs_store(tmp_path, monkeypatch) -> None:
    prefs_path = tmp_path / "note_for_yourself.json"
    prefs_path.write_text(json.dumps({"card_id": "Anger", "upgrades": 0}), encoding="utf-8")
    monkeypatch.setattr(run_engine_module, "NOTE_FOR_YOURSELF_PREFS_PATH", prefs_path)

    engine = RunEngine.create("PHASE273NOTE", ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine.state.deck = ["Strike"]
    engine._set_current_event(build_event("NoteForYourself"))

    first = engine.choose_event_option(0)
    second = engine.choose_event_option(0)
    third = engine.choose_card_for_event(0)

    assert first["event_continues"] is True
    assert second["requires_card_choice"] is True
    assert third["action"] == "stored_card"
    assert engine.state.deck == ["Anger"]
    assert json.loads(prefs_path.read_text(encoding="utf-8")) == {"card_id": "Strike", "upgrades": 0}


def test_phase273_wheel_of_change_remove_card_result_uses_real_remove_prompt(monkeypatch) -> None:
    engine = RunEngine.create("PHASE273WHEEL", ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine.state.deck = ["Strike", "Bash"]
    engine._set_current_event(build_event("Wheel of Change"))
    monkeypatch.setattr(engine.state.rng.event_rng, "random_int", lambda upper: 4)

    first = engine.choose_event_option(0)
    second = engine.choose_event_option(0)

    assert first["event_continues"] is True
    assert second["requires_card_choice"] is True
    assert engine.state.pending_card_choice is not None
    assert engine.state.pending_card_choice["prompt"] == "Select a Card to Remove."
    third = engine.choose_card_for_event(1)
    assert third["action"] == "card_removed"
    assert third["card_id"] == "Bash"


def test_phase273_sensory_stone_adds_requested_colorless_cards() -> None:
    engine = RunEngine.create("PHASE273SENSORY", ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine._set_current_event(build_event("SensoryStone"))
    engine.state.rng.event_rng.random_int = lambda upper: 0  # type: ignore[method-assign]

    first = engine.choose_event_option(0)
    second = engine.choose_event_option(2)

    assert first["event_continues"] is True
    assert second["action"] == "recalled"
    assert len(second["cards"]) == 3
    assert engine.state.deck[-3:] == second["cards"]
    assert second["hp_loss"] == 10


def test_phase273_spire_heart_branches_to_act4_or_game_over() -> None:
    act4_engine = RunEngine.create("PHASE273HEARTACT4", ascension=0)
    act4_engine.state.phase = RunPhase.EVENT
    act4_engine.state.ruby_key_obtained = True
    act4_engine.state.emerald_key_obtained = True
    act4_engine.state.sapphire_key_obtained = True
    act4_engine._set_current_event(build_event("SpireHeart"))

    act4_engine.choose_event_option(0)
    act4_engine.choose_event_option(0)
    act4_engine.choose_event_option(0)
    result = act4_engine.choose_event_option(0)

    assert result["action"] == "enter_act4"
    assert act4_engine.state.act == 4
    assert act4_engine.state.phase == RunPhase.MAP

    death_engine = RunEngine.create("PHASE273HEARTDEATH", ascension=0)
    death_engine.state.phase = RunPhase.EVENT
    death_engine._set_current_event(build_event("SpireHeart"))

    death_engine.choose_event_option(0)
    death_engine.choose_event_option(0)
    death_engine.choose_event_option(0)
    death_result = death_engine.choose_event_option(0)

    assert death_result["action"] == "game_over"
    assert death_engine.state.phase == RunPhase.GAME_OVER


def test_phase273_wiki_audit_event_flow_facts_and_alias_candidates_cover_closeout_events() -> None:
    colosseum = build_event_source_facts(build_event("Colosseum"))
    match_game = build_event_source_facts(build_event("Match and Keep!"))
    wheel = build_event_source_facts(build_event("Wheel of Change"))

    assert colosseum["flow_kind"] == "event_combat_reentry"
    assert colosseum["event_combat_reentry"] is True
    assert match_game["dynamic_option_slots"] == 12
    assert wheel["reward_surface"] == "mixed"
    assert "A Note For Yourself" in _generic_en_page_candidates("event", "NoteForYourself", "A Note For Yourself")
    assert "The Divine Fountain" in _generic_en_page_candidates("event", "Fountain of Cleansing", "Fountain of Cleansing")
