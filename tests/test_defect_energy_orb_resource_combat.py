from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.orbs import LightningOrb, PlasmaOrb
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


def _make_combat(*, energy: int = 3, attack_damage: int = 0) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [DummyMonster("Dummy0", hp=40, attack_damage=attack_damage)]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=75,
        player_max_hp=75,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Turbo", "DoubleEnergy", "Fission", "MultiCast", "Recycle", "Fusion", "Capacitor", "MeteorStrike", "Tempest", "ReinforcedBody", "Dualcast"],
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


class TestDefectEnergyOrbResourceCombat:
    def test_turbo_gains_energy_and_adds_void(self):
        combat = _make_combat(energy=1)
        _set_piles(combat, hand_cards=[CardInstance("Turbo")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.energy == 3
        assert combat.state.card_manager.energy == 3
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Void", "Turbo"]

        upgraded = _make_combat(energy=1)
        _set_piles(upgraded, hand_cards=[CardInstance("Turbo", upgraded=True)], draw_cards=[])
        assert upgraded.play_card(0)
        assert upgraded.state.player.energy == 4

    def test_drawing_void_still_loses_energy(self):
        combat = _make_combat(energy=3)
        _set_piles(combat, hand_cards=[], draw_cards=[CardInstance("Void")])

        drawn = combat.state.card_manager.draw_card(combat.ai_rng)
        assert drawn is not None and drawn.card_id == "Void"
        assert combat.state.player.energy == 2

    def test_double_energy_doubles_current_energy_and_plus_costs_zero(self):
        combat = _make_combat(energy=3)
        _set_piles(combat, hand_cards=[CardInstance("DoubleEnergy")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.energy == 4
        assert combat.state.card_manager.energy == 4
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["DoubleEnergy"]
        assert CardInstance("DoubleEnergy", upgraded=True).cost == 0

    def test_fission_gains_energy_and_draw_and_handles_remove_vs_evoke(self):
        combat = _make_combat(energy=0)
        combat.state.player.orbs.channels = [LightningOrb(), PlasmaOrb()]
        combat.state.player.orbs.owner = combat.state.player
        combat.state.player.orbs.combat_state = combat.state
        _set_piles(combat, hand_cards=[CardInstance("Fission")], draw_cards=[CardInstance("Strike_B"), CardInstance("Defend_B")])

        assert combat.play_card(0)
        assert combat.state.player.energy == 2
        assert combat.state.card_manager.energy == 2
        assert len(combat.state.card_manager.hand.cards) == 2
        assert combat.state.player.orbs.filled_count() == 0
        assert combat.state.monsters[0].hp == 40

        upgraded = _make_combat(energy=0)
        upgraded.state.player.orbs.channels = [LightningOrb(), PlasmaOrb()]
        upgraded.state.player.orbs.owner = upgraded.state.player
        upgraded.state.player.orbs.combat_state = upgraded.state
        _set_piles(upgraded, hand_cards=[CardInstance("Fission", upgraded=True)], draw_cards=[CardInstance("Strike_B"), CardInstance("Defend_B")])
        assert upgraded.play_card(0)
        assert upgraded.state.player.energy == 4
        assert upgraded.state.monsters[0].hp == 32
        assert upgraded.state.player.orbs.filled_count() == 0

    def test_multicast_hits_leftmost_orb_x_or_x_plus_one_times(self):
        combat = _make_combat(energy=2)
        combat.state.player.orbs.channels = [PlasmaOrb()]
        combat.state.player.orbs.owner = combat.state.player
        combat.state.player.orbs.combat_state = combat.state
        _set_piles(combat, hand_cards=[CardInstance("MultiCast")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.energy == 4
        assert combat.state.card_manager.energy == 4
        assert combat.state.player.orbs.filled_count() == 0

        upgraded = _make_combat(energy=2)
        upgraded.state.player.orbs.channels = [PlasmaOrb()]
        upgraded.state.player.orbs.owner = upgraded.state.player
        upgraded.state.player.orbs.combat_state = upgraded.state
        _set_piles(upgraded, hand_cards=[CardInstance("MultiCast", upgraded=True)], draw_cards=[])
        assert upgraded.play_card(0)
        assert upgraded.state.player.energy == 6

        no_orb = _make_combat(energy=2)
        _set_piles(no_orb, hand_cards=[CardInstance("MultiCast")], draw_cards=[])
        assert no_orb.play_card(0)
        assert no_orb.state.player.energy == 0

    def test_recycle_exhausts_first_other_card_and_gains_energy(self):
        combat = _make_combat(energy=1)
        _set_piles(combat, hand_cards=[CardInstance("Recycle"), CardInstance("Fusion")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.energy == 2
        assert combat.state.card_manager.energy == 2
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Fusion"]

        x_cost = _make_combat(energy=3)
        _set_piles(x_cost, hand_cards=[CardInstance("Recycle"), CardInstance("Tempest")], draw_cards=[])
        assert x_cost.play_card(0)
        assert x_cost.state.player.energy == 4
        assert x_cost.state.card_manager.energy == 4

        upgraded = _make_combat(energy=0)
        _set_piles(upgraded, hand_cards=[CardInstance("Recycle", upgraded=True)], draw_cards=[])
        assert upgraded.play_card(0)
        assert CardInstance("Recycle", upgraded=True).cost == 0

    def test_fusion_capacitor_reinforced_body_and_meteor_strike(self):
        fusion = _make_combat(energy=2)
        _set_piles(fusion, hand_cards=[CardInstance("Fusion")], draw_cards=[])
        assert fusion.play_card(0)
        assert fusion.state.player.orbs.channels[0].orb_id == "Plasma"
        assert CardInstance("Fusion", upgraded=True).cost == 1

        capacitor = _make_combat(energy=1)
        _set_piles(capacitor, hand_cards=[CardInstance("Capacitor")], draw_cards=[])
        assert capacitor.play_card(0)
        assert capacitor.state.player.max_orbs == 5
        assert CardInstance("Capacitor", upgraded=True).magic_number == 3

        reinforced = _make_combat(energy=3)
        _set_piles(reinforced, hand_cards=[CardInstance("ReinforcedBody")], draw_cards=[])
        assert reinforced.play_card(0)
        assert reinforced.state.player.block == 21
        assert CardInstance("Reinforced Body").card_id == "ReinforcedBody"

        meteor = _make_combat(energy=5)
        _set_piles(meteor, hand_cards=[CardInstance("MeteorStrike"), CardInstance("Dualcast")], draw_cards=[])
        assert meteor.play_card(0, 0)
        assert meteor.state.monsters[0].hp == 16
        assert meteor.state.player.orbs.filled_count() == 3
        meteor.state.player.energy = 1
        meteor.state.card_manager.set_energy(1)
        dualcast_index = next(i for i, c in enumerate(meteor.state.card_manager.hand.cards) if c.card_id == "Dualcast")
        assert meteor.play_card(dualcast_index)
        assert meteor.state.player.energy == 4
