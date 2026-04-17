from __future__ import annotations

import json
from pathlib import Path

import pytest

from sts_py.tools.fidelity_audit import KNOWN_APPROXIMATIONS_PATH, run_fidelity_audit
from tests.log_helpers import require_checked_in_fixture


@pytest.fixture(scope="module")
def phase267_fidelity_bundle() -> dict[str, object]:
    return run_fidelity_audit(Path.cwd())


def test_phase267_known_approximations_file_is_checked_in_and_empty(
    phase267_fidelity_bundle: dict[str, object],
) -> None:
    path = require_checked_in_fixture(KNOWN_APPROXIMATIONS_PATH, label="known approximations")
    contents = json.loads(path.read_text(encoding="utf-8"))

    assert contents["schema_version"] == 1
    assert contents["items"] == []
    assert phase267_fidelity_bundle["known_approximations"]["items"] == []


def test_phase267_surface_audit_covers_non_card_runtime_entities_without_shell_blockers(
    phase267_fidelity_bundle: dict[str, object],
) -> None:
    surface_audit = phase267_fidelity_bundle["surface_audit"]
    summary = surface_audit["summary"]

    assert summary["by_entity_type"]["relic"] > 0
    assert summary["by_entity_type"]["potion"] > 0
    assert summary["by_entity_type"]["power"] > 0
    assert summary["by_entity_type"]["monster"] > 0
    assert summary["by_entity_type"]["event"] > 0
    assert summary["by_entity_type"]["room_type"] > 0
    assert summary["by_entity_type"]["ui_term"] > 0
    assert summary["shop_surface"]["card_line_count"] > 0
    assert summary["shop_surface"]["relic_line_count"] > 0
    assert summary["shop_surface"]["potion_line_count"] > 0
    assert surface_audit["blockers"] == []


def test_phase267_fidelity_gate_requires_live_audit_green_plus_surface_green(
    phase267_fidelity_bundle: dict[str, object],
) -> None:
    summary = phase267_fidelity_bundle["summary"]
    wiki_summary = summary["wiki_audit"]
    noncard_summary = phase267_fidelity_bundle["noncard_truth_audit"]["summary"]
    translation_summary = phase267_fidelity_bundle["translation_truth_audit"]["summary"]

    assert summary["known_approximations_count"] == 0
    assert summary["surface_blocker_count"] == 0
    assert summary["translation_truth_blocker_count"] == 0
    assert summary["blocker_count"] == 0
    assert summary["noncard_proof_uncovered"] == 0
    assert summary["noncard_signature_mismatches"] == 0
    assert wiki_summary["missing_in_runtime"] == 0
    assert wiki_summary["runtime_source_mismatches"] == 0
    assert wiki_summary["runtime_name_issue_ok"] == wiki_summary["translation_total"]
    assert translation_summary["exact_match_count"] > 0
    assert translation_summary["blocker_count"] == 0
    assert noncard_summary["entity_count"] > 0
    assert noncard_summary["noncard_proof_uncovered"] == 0


def test_phase267_tests_no_longer_contain_doc_only_unimplemented_markers() -> None:
    banned_markers = ("NOT" + " IMPLEMENTED", "[" + "未实现" + "]", "[" + "需实现" + "]")
    flagged: list[str] = []

    for path in sorted(Path("tests").glob("test_*.py")):
        contents = path.read_text(encoding="utf-8")
        if any(marker in contents for marker in banned_markers):
            flagged.append(str(path))

    assert flagged == []
