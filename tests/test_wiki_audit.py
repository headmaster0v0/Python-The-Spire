from __future__ import annotations

import json
from pathlib import Path

from sts_py.tools import wiki_audit


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "wiki_audit" / "sample_raw_snapshot.json"
RELIC_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "wiki_audit" / "relic_raw_snapshot.json"


def _load_fixture() -> dict:
    return wiki_audit.load_raw_snapshot(FIXTURE_PATH)


def test_normalize_raw_snapshot_handles_aliases_upgrade_notation_and_policy_provenance() -> None:
    normalized = wiki_audit.normalize_raw_snapshot(_load_fixture())
    records = {(record["entity_type"], record["entity_id"]): record for record in normalized["records"]}

    assert normalized["translation_policy"]
    assert records[("relic", "BurningBlood")]["match_meta"]["en_match"] == "exact"
    assert records[("potion", "SmokeBomb")]["match_meta"]["en_match"] == "exact"
    assert records[("card", "SearingBlow+2")]["match_meta"]["en_match"] == "exact"
    assert records[("card", "SearingBlow+2")]["match_meta"]["cn_match"] == "exact"
    assert records[("monster", "JawWorm")]["match_meta"]["cn_match"] == "alias"
    assert records[("event", "Big Fish")]["alignment_status"] == "approved_alias"
    assert records[("event", "Big Fish")]["huiji_page_or_title"] == "大鱼事件"
    assert records[("ui_term", "help")]["reference_source"] == "local_terminal"


def test_translation_audit_uses_explicit_alignment_statuses_and_runtime_name_issues() -> None:
    translation = wiki_audit.build_translation_audit(wiki_audit.normalize_raw_snapshot(_load_fixture()))
    findings = {(finding["entity_type"], finding["entity_id"]): finding for finding in translation["findings"]}
    statuses = {key: finding["status"] for key, finding in findings.items()}
    runtime_name_issues = {key: finding["runtime_name_issue"] for key, finding in findings.items()}
    desc_statuses = {key: finding["description_status"] for key, finding in findings.items()}

    assert "accepted_alias" not in translation["summary"]["by_status"]
    assert statuses[("card", "Bash")] == "exact_match"
    assert statuses[("relic", "BurningBlood")] == "exact_match"
    assert statuses[("potion", "SmokeBomb")] == "exact_match"
    assert statuses[("event", "Big Fish")] == "approved_alias"
    assert statuses[("monster", "JawWorm")] == "needs_review"
    assert statuses[("power", "Artifact")] == "likely_wrong_translation"
    assert statuses[("card", "Shockwave")] == "exact_match"
    assert statuses[("ui_term", "help")] == "wiki_missing"
    assert runtime_name_issues[("power", "Artifact")] == "missing_cn"
    assert runtime_name_issues[("card", "Shockwave")] == "mojibake_or_corrupt"
    assert desc_statuses[("card", "Shockwave")] == "mojibake_runtime_desc"
    assert findings[("event", "Big Fish")]["reference_source"] == "cn_huiji"
    assert findings[("event", "Big Fish")]["huiji_page_or_title"] == "大鱼事件"
    assert findings[("event", "Big Fish")]["approved_alias_note"] == "CLI omits the event suffix."


def test_mechanics_audit_flags_runtime_source_mismatch_and_wiki_conflict() -> None:
    mechanics = wiki_audit.build_mechanics_audit(_load_fixture())
    mismatch_fields = {(item["entity_type"], item["entity_id"], item["field"]) for item in mechanics["runtime_source_mismatches"]}
    wiki_conflict_fields = {(item["entity_type"], item["entity_id"], item["field"], item["wiki_source"]) for item in mechanics["wiki_conflicts"]}

    assert ("card", "Bash", "target_required") in mismatch_fields
    assert ("event", "Big Fish", "choices") in mismatch_fields
    assert ("event", "Big Fish", "choices", "en_wiki") in wiki_conflict_fields


def test_completeness_audit_reports_missing_runtime_catalog_gaps_and_orphan_overrides() -> None:
    completeness = wiki_audit.build_completeness_audit(_load_fixture())

    missing = {(item["entity_type"], item["entity_id"]) for item in completeness["missing_in_runtime"]}
    not_cataloged = {(item["entity_type"], item["entity_id"]) for item in completeness["present_but_not_cataloged"]}
    orphan_overrides = {(item["entity_type"], item["entity_id"]) for item in completeness["catalog_only_without_source_mapping"]}

    assert ("card", "PhantomStrike") in missing
    assert ("power", "Artifact") in not_cataloged
    assert ("card", "Shockwave") in not_cataloged
    assert ("card", "GhostOnlyCatalog") in orphan_overrides


