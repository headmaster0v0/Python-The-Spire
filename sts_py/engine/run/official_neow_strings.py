from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


OFFICIAL_NEOW_STRINGS_PATH = Path(__file__).resolve().parents[2] / "data" / "official_neow_strings.json"


@dataclass(frozen=True)
class OfficialNeowEventStrings:
    names_en: tuple[str, ...]
    names_zhs: tuple[str, ...]
    text_en: tuple[str, ...]
    text_zhs: tuple[str, ...]
    options_en: tuple[str, ...]
    options_zhs: tuple[str, ...]


@dataclass(frozen=True)
class OfficialNeowRewardStrings:
    names_en: tuple[str, ...]
    names_zhs: tuple[str, ...]
    text_en: tuple[str, ...]
    text_zhs: tuple[str, ...]
    options_en: tuple[str, ...]
    options_zhs: tuple[str, ...]
    unique_rewards_en: tuple[str, ...]
    unique_rewards_zhs: tuple[str, ...]


@dataclass(frozen=True)
class OfficialNeowStrings:
    event: OfficialNeowEventStrings
    reward: OfficialNeowRewardStrings


def _tuple_field(record: dict[str, object], key: str) -> tuple[str, ...]:
    return tuple(str(item or "") for item in record.get(key, []) or [])


@lru_cache(maxsize=1)
def load_official_neow_strings() -> OfficialNeowStrings:
    payload = json.loads(OFFICIAL_NEOW_STRINGS_PATH.read_text(encoding="utf-8"))
    records = dict(payload.get("records", {}) or {})

    event_eng = dict(records.get("Neow Event", {}).get("eng", {}) or {})
    event_zhs = dict(records.get("Neow Event", {}).get("zhs", {}) or {})
    reward_eng = dict(records.get("Neow Reward", {}).get("eng", {}) or {})
    reward_zhs = dict(records.get("Neow Reward", {}).get("zhs", {}) or {})

    return OfficialNeowStrings(
        event=OfficialNeowEventStrings(
            names_en=_tuple_field(event_eng, "names"),
            names_zhs=_tuple_field(event_zhs, "names"),
            text_en=_tuple_field(event_eng, "text"),
            text_zhs=_tuple_field(event_zhs, "text"),
            options_en=_tuple_field(event_eng, "options"),
            options_zhs=_tuple_field(event_zhs, "options"),
        ),
        reward=OfficialNeowRewardStrings(
            names_en=_tuple_field(reward_eng, "names"),
            names_zhs=_tuple_field(reward_zhs, "names"),
            text_en=_tuple_field(reward_eng, "text"),
            text_zhs=_tuple_field(reward_zhs, "text"),
            options_en=_tuple_field(reward_eng, "options"),
            options_zhs=_tuple_field(reward_zhs, "options"),
            unique_rewards_en=_tuple_field(reward_eng, "unique_rewards"),
            unique_rewards_zhs=_tuple_field(reward_zhs, "unique_rewards"),
        ),
    )


def get_official_neow_event_strings() -> OfficialNeowEventStrings:
    return load_official_neow_strings().event


def get_official_neow_reward_strings() -> OfficialNeowRewardStrings:
    return load_official_neow_strings().reward


__all__ = [
    "OFFICIAL_NEOW_STRINGS_PATH",
    "OfficialNeowEventStrings",
    "OfficialNeowRewardStrings",
    "OfficialNeowStrings",
    "get_official_neow_event_strings",
    "get_official_neow_reward_strings",
    "load_official_neow_strings",
]
