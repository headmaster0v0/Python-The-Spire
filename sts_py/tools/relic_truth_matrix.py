from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote

from sts_py.engine.content.relics import ALL_RELICS, RelicDef
from sts_py.terminal.translation_policy import get_translation_policy_entry
from sts_py.tools.fidelity_proof import DEDICATED_PROOF_TESTS, build_relic_effect_signatures
from sts_py.tools.wiki_audit import build_relic_source_facts
from sts_py.tools.wiki_bilingual_scraper import BilingualWikiScraper


RELIC_TRUTH_MATRIX_PATH = Path(__file__).resolve().parents[1] / "data" / "relic_truth_matrix.json"

DATA_TRUTH_KINDS = (
    "manifest_overlay",
    "pickup_rng",
    "spawn_rule_static",
    "stateful_text_ui",
)
RUNTIME_TRUTH_KINDS = (
    "combat_runtime",
    "run_runtime",
    "none",
)

RUN_RUNTIME_SIGNATURES = {
    "relic:avoid_enemies",
    "relic:cant_heal",
    "relic:card_choice_three",
    "relic:card_reward",
    "relic:card_reward_max_hp",
    "relic:card_reward_modifier",
    "relic:card_reward_reduce",
    "relic:change_rare_chance",
    "relic:change_uncommon_chance",
    "relic:chest_relics",
    "relic:elite_hp_modifier",
    "relic:elite_reward_relics",
    "relic:extra_card_reward",
    "relic:free_movement",
    "relic:gain_max_HP",
    "relic:on_chest_open",
    "relic:on_combat_end",
    "relic:on_death_save",
    "relic:on_floor_climb",
    "relic:on_pickup",
    "relic:on_question_room",
    "relic:on_rest",
    "relic:on_rest_add_card",
    "relic:on_shop_enter",
    "relic:on_trap_combat",
    "relic:replace_starter_relic",
    "relic:rest_heal_bonus",
    "relic:rest_heal_disabled",
    "relic:rest_site_dig",
    "relic:rest_site_forge_disabled",
    "relic:rest_site_remove",
    "relic:rest_site_strength",
    "relic:rest_site_transform",
    "relic:rest_site_upgrade",
    "relic:shop_no_sell_out",
    "relic:shop_price_modifier",
    "relic:treasure_room_every_n_question",
    "relic:upgrade_random",
}

PICKUP_RNG_RELIC_IDS = {
    "Astrolabe",
    "Cauldron",
    "CallingBell",
    "DollysMirror",
    "Matryoshka",
    "MummifiedHand",
    "Orrery",
    "PandoraBox",
    "TinyHouse",
    "WarPaint",
    "Whetstone",
}

HIGH_RISK_RUNTIME_RELIC_IDS = {
    "Astrolabe",
    "BlackStar",
    "BustedCrown",
    "CallingBell",
    "Cauldron",
    "CursedKey",
    "DollysMirror",
    "LizardTail",
    "MagicFlower",
    "Matryoshka",
    "MummifiedHand",
    "Orrery",
    "PandoraBox",
    "PaperCrane",
    "PaperFrog",
    "PrayerWheel",
    "QuestionCard",
    "SacredBark",
    "SmilingMask",
    "SneckoSkull",
    "Sozu",
    "TheCourier",
    "TheSpecimen",
    "TinyHouse",
    "WarPaint",
    "Whetstone",
}

