from __future__ import annotations

import argparse
import difflib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any

from sts_py.tools.generate_handoff_draft import HandoffDraft, PhaseInput, build_handoff_draft


HEADER_PREFIXES = (
    "> Updated:",
    "> Latest phase:",
    "> Current test result:",
)
BASELINE_HEADING = "## 3. Current Baseline"
NEXT_STEP_HEADING = "## 6. Suggested Next Step"
ASSUMPTIONS_HEADING = "## 7. Assumptions"
LATEST_RECORDER_LINE = "- Latest verified local recorder log:"
ARN_SNAPSHOT_LINE = "- Current ARN baseline snapshot after Phase 100:"
CURRENT_CORPUS_PATTERN = re.compile(r"^\s*-\sCurrent local corpus snapshot")
PHASE_ENTRY_PATTERN = re.compile(r"^\s*-\sPhase \d+\b")


@dataclass(frozen=True)
class HandoffApplyPreview:
    handoff_path: str
    write_requested: bool
    changed: bool
    updated_text: str
    diff_text: str
    fragments: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "handoff_path": self.handoff_path,
            "write_requested": self.write_requested,
            "changed": self.changed,
            "updated_text": self.updated_text,
            "diff_text": self.diff_text,
            "fragments": self.fragments,
        }


def _find_unique_index(lines: list[str], target: str) -> int:
    matches = [idx for idx, line in enumerate(lines) if line == target]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one line matching {target!r}, found {len(matches)}")
    return matches[0]


def _find_heading_index(lines: list[str], heading: str) -> int:
    return _find_unique_index(lines, heading)


def _find_next_heading_index(lines: list[str], start_idx: int) -> int:
    for idx in range(start_idx + 1, len(lines)):
        if lines[idx].startswith("## "):
            return idx
    return len(lines)


def _find_first_phase_entry_index(lines: list[str], start_idx: int, end_idx: int) -> int | None:
    for idx in range(start_idx, end_idx):
        if lines[idx].startswith("- Phase "):
            return idx
        if lines[idx] != "":
            raise ValueError("Unexpected non-phase content before first baseline phase entry")
    return None


def _find_next_top_level_bullet(lines: list[str], start_idx: int, end_idx: int) -> int:
    for idx in range(start_idx, end_idx):
        if lines[idx].startswith("- "):
            return idx
    return end_idx


def _replace_header_metadata(lines: list[str], draft: HandoffDraft) -> list[str]:
    indices = []
    for prefix in HEADER_PREFIXES:
        matches = [idx for idx, line in enumerate(lines) if line.startswith(prefix)]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one header line starting with {prefix!r}, found {len(matches)}")
        indices.append(matches[0])

    if indices != sorted(indices):
        raise ValueError("Header metadata lines are not in the expected order")

    new_lines = lines.copy()
    for idx, replacement in zip(indices, draft.header_metadata_markdown.splitlines(), strict=True):
        new_lines[idx] = replacement
    return new_lines


def _replace_current_baseline_entry(lines: list[str], draft: HandoffDraft) -> list[str]:
    heading_idx = _find_heading_index(lines, BASELINE_HEADING)
    section_end = _find_next_heading_index(lines, heading_idx)
    body_start = heading_idx + 1
    first_phase_idx = _find_first_phase_entry_index(lines, body_start, section_end)
    entry_lines = draft.current_baseline_entry_markdown.splitlines()

    updated = lines.copy()
    if first_phase_idx is None:
        insertion = entry_lines + [""]
        return updated[:body_start] + insertion + updated[body_start:]

    current_end = _find_next_top_level_bullet(updated, first_phase_idx + 1, section_end)
    if updated[first_phase_idx] == entry_lines[0]:
        blank_start = current_end
        while blank_start > first_phase_idx and updated[blank_start - 1] == "":
            blank_start -= 1
        trailing_blanks = updated[blank_start:current_end]
        replacement = entry_lines + trailing_blanks
        return updated[:first_phase_idx] + replacement + updated[current_end:]

    insertion = entry_lines + [""]
    return updated[:first_phase_idx] + insertion + updated[first_phase_idx:]


def _find_phase_history_start(lines: list[str], start_idx: int) -> int:
    for idx in range(start_idx, len(lines)):
        if PHASE_ENTRY_PATTERN.match(lines[idx]):
            return idx
    raise ValueError("Could not locate the historical phase-entry boundary after the corpus snapshot")


def _replace_recorder_and_corpus_block(lines: list[str], draft: HandoffDraft) -> list[str]:
    latest_idx = _find_unique_index(lines, LATEST_RECORDER_LINE)
    arn_idx = _find_unique_index(lines, ARN_SNAPSHOT_LINE)
    if latest_idx >= arn_idx:
        raise ValueError("Latest recorder block must appear before the ARN baseline snapshot")

    corpus_matches = [idx for idx, line in enumerate(lines) if CURRENT_CORPUS_PATTERN.match(line)]
    if len(corpus_matches) != 1:
        raise ValueError(f"Expected exactly one current corpus snapshot marker, found {len(corpus_matches)}")
    corpus_idx = corpus_matches[0]

    replacement_lines = draft.recorder_corpus_snapshot_markdown.splitlines()
    updated = lines.copy()
    if corpus_idx < arn_idx:
        return updated[:latest_idx] + replacement_lines + updated[arn_idx:]

    arn_block = updated[arn_idx:corpus_idx]
    history_start = _find_phase_history_start(updated, corpus_idx + 1)
    return updated[:latest_idx] + replacement_lines + arn_block + updated[history_start:]


