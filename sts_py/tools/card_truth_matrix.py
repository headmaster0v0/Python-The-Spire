from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote

from sts_py.engine.combat.card_effects import get_card_effects
from sts_py.engine.content.card_instance import CardInstance, is_misc_stateful_card
from sts_py.engine.content.cards_min import ALL_CARD_DEFS, CurseEffectType
from sts_py.engine.content.official_card_strings import get_official_card_strings
from sts_py.terminal.translation_policy import get_translation_policy_entry
from sts_py.tools import wiki_audit
from sts_py.tools.wiki_bilingual_scraper import BilingualWikiScraper


CARD_TRUTH_MATRIX_PATH = Path(__file__).resolve().parents[1] / "data" / "card_truth_matrix.json"

CARD_DATA_TRUTH_KINDS = (
    "static_source",
    "runtime_variant",
    "generated_variant",
)
CARD_RUNTIME_TRUTH_KINDS = (
    "dispatch_runtime",
    "hook_runtime",
    "run_runtime",
    "none",
)

STATEFUL_DYNAMIC_CARD_IDS = {"Brilliance", "Claw", "GeneticAlgorithm", "MindBlast", "RitualDagger", "SpiritShield"}
RETAIN_HOOK_CARD_IDS = {"Perseverance", "SandsOfTime", "WindmillStrike"}
DRAW_HOOK_CARD_IDS = {"DeusExMachina", "Normality", "Void"}
DISCARD_HOOK_CARD_IDS = {"Reflex", "Tactician"}
STANCE_HOOK_CARD_IDS = {"FlurryOfBlows"}
TARGET_GATE_CARD_IDS = {"Clash", "GrandFinale", "SecretTechnique", "SecretWeapon", "SignatureMove"}
RUNTIME_VARIANT_CARD_IDS = {"GeneticAlgorithm", "RitualDagger", "SearingBlow"}
GENERATED_VARIANT_CARD_IDS = {
    "Beta",
    "Burn",
    "Burn+",
    "Dazed",
    "Expunger",
    "Insight",
    "Miracle",
    "Omega",
    "Safety",
    "Shiv",
    "Slimed",
    "Smite",
    "ThroughViolence",
    "Void",
    "Wound",
}
GENERATED_CHAIN_CARD_IDS = {
    "Alpha",
    "BattleHymn",
    "CarveReality",
    "Chrysalis",
    "ConjureBlade",
    "DeceiveReality",
    "DeusExMachina",
    "Discovery",
    "Distraction",
    "ForeignInfluence",
    "InfernalBlade",
    "JackOfAllTrades",
    "Magnetism",
    "MasterReality",
    "Mayhem",
    "Metamorphosis",
    "ReachHeaven",
    "TheBomb",
    "Transmutation",
    "Violence",
    *GENERATED_VARIANT_CARD_IDS,
}

