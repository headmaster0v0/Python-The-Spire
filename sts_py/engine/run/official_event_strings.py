from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts_py.engine.run.events import Event


OFFICIAL_EVENT_STRINGS_PATH = Path(__file__).resolve().parents[2] / "data" / "official_event_strings.json"


@dataclass(frozen=True)
class OfficialEventStrings:
    event_key: str
    official_key: str
    event_id: str
    name_en: str
    name_zhs: str
    descriptions_en: tuple[str, ...]
    descriptions_zhs: tuple[str, ...]
    options_en: tuple[str, ...]
    options_zhs: tuple[str, ...]

    @classmethod
    def from_dict(cls, event_key: str, data: dict[str, object]) -> "OfficialEventStrings":
        return cls(
            event_key=event_key,
            official_key=str(data.get("official_key", event_key) or event_key),
            event_id=str(data.get("event_id", event_key) or event_key),
            name_en=str(data.get("eng", {}).get("name", "") or ""),
            name_zhs=str(data.get("zhs", {}).get("name", "") or ""),
            descriptions_en=tuple(str(item or "") for item in data.get("eng", {}).get("descriptions", []) or []),
            descriptions_zhs=tuple(str(item or "") for item in data.get("zhs", {}).get("descriptions", []) or []),
            options_en=tuple(str(item or "") for item in data.get("eng", {}).get("options", []) or []),
            options_zhs=tuple(str(item or "") for item in data.get("zhs", {}).get("options", []) or []),
        )


@lru_cache(maxsize=1)
def load_official_event_strings() -> dict[str, OfficialEventStrings]:
    payload = json.loads(OFFICIAL_EVENT_STRINGS_PATH.read_text(encoding="utf-8"))
    records = payload.get("records", {})
    return {
        str(event_key): OfficialEventStrings.from_dict(str(event_key), dict(record))
        for event_key, record in records.items()
    }


def _resolve_runtime_event_key(identifier: str) -> str | None:
    if not identifier:
        return None

    canonical = str(identifier)
    records = load_official_event_strings()
    if canonical in records:
        return canonical

    if canonical == "Spire Heart":
        return "SpireHeart"

    try:
        from sts_py.engine.run.events import EVENT_KEY_ALIASES, EVENT_KEY_BY_ID
    except Exception:
        return None

    if canonical in EVENT_KEY_ALIASES:
        return EVENT_KEY_ALIASES[canonical]
    if canonical in EVENT_KEY_BY_ID:
        return EVENT_KEY_BY_ID[canonical]
    return None


def get_official_event_strings(identifier: str | None) -> OfficialEventStrings | None:
    if identifier is None:
        return None
    event_key = _resolve_runtime_event_key(str(identifier))
    if event_key is None:
        return None
    return load_official_event_strings().get(event_key)


def apply_official_event_strings(event: "Event") -> None:
    event_key = str(getattr(event, "event_key", "") or getattr(event, "id", "") or "")
    entry = get_official_event_strings(event_key)
    if entry is None:
        return

    event.name = entry.name_en or event.name
    event.name_cn = entry.name_zhs or event.name_cn
    event.source_descriptions = list(entry.descriptions_en)
    event.source_descriptions_cn = list(entry.descriptions_zhs)
    event.source_options = list(entry.options_en)
    event.source_options_cn = list(entry.options_zhs)
    if entry.descriptions_en:
        event.description = entry.descriptions_en[0]
    if entry.descriptions_zhs:
        event.description_cn = entry.descriptions_zhs[0]


__all__ = [
    "OfficialEventStrings",
    "OFFICIAL_EVENT_STRINGS_PATH",
    "apply_official_event_strings",
    "get_official_event_strings",
    "load_official_event_strings",
]
