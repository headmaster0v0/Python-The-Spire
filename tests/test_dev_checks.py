from __future__ import annotations

from pathlib import Path

import xml.etree.ElementTree as ET

from sts_py.tools.dev_checks import (
    HARNESS_TEST,
    SMOKE_TESTS,
    build_pytest_command,
    build_shards,
    default_jobs_for_profile,
    load_timing_cache,
    parse_args,
    parse_junit_timings,
    resolve_profile_items,
    resolve_jobs,
    save_timing_cache,
    timing_cache_path,
)


def test_fast_profile_excludes_harness_and_keeps_broad_suite() -> None:
    repo_root = Path.cwd()

    items = resolve_profile_items(repo_root, "fast")

    assert HARNESS_TEST not in items
    assert "tests/test_phase264_closeout_ship_checklist.py" in items
    assert "tests/test_playability_closure.py" in items


def test_smoke_profile_matches_checked_in_daily_chain() -> None:
    repo_root = Path.cwd()

    assert resolve_profile_items(repo_root, "smoke") == SMOKE_TESTS


def test_parse_args_defaults_to_smoke_profile_and_auto_jobs() -> None:
    args = parse_args([])

    assert args.profile == "smoke"
    assert args.jobs is None


def test_default_jobs_for_profile_is_profile_aware(monkeypatch) -> None:
    monkeypatch.setattr("sts_py.tools.dev_checks.os.cpu_count", lambda: 8)

    assert default_jobs_for_profile("smoke") == 1
    assert default_jobs_for_profile("fast") == 2
    assert default_jobs_for_profile("harness") == 4
    assert default_jobs_for_profile("full") == 4
    assert resolve_jobs("fast", None) == 2
    assert resolve_jobs("full", 3) == 3
    assert resolve_jobs("smoke", 0) == 1


def test_build_shards_splits_harness_by_nodeid_when_parallel_without_timing_cache() -> None:
    repo_root = Path.cwd()
    harness_nodeids = [
        "tests/test_harness_smoke.py::test_alpha",
        "tests/test_harness_smoke.py::test_beta",
        "tests/test_harness_smoke.py::test_gamma",
        "tests/test_harness_smoke.py::test_delta",
    ]

    shards = build_shards(
        repo_root,
        [HARNESS_TEST, "tests/test_phase265_post_ship_maintenance.py"],
        shard_count=2,
        harness_nodeids=harness_nodeids,
    )

    assert len(shards) == 2
    flattened = [item for shard in shards for item in shard]
    assert HARNESS_TEST not in flattened
    assert "tests/test_phase265_post_ship_maintenance.py" in flattened
    assert sorted(item for item in flattened if item.startswith("tests/test_harness_smoke.py::")) == sorted(harness_nodeids)


def test_build_shards_uses_timing_cache_for_non_harness_paths_when_complete(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    for name, size in (("test_alpha.py", 10), ("test_beta.py", 9), ("test_gamma.py", 8)):
        (tests_dir / name).write_text("x" * size, encoding="utf-8")

    shards = build_shards(
        tmp_path,
        ["tests/test_alpha.py", "tests/test_beta.py", "tests/test_gamma.py"],
        shard_count=2,
        timing_cache={
            "schema_version": 1,
            "files": {
                "tests/test_alpha.py": 9.0,
                "tests/test_beta.py": 4.0,
                "tests/test_gamma.py": 3.0,
            },
            "nodeids": {},
        },
    )

    assert shards == [["tests/test_alpha.py"], ["tests/test_beta.py", "tests/test_gamma.py"]]


def test_build_shards_falls_back_to_size_when_file_timing_cache_is_incomplete(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_alpha.py").write_text("a" * 300, encoding="utf-8")
    (tests_dir / "test_beta.py").write_text("b" * 120, encoding="utf-8")
    (tests_dir / "test_gamma.py").write_text("c" * 100, encoding="utf-8")

    shards = build_shards(
        tmp_path,
        ["tests/test_alpha.py", "tests/test_beta.py", "tests/test_gamma.py"],
        shard_count=2,
        timing_cache={
            "schema_version": 1,
            "files": {
                "tests/test_alpha.py": 9.0,
                "tests/test_beta.py": 4.0,
            },
            "nodeids": {},
        },
    )

    assert shards == [["tests/test_alpha.py"], ["tests/test_beta.py", "tests/test_gamma.py"]]


def test_build_shards_uses_timing_cache_for_harness_nodeids_when_complete() -> None:
    repo_root = Path.cwd()
    harness_nodeids = [
        "tests/test_harness_smoke.py::TestSuite::test_alpha",
        "tests/test_harness_smoke.py::TestSuite::test_beta",
        "tests/test_harness_smoke.py::TestSuite::test_gamma",
        "tests/test_harness_smoke.py::TestSuite::test_delta",
    ]

    shards = build_shards(
        repo_root,
        [HARNESS_TEST],
        shard_count=2,
        harness_nodeids=harness_nodeids,
        timing_cache={
            "schema_version": 1,
            "files": {},
            "nodeids": {
                harness_nodeids[0]: 8.0,
                harness_nodeids[1]: 6.0,
                harness_nodeids[2]: 5.0,
                harness_nodeids[3]: 1.0,
            },
        },
    )

    assert shards == [
        [harness_nodeids[0], harness_nodeids[3]],
        [harness_nodeids[1], harness_nodeids[2]],
    ]


def test_load_and_save_timing_cache_round_trip(tmp_path: Path) -> None:
    cache = {
        "schema_version": 1,
        "files": {"tests/test_alpha.py": 1.5},
        "nodeids": {"tests/test_harness_smoke.py::TestSuite::test_alpha": 2.5},
    }

    save_timing_cache(tmp_path, cache)
    loaded = load_timing_cache(tmp_path)

    assert timing_cache_path(tmp_path).exists()
    assert loaded == cache


def test_parse_junit_timings_aggregates_file_and_nodeid_data(tmp_path: Path) -> None:
    report_path = tmp_path / "report.xml"
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite", name="pytest", tests="3")
    ET.SubElement(
        suite,
        "testcase",
        classname="tests.test_alpha",
        name="test_one",
        time="0.125",
    )
    ET.SubElement(
        suite,
        "testcase",
        classname="tests.test_alpha.TestBox",
        name="test_two",
        time="0.375",
    )
    ET.SubElement(
        suite,
        "testcase",
        classname="tests.test_harness_smoke.TestDiffSummary",
        name="test_missing_python_category_reports_missing",
        time="0.500",
    )
    ET.ElementTree(root).write(report_path, encoding="utf-8", xml_declaration=True)

    file_timings, nodeid_timings = parse_junit_timings(
        report_path,
        [
            "tests/test_alpha.py",
            "tests/test_harness_smoke.py::TestDiffSummary::test_missing_python_category_reports_missing",
        ],
    )

    assert file_timings == {"tests/test_alpha.py": 0.5}
    assert nodeid_timings == {
        "tests/test_harness_smoke.py::TestDiffSummary::test_missing_python_category_reports_missing": 0.5
    }


def test_build_pytest_command_keeps_ignore_guards() -> None:
    command = build_pytest_command(["tests/test_phase265_post_ship_maintenance.py"], ["-k", "phase265"])

    assert command[:4] == [command[0], "-m", "pytest", "-q"]
    assert "--ignore=.pytest_tmp" in command
    assert "--ignore=runtime_tmp" in command
    assert "tests/test_phase265_post_ship_maintenance.py" in command
    assert command[-2:] == ["-k", "phase265"]
