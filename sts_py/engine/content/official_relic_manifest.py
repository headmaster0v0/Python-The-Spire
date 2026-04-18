from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import json
import re
import zipfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DESKTOP_JAR_PATH = REPO_ROOT / "desktop-1.0.jar"
RELIC_LIBRARY_PATH = REPO_ROOT / "decompiled_src" / "com" / "megacrit" / "cardcrawl" / "helpers" / "RelicLibrary.java"
RELIC_SRC_DIR = REPO_ROOT / "decompiled_src" / "com" / "megacrit" / "cardcrawl" / "relics"

LEGACY_RUNTIME_RELIC_CLASS_MAP: dict[str, str] = {
    "CaptainWheel": "CaptainsWheel",
    "ChampionBelt": "ChampionsBelt",
    "FrozenEgg": "FrozenEgg2",
    "LeesWaffle": "Waffle",
    "MoltenEgg": "MoltenEgg2",
    "PandoraBox": "PandorasBox",
    "PhilosophersStone": "PhilosopherStone",
    "RingOfTheSnake": "SnakeRing",
    "SlaverCollar": "SlaversCollar",
    "TheAbacus": "Abacus",
    "TheBoot": "Boot",
    "TheCourier": "Courier",
    "ToxicEgg": "ToxicEgg2",
    "WhiteBeastStatue": "WhiteBeast",
    "WingedGreaves": "WingBoots",
}

REVERSE_LEGACY_RUNTIME_RELIC_CLASS_MAP: dict[str, str] = {
    class_name: runtime_id for runtime_id, class_name in LEGACY_RUNTIME_RELIC_CLASS_MAP.items()
}

SPECIAL_RUNTIME_RELICS: dict[str, str] = {
    "Circlet": "Circlet",
}


@dataclass(frozen=True)
class OfficialRelicManifestEntry:
    runtime_id: str
    official_id: str
    class_name: str
    tier: str
    character_class: str
    loadable: bool
    legacy_ids: tuple[str, ...] = field(default_factory=tuple)
    spawn_rules: dict[str, Any] = field(default_factory=dict)
    initial_counter: int | None = None
    depletion_rules: dict[str, Any] = field(default_factory=dict)
    name_en: str = ""
    name_zhs: str = ""
    description_en_parts: tuple[str, ...] = field(default_factory=tuple)
    description_zhs_parts: tuple[str, ...] = field(default_factory=tuple)
    description_en: str = ""
    description_zhs: str = ""
    flavor_en: str = ""
    flavor_zhs: str = ""
    source_methods: tuple[str, ...] = field(default_factory=tuple)
    rng_notes: tuple[str, ...] = field(default_factory=tuple)


def _normalize_lookup_key(value: str | None) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        return ""
    candidate = re.sub(r"[ _'\-]+", "", candidate)
    candidate = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", candidate)
    return candidate.lower()


def _sanitize_localized_text(text: str | None, *, cn: bool) -> str:
    cleaned = str(text or "")
    replacements = {
        "#b": "",
        "#y": "",
        "#r": "",
        "#g": "",
        "#p": "",
        "#o": "",
        " NL ": " ",
        " NL": " ",
        "NL ": " ",
        "NL": " ",
    }
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    cleaned = cleaned.replace("[E]", "1点能量" if cn else "1 Energy")
    cleaned = cleaned.replace("？", "?")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s+([。，“”、！？：；）】》])", r"\1", cleaned)
    cleaned = re.sub(r"([（【《])\s+", r"\1", cleaned)
    cleaned = re.sub(r"([。！？])\s+(?=[\u4e00-\u9fff0-9])", r"\1", cleaned)
    cleaned = re.sub(r"(?<=[\u4e00-\u9fff0-9])\s+(?=[\u4e00-\u9fff])", "", cleaned)
    cleaned = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[0-9])", "", cleaned)
    return cleaned.strip()


def _compose_description(parts: list[str], inserts: list[str], *, cn: bool) -> str:
    if inserts and len(parts) > len(inserts) + 1:
        parts = parts[: len(inserts) + 1]
    sanitized_parts = [_sanitize_localized_text(part, cn=cn) for part in parts if str(part or "").strip()]
    if not sanitized_parts:
        return ""
    if len(sanitized_parts) == 1:
        return sanitized_parts[0]
    if not inserts:
        return sanitized_parts[0]
    rendered: list[str] = [sanitized_parts[0]]
    for idx, part in enumerate(sanitized_parts[1:], start=1):
        if idx - 1 < len(inserts):
            rendered.append(str(inserts[idx - 1]))
        rendered.append(part)
    return re.sub(r"\s+", " ", "".join(rendered)).strip()


def _load_relic_localizations() -> tuple[dict[str, Any], dict[str, Any]]:
    with zipfile.ZipFile(DESKTOP_JAR_PATH) as jar_file:
        eng = json.loads(jar_file.read("localization/eng/relics.json").decode("utf-8"))
        zhs = json.loads(jar_file.read("localization/zhs/relics.json").decode("utf-8"))
    return eng, zhs


