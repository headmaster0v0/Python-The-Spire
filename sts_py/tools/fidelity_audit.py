from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from sts_py.engine.run.run_engine import RunEngine
from sts_py.terminal.render import (
    render_shop_card_lines,
    render_shop_potion_lines,
    render_shop_relic_lines,
)
from sts_py.tools.card_truth_matrix import HIGH_RISK_CARD_IDS, build_card_truth_matrix, load_card_truth_matrix
from sts_py.tools import wiki_audit
from sts_py.tools.fidelity_proof import (
    FIDELITY_PROOF_MATRIX_PATH,
    NONCARD_ENTITY_TYPES,
    build_fidelity_proof_matrix_from_raw_snapshot,
    load_fidelity_proof_matrix,
)


KNOWN_APPROXIMATIONS_PATH = Path(__file__).resolve().parents[1] / "data" / "known_approximations.json"
SURFACE_ENTITY_TYPES = {"relic", "potion", "power", "monster", "event", "room_type", "ui_term"}
PLACEHOLDER_MARKERS = ("placeholder", "randomrelic", "todo", "not implemented")
MOJIBAKE_MARKERS = ("\ufffd", "绗?", "妤煎眰", "鐢熷懡", "閲戝竵")


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _is_presentable_surface_text(text: str | None) -> bool:
    candidate = str(text or "").strip()
    if not candidate:
        return False
    lowered = candidate.lower()
    return not any(marker in candidate for marker in MOJIBAKE_MARKERS) and not any(
        marker in lowered for marker in PLACEHOLDER_MARKERS
    )


def _append_blocker(
    blockers: list[dict[str, str]],
    *,
    lane: str,
    entity_type: str,
    entity_id: str,
    issue: str,
    detail: str = "",
) -> None:
    blockers.append(
        {
            "lane": lane,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "issue": issue,
            "detail": detail,
        }
    )


def load_known_approximations(repo_root: Path | str | None = None) -> dict[str, Any]:
    path = KNOWN_APPROXIMATIONS_PATH
    if repo_root is not None:
        candidate = Path(repo_root) / "sts_py" / "data" / "known_approximations.json"
        if candidate.exists():
            path = candidate
    if not path.exists():
        return {"schema_version": 1, "items": []}
    return json.loads(path.read_text(encoding="utf-8"))