def test_audit_command_writes_all_outputs_from_checked_in_fixture(tmp_path: Path) -> None:
    exit_code = wiki_audit.main(
        [
            "audit",
            "--repo-root",
            str(Path.cwd()),
            "--raw-snapshot",
            str(FIXTURE_PATH),
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    for filename in (
        wiki_audit.RAW_SNAPSHOT_FILENAME,
        wiki_audit.NORMALIZED_SNAPSHOT_FILENAME,
        wiki_audit.TRANSLATION_AUDIT_FILENAME,
        wiki_audit.COMPLETENESS_AUDIT_FILENAME,
        wiki_audit.MECHANICS_AUDIT_FILENAME,
        wiki_audit.FIX_QUEUE_FILENAME,
    ):
        path = tmp_path / filename
        assert path.exists()
        json.loads(path.read_text(encoding="utf-8"))


def test_refresh_offline_writes_outputs_without_network(monkeypatch, tmp_path: Path) -> None:
    def _unexpected_fetch(*args, **kwargs):
        raise AssertionError("offline refresh should not hit wiki fetch")

    monkeypatch.setattr(wiki_audit.BilingualWikiScraper, "fetch_page_with_fallback", _unexpected_fetch)

    exit_code = wiki_audit.main(
        [
            "refresh",
            "--repo-root",
            str(Path.cwd()),
            "--offline",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    for filename in (
        wiki_audit.RAW_SNAPSHOT_FILENAME,
        wiki_audit.NORMALIZED_SNAPSHOT_FILENAME,
        wiki_audit.TRANSLATION_AUDIT_FILENAME,
        wiki_audit.COMPLETENESS_AUDIT_FILENAME,
        wiki_audit.MECHANICS_AUDIT_FILENAME,
        wiki_audit.FIX_QUEUE_FILENAME,
    ):
        assert (tmp_path / filename).exists()


def test_build_cli_raw_snapshot_supports_relic_only_filter() -> None:
    raw_snapshot = wiki_audit.build_cli_raw_snapshot(
        Path.cwd(),
        enable_network=False,
        entity_types={"relic"},
    )

    assert raw_snapshot["entity_types"] == ["relic"]
    assert set(raw_snapshot["runtime_inventory"]) == {"relic"}
    assert set(raw_snapshot["source_inventory"]) == {"relic"}
    assert set(raw_snapshot["catalog_overrides"]) == {"relic"}
    assert all(record["entity_type"] == "relic" for record in raw_snapshot["records"])
    assert len(raw_snapshot["records"]) == 179


def test_relic_only_audit_command_writes_outputs_from_checked_in_fixture(tmp_path: Path) -> None:
    exit_code = wiki_audit.main(
        [
            "audit",
            "--repo-root",
            str(Path.cwd()),
            "--raw-snapshot",
            str(RELIC_FIXTURE_PATH),
            "--entity-types",
            "relic",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    raw_snapshot = json.loads((tmp_path / wiki_audit.RAW_SNAPSHOT_FILENAME).read_text(encoding="utf-8"))
    assert raw_snapshot["entity_types"] == ["relic"]
    assert set(raw_snapshot["runtime_inventory"]) == {"relic"}
    assert set(raw_snapshot["source_inventory"]) == {"relic"}
    assert all(record["entity_type"] == "relic" for record in raw_snapshot["records"])


def test_phase252_offline_audit_closes_remaining_runtime_card_tail() -> None:
    bundle = wiki_audit.run_audit_from_raw_snapshot(
        wiki_audit.build_cli_raw_snapshot(Path.cwd(), enable_network=False),
        repo_root=Path.cwd(),
    )

    missing_runtime_cards = {
        item["entity_id"]
        for item in bundle["completeness_audit"]["missing_in_runtime"]
        if item["entity_type"] == "card"
    }

    assert len(missing_runtime_cards) == 0
    for implemented_card in {
        "Safety",
        "Smite",
        "ThroughViolence",
        "Madness",
        "MasterOfStrategy",
        "Apotheosis",
        "Bite",
        "Apparition",
        "Blind",
        "DeepBreath",
        "Finesse",
        "FlashOfSteel",
        "GoodInstincts",
        "HandOfGreed",
        "Panacea",
        "Trip",
        "DarkShackles",
        "SwiftStrike",
        "PanicButton",
        "BandageUp",
        "DramaticEntrance",
        "Enlightenment",
        "Discovery",
        "Forethought",
        "Impatience",
        "JAX",
        "JackOfAllTrades",
        "MindBlast",
        "Purity",
        "Chrysalis",
        "Metamorphosis",
        "SecretTechnique",
        "SecretWeapon",
        "ThinkingAhead",
        "Violence",
        "Void",
        "Magnetism",
        "Mayhem",
        "Panache",
        "RitualDagger",
        "SadisticNature",
        "TheBomb",
        "Transmutation",
    }:
        assert implemented_card not in missing_runtime_cards
    assert missing_runtime_cards == set()


def test_phase256_offline_audit_closes_card_static_truth_mismatches() -> None:
    bundle = wiki_audit.run_audit_from_raw_snapshot(
        wiki_audit.build_cli_raw_snapshot(Path.cwd(), enable_network=False),
        repo_root=Path.cwd(),
    )

    translation_summary = bundle["translation_audit"]["summary"]
    mechanics_summary = bundle["mechanics_audit"]["summary"]
    completeness_summary = bundle["completeness_audit"]["summary"]

    assert completeness_summary["missing_in_runtime"] == 0
    assert translation_summary["runtime_name_issue"]["ok"] == translation_summary["total"]
    assert mechanics_summary["runtime_source_mismatches"] == 0
    assert bundle["mechanics_audit"]["runtime_source_mismatches"] == []