SCENARIO_NODEIDS = {
    "data_matrix_inventory": (
        "tests/test_card_truth_matrix.py::"
        "test_card_truth_matrix_is_complete_and_decision_filled"
    ),
    "data_source_truth": (
        "tests/test_card_truth_matrix.py::"
        "test_card_truth_matrix_data_rows_match_runtime_source_and_official_truth"
    ),
    "data_wiki_policy_truth": (
        "tests/test_card_truth_matrix.py::"
        "test_card_truth_matrix_wiki_status_and_resolution_notes_follow_translation_policy"
    ),
    "effect_damage": (
        "tests/test_card_truth_matrix.py::"
        "test_judgement_lesson_learned_tantrum_and_flurry_of_blows_change_real_combat_state"
    ),
    "effect_block": (
        "tests/test_card_truth_matrix.py::"
        "test_fasting_mental_fortress_and_spirit_shield_use_real_runtime_state"
    ),
    "effect_draw": (
        "tests/test_card_truth_matrix.py::"
        "test_collect_discipline_and_simmering_fury_delayed_turn_hooks_fire_for_real"
    ),
    "effect_power": (
        "tests/test_card_truth_matrix.py::"
        "test_pressure_points_talk_to_the_hand_wave_of_the_hand_and_wreath_of_flame_hooks_fire"
    ),
    "effect_generated": (
        "tests/test_colorless_nonchoice_tranche_combat.py::"
        "test_jack_of_all_trades_only_generates_implemented_runtime_colorless_cards"
    ),
    "effect_discard_exhaust": (
        "tests/test_silent_discard_utility_combat.py::"
        "test_prepared_plus_draws_two_discards_two"
    ),
    "effect_pile": (
        "tests/test_watcher_rare_draw_combat.py::"
        "test_meditate_recovery_path_respects_hand_limit"
    ),
    "effect_resource": (
        "tests/test_dynamic_x_cost_and_generated_card_truth.py::"
        "test_malaise_free_to_play_keeps_energy_but_chemical_x_still_increases_effect_value"
    ),
    "effect_orb": (
        "tests/test_defect_energy_orb_resource_combat.py::"
        "test_multicast_hits_leftmost_orb_x_or_x_plus_one_times"
    ),
    "effect_stance_turn": (
        "tests/test_watcher_advanced_utility_combat.py::"
        "test_vault_skips_enemy_turn_and_starts_next_player_turn"
    ),
    "effect_heal_hp": (
        "tests/test_colorless_nonchoice_tranche_combat.py::"
        "test_bandage_up_heals_and_exhausts"
    ),
    "effect_noop_misc": (
        "tests/test_curse_combat_comprehensive.py::"
        "test_pride_copy_at_end"
    ),
    "effect_misc_runtime": (
        "tests/test_card_truth_matrix.py::"
        "test_truth_closure_cards_have_explicit_runtime_effect_signatures"
    ),
    "hook_on_draw": (
        "tests/test_watcher_advanced_utility_combat.py::"
        "test_deus_ex_machina_triggers_on_draw_and_generates_miracles"
    ),
    "hook_on_retain": (
        "tests/test_card_truth_matrix.py::"
        "test_retain_hook_cards_and_establishment_apply_real_runtime_mutations"
    ),
    "hook_on_discard": (
        "tests/test_silent_discard_utility_combat.py::"
        "test_reflex_triggers_when_discarded_from_hand"
    ),
    "hook_on_exhaust": (
        "tests/test_ironclad_exhaust_utility_continuation_combat.py::"
        "test_sentinel_exhausted_by_true_grit_grants_energy"
    ),
    "hook_apply_powers_dynamic": (
        "tests/test_colorless_nonchoice_tranche_combat.py::"
        "test_mind_blast_tracks_draw_pile_size_and_upgrade_cost"
    ),
    "hook_on_stance_change": (
        "tests/test_card_truth_matrix.py::"
        "test_judgement_lesson_learned_tantrum_and_flurry_of_blows_change_real_combat_state"
    ),
    "condition_target_or_use_gate": (
        "tests/test_card_truth_matrix.py::"
        "test_follow_up_sanctity_crush_joints_sash_whip_and_signature_move_conditions_hold"
    ),
    "condition_generated_chain": (
        "tests/test_watcher_x_cost_generated_attack_combat.py::"
        "test_conjure_blade_generates_expunger_from_actual_x_cost"
    ),
    "curse_end_of_turn": (
        "tests/test_curse_combat_comprehensive.py::"
        "test_multiple_curses_same_turn"
    ),
    "curse_on_card_played": (
        "tests/test_curse_combat_comprehensive.py::"
        "test_pain_on_card_play"
    ),
    "curse_limit_cards_per_turn": (
        "tests/test_curse_combat_comprehensive.py::"
        "test_normality_limit_cards"
    ),
    "curse_return_on_exhaust": (
        "tests/test_card_dedicated_runtime_truth.py::"
        "test_necronomicurse_returns_to_hand_when_exhausted"
    ),
    "curse_innate_or_ethereal": (
        "tests/test_curse_combat_comprehensive.py::"
        "test_vacuous_exhaust_at_end"
    ),
    "run_stateful_runtime_id": (
        "tests/test_persistent_card_state_identity_truth.py::"
        "test_stateful_card_helpers_and_harness_round_trip_genetic_algorithm_ritual_dagger_and_searing_blow"
    ),
    "run_card_remove_or_transform": (
        "tests/test_card_dedicated_runtime_truth.py::"
        "test_unremovable_curses_and_parasite_penalty_follow_event_rules"
    ),
}

