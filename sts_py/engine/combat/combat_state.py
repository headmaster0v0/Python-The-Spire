from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from sts_py.engine.combat.power_container import PowerContainer
from sts_py.engine.combat.card_piles import CardManager
from sts_py.engine.monsters.monster_base import MonsterBase

if TYPE_CHECKING:
    from sts_py.engine.combat.powers import Power
    from sts_py.engine.combat.stance import Stance


class CombatPhase(Enum):
    INIT = auto()
    PLAYER_TURN = auto()
    MONSTER_TURN = auto()
    END_COMBAT = auto()


def _create_default_orb_slots():
    from sts_py.engine.combat.orbs import OrbSlots

    return OrbSlots()


@dataclass
class Entity:
    id: str
    hp: int
    max_hp: int
    block: int = 0
    powers: PowerContainer = field(default_factory=PowerContainer)

    def is_dead(self) -> bool:
        return self.hp <= 0

    def take_damage(self, amount: int) -> int:
        actual_damage = amount
        if self.block > 0:
            absorbed = min(self.block, amount)
            self.block -= absorbed
            actual_damage -= absorbed
        if actual_damage > 0:
            self.hp = max(0, self.hp - actual_damage)
        return actual_damage

    def gain_block(self, amount: int) -> None:
        actual_gain = max(0, amount)
        if actual_gain <= 0:
            return
        self.block += actual_gain
        if hasattr(self, "powers"):
            self.powers.on_gain_block(self, actual_gain)

    def add_power(self, power: Power) -> None:
        self.powers.add_power(power)

    def remove_power(self, power_id: str) -> Power | None:
        return self.powers.remove_power(power_id)

    def has_power(self, power_id: str) -> bool:
        return self.powers.has_power(power_id)

    def get_power_amount(self, power_id: str) -> int:
        return self.powers.get_power_amount(power_id)


