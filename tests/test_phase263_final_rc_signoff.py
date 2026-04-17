from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import ALL_CARD_DEFS
from sts_py.engine.run.events import Event, EventChoice
from sts_py.engine.run.run_engine import RunEngine, RunPhase, _deck_card_base_id
from sts_py.terminal.render import render_card_detail_lines
from sts_py.tools import wiki_audit
from sts_py.tools.compare_logs import JavaGameLog
from sts_py.tools.ground_truth_harness import replay_java_floor_fixture
from tests.log_helpers import require_optional_corpus_log


STATEFUL_SEED = "PHASE263SIGNOFF"


def _require_arn_log() -> Path:
    return require_optional_corpus_log("primary")


def test_replay_java_floor_fixture_repeated_same_floor_and_neighbor_floors_stays_stable() -> None:
    java_log = JavaGameLog.from_file(_require_arn_log())

    baseline = replay_java_floor_fixture(java_log, 39)
    expected_lane_turn = deepcopy(baseline["debug"]["battle_same_id_jawworm_intent_lane_by_turn"][1])
    expected_collapse = deepcopy(baseline["debug"]["battle_jawworm_lane_collapse_by_turn"][1])

    baseline["debug"]["battle_same_id_jawworm_intent_lane_by_turn"][1][0]["monster_idx"] = 999
    baseline["battle_fixture"]["action_intents_by_turn"][1] = [{"mutated": True}]
    baseline["debug"]["battle_jawworm_lane_collapse_by_turn"][1].clear()

    _ = replay_java_floor_fixture(java_log, 37)
    _ = replay_java_floor_fixture(java_log, 38)
    replay = replay_java_floor_fixture(java_log, 39)

    assert replay["debug"]["battle_same_id_jawworm_intent_lane_by_turn"][1] == expected_lane_turn
    assert replay["debug"]["battle_jawworm_lane_collapse_by_turn"][1] == expected_collapse
    assert replay["battle_fixture"]["action_intents_by_turn"][1] != [{"mutated": True}]


def test_replay_java_floor_fixture_returns_isolated_debug_and_battle_views() -> None:
    java_log = JavaGameLog.from_file(_require_arn_log())

    fixture = replay_java_floor_fixture(java_log, 39)
    fixture["debug"]["java_monster_intents_by_turn"][1][0]["base_damage"] = 123

    assert fixture["battle_fixture"]["expected_intents_by_turn"][1][0]["base_damage"] != 123


def test_offline_audit_repeat_is_stable_after_prior_bundle_mutation() -> None:
    first_raw = wiki_audit.build_cli_raw_snapshot(Path.cwd(), enable_network=False)
    first_bundle = wiki_audit.run_audit_from_raw_snapshot(first_raw, repo_root=Path.cwd())
    expected_translation = deepcopy(first_bundle["translation_audit"]["summary"])
    expected_completeness = deepcopy(first_bundle["completeness_audit"]["summary"])
    expected_mechanics = deepcopy(first_bundle["mechanics_audit"]["summary"])
    expected_fix_summary = deepcopy(first_bundle["fix_queue"]["summary"])

    first_bundle["translation_audit"]["summary"]["total"] = -1
    first_bundle["completeness_audit"]["summary"]["missing_in_runtime"] = -1
    first_bundle["mechanics_audit"]["summary"]["runtime_source_mismatches"] = -1
    first_bundle["fix_queue"]["summary"]["total"] = -1

    second_raw = wiki_audit.build_cli_raw_snapshot(Path.cwd(), enable_network=False)
    second_bundle = wiki_audit.run_audit_from_raw_snapshot(second_raw, repo_root=Path.cwd())

    assert second_bundle["translation_audit"]["summary"] == expected_translation
    assert second_bundle["completeness_audit"]["summary"] == expected_completeness
    assert second_bundle["mechanics_audit"]["summary"] == expected_mechanics
    assert second_bundle["fix_queue"]["summary"] == expected_fix_summary


def test_stateful_render_and_event_paths_repeat_without_identity_drift() -> None:
    first_render = render_card_detail_lines("GeneticAlgorithm#7+", index=1)
    first_render[0] = "mutated"
    second_render = render_card_detail_lines("GeneticAlgorithm#7+", index=1)
    assert second_render[0] == "序号: 1"
    assert "ID: GeneticAlgorithm#7+" in second_render

    first_engine = RunEngine.create(STATEFUL_SEED, ascension=0)
    first_engine.state.phase = RunPhase.EVENT
    first_engine.state.deck = ["GeneticAlgorithm#7+"]
    first_engine._current_event = Event(
        id="Phase263 Transform",
        name="Phase263 Transform",
        choices=[EventChoice(description="transform", requires_card_transform=True)],
    )
    assert first_engine.choose_event_option(0)["requires_card_choice"] is True
    first_result = first_engine.choose_card_for_event(0)

    second_engine = RunEngine.create(STATEFUL_SEED, ascension=0)
    second_engine.state.phase = RunPhase.EVENT
    second_engine.state.deck = ["GeneticAlgorithm#7+"]
    second_engine._current_event = Event(
        id="Phase263 Transform",
        name="Phase263 Transform",
        choices=[EventChoice(description="transform", requires_card_transform=True)],
    )
    assert second_engine.choose_event_option(0)["requires_card_choice"] is True
    second_result = second_engine.choose_card_for_event(0)

    assert first_result == second_result
    assert first_result["old_card"] == "GeneticAlgorithm#7+"
    assert _deck_card_base_id(first_result["old_card"]) == "GeneticAlgorithm"
    assert CardInstance(first_result["new_card"]).card_id in ALL_CARD_DEFS