CARD_FAMILY_TESTS = {
    "effect:block": SCENARIO_NODEIDS["effect_block"],
    "effect:damage": SCENARIO_NODEIDS["effect_damage"],
    "effect:discard_exhaust": SCENARIO_NODEIDS["effect_discard_exhaust"],
    "effect:draw": SCENARIO_NODEIDS["effect_draw"],
    "effect:generated": SCENARIO_NODEIDS["effect_generated"],
    "effect:heal_hp": SCENARIO_NODEIDS["effect_heal_hp"],
    "effect:misc_runtime": SCENARIO_NODEIDS["effect_misc_runtime"],
    "effect:noop_misc": SCENARIO_NODEIDS["effect_noop_misc"],
    "effect:orb": SCENARIO_NODEIDS["effect_orb"],
    "effect:pile": SCENARIO_NODEIDS["effect_pile"],
    "effect:power": SCENARIO_NODEIDS["effect_power"],
    "effect:resource": SCENARIO_NODEIDS["effect_resource"],
    "effect:stance_turn": SCENARIO_NODEIDS["effect_stance_turn"],
    "hook:apply_powers_dynamic": SCENARIO_NODEIDS["hook_apply_powers_dynamic"],
    "hook:on_discard": SCENARIO_NODEIDS["hook_on_discard"],
    "hook:on_draw": SCENARIO_NODEIDS["hook_on_draw"],
    "hook:on_exhaust": SCENARIO_NODEIDS["hook_on_exhaust"],
    "hook:on_retain": SCENARIO_NODEIDS["hook_on_retain"],
    "hook:on_stance_change": SCENARIO_NODEIDS["hook_on_stance_change"],
    "condition:generated_chain": SCENARIO_NODEIDS["condition_generated_chain"],
    "condition:target_or_use_gate": SCENARIO_NODEIDS["condition_target_or_use_gate"],
    "curse:end_of_turn": SCENARIO_NODEIDS["curse_end_of_turn"],
    "curse:innate_or_ethereal": SCENARIO_NODEIDS["curse_innate_or_ethereal"],
    "curse:limit_cards_per_turn": SCENARIO_NODEIDS["curse_limit_cards_per_turn"],
    "curse:on_card_played": SCENARIO_NODEIDS["curse_on_card_played"],
    "curse:remove_penalty": SCENARIO_NODEIDS["run_card_remove_or_transform"],
    "curse:return_on_exhaust": SCENARIO_NODEIDS["curse_return_on_exhaust"],
    "curse:unremovable": SCENARIO_NODEIDS["run_card_remove_or_transform"],
    "run:card_remove_or_transform": SCENARIO_NODEIDS["run_card_remove_or_transform"],
    "run:stateful_runtime_id": SCENARIO_NODEIDS["run_stateful_runtime_id"],
}