def build_runtime_surface_audit(repo_root: Path | str, *, raw_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root)
    snapshot = raw_snapshot or wiki_audit.build_cli_raw_snapshot(repo_root, enable_network=False)
    blockers: list[dict[str, str]] = []
    by_type: Counter[str] = Counter()

    for record in snapshot["records"]:
        entity_type = str(record["entity_type"])
        if entity_type not in SURFACE_ENTITY_TYPES:
            continue
        entity_id = str(record["entity_id"])
        by_type[entity_type] += 1

        runtime_name_cn = str(record.get("runtime_name_cn", "") or "")
        if not _is_presentable_surface_text(runtime_name_cn):
            _append_blocker(
                blockers,
                lane="surface",
                entity_type=entity_type,
                entity_id=entity_id,
                issue="bad_runtime_name_cn",
                detail=runtime_name_cn,
            )
        elif not _contains_cjk(runtime_name_cn):
            _append_blocker(
                blockers,
                lane="surface",
                entity_type=entity_type,
                entity_id=entity_id,
                issue="non_localized_runtime_name_cn",
                detail=runtime_name_cn,
            )

        runtime_desc = str(record.get("runtime_desc_runtime", "") or "")
        if entity_type in {"relic", "potion", "monster", "event"} and not _is_presentable_surface_text(runtime_desc):
            _append_blocker(
                blockers,
                lane="surface",
                entity_type=entity_type,
                entity_id=entity_id,
                issue="bad_runtime_desc",
                detail=runtime_desc,
            )

        runtime_facts = dict(record.get("runtime_facts") or {})
        if entity_type == "event":
            choice_count = int(runtime_facts.get("choice_count", 0) or 0)
            if choice_count <= 0:
                _append_blocker(
                    blockers,
                    lane="surface",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    issue="missing_event_choices",
                )
        elif entity_type == "monster":
            if not list(runtime_facts.get("sample_intents") or []):
                _append_blocker(
                    blockers,
                    lane="surface",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    issue="missing_monster_sample_intents",
                )

    engine = RunEngine.create("PHASE267FIDELITYSHOP", ascension=0)
    engine._enter_shop()
    shop = engine.get_shop()
    if shop is None:
        _append_blocker(
            blockers,
            lane="shop_surface",
            entity_type="shop",
            entity_id="default_shop",
            issue="shop_failed_to_open",
        )
        shop_surface = {"card_line_count": 0, "relic_line_count": 0, "potion_line_count": 0}
    else:
        card_lines, _ = render_shop_card_lines(shop.get_available_cards())
        relic_lines = render_shop_relic_lines(shop.get_available_relics())
        potion_lines = render_shop_potion_lines(shop.get_available_potions())
        shop_surface = {
            "card_line_count": len(card_lines),
            "relic_line_count": len(relic_lines),
            "potion_line_count": len(potion_lines),
        }
        for lane, lines in {
            "shop_cards": card_lines,
            "shop_relics": relic_lines,
            "shop_potions": potion_lines,
        }.items():
            if not lines:
                _append_blocker(
                    blockers,
                    lane="shop_surface",
                    entity_type="shop",
                    entity_id=lane,
                    issue="empty_render_surface",
                )
                continue
            for line in lines:
                if not _is_presentable_surface_text(line):
                    _append_blocker(
                        blockers,
                        lane="shop_surface",
                        entity_type="shop",
                        entity_id=lane,
                        issue="bad_render_line",
                        detail=line,
                    )

    return {
        "summary": {
            "by_entity_type": dict(sorted(by_type.items())),
            "blocker_count": len(blockers),
            "shop_surface": shop_surface,
        },
        "blockers": blockers,
    }


def _translation_alias_is_explicitly_allowed(finding: dict[str, Any]) -> bool:
    if str(finding.get("status", "") or "") != "approved_alias":
        return False
    runtime_name_cn = str(finding.get("runtime_name_cn", "") or "").strip()
    huiji_title = str(finding.get("huiji_page_or_title", "") or "").strip()
    if runtime_name_cn and huiji_title == f"{runtime_name_cn}（能力）":
        return True
    return bool(str(finding.get("approved_alias_note", "") or "").strip())


def build_translation_truth_audit(audit_bundle: dict[str, Any]) -> dict[str, Any]:
    findings = list(audit_bundle.get("translation_audit", {}).get("findings") or [])
    blockers: list[dict[str, str]] = []
    by_status: Counter[str] = Counter()

    for finding in findings:
        entity_type = str(finding.get("entity_type", "") or "")
        entity_id = str(finding.get("entity_id", "") or "")
        status = str(finding.get("status", "") or "")
        runtime_name_cn = str(finding.get("runtime_name_cn", "") or "")
        by_status[status] += 1

        if not _is_presentable_surface_text(runtime_name_cn):
            _append_blocker(
                blockers,
                lane="translation_truth",
                entity_type=entity_type,
                entity_id=entity_id,
                issue="non_presentable_runtime_name_cn",
                detail=runtime_name_cn,
            )
            continue

        if status == "exact_match":
            continue
        if status == "approved_alias":
            if _translation_alias_is_explicitly_allowed(finding):
                continue
            _append_blocker(
                blockers,
                lane="translation_truth",
                entity_type=entity_type,
                entity_id=entity_id,
                issue="unapproved_alias",
                detail=str(finding.get("huiji_page_or_title", "") or ""),
            )
            continue
        if status == "wiki_missing":
            continue
        if not _contains_cjk(runtime_name_cn):
            _append_blocker(
                blockers,
                lane="translation_truth",
                entity_type=entity_type,
                entity_id=entity_id,
                issue="non_localized_runtime_name_cn",
                detail=runtime_name_cn,
            )
            continue
        _append_blocker(
            blockers,
            lane="translation_truth",
            entity_type=entity_type,
            entity_id=entity_id,
            issue=f"translation_status:{status or 'unknown'}",
            detail=str(finding.get("note", "") or ""),
        )

    return {
        "summary": {
            "by_status": dict(sorted(by_status.items())),
            "exact_match_count": by_status.get("exact_match", 0),
            "approved_alias_count": by_status.get("approved_alias", 0),
            "local_fallback_count": by_status.get("wiki_missing", 0),
            "blocker_count": len(blockers),
        },
        "blockers": blockers,
    }


