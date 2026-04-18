from __future__ import annotations

import os
import sys
from typing import Any, Iterable

import wcwidth

from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.run.map_image_generator import show_map_image
from sts_py.engine.run.run_engine import RoomType
from sts_py.terminal.catalog import (
    _looks_presentable_text,
    _looks_sane_translation,
    card_requires_target,
    get_card_info,
    get_potion_info,
    get_power_str,
    get_relic_info,
    translate_monster,
    translate_room_type,
)

ROOM_SHORT_LABELS: dict[RoomType, str] = {
    RoomType.MONSTER: "怪",
    RoomType.ELITE: "精",
    RoomType.BOSS: "王",
    RoomType.EVENT: "?",
    RoomType.SHOP: "商",
    RoomType.REST: "火",
    RoomType.TREASURE: "箱",
    RoomType.EMPTY: " ",
}

ROOM_LONG_LABELS: dict[RoomType, str] = {
    RoomType.MONSTER: "普通怪物",
    RoomType.ELITE: "精英",
    RoomType.BOSS: "首领",
    RoomType.EVENT: "事件",
    RoomType.SHOP: "商店",
    RoomType.REST: "篝火",
    RoomType.TREASURE: "宝箱",
    RoomType.EMPTY: "空房间",
}

MAP_CELL_WIDTH = 6

INTENT_LABELS: dict[MonsterIntent, str] = {
    MonsterIntent.ATTACK: "攻击",
    MonsterIntent.ATTACK_BUFF: "攻击并强化",
    MonsterIntent.ATTACK_DEBUFF: "攻击并施加减益",
    MonsterIntent.ATTACK_DEFEND: "攻击并防御",
    MonsterIntent.BUFF: "强化",
    MonsterIntent.DEBUFF: "减益",
    MonsterIntent.STRONG_DEBUFF: "强减益",
    MonsterIntent.DEFEND: "防御",
    MonsterIntent.DEFEND_DEBUFF: "防御并减益",
    MonsterIntent.DEFEND_BUFF: "防御并强化",
    MonsterIntent.ESCAPE: "逃跑",
    MonsterIntent.MAGIC: "特殊",
    MonsterIntent.NONE: "无",
    MonsterIntent.SLEEP: "沉睡",
    MonsterIntent.STUN: "眩晕",
    MonsterIntent.UNKNOWN: "未知",
    MonsterIntent.WEAK: "虚弱",
    MonsterIntent.VULNERABLE: "易伤",
}

STANCE_LABELS: dict[str, str] = {
    "Neutral": "中立",
    "Wrath": "愤怒",
    "Calm": "平静",
    "Divinity": "神性",
}

ORB_LABELS: dict[str, str] = {
    "Lightning": "闪电",
    "Frost": "冰霜",
    "Dark": "黑暗",
    "Plasma": "等离子",
}

