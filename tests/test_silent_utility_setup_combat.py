from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
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
        deck=["Distraction", "EscapePlan", "Setup", "Nightmare", "Doppelganger", "Deflect", "Blur", "Strike"],
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


class TestSilentUtilitySetupCombat:
    def test_distraction_generates_random_silent_skill_at_zero_cost(self):
        combat = _make_combat(energy=1, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Distraction")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.card_manager.get_hand_size() == 1
        generated = combat.state.card_manager.hand.cards[0]
        assert generated.card_type == generated.card_type.SKILL
        assert generated.cost_for_turn == 0
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Distraction"]

        upgraded = _make_combat(energy=0, attack_damage=0)
        _set_piles(upgraded, hand_cards=[CardInstance("Distraction", upgraded=True)], draw_cards=[])
        assert upgraded.play_card(0)
        assert upgraded.state.card_manager.get_hand_size() == 1

    def test_escape_plan_only_gains_block_when_drawn_card_is_not_skill(self):
        nonskill = _make_combat(energy=0, attack_damage=0)
        _set_piles(nonskill, hand_cards=[CardInstance("EscapePlan", upgraded=True)], draw_cards=[CardInstance("Strike")])
        assert nonskill.play_card(0)
        assert nonskill.state.player.block == 5

        skill = _make_combat(energy=0, attack_damage=0)
        _set_piles(skill, hand_cards=[CardInstance("EscapePlan")], draw_cards=[CardInstance("Blur")])
        assert skill.play_card(0)
        assert skill.state.player.block == 0

        no_draw = _make_combat(energy=0, attack_damage=0)
        no_draw.state.player.add_power(__import__("sts_py.engine.combat.powers", fromlist=["create_power"]).create_power("No Draw", 1, "player"))
        _set_piles(no_draw, hand_cards=[CardInstance("EscapePlan")], draw_cards=[CardInstance("Strike")])
        assert no_draw.play_card(0)
        assert no_draw.state.player.block == 0

    def test_setup_moves_first_other_card_to_top_and_sets_cost_zero_for_turn(self):
        combat = _make_combat(energy=1, attack_damage=0)
        target = CardInstance("Blur")
        _set_piles(combat, hand_cards=[CardInstance("Setup"), target, CardInstance("Strike")], draw_cards=[])

        assert combat.play_card(0)

        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Strike"]
        assert combat.state.card_manager.draw_pile.cards[-1].card_id == "Blur"
        assert combat.state.card_manager.draw_pile.cards[-1].cost_for_turn == 0

    def test_nightmare_generates_three_copies_next_turn(self):
        combat = _make_combat(energy=3, attack_damage=0)
        target = CardInstance("Deflect")
        _set_piles(combat, hand_cards=[CardInstance("Nightmare"), target], draw_cards=[CardInstance("Strike") for _ in range(5)])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Nightmare") == 3

        combat.end_player_turn()

        hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
        assert hand_ids.count("Deflect") == 3

        upgraded = _make_combat(energy=2, attack_damage=0)
        _set_piles(upgraded, hand_cards=[CardInstance("Nightmare", upgraded=True), CardInstance("Deflect")], draw_cards=[])
        assert upgraded.play_card(0)
        assert upgraded.state.player.energy == 0

    def test_doppelganger_ends_turn_and_grants_next_turn_energy_and_draw(self):
        combat = _make_combat(energy=3, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Doppelganger")], draw_cards=[CardInstance("Strike") for _ in range(8)])

        assert combat.play_card(0)
        assert combat.state.phase.name == "PLAYER_TURN"
        assert combat.state.player.energy == 6
        assert combat.state.card_manager.get_hand_size() == 8

        upgraded = _make_combat(energy=2, attack_damage=0)
        _set_piles(upgraded, hand_cards=[CardInstance("Doppelganger", upgraded=True)], draw_cards=[CardInstance("Strike") for _ in range(8)])
        assert upgraded.play_card(0)
        assert upgraded.state.player.energy == 5
