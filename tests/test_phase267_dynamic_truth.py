from __future__ import annotations

from sts_py.engine.combat.potion_effects import use_potion
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.potions import create_potion
from sts_py.engine.run.events import Event, EventChoice
from sts_py.engine.run.run_engine import MapNode, RoomType, RunEngine, RunPhase
from sts_py.engine.run.shop import ShopEngine, ShopItem, ShopItemType, ShopState


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


def test_phase267_reward_mutation_family_keeps_prayer_wheel_and_black_star_live() -> None:
    monster_engine = RunEngine.create("PHASE267PRAYERWHEEL", ascension=0)
    monster_engine.state.relics.append("PrayerWheel")
    _start_room_combat(monster_engine, RoomType.MONSTER, "Cultist")
    _force_win_current_combat(monster_engine)

    assert len(monster_engine.state.pending_card_reward_cards) == 4

    elite_engine = RunEngine.create("PHASE267BLACKSTAR", ascension=0)
    elite_engine.state.relics.append("BlackStar")
    _start_room_combat(elite_engine, RoomType.ELITE, "Gremlin Nob")
    _force_win_current_combat(elite_engine)
    pending = elite_engine.get_pending_reward_state()

    assert len(pending["relics"]) == 2
    assert [entry["source"] for entry in elite_engine.state.relic_history[-2:]] == ["elite", "elite"]


def test_phase267_shop_lane_keeps_courier_restock_and_smiling_mask_remove_truth() -> None:
    courier_engine = RunEngine.create("PHASE267COURIER", ascension=0)
    courier_engine.state.player_gold = 999
    courier_engine.state.relics.append("TheCourier")
    shop = ShopState(
        colorless_cards=[ShopItem(ShopItemType.CARD, "Offering", 150)],
        relics=[ShopItem(ShopItemType.RELIC, "Anchor", 150, tier="common")],
        potions=[ShopItem(ShopItemType.POTION, "BlockPotion", 50, tier="common")],
    )
    courier_shop = ShopEngine(courier_engine, shop)

    colorless_result = courier_shop.buy_card(0, is_colored=False)
    relic_result = courier_shop.buy_relic(0)
    potion_result = courier_shop.buy_potion(0)

    assert colorless_result["success"] is True
    assert "replacement_card" in colorless_result
    assert relic_result["success"] is True
    assert "replacement_relic" in relic_result
    assert potion_result["success"] is True
    assert "replacement_potion" in potion_result
    assert len(courier_shop.get_available_cards()) == 1
    assert len(courier_shop.get_available_relics()) == 1
    assert len(courier_shop.get_available_potions()) == 1

    smiling_engine = RunEngine.create("PHASE267SMILING", ascension=0)
    smiling_engine.state.player_gold = 999
    smiling_engine.state.relics.append("SmilingMask")
    smiling_engine.state.deck.append("Anger")
    smiling_shop = ShopEngine(smiling_engine, ShopState())
    remove_result = smiling_shop.remove_card("Anger")

    assert smiling_shop.get_card_remove_price() == 50
    assert remove_result["success"] is True
    assert remove_result["price_paid"] == 50
    assert "Anger" not in smiling_engine.state.deck


def test_phase267_potion_and_relic_callback_family_remains_live() -> None:
    engine = RunEngine.create("PHASE267POTIONS", ascension=0)
    engine.state.relics.append("MagicFlower")
    engine.start_combat_with_monsters(["Cultist"])
    combat = engine.state.combat
    assert combat is not None

    combat.state.player.hp = 50
    blood_potion = create_potion("BloodPotion")
    entropic_brew = create_potion("EntropicBrew")

    assert blood_potion is not None
    use_potion(blood_potion, combat.state)
    assert combat.state.player.hp == 74

    engine.state.potions = ["BlockPotion", "EmptyPotionSlot", "EmptyPotionSlot"]
    assert entropic_brew is not None
    use_potion(entropic_brew, combat.state)
    assert engine.state.potions[0] == "BlockPotion"
    assert all(slot != "EmptyPotionSlot" for slot in engine.state.potions[1:])


def test_phase267_monster_state_and_event_branching_family_remains_live() -> None:
    combat_engine = RunEngine.create("PHASE267DARKLING", ascension=0)
    combat_engine.start_combat_with_monsters(["Darkling", "Darkling", "Darkling"])
    combat = combat_engine.state.combat
    assert combat is not None
    combat.state.player.energy = 2
    combat.state.monsters[0].hp = 5
    combat.state.card_manager.hand.cards = [CardInstance("HandOfGreed")]
    combat.state.card_manager.draw_pile.cards = []

    assert combat.play_card(0, 0)
    assert combat.state.monsters[0].half_dead is True
    assert combat.state.pending_bonus_gold == 0

    remove_engine = RunEngine.create("PHASE267EVENTREMOVE", ascension=0)
    remove_engine.state.phase = RunPhase.EVENT
    remove_engine.state.deck = ["Strike", "Defend", "Bash"]
    remove_engine._current_event = Event(
        id="Phase267 Remove",
        name="Phase267 Remove",
        choices=[EventChoice(description="remove", description_cn="[移除]", requires_card_removal=True)],
    )
    assert remove_engine.choose_event_option(0)["requires_card_choice"] is True
    remove_result = remove_engine.choose_card_for_event(0)
    assert remove_result["success"] is True
    assert remove_result["card_id"] == "Strike"

    upgrade_engine = RunEngine.create("PHASE267EVENTUPGRADE", ascension=0)
    upgrade_engine.state.phase = RunPhase.EVENT
    upgrade_engine.state.deck = ["Bash", "Defend"]
    upgrade_engine._current_event = Event(
        id="Phase267 Upgrade",
        name="Phase267 Upgrade",
        choices=[EventChoice(description="upgrade", description_cn="[升级]", requires_card_upgrade=True)],
    )
    assert upgrade_engine.choose_event_option(0)["requires_card_choice"] is True
    upgrade_result = upgrade_engine.choose_card_for_event(0)
    assert upgrade_result["success"] is True
    assert upgrade_result["new_card"] == "Bash+"

    transform_engine = RunEngine.create("PHASE267EVENTTRANSFORM", ascension=0)
    transform_engine.state.phase = RunPhase.EVENT
    transform_engine.state.deck = ["Strike"]
    transform_engine._current_event = Event(
        id="Phase267 Transform",
        name="Phase267 Transform",
        choices=[EventChoice(description="transform", description_cn="[变形]", requires_card_transform=True)],
    )
    assert transform_engine.choose_event_option(0)["requires_card_choice"] is True
    transform_result = transform_engine.choose_card_for_event(0)
    assert transform_result["success"] is True
    assert transform_result["old_card"] == "Strike"
    assert transform_result["new_card"] != "Strike"
