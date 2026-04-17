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
        deck=["CloakAndDagger", "BladeDance", "InfiniteBlades"],
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


class TestSilentShivDiscardFoundation:
    def test_shiv_instantiates_with_formal_special_metadata(self):
        shiv = CardInstance("Shiv")

        assert shiv.card_id == "Shiv"
        assert shiv.cost == 0
        assert shiv.damage == 4
        assert shiv.is_attack()
        assert shiv.exhaust is True

    def test_cloak_and_dagger_gains_block_and_adds_shiv(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("CloakAndDagger")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.block == 6
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Shiv"]

    def test_cloak_and_dagger_plus_adds_two_shivs(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("CloakAndDagger", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.block == 8
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Shiv", "Shiv"]

    def test_blade_dance_creates_three_shivs(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("BladeDance")], draw_cards=[])

        assert combat.play_card(0)

        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Shiv", "Shiv", "Shiv"]

    def test_blade_dance_plus_creates_four_shivs(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("BladeDance", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)

        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Shiv", "Shiv", "Shiv", "Shiv"]

    def test_infinite_blades_applies_power(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("InfiniteBlades")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.get_power_amount("InfiniteBlades") == 1

    def test_infinite_blades_generates_shiv_next_turn(self):
        combat = _make_combat(attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("InfiniteBlades")], draw_cards=[CardInstance("Strike")] * 5)

        assert combat.play_card(0)
        combat.end_player_turn()

        assert any(card.card_id == "Shiv" for card in combat.state.card_manager.hand.cards)
