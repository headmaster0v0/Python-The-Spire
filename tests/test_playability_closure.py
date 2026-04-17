from __future__ import annotations

import copy

import builtins

import play_cli
from sts_py.engine.combat.orbs import LightningOrb
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.run.events import ACT1_EVENTS, Event, EventChoice, EventEffect, EventEffectType
from sts_py.engine.run.run_engine import RunEngine, RunPhase


def test_handle_reward_uses_pending_reward_state_and_clears_notifications(monkeypatch) -> None:
    engine = RunEngine.create("TESTPHASE220REWARD", ascension=0)
    engine.state.phase = RunPhase.REWARD
    engine.state.pending_card_reward_cards = ["Anger", "Clash", "Cleave"]
    engine._pending_gold_reward = 15
    engine._pending_potion_reward = "BlockPotion"
    engine._pending_relic_reward = "Anchor"
    initial_gold = engine.state.player_gold

    responses = iter(["g", "", "p", "", "r", "", "c", "0", ""])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(responses))
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)

    play_cli.handle_reward(engine)

    assert engine.state.phase == RunPhase.MAP
    assert engine._pending_gold_reward == 0
    assert engine._pending_potion_reward is None
    assert engine._pending_relic_reward is None
    assert engine.state.pending_card_reward_cards == []
    assert engine.state.card_choices[-1]["picked"] == "Anger"
    assert "Anger" in engine.state.deck
    assert engine.state.player_gold == initial_gold


def test_handle_shop_uses_current_shop_engine_interface(monkeypatch) -> None:
    engine = RunEngine.create("TESTPHASE220SHOP", ascension=0)
    engine._enter_shop()

    responses = iter(["l"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(responses))
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)

    play_cli.handle_shop(engine)

    assert engine.state.phase == RunPhase.MAP


def test_handle_reward_returns_to_victory_after_boss_relic_followup(monkeypatch) -> None:
    engine = RunEngine.create("TESTPHASE226BOSSFOLLOWUP", ascension=0)
    engine.state.phase = RunPhase.VICTORY
    engine.state.pending_boss_relic_choices = ["TinyHouse", "CallingBell", "PandoraBox"]
    engine.choose_boss_relic(0)

    responses = iter(["g", "", "p", "", "r", "", "c", "0", ""])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(responses))
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)

    play_cli.handle_reward(engine)

    assert engine.state.phase == RunPhase.VICTORY
    assert engine._pending_gold_reward == 0
    assert engine._pending_potion_reward is None
    assert engine._pending_relic_reward is None
    assert engine.state.pending_card_reward_cards == []


def test_event_gain_random_relic_uses_real_relic_id() -> None:
    engine = RunEngine.create("TESTPHASE220EVENTRELIC", ascension=0)
    choice = EventChoice(
        description="[Box] Gain a random relic.",
        effects=[EventEffect(EventEffectType.GAIN_RANDOM_RELIC)],
    )

    result = choice.apply(engine)
    effect_result = result["effects_applied"][-1]

    assert effect_result["type"] == "gain_random_relic"
    assert effect_result["relic_id"] != "RandomRelic"
    assert effect_result["relic_id"] in engine.state.relics
    assert engine.get_pending_reward_state()["relic"] == effect_result["relic_id"]
    assert engine.state.relic_history[-1] == {
        "floor": 0,
        "relic_id": effect_result["relic_id"],
        "source": "event",
    }


def test_dead_adventurer_relic_reward_is_not_placeholder(monkeypatch) -> None:
    engine = RunEngine.create("TESTPHASE220DEADADV", ascension=0)
    event = copy.deepcopy(ACT1_EVENTS["Dead Adventurer"])
    da_state = {
        "searches_done": 0,
        "rewards_given": {"gold": True, "nothing": True, "relic": False},
        "encounter_triggered": False,
        "monster_type": None,
        "continuation_mode": False,
    }

    monkeypatch.setattr(engine.state.rng.event_rng, "random_int", lambda upper: upper)
    result = engine._do_dead_adventurer_search(event, da_state)

    assert result["reward"]["type"] == "relic"
    assert result["reward"]["id"] != "RandomRelic"
    assert result["reward"]["id"] in engine.state.relics
    assert engine.get_pending_reward_state()["relic"] == result["reward"]["id"]
    assert engine.state.relic_history[-1] == {
        "floor": 0,
        "relic_id": result["reward"]["id"],
        "source": "event",
    }


