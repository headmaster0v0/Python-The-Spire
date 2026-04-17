from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

COMMON_IGNORE_ARGS = [
    "--ignore=.pytest_tmp",
    "--ignore=runtime_tmp",
    "--ignore=.pytest_cache",
    "--ignore=tests/_tmp_workspace",
    "--ignore=tests/_tmp_workspace_manual2",
    "--ignore=tests/_tmp_workspace_probe",
    "--ignore=tests/_tmp_workspace_probe2",
]

HARNESS_TEST = "tests/test_harness_smoke.py"
TIMING_CACHE_SCHEMA_VERSION = 1
TIMING_CACHE_RELATIVE_PATH = Path(".pytest_tmp") / "dev_checks_timings.json"
REPORTS_DIR_RELATIVE_PATH = Path(".pytest_tmp") / "dev_checks_reports"
SMOKE_TESTS = [
    "tests/test_phase265_post_ship_maintenance.py",
    "tests/test_phase264_closeout_ship_checklist.py",
    "tests/test_wiki_audit.py",
    "tests/test_full_campaign_stability.py",
]


@dataclass(frozen=True)
class ShardResult:
    index: int
    items: list[str]
    command: list[str]
    duration_s: float
    returncode: int
    stdout: str
    stderr: str
    file_timings_s: dict[str, float]
    nodeid_timings_s: dict[str, float]
def timing_cache_path(repo_root: Path) -> Path:
    return repo_root / TIMING_CACHE_RELATIVE_PATH


def _reports_dir(repo_root: Path) -> Path:
    return repo_root / REPORTS_DIR_RELATIVE_PATH


def empty_timing_cache() -> dict[str, object]:
    return {
        "schema_version": TIMING_CACHE_SCHEMA_VERSION,
        "files": {},
        "nodeids": {},
    }


def _tests_dir(repo_root: Path) -> Path:
    return repo_root / "tests"


def discover_test_files(repo_root: Path) -> list[str]:
    tests_dir = _tests_dir(repo_root)
    return sorted(path.relative_to(repo_root).as_posix() for path in tests_dir.glob("test_*.py"))


def resolve_profile_items(repo_root: Path, profile: str) -> list[str]:
    all_tests = discover_test_files(repo_root)
    if profile == "smoke":
        return SMOKE_TESTS.copy()
    if profile == "harness":
        return [HARNESS_TEST]
    if profile == "fast":
        return [path for path in all_tests if path != HARNESS_TEST]
    if profile == "full":
        return all_tests
    raise ValueError(f"unknown profile: {profile}")


def default_jobs_for_profile(profile: str) -> int:
    cpu_count = os.cpu_count() or 2
    if profile == "smoke":
        return 1
    if profile == "fast":
        return 2
    if profile in {"harness", "full"}:
        return max(1, min(4, cpu_count))
    raise ValueError(f"unknown profile: {profile}")


def resolve_jobs(profile: str, requested_jobs: int | None) -> int:
    if requested_jobs is None:
        return default_jobs_for_profile(profile)
    return max(1, requested_jobs)


def split_items_evenly(items: Sequence[str], shard_count: int) -> list[list[str]]:
    if shard_count <= 1:
        return [list(items)]
    shards = [[] for _ in range(shard_count)]
    for index, item in enumerate(items):
        shards[index % shard_count].append(item)
    return [shard for shard in shards if shard]


def balance_items_by_weight(
    items: Sequence[str],
    shard_count: int,
    weight_lookup: Callable[[str], float],
) -> list[list[str]]:
    if shard_count <= 1:
        return [list(items)]
    shards = [[] for _ in range(shard_count)]
    weights = [0.0] * shard_count
    for item in sorted(items, key=lambda current: (-weight_lookup(current), current)):
        shard_index = min(range(shard_count), key=lambda idx: weights[idx])
        shards[shard_index].append(item)
        weights[shard_index] += weight_lookup(item)
    return [shard for shard in shards if shard]


def balance_paths_by_size(
    paths: Sequence[str],
    shard_count: int,
    size_lookup: Callable[[str], int],
) -> list[list[str]]:
    return balance_items_by_weight(paths, shard_count, lambda path: float(size_lookup(path)))


