from __future__ import annotations

from sts_py.engine.core.canon import asdict, state_hash
from sts_py.engine.core.decisions import Decision, DecisionSpec
from sts_py.engine.core.events import EngineEvent, EventType
from sts_py.engine.run.types import EngineState, StepResult


class Engine:
    def __init__(self, state: EngineState):
        self.state = state
        self.events: list[EngineEvent] = []

    def _emit(self, typ: EventType, payload: dict[str, object]) -> None:
        self.events.append(EngineEvent(type=typ, payload=payload))

    def compute_hash(self) -> str:
        return state_hash(asdict(self.state.to_dict()))

    def resolve_actions(self) -> None:
        # Minimal resolver: apply everything until empty.
        while len(self.state.action_queue) > 0:
            action = self.state.action_queue.pop_left()
            self._emit(EventType.ACTION_APPLIED, {"action": action.to_dict()})
            action.apply(self.state)
            self._emit(EventType.STATE_CHANGED, {})

    def list_decisions(self) -> list[DecisionSpec]:
        # Placeholder: no interactive choices yet.
        return []

    def apply_decision(self, decision: Decision) -> StepResult:
        # Placeholder: will validate and enqueue actions.
        self._emit(
            EventType.DECISION_REQUIRED,
            {"decision": {"spec_id": decision.spec_id, "params": decision.params}},
        )
        self.resolve_actions()
        return StepResult(
            events=self.events,
            decision_specs=self.list_decisions(),
            state_hash=self.compute_hash(),
        )

    def step_until_blocked(self) -> StepResult:
        self.events = []
        self.resolve_actions()
        specs = self.list_decisions()
        if specs:
            self._emit(EventType.DECISION_REQUIRED, {"count": len(specs)})
        return StepResult(events=self.events, decision_specs=specs, state_hash=self.compute_hash())
