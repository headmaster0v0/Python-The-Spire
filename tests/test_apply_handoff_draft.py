from __future__ import annotations

import json
from pathlib import Path

import pytest

from sts_py.tools.apply_handoff_draft import apply_draft_to_handoff_text, build_apply_preview, main
from sts_py.tools.generate_handoff_draft import HandoffDraft


def _sample_handoff_text() -> str:
    return "\n".join(
        [
            "# AI Handoff: STS Python Headless",
            "",
            "> Updated: 2026-04-11",
            "> Latest phase: Phase 215 - Alias / Report Hygiene Closure",
            "> Current test result: `1618 passed, 2 xpassed`",
            "",
            "## 1. Project Goal",
            "",
            "Goal text.",
            "",
            "## 3. Current Baseline",
            "",
            "- Phase 215 - Alias / Report Hygiene Closure:",
            "  - old summary",
            "- Phase 193 completed the Silent shiv/card-play payoff cluster:",
            "  - older content",
            "",
            "- Latest verified local recorder log:",
            "  `C:\\Users\\HP\\sts_data_logs\\run_OLD.json`",
            "- Current ARN baseline snapshot after Phase 100:",
            "  - floor diff: `0`",
            "  - matched / checked: `52 / 52`",
            "  - first mismatch: `none`",
            "  - Current local corpus snapshot after Phase 135:",
            "  - primary `run_OLD.json`:",
            "    - `ok = True`",
            "  - Total current corpus snapshot:",
            "    - `checked = 52`",
            "    - `matched = 52`",
            "    - `residual = 0`",
            "  - Phase 156 starts game-content updates on a stable 10-log green corpus baseline:",
            "    - older corpus context",
            "",
            "## 6. Suggested Next Step",
            "",
            "Old next step text.",
            "",
            "1. Old recommendation",
            "",
            "## 7. Assumptions",
            "",
            "- Existing assumption.",
            "",
        ]
    )


def _sample_draft() -> HandoffDraft:
    return HandoffDraft(
        header_metadata={
            "updated": "2026-04-12",
            "latest_phase": "Phase 217 - Handoff Draft Apply Mode",
            "current_test_result": "1620 passed, 2 xpassed",
        },
        header_metadata_markdown="\n".join(
            [
                "> Updated: 2026-04-12",
                "> Latest phase: Phase 217 - Handoff Draft Apply Mode",
                "> Current test result: `1620 passed, 2 xpassed`",
            ]
        ),
        latest_verified_local_recorder_log=r"C:\Users\HP\sts_data_logs\run_NEW.json",
        corpus_summaries=[],
        aggregated_corpus_totals={"checked": 480, "matched": 480, "residual": 0},
        current_baseline_entry_markdown="\n".join(
            [
                "- Phase 217 - Handoff Draft Apply Mode:",
                "  - apply mode now patches fixed handoff regions safely",
                "  - verified with:",
                "    - `python -m pytest -q tests/test_apply_handoff_draft.py`",
            ]
        ),
        recorder_corpus_snapshot_markdown="\n".join(
            [
                "- Latest verified local recorder log:",
                "  `C:\\Users\\HP\\sts_data_logs\\run_NEW.json`",
                "- Current local corpus snapshot:",
                "  - primary `run_NEW.json`:",
                "    - `ok = True`",
                "    - `checked = 52`",
                "    - `diff_count = 0`",
                "    - `first mismatch = none`",
                "  - Total current corpus snapshot:",
                "    - `checked = 480`",
                "    - `matched = 480`",
                "    - `residual = 0`",
            ]
        ),
        suggested_next_step_markdown="\n".join(
            [
                "Apply mode is now the immediate mainline.",
                "",
                "1. Phase 218 - Optional skill sync",
                "2. Keep repo-native apply as the primary path",
            ]
        ),
        markdown_draft="draft preview",
    )


def test_build_apply_preview_does_not_mutate_file(workspace_tmp_path: Path) -> None:
    handoff_path = workspace_tmp_path / "AI_HANDOFF.md"
    original_text = _sample_handoff_text()
    handoff_path.write_text(original_text, encoding="utf-8")

    preview = build_apply_preview(_sample_draft(), handoff_path, write_requested=False)

    assert handoff_path.read_text(encoding="utf-8") == original_text
    assert preview.changed is True
    assert "Phase 217 - Handoff Draft Apply Mode" in preview.diff_text
    assert "header_metadata_markdown" in preview.fragments


def test_apply_draft_updates_only_target_regions_and_preserves_arn_snapshot() -> None:
    updated_text = apply_draft_to_handoff_text(_sample_handoff_text(), _sample_draft())

    assert "> Updated: 2026-04-12" in updated_text
    assert "> Latest phase: Phase 217 - Handoff Draft Apply Mode" in updated_text
    assert "> Current test result: `1620 passed, 2 xpassed`" in updated_text
    assert updated_text.count("- Phase 217 - Handoff Draft Apply Mode:") == 1
    assert "apply mode now patches fixed handoff regions safely" in updated_text
    assert "- Latest verified local recorder log:" in updated_text
    assert "- Current local corpus snapshot:" in updated_text
    assert "- Current ARN baseline snapshot after Phase 100:" in updated_text
    assert "  - floor diff: `0`" in updated_text
    assert "  - matched / checked: `52 / 52`" in updated_text
    assert "Apply mode is now the immediate mainline." in updated_text
    assert "## 7. Assumptions" in updated_text
    assert "- Existing assumption." in updated_text


def test_apply_draft_is_idempotent_for_same_phase() -> None:
    first_pass = apply_draft_to_handoff_text(_sample_handoff_text(), _sample_draft())
    second_pass = apply_draft_to_handoff_text(first_pass, _sample_draft())

    assert second_pass == first_pass
    assert second_pass.count("- Phase 217 - Handoff Draft Apply Mode:") == 1


