from __future__ import annotations

import builtins

import play_cli
from sts_py.engine.combat.orbs import LightningOrb
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.run.events import Event, EventChoice
from sts_py.engine.run.run_engine import RoomType, RunEngine, RunPhase
from sts_py.terminal import render


def test_print_map_is_text_only(monkeypatch, capsys) -> None:
    engine = RunEngine.create("TESTPHASE243RENDERMAP", ascension=0)
    opened: list[bool] = []

    monkeypatch.setattr(render, "show_map_image", lambda current_engine: opened.append(True))

    render.print_map(engine)
    output = capsys.readouterr().out

    assert "地图" in output
    assert "首领" in output
    assert "Boss" not in output
    assert opened == []


def test_open_map_image_calls_show_map_image(monkeypatch) -> None:
    engine = RunEngine.create("TESTPHASE243OPENMAP", ascension=0)
    opened: list[str] = []

    monkeypatch.setattr(render, "show_map_image", lambda current_engine: opened.append(current_engine.state.seed_string))

    render.open_map_image(engine)

    assert opened == ["TESTPHASE243OPENMAP"]


def test_render_help_lines_expose_mapimg_and_inspect() -> None:
    lines = render.render_help_lines("combat")

    assert any("mapimg" in line for line in lines)
    assert any("inspect <index>" in line or "inspect <手牌序号>" in line for line in lines)
    assert any("status" in line for line in lines)
    assert any("intent" in line for line in lines)
    assert any("exhaust" in line for line in lines)


def test_render_card_detail_lines_include_name_id_and_description() -> None:
    lines = render.render_card_detail_lines("Bash", index=2)

    assert lines[0] == "序号: 2"
    assert any("名称: 痛击" in line for line in lines)
    assert any("ID: Bash" in line for line in lines)
    assert any("易伤" in line for line in lines)


def test_render_card_detail_lines_use_fixed_twin_strike_translation() -> None:
    lines = render.render_card_detail_lines("TwinStrike", index=1)

    assert any("名称: 双重打击" in line for line in lines)
    assert all("鍙岄噸" not in line for line in lines)


def test_render_card_detail_lines_use_phase247_card_name_overrides() -> None:
    lines = render.render_card_detail_lines("Accuracy", index=0)

    assert any("名称: 精准" in line for line in lines)
    assert any("ID: Accuracy" in line for line in lines)


def test_render_potion_lines_use_chinese_names_when_available() -> None:
    lines = render.render_potion_lines(["Elixir"])

    assert lines == ["[0] 万灵药水 (Elixir) - 消耗你手牌中的任意张牌。"]


def test_combat_header_uses_chinese_monster_names(capsys) -> None:
    engine = RunEngine.create("TESTPHASE247MONSTERNAME", ascension=0)
    engine.start_combat_with_monsters(["GremlinLeader"])

    play_cli._print_combat_header(engine)
    output = capsys.readouterr().out

    assert "地精首领" in output
    assert "Gremlin Leader" not in output
    assert "姿态 中立" not in output
    assert "充能球:" not in output
    assert "Neutral" not in output


def test_render_status_line_uses_live_combat_hp() -> None:
    engine = RunEngine.create("TESTPHASE266LIVEHP", ascension=0)
    engine.start_combat_with_monsters(["FungiBeast"])
    engine.state.player_hp = 80
    engine.state.combat.state.player.hp = 61

    line = render.render_status_line(engine)

    assert "第 1 幕" in line
    assert "楼层" in line
    assert "生命 61/" in line
    assert "金币" in line
    assert "61/" in line
    assert "80/80" not in line
    assert "绗?" not in line
    assert "妤煎眰" not in line
    assert "鐢熷懡" not in line
    assert "閲戝竵" not in line


def test_render_status_detail_lines_surface_live_combat_state() -> None:
    engine = RunEngine.create("TESTPHASE267STATUSDETAIL", ascension=0, character_class="DEFECT")
    engine.start_combat_with_monsters(["FungiBeast"])
    player = engine.state.combat.state.player
    player.focus = 1
    player.orbs.channel(LightningOrb())
    engine.state.combat.state.card_manager.exhaust_pile.cards = [CardInstance("Bash")]

    lines = render.render_status_detail_lines(engine)
    joined = "\n".join(lines)

    assert "生命" in joined
    assert "姿态: 中立" not in joined
    assert "集中 1" in joined
    assert "充能球:" in joined
    assert "闪电" in joined
    assert "回合末手牌:" in joined
    assert "牌堆:" in joined


