from __future__ import annotations

import re
from pathlib import Path

import sts_py.engine.run.run_engine as run_engine_module
from sts_py.engine.run.events import (
    ACT1_EVENT_KEYS,
    ACT2_EVENT_KEYS,
    ACT3_EVENT_KEYS,
    EVENTS_BY_KEY,
    SPECIAL_ONE_TIME_EVENT_KEYS,
    SHRINE_EVENT_KEYS,
    TERMINAL_EVENT_KEYS,
    build_event,
)
from sts_py.engine.run.run_engine import RunEngine, RunPhase
from sts_py.terminal.render import render_event_choice_lines
from sts_py.tools.wiki_audit import build_cli_raw_snapshot, build_event_source_facts, build_neow_source_facts


ALL_EVENT_KEYS = ACT1_EVENT_KEYS + ACT2_EVENT_KEYS + ACT3_EVENT_KEYS + SHRINE_EVENT_KEYS + SPECIAL_ONE_TIME_EVENT_KEYS + TERMINAL_EVENT_KEYS
PREVIEW_KEYS = [
    "Back to Basics",
    "Drug Dealer",
    "Ghosts",
    "Masked Bandits",
    "Colosseum",
    "MindBloom",
    "Mysterious Sphere",
    "Match and Keep!",
    "Duplicator",
    "Fountain of Cleansing",
    "Lab",
    "Purifier",
    "Transmorgrifier",
    "Upgrade Shrine",
    "The Woman in Blue",
    "Wheel of Change",
    "SecretPortal",
    "SpireHeart",
]


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _event_act(event_key: str) -> int:
    if event_key in ACT1_EVENT_KEYS:
        return 1
    if event_key in ACT2_EVENT_KEYS or event_key in SHRINE_EVENT_KEYS or event_key in SPECIAL_ONE_TIME_EVENT_KEYS:
        return 2
    return 3


