from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


TRANSLATION_POLICY_SCHEMA_VERSION = 1
TRANSLATION_POLICY_PATH = Path(__file__).resolve().parents[1] / "data" / "cli_translation_provenance.json"

VISIBLE_ENTITY_TYPES = {
    "card",
    "relic",
    "potion",
    "power",
    "monster",
    "event",
    "room_type",
    "ui_term",
}

ALIGNMENT_STATUSES = {
    "exact_match",
    "approved_alias",
    "wiki_missing",
    "needs_review",
    "likely_wrong_translation",
}


def _canonical_entity_id(entity_type: str, entity_id: str) -> str:
    canonical_type = str(entity_type or "").strip()
    canonical_id = str(entity_id or "").strip()
    if canonical_type != "event" or not canonical_id:
        return canonical_id
    try:
        from sts_py.engine.run.events import _resolve_event_key
    except Exception:
        return canonical_id
    return str(_resolve_event_key(canonical_id) or canonical_id)


@dataclass(frozen=True)
class TranslationPolicyEntry:
    entity_type: str
    entity_id: str
    runtime_name_cn: str
    reference_source: str
    alignment_status: str
    huiji_page_or_title: str
    approved_alias_note: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "TranslationPolicyEntry":
        entity_type = str(data.get("entity_type", "") or "").strip()
        entity_id = _canonical_entity_id(entity_type, str(data.get("entity_id", "") or "").strip())
        alignment_status = str(data.get("alignment_status", "") or "").strip()
        if entity_type not in VISIBLE_ENTITY_TYPES:
            raise ValueError(f"unknown translation policy entity_type: {entity_type!r}")
        if alignment_status not in ALIGNMENT_STATUSES:
            raise ValueError(f"unknown translation policy alignment_status: {alignment_status!r}")
        return cls(
            entity_type=entity_type,
            entity_id=entity_id,
            runtime_name_cn=str(data.get("runtime_name_cn", "") or ""),
            reference_source=str(data.get("reference_source", "") or ""),
            alignment_status=alignment_status,
            huiji_page_or_title=str(data.get("huiji_page_or_title", "") or ""),
            approved_alias_note=str(data.get("approved_alias_note", "") or ""),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "runtime_name_cn": self.runtime_name_cn,
            "reference_source": self.reference_source,
            "alignment_status": self.alignment_status,
            "huiji_page_or_title": self.huiji_page_or_title,
            "approved_alias_note": self.approved_alias_note,
        }


def _empty_policy_bundle() -> dict[str, object]:
    return {
        "schema_version": TRANSLATION_POLICY_SCHEMA_VERSION,
        "records": [],
    }


@lru_cache(maxsize=1)
def load_translation_policy_bundle() -> dict[str, object]:
    if not TRANSLATION_POLICY_PATH.exists():
        return _empty_policy_bundle()
    payload = json.loads(TRANSLATION_POLICY_PATH.read_text(encoding="utf-8"))
    schema_version = int(payload.get("schema_version", 0) or 0)
    if schema_version != TRANSLATION_POLICY_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported translation policy schema_version {schema_version}; "
            f"expected {TRANSLATION_POLICY_SCHEMA_VERSION}"
        )
    records = [TranslationPolicyEntry.from_dict(record).to_dict() for record in payload.get("records", [])]
    return {
        "schema_version": schema_version,
        "records": records,
    }


@lru_cache(maxsize=1)
def load_translation_policy_entries() -> dict[tuple[str, str], TranslationPolicyEntry]:
    entries: dict[tuple[str, str], TranslationPolicyEntry] = {}
    for record in load_translation_policy_bundle().get("records", []):
        entry = TranslationPolicyEntry.from_dict(dict(record))
        entries[(entry.entity_type, entry.entity_id)] = entry
    return entries


def get_translation_policy_entry(entity_type: str, entity_id: str) -> TranslationPolicyEntry | None:
    canonical_type = str(entity_type)
    canonical_id = _canonical_entity_id(canonical_type, str(entity_id))
    return load_translation_policy_entries().get((canonical_type, canonical_id))


def translation_policy_entity_ids_by_type() -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for entry in load_translation_policy_entries().values():
        grouped.setdefault(entry.entity_type, []).append(entry.entity_id)
    return {entity_type: sorted(set(values)) for entity_type, values in grouped.items()}
