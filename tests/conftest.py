from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from sts_py.tools.compare_logs import JavaGameLog
from sts_py.tools.log_discovery import CORPUS_LOG_SPECS_BY_LABEL, require_corpus_log_path

TMP_ROOT = Path.cwd() / "runtime_tmp"


def _require_corpus_log(label: str) -> Path:
    return require_corpus_log_path(CORPUS_LOG_SPECS_BY_LABEL[label])


@pytest.fixture
def workspace_tmp_path() -> Path:
    """Create a repo-local temp directory that avoids system tmp permission issues."""
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix="workspace_tmp_", dir=TMP_ROOT))
    try:
        yield tmp_dir
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def tmp_path(workspace_tmp_path: Path) -> Path:
    """Route pytest's default tmp_path usage into the repo-local writable temp root."""
    return workspace_tmp_path


@pytest.fixture(scope="module")
def real_java_log_path() -> Path:
    return _require_corpus_log("primary")


@pytest.fixture(scope="module")
def real_java_log(real_java_log_path: Path) -> JavaGameLog:
    return JavaGameLog.from_file(real_java_log_path)


@pytest.fixture(scope="module")
def second_real_java_log_path() -> Path:
    return _require_corpus_log("secondary")


@pytest.fixture(scope="module")
def second_real_java_log(second_real_java_log_path: Path) -> JavaGameLog:
    return JavaGameLog.from_file(second_real_java_log_path)


@pytest.fixture(scope="module")
def third_real_java_log_path() -> Path:
    return _require_corpus_log("tertiary")


@pytest.fixture(scope="module")
def third_real_java_log(third_real_java_log_path: Path) -> JavaGameLog:
    return JavaGameLog.from_file(third_real_java_log_path)


@pytest.fixture(scope="module")
def fourth_real_java_log_path() -> Path:
    return _require_corpus_log("quaternary")


@pytest.fixture(scope="module")
def fourth_real_java_log(fourth_real_java_log_path: Path) -> JavaGameLog:
    return JavaGameLog.from_file(fourth_real_java_log_path)


@pytest.fixture(scope="module")
def fifth_real_java_log_path() -> Path:
    return _require_corpus_log("quinary")


@pytest.fixture(scope="module")
def fifth_real_java_log(fifth_real_java_log_path: Path) -> JavaGameLog:
    return JavaGameLog.from_file(fifth_real_java_log_path)


@pytest.fixture(scope="module")
def sixth_real_java_log_path() -> Path:
    return _require_corpus_log("senary")


@pytest.fixture(scope="module")
def sixth_real_java_log(sixth_real_java_log_path: Path) -> JavaGameLog:
    return JavaGameLog.from_file(sixth_real_java_log_path)


@pytest.fixture(scope="module")
def seventh_real_java_log_path() -> Path:
    return _require_corpus_log("septenary")


@pytest.fixture(scope="module")
def seventh_real_java_log(seventh_real_java_log_path: Path) -> JavaGameLog:
    return JavaGameLog.from_file(seventh_real_java_log_path)


@pytest.fixture(scope="module")
def eighth_real_java_log_path() -> Path:
    return _require_corpus_log("octonary")


@pytest.fixture(scope="module")
def eighth_real_java_log(eighth_real_java_log_path: Path) -> JavaGameLog:
    return JavaGameLog.from_file(eighth_real_java_log_path)


@pytest.fixture(scope="module")
def ninth_real_java_log_path() -> Path:
    return _require_corpus_log("nonary")


@pytest.fixture(scope="module")
def ninth_real_java_log(ninth_real_java_log_path: Path) -> JavaGameLog:
    return JavaGameLog.from_file(ninth_real_java_log_path)


@pytest.fixture(scope="module")
def tenth_real_java_log_path() -> Path:
    return _require_corpus_log("denary")


@pytest.fixture(scope="module")
def tenth_real_java_log(tenth_real_java_log_path: Path) -> JavaGameLog:
    return JavaGameLog.from_file(tenth_real_java_log_path)
