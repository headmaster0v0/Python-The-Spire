from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sts_py.engine.core.actions import ActionQueue
from sts_py.engine.core.decisions import Decision, DecisionSpec
from sts_py.engine.core.events import EngineEvent


@dataclass
class Replay:
    engine_version: str
    content_hash: str
    game_version: str
    seed: str
    decisions: list[Decision]

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_version": self.engine_version,
            "content_hash": self.content_hash,
            "game_version": self.game_version,
            "seed": self.seed,
            "decisions": [
                {"spec_id": d.spec_id, "params": dict(d.params)} for d in self.decisions
            ],
        }


@dataclass
class StepResult:
    events: list[EngineEvent]
    decision_specs: list[DecisionSpec]
    state_hash: str


@dataclass
class EngineState:
    version: str
    data: dict[str, Any]
    action_queue: ActionQueue

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "data": self.data,
            "action_queue": [a.to_dict() for a in self.action_queue.pending],
        }