_HELP_LINES: dict[str, list[str]] = {
    "neow": [
        "数字: 选择涅奥祝福",
        "inspect <index>: 在涅奥选牌时查看当前编号卡牌详情",
        "deck / relics / potions / help: 查看信息",
    ],
    "map": [
        "数字: 选择路径",
        "map: 重新显示文本地图",
        "mapimg: 显式打开地图图片",
        "deck: 查看牌组",
        "relics: 查看遗物",
        "potions: 查看药水",
        "inspect <index>: 查看牌组里的卡牌详情",
        "help: 查看帮助",
    ],
    "combat": [
        "<手牌序号> [目标序号]: 打出卡牌",
        "use <药水槽位> [目标序号]: 使用药水",
        "end: 结束回合",
        "status: 查看玩家当前状态",
        "intent: 查看怪物意图摘要",
        "exhaust: 查看消耗堆",
        "draw: 查看抽牌堆",
        "discard: 查看弃牌堆",
        "deck: 查看牌组",
        "relics: 查看遗物",
        "potions: 查看药水",
        "inspect <手牌序号>: 查看手牌详情",
        "map: 查看文本地图",
        "mapimg: 显式打开地图图片",
        "help: 查看帮助",
    ],
    "reward": [
        "g: 查看并确认金币奖励",
        "p: 查看并确认药水奖励",
        "r: 查看并确认遗物奖励",
        "c: 选择卡牌奖励",
        "s: 跳过卡牌奖励",
        "inspect <index>: 查看当前编号卡牌详情",
        "deck / relics / potions / help: 查看信息",
    ],
    "shop": [
        "c0: 购买彩色卡牌 0 号",
        "x0: 购买无色卡牌 0 号",
        "r0: 购买遗物 0 号",
        "p0: 购买药水 0 号",
        "d: 移除牌组中的 1 张牌",
        "l: 离开商店",
        "inspect <index>: 查看当前编号卡牌详情",
        "deck / relics / potions / help: 查看信息",
    ],
    "event": [
        "数字: 选择事件选项",
        "inspect <index>: 查看当前编号卡牌详情",
        "deck / relics / potions / help: 查看信息",
    ],
    "rest": [
        "r: 休息",
        "s: 锻造",
        "k: 回忆红钥匙",
        "inspect <index>: 查看当前编号卡牌详情",
        "deck / relics / potions / help: 查看信息",
    ],
    "treasure": [
        "数字: 拿取对应遗物",
        "k: 拿蓝钥匙并放弃主遗物",
        "relics / help: 查看信息",
    ],
    "victory": [
        "数字: 选择首领遗物",
        "s: 跳过首领遗物",
        "relics / deck / help: 查看信息",
    ],
}


def configure_console_encoding() -> None:
    if os.name != "nt":
        return
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def print_separator(char: str = "=", length: int = 72) -> None:
    print(char * length)


def _str_width(text: str) -> int:
    if not text:
        return 0
    width = wcwidth.wcswidth(text)
    return len(text) if width < 0 else width


def _center_pad(text: str, width: int) -> str:
    current = _str_width(text)
    if current >= width:
        return text
    left = (width - current) // 2
    right = width - current - left
    return " " * left + text + " " * right


def _format_map_node(node, current_node_idx: int, available_ids: set[int]) -> str:
    label = ROOM_SHORT_LABELS.get(node.room_type, node.room_type.value)
    if node.node_id == current_node_idx:
        return f"<{label}>"
    if node.node_id in available_ids:
        return f"[{label}]"
    return f" {label} "


def _build_layer_lines(
    node_ids: list[int],
    node_map: dict[int, object],
    current_node_idx: int,
    available_ids: set[int],
    max_x: int,
    conns_from_below: list[tuple[int, str]],
) -> list[str]:
    row_cells = ["" for _ in range(max_x + 1)]
    conn_cells = ["" for _ in range(max_x + 1)]

    for node_id in node_ids:
        node = node_map[node_id]
        row_cells[node.x] = _format_map_node(node, current_node_idx, available_ids)

    glyph_by_direction = {"left": "/", "up": "|", "right": "\\"}
    for dst_x, direction in conns_from_below:
        glyph = glyph_by_direction.get(direction, "|")
        if glyph not in conn_cells[dst_x]:
            conn_cells[dst_x] += glyph

    row_str = "".join(_center_pad(cell, MAP_CELL_WIDTH) for cell in row_cells)
    conn_str = "".join(_center_pad(cell, MAP_CELL_WIDTH) for cell in conn_cells)
    return [row_str.rstrip(), conn_str.rstrip()]


