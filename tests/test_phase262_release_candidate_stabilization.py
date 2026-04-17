from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.tools.compare_logs import JavaGameLog
from sts_py.tools.ground_truth_harness import replay_java_floor_fixture
from tests.log_helpers import require_optional_corpus_log


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str = "Dummy", *, hp: int = 50, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, deck: list[str], energy: int = 4, monster_hps: list[int] | None = None) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    combat = CombatEngine.create_with_monsters(
        monsters=[DummyAttackMonster(f"Dummy{index}", hp=hp) for index, hp in enumerate(monster_hps or [50])],
        player_hp=75,
        player_max_hp=75,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=deck,
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
    discard_cards: list[CardInstance] | None = None,
) -> None:
    card_manager = combat.state.card_manager
    card_manager.hand.cards = _bind_cards(combat, hand_cards or [])
    card_manager.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    card_manager.discard_pile.cards = _bind_cards(combat, discard_cards or [])
    card_manager.exhaust_pile.cards = []
    card_manager.limbo_pile.cards = []


def test_nightmare_generated_stateful_copy_does_not_write_back_to_master_deck() -> None:
    combat = _make_combat(deck=["GeneticAlgorithm#7+"], energy=3)
    combat.state.run_engine = SimpleNamespace(state=SimpleNamespace(deck=["GeneticAlgorithm#7+"]))
    combat.state.card_manager.hand.cards = []
    combat.state.card_manager.draw_pile.cards = []
    combat.state.card_manager.discard_pile.cards = []
    combat.state.card_manager.exhaust_pile.cards = []

    combat.state.player.add_power(create_power("Nightmare", 1, "player"))
    nightmare_power = next(power for power in combat.state.player.powers.powers if power.id == "Nightmare")
    nightmare_power.stored_card = CardInstance("GeneticAlgorithm#7+").make_stat_equivalent_copy()
    nightmare_power.stored_card._combat_state = combat.state

    results = combat.state.player.powers.at_start_of_turn(combat.state.player)
    generated = combat.state.card_manager.hand.cards[0]

    assert results == [{"type": "nightmare_generate", "count": 1}]
    assert generated.runtime_card_id == "GeneticAlgorithm#7+"
    assert generated.allow_master_deck_fallback_sync is False

    assert combat.play_card(0)

    assert combat.state.run_engine.state.deck == ["GeneticAlgorithm#7+"]
    assert [card.runtime_card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["GeneticAlgorithm#10+"]


def test_havoc_autoplay_still_updates_deck_bound_stateful_card_identity() -> None:
    combat = _make_combat(deck=["Havoc", "GeneticAlgorithm#7+"], energy=1)
    combat.state.run_engine = SimpleNamespace(state=SimpleNamespace(deck=["Havoc", "GeneticAlgorithm#7+"]))

    havoc = CardInstance("Havoc")
    genetic_algorithm = CardInstance("GeneticAlgorithm#7+")
    setattr(genetic_algorithm, "_master_deck_index", 1)
    _set_piles(combat, hand_cards=[havoc], draw_cards=[genetic_algorithm])

    assert combat.play_card(0)

    assert combat.state.run_engine.state.deck == ["Havoc", "GeneticAlgorithm#10+"]
    assert [card.runtime_card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["GeneticAlgorithm#10+"]
    assert combat.state.pending_combat_choice is None


def test_stateful_runtime_ids_are_shown_in_end_turn_and_omniscience_choices() -> None:
    retain = _make_combat(deck=["WellLaidPlans", "GeneticAlgorithm#7+", "RitualDagger#18+", "Strike", "Dazed"], energy=1)
    _set_piles(
        retain,
        hand_cards=[
            CardInstance("WellLaidPlans"),
            CardInstance("GeneticAlgorithm#7+"),
            CardInstance("RitualDagger#18+"),
            CardInstance("Strike"),
            CardInstance("Dazed"),
        ],
        draw_cards=[],
    )

    assert retain.play_card(0)
    retain.end_player_turn()

    retain_labels = [choice["label"] for choice in retain.get_pending_choices() if "card_id" in choice]
    assert retain_labels == ["GeneticAlgorithm#7+", "RitualDagger#18+", "Strike"]

    omniscience = _make_combat(deck=["Omniscience", "SearingBlow+4", "GeneticAlgorithm#7+"], energy=4)
    _set_piles(
        omniscience,
        hand_cards=[CardInstance("Omniscience")],
        draw_cards=[CardInstance("SearingBlow+4"), CardInstance("GeneticAlgorithm#7+")],
    )

    assert omniscience.play_card(0)
    omni_labels = [choice["label"] for choice in omniscience.get_pending_choices()]
    assert omni_labels == ["SearingBlow+4", "GeneticAlgorithm#7+"]


def test_replay_java_floor_fixture_is_stable_after_prior_fixture_mutation() -> None:
    java_log = JavaGameLog.from_file(require_optional_corpus_log("primary"))
    baseline = replay_java_floor_fixture(java_log, 39)
    expected_lane_turn = deepcopy(baseline["debug"]["battle_same_id_jawworm_intent_lane_by_turn"][1])
    expected_collapse = deepcopy(baseline["debug"]["battle_jawworm_lane_collapse_by_turn"][1])

    baseline["debug"]["battle_same_id_jawworm_intent_lane_by_turn"][1][0]["monster_idx"] = 99
    baseline["debug"]["battle_jawworm_lane_collapse_by_turn"][1].pop()

    _ = replay_java_floor_fixture(java_log, 38)
    replay = replay_java_floor_fixture(java_log, 39)

    assert replay["debug"]["battle_same_id_jawworm_intent_lane_by_turn"][1] == expected_lane_turn
    assert replay["debug"]["battle_jawworm_lane_collapse_by_turn"][1] == expected_collapse
