from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 80, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hps: list[int] | None = None, energy: int = 3, attack_damage: int = 8) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyAttackMonster(f"Dummy{index}", hp=hp, attack_damage=attack_damage)
        for index, hp in enumerate(monster_hps or [80])
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=80,
        player_max_hp=80,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Clothesline", "Thunderclap", "SwordBoomerang", "PommelStrike"],
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


class TestIroncladCommonAttackUtilityIntegration:
    def test_clothesline_deals_damage_then_applies_two_weak(self):
        combat = _make_combat(monster_hps=[50])
        _set_piles(combat, hand_cards=[CardInstance("Clothesline")], draw_cards=[])

        assert combat.play_card(0, 0)

        monster = combat.state.monsters[0]
        assert monster.hp == 38
        assert monster.get_power_amount("Weak") == 2

    def test_clothesline_plus_applies_three_weak(self):
        combat = _make_combat(monster_hps=[50])
        _set_piles(combat, hand_cards=[CardInstance("Clothesline", upgraded=True)], draw_cards=[])

        assert combat.play_card(0, 0)

        monster = combat.state.monsters[0]
        assert monster.hp == 36
        assert monster.get_power_amount("Weak") == 3

    def test_thunderclap_hits_all_living_monsters_and_applies_vulnerable(self):
        combat = _make_combat(monster_hps=[30, 30])
        _set_piles(combat, hand_cards=[CardInstance("Thunderclap")], draw_cards=[])

        assert combat.play_card(0)

        assert [monster.hp for monster in combat.state.monsters] == [26, 26]
        assert [monster.get_power_amount("Vulnerable") for monster in combat.state.monsters] == [1, 1]

    def test_thunderclap_plus_applies_two_vulnerable(self):
        combat = _make_combat(monster_hps=[30, 30])
        _set_piles(combat, hand_cards=[CardInstance("Thunderclap", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)

        assert [monster.get_power_amount("Vulnerable") for monster in combat.state.monsters] == [2, 2]

    def test_sword_boomerang_hits_three_times_with_deterministic_distribution(self):
        combat = _make_combat(monster_hps=[20, 20])
        _set_piles(combat, hand_cards=[CardInstance("SwordBoomerang")], draw_cards=[])

        assert combat.play_card(0)

        assert [monster.hp for monster in combat.state.monsters] == [17, 14]

    def test_sword_boomerang_plus_hits_four_times(self):
        combat = _make_combat(monster_hps=[20, 20])
        _set_piles(combat, hand_cards=[CardInstance("SwordBoomerang", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)

        total_damage_taken = sum(20 - monster.hp for monster in combat.state.monsters)
        assert total_damage_taken == 16

    def test_sword_boomerang_focuses_last_hits_on_only_survivor(self):
        combat = _make_combat(monster_hps=[3, 20])
        _set_piles(combat, hand_cards=[CardInstance("SwordBoomerang", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.monsters[0].hp == 0
        assert combat.state.monsters[1].hp == 8

    def test_pommel_strike_deals_damage_then_draws_one(self):
        combat = _make_combat(monster_hps=[30])
        _set_piles(
            combat,
            hand_cards=[CardInstance("PommelStrike")],
            draw_cards=[CardInstance("Strike")],
        )

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 21
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Strike"]

    def test_pommel_strike_plus_draws_two(self):
        combat = _make_combat(monster_hps=[30])
        _set_piles(
            combat,
            hand_cards=[CardInstance("PommelStrike", upgraded=True)],
            draw_cards=[CardInstance("Strike"), CardInstance("Defend")],
        )

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 20
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Defend", "Strike"]

    def test_pommel_strike_draw_respects_no_draw(self):
        combat = _make_combat(monster_hps=[30])
        combat.state.player.add_power(create_power("No Draw", 1, "player"))
        _set_piles(
            combat,
            hand_cards=[CardInstance("PommelStrike")],
            draw_cards=[CardInstance("Strike")],
        )

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 21
        assert combat.state.card_manager.hand.cards == []
