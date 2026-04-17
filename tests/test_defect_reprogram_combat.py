from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 40, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, energy: int = 3) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [DummyMonster("Dummy0", hp=40, attack_damage=0)]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=75,
        player_max_hp=75,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Reprogram"],
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


def _set_piles(combat: CombatEngine, *, hand_cards: list[CardInstance]) -> None:
    cm = combat.state.card_manager
    cm.hand.cards = _bind_cards(combat, hand_cards)
    cm.draw_pile.cards = []
    cm.discard_pile.cards = []
    cm.exhaust_pile.cards = []


class TestDefectReprogramCombat:
    def test_reprogram_applies_strength_dexterity_and_negative_focus(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Reprogram")])

        assert combat.play_card(0)

        assert combat.state.player.strength == 1
        assert combat.state.player.dexterity == 1
        assert combat.state.player.focus == -1
        assert combat.state.player.get_power_amount("Strength") == 1
        assert combat.state.player.get_power_amount("Dexterity") == 1
        assert combat.state.player.get_power_amount("Focus") == -1

    def test_reprogram_plus_uses_two_point_shift(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Reprogram", upgraded=True)])

        assert combat.play_card(0)

        assert combat.state.player.strength == 2
        assert combat.state.player.dexterity == 2
        assert combat.state.player.focus == -2
        assert combat.state.player.get_power_amount("Strength") == 2
        assert combat.state.player.get_power_amount("Dexterity") == 2
        assert combat.state.player.get_power_amount("Focus") == -2
