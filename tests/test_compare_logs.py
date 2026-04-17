from __future__ import annotations

import json
from pathlib import Path

from sts_py.tools.compare_logs import CardRewardLog, JavaGameLog, compare_card_rewards


def _write_log(tmp_dir: Path, payload: dict) -> Path:
    path = tmp_dir / "java_log.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_java_game_log_defaults_without_new_fields(workspace_tmp_path) -> None:
    log_path = _write_log(
        workspace_tmp_path,
        {
            "seed": 1,
            "seedString": "ABC123",
            "character": "IRONCLAD",
            "cardRewards": [],
            "eventChoices": [],
        },
    )

    log = JavaGameLog.from_file(log_path)

    assert log.run_result == "unknown"
    assert log.run_result_source == "unknown"
    assert log.end_act == 0
    assert log.event_summaries == []
    assert log.treasure_rooms == []
    assert log.boss_relic_choices == []
    assert log.shop_visits == []


def test_java_game_log_reads_new_optional_fields(workspace_tmp_path) -> None:
    log_path = _write_log(
        workspace_tmp_path,
        {
            "seed": 1,
            "seedString": "ABC123",
            "character": "IRONCLAD",
            "runResult": "victory",
            "runResultSource": "VictoryScreen",
            "endAct": 3,
            "cardRewards": [
                {
                    "cardId": "Singing Bowl",
                    "upgraded": False,
                    "skipped": True,
                    "choiceType": "singing_bowl",
                    "notPickedCardIds": ["PommelStrike", "ShrugItOff"],
                    "floor": 7,
                    "timestamp": 123,
                }
            ],
            "eventChoices": [],
            "treasureRooms": [
                {
                    "floor": 17,
                    "roomType": "TreasureRoom",
                    "goldBefore": 99,
                    "goldAfter": 99,
                    "relicId": "Strawberry",
                    "relicName": "Strawberry",
                    "mainRelicId": "Strawberry",
                    "obtainedRelicIds": ["Anchor"],
                    "skippedMainRelicId": "Strawberry",
                    "tookSapphireKey": True,
                    "timestamp": 21,
                }
            ],
            "bossRelicChoices": [
                {
                    "floor": 17,
                    "act": 1,
                    "pickedRelicId": "TinyHouse",
                    "notPickedRelicIds": ["CallingBell", "PandoraBox"],
                    "skipped": False,
                    "timestamp": 22,
                }
            ],
            "eventSummaries": [
                {
                    "eventId": "BigFish",
                    "eventName": "Big Fish",
                    "choiceIndex": 1,
                    "choiceText": "Semantic summary",
                    "floor": 5,
                    "timestamp": 456,
                }
            ],
            "restActions": [
                {
                    "action": "SMITH",
                    "floor": 8,
                    "hpBefore": 77,
                    "maxHp": 88,
                    "timestamp": 10,
                }
            ],
            "cardObtains": [
                {
                    "cardId": "Pommel Strike",
                    "upgraded": False,
                    "source": "reward",
                    "floor": 5,
                    "timestamp": 11,
                }
            ],
            "cardRemovals": [
                {
                    "cardId": "Strike",
                    "source": "shop",
                    "floor": 19,
                    "timestamp": 12,
                }
            ],
            "cardTransforms": [
                {
                    "oldCardId": "Defend",
                    "newCardId": "Shrug It Off",
                    "floor": 9,
                    "timestamp": 13,
                }
            ],
            "relicChanges": [
                {
                    "relicId": "Dream Catcher",
                    "relicName": "Dream Catcher",
                    "floor": 3,
                    "turn": 0,
                    "action": "triggered:onEquip",
                    "source": "elite",
                    "timestamp": 14,
                }
            ],
            "shopPurchases": [
                {
                    "itemType": "relic",
                    "itemId": "Juzu Bracelet",
                    "floor": 19,
                    "gold": 277,
                    "goldSpent": 152,
                    "timestamp": 15,
                }
            ],
            "shopVisits": [
                {
                    "floor": 19,
                    "initialRelicOfferIds": ["Anchor", "Lantern", "Membership Card"],
                    "initialColoredCardOfferIds": ["Pommel Strike", "Shrug It Off", "Inflame", "True Grit", "Demon Form"],
                    "initialColorlessCardOfferIds": ["Madness", "Master of Strategy"],
                    "initialPotionOfferIds": ["AttackPotion", "BlockPotion", "ExplosivePotion"],
                    "surfacedRelicIds": ["Anchor", "Lantern", "Membership Card", "OddlySmoothStone"],
                    "surfacedColoredCardIds": ["Pommel Strike", "Shrug It Off", "Inflame", "True Grit", "Demon Form", "Offering"],
                    "surfacedColorlessCardIds": ["Madness", "Master of Strategy", "Apotheosis"],
                    "surfacedPotionIds": ["AttackPotion", "BlockPotion", "ExplosivePotion", "DexterityPotion"],
                    "purchasedRelicIds": ["Anchor"],
                    "timestamp": 14,
                }
            ],
            "shopPurges": [
                {
                    "floor": 19,
                    "gold": 429,
                    "goldSpent": 100,
                    "timestamp": 16,
                }
            ],
            "goldChanges": [
                {
                    "amount": 14,
                    "source": "reward",
                    "floor": 1,
                    "goldAfter": 113,
                    "timestamp": 17,
                }
            ],
            "hpChanges": [
                {
                    "amount": 8,
                    "source": "increaseMaxHp",
                    "floor": 0,
                    "hpAfter": 88,
                    "maxHp": 88,
                    "timestamp": 18,
                }
            ],
            "potionObtains": [
                {
                    "potionId": "Dexterity Potion",
                    "potionName": "Dexterity Potion",
                    "source": "reward",
                    "floor": 7,
                    "timestamp": 19,
                }
            ],
            "potionUses": [
                {
                    "potionId": "Dexterity Potion",
                    "potionName": "Dexterity Potion",
                    "floor": 12,
                    "turn": 1,
                    "timestamp": 20,
                }
            ],
        },
    )

    log = JavaGameLog.from_file(log_path)

    assert log.run_result == "victory"
    assert log.run_result_source == "VictoryScreen"
    assert log.end_act == 3
    assert log.card_rewards[0].choice_type == "singing_bowl"
    assert log.card_rewards[0].not_picked_card_ids == ["PommelStrike", "ShrugItOff"]
    assert log.event_summaries[0].choice_text == "Semantic summary"
    assert log.rest_actions[0].action == "SMITH"
    assert log.card_obtains[0].card_id == "Pommel Strike"
    assert log.card_removals[0].source == "shop"
    assert log.card_transforms[0].new_card_id == "Shrug It Off"
    assert log.relic_changes[0].action == "triggered:onEquip"
    assert log.shop_visits[0].surfaced_relic_ids[-1] == "OddlySmoothStone"
    assert log.shop_visits[0].purchased_relic_ids == ["Anchor"]
    assert log.shop_visits[0].initial_colored_card_offer_ids[0] == "Pommel Strike"
    assert log.shop_visits[0].initial_colorless_card_offer_ids == ["Madness", "Master of Strategy"]
    assert log.shop_visits[0].initial_potion_offer_ids[-1] == "ExplosivePotion"
    assert log.shop_visits[0].surfaced_colored_card_ids[-1] == "Offering"
    assert log.shop_visits[0].surfaced_colorless_card_ids[-1] == "Apotheosis"
    assert log.shop_visits[0].surfaced_potion_ids[-1] == "DexterityPotion"
    assert log.shop_purchases[0].gold_spent == 152
    assert log.shop_purges[0].gold_spent == 100
    assert log.gold_changes[0].gold_after == 113
    assert log.hp_changes[0].max_hp == 88
    assert log.potion_obtains[0].potion_id == "Dexterity Potion"
    assert log.potion_uses[0].turn == 1
    assert log.treasure_rooms[0].room_type == "TreasureRoom"
    assert log.treasure_rooms[0].obtained_relic_ids == ["Anchor"]


