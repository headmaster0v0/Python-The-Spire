from __future__ import annotations

import builtins

import play_cli
from sts_py.engine.combat.card_effects import _implemented_colorless_combat_card_ids
from sts_py.engine.content.cards_min import COLORLESS_ALL_DEFS, CardRarity
from sts_py.engine.content.relics import RelicTier, get_relic_by_id
from sts_py.engine.run.run_engine import RunEngine, RunPhase


def _make_option(
    reward_type: str,
    *,
    reward_value: int = 0,
    drawback: str = "NONE",
    drawback_value: int = 0,
    label: str | None = None,
) -> dict[str, object]:
    return {
        "category": 0,
        "reward_type": reward_type,
        "reward_value": reward_value,
        "drawback": drawback,
        "drawback_value": drawback_value,
        "label": label or reward_type,
    }


def _capture_cli_seed(monkeypatch, responses: list[str]) -> tuple[dict[str, str], list[str]]:
    created: dict[str, str] = {}
    prompts: list[str] = []
    real_create = play_cli.RunEngine.create

    def _input(prompt: str = "") -> str:
        prompts.append(prompt)
        return responses.pop(0)

    def _create(seed_string: str, ascension: int = 0, character_class: str = "IRONCLAD") -> RunEngine:
        created["seed"] = seed_string
        created["character"] = character_class
        created["ascension"] = str(ascension)
        engine = real_create("TESTPHASE266STARTUP", ascension=0, character_class="IRONCLAD")
        engine.state.phase = RunPhase.GAME_OVER
        return engine

    monkeypatch.setattr(builtins, "input", _input)
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)
    monkeypatch.setattr(play_cli.RunEngine, "create", staticmethod(_create))
    return created, prompts


def test_blank_seed_generates_random_seed_and_echoes_it(monkeypatch, capsys) -> None:
    created, prompts = _capture_cli_seed(monkeypatch, ["", "", ""])

    play_cli.play_cli()
    output = capsys.readouterr().out

    assert created["seed"] != "PHASE243CLI"
    assert created["seed"]
    assert f"本局种子: {created['seed']}" in output
    assert prompts[0] == "种子（留空随机）: "


def test_explicit_seed_is_preserved(monkeypatch, capsys) -> None:
    created, _ = _capture_cli_seed(monkeypatch, ["EXPLICITSEED", "", ""])

    play_cli.play_cli()
    output = capsys.readouterr().out

    assert created["seed"] == "EXPLICITSEED"
    assert "本局种子: EXPLICITSEED" in output


def test_new_run_starts_in_neow_phase() -> None:
    engine = RunEngine.create("TESTPHASE266NEOWSTART", ascension=0)

    assert engine.state.phase == RunPhase.NEOW
    assert len(engine.get_neow_options()) == 4


def test_handle_neow_direct_reward_transitions_to_map(monkeypatch, capsys) -> None:
    engine = RunEngine.create("TESTPHASE266HANDLE", ascension=0)
    engine.state.neow_options = [_make_option("HUNDRED_GOLD", reward_value=100, label="获得 100 金币")]

    monkeypatch.setattr(builtins, "input", lambda prompt="": "0")
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)

    play_cli.handle_neow(engine)
    output = capsys.readouterr().out

    assert "可选的涅奥祝福" in output
    assert "获得 100 金币" in output
    assert engine.state.phase == RunPhase.MAP
    assert engine.state.player_gold == 199


def test_three_enemy_kill_grants_neows_lament_runtime_surface() -> None:
    engine = RunEngine.create("TESTPHASE266LAMENT", ascension=0)
    engine.state.neow_options = [_make_option("THREE_ENEMY_KILL", label="获得涅奥的悲恸")]

    result = engine.choose_neow_option(0)

    assert result["success"] is True
    assert engine.state.phase == RunPhase.MAP
    assert engine.state.neow_blessing is True
    assert engine.state.neow_blessing_remaining == 3
    assert "NeowsLament" in engine.state.relics
    assert engine.state.relic_history[-1]["source"] == "neow"


