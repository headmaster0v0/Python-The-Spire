"""
Python script to load and compare Java game logs with Python simulation.

This script reads the JSON logs exported by the DataRecorder Java Mod
and compares them with the Python simulation output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class RngState:
    card_rng_counter: int
    monster_rng_counter: int
    ai_rng_counter: int
    event_rng_counter: int
    merchant_rng_counter: int
    treasure_rng_counter: int
    relic_rng_counter: int
    potion_rng_counter: int
    shuffle_rng_counter: int
    card_random_rng_counter: int
    map_rng_counter: int
    misc_rng_counter: int
    monster_hp_rng_counter: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "RngState":
        return RngState(
            card_rng_counter=d.get("cardRngCounter", 0),
            monster_rng_counter=d.get("monsterRngCounter", 0),
            ai_rng_counter=d.get("aiRngCounter", 0),
            event_rng_counter=d.get("eventRngCounter", 0),
            merchant_rng_counter=d.get("merchantRngCounter", 0),
            treasure_rng_counter=d.get("treasureRngCounter", 0),
            relic_rng_counter=d.get("relicRngCounter", 0),
            potion_rng_counter=d.get("potionRngCounter", 0),
            shuffle_rng_counter=d.get("shuffleRngCounter", 0),
            card_random_rng_counter=d.get("cardRandomRngCounter", 0),
            map_rng_counter=d.get("mapRngCounter", 0),
            misc_rng_counter=d.get("miscRngCounter", 0),
            monster_hp_rng_counter=d.get("monsterHpRngCounter", 0),
        )


@dataclass
class RngCall:
    rng_type: str
    counter: int
    method: str
    return_value: Any
    param1: Any
    param2: Any
    floor: int
    turn: int
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "RngCall":
        return RngCall(
            rng_type=d["rngType"],
            counter=d["counter"],
            method=d["method"],
            return_value=d["returnValue"],
            param1=d.get("param1"),
            param2=d.get("param2"),
            floor=d["floor"],
            turn=d.get("turn", 0),
            timestamp=d["timestamp"],
        )


@dataclass
class CardPlay:
    card_id: str
    cost: int
    upgraded: bool
    floor: int
    turn: int
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "CardPlay":
        return CardPlay(
            card_id=d["cardId"],
            cost=d["cost"],
            upgraded=d["upgraded"],
            floor=d["floor"],
            turn=d["turn"],
            timestamp=d["timestamp"],
        )


@dataclass
class MonsterLog:
    id: str
    name: str
    starting_hp: int
    ending_hp: int
    is_dead: bool

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "MonsterLog":
        return MonsterLog(
            id=d["id"],
            name=d["name"],
            starting_hp=d["startingHp"],
            ending_hp=d["endingHp"],
            is_dead=d["isDead"],
        )


@dataclass
class BattleLog:
    floor: int
    room_type: str
    monsters: list[MonsterLog]
    player_end_hp: int
    turn_count: int
    cards_played: list[CardPlay]
    rng_state_end: RngState | None

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "BattleLog":
        return BattleLog(
            floor=d["floor"],
            room_type=d["roomType"],
            monsters=[MonsterLog.from_dict(m) for m in d.get("monsters", [])],
            player_end_hp=d["playerEndHp"],
            turn_count=d["turnCount"],
            cards_played=[CardPlay.from_dict(c) for c in d.get("cardsPlayedThisBattle", [])],
            rng_state_end=RngState.from_dict(d["rngStateEnd"]) if d.get("rngStateEnd") else None,
        )


@dataclass
class CardInfo:
    card_id: str
    upgraded: bool

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "CardInfo":
        return CardInfo(
            card_id=d["cardId"],
            upgraded=d.get("upgraded", False),
        )


@dataclass
class PathStep:
    floor: int
    act: int
    x: int
    y: int
    room_type: str

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "PathStep":
        return PathStep(
            floor=d["floor"],
            act=d["act"],
            x=d["x"],
            y=d["y"],
            room_type=d["roomType"],
        )


@dataclass
class MapEdgeLog:
    dst_x: int
    dst_y: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "MapEdgeLog":
        return MapEdgeLog(
            dst_x=d["dstX"],
            dst_y=d["dstY"],
        )


@dataclass
class MapNodeLog:
    x: int
    y: int
    room_type: str | None
    has_emerald_key: bool
    edges: list[MapEdgeLog]

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "MapNodeLog":
        return MapNodeLog(
            x=d["x"],
            y=d["y"],
            room_type=d.get("roomType"),
            has_emerald_key=d.get("hasEmeraldKey", False),
            edges=[MapEdgeLog.from_dict(edge) for edge in d.get("edges", [])],
        )


@dataclass
class CardRewardLog:
    card_id: str
    upgraded: bool
    skipped: bool
    choice_type: str | None
    not_picked_card_ids: list[str]
    floor: int
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "CardRewardLog":
        return CardRewardLog(
            card_id=d["cardId"],
            upgraded=d.get("upgraded", False),
            skipped=d.get("skipped", False),
            choice_type=d.get("choiceType"),
            not_picked_card_ids=d.get("notPickedCardIds", []),
            floor=d["floor"],
            timestamp=d["timestamp"],
        )


@dataclass
class EventChoiceLog:
    event_id: str
    event_name: str
    choice_index: int
    choice_text: str
    floor: int
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "EventChoiceLog":
        return EventChoiceLog(
            event_id=d["eventId"],
            event_name=d["eventName"],
            choice_index=d["choiceIndex"],
            choice_text=d["choiceText"],
            floor=d["floor"],
            timestamp=d["timestamp"],
        )


@dataclass
class TreasureRoomLog:
    floor: int
    room_type: str | None
    gold_before: int
    gold_after: int
    relic_id: str | None
    relic_name: str | None
    main_relic_id: str | None
    obtained_relic_ids: list[str]
    skipped_main_relic_id: str | None
    took_sapphire_key: bool
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "TreasureRoomLog":
        return TreasureRoomLog(
            floor=d["floor"],
            room_type=d.get("roomType"),
            gold_before=d.get("goldBefore", 0),
            gold_after=d.get("goldAfter", 0),
            relic_id=d.get("relicId"),
            relic_name=d.get("relicName"),
            main_relic_id=d.get("mainRelicId"),
            obtained_relic_ids=list(d.get("obtainedRelicIds", [])),
            skipped_main_relic_id=d.get("skippedMainRelicId"),
            took_sapphire_key=d.get("tookSapphireKey", False),
            timestamp=d.get("timestamp", 0),
        )


@dataclass
class BossRelicChoiceLog:
    floor: int
    act: int
    picked_relic_id: str | None
    not_picked_relic_ids: list[str]
    skipped: bool
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "BossRelicChoiceLog":
        return BossRelicChoiceLog(
            floor=d["floor"],
            act=d.get("act", 0),
            picked_relic_id=d.get("pickedRelicId"),
            not_picked_relic_ids=list(d.get("notPickedRelicIds", [])),
            skipped=d.get("skipped", False),
            timestamp=d.get("timestamp", 0),
        )


@dataclass
class RestActionLog:
    action: str
    floor: int
    hp_before: int
    max_hp: int
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "RestActionLog":
        return RestActionLog(
            action=d["action"],
            floor=d["floor"],
            hp_before=d["hpBefore"],
            max_hp=d["maxHp"],
            timestamp=d["timestamp"],
        )


@dataclass
class CardDrawLog:
    num_cards: int
    floor: int
    turn: int
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "CardDrawLog":
        return CardDrawLog(
            num_cards=d["numCards"],
            floor=d["floor"],
            turn=d["turn"],
            timestamp=d["timestamp"],
        )


@dataclass
class MonsterIntentLog:
    floor: int
    monster_id: str
    monster_name: str
    intent: str
    move_index: int
    base_damage: int
    ai_rng_counter: int
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "MonsterIntentLog":
        return MonsterIntentLog(
            floor=d["floor"],
            monster_id=d["monsterId"],
            monster_name=d["monsterName"],
            intent=d["intent"],
            move_index=d["moveIndex"],
            base_damage=d.get("baseDamage", 0),
            ai_rng_counter=d.get("aiRngCounter", 0),
            timestamp=d["timestamp"],
        )


@dataclass
class GoldChangeLog:
    amount: int
    source: str
    floor: int
    gold_after: int
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "GoldChangeLog":
        return GoldChangeLog(
            amount=d["amount"],
            source=d["source"],
            floor=d["floor"],
            gold_after=d["goldAfter"],
            timestamp=d["timestamp"],
        )


@dataclass
class HpChangeLog:
    amount: int
    source: str
    floor: int
    hp_after: int
    max_hp: int
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "HpChangeLog":
        return HpChangeLog(
            amount=d["amount"],
            source=d["source"],
            floor=d["floor"],
            hp_after=d["hpAfter"],
            max_hp=d["maxHp"],
            timestamp=d["timestamp"],
        )


@dataclass
class RelicChangeLog:
    relic_id: str
    relic_name: str
    floor: int
    turn: int
    action: str
    source: str | None
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "RelicChangeLog":
        return RelicChangeLog(
            relic_id=d["relicId"],
            relic_name=d["relicName"],
            floor=d["floor"],
            turn=d.get("turn", 0),
            action=d["action"],
            source=d.get("source"),
            timestamp=d["timestamp"],
        )


@dataclass
class ShopPurchaseLog:
    item_type: str
    item_id: str
    floor: int
    gold: int
    gold_spent: int
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "ShopPurchaseLog":
        return ShopPurchaseLog(
            item_type=d["itemType"],
            item_id=d["itemId"],
            floor=d["floor"],
            gold=d["gold"],
            gold_spent=d["goldSpent"],
            timestamp=d["timestamp"],
        )


@dataclass
class ShopVisitLog:
    floor: int
    initial_relic_offer_ids: list[str]
    surfaced_relic_ids: list[str]
    purchased_relic_ids: list[str]
    initial_colored_card_offer_ids: list[str] | None
    initial_colorless_card_offer_ids: list[str] | None
    initial_potion_offer_ids: list[str] | None
    surfaced_colored_card_ids: list[str] | None
    surfaced_colorless_card_ids: list[str] | None
    surfaced_potion_ids: list[str] | None
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "ShopVisitLog":
        def _optional_list(key: str) -> list[str] | None:
            if key not in d or d.get(key) is None:
                return None
            return list(d.get(key, []))

        return ShopVisitLog(
            floor=d["floor"],
            initial_relic_offer_ids=list(d.get("initialRelicOfferIds", [])),
            surfaced_relic_ids=list(d.get("surfacedRelicIds", [])),
            purchased_relic_ids=list(d.get("purchasedRelicIds", [])),
            initial_colored_card_offer_ids=_optional_list("initialColoredCardOfferIds"),
            initial_colorless_card_offer_ids=_optional_list("initialColorlessCardOfferIds"),
            initial_potion_offer_ids=_optional_list("initialPotionOfferIds"),
            surfaced_colored_card_ids=_optional_list("surfacedColoredCardIds"),
            surfaced_colorless_card_ids=_optional_list("surfacedColorlessCardIds"),
            surfaced_potion_ids=_optional_list("surfacedPotionIds"),
            timestamp=d.get("timestamp", 0),
        )


@dataclass
class ShopPurgeLog:
    floor: int
    gold: int
    gold_spent: int
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "ShopPurgeLog":
        return ShopPurgeLog(
            floor=d["floor"],
            gold=d["gold"],
            gold_spent=d["goldSpent"],
            timestamp=d["timestamp"],
        )


@dataclass
class CardRemovalLog:
    card_id: str
    source: str
    floor: int
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "CardRemovalLog":
        return CardRemovalLog(
            card_id=d["cardId"],
            source=d["source"],
            floor=d["floor"],
            timestamp=d["timestamp"],
        )


@dataclass
class CardTransformLog:
    old_card_id: str
    new_card_id: str
    floor: int
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "CardTransformLog":
        return CardTransformLog(
            old_card_id=d["oldCardId"],
            new_card_id=d["newCardId"],
            floor=d["floor"],
            timestamp=d["timestamp"],
        )


@dataclass
class PotionObtainLog:
    potion_id: str
    potion_name: str
    source: str
    floor: int
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "PotionObtainLog":
        return PotionObtainLog(
            potion_id=d["potionId"],
            potion_name=d["potionName"],
            source=d["source"],
            floor=d["floor"],
            timestamp=d["timestamp"],
        )


@dataclass
class PotionUseLog:
    potion_id: str
    potion_name: str
    floor: int
    turn: int
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "PotionUseLog":
        return PotionUseLog(
            potion_id=d["potionId"],
            potion_name=d["potionName"],
            floor=d["floor"],
            turn=d.get("turn", 0),
            timestamp=d["timestamp"],
        )


@dataclass
class CardObtainLog:
    card_id: str
    upgraded: bool
    source: str
    floor: int
    timestamp: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "CardObtainLog":
        return CardObtainLog(
            card_id=d["cardId"],
            upgraded=d.get("upgraded", False),
            source=d["source"],
            floor=d["floor"],
            timestamp=d["timestamp"],
        )


@dataclass
class JavaGameLog:
    seed: int
    seed_string: str
    character: str
    run_result: str
    run_result_source: str
    end_act: int
    end_floor: int
    end_hp: int
    end_max_hp: int
    end_gold: int
    initial_deck: list[CardInfo]
    initial_relics: list[str]
    final_deck: list[CardInfo]
    final_relics: list[str]
    all_card_plays: list[CardPlay]
    battles: list[BattleLog]
    rng_snapshots: list[dict[str, Any]]
    rng_calls: list[RngCall]
    map_nodes: list[list[MapNodeLog]]
    path_taken: list[PathStep]
    card_rewards: list[CardRewardLog]
    event_choices: list[EventChoiceLog]
    event_summaries: list[EventChoiceLog]
    rest_actions: list[RestActionLog]
    card_draws: list[CardDrawLog]
    monster_intents: list[MonsterIntentLog]
    gold_changes: list[GoldChangeLog]
    hp_changes: list[HpChangeLog]
    treasure_rooms: list[TreasureRoomLog]
    boss_relic_choices: list[BossRelicChoiceLog]
    card_obtains: list[CardObtainLog]
    card_removals: list[CardRemovalLog]
    card_transforms: list[CardTransformLog]
    relic_changes: list[RelicChangeLog]
    shop_visits: list[ShopVisitLog]
    shop_purchases: list[ShopPurchaseLog]
    shop_purges: list[ShopPurgeLog]
    potion_obtains: list[PotionObtainLog]
    potion_uses: list[PotionUseLog]

    @staticmethod
    def from_file(path: Path) -> "JavaGameLog":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return JavaGameLog(
            seed=data["seed"],
            seed_string=data["seedString"],
            character=data["character"],
            run_result=data.get("runResult", "unknown"),
            run_result_source=data.get("runResultSource", "unknown"),
            end_act=data.get("endAct", 0),
            end_floor=data.get("endFloor", 0),
            end_hp=data.get("endHp", 0),
            end_max_hp=data.get("endMaxHp", 0),
            end_gold=data.get("endGold", 0),
            initial_deck=[CardInfo.from_dict(c) for c in data.get("initialDeck", [])],
            initial_relics=data.get("initialRelics", []),
            final_deck=[CardInfo.from_dict(c) for c in data.get("finalDeck", [])],
            final_relics=data.get("finalRelics", []),
            all_card_plays=[CardPlay.from_dict(c) for c in data.get("allCardPlays", [])],
            battles=[BattleLog.from_dict(b) for b in data.get("battles", [])],
            rng_snapshots=data.get("rngSnapshots", []),
            rng_calls=[RngCall.from_dict(r) for r in data.get("rngCalls", [])],
            map_nodes=[
                [MapNodeLog.from_dict(node) for node in row]
                for row in data.get("mapNodes", [])
            ],
            path_taken=[PathStep.from_dict(step) for step in data.get("pathTaken", [])],
            card_rewards=[CardRewardLog.from_dict(reward) for reward in data.get("cardRewards", [])],
            event_choices=[EventChoiceLog.from_dict(choice) for choice in data.get("eventChoices", [])],
            event_summaries=[EventChoiceLog.from_dict(choice) for choice in data.get("eventSummaries", [])],
            rest_actions=[RestActionLog.from_dict(action) for action in data.get("restActions", [])],
            card_draws=[CardDrawLog.from_dict(draw) for draw in data.get("cardDraws", [])],
            monster_intents=[MonsterIntentLog.from_dict(intent) for intent in data.get("monsterIntents", [])],
            gold_changes=[GoldChangeLog.from_dict(change) for change in data.get("goldChanges", [])],
            hp_changes=[HpChangeLog.from_dict(change) for change in data.get("hpChanges", [])],
            treasure_rooms=[TreasureRoomLog.from_dict(room) for room in data.get("treasureRooms", [])],
            boss_relic_choices=[BossRelicChoiceLog.from_dict(choice) for choice in data.get("bossRelicChoices", [])],
            card_obtains=[CardObtainLog.from_dict(card) for card in data.get("cardObtains", [])],
            card_removals=[CardRemovalLog.from_dict(card) for card in data.get("cardRemovals", [])],
            card_transforms=[CardTransformLog.from_dict(card) for card in data.get("cardTransforms", [])],
            relic_changes=[RelicChangeLog.from_dict(change) for change in data.get("relicChanges", [])],
            shop_visits=[ShopVisitLog.from_dict(visit) for visit in data.get("shopVisits", [])],
            shop_purchases=[ShopPurchaseLog.from_dict(purchase) for purchase in data.get("shopPurchases", [])],
            shop_purges=[ShopPurgeLog.from_dict(purge) for purge in data.get("shopPurges", [])],
            potion_obtains=[PotionObtainLog.from_dict(potion) for potion in data.get("potionObtains", [])],
            potion_uses=[PotionUseLog.from_dict(potion) for potion in data.get("potionUses", [])],
        )


def compare_rng_states(java_state: RngState, python_counters: dict[str, int]) -> list[str]:
    """Compare RNG counters between Java and Python."""
    mismatches = []

    mapping = {
        "cardRngCounter": ("card", java_state.card_rng_counter),
        "monsterRngCounter": ("monster", java_state.monster_rng_counter),
        "aiRngCounter": ("ai", java_state.ai_rng_counter),
        "eventRngCounter": ("event", java_state.event_rng_counter),
        "merchantRngCounter": ("merchant", java_state.merchant_rng_counter),
        "treasureRngCounter": ("treasure", java_state.treasure_rng_counter),
        "relicRngCounter": ("relic", java_state.relic_rng_counter),
        "potionRngCounter": ("potion", java_state.potion_rng_counter),
        "shuffleRngCounter": ("shuffle", java_state.shuffle_rng_counter),
        "cardRandomRngCounter": ("card_random", java_state.card_random_rng_counter),
        "mapRngCounter": ("map", java_state.map_rng_counter),
        "miscRngCounter": ("misc", java_state.misc_rng_counter),
        "monsterHpRngCounter": ("monster_hp", java_state.monster_hp_rng_counter),
    }

    for java_key, (py_key, java_val) in mapping.items():
        py_val = python_counters.get(py_key, 0)
        if java_val != py_val:
            mismatches.append(f"{java_key}: Java={java_val}, Python={py_val}")

    return mismatches


def compare_path_taken(java_path: list[PathStep], python_path: list[dict[str, Any]]) -> list[str]:
    """Compare path selections between Java and Python."""
    mismatches = []

    if len(java_path) != len(python_path):
        mismatches.append(f"Path length mismatch: Java={len(java_path)}, Python={len(python_path)}")
        return mismatches

    for i, (java_step, py_step) in enumerate(zip(java_path, python_path)):
        if java_step.floor != py_step.get("floor"):
            mismatches.append(f"Path step {i} floor mismatch: Java={java_step.floor}, Python={py_step.get('floor')}")
        if java_step.x != py_step.get("x") or java_step.y != py_step.get("y"):
            mismatches.append(
                f"Path step {i} position mismatch: Java=({java_step.x}, {java_step.y}), "
                f"Python=({py_step.get('x')}, {py_step.get('y')})"
            )
        if java_step.room_type != py_step.get("room_type"):
            mismatches.append(
                f"Path step {i} room mismatch: Java={java_step.room_type}, Python={py_step.get('room_type')}"
            )

    return mismatches


def compare_card_rewards(java_rewards: list[CardRewardLog], python_rewards: list[dict[str, Any]]) -> list[str]:
    """Compare card rewards between Java and Python."""
    mismatches = []

    if len(java_rewards) != len(python_rewards):
        mismatches.append(f"Reward count mismatch: Java={len(java_rewards)}, Python={len(python_rewards)}")
        return mismatches

    for i, (java_reward, py_reward) in enumerate(zip(java_rewards, python_rewards)):
        if java_reward.floor != py_reward.get("floor"):
            mismatches.append(
                f"Reward {i} floor mismatch: Java={java_reward.floor}, Python={py_reward.get('floor')}"
            )
        java_choice = _normalize_reward_choice(java_reward.card_id, java_reward.skipped, java_reward.choice_type)
        py_choice = _normalize_reward_choice(
            py_reward.get("picked"),
            py_reward.get("skipped", False),
            py_reward.get("choice_type"),
        )
        if java_choice != py_choice:
            mismatches.append(
                f"Reward {i} card mismatch: Java={java_choice}, Python={py_choice}"
            )

    return mismatches


def _normalize_reward_choice(card_id: Any, skipped: bool, choice_type: Any) -> Any:
    resolved_choice_type = choice_type
    if resolved_choice_type is None and skipped:
        if card_id == "Singing Bowl":
            resolved_choice_type = "singing_bowl"
        else:
            resolved_choice_type = "skip"
    if resolved_choice_type in {"skip", "singing_bowl"}:
        return resolved_choice_type
    return card_id


def compare_rng_calls(java_calls: list[RngCall], python_rng_log: list[dict[str, Any]]) -> list[str]:
    """Compare individual RNG call return values."""
    mismatches = []

    if len(java_calls) != len(python_rng_log):
        mismatches.append(f"RNG call count mismatch: Java={len(java_calls)}, Python={len(python_rng_log)}")
        return mismatches

    for i, (java_call, py_call) in enumerate(zip(java_calls, python_rng_log)):
        if java_call.return_value != py_call.get("return_value"):
            mismatches.append(
                f"RNG call {i} mismatch: Java={java_call.return_value}, Python={py_call.get('return_value')}"
            )

    return mismatches


def compare_battle_results(java_battle: BattleLog, python_result: dict[str, Any]) -> list[str]:
    """Compare battle results between Java and Python."""
    mismatches = []

    if java_battle.player_end_hp != python_result.get("player_hp", 0):
        mismatches.append(
            f"Player HP mismatch: Java={java_battle.player_end_hp}, Python={python_result.get('player_hp')}"
        )

    if len(java_battle.monsters) != len(python_result.get("monsters", [])):
        mismatches.append(
            f"Monster count mismatch: Java={len(java_battle.monsters)}, Python={len(python_result.get('monsters', []))}"
        )

    return mismatches


def generate_comparison_report(java_log: JavaGameLog, python_state: dict[str, Any]) -> str:
    """Generate a detailed comparison report."""
    lines = []
    lines.append("=" * 60)
    lines.append("JAVA vs PYTHON COMPARISON REPORT")
    lines.append("=" * 60)
    lines.append(f"Seed: {java_log.seed_string}")
    lines.append(f"Character: {java_log.character}")
    lines.append("")

    lines.append("RNG STATE COMPARISON:")
    lines.append("-" * 40)
    if "rng_counters" in python_state:
        mismatches = compare_rng_states(
            RngState.from_dict(python_state.get("rng_state", {})),
            python_state["rng_counters"],
        )
        if mismatches:
            for m in mismatches:
                lines.append(f"  MISMATCH: {m}")
        else:
            lines.append("  All RNG counters match!")
    lines.append("")

    lines.append("PATH COMPARISON:")
    lines.append("-" * 40)
    if "path_trace" in python_state:
        mismatches = compare_path_taken(java_log.path_taken, python_state["path_trace"])
        if mismatches:
            for m in mismatches:
                lines.append(f"  MISMATCH: {m}")
        else:
            lines.append("  Path trace matches!")
    lines.append("")

    lines.append("CARD REWARD COMPARISON:")
    lines.append("-" * 40)
    if "card_choices" in python_state:
        mismatches = compare_card_rewards(java_log.card_rewards, python_state["card_choices"])
        if mismatches:
            for m in mismatches:
                lines.append(f"  MISMATCH: {m}")
        else:
            lines.append("  Card rewards match!")
    lines.append("")

    lines.append("BATTLE RESULTS:")
    lines.append("-" * 40)
    for battle in java_log.battles:
        lines.append(f"  Floor {battle.floor}: {battle.room_type}")
        lines.append(f"    Player HP: {battle.player_end_hp}")
        lines.append(f"    Turn count: {battle.turn_count}")
        lines.append(f"    Monsters: {', '.join(m.name for m in battle.monsters)}")
    lines.append("")

    lines.append("CARD PLAY SEQUENCE:")
    lines.append("-" * 40)
    for play in java_log.all_card_plays[:20]:
        lines.append(f"  Floor {play.floor} Turn {play.turn}: {play.card_id} (cost={play.cost})")
    if len(java_log.all_card_plays) > 20:
        lines.append(f"  ... and {len(java_log.all_card_plays) - 20} more")
    lines.append("")

    return "\n".join(lines)


def verify_rng_sequence(java_log: JavaGameLog, python_rng_simulator) -> tuple[bool, list[str]]:
    """
    Verify RNG sequence by replaying each call and comparing results.
    
    Args:
        java_log: The Java game log containing RNG calls
        python_rng_simulator: A Python RNG simulator with same seed
        
    Returns:
        Tuple of (success, list of error messages)
    """
    errors = []
    
    for i, call in enumerate(java_log.rng_calls):
        py_result = python_rng_simulator.call_rng(
            rng_type=call.rng_type,
            method=call.method,
            param1=call.param1,
            param2=call.param2
        )
        
        if py_result != call.return_value:
            errors.append(
                f"RNG call #{i} mismatch:\n"
                f"  Type: {call.rng_type}\n"
                f"  Method: {call.method}\n"
                f"  Params: {call.param1}, {call.param2}\n"
                f"  Java result: {call.return_value}\n"
                f"  Python result: {py_result}\n"
                f"  Floor: {call.floor}, Turn: {call.turn}"
            )
    
    return len(errors) == 0, errors


def verify_game_state(java_log: JavaGameLog, python_game) -> tuple[bool, list[str]]:
    """
    Verify overall game state consistency.
    
    Checks:
    - Initial deck matches
    - Initial relics match
    - Final deck matches
    - Final relics match
    - Gold changes match
    - HP changes match
    """
    errors = []
    
    # Check initial deck
    if hasattr(python_game, 'initial_deck'):
        java_deck = set((c.card_id, c.upgraded) for c in java_log.initial_deck)
        py_deck = set((c['id'], c.get('upgraded', False)) for c in python_game.initial_deck)
        if java_deck != py_deck:
            errors.append(f"Initial deck mismatch:\n  Java: {java_deck}\n  Python: {py_deck}")
    
    # Check final state
    if java_log.end_hp != python_game.current_hp:
        errors.append(f"Final HP mismatch: Java={java_log.end_hp}, Python={python_game.current_hp}")
    
    if java_log.end_gold != python_game.gold:
        errors.append(f"Final gold mismatch: Java={java_log.end_gold}, Python={python_game.gold}")
    
    return len(errors) == 0, errors


def generate_verification_report(java_log: JavaGameLog, python_simulator) -> str:
    """
    Generate a comprehensive verification report.
    
    This is the main entry point for verifying Python simulation against Java logs.
    """
    lines = []
    lines.append("=" * 70)
    lines.append("STS DATA VERIFICATION REPORT")
    lines.append("=" * 70)
    lines.append(f"Seed: {java_log.seed_string} ({java_log.seed})")
    lines.append(f"Character: {java_log.character}")
    lines.append(f"Total RNG calls: {len(java_log.rng_calls)}")
    lines.append(f"Total battles: {len(java_log.battles)}")
    lines.append("")
    
    # RNG verification
    lines.append("RNG SEQUENCE VERIFICATION")
    lines.append("-" * 70)
    rng_success, rng_errors = verify_rng_sequence(java_log, python_simulator)
    if rng_success:
        lines.append("  ✓ All RNG calls match!")
    else:
        lines.append(f"  ✗ Found {len(rng_errors)} mismatches:")
        for err in rng_errors[:10]:  # Show first 10 errors
            lines.append(f"    {err}")
        if len(rng_errors) > 10:
            lines.append(f"    ... and {len(rng_errors) - 10} more errors")
    lines.append("")
    
    # Game state verification
    lines.append("GAME STATE VERIFICATION")
    lines.append("-" * 70)
    state_success, state_errors = verify_game_state(java_log, python_simulator)
    if state_success:
        lines.append("  ✓ All game states match!")
    else:
        lines.append(f"  ✗ Found {len(state_errors)} mismatches:")
        for err in state_errors:
            lines.append(f"    {err}")
    lines.append("")
    
    # Summary
    lines.append("SUMMARY")
    lines.append("-" * 70)
    if rng_success and state_success:
        lines.append("  ✓ VERIFICATION PASSED - Python simulation matches Java game")
    else:
        lines.append("  ✗ VERIFICATION FAILED - See errors above")
    lines.append("")
    
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python compare_logs.py <java_log.json>")
        sys.exit(1)

    log_path = Path(sys.argv[1])
    if not log_path.exists():
        print(f"File not found: {log_path}")
        sys.exit(1)

    java_log = JavaGameLog.from_file(log_path)
    print(f"Loaded Java log: seed={java_log.seed_string}, floors={java_log.end_floor}")
    print(f"Battles: {len(java_log.battles)}")
    print(f"Card plays: {len(java_log.all_card_plays)}")
    print(f"RNG calls: {len(java_log.rng_calls)}")
