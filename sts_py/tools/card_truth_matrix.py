from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import ALL_CARD_DEFS, CurseEffectType
from sts_py.engine.content.official_card_strings import get_official_card_strings
from sts_py.engine.combat.card_effects import get_card_effects
from sts_py.terminal.translation_policy import get_translation_policy_entry
from sts_py.tools import wiki_audit


CARD_TRUTH_MATRIX_PATH = Path(__file__).resolve().parents[1] / "data" / "card_truth_matrix.json"

STATEFUL_DYNAMIC_CARD_IDS = {"Brilliance", "Claw", "GeneticAlgorithm", "MindBlast", "RitualDagger", "SpiritShield"}
RETAIN_HOOK_CARD_IDS = {"Perseverance", "SandsOfTime", "WindmillStrike"}
DRAW_HOOK_CARD_IDS = {"DeusExMachina", "Normality", "Void"}
DISCARD_HOOK_CARD_IDS = {"Reflex", "Tactician"}
STANCE_HOOK_CARD_IDS = {"FlurryOfBlows"}


def _json_ready(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _runtime_effect_signatures(card_id: str) -> list[str]:
    signatures: list[str] = []
    for target_idx in (0, None):
        try:
            effects = get_card_effects(CardInstance(card_id), target_idx)
        except Exception:
            effects = []
        for effect in effects:
            signature = type(effect).__name__
            if signature not in signatures:
                signatures.append(signature)
    return signatures


def _curse_behavior_path(card: CardInstance) -> str | None:
    effect_type = getattr(card, "curse_effect_type", CurseEffectType.NONE)
    if effect_type in {
        CurseEffectType.END_OF_TURN_DAMAGE,
        CurseEffectType.END_OF_TURN_WEAK,
        CurseEffectType.END_OF_TURN_VULNERABLE,
        CurseEffectType.END_OF_TURN_FRAIL,
        CurseEffectType.REGRET_EFFECT,
        CurseEffectType.INNATE_COPY_AT_END,
    }:
        return "combat_engine._process_end_of_turn_curses"
    if effect_type == CurseEffectType.ON_CARD_PLAYED_LOSE_HP:
        return "combat_engine._process_pain_curse_effect"
    if effect_type == CurseEffectType.LIMIT_CARDS_PER_TURN:
        return "card_piles._check_normality_in_hand"
    if effect_type == CurseEffectType.RETURN_TO_HAND_ON_EXHAUST:
        return "card_piles.play_card"
    if effect_type == CurseEffectType.CANNOT_REMOVE_FROM_DECK:
        return "run_engine._canonical_card_id"
    if effect_type == CurseEffectType.IF_REMOVED_LOSE_MAX_HP:
        return "run.events._is_card_removable"
    if effect_type == CurseEffectType.VACUOUS:
        return "card_effects.NoOpEffect"
    if effect_type == CurseEffectType.NONE:
        if bool(getattr(card, "is_ethereal", False)):
            return "card_piles.end_turn"
        if bool(getattr(card, "is_innate", False)):
            return "card_piles._prepare_innate_cards"
        if bool(getattr(card, "is_unplayable", False)):
            return "card_effects.NoOpEffect"
    return None


def _behavior_paths_for_card(card_id: str) -> list[str]:
    card = CardInstance(card_id)
    paths: list[str] = []
    signatures = _runtime_effect_signatures(card_id)
    if signatures:
        paths.append(f"card_effects.get_card_effects:{','.join(signatures)}")
    if card_id in DRAW_HOOK_CARD_IDS:
        paths.append("card_instance.on_draw")
    if card_id in DISCARD_HOOK_CARD_IDS:
        paths.append("combat_engine._handle_player_discard_from_hand")
    if card_id in RETAIN_HOOK_CARD_IDS:
        paths.append("card_instance.on_retain")
    if card_id in STANCE_HOOK_CARD_IDS:
        paths.append("stance.change_stance")
    if card_id in STATEFUL_DYNAMIC_CARD_IDS:
        paths.append("card_instance.apply_powers")

    curse_path = _curse_behavior_path(card)
    if curse_path is not None:
        paths.append(curse_path)

    if card_id == "Slimed":
        paths.append("card_effects.NoOpEffect")

    ordered: list[str] = []
    seen: set[str] = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        ordered.append(path)
    return ordered


def _primary_behavior_kind(paths: list[str]) -> str:
    if not paths:
        return "unclassified"
    first = paths[0]
    if first.startswith("card_effects.get_card_effects:"):
        return "dispatch"
    if first.startswith("card_instance.on_"):
        return "card_hook"
    if first.startswith("combat_engine._handle_player_discard_from_hand"):
        return "discard_hook"
    if first.startswith("stance.change_stance"):
        return "stance_hook"
    if first.startswith("run."):
        return "run_hook"
    return "special_hook"


def build_card_truth_matrix(repo_root: Path | str | None = None) -> dict[str, Any]:
    resolved_repo_root = Path(repo_root) if repo_root is not None else Path.cwd()
    raw_snapshot = wiki_audit.build_cli_raw_snapshot(resolved_repo_root, enable_network=False, entity_types={"card"})
    audit_bundle = wiki_audit.run_audit_from_raw_snapshot(raw_snapshot, repo_root=resolved_repo_root)
    translation_findings = {
        item["entity_id"]: item
        for item in audit_bundle["translation_audit"]["findings"]
        if item["entity_type"] == "card"
    }
    completeness_missing = {
        item["entity_id"]
        for item in audit_bundle["completeness_audit"]["missing_in_runtime"]
        if item["entity_type"] == "card"
    }

    rows: list[dict[str, Any]] = []
    behavior_counts: Counter[str] = Counter()
    translation_status_counts: Counter[str] = Counter()

    for card_id in sorted(ALL_CARD_DEFS):
        runtime_facts = wiki_audit.build_card_runtime_facts(card_id)
        java_facts = wiki_audit.build_card_java_facts(resolved_repo_root, card_id)
        official = get_official_card_strings(card_id)
        finding = translation_findings[card_id]
        policy = get_translation_policy_entry("card", card_id)
        behavior_paths = _behavior_paths_for_card(card_id)
        behavior_kind = _primary_behavior_kind(behavior_paths)
        behavior_counts[behavior_kind] += 1
        translation_status_counts[str(finding["status"])] += 1

        rows.append(
            {
                "runtime_id": card_id,
                "official_key": str(getattr(official, "official_key", "") or java_facts.get("official_key", "")),
                "java_class": str(java_facts.get("java_class", "")),
                "java_path": str(java_facts.get("java_path", "")),
                "type": runtime_facts["type"],
                "rarity": runtime_facts["rarity"],
                "cost": runtime_facts["cost"],
                "target_required": runtime_facts["target_required"],
                "damage": runtime_facts["damage"],
                "block": runtime_facts["block"],
                "magic_number": runtime_facts["magic_number"],
                "exhaust": runtime_facts["exhaust"],
                "ethereal": runtime_facts["ethereal"],
                "retain": runtime_facts["retain"],
                "innate": runtime_facts["innate"],
                "is_unplayable": bool(getattr(ALL_CARD_DEFS[card_id], "is_unplayable", False)),
                "official_name_en": str(getattr(official, "name_en", "") or runtime_facts.get("official_name_en", "")),
                "official_name_zhs": str(getattr(official, "name_zhs", "") or runtime_facts.get("official_name_zhs", "")),
                "official_desc_en": str(getattr(official, "description_en", "") or runtime_facts.get("official_desc_en", "")),
                "official_desc_zhs": str(getattr(official, "description_zhs", "") or runtime_facts.get("official_desc_zhs", "")),
                "official_upgrade_desc_en": str(getattr(official, "upgrade_description_en", "") or runtime_facts.get("official_upgrade_desc_en", "")),
                "official_upgrade_desc_zhs": str(getattr(official, "upgrade_description_zhs", "") or runtime_facts.get("official_upgrade_desc_zhs", "")),
                "translation_source": str(runtime_facts.get("translation_source", "")),
                "description_source": str(runtime_facts.get("description_source", "")),
                "translation_status": str(finding["status"]),
                "translation_reference_source": str(finding.get("reference_source", "") or ""),
                "huiji_page_or_title": str(finding.get("huiji_page_or_title", "") or ""),
                "approved_alias_note": str(finding.get("approved_alias_note", "") or ""),
                "runtime_effect_signatures": _runtime_effect_signatures(card_id),
                "behavior_kind": behavior_kind,
                "behavior_paths": behavior_paths,
                "policy_alignment_status": str(getattr(policy, "alignment_status", "") or ""),
                "missing_in_runtime": card_id in completeness_missing,
            }
        )

    return {
        "schema_version": 1,
        "entity_type": "card",
        "summary": {
            "total_cards": len(rows),
            "behavior_kind_counts": dict(sorted(behavior_counts.items())),
            "translation_status_counts": dict(sorted(translation_status_counts.items())),
            "missing_in_runtime": len(completeness_missing),
        },
        "entities": _json_ready(rows),
    }


def load_card_truth_matrix(repo_root: Path | str | None = None) -> dict[str, Any]:
    path = CARD_TRUTH_MATRIX_PATH
    if repo_root is not None:
        candidate = Path(repo_root) / "sts_py" / "data" / "card_truth_matrix.json"
        if candidate.exists():
            path = candidate
    return json.loads(path.read_text(encoding="utf-8"))


__all__ = [
    "CARD_TRUTH_MATRIX_PATH",
    "build_card_truth_matrix",
    "load_card_truth_matrix",
]
