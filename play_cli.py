from __future__ import annotations

import secrets
from typing import Iterable

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import RNG
from sts_py.engine.core.seed import generate_unoffensive_seed, seed_long_to_string
from sts_py.engine.run.run_engine import RunEngine, RunPhase
from sts_py.terminal.catalog import (
    card_requires_target,
    translate_card_name,
    translate_event_name,
    translate_potion,
    translate_relic,
    translate_room_type,
)
from sts_py.terminal.render import (
    clear_screen,
    describe_event_card_choice,
    describe_neow_card_choice,
    configure_console_encoding,
    format_map_lines,
    open_map_image,
    print_map,
    print_separator,
    render_boss_relic_lines,
    render_card_collection_lines,
    render_card_detail_lines,
    render_combat_player_lines,
    render_exhaust_pile_lines,
    render_event_choice_lines,
    render_help_lines,
    render_hand_lines,
    render_combat_command_hint_lines,
    render_intent_lines,
    render_monster_lines,
    render_pending_choice_lines,
    render_potion_lines,
    render_relic_lines,
    render_reward_lines,
    render_room_choice,
    render_shop_card_lines,
    render_shop_potion_lines,
    render_shop_relic_lines,
    render_status_detail_lines,
    render_status_line,
    render_target_prompt_lines,
    render_treasure_relic_lines,
)


def _print_title(title: str) -> None:
    print_separator("=")
    print(title)
    print_separator("=")


def _parse_int(text: str) -> int | None:
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def _generate_random_seed_string() -> str:
    while True:
        _, seed_long = generate_unoffensive_seed(RNG.from_seed(secrets.randbits(64)))
        seed_string = seed_long_to_string(seed_long)
        if seed_string:
            return seed_string


def _alive_monster_indices(engine: RunEngine) -> list[int]:
    combat = engine.state.combat
    if combat is None:
        return []
    return [idx for idx, monster in enumerate(combat.state.monsters) if not monster.is_dead()]


def _show_lines(title: str, lines: Iterable[str]) -> None:
    _print_title(title)
    for line in lines:
        print(line)
    print_separator("-")


def _show_deck(engine: RunEngine) -> None:
    _show_lines("牌组", render_card_collection_lines(engine.state.deck))


def _show_relics(engine: RunEngine) -> None:
    _show_lines("遗物", render_relic_lines(engine.state.relics))


def _show_potions(engine: RunEngine) -> None:
    _show_lines("药水", render_potion_lines(engine.state.potions))


def _show_card_detail(card_id: str, *, index: int | None = None) -> None:
    _show_lines("卡牌详情", render_card_detail_lines(card_id, index=index))


def _pause_for_feedback(message: str | None = None) -> None:
    if message:
        print(message)
    input("按 Enter 继续...")


def _format_failure(prefix: str, reason: str | None = None) -> str:
    detail = str(reason or "未知原因").strip() or "未知原因"
    return f"{prefix}: {detail}"


def _format_shop_replacement(result: dict[str, object]) -> str:
    replacement_card = result.get("replacement_card")
    if replacement_card:
        return translate_card_name(str(replacement_card))
    replacement_relic = result.get("replacement_relic")
    if replacement_relic:
        return translate_relic(str(replacement_relic))
    replacement_potion = result.get("replacement_potion")
    if replacement_potion:
        return translate_potion(str(replacement_potion))
    return ""


def _prompt_card_selection(
    engine: RunEngine,
    *,
    title: str,
    prompt: str,
    card_ids: list[str],
    context: str,
) -> int:
    while True:
        _show_lines(title, render_card_collection_lines(card_ids))
        raw = input(prompt).strip()
        if not raw:
            continue
        if _handle_common_info_command(engine, raw, context=context, inspect_cards=list(card_ids)):
            continue
        pick_idx = _parse_int(raw)
        if pick_idx is None or not 0 <= pick_idx < len(card_ids):
            _pause_for_feedback("操作失败: 请输入有效的卡牌序号。")
            continue
        return pick_idx


def _show_pile(engine: RunEngine, pile_name: str) -> None:
    combat = engine.state.combat
    if combat is None or combat.state.card_manager is None:
        print("当前不在战斗中。")
        return
    card_manager = combat.state.card_manager
    if pile_name == "draw":
        card_ids = [card.card_id for card in card_manager.draw_pile.cards]
        _show_lines("抽牌堆", render_card_collection_lines(card_ids))
    elif pile_name == "discard":
        card_ids = [card.card_id for card in card_manager.discard_pile.cards]
        _show_lines("弃牌堆", render_card_collection_lines(card_ids))


