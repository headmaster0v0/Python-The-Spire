"""Power container for managing powers on entities.

Provides a unified interface for adding, removing, and querying powers,
as well as computing modified damage/block values.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sts_py.engine.combat.powers import (
    Power, PowerType,
    StrengthPower, DexterityPower, VulnerablePower, WeakPower,
    CurlUpPower, RitualPower, AngryPower,
)

if TYPE_CHECKING:
    pass


@dataclass
class PowerChangeLog:
    """Record of a power change event.
    
    Matches Java DataRecorder PowerChangeLog for debugging and replay.
    """
    power_id: str
    action: str  # "applied", "removed", "stacked", "reduced"
    amount: int
    previous_amount: int
    target_type: str  # "player" or "monster"
    target_id: str
    floor: int = 0
    turn: int = 0
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> dict:
        return {
            "powerId": self.power_id,
            "action": self.action,
            "amount": self.amount,
            "previousAmount": self.previous_amount,
            "targetType": self.target_type,
            "targetId": self.target_id,
            "floor": self.floor,
            "turn": self.turn,
        }


@dataclass
class PowerContainer:
    """Container for managing powers on an entity.
    
    Handles:
    - Adding/removing powers
    - Stacking powers
    - Computing modified values (damage, block)
    - End of round processing
    - Power change tracking for debugging/replay
    """
    powers: list[Power] = field(default_factory=list)
    change_log: list[PowerChangeLog] = field(default_factory=list)
    target_type: str = "unknown"  # "player" or "monster"
    target_id: str = ""
    _floor: int = 0
    _turn: int = 0
    
    def set_context(self, target_type: str, target_id: str, floor: int = 0, turn: int = 0) -> None:
        """Set context for logging."""
        self.target_type = target_type
        self.target_id = target_id
        self._floor = floor
        self._turn = turn
    
    def _log_change(self, power_id: str, action: str, amount: int, previous_amount: int) -> None:
        """Log a power change event."""
        log = PowerChangeLog(
            power_id=power_id,
            action=action,
            amount=amount,
            previous_amount=previous_amount,
            target_type=self.target_type,
            target_id=self.target_id,
            floor=self._floor,
            turn=self._turn,
        )
        self.change_log.append(log)
    
    def add_power(self, power: Power) -> None:
        """Add a power, stacking if possible."""
        if hasattr(power, "owner"):
            if self.target_type == "player" and getattr(power, "owner", None) in {"player", "monster"}:
                power.owner = "player"
            elif self.target_type == "monster" and getattr(power, "owner", None) in {"player", "monster"}:
                power.owner = "monster"
        if bool(getattr(power, "allow_parallel_instances", False)):
            self.powers.append(power)
            self._log_change(power.id, "applied", power.amount, 0)
            return
        existing = self.get_power(power.id)
        if existing is not None:
            prev = existing.amount
            existing.stack_power(power.amount)
            if power.id == "Vulnerable" and getattr(power, 'is_source_monster', False):
                existing._just_applied = False
            self._log_change(power.id, "stacked", existing.amount, prev)
        else:
            self.powers.append(power)
            self._log_change(power.id, "applied", power.amount, 0)
    
    def remove_power(self, power_id: str) -> Power | None:
        """Remove a power by ID. Returns the removed power or None."""
        for i, p in enumerate(self.powers):
            if p.id == power_id:
                prev = p.amount
                removed = self.powers.pop(i)
                self._log_change(power_id, "removed", 0, prev)
                return removed
        return None

    def remove_power_instance(self, power: Power) -> Power | None:
        """Remove an exact power instance."""
        for i, existing in enumerate(self.powers):
            if existing is not power:
                continue
            prev = existing.amount
            removed = self.powers.pop(i)
            self._log_change(existing.id, "removed", 0, prev)
            return removed
        return None

    def reduce_power(self, power_id: str, amount: int) -> Power | None:
        """Reduce a power by amount, removing it if depleted."""
        power = self.get_power(power_id)
        if power is None:
            return None
        prev = power.amount
        if hasattr(power, "reduce_power"):
            power.reduce_power(amount)
        else:
            power.amount -= amount
        self._log_change(power_id, "reduced", power.amount, prev)
        if getattr(power, "amount", 0) <= 0:
            self.remove_power(power_id)
        return power
    
    def get_power(self, power_id: str) -> Power | None:
        """Get a power by ID."""
        for p in self.powers:
            if p.id == power_id:
                return p
        return None
    
    def has_power(self, power_id: str) -> bool:
        """Check if entity has a power."""
        return self.get_power(power_id) is not None
    
    def get_power_amount(self, power_id: str) -> int:
        """Get the amount of a power, or 0 if not present."""
        power = self.get_power(power_id)
        return power.amount if power else 0
    
    def get_strength(self) -> int:
        """Get total strength (can be negative)."""
        return self.get_power_amount("Strength")
    
    def get_dexterity(self) -> int:
        """Get total dexterity (can be negative)."""
        return self.get_power_amount("Dexterity")
    
    def get_vulnerable(self) -> int:
        """Get vulnerable stacks."""
        return self.get_power_amount("Vulnerable")
    
    def get_weak(self) -> int:
        """Get weak stacks."""
        return self.get_power_amount("Weak")
    
    def is_vulnerable(self) -> bool:
        """Check if entity is vulnerable."""
        return self.has_power("Vulnerable")
    
    def is_weak(self) -> bool:
        """Check if entity is weak."""
        return self.has_power("Weak")
    
    def apply_damage_modifiers(self, base_damage: float, damage_type: str = "NORMAL") -> float:
        """Apply all damage-giving modifiers from powers.
        
        Order matters: Strength is additive, Weak is multiplicative.
        From Java: Strength is applied in atDamageGive, Weak in atDamageGive.
        """
        damage = base_damage
        
        for power in self.powers:
            if hasattr(power, "at_damage_give"):
                damage = power.at_damage_give(damage, damage_type)
        
        return damage
    
    def apply_damage_receive_modifiers(self, base_damage: float, damage_type: str = "NORMAL") -> float:
        """Apply all damage-receiving modifiers from powers.

        Vulnerable increases damage taken.
        """
        damage = base_damage

        for power in self.powers:
            if hasattr(power, "at_damage_receive"):
                damage = power.at_damage_receive(damage, damage_type)

        return damage

    def apply_damage_final_give_modifiers(self, base_damage: float, damage_type: str = "NORMAL") -> float:
        """Apply final damage-giving modifiers from powers.

        This is called after all other atDamageGive modifiers.
        Used by powers like DemonForm (via Forge effect).
        """
        damage = base_damage

        for power in self.powers:
            if hasattr(power, 'at_damage_final_give'):
                damage = power.at_damage_final_give(damage, damage_type)

        return damage

    def apply_damage_final_receive_modifiers(self, base_damage: float, damage_type: str = "NORMAL") -> float:
        """Apply final damage-receiving modifiers from powers.

        This is called after all other atDamageReceive modifiers.
        """
        damage = base_damage

        for power in self.powers:
            if hasattr(power, 'at_damage_final_receive'):
                damage = power.at_damage_final_receive(damage, damage_type)

        return damage
    
    def apply_block_modifiers(self, base_block: float) -> float:
        """Apply all block modifiers from powers.
        
        Dexterity adds to block.
        """
        block = base_block
        
        for power in self.powers:
            if hasattr(power, "modify_block"):
                block = power.modify_block(block)
        
        return max(0.0, block)
    
    def at_end_of_round(self) -> list[str]:
        """Process end of round for all powers.
        
        Returns list of power IDs to remove.
        """
        to_remove = []
        
        for power in self.powers:
            if hasattr(power, "at_end_of_round") and power.at_end_of_round():
                to_remove.append(power)
        
        for power in to_remove:
            self.remove_power_instance(power)
        
        return [power.id for power in to_remove]

    def at_start_of_turn(self, owner: Any | None = None) -> list[dict[str, Any]]:
        """Process start-of-turn hooks for all powers."""
        results: list[dict[str, Any]] = []
        for power in list(self.powers):
            if hasattr(power, "at_start_of_turn"):
                result = power.at_start_of_turn(owner)
                if result:
                    results.append(result)
        return results

    def on_energy_recharge(self, owner: Any | None = None) -> list[dict[str, Any]]:
        """Process hooks that trigger when the owner's energy is refreshed."""
        results: list[dict[str, Any]] = []
        for power in list(self.powers):
            if hasattr(power, "on_energy_recharge"):
                result = power.on_energy_recharge(owner)
                if result:
                    results.append(result)
        return results

    def at_start_of_turn_post_draw(self, owner: Any | None = None) -> list[dict[str, Any]]:
        """Process hooks that happen after the player's start-of-turn draw."""
        results: list[dict[str, Any]] = []
        for power in list(self.powers):
            if hasattr(power, "at_start_of_turn_post_draw"):
                result = power.at_start_of_turn_post_draw(owner)
                if result:
                    results.append(result)
        return results

    def on_hp_lost(
        self,
        owner: Any | None = None,
        amount: int = 0,
        *,
        source_owner: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Process hooks that react to the owner losing HP."""
        results: list[dict[str, Any]] = []
        for power in list(self.powers):
            if hasattr(power, "on_hp_lost"):
                result = power.on_hp_lost(owner, amount, source_owner=source_owner)
                if result:
                    results.append(result)
        return results

    def on_player_attacked(
        self,
        owner: Any | None = None,
        amount: int = 0,
        *,
        damage_type: str = "NORMAL",
        source_owner: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Process hooks that react to the player taking attack damage."""
        results: list[dict[str, Any]] = []
        for power in list(self.powers):
            if hasattr(power, "on_player_attacked"):
                result = power.on_player_attacked(
                    owner,
                    amount,
                    damage_type=damage_type,
                    source_owner=source_owner,
                )
                if result:
                    results.append(result)
        return results

    def on_inflict_damage(
        self,
        owner: Any | None = None,
        amount: int = 0,
        target: Any | None = None,
        *,
        damage_type: str = "NORMAL",
    ) -> list[dict[str, Any]]:
        """Process hooks that react to this owner inflicting damage."""
        results: list[dict[str, Any]] = []
        for power in list(self.powers):
            if hasattr(power, "on_inflict_damage"):
                result = power.on_inflict_damage(owner, amount, target, damage_type=damage_type)
                if result:
                    results.append(result)
        return results

    def on_gain_block(self, owner: Any | None = None, amount: int = 0) -> list[dict[str, Any]]:
        """Process hooks that react to the owner gaining block."""
        results: list[dict[str, Any]] = []
        for power in list(self.powers):
            if hasattr(power, "on_gain_block"):
                result = power.on_gain_block(owner, amount)
                if result:
                    results.append(result)
        return results

    def on_card_draw(self, owner: Any | None = None, card: Any | None = None) -> list[dict[str, Any]]:
        """Process hooks that react to drawing a card."""
        results: list[dict[str, Any]] = []
        for power in list(self.powers):
            if hasattr(power, "on_card_draw"):
                result = power.on_card_draw(owner, card)
                if result:
                    results.append(result)
        return results

    def on_player_skill_played(self, owner: Any | None = None, card: Any | None = None) -> list[dict[str, Any]]:
        """Process hooks that react to the player playing a skill card."""
        results: list[dict[str, Any]] = []
        for power in list(self.powers):
            if hasattr(power, "on_player_skill_played"):
                result = power.on_player_skill_played(owner, card)
                if result:
                    results.append(result)
        return results

    def on_player_card_played(self, owner: Any | None = None, card: Any | None = None) -> list[dict[str, Any]]:
        """Process hooks that react to the player successfully playing any card."""
        results: list[dict[str, Any]] = []
        for power in list(self.powers):
            if hasattr(power, "on_player_card_played"):
                result = power.on_player_card_played(owner, card)
                if result:
                    results.append(result)
        return results

    def on_player_attack_damage(
        self,
        owner: Any | None = None,
        target: Any | None = None,
        actual_damage: int = 0,
        *,
        damage_type: str = "NORMAL",
    ) -> list[dict[str, Any]]:
        """Process hooks that react to player attacks dealing actual damage."""
        results: list[dict[str, Any]] = []
        for power in list(self.powers):
            if hasattr(power, "on_player_attack_damage"):
                result = power.on_player_attack_damage(
                    owner,
                    target,
                    actual_damage,
                    damage_type=damage_type,
                )
                if result:
                    results.append(result)
        return results

    def on_player_power_played(
        self,
        owner: Any | None = None,
        card: Any | None = None,
        *,
        active_powers: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Process hooks that react to the player successfully playing a power card."""
        results: list[dict[str, Any]] = []
        powers = active_powers if active_powers is not None else list(self.powers)
        for power in list(powers):
            if hasattr(power, "on_player_power_played"):
                result = power.on_player_power_played(owner, card)
                if result:
                    results.append(result)
        return results

    def on_player_apply_power_to_enemy(
        self,
        owner: Any | None = None,
        target: Any | None = None,
        power: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Process hooks that react to the player successfully applying a power to an enemy."""
        results: list[dict[str, Any]] = []
        for current_power in list(self.powers):
            if hasattr(current_power, "on_player_apply_power_to_enemy"):
                result = current_power.on_player_apply_power_to_enemy(owner, target, power)
                if result:
                    results.append(result)
        return results

    def on_scry(self, owner: Any | None = None) -> list[dict[str, Any]]:
        """Process scry hooks for all powers."""
        results: list[dict[str, Any]] = []
        for power in list(self.powers):
            if hasattr(power, "on_scry"):
                result = power.on_scry(owner)
                if result:
                    results.append(result)
        return results

    def on_change_stance(self, owner: Any | None, old_stance: Any, new_stance: Any) -> list[dict[str, Any]]:
        """Process stance-change hooks for all powers."""
        results: list[dict[str, Any]] = []
        for power in list(self.powers):
            if hasattr(power, "on_change_stance"):
                result = power.on_change_stance(owner, old_stance, new_stance)
                if result:
                    results.append(result)
        return results

    def at_end_of_turn_pre_end_turn_cards(self, owner: Any | None = None, is_player: bool = True) -> list[dict[str, Any]]:
        """Process end-of-turn hooks that must happen before hand discard."""
        results: list[dict[str, Any]] = []
        for power in list(self.powers):
            if hasattr(power, "at_end_of_turn_pre_end_turn_cards"):
                result = power.at_end_of_turn_pre_end_turn_cards(owner, is_player)
                if result:
                    results.append(result)
        return results

    def at_end_of_turn(self, owner: Any | None = None, is_player: bool = True) -> list[dict[str, Any]]:
        """Process end-of-turn hooks that happen after hand discard and before monster turn."""
        results: list[dict[str, Any]] = []
        for power in list(self.powers):
            if hasattr(power, "at_end_of_turn"):
                result = power.at_end_of_turn(owner, is_player)
                if result:
                    results.append(result)
        return results

    def on_victory(self, owner: Any | None = None) -> int:
        """Process victory hooks and return total healing granted."""
        total_heal = 0
        for power in list(self.powers):
            if hasattr(power, "on_victory"):
                result = power.on_victory(owner)
                if isinstance(result, int):
                    total_heal += result
                elif isinstance(result, dict):
                    total_heal += int(result.get("heal_amount", 0) or 0)
        return total_heal
    
    def on_attacked(self, actual_damage: int, monster: "MonsterBase" = None) -> int:
        """Handle Curl Up and Angry power triggers when attacked.

        Returns block to gain.
        """
        total_block = 0
        for power in list(self.powers):
            if not hasattr(power, "on_attacked"):
                continue
            if isinstance(power, CurlUpPower):
                result = power.on_attacked(actual_damage)
            elif isinstance(power, AngryPower):
                result = power.on_attacked(actual_damage, monster)
            else:
                result = power.on_attacked(actual_damage, monster)
            if isinstance(result, int):
                total_block += result
        return total_block
    
    def get_ritual_strength_gain(self) -> int:
        """Get total strength to gain from Ritual at end of turn."""
        total = 0
        for power in self.powers:
            if isinstance(power, RitualPower):
                total += power.get_strength_gain()
        return total
    
    def on_exhaust(self, card) -> tuple[int, int]:
        """Trigger exhaust powers. Returns (block_gain, draw_amount)."""
        block_gain = 0
        draw_amount = 0
        for power in self.powers:
            if power.id == "FeelNoPain":
                block_gain += power.amount
            elif power.id == "DarkEmbrace":
                draw_amount += power.amount
        return block_gain, draw_amount
        
    def get_metallicize_block(self) -> int:
        return sum(p.amount for p in self.powers if p.id == "Metallicize")
        
    def get_demon_form_strength(self) -> int:
        return sum(p.amount for p in self.powers if p.id == "DemonForm")
        
    def get_regen_heal(self) -> int:
        return sum(p.amount for p in self.powers if p.id == "Regen")

    def get_rage_block(self) -> int:
        return sum(p.amount for p in self.powers if p.id == "Rage")

    def clear_buffs(self) -> None:
        """Remove all buff powers."""
        self.powers = [p for p in self.powers if p.power_type != PowerType.BUFF]
    
    def clear_debuffs(self) -> None:
        """Remove all debuff powers."""
        self.powers = [p for p in self.powers if p.power_type != PowerType.DEBUFF]
    
    def clear_all(self) -> None:
        """Remove all powers."""
        self.powers.clear()
    
    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "powers": [p.to_dict() for p in self.powers],
            "changeLog": [log.to_dict() for log in self.change_log],
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> PowerContainer:
        """Deserialize from dict."""
        from sts_py.engine.combat.powers import power_from_dict
        container = cls()
        for power_data in data.get("powers", []):
            container.add_power(power_from_dict(power_data))
        return container
    
    def __len__(self) -> int:
        return len(self.powers)
    
    def __iter__(self):
        return iter(self.powers)