def _replace_suggested_next_step(lines: list[str], draft: HandoffDraft) -> list[str]:
    heading_idx = _find_heading_index(lines, NEXT_STEP_HEADING)
    assumptions_idx = _find_heading_index(lines, ASSUMPTIONS_HEADING)
    if heading_idx >= assumptions_idx:
        raise ValueError("Suggested Next Step section must appear before Assumptions")

    body_lines = draft.suggested_next_step_markdown.splitlines()
    replacement = [NEXT_STEP_HEADING, ""] + body_lines + [""]
    return lines[:heading_idx] + replacement + lines[assumptions_idx:]


def apply_draft_to_handoff_text(handoff_text: str, draft: HandoffDraft) -> str:
    lines = handoff_text.splitlines()
    lines = _replace_header_metadata(lines, draft)
    lines = _replace_current_baseline_entry(lines, draft)
    lines = _replace_recorder_and_corpus_block(lines, draft)
    lines = _replace_suggested_next_step(lines, draft)
    return "\n".join(lines).rstrip() + "\n"


def _render_unified_diff(path: Path, original_text: str, updated_text: str) -> str:
    diff = difflib.unified_diff(
        original_text.splitlines(keepends=True),
        updated_text.splitlines(keepends=True),
        fromfile=str(path),
        tofile=f"{path} (updated)",
    )
    return "".join(diff)


def _render_preview_text(preview: HandoffApplyPreview) -> str:
    sections = [
        "=" * 60,
        "HANDOFF APPLY PREVIEW",
        "=" * 60,
        f"Target: {preview.handoff_path}",
        f"Write Requested: {preview.write_requested}",
        f"Changed: {preview.changed}",
        "",
        "Header Metadata Fragment:",
        preview.fragments["header_metadata_markdown"],
        "",
        "Current Baseline Entry Fragment:",
        preview.fragments["current_baseline_entry_markdown"],
        "",
        "Recorder / Corpus Fragment:",
        preview.fragments["recorder_corpus_snapshot_markdown"],
        "",
        "Suggested Next Step Fragment:",
        preview.fragments["suggested_next_step_markdown"],
        "",
        "Unified Diff:",
        preview.diff_text or "(no changes)",
    ]
    return "\n".join(sections).rstrip() + "\n"


def build_apply_preview(
    draft: HandoffDraft,
    handoff_path: Path,
    *,
    write_requested: bool,
) -> HandoffApplyPreview:
    original_text = handoff_path.read_text(encoding="utf-8-sig")
    updated_text = apply_draft_to_handoff_text(original_text, draft)
    diff_text = _render_unified_diff(handoff_path, original_text, updated_text)
    return HandoffApplyPreview(
        handoff_path=str(handoff_path),
        write_requested=write_requested,
        changed=original_text != updated_text,
        updated_text=updated_text,
        diff_text=diff_text,
        fragments={
            "header_metadata_markdown": draft.header_metadata_markdown,
            "current_baseline_entry_markdown": draft.current_baseline_entry_markdown,
            "recorder_corpus_snapshot_markdown": draft.recorder_corpus_snapshot_markdown,
            "suggested_next_step_markdown": draft.suggested_next_step_markdown,
        },
    )


def _atomic_write_text(path: Path, text: str) -> None:
    fd, tmp_name = tempfile.mkstemp(dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preview or apply a generated handoff draft to AI_HANDOFF.md.")
    parser.add_argument("phase_input", type=Path, help="Path to phase input JSON")
    parser.add_argument("--test-result", required=True, help="Top-line pytest result string for the header")
    parser.add_argument("--log-dir", type=Path, default=None, help="Optional override for recorder log discovery")
    parser.add_argument("--handoff-path", type=Path, default=Path("AI_HANDOFF.md"), help="Path to AI_HANDOFF.md")
    parser.add_argument("--write", action="store_true", help="Write updates to the handoff file instead of previewing only")
    parser.add_argument("--json", action="store_true", help="Emit structured preview JSON instead of text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    with args.phase_input.open("r", encoding="utf-8-sig") as handle:
        phase_input = PhaseInput.from_dict(json.load(handle))

    draft = build_handoff_draft(
        phase_input,
        args.test_result,
        log_dir=args.log_dir,
        handoff_path=args.handoff_path,
    )
    preview = build_apply_preview(draft, args.handoff_path, write_requested=args.write)

    if args.write:
        _atomic_write_text(args.handoff_path, preview.updated_text)

    rendered = json.dumps(preview.to_dict(), indent=2, ensure_ascii=False) if args.json else _render_preview_text(preview)
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
