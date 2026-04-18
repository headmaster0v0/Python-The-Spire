from __future__ import annotations

from pathlib import Path

from sts_py.engine.content.relics import ALL_RELICS
from sts_py.engine.run.events import ACT1_EVENTS
from sts_py.engine.run.run_engine import RoomType
from sts_py.terminal.catalog import (
    card_requires_target,
    get_card_info,
    translate_card_name,
    translate_event_name,
    translate_monster,
    translate_potion,
    translate_power,
    translate_relic,
    translate_room_type,
)
from sts_py.tools import wiki_audit


def test_card_translations_use_huiji_aligned_chinese_names() -> None:
    assert translate_card_name("Bash") == "痛击"
    assert translate_card_name("TwinStrike") == "双重打击"
    assert translate_card_name("Clothesline") == "金刚臂"
    assert translate_card_name("Shockwave") == "震荡波"
    assert translate_card_name("Eruption") == "暴怒"
    assert translate_card_name("Accuracy") == "精准"
    assert translate_card_name("FlameBarrier") == "火焰屏障"
    assert translate_card_name("WraithForm") == "幽魂形态"
    assert translate_card_name("Madness") == "疯狂"
    assert translate_card_name("MasterOfStrategy") == "战略大师"
    assert translate_card_name("Apotheosis") == "神化"
    assert translate_card_name("Bite") == "噬咬"
    assert translate_card_name("Apparition") == "幻影"
    assert translate_card_name("Safety") == "平安"
    assert translate_card_name("Smite") == "惩恶"
    assert translate_card_name("ThroughViolence") == "以暴易暴"


def test_entity_translations_cover_relic_potion_monster_power_and_event() -> None:
    assert translate_relic("BurningBlood") == "燃烧之血"
    assert translate_potion("SmokeBomb") == "烟雾弹"
    assert translate_potion("Elixir") == "万灵药水"
    assert translate_monster("JawWorm") == "大颚虫"
    assert translate_monster("AcidSlimeLarge") == "大型酸液史莱姆"
    assert translate_monster("GremlinLeader") == "地精首领"
    assert translate_power("AfterImage") == "余像"
    assert translate_power("Lockon") == "跟踪锁定"
    assert translate_event_name(ACT1_EVENTS["Big Fish"]) == "大鱼"
    assert translate_event_name(ACT1_EVENTS["The Cleric"]) == "牧师"
    assert translate_room_type(RoomType.BOSS) == "首领房间"


def test_card_info_falls_back_to_engine_derived_summary_without_mojibake() -> None:
    name, description = get_card_info("Bash")

    assert name == "痛击"
    assert "8 点伤害" in description
    assert "易伤" in description
    assert "\ufffd" not in name
    assert "\ufffd" not in description
    assert "?" not in description


def test_phase248_card_info_uses_clean_runtime_descriptions() -> None:
    apotheosis_name, apotheosis_desc = get_card_info("Apotheosis")
    madness_name, madness_desc = get_card_info("Madness")
    hand_name, hand_desc = get_card_info("HandOfGreed")

    assert apotheosis_name == "神化"
    assert "升级" in apotheosis_desc
    assert madness_name == "疯狂"
    assert "费用" in madness_desc
    assert hand_name == "贪婪之手"
    assert "金币" in hand_desc
    for text in (apotheosis_name, apotheosis_desc, madness_name, madness_desc, hand_name, hand_desc):
        assert "\ufffd" not in text


def test_priority_one_relic_descriptions_are_cleaned_up() -> None:
    assert ALL_RELICS["JuzuBracelet"].description == "你在 ? 房间中不会再遭遇常规战斗。"
    assert ALL_RELICS["SsserpentHead"].description == "每次进入?房间时获得50金币。"
    assert ALL_RELICS["TinyChest"].description == "每4个 ? 房间的最后一个必是宝箱房。"


def test_priority_one_translation_fix_queue_items_are_cleared() -> None:
    bundle = wiki_audit.run_audit_from_raw_snapshot(
        wiki_audit.build_cli_raw_snapshot(Path.cwd(), enable_network=False),
        repo_root=Path.cwd(),
    )

    priority_one_translation_items = [
        item
        for item in bundle["fix_queue"]["items"]
        if item["priority"] == 1 and item["category"] == "translation"
    ]

    assert priority_one_translation_items == []


def test_phase249_offline_audit_uses_explicit_translation_provenance() -> None:
    bundle = wiki_audit.run_audit_from_raw_snapshot(
        wiki_audit.build_cli_raw_snapshot(Path.cwd(), enable_network=False),
        repo_root=Path.cwd(),
    )

    by_status = bundle["translation_audit"]["summary"]["by_status"]
    runtime_name_issue = bundle["translation_audit"]["summary"]["runtime_name_issue"]

    assert "accepted_alias" not in by_status
    assert runtime_name_issue.get("missing_cn", 0) == 0
    assert runtime_name_issue.get("mojibake_or_corrupt", 0) == 0

    findings = {
        (item["entity_type"], item["entity_id"]): item
        for item in bundle["translation_audit"]["findings"]
    }

    assert findings[("card", "Bash")]["status"] == "exact_match"
    assert findings[("monster", "JawWorm")]["status"] == "exact_match"
    assert findings[("event", "Big Fish")]["status"] == "exact_match"
    assert findings[("power", "AfterImage")]["status"] == "approved_alias"
    assert findings[("power", "AfterImage")]["approved_alias_note"] == "CLI omits the Huiji power disambiguation suffix."
    assert findings[("power", "AfterImage")]["huiji_page_or_title"] == "余像（能力）"
    assert findings[("ui_term", "help")]["status"] == "wiki_missing"


def test_unknown_translations_fall_back_to_humanized_identifier() -> None:
    assert translate_monster("MadeUpMonsterId") == "Made Up Monster Id"


def test_card_targeting_matches_engine_semantics() -> None:
    assert card_requires_target("Bash") is True
    assert card_requires_target("Cleave") is False
