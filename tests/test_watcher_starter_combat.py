from __future__ import annotations

from sts_py.engine.combat.card_effects import (
    ChangeStanceEffect,
    DealDamageEffect,
    GainBlockEffect,
    GainEnergyEffect,
    get_card_effects,
)
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.stance import StanceType
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, hp: int = 80, attack_damage: int = 10):
        super().__init__(id="DummyAttack", name="Dummy Attack", hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, relics: list[str] | None = None, monster_hp: int = 80, attack_damage: int = 10) -> CombatEngine:
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
        relics=relics or [],
    )


def _set_hand(combat: CombatEngine, card_ids: list[str]) -> None:
    cards = [CardInstance(card_id) for card_id in card_ids]
    for card in cards:
        card._combat_state = combat.state
    combat.state.card_manager.hand.cards = cards
    combat.state.card_manager.draw_pile.cards = []
    combat.state.card_manager.discard_pile.cards = []
    combat.state.card_manager.exhaust_pile.cards = []


class TestWatcherStarterCardEffects:
    def test_miracle_effects_gain_energy(self):
        effects = get_card_effects(CardInstance("Miracle"))

        assert len(effects) == 1
        assert isinstance(effects[0], GainEnergyEffect)
        assert effects[0].amount == 1

    def test_eruption_effects_damage_then_wrath(self):
        effects = get_card_effects(CardInstance("Eruption"), target_idx=0)

        assert len(effects) == 2
        assert isinstance(effects[0], DealDamageEffect)
        assert isinstance(effects[1], ChangeStanceEffect)
        assert effects[1].stance_type == StanceType.WRATH

    def test_vigilance_effects_block_then_calm(self):
        effects = get_card_effects(CardInstance("Vigilance"))

        assert len(effects) == 2
        assert isinstance(effects[0], GainBlockEffect)
        assert isinstance(effects[1], ChangeStanceEffect)
        assert effects[1].stance_type == StanceType.CALM

    def test_watcher_starter_alias_effects_work(self):
        strike_effects = get_card_effects(CardInstance("Strike_P"), target_idx=0)
        defend_effects = get_card_effects(CardInstance("Defend_P"))

        assert len(strike_effects) == 1
        assert isinstance(strike_effects[0], DealDamageEffect)
        assert len(defend_effects) == 1
        assert isinstance(defend_effects[0], GainBlockEffect)


class TestWatcherStarterCombatIntegration:
    def test_miracle_grants_energy_and_exhausts(self):
        combat = _make_combat()
        _set_hand(combat, ["Miracle"])

        initial_energy = combat.state.player.energy

        assert combat.play_card(0)
        assert combat.state.player.energy == initial_energy + 1
        assert combat.state.card_manager.get_exhaust_pile_size() == 1
        assert combat.state.card_manager.exhaust_pile.cards[0].card_id == "Miracle"

    def test_eruption_enters_wrath_and_buffs_next_attack(self):
        combat = _make_combat(monster_hp=80)
        _set_hand(combat, ["Eruption", "Strike"])
        monster = combat.state.monsters[0]

        initial_hp = monster.hp
        assert combat.play_card(0, 0)
        assert combat.state.player.stance is not None
        assert combat.state.player.stance.stance_type == StanceType.WRATH
        assert monster.hp == initial_hp - 9

        hp_after_eruption = monster.hp
        assert combat.play_card(0, 0)
        assert monster.hp == hp_after_eruption - 12

    def test_wrath_increases_incoming_attack_damage(self):
        combat = _make_combat(attack_damage=10)
        _set_hand(combat, ["Eruption"])

        assert combat.play_card(0, 0)
        combat.end_player_turn()

        assert combat.state.player.hp == 52

    def test_vigilance_then_eruption_exits_calm_for_energy(self):
        combat = _make_combat(monster_hp=120)
        _set_hand(combat, ["Vigilance", "Miracle", "Eruption"])

        assert combat.play_card(0)
        assert combat.state.player.energy == 1
        assert combat.state.player.stance is not None
        assert combat.state.player.stance.stance_type == StanceType.CALM

        assert combat.play_card(0)
        assert combat.state.player.energy == 2

        assert combat.play_card(0, 0)
        assert combat.state.player.stance is not None
        assert combat.state.player.stance.stance_type == StanceType.WRATH
        assert combat.state.player.energy == 2

    def test_pure_water_adds_miracle_to_opening_hand(self):
        combat = _make_combat(relics=["PureWater"])

        hand_ids = [card.card_id for card in combat.state.card_manager.get_hand()]

        assert "Miracle" in hand_ids
        assert combat.state.card_manager.get_hand_size() == 6