def collect_nodeids(repo_root: Path, target: str) -> list[str]:
    command = [sys.executable, "-m", "pytest", "--collect-only", "-q", *COMMON_IGNORE_ARGS, target]
    completed = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"pytest collection failed for {target}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    nodeids: list[str] = []
    for line in completed.stdout.splitlines():
        candidate = line.strip()
        if "::" not in candidate:
            continue
        if candidate.startswith("tests/") or candidate.startswith("tests\\"):
            nodeids.append(candidate.replace("\\", "/"))
    if not nodeids:
        raise RuntimeError(f"no pytest node ids collected for {target}")
    return nodeids


def load_timing_cache(repo_root: Path) -> dict[str, object]:
    cache_path = timing_cache_path(repo_root)
    if not cache_path.exists():
        return empty_timing_cache()
    try:
        loaded = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return empty_timing_cache()
    if loaded.get("schema_version") != TIMING_CACHE_SCHEMA_VERSION:
        return empty_timing_cache()
    return {
        "schema_version": TIMING_CACHE_SCHEMA_VERSION,
        "files": {str(key): float(value) for key, value in dict(loaded.get("files") or {}).items()},
        "nodeids": {str(key): float(value) for key, value in dict(loaded.get("nodeids") or {}).items()},
    }


def save_timing_cache(repo_root: Path, cache: dict[str, object]) -> None:
    cache_path = timing_cache_path(repo_root)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    serializable = {
        "schema_version": TIMING_CACHE_SCHEMA_VERSION,
        "files": dict(cache.get("files") or {}),
        "nodeids": dict(cache.get("nodeids") or {}),
    }
    tmp_path = cache_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(serializable, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(cache_path)


def merge_timing_cache(base_cache: dict[str, object], results: Sequence[ShardResult]) -> dict[str, object]:
    merged = {
        "schema_version": TIMING_CACHE_SCHEMA_VERSION,
        "files": dict(base_cache.get("files") or {}),
        "nodeids": dict(base_cache.get("nodeids") or {}),
    }
    file_timings = dict(merged["files"])
    nodeid_timings = dict(merged["nodeids"])
    for result in results:
        file_timings.update(result.file_timings_s)
        nodeid_timings.update(result.nodeid_timings_s)
    merged["files"] = file_timings
    merged["nodeids"] = nodeid_timings
    return merged


def _timing_bucket_has_all(bucket: dict[str, float], items: Sequence[str]) -> bool:
    return bool(items) and all(item in bucket for item in items)


def _testcase_file_from_classname(classname: str) -> str | None:
    parts = [part for part in classname.split(".") if part]
    if not parts:
        return None
    try:
        tests_index = parts.index("tests")
    except ValueError:
        return None
    module_parts: list[str] = []
    for part in parts[tests_index:]:
        module_parts.append(part)
        if part.startswith("test_"):
            return "/".join(module_parts) + ".py"
    return None


def _testcase_nodeid(classname: str, name: str) -> str | None:
    parts = [part for part in classname.split(".") if part]
    if not parts:
        return None
    try:
        tests_index = parts.index("tests")
    except ValueError:
        return None
    module_parts: list[str] = []
    module_end_index = tests_index
    for offset, part in enumerate(parts[tests_index:], start=tests_index):
        module_parts.append(part)
        module_end_index = offset
        if part.startswith("test_"):
            break
    else:
        return None
    nodeid = "/".join(module_parts) + ".py"
    class_parts = parts[module_end_index + 1 :]
    if class_parts:
        nodeid += "::" + "::".join(class_parts)
    return f"{nodeid}::{name}"


def parse_junit_timings(report_path: Path, selected_items: Sequence[str]) -> tuple[dict[str, float], dict[str, float]]:
    if not report_path.exists():
        return {}, {}
    try:
        root = ET.parse(report_path).getroot()
    except (ET.ParseError, OSError):
        return {}, {}

    selected_files = {item for item in selected_items if "::" not in item}
    selected_nodeids = {item for item in selected_items if "::" in item}
    file_timings: dict[str, float] = {}
    nodeid_timings: dict[str, float] = {}

    for testcase in root.iter("testcase"):
        classname = testcase.attrib.get("classname", "")
        name = testcase.attrib.get("name", "")
        try:
            duration_s = float(testcase.attrib.get("time", "0") or 0.0)
        except ValueError:
            duration_s = 0.0
        file_path = _testcase_file_from_classname(classname)
        if file_path is not None and file_path in selected_files:
            file_timings[file_path] = file_timings.get(file_path, 0.0) + duration_s
        nodeid = _testcase_nodeid(classname, name)
        if nodeid is not None and nodeid in selected_nodeids:
            nodeid_timings[nodeid] = nodeid_timings.get(nodeid, 0.0) + duration_s
    return file_timings, nodeid_timings


def build_shards(
    repo_root: Path,
    items: Sequence[str],
    shard_count: int,
    harness_nodeids: Sequence[str] | None = None,
    timing_cache: dict[str, object] | None = None,
) -> list[list[str]]:
    if shard_count <= 1:
        return [list(items)]

    non_harness_paths = [item for item in items if item != HARNESS_TEST]

    def size_lookup(path: str) -> int:
        try:
            return (repo_root / Path(path)).stat().st_size
        except OSError:
            return 0

    file_timing_bucket = {
        str(key): float(value)
        for key, value in dict((timing_cache or {}).get("files") or {}).items()
    }
    if _timing_bucket_has_all(file_timing_bucket, non_harness_paths):
        shards = balance_items_by_weight(non_harness_paths, shard_count, lambda path: file_timing_bucket[path])
    else:
        shards = balance_paths_by_size(non_harness_paths, shard_count, size_lookup)
    if len(shards) < shard_count:
        shards.extend([[] for _ in range(shard_count - len(shards))])

    if HARNESS_TEST in items:
        nodeids = list(harness_nodeids) if harness_nodeids is not None else collect_nodeids(repo_root, HARNESS_TEST)
        nodeid_timing_bucket = {
            str(key): float(value)
            for key, value in dict((timing_cache or {}).get("nodeids") or {}).items()
        }
        if _timing_bucket_has_all(nodeid_timing_bucket, nodeids):
            harness_shards = balance_items_by_weight(nodeids, shard_count, lambda nodeid: nodeid_timing_bucket[nodeid])
        else:
            harness_shards = split_items_evenly(nodeids, shard_count)
        for shard_index, nodeid_shard in enumerate(harness_shards):
            shards[shard_index].extend(nodeid_shard)

    return [shard for shard in shards if shard]


def build_pytest_command(items: Sequence[str], extra_pytest_args: Sequence[str]) -> list[str]:
    return [sys.executable, "-m", "pytest", "-q", *COMMON_IGNORE_ARGS, *items, *extra_pytest_args]


def _build_internal_pytest_command(
    items: Sequence[str],
    extra_pytest_args: Sequence[str],
    report_path: Path | None = None,
) -> list[str]:
    command = build_pytest_command(items, extra_pytest_args)
    if report_path is not None:
        command.append(f"--junitxml={report_path.as_posix()}")
    return command


def _report_path_for_shard(repo_root: Path, shard_index: int) -> Path:
    reports_dir = _reports_dir(repo_root)
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir / f"shard_{shard_index}.xml"


def _supports_timing_capture(extra_pytest_args: Sequence[str]) -> bool:
    return not extra_pytest_args


def run_shard(repo_root: Path, shard_index: int, items: Sequence[str], extra_pytest_args: Sequence[str]) -> ShardResult:
    report_path = _report_path_for_shard(repo_root, shard_index) if _supports_timing_capture(extra_pytest_args) else None
    command = _build_internal_pytest_command(items, extra_pytest_args, report_path=report_path)
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    duration_s = time.perf_counter() - started
    file_timings_s, nodeid_timings_s = parse_junit_timings(report_path, items) if report_path is not None else ({}, {})
    if report_path is not None:
        try:
            report_path.unlink()
        except OSError:
            pass
    return ShardResult(
        index=shard_index,
        items=list(items),
        command=command,
        duration_s=duration_s,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        file_timings_s=file_timings_s,
        nodeid_timings_s=nodeid_timings_s,
    )


def _print_shard_result(result: ShardResult) -> None:
    print(f"[shard {result.index}] {' '.join(result.command)}")
    print(f"[shard {result.index}] exit={result.returncode} duration={result.duration_s:.1f}s")
    if result.stdout.strip():
        print(result.stdout.rstrip())
    if result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr)


