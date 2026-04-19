from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
from typing import Any


def asdict(obj: Any) -> Any:
    """Convert objects into JSON-serializable primitives.

    We keep this intentionally small and predictable to preserve determinism.
    """

    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        return asdict(to_dict())

    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)

    if isinstance(obj, dict):
        return {k: asdict(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [asdict(v) for v in obj]

    if isinstance(obj, enum.Enum):
        return obj.name

    # primitives
    if obj is None or isinstance(obj, (str, int, bool, float)):
        return obj

    # If we ever hit this, we should make the state representation explicit.
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def to_canonical_json(obj: Any) -> str:
    """Canonical JSON for deterministic hashing.

    - sort keys
    - no whitespace
    - avoid NaN/Infinity (json disallows if allow_nan=False)
    """

    return json.dumps(
        asdict(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def state_hash(obj: Any) -> str:
    """Compute a SHA-256 hash of canonical JSON."""

    data = to_canonical_json(obj).encode("utf-8")
    return hashlib.sha256(data).hexdigest()