def test_event_combat_reward_bridge_uses_real_relics() -> None:
    engine = RunEngine.create("TESTPHASE220EVENTBRIDGE", ascension=0)
    engine.state.current_event_combat = {
        "enemies": ["FungiBeast"],
        "bonus_reward": None,
        "is_event_combat": True,
        "pending_event_rewards": ["relic", "gold"],
    }

    engine._resolve_event_combat_rewards()

    assert engine._pending_relic_reward is not None
    assert engine._pending_relic_reward != "RandomRelic"
    assert engine._pending_relic_reward in engine.state.relics
    assert engine._pending_gold_reward == 30
    assert engine.state.relic_history[-1]["source"] == "event"


def test_handle_map_does_not_open_image_for_text_map_command(monkeypatch) -> None:
    engine = RunEngine.create("TESTPHASE243MAPTEXT", ascension=0)
    engine.state.phase = RunPhase.MAP
    responses = iter(["map", "0"])
    opened: list[bool] = []

    monkeypatch.setattr(builtins, "input", lambda prompt="": next(responses))
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)
    monkeypatch.setattr(play_cli, "open_map_image", lambda current_engine: opened.append(True))

    play_cli.handle_map(engine)

    assert opened == []


def test_handle_map_opens_image_only_for_mapimg_command(monkeypatch) -> None:
    engine = RunEngine.create("TESTPHASE243MAPIMG", ascension=0)
    engine.state.phase = RunPhase.MAP
    responses = iter(["mapimg", "0"])
    opened: list[str] = []

    monkeypatch.setattr(builtins, "input", lambda prompt="": next(responses))
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)
    monkeypatch.setattr(play_cli, "open_map_image", lambda current_engine: opened.append(current_engine.state.seed_string))

    play_cli.handle_map(engine)

    assert opened == ["TESTPHASE243MAPIMG"]


def test_handle_reward_supports_inspect_for_visible_reward_cards(monkeypatch, capsys) -> None:
    engine = RunEngine.create("TESTPHASE254REWARDINSPECT", ascension=0)
    engine.state.phase = RunPhase.REWARD
    engine.state.pending_card_reward_cards = ["Bash", "Defend"]

    responses = iter(["inspect 1", "c", "0", ""])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(responses))
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)

    play_cli.handle_reward(engine)
    output = capsys.readouterr().out

    assert "卡牌详情" in output
    assert "名称: 防御" in output
    assert "ID: Defend" in output
    assert "已选择卡牌奖励：痛击。" in output
    assert "已选择卡牌奖励：Bash。" not in output


def test_handle_rest_smith_supports_inspect_and_shows_feedback(monkeypatch, capsys) -> None:
    engine = RunEngine.create("TESTPHASE255RESTSMITH", ascension=0)
    engine.state.phase = RunPhase.REST
    engine.state.deck = ["Bash", "Defend"]

    responses = iter(["s", "inspect 1", "1", ""])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(responses))
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)

    play_cli.handle_rest(engine)
    output = capsys.readouterr().out

    assert "卡牌详情" in output
    assert "名称: 防御" in output
    assert "已完成锻造。" in output
    assert engine.state.deck[1] == "Defend+"


def test_handle_shop_remove_supports_inspect_and_shows_feedback(monkeypatch, capsys) -> None:
    engine = RunEngine.create("TESTPHASE255SHOPREMOVE", ascension=0)
    engine._enter_shop()

    responses = iter(["d", "inspect 9", "9", "", "l"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(responses))
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)

    play_cli.handle_shop(engine)
    output = capsys.readouterr().out

    assert "卡牌详情" in output
    assert "名称: 痛击" in output
    assert "已移除卡牌：痛击。" in output
    assert "已移除卡牌：Bash。" not in output
    assert "Bash" not in engine.state.deck


