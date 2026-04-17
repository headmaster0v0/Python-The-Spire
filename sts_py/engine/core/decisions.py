from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence


class DecisionType(str, Enum):
    # Run-level
    CHOOSE_PATH = "choose_path"
    # Combat-level
    PLAY_CARD = "play_card"
    END_TURN = "end_turn"
    # Screens
    CHOOSE_REWARD = "choose_reward"
    SHOP_BUY = "shop_buy"
    EVENT_CHOICE = "event_choice"


@dataclass(frozen=True)
class DecisionSpec:
    """A legal decision offered by the engine at the current state."""

    id: str
    type: DecisionType
    # UI-friendly payload (targets, costs, options, etc.). Must be JSON-serializable.
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class Decision:
    spec_id: str
    # Concrete parameters, if any. Must be JSON-serializable.
    params: Mapping[str, Any]


def index_specs(specs: Sequence[DecisionSpec]) -> dict[str, DecisionSpec]:
    return {s.id: s for s in specs}
