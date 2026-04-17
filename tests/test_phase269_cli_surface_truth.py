from __future__ import annotations

from io import StringIO

import pytest

import play_cli
from sts_py.engine.run.events import Event, EventChoice
from sts_py.engine.run.run_engine import RunEngine, RunPhase
from sts_py.terminal import render
from tests.test_phase267_cli_real_play_signoff import _scripted_cli_phase_walk


@pytest.mark.parametrize(
    ("character_class", "final_phase", "final_title"),
    [
        ("IRONCLAD", RunPhase.VICTORY, "胜利"),
        ("SILENT", RunPhase.VICTORY, "胜利"),
        ("DEFECT", RunPhase.VICTORY, "胜利"),
        ("WATCHER", RunPhase.GAME_OVER, "失败"),
    ],
)
def test_phase269_scripted_cli_walk_uses_readable_chinese_surface(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    character_class: str,
    final_phase: RunPhase,
    final_title: str,
) -> None:
    _scripted_cli_phase_walk(monkeypatch, character_class, final_phase=final_phase)
    output = capsys.readouterr().out

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
    assert "placeholder" not in output.lower()
    assert "RandomRelic" not in output
    assert "\ufffd" not in output


def test_phase269_render_helpers_and_cli_views_surface_readable_chinese() -> None:
    assert render.render_help_lines("combat")[:4] == [
        "<手牌序号> [目标序号]: 打出卡牌",
        "use <药水槽位> [目标序号]: 使用药水",
        "end: 结束回合",
        "status: 查看玩家当前状态",
    ]
    assert render.render_card_detail_lines("Bash", index=2) == [
        "序号: 2",
        "名称: 痛击",
        "ID: Bash",
        "说明: 造成 8 点伤害并施加 2 层易伤。",
    ]

    event = Event(
        id="Phase269 Event",
        name="Phase269 Event",
        description="english fallback",
        description_cn="中文事件描述",
        choices=[EventChoice(description="english choice", description_cn="[中文选项] 离开")],
    )
    assert render.render_event_choice_lines(event) == ["中文事件描述", "[0] [中文选项] 离开"]

    hint_lines = render.render_combat_command_hint_lines(has_pending_choice=True)
    assert hint_lines == [
        "当前有待选项：输入编号选择",
        "出牌: <手牌序号> [目标序号]",
        "药水: use <槽位> [目标序号]",
        "结束回合: end",
        "状态: status",
        "意图: intent",
        "消耗堆: exhaust",
        "更多命令: help",
    ]


def test_phase269_status_intent_and_exhaust_views_stay_readable_and_live(capsys: pytest.CaptureFixture[str]) -> None:
    engine = RunEngine.create("PHASE269CLISTATUS", ascension=0)
    engine.start_combat_with_monsters(["FungiBeast"])
    engine.state.combat.state.player.hp = 61
    engine.state.combat.state.card_manager.exhaust_pile.cards = []

    play_cli._show_lines("状态", render.render_status_detail_lines(engine))
    play_cli._show_lines("怪物意图", render.render_intent_lines(engine))
    play_cli._show_lines("消耗堆", render.render_exhaust_pile_lines(engine))
    output = capsys.readouterr().out

    assert "状态" in output
    assert "玩家: 生命 61/80" in output
    assert "力量 0 | 敏捷 0" in output
    assert "姿态: 中立" not in output
    assert "充能球:" not in output
    assert "怪物意图" in output
    assert "真菌兽" in output
    assert "消耗堆" in output
    assert "当前消耗堆为空。" in output
