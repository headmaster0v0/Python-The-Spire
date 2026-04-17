from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 40, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hps: list[int] | None = None, energy: int = 3, relics: list[str] | None = None, attack_damage: int = 0) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyAttackMonster(f"Dummy{index}", hp=hp, attack_damage=attack_damage)
        for index, hp in enumerate(monster_hps or [40])
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=70,
        player_max_hp=70,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["DaggerThrow", "SneakyStrike", "Eviscerate", "Concentrate", "CalculatedGamble"],
        relics=relics or [],
    )
    combat.state.player.max_energy = energy
    combat.state.player.energy = energy
    combat.state.card_manager.set_max_energy(energy)
    combat.state.card_manager.set_energy(energy)
    return combat


def _bind_cards(combat: CombatEngine, cards: list[CardInstance]) -> list[CardInstance]:
    for card in cards:
        card._combat_state = combat.state
    return cards


def _set_piles(
    combat: CombatEngine,
    *,
    hand_cards: list[CardInstance] | None = None,
    draw_cards: list[CardInstance] | None = None,
    discard_cards: list[CardInstance] | None = None,
) -> None:
    cm = combat.state.card_manager
    cm.hand.cards = _bind_cards(combat, hand_cards or [])
    cm.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    cm.discard_pile.cards = _bind_cards(combat, discard_cards or [])
    cm.exhaust_pile.cards = []


class TestSilentDiscardPayoffCombat:
    def test_dagger_throw_deals_damage_then_discards_one(self):
        combat = _make_combat()
        _set_piles(
            combat,
            hand_cards=[CardInstance("DaggerThrow"), CardInstance("Strike")],
            draw_cards=[],
        )

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 31
        assert combat.state.card_manager.hand.cards == []
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Strike", "DaggerThrow"]

    def test_sneaky_strike_refunds_energy_if_discard_happened_this_turn(self):
        combat = _make_combat()
        combat.state.player._discards_this_turn = 1
        _set_piles(combat, hand_cards=[CardInstance("SneakyStrike")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.player.energy == 3
        assert combat.state.card_manager.energy == 3

    def test_sneaky_strike_without_discard_gives_no_refund(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("SneakyStrike")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.player.energy == 1

    def test_eviscerate_cost_reduces_across_combat_and_sticks_to_instance(self):
        combat = _make_combat()
        eviscerate = CardInstance("Eviscerate")
        _set_piles(combat, hand_cards=[eviscerate], draw_cards=[CardInstance("Strike")], discard_cards=[])

        assert eviscerate.cost_for_turn == 3

        combat._handle_player_discard_from_hand(CardInstance("Strike"))
        combat._handle_player_discard_from_hand(CardInstance("Strike"))

        assert eviscerate.cost_for_turn == 1

        combat.state.card_manager.discard_pile.add(eviscerate)
        combat.state.card_manager.hand.cards = []
        combat.state.card_manager.draw_pile.cards = [eviscerate]
        combat.state.card_manager.draw_card(combat.ai_rng)

        assert combat.state.card_manager.hand.cards[0] is eviscerate
        assert eviscerate.cost_for_turn == 1

    def test_eviscerate_cost_never_goes_below_zero(self):
        combat = _make_combat()
        eviscerate = CardInstance("Eviscerate")
        _set_piles(combat, hand_cards=[eviscerate], draw_cards=[])

        for _ in range(10):
            combat._handle_player_discard_from_hand(CardInstance("Strike"))

        assert eviscerate.cost_for_turn == 0

    def test_concentrate_discards_and_gains_energy(self):
        combat = _make_combat()
        _set_piles(
            combat,
            hand_cards=[CardInstance("Concentrate"), CardInstance("Strike"), CardInstance("Defend"), CardInstance("Slice")],
            draw_cards=[],
        )

        assert combat.play_card(0)

        assert combat.state.player.energy == 5
        assert combat.state.card_manager.energy == 5
        assert combat.state.card_manager.hand.cards == []

    def test_concentrate_noops_if_not_enough_other_cards(self):
        combat = _make_combat()
        _set_piles(
            combat,
            hand_cards=[CardInstance("Concentrate"), CardInstance("Strike")],
            draw_cards=[],
        )

        assert combat.play_card(0)

        assert combat.state.player.energy == 3
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Strike"]

    def test_calculated_gamble_discards_other_hand_and_draws_same_count(self):
        combat = _make_combat()
        _set_piles(
            combat,
            hand_cards=[CardInstance("CalculatedGamble"), CardInstance("Strike"), CardInstance("Defend")],
            draw_cards=[CardInstance("Slice"), CardInstance("Prepared")],
        )

        assert combat.play_card(0)

        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Prepared", "Slice"]
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["CalculatedGamble"]

    def test_calculated_gamble_respects_no_draw(self):
        combat = _make_combat()
        combat.state.player.add_power(__import__("sts_py.engine.combat.powers", fromlist=["create_power"]).create_power("No Draw", 1, "player"))
        _set_piles(
            combat,
            hand_cards=[CardInstance("CalculatedGamble"), CardInstance("Strike"), CardInstance("Defend")],
            draw_cards=[CardInstance("Slice"), CardInstance("Prepared")],
        )

        assert combat.play_card(0)

        assert combat.state.card_manager.hand.cards == []

    def test_discard_payoff_cards_continue_to_work_with_discard_relics(self):
        combat = _make_combat(monster_hps=[30], relics=["Tingsha", "ToughBandages", "HoveringKite"])
        _set_piles(
            combat,
            hand_cards=[CardInstance("DaggerThrow"), CardInstance("Strike")],
            draw_cards=[],
        )

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 18
        assert combat.state.player.block == 3
        assert combat.state.player.energy == 3
