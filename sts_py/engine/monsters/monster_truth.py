from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sts_py.engine.monsters.official_monster_strings import (
    OFFICIAL_MONSTER_JAVA_CLASS_OVERRIDES,
    get_official_monster_strings,
    load_official_monster_strings,
)


MONSTER_TRUTH_MATRIX_PATH = Path(__file__).resolve().parents[2] / "data" / "monster_truth_matrix.json"


CANONICAL_OFFICIAL_KEY_OVERRIDES: dict[str, str] = {
    "AcidSlimeLarge": "AcidSlime_L",
    "AcidSlimeMedium": "AcidSlime_M",
    "AcidSlimeSmall": "AcidSlime_S",
    "Automaton": "BronzeAutomaton",
    "BanditPointy": "BanditChild",
    "Collector": "TheCollector",
    "LouseDefensive": "FuzzyLouseDefensive",
    "GremlinSneaky": "GremlinThief",
    "GremlinWar": "GremlinWarrior",
    "OrbWalker": "Orb Walker",
    "ShellParasite": "Shelled Parasite",
    "SnakeDagger": "Dagger",
    "SpireGrowth": "Serpent",
    "SpikeSlimeLarge": "SpikeSlime_L",
    "SpikeSlimeMedium": "SpikeSlime_M",
    "SpikeSlimeSmall": "SpikeSlime_S",
    "Taskmaster": "SlaverBoss",
}


CANONICAL_RUNTIME_ALIASES: dict[str, tuple[str, ...]] = {
    "Automaton": ("BronzeAutomaton", "Bronze Automaton"),
    "Collector": ("TheCollector", "The Collector"),
    "FuzzyLouseNormal": ("Louse", "LouseNormal", "FuzzyLouseNormal"),
    "LouseDefensive": ("FuzzyLouseDefensive",),
    "GremlinSneaky": ("GremlinThief",),
    "GremlinWar": ("GremlinWarrior",),
    "OrbWalker": ("Orb Walker",),
    "ShellParasite": ("ShelledParasite", "Shelled Parasite", "Shell Parasite"),
    "SnakeDagger": ("Dagger",),
    "SpireGrowth": ("Serpent",),
    "Taskmaster": ("SlaverBoss",),
    "BanditPointy": ("BanditChild",),
    "AcidSlimeLarge": ("AcidSlime_L",),
    "AcidSlimeMedium": ("AcidSlime_M",),
    "AcidSlimeSmall": ("AcidSlime_S",),
    "SpikeSlimeLarge": ("SpikeSlime_L",),
    "SpikeSlimeMedium": ("SpikeSlime_M",),
    "SpikeSlimeSmall": ("SpikeSlime_S",),
}


COMBAT_CAPABLE_MONSTERS: tuple[str, ...] = (
    "AcidSlimeLarge",
    "AcidSlimeMedium",
    "AcidSlimeSmall",
    "Automaton",
    "AwakenedOne",
    "BanditBear",
    "BanditLeader",
    "BanditPointy",
    "BookOfStabbing",
    "BronzeOrb",
    "Byrd",
    "Centurion",
    "Champ",
    "Chosen",
    "Collector",
    "CorruptHeart",
    "Cultist",
    "Darkling",
    "Deca",
    "Donu",
    "Exploder",
    "FungiBeast",
    "FuzzyLouseNormal",
    "GiantHead",
    "GremlinFat",
    "GremlinLeader",
    "GremlinNob",
    "GremlinSneaky",
    "GremlinTsundere",
    "GremlinWar",
    "GremlinWizard",
    "Healer",
    "Hexaghost",
    "JawWorm",
    "Lagavulin",
    "Looter",
    "LouseDefensive",
    "Maw",
    "Mugger",
    "Nemesis",
    "OrbWalker",
    "Reptomancer",
    "Repulsor",
    "Sentry",
    "ShellParasite",
    "SlaverBlue",
    "SlaverRed",
    "SlimeBoss",
    "SnakeDagger",
    "SnakePlant",
    "Snecko",
    "SphericGuardian",
    "SpikeSlimeLarge",
    "SpikeSlimeMedium",
    "SpikeSlimeSmall",
    "Spiker",
    "SpireGrowth",
    "SpireShield",
    "SpireSpear",
    "Taskmaster",
    "TheGuardian",
    "TimeEater",
    "TorchHead",
    "Transient",
    "WrithingMass",
)