def _handle_common_info_command(
    engine: RunEngine,
    raw: str,
    *,
    context: str,
    inspect_cards: list[str] | None = None,
    allow_draw_discard: bool = False,
) -> bool:
    command = raw.strip()
    lowered = command.lower()

    if lowered == "help":
        _show_lines("帮助", render_help_lines(context))
        return True
    if lowered == "map":
        print_map(engine)
        return True
    if lowered == "mapimg":
        open_map_image(engine)
        return True
    if lowered == "deck":
        _show_deck(engine)
        return True
    if lowered == "relics":
        _show_relics(engine)
        return True
    if lowered == "potions":
        _show_potions(engine)
        return True
    if lowered == "status":
        _show_lines("状态", render_status_detail_lines(engine))
        return True
    if lowered == "intent":
        _show_lines("怪物意图", render_intent_lines(engine))
        return True
    if lowered == "exhaust":
        _show_lines("消耗堆", render_exhaust_pile_lines(engine))
        return True
    if allow_draw_discard and lowered == "draw":
        _show_pile(engine, "draw")
        return True
    if allow_draw_discard and lowered == "discard":
        _show_pile(engine, "discard")
        return True
    if lowered.startswith("inspect "):
        idx = _parse_int(command.split(maxsplit=1)[1])
        if idx is None:
            print("请输入有效的序号。")
            return True
        card_ids = inspect_cards if inspect_cards is not None else engine.state.deck
        if not 0 <= idx < len(card_ids):
            print("序号超出范围。")
            return True
        _show_card_detail(card_ids[idx], index=idx)
        return True
    return False


def _print_map_header(engine: RunEngine) -> None:
    _print_title("地图阶段")
    print(render_status_line(engine))
    current_room = engine.get_current_room()
    if current_room is not None:
        print(f"当前位置: {translate_room_type(current_room.room_type)}")
    print_separator("-")
    print_map(engine)


def _print_combat_header(engine: RunEngine) -> list[str]:
    combat = engine.state.combat
    assert combat is not None
    hand_cards = [card.card_id for card in combat.state.card_manager.hand.cards]
    player = combat.state.player

    _print_title("战斗")
    print(render_status_line(engine))
    for line in render_combat_player_lines(player):
        print(line)
    print_separator("-")

    for line in render_monster_lines(combat.state.monsters):
        print(line)

    print_separator("-")
    if hand_cards:
        print("手牌:")
        for line in render_hand_lines(hand_cards):
            print(line)
    else:
        print("手牌为空。")

    pending_choices = combat.get_pending_choices()
    if pending_choices:
        print_separator("-")
        print("待选项:")
        for line in render_pending_choice_lines(pending_choices):
            print(line)
    print_separator("-")
    for line in render_combat_command_hint_lines(has_pending_choice=bool(pending_choices)):
        print(line)
    print_separator("-")
    return hand_cards


def handle_neow(engine: RunEngine, reached_boss: bool = False) -> None:
    while engine.state.phase == RunPhase.NEOW:
        clear_screen()
        _print_title("涅奥")
        print(render_status_line(engine))
        print_separator("-")

        pending_choice = getattr(engine.state, "pending_neow_choice", None)
        if pending_choice:
            card_ids = engine.get_neow_choice_cards()
            _show_lines(describe_neow_card_choice(pending_choice), render_card_collection_lines(card_ids))
            raw = input("涅奥选牌> ").strip()
            if not raw:
                continue
            if _handle_common_info_command(engine, raw, context="neow", inspect_cards=card_ids):
                continue
            pick_idx = _parse_int(raw)
            if pick_idx is None:
                _pause_for_feedback("选择失败: 请输入有效的卡牌序号。")
                continue
            result = engine.choose_card_for_neow(pick_idx)
            if result.get("success"):
                continue
            _pause_for_feedback(_format_failure("选择失败", result.get("reason")))
            continue

        print("可选的涅奥祝福：")
        for idx, option in enumerate(engine.get_neow_options()):
            print(f"[{idx}] {option.get('label', '')}")
        print_separator("-")
        raw = input("涅奥> ").strip()
        if not raw:
            continue
        if _handle_common_info_command(engine, raw, context="neow"):
            continue
        choice_idx = _parse_int(raw)
        if choice_idx is None:
            _pause_for_feedback("选择失败: 请输入有效的选项序号。")
            continue
        result = engine.choose_neow_option(choice_idx)
        if result.get("success"):
            continue
        _pause_for_feedback(_format_failure("选择失败", result.get("reason")))


