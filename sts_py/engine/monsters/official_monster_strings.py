from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


OFFICIAL_MONSTER_STRINGS_PATH = Path(__file__).resolve().parents[2] / "data" / "official_monster_strings.json"
OFFICIAL_MONSTER_TRANSLATION_SOURCE = "desktop-1.0.jar:localization/zhs/monsters.json"
OFFICIAL_MONSTER_DESCRIPTION_SOURCE = "desktop-1.0.jar:localization/eng/monsters.json + localization/zhs/monsters.json"


OFFICIAL_MONSTER_JAVA_CLASS_OVERRIDES: dict[str, str] = {
    "BanditChild": "BanditPointy",
    "Dagger": "SnakeDagger",
    "Serpent": "SpireGrowth",
    "SlaverBoss": "Taskmaster",
}


def _normalize_lookup_token(text: str | None) -> str:
    return re.sub(r"[^0-9a-z]+", "", str(text or "").lower())


def _humanize_identifier(identifier: str) -> str:
    if not identifier:
        return ""
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", identifier.replace("_", " "))
    return re.sub(r"\s+", " ", spaced).strip()


@dataclass(frozen=True)
class OfficialMonsterStrings:
    official_key: str
    java_class: str
    name_en: str
    name_zhs: str
    moves_en: tuple[str, ...]
    moves_zhs: tuple[str, ...]
    dialog_en: tuple[str, ...]
    dialog_zhs: tuple[str, ...]
    translation_source: str = OFFICIAL_MONSTER_TRANSLATION_SOURCE
    description_source: str = OFFICIAL_MONSTER_DESCRIPTION_SOURCE

    @classmethod
    def from_dict(cls, official_key: str, data: dict[str, object]) -> "OfficialMonsterStrings":
        return cls(
            official_key=str(data.get("official_key", official_key) or official_key),
            java_class=str(data.get("java_class", official_key) or official_key),
            name_en=str(data.get("name_en", "") or ""),
            name_zhs=str(data.get("name_zhs", "") or ""),
            moves_en=tuple(str(item or "") for item in data.get("moves_en", []) or []),
            moves_zhs=tuple(str(item or "") for item in data.get("moves_zhs", []) or []),
            dialog_en=tuple(str(item or "") for item in data.get("dialog_en", []) or []),
            dialog_zhs=tuple(str(item or "") for item in data.get("dialog_zhs", []) or []),
            translation_source=str(data.get("translation_source", OFFICIAL_MONSTER_TRANSLATION_SOURCE) or OFFICIAL_MONSTER_TRANSLATION_SOURCE),
            description_source=str(data.get("description_source", OFFICIAL_MONSTER_DESCRIPTION_SOURCE) or OFFICIAL_MONSTER_DESCRIPTION_SOURCE),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "official_key": self.official_key,
            "java_class": self.java_class,
            "name_en": self.name_en,
            "name_zhs": self.name_zhs,
            "moves_en": list(self.moves_en),
            "moves_zhs": list(self.moves_zhs),
            "dialog_en": list(self.dialog_en),
            "dialog_zhs": list(self.dialog_zhs),
            "translation_source": self.translation_source,
            "description_source": self.description_source,
        }


def _monster_java_class_inventory(repo_root: Path) -> dict[str, str]:
    monsters_root = repo_root / "decompiled_src" / "com" / "megacrit" / "cardcrawl" / "monsters"
    inventory: dict[str, str] = {}
    if not monsters_root.exists():
        return inventory
    for java_file in monsters_root.rglob("*.java"):
        inventory[_normalize_lookup_token(java_file.stem)] = java_file.stem
    return inventory


def _resolve_java_class(official_key: str, *, repo_root: Path) -> str:
    override = OFFICIAL_MONSTER_JAVA_CLASS_OVERRIDES.get(official_key)
    if override:
        return override

    inventory = _monster_java_class_inventory(repo_root)
    for candidate in (official_key, _humanize_identifier(official_key)):
        java_class = inventory.get(_normalize_lookup_token(candidate))
        if java_class:
            return java_class
    return str(official_key)


def build_official_monster_strings_snapshot(
    jar_path: Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, object]:
    resolved_repo_root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[3]

    with zipfile.ZipFile(jar_path) as jar:
        eng_monsters = json.loads(jar.read("localization/eng/monsters.json").decode("utf-8"))
        zhs_monsters = json.loads(jar.read("localization/zhs/monsters.json").decode("utf-8-sig"))

    all_keys = sorted(set(eng_monsters) | set(zhs_monsters))
    records: dict[str, object] = {}
    for official_key in all_keys:
        eng_record = dict(eng_monsters.get(official_key, {}) or {})
        zhs_record = dict(zhs_monsters.get(official_key, {}) or {})
        records[official_key] = OfficialMonsterStrings(
            official_key=official_key,
            java_class=_resolve_java_class(official_key, repo_root=resolved_repo_root),
            name_en=str(eng_record.get("NAME", "") or ""),
            name_zhs=str(zhs_record.get("NAME", "") or ""),
            moves_en=tuple(str(item or "") for item in eng_record.get("MOVES", []) or []),
            moves_zhs=tuple(str(item or "") for item in zhs_record.get("MOVES", []) or []),
            dialog_en=tuple(str(item or "") for item in eng_record.get("DIALOG", []) or []),
            dialog_zhs=tuple(str(item or "") for item in zhs_record.get("DIALOG", []) or []),
        ).to_dict()

    return {
        "schema_version": 1,
        "jar_path": str(jar_path),
        "records": records,
    }


@lru_cache(maxsize=1)
def load_official_monster_strings() -> dict[str, OfficialMonsterStrings]:
    payload = json.loads(OFFICIAL_MONSTER_STRINGS_PATH.read_text(encoding="utf-8"))
    return {
        str(official_key): OfficialMonsterStrings.from_dict(str(official_key), dict(record))
        for official_key, record in dict(payload.get("records", {}) or {}).items()
    }


def get_official_monster_strings(official_key: str | None) -> OfficialMonsterStrings | None:
    if official_key is None:
        return None
    return load_official_monster_strings().get(str(official_key))


__all__ = [
    "OFFICIAL_MONSTER_DESCRIPTION_SOURCE",
    "OFFICIAL_MONSTER_JAVA_CLASS_OVERRIDES",
    "OFFICIAL_MONSTER_STRINGS_PATH",
    "OFFICIAL_MONSTER_TRANSLATION_SOURCE",
    "OfficialMonsterStrings",
    "build_official_monster_strings_snapshot",
    "get_official_monster_strings",
    "load_official_monster_strings",
]
