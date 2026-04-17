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


def _make_combat(*, deck: list[str] | None = None, energy: int = 3, attack_damage: int = 0) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [DummyMonster("Dummy0", hp=40, attack_damage=attack_damage)]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=75,
        player_max_hp=75,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=deck or ["WhiteNoise", "Chaos", "Overclock", "CreativeAI"],
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


class TestDefectRandomSetupCombat:
    def test_white_noise_generates_zero_cost_power_and_plus_costs_zero(self):
        combat = _make_combat(energy=1)
        _set_piles(combat, hand_cards=[CardInstance("WhiteNoise")], draw_cards=[])

        assert combat.play_card(0)

        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["WhiteNoise"]
        assert len(combat.state.card_manager.hand.cards) == 1
        generated = combat.state.card_manager.hand.cards[0]
        assert generated.card_type == generated.card_type.POWER
        assert generated.cost_for_turn == 0

        assert CardInstance("WhiteNoise+").cost == 0

    def test_white_noise_generation_is_deterministic_for_same_seed(self):
        first = _make_combat(energy=1)
        _set_piles(first, hand_cards=[CardInstance("WhiteNoise")], draw_cards=[])
        assert first.play_card(0)
        first_generated = first.state.card_manager.hand.cards[0].card_id

        second = _make_combat(energy=1)
        _set_piles(second, hand_cards=[CardInstance("WhiteNoise")], draw_cards=[])
        assert second.play_card(0)
        second_generated = second.state.card_manager.hand.cards[0].card_id

        assert first_generated == second_generated

    def test_chaos_channels_random_orbs_deterministically(self):
        first = _make_combat(energy=1)
        _set_piles(first, hand_cards=[CardInstance("Chaos")], draw_cards=[])
        assert first.play_card(0)
        first_ids = [orb.orb_id for orb in first.state.player.orbs.channels]

        second = _make_combat(energy=1)
        _set_piles(second, hand_cards=[CardInstance("Chaos")], draw_cards=[])
        assert second.play_card(0)
        second_ids = [orb.orb_id for orb in second.state.player.orbs.channels]

        assert first_ids == second_ids
        assert len(first_ids) == 1
        assert set(first_ids) <= {"Lightning", "Frost", "Dark", "Plasma"}

    def test_chaos_plus_channels_two_random_orbs(self):
        combat = _make_combat(energy=1)
        _set_piles(combat, hand_cards=[CardInstance("Chaos", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)

        assert len(combat.state.player.orbs.channels) == 2
        assert {orb.orb_id for orb in combat.state.player.orbs.channels} <= {"Lightning", "Frost", "Dark", "Plasma"}

    def test_overclock_draws_and_adds_burn_even_under_no_draw(self):
        combat = _make_combat(energy=0)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Overclock")],
            draw_cards=[CardInstance("Strike_B"), CardInstance("Defend_B"), CardInstance("Zap")],
        )

        assert combat.play_card(0)

        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Zap", "Defend_B"]
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Burn", "Overclock"]

        no_draw = _make_combat(energy=0)
        no_draw.state.player.add_power(__import__("sts_py.engine.combat.powers", fromlist=["create_power"]).create_power("No Draw", 1, "player"))
        _set_piles(no_draw, hand_cards=[CardInstance("Overclock", upgraded=True)], draw_cards=[CardInstance("Strike_B")])
        assert no_draw.play_card(0)
        assert no_draw.state.card_manager.hand.cards == []
        assert [card.card_id for card in no_draw.state.card_manager.discard_pile.cards] == ["Burn", "Overclock"]

    def test_creative_ai_applies_power_and_generates_power_at_start_of_turn(self):
        combat = _make_combat(deck=["CreativeAI", "Strike_B", "Strike_B", "Strike_B", "Strike_B", "Strike_B"], energy=3, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("CreativeAI")], draw_cards=[CardInstance("Strike_B")] * 5)

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("CreativeAI") == 1

        combat.end_player_turn()

        power_cards = [card for card in combat.state.card_manager.hand.cards if card.card_type == card.card_type.POWER]
        assert len(power_cards) >= 1

    def test_creative_ai_generated_power_respects_hand_limit_overflow(self):
        combat = _make_combat(energy=0)
        combat.state.player.add_power(__import__("sts_py.engine.combat.powers", fromlist=["create_power"]).create_power("CreativeAI", 1, "player"))
        _set_piles(
            combat,
            hand_cards=[CardInstance("Strike_B") for _ in range(10)],
            draw_cards=[],
            discard_cards=[],
        )

        combat._process_player_start_of_turn_powers()

        assert len(combat.state.card_manager.hand.cards) == 10
        assert len(combat.state.card_manager.discard_pile.cards) == 1
        assert combat.state.card_manager.discard_pile.cards[0].card_type == combat.state.card_manager.discard_pile.cards[0].card_type.POWER
