from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 40):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=0, name="Attack"))


def _make_combat(*, monster_hps: list[int] | None = None, relics: list[str] | None = None) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [DummyAttackMonster(f"Dummy{idx}", hp=hp) for idx, hp in enumerate(monster_hps or [40])]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=70,
        player_max_hp=70,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["DeadlyPoison", "PoisonedStab", "BouncingFlask", "NoxiousFumes"],
        relics=relics or [],
    )
    combat.state.player.max_energy = 3
    combat.state.player.energy = 3
    combat.state.card_manager.set_max_energy(3)
    combat.state.card_manager.set_energy(3)
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


class TestSilentPoisonCombatIntegration:
    def test_deadly_poison_applies_correct_poison(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("DeadlyPoison")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].get_power_amount("Poison") == 5

    def test_deadly_poison_plus_applies_seven_poison(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("DeadlyPoison", upgraded=True)], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].get_power_amount("Poison") == 7

    def test_poisoned_stab_deals_damage_then_applies_poison(self):
        combat = _make_combat(monster_hps=[30])
        _set_piles(combat, hand_cards=[CardInstance("PoisonedStab")], draw_cards=[])

        assert combat.play_card(0, 0)

        monster = combat.state.monsters[0]
        assert monster.hp == 24
        assert monster.get_power_amount("Poison") == 3

    def test_bouncing_flask_applies_three_poison_hits_deterministically(self):
        first = _make_combat(monster_hps=[30, 30])
        second = _make_combat(monster_hps=[30, 30])
        _set_piles(first, hand_cards=[CardInstance("BouncingFlask")], draw_cards=[])
        _set_piles(second, hand_cards=[CardInstance("BouncingFlask")], draw_cards=[])

        assert first.play_card(0)
        assert second.play_card(0)

        assert [monster.get_power_amount("Poison") for monster in first.state.monsters] == [monster.get_power_amount("Poison") for monster in second.state.monsters]
        assert sum(monster.get_power_amount("Poison") for monster in first.state.monsters) == 9

    def test_bouncing_flask_plus_hits_four_times(self):
        combat = _make_combat(monster_hps=[30, 30])
        _set_piles(combat, hand_cards=[CardInstance("BouncingFlask", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)

        assert sum(monster.get_power_amount("Poison") for monster in combat.state.monsters) == 12

    def test_noxious_fumes_applies_power(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("NoxiousFumes")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.get_power_amount("NoxiousFumes") == 2

    def test_noxious_fumes_applies_poison_to_all_enemies_at_end_of_turn(self):
        combat = _make_combat(monster_hps=[30, 30])
        _set_piles(combat, hand_cards=[CardInstance("NoxiousFumes")], draw_cards=[CardInstance("Strike")] * 5)

        assert combat.play_card(0)
        combat.end_player_turn()

        assert [monster.hp for monster in combat.state.monsters] == [28, 28]
        assert [monster.get_power_amount("Poison") for monster in combat.state.monsters] == [1, 1]

    def test_monster_poison_ticks_and_reduces_by_one_at_start_of_monster_turn(self):
        combat = _make_combat(monster_hps=[30])
        _set_piles(combat, hand_cards=[CardInstance("DeadlyPoison")], draw_cards=[CardInstance("Strike")] * 5)

        assert combat.play_card(0, 0)
        combat.end_player_turn()

        monster = combat.state.monsters[0]
        assert monster.hp == 25
        assert monster.get_power_amount("Poison") == 4

    def test_specimen_transfer_still_works_with_formal_poison_power(self):
        combat = _make_combat(monster_hps=[4, 20], relics=["The Specimen"])
        _set_piles(combat, hand_cards=[CardInstance("DeadlyPoison")], draw_cards=[CardInstance("Strike")] * 5)

        assert combat.play_card(0, 0)
        combat.end_player_turn()

        assert combat.state.monsters[0].is_dead()
        assert combat.state.monsters[1].hp == 16
        assert combat.state.monsters[1].get_power_amount("Poison") == 3
