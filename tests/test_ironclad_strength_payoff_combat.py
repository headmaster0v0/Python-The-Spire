from __future__ import annotations

from sts_py.engine.combat.card_effects import (
    DealDamageWithStrengthEffect,
    DoubleTapEffect,
    SpotWeaknessEffect,
    get_card_effects,
)
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyIntentMonster(MonsterBase):
    def __init__(
        self,
        *,
        hp: int = 120,
        intent: MonsterIntent = MonsterIntent.ATTACK,
        attack_damage: int = 0,
    ):
        super().__init__(id="DummyIntent", name="Dummy Intent", hp=hp, max_hp=hp)
        self.intent = intent
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        base_damage = self.attack_damage if self.intent.is_attack() else -1
        self.set_move(MonsterMove(1, self.intent, base_damage=base_damage, name="Intent"))


def _make_combat(
    *,
    monster_hp: int = 120,
    monster_intent: MonsterIntent = MonsterIntent.ATTACK,
    attack_damage: int = 0,
) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monster = DummyIntentMonster(hp=monster_hp, intent=monster_intent, attack_damage=attack_damage)
    return CombatEngine.create_with_monsters(
        monsters=[monster],
        player_hp=80,
        player_max_hp=80,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Strike", "Strike", "Strike", "Defend", "Defend", "Bash", "Inflame", "HeavyBlade", "DoubleTap"],
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


class TestIroncladStrengthPayoffEffects:
    def test_double_tap_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("DoubleTap"))

        assert len(effects) == 1
        assert isinstance(effects[0], DoubleTapEffect)

    def test_spot_weakness_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("SpotWeakness"), target_idx=0)

        assert len(effects) == 1
        assert isinstance(effects[0], SpotWeaknessEffect)

    def test_heavy_blade_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("HeavyBlade"), target_idx=0)

        assert len(effects) == 1
        assert isinstance(effects[0], DealDamageWithStrengthEffect)

    def test_inflame_upgrade_increases_strength_amount(self):
        base = CardInstance("Inflame")
        upgraded = CardInstance("Inflame", upgraded=True)

        assert base.magic_number == 2
        assert upgraded.magic_number == 3


class TestIroncladStrengthPayoffIntegration:
    def test_inflame_gives_strength(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Inflame")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.strength == 2
        assert combat.state.player.get_power_amount("Strength") == 2

    def test_spot_weakness_grants_strength_against_attack_intent(self):
        combat = _make_combat(monster_intent=MonsterIntent.ATTACK, attack_damage=8)
        _set_piles(combat, hand_cards=[CardInstance("SpotWeakness")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.player.strength == 3
        assert combat.state.player.get_power_amount("Strength") == 3

    def test_spot_weakness_does_not_trigger_against_non_attack_intent(self):
        combat = _make_combat(monster_intent=MonsterIntent.DEFEND)
        _set_piles(combat, hand_cards=[CardInstance("SpotWeakness")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.player.strength == 0
        assert combat.state.player.get_power_amount("Strength") == 0

    def test_heavy_blade_scales_with_strength(self):
        combat = _make_combat(monster_hp=50)
        combat.state.player.strength = 2
        _set_piles(combat, hand_cards=[CardInstance("HeavyBlade")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 28

    def test_heavy_blade_plus_scales_harder_than_base(self):
        combat = _make_combat(monster_hp=80)
        combat.state.player.max_energy = 4
        combat.state.player.energy = 4
        combat.state.card_manager.set_max_energy(4)
        combat.state.card_manager.set_energy(4)
        combat.state.player.strength = 2
        _set_piles(combat, hand_cards=[CardInstance("HeavyBlade"), CardInstance("HeavyBlade", upgraded=True)], draw_cards=[])

        assert combat.play_card(0, 0)
        hp_after_base = combat.state.monsters[0].hp
        assert combat.play_card(0, 0)
        hp_after_upgraded = combat.state.monsters[0].hp

        assert hp_after_base == 58
        assert hp_after_upgraded == 32
        assert (80 - hp_after_upgraded) > (80 - hp_after_base)

    def test_limit_break_doubles_positive_strength(self):
        combat = _make_combat()
        combat.state.player.strength = 4
        _set_piles(combat, hand_cards=[CardInstance("LimitBreak")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.strength == 8
        assert combat.state.player.get_power_amount("Strength") == 4

    def test_limit_break_does_not_create_strength_from_zero(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("LimitBreak")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.strength == 0
        assert combat.state.player.get_power_amount("Strength") == 0

    def test_double_tap_applies_power_then_repeats_next_attack_without_extra_energy(self):
        combat = _make_combat(monster_hp=40)
        _set_piles(combat, hand_cards=[CardInstance("DoubleTap"), CardInstance("Strike")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("DoubleTap") == 1
        assert combat.state.player.energy == 2

        assert combat.play_card(0, 0)

        assert combat.state.player.energy == 1
        assert combat.state.monsters[0].hp == 28
        assert combat.state.player.get_power_amount("DoubleTap") == 0

    def test_double_tap_is_not_consumed_by_non_attack(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("DoubleTap"), CardInstance("Inflame")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.play_card(0)

        assert combat.state.player.get_power_amount("DoubleTap") == 1
        assert combat.state.player.strength == 2

    def test_inflame_limit_break_heavy_blade_chain_works_in_one_combat(self):
        combat = _make_combat(monster_hp=80)
        combat.state.player.max_energy = 5
        combat.state.player.energy = 5
        combat.state.card_manager.set_max_energy(5)
        combat.state.card_manager.set_energy(5)
        _set_piles(combat, hand_cards=[CardInstance("Inflame"), CardInstance("LimitBreak"), CardInstance("HeavyBlade")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.strength == 2
        assert combat.play_card(0)
        assert combat.state.player.strength == 4
        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 50

    def test_double_tap_heavy_blade_hits_same_target_twice(self):
        combat = _make_combat(monster_hp=80)
        combat.state.player.max_energy = 4
        combat.state.player.energy = 4
        combat.state.card_manager.set_max_energy(4)
        combat.state.card_manager.set_energy(4)
        combat.state.player.strength = 2
        _set_piles(combat, hand_cards=[CardInstance("DoubleTap"), CardInstance("HeavyBlade")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 36
