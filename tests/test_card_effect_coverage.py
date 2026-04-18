from __future__ import annotations

import json
from pathlib import Path

from sts_py.tools.card_truth_matrix import CARD_TRUTH_MATRIX_PATH, HIGH_RISK_CARD_IDS, _effect_family
from tests.log_helpers import require_checked_in_fixture


REPO_ROOT = Path.cwd()


def _split_nodeid(nodeid: str) -> tuple[Path, str]:
    path_text, function_name = nodeid.split("::", maxsplit=1)
    return REPO_ROOT / path_text, function_name


def _assert_nodeid_exists(nodeid: str) -> None:
    path, function_name = _split_nodeid(nodeid)
    contents = require_checked_in_fixture(path, label=f"card effect proof {nodeid}").read_text(encoding="utf-8")
    assert f"def {function_name}(" in contents


def _load_matrix() -> dict[str, object]:
    path = require_checked_in_fixture(CARD_TRUTH_MATRIX_PATH, label="card truth matrix")
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_used_card_effect_family_has_at_least_one_proof_nodeid() -> None:
    matrix = _load_matrix()
    coverage: dict[str, list[str]] = {}

    for row in matrix["entities"]:
        runtime_proof_nodeids = [str(nodeid) for nodeid in row.get("runtime_proof_nodeids", []) or []]
        for signature in row.get("runtime_effect_signatures", []) or []:
            family_id = _effect_family(str(signature))
            coverage.setdefault(family_id, [])
            coverage[family_id].extend(runtime_proof_nodeids)

    missing = sorted(family_id for family_id, nodeids in coverage.items() if not nodeids)
    assert missing == []

    for nodeids in coverage.values():
        for nodeid in dict.fromkeys(nodeids):
            _assert_nodeid_exists(nodeid)


def test_non_dispatch_runtime_lanes_and_high_risk_cards_have_proof_coverage() -> None:
    matrix = _load_matrix()
    rows = {row["runtime_id"]: row for row in matrix["entities"]}
    family_tests = dict(matrix.get("family_tests") or {})
    dedicated_tests = dict(matrix.get("dedicated_tests") or {})

    for row in rows.values():
        if row["runtime_truth_kind"] != "none":
            assert row["runtime_proof_nodeids"]
        for family_id in row.get("family_ids", []) or []:
            assert family_id in family_tests
            _assert_nodeid_exists(str(family_tests[family_id]))

    for card_id in HIGH_RISK_CARD_IDS:
        row = rows[card_id]
        dedicated_key = f"card:{card_id}"
        assert dedicated_key in dedicated_tests
        assert dedicated_tests[dedicated_key] in row["runtime_proof_nodeids"]
        _assert_nodeid_exists(str(dedicated_tests[dedicated_key]))
