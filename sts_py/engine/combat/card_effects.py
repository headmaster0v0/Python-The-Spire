"""Card effect execution framework.

This module implements the action-based card effect system used in STS.
Cards generate actions when used, which are then executed by the combat engine.

Key concepts from Java:
- Cards use addToBot() to queue actions
- Actions execute in order (FIFO)
- Actions can spawn more actions
- Damage/Block/Power application happens through actions
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from functools import lru_cache
from typing import TYPE_CHECKING, Any
try:
    from typing import Protocol
except ImportError:
    class Protocol(object):
        pass

if TYPE_CHECKING:
    from sts_py.engine.content.card_instance import CardInstance
    from sts_py.engine.combat.combat_state import CombatState, Player
    from sts_py.engine.monsters.monster_base import MonsterBase

from sts_py.engine.content.card_instance import CardInstance, get_default_misc_for_card, get_runtime_card_base_id
from sts_py.engine.content.cards_min import ALL_CARD_DEFS, ALL_COLOR_CARD_DEFS, COLORLESS_ALL_DEFS, DEFECT_ALL_DEFS, CardRarity, CardType
from sts_py.engine.combat.powers import create_power, gain_mantra
from sts_py.engine.combat.stance import StanceType, change_stance


def _card_manager_rng(card_manager: Any):
    return getattr(card_manager, "rng", None) if card_manager is not None else None


def _hand_limit_offset_for_played_card(card_manager: Any, played_card: CardInstance) -> int:
    if card_manager is None:
        return 0
    return 1 if played_card in getattr(card_manager.hand, "cards", []) else 0


def _hand_cards_excluding_played(card_manager: Any, played_card: CardInstance) -> list[tuple[int, CardInstance]]:
    if card_manager is None:
        return []
    return [
        (index, hand_card)
        for index, hand_card in enumerate(card_manager.hand.cards)
        if hand_card is not played_card
    ]


def _select_hand_card_index(
    card_manager: Any,
    played_card: CardInstance,
    *,
    predicate=None,
) -> int | None:
    candidates = []
    for index, hand_card in _hand_cards_excluding_played(card_manager, played_card):
        if predicate is not None and not predicate(hand_card):
            continue
        candidates.append(index)
    if not candidates:
        return None
    rng = _card_manager_rng(card_manager)
    if rng is not None and len(candidates) > 1:
        return candidates[rng.random_int(len(candidates) - 1)]
    return candidates[0]


def _select_first_hand_card_index(
    card_manager: Any,
    played_card: CardInstance,
    *,
    predicate=None,
) -> int | None:
    for index, hand_card in _hand_cards_excluding_played(card_manager, played_card):
        if predicate is not None and not predicate(hand_card):
            continue
        return index
    return None


def _select_hand_card_index_by_uuid(
    card_manager: Any,
    played_card: CardInstance,
    target_uuid: str | None,
) -> int | None:
    if not target_uuid or card_manager is None:
        return None
    for index, hand_card in _hand_cards_excluding_played(card_manager, played_card):
        if str(getattr(hand_card, "uuid", "")) == str(target_uuid):
            return index
    return None


def _apply_temporary_upgrade(card_to_upgrade: CardInstance) -> bool:
    if getattr(card_to_upgrade, "upgraded", False):
        return False
    card_to_upgrade.upgrade()
    return True


def _trigger_exhaust_hooks(
    card_manager: Any,
    source: Any,
    exhausted_card: CardInstance,
) -> None:
    exhausted_card.on_exhaust()
    if not hasattr(source, "powers"):
        return
    block_gain, draw_amount = source.powers.on_exhaust(exhausted_card)
    if block_gain > 0:
        source.gain_block(block_gain)
    if draw_amount > 0 and card_manager is not None:
        card_manager.draw_cards(draw_amount)
    combat_state = getattr(card_manager, "_combat_state", None)
    engine = getattr(combat_state, "engine", None)
    if engine is not None and hasattr(engine, "_trigger_relic_effects"):
        engine._trigger_relic_effects("on_exhaust")


def _move_hand_card_to_exhaust(
    card_manager: Any,
    source: Any,
    *,
    hand_index: int,
) -> CardInstance | None:
    if card_manager is None or hand_index < 0 or hand_index >= len(card_manager.hand.cards):
        return None
    exhausted_card = card_manager.hand.pop(hand_index)
    if exhausted_card is None:
        return None
    if hasattr(card_manager, "_check_normality_in_hand"):
        card_manager._check_normality_in_hand()
    _trigger_exhaust_hooks(card_manager, source, exhausted_card)
    card_manager.exhaust_pile.add(exhausted_card)
    return exhausted_card


def _move_hand_card_to_discard(
    card_manager: Any,
    *,
    hand_index: int,
) -> CardInstance | None:
    if card_manager is None or hand_index < 0 or hand_index >= len(card_manager.hand.cards):
        return None
    discarded_card = card_manager.hand.pop(hand_index)
    if discarded_card is None:
        return None
    if hasattr(card_manager, "_check_normality_in_hand"):
        card_manager._check_normality_in_hand()
    combat_state = getattr(card_manager, "_combat_state", None)
    engine = getattr(combat_state, "engine", None)
    if engine is not None and hasattr(engine, "_handle_player_discard_from_hand"):
        engine._handle_player_discard_from_hand(discarded_card)
    else:
        card_manager.discard_pile.add(discarded_card)
    return discarded_card


def _apply_poison_to_monster(source: Player, monster: MonsterBase, amount: int) -> None:
    if amount <= 0 or monster.is_dead():
        return
    bonus = max(0, int(getattr(source, "_extra_poison_on_applied", 0) or 0))
    if bonus == 0:
        combat_state = getattr(source, "_combat_state", None)
        engine = getattr(combat_state, "engine", None)
        if engine is not None:
            from sts_py.engine.content.relics import RelicEffectType, get_relic_by_id
            for relic_id in getattr(engine, "relics", []) or []:
                relic_def = get_relic_by_id(relic_id)
                if relic_def is None:
                    continue
                for effect in getattr(relic_def, "effects", []) or []:
                    if effect.effect_type == RelicEffectType.ON_POISON_APPLIED and effect.extra.get("type") == "extra_poison":
                        bonus += int(effect.value or 0)
            if bonus > 0:
                source._extra_poison_on_applied = bonus
    _apply_power_to_enemy_from_player(source, monster, "Poison", amount + bonus)


def _sync_monster_power_trackers(monster: MonsterBase, power_type: str, amount: int) -> None:
    if power_type == "Vulnerable":
        current = int(getattr(monster, "vulnerable", 0) or 0)
        monster.vulnerable = max(0, current + amount)
    elif power_type == "Weak":
        current = int(getattr(monster, "weak", 0) or 0)
        monster.weak = max(0, current + amount)


def _apply_power_to_enemy_from_player(
    source: Player | None,
    monster: MonsterBase,
    power_type: str,
    amount: int,
) -> bool:
    if amount <= 0 or monster.is_dead():
        return False
    from sts_py.engine.combat.powers import PowerType, create_power

    applied_power = create_power("Strength", -amount, monster.id) if power_type == "StrengthDown" else create_power(power_type, amount, monster.id)
    if getattr(applied_power, "power_type", None) == PowerType.DEBUFF and monster.has_power("Artifact"):
        monster.powers.reduce_power("Artifact", 1)
        return False
    if power_type == "Strength":
        monster.gain_strength(amount)
    else:
        monster.add_power(applied_power)
        _sync_monster_power_trackers(monster, power_type, amount)
    if source is not None and hasattr(source, "powers"):
        source.powers.on_player_apply_power_to_enemy(source, monster, applied_power)
    return True


def _is_minion_target(target: Any) -> bool:
    if bool(getattr(target, "is_minion", False) or getattr(target, "minion", False)):
        return True
    powers = getattr(target, "powers", None)
    return bool(powers is not None and hasattr(powers, "has_power") and powers.has_power("Minion"))


def _is_true_kill_reward_target(target: Any) -> bool:
    if target is None:
        return False
    if not bool(getattr(target, "is_dead", lambda: False)()):
        return False
    if bool(getattr(target, "half_dead", False)):
        return False
    if _is_minion_target(target):
        return False
    return True


def _refresh_misc_stateful_card_instance(card: CardInstance, combat_state: Any) -> None:
    card_id = getattr(card, "card_id", None)
    default_misc = int(get_default_misc_for_card(str(card_id)) or 0)
    misc_value = max(0, int(getattr(card, "misc", 0) or default_misc))
    if card_id == "RitualDagger":
        card.base_damage = misc_value
        card.damage = card.base_damage
    elif card_id == "GeneticAlgorithm":
        card.base_block = misc_value
        card.block = card.base_block
        card.is_block_modified = False
    else:
        return
    if hasattr(card, "apply_powers"):
        card.apply_powers(combat_state)


def _update_stateful_card_master_deck(card: CardInstance, combat_state: Any) -> None:
    run_engine = getattr(combat_state, "run_engine", None)
    run_state = getattr(run_engine, "state", None) if run_engine is not None else None
    deck = getattr(run_state, "deck", None)
    if not isinstance(deck, list):
        return

    deck_index = getattr(card, "_master_deck_index", None)
    if isinstance(deck_index, int) and 0 <= deck_index < len(deck):
        if get_runtime_card_base_id(str(deck[deck_index])) == getattr(card, "card_id", None):
            deck[deck_index] = card.runtime_card_id
            return

    if not bool(getattr(card, "allow_master_deck_fallback_sync", True)):
        return

    matching_indices = [
        index
        for index, deck_card in enumerate(deck)
        if get_runtime_card_base_id(str(deck_card)) == getattr(card, "card_id", None)
    ]
    if len(matching_indices) == 1:
        deck[matching_indices[0]] = card.runtime_card_id


def _apply_misc_stateful_growth(card: CardInstance, combat_state: Any, amount: int) -> None:
    if amount <= 0:
        return
    if getattr(card, "card_id", None) not in {"RitualDagger", "GeneticAlgorithm"}:
        return

    target_uuid = str(getattr(card, "uuid", ""))
    seen: set[int] = set()

    def _grow(candidate: CardInstance | None) -> None:
        if candidate is None:
            return
        if str(getattr(candidate, "uuid", "")) != target_uuid:
            return
        identity = id(candidate)
        if identity in seen:
            return
        seen.add(identity)
        default_misc = int(get_default_misc_for_card(str(getattr(candidate, "card_id", ""))) or 0)
        candidate.misc = int(getattr(candidate, "misc", 0) or default_misc) + amount
        _refresh_misc_stateful_card_instance(candidate, combat_state)

    _grow(card)

    card_manager = getattr(combat_state, "card_manager", None)
    if card_manager is not None:
        for pile in (
            card_manager.hand,
            card_manager.draw_pile,
            card_manager.discard_pile,
            card_manager.exhaust_pile,
            card_manager.limbo_pile,
        ):
            for candidate in getattr(pile, "cards", []) or []:
                _grow(candidate)

    _update_stateful_card_master_deck(card, combat_state)


def _apply_ritual_dagger_growth(card: CardInstance, combat_state: Any, amount: int) -> None:
    _apply_misc_stateful_growth(card, combat_state, amount)


def _grow_claw_cards(combat_state: Any, played_card: CardInstance, amount: int) -> None:
    if amount <= 0:
        return
    seen: set[int] = set()

    def _boost(card: CardInstance | None) -> None:
        if card is None or getattr(card, "card_id", None) != "Claw":
            return
        identity = id(card)
        if identity in seen:
            return
        seen.add(identity)
        card.combat_damage_bonus = int(getattr(card, "combat_damage_bonus", 0) or 0) + amount
        try:
            card.apply_powers(combat_state)
        except Exception:
            pass

    _boost(played_card)
    card_manager = getattr(combat_state, "card_manager", None)
    if card_manager is None:
        return
    for pile in (card_manager.hand, card_manager.draw_pile, card_manager.discard_pile):
        for pile_card in getattr(pile, "cards", []) or []:
            _boost(pile_card)


def _combat_rng(combat_state: Any):
    card_manager = getattr(combat_state, "card_manager", None)
    if card_manager is not None and getattr(card_manager, "rng", None) is not None:
        return card_manager.rng
    return getattr(combat_state, "rng", None)


def _last_played_card_type_matches(combat_state: Any, card_type: CardType) -> bool:
    return str(getattr(combat_state, "_last_card_played_type", "") or "") == card_type.value


def _monster_intends_attack(monster: Any) -> bool:
    move = getattr(monster, "move", None)
    intent = getattr(move, "intent", None)
    if intent is None:
        intent = getattr(monster, "intent", None)
    if intent is None:
        return False
    intent_name = str(getattr(intent, "name", intent) or "")
    return "ATTACK" in intent_name


def _living_monsters(combat_state: Any) -> list[Any]:
    return [monster for monster in getattr(combat_state, "monsters", []) or [] if not monster.is_dead()]


def _lose_hp_direct(monster: Any, amount: int) -> int:
    hp_loss = max(0, int(amount or 0))
    if hp_loss <= 0 or monster is None or monster.is_dead():
        return 0
    current_hp = max(0, int(getattr(monster, "hp", 0) or 0))
    monster.hp = max(0, current_hp - hp_loss)
    if monster.hp <= 0:
        monster.is_dying = True
    return hp_loss


def _upgrade_first_upgradeable_card(combat_state: Any, source_card: CardInstance | None = None) -> str | None:
    card_manager = getattr(combat_state, "card_manager", None)
    seen_runtime_ids: set[str] = set()
    if card_manager is not None:
        for pile in (
            getattr(card_manager, "hand", None),
            getattr(card_manager, "draw_pile", None),
            getattr(card_manager, "discard_pile", None),
            getattr(card_manager, "exhaust_pile", None),
        ):
            for candidate in getattr(pile, "cards", []) or []:
                if candidate is source_card:
                    continue
                if getattr(candidate, "upgraded", False):
                    continue
                candidate.upgrade()
                seen_runtime_ids.add(str(getattr(candidate, "runtime_card_id", "") or ""))
                return str(getattr(candidate, "runtime_card_id", "") or "")

    run_engine = getattr(combat_state, "run_engine", None)
    run_state = getattr(run_engine, "state", None) if run_engine is not None else None
    deck = getattr(run_state, "deck", None)
    if not isinstance(deck, list):
        return None
    for index, card_id in enumerate(deck):
        candidate = CardInstance(str(card_id))
        if candidate.upgraded:
            continue
        candidate.upgrade()
        deck[index] = candidate.runtime_card_id
        return candidate.runtime_card_id
    return None


def _implemented_power_card_ids() -> list[str]:
    power_ids: list[str] = []
    for card_id, card_def in ALL_CARD_DEFS.items():
        if getattr(card_def, "card_type", None) != CardType.POWER:
            continue
        if getattr(card_def, "is_unplayable", False):
            continue
        try:
            if get_card_effects(CardInstance(card_id)):
                power_ids.append(card_id)
        except Exception:
            continue
    return sorted(set(power_ids))


def _implemented_defect_common_card_ids() -> list[str]:
    common_ids: list[str] = []
    for card_id, card_def in DEFECT_ALL_DEFS.items():
        if getattr(card_def, "rarity", None) != CardRarity.COMMON:
            continue
        if getattr(card_def, "is_unplayable", False):
            continue
        try:
            if get_card_effects(CardInstance(card_id)):
                common_ids.append(card_id)
        except Exception:
            continue
    return sorted(set(common_ids))


def _implemented_silent_skill_card_ids() -> list[str]:
    from sts_py.engine.content.cards_min import SILENT_ALL_DEFS

    skill_ids: list[str] = []
    for card_id, card_def in SILENT_ALL_DEFS.items():
        if getattr(card_def, "card_type", None) != CardType.SKILL:
            continue
        if getattr(card_def, "is_unplayable", False):
            continue
        try:
            if get_card_effects(CardInstance(card_id)):
                skill_ids.append(card_id)
        except Exception:
            continue
    return sorted(set(skill_ids))


DISCOVERY_HEALING_EXCLUDED_IDS = {
    "BandageUp",
    "Bite",
    "Feed",
    "Reaper",
    "SelfRepair",
}

COLORLESS_HEALING_EXCLUDED_IDS = {
    "BandageUp",
}


def _has_runtime_effects(card_id: str) -> bool:
    try:
        return bool(get_card_effects(CardInstance(card_id), 0) or get_card_effects(CardInstance(card_id), None))
    except Exception:
        return False


def _implemented_combat_card_ids(
    card_defs: dict[str, Any],
    *,
    card_type: CardType,
    allowed_rarities: tuple[CardRarity, ...],
    excluded_card_ids: set[str] | None = None,
) -> list[str]:
    card_ids: list[str] = []
    excluded = excluded_card_ids or set()
    for card_id, card_def in card_defs.items():
        if getattr(card_def, "card_type", None) != card_type:
            continue
        if getattr(card_def, "rarity", None) not in allowed_rarities:
            continue
        if getattr(card_def, "is_unplayable", False):
            continue
        if card_id in excluded:
            continue
        if _has_runtime_effects(card_id):
            card_ids.append(card_id)
    return sorted(set(card_ids))


@lru_cache(maxsize=None)
def _implemented_colorless_combat_card_ids() -> tuple[str, ...]:
    allowed_rarities = (
        CardRarity.COMMON,
        CardRarity.UNCOMMON,
        CardRarity.RARE,
    )
    return tuple(
        _implemented_combat_card_ids(
            COLORLESS_ALL_DEFS,
            card_type=CardType.SKILL,
            allowed_rarities=allowed_rarities,
            excluded_card_ids=COLORLESS_HEALING_EXCLUDED_IDS,
        )
        + _implemented_combat_card_ids(
            COLORLESS_ALL_DEFS,
            card_type=CardType.ATTACK,
            allowed_rarities=allowed_rarities,
            excluded_card_ids=COLORLESS_HEALING_EXCLUDED_IDS,
        )
        + _implemented_combat_card_ids(
            COLORLESS_ALL_DEFS,
            card_type=CardType.POWER,
            allowed_rarities=allowed_rarities,
            excluded_card_ids=COLORLESS_HEALING_EXCLUDED_IDS,
        )
    )


@lru_cache(maxsize=None)
def _implemented_colored_discovery_card_ids() -> tuple[str, ...]:
    return tuple(
        _implemented_combat_card_ids(
            ALL_COLOR_CARD_DEFS,
            card_type=CardType.SKILL,
            allowed_rarities=(CardRarity.COMMON, CardRarity.UNCOMMON, CardRarity.RARE),
            excluded_card_ids=DISCOVERY_HEALING_EXCLUDED_IDS,
        )
        + _implemented_combat_card_ids(
            ALL_COLOR_CARD_DEFS,
            card_type=CardType.ATTACK,
            allowed_rarities=(CardRarity.COMMON, CardRarity.UNCOMMON, CardRarity.RARE),
            excluded_card_ids=DISCOVERY_HEALING_EXCLUDED_IDS,
        )
        + _implemented_combat_card_ids(
            ALL_COLOR_CARD_DEFS,
            card_type=CardType.POWER,
            allowed_rarities=(CardRarity.COMMON, CardRarity.UNCOMMON, CardRarity.RARE),
            excluded_card_ids=DISCOVERY_HEALING_EXCLUDED_IDS,
        )
    )


@lru_cache(maxsize=None)
def _implemented_attack_card_ids() -> tuple[str, ...]:
    return tuple(
        _implemented_combat_card_ids(
            ALL_CARD_DEFS,
            card_type=CardType.ATTACK,
            allowed_rarities=(
                CardRarity.BASIC,
                CardRarity.COMMON,
                CardRarity.UNCOMMON,
                CardRarity.RARE,
            ),
        )
    )


@lru_cache(maxsize=None)
def _implemented_skill_card_ids() -> tuple[str, ...]:
    return tuple(
        _implemented_combat_card_ids(
            ALL_CARD_DEFS,
            card_type=CardType.SKILL,
            allowed_rarities=(
                CardRarity.BASIC,
                CardRarity.COMMON,
                CardRarity.UNCOMMON,
                CardRarity.RARE,
            ),
        )
    )


def _choose_random_implemented_power_card_id(combat_state: Any) -> str | None:
    power_ids = _implemented_power_card_ids()
    if not power_ids:
        return None
    rng = _combat_rng(combat_state)
    if rng is not None and len(power_ids) > 1:
        return power_ids[rng.random_int(len(power_ids) - 1)]
    return power_ids[0]


def _choose_random_implemented_defect_common_card_id(combat_state: Any) -> str | None:
    common_ids = _implemented_defect_common_card_ids()
    if not common_ids:
        return None
    rng = _combat_rng(combat_state)
    if rng is not None and len(common_ids) > 1:
        return common_ids[rng.random_int(len(common_ids) - 1)]
    return common_ids[0]


def _choose_random_implemented_silent_skill_card_id(combat_state: Any) -> str | None:
    skill_ids = _implemented_silent_skill_card_ids()
    if not skill_ids:
        return None
    rng = _combat_rng(combat_state)
    if rng is not None and len(skill_ids) > 1:
        return skill_ids[rng.random_int(len(skill_ids) - 1)]
    return skill_ids[0]


def _choose_random_card_id_from_pool(
    combat_state: Any,
    card_ids: list[str] | tuple[str, ...],
) -> str | None:
    if not card_ids:
        return None
    rng = _combat_rng(combat_state)
    if rng is not None and len(card_ids) > 1:
        return card_ids[rng.random_int(len(card_ids) - 1)]
    return card_ids[0]


def _generate_random_colorless_combat_cards_to_hand(
    combat_state: Any,
    count: int,
    *,
    hand_limit_offset: int = 0,
    configure_card=None,
) -> list[str]:
    card_manager = getattr(combat_state, "card_manager", None)
    if card_manager is None or count <= 0:
        return []
    generated_ids: list[str] = []
    pool = list(_implemented_colorless_combat_card_ids())
    for _ in range(count):
        selected_card_id = _choose_random_card_id_from_pool(combat_state, pool)
        if not selected_card_id:
            break
        card_manager.generate_cards_to_hand(
            selected_card_id,
            1,
            hand_limit_offset=hand_limit_offset,
            configure_card=configure_card,
        )
        generated_ids.append(selected_card_id)
    return generated_ids


def _x_cost_bonus(combat_state: Any) -> int:
    engine = getattr(combat_state, "engine", None)
    relics = getattr(engine, "relics", []) if engine is not None else []
    return 2 if "ChemicalX" in (relics or []) else 0


def _resolve_x_cost_values(card: CardInstance, combat_state: Any, source: Any) -> tuple[int | None, int | None]:
    if card.cost != -1:
        return None, None
    preset_resolved_x_cost = getattr(card, "_resolved_x_cost", None)
    if preset_resolved_x_cost is not None:
        preset_actual_x_cost = getattr(card, "_actual_x_cost", None)
        return (
            0 if preset_actual_x_cost is None else max(0, int(preset_actual_x_cost or 0)),
            max(0, int(preset_resolved_x_cost or 0)),
        )
    actual_x_cost = 0 if card.free_to_play_once else max(0, int(getattr(source, "energy", 0) or 0))
    effect_x_cost = actual_x_cost + _x_cost_bonus(combat_state)
    return actual_x_cost, effect_x_cost


def _frost_channels_this_combat(combat_state: Any) -> int:
    player = getattr(combat_state, "player", None)
    return max(0, int(getattr(player, "_frost_orbs_channeled_this_combat", 0) or 0))


def _refresh_dynamic_card_for_current_state(card: CardInstance, combat_state: Any) -> None:
    if getattr(card, "card_id", None) == "Blizzard":
        base_damage = _frost_channels_this_combat(combat_state) * max(0, int(getattr(card, "magic_number", 0) or 0))
    elif getattr(card, "card_id", None) == "MindBlast":
        draw_pile = getattr(getattr(combat_state, "card_manager", None), "draw_pile", None)
        base_damage = len(getattr(draw_pile, "cards", []) or [])
    else:
        return
    card.base_damage = base_damage
    card.damage = base_damage
    card.is_damage_modified = False


def _configure_zero_cost_if_positive(new_card: CardInstance) -> None:
    if int(getattr(new_card, "cost", -1) or -1) > 0:
        new_card.cost = 0
        new_card.cost_for_turn = 0
        new_card.is_cost_modified = True
        new_card.is_cost_modified_for_turn = True


def _card_choice_label(card: CardInstance) -> str:
    runtime_id = getattr(card, "runtime_card_id", None)
    if runtime_id:
        return str(runtime_id)
    return str(getattr(card, "card_id", ""))


def _card_options(cards: list[CardInstance]) -> list[dict[str, Any]]:
    return [
        {
            "label": _card_choice_label(card),
            "card_id": card.card_id,
            "upgraded": bool(getattr(card, "upgraded", False)),
            "uuid": str(card.uuid),
        }
        for card in cards
    ]


def _find_card_by_uuid(cards: list[CardInstance], target_uuid: str | None) -> CardInstance | None:
    if not target_uuid:
        return None
    for card in cards:
        if str(getattr(card, "uuid", "")) == str(target_uuid):
            return card
    return None


def _add_card_to_hand_or_discard(
    card_manager: Any,
    card: CardInstance,
    *,
    hand_limit_offset: int = 0,
) -> str:
    if card_manager is None:
        return "discard"
    if getattr(card_manager, "_combat_state", None) is not None:
        card._combat_state = card_manager._combat_state
    if card_manager._can_add_to_hand(hand_limit_offset=hand_limit_offset):
        card_manager.hand.add(card)
        if hasattr(card_manager, "_check_normality_in_hand"):
            card_manager._check_normality_in_hand()
        return "hand"
    card_manager.discard_pile.add(card)
    return "discard"


def _apply_master_reality_if_needed(card_manager: Any, card: CardInstance) -> None:
    should_upgrade = bool(getattr(card_manager, "_should_upgrade_generated_card", lambda _: False)(card))
    if should_upgrade and not getattr(card, "upgraded", False):
        card.upgrade()


def _open_generated_single_pick(
    combat_state: Any,
    source_card: CardInstance,
    *,
    choice_type: str,
    generated_cards: list[CardInstance],
    selection_action: str,
) -> None:
    combat_state.pending_combat_choice = {
        "source_card_id": source_card.card_id,
        "choice_type": choice_type,
        "selection_action": selection_action,
        "resolved": False,
        "generated_cards": generated_cards,
        "options": _card_options(generated_cards),
    }


def _open_draw_pile_single_pick(
    combat_state: Any,
    source_card: CardInstance,
    *,
    choice_type: str,
    selection_action: str,
    candidate_cards: list[CardInstance],
) -> None:
    combat_state.pending_combat_choice = {
        "source_card_id": source_card.card_id,
        "choice_type": choice_type,
        "selection_action": selection_action,
        "resolved": False,
        "candidate_uuids": [str(card.uuid) for card in candidate_cards],
        "options": _card_options(candidate_cards),
    }


def _open_hand_single_pick(
    combat_state: Any,
    source_card: CardInstance,
    *,
    choice_type: str,
    selection_action: str,
    candidate_cards: list[CardInstance],
) -> None:
    combat_state.pending_combat_choice = {
        "source_card_id": source_card.card_id,
        "choice_type": choice_type,
        "selection_action": selection_action,
        "resolved": False,
        "candidate_uuids": [str(card.uuid) for card in candidate_cards],
        "options": _card_options(candidate_cards),
    }


def _refresh_hand_multi_pick_options(combat_state: Any, pending: dict[str, Any]) -> list[dict[str, Any]]:
    card_manager = getattr(combat_state, "card_manager", None)
    if card_manager is None:
        pending["options"] = []
        return []
    remaining_uuids = {str(uuid) for uuid in pending.get("candidate_uuids", [])}
    remaining_cards = [
        hand_card
        for hand_card in getattr(card_manager.hand, "cards", []) or []
        if str(getattr(hand_card, "uuid", "")) in remaining_uuids
    ]
    options = _card_options(remaining_cards)
    options.append({"label": "完成", "action": "complete"})
    options.append({"label": "跳过", "action": "skip"})
    pending["options"] = options
    return options


def _open_hand_multi_pick(
    combat_state: Any,
    source_card: CardInstance,
    *,
    choice_type: str,
    selection_action: str,
    candidate_cards: list[CardInstance],
    max_picks: int,
) -> None:
    pending = {
        "source_card_id": source_card.card_id,
        "choice_type": choice_type,
        "selection_action": selection_action,
        "resolved": False,
        "candidate_uuids": [str(card.uuid) for card in candidate_cards],
        "selected_count": 0,
        "max_picks": max(0, int(max_picks)),
    }
    _refresh_hand_multi_pick_options(combat_state, pending)
    combat_state.pending_combat_choice = pending


def _resolve_discovery_choice(combat_state: Any, selected_card: CardInstance, *, source_card: CardInstance | None = None) -> None:
    card_manager = getattr(combat_state, "card_manager", None)
    if card_manager is None:
        return
    hand_limit_offset = _hand_limit_offset_for_played_card(card_manager, source_card) if source_card is not None else 0
    chosen_copy = selected_card.make_stat_equivalent_copy()
    _apply_master_reality_if_needed(card_manager, chosen_copy)
    chosen_copy.cost_for_turn = 0
    chosen_copy.is_cost_modified_for_turn = True
    _add_card_to_hand_or_discard(card_manager, chosen_copy, hand_limit_offset=hand_limit_offset)


def _resolve_generated_choice_to_hand(
    combat_state: Any,
    selected_card: CardInstance,
    *,
    source_card: CardInstance | None = None,
    zero_cost_this_turn: bool = False,
) -> None:
    card_manager = getattr(combat_state, "card_manager", None)
    if card_manager is None:
        return
    hand_limit_offset = _hand_limit_offset_for_played_card(card_manager, source_card) if source_card is not None else 0
    chosen_copy = selected_card.make_stat_equivalent_copy()
    _apply_master_reality_if_needed(card_manager, chosen_copy)
    if zero_cost_this_turn and int(getattr(chosen_copy, "cost", -1) or -1) > 0:
        chosen_copy.cost_for_turn = 0
        chosen_copy.is_cost_modified_for_turn = True
    _add_card_to_hand_or_discard(card_manager, chosen_copy, hand_limit_offset=hand_limit_offset)


def _resolve_draw_pile_card_to_hand_or_discard(
    combat_state: Any,
    selected_card: CardInstance,
    *,
    source_card: CardInstance | None = None,
) -> None:
    card_manager = getattr(combat_state, "card_manager", None)
    if card_manager is None:
        return
    if not card_manager.draw_pile.remove(selected_card):
        return
    hand_limit_offset = _hand_limit_offset_for_played_card(card_manager, source_card) if source_card is not None else 0
    _add_card_to_hand_or_discard(card_manager, selected_card, hand_limit_offset=hand_limit_offset)


def _move_selected_hand_card_to_draw_pile(
    combat_state: Any,
    selected_card: CardInstance,
    *,
    to_top: bool,
    grant_free_to_play_once: bool = False,
) -> None:
    card_manager = getattr(combat_state, "card_manager", None)
    if card_manager is None:
        return
    if not card_manager.hand.remove(selected_card):
        return
    if grant_free_to_play_once and int(getattr(selected_card, "cost", -1) or -1) > 0:
        selected_card.free_to_play_once = True
    if to_top:
        card_manager.draw_pile.add(selected_card)
    else:
        card_manager.draw_pile.cards.insert(0, selected_card)
    if hasattr(card_manager, "_check_normality_in_hand"):
        card_manager._check_normality_in_hand()


def _trigger_player_attack_damage_hooks(
    combat_state: Any,
    source: Any,
    target: Any,
    actual_damage: int,
    *,
    damage_type: str = "NORMAL",
) -> None:
    if source is None or target is None or actual_damage <= 0:
        return
    powers = getattr(source, "powers", None)
    if powers is None or not hasattr(powers, "on_player_attack_damage"):
        return
    powers.on_player_attack_damage(source, target, actual_damage, damage_type=damage_type)


def _generate_random_power_cards_to_hand(
    combat_state: Any,
    count: int,
    *,
    hand_limit_offset: int = 0,
    zero_cost_for_turn: bool = False,
) -> list[str]:
    card_manager = getattr(combat_state, "card_manager", None)
    if card_manager is None or count <= 0:
        return []
    generated_ids: list[str] = []
    for _ in range(count):
        selected_card_id = _choose_random_implemented_power_card_id(combat_state)
        if not selected_card_id:
            break

        def _configure_generated_power(new_card: CardInstance) -> None:
            if zero_cost_for_turn:
                new_card.cost_for_turn = 0
                new_card.is_cost_modified_for_turn = True

        configure_card = _configure_generated_power if zero_cost_for_turn else None
        card_manager.generate_cards_to_hand(
            selected_card_id,
            1,
            hand_limit_offset=hand_limit_offset,
            configure_card=configure_card,
        )
        generated_ids.append(selected_card_id)
    return generated_ids


def _generate_random_defect_common_cards_to_hand(
    combat_state: Any,
    count: int,
    *,
    hand_limit_offset: int = 0,
) -> list[str]:
    card_manager = getattr(combat_state, "card_manager", None)
    if card_manager is None or count <= 0:
        return []
    generated_ids: list[str] = []
    for _ in range(count):
        selected_card_id = _choose_random_implemented_defect_common_card_id(combat_state)
        if not selected_card_id:
            break
        card_manager.generate_cards_to_hand(
            selected_card_id,
            1,
            hand_limit_offset=hand_limit_offset,
        )
        generated_ids.append(selected_card_id)
    return generated_ids


def _random_orb_instance(combat_state: Any):
    from sts_py.engine.combat.orbs import DarkOrb, FrostOrb, LightningOrb, PlasmaOrb

    orb_classes = [LightningOrb, FrostOrb, DarkOrb, PlasmaOrb]
    rng = _combat_rng(combat_state)
    if rng is not None and len(orb_classes) > 1:
        return orb_classes[rng.random_int(len(orb_classes) - 1)]()
    return orb_classes[0]()


def _apply_temporary_strength_down_to_monster(monster: MonsterBase, amount: int) -> None:
    if amount <= 0 or monster.is_dead():
        return
    if monster.has_power("Artifact"):
        monster.powers.reduce_power("Artifact", 1)
        return
    monster.strength -= amount
    monster.add_power(create_power("Lose Strength", amount, monster.id))


class DamageType(Enum):
    NORMAL = auto()
    THORNS = auto()
    HP_LOSS = auto()


class AttackEffect(Enum):
    NONE = auto()
    SLASH_DIAGONAL = auto()
    SLASH_HEAVY = auto()
    SLASH_HORIZONTAL = auto()
    BLUNT_HEAVY = auto()
    BLUNT_LIGHT = auto()
    FIRE = auto()
    POISON = auto()


class CardEffect(Protocol):
    """Protocol for card effects that can be executed."""
    
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        """Execute this effect and return any follow-up effects."""
        ...


@dataclass
class DealDamageEffect:
    """Deal damage to a target monster."""
    target_idx: int
    damage: int
    damage_type: DamageType = DamageType.NORMAL
    attack_effect: AttackEffect = AttackEffect.SLASH_DIAGONAL
    
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        
        actual_damage = monster.take_damage(self.damage)
        card._last_damage_dealt = actual_damage
        source._last_damage_dealt = actual_damage
        _trigger_player_attack_damage_hooks(
            combat_state,
            source,
            monster,
            actual_damage,
            damage_type=self.damage_type.name if hasattr(self.damage_type, "name") else "NORMAL",
        )
        return []


@dataclass
class DealDamageAllEffect:
    """Deal damage to all monsters.

    Follows Java multi-damage calculation:
    1. Player modifiers (Strength, etc.) are applied ONCE to base damage
    2. Apply stance atDamageGive (Wrath +50%, Divinity +50%)
    3. The resulting damage is applied to each monster
    4. Each monster's individual atDamageReceive modifiers (Vulnerable, etc.) are applied
    """
    damage: int
    damage_type: DamageType = DamageType.NORMAL
    attack_effect: AttackEffect = AttackEffect.SLASH_DIAGONAL

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        effects = []
        tmp = float(self.damage)

        if hasattr(source, 'strength') and source.strength != 0:
            tmp += source.strength

        if hasattr(source, 'powers'):
            tmp = source.powers.apply_damage_modifiers(tmp, self.damage_type.value if hasattr(self.damage_type, 'value') else "NORMAL")

        if hasattr(source, 'stance') and source.stance is not None:
            tmp = source.stance.at_damage_give(tmp, self.damage_type.value if hasattr(self.damage_type, 'value') else "NORMAL")

        if hasattr(source, 'powers'):
            tmp = source.powers.apply_damage_final_give_modifiers(tmp, self.damage_type.value if hasattr(self.damage_type, 'value') else "NORMAL")

        for i, monster in enumerate(combat_state.monsters):
            if not monster.is_dead():
                final_damage = tmp
                if hasattr(monster, 'vulnerable') and monster.vulnerable > 0:
                    final_damage *= 1.5
                if hasattr(monster, 'powers'):
                    final_damage = monster.powers.apply_damage_receive_modifiers(final_damage, self.damage_type.value if hasattr(self.damage_type, 'value') else "NORMAL")
                    final_damage = monster.powers.apply_damage_final_receive_modifiers(final_damage, self.damage_type.value if hasattr(self.damage_type, 'value') else "NORMAL")
                final_damage = max(0, int(final_damage))
                actual_damage = monster.take_damage(final_damage)
                _trigger_player_attack_damage_hooks(
                    combat_state,
                    source,
                    monster,
                    actual_damage,
                    damage_type=self.damage_type.name if hasattr(self.damage_type, "name") else "NORMAL",
                )
        return effects


@dataclass
class GainBlockEffect:
    """Gain block for the player."""
    amount: int
    
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        source.gain_block(self.amount)
        return []


@dataclass
class ApplyPowerEffect:
    """Apply a power to a creature."""
    power_type: str
    amount: int
    target_type: str  # "player", "monster", "all_monsters"
    target_idx: int = 0
    
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if self.target_type == "player":
            self._apply_to_player(source)
        elif self.target_type == "monster" and target is not None:
            self._apply_to_monster(target, source)
        elif self.target_type == "all_monsters":
            for monster in combat_state.monsters:
                if not monster.is_dead():
                    self._apply_to_monster(monster, source)
        return []
    
    def _apply_to_player(self, player: Player) -> None:
        from sts_py.engine.combat.powers import create_power
        if self.power_type in ["Strength", "Dexterity", "DemonForm", "Enrage", "Evolve", "FeelNoPain", "DarkEmbrace", "Thorns", "Regen", "Metallicize", "Combust", "FireBreathing", "BattleHymn", "Vulnerable", "DoubleTap", "Juggernaut", "Rage", "Rupture", "Brutality", "Corruption", "NoDraw", "NoBlock", "DevaPower", "Devotion", "Study", "MasterReality", "OmegaPower", "Foresight", "LikeWater", "Nirvana", "Rushdown", "EndTurnDeath", "NoxiousFumes", "InfiniteBlades", "Accuracy", "ThousandCuts", "AfterImage", "Blur", "Focus", "Artifact", "Buffer", "Loop", "Rebound", "CreativeAI", "Amplify", "Burst", "EchoForm", "Electro", "StaticDischarge", "Bias", "Storm", "Heatsinks", "MachineLearning", "Hello", "Repair", "Energized", "EnergizedBlue", "Equilibrium", "Tools Of The Trade", "Retain Cards", "WraithForm", "Intangible", "Draw Card", "Next Turn Block", "Envenom", "Phantasmal", "Magnetism", "Mayhem", "Panache", "Sadistic", "Collect", "Discipline", "Establishment", "Fasting", "MentalFortress", "SimmeringFury", "Swivel", "WaveOfTheHand", "WreathOfFlame"]:
            if self.power_type == "DemonForm": name = "DemonForm"
            elif self.power_type == "FeelNoPain": name = "FeelNoPain"
            elif self.power_type == "DarkEmbrace": name = "DarkEmbrace"
            elif self.power_type == "FireBreathing": name = "FireBreathing"
            elif self.power_type == "BattleHymn": name = "BattleHymn"
            elif self.power_type == "DoubleTap": name = "DoubleTap"
            elif self.power_type == "NoDraw": name = "No Draw"
            elif self.power_type == "NoBlock": name = "NoBlock"
            else: name = self.power_type
            player.add_power(create_power(name, self.amount, "player"))
            if self.power_type == "Strength": player.strength += self.amount
            if self.power_type == "Dexterity" and hasattr(player, 'dexterity'): player.dexterity += self.amount
            if self.power_type == "Blur": player.blur_active = True
            if self.power_type == "Focus" and hasattr(player, 'focus'): player.focus += self.amount
        elif self.power_type == "Flex":
            # Flex: gain temporary strength (removed at end of turn)
            player.add_power(create_power("Strength", self.amount, "player"))
            player.strength += self.amount
            # Track how much Flex strength to remove at end of turn
            if not hasattr(player, '_flex_amount'):
                player._flex_amount = 0
            player._flex_amount += self.amount
        elif self.power_type == "StrengthDouble":
            current_str = max(0, int(getattr(player, "strength", 0) or 0))
            if current_str > 0:
                player.add_power(create_power("Strength", current_str, "player"))
                player.strength += current_str
        elif self.power_type == "Energized":
            player.energy += self.amount
        elif self.power_type == "Draw":
            pass
    
    def _apply_to_monster(self, monster: MonsterBase, source: Player | None = None) -> None:
        if self.power_type in {"Vulnerable", "Weak", "Strength", "StrengthDown", "Lockon"}:
            _apply_power_to_enemy_from_player(source, monster, self.power_type, self.amount)
        elif self.power_type in {"TalkToTheHand", "Mark"}:
            _apply_power_to_enemy_from_player(source, monster, self.power_type, self.amount)


@dataclass
class DrawCardsEffect:
    """Draw cards from draw pile."""
    count: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if combat_state.card_manager is not None:
            combat_state.card_manager.draw_cards(
                self.count,
                hand_limit_offset=_hand_limit_offset_for_played_card(combat_state.card_manager, card),
            )
        return []


@dataclass
class MadnessEffect:
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return []

        preferred_candidates = [
            hand_card
            for _, hand_card in _hand_cards_excluding_played(card_manager, card)
            if int(getattr(hand_card, "cost_for_turn", getattr(hand_card, "cost", -1)) or -1) > 0
        ]
        fallback_candidates = [
            hand_card
            for _, hand_card in _hand_cards_excluding_played(card_manager, card)
            if int(getattr(hand_card, "cost", -1) or -1) > 0
        ]
        candidates = preferred_candidates or fallback_candidates
        if not candidates:
            return []

        rng = _card_manager_rng(card_manager)
        if rng is not None and len(candidates) > 1:
            chosen = candidates[rng.random_int(len(candidates) - 1)]
        else:
            chosen = candidates[0]

        chosen.cost = 0
        chosen.cost_for_turn = 0
        chosen.is_cost_modified = True
        chosen.is_cost_modified_for_turn = True
        return []


@dataclass
class DeepBreathEffect:
    draw_count: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return []
        if not card_manager.discard_pile.is_empty():
            card_manager._shuffle_discard_into_draw(card_manager.rng)
        card_manager.draw_cards(
            self.draw_count,
            hand_limit_offset=_hand_limit_offset_for_played_card(card_manager, card),
        )
        return []


@dataclass
class ApotheosisEffect:
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return []

        for pile in (
            card_manager.hand.cards,
            card_manager.draw_pile.cards,
            card_manager.discard_pile.cards,
            card_manager.exhaust_pile.cards,
        ):
            for upgrade_candidate in pile:
                if upgrade_candidate is card:
                    continue
                if getattr(upgrade_candidate, "times_upgraded", 0) > 0:
                    continue
                if upgrade_candidate.card_type in {CardType.CURSE, CardType.STATUS}:
                    continue
                upgrade_candidate.upgrade()
                if hasattr(upgrade_candidate, "apply_powers"):
                    upgrade_candidate.apply_powers(combat_state)

        if hasattr(card_manager, "refresh_hand_costs_for_current_state"):
            card_manager.refresh_hand_costs_for_current_state()
        return []


@dataclass
class HandOfGreedEffect:
    target_idx: int
    damage: int
    gold_gain: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        monster.take_damage(self.damage)
        if _is_true_kill_reward_target(monster):
            combat_state.pending_bonus_gold += self.gold_gain
        return []


@dataclass
class RitualDaggerEffect:
    target_idx: int
    damage: int
    growth: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        actual_damage = monster.take_damage(self.damage)
        card._last_damage_dealt = actual_damage
        source._last_damage_dealt = actual_damage
        _trigger_player_attack_damage_hooks(combat_state, source, monster, actual_damage, damage_type="NORMAL")
        if _is_true_kill_reward_target(monster):
            _apply_ritual_dagger_growth(card, combat_state, self.growth)
        return []


@dataclass
class EnlightenmentEffect:
    permanent_for_combat: bool = False

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return []
        for hand_card in getattr(card_manager.hand, "cards", []) or []:
            if hand_card is card:
                continue
            if int(getattr(hand_card, "cost_for_turn", getattr(hand_card, "cost", -1)) or -1) > 1:
                hand_card.cost_for_turn = 1
                hand_card.is_cost_modified_for_turn = True
            if self.permanent_for_combat and int(getattr(hand_card, "cost", -1) or -1) > 1:
                hand_card.cost = 1
                hand_card.is_cost_modified = True
        return []


@dataclass
class ConditionalNoAttackDrawEffect:
    draw_count: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return []
        if any(hand_card.card_type == CardType.ATTACK for _, hand_card in _hand_cards_excluding_played(card_manager, card)):
            return []
        card_manager.draw_cards(
            self.draw_count,
            hand_limit_offset=_hand_limit_offset_for_played_card(card_manager, card),
        )
        return []


@dataclass
class DiscoveryEffect:
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        pool = list(_implemented_colored_discovery_card_ids())
        if not pool:
            return []
        rng = _combat_rng(combat_state)
        candidate_ids: list[str] = []
        available = pool[:]
        while available and len(candidate_ids) < 3:
            selected_index = rng.random_int(len(available) - 1) if rng is not None and len(available) > 1 else 0
            candidate_ids.append(available.pop(selected_index))
        generated_cards = [CardInstance(card_id) for card_id in candidate_ids]
        if len(generated_cards) == 1:
            _resolve_discovery_choice(combat_state, generated_cards[0], source_card=card)
            return []
        _open_generated_single_pick(
            combat_state,
            card,
            choice_type="generated_single_pick",
            generated_cards=generated_cards,
            selection_action="discovery",
        )
        return []


@dataclass
class ForethoughtEffect:
    allow_multiple: bool = False

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return []
        candidate_cards = [hand_card for _, hand_card in _hand_cards_excluding_played(card_manager, card)]
        if not candidate_cards:
            return []
        if not self.allow_multiple:
            if len(candidate_cards) == 1:
                _move_selected_hand_card_to_draw_pile(
                    combat_state,
                    candidate_cards[0],
                    to_top=False,
                    grant_free_to_play_once=True,
                )
                return []
            _open_hand_single_pick(
                combat_state,
                card,
                choice_type="hand_single_pick",
                selection_action="forethought",
                candidate_cards=candidate_cards,
            )
            return []
        _open_hand_multi_pick(
            combat_state,
            card,
            choice_type="hand_multi_pick_up_to_n",
            selection_action="forethought",
            candidate_cards=candidate_cards,
            max_picks=len(candidate_cards),
        )
        return []


@dataclass
class PurityEffect:
    max_exhaust: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return []
        candidate_cards = [hand_card for _, hand_card in _hand_cards_excluding_played(card_manager, card)]
        if not candidate_cards or self.max_exhaust <= 0:
            return []
        _open_hand_multi_pick(
            combat_state,
            card,
            choice_type="hand_multi_pick_up_to_n",
            selection_action="purity",
            candidate_cards=candidate_cards,
            max_picks=min(self.max_exhaust, len(candidate_cards)),
        )
        return []


@dataclass
class DrawPileTutorEffect:
    card_type: CardType
    selection_action: str

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return []
        candidate_cards = [
            draw_card
            for draw_card in getattr(card_manager.draw_pile, "cards", []) or []
            if getattr(draw_card, "card_type", None) == self.card_type
        ]
        if not candidate_cards:
            return []
        if len(candidate_cards) == 1:
            _resolve_draw_pile_card_to_hand_or_discard(combat_state, candidate_cards[0], source_card=card)
            return []
        _open_draw_pile_single_pick(
            combat_state,
            card,
            choice_type="draw_pile_single_pick",
            selection_action=self.selection_action,
            candidate_cards=candidate_cards,
        )
        return []


@dataclass
class ThinkingAheadEffect:
    draw_count: int = 2

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return []
        card_manager.draw_cards(
            self.draw_count,
            hand_limit_offset=_hand_limit_offset_for_played_card(card_manager, card),
        )
        candidate_cards = [hand_card for _, hand_card in _hand_cards_excluding_played(card_manager, card)]
        if not candidate_cards:
            return []
        if len(candidate_cards) == 1:
            _move_selected_hand_card_to_draw_pile(
                combat_state,
                candidate_cards[0],
                to_top=True,
                grant_free_to_play_once=False,
            )
            return []
        _open_hand_single_pick(
            combat_state,
            card,
            choice_type="hand_single_pick",
            selection_action="thinking_ahead",
            candidate_cards=candidate_cards,
        )
        return []


@dataclass
class DrawCardsTrackedEffect:
    """Draw cards and remember which cards actually entered hand."""
    count: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None or self.count <= 0:
            card._last_drawn_cards = []
            return []
        drawn_cards: list[CardInstance] = []
        for _ in range(self.count):
            drawn_card = card_manager.draw_card(
                card_manager.rng,
                hand_limit_offset=_hand_limit_offset_for_played_card(card_manager, card),
            )
            if drawn_card is None:
                break
            drawn_cards.append(drawn_card)
        card._last_drawn_cards = drawn_cards
        return []


@dataclass
class DrawToHandLimitEffect:
    """Draw cards until the hand reaches its maximum size."""

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if combat_state.card_manager is not None:
            combat_state.card_manager.draw_to_hand_limit(
                hand_limit_offset=_hand_limit_offset_for_played_card(combat_state.card_manager, card),
            )
        return []


@dataclass
class DrawToHandCountEffect:
    """Draw until the hand reaches the requested count."""
    count: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if combat_state.card_manager is not None:
            combat_state.card_manager.draw_to_hand_count(
                self.count,
                hand_limit_offset=_hand_limit_offset_for_played_card(combat_state.card_manager, card),
            )
        return []


@dataclass
class DistractionEffect:
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return []
        selected_card_id = _choose_random_implemented_silent_skill_card_id(combat_state)
        if not selected_card_id:
            return []

        def _configure_generated_skill(new_card: CardInstance) -> None:
            new_card.cost_for_turn = 0
            new_card.is_cost_modified_for_turn = True

        card_manager.generate_cards_to_hand(
            selected_card_id,
            1,
            hand_limit_offset=_hand_limit_offset_for_played_card(card_manager, card),
            configure_card=_configure_generated_skill,
        )
        return []


@dataclass
class EscapePlanEffect:
    block_amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        DrawCardsTrackedEffect(count=1).execute(combat_state, card, source, target)
        drawn_cards = list(getattr(card, "_last_drawn_cards", []) or [])
        if len(drawn_cards) != 1:
            return []
        if getattr(drawn_cards[0], "card_type", None) != CardType.SKILL:
            source.gain_block(self.block_amount)
        return []


@dataclass
class BulletTimeEffect:
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        source.add_power(create_power("No Draw", 1, "player"))
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return []
        for hand_card in list(card_manager.hand.cards):
            if hand_card is card:
                continue
            card_cost = int(getattr(hand_card, "cost", -1) or -1)
            if card_cost < 0:
                continue
            hand_card.cost_for_turn = 0
            hand_card.is_cost_modified_for_turn = True
        return []


@dataclass
class SetupEffect:
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return []
        hand_index = _select_first_hand_card_index(card_manager, card)
        if hand_index is None:
            return []
        selected_card = card_manager.hand.pop(hand_index)
        if selected_card is None:
            return []
        selected_card.cost_for_turn = 0
        selected_card.is_cost_modified_for_turn = True
        card_manager.draw_pile.add(selected_card)
        if hasattr(card_manager, "_check_normality_in_hand"):
            card_manager._check_normality_in_hand()
        return []


@dataclass
class ChokeAttackEffect:
    target_idx: int
    damage: int
    choke_amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        actual_damage = monster.take_damage(self.damage)
        _trigger_player_attack_damage_hooks(combat_state, source, monster, actual_damage, damage_type="NORMAL")
        monster.add_power(create_power("Choked", self.choke_amount, monster.id))
        return []


@dataclass
class NightmareEffect:
    copies: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return []
        hand_index = _select_first_hand_card_index(card_manager, card)
        if hand_index is None:
            return []
        selected_card = card_manager.hand.cards[hand_index]
        power = create_power("Nightmare", self.copies, "player")
        setattr(power, "stored_card", selected_card.make_stat_equivalent_copy())
        source.add_power(power)
        return []


@dataclass
class DoppelgangerEffect:
    upgraded: bool = False

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        resolved_x_cost = max(0, int(getattr(card, "_resolved_x_cost", 0) or 0))
        amount = resolved_x_cost + (1 if self.upgraded else 0)
        if amount > 0:
            power = create_power("Doppelganger", amount, "player")
            if hasattr(power, "draw_amount"):
                power.draw_amount = amount
            source.add_power(power)
        combat_state._end_player_turn_requested = True
        return []


@dataclass
class SkewerEffect:
    target_idx: int
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        resolved_x_cost = max(0, int(getattr(card, "_resolved_x_cost", 0) or 0))
        for _ in range(resolved_x_cost):
            if monster.is_dead():
                break
            actual_damage = monster.take_damage(self.damage)
            _trigger_player_attack_damage_hooks(combat_state, source, monster, actual_damage, damage_type="NORMAL")
        return []


@dataclass
class StormOfSteelEffect:
    upgraded: bool = False

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return []
        discarded_cards = [hand_card for hand_card in list(card_manager.hand.cards) if hand_card is not card]
        discard_count = 0
        for discard_card in discarded_cards:
            if discard_card in card_manager.hand.cards:
                hand_index = card_manager.hand.cards.index(discard_card)
                _move_hand_card_to_discard(card_manager, hand_index=hand_index)
                discard_count += 1
        if discard_count <= 0:
            return []

        def _configure_shiv(new_card: CardInstance) -> None:
            if self.upgraded:
                new_card.upgrade()

        card_manager.generate_cards_to_hand(
            "Shiv",
            discard_count,
            hand_limit_offset=_hand_limit_offset_for_played_card(card_manager, card),
            configure_card=_configure_shiv if self.upgraded else None,
        )
        return []


@dataclass
class AlchemizeEffect:
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        run_engine = getattr(combat_state, "run_engine", None)
        if run_engine is None:
            return []
        potion_rng = getattr(getattr(run_engine.state, "rng", None), "potion_rng", None)
        if potion_rng is None:
            return []
        from sts_py.engine.content.potions import get_common_potions, get_uncommon_potions, get_rare_potions

        character_class = getattr(run_engine.state, "character_class", "IRONCLAD")
        common_potions = get_common_potions(character_class)
        uncommon_potions = get_uncommon_potions(character_class)
        rare_potions = get_rare_potions(character_class)
        roll = potion_rng.random_int(99)
        selected = None
        if roll < 65 and common_potions:
            selected = common_potions[potion_rng.random_int(len(common_potions) - 1)]
        elif roll < 90 and uncommon_potions:
            selected = uncommon_potions[potion_rng.random_int(len(uncommon_potions) - 1)]
        elif rare_potions:
            selected = rare_potions[potion_rng.random_int(len(rare_potions) - 1)]
        if selected is None:
            return []
        run_engine.gain_potion(selected.potion_id)
        return []


@dataclass
class OpenCombatChoiceEffect:
    """Open a narrow combat choice flow for cards like Wish."""
    choice_type: str

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if self.choice_type == "wish":
            combat_state.pending_combat_choice = {
                "source_card_id": card.card_id,
                "choice_type": self.choice_type,
                "resolved": False,
                "options": [
                    {"label": "Wish for Strength", "effect": "strength", "amount": card.damage},
                    {"label": "Wish for Plated Armor", "effect": "plated_armor", "amount": card.block},
                    {"label": "Wish for Riches", "effect": "gold", "amount": card.magic_number},
                ],
            }
        elif self.choice_type == "omniscience":
            card_manager = combat_state.card_manager
            if card_manager is None or card_manager.draw_pile.is_empty():
                return []
            combat_state.pending_combat_choice = {
                "source_card_id": card.card_id,
                "choice_type": self.choice_type,
                "resolved": False,
                "play_count": card.magic_number,
                "options": [
                    {
                        "label": _card_choice_label(draw_card),
                        "effect": "play_draw_pile_card",
                        "card_id": draw_card.card_id,
                        "upgraded": draw_card.upgraded,
                        "uuid": str(draw_card.uuid),
                    }
                    for draw_card in card_manager.draw_pile.cards
                ],
            }
        return []


@dataclass
class ScryEffect:
    """Scry the top cards of the draw pile with deterministic auto-choice."""
    count: int
    shuffle_if_empty: bool = False

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if combat_state.card_manager is not None:
            combat_state.card_manager.resolve_scry(
                self.count,
                shuffle_if_empty=self.shuffle_if_empty,
                hand_limit_offset=_hand_limit_offset_for_played_card(combat_state.card_manager, card),
            )
        return []


@dataclass
class DealDamageToRandomEffect:
    """Deal damage to a random monster."""
    damage: int
    damage_type: DamageType = DamageType.NORMAL
    attack_effect: AttackEffect = AttackEffect.SLASH_DIAGONAL

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        alive_monsters = [m for m in combat_state.monsters if not m.is_dead()]
        if not alive_monsters:
            return []
        # Use seeded RNG from combat_state instead of stdlib random
        if combat_state.card_manager is not None and hasattr(combat_state.card_manager, 'rng') and combat_state.card_manager.rng is not None:
            idx = combat_state.card_manager.rng.random_int(len(alive_monsters) - 1)
        else:
            import random
            idx = random.randint(0, len(alive_monsters) - 1)
        target_monster = alive_monsters[idx]
        actual_damage = target_monster.take_damage(self.damage)
        _trigger_player_attack_damage_hooks(
            combat_state,
            source,
            target_monster,
            actual_damage,
            damage_type=self.damage_type.name if hasattr(self.damage_type, "name") else "NORMAL",
        )
        return []


@dataclass
class SetBlockFlagEffect:
    """Set a block-related flag on the player."""
    flag: str
    value: bool

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if self.flag == "barricade":
            source.barricade_active = self.value
        elif self.flag == "blur":
            source.blur_active = self.value
        return []


@dataclass
class GainEnergyEffect:
    """Gain energy for this turn."""
    amount: int
    
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        source.energy += self.amount
        if combat_state.card_manager is not None:
            combat_state.card_manager.set_energy(source.energy)
        return []


@dataclass
class GainMantraEffect:
    """Gain Mantra and trigger Divinity when reaching the threshold."""
    amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        gain_mantra(source, self.amount)
        if combat_state.card_manager is not None:
            combat_state.card_manager.set_energy(source.energy)
        return []


@dataclass
class GainBlockFromLastDamageEffect:
    """Gain block equal to the last damage this card actually dealt."""

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        amount = max(0, int(getattr(card, "_last_damage_dealt", 0)))
        if amount > 0:
            source.gain_block(amount)
        return []


@dataclass
class MakeTempCardInDrawPileEffect:
    """Create real temporary cards in the draw pile using generated-card helpers."""
    card_id: str
    count: int
    shuffle_into: bool = True
    configure_card: Any = None

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if combat_state.card_manager is not None:
            combat_state.card_manager.generate_cards_to_draw_pile(
                self.card_id,
                self.count,
                shuffle_into=self.shuffle_into,
                configure_card=self.configure_card,
            )
        return []


@dataclass
class MakeTempCardInDiscardEffect:
    """Create real temporary cards in discard pile using generated-card helpers."""
    card_id: str
    count: int
    configure_card: Any = None

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None or self.count <= 0:
            return []
        for _ in range(self.count):
            generated = card_manager._make_generated_card(self.card_id, configure_card=self.configure_card)
            card_manager.discard_pile.add(generated)
        return []


@dataclass
class RebootEffect:
    draw_count: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return []
        card_manager.shuffle_hand_and_discard_into_draw_excluding(card)
        card_manager.draw_cards(
            self.draw_count,
            hand_limit_offset=_hand_limit_offset_for_played_card(card_manager, card),
        )
        return []


@dataclass
class RecoverFromDiscardEffect:
    """Recover cards from discard pile using deterministic auto-choice."""
    count: int
    temporary_retain: bool = True

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if combat_state.card_manager is not None:
            combat_state.card_manager.recover_from_discard(
                self.count,
                hand_limit_offset=_hand_limit_offset_for_played_card(combat_state.card_manager, card),
                temporary_retain=self.temporary_retain,
            )
        return []


@dataclass
class RecoverAllDiscardZeroCostEffect:
    """Recover every discard card whose base cost is zero."""

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if combat_state.card_manager is not None:
            combat_state.card_manager.recover_all_zero_cost_from_discard(
                hand_limit_offset=_hand_limit_offset_for_played_card(combat_state.card_manager, card),
            )
        return []


@dataclass
class MoveDrawPileTopToHandEffect:
    """Move cards from the top of the draw pile directly into hand."""
    count: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if combat_state.card_manager is not None:
            combat_state.card_manager.move_draw_pile_top_to_hand(
                self.count,
                hand_limit_offset=_hand_limit_offset_for_played_card(combat_state.card_manager, card),
            )
        return []


@dataclass
class ChangeStanceEffect:
    """Change the player's stance and apply stance-exit side effects."""
    stance_type: StanceType

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        old_stance = getattr(source, "stance", None)
        exit_effects = change_stance(source, self.stance_type)
        new_stance = getattr(source, "stance", None)
        if exit_effects.get("energy"):
            source.energy += int(exit_effects["energy"])
        if old_stance is not None and new_stance is not None and old_stance.stance_type != new_stance.stance_type:
            source.powers.on_change_stance(source, old_stance, new_stance)
        if combat_state.card_manager is not None:
            combat_state.card_manager.set_energy(source.energy)
        return []


