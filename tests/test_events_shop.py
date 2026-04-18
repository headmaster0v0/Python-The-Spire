"""Event and shop system tests.

Tests the event and shop mechanics including:
- Event selection
- Event choice effects
- Shop generation
- Shop purchases
"""
from __future__ import annotations

import pytest

from sts_py.engine.run.run_engine import RunEngine, RunPhase, RoomType
from sts_py.engine.run.events import Event, EventChoice, EventEffect, EventEffectType, ACT1_EVENTS, ACT2_EVENTS, get_event_for_act
from sts_py.engine.run.shop import ShopState, ShopItem, ShopItemType, generate_colorless_cards, generate_shop


SEED_STRING = "1B40C4J3IIYDA"


class TestEventSystem:
    def test_event_has_choices(self):
        event = ACT1_EVENTS["Big Fish"]
        assert len(event.choices) >= 1
    
    def test_event_choice_description(self):
        event = ACT1_EVENTS["Big Fish"]
        assert event.choices[0].description != ""
    
    def test_get_event_for_act_returns_event(self):
        from sts_py.engine.core.rng import MutableRNG
        rng = MutableRNG.from_seed(12345, counter=0)
        event = get_event_for_act(1, rng)
        assert event is not None
        assert isinstance(event, Event)
    
    def test_event_get_choice_valid_index(self):
        event = ACT1_EVENTS["Big Fish"]
        choice = event.get_choice(0)
        assert choice is not None
        assert isinstance(choice, EventChoice)
    
    def test_event_get_choice_invalid_index(self):
        event = ACT1_EVENTS["Big Fish"]
        choice = event.get_choice(999)
        assert choice is None


