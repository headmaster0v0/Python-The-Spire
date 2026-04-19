from __future__ import annotations

from sts_py.engine.content.cards_min import ALL_CARD_DEFS
from sts_py.engine.content.card_instance import get_runtime_card_base_id
from sts_py.engine.content.relics import RelicSource, get_relic_by_id, normalize_relic_id
from sts_py.engine.run.run_engine import MapNode, RoomType, RunEngine, RunPhase
from sts_py.engine.run.shop import ShopEngine, ShopItem, ShopItemType, ShopState
from sts_py.terminal.catalog import build_relic_contexts_from_engine


def _force_win_current_combat(engine: RunEngine) -> None:
    assert engine.state.combat is not None
    for monster in engine.state.combat.state.monsters:
        monster.hp = 0
        monster.is_dying = True
    engine.end_combat()


def _start_room_combat(engine: RunEngine, room_type: RoomType, encounter: str) -> None:
    engine.state.map_nodes = [MapNode(floor=1, room_type=room_type, node_id=0)]
    engine.state.current_node_idx = 0
    engine._start_combat(encounter)


def _canon(relic_id: str | None) -> str | None:
    return normalize_relic_id(relic_id) if relic_id is not None else None


def _canon_list(relic_ids: list[str]) -> list[str]:
    return [str(_canon(relic_id) or relic_id) for relic_id in relic_ids]


def test_normal_combat_generates_card_reward_candidates() -> None:
    engine = RunEngine.create("PHASE225MONSTERREWARD", ascension=0)
    _start_room_combat(engine, RoomType.MONSTER, "Cultist")

    _force_win_current_combat(engine)

    assert engine.state.phase == RunPhase.REWARD
    assert len(engine.state.pending_card_reward_cards) == 3


def test_question_card_and_busted_crown_modify_reward_count() -> None:
    question = RunEngine.create("PHASE225QUESTIONCARD", ascension=0)
    question.state.relics.append("QuestionCard")
    _start_room_combat(question, RoomType.MONSTER, "Cultist")
    _force_win_current_combat(question)
    assert len(question.state.pending_card_reward_cards) == 4

    crown = RunEngine.create("PHASE225BUSTEDCROWN", ascension=0)
    crown.state.relics.append("BustedCrown")
    _start_room_combat(crown, RoomType.MONSTER, "Cultist")
    _force_win_current_combat(crown)
    assert len(crown.state.pending_card_reward_cards) == 1


def test_prayer_wheel_applies_only_to_normal_combat_rewards() -> None:
    monster_engine = RunEngine.create("PHASE225PRAYERWHEELMONSTER", ascension=0)
    monster_engine.state.relics.append("PrayerWheel")
    _start_room_combat(monster_engine, RoomType.MONSTER, "Cultist")
    _force_win_current_combat(monster_engine)
    assert len(monster_engine.state.pending_card_reward_cards) == 4

    elite_engine = RunEngine.create("PHASE225PRAYERWHEELELITE", ascension=0)
    elite_engine.state.relics.append("PrayerWheel")
    _start_room_combat(elite_engine, RoomType.ELITE, "Gremlin Nob")
    _force_win_current_combat(elite_engine)
    assert len(elite_engine.state.pending_card_reward_cards) == 3


def test_elite_reward_relics_and_black_star_use_pending_relic_list() -> None:
    engine = RunEngine.create("PHASE225BLACKSTAR", ascension=0)
    engine.state.relics.append("BlackStar")
    _start_room_combat(engine, RoomType.ELITE, "Gremlin Nob")

    _force_win_current_combat(engine)

    pending = engine.get_pending_reward_state()
    assert pending["relic"] == pending["relics"][0]
    assert len(pending["relics"]) == 2
    assert [entry["source"] for entry in engine.state.relic_history] == ["elite", "elite"]


