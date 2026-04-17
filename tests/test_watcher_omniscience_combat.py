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
    def __init__(self, monster_id: str, hp: int = 80, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hps: list[int], energy: int = 4) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyAttackMonster(monster_id=f"Dummy{index}", hp=hp, attack_damage=0)
        for index, hp in enumerate(monster_hps)
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=72,
        player_max_hp=72,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Strike", "Strike", "Strike", "Defend", "Defend", "Defend", "Defend", "Eruption", "Vigilance"],
        relics=[],
    )
    combat.state.player.energy = energy
    combat.state.player.max_energy = energy
    combat.state.card_manager.set_energy(energy)
    combat.state.card_manager.set_max_energy(energy)
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
) -> None:
    combat.state.card_manager.hand.cards = _bind_cards(combat, hand_cards or [])
    combat.state.card_manager.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    combat.state.card_manager.discard_pile.cards = []
    combat.state.card_manager.exhaust_pile.cards = []


class TestWatcherOmniscienceEffects:
    def test_omniscience_effect_opens_combat_choice(self):
        effects = get_card_effects(CardInstance("Omniscience"))

        assert len(effects) == 1
        assert isinstance(effects[0], OpenCombatChoiceEffect)
        assert effects[0].choice_type == "omniscience"

    def test_omniscience_upgrade_keeps_magic_and_exhaust(self):
        card = CardInstance("Omniscience", upgraded=True)

        assert card.cost == 3
        assert card.magic_number == 2
        assert card.exhaust is True


class TestWatcherOmniscienceCombatIntegration:
    def test_playing_omniscience_creates_draw_pile_pending_choice(self):
        combat = _make_combat(monster_hps=[80], energy=4)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Omniscience")],
            draw_cards=[CardInstance("Devotion"), CardInstance("Strike")],
        )

        assert combat.play_card(0)

        choices = combat.get_pending_choices()
        assert [choice["label"] for choice in choices] == ["Devotion", "Strike"]
        assert all(choice["effect"] == "play_draw_pile_card" for choice in choices)
        assert combat.state.card_manager.get_hand_size() == 0
        assert any(card.card_id == "Omniscience" for card in combat.state.card_manager.exhaust_pile.cards)

    def test_empty_draw_pile_creates_no_pending_choice(self):
        combat = _make_combat(monster_hps=[80], energy=4)
        _set_piles(combat, hand_cards=[CardInstance("Omniscience")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.pending_combat_choice is None
        assert combat.get_pending_choices() == []
        assert any(card.card_id == "Omniscience" for card in combat.state.card_manager.exhaust_pile.cards)

    def test_choose_non_target_card_autoplays_twice_and_exhausts_original(self):
        combat = _make_combat(monster_hps=[80], energy=4)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Omniscience")],
            draw_cards=[CardInstance("Devotion")],
        )

        assert combat.play_card(0)
        energy_after_play = combat.state.player.energy

        assert combat.choose_combat_option(0) is True

        assert combat.state.player.get_power_amount("Devotion") == 4
        assert combat.state.player.energy == energy_after_play
        assert combat.state.pending_combat_choice is None
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards].count("Devotion") == 1
        all_remaining_ids = (
            [card.card_id for card in combat.state.card_manager.hand.cards]
            + [card.card_id for card in combat.state.card_manager.draw_pile.cards]
            + [card.card_id for card in combat.state.card_manager.discard_pile.cards]
            + [card.card_id for card in combat.state.card_manager.exhaust_pile.cards]
        )
        assert all_remaining_ids.count("Devotion") == 1

    def test_targeted_autoplay_uses_deterministic_rng_targeting(self):
        first = _make_combat(monster_hps=[40, 40], energy=4)
        second = _make_combat(monster_hps=[40, 40], energy=4)
        for combat in (first, second):
            _set_piles(
                combat,
                hand_cards=[CardInstance("Omniscience")],
                draw_cards=[CardInstance("Strike")],
            )

        assert first.play_card(0)
        assert second.play_card(0)
        assert first.choose_combat_option(0) is True
        assert second.choose_combat_option(0) is True

        first_hps = tuple(monster.hp for monster in first.state.monsters)
        second_hps = tuple(monster.hp for monster in second.state.monsters)
        assert first_hps == second_hps
        assert sum(40 - hp for hp in first_hps) == 12

    def test_pending_choice_blocks_play_and_end_turn_until_resolved(self):
        combat = _make_combat(monster_hps=[80], energy=5)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Omniscience"), CardInstance("Strike")],
            draw_cards=[CardInstance("Devotion")],
        )

        assert combat.play_card(0)
        assert combat.play_card(0, target_idx=0) is False

        combat.end_player_turn()

        assert combat.state.phase == CombatPhase.PLAYER_TURN
        assert combat.state.pending_combat_choice is not None

    def test_choice_cannot_be_resolved_twice(self):
        combat = _make_combat(monster_hps=[80], energy=4)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Omniscience")],
            draw_cards=[CardInstance("Devotion")],
        )

        assert combat.play_card(0)
        assert combat.choose_combat_option(0) is True
        assert combat.choose_combat_option(0) is False


class TestWatcherOmniscienceRunIntegration:
    def test_run_engine_bridges_draw_pile_combat_choices(self):
        engine = RunEngine.create("WATCHEROMNICHOICE", ascension=0, character_class="WATCHER")
        combat = _make_combat(monster_hps=[80], energy=4)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Omniscience")],
            draw_cards=[CardInstance("Devotion"), CardInstance("Strike")],
        )
        engine.state.combat = combat
        engine.state.phase = RunPhase.COMBAT

        assert engine.combat_play_card(0)
        choices = engine.get_combat_choices()

        assert [choice["label"] for choice in choices] == ["Devotion", "Strike"]

    def test_run_engine_choice_triggers_autoplay_without_extra_energy_cost(self):
        engine = RunEngine.create("WATCHEROMNIPLAY", ascension=0, character_class="WATCHER")
        combat = _make_combat(monster_hps=[80], energy=4)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Omniscience")],
            draw_cards=[CardInstance("Devotion")],
        )
        engine.state.combat = combat
        engine.state.phase = RunPhase.COMBAT

        assert engine.combat_play_card(0)
        energy_after_play = combat.state.player.energy

        assert engine.choose_combat_option(0) is True

        assert combat.state.player.energy == energy_after_play
        lingering_ids = (
            [card.card_id for card in combat.state.card_manager.hand.cards]
            + [card.card_id for card in combat.state.card_manager.draw_pile.cards]
            + [card.card_id for card in combat.state.card_manager.discard_pile.cards]
            + [card.card_id for card in combat.state.card_manager.exhaust_pile.cards]
        )
        assert lingering_ids.count("Devotion") == 1
