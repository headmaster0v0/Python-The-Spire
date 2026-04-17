from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 40, attack_damage: int = 10, starting_strength: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage
        self.strength = starting_strength

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(
    *,
    monster_hps: list[int] | None = None,
    energy: int = 3,
    attack_damage: int = 10,
    starting_strength: int = 0,
) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyAttackMonster(
            f"Dummy{index}",
            hp=hp,
            attack_damage=attack_damage,
            starting_strength=starting_strength,
        )
        for index, hp in enumerate(monster_hps or [40])
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=70,
        player_max_hp=70,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Footwork", "LegSweep", "PiercingWail", "Terror", "Malaise", "Disarm"],
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
    cm = combat.state.card_manager
    cm.hand.cards = _bind_cards(combat, hand_cards or [])
    cm.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    cm.discard_pile.cards = _bind_cards(combat, discard_cards or [])
    cm.exhaust_pile.cards = []


class TestSilentDefensiveUtilityCombat:
    def test_footwork_applies_dexterity(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Footwork")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.dexterity == 2
        assert combat.state.player.get_power_amount("Dexterity") == 2

    def test_footwork_plus_applies_three_dexterity(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Footwork", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.dexterity == 3
        assert combat.state.player.get_power_amount("Dexterity") == 3

    def test_leg_sweep_gains_block_then_applies_two_weak(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("LegSweep")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.player.block == 11
        assert combat.state.monsters[0].get_power_amount("Weak") == 2

    def test_leg_sweep_plus_only_increases_block(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("LegSweep", upgraded=True)], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.player.block == 14
        assert combat.state.monsters[0].get_power_amount("Weak") == 2

    def test_piercing_wail_temporarily_reduces_all_monster_strength_and_restores_after_round(self):
        combat = _make_combat(monster_hps=[40, 40], energy=1, attack_damage=10)
        _set_piles(combat, hand_cards=[CardInstance("PiercingWail")], draw_cards=[])

        assert combat.play_card(0)

        assert [monster.strength for monster in combat.state.monsters] == [-6, -6]
        assert [monster.get_power_amount("Lose Strength") for monster in combat.state.monsters] == [6, 6]
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["PiercingWail"]

        combat.end_player_turn()

        assert combat.state.player.hp == 62
        assert [monster.strength for monster in combat.state.monsters] == [0, 0]
        assert [monster.get_power_amount("Lose Strength") for monster in combat.state.monsters] == [0, 0]

    def test_piercing_wail_plus_reduces_eight_strength(self):
        combat = _make_combat(monster_hps=[40, 40], energy=1, attack_damage=10)
        _set_piles(combat, hand_cards=[CardInstance("PiercingWail", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)

        assert [monster.strength for monster in combat.state.monsters] == [-8, -8]
        assert [monster.get_power_amount("Lose Strength") for monster in combat.state.monsters] == [8, 8]

    def test_terror_applies_ninety_nine_vulnerable(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Terror")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].get_power_amount("Vulnerable") == 99
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Terror"]

    def test_malaise_uses_actual_x_cost_and_exhausts(self):
        combat = _make_combat(energy=3, attack_damage=10)
        _set_piles(combat, hand_cards=[CardInstance("Malaise")], draw_cards=[])

        assert combat.play_card(0, 0)

        target = combat.state.monsters[0]
        assert combat.state.player.energy == 0
        assert target.get_power_amount("Weak") == 3
        assert target.strength == -3
        assert target.get_power_amount("Lose Strength") == 3
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Malaise"]

    def test_malaise_plus_adds_one_to_actual_x_cost(self):
        combat = _make_combat(energy=3, attack_damage=10)
        _set_piles(combat, hand_cards=[CardInstance("Malaise", upgraded=True)], draw_cards=[])

        assert combat.play_card(0, 0)

        target = combat.state.monsters[0]
        assert combat.state.player.energy == 0
        assert target.get_power_amount("Weak") == 4
        assert target.strength == -4
        assert target.get_power_amount("Lose Strength") == 4

    def test_temporary_strength_down_does_not_overwrite_permanent_disarm(self):
        combat = _make_combat(energy=2, attack_damage=10)
        _set_piles(combat, hand_cards=[CardInstance("Disarm"), CardInstance("PiercingWail")], draw_cards=[])

        assert combat.play_card(0, 0)
        assert combat.play_card(0)

        target = combat.state.monsters[0]
        assert target.get_power_amount("Strength") == -2
        assert target.strength == -6
        assert target.get_power_amount("Lose Strength") == 6

        combat.end_player_turn()

        assert target.get_power_amount("Strength") == -2
        assert target.strength == 0
        assert target.get_power_amount("Lose Strength") == 0