def test_boss_combat_generates_boss_relic_choices_before_transition() -> None:
    engine = RunEngine.create("PHASE226BOSSRELIC", ascension=0)
    _start_room_combat(engine, RoomType.BOSS, "Hexaghost")

    _force_win_current_combat(engine)

    assert engine.state.phase == RunPhase.VICTORY
    assert len(engine.state.pending_boss_relic_choices) == 3
    assert len(set(engine.state.pending_boss_relic_choices)) == 3
    assert set(_canon_list(engine.state.pending_boss_relic_choices)).issubset(set(engine.state.relic_pool_consumed["boss"]))


def test_transition_to_next_act_is_blocked_until_boss_relic_resolves() -> None:
    engine = RunEngine.create("PHASE226BOSSGATE", ascension=0)
    engine.state.phase = RunPhase.VICTORY
    engine.state.pending_boss_relic_choices = ["TinyHouse", "CallingBell", "PandoraBox"]

    engine.transition_to_next_act()

    assert engine.state.act == 1
    assert engine.state.phase == RunPhase.VICTORY


def test_choose_boss_relic_replaces_starter_and_allows_transition() -> None:
    engine = RunEngine.create("PHASE226BLACKBLOOD", ascension=0)
    engine.state.phase = RunPhase.VICTORY
    engine.state.pending_boss_relic_choices = ["BlackBlood", "TinyHouse", "CallingBell"]

    result = engine.choose_boss_relic(0)

    assert result["success"] is True
    assert result["relic_id"] == "BlackBlood"
    assert "BurningBlood" not in engine.state.relics
    assert "BlackBlood" in engine.state.relics
    assert engine.get_pending_reward_state()["relic"] is None
    assert engine.state.pending_boss_relic_choices == []
    assert engine.state.relic_history[-1] == {
        "floor": 0,
        "relic_id": "Black Blood",
        "source": "boss",
    }

    engine.transition_to_next_act()

    assert engine.state.act == 2
    assert engine.state.phase == RunPhase.MAP


def test_skip_boss_relic_choice_keeps_victory_and_allows_transition() -> None:
    engine = RunEngine.create("PHASE226SKIPBOSS", ascension=0)
    engine.state.phase = RunPhase.VICTORY
    engine.state.pending_boss_relic_choices = ["TinyHouse", "CallingBell", "PandoraBox"]

    result = engine.skip_boss_relic_choice()

    assert result["success"] is True
    assert engine.state.pending_boss_relic_choices == []
    assert engine.state.phase == RunPhase.VICTORY

    engine.transition_to_next_act()

    assert engine.state.act == 2
    assert engine.state.phase == RunPhase.MAP


def test_skipped_act1_boss_relic_offer_is_consumed_for_act2_offer() -> None:
    engine = RunEngine.create("PHASE232BOSSPOOL", ascension=0)
    _start_room_combat(engine, RoomType.BOSS, "Hexaghost")
    _force_win_current_combat(engine)

    act1_choices = list(engine.state.pending_boss_relic_choices)
    engine.skip_boss_relic_choice()
    engine.transition_to_next_act()

    _start_room_combat(engine, RoomType.BOSS, "Champ")
    _force_win_current_combat(engine)
    act2_choices = list(engine.state.pending_boss_relic_choices)

    assert not (set(_canon_list(act1_choices)) & set(_canon_list(act2_choices)))
    assert set(_canon_list(act1_choices + act2_choices)).issubset(set(engine.state.relic_pool_consumed["boss"]))


def test_meal_ticket_heals_on_shop_enter() -> None:
    engine = RunEngine.create("PHASE225MEALTICKET", ascension=0)
    engine.state.player_hp = 50
    engine.state.relics.append("MealTicket")

    engine._enter_shop()

    assert engine.state.phase == RunPhase.SHOP
    assert engine.state.player_hp == 65