def test_java_game_log_keeps_new_shop_surface_fields_optional(workspace_tmp_path) -> None:
    log_path = _write_log(
        workspace_tmp_path,
        {
            "seed": 1,
            "seedString": "SHOPOPTIONAL",
            "character": "IRONCLAD",
            "initialDeck": [],
            "initialRelics": [],
            "finalDeck": [],
            "finalRelics": [],
            "allCardPlays": [],
            "battles": [],
            "rngSnapshots": [],
            "rngCalls": [],
            "mapNodes": [],
            "pathTaken": [],
            "cardRewards": [],
            "eventChoices": [],
            "eventSummaries": [],
            "restActions": [],
            "cardDraws": [],
            "monsterIntents": [],
            "goldChanges": [],
            "hpChanges": [],
            "treasureRooms": [],
            "bossRelicChoices": [],
            "cardObtains": [],
            "cardRemovals": [],
            "cardTransforms": [],
            "relicChanges": [],
            "shopVisits": [
                {
                    "floor": 4,
                    "initialRelicOfferIds": ["Anchor", "Lantern", "Membership Card"],
                    "surfacedRelicIds": ["Anchor", "Lantern", "Membership Card"],
                    "purchasedRelicIds": [],
                    "timestamp": 1,
                }
            ],
            "shopPurchases": [],
            "shopPurges": [],
            "potionObtains": [],
            "potionUses": [],
            "runResult": "unknown",
            "runResultSource": "unknown",
            "endAct": 0,
            "endFloor": 4,
            "endHp": 0,
            "endMaxHp": 0,
            "endGold": 0,
        },
    )

    log = JavaGameLog.from_file(log_path)

    assert log.shop_visits[0].initial_colored_card_offer_ids is None
    assert log.shop_visits[0].initial_colorless_card_offer_ids is None
    assert log.shop_visits[0].initial_potion_offer_ids is None
    assert log.shop_visits[0].surfaced_colored_card_ids is None
    assert log.shop_visits[0].surfaced_colorless_card_ids is None
    assert log.shop_visits[0].surfaced_potion_ids is None