INTERNAL_MONSTER_ENTRIES: dict[str, dict[str, object]] = {
    "ApologySlime": {
        "official_key": "Apology Slime",
        "java_class": "ApologySlime",
        "category": "SPECIAL",
        "act": 1,
        "internal_surface": "special_fallback",
        "combat_capable": False,
    },
    "FireOrb": {
        "official_key": "FireOrb",
        "java_class": "HexaghostOrb",
        "category": "SPECIAL",
        "act": 1,
        "internal_surface": "internal_visual",
        "combat_capable": False,
    },
    "HexaghostBody": {
        "official_key": "HexaghostBody",
        "java_class": "HexaghostBody",
        "category": "SPECIAL",
        "act": 1,
        "internal_surface": "internal_visual",
        "combat_capable": False,
    },
    "HexaghostOrb": {
        "official_key": "HexaghostOrb",
        "java_class": "HexaghostOrb",
        "category": "SPECIAL",
        "act": 1,
        "internal_surface": "internal_visual",
        "combat_capable": False,
    },
    "Puppeteer": {
        "official_key": "Puppeteer",
        "java_class": "TheCollector",
        "category": "SPECIAL",
        "act": 2,
        "internal_surface": "internal_script",
        "combat_capable": False,
    },
    "FlameBruiser": {
        "official_key": "FlameBruiser",
        "java_class": "Reptomancer",
        "category": "SPECIAL",
        "act": 3,
        "internal_surface": "internal_script",
        "combat_capable": False,
    },
    "TheGuardianOrb": {
        "official_key": "TheGuardianOrb",
        "java_class": "TheGuardianOrb",
        "category": "SPECIAL",
        "act": 1,
        "internal_surface": "internal_visual",
        "combat_capable": False,
    },
}


MONSTER_CATEGORY_OVERRIDES: dict[str, str] = {
    "GremlinNob": "ELITE",
    "Lagavulin": "ELITE",
    "Sentry": "ELITE",
    "BookOfStabbing": "ELITE",
    "GremlinLeader": "ELITE",
    "Taskmaster": "ELITE",
    "Nemesis": "ELITE",
    "Reptomancer": "ELITE",
    "GiantHead": "ELITE",
    "Hexaghost": "BOSS",
    "SlimeBoss": "BOSS",
    "TheGuardian": "BOSS",
    "Champ": "BOSS",
    "Collector": "BOSS",
    "Automaton": "BOSS",
    "AwakenedOne": "BOSS",
    "TimeEater": "BOSS",
    "Donu": "BOSS",
    "Deca": "BOSS",
    "CorruptHeart": "BOSS",
    "SpireShield": "ELITE",
    "SpireSpear": "ELITE",
    "BronzeOrb": "SUMMON",
    "TorchHead": "SUMMON",
    "SnakeDagger": "SUMMON",
    "BanditBear": "SPECIAL",
    "BanditLeader": "SPECIAL",
    "BanditPointy": "SPECIAL",
}


MONSTER_ACT_OVERRIDES: dict[str, int] = {
    "AcidSlimeLarge": 1,
    "AcidSlimeMedium": 1,
    "AcidSlimeSmall": 1,
    "Cultist": 1,
    "FungiBeast": 1,
    "FuzzyLouseNormal": 1,
    "GremlinFat": 1,
    "GremlinNob": 1,
    "GremlinSneaky": 1,
    "GremlinTsundere": 1,
    "GremlinWar": 1,
    "GremlinWizard": 1,
    "Hexaghost": 1,
    "JawWorm": 1,
    "Lagavulin": 1,
    "Looter": 1,
    "LouseDefensive": 1,
    "Mugger": 1,
    "Sentry": 1,
    "SlaverBlue": 1,
    "SlaverRed": 1,
    "SlimeBoss": 1,
    "SpikeSlimeLarge": 1,
    "SpikeSlimeMedium": 1,
    "SpikeSlimeSmall": 1,
    "TheGuardian": 1,
    "BookOfStabbing": 2,
    "Byrd": 2,
    "Centurion": 2,
    "Champ": 2,
    "Chosen": 2,
    "Collector": 2,
    "GremlinLeader": 2,
    "Healer": 2,
    "ShellParasite": 2,
    "SnakePlant": 2,
    "Snecko": 2,
    "SphericGuardian": 2,
    "Taskmaster": 2,
    "TorchHead": 2,
    "BanditBear": 2,
    "BanditLeader": 2,
    "BanditPointy": 2,
    "Automaton": 2,
    "BronzeOrb": 2,
    "AwakenedOne": 3,
    "Darkling": 3,
    "Deca": 3,
    "Donu": 3,
    "Exploder": 3,
    "GiantHead": 3,
    "Maw": 3,
    "Nemesis": 3,
    "OrbWalker": 3,
    "Reptomancer": 3,
    "Repulsor": 3,
    "SnakeDagger": 3,
    "Spiker": 3,
    "SpireGrowth": 3,
    "TimeEater": 3,
    "Transient": 3,
    "WrithingMass": 3,
    "CorruptHeart": 4,
    "SpireShield": 4,
    "SpireSpear": 4,
}


