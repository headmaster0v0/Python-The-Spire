from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.orbs import DarkOrb, FrostOrb, LightningOrb
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


def _make_combat(*, monster_hps: list[int] | None = None, energy: int = 3, attack_damage: int = 0, relics: list[str] | None = None) -> CombatEngine:
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
        deck=["Barrage", "Darkness", "Loop", "Consume", "Buffer", "Zap", "Dualcast"],
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


class TestDefectOrbPayoffControlCombat:
    def test_barrage_hits_once_per_current_orb(self):
        combat = _make_combat(energy=1)
        combat.state.player.orbs.channels = [LightningOrb(), FrostOrb()]
        combat.state.player.orbs.owner = combat.state.player
        combat.state.player.orbs.combat_state = combat.state
        _set_piles(combat, hand_cards=[CardInstance("Barrage")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 32

    def test_barrage_plus_has_higher_per_hit_damage(self):
        base = _make_combat(energy=1)
        base.state.player.orbs.channels = [LightningOrb()]
        base.state.player.orbs.owner = base.state.player
        base.state.player.orbs.combat_state = base.state
        _set_piles(base, hand_cards=[CardInstance("Barrage")], draw_cards=[])
        assert base.play_card(0, 0)

        upgraded = _make_combat(energy=1)
        upgraded.state.player.orbs.channels = [LightningOrb()]
        upgraded.state.player.orbs.owner = upgraded.state.player
        upgraded.state.player.orbs.combat_state = upgraded.state
        _set_piles(upgraded, hand_cards=[CardInstance("Barrage", upgraded=True)], draw_cards=[])
        assert upgraded.play_card(0, 0)

        assert upgraded.state.monsters[0].hp < base.state.monsters[0].hp

    def test_barrage_without_orbs_is_noop(self):
        combat = _make_combat(energy=1)
        _set_piles(combat, hand_cards=[CardInstance("Barrage")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 40

    def test_darkness_channels_dark_orb_and_plus_applies_dark_impulse(self):
        combat = _make_combat(energy=1)
        _set_piles(combat, hand_cards=[CardInstance("Darkness", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)

        assert len(combat.state.player.orbs) == 1
        dark_orb = combat.state.player.orbs.channels[0]
        assert isinstance(dark_orb, DarkOrb)
        assert dark_orb.stored_damage == 12

    def test_dark_orb_passive_and_evoke_use_stored_damage(self):
        combat = _make_combat(energy=2)
        _set_piles(combat, hand_cards=[CardInstance("Darkness"), CardInstance("Dualcast")], draw_cards=[])

        assert combat.play_card(0)
        dark_orb = combat.state.player.orbs.channels[0]
        assert isinstance(dark_orb, DarkOrb)
        assert dark_orb.stored_damage == 6

        combat.end_player_turn()
        assert dark_orb.stored_damage == 12

        dualcast_index = next(i for i, card in enumerate(combat.state.card_manager.hand.cards) if card.card_id == "Dualcast")
        assert combat.play_card(dualcast_index)

        assert combat.state.monsters[0].hp == 16
        assert len(combat.state.player.orbs) == 0

    def test_loop_triggers_leftmost_orb_passive_at_start_of_turn(self):
        combat = _make_combat(energy=1, attack_damage=0)
        combat.state.player.orbs.channels = [LightningOrb(), FrostOrb()]
        combat.state.player.orbs.owner = combat.state.player
        combat.state.player.orbs.combat_state = combat.state
        _set_piles(combat, hand_cards=[CardInstance("Loop")], draw_cards=[CardInstance("Strike_B")] * 5)

        assert combat.play_card(0)
        combat.end_player_turn()

        assert combat.state.player.get_power_amount("Loop") == 1
        assert combat.state.monsters[0].hp == 34

    def test_loop_plus_triggers_twice(self):
        combat = _make_combat(energy=1, attack_damage=0)
        combat.state.player.orbs.channels = [LightningOrb()]
        combat.state.player.orbs.owner = combat.state.player
        combat.state.player.orbs.combat_state = combat.state
        _set_piles(combat, hand_cards=[CardInstance("Loop", upgraded=True)], draw_cards=[CardInstance("Strike_B")] * 5)

        assert combat.play_card(0)
        combat.end_player_turn()

        assert combat.state.monsters[0].hp == 31

    def test_consume_gains_focus_and_reduces_orb_slots_with_overflow_evoke(self):
        combat = _make_combat(energy=2)
        combat.state.player.orbs.channels = [LightningOrb(), LightningOrb(), LightningOrb()]
        combat.state.player.orbs.owner = combat.state.player
        combat.state.player.orbs.combat_state = combat.state
        combat.state.player.orbs.slots = combat.state.player.max_orbs
        _set_piles(combat, hand_cards=[CardInstance("Consume")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.focus == 2
        assert combat.state.player.max_orbs == 2
        assert combat.state.player.orbs.slots == 2
        assert len(combat.state.player.orbs) == 2
        assert combat.state.monsters[0].hp == 30

    def test_buffer_power_blocks_next_take_damage_and_direct_lose_hp(self):
        combat = _make_combat(energy=2)
        _set_piles(combat, hand_cards=[CardInstance("Buffer")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Buffer") == 1

        assert combat.state.player.take_damage(9) == 0
        assert combat.state.player.hp == 75
        assert combat.state.player.get_power_amount("Buffer") == 0

        _set_piles(combat, hand_cards=[CardInstance("Buffer")], draw_cards=[])
        combat.state.player.energy = 2
        combat.state.card_manager.set_energy(2)
        assert combat.play_card(0)
        assert combat.state.player.lose_hp(7, source_owner=combat.state.player) == 0
        assert combat.state.player.hp == 75
        assert combat.state.player.get_power_amount("Buffer") == 0

    def test_fossilized_helix_battle_start_buffer_uses_same_prevention_path(self):
        combat = _make_combat(relics=["FossilizedHelix"])

        assert combat.state.player.get_power_amount("Buffer") == 1
        assert combat.state.player.take_damage(11) == 0
        assert combat.state.player.hp == 75
        assert combat.state.player.get_power_amount("Buffer") == 0