def _matrix_entity_key(entity_type: str, entity_id: str) -> str:
    return f"{entity_type}:{entity_id}"


def _matrix_entry_map(matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for entry in list(matrix.get("entities") or []):
        entity_type = str(entry.get("entity_type", ""))
        entity_id = str(entry.get("entity_id", ""))
        if not entity_type or not entity_id:
            continue
        mapping[_matrix_entity_key(entity_type, entity_id)] = dict(entry)
    return mapping


def _card_matrix_entry_map(matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for entry in list(matrix.get("entities") or []):
        runtime_id = str(entry.get("runtime_id", "") or "")
        if not runtime_id:
            continue
        mapping[runtime_id] = dict(entry)
    return mapping


def build_noncard_truth_audit(repo_root: Path | str, *, raw_snapshot: dict[str, Any]) -> dict[str, Any]:
    repo_root = Path(repo_root)
    expected_matrix = build_fidelity_proof_matrix_from_raw_snapshot(raw_snapshot)
    checked_in_matrix = load_fidelity_proof_matrix(repo_root)
    expected_entries = _matrix_entry_map(expected_matrix)
    checked_in_entries = _matrix_entry_map(checked_in_matrix)

    uncovered: list[dict[str, Any]] = []
    signature_mismatches: list[dict[str, Any]] = []
    stale_entries: list[dict[str, Any]] = []
    missing_family_test_refs: list[dict[str, Any]] = []
    missing_dedicated_test_refs: list[dict[str, Any]] = []

    checked_in_family_tests = dict(checked_in_matrix.get("family_tests") or {})
    checked_in_dedicated_tests = dict(checked_in_matrix.get("dedicated_tests") or {})
    by_type: Counter[str] = Counter()

    for record in list(raw_snapshot.get("records") or []):
        entity_type = str(record.get("entity_type", ""))
        if entity_type not in NONCARD_ENTITY_TYPES:
            continue
        entity_id = str(record.get("entity_id", ""))
        entity_key = _matrix_entity_key(entity_type, entity_id)
        by_type[entity_type] += 1
        expected_entry = expected_entries[entity_key]
        checked_in_entry = checked_in_entries.get(entity_key)

        if checked_in_entry is None:
            uncovered.append(
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "issue": "missing_matrix_entry",
                }
            )
            continue

        expected_family_ids = sorted(str(item) for item in expected_entry.get("family_ids") or [])
        checked_in_family_ids = sorted(str(item) for item in checked_in_entry.get("family_ids") or [])
        expected_kind = str(expected_entry.get("proof_kind", "") or "")
        checked_in_kind = str(checked_in_entry.get("proof_kind", "") or "")

        if not checked_in_family_ids:
            uncovered.append(
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "issue": "empty_family_ids",
                }
            )

        if expected_family_ids != checked_in_family_ids or expected_kind != checked_in_kind:
            signature_mismatches.append(
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "expected_family_ids": expected_family_ids,
                    "checked_in_family_ids": checked_in_family_ids,
                    "expected_proof_kind": expected_kind,
                    "checked_in_proof_kind": checked_in_kind,
                }
            )

        for family_id in checked_in_family_ids:
            if family_id not in checked_in_family_tests:
                missing_family_test_refs.append(
                    {
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "family_id": family_id,
                    }
                )

        if checked_in_kind == "dedicated" and entity_key not in checked_in_dedicated_tests:
            missing_dedicated_test_refs.append(
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                }
            )

    for entity_key, entry in sorted(checked_in_entries.items()):
        if entity_key in expected_entries:
            continue
        stale_entries.append(
            {
                "entity_type": str(entry.get("entity_type", "")),
                "entity_id": str(entry.get("entity_id", "")),
                "issue": "stale_matrix_entry",
            }
        )

    registry_mismatches = {
        "family_tests": checked_in_family_tests != dict(expected_matrix.get("family_tests") or {}),
        "dedicated_tests": checked_in_dedicated_tests != dict(expected_matrix.get("dedicated_tests") or {}),
    }
    uncovered_count = len(uncovered) + len(missing_family_test_refs) + len(missing_dedicated_test_refs)

    return {
        "summary": {
            "by_entity_type": dict(sorted(by_type.items())),
            "entity_count": sum(by_type.values()),
            "matrix_entry_count": len(checked_in_entries),
            "noncard_proof_uncovered": uncovered_count,
            "signature_mismatches": len(signature_mismatches),
            "stale_matrix_entries": len(stale_entries),
            "family_test_registry_mismatch": int(registry_mismatches["family_tests"]),
            "dedicated_test_registry_mismatch": int(registry_mismatches["dedicated_tests"]),
            "blocker_count": uncovered_count
            + len(signature_mismatches)
            + len(stale_entries)
            + int(registry_mismatches["family_tests"])
            + int(registry_mismatches["dedicated_tests"]),
        },
        "matrix_path": str((repo_root / "sts_py" / "data" / "fidelity_proof_matrix.json").resolve()),
        "expected_matrix": expected_matrix,
        "checked_in_matrix": checked_in_matrix,
        "uncovered": uncovered,
        "signature_mismatches": signature_mismatches,
        "stale_entries": stale_entries,
        "missing_family_test_refs": missing_family_test_refs,
        "missing_dedicated_test_refs": missing_dedicated_test_refs,
        "registry_mismatches": registry_mismatches,
    }


