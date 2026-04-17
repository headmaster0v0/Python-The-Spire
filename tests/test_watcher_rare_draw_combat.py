from __future__ import annotations

from sts_py.engine.combat.card_effects import DrawToHandLimitEffect, get_card_effects
from sts_py.engine.combat.card_piles import MAX_HAND_SIZE
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, hp: int = 80, attack_damage: int = 0):
        super().__init__(id="DummyAttack", name="Dummy Attack", hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hp: int = 80, attack_damage: int = 0) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monster = DummyAttackMonster(hp=monster_hp, attack_damage=attack_damage)
    return CombatEngine.create_with_monsters(
        monsters=[monster],
        player_hp=72,
        player_max_hp=72,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Strike", "Strike", "Strike", "Defend", "Defend", "Defend", "Defend", "Eruption", "Vigilance"],
        relics=[],
    )


def _bind_cards(combat: CombatEngine, cards: list[CardInstance]) -> list[CardInstance]:
    for card in cards:
        card._combat_state = combat.state
    return cards


def _set_piles(
    combat: CombatEngine,
    *,
    hand_ids: list[str] | None = None,
    draw_ids: list[str] | None = None,
    discard_cards: list[str | CardInstance] | None = None,
) -> None:
    combat.state.card_manager.hand.cards = _bind_cards(
        combat,
        [CardInstance(card_id) for card_id in (hand_ids or [])],
    )
    combat.state.card_manager.draw_pile.cards = _bind_cards(
        combat,
        [CardInstance(card_id) for card_id in (draw_ids or [])],
    )

    discard_instances: list[CardInstance] = []
    for card in discard_cards or []:
        instance = card if isinstance(card, CardInstance) else CardInstance(card)
        discard_instances.append(instance)
    combat.state.card_manager.discard_pile.cards = _bind_cards(combat, discard_instances)
    combat.state.card_manager.exhaust_pile.cards = []


class TestWatcherRareDrawEffects:
    def test_scrawl_effect_draws_until_hand_limit(self):
        effects = get_card_effects(CardInstance("Scrawl"))

        assert len(effects) == 1
        assert isinstance(effects[0], DrawToHandLimitEffect)

    def test_scrawl_upgrade_keeps_zero_cost(self):
        card = CardInstance("Scrawl", upgraded=True)

        assert card.cost == 0
        assert card.cost_for_turn == 0


class TestWatcherRareDrawIntegration:
    def test_scrawl_fills_hand_to_max_size(self):
        combat = _make_combat()
        draw_ids = (["Strike", "Defend"] * (MAX_HAND_SIZE + 1))[: MAX_HAND_SIZE + 2]
        _set_piles(combat, hand_ids=["Scrawl"], draw_ids=draw_ids)

        assert combat.play_card(0)

        assert combat.state.card_manager.get_hand_size() == MAX_HAND_SIZE
        assert all(card.card_id != "Scrawl" for card in combat.state.card_manager.hand.cards)

    def test_scrawl_shuffles_discard_when_draw_pile_is_empty(self):
        combat = _make_combat()
        discard_cards = [CardInstance("Strike") for _ in range(MAX_HAND_SIZE)]
        _set_piles(combat, hand_ids=["Scrawl"], draw_ids=[], discard_cards=discard_cards)

        assert combat.play_card(0)

        assert combat.state.card_manager.get_hand_size() == MAX_HAND_SIZE
        assert combat.state.card_manager.get_draw_pile_size() == 0
        assert any(card.card_id == "Scrawl" for card in combat.state.card_manager.exhaust_pile.cards)

    def test_scrawl_stops_cleanly_when_no_cards_remain(self):
        combat = _make_combat()
        _set_piles(combat, hand_ids=["Scrawl"], draw_ids=["Strike"], discard_cards=[])

        assert combat.play_card(0)

        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Strike"]
        assert combat.state.card_manager.get_draw_pile_size() == 0

    def test_scrawl_respects_no_draw(self):
        combat = _make_combat()
        _set_piles(combat, hand_ids=["Scrawl"], draw_ids=["Strike", "Defend"])
        combat.state.player.add_power(create_power("NoDraw", 1, "player"))

        assert combat.play_card(0)

        assert combat.state.card_manager.get_hand_size() == 0
        assert [card.card_id for card in combat.state.card_manager.draw_pile.cards] == ["Strike", "Defend"]

    def test_scrawl_keeps_deus_ex_machina_draw_trigger_working(self):
        combat = _make_combat()
        _set_piles(combat, hand_ids=["Scrawl"], draw_ids=["Strike", "DeusExMachina"])

        assert combat.play_card(0)

        hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
        assert hand_ids.count("Miracle") == 2
        assert "Strike" in hand_ids
        assert any(card.card_id == "DeusExMachina" for card in combat.state.card_manager.exhaust_pile.cards)

    def test_generate_cards_to_hand_overflow_goes_to_discard(self):
        combat = _make_combat()
        _set_piles(combat, hand_ids=["Strike"] * MAX_HAND_SIZE)

        generated = combat.state.card_manager.generate_cards_to_hand("Miracle", 2)

        assert len(generated) == 2
        assert combat.state.card_manager.get_hand_size() == MAX_HAND_SIZE
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Miracle", "Miracle"]

    def test_weave_stays_in_discard_when_hand_is_full(self):
        combat = _make_combat()
        weave = CardInstance("Weave")
        _set_piles(
            combat,
            hand_ids=["Strike"] * MAX_HAND_SIZE,
            draw_ids=["Burn"],
            discard_cards=[weave],
        )

        combat.state.card_manager.resolve_scry(1)

        assert combat.state.card_manager.get_hand_size() == MAX_HAND_SIZE
        assert weave in combat.state.card_manager.discard_pile.cards
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Weave", "Burn"]

    def test_meditate_recovery_path_respects_hand_limit(self):
        combat = _make_combat(attack_damage=0)
        discard_cards = [CardInstance("Wallop"), CardInstance("Eruption")]
        _set_piles(
            combat,
            hand_ids=["Meditate"] + ["Strike"] * (MAX_HAND_SIZE - 1),
            discard_cards=discard_cards,
        )

        recovered = combat.state.card_manager.recover_from_discard(2, hand_limit_offset=1)
        combat.state.card_manager.play_card(0)

        hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
        assert len(hand_ids) == MAX_HAND_SIZE
        assert len(recovered) == 1
        assert "Wallop" in hand_ids
        assert "Eruption" not in hand_ids
        assert any(card.card_id == "Eruption" for card in combat.state.card_manager.discard_pile.cards)
