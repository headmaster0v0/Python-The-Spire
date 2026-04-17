"""Relic definitions for Slay The Spire.

This module contains relic data extracted from the decompiled source.
Relics are organized by tier (STARTER, COMMON, UNCOMMON, RARE, BOSS, SHOP, SPECIAL, EVENT).

Each relic has:
- id: Unique identifier
- tier: RelicTier enum value
- name: Display name (Chinese)
- effects: List of effect descriptors for game logic
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RelicTier(str, Enum):
    STARTER = "STARTER"
    COMMON = "COMMON"
    UNCOMMON = "UNCOMMON"
    RARE = "RARE"
    BOSS = "BOSS"
    SHOP = "SHOP"
    SPECIAL = "SPECIAL"
    EVENT = "EVENT"
    DEPRECATED = "DEPRECATED"


class RelicEffectType(str, Enum):
    AT_BATTLE_START = "at_battle_start"
    AT_BATTLE_START_ENERGY = "at_battle_start_energy"
    ON_VICTORY = "on_victory"
    ON_CARD_PLAYED = "on_card_played"
    ON_ATTACK = "on_attack"
    ON_DAMAGE = "on_damage"
    MODIFY_DAMAGE = "modify_damage"
    MODIFY_BLOCK = "modify_block"
    CHANGE_RARE_CHANCE = "change_rare_chance"
    CHANGE_UNCOMMON_CHANCE = "change_uncommon_chance"
    ON_GAIN_GOLD = "on_gain_gold"
    ON_HEAL = "on_heal"
    AT_TURN_START = "at_turn_start"
    AT_TURN_END = "at_turn_end"
    AT_TURN_START_NO_ATTACK = "at_turn_start_no_attack"
    AT_TURN_START_DELAYED = "at_turn_start_delayed"
    ON_HP_LOSS = "on_hp_loss"
    ON_SHUFFLE = "on_shuffle"
    ON_EXHAUST = "on_exhaust"
    ON_DISCARD = "on_discard"
    DOUBLE_POTION_POTENCY = "double_potion_potency"
    ON_REST = "on_rest"
    ON_FLOOR_CLIMB = "on_floor_climb"
    ON_SHOP_ENTER = "on_shop_enter"
    ON_CARD_ADDED = "on_card_added"
    ON_POTION_USE = "on_potion_use"
    ON_ATTACK_DAMAGE_DEALT = "on_attack_damage_dealt"
    FIRST_ATTACK_COMBAT = "first_attack_combat"
    EVERY_N_TURNS = "every_n_turns"
    EVERY_N_TURNS_SELF = "every_n_turns_self"
    EVERY_N_ATTACKS = "every_n_attacks"
    EVERY_N_ATTACKS_SELF = "every_n_attacks_self"
    EVERY_N_SKILLS = "every_n_skills"
    EVERY_N_CARDS = "every_n_cards"
    AT_BOSS_START = "at_boss_start"
    ON_TRAP_COMBAT = "on_trap_combat"
    ELITE_HP_MODIFIER = "elite_hp_modifier"
    CARD_REWARD_MODIFIER = "card_reward_modifier"
    SHOP_PRICE_MODIFIER = "shop_price_modifier"
    CURSE_NEGATE = "curse_negate"
    CURSE_NEGATE_TRIGGER = "curse_negate_trigger"
    REST_HEAL_BONUS = "rest_heal_bonus"
    MODIFY_STRENGTH = "modify_strength"
    MODIFY_STRIKE = "modify_strike"
    ON_PICKUP = "on_pickup"
    MODIFY_DEXTERITY = "modify_dexterity"
    AVOID_ENEMIES = "avoid_enemies"
    GAIN_THORNS = "gain_thorns"
    GAIN_INTANGIBLE = "gain_intangible"
    GAIN_MANTRA = "gain_mantra"
    ON_POISON_APPLIED = "on_poison_applied"
    MODIFY_MIN_DAMAGE = "modify_min_damage"
    TREASURE_ROOM_EVERY_N_QUESTION = "treasure_room_every_n_question"
    CURSE_PLAYABLE = "curse_playable"
    CARD_REWARD_MAX_HP = "card_reward_max_hp"
    BOTTLED = "bottled"
    ON_CURSE_RECEIVED = "on_curse_received"
    ON_POWER_PLAYED = "on_power_played"
    ON_ENEMY_DEATH = "on_enemy_death"
    ON_COMBAT_END = "on_combat_end"
    MODIFY_WEAK = "modify_weak"
    MODIFY_VULNERABLE = "modify_vulnerable"
    EXTRA_CARD_REWARD = "extra_card_reward"
    CHEST_RELICS = "chest_relics"
    ORB_PASSIVE_MULTIPLY = "orb_passive_multiply"
    SHOP_NO_SELL_OUT = "shop_no_sell_out"
    POTION_ALWAYS_DROP = "potion_always_drop"
    AT_TURN_START_BLOCK = "at_turn_start_block"
    AT_TURN_START_SPECIFIC = "at_turn_start_specific"
    AT_TURN_END_HAND_BLOCK = "at_turn_end_hand_block"
    ON_EXHAUST_DAMAGE_ALL = "on_exhaust_damage_all"
    ON_EXHAUST_ADD_RANDOM = "on_exhaust_add_random"
    CURSE_STRENGTH = "curse_strength"
    AT_BATTLE_START_BUFFER = "at_battle_start_buffer"
    AT_BATTLE_START_DISCARD_DRAW = "at_battle_start_discard_draw"
    IMMUNE_WEAK = "immune_weak"
    IMMUNE_FRAIL = "immune_frail"
    REST_SITE_STRENGTH = "rest_site_strength"
    REST_SITE_REMOVE = "rest_site_remove"
    REST_SITE_DIG = "rest_site_dig"
    SCRY_BONUS = "scry_bonus"
    CONSERVE_ENERGY = "conserve_energy"
    START_WITH_STRENGTH_PER_CURSE = "start_with_strength_per_curse"
    ON_DEATH_SAVE = "on_death_save"
    HEAL_MULTIPLY = "heal_multiply"
    GAIN_MAX_HP = "gain_max_HP"
    GAIN_GOLD = "gain_gold"
    LIMIT_CARDS_DRAW = "limit_cards_draw"
    END_OF_TURN_DAMAGE_ALL_SPECIFIC = "end_of_turn_damage_all_specific"
    ON_ENEMY_DEATH_POISON_TRANSFER = "on_enemy_death_poison_transfer"
    EMPTY_HAND_DRAW = "empty_hand_draw"
    FREE_MOVEMENT = "free_movement"
    ON_VULNERABLE_APPLY = "on_vulnerable_apply"
    ON_HP_LOSS_GOLD = "on_hp_loss_gold"
    ON_CHEST_OPEN = "on_chest_open"
    LIMIT_CARDS_PLAY = "limit_cards_play"
    ON_DISCARD_ENERGY = "on_discard_energy"
    ON_EXIT_CALM_ENERGY = "on_exit_calm_energy"
    ZERO_COST_BONUS_DAMAGE = "zero_cost_bonus_damage"
    UPGRADE_RANDOM = "upgrade_random"
    BLOCK_INTENT = "block_intent"
    AT_TURN_END_NO_DISCARD = "at_turn_end_no_discard"
    AT_TURN_END_EMPTY_ORB = "at_turn_end_empty_orb"
    EVERY_2_TURNS = "every_2_turns"
    CARD_REWARD = "card_reward"
    MIRACLE = "miracle"
    ON_FIRST_DISCARD_PER_TURN = "on_first_discard_per_turn"
    GOLD_DISABLED = "gold_disabled"
    REST_HEAL_DISABLED = "rest_heal_disabled"
    REST_SITE_FORGE_DISABLED = "rest_site_forge_disabled"
    REPLACE_STARTER_RELIC = "replace_starter_relic"
    AT_BOSS_ELITE_START = "at_boss_elite_start"
    CARD_REWARD_REDUCE = "card_reward_reduce"
    ZERO_COST_ATTACK_BONUS_DAMAGE = "zero_cost_attack_bonus_damage"
    ON_EXIT_CALM = "on_exit_calm"
    GAIN_POTION = "gain_potion"
    POTION_GAIN_DISABLED = "potion_gain_disabled"
    AT_FIRST_TURN_DRAW = "at_first_turn_draw"
    GOLD_MULTIPLY = "gold_multiply"
    ELITE_REWARD_RELICS = "elite_reward_relics"
    ON_REST_ADD_CARD = "on_rest_add_card"
    START_WITH_SHIVS = "start_with_shivs"
    SCYTHE = "scythe"
    CARD_REMOVE_DISCOUNT = "card_remove_discount"
    CHANCE_FOR_FREE_ATTACK = "chance_for_free_attack"
    HEAL_PER_POWER = "heal_per_power"
    DEBUFF_CLEAR = "debuff_clear"
    SCRY_ON_SHUFFLE = "scry_on_shuffle"
    STRIKE_DAMAGE_BONUS = "strike_damage_bonus"
    MANA_GAIN_DISABLED = "mana_gain_disabled"
    REMOVE_CARDS_FROM_DECK = "remove_cards_from_deck"
    DECK_TRANSFORM = "deck_transform"
    DECK_TRANSFORM_AND_UPGRADE = "deck_transform_and_upgrade"
    FIRST_ATTACK_TWICE = "first_attack_twice"
    ARTIFACT_START = "artifact_start"
    GAIN_MANTRA_PER_TURN = "gain_mantra_per_turn"
    REST_SITE_TRANSFORM = "rest_site_transform"
    REST_SITE_UPGRADE = "rest_site_upgrade"
    CANT_HEAL = "cant_heal"
    FIRST_COMBAT_HP_ONE = "first_combat_hp_one"
    CARD_CHOICE_THREE = "card_choice_three"
    STACKABLE_DEBUFF = "stackable_debuff"
    START_WITH_CURSE = "start_with_curse"
    CARD_COPY = "card_copy"
    APPLY_WEAK_START = "apply_weak_start"
    START_WITH_ENERGY = "start_with_energy"
    START_WITH_BLOCK = "start_with_block"
    CHANCE_FOR_FREE_SKILL = "chance_for_free_skill"
    GOLD_PER_FLOOR = "gold_per_floor"
    ON_QUESTION_ROOM = "on_question_room"


@dataclass
class RelicEffect:
    effect_type: RelicEffectType
    value: int = 0
    target: str = "player"
    extra: dict[str, Any] = field(default_factory=dict)


class RelicSource(str, Enum):
    """Source where a relic was obtained.
    
    Matches Java DataRecorder.determineRelicSource() logic.
    """
    STARTER = "starter"
    SHOP = "shop"
    TREASURE = "treasure"
    REST = "rest"
    EVENT = "event"
    ELITE = "elite"
    BOSS = "boss"
    COMBAT = "combat"
    CALLING_BELL = "calling_bell"
    NEOW = "neow"
    UNKNOWN = "unknown"


@dataclass
class RelicInstance:
    """Instance of a relic with tracking information.
    
    Tracks when and how the relic was obtained, for debugging and replay.
    """
    relic_id: str
    source: RelicSource = RelicSource.UNKNOWN
    floor_obtained: int = 0
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            import time
            object.__setattr__(self, 'timestamp', time.time())
    
    def to_dict(self) -> dict:
        return {
            "relicId": self.relic_id,
            "source": self.source.value,
            "floorObtained": self.floor_obtained,
        }


@dataclass
class RelicDef:
    id: str
    tier: RelicTier
    name: str = ""
    name_en: str = ""
    description: str = ""
    flavor: str = ""
    effects: list[RelicEffect] = field(default_factory=list)
    price: int = -1
    character_class: str = "UNIVERSAL"
    rarity: str = ""
    wiki_url: str = ""
    related_links: list = field(default_factory=list)

    def __post_init__(self):
        if not self.name:
            self.name = self.id

    def get_price(self) -> int:
        if self.price >= 0:
            return self.price
        tier_prices = {
            RelicTier.STARTER: 300,
            RelicTier.COMMON: 150,
            RelicTier.UNCOMMON: 250,
            RelicTier.RARE: 300,
            RelicTier.SHOP: 150,
            RelicTier.SPECIAL: 400,
            RelicTier.BOSS: 999,
        }
        return tier_prices.get(self.tier, -1)


@dataclass
class RelicTracker:
    """Tracks relic acquisition and triggers for debugging and replay.
    
    Based on Java DataRecorder relic tracking system.
    """
    relics: list[RelicInstance] = field(default_factory=list)
    trigger_log: list[dict] = field(default_factory=list)
    
    def add_relic(
        self,
        relic_id: str,
        source: RelicSource,
        floor: int,
    ) -> RelicInstance:
        """Record obtaining a relic."""
        instance = RelicInstance(
            relic_id=relic_id,
            source=source,
            floor_obtained=floor,
        )
        self.relics.append(instance)
        return instance
    
    def log_trigger(
        self,
        relic_id: str,
        trigger_type: str,
        floor: int,
        turn: int = 0,
    ) -> None:
        """Log a relic trigger event."""
        import time
        self.trigger_log.append({
            "relicId": relic_id,
            "triggerType": trigger_type,
            "floor": floor,
            "turn": turn,
            "timestamp": time.time(),
        })
    
    def get_relics_by_source(self, source: RelicSource) -> list[RelicInstance]:
        """Get all relics obtained from a specific source."""
        return [r for r in self.relics if r.source == source]
    
    def get_relics_by_floor(self, floor: int) -> list[RelicInstance]:
        """Get all relics obtained on a specific floor."""
        return [r for r in self.relics if r.floor_obtained == floor]
    
    def has_relic(self, relic_id: str) -> bool:
        """Check if player has a specific relic."""
        return any(r.relic_id == relic_id for r in self.relics)
    
    def remove_relic(self, relic_id: str) -> RelicInstance | None:
        """Remove a relic and return it."""
        for i, r in enumerate(self.relics):
            if r.relic_id == relic_id:
                return self.relics.pop(i)
        return None
    
    def to_dict(self) -> dict:
        return {
            "relics": [r.to_dict() for r in self.relics],
            "triggerLog": self.trigger_log,
        }


IRONCLAD_STARTER_RELICS: dict[str, RelicDef] = {
    "BurningBlood": RelicDef(
        id="BurningBlood",
        tier=RelicTier.STARTER,
        name="燃烧之血",
        description="战斗结束时，治疗6点生命。",
        character_class="IRONCLAD",
        effects=[
            RelicEffect(RelicEffectType.ON_VICTORY, value=6, target="player"),
        ],
    ),
}

DEFECT_STARTER_RELICS: dict[str, RelicDef] = {
    "CrackedCore": RelicDef(
        id="CrackedCore",
        tier=RelicTier.STARTER,
        name="破损核心",
        description="每场战斗开始时，引导1个闪电球。",
        character_class="DEFECT",
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=1, extra={"type": "lightning_orb"}),
        ],
    ),
}

WATCHER_STARTER_RELICS: dict[str, RelicDef] = {
    "PureWater": RelicDef(
        id="PureWater",
        tier=RelicTier.STARTER,
        name="至纯之水",
        description="每场战斗开始时，将1张 Miracle 加入手牌。",
        character_class="WATCHER",
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=1, extra={"type": "miracle"}),
        ],
    ),
}

SILENT_STARTER_RELICS: dict[str, RelicDef] = {
    "RingOfTheSnake": RelicDef(
        id="RingOfTheSnake",
        tier=RelicTier.STARTER,
        name="蛇之戒指",
        description="每场战斗开始时，额外抽2张牌。",
        character_class="SILENT",
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=2, extra={"type": "draw_extra"}),
        ],
    ),
}

COMMON_RELICS: dict[str, RelicDef] = {
    "Akabeko": RelicDef(
        id="Akabeko",
        name="赤牛",
        description="你的第一张攻击牌在本场战斗中额外造成8点伤害。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.FIRST_ATTACK_COMBAT, value=8, extra={"type": "bonus_damage"}),
        ],
    ),
    "Anchor": RelicDef(
        id="Anchor",
        name="铁锚",
        description="每场战斗开始时获得10点格挡。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=10, extra={"type": "block"}),
        ],
    ),
    "AncientTeaSet": RelicDef(
        id="AncientTeaSet",
        name="古茶具套装",
        description="每次进入休息站点，下一场战斗开始时获得2点能量。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_REST, value=0, extra={"type": "tea_set_pending"}),
        ],
    ),
    "ArtOfWar": RelicDef(
        id="ArtOfWar",
        name="孙子兵法",
        description="如果你的回合没有打出击牌，下回合获得1点额外能量。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.AT_TURN_START_NO_ATTACK, value=1, extra={"type": "energy"}),
        ],
    ),
    "BagOfMarbles": RelicDef(
        id="BagOfMarbles",
        name="弹珠袋",
        description="每场战斗开始时对所有敌人施加1层易伤。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=1, target="all_enemies", extra={"type": "vulnerable"}),
        ],
    ),
    "BagOfPreparation": RelicDef(
        id="BagOfPreparation",
        name="准备背包",
        description="每场战斗开始时额外抽2张牌。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=2, extra={"type": "draw_extra"}),
        ],
    ),
    "BloodVial": RelicDef(
        id="BloodVial",
        name="小血瓶",
        description="每场战斗开始时治疗2点生命。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=2, extra={"type": "heal"}),
        ],
    ),
    "BronzeScales": RelicDef(
        id="BronzeScales",
        name="铜制鳞片",
        description="每次受到伤害时，反弹3点伤害。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=3, extra={"type": "thorns"}),
        ],
    ),
    "CentennialPuzzle": RelicDef(
        id="CentennialPuzzle",
        name="百年积木",
        description="第一次失去生命时抽3张牌。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_HP_LOSS, value=1, extra={"condition": "first_time", "type": "draw"}),
        ],
    ),
    "CeramicFish": RelicDef(
        id="CeramicFish",
        name="陶瓷小鱼",
        description="每次向牌组添加卡牌时获得9金币。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_CARD_ADDED, value=9, extra={"type": "gold"}),
        ],
    ),
    "DataDisk": RelicDef(
        id="DataDisk",
        name="数据磁盘",
        description="每场战斗开始时获得1点专注。",
        tier=RelicTier.COMMON,
        character_class="DEFECT",
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=1, extra={"type": "focus"}),
        ],
    ),
    "Damaru": RelicDef(
        id="Damaru",
        name="手摇鼓",
        description="每3次攻击获得1张随机费用为X的卡。",
        tier=RelicTier.COMMON,
        character_class="WATCHER",
        effects=[
            RelicEffect(RelicEffectType.EVERY_N_ATTACKS_SELF, value=3, extra={"type": "mantra", "amount": 1}),
        ],
    ),
    "DreamCatcher": RelicDef(
        id="DreamCatcher",
        name="捕梦网",
        description="休息时可以将一张卡牌加入你的牌组。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_REST, value=1, extra={"type": "card_reward"}),
        ],
    ),
    "HappyFlower": RelicDef(
        id="HappyFlower",
        name="开心小花",
        description="每3回合获得1点能量。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.EVERY_N_TURNS_SELF, value=3, extra={"type": "energy", "amount": 1}),
        ],
    ),
    "JuzuBracelet": RelicDef(
        id="JuzuBracelet",
        name="佛珠手链",
        description="?房间不再遭遇普通敌人。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_TRAP_COMBAT, value=0, extra={"type": "avoid"}),
        ],
    ),
    "Lantern": RelicDef(
        id="Lantern",
        name="灯笼",
        description="每场战斗第一回合获得1点能量。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START_ENERGY, value=1),
        ],
    ),
    "MawBank": RelicDef(
        id="MawBank",
        name="巨口储蓄罐",
        description="每次上一层获得12金币。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_FLOOR_CLIMB, value=12, extra={"type": "gold"}),
        ],
    ),
    "MealTicket": RelicDef(
        id="MealTicket",
        name="餐券",
        description="进入商店时治疗15点生命。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_SHOP_ENTER, value=15, extra={"type": "heal"}),
        ],
    ),
    "Nunchaku": RelicDef(
        id="Nunchaku",
        name="双节棍",
        description="打出10张攻击牌后获得1点能量。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.EVERY_N_ATTACKS_SELF, value=10, extra={"type": "energy", "amount": 1}),
        ],
    ),
    "OddlySmoothStone": RelicDef(
        id="OddlySmoothStone",
        name="意外光滑的石头",
        description="每场战斗开始时获得1点敏捷。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=1, extra={"type": "dexterity"}),
        ],
    ),
    "Omamori": RelicDef(
        id="Omamori",
        name="御守",
        description="免疫接下来获得的2张诅咒。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.CURSE_NEGATE_TRIGGER, value=2),
        ],
    ),
    "Orichalcum": RelicDef(
        id="Orichalcum",
        name="奥利哈钢",
        description="如果回合结束时没有格挡，获得6点格挡。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.AT_TURN_END, value=6, extra={"type": "block", "condition": "no_block"}),
        ],
    ),
    "PenNib": RelicDef(
        id="PenNib",
        name="钢笔尖",
        description="每打出10张攻击牌，下一次伤害翻倍。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.EVERY_N_ATTACKS_SELF, value=10, extra={"type": "double_damage"}),
        ],
    ),
    "PotionBelt": RelicDef(
        id="PotionBelt",
        name="药水腰带",
        description="拾取时获得2个药水槽。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_PICKUP, value=2, extra={"type": "potion_slots"}),
        ],
    ),
    "PreservedInsect": RelicDef(
        id="PreservedInsect",
        name="昆虫标本",
        description="精英敌人生命值减少25%。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.ELITE_HP_MODIFIER, value=-25),
        ],
    ),
    "RedSkull": RelicDef(
        id="RedSkull",
        name="红头骨",
        description="生命值低于等于50%时获得3点力量。",
        tier=RelicTier.COMMON,
        character_class="IRONCLAD",
        effects=[
            RelicEffect(RelicEffectType.MODIFY_STRENGTH, value=3, extra={"condition": "hp_below_50"}),
        ],
    ),
    "RegalPillow": RelicDef(
        id="RegalPillow",
        name="皇家枕头",
        description="休息时额外治疗15点生命。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.REST_HEAL_BONUS, value=15),
        ],
    ),
    "SmilingMask": RelicDef(
        id="SmilingMask",
        name="微笑面具",
        description="商店移除卡牌费用固定为50金币。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.CARD_REMOVE_DISCOUNT, value=50),
        ],
    ),
    "SneckoSkull": RelicDef(
        id="SneckoSkull",
        name="异蛇头骨",
        description="施加毒时额外施加1层。",
        tier=RelicTier.COMMON,
        character_class="SILENT",
        effects=[
            RelicEffect(RelicEffectType.ON_POISON_APPLIED, value=1, extra={"type": "extra_poison"}),
        ],
    ),
    "Strawberry": RelicDef(
        id="Strawberry",
        name="草莓",
        description="提升7点最大生命值。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_PICKUP, value=7, extra={"type": "max_hp"}),
        ],
    ),
    "TheBoot": RelicDef(
        id="TheBoot",
        name="发条靴",
        description="伤害小于等于4点的未格挡攻击提升至5点。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.MODIFY_MIN_DAMAGE, value=5, extra={"max": 5}),
        ],
    ),
    "TinyChest": RelicDef(
        id="TinyChest",
        name="小宝箱",
        description="每4个?房间变成宝藏房间。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.TREASURE_ROOM_EVERY_N_QUESTION, value=4),
        ],
    ),
    "ToyOrnithopter": RelicDef(
        id="ToyOrnithopter",
        name="玩具扑翼飞机",
        description="使用药水时治疗5点生命。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_POTION_USE, value=5, extra={"type": "heal"}),
        ],
    ),
    "Vajra": RelicDef(
        id="Vajra",
        name="金刚杵",
        description="每场战斗开始时获得1点力量。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=1, extra={"type": "strength"}),
        ],
    ),
    "WarPaint": RelicDef(
        id="WarPaint",
        name="战纹涂料",
        description="拾取时升级2张随机技能牌。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_PICKUP, value=2, extra={"type": "upgrade_skills"}),
        ],
    ),
    "Whetstone": RelicDef(
        id="Whetstone",
        name="磨刀石",
        description="拾取时升级2张随机攻击牌。",
        tier=RelicTier.COMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_PICKUP, value=2, extra={"type": "upgrade_attacks"}),
        ],
    ),
}

UNCOMMON_RELICS: dict[str, RelicDef] = {
    "BlueCandle": RelicDef(
        id="BlueCandle",
        name="蓝蜡烛",
        description="诅咒牌现在可以被打出，打出诅咒失去1点生命并消耗掉该牌。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.CURSE_PLAYABLE, value=1, extra={"type": "curse_playable"}),
        ],
    ),
    "BottledFlame": RelicDef(
        id="BottledFlame",
        name="瓶装火焰",
        description="拾取时选择一张攻击牌，每场战斗开始时这张牌会在手牌中。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.BOTTLED, value=1, extra={"card_type": "attack"}),
        ],
    ),
    "BottledLightning": RelicDef(
        id="BottledLightning",
        name="瓶装闪电",
        description="拾取时选择一张技能牌，每场战斗开始时这张牌会在手牌中。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.BOTTLED, value=1, extra={"card_type": "skill"}),
        ],
    ),
    "BottledTornado": RelicDef(
        id="BottledTornado",
        name="瓶装旋风",
        description="拾取时选择一张力量牌，每场战斗开始时这张牌会在手牌中。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.BOTTLED, value=1, extra={"card_type": "power"}),
        ],
    ),
    "DarkstonePeriapt": RelicDef(
        id="DarkstonePeriapt",
        name="黑石护符",
        description="获得诅咒时提升6点最大生命值。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_CURSE_RECEIVED, value=6, extra={"type": "max_hp"}),
        ],
    ),
    "Duality": RelicDef(
        id="Duality",
        name="两仪",
        description="打出攻击牌时获得1点临时敏捷。",
        tier=RelicTier.UNCOMMON,
        character_class="WATCHER",
        effects=[
            RelicEffect(RelicEffectType.ON_ATTACK, value=1, extra={"type": "temp_dexterity"}),
        ],
    ),
    "EternalFeather": RelicDef(
        id="EternalFeather",
        name="永恒羽毛",
        description="牌组每有5张卡牌，进入休息站点时治疗3点生命。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_REST, value=3, extra={"per_cards": 5, "type": "heal"}),
        ],
    ),
    "FrozenEgg": RelicDef(
        id="FrozenEgg",
        name="冻结之蛋",
        description="向牌组添加力量牌时使其升级。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_CARD_ADDED, value=1, extra={"type": "upgrade_power"}),
        ],
    ),
    "GoldPlatedCables": RelicDef(
        id="GoldPlatedCables",
        name="镀金缆线",
        description="最右边的充能球被动效果额外触发一次。",
        tier=RelicTier.UNCOMMON,
        character_class="DEFECT",
        effects=[
            RelicEffect(RelicEffectType.ORB_PASSIVE_MULTIPLY, value=1, extra={"type": "extra_rightmost_trigger"}),
        ],
    ),
    "GremlinHorn": RelicDef(
        id="GremlinHorn",
        name="地精之角",
        description="敌人死亡时获得1点能量并抽1张牌。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_ENEMY_DEATH, value=1, extra={"energy": 1, "draw": 1}),
        ],
    ),
    "HornCleat": RelicDef(
        id="HornCleat",
        name="船夹板",
        description="第2回合开始时获得14点格挡。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.AT_TURN_START_DELAYED, value=14, extra={"turn": 2, "type": "block"}),
        ],
    ),
    "InkBottle": RelicDef(
        id="InkBottle",
        name="墨水瓶",
        description="打出10张卡牌时抽1张牌。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.EVERY_N_CARDS, value=10, extra={"type": "draw", "amount": 1}),
        ],
    ),
    "Kunai": RelicDef(
        id="Kunai",
        name="苦无",
        description="单回合打出3张攻击牌时获得1点敏捷。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.EVERY_N_ATTACKS, value=3, extra={"type": "dexterity", "amount": 1}),
        ],
    ),
    "LetterOpener": RelicDef(
        id="LetterOpener",
        name="开信刀",
        description="单回合打出3张技能牌时对所有敌人造成5点伤害。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.EVERY_N_SKILLS, value=3, extra={"type": "damage_all", "amount": 5}),
        ],
    ),
    "Matryoshka": RelicDef(
        id="Matryoshka",
        name="套娃",
        description="接下来的2个宝箱包含2件遗物（不含Boss箱）。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.CHEST_RELICS, value=2, extra={"chests": 2}),
        ],
    ),
    "MeatOnTheBone": RelicDef(
        id="MeatOnTheBone",
        name="带骨肉",
        description="战斗结束时若生命值低于等于50%则治疗12点生命。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_COMBAT_END, value=12, extra={"condition": "hp_below_50", "type": "heal"}),
        ],
    ),
    "MercuryHourglass": RelicDef(
        id="MercuryHourglass",
        name="水银沙漏",
        description="回合开始时对所有敌人造成3点伤害。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.AT_TURN_START, value=3, target="all_enemies", extra={"type": "damage"}),
        ],
    ),
    "MoltenEgg": RelicDef(
        id="MoltenEgg",
        name="熔火之蛋",
        description="向牌组添加攻击牌时使其升级。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_CARD_ADDED, value=1, extra={"type": "upgrade_attack"}),
        ],
    ),
    "MummifiedHand": RelicDef(
        id="MummifiedHand",
        name="干瘪之手",
        description="打出力量牌时手牌中随机一张卡牌本回合花费变为0。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_POWER_PLAYED, value=1, extra={"type": "random_zero_cost"}),
        ],
    ),
    "NinjaScroll": RelicDef(
        id="NinjaScroll",
        name="忍术卷轴",
        description="每场战斗开始时手牌中有3张手里剑。",
        tier=RelicTier.UNCOMMON,
        character_class="SILENT",
        effects=[
            RelicEffect(RelicEffectType.START_WITH_SHIVS, value=3),
        ],
    ),
    "OrnamentalFan": RelicDef(
        id="OrnamentalFan",
        name="精致折扇",
        description="单回合打出3张攻击牌时获得4点格挡。",
        tier=RelicTier.UNCOMMON,
        character_class="SILENT",
        effects=[
            RelicEffect(RelicEffectType.EVERY_N_ATTACKS, value=3, extra={"type": "block", "amount": 4}),
        ],
    ),
    "Pantograph": RelicDef(
        id="Pantograph",
        name="缩放仪",
        description="Boss战开始时治疗25点生命。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.AT_BOSS_START, value=25, extra={"type": "heal"}),
        ],
    ),
    "PaperCrane": RelicDef(
        id="PaperCrane",
        name="纸鹤",
        description="易伤敌人伤害减少40%（而非25%）。",
        tier=RelicTier.UNCOMMON,
        character_class="SILENT",
        effects=[
            RelicEffect(RelicEffectType.MODIFY_WEAK, value=40, extra={"type": "reduce_damage", "default": 25}),
        ],
    ),
    "PaperFrog": RelicDef(
        id="PaperFrog",
        name="纸蛙",
        description="易伤敌人受到75%伤害（而非50%）。",
        tier=RelicTier.UNCOMMON,
        character_class="IRONCLAD",
        effects=[
            RelicEffect(RelicEffectType.MODIFY_VULNERABLE, value=75, extra={"type": "increase_damage", "default": 50}),
        ],
    ),
    "Pear": RelicDef(
        id="Pear",
        name="梨子",
        description="提升10点最大生命值。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_PICKUP, value=10, extra={"type": "max_hp"}),
        ],
    ),
    "QuestionCard": RelicDef(
        id="QuestionCard",
        name="问号牌",
        description="卡牌奖励界面额外出现1张卡牌。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.EXTRA_CARD_REWARD, value=1),
        ],
    ),
    "SelfFormingClay": RelicDef(
        id="SelfFormingClay",
        name="自成型黏土",
        description="在战斗中失去生命时下一个回合获得3点格挡。",
        tier=RelicTier.UNCOMMON,
        character_class="IRONCLAD",
        effects=[
            RelicEffect(RelicEffectType.ON_HP_LOSS, value=3, extra={"type": "block_next_turn"}),
        ],
    ),
    "Shuriken": RelicDef(
        id="Shuriken",
        name="手里剑",
        description="单回合打出3张攻击牌时获得1点力量。",
        tier=RelicTier.UNCOMMON,
        character_class="SILENT",
        effects=[
            RelicEffect(RelicEffectType.EVERY_N_ATTACKS, value=3, extra={"type": "strength", "amount": 1}),
        ],
    ),
    "SingingBowl": RelicDef(
        id="SingingBowl",
        name="颂钵",
        description="向牌组添加卡牌时获得2点最大生命值。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.CARD_REWARD_MAX_HP, value=2),
        ],
    ),
    "StrikeDummy": RelicDef(
        id="StrikeDummy",
        name="打击木偶",
        description="包含 Strike 的卡牌额外造成3点伤害。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.STRIKE_DAMAGE_BONUS, value=3),
        ],
    ),
    "Sundial": RelicDef(
        id="Sundial",
        name="日晷",
        description="牌组每洗牌3次获得2点能量。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_SHUFFLE, value=3, extra={"type": "energy", "amount": 2}),
        ],
    ),
    "SymbioticVirus": RelicDef(
        id="SymbioticVirus",
        name="共生病毒",
        description="每场战斗开始时引导1个暗影球。",
        tier=RelicTier.UNCOMMON,
        character_class="DEFECT",
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=1, extra={"type": "dark_orb"}),
        ],
    ),
    "TeardropLocket": RelicDef(
        id="TeardropLocket",
        name="泪滴吊坠盒",
        description="每场战斗开始时处于平静状态。",
        tier=RelicTier.UNCOMMON,
        character_class="WATCHER",
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=1, extra={"type": "calm_stance"}),
        ],
    ),
    "TheCourier": RelicDef(
        id="TheCourier",
        name="送货员",
        description="商店物品不会用尽且价格降低20%。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.SHOP_NO_SELL_OUT, value=20, extra={"type": "price_reduction"}),
        ],
    ),
    "ToxicEgg": RelicDef(
        id="ToxicEgg",
        name="毒素之蛋",
        description="向牌组添加技能牌时使其升级。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.ON_CARD_ADDED, value=1, extra={"type": "upgrade_skill"}),
        ],
    ),
    "WhiteBeastStatue": RelicDef(
        id="WhiteBeastStatue",
        name="白兽雕像",
        description="战斗后必定掉落药水。",
        tier=RelicTier.UNCOMMON,
        effects=[
            RelicEffect(RelicEffectType.POTION_ALWAYS_DROP, value=1),
        ],
    ),
}

RARE_RELICS: dict[str, RelicDef] = {
    "BirdFacedUrn": RelicDef(
        id="BirdFacedUrn",
        name="鸟面瓮",
        description="使用力量牌时治疗2点生命。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.HEAL_PER_POWER, value=2),
        ],
    ),
    "Calipers": RelicDef(
        id="Calipers",
        name="外卡钳",
        description="回合开始时失去15点格挡而非全部。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.AT_TURN_START, value=15, extra={"type": "lose_block"}),
        ],
    ),
    "CaptainWheel": RelicDef(
        id="CaptainWheel",
        name="舵盘",
        description="第3回合开始时获得18点格挡。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.EVERY_N_TURNS, value=3, extra={"type": "block", "amount": 18}),
        ],
    ),
    "ChampionBelt": RelicDef(
        id="ChampionBelt",
        name="冠军腰带",
        description="成功施加易伤时也施加1层虚弱。",
        tier=RelicTier.RARE,
        character_class="IRONCLAD",
        effects=[
            RelicEffect(RelicEffectType.ON_VULNERABLE_APPLY, value=1, extra={"type": "apply_weak"}),
        ],
    ),
    "CharonsAshes": RelicDef(
        id="CharonsAshes",
        name="卡戎之灰",
        description="消耗卡牌时对所有敌人造成3点伤害。",
        tier=RelicTier.RARE,
        character_class="IRONCLAD",
        effects=[
            RelicEffect(RelicEffectType.ON_EXHAUST_DAMAGE_ALL, value=3),
        ],
    ),
    "CloakClasp": RelicDef(
        id="CloakClasp",
        name="斗篷扣",
        description="回合结束时根据手牌数量获得等量格挡。",
        tier=RelicTier.RARE,
        character_class="WATCHER",
        effects=[
            RelicEffect(RelicEffectType.AT_TURN_END_HAND_BLOCK, value=1),
        ],
    ),
    "DeadBranch": RelicDef(
        id="DeadBranch",
        name="枯木树枝",
        description="消耗卡牌时获得一张本职业随机卡牌。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.ON_EXHAUST_ADD_RANDOM, value=1),
        ],
    ),
    "DuVuDoll": RelicDef(
        id="DuVuDoll",
        name="毒巫娃娃",
        description="牌组中每有1张诅咒，战斗开始时获得1层力量。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.START_WITH_STRENGTH_PER_CURSE, value=1),
        ],
    ),
    "EmotionChip": RelicDef(
        id="EmotionChip",
        name="情感芯片",
        description="回合开始时若之前受过伤则触发所有充能球被动效果。",
        tier=RelicTier.RARE,
        character_class="DEFECT",
        effects=[
            RelicEffect(RelicEffectType.AT_TURN_START, value=0, extra={"type": "trigger_orbs_if_damaged"}),
        ],
    ),
    "FossilizedHelix": RelicDef(
        id="FossilizedHelix",
        name="螺类化石",
        description="战斗开始时获得1层缓冲。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START_BUFFER, value=1),
        ],
    ),
    "GamblingChip": RelicDef(
        id="GamblingChip",
        name="赌博筹码",
        description="战斗开始时丢弃任意数量卡牌然后抽等量。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=0, extra={"type": "discard_draw"}),
        ],
    ),
    "Ginger": RelicDef(
        id="Ginger",
        name="生姜",
        description="不会再获得虚弱。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.IMMUNE_WEAK, value=1),
        ],
    ),
    "Girya": RelicDef(
        id="Girya",
        name="壶铃",
        description="现在可以在休息处获得力量（最多3次）。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.REST_SITE_STRENGTH, value=3),
        ],
    ),
    "GoldenEye": RelicDef(
        id="GoldenEye",
        name="黄金眼",
        description="预见时额外预见2张牌。",
        tier=RelicTier.RARE,
        character_class="WATCHER",
        effects=[
            RelicEffect(RelicEffectType.SCRY_BONUS, value=2),
        ],
    ),
    "IceCream": RelicDef(
        id="IceCream",
        name="冰淇淋",
        description="能量在回合间保留。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.CONSERVE_ENERGY, value=1),
        ],
    ),
    "IncenseBurner": RelicDef(
        id="IncenseBurner",
        name="香炉",
        description="每6回合获得1层无实体。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.EVERY_N_TURNS, value=6, extra={"type": "intangible", "amount": 1}),
        ],
    ),
    "LizardTail": RelicDef(
        id="LizardTail",
        name="蜥蜴尾巴",
        description="即将死亡时治疗至50%最大生命值（生效一次）。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.ON_DEATH_SAVE, value=1, extra={"type": "revive_half_hp"}),
        ],
    ),
    "MagicFlower": RelicDef(
        id="MagicFlower",
        name="魔法花",
        description="战斗中的回复效果提升50%。",
        tier=RelicTier.RARE,
        character_class="IRONCLAD",
        effects=[
            RelicEffect(RelicEffectType.HEAL_MULTIPLY, value=2),
        ],
    ),
    "Mango": RelicDef(
        id="Mango",
        name="芒果",
        description="提升14点最大生命值。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.GAIN_MAX_HP, value=14),
        ],
    ),
    "OldCoin": RelicDef(
        id="OldCoin",
        name="古钱币",
        description="获得300金币。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.GAIN_GOLD, value=300),
        ],
    ),
    "PeacePipe": RelicDef(
        id="PeacePipe",
        name="宁静烟斗",
        description="可以在休息站点移除卡牌。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.REST_SITE_REMOVE, value=1),
        ],
    ),
    "Pocketwatch": RelicDef(
        id="Pocketwatch",
        name="怀表",
        description="一回合打出3张或更少卡牌时下回合额外抽3张。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.AT_FIRST_TURN_DRAW, value=3),
        ],
    ),
    "PrayerWheel": RelicDef(
        id="PrayerWheel",
        name="转经轮",
        description="普通敌人额外掉落1张卡牌奖励。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.CARD_REWARD, value=1),
        ],
    ),
    "Shovel": RelicDef(
        id="Shovel",
        name="铲子",
        description="可以在休息处挖掘遗物。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.REST_SITE_DIG, value=1),
        ],
    ),
    "StoneCalendar": RelicDef(
        id="StoneCalendar",
        name="历石",
        description="第7回合结束时对所有敌人造成52点伤害。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.EVERY_N_TURNS, value=7, extra={"type": "damage_all", "amount": 52}),
        ],
    ),
    "TheSpecimen": RelicDef(
        id="TheSpecimen",
        name="生物样本",
        description="敌人死亡时将其身上的毒层数转移给随机敌人。",
        tier=RelicTier.RARE,
        character_class="SILENT",
        effects=[
            RelicEffect(RelicEffectType.ON_ENEMY_DEATH_POISON_TRANSFER, value=0),
        ],
    ),
    "ThreadAndNeedle": RelicDef(
        id="ThreadAndNeedle",
        name="针线",
        description="战斗开始时获得4层多层护甲。",
        tier=RelicTier.RARE,
        character_class="SILENT",
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=4, extra={"type": "plated_armor"}),
        ],
    ),
    "Tingsha": RelicDef(
        id="Tingsha",
        name="铜钹",
        description="回合丢弃卡牌时对随机敌人造成3点伤害。",
        tier=RelicTier.RARE,
        character_class="SILENT",
        effects=[
            RelicEffect(RelicEffectType.ON_DISCARD, value=3, extra={"type": "damage_random"}),
        ],
    ),
    "Torii": RelicDef(
        id="Torii",
        name="鸟居",
        description="受到5点或更少未格挡攻击伤害时降至1。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.MODIFY_DAMAGE, value=1, extra={"type": "min_damage_receive", "max": 5}),
        ],
    ),
    "ToughBandages": RelicDef(
        id="ToughBandages",
        name="结实绷带",
        description="回合丢弃卡牌时获得3点格挡。",
        tier=RelicTier.RARE,
        character_class="SILENT",
        effects=[
            RelicEffect(RelicEffectType.ON_DISCARD, value=3, extra={"type": "block"}),
        ],
    ),
    "TungstenRod": RelicDef(
        id="TungstenRod",
        name="钨合金棍",
        description="每次失去生命时减少1点失去量。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.ON_HP_LOSS, value=1, extra={"type": "reduce_loss"}),
        ],
    ),
    "Turnip": RelicDef(
        id="Turnip",
        name="萝卜",
        description="不会再获得脆弱。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.IMMUNE_FRAIL, value=1),
        ],
    ),
    "UnceasingTop": RelicDef(
        id="UnceasingTop",
        name="不休陀螺",
        description="回合没有手牌时抽1张牌。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.EMPTY_HAND_DRAW, value=1),
        ],
    ),
    "WingedGreaves": RelicDef(
        id="WingedGreaves",
        name="羽翼之靴",
        description="选择下一层房间时有3次机会无视当前路线。",
        tier=RelicTier.RARE,
        effects=[
            RelicEffect(RelicEffectType.FREE_MOVEMENT, value=3),
        ],
    ),
}

BOSS_RELICS: dict[str, RelicDef] = {
    "Astrolabe": RelicDef(
        id="Astrolabe",
        name="星盘",
        description="拾取时选择并转化3张卡牌，然后升级它们。",
        tier=RelicTier.BOSS,
        effects=[
            RelicEffect(RelicEffectType.ON_PICKUP, value=0, extra={
                "type": "transform_3_cards",
                "upgrade": True
            }),
        ],
    ),
    "BlackBlood": RelicDef(
        id="BlackBlood",
        name="黑暗之血",
        description="替换燃血。战斗结束时治疗12点生命。",
        tier=RelicTier.BOSS,
        character_class="IRONCLAD",
        effects=[
            RelicEffect(RelicEffectType.REPLACE_STARTER_RELIC, value=0, extra={"replaced": "BurningBlood"}),
            RelicEffect(RelicEffectType.ON_VICTORY, value=12, target="player"),
        ],
    ),
    "BlackStar": RelicDef(
        id="BlackStar",
        name="黑星",
        description="精英现在掉落2件遗物。",
        tier=RelicTier.BOSS,
        effects=[
            RelicEffect(RelicEffectType.ELITE_REWARD_RELICS, value=2),
        ],
    ),
    "BustedCrown": RelicDef(
        id="BustedCrown",
        name="破碎金冠",
        description="每回合开始时获得1能量，卡牌奖励界面减少2张卡牌选择。",
        tier=RelicTier.BOSS,
        effects=[
            RelicEffect(RelicEffectType.START_WITH_ENERGY, value=1),
            RelicEffect(RelicEffectType.CARD_REWARD_REDUCE, value=2),
        ],
    ),
    "CallingBell": RelicDef(
        id="CallingBell",
        name="召唤铃铛",
        description="拾取时获得1张独特诅咒和3件遗物。",
        tier=RelicTier.BOSS,
        effects=[
            RelicEffect(RelicEffectType.ON_PICKUP, value=0, extra={
                "type": "gain_curse_and_relics",
                "curse": "Curse",
                "relic_count": 3
            }),
        ],
    ),
    "CoffeeDripper": RelicDef(
        id="CoffeeDripper",
        name="咖啡滤杯",
        description="每回合开始时获得1能量，休息站点无法休息。",
        tier=RelicTier.BOSS,
        effects=[
            RelicEffect(RelicEffectType.START_WITH_ENERGY, value=1),
            RelicEffect(RelicEffectType.REST_HEAL_DISABLED, value=1),
        ],
    ),
    "CursedKey": RelicDef(
        id="CursedKey",
        name="诅咒钥匙",
        description="每回合开始时获得1能量，打开非Boss宝箱获得诅咒。",
        tier=RelicTier.BOSS,
        effects=[
            RelicEffect(RelicEffectType.START_WITH_ENERGY, value=1),
            RelicEffect(RelicEffectType.ON_CHEST_OPEN, value=0, extra={
                "type": "add_curse",
                "exclude_curse": ["Ascender's Bane", "Curse of the Bell", "Necronomicurse", "Pride"]
            }),
        ],
    ),
    "Ectoplasm": RelicDef(
        id="Ectoplasm",
        name="灵体外质",
        description="每回合开始时获得1能量，无法获得金币。",
        tier=RelicTier.BOSS,
        effects=[
            RelicEffect(RelicEffectType.START_WITH_ENERGY, value=1),
            RelicEffect(RelicEffectType.GOLD_DISABLED, value=1),
        ],
    ),
    "EmptyCage": RelicDef(
        id="EmptyCage",
        name="空鸟笼",
        description="拾取时从牌组移除2张卡牌。",
        tier=RelicTier.BOSS,
        effects=[
            RelicEffect(RelicEffectType.REMOVE_CARDS_FROM_DECK, value=2, extra={
                "exclude_unremovable": True
            }),
        ],
    ),
    "FrozenCore": RelicDef(
        id="FrozenCore",
        name="冻结核心",
        description="替换裂纹核心。充能球槽为空时引导1个冰霜球。",
        tier=RelicTier.BOSS,
        character_class="DEFECT",
        effects=[
            RelicEffect(RelicEffectType.REPLACE_STARTER_RELIC, value=0, extra={"replaced": "CrackedCore"}),
            RelicEffect(RelicEffectType.AT_TURN_END_EMPTY_ORB, value=1, extra={"type": "channel_frost"}),
        ],
    ),
    "FusionHammer": RelicDef(
        id="FusionHammer",
        name="融合之锤",
        description="每回合开始时获得1能量，无法在休息站点锻造。",
        tier=RelicTier.BOSS,
        effects=[
            RelicEffect(RelicEffectType.START_WITH_ENERGY, value=1),
            RelicEffect(RelicEffectType.REST_SITE_FORGE_DISABLED, value=1),
        ],
    ),
    "HolyWater": RelicDef(
        id="HolyWater",
        name="圣水",
        description="替换清水。每场战斗开始时将3张 Miracle 加入手牌。",
        tier=RelicTier.BOSS,
        character_class="WATCHER",
        effects=[
            RelicEffect(RelicEffectType.REPLACE_STARTER_RELIC, value=0, extra={"replaced": "PureWater"}),
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=3, extra={"type": "miracle"}),
        ],
    ),
    "HoveringKite": RelicDef(
        id="HoveringKite",
        name="悬浮风筝",
        description="首次丢弃卡牌时获得1能量。",
        tier=RelicTier.BOSS,
        character_class="SILENT",
        effects=[
            RelicEffect(RelicEffectType.ON_FIRST_DISCARD_PER_TURN, value=1, extra={"type": "energy"}),
        ],
    ),
    "Inserter": RelicDef(
        id="Inserter",
        name="机械臂",
        description="每2回合获得1个充能球槽。",
        tier=RelicTier.BOSS,
        character_class="DEFECT",
        effects=[
            RelicEffect(RelicEffectType.EVERY_2_TURNS, value=1, extra={"type": "orb_slot"}),
        ],
    ),
    "MarkOfPain": RelicDef(
        id="MarkOfPain",
        name="痛楚印记",
        description="每回合开始时获得1能量，初始抽牌堆中有2张伤口。",
        tier=RelicTier.BOSS,
        character_class="IRONCLAD",
        effects=[
            RelicEffect(RelicEffectType.START_WITH_ENERGY, value=1),
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=2, extra={"type": "add_wound_to_draw", "timing": "after_first_draw"}),
        ],
    ),
    "NuclearBattery": RelicDef(
        id="NuclearBattery",
        name="核能电池",
        description="每场战斗开始时引导1个等离子球。",
        tier=RelicTier.BOSS,
        character_class="DEFECT",
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=1, extra={"type": "plasma_orb"}),
        ],
    ),
    "PandoraBox": RelicDef(
        id="PandoraBox",
        name="潘多拉魔盒",
        description="转化所有 Strike 和 Defend。",
        tier=RelicTier.BOSS,
        effects=[
            RelicEffect(RelicEffectType.ON_PICKUP, value=0, extra={
                "type": "transform_all_strikes_defends",
            }),
        ],
    ),
    "PhilosophersStone": RelicDef(
        id="PhilosophersStone",
        name="贤者之石",
        description="每回合开始时获得1能量，所有敌人开始时有1层力量。",
        tier=RelicTier.BOSS,
        effects=[
            RelicEffect(RelicEffectType.START_WITH_ENERGY, value=1),
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=1, extra={"type": "enemy_strength_start"}),
        ],
    ),
    "RingOfTheSerpent": RelicDef(
        id="RingOfTheSerpent",
        name="长蛇戒指",
        description="替换蛇戒。回合开始时额外抽1张牌。",
        tier=RelicTier.BOSS,
        character_class="SILENT",
        effects=[
            RelicEffect(RelicEffectType.REPLACE_STARTER_RELIC, value=0, extra={"replaced": "RingOfTheSnake"}),
            RelicEffect(RelicEffectType.AT_TURN_START, value=1, extra={"type": "draw_extra"}),
        ],
    ),
    "RunicCube": RelicDef(
        id="RunicCube",
        name="符文立方体",
        description="失去生命时抽1张牌。",
        tier=RelicTier.BOSS,
        character_class="IRONCLAD",
        effects=[
            RelicEffect(RelicEffectType.ON_HP_LOSS, value=1, extra={"type": "draw"}),
        ],
    ),
    "RunicDome": RelicDef(
        id="RunicDome",
        name="符文圆顶",
        description="每回合开始时获得1能量，无法看到敌人意图。",
        tier=RelicTier.BOSS,
        effects=[
            RelicEffect(RelicEffectType.START_WITH_ENERGY, value=1),
            RelicEffect(RelicEffectType.BLOCK_INTENT, value=1),
        ],
    ),
    "RunicPyramid": RelicDef(
        id="RunicPyramid",
        name="符文金字塔",
        description="回合结束时不再丢弃手牌。",
        tier=RelicTier.BOSS,
        effects=[
            RelicEffect(RelicEffectType.AT_TURN_END_NO_DISCARD, value=1),
        ],
    ),
    "SacredBark": RelicDef(
        id="SacredBark",
        name="神圣树皮",
        description="药水效果翻倍。",
        tier=RelicTier.BOSS,
        effects=[
            RelicEffect(RelicEffectType.DOUBLE_POTION_POTENCY, value=2, target="player"),
        ],
    ),
    "SlaverCollar": RelicDef(
        id="SlaverCollar",
        name="奴隶贩子颈环",
        description="Boss和精英战斗时回合开始获得能量。",
        tier=RelicTier.BOSS,
        effects=[
            RelicEffect(RelicEffectType.AT_BOSS_ELITE_START, value=1, extra={"type": "energy"}),
        ],
    ),
    "SneckoEye": RelicDef(
        id="SneckoEye",
        name="异蛇之眼",
        description="每回合额外抽2张牌，每场战斗开始时处于困惑状态。",
        tier=RelicTier.BOSS,
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=0, extra={"type": "confused"}),
            RelicEffect(RelicEffectType.LIMIT_CARDS_DRAW, value=2),
        ],
    ),
    "Sozu": RelicDef(
        id="Sozu",
        name="添水",
        description="每回合开始时获得1能量，无法再获得药水。",
        tier=RelicTier.BOSS,
        effects=[
            RelicEffect(RelicEffectType.START_WITH_ENERGY, value=1),
            RelicEffect(RelicEffectType.POTION_GAIN_DISABLED, value=1),
        ],
    ),
    "TinyHouse": RelicDef(
        id="TinyHouse",
        name="小屋子",
        description="获得1瓶药水，50金币，5点最大生命值，1张卡牌，升级1张随机卡牌。",
        tier=RelicTier.BOSS,
        effects=[
            RelicEffect(RelicEffectType.ON_PICKUP, value=0, extra={"type": "full_restore"}),
            RelicEffect(RelicEffectType.GAIN_GOLD, value=50),
            RelicEffect(RelicEffectType.GAIN_MAX_HP, value=5),
            RelicEffect(RelicEffectType.CARD_REWARD, value=1),
            RelicEffect(RelicEffectType.UPGRADE_RANDOM, value=1),
            RelicEffect(RelicEffectType.GAIN_POTION, value=1),
        ],
    ),
    "VelvetChoker": RelicDef(
        id="VelvetChoker",
        name="天鹅绒颈圈",
        description="每回合开始时获得1能量，每回合最多打6张牌。",
        tier=RelicTier.BOSS,
        effects=[
            RelicEffect(RelicEffectType.START_WITH_ENERGY, value=1),
            RelicEffect(RelicEffectType.LIMIT_CARDS_PLAY, value=6),
        ],
    ),
    "VioletLotus": RelicDef(
        id="VioletLotus",
        name="紫色莲花",
        description="退出平静时获得1额外能量。",
        tier=RelicTier.BOSS,
        character_class="WATCHER",
        effects=[
            RelicEffect(RelicEffectType.ON_EXIT_CALM_ENERGY, value=1),
        ],
    ),
    "WristBlade": RelicDef(
        id="WristBlade",
        name="袖剑",
        description="费用为0的攻击牌额外造成4点伤害。",
        tier=RelicTier.BOSS,
        character_class="SILENT",
        effects=[
            RelicEffect(RelicEffectType.ZERO_COST_ATTACK_BONUS_DAMAGE, value=4),
        ],
    ),
}

EVENT_RELICS: dict[str, RelicDef] = {
    "BloodyIdol": RelicDef(
        id="BloodyIdol",
        name="鲜血神像",
        description="获得金币时治疗5点生命。",
        tier=RelicTier.EVENT,
        effects=[
            RelicEffect(RelicEffectType.ON_GAIN_GOLD, value=5, extra={"type": "heal"}),
        ],
    ),
    "CultistMask": RelicDef(
        id="CultistMask",
        name="邪教徒头套",
        description="感觉更健谈。",
        tier=RelicTier.EVENT,
        effects=[
            RelicEffect(RelicEffectType.ON_PICKUP, value=0, extra={"type": "talkative"}),
        ],
    ),
    "Enchiridion": RelicDef(
        id="Enchiridion",
        name="英雄宝典",
        description="每场战斗开始时将1张随机力量牌加入手牌，该牌本回合费用为0。",
        tier=RelicTier.EVENT,
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=1, extra={"type": "free_power"}),
        ],
    ),
    "FaceOfCleric": RelicDef(
        id="FaceOfCleric",
        name="牧师的脸",
        description="每次战斗后提升1点最大生命值。",
        tier=RelicTier.EVENT,
        effects=[
            RelicEffect(RelicEffectType.ON_VICTORY, value=1, extra={"type": "max_hp"}),
        ],
    ),
    "GoldenIdol": RelicDef(
        id="GoldenIdol",
        name="金神像",
        description="敌人掉落金币增加25%。",
        tier=RelicTier.EVENT,
        effects=[
            RelicEffect(RelicEffectType.GOLD_MULTIPLY, value=25),
        ],
    ),
    "GremlinMask": RelicDef(
        id="GremlinMask",
        name="地精容貌",
        description="每场战斗开始时获得1层虚弱。",
        tier=RelicTier.EVENT,
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=1, target="player", extra={"type": "weak"}),
        ],
    ),
    "MarkOfTheBloom": RelicDef(
        id="MarkOfTheBloom",
        name="绽放印记",
        description="无法再获得治疗。",
        tier=RelicTier.EVENT,
        effects=[
            RelicEffect(RelicEffectType.CANT_HEAL, value=1),
        ],
    ),
    "MutagenicStrength": RelicDef(
        id="MutagenicStrength",
        name="突变之力",
        description="战斗开始时获得3层力量，战斗结束时失去。",
        tier=RelicTier.EVENT,
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=3, extra={"type": "strength_lost"}),
        ],
    ),
    "NlothsGift": RelicDef(
        id="NlothsGift",
        name="恩洛斯的礼物",
        description="怪物奖励获得稀有卡牌的概率翻三倍。",
        tier=RelicTier.EVENT,
        effects=[
            RelicEffect(RelicEffectType.CHANGE_RARE_CHANCE, value=3),
        ],
    ),
    "NlothsMask": RelicDef(
        id="NlothsMask",
        name="恩洛斯的饥饿的脸",
        description="下一个非Boss宝箱为空。",
        tier=RelicTier.EVENT,
        effects=[
            RelicEffect(RelicEffectType.ON_CHEST_OPEN, value=0, extra={"type": "empty_chest_next"}),
        ],
    ),
    "Necronomicon": RelicDef(
        id="Necronomicon",
        name="死灵之书",
        description="每回合第一张费用为2或更多的攻击牌打两次，拾取时获得诅咒。",
        tier=RelicTier.EVENT,
        effects=[
            RelicEffect(RelicEffectType.FIRST_ATTACK_TWICE, value=1),
            RelicEffect(RelicEffectType.START_WITH_CURSE, value=1, extra={"type": "curse"}),
        ],
    ),
    "NeowsLament": RelicDef(
        id="NeowsLament",
        name="涅奥的悲恸",
        description="前3场战斗敌人只有1点生命。",
        tier=RelicTier.EVENT,
        effects=[
            RelicEffect(RelicEffectType.FIRST_COMBAT_HP_ONE, value=3),
        ],
    ),
    "NilrysCodex": RelicDef(
        id="NilrysCodex",
        name="尼利的宝典",
        description="回合结束时可以从3张随机卡牌中选择1张洗入抽牌堆。",
        tier=RelicTier.EVENT,
        effects=[
            RelicEffect(RelicEffectType.CARD_CHOICE_THREE, value=1),
        ],
    ),
    "OddMushroom": RelicDef(
        id="OddMushroom",
        name="奇怪蘑菇",
        description="易伤时受到25%更多伤害（而非50%）。",
        tier=RelicTier.EVENT,
        effects=[
            RelicEffect(RelicEffectType.MODIFY_VULNERABLE, value=25, extra={"type": "extra_damage_percent"}),
        ],
    ),
    "RedMask": RelicDef(
        id="RedMask",
        name="红面具",
        description="每场战斗开始时对所有敌人施加1层虚弱。",
        tier=RelicTier.EVENT,
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=1, target="all_enemies", extra={"type": "weak"}),
        ],
    ),
    "SpiritPoop": RelicDef(
        id="SpiritPoop",
        name="精灵便便",
        description="令人不快的。",
        tier=RelicTier.EVENT,
        effects=[
            RelicEffect(RelicEffectType.ON_PICKUP, value=0, extra={"type": "unpleasant"}),
        ],
    ),
    "SsserpentHead": RelicDef(
        id="SsserpentHead",
        name="蛇的头",
        description="进入?房间时获得50金币。",
        tier=RelicTier.EVENT,
        effects=[
            RelicEffect(RelicEffectType.ON_QUESTION_ROOM, value=50, extra={"type": "gold"}),
        ],
    ),
    "WarpedTongs": RelicDef(
        id="WarpedTongs",
        name="弯曲铁钳",
        description="回合开始时升级手牌中1张随机卡牌。",
        tier=RelicTier.EVENT,
        effects=[
            RelicEffect(RelicEffectType.AT_TURN_START, value=1, extra={"type": "upgrade_random"}),
        ],
    ),
}

SHOP_RELICS: dict[str, RelicDef] = {
    "Brimstone": RelicDef(
        id="Brimstone",
        name="硫磺",
        description="回合开始时获得2层力量，所有敌人获得1层力量。",
        tier=RelicTier.SHOP,
        character_class="IRONCLAD",
        effects=[
            RelicEffect(RelicEffectType.AT_TURN_START, value=2, extra={"type": "strength"}),
            RelicEffect(RelicEffectType.AT_TURN_START, value=1, target="all_enemies", extra={"type": "strength"}),
        ],
    ),
    "Cauldron": RelicDef(
        id="Cauldron",
        name="大锅",
        description="获得时酿造5瓶随机药水。",
        tier=RelicTier.SHOP,
        effects=[
            RelicEffect(RelicEffectType.ON_PICKUP, value=5, extra={"type": "brew_potions"}),
        ],
    ),
    "ChemicalX": RelicDef(
        id="ChemicalX",
        name="化学物X",
        description="费用X的卡牌效果增加2。",
        tier=RelicTier.SHOP,
        effects=[
            RelicEffect(RelicEffectType.ON_PICKUP, value=0, extra={"type": "x_cost_bonus"}),
        ],
    ),
    "ClockworkSouvenir": RelicDef(
        id="ClockworkSouvenir",
        name="齿轮工艺品",
        description="每场战斗开始时获得1层人工制品。",
        tier=RelicTier.SHOP,
        effects=[
            RelicEffect(RelicEffectType.ARTIFACT_START, value=1),
        ],
    ),
    "DollysMirror": RelicDef(
        id="DollysMirror",
        name="多利之镜",
        description="拾取时获得牌组中1张卡的额外复制。",
        tier=RelicTier.SHOP,
        effects=[
            RelicEffect(RelicEffectType.CARD_COPY, value=1),
        ],
    ),
    "FrozenEye": RelicDef(
        id="FrozenEye",
        name="冻结之眼",
        description="查看抽牌堆时卡牌按顺序显示。",
        tier=RelicTier.SHOP,
        effects=[
            RelicEffect(RelicEffectType.ON_PICKUP, value=0, extra={"type": "ordered_draw"}),
        ],
    ),
    "HandDrill": RelicDef(
        id="HandDrill",
        name="手钻",
        description="打破敌人格挡时施加2层易伤。",
        tier=RelicTier.SHOP,
        effects=[
            RelicEffect(RelicEffectType.ON_DAMAGE, value=2, extra={"type": "vulnerable"}),
        ],
    ),
    "LeesWaffle": RelicDef(
        id="LeesWaffle",
        name="李家华夫饼",
        description="提升7点最大生命值并治疗所有生命。",
        tier=RelicTier.SHOP,
        effects=[
            RelicEffect(RelicEffectType.ON_PICKUP, value=7, extra={"type": "max_hp_and_heal"}),
        ],
    ),
    "MedicalKit": RelicDef(
        id="MedicalKit",
        name="医药箱",
        description="状态牌现在可以被打出，打出状态牌会消耗该牌。",
        tier=RelicTier.SHOP,
        effects=[
            RelicEffect(RelicEffectType.ON_PICKUP, value=0, extra={"type": "status_playable"}),
        ],
    ),
    "Melange": RelicDef(
        id="Melange",
        name="美琅脂",
        description="洗牌时预测3。",
        tier=RelicTier.SHOP,
        character_class="WATCHER",
        effects=[
            RelicEffect(RelicEffectType.SCRY_ON_SHUFFLE, value=3),
        ],
    ),
    "MembershipCard": RelicDef(
        id="MembershipCard",
        name="会员卡",
        description="所有商品5折。",
        tier=RelicTier.SHOP,
        effects=[
            RelicEffect(RelicEffectType.SHOP_PRICE_MODIFIER, value=-50),
        ],
    ),
    "OrangePellets": RelicDef(
        id="OrangePellets",
        name="橙色药丸",
        description="同一回合打出力量、攻击和技能各1张时移除所有减益。",
        tier=RelicTier.SHOP,
        effects=[
            RelicEffect(RelicEffectType.DEBUFF_CLEAR, value=1),
        ],
    ),
    "Orrery": RelicDef(
        id="Orrery",
        name="星系仪",
        description="选择并向牌组添加5张卡牌。",
        tier=RelicTier.SHOP,
        effects=[
            RelicEffect(RelicEffectType.ON_PICKUP, value=5, extra={"type": "add_cards"}),
        ],
    ),
    "PrismaticShard": RelicDef(
        id="PrismaticShard",
        name="棱镜碎片",
        description="战斗奖励界面现在包含无色卡和其他颜色的卡。",
        tier=RelicTier.SHOP,
        effects=[
            RelicEffect(RelicEffectType.CARD_REWARD_MODIFIER, value=0, extra={"type": "add_other_class_cards"}),
        ],
    ),
    "RunicCapacitor": RelicDef(
        id="RunicCapacitor",
        name="符文电容器",
        description="额外获得3个充能球槽。",
        tier=RelicTier.SHOP,
        character_class="DEFECT",
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=3, extra={"type": "orb_slots"}),
        ],
    ),
    "Sling": RelicDef(
        id="Sling",
        name="勇气投石索",
        description="精英战斗开始时获得2层力量。",
        tier=RelicTier.SHOP,
        effects=[
            RelicEffect(RelicEffectType.AT_BOSS_ELITE_START, value=2, extra={"type": "strength"}),
        ],
    ),
    "StrangeSpoon": RelicDef(
        id="StrangeSpoon",
        name="奇怪的勺子",
        description="消耗的卡牌有50%概率改为丢弃。",
        tier=RelicTier.SHOP,
        effects=[
            RelicEffect(RelicEffectType.ON_PICKUP, value=0, extra={"type": "exhaust_chance_50"}),
        ],
    ),
    "TheAbacus": RelicDef(
        id="TheAbacus",
        name="算盘",
        description="洗牌时获得6点格挡。",
        tier=RelicTier.SHOP,
        effects=[
            RelicEffect(RelicEffectType.ON_SHUFFLE, value=6, extra={"type": "block"}),
        ],
    ),
    "Toolbox": RelicDef(
        id="Toolbox",
        name="工具箱",
        description="每场战斗开始时从3张随机无色卡中选择1张加入手牌。",
        tier=RelicTier.SHOP,
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=0, extra={"type": "add_colorless_card"}),
        ],
    ),
    "TwistedFunnel": RelicDef(
        id="TwistedFunnel",
        name="扭曲漏斗",
        description="每场战斗开始时对所有敌人施加4层毒。",
        tier=RelicTier.SHOP,
        character_class="SILENT",
        effects=[
            RelicEffect(RelicEffectType.AT_BATTLE_START, value=4, target="all_enemies", extra={"type": "poison"}),
        ],
    ),
}

SPECIAL_RELICS: dict[str, RelicDef] = {
    "Circlet": RelicDef(
        id="Circlet",
        name="头环",
        description="尽可能多地收集。",
        tier=RelicTier.SPECIAL,
        effects=[
            RelicEffect(RelicEffectType.ON_PICKUP, value=0, extra={"type": "collect"}),
        ],
    ),
}

ALL_STARTER_RELICS: dict[str, RelicDef] = {}
ALL_STARTER_RELICS.update(IRONCLAD_STARTER_RELICS)
ALL_STARTER_RELICS.update(DEFECT_STARTER_RELICS)
ALL_STARTER_RELICS.update(WATCHER_STARTER_RELICS)
ALL_STARTER_RELICS.update(SILENT_STARTER_RELICS)

ALL_RELICS: dict[str, RelicDef] = {}
ALL_RELICS.update(ALL_STARTER_RELICS)
ALL_RELICS.update(COMMON_RELICS)
for k, v in UNCOMMON_RELICS.items():
    if k not in ALL_RELICS:
        ALL_RELICS[k] = v
for k, v in RARE_RELICS.items():
    if k not in ALL_RELICS:
        ALL_RELICS[k] = v
for k, v in BOSS_RELICS.items():
    if k not in ALL_RELICS:
        ALL_RELICS[k] = v
for k, v in EVENT_RELICS.items():
    if k not in ALL_RELICS:
        ALL_RELICS[k] = v
for k, v in SHOP_RELICS.items():
    if k not in ALL_RELICS:
        ALL_RELICS[k] = v
for k, v in SPECIAL_RELICS.items():
    if k not in ALL_RELICS:
        ALL_RELICS[k] = v

ALL_RELICS["JuzuBracelet"].description = "事件房间不再遭遇普通敌人。"
ALL_RELICS["SsserpentHead"].description = "进入事件房间时获得 50 金币。"
ALL_RELICS["TinyChest"].description = "每 4 个事件房间变成宝藏房间。"


def get_relic_pool(tier: RelicTier) -> list[RelicDef]:
    tier_map = {
        RelicTier.COMMON: COMMON_RELICS,
        RelicTier.UNCOMMON: UNCOMMON_RELICS,
        RelicTier.RARE: RARE_RELICS,
        RelicTier.BOSS: BOSS_RELICS,
        RelicTier.SHOP: SHOP_RELICS,
        RelicTier.EVENT: EVENT_RELICS,
    }
    return list(tier_map.get(tier, {}).values())


def get_starter_relic_pool(character_class: str) -> list[RelicDef]:
    class_map = {
        "IRONCLAD": IRONCLAD_STARTER_RELICS,
        "DEFECT": DEFECT_STARTER_RELICS,
        "WATCHER": WATCHER_STARTER_RELICS,
        "SILENT": SILENT_STARTER_RELICS,
    }
    return list(class_map.get(character_class, {}).values())


RELIC_ID_ALIASES: dict[str, str] = {
    "Akabeko": "赤牛",
    "Anchor": "铁锚",
    "AncientTeaSet": "古茶具套装",
    "ArtOfWar": "孙子兵法",
    "BagOfMarbles": "弹珠袋",
    "BagOfPreparation": "准备背包",
    "BloodVial": "小血瓶",
    "BronzeScales": "铜制鳞片",
    "CentennialPuzzle": "百年积木",
    "CeramicFish": "陶瓷小鱼",
    "Damaru": "手摇鼓",
    "DataDisk": "数据磁盘",
    "DreamCatcher": "捕梦网",
    "HappyFlower": "开心小花",
    "JuzuBracelet": "佛珠手链",
    "Lantern": "灯笼",
    "MawBank": "巨口储蓄罐",
    "MealTicket": "餐券",
    "Nunchaku": "双节棍",
    "OddlySmoothStone": "意外光滑的石头",
    "Omamori": "御守",
    "Orichalcum": "奥利哈钢",
    "PenNib": "钢笔尖",
    "PotionBelt": "药水腰带",
    "PreservedInsect": "昆虫标本",
    "RedSkull": "红头骨",
    "RegalPillow": "皇家枕头",
    "SmilingMask": "微笑面具",
    "SneckoSkull": "异蛇头骨",
    "Strawberry": "草莓",
    "TheBoot": "发条靴",
    "TinyChest": "小宝箱",
    "ToyOrnithopter": "玩具扑翼飞机",
    "Vajra": "金刚杵",
    "WarPaint": "战纹涂料",
    "Whetstone": "磨刀石",
    "BlueCandle": "蓝蜡烛",
    "BottledFlame": "瓶装火焰",
    "BottledLightning": "瓶装闪电",
    "BottledTornado": "瓶装旋风",
    "DarkstonePeriapt": "黑石护符",
    "Duality": "两仪",
    "EternalFeather": "永恒羽毛",
    "FrozenEgg": "冻结之蛋",
    "GoldPlatedCables": "镀金缆线",
    "GremlinHorn": "地精之角",
    "HornCleat": "船夹板",
    "InkBottle": "墨水瓶",
    "Kunai": "苦无",
    "LetterOpener": "开信刀",
    "Matryoshka": "套娃",
    "MeatOnTheBone": "带骨肉",
    "MercuryHourglass": "水银沙漏",
    "MoltenEgg": "熔火之蛋",
    "MummifiedHand": "干瘪之手",
    "NinjaScroll": "忍术卷轴",
    "OrnamentalFan": "精致折扇",
    "Pantograph": "缩放仪",
    "PaperCrane": "纸鹤",
    "PaperFrog": "纸蛙",
    "Pear": "梨子",
    "QuestionCard": "问号牌",
    "SelfFormingClay": "自成型黏土",
    "Shuriken": "手里剑",
    "SingingBowl": "颂钵",
    "StrikeDummy": "打击木偶",
    "Sundial": "日晷",
    "SymbioticVirus": "共生病毒",
    "TeardropLocket": "泪滴吊坠盒",
    "TheCourier": "送货员",
    "ToxicEgg": "毒素之蛋",
    "WhiteBeastStatue": "白兽雕像",
    "BirdFacedUrn": "鸟面瓮",
    "Calipers": "外卡钳",
    "CaptainWheel": "舵盘",
    "ChampionBelt": "冠军腰带",
    "CharonsAshes": "卡戎之灰",
    "CloakClasp": "斗篷扣",
    "DeadBranch": "枯木树枝",
    "枯木树枝": "DeadBranch",
    "DuVuDoll": "毒巫娃娃",
    "毒巫娃娃": "DuVuDoll",
    "EmotionChip": "情感芯片",
    "FossilizedHelix": "螺类化石",
    "GamblingChip": "赌博筹码",
    "Ginger": "生姜",
    "Girya": "壶铃",
    "GoldenEye": "黄金眼",
    "IceCream": "冰淇淋",
    "IncenseBurner": "香炉",
    "香炉": "香炉",
    "LizardTail": "蜥蜴尾巴",
    "MagicFlower": "魔法花",
    "Mango": "芒果",
    "OldCoin": "古钱币",
    "PeacePipe": "宁静烟斗",
    "Pocketwatch": "怀表",
    "PrayerWheel": "转经轮",
    "Shovel": "铲子",
    "StoneCalendar": "历石",
    "TheSpecimen": "生物样本",
    "ThreadAndNeedle": "针线",
    "Tingsha": "铜钹",
    "Torii": "鸟居",
    "ToughBandages": "结实绷带",
    "TungstenRod": "钨合金棍",
    "Turnip": "萝卜",
    "UnceasingTop": "不休陀螺",
    "WingedGreaves": "羽翼之靴",
    "Astrolabe": "星盘",
    "BlackBlood": "黑暗之血",
    "BlackStar": "黑星",
    "BustedCrown": "破碎金冠",
    "CallingBell": "召唤铃铛",
    "CoffeeDripper": "咖啡滤杯",
    "CursedKey": "诅咒钥匙",
    "Ectoplasm": "灵体外质",
    "EmptyCage": "空鸟笼",
    "FrozenCore": "冻结核心",
    "FusionHammer": "融合之锤",
    "HolyWater": "圣水",
    "HoveringKite": "悬浮风筝",
    "Inserter": "机械臂",
    "MarkOfPain": "痛楚印记",
    "NuclearBattery": "核能电池",
    "核电池": "NuclearBattery",
    "PandoraBox": "潘多拉魔盒",
    "PhilosophersStone": "贤者之石",
    "RingOfTheSerpent": "长蛇戒指",
    "RunicCube": "符文立方体",
    "RunicDome": "符文圆顶",
    "RunicPyramid": "符文金字塔",
    "SacredBark": "神圣树皮",
    "SlaverCollar": "奴隶贩子颈环",
    "SneckoEye": "异蛇之眼",
    "斯内克之眼": "SneckoEye",
    "Sozu": "添水",
    "TinyHouse": "小屋子",
    "VelvetChoker": "天鹅绒颈圈",
    "VioletLotus": "紫色莲花",
    "WristBlade": "袖剑",
    "Circlet": "头环",
    "BloodyIdol": "鲜血神像",
    "CultistMask": "邪教徒头套",
    "Enchiridion": "英雄宝典",
    "FaceOfCleric": "牧师的脸",
    "GoldenIdol": "金神像",
    "GremlinMask": "地精容貌",
    "MarkOfTheBloom": "绽放印记",
    "MutagenicStrength": "突变之力",
    "NlothsGift": "恩洛斯的礼物",
    "NlothsMask": "恩洛斯的饥饿的脸",
    "Necronomicon": "死灵之书",
    "NeowsLament": "涅奥的悲恸",
    "NilrysCodex": "尼利的宝典",
    "OddMushroom": "奇怪蘑菇",
    "RedMask": "红面具",
    "SpiritPoop": "精灵便便",
    "SsserpentHead": "蛇的头",
    "WarpedTongs": "弯曲铁钳",
    "Brimstone": "硫磺",
    "Cauldron": "大锅",
    "ChemicalX": "化学物X",
    "ClockworkSouvenir": "齿轮工艺品",
    "DollysMirror": "多利之镜",
    "FrozenEye": "冻结之眼",
    "HandDrill": "手钻",
    "LeesWaffle": "李家华夫饼",
    "MedicalKit": "医药箱",
    "Melange": "美琅脂",
    "MembershipCard": "会员卡",
    "OrangePellets": "橙色药丸",
    "Orrery": "星系仪",
    "PrismaticShard": "棱镜碎片",
    "RunicCapacitor": "符文电容器",
    "Sling": "勇气投石索",
    "StrangeSpoon": "奇怪的勺子",
    "TheAbacus": "算盘",
    "Toolbox": "工具箱",
    "TwistedFunnel": "扭曲漏斗",
    "BurningBlood": "燃烧之血",
    "CrackedCore": "破损核心",
    "PureWater": "至纯之水",
    "RingOfTheSnake": "蛇之戒指",
}

def _normalize_relic_lookup_key(value: str | None) -> str:
    return str(value or "").replace(" ", "").replace("_", "").lower()


def get_relic_by_id(relic_id: str) -> RelicDef | None:
    normalized_target = _normalize_relic_lookup_key(relic_id)
    if relic_id in ALL_RELICS:
        return ALL_RELICS.get(relic_id)
    for relic in ALL_RELICS.values():
        if relic.name == relic_id:
            return relic
    for relic in ALL_RELICS.values():
        if (
            _normalize_relic_lookup_key(relic.id) == normalized_target
            or _normalize_relic_lookup_key(relic.name) == normalized_target
        ):
            return relic
    if relic_id in RELIC_ID_ALIASES:
        mapped_id = RELIC_ID_ALIASES[relic_id]
        if mapped_id in ALL_RELICS:
            return ALL_RELICS[mapped_id]
        for relic in ALL_RELICS.values():
            if relic.name == mapped_id:
                return relic
    for alias_id, mapped_id in RELIC_ID_ALIASES.items():
        if _normalize_relic_lookup_key(alias_id) != normalized_target:
            continue
        if mapped_id in ALL_RELICS:
            return ALL_RELICS[mapped_id]
        for relic in ALL_RELICS.values():
            if relic.name == mapped_id:
                return relic
    for eng_id, cn_name in RELIC_ID_ALIASES.items():
        if cn_name == relic_id and eng_id in ALL_RELICS:
            return ALL_RELICS[eng_id]
    return None


def get_random_relic_by_tier(tier_str: str, rng=None) -> str | None:
    """Get a random relic ID from the given tier.

    Args:
        tier_str: "COMMON", "UNCOMMON", "RARE", "BOSS", "EVENT", "SHOP"
        rng: Optional MutableRNG for seeded selection
    Returns:
        Relic ID string, or None if pool is empty
    """
    tier_map = {
        "COMMON": RelicTier.COMMON,
        "UNCOMMON": RelicTier.UNCOMMON,
        "RARE": RelicTier.RARE,
        "BOSS": RelicTier.BOSS,
        "EVENT": RelicTier.EVENT,
        "SHOP": RelicTier.SHOP,
    }
    tier = tier_map.get(tier_str)
    if tier is None:
        return None
    pool = get_relic_pool(tier)
    if not pool:
        return None
    if rng is not None:
        idx = rng.random_int(len(pool) - 1)
    else:
        import random
        idx = random.randint(0, len(pool) - 1)
    return pool[idx].id


class RelicRarityProbability:
    COMMON_CHANCE = 50
    UNCOMMON_CHANCE = 33
    RARE_CHANCE = 17

    CHEST_COMMON_CHANCE = 49
    CHEST_UNCOMMON_CHANCE = 42
    CHEST_RARE_CHANCE = 9


def roll_relic_rarity(rng=None, source: str = "default") -> RelicTier:
    """Roll for relic rarity based on source.

    Args:
        rng: Optional MutableRNG for seeded selection
        source: "default" (3:2:1 ratio) or "chest" (49:42:9 ratio)

    Returns:
        RelicTier based on rolled probability
    """
    if source == "chest":
        common_cap = RelicRarityProbability.CHEST_COMMON_CHANCE
        uncommon_cap = common_cap + RelicRarityProbability.CHEST_UNCOMMON_CHANCE
    else:
        common_cap = RelicRarityProbability.COMMON_CHANCE
        uncommon_cap = common_cap + RelicRarityProbability.UNCOMMON_CHANCE

    if rng is not None:
        roll = rng.random_int(99)
    else:
        import random
        roll = random.randint(0, 99)

    if roll < common_cap:
        return RelicTier.COMMON
    elif roll < uncommon_cap:
        return RelicTier.UNCOMMON
    else:
        return RelicTier.RARE
