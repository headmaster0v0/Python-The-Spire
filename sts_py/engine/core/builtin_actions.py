from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..core.actions import Action


@dataclass(frozen=True)
class SetValue(Action):
    path: str
    value: Any

    def apply(self, state: Any) -> None:
        # Very small helper for early scaffolding.
        # path supports dot-separated keys in state.data
        cur = state.data
        parts = self.path.split(".") if self.path else []
        for p in parts[:-1]:
            if p not in cur or not isinstance(cur[p], dict):
                cur[p] = {}
            cur = cur[p]
        if not parts:
            raise ValueError("path must not be empty")
        cur[parts[-1]] = self.value

    def to_dict(self) -> dict[str, Any]:
        return {"type": "set_value", "path": self.path, "value": self.value}
