from __future__ import annotations

from sts_py.engine.combat.card_effects import DropkickEffect, RampageEffect, WhirlwindEffect, get_card_effects
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 80, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hps: list[int] | None = None, energy: int = 3) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyAttackMonster(f"Dummy{index}", hp=hp, attack_damage=6)
        for index, hp in enumerate(monster_hps or [80])
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=80,
        player_max_hp=80,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Defend", "Whirlwind", "Pummel", "Dropkick", "Rampage"],
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


class TestIroncladAttackUtilityEffects:
    def test_whirlwind_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("Whirlwind"))

        assert len(effects) == 1
        assert isinstance(effects[0], WhirlwindEffect)

    def test_dropkick_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("Dropkick"), target_idx=0)

        assert len(effects) == 1
        assert isinstance(effects[0], DropkickEffect)

    def test_rampage_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("Rampage"), target_idx=0)

        assert len(effects) == 1
        assert isinstance(effects[0], RampageEffect)

    def test_pummel_plus_uses_upgraded_hit_count(self):
        effects = get_card_effects(CardInstance("Pummel", upgraded=True), target_idx=0)

        assert len(effects) == 5


class TestIroncladAttackUtilityIntegration:
    def test_whirlwind_uses_actual_x_cost_for_all_enemies(self):
        combat = _make_combat(monster_hps=[40, 40], energy=3)
        _set_piles(combat, hand_cards=[CardInstance("Whirlwind")], draw_cards=[])

        assert combat.play_card(0)

        assert [monster.hp for monster in combat.state.monsters] == [25, 25]
        assert combat.state.player.energy == 0

    def test_whirlwind_plus_scales_damage_but_not_hit_count(self):
        combat = _make_combat(monster_hps=[40, 40], energy=2)
        _set_piles(combat, hand_cards=[CardInstance("Whirlwind", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)

        assert [monster.hp for monster in combat.state.monsters] == [24, 24]

    def test_whirlwind_free_to_play_does_not_repeat_from_current_energy(self):
        combat = _make_combat(monster_hps=[20, 20], energy=3)
        card = CardInstance("Whirlwind")
        card.free_to_play_once = True
        card._combat_state = combat.state

        assert combat.autoplay_card_instance(card)

        assert [monster.hp for monster in combat.state.monsters] == [20, 20]
        assert combat.state.player.energy == 3

    def test_pummel_hits_same_target_four_times(self):
        combat = _make_combat(monster_hps=[20])
        _set_piles(combat, hand_cards=[CardInstance("Pummel")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 12

    def test_pummel_plus_hits_five_times(self):
        combat = _make_combat(monster_hps=[20])
        _set_piles(combat, hand_cards=[CardInstance("Pummel", upgraded=True)], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 10

    def test_dropkick_refunds_energy_and_draws_when_target_is_vulnerable(self):
        combat = _make_combat(monster_hps=[20], energy=3)
        combat.state.monsters[0].add_power(create_power("Vulnerable", 1, "monster"))
        _set_piles(
            combat,
            hand_cards=[CardInstance("Dropkick")],
            draw_cards=[CardInstance("Strike")],
        )

        assert combat.play_card(0, 0)

        assert combat.state.player.energy == 3
        assert combat.state.card_manager.energy == 3
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Strike"]

    def test_dropkick_without_vulnerable_grants_no_bonus(self):
        combat = _make_combat(monster_hps=[20], energy=3)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Dropkick")],
            draw_cards=[CardInstance("Strike")],
        )

        assert combat.play_card(0, 0)

        assert combat.state.player.energy == 2
        assert combat.state.card_manager.energy == 2
        assert combat.state.card_manager.hand.cards == []

    def test_dropkick_draw_respects_no_draw(self):
        combat = _make_combat(monster_hps=[20], energy=3)
        combat.state.monsters[0].add_power(create_power("Vulnerable", 1, "monster"))
        combat.state.player.add_power(create_power("No Draw", 1, "player"))
        _set_piles(
            combat,
            hand_cards=[CardInstance("Dropkick")],
            draw_cards=[CardInstance("Strike")],
        )

        assert combat.play_card(0, 0)

        assert combat.state.player.energy == 3
        assert combat.state.card_manager.hand.cards == []

    def test_rampage_grows_on_same_instance_across_discard_draw_and_hand(self):
        combat = _make_combat(monster_hps=[40], energy=4)
        rampage = CardInstance("Rampage")
        _set_piles(combat, hand_cards=[rampage], draw_cards=[])

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 32

        same_rampage = combat.state.card_manager.discard_pile.cards.pop()
        assert same_rampage is rampage
        combat.state.card_manager.draw_pile.cards = _bind_cards(combat, [same_rampage])
        combat.state.card_manager.draw_cards(1)

        assert combat.state.card_manager.hand.cards[0] is rampage
        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 19

    def test_rampage_plus_has_larger_growth_than_base(self):
        base_combat = _make_combat(monster_hps=[50], energy=4)
        base_rampage = CardInstance("Rampage")
        _set_piles(base_combat, hand_cards=[base_rampage], draw_cards=[])
        assert base_combat.play_card(0, 0)
        base_rampage = base_combat.state.card_manager.discard_pile.cards.pop()
        base_combat.state.card_manager.draw_pile.cards = _bind_cards(base_combat, [base_rampage])
        base_combat.state.card_manager.draw_cards(1)
        assert base_combat.play_card(0, 0)

        upgraded_combat = _make_combat(monster_hps=[50], energy=4)
        upgraded_rampage = CardInstance("Rampage", upgraded=True)
        _set_piles(upgraded_combat, hand_cards=[upgraded_rampage], draw_cards=[])
        assert upgraded_combat.play_card(0, 0)
        upgraded_rampage = upgraded_combat.state.card_manager.discard_pile.cards.pop()
        upgraded_combat.state.card_manager.draw_pile.cards = _bind_cards(upgraded_combat, [upgraded_rampage])
        upgraded_combat.state.card_manager.draw_cards(1)
        assert upgraded_combat.play_card(0, 0)

        assert base_combat.state.monsters[0].hp == 29
        assert upgraded_combat.state.monsters[0].hp == 26
        assert upgraded_combat.state.monsters[0].hp < base_combat.state.monsters[0].hp
