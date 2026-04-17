from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.orbs import LightningOrb
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


def _make_combat(*, monster_hps: list[int] | None = None, energy: int = 3, relics: list[str] | None = None, attack_damage: int = 0) -> CombatEngine:
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
        deck=["Strike_B", "Defend_B", "Zap", "Dualcast"],
        relics=relics or [],
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


class TestDefectStarterOrbCombat:
    def test_strike_b_and_defend_b_use_starter_attack_and_block_truth(self):
        combat = _make_combat(energy=2)
        _set_piles(combat, hand_cards=[CardInstance("Strike_B"), CardInstance("Defend_B")], draw_cards=[])

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 34

        assert combat.play_card(0)
        assert combat.state.player.block == 5

    def test_zap_channels_lightning_orb_and_plus_costs_zero(self):
        combat = _make_combat(energy=1)
        _set_piles(combat, hand_cards=[CardInstance("Zap")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.energy == 0
        assert len(combat.state.player.orbs) == 1
        assert combat.state.player.orbs.channels[0].orb_id == "Lightning"
        assert CardInstance("Zap+").cost == 0

    def test_dualcast_evokes_leftmost_orb_twice_and_removes_it(self):
        combat = _make_combat(energy=2)
        _set_piles(combat, hand_cards=[CardInstance("Zap"), CardInstance("Dualcast")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.play_card(0)

        assert len(combat.state.player.orbs) == 0
        assert combat.state.monsters[0].hp == 24
        assert CardInstance("Dualcast+").cost == 0

    def test_cracked_core_channels_lightning_orb_at_battle_start(self):
        combat = _make_combat(relics=["CrackedCore"])

        assert len(combat.state.player.orbs) == 1
        assert combat.state.player.orbs.channels[0].orb_id == "Lightning"

    def test_lightning_orb_passive_triggers_at_player_end_turn(self):
        combat = _make_combat(energy=1, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Zap")], draw_cards=[])

        assert combat.play_card(0)
        combat.end_player_turn()

        assert combat.state.monsters[0].hp == 37
        assert len(combat.state.player.orbs) == 1

    def test_channeling_when_full_evokes_leftmost_before_adding_new_orb(self):
        combat = _make_combat(energy=1)
        combat.state.player.orbs.channels = [LightningOrb(), LightningOrb(), LightningOrb()]
        combat.state.player.orbs.owner = combat.state.player
        combat.state.player.orbs.combat_state = combat.state
        combat.state.player.orbs.slots = combat.state.player.max_orbs
        _set_piles(combat, hand_cards=[CardInstance("Zap")], draw_cards=[])

        assert combat.play_card(0)

        assert len(combat.state.player.orbs) == 3
        assert combat.state.monsters[0].hp == 32