def build_card_truth_audit(
    repo_root: Path | str,
    *,
    raw_snapshot: dict[str, Any],
    audit_bundle: dict[str, Any],
) -> dict[str, Any]:
    repo_root = Path(repo_root)
    expected_matrix = build_card_truth_matrix(repo_root, raw_snapshot=raw_snapshot, audit_bundle=audit_bundle)
    checked_in_matrix = load_card_truth_matrix(repo_root)
    expected_entries = _card_matrix_entry_map(expected_matrix)
    checked_in_entries = _card_matrix_entry_map(checked_in_matrix)

    uncovered: list[dict[str, Any]] = []
    signature_mismatches: list[dict[str, Any]] = []
    stale_entries: list[dict[str, Any]] = []
    missing_family_test_refs: list[dict[str, Any]] = []
    missing_dedicated_test_refs: list[dict[str, Any]] = []

    checked_in_family_tests = dict(checked_in_matrix.get("family_tests") or {})
    checked_in_dedicated_tests = dict(checked_in_matrix.get("dedicated_tests") or {})
    checked_in_high_risk = sorted(str(item) for item in checked_in_matrix.get("high_risk_card_ids") or [])
    expected_high_risk = sorted(str(item) for item in expected_matrix.get("high_risk_card_ids") or [])

    for card_id, expected_entry in sorted(expected_entries.items()):
        checked_in_entry = checked_in_entries.get(card_id)
        if checked_in_entry is None:
            uncovered.append({"card_id": card_id, "issue": "missing_matrix_entry"})
            continue

        expected_family_ids = sorted(str(item) for item in expected_entry.get("family_ids") or [])
        checked_in_family_ids = sorted(str(item) for item in checked_in_entry.get("family_ids") or [])
        expected_runtime_truth_kind = str(expected_entry.get("runtime_truth_kind", "") or "")
        checked_in_runtime_truth_kind = str(checked_in_entry.get("runtime_truth_kind", "") or "")
        expected_data_truth_kind = str(expected_entry.get("data_truth_kind", "") or "")
        checked_in_data_truth_kind = str(checked_in_entry.get("data_truth_kind", "") or "")

        if not list(checked_in_entry.get("data_proof_nodeids") or []):
            uncovered.append({"card_id": card_id, "issue": "missing_data_proof_nodeids"})
        if checked_in_runtime_truth_kind != "none" and not list(checked_in_entry.get("runtime_proof_nodeids") or []):
            uncovered.append({"card_id": card_id, "issue": "missing_runtime_proof_nodeids"})

        if (
            expected_family_ids != checked_in_family_ids
            or expected_runtime_truth_kind != checked_in_runtime_truth_kind
            or expected_data_truth_kind != checked_in_data_truth_kind
        ):
            signature_mismatches.append(
                {
                    "card_id": card_id,
                    "expected_family_ids": expected_family_ids,
                    "checked_in_family_ids": checked_in_family_ids,
                    "expected_runtime_truth_kind": expected_runtime_truth_kind,
                    "checked_in_runtime_truth_kind": checked_in_runtime_truth_kind,
                    "expected_data_truth_kind": expected_data_truth_kind,
                    "checked_in_data_truth_kind": checked_in_data_truth_kind,
                }
            )

        for family_id in checked_in_family_ids:
            if family_id not in checked_in_family_tests:
                missing_family_test_refs.append({"card_id": card_id, "family_id": family_id})

        if card_id in HIGH_RISK_CARD_IDS and f"card:{card_id}" not in checked_in_dedicated_tests:
            missing_dedicated_test_refs.append({"card_id": card_id, "issue": "missing_high_risk_dedicated_test"})

    for card_id in sorted(checked_in_entries):
        if card_id in expected_entries:
            continue
        stale_entries.append({"card_id": card_id, "issue": "stale_matrix_entry"})

    registry_mismatches = {
        "scenario_nodeids": dict(checked_in_matrix.get("scenario_nodeids") or {}) != dict(expected_matrix.get("scenario_nodeids") or {}),
        "family_tests": checked_in_family_tests != dict(expected_matrix.get("family_tests") or {}),
        "dedicated_tests": checked_in_dedicated_tests != dict(expected_matrix.get("dedicated_tests") or {}),
        "high_risk_card_ids": checked_in_high_risk != expected_high_risk,
    }
    uncovered_count = len(uncovered) + len(missing_family_test_refs) + len(missing_dedicated_test_refs)

    return {
        "summary": {
            "card_count": len(expected_entries),
            "matrix_entry_count": len(checked_in_entries),
            "card_proof_uncovered": uncovered_count,
            "signature_mismatches": len(signature_mismatches),
            "stale_matrix_entries": len(stale_entries),
            "scenario_registry_mismatch": int(registry_mismatches["scenario_nodeids"]),
            "family_test_registry_mismatch": int(registry_mismatches["family_tests"]),
            "dedicated_test_registry_mismatch": int(registry_mismatches["dedicated_tests"]),
            "high_risk_registry_mismatch": int(registry_mismatches["high_risk_card_ids"]),
            "blocker_count": uncovered_count
            + len(signature_mismatches)
            + len(stale_entries)
            + int(registry_mismatches["scenario_nodeids"])
            + int(registry_mismatches["family_tests"])
            + int(registry_mismatches["dedicated_tests"])
            + int(registry_mismatches["high_risk_card_ids"]),
        },
        "matrix_path": str((repo_root / "sts_py" / "data" / "card_truth_matrix.json").resolve()),
        "expected_matrix": expected_matrix,
        "checked_in_matrix": checked_in_matrix,
        "uncovered": uncovered,
        "signature_mismatches": signature_mismatches,
        "stale_entries": stale_entries,
        "missing_family_test_refs": missing_family_test_refs,
        "missing_dedicated_test_refs": missing_dedicated_test_refs,
        "registry_mismatches": registry_mismatches,
    }