def format_map_lines(engine) -> list[str]:
    nodes = engine.state.map_nodes
    if not nodes:
        return ["  (地图尚未生成)"]

    node_map = {node.node_id: node for node in nodes}
    floors_y: dict[int, list[int]] = {}
    for node in nodes:
        floors_y.setdefault(node.y, []).append(node.node_id)

    current_node_idx = engine.state.current_node_idx
    available_ids = {node.node_id for node in engine.get_available_paths()}
    min_y = min(floors_y)
    max_y = max(floors_y)
    max_x = max(node.x for node in nodes)

    incoming: dict[int, list[tuple[int, str]]] = {}
    for node in nodes:
        for dst_id in node.connections:
            dst_node = node_map[dst_id]
            if dst_node.y != node.y + 1:
                continue
            incoming.setdefault(dst_node.y, [])
            dx = node.x - dst_node.x
            direction = "left" if dx < 0 else "right" if dx > 0 else "up"
            incoming[dst_node.y].append((dst_node.x, direction))

    lines: list[str] = []
    for y in range(max_y, min_y - 1, -1):
        node_ids = sorted(floors_y.get(y, []), key=lambda node_id: node_map[node_id].x)
        if not node_ids:
            continue
        floor_label = "首领" if y == max_y else f"F{y - min_y:02d}"
        row_line, conn_line = _build_layer_lines(
            node_ids,
            node_map,
            current_node_idx,
            available_ids,
            max_x,
            incoming.get(y, []),
        )
        lines.append(f"  {floor_label}: {row_line}")
        if conn_line.strip():
            lines.append(f"       {conn_line}")
    return lines


def print_map(engine) -> None:
    print()
    print_separator("=")
    print(f"地图 - 第 {engine.state.act} 幕")
    print_separator("=")
    for line in format_map_lines(engine):
        print(line)
    print_separator("-")
    legend = "  图例: <X>=当前位置  [X]=可前往  "
    legend += "  ".join(
        f"{ROOM_SHORT_LABELS[room_type]}:{ROOM_LONG_LABELS[room_type]}"
        for room_type in (
            RoomType.MONSTER,
            RoomType.ELITE,
            RoomType.BOSS,
            RoomType.EVENT,
            RoomType.SHOP,
            RoomType.REST,
            RoomType.TREASURE,
        )
    )
    print(legend)
    print_separator("=")
    print()


def render_status_line(engine) -> str:
    hp = int(getattr(engine.state, "player_hp", 0) or 0)
    max_hp = int(getattr(engine.state, "player_max_hp", 0) or 0)
    combat = getattr(engine.state, "combat", None)
    if str(getattr(engine.state, "phase", "")) == "RunPhase.COMBAT" and combat is not None:
        combat_player = getattr(getattr(combat, "state", None), "player", None)
        if combat_player is not None:
            hp = int(getattr(combat_player, "hp", hp) or hp)
            max_hp = int(getattr(combat_player, "max_hp", max_hp) or max_hp)
    return (
        f"第 {engine.state.act} 幕 | 楼层 {engine.state.floor} | "
        f"生命 {hp}/{max_hp} | "
        f"金币 {engine.state.player_gold}"
    )


def _format_power_summary(power_container) -> str:
    powers = list(getattr(power_container, "powers", []) or [])
    if not powers:
        return "无"
    parts: list[str] = []
    for power in powers:
        power_id = str(getattr(power, "id", type(power).__name__.removesuffix("Power")))
        amount = int(getattr(power, "amount", 0) or 0)
        parts.append(get_power_str(power_id, amount))
    return "，".join(parts)


def translate_stance_name(stance: Any | None) -> str:
    if stance is None:
        return STANCE_LABELS["Neutral"]
    stance_name = str(getattr(stance, "name", getattr(getattr(stance, "stance_type", None), "value", "Neutral")) or "Neutral")
    return STANCE_LABELS.get(stance_name, stance_name)


def _player_character_class(player: Any) -> str:
    return str(getattr(player, "character_class", "IRONCLAD") or "IRONCLAD").upper()


def _player_mantra_amount(player: Any) -> int:
    powers = getattr(player, "powers", None)
    if powers is None:
        return 0
    get_power_amount = getattr(powers, "get_power_amount", None)
    if not callable(get_power_amount):
        return 0
    return max(0, int(get_power_amount("Mantra") or 0))


def _player_stat_parts(player: Any, *, detailed: bool) -> list[str]:
    character_class = _player_character_class(player)
    parts: list[str] = []
    if character_class == "WATCHER":
        label = "姿态:" if detailed else "姿态"
        parts.append(f"{label} {translate_stance_name(getattr(player, 'stance', None))}")
        mantra = _player_mantra_amount(player)
        if mantra > 0:
            parts.append(f"真言 {mantra}")
    parts.append(f"力量 {int(getattr(player, 'strength', 0) or 0)}")
    parts.append(f"敏捷 {int(getattr(player, 'dexterity', 0) or 0)}")
    if character_class == "DEFECT":
        parts.append(f"集中 {int(getattr(player, 'focus', 0) or 0)}")
    return parts


