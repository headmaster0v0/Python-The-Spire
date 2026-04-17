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


def _make_combat(*, monster_hps: list[int] | None = None, energy: int = 3, attack_damage: int = 0) -> CombatEngine:
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
        deck=["Accuracy", "Finisher", "ThousandCuts", "AfterImage", "BladeDance", "CloakAndDagger", "InfiniteBlades"],
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


class TestSilentShivCardPlayPayoffCombat:
    def test_accuracy_applies_power(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Accuracy")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.get_power_amount("Accuracy") == 4

    def test_shiv_with_accuracy_deals_bonus_damage(self):
        combat = _make_combat(monster_hps=[20], energy=2)
        _set_piles(combat, hand_cards=[CardInstance("Accuracy"), CardInstance("Shiv")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 12

    def test_finisher_hits_once_per_prior_attack(self):
        combat = _make_combat(monster_hps=[50], energy=3)
        _set_piles(combat, hand_cards=[CardInstance("Strike"), CardInstance("Strike"), CardInstance("Finisher")], draw_cards=[])

        assert combat.play_card(0, 0)
        assert combat.play_card(0, 0)
        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 26

    def test_finisher_plus_has_higher_per_hit_damage(self):
        base = _make_combat(monster_hps=[50], energy=2)
        _set_piles(base, hand_cards=[CardInstance("Strike"), CardInstance("Finisher")], draw_cards=[])
        assert base.play_card(0, 0)
        assert base.play_card(0, 0)

        upgraded = _make_combat(monster_hps=[50], energy=2)
        _set_piles(upgraded, hand_cards=[CardInstance("Strike"), CardInstance("Finisher", upgraded=True)], draw_cards=[])
        assert upgraded.play_card(0, 0)
        assert upgraded.play_card(0, 0)

        assert upgraded.state.monsters[0].hp < base.state.monsters[0].hp

    def test_finisher_with_no_prior_attacks_is_noop(self):
        combat = _make_combat(monster_hps=[40], energy=1)
        _set_piles(combat, hand_cards=[CardInstance("Finisher")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 40

    def test_thousand_cuts_triggers_on_each_card_play(self):
        combat = _make_combat(monster_hps=[40], energy=3)
        _set_piles(combat, hand_cards=[CardInstance("ThousandCuts"), CardInstance("Strike")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("ThousandCuts") == 1
        assert combat.state.monsters[0].hp == 39

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 32

    def test_after_image_triggers_on_each_card_play(self):
        combat = _make_combat(monster_hps=[40], energy=2)
        _set_piles(combat, hand_cards=[CardInstance("AfterImage"), CardInstance("Strike")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("AfterImage") == 1
        assert combat.state.player.block == 1

        assert combat.play_card(0, 0)
        assert combat.state.player.block == 2

    def test_after_image_plus_becomes_innate_without_cost_change(self):
        upgraded = CardInstance("AfterImage", upgraded=True)
        assert upgraded.cost == 1
        assert upgraded.is_innate is True

    def test_after_image_and_thousand_cuts_trigger_on_autoplay(self):
        combat = _make_combat(monster_hps=[40], energy=4)
        _set_piles(
            combat,
            hand_cards=[CardInstance("AfterImage"), CardInstance("ThousandCuts"), CardInstance("Havoc")],
            draw_cards=[CardInstance("Strike")],
        )

        assert combat.play_card(0)
        assert combat.play_card(0)
        assert combat.play_card(0)

        assert combat.state.player.block == 4
        assert combat.state.monsters[0].hp == 31

    def test_blade_dance_generated_shivs_get_accuracy_bonus(self):
        combat = _make_combat(monster_hps=[30], energy=2)
        _set_piles(combat, hand_cards=[CardInstance("Accuracy"), CardInstance("BladeDance")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.play_card(0)
        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 22

    def test_cloak_and_dagger_generated_shiv_gets_accuracy_bonus(self):
        combat = _make_combat(monster_hps=[30], energy=2)
        _set_piles(combat, hand_cards=[CardInstance("Accuracy"), CardInstance("CloakAndDagger")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.play_card(0)
        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 22

    def test_infinite_blades_generated_shiv_gets_accuracy_bonus(self):
        combat = _make_combat(monster_hps=[30], energy=2, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Accuracy"), CardInstance("InfiniteBlades")], draw_cards=[CardInstance("Strike")] * 5)

        assert combat.play_card(0)
        assert combat.play_card(0)
        combat.end_player_turn()

        shiv_index = next(i for i, card in enumerate(combat.state.card_manager.hand.cards) if card.card_id == "Shiv")
        assert combat.play_card(shiv_index, 0)

        assert combat.state.monsters[0].hp == 22
