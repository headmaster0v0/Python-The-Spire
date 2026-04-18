from __future__ import annotations

import json
import re
from pathlib import Path

from sts_py.engine.content.relics import ALL_RELICS
from sts_py.tools.relic_truth_matrix import RELIC_TRUTH_MATRIX_PATH
from tests.log_helpers import require_checked_in_fixture


REPO_ROOT = Path.cwd()
HANDLER_PATHS = (
    REPO_ROOT / "sts_py" / "engine" / "combat" / "combat_engine.py",
    REPO_ROOT / "sts_py" / "engine" / "run" / "run_engine.py",
    REPO_ROOT / "sts_py" / "engine" / "combat" / "potion_effects.py",
    REPO_ROOT / "sts_py" / "terminal" / "catalog.py",
)
MANUAL_HANDLER_EFFECT_TYPES = {
    "DOUBLE_POTION_POTENCY",
}


def _split_nodeid(nodeid: str) -> tuple[Path, str]:
    path_text, function_name = nodeid.split("::", maxsplit=1)
    return REPO_ROOT / path_text, function_name


def _assert_nodeid_exists(nodeid: str) -> None:
    path, function_name = _split_nodeid(nodeid)
    contents = require_checked_in_fixture(path, label=f"relic effect proof {nodeid}").read_text(encoding="utf-8")
    assert f"def {function_name}(" in contents


def _used_effect_types() -> dict[str, list[str]]:
    effect_types: dict[str, list[str]] = {}
    for relic_id, relic_def in sorted(ALL_RELICS.items()):
        for effect in relic_def.effects:
            effect_types.setdefault(effect.effect_type.name, []).append(relic_id)
    return effect_types


def _handled_effect_types() -> set[str]:
    handled: set[str] = set(MANUAL_HANDLER_EFFECT_TYPES)
    for path in HANDLER_PATHS:
        text = require_checked_in_fixture(path, label=f"relic handler file {path.name}").read_text(encoding="utf-8")
        handled.update(re.findall(r"RelicEffectType\.(\w+)", text))
    return handled


def test_every_used_relic_effect_type_has_handler_coverage() -> None:
    used_effect_types = _used_effect_types()
    handled_effect_types = _handled_effect_types()

    missing = sorted(set(used_effect_types) - handled_effect_types)
    assert missing == []


def test_every_used_relic_effect_type_has_at_least_one_regression_nodeid() -> None:
    matrix = json.loads(require_checked_in_fixture(RELIC_TRUTH_MATRIX_PATH, label="relic truth matrix").read_text(encoding="utf-8"))
    rows = {row["runtime_id"]: row for row in matrix["entities"]}
    coverage: dict[str, list[str]] = {}

    for effect_type, relic_ids in _used_effect_types().items():
        nodeids: list[str] = []
        for relic_id in relic_ids:
            row = rows[relic_id]
            nodeids.extend(str(nodeid) for nodeid in row.get("runtime_proof_nodeids", []) or [])
        deduped: list[str] = []
        seen: set[str] = set()
        for nodeid in nodeids:
            if nodeid in seen:
                continue
            seen.add(nodeid)
            deduped.append(nodeid)
        coverage[effect_type] = deduped

    missing = sorted(effect_type for effect_type, nodeids in coverage.items() if not nodeids)
    assert missing == []

    for nodeids in coverage.values():
        for nodeid in nodeids:
            _assert_nodeid_exists(nodeid)