def _format_rerun_command(items: Sequence[str], extra_pytest_args: Sequence[str]) -> str:
    return " ".join(build_pytest_command(items, extra_pytest_args))


def _shard_slowest_observed_item(result: ShardResult) -> tuple[str | None, float]:
    combined = dict(result.file_timings_s)
    combined.update(result.nodeid_timings_s)
    if not combined:
        return None, 0.0
    item, duration_s = max(combined.items(), key=lambda entry: (entry[1], entry[0]))
    return item, duration_s


def _print_run_summary(
    profile: str,
    results: Sequence[ShardResult],
    total_wall_s: float,
    extra_pytest_args: Sequence[str],
) -> None:
    if not results:
        return
    print(f"[summary] profile={profile} total_wall={total_wall_s:.1f}s shards={len(results)}")
    ordered_results = sorted(results, key=lambda result: result.index)
    for result in ordered_results:
        slowest_item, slowest_duration_s = _shard_slowest_observed_item(result)
        if slowest_item is None:
            print(f"[summary] shard={result.index} wall={result.duration_s:.1f}s")
        else:
            print(
                f"[summary] shard={result.index} wall={result.duration_s:.1f}s "
                f"slowest={slowest_item} observed={slowest_duration_s:.3f}s"
            )
    slowest_result = max(results, key=lambda result: (result.duration_s, result.index))
    print(f"[summary] slowest_shard={slowest_result.index} wall={slowest_result.duration_s:.1f}s")
    failed_results = [result for result in results if result.returncode != 0]
    if failed_results:
        rerun_result = max(failed_results, key=lambda result: (result.duration_s, result.index))
        print(f"[summary] rerun failed shard: {_format_rerun_command(rerun_result.items, extra_pytest_args)}")


