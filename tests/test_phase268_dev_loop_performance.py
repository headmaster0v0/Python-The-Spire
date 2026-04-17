from __future__ import annotations

from pathlib import Path

from sts_py.tools.dev_checks import HARNESS_TEST, SMOKE_TESTS, parse_args, resolve_profile_items
from tests.log_helpers import require_checked_in_fixture


RELEASE_CHECKLIST_PATH = Path.cwd() / "RELEASE_CHECKLIST.md"
AI_HANDOFF_PATH = Path.cwd() / "AI_HANDOFF.md"


def test_phase268_release_checklist_documents_the_new_dev_loop_command_gradient() -> None:
    contents = require_checked_in_fixture(RELEASE_CHECKLIST_PATH, label="release checklist").read_text(encoding="utf-8")

    assert "## Daily Maintenance Commands" in contents
    assert "python scripts/run_dev_checks.py" in contents
    assert "python scripts/run_dev_checks.py --profile fast" in contents
    assert "python scripts/run_dev_checks.py --profile harness" in contents
    assert "python scripts/run_dev_checks.py --profile full --jobs 4" in contents
    assert "profile-aware default" in contents
    assert "verification throughput" in contents
    assert "do not open a default Phase 269" in contents
    assert "Repeated-run fixture drift, harness instability, or replay-order pollution should be treated as `harness/audit regression` work." in contents


def test_phase268_handoff_declares_verification_throughput_phase_and_return_to_maintenance() -> None:
    contents = require_checked_in_fixture(AI_HANDOFF_PATH, label="AI handoff").read_text(encoding="utf-8")

    assert "> Latest phase: Phase 268 - Dev-Loop Performance / Verification Throughput Closure" in contents
    assert "- Phase 268 - Dev-Loop Performance / Verification Throughput Closure:" in contents
    assert "default `python scripts/run_dev_checks.py` path now resolves to the shortest `smoke` loop" in contents
    assert "timing cache" in contents
    assert "The default next step is to return to targeted maintenance" in contents
    assert "do not open a default Phase 269" in contents
    assert "repeated-run / harness drift belongs in `harness/audit regression`" in contents


def test_phase268_default_dev_loop_stays_on_short_smoke_profile() -> None:
    repo_root = Path.cwd()
    args = parse_args([])
    smoke_items = resolve_profile_items(repo_root, "smoke")

    assert args.profile == "smoke"
    assert smoke_items == SMOKE_TESTS
    assert HARNESS_TEST not in smoke_items
    assert "tests/test_phase267_fidelity_audit.py" not in smoke_items
    assert "tests/test_performance.py" not in smoke_items
