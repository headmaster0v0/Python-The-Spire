from __future__ import annotations

from sts_py.engine.combat.card_effects import _implemented_colorless_combat_card_ids
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 120):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=0, name="Attack"))


def _make_combat(
    *,
    monster_hps: list[int],
    energy: int = 3,
    relics: list[str] | None = None,
) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [DummyAttackMonster(f"Dummy{index}", hp=hp) for index, hp in enumerate(monster_hps)]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=72,
        player_max_hp=72,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Malaise", "ConjureBlade", "Expunger", "Transmutation"],
        relics=relics or [],
    )
    combat.state.player.energy = energy
    combat.state.player.max_energy = energy
    combat.state.card_manager.set_energy(energy)
    combat.state.card_manager.set_max_energy(energy)
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
) -> None:
    card_manager = combat.state.card_manager
    card_manager.hand.cards = _bind_cards(combat, hand_cards or [])
    card_manager.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    card_manager.discard_pile.cards = []
    card_manager.exhaust_pile.cards = []


def test_malaise_free_to_play_keeps_energy_but_chemical_x_still_increases_effect_value() -> None:
    combat = _make_combat(monster_hps=[80], energy=3, relics=["ChemicalX"])
    malaise = CardInstance("Malaise", upgraded=True)
    malaise.free_to_play_once = True
    _set_piles(combat, hand_cards=[malaise], draw_cards=[])

    assert combat.play_card(0, 0)

    target = combat.state.monsters[0]
    assert combat.state.player.energy == 3
    assert target.get_power_amount("Weak") == 3
    assert target.strength == -3
    assert target.get_power_amount("Lose Strength") == 3


def test_conjure_blade_uses_effect_side_x_for_expunger_metadata() -> None:
    combat = _make_combat(monster_hps=[120], energy=2, relics=["ChemicalX"])
    _set_piles(combat, hand_cards=[CardInstance("ConjureBlade", upgraded=True)], draw_cards=[])

    assert combat.play_card(0)

    expunger = combat.state.card_manager.draw_pile.cards[0]
    assert combat.state.player.energy == 0
    assert expunger.card_id == "Expunger"
    assert expunger.upgraded is False
    assert expunger.misc == 5
    assert expunger.base_magic_number == 5
    assert expunger.magic_number == 5
    assert expunger.base_damage == 9
    assert expunger.damage == 9


def test_expunger_hits_only_selected_target_for_its_full_hit_count() -> None:
    combat = _make_combat(monster_hps=[200, 200], energy=3)
    expunger = CardInstance("Expunger")
    expunger.base_magic_number = 3
    expunger.magic_number = 3
    _set_piles(combat, hand_cards=[expunger], draw_cards=[])

    assert combat.play_card(0, 1)

    assert combat.state.monsters[0].hp == 200
    assert combat.state.monsters[1].hp == 173


def test_transmutation_free_to_play_uses_effect_x_for_generated_cards_without_spending_energy() -> None:
    combat = _make_combat(monster_hps=[80], energy=3, relics=["ChemicalX"])
    transmutation = CardInstance("Transmutation", upgraded=True)
    transmutation.free_to_play_once = True
    _set_piles(combat, hand_cards=[transmutation], draw_cards=[])

    assert combat.play_card(0)

    legal_pool = set(_implemented_colorless_combat_card_ids())
    generated = combat.state.card_manager.hand.cards

    assert combat.state.player.energy == 3
    assert len(generated) == 2
    assert all(card.card_id in legal_pool for card in generated)
    assert all(card.upgraded is True for card in generated)
    assert all(card.cost_for_turn == 0 for card in generated)
