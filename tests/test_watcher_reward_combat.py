from __future__ import annotations

from sts_py.engine.combat.card_effects import (
    ApplyPowerEffect,
    DealDamageEffect,
    GainBlockEffect,
    GainBlockFromLastDamageEffect,
    GainMantraEffect,
    get_card_effects,
)
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
from sts_py.engine.combat.stance import StanceType
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


def _set_hand(combat: CombatEngine, card_ids: list[str]) -> None:
    cards = [CardInstance(card_id) for card_id in card_ids]
    for card in cards:
        card._combat_state = combat.state
    combat.state.card_manager.hand.cards = cards
    combat.state.card_manager.draw_pile.cards = []
    combat.state.card_manager.discard_pile.cards = []
    combat.state.card_manager.exhaust_pile.cards = []


class TestWatcherRewardCardEffects:
    def test_wallop_effects_damage_then_gain_block_from_actual_damage(self):
        effects = get_card_effects(CardInstance("Wallop"), target_idx=0)

        assert len(effects) == 2
        assert isinstance(effects[0], DealDamageEffect)
        assert isinstance(effects[1], GainBlockFromLastDamageEffect)

    def test_prostrate_effects_gain_block_and_mantra(self):
        effects = get_card_effects(CardInstance("Prostrate"))

        assert len(effects) == 2
        assert isinstance(effects[0], GainBlockEffect)
        assert isinstance(effects[1], GainMantraEffect)
        assert effects[1].amount == 2

    def test_devotion_effects_apply_power(self):
        effects = get_card_effects(CardInstance("Devotion"))

        assert len(effects) == 1
        assert isinstance(effects[0], ApplyPowerEffect)
        assert effects[0].power_type == "Devotion"


class TestWatcherRewardCombatIntegration:
    def test_wallop_gains_block_equal_to_unblocked_damage(self):
        combat = _make_combat(monster_hp=80)
        _set_hand(combat, ["Wallop"])
        monster = combat.state.monsters[0]

        assert combat.play_card(0, 0)
        assert monster.hp == 71
        assert combat.state.player.block == 9

    def test_wallop_only_counts_actual_damage_through_block(self):
        combat = _make_combat(monster_hp=80)
        _set_hand(combat, ["Wallop"])
        monster = combat.state.monsters[0]
        monster.block = 5

        assert combat.play_card(0, 0)
        assert monster.hp == 76
        assert monster.block == 0
        assert combat.state.player.block == 4

    def test_prostrate_adds_mantra_and_block(self):
        combat = _make_combat()
        _set_hand(combat, ["Prostrate"])

        assert combat.play_card(0)
        assert combat.state.player.block == 4
        assert combat.state.player.get_power_amount("Mantra") == 2
        assert combat.state.player.stance is not None
        assert combat.state.player.stance.stance_type == StanceType.NEUTRAL

    def test_devotion_gains_mantra_at_start_of_next_turn(self):
        combat = _make_combat(attack_damage=0)
        _set_hand(combat, ["Devotion"])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Devotion") == 2
        assert combat.state.player.get_power_amount("Mantra") == 0

        combat.end_player_turn()

        assert combat.state.phase.name == "PLAYER_TURN"
        assert combat.state.player.get_power_amount("Mantra") == 2

    def test_mantra_reaching_ten_enters_divinity_and_grants_energy(self):
        combat = _make_combat()
        _set_hand(combat, ["Prostrate", "Prostrate", "Prostrate", "Prostrate", "Prostrate"])

        for _ in range(5):
            assert combat.play_card(0)

        assert combat.state.player.stance is not None
        assert combat.state.player.stance.stance_type == StanceType.DIVINITY
        assert combat.state.player.energy == 6
        assert combat.state.player.get_power_amount("Mantra") == 0
        assert combat.state.card_manager.energy == 6

    def test_divinity_boosts_attack_damage(self):
        combat = _make_combat(monster_hp=80)
        combat.state.player.add_power(create_power("Mantra", 8, "player"))
        _set_hand(combat, ["Prostrate", "Strike"])
        monster = combat.state.monsters[0]

        assert combat.play_card(0)
        assert combat.state.player.stance is not None
        assert combat.state.player.stance.stance_type == StanceType.DIVINITY

        assert combat.play_card(0, 0)
        assert monster.hp == 62

    def test_divinity_does_not_stack_with_wrath_on_eruption_hit(self):
        combat = _make_combat(monster_hp=100)
        combat.state.player.add_power(create_power("Mantra", 8, "player"))
        _set_hand(combat, ["Prostrate", "Eruption"])
        monster = combat.state.monsters[0]

        assert combat.play_card(0)
        assert combat.state.player.stance is not None
        assert combat.state.player.stance.stance_type == StanceType.DIVINITY

        assert combat.play_card(0, 0)
        assert monster.hp == 73
        assert combat.state.player.stance is not None
        assert combat.state.player.stance.stance_type == StanceType.WRATH
