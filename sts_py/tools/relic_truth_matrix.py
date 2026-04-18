from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote

from sts_py.engine.content.relics import ALL_RELICS, RelicDef
from sts_py.terminal.translation_policy import get_translation_policy_entry
from sts_py.tools.fidelity_proof import (
    DEDICATED_PROOF_TESTS,
    RELIC_BATTLE_START_SIGNATURES,
    RELIC_CARDPLAY_SIGNATURES,
    RELIC_CURSE_SIGNATURES,
    RELIC_DECK_SIGNATURES,
    RELIC_DRAW_DISCARD_SIGNATURES,
    RELIC_MISC_SIGNATURES,
    RELIC_ORB_STANCE_SIGNATURES,
    RELIC_PICKUP_SIGNATURES,
    RELIC_PROGRESS_SIGNATURES,
    RELIC_RESOURCE_SIGNATURES,
    RELIC_REST_SIGNATURES,
    RELIC_REWARD_SIGNATURES,
    RELIC_SHOP_SIGNATURES,
    RELIC_TURN_SIGNATURES,
    build_relic_effect_signatures,
)
from sts_py.tools.wiki_audit import build_relic_source_facts
from sts_py.tools.wiki_bilingual_scraper import BilingualWikiScraper


RELIC_TRUTH_MATRIX_PATH = Path(__file__).resolve().parents[1] / "data" / "relic_truth_matrix.json"
PRIMARY_PROOF_KINDS = (
    "combat_runtime",
    "run_runtime",
    "pickup_rng",
    "spawn_rule_static",
    "stateful_text_ui",
)

COMBAT_CARDPLAY_SIGNATURES = (
    RELIC_CARDPLAY_SIGNATURES
    | RELIC_DRAW_DISCARD_SIGNATURES
    | RELIC_DECK_SIGNATURES
    | RELIC_CURSE_SIGNATURES
    | RELIC_ORB_STANCE_SIGNATURES
)
RUN_RUNTIME_SIGNATURES = (
    RELIC_REWARD_SIGNATURES
    | RELIC_SHOP_SIGNATURES
    | RELIC_REST_SIGNATURES
    | RELIC_PICKUP_SIGNATURES
    | RELIC_PROGRESS_SIGNATURES
    | RELIC_MISC_SIGNATURES
)

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

SCENARIO_NODEIDS = {
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
}

SPECIAL_SCENARIOS_BY_RELIC = {
    "BlackStar": ["black_star_elite_double_relic"],
    "BustedCrown": ["question_card_busted_crown_prayer_wheel_stack"],
    "CursedKey": ["cursed_key_matryoshka_sapphire_key"],
    "LizardTail": ["cross_relic_callbacks_truth"],
    "MagicFlower": ["cross_relic_callbacks_truth"],
    "Matryoshka": ["cursed_key_matryoshka_sapphire_key"],
    "PaperCrane": ["cross_relic_callbacks_truth"],
    "PaperFrog": ["cross_relic_callbacks_truth"],
    "PrayerWheel": ["question_card_busted_crown_prayer_wheel_stack"],
    "QuestionCard": ["question_card_busted_crown_prayer_wheel_stack"],
    "SacredBark": ["cross_relic_callbacks_truth"],
    "SneckoSkull": ["cross_relic_callbacks_truth"],
    "Sozu": ["sozu_blocks_potion_gain"],
    "TheSpecimen": ["cross_relic_callbacks_truth"],
}


def _wiki_page_url(base_url: str, page_title: str) -> str:
    return f"{base_url}/{quote(page_title.replace(' ', '_'))}"