FIXED_ENCOUNTER_MEMBERS: dict[str, tuple[str, ...]] = {
    "Cultist": ("Cultist",),
    "Jaw Worm": ("JawWorm",),
    "Blue Slaver": ("SlaverBlue",),
    "Red Slaver": ("SlaverRed",),
    "Looter": ("Looter",),
    "2 Fungi Beasts": ("FungiBeast", "FungiBeast"),
    "Gremlin Nob": ("GremlinNob",),
    "Lagavulin": ("Lagavulin",),
    "3 Sentries": ("Sentry", "Sentry", "Sentry"),
    "Lagavulin Event": ("Lagavulin",),
    "The Mushroom Lair": ("FungiBeast", "FungiBeast", "FungiBeast"),
    "The Guardian": ("TheGuardian",),
    "Hexaghost": ("Hexaghost",),
    "Slime Boss": ("SlimeBoss",),
    "2 Thieves": ("Looter", "Mugger"),
    "3 Byrds": ("Byrd", "Byrd", "Byrd"),
    "4 Byrds": ("Byrd", "Byrd", "Byrd", "Byrd"),
    "Chosen": ("Chosen",),
    "Shell Parasite": ("ShellParasite",),
    "Spheric Guardian": ("SphericGuardian",),
    "Cultist and Chosen": ("Cultist", "Chosen"),
    "3 Cultists": ("Cultist", "Cultist", "Cultist"),
    "Chosen and Byrds": ("Byrd", "Chosen"),
    "Sentry and Sphere": ("Sentry", "SphericGuardian"),
    "Snake Plant": ("SnakePlant",),
    "Snecko": ("Snecko",),
    "Centurion and Healer": ("Centurion", "Healer"),
    "Shelled Parasite and Fungi": ("ShellParasite", "FungiBeast"),
    "Book of Stabbing": ("BookOfStabbing",),
    "Slavers": ("SlaverBlue", "Taskmaster", "SlaverRed"),
    "Masked Bandits": ("BanditPointy", "BanditLeader", "BanditBear"),
    "Colosseum Nobs": ("Taskmaster", "GremlinNob"),
    "Colosseum Slavers": ("SlaverBlue", "SlaverRed"),
    "Automaton": ("Automaton",),
    "Champ": ("Champ",),
    "Collector": ("Collector",),
    "Transient": ("Transient",),
    "3 Darklings": ("Darkling", "Darkling", "Darkling"),
    "Jaw Worm Horde": ("JawWorm", "JawWorm", "JawWorm"),
    "Snecko and Mystics": ("Healer", "Snecko", "Healer"),
    "Orb Walker": ("OrbWalker",),
    "Spire Growth": ("SpireGrowth",),
    "Maw": ("Maw",),
    "2 Orb Walkers": ("OrbWalker", "OrbWalker"),
    "Nemesis": ("Nemesis",),
    "Writhing Mass": ("WrithingMass",),
    "Giant Head": ("GiantHead",),
    "Time Eater": ("TimeEater",),
    "Awakened One": ("Cultist", "Cultist", "AwakenedOne"),
    "Donu and Deca": ("Deca", "Donu"),
    "The Heart": ("CorruptHeart",),
    "Shield and Spear": ("SpireShield", "SpireSpear"),
}


SUMMONED_ENCOUNTER_MEMBERS: dict[str, tuple[str, ...]] = {
    "Automaton": ("BronzeOrb",),
    "Collector": ("TorchHead",),
}


