from __future__ import annotations

from dataclasses import dataclass
from typing import Any
try:
    from typing import Protocol
except ImportError:
    class Protocol(object):
        pass


class Action(Protocol):
    """Atomic state transition.

    Actions are the only way to mutate state. This makes ordering explicit and
    deterministic.
    """

    def apply(self, state: Any) -> None: ...

    def to_dict(self) -> dict[str, Any]: ...


@dataclass
class ActionQueue:
    pending: list[Action]

    def push(self, action: Action) -> None:
        self.pending.append(action)

    def extend(self, actions: list[Action]) -> None:
        self.pending.extend(actions)

    def pop_left(self) -> Action:
        if not self.pending:
            raise IndexError("ActionQueue is empty")
        return self.pending.pop(0)

    def __len__(self) -> int:
        return len(self.pending)