DEDICATED_CARD_TESTS = {
    "card:Brilliance": (
        "tests/test_card_dedicated_runtime_truth.py::"
        "test_brilliance_scales_from_mantra_gained_this_combat"
    ),
    "card:Collect": (
        "tests/test_card_truth_matrix.py::"
        "test_collect_discipline_and_simmering_fury_delayed_turn_hooks_fire_for_real"
    ),
    "card:ConjureBlade": (
        "tests/test_phase253_stabilization.py::"
        "test_phase253_conjure_blade_chemical_x_and_upgrade_flow_into_expunger_x"
    ),
    "card:CurseOfTheBell": SCENARIO_NODEIDS["run_card_remove_or_transform"],
    "card:DeusExMachina": (
        "tests/test_watcher_advanced_utility_combat.py::"
        "test_deus_ex_machina_triggers_on_draw_and_generates_miracles"
    ),
    "card:Expunger": (
        "tests/test_watcher_x_cost_generated_attack_combat.py::"
        "test_expunger_only_hits_the_selected_target"
    ),
    "card:FlurryOfBlows": (
        "tests/test_card_truth_matrix.py::"
        "test_judgement_lesson_learned_tantrum_and_flurry_of_blows_change_real_combat_state"
    ),
    "card:GeneticAlgorithm": (
        "tests/test_persistent_card_state_identity_truth.py::"
        "test_genetic_algorithm_growth_updates_only_the_played_master_deck_slot"
    ),
    "card:Malaise": (
        "tests/test_phase253_stabilization.py::"
        "test_phase253_malaise_chemical_x_and_upgrade_apply_to_effect_value_only"
    ),
    "card:MindBlast": (
        "tests/test_colorless_nonchoice_tranche_combat.py::"
        "test_mind_blast_tracks_draw_pile_size_and_upgrade_cost"
    ),
    "card:MultiCast": (
        "tests/test_phase253_stabilization.py::"
        "test_phase253_tempest_reinforced_body_and_multicast_share_effect_x_rules"
    ),
    "card:Necronomicurse": SCENARIO_NODEIDS["curse_return_on_exhaust"],
    "card:Normality": SCENARIO_NODEIDS["curse_limit_cards_per_turn"],
    "card:Parasite": SCENARIO_NODEIDS["run_card_remove_or_transform"],
    "card:Perseverance": (
        "tests/test_card_truth_matrix.py::"
        "test_retain_hook_cards_and_establishment_apply_real_runtime_mutations"
    ),
    "card:Reflex": (
        "tests/test_silent_discard_utility_combat.py::"
        "test_reflex_triggers_when_discarded_from_hand"
    ),
    "card:ReinforcedBody": (
        "tests/test_phase253_stabilization.py::"
        "test_phase253_tempest_reinforced_body_and_multicast_share_effect_x_rules"
    ),
    "card:RitualDagger": (
        "tests/test_colorless_power_trigger_persistent_tranche_combat.py::"
        "test_ritual_dagger_kill_updates_battle_instance_and_master_deck_string"
    ),
    "card:SandsOfTime": (
        "tests/test_card_truth_matrix.py::"
        "test_retain_hook_cards_and_establishment_apply_real_runtime_mutations"
    ),
    "card:SearingBlow": (
        "tests/test_dynamic_stateful_noncombat_truth.py::"
        "test_searing_blow_plus_n_uses_same_upgrade_path_for_rest_and_event_flows"
    ),
    "card:SpiritShield": (
        "tests/test_card_truth_matrix.py::"
        "test_fasting_mental_fortress_and_spirit_shield_use_real_runtime_state"
    ),
    "card:Tactician": (
        "tests/test_silent_discard_utility_combat.py::"
        "test_tactician_triggers_when_discarded_from_hand_and_syncs_energy"
    ),
    "card:Tempest": (
        "tests/test_phase253_stabilization.py::"
        "test_phase253_tempest_reinforced_body_and_multicast_share_effect_x_rules"
    ),
    "card:Transmutation": (
        "tests/test_phase253_stabilization.py::"
        "test_phase253_transmutation_free_to_play_keeps_energy_and_still_gets_chemical_x_bonus"
    ),
    "card:Whirlwind": (
        "tests/test_phase253_stabilization.py::"
        "test_phase253_whirlwind_chemical_x_uses_effect_hits_but_spends_only_actual_energy"
    ),
    "card:WindmillStrike": (
        "tests/test_card_truth_matrix.py::"
        "test_retain_hook_cards_and_establishment_apply_real_runtime_mutations"
    ),
}

HIGH_RISK_CARD_IDS = {
    "Brilliance",
    "Collect",
    "ConjureBlade",
    "CurseOfTheBell",
    "DeusExMachina",
    "Expunger",
    "FlurryOfBlows",
    "GeneticAlgorithm",
    "Malaise",
    "MindBlast",
    "MultiCast",
    "Necronomicurse",
    "Normality",
    "Parasite",
    "Perseverance",
    "Reflex",
    "ReinforcedBody",
    "RitualDagger",
    "SandsOfTime",
    "SearingBlow",
    "SpiritShield",
    "Tactician",
    "Tempest",
    "Transmutation",
    "Whirlwind",
    "WindmillStrike",
}

DATA_SCENARIOS_BY_KIND = {
    "generated_variant": [
        SCENARIO_NODEIDS["data_matrix_inventory"],
        SCENARIO_NODEIDS["data_source_truth"],
        SCENARIO_NODEIDS["data_wiki_policy_truth"],
        SCENARIO_NODEIDS["condition_generated_chain"],
    ],
    "runtime_variant": [
        SCENARIO_NODEIDS["data_matrix_inventory"],
        SCENARIO_NODEIDS["data_source_truth"],
        SCENARIO_NODEIDS["data_wiki_policy_truth"],
        SCENARIO_NODEIDS["run_stateful_runtime_id"],
    ],
    "static_source": [
        SCENARIO_NODEIDS["data_matrix_inventory"],
        SCENARIO_NODEIDS["data_source_truth"],
        SCENARIO_NODEIDS["data_wiki_policy_truth"],
    ],
}


def _humanize_identifier(identifier: str) -> str:
    if not identifier:
        return ""
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", identifier.replace("_", " "))
    return re.sub(r"\s+", " ", spaced).strip()


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

    return _unique_preserve_order(paths)


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