def test_shop_entry_surfaces_relics_and_records_shop_history() -> None:
    engine = RunEngine.create("PHASE234SHOPSURFACE", ascension=0)
    engine.state.floor = 12

    engine._enter_shop()

    shop = engine.get_shop()
    assert shop is not None
    offer_ids = [item["relic_id"] for item in shop.get_available_relics()]
    colored_ids = [item["card_id"] for item in shop.get_available_cards() if item["is_colored"]]
    colorless_ids = [item["card_id"] for item in shop.get_available_cards() if not item["is_colored"]]
    potion_ids = [item["potion_id"] for item in shop.get_available_potions()]
    assert len(offer_ids) == 3
    assert shop.shop.relics[2].tier == "shop"
    shop_history = engine.state.shop_history[-1]
    assert shop_history["floor"] == 12
    assert shop_history["surfaced_relic_ids"] == _canon_list(offer_ids)
    assert shop_history["current_relic_ids"] == _canon_list(offer_ids)
    assert shop_history["purchased_relic_ids"] == []
    assert shop_history["initial_colored_card_ids"] == colored_ids
    assert shop_history["current_colored_card_ids"] == colored_ids
    assert shop_history["surfaced_colored_card_ids"] == colored_ids
    assert shop_history["initial_colorless_card_ids"] == colorless_ids
    assert shop_history["current_colorless_card_ids"] == colorless_ids
    assert shop_history["surfaced_colorless_card_ids"] == colorless_ids
    assert shop_history["initial_potion_ids"] == potion_ids
    assert shop_history["current_potion_ids"] == potion_ids
    assert shop_history["surfaced_potion_ids"] == potion_ids
    for item in shop.shop.relics:
        assert item.tier is not None
        assert _canon(item.item_id) in engine.state.relic_pool_consumed[item.tier]


def test_shop_surface_does_not_repeat_between_visits() -> None:
    engine = RunEngine.create("PHASE234SHOPREPEAT", ascension=0)
    engine.state.floor = 7
    engine._enter_shop()
    shop1 = engine.get_shop()
    assert shop1 is not None
    first_offers = [item["relic_id"] for item in shop1.get_available_relics()]

    engine.leave_shop()
    engine.state.floor = 8
    engine._enter_shop()
    shop2 = engine.get_shop()
    assert shop2 is not None
    second_offers = [item["relic_id"] for item in shop2.get_available_relics()]

    assert not (set(first_offers) & set(second_offers))


def test_shop_relic_purchase_applies_pickup_effects_immediately() -> None:
    engine = RunEngine.create("PHASE225SHOPPICKUP", ascension=0)
    engine.state.player_gold = 999
    engine.state.deck = ["Defend", "ShrugItOff", "Strike", "Bash"]

    shop = ShopState(
        relics=[
            ShopItem(ShopItemType.RELIC, "Strawberry", 150),
            ShopItem(ShopItemType.RELIC, "WarPaint", 150),
            ShopItem(ShopItemType.RELIC, "Whetstone", 150),
        ]
    )
    shop_engine = ShopEngine(engine, shop)

    hp_before = engine.state.player_max_hp
    result = shop_engine.buy_relic(0)
    assert result["success"] is True
    assert engine.state.player_max_hp == hp_before + 7

    result = shop_engine.buy_relic(1)
    assert result["success"] is True
    assert "Defend+" in engine.state.deck
    assert "ShrugItOff+" in engine.state.deck

    result = shop_engine.buy_relic(2)
    assert result["success"] is True
    assert "Strike+" in engine.state.deck
    assert "Bash+" in engine.state.deck
    assert [entry["source"] for entry in engine.state.relic_history[-3:]] == ["shop", "shop", "shop"]


def test_courier_relic_purchase_replaces_slot_and_records_shop_history() -> None:
    engine = RunEngine.create("PHASE234COURIERRELIC", ascension=0)
    engine.state.floor = 14
    engine.state.relics.append("TheCourier")
    engine.state.player_gold = 999
    engine._enter_shop()
    shop = engine.get_shop()
    assert shop is not None

    initial_offers = [item["relic_id"] for item in shop.get_available_relics()]
    purchased_relic = initial_offers[0]
    result = shop.buy_relic(0)

    assert result["success"] is True
    assert result["replacement_relic"] != purchased_relic
    assert result["replacement_relic"] not in initial_offers
    assert len(shop.get_available_relics()) == 3
    assert engine.state.shop_history[-1]["purchased_relic_ids"] == _canon_list([purchased_relic])
    assert engine.state.shop_history[-1]["surfaced_relic_ids"] == _canon_list([*initial_offers, result["replacement_relic"]])
    assert engine.state.shop_history[-1]["current_relic_ids"] == _canon_list(
        [item["relic_id"] for item in shop.get_available_relics()]
    )

    replacement_item = next(item for item in shop.shop.relics if item.item_id == result["replacement_relic"])
    assert replacement_item.tier in {"common", "uncommon", "rare"}
    assert _canon(replacement_item.item_id) in engine.state.relic_pool_consumed[replacement_item.tier]