@dataclass
class EndTurnEffect:
    """Request that the current player turn end after card resolution."""

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        combat_state._end_player_turn_requested = True
        return []


@dataclass
class SkipEnemyTurnEffect:
    """Skip the upcoming enemy turn and proceed to the next player turn."""

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        combat_state._skip_next_enemy_turn = True
        return []


@dataclass
class InnerPeaceEffect:
    """If in Calm, draw cards; otherwise enter Calm."""
    draw_count: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        current_stance = getattr(getattr(source, "stance", None), "stance_type", None)
        if current_stance == StanceType.CALM:
            if combat_state.card_manager is not None:
                combat_state.card_manager.draw_cards(
                    self.draw_count,
                    hand_limit_offset=_hand_limit_offset_for_played_card(combat_state.card_manager, card),
                )
        else:
            change_stance(source, StanceType.CALM)
        return []


@dataclass
class ExpungerEffect:
    """Deal damage to the chosen monster multiple times."""
    damage: int
    hit_count: int
    target_idx: int | None = None

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if self.hit_count <= 0 or self.damage <= 0:
            return []
        if target is None:
            if self.target_idx is None or self.target_idx >= len(combat_state.monsters):
                return []
            target = combat_state.monsters[self.target_idx]
        for _ in range(self.hit_count):
            if target.is_dead():
                break
            target.take_damage(self.damage)
        return []