def handle_map(engine: RunEngine) -> None:
    while engine.state.phase == RunPhase.MAP:
        clear_screen()
        _print_map_header(engine)
        available = engine.get_available_paths()
        if not available:
            print("没有可选路径。")
            return
        print("可前往房间:")
        for idx, node in enumerate(available):
            print(render_room_choice(node, index=idx, burning=getattr(node, "burning_elite", False)))
        print_separator("-")
        raw = input("地图> ").strip()
        if not raw:
            continue
        if _handle_common_info_command(engine, raw, context="map"):
            continue
        choice_idx = _parse_int(raw)
        if choice_idx is None or not 0 <= choice_idx < len(available):
            print("请输入有效的路径序号。")
            continue
        if engine.choose_path(available[choice_idx].node_id):
            return
        print("无法进入该房间。")


def _prompt_target(engine: RunEngine, card_id: str) -> int | None:
    alive = _alive_monster_indices(engine)
    if not alive:
        return None
    if len(alive) == 1:
        return alive[0]
    combat = engine.state.combat
    assert combat is not None
    for line in render_target_prompt_lines(card_id, combat.state.monsters):
        print(line)
    target_raw = input("目标> ").strip()
    target_idx = _parse_int(target_raw)
    if target_idx is None or target_idx not in alive:
        print("目标无效。")
        return None
    return target_idx


def _try_use_potion(engine: RunEngine, raw: str) -> bool:
    if not raw.lower().startswith("use "):
        return False
    parts = raw.split()
    if len(parts) < 2:
        print("用法: use <药水槽位> [目标序号]")
        return True
    potion_idx = _parse_int(parts[1])
    target_idx = _parse_int(parts[2]) if len(parts) >= 3 else 0
    if potion_idx is None:
        print("请输入有效的药水槽位。")
        return True
    if engine.use_potion(potion_idx, target_idx or 0):
        print("已使用药水。")
    else:
        print("药水使用失败。")
    return True


def handle_combat(engine: RunEngine) -> None:
    while engine.state.phase == RunPhase.COMBAT and engine.state.combat is not None:
        clear_screen()
        hand_cards = _print_combat_header(engine)
        raw = input("战斗> ").strip()
        if not raw:
            continue
        if _handle_common_info_command(
            engine,
            raw,
            context="combat",
            inspect_cards=hand_cards,
            allow_draw_discard=True,
        ):
            continue
        if _try_use_potion(engine, raw):
            if engine.is_combat_over():
                engine.end_combat()
                return
            continue
        if raw.lower() == "end":
            engine.combat_end_turn()
            if engine.is_combat_over():
                engine.end_combat()
                return
            continue

        pending_choices = engine.get_combat_choices()
        if pending_choices:
            option_idx = _parse_int(raw)
            if option_idx is None:
                print("当前有待选项，请输入数字序号选择。")
                continue
            if not engine.choose_combat_option(option_idx):
                print("选项无效。")
                continue
            if engine.is_combat_over():
                engine.end_combat()
                return
            continue

        parts = raw.split()
        card_idx = _parse_int(parts[0])
        if card_idx is None or not 0 <= card_idx < len(hand_cards):
            print("战斗命令格式：<手牌序号> [目标序号]、use <槽位> [目标序号]、end")
            continue

        target_idx = _parse_int(parts[1]) if len(parts) >= 2 else None
        if card_requires_target(hand_cards[card_idx]) and target_idx is None:
            target_idx = _prompt_target(engine, hand_cards[card_idx])
            if target_idx is None:
                continue

        if not engine.combat_play_card(card_idx, target_idx):
            print("打牌失败。")
            continue
        if engine.is_combat_over():
            engine.end_combat()
            return