def test_render_intent_and_exhaust_lines_use_runtime_surfaces() -> None:
    engine = RunEngine.create("TESTPHASE267INTENTEXHAUST", ascension=0)
    engine.start_combat_with_monsters(["FungiBeast"])
    engine.state.combat.state.card_manager.exhaust_pile.cards = [CardInstance("Bash")]

    intent_lines = render.render_intent_lines(engine)
    exhaust_lines = render.render_exhaust_pile_lines(engine)

    assert any("真菌兽" in line for line in intent_lines)
    assert any("意图" in line for line in intent_lines)
    assert exhaust_lines[0].startswith("[0] 痛击 - ")


def test_render_combat_command_hints_include_core_syntax() -> None:
    lines = render.render_combat_command_hint_lines(has_pending_choice=True)

    assert lines[0] == "当前有待选项：输入编号选择"
    assert "出牌: <手牌序号> [目标序号]" in lines
    assert "药水: use <槽位> [目标序号]" in lines
    assert "结束回合: end" in lines
    assert "状态: status" in lines
    assert "意图: intent" in lines
    assert "消耗堆: exhaust" in lines


def test_render_event_choice_lines_prefer_description_cn() -> None:
    event = Event(
        id="Render Event",
        name="Render Event",
        description="english event body",
        description_cn="中文事件描述",
        choices=[
            EventChoice(description="english choice", description_cn="[中文选项] 获得奖励"),
        ],
    )

    lines = render.render_event_choice_lines(event)

    assert lines[0] == "中文事件描述"
    assert lines[1] == "[0] [中文选项] 获得奖励"
    assert all("english" not in line for line in lines)


def test_render_shop_card_lines_include_inspect_index_buy_slot_and_summary() -> None:
    engine = RunEngine.create("TESTPHASE254SHOPCARDLINES", ascension=0)
    engine._enter_shop()
    shop = engine.get_shop()
    assert shop is not None

    lines, inspect_cards = render.render_shop_card_lines(shop.get_available_cards())

    assert lines
    assert inspect_cards
    assert lines[0].startswith("[0] ")
    assert any(marker in lines[0] for marker in (" c", " x", "c0:", "x0:"))
    assert "费用" in lines[0] or "伤害" in lines[0] or "格挡" in lines[0]


def test_render_shop_relic_and_potion_lines_include_descriptions() -> None:
    relic_lines = render.render_shop_relic_lines(
        [{"index": 0, "relic_id": "BurningBlood", "price": 300, "affordable": True}]
    )
    potion_lines = render.render_shop_potion_lines(
        [{"index": 0, "potion_id": "Elixir", "price": 70, "affordable": True}]
    )

    assert relic_lines == ["r0: 燃烧之血 (BurningBlood) - 300G | 在战斗结束时，回复6点生命。"]
    assert potion_lines == ["p0: 万灵药水 (Elixir) - 70G | 消耗你手牌中的任意张牌。"]


def test_render_boss_relic_lines_include_descriptions() -> None:
    lines = render.render_boss_relic_lines(["TinyHouse"])

    assert lines == ["[0] 小屋子 (TinyHouse) | 拾起时，获得1瓶药水。获得50金币。将你的最大生命值提升5。获得1张牌。随机升级1张牌。"]


def test_render_treasure_relic_lines_include_main_marker_and_description() -> None:
    lines = render.render_treasure_relic_lines(["Anchor"], pending_main_relic_id="Anchor")

    assert lines == ["[0] 锚 (Anchor) [主遗物] | 每场战斗开始时获得10点格挡。"]


def test_handle_boss_relic_choice_uses_chinese_title_and_prompt(monkeypatch, capsys) -> None:
    engine = RunEngine.create("TESTPHASE254BOSSRELIC", ascension=0)
    engine.state.phase = RunPhase.VICTORY
    engine.state.pending_boss_relic_choices = ["TinyHouse", "CallingBell", "PandoraBox"]
    prompts: list[str] = []

    def _input(prompt: str = "") -> str:
        prompts.append(prompt)
        return "s"

    monkeypatch.setattr(builtins, "input", _input)
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)

    play_cli.handle_boss_relic_choice(engine)
    output = capsys.readouterr().out

    assert "首领遗物" in output
    assert "Boss 遗物" not in output
    assert "小屋子 (TinyHouse) |" in output
    assert prompts == ["首领遗物> "]


def test_translate_room_type_keeps_boss_surface_in_chinese() -> None:
    assert render.translate_room_type(RoomType.BOSS) == "首领房间"
