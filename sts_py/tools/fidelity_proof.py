from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import sts_py.engine.combat.powers as power_module
from sts_py.engine.combat.potion_effects import POTION_EFFECTS
from sts_py.engine.content.relics import ALL_RELICS, RelicDef

FIDELITY_PROOF_MATRIX_PATH = Path(__file__).resolve().parents[1] / "data" / "fidelity_proof_matrix.json"
NONCARD_ENTITY_TYPES = ("relic", "potion", "power", "monster", "event")

POWER_CALLBACK_NAMES = (
    "at_damage_give",
    "at_damage_final_give",
    "at_damage_receive",
    "at_damage_final_receive",
    "modify_block",
    "at_start_of_turn",
    "at_start_of_turn_post_draw",
    "at_end_of_turn",
    "at_end_of_turn_pre_end_turn_cards",
    "at_end_of_round",
    "on_attacked",
    "on_card_draw",
    "on_change_stance",
    "on_energy_recharge",
    "on_gain_block",
    "on_hp_lost",
    "on_inflict_damage",
    "on_player_apply_power_to_enemy",
    "on_player_attack_damage",
    "on_player_attacked",
    "on_player_card_played",
    "on_player_power_played",
    "on_player_skill_played",
    "on_scry",
    "on_steal_gold",
    "on_death",
    "on_victory",
)

MONSTER_STATE_BASIC = "monster:basic_intents"

RELIC_BATTLE_START_SIGNATURES = {
    "relic:apply_weak_start",
    "relic:artifact_start",
    "relic:at_battle_start",
    "relic:at_battle_start_buffer",
    "relic:at_battle_start_energy",
    "relic:at_boss_elite_start",
    "relic:at_boss_start",
    "relic:at_first_turn_draw",
    "relic:first_combat_hp_one",
    "relic:start_with_block",
    "relic:start_with_curse",
    "relic:start_with_energy",
    "relic:start_with_shivs",
}
RELIC_TURN_SIGNATURES = {
    "relic:at_turn_end",
    "relic:at_turn_end_empty_orb",
    "relic:at_turn_end_hand_block",
    "relic:at_turn_end_no_discard",
    "relic:at_turn_start",
    "relic:at_turn_start_delayed",
    "relic:at_turn_start_no_attack",
    "relic:block_intent",
    "relic:conserve_energy",
    "relic:every_2_turns",
    "relic:every_n_turns",
    "relic:every_n_turns_self",
    "relic:gain_mantra_per_turn",
}
RELIC_CARDPLAY_SIGNATURES = {
    "relic:chance_for_free_attack",
    "relic:chance_for_free_skill",
    "relic:every_n_attacks",
    "relic:every_n_attacks_self",
    "relic:every_n_cards",
    "relic:every_n_skills",
    "relic:first_attack_combat",
    "relic:first_attack_twice",
    "relic:modify_damage",
    "relic:modify_min_damage",
    "relic:on_attack",
    "relic:on_card_played",
    "relic:on_damage",
    "relic:on_enemy_death",
    "relic:on_enemy_death_poison_transfer",
    "relic:on_poison_applied",
    "relic:on_power_played",
    "relic:strike_damage_bonus",
    "relic:zero_cost_attack_bonus_damage",
}
RELIC_DRAW_DISCARD_SIGNATURES = {
    "relic:empty_hand_draw",
    "relic:limit_cards_draw",
    "relic:on_discard",
    "relic:on_exhaust_add_random",
    "relic:on_exhaust_damage_all",
    "relic:on_first_discard_per_turn",
    "relic:on_shuffle",
    "relic:scry_on_shuffle",
}
RELIC_RESOURCE_SIGNATURES = {
    "relic:card_remove_discount",
    "relic:debuff_clear",
    "relic:double_potion_potency",
    "relic:gain_gold",
    "relic:gain_potion",
    "relic:gold_disabled",
    "relic:gold_multiply",
    "relic:heal_multiply",
    "relic:heal_per_power",
    "relic:limit_cards_play",
    "relic:mana_gain_disabled",
    "relic:on_gain_gold",
    "relic:on_heal",
    "relic:on_hp_loss",
    "relic:on_potion_use",
    "relic:on_victory",
    "relic:potion_always_drop",
    "relic:potion_gain_disabled",
}
RELIC_REWARD_SIGNATURES = {
    "relic:card_choice_three",
    "relic:card_reward",
    "relic:card_reward_max_hp",
    "relic:card_reward_modifier",
    "relic:card_reward_reduce",
    "relic:change_rare_chance",
    "relic:change_uncommon_chance",
    "relic:chest_relics",
    "relic:elite_reward_relics",
    "relic:extra_card_reward",
    "relic:on_chest_open",
}
RELIC_SHOP_SIGNATURES = {
    "relic:on_shop_enter",
    "relic:shop_no_sell_out",
    "relic:shop_price_modifier",
}
RELIC_REST_SIGNATURES = {
    "relic:on_rest",
    "relic:on_rest_add_card",
    "relic:rest_heal_bonus",
    "relic:rest_heal_disabled",
    "relic:rest_site_dig",
    "relic:rest_site_forge_disabled",
    "relic:rest_site_remove",
    "relic:rest_site_strength",
    "relic:rest_site_transform",
    "relic:rest_site_upgrade",
}
RELIC_PICKUP_SIGNATURES = {
    "relic:gain_max_HP",
    "relic:on_pickup",
    "relic:upgrade_random",
}
RELIC_DECK_SIGNATURES = {
    "relic:bottled",
    "relic:card_copy",
    "relic:deck_transform",
    "relic:deck_transform_and_upgrade",
    "relic:modify_strike",
    "relic:on_card_added",
    "relic:remove_cards_from_deck",
}
RELIC_PROGRESS_SIGNATURES = {
    "relic:avoid_enemies",
    "relic:elite_hp_modifier",
    "relic:free_movement",
    "relic:on_floor_climb",
    "relic:on_question_room",
    "relic:treasure_room_every_n_question",
}
RELIC_CURSE_SIGNATURES = {
    "relic:curse_negate_trigger",
    "relic:curse_playable",
    "relic:immune_frail",
    "relic:immune_weak",
    "relic:modify_strength",
    "relic:modify_vulnerable",
    "relic:modify_weak",
    "relic:on_curse_received",
    "relic:on_vulnerable_apply",
    "relic:start_with_strength_per_curse",
}
RELIC_ORB_STANCE_SIGNATURES = {
    "relic:gain_intangible",
    "relic:miracle",
    "relic:on_exit_calm",
    "relic:on_exit_calm_energy",
    "relic:orb_passive_multiply",
    "relic:scry_bonus",
}
RELIC_MISC_SIGNATURES = {
    "relic:cant_heal",
    "relic:on_combat_end",
    "relic:on_death_save",
    "relic:on_trap_combat",
    "relic:replace_starter_relic",
}

