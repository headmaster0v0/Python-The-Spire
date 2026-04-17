from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sts_py.tools.generate_handoff_draft import (
    CorpusHarnessSummary,
    HandoffDraft,
    PhaseInput,
    build_handoff_draft,
    main,
)
from sts_py.tools.log_discovery import CorpusLogSpec, ResolvedCorpusLog


def _sample_phase_input() -> PhaseInput:
    return PhaseInput(
        phase_number=216,
        phase_title="Handoff / Report Automation",
        phase_summary=[
            "new tool `sts_py/tools/generate_handoff_draft.py` emits reviewable Markdown and JSON handoff drafts",
            "shared log discovery and corpus registry now live under `sts_py.tools.log_discovery`",
        ],
        verified_commands=[
            "python -m pytest -q tests/test_log_discovery.py",
            "python -m pytest -q tests/test_handoff_draft_generator.py",
        ],
    )


def _sample_summaries() -> list[CorpusHarnessSummary]:
    return [
        CorpusHarnessSummary(
            label="primary",
            filename="run_PRIMARY.json",
            path="C:\\Users\\HP\\sts_data_logs\\run_PRIMARY.json",
            ok=True,
            checked=52,
            diff_count=0,
            first_mismatch="none",
            character="IRONCLAD",
            run_result="victory",
            end_floor=51,
        ),
        CorpusHarnessSummary(
            label="secondary",
            filename="run_SECONDARY.json",
            path="C:\\Users\\HP\\sts_data_logs\\run_SECONDARY.json",
            ok=False,
            checked=34,
            diff_count=2,
            first_mismatch="F1 battle.player_end_hp",
            character="SILENT",
            run_result="defeat",
            end_floor=18,
        ),
    ]


def test_phase_input_rejects_unknown_keys() -> None:
    try:
        PhaseInput.from_dict(
            {
                "phase_number": 216,
                "phase_title": "Handoff / Report Automation",
                "phase_summary": [],
                "verified_commands": [],
                "extra": "nope",
            }
        )
    except ValueError as exc:
        assert "Unsupported phase input keys" in str(exc)
    else:
        raise AssertionError("PhaseInput.from_dict should reject unknown keys")


