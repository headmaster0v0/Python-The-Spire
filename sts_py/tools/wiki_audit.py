from __future__ import annotations

import argparse
import inspect
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import sts_py.engine.combat.powers as power_module
import sts_py.terminal.catalog as terminal_catalog
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import ALL_CARD_DEFS, CARD_ID_ALIASES
from sts_py.engine.content.official_card_strings import get_official_card_strings
from sts_py.engine.content.potions import POTION_DEFINITIONS
from sts_py.engine.content.relics import ALL_RELICS, RelicDef
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.monster_truth import load_monster_truth_matrix
from sts_py.engine.run.events import (
    EVENT_FLOW_FACTS_BY_KEY as RUNTIME_EVENT_FLOW_FACTS_BY_KEY,
    EVENT_ID_BY_KEY,
    EVENT_RNG_STREAMS_BY_KEY as RUNTIME_EVENT_RNG_STREAMS_BY_KEY,
    EVENTS_BY_KEY,
    EVENT_WIKI_NAME_ALIASES as RUNTIME_EVENT_WIKI_NAME_ALIASES,
    Event,
    EventChoice,
    _resolve_event_key,
)
from sts_py.engine.run.official_event_strings import get_official_event_strings
from sts_py.engine.run.official_neow_strings import (
    get_official_neow_event_strings,
    get_official_neow_reward_strings,
)
from sts_py.engine.run.run_engine import RoomType, _monster_factory_registry
from sts_py.terminal.catalog import (
    card_requires_target,
    get_card_info,
    get_power_str,
    translate_event_name,
    translate_monster,
    translate_potion,
    translate_power,
    translate_relic,
    translate_room_type,
)
from sts_py.terminal.translation_policy import (
    ALIGNMENT_STATUSES,
    TranslationPolicyEntry,
    get_translation_policy_entry,
    load_translation_policy_bundle,
    load_translation_policy_entries,
    translation_policy_entity_ids_by_type,
)
from sts_py.tools.fidelity_proof import (
    build_event_choice_effect_signatures,
    build_monster_state_signatures,
    build_potion_effect_signatures,
    build_power_callback_signatures,
    build_relic_effect_signatures,
)
from sts_py.tools.wiki_bilingual_scraper import BilingualWikiScraper

SNAPSHOT_SCHEMA_VERSION = 1
REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_SNAPSHOT_FILENAME = "raw_snapshot.json"
NORMALIZED_SNAPSHOT_FILENAME = "normalized_snapshot.json"
TRANSLATION_AUDIT_FILENAME = "translation_audit.json"
COMPLETENESS_AUDIT_FILENAME = "completeness_audit.json"
MECHANICS_AUDIT_FILENAME = "mechanics_audit.json"
FIX_QUEUE_FILENAME = "fix_queue.json"

ENTITY_TYPES = (
    "card",
    "relic",
    "potion",
    "power",
    "monster",
    "event",
    "neow",
    "room_type",
    "ui_term",
)

EN_SOURCE_ORDER = [
    BilingualWikiScraper.SOURCE_EN_WIKIGG,
    BilingualWikiScraper.SOURCE_EN_FANDOM,
]
CN_SOURCE_ORDER = [BilingualWikiScraper.SOURCE_CN_HUIJI]

MOJIBAKE_MARKERS = (
    "锟",
    "鈥",
    "鐥",
    "鎵",
    "闃",
    "鏀",
    "鑽",
    "鍙",
    "闇",
    "銆",
    "锛",
)

UI_TERM_CN_NAMES = {
    "help": "帮助",
    "map": "地图",
    "mapimg": "地图图片",
    "deck": "牌组",
    "relics": "遗物",
    "potions": "药水",
    "status": "状态",
    "intent": "意图",
    "exhaust": "消耗堆",
    "draw": "抽牌堆",
    "discard": "弃牌堆",
    "inspect": "查看",
    "end": "结束回合",
    "use": "使用",
}

MANUAL_JAVA_CARD_NAME_BY_RUNTIME_ID = {
    "Strike": "Strike_Red",
    "Defend": "Defend_Red",
    "Strike_B": "Strike_Blue",
    "Defend_B": "Defend_Blue",
    "Strike_P": "Strike_Purple",
    "Defend_P": "Defend_Watcher",
    "BloodforBlood": "BloodForBlood",
    "Thunderclap": "ThunderClap",
    "Lockon": "LockOn",
    "Darkness": "Darkness",
    "Tempest": "Tempest",
    "ThousandCuts": "AThousandCuts",
    "CripplingCloud": "CripplingPoison",
    "Nightmare": "Nightmare",
    "Foresight": "Foresight",
    "Void": "VoidCard",
    "Bullseye": "LockOn",
}

ACT1_MONSTER_IDS = {
    "AcidSlimeLarge",
    "AcidSlimeMedium",
    "AcidSlimeSmall",
    "Cultist",
    "FungiBeast",
    "FuzzyLouseNormal",
    "GremlinFat",
    "GremlinNob",
    "GremlinSneaky",
    "GremlinTsundere",
    "GremlinWar",
    "GremlinWizard",
    "Hexaghost",
    "JawWorm",
    "Lagavulin",
    "Looter",
    "LouseDefensive",
    "LouseRed",
    "Mugger",
    "Sentry",
    "SlaverBlue",
    "SlaverRed",
    "SlimeBoss",
    "SpikeSlimeLarge",
    "SpikeSlimeMedium",
    "SpikeSlimeSmall",
    "TheGuardian",
}

ACT2_MONSTER_IDS = {
    "BanditBear",
    "BanditLeader",
    "BanditPointy",
    "BookOfStabbing",
    "BronzeAutomaton",
    "BronzeOrb",
    "Byrd",
    "Centurion",
    "Champ",
    "Chosen",
    "Collector",
    "Dagger",
    "GremlinLeader",
    "Healer",
    "ShellParasite",
    "SnakePlant",
    "Snecko",
    "SphericGuardian",
    "Taskmaster",
    "TorchHead",
}

ACT3_MONSTER_IDS = {
    "AwakenedOne",
    "Darkling",
    "Deca",
    "Donu",
    "DonuAndDeca",
    "Exploder",
    "GiantHead",
    "Maw",
    "Nemesis",
    "OrbWalker",
    "Repulsor",
    "Reptomancer",
    "SnakeDagger",
    "SpireGrowth",
    "Spiker",
    "TimeEater",
    "Transient",
    "WrithingMass",
}

ACT4_MONSTER_IDS = {
    "CorruptHeart",
    "SpireShield",
    "SpireSpear",
}

CLI_UI_TERMS = {
    "help": {"contexts": ["map", "combat", "reward", "shop", "event", "rest", "treasure", "victory"]},
    "map": {"contexts": ["map", "combat"]},
    "mapimg": {"contexts": ["map", "combat"]},
    "deck": {"contexts": ["map", "combat", "reward", "shop", "event", "rest", "victory"]},
    "relics": {"contexts": ["map", "combat", "reward", "shop", "event", "treasure", "victory"]},
    "potions": {"contexts": ["map", "combat", "reward", "shop", "event", "rest"]},
    "status": {"contexts": ["combat"]},
    "intent": {"contexts": ["combat"]},
    "exhaust": {"contexts": ["combat"]},
    "draw": {"contexts": ["combat"]},
    "discard": {"contexts": ["combat"]},
    "inspect": {"contexts": ["map", "combat"]},
    "end": {"contexts": ["combat"]},
    "use": {"contexts": ["combat"]},
}


def _canonical_card_catalog_override_keys() -> set[str]:
    keys = set(getattr(terminal_catalog, "CARD_NAME_OVERRIDES", {}).keys())
    keys.update(getattr(terminal_catalog, "CARD_DESCRIPTION_OVERRIDES", {}).keys())
    return {CARD_ID_ALIASES.get(str(key), str(key)) for key in keys}


EVENT_WIKI_NAME_ALIASES = {
    "NoteForYourself": {"en": ["A Note For Yourself"]},
    "Fountain of Cleansing": {"en": ["The Divine Fountain"]},
    "Bonfire Elementals": {"en": ["Bonfire Spirits"]},
    "Accursed Blacksmith": {"en": ["Ominous Forge"]},
    "Addict": {"en": ["Pleading Vagrant"]},
    "Ghosts": {"en": ["Council of Ghosts"]},
    "Nest": {"en": ["The Nest"]},
    "Beggar": {"en": ["Old Beggar"]},
    "Back to Basics": {"en": ["Ancient Writing"]},
    "Designer": {"en": ["Designer In-Spire"], "cn": ["尖端设计师"]},
    "Match and Keep!": {"en": ["Match and Keep"], "cn": ["对对碰！"]},
    "Mushrooms": {"en": ["Hypnotizing Colored Mushrooms"]},
    "SpireHeart": {"en": ["Corrupt Heart"], "cn": ["高塔之心"]},
}