def _effect_family(signature: str) -> str:
    if signature == "NoOpEffect":
        return "effect:noop_misc"

    if any(token in signature for token in ("Orb", "Dualcast", "Tempest", "MultiCast", "Fission", "Recursion", "Chaos", "Chill")):
        return "effect:orb"

    if any(token in signature for token in ("ChangeStance", "EndTurn", "SkipEnemyTurn", "InnerPeace")):
        return "effect:stance_turn"

    if signature in {
        "GainEnergyEffect",
        "LoseHPEffect",
        "CollectEffect",
        "BloodForBloodEffect",
        "AggregateEffect",
        "DoubleEnergyEffect",
        "RecycleEffect",
        "TurboEffect",
        "SeeingRedEffect",
        "BattleTranceEffect",
        "ConcentrateEffect",
        "DoppelgangerEffect",
        "SkewerEffect",
        "WhirlwindEffect",
        "MalaiseEffect",
        "ReinforcedBodyEffect",
    }:
        return "effect:resource"

    if signature in {"HealEffect", "HandOfGreedEffect", "ReaperEffect", "FeedEffect", "AlchemizeEffect"}:
        return "effect:heal_hp"

    if any(token in signature for token in ("Generate", "MakeTemp", "JackOfAllTrades", "Discovery", "Distraction", "Transmutation", "ForeignInfluence", "ConjureBlade", "WhiteNoise", "InfernalBlade", "RandomCombatCards")):
        return "effect:generated"

    if any(token in signature for token in ("Exhaust", "Discard", "SecondWind", "SeverSoul", "FiendFire", "Purity", "CalculatedGamble", "BulletTime", "BurningPact", "Unload")):
        return "effect:discard_exhaust"

    if any(token in signature for token in ("Draw", "Scry", "ThinkingAhead", "Forethought", "Setup", "DeepBreath", "Reboot", "Recover", "MoveDrawPileTopToHand", "DrawPileTutor")):
        return "effect:draw"

    if signature in {"UpgradeHandCardEffect", "ApotheosisEffect", "EnlightenmentEffect"}:
        return "effect:pile"

    if any(token in signature for token in ("AddCardToDrawPile", "Entrench", "Havoc", "Madness", "PerfectedStrike", "RandomDrawPileTypeToHand", "OpenCombatChoice")):
        return "effect:pile"

    if any(token in signature for token in ("GainBlock", "Block", "Halt", "FlameBarrier", "AutoShields", "Entrench", "SpiritShield", "Sentinel", "PowerThrough", "Stack", "SteamBarrier", "Wallop")):
        return "effect:block"

    if any(token in signature for token in ("ApplyPower", "ApplyPoison", "Power", "Poison", "Catalyst", "CripplingCloud", "CorpseExplosion", "TemporaryStrengthDown", "GainMantra", "Indignation", "PressurePoints", "Judgement", "TheBomb", "Brutality", "Corruption", "DoubleTap", "InfiniteBlades")):
        return "effect:power"

    if any(token in signature for token in ("Damage", "Attack", "Bane", "Barrage", "Claw", "CompileDriver", "Dropkick", "FTL", "GlassKnife", "HeelHook", "Hemokinesis", "Immolate", "Melter", "Rampage", "RiddleWithHoles", "Scrape", "Sunder", "BowlingBash", "BodySlam", "RitualDagger", "GoForTheEyes")):
        return "effect:damage"

    return "effect:misc_runtime"


def _risk_flags(
    card_id: str,
    runtime_facts: dict[str, Any],
    behavior_paths: list[str],
) -> list[str]:
    flags: list[str] = []
    if int(runtime_facts.get("cost", 0) or 0) == -1 or card_id in {"Expunger"}:
        flags.append("x_cost")
    if card_id in GENERATED_CHAIN_CARD_IDS:
        flags.append("generated_chain")
    if card_id in STATEFUL_DYNAMIC_CARD_IDS or is_misc_stateful_card(card_id) or card_id == "SearingBlow":
        flags.append("misc_stateful")
    if card_id in RETAIN_HOOK_CARD_IDS:
        flags.append("retain_hook")
    if card_id in DRAW_HOOK_CARD_IDS:
        flags.append("draw_hook")
    if card_id in DISCARD_HOOK_CARD_IDS:
        flags.append("discard_hook")
    if card_id in STANCE_HOOK_CARD_IDS:
        flags.append("stance_hook")
    if card_id in RUNTIME_VARIANT_CARD_IDS or any(path.startswith("run.") or path.startswith("run_engine.") for path in behavior_paths):
        flags.append("run_hook")
    if card_id in GENERATED_CHAIN_CARD_IDS or card_id in RUNTIME_VARIANT_CARD_IDS:
        flags.append("deck_mutation")
    if bool(runtime_facts.get("target_required")) or card_id in TARGET_GATE_CARD_IDS:
        flags.append("target_gate")
    card_def = ALL_CARD_DEFS[card_id]
    if any(
        getattr(card_def, attr) is not None
        for attr in (
            "upgrade_cost",
            "upgrade_exhaust",
            "upgrade_ethereal",
            "upgrade_innate",
            "upgrade_retain",
        )
    ) or int(getattr(card_def, "upgrade_damage", 0) or 0) > 0 or int(getattr(card_def, "upgrade_block", 0) or 0) > 0 or int(getattr(card_def, "upgrade_magic_number", 0) or 0) > 0 or card_id in RUNTIME_VARIANT_CARD_IDS:
        flags.append("upgrade_toggle")
    return _unique_preserve_order(flags)