@dataclass
class ConjureBladeEffect:
    """Generate an Expunger whose X matches the resolved effect value."""

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if combat_state.card_manager is None:
            return []

        effect_x_cost = max(0, int(getattr(card, "_resolved_x_cost", 0) or 0))
        if card.upgraded:
            effect_x_cost += 1

        def _configure_expunger(generated_card: CardInstance) -> None:
            generated_card.misc = effect_x_cost
            generated_card.base_magic_number = effect_x_cost
            generated_card.magic_number = effect_x_cost
            base_damage = 9 + (6 if generated_card.upgraded else 0)
            generated_card.base_damage = base_damage
            generated_card.damage = base_damage

        combat_state.card_manager.generate_cards_to_draw_pile(
            "Expunger",
            1,
            shuffle_into=True,
            configure_card=_configure_expunger,
        )
        return []
        return ChangeStanceEffect(stance_type=StanceType.CALM).execute(combat_state, card, source, target)


@dataclass
class ExhaustCardEffect:
    """Exhaust a card."""
    target_card_uuid: str | None = None
    
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card.on_exhaust()
        return []


@dataclass
class DiscardCardEffect:
    """Discard a card from hand."""
    target_card_uuid: str | None = None
    
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        return []


@dataclass
class DiscardDeterministicHandCardEffect:
    """Discard the first other card in hand, with optional replay-only target hint."""
    count: int = 1

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm is None or cm.get_hand_size() <= 0:
            return []

        for _ in range(max(0, int(self.count))):
            if cm.get_hand_size() <= 0:
                break
            replay_target_uuid = getattr(card, "_replay_discard_target_uuid", None)
            hand_index = _select_hand_card_index_by_uuid(cm, card, replay_target_uuid)
            if hand_index is None:
                hand_index = _select_first_hand_card_index(cm, card)
            if hand_index is None:
                break
            _move_hand_card_to_discard(cm, hand_index=hand_index)
        return []


