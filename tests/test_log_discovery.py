from __future__ import annotations

from pathlib import Path

import pytest

from sts_py.tools.log_discovery import (
    CORPUS_LOG_SPECS_BY_LABEL,
    DEFAULT_LOG_DIR,
    discover_java_logs,
    require_corpus_log_path,
    require_java_log_path,
    resolve_available_corpus_logs,
    resolve_java_log_path,
)


def _touch_log(path: Path) -> None:
    path.write_text("{}", encoding="utf-8")


def test_resolve_java_log_path_prefers_explicit_env(monkeypatch, workspace_tmp_path) -> None:
    explicit = workspace_tmp_path / "explicit.json"
    fallback_dir = workspace_tmp_path / "logs"
    fallback_dir.mkdir()
    _touch_log(explicit)
    _touch_log(fallback_dir / "run_FALLBACK_1.json")

    monkeypatch.setenv("STS_JAVA_LOG", str(explicit))
    monkeypatch.setenv("STS_LOG_DIR", str(fallback_dir))

    assert resolve_java_log_path() == explicit.resolve()


def test_resolve_java_log_path_uses_latest_log_from_dir(monkeypatch, workspace_tmp_path) -> None:
    first = workspace_tmp_path / "run_OLDER_1.json"
    second = workspace_tmp_path / "run_NEWER_2.json"
    _touch_log(first)
    _touch_log(second)

    monkeypatch.delenv("STS_JAVA_LOG", raising=False)
    monkeypatch.setenv("STS_LOG_DIR", str(workspace_tmp_path))

    logs = discover_java_logs()
    assert logs == [second.resolve(), first.resolve()]
    assert resolve_java_log_path() == second.resolve()


def test_require_java_log_path_skips_when_no_logs_available(monkeypatch) -> None:
    monkeypatch.delenv("STS_JAVA_LOG", raising=False)
    monkeypatch.delenv("STS_LOG_DIR", raising=False)

    fake_default = DEFAULT_LOG_DIR / "definitely_missing_for_test"
    with pytest.MonkeyPatch.context() as nested:
        nested.setattr("sts_py.tools.log_discovery.DEFAULT_LOG_DIR", fake_default)
        with pytest.raises(pytest.skip.Exception):
            require_java_log_path()


def test_second_log_fallback_uses_next_available_log(monkeypatch, workspace_tmp_path) -> None:
    first = workspace_tmp_path / "run_LATEST_2.json"
    second = workspace_tmp_path / "run_OLDER_1.json"
    _touch_log(second)
    _touch_log(first)

    monkeypatch.delenv("STS_JAVA_LOG_2", raising=False)
    monkeypatch.setenv("STS_LOG_DIR", str(workspace_tmp_path))

    assert resolve_java_log_path(env_var="STS_JAVA_LOG_2", fallback_index=1) == second.resolve()


def test_third_log_fallback_uses_third_available_log(monkeypatch, workspace_tmp_path) -> None:
    first = workspace_tmp_path / "run_LATEST_3.json"
    second = workspace_tmp_path / "run_MIDDLE_2.json"
    third = workspace_tmp_path / "run_OLDER_1.json"
    _touch_log(third)
    _touch_log(second)
    _touch_log(first)

    monkeypatch.delenv("STS_JAVA_LOG_3", raising=False)
    monkeypatch.setenv("STS_LOG_DIR", str(workspace_tmp_path))

    assert resolve_java_log_path(env_var="STS_JAVA_LOG_3", fallback_index=2) == third.resolve()


def test_resolve_java_log_path_prefers_named_baseline_over_newer_logs(monkeypatch, workspace_tmp_path) -> None:
    newest = workspace_tmp_path / "run_NEWEST_3.json"
    preferred = workspace_tmp_path / "run_BASELINE_1.json"
    middle = workspace_tmp_path / "run_MIDDLE_2.json"
    _touch_log(preferred)
    _touch_log(middle)
    _touch_log(newest)

    monkeypatch.delenv("STS_JAVA_LOG", raising=False)
    monkeypatch.setenv("STS_LOG_DIR", str(workspace_tmp_path))

    assert resolve_java_log_path(preferred_filename="run_BASELINE_1.json") == preferred.resolve()


def test_require_java_log_path_uses_preferred_filename_before_index(monkeypatch, workspace_tmp_path) -> None:
    newest = workspace_tmp_path / "run_NEWEST_3.json"
    preferred = workspace_tmp_path / "run_TARGET_1.json"
    middle = workspace_tmp_path / "run_MIDDLE_2.json"
    _touch_log(preferred)
    _touch_log(middle)
    _touch_log(newest)

    monkeypatch.delenv("STS_JAVA_LOG_6", raising=False)
    monkeypatch.setenv("STS_LOG_DIR", str(workspace_tmp_path))

    assert require_java_log_path(
        env_var="STS_JAVA_LOG_6",
        fallback_index=2,
        preferred_filename="run_TARGET_1.json",
        label="Sixth Java recorder log",
    ) == preferred.resolve()


def test_require_corpus_log_path_uses_shared_registry(monkeypatch, workspace_tmp_path) -> None:
    preferred = workspace_tmp_path / CORPUS_LOG_SPECS_BY_LABEL["primary"].preferred_filename
    _touch_log(preferred)

    monkeypatch.delenv("STS_JAVA_LOG", raising=False)
    monkeypatch.setenv("STS_LOG_DIR", str(workspace_tmp_path))

    assert require_corpus_log_path(CORPUS_LOG_SPECS_BY_LABEL["primary"]) == preferred.resolve()


def test_resolve_available_corpus_logs_skips_duplicate_paths(monkeypatch, workspace_tmp_path) -> None:
    only_log = workspace_tmp_path / CORPUS_LOG_SPECS_BY_LABEL["primary"].preferred_filename
    _touch_log(only_log)

    monkeypatch.delenv("STS_JAVA_LOG", raising=False)
    monkeypatch.delenv("STS_JAVA_LOG_2", raising=False)
    monkeypatch.setenv("STS_LOG_DIR", str(workspace_tmp_path))

    resolved = resolve_available_corpus_logs()
    assert [entry.spec.label for entry in resolved] == ["primary"]
    assert [entry.path for entry in resolved] == [only_log.resolve()]