def _card_family_ids(
    card_id: str,
    runtime_effect_signatures: list[str],
    behavior_paths: list[str],
    risk_flags: list[str],
) -> list[str]:
    family_ids: list[str] = []
    for signature in runtime_effect_signatures:
        family_ids.append(_effect_family(signature))

    for path in behavior_paths:
        if path == "card_instance.on_draw":
            family_ids.append("hook:on_draw")
        elif path == "card_instance.on_retain":
            family_ids.append("hook:on_retain")
        elif path == "combat_engine._handle_player_discard_from_hand":
            family_ids.append("hook:on_discard")
        elif path == "card_instance.apply_powers":
            family_ids.append("hook:apply_powers_dynamic")
        elif path == "stance.change_stance":
            family_ids.append("hook:on_stance_change")
        elif path == "combat_engine._process_end_of_turn_curses":
            family_ids.append("curse:end_of_turn")
        elif path == "combat_engine._process_pain_curse_effect":
            family_ids.append("curse:on_card_played")
        elif path == "card_piles._check_normality_in_hand":
            family_ids.append("curse:limit_cards_per_turn")
        elif path == "card_piles.play_card":
            family_ids.append("curse:return_on_exhaust")
        elif path in {"card_piles.end_turn", "card_piles._prepare_innate_cards"}:
            family_ids.append("curse:innate_or_ethereal")
        elif path == "run.events._is_card_removable":
            family_ids.extend(["curse:remove_penalty", "run:card_remove_or_transform"])
        elif path == "run_engine._canonical_card_id":
            family_ids.extend(["curse:unremovable", "run:card_remove_or_transform"])
        elif path == "card_effects.NoOpEffect":
            family_ids.append("effect:noop_misc")

    if "misc_stateful" in risk_flags:
        family_ids.append("run:stateful_runtime_id")
    if "target_gate" in risk_flags:
        family_ids.append("condition:target_or_use_gate")
    if "generated_chain" in risk_flags:
        family_ids.append("condition:generated_chain")
    if card_id in {"Sentinel"}:
        family_ids.append("hook:on_exhaust")

    return sorted(set(_unique_preserve_order(family_ids)))


def _data_truth_kind(card_id: str) -> str:
    if card_id in RUNTIME_VARIANT_CARD_IDS:
        return "runtime_variant"
    if card_id in GENERATED_VARIANT_CARD_IDS:
        return "generated_variant"
    return "static_source"


def _runtime_truth_kind(behavior_paths: list[str], behavior_kind: str) -> str:
    if behavior_kind == "dispatch":
        return "dispatch_runtime"
    if behavior_kind == "run_hook":
        return "run_runtime"
    if behavior_paths:
        return "hook_runtime"
    return "none"


def _wiki_status_and_conflicts(card_id: str, translation_status: str) -> tuple[str, list[str]]:
    policy = get_translation_policy_entry("card", card_id)
    if policy is None:
        if translation_status == "approved_alias":
            return translation_status, ["approved_alias"]
        if translation_status == "wiki_missing":
            return translation_status, ["page_missing"]
        if translation_status == "exact_match":
            return translation_status, []
        return "untracked", ["policy_missing"]
    if policy.alignment_status == "wiki_missing":
        return policy.alignment_status, ["page_missing"]
    if policy.alignment_status == "approved_alias":
        return policy.alignment_status, ["approved_alias"]
    if policy.alignment_status == "exact_match":
        return policy.alignment_status, []
    return policy.alignment_status, ["translation_needs_review"]


