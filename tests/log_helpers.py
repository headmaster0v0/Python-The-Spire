from __future__ import annotations

import os
from pathlib import Path

import pytest

from sts_py.tools.log_discovery import (
    CORPUS_LOG_SPECS_BY_LABEL,
    DEFAULT_LOG_DIR,
    RUN_LOG_GLOB,
    discover_java_logs,
    get_corpus_log_spec,
    require_java_log_path,
    resolve_java_log_path,
)


def _resolve_log_dir(log_dir: Path | None = None) -> Path:
    chosen = os.environ.get("STS_LOG_DIR")
    return Path(chosen or log_dir or DEFAULT_LOG_DIR).expanduser().resolve()


def describe_optional_corpus_log_requirement(
    label: str,
    *,
    log_dir: Path | None = None,
) -> tuple[Path | None, str | None]:
    spec = get_corpus_log_spec(label)
    path = resolve_java_log_path(
        env_var=spec.env_var,
        fallback_index=spec.fallback_index,
        preferred_filename=spec.preferred_filename,
        log_dir=log_dir,
    )
    if path is not None:
        return path, None
    return None, f"optional local corpus log missing: {spec.label} ({spec.preferred_filename})"


def require_optional_corpus_log(label: str, *, log_dir: Path | None = None) -> Path:
    path, reason = describe_optional_corpus_log_requirement(label, log_dir=log_dir)
    if path is not None:
        return path
    pytest.skip(reason or f"optional local corpus log missing: {label}")


def describe_optional_recent_live_log_requirement(
    filename: str,
    *,
    human_label: str,
    log_dir: Path | None = None,
) -> tuple[Path | None, str | None]:
    chosen_dir = _resolve_log_dir(log_dir=log_dir)
    candidate = (chosen_dir / filename).resolve()
    if candidate.exists():
        return candidate, None
    return None, f"optional recent live log missing: {human_label} ({filename})"


def require_optional_recent_live_log(
    filename: str,
    *,
    human_label: str,
    log_dir: Path | None = None,
) -> Path:
    path, reason = describe_optional_recent_live_log_requirement(
        filename,
        human_label=human_label,
        log_dir=log_dir,
    )
    if path is not None:
        return path
    pytest.skip(reason or f"optional recent live log missing: {human_label}")


def require_checked_in_fixture(path: Path, *, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise AssertionError(f"checked-in fixture required: {label} ({resolved})")
    return resolved


__all__ = [
    "CORPUS_LOG_SPECS_BY_LABEL",
    "DEFAULT_LOG_DIR",
    "RUN_LOG_GLOB",
    "describe_optional_corpus_log_requirement",
    "describe_optional_recent_live_log_requirement",
    "discover_java_logs",
    "get_corpus_log_spec",
    "require_checked_in_fixture",
    "require_optional_corpus_log",
    "require_optional_recent_live_log",
    "require_java_log_path",
    "resolve_java_log_path",
]