POSSIBLE_ENCOUNTER_MEMBERS: dict[str, tuple[str, ...]] = {
    "2 Louse": ("FuzzyLouseNormal", "LouseDefensive"),
    "3 Louse": ("FuzzyLouseNormal", "LouseDefensive"),
    "Small Slimes": ("AcidSlimeMedium", "AcidSlimeSmall", "SpikeSlimeMedium", "SpikeSlimeSmall"),
    "Large Slime": ("AcidSlimeLarge", "SpikeSlimeLarge"),
    "Lots of Slimes": ("AcidSlimeSmall", "SpikeSlimeSmall"),
    "Gremlin Gang": ("GremlinWar", "GremlinSneaky", "GremlinFat", "GremlinTsundere", "GremlinWizard"),
    "Exordium Thugs": ("Cultist", "SlaverBlue", "SlaverRed", "Looter", "FuzzyLouseNormal", "LouseDefensive", "SpikeSlimeMedium", "AcidSlimeMedium"),
    "Exordium Wildlife": ("FungiBeast", "JawWorm", "FuzzyLouseNormal", "LouseDefensive", "SpikeSlimeMedium", "AcidSlimeMedium"),
    "Gremlin Leader": ("GremlinWar", "GremlinSneaky", "GremlinFat", "GremlinTsundere", "GremlinWizard", "GremlinLeader"),
    "Flame Bruiser 1 Orb": ("Reptomancer", "SnakeDagger"),
    "Flame Bruiser 2 Orb": ("Reptomancer", "SnakeDagger"),
    "Reptomancer": ("Reptomancer", "SnakeDagger"),
    "3 Shapes": ("Repulsor", "Exploder", "Spiker"),
    "4 Shapes": ("Repulsor", "Exploder", "Spiker"),
    "Sphere and 2 Shapes": ("Repulsor", "Exploder", "Spiker", "SphericGuardian"),
    "Mysterious Sphere": ("Repulsor", "Exploder", "Spiker", "OrbWalker"),
}


POOL_MEMBERSHIP: dict[str, tuple[str, ...]] = {
    "pool:act1:weak": ("Cultist", "Jaw Worm", "2 Louse", "Small Slimes"),
    "pool:act1:strong": ("Blue Slaver", "Gremlin Gang", "Looter", "Large Slime", "Lots of Slimes", "Exordium Thugs", "Exordium Wildlife", "Red Slaver", "3 Louse", "2 Fungi Beasts"),
    "pool:act1:elite": ("Gremlin Nob", "Lagavulin", "3 Sentries"),
    "pool:act1:boss": ("The Guardian", "Hexaghost", "Slime Boss"),
    "pool:act2:weak": ("Spheric Guardian", "Chosen", "Shell Parasite", "3 Byrds", "2 Thieves"),
    "pool:act2:strong": ("Chosen and Byrds", "Sentry and Sphere", "Snake Plant", "Snecko", "Centurion and Healer", "Cultist and Chosen", "3 Cultists", "Shelled Parasite and Fungi"),
    "pool:act2:elite": ("Gremlin Leader", "Slavers", "Book of Stabbing"),
    "pool:act2:boss": ("Automaton", "Collector", "Champ"),
    "pool:act3:weak": ("3 Darklings", "Orb Walker", "3 Shapes"),
    "pool:act3:strong": ("Spire Growth", "Transient", "4 Shapes", "Maw", "Sphere and 2 Shapes", "Jaw Worm Horde", "3 Darklings", "Writhing Mass"),
    "pool:act3:elite": ("Giant Head", "Nemesis", "Reptomancer"),
    "pool:act3:boss": ("Awakened One", "Time Eater", "Donu and Deca"),
    "pool:act4:elite": ("Shield and Spear",),
    "pool:act4:boss": ("The Heart",),
    "pool:event:special": ("Masked Bandits", "Colosseum Slavers", "Colosseum Nobs", "Lagavulin Event", "Mysterious Sphere", "The Mushroom Lair", "Snecko and Mystics", "2 Orb Walkers", "Flame Bruiser 1 Orb", "Flame Bruiser 2 Orb"),
}


def _normalize_lookup_token(text: str | None) -> str:
    return re.sub(r"[^0-9a-z]+", "", str(text or "").lower())


