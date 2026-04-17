from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 40, attack_damage: int = 6):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(
    *,
    monster_hps: list[int] | None = None,
    energy: int = 3,
    attack_damage: int = 6,
) -> CombatEngine:
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
        deck=["Blur", "EndlessAgony", "Flechettes", "GlassKnife", "HeelHook", "MasterfulStab", "RiddleWithHoles", "Unload"],
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


class TestSilentHandStateAttackCombat:
    def test_blur_single_and_stacked_layers_preserve_block_across_turns(self):
        single = _make_combat(energy=1, attack_damage=0)
        _set_piles(single, hand_cards=[CardInstance("Blur")], draw_cards=[CardInstance("Strike") for _ in range(5)])

        assert single.play_card(0)
        assert single.state.player.block == 5
        assert single.state.player.get_power_amount("Blur") == 1

        single.end_player_turn()
        assert single.state.player.block == 5
        assert single.state.player.get_power_amount("Blur") == 0

        single.end_player_turn()
        assert single.state.player.block == 0

        stacked = _make_combat(energy=2, attack_damage=0)
        _set_piles(stacked, hand_cards=[CardInstance("Blur"), CardInstance("Blur")], draw_cards=[CardInstance("Strike") for _ in range(5)])

        assert stacked.play_card(0)
        assert stacked.play_card(0)
        assert stacked.state.player.block == 10
        assert stacked.state.player.get_power_amount("Blur") == 2

        stacked.end_player_turn()
        assert stacked.state.player.block == 10
        assert stacked.state.player.get_power_amount("Blur") == 1

        stacked.end_player_turn()
        assert stacked.state.player.block == 10
        assert stacked.state.player.get_power_amount("Blur") == 0

        stacked.end_player_turn()
        assert stacked.state.player.block == 0

    def test_endless_agony_copies_when_drawn_and_exhausts_on_play(self):
        combat = _make_combat(energy=1, attack_damage=0)
        endless_agony = CardInstance("EndlessAgony", upgraded=True)
        _set_piles(combat, hand_cards=[], draw_cards=[endless_agony], discard_cards=[])

        drawn = combat.state.card_manager.draw_card(combat.state.card_manager.rng)

        assert drawn is endless_agony
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["EndlessAgony", "EndlessAgony"]

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 34
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["EndlessAgony"]

    def test_flechettes_hits_once_per_skill_in_hand(self):
        combat = _make_combat(energy=1, attack_damage=0)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Flechettes"), CardInstance("Deflect"), CardInstance("Blur"), CardInstance("Strike")],
            draw_cards=[],
        )

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 32

        single_skill = _make_combat(energy=1, attack_damage=0)
        _set_piles(single_skill, hand_cards=[CardInstance("Flechettes", upgraded=True), CardInstance("Deflect"), CardInstance("Strike")], draw_cards=[])
        assert single_skill.play_card(0, 0)
        assert single_skill.state.monsters[0].hp == 34

    def test_glass_knife_double_hits_and_same_instance_damage_decays(self):
        combat = _make_combat(energy=2, attack_damage=0)
        glass_knife = CardInstance("GlassKnife", upgraded=True)
        _set_piles(combat, hand_cards=[glass_knife], draw_cards=[])

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 16
        stored = combat.state.card_manager.discard_pile.cards[-1]
        assert stored.base_damage == 10

        combat.state.player.energy = 2
        combat.state.card_manager.set_energy(2)
        combat.state.card_manager.discard_pile.remove(stored)
        combat.state.card_manager.hand.add(stored)

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 0
        stored = combat.state.card_manager.discard_pile.cards[-1]
        assert stored.base_damage == 8

    def test_heel_hook_rewards_only_when_target_is_weak(self):
        no_weak = _make_combat(energy=1, attack_damage=0)
        _set_piles(no_weak, hand_cards=[CardInstance("HeelHook")], draw_cards=[CardInstance("Strike")])
        assert no_weak.play_card(0, 0)
        assert no_weak.state.monsters[0].hp == 35
        assert no_weak.state.player.energy == 0
        assert no_weak.state.card_manager.get_hand_size() == 0

        weak = _make_combat(energy=1, attack_damage=0)
        weak.state.monsters[0].add_power(create_power("Weak", 1, weak.state.monsters[0].id))
        _set_piles(weak, hand_cards=[CardInstance("HeelHook", upgraded=True)], draw_cards=[CardInstance("Strike")])
        assert weak.play_card(0, 0)
        assert weak.state.monsters[0].hp == 32
        assert weak.state.player.energy == 1
        assert [card.card_id for card in weak.state.card_manager.hand.cards] == ["Strike"]

    def test_masterful_stab_gains_cost_when_player_takes_damage_and_persists(self):
        combat = _make_combat(energy=1, attack_damage=0)
        masterful_stab = CardInstance("MasterfulStab", upgraded=True)
        _set_piles(combat, hand_cards=[], draw_cards=[], discard_cards=[masterful_stab])

        assert masterful_stab.cost_for_turn == 0
        combat.state.player.take_damage(5)
        assert masterful_stab.cost_for_turn == 1

        combat.state.player.take_damage(3)
        assert masterful_stab.cost_for_turn == 2

        combat.state.card_manager.discard_pile.remove(masterful_stab)
        combat.state.card_manager.hand.add(masterful_stab)
        assert masterful_stab.cost_for_turn == 2
        assert masterful_stab.damage == 16

    def test_riddle_with_holes_hits_five_times(self):
        combat = _make_combat(energy=2, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("RiddleWithHoles")], draw_cards=[])

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 25

        upgraded = _make_combat(energy=2, attack_damage=0)
        _set_piles(upgraded, hand_cards=[CardInstance("RiddleWithHoles", upgraded=True)], draw_cards=[])
        assert upgraded.play_card(0, 0)
        assert upgraded.state.monsters[0].hp == 20

    def test_unload_discards_all_other_hand_cards_after_damage(self):
        combat = _make_combat(energy=1, attack_damage=0)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Unload", upgraded=True), CardInstance("Strike"), CardInstance("Deflect"), CardInstance("Blur")],
            draw_cards=[],
        )

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 22
        assert combat.state.card_manager.hand.cards == []
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Strike", "Deflect", "Blur", "Unload"]

        empty_other = _make_combat(energy=1, attack_damage=0)
        _set_piles(empty_other, hand_cards=[CardInstance("Unload")], draw_cards=[])
        assert empty_other.play_card(0, 0)
        assert empty_other.state.monsters[0].hp == 26
