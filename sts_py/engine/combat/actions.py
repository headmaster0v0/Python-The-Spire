from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sts_py.engine.core.actions import Action
from sts_py.engine.combat.combat_state import CombatState, Player, Entity
from sts_py.engine.monsters.monster_base import MonsterBase

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class GainBlock(Action):
    target: str
    amount: int

    def apply(self, state: any) -> None:
        cs: CombatState = state.data["combat"]
        if self.target == "player":
            cs.player.gain_block(self.amount)
        elif hasattr(cs, 'monsters') and cs.monsters:
            idx = int(self.target.split("_")[1])
            cs.monsters[idx].gain_block(self.amount)

    def to_dict(self) -> dict[str, any]:
        return {"type": "gain_block", "target": self.target, "amount": self.amount}


@dataclass(frozen=True)
class DealDamage(Action):
    source: str
    target: str
    amount: int

    def apply(self, state: any) -> None:
        cs: CombatState = state.data["combat"]
        if self.target == "player":
            cs.player.take_damage(self.amount)
        elif hasattr(cs, 'monsters') and cs.monsters:
            idx = int(self.target.split("_")[1])
            cs.monsters[idx].take_damage(self.amount)

    def to_dict(self) -> dict[str, any]:
        return {
            "type": "deal_damage",
            "source": self.source,
            "target": self.target,
            "amount": self.amount,
        }


@dataclass(frozen=True)
class GainStrength(Action):
    target: str
    amount: int

    def apply(self, state: any) -> None:
        cs: CombatState = state.data["combat"]
        if self.target == "player":
            if hasattr(cs.player, 'strength'):
                cs.player.strength += self.amount
        elif hasattr(cs, 'monsters') and cs.monsters:
            idx = int(self.target.split("_")[1])
            cs.monsters[idx].gain_strength(self.amount)

    def to_dict(self) -> dict[str, any]:
        return {"type": "gain_strength", "target": self.target, "amount": self.amount}


@dataclass(frozen=True)
class EndTurn(Action):
    def apply(self, state: any) -> None:
        cs: CombatState = state.data["combat"]
        cs.turn += 1

    def to_dict(self) -> dict[str, any]:
        return {"type": "end_turn"}


EndPlayerTurn = EndTurn


@dataclass(frozen=True)
class EndMonsterTurn(Action):
    def apply(self, state: any) -> None:
        cs: CombatState = state.data["combat"]
        if hasattr(cs, 'monsters'):
            for m in cs.monsters:
                m.block = 0
        cs.turn += 1

    def to_dict(self) -> dict[str, any]:
        return {"type": "end_monster_turn"}


@dataclass(frozen=True)
class MonsterExecuteMove(Action):
    monster_idx: int

    def apply(self, state: any) -> None:
        cs: CombatState = state.data["combat"]
        if not hasattr(cs, 'monsters') or not cs.monsters:
            return
        monster = cs.monsters[self.monster_idx]
        if monster.next_move is None:
            return

        move = monster.next_move
        intent = move.intent

        if intent.is_attack():
            damage = monster.get_intent_damage()
            cs.player.take_damage(damage)

        if intent.is_defend():
            if monster.id == "JawWorm":
                monster.gain_block(5 if move.move_id == 3 else 6)
            else:
                monster.gain_block(5)

        if intent.is_buff():
            if monster.id == "JawWorm" and move.move_id == 2:
                monster.gain_strength(monster.bellow_str)
            elif monster.id == "FuzzyLouseNormal" and move.move_id == 4:
                monster.gain_strength(3)
            elif monster.id == "Cultist" and move.move_id == 3:
                monster.gain_strength(monster.ritual_amount)

        if intent.is_debuff():
            pass

    def to_dict(self) -> dict[str, any]:
        return {"type": "monster_execute_move", "monster_idx": self.monster_idx}