POTION_DISCOVERY_SIGNATURES = {
    "potion:AttackPotionEffect",
    "potion:ColorlessPotionEffect",
    "potion:PowerPotionEffect",
    "potion:SkillPotionEffect",
}
POTION_RESOURCE_SIGNATURES = {
    "potion:BlockPotionEffect",
    "potion:BloodPotionEffect",
    "potion:EnergyPotionEffect",
    "potion:FruitJuiceEffect",
    "potion:SwiftPotionEffect",
}
POTION_PLAYER_POWER_SIGNATURES = {
    "potion:AncientPotionEffect",
    "potion:CultistPotionEffect",
    "potion:DexterityPotionEffect",
    "potion:DuplicationPotionEffect",
    "potion:EssenceOfSteelEffect",
    "potion:FlexPotionEffect",
    "potion:FocusPotionEffect",
    "potion:GhostInAJarEffect",
    "potion:HeartofIronEffect",
    "potion:LiquidBronzeEffect",
    "potion:RegenPotionEffect",
    "potion:SpeedPotionEffect",
    "potion:StrengthPotionEffect",
}
POTION_ENEMY_POWER_SIGNATURES = {
    "potion:FearPotionEffect",
    "potion:PoisonPotionEffect",
    "potion:WeakPotionEffect",
}
POTION_CARD_MUTATION_SIGNATURES = {
    "potion:BlessingOfTheForgeEffect",
    "potion:BottledMiracleEffect",
    "potion:CunningPotionEffect",
    "potion:ElixirEffect",
    "potion:GamblersBrewEffect",
    "potion:LiquidMemoriesEffect",
    "potion:SneckoOilEffect",
}
POTION_SPECIAL_SIGNATURES = {
    "potion:AmbrosiaEffect",
    "potion:DistilledChaosEffect",
    "potion:EntropicBrewEffect",
    "potion:EssenceOfDarknessEffect",
    "potion:ExplosivePotionEffect",
    "potion:FairyInABottleEffect",
    "potion:FirePotionEffect",
    "potion:PotionofCapacityEffect",
    "potion:SmokeBombEffect",
    "potion:StancePotionEffect",
}

