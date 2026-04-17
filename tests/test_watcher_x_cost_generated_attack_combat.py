from __future__ import annotations

from sts_py.engine.combat.card_effects import ConjureBladeEffect, ExpungerEffect, get_card_effects
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.combat.powers import create_power


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, hp: int = 120, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hps: list[int], energy: int = 3) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyAttackMonster(monster_id=f"Dummy{index}", hp=hp, attack_damage=0)
        for index, hp in enumerate(monster_hps)
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=72,
        player_max_hp=72,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Strike", "Strike", "Strike", "Defend", "Defend", "Defend", "Defend", "Eruption", "Vigilance"],
        relics=[],
    )
    combat.state.player.energy = energy
    combat.state.player.max_energy = energy
    combat.state.card_manager.set_energy(energy)
    combat.state.card_manager.set_max_energy(energy)
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
) -> None:
    combat.state.card_manager.hand.cards = _bind_cards(combat, hand_cards or [])
    combat.state.card_manager.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    combat.state.card_manager.discard_pile.cards = []
    combat.state.card_manager.exhaust_pile.cards = []


class TestWatcherXCostGeneratedAttackEffects:
    def test_expunger_metadata(self):
        card = CardInstance("Expunger")

        assert card.card_id == "Expunger"
        assert card.is_ethereal is False
        assert card.base_damage == 9
        assert card.magic_number == 0

    def test_conjure_blade_effect_generates_expunger(self):
        effects = get_card_effects(CardInstance("ConjureBlade"))

        assert len(effects) == 1
        assert isinstance(effects[0], ConjureBladeEffect)

    def test_expunger_effect_uses_card_damage_and_hit_count(self):
        card = CardInstance("Expunger")
        card.base_magic_number = 3
        card.magic_number = 3

        effects = get_card_effects(card)

        assert len(effects) == 1
        assert isinstance(effects[0], ExpungerEffect)
        assert effects[0].damage == 9
        assert effects[0].hit_count == 3

    def test_conjure_blade_upgrade_keeps_x_cost(self):
        card = CardInstance("ConjureBlade", upgraded=True)

        assert card.cost == -1
        assert card.exhaust is True


class TestWatcherXCostGeneratedAttackIntegration:
    def test_conjure_blade_generates_expunger_from_actual_x_cost(self):
        combat = _make_combat(monster_hps=[120], energy=3)
        _set_piles(combat, hand_cards=[CardInstance("ConjureBlade")], draw_cards=[])

        assert combat.play_card(0)

        generated = combat.state.card_manager.draw_pile.cards
        assert len(generated) == 1
        expunger = generated[0]
        assert expunger.card_id == "Expunger"
        assert expunger.misc == 3
        assert expunger.base_magic_number == 3
        assert expunger.magic_number == 3
        assert expunger.base_damage == 9
        assert expunger.damage == 9

    def test_expunger_can_be_drawn_and_hits_selected_target_x_times(self):
        combat = _make_combat(monster_hps=[400], energy=3)
        expunger = CardInstance("Expunger")
        expunger.base_magic_number = 2
        expunger.magic_number = 2
        _set_piles(combat, hand_cards=[expunger], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 400 - (9 * 2)

    def test_expunger_only_hits_the_selected_target(self):
        combat = _make_combat(monster_hps=[200, 200], energy=3)
        expunger = CardInstance("Expunger")
        expunger.base_magic_number = 2
        expunger.magic_number = 2
        _set_piles(combat, hand_cards=[expunger], draw_cards=[])

        assert combat.play_card(0, 1)

        assert combat.state.monsters[0].hp == 200
        assert combat.state.monsters[1].hp == 200 - (9 * 2)

    def test_master_reality_marks_generated_expunger_upgraded(self):
        combat = _make_combat(monster_hps=[120], energy=2)
        _set_piles(combat, hand_cards=[CardInstance("ConjureBlade")], draw_cards=[])
        combat.state.player.add_power(create_power("MasterReality", 1, "player"))

        assert combat.play_card(0)

        expunger = combat.state.card_manager.draw_pile.cards[0]
        assert expunger.card_id == "Expunger"
        assert expunger.upgraded is True
        assert expunger.misc == 2
        assert expunger.magic_number == 2
        assert expunger.damage == 15

    def test_free_to_play_once_conjure_blade_generates_zero_hit_expunger(self):
        combat = _make_combat(monster_hps=[120], energy=3)
        conjure_blade = CardInstance("ConjureBlade")
        conjure_blade.free_to_play_once = True
        _set_piles(combat, hand_cards=[conjure_blade], draw_cards=[])

        assert combat.play_card(0)

        expunger = combat.state.card_manager.draw_pile.cards[0]
        assert expunger.misc == 0
        assert expunger.magic_number == 0
        assert expunger.damage == 9
        assert combat.state.player.energy == 3
