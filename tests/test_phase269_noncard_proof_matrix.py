from __future__ import annotations

import json
from pathlib import Path

import pytest

from sts_py.tools import wiki_audit
from sts_py.tools.fidelity_audit import run_fidelity_audit
from sts_py.tools.fidelity_proof import FIDELITY_PROOF_MATRIX_PATH, build_fidelity_proof_matrix_from_raw_snapshot
from tests.log_helpers import require_checked_in_fixture


def _split_nodeid(nodeid: str) -> tuple[Path, str]:
    path_text, function_name = nodeid.split("::", maxsplit=1)
    return Path.cwd() / path_text, function_name


def _assert_nodeid_exists(nodeid: str) -> None:
    path, function_name = _split_nodeid(nodeid)
    contents = require_checked_in_fixture(path, label=f"proof target {nodeid}").read_text(encoding="utf-8")
    assert f"def {function_name}(" in contents


@pytest.fixture(scope="module")
def phase269_raw_snapshot() -> dict[str, object]:
    return wiki_audit.build_cli_raw_snapshot(Path.cwd(), enable_network=False)


@pytest.fixture(scope="module")
def phase269_expected_matrix(phase269_raw_snapshot: dict[str, object]) -> dict[str, object]:
    return build_fidelity_proof_matrix_from_raw_snapshot(phase269_raw_snapshot)


@pytest.fixture(scope="module")
def phase269_fidelity_bundle() -> dict[str, object]:
    return run_fidelity_audit(Path.cwd())


def test_phase269_checked_in_noncard_proof_matrix_matches_generated_runtime_inventory(
    phase269_expected_matrix: dict[str, object],
) -> None:
    path = require_checked_in_fixture(FIDELITY_PROOF_MATRIX_PATH, label="fidelity proof matrix")
    checked_in = json.loads(path.read_text(encoding="utf-8"))

    assert checked_in == phase269_expected_matrix


def test_phase269_proof_matrix_references_checked_in_truth_tests(
    phase269_expected_matrix: dict[str, object],
) -> None:
    for nodeid in sorted(set(phase269_expected_matrix["family_tests"].values())):
        _assert_nodeid_exists(nodeid)
    for nodeid in sorted(set(phase269_expected_matrix["dedicated_tests"].values())):
        _assert_nodeid_exists(nodeid)


def test_phase269_fidelity_audit_requires_noncard_proof_coverage_to_be_green(
    phase269_expected_matrix: dict[str, object],
    phase269_fidelity_bundle: dict[str, object],
) -> None:
    summary = phase269_fidelity_bundle["summary"]
    noncard_summary = phase269_fidelity_bundle["noncard_truth_audit"]["summary"]

    assert summary["blocker_count"] == 0
    assert summary["known_approximations_count"] == 0
    assert summary["noncard_proof_uncovered"] == 0
    assert summary["noncard_signature_mismatches"] == 0
    assert noncard_summary["entity_count"] == len(phase269_expected_matrix["entities"])
    assert noncard_summary["noncard_proof_uncovered"] == 0
    assert noncard_summary["signature_mismatches"] == 0
    assert noncard_summary["stale_matrix_entries"] == 0
    assert noncard_summary["family_test_registry_mismatch"] == 0
    assert noncard_summary["dedicated_test_registry_mismatch"] == 0


def test_phase269_proof_matrix_entries_have_valid_proof_kind_and_no_notes(
    phase269_expected_matrix: dict[str, object],
) -> None:
    proof_kinds = {entry["proof_kind"] for entry in phase269_expected_matrix["entities"]}

    assert proof_kinds == {"family", "dedicated"}
    assert all(entry["notes"] == "" for entry in phase269_expected_matrix["entities"])