@dataclass(frozen=True)
class MonsterTruthEntry:
    canonical_id: str
    official_key: str
    java_class: str
    runtime_aliases: tuple[str, ...]
    category: str
    act: int | None
    encounters: tuple[str, ...]
    pool_buckets: tuple[str, ...]
    official_name_en: str
    official_name_zhs: str
    official_moves_en: tuple[str, ...]
    official_moves_zhs: tuple[str, ...]
    internal_surface: str
    combat_capable: bool
    translation_authority: str

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "MonsterTruthEntry":
        return cls(
            canonical_id=str(data.get("canonical_id", "") or ""),
            official_key=str(data.get("official_key", "") or ""),
            java_class=str(data.get("java_class", "") or ""),
            runtime_aliases=tuple(str(item or "") for item in data.get("runtime_aliases", []) or []),
            category=str(data.get("category", "NORMAL") or "NORMAL"),
            act=int(data["act"]) if data.get("act") is not None else None,
            encounters=tuple(str(item or "") for item in data.get("encounters", []) or []),
            pool_buckets=tuple(str(item or "") for item in data.get("pool_buckets", []) or []),
            official_name_en=str(data.get("official_name_en", "") or ""),
            official_name_zhs=str(data.get("official_name_zhs", "") or ""),
            official_moves_en=tuple(str(item or "") for item in data.get("official_moves_en", []) or []),
            official_moves_zhs=tuple(str(item or "") for item in data.get("official_moves_zhs", []) or []),
            internal_surface=str(data.get("internal_surface", "runtime_combat") or "runtime_combat"),
            combat_capable=bool(data.get("combat_capable", False)),
            translation_authority=str(data.get("translation_authority", "official_localization") or "official_localization"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "canonical_id": self.canonical_id,
            "official_key": self.official_key,
            "java_class": self.java_class,
            "runtime_aliases": list(self.runtime_aliases),
            "category": self.category,
            "act": self.act,
            "encounters": list(self.encounters),
            "pool_buckets": list(self.pool_buckets),
            "official_name_en": self.official_name_en,
            "official_name_zhs": self.official_name_zhs,
            "official_moves_en": list(self.official_moves_en),
            "official_moves_zhs": list(self.official_moves_zhs),
            "internal_surface": self.internal_surface,
            "combat_capable": self.combat_capable,
            "translation_authority": self.translation_authority,
        }


def _official_key_for_canonical_id(canonical_id: str) -> str:
    return CANONICAL_OFFICIAL_KEY_OVERRIDES.get(canonical_id, canonical_id)


def _java_class_for_entry(canonical_id: str, official_key: str) -> str:
    if official_key in OFFICIAL_MONSTER_JAVA_CLASS_OVERRIDES:
        return str(OFFICIAL_MONSTER_JAVA_CLASS_OVERRIDES[official_key])
    return canonical_id


def _runtime_aliases_for_entry(canonical_id: str, official_key: str, java_class: str) -> tuple[str, ...]:
    aliases = {canonical_id, official_key, java_class}
    aliases.update(CANONICAL_RUNTIME_ALIASES.get(canonical_id, ()))
    if official_key:
        aliases.add(official_key.replace(" ", ""))
    return tuple(sorted(alias for alias in aliases if alias))


def _encounters_for_canonical_id(canonical_id: str) -> tuple[str, ...]:
    encounters: set[str] = set()
    for encounter_name, members in FIXED_ENCOUNTER_MEMBERS.items():
        if canonical_id in members:
            encounters.add(encounter_name)
    for encounter_name, members in SUMMONED_ENCOUNTER_MEMBERS.items():
        if canonical_id in members:
            encounters.add(encounter_name)
    for encounter_name, possible_members in POSSIBLE_ENCOUNTER_MEMBERS.items():
        if canonical_id in possible_members:
            encounters.add(encounter_name)
    return tuple(sorted(encounters))


def _pool_buckets_for_canonical_id(canonical_id: str) -> tuple[str, ...]:
    buckets: set[str] = set()
    member_encounters = set(_encounters_for_canonical_id(canonical_id))
    for bucket, encounter_names in POOL_MEMBERSHIP.items():
        if member_encounters.intersection(encounter_names):
            buckets.add(bucket)
    if not buckets and MONSTER_CATEGORY_OVERRIDES.get(canonical_id) == "SUMMON":
        buckets.add("pool:summon")
    return tuple(sorted(buckets))


def build_monster_truth_matrix_snapshot() -> dict[str, object]:
    official_records = load_official_monster_strings()
    records: dict[str, object] = {}

    for canonical_id in COMBAT_CAPABLE_MONSTERS:
        official_key = _official_key_for_canonical_id(canonical_id)
        official = official_records.get(official_key)
        java_class = _java_class_for_entry(canonical_id, official_key)
        records[canonical_id] = MonsterTruthEntry(
            canonical_id=canonical_id,
            official_key=official_key,
            java_class=java_class,
            runtime_aliases=_runtime_aliases_for_entry(canonical_id, official_key, java_class),
            category=MONSTER_CATEGORY_OVERRIDES.get(canonical_id, "NORMAL"),
            act=MONSTER_ACT_OVERRIDES.get(canonical_id),
            encounters=_encounters_for_canonical_id(canonical_id),
            pool_buckets=_pool_buckets_for_canonical_id(canonical_id),
            official_name_en=str(getattr(official, "name_en", "") or canonical_id),
            official_name_zhs=str(getattr(official, "name_zhs", "") or ""),
            official_moves_en=tuple(getattr(official, "moves_en", ()) or ()),
            official_moves_zhs=tuple(getattr(official, "moves_zhs", ()) or ()),
            internal_surface="runtime_combat",
            combat_capable=True,
            translation_authority="official_localization",
        ).to_dict()

    for canonical_id, meta in INTERNAL_MONSTER_ENTRIES.items():
        official_key = str(meta.get("official_key", canonical_id) or canonical_id)
        official = get_official_monster_strings(official_key)
        java_class = str(meta.get("java_class", canonical_id) or canonical_id)
        records[canonical_id] = MonsterTruthEntry(
            canonical_id=canonical_id,
            official_key=official_key,
            java_class=java_class,
            runtime_aliases=_runtime_aliases_for_entry(canonical_id, official_key, java_class),
            category=str(meta.get("category", "SPECIAL") or "SPECIAL"),
            act=int(meta["act"]) if meta.get("act") is not None else None,
            encounters=tuple(str(item) for item in meta.get("encounters", ()) or ()),
            pool_buckets=tuple(str(item) for item in meta.get("pool_buckets", ()) or ()),
            official_name_en=str(getattr(official, "name_en", "") or canonical_id),
            official_name_zhs=str(getattr(official, "name_zhs", "") or ""),
            official_moves_en=tuple(getattr(official, "moves_en", ()) or ()),
            official_moves_zhs=tuple(getattr(official, "moves_zhs", ()) or ()),
            internal_surface=str(meta.get("internal_surface", "internal_only") or "internal_only"),
            combat_capable=bool(meta.get("combat_capable", False)),
            translation_authority="official_localization",
        ).to_dict()

    return {
        "schema_version": 1,
        "records": records,
    }


@lru_cache(maxsize=1)
def load_monster_truth_matrix() -> dict[str, MonsterTruthEntry]:
    payload = json.loads(MONSTER_TRUTH_MATRIX_PATH.read_text(encoding="utf-8"))
    return {
        str(canonical_id): MonsterTruthEntry.from_dict(dict(record))
        for canonical_id, record in dict(payload.get("records", {}) or {}).items()
    }


@lru_cache(maxsize=1)
def _monster_alias_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for canonical_id, entry in load_monster_truth_matrix().items():
        for alias in entry.runtime_aliases:
            lookup.setdefault(_normalize_lookup_token(alias), canonical_id)
        lookup.setdefault(_normalize_lookup_token(canonical_id), canonical_id)
    return lookup


def canonicalize_monster_id(monster_id: str | None) -> str | None:
    if monster_id is None:
        return None
    return _monster_alias_lookup().get(_normalize_lookup_token(monster_id))


def get_monster_truth(monster_id: str | None) -> MonsterTruthEntry | None:
    canonical_id = canonicalize_monster_id(monster_id)
    if canonical_id is None:
        return None
    return load_monster_truth_matrix().get(canonical_id)


def official_monster_name_zhs(monster_id: str | None) -> str | None:
    entry = get_monster_truth(monster_id)
    if entry is None or not entry.official_name_zhs:
        return None
    return entry.official_name_zhs


__all__ = [
    "COMBAT_CAPABLE_MONSTERS",
    "MONSTER_TRUTH_MATRIX_PATH",
    "MonsterTruthEntry",
    "build_monster_truth_matrix_snapshot",
    "canonicalize_monster_id",
    "get_monster_truth",
    "load_monster_truth_matrix",
    "official_monster_name_zhs",
]
