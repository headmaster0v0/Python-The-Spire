from __future__ import annotations

from sts_py.engine.combat.card_effects import BodySlamEffect, EntrenchEffect, JuggernautEffect, SetBlockFlagEffect, get_card_effects
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, hp: int = 120, attack_damage: int = 0):
        super().__init__(id="DummyAttack", name="Dummy Attack", hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hp: int = 120, attack_damage: int = 0) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monster = DummyAttackMonster(hp=monster_hp, attack_damage=attack_damage)
    return CombatEngine.create_with_monsters(
        monsters=[monster],
        player_hp=80,
        player_max_hp=80,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Strike", "Strike", "Strike", "Defend", "Defend", "Bash", "ShrugItOff", "PommelStrike", "TrueGrit"],
        relics=[],
    )


def _make_multi_monster_combat(*, monster_hps: list[int]) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [DummyAttackMonster(hp=hp, attack_damage=0) for hp in monster_hps]
    return CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=80,
        player_max_hp=80,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Strike", "Strike", "Strike", "Defend", "Defend", "Bash", "ShrugItOff", "PommelStrike", "TrueGrit"],
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


class TestIroncladBlockPayoffEffects:
    def test_barricade_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("Barricade"))

        assert len(effects) == 1
        assert isinstance(effects[0], SetBlockFlagEffect)

    def test_entrench_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("Entrench"))

        assert len(effects) == 1
        assert isinstance(effects[0], EntrenchEffect)

    def test_body_slam_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("BodySlam"), target_idx=0)

        assert len(effects) == 1
        assert isinstance(effects[0], BodySlamEffect)

    def test_juggernaut_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("Juggernaut"))

        assert len(effects) == 1
        assert isinstance(effects[0], JuggernautEffect)


class TestIroncladBlockPayoffIntegration:
    def test_barricade_retains_block_across_turn_end(self):
        combat = _make_combat(attack_damage=0)
        combat.state.player.max_energy = 5
        combat.state.player.energy = 5
        combat.state.card_manager.set_max_energy(5)
        combat.state.card_manager.set_energy(5)
        _set_piles(combat, hand_cards=[CardInstance("Barricade"), CardInstance("Defend")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.play_card(0)
        assert combat.state.player.block == 5

        combat.end_player_turn()

        assert combat.state.player.block == 5

    def test_juggernaut_applies_power(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Juggernaut")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Juggernaut") == 5

    def test_juggernaut_triggers_on_gained_block_single_target(self):
        combat = _make_combat(monster_hp=40)
        _set_piles(combat, hand_cards=[CardInstance("Juggernaut"), CardInstance("Defend")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.play_card(0)

        assert combat.state.player.block == 5
        assert combat.state.monsters[0].hp == 35

    def test_entrench_doubles_current_block(self):
        combat = _make_combat()
        combat.state.player.block = 7
        _set_piles(combat, hand_cards=[CardInstance("Entrench")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.block == 14

    def test_entrench_triggers_juggernaut_on_added_block(self):
        combat = _make_combat(monster_hp=40)
        combat.state.player.max_energy = 4
        combat.state.player.energy = 4
        combat.state.card_manager.set_max_energy(4)
        combat.state.card_manager.set_energy(4)
        combat.state.player.block = 6
        _set_piles(combat, hand_cards=[CardInstance("Juggernaut"), CardInstance("Entrench")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.play_card(0)

        assert combat.state.player.block == 12
        assert combat.state.monsters[0].hp == 35

    def test_body_slam_uses_current_block_without_consuming_it(self):
        combat = _make_combat(monster_hp=40)
        combat.state.player.block = 11
        _set_piles(combat, hand_cards=[CardInstance("BodySlam")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 29
        assert combat.state.player.block == 11

    def test_barricade_entrench_body_slam_chain_works_in_one_combat(self):
        combat = _make_combat(monster_hp=40)
        combat.state.player.max_energy = 10
        combat.state.player.energy = 10
        combat.state.card_manager.set_max_energy(10)
        combat.state.card_manager.set_energy(10)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Barricade"), CardInstance("Defend"), CardInstance("Entrench"), CardInstance("BodySlam")],
            draw_cards=[],
        )

        assert combat.play_card(0)
        assert combat.play_card(0)
        assert combat.state.player.block == 5
        assert combat.play_card(0)
        assert combat.state.player.block == 10
        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 30
        assert combat.state.player.block == 10
