from __future__ import annotations

from sts_py.engine.combat.card_effects import ApplyPowerEffect, get_card_effects
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
    hand_cards: list[CardInstance] | None = None,
    draw_cards: list[CardInstance] | None = None,
) -> None:
    combat.state.card_manager.hand.cards = _bind_cards(combat, hand_cards or [])
    combat.state.card_manager.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    combat.state.card_manager.discard_pile.cards = []
    combat.state.card_manager.exhaust_pile.cards = []


class TestWatcherEnergyRampEffects:
    def test_deva_form_effect_applies_deva_power(self):
        effects = get_card_effects(CardInstance("DevaForm"))

        assert len(effects) == 1
        assert isinstance(effects[0], ApplyPowerEffect)
        assert effects[0].power_type == "DevaPower"
        assert effects[0].amount == 1

    def test_deva_form_metadata_tracks_ethereal_upgrade(self):
        card = CardInstance("DevaForm")
        upgraded = CardInstance("DevaForm", upgraded=True)

        assert card.is_ethereal is True
        assert upgraded.is_ethereal is False


class TestWatcherEnergyRampIntegration:
    def test_deva_form_applies_power(self):
        combat = _make_combat(attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("DevaForm")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("DevaPower") == 1

    def test_deva_power_grants_incrementing_energy_each_turn(self):
        combat = _make_combat(attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("DevaForm")], draw_cards=[])

        assert combat.play_card(0)

        combat.end_player_turn()
        assert combat.state.player.energy == combat.state.player.max_energy + 1
        assert combat.state.card_manager.energy == combat.state.player.max_energy + 1

        combat.end_player_turn()
        assert combat.state.player.energy == combat.state.player.max_energy + 2
        assert combat.state.card_manager.energy == combat.state.player.max_energy + 2

    def test_stacked_deva_power_accelerates_energy_gain(self):
        combat = _make_combat(attack_damage=0)
        combat.state.player.add_power(create_power("DevaPower", 1, "player"))
        combat.state.player.add_power(create_power("DevaPower", 1, "player"))

        assert combat.state.player.get_power_amount("DevaPower") == 2

        combat.end_player_turn()
        assert combat.state.player.energy == combat.state.player.max_energy + 2

        combat.end_player_turn()
        assert combat.state.player.energy == combat.state.player.max_energy + 4

    def test_deva_form_plus_is_discarded_instead_of_exhausted_at_end_of_turn(self):
        combat = _make_combat(attack_damage=0)
        _set_piles(
            combat,
            hand_cards=[CardInstance("DevaForm", upgraded=True)],
            draw_cards=[CardInstance("Strike"), CardInstance("Strike"), CardInstance("Strike"), CardInstance("Strike"), CardInstance("Strike")],
        )

        combat.end_player_turn()

        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["DevaForm"]
        assert combat.state.card_manager.exhaust_pile.cards == []