POWER_DAMAGE_SIGNATURES = {
    "power:at_damage_final_give",
    "power:at_damage_final_receive",
    "power:at_damage_give",
    "power:at_damage_receive",
    "power:modify_block",
}
POWER_TURN_SIGNATURES = {
    "power:at_end_of_round",
    "power:at_end_of_turn",
    "power:at_end_of_turn_pre_end_turn_cards",
    "power:at_start_of_turn",
    "power:at_start_of_turn_post_draw",
    "power:on_energy_recharge",
    "power:passive_state",
}
POWER_CARDPLAY_SIGNATURES = {
    "power:on_player_apply_power_to_enemy",
    "power:on_player_attack_damage",
    "power:on_player_card_played",
    "power:on_player_power_played",
    "power:on_player_skill_played",
}
POWER_REACTION_SIGNATURES = {
    "power:on_attacked",
    "power:on_card_draw",
    "power:on_change_stance",
    "power:on_gain_block",
    "power:on_hp_lost",
    "power:on_inflict_damage",
    "power:on_player_attacked",
    "power:on_scry",
    "power:on_steal_gold",
    "power:on_death",
    "power:on_victory",
}

MONSTER_STATE_TEST_GROUPS = {
    "tests/test_phase269_monster_event_shop_truth.py::test_phase269_monster_state_family_truth": {
        MONSTER_STATE_BASIC,
        "monster:artifact",
        "monster:escape",
        "monster:half_dead_revive",
        "monster:intangible",
        "monster:minion",
        "monster:spawn_summon",
        "monster:split",
    }
}

EVENT_CARD_SIGNATURES = {
    "event:choose_card_to_remove",
    "event:gain_card",
    "event:remove_card",
    "event:transform_random_card",
    "event:upgrade_card",
    "event_gating:requires_card_removal",
    "event_gating:requires_card_transform",
    "event_gating:requires_card_upgrade",
}
EVENT_RESOURCE_SIGNATURES = {
    "event:gain_dexterity",
    "event:gain_gold",
    "event:gain_hp",
    "event:gain_max_hp",
    "event:gain_max_hp_percent",
    "event:gain_random_relic",
    "event:gain_strength",
    "event:lose_gold",
    "event:lose_hp",
    "event:lose_max_hp",
    "event:lose_max_hp_percent",
    "event:obtain_potion",
    "event_gating:cost",
}
EVENT_BRANCH_SIGNATURES = {
    "event:no_effect_choices",
    "event:search",
    "event:trade_faces",
    "event:trigger_combat",
    "event_gating:requires_attack_card",
}