def test_handle_treasure_take_relic_shows_feedback(monkeypatch, capsys) -> None:
    engine = RunEngine.create("TESTPHASE255TREASURE", ascension=0)
    engine.state.phase = RunPhase.TREASURE
    engine.state.pending_chest_relic_choices = ["Anchor"]
    engine.state.pending_treasure_relic = "Anchor"

    responses = iter(["0", ""])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(responses))
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)

    play_cli.handle_treasure(engine)
    output = capsys.readouterr().out

    assert "已获得遗物：锚。" in output
    assert "已获得遗物：Anchor。" not in output
    assert "Anchor" in engine.state.relics


def test_handle_event_prefers_description_cn_for_choice_lines(monkeypatch, capsys) -> None:
    engine = RunEngine.create("TESTPHASE254EVENTCN", ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine._current_event = Event(
        id="Phase254 Event",
        name="Phase254 Event",
        description="english body",
        description_cn="中文事件正文",
        choices=[EventChoice(description="english option", description_cn="[中文选项] 离开")],
    )

    monkeypatch.setattr(builtins, "input", lambda prompt="": "0")
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)

    play_cli.handle_event(engine)
    output = capsys.readouterr().out

    assert "中文事件正文" in output
    assert "[中文选项] 离开" in output
    assert "english option" not in output


def test_handle_event_card_selection_supports_inspect_and_labels_action(monkeypatch, capsys) -> None:
    engine = RunEngine.create("TESTPHASE254EVENTINSPECT", ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine.state.deck = ["Bash", "Defend"]
    engine._current_event = Event(
        id="Phase254 Upgrade",
        name="Phase254 Upgrade",
        choices=[EventChoice(description="upgrade", description_cn="[升级]", requires_card_upgrade=True)],
    )

    responses = iter(["0", "inspect 1", "1"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(responses))
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)

    play_cli.handle_event(engine)
    output = capsys.readouterr().out

    assert "事件选牌 - 选择要升级的牌" in output
    assert "名称: 防御" in output
    assert engine.state.deck[1] == "Defend+"


def test_handle_combat_prompts_for_targeted_card_target(monkeypatch) -> None:
    engine = RunEngine.create("TESTPHASE243TARGET", ascension=0)
    engine.start_combat_with_monsters(["FungiBeast", "JawWorm"])
    engine.state.combat.state.card_manager.hand.cards = [CardInstance("Bash")]
    captured: dict[str, int | None] = {"card_idx": None, "target_idx": None}
    played = {"done": False}

    monkeypatch.setattr(builtins, "input", lambda prompt="": "0" if prompt == "战斗> " else "1")
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)

    def _play(card_idx: int, target_idx: int | None = None) -> bool:
        captured["card_idx"] = card_idx
        captured["target_idx"] = target_idx
        played["done"] = True
        return True

    monkeypatch.setattr(engine, "combat_play_card", _play)
    monkeypatch.setattr(engine, "is_combat_over", lambda: played["done"])
    monkeypatch.setattr(engine, "end_combat", lambda: None)

    play_cli.handle_combat(engine)

    assert captured == {"card_idx": 0, "target_idx": 1}


def test_handle_combat_target_prompt_lists_card_and_legal_targets(monkeypatch, capsys) -> None:
    engine = RunEngine.create("TESTPHASE254TARGETPROMPT", ascension=0)
    engine.start_combat_with_monsters(["FungiBeast", "JawWorm"])
    engine.state.combat.state.card_manager.hand.cards = [CardInstance("Bash")]
    played = {"done": False}

    monkeypatch.setattr(builtins, "input", lambda prompt="": "0" if prompt == "战斗> " else "1")
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)
    monkeypatch.setattr(engine, "combat_play_card", lambda card_idx, target_idx=None: played.__setitem__("done", True) or True)
    monkeypatch.setattr(engine, "is_combat_over", lambda: played["done"])
    monkeypatch.setattr(engine, "end_combat", lambda: None)

    play_cli.handle_combat(engine)
    output = capsys.readouterr().out

    assert "「痛击」需要选择目标。" in output
    assert "真菌兽" in output
    assert "大颚虫" in output


