"""Combat logging system for debugging and verification."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


MONSTER_NAME_MAP = {
    "Cultist": "邪教徒",
    "JawWorm": "颚虫",
    "FuzzyLouseNormal": "大头虱(攻击)",
    "FuzzyLouseDefensive": "大头虱(防御)",
    "SlaverRed": "红奴隶贩子",
    "SlaverBlue": "蓝奴隶贩子",
    "GremlinNob": "地精大块头",
    "Lagavulin": "乐加维林",
    "Sentry": "哨卫",
    "Hexaghost": "六角鬼",
    "SlimeBoss": "史莱姆老大",
    "TheGuardian": "守护者",
    "GremlinFat": "胖地精",
    "GremlinWizard": "地精巫师",
    "FungiBeast": "真菌兽",
    "Champ": "冠军",
    "Collector": "收藏家",
    "Automaton": "铜制自动机",
    "AwakenedOne": "觉醒者",
    "TimeEater": "时间吞噬者",
    "DonuAndDeca": "多努和德卡",
    "Chosen": "被选中者",
    "SphericGuardian": "球形守护者",
    "ShellParasite": "壳寄生虫",
    "SnakePlant": "蛇草",
    "Snecko": "蛇眼怪",
    "Centurion": "百夫长",
    "Healer": "治疗师",
    "Darkling": "暗黑精灵",
    "OrbWalker": "球体行者",
    "Transient": "短暂者",
    "Maw": "巨颚",
    "WrithingMass": "蠕动之块",
    "GiantHead": "巨型头颅",
    "Nemesis": "复仇女神",
    "Reptomancer": "蜥蜴法师",
    "Byrd": "伯德",
    "Slime": "史莱姆",
}


def translate_monster(m_id: str) -> str:
    """Translate monster ID to Chinese name."""
    return MONSTER_NAME_MAP.get(m_id, m_id)


CARD_NAME_MAP = {
    "Strike": "打击",
    "Defend": "防御",
    "Bash": "重击",
    "Cleave": "顺斩",
    "IronWave": "铁斩波",
    "BodySlam": "身体撞击",
    "Clash": "冲突",
    "Clothesline": "晾衣绳",
    "Headbutt": "头槌",
    "HeavyBlade": "重刃",
    "PommelStrike": "柄击",
    "ShrugItOff": "甩开",
    "SwordBoomerang": "剑回旋镖",
    "Thunderclap": "雷鸣",
    "TwinStrike": "双击",
    "WildStrike": "狂野打击",
    "Flex": "活动肌肉",
    "Havoc": "浩劫",
    "TrueGrit": "真材实料",
    "Warcry": "战吼",
    "Armaments": "武装",
    "Anger": "愤怒",
    "Inflame": "点燃",
    "DemonForm": "恶魔形态",
    "Impervious": "不朽",
    "LimitBreak": "限界突破",
    "Offering": "献祭",
    "FlameBarrier": "火焰屏障",
    "Disarm": "缴械",
    "Bloodletting": "流血",
    "Carnage": "大屠杀",
    "Combust": "燃烧",
    "Metallicize": "金属化",
    "DarkEmbrace": "黑暗拥抱",
    "Evolve": "进化",
    "FeelNoPain": "无痛",
    "FireBreathing": "火焰吐息",
    "GhostlyArmor": "幽灵护甲",
    "Rupture": "破裂",
    "Berserk": "狂暴",
    "Barricade": "壁垒",
    "Blur": "模糊",
    "Uppercut": "上勾拳",
    "SpotWeakness": "发现弱点",
    "Sentinel": "哨兵",
    "Whirlwind": "旋风",
    "Pummel": "猛击",
    "RecklessCharge": "鲁莽冲撞",
    "Rage": "狂怒",
}


def translate_card(card_id: str) -> str:
    """Translate card ID to Chinese name."""
    base_id = card_id.replace("_R", "").replace("_U", "").replace("_B", "")
    is_upgraded = base_id.endswith("+")
    actual_id = base_id[:-1] if is_upgraded else base_id
    name = CARD_NAME_MAP.get(actual_id, actual_id)
    if is_upgraded:
        name += "+"
    return name


@dataclass
class CombatEvent:
    timestamp: int
    event_type: str
    details: dict[str, Any]


@dataclass
class CombatLog:
    """Detailed combat log for debugging."""
    floor: int = 0
    encounter: str = ""
    events: list[CombatEvent] = field(default_factory=list)
    turn_count: int = 0
    player_start_hp: int = 0
    player_end_hp: int = 0

    def add_event(self, event_type: str, **details) -> None:
        self.events.append(CombatEvent(
            timestamp=len(self.events),
            event_type=event_type,
            details=details
        ))

    def add_turn_start(self, turn: int, energy: int, player_hp: int, player_block: int) -> None:
        self.add_event("TURN_START", turn=turn, energy=energy, player_hp=player_hp, player_block=player_block)

    def add_turn_end(self, turn: int) -> None:
        self.add_event("TURN_END", turn=turn)

    def add_card_played(self, card_name: str, card_idx: int, target_idx: int | None, energy_cost: int, success: bool) -> None:
        self.add_event("CARD_PLAYED", card_name=card_name, card_idx=card_idx, target_idx=target_idx, energy_cost=energy_cost, success=success)

    def add_damage_dealt(self, source: str, target_idx: int, target_name: str, damage: int, blocked: int, effective_damage: int) -> None:
        self.add_event("DAMAGE_DEALT", source=source, target_idx=target_idx, target_name=target_name, damage=damage, blocked=blocked, effective_damage=effective_damage)

    def add_block_gained(self, source: str, amount: int, total_block: int) -> None:
        self.add_event("BLOCK_GAINED", source=source, amount=amount, total_block=total_block)

    def add_power_applied(self, power_name: str, target: str, target_idx: int | None, amount: int, duration: int | None) -> None:
        self.add_event("POWER_APPLIED", power_name=power_name, target=target, target_idx=target_idx, amount=amount, duration=duration)

    def add_power_removed(self, power_name: str, target: str, target_idx: int | None) -> None:
        self.add_event("POWER_REMOVED", power_name=power_name, target=target, target_idx=target_idx)

    def add_monster_intent(self, monster_idx: int, monster_name: str, intent_type: str, damage: int | None, other: str | None) -> None:
        self.add_event("MONSTER_INTENT", monster_idx=monster_idx, monster_name=monster_name, intent_type=intent_type, damage=damage, other=other)

    def add_monster_action(self, monster_idx: int, monster_name: str, action: str, details: str) -> None:
        self.add_event("MONSTER_ACTION", monster_idx=monster_idx, monster_name=monster_name, action=action, details=details)

    def add_relic_triggered(self, relic_name: str, trigger_type: str, effect: str) -> None:
        self.add_event("RELIC_TRIGGERED", relic_name=relic_name, trigger_type=trigger_type, effect=effect)

    def add_hp_change(self, target: str, target_idx: int | None, old_hp: int, new_hp: int, change: int) -> None:
        self.add_event("HP_CHANGE", target=target, target_idx=target_idx, old_hp=old_hp, new_hp=new_hp, change=change)

    def add_combat_start(self, monsters: list[tuple[int, str, int]]) -> None:
        translated = [f"{idx}:{translate_monster(name)}:{hp}" for idx, name, hp in monsters]
        self.add_event("COMBAT_START", monsters=translated)

    def add_combat_end(self, victory: bool, turns: int, player_hp: int) -> None:
        self.add_event("COMBAT_END", victory=victory, turns=turns, player_hp=player_hp)

    def format_summary(self) -> str:
        lines = []
        lines.append("=" * 70)
        lines.append(f"战斗日志: Floor {self.floor} - {translate_monster(self.encounter)}")
        lines.append("=" * 70)

        lines.append(f"\n【战斗信息】")
        lines.append(f"  回合数: {self.turn_count}")
        lines.append(f"  玩家起始HP: {self.player_start_hp}")
        lines.append(f"  玩家结束HP: {self.player_end_hp}")

        lines.append(f"\n【事件列表】({len(self.events)} 个事件)")
        lines.append("-" * 70)

        for event in self.events:
            lines.append(self._format_event(event))

        lines.append("=" * 70)
        return "\n".join(lines)

    def _format_event(self, event: CombatEvent) -> str:
        t = event.event_type
        d = event.details

        if t == "COMBAT_START":
            monsters = d.get("monsters", [])
            return f"[{event.timestamp:03d}] ⚔️ 战斗开始: {', '.join(monsters)}"

        elif t == "TURN_START":
            turn = d.get('turn', '?')
            return f"[{event.timestamp:03d}] 🔄 回合开始: T{turn} | 能量:{d['energy']} | HP:{d['player_hp']} | 护甲:{d['player_block']}"

        elif t == "TURN_END":
            return f"[{event.timestamp:03d}] ⏭️  回合结束: T{d['turn']}"

        elif t == "CARD_PLAYED":
            success_str = "成功" if d['success'] else "失败"
            target_str = f"→ 目标{d['target_idx']}" if d['target_idx'] is not None else "→ 无目标"
            card_name = translate_card(d['card_name'])
            return f"[{event.timestamp:03d}] 🃏 出牌: {card_name} [{d['card_idx']}] {target_str} (能量:{d['energy_cost']}) [{success_str}]"

        elif t == "DAMAGE_DEALT":
            blocked_str = f" (被格挡:{d['blocked']})" if d['blocked'] > 0 else ""
            return f"[{event.timestamp:03d}] ⚔️  伤害: {d['source']} → {d['target_name']}[{d['target_idx']}] 伤害:{d['damage']}{blocked_str} → 有效伤害:{d['effective_damage']}"

        elif t == "BLOCK_GAINED":
            return f"[{event.timestamp:03d}] 🛡️  护甲: {d['source']} 获得 {d['amount']} 护甲 (总计:{d['total_block']})"

        elif t == "POWER_APPLIED":
            target_str = f"{d['target']}[{d['target_idx']}]" if d['target_idx'] is not None else d['target']
            duration_str = f" 持续{d['duration']}回合" if d['duration'] else ""
            return f"[{event.timestamp:03d}] ✨ 状态: {d['power_name']} → {target_str} ×{d['amount']}{duration_str}"

        elif t == "POWER_REMOVED":
            target_str = f"{d['target']}[{d['target_idx']}]" if d['target_idx'] is not None else d['target']
            return f"[{event.timestamp:03d}] ❌ 状态移除: {d['power_name']} 从 {target_str}"

        elif t == "MONSTER_INTENT":
            if d['damage'] is not None:
                intent_str = f"准备攻击(伤害:{d['damage']})"
            elif d['other']:
                intent_str = f"准备{d['other']}"
            else:
                intent_str = "准备防御"
            monster_name = translate_monster(d['monster_name'])
            return f"[{event.timestamp:03d}] 👁️  意图: {monster_name}[{d['monster_idx']}] {intent_str}"

        elif t == "MONSTER_ACTION":
            monster_name = translate_monster(d['monster_name'])
            return f"[{event.timestamp:03d}] 👹 怪物行动: {monster_name}[{d['monster_idx']}] {d['action']} - {d['details']}"

        elif t == "RELIC_TRIGGERED":
            return f"[{event.timestamp:03d}] 🏆 遗物触发: {d['relic_name']} ({d['trigger_type']}) - {d['effect']}"

        elif t == "HP_CHANGE":
            change_str = f"+{d['change']}" if d['change'] > 0 else str(d['change'])
            target_str = f"{d['target']}[{d['target_idx']}]" if d['target_idx'] is not None else d['target']
            return f"[{event.timestamp:03d}] 💔 HP变化: {target_str} {d['old_hp']} → {d['new_hp']} ({change_str})"

        elif t == "COMBAT_END":
            result_str = "胜利 ✓" if d['victory'] else "失败 ✗"
            return f"[{event.timestamp:03d}] 🏁 战斗结束: {result_str} | 回合:{d['turns']} | 剩余HP:{d['player_hp']}"

        else:
            return f"[{event.timestamp:03d}] {t}: {d}"


class CombatLogger:
    """Logger that attaches to CombatEngine for detailed combat recording."""

    def __init__(self, floor: int = 0, encounter: str = ""):
        self.log = CombatLog(floor=floor, encounter=encounter)
        self._enabled = True

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def is_enabled(self) -> bool:
        return self._enabled

    def get_log(self) -> CombatLog:
        return self.log

    def log_combat_start(self, combat) -> None:
        if not self._enabled:
            return
        monsters = [(i, m.id, m.hp) for i, m in enumerate(combat.state.monsters)]
        self.log.add_combat_start(monsters)
        self.log.player_start_hp = combat.state.player.hp

    def log_turn_start(self, combat, turn: int) -> None:
        if not self._enabled:
            return
        self.log.add_turn_start(
            turn=turn,
            energy=combat.state.player.energy,
            player_hp=combat.state.player.hp,
            player_block=combat.state.player.block
        )

    def log_turn_end(self, turn: int) -> None:
        if not self._enabled:
            return
        self.log.add_turn_end(turn)

    def log_card_played(self, card_name: str, card_idx: int, target_idx: int | None, energy_cost: int, success: bool) -> None:
        if not self._enabled:
            return
        self.log.add_card_played(card_name, card_idx, target_idx, energy_cost, success)

    def log_damage_dealt(self, source: str, target_idx: int, target_name: str, damage: int, blocked: int) -> None:
        if not self._enabled:
            return
        self.log.add_damage_dealt(source, target_idx, target_name, damage, blocked, damage - blocked)

    def log_block_gained(self, source: str, amount: int, total_block: int) -> None:
        if not self._enabled:
            return
        self.log.add_block_gained(source, amount, total_block)

    def log_power_applied(self, power_name: str, target: str, target_idx: int | None, amount: int, duration: int | None = None) -> None:
        if not self._enabled:
            return
        self.log.add_power_applied(power_name, target, target_idx, amount, duration)

    def log_power_removed(self, power_name: str, target: str, target_idx: int | None = None) -> None:
        if not self._enabled:
            return
        self.log.add_power_removed(power_name, target, target_idx)

    def log_monster_intent(self, monster_idx: int, monster_name: str, intent_type: str, damage: int | None = None, other: str | None = None) -> None:
        if not self._enabled:
            return
        self.log.add_monster_intent(monster_idx, monster_name, intent_type, damage, other)

    def log_monster_action(self, monster_idx: int, monster_name: str, action: str, details: str) -> None:
        if not self._enabled:
            return
        self.log.add_monster_action(monster_idx, monster_name, action, details)

    def log_relic_triggered(self, relic_name: str, trigger_type: str, effect: str) -> None:
        if not self._enabled:
            return
        self.log.add_relic_triggered(relic_name, trigger_type, effect)

    def log_hp_change(self, target: str, target_idx: int | None, old_hp: int, new_hp: int) -> None:
        if not self._enabled:
            return
        self.log.add_hp_change(target, target_idx, old_hp, new_hp, new_hp - old_hp)

    def log_combat_end(self, victory: bool, turns: int, player_hp: int) -> None:
        if not self._enabled:
            return
        self.log.add_combat_end(victory, turns, player_hp)
        self.log.player_end_hp = player_hp
        self.log.turn_count = turns