def _should_show_orb_summary(player: Any) -> bool:
    return _player_character_class(player) == "DEFECT"


def _effective_orb_amount(base: Any, focus: Any) -> int:
    return max(0, int(base or 0) + int(focus or 0))


def _format_orb_summary(player) -> str:
    orbs = getattr(player, "orbs", None)
    channels = list(getattr(orbs, "channels", []) or [])
    if not channels:
        return "无"

    focus = int(getattr(player, "focus", 0) or 0)
    parts: list[str] = []
    for idx, orb in enumerate(channels):
        orb_id = str(getattr(orb, "orb_id", getattr(orb, "name", type(orb).__name__)) or "")
        orb_label = ORB_LABELS.get(orb_id, orb_id or "未知")
        if orb_id == "Dark":
            stored_damage = int(getattr(orb, "stored_damage", getattr(orb, "evoke_amount", 0)) or 0)
            passive_gain = _effective_orb_amount(getattr(orb, "passive_amount", 0), focus)
            parts.append(f"[{idx}] {orb_label} 储能 {stored_damage} | 每回合 +{passive_gain}")
            continue
        passive_amount = _effective_orb_amount(getattr(orb, "passive_amount", 0), focus)
        evoke_amount = _effective_orb_amount(getattr(orb, "evoke_amount", 0), focus)
        parts.append(f"[{idx}] {orb_label} 被动 {passive_amount} | 唤起 {evoke_amount}")

    empty_slots = max(0, int(getattr(orbs, "slots", len(channels)) or 0) - len(channels))
    if empty_slots:
        parts.append(f"空槽 {empty_slots}")
    return "；".join(parts)


def _combat_has_no_discard(combat) -> bool:
    checker = getattr(combat, "_player_has_end_turn_no_discard", None)
    if callable(checker):
        try:
            return bool(checker())
        except Exception:
            return False
    return False


def _format_intent(monster) -> str:
    move = getattr(monster, "next_move", None)
    if move is None:
        return "意图 未知"
    label = INTENT_LABELS.get(move.intent, move.intent.name)
    if move.intent.is_attack():
        damage = monster.get_intent_damage()
        hits = int(getattr(move, "multiplier", 0) or 0)
        if bool(getattr(move, "is_multi_damage", False)) or hits > 1:
            return f"意图 {label} {damage}x{max(1, hits)}"
        return f"意图 {label} {damage}"
    return f"意图 {label}"


def render_combat_player_lines(player) -> list[str]:
    summary_line = f"玩家: 格挡 {player.block} | 能量 {player.energy}/{player.max_energy}"
    stat_parts = _player_stat_parts(player, detailed=False)
    if stat_parts:
        summary_line = f"{summary_line} | {' | '.join(stat_parts)}"

    lines = [
        summary_line,
        f"玩家能力: {_format_power_summary(player.powers)}",
    ]
    if _should_show_orb_summary(player):
        lines.append(f"充能球: {_format_orb_summary(player)}")
    return lines