def test_courier_keeps_colorless_relic_and_potion_slots_available() -> None:
    engine = RunEngine.create("PHASE234COURIERNOSOLDOUT", ascension=0)
    engine.state.player_gold = 999
    engine.state.relics.append("TheCourier")
    shop = ShopState(
        colorless_cards=[ShopItem(ShopItemType.CARD, "Offering", 150)],
        relics=[ShopItem(ShopItemType.RELIC, "Anchor", 150, tier="common")],
        potions=[ShopItem(ShopItemType.POTION, "BlockPotion", 50, tier="common")],
    )
    shop_engine = ShopEngine(engine, shop)

    colorless_result = shop_engine.buy_card(0, is_colored=False)
    relic_result = shop_engine.buy_relic(0)
    potion_result = shop_engine.buy_potion(0)

    assert colorless_result["success"] is True
    assert "replacement_card" in colorless_result
    assert relic_result["success"] is True
    assert "replacement_relic" in relic_result
    assert potion_result["success"] is True
    assert "replacement_potion" in potion_result
    assert len(shop_engine.get_available_cards()) == 1
    assert len(shop_engine.get_available_relics()) == 1
    assert len(shop_engine.get_available_potions()) == 1
    assert shop_engine.run_engine.state.shop_history[-1]["surfaced_colorless_card_ids"] == [
        "Offering",
        shop_engine.run_engine._canonical_card_id(colorless_result["replacement_card"]),
    ]
    assert shop_engine.run_engine.state.shop_history[-1]["current_colorless_card_ids"] == [
        item["card_id"] for item in shop_engine.get_available_cards() if not item["is_colored"]
    ]
    assert shop_engine.run_engine.state.shop_history[-1]["surfaced_potion_ids"] == [
        "BlockPotion",
        shop_engine.run_engine._canonical_potion_id(potion_result["replacement_potion"]),
    ]
    assert shop_engine.run_engine.state.shop_history[-1]["current_potion_ids"] == [
        item["potion_id"] for item in shop_engine.get_available_potions()
    ]


def test_take_treasure_relic_uses_acquisition_helper() -> None:
    engine = RunEngine.create("PHASE225TREASURE", ascension=0)
    engine.state.phase = RunPhase.TREASURE
    engine.state.pending_chest_relic_choices = ["Strawberry"]
    engine.state.pending_treasure_relic = "Strawberry"
    max_hp_before = engine.state.player_max_hp

    result = engine.take_treasure_relic()

    assert result["success"] is True
    assert engine.state.player_max_hp == max_hp_before + 7
    assert engine.get_pending_reward_state()["relic"] == "Strawberry"
    assert engine.state.treasure_rooms[-1]["obtained_relic_ids"] == ["Strawberry"]
    assert engine.state.relic_history[-1] == {
        "floor": 0,
        "relic_id": "Strawberry",
        "source": "treasure",
    }


def test_cursed_key_adds_curse_when_chest_is_opened() -> None:
    engine = RunEngine.create("PHASE225CURSEDKEY", ascension=0)
    engine.state.relics.append("CursedKey")
    deck_before = len(engine.state.deck)

    engine._enter_treasure()

    assert len(engine.state.deck) == deck_before + 1
    assert any(card_id != "AscendersBane" for card_id in engine.state.deck[deck_before:])


