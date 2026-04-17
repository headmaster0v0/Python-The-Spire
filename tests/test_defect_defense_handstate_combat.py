from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
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
        deck=["ConserveBattery", "Equilibrium", "ForceField", "Stack", "SteamBarrier", "Loop", "Storm"],
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


class TestDefectDefenseHandstateCombat:
    def test_conserve_battery_gives_block_and_next_turn_energy(self):
        combat = _make_combat(energy=1, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("ConserveBattery")], draw_cards=[CardInstance("Strike_B")] * 5)

        assert combat.play_card(0)
        assert combat.state.player.block == 7
        assert combat.state.player.get_power_amount("EnergizedBlue") == 1

        combat.end_player_turn()
        assert combat.state.player.energy == 2
        assert combat.state.card_manager.energy == 2
        assert combat.state.player.get_power_amount("EnergizedBlue") == 0

        assert CardInstance("ConserveBattery", upgraded=True).block == 10

    def test_equilibrium_retains_non_ethereal_cards_but_not_ethereal(self):
        combat = _make_combat(energy=2)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Equilibrium"), CardInstance("Strike_B"), CardInstance("Carnage")],
            draw_cards=[CardInstance("Zap"), CardInstance("Leap"), CardInstance("Coolheaded"), CardInstance("BeamCell"), CardInstance("Claw")],
        )

        assert combat.play_card(0)
        assert combat.state.player.block == 13
        assert combat.state.player.get_power_amount("Equilibrium") == 1

        combat.end_player_turn()

        assert "Strike_B" in [card.card_id for card in combat.state.card_manager.hand.cards]
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Carnage"]

    def test_force_field_cost_reduces_with_power_plays_and_future_draws(self):
        combat = _make_combat(energy=2)
        field_in_hand = CardInstance("ForceField")
        _set_piles(
            combat,
            hand_cards=[field_in_hand, CardInstance("Loop"), CardInstance("Storm")],
            draw_cards=[],
        )

        assert field_in_hand.cost_for_turn == 4
        assert combat.play_card(1)
        assert field_in_hand.cost_for_turn == 3

        assert combat.play_card(1)
        assert field_in_hand.cost_for_turn == 2

        drawn_case = _make_combat(energy=2)
        _set_piles(
            drawn_case,
            hand_cards=[CardInstance("Loop"), CardInstance("Storm")],
            draw_cards=[CardInstance("ForceField")],
        )
        assert drawn_case.play_card(0)
        assert drawn_case.play_card(0)
        drawn = drawn_case.state.card_manager.draw_card(drawn_case.ai_rng)
        assert drawn is not None and drawn.card_id == "ForceField"
        assert drawn.cost_for_turn == 2

    def test_stack_uses_discard_pile_size_and_plus_adds_three(self):
        combat = _make_combat(energy=1)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Stack")],
            draw_cards=[],
            discard_cards=[CardInstance("Strike_B"), CardInstance("Defend_B"), CardInstance("Zap")],
        )
        assert combat.play_card(0)
        assert combat.state.player.block == 3

        upgraded = _make_combat(energy=1)
        _set_piles(
            upgraded,
            hand_cards=[CardInstance("Stack", upgraded=True)],
            draw_cards=[],
            discard_cards=[CardInstance("Strike_B"), CardInstance("Defend_B"), CardInstance("Zap")],
        )
        assert upgraded.play_card(0)
        assert upgraded.state.player.block == 6

    def test_steam_barrier_decays_current_instance_across_plays(self):
        combat = _make_combat(energy=0)
        barrier = CardInstance("SteamBarrier")
        _set_piles(combat, hand_cards=[barrier], draw_cards=[])
        assert combat.play_card(0)
        played_copy = combat.state.card_manager.discard_pile.cards[-1]
        assert played_copy.base_block == 5

        combat.state.player.block = 0
        combat.state.card_manager.discard_pile.remove(played_copy)
        combat.state.card_manager.hand.add(played_copy)
        assert combat.play_card(0)
        played_copy = combat.state.card_manager.discard_pile.cards[-1]
        assert played_copy.base_block == 4

        upgraded = _make_combat(energy=0)
        upgraded_barrier = CardInstance("SteamBarrier", upgraded=True)
        _set_piles(upgraded, hand_cards=[upgraded_barrier], draw_cards=[])
        assert upgraded.play_card(0)
        upgraded_copy = upgraded.state.card_manager.discard_pile.cards[-1]
        assert upgraded_copy.base_block == 7
