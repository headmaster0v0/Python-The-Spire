from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
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


def _bind_cards(combat: CombatEngine, cards: list[CardInstance]) -> list[CardInstance]:
    for card in cards:
        card._combat_state = combat.state
    return cards


def _set_piles(
    combat: CombatEngine,
    *,
    hand_cards: list[CardInstance] | None = None,
    draw_cards: list[CardInstance] | None = None,
    exhaust_cards: list[CardInstance] | None = None,
) -> None:
    cm = combat.state.card_manager
    cm.hand.cards = _bind_cards(combat, hand_cards or [])
    cm.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    cm.discard_pile.cards = []
    cm.exhaust_pile.cards = _bind_cards(combat, exhaust_cards or [])


class TestIroncladExhaustCombat:
    def test_corruption_refreshes_current_hand_skill_costs(self):
        combat = _make_combat(attack_damage=0)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Corruption"), CardInstance("Defend"), CardInstance("ShrugItOff")],
            draw_cards=[],
        )

        assert combat.play_card(0)

        costs = {card.card_id: card.cost_for_turn for card in combat.state.card_manager.hand.cards}
        assert costs["Defend"] == 0
        assert costs["ShrugItOff"] == 0

    def test_corruption_makes_skill_free_and_exhausts_on_play(self):
        combat = _make_combat(attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Defend")], draw_cards=[])
        combat.state.player.add_power(create_power("Corruption", 1, "player"))
        combat.state.player.energy = 0
        combat.state.card_manager.set_energy(0)

        assert combat.play_card(0)
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Defend"]

    def test_newly_drawn_skill_is_free_under_corruption(self):
        combat = _make_combat(attack_damage=0)
        _set_piles(combat, hand_cards=[], draw_cards=[CardInstance("Defend")])
        combat.state.player.add_power(create_power("Corruption", 1, "player"))

        drawn = combat.state.card_manager.draw_card(combat.ai_rng)

        assert drawn is not None
        assert drawn.card_id == "Defend"
        assert drawn.cost_for_turn == 0

    def test_burning_pact_triggers_feel_no_pain_and_dark_embrace(self):
        combat = _make_combat(attack_damage=0)
        _set_piles(
            combat,
            hand_cards=[CardInstance("BurningPact"), CardInstance("Defend")],
            draw_cards=[CardInstance("Strike"), CardInstance("Bash"), CardInstance("PommelStrike")],
        )
        combat.state.player.add_power(create_power("FeelNoPain", 3, "player"))
        combat.state.player.add_power(create_power("DarkEmbrace", 1, "player"))

        assert combat.play_card(0)

        assert combat.state.player.block == 3
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Defend"]
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["BurningPact"]
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["PommelStrike", "Bash", "Strike"]

    def test_second_wind_triggers_exhaust_powers_per_card(self):
        combat = _make_combat(attack_damage=0)
        _set_piles(
            combat,
            hand_cards=[CardInstance("SecondWind"), CardInstance("Defend"), CardInstance("ShrugItOff"), CardInstance("Strike")],
            draw_cards=[CardInstance("Bash"), CardInstance("PommelStrike")],
        )
        combat.state.player.add_power(create_power("FeelNoPain", 4, "player"))
        combat.state.player.add_power(create_power("DarkEmbrace", 1, "player"))

        assert combat.play_card(0)

        assert combat.state.player.block == 18
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Defend", "ShrugItOff"]
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Strike", "PommelStrike", "Bash"]

    def test_fiend_fire_triggers_exhaust_powers_and_scales_damage(self):
        combat = _make_combat(monster_hp=100, attack_damage=0)
        _set_piles(
            combat,
            hand_cards=[CardInstance("FiendFire"), CardInstance("Strike"), CardInstance("Defend")],
            draw_cards=[CardInstance("Bash"), CardInstance("ShrugItOff")],
        )
        combat.state.player.add_power(create_power("FeelNoPain", 3, "player"))
        combat.state.player.add_power(create_power("DarkEmbrace", 1, "player"))

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 86
        assert combat.state.player.block == 9
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Strike", "Defend", "FiendFire"]
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["ShrugItOff", "Bash"]

    def test_exhume_uses_deterministic_combat_rng(self):
        first = _make_combat(attack_damage=0)
        second = _make_combat(attack_damage=0)
        exhaust_cards = [CardInstance("Bash"), CardInstance("ShrugItOff")]

        _set_piles(first, hand_cards=[CardInstance("Exhume")], draw_cards=[], exhaust_cards=[card.make_stat_equivalent_copy() for card in exhaust_cards])
        _set_piles(second, hand_cards=[CardInstance("Exhume")], draw_cards=[], exhaust_cards=[card.make_stat_equivalent_copy() for card in exhaust_cards])

        assert first.play_card(0)
        assert second.play_card(0)

        first_hand = [card.card_id for card in first.state.card_manager.hand.cards]
        second_hand = [card.card_id for card in second.state.card_manager.hand.cards]
        assert first_hand == second_hand
        assert len(first_hand) == 1

    def test_infernal_blade_uses_combat_rng_and_generates_zero_cost_attack(self):
        first = _make_combat(attack_damage=0)
        second = _make_combat(attack_damage=0)
        _set_piles(first, hand_cards=[CardInstance("InfernalBlade")], draw_cards=[])
        _set_piles(second, hand_cards=[CardInstance("InfernalBlade")], draw_cards=[])

        assert first.play_card(0)
        assert second.play_card(0)

        first_generated = first.state.card_manager.hand.cards[0]
        second_generated = second.state.card_manager.hand.cards[0]
        assert first_generated.card_id == second_generated.card_id
        assert first_generated.card_type.value == "ATTACK"
        assert first_generated.cost_for_turn == 0
        assert [card.card_id for card in first.state.card_manager.exhaust_pile.cards] == ["InfernalBlade"]
