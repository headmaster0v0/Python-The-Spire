from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sts_py.engine.content.cards_min import ALL_CARD_DEFS, CARD_ID_ALIASES


OFFICIAL_CARD_STRINGS_PATH = Path(__file__).resolve().parents[2] / "data" / "official_card_strings.json"
OFFICIAL_CARD_TRANSLATION_SOURCE = "desktop-1.0.jar:localization/zhs/cards.json"
OFFICIAL_CARD_DESCRIPTION_SOURCE = "desktop-1.0.jar:localization/eng/cards.json + localization/zhs/cards.json"


def _normalize_lookup_token(text: str | None) -> str:
    return re.sub(r"[^0-9a-z]+", "", str(text or "").lower())


def _strip_runtime_variant(card_id: str) -> str:
    candidate = str(card_id or "").strip()
    if not candidate:
        return ""
    if candidate in ALL_CARD_DEFS:
        return candidate
    if "#" in candidate:
        candidate = candidate.split("#", 1)[0]
        if candidate in ALL_CARD_DEFS:
            return candidate
    if re.search(r"\+\d+$", candidate):
        base_candidate = re.sub(r"\+\d+$", "", candidate)
        if base_candidate in ALL_CARD_DEFS:
            return base_candidate
    if candidate.endswith("+"):
        base_candidate = candidate[:-1]
        if base_candidate in ALL_CARD_DEFS:
            return base_candidate
    return candidate


def _humanize_identifier(identifier: str) -> str:
    if not identifier:
        return ""
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", identifier.replace("_", " "))
    return re.sub(r"\s+", " ", spaced).strip()


def _inverse_card_aliases() -> dict[str, list[str]]:
    inverse: dict[str, list[str]] = {}
    for alias, runtime_id in CARD_ID_ALIASES.items():
        inverse.setdefault(runtime_id, []).append(alias)
    return inverse


@dataclass(frozen=True)
class OfficialCardStrings:
    runtime_id: str
    official_key: str
    java_class: str
    name_en: str
    name_zhs: str
    description_en: str
    description_zhs: str
    upgrade_description_en: str
    upgrade_description_zhs: str
    extended_description_en: tuple[str, ...]
    extended_description_zhs: tuple[str, ...]
    translation_source: str = OFFICIAL_CARD_TRANSLATION_SOURCE
    description_source: str = OFFICIAL_CARD_DESCRIPTION_SOURCE
    variant_kind: str = "base"

    @classmethod
    def from_dict(cls, runtime_id: str, data: dict[str, object]) -> "OfficialCardStrings":
        return cls(
            runtime_id=runtime_id,
            official_key=str(data.get("official_key", runtime_id) or runtime_id),
            java_class=str(data.get("java_class", runtime_id) or runtime_id),
            name_en=str(data.get("name_en", "") or ""),
            name_zhs=str(data.get("name_zhs", "") or ""),
            description_en=str(data.get("description_en", "") or ""),
            description_zhs=str(data.get("description_zhs", "") or ""),
            upgrade_description_en=str(data.get("upgrade_description_en", "") or ""),
            upgrade_description_zhs=str(data.get("upgrade_description_zhs", "") or ""),
            extended_description_en=tuple(str(item or "") for item in data.get("extended_description_en", []) or []),
            extended_description_zhs=tuple(str(item or "") for item in data.get("extended_description_zhs", []) or []),
            translation_source=str(data.get("translation_source", OFFICIAL_CARD_TRANSLATION_SOURCE) or OFFICIAL_CARD_TRANSLATION_SOURCE),
            description_source=str(data.get("description_source", OFFICIAL_CARD_DESCRIPTION_SOURCE) or OFFICIAL_CARD_DESCRIPTION_SOURCE),
            variant_kind=str(data.get("variant_kind", "base") or "base"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "official_key": self.official_key,
            "java_class": self.java_class,
            "name_en": self.name_en,
            "name_zhs": self.name_zhs,
            "description_en": self.description_en,
            "description_zhs": self.description_zhs,
            "upgrade_description_en": self.upgrade_description_en,
            "upgrade_description_zhs": self.upgrade_description_zhs,
            "extended_description_en": list(self.extended_description_en),
            "extended_description_zhs": list(self.extended_description_zhs),
            "translation_source": self.translation_source,
            "description_source": self.description_source,
            "variant_kind": self.variant_kind,
        }


def _parse_card_strings_key(java_file: Path | None) -> str | None:
    if java_file is None or not java_file.exists():
        return None
    text = java_file.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r'getCardStrings\("([^"]+)"\)', text)
    if match:
        return match.group(1)
    return None


def _build_card_string_lookup(records: dict[str, dict[str, object]]) -> dict[str, tuple[str, dict[str, object]]]:
    lookup: dict[str, tuple[str, dict[str, object]]] = {}
    for official_key, record in records.items():
        for token in {official_key, str(record.get("NAME", "") or "")}:
            normalized = _normalize_lookup_token(token)
            if not normalized or normalized in lookup:
                continue
            lookup[normalized] = (official_key, record)
    return lookup