def _card_wiki_titles(card_id: str, official_name_en: str, official_name_zhs: str) -> tuple[str, str]:
    policy = get_translation_policy_entry("card", card_id)
    en_title = official_name_en or _humanize_identifier(card_id)
    if policy is not None and policy.huiji_page_or_title.strip():
        return en_title, policy.huiji_page_or_title.strip()
    fallback_cn = official_name_zhs or (policy.runtime_name_cn if policy is not None else "") or card_id
    return en_title, fallback_cn


def _wiki_url(base_url: str, title: str) -> str:
    if not title:
        return ""
    return f"{base_url}/{quote(title.replace(' ', '_'))}"


def _resolution_notes(card_id: str, data_truth_kind: str) -> str:
    policy = get_translation_policy_entry("card", card_id)
    if policy is not None:
        if policy.alignment_status == "approved_alias":
            if policy.approved_alias_note.strip():
                return policy.approved_alias_note.strip()
            if policy.huiji_page_or_title.strip() and policy.runtime_name_cn.strip():
                return f"Approved Huiji alias: {policy.runtime_name_cn} -> {policy.huiji_page_or_title}"
        if policy.alignment_status == "wiki_missing":
            return "Huiji reference page missing; official card strings retained."
    if data_truth_kind == "runtime_variant":
        return "Runtime notation carries upgrade or misc state while official strings stay on the base card."
    if data_truth_kind == "generated_variant":
        return "Generated or variant card reuses official card-string truth while keeping runtime-specific identity."
    return ""


def _truth_sources(
    java_facts: dict[str, Any],
    runtime_facts: dict[str, Any],
    finding: dict[str, Any],
    policy_alignment_status: str,
) -> dict[str, Any]:
    return {
        "mechanics_source": str(java_facts.get("source_kind", "") or "decompiled_java_card"),
        "java_source_path": str(java_facts.get("java_path", "") or ""),
        "runtime_source": str(runtime_facts.get("source_kind", "") or "runtime_card_def"),
        "official_translation_source": str(runtime_facts.get("translation_source", "") or ""),
        "official_description_source": str(runtime_facts.get("description_source", "") or ""),
        "wiki_reference_source": str(finding.get("reference_source", "") or ""),
        "translation_policy_alignment_status": policy_alignment_status,
    }