def test_build_handoff_draft_renders_header_phase_entry_snapshot_and_default_next_step(
    monkeypatch,
    workspace_tmp_path: Path,
) -> None:
    handoff_path = workspace_tmp_path / "AI_HANDOFF.md"
    handoff_path.write_text(
        "\n".join(
            [
                "# AI Handoff",
                "",
                "## 6. Suggested Next Step",
                "",
                "Keep the current automation line moving.",
                "",
                "1. Phase 217 - Apply Mode",
                "2. Optional skill integration",
                "",
                "## 7. Assumptions",
                "",
                "- Example",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sts_py.tools.generate_handoff_draft.discover_java_logs",
        lambda log_dir=None: [Path(r"C:\Users\HP\sts_data_logs\run_LATEST.json")],
    )
    monkeypatch.setattr(
        "sts_py.tools.generate_handoff_draft.resolve_available_corpus_logs",
        lambda log_dir=None: [
            ResolvedCorpusLog(
                spec=CorpusLogSpec("primary", "STS_JAVA_LOG", 0, "run_PRIMARY.json", "Java recorder log"),
                path=Path(r"C:\Users\HP\sts_data_logs\run_PRIMARY.json"),
            )
        ],
    )
    monkeypatch.setattr(
        "sts_py.tools.generate_handoff_draft.summarize_corpus_logs",
        lambda resolved_logs: _sample_summaries(),
    )

    draft = build_handoff_draft(
        _sample_phase_input(),
        "1618 passed, 2 xpassed",
        handoff_path=handoff_path,
        today=date(2026, 4, 11),
    )

    assert draft.header_metadata == {
        "updated": "2026-04-11",
        "latest_phase": "Phase 216 - Handoff / Report Automation",
        "current_test_result": "1618 passed, 2 xpassed",
    }
    assert draft.header_metadata_markdown == "\n".join(
        [
            "> Updated: 2026-04-11",
            "> Latest phase: Phase 216 - Handoff / Report Automation",
            "> Current test result: `1618 passed, 2 xpassed`",
        ]
    )
    assert draft.latest_verified_local_recorder_log == r"C:\Users\HP\sts_data_logs\run_LATEST.json"
    assert draft.aggregated_corpus_totals == {
        "checked": 86,
        "matched": 84,
        "residual": 2,
    }
    assert "## Header Metadata" in draft.markdown_draft
    assert "> Updated: 2026-04-11" in draft.markdown_draft
    assert "- Phase 216 - Handoff / Report Automation:" in draft.markdown_draft
    assert "- Latest verified local recorder log:" in draft.markdown_draft
    assert "- Current local corpus snapshot:" in draft.recorder_corpus_snapshot_markdown
    assert "  - primary `run_PRIMARY.json`:" in draft.markdown_draft
    assert "  - secondary `run_SECONDARY.json`:" in draft.markdown_draft
    assert "    - `matched = 84`" in draft.markdown_draft
    assert "Keep the current automation line moving." in draft.markdown_draft
    assert "1. Phase 217 - Apply Mode" in draft.markdown_draft


def test_build_handoff_draft_uses_next_step_override(monkeypatch, workspace_tmp_path: Path) -> None:
    monkeypatch.setattr(
        "sts_py.tools.generate_handoff_draft.discover_java_logs",
        lambda log_dir=None: [],
    )
    monkeypatch.setattr(
        "sts_py.tools.generate_handoff_draft.resolve_available_corpus_logs",
        lambda log_dir=None: [],
    )
    monkeypatch.setattr(
        "sts_py.tools.generate_handoff_draft.summarize_corpus_logs",
        lambda resolved_logs: [],
    )

    phase_input = PhaseInput(
        phase_number=216,
        phase_title="Handoff / Report Automation",
        phase_summary=["summary line"],
        verified_commands=["python -m pytest -q tests/test_handoff_draft_generator.py"],
        next_step_lines=["Custom next step.", "1. Follow-up"],
    )

    draft = build_handoff_draft(
        phase_input,
        "1618 passed, 2 xpassed",
        handoff_path=workspace_tmp_path / "missing.md",
        today=date(2026, 4, 11),
    )

    assert draft.suggested_next_step_markdown == "Custom next step.\n1. Follow-up"
    assert "Custom next step." in draft.markdown_draft
    assert "1. Follow-up" in draft.markdown_draft


def test_build_handoff_draft_supports_phase227_reward_surface_wording(monkeypatch, workspace_tmp_path: Path) -> None:
    monkeypatch.setattr(
        "sts_py.tools.generate_handoff_draft.discover_java_logs",
        lambda log_dir=None: [],
    )
    monkeypatch.setattr(
        "sts_py.tools.generate_handoff_draft.resolve_available_corpus_logs",
        lambda log_dir=None: [],
    )
    monkeypatch.setattr(
        "sts_py.tools.generate_handoff_draft.summarize_corpus_logs",
        lambda resolved_logs: [],
    )

    phase_input = PhaseInput(
        phase_number=227,
        phase_title="Recorder / Harness Reward-Surface Alignment",
        phase_summary=["reward-surface schema now includes boss relic choice and treasure summaries"],
        verified_commands=["python -m pytest -q tests/test_compare_logs.py tests/test_harness_smoke.py"],
        next_step_lines=[
            "Reward-surface alignment is now the current mainline.",
            "1. Phase 228 - Run-Scoped Relic Pool / Reward-History Fidelity",
        ],
    )

    draft = build_handoff_draft(
        phase_input,
        "1723 passed, 2 xpassed",
        handoff_path=workspace_tmp_path / "missing.md",
        today=date(2026, 4, 14),
    )

    assert draft.header_metadata["latest_phase"] == "Phase 227 - Recorder / Harness Reward-Surface Alignment"
    assert "Reward-surface alignment is now the current mainline." in draft.markdown_draft
    assert "1. Phase 228 - Run-Scoped Relic Pool / Reward-History Fidelity" in draft.markdown_draft


def _stub_draft() -> HandoffDraft:
    return HandoffDraft(
        header_metadata={
            "updated": "2026-04-11",
            "latest_phase": "Phase 216 - Handoff / Report Automation",
            "current_test_result": "1618 passed, 2 xpassed",
        },
        header_metadata_markdown="> Updated: 2026-04-11\n> Latest phase: Phase 216 - Handoff / Report Automation\n> Current test result: `1618 passed, 2 xpassed`",
        latest_verified_local_recorder_log=r"C:\Users\HP\sts_data_logs\run_LATEST.json",
        corpus_summaries=_sample_summaries(),
        aggregated_corpus_totals={"checked": 86, "matched": 84, "residual": 2},
        current_baseline_entry_markdown="- Phase 216 - Handoff / Report Automation:\n  - summary",
        recorder_corpus_snapshot_markdown="- Latest verified local recorder log:\n  `C:\\Users\\HP\\sts_data_logs\\run_LATEST.json`\n\n- Current local corpus snapshot:\n  - primary `run_PRIMARY.json`:",
        suggested_next_step_markdown="1. Follow-up",
        markdown_draft="## Header Metadata\n> Updated: 2026-04-11\n",
    )


def test_cli_writes_markdown_to_stdout(monkeypatch, workspace_tmp_path: Path, capsys) -> None:
    phase_input_path = workspace_tmp_path / "phase216.json"
    phase_input_path.write_text(
        json.dumps(
            {
                "phase_number": 216,
                "phase_title": "Handoff / Report Automation",
                "phase_summary": ["summary"],
                "verified_commands": ["pytest"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("sts_py.tools.generate_handoff_draft.build_handoff_draft", lambda *args, **kwargs: _stub_draft())

    assert main([str(phase_input_path), "--test-result", "1618 passed, 2 xpassed"]) == 0
    captured = capsys.readouterr()
    assert "## Header Metadata" in captured.out


def test_cli_writes_json_to_output_file(monkeypatch, workspace_tmp_path: Path) -> None:
    phase_input_path = workspace_tmp_path / "phase216.json"
    output_path = workspace_tmp_path / "draft.json"
    phase_input_path.write_text(
        json.dumps(
            {
                "phase_number": 216,
                "phase_title": "Handoff / Report Automation",
                "phase_summary": ["summary"],
                "verified_commands": ["pytest"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("sts_py.tools.generate_handoff_draft.build_handoff_draft", lambda *args, **kwargs: _stub_draft())

    assert main([str(phase_input_path), "--test-result", "1618 passed, 2 xpassed", "--json", "--output", str(output_path)]) == 0
    rendered = json.loads(output_path.read_text(encoding="utf-8"))
    assert rendered["header_metadata"]["updated"] == "2026-04-11"
    assert rendered["aggregated_corpus_totals"]["residual"] == 2


def test_cli_accepts_utf8_sig_phase_input(monkeypatch, workspace_tmp_path: Path, capsys) -> None:
    phase_input_path = workspace_tmp_path / "phase216_bom.json"
    phase_input_path.write_text(
        json.dumps(
            {
                "phase_number": 216,
                "phase_title": "Handoff / Report Automation",
                "phase_summary": ["summary"],
                "verified_commands": ["pytest"],
            }
        ),
        encoding="utf-8-sig",
    )
    monkeypatch.setattr("sts_py.tools.generate_handoff_draft.build_handoff_draft", lambda *args, **kwargs: _stub_draft())

    assert main([str(phase_input_path), "--test-result", "1618 passed, 2 xpassed"]) == 0
    captured = capsys.readouterr()
    assert "## Header Metadata" in captured.out