def _official_lookup_candidates(
    runtime_id: str,
    *,
    java_class: str,
    official_key: str | None,
) -> list[str]:
    inverse_aliases = _inverse_card_aliases()
    candidates: list[str] = []
    for candidate in (
        official_key,
        java_class,
        runtime_id,
        _humanize_identifier(runtime_id),
        _humanize_identifier(java_class),
        _humanize_identifier(str(official_key or "")),
    ):
        candidate_text = str(candidate or "").strip()
        if candidate_text and candidate_text not in candidates:
            candidates.append(candidate_text)
    for alias in inverse_aliases.get(runtime_id, []):
        for candidate in (alias, _humanize_identifier(alias)):
            candidate_text = str(candidate or "").strip()
            if candidate_text and candidate_text not in candidates:
                candidates.append(candidate_text)
    if runtime_id == "Burn+":
        for candidate in ("Burn", "Burn+", "Burn +"):
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def _lookup_card_record(
    lookup: dict[str, tuple[str, dict[str, object]]],
    runtime_id: str,
    *,
    java_class: str,
    official_key: str | None,
) -> tuple[str, dict[str, object]]:
    for candidate in _official_lookup_candidates(runtime_id, java_class=java_class, official_key=official_key):
        match = lookup.get(_normalize_lookup_token(candidate))
        if match is not None:
            return match
    raise KeyError(f"could not resolve official card strings for {runtime_id}")


def build_official_card_strings_snapshot(
    jar_path: Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, object]:
    resolved_repo_root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[3]

    with zipfile.ZipFile(jar_path) as jar:
        eng_cards = json.loads(jar.read("localization/eng/cards.json").decode("utf-8"))
        zhs_cards = json.loads(jar.read("localization/zhs/cards.json").decode("utf-8-sig"))

    eng_lookup = _build_card_string_lookup(dict(eng_cards))
    zhs_lookup = _build_card_string_lookup(dict(zhs_cards))
    records: dict[str, object] = {}

    # Import lazily to avoid making the runtime loader depend on wiki_audit.
    from sts_py.tools import wiki_audit

    for runtime_id in sorted(ALL_CARD_DEFS):
        java_class = wiki_audit._resolve_java_card_class_name(runtime_id)
        java_file = wiki_audit._java_card_file(resolved_repo_root, runtime_id)
        official_key = _parse_card_strings_key(java_file)
        eng_key, eng_record = _lookup_card_record(
            eng_lookup,
            runtime_id,
            java_class=java_class,
            official_key=official_key,
        )
        zhs_key, zhs_record = _lookup_card_record(
            zhs_lookup,
            runtime_id,
            java_class=java_class,
            official_key=official_key or eng_key,
        )
        variant_kind = "upgrade_variant" if runtime_id == "Burn+" else "base"
        records[runtime_id] = OfficialCardStrings(
            runtime_id=runtime_id,
            official_key=str(official_key or eng_key or zhs_key),
            java_class=str(java_class),
            name_en=str(eng_record.get("NAME", "") or ""),
            name_zhs=str(zhs_record.get("NAME", "") or ""),
            description_en=str(eng_record.get("DESCRIPTION", "") or ""),
            description_zhs=str(zhs_record.get("DESCRIPTION", "") or ""),
            upgrade_description_en=str(eng_record.get("UPGRADE_DESCRIPTION", "") or ""),
            upgrade_description_zhs=str(zhs_record.get("UPGRADE_DESCRIPTION", "") or ""),
            extended_description_en=tuple(str(item or "") for item in eng_record.get("EXTENDED_DESCRIPTION", []) or []),
            extended_description_zhs=tuple(str(item or "") for item in zhs_record.get("EXTENDED_DESCRIPTION", []) or []),
            variant_kind=variant_kind,
        ).to_dict()

    return {
        "schema_version": 1,
        "jar_path": str(jar_path),
        "records": records,
    }


@lru_cache(maxsize=1)
def load_official_card_strings() -> dict[str, OfficialCardStrings]:
    payload = json.loads(OFFICIAL_CARD_STRINGS_PATH.read_text(encoding="utf-8"))
    records = payload.get("records", {})
    return {
        str(runtime_id): OfficialCardStrings.from_dict(str(runtime_id), dict(record))
        for runtime_id, record in records.items()
    }


def get_official_card_strings(card_id: str | None) -> OfficialCardStrings | None:
    if card_id is None:
        return None
    canonical = _strip_runtime_variant(str(card_id))
    canonical = CARD_ID_ALIASES.get(canonical, canonical)
    records = load_official_card_strings()
    if canonical in records:
        return records[canonical]
    if str(card_id) in records:
        return records[str(card_id)]
    return None


__all__ = [
    "OFFICIAL_CARD_DESCRIPTION_SOURCE",
    "OFFICIAL_CARD_STRINGS_PATH",
    "OFFICIAL_CARD_TRANSLATION_SOURCE",
    "OfficialCardStrings",
    "build_official_card_strings_snapshot",
    "get_official_card_strings",
    "load_official_card_strings",
]
