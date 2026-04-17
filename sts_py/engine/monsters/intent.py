from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class MonsterIntent(Enum):
    ATTACK = auto()
    ATTACK_BUFF = auto()
    ATTACK_DEBUFF = auto()
    ATTACK_DEFEND = auto()
    BUFF = auto()
    DEBUFF = auto()
    STRONG_DEBUFF = auto()
    DEBUG = auto()
    DEFEND = auto()
    DEFEND_DEBUFF = auto()
    DEFEND_BUFF = auto()
    ESCAPE = auto()
    MAGIC = auto()
    NONE = auto()
    SLEEP = auto()
    STUN = auto()
    UNKNOWN = auto()
    WEAK = auto()
    VULNERABLE = auto()

    def is_attack(self) -> bool:
        return self in (
            MonsterIntent.ATTACK,
            MonsterIntent.ATTACK_BUFF,
            MonsterIntent.ATTACK_DEBUFF,
            MonsterIntent.ATTACK_DEFEND,
        )

    def is_defend(self) -> bool:
        return self in (
            MonsterIntent.DEFEND,
            MonsterIntent.DEFEND_BUFF,
            MonsterIntent.DEFEND_DEBUFF,
            MonsterIntent.ATTACK_DEFEND,
        )

    def is_buff(self) -> bool:
        return self in (
            MonsterIntent.BUFF,
            MonsterIntent.ATTACK_BUFF,
            MonsterIntent.DEFEND_BUFF,
        )

    def is_debuff(self) -> bool:
        return self in (
            MonsterIntent.DEBUFF,
            MonsterIntent.STRONG_DEBUFF,
            MonsterIntent.ATTACK_DEBUFF,
            MonsterIntent.DEFEND_DEBUFF,
        )

    @staticmethod
    def from_java_name(name: str) -> "MonsterIntent":
        """Convert Java Intent enum name to Python MonsterIntent."""
        mapping = {
            "ATTACK": MonsterIntent.ATTACK,
            "ATTACK_BUFF": MonsterIntent.ATTACK_BUFF,
            "ATTACK_DEBUFF": MonsterIntent.ATTACK_DEBUFF,
            "ATTACK_DEFEND": MonsterIntent.ATTACK_DEFEND,
            "BUFF": MonsterIntent.BUFF,
            "DEBUFF": MonsterIntent.DEBUFF,
            "STRONG_DEBUFF": MonsterIntent.STRONG_DEBUFF,
            "DEBUG": MonsterIntent.DEBUG,
            "DEFEND": MonsterIntent.DEFEND,
            "DEFEND_DEBUFF": MonsterIntent.DEFEND_DEBUFF,
            "DEFEND_BUFF": MonsterIntent.DEFEND_BUFF,
            "ESCAPE": MonsterIntent.ESCAPE,
            "MAGIC": MonsterIntent.MAGIC,
            "NONE": MonsterIntent.NONE,
            "SLEEP": MonsterIntent.SLEEP,
            "STUN": MonsterIntent.STUN,
            "UNKNOWN": MonsterIntent.UNKNOWN,
        }
        return mapping.get(name, MonsterIntent.UNKNOWN)


@dataclass
class IntentRecord:
    """Record of a monster's intent at a point in time.
    
    Matches Java DataRecorder.IntentRecord for debugging and replay.
    """
    floor: int
    monster_id: str
    monster_name: str
    intent: MonsterIntent
    move_index: int
    base_damage: int
    ai_rng_counter: int
    multi_damage_count: int = 0
    timestamp: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "floor": self.floor,
            "monsterId": self.monster_id,
            "monsterName": self.monster_name,
            "intent": self.intent.name,
            "moveIndex": self.move_index,
            "baseDamage": self.base_damage,
            "aiRngCounter": self.ai_rng_counter,
            "multiDamageCount": self.multi_damage_count,
        }


@dataclass
class IntentTracker:
    """Tracks monster intents over time for debugging and replay.
    
    Based on Java MonsterIntentPatches from DataRecorder mod.
    """
    records: list[IntentRecord] = field(default_factory=list)
    
    def record_intent(
        self,
        floor: int,
        monster_id: str,
        monster_name: str,
        intent: MonsterIntent,
        move_index: int,
        base_damage: int,
        ai_rng_counter: int,
        multi_damage_count: int = 0,
    ) -> IntentRecord:
        """Record a monster's intent when it rolls a move."""
        import time
        record = IntentRecord(
            floor=floor,
            monster_id=monster_id,
            monster_name=monster_name,
            intent=intent,
            move_index=move_index,
            base_damage=base_damage,
            ai_rng_counter=ai_rng_counter,
            multi_damage_count=multi_damage_count,
            timestamp=time.time(),
        )
        self.records.append(record)
        return record
    
    def get_intents_for_floor(self, floor: int) -> list[IntentRecord]:
        """Get all intent records for a specific floor."""
        return [r for r in self.records if r.floor == floor]
    
    def get_intents_for_monster(self, monster_id: str) -> list[IntentRecord]:
        """Get all intent records for a specific monster."""
        return [r for r in self.records if r.monster_id == monster_id]
    
    def clear(self) -> None:
        """Clear all recorded intents."""
        self.records.clear()
    
    def to_dict(self) -> dict:
        return {
            "records": [r.to_dict() for r in self.records],
        }