def test_matryoshka_adds_one_extra_chest_relic_for_two_chests() -> None:
    engine = RunEngine.create("PHASE226MATRYOSHKA", ascension=0)
    engine.state.relics.append("Matryoshka")
    engine.state.relic_counters["Matryoshka"] = 2

    engine._enter_treasure()
    first_rewards = list(engine.state.pending_chest_relic_choices)
    first_main = engine.state.pending_treasure_relic

    assert len(first_rewards) == 2
    assert first_main == first_rewards[-1]
    assert engine.state.relic_counters["Matryoshka"] == 1

    engine.state.phase = RunPhase.MAP
    engine._enter_treasure()
    second_rewards = list(engine.state.pending_chest_relic_choices)

    assert len(second_rewards) == 2
    assert engine.state.relic_counters["Matryoshka"] == 0
    assert first_rewards[0] not in second_rewards

    engine.state.phase = RunPhase.MAP
    engine._enter_treasure()

    assert len(engine.state.pending_chest_relic_choices) == 1
    assert engine.state.relic_counters["Matryoshka"] == 0
    assert first_rewards[0] not in engine.state.pending_chest_relic_choices


def test_sapphire_key_only_replaces_main_chest_relic() -> None:
    engine = RunEngine.create("PHASE226SAPPHIRE", ascension=0)
    engine.state.phase = RunPhase.TREASURE
    engine.state.pending_chest_relic_choices = ["Anchor", "Strawberry"]
    engine.state.pending_treasure_relic = "Strawberry"
    max_hp_before = engine.state.player_max_hp

    result = engine.take_sapphire_key()

    assert result["success"] is True
    assert engine.state.sapphire_key_obtained is True
    assert engine.state.pending_treasure_relic is None
    assert engine.state.pending_chest_relic_choices == ["Anchor"]
    assert engine.state.phase == RunPhase.TREASURE

    result = engine.take_treasure_relic(0)

    assert result["success"] is True
    assert "Anchor" in engine.state.relics
    assert engine.state.player_max_hp == max_hp_before
    assert engine.state.phase == RunPhase.MAP
    assert engine.state.treasure_rooms[-1] == {
        "floor": 0,
        "room_type": "TreasureRoom",
        "main_relic_id": "Strawberry",
        "obtained_relic_ids": ["Anchor"],
        "skipped_main_relic_id": "Strawberry",
        "took_sapphire_key": True,
    }


def test_skipped_main_chest_relic_is_still_consumed_for_future_chests() -> None:
    engine = RunEngine.create("PHASE232SAPPHIREPOOL", ascension=0)
    engine.state.floor = 9
    engine._enter_treasure()
    first_main = engine.state.pending_treasure_relic
    assert first_main is not None

    skip_result = engine.take_sapphire_key()
    assert skip_result["success"] is True
    while engine.state.phase == RunPhase.TREASURE:
        engine.take_treasure_relic(0)

    first_main_tier = get_relic_by_id(first_main).tier.value.lower()
    assert _canon(first_main) in engine.state.relic_pool_consumed[first_main_tier]

    engine.state.phase = RunPhase.MAP
    engine.state.floor = 10
    engine._enter_treasure()

    assert engine.state.pending_treasure_relic != first_main


def test_run_scoped_chest_pool_prevents_repeat_after_relic_is_lost() -> None:
    engine = RunEngine.create("PHASE232CHESTPOOL", ascension=0)
    engine.state.floor = 1
    engine._enter_treasure()
    first_main = engine.state.pending_treasure_relic
    assert first_main is not None

    first_index = engine.state.pending_chest_relic_choices.index(first_main)
    take_result = engine.take_treasure_relic(first_index)
    assert take_result["success"] is True

    engine.state.relics.remove(first_main)
    engine.state.phase = RunPhase.MAP
    engine.state.floor = 2
    engine._enter_treasure()

    assert engine.state.pending_treasure_relic != first_main