def handle_rest(engine: RunEngine) -> None:
    while engine.state.phase == RunPhase.REST:
        clear_screen()
        _print_title("篝火")
        print(render_status_line(engine))
        print_separator("-")
        print("[r] 休息")
        print("[s] 锻造")
        if not engine.state.ruby_key_obtained:
            print("[k] 回忆红钥匙")
        print_separator("-")
        raw = input("篝火> ").strip()
        if not raw:
            continue
        if _handle_common_info_command(engine, raw, context="rest"):
            continue
        lowered = raw.lower()
        if lowered == "r":
            healed = engine.rest()
            _pause_for_feedback(f"已休息，恢复 {healed} 点生命。")
            return
        if lowered == "k":
            if engine.recall():
                _pause_for_feedback("已获得红钥匙。")
                return
            _pause_for_feedback("操作失败: 当前不能回忆红钥匙。")
            continue
        if lowered == "s":
            upgradable = [(idx, card_id) for idx, card_id in enumerate(engine.state.deck) if "+" not in card_id]
            if not upgradable:
                _pause_for_feedback("操作失败: 当前没有可升级的牌。")
                continue
            upgradable_card_ids = [card_id for _, card_id in upgradable]
            pick_idx = _prompt_card_selection(
                engine,
                title="可升级卡牌",
                prompt="锻造> ",
                card_ids=upgradable_card_ids,
                context="rest",
            )
            engine.smith(upgradable[pick_idx][0])
            _pause_for_feedback("已完成锻造。")
            return
        _pause_for_feedback("操作失败: 请输入 r、s 或 k。")


def handle_boss_relic_choice(engine: RunEngine) -> None:
    while engine.state.phase == RunPhase.VICTORY and engine.state.pending_boss_relic_choices:
        clear_screen()
        _print_title("首领遗物")
        print(render_status_line(engine))
        print_separator("-")
        for line in render_boss_relic_lines(engine.state.pending_boss_relic_choices):
            print(line)
        print("[s] 跳过")
        print_separator("-")
        raw = input("首领遗物> ").strip()
        if not raw:
            continue
        if _handle_common_info_command(engine, raw, context="victory"):
            continue
        if raw.lower() == "s":
            engine.skip_boss_relic_choice()
            return
        pick_idx = _parse_int(raw)
        if pick_idx is None:
            _pause_for_feedback("选择失败: 请输入有效的遗物序号。")
            continue
        result = engine.choose_boss_relic(pick_idx)
        if result.get("success"):
            return
        _pause_for_feedback(_format_failure("选择失败", result.get("reason")))


def handle_treasure(engine: RunEngine) -> None:
    while engine.state.phase == RunPhase.TREASURE:
        clear_screen()
        _print_title("宝箱")
        print(render_status_line(engine))
        print_separator("-")
        for line in render_treasure_relic_lines(
            engine.state.pending_chest_relic_choices,
            pending_main_relic_id=engine.state.pending_treasure_relic,
        ):
            print(line)
        if engine.state.pending_treasure_relic and not engine.state.sapphire_key_obtained:
            print("[k] 拿蓝钥匙并放弃主遗物")
        print_separator("-")
        raw = input("宝箱> ").strip()
        if not raw:
            continue
        if _handle_common_info_command(engine, raw, context="treasure"):
            continue
        if raw.lower() == "k":
            result = engine.take_sapphire_key()
            if result.get("success"):
                _pause_for_feedback("已获得蓝钥匙。")
                if engine.state.phase != RunPhase.TREASURE:
                    return
                continue
            _pause_for_feedback(_format_failure("操作失败", result.get("reason")))
            continue
        pick_idx = _parse_int(raw)
        if pick_idx is None:
            _pause_for_feedback("操作失败: 请输入有效的遗物序号。")
            continue
        result = engine.take_treasure_relic(pick_idx)
        if result.get("success"):
            relic_id = result.get("relic_id")
            if relic_id:
                _pause_for_feedback(f"已获得遗物：{translate_relic(str(relic_id))}。")
            if engine.state.phase != RunPhase.TREASURE:
                return
            continue
        _pause_for_feedback(_format_failure("操作失败", result.get("reason")))


def handle_event(engine: RunEngine) -> None:
    while engine.state.phase == RunPhase.EVENT:
        clear_screen()
        event = engine.get_current_event()
        if event is None:
            return
        _print_title(f"事件 - {translate_event_name(event)}")
        print(render_status_line(engine))
        print_separator("-")
        for line in render_event_choice_lines(event):
            print(line)
        print_separator("-")
        raw = input("事件> ").strip()
        if not raw:
            continue
        if _handle_common_info_command(engine, raw, context="event"):
            continue
        choice_idx = _parse_int(raw)
        if choice_idx is None:
            _pause_for_feedback("选择失败: 请输入有效的选项序号。")
            continue
        result = engine.choose_event_option(choice_idx)
        if result.get("requires_card_choice"):
            handle_card_selection(engine)
            return
        if result.get("success", True) or engine.state.phase != RunPhase.EVENT:
            return
        _pause_for_feedback(_format_failure("选择失败", result.get("reason")))