def test_neow_reward_pick_variants_surface_legal_cards() -> None:
    engine = RunEngine.create("TESTPHASE266CARDPICK", ascension=0)

    engine.state.neow_options = [_make_option("THREE_CARDS")]
    result = engine.choose_neow_option(0)
    cards = engine.get_neow_choice_cards()
    assert result["requires_card_choice"] is True
    assert len(cards) == 3
    assert len(set(cards)) == 3
    assert all(card not in _implemented_colorless_combat_card_ids() for card in cards)

    engine = RunEngine.create("TESTPHASE266RAREPICK", ascension=0)
    engine.state.neow_options = [_make_option("THREE_RARE_CARDS")]
    result = engine.choose_neow_option(0)
    rare_cards = engine.get_neow_choice_cards()
    assert result["requires_card_choice"] is True
    assert len(rare_cards) == 3

    legal_uncommon_colorless = {
        card_id
        for card_id in _implemented_colorless_combat_card_ids()
        if COLORLESS_ALL_DEFS[card_id].rarity == CardRarity.UNCOMMON
    }
    engine = RunEngine.create("TESTPHASE266COLORLESS", ascension=0)
    engine.state.neow_options = [_make_option("RANDOM_COLORLESS")]
    result = engine.choose_neow_option(0)
    colorless_cards = engine.get_neow_choice_cards()
    assert result["requires_card_choice"] is True
    assert set(colorless_cards).issubset(legal_uncommon_colorless)

    legal_rare_colorless = {
        card_id
        for card_id in _implemented_colorless_combat_card_ids()
        if COLORLESS_ALL_DEFS[card_id].rarity == CardRarity.RARE
    }
    engine = RunEngine.create("TESTPHASE266COLORLESS2", ascension=0)
    engine.state.neow_options = [_make_option("RANDOM_COLORLESS_2")]
    result = engine.choose_neow_option(0)
    rare_colorless_cards = engine.get_neow_choice_cards()
    assert result["requires_card_choice"] is True
    assert set(rare_colorless_cards).issubset(legal_rare_colorless)


def test_neow_reward_pick_selection_adds_card_and_finishes() -> None:
    engine = RunEngine.create("TESTPHASE266PICKFINISH", ascension=0)
    engine.state.neow_options = [_make_option("THREE_CARDS")]

    engine.choose_neow_option(0)
    cards = engine.get_neow_choice_cards()
    picked = cards[0]
    result = engine.choose_card_for_neow(0)

    assert result["success"] is True
    assert result["picked_card"] == picked
    assert picked in engine.state.deck
    assert engine.state.phase == RunPhase.MAP


def test_neow_remove_upgrade_and_transform_paths() -> None:
    remove_engine = RunEngine.create("TESTPHASE266REMOVE", ascension=0)
    remove_engine.state.deck = ["Strike", "Defend", "Bash"]
    remove_engine.state.neow_options = [_make_option("REMOVE_CARD")]

    assert remove_engine.choose_neow_option(0)["requires_card_choice"] is True
    assert remove_engine.choose_card_for_neow(0)["removed_card"] == "Strike"
    assert remove_engine.state.deck == ["Defend", "Bash"]
    assert remove_engine.state.phase == RunPhase.MAP

    upgrade_engine = RunEngine.create("TESTPHASE266UPGRADE", ascension=0)
    upgrade_engine.state.deck = ["Bash", "Defend"]
    upgrade_engine.state.neow_options = [_make_option("UPGRADE_CARD")]

    assert upgrade_engine.choose_neow_option(0)["requires_card_choice"] is True
    assert upgrade_engine.choose_card_for_neow(0)["new_card"] == "Bash+"
    assert upgrade_engine.state.deck[0] == "Bash+"
    assert upgrade_engine.state.phase == RunPhase.MAP

    transform_engine = RunEngine.create("TESTPHASE266TRANSFORM", ascension=0)
    transform_engine.state.deck = ["Strike"]
    transform_engine.state.neow_options = [_make_option("TRANSFORM_CARD")]

    assert transform_engine.choose_neow_option(0)["requires_card_choice"] is True
    result = transform_engine.choose_card_for_neow(0)
    assert result["old_card"] == "Strike"
    assert transform_engine.state.deck[0] == result["new_card"]
    assert transform_engine.state.deck[0] != "Strike"


def test_neow_remove_two_and_transform_two_consume_two_picks() -> None:
    remove_engine = RunEngine.create("TESTPHASE266REMOVE2", ascension=0)
    remove_engine.state.deck = ["Strike", "Defend", "Bash"]
    remove_engine.state.neow_options = [_make_option("REMOVE_TWO")]

    assert remove_engine.choose_neow_option(0)["remaining"] == 2
    assert remove_engine.choose_card_for_neow(0)["remaining"] == 1
    final_remove = remove_engine.choose_card_for_neow(0)
    assert final_remove["success"] is True
    assert len(remove_engine.state.deck) == 1
    assert remove_engine.state.phase == RunPhase.MAP

    transform_engine = RunEngine.create("TESTPHASE266TRANSFORM2", ascension=0)
    transform_engine.state.deck = ["Strike", "Defend", "Bash"]
    transform_engine.state.neow_options = [_make_option("TRANSFORM_TWO_CARDS")]

    assert transform_engine.choose_neow_option(0)["remaining"] == 2
    first = transform_engine.choose_card_for_neow(0)
    assert first["remaining"] == 1
    original_tail = list(transform_engine.state.deck)
    second = transform_engine.choose_card_for_neow(0)
    assert second["success"] is True
    assert transform_engine.state.phase == RunPhase.MAP
    assert transform_engine.state.deck != original_tail


