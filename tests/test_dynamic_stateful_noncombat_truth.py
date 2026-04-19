from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import ALL_CARD_DEFS, COLORLESS_ALL_DEFS
from sts_py.engine.rewards.card_rewards_min import character_pools
from sts_py.engine.run.events import ACT1_EVENTS, Event, EventChoice, _event_card_base_id
from sts_py.engine.run.run_engine import RunEngine, RunPhase, _deck_card_base_id
from sts_py.terminal.render import render_card_detail_lines


SEED_STRING = "PHASE257STATEFUL"


def test_ritual_dagger_runtime_string_survives_smith_and_event_upgrade_remove() -> None:
    smith_engine = RunEngine.create(SEED_STRING, ascension=0)
    smith_engine.state.phase = RunPhase.REST
    smith_engine.state.deck = ["RitualDagger#15"]

    assert smith_engine.smith(0) is True
    assert smith_engine.state.deck == ["RitualDagger#15+"]

    upgrade_engine = RunEngine.create(SEED_STRING, ascension=0)
    upgrade_engine.state.phase = RunPhase.EVENT
    upgrade_engine.state.deck = ["RitualDagger#18"]
    upgrade_engine._current_event = Event(
        id="Test Upgrade",
        name="Test Upgrade",
        choices=[EventChoice(description="upgrade", requires_card_upgrade=True)],
    )

    assert upgrade_engine.choose_event_option(0)["requires_card_choice"] is True
    upgrade_result = upgrade_engine.choose_card_for_event(0)
    assert upgrade_result["success"] is True
    assert upgrade_result["old_card"] == "RitualDagger#18"
    assert upgrade_result["new_card"] == "RitualDagger#18+"
    assert upgrade_engine.state.deck == ["RitualDagger#18+"]

    remove_engine = RunEngine.create(SEED_STRING, ascension=0)
    remove_engine.state.phase = RunPhase.EVENT
    remove_engine.state.deck = ["RitualDagger#18+"]
    remove_engine._current_event = Event(
        id="Test Remove",
        name="Test Remove",
        choices=[EventChoice(description="remove", requires_card_removal=True)],
    )

    assert remove_engine.choose_event_option(0)["requires_card_choice"] is True
    remove_result = remove_engine.choose_card_for_event(0)
    assert remove_result == {"success": True, "action": "card_removed", "card_id": "RitualDagger#18+"}
    assert remove_engine.state.deck == []