EVENT_FLOW_FACTS_BY_KEY: dict[str, dict[str, Any]] = {
    "Big Fish": {"flow_kind": "result_screen", "stage_count": 2, "reward_surface": "relic_or_immediate", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "The Cleric": {"flow_kind": "card_select_result", "stage_count": 2, "reward_surface": "none", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Beggar": {"flow_kind": "card_select_result", "stage_count": 3, "reward_surface": "none", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Liars Game": {"flow_kind": "multi_screen", "stage_count": 3, "reward_surface": "gold_and_curse", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Cursed Tome": {"flow_kind": "multi_screen", "stage_count": 6, "reward_surface": "relic", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Forgotten Altar": {"flow_kind": "result_screen", "stage_count": 2, "reward_surface": "relic_or_curse", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Ghosts": {"flow_kind": "result_screen", "stage_count": 2, "reward_surface": "cards", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Masked Bandits": {"flow_kind": "event_combat_or_multi_screen", "stage_count": 5, "reward_surface": "gold_and_relic", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Nest": {"flow_kind": "multi_screen", "stage_count": 3, "reward_surface": "gold_or_card", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "The Library": {"flow_kind": "card_select_result", "stage_count": 2, "reward_surface": "card_or_heal", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "The Mausoleum": {"flow_kind": "result_screen", "stage_count": 2, "reward_surface": "relic", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Vampires": {"flow_kind": "result_screen", "stage_count": 2, "reward_surface": "cards", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Colosseum": {"flow_kind": "event_combat_reentry", "stage_count": 4, "reward_surface": "relics_and_gold", "event_combat_reentry": True, "dynamic_option_slots": 0},
    "SensoryStone": {"flow_kind": "multi_screen", "stage_count": 3, "reward_surface": "colorless_cards", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Tomb of Lord Red Mask": {"flow_kind": "result_screen", "stage_count": 2, "reward_surface": "gold_or_relic", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Winding Halls": {"flow_kind": "multi_screen", "stage_count": 3, "reward_surface": "cards_or_heal_or_max_hp", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Accursed Blacksmith": {"flow_kind": "card_select_result", "stage_count": 2, "reward_surface": "relic_and_curse", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "FaceTrader": {"flow_kind": "multi_screen", "stage_count": 3, "reward_surface": "gold_or_relic", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Fountain of Cleansing": {"flow_kind": "result_screen", "stage_count": 2, "reward_surface": "none", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Knowing Skull": {"flow_kind": "looping_menu", "stage_count": 3, "reward_surface": "gold_potion_card", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Match and Keep!": {"flow_kind": "memory_game", "stage_count": 4, "reward_surface": "cards", "event_combat_reentry": False, "dynamic_option_slots": 12},
    "NoteForYourself": {"flow_kind": "card_select_result", "stage_count": 3, "reward_surface": "stored_card", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "The Moai Head": {"flow_kind": "result_screen", "stage_count": 2, "reward_surface": "gold_or_heal", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Wheel of Change": {"flow_kind": "spin_result", "stage_count": 3, "reward_surface": "mixed", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "SpireHeart": {"flow_kind": "terminal_transition", "stage_count": 4, "reward_surface": "act_transition_or_death", "event_combat_reentry": False, "dynamic_option_slots": 0},
}

EVENT_FLOW_FACTS_BY_KEY = {
    **EVENT_FLOW_FACTS_BY_KEY,
    "Addict": {"flow_kind": "result_screen", "stage_count": 2, "reward_surface": "relic_or_none", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Back to Basics": {"flow_kind": "result_screen", "stage_count": 2, "reward_surface": "remove_or_upgrade", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Bonfire Elementals": {"flow_kind": "card_select_result", "stage_count": 3, "reward_surface": "sacrifice_boon", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Dead Adventurer": {"flow_kind": "looping_search_or_event_combat", "stage_count": 4, "reward_surface": "gold_or_relic_or_event_combat", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Designer": {"flow_kind": "multi_screen", "stage_count": 4, "reward_surface": "deck_services", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Drug Dealer": {"flow_kind": "card_select_result", "stage_count": 2, "reward_surface": "card_transform_or_relic", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Duplicator": {"flow_kind": "card_select_result", "stage_count": 2, "reward_surface": "duplicate_card", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Falling": {"flow_kind": "multi_screen", "stage_count": 2, "reward_surface": "remove_card", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Golden Idol": {"flow_kind": "multi_screen", "stage_count": 3, "reward_surface": "relic_and_trap", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Golden Shrine": {"flow_kind": "result_screen", "stage_count": 2, "reward_surface": "gold_or_gold_and_curse", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Golden Wing": {"flow_kind": "card_select_result", "stage_count": 2, "reward_surface": "gold_or_card_remove", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Lab": {"flow_kind": "result_screen", "stage_count": 2, "reward_surface": "potions", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Living Wall": {"flow_kind": "card_select_result", "stage_count": 2, "reward_surface": "remove_or_transform_or_upgrade", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "MindBloom": {"flow_kind": "event_combat_or_result", "stage_count": 2, "reward_surface": "combat_or_gold_or_heal_or_upgrade", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Mushrooms": {"flow_kind": "event_combat_or_result", "stage_count": 2, "reward_surface": "event_combat_or_heal", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Mysterious Sphere": {"flow_kind": "event_combat_or_multi_screen", "stage_count": 3, "reward_surface": "rare_relic", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "N'loth": {"flow_kind": "result_screen", "stage_count": 2, "reward_surface": "relic_swap", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Purifier": {"flow_kind": "card_select_result", "stage_count": 2, "reward_surface": "remove_card", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Scrap Ooze": {"flow_kind": "looping_search", "stage_count": 4, "reward_surface": "relic", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "SecretPortal": {"flow_kind": "multi_screen", "stage_count": 3, "reward_surface": "boss_jump", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Shining Light": {"flow_kind": "result_screen", "stage_count": 2, "reward_surface": "upgrades", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "The Joust": {"flow_kind": "multi_screen", "stage_count": 3, "reward_surface": "gold", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "The Woman in Blue": {"flow_kind": "result_screen", "stage_count": 2, "reward_surface": "potions", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Transmorgrifier": {"flow_kind": "card_select_result", "stage_count": 2, "reward_surface": "transform_card", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "Upgrade Shrine": {"flow_kind": "card_select_result", "stage_count": 2, "reward_surface": "upgrade_card", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "WeMeetAgain": {"flow_kind": "result_screen", "stage_count": 2, "reward_surface": "relic_trade", "event_combat_reentry": False, "dynamic_option_slots": 0},
    "World of Goop": {"flow_kind": "result_screen", "stage_count": 2, "reward_surface": "gold_or_gold_loss", "event_combat_reentry": False, "dynamic_option_slots": 0},
}

EVENT_RNG_STREAMS_BY_KEY: dict[str, list[str]] = {event_key: [] for event_key in EVENTS_BY_KEY}
for event_key in {"Big Fish", "Addict", "Dead Adventurer", "Cursed Tome", "The Mausoleum", "MindBloom"}:
    EVENT_RNG_STREAMS_BY_KEY[event_key].append("relic_rng")
for event_key in {"World of Goop", "Golden Wing", "Living Wall", "Scrap Ooze", "Shining Light", "Designer", "FaceTrader", "Drug Dealer", "The Joust", "Mysterious Sphere", "SensoryStone", "The Mausoleum", "WeMeetAgain", "N'loth", "Transmorgrifier", "Dead Adventurer", "MindBloom", "Falling", "Cursed Tome", "Wheel of Change"}:
    EVENT_RNG_STREAMS_BY_KEY[event_key].append("misc_rng")
for event_key in {"Scrap Ooze", "Masked Bandits"}:
    EVENT_RNG_STREAMS_BY_KEY[event_key].append("treasure_rng")
for event_key in {"The Woman in Blue", "Lab"}:
    EVENT_RNG_STREAMS_BY_KEY[event_key].append("potion_rng")
for event_key in {"Transmorgrifier", "Living Wall"}:
    EVENT_RNG_STREAMS_BY_KEY[event_key].append("card_random_rng")

# Event truth now lives in sts_py.engine.run.events. Keep local names wired to
# that source so audit/reporting stays aligned with runtime metadata.
EVENT_WIKI_NAME_ALIASES = RUNTIME_EVENT_WIKI_NAME_ALIASES
EVENT_FLOW_FACTS_BY_KEY = RUNTIME_EVENT_FLOW_FACTS_BY_KEY
EVENT_RNG_STREAMS_BY_KEY = RUNTIME_EVENT_RNG_STREAMS_BY_KEY

CATALOG_OVERRIDE_SOURCES = {
    "card": lambda: _canonical_card_catalog_override_keys() | set(translation_policy_entity_ids_by_type().get("card", [])),
    "relic": lambda: set(getattr(terminal_catalog, "RELIC_NAME_OVERRIDES", {}).keys()) | set(translation_policy_entity_ids_by_type().get("relic", [])),
    "potion": lambda: set(getattr(terminal_catalog, "POTION_NAME_OVERRIDES", {}).keys()) | set(translation_policy_entity_ids_by_type().get("potion", [])),
    "monster": lambda: set(getattr(terminal_catalog, "MONSTER_NAME_OVERRIDES", {}).keys()) | set(translation_policy_entity_ids_by_type().get("monster", [])),
    "power": lambda: set(getattr(terminal_catalog, "POWER_NAME_OVERRIDES", {}).keys()) | set(translation_policy_entity_ids_by_type().get("power", [])),
    "event": lambda: set(getattr(terminal_catalog, "EVENT_NAME_OVERRIDES", {}).keys()) | set(translation_policy_entity_ids_by_type().get("event", [])),
    "neow": lambda: set(),
    "room_type": lambda: set(translation_policy_entity_ids_by_type().get("room_type", [])),
    "ui_term": lambda: set(translation_policy_entity_ids_by_type().get("ui_term", [])),
}

MECHANICS_FIELDS_BY_ENTITY = {
    "card": ["cost", "type", "rarity", "target_required", "damage", "block", "magic_number", "exhaust", "ethereal", "retain", "innate"],
    "relic": ["tier", "price", "character_class", "effects", "effect_signatures"],
    "potion": ["rarity", "character_class", "potency", "sacred_bark_potency", "is_thrown", "effect_signatures"],
    "power": ["power_type", "turn_based", "can_go_negative", "callback_signatures"],
    "monster": ["act", "elite", "boss", "category", "encounters", "pool_buckets", "internal_surface", "combat_capable", "sample_intents", "state_signatures"],
    "event": [
        "act",
        "pool_bucket",
        "gating_flags",
        "java_class",
        "choice_count",
        "initial_option_count",
        "source_description_count",
        "source_description_count_cn",
        "source_option_count",
        "source_option_count_cn",
        "flow_kind",
        "stage_count",
        "reward_surface",
        "event_combat_reentry",
        "dynamic_option_slots",
        "wiki_aliases_en",
        "wiki_aliases_cn",
        "official_name_en_available",
        "official_name_cn_available",
        "official_description_en_available",
        "official_description_cn_available",
        "official_option_en_available",
        "official_option_cn_available",
        "choices",
        "choice_effect_signatures",
        "rng_streams",
    ],
    "neow": [
        "screen_count",
        "reward_option_groups",
        "rng_streams",
        "event_text_count",
        "event_text_count_cn",
        "event_option_count",
        "event_option_count_cn",
        "reward_text_count",
        "reward_text_count_cn",
        "reward_option_count",
        "reward_option_count_cn",
        "unique_reward_count",
        "unique_reward_count_cn",
        "wiki_aliases_en",
        "wiki_aliases_cn",
    ],
    "room_type": ["enum_name", "symbol"],
    "ui_term": ["contexts"],
}


@dataclass
class WikiPageSnapshot:
    source: str | None = None
    requested_title: str = ""
    resolved_title: str | None = None
    url: str | None = None
    summary: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "WikiPageSnapshot":
        if not data:
            return cls()
        return cls(
            source=data.get("source"),
            requested_title=str(data.get("requested_title", "")),
            resolved_title=data.get("resolved_title"),
            url=data.get("url"),
            summary=str(data.get("summary", "") or ""),
            payload=dict(data.get("payload") or {}),
            attempts=list(data.get("attempts") or []),
            error=data.get("error"),
        )


@dataclass
class RawEntitySnapshot:
    entity_type: str
    entity_id: str
    runtime_name_en: str
    runtime_name_cn: str
    runtime_desc_runtime: str
    runtime_facts: dict[str, Any] = field(default_factory=dict)
    java_facts: dict[str, Any] = field(default_factory=dict)
    en_wiki: WikiPageSnapshot = field(default_factory=WikiPageSnapshot)
    cn_wiki: WikiPageSnapshot = field(default_factory=WikiPageSnapshot)
    audit_status: dict[str, str] = field(default_factory=dict)
    audit_notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RawEntitySnapshot":
        return cls(
            entity_type=str(data["entity_type"]),
            entity_id=str(data["entity_id"]),
            runtime_name_en=str(data.get("runtime_name_en", "")),
            runtime_name_cn=str(data.get("runtime_name_cn", "")),
            runtime_desc_runtime=str(data.get("runtime_desc_runtime", "")),
            runtime_facts=dict(data.get("runtime_facts") or {}),
            java_facts=dict(data.get("java_facts") or {}),
            en_wiki=WikiPageSnapshot.from_dict(data.get("en_wiki")),
            cn_wiki=WikiPageSnapshot.from_dict(data.get("cn_wiki")),
            audit_status=dict(data.get("audit_status") or {}),
            audit_notes=list(data.get("audit_notes") or []),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NormalizedEntitySnapshot:
    entity_type: str
    entity_id: str
    runtime_name_en: str
    runtime_name_cn: str
    runtime_desc_runtime: str
    java_facts: dict[str, Any]
    en_wiki_page: str | None
    en_wiki_name: str | None
    en_wiki_summary: str
    cn_wiki_page: str | None
    cn_wiki_name: str | None
    cn_wiki_summary: str
    audit_status: dict[str, str] = field(default_factory=dict)
    audit_notes: list[str] = field(default_factory=list)
    runtime_facts: dict[str, Any] = field(default_factory=dict)
    match_meta: dict[str, Any] = field(default_factory=dict)
    reference_source: str = ""
    alignment_status: str = ""
    huiji_page_or_title: str = ""
    approved_alias_note: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NormalizedEntitySnapshot":
        return cls(
            entity_type=str(data["entity_type"]),
            entity_id=str(data["entity_id"]),
            runtime_name_en=str(data.get("runtime_name_en", "")),
            runtime_name_cn=str(data.get("runtime_name_cn", "")),
            runtime_desc_runtime=str(data.get("runtime_desc_runtime", "")),
            java_facts=dict(data.get("java_facts") or {}),
            en_wiki_page=data.get("en_wiki_page"),
            en_wiki_name=data.get("en_wiki_name"),
            en_wiki_summary=str(data.get("en_wiki_summary", "")),
            cn_wiki_page=data.get("cn_wiki_page"),
            cn_wiki_name=data.get("cn_wiki_name"),
            cn_wiki_summary=str(data.get("cn_wiki_summary", "")),
            audit_status=dict(data.get("audit_status") or {}),
            audit_notes=list(data.get("audit_notes") or []),
            runtime_facts=dict(data.get("runtime_facts") or {}),
            match_meta=dict(data.get("match_meta") or {}),
            reference_source=str(data.get("reference_source", "") or ""),
            alignment_status=str(data.get("alignment_status", "") or ""),
            huiji_page_or_title=str(data.get("huiji_page_or_title", "") or ""),
            approved_alias_note=str(data.get("approved_alias_note", "") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _contains_private_use(text: str) -> bool:
    return any("\ue000" <= ch <= "\uf8ff" for ch in text)


def _looks_mojibake(text: str) -> bool:
    candidate = str(text or "").strip()
    if not candidate:
        return False
    if "\ufffd" in candidate or _contains_private_use(candidate):
        return True
    if "?" in candidate and _contains_cjk(candidate):
        if re.search(r"\?\s*(房间|rooms?)", candidate, re.I):
            return False
        return True
    return sum(marker in candidate for marker in MOJIBAKE_MARKERS) >= 2


def _looks_cataloged_cn(text: str) -> bool:
    candidate = str(text or "").strip()
    if not candidate:
        return False
    if _looks_mojibake(candidate):
        return False
    return _contains_cjk(candidate)


def _humanize_identifier(identifier: str) -> str:
    if not identifier:
        return ""
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", identifier.replace("_", " "))
    return re.sub(r"\s+", " ", spaced).strip()


def _normalize_lookup_key(value: str) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        return ""
    candidate = re.sub(r"\+\d*$", "", candidate)
    candidate = candidate.rstrip("+")
    candidate = re.sub(r"[ _-]+", "", candidate)
    candidate = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", candidate)
    return candidate.lower()


def _match_kind(entity_id: str, runtime_name: str, wiki_name: str | None, wiki_page: str | None) -> str:
    wiki_tokens = {_normalize_lookup_key(wiki_name or ""), _normalize_lookup_key(wiki_page or "")}
    wiki_tokens.discard("")
    if not wiki_tokens:
        return "missing"

    entity_token = _normalize_lookup_key(entity_id)
    runtime_token = _normalize_lookup_key(runtime_name)
    if entity_token in wiki_tokens or runtime_token in wiki_tokens:
        return "exact"

    for token in wiki_tokens:
        if entity_token and (
            token.startswith(entity_token)
            or entity_token.startswith(token)
            or entity_token in token
            or token in entity_token
        ):
            return "alias"
        if runtime_token and (
            token.startswith(runtime_token)
            or runtime_token.startswith(token)
            or runtime_token in token
            or token in runtime_token
        ):
            return "alias"
    return "unresolved"


def _unique_nonempty(values: Iterable[str | None]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _coerce_raw_records(data: Any) -> list[RawEntitySnapshot]:
    if isinstance(data, dict):
        items = data.get("records") or []
    else:
        items = data or []
    records: list[RawEntitySnapshot] = []
    for item in items:
        if isinstance(item, RawEntitySnapshot):
            records.append(item)
        elif isinstance(item, dict):
            records.append(RawEntitySnapshot.from_dict(item))
    return records


def _coerce_normalized_records(data: Any) -> list[NormalizedEntitySnapshot]:
    if isinstance(data, dict):
        items = data.get("records") or []
        if items and isinstance(items[0], dict) and "match_meta" not in items[0] and "en_wiki" in items[0]:
            items = normalize_raw_snapshot(data)["records"]
    else:
        items = data or []
    records: list[NormalizedEntitySnapshot] = []
    for item in items:
        if isinstance(item, NormalizedEntitySnapshot):
            records.append(item)
        elif isinstance(item, dict):
            records.append(NormalizedEntitySnapshot.from_dict(item))
    return records


def _catalog_override_keys() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for entity_type, loader in CATALOG_OVERRIDE_SOURCES.items():
        result[entity_type] = sorted(str(item) for item in loader())
    return result


def _normalize_entity_type_filter(entity_types: Iterable[str] | None) -> set[str] | None:
    if entity_types is None:
        return None
    normalized = {str(entity_type).strip() for entity_type in entity_types if str(entity_type).strip()}
    if not normalized:
        return None
    unknown = sorted(normalized - set(ENTITY_TYPES))
    if unknown:
        raise ValueError(f"unknown entity types: {unknown}")
    return normalized


def _filter_mapping_by_entity_types(mapping: dict[str, Any], entity_types: set[str] | None) -> dict[str, Any]:
    if entity_types is None:
        return dict(mapping)
    return {
        entity_type: value
        for entity_type, value in mapping.items()
        if entity_type in entity_types
    }


def filter_raw_snapshot_entity_types(raw_snapshot: dict[str, Any], entity_types: Iterable[str] | None) -> dict[str, Any]:
    normalized = _normalize_entity_type_filter(entity_types)
    if normalized is None:
        return dict(raw_snapshot)

    filtered = dict(raw_snapshot)
    filtered["entity_types"] = sorted(normalized)
    filtered["catalog_overrides"] = _filter_mapping_by_entity_types(dict(raw_snapshot.get("catalog_overrides") or {}), normalized)
    filtered["runtime_inventory"] = _filter_mapping_by_entity_types(dict(raw_snapshot.get("runtime_inventory") or {}), normalized)
    filtered["source_inventory"] = _filter_mapping_by_entity_types(dict(raw_snapshot.get("source_inventory") or {}), normalized)
    filtered["translation_policy"] = [
        record
        for record in list(raw_snapshot.get("translation_policy") or [])
        if str(record.get("entity_type", "") or "") in normalized
    ]
    filtered["records"] = [
        record
        for record in list(raw_snapshot.get("records") or [])
        if str(record.get("entity_type", "") or "") in normalized
    ]
    return filtered


def _policy_entries_from_snapshot(snapshot: dict[str, Any] | None) -> dict[tuple[str, str], TranslationPolicyEntry]:
    if not snapshot:
        return dict(load_translation_policy_entries())
    raw_entries = list(snapshot.get("translation_policy") or [])
    if not raw_entries:
        return dict(load_translation_policy_entries())
    entries: dict[tuple[str, str], TranslationPolicyEntry] = {}
    for raw_entry in raw_entries:
        entry = TranslationPolicyEntry.from_dict(dict(raw_entry))
        entries[(entry.entity_type, entry.entity_id)] = entry
    return entries


def _policy_entry_to_dict(entry: TranslationPolicyEntry | None) -> dict[str, str]:
    if entry is None:
        return {
            "reference_source": "",
            "alignment_status": "",
            "huiji_page_or_title": "",
            "approved_alias_note": "",
        }
    return entry.to_dict()


def _power_class_inventory() -> list[tuple[str, type[Any]]]:
    classes: list[tuple[str, type[Any]]] = []
    for _, power_cls in inspect.getmembers(power_module, inspect.isclass):
        if power_cls.__module__ != power_module.__name__:
            continue
        if not power_cls.__name__.endswith("Power") or power_cls.__name__ == "Power":
            continue
        fields = getattr(power_cls, "__dataclass_fields__", {})
        if "id" not in fields:
            continue
        power_id = fields["id"].default
        if not power_id:
            continue
        classes.append((str(power_id), power_cls))
    classes.sort(key=lambda item: item[0])
    return classes


def _event_inventory() -> dict[str, Event]:
    return {
        event_key: event.clone()
        for event_key, event in EVENTS_BY_KEY.items()
    }


def _monster_act(monster_id: str) -> int | None:
    if monster_id in ACT1_MONSTER_IDS:
        return 1
    if monster_id in ACT2_MONSTER_IDS:
        return 2
    if monster_id in ACT3_MONSTER_IDS:
        return 3
    if monster_id in ACT4_MONSTER_IDS:
        return 4
    return None


def _monster_is_elite(monster_id: str) -> bool:
    return monster_id in {"GremlinNob", "Lagavulin", "Sentry", "BookOfStabbing", "GremlinLeader", "Nemesis", "Reptomancer", "GiantHead", "Taskmaster", "SpireShield", "SpireSpear"}


def _monster_is_boss(monster_id: str) -> bool:
    return monster_id in {
        "Hexaghost",
        "SlimeBoss",
        "TheGuardian",
        "Champ",
        "Collector",
        "Automaton",
        "BronzeAutomaton",
        "AwakenedOne",
        "TimeEater",
        "DonuAndDeca",
        "Donu",
        "Deca",
        "CorruptHeart",
    }


def _monster_inventory() -> dict[str, type[Any]]:
    inventory: dict[str, type[Any]] = {}
    rng = MutableRNG.from_seed(1, rng_type="monsterHpRng")
    for registry_id, monster_cls in sorted(_monster_factory_registry().items()):
        if registry_id == "genericmonsterproxy":
            continue
        try:
            monster = monster_cls.create(rng, 0)
            monster_id = str(getattr(monster, "id", "") or "")
        except Exception:
            monster_id = ""
        if not monster_id:
            monster_id = _humanize_identifier(registry_id).replace(" ", "")
        inventory[monster_id] = monster_cls
    return inventory


def _monster_source_inventory() -> set[str]:
    return {
        canonical_id
        for canonical_id, entry in load_monster_truth_matrix().items()
        if bool(getattr(entry, "combat_capable", False))
    }


def _resolve_java_card_class_name(card_id: str) -> str:
    if card_id in MANUAL_JAVA_CARD_NAME_BY_RUNTIME_ID:
        return MANUAL_JAVA_CARD_NAME_BY_RUNTIME_ID[card_id]
    return card_id


def _java_card_file(repo_root: Path, card_id: str) -> Path | None:
    if card_id == "Burn+":
        card_id = "Burn"
    java_name = _resolve_java_card_class_name(card_id)
    for relative_dir in (
        "decompiled_src/com/megacrit/cardcrawl/cards/red",
        "decompiled_src/com/megacrit/cardcrawl/cards/green",
        "decompiled_src/com/megacrit/cardcrawl/cards/blue",
        "decompiled_src/com/megacrit/cardcrawl/cards/purple",
        "decompiled_src/com/megacrit/cardcrawl/cards/colorless",
        "decompiled_src/com/megacrit/cardcrawl/cards/curses",
        "decompiled_src/com/megacrit/cardcrawl/cards/status",
        "decompiled_src/com/megacrit/cardcrawl/cards/tempCards",
    ):
        candidate = repo_root / relative_dir / f"{java_name}.java"
        if candidate.exists():
            return candidate
    return None


def _decompiled_card_runtime_inventory(repo_root: Path) -> set[str]:
    inverse_manual = {value: key for key, value in MANUAL_JAVA_CARD_NAME_BY_RUNTIME_ID.items()}
    inventory: set[str] = set()
    for relative_dir in (
        "decompiled_src/com/megacrit/cardcrawl/cards/red",
        "decompiled_src/com/megacrit/cardcrawl/cards/green",
        "decompiled_src/com/megacrit/cardcrawl/cards/blue",
        "decompiled_src/com/megacrit/cardcrawl/cards/purple",
        "decompiled_src/com/megacrit/cardcrawl/cards/colorless",
        "decompiled_src/com/megacrit/cardcrawl/cards/curses",
        "decompiled_src/com/megacrit/cardcrawl/cards/status",
        "decompiled_src/com/megacrit/cardcrawl/cards/tempCards",
    ):
        folder = repo_root / relative_dir
        if not folder.exists():
            continue
        for java_file in folder.glob("*.java"):
            class_name = java_file.stem
            runtime_id = inverse_manual.get(class_name) or CARD_ID_ALIASES.get(class_name) or class_name
            inventory.add(str(runtime_id))
            if class_name == "LockOn":
                inventory.add("Lockon")
    if "Burn" in inventory:
        inventory.add("Burn+")
    return inventory


def _extract_super_call_args(text: str) -> list[str]:
    marker = "super("
    start = text.find(marker)
    if start < 0:
        return []
    idx = start + len(marker)
    depth = 1
    current: list[str] = []
    args: list[str] = []
    string_delim: str | None = None

    while idx < len(text):
        ch = text[idx]
        if string_delim is not None:
            current.append(ch)
            if ch == string_delim and text[idx - 1] != "\\":
                string_delim = None
            idx += 1
            continue
        if ch in {'"', "'"}:
            string_delim = ch
            current.append(ch)
            idx += 1
            continue
        if ch == "(":
            depth += 1
            current.append(ch)
            idx += 1
            continue
        if ch == ")":
            depth -= 1
            if depth == 0:
                args.append("".join(current).strip())
                break
            current.append(ch)
            idx += 1
            continue
        if ch == "," and depth == 1:
            args.append("".join(current).strip())
            current = []
            idx += 1
            continue
        current.append(ch)
        idx += 1
    return [arg for arg in args if arg]


def _extract_java_card_super_fields(text: str) -> dict[str, Any]:
    args = _extract_super_call_args(text)
    if len(args) < 9:
        return {}
    cost_match = re.search(r"-?\d+", args[3])
    type_match = re.search(r"CardType\.(\w+)", args[5])
    rarity_match = re.search(r"CardRarity\.(\w+)", args[7])
    target_match = re.search(r"CardTarget\.(\w+)", args[8] if len(args) > 8 else "")
    if cost_match is None or type_match is None or rarity_match is None or target_match is None:
        return {}
    target = target_match.group(1)
    return {
        "cost": int(cost_match.group(0)),
        "type": type_match.group(1),
        "rarity": rarity_match.group(1),
        "target": target,
        "target_required": target in {"ENEMY", "SELF_AND_ENEMY"},
    }


def _first_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text)
    return int(match.group(1)) if match else None


_JAVA_CARD_FACT_OVERRIDES: dict[str, dict[str, Any]] = {
    "Adrenaline": {"magic_number": 1},
    "AfterImage": {"magic_number": 1, "innate": False},
    "Backflip": {"magic_number": 2},
    "Eviscerate": {"magic_number": 3},
    "GeneticAlgorithm": {"block": 1},
    "Outmaneuver": {"magic_number": 2},
    "Predator": {"magic_number": 2},
    "RitualDagger": {"damage": 15},
    "Shiv": {"damage": 4},
    "Terror": {"magic_number": 99},
    "ToolsOfTheTrade": {"magic_number": 1},
}


def build_card_java_facts(repo_root: Path, card_id: str) -> dict[str, Any]:
    java_file = _java_card_file(repo_root, card_id)
    official = get_official_card_strings(card_id)
    if java_file is None:
        return {
            "source_kind": "decompiled_java_card",
            "missing": True,
            "official_key": str(getattr(official, "official_key", "") or ""),
            "official_name_en": str(getattr(official, "name_en", "") or ""),
            "official_name_zhs": str(getattr(official, "name_zhs", "") or ""),
            "translation_source": str(getattr(official, "translation_source", "") or ""),
            "description_source": str(getattr(official, "description_source", "") or ""),
        }
    text = java_file.read_text(encoding="utf-8", errors="ignore")
    super_fields = _extract_java_card_super_fields(text)
    path_text = str(java_file).replace("\\", "/")
    normalized_rarity = super_fields.get("rarity")
    if "/cards/curses/" in path_text:
        normalized_rarity = "CURSE"
    elif "/cards/status/" in path_text:
        normalized_rarity = "SPECIAL"
    facts = {
        "source_kind": "decompiled_java_card",
        "java_class": java_file.stem,
        "java_path": str(java_file),
        "official_key": str(getattr(official, "official_key", "") or ""),
        "official_name_en": str(getattr(official, "name_en", "") or ""),
        "official_name_zhs": str(getattr(official, "name_zhs", "") or ""),
        "translation_source": str(getattr(official, "translation_source", "") or ""),
        "description_source": str(getattr(official, "description_source", "") or ""),
        **super_fields,
        "rarity": normalized_rarity,
        "damage": _first_int(r"baseDamage\s*=\s*(\d+)", text) or 0,
        "block": _first_int(r"baseBlock\s*=\s*(\d+)", text) or 0,
        "magic_number": _first_int(r"baseMagicNumber\s*=\s*(\d+)", text)
        or _first_int(r"magicNumber\s*=\s*this\.baseMagicNumber\s*=\s*(\d+)", text)
        or 0,
        "exhaust": "this.exhaust = true;" in text,
        "ethereal": "this.isEthereal = true;" in text,
        "retain": "this.selfRetain = true;" in text or "this.retain = true;" in text,
        "innate": "this.isInnate = true;" in text,
    }
    facts.update(_JAVA_CARD_FACT_OVERRIDES.get(card_id, {}))
    return facts


def build_card_runtime_facts(card_id: str) -> dict[str, Any]:
    card = CardInstance(card_id)
    official = get_official_card_strings(card_id)
    return {
        "source_kind": "runtime_card_def",
        "cost": int(card.cost),
        "type": card.card_type.value,
        "rarity": card.rarity.value,
        "target_required": card_requires_target(card_id),
        "damage": max(0, int(card.base_damage)),
        "block": max(0, int(card.base_block)),
        "magic_number": max(0, int(card.base_magic_number)),
        "exhaust": bool(card.exhaust),
        "ethereal": bool(card.is_ethereal),
        "retain": bool(card.retain or card.self_retain),
        "innate": bool(card.is_innate),
        "official_key": str(getattr(official, "official_key", "") or ""),
        "official_name_en": str(getattr(official, "name_en", "") or ""),
        "official_name_zhs": str(getattr(official, "name_zhs", "") or ""),
        "official_desc_en": str(getattr(official, "description_en", "") or ""),
        "official_desc_zhs": str(getattr(official, "description_zhs", "") or ""),
        "official_upgrade_desc_en": str(getattr(official, "upgrade_description_en", "") or ""),
        "official_upgrade_desc_zhs": str(getattr(official, "upgrade_description_zhs", "") or ""),
        "translation_source": str(getattr(official, "translation_source", "") or ""),
        "description_source": str(getattr(official, "description_source", "") or ""),
        "official_name_cn_available": bool(str(getattr(official, "name_zhs", "") or "").strip()),
        "official_description_cn_available": bool(str(getattr(official, "description_zhs", "") or "").strip()),
    }


def build_relic_source_facts(relic_def: RelicDef) -> dict[str, Any]:
    return {
        "source_kind": "python_content_source",
        "tier": relic_def.tier.value if hasattr(relic_def.tier, "value") else str(relic_def.tier),
        "display_name": relic_def.name or relic_def.id,
        "display_name_en": getattr(relic_def, "name_en", "") or _humanize_identifier(relic_def.id),
        "price": relic_def.get_price(),
        "character_class": relic_def.character_class,
        "official_id": getattr(relic_def, "official_id", "") or relic_def.id,
        "class_name": getattr(relic_def, "class_name", "") or "",
        "spawn_rules": dict(getattr(relic_def, "spawn_rules", {}) or {}),
        "source_methods": list(getattr(relic_def, "source_methods", ()) or ()),
        "rng_notes": list(getattr(relic_def, "rng_notes", ()) or ()),
        "description_source": str(getattr(relic_def, "description_source", "") or ""),
        "translation_source": str(getattr(relic_def, "translation_source", "") or ""),
        "default_description_en": str(getattr(relic_def, "description_en", "") or ""),
        "default_description_zhs": str(getattr(relic_def, "description_zhs", "") or ""),
        "stateful_description_variants": [dict(item) for item in getattr(relic_def, "stateful_description_variants", ()) or ()],
        "ui_prompt_slots": list(getattr(relic_def, "ui_prompt_slots", ()) or ()),
        "wiki_url_en": str(getattr(relic_def, "wiki_url_en", "") or ""),
        "wiki_url_cn": str(getattr(relic_def, "wiki_url_cn", "") or ""),
        "truth_sources": dict(getattr(relic_def, "truth_sources", {}) or {}),
        "effect_signatures": build_relic_effect_signatures(relic_def),
        "effects": [
            {
                "type": effect.effect_type.value,
                "value": int(effect.value),
                "target": str(effect.target),
                "extra_type": str(effect.extra.get("type", "")),
            }
            for effect in relic_def.effects
        ],
    }


def build_potion_source_facts(potion_id: str) -> dict[str, Any]:
    potion_data = POTION_DEFINITIONS[potion_id]
    potion = potion_data.create_potion()
    return {
        "source_kind": "python_content_source",
        "display_name": getattr(potion_data, "NAME", potion.name),
        "rarity": getattr(getattr(potion_data, "RARITY", None), "name", ""),
        "character_class": getattr(getattr(potion_data, "CHAR_CLASS", None), "name", ""),
        "potency": int(getattr(potion, "potency", 0) or 0),
        "sacred_bark_potency": getattr(potion, "sacred_bark_potency", None),
        "is_thrown": bool(getattr(potion, "is_Thrown", False)),
        "effect_signatures": build_potion_effect_signatures(potion_id),
    }


def build_power_source_facts(power_id: str, power_cls: type[Any]) -> dict[str, Any]:
    instance = power_cls()
    return {
        "source_kind": "python_combat_source",
        "display_name": str(getattr(instance, "name", power_id)),
        "power_type": str(getattr(getattr(instance, "power_type", None), "name", "")),
        "turn_based": bool(getattr(instance, "is_turn_based", False)),
        "can_go_negative": bool(getattr(instance, "can_go_negative", False)),
        "callback_signatures": build_power_callback_signatures(power_cls),
    }


def build_monster_source_facts(monster_id: str, monster_cls: type[Any]) -> dict[str, Any]:
    rng = MutableRNG.from_seed(1, rng_type="monsterHpRng")
    monster = monster_cls.create(rng, 0)
    source_file = inspect.getsourcefile(monster_cls)
    sample_intents: list[str] = []
    if source_file:
        source_text = Path(source_file).read_text(encoding="utf-8", errors="ignore")
        sample_intents = sorted(set(re.findall(r"MonsterIntent\.([A-Z_]+)", source_text)))
    truth_entry = load_monster_truth_matrix().get(monster_id)
    return {
        "source_kind": "python_monster_source",
        "display_name": str(getattr(monster, "name", monster_id)),
        "act": getattr(truth_entry, "act", None) if truth_entry is not None else _monster_act(monster_id),
        "elite": getattr(truth_entry, "category", "") == "ELITE" if truth_entry is not None else _monster_is_elite(monster_id),
        "boss": getattr(truth_entry, "category", "") == "BOSS" if truth_entry is not None else _monster_is_boss(monster_id),
        "category": str(getattr(truth_entry, "category", "")),
        "encounters": list(getattr(truth_entry, "encounters", ()) or ()),
        "pool_buckets": list(getattr(truth_entry, "pool_buckets", ()) or ()),
        "internal_surface": str(getattr(truth_entry, "internal_surface", "")),
        "combat_capable": bool(getattr(truth_entry, "combat_capable", True)),
        "sample_intents": sample_intents,
        "state_signatures": build_monster_state_signatures(monster_id, monster_cls),
        "source_path": source_file,
    }


def build_monster_java_facts(monster_id: str) -> dict[str, Any]:
    truth_entry = load_monster_truth_matrix().get(monster_id)
    if truth_entry is None:
        return {
            "source_kind": "monster_truth_matrix",
            "missing": True,
        }
    sample_intents: list[str] = []
    state_signatures: list[str] = []
    monster_cls = _monster_inventory().get(monster_id)
    if monster_cls is not None:
        runtime_facts = build_monster_source_facts(monster_id, monster_cls)
        sample_intents = list(runtime_facts.get("sample_intents") or [])
        state_signatures = list(runtime_facts.get("state_signatures") or [])
    return {
        "source_kind": "monster_truth_matrix",
        "display_name": truth_entry.official_name_en or monster_id,
        "official_name_en": truth_entry.official_name_en,
        "official_name_zhs": truth_entry.official_name_zhs,
        "official_key": truth_entry.official_key,
        "java_class": truth_entry.java_class,
        "act": truth_entry.act,
        "elite": truth_entry.category == "ELITE",
        "boss": truth_entry.category == "BOSS",
        "category": truth_entry.category,
        "encounters": list(truth_entry.encounters),
        "pool_buckets": list(truth_entry.pool_buckets),
        "internal_surface": truth_entry.internal_surface,
        "combat_capable": truth_entry.combat_capable,
        "sample_intents": sample_intents,
        "state_signatures": state_signatures,
    }


def _event_choice_gating(choice: EventChoice) -> list[str]:
    gates: list[str] = []
    if choice.requires_card_removal:
        gates.append("requires_card_removal")
    if choice.requires_card_transform:
        gates.append("requires_card_transform")
    if choice.requires_card_upgrade:
        gates.append("requires_card_upgrade")
    if choice.requires_attack_card:
        gates.append("requires_attack_card")
    if choice.requires_upgrade_any:
        gates.append("requires_upgrade_any")
    if choice.cost:
        gates.append("cost")
    if choice.trigger_combat:
        gates.append("trigger_combat")
    if choice.search_level:
        gates.append("search")
    return gates


def _event_choice_effect_kinds(choice: EventChoice) -> list[str]:
    kinds: list[str] = [effect.effect_type.value for effect in choice.effects]
    if choice.trigger_combat:
        kinds.append("trigger_combat")
    if choice.search_level:
        kinds.append("search")
    if choice.trade_faces:
        kinds.append("trade_faces")
    return sorted(set(kinds))


@lru_cache(maxsize=8)
def _event_java_files(repo_root_str: str) -> dict[str, str]:
    events_root = Path(repo_root_str) / "decompiled_src" / "com" / "megacrit" / "cardcrawl" / "events"
    mapping: dict[str, str] = {}
    if not events_root.exists():
        return mapping
    for path in events_root.rglob("*.java"):
        mapping[path.stem] = str(path)
    return mapping


def _event_java_source_path(repo_root: Path, event_key: str) -> Path | None:
    java_files = _event_java_files(str(repo_root))
    java_stem = EVENT_ID_BY_KEY.get(event_key, "")
    source_path = java_files.get(java_stem)
    return Path(source_path) if source_path else None


@lru_cache(maxsize=8)
def _event_java_pool_inventory(repo_root_str: str) -> dict[str, set[str]]:
    repo_root = Path(repo_root_str)
    inventory = {
        "act1": set(),
        "act2": set(),
        "act3": set(),
        "shrine": set(),
        "special_one_time": set(),
    }
    dungeon_files = {
        "act1": repo_root / "decompiled_src" / "com" / "megacrit" / "cardcrawl" / "dungeons" / "Exordium.java",
        "act2": repo_root / "decompiled_src" / "com" / "megacrit" / "cardcrawl" / "dungeons" / "TheCity.java",
        "act3": repo_root / "decompiled_src" / "com" / "megacrit" / "cardcrawl" / "dungeons" / "TheBeyond.java",
    }
    for bucket, path in dungeon_files.items():
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for raw_key in re.findall(r'eventList\.add\("([^"]+)"\);', text):
            canonical = _resolve_event_key(raw_key)
            if canonical:
                inventory[bucket].add(canonical)
        for raw_key in re.findall(r'shrineList\.add\("([^"]+)"\);', text):
            canonical = _resolve_event_key(raw_key)
            if canonical:
                inventory["shrine"].add(canonical)

    abstract_dungeon = repo_root / "decompiled_src" / "com" / "megacrit" / "cardcrawl" / "dungeons" / "AbstractDungeon.java"
    if abstract_dungeon.exists():
        text = abstract_dungeon.read_text(encoding="utf-8", errors="ignore")
        for raw_key in re.findall(r'specialOneTimeEventList\.add\("([^"]+)"\);', text):
            canonical = _resolve_event_key(raw_key)
            if canonical:
                inventory["special_one_time"].add(canonical)
    return inventory


def _event_java_pool_bucket(repo_root: Path, event_key: str, fallback: str) -> str:
    inventory = _event_java_pool_inventory(str(repo_root))
    if event_key in inventory["act1"] or event_key in inventory["act2"] or event_key in inventory["act3"]:
        return "act_event"
    if event_key in inventory["shrine"]:
        return "shrine"
    if event_key in inventory["special_one_time"]:
        return "special_one_time"
    return fallback


def _event_java_initial_option_count(repo_root: Path, event_key: str, fallback: int) -> int:
    source_path = _event_java_source_path(repo_root, event_key)
    if source_path is None or not source_path.exists():
        return fallback
    text = source_path.read_text(encoding="utf-8", errors="ignore")
    constructor_region = text.split("@Override", 1)[0]
    count = len(re.findall(r"(?:setDialogOption|addDialogOption)\(", constructor_region))
    return count if count > 0 else fallback


def build_event_java_facts(repo_root: Path, event_key: str, event: Event | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root)
    runtime_event = event.clone() if event is not None else EVENTS_BY_KEY[event_key].clone()
    official = get_official_event_strings(event_key)
    source_descriptions = list(
        official.descriptions_en if official is not None and official.descriptions_en
        else getattr(runtime_event, "source_descriptions", []) or []
    )
    source_options = list(
        official.options_en if official is not None and official.options_en
        else getattr(runtime_event, "source_options", []) or []
    )
    source_path = _event_java_source_path(repo_root, event_key)
    wiki_aliases_en = list(getattr(runtime_event, "wiki_aliases_en", []) or [])
    wiki_aliases_cn = list(getattr(runtime_event, "wiki_aliases_cn", []) or [])
    return {
        "source_kind": "decompiled_event_source",
        "java_path": str(source_path) if source_path is not None else "",
        "java_class": source_path.stem if source_path is not None else str(getattr(runtime_event, "java_class", "") or ""),
        "event_key": event_key,
        "event_id": str(EVENT_ID_BY_KEY.get(event_key, getattr(runtime_event, "event_id", event_key))),
        "pool_bucket": _event_java_pool_bucket(repo_root, event_key, str(getattr(runtime_event, "pool_bucket", "") or "")),
        "gating_flags": list(getattr(runtime_event, "gating_flags", []) or []),
        "act": int(runtime_event.act),
        "choice_count": len(runtime_event.choices),
        "initial_option_count": _event_java_initial_option_count(repo_root, event_key, len(runtime_event.choices)),
        "source_description_count": len(source_descriptions),
        "source_option_count": len(source_options),
        "flow_kind": str(getattr(runtime_event, "flow_kind", "single_screen")),
        "stage_count": int(getattr(runtime_event, "stage_count", max(1, len(source_descriptions))) or 0),
        "reward_surface": str(getattr(runtime_event, "reward_surface", "none") or "none"),
        "event_combat_reentry": bool(getattr(runtime_event, "event_combat_reentry", False)),
        "dynamic_option_slots": int(getattr(runtime_event, "dynamic_option_slots", max(0, len(source_options) - len(runtime_event.choices))) or 0),
        "rng_streams": list(getattr(runtime_event, "rng_streams", []) or []),
        "wiki_aliases_en": wiki_aliases_en,
        "wiki_aliases_cn": wiki_aliases_cn,
        "official_name_en_available": bool(getattr(official, "name_en", "") or getattr(runtime_event, "name", "")),
        "official_name_cn_available": bool(getattr(official, "name_zhs", "") or getattr(runtime_event, "name_cn", "")),
        "official_description_en_available": bool(source_descriptions),
        "official_description_cn_available": bool(getattr(official, "descriptions_zhs", ()) or getattr(runtime_event, "source_descriptions_cn", [])),
        "official_option_en_available": bool(source_options),
        "official_option_cn_available": bool(getattr(official, "options_zhs", ()) or getattr(runtime_event, "source_options_cn", [])),
        "choice_effect_signatures": build_event_choice_effect_signatures(runtime_event),
        "choices": [
            {
                "index": idx,
                "gating": _event_choice_gating(choice),
                "effect_kinds": _event_choice_effect_kinds(choice),
            }
            for idx, choice in enumerate(runtime_event.choices)
        ],
    }


def build_event_source_facts(event: Event) -> dict[str, Any]:
    event_key = str(getattr(event, "event_key", "") or getattr(event, "name", "") or getattr(event, "id", ""))
    source_descriptions = list(getattr(event, "source_descriptions", []) or [])
    source_descriptions_cn = list(getattr(event, "source_descriptions_cn", []) or [])
    source_options = list(getattr(event, "source_options", []) or [])
    source_options_cn = list(getattr(event, "source_options_cn", []) or [])
    initial_option_count = _event_java_initial_option_count(REPO_ROOT, event_key, len(event.choices))
    return {
        "source_kind": "python_run_source",
        "event_key": event_key,
        "event_id": str(getattr(event, "event_id", getattr(event, "id", "")) or ""),
        "pool_bucket": str(getattr(event, "pool_bucket", "") or ""),
        "gating_flags": list(getattr(event, "gating_flags", []) or []),
        "java_class": str(getattr(event, "java_class", "") or ""),
        "act": int(event.act),
        "choice_count": len(event.choices),
        "initial_option_count": initial_option_count,
        "source_description_count": len(source_descriptions),
        "source_description_count_cn": len(source_descriptions_cn),
        "source_option_count": len(source_options),
        "source_option_count_cn": len(source_options_cn),
        "flow_kind": str(getattr(event, "flow_kind", "single_screen")),
        "stage_count": int(getattr(event, "stage_count", max(1, len(source_descriptions))) or 0),
        "reward_surface": str(getattr(event, "reward_surface", "none") or "none"),
        "event_combat_reentry": bool(getattr(event, "event_combat_reentry", False)),
        "dynamic_option_slots": int(getattr(event, "dynamic_option_slots", max(0, len(source_options) - len(event.choices))) or 0),
        "rng_streams": list(getattr(event, "rng_streams", []) or []),
        "wiki_aliases_en": list(getattr(event, "wiki_aliases_en", []) or []),
        "wiki_aliases_cn": list(getattr(event, "wiki_aliases_cn", []) or []),
        "official_name_en_available": bool(str(getattr(event, "name", "") or "")),
        "official_name_cn_available": bool(str(getattr(event, "name_cn", "") or "")),
        "official_description_en_available": bool(source_descriptions),
        "official_description_cn_available": bool(source_descriptions_cn),
        "official_option_en_available": bool(source_options),
        "official_option_cn_available": bool(source_options_cn),
        "choice_effect_signatures": build_event_choice_effect_signatures(event),
        "choices": [
            {
                "index": idx,
                "gating": _event_choice_gating(choice),
                "effect_kinds": _event_choice_effect_kinds(choice),
            }
            for idx, choice in enumerate(event.choices)
        ],
    }


def build_neow_source_facts() -> dict[str, Any]:
    event_strings = get_official_neow_event_strings()
    reward_strings = get_official_neow_reward_strings()
    return {
        "source_kind": "python_run_source",
        "screen_count": 4,
        "reward_option_groups": {"mini": 2, "full": 4},
        "rng_streams": ["neow_rng"],
        "event_text_count": len(event_strings.text_en),
        "event_text_count_cn": len(event_strings.text_zhs),
        "event_option_count": len(event_strings.options_en),
        "event_option_count_cn": len(event_strings.options_zhs),
        "reward_text_count": len(reward_strings.text_en),
        "reward_text_count_cn": len(reward_strings.text_zhs),
        "reward_option_count": len(reward_strings.options_en),
        "reward_option_count_cn": len(reward_strings.options_zhs),
        "unique_reward_count": len(reward_strings.unique_rewards_en),
        "unique_reward_count_cn": len(reward_strings.unique_rewards_zhs),
        "wiki_aliases_en": [str(event_strings.names_en[0] if event_strings.names_en else "Neow")],
        "wiki_aliases_cn": [str(event_strings.names_zhs[0] if event_strings.names_zhs else "")],
        "profile_dependencies": ["neow_intro_seen", "spirits", "highest_unlocked_ascension", "last_ascension_level"],
    }


def build_neow_java_facts() -> dict[str, Any]:
    event_strings = get_official_neow_event_strings()
    reward_strings = get_official_neow_reward_strings()
    return {
        "source_kind": "official_neow_source",
        "screen_count": 4,
        "reward_option_groups": {"mini": 2, "full": 4},
        "rng_streams": ["neow_rng"],
        "event_text_count": len(event_strings.text_en),
        "event_text_count_cn": len(event_strings.text_zhs),
        "event_option_count": len(event_strings.options_en),
        "event_option_count_cn": len(event_strings.options_zhs),
        "reward_text_count": len(reward_strings.text_en),
        "reward_text_count_cn": len(reward_strings.text_zhs),
        "reward_option_count": len(reward_strings.options_en),
        "reward_option_count_cn": len(reward_strings.options_zhs),
        "unique_reward_count": len(reward_strings.unique_rewards_en),
        "unique_reward_count_cn": len(reward_strings.unique_rewards_zhs),
        "wiki_aliases_en": [str(event_strings.names_en[0] if event_strings.names_en else "Neow")],
        "wiki_aliases_cn": [str(event_strings.names_zhs[0] if event_strings.names_zhs else "")],
        "profile_dependencies": ["neow_intro_seen", "spirits", "highest_unlocked_ascension", "last_ascension_level"],
    }


def build_room_type_source_facts(room_type: RoomType) -> dict[str, Any]:
    return {
        "source_kind": "python_run_source",
        "enum_name": room_type.name,
        "symbol": room_type.value,
    }


def build_ui_term_source_facts(command: str) -> dict[str, Any]:
    return {
        "source_kind": "terminal_command_surface",
        "contexts": list(CLI_UI_TERMS.get(command, {}).get("contexts", [])),
    }


def _card_page_candidates(card_id: str) -> list[str]:
    java_name = _resolve_java_card_class_name(card_id)
    return _unique_nonempty([_humanize_identifier(java_name), _humanize_identifier(card_id)])


def _generic_en_page_candidates(entity_type: str, entity_id: str, runtime_name_en: str) -> list[str]:
    if entity_type == "card":
        return _card_page_candidates(entity_id)
    if entity_type == "event":
        aliases = list(EVENT_WIKI_NAME_ALIASES.get(entity_id, {}).get("en", []))
        return _unique_nonempty([*aliases, runtime_name_en, _humanize_identifier(entity_id)])
    if entity_type == "relic":
        return _unique_nonempty([runtime_name_en, _humanize_identifier(entity_id)])
    return _unique_nonempty([runtime_name_en, _humanize_identifier(entity_id)])


def _generic_cn_page_candidates(entity_type: str, entity_id: str, runtime_name_cn: str, runtime_name_en: str) -> list[str]:
    if entity_type == "relic":
        policy = get_translation_policy_entry("relic", entity_id)
        candidates: list[str] = []
        if policy is not None and policy.huiji_page_or_title.strip():
            candidates.append(policy.huiji_page_or_title.strip())
        if policy is not None and policy.alignment_status == "approved_alias" and policy.runtime_name_cn.strip():
            candidates.append(policy.runtime_name_cn.strip())
        if _looks_cataloged_cn(runtime_name_cn):
            candidates.append(runtime_name_cn)
        if _contains_cjk(runtime_name_en):
            candidates.append(runtime_name_en)
        return _unique_nonempty(candidates)
    candidates = list(EVENT_WIKI_NAME_ALIASES.get(entity_id, {}).get("cn", [])) if entity_type == "event" else []
    if _looks_cataloged_cn(runtime_name_cn):
        candidates.append(runtime_name_cn)
    if _contains_cjk(runtime_name_en):
        candidates.append(runtime_name_en)
    return _unique_nonempty(candidates)


def _parse_relic_wiki_summary_facts(summary: str) -> dict[str, Any]:
    text = str(summary or "").strip()
    if not text:
        return {}
    facts: dict[str, Any] = {}
    tier_match = re.search(
        r"\bis\s+(?:an?|the)\s+(?:[\w-]+\s+){0,4}?(Starter|Common|Uncommon|Rare|Boss|Shop|Event|Special)\s+Relic\b",
        text,
        re.I,
    )
    if tier_match:
        facts["tier"] = tier_match.group(1).upper()
    class_match = re.search(r"\b(Ironclad|Silent|Defect|Watcher)\b(?:\s+Only)?", text)
    if class_match:
        facts["character_class"] = class_match.group(1).upper()
    return facts


def _normalize_relic_wiki_infobox_facts(facts: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    rarity_text = str(facts.get("rarity") or facts.get("tier") or "").strip()
    if rarity_text:
        tier_match = re.search(r"\b(Starter|Common|Uncommon|Rare|Boss|Shop|Event|Special)\b", rarity_text, re.I)
        if tier_match:
            normalized["tier"] = tier_match.group(1).upper()

    character_text = str(facts.get("character") or facts.get("class") or facts.get("character_class") or "").strip()
    if character_text:
        class_match = re.search(r"\b(Ironclad|Silent|Defect|Watcher)\b", character_text, re.I)
        if class_match:
            normalized["character_class"] = class_match.group(1).upper()

    description = str(facts.get("description") or facts.get("effect") or facts.get("text") or "").strip()
    if description:
        normalized["description"] = description

    return normalized


def _augment_relic_wiki_page(page: WikiPageSnapshot, *, source_lang: str) -> WikiPageSnapshot:
    if page.error:
        return page
    payload = dict(page.payload or {})
    facts = dict(payload.get("facts") or {})
    facts.update(_normalize_relic_wiki_infobox_facts(facts))
    if source_lang == "en" and not {"tier", "character_class"} <= set(facts):
        for key, value in _parse_relic_wiki_summary_facts(page.summary).items():
            facts.setdefault(key, value)
    payload["facts"] = facts
    return WikiPageSnapshot(
        source=page.source,
        requested_title=page.requested_title,
        resolved_title=page.resolved_title,
        url=page.url,
        summary=page.summary,
        payload=payload,
        attempts=list(page.attempts or []),
        error=page.error,
    )


def _fetch_entity_wiki_pages(
    scraper: BilingualWikiScraper,
    *,
    entity_type: str,
    entity_id: str,
    runtime_name_en: str,
    runtime_name_cn: str,
    enable_network: bool,
) -> tuple[WikiPageSnapshot, WikiPageSnapshot]:
    if not enable_network or entity_type in {"room_type", "ui_term"}:
        return WikiPageSnapshot(), WikiPageSnapshot()

    en_candidates = _generic_en_page_candidates(entity_type, entity_id, runtime_name_en)
    cn_candidates = _generic_cn_page_candidates(entity_type, entity_id, runtime_name_cn, runtime_name_en)

    en_page = WikiPageSnapshot.from_dict(scraper.fetch_page_with_fallback(EN_SOURCE_ORDER, en_candidates))
    cn_page = WikiPageSnapshot.from_dict(scraper.fetch_page_with_fallback(CN_SOURCE_ORDER, cn_candidates))
    if entity_type == "relic":
        en_page = _augment_relic_wiki_page(en_page, source_lang="en")
        cn_page = _augment_relic_wiki_page(cn_page, source_lang="cn")
    return en_page, cn_page


def _first_nonempty(*values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _event_runtime_description(event: Event) -> str:
    snippets = []
    for choice in event.choices[:3]:
        text = str(choice.description_cn or choice.description or "").strip()
        if text:
            snippets.append(text)
    return " | ".join(snippets)


def _neow_runtime_description() -> str:
    event_strings = get_official_neow_event_strings()
    reward_strings = get_official_neow_reward_strings()
    snippets = [
        str(event_strings.text_zhs[0] if event_strings.text_zhs else event_strings.text_en[0] if event_strings.text_en else "").strip(),
        str(reward_strings.text_zhs[28] if len(reward_strings.text_zhs) > 28 else "").strip(),
        str(reward_strings.unique_rewards_zhs[0] if reward_strings.unique_rewards_zhs else reward_strings.unique_rewards_en[0] if reward_strings.unique_rewards_en else "").strip(),
    ]
    return " | ".join(text for text in snippets if text)


def _source_inventory_from_repo(repo_root: Path, *, entity_types: set[str] | None = None) -> dict[str, list[str]]:
    inventory = {
        "card": sorted(_decompiled_card_runtime_inventory(repo_root)),
        "relic": sorted(ALL_RELICS.keys()),
        "potion": sorted(POTION_DEFINITIONS.keys()),
        "power": sorted(power_id for power_id, _ in _power_class_inventory()),
        "monster": sorted(_monster_source_inventory()),
        "event": sorted(_event_inventory().keys()),
        "neow": ["NeowEvent"],
        "room_type": sorted(room_type.name for room_type in RoomType),
        "ui_term": sorted(CLI_UI_TERMS.keys()),
    }
    return _filter_mapping_by_entity_types(inventory, entity_types)


def build_cli_raw_snapshot(
    repo_root: Path,
    *,
    enable_network: bool = False,
    scraper: BilingualWikiScraper | None = None,
    entity_types: Iterable[str] | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_root)
    entity_type_filter = _normalize_entity_type_filter(entity_types)
    if enable_network and scraper is None:
        scraper = BilingualWikiScraper(use_cache=True)

    records: list[RawEntitySnapshot] = []

    if entity_type_filter is None or "card" in entity_type_filter:
        for card_id in sorted(ALL_CARD_DEFS):
            runtime_name_cn, runtime_desc = get_card_info(card_id)
            official = get_official_card_strings(card_id)
            runtime_name_en = str(getattr(official, "name_en", "") or _humanize_identifier(_resolve_java_card_class_name(card_id)))
            runtime_facts = build_card_runtime_facts(card_id)
            java_facts = build_card_java_facts(repo_root, card_id)
            en_wiki, cn_wiki = (
                _fetch_entity_wiki_pages(
                    scraper,
                    entity_type="card",
                    entity_id=card_id,
                    runtime_name_en=runtime_name_en,
                    runtime_name_cn=runtime_name_cn,
                    enable_network=enable_network,
                )
                if scraper is not None
                else (WikiPageSnapshot(), WikiPageSnapshot())
            )
            records.append(
                RawEntitySnapshot(
                    entity_type="card",
                    entity_id=card_id,
                    runtime_name_en=runtime_name_en,
                    runtime_name_cn=runtime_name_cn,
                    runtime_desc_runtime=runtime_desc,
                    runtime_facts=runtime_facts,
                    java_facts=java_facts,
                    en_wiki=en_wiki,
                    cn_wiki=cn_wiki,
                )
            )

    if entity_type_filter is None or "relic" in entity_type_filter:
        for relic_id, relic_def in sorted(ALL_RELICS.items()):
            source_facts = build_relic_source_facts(relic_def)
            runtime_name_en = str(source_facts.get("display_name_en") or _humanize_identifier(relic_id))
            runtime_name_cn = translate_relic(relic_id)
            en_wiki, cn_wiki = (
                _fetch_entity_wiki_pages(
                    scraper,
                    entity_type="relic",
                    entity_id=relic_id,
                    runtime_name_en=runtime_name_en,
                    runtime_name_cn=runtime_name_cn,
                    enable_network=enable_network,
                )
                if scraper is not None
                else (WikiPageSnapshot(), WikiPageSnapshot())
            )
            records.append(
                RawEntitySnapshot(
                    entity_type="relic",
                    entity_id=relic_id,
                    runtime_name_en=runtime_name_en,
                    runtime_name_cn=runtime_name_cn,
                    runtime_desc_runtime=str(getattr(relic_def, "description", "") or ""),
                    runtime_facts=source_facts,
                    java_facts=source_facts,
                    en_wiki=en_wiki,
                    cn_wiki=cn_wiki,
                )
            )

    if entity_type_filter is None or "potion" in entity_type_filter:
        for potion_id in sorted(POTION_DEFINITIONS):
            source_facts = build_potion_source_facts(potion_id)
            potion_data = POTION_DEFINITIONS[potion_id]
            runtime_name_en = _humanize_identifier(potion_id)
            runtime_name_cn = translate_potion(potion_id)
            en_wiki, cn_wiki = (
                _fetch_entity_wiki_pages(
                    scraper,
                    entity_type="potion",
                    entity_id=potion_id,
                    runtime_name_en=runtime_name_en,
                    runtime_name_cn=runtime_name_cn,
                    enable_network=enable_network,
                )
                if scraper is not None
                else (WikiPageSnapshot(), WikiPageSnapshot())
            )
            records.append(
                RawEntitySnapshot(
                    entity_type="potion",
                    entity_id=potion_id,
                    runtime_name_en=runtime_name_en,
                    runtime_name_cn=runtime_name_cn,
                    runtime_desc_runtime=str(getattr(potion_data, "DESCRIPTION", "") or ""),
                    runtime_facts=source_facts,
                    java_facts=source_facts,
                    en_wiki=en_wiki,
                    cn_wiki=cn_wiki,
                )
            )

    if entity_type_filter is None or "power" in entity_type_filter:
        for power_id, power_cls in _power_class_inventory():
            source_facts = build_power_source_facts(power_id, power_cls)
            runtime_name_en = str(source_facts.get("display_name") or _humanize_identifier(power_id))
            runtime_name_cn = translate_power(power_id)
            en_wiki, cn_wiki = (
                _fetch_entity_wiki_pages(
                    scraper,
                    entity_type="power",
                    entity_id=power_id,
                    runtime_name_en=runtime_name_en,
                    runtime_name_cn=runtime_name_cn,
                    enable_network=enable_network,
                )
                if scraper is not None
                else (WikiPageSnapshot(), WikiPageSnapshot())
            )
            records.append(
                RawEntitySnapshot(
                    entity_type="power",
                    entity_id=power_id,
                    runtime_name_en=runtime_name_en,
                    runtime_name_cn=runtime_name_cn,
                    runtime_desc_runtime=get_power_str(power_id, 0),
                    runtime_facts=source_facts,
                    java_facts=source_facts,
                    en_wiki=en_wiki,
                    cn_wiki=cn_wiki,
                )
            )

    if entity_type_filter is None or "monster" in entity_type_filter:
        for monster_id, monster_cls in sorted(_monster_inventory().items()):
            runtime_facts = build_monster_source_facts(monster_id, monster_cls)
            java_facts = build_monster_java_facts(monster_id)
            runtime_name_en = str(runtime_facts.get("display_name") or _humanize_identifier(monster_id))
            runtime_name_cn = translate_monster(monster_id)
            runtime_desc = ", ".join(runtime_facts.get("sample_intents") or [])
            en_wiki, cn_wiki = (
                _fetch_entity_wiki_pages(
                    scraper,
                    entity_type="monster",
                    entity_id=monster_id,
                    runtime_name_en=runtime_name_en,
                    runtime_name_cn=runtime_name_cn,
                    enable_network=enable_network,
                )
                if scraper is not None
                else (WikiPageSnapshot(), WikiPageSnapshot())
            )
            records.append(
                RawEntitySnapshot(
                    entity_type="monster",
                    entity_id=monster_id,
                    runtime_name_en=runtime_name_en,
                    runtime_name_cn=runtime_name_cn,
                    runtime_desc_runtime=runtime_desc,
                    runtime_facts=runtime_facts,
                    java_facts=java_facts,
                    en_wiki=en_wiki,
                    cn_wiki=cn_wiki,
                )
            )

    if entity_type_filter is None or "event" in entity_type_filter:
        for event_id, event in sorted(_event_inventory().items()):
            source_facts = build_event_source_facts(event)
            java_facts = build_event_java_facts(repo_root, event_id, event)
            runtime_name_en = str(getattr(event, "name", "") or getattr(event, "event_key", "") or event_id)
            runtime_name_cn = translate_event_name(event)
            en_wiki, cn_wiki = (
                _fetch_entity_wiki_pages(
                    scraper,
                    entity_type="event",
                    entity_id=event_id,
                    runtime_name_en=runtime_name_en,
                    runtime_name_cn=runtime_name_cn,
                    enable_network=enable_network,
                )
                if scraper is not None
                else (WikiPageSnapshot(), WikiPageSnapshot())
            )
            records.append(
                RawEntitySnapshot(
                    entity_type="event",
                    entity_id=event_id,
                    runtime_name_en=runtime_name_en,
                    runtime_name_cn=runtime_name_cn,
                    runtime_desc_runtime=_event_runtime_description(event),
                    runtime_facts=source_facts,
                    java_facts=java_facts,
                    en_wiki=en_wiki,
                    cn_wiki=cn_wiki,
                )
            )
    if entity_type_filter is None or "neow" in entity_type_filter:
        neow_event_strings = get_official_neow_event_strings()
        neow_name_en = str(neow_event_strings.names_en[0] if neow_event_strings.names_en else "Neow")
        neow_name_cn = str(neow_event_strings.names_zhs[0] if neow_event_strings.names_zhs else neow_name_en)
        neow_facts = build_neow_source_facts()
        neow_java_facts = build_neow_java_facts()
        en_wiki, cn_wiki = (
            _fetch_entity_wiki_pages(
                scraper,
                entity_type="neow",
                entity_id="NeowEvent",
                runtime_name_en=neow_name_en,
                runtime_name_cn=neow_name_cn,
                enable_network=enable_network,
            )
            if scraper is not None
            else (WikiPageSnapshot(), WikiPageSnapshot())
        )
        records.append(
            RawEntitySnapshot(
                entity_type="neow",
                entity_id="NeowEvent",
                runtime_name_en=neow_name_en,
                runtime_name_cn=neow_name_cn,
                runtime_desc_runtime=_neow_runtime_description(),
                runtime_facts=neow_facts,
                java_facts=neow_java_facts,
                en_wiki=en_wiki,
                cn_wiki=cn_wiki,
            )
        )

    if entity_type_filter is None or "room_type" in entity_type_filter:
        for room_type in RoomType:
            runtime_name_en = _humanize_identifier(room_type.name.title())
            runtime_name_cn = translate_room_type(room_type)
            source_facts = build_room_type_source_facts(room_type)
            records.append(
                RawEntitySnapshot(
                    entity_type="room_type",
                    entity_id=room_type.name,
                    runtime_name_en=runtime_name_en,
                    runtime_name_cn=runtime_name_cn,
                    runtime_desc_runtime=room_type.value,
                    runtime_facts=source_facts,
                    java_facts=source_facts,
                )
            )

    if entity_type_filter is None or "ui_term" in entity_type_filter:
        for command in sorted(CLI_UI_TERMS):
            source_facts = build_ui_term_source_facts(command)
            records.append(
                RawEntitySnapshot(
                    entity_type="ui_term",
                    entity_id=command,
                    runtime_name_en=command,
                    runtime_name_cn=UI_TERM_CN_NAMES.get(command, command),
                    runtime_desc_runtime=", ".join(source_facts["contexts"]),
                    runtime_facts=source_facts,
                    java_facts=source_facts,
                )
            )

    runtime_inventory: dict[str, list[str]] = {entity_type: [] for entity_type in ENTITY_TYPES}
    for record in records:
        runtime_inventory.setdefault(record.entity_type, []).append(record.entity_id)
    runtime_inventory = {entity_type: sorted(set(values)) for entity_type, values in runtime_inventory.items() if values}

    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "repo_root": str(repo_root),
        "network_enabled": bool(enable_network),
        "entity_types": sorted(entity_type_filter or set(ENTITY_TYPES)),
        "source_priority": {
            "mechanics_truth": "decompiled_src",
            "english_reference": EN_SOURCE_ORDER,
            "chinese_reference": CN_SOURCE_ORDER,
        },
        "catalog_overrides": _filter_mapping_by_entity_types(_catalog_override_keys(), entity_type_filter),
        "translation_policy": list(load_translation_policy_bundle().get("records") or []),
        "runtime_inventory": runtime_inventory,
        "source_inventory": _source_inventory_from_repo(repo_root, entity_types=entity_type_filter),
        "records": [record.to_dict() for record in records],
    }


def normalize_raw_snapshot(raw_snapshot: dict[str, Any]) -> dict[str, Any]:
    records = _coerce_raw_records(raw_snapshot)
    policy_entries = _policy_entries_from_snapshot(raw_snapshot)
    normalized_records: list[NormalizedEntitySnapshot] = []

    for record in records:
        policy_entry = policy_entries.get((record.entity_type, record.entity_id))
        policy = _policy_entry_to_dict(policy_entry)
        en_page = _first_nonempty(record.en_wiki.resolved_title, record.en_wiki.requested_title)
        cn_page = _first_nonempty(
            record.cn_wiki.resolved_title,
            record.cn_wiki.requested_title,
            policy["huiji_page_or_title"],
        )
        en_name = _first_nonempty(record.en_wiki.payload.get("name"), record.en_wiki.payload.get("title"), en_page)
        cn_name = _first_nonempty(
            record.cn_wiki.payload.get("name"),
            record.cn_wiki.payload.get("title"),
            cn_page,
            policy["huiji_page_or_title"],
        )
        en_match = _match_kind(record.entity_id, record.runtime_name_en, en_name, en_page)
        cn_match = _match_kind(record.entity_id, record.runtime_name_cn or record.runtime_name_en, cn_name, cn_page)

        audit_status = dict(record.audit_status)
        audit_status.setdefault("en_wiki_match", en_match)
        audit_status.setdefault("cn_wiki_match", cn_match)
        audit_status.setdefault("translation_reference_source", policy["reference_source"])
        audit_status.setdefault("translation_alignment_status", policy["alignment_status"])
        reference_source = str(policy["reference_source"] or record.runtime_facts.get("translation_source") or "")
        alignment_status = str(policy["alignment_status"] or "")
        if (
            not alignment_status
            and record.entity_type == "card"
            and bool(str(record.runtime_facts.get("official_name_zhs", "") or "").strip())
        ):
            alignment_status = "exact_match"

        normalized_records.append(
            NormalizedEntitySnapshot(
                entity_type=record.entity_type,
                entity_id=record.entity_id,
                runtime_name_en=record.runtime_name_en,
                runtime_name_cn=record.runtime_name_cn,
                runtime_desc_runtime=record.runtime_desc_runtime,
                java_facts=record.java_facts,
                en_wiki_page=en_page,
                en_wiki_name=en_name,
                en_wiki_summary=record.en_wiki.summary,
                cn_wiki_page=cn_page,
                cn_wiki_name=cn_name,
                cn_wiki_summary=record.cn_wiki.summary,
                audit_status=audit_status,
                audit_notes=list(record.audit_notes),
                runtime_facts=record.runtime_facts,
                match_meta={
                    "en_match": en_match,
                    "cn_match": cn_match,
                    "en_source": record.en_wiki.source,
                    "cn_source": record.cn_wiki.source,
                },
                reference_source=reference_source,
                alignment_status=alignment_status,
                huiji_page_or_title=policy["huiji_page_or_title"],
                approved_alias_note=policy["approved_alias_note"],
            )
        )

    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "generated_at": raw_snapshot.get("generated_at"),
        "normalized_at": _utc_now(),
        "repo_root": raw_snapshot.get("repo_root"),
        "network_enabled": bool(raw_snapshot.get("network_enabled")),
        "source_priority": dict(raw_snapshot.get("source_priority") or {}),
        "catalog_overrides": dict(raw_snapshot.get("catalog_overrides") or {}),
        "translation_policy": list(raw_snapshot.get("translation_policy") or load_translation_policy_bundle().get("records") or []),
        "runtime_inventory": dict(raw_snapshot.get("runtime_inventory") or {}),
        "source_inventory": dict(raw_snapshot.get("source_inventory") or {}),
        "record_count": len(normalized_records),
        "records": [record.to_dict() for record in normalized_records],
    }


def _description_status(record: NormalizedEntitySnapshot) -> str:
    description = str(record.runtime_desc_runtime or "").strip()
    if not description:
        return "missing_runtime_desc"
    if _looks_mojibake(description):
        return "mojibake_runtime_desc"
    return "ok"


def build_translation_audit(records: Any) -> dict[str, Any]:
    normalized_records = _coerce_normalized_records(records)
    findings: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    description_counts: Counter[str] = Counter()

    for record in normalized_records:
        if _looks_mojibake(record.runtime_name_cn):
            status = "mojibake_or_corrupt"
            note = "runtime/CLI 中文名存在明显乱码或编码污染"
        elif not _looks_cataloged_cn(record.runtime_name_cn):
            status = "missing_cn"
            note = "runtime/CLI 中文名缺失或未本地化"
        elif record.cn_wiki_name or record.cn_wiki_page:
            cn_match = str(record.match_meta.get("cn_match", "missing"))
            if cn_match == "exact":
                status = "exact_match"
                note = "runtime/CLI 中文名与 Huiji 常用标题一致"
            elif cn_match == "alias":
                status = "accepted_alias"
                note = "runtime/CLI 中文名与 Huiji 标题存在可接受别名差异"
            else:
                status = "likely_wrong_translation"
                note = "runtime/CLI 中文名与 Huiji 标题冲突"
        else:
            status = "accepted_alias"
            note = "缺少 Huiji 页面对照，保留 runtime/CLI 中文名"

        desc_status = _description_status(record)
        status_counts[status] += 1
        description_counts[desc_status] += 1
        findings.append(
            {
                "entity_type": record.entity_type,
                "entity_id": record.entity_id,
                "status": status,
                "runtime_name_cn": record.runtime_name_cn,
                "cn_wiki_name": record.cn_wiki_name,
                "cn_wiki_page": record.cn_wiki_page,
                "runtime_desc_runtime": record.runtime_desc_runtime,
                "description_status": desc_status,
                "note": note,
            }
        )

    return {
        "summary": {
            "total": len(findings),
            "by_status": dict(status_counts),
            "description_status": dict(description_counts),
        },
        "findings": findings,
    }


def _runtime_name_issue(record: NormalizedEntitySnapshot) -> str:
    runtime_name_cn = str(record.runtime_name_cn or "").strip()
    if _looks_mojibake(runtime_name_cn):
        return "mojibake_or_corrupt"
    if (
        record.entity_type == "card"
        and bool(str(record.runtime_facts.get("official_name_zhs", "") or "").strip())
        and _normalize_lookup_key(runtime_name_cn)
        == _normalize_lookup_key(str(record.runtime_facts.get("official_name_zhs", "") or "").strip())
    ):
        return "ok"
    if not _looks_cataloged_cn(runtime_name_cn):
        return "missing_cn"
    return "ok"


def _translation_status_note(status: str) -> str:
    if status == "exact_match":
        return "CLI 中文名与 Huiji 参考标题一致。"
    if status == "approved_alias":
        return "CLI 中文名使用了已在策略表中登记的批准别名。"
    if status == "wiki_missing":
        return "Huiji 缺少可用词条，当前名称只能依赖本地 catalog 或英文 fallback。"
    if status == "needs_review":
        return "CLI 中文名接近 Huiji 标题，但未在批准别名表中登记。"
    if status == "likely_wrong_translation":
        return "CLI 中文名与 Huiji 参考明显不一致，疑似误译。"
    return ""


def _resolve_translation_status(record: NormalizedEntitySnapshot) -> tuple[str, str]:
    policy_status = str(record.alignment_status or "").strip()
    if (
        record.entity_type == "card"
        and bool(str(record.runtime_facts.get("official_name_zhs", "") or "").strip())
    ):
        official_name_cn = str(record.runtime_facts.get("official_name_zhs", "") or "").strip()
        if policy_status == "approved_alias":
            return "approved_alias", record.approved_alias_note or "官方卡牌简中保留，Huiji 页名差异已登记为批准别名。"
        if _normalize_lookup_key(record.runtime_name_cn) == _normalize_lookup_key(official_name_cn):
            return "exact_match", "CLI 中文名与官方卡牌简中资源一致。"
        return "likely_wrong_translation", "CLI 中文名与官方卡牌简中资源不一致。"

    if policy_status in ALIGNMENT_STATUSES:
        return policy_status, _translation_status_note(policy_status)

    has_huiji_reference = bool(
        _first_nonempty(
            record.huiji_page_or_title,
            record.cn_wiki_page,
            record.cn_wiki_name,
        )
    )
    if not has_huiji_reference:
        return "wiki_missing", _translation_status_note("wiki_missing")

    cn_match = str(record.match_meta.get("cn_match", "missing") or "missing")
    if cn_match == "exact":
        return "exact_match", _translation_status_note("exact_match")
    if cn_match == "alias":
        return "needs_review", _translation_status_note("needs_review")
    return "likely_wrong_translation", _translation_status_note("likely_wrong_translation")


def build_translation_audit(records: Any) -> dict[str, Any]:
    normalized_records = _coerce_normalized_records(records)
    findings: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    runtime_name_issue_counts: Counter[str] = Counter()
    description_counts: Counter[str] = Counter()

    for record in normalized_records:
        status, note = _resolve_translation_status(record)
        runtime_name_issue = _runtime_name_issue(record)
        desc_status = _description_status(record)
        status_counts[status] += 1
        runtime_name_issue_counts[runtime_name_issue] += 1
        description_counts[desc_status] += 1

        reference_source = str(record.reference_source or "").strip()
        huiji_page_or_title = _first_nonempty(record.huiji_page_or_title, record.cn_wiki_page, record.cn_wiki_name) or ""
        if not reference_source and huiji_page_or_title:
            reference_source = BilingualWikiScraper.SOURCE_CN_HUIJI

        findings.append(
            {
                "entity_type": record.entity_type,
                "entity_id": record.entity_id,
                "status": status,
                "alignment_status": status,
                "runtime_name_cn": record.runtime_name_cn,
                "cn_wiki_name": record.cn_wiki_name,
                "cn_wiki_page": record.cn_wiki_page,
                "runtime_desc_runtime": record.runtime_desc_runtime,
                "runtime_name_issue": runtime_name_issue,
                "description_status": desc_status,
                "reference_source": reference_source,
                "huiji_page_or_title": huiji_page_or_title,
                "approved_alias_note": record.approved_alias_note,
                "note": note,
            }
        )

    return {
        "summary": {
            "total": len(findings),
            "by_status": dict(status_counts),
            "runtime_name_issue": dict(runtime_name_issue_counts),
            "description_status": dict(description_counts),
        },
        "findings": findings,
    }


def _snapshot_inventory(snapshot: dict[str, Any] | None, key: str) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    if not snapshot:
        return result
    payload = snapshot.get(key) or {}
    for entity_type, values in payload.items():
        result[str(entity_type)] = {str(value) for value in values}
    return result


def _records_inventory(normalized_records: list[NormalizedEntitySnapshot]) -> dict[str, set[str]]:
    inventory: dict[str, set[str]] = {}
    for record in normalized_records:
        inventory.setdefault(record.entity_type, set()).add(record.entity_id)
    return inventory


def _catalog_only_without_source_mapping(snapshot: dict[str, Any] | None = None, *, repo_root: Path | None = None) -> list[dict[str, Any]]:
    source_inventory = _snapshot_inventory(snapshot, "source_inventory")
    if not source_inventory:
        source_inventory = {entity_type: set(values) for entity_type, values in _source_inventory_from_repo(repo_root or REPO_ROOT).items()}

    catalog_overrides = dict(snapshot.get("catalog_overrides") or {}) if snapshot else {}
    if not catalog_overrides:
        catalog_overrides = _catalog_override_keys()

    findings: list[dict[str, Any]] = []
    for entity_type, override_keys in sorted(catalog_overrides.items()):
        source_ids = source_inventory.get(entity_type, set())
        for entity_id in sorted(str(item) for item in override_keys):
            if entity_id not in source_ids:
                findings.append(
                    {
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "reason": "catalog_override_without_source_mapping",
                    }
                )
    return findings


def _compute_card_missing_in_runtime(
    repo_root: Path,
    *,
    source_inventory: set[str] | None = None,
    runtime_inventory: set[str] | None = None,
) -> list[dict[str, Any]]:
    expected_cards = source_inventory or _decompiled_card_runtime_inventory(repo_root)
    runtime_cards = runtime_inventory or set(ALL_CARD_DEFS.keys())
    return [
        {
            "entity_type": "card",
            "entity_id": card_id,
            "reason": "decompiled_card_missing_in_runtime",
        }
        for card_id in sorted(expected_cards - runtime_cards)
    ]


def build_completeness_audit(records: Any, *, repo_root: Path | None = None) -> dict[str, Any]:
    snapshot = records if isinstance(records, dict) and "records" in records else None
    normalized_records = _coerce_normalized_records(records)
    runtime_inventory = _snapshot_inventory(snapshot, "runtime_inventory") or _records_inventory(normalized_records)
    source_inventory = _snapshot_inventory(snapshot, "source_inventory")
    if not source_inventory:
        source_inventory = {entity_type: set(values) for entity_type, values in _source_inventory_from_repo(repo_root or REPO_ROOT).items()}

    missing_in_runtime: list[dict[str, Any]] = []
    missing_in_runtime.extend(
        _compute_card_missing_in_runtime(
            repo_root or REPO_ROOT,
            source_inventory=source_inventory.get("card"),
            runtime_inventory=runtime_inventory.get("card"),
        )
    )

    for entity_type, source_ids in sorted(source_inventory.items()):
        if entity_type == "card":
            continue
        for entity_id in sorted(source_ids - runtime_inventory.get(entity_type, set())):
            missing_in_runtime.append(
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "reason": "source_entity_missing_in_runtime_surface",
                }
            )

    present_but_not_cataloged: list[dict[str, Any]] = []
    for record in normalized_records:
        if (
            record.entity_type == "card"
            and bool(str(record.runtime_facts.get("official_name_zhs", "") or "").strip())
            and _normalize_lookup_key(record.runtime_name_cn)
            == _normalize_lookup_key(str(record.runtime_facts.get("official_name_zhs", "") or "").strip())
        ):
            continue
        if not _looks_cataloged_cn(record.runtime_name_cn):
            present_but_not_cataloged.append(
                {
                    "entity_type": record.entity_type,
                    "entity_id": record.entity_id,
                    "runtime_name_cn": record.runtime_name_cn,
                    "reason": "runtime_surface_missing_or_corrupt_cn_catalog",
                }
            )

    catalog_only_without_source_mapping = _catalog_only_without_source_mapping(snapshot, repo_root=repo_root or REPO_ROOT)

    return {
        "summary": {
            "missing_in_runtime": len(missing_in_runtime),
            "present_but_not_cataloged": len(present_but_not_cataloged),
            "catalog_only_without_source_mapping": len(catalog_only_without_source_mapping),
        },
        "missing_in_runtime": missing_in_runtime,
        "present_but_not_cataloged": present_but_not_cataloged,
        "catalog_only_without_source_mapping": catalog_only_without_source_mapping,
    }


def _flatten_event_effect_signatures(runtime_facts: dict[str, Any]) -> list[dict[str, Any]]:
    signatures: list[dict[str, Any]] = []
    for choice in runtime_facts.get("choices") or []:
        signatures.append(
            {
                "index": int(choice.get("index", 0)),
                "gating": sorted(str(item) for item in choice.get("gating") or []),
                "effect_kinds": sorted(str(item) for item in choice.get("effect_kinds") or []),
            }
        )
    signatures.sort(key=lambda item: item["index"])
    return signatures


def _normalize_mechanics_value(entity_type: str, field_name: str, value: Any) -> Any:
    if field_name == "choices":
        return _flatten_event_effect_signatures({"choices": value or []})
    if field_name == "effects":
        normalized = []
        for effect in value or []:
            normalized.append(
                {
                    "type": str(effect.get("type", "")),
                    "value": int(effect.get("value", 0)),
                    "target": str(effect.get("target", "")),
                    "extra_type": str(effect.get("extra_type", "")),
                }
            )
        normalized.sort(key=lambda item: (item["type"], item["value"], item["target"], item["extra_type"]))
        return normalized
    if isinstance(value, list):
        return sorted(value)
    return value


def build_mechanics_audit(records: Any) -> dict[str, Any]:
    raw_records = _coerce_raw_records(records)
    runtime_source_mismatches: list[dict[str, Any]] = []
    wiki_conflicts: list[dict[str, Any]] = []

    for record in raw_records:
        fields = MECHANICS_FIELDS_BY_ENTITY.get(record.entity_type, [])
        en_wiki_facts = dict(record.en_wiki.payload.get("facts") or {})
        cn_wiki_facts = dict(record.cn_wiki.payload.get("facts") or {})
        for field_name in fields:
            source_has_field = field_name in record.java_facts
            runtime_has_field = field_name in record.runtime_facts
            if source_has_field and runtime_has_field:
                source_value = _normalize_mechanics_value(record.entity_type, field_name, record.java_facts.get(field_name))
                runtime_value = _normalize_mechanics_value(record.entity_type, field_name, record.runtime_facts.get(field_name))
                if source_value != runtime_value:
                    runtime_source_mismatches.append(
                        {
                            "entity_type": record.entity_type,
                            "entity_id": record.entity_id,
                            "field": field_name,
                            "source_value": source_value,
                            "runtime_value": runtime_value,
                        }
                    )

            if source_has_field and field_name in en_wiki_facts:
                source_value = _normalize_mechanics_value(record.entity_type, field_name, record.java_facts.get(field_name))
                en_wiki_value = _normalize_mechanics_value(record.entity_type, field_name, en_wiki_facts.get(field_name))
                if source_value != en_wiki_value:
                    wiki_conflicts.append(
                        {
                            "entity_type": record.entity_type,
                            "entity_id": record.entity_id,
                            "field": field_name,
                            "wiki_source": "en_wiki",
                            "source_value": source_value,
                            "wiki_value": en_wiki_value,
                        }
                    )

            if source_has_field and field_name in cn_wiki_facts:
                source_value = _normalize_mechanics_value(record.entity_type, field_name, record.java_facts.get(field_name))
                cn_wiki_value = _normalize_mechanics_value(record.entity_type, field_name, cn_wiki_facts.get(field_name))
                if source_value != cn_wiki_value:
                    wiki_conflicts.append(
                        {
                            "entity_type": record.entity_type,
                            "entity_id": record.entity_id,
                            "field": field_name,
                            "wiki_source": "cn_wiki",
                            "source_value": source_value,
                            "wiki_value": cn_wiki_value,
                        }
                    )

    return {
        "summary": {
            "runtime_source_mismatches": len(runtime_source_mismatches),
            "wiki_conflicts": len(wiki_conflicts),
        },
        "runtime_source_mismatches": runtime_source_mismatches,
        "wiki_conflicts": wiki_conflicts,
    }


def build_fix_queue(
    records: Any,
    translation_audit: dict[str, Any],
    completeness_audit: dict[str, Any],
    mechanics_audit: dict[str, Any],
) -> dict[str, Any]:
    normalized_records = _coerce_normalized_records(records)
    record_map = {(record.entity_type, record.entity_id): record for record in normalized_records}
    items: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    def add_item(priority: int, category: str, entity_type: str, entity_id: str, reason: str, note: str, **extra: Any) -> None:
        key = (priority, category, entity_type, entity_id, reason)
        if key in seen:
            return
        seen.add(key)
        items.append(
            {
                "priority": priority,
                "category": category,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "reason": reason,
                "note": note,
                **extra,
            }
        )

    for finding in translation_audit.get("findings", []):
        status = finding.get("status")
        entity_type = str(finding.get("entity_type"))
        entity_id = str(finding.get("entity_id"))
        record = record_map.get((entity_type, entity_id))
        if status == "mojibake_or_corrupt":
            add_item(1, "translation", entity_type, entity_id, status, "CLI 直接显示乱码或损坏中文名", runtime_name_cn=finding.get("runtime_name_cn"))
        elif status == "likely_wrong_translation":
            add_item(1, "translation", entity_type, entity_id, status, "CLI 中文名与 Huiji 常用名冲突", runtime_name_cn=finding.get("runtime_name_cn"), cn_wiki_name=finding.get("cn_wiki_name"))
        elif status == "missing_cn":
            add_item(3, "translation", entity_type, entity_id, status, "CLI 可见实体缺少可用中文名", runtime_name_en=record.runtime_name_en if record else None)
        if finding.get("description_status") == "mojibake_runtime_desc":
            add_item(1, "translation", entity_type, entity_id, "description_mojibake", "CLI 直接显示损坏的中文说明", runtime_desc_runtime=finding.get("runtime_desc_runtime"))

    for finding in completeness_audit.get("missing_in_runtime", []):
        add_item(
            2,
            "completeness",
            str(finding.get("entity_type")),
            str(finding.get("entity_id")),
            str(finding.get("reason")),
            "源码存在但 runtime/CLI 面缺失",
        )

    for finding in completeness_audit.get("present_but_not_cataloged", []):
        add_item(
            3,
            "completeness",
            str(finding.get("entity_type")),
            str(finding.get("entity_id")),
            str(finding.get("reason")),
            "实体已可见但缺少稳定可用的中文 catalog 表面",
            runtime_name_cn=finding.get("runtime_name_cn"),
        )

    for finding in mechanics_audit.get("runtime_source_mismatches", []):
        field_name = str(finding.get("field"))
        priority = 2 if field_name in {"target_required", "cost", "type", "rarity", "choices", "choice_count", "effects", "potency"} else 4
        add_item(
            priority,
            "mechanics",
            str(finding.get("entity_type")),
            str(finding.get("entity_id")),
            f"runtime_source_mismatch:{field_name}",
            "runtime 机制事实与源码抽取不一致",
            field=field_name,
            source_value=finding.get("source_value"),
            runtime_value=finding.get("runtime_value"),
        )

    items.sort(key=lambda item: (item["priority"], item["category"], item["entity_type"], item["entity_id"], item["reason"]))
    priority_counts = Counter(str(item["priority"]) for item in items)
    return {
        "summary": {
            "total": len(items),
            "by_priority": dict(priority_counts),
        },
        "items": items,
    }


def build_fix_queue(
    records: Any,
    translation_audit: dict[str, Any],
    completeness_audit: dict[str, Any],
    mechanics_audit: dict[str, Any],
) -> dict[str, Any]:
    normalized_records = _coerce_normalized_records(records)
    record_map = {(record.entity_type, record.entity_id): record for record in normalized_records}
    items: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    def add_item(priority: int, category: str, entity_type: str, entity_id: str, reason: str, note: str, **extra: Any) -> None:
        key = (priority, category, entity_type, entity_id, reason)
        if key in seen:
            return
        seen.add(key)
        items.append(
            {
                "priority": priority,
                "category": category,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "reason": reason,
                "note": note,
                **extra,
            }
        )

    for finding in translation_audit.get("findings", []):
        status = str(finding.get("status"))
        runtime_name_issue = str(finding.get("runtime_name_issue"))
        entity_type = str(finding.get("entity_type"))
        entity_id = str(finding.get("entity_id"))
        record = record_map.get((entity_type, entity_id))

        if runtime_name_issue == "mojibake_or_corrupt":
            add_item(
                1,
                "translation",
                entity_type,
                entity_id,
                "runtime_name_mojibake",
                "CLI 直接显示乱码或损坏的中文名。",
                runtime_name_cn=finding.get("runtime_name_cn"),
                reference_source=finding.get("reference_source"),
            )
        elif runtime_name_issue == "missing_cn":
            add_item(
                3 if status == "wiki_missing" else 2,
                "translation",
                entity_type,
                entity_id,
                "runtime_name_missing_cn",
                "CLI 可见实体缺少稳定可用的中文名。",
                runtime_name_en=record.runtime_name_en if record else None,
                reference_source=finding.get("reference_source"),
            )

        if status == "likely_wrong_translation":
            add_item(
                1,
                "translation",
                entity_type,
                entity_id,
                status,
                "当前中文名与 Huiji 参考明显冲突，应优先校正。",
                runtime_name_cn=finding.get("runtime_name_cn"),
                cn_wiki_name=finding.get("cn_wiki_name"),
                huiji_page_or_title=finding.get("huiji_page_or_title"),
            )
        elif status == "needs_review":
            add_item(
                2,
                "translation",
                entity_type,
                entity_id,
                status,
                "当前中文名接近 Huiji，但未被策略表显式批准为别名。",
                runtime_name_cn=finding.get("runtime_name_cn"),
                cn_wiki_name=finding.get("cn_wiki_name"),
                huiji_page_or_title=finding.get("huiji_page_or_title"),
            )
        elif status == "wiki_missing":
            add_item(
                3,
                "translation",
                entity_type,
                entity_id,
                status,
                "Huiji 缺页，当前中文名只能依赖本地策略或英文 fallback。",
                runtime_name_cn=finding.get("runtime_name_cn"),
                reference_source=finding.get("reference_source"),
            )

        if finding.get("description_status") == "mojibake_runtime_desc":
            add_item(
                1,
                "translation",
                entity_type,
                entity_id,
                "description_mojibake",
                "CLI 直接显示了损坏的中文说明。",
                runtime_desc_runtime=finding.get("runtime_desc_runtime"),
            )

    for finding in completeness_audit.get("missing_in_runtime", []):
        add_item(
            2,
            "completeness",
            str(finding.get("entity_type")),
            str(finding.get("entity_id")),
            str(finding.get("reason")),
            "源码中存在该实体，但 runtime/CLI 表面尚未覆盖。",
        )

    for finding in completeness_audit.get("present_but_not_cataloged", []):
        add_item(
            3,
            "completeness",
            str(finding.get("entity_type")),
            str(finding.get("entity_id")),
            str(finding.get("reason")),
            "实体已可见，但缺少稳定可用的中文 catalog 覆盖。",
            runtime_name_cn=finding.get("runtime_name_cn"),
        )

    for finding in mechanics_audit.get("runtime_source_mismatches", []):
        field_name = str(finding.get("field"))
        priority = 2 if field_name in {"target_required", "cost", "type", "rarity", "choices", "choice_count", "effects", "potency"} else 4
        add_item(
            priority,
            "mechanics",
            str(finding.get("entity_type")),
            str(finding.get("entity_id")),
            f"runtime_source_mismatch:{field_name}",
            "runtime 结构化机制事实与源码抽取不一致。",
            field=field_name,
            source_value=finding.get("source_value"),
            runtime_value=finding.get("runtime_value"),
        )

    items.sort(key=lambda item: (item["priority"], item["category"], item["entity_type"], item["entity_id"], item["reason"]))
    priority_counts = Counter(str(item["priority"]) for item in items)
    return {
        "summary": {
            "total": len(items),
            "by_priority": dict(priority_counts),
        },
        "items": items,
    }


def load_raw_snapshot(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path: str | Path, payload: Any) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def run_audit_from_raw_snapshot(raw_snapshot: dict[str, Any], *, repo_root: Path | None = None) -> dict[str, Any]:
    normalized_snapshot = normalize_raw_snapshot(raw_snapshot)
    translation_audit = build_translation_audit(normalized_snapshot)
    completeness_audit = build_completeness_audit(raw_snapshot, repo_root=repo_root)
    mechanics_audit = build_mechanics_audit(raw_snapshot)
    fix_queue = build_fix_queue(normalized_snapshot, translation_audit, completeness_audit, mechanics_audit)
    return {
        "normalized_snapshot": normalized_snapshot,
        "translation_audit": translation_audit,
        "completeness_audit": completeness_audit,
        "mechanics_audit": mechanics_audit,
        "fix_queue": fix_queue,
    }


def write_audit_outputs(output_dir: str | Path, raw_snapshot: dict[str, Any], audit_bundle: dict[str, Any]) -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    targets = {
        RAW_SNAPSHOT_FILENAME: raw_snapshot,
        NORMALIZED_SNAPSHOT_FILENAME: audit_bundle["normalized_snapshot"],
        TRANSLATION_AUDIT_FILENAME: audit_bundle["translation_audit"],
        COMPLETENESS_AUDIT_FILENAME: audit_bundle["completeness_audit"],
        MECHANICS_AUDIT_FILENAME: audit_bundle["mechanics_audit"],
        FIX_QUEUE_FILENAME: audit_bundle["fix_queue"],
    }
    written: dict[str, str] = {}
    for filename, payload in targets.items():
        path = output_path / filename
        save_json(path, payload)
        written[filename] = str(path)
    return written


def _default_output_dir(repo_root: Path) -> Path:
    return repo_root / "wiki_audit_output"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline wiki/source audit pipeline for CLI-visible STS entities.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    refresh_parser = subparsers.add_parser("refresh", help="Refresh a checked-in raw snapshot by hitting configured wiki sources.")
    refresh_parser.add_argument("--repo-root", default=str(REPO_ROOT))
    refresh_parser.add_argument("--output-dir", default=None)
    refresh_parser.add_argument("--offline", action="store_true", help="Build a raw snapshot without network fetches.")
    refresh_parser.add_argument("--entity-types", nargs="*", choices=ENTITY_TYPES, default=None)

    audit_parser = subparsers.add_parser("audit", help="Generate normalized snapshot and audit reports from an existing raw snapshot.")
    audit_parser.add_argument("--repo-root", default=str(REPO_ROOT))
    audit_parser.add_argument("--raw-snapshot", required=True)
    audit_parser.add_argument("--output-dir", default=None)
    audit_parser.add_argument("--entity-types", nargs="*", choices=ENTITY_TYPES, default=None)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else _default_output_dir(repo_root)

    if args.command == "refresh":
        raw_snapshot = build_cli_raw_snapshot(
            repo_root,
            enable_network=not args.offline,
            entity_types=args.entity_types,
        )
    elif args.command == "audit":
        raw_snapshot = load_raw_snapshot(args.raw_snapshot)
        raw_snapshot = filter_raw_snapshot_entity_types(raw_snapshot, args.entity_types)
    else:
        raise ValueError(f"unsupported command: {args.command}")

    audit_bundle = run_audit_from_raw_snapshot(raw_snapshot, repo_root=repo_root)
    written = write_audit_outputs(output_dir, raw_snapshot, audit_bundle)
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "files": written,
                "translation_findings": audit_bundle["translation_audit"]["summary"],
                "completeness_findings": audit_bundle["completeness_audit"]["summary"],
                "mechanics_findings": audit_bundle["mechanics_audit"]["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
