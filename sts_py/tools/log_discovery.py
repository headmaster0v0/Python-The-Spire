from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_LOG_DIR = Path.home() / "sts_data_logs"
RUN_LOG_GLOB = "run_*.json"


@dataclass(frozen=True)
class CorpusLogSpec:
    label: str
    env_var: str
    fallback_index: int
    preferred_filename: str
    human_label: str


@dataclass(frozen=True)
class ResolvedCorpusLog:
    spec: CorpusLogSpec
    path: Path


CORPUS_LOG_SPECS: tuple[CorpusLogSpec, ...] = (
    CorpusLogSpec("primary", "STS_JAVA_LOG", 0, "run_ARN01H96IRKX_1774512533560.json", "Java recorder log"),
    CorpusLogSpec("secondary", "STS_JAVA_LOG_2", 1, "run_4ZC8S2C0BGHJ5_1774511272164.json", "Second Java recorder log"),
    CorpusLogSpec("tertiary", "STS_JAVA_LOG_3", 2, "run_3Z682MZ5HICA5_1774505284645.json", "Third Java recorder log"),
    CorpusLogSpec("quaternary", "STS_JAVA_LOG_4", 3, "run_3KG27R6SZ2R8A_1775106066893.json", "Fourth Java recorder log"),
    CorpusLogSpec("quinary", "STS_JAVA_LOG_5", 4, "run_1PP3LEYCUGZC_1775108452915.json", "Fifth Java recorder log"),
    CorpusLogSpec("senary", "STS_JAVA_LOG_6", 5, "run_5FUAJSFY9CMEF_1775114007312.json", "Sixth Java recorder log"),
    CorpusLogSpec("septenary", "STS_JAVA_LOG_7", 6, "run_BQNI0J9Z4RG4_1775140624744.json", "Seventh Java recorder log"),
    CorpusLogSpec("octonary", "STS_JAVA_LOG_8", 7, "run_2QLWJXV32R1N_1775182902486.json", "Eighth Java recorder log"),
    CorpusLogSpec("nonary", "STS_JAVA_LOG_9", 8, "run_49NI25MN58GJ9_1775191352320.json", "Ninth Java recorder log"),
    CorpusLogSpec("denary", "STS_JAVA_LOG_10", 9, "run_40HU359J4UKQP_1775211053238.json", "Tenth Java recorder log"),
)

CORPUS_LOG_SPECS_BY_LABEL: dict[str, CorpusLogSpec] = {
    spec.label: spec for spec in CORPUS_LOG_SPECS
}


def _normalize_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def discover_java_logs(log_dir: Path | None = None) -> list[Path]:
    """Return available Java recorder logs sorted by newest first."""
    chosen_dir = log_dir
    if chosen_dir is None:
        env_dir = os.environ.get("STS_LOG_DIR")
        chosen_dir = _normalize_path(env_dir) if env_dir else DEFAULT_LOG_DIR
    else:
        chosen_dir = _normalize_path(chosen_dir)

    if not chosen_dir.exists() or not chosen_dir.is_dir():
        return []

    return sorted(
        (path.resolve() for path in chosen_dir.glob(RUN_LOG_GLOB)),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _resolve_preferred_log_path(
    logs: list[Path],
    preferred_filename: str | None = None,
) -> Path | None:
    if not preferred_filename:
        return None

    for path in logs:
        if path.name == preferred_filename:
            return path
    return None


def resolve_java_log_path(
    *,
    env_var: str = "STS_JAVA_LOG",
    fallback_index: int = 0,
    preferred_filename: str | None = None,
    log_dir: Path | None = None,
) -> Path | None:
    """Resolve a Java recorder log path from env override or latest local logs."""
    explicit_path = os.environ.get(env_var)
    if explicit_path:
        candidate = _normalize_path(explicit_path)
        return candidate if candidate.exists() else None

    logs = discover_java_logs(log_dir=log_dir)
    preferred_path = _resolve_preferred_log_path(logs, preferred_filename=preferred_filename)
    if preferred_path is not None:
        return preferred_path

    if fallback_index < 0 or fallback_index >= len(logs):
        return None
    return logs[fallback_index]


def require_java_log_path(
    *,
    env_var: str = "STS_JAVA_LOG",
    fallback_index: int = 0,
    preferred_filename: str | None = None,
    label: str = "Java recorder log",
    log_dir: Path | None = None,
) -> Path:
    """Resolve a Java log or raise a pytest skip with a clear reason."""
    import pytest

    path = resolve_java_log_path(
        env_var=env_var,
        fallback_index=fallback_index,
        preferred_filename=preferred_filename,
        log_dir=log_dir,
    )
    if path is not None:
        return path

    explicit_path = os.environ.get(env_var)
    if explicit_path:
        pytest.skip(f"{label} not found at configured {env_var}={explicit_path}")

    chosen_log_dir = _normalize_path(os.environ.get("STS_LOG_DIR") or log_dir or DEFAULT_LOG_DIR)
    pytest.skip(
        f"{label} not found; set {env_var} or place {RUN_LOG_GLOB} under {chosen_log_dir}"
    )


def get_corpus_log_spec(label: str) -> CorpusLogSpec:
    try:
        return CORPUS_LOG_SPECS_BY_LABEL[label]
    except KeyError as exc:
        raise KeyError(f"Unknown corpus log label: {label}") from exc


def require_corpus_log_path(spec: CorpusLogSpec, *, log_dir: Path | None = None) -> Path:
    return require_java_log_path(
        env_var=spec.env_var,
        fallback_index=spec.fallback_index,
        preferred_filename=spec.preferred_filename,
        label=spec.human_label,
        log_dir=log_dir,
    )


def resolve_available_corpus_logs(log_dir: Path | None = None) -> list[ResolvedCorpusLog]:
    resolved: list[ResolvedCorpusLog] = []
    seen_paths: set[Path] = set()
    for spec in CORPUS_LOG_SPECS:
        path = resolve_java_log_path(
            env_var=spec.env_var,
            fallback_index=spec.fallback_index,
            preferred_filename=spec.preferred_filename,
            log_dir=log_dir,
        )
        if path is None or path in seen_paths:
            continue
        resolved.append(ResolvedCorpusLog(spec=spec, path=path))
        seen_paths.add(path)
    return resolved
