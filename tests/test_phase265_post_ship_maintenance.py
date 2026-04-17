from __future__ import annotations

from pathlib import Path

from sts_py.engine.simulation import simulate_run_with_logs
from sts_py.terminal import render
from sts_py.tools import wiki_audit
from tests.log_helpers import require_checked_in_fixture


RELEASE_CHECKLIST_PATH = Path.cwd() / "RELEASE_CHECKLIST.md"
AI_HANDOFF_PATH = Path.cwd() / "AI_HANDOFF.md"


def test_phase265_release_checklist_documents_post_ship_maintenance_mode() -> None:
    contents = require_checked_in_fixture(RELEASE_CHECKLIST_PATH, label="release checklist").read_text(encoding="utf-8")

    assert "## Post-Ship Maintenance Mode" in contents
    assert "official runtime content is already closed for the audited ship scope" in contents
    assert "random-seed startup and Neow" in contents
    assert "## Daily Maintenance Commands" in contents
    assert "python scripts/run_dev_checks.py" in contents
    assert "python scripts/run_dev_checks.py --profile fast" in contents
    assert "python -m pytest -q tests/test_phase264_closeout_ship_checklist.py tests/test_phase263_final_rc_signoff.py tests/test_wiki_audit.py tests/test_full_campaign_stability.py" in contents
    assert "python scripts/run_dev_checks.py --profile harness" in contents
    assert "python scripts/run_dev_checks.py --profile full --jobs 4" in contents
    assert "python -m pytest -q tests/test_harness_smoke.py" in contents
    assert "run_regressions.py --repo . --new-tests <targeted_test_file> --focus silent" in contents
    assert "tests/test_harness_smoke.py` is the dominant wall-clock cost" in contents
    assert "## Targeted Regression Intake" in contents
    assert "do not open a default Phase 269" in contents
    assert "one-off local failure" in contents
    for category in (
        "gameplay truth bug",
        "CLI/readability bug",
        "harness/audit regression",
        "optional-local-log gap",
    ):
        assert category in contents


def test_phase265_release_checklist_pins_stable_cli_command_surface() -> None:
    contents = require_checked_in_fixture(RELEASE_CHECKLIST_PATH, label="release checklist").read_text(encoding="utf-8")

    assert "## Stable CLI Command Surface" in contents
    for command in (
        "`help`",
        "`map`",
        "`mapimg`",
        "`deck`",
        "`relics`",
        "`potions`",
        "`draw`",
        "`discard`",
        "`inspect <index>`",
        "`status`",
        "`intent`",
        "`exhaust`",
    ):
        assert command in contents
    assert "Do not expand the top-level command surface" in contents


def test_phase265_handoff_declares_maintenance_baseline_and_phase267_fidelity_closure() -> None:
    contents = require_checked_in_fixture(AI_HANDOFF_PATH, label="AI handoff").read_text(encoding="utf-8")

    assert "> Latest phase: Phase 268 - Dev-Loop Performance / Verification Throughput Closure" in contents
    assert "- Phase 268 - Dev-Loop Performance / Verification Throughput Closure:" in contents
    assert "- Phase 267 - Original Fidelity / Experience Reality Closure:" in contents
    assert "- Phase 266 - CLI Startup / Neow / Combat Reality Closure:" in contents
    assert "- Phase 265 - Post-Ship Maintenance / Targeted Regression Intake:" in contents
    assert "official runtime content is already closed for the audited ship scope" in contents
    assert "close source fidelity rather than seed-perfect parity" in contents
    assert "return to targeted maintenance rather than open a default Phase 269" in contents
    assert "repeated-run / harness drift belongs in `harness/audit regression`" in contents
    assert "the stable CLI command surface is now:" in contents
    assert "`help / map / mapimg / deck / relics / potions / draw / discard / inspect <index> / status / intent / exhaust`" in contents
    assert "random-seed launch path" in contents
    assert "RunPhase.NEOW" in contents


def test_phase265_daily_maintenance_baseline_stays_green() -> None:
    bundle = wiki_audit.run_audit_from_raw_snapshot(
        wiki_audit.build_cli_raw_snapshot(Path.cwd(), enable_network=False),
        repo_root=Path.cwd(),
    )
    short_result = simulate_run_with_logs("TESTPHASE222SHORT", max_floors=8, verbose=False, enable_combat_logs=False)
    mid_result = simulate_run_with_logs("TESTPHASE222MID", max_floors=20, verbose=False, enable_combat_logs=False)

    assert bundle["completeness_audit"]["summary"]["missing_in_runtime"] == 0
    assert bundle["mechanics_audit"]["summary"]["runtime_source_mismatches"] == 0
    assert bundle["translation_audit"]["summary"]["runtime_name_issue"]["ok"] == bundle["translation_audit"]["summary"]["total"]
    assert short_result.errors == []
    assert mid_result.errors == []


def test_phase265_render_help_lines_continue_to_expose_the_stable_command_set() -> None:
    combined_lines = (
        render.render_help_lines("map")
        + render.render_help_lines("combat")
        + render.render_help_lines("reward")
        + render.render_help_lines("shop")
    )
    combined = "\n".join(combined_lines)

    for token in (
        "mapimg",
        "deck",
        "relics",
        "potions",
        "draw",
        "discard",
        "status",
        "intent",
        "exhaust",
        "help",
        "inspect <index>",
    ):
        assert token in combined
