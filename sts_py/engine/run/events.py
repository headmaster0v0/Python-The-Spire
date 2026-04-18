"""Event system for Slay The Spire.

This module contains both the legacy local event tables and the canonical
Java-aligned event registry used by runtime generation, audit, and harness
surfaces.
"""
from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Callable

from sts_py.engine.content.relics import RelicSource
from sts_py.engine.run.official_event_strings import apply_official_event_strings, get_official_event_strings

if TYPE_CHECKING:
    from sts_py.engine.run.run_engine import RunEngine


def _can_remove_card(state, card_id: str) -> bool:
    """Check if a card can be removed from deck (no CANNOT_REMOVE_FROM_DECK effect)."""
    from sts_py.engine.content.cards_min import IRONCLAD_CURSE_DEFS

    base_id = _event_card_base_id(card_id)
    if base_id in IRONCLAD_CURSE_DEFS:
        card_def = IRONCLAD_CURSE_DEFS[base_id]
        if card_def.curse_effect_type.value == "cannot_remove_from_deck":
            return False
    return True


def _apply_parasite_penalty(state, card_id: str) -> None:
    """Apply Parasite curse penalty when removed from deck."""
    from sts_py.engine.content.cards_min import IRONCLAD_CURSE_DEFS

    base_id = _event_card_base_id(card_id)
    if base_id in IRONCLAD_CURSE_DEFS:
        card_def = IRONCLAD_CURSE_DEFS[base_id]
        if card_def.curse_effect_type.value == "if_removed_lose_max_hp":
            penalty = card_def.curse_effect_value
            state.player_max_hp -= penalty
            if state.player_hp > state.player_max_hp:
                state.player_hp = state.player_max_hp


def _event_card_base_id(card_id: str) -> str:
    from sts_py.engine.content.card_instance import get_runtime_card_base_id

    return get_runtime_card_base_id(card_id)


def _is_curse_card(card_id: str) -> bool:
    """Check if a card is a curse card."""
    from sts_py.engine.content.cards_min import IRONCLAD_CURSE_DEFS
    return _event_card_base_id(card_id) in IRONCLAD_CURSE_DEFS


def _remove_starter_strikes_from_deck(state) -> list[str]:
    starter_strike_ids = {"Strike", "Strike_B", "Strike_P"}
    removed: list[str] = []
    remaining: list[str] = []
    for deck_card in list(getattr(state, "deck", [])):
        base_id = _event_card_base_id(str(deck_card))
        if base_id in starter_strike_ids:
            removed.append(deck_card)
            continue
        remaining.append(deck_card)
    state.deck = remaining
    return removed


def _get_transformed_card(old_card_id: str, rng: Any) -> str:
    """Get a random transformed card (same cost, different card)."""
    from sts_py.engine.content.cards_min import ALL_CARD_DEFS

    base_id = _event_card_base_id(old_card_id)
    old_cost = 0
    if base_id in ALL_CARD_DEFS:
        old_cost = ALL_CARD_DEFS[base_id].cost

    eligible_cards = [
        cid for cid, card_def in ALL_CARD_DEFS.items()
        if card_def.cost == old_cost and cid != base_id
    ]

    if eligible_cards:
        idx = rng.random_int(len(eligible_cards) - 1) if rng else 0
        return eligible_cards[idx]
    return old_card_id


class EventEffectType(str, Enum):
    GAIN_GOLD = "gain_gold"
    LOSE_GOLD = "lose_gold"
    GAIN_HP = "gain_hp"
    LOSE_HP = "lose_hp"
    GAIN_MAX_HP = "gain_max_hp"
    LOSE_MAX_HP = "lose_max_hp"
    GAIN_CARD = "gain_card"
    REMOVE_CARD = "remove_card"
    UPGRADE_CARD = "upgrade_card"
    GAIN_RELIC = "gain_relic"
    LOSE_RELIC = "lose_relic"
    TRANSFORM_CARD = "transform_card"
    GAIN_RANDOM_RELIC = "gain_random_relic"
    GAIN_STRENGTH = "gain_strength"
    GAIN_DEXTERITY = "gain_dexterity"
    GAIN_WEAK = "gain_weak"
    GAIN_VULNERABLE = "gain_vulnerable"
    GAIN_POISON = "gain_poison"
    GAIN_BLOCK = "gain_block"
    GAIN_ENERGY = "gain_energy"
    LOSE_ENERGY = "lose_energy"
    LOSE_STRENGTH = "lose_strength"
    LOSE_DEXTERITY = "lose_dexterity"
    TRANSFORM_RANDOM_CARD = "transform_random_card"
    REMOVE_RANDOM_CURSE = "remove_random_curse"
    CHOOSE_CARD_TO_REMOVE = "choose_card_to_remove"
    CHOOSE_CARD_TO_TRANSFORM = "choose_card_to_transform"
    CHOOSE_CARD_TO_UPGRADE = "choose_card_to_upgrade"
    OBTAIN_POTION = "obtain_potion"
    GAIN_MAX_HP_PERCENT = "gain_max_hp_percent"
    LOSE_HP_PERCENT = "lose_hp_percent"
    LOSE_MAX_HP_PERCENT = "lose_max_hp_percent"


@dataclass
class EventEffect:
    effect_type: EventEffectType
    amount: int = 0
    card_id: str | None = None
    relic_id: str | None = None


