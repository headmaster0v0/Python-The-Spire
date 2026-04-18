from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


PLAYER_PROFILE_PATH = Path.home() / ".sts_py_player_profile.json"
LEGACY_NOTE_FOR_YOURSELF_PATH = Path.home() / ".sts_py_note_for_yourself.json"


@dataclass
class NoteForYourselfProfile:
    card_id: str = "IronWave"
    upgrades: int = 0

    @classmethod
    def from_raw(cls, raw: Any) -> "NoteForYourselfProfile":
        payload = raw if isinstance(raw, dict) else {}
        card_id = str(payload.get("card_id", "IronWave") or "IronWave")
        upgrades = max(0, int(payload.get("upgrades", 0) or 0))
        return cls(card_id=card_id, upgrades=upgrades)


@dataclass
class CharacterProgress:
    spirits: int = 0
    highest_unlocked_ascension: int = 1
    last_ascension_level: int = 1

    @classmethod
    def from_raw(cls, raw: Any) -> "CharacterProgress":
        payload = raw if isinstance(raw, dict) else {}
        highest = max(1, int(payload.get("highest_unlocked_ascension", 1) or 1))
        last = max(1, int(payload.get("last_ascension_level", highest) or highest))
        spirits = max(0, int(payload.get("spirits", 0) or 0))
        return cls(spirits=spirits, highest_unlocked_ascension=highest, last_ascension_level=last)


@dataclass
class PlayerProfile:
    schema_version: int = 1
    neow_intro_seen: bool = False
    note_for_yourself: NoteForYourselfProfile = field(default_factory=NoteForYourselfProfile)
    characters: dict[str, CharacterProgress] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: Any) -> "PlayerProfile":
        payload = raw if isinstance(raw, dict) else {}
        characters = {
            str(character_class).upper(): CharacterProgress.from_raw(progress)
            for character_class, progress in dict(payload.get("characters", {}) or {}).items()
        }
        return cls(
            schema_version=max(1, int(payload.get("schema_version", 1) or 1)),
            neow_intro_seen=bool(payload.get("neow_intro_seen", False)),
            note_for_yourself=NoteForYourselfProfile.from_raw(payload.get("note_for_yourself", {})),
            characters=characters,
        )

    def character_progress(self, character_class: str) -> CharacterProgress:
        key = str(character_class or "IRONCLAD").upper()
        progress = self.characters.get(key)
        if progress is None:
            progress = CharacterProgress()
            self.characters[key] = progress
        return progress

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "neow_intro_seen": self.neow_intro_seen,
            "note_for_yourself": asdict(self.note_for_yourself),
            "characters": {
                key: asdict(progress)
                for key, progress in sorted(self.characters.items())
            },
        }


def load_player_profile(
    *,
    path: Path | None = None,
    legacy_note_path: Path | None = None,
) -> PlayerProfile:
    profile_path = path or PLAYER_PROFILE_PATH
    note_path = legacy_note_path or LEGACY_NOTE_FOR_YOURSELF_PATH
    profile: PlayerProfile | None = None
    if profile_path.exists():
        try:
            profile = PlayerProfile.from_raw(json.loads(profile_path.read_text(encoding="utf-8")))
        except Exception:
            profile = None

    if profile is None:
        profile = PlayerProfile()

    if note_path.exists():
        try:
            profile.note_for_yourself = NoteForYourselfProfile.from_raw(
                json.loads(note_path.read_text(encoding="utf-8"))
            )
        except Exception:
            pass
    return profile


def save_player_profile(
    profile: PlayerProfile,
    *,
    path: Path | None = None,
) -> None:
    profile_path = path or PLAYER_PROFILE_PATH
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        json.dumps(profile.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "CharacterProgress",
    "LEGACY_NOTE_FOR_YOURSELF_PATH",
    "NoteForYourselfProfile",
    "PLAYER_PROFILE_PATH",
    "PlayerProfile",
    "load_player_profile",
    "save_player_profile",
]