def test_neow_direct_relic_potion_and_boss_relic_rewards() -> None:
    common_relic_engine = RunEngine.create("TESTPHASE266COMMONRELIC", ascension=0)
    common_relic_engine.state.neow_options = [_make_option("RANDOM_COMMON_RELIC")]
    result = common_relic_engine.choose_neow_option(0)
    common_relic = get_relic_by_id(result["details"]["relic_id"])
    assert common_relic is not None
    assert common_relic.tier == RelicTier.COMMON

    rare_relic_engine = RunEngine.create("TESTPHASE266RARERELIC", ascension=0)
    rare_relic_engine.state.neow_options = [_make_option("ONE_RARE_RELIC")]
    result = rare_relic_engine.choose_neow_option(0)
    rare_relic = get_relic_by_id(result["details"]["relic_id"])
    assert rare_relic is not None
    assert rare_relic.tier == RelicTier.RARE

    potion_engine = RunEngine.create("TESTPHASE266POTIONS", ascension=0)
    potion_engine.state.neow_options = [_make_option("THREE_SMALL_POTIONS")]
    result = potion_engine.choose_neow_option(0)
    assert len(result["details"]["potions"]) == 3
    assert all(slot != "EmptyPotionSlot" for slot in potion_engine.state.potions[:3])

    boss_engine = RunEngine.create("TESTPHASE266BOSSRELIC", ascension=0)
    starter = boss_engine.state.relics[0]
    boss_engine.state.neow_options = [_make_option("BOSS_RELIC")]
    result = boss_engine.choose_neow_option(0)
    boss_relic = get_relic_by_id(result["details"]["relic_id"])
    assert boss_relic is not None
    assert boss_relic.tier == RelicTier.BOSS
    assert starter not in boss_engine.state.relics
    assert len(boss_engine.state.relics) == 1


def test_neow_drawback_representatives_apply_before_reward() -> None:
    no_gold_engine = RunEngine.create("TESTPHASE266NOGOLD", ascension=0)
    no_gold_engine.state.player_gold = 99
    no_gold_engine.state.neow_options = [_make_option("HUNDRED_GOLD", reward_value=100, drawback="NO_GOLD")]
    no_gold_engine.choose_neow_option(0)
    assert no_gold_engine.state.player_gold == 100

    hp_loss_engine = RunEngine.create("TESTPHASE266HPLOSS", ascension=0)
    hp_loss_engine.state.neow_options = [
        _make_option("HUNDRED_GOLD", reward_value=100, drawback="TEN_PERCENT_HP_LOSS", drawback_value=8)
    ]
    hp_loss_engine.choose_neow_option(0)
    assert hp_loss_engine.state.player_max_hp == 72
    assert hp_loss_engine.state.player_hp == 72

    percent_damage_engine = RunEngine.create("TESTPHASE266DAMAGE", ascension=0)
    percent_damage_engine.state.neow_options = [
        _make_option("HUNDRED_GOLD", reward_value=100, drawback="PERCENT_DAMAGE", drawback_value=24)
    ]
    percent_damage_engine.choose_neow_option(0)
    assert percent_damage_engine.state.player_hp == 56

    curse_engine = RunEngine.create("TESTPHASE266CURSE", ascension=0)
    initial_deck_size = len(curse_engine.state.deck)
    curse_engine.state.neow_options = [_make_option("HUNDRED_GOLD", reward_value=100, drawback="CURSE")]
    curse_engine.choose_neow_option(0)
    assert len(curse_engine.state.deck) == initial_deck_size + 1


def test_handle_neow_card_selection_supports_inspect(monkeypatch, capsys) -> None:
    engine = RunEngine.create("TESTPHASE266NEOWINSPECT", ascension=0)
    engine.state.deck = ["Strike", "Defend", "Bash"]
    engine.state.neow_options = [_make_option("REMOVE_CARD", label="移除 1 张牌")]

    responses = iter(["0", "inspect 1", "1"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(responses))
    monkeypatch.setattr(play_cli, "clear_screen", lambda: None)

    play_cli.handle_neow(engine)
    output = capsys.readouterr().out

    assert "涅奥选牌" in output
    assert "卡牌详情" in output
    assert "ID: Defend" in output
    assert "Defend" not in engine.state.deck