def test_ritual_dagger_transform_and_detail_render_keep_base_metadata_accessible() -> None:
    engine = RunEngine.create(SEED_STRING, ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine.state.deck = ["RitualDagger#18+"]
    engine._current_event = Event(
        id="Test Transform",
        name="Test Transform",
        choices=[EventChoice(description="transform", requires_card_transform=True)],
    )

    assert engine.choose_event_option(0)["requires_card_choice"] is True
    transform_result = engine.choose_card_for_event(0)

    assert transform_result["success"] is True
    assert transform_result["old_card"] == "RitualDagger#18+"
    transformed_base = CardInstance(transform_result["new_card"]).card_id
    assert transformed_base != "RitualDagger"
    assert transformed_base in COLORLESS_ALL_DEFS
    assert _event_card_base_id("RitualDagger#18+") == "RitualDagger"
    assert _deck_card_base_id("RitualDagger#18+") == "RitualDagger"

    detail_lines = render_card_detail_lines("RitualDagger#18+", index=2)
    assert any(line == "ID: RitualDagger#18+" for line in detail_lines)
    assert all("\ufffd" not in line for line in detail_lines)


def test_searing_blow_plus_n_uses_same_upgrade_path_for_rest_and_event_flows() -> None:
    smith_engine = RunEngine.create(SEED_STRING, ascension=0)
    smith_engine.state.phase = RunPhase.REST
    smith_engine.state.deck = ["SearingBlow+2"]

    assert smith_engine.smith(0) is True
    assert smith_engine.state.deck == ["SearingBlow+3"]

    event_engine = RunEngine.create(SEED_STRING, ascension=0)
    event_engine.state.phase = RunPhase.EVENT
    event_engine.state.deck = ["SearingBlow+2"]
    event_engine._current_event = ACT1_EVENTS["Living Wall"]

    choice_result = event_engine.choose_event_option(2)
    assert choice_result["success"] is True
    assert choice_result["action"] == "select_card"

    upgrade_result = event_engine.choose_event_option(0)
    assert upgrade_result["success"] is True
    assert upgrade_result["action"] == "card_upgraded"
    assert upgrade_result["old_card"] == "SearingBlow+2"
    assert upgrade_result["new_card"] == "SearingBlow+3"
    assert event_engine.state.deck == ["SearingBlow+3"]


def test_stateful_card_string_helpers_normalize_ritual_dagger_and_searing_blow() -> None:
    ritual = CardInstance("RitualDagger#18+")
    genetic_algorithm = CardInstance("GeneticAlgorithm#7+")
    searing = CardInstance("SearingBlow+4")

    assert ritual.card_id == "RitualDagger"
    assert ritual.misc == 18
    assert ritual.runtime_card_id == "RitualDagger#18+"
    assert _event_card_base_id("RitualDagger#18+") == "RitualDagger"
    assert _deck_card_base_id("RitualDagger#18+") == "RitualDagger"

    assert genetic_algorithm.card_id == "GeneticAlgorithm"
    assert genetic_algorithm.misc == 7
    assert genetic_algorithm.runtime_card_id == "GeneticAlgorithm#7+"
    assert _event_card_base_id("GeneticAlgorithm#7+") == "GeneticAlgorithm"
    assert _deck_card_base_id("GeneticAlgorithm#7+") == "GeneticAlgorithm"

    assert searing.card_id == "SearingBlow"
    assert searing.times_upgraded == 4
    assert searing.runtime_card_id == "SearingBlow+4"
    assert _event_card_base_id("SearingBlow+4") == "SearingBlow"
    assert _deck_card_base_id("SearingBlow+4") == "SearingBlow"


def test_genetic_algorithm_runtime_string_survives_smith_and_event_upgrade_remove() -> None:
    smith_engine = RunEngine.create(SEED_STRING, ascension=0)
    smith_engine.state.phase = RunPhase.REST
    smith_engine.state.deck = ["GeneticAlgorithm#7"]

    assert smith_engine.smith(0) is True
    assert smith_engine.state.deck == ["GeneticAlgorithm#7+"]

    upgrade_engine = RunEngine.create(SEED_STRING, ascension=0)
    upgrade_engine.state.phase = RunPhase.EVENT
    upgrade_engine.state.deck = ["GeneticAlgorithm#9"]
    upgrade_engine._current_event = Event(
        id="Test Genetic Upgrade",
        name="Test Genetic Upgrade",
        choices=[EventChoice(description="upgrade", requires_card_upgrade=True)],
    )

    assert upgrade_engine.choose_event_option(0)["requires_card_choice"] is True
    upgrade_result = upgrade_engine.choose_card_for_event(0)
    assert upgrade_result["success"] is True
    assert upgrade_result["old_card"] == "GeneticAlgorithm#9"
    assert upgrade_result["new_card"] == "GeneticAlgorithm#9+"
    assert upgrade_engine.state.deck == ["GeneticAlgorithm#9+"]

    remove_engine = RunEngine.create(SEED_STRING, ascension=0)
    remove_engine.state.phase = RunPhase.EVENT
    remove_engine.state.deck = ["GeneticAlgorithm#9+"]
    remove_engine._current_event = Event(
        id="Test Genetic Remove",
        name="Test Genetic Remove",
        choices=[EventChoice(description="remove", requires_card_removal=True)],
    )

    assert remove_engine.choose_event_option(0)["requires_card_choice"] is True
    remove_result = remove_engine.choose_card_for_event(0)
    assert remove_result == {"success": True, "action": "card_removed", "card_id": "GeneticAlgorithm#9+"}
    assert remove_engine.state.deck == []


def test_genetic_algorithm_transform_and_detail_render_keep_base_metadata_accessible() -> None:
    engine = RunEngine.create(SEED_STRING, ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine.state.deck = ["GeneticAlgorithm#7+"]
    engine._current_event = Event(
        id="Test Genetic Transform",
        name="Test Genetic Transform",
        choices=[EventChoice(description="transform", requires_card_transform=True)],
    )

    assert engine.choose_event_option(0)["requires_card_choice"] is True
    transform_result = engine.choose_card_for_event(0)

    assert transform_result["success"] is True
    assert transform_result["old_card"] == "GeneticAlgorithm#7+"
    transformed_base = CardInstance(transform_result["new_card"]).card_id
    reward_pool_ids = {
        card.id
        for pool in character_pools(engine.state.character_class).values()
        for card in pool
    }
    assert transformed_base != "GeneticAlgorithm"
    assert transformed_base in reward_pool_ids
    assert _event_card_base_id("GeneticAlgorithm#7+") == "GeneticAlgorithm"
    assert _deck_card_base_id("GeneticAlgorithm#7+") == "GeneticAlgorithm"

    detail_lines = render_card_detail_lines("GeneticAlgorithm#7+", index=1)
    assert any(line == "ID: GeneticAlgorithm#7+" for line in detail_lines)
    assert all("\ufffd" not in line for line in detail_lines)