def _json_ready(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


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


def _primary_proof_kind(relic_def: RelicDef) -> str:
    effect_signatures = set(build_relic_effect_signatures(relic_def))
    has_spawn_rules = bool(getattr(relic_def, "spawn_rules", {}) or {})
    has_text_state = bool(getattr(relic_def, "stateful_description_variants", ()) or getattr(relic_def, "ui_prompt_slots", ()))
    has_rng_truth = bool(getattr(relic_def, "rng_notes", ()) or relic_def.id in PICKUP_RNG_RELIC_IDS)

    if has_rng_truth:
        return "pickup_rng"
    if has_text_state:
        return "stateful_text_ui"
    if has_spawn_rules:
        return "spawn_rule_static"
    if effect_signatures & RUN_RUNTIME_SIGNATURES:
        return "run_runtime"
    return "combat_runtime"


def _base_scenario_key(relic_def: RelicDef, primary_proof_kind: str) -> str:
    effect_signatures = set(build_relic_effect_signatures(relic_def))
    if primary_proof_kind == "combat_runtime":
        if effect_signatures & COMBAT_CARDPLAY_SIGNATURES:
            return "combat_runtime_cardplay_deck_status"
        return "combat_runtime_battle_turn_resource"
    if primary_proof_kind == "run_runtime":
        return "run_runtime_reward_shop_rest_pickup"
    if primary_proof_kind == "pickup_rng":
        return "pickup_rng_fixed_seed_truth"
    if primary_proof_kind == "spawn_rule_static":
        return "spawn_rule_manifest_filters"
    if primary_proof_kind == "stateful_text_ui":
        return "stateful_text_ui_manifest_truth"
    raise ValueError(f"unsupported proof kind: {primary_proof_kind}")


def _proof_test_nodeid(relic_def: RelicDef, primary_proof_kind: str, base_scenario_key: str) -> str:
    dedicated = DEDICATED_PROOF_TESTS.get(f"relic:{relic_def.id}")
    if dedicated and primary_proof_kind in {"combat_runtime", "run_runtime"}:
        return dedicated
    return SCENARIO_NODEIDS[base_scenario_key]


def _required_scenarios(relic_def: RelicDef, base_scenario_key: str) -> list[str]:
    scenarios = [base_scenario_key]
    scenarios.extend(SPECIAL_SCENARIOS_BY_RELIC.get(relic_def.id, []))
    deduped: list[str] = []
    for scenario in scenarios:
        if scenario not in deduped:
            deduped.append(scenario)
    return deduped


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
    proof_kind_counts: Counter[str] = Counter()

    for relic_id, relic_def in sorted(ALL_RELICS.items()):
        source_facts = build_relic_source_facts(relic_def)
        primary_proof_kind = _primary_proof_kind(relic_def)
        base_scenario_key = _base_scenario_key(relic_def, primary_proof_kind)
        wiki_en_title, wiki_cn_title = _relic_wiki_titles(relic_def)

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
            "spawn_rules": _json_ready(dict(source_facts.get("spawn_rules") or {})),
            "rng_streams": list(source_facts.get("rng_notes") or []),
            "effect_signatures": list(source_facts.get("effect_signatures") or []),
            "primary_proof_kind": primary_proof_kind,
            "proof_test_nodeid": _proof_test_nodeid(relic_def, primary_proof_kind, base_scenario_key),
            "required_scenarios": _required_scenarios(relic_def, base_scenario_key),
            "stateful_description_variants": _json_ready(list(source_facts.get("stateful_description_variants") or [])),
            "ui_prompt_slots": list(source_facts.get("ui_prompt_slots") or []),
            "truth_sources": _json_ready(dict(source_facts.get("truth_sources") or {})),
            "resolution_notes": _resolution_notes(relic_id),
        }
        entities.append(row)
        proof_kind_counts[primary_proof_kind] += 1

    return {
        "schema_version": 1,
        "summary": {
            "relic_count": len(entities),
            "proof_kind_counts": dict(sorted(proof_kind_counts.items())),
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
            "schema_version": 1,
            "summary": {
                "relic_count": 0,
                "proof_kind_counts": {},
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
    "PRIMARY_PROOF_KINDS",
    "PICKUP_RNG_RELIC_IDS",
    "RELIC_TRUTH_MATRIX_PATH",
    "SCENARIO_NODEIDS",
    "build_relic_truth_matrix",
    "load_relic_truth_matrix",
]