def test_apply_draft_supports_phase227_reward_surface_wording() -> None:
    draft = HandoffDraft(
        header_metadata={
            "updated": "2026-04-14",
            "latest_phase": "Phase 227 - Recorder / Harness Reward-Surface Alignment",
            "current_test_result": "1723 passed, 2 xpassed",
        },
        header_metadata_markdown="\n".join(
            [
                "> Updated: 2026-04-14",
                "> Latest phase: Phase 227 - Recorder / Harness Reward-Surface Alignment",
                "> Current test result: `1723 passed, 2 xpassed`",
            ]
        ),
        latest_verified_local_recorder_log=r"C:\Users\HP\sts_data_logs\run_PHASE227.json",
        corpus_summaries=[],
        aggregated_corpus_totals={"checked": 0, "matched": 0, "residual": 0},
        current_baseline_entry_markdown="- Phase 227 - Recorder / Harness Reward-Surface Alignment:\n  - reward-surface schema now reaches recorder, parser, harness, and handoff",
        recorder_corpus_snapshot_markdown="- Latest verified local recorder log:\n  `C:\\Users\\HP\\sts_data_logs\\run_PHASE227.json`\n\n- Current local corpus snapshot:\n  - none",
        suggested_next_step_markdown="1. Phase 228 - Run-Scoped Relic Pool / Reward-History Fidelity",
        markdown_draft="draft preview",
    )

    updated_text = apply_draft_to_handoff_text(_sample_handoff_text(), draft)

    assert "> Latest phase: Phase 227 - Recorder / Harness Reward-Surface Alignment" in updated_text
    assert "> Current test result: `1723 passed, 2 xpassed`" in updated_text
    assert "- Phase 227 - Recorder / Harness Reward-Surface Alignment:" in updated_text
    assert "1. Phase 228 - Run-Scoped Relic Pool / Reward-History Fidelity" in updated_text


def test_apply_draft_raises_when_required_anchor_is_missing() -> None:
    broken_text = _sample_handoff_text().replace("## 6. Suggested Next Step", "## 6. Missing")
    with pytest.raises(ValueError, match="Suggested Next Step|## 6"):
        apply_draft_to_handoff_text(broken_text, _sample_draft())


def test_apply_draft_raises_when_required_anchor_is_duplicated() -> None:
    duplicated_text = _sample_handoff_text() + "- Latest verified local recorder log:\n  `duplicate`\n"
    with pytest.raises(ValueError, match="Latest verified local recorder log"):
        apply_draft_to_handoff_text(duplicated_text, _sample_draft())


def test_cli_preview_json_and_write_modes(monkeypatch, workspace_tmp_path: Path, capsys) -> None:
    phase_input_path = workspace_tmp_path / "phase217.json"
    handoff_path = workspace_tmp_path / "AI_HANDOFF.md"
    phase_input_path.write_text(
        json.dumps(
            {
                "phase_number": 217,
                "phase_title": "Handoff Draft Apply Mode",
                "phase_summary": ["summary"],
                "verified_commands": ["pytest"],
            }
        ),
        encoding="utf-8",
    )
    handoff_path.write_text(_sample_handoff_text(), encoding="utf-8")
    monkeypatch.setattr("sts_py.tools.apply_handoff_draft.build_handoff_draft", lambda *args, **kwargs: _sample_draft())

    assert main([str(phase_input_path), "--test-result", "1620 passed, 2 xpassed", "--handoff-path", str(handoff_path)]) == 0
    preview_out = capsys.readouterr().out
    assert "HANDOFF APPLY PREVIEW" in preview_out
    assert handoff_path.read_text(encoding="utf-8") == _sample_handoff_text()

    assert main(
        [
            str(phase_input_path),
            "--test-result",
            "1620 passed, 2 xpassed",
            "--handoff-path",
            str(handoff_path),
            "--json",
        ]
    ) == 0
    json_out = json.loads(capsys.readouterr().out)
    assert json_out["changed"] is True
    assert "Phase 217 - Handoff Draft Apply Mode" in json_out["diff_text"]

    assert main(
        [
            str(phase_input_path),
            "--test-result",
            "1620 passed, 2 xpassed",
            "--handoff-path",
            str(handoff_path),
            "--write",
        ]
    ) == 0
    written_text = handoff_path.read_text(encoding="utf-8")
    assert "> Latest phase: Phase 217 - Handoff Draft Apply Mode" in written_text
    assert "Apply mode is now the immediate mainline." in written_text


def test_cli_accepts_utf8_sig_handoff_file(monkeypatch, workspace_tmp_path: Path, capsys) -> None:
    phase_input_path = workspace_tmp_path / "phase217.json"
    handoff_path = workspace_tmp_path / "AI_HANDOFF_bom.md"
    phase_input_path.write_text(
        json.dumps(
            {
                "phase_number": 217,
                "phase_title": "Handoff Draft Apply Mode",
                "phase_summary": ["summary"],
                "verified_commands": ["pytest"],
            }
        ),
        encoding="utf-8",
    )
    handoff_path.write_text(_sample_handoff_text(), encoding="utf-8-sig")
    monkeypatch.setattr("sts_py.tools.apply_handoff_draft.build_handoff_draft", lambda *args, **kwargs: _sample_draft())

    assert main([str(phase_input_path), "--test-result", "1620 passed, 2 xpassed", "--handoff-path", str(handoff_path)]) == 0
    captured = capsys.readouterr()
    assert "HANDOFF APPLY PREVIEW" in captured.out