def _prime_event_engine(event_key: str) -> RunEngine:
    engine = RunEngine.create(f"PHASE277{re.sub(r'[^A-Z0-9]', '', event_key.upper())}", ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine.state.act = _event_act(event_key)
    engine.state.floor = 39 if event_key in {"MindBloom", "SecretPortal", "SpireHeart"} else 20
    engine.state.playtime_seconds = 900.0
    engine.state.player_max_hp = 80
    engine.state.player_hp = 80
    engine.state.player_gold = 999
    engine.state.deck = ["Strike", "Defend", "Bash", "Inflame", "Anger", "Regret"]
    engine.state.potions = ["FirePotion", "EmptyPotionSlot", "EmptyPotionSlot"]
    engine.state.relics = ["BurningBlood", "Anchor", "Lantern", "GoldenIdol"]
    engine.state.note_for_yourself_payload = {"card_id": "Anger", "upgrades": 0}
    if event_key == "Fountain of Cleansing":
        engine.state.deck = ["Strike", "Bash", "Regret"]
    if event_key == "N'loth":
        engine.state.relics = ["BurningBlood", "Anchor", "Lantern"]
    if event_key == "The Woman in Blue":
        engine.state.player_gold = 100
    if event_key == "WeMeetAgain":
        engine.state.deck = ["Strike", "Bash", "Anger"]
        engine.state.player_gold = 120
    if event_key == "Designer":
        engine.state.player_gold = 120
        engine.state.act = 2
    engine._set_current_event(build_event(event_key))
    return engine


def test_phase277_neow_public_entrypoints_are_single_definition() -> None:
    source = Path(run_engine_module.__file__).read_text(encoding="utf-8")

    assert len(re.findall(r"^\s*def _init_neow\(", source, re.M)) == 1
    assert len(re.findall(r"^\s*def _build_neow_option\(", source, re.M)) == 1
    assert len(re.findall(r"^\s*def get_neow_options\(", source, re.M)) == 1
    assert len(re.findall(r"^\s*def choose_neow_option\(", source, re.M)) == 1
    assert len(re.findall(r"^\s*def choose_card_for_neow\(", source, re.M)) == 1


def test_phase277_all_events_carry_truth_metadata_and_official_text() -> None:
    for event_key in ALL_EVENT_KEYS:
        event = EVENTS_BY_KEY[event_key]
        facts = build_event_source_facts(event)

        assert facts["event_key"] == event_key
        assert facts["java_class"]
        assert facts["flow_kind"]
        assert facts["stage_count"] >= 1
        assert facts["source_description_count"] >= 1
        assert facts["source_description_count_cn"] >= 1
        assert facts["source_option_count"] >= 1
        assert facts["source_option_count_cn"] >= 1
        assert facts["official_name_en_available"] is True
        assert facts["official_name_cn_available"] is True
        assert facts["official_description_en_available"] is True
        assert facts["official_description_cn_available"] is True
        assert facts["official_option_en_available"] is True
        assert facts["official_option_cn_available"] is True


def test_phase277_build_event_preview_surfaces_use_official_cn_for_known_placeholder_cluster() -> None:
    for event_key in PREVIEW_KEYS:
        lines = render_event_choice_lines(build_event(event_key))

        assert lines
        assert _contains_cjk(lines[0])
        assert not any("Nothing happens" in line for line in lines)
        assert not any("mysterious aid" in line.lower() for line in lines)
        assert any(_contains_cjk(line) for line in lines[1:])


def test_phase277_all_events_prepare_runtime_surface_with_localized_choices() -> None:
    for event_key in ALL_EVENT_KEYS:
        engine = _prime_event_engine(event_key)
        event = engine.get_current_event()

        assert event is not None
        lines = render_event_choice_lines(event)
        assert lines
        assert len(lines) >= 2
        assert _contains_cjk(lines[0])
        assert not any("Nothing happens" in line for line in lines)
        assert not any("mysterious aid" in line.lower() for line in lines)


def test_phase277_all_enabled_initial_event_choices_dispatch_without_invalid_reasons() -> None:
    for event_key in ALL_EVENT_KEYS:
        engine = _prime_event_engine(event_key)
        event = engine.get_current_event()
        assert event is not None

        for idx, choice in enumerate(event.choices):
            if not getattr(choice, "enabled", True):
                continue
            branch_engine = _prime_event_engine(event_key)
            result = branch_engine.choose_event_option(idx)
            assert result.get("reason") not in {"invalid_choice", "choice_disabled", "no_event"}


def test_phase277_event_and_neow_audit_facts_expose_aliases_and_official_availability() -> None:
    designer = build_event_source_facts(build_event("Designer"))
    spire_heart = build_event_source_facts(build_event("SpireHeart"))
    neow = build_neow_source_facts()

    assert "Designer In-Spire" in designer["wiki_aliases_en"]
    assert "尖端设计师" in designer["wiki_aliases_cn"]
    assert "Corrupt Heart" in spire_heart["wiki_aliases_en"]
    assert designer["official_option_cn_available"] is True
    assert neow["event_text_count_cn"] >= 1
    assert neow["reward_text_count_cn"] >= 1
    assert neow["unique_reward_count_cn"] >= 1


def test_phase277_raw_snapshot_keeps_event_and_neow_truth_flags() -> None:
    snapshot = build_cli_raw_snapshot(Path.cwd(), enable_network=False)
    designer = next(item for item in snapshot["records"] if item["entity_type"] == "event" and item["entity_id"] == "Designer")
    neow = next(item for item in snapshot["records"] if item["entity_type"] == "neow" and item["entity_id"] == "NeowEvent")

    assert designer["runtime_facts"]["official_option_cn_available"] is True
    assert "Designer In-Spire" in designer["runtime_facts"]["wiki_aliases_en"]
    assert designer["java_facts"]["official_description_cn_available"] is True
    assert neow["runtime_facts"]["event_text_count_cn"] >= 1
    assert neow["java_facts"]["unique_reward_count_cn"] >= 1