def test_run_state_to_dict_includes_relic_reward_history_fields() -> None:
    engine = RunEngine.create("PHASE232TODICT", ascension=0)
    engine.state.floor = 17
    engine.state.phase = RunPhase.VICTORY
    engine.state.pending_boss_relic_choices = ["TinyHouse", "CallingBell", "PandoraBox"]
    engine.state.relic_pool_consumed["boss"] = ["TinyHouse", "CallingBell", "PandoraBox"]

    boss_result = engine.skip_boss_relic_choice()
    assert boss_result["success"] is True

    engine.state.floor = 18
    engine.state.phase = RunPhase.TREASURE
    engine.state.pending_chest_relic_choices = ["Anchor", "Strawberry"]
    engine.state.pending_treasure_relic = "Strawberry"
    engine.take_sapphire_key()
    engine.take_treasure_relic(0)

    state = engine.state.to_dict()

    assert "relic_pool_consumed" in state
    assert "relic_history" in state
    assert "boss_relic_choices" in state
    assert "treasure_rooms" in state
    assert state["relic_history"][-1] == {
        "floor": 18,
        "relic_id": "Anchor",
        "source": "treasure",
    }
    assert state["boss_relic_choices"][-1] == {
        "floor": 17,
        "picked_relic_id": None,
        "not_picked_relic_ids": ["TinyHouse", "CallingBell", "PandoraBox"],
        "skipped": True,
    }
    assert state["treasure_rooms"][-1] == {
        "floor": 18,
        "room_type": "TreasureRoom",
        "main_relic_id": "Strawberry",
        "obtained_relic_ids": ["Anchor"],
        "skipped_main_relic_id": "Strawberry",
        "took_sapphire_key": True,
    }


def test_run_state_to_dict_includes_shop_history() -> None:
    engine = RunEngine.create("PHASE234SHOPTODICT", ascension=0)
    engine.state.floor = 9
    engine._enter_shop()
    state = engine.state.to_dict()

    assert "shop_history" in state
    assert state["shop_history"][-1]["floor"] == 9
    assert len(state["shop_history"][-1]["surfaced_relic_ids"]) == 3
    assert len(state["shop_history"][-1]["surfaced_colored_card_ids"]) == 5
    assert len(state["shop_history"][-1]["surfaced_colorless_card_ids"]) == 2
    assert len(state["shop_history"][-1]["surfaced_potion_ids"]) == 3


def test_boss_relic_choice_does_not_consume_matryoshka_counter() -> None:
    engine = RunEngine.create("PHASE226MATRBOSS", ascension=0)
    engine.state.relics.append("Matryoshka")
    engine.state.relic_counters["Matryoshka"] = 2
    _start_room_combat(engine, RoomType.BOSS, "Hexaghost")

    _force_win_current_combat(engine)

    assert len(engine.state.pending_boss_relic_choices) == 3
    assert engine.state.relic_counters["Matryoshka"] == 2


def test_tiny_house_boss_choice_returns_to_victory_after_reward_resolution() -> None:
    engine = RunEngine.create("PHASE226TINYHOUSE", ascension=0)
    engine.state.phase = RunPhase.VICTORY
    engine.state.pending_boss_relic_choices = ["TinyHouse", "CallingBell", "PandoraBox"]

    result = engine.choose_boss_relic(0)

    assert result["success"] is True
    assert engine.state.phase == RunPhase.REWARD
    assert len(engine.state.pending_card_reward_cards) == 3

    engine.skip_card_reward()
    engine.clear_pending_reward_notifications()

    assert engine.state.phase == RunPhase.VICTORY


def test_pandora_box_transforms_all_strikes_and_defends() -> None:
    engine = RunEngine.create("PHASE225PANDORA", ascension=0)
    original_deck = list(engine.state.deck)

    engine._acquire_relic("PandoraBox", record_pending=True)

    assert len(engine.state.deck) == len(original_deck)
    assert all(card_id not in {"Strike", "Defend"} for card_id in engine.state.deck)


def test_tiny_house_applies_full_pickup_bundle() -> None:
    engine = RunEngine.create("PHASE225TINYHOUSE", ascension=0)
    engine.state.player_hp = 20
    engine.state.player_gold = 99

    engine._acquire_relic("TinyHouse", record_pending=True)

    assert engine.state.player_max_hp == 85
    assert engine.state.player_hp == 85
    assert engine.state.player_gold == 149
    assert len(engine.state.pending_card_reward_cards) == 3
    assert any(potion != "EmptyPotionSlot" for potion in engine.state.potions)


