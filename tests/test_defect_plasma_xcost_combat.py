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
        deck=["Fusion", "Capacitor", "Tempest", "ReinforcedBody", "MeteorStrike", "Dualcast"],
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


class TestDefectPlasmaXCostCombat:
    def test_fusion_channels_plasma_and_plus_costs_one(self):
        combat = _make_combat(energy=3)
        _set_piles(combat, hand_cards=[CardInstance("Fusion")], draw_cards=[])

        assert combat.play_card(0)

        assert len(combat.state.player.orbs.channels) == 1
        assert combat.state.player.orbs.channels[0].orb_id == "Plasma"
        assert combat.state.player.energy == 1
        assert CardInstance("Fusion+").cost == 1

    def test_plasma_orb_grants_start_of_turn_energy_and_dualcast_grants_two_plus_two(self):
        combat = _make_combat(energy=2, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Fusion")], draw_cards=[CardInstance("Strike_B")] * 5)

        assert combat.play_card(0)
        combat.end_player_turn()

        assert combat.state.player.energy == 3
        assert combat.state.card_manager.energy == 3

        dualcast = _make_combat(energy=1)
        dualcast.state.player.orbs.channels = [PlasmaOrb()]
        dualcast.state.player.orbs.owner = dualcast.state.player
        dualcast.state.player.orbs.combat_state = dualcast.state
        _set_piles(dualcast, hand_cards=[CardInstance("Dualcast")], draw_cards=[])

        assert dualcast.play_card(0)
        assert dualcast.state.player.energy == 4
        assert dualcast.state.card_manager.energy == 4

    def test_capacitor_increases_slots_and_prevents_early_overflow(self):
        combat = _make_combat(energy=3)
        combat.state.player.orbs.channels = [LightningOrb(), LightningOrb(), LightningOrb()]
        combat.state.player.orbs.owner = combat.state.player
        combat.state.player.orbs.combat_state = combat.state
        combat.state.player.orbs.slots = combat.state.player.max_orbs
        _set_piles(combat, hand_cards=[CardInstance("Capacitor"), CardInstance("Fusion")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.max_orbs == 5
        assert combat.state.player.orbs.slots == 5

        assert combat.play_card(0)
        assert len(combat.state.player.orbs.channels) == 4
        assert combat.state.monsters[0].hp == 40

        assert CardInstance("Capacitor+").magic_number == 3

    def test_tempest_channels_lightning_by_x_and_plus_adds_one(self):
        combat = _make_combat(energy=2)
        _set_piles(combat, hand_cards=[CardInstance("Tempest")], draw_cards=[])

        assert combat.play_card(0)

        assert len(combat.state.player.orbs.channels) == 2
        assert all(orb.orb_id == "Lightning" for orb in combat.state.player.orbs.channels)
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Tempest"]

        upgraded = _make_combat(energy=2)
        _set_piles(upgraded, hand_cards=[CardInstance("Tempest", upgraded=True)], draw_cards=[])
        assert upgraded.play_card(0)
        assert len(upgraded.state.player.orbs.channels) == 3

    def test_reinforced_body_gains_block_by_x(self):
        combat = _make_combat(energy=3)
        _set_piles(combat, hand_cards=[CardInstance("ReinforcedBody")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.block == 21

        upgraded = _make_combat(energy=2)
        _set_piles(upgraded, hand_cards=[CardInstance("ReinforcedBody", upgraded=True)], draw_cards=[])
        assert upgraded.play_card(0)
        assert upgraded.state.player.block == 18

    def test_meteor_strike_deals_damage_and_channels_three_plasma(self):
        combat = _make_combat(energy=5)
        _set_piles(combat, hand_cards=[CardInstance("MeteorStrike")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 16
        assert len(combat.state.player.orbs.channels) == 3
        assert all(orb.orb_id == "Plasma" for orb in combat.state.player.orbs.channels)

        upgraded = _make_combat(energy=5)
        _set_piles(upgraded, hand_cards=[CardInstance("MeteorStrike", upgraded=True)], draw_cards=[])
        assert upgraded.play_card(0, 0)
        assert upgraded.state.monsters[0].hp == 10