@dataclass
class Player:
    hp: int
    max_hp: int
    id: str = "player"
    block: int = 0
    strength: int = 0
    dexterity: int = 0
    focus: int = 0
    thorns: int = 0
    orbs: Any = field(default_factory=_create_default_orb_slots)
    max_orbs: int = 3
    energy: int = 3
    max_energy: int = 3
    powers: PowerContainer = field(default_factory=PowerContainer)
    barricade_active: bool = False
    blur_active: bool = False
    stance: Stance | None = None
    pending_tea_energy: int = 0

    def _consume_buffer_charge(self) -> bool:
        power = self.powers.get_power("Buffer")
        if power is None:
            return False
        self.powers.reduce_power("Buffer", 1)
        return True

    def _apply_intangible_cap(self, amount: int) -> int:
        adjusted_amount = max(0, int(amount))
        if adjusted_amount > 1 and self.powers.has_power("Intangible"):
            return 1
        return adjusted_amount

    def take_damage(
        self,
        amount: int,
        *,
        damage_type: str = "NORMAL",
        source_owner: Any | None = None,
    ) -> int:
        actual_damage = max(0, int(amount))
        if self.block > 0:
            absorbed = min(self.block, actual_damage)
            self.block -= absorbed
            actual_damage -= absorbed
        torii_max_damage = int(getattr(self, "_torii_max_damage", 0) or 0)
        if getattr(self, "_torii_active", False) and 1 < actual_damage <= torii_max_damage:
            actual_damage = 1
        actual_damage = self._apply_intangible_cap(actual_damage)
        if actual_damage > 0 and self._consume_buffer_charge():
            return 0
        if actual_damage > 0:
            self.hp = max(0, self.hp - actual_damage)
            if source_owner is not None and hasattr(source_owner, "powers"):
                source_owner.powers.on_inflict_damage(
                    source_owner,
                    actual_damage,
                    self,
                    damage_type=damage_type,
                )
            self.powers.on_player_attacked(
                self,
                actual_damage,
                damage_type=damage_type,
                source_owner=source_owner,
            )
            combat_state = getattr(self, "_combat_state", None)
            card_manager = getattr(combat_state, "card_manager", None)
            if card_manager is not None and hasattr(card_manager, "on_player_hp_loss"):
                card_manager.on_player_hp_loss(actual_damage)
        return actual_damage

    def lose_hp(self, amount: int, *, source_owner: Any | None = None) -> int:
        """Lose HP directly, ignoring block, and trigger HP-loss reactions."""
        actual_hp_loss = max(0, min(self.hp, int(amount)))
        if actual_hp_loss <= 0:
            return 0
        actual_hp_loss = self._apply_intangible_cap(actual_hp_loss)
        if self._consume_buffer_charge():
            return 0
        self.hp = max(0, self.hp - actual_hp_loss)
        self.powers.on_hp_lost(self, actual_hp_loss, source_owner=source_owner)
        combat_state = getattr(self, "_combat_state", None)
        card_manager = getattr(combat_state, "card_manager", None)
        if card_manager is not None and hasattr(card_manager, "on_player_hp_loss"):
            card_manager.on_player_hp_loss(actual_hp_loss)
        return actual_hp_loss

    def heal(self, amount: int) -> int:
        heal_amount = max(0, int(amount))
        if heal_amount <= 0 or getattr(self, "_cant_heal", False):
            return 0

        combat_state = getattr(self, "_combat_state", None)
        engine = getattr(combat_state, "engine", None)
        if engine is not None and hasattr(engine, "_apply_heal_amplification"):
            heal_amount = engine._apply_heal_amplification(heal_amount)

        actual_heal = min(max(0, self.max_hp - self.hp), heal_amount)
        if actual_heal <= 0:
            return 0
        self.hp += actual_heal
        return actual_heal

    def gain_block(self, amount: int) -> None:
        actual_gain = max(0, amount)
        if actual_gain <= 0:
            return
        self.block += actual_gain
        self.powers.on_gain_block(self, actual_gain)

    def is_dead(self) -> bool:
        return self.hp <= 0

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

    def get_effective_dexterity(self) -> int:
        return self.dexterity + self.powers.get_dexterity()

    def to_dict(self) -> dict:
        return {
            "hp": self.hp,
            "max_hp": self.max_hp,
            "block": self.block,
            "strength": self.strength,
            "dexterity": self.dexterity,
            "focus": self.focus,
            "energy": self.energy,
            "max_energy": self.max_energy,
            "powers": self.powers.to_dict(),
        }


@dataclass
class CombatState:
    player: Player | Entity
    monsters: list[MonsterBase] = field(default_factory=list)
    monster: Entity | None = None
    turn: int = 1
    phase: CombatPhase = CombatPhase.INIT
    card_manager: CardManager | None = None
    card_random_rng: Any | None = None
    cards_played_this_turn: list[str] = field(default_factory=list)
    turn_has_ended: bool = False
    pending_combat_choice: dict[str, Any] | None = None
    pending_bonus_gold: int = 0

    def all_monsters_dead(self) -> bool:
        if self.monster is not None:
            return self.monster.is_dead()
        return all(m.is_dead() for m in self.monsters)

    def get_alive_monsters(self) -> list[MonsterBase]:
        return [m for m in self.monsters if not m.is_dead()]

    def add_monster(self, monster: MonsterBase) -> None:
        self.monsters.append(monster)
        monster.state = self

    def to_dict(self) -> dict:
        player_dict = self.player.to_dict() if hasattr(self.player, 'to_dict') else {"hp": self.player.hp, "max_hp": self.player.max_hp, "block": self.player.block}
        return {
            "player": player_dict,
            "monsters": [m.to_dict() for m in self.monsters],
            "turn": self.turn,
            "phase": self.phase.name,
            "card_manager": self.card_manager.to_dict() if self.card_manager else None,
            "cards_played_this_turn": self.cards_played_this_turn,
        }