@dataclass
class GenerateCardsToHandEffect:
    card_id: str
    count: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm is None or self.count <= 0:
            return []
        cm.generate_cards_to_hand(
            self.card_id,
            self.count,
            hand_limit_offset=_hand_limit_offset_for_played_card(cm, card),
        )
        return []


@dataclass
class RandomDrawPileTypeToHandEffect:
    count: int
    card_type: CardType

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None or self.count <= 0:
            return []

        matching_cards = [
            draw_card
            for draw_card in getattr(card_manager.draw_pile, "cards", []) or []
            if getattr(draw_card, "card_type", None) == self.card_type
        ]
        if not matching_cards:
            return []

        hand_limit_offset = _hand_limit_offset_for_played_card(card_manager, card)
        rng = _combat_rng(combat_state)
        for _ in range(self.count):
            if not matching_cards:
                break
            if rng is not None and len(matching_cards) > 1:
                selected_card = matching_cards.pop(rng.random_int(len(matching_cards) - 1))
            else:
                selected_card = matching_cards.pop(0)
            if not card_manager.draw_pile.remove(selected_card):
                continue
            card_manager._add_card_to_hand_with_limit(selected_card, hand_limit_offset=hand_limit_offset)
        if hasattr(card_manager, "_check_normality_in_hand"):
            card_manager._check_normality_in_hand()
        return []


@dataclass
class JackOfAllTradesEffect:
    count: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None or self.count <= 0:
            return []
        hand_limit_offset = _hand_limit_offset_for_played_card(card_manager, card)
        generated_ids = _generate_random_colorless_combat_cards_to_hand(
            combat_state,
            self.count,
            hand_limit_offset=hand_limit_offset,
        )
        card._generated_card_ids = generated_ids
        return []


@dataclass
class RandomCombatCardsToDrawPileEffect:
    count: int
    pool_type: CardType

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None or self.count <= 0:
            return []
        if self.pool_type == CardType.ATTACK:
            pool = [card_id for card_id in _implemented_attack_card_ids() if card_id != card.card_id]
        else:
            pool = [card_id for card_id in _implemented_skill_card_ids() if card_id != card.card_id]
        generated_ids: list[str] = []
        for _ in range(self.count):
            selected_card_id = _choose_random_card_id_from_pool(combat_state, pool)
            if not selected_card_id:
                break
            card_manager.generate_cards_to_draw_pile(
                selected_card_id,
                1,
                shuffle_into=True,
                configure_card=_configure_zero_cost_if_positive,
            )
            generated_ids.append(selected_card_id)
        card._generated_card_ids = generated_ids
        return []


@dataclass
class TransmutationEffect:
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return []
        effect_x_cost = max(0, int(getattr(card, "_resolved_x_cost", 0) or 0))
        if effect_x_cost <= 0:
            return []

        def _configure_generated_card(new_card: CardInstance) -> None:
            if card.upgraded and not getattr(new_card, "upgraded", False):
                new_card.upgrade()
            new_card.cost_for_turn = 0
            new_card.is_cost_modified_for_turn = True

        generated_ids = _generate_random_colorless_combat_cards_to_hand(
            combat_state,
            effect_x_cost,
            hand_limit_offset=_hand_limit_offset_for_played_card(card_manager, card),
            configure_card=_configure_generated_card,
        )
        card._generated_card_ids = generated_ids
        return []


@dataclass
class TheBombEffect:
    turns: int
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        from sts_py.engine.combat.powers import TheBombPower

        source.add_power(TheBombPower(amount=self.turns, owner="player", damage=self.damage))
        return []


@dataclass
class InfiniteBladesEffect:
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        source.add_power(create_power("InfiniteBlades", 1, "player"))
        return []


@dataclass
class FinisherEffect:
    target_idx: int
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []

        hit_count = 0
        for played_card_id in getattr(combat_state, "cards_played_this_turn", []) or []:
            card_def = ALL_CARD_DEFS.get(played_card_id)
            if card_def is not None and getattr(card_def, "card_type", None) == CardType.ATTACK:
                hit_count += 1

        for _ in range(hit_count):
            if monster.is_dead():
                break
            monster.take_damage(self.damage)
        return []


@dataclass
class SneakyStrikeEffect:
    damage: int
    energy_gain: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is not None and not target.is_dead():
            target.take_damage(self.damage)
        if int(getattr(source, "_discards_this_turn", 0) or 0) > 0:
            source.energy += self.energy_gain
            card_manager = getattr(combat_state, "card_manager", None)
            if card_manager is not None:
                card_manager.set_energy(source.energy)
        return []


@dataclass
class ConcentrateEffect:
    discard_count: int
    energy_gain: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm is None:
            return []
        available = _hand_cards_excluding_played(cm, card)
        if len(available) < self.discard_count:
            return []
        for _ in range(self.discard_count):
            hand_index = _select_first_hand_card_index(cm, card)
            if hand_index is None:
                return []
            _move_hand_card_to_discard(cm, hand_index=hand_index)
        source.energy += self.energy_gain
        cm.set_energy(source.energy)
        return []


@dataclass
class CalculatedGambleEffect:
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm is None:
            return []
        original_cards = [hand_card for hand_card in list(cm.hand.cards) if hand_card is not card]
        discard_count = len(original_cards)
        for discard_card in original_cards:
            if discard_card in cm.hand.cards:
                hand_index = cm.hand.cards.index(discard_card)
                _move_hand_card_to_discard(cm, hand_index=hand_index)
        if discard_count > 0:
            cm.draw_cards(discard_count, hand_limit_offset=_hand_limit_offset_for_played_card(cm, card))
        return []


@dataclass
class HealEffect:
    """Heal the player."""
    amount: int
    
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        source.hp = min(source.max_hp, source.hp + self.amount)
        return []


@dataclass
class LoseHPEffect:
    """Lose HP (not damage, ignores block)."""
    amount: int
    
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if hasattr(source, "lose_hp"):
            source.lose_hp(self.amount, source_owner=source)
        else:
            source.hp = max(0, source.hp - self.amount)
        return []


@dataclass
class DiscardToTopEffect:
    """Move a card from discard pile to top of draw pile (Headbutt)."""

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm and cm.get_discard_pile_size() > 0:
            # Deterministic non-UI fallback: choose the first card in the
            # current discard-pile order and move it to the top of draw.
            top_discard = cm.discard_pile.pop(0)
            if top_discard is not None:
                cm.draw_pile.add(top_discard)
        return []


@dataclass
class BodySlamEffect:
    target_idx: int
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        
        base_damage = source.block
        modified_val = float(base_damage)
        if hasattr(target, 'vulnerable') and target.vulnerable > 0:
            modified_val *= 1.5
        if source.powers.is_weak():
            modified_val *= 0.75
        
        monster.take_damage(int(modified_val))
        return []

@dataclass
class HavocEffect:
    target_idx: int | None = None
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm is None or cm.get_draw_pile_size() <= 0:
            return []
        top_card = cm.draw_pile.pop()
        top_card._combat_state = combat_state
        top_card.free_to_play_once = True
        top_card.exhaust_on_use_once = True
        engine = getattr(combat_state, "engine", None)
        if engine is not None:
            engine.autoplay_card_instance(top_card, self.target_idx)
        else:
            execute_card(top_card, combat_state, source, self.target_idx)
            cm.exhaust_pile.add(top_card)
            _trigger_exhaust_hooks(cm, source, top_card)
        return []

@dataclass
class WarcryEffect:
    draw_count: int
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm is not None:
            cm.draw_cards(
                self.draw_count,
                hand_limit_offset=_hand_limit_offset_for_played_card(cm, card),
            )
            hand_index = _select_first_hand_card_index(cm, card)
            if hand_index is not None:
                card_to_put = cm.hand.pop(hand_index)
                cm.draw_pile.add(card_to_put)
        return []

@dataclass
class SpotWeaknessEffect:
    target_idx: int
    amount: int
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is not None and target.next_move is not None:
            if target.next_move.intent.is_attack():
                from sts_py.engine.combat.powers import create_power
                source.add_power(create_power("Strength", self.amount, "player"))
                source.strength += self.amount
        return []


@dataclass
class ApplyPoisonEffect:
    amount: int
    target_idx: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        _apply_poison_to_monster(source, monster, self.amount)
        return []


@dataclass
class BouncingFlaskEffect:
    hit_count: int
    poison_amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        rng = None
        if combat_state.card_manager is not None:
            rng = getattr(combat_state.card_manager, "rng", None)
        if rng is None:
            rng = getattr(combat_state, "rng", None)

        for _ in range(self.hit_count):
            alive_monsters = [monster for monster in combat_state.monsters if not monster.is_dead()]
            if not alive_monsters:
                break
            chosen_monster = alive_monsters[0]
            if rng is not None and len(alive_monsters) > 1:
                chosen_monster = alive_monsters[rng.random_int(len(alive_monsters) - 1)]
            _apply_poison_to_monster(source, chosen_monster, self.poison_amount)
        return []


@dataclass
class CatalystEffect:
    target_idx: int
    multiplier: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        current_poison = monster.get_power_amount("Poison")
        if current_poison <= 0:
            return []
        monster.powers.reduce_power("Poison", current_poison)
        monster.add_power(create_power("Poison", current_poison * self.multiplier, monster.id))
        return []


@dataclass
class CripplingCloudEffect:
    poison_amount: int
    weak_amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        from sts_py.engine.combat.powers import create_power
        for monster in combat_state.monsters:
            if monster.is_dead():
                continue
            monster.add_power(create_power("Weak", self.weak_amount, monster.id))
            _apply_poison_to_monster(source, monster, self.poison_amount)
        return []


@dataclass
class CorpseExplosionEffect:
    target_idx: int
    poison_amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        from sts_py.engine.combat.powers import create_power
        _apply_poison_to_monster(source, monster, self.poison_amount)
        monster.add_power(create_power("CorpseExplosion", 1, monster.id))
        return []


@dataclass
class TemporaryStrengthDownEffect:
    amount: int
    target_idx: int | None = None
    target_all: bool = False

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if self.target_all:
            for monster in combat_state.monsters:
                if monster.is_dead():
                    continue
                _apply_temporary_strength_down_to_monster(monster, self.amount)
            return []

        if target is None or self.target_idx is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        _apply_temporary_strength_down_to_monster(monster, self.amount)
        return []


@dataclass
class MalaiseEffect:
    target_idx: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []

        resolved_x_cost = max(0, int(getattr(card, "_resolved_x_cost", 0) or 0))
        total_amount = resolved_x_cost + max(0, int(getattr(card, "magic_number", 0) or 0))
        if total_amount <= 0:
            return []

        monster.add_power(create_power("Weak", total_amount, monster.id))
        _apply_temporary_strength_down_to_monster(monster, total_amount)
        return []


@dataclass
class ChannelOrbEffect:
    orb_type: str
    count: int = 1

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        engine = getattr(combat_state, "engine", None)
        if engine is None or self.count <= 0:
            return []

        from sts_py.engine.combat.orbs import FrostOrb, LightningOrb, PlasmaOrb, DarkOrb

        orb_classes = {
            "Lightning": LightningOrb,
            "Frost": FrostOrb,
            "Plasma": PlasmaOrb,
            "Dark": DarkOrb,
        }
        orb_class = orb_classes.get(self.orb_type)
        if orb_class is None:
            return []

        for _ in range(self.count):
            engine._channel_orb(orb_class())
        return []


@dataclass
class DualcastEffect:
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        orbs = getattr(source, "orbs", None)
        if orbs is None or len(orbs) == 0:
            return []
        orbs.evoke_first_twice()
        return []


@dataclass
class GoForTheEyesEffect:
    target_idx: int
    damage: int
    weak_amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        monster.take_damage(self.damage)
        if monster.next_move is not None and monster.next_move.intent.is_attack():
            monster.add_power(create_power("Weak", self.weak_amount, monster.id))
        return []


@dataclass
class BaneEffect:
    target_idx: int
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        monster.take_damage(self.damage)
        if monster.is_dead():
            return []
        if monster.get_power_amount("Poison") > 0:
            monster.take_damage(self.damage)
        return []


@dataclass
class DaggerSprayEffect:
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        DealDamageAllEffect(damage=self.damage).execute(combat_state, card, source, target)
        DealDamageAllEffect(damage=self.damage).execute(combat_state, card, source, target)
        return []


@dataclass
class AllOutAttackEffect:
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        DealDamageAllEffect(damage=self.damage).execute(combat_state, card, source, target)
        DiscardDeterministicHandCardEffect(count=1).execute(combat_state, card, source, target)
        return []


@dataclass
class CompileDriverEffect:
    target_idx: int
    damage: int
    draw_count: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        monster.take_damage(self.damage)
        if monster.is_dead() and combat_state.card_manager is not None:
            combat_state.card_manager.draw_cards(
                self.draw_count,
                hand_limit_offset=_hand_limit_offset_for_played_card(combat_state.card_manager, card),
            )
        return []


@dataclass
class StreamlineEffect:
    target_idx: int
    damage: int
    cost_reduction: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        monster.take_damage(self.damage)
        max_reduction = max(0, int(getattr(card, "cost", 0) or 0))
        card.combat_cost_reduction = min(
            max_reduction,
            max(0, int(getattr(card, "combat_cost_reduction", 0) or 0)) + max(0, int(self.cost_reduction)),
        )
        if hasattr(card, "apply_combat_cost_modifiers"):
            card.apply_combat_cost_modifiers()
        return []


@dataclass
class BarrageEffect:
    target_idx: int
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        hit_count = len(getattr(source, "orbs", []) or [])
        for _ in range(hit_count):
            if monster.is_dead():
                break
            monster.take_damage(self.damage)
        return []


@dataclass
class DarkImpulseEffect:
    amount: int = 1

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        orbs = getattr(source, "orbs", None)
        if orbs is None:
            return []
        orbs.dark_impulse(self.amount)
        return []


@dataclass
class ConsumeEffect:
    focus_amount: int
    slot_loss: int = 1

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        source.add_power(create_power("Focus", self.focus_amount, "player"))
        if hasattr(source, "focus"):
            source.focus += self.focus_amount
        orbs = getattr(source, "orbs", None)
        if orbs is not None:
            orbs.decrease_slots(self.slot_loss)
        return []