def render_status_detail_lines(engine) -> list[str]:
    lines = [render_status_line(engine)]
    combat = getattr(engine.state, "combat", None)
    if str(getattr(engine.state, "phase", "")) != "RunPhase.COMBAT" or combat is None:
        filled_potions = sum(1 for potion in getattr(engine.state, "potions", []) if potion != "EmptyPotionSlot")
        total_potions = len(getattr(engine.state, "potions", []) or [])
        lines.append("当前不在战斗中。")
        lines.append(
            f"牌组 {len(getattr(engine.state, 'deck', []) or [])} | "
            f"遗物 {len(getattr(engine.state, 'relics', []) or [])} | "
            f"药水 {filled_potions}/{total_potions}"
        )
        return lines

    state = getattr(combat, "state", None)
    player = getattr(state, "player", None)
    card_manager = getattr(state, "card_manager", None)
    if player is None or card_manager is None:
        lines.append("当前战斗状态不可用。")
        return lines

    retained_cards = sum(1 for card in card_manager.hand.cards if getattr(card, "retain", False) or getattr(card, "self_retain", False))
    ethereal_cards = sum(1 for card in card_manager.hand.cards if getattr(card, "is_ethereal", False))
    no_discard = _combat_has_no_discard(combat) or player.powers.has_power("Equilibrium")
    retain_amount = max(0, int(player.powers.get_power_amount("Retain Cards") or 0))
    stat_line = " | ".join(_player_stat_parts(player, detailed=True))

    lines.append(f"玩家: 生命 {player.hp}/{player.max_hp} | 格挡 {player.block} | 能量 {player.energy}/{player.max_energy}")
    if stat_line:
        lines.append(stat_line)
    lines.append(f"能力: {_format_power_summary(player.powers)}")
    if _should_show_orb_summary(player):
        lines.append(f"充能球: {_format_orb_summary(player)}")
    lines.extend(
        [
            f"回合末手牌: 不弃牌 {'是' if no_discard else '否'} | 额外保留 {retain_amount} | 已保留 {retained_cards} | 虚无 {ethereal_cards}",
            (
                f"牌堆: 手牌 {card_manager.get_hand_size()} | 抽牌堆 {card_manager.get_draw_pile_size()} | "
                f"弃牌堆 {card_manager.get_discard_pile_size()} | 消耗堆 {card_manager.get_exhaust_pile_size()}"
            ),
        ]
    )
    return lines


def render_monster_lines(monsters: Iterable[Any]) -> list[str]:
    lines: list[str] = []
    for idx, monster in enumerate(monsters):
        if monster.is_dead():
            continue
        lines.append(
            f"[{idx}] {translate_monster(monster.id)} | "
            f"生命 {monster.hp}/{monster.max_hp} | 格挡 {monster.block} | "
            f"{_format_intent(monster)}"
        )
        lines.append(f"    能力: {_format_power_summary(monster.powers)}")
    return lines


def render_intent_lines(engine) -> list[str]:
    combat = getattr(engine.state, "combat", None)
    if str(getattr(engine.state, "phase", "")) != "RunPhase.COMBAT" or combat is None:
        return ["当前不在战斗中。"]
    lines = render_monster_lines(getattr(getattr(combat, "state", None), "monsters", []) or [])
    return lines or ["当前没有存活怪物。"]


def render_hand_lines(card_ids: Iterable[str]) -> list[str]:
    lines: list[str] = []
    for idx, card_id in enumerate(card_ids):
        name, description = get_card_info(card_id)
        target_tag = " 需目标" if card_requires_target(card_id) else ""
        lines.append(f"[{idx}] {name}{target_tag} - {description}")
    return lines


def render_pending_choice_lines(options: Iterable[dict[str, Any]]) -> list[str]:
    return [f"[{idx}] {option.get('label', option)}" for idx, option in enumerate(options)]


def open_map_image(engine) -> None:
    show_map_image(engine)


def render_exhaust_pile_lines(engine) -> list[str]:
    combat = getattr(engine.state, "combat", None)
    if str(getattr(engine.state, "phase", "")) != "RunPhase.COMBAT" or combat is None:
        return ["当前不在战斗中。"]
    state = getattr(combat, "state", None)
    card_manager = getattr(state, "card_manager", None)
    if card_manager is None:
        return ["当前战斗状态不可用。"]
    card_ids = [getattr(card, "runtime_card_id", getattr(card, "card_id", "")) for card in card_manager.exhaust_pile.cards]
    if not card_ids:
        return ["当前消耗堆为空。"]
    return render_card_collection_lines(card_ids)


def render_card_collection_lines(card_ids: Iterable[str], *, include_index: bool = True) -> list[str]:
    lines: list[str] = []
    for idx, card_id in enumerate(card_ids):
        name, description = get_card_info(card_id)
        prefix = f"[{idx}] " if include_index else ""
        lines.append(f"{prefix}{name} - {description}")
    return lines