SCENARIO_NODEIDS = {
    "data_manifest_overlay_truth": (
        "tests/test_relic_truth_matrix.py::"
        "test_relic_truth_matrix_data_truth_rows_match_runtime_source_facts"
    ),
    "data_wiki_policy_truth": (
        "tests/test_relic_truth_matrix.py::"
        "test_relic_truth_matrix_wiki_status_and_resolution_notes_follow_translation_policy"
    ),
    "combat_runtime_battle_turn_resource": (
        "tests/test_phase269_relic_potion_power_truth.py::"
        "test_phase269_relic_family_battle_turn_and_resource_truth"
    ),
    "combat_runtime_cardplay_deck_status": (
        "tests/test_phase269_relic_potion_power_truth.py::"
        "test_phase269_relic_family_cardplay_deck_and_status_truth"
    ),
    "run_runtime_reward_shop_rest_pickup": (
        "tests/test_phase269_relic_potion_power_truth.py::"
        "test_phase269_relic_family_reward_shop_rest_and_pickup_truth"
    ),
    "pickup_rng_fixed_seed_truth": (
        "tests/test_relic_truth_matrix.py::"
        "test_relic_truth_matrix_rng_relics_match_fixed_seed_truth"
    ),
    "spawn_rule_manifest_filters": (
        "tests/test_relic_truth_matrix.py::"
        "test_relic_truth_matrix_spawn_rule_static_rows_match_manifest_filters"
    ),
    "stateful_text_ui_manifest_truth": (
        "tests/test_relic_truth_matrix.py::"
        "test_relic_truth_matrix_stateful_text_and_ui_rows_match_manifest_truth"
    ),
    "question_card_busted_crown_prayer_wheel_stack": (
        "tests/test_relic_truth_matrix.py::"
        "test_relic_truth_matrix_question_card_busted_crown_and_prayer_wheel_stack"
    ),
    "black_star_elite_double_relic": (
        "tests/test_relic_truth_matrix.py::"
        "test_relic_truth_matrix_black_star_grants_double_elite_relic_reward"
    ),
    "cursed_key_matryoshka_sapphire_key": (
        "tests/test_relic_truth_matrix.py::"
        "test_relic_truth_matrix_cursed_key_and_matryoshka_preserve_bonus_relics_when_taking_sapphire_key"
    ),
    "sozu_blocks_potion_gain": (
        "tests/test_relic_truth_matrix.py::"
        "test_relic_truth_matrix_sozu_blocks_potion_gain_from_relic_rewards"
    ),
    "cross_relic_callbacks_truth": (
        "tests/test_relic_truth_matrix.py::"
        "test_relic_truth_matrix_cross_relic_callbacks_and_modifiers_remain_live"
    ),
    "calling_bell_pickup_truth": (
        "tests/test_run_layer_relic_fidelity.py::"
        "test_calling_bell_adds_curse_and_three_extra_relics"
    ),
    "pandora_box_pickup_truth": (
        "tests/test_run_layer_relic_fidelity.py::"
        "test_pandora_box_transforms_all_strikes_and_defends"
    ),
    "tiny_house_pickup_truth": (
        "tests/test_run_layer_relic_fidelity.py::"
        "test_tiny_house_applies_full_pickup_bundle"
    ),
    "empty_cage_pickup_truth": (
        "tests/test_run_layer_relic_fidelity.py::"
        "test_empty_cage_removes_first_two_removable_cards"
    ),
}

SPECIAL_RUNTIME_SCENARIOS_BY_RELIC = {
    "Astrolabe": ["pickup_rng_fixed_seed_truth"],
    "BlackStar": ["black_star_elite_double_relic"],
    "BustedCrown": ["question_card_busted_crown_prayer_wheel_stack"],
    "CallingBell": ["calling_bell_pickup_truth"],
    "CursedKey": ["cursed_key_matryoshka_sapphire_key"],
    "LizardTail": ["cross_relic_callbacks_truth"],
    "MagicFlower": ["cross_relic_callbacks_truth"],
    "Matryoshka": ["cursed_key_matryoshka_sapphire_key", "pickup_rng_fixed_seed_truth"],
    "MummifiedHand": ["pickup_rng_fixed_seed_truth"],
    "PandoraBox": ["pandora_box_pickup_truth"],
    "PaperCrane": ["cross_relic_callbacks_truth"],
    "PaperFrog": ["cross_relic_callbacks_truth"],
    "PrayerWheel": ["question_card_busted_crown_prayer_wheel_stack"],
    "QuestionCard": ["question_card_busted_crown_prayer_wheel_stack"],
    "SacredBark": ["cross_relic_callbacks_truth"],
    "SneckoSkull": ["cross_relic_callbacks_truth"],
    "Sozu": ["sozu_blocks_potion_gain"],
    "TheSpecimen": ["cross_relic_callbacks_truth"],
    "TinyHouse": ["tiny_house_pickup_truth", "pickup_rng_fixed_seed_truth"],
    "WarPaint": ["pickup_rng_fixed_seed_truth"],
    "Whetstone": ["pickup_rng_fixed_seed_truth"],
}

