from __future__ import annotations

import builtins

import pytest

import play_cli
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.run.events import Event, EventChoice
from sts_py.engine.run.run_engine import RunEngine, RunPhase


def _set_inputs(monkeypatch: pytest.MonkeyPatch, responses: list[str]) -> None:
    remaining = iter(responses)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(remaining))


def _scripted_cli_phase_walk(
    monkeypatch: pytest.MonkeyPatch,
    character_class: str,
    *,
    final_phase: RunPhase,
) -> RunEngine:
    engine = RunEngine.create(f"PHASE267CLI{character_class}", ascension=0, character_class=character_class)
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)

    engine.state.neow_options = [
        {
            "category": 1,
            "reward_type": "HUNDRED_GOLD",
            "reward_value": 100,
            "drawback": "NONE",
            "drawback_value": 0,
            "label": "获得 100 金币",
        }
    ]
    _set_inputs(monkeypatch, ["help", "0"])
    play_cli.handle_neow(engine)

    engine.state.phase = RunPhase.MAP
    _set_inputs(monkeypatch, ["help", "map", "0"])
    play_cli.handle_map(engine)

    engine.start_combat_with_monsters(["FungiBeast"])
    combat = engine.state.combat
    assert combat is not None
    combat.state.monsters[0].hp = 1
    combat.state.card_manager.hand.cards = [CardInstance(engine.state.deck[0])]
    combat.state.card_manager.draw_pile.cards = []
    combat.state.card_manager.discard_pile.cards = []
    _set_inputs(monkeypatch, ["status", "intent", "exhaust", "inspect 0", "0 0"])
    play_cli.handle_combat(engine)

    engine.state.phase = RunPhase.REWARD
    engine.state.pending_card_reward_cards = [engine.state.deck[0], engine.state.deck[1]]
    engine._pending_gold_reward = 15
    engine._pending_potion_reward = "BlockPotion"
    engine._pending_relic_rewards = ["Anchor"]
    engine._pending_relic_reward = "Anchor"
    _set_inputs(monkeypatch, ["g", "", "p", "", "r", "", "inspect 0", "c", "0", ""])
    play_cli.handle_reward(engine)

    engine._enter_shop()
    _set_inputs(monkeypatch, ["help", "inspect 0", "l"])
    play_cli.handle_shop(engine)

    engine.state.phase = RunPhase.EVENT
    engine.state.deck = [engine.state.deck[0], engine.state.deck[1]]
    engine._current_event = Event(
        id=f"Phase267 Event {character_class}",
        name=f"Phase267 Event {character_class}",
        description="english fallback should stay hidden",
        description_cn="中文事件正文",
        choices=[EventChoice(description="upgrade", description_cn="[升级]", requires_card_upgrade=True)],
    )
    _set_inputs(monkeypatch, ["0", "inspect 0", "0"])
    play_cli.handle_event(engine)

    engine.state.phase = RunPhase.REST
    _set_inputs(monkeypatch, ["s", "inspect 0", "0", ""])
    play_cli.handle_rest(engine)

    engine.state.phase = RunPhase.TREASURE
    engine.state.pending_chest_relic_choices = ["Anchor"]
    engine.state.pending_treasure_relic = "Anchor"
    _set_inputs(monkeypatch, ["0", ""])
    play_cli.handle_treasure(engine)

    engine.state.phase = RunPhase.VICTORY
    engine.state.pending_boss_relic_choices = ["TinyHouse", "CallingBell", "PandoraBox"]
    _set_inputs(monkeypatch, ["0"])
    play_cli.handle_boss_relic_choice(engine)

    engine.state.pending_boss_relic_choices = []
    if final_phase == RunPhase.VICTORY:
        engine.state.act = 4
        engine.state.phase = RunPhase.VICTORY
    else:
        engine.state.phase = RunPhase.GAME_OVER
    assert play_cli._render_terminal_outcome(engine) is True
    return engine


@pytest.mark.parametrize(
    ("character_class", "final_phase", "final_title"),
    [
        ("IRONCLAD", RunPhase.VICTORY, "胜利"),
        ("SILENT", RunPhase.VICTORY, "胜利"),
        ("DEFECT", RunPhase.VICTORY, "胜利"),
        ("WATCHER", RunPhase.GAME_OVER, "失败"),
    ],
)
def test_phase267_scripted_cli_signoff_walks_real_play_stages_without_placeholder_surface(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    character_class: str,
    final_phase: RunPhase,
    final_title: str,
) -> None:
    engine = _scripted_cli_phase_walk(monkeypatch, character_class, final_phase=final_phase)
    output = capsys.readouterr().out

    assert engine.state.character_class == character_class
    assert "涅奥" in output
    assert "地图阶段" in output
    assert "战斗" in output
    assert "奖励" in output
    assert "商店" in output
    assert "事件" in output
    assert "篝火" in output
    assert "宝箱" in output
    assert "首领遗物" in output
    assert final_title in output
    assert "状态" in output
    assert "怪物意图" in output
    assert "消耗堆" in output
    assert "当前有待选项：输入编号选择" not in output or "输入编号选择" in output
    assert "\ufffd" not in output
    assert "Boss 遗物" not in output
    assert "Boss 房间" not in output
    assert "RandomRelic" not in output
    assert "placeholder" not in output.lower()
