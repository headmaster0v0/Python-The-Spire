from __future__ import annotations

from sts_py.engine.combat.card_effects import ApplyPowerEffect, GainBlockEffect, get_card_effects
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, hp: int = 120, attack_damage: int = 0):
        super().__init__(id="DummyAttack", name="Dummy Attack", hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hp: int = 120, attack_damage: int = 0, monster_count: int = 1) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [DummyAttackMonster(hp=monster_hp, attack_damage=attack_damage) for _ in range(monster_count)]
    return CombatEngine.create_with_monsters(
        monsters=monsters,
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


class TestIroncladSelfDamagePowerEffects:
    def test_combust_maps_to_apply_power(self):
        effects = get_card_effects(CardInstance("Combust"))

        assert len(effects) == 1
        assert isinstance(effects[0], ApplyPowerEffect)
        assert effects[0].power_type == "Combust"

    def test_impervious_maps_to_gain_block(self):
        effects = get_card_effects(CardInstance("Impervious"))

        assert len(effects) == 1
        assert isinstance(effects[0], GainBlockEffect)
        assert effects[0].amount == 30


class TestIroncladSelfDamagePowerIntegration:
    def test_combust_applies_power(self):
        combat = _make_combat(monster_hp=30, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Combust")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Combust") == 5

    def test_combust_end_of_turn_loses_hp_and_hits_all_monsters(self):
        combat = _make_combat(monster_hp=30, attack_damage=0, monster_count=2)
        _set_piles(combat, hand_cards=[CardInstance("Combust")], draw_cards=[])

        assert combat.play_card(0)
        combat.end_player_turn()

        assert combat.state.player.hp == 79
        assert [monster.hp for monster in combat.state.monsters] == [25, 25]

    def test_berserk_applies_vulnerable_and_enrage(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Berserk")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.get_power_amount("Vulnerable") == 2
        assert combat.state.player.get_power_amount("Enrage") == 1

    def test_enrage_gains_strength_on_skill_play(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Berserk"), CardInstance("Defend")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.play_card(0)

        assert combat.state.player.strength == 1
        assert combat.state.player.get_power_amount("Strength") == 1

    def test_enrage_does_not_trigger_on_non_skill(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Berserk"), CardInstance("Strike")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.play_card(0, 0)

        assert combat.state.player.strength == 0
        assert combat.state.player.get_power_amount("Strength") == 0

    def test_disarm_reduces_monster_strength_and_exhausts(self):
        combat = _make_combat(monster_hp=40, attack_damage=10)
        combat.state.monsters[0].strength = 3
        disarm = CardInstance("Disarm")
        _set_piles(combat, hand_cards=[disarm], draw_cards=[])

        assert combat.state.monsters[0].get_intent_damage() == 13
        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].get_intent_damage() == 11
        assert combat.state.card_manager.exhaust_pile.cards == [disarm]

    def test_impervious_gains_block_and_exhausts(self):
        combat = _make_combat()
        impervious = CardInstance("Impervious")
        _set_piles(combat, hand_cards=[impervious], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.block == 30
        assert combat.state.card_manager.exhaust_pile.cards == [impervious]