def run_fidelity_audit(repo_root: Path | str) -> dict[str, Any]:
    repo_root = Path(repo_root)
    raw_snapshot = wiki_audit.build_cli_raw_snapshot(repo_root, enable_network=False)
    audit_bundle = wiki_audit.run_audit_from_raw_snapshot(raw_snapshot, repo_root=repo_root)
    known_approximations = load_known_approximations(repo_root)
    surface_audit = build_runtime_surface_audit(repo_root, raw_snapshot=raw_snapshot)
    translation_truth_audit = build_translation_truth_audit(audit_bundle)
    card_truth_audit = build_card_truth_audit(repo_root, raw_snapshot=raw_snapshot, audit_bundle=audit_bundle)
    noncard_truth_audit = build_noncard_truth_audit(repo_root, raw_snapshot=raw_snapshot)
    blockers = list(surface_audit["blockers"])
    blockers.extend(list(translation_truth_audit["blockers"]))

    for item in list(known_approximations.get("items") or []):
        _append_blocker(
            blockers,
            lane="known_approximations",
            entity_type=str(item.get("entity_type", "runtime")),
            entity_id=str(item.get("entity_id", "unknown")),
            issue=str(item.get("issue", "listed_approximation")),
            detail=str(item.get("detail", "")),
        )

    translation_summary = audit_bundle["translation_audit"]["summary"]
    mechanics_summary = audit_bundle["mechanics_audit"]["summary"]
    completeness_summary = audit_bundle["completeness_audit"]["summary"]

    if completeness_summary["missing_in_runtime"] != 0:
        _append_blocker(
            blockers,
            lane="wiki_audit",
            entity_type="card_surface",
            entity_id="missing_in_runtime",
            issue="missing_runtime_content",
            detail=str(completeness_summary["missing_in_runtime"]),
        )
    if mechanics_summary["runtime_source_mismatches"] != 0:
        _append_blocker(
            blockers,
            lane="wiki_audit",
            entity_type="card_truth",
            entity_id="runtime_source_mismatches",
            issue="card_static_truth_regressed",
            detail=str(mechanics_summary["runtime_source_mismatches"]),
        )
    if translation_summary["runtime_name_issue"]["ok"] != translation_summary["total"]:
        _append_blocker(
            blockers,
            lane="wiki_audit",
            entity_type="translation",
            entity_id="runtime_name_issue",
            issue="translation_runtime_name_issue",
            detail=str(translation_summary["runtime_name_issue"]),
        )

    for finding in list(card_truth_audit["uncovered"]):
        _append_blocker(
            blockers,
            lane="card_truth",
            entity_type="card",
            entity_id=str(finding.get("card_id", "unknown")),
            issue=str(finding.get("issue", "card_proof_uncovered")),
        )
    for finding in list(card_truth_audit["missing_family_test_refs"]):
        _append_blocker(
            blockers,
            lane="card_truth",
            entity_type="card",
            entity_id=str(finding.get("card_id", "unknown")),
            issue=f"missing_family_test_ref:{finding.get('family_id', '')}",
        )
    for finding in list(card_truth_audit["missing_dedicated_test_refs"]):
        _append_blocker(
            blockers,
            lane="card_truth",
            entity_type="card",
            entity_id=str(finding.get("card_id", "unknown")),
            issue=str(finding.get("issue", "missing_dedicated_test_ref")),
        )
    for finding in list(card_truth_audit["signature_mismatches"]):
        _append_blocker(
            blockers,
            lane="card_truth",
            entity_type="card",
            entity_id=str(finding.get("card_id", "unknown")),
            issue="proof_matrix_signature_mismatch",
        )
    for finding in list(card_truth_audit["stale_entries"]):
        _append_blocker(
            blockers,
            lane="card_truth",
            entity_type="card",
            entity_id=str(finding.get("card_id", "unknown")),
            issue="stale_matrix_entry",
        )
    if card_truth_audit["registry_mismatches"]["scenario_nodeids"]:
        _append_blocker(
            blockers,
            lane="card_truth",
            entity_type="proof_matrix",
            entity_id="scenario_nodeids",
            issue="scenario_registry_drift",
        )
    if card_truth_audit["registry_mismatches"]["family_tests"]:
        _append_blocker(
            blockers,
            lane="card_truth",
            entity_type="proof_matrix",
            entity_id="family_tests",
            issue="family_test_registry_drift",
        )
    if card_truth_audit["registry_mismatches"]["dedicated_tests"]:
        _append_blocker(
            blockers,
            lane="card_truth",
            entity_type="proof_matrix",
            entity_id="dedicated_tests",
            issue="dedicated_test_registry_drift",
        )
    if card_truth_audit["registry_mismatches"]["high_risk_card_ids"]:
        _append_blocker(
            blockers,
            lane="card_truth",
            entity_type="proof_matrix",
            entity_id="high_risk_card_ids",
            issue="high_risk_registry_drift",
        )

    for finding in list(noncard_truth_audit["uncovered"]):
        _append_blocker(
            blockers,
            lane="noncard_truth",
            entity_type=str(finding.get("entity_type", "runtime")),
            entity_id=str(finding.get("entity_id", "unknown")),
            issue=str(finding.get("issue", "noncard_proof_uncovered")),
        )
    for finding in list(noncard_truth_audit["missing_family_test_refs"]):
        _append_blocker(
            blockers,
            lane="noncard_truth",
            entity_type=str(finding.get("entity_type", "runtime")),
            entity_id=str(finding.get("entity_id", "unknown")),
            issue=f"missing_family_test_ref:{finding.get('family_id', '')}",
        )
    for finding in list(noncard_truth_audit["missing_dedicated_test_refs"]):
        _append_blocker(
            blockers,
            lane="noncard_truth",
            entity_type=str(finding.get("entity_type", "runtime")),
            entity_id=str(finding.get("entity_id", "unknown")),
            issue="missing_dedicated_test_ref",
        )
    for finding in list(noncard_truth_audit["signature_mismatches"]):
        _append_blocker(
            blockers,
            lane="noncard_truth",
            entity_type=str(finding.get("entity_type", "runtime")),
            entity_id=str(finding.get("entity_id", "unknown")),
            issue="proof_matrix_signature_mismatch",
        )
    for finding in list(noncard_truth_audit["stale_entries"]):
        _append_blocker(
            blockers,
            lane="noncard_truth",
            entity_type=str(finding.get("entity_type", "runtime")),
            entity_id=str(finding.get("entity_id", "unknown")),
            issue="stale_matrix_entry",
        )
    if noncard_truth_audit["registry_mismatches"]["family_tests"]:
        _append_blocker(
            blockers,
            lane="noncard_truth",
            entity_type="proof_matrix",
            entity_id="family_tests",
            issue="family_test_registry_drift",
            detail=str(FIDELITY_PROOF_MATRIX_PATH),
        )
    if noncard_truth_audit["registry_mismatches"]["dedicated_tests"]:
        _append_blocker(
            blockers,
            lane="noncard_truth",
            entity_type="proof_matrix",
            entity_id="dedicated_tests",
            issue="dedicated_test_registry_drift",
            detail=str(FIDELITY_PROOF_MATRIX_PATH),
        )

    return {
        "summary": {
            "known_approximations_count": len(list(known_approximations.get("items") or [])),
            "blocker_count": len(blockers),
            "surface_blocker_count": len(surface_audit["blockers"]),
            "translation_truth_blocker_count": len(translation_truth_audit["blockers"]),
            "card_proof_uncovered": card_truth_audit["summary"]["card_proof_uncovered"],
            "card_signature_mismatches": card_truth_audit["summary"]["signature_mismatches"],
            "noncard_proof_uncovered": noncard_truth_audit["summary"]["noncard_proof_uncovered"],
            "noncard_signature_mismatches": noncard_truth_audit["summary"]["signature_mismatches"],
            "wiki_audit": {
                "missing_in_runtime": completeness_summary["missing_in_runtime"],
                "runtime_source_mismatches": mechanics_summary["runtime_source_mismatches"],
                "runtime_name_issue_ok": translation_summary["runtime_name_issue"]["ok"],
                "translation_total": translation_summary["total"],
            },
        },
        "known_approximations": known_approximations,
        "surface_audit": surface_audit,
        "translation_truth_audit": translation_truth_audit,
        "card_truth_audit": card_truth_audit,
        "noncard_truth_audit": noncard_truth_audit,
        "wiki_audit": audit_bundle,
        "blockers": blockers,
    }


__all__ = [
    "KNOWN_APPROXIMATIONS_PATH",
    "build_card_truth_audit",
    "build_noncard_truth_audit",
    "build_translation_truth_audit",
    "build_runtime_surface_audit",
    "load_known_approximations",
    "run_fidelity_audit",
]