FAMILY_PROOF_TEST_GROUPS = {
    "tests/test_phase269_relic_potion_power_truth.py::test_phase269_relic_family_battle_turn_and_resource_truth": (
        RELIC_BATTLE_START_SIGNATURES | RELIC_TURN_SIGNATURES | RELIC_RESOURCE_SIGNATURES
    ),
    "tests/test_phase269_relic_potion_power_truth.py::test_phase269_relic_family_reward_shop_rest_and_pickup_truth": (
        RELIC_REWARD_SIGNATURES
        | RELIC_SHOP_SIGNATURES
        | RELIC_REST_SIGNATURES
        | RELIC_PICKUP_SIGNATURES
        | RELIC_PROGRESS_SIGNATURES
        | RELIC_MISC_SIGNATURES
    ),
    "tests/test_phase269_relic_potion_power_truth.py::test_phase269_relic_family_cardplay_deck_and_status_truth": (
        RELIC_CARDPLAY_SIGNATURES
        | RELIC_DRAW_DISCARD_SIGNATURES
        | RELIC_DECK_SIGNATURES
        | RELIC_CURSE_SIGNATURES
        | RELIC_ORB_STANCE_SIGNATURES
    ),
    "tests/test_phase269_relic_potion_power_truth.py::test_phase269_potion_family_resource_and_power_truth": (
        POTION_RESOURCE_SIGNATURES | POTION_PLAYER_POWER_SIGNATURES | POTION_ENEMY_POWER_SIGNATURES
    ),
    "tests/test_phase269_relic_potion_power_truth.py::test_phase269_potion_family_card_and_special_truth": (
        POTION_DISCOVERY_SIGNATURES | POTION_CARD_MUTATION_SIGNATURES | POTION_SPECIAL_SIGNATURES
    ),
    "tests/test_phase269_relic_potion_power_truth.py::test_phase269_power_callback_family_turn_and_damage_truth": (
        POWER_DAMAGE_SIGNATURES | POWER_TURN_SIGNATURES
    ),
    "tests/test_phase269_relic_potion_power_truth.py::test_phase269_power_callback_family_play_and_reaction_truth": (
        POWER_CARDPLAY_SIGNATURES | POWER_REACTION_SIGNATURES
    ),
    "tests/test_phase269_monster_event_shop_truth.py::test_phase269_event_choice_family_card_and_resource_truth": (
        EVENT_CARD_SIGNATURES | EVENT_RESOURCE_SIGNATURES
    ),
    "tests/test_phase269_monster_event_shop_truth.py::test_phase269_event_choice_family_branching_truth": (
        EVENT_BRANCH_SIGNATURES
    ),
    **MONSTER_STATE_TEST_GROUPS,
}