def build_card_truth_matrix(
    repo_root: Path | str | None = None,
    *,
    raw_snapshot: dict[str, Any] | None = None,
    audit_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_repo_root = Path(repo_root) if repo_root is not None else Path.cwd()
    raw_snapshot = raw_snapshot or wiki_audit.build_cli_raw_snapshot(
        resolved_repo_root,
        enable_network=False,
        entity_types={"card"},
    )
    audit_bundle = audit_bundle or wiki_audit.run_audit_from_raw_snapshot(raw_snapshot, repo_root=resolved_repo_root)
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
    data_truth_counts: Counter[str] = Counter()
    runtime_truth_counts: Counter[str] = Counter()
    wiki_status_counts: Counter[str] = Counter()
    runtime_family_ids: set[str] = set()

    for card_id in sorted(ALL_CARD_DEFS):
        runtime_facts = wiki_audit.build_card_runtime_facts(card_id)
        java_facts = wiki_audit.build_card_java_facts(resolved_repo_root, card_id)
        official = get_official_card_strings(card_id)
        finding = translation_findings[card_id]
        policy = get_translation_policy_entry("card", card_id)
        runtime_effect_signatures = _runtime_effect_signatures(card_id)
        behavior_paths = _behavior_paths_for_card(card_id)
        behavior_kind = _primary_behavior_kind(behavior_paths)
        risk_flags = _risk_flags(card_id, runtime_facts, behavior_paths)
        family_ids = _card_family_ids(card_id, runtime_effect_signatures, behavior_paths, risk_flags)
        data_truth_kind = _data_truth_kind(card_id)
        runtime_truth_kind = _runtime_truth_kind(behavior_paths, behavior_kind)
        wiki_status, wiki_conflict_fields = _wiki_status_and_conflicts(card_id, str(finding["status"]))
        wiki_en_title, wiki_cn_title = _card_wiki_titles(
            card_id,
            str(getattr(official, "name_en", "") or runtime_facts.get("official_name_en", "")),
            str(getattr(official, "name_zhs", "") or runtime_facts.get("official_name_zhs", "")),
        )

        behavior_counts[behavior_kind] += 1
        translation_status_counts[str(finding["status"])] += 1
        data_truth_counts[data_truth_kind] += 1
        runtime_truth_counts[runtime_truth_kind] += 1
        wiki_status_counts[wiki_status] += 1
        runtime_family_ids.update(family_ids)

        row = {
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
            "runtime_effect_signatures": runtime_effect_signatures,
            "behavior_kind": behavior_kind,
            "behavior_paths": behavior_paths,
            "policy_alignment_status": str(getattr(policy, "alignment_status", "") or ""),
            "missing_in_runtime": card_id in completeness_missing,
            "data_truth_kind": data_truth_kind,
            "runtime_truth_kind": runtime_truth_kind,
            "family_ids": family_ids,
            "data_proof_nodeids": DATA_SCENARIOS_BY_KIND[data_truth_kind],
            "runtime_proof_nodeids": _unique_preserve_order(
                [CARD_FAMILY_TESTS[family_id] for family_id in family_ids if family_id in CARD_FAMILY_TESTS]
                + ([DEDICATED_CARD_TESTS[f"card:{card_id}"]] if f"card:{card_id}" in DEDICATED_CARD_TESTS else [])
            ),
            "wiki_en_url": _wiki_url(BilingualWikiScraper.EN_WIKIGG_WIKI_URL, wiki_en_title),
            "wiki_cn_url": _wiki_url(BilingualWikiScraper.CN_WIKI_URL, wiki_cn_title),
            "wiki_en_title": wiki_en_title,
            "wiki_cn_title": wiki_cn_title,
            "wiki_status": wiki_status,
            "wiki_conflict_fields": wiki_conflict_fields,
            "truth_sources": _json_ready(
                _truth_sources(
                    java_facts=java_facts,
                    runtime_facts=runtime_facts,
                    finding=finding,
                    policy_alignment_status=str(getattr(policy, "alignment_status", "") or ""),
                )
            ),
            "resolution_notes": _resolution_notes(card_id, data_truth_kind),
            "risk_flags": risk_flags,
        }
        rows.append(row)

    return {
        "schema_version": 2,
        "entity_type": "card",
        "summary": {
            "total_cards": len(rows),
            "behavior_kind_counts": dict(sorted(behavior_counts.items())),
            "translation_status_counts": dict(sorted(translation_status_counts.items())),
            "data_truth_kind_counts": dict(sorted(data_truth_counts.items())),
            "runtime_truth_kind_counts": dict(sorted(runtime_truth_counts.items())),
            "wiki_status_counts": dict(sorted(wiki_status_counts.items())),
            "family_count": len(runtime_family_ids),
            "high_risk_card_count": len(HIGH_RISK_CARD_IDS),
            "dedicated_card_count": len(DEDICATED_CARD_TESTS),
            "missing_in_runtime": len(completeness_missing),
        },
        "scenario_nodeids": dict(sorted(SCENARIO_NODEIDS.items())),
        "family_tests": dict(sorted(CARD_FAMILY_TESTS.items())),
        "dedicated_tests": dict(sorted(DEDICATED_CARD_TESTS.items())),
        "high_risk_card_ids": sorted(HIGH_RISK_CARD_IDS),
        "entities": _json_ready(rows),
    }


def load_card_truth_matrix(repo_root: Path | str | None = None) -> dict[str, Any]:
    path = CARD_TRUTH_MATRIX_PATH
    if repo_root is not None:
        candidate = Path(repo_root) / "sts_py" / "data" / "card_truth_matrix.json"
        if candidate.exists():
            path = candidate
    if not path.exists():
        return {
            "schema_version": 2,
            "entity_type": "card",
            "summary": {
                "total_cards": 0,
                "behavior_kind_counts": {},
                "translation_status_counts": {},
                "data_truth_kind_counts": {},
                "runtime_truth_kind_counts": {},
                "wiki_status_counts": {},
                "family_count": 0,
                "high_risk_card_count": 0,
                "dedicated_card_count": 0,
                "missing_in_runtime": 0,
            },
            "scenario_nodeids": {},
            "family_tests": {},
            "dedicated_tests": {},
            "high_risk_card_ids": [],
            "entities": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


__all__ = [
    "CARD_DATA_TRUTH_KINDS",
    "CARD_FAMILY_TESTS",
    "CARD_RUNTIME_TRUTH_KINDS",
    "CARD_TRUTH_MATRIX_PATH",
    "DEDICATED_CARD_TESTS",
    "HIGH_RISK_CARD_IDS",
    "SCENARIO_NODEIDS",
    "_behavior_paths_for_card",
    "_effect_family",
    "build_card_truth_matrix",
    "load_card_truth_matrix",
]