def _parse_loaded_relic_classes() -> list[tuple[str, str]]:
    text = RELIC_LIBRARY_PATH.read_text(encoding="utf-8", errors="ignore")
    return re.findall(r"RelicLibrary\.add(?:(Red|Green|Blue|Purple))?\(new (\w+)\(", text)


def _extract_source_methods(source_text: str) -> tuple[str, ...]:
    methods = re.findall(r"@Override\s+public\s+[^\n(]+\s+(\w+)\s*\(", source_text)
    return tuple(dict.fromkeys(methods))


def _extract_constructor_body(source_text: str, class_name: str) -> str:
    match = re.search(rf"public\s+{re.escape(class_name)}\s*\(\)\s*\{{(?P<body>.*?)\n\s*\}}", source_text, re.S)
    return match.group("body") if match else ""


def _extract_tier(source_text: str) -> str:
    match = re.search(r"AbstractRelic\.RelicTier\.(\w+)", source_text)
    return str(match.group(1) if match else "SPECIAL")


def _extract_spawn_rules(source_text: str) -> dict[str, Any]:
    spawn_rules: dict[str, Any] = {}
    can_spawn = re.search(r"boolean\s+canSpawn\s*\(\)\s*\{(?P<body>.*?)\n\s*\}", source_text, re.S)
    if not can_spawn:
        return spawn_rules
    body = can_spawn.group("body")
    floor_limit = re.search(r"AbstractDungeon\.floorNum\s*<=\s*(\d+)", body)
    if floor_limit:
        spawn_rules["floor_limit"] = int(floor_limit.group(1))
    if "ShopRoom" in body:
        spawn_rules["disallow_reward_in_shop_room"] = True
    if "Settings.isEndless" in body:
        spawn_rules["endless_bypass"] = True
    return spawn_rules


def _extract_initial_counter(source_text: str, class_name: str) -> int | None:
    constructor_body = _extract_constructor_body(source_text, class_name)
    match = re.search(r"this\.counter\s*=\s*(-?\d+)", constructor_body)
    return int(match.group(1)) if match else None


def _extract_depletion_rules(source_text: str) -> dict[str, Any]:
    rules: dict[str, Any] = {}
    if "usedUp()" in source_text:
        rules["uses_used_up"] = True
    if "stopPulse()" in source_text:
        rules["uses_pulse"] = True
    return rules


def _extract_rng_notes(source_text: str) -> tuple[str, ...]:
    rng_matches = re.findall(r"AbstractDungeon\.(\w+Rng)", source_text)
    return tuple(dict.fromkeys(rng_matches))


def _extract_description_inserts(source_text: str) -> list[str]:
    return re.findall(r"DESCRIPTIONS\[\d+\]\s*\+\s*(-?\d+)\s*(?=\+)", source_text)


def _character_class_for_call(color_variant: str, tier: str) -> str:
    if color_variant == "Red":
        return "IRONCLAD"
    if color_variant == "Green":
        return "SILENT"
    if color_variant == "Blue":
        return "DEFECT"
    if color_variant == "Purple":
        return "WATCHER"
    return "UNIVERSAL"


def _build_entry(
    runtime_id: str,
    class_name: str,
    official_id: str,
    *,
    tier: str,
    character_class: str,
    loadable: bool,
    eng_localized: dict[str, Any],
    zhs_localized: dict[str, Any],
) -> OfficialRelicManifestEntry:
    source_path = RELIC_SRC_DIR / f"{class_name}.java"
    source_text = source_path.read_text(encoding="utf-8", errors="ignore") if source_path.exists() else ""
    eng_entry = eng_localized.get(official_id, {})
    zhs_entry = zhs_localized.get(official_id, {})
    desc_inserts = _extract_description_inserts(source_text)
    legacy_ids = [runtime_id]
    if runtime_id != class_name:
        legacy_ids.append(class_name)
    if runtime_id != official_id:
        legacy_ids.append(official_id)
    return OfficialRelicManifestEntry(
        runtime_id=runtime_id,
        official_id=official_id,
        class_name=class_name,
        tier=tier,
        character_class=character_class,
        loadable=loadable,
        legacy_ids=tuple(dict.fromkeys(str(item) for item in legacy_ids if str(item).strip())),
        spawn_rules=_extract_spawn_rules(source_text),
        initial_counter=_extract_initial_counter(source_text, class_name),
        depletion_rules=_extract_depletion_rules(source_text),
        name_en=str(eng_entry.get("NAME", "") or ""),
        name_zhs=str(zhs_entry.get("NAME", "") or ""),
        description_en_parts=tuple(str(part or "") for part in eng_entry.get("DESCRIPTIONS", []) or []),
        description_zhs_parts=tuple(str(part or "") for part in zhs_entry.get("DESCRIPTIONS", []) or []),
        description_en=_compose_description(list(eng_entry.get("DESCRIPTIONS", []) or []), desc_inserts, cn=False),
        description_zhs=_compose_description(list(zhs_entry.get("DESCRIPTIONS", []) or []), desc_inserts, cn=True),
        flavor_en=_sanitize_localized_text(eng_entry.get("FLAVOR", ""), cn=False),
        flavor_zhs=_sanitize_localized_text(zhs_entry.get("FLAVOR", ""), cn=True),
        source_methods=_extract_source_methods(source_text),
        rng_notes=_extract_rng_notes(source_text),
    )