DEDICATED_PROOF_TESTS = {
    "relic:Astrolabe": "tests/test_relic_truth_matrix.py::test_relic_truth_matrix_rng_relics_match_fixed_seed_truth",
    "relic:BlackStar": "tests/test_phase267_dynamic_truth.py::test_phase267_reward_mutation_family_keeps_prayer_wheel_and_black_star_live",
    "relic:BustedCrown": "tests/test_relic_truth_matrix.py::test_relic_truth_matrix_question_card_busted_crown_and_prayer_wheel_stack",
    "relic:CallingBell": "tests/test_run_layer_relic_fidelity.py::test_calling_bell_adds_curse_and_three_extra_relics",
    "relic:CursedKey": "tests/test_relic_truth_matrix.py::test_relic_truth_matrix_cursed_key_and_matryoshka_preserve_bonus_relics_when_taking_sapphire_key",
    "relic:LizardTail": "tests/test_relic_truth_matrix.py::test_relic_truth_matrix_cross_relic_callbacks_and_modifiers_remain_live",
    "relic:MagicFlower": "tests/test_phase267_dynamic_truth.py::test_phase267_potion_and_relic_callback_family_remains_live",
    "relic:Matryoshka": "tests/test_relic_truth_matrix.py::test_relic_truth_matrix_cursed_key_and_matryoshka_preserve_bonus_relics_when_taking_sapphire_key",
    "relic:MummifiedHand": "tests/test_relic_truth_matrix.py::test_relic_truth_matrix_rng_relics_match_fixed_seed_truth",
    "relic:PandoraBox": "tests/test_run_layer_relic_fidelity.py::test_pandora_box_transforms_all_strikes_and_defends",
    "relic:PaperCrane": "tests/test_relic_truth_matrix.py::test_relic_truth_matrix_cross_relic_callbacks_and_modifiers_remain_live",
    "relic:PaperFrog": "tests/test_relic_truth_matrix.py::test_relic_truth_matrix_cross_relic_callbacks_and_modifiers_remain_live",
    "relic:PrayerWheel": "tests/test_phase267_dynamic_truth.py::test_phase267_reward_mutation_family_keeps_prayer_wheel_and_black_star_live",
    "relic:QuestionCard": "tests/test_relic_truth_matrix.py::test_relic_truth_matrix_question_card_busted_crown_and_prayer_wheel_stack",
    "relic:SacredBark": "tests/test_phase269_relic_potion_power_truth.py::test_phase269_relic_and_potion_dedicated_bespoke_truth",
    "relic:SmilingMask": "tests/test_phase267_dynamic_truth.py::test_phase267_shop_lane_keeps_courier_restock_and_smiling_mask_remove_truth",
    "relic:SneckoSkull": "tests/test_relic_truth_matrix.py::test_relic_truth_matrix_cross_relic_callbacks_and_modifiers_remain_live",
    "relic:Sozu": "tests/test_relic_truth_matrix.py::test_relic_truth_matrix_sozu_blocks_potion_gain_from_relic_rewards",
    "relic:TheCourier": "tests/test_phase267_dynamic_truth.py::test_phase267_shop_lane_keeps_courier_restock_and_smiling_mask_remove_truth",
    "relic:TheSpecimen": "tests/test_relic_truth_matrix.py::test_relic_truth_matrix_cross_relic_callbacks_and_modifiers_remain_live",
    "relic:TinyHouse": "tests/test_run_layer_relic_fidelity.py::test_tiny_house_applies_full_pickup_bundle",
    "relic:WarPaint": "tests/test_relic_truth_matrix.py::test_relic_truth_matrix_rng_relics_match_fixed_seed_truth",
    "relic:Whetstone": "tests/test_relic_truth_matrix.py::test_relic_truth_matrix_rng_relics_match_fixed_seed_truth",
    "potion:DistilledChaos": "tests/test_dynamic_autoplay_replay_truth.py::test_havoc_mayhem_and_distilled_chaos_leave_no_residual_choice_when_no_targets_exist",
    "potion:EntropicBrew": "tests/test_phase267_dynamic_truth.py::test_phase267_potion_and_relic_callback_family_remains_live",
    "potion:FairyInABottle": "tests/test_phase269_relic_potion_power_truth.py::test_phase269_relic_and_potion_dedicated_bespoke_truth",
    "potion:GamblersBrew": "tests/test_phase269_relic_potion_power_truth.py::test_phase269_relic_and_potion_dedicated_bespoke_truth",
    "potion:LiquidMemories": "tests/test_phase269_relic_potion_power_truth.py::test_phase269_relic_and_potion_dedicated_bespoke_truth",
    "potion:SmokeBomb": "tests/test_phase269_relic_potion_power_truth.py::test_phase269_relic_and_potion_dedicated_bespoke_truth",
    "power:AfterImage": "tests/test_phase269_relic_potion_power_truth.py::test_phase269_power_callback_family_play_and_reaction_truth",
    "power:Burst": "tests/test_dynamic_autoplay_replay_truth.py::test_burst_plus_consumes_two_skills_without_recursive_replay",
    "power:EchoForm": "tests/test_dynamic_autoplay_replay_truth.py::test_echo_form_only_duplicates_the_first_original_card_each_turn",
    "power:Equilibrium": "tests/test_dynamic_turn_boundary_truth.py::test_equilibrium_retains_non_ethereal_without_opening_choice",
    "power:Nightmare": "tests/test_dynamic_autoplay_replay_truth.py::test_nightmare_preserves_special_runtime_identity_and_respects_hand_limit",
    "power:Rebound": "tests/test_dynamic_autoplay_replay_truth.py::test_rebound_moves_the_next_non_power_played_card_to_the_top_of_draw_pile",
    "power:Repair": "tests/test_phase269_relic_potion_power_truth.py::test_phase269_power_dedicated_bespoke_truth",
    "power:Retain Cards": "tests/test_dynamic_turn_boundary_truth.py::test_well_laid_plans_opens_end_turn_retain_choice_and_auto_resumes_after_selection",
    "power:Rupture": "tests/test_phase269_relic_potion_power_truth.py::test_phase269_power_dedicated_bespoke_truth",
    "power:Rushdown": "tests/test_phase269_relic_potion_power_truth.py::test_phase269_power_dedicated_bespoke_truth",
    "power:StaticDischarge": "tests/test_phase269_relic_potion_power_truth.py::test_phase269_power_dedicated_bespoke_truth",
    "monster:Collector": "tests/test_phase269_monster_event_shop_truth.py::test_phase269_monster_dedicated_bespoke_truth",
    "monster:Darkling": "tests/test_phase267_dynamic_truth.py::test_phase267_monster_state_and_event_branching_family_remains_live",
    "monster:GremlinLeader": "tests/test_phase269_monster_event_shop_truth.py::test_phase269_monster_dedicated_bespoke_truth",
    "monster:Looter": "tests/test_phase269_monster_event_shop_truth.py::test_phase269_monster_dedicated_bespoke_truth",
    "monster:Mugger": "tests/test_phase269_monster_event_shop_truth.py::test_phase269_monster_dedicated_bespoke_truth",
    "monster:Nemesis": "tests/test_phase269_monster_event_shop_truth.py::test_phase269_monster_dedicated_bespoke_truth",
    "monster:SlimeBoss": "tests/test_phase269_monster_event_shop_truth.py::test_phase269_monster_dedicated_bespoke_truth",
    "event:Dead Adventurer": "tests/test_phase269_monster_event_shop_truth.py::test_phase269_event_dedicated_bespoke_truth",
    "event:Face Trader": "tests/test_phase269_monster_event_shop_truth.py::test_phase269_event_dedicated_bespoke_truth",
    "event:Living Wall": "tests/test_phase269_monster_event_shop_truth.py::test_phase269_event_dedicated_bespoke_truth",
}