class TestEventEffects:
    def test_gain_gold_effect(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        initial_gold = engine.state.player_gold
        
        effect = EventEffect(EventEffectType.GAIN_GOLD, amount=50)
        choice = EventChoice(description="test", effects=[effect])
        choice.apply(engine)
        
        assert engine.state.player_gold == initial_gold + 50
    
    def test_lose_gold_effect(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        initial_gold = engine.state.player_gold
        
        effect = EventEffect(EventEffectType.LOSE_GOLD, amount=30)
        choice = EventChoice(description="test", effects=[effect])
        choice.apply(engine)
        
        assert engine.state.player_gold == initial_gold - 30
    
    def test_lose_gold_cannot_go_negative(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.player_gold = 10
        
        effect = EventEffect(EventEffectType.LOSE_GOLD, amount=100)
        choice = EventChoice(description="test", effects=[effect])
        choice.apply(engine)
        
        assert engine.state.player_gold == 0
    
    def test_gain_hp_effect(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.player_hp = 50
        
        effect = EventEffect(EventEffectType.GAIN_HP, amount=20)
        choice = EventChoice(description="test", effects=[effect])
        choice.apply(engine)
        
        assert engine.state.player_hp == 70
    
    def test_gain_hp_cannot_exceed_max(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.player_hp = 75
        
        effect = EventEffect(EventEffectType.GAIN_HP, amount=20)
        choice = EventChoice(description="test", effects=[effect])
        choice.apply(engine)
        
        assert engine.state.player_hp == 80
    
    def test_lose_hp_effect(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        initial_hp = engine.state.player_hp
        
        effect = EventEffect(EventEffectType.LOSE_HP, amount=10)
        choice = EventChoice(description="test", effects=[effect])
        choice.apply(engine)
        
        assert engine.state.player_hp == initial_hp - 10
    
    def test_gain_max_hp_effect(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        initial_max = engine.state.player_max_hp
        
        effect = EventEffect(EventEffectType.GAIN_MAX_HP, amount=5)
        choice = EventChoice(description="test", effects=[effect])
        choice.apply(engine)
        
        assert engine.state.player_max_hp == initial_max + 5
        assert engine.state.player_hp == initial_max + 5
    
    def test_lose_max_hp_effect(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        initial_max = engine.state.player_max_hp
        
        effect = EventEffect(EventEffectType.LOSE_MAX_HP, amount=5)
        choice = EventChoice(description="test", effects=[effect])
        choice.apply(engine)
        
        assert engine.state.player_max_hp == initial_max - 5
    
    def test_gain_card_effect(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        initial_deck_size = len(engine.state.deck)
        
        effect = EventEffect(EventEffectType.GAIN_CARD, card_id="Anger")
        choice = EventChoice(description="test", effects=[effect])
        choice.apply(engine)
        
        assert len(engine.state.deck) == initial_deck_size + 1
        assert "Anger" in engine.state.deck

    def test_gain_card_effect_respects_amount(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        initial_deck_size = len(engine.state.deck)

        effect = EventEffect(EventEffectType.GAIN_CARD, amount=3, card_id="Bite")
        choice = EventChoice(description="test", effects=[effect])
        result = choice.apply(engine)

        assert len(engine.state.deck) == initial_deck_size + 3
        assert engine.state.deck.count("Bite") == 3
        assert result["effects_applied"][-1] == {"type": "gain_card", "card_id": "Bite", "count": 3}
    
    def test_gain_relic_effect(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        initial_relic_count = len(engine.state.relics)
        
        effect = EventEffect(EventEffectType.GAIN_RELIC, relic_id="Anchor")
        choice = EventChoice(description="test", effects=[effect])
        choice.apply(engine)
        
        assert len(engine.state.relics) == initial_relic_count + 1
        assert "Anchor" in engine.state.relics
        assert engine.get_pending_reward_state()["relic"] == "Anchor"
        assert engine.state.relic_history[-1] == {
            "floor": 0,
            "relic_id": "Anchor",
            "source": "event",
        }

    def test_trade_faces_effect_records_event_relic_history(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        choice = EventChoice(description="test", trade_faces=True)

        result = choice.apply(engine)
        mask = result["effects_applied"][0]["relic_obtained"]

        assert mask in engine.state.relics
        assert engine.get_pending_reward_state()["relic"] == mask
        assert engine.state.relic_history[-1] == {
            "floor": 0,
            "relic_id": mask,
            "source": "event",
        }

    def test_vampires_event_replaces_starter_strikes_with_bites(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.deck = ["Strike", "Strike+", "Bash", "Defend"]

        ACT2_EVENTS["Vampires"].choices[0].apply(engine)

        assert "Strike" not in engine.state.deck
        assert "Strike+" not in engine.state.deck
        assert engine.state.deck.count("Bite") == 5
        assert engine.state.player_max_hp == 56

    def test_ghost_event_grants_five_apparitions_below_ascension_15(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)

        ACT2_EVENTS["Ghost"].choices[0].apply(engine)

        assert engine.state.deck.count("Apparition") == 5
        assert engine.state.player_max_hp == 40

    def test_ghost_event_grants_three_apparitions_at_ascension_15(self):
        engine = RunEngine.create(SEED_STRING, ascension=15)

        ACT2_EVENTS["Ghost"].choices[0].apply(engine)

        assert engine.state.deck.count("Apparition") == 3
        assert engine.state.player_max_hp == 40


class TestShopGeneration:
    class _FixedShopRng:
        def __init__(self, ints: list[int], *, random_float: float = 0.5):
            self._ints = list(ints)
            self._random_float = random_float

        def random_int(self, upper: int) -> int:
            if self._ints:
                return max(0, min(upper, self._ints.pop(0)))
            return 0

        def random_float(self) -> float:
            return self._random_float

    def test_generate_shop_returns_shop_state(self):
        from sts_py.engine.core.rng import MutableRNG
        rng = MutableRNG.from_seed(12345, counter=0)
        shop = generate_shop(rng, act=1)
        
        assert isinstance(shop, ShopState)
        assert len(shop.colored_cards) == 5
        assert len(shop.colorless_cards) == 2
        assert len(shop.relics) == 3
        assert len(shop.potions) == 3

    def test_generate_colorless_cards_uses_real_colorless_runtime_pool(self):
        rng = TestShopGeneration._FixedShopRng([6, 2])

        cards = generate_colorless_cards(rng)

        assert [item.item_id for item in cards] == ["Madness", "MasterOfStrategy"]

    def test_generate_shop_preserves_injected_relics(self):
        from sts_py.engine.core.rng import MutableRNG

        rng = MutableRNG.from_seed(12345, counter=0)
        injected = [
            ShopItem(ShopItemType.RELIC, "Anchor", 150, tier="common"),
            ShopItem(ShopItemType.RELIC, "Lantern", 150, tier="common"),
            ShopItem(ShopItemType.RELIC, "MembershipCard", 150, tier="shop"),
        ]

        shop = generate_shop(rng, act=1, relics=injected)

        assert [item.item_id for item in shop.relics] == ["Anchor", "Lantern", "MembershipCard"]
    
    def test_shop_items_have_prices(self):
        from sts_py.engine.core.rng import MutableRNG
        rng = MutableRNG.from_seed(12345, counter=0)
        shop = generate_shop(rng, act=1)
        
        for card in shop.colored_cards:
            assert card.price > 0
            assert card.item_type == ShopItemType.CARD
        
        for relic in shop.relics:
            assert relic.price > 0
            assert relic.item_type == ShopItemType.RELIC
    
    def test_shop_card_remove_cost(self):
        from sts_py.engine.core.rng import MutableRNG
        rng = MutableRNG.from_seed(12345, counter=0)
        shop = generate_shop(rng, act=1)
        
        assert shop.card_remove_cost >= 75


class TestShopEngine:
    def test_buy_card_success(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.player_gold = 200
        
        from sts_py.engine.core.rng import MutableRNG
        rng = MutableRNG.from_seed(12345, counter=0)
        from sts_py.engine.run.shop import generate_shop, ShopEngine
        shop = generate_shop(rng, act=1)
        shop_engine = ShopEngine(engine, shop)
        
        initial_deck_size = len(engine.state.deck)
        result = shop_engine.buy_card(0)
        
        assert result["success"] == True
        assert len(engine.state.deck) == initial_deck_size + 1
    
    def test_buy_card_not_enough_gold(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.player_gold = 0
        
        from sts_py.engine.core.rng import MutableRNG
        rng = MutableRNG.from_seed(12345, counter=0)
        from sts_py.engine.run.shop import generate_shop, ShopEngine
        shop = generate_shop(rng, act=1)
        shop_engine = ShopEngine(engine, shop)
        
        result = shop_engine.buy_card(0)
        
        assert result["success"] == False
        assert result["reason"] == "not_enough_gold"
    
    def test_buy_card_already_sold(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.player_gold = 500
        
        from sts_py.engine.core.rng import MutableRNG
        rng = MutableRNG.from_seed(12345, counter=0)
        from sts_py.engine.run.shop import generate_shop, ShopEngine
        shop = generate_shop(rng, act=1)
        shop_engine = ShopEngine(engine, shop)
        
        shop_engine.buy_card(0)
        result = shop_engine.buy_card(0)
        
        assert result["success"] == False
        assert result["reason"] == "already_sold"
    
    def test_buy_relic_success(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.player_gold = 300
        
        from sts_py.engine.core.rng import MutableRNG
        rng = MutableRNG.from_seed(12345, counter=0)
        from sts_py.engine.run.shop import generate_shop, ShopEngine
        shop = generate_shop(rng, act=1)
        shop_engine = ShopEngine(engine, shop)
        
        initial_relic_count = len(engine.state.relics)
        result = shop_engine.buy_relic(0)
        
        assert result["success"] == True
        assert len(engine.state.relics) == initial_relic_count + 1
        assert engine.get_pending_reward_state()["relic"] == result["relic_id"]
        assert engine.state.relic_history[-1]["source"] == "shop"

    def test_buy_relic_with_courier_keeps_slot_available(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.player_gold = 999
        engine.state.relics.append("TheCourier")
        from sts_py.engine.run.shop import ShopEngine
        shop = ShopState(relics=[ShopItem(ShopItemType.RELIC, "Anchor", 150, tier="common")])
        shop_engine = ShopEngine(engine, shop)

        result = shop_engine.buy_relic(0)

        assert result["success"] == True
        assert "replacement_relic" in result
        assert len(shop_engine.get_available_relics()) == 1
    
    def test_remove_card_success(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.player_gold = 100
        engine.state.deck.append("Anger")
        
        from sts_py.engine.core.rng import MutableRNG
        rng = MutableRNG.from_seed(12345, counter=0)
        from sts_py.engine.run.shop import generate_shop, ShopEngine
        shop = generate_shop(rng, act=1)
        shop_engine = ShopEngine(engine, shop)
        
        initial_deck_size = len(engine.state.deck)
        result = shop_engine.remove_card("Anger")
        
        assert result["success"] == True
        assert len(engine.state.deck) == initial_deck_size - 1
    
    def test_remove_card_not_in_deck(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.player_gold = 100
        
        from sts_py.engine.core.rng import MutableRNG
        rng = MutableRNG.from_seed(12345, counter=0)
        from sts_py.engine.run.shop import generate_shop, ShopEngine
        shop = generate_shop(rng, act=1)
        shop_engine = ShopEngine(engine, shop)
        
        result = shop_engine.remove_card("NonExistentCard")
        
        assert result["success"] == False
        assert result["reason"] == "card_not_in_deck"


class TestRunEngineEventIntegration:
    def test_enter_event_room(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.map_nodes[0].room_type = RoomType.EVENT
        engine.choose_path(0)
        
        assert engine.state.phase == RunPhase.EVENT
    
    def test_get_event_choices_returns_list(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.map_nodes[0].room_type = RoomType.EVENT
        engine.choose_path(0)
        
        choices = engine.get_event_choices()
        assert isinstance(choices, list)
    
    def test_choose_event_option(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.map_nodes[0].room_type = RoomType.EVENT
        engine.choose_path(0)
        
        result = engine.choose_event_option(0)
        
        assert "success" in result or "effects_applied" in result
        if result.get("requires_card_choice"):
            card_index = 0
            engine.choose_card_for_event(card_index)
        assert engine.state.phase in (RunPhase.MAP, RunPhase.EVENT)

    def test_choose_generic_effect_event_option_does_not_crash(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.phase = RunPhase.EVENT
        engine._current_event = ACT1_EVENTS["Big Fish"]

        result = engine.choose_event_option(0)

        assert result["success"] is True
        assert result["event_continues"] is True
        assert engine.state.phase == RunPhase.EVENT

    def test_generic_choose_card_upgrade_replaces_selected_card(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.phase = RunPhase.EVENT
        engine.state.deck = ["SearingBlow+2"]
        engine._current_event = Event(
            id="Test Upgrade",
            name="Test Upgrade",
            choices=[EventChoice(description="upgrade", requires_card_upgrade=True)],
        )

        choice_result = engine.choose_event_option(0)

        assert choice_result["requires_card_choice"] is True
        upgrade_result = engine.choose_card_for_event(0)
        assert upgrade_result["success"] is True
        assert upgrade_result["action"] == "card_upgraded"
        assert upgrade_result["old_card"] == "SearingBlow+2"
        assert upgrade_result["new_card"] == "SearingBlow+3"
        assert engine.state.deck == ["SearingBlow+3"]

    def test_generic_choose_card_transform_replaces_selected_card(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.phase = RunPhase.EVENT
        engine.state.deck = ["Strike"]
        engine._current_event = Event(
            id="Test Transform",
            name="Test Transform",
            choices=[EventChoice(description="transform", requires_card_transform=True)],
        )

        choice_result = engine.choose_event_option(0)

        assert choice_result["requires_card_choice"] is True
        transform_result = engine.choose_card_for_event(0)
        assert transform_result["success"] is True
        assert transform_result["action"] == "card_transformed"
        assert transform_result["old_card"] == "Strike"
        assert engine.state.deck[0] == transform_result["new_card"]
        assert engine.state.deck[0] != "Strike"


class TestRunEngineShopIntegration:
    def test_enter_shop_room(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.map_nodes[0].room_type = RoomType.SHOP
        engine.choose_path(0)
        
        assert engine.state.phase == RunPhase.SHOP
    
    def test_get_shop_returns_engine(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.map_nodes[0].room_type = RoomType.SHOP
        engine.choose_path(0)
        
        shop = engine.get_shop()
        assert shop is not None
    
    def test_buy_card_through_engine(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.player_gold = 200
        engine.state.map_nodes[0].room_type = RoomType.SHOP
        engine.choose_path(0)
        
        initial_deck_size = len(engine.state.deck)
        result = engine.buy_card(0)
        
        assert result["success"] == True
        assert len(engine.state.deck) == initial_deck_size + 1
    
    def test_leave_shop(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.map_nodes[0].room_type = RoomType.SHOP
        engine.choose_path(0)
        
        engine.leave_shop()
        
        assert engine.state.phase == RunPhase.MAP
        assert engine.get_shop() is None
