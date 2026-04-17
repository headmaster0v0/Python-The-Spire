from __future__ import annotations

import importlib

from sts_py.engine.combat.card_effects import DealDamageEffect, get_card_effects
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.run.events import ACT1_EVENTS
from sts_py.engine.run.run_engine import RunEngine, RunPhase
import sts_py.tools.ground_truth_harness as harness


SEED_STRING = "SEARINGBLOWTEST"
SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 80):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=0, name="Attack"))


def _make_combat(*, monster_hp: int = 80, energy: int = 3) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    combat = CombatEngine.create_with_monsters(
        monsters=[DummyAttackMonster("Dummy", hp=monster_hp)],
        player_hp=80,
        player_max_hp=80,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["SearingBlow"],
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


class TestIroncladSearingBlowRuntime:
    def test_searing_blow_base_damage_is_twelve(self):
        card = CardInstance("SearingBlow")

        assert card.card_id == "SearingBlow"
        assert card.upgraded is False
        assert card.times_upgraded == 0
        assert card.damage == 12

    def test_searing_blow_plus_one_and_plus_two_parse_correctly(self):
        plus_one = CardInstance("SearingBlow+1")
        plus_two = CardInstance("SearingBlow+2")

        assert plus_one.card_id == "SearingBlow"
        assert plus_one.upgraded is True
        assert plus_one.times_upgraded == 1
        assert plus_one.damage == 16

        assert plus_two.card_id == "SearingBlow"
        assert plus_two.upgraded is True
        assert plus_two.times_upgraded == 2
        assert plus_two.damage == 21

    def test_searing_blow_repeated_upgrade_accumulates_damage(self):
        card = CardInstance("SearingBlow")

        card.upgrade()
        assert card.times_upgraded == 1
        assert card.damage == 16

        card.upgrade()
        assert card.times_upgraded == 2
        assert card.damage == 21

        card.upgrade()
        assert card.times_upgraded == 3
        assert card.damage == 27

    def test_searing_blow_effect_mapping_remains_single_target_damage(self):
        effects = get_card_effects(CardInstance("SearingBlow"), target_idx=0)

        assert len(effects) == 1
        assert isinstance(effects[0], DealDamageEffect)

    def test_searing_blow_plus_n_deals_correct_damage_in_combat(self):
        combat = _make_combat(monster_hp=50, energy=2)
        _set_piles(combat, hand_cards=[CardInstance("SearingBlow+2")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 29


class TestIroncladSearingBlowRunUpgradeFlow:
    def test_smith_still_upgrades_normal_cards_once(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.phase = RunPhase.REST
        engine.state.deck = ["Bash"]

        assert engine.smith(0) is True
        assert engine.state.deck == ["Bash+"]

        engine.state.phase = RunPhase.REST
        assert engine.smith(0) is True
        assert engine.state.deck == ["Bash+"]

    def test_smith_repeatedly_upgrades_searing_blow(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.deck = ["SearingBlow"]

        engine.state.phase = RunPhase.REST
        assert engine.smith(0) is True
        assert engine.state.deck == ["SearingBlow+1"]

        engine.state.phase = RunPhase.REST
        assert engine.smith(0) is True
        assert engine.state.deck == ["SearingBlow+2"]

        engine.state.phase = RunPhase.REST
        assert engine.smith(0) is True
        assert engine.state.deck == ["SearingBlow+3"]

    def test_living_wall_upgrade_path_uses_same_searing_blow_upgrade_logic(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.phase = RunPhase.EVENT
        engine.state.deck = ["SearingBlow+2"]
        engine._current_event = ACT1_EVENTS["Living Wall"]

        choice_result = engine.choose_event_option(2)
        assert choice_result["success"] is True
        assert choice_result["action"] == "select_card"

        upgrade_result = engine.choose_event_option(0)
        assert upgrade_result["success"] is True
        assert upgrade_result["action"] == "card_upgraded"
        assert upgrade_result["old_card"] == "SearingBlow+2"
        assert upgrade_result["new_card"] == "SearingBlow+3"
        assert engine.state.deck == ["SearingBlow+3"]

    def test_shining_light_uses_same_searing_blow_upgrade_logic(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        engine.state.phase = RunPhase.EVENT
        engine.state.deck = ["SearingBlow+2"]
        engine._current_event = ACT1_EVENTS["Shining Light"]

        result = engine.choose_event_option(0)

        assert result["success"] is True
        assert result["action"] == "upgraded"
        assert result["upgraded_cards"] == ["SearingBlow+2"]
        assert engine.state.deck == ["SearingBlow+3"]

    def test_deck_entry_round_trips_to_runtime_card_instance(self):
        card = CardInstance("SearingBlow+4")

        assert card.card_id == "SearingBlow"
        assert card.times_upgraded == 4
        assert card.damage == 34


class TestIroncladSearingBlowHarnessNormalization:
    def test_normalize_deck_card_supports_multi_upgrade_searing_blow(self):
        assert harness._normalize_deck_card("SearingBlow") == "SearingBlow|0"
        assert harness._normalize_deck_card("SearingBlow+2") == "SearingBlow|2"
        assert harness._normalize_deck_card(CardInstance("SearingBlow+3")) == "SearingBlow|3"

    def test_deck_card_to_runtime_card_supports_multi_upgrade_searing_blow(self):
        assert harness._deck_card_to_runtime_card("SearingBlow|0") == "SearingBlow"
        assert harness._deck_card_to_runtime_card("SearingBlow|2") == "SearingBlow+2"

    def test_runtime_card_to_base_id_supports_multi_upgrade_searing_blow(self):
        assert harness._runtime_card_to_base_id("SearingBlow+4") == "SearingBlow"

    def test_remove_matching_normalized_card_handles_multi_upgrade_searing_blow(self):
        cards = ["Strike|-", "SearingBlow|3", "Bash|+"]

        removed = harness._remove_matching_normalized_card(cards, "SearingBlow")

        assert removed is True
        assert cards == ["Strike|-", "Bash|+"]
