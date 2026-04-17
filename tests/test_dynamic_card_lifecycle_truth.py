from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 50, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(
    *,
    deck: list[str] | None = None,
    monster_hps: list[int] | None = None,
    energy: int = 3,
    attack_damage: int = 0,
) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyAttackMonster(f"Dummy{index}", hp=hp, attack_damage=attack_damage)
        for index, hp in enumerate(monster_hps or [50])
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=70,
        player_max_hp=70,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=deck or ["AfterImage", "Adrenaline", "Prepared", "Predator", "Eviscerate"],
        relics=[],
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
    card_manager = combat.state.card_manager
    card_manager.hand.cards = _bind_cards(combat, hand_cards or [])
    card_manager.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    card_manager.discard_pile.cards = _bind_cards(combat, discard_cards or [])
    card_manager.exhaust_pile.cards = []


def test_after_image_plus_starts_in_opening_hand_but_keeps_cost_one() -> None:
    combat = _make_combat(
        deck=[
            "Strike",
            "Strike",
            "Strike",
            "Strike",
            "Strike",
            "Strike",
            "Defend",
            "Defend",
            "Defend",
            "Defend",
            "AfterImage+",
        ],
    )

    opening_hand = combat.state.card_manager.hand.cards
    after_image = next(card for card in opening_hand if card.card_id == "AfterImage")

    assert after_image.upgraded is True
    assert after_image.is_innate is True
    assert after_image.cost == 1
    assert after_image.cost_for_turn == 1


def test_adrenaline_draws_gains_energy_and_exhausts_without_leaving_choice_state() -> None:
    combat = _make_combat(energy=3, attack_damage=0)
    _set_piles(
        combat,
        hand_cards=[CardInstance("Adrenaline")],
        draw_cards=[CardInstance("Strike"), CardInstance("Defend")],
    )

    assert combat.play_card(0)

    assert combat.state.player.energy == 4
    assert combat.state.card_manager.energy == 4
    assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Defend", "Strike"]
    assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Adrenaline"]
    assert combat.state.pending_combat_choice is None


def test_prepared_plus_discard_flow_reduces_eviscerate_and_reduced_cost_survives_redraw() -> None:
    combat = _make_combat(energy=3, attack_damage=0)
    _set_piles(
        combat,
        hand_cards=[
            CardInstance("Prepared", upgraded=True),
            CardInstance("Strike"),
            CardInstance("Defend"),
            CardInstance("Eviscerate"),
        ],
        draw_cards=[CardInstance("Backflip"), CardInstance("Slice")],
    )

    assert combat.play_card(0)

    eviscerate = next(card for card in combat.state.card_manager.hand.cards if card.card_id == "Eviscerate")
    assert eviscerate.cost == 3
    assert eviscerate.cost_for_turn == 1
    assert eviscerate.combat_cost_reduction == 2
    assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Strike", "Defend", "Prepared"]

    combat.state.card_manager.hand.cards = []
    combat.state.card_manager.draw_pile.cards = [eviscerate]
    combat.state.card_manager.draw_card(combat.ai_rng)

    assert combat.state.card_manager.hand.cards[0] is eviscerate
    assert eviscerate.cost_for_turn == 1


def test_predator_draw_power_resolves_next_turn_post_draw_and_then_clears() -> None:
    combat = _make_combat(energy=2, attack_damage=0, monster_hps=[80])
    _set_piles(
        combat,
        hand_cards=[CardInstance("Predator")],
        draw_cards=[CardInstance("Strike") for _ in range(7)],
    )

    assert combat.play_card(0, 0)

    assert combat.state.monsters[0].hp == 65
    assert combat.state.player.get_power_amount("Draw Card") == 2
    assert combat.state.card_manager.get_hand_size() == 0

    combat.end_player_turn()

    assert combat.state.card_manager.get_hand_size() == 7
    assert combat.state.player.get_power_amount("Draw Card") == 0
