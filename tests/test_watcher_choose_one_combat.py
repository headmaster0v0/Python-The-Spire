from __future__ import annotations

from sts_py.engine.combat.card_effects import OpenCombatChoiceEffect, get_card_effects
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.combat_state import CombatPhase
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.run.run_engine import RunEngine, RunPhase


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, hp: int = 80, attack_damage: int = 0):
        super().__init__(id="DummyAttack", name="Dummy Attack", hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hp: int = 80, attack_damage: int = 0) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monster = DummyAttackMonster(hp=monster_hp, attack_damage=attack_damage)
    return CombatEngine.create_with_monsters(
        monsters=[monster],
        player_hp=72,
        player_max_hp=72,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Strike", "Strike", "Strike", "Defend", "Defend", "Defend", "Defend", "Eruption", "Vigilance"],
        relics=[],
    )


def _bind_cards(combat: CombatEngine, cards: list[CardInstance]) -> list[CardInstance]:
    for card in cards:
        card._combat_state = combat.state
    return cards


def _set_piles(
    combat: CombatEngine,
    *,
    hand_ids: list[str] | None = None,
    draw_ids: list[str] | None = None,
) -> None:
    combat.state.card_manager.hand.cards = _bind_cards(
        combat,
        [CardInstance(card_id) for card_id in (hand_ids or [])],
    )
    combat.state.card_manager.draw_pile.cards = _bind_cards(
        combat,
        [CardInstance(card_id) for card_id in (draw_ids or [])],
    )
    combat.state.card_manager.discard_pile.cards = []
    combat.state.card_manager.exhaust_pile.cards = []


class TestWatcherWishEffects:
    def test_wish_effect_opens_combat_choice(self):
        effects = get_card_effects(CardInstance("Wish"))

        assert len(effects) == 1
        assert isinstance(effects[0], OpenCombatChoiceEffect)
        assert effects[0].choice_type == "wish"

    def test_wish_upgrade_uses_upgraded_option_values(self):
        card = CardInstance("Wish", upgraded=True)

        assert card.exhaust is True
        assert card.damage == 4
        assert card.block == 8
        assert card.magic_number == 30


class TestWatcherWishCombatIntegration:
    def test_playing_wish_creates_pending_choices_and_exhausts_card(self):
        combat = _make_combat()
        _set_piles(combat, hand_ids=["Wish"])

        assert combat.play_card(0)

        choices = combat.get_pending_choices()
        assert [choice["label"] for choice in choices] == [
            "Wish for Strength",
            "Wish for Plated Armor",
            "Wish for Riches",
        ]
        assert combat.state.card_manager.get_hand_size() == 0
        assert any(card.card_id == "Wish" for card in combat.state.card_manager.exhaust_pile.cards)

    def test_wish_strength_option_grants_strength(self):
        combat = _make_combat()
        _set_piles(combat, hand_ids=["Wish"])

        assert combat.play_card(0)
        assert combat.choose_combat_option(0) is True

        assert combat.state.player.strength == 3
        assert combat.state.pending_combat_choice is None
        assert combat.choose_combat_option(0) is False

    def test_wish_plated_armor_option_applies_power(self):
        combat = _make_combat()
        _set_piles(combat, hand_ids=["Wish"])

        assert combat.play_card(0)
        assert combat.choose_combat_option(1) is True

        assert combat.state.player.get_power_amount("Plated Armor") == 6
        assert combat.state.pending_combat_choice is None

    def test_wish_riches_option_stashes_bonus_gold(self):
        combat = _make_combat()
        _set_piles(combat, hand_ids=["Wish"])

        assert combat.play_card(0)
        assert combat.choose_combat_option(2) is True

        assert combat.state.pending_bonus_gold == 25

    def test_pending_choice_blocks_end_turn_until_resolved(self):
        combat = _make_combat()
        _set_piles(combat, hand_ids=["Wish"])

        assert combat.play_card(0)
        combat.end_player_turn()

        assert combat.state.phase == CombatPhase.PLAYER_TURN
        assert combat.state.pending_combat_choice is not None


class TestWatcherWishRunIntegration:
    def test_run_engine_bridges_combat_choice_api(self):
        engine = RunEngine.create("WATCHERWISHCHOICE", ascension=0, character_class="WATCHER")
        combat = _make_combat()
        _set_piles(combat, hand_ids=["Wish"])
        engine.state.combat = combat
        engine.state.phase = RunPhase.COMBAT

        assert engine.combat_play_card(0)
        choices = engine.get_combat_choices()

        assert len(choices) == 3
        assert choices[2]["label"] == "Wish for Riches"
        assert engine.choose_combat_option(0) is True
        assert engine.state.combat.state.player.strength == 3

    def test_wish_riches_adds_gold_on_victory(self):
        engine = RunEngine.create("WATCHERWISHRICHES", ascension=0, character_class="WATCHER")
        combat = _make_combat()
        _set_piles(combat, hand_ids=["Wish"])
        engine.state.combat = combat
        engine.state.phase = RunPhase.COMBAT
        starting_gold = engine.state.player_gold

        assert engine.combat_play_card(0)
        assert engine.choose_combat_option(2) is True
        combat.state.monsters[0].hp = 0
        engine.end_combat()

        assert engine.state.player_gold >= starting_gold + 25
        assert engine._pending_gold_reward >= 25
        assert engine.state.phase == RunPhase.REWARD

    def test_wish_riches_does_not_add_gold_on_loss(self):
        engine = RunEngine.create("WATCHERWISHLOSS", ascension=0, character_class="WATCHER")
        combat = _make_combat()
        _set_piles(combat, hand_ids=["Wish"])
        engine.state.combat = combat
        engine.state.phase = RunPhase.COMBAT
        starting_gold = engine.state.player_gold

        assert engine.combat_play_card(0)
        assert engine.choose_combat_option(2) is True
        combat.state.player.hp = 0
        engine.end_combat()

        assert engine.state.player_gold == starting_gold
        assert engine.state.phase == RunPhase.GAME_OVER
