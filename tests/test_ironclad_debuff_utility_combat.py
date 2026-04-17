from __future__ import annotations

from sts_py.engine.combat.card_effects import IntimidateEffect, ShockwaveEffect, get_card_effects
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 120, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hps: list[int], attack_damage: int = 8) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyAttackMonster(f"Dummy{index}", hp=hp, attack_damage=attack_damage)
        for index, hp in enumerate(monster_hps)
    ]
    return CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=80,
        player_max_hp=80,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Defend", "Shockwave", "Uppercut", "Intimidate"],
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


class TestIroncladDebuffUtilityEffects:
    def test_shockwave_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("Shockwave"))

        assert len(effects) == 1
        assert isinstance(effects[0], ShockwaveEffect)

    def test_intimidate_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("Intimidate"))

        assert len(effects) == 1
        assert isinstance(effects[0], IntimidateEffect)

    def test_shockwave_and_intimidate_exhaust_after_play(self):
        combat = _make_combat(monster_hps=[40])
        _set_piles(combat, hand_cards=[CardInstance("Shockwave")], draw_cards=[])

        assert combat.play_card(0)
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Shockwave"]

        combat = _make_combat(monster_hps=[40])
        _set_piles(combat, hand_cards=[CardInstance("Intimidate")], draw_cards=[])

        assert combat.play_card(0)
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Intimidate"]

    def test_uppercut_plus_uses_two_turns_of_both_debuffs(self):
        card = CardInstance("Uppercut", upgraded=True)

        assert card.magic_number == 2


class TestIroncladDebuffUtilityIntegration:
    def test_shockwave_applies_weak_and_vulnerable_to_all_living_monsters(self):
        combat = _make_combat(monster_hps=[40, 40])
        _set_piles(combat, hand_cards=[CardInstance("Shockwave")], draw_cards=[])

        assert combat.play_card(0)

        assert [monster.get_power_amount("Weak") for monster in combat.state.monsters] == [3, 3]
        assert [monster.get_power_amount("Vulnerable") for monster in combat.state.monsters] == [3, 3]
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Shockwave"]

    def test_shockwave_plus_applies_five_turns_to_all_living_monsters(self):
        combat = _make_combat(monster_hps=[40, 40])
        _set_piles(combat, hand_cards=[CardInstance("Shockwave", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)

        assert [monster.get_power_amount("Weak") for monster in combat.state.monsters] == [5, 5]
        assert [monster.get_power_amount("Vulnerable") for monster in combat.state.monsters] == [5, 5]

    def test_intimidate_applies_weak_to_all_living_monsters(self):
        combat = _make_combat(monster_hps=[40, 40])
        _set_piles(combat, hand_cards=[CardInstance("Intimidate")], draw_cards=[])

        assert combat.play_card(0)

        assert [monster.get_power_amount("Weak") for monster in combat.state.monsters] == [1, 1]
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Intimidate"]

    def test_intimidate_plus_applies_two_weak(self):
        combat = _make_combat(monster_hps=[40, 40])
        _set_piles(combat, hand_cards=[CardInstance("Intimidate", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)

        assert [monster.get_power_amount("Weak") for monster in combat.state.monsters] == [2, 2]

    def test_uppercut_hits_target_then_applies_matching_debuffs(self):
        combat = _make_combat(monster_hps=[50, 50])
        _set_piles(combat, hand_cards=[CardInstance("Uppercut")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert [monster.hp for monster in combat.state.monsters] == [37, 50]
        assert combat.state.monsters[0].get_power_amount("Weak") == 1
        assert combat.state.monsters[0].get_power_amount("Vulnerable") == 1
        assert combat.state.monsters[1].get_power_amount("Weak") == 0
        assert combat.state.monsters[1].get_power_amount("Vulnerable") == 0

    def test_uppercut_plus_applies_two_weak_and_two_vulnerable(self):
        combat = _make_combat(monster_hps=[50])
        _set_piles(combat, hand_cards=[CardInstance("Uppercut", upgraded=True)], draw_cards=[])

        assert combat.play_card(0, 0)

        monster = combat.state.monsters[0]
        assert monster.get_power_amount("Weak") == 2
        assert monster.get_power_amount("Vulnerable") == 2

    def test_weak_reduces_future_monster_attack_damage(self):
        combat = _make_combat(monster_hps=[40], attack_damage=8)
        _set_piles(combat, hand_cards=[CardInstance("Intimidate")], draw_cards=[])

        assert combat.state.monsters[0].get_intent_damage() == 8
        assert combat.play_card(0)

        assert combat.state.monsters[0].get_intent_damage() == 6
        combat.end_player_turn()

        assert combat.state.player.hp == 74

    def test_shockwave_and_intimidate_skip_dead_monsters_without_error(self):
        combat = _make_combat(monster_hps=[0, 40])
        combat.state.monsters[0].hp = 0
        _set_piles(combat, hand_cards=[CardInstance("Shockwave"), CardInstance("Intimidate")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.play_card(0)

        assert combat.state.monsters[0].get_power_amount("Weak") == 0
        assert combat.state.monsters[0].get_power_amount("Vulnerable") == 0
        assert combat.state.monsters[1].get_power_amount("Weak") == 4
        assert combat.state.monsters[1].get_power_amount("Vulnerable") == 3