def test_calling_bell_adds_curse_and_three_extra_relics() -> None:
    engine = RunEngine.create("PHASE225CALLINGBELL", ascension=0)
    relic_count_before = len(engine.state.relics)

    engine._acquire_relic("CallingBell", source=RelicSource.BOSS, record_pending=True)

    pending = engine.get_pending_reward_state()
    assert "CurseOfTheBell" in engine.state.deck
    assert len(engine.state.relics) == relic_count_before + 4
    assert pending["relics"][0] == "CallingBell"
    assert len(pending["relics"]) == 4
    assert engine.state.relic_history[0] == {
        "floor": 0,
        "relic_id": "Calling Bell",
        "source": "boss",
    }
    assert [entry["source"] for entry in engine.state.relic_history[1:]] == [
        "calling_bell",
        "calling_bell",
        "calling_bell",
    ]


def test_empty_cage_removes_first_two_removable_cards() -> None:
    engine = RunEngine.create("PHASE225EMPTYCAGE", ascension=0)
    engine.state.deck = ["Strike", "Defend", "Bash", "Anger"]

    engine._acquire_relic("EmptyCage", record_pending=True)

    assert engine.state.deck == ["Bash", "Anger"]


def test_black_blood_replaces_burning_blood() -> None:
    engine = RunEngine.create("PHASE225BLACKBLOOD", ascension=0)

    engine._acquire_relic("BlackBlood", record_pending=True)

    assert "BurningBlood" not in engine.state.relics
    assert "BlackBlood" in engine.state.relics


def test_shop_card_preview_and_card_added_hooks_follow_runtime_truth() -> None:
    engine = RunEngine.create("PHASE278SHOPHOOKS", ascension=0)
    engine.state.player_gold = 999
    engine.state.relics.extend(["MoltenEgg", "CeramicFish"])
    engine._enter_shop()
    shop = engine.get_shop()
    assert shop is not None

    attack_offer = next(
        item
        for item in shop.get_available_cards()
        if ALL_CARD_DEFS[get_runtime_card_base_id(item["card_id"])].card_type.value == "ATTACK"
    )
    assert attack_offer["card_id"].endswith("+")
    gold_before = engine.state.player_gold

    result = shop.buy_card(int(attack_offer["index"]), is_colored=bool(attack_offer["is_colored"]))

    assert result["success"] is True
    assert result["card_id"].endswith("+")
    assert engine.state.player_gold == gold_before - attack_offer["price"] + 9
    assert result["card_id"] in engine.state.deck


def test_bottled_card_metadata_blocks_purge_and_starts_in_opening_hand() -> None:
    purge_engine = RunEngine.create("PHASE278BOTTLEPURGE", ascension=0)
    purge_engine.state.player_gold = 999
    purge_engine.state.deck = ["Anger", "Defend", "Bash"]
    purge_engine.state.relics.append("BottledFlame")
    purge_engine.state.bottled_cards = {"BottledFlame": 0}
    purge_shop = ShopEngine(purge_engine, ShopState())

    assert purge_shop.remove_card("Anger") == {"success": False, "reason": "card_cannot_be_removed"}

    combat_engine = RunEngine.create("PHASE278BOTTLECOMBAT", ascension=0)
    combat_engine.state.deck = ["Anger", "Defend", "Bash"]
    combat_engine.state.relics.append("BottledFlame")
    combat_engine.state.bottled_cards = {"BottledFlame": 0}
    combat_engine.start_combat_with_monsters(["Cultist"])
    assert combat_engine.state.combat is not None
    opening_hand = [card.card_id for card in combat_engine.state.combat.state.card_manager.hand.cards]

    assert "Anger" in opening_hand
    contexts = build_relic_contexts_from_engine(combat_engine)
    assert contexts["BottledFlame"]["selected_card_name"]