def handle_card_selection(engine: RunEngine) -> None:
    while engine.state.phase == RunPhase.EVENT and getattr(engine.state, "pending_card_choice", None):
        clear_screen()
        pending_choice = getattr(engine.state, "pending_card_choice", None)
        _show_lines(
            describe_event_card_choice(pending_choice),
            render_card_collection_lines(engine.state.deck),
        )
        raw = input("选牌> ").strip()
        if not raw:
            continue
        if _handle_common_info_command(engine, raw, context="event", inspect_cards=list(engine.state.deck)):
            continue
        pick_idx = _parse_int(raw)
        if pick_idx is None:
            _pause_for_feedback("选择失败: 请输入有效的卡牌序号。")
            continue
        result = engine.choose_card_for_event(pick_idx)
        if result.get("success"):
            return
        _pause_for_feedback(_format_failure("选择失败", result.get("reason")))


def _print_reward_surface(engine: RunEngine, pending: dict) -> None:
    _print_title("奖励")
    print(render_status_line(engine))
    print_separator("-")
    for line in render_reward_lines(pending):
        print(line)
    print_separator("-")


def handle_reward(engine: RunEngine) -> None:
    while engine.state.phase == RunPhase.REWARD:
        pending = engine.get_pending_reward_state()
        clear_screen()
        _print_reward_surface(engine, pending)
        raw = input("奖励> ").strip()
        if not raw:
            continue
        reward_cards = list(pending["cards"] or [])
        if _handle_common_info_command(engine, raw, context="reward", inspect_cards=reward_cards):
            continue

        lowered = raw.lower()
        if lowered == "g":
            if pending["gold"]:
                _pause_for_feedback(f"已确认金币奖励：{pending['gold']}。")
                engine.clear_pending_reward_notifications(gold=True, potion=False, relic=False)
            continue
        if lowered == "p":
            if pending["potion"]:
                potion_id = str(pending["potion"])
                _pause_for_feedback(f"已确认药水奖励：{translate_potion(potion_id)}。")
                engine.clear_pending_reward_notifications(gold=False, potion=True, relic=False)
            continue
        if lowered == "r":
            relics = list(pending.get("relics") or [])
            if pending["relic"]:
                if not relics:
                    relics = [str(pending["relic"])]
                _pause_for_feedback("已确认遗物奖励：" + "，".join(translate_relic(relic_id) for relic_id in relics))
                engine.clear_pending_reward_notifications(gold=False, potion=False, relic=True)
            continue
        if lowered == "s":
            if pending["cards"]:
                engine.skip_card_reward()
                _pause_for_feedback("已跳过卡牌奖励。")
                if engine.state.phase != RunPhase.REWARD:
                    return
            continue
        if lowered == "c":
            if not pending["cards"]:
                _pause_for_feedback("操作失败: 当前没有卡牌奖励。")
                continue
            pick_idx = _prompt_card_selection(
                engine,
                title="可选卡牌奖励",
                prompt="选牌> ",
                card_ids=list(pending["cards"]),
                context="reward",
            )
            picked = pending["cards"][pick_idx]
            not_picked = [card_id for idx, card_id in enumerate(pending["cards"]) if idx != pick_idx]
            engine.choose_card_reward(picked, not_picked)
            _pause_for_feedback(f"已选择卡牌奖励：{translate_card_name(picked)}。")
            if engine.state.phase != RunPhase.REWARD:
                return
            continue
        _pause_for_feedback("操作失败: 请输入 g、p、r、c 或 s。")


