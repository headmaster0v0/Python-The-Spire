from __future__ import annotations

from sts_py.engine.combat.card_effects import (
    ApplyPowerEffect,
    DrawCardsEffect,
    FeedEffect,
    GainEnergyEffect,
    LoseHPEffect,
    get_card_effects,
)
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.run.run_engine import RunEngine, RunPhase


SEED_STRING = "1B40C4J3IIYDA"
SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, hp: int = 120, attack_damage: int = 0):
        super().__init__(id="DummyAttack", name="Dummy Attack", hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hp: int = 120, attack_damage: int = 0) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monster = DummyAttackMonster(hp=monster_hp, attack_damage=attack_damage)
    return CombatEngine.create_with_monsters(
        monsters=[monster],
        player_hp=80,
        player_max_hp=80,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Strike", "Strike", "Strike", "Defend", "Defend", "Bash", "ShrugItOff", "PommelStrike", "TrueGrit"],
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
    discard_cards: list[CardInstance] | None = None,
) -> None:
    cm = combat.state.card_manager
    cm.hand.cards = _bind_cards(combat, hand_cards or [])
    cm.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    cm.discard_pile.cards = _bind_cards(combat, discard_cards or [])
    cm.exhaust_pile.cards = []


class TestIroncladRareFinisherEffects:
    def test_feed_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("Feed"), target_idx=0)

        assert len(effects) == 1
        assert isinstance(effects[0], FeedEffect)

    def test_offering_effect_mapping_matches_hp_energy_and_draw(self):
        effects = get_card_effects(CardInstance("Offering"))

        assert [type(effect) for effect in effects] == [LoseHPEffect, GainEnergyEffect, DrawCardsEffect]
        assert effects[0].amount == 6
        assert effects[1].amount == 2

    def test_demon_form_applies_power_effect(self):
        effects = get_card_effects(CardInstance("DemonForm"))

        assert len(effects) == 1
        assert isinstance(effects[0], ApplyPowerEffect)
        assert effects[0].power_type == "DemonForm"
        assert effects[0].amount == 2


class TestIroncladRareFinisherIntegration:
    def test_demon_form_applies_power(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("DemonForm")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("DemonForm") == 2

    def test_demon_form_power_grants_strength_each_turn(self):
        combat = _make_combat(attack_damage=0)
        combat.state.player.add_power(create_power("DemonForm", 2, "player"))
        _set_piles(combat, hand_cards=[], draw_cards=[CardInstance("Strike")] * 6)

        combat.end_player_turn()

        assert combat.state.player.strength == 2
        assert combat.state.player.get_power_amount("Strength") == 2

    def test_stacked_demon_form_accelerates_strength_gain(self):
        combat = _make_combat(attack_damage=0)
        combat.state.player.add_power(create_power("DemonForm", 2, "player"))
        combat.state.player.add_power(create_power("DemonForm", 2, "player"))
        _set_piles(combat, hand_cards=[], draw_cards=[CardInstance("Strike")] * 6)

        combat.end_player_turn()

        assert combat.state.player.get_power_amount("DemonForm") == 4
        assert combat.state.player.strength == 4
        assert combat.state.player.get_power_amount("Strength") == 4

    def test_offering_loses_hp_gains_energy_draws_and_exhausts(self):
        combat = _make_combat()
        combat.state.player.energy = 3
        combat.state.card_manager.set_energy(3)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Offering")],
            draw_cards=[CardInstance("Strike"), CardInstance("Defend"), CardInstance("Bash")],
        )

        assert combat.play_card(0)

        assert combat.state.player.hp == 74
        assert combat.state.player.energy == 5
        assert combat.state.card_manager.energy == 5
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Bash", "Defend", "Strike"]
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Offering"]

    def test_offering_triggers_rupture_on_hp_loss(self):
        combat = _make_combat()
        combat.state.player.add_power(create_power("Rupture", 1, "player"))
        _set_piles(
            combat,
            hand_cards=[CardInstance("Offering")],
            draw_cards=[CardInstance("Strike"), CardInstance("Defend"), CardInstance("Bash")],
        )

        assert combat.play_card(0)

        assert combat.state.player.hp == 74
        assert combat.state.player.strength == 1
        assert combat.state.player.get_power_amount("Strength") == 1

    def test_feed_kill_increases_combat_max_hp_and_current_hp(self):
        combat = _make_combat(monster_hp=10)
        combat.state.player.hp = 70
        _set_piles(combat, hand_cards=[CardInstance("Feed")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.player.max_hp == 83
        assert combat.state.player.hp == 73
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Feed"]

    def test_feed_nonlethal_does_not_increase_max_hp(self):
        combat = _make_combat(monster_hp=20)
        combat.state.player.hp = 70
        _set_piles(combat, hand_cards=[CardInstance("Feed")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.player.max_hp == 80
        assert combat.state.player.hp == 70


class TestIroncladRareFinisherRunSync:
    def test_feed_end_combat_syncs_max_hp_back_to_run_state(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        combat = _make_combat(monster_hp=10)
        combat.state.player.hp = 70
        _set_piles(combat, hand_cards=[CardInstance("Feed")], draw_cards=[])
        engine.state.combat = combat
        engine.state.phase = RunPhase.COMBAT

        assert combat.play_card(0, 0)
        assert combat.player_won()

        engine.end_combat()

        assert engine.state.player_max_hp == 83
        assert engine.state.player_hp == 73
        assert engine.state.phase == RunPhase.REWARD

    def test_offering_does_not_change_run_max_hp(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        combat = _make_combat(monster_hp=10, attack_damage=0)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Offering"), CardInstance("Feed")],
            draw_cards=[CardInstance("Strike"), CardInstance("Defend"), CardInstance("Bash")],
        )
        engine.state.combat = combat
        engine.state.phase = RunPhase.COMBAT

        assert combat.play_card(0)
        assert combat.play_card(0, 0)
        assert combat.player_won()

        engine.end_combat()

        assert engine.state.player_max_hp == 83
        assert engine.state.player_hp == 77
