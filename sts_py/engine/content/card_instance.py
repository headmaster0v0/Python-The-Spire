"""CardInstance - Dynamic card instance with mutable state.

This module implements the runtime card instance system, separating
static card definitions (CardDef) from mutable instance state.

Key concepts from Java AbstractCard:
- Cards have base values (baseDamage, baseBlock, baseMagicNumber)
- Instance values (damage, block, magicNumber) are computed at runtime
- Powers and relics modify these values through applyPowers()
- Cards can be upgraded, which modifies base values
- Cards have per-turn state (costForTurn, freeToPlayOnce, etc.)
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sts_py.engine.content.cards_min import (
    ALL_CARD_DEFS,
    CARD_ID_ALIASES,
    STARTER_DECK_CARD_IDS,
    CardDef,
    CardRarity,
    CardType,
)

if TYPE_CHECKING:
    from sts_py.engine.combat.combat_state import CombatState


class CardTarget(str):
    ATTACK = "ATTACK"
    SKILL = "SKILL"
    POWER = "POWER"
    STATUS = "STATUS"
    CURSE = "CURSE"


STATEFUL_MISC_CARD_DEFAULTS: dict[str, int] = {
    "RitualDagger": 15,
    "GeneticAlgorithm": 1,
}

STATEFUL_MISC_HIDE_DEFAULT_RUNTIME_ID = {"GeneticAlgorithm"}


def _canonicalize_runtime_card_id(card_id: str) -> str:
    if not card_id:
        return card_id
    if card_id in ALL_CARD_DEFS:
        return card_id
    if card_id in CARD_ID_ALIASES:
        return CARD_ID_ALIASES[card_id]

    collapsed = card_id.replace(" ", "").replace("_", "")
    if collapsed in ALL_CARD_DEFS:
        return collapsed
    if collapsed in CARD_ID_ALIASES:
        return CARD_ID_ALIASES[collapsed]
    return card_id


def get_default_misc_for_card(card_id: str) -> int | None:
    return STATEFUL_MISC_CARD_DEFAULTS.get(card_id)


def is_misc_stateful_card(card_id: str) -> bool:
    return card_id in STATEFUL_MISC_CARD_DEFAULTS


def format_runtime_card_id(
    card_id: str,
    *,
    upgraded: bool = False,
    times_upgraded: int = 0,
    misc: int | None = None,
) -> str:
    if card_id == "SearingBlow":
        return f"SearingBlow+{times_upgraded}" if int(times_upgraded or 0) > 0 else "SearingBlow"

    if is_misc_stateful_card(card_id):
        default_misc = int(get_default_misc_for_card(card_id) or 0)
        misc_value = int(misc if misc is not None else default_misc)
        include_misc = misc_value > 0 and (
            card_id not in STATEFUL_MISC_HIDE_DEFAULT_RUNTIME_ID or misc_value != default_misc
        )
        misc_part = f"#{misc_value}" if include_misc else ""
        upgrade_part = "+" if upgraded else ""
        return f"{card_id}{misc_part}{upgrade_part}"

    return f"{card_id}+" if upgraded else card_id


def get_runtime_card_base_id(card_id: str) -> str:
    base_id, _, _ = _parse_runtime_card_notation(card_id)
    return _canonicalize_runtime_card_id(base_id)


def _parse_runtime_card_notation(card_id: str) -> tuple[str, int, int | None]:
    if not card_id:
        return card_id, 0, None
    match = re.fullmatch(r"(SearingBlow)\+(\d+)", card_id)
    if match:
        return match.group(1), int(match.group(2)), None
    collapsed = card_id.replace(" ", "").replace("_", "")
    misc_match = re.fullmatch(r"(RitualDagger|GeneticAlgorithm)(?:#(\d+))?(\+)?", collapsed)
    if misc_match:
        misc_value = misc_match.group(2)
        return misc_match.group(1), 1 if misc_match.group(3) else 0, int(misc_value) if misc_value else None
    if card_id.endswith("+"):
        return card_id[:-1], 1, None
    return card_id, 0, None


def _searing_blow_damage_for_upgrades(times_upgraded: int) -> int:
    upgrades = max(0, int(times_upgraded))
    return 12 + (upgrades * (upgrades + 7) // 2)


@dataclass
class CardInstance:
    """Mutable card instance with runtime state.
    
    Separates static definition (CardDef) from dynamic instance state.
    Each instance has a unique UUID and tracks:
    - Upgrade state (upgraded, timesUpgraded)
    - Cost modifications (costForTurn, isCostModified)
    - Damage/block/magic number values
    - Per-turn temporary states
    """
    card_id: str
    uuid: uuid.UUID = field(default_factory=uuid.uuid4)
    
    upgraded: bool = False
    times_upgraded: int = 0
    
    cost: int = -1
    cost_for_turn: int = -1
    is_cost_modified: bool = False
    is_cost_modified_for_turn: bool = False
    
    base_damage: int = -1
    damage: int = -1
    is_damage_modified: bool = False
    
    base_block: int = -1
    block: int = -1
    is_block_modified: bool = False
    
    base_magic_number: int = -1
    magic_number: int = -1
    is_magic_number_modified: bool = False
    
    misc: int = 0
    combat_damage_bonus: int = 0
    combat_cost_reduction: int = 0
    combat_cost_increase: int = 0
    allow_master_deck_fallback_sync: bool = True
    
    free_to_play_once: bool = False
    purge_on_use: bool = False
    exhaust_on_use_once: bool = False
    return_to_hand: bool = False
    shuffle_back_into_draw_pile: bool = False
    
    exhaust: bool = False
    is_ethereal: bool = False
    retain: bool = False
    self_retain: bool = False
    is_innate: bool = False
    is_unplayable: bool = False
    cards_played_this_turn: int = 0
    was_played_this_turn: bool = False

    _def: CardDef = field(default=None, repr=False)

    @property
    def curse_effect_type(self):
        if self._def:
            return self._def.curse_effect_type
        return None

    @property
    def curse_effect_value(self):
        if self._def:
            return self._def.curse_effect_value
        return 0

    @property
    def runtime_card_id(self) -> str:
        return format_runtime_card_id(
            self.card_id,
            upgraded=self.upgraded,
            times_upgraded=self.times_upgraded,
            misc=self.misc,
        )
    
    def __post_init__(self):
        self.card_id, parsed_upgrade_count, parsed_misc = _parse_runtime_card_notation(self.card_id)
        needs_init_upgrade = parsed_upgrade_count > 0
        self.card_id = _canonicalize_runtime_card_id(self.card_id)
            
        if self._def is None:
            self._def = ALL_CARD_DEFS.get(self.card_id)
        
        if self.cost == -1 and self._def:
            self.cost = self._get_base_cost()
            self.cost_for_turn = self.cost
        
        if self.base_damage == -1:
            self.base_damage = self._get_base_damage()
            self.damage = self.base_damage
        
        if self.base_block == -1:
            self.base_block = self._get_base_block()
            self.block = self.base_block
        
        if self.base_magic_number == -1:
            self.base_magic_number = self._get_base_magic_number()
            self.magic_number = self.base_magic_number

        if self._def and hasattr(self._def, 'is_unplayable'):
            self.is_unplayable = self._def.is_unplayable
        if self._def and hasattr(self._def, 'is_innate'):
            self.is_innate = self._def.is_innate
        if self._def and hasattr(self._def, 'is_exhaust'):
            self.exhaust = self._def.is_exhaust
        if self._def and hasattr(self._def, 'is_ethereal'):
            self.is_ethereal = self._def.is_ethereal
        if self._def and hasattr(self._def, 'is_retain'):
            self.retain = self._def.is_retain
            self.self_retain = self._def.is_retain

        if self.card_id == "SearingBlow":
            target_upgrades = max(
                int(parsed_upgrade_count),
                int(self.times_upgraded),
                1 if self.upgraded and self.times_upgraded == 0 else 0,
            )
            if target_upgrades > 0:
                self.upgraded = True
                self.times_upgraded = target_upgrades
                self.base_damage = _searing_blow_damage_for_upgrades(target_upgrades)
                self.damage = self.base_damage
            else:
                self.upgraded = False
                self.times_upgraded = 0
                self.base_damage = _searing_blow_damage_for_upgrades(0)
                self.damage = self.base_damage
            return

        if is_misc_stateful_card(self.card_id):
            if parsed_misc is not None:
                self.misc = parsed_misc
            elif int(self.misc or 0) <= 0:
                self.misc = int(get_default_misc_for_card(self.card_id) or 0)
            if self.card_id == "RitualDagger":
                self.base_damage = int(self.misc)
                self.damage = self.base_damage
            elif self.card_id == "GeneticAlgorithm":
                self.base_block = int(self.misc)
                self.block = self.base_block

        if needs_init_upgrade or (self.upgraded and self.times_upgraded == 0):
            self.upgrade()
    
    @property
    def rarity(self) -> CardRarity:
        if self._def:
            return self._def.rarity
        return CardRarity.COMMON
    
    @property
    def card_type(self) -> CardType:
        if self._def:
            return self._def.card_type
        return CardType.ATTACK
    
    def _get_base_cost(self) -> int:
        if self._def:
            return self._def.cost
        return 1
    
    def _get_base_damage(self) -> int:
        if self._def:
            return self._def.base_damage
        return -1
    
    def _get_base_block(self) -> int:
        if self._def:
            return self._def.base_block
        return -1
    
    def _get_base_magic_number(self) -> int:
        if self._def:
            return self._def.base_magic_number
        return -1
    
    def is_attack(self) -> bool:
        return self.card_type == CardType.ATTACK
    
    def is_skill(self) -> bool:
        return self.card_type == CardType.SKILL
    
    def is_power(self) -> bool:
        return self.card_type == CardType.POWER
    
    def is_starter_strike(self) -> bool:
        return self.card_id in {"Strike", "Strike_P"}
    
    def is_starter_defend(self) -> bool:
        return self.card_id in {"Defend", "Defend_P"}
    
    def can_use(self, energy: int) -> bool:
        if self.card_id == "GrandFinale":
            combat_state = getattr(self, "_combat_state", None)
            card_manager = getattr(combat_state, "card_manager", None)
            if card_manager is not None and getattr(card_manager, "get_draw_pile_size", None) is not None:
                if card_manager.get_draw_pile_size() > 0:
                    return False
        if self.card_id == "SignatureMove":
            combat_state = getattr(self, "_combat_state", None)
            card_manager = getattr(combat_state, "card_manager", None)
            if card_manager is not None:
                other_attacks = [
                    hand_card
                    for hand_card in getattr(card_manager.hand, "cards", []) or []
                    if hand_card is not self and hasattr(hand_card, "is_attack") and hand_card.is_attack()
                ]
                if other_attacks:
                    return False
        if self.card_id in {"SecretTechnique", "SecretWeapon"}:
            combat_state = getattr(self, "_combat_state", None)
            card_manager = getattr(combat_state, "card_manager", None)
            if card_manager is not None:
                required_type = CardType.SKILL if self.card_id == "SecretTechnique" else CardType.ATTACK
                draw_cards = getattr(getattr(card_manager, "draw_pile", None), "cards", []) or []
                if not any(getattr(draw_card, "card_type", None) == required_type for draw_card in draw_cards):
                    return False
        if self.card_id == "Clash":
            combat_state = getattr(self, "_combat_state", None)
            if combat_state is not None and hasattr(combat_state, "card_manager"):
                hand_cards = getattr(combat_state.card_manager.hand, "cards", [])
                for hand_card in hand_cards:
                    if hand_card is self:
                        continue
                    if not hand_card.is_attack():
                        return False
        if self.cost == -1:
            return energy >= 0
        return energy >= self.cost_for_turn
    
    def apply_powers(self, combat_state: CombatState) -> None:
        """Apply powers and relics to compute final damage/block values.
        
        This mirrors Java AbstractCard.applyPowers():
        1. Apply powers to block
        2. Apply relics and powers to damage
        3. Track isDamageModified/isBlockModified
        """
        self._apply_powers_to_block(combat_state)
        self._apply_powers_to_damage(combat_state)

    def _refresh_dynamic_base_block(self) -> None:
        if self.card_id == "GeneticAlgorithm":
            default_misc = int(get_default_misc_for_card(self.card_id) or 0)
            self.base_block = max(0, int(getattr(self, "misc", 0) or default_misc))
        elif self.card_id == "SpiritShield":
            combat_state = getattr(self, "_combat_state", None)
            card_manager = getattr(combat_state, "card_manager", None)
            hand_cards = getattr(getattr(card_manager, "hand", None), "cards", []) or []
            self.base_block = max(0, len(hand_cards) * max(0, int(getattr(self, "magic_number", 0) or 0)))

    def _refresh_dynamic_base_damage(self, combat_state: CombatState) -> None:
        if self.card_id == "MindBlast":
            draw_pile = getattr(getattr(combat_state, "card_manager", None), "draw_pile", None)
            self.base_damage = len(getattr(draw_pile, "cards", []) or [])
        elif self.card_id == "Blizzard":
            player = getattr(combat_state, "player", None)
            frost_channels = max(0, int(getattr(player, "_frost_orbs_channeled_this_combat", 0) or 0))
            self.base_damage = frost_channels * max(0, int(getattr(self, "magic_number", 0) or 0))
        elif self.card_id == "Brilliance":
            player = getattr(combat_state, "player", None)
            mantra_damage = max(0, int(getattr(player, "_mantra_gained_this_combat", 0) or 0))
            self.base_damage = max(0, int(self._def.base_damage)) + mantra_damage
        elif self.card_id == "RitualDagger":
            self.base_damage = max(0, int(getattr(self, "misc", 0) or 0))

    def _apply_powers_to_block(self, combat_state: CombatState) -> None:
        self._refresh_dynamic_base_block()
        if self.base_block < 0:
            return

        self.is_block_modified = False
        tmp = float(self.base_block)

        if hasattr(combat_state.player, 'dexterity'):
            tmp += combat_state.player.dexterity

        if hasattr(combat_state.player, 'powers'):
            tmp = combat_state.player.powers.apply_block_modifiers(tmp)

        if self.base_block != int(tmp):
            self.is_block_modified = True

        if tmp < 0:
            tmp = 0.0

        self.block = int(tmp)
    
    def _apply_powers_to_damage(self, combat_state: CombatState) -> None:
        self._refresh_dynamic_base_damage(combat_state)
        if self.base_damage < 0:
            return

        self.is_damage_modified = False
        effective_base_damage = self.base_damage + self.combat_damage_bonus
        tmp = float(effective_base_damage)
        
        if hasattr(combat_state.player, 'strength'):
            tmp += combat_state.player.strength
        
        if effective_base_damage != int(tmp):
            self.is_damage_modified = True
        
        if tmp < 0:
            tmp = 0.0
        
        self.damage = int(tmp)
    
    def calculate_card_damage(self, combat_state: CombatState, target=None) -> None:
        """Calculate damage against a specific target.

        Follows Java AbstractCard.calculateCardDamage order:
        1. Start with baseDamage
        2. Apply player powers atDamageGive (Strength, etc.)
        3. Apply stance atDamageGive (Wrath +50%, Divinity +50%)
        4. Apply player powers atDamageFinalGive
        5. Apply target powers atDamageReceive (Vulnerable, etc.)
        6. Apply target powers atDamageFinalReceive
        7. Floor to minimum of 0
        """
        self._apply_powers_to_block(combat_state)
        self._refresh_dynamic_base_damage(combat_state)

        if self.base_damage < 0:
            return

        self.is_damage_modified = False
        effective_base_damage = self.base_damage + self.combat_damage_bonus
        tmp = float(effective_base_damage)

        if hasattr(combat_state.player, 'strength') and combat_state.player.strength != 0:
            tmp += combat_state.player.strength
            self.is_damage_modified = True

        if hasattr(combat_state.player, 'powers'):
            tmp = combat_state.player.powers.apply_damage_modifiers(tmp, "NORMAL")

        if hasattr(combat_state.player, 'stance') and combat_state.player.stance is not None:
            tmp = combat_state.player.stance.at_damage_give(tmp, "NORMAL")

        if target is not None and hasattr(target, 'powers'):
            tmp = target.powers.apply_damage_receive_modifiers(tmp, "NORMAL")

        if hasattr(combat_state.player, 'powers'):
            tmp = combat_state.player.powers.apply_damage_final_give_modifiers(tmp, "NORMAL")

        if target is not None and hasattr(target, 'powers'):
            tmp = target.powers.apply_damage_final_receive_modifiers(tmp, "NORMAL")

        if tmp < 0:
            tmp = 0.0

        self.damage = int(tmp)

        if effective_base_damage != self.damage:
            self.is_damage_modified = True
    
    def upgrade(self) -> None:
        """Upgrade this card instance.

        Each card has specific upgrade effects defined in Java.
        This method handles common upgrade patterns.
        """
        if self.card_id == "SearingBlow":
            self.upgraded = True
            self.times_upgraded += 1
            self.base_damage = _searing_blow_damage_for_upgrades(self.times_upgraded)
            self.damage = self.base_damage
            return

        if self.times_upgraded > 0:
            return

        self.upgraded = True
        self.times_upgraded += 1

        if self._def and self._def.card_type == CardType.STATUS:
            from sts_py.engine.content.cards_min import STATUS_CARD_DEFS
            upgraded_id = self.card_id + "+"
            if upgraded_id in STATUS_CARD_DEFS:
                self._def = STATUS_CARD_DEFS[upgraded_id]
                if hasattr(self._def, 'curse_effect_value'):
                    pass
                return

        if self._def:
            if self._def.upgrade_damage:
                self.base_damage += self._def.upgrade_damage
                self.damage = self.base_damage
            if self._def.upgrade_block:
                self.base_block += self._def.upgrade_block
                self.block = self.base_block
            if self._def.upgrade_magic_number:
                self.base_magic_number += self._def.upgrade_magic_number
                self.magic_number = self.base_magic_number
            if self._def.upgrade_cost is not None:
                self.cost = self._def.upgrade_cost
                self.cost_for_turn = self._def.upgrade_cost
                self.is_cost_modified = True
            if self._def.upgrade_exhaust is not None:
                self.exhaust = self._def.upgrade_exhaust
            if self._def.upgrade_ethereal is not None:
                self.is_ethereal = self._def.upgrade_ethereal
            if self._def.upgrade_innate is not None:
                self.is_innate = self._def.upgrade_innate
            if self._def.upgrade_retain is not None:
                self.retain = self._def.upgrade_retain
                self.self_retain = self._def.upgrade_retain
            return
    
    def make_copy(self) -> CardInstance:
        """Create a new instance with the same card ID but new UUID."""
        return CardInstance(card_id=self.runtime_card_id, allow_master_deck_fallback_sync=False)
    
    def make_stat_equivalent_copy(self) -> CardInstance:
        """Create a copy with same stats and upgrade state."""
        copy = CardInstance(
            card_id=self.card_id,
            upgraded=self.upgraded,
            times_upgraded=self.times_upgraded,
            cost=self.cost,
            cost_for_turn=self.cost_for_turn,
            base_damage=self.base_damage,
            damage=self.damage,
            base_block=self.base_block,
            block=self.block,
            base_magic_number=self.base_magic_number,
            magic_number=self.magic_number,
            misc=self.misc,
            combat_damage_bonus=self.combat_damage_bonus,
            combat_cost_reduction=self.combat_cost_reduction,
            combat_cost_increase=self.combat_cost_increase,
            allow_master_deck_fallback_sync=False,
            exhaust=self.exhaust,
            is_ethereal=self.is_ethereal,
            retain=self.retain,
            self_retain=self.self_retain,
            is_innate=self.is_innate,
        )
        return copy
    
    def make_same_instance(self) -> CardInstance:
        """Create a copy that shares the same UUID (for tracking)."""
        copy = self.make_stat_equivalent_copy()
        copy.uuid = self.uuid
        copy.allow_master_deck_fallback_sync = self.allow_master_deck_fallback_sync
        if hasattr(self, "_master_deck_index"):
            setattr(copy, "_master_deck_index", getattr(self, "_master_deck_index"))
        return copy
    
    def reset_for_turn(self) -> None:
        """Reset per-turn state at start of turn."""
        self.cost_for_turn = self.cost
        self.is_cost_modified_for_turn = False
        self.free_to_play_once = False
        self.exhaust_on_use_once = False
        self.purge_on_use = False
        self.return_to_hand = False
        self.shuffle_back_into_draw_pile = False
    
    def on_draw(self) -> None:
        """Called when card is drawn from draw pile.

        Normality: Drawing Normality instantly puts it into effect.
        If player has already played 3+ cards, they can no longer play cards this turn.
        Void: When drawn, lose 1 energy.
        Confusion: If player has Confused power and not Corruption (for Skills),
        randomize cost_for_turn to 0-3 (X-cost cards unaffected).
        """
        self.reset_for_turn()

        if self.card_type.value in ("CURSE", "STATUS"):
            from sts_py.engine.content.cards_min import CurseEffectType
            if self.curse_effect_type == CurseEffectType.LIMIT_CARDS_PER_TURN:
                if hasattr(self, '_combat_state') and self._combat_state:
                    cs = self._combat_state
                    if isinstance(cs, __import__('sts_py.engine.combat.combat_state', fromlist=['CombatState']).CombatState):
                        cs.player._normality_locked = True
                    elif hasattr(cs, '_combat_state') and cs._combat_state:
                        cs._combat_state.player._normality_locked = True
            elif self.curse_effect_type == CurseEffectType.ON_CARD_PLAYED_LOSE_HP:
                if hasattr(self, '_combat_state') and self._combat_state:
                    cs = self._combat_state
                    if isinstance(cs, __import__('sts_py.engine.combat.combat_state', fromlist=['CombatState']).CombatState):
                        energy_loss = self.curse_effect_value
                        cs.player.energy = max(0, cs.player.energy - energy_loss)
                    elif hasattr(cs, '_combat_state') and cs._combat_state:
                        energy_loss = self.curse_effect_value
                        cs._combat_state.player.energy = max(0, cs._combat_state.player.energy - energy_loss)

        self.apply_combat_cost_modifiers()
        self._apply_confusion_if_needed()
    
    def on_exhaust(self) -> None:
        """Called when card is exhausted."""
        if self.card_id != "Sentinel":
            return

        player = self._resolve_combat_player()
        if player is None:
            return

        player.energy += 3 if self.upgraded else 2

        combat_state = getattr(player, "_combat_state", None)
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is not None:
            card_manager.set_energy(player.energy)
    
    def on_retain(self) -> None:
        """Called when card is retained at end of turn."""
        if self.card_id == "Perseverance":
            self.base_block = max(0, int(getattr(self, "base_block", 0) or 0) + int(getattr(self, "magic_number", 0) or 0))
            self.block = self.base_block
        elif self.card_id == "WindmillStrike":
            self.base_damage = max(0, int(getattr(self, "base_damage", 0) or 0) + int(getattr(self, "magic_number", 0) or 0))
            self.damage = self.base_damage
        elif self.card_id == "SandsOfTime":
            self.combat_cost_reduction = max(0, int(getattr(self, "combat_cost_reduction", 0) or 0) + 1)

        player = self._resolve_combat_player()
        if player is None:
            return

        establishment_discount = max(0, int(player.powers.get_power_amount("Establishment") or 0))
        if establishment_discount > 0 and int(getattr(self, "cost", -1) or -1) >= 0:
            self.combat_cost_reduction = max(
                0,
                int(getattr(self, "combat_cost_reduction", 0) or 0) + establishment_discount,
            )

        self.apply_combat_cost_modifiers()

    def _resolve_combat_player(self):
        if not hasattr(self, '_combat_state') or not self._combat_state:
            return None

        card_manager = self._combat_state
        if hasattr(card_manager, '_combat_state') and card_manager._combat_state:
            combat_state = card_manager._combat_state
            player = combat_state.player
        elif hasattr(card_manager, 'state'):
            player = card_manager.state.player
        elif hasattr(card_manager, 'player'):
            player = card_manager.player
        else:
            return None

        if not hasattr(player, 'powers'):
            return None
        return player

    def apply_combat_cost_modifiers(self) -> None:
        """Apply persistent combat-time cost modifiers like Corruption."""
        player = self._resolve_combat_player()
        if player is None:
            return

        from sts_py.engine.combat.powers import CorruptionPower

        if self.card_id in {"BloodforBlood", "Eviscerate", "Streamline", "ForceField", "MasterfulStab", "SandsOfTime"} and self.cost >= 0:
            reduction = max(0, int(self.combat_cost_reduction))
            increase = max(0, int(self.combat_cost_increase))
            if self.card_id == "ForceField":
                reduction = max(
                    reduction,
                    max(0, int(getattr(player, "_power_cards_played_this_combat", 0) or 0)),
                )
            self.cost_for_turn = max(0, self.cost - reduction + increase)
            self.is_cost_modified_for_turn = reduction > 0 or increase > 0

        has_corruption = any(isinstance(p, CorruptionPower) for p in player.powers.powers)
        if self.card_type.value == "SKILL" and has_corruption:
            self.cost_for_turn = 0
            self.is_cost_modified_for_turn = True
        elif self.card_type.value == "ATTACK" and player.powers.get_power_amount("Swivel") > 0 and self.cost >= 0:
            self.cost_for_turn = 0
            self.is_cost_modified_for_turn = True

    def _apply_confusion_if_needed(self) -> None:
        """Apply confusion effect if player has Confused power.

        Rules:
        - Only applies when card is actually drawn (not from special effects)
        - X-cost cards are unaffected
        - Corruption overrides confusion: Skills always cost 0
        """
        player = self._resolve_combat_player()
        if player is None:
            return

        from sts_py.engine.combat.powers import ConfusedPower, CorruptionPower
        has_confused = any(isinstance(p, ConfusedPower) for p in player.powers.powers)

        if not has_confused:
            return

        has_corruption = any(isinstance(p, CorruptionPower) for p in player.powers.powers)

        if self.card_type.value == "SKILL" and has_corruption:
            self.cost_for_turn = 0
            return

        if self.cost == -1:
            self.cost = self._get_base_cost()

        if self.cost < 0:
            return

        import random
        self.cost_for_turn = random.randint(0, 3)
        self.is_cost_modified_for_turn = True

    def to_dict(self) -> dict:
        """Serialize to dict for canonical JSON."""
        return {
            "card_id": self.card_id,
            "uuid": str(self.uuid),
            "upgraded": self.upgraded,
            "times_upgraded": self.times_upgraded,
            "cost": self.cost,
            "cost_for_turn": self.cost_for_turn,
            "base_damage": self.base_damage,
            "damage": self.damage,
            "base_block": self.base_block,
            "block": self.block,
            "base_magic_number": self.base_magic_number,
            "magic_number": self.magic_number,
            "misc": self.misc,
            "combat_damage_bonus": self.combat_damage_bonus,
            "combat_cost_reduction": self.combat_cost_reduction,
            "combat_cost_increase": self.combat_cost_increase,
            "allow_master_deck_fallback_sync": self.allow_master_deck_fallback_sync,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> CardInstance:
        """Deserialize from dict."""
        instance = cls(
            card_id=data["card_id"],
            uuid=uuid.UUID(data["uuid"]) if "uuid" in data else uuid.uuid4(),
            upgraded=data.get("upgraded", False),
            times_upgraded=data.get("times_upgraded", 0),
            cost=data.get("cost", -1),
            cost_for_turn=data.get("cost_for_turn", -1),
            base_damage=data.get("base_damage", -1),
            damage=data.get("damage", -1),
            base_block=data.get("base_block", -1),
            block=data.get("block", -1),
            base_magic_number=data.get("base_magic_number", -1),
            magic_number=data.get("magic_number", -1),
            misc=data.get("misc", 0),
            combat_damage_bonus=data.get("combat_damage_bonus", 0),
            combat_cost_reduction=data.get("combat_cost_reduction", 0),
            combat_cost_increase=data.get("combat_cost_increase", 0),
            allow_master_deck_fallback_sync=data.get("allow_master_deck_fallback_sync", True),
        )
        return instance
    
    def __hash__(self) -> int:
        return hash(self.uuid)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CardInstance):
            return False
        return self.uuid == other.uuid
    
    def __lt__(self, other: CardInstance) -> bool:
        return self.card_id < other.card_id
    
    def __repr__(self) -> str:
        return f"CardInstance({self.runtime_card_id}, cost={self.cost_for_turn})"


def create_starter_deck(character_class: str = "IRONCLAD") -> list[CardInstance]:
    """Create a starter deck for the requested character class."""
    card_ids = STARTER_DECK_CARD_IDS.get(character_class, STARTER_DECK_CARD_IDS["IRONCLAD"])
    return [CardInstance(card_id=card_id) for card_id in card_ids]