def render_card_detail_lines(card_id: str, *, index: int | None = None) -> list[str]:
    name, description = get_card_info(card_id)
    lines = [f"名称: {name}", f"ID: {card_id}", f"说明: {description}"]
    if index is not None:
        lines.insert(0, f"序号: {index}")
    return lines


def render_relic_lines(relic_ids: Iterable[str]) -> list[str]:
    lines: list[str] = []
    for idx, relic_id in enumerate(relic_ids):
        name, description = get_relic_info(relic_id)
        suffix = f" - {description}" if description else ""
        lines.append(f"[{idx}] {name} ({relic_id}){suffix}")
    return lines


def render_potion_lines(potion_ids: Iterable[str]) -> list[str]:
    lines: list[str] = []
    for idx, potion_id in enumerate(potion_ids):
        name, description = get_potion_info(potion_id)
        suffix = f" - {description}" if description else ""
        lines.append(f"[{idx}] {name} ({potion_id}){suffix}")
    return lines


def render_reward_lines(pending: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if pending["gold"]:
        lines.append(f"[g] 查看金币奖励：{pending['gold']}")
    if pending["potion"]:
        potion_id = str(pending["potion"])
        potion_name, potion_desc = get_potion_info(potion_id)
        desc_suffix = f" | {potion_desc}" if potion_desc else ""
        lines.append(f"[p] 查看药水奖励：{potion_name} ({potion_id}){desc_suffix}")
    relics = list(pending.get("relics") or [])
    if pending["relic"]:
        if not relics:
            relics = [str(pending["relic"])]
        lines.append("[r] 查看遗物奖励：")
        for relic_id in relics:
            relic_name, relic_desc = get_relic_info(relic_id)
            desc_suffix = f" | {relic_desc}" if relic_desc else ""
            lines.append(f"    {relic_name} ({relic_id}){desc_suffix}")
    if pending["cards"]:
        lines.append("[c] 选择卡牌奖励：")
        lines.extend(f"    {line}" for line in render_card_collection_lines(pending["cards"]))
        lines.append("[s] 跳过卡牌奖励")
    return lines


def render_shop_card_lines(cards: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    lines: list[str] = []
    inspect_card_ids: list[str] = []
    for inspect_idx, item in enumerate(cards):
        prefix = "c" if item.get("is_colored", True) else "x"
        card_id = str(item["card_id"])
        name, description = get_card_info(card_id)
        sale_text = " [半价]" if item.get("on_sale") else ""
        afford_text = "" if item.get("affordable") else " [金币不足]"
        lines.append(
            f"[{inspect_idx}] {prefix}{item['index']}: {name} - {item['price']}G{sale_text}{afford_text} | {description}"
        )
        inspect_card_ids.append(card_id)
    return lines, inspect_card_ids


def render_shop_relic_lines(relics: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in relics:
        relic_id = str(item["relic_id"])
        name, description = get_relic_info(relic_id)
        afford_text = "" if item.get("affordable") else " [金币不足]"
        desc_suffix = f" | {description}" if description else ""
        lines.append(f"r{item['index']}: {name} ({relic_id}) - {item['price']}G{afford_text}{desc_suffix}")
    return lines


def render_shop_potion_lines(potions: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in potions:
        potion_id = str(item["potion_id"])
        name, description = get_potion_info(potion_id)
        afford_text = "" if item.get("affordable") else " [金币不足]"
        desc_suffix = f" | {description}" if description else ""
        lines.append(f"p{item['index']}: {name} ({potion_id}) - {item['price']}G{afford_text}{desc_suffix}")
    return lines


def render_event_choice_lines(event) -> list[str]:
    lines: list[str] = []
    description_cn = str(getattr(event, "description_cn", "") or "").strip()
    description_en = str(getattr(event, "description", "") or "").strip()
    if _looks_sane_translation(description_cn):
        lines.append(description_cn)
    elif _looks_presentable_text(description_en):
        lines.append(description_en)
    for idx, choice in enumerate(getattr(event, "choices", []) or []):
        choice_cn = str(getattr(choice, "description_cn", "") or "").strip()
        choice_en = str(getattr(choice, "description", "") or "").strip()
        label = choice_cn if _looks_sane_translation(choice_cn) else choice_en
        if not getattr(choice, "enabled", True):
            disabled_cn = str(getattr(choice, "disabled_reason_cn", "") or "").strip()
            disabled_en = str(getattr(choice, "disabled_reason", "") or "").strip()
            if disabled_cn and disabled_cn not in label:
                label = f"{label} ({disabled_cn})"
            elif disabled_en and disabled_en not in label:
                label = f"{label} ({disabled_en})"
        lines.append(f"[{idx}] {label}")
    return lines


def describe_event_card_choice(pending_choice: dict[str, Any] | None) -> str:
    prompt_cn = str((pending_choice or {}).get("prompt_cn", "") or "").strip()
    prompt = str((pending_choice or {}).get("prompt", "") or "").strip()
    if prompt_cn:
        return prompt_cn
    if prompt:
        return prompt
    effect_type = str((pending_choice or {}).get("effect_type", "") or "")
    label_map = {
        "choose_card_to_remove": "移除",
        "choose_card_to_transform": "变形",
        "choose_card_to_upgrade": "升级",
    }
    action = label_map.get(effect_type, "处理")
    return f"事件选牌 - 选择要{action}的牌"


def render_boss_relic_lines(relic_ids: Iterable[str]) -> list[str]:
    lines: list[str] = []
    for idx, relic_id in enumerate(relic_ids):
        name, description = get_relic_info(relic_id)
        desc_suffix = f" | {description}" if description else ""
        lines.append(f"[{idx}] {name} ({relic_id}){desc_suffix}")
    return lines


def render_treasure_relic_lines(
    relic_ids: Iterable[str],
    *,
    pending_main_relic_id: str | None = None,
) -> list[str]:
    lines: list[str] = []
    for idx, relic_id in enumerate(relic_ids):
        name, description = get_relic_info(relic_id)
        main_tag = " [主遗物]" if relic_id == pending_main_relic_id else ""
        desc_suffix = f" | {description}" if description else ""
        lines.append(f"[{idx}] {name} ({relic_id}){main_tag}{desc_suffix}")
    return lines


def render_target_prompt_lines(card_id: str, monsters: Iterable[Any]) -> list[str]:
    card_name, _ = get_card_info(card_id)
    lines = [f"「{card_name}」需要选择目标。"]
    alive = [(idx, monster) for idx, monster in enumerate(monsters) if not monster.is_dead()]
    if alive:
        target_text = "，".join(f"[{idx}] {translate_monster(monster.id)}" for idx, monster in alive)
        lines.append(f"可选目标: {target_text}")
    return lines


def render_combat_command_hint_lines(*, has_pending_choice: bool = False) -> list[str]:
    lines = [
        "出牌: <手牌序号> [目标序号]",
        "药水: use <槽位> [目标序号]",
        "结束回合: end",
        "状态: status",
        "意图: intent",
        "消耗堆: exhaust",
        "更多命令: help",
    ]
    if has_pending_choice:
        lines.insert(0, "当前有待选项：输入编号选择")
    return lines


def describe_neow_card_choice(pending_choice: dict[str, Any] | None) -> str:
    action = str((pending_choice or {}).get("action", "") or "")
    remaining = int((pending_choice or {}).get("remaining", 1) or 1)
    if action == "reward_pick":
        return "涅奥选牌 - 选择要获得的卡牌"
    if action == "remove":
        return f"涅奥选牌 - 选择要移除的卡牌（剩余 {remaining} 张）"
    if action == "transform":
        return f"涅奥选牌 - 选择要变形的卡牌（剩余 {remaining} 张）"
    if action == "upgrade":
        return "涅奥选牌 - 选择要升级的卡牌"
    return "涅奥选牌"


def render_help_lines(context: str) -> list[str]:
    return list(_HELP_LINES.get(context, []))


def render_room_choice(node, *, index: int, burning: bool = False) -> str:
    suffix = " [火精英]" if burning else ""
    return f"[{index}] {translate_room_type(node.room_type)}{suffix} (楼层 {node.floor}, x={node.x})"
