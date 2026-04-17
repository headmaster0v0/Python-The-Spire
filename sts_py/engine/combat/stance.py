"""Stance system for combat.

This module implements the stance system from Slay the Spire.
Stances modify how damage is dealt and received.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class StanceType(Enum):
    """Available stance types."""
    NEUTRAL = "Neutral"
    WRATH = "Wrath"
    CALM = "Calm"
    DIVINITY = "Divinity"


@dataclass
class Stance:
    """Represents a combat stance.

    Stances modify damage dealt and received. The most commonly used
    stances are Wrath (+50% damage dealt and received) and Calm
    (gain 2 energy when exiting).
    """
    stance_type: StanceType
    name: str
    description: str

    def at_damage_give(self, damage: float, damage_type: str = "NORMAL") -> float:
        """Modify outgoing damage.

        Args:
            damage: Base damage value
            damage_type: Type of damage (NORMAL, THORNS, etc.)

        Returns:
            Modified damage value
        """
        if damage_type == "NORMAL":
            if self.stance_type == StanceType.WRATH:
                return damage * 2.0
            elif self.stance_type == StanceType.DIVINITY:
                return damage * 3.0
        return damage

    def at_damage_receive(self, damage: float, damage_type: str = "NORMAL") -> float:
        """Modify incoming damage.

        Args:
            damage: Incoming damage value
            damage_type: Type of damage (NORMAL, THORNS, etc.)

        Returns:
            Modified damage value
        """
        if damage_type == "NORMAL":
            if self.stance_type == StanceType.WRATH:
                return damage * 2.0
        return damage

    def on_enter(self) -> None:
        """Called when entering this stance."""
        pass

    def on_exit(self) -> dict:
        """Called when exiting this stance.

        Returns:
            Dict of effects to apply when exiting (e.g., {'energy': 2} for Calm)
        """
        if self.stance_type == StanceType.CALM:
            return {"energy": 2}
        return {}


NEUTRAL_STANCE = Stance(
    stance_type=StanceType.NEUTRAL,
    name="Neutral",
    description="Default stance."
)

WRATH_STANCE = Stance(
    stance_type=StanceType.WRATH,
    name="Wrath",
    description="Deal and receive double damage."
)

CALM_STANCE = Stance(
    stance_type=StanceType.CALM,
    name="Calm",
    description="Gain 2 Energy when exiting this stance."
)

DIVINITY_STANCE = Stance(
    stance_type=StanceType.DIVINITY,
    name="Divinity",
    description="Deal triple damage."
)


def get_stance(stance_type: StanceType) -> Stance:
    """Get stance instance by type.

    Args:
        stance_type: Type of stance to get

    Returns:
        Stance instance
    """
    stances = {
        StanceType.NEUTRAL: NEUTRAL_STANCE,
        StanceType.WRATH: WRATH_STANCE,
        StanceType.CALM: CALM_STANCE,
        StanceType.DIVINITY: DIVINITY_STANCE,
    }
    return stances.get(stance_type, NEUTRAL_STANCE)


def change_stance(player: Any, stance_type: StanceType | None) -> dict[str, int]:
    """Change a player's stance and return any exit effects.

    This keeps the real `player.stance` field and the historical `_stance`
    string in sync so older combat/relic paths continue to function.
    """
    next_type = stance_type or StanceType.NEUTRAL
    current_stance = getattr(player, "stance", None) or NEUTRAL_STANCE

    if current_stance.stance_type == next_type:
        return {}

    exit_effects = current_stance.on_exit()
    next_stance = get_stance(next_type)
    player.stance = next_stance

    if next_type == StanceType.NEUTRAL:
        player._stance = None
    else:
        player._stance = next_type.value.lower()

    return exit_effects