@dataclass
class EventChoice:
    description: str
    description_cn: str = ""
    effects: list[EventEffect] = field(default_factory=list)
    enabled: bool = True
    disabled_reason: str = ""
    disabled_reason_cn: str = ""
    cost: int = 0
    encounter_chance: int = 0
    search_level: int = 0
    search_rewards: list[str] | None = None
    search_enemies: list[str] | None = None
    requires_card_removal: bool = False
    requires_card_transform: bool = False
    requires_card_upgrade: bool = False
    requires_attack_card: bool = False
    gold_range: list[int] | None = None
    trap_triggered: bool = False
    lose_gold_range: list[int] | None = None
    trigger_combat: bool = False
    combat_enemies: list[str] | None = None
    combat_reward: str | None = None
    base_damage: int = 0
    base_chance: int = 0
    requires_upgrade_any: bool = False
    upgrades_count: int = 0
    lose_hp_percent: int = 0
    gain_gold: int = 0
    trade_faces: bool = False
    ascension_gold_15: int = 0
    gain_card_count_ascension_15: int = 0
    remove_starter_strikes: bool = False

    def _ascension_level(self, engine: "RunEngine") -> int:
        return int(getattr(engine.state, "ascension_level", getattr(engine.state, "ascension", 0)) or 0)

    def apply(self, engine: "RunEngine") -> dict[str, Any]:
        result = {"effects_applied": [], "cost_paid": 0}
        if self.cost > 0:
            actual_cost = min(self.cost, engine.state.player_gold)
            engine.state.player_gold -= actual_cost
            result["cost_paid"] = actual_cost
            result["effects_applied"].append({"type": "lose_gold", "amount": actual_cost})

        if self.lose_hp_percent > 0:
            damage = max(1, engine.state.player_max_hp * self.lose_hp_percent // 100)
            actual_loss = min(damage, engine.state.player_hp)
            engine.state.player_hp -= actual_loss
            result["effects_applied"].append({"type": "lose_hp_percent", "percent": self.lose_hp_percent, "actual_damage": actual_loss})

        if self.gain_gold > 0:
            engine.state.player_gold += self.gain_gold
            result["effects_applied"].append({"type": "gain_gold", "amount": self.gain_gold})

        if self.ascension_gold_15 > 0:
            ascension = self._ascension_level(engine)
            gold = self.ascension_gold_15 if ascension >= 15 else self.gain_gold
            engine.state.player_gold += gold
            result["effects_applied"].append({"type": "gain_gold", "amount": gold})

        if self.trade_faces:
            mask_result = self._apply_trade_faces(engine)
            result["effects_applied"].append(mask_result)

        if self.trigger_combat:
            combat_result = self._apply_combat_trigger(engine)
            result["effects_applied"].append(combat_result)

        if self.search_level > 0:
            search_result = self._apply_search(engine)
            result["effects_applied"].append(search_result)

        if self.remove_starter_strikes:
            removed = _remove_starter_strikes_from_deck(engine.state)
            result["effects_applied"].append({"type": "remove_starter_strikes", "cards": removed})

        ascension = self._ascension_level(engine)
        gain_card_amount_override = self.gain_card_count_ascension_15 if ascension >= 15 else 0
        for effect in self.effects:
            effect_result = self._apply_effect(effect, engine, gain_card_amount_override=gain_card_amount_override)
            result["effects_applied"].append(effect_result)
        return result

    def _apply_combat_trigger(self, engine: "RunEngine") -> dict[str, Any]:
        if not self.combat_enemies:
            return {"type": "trigger_combat", "status": "no_enemies"}

        if not hasattr(engine.state, 'pending_combat'):
            engine.state.pending_combat = {}
        engine.state.pending_combat = {
            "enemies": self.combat_enemies.copy(),
            "is_elite": True,
            "reward": self.combat_reward,
        }
        return {"type": "trigger_combat", "enemies": self.combat_enemies, "is_elite": True, "reward": self.combat_reward}

    def _apply_trade_faces(self, engine: "RunEngine") -> dict[str, Any]:
        from sts_py.engine.run.events import EventEffectType
        mask_ids = ["CultistMask", "FaceOfCleric", "GremlinMask", "NlothsMask", "SsserpentHead"]
        current_masks = [r for r in getattr(engine.state, 'relics', []) if r in mask_ids]
        available_masks = [m for m in mask_ids if m not in current_masks]

        if not available_masks:
            available_masks = ["Circlet"]

        rng = getattr(engine.state, 'rng', None)
        event_rng = getattr(rng, "event_rng", None)
        if event_rng is not None:
            mask = available_masks[event_rng.random_int(len(available_masks) - 1)]
        else:
            mask = available_masks[0]

        engine._acquire_relic(mask, source=RelicSource.EVENT, record_pending=True)

        return {"type": "trade_faces", "relic_obtained": mask}

    def _apply_search(self, engine: "RunEngine") -> dict[str, Any]:
        from sts_py.engine.run.events import EventEffectType
        search_level = self.search_level
        encounter_chance = self.encounter_chance
        ascension = self._ascension_level(engine)

        if ascension >= 15:
            encounter_chance = encounter_chance + 10

        rng = getattr(engine.state, 'rng', None)
        roll = rng.random_int(0, 99) if rng else 50

        if roll < encounter_chance:
            if not hasattr(engine.state, 'search_enemies'):
                engine.state.search_enemies = []

            if not hasattr(engine.state, 'dead_adventurer_enemy'):
                enemy_roll = rng.random_int(0, 2) if rng else 0
                if enemy_roll == 0:
                    engine.state.dead_adventurer_enemy = ["Sentry", "Sentry", "Sentry"]
                elif enemy_roll == 1:
                    engine.state.dead_adventurer_enemy = ["GremlinNob"]
                else:
                    engine.state.dead_adventurer_enemy = ["Lagavulin Event"]

            enemies = engine.state.dead_adventurer_enemy
            engine.state.search_enemies = enemies
            engine.state.pending_combat = {
                "enemies": enemies,
                "is_elite": True,
                "reward": None,
            }
            return {"type": "search", "result": "combat", "enemies": enemies}

        if self.search_rewards:
            reward = self.search_rewards.pop(0) if self.search_rewards else "NOTHING"
        else:
            reward_roll = rng.random_int(0, 2) if rng else 1
            reward = ["GOLD", "NOTHING", "RELIC"][reward_roll]

        if reward == "GOLD":
            gold_amount = 30
            engine.state.player_gold += gold_amount
            return {"type": "search", "result": "gold", "amount": gold_amount}
        elif reward == "RELIC":
            if not hasattr(engine.state, 'pending_relic'):
                engine.state.pending_relic = True
            return {"type": "search", "result": "relic"}
        else:
            return {"type": "search", "result": "nothing"}

    def _apply_effect(
        self,
        effect: EventEffect,
        engine: "RunEngine",
        *,
        gain_card_amount_override: int = 0,
    ) -> dict[str, Any]:
        state = engine.state

        if effect.effect_type == EventEffectType.GAIN_GOLD:
            state.player_gold += effect.amount
            return {"type": "gain_gold", "amount": effect.amount}

        elif effect.effect_type == EventEffectType.LOSE_GOLD:
            actual_loss = min(effect.amount, state.player_gold)
            state.player_gold -= actual_loss
            return {"type": "lose_gold", "amount": actual_loss}

        elif effect.effect_type == EventEffectType.GAIN_HP:
            actual_gain = min(effect.amount, state.player_max_hp - state.player_hp)
            state.player_hp += actual_gain
            return {"type": "gain_hp", "amount": actual_gain}

        elif effect.effect_type == EventEffectType.LOSE_HP:
            actual_loss = min(effect.amount, state.player_hp)
            state.player_hp -= actual_loss
            return {"type": "lose_hp", "amount": actual_loss}

        elif effect.effect_type == EventEffectType.GAIN_MAX_HP:
            state.player_max_hp += effect.amount
            state.player_hp += effect.amount
            return {"type": "gain_max_hp", "amount": effect.amount}

        elif effect.effect_type == EventEffectType.LOSE_MAX_HP:
            actual_loss = min(effect.amount, state.player_max_hp - 1)
            state.player_max_hp -= actual_loss
            if state.player_hp > state.player_max_hp:
                state.player_hp = state.player_max_hp
            return {"type": "lose_max_hp", "amount": actual_loss}

        elif effect.effect_type == EventEffectType.GAIN_MAX_HP_PERCENT:
            heal_amount = int(state.player_max_hp * effect.amount / 100)
            actual_gain = min(heal_amount, state.player_max_hp - state.player_hp)
            state.player_hp += actual_gain
            return {"type": "gain_max_hp_percent", "amount": effect.amount, "actual_heal": actual_gain}

        elif effect.effect_type == EventEffectType.LOSE_MAX_HP_PERCENT:
            lose_amount = int(state.player_max_hp * effect.amount / 100)
            state.player_max_hp -= lose_amount
            if state.player_hp > state.player_max_hp:
                state.player_hp = state.player_max_hp
            return {"type": "lose_max_hp_percent", "amount": effect.amount}

        elif effect.effect_type == EventEffectType.LOSE_HP_PERCENT:
            lose_amount = int(state.player_max_hp * effect.amount / 100)
            actual_loss = min(lose_amount, state.player_hp)
            state.player_hp -= actual_loss
            return {"type": "lose_hp_percent", "amount": effect.amount, "actual_loss": actual_loss}

        elif effect.effect_type == EventEffectType.GAIN_CARD:
            if effect.card_id:
                count = gain_card_amount_override if gain_card_amount_override > 0 else max(1, int(effect.amount or 0))
                for _ in range(count):
                    state.deck.append(effect.card_id)
                return {"type": "gain_card", "card_id": effect.card_id, "count": count}

        elif effect.effect_type == EventEffectType.REMOVE_CARD:
            if effect.card_id and effect.card_id in state.deck:
                _apply_parasite_penalty(state, effect.card_id)
                state.deck.remove(effect.card_id)
                return {"type": "remove_card", "card_id": effect.card_id}

        elif effect.effect_type == EventEffectType.TRANSFORM_CARD:
            if effect.card_id and effect.card_id in state.deck:
                _apply_parasite_penalty(state, effect.card_id)
                state.deck.remove(effect.card_id)
                return {"type": "transform_card", "card_id": effect.card_id}

        elif effect.effect_type == EventEffectType.GAIN_RELIC:
            if effect.relic_id:
                engine._acquire_relic(effect.relic_id, source=RelicSource.EVENT, record_pending=True)
                return {"type": "gain_relic", "relic_id": effect.relic_id}

        elif effect.effect_type == EventEffectType.GAIN_RANDOM_RELIC:
            from sts_py.engine.content.relics import get_random_relic_by_tier, roll_relic_rarity

            rng_state = getattr(state, "rng", None)
            rng = getattr(rng_state, "relic_rng", rng_state)
            rarity = roll_relic_rarity(rng)
            relic_id = get_random_relic_by_tier(rarity.value, rng)
            if relic_id:
                engine._acquire_relic(relic_id, source=RelicSource.EVENT, record_pending=True)
                return {"type": "gain_random_relic", "relic_id": relic_id}
            return {"type": "gain_random_relic", "applied": False, "reason": "no_relic_available"}

        elif effect.effect_type == EventEffectType.GAIN_STRENGTH:
            state.player_strength = getattr(state, 'player_strength', 0) + effect.amount
            return {"type": "gain_strength", "amount": effect.amount}

        elif effect.effect_type == EventEffectType.GAIN_DEXTERITY:
            state.player_dexterity = getattr(state, 'player_dexterity', 0) + effect.amount
            return {"type": "gain_dexterity", "amount": effect.amount}

        elif effect.effect_type == EventEffectType.GAIN_WEAK:
            return {"type": "gain_weak", "amount": effect.amount}

        elif effect.effect_type == EventEffectType.GAIN_VULNERABLE:
            return {"type": "gain_vulnerable", "amount": effect.amount}

        elif effect.effect_type == EventEffectType.GAIN_POISON:
            return {"type": "gain_poison", "amount": effect.amount}

        elif effect.effect_type == EventEffectType.GAIN_BLOCK:
            state.player_block = getattr(state, 'player_block', 0) + effect.amount
            return {"type": "gain_block", "amount": effect.amount}

        elif effect.effect_type == EventEffectType.GAIN_ENERGY:
            state.player_energy = getattr(state, 'player_energy', 0) + effect.amount
            return {"type": "gain_energy", "amount": effect.amount}

        elif effect.effect_type == EventEffectType.LOSE_ENERGY:
            state.player_energy = max(0, getattr(state, 'player_energy', 0) - effect.amount)
            return {"type": "lose_energy", "amount": effect.amount}

        elif effect.effect_type == EventEffectType.LOSE_STRENGTH:
            state.player_strength = max(0, getattr(state, 'player_strength', 0) - effect.amount)
            return {"type": "lose_strength", "amount": effect.amount}

        elif effect.effect_type == EventEffectType.LOSE_DEXTERITY:
            state.player_dexterity = max(0, getattr(state, 'player_dexterity', 0) - effect.amount)
            return {"type": "lose_dexterity", "amount": effect.amount}

        elif effect.effect_type == EventEffectType.TRANSFORM_RANDOM_CARD:
            if state.deck:
                rng = getattr(state, 'rng', None)
                idx = rng.random_int(len(state.deck) - 1) if rng else 0
                old_card = state.deck[idx]
                new_card = _get_transformed_card(old_card, rng)
                state.deck[idx] = new_card
                return {"type": "transform_random_card", "old_card": old_card, "new_card": new_card}
            return {"type": "transform_random_card", "applied": False, "reason": "no_cards"}

        elif effect.effect_type == EventEffectType.REMOVE_RANDOM_CURSE:
            curse_cards = [c for c in state.deck if _is_curse_card(c)]
            if curse_cards:
                rng = getattr(state, 'rng', None)
                idx = rng.random_int(len(curse_cards) - 1) if rng else 0
                curse_to_remove = curse_cards[idx]
                state.deck.remove(curse_to_remove)
                return {"type": "remove_random_curse", "card_removed": curse_to_remove}
            return {"type": "remove_random_curse", "applied": False, "reason": "no_curses"}

        elif effect.effect_type == EventEffectType.OBTAIN_POTION:
            if not hasattr(state, 'potions'):
                state.potions = []
            if effect.card_id:
                state.potions.append(effect.card_id)
                return {"type": "obtain_potion", "potion_id": effect.card_id}
            return {"type": "obtain_potion", "applied": False, "reason": "no_potion_id"}

        return {"type": effect.effect_type.value, "applied": False}


@dataclass
class Event:
    id: str
    name: str
    name_cn: str = ""
    event_key: str = ""
    pool_bucket: str = "act_event"
    gating_flags: list[str] = field(default_factory=list)
    description: str = ""
    description_cn: str = ""
    description_variants: list[str] = field(default_factory=list)
    description_cn_variants: list[str] = field(default_factory=list)
    source_descriptions: list[str] = field(default_factory=list)
    source_descriptions_cn: list[str] = field(default_factory=list)
    source_options: list[str] = field(default_factory=list)
    source_options_cn: list[str] = field(default_factory=list)
    choices: list[EventChoice] = field(default_factory=list)
    act: int = 1
    min_floor: int = 0

    @property
    def event_id(self) -> str:
        return self.id

    def get_choice(self, index: int) -> EventChoice | None:
        if 0 <= index < len(self.choices):
            return self.choices[index]
        return None

    def select_variant(self, rng: Any) -> "Event":
        if self.description_variants:
            idx = rng.random_int(len(self.description_variants) - 1)
            self.description = self.description_variants[idx]
            self.description_cn = self.description_cn_variants[idx]
        return self

    def clone(self) -> "Event":
        return deepcopy(self)


ACT1_EVENTS: dict[str, Event] = {
    "Big Fish": Event(
        id="Big Fish",
        name="Big Fish",
        name_cn="大鱼",
        description="When you walk through a corridor, you see a banana, a donut, and a box floating in the air. They are tied to strings hanging from holes in the ceiling. You hear giggling from above.",
        description_cn="当你走过一条长廊时，你看见空中漂浮着一根香蕉，一个甜甜圈，和一个盒子。它们都是被用绳子系着，从天花板上的几个洞里悬挂下来的。你在接近这几样东西时，上方似乎传来一阵咯咯的笑声。",
        choices=[
            EventChoice(
                description="[Banana] Heal 33% of max HP.",
                description_cn="[香蕉] 回复最大生命值的1/3。",
                effects=[
                    EventEffect(EventEffectType.GAIN_MAX_HP_PERCENT, amount=33),
                ]
            ),
            EventChoice(
                description="[Donut] Gain 5 Max HP.",
                description_cn="[甜甜圈] 最大生命值+5。",
                effects=[
                    EventEffect(EventEffectType.GAIN_MAX_HP, amount=5),
                ]
            ),
            EventChoice(
                description="[Box] Gain a random relic. Get cursed with Regret.",
                description_cn="[盒子] 获得一件遗物。被诅咒——诅咒牌「悔恨」。",
                effects=[
                    EventEffect(EventEffectType.GAIN_RANDOM_RELIC),
                    EventEffect(EventEffectType.GAIN_CARD, card_id="Regret"),
                ]
            ),
        ],
        act=1,
    ),
    "The Cleric": Event(
        id="The Cleric",
        name="The Cleric",
        name_cn="牧师",
        description="A strange blue humanoid with a golden helmet walks up to you with a big smile. 'Hello friend! I'm the Cleric! Do you want to try my services?!' the creature shouts.",
        description_cn='一个戴着金头盔（？）的奇怪蓝色人形生物脸上带着大大的微笑走到了你面前。"你好啊朋友！我是牧师！你想不想试试我的服务呐？！"那个生物大声喊叫起来。',
        choices=[
            EventChoice(
                description="[Heal] 35 Gold: Heal 25% HP. (Requires 35 Gold)",
                description_cn="[治疗] 35金币：回复25%生命。（需要：35金币）",
                effects=[
                    EventEffect(EventEffectType.GAIN_MAX_HP_PERCENT, amount=25),
                ],
                cost=35,
            ),
            EventChoice(
                description="[Purify] 50 Gold: Remove a card from your deck. (Requires 50 Gold)",
                description_cn="[净化] 50金币：从你的牌组中移除一张牌。（需要：50金币）",
                effects=[
                    EventEffect(EventEffectType.CHOOSE_CARD_TO_REMOVE),
                ],
                cost=50,
            ),
            EventChoice(
                description="[Leave] You don't trust this 'Cleric' and walk away.",
                description_cn='[离开] 你完全不相信这个"牧师"，就这样走开了。',
                effects=[]
            ),
        ],
        act=1,
    ),
    "Dead Adventurer": Event(
        id="Dead Adventurer",
        name="Dead Adventurer",
        name_cn="冒险者尸体",
        description_variants=[
            "You find a dead adventurer on the ground. His pants have been stolen! He appears to have been burned by flames - the Sentry must have done this.",
            "You find a dead adventurer on the ground. His pants have been stolen! He appears to have been gored by a horned creature - Gremlin Nob must have done this.",
            "You find a dead adventurer on the ground. His pants have been stolen! His insides seem to have been shredded by huge claws - Leg Sweeper must have done this.",
        ],
        description_cn_variants=[
            "你发现地上有一具冒险者尸体。他的裤子都被偷了！他的护甲和脸似乎被火焰灼烧过——一定是哨卫干的。",
            "你发现地上有一具冒险者尸体。他的裤子都被偷了！看起来他被一个带角的生物戳伤和踩踏过——一定是地精大块头干的。",
            "你发现地上有一具冒险者尸体。他的裤子都被偷了！他的内脏似乎被巨大的爪子撕扯出来并切碎了——一定是乐加维林干的。",
        ],
        description="",
        description_cn="",
        choices=[
            EventChoice(
                description="[Search 1] Search the body. 25% chance to encounter.",
                description_cn="[搜索] 寻找东西。25%：遇见回来的怪物。",
                effects=[],
                encounter_chance=25,
                search_level=1,
            ),
            EventChoice(
                description="[Search 2] Search again. 50% chance to encounter.",
                description_cn="[继续] 寻找东西。50%：遇见回来的怪物。",
                effects=[],
                encounter_chance=50,
                search_level=2,
            ),
            EventChoice(
                description="[Search 3] Search one more time. 75% chance to encounter.",
                description_cn="[继续] 寻找东西。75%：遇见回来的怪物。",
                effects=[],
                encounter_chance=75,
                search_level=3,
            ),
            EventChoice(
                description="[Leave] You leave silently.",
                description_cn="[离开] 你一声不发地离开了。",
                effects=[]
            ),
        ],
        act=1,
        min_floor=7,
    ),
    "Golden Shrine": Event(
        id="Golden Shrine",
        name="Golden Shrine",
        name_cn="金神像",
        description="On a small unremarkable pedestal, you spot a glittering golden idol resting peacefully on top, looking very valuable. The surroundings appear completely free of traps.",
        description_cn="在一个不引人注意的小高台上，你发现了一个闪闪发光的金神像安然放置在上面，看起来非常值钱。周围看起来完全没有什么陷阱的样子。",
        choices=[
            EventChoice(
                description="[Take] Take the golden idol. Trigger a trap!",
                description_cn="[拿走] 得到金神像。触发一个陷阱！",
                effects=[],
                trap_triggered=True,
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 没有比这更明显的陷阱了吧。你决定还是不要去碰高台上的东西了。",
                effects=[]
            ),
        ],
        act=1,
    ),
    "Wing Statuette": Event(
        id="Wing Statuette",
        name="Wing Statuette",
        name_cn="翅膀雕像",
        description="Between boulders of different shapes, you see a finely crafted blue statuette shaped like wings. You can see gold falling from cracks in the statue. Maybe there's more inside...",
        description_cn="在形状不同的巨石之间，你看见一尊做工精细的翅膀形状的蓝色雕像。你可以看见雕像的裂缝中有金币掉出来。或许里面还有更多……",
        choices=[
            EventChoice(
                description="[Pray] Remove a card. Lose 7 HP.",
                description_cn="[祈祷] 从你的牌组中移除一张牌。失去7生命。",
                effects=[
                    EventEffect(EventEffectType.LOSE_HP, amount=7),
                ],
                requires_card_removal=True,
            ),
            EventChoice(
                description="[Destroy] Gain 50-80 gold. Requires: Attack card with damage >= 10.",
                description_cn="[摧毁] 获得50-80金币。需要：卡组里有伤害等于或超过10的攻击牌。",
                effects=[],
                gold_range=[50, 80],
                requires_attack_card=True,
            ),
            EventChoice(
                description="[Leave] This statue makes you uneasy. You decide to leave.",
                description_cn="[离开] 这个雕像让你觉得有点不安。你决定不要去惊扰它，直接离开了。",
                effects=[]
            ),
        ],
        act=1,
    ),
    "World of Goop": Event(
        id="World of Goop",
        name="World of Goop",
        name_cn="黏液世界",
        description="You fall into a puddle, but it's all slime gel! You feel the gel burning you as you desperately try to escape. Your ears, nose, and whole body are soaked. After crawling out, you notice your gold is少了. Looking back, you see not only your dropped money but also gold from other unfortunate adventurers in the puddle.",
        description_cn="你掉进了一个水坑里。可是坑里全是史莱姆黏液！你感觉到这黏液似乎会灼伤你，便拼命想要从坑中脱身。你的耳朵、鼻子和全身都被黏液给浸透了。爬出来后，你发现自己的金币似乎变少了。你回头一看，发现水坑里不但有你掉落的钱，还有不少其他不幸的冒险者们落下的金币。",
        choices=[
            EventChoice(
                description="[Collect] Gain 75 gold. Lose 11 HP.",
                description_cn="[收集金币] 获得75金币。失去11生命。",
                effects=[
                    EventEffect(EventEffectType.GAIN_GOLD, amount=75),
                    EventEffect(EventEffectType.LOSE_HP, amount=11),
                ]
            ),
            EventChoice(
                description="[Leave] Lose 20~50 random gold.",
                description_cn="[放手吧] 失去20~50（随机）金币。",
                effects=[],
                lose_gold_range=[20, 50],
            ),
        ],
        act=1,
    ),
    "Liars Game": Event(
        id="Liars Game",
        name="Liars Game",
        name_cn="蛇",
        description="You enter a room and see a big hole. As you approach it, a giant snake-like creature emerges. 'Hello hello! Who is this? Oh dear, hello adventurer! I'll ask you a simple question. The happiest life is being able to buy anything - rich person life! Do you agree?'",
        description_cn='你走进一间房间，看见地上有一个大洞。当你靠近洞时，一条巨大的蛇形生物从里面钻了出来。"嚯嚯嚯！你好，你好啊！这是谁呀？哎呀呀，你好冒险者，我就问一个简单的问题。最幸福的人生当然就是什么东西都能买得起的土豪生活了！你同意吗？"',
        choices=[
            EventChoice(
                description="[Agree] Gain 175 gold. Get cursed with Doubt.",
                description_cn="[同意] 得到175金币。被诅咒——诅咒牌「疑虑」。",
                effects=[
                    EventEffect(EventEffectType.GAIN_GOLD, amount=175),
                    EventEffect(EventEffectType.GAIN_CARD, card_id="Doubt"),
                ]
            ),
            EventChoice(
                description="[Disagree] The snake looks very disappointed.",
                description_cn="[反对] 蛇非常失望地看着你。",
                effects=[]
            ),
        ],
        act=1,
    ),
    "Living Wall": Event(
        id="Living Wall",
        name="Living Wall",
        name_cn="活墙壁",
        description="You walk into a dead end. As you turn to leave, walls crash down from the ceiling! Three faces appear on the wall: 'Forget what you know, and I'll let you go.' 'Change something, and I'll show you new paths.' 'If you want to pass through me, you must grow.'",
        description_cn='你走进一条死路，正准备要回头时，四周突然有墙壁从天花板上哐地一下砸了下来！三张脸出现在墙壁上："忘记你所知道的，我就让你走。""有所改变，我就让你看见新的道路。""如果你想要从我这里通过，你就必须有所成长。"',
        choices=[
            EventChoice(
                description="[Forget] Remove a card from your deck.",
                description_cn="[遗忘] 移除你牌组中的一张牌。",
                effects=[],
                requires_card_removal=True,
            ),
            EventChoice(
                description="[Change] Transform a card in your deck.",
                description_cn="[改变] 变化你牌组中的一张牌。",
                effects=[],
                requires_card_transform=True,
            ),
            EventChoice(
                description="[Grow] Upgrade a card in your deck. (Requires upgradeable card)",
                description_cn="[成长] 升级你牌组中的一张牌。（需要：可以升级的牌）",
                effects=[],
                requires_card_upgrade=True,
            ),
        ],
        act=1,
    ),
    "Mushrooms": Event(
        id="Mushrooms",
        name="Mushrooms",
        name_cn="蘑菇",
        description="You walk through a corridor covered in colorful mushrooms. Since you know nothing about mycology, you can't identify their types. You want to leave, but feel a strange urge to eat a mushroom...",
        description_cn="你走进一条遍地是五彩斑斓蘑菇的走廊。由于你对真菌学毫无研究，你无法辨识它们的种类。你想要离开这里，但却有一种奇怪的冲动想要去吃一个蘑菇……",
        choices=[
            EventChoice(
                description="[Stomp] Enrage the mushrooms! Ambush!",
                description_cn="[踩扁] 激怒蘑菇们。有埋伏！！",
                effects=[],
                trigger_combat=True,
                combat_enemies=["FungiBeast", "FungiBeast", "FungiBeast"],
                combat_reward="Strange Mushroom",
            ),
            EventChoice(
                description="[Eat] Heal 25% HP. Get cursed with Parasite.",
                description_cn="[吃下] 回复25%生命。被诅咒——获得诅咒牌「寄生」。",
                effects=[
                    EventEffect(EventEffectType.GAIN_MAX_HP_PERCENT, amount=25),
                    EventEffect(EventEffectType.GAIN_CARD, card_id="Parasite"),
                ]
            ),
        ],
        act=1,
        min_floor=7,
    ),
    "Scrap Ooze": Event(
        id="Scrap Ooze",
        name="Scrap Ooze",
        name_cn="破烂软泥",
        description="You hear strange gurgling and metal scraping sounds. Before you is a slime-like creature that has eaten too much scrap metal and is digesting poorly. You see a strange glow in its center - perhaps a magical item? You could reach into its... opening to get treasure, but acid and sharp scraps might hurt you.",
        description_cn="你刚走进房间，就听见奇怪的咕嘟声和金属的摩擦声。在你面前的是一个史莱姆状的生物，它显然是吃了太多的破铜烂铁，消化不良了。你在这个生物的中央见到了奇怪的光芒，或许是什么有魔法的物品？看起来只要你愿意把手伸进这东西的……开口，你就能得到什么财宝。当然，酸液和尖锐的破烂有可能会让你受伤。",
        choices=[
            EventChoice(
                description="[Reach In] Lose 3 HP. 25% chance to find a relic.",
                description_cn="[伸手进去] 失去3生命。25%：找到一件遗物。",
                effects=[],
                base_damage=3,
                base_chance=25,
            ),
            EventChoice(
                description="[Leave] The slime continues digesting. You leave.",
                description_cn="[离开] 史莱姆并不在意，接着慢慢消化它的美餐。你决定离开。",
                effects=[]
            ),
        ],
        act=1,
    ),
    "Shining Light": Event(
        id="Shining Light",
        name="Shining Light",
        name_cn="闪耀之光",
        description="You discover a thick beam of light in the center of the room. The light pillar has warm, shimmering patterns that seem to invite you in.",
        description_cn="你发现在房间中央围绕着一束很粗的光柱。光柱上有着温暖而闪烁的美丽花纹仿佛在邀请你进入。",
        choices=[
            EventChoice(
                description="[Enter] Upgrade 2 random cards. Lose 20% of max HP. (Requires upgradeable cards)",
                description_cn="[走进] 随机升级2张牌。失去20%最大生命值的生命。（需要：可以升级的牌）",
                effects=[],
                requires_upgrade_any=True,
                upgrades_count=2,
                lose_hp_percent=20,
            ),
            EventChoice(
                description="[Leave] You walk around the light, curious but cautious.",
                description_cn="[离开] 你绕过光柱，虽然心中仍有些好奇如果走进去会怎么样。",
                effects=[]
            ),
        ],
        act=1,
    ),

    "Face Trader": Event(
        id="Face Trader",
        name="Face Trader",
        name_cn="换脸商",
        description="You pass a strange statue holding many masks. Before you can leave, a gentle voice calls out: 'Please, stay.' The statue turns to face you - it's not a statue at all, but a pale, thin man. 'Your face, may I touch it? Or, would you like to trade?'",
        description_cn='你经过一尊举着许多不同面具的奇怪雕像，但没走几步……你就听见身后传来一个轻柔的声音："请留步。"你回了回头，却发现那尊雕像也已经转向了你！仔细一看，原来这并不是一尊雕像，只是一个肤色如同雕像的消瘦男人……他是不是根本没有在呼吸？"你的脸，让我碰碰？或者，想要交易？"',
        choices=[
            EventChoice(
                description="[Touch] Lose 10% max HP. Gain 75 gold (50 if Ascension 15+).",
                description_cn="[触碰] 失去10%最大生命值的生命，获得75金币（ ascension 15+为50）。",
                effects=[],
                lose_hp_percent=10,
                gain_gold=75,
                ascension_gold_15=50,
            ),
            EventChoice(
                description="[Trade] 40% good face, 40% bad face, 20% neutral face.",
                description_cn="[交易] 40%好脸；40%坏脸；20%中间脸。",
                effects=[],
                trade_faces=True,
            ),
            EventChoice(
                description="[Leave] 'Stay, please, stay.' You made the right choice.",
                description_cn='[离开] "留步，留步啊，请留步，请留步，请留步。"你觉得自己做出了正确的选择。',
                effects=[]
            ),
        ],
        act=1,
        min_floor=0,
    ),
}


ACT2_EVENTS: dict[str, Event] = {
    "Face Trader": Event(
        id="Face Trader",
        name="Face Trader",
        name_cn="换脸商",
        description="You pass a strange statue holding many masks. Before you can leave, a gentle voice calls out: 'Please, stay.' The statue turns to face you - it's not a statue at all, but a pale, thin man. 'Your face, may I touch it? Or, would you like to trade?'",
        description_cn='你经过一尊举着许多不同面具的奇怪雕像，但没走几步……你就听见身后传来一个轻柔的声音："请留步。"你回了回头，却发现那尊雕像也已经转向了你！仔细一看，原来这并不是一尊雕像，只是一个肤色如同雕像的消瘦男人……他是不是根本没有在呼吸？"你的脸，让我碰碰？或者，想要交易？"',
        choices=[
            EventChoice(
                description="[Touch] Lose 10% max HP. Gain 75 gold.",
                description_cn="[触碰] 失去10%最大生命值的生命，获得75金币。",
                effects=[],
                lose_hp_percent=10,
                gain_gold=75,
            ),
            EventChoice(
                description="[Trade] 40% good face, 40% bad face, 20% neutral face.",
                description_cn="[交易] 40%好脸；40%坏脸；20%中间脸。",
                effects=[],
                trade_faces=True,
            ),
            EventChoice(
                description="[Leave] 'Stay, please, stay.' You made the right choice.",
                description_cn='[离开] "留步，留步啊，请留步，请留步，请留步。"你觉得自己做出了正确的选择。',
                effects=[]
            ),
        ],
        act=2,
        min_floor=0,
    ),
    "Faceless Trader": Event(
        id="Faceless Trader",
        name="Faceless Trader",
        name_cn="换脸商",
        description="A mysterious merchant with a changing face.",
        description_cn="一个有着不断变化面孔的神秘商人。",
        choices=[
            EventChoice(
                description="[Trade] Remove a card. Gain 50 gold.",
                description_cn="[交易] 移除一张卡牌，获得50金币。",
                effects=[
                    EventEffect(EventEffectType.CHOOSE_CARD_TO_REMOVE),
                    EventEffect(EventEffectType.GAIN_GOLD, amount=50),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=2,
    ),
    "The Nest": Event(
        id="The Nest",
        name="The Nest",
        name_cn="巢穴",
        description="A nest full of strange eggs.",
        description_cn="一个满是奇怪蛋的巢穴。",
        choices=[
            EventChoice(
                description="[Take Egg] Lose 10 HP. Gain 100 gold.",
                description_cn="[拿走蛋] 失去10点生命，获得100金币。",
                effects=[
                    EventEffect(EventEffectType.LOSE_HP, amount=10),
                    EventEffect(EventEffectType.GAIN_GOLD, amount=100),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=2,
    ),
    "The Colosseum": Event(
        id="The Colosseum",
        name="The Colosseum",
        name_cn="竞技场",
        description="You enter a grand colosseum. The crowd roars.",
        description_cn="你进入了一个宏伟的竞技场。观众欢呼雀跃。",
        choices=[
            EventChoice(
                description="[Fight] Lose 10 HP. Gain 100 gold.",
                description_cn="[战斗] 失去10点生命，获得100金币。",
                effects=[
                    EventEffect(EventEffectType.LOSE_HP, amount=10),
                    EventEffect(EventEffectType.GAIN_GOLD, amount=100),
                ]
            ),
            EventChoice(
                description="[Flee] Nothing happens.",
                description_cn="[逃跑] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=2,
    ),
    "N'loth": Event(
        id="N'loth",
        name="N'loth",
        name_cn="恩洛斯",
        description="A strange creature offers you a deal.",
        description_cn="一个奇怪的生物向你提供了一个交易。",
        choices=[
            EventChoice(
                description="[Bargain] Lose 50 gold. Remove a card.",
                description_cn="[讨价还价] 失去50金币，移除一张卡牌。",
                effects=[
                    EventEffect(EventEffectType.LOSE_GOLD, amount=50),
                    EventEffect(EventEffectType.CHOOSE_CARD_TO_REMOVE),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=2,
    ),
    "Addict": Event(
        id="Addict",
        name="Addict",
        name_cn="流浪汉的恳求",
        description="A desperate addict begs for help.",
        description_cn="一个绝望的流浪汉乞求帮助。",
        choices=[
            EventChoice(
                description="[Help] Lose 30 gold. Gain 1 Strength.",
                description_cn="[帮助] 失去30金币，获得1点力量。",
                effects=[
                    EventEffect(EventEffectType.LOSE_GOLD, amount=30),
                    EventEffect(EventEffectType.GAIN_STRENGTH, amount=1),
                ]
            ),
            EventChoice(
                description="[Ignore] Nothing happens.",
                description_cn="[忽略] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=2,
    ),
    "Ancient Writing": Event(
        id="Ancient Writing",
        name="Ancient Writing",
        name_cn="古老文字",
        description="Ancient texts reveal hidden knowledge.",
        description_cn="古老的文本揭示了隐藏的知识。",
        choices=[
            EventChoice(
                description="[Study] Gain 1 Strength. Gain 1 Dexterity.",
                description_cn="[研究] 获得1点力量，获得1点敏捷。",
                effects=[
                    EventEffect(EventEffectType.GAIN_STRENGTH, amount=1),
                    EventEffect(EventEffectType.GAIN_DEXTERITY, amount=1),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=2,
    ),
    "Beggar": Event(
        id="Beggar",
        name="Beggar",
        name_cn="老乞丐",
        description="A humble beggar asks for charity.",
        description_cn="一个谦卑的乞丐请求施舍。",
        choices=[
            EventChoice(
                description="[Give 50g] Remove a card.",
                description_cn="[给予50金] 移除一张卡牌。",
                effects=[
                    EventEffect(EventEffectType.LOSE_GOLD, amount=50),
                    EventEffect(EventEffectType.CHOOSE_CARD_TO_REMOVE),
                ]
            ),
            EventChoice(
                description="[Give 100g] Remove 2 cards.",
                description_cn="[给予100金] 移除两张卡牌。",
                effects=[
                    EventEffect(EventEffectType.LOSE_GOLD, amount=100),
                    EventEffect(EventEffectType.REMOVE_CARD, amount=2),
                ]
            ),
            EventChoice(
                description="[Ignore] Nothing happens.",
                description_cn="[忽略] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=2,
    ),
    "Cursed Tome": Event(
        id="Cursed Tome",
        name="Cursed Tome",
        name_cn="诅咒书本",
        description="A dark tome pulses with forbidden knowledge.",
        description_cn="一本黑暗的书籍散发着禁忌知识的气息。",
        choices=[
            EventChoice(
                description="[Read] Add a Curse to your deck.",
                description_cn="[阅读] 将一张诅咒加入牌组。",
                effects=[
                    EventEffect(EventEffectType.GAIN_CARD, card_id="Regret"),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=2,
    ),
    "Forgotten Altar": Event(
        id="Forgotten Altar",
        name="Forgotten Altar",
        name_cn="被遗忘的祭坛",
        description="A dark altar with a golden idol.",
        description_cn="一个有着金色偶像的黑暗祭坛。",
        choices=[
            EventChoice(
                description="[Offer] Lose 5 Max HP. Gain a random relic.",
                description_cn="[供奉] 失去5点最大生命，获得一个随机遗物。",
                effects=[
                    EventEffect(EventEffectType.LOSE_MAX_HP, amount=5),
                    EventEffect(EventEffectType.GAIN_RANDOM_RELIC),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=2,
    ),
    "Knowing Skull": Event(
        id="Knowing Skull",
        name="Knowing Skull",
        name_cn="全知头骨",
        description="A severed head that speaks in riddles.",
        description_cn="一个用谜语说话的斩首。",
        choices=[
            EventChoice(
                description="[Consult] Lose 8 HP. Obtain a potion.",
                description_cn="[咨询] 失去8点生命，获得一瓶药水。",
                effects=[
                    EventEffect(EventEffectType.LOSE_HP, amount=8),
                    EventEffect(EventEffectType.OBTAIN_POTION),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=2,
    ),
    "Red Mask": Event(
        id="Red Mask",
        name="Red Mask",
        name_cn="蒙面强盗",
        description="Armed bandits demand your gold.",
        description_cn="武装强盗要求你交出金币。",
        choices=[
            EventChoice(
                description="[Pay] Lose 50 gold.",
                description_cn="[支付] 失去50金币。",
                effects=[
                    EventEffect(EventEffectType.LOSE_GOLD, amount=50),
                ]
            ),
            EventChoice(
                description="[Fight] Lose 15 HP. Gain 100 gold.",
                description_cn="[战斗] 失去15点生命，获得100金币。",
                effects=[
                    EventEffect(EventEffectType.LOSE_HP, amount=15),
                    EventEffect(EventEffectType.GAIN_GOLD, amount=100),
                ]
            ),
        ],
        act=2,
    ),
    "Joust": Event(
        id="Joust",
        name="Joust",
        name_cn="长枪决斗",
        description="A knight challenges you to a joust.",
        description_cn="一位骑士向你发起长枪决斗挑战。",
        choices=[
            EventChoice(
                description="[Joust] Lose 10 HP. Gain 75 gold.",
                description_cn="[决斗] 失去10点生命，获得75金币。",
                effects=[
                    EventEffect(EventEffectType.LOSE_HP, amount=10),
                    EventEffect(EventEffectType.GAIN_GOLD, amount=75),
                ]
            ),
            EventChoice(
                description="[Decline] Nothing happens.",
                description_cn="[拒绝] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=2,
    ),
    "The Library": Event(
        id="The Library",
        name="The Library",
        name_cn="大图书馆",
        description="You find a dusty library filled with ancient tomes.",
        description_cn="你发现了一个满是古老典籍的图书馆。",
        choices=[
            EventChoice(
                description="[Read] Heal 20 HP.",
                description_cn="[阅读] 恢复20点生命。",
                effects=[
                    EventEffect(EventEffectType.GAIN_HP, amount=20),
                ]
            ),
            EventChoice(
                description="[Sleep] Gain 5 Max HP.",
                description_cn="[睡觉] 获得5点最大生命。",
                effects=[
                    EventEffect(EventEffectType.GAIN_MAX_HP, amount=5),
                ]
            ),
        ],
        act=2,
    ),
    "The Mausoleum": Event(
        id="The Mausoleum",
        name="The Mausoleum",
        name_cn="陵墓",
        description="A dark mausoleum stands before you.",
        description_cn="一座黑暗的陵墓矗立在你面前。",
        choices=[
            EventChoice(
                description="[Open] Gain 150 gold. Lose 10 Max HP.",
                description_cn="[打开] 获得150金币，失去10点最大生命。",
                effects=[
                    EventEffect(EventEffectType.GAIN_GOLD, amount=150),
                    EventEffect(EventEffectType.LOSE_MAX_HP, amount=10),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=2,
    ),
    "Vampires": Event(
        id="Vampires",
        name="Vampires",
        name_cn="吸血鬼",
        description="A circle of pale figures closes in and offers you a dark bargain.",
        description_cn="一群脸色苍白的身影围了上来，向你提出了一笔黑暗交易。",
        choices=[
            EventChoice(
                description="[Bite] Lose 30% Max HP. Remove all Strikes. Gain 5 Bites.",
                description_cn="[接受] 失去 30% 最大生命值。移除所有打击。获得 5 张咬噬。",
                effects=[
                    EventEffect(EventEffectType.LOSE_MAX_HP_PERCENT, amount=30),
                    EventEffect(EventEffectType.GAIN_CARD, amount=5, card_id="Bite"),
                ]
                ,
                remove_starter_strikes=True,
            ),
            EventChoice(
                description="[Flee] Nothing happens.",
                description_cn="[逃跑] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=2,
    ),
    "Ghost": Event(
        id="Ghost",
        name="Ghosts",
        name_cn="幽灵议会",
        description="A whispering chorus of ghosts offers power in exchange for your life.",
        description_cn="一群低语的幽灵向你许诺力量，并索取你的生命。",
        choices=[
            EventChoice(
                description="[Become a Ghost] Lose 50% Max HP. Gain 5 Apparitions. (Ascension 15+: 3)",
                description_cn="[成为幽灵] 失去 50% 最大生命值。获得 5 张幻影（进阶 15+ 时为 3 张）。",
                effects=[
                    EventEffect(EventEffectType.LOSE_MAX_HP_PERCENT, amount=50),
                    EventEffect(EventEffectType.GAIN_CARD, amount=5, card_id="Apparition"),
                ]
                ,
                gain_card_count_ascension_15=3,
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=2,
    ),
}


ACT3_EVENTS: dict[str, Event] = {
    "Mind Bloom": Event(
        id="Mind Bloom",
        name="Mind Bloom",
        name_cn="心灵绽放",
        description="A beautiful flower blooms before you.",
        description_cn="一朵美丽的花在你面前绽放。",
        choices=[
            EventChoice(
                description="[Smell] Heal to full HP.",
                description_cn="[闻] 恢复到满生命。",
                effects=[
                    EventEffect(EventEffectType.GAIN_HP, amount=999),
                ]
            ),
            EventChoice(
                description="[Pick] Gain 50 gold. Lose 10 HP.",
                description_cn="[采摘] 获得50金币，失去10点生命。",
                effects=[
                    EventEffect(EventEffectType.GAIN_GOLD, amount=50),
                    EventEffect(EventEffectType.LOSE_HP, amount=10),
                ]
            ),
        ],
        act=3,
    ),
    "Secret Portal": Event(
        id="Secret Portal",
        name="Secret Portal",
        name_cn="秘密传送门",
        description="A shimmering portal appears.",
        description_cn="一个闪闪发光的传送门出现了。",
        choices=[
            EventChoice(
                description="[Enter] Lose 20 HP. Gain a random relic.",
                description_cn="[进入] 失去20点生命，获得一个随机遗物。",
                effects=[
                    EventEffect(EventEffectType.LOSE_HP, amount=20),
                    EventEffect(EventEffectType.GAIN_RANDOM_RELIC),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=3,
    ),
    "Sensory Stone": Event(
        id="Sensory Stone",
        name="Sensory Stone",
        name_cn="感知石",
        description="A strange stone pulses with energy.",
        description_cn="一块奇怪的石头散发着能量。",
        choices=[
            EventChoice(
                description="[Touch] Gain 10 Max HP.",
                description_cn="[触摸] 获得10点最大生命。",
                effects=[
                    EventEffect(EventEffectType.GAIN_MAX_HP, amount=10),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=3,
    ),
    "Falling": Event(
        id="Falling",
        name="Falling",
        name_cn="坠落",
        description="You fall through a endless void.",
        description_cn="你坠入无尽的虚空。",
        choices=[
            EventChoice(
                description="[Brace] Lose 15 HP. Gain 2 Strength.",
                description_cn="[缓冲] 失去15点生命，获得2点力量。",
                effects=[
                    EventEffect(EventEffectType.LOSE_HP, amount=15),
                    EventEffect(EventEffectType.GAIN_STRENGTH, amount=2),
                ]
            ),
            EventChoice(
                description="[Continue] Lose 30 HP.",
                description_cn="[继续] 失去30点生命。",
                effects=[
                    EventEffect(EventEffectType.LOSE_HP, amount=30),
                ]
            ),
        ],
        act=3,
    ),
    "Moai Head": Event(
        id="Moai Head",
        name="Moai Head",
        name_cn="摩艾石像",
        description="A massive stone head gazes at you.",
        description_cn="一尊巨大的石像注视着你。",
        choices=[
            EventChoice(
                description="[Worship] Gain 6 Max HP.",
                description_cn="[崇拜] 获得6点最大生命。",
                effects=[
                    EventEffect(EventEffectType.GAIN_MAX_HP, amount=6),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=3,
    ),
    "Mysterious Sphere": Event(
        id="Mysterious Sphere",
        name="Mysterious Sphere",
        name_cn="神秘圆球",
        description="A glowing sphere floats before you.",
        description_cn="一个发光的球体漂浮在你面前。",
        choices=[
            EventChoice(
                description="[Touch] Lose 15 HP. Gain 200 gold.",
                description_cn="[触摸] 失去15点生命，获得200金币。",
                effects=[
                    EventEffect(EventEffectType.LOSE_HP, amount=15),
                    EventEffect(EventEffectType.GAIN_GOLD, amount=200),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=3,
    ),
    "Tomb of Lord Red Mask": Event(
        id="Tomb of Lord Red Mask",
        name="Tomb of Lord Red Mask",
        name_cn="红面具大人之墓",
        description="You discover an ancient tomb.",
        description_cn="你发现了一座古老的坟墓。",
        choices=[
            EventChoice(
                description="[Open] Gain 222 gold.",
                description_cn="[打开] 获得222金币。",
                effects=[
                    EventEffect(EventEffectType.GAIN_GOLD, amount=222),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=3,
    ),
    "Winding": Event(
        id="Winding",
        name="Winding",
        name_cn="蜿蜒走廊",
        description="A winding corridor stretches before you.",
        description_cn="一条蜿蜒的走廊延伸在你面前。",
        choices=[
            EventChoice(
                description="[Walk] Heal 33% HP.",
                description_cn="[行走] 恢复33%生命。",
                effects=[
                    EventEffect(EventEffectType.GAIN_MAX_HP_PERCENT, amount=33),
                ]
            ),
            EventChoice(
                description="[Rest] Nothing happens.",
                description_cn="[休息] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=3,
    ),
    "Corrupt Heart": Event(
        id="Corrupt Heart",
        name="Corrupt Heart",
        name_cn="高塔之心",
        description="The heart of the spire beats ominously.",
        description_cn="高塔之心不祥地跳动着。",
        choices=[
            EventChoice(
                description="[Face] Lose 50 HP. Gain 500 gold.",
                description_cn="[面对] 失去50点生命，获得500金币。",
                effects=[
                    EventEffect(EventEffectType.LOSE_HP, amount=50),
                    EventEffect(EventEffectType.GAIN_GOLD, amount=500),
                ]
            ),
            EventChoice(
                description="[Flee] Nothing happens.",
                description_cn="[逃跑] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=3,
    ),
}


ALL_STAGE_EVENTS: dict[str, Event] = {
    "WeMeetAgain": Event(
        id="WeMeetAgain",
        name="We Meet Again",
        name_cn="我们又见面了！",
        description="A familiar face appears.",
        description_cn="一张熟悉的面孔出现了。",
        choices=[
            EventChoice(
                description="[Chat] Heal 20% HP.",
                description_cn="[聊天] 恢复20%生命。",
                effects=[
                    EventEffect(EventEffectType.GAIN_MAX_HP_PERCENT, amount=20),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=0,
    ),
    "Fountain": Event(
        id="Fountain",
        name="Fountain",
        name_cn="神圣泉水",
        description="A sacred fountain shimmers with healing waters.",
        description_cn="一口神圣的泉水闪烁着治愈之水。",
        choices=[
            EventChoice(
                description="[Drink] Heal 20% HP.",
                description_cn="[饮用] 恢复20%生命。",
                effects=[
                    EventEffect(EventEffectType.GAIN_MAX_HP_PERCENT, amount=20),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=0,
    ),
    "Designer": Event(
        id="Designer",
        name="Designer",
        name_cn="尖端设计师",
        description="A mysterious designer offers upgrades.",
        description_cn="一个神秘的设计师提供升级。",
        choices=[
            EventChoice(
                description="[Upgrade] Transform a card in your deck.",
                description_cn="[升级] 转化你牌组中的一张卡牌。",
                effects=[
                    EventEffect(EventEffectType.TRANSFORM_RANDOM_CARD),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=0,
    ),
    "Self Note": Event(
        id="Self Note",
        name="Self Note",
        name_cn="留给自己的讯息",
        description="A note left by your past self.",
        description_cn="过去的你留下的一张纸条。",
        choices=[
            EventChoice(
                description="[Read] Gain 50 gold.",
                description_cn="[阅读] 获得50金币。",
                effects=[
                    EventEffect(EventEffectType.GAIN_GOLD, amount=50),
                ]
            ),
            EventChoice(
                description="[Ignore] Nothing happens.",
                description_cn="[忽略] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=0,
    ),
    "Duplicate": Event(
        id="Duplicate",
        name="Duplicate",
        name_cn="复制祭坛",
        description="A shrine that can duplicate your cards.",
        description_cn="一个可以复制你卡牌的祭坛。",
        choices=[
            EventChoice(
                description="[Duplicate] Choose a card to add a copy to your deck.",
                description_cn="[复制] 选择一张卡牌，将复制加入牌组。",
                effects=[
                    EventEffect(EventEffectType.GAIN_CARD),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=0,
    ),
    "Blacksmith": Event(
        id="Blacksmith",
        name="Blacksmith",
        name_cn="邪恶熔炉",
        description="A dark furnace that can upgrade your cards.",
        description_cn="一个可以升级你卡牌的黑暗熔炉。",
        choices=[
            EventChoice(
                description="[Upgrade] Upgrade a random card in your deck.",
                description_cn="[升级] 升级你牌组中的一张随机卡牌。",
                effects=[
                    EventEffect(EventEffectType.UPGRADE_CARD),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=0,
    ),
    "Bonfire": Event(
        id="Bonfire",
        name="Bonfire",
        name_cn="篝火精灵",
        description="A mystical bonfire offers comfort.",
        description_cn="一个神秘的篝火提供慰藉。",
        choices=[
            EventChoice(
                description="[Rest] Heal 20% HP.",
                description_cn="[休息] 恢复20%生命。",
                effects=[
                    EventEffect(EventEffectType.GAIN_MAX_HP_PERCENT, amount=20),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=0,
    ),
    "Match and Keep": Event(
        id="Match and Keep",
        name="Match and Keep",
        name_cn="对对碰！",
        description="A game of chance and luck.",
        description_cn="一个关于运气和机会的游戏。",
        choices=[
            EventChoice(
                description="[Play] Lose 10 HP. Gain 100 gold.",
                description_cn="[游戏] 失去10点生命，获得100金币。",
                effects=[
                    EventEffect(EventEffectType.LOSE_HP, amount=10),
                    EventEffect(EventEffectType.GAIN_GOLD, amount=100),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=0,
    ),
    "Gold Shrine": Event(
        id="Gold Shrine",
        name="Gold Shrine",
        name_cn="金色神龛",
        description="A shrine blessed with fortune.",
        description_cn="一个被 fortune 保佑的神龛。",
        choices=[
            EventChoice(
                description="[Pray] Gain 150 gold.",
                description_cn="[祈祷] 获得150金币。",
                effects=[
                    EventEffect(EventEffectType.GAIN_GOLD, amount=150),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=0,
    ),
    "Lab": Event(
        id="Lab",
        name="Lab",
        name_cn="实验室",
        description="A mysterious laboratory full of experiments.",
        description_cn="一个满是实验的神秘实验室。",
        choices=[
            EventChoice(
                description="[Experiment] Transform 2 random cards.",
                description_cn="[实验] 转化2张随机卡牌。",
                effects=[
                    EventEffect(EventEffectType.TRANSFORM_RANDOM_CARD),
                    EventEffect(EventEffectType.TRANSFORM_RANDOM_CARD),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=0,
    ),
    "Purify": Event(
        id="Purify",
        name="Purify",
        name_cn="净化",
        description="A purifying light cleanses your deck.",
        description_cn="一道净化之光清洁你的牌组。",
        choices=[
            EventChoice(
                description="[Purify] Remove a Curse from your deck.",
                description_cn="[净化] 从你的牌组中移除一张诅咒。",
                effects=[
                    EventEffect(EventEffectType.REMOVE_RANDOM_CURSE),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=0,
    ),
    "Transmogrifier": Event(
        id="Transmogrifier",
        name="Transmogrifier",
        name_cn="转化神龛",
        description="A shrine that transforms cards.",
        description_cn="一个可以转化卡牌的祭坛。",
        choices=[
            EventChoice(
                description="[Transform] Transform a random card in your deck.",
                description_cn="[转化] 转化你牌组中的一张随机卡牌。",
                effects=[
                    EventEffect(EventEffectType.TRANSFORM_RANDOM_CARD),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=0,
    ),
    "Upgrade Shrine": Event(
        id="Upgrade Shrine",
        name="Upgrade Shrine",
        name_cn="升级神龛",
        description="A shrine that empowers your cards.",
        description_cn="一个可以强化你卡牌的祭坛。",
        choices=[
            EventChoice(
                description="[Upgrade] Upgrade 2 random cards in your deck.",
                description_cn="[升级] 升级你牌组中的2张随机卡牌。",
                effects=[
                    EventEffect(EventEffectType.UPGRADE_CARD),
                    EventEffect(EventEffectType.UPGRADE_CARD),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=0,
    ),
    "Wheel": Event(
        id="Wheel",
        name="Wheel",
        name_cn="变化大转盘",
        description="A mysterious wheel of fate.",
        description_cn="一个神秘的命运转盘。",
        choices=[
            EventChoice(
                description="[Spin] Random outcome.",
                description_cn="[旋转] 随机结果。",
                effects=[
                    EventEffect(EventEffectType.GAIN_GOLD, amount=50),
                ]
            ),
            EventChoice(
                description="[Leave] Nothing happens.",
                description_cn="[离开] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=0,
    ),
    "Lady In Blue": Event(
        id="Lady In Blue",
        name="Lady In Blue",
        name_cn="蓝衣女子",
        description="A woman in blue offers mysterious aid.",
        description_cn="一个蓝衣女子提供神秘的帮助。",
        choices=[
            EventChoice(
                description="[Accept] Heal 50% HP. Gain 3 Strength.",
                description_cn="[接受] 恢复50%生命，获得3点力量。",
                effects=[
                    EventEffect(EventEffectType.GAIN_MAX_HP_PERCENT, amount=50),
                    EventEffect(EventEffectType.GAIN_STRENGTH, amount=3),
                ]
            ),
            EventChoice(
                description="[Decline] Nothing happens.",
                description_cn="[拒绝] 什么都没有发生。",
                effects=[]
            ),
        ],
        act=0,
    ),
}
ACT1_EVENT_KEYS = [
    "Big Fish",
    "The Cleric",
    "Dead Adventurer",
    "Golden Idol",
    "Golden Wing",
    "World of Goop",
    "Liars Game",
    "Living Wall",
    "Mushrooms",
    "Scrap Ooze",
    "Shining Light",
]

ACT2_EVENT_KEYS = [
    "Addict",
    "Back to Basics",
    "Beggar",
    "Colosseum",
    "Cursed Tome",
    "Drug Dealer",
    "Forgotten Altar",
    "Ghosts",
    "Masked Bandits",
    "Nest",
    "The Library",
    "The Mausoleum",
    "Vampires",
]

ACT3_EVENT_KEYS = [
    "Falling",
    "MindBloom",
    "The Moai Head",
    "Mysterious Sphere",
    "SensoryStone",
    "Tomb of Lord Red Mask",
    "Winding Halls",
]

SHRINE_EVENT_KEYS = [
    "Match and Keep!",
    "Golden Shrine",
    "Transmorgrifier",
    "Purifier",
    "Upgrade Shrine",
    "Wheel of Change",
]

SPECIAL_ONE_TIME_EVENT_KEYS = [
    "Accursed Blacksmith",
    "Bonfire Elementals",
    "Designer",
    "Duplicator",
    "FaceTrader",
    "Fountain of Cleansing",
    "Knowing Skull",
    "Lab",
    "N'loth",
    "NoteForYourself",
    "SecretPortal",
    "The Joust",
    "WeMeetAgain",
    "The Woman in Blue",
]

TERMINAL_EVENT_KEYS = ["SpireHeart"]

ACT_EVENT_KEYS_BY_ACT = {
    1: ACT1_EVENT_KEYS,
    2: ACT2_EVENT_KEYS,
    3: ACT3_EVENT_KEYS,
}

SHRINE_EVENT_KEYS_BY_ACT = {
    1: SHRINE_EVENT_KEYS,
    2: SHRINE_EVENT_KEYS,
    3: SHRINE_EVENT_KEYS,
}

SHRINE_CHANCE = 0.25

EVENT_KEY_ALIASES: dict[str, str] = {
    "Golden Shrine Trap": "Golden Idol",
    "Wing Statuette": "Golden Wing",
    "Golden Wing": "Golden Wing",
    "GoopPuddle": "World of Goop",
    "World of Goop": "World of Goop",
    "Sssserpent": "Liars Game",
    "Liars Game": "Liars Game",
    "Ghost": "Ghosts",
    "Ghosts": "Ghosts",
    "The Nest": "Nest",
    "Nest": "Nest",
    "The Colosseum": "Colosseum",
    "Colosseum": "Colosseum",
    "Winding": "Winding Halls",
    "Winding Halls": "Winding Halls",
    "Lady In Blue": "The Woman in Blue",
    "The Woman in Blue": "The Woman in Blue",
    "Fountain": "Fountain of Cleansing",
    "Blacksmith": "Accursed Blacksmith",
    "Bonfire": "Bonfire Elementals",
    "Duplicate": "Duplicator",
    "Gold Shrine": "Golden Shrine",
    "Purify": "Purifier",
    "Wheel": "Wheel of Change",
    "Self Note": "NoteForYourself",
    "Joust": "The Joust",
    "Red Mask": "Masked Bandits",
    "Face Trader": "FaceTrader",
    "Mind Bloom": "MindBloom",
    "Secret Portal": "SecretPortal",
    "Sensory Stone": "SensoryStone",
    "Moai Head": "The Moai Head",
    "Corrupt Heart": "SpireHeart",
}

EVENT_ID_BY_KEY = {
    "Big Fish": "BigFish",
    "The Cleric": "Cleric",
    "Dead Adventurer": "DeadAdventurer",
    "Golden Idol": "GoldenIdolEvent",
    "Golden Wing": "GoldenWing",
    "World of Goop": "GoopPuddle",
    "Liars Game": "Sssserpent",
    "Living Wall": "LivingWall",
    "Mushrooms": "Mushrooms",
    "Scrap Ooze": "ScrapOoze",
    "Shining Light": "ShiningLight",
    "Addict": "Addict",
    "Back to Basics": "BackToBasics",
    "Beggar": "Beggar",
    "Colosseum": "Colosseum",
    "Cursed Tome": "CursedTome",
    "Drug Dealer": "DrugDealer",
    "Forgotten Altar": "ForgottenAltar",
    "Ghosts": "Ghosts",
    "Masked Bandits": "MaskedBandits",
    "Nest": "Nest",
    "The Library": "TheLibrary",
    "The Mausoleum": "TheMausoleum",
    "Vampires": "Vampires",
    "Falling": "Falling",
    "MindBloom": "MindBloom",
    "The Moai Head": "MoaiHead",
    "Mysterious Sphere": "MysteriousSphere",
    "SensoryStone": "SensoryStone",
    "Tomb of Lord Red Mask": "TombRedMask",
    "Winding Halls": "WindingHalls",
    "Match and Keep!": "GremlinMatchGame",
    "Golden Shrine": "GoldShrine",
    "Transmorgrifier": "Transmogrifier",
    "Purifier": "PurificationShrine",
    "Upgrade Shrine": "UpgradeShrine",
    "Wheel of Change": "GremlinWheelGame",
    "Accursed Blacksmith": "AccursedBlacksmith",
    "Bonfire Elementals": "Bonfire",
    "Designer": "Designer",
    "Duplicator": "Duplicator",
    "FaceTrader": "FaceTrader",
    "Fountain of Cleansing": "FountainOfCurseRemoval",
    "Knowing Skull": "KnowingSkull",
    "Lab": "Lab",
    "N'loth": "Nloth",
    "NoteForYourself": "NoteForYourself",
    "SecretPortal": "SecretPortal",
    "The Joust": "TheJoust",
    "WeMeetAgain": "WeMeetAgain",
    "The Woman in Blue": "WomanInBlue",
    "SpireHeart": "SpireHeart",
}

EVENT_POOL_BUCKET_BY_KEY = {
    **{key: "act_event" for key in ACT1_EVENT_KEYS + ACT2_EVENT_KEYS + ACT3_EVENT_KEYS},
    **{key: "shrine" for key in SHRINE_EVENT_KEYS},
    **{key: "special_one_time" for key in SPECIAL_ONE_TIME_EVENT_KEYS},
    **{key: "terminal" for key in TERMINAL_EVENT_KEYS},
}

EVENT_GATING_FLAGS_BY_KEY = {
    "Dead Adventurer": ["floor_gt_6"],
    "Mushrooms": ["floor_gt_6"],
    "The Cleric": ["gold_gte_35"],
    "Beggar": ["gold_gte_75"],
    "Colosseum": ["map_depth_gt_half"],
    "The Moai Head": ["golden_idol_or_half_hp"],
    "Fountain of Cleansing": ["player_is_cursed"],
    "Designer": ["act_2_or_3", "gold_gte_75"],
    "Duplicator": ["act_2_or_3"],
    "FaceTrader": ["act_1_or_2"],
    "Knowing Skull": ["act_2", "hp_gt_12"],
    "N'loth": ["act_2", "relic_count_gte_2"],
    "The Joust": ["act_2", "gold_gte_50"],
    "The Woman in Blue": ["gold_gte_50"],
    "SecretPortal": ["act_3", "playtime_seconds_gte_800"],
    "NoteForYourself": ["ascension_lt_15"],
}

_LEGACY_EVENT_SOURCE_MAP: dict[str, tuple[dict[str, Event], str]] = {
    "Big Fish": (ACT1_EVENTS, "Big Fish"),
    "The Cleric": (ACT1_EVENTS, "The Cleric"),
    "Dead Adventurer": (ACT1_EVENTS, "Dead Adventurer"),
    "Golden Idol": (ACT1_EVENTS, "Golden Shrine"),
    "Golden Wing": (ACT1_EVENTS, "Wing Statuette"),
    "World of Goop": (ACT1_EVENTS, "World of Goop"),
    "Liars Game": (ACT1_EVENTS, "Liars Game"),
    "Living Wall": (ACT1_EVENTS, "Living Wall"),
    "Mushrooms": (ACT1_EVENTS, "Mushrooms"),
    "Scrap Ooze": (ACT1_EVENTS, "Scrap Ooze"),
    "Shining Light": (ACT1_EVENTS, "Shining Light"),
    "Addict": (ACT2_EVENTS, "Addict"),
    "Back to Basics": (ACT2_EVENTS, "Ancient Writing"),
    "Beggar": (ACT2_EVENTS, "Beggar"),
    "Colosseum": (ACT2_EVENTS, "The Colosseum"),
    "Cursed Tome": (ACT2_EVENTS, "Cursed Tome"),
    "Drug Dealer": (ACT2_EVENTS, "Addict"),
    "Forgotten Altar": (ACT2_EVENTS, "Forgotten Altar"),
    "Ghosts": (ACT2_EVENTS, "Ghost"),
    "Masked Bandits": (ACT2_EVENTS, "Red Mask"),
    "Nest": (ACT2_EVENTS, "The Nest"),
    "The Library": (ACT2_EVENTS, "The Library"),
    "The Mausoleum": (ACT2_EVENTS, "The Mausoleum"),
    "Vampires": (ACT2_EVENTS, "Vampires"),
    "Falling": (ACT3_EVENTS, "Falling"),
    "MindBloom": (ACT3_EVENTS, "Mind Bloom"),
    "The Moai Head": (ACT3_EVENTS, "Moai Head"),
    "Mysterious Sphere": (ACT3_EVENTS, "Mysterious Sphere"),
    "SensoryStone": (ACT3_EVENTS, "Sensory Stone"),
    "Tomb of Lord Red Mask": (ACT3_EVENTS, "Tomb of Lord Red Mask"),
    "Winding Halls": (ACT3_EVENTS, "Winding"),
    "Match and Keep!": (ALL_STAGE_EVENTS, "Match and Keep"),
    "Golden Shrine": (ALL_STAGE_EVENTS, "Gold Shrine"),
    "Transmorgrifier": (ALL_STAGE_EVENTS, "Transmogrifier"),
    "Purifier": (ALL_STAGE_EVENTS, "Purify"),
    "Upgrade Shrine": (ALL_STAGE_EVENTS, "Upgrade Shrine"),
    "Wheel of Change": (ALL_STAGE_EVENTS, "Wheel"),
    "Accursed Blacksmith": (ALL_STAGE_EVENTS, "Blacksmith"),
    "Bonfire Elementals": (ALL_STAGE_EVENTS, "Bonfire"),
    "Designer": (ALL_STAGE_EVENTS, "Designer"),
    "Duplicator": (ALL_STAGE_EVENTS, "Duplicate"),
    "FaceTrader": (ACT2_EVENTS, "Face Trader"),
    "Fountain of Cleansing": (ALL_STAGE_EVENTS, "Fountain"),
    "Knowing Skull": (ACT2_EVENTS, "Knowing Skull"),
    "Lab": (ALL_STAGE_EVENTS, "Lab"),
    "N'loth": (ACT2_EVENTS, "N'loth"),
    "NoteForYourself": (ALL_STAGE_EVENTS, "Self Note"),
    "SecretPortal": (ACT3_EVENTS, "Secret Portal"),
    "The Joust": (ACT2_EVENTS, "Joust"),
    "WeMeetAgain": (ALL_STAGE_EVENTS, "WeMeetAgain"),
    "The Woman in Blue": (ALL_STAGE_EVENTS, "Lady In Blue"),
    "SpireHeart": (ACT3_EVENTS, "Corrupt Heart"),
}


def _resolve_event_key(identifier: str) -> str | None:
    if identifier in EVENT_ID_BY_KEY:
        return identifier
    if identifier in EVENT_KEY_ALIASES:
        return EVENT_KEY_ALIASES[identifier]
    for key, event_id in EVENT_ID_BY_KEY.items():
        if event_id == identifier:
            return key
    return None


def _canonicalize_event_template(event_key: str) -> Event:
    source = _LEGACY_EVENT_SOURCE_MAP.get(event_key)
    if source is None:
        raise KeyError(f"Unknown event key: {event_key}")
    source_bucket, source_key = source
    event = source_bucket[source_key].clone()
    event.event_key = event_key
    event.id = EVENT_ID_BY_KEY[event_key]
    event.pool_bucket = EVENT_POOL_BUCKET_BY_KEY[event_key]
    event.gating_flags = list(EVENT_GATING_FLAGS_BY_KEY.get(event_key, []))
    return event


def _set_choice_text(
    event: Event,
    descriptions: list[str],
    descriptions_cn: list[str] | None = None,
) -> None:
    cn_labels = list(descriptions_cn or [])
    for idx, label in enumerate(descriptions):
        if idx >= len(event.choices):
            break
        event.choices[idx].description = label
        event.choices[idx].description_cn = cn_labels[idx] if idx < len(cn_labels) else ""


def _apply_event_truth_overrides(event: Event) -> None:
    if event.event_key == "Back to Basics":
        event.name = "Back to Basics"
        event.description = "Inside the ancient ruins, two paths present themselves: embrace elegance and remove a card, or choose simplicity and upgrade all your starter Strikes and Defends."
        event.choices = [
            EventChoice(description="[Elegance] Remove a card from your deck."),
            EventChoice(description="[Simplicity] Upgrade all starter Strikes and Defends."),
        ]
    elif event.event_key == "Drug Dealer":
        event.name = "Drug Dealer"
        event.description = "A hooded dealer lays out three offers: a dose of J.A.X., a risky two-card experiment, or a mutagenic injection."
        event.choices = [
            EventChoice(description="[J.A.X.] Obtain J.A.X."),
            EventChoice(description="[Experiment] Transform 2 cards."),
            EventChoice(description="[Inject Mutagens] Obtain Mutagenic Strength."),
        ]
    elif event.event_key == "Ghosts":
        event.name = "Ghosts"
        event.description = "A chorus of whispering spirits offers ethereal power in exchange for part of your life."
        _set_choice_text(event, [
            "[Accept] Lose 50% Max HP. Obtain Apparitions.",
            "[Leave] Walk away.",
        ])
    elif event.event_key == "Masked Bandits":
        event.name = "Masked Bandits"
        event.description = "Masked bandits step from the shadows and demand your gold. You can pay up, or refuse and fight."
        event.choices = [
            EventChoice(description="[Pay] Lose all your gold.", effects=[EventEffect(EventEffectType.LOSE_GOLD, amount=9999)]),
            EventChoice(description="[Fight] Refuse and battle the bandits.", trigger_combat=True, combat_enemies=["Pointy", "Romeo", "Bear"]),
        ]
    elif event.event_key == "Nest":
        event.name = "Nest"
        event.description = "You discover a nest of stolen treasures and a choice between shiny coins and a strange ritual dagger."
    elif event.event_key == "Colosseum":
        event.name = "Colosseum"
        event.description = "The arena crowd spots you. First comes the spectacle, and if you crave more, a second brutal match awaits."
        event.choices = [EventChoice(description="[Continue] Step into the arena.")]
    elif event.event_key == "The Library":
        event.description = "You uncover a quiet library. You may rest among the books, or study and claim one of the offered cards."
        event.choices = [
            EventChoice(description="[Read] Choose a card to add to your deck."),
            EventChoice(description="[Sleep] Heal 33% of max HP."),
        ]
    elif event.event_key == "Forgotten Altar":
        event.description = "A forgotten altar looms in the dark. Its offerings change depending on whether you still carry the Golden Idol."
    elif event.event_key == "Knowing Skull":
        event.description = "The skull offers repeated bargains: potion, gold, or a colorless card. Each answer costs life."
        event.choices = [EventChoice(description="[Approach] Hear the skull's offers.")]
    elif event.event_key == "MindBloom":
        event.name = "Mind Bloom"
        event.description = "A strange bloom offers three impossible answers: fight an old boss, take immense gold with a curse, or bless your whole deck with the Mark of the Bloom."
        event.choices = [
            EventChoice(description="[I am War] Fight an Act 1 boss. Gain a rare relic and gold."),
            EventChoice(description="[I am Awake] Upgrade all cards. Obtain Mark of the Bloom."),
            EventChoice(description="[I am Rich / Healthy] Gain the floor-based reward and its curse."),
        ]
    elif event.event_key == "SecretPortal":
        event.name = "Secret Portal"
        event.description = "A hidden portal tears open in the Beyond, offering a shortcut to the final stretch."
        event.choices = [
            EventChoice(description="[Enter] Skip ahead to Act 3 floor 50."),
            EventChoice(description="[Ignore] Leave."),
        ]
    elif event.event_key == "SensoryStone":
        event.name = "Sensory Stone"
        event.description = "A sensory stone floods your mind with memories. Endure them to claim a set of colorless cards."
    elif event.event_key == "Falling":
        event.description = "As you fall through darkness, you must let go of an Attack, Skill, or Power to survive."
    elif event.event_key == "The Moai Head":
        event.name = "Moai Head"
        event.description = "An immense stone head offers devotion or sacrifice. The Golden Idol unlocks its richer bargain."
    elif event.event_key == "Mysterious Sphere":
        event.description = "A crackling sphere hovers in your path. You can walk away or disturb it and fight for a rare reward."
        event.choices = [
            EventChoice(description="[Open] Fight 2 Orb Walkers. Obtain a rare relic.", trigger_combat=True, combat_enemies=["OrbWalker", "OrbWalker"]),
            EventChoice(description="[Leave] Leave."),
        ]
    elif event.event_key == "Tomb of Lord Red Mask":
        event.description = "The tomb of the Red Mask offers gold, but the mask itself may react if you already possess it."
    elif event.event_key == "Winding Halls":
        event.name = "Winding Halls"
        event.description = "The halls twist your thoughts. Endure the maze, embrace madness for power, or turn back."
    elif event.event_key == "Accursed Blacksmith":
        event.description = "A demonic smith offers to upgrade a card, but there is a chance of taking a curse."
    elif event.event_key == "Bonfire Elementals":
        event.description = "A bonfire crackles with hungry elementals. Feed it a card to receive a powerful blessing."
    elif event.event_key == "Designer":
        event.description = "A bizarre designer offers cleanup, adjustments, or the full service for gold."
    elif event.event_key == "Duplicator":
        event.description = "A shrine invites you to duplicate one card in your deck."
        event.choices = [
            EventChoice(description="[Pray] Duplicate a card in your deck."),
            EventChoice(description="[Leave] Leave."),
        ]
    elif event.event_key == "FaceTrader":
        event.name = "Face Trader"
        event.description = "A gaunt man offers to touch your face or trade for one of his masks."
    elif event.event_key == "Fountain of Cleansing":
        event.description = "A cleansing fountain can purge curses from your deck."
        event.choices = [
            EventChoice(description="[Drink] Remove all curses from your deck."),
            EventChoice(description="[Leave] Leave."),
        ]
    elif event.event_key == "Golden Shrine":
        event.description = "A radiant shrine glitters with coins. It promises wealth, but greed may spring a trap."
    elif event.event_key == "Match and Keep!":
        event.description = "A Gremlin invites you to play a memory game for cards."
        event.choices = [EventChoice(description="[Play] Begin the match game.")]
    elif event.event_key == "Lab":
        event.description = "A hidden lab offers free potions to the bold."
        event.choices = [
            EventChoice(description="[Search] Obtain 3 random potions."),
            EventChoice(description="[Leave] Leave."),
        ]
    elif event.event_key == "N'loth":
        event.description = "N'loth offers his gift in exchange for one of two relics."
    elif event.event_key == "NoteForYourself":
        event.description = "A note from another run offers a stored card if you are willing to trade one away."
    elif event.event_key == "Purifier":
        event.description = "A purifying shrine offers to remove a card from your deck."
        event.choices = [
            EventChoice(description="[Pray] Remove a card from your deck."),
            EventChoice(description="[Leave] Leave."),
        ]
    elif event.event_key == "Transmorgrifier":
        event.description = "A mutating shrine offers to transform a card from your deck."
        event.choices = [
            EventChoice(description="[Pray] Transform a card in your deck."),
            EventChoice(description="[Leave] Leave."),
        ]
    elif event.event_key == "Upgrade Shrine":
        event.description = "An ancient shrine offers to upgrade a card in your deck."
        event.choices = [
            EventChoice(description="[Pray] Upgrade a card in your deck."),
            EventChoice(description="[Leave] Leave."),
        ]
    elif event.event_key == "WeMeetAgain":
        event.description = "A familiar figure asks for one of three things: a potion, gold, or a card. Pay the requested price for a relic."
    elif event.event_key == "The Woman in Blue":
        event.description = "The woman in blue sells potions for 20, 30, or 40 gold, or sends you away empty-handed."
        event.choices = [
            EventChoice(description="[Buy 1] Lose 20 gold. Obtain 1 potion."),
            EventChoice(description="[Buy 2] Lose 30 gold. Obtain 2 potions."),
            EventChoice(description="[Buy 3] Lose 40 gold. Obtain 3 potions."),
            EventChoice(description="[Leave] Leave."),
        ]
    elif event.event_key == "Wheel of Change":
        event.description = "A giant wheel offers fortune and misfortune in equal measure."
        event.choices = [EventChoice(description="[Spin] Spin the wheel.")]
    elif event.event_key == "The Joust":
        event.description = "A betting table offers odds on the murder of a peasant or the fall of a beast."
    elif event.event_key == "SpireHeart":
        event.name = "Spire Heart"
        event.description = "The Spire Heart pulses before you as the run reaches its final threshold."
        event.choices = [EventChoice(description="[Continue] Face the Heart.")]

    official = get_official_event_strings(str(getattr(event, "event_key", "") or getattr(event, "id", "") or ""))
    if official is not None:
        if official.name_en:
            event.name = official.name_en
        if official.name_zhs:
            event.name_cn = official.name_zhs
        if official.descriptions_en:
            event.description = official.descriptions_en[0]
        if official.descriptions_zhs:
            event.description_cn = official.descriptions_zhs[0]


def build_event(event_key: str, event_rng: Any | None = None) -> Event:
    canonical_key = _resolve_event_key(event_key)
    if canonical_key is None:
        raise KeyError(f"Unknown event identifier: {event_key}")
    event = _canonicalize_event_template(canonical_key)
    apply_official_event_strings(event)
    _apply_event_truth_overrides(event)
    if event_rng is not None:
        event.select_variant(event_rng)
    return event


EVENTS_BY_KEY: dict[str, Event] = {
    key: build_event(key)
    for key in ACT1_EVENT_KEYS + ACT2_EVENT_KEYS + ACT3_EVENT_KEYS + SHRINE_EVENT_KEYS + SPECIAL_ONE_TIME_EVENT_KEYS + TERMINAL_EVENT_KEYS
}

SHRINE_EVENTS: dict[str, Event] = {key: EVENTS_BY_KEY[key] for key in SHRINE_EVENT_KEYS}
SPECIAL_ONE_TIME_EVENTS: dict[str, Event] = {key: EVENTS_BY_KEY[key] for key in SPECIAL_ONE_TIME_EVENT_KEYS}
EVENT_KEY_BY_ID: dict[str, str] = {event.event_id: key for key, event in EVENTS_BY_KEY.items()}


def get_event_for_act(act: int, event_rng: Any) -> Event:
    event_keys = list(ACT_EVENT_KEYS_BY_ACT.get(act, ACT1_EVENT_KEYS))
    if not event_keys:
        return build_event("Big Fish", event_rng)
    idx = event_rng.random_int(len(event_keys) - 1) if event_rng is not None else 0
    return build_event(event_keys[idx], event_rng)