@lru_cache(maxsize=1)
def get_runtime_relic_manifest() -> dict[str, OfficialRelicManifestEntry]:
    eng_localized, zhs_localized = _load_relic_localizations()
    class_to_official_id: dict[str, str] = {}
    for source_path in RELIC_SRC_DIR.glob("*.java"):
        if source_path.stem == "AbstractRelic":
            continue
        match = re.search(
            r'public static final String ID = "([^"]+)";',
            source_path.read_text(encoding="utf-8", errors="ignore"),
        )
        if match:
            class_to_official_id[source_path.stem] = match.group(1)

    manifest: dict[str, OfficialRelicManifestEntry] = {}
    for color_variant, class_name in _parse_loaded_relic_classes():
        runtime_id = REVERSE_LEGACY_RUNTIME_RELIC_CLASS_MAP.get(class_name, class_name)
        official_id = class_to_official_id.get(class_name, runtime_id)
        tier_source = (RELIC_SRC_DIR / f"{class_name}.java").read_text(encoding="utf-8", errors="ignore")
        tier = _extract_tier(tier_source)
        character_class = _character_class_for_call(color_variant, tier)
        manifest[runtime_id] = _build_entry(
            runtime_id,
            class_name,
            official_id,
            tier=tier,
            character_class=character_class,
            loadable=True,
            eng_localized=eng_localized,
            zhs_localized=zhs_localized,
        )

    for runtime_id, official_id in SPECIAL_RUNTIME_RELICS.items():
        manifest[runtime_id] = _build_entry(
            runtime_id,
            runtime_id,
            official_id,
            tier="SPECIAL",
            character_class="UNIVERSAL",
            loadable=True,
            eng_localized=eng_localized,
            zhs_localized=zhs_localized,
        )
    return manifest


@lru_cache(maxsize=1)
def get_localization_only_relic_manifest() -> dict[str, OfficialRelicManifestEntry]:
    eng_localized, zhs_localized = _load_relic_localizations()
    runtime_manifest = get_runtime_relic_manifest()
    runtime_official_ids = {entry.official_id for entry in runtime_manifest.values()}
    localization_only: dict[str, OfficialRelicManifestEntry] = {}
    for official_id in sorted(set(eng_localized) - runtime_official_ids):
        localization_only[official_id] = OfficialRelicManifestEntry(
            runtime_id=official_id,
            official_id=official_id,
            class_name="",
            tier="LOCALIZATION_ONLY",
            character_class="UNIVERSAL",
            loadable=False,
            legacy_ids=tuple(),
            spawn_rules={},
            initial_counter=None,
            depletion_rules={},
            name_en=str(eng_localized[official_id].get("NAME", "") or ""),
            name_zhs=str(zhs_localized.get(official_id, {}).get("NAME", "") or ""),
            description_en_parts=tuple(str(part or "") for part in eng_localized[official_id].get("DESCRIPTIONS", []) or []),
            description_zhs_parts=tuple(str(part or "") for part in zhs_localized.get(official_id, {}).get("DESCRIPTIONS", []) or []),
            description_en=_compose_description(list(eng_localized[official_id].get("DESCRIPTIONS", []) or []), [], cn=False),
            description_zhs=_compose_description(list(zhs_localized.get(official_id, {}).get("DESCRIPTIONS", []) or []), [], cn=True),
            flavor_en=_sanitize_localized_text(eng_localized[official_id].get("FLAVOR", ""), cn=False),
            flavor_zhs=_sanitize_localized_text(zhs_localized.get(official_id, {}).get("FLAVOR", ""), cn=True),
            source_methods=tuple(),
            rng_notes=tuple(),
        )
    return localization_only


@lru_cache(maxsize=1)
def get_relic_lookup_aliases() -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for runtime_id, entry in get_runtime_relic_manifest().items():
        alias_candidates = {
            runtime_id,
            entry.class_name,
            entry.official_id,
            entry.name_en,
            entry.name_zhs,
            *entry.legacy_ids,
        }
        for candidate in alias_candidates:
            normalized = _normalize_lookup_key(candidate)
            if normalized:
                alias_map[normalized] = runtime_id
    return alias_map