def test_java_game_log_preserves_obtained_relic_change_sources(workspace_tmp_path) -> None:
    log_path = _write_log(
        workspace_tmp_path,
        {
            "seed": 1,
            "seedString": "ABC123",
            "character": "IRONCLAD",
            "cardRewards": [],
            "eventChoices": [],
            "relicChanges": [
                {
                    "relicId": "Calling Bell",
                    "relicName": "Calling Bell",
                    "floor": 17,
                    "turn": 0,
                    "action": "obtained",
                    "source": "boss",
                    "timestamp": 10,
                },
                {
                    "relicId": "Anchor",
                    "relicName": "Anchor",
                    "floor": 17,
                    "turn": 0,
                    "action": "obtained",
                    "source": "calling_bell",
                    "timestamp": 11,
                },
                {
                    "relicId": "Lantern",
                    "relicName": "Lantern",
                    "floor": 22,
                    "turn": 0,
                    "action": "obtained",
                    "source": "shop",
                    "timestamp": 12,
                },
            ],
        },
    )

    log = JavaGameLog.from_file(log_path)

    assert [(change.action, change.source) for change in log.relic_changes] == [
        ("obtained", "boss"),
        ("obtained", "calling_bell"),
        ("obtained", "shop"),
    ]


def test_compare_card_rewards_normalizes_skip_and_singing_bowl() -> None:
    java_rewards = [
        CardRewardLog.from_dict(
            {
                "cardId": "SKIP",
                "upgraded": False,
                "skipped": True,
                "choiceType": "skip",
                "floor": 3,
                "timestamp": 1,
            }
        ),
        CardRewardLog.from_dict(
            {
                "cardId": "Singing Bowl",
                "upgraded": False,
                "skipped": True,
                "choiceType": "singing_bowl",
                "floor": 4,
                "timestamp": 2,
            }
        ),
    ]

    mismatches = compare_card_rewards(
        java_rewards,
        [
            {"floor": 3, "picked": "SKIP", "skipped": True, "choice_type": "skip"},
            {"floor": 4, "picked": None, "skipped": True, "choice_type": "singing_bowl"},
        ],
    )

    assert mismatches == []
