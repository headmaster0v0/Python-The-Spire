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
ENG_RELICS_JSON_PATH = "localization/eng/relics.json"
ZHS_RELICS_JSON_PATH = "localization/zhs/relics.json"
CN_SELECTED_CARD_PLACEHOLDER = "{selected_card_name}"
EN_SELECTED_CARD_PLACEHOLDER = "{selected_card_name}"

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
class OfficialRelicTextVariant:
    kind: str
    source_method: str
    description_en: str = ""
    description_zhs: str = ""
    slots_used: tuple[int, ...] = field(default_factory=tuple)


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
    default_description_en: str = ""
    default_description_zhs: str = ""
    description_slots_used: tuple[int, ...] = field(default_factory=tuple)
    stateful_description_variants: tuple[OfficialRelicTextVariant, ...] = field(default_factory=tuple)
    ui_prompt_slots: tuple[int, ...] = field(default_factory=tuple)
    flavor_en: str = ""
    flavor_zhs: str = ""
    source_methods: tuple[str, ...] = field(default_factory=tuple)
    rng_notes: tuple[str, ...] = field(default_factory=tuple)
    truth_sources: dict[str, Any] = field(default_factory=dict)


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


def _dedupe_preserve_order(items: list[Any]) -> tuple[Any, ...]:
    seen: set[Any] = set()
    ordered: list[Any] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return tuple(ordered)


def _load_relic_localizations() -> tuple[dict[str, Any], dict[str, Any]]:
    with zipfile.ZipFile(DESKTOP_JAR_PATH) as jar_file:
        eng = json.loads(jar_file.read(ENG_RELICS_JSON_PATH).decode("utf-8"))
        zhs = json.loads(jar_file.read(ZHS_RELICS_JSON_PATH).decode("utf-8"))
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


def _extract_braced_block(source_text: str, brace_start: int) -> str:
    depth = 0
    in_string = False
    string_char = ""
    escaped = False
    for index in range(brace_start, len(source_text)):
        char = source_text[index]
        if in_string:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == string_char:
                in_string = False
            continue
        if char in ('"', "'"):
            in_string = True
            string_char = char
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return source_text[brace_start + 1 : index]
    return ""


def _iter_method_blocks(source_text: str) -> list[tuple[str, str]]:
    method_pattern = re.compile(
        r"(?:public|protected|private)\s+(?:static\s+)?[^\n;{}=]+?\s+(\w+)\s*\([^)]*\)\s*\{",
        re.S,
    )
    blocks: list[tuple[str, str]] = []
    for match in method_pattern.finditer(source_text):
        method_name = str(match.group(1))
        body = _extract_braced_block(source_text, match.end() - 1)
        blocks.append((method_name, body))
    return blocks


def _extract_method_body(source_text: str, method_name: str) -> str:
    for candidate_name, body in _iter_method_blocks(source_text):
        if candidate_name == method_name:
            return body
    return ""


