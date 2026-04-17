from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class EventType(str, Enum):
    ACTION_ENQUEUED = "action_enqueued"
    ACTION_APPLIED = "action_applied"
    DECISION_REQUIRED = "decision_required"
    STATE_CHANGED = "state_changed"


@dataclass(frozen=True)
class EngineEvent:
    type: EventType
    payload: Mapping[str, Any]