def _sorted_unique(values: list[str] | set[str] | tuple[str, ...]) -> list[str]:
    return sorted({str(value) for value in values if str(value).strip()})


def _invert_group_mapping(groups: dict[str, set[str]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for nodeid, family_ids in groups.items():
        for family_id in family_ids:
            if family_id in mapping and mapping[family_id] != nodeid:
                raise ValueError(f"family id {family_id!r} mapped to multiple proof tests")
            mapping[family_id] = nodeid
    return dict(sorted(mapping.items()))


FAMILY_PROOF_TESTS = _invert_group_mapping(FAMILY_PROOF_TEST_GROUPS)


def build_relic_effect_signatures(relic_def: RelicDef) -> list[str]:
    return _sorted_unique({f"relic:{effect.effect_type.value}" for effect in relic_def.effects})


def build_potion_effect_signatures(potion_id: str) -> list[str]:
    effect = POTION_EFFECTS.get(potion_id)
    if effect is None:
        return []
    return [f"potion:{type(effect).__name__}"]


def build_power_callback_signatures(power_cls: type[Any]) -> list[str]:
    signatures = []
    for callback_name in POWER_CALLBACK_NAMES:
        if callback_name in power_cls.__dict__:
            signatures.append(f"power:{callback_name}")
    if not signatures:
        signatures.append("power:passive_state")
    return _sorted_unique(signatures)


def build_monster_state_signatures(monster_id: str, monster_cls: type[Any]) -> list[str]:
    text = inspect.getsource(monster_cls)
    attrs = set(vars(monster_cls).keys())
    signatures = {MONSTER_STATE_BASIC}
    if any(name in attrs for name in ("has_split", "has_split_triggered", "split_triggered")):
        signatures.add("monster:split")
    if any(name in attrs for name in ("can_revive", "half_dead")):
        signatures.add("monster:half_dead_revive")
    if any(name in attrs for name in ("escape_def", "escaped")) or "def escape(" in text:
        signatures.add("monster:escape")
    if any(token in text for token in ("summon", "spawn", "pending_spawn", "_summon_")):
        signatures.add("monster:spawn_summon")
    if "Artifact" in text:
        signatures.add("monster:artifact")
    if "Intangible" in text:
        signatures.add("monster:intangible")
    if "MinionPower" in text or monster_id in {"BronzeOrb", "Dagger", "TorchHead"}:
        signatures.add("monster:minion")
    return _sorted_unique(signatures)


def build_event_choice_effect_signatures(event: Any) -> list[str]:
    signatures: set[str] = set()
    for choice in getattr(event, "choices", []) or []:
        choice_signatures = {effect.effect_type.value for effect in getattr(choice, "effects", []) or []}
        if getattr(choice, "requires_card_removal", False):
            choice_signatures.add("gating:requires_card_removal")
        if getattr(choice, "requires_card_transform", False):
            choice_signatures.add("gating:requires_card_transform")
        if getattr(choice, "requires_card_upgrade", False):
            choice_signatures.add("gating:requires_card_upgrade")
        if getattr(choice, "requires_attack_card", False):
            choice_signatures.add("gating:requires_attack_card")
        if int(getattr(choice, "cost", 0) or 0) > 0:
            choice_signatures.add("gating:cost")
        if getattr(choice, "trigger_combat", False):
            choice_signatures.add("trigger_combat")
        if getattr(choice, "search_level", 0):
            choice_signatures.add("search")
        if getattr(choice, "trade_faces", False):
            choice_signatures.add("trade_faces")
        for signature in choice_signatures:
            if signature.startswith("gating:"):
                signatures.add(f"event_{signature}")
            else:
                signatures.add(f"event:{signature}")
    if not signatures:
        signatures.add("event:no_effect_choices")
    return _sorted_unique(signatures)


def _noncard_signature_field(entity_type: str) -> str:
    return {
        "relic": "effect_signatures",
        "potion": "effect_signatures",
        "power": "callback_signatures",
        "monster": "state_signatures",
        "event": "choice_effect_signatures",
    }[entity_type]


def get_runtime_family_ids(entity_type: str, runtime_facts: dict[str, Any]) -> list[str]:
    field_name = _noncard_signature_field(entity_type)
    return _sorted_unique(list(runtime_facts.get(field_name) or []))


def build_fidelity_proof_matrix_from_raw_snapshot(raw_snapshot: dict[str, Any]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    counts: dict[str, int] = {entity_type: 0 for entity_type in NONCARD_ENTITY_TYPES}

    for record in list(raw_snapshot.get("records") or []):
        entity_type = str(record.get("entity_type", ""))
        if entity_type not in NONCARD_ENTITY_TYPES:
            continue
        entity_id = str(record.get("entity_id", ""))
        runtime_facts = dict(record.get("runtime_facts") or {})
        family_ids = get_runtime_family_ids(entity_type, runtime_facts)
        entity_key = f"{entity_type}:{entity_id}"
        proof_kind = "dedicated" if entity_key in DEDICATED_PROOF_TESTS else "family"
        entries.append(
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "family_ids": family_ids,
                "proof_kind": proof_kind,
                "notes": "",
            }
        )
        counts[entity_type] += 1

    entries.sort(key=lambda item: (item["entity_type"], item["entity_id"]))
    unique_families = sorted({family_id for entry in entries for family_id in entry["family_ids"]})
    dedicated_count = sum(1 for entry in entries if entry["proof_kind"] == "dedicated")
    return {
        "schema_version": 1,
        "summary": {
            "entity_counts": counts,
            "family_count": len(unique_families),
            "dedicated_entity_count": dedicated_count,
            "family_entity_count": len(entries) - dedicated_count,
        },
        "family_tests": FAMILY_PROOF_TESTS,
        "dedicated_tests": dict(sorted(DEDICATED_PROOF_TESTS.items())),
        "entities": entries,
    }


def build_fidelity_proof_matrix(repo_root: Path | str, *, raw_snapshot: dict[str, Any]) -> dict[str, Any]:
    _ = Path(repo_root)
    return build_fidelity_proof_matrix_from_raw_snapshot(raw_snapshot)


def load_fidelity_proof_matrix(repo_root: Path | str | None = None) -> dict[str, Any]:
    path = FIDELITY_PROOF_MATRIX_PATH
    if repo_root is not None:
        candidate = Path(repo_root) / "sts_py" / "data" / "fidelity_proof_matrix.json"
        if candidate.exists():
            path = candidate
    if not path.exists():
        return {
            "schema_version": 1,
            "summary": {
                "entity_counts": {},
                "family_count": 0,
                "dedicated_entity_count": 0,
                "family_entity_count": 0,
            },
            "family_tests": {},
            "dedicated_tests": {},
            "entities": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


__all__ = [
    "DEDICATED_PROOF_TESTS",
    "FAMILY_PROOF_TESTS",
    "FIDELITY_PROOF_MATRIX_PATH",
    "MONSTER_STATE_BASIC",
    "NONCARD_ENTITY_TYPES",
    "POWER_CALLBACK_NAMES",
    "build_event_choice_effect_signatures",
    "build_fidelity_proof_matrix",
    "build_fidelity_proof_matrix_from_raw_snapshot",
    "build_monster_state_signatures",
    "build_potion_effect_signatures",
    "build_power_callback_signatures",
    "build_relic_effect_signatures",
    "get_runtime_family_ids",
    "load_fidelity_proof_matrix",
]
