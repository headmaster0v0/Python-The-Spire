from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.orbs import DarkOrb, LightningOrb
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 40, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hps: list[int] | None = None, energy: int = 3, attack_damage: int = 0) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyMonster(f"Dummy{index}", hp=hp, attack_damage=attack_damage)
        for index, hp in enumerate(monster_hps or [40])
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=75,
        player_max_hp=75,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Lockon", "Recursion", "Rainbow", "Electrodynamics", "BiasedCognition", "Zap", "Dualcast"],
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


class TestDefectOrbDamageContinuationCombat:
    def test_lockon_applies_debuff_and_amplifies_orb_damage(self):
        combat = _make_combat(energy=2)
        _set_piles(combat, hand_cards=[CardInstance("Lockon"), CardInstance("Zap")], draw_cards=[])

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].get_power_amount("Lockon") == 2

        assert combat.play_card(0)
        combat.end_player_turn()

        assert combat.state.monsters[0].hp == 28
        assert combat.state.monsters[0].get_power_amount("Lockon") == 1

    def test_lockon_also_amplifies_dark_orb_damage_and_decays(self):
        combat = _make_combat(energy=2, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Darkness"), CardInstance("Lockon"), CardInstance("Dualcast")], draw_cards=[])

        assert combat.play_card(0)
        combat.end_player_turn()

        _set_piles(combat, hand_cards=[CardInstance("Lockon"), CardInstance("Dualcast")], draw_cards=[])
        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].get_power_amount("Lockon") == 2

        assert combat.play_card(0)

        assert combat.state.monsters[0].is_dead()

    def test_recursion_evokes_leftmost_orb_and_channels_copy(self):
        combat = _make_combat(energy=1)
        combat.state.player.orbs.channels = [LightningOrb()]
        combat.state.player.orbs.owner = combat.state.player
        combat.state.player.orbs.combat_state = combat.state
        _set_piles(combat, hand_cards=[CardInstance("Recursion")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.monsters[0].hp == 32
        assert len(combat.state.player.orbs.channels) == 1
        assert combat.state.player.orbs.channels[0].orb_id == "Lightning"
        assert CardInstance("Recursion+").cost == 0

    def test_recursion_without_orbs_is_noop(self):
        combat = _make_combat(energy=1)
        _set_piles(combat, hand_cards=[CardInstance("Recursion")], draw_cards=[])

        assert combat.play_card(0)
        assert len(combat.state.player.orbs.channels) == 0
        assert combat.state.monsters[0].hp == 40

    def test_rainbow_channels_lightning_frost_dark_and_plus_drops_exhaust(self):
        combat = _make_combat(energy=2)
        _set_piles(combat, hand_cards=[CardInstance("Rainbow")], draw_cards=[])

        assert combat.play_card(0)
        assert [orb.orb_id for orb in combat.state.player.orbs.channels] == ["Lightning", "Frost", "Dark"]
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Rainbow"]

        upgraded = _make_combat(energy=2)
        _set_piles(upgraded, hand_cards=[CardInstance("Rainbow", upgraded=True)], draw_cards=[])
        assert upgraded.play_card(0)
        assert [card.card_id for card in upgraded.state.card_manager.exhaust_pile.cards] == []

    def test_electrodynamics_channels_lightning_and_makes_lightning_hit_all(self):
        combat = _make_combat(monster_hps=[40, 40], energy=2, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Electrodynamics")], draw_cards=[CardInstance("Strike_B")] * 5)

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Electro") == 1
        assert [orb.orb_id for orb in combat.state.player.orbs.channels] == ["Lightning", "Lightning"]

        combat.end_player_turn()

        assert [monster.hp for monster in combat.state.monsters] == [34, 34]

    def test_electrodynamics_plus_channels_three_lightning(self):
        combat = _make_combat(energy=2)
        _set_piles(combat, hand_cards=[CardInstance("Electrodynamics", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)
        assert len(combat.state.player.orbs.channels) == 3
        assert all(orb.orb_id == "Lightning" for orb in combat.state.player.orbs.channels)

    def test_biased_cognition_grants_focus_then_loses_one_each_turn(self):
        combat = _make_combat(energy=1, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("BiasedCognition"), CardInstance("Zap")], draw_cards=[CardInstance("Strike_B")] * 5)

        assert combat.play_card(0)
        assert combat.state.player.focus == 4
        assert combat.state.player.get_power_amount("Bias") == 1

        combat.state.player.energy = 1
        combat.state.card_manager.set_energy(1)
        assert combat.play_card(0)
        combat.end_player_turn()

        assert combat.state.player.focus == 3
        assert combat.state.monsters[0].hp == 33

        upgraded = _make_combat(energy=1)
        _set_piles(upgraded, hand_cards=[CardInstance("BiasedCognition", upgraded=True)], draw_cards=[])
        assert upgraded.play_card(0)
        assert upgraded.state.player.focus == 5