def _split_top_level(value: str, delimiter: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth_paren = 0
    depth_bracket = 0
    in_string = False
    string_char = ""
    escaped = False
    for char in value:
        if in_string:
            current.append(char)
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == string_char:
                in_string = False
            continue
        if char in ('"', "'"):
            in_string = True
            string_char = char
            current.append(char)
            continue
        if char == "(":
            depth_paren += 1
        elif char == ")":
            depth_paren = max(0, depth_paren - 1)
        elif char == "[":
            depth_bracket += 1
        elif char == "]":
            depth_bracket = max(0, depth_bracket - 1)
        if char == delimiter and depth_paren == 0 and depth_bracket == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    final = "".join(current).strip()
    if final:
        parts.append(final)
    return parts


def _strip_wrapping_parens(value: str) -> str:
    candidate = value.strip()
    while candidate.startswith("(") and candidate.endswith(")"):
        inner = candidate[1:-1].strip()
        if inner.count("(") != inner.count(")"):
            break
        candidate = inner
    return candidate


def _extract_description_slots(expression: str) -> tuple[int, ...]:
    return tuple(int(match) for match in re.findall(r"DESCRIPTIONS\[(\d+)\]", expression))


def _render_java_expression(
    expression: str,
    localized_parts: list[str],
    localized_name: str,
    *,
    cn: bool,
) -> str:
    rendered: list[str] = []
    for raw_part in _split_top_level(_strip_wrapping_parens(expression), "+"):
        part = _strip_wrapping_parens(raw_part)
        if not part:
            continue
        desc_match = re.fullmatch(r"(?:this\.)?DESCRIPTIONS\[(\d+)\]", part)
        if desc_match:
            index = int(desc_match.group(1))
            rendered.append(localized_parts[index] if index < len(localized_parts) else "")
            continue
        if re.fullmatch(r"-?\d+", part):
            rendered.append(part)
            continue
        if part == "LocalizedStrings.PERIOD":
            rendered.append("。" if cn else ".")
            continue
        if part in {"this.name", "name"}:
            rendered.append(localized_name)
            continue
        if "this.card.name" in part or "card.name" in part:
            rendered.append(CN_SELECTED_CARD_PLACEHOLDER if cn else EN_SELECTED_CARD_PLACEHOLDER)
            continue
        string_match = re.fullmatch(r'"(.*)"', part, re.S)
        if string_match:
            rendered.append(string_match.group(1))
            continue
        rendered.append(part)
    return _sanitize_localized_text("".join(rendered), cn=cn)


def _extract_return_expressions(method_body: str) -> list[str]:
    return [match.strip() for match in re.findall(r"return\s+(.*?);", method_body, re.S)]


def _resolve_return_expression(
    method_body: str,
    localized_parts: list[str],
) -> str:
    conditional = re.search(
        r'if\s*\(\s*!?\s*(?:this\.)?DESCRIPTIONS\[(\d+)\]\.equals\(""\)\s*\)\s*\{\s*return\s+(.*?);\s*\}\s*return\s+(.*?);',
        method_body,
        re.S,
    )
    if conditional:
        index = int(conditional.group(1))
        primary = conditional.group(2).strip()
        fallback = conditional.group(3).strip()
        has_text = index < len(localized_parts) and bool(str(localized_parts[index]).strip())
        condition_is_negated = "!" in conditional.group(0).split("return", 1)[0]
        if condition_is_negated:
            return primary if has_text else fallback
        return primary if not has_text else fallback
    returns = _extract_return_expressions(method_body)
    return returns[0] if returns else ""


def _resolve_method_expression(
    source_text: str,
    method_name: str,
    localized_parts: list[str],
    localized_name: str,
    *,
    cn: bool,
    visited: tuple[str, ...] = (),
) -> tuple[str, tuple[int, ...]]:
    if method_name in visited:
        return "", tuple()
    method_body = _extract_method_body(source_text, method_name)
    if not method_body:
        return "", tuple()
    expression = _resolve_return_expression(method_body, localized_parts)
    helper_match = re.fullmatch(r"this\.(\w+)\([^)]*\)", _strip_wrapping_parens(expression))
    if helper_match:
        return _resolve_method_expression(
            source_text,
            helper_match.group(1),
            localized_parts,
            localized_name,
            cn=cn,
            visited=visited + (method_name,),
        )
    return _render_java_expression(expression, localized_parts, localized_name, cn=cn), _extract_description_slots(expression)


def _extract_assignment_variants(
    source_text: str,
    eng_parts: list[str],
    zhs_parts: list[str],
    name_en: str,
    name_zhs: str,
    *,
    default_en: str,
    default_zhs: str,
) -> tuple[OfficialRelicTextVariant, ...]:
    variants: list[OfficialRelicTextVariant] = []
    for method_name, method_body in _iter_method_blocks(source_text):
        for expr in re.findall(r"this\.description\s*=\s*(.*?);", method_body, re.S):
            stripped = _strip_wrapping_parens(expr)
            helper_match = re.fullmatch(r"this\.(\w+)\([^)]*\)", stripped)
            if helper_match:
                rendered_en, slots = _resolve_method_expression(source_text, helper_match.group(1), eng_parts, name_en, cn=False)
                rendered_zhs, _ = _resolve_method_expression(source_text, helper_match.group(1), zhs_parts, name_zhs, cn=True)
            else:
                rendered_en = _render_java_expression(stripped, eng_parts, name_en, cn=False)
                rendered_zhs = _render_java_expression(stripped, zhs_parts, name_zhs, cn=True)
                slots = _extract_description_slots(stripped)
            if not rendered_en and not rendered_zhs:
                continue
            if rendered_en == default_en and rendered_zhs == default_zhs:
                continue
            variants.append(
                OfficialRelicTextVariant(
                    kind="stateful",
                    source_method=method_name,
                    description_en=rendered_en,
                    description_zhs=rendered_zhs,
                    slots_used=_dedupe_preserve_order(list(slots)),
                )
            )

    used_slots = {
        slot
        for variant in variants
        for slot in variant.slots_used
    }
    if "usedUp()" in source_text:
        for index in range(len(eng_parts) - 1, -1, -1):
            if index in used_slots:
                continue
            used_up_en = _sanitize_localized_text(eng_parts[index], cn=False)
            used_up_zhs = _sanitize_localized_text(zhs_parts[index] if index < len(zhs_parts) else "", cn=True)
            if not used_up_en and not used_up_zhs:
                continue
            if "used up" not in used_up_en.lower() and "耗尽" not in used_up_zhs:
                continue
            variants.append(
                OfficialRelicTextVariant(
                    kind="stateful",
                    source_method="usedUp",
                    description_en=used_up_en,
                    description_zhs=used_up_zhs,
                    slots_used=(index,),
                )
            )
            break
    return _dedupe_preserve_order(variants)


def _extract_ui_prompt_slots(source_text: str) -> tuple[int, ...]:
    prompt_slots: list[int] = []
    prompt_targets = (
        ("gridSelectScreen.openConfirmationGrid", 1),
        ("gridSelectScreen.open", 2),
        ("combatRewardScreen.open", 0),
    )
    for method_name, method_body in _iter_method_blocks(source_text):
        del method_name
        for target, arg_index in prompt_targets:
            pattern = re.compile(rf"(?:AbstractDungeon\.)?{re.escape(target)}\((?P<args>.*?)\);", re.S)
            for match in pattern.finditer(method_body):
                args = _split_top_level(match.group("args"), ",")
                if arg_index >= len(args):
                    continue
                prompt_slots.extend(_extract_description_slots(args[arg_index]))
    return _dedupe_preserve_order(prompt_slots)


def _extract_spawn_rules(source_text: str) -> dict[str, Any]:
    spawn_rules: dict[str, Any] = {}
    can_spawn = _extract_method_body(source_text, "canSpawn")
    if not can_spawn:
        return spawn_rules

    floor_limit = re.search(r"AbstractDungeon\.floorNum\s*(?:<=|>=)\s*(\d+)", can_spawn)
    if floor_limit:
        spawn_rules["floor_limit"] = int(floor_limit.group(1))
    if "ShopRoom" in can_spawn:
        spawn_rules["disallow_reward_in_shop_room"] = True
    if "Settings.isEndless" in can_spawn:
        spawn_rules["endless_bypass"] = True

    act_limit = re.search(r"AbstractDungeon\.actNum\s*<=\s*(\d+)", can_spawn)
    if act_limit:
        spawn_rules["act_max"] = int(act_limit.group(1))

    required_relics = re.findall(r'hasRelic\("([^"]+)"\)', can_spawn)
    if required_relics:
        spawn_rules["required_relics"] = tuple(required_relics)

    if "AbstractCard.CardType.ATTACK" in can_spawn or "getAttacks().size() > 0" in can_spawn:
        spawn_rules["required_deck_card_type"] = "ATTACK"
        spawn_rules["exclude_basic_cards"] = True
    elif "AbstractCard.CardType.SKILL" in can_spawn or "getSkills().size() > 0" in can_spawn:
        spawn_rules["required_deck_card_type"] = "SKILL"
        spawn_rules["exclude_basic_cards"] = True
    elif "CardHelper.hasCardType(AbstractCard.CardType.POWER)" in can_spawn or "getPowers().size() > 0" in can_spawn:
        spawn_rules["required_deck_card_type"] = "POWER"

    campfire_family = re.findall(r"instanceof\s+(\w+)", can_spawn)
    if campfire_family and "campfireRelicCount < 2" in can_spawn:
        spawn_rules["exclusive_with_relics"] = tuple(REVERSE_LEGACY_RUNTIME_RELIC_CLASS_MAP.get(name, name) for name in campfire_family)
        spawn_rules["exclusive_relic_limit"] = 2
    return spawn_rules


def _build_truth_sources(
    *,
    class_name: str,
    source_path: Path,
    stateful_variants: tuple[OfficialRelicTextVariant, ...],
    ui_prompt_slots: tuple[int, ...],
    rng_notes: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "java_class": class_name,
        "java_source_path": str(source_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "name_sources": (
            f"desktop-1.0.jar:{ENG_RELICS_JSON_PATH}",
            f"desktop-1.0.jar:{ZHS_RELICS_JSON_PATH}",
        ),
        "default_description_source": "java:getUpdatedDescription",
        "stateful_description_sources": _dedupe_preserve_order([variant.source_method for variant in stateful_variants]),
        "ui_prompt_source": "java:ui_prompt_slots" if ui_prompt_slots else "",
        "rng_sources": rng_notes,
    }


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
    eng_parts = [str(part or "") for part in eng_entry.get("DESCRIPTIONS", []) or []]
    zhs_parts = [str(part or "") for part in zhs_entry.get("DESCRIPTIONS", []) or []]

    default_description_en, default_slots_en = _resolve_method_expression(
        source_text,
        "getUpdatedDescription",
        eng_parts,
        str(eng_entry.get("NAME", "") or official_id),
        cn=False,
    )
    default_description_zhs, default_slots_zhs = _resolve_method_expression(
        source_text,
        "getUpdatedDescription",
        zhs_parts,
        str(zhs_entry.get("NAME", "") or eng_entry.get("NAME", "") or runtime_id),
        cn=True,
    )

    if not default_description_en:
        default_description_en = _sanitize_localized_text(eng_parts[0] if eng_parts else "", cn=False)
    if not default_description_zhs:
        default_description_zhs = _sanitize_localized_text(zhs_parts[0] if zhs_parts else "", cn=True)

    stateful_variants = _extract_assignment_variants(
        source_text,
        eng_parts,
        zhs_parts,
        str(eng_entry.get("NAME", "") or official_id),
        str(zhs_entry.get("NAME", "") or eng_entry.get("NAME", "") or runtime_id),
        default_en=default_description_en,
        default_zhs=default_description_zhs,
    )
    ui_prompt_slots = _extract_ui_prompt_slots(source_text)
    rng_notes = _extract_rng_notes(source_text)
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
        legacy_ids=_dedupe_preserve_order([str(item) for item in legacy_ids if str(item).strip()]),
        spawn_rules=_extract_spawn_rules(source_text),
        initial_counter=_extract_initial_counter(source_text, class_name),
        depletion_rules=_extract_depletion_rules(source_text),
        name_en=str(eng_entry.get("NAME", "") or ""),
        name_zhs=str(zhs_entry.get("NAME", "") or ""),
        description_en_parts=tuple(eng_parts),
        description_zhs_parts=tuple(zhs_parts),
        description_en=default_description_en,
        description_zhs=default_description_zhs,
        default_description_en=default_description_en,
        default_description_zhs=default_description_zhs,
        description_slots_used=_dedupe_preserve_order(list(default_slots_en) + list(default_slots_zhs)),
        stateful_description_variants=stateful_variants,
        ui_prompt_slots=ui_prompt_slots,
        flavor_en=_sanitize_localized_text(eng_entry.get("FLAVOR", ""), cn=False),
        flavor_zhs=_sanitize_localized_text(zhs_entry.get("FLAVOR", ""), cn=True),
        source_methods=_extract_source_methods(source_text),
        rng_notes=rng_notes,
        truth_sources=_build_truth_sources(
            class_name=class_name,
            source_path=source_path,
            stateful_variants=stateful_variants,
            ui_prompt_slots=ui_prompt_slots,
            rng_notes=rng_notes,
        ),
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
        eng_parts = [str(part or "") for part in eng_localized[official_id].get("DESCRIPTIONS", []) or []]
        zhs_parts = [str(part or "") for part in zhs_localized.get(official_id, {}).get("DESCRIPTIONS", []) or []]
        default_description_en = _sanitize_localized_text(eng_parts[0] if eng_parts else "", cn=False)
        default_description_zhs = _sanitize_localized_text(zhs_parts[0] if zhs_parts else "", cn=True)
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
            description_en_parts=tuple(eng_parts),
            description_zhs_parts=tuple(zhs_parts),
            description_en=default_description_en,
            description_zhs=default_description_zhs,
            default_description_en=default_description_en,
            default_description_zhs=default_description_zhs,
            description_slots_used=(0,) if eng_parts or zhs_parts else tuple(),
            stateful_description_variants=tuple(),
            ui_prompt_slots=tuple(),
            flavor_en=_sanitize_localized_text(eng_localized[official_id].get("FLAVOR", ""), cn=False),
            flavor_zhs=_sanitize_localized_text(zhs_localized.get(official_id, {}).get("FLAVOR", ""), cn=True),
            source_methods=tuple(),
            rng_notes=tuple(),
            truth_sources={
                "name_sources": (
                    f"desktop-1.0.jar:{ENG_RELICS_JSON_PATH}",
                    f"desktop-1.0.jar:{ZHS_RELICS_JSON_PATH}",
                ),
                "default_description_source": "localization_only",
                "stateful_description_sources": tuple(),
                "ui_prompt_source": "",
                "rng_sources": tuple(),
            },
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
