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
        deck=deck or ["Skim", "Seek", "Aggregate", "AutoShields", "BootSequence"],
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


class TestDefectDrawSetupCombat:
    def test_skim_draws_three_or_four_and_respects_no_draw(self):
        combat = _make_combat(energy=1)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Skim")],
            draw_cards=[CardInstance("Strike_B"), CardInstance("Defend_B"), CardInstance("Zap"), CardInstance("Dualcast")],
        )

        assert combat.play_card(0)
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Dualcast", "Zap", "Defend_B"]

        upgraded = _make_combat(energy=1)
        _set_piles(
            upgraded,
            hand_cards=[CardInstance("Skim", upgraded=True)],
            draw_cards=[CardInstance("Strike_B"), CardInstance("Defend_B"), CardInstance("Zap"), CardInstance("Dualcast")],
        )
        assert upgraded.play_card(0)
        assert [card.card_id for card in upgraded.state.card_manager.hand.cards] == ["Dualcast", "Zap", "Defend_B", "Strike_B"]

        no_draw = _make_combat(energy=1)
        no_draw.state.player.add_power(__import__("sts_py.engine.combat.powers", fromlist=["create_power"]).create_power("No Draw", 1, "player"))
        _set_piles(no_draw, hand_cards=[CardInstance("Skim")], draw_cards=[CardInstance("Strike_B")])
        assert no_draw.play_card(0)
        assert no_draw.state.card_manager.hand.cards == []

    def test_seek_moves_top_of_draw_pile_to_hand_and_respects_hand_limit(self):
        combat = _make_combat(energy=0)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Seek")],
            draw_cards=[CardInstance("Strike_B"), CardInstance("Defend_B"), CardInstance("Zap")],
        )

        assert combat.play_card(0)
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Zap"]
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Seek"]

        upgraded = _make_combat(energy=0)
        _set_piles(
            upgraded,
            hand_cards=[CardInstance("Seek", upgraded=True)],
            draw_cards=[CardInstance("Strike_B"), CardInstance("Defend_B"), CardInstance("Zap")],
        )
        assert upgraded.play_card(0)
        assert [card.card_id for card in upgraded.state.card_manager.hand.cards] == ["Zap", "Defend_B"]

        hand_limit = _make_combat(energy=0)
        fullish_hand = [CardInstance("Seek", upgraded=True)] + [CardInstance("Strike_B") for _ in range(9)]
        _set_piles(hand_limit, hand_cards=fullish_hand, draw_cards=[CardInstance("Defend_B"), CardInstance("Zap")])
        assert hand_limit.play_card(0)
        assert len(hand_limit.state.card_manager.hand.cards) == 10
        assert any(card.card_id == "Zap" for card in hand_limit.state.card_manager.hand.cards)
        assert any(card.card_id == "Defend_B" for card in hand_limit.state.card_manager.draw_pile.cards)

    def test_aggregate_gains_energy_by_draw_pile_size_divisor(self):
        combat = _make_combat(energy=1)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Aggregate")],
            draw_cards=[CardInstance("Strike_B") for _ in range(9)],
        )

        assert combat.play_card(0)
        assert combat.state.player.energy == 2
        assert combat.state.card_manager.energy == 2

        upgraded = _make_combat(energy=1)
        _set_piles(
            upgraded,
            hand_cards=[CardInstance("Aggregate", upgraded=True)],
            draw_cards=[CardInstance("Strike_B") for _ in range(10)],
        )
        assert upgraded.play_card(0)
        assert upgraded.state.player.energy == 3
        assert upgraded.state.card_manager.energy == 3

    def test_auto_shields_only_works_when_current_block_is_zero(self):
        combat = _make_combat(energy=1)
        _set_piles(combat, hand_cards=[CardInstance("AutoShields")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.block == 11

        blocked = _make_combat(energy=1)
        blocked.state.player.block = 3
        _set_piles(blocked, hand_cards=[CardInstance("AutoShields", upgraded=True)], draw_cards=[])
        assert blocked.play_card(0)
        assert blocked.state.player.block == 3

    def test_boot_sequence_is_in_opening_hand_and_exhausts_after_play(self):
        combat = _make_combat(deck=["Strike_B", "Defend_B", "Zap", "Dualcast", "BallLightning", "BootSequence"], energy=0)

        assert any(card.card_id == "BootSequence" for card in combat.state.card_manager.hand.cards)

        boot_index = next(i for i, card in enumerate(combat.state.card_manager.hand.cards) if card.card_id == "BootSequence")
        assert combat.play_card(boot_index)

        assert combat.state.player.block == 10
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["BootSequence"]

        upgraded = _make_combat(energy=0)
        _set_piles(upgraded, hand_cards=[CardInstance("BootSequence", upgraded=True)], draw_cards=[])
        assert upgraded.play_card(0)
        assert upgraded.state.player.block == 13
