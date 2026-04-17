from __future__ import annotations

from pathlib import Path

import play_cli
from sts_py.engine.run.run_engine import MapNode, RoomType, RunEngine, RunPhase
from sts_py.engine.simulation import simulate_run_with_logs


def _force_win_current_combat(engine: RunEngine) -> None:
    assert engine.state.combat is not None
    for monster in engine.state.combat.state.monsters:
        monster.hp = 0
        monster.is_dying = True
    engine.end_combat()


def test_campaign_state_cleanup_across_phase_boundaries() -> None:
    engine = RunEngine.create("TESTPHASE222STATE", ascension=0)
    engine.state.pending_card_reward_cards = ["Anger", "Clash", "Cleave"]
    engine._pending_gold_reward = 25
    engine._pending_potion_reward = "BlockPotion"
    engine._pending_relic_reward = "Anchor"
    engine.state.pending_treasure_relic = "Anchor"
    engine._set_current_event_combat(
        enemies=["FungiBeast"],
        bonus_reward="Anchor",
        pending_event_rewards=["gold"],
        is_elite_combat=False,
    )
    engine.state.phase = RunPhase.VICTORY

    engine.transition_to_next_act()

    assert engine.state.pending_card_reward_cards == []
    assert engine._pending_gold_reward == 0
    assert engine._pending_potion_reward is None
    assert engine._pending_relic_reward is None
    assert engine.state.pending_treasure_relic is None
    assert engine.state.current_event_combat is None


def test_keyless_act3_boss_victory_is_final_victory() -> None:
    engine = RunEngine.create("TESTPHASE222KEYLESS", ascension=0)
    engine.state.act = 3
    engine.state.map_nodes = [MapNode(floor=51, room_type=RoomType.BOSS, node_id=0)]
    engine.state.current_node_idx = 0
    engine._start_combat("Awakened One")

    _force_win_current_combat(engine)

    assert engine.state.phase == RunPhase.VICTORY
    assert engine.state.act == 3
    assert play_cli._is_final_victory(engine) is True


def test_keyed_act3_boss_victory_transitions_into_act4_not_final_victory() -> None:
    engine = RunEngine.create("TESTPHASE222KEYED", ascension=0)
    engine.state.act = 3
    engine.state.ruby_key_obtained = True
    engine.state.emerald_key_obtained = True
    engine.state.sapphire_key_obtained = True
    engine.state.map_nodes = [MapNode(floor=51, room_type=RoomType.BOSS, node_id=0)]
    engine.state.current_node_idx = 0
    engine._start_combat("Awakened One")

    _force_win_current_combat(engine)

    assert engine.state.act == 3
    assert engine.state.phase == RunPhase.VICTORY
    assert len(engine.state.pending_boss_relic_choices) == 3

    engine.choose_boss_relic(0)
    engine.clear_pending_reward_notifications()
    engine.transition_to_next_act()

    assert engine.state.act == 4
    assert engine.state.phase == RunPhase.MAP
    assert [node.room_type for node in engine.state.map_nodes] == [
        RoomType.REST,
        RoomType.SHOP,
        RoomType.ELITE,
        RoomType.BOSS,
    ]


def test_act4_heart_victory_clears_pending_state() -> None:
    engine = RunEngine.create("TESTPHASE222HEART", ascension=0)
    engine.state.act = 4
    engine.state.map_nodes = [MapNode(floor=55, room_type=RoomType.BOSS, node_id=0)]
    engine.state.current_node_idx = 0
    engine.state.pending_card_reward_cards = ["Anger"]
    engine._pending_gold_reward = 10
    engine._pending_potion_reward = "BlockPotion"
    engine._pending_relic_reward = "Anchor"
    engine.state.pending_treasure_relic = "Anchor"
    engine._set_current_event_combat(
        enemies=["FungiBeast"],
        bonus_reward=None,
        pending_event_rewards=["gold"],
        is_elite_combat=False,
    )
    engine._start_combat("The Heart")

    _force_win_current_combat(engine)

    assert engine.state.phase == RunPhase.VICTORY
    assert engine.state.pending_card_reward_cards == []
    assert engine._pending_gold_reward == 0
    assert engine._pending_potion_reward is None
    assert engine._pending_relic_reward is None
    assert engine.state.pending_treasure_relic is None
    assert engine.state.current_event_combat is None


def test_simulation_short_and_mid_campaign_smoke_has_no_errors() -> None:
    short_result = simulate_run_with_logs("TESTPHASE222SHORT", max_floors=8, verbose=False, enable_combat_logs=False)
    mid_result = simulate_run_with_logs("TESTPHASE222MID", max_floors=20, verbose=False, enable_combat_logs=False)

    assert short_result.errors == []
    assert mid_result.errors == []
    assert short_result.combat_count >= 1
    assert mid_result.combat_count >= short_result.combat_count


def test_play_cli_structure_has_single_reward_and_shop_handler() -> None:
    source = Path("play_cli.py").read_text(encoding="utf-8")

    assert source.count("def handle_reward(") == 1
    assert source.count("def handle_shop(") == 1
