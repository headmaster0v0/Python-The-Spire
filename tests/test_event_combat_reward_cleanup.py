from __future__ import annotations

from pathlib import Path

from sts_py.engine.run.run_engine import RunEngine


def test_event_combat_reward_resolution_is_idempotent() -> None:
    engine = RunEngine.create("TESTPHASE221IDEMPOTENT", ascension=0)
    engine._set_current_event_combat(
        enemies=["FungiBeast"],
        bonus_reward="Anchor",
        pending_event_rewards=["relic", "gold"],
        is_elite_combat=True,
    )

    initial_gold = engine.state.player_gold
    initial_relics = list(engine.state.relics)

    engine._resolve_event_combat_rewards()
    first_relic = engine._pending_relic_reward
    first_gold = engine._pending_gold_reward
    relic_count_after_first = len(engine.state.relics)
    gold_after_first = engine.state.player_gold

    engine._resolve_event_combat_rewards()

    assert engine._pending_relic_reward == first_relic
    assert engine._pending_gold_reward == first_gold
    assert len(engine.state.relics) == relic_count_after_first
    assert engine.state.player_gold == gold_after_first
    assert engine.state.player_gold == initial_gold + 30
    assert len(engine.state.relics) == len(initial_relics) + 2
    assert engine._get_current_event_combat()["rewards_resolved"] is True


def test_event_combat_state_clears_after_end_combat() -> None:
    engine = RunEngine.create("TESTPHASE221CLEAR", ascension=0)
    engine.state.current_node_idx = -1
    engine._set_current_event_combat(
        enemies=["FungiBeast"],
        bonus_reward=None,
        pending_event_rewards=["gold"],
        is_elite_combat=False,
    )
    engine.start_combat_with_monsters(["FungiBeast"])
    for monster in engine.state.combat.state.monsters:
        monster.hp = 0
        monster.is_dying = True

    engine.end_combat()

    assert engine.state.current_event_combat is None


def test_event_combat_bonus_reward_is_not_duplicated_if_already_owned() -> None:
    engine = RunEngine.create("TESTPHASE221BONUS", ascension=0)
    engine.state.relics.append("Anchor")
    engine._set_current_event_combat(
        enemies=["FungiBeast"],
        bonus_reward="Anchor",
        pending_event_rewards=[],
        is_elite_combat=False,
    )

    engine._resolve_event_combat_rewards()

    assert engine.state.relics.count("Anchor") == 1
    assert engine._pending_relic_reward is None


def test_play_cli_only_has_one_real_handle_reward_and_shop_definition() -> None:
    source = Path("play_cli.py").read_text(encoding="utf-8")

    assert source.count("def handle_reward(") == 1
    assert source.count("def handle_shop(") == 1
    assert "card_reward_options" not in source
    assert "engine.state.pending_gold_reward" not in source
    assert "engine.state.pending_potion" not in source