def test_handle_combat_keeps_untargeted_card_target_none(monkeypatch) -> None:
    engine = RunEngine.create("TESTPHASE243NOTARGET", ascension=0)
    engine.start_combat_with_monsters(["FungiBeast", "JawWorm"])
    engine.state.combat.state.card_manager.hand.cards = [CardInstance("Cleave")]
    captured: dict[str, int | None] = {"card_idx": None, "target_idx": None}
    played = {"done": False}

    monkeypatch.setattr(builtins, "input", lambda prompt="": "0")
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)

    def _play(card_idx: int, target_idx: int | None = None) -> bool:
        captured["card_idx"] = card_idx
        captured["target_idx"] = target_idx
        played["done"] = True
        return True

    monkeypatch.setattr(engine, "combat_play_card", _play)
    monkeypatch.setattr(engine, "is_combat_over", lambda: played["done"])
    monkeypatch.setattr(engine, "end_combat", lambda: None)

    play_cli.handle_combat(engine)

    assert captured == {"card_idx": 0, "target_idx": None}


def test_handle_combat_header_shows_persistent_command_hints(monkeypatch, capsys) -> None:
    engine = RunEngine.create("TESTPHASE266COMBATHINTS", ascension=0)
    engine.start_combat_with_monsters(["FungiBeast"])

    monkeypatch.setattr(builtins, "input", lambda prompt="": "end")
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)
    monkeypatch.setattr(engine, "combat_end_turn", lambda: setattr(engine.state, "phase", RunPhase.MAP))
    monkeypatch.setattr(engine, "is_combat_over", lambda: False)

    play_cli.handle_combat(engine)
    output = capsys.readouterr().out

    assert "出牌: <手牌序号> [目标序号]" in output
    assert "药水: use <槽位> [目标序号]" in output
    assert "结束回合: end" in output
    assert "更多命令: help" in output


def test_handle_combat_invalid_input_shows_concrete_syntax(monkeypatch, capsys) -> None:
    engine = RunEngine.create("TESTPHASE266COMBATINVALID", ascension=0)
    engine.start_combat_with_monsters(["FungiBeast"])
    responses = iter(["abc", "end"])

    monkeypatch.setattr(builtins, "input", lambda prompt="": next(responses))
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)
    monkeypatch.setattr(engine, "combat_end_turn", lambda: setattr(engine.state, "phase", RunPhase.MAP))
    monkeypatch.setattr(engine, "is_combat_over", lambda: False)

    play_cli.handle_combat(engine)
    output = capsys.readouterr().out

    assert "战斗命令格式" in output
    assert "use <槽位> [目标序号]" in output
    assert "end" in output


def test_handle_combat_reality_info_commands_show_live_state(monkeypatch, capsys) -> None:
    engine = RunEngine.create("TESTPHASE267INFOCOMMANDS", ascension=0, character_class="DEFECT")
    engine.start_combat_with_monsters(["FungiBeast"])
    engine.state.combat.state.player.focus = 1
    engine.state.combat.state.player.orbs.channel(LightningOrb())
    engine.state.combat.state.card_manager.exhaust_pile.cards = [CardInstance("Bash")]
    responses = iter(["status", "intent", "exhaust", "end"])

    monkeypatch.setattr(builtins, "input", lambda prompt="": next(responses))
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)
    monkeypatch.setattr(engine, "combat_end_turn", lambda: setattr(engine.state, "phase", RunPhase.MAP))
    monkeypatch.setattr(engine, "is_combat_over", lambda: False)

    play_cli.handle_combat(engine)
    output = capsys.readouterr().out

    assert "状态" in output
    assert "怪物意图" in output
    assert "消耗堆" in output
    assert "充能球:" in output
    assert "闪电" in output
    assert "真菌兽" in output
    assert "当前消耗堆为空。" not in output
    assert "痛击" in output


def test_render_terminal_outcome_uses_real_titles(monkeypatch, capsys) -> None:
    victory_engine = RunEngine.create("TESTPHASE267VICTORY", ascension=0)
    victory_engine.state.act = 4
    victory_engine.state.phase = RunPhase.VICTORY

    defeat_engine = RunEngine.create("TESTPHASE267DEFEAT", ascension=0)
    defeat_engine.state.phase = RunPhase.GAME_OVER

    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)

    assert play_cli._render_terminal_outcome(victory_engine) is True
    assert play_cli._render_terminal_outcome(defeat_engine) is True
    output = capsys.readouterr().out

    assert "胜利" in output
    assert "失败" in output
    assert "本局已结束。" in output
