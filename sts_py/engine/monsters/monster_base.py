from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sts_py.engine.combat.power_container import PowerContainer
from sts_py.engine.monsters.intent import MonsterIntent

if TYPE_CHECKING:
    from sts_py.engine.combat.powers import Power
    from sts_py.engine.core.rng import MutableRNG


@dataclass
class MonsterMove:
    move_id: int
    intent: MonsterIntent
    base_damage: int = -1
    multiplier: int = 0
    is_multi_damage: bool = False
    name: str | None = None


@dataclass
class MonsterBase:
    id: str
    name: str
    hp: int
    max_hp: int
    block: int = 0
    strength: int = 0
    move_history: list[int] = field(default_factory=list)
    next_move: MonsterMove | None = None
    first_move: bool = True
    is_dying: bool = False
    powers: PowerContainer = field(default_factory=PowerContainer)
    ai_rng: "MutableRNG | None" = None

    def is_dead(self) -> bool:
        return self.hp <= 0 or self.is_dying

    def last_move(self, move_id: int) -> bool:
        if not self.move_history:
            return False
        return self.move_history[-1] == move_id

    def last_two_moves(self, move_id: int) -> bool:
        if len(self.move_history) < 2:
            return False
        return self.move_history[-1] == move_id and self.move_history[-2] == move_id

    def last_move_before(self, move_id: int) -> bool:
        if len(self.move_history) < 2:
            return False
        return self.move_history[-2] == move_id

    def set_move(self, move: MonsterMove) -> None:
        if move.move_id != -1:
            self.move_history.append(move.move_id)
        self.next_move = move

    def roll_move(self, ai_rng: "MutableRNG") -> None:
        self.ai_rng = ai_rng
        roll = ai_rng.random_int(99)
        self.get_move(roll)

    def get_move(self, roll: int) -> None:
        raise NotImplementedError("Subclasses must implement get_move")

    def take_damage(self, amount: int) -> int:
        actual_damage = amount
        if self.block > 0:
            absorbed = min(self.block, amount)
            self.block -= absorbed
            actual_damage -= absorbed
        if actual_damage > 0:
            # Trigger on_damage_taken for monsters like Lagavulin (wake from sleep)
            if hasattr(self, 'on_damage_taken'):
                self.on_damage_taken(actual_damage)
            self.hp = max(0, self.hp - actual_damage)
            # Trigger on_attacked for powers like Curl Up and Angry
            for p in list(self.powers.powers):
                if hasattr(p, 'on_attacked'):
                    block_gain = p.on_attacked(actual_damage, self)
                    if isinstance(block_gain, int) and block_gain > 0:
                        self.gain_block(block_gain)
            if self.hp <= 0:
                self.is_dying = True
        return actual_damage

    def gain_block(self, amount: int) -> None:
        self.block += amount

    def gain_strength(self, amount: int) -> None:
        self.strength += amount
    
    def add_power(self, power: Power) -> None:
        self.powers.add_power(power)
    
    def remove_power(self, power_id: str) -> Power | None:
        return self.powers.remove_power(power_id)
    
    def has_power(self, power_id: str) -> bool:
        return self.powers.has_power(power_id)
    
    def get_power_amount(self, power_id: str) -> int:
        return self.powers.get_power_amount(power_id)
    
    def get_effective_strength(self) -> int:
        return self.strength + self.powers.get_strength()

    def get_intent_damage(self) -> int:
        if self.next_move is None or self.next_move.base_damage < 0:
            return 0
        base_damage = self.next_move.base_damage
        effective_strength = self.get_effective_strength()
        damage = base_damage + effective_strength
        if self.powers.is_weak():
            damage = int(damage * 0.75)
        if self.has_power("BackAttack"):
            damage = int(damage * 1.5)
        return max(0, damage)

    def take_turn(self, player) -> None:
        """Execute this monster's current move against the player.

        Subclasses should override this to implement move-specific logic
        (block, buff, debuff, multi-hit, etc.). The default implementation
        handles basic attack intent only.
        """
        if self.next_move is None:
            return
        move = self.next_move
        intent = move.intent
        if intent.is_attack():
            damage = self.get_intent_damage()
            player.take_damage(damage)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "block": self.block,
            "strength": self.strength,
            "move_history": self.move_history.copy(),
            "next_move": self.next_move.move_id if self.next_move else None,
            "is_dying": self.is_dying,
            "powers": self.powers.to_dict(),
        }
