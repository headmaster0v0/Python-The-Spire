from __future__ import annotations

import json

import sts_py.engine.run.run_engine as run_engine_module
from sts_py.engine.run.official_neow_strings import (
    get_official_neow_event_strings,
    get_official_neow_reward_strings,
)
from sts_py.engine.run.run_engine import RunEngine, RunPhase


def test_phase274_official_neow_snapshot_drives_intro_surface(tmp_path, monkeypatch) -> None:
    profile_path = tmp_path / "player_profile.json"
    monkeypatch.setattr(run_engine_module, "PLAYER_PROFILE_PATH", profile_path)
    monkeypatch.setattr(run_engine_module, "NOTE_FOR_YOURSELF_PREFS_PATH", tmp_path / "legacy_note.json")

    engine = RunEngine.create("PHASE274NEOWINTRO", ascension=0)
    event_strings = get_official_neow_event_strings()

    assert event_strings.names_en[0] == "Neow"
    assert engine.state.phase == RunPhase.NEOW
    assert engine.state.neow_screen == "intro"
    assert engine.state.neow_body == event_strings.text_en[0]
    assert engine.get_neow_options()[0]["label_en"] == event_strings.options_en[1]


def test_phase274_note_for_yourself_gating_uses_highest_unlocked_ascension_profile(tmp_path, monkeypatch) -> None:
    profile_path = tmp_path / "player_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "note_for_yourself": {"card_id": "Anger", "upgrades": 0},
                "characters": {
                    "IRONCLAD": {
                        "spirits": 0,
                        "highest_unlocked_ascension": 5,
                        "last_ascension_level": 5,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_engine_module, "PLAYER_PROFILE_PATH", profile_path)
    monkeypatch.setattr(run_engine_module, "NOTE_FOR_YOURSELF_PREFS_PATH", tmp_path / "legacy_note.json")

    lower = RunEngine.create("PHASE274NOTELOWER", ascension=4)
    equal = RunEngine.create("PHASE274NOTEEQUAL", ascension=5)

    assert "NoteForYourself" in lower.state.special_one_time_event_list
    assert "NoteForYourself" not in equal.state.special_one_time_event_list


def test_phase274_spirits_profile_unlocks_full_neow_blessing_after_dialog(tmp_path, monkeypatch) -> None:
    profile_path = tmp_path / "player_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "neow_intro_seen": True,
                "note_for_yourself": {"card_id": "IronWave", "upgrades": 0},
                "characters": {
                    "IRONCLAD": {
                        "spirits": 1,
                        "highest_unlocked_ascension": 1,
                        "last_ascension_level": 1,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_engine_module, "PLAYER_PROFILE_PATH", profile_path)
    monkeypatch.setattr(run_engine_module, "NOTE_FOR_YOURSELF_PREFS_PATH", tmp_path / "legacy_note.json")

    engine = RunEngine.create("PHASE274SPIRITS", ascension=0)
    result = engine.choose_neow_option(0)
    reward_strings = get_official_neow_reward_strings()

    assert result["success"] is True
    assert result["event_continues"] is True
    assert engine.state.neow_screen == "reward_select"
    assert len(engine.get_neow_options()) == 4
    assert engine.get_neow_options()[-1]["label_en"] == reward_strings.unique_rewards_en[0]


def test_phase274_neow_and_note_updates_persist_into_player_profile(tmp_path, monkeypatch) -> None:
    profile_path = tmp_path / "player_profile.json"
    monkeypatch.setattr(run_engine_module, "PLAYER_PROFILE_PATH", profile_path)
    monkeypatch.setattr(run_engine_module, "NOTE_FOR_YOURSELF_PREFS_PATH", tmp_path / "legacy_note.json")

    engine = RunEngine.create("PHASE274PERSIST", ascension=0)
    engine.choose_neow_option(0)
    engine._save_note_for_yourself_payload(card_id="Anger", upgrades=1)

    saved = json.loads(profile_path.read_text(encoding="utf-8"))

    assert saved["neow_intro_seen"] is True
    assert saved["note_for_yourself"] == {"card_id": "Anger", "upgrades": 1}


def test_phase274_standard_run_terminal_profile_updates_spirits_and_ascension(tmp_path, monkeypatch) -> None:
    profile_path = tmp_path / "player_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "characters": {
                    "IRONCLAD": {
                        "spirits": 0,
                        "highest_unlocked_ascension": 3,
                        "last_ascension_level": 3,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_engine_module, "PLAYER_PROFILE_PATH", profile_path)
    monkeypatch.setattr(run_engine_module, "NOTE_FOR_YOURSELF_PREFS_PATH", tmp_path / "legacy_note.json")

    victory_engine = RunEngine.create("PHASE274VICTORYPROFILE", ascension=3)
    victory_engine.state.floor = 51
    victory_engine._record_standard_run_profile_outcome(victory=True)

    defeat_engine = RunEngine.create("PHASE274DEFEATPROFILE", ascension=3)
    defeat_engine.state.floor = 20
    defeat_engine._record_standard_run_profile_outcome(victory=False)

    saved = json.loads(profile_path.read_text(encoding="utf-8"))

    assert saved["characters"]["IRONCLAD"]["highest_unlocked_ascension"] == 4
    assert saved["characters"]["IRONCLAD"]["spirits"] == 1


def test_phase274_low_floor_standard_defeat_clears_spirits(tmp_path, monkeypatch) -> None:
    profile_path = tmp_path / "player_profile.json"
    monkeypatch.setattr(run_engine_module, "PLAYER_PROFILE_PATH", profile_path)
    monkeypatch.setattr(run_engine_module, "NOTE_FOR_YOURSELF_PREFS_PATH", tmp_path / "legacy_note.json")

    engine = RunEngine.create("PHASE274LOWDEATH", ascension=2)
    engine.state.floor = 10
    engine._record_standard_run_profile_outcome(victory=False)

    saved = json.loads(profile_path.read_text(encoding="utf-8"))

    assert saved["characters"]["IRONCLAD"]["spirits"] == 0
