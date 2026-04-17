from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sts_py.tools.compare_logs import JavaGameLog
from sts_py.tools.ground_truth_harness import run_harness
from sts_py.tools.log_discovery import ResolvedCorpusLog, discover_java_logs, resolve_available_corpus_logs


@dataclass(frozen=True)
class PhaseInput:
    phase_number: int
    phase_title: str
    phase_summary: list[str]
    verified_commands: list[str]
    next_step_lines: list[str] | None = None

    @property
    def latest_phase_line(self) -> str:
        return f"Phase {self.phase_number} - {self.phase_title}"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PhaseInput":
        allowed = {
            "phase_number",
            "phase_title",
            "phase_summary",
            "verified_commands",
            "next_step_lines",
        }
        required = {
            "phase_number",
            "phase_title",
            "phase_summary",
            "verified_commands",
        }
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ValueError(f"Unsupported phase input keys: {', '.join(unknown)}")
        missing = sorted(required - set(data))
        if missing:
            raise ValueError(f"Missing required phase input keys: {', '.join(missing)}")

        phase_summary = data["phase_summary"]
        verified_commands = data["verified_commands"]
        next_step_lines = data.get("next_step_lines")
        if not isinstance(phase_summary, list) or not all(isinstance(item, str) for item in phase_summary):
            raise ValueError("phase_summary must be a list of strings")
        if not isinstance(verified_commands, list) or not all(isinstance(item, str) for item in verified_commands):
            raise ValueError("verified_commands must be a list of strings")
        if next_step_lines is not None and (
            not isinstance(next_step_lines, list) or not all(isinstance(item, str) for item in next_step_lines)
        ):
            raise ValueError("next_step_lines must be a list of strings when provided")

        return cls(
            phase_number=int(data["phase_number"]),
            phase_title=str(data["phase_title"]),
            phase_summary=list(phase_summary),
            verified_commands=list(verified_commands),
            next_step_lines=list(next_step_lines) if next_step_lines is not None else None,
        )


@dataclass(frozen=True)
class CorpusHarnessSummary:
    label: str
    filename: str
    path: str
    ok: bool
    checked: int
    diff_count: int
    first_mismatch: str
    character: str | None = None
    run_result: str | None = None
    end_floor: int | None = None


@dataclass(frozen=True)
class HandoffDraft:
    header_metadata: dict[str, str]
    header_metadata_markdown: str
    latest_verified_local_recorder_log: str | None
    corpus_summaries: list[CorpusHarnessSummary]
    aggregated_corpus_totals: dict[str, int]
    current_baseline_entry_markdown: str
    recorder_corpus_snapshot_markdown: str
    suggested_next_step_markdown: str
    markdown_draft: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "header_metadata": self.header_metadata,
            "header_metadata_markdown": self.header_metadata_markdown,
            "latest_verified_local_recorder_log": self.latest_verified_local_recorder_log,
            "corpus_summaries": [asdict(summary) for summary in self.corpus_summaries],
            "aggregated_corpus_totals": self.aggregated_corpus_totals,
            "current_baseline_entry_markdown": self.current_baseline_entry_markdown,
            "recorder_corpus_snapshot_markdown": self.recorder_corpus_snapshot_markdown,
            "suggested_next_step_markdown": self.suggested_next_step_markdown,
            "markdown_draft": self.markdown_draft,
        }


def _format_first_mismatch(mismatch: dict[str, Any] | None) -> str:
    if not mismatch:
        return "none"

    floor = mismatch.get("floor")
    category = mismatch.get("category")
    field = mismatch.get("field")
    prefix = f"F{floor}" if floor is not None else "unknown"
    if category and field:
        return f"{prefix} {category}.{field}"
    if category:
        return f"{prefix} {category}"
    if field:
        return f"{prefix} {field}"
    return prefix


def summarize_harness_report(resolved_log: ResolvedCorpusLog) -> CorpusHarnessSummary:
    report = run_harness(resolved_log.path)
    java_log = JavaGameLog.from_file(resolved_log.path)
    diff_count = len(report.diff.mismatches)
    return CorpusHarnessSummary(
        label=resolved_log.spec.label,
        filename=resolved_log.path.name,
        path=str(resolved_log.path),
        ok=report.diff.ok,
        checked=len(report.diff.checked_floors),
        diff_count=diff_count,
        first_mismatch=_format_first_mismatch(report.diff.first_mismatch),
        character=getattr(java_log, "character", None),
        run_result=getattr(java_log, "run_result", None),
        end_floor=getattr(java_log, "end_floor", None),
    )


def summarize_corpus_logs(resolved_logs: list[ResolvedCorpusLog]) -> list[CorpusHarnessSummary]:
    return [summarize_harness_report(resolved_log) for resolved_log in resolved_logs]


def _render_phase_entry(phase_input: PhaseInput) -> str:
    lines = [f"- {phase_input.latest_phase_line}:"]
    for bullet in phase_input.phase_summary:
        lines.append(f"  - {bullet}")
    lines.append("  - verified with:")
    for command in phase_input.verified_commands:
        lines.append(f"    - `{command}`")
    return "\n".join(lines)


def _render_header_metadata_block(header_metadata: dict[str, str]) -> str:
    return "\n".join(
        [
            f"> Updated: {header_metadata['updated']}",
            f"> Latest phase: {header_metadata['latest_phase']}",
            f"> Current test result: `{header_metadata['current_test_result']}`",
        ]
    )