DATA_SCENARIOS_BY_KIND = {
    "manifest_overlay": ["data_manifest_overlay_truth", "data_wiki_policy_truth"],
    "pickup_rng": ["data_manifest_overlay_truth", "data_wiki_policy_truth", "pickup_rng_fixed_seed_truth"],
    "spawn_rule_static": ["data_manifest_overlay_truth", "data_wiki_policy_truth", "spawn_rule_manifest_filters"],
    "stateful_text_ui": ["data_manifest_overlay_truth", "data_wiki_policy_truth", "stateful_text_ui_manifest_truth"],
}


def _wiki_page_url(base_url: str, page_title: str) -> str:
    return f"{base_url}/{quote(page_title.replace(' ', '_'))}"


def _json_ready(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _resolution_notes(relic_id: str) -> str:
    policy = get_translation_policy_entry("relic", relic_id)
    if policy is None:
        return ""
    if policy.alignment_status == "approved_alias":
        note = policy.approved_alias_note.strip()
        if note:
            return note
        if policy.huiji_page_or_title.strip() and policy.huiji_page_or_title.strip() != policy.runtime_name_cn.strip():
            return f"Approved Huiji alias: {policy.runtime_name_cn} -> {policy.huiji_page_or_title}"
    if policy.alignment_status == "wiki_missing":
        return "Huiji reference page missing; local official translation retained."
    return ""


def _data_truth_kind(relic_def: RelicDef) -> str:
    if bool(getattr(relic_def, "rng_notes", ()) or relic_def.id in PICKUP_RNG_RELIC_IDS):
        return "pickup_rng"
    if bool(getattr(relic_def, "stateful_description_variants", ()) or getattr(relic_def, "ui_prompt_slots", ())):
        return "stateful_text_ui"
    if bool(getattr(relic_def, "spawn_rules", {}) or {}):
        return "spawn_rule_static"
    return "manifest_overlay"


def _runtime_truth_kind(relic_def: RelicDef) -> str:
    effect_signatures = set(build_relic_effect_signatures(relic_def))
    if not effect_signatures:
        return "none"
    if effect_signatures & RUN_RUNTIME_SIGNATURES:
        return "run_runtime"
    return "combat_runtime"


def _runtime_family_scenario_key(relic_def: RelicDef, runtime_truth_kind: str) -> str:
    if runtime_truth_kind == "run_runtime":
        return "run_runtime_reward_shop_rest_pickup"
    if runtime_truth_kind == "combat_runtime":
        effect_signatures = set(build_relic_effect_signatures(relic_def))
        cardplay_like = {
            "relic:bottled",
            "relic:card_copy",
            "relic:chance_for_free_attack",
            "relic:chance_for_free_skill",
            "relic:curse_negate_trigger",
            "relic:curse_playable",
            "relic:deck_transform",
            "relic:deck_transform_and_upgrade",
            "relic:empty_hand_draw",
            "relic:every_n_attacks",
            "relic:every_n_attacks_self",
            "relic:every_n_cards",
            "relic:every_n_skills",
            "relic:first_attack_combat",
            "relic:first_attack_twice",
            "relic:gain_intangible",
            "relic:immune_frail",
            "relic:immune_weak",
            "relic:limit_cards_draw",
            "relic:miracle",
            "relic:modify_damage",
            "relic:modify_min_damage",
            "relic:modify_strength",
            "relic:modify_strike",
            "relic:modify_vulnerable",
            "relic:modify_weak",
            "relic:on_attack",
            "relic:on_card_added",
            "relic:on_card_played",
            "relic:on_curse_received",
            "relic:on_damage",
            "relic:on_discard",
            "relic:on_enemy_death",
            "relic:on_enemy_death_poison_transfer",
            "relic:on_exhaust_add_random",
            "relic:on_exhaust_damage_all",
            "relic:on_exit_calm",
            "relic:on_exit_calm_energy",
            "relic:on_first_discard_per_turn",
            "relic:on_poison_applied",
            "relic:on_power_played",
            "relic:on_shuffle",
            "relic:on_vulnerable_apply",
            "relic:orb_passive_multiply",
            "relic:remove_cards_from_deck",
            "relic:scry_bonus",
            "relic:scry_on_shuffle",
            "relic:start_with_strength_per_curse",
            "relic:strike_damage_bonus",
            "relic:zero_cost_attack_bonus_damage",
        }
        if effect_signatures & cardplay_like:
            return "combat_runtime_cardplay_deck_status"
        return "combat_runtime_battle_turn_resource"
    raise ValueError(f"unsupported runtime truth kind: {runtime_truth_kind}")


def _runtime_proof_nodeids(relic_def: RelicDef, runtime_truth_kind: str) -> list[str]:
    if runtime_truth_kind == "none":
        return []
    entity_key = f"relic:{relic_def.id}"
    scenarios: list[str] = []
    dedicated = DEDICATED_PROOF_TESTS.get(entity_key)
    if relic_def.id in HIGH_RISK_RUNTIME_RELIC_IDS and dedicated:
        scenarios.append(dedicated)
    else:
        scenarios.append(SCENARIO_NODEIDS[_runtime_family_scenario_key(relic_def, runtime_truth_kind)])
    scenarios.extend(SCENARIO_NODEIDS[key] for key in SPECIAL_RUNTIME_SCENARIOS_BY_RELIC.get(relic_def.id, []))
    return _unique_preserve_order(scenarios)


def _data_proof_nodeids(data_truth_kind: str) -> list[str]:
    return [SCENARIO_NODEIDS[key] for key in DATA_SCENARIOS_BY_KIND[data_truth_kind]]


def _wiki_status_and_conflicts(relic_id: str) -> tuple[str, list[str]]:
    policy = get_translation_policy_entry("relic", relic_id)
    if policy is None:
        return "untracked", ["policy_missing"]
    if policy.alignment_status == "wiki_missing":
        return policy.alignment_status, ["page_missing"]
    if policy.alignment_status == "approved_alias":
        return policy.alignment_status, ["approved_alias"]
    if policy.alignment_status == "exact_match":
        return policy.alignment_status, []
    return policy.alignment_status, ["translation_needs_review"]


def _relic_wiki_titles(relic_def: RelicDef) -> tuple[str, str]:
    official_en = str(getattr(relic_def, "name_en", "") or relic_def.id)
    policy = get_translation_policy_entry("relic", relic_def.id)
    if policy is not None and policy.huiji_page_or_title.strip():
        return official_en, policy.huiji_page_or_title.strip()
    official_zhs = str(getattr(relic_def, "name_zhs", "") or getattr(relic_def, "name", "") or relic_def.id)
    return official_en, official_zhs


def build_relic_truth_matrix(repo_root: Path | str | None = None) -> dict[str, Any]:
    _ = Path(repo_root) if repo_root is not None else None

    entities: list[dict[str, Any]] = []
    data_truth_counts: Counter[str] = Counter()
    runtime_truth_counts: Counter[str] = Counter()
    wiki_status_counts: Counter[str] = Counter()

    for relic_id, relic_def in sorted(ALL_RELICS.items()):
        source_facts = build_relic_source_facts(relic_def)
        data_truth_kind = _data_truth_kind(relic_def)
        runtime_truth_kind = _runtime_truth_kind(relic_def)
        wiki_en_title, wiki_cn_title = _relic_wiki_titles(relic_def)
        wiki_status, wiki_conflict_fields = _wiki_status_and_conflicts(relic_id)

        row = {
            "runtime_id": relic_id,
            "official_id": str(source_facts.get("official_id", "") or relic_id),
            "class_name": str(source_facts.get("class_name", "") or ""),
            "tier": str(source_facts.get("tier", "") or ""),
            "character_class": str(source_facts.get("character_class", "") or ""),
            "official_name_en": str(source_facts.get("display_name_en", "") or ""),
            "official_name_zhs": str(getattr(relic_def, "name_zhs", "") or getattr(relic_def, "name", "") or ""),
            "official_desc_en": str(source_facts.get("default_description_en", "") or ""),
            "official_desc_zhs": str(source_facts.get("default_description_zhs", "") or ""),
            "wiki_en_url": _wiki_page_url(BilingualWikiScraper.EN_WIKIGG_WIKI_URL, wiki_en_title),
            "wiki_cn_url": _wiki_page_url(BilingualWikiScraper.CN_WIKI_URL, wiki_cn_title),
            "wiki_en_title": wiki_en_title,
            "wiki_cn_title": wiki_cn_title,
            "wiki_status": wiki_status,
            "wiki_conflict_fields": wiki_conflict_fields,
            "data_truth_kind": data_truth_kind,
            "runtime_truth_kind": runtime_truth_kind,
            "data_proof_nodeids": _data_proof_nodeids(data_truth_kind),
            "runtime_proof_nodeids": _runtime_proof_nodeids(relic_def, runtime_truth_kind),
            "spawn_rules": _json_ready(dict(source_facts.get("spawn_rules") or {})),
            "rng_streams": list(source_facts.get("rng_notes") or []),
            "effect_signatures": list(source_facts.get("effect_signatures") or []),
            "stateful_description_variants": _json_ready(list(source_facts.get("stateful_description_variants") or [])),
            "ui_prompt_slots": list(source_facts.get("ui_prompt_slots") or []),
            "truth_sources": _json_ready(dict(source_facts.get("truth_sources") or {})),
            "resolution_notes": _resolution_notes(relic_id),
        }
        entities.append(row)
        data_truth_counts[data_truth_kind] += 1
        runtime_truth_counts[runtime_truth_kind] += 1
        wiki_status_counts[wiki_status] += 1

    return {
        "schema_version": 2,
        "summary": {
            "relic_count": len(entities),
            "data_truth_kind_counts": dict(sorted(data_truth_counts.items())),
            "runtime_truth_kind_counts": dict(sorted(runtime_truth_counts.items())),
            "wiki_status_counts": dict(sorted(wiki_status_counts.items())),
            "stateful_text_relic_count": sum(1 for row in entities if row["stateful_description_variants"]),
            "ui_prompt_relic_count": sum(1 for row in entities if row["ui_prompt_slots"]),
            "spawn_rule_relic_count": sum(1 for row in entities if row["spawn_rules"]),
            "rng_relic_count": sum(1 for row in entities if row["rng_streams"]),
        },
        "scenario_nodeids": dict(sorted(SCENARIO_NODEIDS.items())),
        "entities": entities,
    }


def load_relic_truth_matrix(repo_root: Path | str | None = None) -> dict[str, Any]:
    path = RELIC_TRUTH_MATRIX_PATH
    if repo_root is not None:
        candidate = Path(repo_root) / "sts_py" / "data" / "relic_truth_matrix.json"
        if candidate.exists():
            path = candidate
    if not path.exists():
        return {
            "schema_version": 2,
            "summary": {
                "relic_count": 0,
                "data_truth_kind_counts": {},
                "runtime_truth_kind_counts": {},
                "wiki_status_counts": {},
                "stateful_text_relic_count": 0,
                "ui_prompt_relic_count": 0,
                "spawn_rule_relic_count": 0,
                "rng_relic_count": 0,
            },
            "scenario_nodeids": {},
            "entities": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


__all__ = [
    "DATA_TRUTH_KINDS",
    "HIGH_RISK_RUNTIME_RELIC_IDS",
    "PICKUP_RNG_RELIC_IDS",
    "RELIC_TRUTH_MATRIX_PATH",
    "RUNTIME_TRUTH_KINDS",
    "SCENARIO_NODEIDS",
    "build_relic_truth_matrix",
    "load_relic_truth_matrix",
]
