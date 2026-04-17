from __future__ import annotations

from pathlib import Path

import pytest

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import ALL_CARD_DEFS
from sts_py.engine.run.events import Event, EventChoice, _event_card_base_id
from sts_py.engine.run.run_engine import RunEngine, RunPhase, _deck_card_base_id
from sts_py.engine.simulation import simulate_run_with_logs
from sts_py.terminal.render import render_card_detail_lines
from sts_py.tools import wiki_audit
from tests.log_helpers import (
    describe_optional_corpus_log_requirement,
    describe_optional_recent_live_log_requirement,
    get_corpus_log_spec,
    require_checked_in_fixture,
)


RELEASE_CHECKLIST_PATH = Path.cwd() / "RELEASE_CHECKLIST.md"
WIKI_AUDIT_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "wiki_audit" / "sample_raw_snapshot.json"
STATEFUL_SEED = "PHASE264SHIP"


def test_phase264_release_checklist_is_checked_in_and_calls_out_ship_contract() -> None:
    checklist_path = require_checked_in_fixture(RELEASE_CHECKLIST_PATH, label="release checklist")
    contents = checklist_path.read_text(encoding="utf-8")

    assert "# Release Checklist" in contents
    assert "not seed-perfect parity" in contents
    assert "python -m pytest -q tests/test_phase264_closeout_ship_checklist.py tests/test_phase263_final_rc_signoff.py tests/test_harness_smoke.py tests/test_wiki_audit.py tests/test_full_campaign_stability.py" in contents
    assert "python -m pytest -q tests" in contents
    assert "optional local prerequisite" in contents
    assert "`skip` means the optional local log corpus is unavailable" in contents
    assert "`fail` means a checked-in truth lane regressed" in contents


def test_phase264_offline_audit_ship_baseline_is_green_and_repeated() -> None:
    first_bundle = wiki_audit.run_audit_from_raw_snapshot(
        wiki_audit.build_cli_raw_snapshot(Path.cwd(), enable_network=False),
        repo_root=Path.cwd(),
    )
    second_bundle = wiki_audit.run_audit_from_raw_snapshot(
        wiki_audit.build_cli_raw_snapshot(Path.cwd(), enable_network=False),
        repo_root=Path.cwd(),
    )

    for bundle in (first_bundle, second_bundle):
        translation_summary = bundle["translation_audit"]["summary"]
        mechanics_summary = bundle["mechanics_audit"]["summary"]
        completeness_summary = bundle["completeness_audit"]["summary"]

        assert completeness_summary["missing_in_runtime"] == 0
        assert mechanics_summary["runtime_source_mismatches"] == 0
        assert translation_summary["runtime_name_issue"]["ok"] == translation_summary["total"]

    assert first_bundle["translation_audit"]["summary"] == second_bundle["translation_audit"]["summary"]
    assert first_bundle["mechanics_audit"]["summary"] == second_bundle["mechanics_audit"]["summary"]
    assert first_bundle["completeness_audit"]["summary"] == second_bundle["completeness_audit"]["summary"]


def test_phase264_full_campaign_ship_smoke_has_no_errors() -> None:
    short_result = simulate_run_with_logs("TESTPHASE222SHORT", max_floors=8, verbose=False, enable_combat_logs=False)
    mid_result = simulate_run_with_logs("TESTPHASE222MID", max_floors=20, verbose=False, enable_combat_logs=False)

    assert short_result.errors == []
    assert mid_result.errors == []
    assert short_result.combat_count >= 1
    assert mid_result.combat_count >= short_result.combat_count


def test_phase264_stateful_wire_shapes_remain_stable_across_render_and_event_paths() -> None:
    ritual_detail = render_card_detail_lines("RitualDagger#18+", index=2)
    genetic_detail = render_card_detail_lines("GeneticAlgorithm#7+", index=1)
    searing_detail = render_card_detail_lines("SearingBlow+4", index=3)

    assert any(line == "ID: RitualDagger#18+" for line in ritual_detail)
    assert any(line == "ID: GeneticAlgorithm#7+" for line in genetic_detail)
    assert any(line == "ID: SearingBlow+4" for line in searing_detail)
    assert _deck_card_base_id("RitualDagger#18+") == "RitualDagger"
    assert _event_card_base_id("GeneticAlgorithm#7+") == "GeneticAlgorithm"
    assert _deck_card_base_id("SearingBlow+4") == "SearingBlow"

    engine = RunEngine.create(STATEFUL_SEED, ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine.state.deck = ["GeneticAlgorithm#7+"]
    engine._current_event = Event(
        id="Phase264 Transform",
        name="Phase264 Transform",
        choices=[EventChoice(description="transform", requires_card_transform=True)],
    )

    assert engine.choose_event_option(0)["requires_card_choice"] is True
    result = engine.choose_card_for_event(0)

    assert result["success"] is True
    assert result["old_card"] == "GeneticAlgorithm#7+"
    assert _deck_card_base_id(result["old_card"]) == "GeneticAlgorithm"
    assert CardInstance(result["new_card"]).card_id in ALL_CARD_DEFS


def test_phase264_log_requirement_helpers_distinguish_checked_in_fixture_and_optional_local_logs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    assert require_checked_in_fixture(WIKI_AUDIT_FIXTURE_PATH, label="wiki audit sample fixture") == WIKI_AUDIT_FIXTURE_PATH.resolve()

    missing_checked_in = tmp_path / "missing_fixture.json"
    with pytest.raises(AssertionError, match="checked-in fixture required: missing fixture"):
        require_checked_in_fixture(missing_checked_in, label="missing fixture")

    spec = get_corpus_log_spec("primary")
    monkeypatch.delenv(spec.env_var, raising=False)
    monkeypatch.setenv("STS_LOG_DIR", str(tmp_path))

    corpus_path, corpus_reason = describe_optional_corpus_log_requirement("primary", log_dir=tmp_path)
    recent_path, recent_reason = describe_optional_recent_live_log_requirement(
        "run_latest.json",
        human_label="latest ironclad live log",
        log_dir=tmp_path,
    )

    assert corpus_path is None
    assert corpus_reason == f"optional local corpus log missing: {spec.label} ({spec.preferred_filename})"
    assert recent_path is None
    assert recent_reason == "optional recent live log missing: latest ironclad live log (run_latest.json)"

    corpus_file = tmp_path / spec.preferred_filename
    corpus_file.write_text("{}", encoding="utf-8")
    recent_file = tmp_path / "run_latest.json"
    recent_file.write_text("{}", encoding="utf-8")

    corpus_path, corpus_reason = describe_optional_corpus_log_requirement("primary", log_dir=tmp_path)
    recent_path, recent_reason = describe_optional_recent_live_log_requirement(
        "run_latest.json",
        human_label="latest ironclad live log",
        log_dir=tmp_path,
    )

    assert corpus_path == corpus_file.resolve()
    assert corpus_reason is None
    assert recent_path == recent_file.resolve()
    assert recent_reason is None
