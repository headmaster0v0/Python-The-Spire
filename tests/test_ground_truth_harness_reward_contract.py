from __future__ import annotations

from sts_py.tools.compare_logs import JavaGameLog
from sts_py.tools.ground_truth_harness import (
    _normalize_reward_summary,
    build_card_upgrade_audit,
)
from tests.log_helpers import require_optional_recent_live_log


LATEST_IRONCLAD_EARLY_BATTLE_DEATH_LIVE_LOG = "run_1NAXPJBANK0G2_1776229559372.json"
LATEST_IRONCLAD_EARLY_BATTLE_VICTORY_LIVE_LOG = "run_58JCYX0E41APV_1776228717319.json"


def _load_live_log(filename: str, *, label: str) -> JavaGameLog:
    return JavaGameLog.from_file(
        require_optional_recent_live_log(filename, human_label=label)
    )


def test_reward_summary_normalizes_upgrade_markup_into_explicit_boolean() -> None:
    assert _normalize_reward_summary(
        picked="True Grit+",
        upgraded=True,
        skipped=False,
        choice_type="pick",
    ) == {
        "choice_type": "pick",
        "picked": "True Grit",
        "upgraded": True,
        "skipped": False,
    }
    assert _normalize_reward_summary(
        picked="SearingBlow+2",
        upgraded=True,
        skipped=False,
        choice_type="pick",
    )["picked"] == "SearingBlow"
    assert _normalize_reward_summary(
        picked="GeneticAlgorithm#5+",
        upgraded=True,
        skipped=False,
        choice_type="pick",
    )["picked"] == "GeneticAlgorithm"


def test_latest_ironclad_1nax_upgrade_audit_separates_explained_shop_upgrades_from_unexplained_reward_upgrade() -> None:
    java_log = _load_live_log(
        LATEST_IRONCLAD_EARLY_BATTLE_DEATH_LIVE_LOG,
        label="latest ironclad 1NAX live log",
    )
    audit = build_card_upgrade_audit(java_log)

    reward_findings = [finding for finding in audit["findings"] if finding["source"] == "reward"]
    shop_findings = [finding for finding in audit["findings"] if finding["source"] == "shop"]

    assert [(finding["floor"], finding["card_id"], finding["explained"]) for finding in reward_findings] == [
        (28, "True Grit", False),
    ]
    assert sorted((finding["floor"], finding["card_id"]) for finding in shop_findings) == [
        (25, "Evolve"),
        (25, "Feel No Pain"),
    ]
    assert all(finding["explained"] for finding in shop_findings)
    assert {
        (finding["floor"], finding["card_id"], tuple(finding["explaining_relic_ids"]))
        for finding in shop_findings
    } == {
        (25, "Evolve", ("frozenegg2",)),
        (25, "Feel No Pain", ("frozenegg2",)),
    }


def test_latest_ironclad_58jc_upgrade_audit_identifies_unexplained_non_skill_reward_upgrades() -> None:
    java_log = _load_live_log(
        LATEST_IRONCLAD_EARLY_BATTLE_VICTORY_LIVE_LOG,
        label="latest ironclad 58JC live log",
    )
    audit = build_card_upgrade_audit(java_log)

    reward_findings = [finding for finding in audit["findings"] if finding["source"] == "reward"]
    shop_findings = [finding for finding in audit["findings"] if finding["source"] == "shop"]

    explained_reward_cards = {finding["card_id"] for finding in reward_findings if finding["explained"]}
    unexplained_reward_cards = {finding["card_id"] for finding in reward_findings if not finding["explained"]}

    assert {
        "Warcry",
        "True Grit",
        "Rage",
        "Double Tap",
        "Armaments",
        "Shockwave",
        "Shrug It Off",
    } <= explained_reward_cards
    assert {"Body Slam", "Dark Embrace"} <= unexplained_reward_cards
    assert {finding["card_id"] for finding in shop_findings} == {"Offering", "Apotheosis", "Blind"}
    assert all(finding["explained"] for finding in shop_findings)