def run_profile(
    repo_root: Path,
    profile: str,
    jobs: int | None,
    extra_pytest_args: Sequence[str],
    dry_run: bool = False,
) -> int:
    items = resolve_profile_items(repo_root, profile)
    resolved_jobs = resolve_jobs(profile, jobs)
    timing_cache = load_timing_cache(repo_root)
    harness_nodeids = None
    if resolved_jobs > 1 and HARNESS_TEST in items:
        harness_nodeids = collect_nodeids(repo_root, HARNESS_TEST)

    shards = build_shards(
        repo_root,
        items,
        resolved_jobs,
        harness_nodeids=harness_nodeids,
        timing_cache=timing_cache,
    )
    if dry_run:
        for shard_index, shard_items in enumerate(shards, start=1):
            print(" ".join(build_pytest_command(shard_items, extra_pytest_args)))
        return 0

    if len(shards) == 1:
        result = run_shard(repo_root, 1, shards[0], extra_pytest_args)
        _print_shard_result(result)
        _print_run_summary(profile, [result], result.duration_s, extra_pytest_args)
        if _supports_timing_capture(extra_pytest_args):
            save_timing_cache(repo_root, merge_timing_cache(timing_cache, [result]))
        return result.returncode

    failures = 0
    worker_count = min(resolved_jobs, len(shards))
    print(f"Running profile={profile} with {worker_count} parallel shards")
    started = time.perf_counter()
    results: list[ShardResult] = []
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_map = {
            executor.submit(run_shard, repo_root, index, shard_items, extra_pytest_args): index
            for index, shard_items in enumerate(shards, start=1)
        }
        for future in as_completed(future_map):
            result = future.result()
            results.append(result)
            _print_shard_result(result)
            if result.returncode != 0:
                failures += 1
    total_wall_s = time.perf_counter() - started
    _print_run_summary(profile, results, total_wall_s, extra_pytest_args)
    if _supports_timing_capture(extra_pytest_args):
        save_timing_cache(repo_root, merge_timing_cache(timing_cache, results))
    return 0 if failures == 0 else 1


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run fast local STS pytest profiles without defaulting to the slow harness lane."
    )
    parser.add_argument(
        "--profile",
        choices=["smoke", "fast", "harness", "full"],
        default="smoke",
        help="smoke=daily maintenance, fast=all tests except harness, harness=harness only, full=everything",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=None,
        help="number of parallel pytest shards; if omitted, the default is profile-aware and harness is split by node id",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the pytest command(s) without running them",
    )
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER, help="extra pytest args after '--'")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path.cwd()
    extra_pytest_args = list(args.pytest_args)
    if extra_pytest_args and extra_pytest_args[0] == "--":
        extra_pytest_args = extra_pytest_args[1:]
    return run_profile(repo_root, args.profile, args.jobs, extra_pytest_args, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