def _render_corpus_snapshot_block(
    latest_log: str | None,
    summaries: list[CorpusHarnessSummary],
    totals: dict[str, int],
) -> str:
    lines: list[str] = [
        "- Latest verified local recorder log:",
        f"  `{latest_log}`" if latest_log is not None else "  `none`",
        "",
        "- Current local corpus snapshot:",
    ]
    for summary in summaries:
        lines.append(f"  - {summary.label} `{summary.filename}`:")
        lines.append(f"    - `ok = {summary.ok}`")
        lines.append(f"    - `checked = {summary.checked}`")
        lines.append(f"    - `diff_count = {summary.diff_count}`")
        lines.append(f"    - `first mismatch = {summary.first_mismatch}`")
        if summary.character:
            lines.append(f"    - `character = {summary.character}`")
        if summary.run_result and summary.run_result != "unknown":
            lines.append(f"    - `run_result = {summary.run_result}`")
        if summary.end_floor is not None:
            lines.append(f"    - `end_floor = {summary.end_floor}`")
    lines.append("  - Total current corpus snapshot:")
    lines.append(f"    - `checked = {totals['checked']}`")
    lines.append(f"    - `matched = {totals['matched']}`")
    lines.append(f"    - `residual = {totals['residual']}`")
    return "\n".join(lines)


def _extract_markdown_section(handoff_text: str, heading: str) -> list[str]:
    lines = handoff_text.splitlines()
    start_idx: int | None = None
    for idx, line in enumerate(lines):
        if line.strip() == heading:
            start_idx = idx + 1
            break
    if start_idx is None:
        return []

    section_lines: list[str] = []
    for line in lines[start_idx:]:
        if line.startswith("## "):
            break
        section_lines.append(line)
    while section_lines and section_lines[0] == "":
        section_lines.pop(0)
    while section_lines and section_lines[-1] == "":
        section_lines.pop()
    return section_lines


def _load_default_next_step_lines(handoff_path: Path) -> list[str]:
    if not handoff_path.exists():
        return []
    return _extract_markdown_section(handoff_path.read_text(encoding="utf-8-sig"), "## 6. Suggested Next Step")


def _render_markdown_draft(
    header_metadata_markdown: str,
    phase_entry_markdown: str,
    corpus_snapshot_markdown: str,
    next_step_lines: list[str],
) -> str:
    sections = [
        "## Header Metadata",
        header_metadata_markdown,
        "",
        "## Current Baseline Entry",
        phase_entry_markdown,
        "",
        "## Corpus Snapshot Block",
        corpus_snapshot_markdown,
        "",
        "## Suggested Next Step",
        *next_step_lines,
    ]
    return "\n".join(sections).rstrip() + "\n"


def build_handoff_draft(
    phase_input: PhaseInput,
    test_result: str,
    *,
    log_dir: Path | None = None,
    handoff_path: Path | None = None,
    today: date | None = None,
) -> HandoffDraft:
    handoff_path = handoff_path or Path("AI_HANDOFF.md")
    today = today or date.today()

    latest_logs = discover_java_logs(log_dir=log_dir)
    latest_verified_local_recorder_log = str(latest_logs[0]) if latest_logs else None

    resolved_logs = resolve_available_corpus_logs(log_dir=log_dir)
    corpus_summaries = summarize_corpus_logs(resolved_logs)
    total_checked = sum(summary.checked for summary in corpus_summaries)
    total_residual = sum(summary.diff_count for summary in corpus_summaries)
    aggregated_corpus_totals = {
        "checked": total_checked,
        "matched": total_checked - total_residual,
        "residual": total_residual,
    }

    header_metadata = {
        "updated": today.isoformat(),
        "latest_phase": phase_input.latest_phase_line,
        "current_test_result": test_result,
    }
    header_metadata_markdown = _render_header_metadata_block(header_metadata)
    phase_entry_markdown = _render_phase_entry(phase_input)
    next_step_lines = phase_input.next_step_lines or _load_default_next_step_lines(handoff_path)
    corpus_snapshot_markdown = _render_corpus_snapshot_block(
        latest_verified_local_recorder_log,
        corpus_summaries,
        aggregated_corpus_totals,
    )
    markdown_draft = _render_markdown_draft(
        header_metadata_markdown,
        phase_entry_markdown,
        corpus_snapshot_markdown,
        next_step_lines,
    )

    return HandoffDraft(
        header_metadata=header_metadata,
        header_metadata_markdown=header_metadata_markdown,
        latest_verified_local_recorder_log=latest_verified_local_recorder_log,
        corpus_summaries=corpus_summaries,
        aggregated_corpus_totals=aggregated_corpus_totals,
        current_baseline_entry_markdown=phase_entry_markdown,
        recorder_corpus_snapshot_markdown=corpus_snapshot_markdown,
        suggested_next_step_markdown="\n".join(next_step_lines),
        markdown_draft=markdown_draft,
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a paste-ready AI_HANDOFF draft from corpus harness data.")
    parser.add_argument("phase_input", type=Path, help="Path to phase input JSON")
    parser.add_argument("--test-result", required=True, help="Top-line pytest result string for the header")
    parser.add_argument("--log-dir", type=Path, default=None, help="Optional override for recorder log discovery")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON instead of Markdown")
    parser.add_argument("--output", type=Path, default=None, help="Optional output path; stdout by default")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    with args.phase_input.open("r", encoding="utf-8-sig") as handle:
        phase_input = PhaseInput.from_dict(json.load(handle))

    draft = build_handoff_draft(
        phase_input,
        args.test_result,
        log_dir=args.log_dir,
    )
    rendered = json.dumps(draft.to_dict(), indent=2, ensure_ascii=False) if args.json else draft.markdown_draft

    if args.output is not None:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
