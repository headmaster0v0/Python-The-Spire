"""Power system for combat effects.

This module implements the power system from STS, which provides
persistent effects that modify combat behavior.

Key concepts from Java AbstractPower:
- Powers have ID, name, amount, owner, and type (BUFF/DEBUFF)
- Powers hook into various combat events (damage, block, turn start/end)
- Powers can stack (positive or negative amounts)
- Turn-based powers reduce at end of round

Common powers:
- Strength: Increases attack damage
- Dexterity: Increases block gained
- Vulnerable: Increases damage taken by 50%
- Weak: Reduces damage dealt by 25%
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any
try:
    from typing import Protocol, runtime_checkable
except ImportError:
    class Protocol(object):
        pass

    def runtime_checkable(cls):
        return cls

if TYPE_CHECKING:
    from sts_py.engine.combat.combat_state import Player
    from sts_py.engine.monsters.monster_base import MonsterBase

from sts_py.engine.content.card_instance import CardInstance


class PowerType(Enum):
    BUFF = auto()
    DEBUFF = auto()
    STATUS = auto()


@runtime_checkable
class Power(Protocol):
    """Protocol for power effects.

    Powers are persistent effects that modify combat behavior through
    hook methods called at specific times during combat.
    """
    id: str
    name: str
    amount: int
    owner: str  # "player" or monster index
    power_type: PowerType
    is_turn_based: bool
    can_go_negative: bool

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        """Called when owner deals damage. Return modified damage."""
        ...

    def at_damage_final_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        """Called after all other damage Give modifiers. Final pass for damage dealt."""
        ...

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        """Called when owner receives damage. Return modified damage."""
        ...

    def at_damage_final_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        """Called after all other damage Receive modifiers. Final pass for damage taken."""
        ...

    def modify_block(self, block: float) -> float:
        """Called when owner gains block. Return modified block."""
        ...

    def at_end_of_round(self) -> bool:
        """Called at end of round. Return True if power should be removed."""
        ...

    def stack_power(self, amount: int) -> None:
        """Add to power amount."""
        ...

    def reduce_power(self, amount: int) -> None:
        """Reduce power amount."""
        ...

    def to_dict(self) -> dict:
        """Serialize to dict."""
        ...


@dataclass
class StrengthPower:
    """Strength power - increases attack damage.
    
    From Java: atDamageGive returns damage + amount for NORMAL damage type.
    Can go negative (reduces damage).
    """
    id: str = "Strength"
    name: str = "Strength"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = True
    
    def __post_init__(self):
        self._update_type()
    
    def _update_type(self) -> None:
        if self.amount < 0:
            self.power_type = PowerType.DEBUFF
        else:
            self.power_type = PowerType.BUFF
    
    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        if damage_type == "NORMAL":
            return damage + self.amount
        return damage

    def at_damage_final_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_final_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage
    
    def modify_block(self, block: float) -> float:
        return block
    
    def at_end_of_round(self) -> bool:
        return False
    
    def stack_power(self, amount: int) -> None:
        self.amount += amount
        self._update_type()
        if self.amount == 0:
            pass
    
    def reduce_power(self, amount: int) -> None:
        self.amount -= amount
        self._update_type()
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class DexterityPower:
    """Dexterity power - increases block gained.
    
    From Java: modifyBlock returns block + amount.
    Can go negative (reduces block).
    """
    id: str = "Dexterity"
    name: str = "Dexterity"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = True
    
    def __post_init__(self):
        self._update_type()
    
    def _update_type(self) -> None:
        if self.amount < 0:
            self.power_type = PowerType.DEBUFF
        else:
            self.power_type = PowerType.BUFF
    
    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage
    
    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage
    
    def modify_block(self, block: float) -> float:
        result = block + self.amount
        return max(0.0, result)
    
    def at_end_of_round(self) -> bool:
        return False
    
    def stack_power(self, amount: int) -> None:
        self.amount += amount
        self._update_type()
    
    def reduce_power(self, amount: int) -> None:
        self.amount -= amount
        self._update_type()
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class VulnerablePower:
    """Vulnerable power - increases damage taken by 50%.

    From Java: atDamageReceive returns damage * 1.5 for NORMAL damage type.
    Turn-based: reduces by 1 at end of round.

    If is_source_monster=True and applied at end of turn, justApplied skips
    the first reduction, effectively giving the vulnerable +1 duration.
    """
    id: str = "Vulnerable"
    name: str = "Vulnerable"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.DEBUFF
    is_turn_based: bool = True
    can_go_negative: bool = False
    is_source_monster: bool = False

    PLAYER_EFFECTIVENESS: float = 1.5
    MONSTER_EFFECTIVENESS: float = 1.5

    def __post_init__(self):
        self._just_applied: bool = False

    def _current_effectiveness(self) -> float:
        if self.owner == "player":
            return self.__class__.PLAYER_EFFECTIVENESS
        return self.__class__.MONSTER_EFFECTIVENESS

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        if damage_type == "NORMAL":
            return damage * self._current_effectiveness()
        return damage

    def modify_block(self, block: float) -> float:
        return block

    def at_end_of_round(self) -> bool:
        if self._just_applied:
            self._just_applied = False
            return False

        self.amount -= 1
        return self.amount <= 0

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
            "is_source_monster": self.is_source_monster,
        }


@dataclass
class WeakPower:
    """Weak power - reduces damage dealt by 25%.

    From Java: atDamageGive returns damage * 0.75 for NORMAL damage type.
    Turn-based: reduces by 1 at end of round.
    """
    id: str = "Weak"
    name: str = "Weak"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.DEBUFF
    is_turn_based: bool = True
    can_go_negative: bool = False

    PLAYER_EFFECTIVENESS: float = 0.75
    MONSTER_EFFECTIVENESS: float = 0.75

    def __post_init__(self):
        self._just_applied: bool = True

    def _current_effectiveness(self) -> float:
        if self.owner == "player":
            return self.__class__.PLAYER_EFFECTIVENESS
        return self.__class__.MONSTER_EFFECTIVENESS

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        if damage_type == "NORMAL":
            return damage * self._current_effectiveness()
        return damage
    
    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage
    
    def modify_block(self, block: float) -> float:
        return block
    
    def at_end_of_round(self) -> bool:
        if self._just_applied:
            self._just_applied = False
            return False
        
        self.amount -= 1
        return self.amount <= 0
    
    def stack_power(self, amount: int) -> None:
        self.amount += amount
    
    def reduce_power(self, amount: int) -> None:
        self.amount -= amount
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class CurlUpPower:
    """Curl Up power - Louse gains block when attacked.
    
    From Java: onAttacked triggers block gain once per combat.
    Amount is the block to gain.
    """
    id: str = "Curl Up"
    name: str = "Curl Up"
    amount: int = 4
    owner: str = "monster_0"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False
    
    def __post_init__(self):
        self._triggered: bool = False
    
    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage
    
    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage
    
    def modify_block(self, block: float) -> float:
        return block
    
    def at_end_of_round(self) -> bool:
        return False
    
    def on_attacked(self, actual_damage: int, monster: "MonsterBase" = None) -> int:
        """Called when owner is attacked. Returns block to gain."""
        if self._triggered or actual_damage <= 0:
            return 0
        self._triggered = True
        return self.amount
    
    def stack_power(self, amount: int) -> None:
        self.amount += amount
    
    def reduce_power(self, amount: int) -> None:
        self.amount -= amount
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class RitualPower:
    """Ritual power - gain Strength at end of turn.

    For monsters: Does NOT trigger on the turn Ritual is gained.
    For players: Does trigger on the turn Ritual is gained.

    From Java: atEndOfTurn adds Strength equal to amount.
    Used by Cultist.
    """
    id: str = "Ritual"
    name: str = "Ritual"
    amount: int = 3
    owner: str = "monster_0"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False
    skip_first: bool = True
    on_player: bool = False

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def modify_block(self, block: float) -> float:
        return block

    def at_end_of_round(self) -> bool:
        if not self.on_player:
            if self.skip_first:
                self.skip_first = False
        return False

    def get_strength_gain(self) -> int:
        """Return amount of Strength to gain at end of turn.

        For monsters: returns 0 if skip_first is True.
        For players: always returns full amount.
        """
        if self.owner.startswith("monster") and self.skip_first:
            return 0
        return self.amount

    def stack_power(self, amount: int) -> None:
        self.skip_first = False
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class AngerPower:
    """Anger power - gain Strength when player plays a Skill.
    
    From Java: onCardUse triggers when player plays a Skill card.
    Used by Gremlin Nob.
    """
    id: str = "Anger"
    name: str = "Anger"
    amount: int = 2
    owner: str = "monster_0"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False
    
    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage
    
    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage
    
    def modify_block(self, block: float) -> float:
        return block
    
    def at_end_of_round(self) -> bool:
        return False
    
    def on_player_skill_played(self) -> int:
        """Return amount of Strength to gain when player plays a Skill."""
        return self.amount
    
    def stack_power(self, amount: int) -> None:
        self.amount += amount
    
    def reduce_power(self, amount: int) -> None:
        self.amount -= amount
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class DemonFormPower:
    id: str = "DemonForm"
    name: str = "DemonForm"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def modify_block(self, block: float) -> float:
        return block

    def at_end_of_round(self) -> bool:
        return False

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class FrailPower:
    """Frail power - reduces block gained from cards by 25%.

    From Java: modifyBlock returns block * 0.75 for NORMAL block type.
    Turn-based: reduces by 1 at end of round.
    """
    id: str = "Frail"
    name: str = "Frail"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.DEBUFF
    is_turn_based: bool = True
    can_go_negative: bool = False

    EFFECTIVENESS: float = 0.75

    def __post_init__(self):
        self._just_applied: bool = False
        self._effectiveness = self.__class__.EFFECTIVENESS

    def modify_block(self, block: float) -> float:
        return block * self._effectiveness

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_end_of_round(self) -> bool:
        if self._just_applied:
            self._just_applied = False
            return False

        self.amount -= 1
        return self.amount <= 0

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


class SporeCloudPower:
    """Spore Cloud power - applies Vulnerable to player when monster dies.

    From Java: onDeath applies VulnerablePower to player equal to amount.
    This is not a turn-based power.
    """
    id: str = "Spore Cloud"
    name: str = "Spore Cloud"
    amount: int = 2
    owner: str = "monster"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def modify_block(self, block: float) -> float:
        return block

    def on_death(self) -> None:
        pass

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


class ThieveryPower:
    """Thievery power - steals gold when attacking.

    From Java: This power is used by Looter/Mugger monsters to steal gold on attack.
    The amount represents gold stolen per attack.
    """
    id: str = "Thievery"
    name: str = "Thievery"
    amount: int = 15
    owner: str = "monster"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def modify_block(self, block: float) -> float:
        return block

    def on_steal_gold(self, player_gold: int) -> int:
        return min(self.amount, player_gold)

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class MetallicizePower:
    id: str = "Metallicize"
    name: str = "Metallicize"
    amount: int = 3
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def modify_block(self, block: float) -> float:
        return block

    def at_end_of_round(self) -> bool:
        return False

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }

@dataclass
class SharpHidePower:
    id: str = "Sharp Hide"
    name: str = "Sharp Hide"
    amount: int = 3
    owner: str = "monster"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def on_use_card(self, card) -> None:
        from sts_py.engine.content.card_instance import CardType
        if card.card_type == CardType.ATTACK:
            from sts_py.engine.combat.combat_engine import CombatEngine
            from sts_py.engine.combat.powers import DamageInfo, DamageType
            dmg_info = DamageInfo(owner=self.owner, baseDamage=self.amount, damage_type=DamageType.THORNS)
            if CombatEngine.instance and CombatEngine.instance.state and CombatEngine.instance.state.player:
                CombatEngine.instance.state.player.take_damage(self.amount)

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }

@dataclass
class ThornsPower:
    id: str = "Thorns"
    name: str = "Thorns"
    amount: int = 3
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def modify_block(self, block: float) -> float:
        return block

    def at_end_of_round(self) -> bool:
        return False

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def on_player_attacked(
        self,
        owner: Any | None = None,
        damage_amount: int = 0,
        *,
        damage_type: str = "NORMAL",
        source_owner: Any | None = None,
    ) -> dict[str, Any] | None:
        if owner is None or damage_amount <= 0 or self.amount <= 0:
            return None
        if damage_type != "NORMAL" or source_owner is None:
            return None
        if hasattr(source_owner, "is_dead") and source_owner.is_dead():
            return None
        source_owner.take_damage(self.amount)
        return {"type": "thorns_retaliate", "amount": self.amount}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class FlameBarrierPower:
    id: str = "FlameBarrier"
    name: str = "FlameBarrier"
    amount: int = 4
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = True
    can_go_negative: bool = False

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def modify_block(self, block: float) -> float:
        return block

    def at_end_of_round(self) -> bool:
        return True

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount = max(0, self.amount - amount)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }

@dataclass
class RegenPower:
    id: str = "Regen"
    name: str = "Regen"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = True
    can_go_negative: bool = False

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def modify_block(self, block: float) -> float:
        return block

    def at_end_of_round(self) -> bool:
        self.amount -= 1
        return self.amount <= 0

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }

@dataclass
class FeelNoPainPower:
    id: str = "FeelNoPain"
    name: str = "FeelNoPain"
    amount: int = 3
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def modify_block(self, block: float) -> float:
        return block

    def at_end_of_round(self) -> bool:
        return False

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }

@dataclass
class DarkEmbracePower:
    id: str = "DarkEmbrace"
    name: str = "DarkEmbrace"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def modify_block(self, block: float) -> float:
        return block

    def at_end_of_round(self) -> bool:
        return False

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class CombustPower:
    """Combust power - at end of turn, lose 1 HP and deal amount damage to ALL enemies.

    From Java: CombustPower.atEndOfTurn() → loseHP(1), deal amount damage to all monsters.
    """
    id: str = "Combust"
    name: str = "Combust"
    amount: int = 5
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False
    hp_loss: int = 1

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def modify_block(self, block: float) -> float:
        return block

    def at_end_of_round(self) -> bool:
        return False

    def at_end_of_turn(self, owner: Any | None = None, is_player: bool = True) -> dict[str, Any] | None:
        if not is_player or owner is None:
            return None
        actual_hp_loss = 0
        if hasattr(owner, "lose_hp"):
            actual_hp_loss = owner.lose_hp(self.hp_loss, source_owner=owner)
        combat_state = getattr(owner, "_combat_state", None)
        if combat_state is None:
            return None
        for monster in getattr(combat_state, "monsters", []):
            if monster.is_dead():
                continue
            monster.take_damage(self.amount)
        return {"type": "combust", "hp_loss": actual_hp_loss, "damage": self.amount}

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class EnragePower:
    """Enrage power - whenever you play a Skill, gain amount Strength.

    From Java: EnragePower.onSkillUse() → owner gains Strength.
    """
    id: str = "Enrage"
    name: str = "Enrage"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount = max(0, self.amount - amount)

    def on_player_skill_played(self, owner: Any | None = None, card: Any | None = None) -> dict[str, Any] | None:
        if owner is None or card is None:
            return None
        if not hasattr(card, "is_skill") or not card.is_skill():
            return None
        owner.add_power(create_power("Strength", self.amount, "player"))
        owner.strength += self.amount
        return {"type": "gain_strength_on_skill", "amount": self.amount}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class EvolvePower:
    id: str = "Evolve"
    name: str = "Evolve"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def on_card_draw(self, owner: Any | None, card: Any | None) -> dict[str, Any] | None:
        if owner is None or card is None:
            return None
        if getattr(getattr(card, "card_type", None), "value", None) != "STATUS":
            return None
        combat_state = getattr(owner, "_combat_state", None)
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return None
        card_manager.draw_cards(self.amount)
        return {"type": "draw_on_status", "amount": self.amount}


@dataclass
class FireBreathingPower:
    """Fire Breathing power - when a Status or Curse card is drawn, deal amount damage to ALL enemies.

    From Java: FireBreathingPower.onCardDraw(card) → if card is Status/Curse, deal amount to all.
    """
    id: str = "FireBreathing"
    name: str = "FireBreathing"
    amount: int = 6
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def modify_block(self, block: float) -> float:
        return block

    def at_end_of_round(self) -> bool:
        return False

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def on_card_draw(self, owner: Any | None, card: Any | None) -> dict[str, Any] | None:
        if owner is None or card is None:
            return None
        card_type = getattr(getattr(card, "card_type", None), "value", None)
        if card_type not in {"STATUS", "CURSE"}:
            return None
        combat_state = getattr(owner, "_combat_state", None)
        monsters = getattr(combat_state, "monsters", []) if combat_state is not None else []
        did_damage = False
        for monster in monsters:
            if monster.is_dead():
                continue
            monster.take_damage(self.amount)
            did_damage = True
        if not did_damage:
            return None
        return {"type": "aoe_status_curse_damage", "amount": self.amount}


@dataclass
class RagePower:
    id: str = "Rage"
    name: str = "Rage"
    amount: int = 3
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = True
    can_go_negative: bool = False

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount = max(0, self.amount - amount)

    def at_end_of_round(self) -> bool:
        return True


@dataclass
class AngryPower:
    id: str = "Angry"
    name: str = "Angry"
    amount: int = 1
    owner: str = "monster"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def modify_block(self, block: float) -> float:
        return block

    def on_attacked(self, actual_damage: int, monster: "MonsterBase" = None) -> int:
        if actual_damage <= 0:
            return 0
        if monster is not None:
            monster.gain_strength(self.amount)
        return 0

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount


@dataclass
class RupturePower:
    id: str = "Rupture"
    name: str = "Rupture"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def modify_block(self, block: float) -> float:
        return block

    def at_end_of_round(self) -> bool:
        return False

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def on_hp_lost(self, owner: Any | None, damage_amount: int, *, source_owner: Any | None = None) -> dict[str, Any] | None:
        if owner is None or damage_amount <= 0:
            return None
        normalized_owner = getattr(owner, "id", owner)
        normalized_source = getattr(source_owner, "id", source_owner)
        if normalized_source != normalized_owner:
            return None
        owner.add_power(create_power("Strength", self.amount, "player"))
        if hasattr(owner, "strength"):
            owner.strength += self.amount
        return {"type": "strength", "amount": self.amount}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class BrutalityPower:
    id: str = "Brutality"
    name: str = "Brutality"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def modify_block(self, block: float) -> float:
        return block

    def at_end_of_round(self) -> bool:
        return False

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_start_of_turn_post_draw(self, owner: Any | None) -> dict[str, Any] | None:
        if owner is None:
            return None
        combat_state = getattr(owner, "_combat_state", None)
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is not None:
            card_manager.draw_cards(self.amount)
        if hasattr(owner, "lose_hp"):
            owner.lose_hp(self.amount, source_owner=owner)
        else:
            owner.hp = max(0, owner.hp - self.amount)
        return {"type": "draw_and_lose_hp", "amount": self.amount}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class CorruptionPower:
    id: str = "Corruption"
    name: str = "Corruption"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF


@dataclass
class DoubleTapPower:
    id: str = "DoubleTap"
    name: str = "DoubleTap"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = True
    can_go_negative: bool = False

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount = max(0, self.amount - amount)

    def on_player_card_played(self, owner: Any | None = None, card: Any | None = None) -> dict[str, Any] | None:
        if owner is None or card is None or self.amount <= 0:
            return None
        if not hasattr(card, "is_attack") or not card.is_attack():
            return None
        if bool(getattr(card, "purge_on_use", False)):
            return None
        combat_state = getattr(owner, "_combat_state", None)
        engine = getattr(combat_state, "engine", None)
        if engine is None:
            return None
        if not engine._repeat_same_instance_card(card, target_idx=getattr(card, "_last_target_idx", None)):
            return None
        self.amount = max(0, self.amount - 1)
        if self.amount <= 0 and hasattr(owner, "remove_power"):
            owner.remove_power(self.id)
        return {"type": "double_tap_repeat", "remaining": self.amount}

    def at_end_of_round(self) -> bool:
        return True


@dataclass
class JuggernautPower:
    id: str = "Juggernaut"
    name: str = "Juggernaut"
    amount: int = 5
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def on_gain_block(self, owner: Any | None, block_amount: int) -> dict[str, Any] | None:
        if owner is None or block_amount <= 0:
            return None
        combat_state = getattr(owner, "_combat_state", None)
        card_manager = getattr(combat_state, "card_manager", None)
        monsters = getattr(combat_state, "monsters", []) if combat_state is not None else []
        living = [monster for monster in monsters if not monster.is_dead()]
        if not living:
            return None
        if len(living) == 1 or getattr(card_manager, "rng", None) is None:
            target = living[0]
        else:
            target = living[card_manager.rng.random_int(len(living) - 1)]
        target.take_damage(self.amount)
        return {"type": "damage_random_enemy", "amount": self.amount}


@dataclass
class NoDrawPower:
    id: str = "No Draw"
    name: str = "No Draw"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_round(self) -> bool:
        return True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class ChokePower:
    id: str = "Choked"
    name: str = "Choked"
    amount: int = 3
    owner: str = "monster_0"
    power_type: PowerType = PowerType.DEBUFF
    _skip_first_card: bool = True

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def on_player_card_played(self, owner: Any | None = None, card: Any | None = None) -> dict[str, Any] | None:
        if owner is None or self.amount <= 0 or int(getattr(owner, "hp", 0) or 0) <= 0:
            return None
        if self._skip_first_card:
            self._skip_first_card = False
            return None
        owner.hp = max(0, int(getattr(owner, "hp", 0) or 0) - self.amount)
        return {"type": "choke_hp_loss", "amount": self.amount}

    def at_end_of_round(self) -> bool:
        return True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class EnvenomPower:
    id: str = "Envenom"
    name: str = "Envenom"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def on_player_attack_damage(
        self,
        owner: Any | None = None,
        target: Any | None = None,
        actual_damage: int = 0,
        *,
        damage_type: str = "NORMAL",
    ) -> dict[str, Any] | None:
        if owner is None or target is None or self.amount <= 0 or actual_damage <= 0:
            return None
        if damage_type != "NORMAL" or target is owner:
            return None
        target.add_power(create_power("Poison", self.amount, target.id))
        return {"type": "envenom_poison", "amount": self.amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class PhantasmalPower:
    id: str = "Phantasmal"
    name: str = "Phantasmal"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_start_of_turn(self, owner: Any | None) -> dict[str, int] | None:
        if owner is None or self.amount <= 0:
            return None
        owner._double_attack_damage_turns = max(0, int(getattr(owner, "_double_attack_damage_turns", 0) or 0)) + 1
        if hasattr(owner, "powers"):
            owner.powers.remove_power(self.id)
        return {"type": "phantasmal_ready", "amount": self.amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class SpeedPower:
    id: str = "Speed"
    name: str = "Speed"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class FlexPower:
    id: str = "Flex"
    name: str = "Flex"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class ArtifactPower:
    id: str = "Artifact"
    name: str = "Artifact"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        return damage

    def modify_block(self, block: float) -> float:
        return block

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class BattleHymnPower:
    id: str = "BattleHymn"
    name: str = "BattleHymn"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_start_of_turn(self, owner: Any | None = None) -> dict[str, int] | None:
        if owner is None or self.amount <= 0:
            return None
        combat_state = getattr(owner, "_combat_state", None)
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return None
        generated = card_manager.generate_cards_to_hand("Smite", self.amount)
        if not generated:
            return None
        return {"type": "battle_hymn_generate", "count": len(generated)}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class NoBlockPower:
    id: str = "NoBlock"
    name: str = "NoBlock"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.DEBUFF
    is_turn_based: bool = True

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def modify_block(self, block: float) -> float:
        return 0.0

    def on_gain_block(self, owner: Any | None, block_amount: int) -> dict[str, Any] | None:
        if owner is None or block_amount <= 0:
            return None
        if hasattr(owner, "block"):
            owner.block = max(0, int(getattr(owner, "block", 0) or 0) - int(block_amount))
        return {"type": "no_block_prevented", "amount": int(block_amount)}

    def at_end_of_round(self) -> bool:
        self.amount -= 1
        return self.amount <= 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class ConfusedPower:
    id: str = "Confused"
    name: str = "Confused"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.DEBUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class LoseStrengthPower:
    id: str = "Lose Strength"
    name: str = "Lose Strength"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.DEBUFF

    def at_end_of_turn(self, owner: Any | None = None, is_player: bool = True) -> dict[str, int] | None:
        if owner is None or self.amount <= 0:
            return None
        restored_amount = self.amount
        if hasattr(owner, "strength"):
            owner.strength += restored_amount
        self.amount = 0
        if hasattr(owner, "powers"):
            owner.powers.remove_power(self.id)
        return {"type": "restore_strength", "amount": restored_amount}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class LoseDexterityPower:
    id: str = "Lose Dexterity"
    name: str = "Lose Dexterity"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.DEBUFF

    def at_turn_end(self, owner: Any) -> None:
        if hasattr(owner, 'dexterity'):
            owner.dexterity -= self.amount
        self.reduce_power(self.amount)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class EnergizedPower:
    id: str = "Energized"
    name: str = "Energized"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount = min(999, self.amount + amount)

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def on_energy_recharge(self, owner: Any) -> dict[str, int] | None:
        if owner is None or self.amount <= 0:
            return None
        owner.energy += self.amount
        combat_state = getattr(owner, "_combat_state", None)
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is not None:
            card_manager.set_energy(owner.energy)
        if hasattr(owner, "powers"):
            owner.powers.remove_power(self.id)
        return {"type": "energized", "amount": self.amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class EnergizedBluePower:
    id: str = "EnergizedBlue"
    name: str = "EnergizedBlue"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def on_energy_recharge(self, owner: Any) -> dict[str, int] | None:
        if owner is None or self.amount <= 0:
            return None
        owner.energy += self.amount
        combat_state = getattr(owner, "_combat_state", None)
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is not None:
            card_manager.set_energy(owner.energy)
        if hasattr(owner, "powers"):
            owner.powers.remove_power(self.id)
        return {"type": "energized_blue", "amount": self.amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class EquilibriumPower:
    id: str = "Equilibrium"
    name: str = "Equilibrium"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = True

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_turn_pre_end_turn_cards(self, owner: Any, is_player: bool) -> dict[str, int] | None:
        if not is_player or owner is None:
            return None
        combat_state = getattr(owner, "_combat_state", None)
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return None
        retained = 0
        for card in list(card_manager.hand.cards):
            if getattr(card, "is_ethereal", False):
                continue
            card.retain = True
            retained += 1
        if retained <= 0:
            return None
        return {"type": "equilibrium_retain", "count": retained}

    def at_end_of_round(self) -> bool:
        self.amount -= 1
        return self.amount <= 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class RetainCardsPower:
    id: str = "Retain Cards"
    name: str = "Retain Cards"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_turn_pre_end_turn_cards(self, owner: Any, is_player: bool) -> dict[str, int] | None:
        if not is_player or owner is None or self.amount <= 0:
            return None
        if hasattr(owner, "powers") and owner.powers.has_power("Equilibrium"):
            return None
        combat_state = getattr(owner, "_combat_state", None)
        if bool(getattr(combat_state, "_skip_retain_cards_pre_end_turn", False)):
            return None
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return None
        retained = 0
        for card in list(card_manager.hand.cards):
            if retained >= self.amount:
                break
            if getattr(card, "is_ethereal", False):
                continue
            if getattr(card, "retain", False) or getattr(card, "self_retain", False):
                continue
            card.retain = True
            retained += 1
        if retained <= 0:
            return None
        return {"type": "retain_cards", "count": retained}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class PlatedArmorPower:
    id: str = "Plated Armor"
    name: str = "Plated Armor"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class DuplicationPower:
    id: str = "Duplication"
    name: str = "Duplication"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class MantraPower:
    id: str = "Mantra"
    name: str = "Mantra"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


def gain_mantra(player: Any, amount: int) -> dict[str, int | bool]:
    """Add Mantra and enter Divinity when reaching the threshold."""
    from sts_py.engine.combat.stance import StanceType, change_stance

    mantra_power = player.powers.get_power("Mantra")
    if mantra_power is None:
        mantra_power = MantraPower(amount=0, owner=getattr(player, "id", "player"))
        player.add_power(mantra_power)

    mantra_power.stack_power(amount)
    entered_divinity = False
    energy_gain = 0

    current_stance = getattr(getattr(player, "stance", None), "stance_type", StanceType.NEUTRAL)
    if mantra_power.amount >= 10 and current_stance != StanceType.DIVINITY:
        player.powers.remove_power("Mantra")
        change_stance(player, StanceType.DIVINITY)
        player.energy += 3
        entered_divinity = True
        energy_gain = 3

    return {"entered_divinity": entered_divinity, "energy_gain": energy_gain}


def _resolve_owner_card_manager(owner: Any) -> Any | None:
    combat_state = getattr(owner, "_combat_state", None)
    if combat_state is not None:
        return getattr(combat_state, "card_manager", None)
    return None


@dataclass
class DrawCardNextTurnPower:
    id: str = "Draw Card"
    name: str = "Draw Card"
    amount: int = 2
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_start_of_turn_post_draw(self, owner: Any | None) -> dict[str, int] | None:
        if owner is None or self.amount <= 0:
            return None
        card_manager = _resolve_owner_card_manager(owner)
        if card_manager is None:
            return None
        card_manager.draw_cards(self.amount)
        if hasattr(owner, "powers"):
            owner.powers.remove_power(self.id)
        return {"type": "draw_next_turn", "amount": self.amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class NightmarePower:
    id: str = "Nightmare"
    name: str = "Nightmare"
    amount: int = 3
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    stored_card: Any | None = None

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_start_of_turn(self, owner: Any | None) -> dict[str, int] | None:
        if owner is None or self.amount <= 0 or self.stored_card is None:
            return None
        card_manager = _resolve_owner_card_manager(owner)
        if card_manager is None:
            return None
        for _ in range(self.amount):
            generated = self.stored_card.make_stat_equivalent_copy()
            generated.uuid = __import__("uuid").uuid4()
            generated._combat_state = getattr(owner, "_combat_state", None)
            card_manager._add_card_to_hand_with_limit(generated)
        if hasattr(owner, "powers"):
            owner.powers.remove_power(self.id)
        return {"type": "nightmare_generate", "count": self.amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class DoppelgangerPower:
    id: str = "Doppelganger"
    name: str = "Doppelganger"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    draw_amount: int = 0
    _pending_next_turn: bool = True

    def stack_power(self, amount: int) -> None:
        self.amount += amount
        self.draw_amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount
        self.draw_amount -= amount

    def on_energy_recharge(self, owner: Any | None) -> dict[str, int] | None:
        if owner is None or self.amount <= 0 or not self._pending_next_turn:
            return None
        owner.energy += self.amount
        card_manager = _resolve_owner_card_manager(owner)
        if card_manager is not None:
            card_manager.set_energy(owner.energy)
        self._pending_next_turn = False
        return {"type": "doppelganger_energy", "amount": self.amount}

    def at_start_of_turn_post_draw(self, owner: Any | None) -> dict[str, int] | None:
        if owner is None or self.draw_amount <= 0 or self._pending_next_turn:
            return None
        card_manager = _resolve_owner_card_manager(owner)
        if card_manager is None:
            return None
        card_manager.draw_cards(self.draw_amount)
        if hasattr(owner, "powers"):
            owner.powers.remove_power(self.id)
        return {"type": "doppelganger_draw", "amount": self.draw_amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class NextTurnBlockPower:
    id: str = "Next Turn Block"
    name: str = "Next Turn Block"
    amount: int = 4
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_start_of_turn(self, owner: Any | None) -> dict[str, int] | None:
        if owner is None or self.amount <= 0:
            return None
        if hasattr(owner, "gain_block"):
            owner.gain_block(self.amount)
        if hasattr(owner, "powers"):
            owner.powers.remove_power(self.id)
        return {"type": "next_turn_block", "amount": self.amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class DevotionPower:
    id: str = "Devotion"
    name: str = "Devotion"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def at_start_of_turn(self, owner: Any) -> dict[str, int | bool]:
        return gain_mantra(owner, self.amount)

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class DevaPower:
    id: str = "DevaPower"
    name: str = "DevaPower"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False
    energy_gain_amount: int = 1

    def on_energy_recharge(self, owner: Any) -> dict[str, int] | None:
        if owner is None:
            return None
        card_manager = _resolve_owner_card_manager(owner)
        owner.energy += self.energy_gain_amount
        if card_manager is not None:
            card_manager.set_energy(owner.energy)
        gained = self.energy_gain_amount
        self.energy_gain_amount += self.amount
        return {"energy_gained": gained, "next_energy_gain": self.energy_gain_amount}

    def stack_power(self, amount: int) -> None:
        self.amount += amount
        self.energy_gain_amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount
        self.energy_gain_amount = max(0, self.energy_gain_amount - amount)

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
            "energy_gain_amount": self.energy_gain_amount,
        }


@dataclass
class StudyPower:
    id: str = "Study"
    name: str = "Study"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def at_end_of_turn(self, owner: Any, is_player: bool) -> dict[str, int] | None:
        if not is_player:
            return None
        card_manager = _resolve_owner_card_manager(owner)
        if card_manager is None:
            return None
        generated = card_manager.generate_cards_to_draw_pile("Insight", self.amount, shuffle_into=True)
        return {"generated_count": len(generated)}

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class MasterRealityPower:
    id: str = "MasterReality"
    name: str = "MasterReality"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class OmegaPower:
    id: str = "OmegaPower"
    name: str = "OmegaPower"
    amount: int = 50
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def at_end_of_turn(self, owner: Any, is_player: bool) -> dict[str, int] | None:
        if not is_player:
            return None
        combat_state = getattr(owner, "_combat_state", None)
        if combat_state is None:
            return None
        hit_count = 0
        for monster in getattr(combat_state, "monsters", []):
            if monster.is_dead():
                continue
            monster.take_damage(self.amount)
            hit_count += 1
        return {"aoe_damage": self.amount, "targets_hit": hit_count}

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class ForesightPower:
    id: str = "Foresight"
    name: str = "Foresight"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def at_start_of_turn(self, owner: Any) -> dict[str, int | bool]:
        card_manager = _resolve_owner_card_manager(owner)
        if card_manager is None:
            return {}
        result = card_manager.resolve_scry(self.amount, shuffle_if_empty=True)
        return {
            "scry_count": self.amount,
            "discarded_count": len(result.get("discarded", [])),
            "returned_count": len(result.get("returned_to_hand", [])),
        }

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class NirvanaPower:
    id: str = "Nirvana"
    name: str = "Nirvana"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def on_scry(self, owner: Any) -> dict[str, int]:
        owner.gain_block(self.amount)
        return {"block_gain": self.amount}

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class RushdownPower:
    id: str = "Rushdown"
    name: str = "Rushdown"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def on_change_stance(self, owner: Any, old_stance: Any, new_stance: Any) -> dict[str, int] | None:
        old_type = getattr(old_stance, "stance_type", None)
        new_type = getattr(new_stance, "stance_type", None)
        from sts_py.engine.combat.stance import StanceType

        if new_type == StanceType.WRATH and old_type != StanceType.WRATH:
            card_manager = _resolve_owner_card_manager(owner)
            if card_manager is not None:
                card_manager.draw_cards(self.amount)
            return {"draw_amount": self.amount}
        return None

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class LikeWaterPower:
    id: str = "LikeWater"
    name: str = "LikeWater"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def at_end_of_turn_pre_end_turn_cards(self, owner: Any, is_player: bool) -> dict[str, int] | None:
        from sts_py.engine.combat.stance import StanceType

        current_type = getattr(getattr(owner, "stance", None), "stance_type", None)
        if is_player and current_type == StanceType.CALM:
            owner.gain_block(self.amount)
            return {"block_gain": self.amount}
        return None

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class EndTurnDeathPower:
    id: str = "EndTurnDeath"
    name: str = "EndTurnDeath"
    amount: int = -1
    owner: str = "player"
    power_type: PowerType = PowerType.DEBUFF
    is_turn_based: bool = False
    can_go_negative: bool = False

    def at_start_of_turn(self, owner: Any) -> dict[str, int | bool]:
        owner.hp = 0
        owner.powers.remove_power(self.id)
        return {"fatal_hp_loss": True}

    def stack_power(self, amount: int) -> None:
        self.amount = amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class IntangiblePower:
    id: str = "Intangible"
    name: str = "Intangible"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_round(self) -> bool:
        self.amount -= 1
        return self.amount <= 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class FocusPower:
    id: str = "Focus"
    name: str = "Focus"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class BufferPower:
    id: str = "Buffer"
    name: str = "Buffer"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class LoopPower:
    id: str = "Loop"
    name: str = "Loop"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_start_of_turn(self, owner: Any) -> dict[str, int] | None:
        orbs = getattr(owner, "orbs", None)
        if orbs is None:
            return None
        results = orbs.trigger_leftmost_passive(self.amount)
        if not results:
            return None
        return {"type": "loop_trigger", "count": len(results)}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class ReboundPower:
    id: str = "Rebound"
    name: str = "Rebound"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    _skip_first_card: bool = True

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def on_player_card_played(self, owner: Any | None = None, card: Any | None = None) -> dict[str, Any] | None:
        if owner is None or card is None or self.amount <= 0:
            return None
        if self._skip_first_card:
            self._skip_first_card = False
            return None
        if not hasattr(card, "is_power") or card.is_power():
            return None
        if bool(getattr(card, "purge_on_use", False)):
            return None
        card.shuffle_back_into_draw_pile = True
        self.amount = max(0, self.amount - 1)
        if self.amount <= 0 and hasattr(owner, "powers"):
            owner.powers.remove_power(self.id)
        return {"type": "rebound_redirect", "card_id": getattr(card, "card_id", "")}

    def at_end_of_round(self) -> bool:
        return True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class CreativeAIPower:
    id: str = "CreativeAI"
    name: str = "CreativeAI"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_start_of_turn(self, owner: Any) -> dict[str, int] | None:
        if owner is None or self.amount <= 0:
            return None
        combat_state = getattr(owner, "_combat_state", None)
        if combat_state is None:
            return None
        from sts_py.engine.combat.card_effects import _generate_random_power_cards_to_hand

        generated = _generate_random_power_cards_to_hand(combat_state, self.amount)
        if not generated:
            return None
        return {"type": "creative_ai_generate", "count": len(generated)}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class AmplifyPower:
    id: str = "Amplify"
    name: str = "Amplify"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = True

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount = max(0, self.amount - amount)

    def on_player_power_played(self, owner: Any | None = None, card: Any | None = None) -> dict[str, Any] | None:
        if owner is None or card is None or self.amount <= 0:
            return None
        if not hasattr(card, "is_power") or not card.is_power():
            return None
        if bool(getattr(card, "purge_on_use", False)):
            return None
        combat_state = getattr(owner, "_combat_state", None)
        engine = getattr(combat_state, "engine", None)
        if engine is None:
            return None
        if not engine._repeat_same_instance_card(card, target_idx=getattr(card, "_last_target_idx", None)):
            return None
        self.amount = max(0, self.amount - 1)
        if self.amount <= 0 and hasattr(owner, "remove_power"):
            owner.remove_power(self.id)
        return {"type": "amplify_repeat", "remaining": self.amount}

    def at_end_of_round(self) -> bool:
        return True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class EchoPower:
    id: str = "EchoForm"
    name: str = "Echo Form"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    cards_doubled_this_turn: int = 0

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_start_of_turn(self, owner: Any | None = None) -> dict[str, Any] | None:
        self.cards_doubled_this_turn = 0
        return None

    def on_player_card_played(self, owner: Any | None = None, card: Any | None = None) -> dict[str, Any] | None:
        if owner is None or card is None or self.amount <= 0:
            return None
        if bool(getattr(card, "purge_on_use", False)):
            return None
        existing_power_ids = set(getattr(card, "_existing_power_ids_before_play", set()) or set())
        if getattr(card, "card_id", None) == "EchoForm" and self.id not in existing_power_ids:
            return None
        combat_state = getattr(owner, "_combat_state", None)
        engine = getattr(combat_state, "engine", None)
        if engine is None:
            return None
        cards_played = len(getattr(combat_state, "cards_played_this_turn", []) or [])
        if cards_played - self.cards_doubled_this_turn > self.amount:
            return None
        if not engine._repeat_same_instance_card(card, target_idx=getattr(card, "_last_target_idx", None)):
            return None
        self.cards_doubled_this_turn += 1
        return {"type": "echo_repeat", "count": self.cards_doubled_this_turn}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class BurstPower:
    id: str = "Burst"
    name: str = "Burst"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = True

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount = max(0, self.amount - amount)

    def on_player_skill_played(self, owner: Any | None = None, card: Any | None = None) -> dict[str, Any] | None:
        if owner is None or card is None or self.amount <= 0:
            return None
        if not hasattr(card, "is_skill") or not card.is_skill():
            return None
        if bool(getattr(card, "purge_on_use", False)):
            return None
        existing_power_ids = set(getattr(card, "_existing_power_ids_before_play", set()) or set())
        if getattr(card, "card_id", None) == "Burst" and self.id not in existing_power_ids:
            return None
        combat_state = getattr(owner, "_combat_state", None)
        engine = getattr(combat_state, "engine", None)
        if engine is None:
            return None
        if not engine._repeat_same_instance_card(card, target_idx=getattr(card, "_last_target_idx", None)):
            return None
        self.amount = max(0, self.amount - 1)
        if self.amount <= 0 and hasattr(owner, "remove_power"):
            owner.remove_power(self.id)
        return {"type": "burst_repeat", "remaining": self.amount}

    def at_end_of_round(self) -> bool:
        return True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class ToolsOfTheTradePower:
    id: str = "Tools Of The Trade"
    name: str = "Tools Of The Trade"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_start_of_turn_post_draw(self, owner: Any | None) -> dict[str, int] | None:
        if owner is None or self.amount <= 0:
            return None
        combat_state = getattr(owner, "_combat_state", None)
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return None
        from sts_py.engine.combat.card_effects import _move_hand_card_to_discard

        hand_before = card_manager.get_hand_size()
        card_manager.draw_cards(self.amount)
        discarded = 0
        for _ in range(min(self.amount, card_manager.get_hand_size())):
            if card_manager.get_hand_size() <= 0:
                break
            _move_hand_card_to_discard(card_manager, hand_index=0)
            discarded += 1
        return {"type": "tools_of_the_trade", "drawn_upper_bound": self.amount, "hand_before": hand_before, "discarded": discarded}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class WraithFormPower:
    id: str = "WraithForm"
    name: str = "Wraith Form"
    amount: int = -1
    owner: str = "player"
    power_type: PowerType = PowerType.DEBUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_turn(self, owner: Any | None = None, is_player: bool = True) -> dict[str, int] | None:
        if owner is None or not is_player or self.amount == 0:
            return None
        owner.add_power(create_power("Dexterity", self.amount, "player"))
        if hasattr(owner, "dexterity"):
            owner.dexterity += self.amount
        return {"type": "wraith_form_dexterity", "amount": self.amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class LockOnPower:
    id: str = "Lockon"
    name: str = "Lockon"
    amount: int = 0
    owner: str = "monster"
    power_type: PowerType = PowerType.DEBUFF
    is_turn_based: bool = True

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_round(self) -> bool:
        self.amount -= 1
        return self.amount <= 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class ElectroPower:
    id: str = "Electro"
    name: str = "Electro"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class StaticDischargePower:
    id: str = "StaticDischarge"
    name: str = "Static Discharge"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def on_player_attacked(
        self,
        owner: Any | None = None,
        damage_amount: int = 0,
        *,
        damage_type: str = "NORMAL",
        source_owner: Any | None = None,
    ) -> dict[str, Any] | None:
        if owner is None or self.amount <= 0 or damage_amount <= 0:
            return None
        if damage_type != "NORMAL":
            return None
        combat_state = getattr(owner, "_combat_state", None)
        engine = getattr(combat_state, "engine", None)
        if engine is None:
            return None
        from sts_py.engine.combat.orbs import LightningOrb

        for _ in range(self.amount):
            engine._channel_orb(LightningOrb())
        return {"type": "static_discharge_channel", "count": self.amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class BiasPower:
    id: str = "Bias"
    name: str = "Bias"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.DEBUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_start_of_turn(self, owner: Any) -> dict[str, int] | None:
        if owner is None or self.amount <= 0:
            return None
        owner.add_power(create_power("Focus", -self.amount, "player"))
        if hasattr(owner, "focus"):
            owner.focus -= self.amount
        return {"type": "lose_focus", "amount": self.amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class StormPower:
    id: str = "Storm"
    name: str = "Storm"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def on_player_power_played(self, owner: Any | None = None, card: Any | None = None) -> dict[str, int] | None:
        if owner is None or card is None or self.amount <= 0:
            return None
        if not hasattr(card, "is_power") or not card.is_power():
            return None
        combat_state = getattr(owner, "_combat_state", None)
        engine = getattr(combat_state, "engine", None)
        if engine is None:
            return None
        from sts_py.engine.combat.orbs import LightningOrb

        for _ in range(self.amount):
            engine._channel_orb(LightningOrb())
        return {"type": "storm_channel", "count": self.amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class HeatsinksPower:
    id: str = "Heatsinks"
    name: str = "Heatsinks"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def on_player_power_played(self, owner: Any | None = None, card: Any | None = None) -> dict[str, int] | None:
        if owner is None or card is None or self.amount <= 0:
            return None
        if not hasattr(card, "is_power") or not card.is_power():
            return None
        combat_state = getattr(owner, "_combat_state", None)
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return None
        hand_limit_offset = 1 if card in getattr(card_manager.hand, "cards", []) else 0
        card_manager.draw_cards(self.amount, hand_limit_offset=hand_limit_offset)
        return {"type": "heatsinks_draw", "count": self.amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class MachineLearningPower:
    id: str = "MachineLearning"
    name: str = "MachineLearning"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_start_of_turn_post_draw(self, owner: Any | None) -> dict[str, int] | None:
        if owner is None or self.amount <= 0:
            return None
        combat_state = getattr(owner, "_combat_state", None)
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return None
        card_manager.draw_cards(self.amount)
        return {"type": "machine_learning_draw", "count": self.amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class HelloPower:
    id: str = "Hello"
    name: str = "Hello"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_start_of_turn(self, owner: Any | None) -> dict[str, int] | None:
        if owner is None or self.amount <= 0:
            return None
        combat_state = getattr(owner, "_combat_state", None)
        if combat_state is None:
            return None
        from sts_py.engine.combat.card_effects import _generate_random_defect_common_cards_to_hand

        generated = _generate_random_defect_common_cards_to_hand(combat_state, self.amount)
        if not generated:
            return None
        return {"type": "hello_generate", "count": len(generated)}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class RepairPower:
    id: str = "Repair"
    name: str = "Repair"
    amount: int = 7
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def on_victory(self, owner: Any | None = None) -> int:
        if owner is None or int(getattr(owner, "hp", 0) or 0) <= 0:
            return 0
        return max(0, int(self.amount))

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class PoisonPower:
    id: str = "Poison"
    name: str = "Poison"
    amount: int = 0
    owner: str = "monster_0"
    power_type: PowerType = PowerType.DEBUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_round(self) -> bool:
        return self.amount <= 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class NoxiousFumesPower:
    id: str = "NoxiousFumes"
    name: str = "NoxiousFumes"
    amount: int = 0
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_turn(self, owner: Any, is_player: bool) -> dict[str, int] | None:
        if not is_player or self.amount <= 0:
            return None
        return {"type": "apply_poison_all_enemies", "amount": self.amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class CorpseExplosionPower:
    id: str = "CorpseExplosion"
    name: str = "CorpseExplosion"
    amount: int = 1
    owner: str = "monster_0"
    power_type: PowerType = PowerType.DEBUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_round(self) -> bool:
        return self.amount <= 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class InfiniteBladesPower:
    id: str = "InfiniteBlades"
    name: str = "InfiniteBlades"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_start_of_turn(self, owner: Any) -> dict[str, int] | None:
        combat_state = getattr(owner, "_combat_state", None)
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return None
        card_manager.generate_cards_to_hand("Shiv", self.amount)
        return {"type": "generate_shiv", "count": self.amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class AccuracyPower:
    id: str = "Accuracy"
    name: str = "Accuracy"
    amount: int = 4
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class ThousandCutsPower:
    id: str = "ThousandCuts"
    name: str = "ThousandCuts"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def on_player_card_played(self, owner: Any | None = None, card: Any | None = None) -> dict[str, Any] | None:
        if owner is None or self.amount <= 0:
            return None
        combat_state = getattr(owner, "_combat_state", None)
        monsters = getattr(combat_state, "monsters", []) if combat_state is not None else []
        did_damage = False
        for monster in monsters:
            if monster.is_dead():
                continue
            monster.take_damage(self.amount)
            did_damage = True
        if not did_damage:
            return None
        return {"type": "aoe_on_card_played", "amount": self.amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class AfterImagePower:
    id: str = "AfterImage"
    name: str = "AfterImage"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def on_player_card_played(self, owner: Any | None = None, card: Any | None = None) -> dict[str, Any] | None:
        if owner is None or self.amount <= 0:
            return None
        owner.gain_block(self.amount)
        return {"type": "gain_block_on_card_played", "amount": self.amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class BlurPower:
    id: str = "Blur"
    name: str = "Blur"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    is_turn_based: bool = True

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_round(self) -> bool:
        self.amount -= 1
        return self.amount <= 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class SurroundedPower:
    id: str = "Surrounded"
    name: str = "Surrounded"
    amount: int = -1
    owner: str = "player"
    power_type: PowerType = PowerType.DEBUFF

    def stack_power(self, amount: int) -> None:
        self.amount = -1

    def reduce_power(self, amount: int) -> None:
        self.amount = -1

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class BackAttackPower:
    id: str = "BackAttack"
    name: str = "BackAttack"
    amount: int = -1
    owner: str = "monster"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount = -1

    def reduce_power(self, amount: int) -> None:
        self.amount = -1

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class BeatOfDeathPower:
    id: str = "BeatOfDeath"
    name: str = "BeatOfDeath"
    amount: int = 1
    owner: str = "monster"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def on_player_card_played(self, owner: Any | None = None, card: Any | None = None) -> dict[str, Any] | None:
        if owner is None or self.amount <= 0:
            return None
        combat_state = getattr(owner, "_combat_state", None) or getattr(owner, "state", None)
        player = getattr(combat_state, "player", None) if combat_state is not None else None
        if player is None:
            return None
        player.take_damage(self.amount, damage_type="THORNS", source_owner=owner)
        return {"type": "beat_of_death", "amount": self.amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class InvinciblePower:
    id: str = "Invincible"
    name: str = "Invincible"
    amount: int = 300
    owner: str = "monster"
    power_type: PowerType = PowerType.BUFF
    max_amount: int = 300

    def __post_init__(self) -> None:
        self.max_amount = self.amount

    def stack_power(self, amount: int) -> None:
        self.amount += amount
        self.max_amount = max(self.max_amount, self.amount)

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_start_of_turn(self, owner: Any | None = None) -> dict[str, int] | None:
        self.amount = self.max_amount
        return {"type": "invincible_reset", "amount": self.amount}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
            "max_amount": self.max_amount,
        }


@dataclass
class PainfulStabsPower:
    id: str = "Painful Stabs"
    name: str = "Painful Stabs"
    amount: int = -1
    owner: str = "monster"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount = -1

    def reduce_power(self, amount: int) -> None:
        self.amount = -1

    def on_inflict_damage(
        self,
        owner: Any | None = None,
        damage_amount: int = 0,
        target: Any | None = None,
        *,
        damage_type: str = "NORMAL",
    ) -> dict[str, Any] | None:
        if owner is None or target is None or damage_amount <= 0 or damage_type == "THORNS":
            return None
        combat_state = getattr(owner, "_combat_state", None) or getattr(owner, "state", None)
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is None:
            return None
        card_manager.discard_pile.add(CardInstance(card_id="Wound"))
        return {"type": "painful_stabs_wound", "amount": 1}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class EntangledPower:
    id: str = "Entangled"
    name: str = "Entangled"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.DEBUFF
    is_turn_based: bool = True

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_turn(self, owner: Any | None = None, is_player: bool = True) -> dict[str, Any] | None:
        if is_player and owner is not None and hasattr(owner, "powers"):
            owner.powers.remove_power(self.id)
            return {"type": "remove_entangled"}
        return None

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class MagnetismPower:
    id: str = "Magnetism"
    name: str = "Magnetism"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_start_of_turn(self, owner: Any | None = None) -> dict[str, Any] | None:
        if owner is None or self.amount <= 0:
            return None
        combat_state = getattr(owner, "_combat_state", None)
        card_manager = getattr(combat_state, "card_manager", None)
        monsters = getattr(combat_state, "monsters", []) if combat_state is not None else []
        if card_manager is None or not any(not monster.is_dead() for monster in monsters):
            return None
        from sts_py.engine.combat.card_effects import _generate_random_colorless_combat_cards_to_hand

        generated = _generate_random_colorless_combat_cards_to_hand(combat_state, self.amount)
        if not generated:
            return None
        return {"type": "magnetism_generate", "count": len(generated)}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class MayhemPower:
    id: str = "Mayhem"
    name: str = "Mayhem"
    amount: int = 1
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_start_of_turn(self, owner: Any | None = None) -> dict[str, Any] | None:
        if owner is None or self.amount <= 0:
            return None
        combat_state = getattr(owner, "_combat_state", None)
        engine = getattr(combat_state, "engine", None)
        card_manager = getattr(combat_state, "card_manager", None)
        if engine is None or card_manager is None:
            return None

        autoplay_count = 0
        for _ in range(self.amount):
            if card_manager.draw_pile.is_empty():
                if card_manager.discard_pile.is_empty():
                    break
                card_manager._shuffle_discard_into_draw(card_manager.rng)
            top_card = card_manager.draw_pile.pop()
            if top_card is None:
                break
            top_card._combat_state = combat_state
            top_card.free_to_play_once = True
            if engine.autoplay_card_instance(top_card):
                autoplay_count += 1
            else:
                card_manager.discard_pile.add(top_card)
        if autoplay_count <= 0:
            return None
        return {"type": "mayhem_autoplay", "count": autoplay_count}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class PanachePower:
    id: str = "Panache"
    name: str = "Panache"
    amount: int = 10
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    cards_until_trigger: int = 5

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_start_of_turn(self, owner: Any | None = None) -> dict[str, Any] | None:
        self.cards_until_trigger = 5
        return {"type": "panache_reset", "remaining": self.cards_until_trigger}

    def on_player_card_played(self, owner: Any | None = None, card: Any | None = None) -> dict[str, Any] | None:
        if owner is None or self.amount <= 0:
            return None
        self.cards_until_trigger -= 1
        if self.cards_until_trigger > 0:
            return {"type": "panache_progress", "remaining": self.cards_until_trigger}
        combat_state = getattr(owner, "_combat_state", None)
        monsters = getattr(combat_state, "monsters", []) if combat_state is not None else []
        hit_count = 0
        for monster in monsters:
            if monster.is_dead():
                continue
            monster.take_damage(self.amount)
            hit_count += 1
        self.cards_until_trigger = 5
        if hit_count <= 0:
            return {"type": "panache_progress", "remaining": self.cards_until_trigger}
        return {"type": "panache_burst", "damage": self.amount, "targets": hit_count}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
            "cards_until_trigger": self.cards_until_trigger,
        }


@dataclass
class SadisticNaturePower:
    id: str = "Sadistic"
    name: str = "Sadistic Nature"
    amount: int = 5
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def on_player_apply_power_to_enemy(
        self,
        owner: Any | None = None,
        target: Any | None = None,
        power: Any | None = None,
    ) -> dict[str, Any] | None:
        if owner is None or target is None or power is None or self.amount <= 0:
            return None
        if target is owner or target.is_dead():
            return None
        if getattr(power, "power_type", None) != PowerType.DEBUFF:
            return None
        if getattr(power, "id", "") == "Shackled":
            return None
        target.take_damage(self.amount)
        return {"type": "sadistic_nature", "damage": self.amount, "target": getattr(target, "id", "")}

    def at_end_of_round(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
        }


@dataclass
class TheBombPower:
    id: str = "TheBomb"
    name: str = "The Bomb"
    amount: int = 3
    owner: str = "player"
    power_type: PowerType = PowerType.BUFF
    damage: int = 40
    allow_parallel_instances: bool = True

    def stack_power(self, amount: int) -> None:
        self.amount += amount

    def reduce_power(self, amount: int) -> None:
        self.amount -= amount

    def at_end_of_turn(self, owner: Any | None = None, is_player: bool = True) -> dict[str, Any] | None:
        if not is_player or owner is None:
            return None
        combat_state = getattr(owner, "_combat_state", None)
        monsters = getattr(combat_state, "monsters", []) if combat_state is not None else []
        alive_monsters = [monster for monster in monsters if not monster.is_dead()]
        if not alive_monsters:
            return None
        if self.amount <= 1:
            for monster in alive_monsters:
                monster.take_damage(self.damage)
            self.amount = 0
            return {"type": "the_bomb_explode", "damage": self.damage, "targets": len(alive_monsters)}
        self.amount -= 1
        return {"type": "the_bomb_countdown", "remaining": self.amount}

    def at_end_of_round(self) -> bool:
        return self.amount <= 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "owner": self.owner,
            "power_type": self.power_type.name,
            "damage": self.damage,
        }


POWER_CLASSES = {
    "Strength": StrengthPower,
    "Dexterity": DexterityPower,
    "EnergizedBlue": EnergizedBluePower,
    "Equilibrium": EquilibriumPower,
    "Vulnerable": VulnerablePower,
    "Weak": WeakPower,
    "Curl Up": CurlUpPower,
    "Ritual": RitualPower,
    "Anger": AngerPower,
    "Angry": AngryPower,
    "DemonForm": DemonFormPower,
    "Metallicize": MetallicizePower,
    "Thorns": ThornsPower,
    "FlameBarrier": FlameBarrierPower,
    "Regen": RegenPower,
    "FeelNoPain": FeelNoPainPower,
    "DarkEmbrace": DarkEmbracePower,
    "Combust": CombustPower,
    "Enrage": EnragePower,
    "FireBreathing": FireBreathingPower,
    "BattleHymn": BattleHymnPower,
    "Evolve": EvolvePower,
    "Rage": RagePower,
    "Rupture": RupturePower,
    "Brutality": BrutalityPower,
    "Corruption": CorruptionPower,
    "DoubleTap": DoubleTapPower,
    "Juggernaut": JuggernautPower,
    "NoDraw": NoDrawPower,
    "No Draw": NoDrawPower,
    "NoBlock": NoBlockPower,
    "NoBlockPower": NoBlockPower,
    "Choked": ChokePower,
    "Envenom": EnvenomPower,
    "Phantasmal": PhantasmalPower,
    "Speed": SpeedPower,
    "Flex": FlexPower,
    "Artifact": ArtifactPower,
    "Plated Armor": PlatedArmorPower,
    "Duplication": DuplicationPower,
    "Energized": EnergizedPower,
    "Lose Strength": LoseStrengthPower,
    "Lose Dexterity": LoseDexterityPower,
    "Mantra": MantraPower,
    "DevaPower": DevaPower,
    "Draw Card": DrawCardNextTurnPower,
    "Nightmare": NightmarePower,
    "Doppelganger": DoppelgangerPower,
    "Next Turn Block": NextTurnBlockPower,
    "Devotion": DevotionPower,
    "Study": StudyPower,
    "MasterReality": MasterRealityPower,
    "OmegaPower": OmegaPower,
    "Foresight": ForesightPower,
    "Nirvana": NirvanaPower,
    "Rushdown": RushdownPower,
    "LikeWater": LikeWaterPower,
    "EndTurnDeath": EndTurnDeathPower,
    "Intangible": IntangiblePower,
    "Focus": FocusPower,
    "Buffer": BufferPower,
    "Loop": LoopPower,
    "Rebound": ReboundPower,
    "CreativeAI": CreativeAIPower,
    "Amplify": AmplifyPower,
    "Burst": BurstPower,
    "Tools Of The Trade": ToolsOfTheTradePower,
    "Retain Cards": RetainCardsPower,
    "WraithForm": WraithFormPower,
    "Wraith Form v2": WraithFormPower,
    "Echo Form": EchoPower,
    "EchoForm": EchoPower,
    "Lockon": LockOnPower,
    "Electro": ElectroPower,
    "Static Discharge": StaticDischargePower,
    "StaticDischarge": StaticDischargePower,
    "Bias": BiasPower,
    "Storm": StormPower,
    "Heatsinks": HeatsinksPower,
    "MachineLearning": MachineLearningPower,
    "Hello": HelloPower,
    "Repair": RepairPower,
    "Poison": PoisonPower,
    "NoxiousFumes": NoxiousFumesPower,
    "CorpseExplosion": CorpseExplosionPower,
    "InfiniteBlades": InfiniteBladesPower,
    "Magnetism": MagnetismPower,
    "Mayhem": MayhemPower,
    "Panache": PanachePower,
    "Sadistic": SadisticNaturePower,
    "Accuracy": AccuracyPower,
    "ThousandCuts": ThousandCutsPower,
    "AfterImage": AfterImagePower,
    "Blur": BlurPower,
    "Frail": FrailPower,
    "Spore Cloud": SporeCloudPower,
    "Thievery": ThieveryPower,
    "Sharp Hide": SharpHidePower,
    "Surrounded": SurroundedPower,
    "BackAttack": BackAttackPower,
    "BeatOfDeath": BeatOfDeathPower,
    "Invincible": InvinciblePower,
    "Painful Stabs": PainfulStabsPower,
    "Entangled": EntangledPower,
    "TheBomb": TheBombPower,
}


def create_power(power_id: str, amount: int, owner: str = "player", is_source_monster: bool = False, turn_has_ended: bool = False) -> Power:
    """Factory function to create a power by ID."""
    power_class = POWER_CLASSES.get(power_id)
    if power_class is None:
        raise ValueError(f"Unknown power ID: {power_id}")
    power = power_class(amount=amount, owner=owner)
    if power_id == "Vulnerable" and is_source_monster:
        power.is_source_monster = True
        if turn_has_ended:
            power._just_applied = True
    return power


def power_from_dict(data: dict) -> Power:
    """Deserialize a power from dict."""
    power_id = data["id"]
    amount = data["amount"]
    owner = data.get("owner", "player")
    if power_id == "Panache":
        power = PanachePower(amount=amount, owner=owner)
        power.cards_until_trigger = int(data.get("cards_until_trigger", 5) or 5)
        return power
    if power_id == "TheBomb":
        return TheBombPower(amount=amount, owner=owner, damage=int(data.get("damage", 40) or 40))
    return create_power(power_id, amount, owner)