@dataclass
class AggregateEffect:
    divisor: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return []
        divisor = max(1, int(self.divisor))
        energy_gain = max(0, int(card_manager.get_draw_pile_size() // divisor))
        if energy_gain <= 0:
            return []
        source.energy += energy_gain
        card_manager.set_energy(source.energy)
        return []


@dataclass
class AutoShieldsEffect:
    amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if int(getattr(source, "block", 0) or 0) != 0:
            return []
        source.gain_block(self.amount)
        return []


@dataclass
class WhiteNoiseEffect:
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        hand_limit_offset = 0
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is not None:
            hand_limit_offset = _hand_limit_offset_for_played_card(card_manager, card)
        _generate_random_power_cards_to_hand(
            combat_state,
            1,
            hand_limit_offset=hand_limit_offset,
            zero_cost_for_turn=True,
        )
        return []


@dataclass
class ChaosEffect:
    count: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        engine = getattr(combat_state, "engine", None)
        if engine is None or self.count <= 0:
            return []
        for _ in range(self.count):
            engine._channel_orb(_random_orb_instance(combat_state))
        return []


@dataclass
class RecursionEffect:
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        orbs = getattr(source, "orbs", None)
        if orbs is None or len(orbs) == 0:
            return []
        orbs.evoke_and_channel_copy_leftmost()
        return []


@dataclass
class IncreaseOrbSlotsEffect:
    amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        orbs = getattr(source, "orbs", None)
        if orbs is None:
            return []
        orbs.increase_slots(self.amount)
        return []


@dataclass
class ChillEffect:
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        engine = getattr(combat_state, "engine", None)
        if engine is None:
            return []
        live_enemy_count = sum(1 for monster in combat_state.monsters if not monster.is_dead())
        if live_enemy_count <= 0:
            return []
        from sts_py.engine.combat.orbs import FrostOrb
        for _ in range(live_enemy_count):
            engine._channel_orb(FrostOrb())
        return []


@dataclass
class TempestEffect:
    extra_channels: int = 0

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        engine = getattr(combat_state, "engine", None)
        if engine is None:
            return []
        resolved_x_cost = max(0, int(getattr(card, "_resolved_x_cost", 0) or 0))
        total_channels = resolved_x_cost + max(0, int(self.extra_channels))
        if total_channels <= 0:
            return []
        from sts_py.engine.combat.orbs import LightningOrb
        for _ in range(total_channels):
            engine._channel_orb(LightningOrb())
        return []


@dataclass
class ReinforcedBodyEffect:
    block_per_energy: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        resolved_x_cost = max(0, int(getattr(card, "_resolved_x_cost", 0) or 0))
        if resolved_x_cost <= 0:
            return []
        total_block = max(0, int(self.block_per_energy)) * resolved_x_cost
        if total_block > 0:
            source.gain_block(total_block)
        return []


@dataclass
class TurboEffect:
    amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        source.energy += self.amount
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is not None:
            card_manager.set_energy(source.energy)
        return []


@dataclass
class DoubleEnergyEffect:
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        pending_cost = 0 if card.free_to_play_once else max(0, int(getattr(card, "cost_for_turn", getattr(card, "cost", 0)) or 0))
        source.energy = max(0, (int(getattr(source, "energy", 0) or 0) * 2) - pending_cost)
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is not None:
            card_manager.set_energy(source.energy)
        return []


@dataclass
class FissionEffect:
    upgraded: bool = False

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        orbs = getattr(source, "orbs", None)
        card_manager = getattr(combat_state, "card_manager", None)
        if orbs is None or card_manager is None:
            return []
        orb_count = max(0, int(orbs.filled_count()))
        if self.upgraded:
            orbs.evoke_all_orbs()
        else:
            orbs.remove_all_orbs()
        if orb_count > 0:
            source.energy += orb_count
            card_manager.set_energy(source.energy)
            card_manager.draw_cards(
                orb_count,
                hand_limit_offset=_hand_limit_offset_for_played_card(card_manager, card),
            )
        return []


@dataclass
class MultiCastEffect:
    extra_evokes: int = 0

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        orbs = getattr(source, "orbs", None)
        if orbs is None or orbs.filled_count() <= 0:
            return []
        evoke_count = max(0, int(getattr(card, "_resolved_x_cost", 0) or 0)) + max(0, int(self.extra_evokes))
        if evoke_count <= 0:
            return []
        orbs.evoke_leftmost_n_times(evoke_count)
        return []


@dataclass
class RecycleEffect:
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return []
        hand_index = _select_first_hand_card_index(card_manager, card)
        if hand_index is None:
            return []
        recycled_card = card_manager.hand.cards[hand_index]
        gain_amount = 0
        pending_cost = 0 if card.free_to_play_once else max(0, int(getattr(card, "cost_for_turn", getattr(card, "cost", 0)) or 0))
        target_cost = int(getattr(recycled_card, "cost_for_turn", getattr(recycled_card, "cost", -1)) or -1)
        if target_cost == -1:
            gain_amount = max(0, int(getattr(source, "energy", 0) or 0) - pending_cost)
        elif target_cost > 0:
            gain_amount = target_cost
        _move_hand_card_to_exhaust(card_manager, source, hand_index=hand_index)
        if gain_amount > 0:
            source.energy += gain_amount
            card_manager.set_energy(source.energy)
        return []


@dataclass
class StackEffect:
    upgraded_bonus: int = 0

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        discard_size = card_manager.get_discard_pile_size() if card_manager is not None else 0
        total_block = max(0, int(discard_size)) + max(0, int(self.upgraded_bonus))
        if total_block > 0:
            source.gain_block(total_block)
        return []


@dataclass
class SteamBarrierEffect:
    amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        source.gain_block(self.amount)
        card.base_block = max(0, int(getattr(card, "base_block", 0) or 0) - 1)
        card.block = card.base_block
        return []


@dataclass
class GeneticAlgorithmEffect:
    amount: int
    block_growth: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        source.gain_block(self.amount)
        _apply_misc_stateful_growth(card, combat_state, max(0, int(self.block_growth)))
        return []


@dataclass
class ClawEffect:
    target_idx: int
    damage: int
    damage_growth: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        monster.take_damage(self.damage)
        _grow_claw_cards(combat_state, card, self.damage_growth)
        return []


@dataclass
class FTLEffect:
    target_idx: int
    damage: int
    card_play_threshold: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        monster.take_damage(self.damage)
        played_count = len(getattr(combat_state, "cards_played_this_turn", []) or [])
        if played_count < max(0, int(self.card_play_threshold)):
            card_manager = getattr(combat_state, "card_manager", None)
            if card_manager is not None:
                card_manager.draw_cards(
                    1,
                    hand_limit_offset=_hand_limit_offset_for_played_card(card_manager, card),
                )
        return []


@dataclass
class MelterEffect:
    target_idx: int
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        monster.block = 0
        monster.take_damage(self.damage)
        return []


@dataclass
class SunderEffect:
    target_idx: int
    damage: int
    energy_gain: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        monster.take_damage(self.damage)
        if monster.is_dead():
            source.energy += self.energy_gain
            card_manager = getattr(combat_state, "card_manager", None)
            if card_manager is not None:
                card_manager.set_energy(source.energy)
        return []


@dataclass
class ScrapeEffect:
    target_idx: int
    damage: int
    draw_count: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        monster.take_damage(self.damage)
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return []
        drawn_cards: list[CardInstance] = []
        for _ in range(max(0, int(self.draw_count))):
            drawn_card = card_manager.draw_card(
                card_manager.rng,
                hand_limit_offset=_hand_limit_offset_for_played_card(card_manager, card),
            )
            if drawn_card is None:
                break
            drawn_cards.append(drawn_card)
        for drawn_card in drawn_cards:
            if drawn_card not in getattr(card_manager.hand, "cards", []):
                continue
            cost_for_turn = int(getattr(drawn_card, "cost_for_turn", getattr(drawn_card, "cost", -1)) or -1)
            if cost_for_turn > 0 and not bool(getattr(drawn_card, "free_to_play_once", False)):
                hand_index = card_manager.hand.cards.index(drawn_card)
                _move_hand_card_to_discard(card_manager, hand_index=hand_index)
        return []


@dataclass
class BludgeonEffect:
    """Deal 32(42) damage (Bludgeon)."""
    target_idx: int
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        monster.take_damage(self.damage)
        return []


@dataclass
class BrutalityEffect:
    """At start of turn, lose 1 HP and draw 1 card (Brutality)."""
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        source.add_power(create_power("Brutality", 1, "player"))
        return []


@dataclass
class CorruptionEffect:
    """Skills cost 0 and are exhausted when played (Corruption)."""
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        source.add_power(create_power("Corruption", 1, "player"))
        return []


@dataclass
class DoubleTapEffect:
    """Next Attack played twice this turn (Double Tap)."""
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        source.add_power(create_power("DoubleTap", 1, "player"))
        return []


@dataclass
class ExhumeEffect:
    """Put a random card from exhaust into hand (Exhume)."""
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm and hasattr(cm, 'exhaust_pile') and cm.exhaust_pile.cards:
            exhaust_cards = list(cm.exhaust_pile.cards)
            selected_index = 0
            if getattr(cm, "rng", None) is not None and len(exhaust_cards) > 1:
                selected_index = cm.rng.random_int(len(exhaust_cards) - 1)
            selected_card = exhaust_cards[selected_index]
            cm.exhaust_pile.remove(selected_card)
            cm._add_card_to_hand_with_limit(selected_card)
        return []


@dataclass
class FeedEffect:
    """Deal 10(12) damage. If kills, gain 3(4) Max HP (Feed). Exhaust."""
    target_idx: int
    damage: int
    max_hp_gain: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        monster.take_damage(self.damage)
        if _is_true_kill_reward_target(monster):
            source.max_hp += self.max_hp_gain
            source.hp = min(source.hp + self.max_hp_gain, source.max_hp)
        return []


@dataclass
class FiendFireEffect:
    """Exhaust hand. Deal 7(10) damage per card exhausted (Fiend Fire)."""
    target_idx: int
    damage_per_card: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        exhausted_cards: list[CardInstance] = []
        if cm:
            remaining = []
            for hand_card in cm.hand.cards:
                if hand_card is card:
                    remaining.append(hand_card)
                else:
                    exhausted_cards.append(hand_card)
            cm.hand.cards = remaining
            if hasattr(cm, "_check_normality_in_hand"):
                cm._check_normality_in_hand()
            for exhausted_card in exhausted_cards:
                _trigger_exhaust_hooks(cm, source, exhausted_card)
                cm.exhaust_pile.add(exhausted_card)
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        target_monster = combat_state.monsters[self.target_idx]
        if target_monster.is_dead():
            return []
        for _ in exhausted_cards:
            if target_monster.is_dead():
                break
            target_monster.take_damage(self.damage_per_card)
        return []


@dataclass
class ImmolateEffect:
    """Deal 21(28) damage to ALL enemies. Add Burn to discard (Immolate)."""
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        for monster in combat_state.monsters:
            if not monster.is_dead():
                monster.take_damage(self.damage)
        cm = combat_state.card_manager
        if cm:
            burn = CardInstance(card_id="Burn", upgraded=False)
            cm.discard_pile.add(burn)
        return []


@dataclass
class JuggernautEffect:
    """Whenever you gain block, deal 5(7) to random enemy (Juggernaut)."""
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        source.add_power(create_power("Juggernaut", self.damage, "player"))
        return []


@dataclass
class ReaperEffect:
    """Deal 4(5) to ALL. Heal HP equal to unblocked damage. Exhaust (Reaper)."""
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        total_actual_damage = 0
        tmp = float(self.damage)

        if hasattr(source, "strength") and source.strength != 0:
            tmp += source.strength

        if hasattr(source, "powers"):
            tmp = source.powers.apply_damage_modifiers(tmp, DamageType.NORMAL.value)

        if hasattr(source, "stance") and source.stance is not None:
            tmp = source.stance.at_damage_give(tmp, DamageType.NORMAL.value)

        if hasattr(source, "powers"):
            tmp = source.powers.apply_damage_final_give_modifiers(tmp, DamageType.NORMAL.value)

        for monster in combat_state.monsters:
            if monster.is_dead():
                continue
            final_damage = tmp
            if hasattr(monster, "vulnerable") and monster.vulnerable > 0:
                final_damage *= 1.5
            if hasattr(monster, "powers"):
                final_damage = monster.powers.apply_damage_receive_modifiers(final_damage, DamageType.NORMAL.value)
                final_damage = monster.powers.apply_damage_final_receive_modifiers(final_damage, DamageType.NORMAL.value)
            final_damage = max(0, int(final_damage))
            total_actual_damage += monster.take_damage(final_damage)
        if total_actual_damage > 0:
            source.hp = min(source.max_hp, source.hp + total_actual_damage)
        return []


@dataclass
class BattleTranceEffect:
    """Draw 3(4) cards. You cannot draw additional cards this turn (Battle Trance)."""
    draw_count: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm:
            cm.draw_cards(
                self.draw_count,
                hand_limit_offset=_hand_limit_offset_for_played_card(cm, card),
            )
            source.add_power(create_power("NoDraw", 1, "player"))
        return []


@dataclass
class BloodForBloodEffect:
    """Costs 1 less for each HP lost in combat. Deal 18(22) damage (Blood for Blood)."""
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None:
            return []
        target.take_damage(self.damage)
        return []


@dataclass
class BurningPactEffect:
    """Exhaust 1 card. Draw 2(3) cards (Burning Pact)."""
    draw_count: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm:
            hand_index = _select_hand_card_index(cm, card)
            if hand_index is not None:
                _move_hand_card_to_exhaust(cm, source, hand_index=hand_index)
        if cm:
            cm.draw_cards(self.draw_count)
        return []


@dataclass
class DropkickEffect:
    """Deal 5(8) damage. If target has Vulnerable, gain 1 Energy and draw 1 card (Dropkick)."""
    damage: int
    energy_gain: int
    draw_count: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None:
            return []
        target.take_damage(self.damage)
        if target.get_power_amount("Vulnerable") > 0:
            source.energy += self.energy_gain
            cm = combat_state.card_manager
            if cm:
                cm.set_energy(source.energy)
                cm.draw_cards(self.draw_count)
        return []


@dataclass
class FlechettesEffect:
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or target.is_dead():
            return []
        card_manager = getattr(combat_state, "card_manager", None)
        skill_count = 0
        if card_manager is not None:
            for hand_card in getattr(card_manager.hand, "cards", []):
                if getattr(hand_card, "card_type", None) == CardType.SKILL:
                    skill_count += 1
        for _ in range(skill_count):
            if target.is_dead():
                break
            target.take_damage(self.damage)
        return []


@dataclass
class GlassKnifeEffect:
    target_idx: int
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        monster.take_damage(self.damage)
        if not monster.is_dead():
            monster.take_damage(self.damage)
        card.base_damage = max(0, int(getattr(card, "base_damage", 0) or 0) - 2)
        card.damage = card.base_damage
        card.is_damage_modified = False
        return []


@dataclass
class HeelHookEffect:
    damage: int
    energy_gain: int
    draw_count: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None:
            return []
        target.take_damage(self.damage)
        if target.get_power_amount("Weak") > 0:
            source.energy += self.energy_gain
            cm = combat_state.card_manager
            if cm:
                cm.set_energy(source.energy)
                cm.draw_cards(self.draw_count)
        return []


@dataclass
class RiddleWithHolesEffect:
    target_idx: int
    damage: int
    hit_count: int = 5

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        for _ in range(max(0, int(self.hit_count))):
            if monster.is_dead():
                break
            monster.take_damage(self.damage)
        return []


@dataclass
class UnloadEffect:
    target_idx: int
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if target is not None and not target.is_dead():
            target.take_damage(self.damage)
        if cm is None:
            return []
        remaining_cards = [hand_card for hand_card in list(cm.hand.cards) if hand_card is not card]
        for discard_card in remaining_cards:
            if discard_card in cm.hand.cards:
                hand_index = cm.hand.cards.index(discard_card)
                _move_hand_card_to_discard(cm, hand_index=hand_index)
        return []


@dataclass
class DualWieldEffect:
    """Create a copy of an Attack or Power card in hand (Dual Wield)."""
    copies: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm:
            hand_index = _select_first_hand_card_index(
                cm,
                card,
                predicate=lambda hand_card: hasattr(hand_card, "card_type") and hand_card.card_type.value in ["ATTACK", "POWER"],
            )
            if hand_index is None:
                return []
            original = cm.hand.cards[hand_index]
            hand_limit_offset = _hand_limit_offset_for_played_card(cm, card)
            for _ in range(self.copies):
                copy = original.make_stat_equivalent_copy()
                copy._combat_state = combat_state
                cm._add_card_to_hand_with_limit(copy, hand_limit_offset=hand_limit_offset)
        return []


@dataclass
class EntrenchEffect:
    """Double your current Block (Entrench)."""
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        source.gain_block(source.block)
        return []


@dataclass
class HemokinesisEffect:
    """Lose 2 HP. Deal 15(20) damage (Hemokinesis)."""
    damage: int
    hp_loss: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if hasattr(source, "lose_hp"):
            source.lose_hp(self.hp_loss, source_owner=source)
        else:
            source.hp = max(0, source.hp - self.hp_loss)
        if target is None:
            return []
        target.take_damage(self.damage)
        return []


@dataclass
class InfernalBladeEffect:
    """Add a random Attack to hand. It costs 0 this turn. Exhaust (Infernal Blade)."""
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm is None:
            return []
        from sts_py.engine.content.cards_min import ALL_CARD_DEFS, CardRarity, CardType
        attack_cards = [
            card_id
            for card_id, card_def in ALL_CARD_DEFS.items()
            if card_def.card_type == CardType.ATTACK and card_def.rarity in {
                CardRarity.BASIC,
                CardRarity.COMMON,
                CardRarity.UNCOMMON,
                CardRarity.RARE,
            }
        ]
        if not attack_cards:
            return []
        selected_index = 0
        if getattr(cm, "rng", None) is not None and len(attack_cards) > 1:
            selected_index = cm.rng.random_int(len(attack_cards) - 1)
        selected_card_id = attack_cards[selected_index]

        def _configure_generated_attack(new_card: CardInstance) -> None:
            new_card.cost = 0
            new_card.cost_for_turn = 0
            new_card.is_cost_modified_for_turn = True

        cm.generate_cards_to_hand(selected_card_id, 1, configure_card=_configure_generated_attack)
        return []


@dataclass
class IntimidateEffect:
    """Apply 1(2) Weak to ALL enemies. Exhaust (Intimidate)."""
    weak_amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        for monster in combat_state.monsters:
            if not monster.is_dead():
                monster.add_power(create_power("Weak", self.weak_amount, "monster"))
        return []


@dataclass
class PowerThroughEffect:
    """Add 2 Wounds to hand. Gain 15(20) Block (Power Through)."""
    block_amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm:
            cm.generate_cards_to_hand("Wound", 2, hand_limit_offset=_hand_limit_offset_for_played_card(cm, card))
        source.gain_block(self.block_amount)
        return []


@dataclass
class RageEffect:
    """Whenever you play an Attack this turn, gain 3(5) Block (Rage)."""
    block_amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        source.add_power(create_power("Rage", self.block_amount, "player"))
        return []


@dataclass
class RampageEffect:
    """Deal 8 damage. Increases by 5(8) each time this card is played (Rampage)."""
    base_damage: int
    damage_increase: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None:
            return []
        target.take_damage(card.damage)
        card.combat_damage_bonus += self.damage_increase
        return []


@dataclass
class RecklessChargeEffect:
    """Deal 7(10) damage. Shuffle a Dazed into your draw pile (Reckless Charge)."""
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None:
            return []
        target.take_damage(self.damage)
        cm = combat_state.card_manager
        if cm:
            cm.generate_cards_to_draw_pile("Dazed", 1, shuffle_into=False)
        return []


@dataclass
class FlameBarrierEffect:
    """Gain 12(16) Block. Deal 4(6) damage when attacked (Flame Barrier)."""
    block_amount: int
    thorns_damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        source.gain_block(self.block_amount)
        source.add_power(create_power("FlameBarrier", self.thorns_damage, "player"))
        return []


@dataclass
class SentinelEffect:
    """Gain 5(8) Block. If exhausted, gain 2(3) Energy (Sentinel)."""
    block_amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        source.gain_block(self.block_amount)
        return []


@dataclass
class SecondWindEffect:
    """Exhaust non-Attack cards in hand. Gain 5(7) Block per card exhausted (Second Wind)."""
    block_per_card: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm:
            exhausted = []
            remaining = []
            for c in cm.hand.cards:
                if c is card or (hasattr(c, 'card_type') and c.card_type.value == 'ATTACK'):
                    remaining.append(c)
                else:
                    exhausted.append(c)
            cm.hand.cards = remaining
            if hasattr(cm, "_check_normality_in_hand"):
                cm._check_normality_in_hand()
            for c in exhausted:
                _trigger_exhaust_hooks(cm, source, c)
                cm.exhaust_pile.add(c)
                source.gain_block(self.block_per_card)
        return []


@dataclass
class SeeingRedEffect:
    """Gain 2 Energy. Exhaust (Seeing Red)."""
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        source.energy += 2
        cm = combat_state.card_manager
        if cm:
            cm.set_energy(source.energy)
        return []


@dataclass
class SeverSoulEffect:
    """Exhaust non-Attack cards in hand. Deal 16(22) damage (Sever Soul)."""
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm:
            exhausted = []
            remaining = []
            for c in cm.hand.cards:
                if c is card or (hasattr(c, 'card_type') and c.card_type.value == 'ATTACK'):
                    remaining.append(c)
                else:
                    exhausted.append(c)
            cm.hand.cards = remaining
            if hasattr(cm, "_check_normality_in_hand"):
                cm._check_normality_in_hand()
            for c in exhausted:
                _trigger_exhaust_hooks(cm, source, c)
                cm.exhaust_pile.add(c)
        if target is None:
            return []
        target.take_damage(self.damage)
        return []


@dataclass
class ShockwaveEffect:
    """Apply 3(5) Weak and Vulnerable to ALL enemies. Exhaust (Shockwave)."""
    weak_amount: int
    vul_amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        for monster in combat_state.monsters:
            if not monster.is_dead():
                monster.add_power(create_power("Weak", self.weak_amount, "monster"))
                monster.add_power(create_power("Vulnerable", self.vul_amount, "monster"))
        return []


@dataclass
class WhirlwindEffect:
    """Deal 5(8) damage X times to ALL enemies (Whirlwind)."""
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        hit_count = getattr(card, "_resolved_x_cost", None)
        if hit_count is None:
            hit_count = 0 if card.free_to_play_once else max(0, int(getattr(source, "energy", 0) or 0))
        for _ in range(max(0, int(hit_count))):
            for monster in combat_state.monsters:
                if not monster.is_dead():
                    monster.take_damage(self.damage)
        return []


@dataclass
class PerfectedStrikeEffect:
    """Deal damage +2 for each 'Strike' card in deck (Perfected Strike)."""
    target_idx: int
    base_damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []

        cm = combat_state.card_manager
        strike_ids = {"Strike", "Strike_P"}
        strike_count = 1 if card.card_id in strike_ids else 0
        if cm:
            all_cards = (
                list(cm.draw_pile.cards)
                + list(cm.hand.cards)
                + list(cm.discard_pile.cards)
                + list(cm.exhaust_pile.cards)
            )
            for pile_card in all_cards:
                if pile_card is card:
                    continue
                if getattr(pile_card, "card_id", None) in strike_ids:
                    strike_count += 1

        bonus_per_strike = 2 if not card.upgraded else 3
        total_damage = self.base_damage + (strike_count * bonus_per_strike)
        monster.take_damage(total_damage)
        return []


@dataclass
class MakeCardEffect:
    """Create a copy of the current card and add to discard pile (Anger)."""
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm:
            copy = card.make_stat_equivalent_copy()
            copy.free_to_play_once = False
            copy.exhaust_on_use_once = False
            copy.purge_on_use = False
            copy.return_to_hand = False
            copy.shuffle_back_into_draw_pile = False
            copy._combat_state = combat_state
            cm.discard_pile.add(copy)
        return []


@dataclass
class UpgradeHandCardEffect:
    """Upgrade one random card in hand (Armaments)."""
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm is None or cm.get_hand_size() <= 0:
            return []

        if card.upgraded:
            for _, card_to_upgrade in _hand_cards_excluding_played(cm, card):
                _apply_temporary_upgrade(card_to_upgrade)
            return []

        hand_index = _select_first_hand_card_index(
            cm,
            card,
            predicate=lambda candidate: not getattr(candidate, "upgraded", False),
        )
        if hand_index is None:
            hand_index = _select_first_hand_card_index(cm, card)
        if hand_index is not None:
            _apply_temporary_upgrade(cm.hand.cards[hand_index])
        return []


@dataclass
class AddCardToDrawPileEffect:
    """Add a card to the draw pile (Wild Strike)."""
    card_to_add: str
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm:
            cm.generate_cards_to_draw_pile(self.card_to_add, 1, shuffle_into=False)
        return []


@dataclass
class ExhaustRandomHandCardEffect:
    """Exhaust a random card from hand, with optional replay-only target hint."""

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm is None or cm.get_hand_size() <= 0:
            return []

        replay_target_uuid = getattr(card, "_replay_exhaust_target_uuid", None)
        hand_index = _select_hand_card_index_by_uuid(cm, card, replay_target_uuid)
        if hand_index is None:
            hand_index = _select_hand_card_index(cm, card)
        if hand_index is not None:
            _move_hand_card_to_exhaust(cm, source, hand_index=hand_index)
        return []


@dataclass
class ExhaustDeterministicHandCardEffect:
    """Exhaust the first other card in hand, with optional replay-only target hint."""

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        cm = combat_state.card_manager
        if cm is None or cm.get_hand_size() <= 0:
            return []

        replay_target_uuid = getattr(card, "_replay_exhaust_target_uuid", None)
        hand_index = _select_hand_card_index_by_uuid(cm, card, replay_target_uuid)
        if hand_index is None:
            hand_index = _select_first_hand_card_index(cm, card)
        if hand_index is not None:
            _move_hand_card_to_exhaust(cm, source, hand_index=hand_index)
        return []


@dataclass
class DealDamageWithStrengthEffect:
    """Deal damage with strength multiplier (Heavy Blade)."""
    target_idx: int
    damage: int
    strength_multiplier: int = 3

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []

        current_strength = max(0, int(getattr(source, "strength", 0) or 0))
        base_damage = int(getattr(card, "base_damage", self.damage) if getattr(card, "base_damage", -1) >= 0 else self.damage)
        total_damage = base_damage + (current_strength * (1 + self.strength_multiplier))
        actual_damage = monster.take_damage(max(0, total_damage))
        card._last_damage_dealt = actual_damage
        source._last_damage_dealt = actual_damage
        return []


@dataclass
class BowlingBashEffect:
    target_idx: int
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        hit_count = max(1, len(_living_monsters(combat_state)))
        for _ in range(hit_count):
            if monster.is_dead():
                break
            actual_damage = monster.take_damage(self.damage)
            _trigger_player_attack_damage_hooks(combat_state, source, monster, actual_damage, damage_type="NORMAL")
        return []


@dataclass
class DealDamageRepeatedEffect:
    target_idx: int
    damage: int
    hit_count: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        for _ in range(max(0, int(self.hit_count or 0))):
            if monster.is_dead():
                break
            actual_damage = monster.take_damage(self.damage)
            _trigger_player_attack_damage_hooks(combat_state, source, monster, actual_damage, damage_type="NORMAL")
        return []


@dataclass
class DealDamageRandomEnemyRepeatedEffect:
    damage: int
    hit_count: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        rng = _combat_rng(combat_state)
        for _ in range(max(0, int(self.hit_count or 0))):
            living = _living_monsters(combat_state)
            if not living:
                break
            if rng is not None and len(living) > 1:
                monster = living[rng.random_int(len(living) - 1)]
            else:
                monster = living[0]
            actual_damage = monster.take_damage(self.damage)
            _trigger_player_attack_damage_hooks(combat_state, source, monster, actual_damage, damage_type="NORMAL")
        return []


@dataclass
class ConditionalLastCardTypeGainEnergyEffect:
    required_type: CardType
    amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if not _last_played_card_type_matches(combat_state, self.required_type):
            return []
        source.energy += self.amount
        if combat_state.card_manager is not None:
            combat_state.card_manager.set_energy(source.energy)
        return []


@dataclass
class ConditionalLastCardTypeDrawEffect:
    required_type: CardType
    amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if not _last_played_card_type_matches(combat_state, self.required_type):
            return []
        if combat_state.card_manager is not None:
            combat_state.card_manager.draw_cards(
                self.amount,
                hand_limit_offset=_hand_limit_offset_for_played_card(combat_state.card_manager, card),
            )
        return []


@dataclass
class ConditionalLastCardTypeApplyMonsterPowerEffect:
    required_type: CardType
    target_idx: int
    power_type: str
    amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if not _last_played_card_type_matches(combat_state, self.required_type):
            return []
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        _apply_power_to_enemy_from_player(source, monster, self.power_type, self.amount)
        return []


@dataclass
class HaltEffect:
    base_block: int
    wrath_bonus_block: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        total_block = self.base_block
        if getattr(getattr(source, "stance", None), "stance_type", None) == StanceType.WRATH:
            total_block += self.wrath_bonus_block
        source.gain_block(total_block)
        return []


@dataclass
class ConditionalAttackIntentChangeStanceEffect:
    target_idx: int
    stance_type: StanceType

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead() or not _monster_intends_attack(monster):
            return []
        return ChangeStanceEffect(self.stance_type).execute(combat_state, card, source, target)


@dataclass
class IndignationEffect:
    amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if getattr(getattr(source, "stance", None), "stance_type", None) == StanceType.WRATH:
            for monster in _living_monsters(combat_state):
                _apply_power_to_enemy_from_player(source, monster, "Vulnerable", self.amount)
            return []
        return ChangeStanceEffect(StanceType.WRATH).execute(combat_state, card, source, target)


@dataclass
class PressurePointsEffect:
    target_idx: int
    amount: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        _apply_power_to_enemy_from_player(source, monster, "Mark", self.amount)
        for current_monster in _living_monsters(combat_state):
            mark_amount = int(getattr(current_monster.powers.get_power("Mark"), "amount", 0) or 0)
            _lose_hp_direct(current_monster, mark_amount)
        return []


@dataclass
class JudgementEffect:
    target_idx: int
    threshold: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        if int(getattr(monster, "hp", 0) or 0) <= self.threshold:
            monster.hp = 0
            monster.is_dying = True
        return []


@dataclass
class LessonLearnedEffect:
    target_idx: int
    damage: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        if target is None or self.target_idx >= len(combat_state.monsters):
            return []
        monster = combat_state.monsters[self.target_idx]
        if monster.is_dead():
            return []
        actual_damage = monster.take_damage(self.damage)
        _trigger_player_attack_damage_hooks(combat_state, source, monster, actual_damage, damage_type="NORMAL")
        if _is_true_kill_reward_target(monster):
            upgraded_card = _upgrade_first_upgradeable_card(combat_state, source_card=card)
            if upgraded_card is not None:
                card._upgraded_card_from_lesson_learned = upgraded_card
        return []


@dataclass
class ForeignInfluenceEffect:
    upgraded: bool = False

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        pool = [card_id for card_id in _implemented_attack_card_ids() if card_id != card.card_id]
        if not pool:
            return []
        rng = _combat_rng(combat_state)
        available = pool[:]
        candidate_ids: list[str] = []
        while available and len(candidate_ids) < 3:
            selected_index = rng.random_int(len(available) - 1) if rng is not None and len(available) > 1 else 0
            candidate_ids.append(available.pop(selected_index))
        generated_cards = [CardInstance(card_id) for card_id in candidate_ids]
        if len(generated_cards) == 1:
            _resolve_generated_choice_to_hand(
                combat_state,
                generated_cards[0],
                source_card=card,
                zero_cost_this_turn=self.upgraded,
            )
            return []
        _open_generated_single_pick(
            combat_state,
            card,
            choice_type="generated_single_pick",
            generated_cards=generated_cards,
            selection_action="foreign_influence_upgraded" if self.upgraded else "foreign_influence",
        )
        return []


@dataclass
class SpiritShieldEffect:
    block_per_card: int

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        card_manager = getattr(combat_state, "card_manager", None)
        hand_size = len(getattr(getattr(card_manager, "hand", None), "cards", []) or [])
        source.gain_block(max(0, hand_size * self.block_per_card))
        return []


@dataclass
class CollectEffect:
    upgraded: bool = False

    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        effect_turns = max(0, int(getattr(card, "_resolved_x_cost", 0) or 0)) + (1 if self.upgraded else 0)
        if effect_turns > 0:
            source.add_power(create_power("Collect", effect_turns, "player"))
        return []


@dataclass
class UnravelingEffect:
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        engine = getattr(combat_state, "engine", None)
        card_manager = getattr(combat_state, "card_manager", None)
        if engine is None or card_manager is None:
            return []
        queued_cards = [hand_card for hand_card in list(card_manager.hand.cards) if hand_card is not card]
        for queued_card in queued_cards:
            if queued_card not in card_manager.hand.cards:
                continue
            queued_card.free_to_play_once = True
            preferred_target_idx = engine._resolve_autoplay_target_idx(queued_card)
            engine.autoplay_card_instance(queued_card, preferred_target_idx)
        return []


@dataclass
class NoOpEffect:
    def execute(self, combat_state: CombatState, card: CardInstance, source: Player, target: MonsterBase | None) -> list[CardEffect]:
        return []

def get_card_effects(card: CardInstance, target_idx: int | None = None) -> list[CardEffect]:
    """Get the effects for playing a card.
    
    This maps card IDs to their effect lists based on Java card implementations.
    """
    effects: list[CardEffect] = []
    card_id = card.card_id
    
    if card_id in {"Strike", "Strike_P", "Strike_B"}:
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id in {"Defend", "Defend_P", "Defend_B"}:
        effects.append(GainBlockEffect(amount=card.block))

    elif card_id == "Zap":
        effects.append(ChannelOrbEffect(orb_type="Lightning", count=card.magic_number))

    elif card_id == "Dualcast":
        effects.append(DualcastEffect())

    elif card_id == "Miracle":
        effects.append(GainEnergyEffect(amount=2 if card.upgraded else 1))

    elif card_id == "Eruption":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
        effects.append(ChangeStanceEffect(stance_type=StanceType.WRATH))

    elif card_id == "Vigilance":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(ChangeStanceEffect(stance_type=StanceType.CALM))

    elif card_id == "BowlingBash":
        if target_idx is not None:
            effects.append(BowlingBashEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "Consecrate":
        effects.append(DealDamageAllEffect(damage=card.damage))

    elif card_id == "Crescendo":
        effects.append(ChangeStanceEffect(stance_type=StanceType.WRATH))

    elif card_id == "CrushJoints":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
            effects.append(
                ConditionalLastCardTypeApplyMonsterPowerEffect(
                    required_type=CardType.SKILL,
                    target_idx=target_idx,
                    power_type="Vulnerable",
                    amount=card.magic_number,
                )
            )

    elif card_id == "EmptyBody":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(ChangeStanceEffect(stance_type=StanceType.NEUTRAL))

    elif card_id == "EmptyFist":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
        effects.append(ChangeStanceEffect(stance_type=StanceType.NEUTRAL))

    elif card_id == "FlurryOfBlows":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "FlyingSleeves":
        if target_idx is not None:
            effects.append(DealDamageRepeatedEffect(target_idx=target_idx, damage=card.damage, hit_count=2))

    elif card_id == "FollowUp":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
        effects.append(ConditionalLastCardTypeGainEnergyEffect(required_type=CardType.ATTACK, amount=1))

    elif card_id == "Halt":
        effects.append(HaltEffect(base_block=card.block, wrath_bonus_block=card.magic_number))

    elif card_id == "PressurePoints":
        if target_idx is not None:
            effects.append(PressurePointsEffect(target_idx=target_idx, amount=card.magic_number))

    elif card_id == "Protect":
        effects.append(GainBlockEffect(amount=card.block))

    elif card_id == "SashWhip":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
            effects.append(
                ConditionalLastCardTypeApplyMonsterPowerEffect(
                    required_type=CardType.ATTACK,
                    target_idx=target_idx,
                    power_type="Weak",
                    amount=card.magic_number,
                )
            )

    elif card_id == "Tranquility":
        effects.append(ChangeStanceEffect(stance_type=StanceType.CALM))

    elif card_id == "Wallop":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
            effects.append(GainBlockFromLastDamageEffect())

    elif card_id == "Prostrate":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(GainMantraEffect(amount=card.magic_number))

    elif card_id == "Collect":
        effects.append(CollectEffect(upgraded=card.upgraded))

    elif card_id == "Conclude":
        effects.append(DealDamageAllEffect(damage=card.damage))
        effects.append(EndTurnEffect())

    elif card_id == "Devotion":
        effects.append(ApplyPowerEffect(power_type="Devotion", amount=card.magic_number, target_type="player"))

    elif card_id == "DevaForm":
        effects.append(ApplyPowerEffect(power_type="DevaPower", amount=card.magic_number, target_type="player"))

    elif card_id == "Discipline":
        effects.append(ApplyPowerEffect(power_type="Discipline", amount=1, target_type="player"))

    elif card_id == "EmptyMind":
        effects.append(DrawCardsEffect(count=card.magic_number))
        effects.append(ChangeStanceEffect(stance_type=StanceType.NEUTRAL))

    elif card_id == "Establishment":
        effects.append(ApplyPowerEffect(power_type="Establishment", amount=card.magic_number if card.magic_number > 0 else 1, target_type="player"))

    elif card_id == "Fasting":
        effects.append(ApplyPowerEffect(power_type="Strength", amount=card.magic_number, target_type="player"))
        effects.append(ApplyPowerEffect(power_type="Dexterity", amount=card.magic_number, target_type="player"))
        effects.append(ApplyPowerEffect(power_type="Fasting", amount=1, target_type="player"))

    elif card_id == "FearNoEvil":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
            effects.append(ConditionalAttackIntentChangeStanceEffect(target_idx=target_idx, stance_type=StanceType.CALM))

    elif card_id == "ForeignInfluence":
        effects.append(ForeignInfluenceEffect(upgraded=card.upgraded))

    elif card_id == "Insight":
        effects.append(DrawCardsEffect(count=card.magic_number))

    elif card_id == "Study":
        effects.append(ApplyPowerEffect(power_type="Study", amount=card.magic_number, target_type="player"))

    elif card_id == "MasterReality":
        effects.append(ApplyPowerEffect(power_type="MasterReality", amount=1, target_type="player"))

    elif card_id == "BattleHymn":
        effects.append(ApplyPowerEffect(power_type="BattleHymn", amount=card.magic_number, target_type="player"))

    elif card_id == "Alpha":
        effects.append(MakeTempCardInDrawPileEffect(card_id="Beta", count=1, shuffle_into=True))

    elif card_id == "Beta":
        effects.append(MakeTempCardInDrawPileEffect(card_id="Omega", count=1, shuffle_into=True))

    elif card_id == "Omega":
        effects.append(ApplyPowerEffect(power_type="OmegaPower", amount=card.magic_number, target_type="player"))

    elif card_id == "ConjureBlade":
        effects.append(ConjureBladeEffect())

    elif card_id == "Expunger":
        effects.append(ExpungerEffect(target_idx=target_idx, damage=card.damage, hit_count=card.magic_number))

    elif card_id == "Pray":
        effects.append(GainMantraEffect(amount=card.magic_number))
        effects.append(MakeTempCardInDrawPileEffect(card_id="Insight", count=1, shuffle_into=True))

    elif card_id == "Evaluate":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(MakeTempCardInDrawPileEffect(card_id="Insight", count=1, shuffle_into=True))

    elif card_id == "CarveReality":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage, attack_effect=AttackEffect.SLASH_HEAVY))
        effects.append(GenerateCardsToHandEffect(card_id="Smite", count=1))

    elif card_id == "DeceiveReality":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(GenerateCardsToHandEffect(card_id="Safety", count=1))

    elif card_id == "ReachHeaven":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage, attack_effect=AttackEffect.SLASH_HEAVY))
        effects.append(MakeTempCardInDrawPileEffect(card_id="ThroughViolence", count=1, shuffle_into=True))

    elif card_id == "ThirdEye":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(ScryEffect(count=card.magic_number))

    elif card_id == "JustLucky":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(ScryEffect(count=card.magic_number))

    elif card_id == "CutThroughFate":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
        effects.append(ScryEffect(count=card.magic_number))
        effects.append(DrawCardsEffect(count=1))

    elif card_id == "Foresight":
        effects.append(ApplyPowerEffect(power_type="Foresight", amount=card.magic_number, target_type="player"))

    elif card_id == "Weave":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "Meditate":
        effects.append(RecoverFromDiscardEffect(count=card.magic_number))
        effects.append(ChangeStanceEffect(stance_type=StanceType.CALM))
        effects.append(EndTurnEffect())

    elif card_id == "InnerPeace":
        effects.append(InnerPeaceEffect(draw_count=card.magic_number))

    elif card_id == "Indignation":
        effects.append(IndignationEffect(amount=card.magic_number))

    elif card_id == "Judgement":
        if target_idx is not None:
            effects.append(JudgementEffect(target_idx=target_idx, threshold=card.magic_number))

    elif card_id == "LessonLearned":
        if target_idx is not None:
            effects.append(LessonLearnedEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "LikeWater":
        effects.append(ApplyPowerEffect(power_type="LikeWater", amount=card.magic_number, target_type="player"))

    elif card_id == "MentalFortress":
        effects.append(ApplyPowerEffect(power_type="MentalFortress", amount=card.magic_number, target_type="player"))

    elif card_id == "Nirvana":
        effects.append(ApplyPowerEffect(power_type="Nirvana", amount=card.magic_number, target_type="player"))

    elif card_id == "Rushdown":
        effects.append(ApplyPowerEffect(power_type="Rushdown", amount=card.magic_number, target_type="player"))

    elif card_id == "Perseverance":
        effects.append(GainBlockEffect(amount=card.block))

    elif card_id == "Sanctity":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(ConditionalLastCardTypeDrawEffect(required_type=CardType.SKILL, amount=card.magic_number))

    elif card_id == "SandsOfTime":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "SignatureMove":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "SimmeringFury":
        effects.append(ApplyPowerEffect(power_type="SimmeringFury", amount=card.magic_number, target_type="player"))

    elif card_id == "SpiritShield":
        effects.append(SpiritShieldEffect(block_per_card=card.magic_number))

    elif card_id == "Swivel":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(ApplyPowerEffect(power_type="Swivel", amount=1, target_type="player"))

    elif card_id == "Blasphemy":
        effects.append(ChangeStanceEffect(stance_type=StanceType.DIVINITY))
        effects.append(ApplyPowerEffect(power_type="EndTurnDeath", amount=1, target_type="player"))

    elif card_id == "Vault":
        effects.append(SkipEnemyTurnEffect())
        effects.append(EndTurnEffect())

    elif card_id == "Wish":
        effects.append(OpenCombatChoiceEffect(choice_type="wish"))

    elif card_id == "Omniscience":
        effects.append(OpenCombatChoiceEffect(choice_type="omniscience"))

    elif card_id == "Scrawl":
        effects.append(DrawToHandLimitEffect())

    elif card_id == "TalkToTheHand":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
            effects.append(ApplyPowerEffect(power_type="TalkToTheHand", amount=card.magic_number, target_type="monster", target_idx=target_idx))

    elif card_id == "Tantrum":
        if target_idx is not None:
            effects.append(DealDamageRepeatedEffect(target_idx=target_idx, damage=card.damage, hit_count=card.magic_number))
        effects.append(ChangeStanceEffect(stance_type=StanceType.WRATH))
        card.shuffle_back_into_draw_pile = True

    elif card_id == "Safety":
        effects.append(GainBlockEffect(amount=card.block))

    elif card_id == "Smite":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "ThroughViolence":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "Unraveling":
        effects.append(UnravelingEffect())

    elif card_id == "WaveOfTheHand":
        effects.append(ApplyPowerEffect(power_type="WaveOfTheHand", amount=card.magic_number, target_type="player"))

    elif card_id == "WheelKick":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
        effects.append(DrawCardsEffect(count=card.magic_number))

    elif card_id == "WindmillStrike":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "Worship":
        effects.append(GainMantraEffect(amount=card.magic_number))

    elif card_id == "WreathOfFlame":
        effects.append(ApplyPowerEffect(power_type="WreathOfFlame", amount=card.magic_number, target_type="player"))

    elif card_id == "Brilliance":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "Ragnarok":
        effects.append(DealDamageRandomEnemyRepeatedEffect(damage=card.damage, hit_count=card.magic_number))

    elif card_id == "Madness":
        effects.append(MadnessEffect())

    elif card_id == "BandageUp":
        effects.append(HealEffect(amount=card.magic_number))

    elif card_id == "DramaticEntrance":
        effects.append(DealDamageAllEffect(damage=card.damage))

    elif card_id == "Discovery":
        effects.append(DiscoveryEffect())

    elif card_id == "Enlightenment":
        effects.append(EnlightenmentEffect(permanent_for_combat=card.upgraded))

    elif card_id == "Forethought":
        effects.append(ForethoughtEffect(allow_multiple=card.upgraded))

    elif card_id == "Impatience":
        effects.append(ConditionalNoAttackDrawEffect(draw_count=card.magic_number))

    elif card_id == "JAX":
        effects.append(LoseHPEffect(amount=3))
        effects.append(ApplyPowerEffect(power_type="Strength", amount=card.magic_number, target_type="player"))

    elif card_id == "JackOfAllTrades":
        effects.append(JackOfAllTradesEffect(count=card.magic_number))

    elif card_id == "Magnetism":
        effects.append(ApplyPowerEffect(power_type="Magnetism", amount=card.magic_number, target_type="player"))

    elif card_id == "MasterOfStrategy":
        effects.append(DrawCardsEffect(count=card.magic_number))

    elif card_id == "Mayhem":
        effects.append(ApplyPowerEffect(power_type="Mayhem", amount=card.magic_number, target_type="player"))

    elif card_id == "MindBlast":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage, attack_effect=AttackEffect.NONE))

    elif card_id == "Panache":
        effects.append(ApplyPowerEffect(power_type="Panache", amount=card.magic_number, target_type="player"))

    elif card_id == "Purity":
        effects.append(PurityEffect(max_exhaust=card.magic_number))

    elif card_id == "Apotheosis":
        effects.append(ApotheosisEffect())

    elif card_id == "Bite":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
        effects.append(HealEffect(amount=card.magic_number))

    elif card_id == "Apparition":
        effects.append(ApplyPowerEffect(power_type="Intangible", amount=1, target_type="player"))

    elif card_id == "Blind":
        if card.upgraded:
            effects.append(ApplyPowerEffect(power_type="Weak", amount=card.magic_number, target_type="all_monsters"))
        elif target_idx is not None:
            effects.append(ApplyPowerEffect(power_type="Weak", amount=card.magic_number, target_type="monster", target_idx=target_idx))

    elif card_id == "DeepBreath":
        effects.append(DeepBreathEffect(draw_count=card.magic_number))

    elif card_id == "Finesse":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(DrawCardsEffect(count=1))

    elif card_id == "FlashOfSteel":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
        effects.append(DrawCardsEffect(count=1))

    elif card_id == "GoodInstincts":
        effects.append(GainBlockEffect(amount=card.block))

    elif card_id == "HandOfGreed":
        if target_idx is not None:
            effects.append(HandOfGreedEffect(target_idx=target_idx, damage=card.damage, gold_gain=card.magic_number))

    elif card_id == "Panacea":
        effects.append(ApplyPowerEffect(power_type="Artifact", amount=card.magic_number, target_type="player"))

    elif card_id == "Trip":
        if target_idx is not None:
            effects.append(ApplyPowerEffect(power_type="Vulnerable", amount=card.magic_number, target_type="monster", target_idx=target_idx))

    elif card_id == "DarkShackles":
        if target_idx is not None:
            effects.append(TemporaryStrengthDownEffect(amount=card.magic_number, target_idx=target_idx))

    elif card_id == "SwiftStrike":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "PanicButton":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(ApplyPowerEffect(power_type="NoBlock", amount=card.magic_number, target_type="player"))

    elif card_id == "Pride":
        effects.append(NoOpEffect())

    elif card_id == "RitualDagger":
        if target_idx is not None:
            effects.append(RitualDaggerEffect(target_idx=target_idx, damage=card.damage, growth=card.magic_number))

    elif card_id == "SadisticNature":
        effects.append(ApplyPowerEffect(power_type="Sadistic", amount=card.magic_number, target_type="player"))

    elif card_id == "Chrysalis":
        effects.append(RandomCombatCardsToDrawPileEffect(count=card.magic_number, pool_type=CardType.SKILL))

    elif card_id == "Metamorphosis":
        effects.append(RandomCombatCardsToDrawPileEffect(count=card.magic_number, pool_type=CardType.ATTACK))

    elif card_id == "TheBomb":
        effects.append(TheBombEffect(turns=3, damage=card.magic_number))

    elif card_id == "Transmutation":
        effects.append(TransmutationEffect())

    elif card_id == "Violence":
        effects.append(RandomDrawPileTypeToHandEffect(count=card.magic_number, card_type=CardType.ATTACK))

    elif card_id == "SecretTechnique":
        effects.append(DrawPileTutorEffect(card_type=CardType.SKILL, selection_action="secret_technique"))

    elif card_id == "SecretWeapon":
        effects.append(DrawPileTutorEffect(card_type=CardType.ATTACK, selection_action="secret_weapon"))

    elif card_id == "ThinkingAhead":
        effects.append(ThinkingAheadEffect(draw_count=2))

    elif card_id == "Neutralize":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
            effects.append(ApplyPowerEffect(power_type="Weak", amount=card.magic_number, target_type="monster", target_idx=target_idx))

    elif card_id == "Shiv":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "Survivor":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(DiscardDeterministicHandCardEffect())

    elif card_id == "CloakAndDagger":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(GenerateCardsToHandEffect(card_id="Shiv", count=card.magic_number))

    elif card_id == "BladeDance":
        effects.append(GenerateCardsToHandEffect(card_id="Shiv", count=card.magic_number))

    elif card_id == "Prepared":
        effects.append(DrawCardsEffect(count=card.magic_number))
        effects.append(DiscardDeterministicHandCardEffect(count=card.magic_number))

    elif card_id == "Acrobatics":
        effects.append(DrawCardsEffect(count=card.magic_number))
        effects.append(DiscardDeterministicHandCardEffect(count=1))

    elif card_id == "Distraction":
        effects.append(DistractionEffect())

    elif card_id == "EscapePlan":
        effects.append(EscapePlanEffect(block_amount=card.block))

    elif card_id == "BulletTime":
        effects.append(BulletTimeEffect())

    elif card_id == "Bane":
        if target_idx is not None:
            effects.append(BaneEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "DaggerSpray":
        effects.append(DaggerSprayEffect(damage=card.damage))

    elif card_id == "Outmaneuver":
        effects.append(ApplyPowerEffect(power_type="Energized", amount=2 if not card.upgraded else 3, target_type="player"))

    elif card_id == "Setup":
        effects.append(SetupEffect())

    elif card_id == "InfiniteBlades":
        effects.append(InfiniteBladesEffect())

    elif card_id == "Accuracy":
        effects.append(ApplyPowerEffect(power_type="Accuracy", amount=card.magic_number, target_type="player"))

    elif card_id == "Finisher":
        if target_idx is not None:
            effects.append(FinisherEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "Expertise":
        effects.append(DrawToHandCountEffect(count=card.magic_number))

    elif card_id == "WellLaidPlans":
        effects.append(ApplyPowerEffect(power_type="Retain Cards", amount=card.magic_number, target_type="player"))

    elif card_id == "Backstab":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage, attack_effect=AttackEffect.SLASH_HEAVY))

    elif card_id == "Caltrops":
        effects.append(ApplyPowerEffect(power_type="Thorns", amount=card.magic_number, target_type="player"))

    elif card_id == "Choke":
        if target_idx is not None:
            effects.append(ChokeAttackEffect(target_idx=target_idx, damage=card.damage, choke_amount=card.magic_number))

    elif card_id == "AllOutAttack":
        effects.append(AllOutAttackEffect(damage=card.damage))

    elif card_id == "Predator":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage, attack_effect=AttackEffect.SLASH_HEAVY))
        effects.append(ApplyPowerEffect(power_type="Draw Card", amount=2, target_type="player"))

    elif card_id == "Skewer":
        if target_idx is not None:
            effects.append(SkewerEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "Burst":
        effects.append(ApplyPowerEffect(power_type="Burst", amount=card.magic_number, target_type="player"))

    elif card_id == "Nightmare":
        effects.append(NightmareEffect(copies=card.magic_number))

    elif card_id == "Envenom":
        effects.append(ApplyPowerEffect(power_type="Envenom", amount=1, target_type="player"))

    elif card_id == "ThousandCuts":
        effects.append(ApplyPowerEffect(power_type="ThousandCuts", amount=card.magic_number, target_type="player"))

    elif card_id == "AfterImage":
        effects.append(ApplyPowerEffect(power_type="AfterImage", amount=1, target_type="player"))

    elif card_id == "BallLightning":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
        effects.append(ChannelOrbEffect(orb_type="Lightning", count=card.magic_number))

    elif card_id == "ColdSnap":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
        effects.append(ChannelOrbEffect(orb_type="Frost", count=card.magic_number))

    elif card_id == "Coolheaded":
        effects.append(ChannelOrbEffect(orb_type="Frost", count=1))
        effects.append(DrawCardsEffect(count=card.magic_number))

    elif card_id == "CompileDriver":
        if target_idx is not None:
            effects.append(CompileDriverEffect(target_idx=target_idx, damage=card.damage, draw_count=card.magic_number))

    elif card_id == "GoForTheEyes":
        if target_idx is not None:
            effects.append(GoForTheEyesEffect(target_idx=target_idx, damage=card.damage, weak_amount=card.magic_number))

    elif card_id == "BeamCell":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
            effects.append(ApplyPowerEffect(power_type="Vulnerable", amount=card.magic_number, target_type="monster", target_idx=target_idx))

    elif card_id == "Recursion":
        effects.append(RecursionEffect())

    elif card_id == "Turbo":
        effects.append(TurboEffect(amount=card.magic_number))
        effects.append(MakeTempCardInDiscardEffect(card_id="Void", count=1))

    elif card_id == "ConserveBattery":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(ApplyPowerEffect(power_type="EnergizedBlue", amount=1, target_type="player"))

    elif card_id == "Deflect":
        effects.append(GainBlockEffect(amount=card.block))

    elif card_id == "DodgeAndRoll":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(ApplyPowerEffect(power_type="Next Turn Block", amount=card.block, target_type="player"))

    elif card_id == "FlyingKnee":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage, attack_effect=AttackEffect.BLUNT_HEAVY))
        effects.append(ApplyPowerEffect(power_type="Energized", amount=1, target_type="player"))

    elif card_id == "Claw":
        if target_idx is not None:
            effects.append(ClawEffect(target_idx=target_idx, damage=card.damage, damage_growth=card.magic_number))

    elif card_id == "Fusion":
        effects.append(ChannelOrbEffect(orb_type="Plasma", count=card.magic_number))

    elif card_id == "SweepingBeam":
        effects.append(DealDamageAllEffect(damage=card.damage))
        effects.append(DrawCardsEffect(count=card.magic_number))

    elif card_id == "FTL":
        if target_idx is not None:
            effects.append(FTLEffect(target_idx=target_idx, damage=card.damage, card_play_threshold=card.magic_number))

    elif card_id == "Defragment":
        effects.append(ApplyPowerEffect(power_type="Focus", amount=card.magic_number, target_type="player"))

    elif card_id == "Blizzard":
        effects.append(DealDamageAllEffect(damage=card.damage, attack_effect=AttackEffect.BLUNT_HEAVY))

    elif card_id == "Bullseye":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
            effects.append(ApplyPowerEffect(power_type="Lockon", amount=card.magic_number, target_type="monster", target_idx=target_idx))

    elif card_id == "CoreSurge":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
        effects.append(ApplyPowerEffect(power_type="Artifact", amount=card.magic_number, target_type="player"))

    elif card_id == "Barrage":
        if target_idx is not None:
            effects.append(BarrageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "Hologram":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(RecoverFromDiscardEffect(count=1, temporary_retain=False))

    elif card_id == "Rebound":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
        effects.append(ApplyPowerEffect(power_type="Rebound", amount=1, target_type="player"))

    elif card_id == "Streamline":
        if target_idx is not None:
            effects.append(StreamlineEffect(target_idx=target_idx, damage=card.damage, cost_reduction=card.magic_number))

    elif card_id == "Leap":
        effects.append(GainBlockEffect(amount=card.block))

    elif card_id == "Darkness":
        effects.append(ChannelOrbEffect(orb_type="Dark", count=1))
        if card.upgraded:
            effects.append(DarkImpulseEffect(amount=1))

    elif card_id == "Chill":
        effects.append(ChillEffect())

    elif card_id == "DoomAndGloom":
        effects.append(DealDamageAllEffect(damage=card.damage))
        effects.append(ChannelOrbEffect(orb_type="Dark", count=card.magic_number))

    elif card_id == "Loop":
        effects.append(ApplyPowerEffect(power_type="Loop", amount=card.magic_number, target_type="player"))

    elif card_id == "Consume":
        effects.append(ConsumeEffect(focus_amount=card.magic_number, slot_loss=1))

    elif card_id == "Tempest":
        effects.append(TempestEffect(extra_channels=1 if card.upgraded else 0))

    elif card_id == "DoubleEnergy":
        effects.append(DoubleEnergyEffect())

    elif card_id == "Recycle":
        effects.append(RecycleEffect())

    elif card_id == "Capacitor":
        effects.append(IncreaseOrbSlotsEffect(amount=card.magic_number))

    elif card_id == "Equilibrium":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(ApplyPowerEffect(power_type="Equilibrium", amount=card.magic_number, target_type="player"))

    elif card_id == "ForceField":
        effects.append(GainBlockEffect(amount=card.block))

    elif card_id == "Buffer":
        effects.append(ApplyPowerEffect(power_type="Buffer", amount=card.magic_number, target_type="player"))

    elif card_id == "Glacier":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(ChannelOrbEffect(orb_type="Frost", count=card.magic_number))

    elif card_id == "GeneticAlgorithm":
        effects.append(GeneticAlgorithmEffect(amount=card.block, block_growth=card.magic_number))

    elif card_id == "HelloWorld":
        effects.append(ApplyPowerEffect(power_type="Hello", amount=1, target_type="player"))

    elif card_id == "Stack":
        effects.append(StackEffect(upgraded_bonus=3 if card.upgraded else 0))

    elif card_id == "Skim":
        effects.append(DrawCardsEffect(count=card.magic_number))

    elif card_id == "Seek":
        effects.append(MoveDrawPileTopToHandEffect(count=card.magic_number))

    elif card_id == "Aggregate":
        effects.append(AggregateEffect(divisor=card.magic_number))

    elif card_id == "AutoShields":
        effects.append(AutoShieldsEffect(amount=card.block))

    elif card_id == "BootSequence":
        effects.append(GainBlockEffect(amount=card.block))

    elif card_id == "WhiteNoise":
        effects.append(WhiteNoiseEffect())

    elif card_id == "Chaos":
        effects.append(ChaosEffect(count=card.magic_number))

    elif card_id == "Overclock":
        effects.append(DrawCardsEffect(count=card.magic_number))
        effects.append(MakeTempCardInDiscardEffect(card_id="Burn", count=1))

    elif card_id == "CreativeAI":
        effects.append(ApplyPowerEffect(power_type="CreativeAI", amount=card.magic_number, target_type="player"))

    elif card_id == "ToolsOfTheTrade":
        effects.append(ApplyPowerEffect(power_type="Tools Of The Trade", amount=1, target_type="player"))

    elif card_id == "Lockon":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
            effects.append(ApplyPowerEffect(power_type="Lockon", amount=card.magic_number, target_type="monster", target_idx=target_idx))

    elif card_id == "Tempest":
        effects.append(TempestEffect(extra_channels=1 if card.upgraded else 0))

    elif card_id == "ReinforcedBody":
        effects.append(ReinforcedBodyEffect(block_per_energy=card.block))

    elif card_id == "Fission":
        effects.append(FissionEffect(upgraded=card.upgraded))

    elif card_id == "MultiCast":
        effects.append(MultiCastEffect(extra_evokes=1 if card.upgraded else 0))

    elif card_id == "Rainbow":
        effects.append(ChannelOrbEffect(orb_type="Lightning", count=1))
        effects.append(ChannelOrbEffect(orb_type="Frost", count=1))
        effects.append(ChannelOrbEffect(orb_type="Dark", count=1))

    elif card_id == "MeteorStrike":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
        effects.append(ChannelOrbEffect(orb_type="Plasma", count=card.magic_number))

    elif card_id == "Storm":
        effects.append(ApplyPowerEffect(power_type="Storm", amount=card.magic_number, target_type="player"))

    elif card_id == "Heatsinks":
        effects.append(ApplyPowerEffect(power_type="Heatsinks", amount=card.magic_number, target_type="player"))

    elif card_id == "StaticDischarge":
        effects.append(ApplyPowerEffect(power_type="StaticDischarge", amount=card.magic_number, target_type="player"))

    elif card_id == "Melter":
        if target_idx is not None:
            effects.append(MelterEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "RipAndTear":
        for _ in range(card.magic_number):
            effects.append(DealDamageToRandomEffect(damage=card.damage))

    elif card_id == "MachineLearning":
        effects.append(ApplyPowerEffect(power_type="MachineLearning", amount=card.magic_number, target_type="player"))

    elif card_id == "SelfRepair":
        effects.append(ApplyPowerEffect(power_type="Repair", amount=card.magic_number, target_type="player"))

    elif card_id == "Reprogram":
        effects.append(ApplyPowerEffect(power_type="Focus", amount=-card.magic_number, target_type="player"))
        effects.append(ApplyPowerEffect(power_type="Strength", amount=card.magic_number, target_type="player"))
        effects.append(ApplyPowerEffect(power_type="Dexterity", amount=card.magic_number, target_type="player"))

    elif card_id == "Reboot":
        effects.append(RebootEffect(draw_count=card.magic_number))

    elif card_id == "Sunder":
        if target_idx is not None:
            effects.append(SunderEffect(target_idx=target_idx, damage=card.damage, energy_gain=3))

    elif card_id == "Scrape":
        if target_idx is not None:
            effects.append(ScrapeEffect(target_idx=target_idx, damage=card.damage, draw_count=card.magic_number))

    elif card_id == "SteamBarrier":
        effects.append(SteamBarrierEffect(amount=card.block))

    elif card_id == "Electrodynamics":
        effects.append(ApplyPowerEffect(power_type="Electro", amount=1, target_type="player"))
        effects.append(ChannelOrbEffect(orb_type="Lightning", count=card.magic_number))

    elif card_id == "BiasedCognition":
        effects.append(ApplyPowerEffect(power_type="Focus", amount=card.magic_number, target_type="player"))
        effects.append(ApplyPowerEffect(power_type="Bias", amount=1, target_type="player"))

    elif card_id == "AllForOne":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage, attack_effect=AttackEffect.BLUNT_HEAVY))
        effects.append(RecoverAllDiscardZeroCostEffect())

    elif card_id == "Amplify":
        effects.append(ApplyPowerEffect(power_type="Amplify", amount=card.magic_number, target_type="player"))

    elif card_id == "EchoForm":
        effects.append(ApplyPowerEffect(power_type="EchoForm", amount=1, target_type="player"))

    elif card_id == "Hyperbeam":
        effects.append(DealDamageAllEffect(damage=card.damage))
        effects.append(ApplyPowerEffect(power_type="Focus", amount=-card.magic_number, target_type="player"))

    elif card_id == "WraithForm":
        effects.append(ApplyPowerEffect(power_type="Intangible", amount=card.magic_number, target_type="player"))
        effects.append(ApplyPowerEffect(power_type="WraithForm", amount=-1, target_type="player"))

    elif card_id == "GrandFinale":
        effects.append(DealDamageAllEffect(damage=card.damage, attack_effect=AttackEffect.SLASH_HEAVY))

    elif card_id == "PhantasmalKiller":
        effects.append(ApplyPowerEffect(power_type="Phantasmal", amount=1, target_type="player"))

    elif card_id == "Doppelganger":
        effects.append(DoppelgangerEffect(upgraded=card.upgraded))

    elif card_id == "StormOfSteel":
        effects.append(StormOfSteelEffect(upgraded=card.upgraded))

    elif card_id == "Alchemize":
        effects.append(AlchemizeEffect())

    elif card_id == "Footwork":
        effects.append(ApplyPowerEffect(power_type="Dexterity", amount=card.magic_number, target_type="player"))

    elif card_id == "LegSweep":
        if target_idx is not None:
            effects.append(GainBlockEffect(amount=card.block))
            effects.append(ApplyPowerEffect(power_type="Weak", amount=card.magic_number, target_type="monster", target_idx=target_idx))

    elif card_id == "PiercingWail":
        effects.append(TemporaryStrengthDownEffect(amount=card.magic_number, target_all=True))

    elif card_id == "Terror":
        if target_idx is not None:
            effects.append(ApplyPowerEffect(power_type="Vulnerable", amount=card.magic_number, target_type="monster", target_idx=target_idx))

    elif card_id == "Malaise":
        if target_idx is not None:
            effects.append(MalaiseEffect(target_idx=target_idx))

    elif card_id == "DaggerThrow":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
        effects.append(DiscardDeterministicHandCardEffect(count=1))

    elif card_id == "SneakyStrike":
        if target_idx is not None:
            effects.append(SneakyStrikeEffect(damage=card.damage, energy_gain=2))

    elif card_id == "Eviscerate":
        if target_idx is not None:
            for _ in range(card.magic_number):
                effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "Concentrate":
        effects.append(ConcentrateEffect(discard_count=card.magic_number, energy_gain=2))

    elif card_id == "CalculatedGamble":
        effects.append(CalculatedGambleEffect())

    elif card_id == "Slice":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "Slimed":
        effects.append(NoOpEffect())

    elif card_id == "QuickSlash":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
            effects.append(DrawCardsEffect(count=1))

    elif card_id == "SuckerPunch":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
            effects.append(ApplyPowerEffect(power_type="Weak", amount=card.magic_number, target_type="monster", target_idx=target_idx))

    elif card_id == "Backflip":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(DrawCardsEffect(count=2))

    elif card_id == "Dash":
        if target_idx is not None:
            effects.append(GainBlockEffect(amount=card.block))
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "Adrenaline":
        effects.append(DrawCardsEffect(count=2))
        effects.append(GainEnergyEffect(amount=1))

    elif card_id == "DieDieDie":
        effects.append(DealDamageAllEffect(damage=card.damage))

    elif card_id == "DeadlyPoison":
        if target_idx is not None:
            effects.append(ApplyPoisonEffect(amount=card.magic_number, target_idx=target_idx))

    elif card_id == "PoisonedStab":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
            effects.append(ApplyPoisonEffect(amount=card.magic_number, target_idx=target_idx))

    elif card_id == "BouncingFlask":
        effects.append(BouncingFlaskEffect(hit_count=card.magic_number, poison_amount=3))

    elif card_id == "NoxiousFumes":
        effects.append(ApplyPowerEffect(power_type="NoxiousFumes", amount=card.magic_number, target_type="player"))

    elif card_id == "Catalyst":
        if target_idx is not None:
            effects.append(CatalystEffect(target_idx=target_idx, multiplier=3 if card.upgraded else 2))

    elif card_id == "CripplingCloud":
        effects.append(CripplingCloudEffect(poison_amount=card.magic_number, weak_amount=2))

    elif card_id == "CorpseExplosion":
        if target_idx is not None:
            effects.append(CorpseExplosionEffect(target_idx=target_idx, poison_amount=card.magic_number))

    elif card_id == "Bash":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage, attack_effect=AttackEffect.BLUNT_HEAVY))
            effects.append(ApplyPowerEffect(power_type="Vulnerable", amount=card.magic_number, target_type="monster", target_idx=target_idx))
    
    elif card_id == "Anger":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
            effects.append(MakeCardEffect())
    
    elif card_id == "Clothesline":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
            effects.append(ApplyPowerEffect(power_type="Weak", amount=2 if not card.upgraded else 3, target_type="monster", target_idx=target_idx))
    
    elif card_id == "Cleave":
        effects.append(DealDamageAllEffect(damage=card.damage))
    
    elif card_id == "IronWave":
        if target_idx is not None:
            effects.append(GainBlockEffect(amount=card.block))
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
    
    elif card_id == "PerfectedStrike":
        if target_idx is not None:
            effects.append(PerfectedStrikeEffect(target_idx=target_idx, base_damage=card.damage))

    elif card_id == "PommelStrike":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
            effects.append(DrawCardsEffect(count=card.magic_number if card.magic_number > 0 else 1))
    
    elif card_id == "Thunderclap":
        effects.append(DealDamageAllEffect(damage=card.damage))
        effects.append(
            ApplyPowerEffect(
                power_type="Vulnerable",
                amount=1 if not card.upgraded else 2,
                target_type="all_monsters",
            )
        )

    elif card_id == "TwinStrike":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "SwordBoomerang":
        hit_count = card.magic_number if card.magic_number > 0 else 3
        for _ in range(hit_count if not card.upgraded else 4):
            effects.append(DealDamageToRandomEffect(damage=card.damage))
    
    elif card_id == "Headbutt":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
            effects.append(DiscardToTopEffect())
    
    elif card_id == "ShrugItOff":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(DrawCardsEffect(count=1))
    
    elif card_id == "Armaments":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(UpgradeHandCardEffect())
    
    elif card_id == "Flex":
        effects.append(ApplyPowerEffect(power_type="Flex", amount=card.magic_number, target_type="player"))
    
    elif card_id == "HeavyBlade":
        if target_idx is not None:
            multiplier = 5 if card.upgraded else 3
            effects.append(DealDamageWithStrengthEffect(target_idx=target_idx, damage=card.damage, strength_multiplier=multiplier))
    
    elif card_id == "WildStrike":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
            effects.append(AddCardToDrawPileEffect(card_to_add="Wound"))
    
    elif card_id == "BodySlam":
        if target_idx is not None:
            effects.append(BodySlamEffect(target_idx=target_idx))
    
    elif card_id == "Clash":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
    
    elif card_id == "TrueGrit":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(ExhaustDeterministicHandCardEffect())
    
    elif card_id == "Havoc":
        effects.append(HavocEffect(target_idx=target_idx))
    
    elif card_id == "Warcry":
        effects.append(WarcryEffect(draw_count=card.magic_number))

    elif card_id == "Inflame":
        effects.append(ApplyPowerEffect(power_type="Strength", amount=card.magic_number if card.magic_number > 0 else 2, target_type="player"))

    elif card_id == "Combust":
        effects.append(ApplyPowerEffect(power_type="Combust", amount=card.magic_number, target_type="player"))

    elif card_id == "Metallicize":
        effects.append(ApplyPowerEffect(power_type="Metallicize", amount=card.magic_number, target_type="player"))

    elif card_id == "DemonForm":
        effects.append(ApplyPowerEffect(power_type="DemonForm", amount=card.magic_number, target_type="player"))

    elif card_id == "Berserk":
        effects.append(ApplyPowerEffect(power_type="Vulnerable", amount=2 if not card.upgraded else 1, target_type="player"))
        effects.append(ApplyPowerEffect(power_type="Enrage", amount=1, target_type="player"))

    elif card_id == "FireBreathing":
        effects.append(ApplyPowerEffect(power_type="FireBreathing", amount=card.magic_number, target_type="player"))

    elif card_id == "Evolve":
        effects.append(ApplyPowerEffect(power_type="Evolve", amount=card.magic_number, target_type="player"))

    elif card_id == "FeelNoPain":
        effects.append(ApplyPowerEffect(power_type="FeelNoPain", amount=card.magic_number, target_type="player"))

    elif card_id == "DarkEmbrace":
        effects.append(ApplyPowerEffect(power_type="DarkEmbrace", amount=card.magic_number, target_type="player"))

    elif card_id == "FlameBarrier":
        effects.append(FlameBarrierEffect(block_amount=card.block, thorns_damage=card.magic_number if card.magic_number > 0 else 4))

    elif card_id == "GhostlyArmor":
        effects.append(GainBlockEffect(amount=card.block))

    elif card_id == "Barricade":
        effects.append(SetBlockFlagEffect(flag="barricade", value=True))

    elif card_id == "Blur":
        effects.append(GainBlockEffect(amount=card.block))
        effects.append(ApplyPowerEffect(power_type="Blur", amount=1, target_type="player"))

    elif card_id == "Bloodletting":
        effects.append(LoseHPEffect(amount=3))
        effects.append(GainEnergyEffect(amount=card.magic_number if card.magic_number > 0 else (3 if card.upgraded else 2)))

    elif card_id == "BattleTrance":
        effects.append(BattleTranceEffect(draw_count=card.magic_number if card.magic_number > 0 else (4 if card.upgraded else 3)))

    elif card_id == "BloodforBlood":
        effects.append(BloodForBloodEffect(damage=card.damage))

    elif card_id == "BurningPact":
        effects.append(BurningPactEffect(draw_count=2 if not card.upgraded else 3))

    elif card_id == "Carnage":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "Disarm":
        if target_idx is not None:
            effects.append(ApplyPowerEffect(power_type="StrengthDown", amount=2 if not card.upgraded else 3, target_type="monster", target_idx=target_idx))

    elif card_id == "Dropkick":
        if target_idx is not None:
            effects.append(DropkickEffect(damage=card.damage, energy_gain=1, draw_count=1))

    elif card_id == "EndlessAgony":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "Flechettes":
        if target_idx is not None:
            effects.append(FlechettesEffect(damage=card.damage))

    elif card_id == "GlassKnife":
        if target_idx is not None:
            effects.append(GlassKnifeEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "HeelHook":
        if target_idx is not None:
            effects.append(HeelHookEffect(damage=card.damage, energy_gain=1, draw_count=1))

    elif card_id == "MasterfulStab":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage, attack_effect=AttackEffect.SLASH_HEAVY))

    elif card_id == "RiddleWithHoles":
        if target_idx is not None:
            effects.append(RiddleWithHolesEffect(target_idx=target_idx, damage=card.damage, hit_count=5))

    elif card_id == "Unload":
        if target_idx is not None:
            effects.append(UnloadEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "DualWield":
        effects.append(DualWieldEffect(copies=card.magic_number if card.magic_number > 0 else (2 if card.upgraded else 1)))

    elif card_id == "Entrench":
        effects.append(EntrenchEffect())

    elif card_id == "Hemokinesis":
        if target_idx is not None:
            effects.append(HemokinesisEffect(damage=card.damage, hp_loss=2))

    elif card_id == "InfernalBlade":
        effects.append(InfernalBladeEffect())

    elif card_id == "Intimidate":
        effects.append(IntimidateEffect(weak_amount=1 if not card.upgraded else 2))

    elif card_id == "PowerThrough":
        effects.append(PowerThroughEffect(block_amount=15 if not card.upgraded else 20))

    elif card_id == "Pummel":
        if target_idx is not None:
            hit_count = card.magic_number if card.magic_number > 0 else (5 if card.upgraded else 4)
            for _ in range(hit_count):
                effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "Rage":
        effects.append(RageEffect(block_amount=3 if not card.upgraded else 5))

    elif card_id == "Rampage":
        effects.append(RampageEffect(base_damage=card.damage, damage_increase=5 if not card.upgraded else 8))

    elif card_id == "RecklessCharge":
        if target_idx is not None:
            effects.append(RecklessChargeEffect(damage=card.damage))

    elif card_id == "Rupture":
        effects.append(ApplyPowerEffect(power_type="Rupture", amount=1 if not card.upgraded else 2, target_type="player"))

    elif card_id == "SecondWind":
        effects.append(SecondWindEffect(block_per_card=5 if not card.upgraded else 7))

    elif card_id == "SeeingRed":
        effects.append(SeeingRedEffect())

    elif card_id == "SeverSoul":
        if target_idx is not None:
            effects.append(SeverSoulEffect(damage=card.damage))

    elif card_id == "Shockwave":
        effects.append(ShockwaveEffect(weak_amount=3 if not card.upgraded else 5, vul_amount=3 if not card.upgraded else 5))

    elif card_id == "SearingBlow":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "SpotWeakness":
        if target_idx is not None:
            effects.append(SpotWeaknessEffect(target_idx=target_idx, amount=3 if not card.upgraded else 4))

    elif card_id == "Carnage":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "Shieldslam":
        if target_idx is not None:
            effects.append(BodySlamEffect(target_idx=target_idx))

    elif card_id == "Sentinel":
        effects.append(SentinelEffect(block_amount=card.block))

    elif card_id == "SpotWeakness":
        if target_idx is not None:
            effects.append(SpotWeaknessEffect(target_idx=target_idx, amount=card.magic_number))

    elif card_id == "Uppercut":
        if target_idx is not None:
            effects.append(DealDamageEffect(target_idx=target_idx, damage=card.damage))
            effects.append(ApplyPowerEffect(power_type="Weak", amount=card.magic_number if card.magic_number > 0 else 1, target_type="monster", target_idx=target_idx))
            effects.append(ApplyPowerEffect(power_type="Vulnerable", amount=card.magic_number if card.magic_number > 0 else 1, target_type="monster", target_idx=target_idx))

    elif card_id == "Impervious":
        effects.append(GainBlockEffect(amount=card.block))

    elif card_id == "LimitBreak":
        effects.append(ApplyPowerEffect(power_type="StrengthDouble", amount=1, target_type="player"))

    elif card_id == "Offering":
        effects.append(LoseHPEffect(amount=6))
        effects.append(GainEnergyEffect(amount=2))
        effects.append(DrawCardsEffect(count=3 if not card.upgraded else 5))

    elif card_id == "Bludgeon":
        if target_idx is not None:
            effects.append(BludgeonEffect(target_idx=target_idx, damage=card.damage))

    elif card_id == "Brutality":
        effects.append(BrutalityEffect())

    elif card_id == "Corruption":
        effects.append(CorruptionEffect())

    elif card_id == "DoubleTap":
        effects.append(DoubleTapEffect())

    elif card_id == "Exhume":
        effects.append(ExhumeEffect())

    elif card_id == "Feed":
        if target_idx is not None:
            effects.append(FeedEffect(target_idx=target_idx, damage=card.damage, max_hp_gain=3 if not card.upgraded else 4))

    elif card_id == "FiendFire":
        if target_idx is not None:
            effects.append(FiendFireEffect(target_idx=target_idx, damage_per_card=card.magic_number if card.magic_number > 0 else 7))

    elif card_id == "Immolate":
        effects.append(ImmolateEffect(damage=card.damage))

    elif card_id == "Juggernaut":
        effects.append(JuggernautEffect(damage=card.magic_number if card.magic_number > 0 else 5))

    elif card_id == "Reaper":
        effects.append(ReaperEffect(damage=card.damage))

    elif card_id == "Whirlwind":
        effects.append(WhirlwindEffect(damage=card.damage))

    return effects


def execute_card(
    card: CardInstance,
    combat_state: CombatState,
    source: Player,
    target_idx: int | None = None,
) -> tuple[list[CardEffect], int]:
    """Execute a card and return the effects and energy cost.

    This is the main entry point for playing a card:
    1. Apply powers to compute final damage/block values
    2. Get the card's effects
    3. Execute each effect
    4. Return energy cost for the card

    Returns:
        Tuple of (list of executed effects, energy cost)
    """
    target = None
    if target_idx is not None and target_idx < len(combat_state.monsters):
        target = combat_state.monsters[target_idx]

    restore_shiv_bonus = card.card_id == "Shiv"
    original_combat_damage_bonus = int(getattr(card, "combat_damage_bonus", 0) or 0)
    if restore_shiv_bonus:
        card.combat_damage_bonus = original_combat_damage_bonus + source.powers.get_power_amount("Accuracy")

    _refresh_dynamic_card_for_current_state(card, combat_state)

    strike_bonus = getattr(source, '_strike_bonus_damage', 0)
    if strike_bonus > 0 and "Strike" in card.card_id:
        card.damage += strike_bonus
        card.base_damage += strike_bonus

    card.apply_powers(combat_state)

    if target is not None:
        card.calculate_card_damage(combat_state, target)

    if card.is_attack() and int(getattr(source, "_double_attack_damage_turns", 0) or 0) > 0:
        if getattr(card, "damage", -1) >= 0:
            card.damage *= 2

    if card.is_attack() and getattr(source, "_next_attack_double", False):
        if getattr(card, "damage", -1) >= 0:
            card.damage *= 2
        source._next_attack_double = False

    actual_x_cost, resolved_x_cost = _resolve_x_cost_values(card, combat_state, source)
    if resolved_x_cost is not None:
        card._resolved_x_cost = resolved_x_cost
        card._actual_x_cost = actual_x_cost
    elif hasattr(card, "_resolved_x_cost"):
        delattr(card, "_resolved_x_cost")
    if actual_x_cost is None and hasattr(card, "_actual_x_cost"):
        delattr(card, "_actual_x_cost")

    card._last_damage_dealt = 0
    effects = get_card_effects(card, target_idx)

    for effect in effects:
        effect.execute(combat_state, card, source, target)

    energy_cost = card.cost_for_turn
    if card.cost == -1:
        energy_cost = actual_x_cost if actual_x_cost is not None else source.energy

    if card.free_to_play_once:
        energy_cost = 0

    if restore_shiv_bonus:
        card.combat_damage_bonus = original_combat_damage_bonus

    return effects, energy_cost