def handle_shop(engine: RunEngine) -> None:
    while engine.state.phase == RunPhase.SHOP:
        clear_screen()
        shop = engine.get_shop()
        if shop is None:
            return
        _print_title("商店")
        print(render_status_line(engine))
        print_separator("-")

        card_lines, inspect_cards = render_shop_card_lines(shop.get_available_cards())
        if card_lines:
            print("卡牌:")
            for line in card_lines:
                print(line)
            print_separator("-")

        relics = shop.get_available_relics()
        if relics:
            print("遗物:")
            for line in render_shop_relic_lines(relics):
                print(line)
            print_separator("-")

        potions = shop.get_available_potions()
        if potions:
            print("药水:")
            for line in render_shop_potion_lines(potions):
                print(line)
            print_separator("-")

        if shop.is_card_remove_available():
            print(f"[d] 移除卡牌 - {shop.get_card_remove_price()}G")
        print("[l] 离开商店")
        print_separator("-")

        raw = input("商店> ").strip()
        if not raw:
            continue
        if _handle_common_info_command(engine, raw, context="shop", inspect_cards=inspect_cards):
            continue

        lowered = raw.lower()
        if lowered == "l":
            engine.leave_shop()
            return
        if lowered == "d":
            if not shop.is_card_remove_available():
                _pause_for_feedback("操作失败: 本次商店已经移除过卡牌。")
                continue
            pick_idx = _prompt_card_selection(
                engine,
                title="可移除卡牌",
                prompt="移除> ",
                card_ids=list(engine.state.deck),
                context="shop",
            )
            result = shop.remove_card(engine.state.deck[pick_idx])
            if result.get("success"):
                removed_card = str(
                    result.get("card_id")
                    or (engine.state.removed_cards[-1] if getattr(engine.state, "removed_cards", None) else "")
                )
                label = translate_card_name(removed_card) if removed_card else "所选卡牌"
                _pause_for_feedback(f"已移除卡牌：{label}。")
                continue
            _pause_for_feedback(_format_failure("操作失败", result.get("reason")))
            continue

        if len(raw) >= 2 and raw[0].lower() in {"c", "x", "r", "p"}:
            slot = _parse_int(raw[1:])
            if slot is None:
                _pause_for_feedback("购买失败: 请输入有效的商店槽位。")
                continue
            prefix = raw[0].lower()
            if prefix == "c":
                result = shop.buy_card(slot, is_colored=True)
            elif prefix == "x":
                result = shop.buy_card(slot, is_colored=False)
            elif prefix == "r":
                result = shop.buy_relic(slot)
            else:
                result = shop.buy_potion(slot)
            if result.get("success"):
                replacement = _format_shop_replacement(result)
                if replacement:
                    _pause_for_feedback(f"购买成功。信使补货：{replacement}")
                else:
                    _pause_for_feedback("购买成功。")
                continue
            _pause_for_feedback(_format_failure("购买失败", result.get("reason")))
            continue

        _pause_for_feedback("操作失败: 请输入 c/x/r/p 开头的购买命令，或 d / l。")


def _is_final_victory(engine: RunEngine) -> bool:
    if engine.state.act >= 4:
        return True
    if engine.state.act == 3 and not engine.has_all_act4_keys():
        return True
    return False


def _render_terminal_outcome(engine: RunEngine) -> bool:
    if engine.state.phase == RunPhase.VICTORY and _is_final_victory(engine):
        clear_screen()
        _print_title("胜利")
        print(render_status_line(engine))
        print("本局已结束。")
        print_separator("-")
        return True
    if engine.state.phase == RunPhase.GAME_OVER:
        clear_screen()
        _print_title("失败")
        print(render_status_line(engine))
        print("本局已结束。")
        print_separator("-")
        return True
    return False


def play_cli() -> None:
    configure_console_encoding()
    clear_screen()
    _print_title("杀戮尖塔 - 终端试玩")
    seed_input = input("种子（留空随机）: ").strip()
    seed_string = seed_input or _generate_random_seed_string()
    character = input("角色（IRONCLAD/SILENT/DEFECT/WATCHER，留空默认 IRONCLAD）: ").strip().upper() or "IRONCLAD"
    ascension = _parse_int(input("进阶等级（留空默认 0）: ").strip()) or 0
    print(f"本局种子: {seed_string}")
    engine = RunEngine.create(seed_string, ascension=ascension, character_class=character)

    while True:
        phase = engine.state.phase
        if phase == RunPhase.NEOW:
            handle_neow(engine)
        elif phase == RunPhase.MAP:
            handle_map(engine)
        elif phase == RunPhase.COMBAT:
            handle_combat(engine)
        elif phase == RunPhase.REWARD:
            handle_reward(engine)
        elif phase == RunPhase.EVENT:
            handle_event(engine)
        elif phase == RunPhase.SHOP:
            handle_shop(engine)
        elif phase == RunPhase.REST:
            handle_rest(engine)
        elif phase == RunPhase.TREASURE:
            handle_treasure(engine)
        elif phase == RunPhase.VICTORY:
            if engine.state.pending_boss_relic_choices:
                handle_boss_relic_choice(engine)
                continue
            if _render_terminal_outcome(engine):
                break
            engine.transition_to_next_act()
        elif phase == RunPhase.GAME_OVER:
            _render_terminal_outcome(engine)
            break
        else:
            print(f"未知阶段: {phase}")
            break


if __name__ == "__main__":
    play_cli()
