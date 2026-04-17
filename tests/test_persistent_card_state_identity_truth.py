from __future__ import annotations

from types import SimpleNamespace

import sts_py.tools.ground_truth_harness as harness
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.run.events import _event_card_base_id
from sts_py.engine.run.run_engine import _deck_card_base_id


SEED_LONG = 4452322743548530140


class DummyMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 40):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=0, name="Attack"))


def _make_combat(*, energy: int = 3) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    combat = CombatEngine.create_with_monsters(
        monsters=[DummyMonster("Dummy")],
        player_hp=75,
        player_max_hp=75,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Defend_B"],
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
    cm.limbo_pile.cards = []


def test_genetic_algorithm_runtime_notation_uses_misc_as_persistent_block_seed() -> None:
    base = CardInstance("GeneticAlgorithm")
    grown = CardInstance("GeneticAlgorithm#7+")

    assert base.card_id == "GeneticAlgorithm"
    assert base.misc == 1
    assert base.base_block == 1
    assert base.runtime_card_id == "GeneticAlgorithm"

    assert grown.card_id == "GeneticAlgorithm"
    assert grown.upgraded is True
    assert grown.magic_number == 3
    assert grown.misc == 7
    assert grown.base_block == 7
    assert grown.runtime_card_id == "GeneticAlgorithm#7+"


def test_stateful_card_helpers_and_harness_round_trip_genetic_algorithm_ritual_dagger_and_searing_blow() -> None:
    assert harness._normalize_deck_card("GeneticAlgorithm") == "GeneticAlgorithm|1|-"
    assert harness._normalize_deck_card("GeneticAlgorithm#7+") == "GeneticAlgorithm|7|+"
    assert harness._deck_card_to_runtime_card("GeneticAlgorithm|1|-") == "GeneticAlgorithm"
    assert harness._deck_card_to_runtime_card("GeneticAlgorithm|7|+") == "GeneticAlgorithm#7+"
    assert harness._runtime_card_to_base_id("GeneticAlgorithm#7+") == "GeneticAlgorithm"
    assert _deck_card_base_id("GeneticAlgorithm#7+") == "GeneticAlgorithm"
    assert _event_card_base_id("GeneticAlgorithm#7+") == "GeneticAlgorithm"

    assert harness._normalize_deck_card("RitualDagger#18+") == "RitualDagger|18|+"
    assert harness._deck_card_to_runtime_card("RitualDagger|18|+") == "RitualDagger#18+"
    assert harness._runtime_card_to_base_id("RitualDagger#18+") == "RitualDagger"

    assert harness._normalize_deck_card("SearingBlow+4") == "SearingBlow|4"
    assert harness._deck_card_to_runtime_card("SearingBlow|4") == "SearingBlow+4"
    assert harness._runtime_card_to_base_id("SearingBlow+4") == "SearingBlow"


def test_genetic_algorithm_growth_updates_only_the_played_master_deck_slot() -> None:
    combat = _make_combat(energy=1)
    combat.state.run_engine = SimpleNamespace(state=SimpleNamespace(deck=["GeneticAlgorithm#7", "GeneticAlgorithm#10"]))

    first = CardInstance("GeneticAlgorithm#7")
    second = CardInstance("GeneticAlgorithm#10")
    setattr(first, "_master_deck_index", 0)
    setattr(second, "_master_deck_index", 1)
    _set_piles(combat, hand_cards=[first], draw_cards=[second])

    assert combat.play_card(0)

    exhausted = combat.state.card_manager.exhaust_pile.cards[-1]
    assert combat.state.player.block == 7
    assert exhausted.card_id == "GeneticAlgorithm"
    assert exhausted.misc == 9
    assert exhausted.base_block == 9
    assert combat.state.run_engine.state.deck == ["GeneticAlgorithm#9", "GeneticAlgorithm#10"]


def test_genetic_algorithm_same_instance_replay_keeps_misc_growth_and_master_deck_identity() -> None:
    combat = _make_combat(energy=1)
    combat.state.run_engine = SimpleNamespace(state=SimpleNamespace(deck=["GeneticAlgorithm#7"]))

    genetic_algorithm = CardInstance("GeneticAlgorithm#7")
    setattr(genetic_algorithm, "_master_deck_index", 0)
    genetic_algorithm._combat_state = combat.state

    assert combat._repeat_same_instance_card(genetic_algorithm) is True
    assert combat.state.player.block == 7
    assert genetic_algorithm.misc == 9
    assert genetic_algorithm.base_block == 9
    assert combat.state.run_engine.state.deck == ["GeneticAlgorithm#9"]
