"""Smoke tests for ground_truth_harness.

Validates that the harness can:
1. Parse the real Java log into floor checkpoints
2. Compare Java checkpoints against themselves (self-parity)
3. Detect mismatches when Python data diverges
4. Handle missing Python floors gracefully
"""
from __future__ import annotations

from collections import Counter
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import sts_py.tools.ground_truth_harness as harness
from sts_py.engine.combat.card_effects import (
    BattleTranceEffect,
    BurningPactEffect,
    DrawCardsEffect,
    get_card_effects,
    SeverSoulEffect,
    UpgradeHandCardEffect,
)
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.relics import get_relic_by_id
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.bosses import BronzeOrb, Champ, Collector, Deca, Donu, Hexaghost, SlimeBoss, TorchHead
from sts_py.engine.monsters.city_beyond import (
    BookOfStabbing,
    Centurion,
    Chosen,
    Darkling,
    Dagger,
    Exploder,
    GenericMonsterProxy,
    GremlinLeader,
    Healer,
    Maw,
    Nemesis,
    OrbWalker,
    Reptomancer,
    Repulsor,
    Serpent,
    SnakePlant,
    Snecko,
    Spiker,
    SphericGuardian,
    Transient,
    WrithingMass,
)
from sts_py.engine.monsters.exordium import (
    AcidSlimeLarge,
    AcidSlimeMedium,
    FungiBeast,
    GremlinNob,
    GremlinTsundere,
    Looter,
    Mugger,
    SlaverRed,
    SlaverBlue,
    SpikeSlimeLarge,
)
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterMove
from sts_py.engine.run.run_engine import RunEngine, _create_replay_monster
from sts_py.tools.compare_logs import EventChoiceLog, JavaGameLog
from sts_py.tools.ground_truth_harness import (
    FloorCheckpoint,
    RunStateDiff,
    _apply_phase231_live_log_deck_removal_slots,
    _apply_phase231_live_log_smith_upgrade,
    _apply_phase231_live_log_transmogrifier_transform,
    _maybe_apply_java_all_monsters_dead_player_phase_terminal_closure,
    build_java_floor_checkpoints,
    build_java_run_state_summary,
    build_python_floor_checkpoints,
    build_python_run_state_summary,
    compare_floor_checkpoints,
    compare_run_state_summaries,
    replay_java_log,
    replay_java_floor_fixture,
    run_harness,
)
from tests.log_helpers import require_optional_recent_live_log


LATEST_IRONCLAD_LIVE_LOG = "run_Z6TK28WMDYCE_1776168047906.json"
LATEST_IRONCLAD_SHOP_LIVE_LOG = "run_1NAXPJBANK0G2_1776229559372.json"
LATEST_IRONCLAD_SHOP_FULL_SURFACE_LIVE_LOG = "run_1NAXPJBANK0G2_1776233200000.json"
LATEST_IRONCLAD_EARLY_BATTLE_DEATH_LIVE_LOG = "run_1NAXPJBANK0G2_1776229559372.json"
LATEST_IRONCLAD_EARLY_BATTLE_VICTORY_LIVE_LOG = "run_58JCYX0E41APV_1776228717319.json"


def _require_latest_ironclad_live_log() -> Path:
    return require_optional_recent_live_log(
        LATEST_IRONCLAD_LIVE_LOG,
        human_label="latest ironclad live log",
    )


def _require_latest_ironclad_shop_live_log() -> Path:
    return require_optional_recent_live_log(
        LATEST_IRONCLAD_SHOP_LIVE_LOG,
        human_label="latest ironclad shop live log",
    )


def _require_latest_ironclad_shop_full_surface_live_log() -> Path:
    return require_optional_recent_live_log(
        LATEST_IRONCLAD_SHOP_FULL_SURFACE_LIVE_LOG,
        human_label="latest ironclad full-surface shop live log",
    )


def _require_latest_ironclad_1nax_live_log(*, lane: str) -> Path:
    return require_optional_recent_live_log(
        LATEST_IRONCLAD_EARLY_BATTLE_DEATH_LIVE_LOG,
        human_label=f"latest ironclad 1NAX {lane} live log",
    )


def _require_latest_ironclad_58jc_live_log(*, lane: str) -> Path:
    return require_optional_recent_live_log(
        LATEST_IRONCLAD_EARLY_BATTLE_VICTORY_LIVE_LOG,
        human_label=f"latest ironclad 58JC {lane} live log",
    )


def _minimal_java_log(**overrides):
    base = {
        "seed_string": "TESTSEED",
        "character": "IRONCLAD",
        "initial_deck": [SimpleNamespace(card_id="Strike", upgraded=False) for _ in range(10)],
        "initial_relics": ["Burning Blood"],
        "final_deck": [SimpleNamespace(card_id="Strike", upgraded=False) for _ in range(10)],
        "final_relics": ["Burning Blood"],
        "end_floor": 1,
        "run_result": "unknown",
        "path_taken": [],
        "battles": [],
        "card_rewards": [],
        "boss_relic_choices": [],
        "treasure_rooms": [],
        "event_choices": [],
        "event_summaries": [],
        "rest_actions": [],
        "hp_changes": [],
        "gold_changes": [],
        "card_obtains": [],
        "card_removals": [],
        "card_transforms": [],
        "relic_changes": [],
        "shop_visits": [],
        "shop_purchases": [],
        "shop_purges": [],
        "potion_obtains": [],
        "potion_uses": [],
        "card_draws": [],
        "monster_intents": [],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _make_test_combat(deck: list[str] | None = None) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(123456789, counter=0)
    hp_rng = MutableRNG.from_seed(987654321, counter=0)
    combat = CombatEngine.create(
        encounter_name="Jaw Worm",
        player_hp=80,
        player_max_hp=80,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=deck or ["Strike", "Defend", "Bash", "Armaments", "BurningPact"],
    )
    cm = combat.state.card_manager
    assert cm is not None
    cm.hand.cards = []
    cm.draw_pile.cards = []
    cm.discard_pile.cards = []
    cm.exhaust_pile.cards = []
    cm._cards_drawn_this_turn = 0
    return combat


def _assert_only_non_material_unmatched_cards(debug: dict) -> None:
    unmatched = debug.get("battle_unmatched_cards")
    if unmatched is None:
        return
    assert isinstance(unmatched, list)
    assert all(isinstance(entry, dict) for entry in unmatched)
    assert all("card_id" in entry and "reason" in entry for entry in unmatched)


def _assert_continuity_turn_or_any(debug: dict, key: str, turn: int) -> None:
    continuity = debug.get(key) or {}
    assert isinstance(continuity, dict)
    if turn in continuity:
        assert continuity[turn]
        return
    assert continuity == {} or any(entries for entries in continuity.values())


class TestDiffSummary:

    def test_collects_multiple_mismatches_in_stable_order(self) -> None:
        java_floors = [
            FloorCheckpoint(
                floor=1,
                path={"x": 0, "y": 0, "room_type": "MonsterRoom"},
                reward={"picked": "Shockwave", "upgraded": False, "skipped": False},
            ),
            FloorCheckpoint(
                floor=2,
                battle={
                    "room_type": "MonsterRoom",
                    "monster_ids": ["JawWorm"],
                    "turns": 3,
                    "player_end_hp": 75,
                    "monster_end_hp": [0],
                    "rng": None,
                },
            ),
        ]
        python_floors = [
            {
                "floor": 1,
                "path": {"x": 2, "y": 0, "room_type": "M"},
                "reward": {"picked": "Flame Barrier", "upgraded": False, "skipped": False},
            },
            {
                "floor": 2,
                "battle": {
                    "room_type": "MonsterRoom",
                    "monster_ids": ["JawWorm"],
                    "turns": 4,
                    "player_end_hp": 75,
                    "monster_end_hp": [0],
                    "rng": None,
                },
            },
        ]

        diff = compare_floor_checkpoints(java_floors, python_floors)

        assert not diff.ok
        assert diff.first_mismatch == diff.mismatches[0]
        assert [
            (m["floor"], m["category"], m["field"]) for m in diff.mismatches
        ] == [
            (1, "path", "x"),
            (1, "reward", "picked"),
            (2, "battle", "turns"),
        ]
        assert diff.mismatch_summary == [
            "F1 path.x",
            "F1 reward.picked",
            "F2 battle.turns",
        ]

    def test_missing_python_category_reports_missing(self) -> None:
        java_floors = [
            FloorCheckpoint(
                floor=1,
                reward={"picked": "Shockwave", "upgraded": False, "skipped": False},
            )
        ]

        diff = compare_floor_checkpoints(java_floors, [{"floor": 1}])

        assert not diff.ok
        assert diff.first_mismatch["category"] == "reward"
        assert diff.first_mismatch["field"] == "missing"
        assert diff.first_mismatch["python"] is None

    def test_detects_state_mismatch(self) -> None:
        java_floors = [
            FloorCheckpoint(
                floor=19,
                state={"hp": 70, "max_hp": 88, "gold": 177, "deck_count": 18, "relic_count": 5},
            )
        ]
        python_floors = [
            {
                "floor": 19,
                "state": {"hp": 70, "max_hp": 88, "gold": 277, "deck_count": 18, "relic_count": 5},
            }
        ]

        diff = compare_floor_checkpoints(java_floors, python_floors)

        assert not diff.ok
        assert diff.first_mismatch == {
            "floor": 19,
            "category": "state",
            "field": "gold",
            "java": 177,
            "python": 277,
        }
        assert "F19 state.gold" in diff.mismatch_summary


class TestReplayOutcomeHelpers:

    def test_get_relic_by_id_accepts_normalized_runtime_ids(self) -> None:
        relic = get_relic_by_id("bustedcrown")

        assert relic is not None
        assert relic.id == "BustedCrown"

    def test_combat_engine_applies_start_with_energy_for_normalized_relic_ids(self) -> None:
        ai_rng = MutableRNG.from_seed(123, counter=0)
        hp_rng = MutableRNG.from_seed(456, counter=0)

        combat = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
            relics=["bustedcrown"],
        )

        assert combat.state.player.max_energy == 4
        assert combat.state.player.energy == 4
        assert combat.state.card_manager is not None
        assert combat.state.card_manager.max_energy == 4
        assert combat.state.card_manager.energy == 4

    def test_card_instance_canonicalizes_spaced_runtime_ids(self) -> None:
        card = CardInstance(card_id="Wild Strike", upgraded=True)

        assert card.card_id == "WildStrike"
        assert card.cost == 1
        assert card.cost_for_turn == 1
        assert card.damage == 17

    def test_find_attack_target_index_prefers_lowest_hp_alive_monster(self) -> None:
        monsters = [
            SimpleNamespace(id="Louse", hp=12, block=0, is_dead=lambda: False),
            SimpleNamespace(id="Louse", hp=4, block=0, is_dead=lambda: False),
            SimpleNamespace(id="Louse", hp=9, block=2, is_dead=lambda: False),
        ]
        engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(monsters=monsters),
                )
            )
        )

        assert harness._find_attack_target_index(engine) == 1

    def test_reconcile_live_victory_summary_applies_relic_heal(self) -> None:
        combat = SimpleNamespace(trigger_victory_effects=lambda: 6)
        engine = SimpleNamespace(
            state=SimpleNamespace(
                player_max_hp=80,
                combat=combat,
            )
        )
        replay_debug: dict[str, object] = {}
        summary = {
            "player_end_hp": 74,
            "monster_end_hp": [0],
            "turns": 2,
        }

        reconciled = harness._reconcile_live_victory_summary(engine, summary, replay_debug)

        assert reconciled is not None
        assert reconciled["player_end_hp"] == 80
        assert replay_debug["battle_live_victory_reconciled"] is True
        assert replay_debug["battle_live_victory_heal"] == 6
        assert replay_debug["battle_terminal_reason"] == "all_monsters_dead"

    def test_reconcile_live_victory_turns_from_outcomes_recovers_zero_turn_summary(self) -> None:
        replay_debug: dict[str, object] = {
            "python_monster_outcomes_by_turn": {
                0: {
                    "monsters": [
                        {"id": "FuzzyLouseDefensive", "hp": 12, "alive": True},
                        {"id": "FuzzyLouseNormal", "hp": 0, "alive": False},
                    ]
                },
                1: {
                    "monsters": [
                        {"id": "FuzzyLouseDefensive", "hp": 0, "alive": False},
                        {"id": "FuzzyLouseNormal", "hp": 0, "alive": False},
                    ]
                },
            }
        }
        summary = {
            "player_end_hp": 28,
            "monster_end_hp": [0, 0],
            "turns": 0,
        }

        reconciled = harness._reconcile_live_victory_turns_from_outcomes(summary, replay_debug)

        assert reconciled is not None
        assert reconciled["turns"] == 1
        assert replay_debug["battle_live_victory_turn_reconciled"] is True
        assert replay_debug["battle_live_victory_terminal_turn"] == 1

    def test_resolved_attack_damage_total_caps_block_loss_to_expected_attack(self) -> None:
        assert harness._resolved_attack_damage_total(
            expected_attack_damage_total=12,
            player_hp_before=79,
            player_hp_after=72,
            player_block_before=5,
            player_block_after=0,
        ) == 12

    def test_resolved_attack_damage_total_does_not_count_natural_block_clear(self) -> None:
        assert harness._resolved_attack_damage_total(
            expected_attack_damage_total=6,
            player_hp_before=64,
            player_hp_after=64,
            player_block_before=12,
            player_block_after=0,
        ) == 6

    def test_find_attack_target_index_for_two_same_id_attackers_prefers_high_damage_match(self) -> None:
        class _FakeMonster:
            def __init__(self, hp: int, bite_damage: int, intent_damage: int) -> None:
                self.id = "FuzzyLouseDefensive"
                self.hp = hp
                self.block = 0
                self.bite_damage = bite_damage
                self.next_move = SimpleNamespace(base_damage=intent_damage)

            def is_dead(self) -> bool:
                return self.hp <= 0

        engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(
                        monsters=[
                            _FakeMonster(hp=15, bite_damage=7, intent_damage=7),
                            _FakeMonster(hp=9, bite_damage=5, intent_damage=5),
                        ]
                    )
                )
            )
        )

        target_idx = harness._find_attack_target_index_for_two_same_id_attackers(
            engine,
            [
                {"monster_id": "FuzzyLouseDefensive", "intent": "ATTACK", "base_damage": 7},
                {"monster_id": "FuzzyLouseDefensive", "intent": "ATTACK", "base_damage": 5},
            ],
            logged_card=SimpleNamespace(
                card_id="Strike",
                is_attack=lambda: True,
            ),
        )

        assert target_idx == 0

    def test_find_attack_target_index_for_two_same_id_attackers_skips_multi_target_attacks(self) -> None:
        engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(
                        monsters=[
                            SimpleNamespace(id="FuzzyLouseDefensive", hp=15, block=0, next_move=SimpleNamespace(base_damage=7), is_dead=lambda: False),
                            SimpleNamespace(id="FuzzyLouseDefensive", hp=9, block=0, next_move=SimpleNamespace(base_damage=5), is_dead=lambda: False),
                        ]
                    )
                )
            )
        )

        target_idx = harness._find_attack_target_index_for_two_same_id_attackers(
            engine,
            [
                {"monster_id": "FuzzyLouseDefensive", "intent": "ATTACK", "base_damage": 7},
                {"monster_id": "FuzzyLouseDefensive", "intent": "ATTACK", "base_damage": 5},
            ],
            logged_card=SimpleNamespace(
                card_id="Immolate",
                is_attack=lambda: True,
            ),
        )

        assert target_idx is None

    def test_find_attack_target_index_for_unique_logged_intent_survivor_rebinds_exact_single_target_attack(self) -> None:
        engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(
                        monsters=[
                            SimpleNamespace(id="AcidSlime_S", hp=45, block=10, is_dead=lambda: False),
                            SimpleNamespace(id="SpikeSlime_M", hp=80, block=0, is_dead=lambda: False),
                        ]
                    )
                )
            )
        )

        target_idx = harness._find_attack_target_index_for_unique_logged_intent_survivor(
            engine,
            [{"monster_id": "SpikeSlime_M", "intent": "ATTACK_DEBUFF", "base_damage": 0}],
            java_turn=2,
            logged_card=SimpleNamespace(card_id="Pommel Strike", is_attack=lambda: True),
            unmatched_cards=[],
            turn_fallback_count=0,
        )

        assert target_idx == 1

    def test_find_attack_target_index_for_unique_logged_intent_survivor_skips_when_logged_roster_still_has_both_ids(self) -> None:
        engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(
                        monsters=[
                            SimpleNamespace(id="AcidSlime_S", hp=45, block=10, is_dead=lambda: False),
                            SimpleNamespace(id="SpikeSlime_M", hp=80, block=0, is_dead=lambda: False),
                        ]
                    )
                )
            )
        )

        target_idx = harness._find_attack_target_index_for_unique_logged_intent_survivor(
            engine,
            [
                {"monster_id": "AcidSlime_S", "intent": "ATTACK", "base_damage": 3},
                {"monster_id": "SpikeSlime_M", "intent": "ATTACK_DEBUFF", "base_damage": 0},
            ],
            java_turn=2,
            logged_card=SimpleNamespace(card_id="Pommel Strike", is_attack=lambda: True),
            unmatched_cards=[],
            turn_fallback_count=0,
        )

        assert target_idx is None

    def test_find_attack_target_index_for_unique_logged_intent_survivor_skips_non_exact_lane_inputs(self) -> None:
        engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(
                        monsters=[
                            SimpleNamespace(id="AcidSlime_S", hp=45, block=10, is_dead=lambda: False),
                            SimpleNamespace(id="SpikeSlime_M", hp=80, block=0, is_dead=lambda: False),
                        ]
                    )
                )
            )
        )

        multi_target_idx = harness._find_attack_target_index_for_unique_logged_intent_survivor(
            engine,
            [{"monster_id": "SpikeSlime_M", "intent": "ATTACK_DEBUFF", "base_damage": 0}],
            java_turn=2,
            logged_card=SimpleNamespace(card_id="Immolate", is_attack=lambda: True),
            unmatched_cards=[],
            turn_fallback_count=0,
        )
        unmatched_idx = harness._find_attack_target_index_for_unique_logged_intent_survivor(
            engine,
            [{"monster_id": "SpikeSlime_M", "intent": "ATTACK_DEBUFF", "base_damage": 0}],
            java_turn=2,
            logged_card=SimpleNamespace(card_id="Pommel Strike", is_attack=lambda: True),
            unmatched_cards=[{"turn": 2, "card_id": "Pommel Strike"}],
            turn_fallback_count=0,
        )

        assert multi_target_idx is None
        assert unmatched_idx is None

    def test_logged_intent_roster_closure_closes_unique_missing_monster_id(self) -> None:
        class _FakeMonster:
            def __init__(self, monster_id: str, hp: int) -> None:
                self.id = monster_id
                self.hp = hp
                self.block = 7
                self.is_dying = False
                self.next_move = SimpleNamespace(move_id=1, intent=MonsterIntent.ATTACK, base_damage=6)

            def is_dead(self) -> bool:
                return self.hp <= 0 or self.is_dying

        monsters = [_FakeMonster("AcidSlime_S", 40), _FakeMonster("SpikeSlime_M", 80)]
        engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(monsters=monsters),
                )
            )
        )
        replay_debug = {"battle_logged_intent_roster_closure_by_turn": {}}

        applied = harness._maybe_apply_logged_intent_roster_closure(
            engine,
            [{"monster_id": "SpikeSlime_M", "intent": "ATTACK_DEBUFF"}],
            replay_debug,
            java_turn=2,
            unmatched_cards=[],
            turn_fallback_count=0,
        )

        assert applied is True
        assert monsters[0].hp == 0
        assert monsters[0].block == 0
        assert monsters[0].is_dying is True
        assert replay_debug["battle_logged_intent_roster_closure_by_turn"][2] == [
            {
                "java_turn": 2,
                "mode": "unique_id_disappearance",
                "monster_id": "AcidSlime_S",
                "runtime_count": 1,
                "logged_count": 0,
                "closed_idx": 0,
            }
        ]

    def test_logged_intent_roster_closure_closes_lowest_hp_same_id_duplicate(self) -> None:
        class _FakeMonster:
            def __init__(self, hp: int, block: int = 0) -> None:
                self.id = "Repulsor"
                self.hp = hp
                self.block = block
                self.is_dying = False
                self.next_move = SimpleNamespace(move_id=1, intent=MonsterIntent.DEBUFF, base_damage=0)

            def is_dead(self) -> bool:
                return self.hp <= 0 or self.is_dying

        monsters = [
            SimpleNamespace(
                id="Spiker",
                hp=79,
                block=0,
                is_dying=False,
                next_move=SimpleNamespace(move_id=2, intent=MonsterIntent.BUFF, base_damage=0),
                is_dead=lambda: False,
            ),
            _FakeMonster(hp=141, block=20),
            _FakeMonster(hp=151, block=0),
        ]
        engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(monsters=monsters),
                )
            )
        )
        replay_debug = {"battle_logged_intent_roster_closure_by_turn": {}}

        applied = harness._maybe_apply_logged_intent_roster_closure(
            engine,
            [
                {"monster_id": "Spiker", "intent": "BUFF"},
                {"monster_id": "Repulsor", "intent": "DEBUFF"},
            ],
            replay_debug,
            java_turn=3,
            unmatched_cards=[],
            turn_fallback_count=0,
        )

        assert applied is True
        assert monsters[1].hp == 0
        assert monsters[1].block == 0
        assert monsters[1].is_dying is True

    def test_unique_id_survivor_terminal_closure_closes_last_distinct_survivor(self) -> None:
        class _FakeMonster:
            def __init__(self, monster_id: str, hp: int) -> None:
                self.id = monster_id
                self.hp = hp
                self.block = 6
                self.is_dying = False
                self.next_move = SimpleNamespace(move_id=1, intent=MonsterIntent.ATTACK, base_damage=6)

            def is_dead(self) -> bool:
                return self.hp <= 0 or self.is_dying

        monsters = [_FakeMonster("AcidSlime_S", 0), _FakeMonster("SpikeSlime_M", 74)]
        monsters[0].is_dying = True
        engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(monsters=monsters),
                )
            )
        )
        replay_debug = {
            "battle_logged_intent_roster_closure_by_turn": {
                2: [
                    {
                        "java_turn": 2,
                        "mode": "unique_id_disappearance",
                        "monster_id": "AcidSlime_S",
                        "runtime_count": 1,
                        "logged_count": 0,
                        "closed_idx": 0,
                    }
                ]
            },
            "battle_unique_id_target_rebind_by_turn": {
                2: [
                    {
                        "java_turn": 2,
                        "card_id": "Pommel Strike",
                        "from_monster_id": "AcidSlime_S",
                        "to_monster_id": "SpikeSlime_M",
                        "from_idx": 0,
                        "to_idx": 1,
                    }
                ]
            },
            "battle_unique_id_survivor_terminal_closure_by_turn": {},
        }
        battle = SimpleNamespace(monsters=[SimpleNamespace(ending_hp=0), SimpleNamespace(ending_hp=0)])
        python_cards_played_by_turn = {
            2: [
                {
                    "logged_card_id": "Pommel Strike",
                    "runtime_card_id": "PommelStrike",
                    "match_type": "exact",
                    "target_idx": 1,
                    "fallback": False,
                }
            ]
        }

        applied = harness._maybe_apply_unique_id_survivor_terminal_closure(
            engine,
            battle,
            replay_debug,
            java_turn=2,
            logged_intents=[{"monster_id": "SpikeSlime_M", "intent": "ATTACK_DEBUFF", "base_damage": 0}],
            unmatched_cards=[],
            turn_fallback_count=0,
            battle_player_attack_targets_by_turn={
                2: [
                    {
                        "logged_card_id": "Pommel Strike",
                        "runtime_card_id": "PommelStrike",
                        "target_idx": 1,
                        "target_monster_id": "SpikeSlime_M",
                    }
                ]
            },
            python_cards_played_by_turn=python_cards_played_by_turn,
        )

        assert applied is True
        assert monsters[1].hp == 0
        assert monsters[1].block == 0
        assert monsters[1].is_dying is True
        assert replay_debug["battle_unique_id_survivor_terminal_closure_by_turn"][2] == [
            {
                "java_turn": 2,
                "survivor_monster_id": "SpikeSlime_M",
                "survivor_idx": 1,
                "roster_closed_monster_id": "AcidSlime_S",
                "rebound_card_ids": ["Pommel Strike"],
            }
        ]

    def test_unique_id_survivor_terminal_closure_skips_guarded_non_target_cases(self) -> None:
        class _FakeMonster:
            def __init__(self, monster_id: str, hp: int) -> None:
                self.id = monster_id
                self.hp = hp
                self.block = 6
                self.is_dying = False
                self.next_move = SimpleNamespace(move_id=1, intent=MonsterIntent.ATTACK, base_damage=6)

            def is_dead(self) -> bool:
                return self.hp <= 0 or self.is_dying

        same_id_engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(
                        monsters=[_FakeMonster("FuzzyLouseDefensive", 0), _FakeMonster("FuzzyLouseDefensive", 5)]
                    )
                )
            )
        )
        same_id_engine.state.combat.state.monsters[0].is_dying = True
        replay_debug = {
            "battle_logged_intent_roster_closure_by_turn": {
                1: [{"java_turn": 1, "mode": "unique_id_disappearance", "monster_id": "FuzzyLouseDefensive"}]
            },
            "battle_unique_id_target_rebind_by_turn": {1: [{"java_turn": 1, "card_id": "Strike_R"}]},
            "battle_unique_id_survivor_terminal_closure_by_turn": {},
        }
        battle = SimpleNamespace(monsters=[SimpleNamespace(ending_hp=0), SimpleNamespace(ending_hp=0)])

        same_id_applied = harness._maybe_apply_unique_id_survivor_terminal_closure(
            same_id_engine,
            battle,
            replay_debug,
            java_turn=1,
            logged_intents=[{"monster_id": "FuzzyLouseDefensive", "intent": "ATTACK", "base_damage": 5}],
            unmatched_cards=[],
            turn_fallback_count=0,
            battle_player_attack_targets_by_turn={},
            python_cards_played_by_turn={
                1: [{"logged_card_id": "Strike_R", "runtime_card_id": "Strike", "match_type": "exact", "target_idx": 1, "fallback": False}]
            },
        )

        fallback_engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(
                        monsters=[_FakeMonster("AcidSlime_S", 0), _FakeMonster("SpikeSlime_M", 74)]
                    )
                )
            )
        )
        fallback_engine.state.combat.state.monsters[0].is_dying = True
        fallback_replay_debug = {
            "battle_logged_intent_roster_closure_by_turn": {
                2: [{"java_turn": 2, "mode": "unique_id_disappearance", "monster_id": "AcidSlime_S"}]
            },
            "battle_unique_id_target_rebind_by_turn": {2: [{"java_turn": 2, "card_id": "Pommel Strike"}]},
            "battle_unique_id_survivor_terminal_closure_by_turn": {},
        }
        fallback_applied = harness._maybe_apply_unique_id_survivor_terminal_closure(
            fallback_engine,
            battle,
            fallback_replay_debug,
            java_turn=2,
            logged_intents=[{"monster_id": "SpikeSlime_M", "intent": "ATTACK_DEBUFF", "base_damage": 0}],
            unmatched_cards=[],
            turn_fallback_count=1,
            battle_player_attack_targets_by_turn={},
            python_cards_played_by_turn={
                2: [{"logged_card_id": "Pommel Strike", "runtime_card_id": "PommelStrike", "match_type": "exact", "target_idx": 1, "fallback": False}]
            },
        )

        assert same_id_applied is False
        assert same_id_engine.state.combat.state.monsters[1].hp == 5
        assert fallback_applied is False
        assert fallback_engine.state.combat.state.monsters[1].hp == 74

    def test_same_id_triplet_fungi_terminal_closure_closes_last_low_hp_survivor(self) -> None:
        class _FakeMonster:
            def __init__(self, monster_id: str, hp: int) -> None:
                self.id = monster_id
                self.hp = hp
                self.block = 3
                self.is_dying = False
                self.next_move = SimpleNamespace(move_id=1, intent=MonsterIntent.ATTACK, base_damage=6)

            def is_dead(self) -> bool:
                return self.hp <= 0 or self.is_dying

        monsters = [_FakeMonster("FungiBeast", 0), _FakeMonster("FungiBeast", 5), _FakeMonster("FungiBeast", 0)]
        monsters[0].is_dying = True
        monsters[2].is_dying = True
        engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(monsters=monsters),
                )
            )
        )
        replay_debug = {"battle_same_id_triplet_fungi_terminal_closure_by_turn": {}}
        battle = SimpleNamespace(
            room_type="EventRoom",
            monsters=[
                SimpleNamespace(ending_hp=0),
                SimpleNamespace(ending_hp=0),
                SimpleNamespace(ending_hp=0),
            ],
        )

        applied = harness._maybe_apply_same_id_triplet_fungi_terminal_closure(
            engine,
            battle,
            replay_debug,
            java_turn=2,
            room_type="EventRoom",
            unmatched_cards=[],
            turn_fallback_count=0,
            python_cards_played_by_turn={
                2: [
                    {
                        "logged_card_id": "Wild Strike",
                        "runtime_card_id": "WildStrike",
                        "match_type": "temporary_upgrade_match",
                        "target_idx": 1,
                        "fallback": False,
                    },
                    {
                        "logged_card_id": "Pommel Strike",
                        "runtime_card_id": "PommelStrike",
                        "match_type": "exact",
                        "target_idx": 1,
                        "fallback": False,
                    },
                ]
            },
        )

        assert applied is True
        assert monsters[1].hp == 0
        assert monsters[1].block == 0
        assert monsters[1].is_dying is True
        assert replay_debug["battle_same_id_triplet_fungi_terminal_closure_by_turn"][2] == [
            {
                "java_turn": 2,
                "monster_id": "FungiBeast",
                "survivor_idx": 1,
                "survivor_hp_before_closure": 5,
            }
        ]

    def test_same_id_triplet_fungi_terminal_closure_skips_guarded_non_fungi_cases(self) -> None:
        class _FakeMonster:
            def __init__(self, monster_id: str, hp: int) -> None:
                self.id = monster_id
                self.hp = hp
                self.block = 3
                self.is_dying = False
                self.next_move = SimpleNamespace(move_id=1, intent=MonsterIntent.ATTACK, base_damage=6)

            def is_dead(self) -> bool:
                return self.hp <= 0 or self.is_dying

        fungi_engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(
                        monsters=[_FakeMonster("FungiBeast", 0), _FakeMonster("FungiBeast", 8), _FakeMonster("FungiBeast", 0)]
                    )
                )
            )
        )
        fungi_engine.state.combat.state.monsters[0].is_dying = True
        fungi_engine.state.combat.state.monsters[2].is_dying = True
        replay_debug = {"battle_same_id_triplet_fungi_terminal_closure_by_turn": {}}
        battle = SimpleNamespace(
            room_type="EventRoom",
            monsters=[
                SimpleNamespace(ending_hp=0),
                SimpleNamespace(ending_hp=0),
                SimpleNamespace(ending_hp=0),
            ],
        )

        high_hp_applied = harness._maybe_apply_same_id_triplet_fungi_terminal_closure(
            fungi_engine,
            battle,
            replay_debug,
            java_turn=2,
            room_type="EventRoom",
            unmatched_cards=[],
            turn_fallback_count=0,
            python_cards_played_by_turn={
                2: [
                    {
                        "logged_card_id": "Pommel Strike",
                        "runtime_card_id": "PommelStrike",
                        "match_type": "exact",
                        "target_idx": 1,
                        "fallback": False,
                    },
                ]
            },
        )

        repulsor_engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(
                        monsters=[_FakeMonster("Repulsor", 0), _FakeMonster("Repulsor", 5), _FakeMonster("Repulsor", 0)]
                    )
                )
            )
        )
        repulsor_engine.state.combat.state.monsters[0].is_dying = True
        repulsor_engine.state.combat.state.monsters[2].is_dying = True
        repulsor_applied = harness._maybe_apply_same_id_triplet_fungi_terminal_closure(
            repulsor_engine,
            battle,
            replay_debug,
            java_turn=2,
            room_type="EventRoom",
            unmatched_cards=[],
            turn_fallback_count=0,
            python_cards_played_by_turn={
                2: [
                    {
                        "logged_card_id": "Pommel Strike",
                        "runtime_card_id": "PommelStrike",
                        "match_type": "exact",
                        "target_idx": 1,
                        "fallback": False,
                    },
                ]
            },
        )

        fallback_applied = harness._maybe_apply_same_id_triplet_fungi_terminal_closure(
            fungi_engine,
            battle,
            replay_debug,
            java_turn=2,
            room_type="EventRoom",
            unmatched_cards=[],
            turn_fallback_count=1,
            python_cards_played_by_turn={
                2: [
                    {
                        "logged_card_id": "Pommel Strike",
                        "runtime_card_id": "PommelStrike",
                        "match_type": "exact",
                        "target_idx": 1,
                        "fallback": False,
                    },
                ]
            },
        )

        assert high_hp_applied is False
        assert repulsor_applied is False
        assert fallback_applied is False
        assert replay_debug["battle_same_id_triplet_fungi_terminal_closure_by_turn"] == {}

    def test_logged_intent_roster_closure_skips_turn_with_unmatched_cards(self) -> None:
        monsters = [
            SimpleNamespace(id="AcidSlime_S", hp=40, block=0, is_dying=False, next_move=None, is_dead=lambda: False),
            SimpleNamespace(id="SpikeSlime_M", hp=80, block=0, is_dying=False, next_move=None, is_dead=lambda: False),
        ]
        engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(monsters=monsters),
                )
            )
        )
        replay_debug = {"battle_logged_intent_roster_closure_by_turn": {}}

        applied = harness._maybe_apply_logged_intent_roster_closure(
            engine,
            [{"monster_id": "SpikeSlime_M", "intent": "ATTACK_DEBUFF"}],
            replay_debug,
            java_turn=2,
            unmatched_cards=[{"turn": 2, "reason": "no_match_in_hand"}],
            turn_fallback_count=0,
        )

        assert applied is False
        assert monsters[0].hp == 40
        assert replay_debug["battle_logged_intent_roster_closure_by_turn"] == {}

    def test_logged_intent_roster_closure_skips_turn_with_fallback_cards(self) -> None:
        monsters = [
            SimpleNamespace(id="AcidSlime_S", hp=40, block=0, is_dying=False, next_move=None, is_dead=lambda: False),
            SimpleNamespace(id="SpikeSlime_M", hp=80, block=0, is_dying=False, next_move=None, is_dead=lambda: False),
        ]
        engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(monsters=monsters),
                )
            )
        )
        replay_debug = {"battle_logged_intent_roster_closure_by_turn": {}}

        applied = harness._maybe_apply_logged_intent_roster_closure(
            engine,
            [{"monster_id": "SpikeSlime_M", "intent": "ATTACK_DEBUFF"}],
            replay_debug,
            java_turn=2,
            unmatched_cards=[],
            turn_fallback_count=1,
        )

        assert applied is False
        assert monsters[0].hp == 40
        assert replay_debug["battle_logged_intent_roster_closure_by_turn"] == {}

    def test_room_type_normalize_keeps_symbol_and_java_name_equivalent(self) -> None:
        java_floors = [
            FloorCheckpoint(
                floor=1,
                path={"x": 0, "y": 0, "room_type": "MonsterRoom"},
            )
        ]
        python_floors = [
            {"floor": 1, "path": {"x": 0, "y": 0, "room_type": "M"}}
        ]

        diff = compare_floor_checkpoints(java_floors, python_floors)

        assert diff.ok
        assert diff.mismatches == []

    def test_build_java_floor_checkpoints_normalizes_treasure_room_boss_path(self) -> None:
        java_log = SimpleNamespace(
            path_taken=[SimpleNamespace(floor=17, x=-1, y=15, room_type="TreasureRoomBoss")],
            battles=[],
            card_rewards=[],
            boss_relic_choices=[],
            treasure_rooms=[],
            event_choices=[],
            event_summaries=[],
            monster_intents=[],
            card_draws=[],
        )

        floors = build_java_floor_checkpoints(java_log)

        assert floors[0].path == {"x": -1, "y": 15, "room_type": "TreasureRoom"}
        assert floors[0].debug["raw_room_type"] == "TreasureRoomBoss"

    def test_build_java_floor_checkpoints_includes_boss_relic_choice_and_treasure(self) -> None:
        java_log = _minimal_java_log(
            path_taken=[SimpleNamespace(floor=17, x=-1, y=15, room_type="TreasureRoomBoss")],
            boss_relic_choices=[
                SimpleNamespace(
                    floor=17,
                    picked_relic_id="TinyHouse",
                    not_picked_relic_ids=["CallingBell", "PandoraBox"],
                    skipped=False,
                )
            ],
            treasure_rooms=[
                SimpleNamespace(
                    floor=17,
                    room_type="TreasureRoomBoss",
                    main_relic_id="TinyHouse",
                    relic_id="TinyHouse",
                    obtained_relic_ids=[],
                    skipped_main_relic_id=None,
                    took_sapphire_key=False,
                )
            ],
        )

        floors = build_java_floor_checkpoints(java_log)

        assert floors[0].boss_relic_choice == {
            "picked_relic_id": "TinyHouse",
            "not_picked_relic_ids": ["CallingBell", "PandoraBox"],
            "skipped": False,
        }
        assert floors[0].treasure == {
            "room_type": "TreasureRoom",
            "main_relic_id": "TinyHouse",
            "obtained_relic_ids": [],
            "skipped_main_relic_id": None,
            "took_sapphire_key": False,
        }

    def test_java_all_monsters_dead_player_phase_terminal_closure_closes_alive_survivors(self) -> None:
        engine = RunEngine.create("TESTZEROTURNCLOSURE", ascension=0)
        engine.start_combat_with_monsters(["Cultist"])
        monster = engine.state.combat.state.monsters[0]
        monster.hp = 12
        monster.is_dying = False

        applied = _maybe_apply_java_all_monsters_dead_player_phase_terminal_closure(
            engine,
            SimpleNamespace(turn_count=0, monsters=[SimpleNamespace(ending_hp=0)]),
            {},
            java_turn=0,
            unmatched_cards=[],
            turn_fallback_count=0,
            next_turn_logged_cards=[],
            python_cards_played_by_turn={0: [{"logged_card_id": "Bash", "fallback": False}]},
        )

        assert applied is True
        assert monster.hp == 0
        assert monster.is_dying is True

    def test_build_java_floor_checkpoints_merges_floor_0_neow_to_reward_choice(self) -> None:
        java_log = SimpleNamespace(
            path_taken=[],
            battles=[],
            card_rewards=[],
            event_choices=[
                EventChoiceLog(
                    event_id="NeowEvent",
                    event_name="Neow",
                    choice_index=0,
                    choice_text="Intro text",
                    floor=0,
                    timestamp=1,
                ),
                EventChoiceLog(
                    event_id="NeowEvent",
                    event_name="Neow",
                    choice_index=1,
                    choice_text="#g+8 Max HP",
                    floor=0,
                    timestamp=2,
                ),
            ],
            monster_intents=[],
            card_draws=[],
        )

        floors = build_java_floor_checkpoints(java_log)

        assert len(floors) == 1
        assert floors[0].floor == 0
        assert floors[0].event == {
            "event_id": "NeowEvent",
            "choice_index": 1,
            "choice_text": "#g+8 Max HP",
        }

    def test_build_java_floor_checkpoints_prefers_event_summaries_when_present(self) -> None:
        java_log = SimpleNamespace(
            path_taken=[],
            battles=[],
            card_rewards=[],
            event_choices=[
                EventChoiceLog(
                    event_id="BigFish",
                    event_name="Big Fish",
                    choice_index=0,
                    choice_text="Intro",
                    floor=5,
                    timestamp=1,
                ),
                EventChoiceLog(
                    event_id="BigFish",
                    event_name="Big Fish",
                    choice_index=1,
                    choice_text="[Leave]",
                    floor=5,
                    timestamp=2,
                ),
            ],
            event_summaries=[
                EventChoiceLog(
                    event_id="BigFish",
                    event_name="Big Fish",
                    choice_index=7,
                    choice_text="Semantic summary",
                    floor=5,
                    timestamp=3,
                )
            ],
            monster_intents=[],
            card_draws=[],
        )

        floors = build_java_floor_checkpoints(java_log)

        assert floors[0].event == {
            "event_id": "BigFish",
            "choice_index": 7,
            "choice_text": "Semantic summary",
        }
        assert floors[0].debug["event_sequence"][0]["choice_text"] == "Intro"

    def test_build_java_floor_checkpoints_adds_floor_state(self) -> None:
        java_log = _minimal_java_log(
            character="IRONCLAD",
            initial_deck=[SimpleNamespace(card_id="Strike", upgraded=False) for _ in range(10)],
            initial_relics=["Burning Blood"],
            final_deck=[SimpleNamespace(card_id="Strike", upgraded=False) for _ in range(10)] + [SimpleNamespace(card_id="Armaments", upgraded=False)],
            final_relics=["Burning Blood", "Dream Catcher"],
            path_taken=[SimpleNamespace(floor=1, x=0, y=0, room_type="MonsterRoom")],
            battles=[
                SimpleNamespace(
                    floor=1,
                    room_type="MonsterRoom",
                    monsters=[],
                    turn_count=3,
                    player_end_hp=82,
                    cards_played=[],
                    rng_state_end=None,
                )
            ],
            card_rewards=[],
            event_choices=[],
            event_summaries=[],
            rest_actions=[SimpleNamespace(action="SMITH", floor=1, hp_before=82, max_hp=88, timestamp=6)],
            monster_intents=[],
            card_draws=[],
            hp_changes=[SimpleNamespace(amount=6, source="heal", floor=1, hp_after=88, max_hp=88, timestamp=2)],
            gold_changes=[SimpleNamespace(amount=14, source="reward", floor=1, gold_after=113, timestamp=3)],
            card_obtains=[SimpleNamespace(card_id="Armaments", upgraded=False, source="reward", floor=1, timestamp=4)],
            card_removals=[],
            card_transforms=[],
            relic_changes=[SimpleNamespace(relic_id="Dream Catcher", relic_name="Dream Catcher", floor=1, turn=0, action="triggered:onEquip", source="elite", timestamp=5)],
            shop_purchases=[],
            shop_purges=[],
        )

        floors = build_java_floor_checkpoints(java_log)

        assert floors[0].state == {
            "hp": 88,
            "max_hp": 88,
            "gold": 113,
            "deck_count": 11,
            "relic_count": 2,
        }
        assert floors[0].debug["rest_actions"] == ["SMITH"]
        assert floors[0].debug["unresolved_upgrade_targets"] is True

    def test_build_java_floor_checkpoints_applies_goop_puddle_semantics(self) -> None:
        java_log = _minimal_java_log(
            end_floor=11,
            path_taken=[SimpleNamespace(floor=11, x=0, y=0, room_type="EventRoom")],
            event_choices=[
                EventChoiceLog(
                    event_id="GoopPuddle",
                    event_name="World of Goop",
                    choice_index=0,
                    choice_text="[收集金币] 75/11",
                    floor=11,
                    timestamp=1,
                ),
                EventChoiceLog(
                    event_id="GoopPuddle",
                    event_name="World of Goop",
                    choice_index=0,
                    choice_text="[离开]",
                    floor=11,
                    timestamp=2,
                ),
            ],
        )

        floors = build_java_floor_checkpoints(java_log)

        assert floors[0].state == {
            "hp": 69,
            "max_hp": 80,
            "gold": 174,
            "deck_count": 10,
            "relic_count": 1,
        }
        assert floors[0].debug["event_semantic_applied"] == ["GoopPuddle:gold_hp"]

    def test_build_java_floor_checkpoints_marks_bonfire_as_unresolved(self) -> None:
        java_log = _minimal_java_log(
            end_floor=4,
            path_taken=[SimpleNamespace(floor=4, x=0, y=0, room_type="EventRoom")],
            event_choices=[
                EventChoiceLog("Bonfire", "Bonfire", 0, "[继续]", 4, 1),
                EventChoiceLog("Bonfire", "Bonfire", 0, "[献上]", 4, 2),
                EventChoiceLog("Bonfire", "Bonfire", 0, "[离开]", 4, 3),
            ],
        )

        floors = build_java_floor_checkpoints(java_log)

        assert floors[0].debug["unresolved_event_semantics"] == ["Bonfire"]

    def test_build_java_floor_checkpoints_marks_upgrade_shrine_as_unresolved_upgrade(self) -> None:
        java_log = _minimal_java_log(
            end_floor=38,
            path_taken=[SimpleNamespace(floor=38, x=0, y=0, room_type="EventRoom")],
            event_choices=[
                EventChoiceLog("UpgradeShrine", "Upgrade Shrine", 0, "[祈祷]", 38, 1),
                EventChoiceLog("UpgradeShrine", "Upgrade Shrine", 0, "[离开]", 38, 2),
            ],
        )

        floors = build_java_floor_checkpoints(java_log)

        assert floors[0].debug["unresolved_upgrade_targets"] is True
        assert floors[0].debug["event_semantic_applied"] == ["UpgradeShrine:upgrade"]

    def test_phase231_live_log_purge_slots_infer_starter_removals(self) -> None:
        deck = [
            "Strike|-",
            "Strike|-",
            "Strike|-",
            "Strike|-",
            "Strike|-",
            "Defend|-",
            "Defend|-",
            "Defend|-",
            "Defend|-",
            "Bash|+",
            "Shrug It Off|-",
        ]
        final_deck = ["Strike|-", "Strike|-", "Strike|-", "Bash|+", "Shrug It Off|-"]
        state_debug: dict[str, object] = {}

        removed = _apply_phase231_live_log_deck_removal_slots(
            deck=deck,
            final_deck=final_deck,
            future_additions=Counter(),
            slots=4,
            floor=11,
            source="shop_purge",
            state_debug=state_debug,
        )

        assert removed == ["Defend|-", "Defend|-", "Defend|-", "Defend|-"]
        assert deck == ["Strike|-", "Strike|-", "Strike|-", "Strike|-", "Strike|-", "Bash|+", "Shrug It Off|-"]
        assert state_debug["state_phase231_live_log_purge_slots_applied"] == {
            "floor": 11,
            "source": "shop_purge",
            "slots": 4,
            "removed_cards": ["Defend|-", "Defend|-", "Defend|-", "Defend|-"],
        }

    def test_phase231_live_log_smith_upgrade_replaces_base_card(self) -> None:
        deck = ["Bash|-", "Strike|-"]
        final_deck = ["Bash|+", "Strike|-"]
        state_debug: dict[str, object] = {}

        upgraded = _apply_phase231_live_log_smith_upgrade(
            deck=deck,
            final_deck=final_deck,
            floor=8,
            state_debug=state_debug,
        )

        assert upgraded == "Bash|+"
        assert deck == ["Bash|+", "Strike|-"]
        assert state_debug["state_phase231_live_log_smith_upgrade_applied"] == {
            "floor": 8,
            "card_id": "Bash",
            "old_card": "Bash|-",
            "new_card": "Bash|+",
        }

    def test_phase231_live_log_transmogrifier_transform_replaces_strike_with_shrug(self) -> None:
        deck = ["Strike|-", "Bash|+"]
        final_deck = ["Shrug It Off|-", "Bash|+"]
        state_debug: dict[str, object] = {}

        transformed = _apply_phase231_live_log_transmogrifier_transform(
            deck=deck,
            final_deck=final_deck,
            floor=39,
            state_debug=state_debug,
        )

        assert transformed == ("Strike|-", "Shrug It Off|-")
        assert deck == ["Shrug It Off|-", "Bash|+"]
        assert state_debug["state_phase231_live_log_transform_applied"] == {
            "floor": 39,
            "old_card": "Strike|-",
            "new_card": "Shrug It Off|-",
        }

    def test_reward_normalize_treats_skip_as_non_card_pick(self) -> None:
        java_floors = [
            FloorCheckpoint(
                floor=1,
                reward={
                    "choice_type": "skip",
                    "picked": None,
                    "upgraded": False,
                    "skipped": True,
                },
            )
        ]
        python_floors = [
            {
                "floor": 1,
                "reward": {
                    "picked": "SKIP",
                    "upgraded": False,
                    "skipped": True,
                    "choice_type": "skip",
                },
            }
        ]

        diff = compare_floor_checkpoints(java_floors, python_floors)

        assert diff.ok
        assert diff.mismatches == []

    def test_report_format_includes_summary(self) -> None:
        java_floors = [
            FloorCheckpoint(
                floor=1,
                path={"x": 0, "y": 0, "room_type": "MonsterRoom"},
            )
        ]
        diff = compare_floor_checkpoints(
            java_floors,
            [{"floor": 1, "path": {"x": 9, "y": 0, "room_type": "M"}}],
        )
        report = harness.HarnessReport(
            java_floors=java_floors,
            python_floors=[{"floor": 1, "path": {"x": 9, "y": 0, "room_type": "M"}}],
            diff=diff,
        )

        text = report.format_text()
        assert "Floor Diff:" in text
        assert "Run State Diff:" in text
        assert "Total mismatches: 1" in text
        assert "Mismatch summary:" in text
        assert "F1 path.x" in text

    def test_run_harness_auto_replays_when_python_floor_file_is_missing(self, monkeypatch) -> None:
        fake_log = object()
        monkeypatch.setattr(harness.JavaGameLog, "from_file", staticmethod(lambda _: fake_log))
        monkeypatch.setattr(
            harness,
            "build_java_floor_checkpoints",
            lambda _: [FloorCheckpoint(floor=1, path={"x": 0, "y": 0, "room_type": "MonsterRoom"})],
        )
        monkeypatch.setattr(
            harness,
            "replay_java_log",
            lambda _: {
                "floors": [{"floor": 1, "path": {"x": 0, "y": 0, "room_type": "M"}}],
                "phase": "map",
                "act": 1,
                "floor": 1,
                "player_hp": 80,
                "player_max_hp": 80,
                "player_gold": 99,
                "deck": ["Strike"],
                "relics": ["BurningBlood"],
            },
        )
        monkeypatch.setattr(
            harness,
            "build_java_run_state_summary",
            lambda _: {
                "run_result": "unknown",
                "end_act": 1,
                "end_floor": 1,
                "end_hp": 80,
                "end_max_hp": 80,
                "end_gold": 99,
                "final_deck": ["Strike|-"],
                "final_relics": ["burningblood"],
            },
        )

        report = run_harness(Path("fake_java_log.json"))

        assert len(report.python_floors) == 1
        assert report.diff.ok
        assert report.run_state_diff is not None
        assert report.run_state_diff.ok
        assert report.diff.checked_floors == [1]

    def test_run_state_summary_derives_death_from_game_over_and_zero_hp(self) -> None:
        summary = build_python_run_state_summary(
            {
                "phase": "game_over",
                "act": 3,
                "floor": 50,
                "player_hp": 0,
                "player_max_hp": 98,
                "player_gold": 117,
                "deck": ["Strike", "Bash+"],
                "relics": ["Burning Blood"],
            }
        )

        assert summary["run_result"] == "death"
        assert summary["final_deck"] == ["Bash|+", "Strike|-"]
        assert summary["final_relics"] == ["burningblood"]

    def test_run_state_summary_uses_derived_terminal_death(self) -> None:
        summary = build_python_run_state_summary(
            {
                "derived_run_result": "death",
                "phase": "game_over",
                "act": 3,
                "floor": 50,
                "player_hp": 98,
                "player_max_hp": 98,
                "player_gold": 117,
                "deck": ["Strike"],
                "relics": ["Burning Blood"],
            }
        )

        assert summary["run_result"] == "death"

    def test_compare_run_state_detects_end_hp_mismatch(self) -> None:
        diff = compare_run_state_summaries(
            {"run_result": "death", "end_act": 3, "end_floor": 50, "end_hp": 0, "end_max_hp": 98, "end_gold": 117, "final_deck": [], "final_relics": []},
            {"run_result": "death", "end_act": 3, "end_floor": 50, "end_hp": 98, "end_max_hp": 98, "end_gold": 117, "final_deck": [], "final_relics": []},
        )

        assert not diff.ok
        assert diff.first_mismatch["field"] == "end_hp"

    def test_compare_run_state_detects_end_gold_mismatch(self) -> None:
        diff = compare_run_state_summaries(
            {"run_result": "death", "end_act": 3, "end_floor": 50, "end_hp": 0, "end_max_hp": 98, "end_gold": 117, "final_deck": [], "final_relics": []},
            {"run_result": "death", "end_act": 3, "end_floor": 50, "end_hp": 0, "end_max_hp": 98, "end_gold": None, "final_deck": [], "final_relics": []},
        )

        assert not diff.ok
        assert diff.first_mismatch["field"] == "end_gold"

    def test_compare_run_state_detects_final_deck_mismatch(self) -> None:
        diff = compare_run_state_summaries(
            {"run_result": "death", "end_act": 3, "end_floor": 50, "end_hp": 0, "end_max_hp": 98, "end_gold": 117, "final_deck": ["Bash|+", "Strike|-"], "final_relics": []},
            {"run_result": "death", "end_act": 3, "end_floor": 50, "end_hp": 0, "end_max_hp": 98, "end_gold": 117, "final_deck": ["Strike|-"], "final_relics": []},
        )

        assert not diff.ok
        assert diff.first_mismatch["field"] == "final_deck"
        assert "content_missing_in_python" in diff.first_mismatch["detail"]

    def test_compare_run_state_marks_upgrade_only_deck_mismatch(self) -> None:
        diff = compare_run_state_summaries(
            {"run_result": "death", "end_act": 3, "end_floor": 50, "end_hp": 0, "end_max_hp": 98, "end_gold": 117, "final_deck": ["Bash|+", "Strike|-"], "final_relics": []},
            {"run_result": "death", "end_act": 3, "end_floor": 50, "end_hp": 0, "end_max_hp": 98, "end_gold": 117, "final_deck": ["Bash|-", "Strike|-"], "final_relics": []},
        )

        assert not diff.ok
        assert diff.first_mismatch["field"] == "final_deck"
        assert "upgrade_only_mismatch=True" in diff.first_mismatch["detail"]

    def test_compare_run_state_detects_final_relics_mismatch(self) -> None:
        diff = compare_run_state_summaries(
            {"run_result": "death", "end_act": 3, "end_floor": 50, "end_hp": 0, "end_max_hp": 98, "end_gold": 117, "final_deck": [], "final_relics": ["burningblood", "kunai"]},
            {"run_result": "death", "end_act": 3, "end_floor": 50, "end_hp": 0, "end_max_hp": 98, "end_gold": 117, "final_deck": [], "final_relics": ["burningblood"]},
        )

        assert not diff.ok
        assert diff.first_mismatch["field"] == "final_relics"
        assert "missing_in_python" in diff.first_mismatch["detail"]

    def test_report_format_includes_run_state_diff(self) -> None:
        report = harness.HarnessReport(
            java_floors=[],
            python_floors=[],
            diff=harness.DiffResult(ok=True, checked_floors=[1]),
            java_run_state={"end_hp": 0},
            python_run_state={"end_hp": 98},
            run_state_diff=RunStateDiff(
                ok=False,
                checked_fields=["end_hp"],
                first_mismatch={"field": "end_hp", "java": 0, "python": 98},
                mismatches=[{"field": "end_hp", "java": 0, "python": 98}],
                mismatch_summary=["run_state.end_hp"],
            ),
        )

        text = report.format_text()
        assert "Run State Diff:" in text
        assert "run_state.end_hp" in text


class TestBuildJavaFloorCheckpoints:

    def test_returns_nonempty(self, real_java_log: JavaGameLog) -> None:
        floors = build_java_floor_checkpoints(real_java_log)
        assert len(floors) > 0

    def test_floors_are_sorted(self, real_java_log: JavaGameLog) -> None:
        floors = build_java_floor_checkpoints(real_java_log)
        floor_nums = [f.floor for f in floors]
        assert floor_nums == sorted(floor_nums)

    def test_floor_1_has_battle(self, real_java_log: JavaGameLog) -> None:
        floors = build_java_floor_checkpoints(real_java_log)
        floor_1 = next((f for f in floors if f.floor == 1), None)
        assert floor_1 is not None
        assert floor_1.battle is not None
        assert "player_end_hp" in floor_1.battle
        assert "turns" in floor_1.battle

    def test_floor_1_has_path(self, real_java_log: JavaGameLog) -> None:
        floors = build_java_floor_checkpoints(real_java_log)
        floor_1 = next((f for f in floors if f.floor == 1), None)
        assert floor_1 is not None
        assert floor_1.path is not None
        assert "x" in floor_1.path
        assert "y" in floor_1.path
        assert "room_type" in floor_1.path

    def test_floor_1_has_reward(self, real_java_log: JavaGameLog) -> None:
        floors = build_java_floor_checkpoints(real_java_log)
        floor_1 = next((f for f in floors if f.floor == 1), None)
        assert floor_1 is not None
        assert floor_1.reward is not None
        assert "picked" in floor_1.reward

    def test_floor_1_battle_rng_snapshot(self, real_java_log: JavaGameLog) -> None:
        floors = build_java_floor_checkpoints(real_java_log)
        floor_1 = next((f for f in floors if f.floor == 1), None)
        assert floor_1 is not None
        rng = floor_1.battle["rng"]
        assert rng is not None
        assert "ai_rng_counter" in rng
        assert "shuffle_rng_counter" in rng

    def test_floor_1_monster_ids(self, real_java_log: JavaGameLog) -> None:
        floors = build_java_floor_checkpoints(real_java_log)
        floor_1 = next((f for f in floors if f.floor == 1), None)
        assert floor_1 is not None
        assert "monster_ids" in floor_1.battle
        assert len(floor_1.battle["monster_ids"]) > 0


class TestSelfParity:
    """Java checkpoints compared against themselves should always pass."""

    def test_self_parity_ok(self, real_java_log: JavaGameLog) -> None:
        java_floors = build_java_floor_checkpoints(real_java_log)
        python_floors = [f.to_dict() for f in java_floors]
        diff = compare_floor_checkpoints(java_floors, python_floors)
        assert diff.ok, f"Self-parity failed: {diff.first_mismatch}"

    def test_self_parity_checked_all_floors(self, real_java_log: JavaGameLog) -> None:
        java_floors = build_java_floor_checkpoints(real_java_log)
        python_floors = [f.to_dict() for f in java_floors]
        diff = compare_floor_checkpoints(java_floors, python_floors)
        assert len(diff.checked_floors) == len(java_floors)


class TestMismatchDetection:

    def test_detects_hp_mismatch(self, real_java_log: JavaGameLog) -> None:
        java_floors = build_java_floor_checkpoints(real_java_log)
        python_floors = [f.to_dict() for f in java_floors]

        # Corrupt floor 1 battle hp
        for pf in python_floors:
            if pf["floor"] == 1 and pf.get("battle"):
                pf["battle"]["player_end_hp"] = 999
                break

        diff = compare_floor_checkpoints(java_floors, python_floors)
        assert not diff.ok
        assert diff.first_mismatch is not None
        assert diff.first_mismatch["floor"] == 1
        assert diff.first_mismatch["category"] == "battle"
        assert diff.first_mismatch["field"] == "player_end_hp"

    def test_detects_reward_mismatch(self, real_java_log: JavaGameLog) -> None:
        java_floors = build_java_floor_checkpoints(real_java_log)
        python_floors = [f.to_dict() for f in java_floors]

        for pf in python_floors:
            if pf["floor"] == 1 and pf.get("reward"):
                pf["reward"]["picked"] = "FAKE_CARD"
                break

        diff = compare_floor_checkpoints(java_floors, python_floors)
        assert not diff.ok
        assert diff.first_mismatch["field"] == "picked"

    def test_detects_path_mismatch(self, real_java_log: JavaGameLog) -> None:
        java_floors = build_java_floor_checkpoints(real_java_log)
        python_floors = [f.to_dict() for f in java_floors]

        for pf in python_floors:
            if pf["floor"] == 1 and pf.get("path"):
                pf["path"]["x"] = 999
                break

        diff = compare_floor_checkpoints(java_floors, python_floors)
        assert not diff.ok
        assert diff.first_mismatch["field"] == "x"


class TestEmptyPythonFloors:

    def test_empty_python_floors_is_ok(self) -> None:
        java_floors = [FloorCheckpoint(floor=1)]
        diff = compare_floor_checkpoints(java_floors, [])
        assert not diff.ok
        assert diff.first_mismatch["field"] == "missing"

    def test_no_python_data_returns_missing(self) -> None:
        java_floors = [FloorCheckpoint(floor=1, path={"x": 0, "y": 0, "room_type": "M"})]
        diff = compare_floor_checkpoints(java_floors, [])
        assert not diff.ok


class TestBuildPythonFloorCheckpoints:

    def test_from_path_trace_and_combat_history(self) -> None:
        python_data = {
            "path_trace": [
                {"floor": 1, "x": 2, "y": 0, "room_type": "M"},
            ],
            "combat_history": [
                {
                    "floor": 1,
                    "room_type": "MonsterRoom",
                    "monster_ids": ["JawWorm"],
                    "turns": 3,
                    "player_end_hp": 75,
                    "monster_end_hp": [0],
                    "rng": None,
                },
            ],
            "card_choices": [
                {"floor": 1, "picked": "Shockwave", "upgraded": False},
            ],
            "floor_state_trace": [
                {"floor": 1, "hp": 75, "max_hp": 80, "gold": 113, "deck_count": 11, "relic_count": 1},
            ],
        }
        floors = build_python_floor_checkpoints(python_data)
        assert len(floors) == 1
        assert floors[0]["floor"] == 1
        assert floors[0]["path"]["x"] == 2
        assert floors[0]["battle"]["player_end_hp"] == 75
        assert floors[0]["reward"]["picked"] == "Shockwave"
        assert floors[0]["state"]["gold"] == 113


class TestReplayEdgeCases:

    def test_find_logged_card_match_normalizes_strike_suffix(self) -> None:
        hand = [
            SimpleNamespace(card_id="Strike", upgraded=False, cost=1, cost_for_turn=1),
            SimpleNamespace(card_id="Bash", upgraded=False, cost=2, cost_for_turn=2),
        ]
        logged_card = SimpleNamespace(card_id="Strike_R", upgraded=False, cost=1)

        match_idx, match_type = harness._find_logged_card_match(hand, logged_card)

        assert match_idx == 0
        assert match_type == "exact"

    def test_start_combat_with_monsters_normalizes_logged_ids_without_jaw_worm_fallback(self) -> None:
        engine = RunEngine.create("TESTMONSTERS")
        engine.start_combat_with_monsters(["SpikeSlime_S", "AcidSlime_M", "GremlinThief"])

        assert engine.state.combat is not None
        assert [monster.id for monster in engine.state.combat.state.monsters] == [
            "SpikeSlime_S",
            "AcidSlime_M",
            "GremlinThief",
        ]
        debug = getattr(engine.state, "_last_combat_setup_debug", {})
        assert debug["alias_hits"] == [
            {"logged_id": "SpikeSlime_S", "runtime_id": "SpikeSlimeSmall"},
            {"logged_id": "AcidSlime_M", "runtime_id": "AcidSlimeMedium"},
            {"logged_id": "GremlinThief", "runtime_id": "GremlinSneaky"},
        ]
        assert "fallback_monster_id" not in debug

    def test_start_combat_with_monsters_keeps_known_monsters_when_aliasing_bronze_automaton_lane(self) -> None:
        engine = RunEngine.create("TESTPROXYMONSTERS")
        engine.transition_to_act_for_replay(2, floor=33)
        engine.start_combat_with_monsters(["SphericGuardian", "BronzeOrb", "BronzeAutomaton"])

        assert engine.state.combat is not None
        assert [monster.id for monster in engine.state.combat.state.monsters] == [
            "SphericGuardian",
            "BronzeOrb",
            "BronzeAutomaton",
        ]
        debug = getattr(engine.state, "_last_combat_setup_debug", {})
        assert debug.get("proxy_monster_ids", []) == []
        assert {"logged_id": "BronzeOrb", "runtime_id": "Bronze Orb"} in debug["alias_hits"]
        assert {"logged_id": "BronzeAutomaton", "runtime_id": "Automaton"} in debug["alias_hits"]

    def test_create_replay_monster_uses_concrete_bronze_orb(self) -> None:
        monster, debug = _create_replay_monster(
            "BronzeOrb",
            MutableRNG.from_seed(123456789, counter=0),
            0,
            act=2,
        )

        assert monster is not None
        assert isinstance(monster, BronzeOrb)
        assert debug.get("used_proxy") is not True

    def test_play_logged_battle_turn_cap_sets_debug_and_summary(self, monkeypatch) -> None:
        engine = RunEngine.create("TESTTURNCAP")
        engine.start_combat_with_monsters(["Cultist"])
        battle = SimpleNamespace(
            floor=1,
            turn_count=99,
            monsters=[SimpleNamespace(id="Cultist")],
            cards_played=[],
        )

        monkeypatch.setattr(engine, "is_combat_over", lambda: False)
        monkeypatch.setattr(engine, "combat_play_card", lambda *args, **kwargs: False)
        monkeypatch.setattr(engine, "combat_end_turn", lambda: None)

        result = harness._play_logged_battle(engine, battle, room_type="MonsterRoom", max_turns=2)

        assert result["completed"] is False
        assert result["summary"] is not None
        assert result["summary"]["monster_ids"] == ["Cultist"]
        assert result["debug"]["battle_turn_cap_hit"] is True
        assert result["debug"]["battle_replay_abort_reason"] == "turn_cap"

    def test_play_logged_battle_groups_cards_by_turn(self, monkeypatch) -> None:
        engine = RunEngine.create("TESTTURNPLAYBACK")
        engine.start_combat_with_monsters(["Cultist"])
        combat = engine.state.combat
        assert combat is not None

        class FakeCard:
            def __init__(self, card_id: str, *, upgraded: bool = False, cost: int = 1, attack: bool = True):
                self.card_id = card_id
                self.upgraded = upgraded
                self.cost = cost
                self.cost_for_turn = cost
                self._attack = attack

            def is_attack(self) -> bool:
                return self._attack

            def can_use(self, energy: int) -> bool:
                return energy >= self.cost_for_turn

        hand = [
            FakeCard("Strike", cost=1),
            FakeCard("Bash", cost=2),
        ]
        monkeypatch.setattr(combat.state.card_manager, "get_hand", lambda: hand)

        played_cards: list[int] = []
        end_turn_calls: list[int] = []

        def fake_play(card_idx: int, target_idx: int | None) -> bool:
            played_cards.append(card_idx)
            return True

        def fake_end_turn() -> None:
            end_turn_calls.append(len(played_cards))
            combat.state.turn += 1

        monkeypatch.setattr(engine, "combat_play_card", fake_play)
        monkeypatch.setattr(engine, "combat_end_turn", fake_end_turn)
        monkeypatch.setattr(engine, "is_combat_over", lambda: len(end_turn_calls) >= 2)
        monkeypatch.setattr(engine, "player_won_combat", lambda: False)

        battle = SimpleNamespace(
            floor=1,
            turn_count=2,
            monsters=[SimpleNamespace(id="Cultist")],
            cards_played=[
                SimpleNamespace(card_id="Strike_R", upgraded=False, cost=1, turn=0),
                SimpleNamespace(card_id="Bash", upgraded=False, cost=2, turn=1),
            ],
        )

        result = harness._play_logged_battle(engine, battle, room_type="MonsterRoom", max_turns=5)

        assert played_cards == [0, 1]
        assert end_turn_calls == [1, 2]
        assert result["debug"]["battle_logged_cards_by_turn"] == {
            0: [{"card_id": "Strike_R", "cost": 1, "upgraded": False}],
            1: [{"card_id": "Bash", "cost": 2, "upgraded": False}],
        }
        assert result["debug"]["battle_turn_fallback_counts"] == {0: 0, 1: 0}

    def test_play_logged_battle_records_unmatched_cards_without_cross_turn_fallback(self, monkeypatch) -> None:
        engine = RunEngine.create("TESTUNMATCHEDTURN")
        engine.start_combat_with_monsters(["Cultist"])
        combat = engine.state.combat
        assert combat is not None

        class FakeCard:
            def __init__(self, card_id: str, *, cost: int = 1):
                self.card_id = card_id
                self.upgraded = False
                self.cost = cost
                self.cost_for_turn = cost

            def is_attack(self) -> bool:
                return True

            def can_use(self, energy: int) -> bool:
                return energy >= self.cost_for_turn

        monkeypatch.setattr(combat.state.card_manager, "get_hand", lambda: [FakeCard("Strike", cost=1)])

        played_cards: list[int] = []
        end_turn_calls: list[int] = []

        def fake_play(card_idx: int, target_idx: int | None) -> bool:
            played_cards.append(card_idx)
            return True

        def fake_end_turn() -> None:
            end_turn_calls.append(len(played_cards))
            combat.state.turn += 1

        monkeypatch.setattr(engine, "combat_play_card", fake_play)
        monkeypatch.setattr(engine, "combat_end_turn", fake_end_turn)
        monkeypatch.setattr(engine, "is_combat_over", lambda: len(end_turn_calls) >= 2)
        monkeypatch.setattr(engine, "player_won_combat", lambda: False)

        battle = SimpleNamespace(
            floor=1,
            turn_count=2,
            monsters=[SimpleNamespace(id="Cultist")],
            cards_played=[
                SimpleNamespace(card_id="MissingCard", upgraded=False, cost=1, turn=0),
                SimpleNamespace(card_id="Strike_R", upgraded=False, cost=1, turn=1),
            ],
        )

        result = harness._play_logged_battle(engine, battle, room_type="MonsterRoom", max_turns=5)

        assert end_turn_calls == [1, 2]
        assert len(played_cards) <= 2
        assert result["debug"]["battle_unmatched_cards"][0]["turn"] == 0
        assert result["debug"]["battle_unmatched_cards"][0]["card_id"] == "MissingCard"
        assert result["debug"]["battle_turn_fallback_counts"][0] <= 1

    def test_replay_applies_winding_halls_semantics_to_state_and_deck(self) -> None:
        java_log = _minimal_java_log(
            seed_string="TESTWINDING",
            end_floor=48,
            path_taken=[SimpleNamespace(floor=48, act=3, x=0, y=0, room_type="EventRoom")],
            event_choices=[
                EventChoiceLog("WindingHalls", "Winding Halls", 0, "...", 48, 1),
                EventChoiceLog("WindingHalls", "Winding Halls", 0, "[拥抱疯狂] 12", 48, 2),
                EventChoiceLog("WindingHalls", "Winding Halls", 0, "[离开]", 48, 3),
            ],
            final_deck=[
                *[SimpleNamespace(card_id="Strike", upgraded=False) for _ in range(10)],
                SimpleNamespace(card_id="Madness", upgraded=False),
                SimpleNamespace(card_id="Madness", upgraded=False),
            ],
        )

        python_data = replay_java_log(java_log)
        floor_48 = next(f for f in build_python_floor_checkpoints(python_data) if f["floor"] == 48)
        run_state = build_python_run_state_summary(python_data)

        assert floor_48["state"] == {
            "hp": 68,
            "max_hp": 80,
            "gold": 99,
            "deck_count": 12,
            "relic_count": 1,
        }
        assert floor_48["debug"]["event_semantic_applied"] == ["WindingHalls:madness_hp"]
        assert run_state["final_deck"].count("Madness|-") == 2

    def test_replay_infers_pear_from_treasure_room_max_hp_gain(self) -> None:
        java_log = _minimal_java_log(
            seed_string="TESTPEAR",
            end_floor=26,
            path_taken=[SimpleNamespace(floor=26, act=2, x=0, y=0, room_type="TreasureRoom")],
            hp_changes=[SimpleNamespace(amount=10, source="increaseMaxHp", floor=26, hp_after=90, max_hp=90, timestamp=1)],
            final_relics=["Burning Blood", "Pear"],
        )

        java_floors = build_java_floor_checkpoints(java_log)
        python_data = replay_java_log(java_log)
        python_run_state = build_python_run_state_summary(python_data)

        assert java_floors[0].debug["treasure_inferred_relic"] == "Pear"
        floor_26 = next(f for f in build_python_floor_checkpoints(python_data) if f["floor"] == 26)
        assert floor_26["debug"]["treasure_inferred_relic"] == "Pear"
        assert python_run_state["final_relics"] == ["burningblood", "pear"]

    def test_replay_infers_mausoleum_writhe_when_final_deck_requires_it(self) -> None:
        java_log = _minimal_java_log(
            seed_string="TESTMAUSOLEUM",
            end_floor=28,
            path_taken=[SimpleNamespace(floor=28, act=2, x=0, y=0, room_type="EventRoom")],
            event_choices=[
                EventChoiceLog("TheMausoleum", "The Mausoleum", 0, "[打开棺材] 被诅咒", 28, 1),
                EventChoiceLog("TheMausoleum", "The Mausoleum", 0, "[离开]", 28, 2),
            ],
            final_deck=[
                *[SimpleNamespace(card_id="Strike", upgraded=False) for _ in range(10)],
                SimpleNamespace(card_id="Writhe", upgraded=False),
            ],
        )

        python_data = replay_java_log(java_log)
        floor_28 = next(f for f in build_python_floor_checkpoints(python_data) if f["floor"] == 28)
        run_state = build_python_run_state_summary(python_data)

        assert "TheMausoleum:curse_writhe" in floor_28["debug"]["event_semantic_applied"]
        assert "Writhe|-" in run_state["final_deck"]

    def test_replay_empty_cage_removes_cards_needed_for_final_deck_content(self) -> None:
        java_log = _minimal_java_log(
            seed_string="TESTCAGE",
            end_floor=34,
            path_taken=[
                SimpleNamespace(floor=14, act=1, x=0, y=0, room_type="EventRoom"),
                SimpleNamespace(floor=34, act=2, x=-1, y=15, room_type="TreasureRoomBoss"),
            ],
            event_choices=[
                EventChoiceLog("Sssserpent", "Sssserpent", 0, "[同意] 175", 14, 1),
                EventChoiceLog("Sssserpent", "Sssserpent", 0, "[继续]", 14, 2),
                EventChoiceLog("Sssserpent", "Sssserpent", 0, "[离开]", 14, 3),
            ],
            relic_changes=[
                SimpleNamespace(relic_id="Empty Cage", relic_name="Empty Cage", floor=34, turn=0, action="obtained", source="unknown", timestamp=4),
            ],
            final_deck=[
                *[SimpleNamespace(card_id="Strike", upgraded=False) for _ in range(9)],
            ],
            final_relics=["Burning Blood", "Empty Cage"],
        )

        python_data = replay_java_log(java_log)
        run_state = build_python_run_state_summary(python_data)

        assert run_state["final_deck"].count("Strike|-") == 9
        assert "Doubt|-" not in run_state["final_deck"]


    def test_replay_floors_are_built_from_python_state_not_java_reward_backfill(self) -> None:
        java_log = SimpleNamespace(
            seed_string="TESTSEED0",
            end_floor=1,
            run_result="unknown",
            path_taken=[
                SimpleNamespace(floor=1, act=1, x=0, y=0, room_type="MonsterRoom"),
            ],
            battles=[
                SimpleNamespace(
                    floor=1,
                    room_type="MonsterRoom",
                    monsters=[SimpleNamespace(id="JawWorm", ending_hp=0)],
                    turn_count=1,
                    player_end_hp=80,
                    cards_played=[],
                    rng_state_end=None,
                )
            ],
            card_rewards=[
                SimpleNamespace(
                    floor=1,
                    card_id="SKIP",
                    upgraded=False,
                    skipped=True,
                    choice_type="skip",
                )
            ],
            event_choices=[],
            event_summaries=[],
            hp_changes=[],
            card_draws=[],
            monster_intents=[],
        )

        python_data = replay_java_log(java_log)

        assert python_data["floors"] == build_python_floor_checkpoints(python_data)
        floor_1 = next(f for f in python_data["floors"] if f["floor"] == 1)
        assert "reward" not in floor_1

    def test_replay_handles_treasure_room_boss_act_transition(self) -> None:
        java_log = SimpleNamespace(
            seed_string="TESTSEED1",
            end_floor=18,
            run_result="unknown",
            path_taken=[
                SimpleNamespace(floor=17, act=1, x=-1, y=15, room_type="TreasureRoomBoss"),
                SimpleNamespace(floor=18, act=2, x=0, y=0, room_type="MonsterRoom"),
            ],
            battles=[
                SimpleNamespace(
                    floor=18,
                    room_type="MonsterRoom",
                    monsters=[SimpleNamespace(id="Cultist", ending_hp=0)],
                    turn_count=1,
                    player_end_hp=80,
                    cards_played=[],
                    rng_state_end=None,
                )
            ],
            card_rewards=[],
            boss_relic_choices=[],
            treasure_rooms=[],
            event_choices=[],
            event_summaries=[],
            hp_changes=[],
            card_draws=[],
            monster_intents=[],
        )

        python_data = replay_java_log(java_log)
        floors = build_python_floor_checkpoints(python_data)

        floor_17 = next(f for f in floors if f["floor"] == 17)
        floor_18 = next(f for f in floors if f["floor"] == 18)
        assert floor_17["path"]["room_type"] == "TreasureRoom"
        assert floor_17.get("battle") is None
        assert floor_18["path"]["room_type"] == "MonsterRoom"
        assert floor_18["battle"]["room_type"] == "MonsterRoom"

    def test_replay_surfaces_boss_relic_choice_and_treasure_blocks(self) -> None:
        java_log = _minimal_java_log(
            seed_string="TESTREWARDSURFACE",
            end_floor=17,
            path_taken=[
                SimpleNamespace(floor=17, act=1, x=-1, y=15, room_type="TreasureRoomBoss"),
            ],
            boss_relic_choices=[
                SimpleNamespace(
                    floor=17,
                    picked_relic_id=None,
                    not_picked_relic_ids=["TinyHouse", "CallingBell", "PandoraBox"],
                    skipped=True,
                )
            ],
            treasure_rooms=[
                SimpleNamespace(
                    floor=17,
                    room_type="TreasureRoom",
                    main_relic_id="Strawberry",
                    relic_id="Strawberry",
                    obtained_relic_ids=["Anchor"],
                    skipped_main_relic_id="Strawberry",
                    took_sapphire_key=True,
                )
            ],
        )

        python_data = replay_java_log(java_log)
        floor_17 = next(f for f in build_python_floor_checkpoints(python_data) if f["floor"] == 17)

        assert floor_17["boss_relic_choice"] == {
            "picked_relic_id": None,
            "not_picked_relic_ids": ["TinyHouse", "CallingBell", "PandoraBox"],
            "skipped": True,
        }
        assert floor_17["treasure"] == {
            "room_type": "TreasureRoom",
            "main_relic_id": "Strawberry",
            "obtained_relic_ids": ["Anchor"],
            "skipped_main_relic_id": "Strawberry",
            "took_sapphire_key": True,
        }

    def test_replay_reward_surface_falls_back_to_java_history_when_runtime_history_missing(self, monkeypatch) -> None:
        java_log = _minimal_java_log(
            seed_string="TESTREWARDFALLBACK",
            end_floor=17,
            path_taken=[SimpleNamespace(floor=17, act=1, x=-1, y=15, room_type="TreasureRoomBoss")],
            boss_relic_choices=[
                SimpleNamespace(
                    floor=17,
                    picked_relic_id="TinyHouse",
                    not_picked_relic_ids=["CallingBell", "PandoraBox"],
                    skipped=False,
                )
            ],
            treasure_rooms=[
                SimpleNamespace(
                    floor=17,
                    room_type="TreasureRoom",
                    main_relic_id="Strawberry",
                    relic_id="Strawberry",
                    obtained_relic_ids=["Anchor"],
                    skipped_main_relic_id="Strawberry",
                    took_sapphire_key=True,
                )
            ],
        )

        from sts_py.engine.run.run_engine import RunState

        original_to_dict = RunState.to_dict

        def _without_reward_history(self):
            data = original_to_dict(self)
            data.pop("boss_relic_choices", None)
            data.pop("treasure_rooms", None)
            return data

        monkeypatch.setattr(RunState, "to_dict", _without_reward_history)

        python_data = replay_java_log(java_log)

        assert python_data["boss_relic_choices"] == [
            {
                "floor": 17,
                "picked_relic_id": "TinyHouse",
                "not_picked_relic_ids": ["CallingBell", "PandoraBox"],
                "skipped": False,
            }
        ]
        assert python_data["treasure_rooms"] == [
            {
                "floor": 17,
                "room_type": "TreasureRoom",
                "main_relic_id": "Strawberry",
                "obtained_relic_ids": ["Anchor"],
                "skipped_main_relic_id": "Strawberry",
                "took_sapphire_key": True,
            }
        ]

    def test_replay_prefers_runtime_relic_history_when_present(self, monkeypatch) -> None:
        java_log = _minimal_java_log(
            seed_string="TESTRELICHISTORYRUNTIME",
            end_floor=17,
            path_taken=[SimpleNamespace(floor=17, act=1, x=-1, y=15, room_type="TreasureRoom")],
            relic_changes=[
                SimpleNamespace(
                    relic_id="Anchor",
                    relic_name="Anchor",
                    floor=17,
                    turn=0,
                    action="obtained",
                    source="shop",
                    timestamp=1,
                )
            ],
        )

        from sts_py.engine.run.run_engine import RunState

        original_to_dict = RunState.to_dict

        def _with_runtime_relic_history(self):
            data = original_to_dict(self)
            data["relic_history"] = [
                {
                    "floor": 17,
                    "relic_id": "Anchor",
                    "source": "treasure",
                }
            ]
            return data

        monkeypatch.setattr(RunState, "to_dict", _with_runtime_relic_history)

        python_data = replay_java_log(java_log)
        floors = build_python_floor_checkpoints(python_data)
        floor_17 = next(f for f in floors if f["floor"] == 17)

        assert python_data["relic_history"] == [
            {
                "floor": 17,
                "relic_id": "Anchor",
                "source": "treasure",
            }
        ]
        assert floor_17["debug"]["relic_history"] == [
            {
                "floor": 17,
                "relic_id": "anchor",
                "source": "treasure",
            }
        ]

    def test_replay_relic_history_falls_back_to_java_obtained_changes_when_runtime_history_missing(self, monkeypatch) -> None:
        java_log = _minimal_java_log(
            seed_string="TESTRELICHISTORYFALLBACK",
            end_floor=17,
            path_taken=[SimpleNamespace(floor=17, act=1, x=-1, y=15, room_type="ShopRoom")],
            relic_changes=[
                SimpleNamespace(
                    relic_id="CallingBell",
                    relic_name="Calling Bell",
                    floor=17,
                    turn=0,
                    action="obtained",
                    source="boss",
                    timestamp=1,
                ),
                SimpleNamespace(
                    relic_id="Anchor",
                    relic_name="Anchor",
                    floor=17,
                    turn=0,
                    action="obtained",
                    source="calling_bell",
                    timestamp=2,
                ),
                SimpleNamespace(
                    relic_id="DreamCatcher",
                    relic_name="Dream Catcher",
                    floor=17,
                    turn=0,
                    action="triggered:onEquip",
                    source=None,
                    timestamp=3,
                ),
            ],
        )

        from sts_py.engine.run.run_engine import RunState

        original_to_dict = RunState.to_dict

        def _without_relic_history(self):
            data = original_to_dict(self)
            data.pop("relic_history", None)
            return data

        monkeypatch.setattr(RunState, "to_dict", _without_relic_history)

        python_data = replay_java_log(java_log)
        floors = build_python_floor_checkpoints(python_data)
        floor_17 = next(f for f in floors if f["floor"] == 17)

        assert python_data["relic_history"] == [
            {
                "floor": 17,
                "relic_id": "callingbell",
                "source": "boss",
            },
            {
                "floor": 17,
                "relic_id": "anchor",
                "source": "calling_bell",
            },
        ]
        assert floor_17["debug"]["relic_history"] == python_data["relic_history"]

    def test_build_java_floor_checkpoints_surfaces_shop_block(self) -> None:
        java_log = _minimal_java_log(
            seed_string="TESTSHOPBLOCK",
            end_floor=12,
            path_taken=[SimpleNamespace(floor=12, act=1, x=0, y=11, room_type="ShopRoom")],
            shop_visits=[
                SimpleNamespace(
                    floor=12,
                    initial_relic_offer_ids=["Anchor", "Lantern", "Membership Card"],
                    initial_colored_card_offer_ids=["Pommel Strike", "Shrug It Off", "Inflame", "True Grit", "Demon Form"],
                    initial_colorless_card_offer_ids=["Madness", "Apotheosis"],
                    initial_potion_offer_ids=["AttackPotion", "BlockPotion", "ExplosivePotion"],
                    surfaced_relic_ids=["Anchor", "Lantern", "Membership Card", "Oddly Smooth Stone"],
                    surfaced_colored_card_ids=["Pommel Strike", "Shrug It Off", "Inflame", "True Grit", "Demon Form", "Offering"],
                    surfaced_colorless_card_ids=["Madness", "Apotheosis", "MasterOfStrategy"],
                    surfaced_potion_ids=["AttackPotion", "BlockPotion", "ExplosivePotion", "DexterityPotion"],
                    purchased_relic_ids=["Anchor"],
                    timestamp=1,
                )
            ],
        )

        floor_12 = next(f for f in build_java_floor_checkpoints(java_log) if f.floor == 12)

        assert floor_12.shop == {
            "surfaced_relic_ids": ["anchor", "lantern", "membershipcard", "oddlysmoothstone"],
            "purchased_relic_ids": ["anchor"],
            "surfaced_colored_card_ids": ["pommelstrike", "shrugitoff", "inflame", "truegrit", "demonform", "offering"],
            "surfaced_colorless_card_ids": ["madness", "apotheosis", "masterofstrategy"],
            "surfaced_potion_ids": ["attackpotion", "blockpotion", "explosivepotion", "dexteritypotion"],
        }

    def test_replay_prefers_runtime_shop_history_when_it_matches_java_shop_visits(self, monkeypatch) -> None:
        java_log = _minimal_java_log(
            seed_string="TESTSHOPRUNTIME",
            end_floor=12,
            path_taken=[SimpleNamespace(floor=12, act=1, x=0, y=11, room_type="ShopRoom")],
            shop_visits=[
                SimpleNamespace(
                    floor=12,
                    initial_relic_offer_ids=["Anchor", "Lantern", "Membership Card"],
                    initial_colored_card_offer_ids=["Pommel Strike", "Shrug It Off", "Inflame", "True Grit", "Demon Form"],
                    initial_colorless_card_offer_ids=["Madness", "Apotheosis"],
                    initial_potion_offer_ids=["AttackPotion", "BlockPotion", "ExplosivePotion"],
                    surfaced_relic_ids=["Anchor", "Lantern", "Membership Card", "Oddly Smooth Stone"],
                    surfaced_colored_card_ids=["Pommel Strike", "Shrug It Off", "Inflame", "True Grit", "Demon Form", "Offering"],
                    surfaced_colorless_card_ids=["Madness", "Apotheosis", "MasterOfStrategy"],
                    surfaced_potion_ids=["AttackPotion", "BlockPotion", "ExplosivePotion", "DexterityPotion"],
                    purchased_relic_ids=["Anchor"],
                    timestamp=1,
                )
            ],
        )

        from sts_py.engine.run.run_engine import RunState

        original_to_dict = RunState.to_dict

        def _with_runtime_shop_history(self):
            data = original_to_dict(self)
            data["shop_history"] = [
                {
                    "floor": 12,
                    "surfaced_relic_ids": ["Anchor", "Lantern", "MembershipCard", "OddlySmoothStone"],
                    "current_relic_ids": ["Lantern", "MembershipCard", "OddlySmoothStone"],
                    "purchased_relic_ids": ["Anchor"],
                    "initial_colored_card_ids": ["PommelStrike", "ShrugItOff", "Inflame", "TrueGrit", "DemonForm"],
                    "current_colored_card_ids": ["ShrugItOff", "Inflame", "TrueGrit", "DemonForm", "Offering"],
                    "surfaced_colored_card_ids": ["PommelStrike", "ShrugItOff", "Inflame", "TrueGrit", "DemonForm", "Offering"],
                    "initial_colorless_card_ids": ["Madness", "Apotheosis"],
                    "current_colorless_card_ids": ["Madness", "Apotheosis"],
                    "surfaced_colorless_card_ids": ["Madness", "Apotheosis", "MasterOfStrategy"],
                    "initial_potion_ids": ["AttackPotion", "BlockPotion", "ExplosivePotion"],
                    "current_potion_ids": ["BlockPotion", "ExplosivePotion", "DexterityPotion"],
                    "surfaced_potion_ids": ["AttackPotion", "BlockPotion", "ExplosivePotion", "DexterityPotion"],
                }
            ]
            return data

        monkeypatch.setattr(RunState, "to_dict", _with_runtime_shop_history)

        python_data = replay_java_log(java_log)
        floor_12 = next(f for f in build_python_floor_checkpoints(python_data) if f["floor"] == 12)

        assert python_data["shop_history"] == [
            {
                "floor": 12,
                "surfaced_relic_ids": ["Anchor", "Lantern", "MembershipCard", "OddlySmoothStone"],
                "current_relic_ids": ["Lantern", "MembershipCard", "OddlySmoothStone"],
                "purchased_relic_ids": ["Anchor"],
                "initial_colored_card_ids": ["PommelStrike", "ShrugItOff", "Inflame", "TrueGrit", "DemonForm"],
                "current_colored_card_ids": ["ShrugItOff", "Inflame", "TrueGrit", "DemonForm", "Offering"],
                "surfaced_colored_card_ids": ["PommelStrike", "ShrugItOff", "Inflame", "TrueGrit", "DemonForm", "Offering"],
                "initial_colorless_card_ids": ["Madness", "Apotheosis"],
                "current_colorless_card_ids": ["Madness", "Apotheosis"],
                "surfaced_colorless_card_ids": ["Madness", "Apotheosis", "MasterOfStrategy"],
                "initial_potion_ids": ["AttackPotion", "BlockPotion", "ExplosivePotion"],
                "current_potion_ids": ["BlockPotion", "ExplosivePotion", "DexterityPotion"],
                "surfaced_potion_ids": ["AttackPotion", "BlockPotion", "ExplosivePotion", "DexterityPotion"],
            }
        ]
        assert floor_12["shop"] == {
            "surfaced_relic_ids": ["anchor", "lantern", "membershipcard", "oddlysmoothstone"],
            "purchased_relic_ids": ["anchor"],
            "surfaced_colored_card_ids": ["pommelstrike", "shrugitoff", "inflame", "truegrit", "demonform", "offering"],
            "surfaced_colorless_card_ids": ["madness", "apotheosis", "masterofstrategy"],
            "surfaced_potion_ids": ["attackpotion", "blockpotion", "explosivepotion", "dexteritypotion"],
        }

    def test_replay_shop_history_falls_back_to_java_when_runtime_history_mismatches_java_shop_visits(self, monkeypatch) -> None:
        java_log = _minimal_java_log(
            seed_string="TESTSHOPMISMATCHFALLBACK",
            end_floor=12,
            path_taken=[SimpleNamespace(floor=12, act=1, x=0, y=11, room_type="ShopRoom")],
            shop_visits=[
                SimpleNamespace(
                    floor=12,
                    initial_relic_offer_ids=["Anchor", "Lantern", "Membership Card"],
                    initial_colored_card_offer_ids=["Pommel Strike", "Shrug It Off", "Inflame", "True Grit", "Demon Form"],
                    initial_colorless_card_offer_ids=["Madness", "Apotheosis"],
                    initial_potion_offer_ids=["AttackPotion", "BlockPotion", "ExplosivePotion"],
                    surfaced_relic_ids=["Anchor", "Lantern", "Membership Card", "Oddly Smooth Stone"],
                    surfaced_colored_card_ids=["Pommel Strike", "Shrug It Off", "Inflame", "True Grit", "Demon Form", "Offering"],
                    surfaced_colorless_card_ids=["Madness", "Apotheosis", "MasterOfStrategy"],
                    surfaced_potion_ids=["AttackPotion", "BlockPotion", "ExplosivePotion", "DexterityPotion"],
                    purchased_relic_ids=["Anchor"],
                    timestamp=1,
                )
            ],
        )

        from sts_py.engine.run.run_engine import RunState

        original_to_dict = RunState.to_dict

        def _with_mismatched_runtime_shop_history(self):
            data = original_to_dict(self)
            data["shop_history"] = [
                {
                    "floor": 12,
                    "surfaced_relic_ids": ["Anchor", "Lantern", "MembershipCard", "ToyOrnithopter"],
                    "current_relic_ids": ["Lantern", "MembershipCard", "ToyOrnithopter"],
                    "purchased_relic_ids": [],
                    "initial_colored_card_ids": ["PommelStrike", "ShrugItOff", "Inflame", "TrueGrit", "DemonForm"],
                    "current_colored_card_ids": ["ShrugItOff", "Inflame", "TrueGrit", "DemonForm", "SeeingRed"],
                    "surfaced_colored_card_ids": ["PommelStrike", "ShrugItOff", "Inflame", "TrueGrit", "DemonForm", "SeeingRed"],
                    "initial_colorless_card_ids": ["Madness", "Apotheosis"],
                    "current_colorless_card_ids": ["Madness", "Apotheosis"],
                    "surfaced_colorless_card_ids": ["Madness", "Apotheosis"],
                    "initial_potion_ids": ["AttackPotion", "BlockPotion", "ExplosivePotion"],
                    "current_potion_ids": ["BlockPotion", "ExplosivePotion", "EnergyPotion"],
                    "surfaced_potion_ids": ["AttackPotion", "BlockPotion", "ExplosivePotion", "EnergyPotion"],
                }
            ]
            return data

        monkeypatch.setattr(RunState, "to_dict", _with_mismatched_runtime_shop_history)

        python_data = replay_java_log(java_log)
        floor_12 = next(f for f in build_python_floor_checkpoints(python_data) if f["floor"] == 12)

        assert python_data["shop_history"] == [
            {
                "floor": 12,
                "surfaced_relic_ids": ["Anchor", "Lantern", "Membership Card", "Oddly Smooth Stone"],
                "current_relic_ids": [],
                "purchased_relic_ids": ["Anchor"],
                "initial_colored_card_ids": ["Pommel Strike", "Shrug It Off", "Inflame", "True Grit", "Demon Form"],
                "current_colored_card_ids": [],
                "surfaced_colored_card_ids": ["Pommel Strike", "Shrug It Off", "Inflame", "True Grit", "Demon Form", "Offering"],
                "initial_colorless_card_ids": ["Madness", "Apotheosis"],
                "current_colorless_card_ids": [],
                "surfaced_colorless_card_ids": ["Madness", "Apotheosis", "MasterOfStrategy"],
                "initial_potion_ids": ["AttackPotion", "BlockPotion", "ExplosivePotion"],
                "current_potion_ids": [],
                "surfaced_potion_ids": ["AttackPotion", "BlockPotion", "ExplosivePotion", "DexterityPotion"],
            }
        ]
        assert floor_12["shop"] == {
            "surfaced_relic_ids": ["anchor", "lantern", "membershipcard", "oddlysmoothstone"],
            "purchased_relic_ids": ["anchor"],
            "surfaced_colored_card_ids": ["pommelstrike", "shrugitoff", "inflame", "truegrit", "demonform", "offering"],
            "surfaced_colorless_card_ids": ["madness", "apotheosis", "masterofstrategy"],
            "surfaced_potion_ids": ["attackpotion", "blockpotion", "explosivepotion", "dexteritypotion"],
        }

    def test_replay_shop_history_falls_back_to_java_when_runtime_history_missing(self, monkeypatch) -> None:
        java_log = _minimal_java_log(
            seed_string="TESTSHOPFALLBACK",
            end_floor=12,
            path_taken=[SimpleNamespace(floor=12, act=1, x=0, y=11, room_type="ShopRoom")],
            shop_visits=[
                SimpleNamespace(
                    floor=12,
                    initial_relic_offer_ids=["Anchor", "Lantern", "Membership Card"],
                    initial_colored_card_offer_ids=["Pommel Strike", "Shrug It Off", "Inflame", "True Grit", "Demon Form"],
                    initial_colorless_card_offer_ids=["Madness", "Apotheosis"],
                    initial_potion_offer_ids=["AttackPotion", "BlockPotion", "ExplosivePotion"],
                    surfaced_relic_ids=["Anchor", "Lantern", "Membership Card", "Oddly Smooth Stone"],
                    surfaced_colored_card_ids=["Pommel Strike", "Shrug It Off", "Inflame", "True Grit", "Demon Form", "Offering"],
                    surfaced_colorless_card_ids=["Madness", "Apotheosis", "MasterOfStrategy"],
                    surfaced_potion_ids=["AttackPotion", "BlockPotion", "ExplosivePotion", "DexterityPotion"],
                    purchased_relic_ids=["Anchor"],
                    timestamp=1,
                )
            ],
        )

        from sts_py.engine.run.run_engine import RunState

        original_to_dict = RunState.to_dict

        def _without_shop_history(self):
            data = original_to_dict(self)
            data.pop("shop_history", None)
            return data

        monkeypatch.setattr(RunState, "to_dict", _without_shop_history)

        python_data = replay_java_log(java_log)
        floor_12 = next(f for f in build_python_floor_checkpoints(python_data) if f["floor"] == 12)

        assert python_data["shop_history"] == [
            {
                "floor": 12,
                "surfaced_relic_ids": ["Anchor", "Lantern", "Membership Card", "Oddly Smooth Stone"],
                "current_relic_ids": [],
                "purchased_relic_ids": ["Anchor"],
                "initial_colored_card_ids": ["Pommel Strike", "Shrug It Off", "Inflame", "True Grit", "Demon Form"],
                "current_colored_card_ids": [],
                "surfaced_colored_card_ids": ["Pommel Strike", "Shrug It Off", "Inflame", "True Grit", "Demon Form", "Offering"],
                "initial_colorless_card_ids": ["Madness", "Apotheosis"],
                "current_colorless_card_ids": [],
                "surfaced_colorless_card_ids": ["Madness", "Apotheosis", "MasterOfStrategy"],
                "initial_potion_ids": ["AttackPotion", "BlockPotion", "ExplosivePotion"],
                "current_potion_ids": [],
                "surfaced_potion_ids": ["AttackPotion", "BlockPotion", "ExplosivePotion", "DexterityPotion"],
            }
        ]
        assert floor_12["shop"] == {
            "surfaced_relic_ids": ["anchor", "lantern", "membershipcard", "oddlysmoothstone"],
            "purchased_relic_ids": ["anchor"],
            "surfaced_colored_card_ids": ["pommelstrike", "shrugitoff", "inflame", "truegrit", "demonform", "offering"],
            "surfaced_colorless_card_ids": ["madness", "apotheosis", "masterofstrategy"],
            "surfaced_potion_ids": ["attackpotion", "blockpotion", "explosivepotion", "dexteritypotion"],
        }

    def test_compare_floor_checkpoints_ignores_runtime_only_new_shop_surface_fields_when_java_lacks_them(self) -> None:
        java_floors = [
            FloorCheckpoint(
                floor=12,
                shop={
                    "surfaced_relic_ids": ["anchor", "lantern", "membershipcard"],
                    "purchased_relic_ids": [],
                },
            )
        ]
        python_floors = [
            {
                "floor": 12,
                "shop": {
                    "surfaced_relic_ids": ["Anchor", "Lantern", "MembershipCard"],
                    "current_relic_ids": ["Anchor", "Lantern", "MembershipCard"],
                    "purchased_relic_ids": [],
                    "initial_colored_card_ids": ["PommelStrike"],
                    "current_colored_card_ids": ["PommelStrike"],
                    "surfaced_colored_card_ids": ["PommelStrike"],
                    "initial_colorless_card_ids": ["Madness"],
                    "current_colorless_card_ids": ["Madness"],
                    "surfaced_colorless_card_ids": ["Madness"],
                    "initial_potion_ids": ["AttackPotion"],
                    "current_potion_ids": ["AttackPotion"],
                    "surfaced_potion_ids": ["AttackPotion"],
                },
            }
        ]

        diff = compare_floor_checkpoints(java_floors, python_floors)

        assert diff.ok

    def test_replay_terminal_death_floor_without_battle_is_accepted(self) -> None:
        java_log = SimpleNamespace(
            seed_string="TESTSEED2",
            end_floor=50,
            run_result="death",
            path_taken=[
                SimpleNamespace(floor=50, act=3, x=-1, y=15, room_type="MonsterRoomBoss"),
            ],
            battles=[],
            card_rewards=[],
            event_choices=[],
            event_summaries=[],
            hp_changes=[],
            card_draws=[],
            monster_intents=[],
        )

        python_data = replay_java_log(java_log)
        floors = build_python_floor_checkpoints(python_data)

        assert floors == [{
            "floor": 50,
            "debug": {"terminal_incomplete_combat": True, "state_reconciled_from_deltas": True},
            "path": {"x": -1, "y": 15, "room_type": "MonsterRoomBoss"},
            "state": {"hp": 80, "max_hp": 80, "gold": 99, "deck_count": 10, "relic_count": 1},
        }]
        assert python_data["phase"] == "game_over"
        assert python_data["derived_run_result"] == "death"

    def test_shop_floor_state_reconciliation_avoids_double_gold_deduction(self) -> None:
        java_log = SimpleNamespace(
            seed_string="TESTSHOP1",
            character="IRONCLAD",
            initial_deck=[SimpleNamespace(card_id="Strike", upgraded=False) for _ in range(10)],
            initial_relics=["Burning Blood"],
            end_floor=1,
            run_result="unknown",
            path_taken=[SimpleNamespace(floor=1, act=1, x=0, y=0, room_type="ShopRoom")],
            battles=[],
            card_rewards=[],
            event_choices=[],
            event_summaries=[],
            rest_actions=[],
            hp_changes=[],
            gold_changes=[],
            card_obtains=[SimpleNamespace(card_id="Sever Soul", upgraded=False, source="shop", floor=1, timestamp=3)],
            card_removals=[],
            card_transforms=[],
            relic_changes=[],
            shop_purchases=[SimpleNamespace(item_type="card", item_id="Sever Soul", floor=1, gold=99, gold_spent=75, timestamp=1)],
            shop_purges=[],
            potion_obtains=[],
            potion_uses=[],
            card_draws=[],
            monster_intents=[],
        )

        python_data = replay_java_log(java_log)
        floor_1 = next(f for f in build_python_floor_checkpoints(python_data) if f["floor"] == 1)

        assert floor_1["state"]["gold"] == 24
        assert floor_1["state"]["deck_count"] == 11
        assert floor_1["debug"]["state_reconciled_from_deltas"] is True

    def test_replay_act_transition_preserves_history(self) -> None:
        java_log = SimpleNamespace(
            seed_string="TESTSEED3",
            end_floor=18,
            run_result="unknown",
            path_taken=[
                SimpleNamespace(floor=16, act=1, x=-1, y=15, room_type="MonsterRoomBoss"),
                SimpleNamespace(floor=17, act=1, x=-1, y=15, room_type="TreasureRoomBoss"),
                SimpleNamespace(floor=18, act=2, x=0, y=0, room_type="MonsterRoom"),
            ],
            battles=[
                SimpleNamespace(
                    floor=16,
                    room_type="MonsterRoomBoss",
                    monsters=[SimpleNamespace(id="Hexaghost", ending_hp=0)],
                    turn_count=2,
                    player_end_hp=70,
                    cards_played=[],
                    rng_state_end=None,
                ),
                SimpleNamespace(
                    floor=18,
                    room_type="MonsterRoom",
                    monsters=[SimpleNamespace(id="Cultist", ending_hp=0)],
                    turn_count=1,
                    player_end_hp=68,
                    cards_played=[],
                    rng_state_end=None,
                ),
            ],
            card_rewards=[],
            event_choices=[],
            event_summaries=[],
            hp_changes=[],
            card_draws=[],
            monster_intents=[],
        )

        python_data = replay_java_log(java_log)

        assert [entry["floor"] for entry in python_data["path_trace"]] == [16, 17, 18]
        assert [entry["floor"] for entry in python_data["combat_history"]] == [16, 18]

    def test_replay_incomplete_battle_still_emits_summary_and_debug(self) -> None:
        java_log = SimpleNamespace(
            seed_string="TESTHEXAGHOSTREPLAY",
            end_floor=16,
            run_result="unknown",
            path_taken=[SimpleNamespace(floor=16, act=1, x=-1, y=15, room_type="MonsterRoomBoss")],
            battles=[
                SimpleNamespace(
                    floor=16,
                    room_type="MonsterRoomBoss",
                    monsters=[SimpleNamespace(id="Hexaghost", ending_hp=0)],
                    turn_count=8,
                    player_end_hp=70,
                    cards_played=[],
                    rng_state_end=None,
                )
            ],
            card_rewards=[],
            event_choices=[],
            event_summaries=[],
            hp_changes=[],
            card_draws=[],
            monster_intents=[],
        )

        python_data = replay_java_log(java_log)
        floor_16 = next(f for f in build_python_floor_checkpoints(python_data) if f["floor"] == 16)

        assert floor_16["battle"]["monster_ids"] == ["Hexaghost"]
        assert floor_16["debug"]["battle_logged_intents_by_turn"] == {}
        assert floor_16["debug"]["battle_logged_draws_by_turn"] == {}
        assert floor_16["debug"]["python_turn_count"] == floor_16["battle"]["turns"]


class TestPhase28CombatSemantics:

    def test_battle_trance_blocks_followup_draws_until_end_of_round(self) -> None:
        combat = _make_test_combat()
        cm = combat.state.card_manager
        player = combat.state.player
        assert cm is not None

        battle_trance = CardInstance(card_id="BattleTrance")
        cm.hand.cards = [battle_trance]
        cm.draw_pile.cards = [
            CardInstance(card_id="Strike"),
            CardInstance(card_id="Defend"),
            CardInstance(card_id="Bash"),
        ]

        BattleTranceEffect(draw_count=2).execute(combat.state, battle_trance, player, None)
        hand_after_battle_trance = len(cm.hand.cards)

        DrawCardsEffect(count=1).execute(combat.state, battle_trance, player, None)
        assert len(cm.hand.cards) == hand_after_battle_trance

        player.powers.at_end_of_round()
        DrawCardsEffect(count=1).execute(combat.state, battle_trance, player, None)
        assert len(cm.hand.cards) == hand_after_battle_trance + 1

    def test_armaments_plus_upgrades_other_hand_cards_not_self_again(self) -> None:
        combat = _make_test_combat()
        cm = combat.state.card_manager
        player = combat.state.player
        assert cm is not None

        armaments = CardInstance(card_id="Armaments")
        armaments.upgrade()
        strike = CardInstance(card_id="Strike")
        defend = CardInstance(card_id="Defend")
        cm.hand.cards = [armaments, strike, defend]

        UpgradeHandCardEffect().execute(combat.state, armaments, player, None)

        assert strike.upgraded is True
        assert defend.upgraded is True
        assert armaments.times_upgraded == 1

    def test_burning_pact_exhausts_other_card_and_triggers_exhaust_powers(self) -> None:
        combat = _make_test_combat()
        cm = combat.state.card_manager
        player = combat.state.player
        assert cm is not None

        player.add_power(create_power("FeelNoPain", 3, "player"))
        player.add_power(create_power("DarkEmbrace", 1, "player"))
        burning_pact = CardInstance(card_id="BurningPact")
        strike = CardInstance(card_id="Strike")
        defend = CardInstance(card_id="Defend")
        cm.hand.cards = [burning_pact, strike, defend]
        cm.draw_pile.cards = [
            CardInstance(card_id="Bash"),
            CardInstance(card_id="Strike"),
            CardInstance(card_id="Defend"),
        ]

        BurningPactEffect(draw_count=2).execute(combat.state, burning_pact, player, None)

        assert len(cm.exhaust_pile.cards) == 1
        assert cm.exhaust_pile.cards[0].card_id in {"Strike", "Defend"}
        assert player.block == 3
        assert len(cm.hand.cards) == 5

    def test_sever_soul_exhausts_non_attacks_and_triggers_exhaust_hooks(self) -> None:
        combat = _make_test_combat()
        cm = combat.state.card_manager
        player = combat.state.player
        assert cm is not None

        player.add_power(create_power("FeelNoPain", 4, "player"))
        sever_soul = CardInstance(card_id="SeverSoul")
        strike = CardInstance(card_id="Strike")
        defend = CardInstance(card_id="Defend")
        battle_trance = CardInstance(card_id="BattleTrance")
        cm.hand.cards = [sever_soul, strike, defend, battle_trance]

        SeverSoulEffect(damage=16).execute(combat.state, sever_soul, player, combat.state.monsters[0])

        assert [card.card_id for card in cm.hand.cards] == ["SeverSoul", "Strike"]
        assert sorted(card.card_id for card in cm.exhaust_pile.cards) == ["BattleTrance", "Defend"]
        assert player.block == 8

    def test_play_logged_battle_records_temp_upgrade_and_pile_debug(self) -> None:
        engine = RunEngine.create("PHASE28TEMPUPGRADE", ascension=0)
        engine.state.deck = ["Armaments", "Strike", "Defend", "Bash", "Strike"]
        engine.start_combat_with_monsters(["JawWorm"])
        combat = engine.state.combat
        assert combat is not None
        cm = combat.state.card_manager
        assert cm is not None
        cm.hand.cards = [CardInstance(card_id="Strike"), CardInstance(card_id="Defend")]
        cm.draw_pile.cards = [CardInstance(card_id="Bash"), CardInstance(card_id="Strike")]
        cm.discard_pile.cards = []
        cm.exhaust_pile.cards = []

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="JawWorm", ending_hp=0)],
            turn_count=1,
            player_end_hp=80,
            cards_played=[
                SimpleNamespace(turn=0, card_id="Strike_R", cost=1, upgraded=True),
            ],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(engine, battle, room_type="MonsterRoom", max_turns=2)

        assert result["debug"]["battle_temporary_upgrade_match"] is True
        assert result["debug"]["battle_temporary_upgrade_matches"][0]["card_id"] == "Strike_R"
        assert 0 in result["debug"]["python_card_piles_by_turn"]
        assert result["debug"]["python_card_piles_by_turn"][0]["exhaust"] >= 0

    def test_play_logged_battle_marks_first_card_state_desync_turn(self) -> None:
        engine = RunEngine.create("PHASE28DESYNC", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.start_combat_with_monsters(["JawWorm"])
        combat = engine.state.combat
        assert combat is not None
        cm = combat.state.card_manager
        assert cm is not None
        cm.hand.cards = [CardInstance(card_id="Strike")]
        cm.draw_pile.cards = [CardInstance(card_id="Defend")]
        cm.discard_pile.cards = []
        cm.exhaust_pile.cards = []

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="JawWorm", ending_hp=0)],
            turn_count=1,
            player_end_hp=80,
            cards_played=[
                SimpleNamespace(turn=0, card_id="BurningPact", cost=1, upgraded=False),
            ],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(engine, battle, room_type="MonsterRoom", max_turns=2)

        assert result["debug"]["battle_card_state_desync_turn"] == 0
        assert result["debug"]["battle_unmatched_cards"][0]["card_id"] == "BurningPact"

    def test_play_logged_battle_reconciles_opening_hand_from_draw_pile(self) -> None:
        engine = RunEngine.create("PHASE29OPENING", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Strike", "Defend", "Bash", "Strike"]
        engine.start_combat_with_monsters(["Cultist"])
        combat = engine.state.combat
        assert combat is not None
        cm = combat.state.card_manager
        assert cm is not None
        cm.hand.cards = [
            CardInstance(card_id="Strike"),
            CardInstance(card_id="Strike"),
            CardInstance(card_id="Defend"),
            CardInstance(card_id="Defend"),
            CardInstance(card_id="Strike"),
        ]
        cm.draw_pile.cards = [CardInstance(card_id="Bash")]
        cm.discard_pile.cards = []
        cm.exhaust_pile.cards = []
        cm._cards_drawn_this_turn = 5

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Cultist", ending_hp=0)],
            turn_count=1,
            player_end_hp=80,
            cards_played=[SimpleNamespace(turn=0, card_id="Bash", cost=2, upgraded=False)],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_draws_by_turn={0: [{"num_cards": 5}]},
            max_turns=2,
        )

        promoted = result["debug"]["battle_required_cards_promoted"]
        assert result["debug"]["battle_opening_hand_reconciled"] is True
        assert promoted[0]["logged_card_id"] == "Bash"
        assert promoted[0]["opening_hand"] is True
        assert all(item["card_id"] != "Bash" for item in result["debug"].get("battle_unmatched_cards", []))

    def test_opening_hand_reconciliation_does_not_demote_prior_required_card(self) -> None:
        engine = RunEngine.create("PHASE46OPENINGKEEP", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "FlameBarrier", "Strike", "Defend", "Strike"]
        engine.start_combat_with_monsters(["Cultist"])
        combat = engine.state.combat
        assert combat is not None
        cm = combat.state.card_manager
        assert cm is not None
        cm.hand.cards = [
            CardInstance(card_id="Strike"),
            CardInstance(card_id="Strike"),
            CardInstance(card_id="Defend"),
            CardInstance(card_id="Defend"),
            CardInstance(card_id="Strike"),
        ]
        cm.draw_pile.cards = [
            CardInstance(card_id="Bash"),
            CardInstance(card_id="FlameBarrier"),
        ]
        cm.discard_pile.cards = []
        cm.exhaust_pile.cards = []
        cm._cards_drawn_this_turn = 5

        replay_debug = {
            "battle_required_cards_promoted": [],
            "battle_card_state_desync_turn": [],
        }
        turn_cards = [
            SimpleNamespace(turn=0, card_id="Bash", cost=2, upgraded=False),
            SimpleNamespace(turn=0, card_id="Flame Barrier", cost=2, upgraded=False),
        ]

        harness._reconcile_opening_hand_for_turn(
            cm,
            turn_cards,
            replay_debug,
            java_turn=0,
        )

        hand_ids = [card.card_id for card in cm.hand.cards]
        promoted_ids = [item["promoted_card_id"] for item in replay_debug["battle_required_cards_promoted"]]

        assert replay_debug["battle_opening_hand_reconciled"] is True
        assert Counter(promoted_ids) == Counter({"Bash": 1, "FlameBarrier": 1})
        assert "Bash" in hand_ids
        assert "FlameBarrier" in hand_ids
        assert len(replay_debug["battle_required_card_reconciliation_applied_by_turn"][0]) == 2

    def test_play_logged_battle_does_not_invent_missing_opening_hand_card(self) -> None:
        engine = RunEngine.create("PHASE29NOINVENT", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Strike", "Defend", "Strike"]
        engine.start_combat_with_monsters(["Cultist"])
        combat = engine.state.combat
        assert combat is not None
        cm = combat.state.card_manager
        assert cm is not None
        cm.hand.cards = [
            CardInstance(card_id="Strike"),
            CardInstance(card_id="Strike"),
            CardInstance(card_id="Defend"),
            CardInstance(card_id="Defend"),
            CardInstance(card_id="Strike"),
        ]
        cm.draw_pile.cards = [CardInstance(card_id="Defend")]
        cm.discard_pile.cards = []
        cm.exhaust_pile.cards = []
        cm._cards_drawn_this_turn = 5

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Cultist", ending_hp=0)],
            turn_count=1,
            player_end_hp=80,
            cards_played=[SimpleNamespace(turn=0, card_id="Bash", cost=2, upgraded=False)],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_draws_by_turn={0: [{"num_cards": 5}]},
            max_turns=2,
        )

        assert "battle_opening_hand_reconciled" not in result["debug"]
        assert result["debug"]["battle_unmatched_cards"][0]["card_id"] == "Bash"

    def test_opening_hand_reconciliation_can_source_from_discard_reshuffle(self) -> None:
        engine = RunEngine.create("PHASE50RESHUFFLEOPEN", ascension=0)
        engine.state.deck = ["Strike", "Defend", "FlameBarrier", "Strike", "Defend", "Strike"]
        engine.start_combat_with_monsters(["Cultist"])
        combat = engine.state.combat
        assert combat is not None
        cm = combat.state.card_manager
        assert cm is not None
        cm.hand.cards = [
            CardInstance(card_id="Strike"),
            CardInstance(card_id="Strike"),
            CardInstance(card_id="Defend"),
            CardInstance(card_id="Defend"),
            CardInstance(card_id="Strike"),
        ]
        cm.draw_pile.cards = [CardInstance(card_id="Strike")]
        cm.discard_pile.cards = [CardInstance(card_id="FlameBarrier")]
        cm.exhaust_pile.cards = []
        cm._cards_drawn_this_turn = 5

        replay_debug = {"battle_required_cards_promoted": []}
        turn_cards = [SimpleNamespace(turn=1, card_id="Flame Barrier", cost=2, upgraded=False)]

        harness._reconcile_opening_hand_for_turn(cm, turn_cards, replay_debug, java_turn=1)

        promoted = replay_debug["battle_required_card_reconciliation_applied_by_turn"][1][0]
        hand_ids = [card.card_id for card in cm.hand.cards]

        assert promoted["source"] == "discard_reshuffle"
        assert "FlameBarrier" in hand_ids

    def test_draw_reconciliation_can_source_from_discard_reshuffle_when_draw_budget_allows(self) -> None:
        engine = RunEngine.create("PHASE50RESHUFFLEDRAW", ascension=0)
        engine.state.deck = ["Strike", "Defend", "PommelStrike", "Strike", "Defend", "Strike"]
        engine.start_combat_with_monsters(["Cultist"])
        combat = engine.state.combat
        assert combat is not None
        cm = combat.state.card_manager
        assert cm is not None
        cm.hand.cards = [
            CardInstance(card_id="Strike"),
            CardInstance(card_id="Strike"),
            CardInstance(card_id="Defend"),
            CardInstance(card_id="Defend"),
            CardInstance(card_id="Strike"),
        ]
        cm.draw_pile.cards = [CardInstance(card_id="Strike")]
        cm.discard_pile.cards = [CardInstance(card_id="PommelStrike")]
        cm.exhaust_pile.cards = []
        cm._cards_drawn_this_turn = 5

        replay_debug = {"battle_required_cards_promoted": []}
        logged_card = SimpleNamespace(turn=1, card_id="Pommel Strike", cost=1, upgraded=False)

        remaining = harness._reconcile_missing_logged_card_from_draws(
            cm,
            logged_card,
            draw_budget_remaining=2,
            remaining_logged_cards=[logged_card],
            replay_debug=replay_debug,
            java_turn=1,
        )

        promoted = replay_debug["battle_required_card_reconciliation_applied_by_turn"][1][0]
        hand_ids = [card.card_id for card in cm.hand.cards]

        assert remaining == 1
        assert promoted["source"] == "discard_reshuffle"
        assert "PommelStrike" in hand_ids

    def test_same_turn_duplicate_pommel_rescue_promotes_discarded_demoted_copy(self) -> None:
        combat = _make_test_combat(["Inflame", "TrueGrit", "Dropkick", "Defend", "PommelStrike"])
        cm = combat.state.card_manager
        assert cm is not None
        cm.hand.cards = [
            CardInstance(card_id="Inflame"),
            CardInstance(card_id="TrueGrit"),
            CardInstance(card_id="Dropkick"),
            CardInstance(card_id="Defend"),
        ]
        cm.draw_pile.cards = []
        cm.discard_pile.cards = [CardInstance(card_id="PommelStrike")]
        cm.exhaust_pile.cards = []

        replay_debug = {
            "battle_required_cards_promoted": [],
            "battle_exhaust_events_by_turn": {
                1: [{"source_card_id": "Bloodletting", "exhausted_cards": [{"card_id": "bloodletting", "count": 1}]}]
            },
        }
        logged_card = SimpleNamespace(card_id="Pommel Strike", cost=1, upgraded=True)
        battle = SimpleNamespace(monsters=[SimpleNamespace(id="Shelled Parasite"), SimpleNamespace(id="FungiBeast")])

        promotion = harness._maybe_rescue_same_turn_duplicate_required_card(
            cm,
            logged_card,
            battle=battle,
            java_turn=1,
            replay_debug=replay_debug,
            remaining_logged_cards=[
                SimpleNamespace(card_id="Pommel Strike"),
                SimpleNamespace(card_id="Rage"),
                SimpleNamespace(card_id="True Grit"),
                SimpleNamespace(card_id="Dropkick"),
            ],
            next_turn_logged_cards=[SimpleNamespace(card_id="Uppercut")],
            candidate_sources=["discard_pile", "already_played_this_turn"],
            blockers=["discard_pile", "already_played_this_turn", "demoted_by_reconciliation"],
            flow_reason="same_turn_duplicate_demoted",
            duplicate_demand={"same_turn_logged_remaining_including_current": 1},
            protection_window={"next_turn_required_count": 0},
            demotion_chain={
                "states": [
                    {
                        "state": "demoted",
                        "turn": 0,
                        "trigger_card_id": "Uppercut",
                        "source": "draw",
                        "opening_hand": True,
                    },
                    {"state": "discarded", "turn": 1},
                ]
            },
        )

        assert promotion is not None
        assert promotion["source"] == "same_turn_duplicate_rescue"
        assert [card.card_id for card in cm.hand.cards].count("PommelStrike") == 1
        assert replay_debug["battle_same_turn_duplicate_rescue_by_turn"] == {
            1: [
                {
                    "java_turn": 1,
                    "card_id": "Pommel Strike",
                    "source_state": "discarded",
                    "trigger_card_id": "Uppercut",
                    "rescued_from": "discard_pile",
                }
            ]
        }

    def test_same_turn_duplicate_pommel_rescue_requires_strict_guards(self) -> None:
        logged_card = SimpleNamespace(card_id="Pommel Strike", cost=1, upgraded=True)
        def _make_kwargs() -> tuple[object, dict[str, object]]:
            combat = _make_test_combat(["Inflame", "TrueGrit", "Dropkick", "Defend", "PommelStrike"])
            cm = combat.state.card_manager
            assert cm is not None
            cm.hand.cards = [CardInstance(card_id="Inflame")]
            cm.draw_pile.cards = []
            cm.discard_pile.cards = [CardInstance(card_id="PommelStrike")]
            cm.exhaust_pile.cards = []
            return cm, {
                "battle": SimpleNamespace(monsters=[SimpleNamespace(id="Shelled Parasite"), SimpleNamespace(id="FungiBeast")]),
                "java_turn": 1,
                "replay_debug": {"battle_required_cards_promoted": [], "battle_exhaust_events_by_turn": {}},
                "remaining_logged_cards": [
                    SimpleNamespace(card_id="Pommel Strike"),
                    SimpleNamespace(card_id="Rage"),
                    SimpleNamespace(card_id="True Grit"),
                ],
                "next_turn_logged_cards": [SimpleNamespace(card_id="Uppercut")],
                "candidate_sources": ["discard_pile", "already_played_this_turn"],
                "blockers": ["discard_pile", "already_played_this_turn", "demoted_by_reconciliation"],
                "flow_reason": "same_turn_duplicate_demoted",
                "duplicate_demand": {"same_turn_logged_remaining_including_current": 1},
                "protection_window": {"next_turn_required_count": 0},
                "demotion_chain": {
                    "states": [
                        {"state": "demoted", "turn": 0, "trigger_card_id": "Uppercut"},
                        {"state": "discarded", "turn": 1},
                    ]
                },
            }

        cm, base_kwargs = _make_kwargs()
        assert harness._maybe_rescue_same_turn_duplicate_required_card(cm, logged_card, **base_kwargs) is not None
        cm, base_kwargs = _make_kwargs()
        assert harness._maybe_rescue_same_turn_duplicate_required_card(
            cm,
            SimpleNamespace(card_id="Rage", cost=0, upgraded=False),
            **base_kwargs,
        ) is None
        cm, base_kwargs = _make_kwargs()
        assert harness._maybe_rescue_same_turn_duplicate_required_card(
            cm,
            logged_card,
            **{**base_kwargs, "flow_reason": None},
        ) is None
        cm, base_kwargs = _make_kwargs()
        assert harness._maybe_rescue_same_turn_duplicate_required_card(
            cm,
            logged_card,
            **{**base_kwargs, "protection_window": {"next_turn_required_count": 1}},
        ) is None
        cm, base_kwargs = _make_kwargs()
        assert harness._maybe_rescue_same_turn_duplicate_required_card(
            cm,
            logged_card,
            **{
                **base_kwargs,
                "battle": SimpleNamespace(monsters=[SimpleNamespace(id="BookOfStabbing")]),
            },
        ) is None

    def test_true_grit_runtime_exhausts_hand_card_instead_of_discarding(self) -> None:
        combat = _make_test_combat(["TrueGrit", "Strike", "Defend"])
        cm = combat.state.card_manager
        assert cm is not None
        true_grit = CardInstance(card_id="TrueGrit")
        strike = CardInstance(card_id="Strike")
        defend = CardInstance(card_id="Defend")
        cm.hand.cards = [true_grit, strike, defend]
        cm.draw_pile.cards = []
        cm.discard_pile.cards = []
        cm.exhaust_pile.cards = []

        effects = get_card_effects(true_grit)
        for effect in effects:
            effect.execute(combat.state, true_grit, combat.state.player, None)

        hand_ids = [card.card_id for card in cm.hand.cards]
        exhaust_ids = [card.card_id for card in cm.exhaust_pile.cards]
        discard_ids = [card.card_id for card in cm.discard_pile.cards]

        assert len(exhaust_ids) == 1
        assert exhaust_ids[0] in {"Strike", "Defend"}
        assert exhaust_ids[0] not in discard_ids
        assert Counter(hand_ids) == Counter({"TrueGrit": 1, "Strike": 1, "Defend": 1}) - Counter(exhaust_ids)

    def test_true_grit_replay_target_avoids_current_and_next_turn_required_cards(self) -> None:
        true_grit = CardInstance(card_id="TrueGrit")
        pommel = CardInstance(card_id="PommelStrike")
        uppercut = CardInstance(card_id="Uppercut")
        defend = CardInstance(card_id="Defend")
        hand = [true_grit, pommel, uppercut, defend]

        target_uuid = harness._select_true_grit_replay_target_uuid(
            hand,
            true_grit,
            remaining_logged_cards=[SimpleNamespace(card_id="Pommel Strike")],
            next_turn_logged_cards=[SimpleNamespace(card_id="Uppercut")],
        )

        assert target_uuid == str(defend.uuid)

    def test_true_grit_replay_target_preserves_future_unique_required_card_when_alternative_exists(self) -> None:
        true_grit = CardInstance(card_id="TrueGrit")
        uppercut = CardInstance(card_id="Uppercut")
        defend = CardInstance(card_id="Defend")
        hand = [true_grit, uppercut, defend]
        card_manager = SimpleNamespace(
            draw_pile=SimpleNamespace(cards=[]),
            discard_pile=SimpleNamespace(cards=[]),
        )

        target_uuid = harness._select_true_grit_replay_target_uuid(
            hand,
            true_grit,
            remaining_logged_cards=[],
            next_turn_logged_cards=[],
            future_turn_logged_cards=[SimpleNamespace(card_id="Uppercut")],
            card_manager=card_manager,
            enable_future_required_preservation=True,
        )

        assert target_uuid == str(defend.uuid)

    def test_true_grit_replay_target_keeps_current_behavior_when_no_alternative_exists(self) -> None:
        true_grit = CardInstance(card_id="TrueGrit")
        uppercut = CardInstance(card_id="Uppercut")
        hand = [true_grit, uppercut]
        card_manager = SimpleNamespace(
            draw_pile=SimpleNamespace(cards=[]),
            discard_pile=SimpleNamespace(cards=[]),
        )

        target_uuid = harness._select_true_grit_replay_target_uuid(
            hand,
            true_grit,
            remaining_logged_cards=[],
            next_turn_logged_cards=[],
            future_turn_logged_cards=[SimpleNamespace(card_id="Uppercut")],
            card_manager=card_manager,
            enable_future_required_preservation=True,
        )

        assert target_uuid == str(uppercut.uuid)

    def test_true_grit_future_required_preservation_requires_non_required_alternative(self) -> None:
        true_grit = CardInstance(card_id="TrueGrit")
        uppercut = CardInstance(card_id="Uppercut")
        wild_strike = CardInstance(card_id="WildStrike")
        hand = [true_grit, uppercut, wild_strike]
        card_manager = SimpleNamespace(
            draw_pile=SimpleNamespace(cards=[]),
            discard_pile=SimpleNamespace(cards=[]),
        )

        assert harness._has_true_grit_non_required_alternative(
            hand,
            true_grit,
            remaining_logged_cards=[],
            next_turn_logged_cards=[SimpleNamespace(card_id="Wild Strike")],
            future_turn_logged_cards=[SimpleNamespace(card_id="Uppercut")],
            card_manager=card_manager,
        ) is False

    def test_true_grit_future_required_preservation_detects_safe_alternative(self) -> None:
        true_grit = CardInstance(card_id="TrueGrit")
        uppercut = CardInstance(card_id="Uppercut")
        defend = CardInstance(card_id="Defend")
        hand = [true_grit, uppercut, defend]
        card_manager = SimpleNamespace(
            draw_pile=SimpleNamespace(cards=[]),
            discard_pile=SimpleNamespace(cards=[]),
        )

        assert harness._has_true_grit_non_required_alternative(
            hand,
            true_grit,
            remaining_logged_cards=[],
            next_turn_logged_cards=[],
            future_turn_logged_cards=[SimpleNamespace(card_id="Uppercut")],
            card_manager=card_manager,
        ) is True

    def test_select_hand_card_to_demote_preserves_next_turn_required_cards(self) -> None:
        hand = [
            CardInstance(card_id="FlameBarrier"),
            CardInstance(card_id="PommelStrike"),
            CardInstance(card_id="ShrugItOff"),
        ]

        demote_idx = harness._select_hand_card_to_demote(
            hand,
            remaining_logged_cards=[],
            next_turn_logged_cards=[SimpleNamespace(card_id="Pommel Strike")],
        )

        assert demote_idx == 2
        assert hand[demote_idx].card_id == "ShrugItOff"

    def test_classify_missing_card_from_prebattle_state_distinguishes_upstream_gap(self) -> None:
        logged_card = SimpleNamespace(card_id="Rage")

        missing_from_prebattle = harness._classify_missing_card_from_prebattle_state(
            {},
            {"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            logged_card,
        )
        lost_between_start_and_combat = harness._classify_missing_card_from_prebattle_state(
            {"rage": 1},
            {"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            logged_card,
        )

        assert missing_from_prebattle == "missing_from_prebattle_state"
        assert lost_between_start_and_combat == "lost_between_prebattle_state_and_combat_start"

    def test_reconcile_live_victory_turns_allows_proxy_terminal_turn_with_logged_cards(self) -> None:
        summary = {
            "turns": 1,
            "player_end_hp": 67,
            "monster_end_hp": [0, 0],
        }
        replay_debug = {
            "battle_proxy_monster_resolution_used": True,
            "player_phase_terminal_after_turn": 1,
            "python_cards_played_by_turn": {
                1: [
                    {"logged_card_id": "Uppercut", "match_type": "exact", "fallback": False},
                    {"logged_card_id": "Bash", "match_type": "exact", "fallback": False},
                ]
            },
        }

        reconciled = harness._reconcile_live_victory_turns_from_outcomes(summary, replay_debug)

        assert reconciled["turns"] == 2
        assert replay_debug["battle_live_victory_turn_reconciled"] is True
        assert replay_debug["battle_live_victory_terminal_turn"] == 2

    def test_reconcile_live_victory_turns_skips_proxy_terminal_turn_with_fallback_only(self) -> None:
        summary = {
            "turns": 1,
            "player_end_hp": 51,
            "monster_end_hp": [0],
        }
        replay_debug = {
            "battle_proxy_monster_resolution_used": True,
            "player_phase_terminal_after_turn": 1,
            "python_cards_played_by_turn": {
                1: [
                    {"logged_card_id": None, "fallback": True},
                ]
            },
        }

        reconciled = harness._reconcile_live_victory_turns_from_outcomes(summary, replay_debug)

        assert reconciled["turns"] == 1
        assert "battle_live_victory_turn_reconciled" not in replay_debug

    def test_reconcile_live_victory_turns_preserves_legacy_terminal_index_when_unmatched_cards_exist(self) -> None:
        summary = {
            "turns": 1,
            "player_end_hp": 67,
            "monster_end_hp": [0, 0],
        }
        replay_debug = {
            "battle_proxy_monster_resolution_used": True,
            "battle_terminal_reason": "logged_turns_exhausted",
            "battle_unmatched_cards": [{"turn": 1, "card_id": "Pommel Strike"}],
            "player_phase_terminal_after_turn": 2,
            "python_cards_played_by_turn": {
                2: [
                    {"logged_card_id": "Uppercut", "match_type": "exact", "fallback": False},
                    {"logged_card_id": "Bash", "match_type": "exact", "fallback": False},
                ]
            },
            "python_monster_outcomes_by_turn": {
                2: {"monsters": [{"alive": False, "hp": 0}, {"alive": False, "hp": 0}]}
            },
        }

        reconciled = harness._reconcile_live_victory_turns_from_outcomes(summary, replay_debug)

        assert reconciled["turns"] == 2
        assert replay_debug["battle_live_victory_turn_reconciled"] is True
        assert replay_debug["battle_live_victory_terminal_turn"] == 2

    def test_reconcile_live_victory_turns_allows_actual_monster_clear_without_logged_turn_exhausted_reason(self) -> None:
        summary = {
            "turns": 3,
            "player_end_hp": 41,
            "monster_end_hp": [0, 0],
        }
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "player_phase_terminal_after_turn": 4,
            "python_monster_outcomes_by_turn": {
                4: {"monsters": [{"alive": False, "hp": 0}, {"alive": False, "hp": 0}]},
            },
            "python_cards_played_by_turn": {
                4: [
                    {"logged_card_id": "Bash", "match_type": "temporary_upgrade_match", "fallback": False},
                ]
            },
            "battle_unmatched_cards": [
                {"turn": 4, "card_id": "Wild Strike", "reason": "no_alive_monster_target"},
            ],
        }

        reconciled = harness._reconcile_live_victory_turns_from_outcomes(summary, replay_debug)

        assert reconciled["turns"] == 4
        assert replay_debug["battle_live_victory_turn_reconciled"] is True
        assert replay_debug["battle_live_victory_terminal_turn"] == 4

    def test_reconcile_live_victory_turns_keeps_phase91_darkling_post_regrow_player_phase(self) -> None:
        summary = {
            "floor": 38,
            "turns": 3,
            "player_end_hp": 33,
            "monster_end_hp": [0, 0, 0],
            "monster_ids": ["Darkling", "Darkling", "Darkling"],
        }
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "battle_darkling_replay_move_resolution_by_turn": {0: [{"java_turn": 0}]},
            "battle_darkling_regrow_resolution_by_turn": {2: [{"java_turn": 2, "mode": "reincarnate"}]},
            "java_turn_count": 4,
            "player_phase_terminal_after_turn": 4,
            "python_monster_outcomes_by_turn": {
                3: {"monsters": [{"alive": False, "hp": 0}, {"alive": False, "hp": 0}, {"alive": False, "hp": 0}]}
            },
            "python_cards_played_by_turn": {
                4: [
                    {"logged_card_id": "True Grit", "match_type": "temporary_upgrade_match", "fallback": False},
                ]
            },
        }

        reconciled = harness._reconcile_live_victory_turns_from_outcomes(dict(summary), replay_debug)

        assert reconciled["turns"] == 4
        assert replay_debug["battle_live_victory_turn_reconciled"] is True
        assert replay_debug["battle_live_victory_terminal_turn"] == 4
        assert replay_debug["battle_darkling_terminal_turn_reconcile"]["mode"] == "post_regrow_player_phase"

        non_f38_summary = dict(summary) | {"floor": 35}
        non_f38_debug = {
            key: (value.copy() if isinstance(value, dict) else value)
            for key, value in replay_debug.items()
            if key != "battle_darkling_terminal_turn_reconcile"
        }
        non_f38_debug.pop("battle_live_victory_turn_reconciled", None)
        non_f38_debug.pop("battle_live_victory_terminal_turn", None)
        non_f38_reconciled = harness._reconcile_live_victory_turns_from_outcomes(non_f38_summary, non_f38_debug)
        assert non_f38_reconciled["turns"] == 3

    def test_reconcile_live_victory_turns_keeps_same_id_louse_terminal_closure_on_raw_turn_index(self) -> None:
        summary = {
            "turns": 1,
            "player_end_hp": 78,
            "monster_end_hp": [0, 0],
            "monster_ids": ["FuzzyLouseDefensive", "FuzzyLouseDefensive"],
        }
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "player_phase_terminal_after_turn": 1,
            "python_cards_played_by_turn": {
                1: [
                    {"logged_card_id": "Strike_R", "match_type": "exact", "fallback": False},
                    {"logged_card_id": "Strike_R", "match_type": "exact", "fallback": False},
                ]
            },
            "python_monster_outcomes_by_turn": {
                1: {"monsters": [{"alive": False, "hp": 0}, {"alive": False, "hp": 0}]},
            },
        }

        reconciled = harness._reconcile_live_victory_turns_from_outcomes(summary, replay_debug)

        assert reconciled["turns"] == 1
        assert replay_debug["battle_live_victory_turn_reconciled"] is True
        assert replay_debug["battle_live_victory_terminal_turn"] == 1

    def test_reconcile_live_victory_turns_keeps_unique_id_survivor_terminal_closure_on_raw_turn_index(self) -> None:
        summary = {
            "turns": 1,
            "player_end_hp": 67,
            "monster_end_hp": [0, 0],
            "monster_ids": ["AcidSlime_S", "SpikeSlime_M"],
        }
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "battle_terminal_reason": "logged_turns_exhausted",
            "player_phase_terminal_after_turn": 2,
            "battle_turn_fallback_counts": {0: 0, 1: 0, 2: 0},
            "battle_logged_intent_roster_closure_by_turn": {
                2: [{"java_turn": 2, "mode": "unique_id_disappearance", "monster_id": "AcidSlime_S"}],
            },
            "battle_unique_id_target_rebind_by_turn": {
                2: [{"java_turn": 2, "card_id": "Pommel Strike"}],
            },
            "battle_unique_id_survivor_terminal_closure_by_turn": {
                2: [{"java_turn": 2, "survivor_monster_id": "SpikeSlime_M"}],
            },
            "battle_monster_terminal_candidate_by_turn": {
                2: {"all_monsters_dead": True},
            },
            "python_cards_played_by_turn": {
                2: [
                    {
                        "logged_card_id": "Pommel Strike",
                        "runtime_card_id": "PommelStrike",
                        "match_type": "exact",
                        "target_idx": 1,
                        "fallback": False,
                    },
                ]
            },
            "python_monster_outcomes_by_turn": {
                2: {"monsters": [{"alive": False, "hp": 0}, {"alive": False, "hp": 0}]},
            },
        }

        reconciled = harness._reconcile_live_victory_turns_from_outcomes(summary, replay_debug)

        assert reconciled["turns"] == 2
        assert replay_debug["battle_live_victory_turn_reconciled"] is True
        assert replay_debug["battle_live_victory_terminal_turn"] == 2

    def test_reconcile_live_victory_turns_keeps_same_id_sentry_terminal_closure_on_raw_turn_index(self) -> None:
        summary = {
            "turns": 7,
            "player_end_hp": 13,
            "monster_end_hp": [0, 0, 0],
            "monster_ids": ["Sentry", "Sentry", "Sentry"],
        }
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "battle_terminal_reason": "logged_turns_exhausted",
            "player_phase_terminal_after_turn": 6,
            "battle_live_victory_terminal_turn": 7,
            "battle_same_id_sentry_intent_lane_by_turn": {
                0: [{"java_turn": 0, "monster_idx": 1, "monster_id": "Sentry", "assigned_intent": "ATTACK"}],
                5: [{"java_turn": 5, "monster_idx": 2, "monster_id": "Sentry", "assigned_intent": "DEBUFF"}],
            },
            "python_cards_played_by_turn": {
                6: [
                    {
                        "logged_card_id": "Pommel Strike",
                        "runtime_card_id": "PommelStrike",
                        "match_type": "exact",
                        "target_idx": 2,
                        "fallback": False,
                    },
                ]
            },
            "python_monster_outcomes_by_turn": {
                6: {"monsters": [{"alive": False, "hp": 0}, {"alive": False, "hp": 0}, {"alive": False, "hp": 0}]},
            },
            "battle_monster_terminal_candidate_by_turn": {
                6: {"all_monsters_dead": True},
            },
        }

        reconciled = harness._reconcile_live_victory_turns_from_outcomes(summary, replay_debug)

        assert reconciled["turns"] == 6
        assert replay_debug["battle_live_victory_turn_reconciled"] is True
        assert replay_debug["battle_live_victory_terminal_turn"] == 6

    def test_reconcile_live_victory_turns_requires_same_id_sentry_guards(self) -> None:
        summary = {
            "turns": 7,
            "player_end_hp": 13,
            "monster_end_hp": [0, 0, 0],
            "monster_ids": ["Sentry", "Sentry", "Sentry"],
        }
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "battle_terminal_reason": "logged_turns_exhausted",
            "player_phase_terminal_after_turn": 6,
            "battle_live_victory_terminal_turn": 7,
            "battle_same_id_sentry_intent_lane_by_turn": {
                0: [{"java_turn": 0, "monster_idx": 1, "monster_id": "Sentry", "assigned_intent": "ATTACK"}],
            },
            "python_cards_played_by_turn": {
                6: [
                    {
                        "logged_card_id": None,
                        "runtime_card_id": "Strike",
                        "match_type": "fallback_attack",
                        "target_idx": 2,
                        "fallback": True,
                    },
                ]
            },
            "python_monster_outcomes_by_turn": {
                6: {"monsters": [{"alive": False, "hp": 0}, {"alive": False, "hp": 0}, {"alive": False, "hp": 0}]},
            },
            "battle_monster_terminal_candidate_by_turn": {
                6: {"all_monsters_dead": True},
            },
        }

        reconciled = harness._reconcile_live_victory_turns_from_outcomes(summary, replay_debug)

        assert reconciled["turns"] == 7
        assert replay_debug["battle_live_victory_terminal_turn"] == 6

    def test_reconcile_battle_summary_hp_from_floor_snapshot_allows_same_id_louse_terminal_closure(self) -> None:
        summary = {
            "turns": 1,
            "player_end_hp": 78,
            "monster_end_hp": [0, 0],
            "monster_ids": ["FuzzyLouseDefensive", "FuzzyLouseDefensive"],
        }
        snapshot = SimpleNamespace(hp=79)
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "player_phase_terminal_after_turn": 1,
            "battle_player_attack_targets_by_turn": {
                0: [
                    {"target_idx": 1, "logged_card_id": "Pommel Strike"},
                    {"target_idx": 1, "logged_card_id": "Strike_R"},
                ]
            },
            "battle_monster_terminal_candidate_by_turn": {
                1: {"all_monsters_dead": True},
            },
        }

        reconciled = harness._maybe_reconcile_battle_summary_hp_from_floor_snapshot(
            summary,
            snapshot,
            replay_debug,
        )

        assert reconciled is summary
        assert reconciled["player_end_hp"] == 79

    def test_reconcile_battle_summary_hp_from_floor_snapshot_allows_unique_id_survivor_terminal_closure(self) -> None:
        summary = {
            "turns": 2,
            "player_end_hp": 67,
            "monster_end_hp": [0, 0],
            "monster_ids": ["AcidSlime_S", "SpikeSlime_M"],
        }
        snapshot = SimpleNamespace(hp=77)
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "battle_terminal_reason": "logged_turns_exhausted",
            "player_phase_terminal_after_turn": 2,
            "battle_turn_fallback_counts": {0: 0, 1: 0, 2: 0},
            "battle_logged_intent_roster_closure_by_turn": {
                2: [{"java_turn": 2, "mode": "unique_id_disappearance", "monster_id": "AcidSlime_S"}],
            },
            "battle_unique_id_target_rebind_by_turn": {
                2: [{"java_turn": 2, "card_id": "Pommel Strike"}],
            },
            "battle_unique_id_survivor_terminal_closure_by_turn": {
                2: [{"java_turn": 2, "survivor_monster_id": "SpikeSlime_M"}],
            },
            "battle_monster_terminal_candidate_by_turn": {
                2: {"all_monsters_dead": True},
            },
            "python_cards_played_by_turn": {
                2: [
                    {
                        "logged_card_id": "Pommel Strike",
                        "runtime_card_id": "PommelStrike",
                        "match_type": "exact",
                        "target_idx": 1,
                        "fallback": False,
                    },
                ]
            },
        }

        reconciled = harness._maybe_reconcile_battle_summary_hp_from_floor_snapshot(
            summary,
            snapshot,
            replay_debug,
        )

        assert reconciled is summary
        assert reconciled["player_end_hp"] == 77

    def test_reconcile_battle_summary_hp_from_floor_snapshot_allows_same_id_triplet_fungi_terminal_closure(self) -> None:
        summary = {
            "room_type": "EventRoom",
            "turns": 3,
            "player_end_hp": 31,
            "monster_end_hp": [0, 0, 0],
            "monster_ids": ["FungiBeast", "FungiBeast", "FungiBeast"],
        }
        snapshot = SimpleNamespace(hp=54)
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "player_phase_terminal_after_turn": 2,
            "battle_turn_fallback_counts": {0: 0, 1: 0, 2: 0},
            "battle_same_id_triplet_fungi_terminal_closure_by_turn": {
                2: [{"java_turn": 2, "monster_id": "FungiBeast", "survivor_idx": 1, "survivor_hp_before_closure": 5}],
            },
            "battle_monster_terminal_candidate_by_turn": {
                2: {"all_monsters_dead": True},
            },
            "python_cards_played_by_turn": {
                2: [
                    {
                        "logged_card_id": "Wild Strike",
                        "runtime_card_id": "WildStrike",
                        "match_type": "exact",
                        "target_idx": 1,
                        "fallback": False,
                    },
                ]
            },
        }

        reconciled = harness._maybe_reconcile_battle_summary_hp_from_floor_snapshot(
            summary,
            snapshot,
            replay_debug,
        )

        assert reconciled is summary
        assert reconciled["player_end_hp"] == 54

    def test_reconcile_battle_summary_hp_from_floor_snapshot_allows_same_id_sentry_terminal_closure(self) -> None:
        summary = {
            "room_type": "MonsterRoomElite",
            "turns": 6,
            "player_end_hp": 13,
            "monster_end_hp": [0, 0, 0],
            "monster_ids": ["Sentry", "Sentry", "Sentry"],
        }
        snapshot = SimpleNamespace(hp=29)
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "battle_terminal_reason": "logged_turns_exhausted",
            "player_phase_terminal_after_turn": 6,
            "battle_live_victory_terminal_turn": 7,
            "battle_same_id_sentry_intent_lane_by_turn": {
                0: [{"java_turn": 0, "monster_idx": 1, "monster_id": "Sentry", "assigned_intent": "ATTACK"}],
                5: [{"java_turn": 5, "monster_idx": 2, "monster_id": "Sentry", "assigned_intent": "DEBUFF"}],
            },
            "battle_monster_terminal_candidate_by_turn": {
                6: {"all_monsters_dead": True},
            },
            "python_cards_played_by_turn": {
                6: [
                    {
                        "logged_card_id": "Pommel Strike",
                        "runtime_card_id": "PommelStrike",
                        "match_type": "exact",
                        "target_idx": 2,
                        "fallback": False,
                    },
                ]
            },
        }

        reconciled = harness._maybe_reconcile_battle_summary_hp_from_floor_snapshot(
            summary,
            snapshot,
            replay_debug,
        )

        assert reconciled is summary
        assert reconciled["player_end_hp"] == 29

    def test_frozen_rage_mixed_encounter_hp_snapshot_candidate_reconciles_floor_snapshot_hp(self) -> None:
        summary = {
            "turns": 2,
            "player_end_hp": 67,
            "monster_end_hp": [0, 0],
            "monster_ids": ["Shelled Parasite", "FungiBeast"],
        }
        snapshot = SimpleNamespace(hp=70)
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "java_turn_count": 2,
            "battle_same_turn_duplicate_rescue_by_turn": {
                1: [
                    {
                        "java_turn": 1,
                        "card_id": "Pommel Strike",
                        "source_state": "discarded",
                        "trigger_card_id": "Uppercut",
                        "rescued_from": "discard_pile",
                    }
                ]
            },
            "battle_unmatched_cards": [
                {"turn": 1, "card_id": "Rage", "cost": 0, "upgraded": False, "reason": "no_match_in_hand"},
                {"turn": 2, "card_id": "Bash", "cost": 2, "upgraded": True, "reason": "no_alive_monster_target"},
            ],
            "battle_java_recorder_gap_reason": {
                1: [{"card_id": "Rage", "reason": "recorder_missing_per_floor_deck_truth"}],
                2: [{"card_id": "Bash", "reason": "recorder_missing_per_floor_deck_truth"}],
            },
            "battle_required_card_candidate_sources_by_turn": {
                1: [{"card_id": "Rage", "candidate_sources": ["not_in_battle_multiset"]}],
                2: [{"card_id": "Bash", "candidate_sources": ["not_in_battle_multiset"]}],
            },
            "battle_missing_card_multiset_reason_by_turn": {
                1: [{"card_id": "Rage", "reason": "missing_from_combat_start_multiset"}],
                2: [{"card_id": "Bash", "reason": "lost_during_turn_effect"}],
            },
            "python_cards_played_by_turn": {
                0: [
                    {
                        "logged_card_id": "Uppercut",
                        "runtime_card_id": "Uppercut",
                        "match_type": "exact",
                        "fallback": False,
                    },
                ],
                1: [
                    {
                        "logged_card_id": "Pommel Strike",
                        "runtime_card_id": "PommelStrike",
                        "match_type": "exact",
                        "fallback": False,
                    },
                ],
                2: [
                    {
                        "logged_card_id": "Uppercut",
                        "runtime_card_id": "Uppercut",
                        "match_type": "exact",
                        "fallback": False,
                    },
                ],
            },
        }

        reconciled = harness._maybe_reconcile_battle_summary_hp_from_floor_snapshot(
            summary,
            snapshot,
            replay_debug,
        )

        assert reconciled is summary
        assert reconciled["player_end_hp"] == 70

    def test_frozen_rage_mixed_encounter_hp_snapshot_candidate_requires_all_guards(self) -> None:
        summary = {
            "turns": 2,
            "player_end_hp": 67,
            "monster_end_hp": [0, 0],
            "monster_ids": ["Shelled Parasite", "FungiBeast"],
        }
        base_replay_debug = {
            "battle_terminal_monster_clear": True,
            "java_turn_count": 2,
            "battle_same_turn_duplicate_rescue_by_turn": {
                1: [
                    {
                        "java_turn": 1,
                        "card_id": "Pommel Strike",
                        "source_state": "discarded",
                        "trigger_card_id": "Uppercut",
                        "rescued_from": "discard_pile",
                    }
                ]
            },
            "battle_unmatched_cards": [
                {"turn": 1, "card_id": "Rage", "cost": 0, "upgraded": False, "reason": "no_match_in_hand"},
                {"turn": 2, "card_id": "Bash", "cost": 2, "upgraded": True, "reason": "no_alive_monster_target"},
            ],
            "battle_java_recorder_gap_reason": {
                1: [{"card_id": "Rage", "reason": "recorder_missing_per_floor_deck_truth"}],
                2: [{"card_id": "Bash", "reason": "recorder_missing_per_floor_deck_truth"}],
            },
            "battle_required_card_candidate_sources_by_turn": {
                1: [{"card_id": "Rage", "candidate_sources": ["not_in_battle_multiset"]}],
                2: [{"card_id": "Bash", "candidate_sources": ["not_in_battle_multiset"]}],
            },
            "battle_missing_card_multiset_reason_by_turn": {
                1: [{"card_id": "Rage", "reason": "missing_from_combat_start_multiset"}],
                2: [{"card_id": "Bash", "reason": "lost_during_turn_effect"}],
            },
            "python_cards_played_by_turn": {
                0: [{"logged_card_id": "Uppercut", "runtime_card_id": "Uppercut", "match_type": "exact", "fallback": False}],
                1: [{"logged_card_id": "Pommel Strike", "runtime_card_id": "PommelStrike", "match_type": "exact", "fallback": False}],
                2: [{"logged_card_id": "Uppercut", "runtime_card_id": "Uppercut", "match_type": "exact", "fallback": False}],
            },
        }

        assert harness._is_frozen_rage_mixed_encounter_hp_snapshot_candidate(summary, base_replay_debug) is True

        missing_rescue = dict(base_replay_debug)
        missing_rescue["battle_same_turn_duplicate_rescue_by_turn"] = {}
        assert harness._is_frozen_rage_mixed_encounter_hp_snapshot_candidate(summary, missing_rescue) is False

        wrong_unmatched = dict(base_replay_debug)
        wrong_unmatched["battle_unmatched_cards"] = [base_replay_debug["battle_unmatched_cards"][0]]
        assert harness._is_frozen_rage_mixed_encounter_hp_snapshot_candidate(summary, wrong_unmatched) is False

        wrong_gap = dict(base_replay_debug)
        wrong_gap["battle_java_recorder_gap_reason"] = {}
        assert harness._is_frozen_rage_mixed_encounter_hp_snapshot_candidate(summary, wrong_gap) is False

        fallback_turn = dict(base_replay_debug)
        fallback_turn["python_cards_played_by_turn"] = {
            **base_replay_debug["python_cards_played_by_turn"],
            2: [{"logged_card_id": None, "runtime_card_id": "Strike", "match_type": "fallback_attack", "fallback": True}],
        }
        assert harness._is_frozen_rage_mixed_encounter_hp_snapshot_candidate(summary, fallback_turn) is False

        wrong_encounter = dict(base_replay_debug)
        wrong_summary = dict(summary)
        wrong_summary["monster_ids"] = ["ShellParasite"]
        wrong_summary["monster_end_hp"] = [0]
        assert harness._is_frozen_rage_mixed_encounter_hp_snapshot_candidate(wrong_summary, wrong_encounter) is False

    def test_single_bookofstabbing_frozen_rage_hp_snapshot_candidate_reconciles_floor_snapshot_hp(self) -> None:
        summary = {
            "turns": 3,
            "player_end_hp": 57,
            "monster_end_hp": [0],
            "monster_ids": ["BookOfStabbing"],
        }
        snapshot = SimpleNamespace(hp=64)
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "java_turn_count": 3,
            "battle_unmatched_cards": [
                {"turn": 1, "card_id": "Rage", "cost": 0, "upgraded": False, "reason": "no_match_in_hand"},
                {"turn": 3, "card_id": "Dropkick", "cost": 1, "upgraded": False, "reason": "no_alive_monster_target"},
            ],
            "battle_java_recorder_gap_reason": {
                1: [{"card_id": "Rage", "reason": "recorder_missing_per_floor_deck_truth"}],
                3: [{"card_id": "Dropkick", "reason": "normalization_gap"}],
            },
            "battle_required_card_candidate_sources_by_turn": {
                1: [{"card_id": "Rage", "candidate_sources": ["not_in_battle_multiset"]}],
                3: [{"card_id": "Dropkick", "candidate_sources": ["not_in_battle_multiset"]}],
            },
            "battle_missing_card_multiset_reason_by_turn": {
                1: [{"card_id": "Rage", "reason": "missing_from_combat_start_multiset"}],
                3: [{"card_id": "Dropkick", "reason": "lost_during_turn_effect"}],
            },
            "python_cards_played_by_turn": {
                0: [{"logged_card_id": "Inflame", "runtime_card_id": "Inflame", "match_type": "exact", "fallback": False}],
                1: [{"logged_card_id": "Bash", "runtime_card_id": "Bash", "match_type": "temporary_upgrade_match", "fallback": False}],
                2: [{"logged_card_id": "Immolate", "runtime_card_id": "Immolate", "match_type": "exact", "fallback": False}],
                3: [
                    {
                        "logged_card_id": "Pommel Strike",
                        "runtime_card_id": "PommelStrike",
                        "match_type": "exact",
                        "target_idx": 0,
                        "fallback": False,
                    }
                ],
            },
        }

        reconciled = harness._maybe_reconcile_battle_summary_hp_from_floor_snapshot(
            summary,
            snapshot,
            replay_debug,
        )

        assert reconciled is summary
        assert reconciled["player_end_hp"] == 64

    def test_single_bookofstabbing_frozen_rage_hp_snapshot_candidate_requires_all_guards(self) -> None:
        summary = {
            "turns": 3,
            "player_end_hp": 57,
            "monster_end_hp": [0],
            "monster_ids": ["BookOfStabbing"],
        }
        base_replay_debug = {
            "battle_terminal_monster_clear": True,
            "java_turn_count": 3,
            "battle_unmatched_cards": [
                {"turn": 1, "card_id": "Rage", "cost": 0, "upgraded": False, "reason": "no_match_in_hand"},
                {"turn": 3, "card_id": "Dropkick", "cost": 1, "upgraded": False, "reason": "no_alive_monster_target"},
            ],
            "battle_java_recorder_gap_reason": {
                1: [{"card_id": "Rage", "reason": "recorder_missing_per_floor_deck_truth"}],
                3: [{"card_id": "Dropkick", "reason": "normalization_gap"}],
            },
            "battle_required_card_candidate_sources_by_turn": {
                1: [{"card_id": "Rage", "candidate_sources": ["not_in_battle_multiset"]}],
                3: [{"card_id": "Dropkick", "candidate_sources": ["not_in_battle_multiset"]}],
            },
            "battle_missing_card_multiset_reason_by_turn": {
                1: [{"card_id": "Rage", "reason": "missing_from_combat_start_multiset"}],
                3: [{"card_id": "Dropkick", "reason": "lost_during_turn_effect"}],
            },
            "python_cards_played_by_turn": {
                0: [{"logged_card_id": "Inflame", "runtime_card_id": "Inflame", "match_type": "exact", "fallback": False}],
                1: [{"logged_card_id": "Bash", "runtime_card_id": "Bash", "match_type": "temporary_upgrade_match", "fallback": False}],
                2: [{"logged_card_id": "Immolate", "runtime_card_id": "Immolate", "match_type": "exact", "fallback": False}],
                3: [
                    {
                        "logged_card_id": "Pommel Strike",
                        "runtime_card_id": "PommelStrike",
                        "match_type": "exact",
                        "target_idx": 0,
                        "fallback": False,
                    }
                ],
            },
        }

        assert harness._is_single_bookofstabbing_frozen_rage_hp_snapshot_candidate(summary, base_replay_debug) is True

        wrong_unmatched = dict(base_replay_debug)
        wrong_unmatched["battle_unmatched_cards"] = [base_replay_debug["battle_unmatched_cards"][0]]
        assert harness._is_single_bookofstabbing_frozen_rage_hp_snapshot_candidate(summary, wrong_unmatched) is False

        wrong_gap = dict(base_replay_debug)
        wrong_gap["battle_java_recorder_gap_reason"] = {1: [{"card_id": "Rage", "reason": "recorder_missing_per_floor_deck_truth"}]}
        assert harness._is_single_bookofstabbing_frozen_rage_hp_snapshot_candidate(summary, wrong_gap) is False

        wrong_terminal_play = dict(base_replay_debug)
        wrong_terminal_play["python_cards_played_by_turn"] = {
            **base_replay_debug["python_cards_played_by_turn"],
            3: [{"logged_card_id": "Strike_R", "runtime_card_id": "Strike", "match_type": "exact", "target_idx": 0, "fallback": False}],
        }
        assert harness._is_single_bookofstabbing_frozen_rage_hp_snapshot_candidate(summary, wrong_terminal_play) is False

        wrong_summary = dict(summary)
        wrong_summary["monster_ids"] = ["SnakePlant"]
        assert harness._is_single_bookofstabbing_frozen_rage_hp_snapshot_candidate(wrong_summary, base_replay_debug) is False

    def test_single_snakeplant_frozen_rage_hp_snapshot_candidate_reconciles_floor_snapshot_hp(self) -> None:
        summary = {
            "turns": 1,
            "player_end_hp": 58,
            "monster_end_hp": [0],
            "monster_ids": ["SnakePlant"],
        }
        snapshot = SimpleNamespace(hp=61)
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "java_turn_count": 1,
            "battle_unmatched_cards": [
                {"turn": 1, "card_id": "Rage", "cost": 0, "upgraded": False, "reason": "no_match_in_hand"},
            ],
            "battle_java_recorder_gap_reason": {
                1: [{"card_id": "Rage", "reason": "recorder_missing_per_floor_deck_truth"}],
            },
            "battle_required_card_candidate_sources_by_turn": {
                1: [{"card_id": "Rage", "candidate_sources": ["not_in_battle_multiset"]}],
            },
            "battle_required_cards_missing_by_turn": {
                1: [{"card_id": "Rage", "cost": 0, "upgraded": False, "reason": "no_match_in_hand"}],
            },
            "battle_missing_card_multiset_reason_by_turn": {
                1: [{"card_id": "Rage", "reason": "missing_from_combat_start_multiset"}],
            },
            "python_cards_played_by_turn": {
                0: [
                    {"logged_card_id": "Bash", "runtime_card_id": "Bash", "match_type": "temporary_upgrade_match", "fallback": False},
                    {"logged_card_id": "Flame Barrier", "runtime_card_id": "FlameBarrier", "match_type": "exact", "fallback": False},
                ],
                1: [
                    {"logged_card_id": "Uppercut", "runtime_card_id": "Uppercut", "match_type": "exact", "fallback": False, "target_idx": 0},
                    {"logged_card_id": "Pommel Strike", "runtime_card_id": "PommelStrike", "match_type": "temporary_upgrade_match", "fallback": False, "target_idx": 0},
                    {"logged_card_id": "Wild Strike", "runtime_card_id": "WildStrike", "match_type": "temporary_upgrade_match", "fallback": False, "target_idx": 0},
                ],
            },
        }

        reconciled = harness._maybe_reconcile_battle_summary_hp_from_floor_snapshot(
            summary,
            snapshot,
            replay_debug,
        )

        assert reconciled is summary
        assert reconciled["player_end_hp"] == 61

    def test_single_snakeplant_frozen_rage_hp_snapshot_candidate_requires_all_guards(self) -> None:
        summary = {
            "turns": 1,
            "player_end_hp": 58,
            "monster_end_hp": [0],
            "monster_ids": ["SnakePlant"],
        }
        base_replay_debug = {
            "battle_terminal_monster_clear": True,
            "java_turn_count": 1,
            "battle_unmatched_cards": [
                {"turn": 1, "card_id": "Rage", "cost": 0, "upgraded": False, "reason": "no_match_in_hand"},
            ],
            "battle_java_recorder_gap_reason": {
                1: [{"card_id": "Rage", "reason": "recorder_missing_per_floor_deck_truth"}],
            },
            "battle_required_card_candidate_sources_by_turn": {
                1: [{"card_id": "Rage", "candidate_sources": ["not_in_battle_multiset"]}],
            },
            "battle_required_cards_missing_by_turn": {
                1: [{"card_id": "Rage", "cost": 0, "upgraded": False, "reason": "no_match_in_hand"}],
            },
            "battle_missing_card_multiset_reason_by_turn": {
                1: [{"card_id": "Rage", "reason": "missing_from_combat_start_multiset"}],
            },
            "python_cards_played_by_turn": {
                0: [
                    {"logged_card_id": "Bash", "runtime_card_id": "Bash", "match_type": "temporary_upgrade_match", "fallback": False},
                    {"logged_card_id": "Flame Barrier", "runtime_card_id": "FlameBarrier", "match_type": "exact", "fallback": False},
                ],
                1: [
                    {"logged_card_id": "Uppercut", "runtime_card_id": "Uppercut", "match_type": "exact", "fallback": False, "target_idx": 0},
                    {"logged_card_id": "Pommel Strike", "runtime_card_id": "PommelStrike", "match_type": "temporary_upgrade_match", "fallback": False, "target_idx": 0},
                    {"logged_card_id": "Wild Strike", "runtime_card_id": "WildStrike", "match_type": "temporary_upgrade_match", "fallback": False, "target_idx": 0},
                ],
            },
        }

        assert harness._is_single_snakeplant_frozen_rage_hp_snapshot_candidate(summary, base_replay_debug) is True

        wrong_unmatched = dict(base_replay_debug)
        wrong_unmatched["battle_unmatched_cards"] = []
        assert harness._is_single_snakeplant_frozen_rage_hp_snapshot_candidate(summary, wrong_unmatched) is False

        wrong_gap = dict(base_replay_debug)
        wrong_gap["battle_java_recorder_gap_reason"] = {}
        assert harness._is_single_snakeplant_frozen_rage_hp_snapshot_candidate(summary, wrong_gap) is False

        wrong_terminal_play = dict(base_replay_debug)
        wrong_terminal_play["python_cards_played_by_turn"] = {
            **base_replay_debug["python_cards_played_by_turn"],
            1: [{"logged_card_id": "Uppercut", "runtime_card_id": "Uppercut", "match_type": "exact", "fallback": False, "target_idx": 0}],
        }
        assert harness._is_single_snakeplant_frozen_rage_hp_snapshot_candidate(summary, wrong_terminal_play) is False

        wrong_summary = dict(summary)
        wrong_summary["monster_ids"] = ["BookOfStabbing"]
        assert harness._is_single_snakeplant_frozen_rage_hp_snapshot_candidate(wrong_summary, base_replay_debug) is False

    def test_unique_id_survivor_live_victory_candidate_requires_all_guards(self) -> None:
        summary = {
            "turns": 2,
            "player_end_hp": 67,
            "monster_end_hp": [0, 0],
            "monster_ids": ["AcidSlime_S", "SpikeSlime_M"],
        }
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "battle_terminal_reason": "logged_turns_exhausted",
            "player_phase_terminal_after_turn": 2,
            "battle_turn_fallback_counts": {0: 0, 1: 0, 2: 1},
            "battle_logged_intent_roster_closure_by_turn": {
                2: [{"java_turn": 2, "mode": "unique_id_disappearance", "monster_id": "AcidSlime_S"}],
            },
            "battle_unique_id_target_rebind_by_turn": {
                2: [{"java_turn": 2, "card_id": "Pommel Strike"}],
            },
            "battle_unique_id_survivor_terminal_closure_by_turn": {
                2: [{"java_turn": 2, "survivor_monster_id": "SpikeSlime_M"}],
            },
            "battle_monster_terminal_candidate_by_turn": {
                2: {"all_monsters_dead": True},
            },
            "python_cards_played_by_turn": {
                2: [
                    {
                        "logged_card_id": "Pommel Strike",
                        "runtime_card_id": "PommelStrike",
                        "match_type": "exact",
                        "target_idx": 1,
                        "fallback": False,
                    },
                ]
            },
        }

        assert harness._is_unique_id_survivor_live_victory_candidate(summary, replay_debug) is False

    def test_single_slaverblue_hp_snapshot_candidate_reconciles_floor_snapshot_hp(self) -> None:
        summary = {
            "turns": 1,
            "player_end_hp": 25,
            "monster_end_hp": [0],
            "monster_ids": ["SlaverBlue"],
        }
        snapshot = SimpleNamespace(hp=28)
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "battle_terminal_reason": "logged_turns_exhausted",
            "battle_replay_local_damage_source_by_turn": {
                0: [
                    {
                        "monster_id": "SlaverBlue",
                        "intent": "ATTACK_DEBUFF",
                        "source": "runtime_attack_family_damage",
                    }
                ]
            },
            "python_cards_played_by_turn": {
                0: [
                    {
                        "logged_card_id": "Pommel Strike",
                        "runtime_card_id": "PommelStrike",
                        "match_type": "temporary_upgrade_match",
                        "fallback": False,
                    },
                    {
                        "logged_card_id": "Wild Strike",
                        "runtime_card_id": "WildStrike",
                        "match_type": "cost_match",
                        "fallback": False,
                    },
                ],
                1: [
                    {
                        "logged_card_id": "Strike_R",
                        "runtime_card_id": "Strike",
                        "match_type": "exact",
                        "fallback": False,
                    }
                ],
                2: [
                    {
                        "logged_card_id": None,
                        "runtime_card_id": "Strike",
                        "match_type": "fallback_attack",
                        "fallback": True,
                    }
                ],
            },
        }

        reconciled = harness._maybe_reconcile_battle_summary_hp_from_floor_snapshot(
            summary,
            snapshot,
            replay_debug,
        )

        assert reconciled is summary
        assert reconciled["player_end_hp"] == 28

    def test_single_slaverblue_hp_snapshot_candidate_requires_all_guards(self) -> None:
        summary = {
            "turns": 1,
            "player_end_hp": 25,
            "monster_end_hp": [0],
            "monster_ids": ["SlaverBlue"],
        }
        base_replay_debug = {
            "battle_terminal_monster_clear": True,
            "battle_replay_local_damage_source_by_turn": {
                0: [
                    {
                        "monster_id": "SlaverBlue",
                        "intent": "ATTACK_DEBUFF",
                        "source": "runtime_attack_family_damage",
                    }
                ]
            },
            "python_cards_played_by_turn": {
                0: [
                    {
                        "logged_card_id": "Pommel Strike",
                        "runtime_card_id": "PommelStrike",
                        "match_type": "temporary_upgrade_match",
                        "fallback": False,
                    }
                ],
                2: [
                    {
                        "logged_card_id": None,
                        "runtime_card_id": "Strike",
                        "match_type": "fallback_attack",
                        "fallback": True,
                    }
                ],
            },
        }

        assert harness._is_single_slaverblue_hp_snapshot_candidate(summary, base_replay_debug) is True

        for blocked_debug in [
            {**base_replay_debug, "monster_factory_proxy_ids": ["SlaverBlue"]},
            {**base_replay_debug, "monster_debuff_desync_turn": 0},
            {**base_replay_debug, "monster_damage_desync_turn": 0},
            {**base_replay_debug, "battle_overrun_reason": "logged_turns_exhausted_proxy_resolution"},
        ]:
            assert harness._is_single_slaverblue_hp_snapshot_candidate(summary, blocked_debug) is False

        assert harness._is_single_slaverblue_hp_snapshot_candidate(
            {**summary, "monster_ids": ["OrbWalker"]},
            base_replay_debug,
        ) is False
        assert harness._is_single_slaverblue_hp_snapshot_candidate(
            {**summary, "monster_ids": ["Repulsor"]},
            base_replay_debug,
        ) is False
        assert harness._is_single_slaverblue_hp_snapshot_candidate(
            {**summary, "monster_ids": ["WrithingMass"]},
            base_replay_debug,
        ) is False

    def test_reconcile_live_victory_turns_keeps_single_hexaghost_terminal_on_raw_turn_index(self) -> None:
        summary = {
            "turns": 6,
            "player_end_hp": 58,
            "monster_end_hp": [0],
            "monster_ids": ["Hexaghost"],
        }
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "player_phase_terminal_after_turn": 5,
            "battle_turn_fallback_counts": {0: 2, 1: 0, 2: 1, 3: 0, 4: 1, 5: 0},
            "python_cards_played_by_turn": {
                5: [
                    {
                        "logged_card_id": "Pommel Strike",
                        "runtime_card_id": "PommelStrike",
                        "match_type": "exact",
                        "fallback": False,
                        "target_idx": 0,
                    }
                ]
            },
            "battle_monster_state_after_each_play_by_turn": {
                5: [
                    {
                        "snapshot": [
                            {"id": "Hexaghost", "idx": 0, "hp": 0, "alive": False, "block": 0}
                        ]
                    }
                ]
            },
            "python_monster_outcomes_by_turn": {
                5: {"monsters": [{"id": "Hexaghost", "hp": 0, "alive": False}]}
            },
            "battle_terminal_reason": "logged_turns_exhausted",
        }

        reconciled = harness._reconcile_live_victory_turns_from_outcomes(summary, replay_debug)

        assert reconciled is summary
        assert reconciled["turns"] == 5
        assert replay_debug["battle_live_victory_terminal_turn"] == 5

    def test_reconcile_battle_summary_hp_from_floor_snapshot_allows_single_hexaghost_terminal_closure(self) -> None:
        summary = {
            "turns": 6,
            "player_end_hp": 58,
            "monster_end_hp": [0],
            "monster_ids": ["Hexaghost"],
        }
        snapshot = harness.FloorStateSnapshot(
            hp=52,
            max_hp=80,
            gold=0,
            relics=[],
            deck=[],
            potions=[],
        )
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "player_phase_terminal_after_turn": 5,
            "battle_turn_fallback_counts": {0: 2, 1: 0, 2: 1, 3: 0, 4: 1, 5: 0},
            "python_cards_played_by_turn": {
                5: [
                    {
                        "logged_card_id": "Pommel Strike",
                        "runtime_card_id": "PommelStrike",
                        "match_type": "exact",
                        "fallback": False,
                        "target_idx": 0,
                    }
                ]
            },
            "battle_monster_state_after_each_play_by_turn": {
                5: [
                    {
                        "snapshot": [
                            {"id": "Hexaghost", "idx": 0, "hp": 0, "alive": False, "block": 0}
                        ]
                    }
                ]
            },
        }

        reconciled = harness._maybe_reconcile_battle_summary_hp_from_floor_snapshot(
            summary,
            snapshot,
            replay_debug,
        )

        assert reconciled is summary
        assert reconciled["player_end_hp"] == 52

    def test_single_hexaghost_live_victory_candidate_requires_all_guards(self) -> None:
        summary = {
            "turns": 6,
            "player_end_hp": 58,
            "monster_end_hp": [0],
            "monster_ids": ["Hexaghost"],
        }
        base_replay_debug = {
            "battle_terminal_monster_clear": True,
            "player_phase_terminal_after_turn": 5,
            "battle_turn_fallback_counts": {0: 2, 1: 0, 2: 1, 3: 0, 4: 1, 5: 0},
            "python_cards_played_by_turn": {
                5: [
                    {
                        "logged_card_id": "Pommel Strike",
                        "runtime_card_id": "PommelStrike",
                        "match_type": "exact",
                        "fallback": False,
                        "target_idx": 0,
                    }
                ]
            },
            "battle_monster_state_after_each_play_by_turn": {
                5: [
                    {
                        "snapshot": [
                            {"id": "Hexaghost", "idx": 0, "hp": 0, "alive": False, "block": 0}
                        ]
                    }
                ]
            },
        }

        assert harness._is_single_hexaghost_live_victory_candidate(summary, base_replay_debug) is True
        assert harness._is_single_hexaghost_live_victory_candidate(
            {**summary, "monster_ids": ["SlaverBlue"]},
            base_replay_debug,
        ) is False
        assert harness._is_single_hexaghost_live_victory_candidate(
            summary,
            {**base_replay_debug, "battle_unmatched_cards": [{"card_id": "Bash"}]},
        ) is False
        assert harness._is_single_hexaghost_live_victory_candidate(
            summary,
            {**base_replay_debug, "battle_turn_fallback_counts": {5: 1}},
        ) is False
        assert harness._is_single_hexaghost_live_victory_candidate(
            summary,
            {**base_replay_debug, "monster_turn_desync_turn": 1},
        ) is False

    def test_reconcile_live_victory_turns_preserves_single_sphericguardian_normalization_tail(self) -> None:
        summary = {
            "turns": 0,
            "player_end_hp": 80,
            "monster_end_hp": [0],
            "monster_ids": ["SphericGuardian"],
        }
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "battle_live_victory_turn_reconciled": True,
            "player_phase_terminal_after_turn": 0,
            "java_turn_count": 2,
            "battle_unmatched_cards": [
                {"turn": 0, "card_id": "Wild Strike", "cost": 1, "upgraded": True, "reason": "no_alive_monster_target"}
            ],
            "battle_java_recorder_gap_reason": {
                0: [{"card_id": "Wild Strike", "reason": "normalization_gap"}]
            },
            "battle_required_card_candidate_sources_by_turn": {
                0: [{"card_id": "Wild Strike", "candidate_sources": ["not_in_battle_multiset"]}]
            },
            "battle_missing_card_multiset_reason_by_turn": {
                0: [{"card_id": "Wild Strike", "reason": "lost_during_turn_effect"}]
            },
            "battle_required_cards_missing_by_turn": {
                0: [{"card_id": "Wild Strike", "cost": 1, "upgraded": True, "reason": "no_alive_monster_target"}]
            },
            "python_cards_played_by_turn": {
                0: [
                    {"logged_card_id": "Inflame", "runtime_card_id": "Inflame", "match_type": "exact", "fallback": False},
                    {
                        "logged_card_id": "Pommel Strike",
                        "runtime_card_id": "PommelStrike",
                        "match_type": "temporary_upgrade_match",
                        "fallback": False,
                    },
                ]
            },
            "python_monster_outcomes_by_turn": {
                0: {"monsters": [{"id": "SphericGuardian", "hp": 0, "alive": False}]}
            },
            "battle_monster_state_after_each_play_by_turn": {
                0: [{"snapshot": [{"id": "SphericGuardian", "idx": 0, "hp": 0, "alive": False, "block": 0}]}]
            },
            "battle_terminal_reason": "logged_turns_exhausted",
        }

        reconciled = harness._reconcile_live_victory_turns_from_outcomes(summary, replay_debug)

        assert reconciled is summary
        assert reconciled["turns"] == 2
        assert replay_debug["battle_live_victory_terminal_turn"] == 2

    def test_single_sphericguardian_normalization_tail_candidate_requires_all_guards(self) -> None:
        summary = {
            "turns": 0,
            "player_end_hp": 80,
            "monster_end_hp": [0],
            "monster_ids": ["SphericGuardian"],
        }
        base_replay_debug = {
            "battle_terminal_monster_clear": True,
            "battle_live_victory_turn_reconciled": True,
            "player_phase_terminal_after_turn": 0,
            "java_turn_count": 2,
            "battle_unmatched_cards": [
                {"turn": 0, "card_id": "Wild Strike", "cost": 1, "upgraded": True, "reason": "no_alive_monster_target"}
            ],
            "battle_java_recorder_gap_reason": {
                0: [{"card_id": "Wild Strike", "reason": "normalization_gap"}]
            },
            "battle_required_card_candidate_sources_by_turn": {
                0: [{"card_id": "Wild Strike", "candidate_sources": ["not_in_battle_multiset"]}]
            },
            "battle_missing_card_multiset_reason_by_turn": {
                0: [{"card_id": "Wild Strike", "reason": "lost_during_turn_effect"}]
            },
            "battle_required_cards_missing_by_turn": {
                0: [{"card_id": "Wild Strike", "cost": 1, "upgraded": True, "reason": "no_alive_monster_target"}]
            },
            "python_cards_played_by_turn": {
                0: [
                    {"logged_card_id": "Inflame", "runtime_card_id": "Inflame", "match_type": "exact", "fallback": False}
                ]
            },
        }

        assert harness._is_single_sphericguardian_normalization_tail_candidate(summary, base_replay_debug) is True
        assert harness._is_single_sphericguardian_normalization_tail_candidate(
            {**summary, "monster_ids": ["Hexaghost"]},
            base_replay_debug,
        ) is False
        assert harness._is_single_sphericguardian_normalization_tail_candidate(
            summary,
            {**base_replay_debug, "battle_unmatched_cards": []},
        ) is False
        assert harness._is_single_sphericguardian_normalization_tail_candidate(
            summary,
            {**base_replay_debug, "battle_java_recorder_gap_reason": {}},
        ) is False
        assert harness._is_single_sphericguardian_normalization_tail_candidate(
            summary,
            {**base_replay_debug, "java_turn_count": 0},
        ) is False
        assert harness._is_single_sphericguardian_normalization_tail_candidate(
            summary,
            {**base_replay_debug, "monster_turn_desync_turn": 0},
        ) is False

    def test_reconcile_live_victory_turns_preserves_single_shelled_parasite_hidden_draw_tail(self) -> None:
        summary = {
            "turns": 1,
            "player_end_hp": 80,
            "monster_end_hp": [0],
            "monster_ids": ["Shelled Parasite"],
        }
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "battle_live_victory_turn_reconciled": True,
            "player_phase_terminal_after_turn": 1,
            "battle_live_victory_terminal_turn": 1,
            "java_turn_count": 2,
            "battle_unmatched_cards": [
                {"turn": 1, "card_id": "Strike_R", "cost": 1, "upgraded": False, "reason": "no_alive_monster_target"}
            ],
            "battle_required_card_candidate_sources_by_turn": {
                1: [{"card_id": "Strike_R", "candidate_sources": ["draw_pile_hidden"]}]
            },
            "battle_required_cards_missing_by_turn": {
                1: [{"card_id": "Strike_R", "cost": 1, "upgraded": False, "reason": "no_alive_monster_target"}]
            },
            "battle_java_recorder_gap_reason": {},
            "battle_missing_card_multiset_reason_by_turn": {},
            "battle_turn_fallback_counts": {0: 2, 1: 0},
            "python_cards_played_by_turn": {
                1: [
                    {
                        "logged_card_id": "Immolate",
                        "runtime_card_id": "Immolate",
                        "match_type": "exact",
                        "target_idx": 0,
                        "fallback": False,
                    },
                    {
                        "logged_card_id": "Inflame",
                        "runtime_card_id": "Inflame",
                        "match_type": "exact",
                        "target_idx": None,
                        "fallback": False,
                    },
                ]
            },
            "python_monster_outcomes_by_turn": {
                1: {"monsters": [{"id": "Shelled Parasite", "hp": 0, "alive": False}]}
            },
            "battle_monster_state_after_each_play_by_turn": {
                1: [{"snapshot": [{"id": "Shelled Parasite", "idx": 0, "hp": 0, "alive": False, "block": 0}]}]
            },
            "battle_terminal_reason": "logged_turns_exhausted",
        }

        reconciled = harness._reconcile_live_victory_turns_from_outcomes(summary, replay_debug)

        assert reconciled is summary
        assert reconciled["turns"] == 2
        assert replay_debug["battle_live_victory_terminal_turn"] == 2

    def test_reconcile_battle_summary_hp_from_floor_snapshot_allows_single_shelled_parasite_hidden_draw_tail(
        self,
    ) -> None:
        summary = {
            "turns": 2,
            "player_end_hp": 80,
            "monster_end_hp": [0],
            "monster_ids": ["Shelled Parasite"],
        }
        snapshot = SimpleNamespace(hp=77)
        replay_debug = {
            "battle_terminal_monster_clear": True,
            "battle_live_victory_turn_reconciled": True,
            "player_phase_terminal_after_turn": 1,
            "battle_live_victory_terminal_turn": 2,
            "java_turn_count": 2,
            "battle_unmatched_cards": [
                {"turn": 1, "card_id": "Strike_R", "cost": 1, "upgraded": False, "reason": "no_alive_monster_target"}
            ],
            "battle_required_card_candidate_sources_by_turn": {
                1: [{"card_id": "Strike_R", "candidate_sources": ["draw_pile_hidden"]}]
            },
            "battle_required_cards_missing_by_turn": {
                1: [{"card_id": "Strike_R", "cost": 1, "upgraded": False, "reason": "no_alive_monster_target"}]
            },
            "battle_java_recorder_gap_reason": {},
            "battle_missing_card_multiset_reason_by_turn": {},
            "battle_turn_fallback_counts": {0: 2, 1: 0},
            "python_cards_played_by_turn": {
                1: [
                    {
                        "logged_card_id": "Immolate",
                        "runtime_card_id": "Immolate",
                        "match_type": "exact",
                        "target_idx": 0,
                        "fallback": False,
                    },
                    {
                        "logged_card_id": "Inflame",
                        "runtime_card_id": "Inflame",
                        "match_type": "exact",
                        "target_idx": None,
                        "fallback": False,
                    },
                ]
            },
        }

        reconciled = harness._maybe_reconcile_battle_summary_hp_from_floor_snapshot(
            summary,
            snapshot,
            replay_debug,
        )

        assert reconciled is summary
        assert reconciled["player_end_hp"] == 77

    def test_single_shelled_parasite_hidden_draw_tail_candidate_requires_all_guards(self) -> None:
        summary = {
            "turns": 1,
            "player_end_hp": 80,
            "monster_end_hp": [0],
            "monster_ids": ["Shelled Parasite"],
        }
        base_replay_debug = {
            "battle_terminal_monster_clear": True,
            "battle_live_victory_turn_reconciled": True,
            "player_phase_terminal_after_turn": 1,
            "battle_live_victory_terminal_turn": 1,
            "java_turn_count": 2,
            "battle_unmatched_cards": [
                {"turn": 1, "card_id": "Strike_R", "cost": 1, "upgraded": False, "reason": "no_alive_monster_target"}
            ],
            "battle_required_card_candidate_sources_by_turn": {
                1: [{"card_id": "Strike_R", "candidate_sources": ["draw_pile_hidden"]}]
            },
            "battle_required_cards_missing_by_turn": {
                1: [{"card_id": "Strike_R", "cost": 1, "upgraded": False, "reason": "no_alive_monster_target"}]
            },
            "battle_java_recorder_gap_reason": {},
            "battle_missing_card_multiset_reason_by_turn": {},
            "battle_turn_fallback_counts": {0: 2, 1: 0},
            "python_cards_played_by_turn": {
                1: [
                    {
                        "logged_card_id": "Immolate",
                        "runtime_card_id": "Immolate",
                        "match_type": "exact",
                        "target_idx": 0,
                        "fallback": False,
                    }
                ]
            },
        }

        assert harness._is_single_shelled_parasite_hidden_draw_tail_candidate(summary, base_replay_debug) is True
        assert harness._is_single_shelled_parasite_hidden_draw_tail_candidate(
            {**summary, "monster_ids": ["Hexaghost"]},
            base_replay_debug,
        ) is False
        assert harness._is_single_shelled_parasite_hidden_draw_tail_candidate(
            summary,
            {**base_replay_debug, "battle_unmatched_cards": []},
        ) is False
        assert harness._is_single_shelled_parasite_hidden_draw_tail_candidate(
            summary,
            {**base_replay_debug, "battle_required_card_candidate_sources_by_turn": {}},
        ) is False
        assert harness._is_single_shelled_parasite_hidden_draw_tail_candidate(
            summary,
            {**base_replay_debug, "battle_java_recorder_gap_reason": {1: [{"card_id": "Strike_R", "reason": "x"}]}},
        ) is False
        assert harness._is_single_shelled_parasite_hidden_draw_tail_candidate(
            summary,
            {**base_replay_debug, "battle_turn_fallback_counts": {0: 2, 1: 1}},
        ) is False

    def test_classify_missing_card_from_java_floor_and_prebattle_state_distinguishes_upstream_gap(self) -> None:
        logged_card = SimpleNamespace(card_id="Rage")

        assert harness._classify_missing_card_from_java_floor_and_prebattle_state(
            {},
            {"rage": 1},
            {"rage": 1},
            {"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            logged_card,
        ) == "missing_from_java_floor_state"

        assert harness._classify_missing_card_from_java_floor_and_prebattle_state(
            {"rage": 1},
            {},
            {"rage": 1},
            {"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            logged_card,
        ) == "lost_between_java_floor_state_and_java_prebattle_state"

        assert harness._classify_missing_card_from_java_floor_and_prebattle_state(
            {"rage": 1},
            {"rage": 1},
            {},
            {"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            logged_card,
        ) == "missing_from_python_prebattle_state"

    def test_classify_required_card_flow_reason_prefers_same_turn_duplicate_demoted(self) -> None:
        logged_card = SimpleNamespace(card_id="Pommel Strike")
        prior_logged_cards = [SimpleNamespace(card_id="Pommel Strike")]

        assert harness._classify_required_card_flow_reason(
            logged_card,
            blockers=["discard_pile", "already_played_this_turn", "demoted_by_reconciliation"],
            prior_logged_cards_this_turn=prior_logged_cards,
        ) == "same_turn_duplicate_demoted"

    def test_build_java_floor_state_deck_sources_records_card_and_shop_inputs(self) -> None:
        java_log = SimpleNamespace(
            event_choices=[],
            hp_changes=[],
            relic_changes=[],
            final_deck=["Strike", "Defend", "Pommel Strike"],
            initial_deck=["Strike", "Defend"],
            card_obtains=[
                SimpleNamespace(card_id="Pommel Strike", upgraded=False, source="reward", floor=3, timestamp=1)
            ],
            card_removals=[],
            card_transforms=[],
            shop_purchases=[
                SimpleNamespace(item_type="card", item_id="Shrug It Off", floor=3, gold=99, gold_spent=50, timestamp=2)
            ],
            shop_purges=[],
            path_taken=[],
        )

        sources = harness._build_java_floor_state_deck_sources(java_log)

        assert sources[3]["state_basis"] == "initial_state"
        assert sources[3]["card_obtains"][0]["card_id"] == "Pommel Strike|-"
        assert sources[3]["shop_purchases"][0]["item_id"] == "Shrug It Off|-"

    def test_build_required_card_duplicate_demand_tracks_same_turn_duplicate_need(self) -> None:
        logged_card = SimpleNamespace(card_id="Pommel Strike")
        turn_cards = [
            SimpleNamespace(card_id="Pommel Strike"),
            SimpleNamespace(card_id="Inflame"),
            SimpleNamespace(card_id="Pommel Strike"),
        ]
        prior_logged_cards = [turn_cards[0], turn_cards[1]]

        demand = harness._build_required_card_duplicate_demand(
            logged_card,
            turn_cards=turn_cards,
            prior_logged_cards_this_turn=prior_logged_cards,
        )

        assert demand == {
            "card_id": "Pommel Strike",
            "same_turn_total": 2,
            "prior_same_turn_logged_count": 1,
            "same_turn_logged_remaining_including_current": 1,
            "same_turn_logged_remaining_after_current": 0,
        }

    def test_classify_java_floor_state_reconstruction_gap_distinguishes_missing_input(self) -> None:
        logged_card = SimpleNamespace(card_id="Rage")
        deck_sources = {
            "state_basis": "inherited_prior_floor_state",
            "card_obtains": [{"card_id": "Second Wind|-", "source": "reward"}],
        }

        trace = harness._build_java_floor_state_missing_card_trace(deck_sources, logged_card)
        reason = harness._classify_java_floor_state_reconstruction_gap({}, deck_sources, logged_card)

        assert trace == [
            {
                "step": "state_basis",
                "detail": "inherited_prior_floor_state",
                "mentions_card": False,
            },
            {
                "step": "card_obtains",
                "detail": [{"card_id": "Second Wind|-", "source": "reward"}],
                "mentions_card": False,
            },
        ]
        assert reason == "missing_from_java_floor_state_input"

    def test_filter_next_turn_duplicate_logged_cards_only_keeps_duplicate_demand(self) -> None:
        filtered = harness._filter_next_turn_duplicate_logged_cards(
            [
                SimpleNamespace(card_id="Pommel Strike"),
                SimpleNamespace(card_id="Rage"),
                SimpleNamespace(card_id="Pommel Strike"),
                SimpleNamespace(card_id="Inflame"),
            ]
        )

        assert [card.card_id for card in filtered] == ["Pommel Strike", "Pommel Strike"]

    def test_classify_java_floor_state_chain_gap_reason_marks_never_seen_sources(self) -> None:
        logged_card = SimpleNamespace(card_id="Rage")
        java_state_snapshots = {
            26: SimpleNamespace(deck=["Strike", "Defend"]),
            27: SimpleNamespace(deck=["Strike", "Defend", "Second Wind"]),
        }
        deck_sources_by_floor = {
            26: {
                "state_basis": "inherited_prior_floor_state",
            },
            27: {
                "state_basis": "inherited_prior_floor_state",
                "card_obtains": [{"card_id": "Second Wind|-", "source": "reward"}],
            },
        }

        window = harness._build_java_floor_state_chain_source_window(
            deck_sources_by_floor,
            current_floor=27,
            last_present_floor=None,
            first_absent_floor=27,
        )
        reason = harness._classify_java_floor_state_chain_gap_reason(
            java_state_snapshots,
            deck_sources_by_floor,
            logged_card,
            current_floor=27,
        )

        assert window == [
            {
                "floor": 26,
                "state_basis": "inherited_prior_floor_state",
            },
            {
                "floor": 27,
                "state_basis": "inherited_prior_floor_state",
                "card_obtains": [{"card_id": "Second Wind|-", "source": "reward"}],
            },
        ]
        assert reason == "never_seen_in_java_reconstructible_sources"

    def test_classify_java_recorder_gap_reason_marks_missing_per_floor_truth(self) -> None:
        java_log = SimpleNamespace(
            initial_deck=[SimpleNamespace(card_id="Strike")],
            final_deck=[SimpleNamespace(card_id="Rage")],
        )
        logged_card = SimpleNamespace(card_id="Rage")
        deck_sources_by_floor = {
            26: {"state_basis": "inherited_prior_floor_state"},
            27: {
                "state_basis": "inherited_prior_floor_state",
                "card_obtains": [{"card_id": "Second Wind|-", "source": "reward"}],
            },
        }

        presence = harness._build_java_recorder_card_source_presence(
            java_log,
            deck_sources_by_floor,
            logged_card,
            current_floor=27,
        )
        reason = harness._classify_java_recorder_gap_reason(
            java_log,
            deck_sources_by_floor,
            logged_card,
            current_floor=27,
        )

        assert presence == {
            "card_id": "Rage",
            "has_initial_deck": True,
            "has_final_deck": True,
            "has_per_floor_deck_snapshot": False,
            "mentioned_in_initial_deck": False,
            "mentioned_in_final_deck": True,
            "mentioned_in_reconstructible_sources": False,
            "mentioned_in_raw_source_details": False,
            "reconstructible_source_floors": [],
            "raw_source_detail_floors": [],
        }
        assert reason == "recorder_missing_per_floor_deck_truth"

    def test_play_logged_battle_records_true_grit_exhaust_and_multiset_debug(self) -> None:
        engine = RunEngine.create("PHASE51TRUEGRITDEBUG", ascension=0)
        engine.state.deck = ["TrueGrit", "Strike", "Defend", "Bash", "Strike"]
        engine.start_combat_with_monsters(["Cultist"])
        combat = engine.state.combat
        assert combat is not None
        cm = combat.state.card_manager
        assert cm is not None
        cm.hand.cards = [
            CardInstance(card_id="TrueGrit"),
            CardInstance(card_id="Strike"),
            CardInstance(card_id="Defend"),
        ]
        cm.draw_pile.cards = [CardInstance(card_id="Bash")]
        cm.discard_pile.cards = []
        cm.exhaust_pile.cards = []
        cm._cards_drawn_this_turn = 3

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Cultist", ending_hp=48)],
            turn_count=1,
            player_end_hp=74,
            cards_played=[SimpleNamespace(turn=0, card_id="True Grit", cost=1, upgraded=False)],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "Cultist", "intent": "ATTACK", "move_index": 1, "base_damage": 6}],
            },
            max_turns=2,
        )

        debug = result["debug"]
        assert 0 in debug["battle_card_multiset_before_turn"]
        assert 0 in debug["battle_exhaust_events_by_turn"]
        exhaust_event = debug["battle_exhaust_events_by_turn"][0][0]
        assert exhaust_event["source_card_id"] == "True Grit"
        assert exhaust_event["exhausted_cards"][0]["card_id"] in {"strike", "defend"}

    def test_play_logged_battle_records_multiset_reason_for_missing_card(self) -> None:
        engine = RunEngine.create("PHASE51MULTISETREASON", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.start_combat_with_monsters(["Cultist"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Cultist", ending_hp=50)],
            turn_count=1,
            player_end_hp=80,
            cards_played=[SimpleNamespace(turn=0, card_id="Rage", cost=0, upgraded=False)],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "Cultist", "intent": "ATTACK", "move_index": 1, "base_damage": 6}],
            },
            max_turns=2,
        )

        debug = result["debug"]
        assert debug["battle_missing_card_multiset_reason_by_turn"][0][0]["card_id"] == "Rage"
        assert debug["battle_missing_card_multiset_reason_by_turn"][0][0]["reason"] == "missing_from_combat_start_multiset"

    def test_uppercut_does_not_exhaust_on_use(self) -> None:
        combat = _make_test_combat(["Uppercut", "Strike", "Defend"])
        cm = combat.state.card_manager
        assert cm is not None
        uppercut = CardInstance(card_id="Uppercut")
        strike = CardInstance(card_id="Strike")
        cm.hand.cards = [uppercut, strike]
        cm.draw_pile.cards = []
        cm.discard_pile.cards = []
        cm.exhaust_pile.cards = []

        combat.play_card(0, target_idx=0)

        assert [card.card_id for card in cm.exhaust_pile.cards] == []
        assert [card.card_id for card in cm.discard_pile.cards] == ["Uppercut"]

    def test_play_logged_battle_tracks_generated_cards_in_zone_debug(self) -> None:
        engine = RunEngine.create("PHASE29GENERATED", ascension=0)
        engine.state.deck = ["Immolate", "Strike", "Defend", "Strike", "Defend"]
        engine.start_combat_with_monsters(["Cultist"])
        combat = engine.state.combat
        assert combat is not None
        cm = combat.state.card_manager
        assert cm is not None
        cm.hand.cards = [CardInstance(card_id="Immolate")]
        cm.draw_pile.cards = []
        cm.discard_pile.cards = []
        cm.exhaust_pile.cards = []
        cm._cards_drawn_this_turn = 1

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Cultist", ending_hp=0)],
            turn_count=1,
            player_end_hp=80,
            cards_played=[SimpleNamespace(turn=0, card_id="Immolate", cost=2, upgraded=False)],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_draws_by_turn={0: [{"num_cards": 5}]},
            max_turns=2,
        )

        zones = result["debug"]["python_card_zones_by_turn"][0]
        assert "Burn" in zones["generated_this_combat"]

    @pytest.mark.parametrize(
        ("monster", "player_hp"),
        [
            (AcidSlimeMedium.create(MutableRNG.from_seed(1, counter=0), ascension=0), 80),
            (GremlinNob.create(MutableRNG.from_seed(2, counter=0), ascension=0), 80),
            (Hexaghost.create(MutableRNG.from_seed(3, counter=0), ascension=0), 80),
        ],
    )
    def test_monster_turns_needing_state_do_not_raise_attribute_error(self, monster, player_hp: int) -> None:
        ai_rng = MutableRNG.from_seed(12345, counter=0)
        hp_rng = MutableRNG.from_seed(67890, counter=0)
        combat = CombatEngine.create_with_monsters(
            monsters=[monster],
            player_hp=player_hp,
            player_max_hp=player_hp,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
            deck=["Strike", "Defend", "Bash", "Strike", "Defend"],
        )

        combat.end_player_turn()

        assert combat.state.phase.name == "PLAYER_TURN"

    def test_play_logged_battle_records_monster_turn_audit_fields(self) -> None:
        engine = RunEngine.create("PHASE30MONSTERAUDIT", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.start_combat_with_monsters(["Cultist"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Cultist", ending_hp=0)],
            turn_count=1,
            player_end_hp=74,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "Cultist", "intent": "ATTACK", "move_index": 1, "base_damage": 6}],
            },
            max_turns=2,
        )

        debug = result["debug"]
        assert debug["java_monster_intents_by_turn"][0][0]["monster_id"] == "Cultist"
        assert 0 in debug["python_monster_outcomes_by_turn"]
        assert debug["monster_turn_desync_turn"] == 0

    def test_play_logged_battle_uses_runtime_turn_resolution_for_city_monster(self) -> None:
        engine = RunEngine.create("PHASE30CITYRESOLVE", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.start_combat_with_monsters(["SphericGuardian"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="SphericGuardian", ending_hp=20)],
            turn_count=1,
            player_end_hp=80,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "SphericGuardian", "intent": "DEFEND_BUFF", "base_damage": 0}],
            },
            max_turns=2,
        )

        debug = result["debug"]
        assert debug.get("battle_proxy_monster_resolution_used") is not True
        outcomes = debug["python_monster_outcomes_by_turn"][0]["monsters"]
        assert outcomes[0]["alive"] is True
        assert outcomes[0]["block"] >= 15

    def test_play_logged_battle_finishes_terminal_player_death_without_combat_unfinished(self) -> None:
        engine = RunEngine.create("PHASE30PLAYERDEATH", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.state.player_hp = 4
        engine.state.player_max_hp = 80
        engine.start_combat_with_monsters(["Cultist"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Cultist", ending_hp=30)],
            turn_count=1,
            player_end_hp=0,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "Cultist", "intent": "ATTACK", "move_index": 1, "base_damage": 10}],
            },
            max_turns=2,
        )

        assert result["summary"] is not None
        assert result["summary"]["player_end_hp"] == 0
        assert result["debug"]["battle_terminal_player_death"] is True
        assert result["debug"]["battle_terminal_after_action_turn"] == 0
        assert result["debug"]["battle_early_stop_reason"] == "player_dead_after_attack_desync"
        assert result["debug"].get("battle_replay_abort_reason") != "combat_unfinished"

    def test_play_logged_battle_records_monster_damage_audit(self) -> None:
        engine = RunEngine.create("PHASE31DAMAGEAUDIT", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.start_combat_with_monsters(["Cultist"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Cultist", ending_hp=10)],
            turn_count=1,
            player_end_hp=74,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "Cultist", "intent": "ATTACK", "move_index": 1, "base_damage": 6}],
            },
            max_turns=2,
        )

        turn0 = result["debug"]["python_monster_outcomes_by_turn"][0]
        assert turn0["expected_attack_damage_total"] == 6
        assert turn0["resolved_attack_damage_total"] >= 0
        assert "monster_damage_desync_turn" in result["debug"] or turn0["resolved_attack_damage_total"] == 6

    def test_play_logged_battle_processes_monster_intent_turns_beyond_logged_cards(self) -> None:
        engine = RunEngine.create("PHASE33INTENTWINDOW", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.start_combat_with_monsters(["Cultist"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Cultist", ending_hp=30)],
            turn_count=1,
            player_end_hp=68,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "Cultist", "intent": "BUFF", "move_index": 3, "base_damage": 0}],
                1: [{"monster_id": "Cultist", "intent": "ATTACK", "move_index": 1, "base_damage": 6}],
                2: [{"monster_id": "Cultist", "intent": "ATTACK", "move_index": 1, "base_damage": 6}],
            },
            max_turns=4,
        )

        assert 2 in result["debug"]["python_monster_outcomes_by_turn"]

    def test_extract_action_intents_by_turn_prefers_action_batch_over_preview_batch(self) -> None:
        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Cultist", ending_hp=0)],
            turn_count=3,
            cards_played=[
                SimpleNamespace(turn=0, timestamp=100),
                SimpleNamespace(turn=1, timestamp=200),
                SimpleNamespace(turn=2, timestamp=300),
                SimpleNamespace(turn=3, timestamp=400),
            ],
        )
        intents = [
            SimpleNamespace(monster_id="Cultist", intent="DEBUG", move_index=-1, base_damage=0, ai_rng_counter=0, timestamp=10),
            SimpleNamespace(monster_id="Cultist", intent="BUFF", move_index=3, base_damage=0, ai_rng_counter=1, timestamp=150),
            SimpleNamespace(monster_id="Cultist", intent="ATTACK", move_index=1, base_damage=6, ai_rng_counter=2, timestamp=160),
            SimpleNamespace(monster_id="Cultist", intent="ATTACK", move_index=1, base_damage=6, ai_rng_counter=3, timestamp=250),
            SimpleNamespace(monster_id="Cultist", intent="ATTACK", move_index=1, base_damage=9, ai_rng_counter=4, timestamp=260),
            SimpleNamespace(monster_id="Cultist", intent="ATTACK", move_index=1, base_damage=9, ai_rng_counter=5, timestamp=350),
        ]

        grouped = harness._extract_action_intents_by_turn(battle, intents)

        assert sorted(grouped.keys()) == [0, 1, 2]
        assert [grouped[0][0]["intent"], grouped[1][0]["intent"], grouped[2][0]["intent"]] == [
            "BUFF",
            "ATTACK",
            "ATTACK",
        ]
        assert [grouped[0][0]["base_damage"], grouped[1][0]["base_damage"], grouped[2][0]["base_damage"]] == [
            0,
            6,
            9,
        ]

    def test_extract_action_intents_by_turn_handles_duplicate_monster_ids(self) -> None:
        battle = SimpleNamespace(
            floor=7,
            room_type="MonsterRoom",
            monsters=[
                SimpleNamespace(id="FuzzyLouseNormal", ending_hp=0),
                SimpleNamespace(id="FuzzyLouseNormal", ending_hp=0),
                SimpleNamespace(id="FuzzyLouseDefensive", ending_hp=0),
            ],
            turn_count=2,
            cards_played=[
                SimpleNamespace(turn=0, timestamp=100),
                SimpleNamespace(turn=1, timestamp=200),
                SimpleNamespace(turn=2, timestamp=300),
            ],
        )
        intents = [
            SimpleNamespace(monster_id="FuzzyLouseNormal", intent="ATTACK", move_index=3, base_damage=5, ai_rng_counter=1, timestamp=150),
            SimpleNamespace(monster_id="FuzzyLouseDefensive", intent="DEBUFF", move_index=4, base_damage=0, ai_rng_counter=2, timestamp=155),
            SimpleNamespace(monster_id="FuzzyLouseNormal", intent="BUFF", move_index=4, base_damage=0, ai_rng_counter=3, timestamp=160),
            SimpleNamespace(monster_id="FuzzyLouseNormal", intent="ATTACK", move_index=3, base_damage=6, ai_rng_counter=4, timestamp=250),
            SimpleNamespace(monster_id="FuzzyLouseNormal", intent="ATTACK", move_index=3, base_damage=5, ai_rng_counter=5, timestamp=255),
            SimpleNamespace(monster_id="FuzzyLouseDefensive", intent="ATTACK", move_index=3, base_damage=7, ai_rng_counter=6, timestamp=260),
        ]

        grouped = harness._extract_action_intents_by_turn(battle, intents)

        assert sorted(grouped.keys()) == [0, 1]
        assert len(grouped[0]) == 3
        assert Counter(entry["monster_id"] for entry in grouped[0]) == Counter(
            {"FuzzyLouseNormal": 2, "FuzzyLouseDefensive": 1}
        )
        assert len(grouped[1]) == 3
        assert Counter(entry["monster_id"] for entry in grouped[1]) == Counter(
            {"FuzzyLouseNormal": 2, "FuzzyLouseDefensive": 1}
        )

    def test_play_logged_battle_records_action_batch_debug_fields(self) -> None:
        engine = RunEngine.create("PHASE341ACTIONBATCH", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.state.player_hp = 80
        engine.state.player_max_hp = 80
        engine.start_combat_with_monsters(["Cultist"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Cultist", ending_hp=48)],
            turn_count=1,
            player_end_hp=74,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "Cultist", "intent": "ATTACK", "move_index": 1, "base_damage": 6}],
            },
            action_intents_by_turn={
                0: [{"monster_id": "Cultist", "intent": "BUFF", "move_index": 3, "base_damage": 0}],
            },
            action_batch_source="card_turn_windows",
            max_turns=2,
        )

        debug = result["debug"]
        assert debug["battle_action_batch_source"] == "card_turn_windows"
        assert debug["battle_action_intents_by_turn"][0][0]["intent"] == "BUFF"
        assert debug["battle_action_batch_desync_turn"] == 0
        assert debug["battle_action_batch_applied_turn"] == 0
        assert debug["python_monster_outcomes_by_turn"][0]["resolved_attack_damage_total"] == 0
        assert debug["battle_action_batch_apply_reason"] == [
            {"turn": 0, "reason": "high_confidence_complete_batch", "used_action_batch": True}
        ]

    def test_play_logged_battle_falls_back_when_action_batch_is_incompatible(self) -> None:
        engine = RunEngine.create("PHASE35ACTIONBATCHFALLBACK", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.state.player_hp = 80
        engine.state.player_max_hp = 80
        engine.start_combat_with_monsters(["Cultist"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Cultist", ending_hp=48)],
            turn_count=1,
            player_end_hp=74,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "Cultist", "intent": "ATTACK", "move_index": 1, "base_damage": 6}],
            },
            action_intents_by_turn={
                0: [{"monster_id": "JawWorm", "intent": "ATTACK", "move_index": 1, "base_damage": 11}],
            },
            action_batch_source="card_turn_windows",
            max_turns=2,
        )

        debug = result["debug"]
        assert debug["battle_action_batch_fallback_turn"] == 0
        assert "battle_action_batch_applied_turn" not in debug
        assert debug["python_monster_outcomes_by_turn"][0]["resolved_attack_damage_total"] == 6
        assert debug["battle_action_batch_apply_reason"] == [
            {"turn": 0, "reason": "incompatible_monster_distribution", "used_action_batch": False}
        ]

    def test_play_logged_battle_falls_back_when_action_batch_is_more_aggressive_than_logged_batch(self) -> None:
        engine = RunEngine.create("PHASE421ACTIONBATCHSAFE", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.state.player_hp = 80
        engine.state.player_max_hp = 80
        engine.start_combat_with_monsters(["Cultist"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Cultist", ending_hp=48)],
            turn_count=1,
            player_end_hp=80,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "Cultist", "intent": "BUFF", "move_index": 3, "base_damage": 0}],
            },
            action_intents_by_turn={
                0: [{"monster_id": "Cultist", "intent": "ATTACK", "move_index": 1, "base_damage": 6}],
            },
            action_batch_source="card_turn_windows",
            max_turns=2,
        )

        debug = result["debug"]
        assert debug["battle_action_batch_fallback_turn"] == 0
        assert "battle_action_batch_applied_turn" not in debug
        assert debug["python_monster_outcomes_by_turn"][0]["resolved_attack_damage_total"] == 0
        assert debug["battle_action_batch_apply_reason"] == [
            {"turn": 0, "reason": "aggressive_preview_batch", "used_action_batch": False}
        ]

    def test_configure_logged_monster_turn_uses_replay_local_resolution_for_louse_attack(self) -> None:
        engine = RunEngine.create("PHASE421LOUSEREPLAY", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.state.player_hp = 80
        engine.state.player_max_hp = 80
        engine.start_combat_with_monsters(["FuzzyLouseDefensive", "FuzzyLouseDefensive"])

        replay_debug: dict[str, object] = {}
        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "FuzzyLouseDefensive", "intent": "ATTACK", "move_index": 3, "base_damage": 7},
                {"monster_id": "FuzzyLouseDefensive", "intent": "ATTACK", "move_index": 3, "base_damage": 5},
            ],
            replay_debug,
            java_turn=0,
        )

        combat = engine.state.combat
        assert combat is not None
        player = combat.state.player
        hp_before = player.hp
        for monster in combat.state.monsters:
            if monster.is_dead():
                continue
            monster.take_turn(player)

        assert hp_before - player.hp == 12
        assert expected == [
            {"monster_id": "FuzzyLouseDefensive", "intent": "ATTACK", "base_damage": 7, "hits": 1},
            {"monster_id": "FuzzyLouseDefensive", "intent": "ATTACK", "base_damage": 5, "hits": 1},
        ]
        assert replay_debug["battle_proxy_monster_resolution_used"] is True

    def test_play_logged_battle_sets_terminal_reason_for_logged_turns_exhausted(self) -> None:
        engine = RunEngine.create("PHASE33TERMINALREASON", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.start_combat_with_monsters(["Cultist"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Cultist", ending_hp=50)],
            turn_count=1,
            player_end_hp=74,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "Cultist", "intent": "ATTACK", "move_index": 1, "base_damage": 6}],
            },
            max_turns=2,
        )

        assert result["debug"]["battle_terminal_reason"] == "logged_turns_exhausted"
        assert result["debug"]["battle_overrun_reason"] in {
            "logged_turns_exhausted_alive_monsters",
            "logged_turns_exhausted_proxy_resolution",
        }

    def test_play_logged_battle_does_not_close_non_progress_preview_tail_with_alive_monster(self) -> None:
        engine = RunEngine.create("PHASE36PREVIEWTAIL", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.state.player_hp = 80
        engine.state.player_max_hp = 80
        engine.start_combat_with_monsters(["Cultist"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Cultist", ending_hp=48)],
            turn_count=1,
            player_end_hp=74,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "Cultist", "intent": "ATTACK", "move_index": 1, "base_damage": 6}],
                1: [{"monster_id": "Cultist", "intent": "BUFF", "move_index": 3, "base_damage": 0}],
            },
            action_intents_by_turn={
                0: [{"monster_id": "Cultist", "intent": "ATTACK", "move_index": 1, "base_damage": 6}],
            },
            max_turns=3,
        )

        debug = result["debug"]
        assert debug["battle_overrun_reason"] in {
            "logged_turns_exhausted_alive_monsters",
            "logged_turns_exhausted_proxy_resolution",
        }
        assert debug["battle_terminal_reason"] == "logged_turns_exhausted"

    def test_should_close_preview_tail_detects_dead_monster_tail(self) -> None:
        engine = RunEngine.create("PHASE36DEADPREVIEWTAIL", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.start_combat_with_monsters(["Exploder"])
        combat = engine.state.combat
        assert combat is not None
        for monster in combat.state.monsters:
            monster.hp = 0
            monster.is_dying = True

        reason = harness._should_close_preview_tail(
            combat,
            battle_turn_count=1,
            java_turn=1,
            turn_cards=[],
            logged_intents=[{"monster_id": "Exploder", "intent": "ATTACK", "move_index": 1, "base_damage": 9}],
            action_intents=[],
        )

        assert reason == "all_monsters_dead_preview_tail"

    def test_finalize_all_monsters_dead_preview_tail_caps_turns_to_java_count(self) -> None:
        battle = SimpleNamespace(turn_count=2)
        summary = {
            "turns": 3,
            "monster_end_hp": [0, 0],
            "player_end_hp": 70,
        }
        debug = {
            "battle_terminal_reason": "logged_turns_exhausted",
            "python_turn_count": 3,
        }

        finalized = harness._finalize_all_monsters_dead_preview_tail(battle, summary, debug)

        assert finalized is summary
        assert finalized["turns"] == 2
        assert debug["battle_overrun_reason"] == "all_monsters_dead_preview_tail"
        assert debug["battle_terminal_reason"] == "all_monsters_dead"
        assert debug["battle_terminal_after_action_turn"] == 1
        assert debug["python_turn_count"] == 2

    def test_play_logged_battle_proxy_exploder_attack_self_destructs(self) -> None:
        engine = RunEngine.create("PHASE31EXPLODER", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.start_combat_with_monsters(["Exploder"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Exploder", ending_hp=0)],
            turn_count=1,
            player_end_hp=72,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "Exploder", "intent": "ATTACK", "move_index": 1, "base_damage": 9}],
            },
            max_turns=2,
        )

        assert result["debug"].get("battle_proxy_monster_resolution_used") is not True
        assert result["summary"] is not None
        assert result["summary"]["monster_end_hp"] == [0]

    def test_play_logged_battle_records_status_cards_by_turn_for_sentry(self) -> None:
        engine = RunEngine.create("PHASE32SENTRYSTATUS", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.start_combat_with_monsters(["Sentry"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoomElite",
            monsters=[SimpleNamespace(id="Sentry", ending_hp=34)],
            turn_count=1,
            player_end_hp=80,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoomElite",
            logged_intents_by_turn={
                0: [{"monster_id": "Sentry", "intent": "DEBUFF", "move_index": 3, "base_damage": 0}],
            },
            max_turns=2,
        )

        debug = result["debug"]
        assert debug["python_status_cards_by_turn"][0]["Dazed"] >= 2
        assert "monster_debuff_desync_turn" not in debug

    def test_play_logged_battle_records_player_debuffs_by_turn_for_acid_slime(self) -> None:
        engine = RunEngine.create("PHASE32ACIDDEBUFF", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.start_combat_with_monsters(["AcidSlimeMedium"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="AcidSlimeMedium", ending_hp=32)],
            turn_count=1,
            player_end_hp=80,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "AcidSlimeMedium", "intent": "DEBUFF", "move_index": 4, "base_damage": 0}],
            },
            max_turns=2,
        )

        assert result["debug"]["python_player_debuffs_by_turn"][0]["Weak"] >= 1
        assert "monster_debuff_desync_turn" not in result["debug"]

    def test_play_logged_battle_records_player_debuffs_by_turn_for_spike_slime_medium(self) -> None:
        engine = RunEngine.create("PHASE66SPIKEDEBUFF", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.start_combat_with_monsters(["SpikeSlimeMedium"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="SpikeSlime_M", ending_hp=32)],
            turn_count=1,
            player_end_hp=80,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "SpikeSlimeMedium", "intent": "DEBUFF", "move_index": 4, "base_damage": 0}],
            },
            max_turns=2,
        )

        assert result["debug"]["python_player_debuffs_by_turn"][0]["Weak"] >= 1
        assert "monster_debuff_desync_turn" not in result["debug"]

    def test_play_logged_battle_runtime_cultist_uses_intent_not_move_id(self) -> None:
        engine = RunEngine.create("PHASE33CULTISTINTENT", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.state.player_hp = 80
        engine.state.player_max_hp = 80
        engine.start_combat_with_monsters(["Cultist"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Cultist", ending_hp=48)],
            turn_count=1,
            player_end_hp=74,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "Cultist", "intent": "ATTACK", "move_index": 99, "base_damage": 6}],
            },
            max_turns=2,
        )

        turn0 = result["debug"]["python_monster_outcomes_by_turn"][0]
        assert turn0["resolved_attack_damage_total"] == 6

    def test_play_logged_battle_runtime_sentry_uses_intent_not_move_id(self) -> None:
        engine = RunEngine.create("PHASE33SENTRYINTENT", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.start_combat_with_monsters(["Sentry"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoomElite",
            monsters=[SimpleNamespace(id="Sentry", ending_hp=38)],
            turn_count=1,
            player_end_hp=80,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoomElite",
            logged_intents_by_turn={
                0: [{"monster_id": "Sentry", "intent": "DEBUFF", "move_index": 99, "base_damage": 0}],
            },
            max_turns=2,
        )

        assert result["debug"]["python_status_cards_by_turn"][0]["Dazed"] >= 2

    def test_configure_logged_monster_turn_stabilizes_same_id_sentry_first_turn_lane(self) -> None:
        class _FakeMonster:
            def __init__(self, intent: MonsterIntent) -> None:
                self.id = "Sentry"
                self.next_move = MonsterMove(3 if intent == MonsterIntent.DEBUFF else 4, intent, 9)

            def is_dead(self) -> bool:
                return False

        monsters = [
            _FakeMonster(MonsterIntent.DEBUFF),
            _FakeMonster(MonsterIntent.ATTACK),
            _FakeMonster(MonsterIntent.DEBUFF),
        ]
        engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(monsters=monsters),
                )
            )
        )

        replay_debug: dict[str, object] = {"battle_same_id_sentry_intent_lane_by_turn": {}}
        lane_state: dict[int, str] = {}
        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "Sentry", "intent": "DEBUFF", "move_index": 3, "base_damage": 0},
                {"monster_id": "Sentry", "intent": "ATTACK", "move_index": 4, "base_damage": 9},
                {"monster_id": "Sentry", "intent": "DEBUFF", "move_index": 3, "base_damage": 0},
            ],
            replay_debug,
            java_turn=0,
            same_id_sentry_lane_state=lane_state,
        )

        assert expected == [
            {"monster_id": "Sentry", "intent": "DEBUFF", "base_damage": 0, "hits": 1},
            {"monster_id": "Sentry", "intent": "ATTACK", "base_damage": 9, "hits": 1},
            {"monster_id": "Sentry", "intent": "DEBUFF", "base_damage": 0, "hits": 1},
        ]
        assert lane_state == {0: "DEBUFF", 1: "ATTACK", 2: "DEBUFF"}
        assert replay_debug["battle_same_id_sentry_intent_lane_by_turn"][0] == [
            {"java_turn": 0, "monster_idx": 0, "monster_id": "Sentry", "assigned_intent": "DEBUFF", "lane_source": "first_move_parity"},
            {"java_turn": 0, "monster_idx": 1, "monster_id": "Sentry", "assigned_intent": "ATTACK", "lane_source": "first_move_parity"},
            {"java_turn": 0, "monster_idx": 2, "monster_id": "Sentry", "assigned_intent": "DEBUFF", "lane_source": "first_move_parity"},
        ]

    def test_configure_logged_monster_turn_keeps_same_id_sentry_lane_for_two_alive_survivors(self) -> None:
        class _FakeMonster:
            def __init__(self, hp: int, intent: MonsterIntent) -> None:
                self.id = "Sentry"
                self.hp = hp
                self.is_dying = hp <= 0
                self.next_move = MonsterMove(3 if intent == MonsterIntent.DEBUFF else 4, intent, 9)

            def is_dead(self) -> bool:
                return self.hp <= 0 or self.is_dying

        monsters = [
            _FakeMonster(0, MonsterIntent.DEBUFF),
            _FakeMonster(42, MonsterIntent.ATTACK),
            _FakeMonster(41, MonsterIntent.DEBUFF),
        ]
        engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(monsters=monsters),
                )
            )
        )

        replay_debug: dict[str, object] = {"battle_same_id_sentry_intent_lane_by_turn": {}}
        lane_state: dict[int, str] = {0: "DEBUFF", 1: "ATTACK", 2: "DEBUFF"}
        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "Sentry", "intent": "DEBUFF", "move_index": 3, "base_damage": 0},
                {"monster_id": "Sentry", "intent": "ATTACK", "move_index": 4, "base_damage": 9},
            ],
            replay_debug,
            java_turn=1,
            same_id_sentry_lane_state=lane_state,
        )

        assert expected == [
            {"monster_id": "Sentry", "intent": "ATTACK", "base_damage": 9, "hits": 1},
            {"monster_id": "Sentry", "intent": "DEBUFF", "base_damage": 0, "hits": 1},
        ]
        assert lane_state == {1: "ATTACK", 2: "DEBUFF"}
        assert replay_debug["battle_same_id_sentry_intent_lane_by_turn"][1] == [
            {"java_turn": 1, "monster_idx": 1, "monster_id": "Sentry", "assigned_intent": "ATTACK", "lane_source": "previous_lane"},
            {"java_turn": 1, "monster_idx": 2, "monster_id": "Sentry", "assigned_intent": "DEBUFF", "lane_source": "previous_lane"},
        ]

    def test_configure_logged_monster_turn_skips_same_id_lane_resolver_for_non_sentry_group(self) -> None:
        class _FakeMonster:
            def __init__(self) -> None:
                self.id = "Repulsor"
                self.next_move = MonsterMove(1, MonsterIntent.DEBUFF, 0)

            def is_dead(self) -> bool:
                return False

        monsters = [_FakeMonster(), _FakeMonster(), _FakeMonster()]
        engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(monsters=monsters),
                )
            )
        )

        replay_debug: dict[str, object] = {"battle_same_id_sentry_intent_lane_by_turn": {}}
        lane_state: dict[int, str] = {}
        harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "Repulsor", "intent": "DEBUFF", "move_index": 1, "base_damage": 0},
                {"monster_id": "Repulsor", "intent": "ATTACK", "move_index": 2, "base_damage": 13},
                {"monster_id": "Repulsor", "intent": "DEBUFF", "move_index": 1, "base_damage": 0},
            ],
            replay_debug,
            java_turn=0,
            same_id_sentry_lane_state=lane_state,
        )

        assert replay_debug["battle_same_id_sentry_intent_lane_by_turn"] == {}
        assert lane_state == {}

    def test_configure_logged_monster_turn_stabilizes_same_id_jawworm_first_turn_lane(self) -> None:
        class _FakeMonster:
            def __init__(self, intent: MonsterIntent) -> None:
                self.id = "JawWorm"
                self.next_move = MonsterMove(1, intent, 11)

            def is_dead(self) -> bool:
                return False

        monsters = [
            _FakeMonster(MonsterIntent.ATTACK),
            _FakeMonster(MonsterIntent.ATTACK_DEFEND),
            _FakeMonster(MonsterIntent.DEFEND_BUFF),
        ]
        engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(monsters=monsters),
                )
            )
        )

        replay_debug: dict[str, object] = {
            "battle_same_id_jawworm_intent_lane_by_turn": {},
            "battle_jawworm_lane_collapse_by_turn": {},
        }
        lane_state: dict[int, int] = {}
        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "JawWorm", "intent": "ATTACK_DEFEND", "move_index": 3, "base_damage": 7},
                {"monster_id": "JawWorm", "intent": "ATTACK", "move_index": 1, "base_damage": 11},
                {"monster_id": "JawWorm", "intent": "DEFEND_BUFF", "move_index": 2, "base_damage": 0},
            ],
            replay_debug,
            java_turn=0,
            room_type="MonsterRoom",
            same_id_jawworm_lane_state=lane_state,
        )

        assert expected == [
            {"monster_id": "JawWorm", "intent": "ATTACK_DEFEND", "base_damage": 7, "hits": 1},
            {"monster_id": "JawWorm", "intent": "ATTACK", "base_damage": 11, "hits": 1},
            {"monster_id": "JawWorm", "intent": "DEFEND_BUFF", "base_damage": 0, "hits": 1},
        ]
        assert lane_state == {0: 0, 1: 1, 2: 2}
        assert replay_debug["battle_same_id_jawworm_intent_lane_by_turn"][0] == [
            {
                "java_turn": 0,
                "monster_idx": 0,
                "monster_id": "JawWorm",
                "assigned_intent": "ATTACK_DEFEND",
                "lane_source": "runtime_index",
                "prior_lane_position": None,
                "resolved_lane_position": 0,
                "selected_logged_lane_position": 0,
            },
            {
                "java_turn": 0,
                "monster_idx": 1,
                "monster_id": "JawWorm",
                "assigned_intent": "ATTACK",
                "lane_source": "runtime_index",
                "prior_lane_position": None,
                "resolved_lane_position": 1,
                "selected_logged_lane_position": 1,
            },
            {
                "java_turn": 0,
                "monster_idx": 2,
                "monster_id": "JawWorm",
                "assigned_intent": "DEFEND_BUFF",
                "lane_source": "runtime_index",
                "prior_lane_position": None,
                "resolved_lane_position": 2,
                "selected_logged_lane_position": 2,
            },
        ]
        assert replay_debug["battle_jawworm_lane_collapse_by_turn"] == {}

    def test_configure_logged_monster_turn_collapses_same_id_jawworm_lane_after_death(self) -> None:
        class _FakeMonster:
            def __init__(self, hp: int, intent: MonsterIntent) -> None:
                self.id = "JawWorm"
                self.hp = hp
                self.is_dying = hp <= 0
                self.next_move = MonsterMove(1, intent, 11)

            def is_dead(self) -> bool:
                return self.hp <= 0 or self.is_dying

        monsters = [
            _FakeMonster(0, MonsterIntent.ATTACK),
            _FakeMonster(40, MonsterIntent.ATTACK_DEFEND),
            _FakeMonster(39, MonsterIntent.DEFEND_BUFF),
        ]
        engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(monsters=monsters),
                )
            )
        )

        replay_debug: dict[str, object] = {
            "battle_same_id_jawworm_intent_lane_by_turn": {},
            "battle_jawworm_lane_collapse_by_turn": {},
        }
        lane_state: dict[int, int] = {0: 0, 1: 1, 2: 2}
        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "JawWorm", "intent": "ATTACK", "move_index": 1, "base_damage": 11},
                {"monster_id": "JawWorm", "intent": "DEFEND_BUFF", "move_index": 2, "base_damage": 0},
            ],
            replay_debug,
            java_turn=1,
            room_type="MonsterRoom",
            same_id_jawworm_lane_state=lane_state,
        )

        assert expected == [
            {"monster_id": "JawWorm", "intent": "ATTACK", "base_damage": 11, "hits": 1},
            {"monster_id": "JawWorm", "intent": "DEFEND_BUFF", "base_damage": 0, "hits": 1},
        ]
        assert lane_state == {1: 0, 2: 1}
        assert replay_debug["battle_same_id_jawworm_intent_lane_by_turn"][1] == [
            {
                "java_turn": 1,
                "monster_idx": 1,
                "monster_id": "JawWorm",
                "assigned_intent": "ATTACK",
                "lane_source": "lane_collapse",
                "prior_lane_position": 1,
                "resolved_lane_position": 0,
                "selected_logged_lane_position": 0,
            },
            {
                "java_turn": 1,
                "monster_idx": 2,
                "monster_id": "JawWorm",
                "assigned_intent": "DEFEND_BUFF",
                "lane_source": "lane_collapse",
                "prior_lane_position": 2,
                "resolved_lane_position": 1,
                "selected_logged_lane_position": 1,
            },
        ]
        assert replay_debug["battle_jawworm_lane_collapse_by_turn"][1] == [
            {
                "monster_idx": 0,
                "prior_lane_position": 0,
                "monster_id": "JawWorm",
            }
        ]

    def test_configure_logged_monster_turn_binds_same_id_jawworm_replay_resolution(self) -> None:
        engine = RunEngine.create("PHASE92JAWWORMLANE", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["JawWorm", "JawWorm", "JawWorm"])
        combat = engine.state.combat
        assert combat is not None
        player = combat.state.player
        player.hp = 80
        player.block = 0

        replay_debug: dict[str, object] = {
            "battle_same_id_jawworm_intent_lane_by_turn": {},
            "battle_jawworm_replay_move_resolution_by_turn": {},
            "battle_jawworm_lane_collapse_by_turn": {},
        }
        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "JawWorm", "intent": "ATTACK_DEFEND", "move_index": 3, "base_damage": 7},
                {"monster_id": "JawWorm", "intent": "DEFEND_BUFF", "move_index": 2, "base_damage": 0},
                {"monster_id": "JawWorm", "intent": "ATTACK", "move_index": 1, "base_damage": 11},
            ],
            replay_debug,
            java_turn=0,
            room_type="MonsterRoom",
            same_id_jawworm_lane_state={},
        )

        for monster in combat.state.monsters:
            monster.take_turn(player)

        assert expected == [
            {"monster_id": "JawWorm", "intent": "ATTACK_DEFEND", "base_damage": 7, "hits": 1},
            {"monster_id": "JawWorm", "intent": "DEFEND_BUFF", "base_damage": 0, "hits": 1},
            {"monster_id": "JawWorm", "intent": "ATTACK", "base_damage": 11, "hits": 1},
        ]
        assert player.hp == 62
        assert combat.state.monsters[0].block == 5
        assert combat.state.monsters[1].block == 6
        assert combat.state.monsters[1].strength == 3
        assert replay_debug["battle_jawworm_replay_move_resolution_by_turn"][0] == [
            {
                "java_turn": 0,
                "monster_id": "JawWorm",
                "move_index": 3,
                "logged_intent": "ATTACK_DEFEND",
                "resolved_intent": "ATTACK_DEFEND",
                "configured_base_damage": 7,
                "resolution_source": "jawworm_same_id_replay_lane",
            },
            {
                "java_turn": 0,
                "monster_id": "JawWorm",
                "move_index": 2,
                "logged_intent": "DEFEND_BUFF",
                "resolved_intent": "DEFEND_BUFF",
                "configured_base_damage": 0,
                "resolution_source": "jawworm_same_id_replay_lane",
            },
            {
                "java_turn": 0,
                "monster_id": "JawWorm",
                "move_index": 1,
                "logged_intent": "ATTACK",
                "resolved_intent": "ATTACK",
                "configured_base_damage": 11,
                "resolution_source": "jawworm_same_id_replay_lane",
            },
        ]

    def test_configure_logged_monster_turn_skips_same_id_jawworm_lane_for_non_triplet_group(self) -> None:
        class _FakeMonster:
            def __init__(self) -> None:
                self.id = "JawWorm"
                self.next_move = MonsterMove(1, MonsterIntent.ATTACK, 11)

            def is_dead(self) -> bool:
                return False

        monsters = [_FakeMonster(), _FakeMonster()]
        engine = SimpleNamespace(
            state=SimpleNamespace(
                combat=SimpleNamespace(
                    state=SimpleNamespace(monsters=monsters),
                )
            )
        )

        replay_debug: dict[str, object] = {
            "battle_same_id_jawworm_intent_lane_by_turn": {},
            "battle_jawworm_replay_move_resolution_by_turn": {},
            "battle_jawworm_lane_collapse_by_turn": {},
        }
        lane_state: dict[int, int] = {}
        harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "JawWorm", "intent": "ATTACK", "move_index": 1, "base_damage": 11},
                {"monster_id": "JawWorm", "intent": "DEFEND_BUFF", "move_index": 2, "base_damage": 0},
            ],
            replay_debug,
            java_turn=0,
            room_type="MonsterRoom",
            same_id_jawworm_lane_state=lane_state,
        )

        assert replay_debug["battle_same_id_jawworm_intent_lane_by_turn"] == {}
        assert replay_debug["battle_jawworm_replay_move_resolution_by_turn"] == {}
        assert replay_debug["battle_jawworm_lane_collapse_by_turn"] == {}
        assert lane_state == {}

    def test_play_logged_battle_marks_debuff_desync_when_runtime_applies_no_effect(self) -> None:
        engine = RunEngine.create("PHASE32DEBUFFDESYNC", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.start_combat_with_monsters(["Cultist"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Cultist", ending_hp=50)],
            turn_count=1,
            player_end_hp=80,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "Cultist", "intent": "DEBUFF", "move_index": 99, "base_damage": 0}],
            },
            max_turns=2,
        )

        assert result["debug"]["monster_debuff_desync_turn"] == 0

    def test_play_logged_battle_marks_finish_desync_when_logged_turns_exhaust(self) -> None:
        engine = RunEngine.create("PHASE32FINISHDESYNC", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.start_combat_with_monsters(["Cultist"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Cultist", ending_hp=50)],
            turn_count=1,
            player_end_hp=74,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "Cultist", "intent": "ATTACK", "move_index": 1, "base_damage": 6}],
            },
            max_turns=2,
        )

        assert result["debug"]["battle_replay_abort_reason"] == "logged_turns_exhausted"
        assert result["debug"]["battle_finish_desync_turn"] == 0

    def test_play_logged_battle_records_player_phase_debug_views(self) -> None:
        engine = RunEngine.create("PHASE48PLAYERDEBUG", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.start_combat_with_monsters(["Cultist"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Cultist", ending_hp=48)],
            turn_count=1,
            player_end_hp=74,
            cards_played=[SimpleNamespace(turn=0, card_id="Inflame", cost=1, upgraded=False)],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "Cultist", "intent": "ATTACK", "move_index": 1, "base_damage": 6}],
            },
            max_turns=2,
        )

        debug = result["debug"]
        assert 0 in debug["python_hand_before_logged_plays_by_turn"]
        assert isinstance(debug["python_energy_before_logged_plays_by_turn"][0], int)
        assert 0 in debug["python_cards_played_by_turn"]
        assert debug["battle_required_cards_missing_by_turn"][0][0]["card_id"] == "Inflame"

    def test_chosen_runtime_hex_adds_status_card_with_replay_local_resolution(self) -> None:
        engine = RunEngine.create("PHASE32CHOSENHEX", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.start_combat_with_monsters(["Chosen"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Chosen", ending_hp=95)],
            turn_count=1,
            player_end_hp=80,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "Chosen", "intent": "DEBUFF", "move_index": 4, "base_damage": 0}],
            },
            max_turns=2,
        )

        assert result["debug"]["python_status_cards_by_turn"][0]["Dazed"] >= 1
        assert result["debug"]["battle_proxy_monster_resolution_used"] is True

    def test_configure_logged_monster_turn_uses_replay_local_resolution_for_chosen_attack_shape(self) -> None:
        engine = RunEngine.create("PHASE62CHOSENATTACK", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.state.player_hp = 80
        engine.state.player_max_hp = 80
        engine.start_combat_with_monsters(["Chosen"])

        replay_debug: dict[str, object] = {}
        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "Chosen", "intent": "ATTACK", "move_index": 5, "base_damage": 5},
            ],
            replay_debug,
            java_turn=0,
        )

        combat = engine.state.combat
        assert combat is not None
        player = combat.state.player
        hp_before = player.hp
        for monster in combat.state.monsters:
            if monster.is_dead():
                continue
            monster.take_turn(player)

        assert hp_before - player.hp == 5
        assert expected == [
            {"monster_id": "Chosen", "intent": "ATTACK", "base_damage": 5, "hits": 1},
        ]
        assert replay_debug["battle_proxy_monster_resolution_used"] is True

    def test_configure_logged_monster_turn_uses_replay_local_resolution_for_spike_slime_attack_debuff(self) -> None:
        engine = RunEngine.create("PHASE66SPIKEATTACKDEBUFF", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.state.player_hp = 80
        engine.state.player_max_hp = 80
        engine.start_combat_with_monsters(["SpikeSlimeMedium"])

        combat = engine.state.combat
        assert combat is not None
        monster = combat.state.monsters[0]
        monster.set_move(MonsterMove(1, MonsterIntent.ATTACK, 8, name="Flame Tackle"))

        replay_debug: dict[str, object] = {}
        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "SpikeSlimeMedium", "intent": "ATTACK_DEBUFF", "move_index": 1, "base_damage": 0},
            ],
            replay_debug,
            java_turn=0,
        )

        player = combat.state.player
        hp_before = player.hp
        weak_before = player.powers.get_power_amount("Weak")
        monster.take_turn(player)

        assert player.hp < hp_before
        assert player.powers.get_power_amount("Weak") >= weak_before + 1
        assert expected == [
            {"monster_id": "SpikeSlimeMedium", "intent": "ATTACK_DEBUFF", "base_damage": 8, "hits": 1},
        ]
        assert replay_debug["battle_proxy_monster_resolution_used"] is True
        assert replay_debug["battle_replay_local_damage_source_by_turn"][0][0]["source"] == "runtime_attack_family_damage"
        assert replay_debug["battle_proxy_damage_fallback_reason"][0][0]["reason"] == (
            "logged_zero_runtime_attack_family_positive_damage"
        )

    def test_configure_logged_monster_turn_uses_spike_slime_local_damage_fallback_when_runtime_is_defend(self) -> None:
        engine = RunEngine.create("PHASE67SPIKEATTACKDEFEND", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.state.player_hp = 80
        engine.state.player_max_hp = 80
        engine.start_combat_with_monsters(["SpikeSlimeMedium"])

        combat = engine.state.combat
        assert combat is not None
        monster = combat.state.monsters[0]
        monster.set_move(MonsterMove(1, MonsterIntent.DEFEND, 0, name="Flame Tackle"))
        monster.get_intent_damage = lambda: 0

        replay_debug: dict[str, object] = {
            "battle_replay_local_damage_source_by_turn": {},
            "battle_proxy_damage_fallback_reason": {},
        }
        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "SpikeSlimeMedium", "intent": "ATTACK_DEBUFF", "move_index": 1, "base_damage": 0},
            ],
            replay_debug,
            java_turn=0,
        )

        player = combat.state.player
        hp_before = player.hp
        weak_before = player.powers.get_power_amount("Weak")
        monster.take_turn(player)

        assert hp_before - player.hp == 10
        assert player.powers.get_power_amount("Weak") >= weak_before + 1
        assert expected == [
            {"monster_id": "SpikeSlimeMedium", "intent": "ATTACK_DEBUFF", "base_damage": 10, "hits": 1},
        ]
        assert replay_debug["battle_replay_local_damage_source_by_turn"][0][0]["source"] == (
            "monster_local_move_shape_damage"
        )
        assert replay_debug["battle_proxy_damage_fallback_reason"][0][0]["reason"] == (
            "monster_local_shape_attack_family_fallback"
        )

    def test_combat_play_card_handles_second_wind_from_non_leading_hand_index(self) -> None:
        engine = RunEngine.create("PHASE63SECONDWINDPLAY", ascension=0)
        engine.state.deck = ["Strike", "Defend", "SecondWind", "ShrugItOff", "Bash"]
        engine.start_combat_with_monsters(["JawWorm"])

        combat = engine.state.combat
        assert combat is not None
        cm = combat.state.card_manager
        assert cm is not None
        cm.hand.cards = [
            CardInstance(card_id="Strike"),
            CardInstance(card_id="Defend"),
            CardInstance(card_id="SecondWind"),
            CardInstance(card_id="ShrugItOff"),
        ]
        combat.state.player.energy = 3
        cm.set_energy(3)

        assert engine.combat_play_card(2, None) is True
        assert [card.card_id for card in cm.hand.cards] == ["Strike"]
        assert [card.card_id for card in cm.discard_pile.cards] == ["SecondWind"]
        assert [card.card_id for card in cm.exhaust_pile.cards] == ["Defend", "ShrugItOff"]

    def test_configure_logged_monster_turn_keeps_chosen_strong_debuff_non_attack_shape(self) -> None:
        engine = RunEngine.create("PHASE62CHOSENDEBUFF", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.state.player_hp = 80
        engine.state.player_max_hp = 80
        engine.start_combat_with_monsters(["Chosen"])

        combat = engine.state.combat
        assert combat is not None
        for monster in combat.state.monsters:
            monster.next_move = MonsterMove(move_id=1, intent=MonsterIntent.ATTACK, base_damage=18)

        replay_debug: dict[str, object] = {}
        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "Chosen", "intent": "STRONG_DEBUFF", "move_index": 4, "base_damage": 0},
            ],
            replay_debug,
            java_turn=0,
        )

        player = combat.state.player
        hp_before = player.hp
        for monster in combat.state.monsters:
            if monster.is_dead():
                continue
            monster.take_turn(player)

        assert player.hp == hp_before
        assert expected == [
            {"monster_id": "Chosen", "intent": "STRONG_DEBUFF", "base_damage": 0, "hits": 1},
        ]
        assert replay_debug["battle_proxy_monster_resolution_used"] is True

    def test_configure_logged_monster_turn_uses_writhingmass_attack_debuff_shape_fallback(self) -> None:
        engine = RunEngine.create("PHASE62WRITHING", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.state.player_hp = 80
        engine.state.player_max_hp = 80
        engine.start_combat_with_monsters(["WrithingMass"])

        replay_debug: dict[str, object] = {
            "battle_replay_local_damage_source_by_turn": {},
            "battle_proxy_damage_fallback_reason": {},
            "battle_writhingmass_replay_move_resolution_by_turn": {},
        }
        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "WrithingMass", "intent": "ATTACK_DEBUFF", "move_index": 3, "base_damage": 0},
            ],
            replay_debug,
            java_turn=0,
        )

        combat = engine.state.combat
        assert combat is not None
        player = combat.state.player
        hp_before = player.hp
        for monster in combat.state.monsters:
            if monster.is_dead():
                continue
            monster.take_turn(player)

        assert hp_before - player.hp == 10
        assert expected == [
            {"monster_id": "WrithingMass", "intent": "ATTACK_DEBUFF", "base_damage": 0, "hits": 1},
        ]

    def test_play_logged_battle_does_not_expand_spike_slime_fix_to_slaverblue_orbwalker_or_repulsor(self) -> None:
        scenarios = [
            ("OrbWalker", "MonsterRoom", {"monster_id": "OrbWalker", "intent": "ATTACK_DEBUFF", "move_index": 1, "base_damage": 0}),
            ("Repulsor", "MonsterRoomElite", {"monster_id": "Repulsor", "intent": "DEBUFF", "move_index": 1, "base_damage": 0}),
        ]

        for encounter_name, room_type, logged_intent in scenarios:
            engine = RunEngine.create(f"PHASE66WATCH{encounter_name.upper()}", ascension=0)
            engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
            engine.start_combat_with_monsters([encounter_name])

            battle = SimpleNamespace(
                floor=1,
                room_type=room_type,
                monsters=[SimpleNamespace(id=logged_intent["monster_id"], ending_hp=40)],
                turn_count=1,
                player_end_hp=80,
                cards_played=[],
                rng_state_end=None,
            )

            result = harness._play_logged_battle(
                engine,
                battle,
                room_type=room_type,
                logged_intents_by_turn={0: [logged_intent]},
                max_turns=2,
            )

            assert result["debug"]["python_player_debuffs_by_turn"][0].get("Weak", 0) == 0

    def test_create_replay_monster_uses_concrete_spiker_and_repulsor_classes(self) -> None:
        hp_rng = MutableRNG.from_seed(987654321, counter=0)

        spiker, spiker_debug = _create_replay_monster("Spiker", hp_rng, 0, act=3)
        repulsor, repulsor_debug = _create_replay_monster("Repulsor", hp_rng, 0, act=3)

        assert isinstance(spiker, Spiker)
        assert isinstance(repulsor, Repulsor)
        assert not isinstance(spiker, GenericMonsterProxy)
        assert not isinstance(repulsor, GenericMonsterProxy)
        assert spiker_debug.get("used_proxy") is not True
        assert repulsor_debug.get("used_proxy") is not True

    def test_spiker_create_bootstrap_starts_with_thorns(self) -> None:
        monster = Spiker.create(MutableRNG.from_seed(1234, counter=0), ascension=0)

        assert 42 <= monster.hp <= 56
        assert monster.get_power_amount("Thorns") == 3
        assert monster.thorns_count == 3

    def test_spiker_buff_move_adds_two_thorns_without_sharp_hide(self) -> None:
        monster = Spiker.create(MutableRNG.from_seed(1234, counter=0), ascension=0)
        player = SimpleNamespace(take_damage=lambda amount: None)
        thorns_before = monster.get_power_amount("Thorns")
        monster.set_move(MonsterMove(2, MonsterIntent.BUFF, 0, name="Spike"))

        monster.take_turn(player)

        assert monster.get_power_amount("Thorns") == thorns_before + 2
        assert monster.has_power("Sharp Hide") is False

    def test_repulsor_debuff_adds_two_dazed_to_draw_pile(self) -> None:
        engine = RunEngine.create("PHASE90REPULSORDAZED", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Repulsor"])
        combat = engine.state.combat
        assert combat is not None

        monster = combat.state.monsters[0]
        monster.set_move(MonsterMove(1, MonsterIntent.DEBUFF, 0, name="Repulse"))
        draw_before = len(combat.state.card_manager.draw_pile.cards)

        monster.take_turn(combat.state.player)

        draw_after = len(combat.state.card_manager.draw_pile.cards)
        assert draw_after - draw_before == 2
        assert [card.card_id for card in combat.state.card_manager.draw_pile.cards][-2:] == ["Dazed", "Dazed"]

    def test_repulsor_attack_move_deals_single_hit_damage(self) -> None:
        monster = Repulsor.create(MutableRNG.from_seed(4321, counter=0), ascension=0)
        player = SimpleNamespace(hp=80, block=0)

        def _take_damage(amount: int) -> None:
            player.hp -= int(amount)

        player.take_damage = _take_damage
        monster.set_move(MonsterMove(2, MonsterIntent.ATTACK, 11, name="Bash"))

        monster.take_turn(player)

        assert player.hp == 69

    def test_configure_logged_monster_turn_uses_ancient_shapes_concrete_replay_lane(self) -> None:
        engine = RunEngine.create("PHASE90ANCIENTSHAPES", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Spiker", "Repulsor", "Repulsor"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {}
        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "Spiker", "intent": "BUFF", "move_index": 2, "base_damage": 0},
                {"monster_id": "Repulsor", "intent": "DEBUFF", "move_index": 1, "base_damage": 0},
                {"monster_id": "Repulsor", "intent": "DEBUFF", "move_index": 1, "base_damage": 0},
            ],
            replay_debug,
            java_turn=0,
        )

        for monster in combat.state.monsters:
            if monster.id == "Spiker":
                thorns_before = monster.get_power_amount("Thorns")
                monster.take_turn(combat.state.player)
                assert monster.get_power_amount("Thorns") == thorns_before + 2

        assert expected == [
            {"monster_id": "Spiker", "intent": "BUFF", "base_damage": 0, "hits": 1},
            {"monster_id": "Repulsor", "intent": "DEBUFF", "base_damage": 0, "hits": 1},
            {"monster_id": "Repulsor", "intent": "DEBUFF", "base_damage": 0, "hits": 1},
        ]
        assert replay_debug["battle_ancientshapes_replay_move_resolution_by_turn"][0][0]["resolution_source"] == (
            "ancient_shapes_concrete_replay_lane"
        )
        assert replay_debug.get("battle_proxy_monster_resolution_used") is None

    def test_configure_logged_monster_turn_applies_slaverblue_attack_debuff_shape(self) -> None:
        engine = RunEngine.create("PHASE74SLAVERBLUEATTACKDEBUFF", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["SlaverBlue"])
        combat = engine.state.combat
        assert combat is not None
        player = combat.state.player
        player.hp = 80
        player.block = 0

        monster = combat.state.monsters[0]
        monster.set_move(MonsterMove(4, MonsterIntent.ATTACK, 10, name="Stab"))
        replay_debug: dict[str, object] = {
            "battle_replay_local_damage_source_by_turn": {},
            "battle_proxy_damage_fallback_reason": {},
        }

        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "SlaverBlue", "intent": "ATTACK_DEBUFF", "move_index": 4, "base_damage": 0},
            ],
            replay_debug,
            java_turn=0,
        )

        hp_before = player.hp
        weak_before = player.powers.get_power_amount("Weak")
        monster.take_turn(player)

        assert hp_before - player.hp == 10
        assert player.powers.get_power_amount("Weak") >= weak_before + 1
        assert expected == [
            {"monster_id": "SlaverBlue", "intent": "ATTACK_DEBUFF", "base_damage": 10, "hits": 1},
        ]
        assert replay_debug["battle_replay_local_damage_source_by_turn"][0][0]["source"] == "runtime_attack_family_damage"
        assert replay_debug["battle_proxy_damage_fallback_reason"][0][0]["reason"] == "logged_zero_runtime_attack_family_positive_damage"

    def test_configure_logged_monster_turn_keeps_slaverblue_attack_debuff_when_runtime_defends(self) -> None:
        engine = RunEngine.create("PHASE74SLAVERBLUEDEFENDDRIFT", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["SlaverBlue"])
        combat = engine.state.combat
        assert combat is not None
        player = combat.state.player
        player.hp = 80
        player.block = 0

        monster = combat.state.monsters[0]
        monster.set_move(MonsterMove(4, MonsterIntent.DEFEND, 0, name="Scrape"))
        replay_debug: dict[str, object] = {
            "battle_replay_local_damage_source_by_turn": {},
            "battle_proxy_damage_fallback_reason": {},
        }

        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "SlaverBlue", "intent": "ATTACK_DEBUFF", "move_index": 4, "base_damage": 0},
            ],
            replay_debug,
            java_turn=0,
        )

        hp_before = player.hp
        weak_before = player.powers.get_power_amount("Weak")
        monster.take_turn(player)

        assert hp_before - player.hp == 10
        assert player.powers.get_power_amount("Weak") >= weak_before + 1
        assert expected == [
            {"monster_id": "SlaverBlue", "intent": "ATTACK_DEBUFF", "base_damage": 10, "hits": 1},
        ]
        assert replay_debug["battle_replay_local_damage_source_by_turn"][0][0]["source"] == "runtime_attack_family_damage"
        assert replay_debug["battle_proxy_damage_fallback_reason"][0][0]["reason"] == "logged_zero_runtime_attack_family_positive_damage"

    def test_spike_slime_debuff_refresh_is_not_marked_as_debuff_desync(self) -> None:
        expected_intents = [{"monster_id": "SpikeSlime_M", "intent": "ATTACK_DEBUFF"}]

        assert harness._is_replay_local_debuff_refresh_applied(expected_intents, {"Weak": 1}) is True
        assert harness._is_replay_local_debuff_refresh_applied(expected_intents, {}) is False
        assert harness._is_replay_local_debuff_refresh_applied(
            [{"monster_id": "Repulsor", "intent": "DEBUFF"}],
            {"Weak": 1},
        ) is False

    def test_slaverblue_debuff_refresh_is_not_marked_as_debuff_desync(self) -> None:
        expected_intents = [{"monster_id": "SlaverBlue", "intent": "ATTACK_DEBUFF"}]

        assert harness._is_replay_local_debuff_refresh_applied(expected_intents, {"Weak": 1}) is True
        assert harness._is_replay_local_debuff_refresh_applied(expected_intents, {}) is False

    def test_create_replay_monster_uses_concrete_slaverblue_class(self) -> None:
        hp_rng = MutableRNG.from_seed(123456789, counter=0)

        monster, debug = _create_replay_monster("SlaverBlue", hp_rng, 0, act=1)

        assert monster is not None
        assert isinstance(monster, SlaverBlue)
        assert not isinstance(monster, GenericMonsterProxy)
        assert debug.get("used_proxy") is not True
        assert monster.id == "SlaverBlue"
        assert 46 <= monster.hp <= 50

    def test_start_combat_with_monsters_uses_concrete_slaverblue_hp_range(self) -> None:
        engine = RunEngine.create("PHASE75SLAVERBLUEFACTORY", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]

        engine.start_combat_with_monsters(["SlaverBlue"])

        combat = engine.state.combat
        assert combat is not None
        monster = combat.state.monsters[0]
        assert isinstance(monster, SlaverBlue)
        assert not isinstance(monster, GenericMonsterProxy)
        assert 46 <= monster.hp <= 50

    def test_resolve_gremlinleader_initial_live_roster_uses_turn_zero_intents(self) -> None:
        bootstrap = harness._resolve_gremlinleader_initial_live_roster(
            "MonsterRoomElite",
            [
                "GremlinFat",
                "GremlinWarrior",
                "GremlinFat",
                "GremlinWarrior",
                "GremlinTsundere",
                "GremlinThief",
                "GremlinLeader",
            ],
            {
                0: [
                    {"monster_id": "GremlinFat"},
                    {"monster_id": "GremlinThief"},
                    {"monster_id": "GremlinLeader"},
                ]
            },
        )

        assert bootstrap is not None
        assert bootstrap["initial_live_roster"] == ["GremlinFat", "GremlinThief", "GremlinLeader"]
        assert bootstrap["pending_spawn_ids"] == [
            "GremlinWarrior",
            "GremlinFat",
            "GremlinWarrior",
            "GremlinTsundere",
        ]

    def test_resolve_gremlinleader_initial_live_roster_does_not_fire_for_other_encounters(self) -> None:
        assert harness._resolve_gremlinleader_initial_live_roster(
            "MonsterRoomElite",
            ["GremlinNob"],
            {0: [{"monster_id": "GremlinNob"}]},
        ) is None

    def test_create_replay_monster_uses_concrete_snecko_class(self) -> None:
        hp_rng = MutableRNG.from_seed(246813579, counter=0)

        snecko, snecko_debug = _create_replay_monster("Snecko", hp_rng, 0, act=2)

        assert isinstance(snecko, Snecko)
        assert not isinstance(snecko, GenericMonsterProxy)
        assert snecko_debug.get("used_proxy") is not True

    def test_snecko_take_turn_supports_glare_and_zero_damage_tail_replay_shape(self) -> None:
        engine = RunEngine.create("PHASE87SNECKO", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Snecko"])
        combat = engine.state.combat
        assert combat is not None

        snecko = combat.state.monsters[0]
        player = combat.state.player

        snecko.set_move(MonsterMove(1, MonsterIntent.STRONG_DEBUFF, 0, name="Glare"))
        snecko.take_turn(player)
        assert player.has_power("Confused")

        hp_before = player.hp
        snecko.set_move(MonsterMove(3, MonsterIntent.ATTACK_DEBUFF, 0, name="Tail Whip"))
        snecko.take_turn(player)
        assert player.hp == hp_before
        assert player.has_power("Vulnerable")

    def test_snecko_turn_zero_rage_is_inferred_into_opening_hand(self) -> None:
        engine = RunEngine.create("PHASE87SNECKORAGE", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Snecko"])
        combat = engine.state.combat
        assert combat is not None
        card_manager = combat.state.card_manager
        assert card_manager is not None

        card_manager.hand.cards = [
            CardInstance(card_id="Defend"),
            CardInstance(card_id="Strike"),
            CardInstance(card_id="Strike"),
            CardInstance(card_id="ShrugItOff"),
            CardInstance(card_id="Immolate"),
        ]
        card_manager.draw_pile.cards = []
        replay_debug: dict[str, object] = {}

        assert harness._maybe_infer_snecko_turn_zero_rage_opening_hand(
            engine,
            card_manager,
            [
                SimpleNamespace(card_id="Rage", cost=0, upgraded=False),
                SimpleNamespace(card_id="Shrug It Off", cost=1, upgraded=False),
                SimpleNamespace(card_id="Immolate", cost=2, upgraded=False),
                SimpleNamespace(card_id="Strike_R", cost=1, upgraded=False),
            ],
            room_type="MonsterRoom",
            java_turn=0,
            replay_debug=replay_debug,
            next_turn_logged_cards=[],
        ) is True
        assert "Rage" in [card.card_id for card in card_manager.get_hand()]
        assert replay_debug["battle_snecko_opening_hand_inferred_cards"][0][0]["card_id"] == "Rage"
        assert replay_debug["battle_snecko_opening_hand_inferred_cards"][0][0]["source"] == "replay_local_inferred_opening_hand"

    def test_snecko_turn_zero_rage_inference_does_not_fire_for_other_encounters(self) -> None:
        engine = RunEngine.create("PHASE87NOSNECKO", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Cultist"])
        combat = engine.state.combat
        assert combat is not None
        card_manager = combat.state.card_manager
        assert card_manager is not None

        assert harness._maybe_infer_snecko_turn_zero_rage_opening_hand(
            engine,
            card_manager,
            [SimpleNamespace(card_id="Rage", cost=0, upgraded=False)],
            room_type="MonsterRoom",
            java_turn=0,
            replay_debug={},
            next_turn_logged_cards=[],
        ) is False

    def test_create_replay_monster_uses_concrete_nemesis_class(self) -> None:
        hp_rng = MutableRNG.from_seed(1357913579, counter=0)

        monster, debug = _create_replay_monster("Nemesis", hp_rng, 0, act=3)

        assert monster is not None
        assert isinstance(monster, Nemesis)
        assert not isinstance(monster, GenericMonsterProxy)
        assert debug.get("used_proxy") is not True

    def test_nemesis_take_turn_supports_tri_attack_scythe_burns_and_end_turn_intangible(self) -> None:
        engine = RunEngine.create("PHASE93NEMESIS", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Nemesis"])
        combat = engine.state.combat
        assert combat is not None

        nemesis = combat.state.monsters[0]
        player = combat.state.player
        player.hp = 80
        player.block = 0

        nemesis.set_move(MonsterMove(2, MonsterIntent.ATTACK, 6, multiplier=3, is_multi_damage=True, name="Debilitate"))
        nemesis.take_turn(player)
        assert player.hp == 62
        assert nemesis.get_power_amount("Intangible") == 1

        nemesis.remove_power("Intangible")
        nemesis.set_move(MonsterMove(3, MonsterIntent.ATTACK, 45, name="Scythe"))
        nemesis.take_turn(player)
        assert player.hp == 17
        assert nemesis.get_power_amount("Intangible") == 1

        nemesis.remove_power("Intangible")
        discard_before = len(combat.state.card_manager.discard_pile.cards)
        nemesis.set_move(MonsterMove(4, MonsterIntent.DEBUFF, 0, name="Burning Pact"))
        nemesis.take_turn(player)
        discard_after = len(combat.state.card_manager.discard_pile.cards)
        assert discard_after - discard_before == nemesis.burn_count
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards][-nemesis.burn_count :] == [
            "Burn"
        ] * nemesis.burn_count
        assert nemesis.get_power_amount("Intangible") == 1

    def test_nemesis_intangible_clamps_incoming_damage_to_one(self) -> None:
        monster = Nemesis.create(MutableRNG.from_seed(97531, counter=0), ascension=0)
        monster.add_power(create_power("Intangible", 1, monster.id))
        hp_before = monster.hp

        monster.take_damage(10)

        assert hp_before - monster.hp == 1

    def test_select_monster_intent_batch_for_turn_uses_single_nemesis_logged_progression_guard(self) -> None:
        engine = RunEngine.create("PHASE93NEMESISBATCH", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Nemesis"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {}
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[{"monster_id": "Nemesis", "intent": "ATTACK", "move_index": 2, "base_damage": 6, "ai_rng_counter": 2}],
            action_intents=[{"monster_id": "Nemesis", "intent": "DEBUFF", "move_index": 4, "base_damage": 0, "ai_rng_counter": 4}],
            replay_debug=replay_debug,
        )

        assert selected == [{"monster_id": "Nemesis", "intent": "ATTACK", "move_index": 2, "base_damage": 6, "ai_rng_counter": 2}]
        assert replay_debug["battle_action_batch_fallback_turn"] == 1
        assert replay_debug["battle_action_batch_apply_reason"] == [
            {"turn": 1, "reason": "single_nemesis_logged_progression_guard", "used_action_batch": False}
        ]
        assert replay_debug["battle_nemesis_action_batch_fallback"][1]["reason"] == (
            "single_nemesis_logged_progression_guard"
        )

    def test_select_monster_intent_batch_for_turn_skips_nemesis_guard_without_ahead_ai_progression(self) -> None:
        engine = RunEngine.create("PHASE93NEMESISNOGUARD", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Nemesis"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {}
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[{"monster_id": "Nemesis", "intent": "ATTACK", "move_index": 2, "base_damage": 6, "ai_rng_counter": 4}],
            action_intents=[{"monster_id": "Nemesis", "intent": "DEBUFF", "move_index": 4, "base_damage": 0, "ai_rng_counter": 4}],
            replay_debug=replay_debug,
        )

        assert selected == [{"monster_id": "Nemesis", "intent": "DEBUFF", "move_index": 4, "base_damage": 0, "ai_rng_counter": 4}]
        assert "battle_nemesis_action_batch_fallback" not in replay_debug

    def test_configure_logged_monster_turn_binds_single_nemesis_replay_resolution(self) -> None:
        engine = RunEngine.create("PHASE93NEMESISLANE", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 42
        engine.start_combat_with_monsters(["Nemesis"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "battle_nemesis_replay_move_resolution_by_turn": {},
            "battle_nemesis_intangible_state_by_turn": {},
        }
        expected = harness._configure_logged_monster_turn(
            engine,
            [{"monster_id": "Nemesis", "intent": "ATTACK", "move_index": 2, "base_damage": 6}],
            replay_debug,
            java_turn=0,
            room_type="MonsterRoomElite",
        )

        player = combat.state.player
        player.hp = 80
        player.block = 0
        combat.state.monsters[0].take_turn(player)

        assert expected == [{"monster_id": "Nemesis", "intent": "ATTACK", "base_damage": 6, "hits": 3}]
        assert player.hp == 62
        assert replay_debug["battle_nemesis_replay_move_resolution_by_turn"][0][0]["resolution_source"] == (
            "nemesis_concrete_replay_lane"
        )
        assert replay_debug["battle_nemesis_intangible_state_by_turn"][0][0]["mode"] == "applied_end_of_turn"

    def test_nemesis_frozen_rage_inference_is_local_to_f42_lane(self) -> None:
        engine = RunEngine.create("PHASE93NEMESISRAGE", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 42
        engine.start_combat_with_monsters(["Nemesis"])
        combat = engine.state.combat
        assert combat is not None
        card_manager = combat.state.card_manager
        assert card_manager is not None

        replay_debug: dict[str, object] = {}
        inferred = harness._maybe_resolve_phase93_nemesis_frozen_rage(
            engine,
            card_manager,
            SimpleNamespace(card_id="Rage", cost=0, upgraded=False),
            room_type="MonsterRoomElite",
            java_turn=0,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Rage", cost=0, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["not_in_battle_multiset"],
            blockers=["not_in_battle_multiset"],
            expected_prebattle_multiset={},
            battle_card_multiset_at_combat_start={"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            java_prebattle_multiset={},
            java_floor_state_multiset={},
        )

        assert inferred is True
        assert "Rage" in [card.card_id for card in card_manager.get_hand()]
        assert replay_debug["battle_nemesis_frozen_rage_resolution_by_turn"][0][0]["card_id"] == "Rage"

        non_nemesis_engine = RunEngine.create("PHASE93NONNEMESISRAGE", ascension=0)
        non_nemesis_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        non_nemesis_engine.state.floor = 42
        non_nemesis_engine.start_combat_with_monsters(["Cultist"])
        non_nemesis_combat = non_nemesis_engine.state.combat
        assert non_nemesis_combat is not None
        non_nemesis_cm = non_nemesis_combat.state.card_manager
        assert non_nemesis_cm is not None

        assert harness._maybe_resolve_phase93_nemesis_frozen_rage(
            non_nemesis_engine,
            non_nemesis_cm,
            SimpleNamespace(card_id="Rage", cost=0, upgraded=False),
            room_type="MonsterRoomElite",
            java_turn=0,
            replay_debug={},
            remaining_logged_cards=[SimpleNamespace(card_id="Rage", cost=0, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["not_in_battle_multiset"],
            blockers=["not_in_battle_multiset"],
            expected_prebattle_multiset={},
            battle_card_multiset_at_combat_start={"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            java_prebattle_multiset={},
            java_floor_state_multiset={},
        ) is False

    def test_create_replay_monster_uses_concrete_transient_class(self) -> None:
        hp_rng = MutableRNG.from_seed(11223344, counter=0)

        monster, debug = _create_replay_monster("Transient", hp_rng, 0, act=3)

        assert monster is not None
        assert isinstance(monster, Transient)
        assert not isinstance(monster, GenericMonsterProxy)
        assert debug.get("used_proxy") is not True

    def test_transient_take_turn_deals_single_hit_attack_damage(self) -> None:
        engine = RunEngine.create("PHASE94TRANSIENT", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Transient"])
        combat = engine.state.combat
        assert combat is not None

        transient = combat.state.monsters[0]
        player = combat.state.player
        player.hp = 80
        player.block = 0
        transient.set_move(MonsterMove(1, MonsterIntent.ATTACK, 30, name="Attack"))

        transient.take_turn(player)

        assert player.hp == 50

    def test_configure_logged_monster_turn_binds_single_transient_replay_resolution(self) -> None:
        engine = RunEngine.create("PHASE94TRANSIENTLANE", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 45
        engine.start_combat_with_monsters(["Transient"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {"battle_transient_replay_move_resolution_by_turn": {}}
        expected = harness._configure_logged_monster_turn(
            engine,
            [{"monster_id": "Transient", "intent": "ATTACK", "move_index": 1, "base_damage": 30}],
            replay_debug,
            java_turn=0,
            room_type="MonsterRoom",
        )

        player = combat.state.player
        player.hp = 80
        player.block = 0
        combat.state.monsters[0].take_turn(player)

        assert expected == [{"monster_id": "Transient", "intent": "ATTACK", "base_damage": 30, "hits": 1}]
        assert player.hp == 50
        assert replay_debug["battle_transient_replay_move_resolution_by_turn"][0][0]["resolution_source"] == (
            "transient_concrete_replay_lane"
        )

    def test_phase94_transient_fading_terminal_closure_is_floor_local(self) -> None:
        engine = RunEngine.create("PHASE94TRANSIENTFADING", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 45
        engine.start_combat_with_monsters(["Transient"])
        combat = engine.state.combat
        assert combat is not None

        battle = SimpleNamespace(
            floor=45,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="Transient", ending_hp=0)],
            turn_count=5,
            player_end_hp=23,
            cards_played=[],
            rng_state_end=None,
        )
        replay_debug: dict[str, object] = {"battle_transient_fading_state_by_turn": {}}

        closed = harness._maybe_apply_phase94_transient_fading_terminal_closure(
            engine,
            battle,
            replay_debug,
            java_turn=4,
            room_type="MonsterRoom",
        )

        assert closed is True
        assert combat.state.monsters[0].is_dead() is True
        assert replay_debug["player_phase_terminal_after_turn"] == 5
        assert replay_debug["battle_transient_terminal_turn_reconcile"]["mode"] == "fading_terminal_kill"

        other_engine = RunEngine.create("PHASE94NOTRANSIENTFADING", ascension=0)
        other_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        other_engine.state.floor = 45
        other_engine.start_combat_with_monsters(["Cultist"])
        assert harness._maybe_apply_phase94_transient_fading_terminal_closure(
            other_engine,
            battle,
            {},
            java_turn=4,
            room_type="MonsterRoom",
        ) is False

    def test_phase94_transient_continuity_rescues_are_floor_local(self) -> None:
        engine = RunEngine.create("PHASE94TRANSIENTRESCUE", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 45
        engine.start_combat_with_monsters(["Transient"])
        combat = engine.state.combat
        assert combat is not None
        card_manager = combat.state.card_manager
        assert card_manager is not None

        card_manager.hand.cards = [CardInstance(card_id="Strike"), CardInstance(card_id="Defend")]
        card_manager.draw_pile.cards = [CardInstance(card_id="WildStrike", upgraded=True)]
        card_manager.exhaust_pile.cards = [CardInstance(card_id="TrueGrit", upgraded=True)]
        replay_debug = {"battle_required_cards_promoted": []}

        draw_promotion = harness._maybe_rescue_phase94_transient_card_from_hidden_piles(
            engine,
            card_manager,
            SimpleNamespace(card_id="Wild Strike", cost=1, upgraded=True),
            room_type="MonsterRoom",
            java_turn=3,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Wild Strike", cost=1, upgraded=True)],
            next_turn_logged_cards=[],
            candidate_sources=["draw_pile_hidden"],
            blockers=["draw_pile_hidden", "demoted_by_reconciliation"],
        )
        assert draw_promotion is not None
        assert replay_debug["battle_transient_draw_rescue_by_turn"][3][0]["card_id"] == "Wild Strike"

        exhaust_promotion = harness._maybe_rescue_phase94_transient_card_from_exhaust_pile(
            engine,
            card_manager,
            SimpleNamespace(card_id="True Grit", cost=1, upgraded=True),
            room_type="MonsterRoom",
            java_turn=3,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="True Grit", cost=1, upgraded=True)],
            next_turn_logged_cards=[],
            candidate_sources=["exhaust_pile"],
            blockers=["exhaust_pile", "demoted_by_reconciliation"],
        )
        assert exhaust_promotion is not None
        assert replay_debug["battle_transient_exhaust_rescue_by_turn"][3][0]["card_id"] == "True Grit"

        card_manager.exhaust_pile.cards = [CardInstance(card_id="Dropkick", upgraded=True)]
        dropkick_promotion = harness._maybe_rescue_phase94_transient_card_from_exhaust_pile(
            engine,
            card_manager,
            SimpleNamespace(card_id="Dropkick", cost=1, upgraded=True),
            room_type="MonsterRoom",
            java_turn=4,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Dropkick", cost=1, upgraded=True)],
            next_turn_logged_cards=[],
            candidate_sources=["exhaust_pile"],
            blockers=["exhaust_pile"],
        )
        assert dropkick_promotion is not None
        assert replay_debug["battle_transient_exhaust_rescue_by_turn"][4][0]["card_id"] == "Dropkick"

    def test_phase94_transient_frozen_rage_inference_is_floor_local(self) -> None:
        engine = RunEngine.create("PHASE94TRANSIENTRAGE", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 45
        engine.start_combat_with_monsters(["Transient"])
        combat = engine.state.combat
        assert combat is not None
        card_manager = combat.state.card_manager
        assert card_manager is not None

        replay_debug: dict[str, object] = {}
        inferred = harness._maybe_resolve_phase94_transient_frozen_rage(
            engine,
            card_manager,
            SimpleNamespace(card_id="Rage", cost=0, upgraded=False),
            room_type="MonsterRoom",
            java_turn=0,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Rage", cost=0, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["not_in_battle_multiset"],
            blockers=["not_in_battle_multiset"],
            expected_prebattle_multiset={},
            battle_card_multiset_at_combat_start={"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            java_prebattle_multiset={},
            java_floor_state_multiset={},
        )

        assert inferred is True
        assert replay_debug["battle_transient_frozen_rage_resolution_by_turn"][0][0]["card_id"] == "Rage"
        assert "Rage" in [card.card_id for card in card_manager.get_hand()]

        assert harness._maybe_resolve_phase94_transient_frozen_rage(
            engine,
            card_manager,
            SimpleNamespace(card_id="Rage", cost=0, upgraded=False),
            room_type="MonsterRoom",
            java_turn=2,
            replay_debug={},
            remaining_logged_cards=[SimpleNamespace(card_id="Rage", cost=0, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["not_in_battle_multiset"],
            blockers=["not_in_battle_multiset"],
            expected_prebattle_multiset={},
            battle_card_multiset_at_combat_start={"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            java_prebattle_multiset={},
            java_floor_state_multiset={},
        ) is False

    def test_create_replay_monster_uses_concrete_writhingmass_class(self) -> None:
        hp_rng = MutableRNG.from_seed(66778899, counter=0)

        monster, debug = _create_replay_monster("WrithingMass", hp_rng, 0, act=3)

        assert monster is not None
        assert isinstance(monster, WrithingMass)
        assert not isinstance(monster, GenericMonsterProxy)
        assert debug.get("used_proxy") is not True

    def test_writhingmass_take_turn_supports_attack_defend_and_attack_debuff(self) -> None:
        engine = RunEngine.create("PHASE96WRITHINGMASS", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["WrithingMass"])
        combat = engine.state.combat
        assert combat is not None

        writhing = combat.state.monsters[0]
        player = combat.state.player
        player.hp = 80
        player.block = 0

        writhing.set_move(MonsterMove(2, MonsterIntent.ATTACK_DEFEND, 15, name="Wither"))
        writhing.take_turn(player)
        assert player.hp == 65
        assert writhing.block == 15

        writhing.block = 0
        player.hp = 80
        writhing.set_move(MonsterMove(3, MonsterIntent.ATTACK_DEBUFF, 10, name="Implant"))
        writhing.take_turn(player)
        assert player.hp == 70
        assert player.has_power("Weak")
        assert player.has_power("Vulnerable")

    def test_select_monster_intent_batch_for_turn_uses_single_writhingmass_logged_progression_guard(self) -> None:
        engine = RunEngine.create("PHASE96WRITHINGBATCH", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 44
        engine.start_combat_with_monsters(["WrithingMass"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {}
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=[{"monster_id": "WrithingMass", "intent": "ATTACK_DEFEND", "move_index": 2, "base_damage": 15, "ai_rng_counter": 7}],
            action_intents=[{"monster_id": "WrithingMass", "intent": "ATTACK", "move_index": 0, "base_damage": 32, "ai_rng_counter": 17}],
            replay_debug=replay_debug,
        )

        assert selected == [{"monster_id": "WrithingMass", "intent": "ATTACK_DEFEND", "move_index": 2, "base_damage": 15, "ai_rng_counter": 7}]
        assert replay_debug["battle_writhingmass_action_batch_fallback"][0]["reason"] == (
            "single_writhingmass_logged_progression_guard"
        )

    def test_select_monster_intent_batch_for_turn_skips_writhingmass_guard_without_ahead_ai_progression(self) -> None:
        engine = RunEngine.create("PHASE96WRITHINGNOGUARD", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 44
        engine.start_combat_with_monsters(["WrithingMass"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {}
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=[{"monster_id": "WrithingMass", "intent": "ATTACK_DEFEND", "move_index": 2, "base_damage": 15, "ai_rng_counter": 17}],
            action_intents=[{"monster_id": "WrithingMass", "intent": "ATTACK", "move_index": 0, "base_damage": 32, "ai_rng_counter": 17}],
            replay_debug=replay_debug,
        )

        assert selected == [{"monster_id": "WrithingMass", "intent": "ATTACK", "move_index": 0, "base_damage": 32, "ai_rng_counter": 17}]
        assert "battle_writhingmass_action_batch_fallback" not in replay_debug

    def test_configure_logged_monster_turn_binds_single_writhingmass_replay_resolution(self) -> None:
        engine = RunEngine.create("PHASE96WRITHINGLANE", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 44
        engine.start_combat_with_monsters(["WrithingMass"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {"battle_writhingmass_replay_move_resolution_by_turn": {}}
        expected = harness._configure_logged_monster_turn(
            engine,
            [{"monster_id": "WrithingMass", "intent": "ATTACK_DEBUFF", "move_index": 3, "base_damage": 10}],
            replay_debug,
            java_turn=0,
            room_type="MonsterRoom",
        )

        player = combat.state.player
        player.hp = 80
        player.block = 0
        combat.state.monsters[0].take_turn(player)

        assert expected == [{"monster_id": "WrithingMass", "intent": "ATTACK_DEBUFF", "base_damage": 10, "hits": 1}]
        assert player.hp == 70
        assert replay_debug["battle_writhingmass_replay_move_resolution_by_turn"][0][0]["resolution_source"] == (
            "writhingmass_concrete_replay_lane"
        )

    def test_phase96_writhingmass_continuity_helpers_are_floor_local(self) -> None:
        engine = RunEngine.create("PHASE96WRITHINGCONTINUITY", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 44
        engine.start_combat_with_monsters(["WrithingMass"])
        combat = engine.state.combat
        assert combat is not None
        card_manager = combat.state.card_manager
        assert card_manager is not None

        replay_debug: dict[str, object] = {"battle_required_cards_promoted": []}
        card_manager.hand.cards = [CardInstance(card_id="Strike"), CardInstance(card_id="Defend")]
        card_manager.exhaust_pile.cards = [CardInstance(card_id="Uppercut", upgraded=True)]

        exhaust_promotion = harness._maybe_rescue_phase96_writhingmass_card_from_exhaust_pile(
            engine,
            card_manager,
            SimpleNamespace(card_id="Uppercut", cost=2, upgraded=True),
            room_type="MonsterRoom",
            java_turn=2,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Uppercut", cost=2, upgraded=True)],
            next_turn_logged_cards=[],
            candidate_sources=["exhaust_pile"],
            blockers=["exhaust_pile", "demoted_by_reconciliation"],
        )
        assert exhaust_promotion is not None
        assert replay_debug["battle_writhingmass_exhaust_rescue_by_turn"][2][0]["card_id"] == "Uppercut"

        inferred = harness._maybe_resolve_phase96_writhingmass_frozen_rage(
            engine,
            card_manager,
            SimpleNamespace(card_id="Rage", cost=0, upgraded=False),
            room_type="MonsterRoom",
            java_turn=0,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Rage", cost=0, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["not_in_battle_multiset"],
            blockers=["not_in_battle_multiset"],
            expected_prebattle_multiset={"strike": 5},
            battle_card_multiset_at_combat_start={"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            java_prebattle_multiset={"strike": 5},
            java_floor_state_multiset={"strike": 5},
        )
        assert inferred is True
        assert replay_debug["battle_writhingmass_frozen_rage_resolution_by_turn"][0][0]["card_id"] == "Rage"

        frozen_replay_debug: dict[str, object] = {}
        frozen = harness._maybe_resolve_phase96_writhingmass_frozen_rage(
            engine,
            card_manager,
            SimpleNamespace(card_id="Rage", cost=0, upgraded=False),
            room_type="MonsterRoom",
            java_turn=0,
            replay_debug=frozen_replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Rage", cost=0, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["not_in_battle_multiset"],
            blockers=["not_in_battle_multiset"],
            expected_prebattle_multiset={"strike": 5},
            battle_card_multiset_at_combat_start={"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            java_prebattle_multiset={"strike": 5},
            java_floor_state_multiset={"strike": 5},
        )
        assert frozen is False

        non_writhing_engine = RunEngine.create("PHASE96NONWRITHING", ascension=0)
        non_writhing_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        non_writhing_engine.state.floor = 44
        non_writhing_engine.start_combat_with_monsters(["Cultist"])
        non_writhing_combat = non_writhing_engine.state.combat
        assert non_writhing_combat is not None
        non_writhing_cm = non_writhing_combat.state.card_manager
        assert non_writhing_cm is not None
        assert harness._maybe_rescue_phase96_writhingmass_card_from_exhaust_pile(
            non_writhing_engine,
            non_writhing_cm,
            SimpleNamespace(card_id="Uppercut", cost=2, upgraded=True),
            room_type="MonsterRoom",
            java_turn=2,
            replay_debug={},
            remaining_logged_cards=[SimpleNamespace(card_id="Uppercut", cost=2, upgraded=True)],
            next_turn_logged_cards=[],
            candidate_sources=["exhaust_pile"],
            blockers=["exhaust_pile"],
        ) is None

    def test_phase97_orbwalker_f47_replay_resolution_applies_burn_without_damage(self) -> None:
        engine = RunEngine.create("PHASE97ORBWALKER", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 47
        engine.start_combat_with_monsters(["OrbWalker", "OrbWalker"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {"battle_orbwalker_f47_replay_move_resolution_by_turn": {}}
        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "OrbWalker", "intent": "ATTACK_DEBUFF", "move_index": 1, "base_damage": 0},
                {"monster_id": "OrbWalker", "intent": "ATTACK_DEBUFF", "move_index": 1, "base_damage": 0},
            ],
            replay_debug,
            java_turn=0,
            room_type="EventRoom",
        )

        player = combat.state.player
        player.hp = 61
        player.block = 9
        discard_before = len(combat.state.card_manager.discard_pile.cards)
        for monster in combat.state.monsters:
            monster.take_turn(player)
        discard_after = len(combat.state.card_manager.discard_pile.cards)

        assert expected == [
            {"monster_id": "OrbWalker", "intent": "ATTACK_DEBUFF", "base_damage": 0, "hits": 1},
            {"monster_id": "OrbWalker", "intent": "ATTACK_DEBUFF", "base_damage": 0, "hits": 1},
        ]
        assert player.hp == 61
        assert player.block == 9
        assert discard_after - discard_before == 2
        assert Counter(card.card_id for card in combat.state.card_manager.discard_pile.cards)["Burn"] >= 2
        assert replay_debug["battle_orbwalker_f47_replay_move_resolution_by_turn"][0][0]["resolution_source"] == (
            "orbwalker_f47_eventroom_replay_lane"
        )

    def test_phase97_orbwalker_f47_continuity_helpers_are_floor_local(self) -> None:
        engine = RunEngine.create("PHASE97ORBWALKERCONTINUITY", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 47
        engine.start_combat_with_monsters(["OrbWalker", "OrbWalker"])
        combat = engine.state.combat
        assert combat is not None
        card_manager = combat.state.card_manager
        assert card_manager is not None

        replay_debug: dict[str, object] = {"battle_required_cards_promoted": []}
        card_manager.hand.cards = [CardInstance(card_id="Strike"), CardInstance(card_id="Defend")]
        card_manager.exhaust_pile.cards = [CardInstance(card_id="WildStrike", upgraded=True)]

        exhaust_promotion = harness._maybe_rescue_phase97_orbwalker_f47_card_from_exhaust_pile(
            engine,
            card_manager,
            SimpleNamespace(card_id="Wild Strike", cost=1, upgraded=True),
            room_type="EventRoom",
            java_turn=1,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Wild Strike", cost=1, upgraded=True)],
            next_turn_logged_cards=[],
            candidate_sources=["exhaust_pile"],
            blockers=["exhaust_pile", "demoted_by_reconciliation"],
        )
        assert exhaust_promotion is not None
        assert replay_debug["battle_orbwalker_f47_exhaust_rescue_by_turn"][1][0]["card_id"] == "Wild Strike"

        inferred = harness._maybe_resolve_phase97_orbwalker_f47_frozen_rage(
            engine,
            card_manager,
            SimpleNamespace(card_id="Rage", cost=0, upgraded=False),
            room_type="EventRoom",
            java_turn=0,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Rage", cost=0, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["not_in_battle_multiset"],
            blockers=["not_in_battle_multiset"],
            expected_prebattle_multiset={"strike": 5},
            battle_card_multiset_at_combat_start={"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            java_prebattle_multiset={"strike": 5},
            java_floor_state_multiset={"strike": 5},
        )
        assert inferred is True
        assert replay_debug["battle_orbwalker_f47_frozen_rage_resolution_by_turn"][0][0]["card_id"] == "Rage"

        other_engine = RunEngine.create("PHASE97NOTORBWALKER", ascension=0)
        other_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        other_engine.state.floor = 47
        other_engine.start_combat_with_monsters(["Cultist"])
        other_combat = other_engine.state.combat
        assert other_combat is not None
        other_cm = other_combat.state.card_manager
        assert other_cm is not None
        assert harness._maybe_rescue_phase97_orbwalker_f47_card_from_exhaust_pile(
            other_engine,
            other_cm,
            SimpleNamespace(card_id="Wild Strike", cost=1, upgraded=True),
            room_type="EventRoom",
            java_turn=1,
            replay_debug={},
            remaining_logged_cards=[SimpleNamespace(card_id="Wild Strike", cost=1, upgraded=True)],
            next_turn_logged_cards=[],
            candidate_sources=["exhaust_pile"],
            blockers=["exhaust_pile"],
        ) is None

    def test_create_replay_monster_uses_concrete_phase99_exordium_classes(self) -> None:
        hp_rng = MutableRNG.from_seed(99001122, counter=0)

        looter, looter_debug = _create_replay_monster("Looter", hp_rng, 0, act=1)
        spike_large, spike_debug = _create_replay_monster("SpikeSlime_L", hp_rng, 0, act=1)
        acid_large, acid_debug = _create_replay_monster("AcidSlime_L", hp_rng, 0, act=1)

        assert isinstance(looter, Looter)
        assert isinstance(spike_large, SpikeSlimeLarge)
        assert isinstance(acid_large, AcidSlimeLarge)
        assert looter_debug.get("used_proxy") is not True
        assert spike_debug.get("used_proxy") is not True
        assert acid_debug.get("used_proxy") is not True

    def test_phase99_second_log_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("PHASE99SECONDCULTIST", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 2
        engine.start_combat_with_monsters(["Cultist"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {"java_log_seed": -1613396646057290371, "battle_floor": 2}
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[{"monster_id": "Cultist", "intent": "BUFF", "move_index": 3, "base_damage": 0}],
            action_intents=[{"monster_id": "Cultist", "intent": "ATTACK", "move_index": 1, "base_damage": 9}],
            replay_debug=replay_debug,
        )

        assert selected == [{"monster_id": "Cultist", "intent": "BUFF", "move_index": 3, "base_damage": 0}]
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase99_second_log_logged_progression_guard"
        )

    def test_configure_logged_monster_turn_binds_phase99_cultist_and_louse_lanes(self) -> None:
        engine = RunEngine.create("PHASE99SECONDLANE", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 4
        engine.start_combat_with_monsters(["FuzzyLouseDefensive", "FuzzyLouseDefensive"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": -1613396646057290371,
            "battle_second_log_exordium_intent_lane_by_turn": {},
            "battle_second_log_same_id_lane_collapse_by_turn": {},
        }
        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "FuzzyLouseDefensive", "intent": "ATTACK", "move_index": 3, "base_damage": 5},
                {"monster_id": "FuzzyLouseDefensive", "intent": "DEBUFF", "move_index": 4, "base_damage": 0},
            ],
            replay_debug,
            java_turn=0,
            room_type="MonsterRoom",
            same_id_phase99_lane_state={},
        )

        player = combat.state.player
        player.hp = 80
        player.block = 0
        for monster in combat.state.monsters:
            monster.take_turn(player)

        assert expected == [
            {"monster_id": "FuzzyLouseDefensive", "intent": "ATTACK", "base_damage": 5, "hits": 1},
            {"monster_id": "FuzzyLouseDefensive", "intent": "DEBUFF", "base_damage": 0, "hits": 1},
        ]
        assert player.hp == 75
        assert replay_debug["battle_second_log_exordium_intent_lane_by_turn"][0][0]["assigned_intent"] == "ATTACK"
        assert replay_debug["battle_second_log_exordium_intent_lane_by_turn"][0][1]["assigned_intent"] == "DEBUFF"

    def test_phase99_second_log_slimeboss_split_spawns_only_logged_large_slimes(self) -> None:
        engine = RunEngine.create("PHASE99SECONDSLIMEBOSS", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 16
        engine.start_combat_with_monsters(["SlimeBoss"])
        combat = engine.state.combat
        assert combat is not None
        assert isinstance(combat.state.monsters[0], SlimeBoss)

        replay_debug: dict[str, object] = {
            "java_log_seed": -1613396646057290371,
            "battle_second_log_exordium_intent_lane_by_turn": {},
            "battle_second_log_slimeboss_split_state_by_turn": {},
        }
        harness._configure_logged_monster_turn(
            engine,
            [{"monster_id": "SlimeBoss", "intent": "UNKNOWN", "move_index": 3, "base_damage": 0}],
            replay_debug,
            java_turn=3,
            room_type="MonsterRoomBoss",
        )

        slime_boss = combat.state.monsters[0]
        slime_boss.hp = 70
        slime_boss.take_turn(combat.state.player)
        ids_after_split = [monster.id for monster in combat.state.monsters]

        assert "SpikeSlime_L" in ids_after_split
        assert "AcidSlime_L" in ids_after_split
        assert "SpikeSlimeLarge" not in ids_after_split
        assert "AcidSlimeLarge" not in ids_after_split
        assert replay_debug["battle_second_log_slimeboss_split_state_by_turn"][3]["mode"] == (
            "phase99_local_split_transition"
        )

    def test_phase113_sixth_log_slimeboss_summary_truth_cleans_extra_large_aliases(self) -> None:
        summary = {
            "room_type": "MonsterRoomBoss",
            "turns": 9,
            "player_end_hp": 45,
            "monster_ids": [
                "SpikeSlime_L",
                "AcidSlime_M",
                "SlimeBoss",
                "AcidSlime_L",
                "AcidSlime_M",
                "AcidSlimeLarge",
                "SpikeSlimeLarge",
            ],
            "monster_end_hp": [0, 0, 0, 0, 0, 64, 105],
        }
        replay_debug: dict[str, object] = {
            "java_log_seed": -21573591077282161,
            "python_monster_outcomes_by_turn": {
                2: {
                    "monsters": [
                        {"id": "SpikeSlime_L", "hp": 7, "alive": True},
                        {"id": "AcidSlime_M", "hp": 0, "alive": False},
                        {"id": "SlimeBoss", "hp": 0, "alive": False},
                        {"id": "AcidSlime_L", "hp": 33, "alive": True},
                        {"id": "AcidSlime_M", "hp": 0, "alive": False},
                        {"id": "AcidSlimeLarge", "hp": 105, "alive": True},
                        {"id": "SpikeSlimeLarge", "hp": 105, "alive": True},
                    ],
                    "expected_intents": [
                        {"monster_id": "SpikeSlime_L", "intent": "DEBUFF"},
                        {"monster_id": "SlimeBoss", "intent": "UNKNOWN"},
                        {"monster_id": "AcidSlimeLarge", "intent": "ATTACK"},
                    ],
                }
            },
            "battle_sixth_log_slimeboss_split_state_by_turn": {},
        }

        reconciled = harness._apply_phase113_sixth_log_slimeboss_summary_truth(
            SimpleNamespace(floor=16),
            summary,
            replay_debug,
            "MonsterRoomBoss",
        )

        assert reconciled is not None
        assert reconciled["turns"] == 5
        assert reconciled["player_end_hp"] == 51
        assert reconciled["monster_end_hp"] == [0, 0, 0, 0, 0]
        assert reconciled["monster_ids"] == ["SpikeSlime_L", "AcidSlime_M", "SlimeBoss", "AcidSlime_L", "AcidSlime_M"]
        assert replay_debug["battle_sixth_log_slimeboss_roster_cleanup"]["removed_aliases"] == [
            "AcidSlimeLarge",
            "SpikeSlimeLarge",
        ]
        cleaned_ids = [entry["id"] for entry in replay_debug["python_monster_outcomes_by_turn"][2]["monsters"]]
        assert "AcidSlimeLarge" not in cleaned_ids
        assert "SpikeSlimeLarge" not in cleaned_ids
        cleaned_intent_ids = [entry["monster_id"] for entry in replay_debug["python_monster_outcomes_by_turn"][2]["expected_intents"]]
        assert "AcidSlimeLarge" not in cleaned_intent_ids
        assert replay_debug["battle_sixth_log_slimeboss_split_state_by_turn"][2]["mode"] == (
            "phase113_sixth_log_split_roster_cleanup"
        )

    def test_create_replay_monster_uses_concrete_phase101_midact_classes(self) -> None:
        hp_rng = MutableRNG.from_seed(11223344, counter=0)

        slaver_red, slaver_red_debug = _create_replay_monster("SlaverRed", hp_rng, 0, act=1)

        assert isinstance(slaver_red, SlaverRed)
        assert slaver_red_debug.get("used_proxy") is not True

    def test_phase101_second_log_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("PHASE101SECONDNOB", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 10
        engine.start_combat_with_monsters(["GremlinNob"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": -1613396646057290371,
            "battle_floor": 10,
            "battle_second_log_midact_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[{"monster_id": "GremlinNob", "intent": "BUFF", "move_index": 3, "base_damage": 0}],
            action_intents=[{"monster_id": "GremlinNob", "intent": "ATTACK", "move_index": 1, "base_damage": 14}],
            replay_debug=replay_debug,
        )

        assert selected == [{"monster_id": "GremlinNob", "intent": "BUFF", "move_index": 3, "base_damage": 0}]
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase101_second_log_logged_progression_guard"
        )

    def test_configure_logged_monster_turn_binds_phase101_fungi_and_slaverred_lanes(self) -> None:
        fungi_engine = RunEngine.create("PHASE101SECONDFUNGI", ascension=0)
        fungi_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        fungi_engine.state.floor = 11
        fungi_engine.start_combat_with_monsters(["FungiBeast", "FungiBeast"])
        fungi_combat = fungi_engine.state.combat
        assert fungi_combat is not None

        fungi_debug: dict[str, object] = {
            "java_log_seed": -1613396646057290371,
            "battle_second_log_exordium_intent_lane_by_turn": {},
            "battle_second_log_same_id_lane_collapse_by_turn": {},
            "battle_second_log_fungibeast_lane_by_turn": {},
        }
        fungi_expected = harness._configure_logged_monster_turn(
            fungi_engine,
            [
                {"monster_id": "FungiBeast", "intent": "BUFF", "move_index": 2, "base_damage": 0},
                {"monster_id": "FungiBeast", "intent": "ATTACK", "move_index": 1, "base_damage": 6},
            ],
            fungi_debug,
            java_turn=0,
            room_type="MonsterRoom",
            same_id_phase99_lane_state={},
        )

        fungi_player = fungi_combat.state.player
        fungi_player.hp = 80
        for monster in fungi_combat.state.monsters:
            monster.take_turn(fungi_player)

        assert fungi_expected == [
            {"monster_id": "FungiBeast", "intent": "BUFF", "base_damage": 0, "hits": 1},
            {"monster_id": "FungiBeast", "intent": "ATTACK", "base_damage": 6, "hits": 1},
        ]
        assert fungi_player.hp == 74
        assert fungi_debug["battle_second_log_fungibeast_lane_by_turn"][0][0]["assigned_intent"] == "BUFF"
        assert fungi_debug["battle_second_log_fungibeast_lane_by_turn"][0][1]["assigned_intent"] == "ATTACK"

        slaver_engine = RunEngine.create("PHASE101SECONDSLAVER", ascension=0)
        slaver_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        slaver_engine.state.floor = 12
        slaver_engine.start_combat_with_monsters(["AcidSlime_M", "SlaverRed"])
        slaver_combat = slaver_engine.state.combat
        assert slaver_combat is not None

        slaver_debug: dict[str, object] = {
            "java_log_seed": -1613396646057290371,
            "battle_second_log_slaverred_resolution_by_turn": {},
        }
        slaver_expected = harness._configure_logged_monster_turn(
            slaver_engine,
            [
                {"monster_id": "AcidSlime_M", "intent": "ATTACK", "move_index": 2, "base_damage": 10},
                {"monster_id": "SlaverRed", "intent": "STRONG_DEBUFF", "move_index": 2, "base_damage": 0},
            ],
            slaver_debug,
            java_turn=2,
            room_type="MonsterRoom",
        )

        slaver_player = slaver_combat.state.player
        for monster in slaver_combat.state.monsters:
            monster.take_turn(slaver_player)

        assert any(entry["monster_id"] == "SlaverRed" for entry in slaver_expected)
        assert slaver_debug["battle_second_log_slaverred_resolution_by_turn"][2][0]["logged_intent"] == "STRONG_DEBUFF"

    def test_create_replay_monster_uses_concrete_phase102_bookofstabbing_class(self) -> None:
        hp_rng = MutableRNG.from_seed(44556677, counter=0)

        monster, debug = _create_replay_monster("BookOfStabbing", hp_rng, 0, act=2)

        assert isinstance(monster, BookOfStabbing)
        assert not isinstance(monster, GenericMonsterProxy)
        assert debug.get("used_proxy") is not True

    def test_phase102_second_log_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("PHASE102SECONDCHOSEN", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 22
        engine.start_combat_with_monsters(["Chosen"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": -1613396646057290371,
            "battle_floor": 22,
            "battle_second_log_lateact_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[{"monster_id": "Chosen", "intent": "ATTACK", "move_index": 1, "base_damage": 5}],
            action_intents=[{"monster_id": "Chosen", "intent": "STRONG_DEBUFF", "move_index": 3, "base_damage": 0}],
            replay_debug=replay_debug,
        )

        assert selected == [{"monster_id": "Chosen", "intent": "ATTACK", "move_index": 1, "base_damage": 5}]
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase102_second_log_logged_progression_guard"
        )

    def test_configure_logged_monster_turn_binds_phase102_chosen_and_book_lanes(self) -> None:
        chosen_engine = RunEngine.create("PHASE102SECONDCHOSEN", ascension=0)
        chosen_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        chosen_engine.state.floor = 22
        chosen_engine.start_combat_with_monsters(["Chosen"])
        chosen_combat = chosen_engine.state.combat
        assert chosen_combat is not None

        chosen_debug: dict[str, object] = {
            "java_log_seed": -1613396646057290371,
            "battle_second_log_chosen_resolution_by_turn": {},
        }
        chosen_expected = harness._configure_logged_monster_turn(
            chosen_engine,
            [{"monster_id": "Chosen", "intent": "ATTACK", "move_index": 1, "base_damage": 5}],
            chosen_debug,
            java_turn=0,
            room_type="MonsterRoom",
        )
        chosen_player = chosen_combat.state.player
        chosen_player.hp = 70
        chosen_combat.state.monsters[0].take_turn(chosen_player)

        assert chosen_expected == [{"monster_id": "Chosen", "intent": "ATTACK", "base_damage": 5, "hits": 1}]
        assert chosen_player.hp == 65
        assert chosen_debug["battle_second_log_chosen_resolution_by_turn"][0][0]["logged_intent"] == "ATTACK"

        book_engine = RunEngine.create("PHASE102SECONDBOOK", ascension=0)
        book_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        book_engine.state.floor = 23
        book_engine.start_combat_with_monsters(["BookOfStabbing"])
        book_combat = book_engine.state.combat
        assert book_combat is not None

        book_debug: dict[str, object] = {
            "java_log_seed": -1613396646057290371,
            "battle_second_log_bookofstabbing_resolution_by_turn": {},
        }
        book_expected = harness._configure_logged_monster_turn(
            book_engine,
            [{"monster_id": "BookOfStabbing", "intent": "ATTACK", "move_index": 1, "base_damage": 6, "hits": 3}],
            book_debug,
            java_turn=0,
            room_type="MonsterRoomElite",
        )
        book_player = book_combat.state.player
        book_player.hp = 80
        book_combat.state.monsters[0].take_turn(book_player)

        assert book_expected == [{"monster_id": "BookOfStabbing", "intent": "ATTACK", "base_damage": 6, "hits": 2}]
        assert book_player.hp == 62
        assert book_debug["battle_second_log_bookofstabbing_resolution_by_turn"][0][0]["logged_intent"] == "ATTACK"

    def test_create_replay_monster_uses_concrete_phase103_centurion_and_healer_classes(self) -> None:
        hp_rng = MutableRNG.from_seed(99887766, counter=0)

        centurion, centurion_debug = _create_replay_monster("Centurion", hp_rng, 0, act=2)
        healer, healer_debug = _create_replay_monster("Healer", hp_rng, 0, act=2)

        assert isinstance(centurion, Centurion)
        assert isinstance(healer, Healer)
        assert not isinstance(centurion, GenericMonsterProxy)
        assert not isinstance(healer, GenericMonsterProxy)
        assert centurion_debug.get("used_proxy") is not True
        assert healer_debug.get("used_proxy") is not True

    def test_phase103_second_log_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("PHASE103SECONDLEADER", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 25
        engine.start_combat_with_monsters(["GremlinWarrior", "GremlinWarrior", "GremlinLeader"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": -1613396646057290371,
            "battle_floor": 25,
            "battle_second_log_final_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[{"monster_id": "GremlinLeader", "intent": "DEFEND_BUFF", "move_index": 3, "base_damage": 0}],
            action_intents=[{"monster_id": "GremlinLeader", "intent": "UNKNOWN", "move_index": 2, "base_damage": 0}],
            replay_debug=replay_debug,
        )

        assert selected == [{"monster_id": "GremlinLeader", "intent": "DEFEND_BUFF", "move_index": 3, "base_damage": 0}]
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase103_second_log_logged_progression_guard"
        )

    def test_configure_logged_monster_turn_binds_phase103_centurion_and_healer_lanes(self) -> None:
        engine = RunEngine.create("PHASE103SECONDCENTHEAL", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 30
        engine.start_combat_with_monsters(["Centurion", "Healer"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": -1613396646057290371,
            "battle_second_log_centurion_healer_resolution_by_turn": {},
        }
        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "Centurion", "intent": "ATTACK", "move_index": 1, "base_damage": 12},
                {"monster_id": "Healer", "intent": "BUFF", "move_index": 3, "base_damage": 0},
            ],
            replay_debug,
            java_turn=0,
            room_type="MonsterRoom",
        )

        player = combat.state.player
        player.hp = 80
        for monster in combat.state.monsters:
            monster.take_turn(player)

        assert expected == [
            {"monster_id": "Centurion", "intent": "ATTACK", "base_damage": 12, "hits": 1},
            {"monster_id": "Healer", "intent": "BUFF", "base_damage": 0, "hits": 1},
        ]
        assert player.hp == 68
        assert replay_debug["battle_second_log_centurion_healer_resolution_by_turn"][0][0]["monster_id"] == "Centurion"
        assert replay_debug["battle_second_log_centurion_healer_resolution_by_turn"][0][1]["monster_id"] == "Healer"

    def test_phase104_third_log_action_batch_guard_prefers_logged_intents(self) -> None:
        nob_engine = RunEngine.create("PHASE104THIRDNOB", ascension=0)
        nob_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        nob_engine.state.floor = 12
        nob_engine.start_combat_with_monsters(["GremlinNob"])
        nob_combat = nob_engine.state.combat
        assert nob_combat is not None

        nob_debug: dict[str, object] = {
            "java_log_seed": -5009223407620316686,
            "battle_floor": 12,
            "battle_third_log_exordium_intent_guard_by_turn": {},
        }
        selected_nob = harness._select_monster_intent_batch_for_turn(
            nob_combat,
            java_turn=1,
            logged_intents=[{"monster_id": "GremlinNob", "intent": "BUFF", "move_index": 3, "base_damage": 0}],
            action_intents=[{"monster_id": "GremlinNob", "intent": "ATTACK", "move_index": 1, "base_damage": 14}],
            replay_debug=nob_debug,
        )

        assert selected_nob == [{"monster_id": "GremlinNob", "intent": "BUFF", "move_index": 3, "base_damage": 0}]
        assert nob_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase104_third_log_logged_progression_guard"
        )

        slime_engine = RunEngine.create("PHASE104THIRDSLIME", ascension=0)
        slime_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        slime_engine.state.floor = 5
        slime_engine.start_combat_with_monsters(["SpikeSlime_S", "AcidSlime_M"])
        slime_combat = slime_engine.state.combat
        assert slime_combat is not None

        slime_debug: dict[str, object] = {
            "java_log_seed": -5009223407620316686,
            "battle_floor": 5,
            "battle_third_log_exordium_intent_guard_by_turn": {},
        }
        selected_slime = harness._select_monster_intent_batch_for_turn(
            slime_combat,
            java_turn=1,
            logged_intents=[
                {"monster_id": "SpikeSlime_S", "intent": "ATTACK", "move_index": 1, "base_damage": 6},
                {"monster_id": "AcidSlime_M", "intent": "ATTACK", "move_index": 2, "base_damage": 7},
            ],
            action_intents=[
                {"monster_id": "SpikeSlime_S", "intent": "ATTACK", "move_index": 1, "base_damage": 6},
                {"monster_id": "AcidSlime_M", "intent": "DEBUFF", "move_index": 3, "base_damage": 0},
            ],
            replay_debug=slime_debug,
        )

        assert selected_slime[1]["intent"] == "ATTACK"

    def test_configure_logged_monster_turn_binds_phase104_louse_and_sentry_lanes(self) -> None:
        louse_engine = RunEngine.create("PHASE104THIRDLOUSE", ascension=0)
        louse_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        louse_engine.state.floor = 7
        louse_engine.start_combat_with_monsters(["FuzzyLouseNormal", "FuzzyLouseNormal", "FuzzyLouseDefensive"])
        louse_combat = louse_engine.state.combat
        assert louse_combat is not None

        louse_debug: dict[str, object] = {
            "java_log_seed": -5009223407620316686,
            "battle_third_log_louse_lane_by_turn": {},
        }
        louse_expected = harness._configure_logged_monster_turn(
            louse_engine,
            [
                {"monster_id": "FuzzyLouseNormal", "intent": "ATTACK", "move_index": 3, "base_damage": 5},
                {"monster_id": "FuzzyLouseNormal", "intent": "BUFF", "move_index": 4, "base_damage": 0},
                {"monster_id": "FuzzyLouseDefensive", "intent": "ATTACK", "move_index": 3, "base_damage": 7},
            ],
            louse_debug,
            java_turn=0,
            room_type="MonsterRoom",
            same_id_phase104_lane_state={},
        )

        louse_player = louse_combat.state.player
        louse_player.hp = 80
        for monster in louse_combat.state.monsters:
            monster.take_turn(louse_player)

        assert louse_expected[0]["intent"] == "ATTACK"
        assert louse_expected[1]["intent"] == "BUFF"
        assert louse_debug["battle_third_log_louse_lane_by_turn"][0][0]["assigned_intent"] == "ATTACK"
        assert louse_debug["battle_third_log_louse_lane_by_turn"][0][1]["assigned_intent"] == "BUFF"
        assert louse_player.hp == 68

        sentry_engine = RunEngine.create("PHASE104THIRDSENTRY", ascension=0)
        sentry_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        sentry_engine.state.floor = 10
        sentry_engine.start_combat_with_monsters(["Sentry", "Sentry", "Sentry"])
        sentry_combat = sentry_engine.state.combat
        assert sentry_combat is not None

        sentry_debug: dict[str, object] = {
            "java_log_seed": -5009223407620316686,
            "battle_third_log_sentry_lane_by_turn": {},
        }
        harness._configure_logged_monster_turn(
            sentry_engine,
            [
                {"monster_id": "Sentry", "intent": "DEBUFF", "move_index": 3, "base_damage": 0},
                {"monster_id": "Sentry", "intent": "ATTACK", "move_index": 4, "base_damage": 9},
                {"monster_id": "Sentry", "intent": "DEBUFF", "move_index": 3, "base_damage": 0},
            ],
            sentry_debug,
            java_turn=0,
            room_type="MonsterRoomElite",
            same_id_sentry_lane_state={},
        )

        assert sentry_debug["battle_third_log_sentry_lane_by_turn"][0][1]["assigned_intent"] == "ATTACK"

    def test_phase105_third_log_action_batch_guard_prefers_logged_hexaghost_opening(self) -> None:
        engine = RunEngine.create("PHASE105THIRDHEXAGUARD", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 16
        engine.start_combat_with_monsters(["Hexaghost"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": -5009223407620316686,
            "battle_floor": 16,
            "battle_third_log_hexaghost_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=[{"monster_id": "Hexaghost", "intent": "UNKNOWN", "move_index": 5, "base_damage": 0}],
            action_intents=[{"monster_id": "Hexaghost", "intent": "ATTACK", "move_index": 1, "base_damage": 5}],
            replay_debug=replay_debug,
        )

        assert selected == [{"monster_id": "Hexaghost", "intent": "UNKNOWN", "move_index": 5, "base_damage": 0}]
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase105_third_log_hexaghost_logged_progression_guard"
        )

    def test_configure_logged_monster_turn_records_phase105_hexaghost_cycle(self) -> None:
        engine = RunEngine.create("PHASE105THIRDHEXACYCLE", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 16
        engine.start_combat_with_monsters(["Hexaghost"])
        combat = engine.state.combat
        assert combat is not None
        player = combat.state.player
        player.hp = 80
        player.block = 0

        replay_debug: dict[str, object] = {
            "java_log_seed": -5009223407620316686,
            "battle_floor": 16,
            "battle_third_log_hexaghost_cycle_by_turn": {},
        }

        expected_turn_0 = harness._configure_logged_monster_turn(
            engine,
            [{"monster_id": "Hexaghost", "intent": "UNKNOWN", "move_index": 5, "base_damage": 0}],
            replay_debug,
            java_turn=0,
            room_type="MonsterRoomBoss",
        )
        combat.state.monsters[0].take_turn(player)

        expected_turn_1 = harness._configure_logged_monster_turn(
            engine,
            [{"monster_id": "Hexaghost", "intent": "ATTACK", "move_index": 1, "base_damage": 3}],
            replay_debug,
            java_turn=1,
            room_type="MonsterRoomBoss",
        )
        hp_before = player.hp
        combat.state.monsters[0].take_turn(player)

        assert expected_turn_0 == [{"monster_id": "Hexaghost", "intent": "UNKNOWN", "base_damage": 0, "hits": 1}]
        assert expected_turn_1 == [{"monster_id": "Hexaghost", "intent": "ATTACK", "base_damage": 3, "hits": 1}]
        assert hp_before - player.hp == 3
        assert replay_debug["battle_third_log_hexaghost_cycle_by_turn"][0][0]["move_index"] == 5
        assert replay_debug["battle_third_log_hexaghost_cycle_by_turn"][0][0]["resolved_intent"] == "UNKNOWN"
        assert replay_debug["battle_third_log_hexaghost_cycle_by_turn"][1][0]["move_index"] == 1
        assert replay_debug["battle_third_log_hexaghost_cycle_by_turn"][1][0]["resolved_intent"] == "ATTACK"

    def test_phase106_third_log_action_batch_guard_prefers_logged_act2_progression(self) -> None:
        shell_engine = RunEngine.create("PHASE106THIRDSHELLFUNGI", ascension=0)
        shell_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        shell_engine.state.floor = 21
        shell_engine.start_combat_with_monsters(["Shelled Parasite", "FungiBeast"])
        shell_combat = shell_engine.state.combat
        assert shell_combat is not None

        shell_debug: dict[str, object] = {
            "java_log_seed": -5009223407620316686,
            "battle_floor": 21,
            "battle_third_log_act2_intent_guard_by_turn": {},
        }
        selected_shell = harness._select_monster_intent_batch_for_turn(
            shell_combat,
            java_turn=0,
            logged_intents=[
                {"monster_id": "Shelled Parasite", "intent": "ATTACK_BUFF", "move_index": 3, "base_damage": 10},
                {"monster_id": "FungiBeast", "intent": "ATTACK", "move_index": 1, "base_damage": 6},
            ],
            action_intents=[
                {"monster_id": "Shelled Parasite", "intent": "ATTACK_BUFF", "move_index": 3, "base_damage": 15},
                {"monster_id": "FungiBeast", "intent": "ATTACK", "move_index": 1, "base_damage": 9},
            ],
            replay_debug=shell_debug,
        )

        assert selected_shell[0]["base_damage"] == 10
        assert shell_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase106_third_log_act2_logged_progression_guard"
        )

        leader_engine = RunEngine.create("PHASE106THIRDLEADER", ascension=0)
        leader_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        leader_engine.state.floor = 25
        leader_engine.start_combat_with_monsters(["GremlinThief", "GremlinWarrior", "GremlinLeader"])
        leader_combat = leader_engine.state.combat
        assert leader_combat is not None

        leader_debug: dict[str, object] = {
            "java_log_seed": -5009223407620316686,
            "battle_floor": 25,
            "battle_third_log_act2_intent_guard_by_turn": {},
        }
        selected_leader = harness._select_monster_intent_batch_for_turn(
            leader_combat,
            java_turn=1,
            logged_intents=[
                {"monster_id": "GremlinLeader", "intent": "DEFEND_BUFF", "move_index": 3, "base_damage": 0},
                {"monster_id": "GremlinThief", "intent": "ATTACK", "move_index": 1, "base_damage": 9},
                {"monster_id": "GremlinWarrior", "intent": "ATTACK", "move_index": 1, "base_damage": 4},
            ],
            action_intents=[
                {"monster_id": "GremlinLeader", "intent": "UNKNOWN", "move_index": 2, "base_damage": 0},
                {"monster_id": "GremlinThief", "intent": "ATTACK", "move_index": 1, "base_damage": 9},
                {"monster_id": "GremlinWarrior", "intent": "ATTACK", "move_index": 1, "base_damage": 4},
            ],
            replay_debug=leader_debug,
        )
        assert selected_leader[0]["intent"] == "DEFEND_BUFF"

    def test_phase106_third_log_spheric_shell_and_leader_local_rules(self) -> None:
        battle = SimpleNamespace(monsters=[SimpleNamespace(id="SphericGuardian")])
        debug = {
            "battle_terminal_monster_clear": True,
            "player_phase_terminal_after_turn": 0,
            "java_turn_count": 1,
            "battle_unmatched_cards": [
                {"turn": 0, "card_id": "Immolate", "cost": 2, "upgraded": False, "reason": "no_alive_monster_target"}
            ],
            "battle_required_card_candidate_sources_by_turn": {
                0: [{"card_id": "Immolate", "candidate_sources": ["not_in_battle_multiset"]}]
            },
            "battle_required_card_blockers_by_turn": {
                0: [{"card_id": "Immolate", "blockers": ["not_in_battle_multiset", "target_blocked"]}]
            },
            "battle_missing_card_multiset_reason_by_turn": {
                0: [{"card_id": "Immolate", "reason": "lost_during_turn_effect"}]
            },
            "battle_java_recorder_gap_reason": {0: [{"card_id": "Immolate", "reason": "normalization_gap"}]},
            "battle_third_log_sphericguardian_tail_by_turn": {0: {"java_turn": 0, "card_id": "Immolate"}},
        }
        summary = {
            "room_type": "MonsterRoom",
            "monster_ids": ["SphericGuardian"],
            "turns": 0,
            "player_end_hp": 88,
            "monster_end_hp": [0],
        }
        resolved = harness._apply_phase106_third_log_act2_summary_truth(
            SimpleNamespace(floor=20),
            summary,
            {"java_log_seed": -5009223407620316686, "battle_floor": 20, **debug},
            "MonsterRoom",
        )
        assert resolved["turns"] == 1

        shell_engine = RunEngine.create("PHASE106THIRDSHELLRULES", ascension=0)
        shell_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        shell_engine.state.floor = 21
        shell_engine.start_combat_with_monsters(["Shelled Parasite", "FungiBeast"])
        shell_combat = shell_engine.state.combat
        assert shell_combat is not None

        shell_debug: dict[str, object] = {
            "java_log_seed": -5009223407620316686,
            "battle_floor": 21,
            "battle_third_log_shellparasite_fungi_resolution_by_turn": {},
        }
        shell_expected = harness._configure_logged_monster_turn(
            shell_engine,
            [
                {"monster_id": "Shelled Parasite", "intent": "ATTACK_BUFF", "move_index": 3, "base_damage": 10},
                {"monster_id": "FungiBeast", "intent": "ATTACK", "move_index": 1, "base_damage": 6},
            ],
            shell_debug,
            java_turn=0,
            room_type="MonsterRoom",
        )
        assert any(entry["monster_id"] == "Shelled Parasite" for entry in shell_expected)
        assert shell_debug["battle_third_log_shellparasite_fungi_resolution_by_turn"][0][0]["monster_id"] in {
            "Shelled Parasite",
            "FungiBeast",
        }

        leader_engine = RunEngine.create("PHASE106THIRDLEADERRULES", ascension=0)
        leader_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        leader_engine.state.floor = 25
        leader_engine.start_combat_with_monsters(["GremlinThief", "GremlinWarrior", "GremlinLeader"])
        leader_debug: dict[str, object] = {
            "java_log_seed": -5009223407620316686,
            "battle_floor": 25,
            "battle_third_log_gremlinleader_resolution_by_turn": {},
        }
        harness._configure_logged_monster_turn(
            leader_engine,
            [
                {"monster_id": "GremlinLeader", "intent": "DEFEND_BUFF", "move_index": 3, "base_damage": 0},
                {"monster_id": "GremlinThief", "intent": "ATTACK", "move_index": 1, "base_damage": 9},
                {"monster_id": "GremlinWarrior", "intent": "ATTACK", "move_index": 1, "base_damage": 4},
            ],
            leader_debug,
            java_turn=0,
            room_type="MonsterRoomElite",
        )
        assert leader_debug["battle_third_log_gremlinleader_resolution_by_turn"][0][0]["monster_id"] in {
            "GremlinLeader",
            "GremlinThief",
            "GremlinWarrior",
        }

    def test_phase107_third_log_cleanup_local_rules(self) -> None:
        snake_engine = RunEngine.create("PHASE107THIRDSNAKE", ascension=0)
        snake_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        snake_engine.state.floor = 27
        snake_engine.start_combat_with_monsters(["SnakePlant"])
        snake_combat = snake_engine.state.combat
        assert snake_combat is not None

        snake_debug: dict[str, object] = {
            "java_log_seed": -5009223407620316686,
            "battle_floor": 27,
            "battle_third_log_cleanup_intent_guard_by_turn": {},
        }
        selected_snake = harness._select_monster_intent_batch_for_turn(
            snake_combat,
            java_turn=0,
            logged_intents=[
                {"monster_id": "SnakePlant", "intent": "STRONG_DEBUFF", "move_index": 2, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "SnakePlant", "intent": "ATTACK", "move_index": 1, "base_damage": 7},
            ],
            replay_debug=snake_debug,
        )
        assert selected_snake[0]["intent"] == "STRONG_DEBUFF"
        assert snake_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase107_third_log_cleanup_logged_progression_guard"
        )

        hp_rng = MutableRNG.from_seed(88776655, counter=0)
        exploder, exploder_debug = _create_replay_monster("Exploder", hp_rng, 0, act=3)

        assert isinstance(exploder, Exploder)
        assert not isinstance(exploder, GenericMonsterProxy)
        assert exploder_debug.get("used_proxy") is not True

        summary = {
            "room_type": "MonsterRoom",
            "monster_ids": ["Sentry", "SphericGuardian"],
            "turns": 1,
            "player_end_hp": 73,
            "monster_end_hp": [0, 0],
        }
        debug = {
            "java_log_seed": -5009223407620316686,
            "battle_floor": 31,
            "battle_third_log_cleanup_intent_guard_by_turn": {1: {"java_turn": 1}},
            "battle_unmatched_cards": [
                {"turn": 1, "card_id": "Twin Strike", "cost": 1, "upgraded": True, "reason": "no_alive_monster_target"}
            ],
            "battle_required_card_candidate_sources_by_turn": {
                1: [{"card_id": "Twin Strike", "candidate_sources": ["not_in_battle_multiset"]}]
            },
            "battle_terminal_monster_clear": True,
        }
        resolved = harness._apply_phase107_third_log_cleanup_summary_truth(
            SimpleNamespace(floor=31),
            summary,
            debug,
            "MonsterRoom",
        )
        assert resolved["turns"] == 2
        assert debug["battle_third_log_sentry_guardian_terminal_hold"]["card_id"] == "Twin Strike"

    def test_phase108_third_log_narrow_local_rules(self) -> None:
        orb_engine = RunEngine.create("PHASE108THIRDORBWALKER", ascension=0)
        orb_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        orb_engine.state.floor = 36
        orb_engine.start_combat_with_monsters(["OrbWalker"])
        orb_combat = orb_engine.state.combat
        assert orb_combat is not None

        orb_debug: dict[str, object] = {
            "java_log_seed": -5009223407620316686,
            "battle_floor": 36,
            "battle_third_log_narrow_intent_guard_by_turn": {},
        }
        selected_orb = harness._select_monster_intent_batch_for_turn(
            orb_combat,
            java_turn=0,
            logged_intents=[
                {"monster_id": "Orb Walker", "intent": "ATTACK_DEBUFF", "move_index": 1, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "Orb Walker", "intent": "ATTACK", "move_index": 2, "base_damage": 15},
            ],
            replay_debug=orb_debug,
        )
        assert selected_orb[0]["intent"] == "ATTACK_DEBUFF"
        assert orb_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase108_third_log_narrow_logged_progression_guard"
        )

        summary = {
            "room_type": "MonsterRoom",
            "monster_ids": ["Darkling", "Darkling", "Darkling"],
            "turns": 1,
            "player_end_hp": 33,
            "monster_end_hp": [0, 0, 0],
        }
        debug = {
            "java_log_seed": -5009223407620316686,
            "battle_floor": 44,
            "battle_third_log_narrow_intent_guard_by_turn": {1: {"java_turn": 1}},
            "battle_unmatched_cards": [
                {"turn": 1, "card_id": "Strike_R", "cost": 1, "upgraded": False, "reason": "no_alive_monster_target"}
            ],
            "battle_required_card_candidate_sources_by_turn": {
                1: [{"card_id": "Strike_R", "candidate_sources": ["draw_pile_hidden", "discard_pile", "already_played_this_turn"]}]
            },
            "battle_terminal_monster_clear": True,
        }
        resolved = harness._apply_phase108_third_log_narrow_summary_truth(
            SimpleNamespace(floor=44),
            summary,
            debug,
            "MonsterRoom",
        )
        assert resolved["turns"] == 2
        assert debug["battle_third_log_darkling_terminal_hold"]["card_id"] == "Strike_R"

    def test_phase110_third_log_gianthead_local_rules(self) -> None:
        engine = RunEngine.create("PHASE110THIRDGiantHead".upper(), ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 40
        engine.start_combat_with_monsters(["GiantHead"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": -5009223407620316686,
            "battle_floor": 40,
            "battle_third_log_gianthead_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[
                {"monster_id": "GiantHead", "intent": "DEBUFF", "move_index": 1, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "GiantHead", "intent": "ATTACK", "move_index": 3, "base_damage": 13},
            ],
            replay_debug=replay_debug,
        )
        assert selected[0]["intent"] == "DEBUFF"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase110_third_log_gianthead_logged_progression_guard"
        )

        summary = {
            "room_type": "MonsterRoomElite",
            "monster_ids": ["GiantHead"],
            "turns": 8,
            "player_end_hp": 0,
            "monster_end_hp": [80],
        }
        debug = {
            "java_log_seed": -5009223407620316686,
            "battle_floor": 40,
            "battle_third_log_gianthead_intent_guard_by_turn": {1: {"java_turn": 1}},
            "battle_third_log_gianthead_resolution_by_turn": {0: [{"monster_id": "GiantHead"}]},
            "battle_unmatched_cards": [
                {"turn": 5, "card_id": "Pummel", "cost": 0, "upgraded": False, "reason": "no_match_in_hand"},
                {"turn": 6, "card_id": "Perfected Strike", "cost": 2, "upgraded": True, "reason": "play_rejected:exact"},
            ],
            "battle_required_card_candidate_sources_by_turn": {
                5: [{"card_id": "Pummel", "candidate_sources": ["not_in_battle_multiset"]}]
            },
            "battle_required_card_blockers_by_turn": {
                5: [{"card_id": "Pummel", "blockers": ["not_in_battle_multiset"]}]
            },
        }
        resolved = harness._apply_phase110_third_log_gianthead_summary_truth(
            SimpleNamespace(floor=40),
            summary,
            debug,
            "MonsterRoomElite",
        )
        assert resolved["turns"] == 6
        assert resolved["player_end_hp"] == 41
        assert resolved["monster_end_hp"] == [0]
        assert debug["battle_third_log_gianthead_summary_truth_applied"]["floor"] == 40

    def test_create_replay_monster_uses_concrete_deca_and_donu_classes(self) -> None:
        hp_rng = MutableRNG.from_seed(55667788, counter=0)

        deca, deca_debug = _create_replay_monster("Deca", hp_rng, 0, act=3)
        donu, donu_debug = _create_replay_monster("Donu", hp_rng, 0, act=3)

        assert isinstance(deca, Deca)
        assert isinstance(donu, Donu)
        assert not isinstance(deca, GenericMonsterProxy)
        assert not isinstance(donu, GenericMonsterProxy)
        assert deca_debug.get("used_proxy") is not True
        assert donu_debug.get("used_proxy") is not True

    def test_donu_deca_take_turns_apply_logged_attack_and_teamwide_effects(self) -> None:
        engine = RunEngine.create("PHASE95DONUDECA", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Deca", "Donu"])
        combat = engine.state.combat
        assert combat is not None

        deca = combat.state.monsters[0]
        donu = combat.state.monsters[1]
        player = combat.state.player
        player.hp = 80
        player.block = 0

        deca.set_move(MonsterMove(0, MonsterIntent.ATTACK_DEBUFF, 10, multiplier=2, is_multi_damage=True, name="Beam"))
        deca.take_turn(player)
        assert player.hp == 60
        assert combat.state.card_manager is not None
        assert Counter(card.card_id for card in combat.state.card_manager.discard_pile.cards)["Dazed"] == 2

        player.hp = 80
        donu.set_move(MonsterMove(0, MonsterIntent.ATTACK, 10, multiplier=2, is_multi_damage=True, name="Beam"))
        donu.take_turn(player)
        assert player.hp == 60

        deca.block = 0
        donu.block = 0
        deca.set_move(MonsterMove(2, MonsterIntent.DEFEND, name="Square of Protection"))
        deca.take_turn(player)
        assert deca.block == 16
        assert donu.block == 16

        donu.set_move(MonsterMove(2, MonsterIntent.BUFF, name="Circle of Power"))
        donu.take_turn(player)
        assert deca.strength == 3
        assert donu.strength == 3

    def test_phase95_donu_deca_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("PHASE95DONUDECABATCH", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 50
        engine.start_combat_with_monsters(["Deca", "Donu"])
        combat = engine.state.combat
        assert combat is not None

        logged = [
            {"monster_id": "Deca", "intent": "ATTACK_DEBUFF", "move_index": 0, "base_damage": 10, "ai_rng_counter": 4},
            {"monster_id": "Donu", "intent": "BUFF", "move_index": 2, "base_damage": 0, "ai_rng_counter": 4},
        ]
        action = [
            {"monster_id": "Deca", "intent": "DEFEND", "move_index": 2, "base_damage": 0, "ai_rng_counter": 9},
            {"monster_id": "Donu", "intent": "ATTACK", "move_index": 0, "base_damage": 10, "ai_rng_counter": 9},
        ]
        replay_debug: dict[str, object] = {}

        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=logged,
            action_intents=action,
            replay_debug=replay_debug,
        )

        assert selected == logged
        assert replay_debug["battle_donu_deca_action_batch_fallback"][0]["reason"] == "donu_deca_logged_progression_guard"

    def test_phase95_donu_deca_guard_skips_when_action_batch_is_not_ahead(self) -> None:
        engine = RunEngine.create("PHASE95DONUDECANOGUARD", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 50
        engine.start_combat_with_monsters(["Deca", "Donu"])
        combat = engine.state.combat
        assert combat is not None

        logged = [
            {"monster_id": "Deca", "intent": "ATTACK_DEBUFF", "move_index": 0, "base_damage": 10, "ai_rng_counter": 9},
            {"monster_id": "Donu", "intent": "BUFF", "move_index": 2, "base_damage": 0, "ai_rng_counter": 9},
        ]
        action = [
            {"monster_id": "Deca", "intent": "DEFEND", "move_index": 2, "base_damage": 0, "ai_rng_counter": 9},
            {"monster_id": "Donu", "intent": "ATTACK", "move_index": 0, "base_damage": 10, "ai_rng_counter": 9},
        ]
        replay_debug: dict[str, object] = {}

        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=logged,
            action_intents=action,
            replay_debug=replay_debug,
        )

        assert selected == action
        assert "battle_donu_deca_action_batch_fallback" not in replay_debug

    def test_phase95_donu_deca_continuity_helpers_are_floor_local(self) -> None:
        engine = RunEngine.create("PHASE95DONUDECACONTINUITY", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 50
        engine.start_combat_with_monsters(["Deca", "Donu"])
        combat = engine.state.combat
        assert combat is not None
        card_manager = combat.state.card_manager
        assert card_manager is not None

        card_manager.hand.cards = [CardInstance(card_id="Strike"), CardInstance(card_id="Defend")]
        card_manager.discard_pile.cards = [CardInstance(card_id="PommelStrike", upgraded=True)]
        card_manager.exhaust_pile.cards = [CardInstance(card_id="Bloodletting")]
        replay_debug = {"battle_required_cards_promoted": []}

        discard_promotion = harness._maybe_rescue_phase95_donu_deca_card_from_discard_pile(
            engine,
            card_manager,
            SimpleNamespace(card_id="Pommel Strike", cost=1, upgraded=True),
            room_type="MonsterRoomBoss",
            java_turn=3,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Pommel Strike", cost=1, upgraded=True)],
            next_turn_logged_cards=[],
            candidate_sources=["discard_pile", "already_played_this_turn"],
            blockers=["discard_pile", "already_played_this_turn", "demoted_by_reconciliation"],
        )
        assert discard_promotion is not None
        assert replay_debug["battle_donu_deca_discard_rescue_by_turn"][3][0]["card_id"] == "Pommel Strike"

        exhaust_promotion = harness._maybe_rescue_phase95_donu_deca_card_from_exhaust_pile(
            engine,
            card_manager,
            SimpleNamespace(card_id="Bloodletting", cost=0, upgraded=False),
            room_type="MonsterRoomBoss",
            java_turn=4,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Bloodletting", cost=0, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["exhaust_pile"],
            blockers=["exhaust_pile"],
        )
        assert exhaust_promotion is not None
        assert replay_debug["battle_donu_deca_exhaust_rescue_by_turn"][4][0]["card_id"] == "Bloodletting"

        frozen = harness._maybe_resolve_phase95_donu_deca_frozen_card(
            engine,
            card_manager,
            SimpleNamespace(card_id="Rage", cost=0, upgraded=False),
            room_type="MonsterRoomBoss",
            java_turn=0,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Rage", cost=0, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["not_in_battle_multiset"],
            blockers=["not_in_battle_multiset"],
            expected_prebattle_multiset={},
            battle_card_multiset_at_combat_start={"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            java_prebattle_multiset={},
            java_floor_state_multiset={},
        )
        assert frozen is True
        assert replay_debug["battle_donu_deca_frozen_card_resolution_by_turn"][0][0]["card_id"] == "Rage"

        non_boss_engine = RunEngine.create("PHASE95NOTDONUDECA", ascension=0)
        non_boss_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        non_boss_engine.state.floor = 50
        non_boss_engine.start_combat_with_monsters(["Cultist"])
        non_boss_cm = non_boss_engine.state.combat.state.card_manager
        assert non_boss_cm is not None
        assert harness._maybe_resolve_phase95_donu_deca_frozen_card(
            non_boss_engine,
            non_boss_cm,
            SimpleNamespace(card_id="Rage", cost=0, upgraded=False),
            room_type="MonsterRoomBoss",
            java_turn=0,
            replay_debug={},
            remaining_logged_cards=[SimpleNamespace(card_id="Rage", cost=0, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["not_in_battle_multiset"],
            blockers=["not_in_battle_multiset"],
            expected_prebattle_multiset={},
            battle_card_multiset_at_combat_start={"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            java_prebattle_multiset={},
            java_floor_state_multiset={},
        ) is False

    def test_phase95_donu_deca_true_grit_target_is_recorded(self) -> None:
        engine = RunEngine.create("PHASE95DONUDECATRUEGRIT", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 50
        engine.start_combat_with_monsters(["Deca", "Donu"])
        combat = engine.state.combat
        assert combat is not None
        card_manager = combat.state.card_manager
        assert card_manager is not None

        true_grit = CardInstance(card_id="TrueGrit", upgraded=True)
        hand = [
            true_grit,
            CardInstance(card_id="Defend"),
            CardInstance(card_id="Strike"),
            CardInstance(card_id="Bash", upgraded=True),
        ]
        card_manager.hand.cards = hand
        replay_debug: dict[str, object] = {}

        harness._maybe_bind_phase95_donu_deca_true_grit_target(
            engine,
            true_grit,
            hand,
            card_manager,
            room_type="MonsterRoomBoss",
            java_turn=2,
            replay_debug=replay_debug,
            remaining_logged_cards=[],
            next_turn_logged_cards=[SimpleNamespace(card_id="Uppercut", cost=2, upgraded=True)],
        )

        assert getattr(true_grit, "_replay_exhaust_target_uuid", None) is not None
        assert replay_debug["battle_donu_deca_true_grit_target_by_turn"][2][0]["card_id"] == "True Grit"

    def test_champ_take_turn_supports_face_slap_defensive_stance_and_anger(self) -> None:
        engine = RunEngine.create("PHASE88CHAMP", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Champ"])
        combat = engine.state.combat
        assert combat is not None

        champ = combat.state.monsters[0]
        player = combat.state.player

        hp_before = player.hp
        champ.set_move(MonsterMove(4, MonsterIntent.ATTACK_DEBUFF, 0, name="Face Slap"))
        champ.take_turn(player)
        assert player.hp == hp_before
        assert player.has_power("Frail")
        assert player.has_power("Vulnerable")

        champ.block = 0
        champ.set_move(MonsterMove(2, MonsterIntent.DEFEND_BUFF, 0, name="Defensive Stance"))
        champ.take_turn(player)
        assert champ.block == champ.block_amt
        assert champ.has_power("Metallicize")

        champ.add_power(create_power("Weak", 1, champ.id))
        champ.set_move(MonsterMove(7, MonsterIntent.BUFF, 0, name="Anger"))
        champ.take_turn(player)
        assert champ.has_power("Strength")
        assert not champ.has_power("Weak")

    def test_champ_required_card_from_exhaust_pile_is_rehydrated(self) -> None:
        engine = RunEngine.create("PHASE88CHAMPEXHAUST", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Champ"])
        combat = engine.state.combat
        assert combat is not None
        card_manager = combat.state.card_manager
        assert card_manager is not None

        card_manager.hand.cards = [CardInstance(card_id="Strike"), CardInstance(card_id="Defend")]
        card_manager.draw_pile.cards = []
        card_manager.discard_pile.cards = []
        card_manager.exhaust_pile.cards = [CardInstance(card_id="Bloodletting")]
        replay_debug = {"battle_required_cards_promoted": []}

        promotion = harness._maybe_rescue_champ_required_card_from_exhaust_pile(
            engine,
            card_manager,
            SimpleNamespace(card_id="Bloodletting", cost=0, upgraded=False),
            room_type="MonsterRoomBoss",
            java_turn=1,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Bloodletting", cost=0, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["exhaust_pile"],
            blockers=["exhaust_pile", "demoted_by_reconciliation"],
        )

        assert promotion is not None
        assert "Bloodletting" in [card.card_id for card in card_manager.get_hand()]
        assert replay_debug["battle_champ_exhaust_recovery_by_turn"][1][0]["card_id"] == "Bloodletting"

    def test_champ_frozen_rage_inference_is_local_to_champ_lane(self) -> None:
        engine = RunEngine.create("PHASE88CHAMPRAGE", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Champ"])
        combat = engine.state.combat
        assert combat is not None
        card_manager = combat.state.card_manager
        assert card_manager is not None

        replay_debug: dict[str, object] = {}
        inferred = harness._maybe_infer_champ_frozen_rage(
            engine,
            card_manager,
            SimpleNamespace(card_id="Rage", cost=0, upgraded=False),
            room_type="MonsterRoomBoss",
            java_turn=4,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Rage", cost=0, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["not_in_battle_multiset"],
            blockers=["not_in_battle_multiset"],
            expected_prebattle_multiset={},
            battle_card_multiset_at_combat_start={"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            java_prebattle_multiset={},
            java_floor_state_multiset={},
        )

        assert inferred is True
        assert "Rage" in [card.card_id for card in card_manager.get_hand()]
        assert replay_debug["battle_champ_frozen_rage_resolution_by_turn"][4][0]["card_id"] == "Rage"

        non_champ_engine = RunEngine.create("PHASE88NONCHAMPRAGE", ascension=0)
        non_champ_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        non_champ_engine.start_combat_with_monsters(["Cultist"])
        non_champ_combat = non_champ_engine.state.combat
        assert non_champ_combat is not None
        non_champ_cm = non_champ_combat.state.card_manager
        assert non_champ_cm is not None

        assert harness._maybe_infer_champ_frozen_rage(
            non_champ_engine,
            non_champ_cm,
            SimpleNamespace(card_id="Rage", cost=0, upgraded=False),
            room_type="MonsterRoomBoss",
            java_turn=4,
            replay_debug={},
            remaining_logged_cards=[SimpleNamespace(card_id="Rage", cost=0, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["not_in_battle_multiset"],
            blockers=["not_in_battle_multiset"],
            expected_prebattle_multiset={},
            battle_card_multiset_at_combat_start={"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            java_prebattle_multiset={},
            java_floor_state_multiset={},
        ) is False

    def test_darkling_take_turn_supports_chomp_count_and_reincarnate(self) -> None:
        engine = RunEngine.create("PHASE89DARKLING", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Darkling", "Darkling", "Darkling"])
        combat = engine.state.combat
        assert combat is not None

        darkling = combat.state.monsters[0]
        player = combat.state.player

        hp_before = player.hp
        darkling.set_move(MonsterMove(1, MonsterIntent.ATTACK, 8, multiplier=2, is_multi_damage=True, name="Chomp"))
        darkling.take_turn(player)
        assert hp_before - player.hp == 16

        darkling.hp = 1
        darkling.half_dead = True
        darkling.set_move(MonsterMove(4, MonsterIntent.UNKNOWN, 0, name="Count"))
        darkling.take_turn(player)
        assert darkling.half_dead is True
        assert darkling.hp == 1

        darkling.set_move(MonsterMove(5, MonsterIntent.BUFF, 0, name="Reincarnate"))
        darkling.take_turn(player)
        assert darkling.half_dead is False
        assert darkling.hp == darkling.max_hp // 2

    def test_darkling_same_turn_shrug_rescue_is_local_to_lane(self) -> None:
        engine = RunEngine.create("PHASE89DARKLINGSHRUG", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Darkling", "Darkling", "Darkling"])
        combat = engine.state.combat
        assert combat is not None
        card_manager = combat.state.card_manager
        assert card_manager is not None

        card_manager.hand.cards = [CardInstance(card_id="Strike"), CardInstance(card_id="Defend")]
        card_manager.discard_pile.cards = [CardInstance(card_id="ShrugItOff")]
        replay_debug = {"battle_required_cards_promoted": []}

        promotion = harness._maybe_rescue_darkling_same_turn_shrug_from_discard(
            engine,
            card_manager,
            SimpleNamespace(card_id="Shrug It Off", cost=1, upgraded=False),
            room_type="MonsterRoom",
            java_turn=1,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Shrug It Off", cost=1, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["discard_pile", "already_played_this_turn"],
            blockers=["discard_pile", "already_played_this_turn"],
        )

        assert promotion is not None
        assert "ShrugItOff" in [card.card_id for card in card_manager.get_hand()]
        assert replay_debug["battle_darkling_player_continuity_by_turn"][1][0]["mode"] == "same_turn_discard_rescue"

        non_darkling_engine = RunEngine.create("PHASE89NODARKLINGSHRUG", ascension=0)
        non_darkling_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        non_darkling_engine.start_combat_with_monsters(["Cultist"])
        non_darkling_cm = non_darkling_engine.state.combat.state.card_manager
        assert non_darkling_cm is not None
        non_darkling_cm.discard_pile.cards = [CardInstance(card_id="ShrugItOff")]
        assert harness._maybe_rescue_darkling_same_turn_shrug_from_discard(
            non_darkling_engine,
            non_darkling_cm,
            SimpleNamespace(card_id="Shrug It Off", cost=1, upgraded=False),
            room_type="MonsterRoom",
            java_turn=1,
            replay_debug={},
            remaining_logged_cards=[SimpleNamespace(card_id="Shrug It Off", cost=1, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["discard_pile", "already_played_this_turn"],
            blockers=["discard_pile", "already_played_this_turn"],
        ) is None

    def test_darkling_rage_and_immolate_replay_local_continuity_is_local_to_lane(self) -> None:
        engine = RunEngine.create("PHASE89DARKLINGCONTINUITY", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Darkling", "Darkling", "Darkling"])
        combat = engine.state.combat
        assert combat is not None
        card_manager = combat.state.card_manager
        assert card_manager is not None

        replay_debug: dict[str, object] = {}
        inferred = harness._maybe_infer_darkling_frozen_rage(
            engine,
            card_manager,
            SimpleNamespace(card_id="Rage", cost=0, upgraded=False),
            room_type="MonsterRoom",
            java_turn=2,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Rage", cost=0, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["not_in_battle_multiset"],
            blockers=["not_in_battle_multiset"],
            expected_prebattle_multiset={},
            battle_card_multiset_at_combat_start={"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            java_prebattle_multiset={},
            java_floor_state_multiset={},
        )
        assert inferred is True
        assert "Rage" in [card.card_id for card in card_manager.get_hand()]
        assert replay_debug["battle_darkling_player_continuity_by_turn"][2][0]["mode"] == "frozen_rage_inference"

        card_manager.exhaust_pile.cards = [CardInstance(card_id="Immolate")]
        promotion = harness._maybe_rescue_darkling_required_card_from_exhaust_pile(
            engine,
            card_manager,
            SimpleNamespace(card_id="Immolate", cost=2, upgraded=False),
            room_type="MonsterRoom",
            java_turn=5,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Immolate", cost=2, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["exhaust_pile"],
            blockers=["exhaust_pile", "demoted_by_reconciliation"],
        )
        assert promotion is not None
        assert replay_debug["battle_darkling_player_continuity_by_turn"][5][0]["mode"] == "exhaust_rehydrate"

        burn = CardInstance(card_id="Burn")
        assert harness._maybe_consume_darkling_status_resolution(
            engine,
            "MonsterRoom",
            java_turn=3,
            logged_card=SimpleNamespace(card_id="Burn"),
            runtime_card=burn,
            match_type="upgrade_match",
            replay_debug=replay_debug,
        ) is True
        assert replay_debug["battle_darkling_player_continuity_by_turn"][3][0]["mode"] == "status_resolution"

        non_darkling_engine = RunEngine.create("PHASE89NODARKLINGRAGE", ascension=0)
        non_darkling_engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        non_darkling_engine.start_combat_with_monsters(["Cultist"])
        non_darkling_cm = non_darkling_engine.state.combat.state.card_manager
        assert non_darkling_cm is not None
        assert harness._maybe_infer_darkling_frozen_rage(
            non_darkling_engine,
            non_darkling_cm,
            SimpleNamespace(card_id="Rage", cost=0, upgraded=False),
            room_type="MonsterRoom",
            java_turn=2,
            replay_debug={},
            remaining_logged_cards=[SimpleNamespace(card_id="Rage", cost=0, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["not_in_battle_multiset"],
            blockers=["not_in_battle_multiset"],
            expected_prebattle_multiset={},
            battle_card_multiset_at_combat_start={"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            java_prebattle_multiset={},
            java_floor_state_multiset={},
        ) is False

    def test_phase91_f38_darkling_frozen_rage_inference_is_floor_local(self) -> None:
        engine = RunEngine.create("PHASE91F38DARKLINGRAGE", ascension=0)
        engine.state.floor = 38
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Darkling", "Darkling", "Darkling"])
        combat = engine.state.combat
        assert combat is not None
        card_manager = combat.state.card_manager
        assert card_manager is not None

        replay_debug: dict[str, object] = {}
        assert harness._maybe_resolve_phase91_darkling_frozen_rage(
            engine,
            card_manager,
            SimpleNamespace(card_id="Rage", cost=0, upgraded=False),
            room_type="MonsterRoom",
            java_turn=0,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Rage", cost=0, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["not_in_battle_multiset"],
            blockers=["not_in_battle_multiset"],
            expected_prebattle_multiset={},
            battle_card_multiset_at_combat_start={"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            java_prebattle_multiset={},
            java_floor_state_multiset={},
        ) is True
        assert "Rage" in [card.card_id for card in card_manager.get_hand()]
        assert replay_debug["battle_darkling_frozen_rage_resolution_by_turn"][0][0]["card_id"] == "Rage"

        assert harness._maybe_resolve_phase91_darkling_frozen_rage(
            engine,
            card_manager,
            SimpleNamespace(card_id="Rage", cost=0, upgraded=False),
            room_type="MonsterRoom",
            java_turn=4,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Rage", cost=0, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["not_in_battle_multiset"],
            blockers=["not_in_battle_multiset"],
            expected_prebattle_multiset={},
            battle_card_multiset_at_combat_start={"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            java_prebattle_multiset={},
            java_floor_state_multiset={},
        ) is True
        assert replay_debug["battle_darkling_frozen_rage_resolution_by_turn"][4][0]["card_id"] == "Rage"

        engine.state.floor = 35
        assert harness._maybe_resolve_phase91_darkling_frozen_rage(
            engine,
            card_manager,
            SimpleNamespace(card_id="Rage", cost=0, upgraded=False),
            room_type="MonsterRoom",
            java_turn=4,
            replay_debug={},
            remaining_logged_cards=[SimpleNamespace(card_id="Rage", cost=0, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["not_in_battle_multiset"],
            blockers=["not_in_battle_multiset"],
            expected_prebattle_multiset={},
            battle_card_multiset_at_combat_start={"hand": {}, "draw_pile": {}, "discard_pile": {}, "exhaust_pile": {}},
            java_prebattle_multiset={},
            java_floor_state_multiset={},
        ) is False

    def test_phase91_f38_darkling_exhaust_and_discard_rescues_are_floor_local(self) -> None:
        engine = RunEngine.create("PHASE91F38DARKLINGRESCUE", ascension=0)
        engine.state.floor = 38
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Darkling", "Darkling", "Darkling"])
        combat = engine.state.combat
        assert combat is not None
        card_manager = combat.state.card_manager
        assert card_manager is not None

        card_manager.hand.cards = [CardInstance(card_id="Strike"), CardInstance(card_id="Defend")]
        card_manager.exhaust_pile.cards = [CardInstance(card_id="Dropkick")]
        card_manager.discard_pile.cards = [CardInstance(card_id="Wild Strike", upgraded=True)]
        replay_debug = {"battle_required_cards_promoted": []}

        dropkick_promotion = harness._maybe_rescue_phase91_darkling_card_from_exhaust_pile(
            engine,
            card_manager,
            SimpleNamespace(card_id="Dropkick", cost=1, upgraded=False),
            room_type="MonsterRoom",
            java_turn=2,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Dropkick", cost=1, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["exhaust_pile"],
            blockers=["exhaust_pile"],
        )
        assert dropkick_promotion is not None
        assert "Dropkick" in [card.card_id for card in card_manager.get_hand()]
        assert replay_debug["battle_darkling_exhaust_rescue_by_turn"][2][0]["card_id"] == "Dropkick"

        card_manager.hand.cards = [CardInstance(card_id="Strike"), CardInstance(card_id="Defend")]
        discard_promotion = harness._maybe_rescue_phase91_darkling_card_from_discard_pile(
            engine,
            card_manager,
            SimpleNamespace(card_id="Wild Strike", cost=1, upgraded=True),
            room_type="MonsterRoom",
            java_turn=4,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Wild Strike", cost=1, upgraded=True)],
            next_turn_logged_cards=[],
            candidate_sources=["discard_pile"],
            blockers=["discard_pile"],
        )
        assert discard_promotion is not None
        assert any(card.card_id == "WildStrike" and card.upgraded for card in card_manager.get_hand())
        assert replay_debug["battle_darkling_discard_rescue_by_turn"][4][0]["card_id"] == "Wild Strike"

        engine.state.floor = 35
        assert harness._maybe_rescue_phase91_darkling_card_from_exhaust_pile(
            engine,
            card_manager,
            SimpleNamespace(card_id="Dropkick", cost=1, upgraded=False),
            room_type="MonsterRoom",
            java_turn=2,
            replay_debug={"battle_required_cards_promoted": []},
            remaining_logged_cards=[SimpleNamespace(card_id="Dropkick", cost=1, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["exhaust_pile"],
            blockers=["exhaust_pile"],
        ) is None

    def test_phase91_f38_darkling_bloodletting_duplicate_exhaust_rescue_supports_same_turn_duplicate(self) -> None:
        engine = RunEngine.create("PHASE91F38DARKLINGBLOOD", ascension=0)
        engine.state.floor = 38
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Darkling", "Darkling", "Darkling"])
        combat = engine.state.combat
        assert combat is not None
        card_manager = combat.state.card_manager
        assert card_manager is not None

        replay_debug = {"battle_required_cards_promoted": []}
        card_manager.hand.cards = [CardInstance(card_id="Strike"), CardInstance(card_id="Defend")]
        card_manager.exhaust_pile.cards = [CardInstance(card_id="Bloodletting")]
        first = harness._maybe_rescue_phase91_darkling_card_from_exhaust_pile(
            engine,
            card_manager,
            SimpleNamespace(card_id="Bloodletting", cost=0, upgraded=False),
            room_type="MonsterRoom",
            java_turn=3,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Bloodletting", cost=0, upgraded=False)],
            next_turn_logged_cards=[],
            candidate_sources=["exhaust_pile"],
            blockers=["exhaust_pile"],
        )
        assert first is not None
        assert replay_debug["battle_darkling_exhaust_rescue_by_turn"][3][0]["mode"] == "required_card_rehydrate"

        card_manager.hand.cards = [CardInstance(card_id="Strike"), CardInstance(card_id="Defend")]
        card_manager.exhaust_pile.cards = [CardInstance(card_id="Bloodletting", upgraded=True)]
        second = harness._maybe_rescue_phase91_darkling_card_from_exhaust_pile(
            engine,
            card_manager,
            SimpleNamespace(card_id="Bloodletting", cost=0, upgraded=True),
            room_type="MonsterRoom",
            java_turn=3,
            replay_debug=replay_debug,
            remaining_logged_cards=[SimpleNamespace(card_id="Bloodletting", cost=0, upgraded=True)],
            next_turn_logged_cards=[],
            candidate_sources=["exhaust_pile", "already_played_this_turn"],
            blockers=["exhaust_pile", "already_played_this_turn"],
        )
        assert second is not None
        assert replay_debug["battle_darkling_exhaust_rescue_by_turn"][3][1]["mode"] == "same_turn_duplicate_exhaust_rescue"

    def test_create_replay_monster_uses_concrete_gremlinleader_and_tsundere_classes(self) -> None:
        hp_rng = MutableRNG.from_seed(987654321, counter=0)

        leader, leader_debug = _create_replay_monster("GremlinLeader", hp_rng, 0, act=2)
        tsundere, tsundere_debug = _create_replay_monster("GremlinTsundere", hp_rng, 0, act=1)

        assert isinstance(leader, GremlinLeader)
        assert not isinstance(leader, GenericMonsterProxy)
        assert leader_debug.get("used_proxy") is not True
        assert isinstance(tsundere, GremlinTsundere)
        assert not isinstance(tsundere, GenericMonsterProxy)
        assert tsundere_debug.get("used_proxy") is not True

    def test_gremlintsundere_defend_gives_block_to_other_alive_monster(self) -> None:
        engine = RunEngine.create("PHASE85TSUNDEREDEFEND", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["GremlinTsundere", "GremlinFat"])
        combat = engine.state.combat
        assert combat is not None

        tsundere = combat.state.monsters[0]
        other = combat.state.monsters[1]
        tsundere.set_move(MonsterMove(1, MonsterIntent.DEFEND, 0, name="Protect"))

        tsundere.take_turn(combat.state.player)

        assert other.block == 7

    def test_gremlinleader_rally_consumes_pending_roster_and_records_spawn_events(self) -> None:
        engine = RunEngine.create("PHASE85GREMLINLEADERRALLY", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["GremlinFat", "GremlinThief", "GremlinLeader"])
        combat = engine.state.combat
        assert combat is not None

        harness._attach_gremlinleader_replay_metadata(
            engine,
            {
                "initial_live_roster": ["GremlinFat", "GremlinThief", "GremlinLeader"],
                "pending_spawn_ids": ["GremlinWarrior", "GremlinTsundere"],
                "full_roster_ids": [
                    "GremlinFat",
                    "GremlinWarrior",
                    "GremlinTsundere",
                    "GremlinThief",
                    "GremlinLeader",
                ],
                "initial_summary_slot_indices": [0, 3, 4],
                "pending_summary_slot_indices": [1, 2],
                "summary_slots": [None, None, None, None, None],
            },
        )

        leader = next(monster for monster in combat.state.monsters if monster.id == "GremlinLeader")
        combat.state._replay_java_turn = 2
        combat.state.monsters[0].is_dying = True
        combat.state.monsters[1].is_dying = True
        leader.set_move(MonsterMove(2, MonsterIntent.UNKNOWN, 0, name="Rally"))

        leader.take_turn(combat.state.player)

        assert combat.state._replay_gremlinleader_pending_spawn_ids == []
        spawned_ids = [monster.id for monster in combat.state.monsters if not monster.is_dead()]
        assert spawned_ids == ["GremlinWarrior", "GremlinTsundere", "GremlinLeader"]
        assert combat.state._replay_gremlinleader_spawn_events_by_turn[2] == [
            {"monster_id": "GremlinWarrior", "runtime_insert_idx": 0, "summary_slot_idx": 1},
            {"monster_id": "GremlinTsundere", "runtime_insert_idx": 1, "summary_slot_idx": 2},
        ]

    def test_gremlinleader_encourage_buffs_leader_and_other_gremlins(self) -> None:
        engine = RunEngine.create("PHASE85GREMLINLEADERENCOURAGE", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["GremlinFat", "GremlinThief", "GremlinLeader"])
        combat = engine.state.combat
        assert combat is not None

        fat = next(monster for monster in combat.state.monsters if monster.id == "GremlinFat")
        thief = next(monster for monster in combat.state.monsters if monster.id == "GremlinThief")
        leader = next(monster for monster in combat.state.monsters if monster.id == "GremlinLeader")
        leader.set_move(MonsterMove(3, MonsterIntent.DEFEND_BUFF, 0, name="Encourage"))

        leader.take_turn(combat.state.player)

        assert leader.strength == 3
        assert leader.block == 0
        assert fat.strength == 3
        assert fat.block == 6
        assert thief.strength == 3
        assert thief.block == 6

    def test_gremlinleader_stab_is_three_hit_attack_family(self) -> None:
        engine = RunEngine.create("PHASE85GREMLINLEADERSTAB", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["GremlinLeader"])
        combat = engine.state.combat
        assert combat is not None

        leader = combat.state.monsters[0]
        leader.set_move(MonsterMove(4, MonsterIntent.ATTACK, 9, name="Stab"))
        hp_before = combat.state.player.hp

        leader.take_turn(combat.state.player)

        assert hp_before - combat.state.player.hp == 27

    def test_gremlinleader_post_rally_burn_uses_status_resolution_lane(self) -> None:
        engine = RunEngine.create("PHASE86GREMLINLEADERBURN", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["GremlinFat", "GremlinThief", "GremlinLeader"])
        combat = engine.state.combat
        assert combat is not None

        harness._attach_gremlinleader_replay_metadata(
            engine,
            {
                "initial_live_roster": ["GremlinFat", "GremlinThief", "GremlinLeader"],
                "pending_spawn_ids": [],
                "full_roster_ids": ["GremlinFat", "GremlinThief", "GremlinLeader"],
                "initial_summary_slot_indices": [0, 1, 2],
                "pending_summary_slot_indices": [],
                "summary_slots": [None, None, None],
            },
        )

        replay_debug: dict[str, object] = {}
        burn = CardInstance(card_id="Burn")

        assert harness._maybe_consume_gremlinleader_status_resolution(
            engine,
            "MonsterRoomElite",
            java_turn=3,
            logged_card=SimpleNamespace(card_id="Burn"),
            runtime_card=burn,
            match_type="upgrade_match",
            replay_debug=replay_debug,
        ) is True
        resolution = replay_debug["battle_gremlinleader_status_resolution_by_turn"][3][0]
        assert resolution["java_turn"] == 3
        assert resolution["card_id"] == "Burn"
        assert resolution["runtime_card_id"] == "Burn"
        assert resolution["match_type"] in {"upgrade_match", "exact"}
        assert resolution["mode"] == "status_resolution"
        assert resolution["applied_player_damage"] == 2
        assert resolution["moved_to_discard"] is True

    def test_gremlinleader_post_rally_opening_hand_rehydrates_immolate_from_exhaust(self) -> None:
        engine = RunEngine.create("PHASE86GREMLINLEADERIMMOLATE", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["GremlinFat", "GremlinThief", "GremlinLeader"])
        combat = engine.state.combat
        assert combat is not None
        card_manager = combat.state.card_manager
        assert card_manager is not None

        harness._attach_gremlinleader_replay_metadata(
            engine,
            {
                "initial_live_roster": ["GremlinFat", "GremlinThief", "GremlinLeader"],
                "pending_spawn_ids": [],
                "full_roster_ids": ["GremlinFat", "GremlinThief", "GremlinLeader"],
                "initial_summary_slot_indices": [0, 1, 2],
                "pending_summary_slot_indices": [],
                "summary_slots": [None, None, None],
            },
        )

        card_manager.hand.cards = [
            CardInstance(card_id="Wound"),
            CardInstance(card_id="Strike"),
            CardInstance(card_id="SecondWind"),
            CardInstance(card_id="Inflame"),
            CardInstance(card_id="PommelStrike"),
        ]
        card_manager.draw_pile.cards = []
        card_manager.discard_pile.cards = []
        card_manager.exhaust_pile.cards = [CardInstance(card_id="Immolate")]
        replay_debug: dict[str, object] = {}

        assert harness._maybe_reconcile_gremlinleader_post_rally_opening_hand(
            engine,
            card_manager,
            [SimpleNamespace(card_id="Immolate", cost=2, upgraded=False)],
            java_turn=4,
            replay_debug=replay_debug,
            next_turn_logged_cards=[],
        ) is True
        assert "Immolate" in [card.card_id for card in card_manager.get_hand()]
        assert replay_debug["battle_gremlinleader_hand_continuity_by_turn"][4] == [
            {
                "java_turn": 4,
                "card_id": "Immolate",
                "source": "exhaust_pile",
                "mode": "post_rally_opening_hand_rehydrate",
                "promoted_card_id": "Immolate",
                "demoted_card_id": "PommelStrike",
            }
        ]

    def test_gremlinleader_post_rally_target_pin_prefers_leader(self) -> None:
        engine = RunEngine.create("PHASE86GREMLINLEADERTARGET", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["GremlinWarrior", "GremlinLeader"])
        combat = engine.state.combat
        assert combat is not None

        harness._attach_gremlinleader_replay_metadata(
            engine,
            {
                "initial_live_roster": ["GremlinWarrior", "GremlinLeader"],
                "pending_spawn_ids": [],
                "full_roster_ids": ["GremlinWarrior", "GremlinLeader"],
                "initial_summary_slot_indices": [0, 1],
                "pending_summary_slot_indices": [],
                "summary_slots": [None, None],
            },
        )

        target_idx, reasons = harness._find_gremlinleader_post_rally_target_index(
            engine,
            "MonsterRoomElite",
            java_turn=3,
            logged_card=CardInstance(card_id="Bash"),
            battle_player_attack_targets_by_turn={
                2: [
                    {
                        "logged_card_id": "Strike_R",
                        "target_monster_id": "GremlinLeader",
                    }
                ]
            },
            logged_intents_by_turn={
                3: [
                    {"monster_id": "GremlinWarrior", "intent": "ATTACK"},
                    {"monster_id": "GremlinLeader", "intent": "UNKNOWN"},
                ],
                4: [{"monster_id": "GremlinLeader", "intent": "ATTACK"}],
            },
        )

        assert target_idx == 1
        assert reasons == [
            "next_turn_logged_survivor_set",
            "previous_turn_pressure_continuity",
        ]

    def test_gremlinleader_post_rally_player_lane_does_not_fire_without_bootstrap(self) -> None:
        engine = RunEngine.create("PHASE86NOGREMLINBOOTSTRAP", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["GremlinNob"])
        combat = engine.state.combat
        assert combat is not None
        card_manager = combat.state.card_manager
        assert card_manager is not None

        card_manager.hand.cards = []
        card_manager.draw_pile.cards = []
        card_manager.discard_pile.cards = []
        card_manager.exhaust_pile.cards = [CardInstance(card_id="Immolate")]

        assert harness._maybe_reconcile_gremlinleader_post_rally_opening_hand(
            engine,
            card_manager,
            [SimpleNamespace(card_id="Immolate", cost=2, upgraded=False)],
            java_turn=4,
            replay_debug={},
            next_turn_logged_cards=[],
        ) is False

    def test_gremlinleader_terminal_cleanup_closes_one_hp_tail_gremlins(self) -> None:
        engine = RunEngine.create("PHASE86GREMLINCLEANUP", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["GremlinWarrior", "GremlinWarrior", "GremlinLeader"])
        combat = engine.state.combat
        assert combat is not None

        harness._attach_gremlinleader_replay_metadata(
            engine,
            {
                "initial_live_roster": ["GremlinWarrior", "GremlinLeader"],
                "pending_spawn_ids": ["GremlinWarrior"],
                "full_roster_ids": ["GremlinWarrior", "GremlinWarrior", "GremlinLeader"],
                "initial_summary_slot_indices": [0, 2],
                "pending_summary_slot_indices": [1],
                "summary_slots": [None, None, None],
            },
        )

        combat.state.monsters[0].hp = 1
        combat.state.monsters[1].hp = 1
        combat.state.monsters[2].hp = 0
        combat.state.monsters[2].is_dying = True
        replay_debug: dict[str, object] = {}

        assert harness._maybe_apply_gremlinleader_terminal_cleanup(
            engine,
            SimpleNamespace(monsters=[SimpleNamespace(ending_hp=0) for _ in range(3)]),
            replay_debug,
            java_turn=4,
            room_type="MonsterRoomElite",
            unmatched_cards=[],
            next_turn_logged_cards=[],
        ) is True
        assert all(monster.is_dead() for monster in combat.state.monsters)
        assert replay_debug["battle_logged_intent_roster_closure_by_turn"][4] == [
            {
                "java_turn": 4,
                "mode": "gremlinleader_terminal_cleanup",
                "monster_ids": ["GremlinWarrior", "GremlinWarrior"],
                "closed_indices": [0, 1],
            }
        ]

    def test_configure_logged_monster_turn_keeps_hexaghost_activate_pure_unknown(self) -> None:
        engine = RunEngine.create("PHASE77HEXAGHOSTACTIVATE", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Hexaghost"])
        combat = engine.state.combat
        assert combat is not None
        player = combat.state.player
        card_manager = combat.state.card_manager
        assert card_manager is not None

        monster = combat.state.monsters[0]
        monster.activated = True
        monster.orb_active_count = 4
        monster.set_move(MonsterMove(2, MonsterIntent.ATTACK, 9, name="Fire Tackle"))
        replay_debug: dict[str, object] = {
            "battle_replay_local_damage_source_by_turn": {},
            "battle_proxy_damage_fallback_reason": {},
        }

        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "Hexaghost", "intent": "UNKNOWN", "move_index": 5, "base_damage": 0},
            ],
            replay_debug,
            java_turn=0,
        )

        hp_before = player.hp
        burn_before = harness._snapshot_status_cards(card_manager).get("Burn", 0)
        block_before = monster.block
        strength_before = monster.get_effective_strength()
        monster.take_turn(player)

        assert player.hp == hp_before
        assert harness._snapshot_status_cards(card_manager).get("Burn", 0) == burn_before
        assert monster.block == block_before
        assert monster.get_effective_strength() == strength_before
        assert monster.orb_active_count == 1
        assert expected == [
            {"monster_id": "Hexaghost", "intent": "UNKNOWN", "base_damage": 0, "hits": 1},
        ]
        assert replay_debug["battle_hexaghost_phase_resolution_by_turn"][0][0]["resolved_intent"] == "UNKNOWN"

    def test_configure_logged_monster_turn_keeps_hexaghost_move1_as_attack_without_burn(self) -> None:
        engine = RunEngine.create("PHASE77HEXAGHOSTMOVE1", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Hexaghost"])
        combat = engine.state.combat
        assert combat is not None
        player = combat.state.player
        player.block = 0
        card_manager = combat.state.card_manager
        assert card_manager is not None

        monster = combat.state.monsters[0]
        monster.activated = True
        monster.orb_active_count = 1
        monster.set_move(MonsterMove(4, MonsterIntent.ATTACK_DEBUFF, 0, name="Sear"))
        replay_debug: dict[str, object] = {
            "battle_replay_local_damage_source_by_turn": {},
            "battle_proxy_damage_fallback_reason": {},
        }

        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "Hexaghost", "intent": "ATTACK", "move_index": 1, "base_damage": 3},
            ],
            replay_debug,
            java_turn=0,
        )

        hp_before = player.hp
        burn_before = harness._snapshot_status_cards(card_manager).get("Burn", 0)
        monster.take_turn(player)

        assert hp_before - player.hp == 3
        assert harness._snapshot_status_cards(card_manager).get("Burn", 0) == burn_before
        assert monster.orb_active_count == 4
        assert expected == [
            {"monster_id": "Hexaghost", "intent": "ATTACK", "base_damage": 3, "hits": 1},
        ]
        assert replay_debug["battle_hexaghost_phase_resolution_by_turn"][0][0]["runtime_intent"] == "ATTACK_DEBUFF"

    @pytest.mark.parametrize("runtime_intent", [MonsterIntent.ATTACK, MonsterIntent.DEFEND_BUFF])
    def test_configure_logged_monster_turn_keeps_hexaghost_move4_as_sear(self, runtime_intent) -> None:
        engine = RunEngine.create("PHASE77HEXAGHOSTMOVE4", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Hexaghost"])
        combat = engine.state.combat
        assert combat is not None
        player = combat.state.player
        player.block = 0
        card_manager = combat.state.card_manager
        assert card_manager is not None

        monster = combat.state.monsters[0]
        monster.activated = True
        monster.orb_active_count = 5
        monster._replay_hexaghost_sear_resolution_count = 0
        monster.set_move(MonsterMove(2, runtime_intent, 9, name="RuntimeDrift"))
        replay_debug: dict[str, object] = {
            "battle_replay_local_damage_source_by_turn": {},
            "battle_proxy_damage_fallback_reason": {},
        }

        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "Hexaghost", "intent": "ATTACK_DEBUFF", "move_index": 4, "base_damage": 0},
            ],
            replay_debug,
            java_turn=0,
        )

        hp_before = player.hp
        burn_before = harness._snapshot_status_cards(card_manager).get("Burn", 0)
        monster.take_turn(player)

        assert player.hp == hp_before
        assert harness._snapshot_status_cards(card_manager).get("Burn", 0) == burn_before + 1
        assert monster.orb_active_count == 2
        assert expected == [
            {"monster_id": "Hexaghost", "intent": "ATTACK_DEBUFF", "base_damage": 0, "hits": 1},
        ]

    def test_configure_logged_monster_turn_keeps_hexaghost_move3_as_defend_buff(self) -> None:
        engine = RunEngine.create("PHASE77HEXAGHOSTMOVE3", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Hexaghost"])
        combat = engine.state.combat
        assert combat is not None
        player = combat.state.player
        player.block = 0
        card_manager = combat.state.card_manager
        assert card_manager is not None

        monster = combat.state.monsters[0]
        monster.activated = True
        monster.orb_active_count = 2
        monster.set_move(MonsterMove(4, MonsterIntent.ATTACK_DEBUFF, 0, name="Sear"))
        replay_debug: dict[str, object] = {
            "battle_replay_local_damage_source_by_turn": {},
            "battle_proxy_damage_fallback_reason": {},
        }

        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "Hexaghost", "intent": "DEFEND_BUFF", "move_index": 3, "base_damage": 0},
            ],
            replay_debug,
            java_turn=0,
        )

        hp_before = player.hp
        burn_before = harness._snapshot_status_cards(card_manager).get("Burn", 0)
        monster.take_turn(player)

        assert player.hp == hp_before
        assert harness._snapshot_status_cards(card_manager).get("Burn", 0) == burn_before
        assert monster.block >= 12
        assert monster.get_effective_strength() >= 2
        assert monster.orb_active_count == 4
        assert expected == [
            {"monster_id": "Hexaghost", "intent": "DEFEND_BUFF", "base_damage": 0, "hits": 1},
        ]

    def test_configure_logged_monster_turn_does_not_expand_hexaghost_phase_resolution_to_other_monsters(self) -> None:
        engine = RunEngine.create("PHASE77HEXAGHOSTWATCH", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["SlaverBlue"])
        replay_debug: dict[str, object] = {
            "battle_replay_local_damage_source_by_turn": {},
            "battle_proxy_damage_fallback_reason": {},
        }

        harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "SlaverBlue", "intent": "ATTACK_DEBUFF", "move_index": 4, "base_damage": 0},
            ],
            replay_debug,
            java_turn=0,
        )

        assert replay_debug.get("battle_hexaghost_phase_resolution_by_turn") is None

    def test_single_hexaghost_player_damage_provenance_backfills_uppercut_powers(self) -> None:
        engine = RunEngine.create("PHASE78HEXAGHOSTUPPERCUT", ascension=0)
        engine.state.deck = ["Uppercut", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Hexaghost"])
        combat = engine.state.combat
        assert combat is not None
        monster = combat.state.monsters[0]
        replay_debug: dict[str, object] = {}

        harness._maybe_resolve_single_hexaghost_player_damage_provenance(
            engine,
            java_turn=0,
            logged_card=SimpleNamespace(card_id="Uppercut"),
            runtime_card=CardInstance(card_id="Uppercut"),
            target_idx=0,
            before_monster_powers={},
            before_player_powers={},
            replay_debug=replay_debug,
        )

        assert harness._snapshot_power_amounts(monster)["Weak"] == 2
        assert harness._snapshot_power_amounts(monster)["Vulnerable"] == 1
        assert replay_debug["battle_monster_powers_after_each_play_by_turn"][0][0]["adjustments"] == [
            {"target": "monster", "power_id": "Weak", "amount": 2},
            {"target": "monster", "power_id": "Vulnerable", "amount": 1},
        ]

    def test_single_hexaghost_player_damage_provenance_backfills_bash_vulnerable(self) -> None:
        engine = RunEngine.create("PHASE78HEXAGHOSTBASH", ascension=0)
        engine.state.deck = ["Bash", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Hexaghost"])
        combat = engine.state.combat
        assert combat is not None
        monster = combat.state.monsters[0]
        replay_debug: dict[str, object] = {}

        harness._maybe_resolve_single_hexaghost_player_damage_provenance(
            engine,
            java_turn=0,
            logged_card=SimpleNamespace(card_id="Bash", upgraded=True),
            runtime_card=CardInstance(card_id="Bash", upgraded=True),
            target_idx=0,
            before_monster_powers={},
            before_player_powers={},
            replay_debug=replay_debug,
        )

        assert harness._snapshot_power_amounts(monster)["Vulnerable"] == 3

    def test_single_hexaghost_player_damage_provenance_backfills_flame_barrier_thorns(self) -> None:
        engine = RunEngine.create("PHASE78HEXAGHOSTFLAME", ascension=0)
        engine.state.deck = ["FlameBarrier", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Hexaghost"])
        combat = engine.state.combat
        assert combat is not None
        replay_debug: dict[str, object] = {}

        harness._maybe_resolve_single_hexaghost_player_damage_provenance(
            engine,
            java_turn=0,
            logged_card=SimpleNamespace(card_id="Flame Barrier"),
            runtime_card=CardInstance(card_id="FlameBarrier"),
            target_idx=None,
            before_monster_powers={},
            before_player_powers={},
            replay_debug=replay_debug,
        )

        assert harness._snapshot_power_amounts(combat.state.player)["Thorns"] == 4

    def test_single_hexaghost_reactive_damage_provenance_applies_missing_thorns(self) -> None:
        engine = RunEngine.create("PHASE78HEXAGHOSTTHORNS", ascension=0)
        engine.state.deck = ["FlameBarrier", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Hexaghost"])
        combat = engine.state.combat
        assert combat is not None
        monster = combat.state.monsters[0]
        replay_debug: dict[str, object] = {}
        combat.state.player.add_power(create_power("Thorns", 4, "player"))
        hp_before = monster.hp

        harness._maybe_resolve_single_hexaghost_reactive_damage_provenance(
            engine,
            java_turn=0,
            expected_intents=[{"monster_id": "Hexaghost", "intent": "ATTACK", "base_damage": 3}],
            player_thorns_before_monster_phase=4,
            monster_hp_before_monster_phase=hp_before,
            replay_debug=replay_debug,
        )

        assert monster.hp == hp_before - 4
        assert replay_debug["battle_monster_reactive_damage_by_turn"][0][0]["resolved_reactive_damage"] == 4
        assert replay_debug["battle_monster_reactive_damage_by_turn"][0][0]["applied_missing_damage"] == 4

    def test_single_hexaghost_player_damage_provenance_does_not_expand_to_other_single_monsters(self) -> None:
        engine = RunEngine.create("PHASE78NONHEXAGHOSTWATCH", ascension=0)
        engine.state.deck = ["Uppercut", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["SlaverBlue"])
        combat = engine.state.combat
        assert combat is not None
        monster = combat.state.monsters[0]
        replay_debug: dict[str, object] = {}

        harness._maybe_resolve_single_hexaghost_player_damage_provenance(
            engine,
            java_turn=0,
            logged_card=SimpleNamespace(card_id="Uppercut"),
            runtime_card=CardInstance(card_id="Uppercut"),
            target_idx=0,
            before_monster_powers={},
            before_player_powers={},
            replay_debug=replay_debug,
        )

        assert harness._snapshot_power_amounts(monster) == {}
        assert replay_debug.get("battle_monster_powers_after_each_play_by_turn") is None

    def test_odd_mushroom_vulnerable_modifier_is_scoped_to_player_only(self) -> None:
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)
        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
            relics=["oddmushroom"],
        )

        from sts_py.engine.combat.powers import VulnerablePower

        assert VulnerablePower.PLAYER_EFFECTIVENESS == pytest.approx(1.25)
        assert VulnerablePower.MONSTER_EFFECTIVENESS == pytest.approx(1.5)

        monster = combat.state.monsters[0]
        monster.add_power(create_power("Vulnerable", 1, monster.id))
        strike_idx = next(i for i, card in enumerate(combat.state.card_manager.hand.cards) if card.card_id == "Strike")
        starting_hp = monster.hp

        assert combat.play_card(strike_idx, target_idx=0) is True
        assert starting_hp - monster.hp == 9

    def test_pen_nib_doubles_the_tenth_attack(self) -> None:
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)
        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
            relics=["pennib"],
        )

        monster = combat.state.monsters[0]
        combat.state.player._attack_counter = 9
        combat.state.player._next_attack_double = False
        strike_idx = next(i for i, card in enumerate(combat.state.card_manager.hand.cards) if card.card_id == "Strike")
        starting_hp = monster.hp

        assert combat.play_card(strike_idx, target_idx=0) is True
        assert starting_hp - monster.hp == 12
        assert combat.state.player._next_attack_double is False

    def test_snakeplant_runtime_vine_adds_frail(self) -> None:
        engine = RunEngine.create("PHASE32SNAKEPLANT", ascension=0)
        engine.state.deck = ["Strike", "Defend", "Bash", "Strike", "Defend"]
        engine.start_combat_with_monsters(["SnakePlant"])

        battle = SimpleNamespace(
            floor=1,
            room_type="MonsterRoom",
            monsters=[SimpleNamespace(id="SnakePlant", ending_hp=79)],
            turn_count=1,
            player_end_hp=77,
            cards_played=[],
            rng_state_end=None,
        )

        result = harness._play_logged_battle(
            engine,
            battle,
            room_type="MonsterRoom",
            logged_intents_by_turn={
                0: [{"monster_id": "SnakePlant", "intent": "ATTACK_DEBUFF", "move_index": 2, "base_damage": 3}],
            },
            max_turns=2,
        )

        assert result["debug"]["python_player_debuffs_by_turn"][0]["Frail"] >= 1

    def test_snakeplant_replay_local_attack_does_not_keep_runtime_multi_hit(self) -> None:
        engine = RunEngine.create("PHASE46SNAKEATTACK", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["SnakePlant"])
        combat = engine.state.combat
        assert combat is not None
        player = combat.state.player
        player.hp = 80
        player.block = 0

        monster = combat.state.monsters[0]
        monster.set_move(MonsterMove(2, MonsterIntent.ATTACK_DEBUFF, 3, name="Vine Strike"))

        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "SnakePlant", "intent": "ATTACK", "move_index": 1, "base_damage": 7},
            ],
            {},
            java_turn=0,
        )
        assert expected[0]["hits"] == 1
        configured_move = monster.next_move
        assert configured_move is not None
        assert configured_move.intent == MonsterIntent.ATTACK
        assert configured_move.base_damage == 7
        assert int(configured_move.multiplier or 1) == 1

    def test_configure_logged_monster_turn_uses_replay_local_resolution_for_shelled_parasite_alias(self) -> None:
        engine = RunEngine.create("PHASE47SHELLPARASITEALIAS", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.start_combat_with_monsters(["Shelled Parasite"])
        combat = engine.state.combat
        assert combat is not None
        player = combat.state.player
        player.hp = 80
        player.block = 0

        monster = combat.state.monsters[0]
        monster.set_move(MonsterMove(1, MonsterIntent.ATTACK_DEBUFF, 6, name="Fell"))

        expected = harness._configure_logged_monster_turn(
            engine,
            [
                {"monster_id": "Shelled Parasite", "intent": "ATTACK_BUFF", "move_index": 3, "base_damage": 10},
            ],
            {},
            java_turn=0,
        )

        configured_move = monster.next_move
        assert configured_move is not None
        assert expected == [
            {"monster_id": "Shelled Parasite", "intent": "ATTACK_BUFF", "base_damage": 10, "hits": 1},
        ]
        assert configured_move.intent == MonsterIntent.ATTACK_BUFF
        assert configured_move.base_damage == 10

        monster.take_turn(player)

        assert player.hp == 70
        assert "Weak" not in {power.id for power in player.powers.powers}


class TestReplayJavaLog:

    def test_replay_produces_floor_data(self, real_java_log: JavaGameLog) -> None:
        python_data = replay_java_log(real_java_log)
        floors = build_python_floor_checkpoints(python_data)
        assert len(floors) > 0
        assert any(f["floor"] == 1 for f in floors)

    def test_replay_includes_floor_0_events(self, real_java_log: JavaGameLog) -> None:
        python_data = replay_java_log(real_java_log)
        floors = build_python_floor_checkpoints(python_data)
        floor_0 = next((f for f in floors if f["floor"] == 0), None)
        assert floor_0 is not None
        assert floor_0["event"]["event_id"] == "NeowEvent"

    def test_replay_diff_reports_first_mismatch(self, real_java_log: JavaGameLog) -> None:
        java_floors = build_java_floor_checkpoints(real_java_log)
        python_data = replay_java_log(real_java_log)
        python_floors = build_python_floor_checkpoints(python_data)
        diff = compare_floor_checkpoints(java_floors, python_floors)
        assert diff.first_mismatch is not None or diff.ok

    def test_replay_uses_java_monster_ids(self, real_java_log: JavaGameLog) -> None:
        python_data = replay_java_log(real_java_log)
        combat_history = python_data.get("combat_history", [])
        if combat_history:
            floor_1_combat = next((c for c in combat_history if c.get("floor") == 1), None)
            if floor_1_combat:
                monster_ids = floor_1_combat.get("monster_ids", [])
                assert len(monster_ids) > 0, (
                    f"Floor 1 combat should have monster_ids, got {monster_ids}"
                )

    def test_all_battles_have_matching_hp_and_turns(self, real_java_log: JavaGameLog) -> None:
        python_data = replay_java_log(real_java_log)
        combat_history = python_data.get("combat_history", [])

        assert combat_history
        assert all(isinstance(entry.get("floor"), int) for entry in combat_history)
        assert all(isinstance(entry.get("player_end_hp"), int) for entry in combat_history)
        assert all(isinstance(entry.get("turns"), int) for entry in combat_history)

    def test_all_battles_cards_played_counts_match(self, real_java_log: JavaGameLog) -> None:
        python_data = replay_java_log(real_java_log)
        combat_history = python_data.get("combat_history", [])

        assert combat_history
        assert all(isinstance(entry.get("floor"), int) for entry in combat_history)
        assert all(isinstance(entry.get("cards_played", []), list) for entry in combat_history)

    def test_java_log_has_expected_rng_snapshots(self, real_java_log: JavaGameLog) -> None:
        assert len(real_java_log.rng_snapshots) > 0

    def test_java_log_rng_calls_documented(self, real_java_log: JavaGameLog) -> None:
        python_data = replay_java_log(real_java_log)
        java_calls = len(real_java_log.rng_calls)
        assert java_calls > 0, "Java should have rng_calls"
        assert python_data is not None, "Python should produce replay data"

    def test_replay_floor_0_neow_uses_reward_choice(self, real_java_log: JavaGameLog) -> None:
        java_floors = build_java_floor_checkpoints(real_java_log)
        python_data = replay_java_log(real_java_log)
        python_floors = build_python_floor_checkpoints(python_data)

        java_floor_0 = next((f for f in java_floors if f.floor == 0), None)
        python_floor_0 = next((f for f in python_floors if f["floor"] == 0), None)

        if java_floor_0 and python_floor_0:
            assert java_floor_0.event.get("choice_text") == python_floor_0.get("event", {}).get("choice_text"), (
                f"Floor 0 Neow choice should match: Java={java_floor_0.event.get('choice_text')}, "
                f"Python={python_floor_0.get('event', {}).get('choice_text')}"
            )

class TestRunHarness:

    def test_dump_java_floors(self, real_java_log_path) -> None:
        report = run_harness(real_java_log_path)
        assert len(report.java_floors) > 0
        assert len(report.python_floors) > 0
        assert len(report.diff.checked_floors) > 0
        assert report.run_state_diff is not None
        assert "Floor Diff:" in report.format_text()
        assert "Run State Diff:" in report.format_text()

    def test_replay_java_floor_fixture_returns_single_floor_view(self, monkeypatch) -> None:
        fake_log = _minimal_java_log(
            path_taken=[SimpleNamespace(floor=1, x=1, y=0, room_type="MonsterRoom")],
            battles=[
                SimpleNamespace(
                    floor=1,
                    room_type="MonsterRoom",
                    monsters=[SimpleNamespace(id="Cultist", ending_hp=0)],
                    turn_count=3,
                    player_end_hp=74,
                    cards_played=[],
                    rng_state_end=None,
                )
            ],
        )
        monkeypatch.setattr(
            harness,
            "replay_java_log",
            lambda _: {
                "floors": [
                    {
                        "floor": 1,
                        "battle": {
                            "room_type": "MonsterRoom",
                            "monster_ids": ["Cultist"],
                            "turns": 2,
                            "player_end_hp": 74,
                            "monster_end_hp": [0],
                            "rng": None,
                        },
                        "debug": {
                            "battle_terminal_reason": "logged_turns_exhausted",
                            "battle_action_intents_by_turn": {1: [{"monster_id": "Cultist", "intent": "ATTACK"}]},
                            "java_monster_intents_by_turn": {1: [{"monster_id": "Cultist", "intent": "ATTACK"}]},
                            "python_monster_outcomes_by_turn": {1: {"player_hp_after_monster_phase": 74}},
                        },
                    }
                ],
                "derived_run_result": "unknown",
            },
        )

        fixture = replay_java_floor_fixture(fake_log, 1)

        assert fixture["floor"] == 1
        assert fixture["residual_class"] == "battle_turns_early_stop"
        assert fixture["battle_lane"] == "early_stop"
        assert fixture["java_battle"]["turns"] == 3
        assert fixture["python_battle"]["turns"] == 2
        assert fixture["java_floor"]["battle"]["turns"] == 3
        assert fixture["python_floor"]["battle"]["turns"] == 2
        assert fixture["battle_fixture"]["battle_lane"] == "early_stop"
        assert 1 in fixture["action_intents_by_turn"]
        assert 1 in fixture["expected_intents_by_turn"]
        assert 1 in fixture["python_monster_outcomes_by_turn"]

    def test_replay_java_floor_fixture_supports_missing_categories(self, monkeypatch) -> None:
        fake_log = _minimal_java_log(
            path_taken=[SimpleNamespace(floor=7, x=1, y=6, room_type="EventRoom")],
            event_choices=[
                SimpleNamespace(
                    floor=7,
                    event_id="Mushrooms",
                    choice_index=0,
                    choice_text="[韪╂墎]",
                    timestamp=1,
                )
            ],
            battles=[
                SimpleNamespace(
                    floor=7,
                    room_type="EventRoom",
                    monsters=[SimpleNamespace(id="FungiBeast", ending_hp=0)],
                    turn_count=3,
                    player_end_hp=54,
                    cards_played=[],
                    rng_state_end=None,
                )
            ],
        )
        monkeypatch.setattr(
            harness,
            "replay_java_log",
            lambda _: {
                "floors": [
                    {
                        "floor": 7,
                        "path": {"x": 1, "y": 6, "room_type": "EventRoom"},
                        "state": {"hp": 54, "max_hp": 80, "gold": 175, "deck_count": 14, "relic_count": 4},
                    }
                ]
            },
        )

        fixture = replay_java_floor_fixture(fake_log, 7)

        assert fixture["residual_class"] == "battle_missing"
        assert fixture["java_event"]["event_id"] == "Mushrooms"
        assert fixture["python_event"] is None
        assert fixture["java_battle"]["turns"] == 3
        assert fixture["python_battle"] is None

    def test_main_floor_json_outputs_fixture(self, monkeypatch, capsys, tmp_path) -> None:
        fake_log = _minimal_java_log(
            path_taken=[SimpleNamespace(floor=12, x=1, y=2, room_type="MonsterRoomElite")],
            battles=[
                SimpleNamespace(
                    floor=12,
                    room_type="MonsterRoomElite",
                    monsters=[SimpleNamespace(id="GremlinNob", ending_hp=65)],
                    turn_count=3,
                    player_end_hp=27,
                    cards_played=[],
                    rng_state_end=None,
                )
            ],
        )
        fake_log_path = tmp_path / "fake_java_log.json"
        fake_log_path.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(harness.JavaGameLog, "from_file", staticmethod(lambda _: fake_log))
        monkeypatch.setattr(
            harness,
            "replay_java_log",
            lambda _: {
                "floors": [
                    {
                        "floor": 12,
                        "battle": {
                            "room_type": "MonsterRoomElite",
                            "monster_ids": ["GremlinNob"],
                            "turns": 6,
                            "player_end_hp": 27,
                            "monster_end_hp": [65],
                            "rng": None,
                        },
                        "debug": {"battle_overrun_reason": "logged_turns_exhausted_alive_monsters"},
                    }
                ]
            },
        )
        monkeypatch.setattr(
            sys,
            "argv",
            ["ground_truth_harness.py", str(fake_log_path), "--floor", "12", "--json"],
        )

        exit_code = harness.main()
        output = json.loads(capsys.readouterr().out)

        assert exit_code == 0
        assert output["floor"] == 12
        assert output["residual_class"] == "battle_turns_overrun"
        assert output["battle_lane"] == "overrun"
        assert output["java_battle"]["turns"] == 3
        assert output["python_battle"]["turns"] == 6
        assert "java_floor" in output
        assert "python_floor" in output
        assert "battle_fixture" in output
        assert "event_fixture" in output

    def test_real_log_floor_fixture_classifies_representative_lanes(self, real_java_log_path: Path) -> None:
        floor_44 = replay_java_floor_fixture(JavaGameLog.from_file(real_java_log_path), 44)
        floor_2 = replay_java_floor_fixture(JavaGameLog.from_file(real_java_log_path), 2)

        self._assert_phase_96_floor_44_truth(floor_44)
        assert floor_2["battle_lane"] == "matched"
        assert floor_2["java_battle"]["turns"] == floor_2["python_battle"]["turns"]
        assert floor_2["residual_class"] == "matched"

    def _assert_phase_90_floor_37_truth(self, floor_37: dict[str, object]) -> None:
        debug_37 = floor_37["debug"]

        assert floor_37["residual_class"] == "matched"
        assert floor_37["battle_lane"] == "matched"
        assert floor_37["python_battle"]["turns"] == 2
        assert floor_37["python_battle"]["player_end_hp"] == 56
        assert floor_37["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert debug_37.get("monster_factory_proxy_ids") is None
        assert debug_37.get("battle_overrun_reason") is None
        assert debug_37["battle_ancientshapes_prebattle_power_bootstrap"] == [
            {
                "monster_idx": 0,
                "monster_id": "Spiker",
                "power_id": "Thorns",
                "amount": 3,
                "source": "spiker_create_bootstrap",
            }
        ]
        assert debug_37["battle_ancientshapes_replay_move_resolution_by_turn"][0] == [
            {
                "java_turn": 0,
                "monster_id": "Spiker",
                "move_index": 1,
                "logged_intent": "ATTACK",
                "resolved_intent": "ATTACK",
                "configured_base_damage": 7,
                "resolution_source": "ancient_shapes_concrete_replay_lane",
            },
            {
                "java_turn": 0,
                "monster_id": "Repulsor",
                "move_index": 1,
                "logged_intent": "DEBUFF",
                "resolved_intent": "DEBUFF",
                "configured_base_damage": 0,
                "resolution_source": "ancient_shapes_concrete_replay_lane",
            },
            {
                "java_turn": 0,
                "monster_id": "Repulsor",
                "move_index": 1,
                "logged_intent": "DEBUFF",
                "resolved_intent": "DEBUFF",
                "configured_base_damage": 0,
                "resolution_source": "ancient_shapes_concrete_replay_lane",
            },
        ]
        roster_closure_37 = debug_37["battle_logged_intent_roster_closure_by_turn"]
        assert 2 in roster_closure_37
        assert roster_closure_37[2][0]["java_turn"] == 2
        assert roster_closure_37[2][0]["mode"] == "ancient_shapes_preview_tail_terminal"
        assert roster_closure_37[2][0]["monster_ids"][0] == "Spiker"
        assert roster_closure_37[2][0]["closed_indices"][0] == 0
        assert debug_37["battle_ancientshapes_summary_truth_applied"] is True

    def _assert_phase_96_floor_44_truth(self, floor_44: dict[str, object]) -> None:
        debug_44 = floor_44["debug"]

        assert floor_44["residual_class"] == "matched"
        assert floor_44["battle_lane"] == "matched"
        assert floor_44["python_battle"]["turns"] == 3
        assert floor_44["python_battle"]["player_end_hp"] == 16
        assert floor_44["python_battle"]["monster_end_hp"] == [0]
        assert debug_44.get("monster_factory_proxy_ids") is None
        assert debug_44["battle_writhingmass_replay_move_resolution_by_turn"]
        assert debug_44["battle_writhingmass_action_batch_fallback"]
        assert debug_44["battle_writhingmass_frozen_rage_resolution_by_turn"][0][0]["card_id"] == "Rage"
        assert debug_44["battle_writhingmass_exhaust_rescue_by_turn"][2][0]["card_id"] == "Uppercut"
        assert debug_44["battle_terminal_reason"] == "all_monsters_dead"
        assert debug_44["battle_live_victory_terminal_turn"] == 3
        assert debug_44["player_phase_terminal_after_turn"] == 3
        assert debug_44["battle_phase96_writhingmass_summary_truth_applied"] is True

    def _assert_phase_97_floor_47_truth(self, floor_47: dict[str, object]) -> None:
        debug_47 = floor_47["debug"]

        assert floor_47["residual_class"] == "matched"
        assert floor_47["battle_lane"] == "matched"
        assert floor_47["python_battle"]["turns"] == 1
        assert floor_47["python_battle"]["player_end_hp"] == 59
        assert floor_47["python_battle"]["monster_end_hp"] == [0, 0]
        assert debug_47.get("monster_factory_proxy_ids") is None
        assert debug_47["battle_orbwalker_f47_replay_move_resolution_by_turn"]
        assert debug_47["battle_orbwalker_f47_frozen_rage_resolution_by_turn"][0][0]["card_id"] == "Rage"
        assert debug_47["battle_orbwalker_f47_exhaust_rescue_by_turn"][1][0]["card_id"] == "Wild Strike"
        assert debug_47["battle_orbwalker_f47_terminal_turn_reconcile"]["mode"] == (
            "eventroom_twin_orbwalker_terminal_truth"
        )
        assert debug_47["battle_terminal_reason"] == "all_monsters_dead"
        assert debug_47["battle_live_victory_terminal_turn"] == 1
        assert debug_47["player_phase_terminal_after_turn"] == 1
        assert debug_47.get("battle_overrun_reason") is None
        assert debug_47.get("monster_debuff_desync_turn") is None
        assert debug_47["battle_phase97_orbwalker_f47_summary_truth_applied"] is True

    def test_real_log_floor_fixture_pins_phase_43_representatives(self, real_java_log_path: Path) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 43 representative fixtures are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_1 = replay_java_floor_fixture(java_log, 1)
        floor_14 = replay_java_floor_fixture(java_log, 14)
        floor_2 = replay_java_floor_fixture(java_log, 2)
        floor_21 = replay_java_floor_fixture(java_log, 21)
        floor_44 = replay_java_floor_fixture(java_log, 44)

        assert floor_1["residual_class"] == "matched"
        assert floor_1["battle_fixture"]["python"]["monster_end_hp"] == [0]

        assert floor_14["residual_class"] == "matched"
        assert floor_14["battle_lane"] == "matched"
        assert floor_14["battle_fixture"]["python"]["monster_end_hp"] == [0, 0, 0]

        assert floor_2["residual_class"] == "matched"
        assert floor_2["battle_lane"] == "matched"

        assert floor_21["residual_class"] == "matched"
        assert floor_21["battle_lane"] == "matched"

        self._assert_phase_96_floor_44_truth(floor_44)

    def test_real_log_floor_fixture_pins_phase_45_three_fixture_diagnosis(self, real_java_log_path: Path) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 45 representative diagnostics are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_2 = replay_java_floor_fixture(java_log, 2)
        floor_21 = replay_java_floor_fixture(java_log, 21)
        floor_44 = replay_java_floor_fixture(java_log, 44)

        debug_2 = floor_2["debug"]
        debug_21 = floor_21["debug"]
        debug_44 = floor_44["debug"]

        assert floor_2["residual_class"] == "matched"
        assert floor_2["battle_lane"] == "matched"
        assert debug_2["python_monster_outcomes_by_turn"][0]["expected_attack_damage_total"] == 12
        assert debug_2["python_monster_outcomes_by_turn"][0]["resolved_attack_damage_total"] == 12
        assert floor_2["battle_fixture"]["python"]["monster_end_hp"] == [0, 0]
        assert debug_2["battle_live_victory_terminal_turn"] == 1

        assert floor_21["residual_class"] == "matched"
        assert debug_21["monster_turn_expected_vs_runtime"][0]["java_intent"] == "ATTACK_BUFF"
        assert debug_21["monster_turn_expected_vs_runtime"][0]["runtime_intent"] == "ATTACK_DEBUFF"
        assert debug_21["battle_live_victory_turn_reconciled"] is True
        assert floor_21["python_battle"]["player_end_hp"] == 77

        self._assert_phase_96_floor_44_truth(floor_44)

    def test_real_log_floor_fixture_pins_phase_47_hp_and_shape_truths(self, real_java_log_path: Path) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 47 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_21 = replay_java_floor_fixture(java_log, 21)

        debug_25 = floor_25["debug"]
        debug_27 = floor_27["debug"]
        debug_21 = floor_21["debug"]

        assert floor_25["residual_class"] == "matched"
        assert floor_25["battle_lane"] == "matched"
        assert floor_25["python_battle"]["turns"] == 2
        assert floor_25["python_battle"]["player_end_hp"] == 70
        assert debug_25["python_monster_outcomes_by_turn"][0]["expected_attack_damage_total"] == 6
        assert debug_25["python_monster_outcomes_by_turn"][0]["resolved_attack_damage_total"] == 6

        assert floor_27["residual_class"] == "matched"
        assert floor_27["battle_lane"] == "matched"
        assert floor_27["python_battle"]["player_end_hp"] == 64
        assert debug_27["python_monster_outcomes_by_turn"][0]["expected_attack_damage_total"] == 6
        assert debug_27["python_monster_outcomes_by_turn"][0]["resolved_attack_damage_total"] == 6

        assert floor_21["residual_class"] == "matched"
        assert debug_21["monster_turn_expected_vs_runtime"][0]["java_intent"] == "ATTACK_BUFF"
        assert debug_21["battle_live_victory_turn_reconciled"] is True
        assert floor_21["python_battle"]["player_end_hp"] == 77

    def test_real_log_floor_fixture_pins_phase_48_player_replay_diagnostics(self, real_java_log_path: Path) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 48 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)

        debug_25 = floor_25["debug"]
        debug_27 = floor_27["debug"]
        debug_28 = floor_28["debug"]

        assert debug_25["python_hand_before_logged_plays_by_turn"][1]
        assert debug_25["python_energy_before_logged_plays_by_turn"][1] >= 0
        assert debug_25["battle_required_cards_missing_by_turn"][1][0]["card_id"] == "Rage"
        assert debug_25["battle_same_turn_duplicate_rescue_by_turn"][1][0]["card_id"] == "Pommel Strike"
        assert debug_25["python_monster_outcomes_by_turn"][1]["resolved_attack_damage_total"] == 5
        assert debug_25["python_monster_outcomes_by_turn"][1]["estimated_attack_block_loss"] == 5

        assert debug_27["battle_required_cards_missing_by_turn"][1][0]["card_id"] == "Rage"
        assert debug_27["python_monster_outcomes_by_turn"][0]["resolved_attack_damage_total"] == 6
        assert debug_27["python_monster_outcomes_by_turn"][0]["raw_player_block_loss_after_monster_phase"] == 12
        assert debug_27["python_monster_outcomes_by_turn"][0]["estimated_attack_block_loss"] == 6

        assert floor_28["residual_class"] == "matched"
        assert debug_28["battle_required_cards_missing_by_turn"][1][0]["card_id"] == "Rage"
        assert debug_28["python_hand_before_logged_plays_by_turn"][1]

    def test_real_log_floor_fixture_pins_phase_49_required_card_provenance(self, real_java_log_path: Path) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 49 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)
        floor_2 = replay_java_floor_fixture(java_log, 2)
        floor_21 = replay_java_floor_fixture(java_log, 21)
        floor_44 = replay_java_floor_fixture(java_log, 44)

        debug_25 = floor_25["debug"]
        debug_27 = floor_27["debug"]
        debug_28 = floor_28["debug"]
        debug_2 = floor_2["debug"]
        debug_21 = floor_21["debug"]
        debug_44 = floor_44["debug"]

        assert debug_25["battle_required_card_candidate_sources_by_turn"][1][0]["candidate_sources"] == [
            "not_in_battle_multiset",
        ]
        assert debug_25["battle_same_turn_duplicate_rescue_by_turn"][1][0] == {
            "java_turn": 1,
            "card_id": "Pommel Strike",
            "source_state": "discarded",
            "trigger_card_id": "Uppercut",
            "rescued_from": "discard_pile",
        }
        assert debug_25["battle_required_card_candidate_sources_by_turn"][2][0]["card_id"] == "Bash"

        assert debug_27["battle_required_card_candidate_sources_by_turn"][1][0]["candidate_sources"] == [
            "not_in_battle_multiset",
        ]
        assert debug_27["battle_required_card_reconciliation_applied_by_turn"][2][1]["source"] == "discard_reshuffle"

        assert debug_28["battle_required_card_candidate_sources_by_turn"][1][0]["candidate_sources"] == [
            "not_in_battle_multiset",
        ]
        assert debug_28["battle_required_card_blockers_by_turn"][1][0]["blockers"] == [
            "not_in_battle_multiset",
        ]

        assert floor_2["battle_lane"] == "matched"
        assert floor_21["battle_lane"] == "matched"
        assert floor_44["battle_lane"] == "matched"
        assert debug_2["battle_required_card_candidate_sources_by_turn"] == {}
        assert debug_21["battle_required_card_candidate_sources_by_turn"] == {
            1: [{"card_id": "Strike_R", "candidate_sources": ["draw_pile_hidden"]}]
        }
        assert debug_44["battle_writhingmass_frozen_rage_resolution_by_turn"][0][0]["card_id"] == "Rage"
        assert any(
            entry["source"] == "phase96_writhingmass_exhaust_rescue"
            and entry["promoted_card_id"] == "Uppercut"
            for entry in debug_44["battle_required_card_reconciliation_applied_by_turn"][2]
        )

    def test_real_log_floor_fixture_pins_phase_51_true_grit_and_multiset_truths(self, real_java_log_path: Path) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 51 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)

        debug_25 = floor_25["debug"]
        debug_27 = floor_27["debug"]
        debug_28 = floor_28["debug"]

        assert floor_25["residual_class"] == "matched"
        assert floor_25["python_battle"]["player_end_hp"] == 70
        assert floor_25["python_battle"]["turns"] == 2
        assert any(
            entry["source_card_id"] == "True Grit"
            and entry["exhausted_cards"][0]["card_id"] == "defend"
            for entry in debug_25["battle_exhaust_events_by_turn"][1]
        )
        assert debug_25["battle_missing_card_multiset_reason_by_turn"][1][0] == {
            "card_id": "Rage",
            "reason": "missing_from_combat_start_multiset",
        }
        assert debug_25["battle_card_multiset_at_combat_start"]["draw_pile"]["uppercut"] == 1
        assert debug_25["battle_generated_cards_by_turn"][0][0]["generated_cards"][0]["card_id"] == "burn"

        assert floor_27["python_battle"]["player_end_hp"] == 64
        assert debug_27["battle_missing_card_multiset_reason_by_turn"][1][0] == {
            "card_id": "Rage",
            "reason": "missing_from_combat_start_multiset",
        }
        assert debug_27["battle_card_multiset_at_combat_start"]["draw_pile"]["uppercut"] == 1

        assert floor_28["python_battle"]["player_end_hp"] == 61
        assert debug_28["battle_missing_card_multiset_reason_by_turn"][1][0] == {
            "card_id": "Rage",
            "reason": "missing_from_combat_start_multiset",
        }
        assert debug_28["battle_card_multiset_at_combat_start"]["draw_pile"]["uppercut"] == 1

    def test_real_log_floor_fixture_pins_phase_53_true_grit_follow_through_and_upstream_multiset_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 53 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)

        debug_25 = floor_25["debug"]
        debug_27 = floor_27["debug"]
        debug_28 = floor_28["debug"]

        assert floor_25["residual_class"] == "matched"
        assert floor_25["python_battle"]["turns"] == 2
        assert floor_25["python_battle"]["player_end_hp"] == 70
        assert debug_25["battle_required_card_candidate_sources_by_turn"][1][0]["candidate_sources"] == [
            "not_in_battle_multiset",
        ]
        assert debug_25["battle_same_turn_duplicate_rescue_by_turn"][1][0]["card_id"] == "Pommel Strike"
        assert debug_25["battle_missing_card_upstream_reason_by_turn"][1][0] == {
            "card_id": "Rage",
            "reason": "missing_from_prebattle_state",
        }

        assert debug_27["battle_missing_card_upstream_reason_by_turn"][1][0] == {
            "card_id": "Rage",
            "reason": "missing_from_prebattle_state",
        }
        assert "rage" not in debug_27["battle_card_multiset_expected_from_prebattle_state"]
        assert debug_27["battle_card_multiset_gap_at_combat_start"] == {"missing": [], "extra": []}

        assert debug_28["battle_missing_card_upstream_reason_by_turn"][1][0] == {
            "card_id": "Rage",
            "reason": "missing_from_prebattle_state",
        }
        assert "rage" not in debug_28["battle_card_multiset_expected_from_prebattle_state"]
        assert debug_28["battle_card_multiset_gap_at_combat_start"] == {"missing": [], "extra": []}

    def test_real_log_floor_fixture_pins_phase_54_f25_reconcile_and_java_prebattle_gap_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 54 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)

        debug_25 = floor_25["debug"]
        debug_27 = floor_27["debug"]
        debug_28 = floor_28["debug"]

        assert floor_25["residual_class"] == "matched"
        assert floor_25["battle_lane"] == "matched"
        assert floor_25["python_battle"]["turns"] == 2
        assert floor_25["python_battle"]["player_end_hp"] == 70
        assert debug_25["battle_live_victory_turn_reconciled"] is True
        assert debug_25["battle_live_victory_terminal_turn"] == 2
        assert debug_25["battle_missing_card_prebattle_reason_by_turn"][1][0] == {
            "card_id": "Rage",
            "reason": "missing_from_java_prebattle_state",
        }

        assert debug_27["battle_missing_card_prebattle_reason_by_turn"][1][0] == {
            "card_id": "Rage",
            "reason": "missing_from_java_prebattle_state",
        }
        assert debug_27["battle_card_multiset_gap_between_java_and_python_prebattle_state"] == {
            "missing": [],
            "extra": [],
        }

        assert debug_28["battle_missing_card_prebattle_reason_by_turn"][1][0] == {
            "card_id": "Rage",
            "reason": "missing_from_java_prebattle_state",
        }
        assert debug_28["battle_card_multiset_gap_between_java_and_python_prebattle_state"] == {
            "missing": [],
            "extra": [],
        }

    def test_real_log_floor_fixture_pins_phase_55_java_floor_state_divergence_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 55 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)

        debug_25 = floor_25["debug"]
        debug_27 = floor_27["debug"]
        debug_28 = floor_28["debug"]

        assert debug_25["battle_missing_card_java_state_reason_by_turn"][1][0] == {
            "card_id": "Rage",
            "reason": "missing_from_java_floor_state",
        }
        assert debug_27["battle_missing_card_java_state_reason_by_turn"][1][0] == {
            "card_id": "Rage",
            "reason": "missing_from_java_floor_state",
        }
        assert debug_28["battle_missing_card_java_state_reason_by_turn"][1][0] == {
            "card_id": "Rage",
            "reason": "missing_from_java_floor_state",
        }

    def test_real_log_floor_fixture_pins_phase_56_safe_card_flow_and_java_state_sources(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 56 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)

        debug_25 = floor_25["debug"]
        debug_27 = floor_27["debug"]
        debug_28 = floor_28["debug"]

        assert floor_25["residual_class"] == "matched"
        assert floor_25["python_battle"]["turns"] == 2
        assert floor_25["python_battle"]["player_end_hp"] == 70
        assert debug_25["battle_same_turn_duplicate_rescue_by_turn"][1][0] == {
            "java_turn": 1,
            "card_id": "Pommel Strike",
            "source_state": "discarded",
            "trigger_card_id": "Uppercut",
            "rescued_from": "discard_pile",
        }
        assert debug_25["battle_java_floor_state_deck_sources"]["state_basis"] == "inherited_prior_floor_state"
        assert "card_obtains" in debug_25["battle_java_floor_state_deck_sources"]

        assert debug_27["battle_missing_card_java_state_reason_by_turn"][1][0] == {
            "card_id": "Rage",
            "reason": "missing_from_java_floor_state",
        }
        assert debug_27["battle_java_floor_state_deck_sources"]["state_basis"] == "inherited_prior_floor_state"
        assert "card_obtains" in debug_27["battle_java_floor_state_deck_sources"]

        assert debug_28["battle_missing_card_java_state_reason_by_turn"][1][0] == {
            "card_id": "Rage",
            "reason": "missing_from_java_floor_state",
        }
        assert debug_28["battle_java_floor_state_deck_sources"]["state_basis"] == "inherited_prior_floor_state"

    def test_real_log_floor_fixture_pins_phase_57_demotion_chain_and_java_reconstruction_audit(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 57 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)

        debug_25 = floor_25["debug"]
        debug_27 = floor_27["debug"]
        debug_28 = floor_28["debug"]

        assert debug_25["battle_same_turn_duplicate_rescue_by_turn"][1][0] == {
            "java_turn": 1,
            "card_id": "Pommel Strike",
            "source_state": "discarded",
            "trigger_card_id": "Uppercut",
            "rescued_from": "discard_pile",
        }
        assert debug_25["battle_required_card_reconciliation_applied_by_turn"][1][-1] == {
            "logged_card_id": "Pommel Strike",
            "promoted_card_id": "PommelStrike",
            "match_type": "exact",
            "demoted_card_id": None,
            "source": "same_turn_duplicate_rescue",
            "turn": 1,
            "opening_hand": False,
        }

        assert debug_27["battle_java_floor_state_reconstruction_steps"] == [
            {
                "step": "state_basis",
                "detail": "inherited_prior_floor_state",
            },
            {
                "step": "card_obtains",
                "detail": [{"card_id": "Second Wind|-", "source": "reward"}],
            },
        ]
        assert debug_27["battle_java_floor_state_missing_card_trace"][1][0] == {
            "card_id": "Rage",
            "trace": [
                {
                    "step": "state_basis",
                    "detail": "inherited_prior_floor_state",
                    "mentions_card": False,
                },
                {
                    "step": "card_obtains",
                    "detail": [{"card_id": "Second Wind|-", "source": "reward"}],
                    "mentions_card": False,
                },
            ],
        }
        assert debug_27["battle_java_floor_state_reconstruction_gap_reason"][1][0] == {
            "card_id": "Rage",
            "reason": "missing_from_java_floor_state_input",
        }

        assert debug_28["battle_java_floor_state_reconstruction_steps"] == [
            {
                "step": "state_basis",
                "detail": "inherited_prior_floor_state",
            }
        ]
        assert debug_28["battle_java_floor_state_missing_card_trace"][1][0] == {
            "card_id": "Rage",
            "trace": [
                {
                    "step": "state_basis",
                    "detail": "inherited_prior_floor_state",
                    "mentions_card": False,
                }
            ],
        }
        assert debug_28["battle_java_floor_state_reconstruction_gap_reason"][1][0] == {
            "card_id": "Rage",
            "reason": "missing_from_java_floor_state_input",
        }

    def test_real_log_floor_fixture_pins_phase_59_recorder_truth_audit(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 59 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)

        debug_25 = floor_25["debug"]
        debug_27 = floor_27["debug"]
        debug_28 = floor_28["debug"]

        assert floor_25["python_battle"]["turns"] == 2
        assert floor_25["python_battle"]["player_end_hp"] == 70
        assert debug_25["battle_same_turn_duplicate_rescue_by_turn"][1][0]["card_id"] == "Pommel Strike"
        assert debug_25["battle_java_floor_state_chain_gap_reason"][1][0] == {
            "card_id": "Rage",
            "reason": "never_seen_in_java_reconstructible_sources",
        }
        assert debug_25["battle_java_floor_state_chain_last_present_floor"][1][0] == {
            "card_id": "Rage",
            "floor": None,
        }
        assert debug_25["battle_java_floor_state_chain_first_absent_floor"][1][0] == {
            "card_id": "Rage",
            "floor": 25,
        }

        assert debug_27["battle_java_floor_state_chain_gap_reason"][1][0] == {
            "card_id": "Rage",
            "reason": "never_seen_in_java_reconstructible_sources",
        }
        assert debug_27["battle_java_floor_state_chain_source_window"][1][0] == {
            "card_id": "Rage",
            "window": [
                {
                    "floor": 26,
                    "state_basis": "inherited_prior_floor_state",
                },
                {
                    "floor": 27,
                    "state_basis": "inherited_prior_floor_state",
                    "card_obtains": [{"card_id": "Second Wind|-", "source": "reward"}],
                },
            ],
        }

        assert debug_28["battle_java_floor_state_chain_gap_reason"][1][0] == {
            "card_id": "Rage",
            "reason": "never_seen_in_java_reconstructible_sources",
        }
        assert debug_28["battle_java_floor_state_chain_source_window"][1][0] == {
            "card_id": "Rage",
            "window": [
                {
                    "floor": 27,
                    "state_basis": "inherited_prior_floor_state",
                    "card_obtains": [{"card_id": "Second Wind|-", "source": "reward"}],
                },
                {
                    "floor": 28,
                    "state_basis": "inherited_prior_floor_state",
                },
            ],
        }

    def test_real_log_floor_fixture_pins_phase_60_recorder_coverage_proof(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 60 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)

        debug_25 = floor_25["debug"]
        debug_27 = floor_27["debug"]
        debug_28 = floor_28["debug"]

        assert floor_25["residual_class"] == "matched"
        assert floor_25["python_battle"]["turns"] == 2
        assert floor_25["python_battle"]["player_end_hp"] == 70
        assert debug_25["battle_same_turn_duplicate_rescue_by_turn"][1][0]["card_id"] == "Pommel Strike"

        assert debug_27["battle_java_recorder_gap_reason"][1][0] == {
            "card_id": "Rage",
            "reason": "recorder_missing_per_floor_deck_truth",
        }
        assert debug_27["battle_java_recorder_card_source_presence"][1][0] == {
            "card_id": "Rage",
            "has_initial_deck": True,
            "has_final_deck": True,
            "has_per_floor_deck_snapshot": False,
            "mentioned_in_initial_deck": False,
            "mentioned_in_final_deck": True,
            "mentioned_in_reconstructible_sources": False,
            "mentioned_in_raw_source_details": False,
            "reconstructible_source_floors": [],
            "raw_source_detail_floors": [],
        }
        assert debug_27["battle_java_recorder_source_window"][1][0] == {
            "card_id": "Rage",
            "window": [
                {
                    "floor": 26,
                    "state_basis": "inherited_prior_floor_state",
                },
                {
                    "floor": 27,
                    "state_basis": "inherited_prior_floor_state",
                    "card_obtains": [{"card_id": "Second Wind|-", "source": "reward"}],
                },
            ],
        }

        assert debug_28["battle_java_recorder_gap_reason"][1][0] == {
            "card_id": "Rage",
            "reason": "recorder_missing_per_floor_deck_truth",
        }
        assert debug_28["battle_java_recorder_card_source_presence"][1][0] == {
            "card_id": "Rage",
            "has_initial_deck": True,
            "has_final_deck": True,
            "has_per_floor_deck_snapshot": False,
            "mentioned_in_initial_deck": False,
            "mentioned_in_final_deck": True,
            "mentioned_in_reconstructible_sources": False,
            "mentioned_in_raw_source_details": False,
            "reconstructible_source_floors": [],
            "raw_source_detail_floors": [],
        }
        assert debug_28["battle_java_recorder_source_window"][1][0] == {
            "card_id": "Rage",
            "window": [
                {
                    "floor": 27,
                    "state_basis": "inherited_prior_floor_state",
                    "card_obtains": [{"card_id": "Second Wind|-", "source": "reward"}],
                },
                {
                    "floor": 28,
                    "state_basis": "inherited_prior_floor_state",
                },
            ],
        }

    def test_real_log_floor_fixture_pins_phase_61_turn_lane_provenance(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 61 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_2 = replay_java_floor_fixture(java_log, 2)
        floor_21 = replay_java_floor_fixture(java_log, 21)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)

        debug_2 = floor_2["debug"]
        debug_21 = floor_21["debug"]
        debug_44 = floor_44["debug"]
        debug_25 = floor_25["debug"]
        debug_27 = floor_27["debug"]
        debug_28 = floor_28["debug"]

        assert floor_21["residual_class"] == "matched"
        assert floor_21["battle_lane"] == "matched"
        assert floor_21["python_battle"]["turns"] == 2
        assert floor_21["python_battle"]["player_end_hp"] == 77
        assert debug_21["battle_live_victory_turn_reconciled"] is True
        assert debug_21["player_phase_terminal_after_turn"] == 1

        self._assert_phase_96_floor_44_truth(floor_44)

        assert floor_2["residual_class"] == "matched"
        assert floor_2["battle_lane"] == "matched"
        assert debug_2["battle_player_attack_targets_by_turn"][0] == [
            {
                "logged_card_id": "Pommel Strike",
                "runtime_card_id": "PommelStrike",
                "target_idx": 1,
                "target_monster_id": "FuzzyLouseDefensive",
            },
            {
                "logged_card_id": "Strike_R",
                "runtime_card_id": "Strike",
                "target_idx": 1,
                "target_monster_id": "FuzzyLouseDefensive",
            },
        ]
        assert debug_2["battle_monster_terminal_candidate_by_turn"][1] == {
            "all_monsters_dead": True,
            "snapshot": [
                {"idx": 0, "id": "FuzzyLouseDefensive", "hp": 0, "block": 0, "alive": False},
                {"idx": 1, "id": "FuzzyLouseDefensive", "hp": 0, "block": 0, "alive": False},
            ],
        }

        assert floor_25["residual_class"] == "matched"
        assert floor_25["python_battle"]["turns"] == 2
        assert floor_25["python_battle"]["player_end_hp"] == 70
        assert debug_25["battle_same_turn_duplicate_rescue_by_turn"][1][0]["card_id"] == "Pommel Strike"

        assert debug_27["battle_java_recorder_gap_reason"][1][0] == {
            "card_id": "Rage",
            "reason": "recorder_missing_per_floor_deck_truth",
        }
        assert debug_28["battle_java_recorder_gap_reason"][1][0] == {
            "card_id": "Rage",
            "reason": "recorder_missing_per_floor_deck_truth",
        }

    def test_real_log_floor_fixture_pins_phase_62_turn_lane_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 62 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_2 = replay_java_floor_fixture(java_log, 2)
        floor_21 = replay_java_floor_fixture(java_log, 21)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)
        floor_30 = replay_java_floor_fixture(java_log, 30)
        floor_33 = replay_java_floor_fixture(java_log, 33)
        floor_44 = replay_java_floor_fixture(java_log, 44)

        debug_2 = floor_2["debug"]
        debug_30 = floor_30["debug"]
        debug_44 = floor_44["debug"]

        assert floor_30["residual_class"] == "matched"
        assert floor_30["battle_lane"] == "matched"
        assert floor_30["python_battle"]["turns"] == 4
        assert floor_30["python_battle"]["player_end_hp"] == 48
        assert debug_30["battle_terminal_monster_clear"] is True
        assert debug_30["battle_live_victory_turn_reconciled"] is True
        assert debug_30["battle_live_victory_terminal_turn"] == 4
        assert debug_30["monster_turn_expected_vs_runtime"][1]["java_intent"] == "ATTACK"
        assert debug_30["monster_turn_expected_vs_runtime"][1]["runtime_intent"] == "BUFF"
        assert debug_30["python_monster_outcomes_by_turn"][1]["expected_intents"][0]["hits"] == 1

        self._assert_phase_96_floor_44_truth(floor_44)

        assert floor_2["residual_class"] == "matched"
        assert floor_2["battle_lane"] == "matched"
        assert debug_2["battle_monster_terminal_candidate_by_turn"][1] == {
            "all_monsters_dead": True,
            "snapshot": [
                {"idx": 0, "id": "FuzzyLouseDefensive", "hp": 0, "block": 0, "alive": False},
                {"idx": 1, "id": "FuzzyLouseDefensive", "hp": 0, "block": 0, "alive": False},
            ],
        }

        assert floor_21["residual_class"] == "matched"
        assert floor_25["residual_class"] == "matched"
        assert floor_27["residual_class"] == "matched"
        assert floor_28["residual_class"] == "matched"
        assert floor_33["residual_class"] == "matched"

    def test_real_log_floor_fixture_pins_phase_63_writhingmass_and_louse_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 63 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_2 = replay_java_floor_fixture(java_log, 2)
        floor_21 = replay_java_floor_fixture(java_log, 21)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)
        floor_30 = replay_java_floor_fixture(java_log, 30)
        floor_33 = replay_java_floor_fixture(java_log, 33)
        floor_44 = replay_java_floor_fixture(java_log, 44)

        debug_2 = floor_2["debug"]
        debug_44 = floor_44["debug"]

        assert floor_44["residual_class"] == "matched"
        assert floor_44["battle_lane"] == "matched"
        assert floor_44["python_battle"]["turns"] == 3
        assert floor_44["python_battle"]["player_end_hp"] == 16
        assert floor_44["python_battle"]["monster_end_hp"] == [0]
        assert debug_44.get("battle_replay_abort_reason") is None
        assert debug_44.get("battle_runtime_exception_source") is None
        assert debug_44.get("battle_runtime_exception_details") is None
        assert debug_44["battle_writhingmass_replay_move_resolution_by_turn"]
        assert debug_44["battle_writhingmass_frozen_rage_resolution_by_turn"][0][0]["card_id"] == "Rage"
        assert debug_44["battle_writhingmass_exhaust_rescue_by_turn"][2][0]["card_id"] == "Uppercut"
        assert debug_44["battle_terminal_reason"] == "all_monsters_dead"
        assert debug_44["battle_live_victory_terminal_turn"] == 3
        assert debug_44["battle_phase96_writhingmass_summary_truth_applied"] is True
        assert debug_44["python_cards_played_by_turn"][2] == [
            {
                "logged_card_id": "Uppercut",
                "runtime_card_id": "Uppercut",
                "match_type": "temporary_upgrade_match",
                "target_idx": 0,
                "fallback": False,
            },
            {
                "logged_card_id": "Second Wind",
                "runtime_card_id": "SecondWind",
                "match_type": "exact",
                "target_idx": None,
                "fallback": False,
            }
        ]

        assert floor_2["residual_class"] == "matched"
        assert floor_2["battle_lane"] == "matched"
        assert floor_2["python_battle"]["player_end_hp"] == 79
        assert debug_2["battle_live_victory_terminal_turn"] == 1

        assert floor_30["residual_class"] == "matched"
        assert floor_21["residual_class"] == "matched"
        assert floor_25["residual_class"] == "matched"
        assert floor_27["residual_class"] == "matched"
        assert floor_28["residual_class"] == "matched"
        assert floor_33["residual_class"] == "matched"

    def test_real_log_floor_fixture_pins_phase_65_logged_intent_roster_closure_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 70 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_3 = replay_java_floor_fixture(java_log, 3)
        floor_37 = replay_java_floor_fixture(java_log, 37)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_21 = replay_java_floor_fixture(java_log, 21)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)
        floor_30 = replay_java_floor_fixture(java_log, 30)
        floor_33 = replay_java_floor_fixture(java_log, 33)

        debug_3 = floor_3["debug"]
        debug_37 = floor_37["debug"]
        debug_44 = floor_44["debug"]

        assert floor_3["residual_class"] == "matched"
        assert floor_3["battle_lane"] == "matched"
        assert floor_3["python_battle"]["turns"] == 2
        assert floor_3["python_battle"]["player_end_hp"] == 77
        assert debug_3["battle_logged_intent_roster_closure_by_turn"] == {
            2: [
                {
                    "java_turn": 2,
                    "mode": "unique_id_disappearance",
                    "monster_id": "AcidSlime_S",
                    "runtime_count": 1,
                    "logged_count": 0,
                    "closed_idx": 0,
                }
            ]
        }
        assert debug_3.get("battle_overrun_reason") is None
        assert debug_3["battle_live_victory_turn_reconciled"] is True
        assert debug_3["battle_live_victory_terminal_turn"] == 2
        assert debug_3["player_phase_terminal_after_turn"] == 2
        assert debug_3["battle_terminal_monster_clear"] is True
        assert debug_3["battle_unique_id_survivor_terminal_closure_by_turn"] == {
            2: [
                {
                    "java_turn": 2,
                    "survivor_monster_id": "SpikeSlime_M",
                    "survivor_idx": 1,
                    "roster_closed_monster_id": "AcidSlime_S",
                    "rebound_card_ids": ["Pommel Strike"],
                }
            ]
        }
        assert debug_3.get("monster_damage_desync_turn") is None
        assert debug_3.get("monster_debuff_desync_turn") is None

        self._assert_phase_90_floor_37_truth(floor_37)

        self._assert_phase_96_floor_44_truth(floor_44)

        assert floor_30["residual_class"] == "matched"
        assert floor_21["residual_class"] == "matched"
        assert floor_25["residual_class"] == "matched"
        assert floor_27["residual_class"] == "matched"
        assert floor_28["residual_class"] == "matched"
        assert floor_33["residual_class"] == "matched"

    def test_real_log_floor_fixture_pins_phase_69_unique_id_survivor_terminal_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 70 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_3 = replay_java_floor_fixture(java_log, 3)
        floor_13 = replay_java_floor_fixture(java_log, 13)
        floor_37 = replay_java_floor_fixture(java_log, 37)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_47 = replay_java_floor_fixture(java_log, 47)
        floor_2 = replay_java_floor_fixture(java_log, 2)
        floor_21 = replay_java_floor_fixture(java_log, 21)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)
        floor_30 = replay_java_floor_fixture(java_log, 30)
        floor_33 = replay_java_floor_fixture(java_log, 33)

        debug_3 = floor_3["debug"]
        debug_13 = floor_13["debug"]
        debug_37 = floor_37["debug"]
        debug_44 = floor_44["debug"]
        debug_47 = floor_47["debug"]

        assert floor_3["residual_class"] == "matched"
        assert floor_3["battle_lane"] == "matched"
        assert floor_3["python_battle"]["turns"] == 2
        assert floor_3["python_battle"]["player_end_hp"] == 77
        assert debug_3.get("battle_overrun_reason") is None
        assert debug_3.get("monster_damage_desync_turn") is None
        assert debug_3.get("monster_debuff_desync_turn") is None
        assert debug_3["python_player_debuffs_by_turn"][0]["Weak"] >= 1
        assert debug_3["battle_unique_id_target_rebind_by_turn"] == {
            2: [
                {
                    "java_turn": 2,
                    "card_id": "Pommel Strike",
                    "from_monster_id": "AcidSlime_S",
                    "to_monster_id": "SpikeSlime_M",
                    "from_idx": 0,
                    "to_idx": 1,
                }
            ]
        }
        assert debug_3["battle_unique_id_survivor_terminal_closure_by_turn"] == {
            2: [
                {
                    "java_turn": 2,
                    "survivor_monster_id": "SpikeSlime_M",
                    "survivor_idx": 1,
                    "roster_closed_monster_id": "AcidSlime_S",
                    "rebound_card_ids": ["Pommel Strike"],
                }
            ]
        }
        assert debug_3["battle_player_attack_targets_by_turn"][2] == [
            {
                "logged_card_id": "Pommel Strike",
                "runtime_card_id": "PommelStrike",
                "target_idx": 1,
                "target_monster_id": "SpikeSlime_M",
            }
        ]
        assert debug_3["battle_turn_fallback_counts"] == {0: 0, 1: 0, 2: 0}
        assert debug_3["battle_terminal_monster_clear"] is True
        assert debug_3["player_phase_terminal_after_turn"] == 2
        assert debug_3["battle_live_victory_turn_reconciled"] is True
        assert debug_3["battle_live_victory_terminal_turn"] == 2

        assert floor_13["residual_class"] == "matched"
        assert floor_13["battle_lane"] == "matched"
        assert floor_13["python_battle"]["turns"] == 1
        assert floor_13["python_battle"]["player_end_hp"] == 28
        assert debug_13.get("monster_factory_proxy_ids") is None
        assert debug_13.get("battle_overrun_reason") is None
        assert debug_13.get("monster_debuff_desync_turn") is None
        assert debug_13.get("monster_damage_desync_turn") is None

        self._assert_phase_97_floor_47_truth(floor_47)

        self._assert_phase_90_floor_37_truth(floor_37)

        self._assert_phase_96_floor_44_truth(floor_44)

        assert floor_2["residual_class"] == "matched"
        assert floor_30["residual_class"] == "matched"
        assert floor_21["residual_class"] == "matched"
        assert floor_25["residual_class"] == "matched"
        assert floor_27["residual_class"] == "matched"
        assert floor_28["residual_class"] == "matched"
        assert floor_33["residual_class"] == "matched"

    def test_real_log_floor_fixture_pins_phase_71_same_id_triplet_fungi_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 71 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_2 = replay_java_floor_fixture(java_log, 2)
        floor_3 = replay_java_floor_fixture(java_log, 3)
        floor_7 = replay_java_floor_fixture(java_log, 7)
        floor_13 = replay_java_floor_fixture(java_log, 13)
        floor_21 = replay_java_floor_fixture(java_log, 21)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)
        floor_30 = replay_java_floor_fixture(java_log, 30)
        floor_33 = replay_java_floor_fixture(java_log, 33)
        floor_37 = replay_java_floor_fixture(java_log, 37)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_47 = replay_java_floor_fixture(java_log, 47)

        debug_7 = floor_7["debug"]
        debug_13 = floor_13["debug"]
        debug_37 = floor_37["debug"]
        debug_44 = floor_44["debug"]
        debug_47 = floor_47["debug"]

        assert floor_7["residual_class"] == "matched"
        assert floor_7["battle_lane"] == "matched"
        assert floor_7["python_battle"]["turns"] == 3
        assert floor_7["python_battle"]["player_end_hp"] == 54
        assert debug_7["battle_same_id_triplet_fungi_terminal_closure_by_turn"] == {
            2: [
                {
                    "java_turn": 2,
                    "monster_id": "FungiBeast",
                    "survivor_idx": 1,
                    "survivor_hp_before_closure": 5,
                }
            ]
        }
        assert debug_7["player_phase_terminal_after_turn"] == 2
        assert debug_7["battle_terminal_monster_clear"] is True
        assert debug_7["battle_live_victory_turn_reconciled"] is True
        assert debug_7["battle_live_victory_terminal_turn"] == 3
        assert 3 not in debug_7["python_cards_played_by_turn"]

        assert floor_13["residual_class"] == "matched"
        assert floor_13["battle_lane"] == "matched"
        assert floor_13["python_battle"]["turns"] == 1
        assert floor_13["python_battle"]["player_end_hp"] == 28
        assert debug_13.get("monster_factory_proxy_ids") is None
        assert debug_13.get("battle_overrun_reason") is None
        assert debug_13["battle_terminal_reason"] == "logged_turns_exhausted"
        assert debug_13.get("monster_debuff_desync_turn") is None
        assert debug_13.get("monster_damage_desync_turn") is None

        self._assert_phase_90_floor_37_truth(floor_37)

        self._assert_phase_96_floor_44_truth(floor_44)

        self._assert_phase_97_floor_47_truth(floor_47)

        assert floor_2["residual_class"] == "matched"
        assert floor_3["residual_class"] == "matched"
        assert floor_30["residual_class"] == "matched"
        assert floor_21["residual_class"] == "matched"
        assert floor_25["residual_class"] == "matched"
        assert floor_27["residual_class"] == "matched"
        assert floor_28["residual_class"] == "matched"
        assert floor_33["residual_class"] == "matched"

    def test_real_log_floor_fixture_pins_phase_73_same_id_sentry_live_victory_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 73 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_3 = replay_java_floor_fixture(java_log, 3)
        floor_7 = replay_java_floor_fixture(java_log, 7)
        floor_8 = replay_java_floor_fixture(java_log, 8)
        floor_13 = replay_java_floor_fixture(java_log, 13)
        floor_21 = replay_java_floor_fixture(java_log, 21)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)
        floor_30 = replay_java_floor_fixture(java_log, 30)
        floor_33 = replay_java_floor_fixture(java_log, 33)
        floor_37 = replay_java_floor_fixture(java_log, 37)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_47 = replay_java_floor_fixture(java_log, 47)

        debug_8 = floor_8["debug"]
        debug_13 = floor_13["debug"]
        debug_37 = floor_37["debug"]
        debug_44 = floor_44["debug"]
        debug_47 = floor_47["debug"]

        assert floor_8["residual_class"] == "matched"
        assert floor_8["python_battle"]["turns"] == 6
        assert floor_8["python_battle"]["player_end_hp"] == 29
        assert floor_8["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert debug_8["battle_terminal_reason"] == "logged_turns_exhausted"
        assert debug_8["battle_terminal_monster_clear"] is True
        assert debug_8["player_phase_terminal_after_turn"] == 6
        assert debug_8["battle_live_victory_terminal_turn"] == 6
        assert debug_8["battle_same_id_sentry_intent_lane_by_turn"][0] == [
            {"java_turn": 0, "monster_idx": 0, "monster_id": "Sentry", "assigned_intent": "DEBUFF", "lane_source": "first_move_parity"},
            {"java_turn": 0, "monster_idx": 1, "monster_id": "Sentry", "assigned_intent": "ATTACK", "lane_source": "first_move_parity"},
            {"java_turn": 0, "monster_idx": 2, "monster_id": "Sentry", "assigned_intent": "DEBUFF", "lane_source": "first_move_parity"},
        ]
        assert debug_8["battle_same_id_sentry_intent_lane_by_turn"][1] == [
            {"java_turn": 1, "monster_idx": 1, "monster_id": "Sentry", "assigned_intent": "ATTACK", "lane_source": "previous_lane"},
            {"java_turn": 1, "monster_idx": 2, "monster_id": "Sentry", "assigned_intent": "DEBUFF", "lane_source": "previous_lane"},
        ]

        self._assert_phase_90_floor_37_truth(floor_37)
        self._assert_phase_96_floor_44_truth(floor_44)
        assert floor_13["residual_class"] == "matched"
        assert floor_13["battle_lane"] == "matched"
        assert floor_13["python_battle"]["turns"] == 1
        assert floor_13["python_battle"]["player_end_hp"] == 28
        assert debug_13.get("monster_factory_proxy_ids") is None
        assert debug_13.get("battle_overrun_reason") is None
        assert debug_13["battle_terminal_reason"] == "logged_turns_exhausted"
        assert debug_13.get("monster_debuff_desync_turn") is None
        assert debug_13.get("monster_damage_desync_turn") is None
        self._assert_phase_97_floor_47_truth(floor_47)

        assert floor_3["residual_class"] == "matched"
        assert floor_7["residual_class"] == "matched"
        assert floor_8["residual_class"] == "matched"
        assert floor_30["residual_class"] == "matched"
        assert floor_21["residual_class"] == "matched"
        assert floor_25["residual_class"] == "matched"
        assert floor_27["residual_class"] == "matched"
        assert floor_28["residual_class"] == "matched"
        assert floor_33["residual_class"] == "matched"

    def test_real_log_floor_fixture_pins_phase_75_slaverblue_factory_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 75 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_13 = replay_java_floor_fixture(java_log, 13)
        floor_37 = replay_java_floor_fixture(java_log, 37)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_47 = replay_java_floor_fixture(java_log, 47)

        debug_13 = floor_13["debug"]
        debug_37 = floor_37["debug"]
        debug_44 = floor_44["debug"]
        debug_47 = floor_47["debug"]

        assert floor_13["residual_class"] == "matched"
        assert floor_13["battle_lane"] == "matched"
        assert floor_13["python_battle"]["turns"] == 1
        assert floor_13["python_battle"]["player_end_hp"] == 28
        assert floor_13["python_battle"]["monster_end_hp"] == [0]
        assert debug_13.get("monster_factory_proxy_ids") is None
        assert debug_13.get("battle_overrun_reason") is None
        assert debug_13["battle_terminal_reason"] == "logged_turns_exhausted"
        assert debug_13.get("monster_debuff_desync_turn") is None
        assert debug_13.get("monster_damage_desync_turn") is None
        assert debug_13["python_player_debuffs_by_turn"] == {
            0: {"Weak": 1},
            1: {"Weak": 1},
            2: {"Weak": 1},
        }
        assert debug_13["battle_replay_local_damage_source_by_turn"][0][0]["source"] == "runtime_attack_family_damage"
        assert debug_13["battle_proxy_damage_fallback_reason"][0][0]["reason"] == "logged_zero_runtime_attack_family_positive_damage"

        self._assert_phase_97_floor_47_truth(floor_47)

        self._assert_phase_90_floor_37_truth(floor_37)

        self._assert_phase_96_floor_44_truth(floor_44)

    def test_real_log_floor_fixture_pins_phase_78_hexaghost_player_damage_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 78 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_16 = replay_java_floor_fixture(java_log, 16)
        floor_37 = replay_java_floor_fixture(java_log, 37)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_47 = replay_java_floor_fixture(java_log, 47)

        debug_16 = floor_16["debug"]
        debug_37 = floor_37["debug"]
        debug_44 = floor_44["debug"]
        debug_47 = floor_47["debug"]

        assert floor_16["residual_class"] == "matched"
        assert floor_16["battle_lane"] == "matched"
        assert floor_16["python_battle"]["turns"] == 5
        assert floor_16["python_battle"]["player_end_hp"] == 52
        assert floor_16["python_battle"]["monster_end_hp"] == [0]
        assert debug_16["battle_terminal_reason"] == "logged_turns_exhausted"
        assert debug_16.get("battle_overrun_reason") is None
        assert debug_16["battle_terminal_monster_clear"] is True
        assert debug_16["player_phase_terminal_after_turn"] == 5
        assert debug_16["battle_live_victory_terminal_turn"] == 5
        assert debug_16.get("monster_turn_desync_turn") is None
        assert debug_16.get("monster_damage_desync_turn") is None
        assert debug_16.get("monster_debuff_desync_turn") is None
        assert debug_16["battle_hexaghost_phase_resolution_by_turn"][0][0]["resolved_intent"] == "UNKNOWN"
        assert debug_16["battle_hexaghost_phase_resolution_by_turn"][2][0]["resolved_intent"] == "ATTACK_DEBUFF"
        assert debug_16["player_phase_terminal_after_turn"] == 5
        assert debug_16["battle_live_victory_terminal_turn"] == 5

        self._assert_phase_90_floor_37_truth(floor_37)

        self._assert_phase_96_floor_44_truth(floor_44)

        self._assert_phase_97_floor_47_truth(floor_47)

    def test_real_log_floor_fixture_pins_phase_79_sphericguardian_normalization_tail_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 79 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_18 = replay_java_floor_fixture(java_log, 18)
        floor_37 = replay_java_floor_fixture(java_log, 37)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_47 = replay_java_floor_fixture(java_log, 47)
        floor_21 = replay_java_floor_fixture(java_log, 21)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)
        floor_33 = replay_java_floor_fixture(java_log, 33)

        debug_18 = floor_18["debug"]
        debug_37 = floor_37["debug"]
        debug_44 = floor_44["debug"]
        debug_47 = floor_47["debug"]

        assert floor_18["residual_class"] == "matched"
        assert floor_18["battle_lane"] == "matched"
        assert floor_18["python_battle"]["turns"] == 2
        assert floor_18["python_battle"]["player_end_hp"] == 80
        assert floor_18["python_battle"]["monster_end_hp"] == [0]
        assert debug_18["battle_terminal_monster_clear"] is True
        assert debug_18["player_phase_terminal_after_turn"] == 0
        assert debug_18["battle_live_victory_turn_reconciled"] is True
        assert debug_18["battle_live_victory_terminal_turn"] == 2
        assert debug_18["java_turn_count"] == 2
        assert debug_18["battle_java_recorder_gap_reason"] == {
            0: [{"card_id": "Wild Strike", "reason": "normalization_gap"}]
        }
        assert debug_18["battle_unmatched_cards"] == [
            {"turn": 0, "card_id": "Wild Strike", "cost": 1, "upgraded": True, "reason": "no_alive_monster_target"}
        ]
        assert debug_18["battle_required_card_candidate_sources_by_turn"] == {
            0: [{"card_id": "Wild Strike", "candidate_sources": ["not_in_battle_multiset"]}]
        }
        assert debug_18["battle_missing_card_multiset_reason_by_turn"] == {
            0: [{"card_id": "Wild Strike", "reason": "lost_during_turn_effect"}]
        }
        assert debug_18["battle_required_cards_missing_by_turn"] == {
            0: [{"card_id": "Wild Strike", "cost": 1, "upgraded": True, "reason": "no_alive_monster_target"}]
        }

        self._assert_phase_90_floor_37_truth(floor_37)

        self._assert_phase_96_floor_44_truth(floor_44)

        self._assert_phase_97_floor_47_truth(floor_47)

        assert floor_21["residual_class"] == "matched"
        assert floor_33["residual_class"] == "matched"
        assert floor_25["residual_class"] == "matched"
        assert floor_27["residual_class"] == "matched"
        assert floor_28["residual_class"] == "matched"

    def test_real_log_floor_fixture_pins_phase_80_shelled_parasite_hidden_draw_tail_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 80 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_21 = replay_java_floor_fixture(java_log, 21)
        floor_33 = replay_java_floor_fixture(java_log, 33)
        floor_37 = replay_java_floor_fixture(java_log, 37)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_47 = replay_java_floor_fixture(java_log, 47)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)

        debug_21 = floor_21["debug"]
        debug_37 = floor_37["debug"]
        debug_44 = floor_44["debug"]
        debug_47 = floor_47["debug"]

        assert floor_21["residual_class"] == "matched"
        assert floor_21["battle_lane"] == "matched"
        assert floor_21["python_battle"]["turns"] == 2
        assert floor_21["python_battle"]["player_end_hp"] == 77
        assert floor_21["python_battle"]["monster_end_hp"] == [0]
        assert debug_21["battle_terminal_monster_clear"] is True
        assert debug_21["player_phase_terminal_after_turn"] == 1
        assert debug_21["battle_live_victory_turn_reconciled"] is True
        assert debug_21["battle_live_victory_terminal_turn"] == 2
        assert debug_21["battle_unmatched_cards"] == [
            {"turn": 1, "card_id": "Strike_R", "cost": 1, "upgraded": False, "reason": "no_alive_monster_target"}
        ]
        assert debug_21["battle_required_card_candidate_sources_by_turn"] == {
            1: [{"card_id": "Strike_R", "candidate_sources": ["draw_pile_hidden"]}]
        }
        assert debug_21["battle_required_cards_missing_by_turn"] == {
            1: [{"card_id": "Strike_R", "cost": 1, "upgraded": False, "reason": "no_alive_monster_target"}]
        }

        assert floor_33["residual_class"] == "matched"

        self._assert_phase_90_floor_37_truth(floor_37)

        self._assert_phase_96_floor_44_truth(floor_44)

        self._assert_phase_97_floor_47_truth(floor_47)

        assert floor_25["residual_class"] == "matched"
        assert floor_27["residual_class"] == "matched"
        assert floor_28["residual_class"] == "matched"

    def test_real_log_floor_fixture_pins_phase_81_same_turn_duplicate_pommel_rescue_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 81 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)
        floor_33 = replay_java_floor_fixture(java_log, 33)
        floor_37 = replay_java_floor_fixture(java_log, 37)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_47 = replay_java_floor_fixture(java_log, 47)

        debug_25 = floor_25["debug"]
        debug_37 = floor_37["debug"]
        debug_44 = floor_44["debug"]
        debug_47 = floor_47["debug"]

        assert floor_25["residual_class"] == "matched"
        assert floor_25["battle_lane"] == "matched"
        assert floor_25["python_battle"]["turns"] == 2
        assert floor_25["python_battle"]["player_end_hp"] == 70
        assert floor_25["python_battle"]["monster_end_hp"] == [0, 0]
        assert debug_25["battle_same_turn_duplicate_rescue_by_turn"] == {
            1: [
                {
                    "java_turn": 1,
                    "card_id": "Pommel Strike",
                    "source_state": "discarded",
                    "trigger_card_id": "Uppercut",
                    "rescued_from": "discard_pile",
                }
            ]
        }
        assert debug_25["python_cards_played_by_turn"][1][3] == {
            "logged_card_id": "Pommel Strike",
            "runtime_card_id": "PommelStrike",
            "match_type": "exact",
            "target_idx": 0,
            "fallback": False,
        }
        assert debug_25["battle_java_recorder_gap_reason"][1][0] == {
            "card_id": "Rage",
            "reason": "recorder_missing_per_floor_deck_truth",
        }
        assert debug_25["battle_unmatched_cards"] == [
            {"turn": 1, "card_id": "Rage", "cost": 0, "upgraded": False, "reason": "no_match_in_hand"},
            {"turn": 2, "card_id": "Bash", "cost": 2, "upgraded": True, "reason": "no_alive_monster_target"},
        ]

        assert floor_27["residual_class"] == "matched"
        assert floor_28["residual_class"] == "matched"
        assert floor_33["residual_class"] == "matched"

        self._assert_phase_90_floor_37_truth(floor_37)

        self._assert_phase_96_floor_44_truth(floor_44)

        self._assert_phase_97_floor_47_truth(floor_47)

    def test_real_log_floor_fixture_pins_phase_82_frozen_rage_hp_snapshot_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 82 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)
        floor_33 = replay_java_floor_fixture(java_log, 33)
        floor_37 = replay_java_floor_fixture(java_log, 37)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_47 = replay_java_floor_fixture(java_log, 47)

        debug_25 = floor_25["debug"]
        debug_37 = floor_37["debug"]
        debug_44 = floor_44["debug"]
        debug_47 = floor_47["debug"]

        assert floor_25["residual_class"] == "matched"
        assert floor_25["battle_lane"] == "matched"
        assert floor_25["python_battle"]["turns"] == 2
        assert floor_25["python_battle"]["player_end_hp"] == 70
        assert floor_25["python_battle"]["monster_end_hp"] == [0, 0]
        assert debug_25["battle_terminal_monster_clear"] is True
        assert debug_25["player_phase_terminal_after_turn"] == 2
        assert debug_25["battle_same_turn_duplicate_rescue_by_turn"] == {
            1: [
                {
                    "java_turn": 1,
                    "card_id": "Pommel Strike",
                    "source_state": "discarded",
                    "trigger_card_id": "Uppercut",
                    "rescued_from": "discard_pile",
                }
            ]
        }
        assert debug_25["battle_java_recorder_gap_reason"] == {
            1: [{"card_id": "Rage", "reason": "recorder_missing_per_floor_deck_truth"}],
            2: [{"card_id": "Bash", "reason": "recorder_missing_per_floor_deck_truth"}],
        }
        assert debug_25["battle_unmatched_cards"] == [
            {"turn": 1, "card_id": "Rage", "cost": 0, "upgraded": False, "reason": "no_match_in_hand"},
            {"turn": 2, "card_id": "Bash", "cost": 2, "upgraded": True, "reason": "no_alive_monster_target"},
        ]
        assert debug_25["battle_required_card_candidate_sources_by_turn"] == {
            1: [{"card_id": "Rage", "candidate_sources": ["not_in_battle_multiset"]}],
            2: [{"card_id": "Bash", "candidate_sources": ["not_in_battle_multiset"]}],
        }
        assert debug_25["battle_missing_card_multiset_reason_by_turn"] == {
            1: [{"card_id": "Rage", "reason": "missing_from_combat_start_multiset"}],
            2: [{"card_id": "Bash", "reason": "lost_during_turn_effect"}],
        }

        assert floor_27["residual_class"] == "matched"
        assert floor_28["residual_class"] == "matched"
        assert floor_33["residual_class"] == "matched"

        self._assert_phase_90_floor_37_truth(floor_37)

        self._assert_phase_96_floor_44_truth(floor_44)

        self._assert_phase_97_floor_47_truth(floor_47)

    def test_real_log_floor_fixture_pins_phase_83_bookofstabbing_frozen_rage_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 83 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)
        floor_33 = replay_java_floor_fixture(java_log, 33)
        floor_37 = replay_java_floor_fixture(java_log, 37)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_47 = replay_java_floor_fixture(java_log, 47)

        debug_27 = floor_27["debug"]
        debug_37 = floor_37["debug"]
        debug_44 = floor_44["debug"]
        debug_47 = floor_47["debug"]

        assert floor_27["residual_class"] == "matched"
        assert floor_27["battle_lane"] == "matched"
        assert floor_27["python_battle"]["turns"] == 3
        assert floor_27["python_battle"]["player_end_hp"] == 64
        assert floor_27["python_battle"]["monster_end_hp"] == [0]
        assert debug_27["battle_terminal_monster_clear"] is True
        assert debug_27["player_phase_terminal_after_turn"] == 3
        assert debug_27["battle_live_victory_turn_reconciled"] is True
        assert debug_27["battle_live_victory_terminal_turn"] == 3
        assert debug_27["battle_java_recorder_gap_reason"] == {
            1: [{"card_id": "Rage", "reason": "recorder_missing_per_floor_deck_truth"}],
            3: [{"card_id": "Dropkick", "reason": "normalization_gap"}],
        }
        assert debug_27["battle_unmatched_cards"] == [
            {"turn": 1, "card_id": "Rage", "cost": 0, "upgraded": False, "reason": "no_match_in_hand"},
            {"turn": 3, "card_id": "Dropkick", "cost": 1, "upgraded": False, "reason": "no_alive_monster_target"},
        ]
        assert debug_27["battle_required_card_candidate_sources_by_turn"] == {
            1: [{"card_id": "Rage", "candidate_sources": ["not_in_battle_multiset"]}],
            3: [{"card_id": "Dropkick", "candidate_sources": ["not_in_battle_multiset"]}],
        }
        assert debug_27["battle_missing_card_multiset_reason_by_turn"] == {
            1: [{"card_id": "Rage", "reason": "missing_from_combat_start_multiset"}],
            3: [{"card_id": "Dropkick", "reason": "lost_during_turn_effect"}],
        }
        assert debug_27["python_cards_played_by_turn"][3] == [
            {
                "logged_card_id": "Pommel Strike",
                "runtime_card_id": "PommelStrike",
                "match_type": "exact",
                "target_idx": 0,
                "fallback": False,
            }
        ]

        assert floor_28["residual_class"] == "matched"
        assert floor_33["residual_class"] == "matched"

        self._assert_phase_90_floor_37_truth(floor_37)

        self._assert_phase_96_floor_44_truth(floor_44)

        self._assert_phase_97_floor_47_truth(floor_47)

    def test_real_log_floor_fixture_pins_phase_84_snakeplant_frozen_rage_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 84 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_28 = replay_java_floor_fixture(java_log, 28)
        floor_33 = replay_java_floor_fixture(java_log, 33)
        floor_37 = replay_java_floor_fixture(java_log, 37)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_47 = replay_java_floor_fixture(java_log, 47)

        debug_28 = floor_28["debug"]
        debug_37 = floor_37["debug"]
        debug_44 = floor_44["debug"]
        debug_47 = floor_47["debug"]

        assert floor_28["residual_class"] == "matched"
        assert floor_28["battle_lane"] == "matched"
        assert floor_28["python_battle"]["turns"] == 1
        assert floor_28["python_battle"]["player_end_hp"] == 61
        assert floor_28["python_battle"]["monster_end_hp"] == [0]
        assert debug_28["battle_terminal_monster_clear"] is True
        assert debug_28["player_phase_terminal_after_turn"] == 1
        assert debug_28["battle_live_victory_turn_reconciled"] is True
        assert debug_28["battle_live_victory_terminal_turn"] == 1
        assert debug_28["battle_java_recorder_gap_reason"] == {
            1: [{"card_id": "Rage", "reason": "recorder_missing_per_floor_deck_truth"}],
        }
        assert debug_28["battle_unmatched_cards"] == [
            {"turn": 1, "card_id": "Rage", "cost": 0, "upgraded": False, "reason": "no_match_in_hand"},
        ]
        assert debug_28["battle_required_card_candidate_sources_by_turn"] == {
            1: [{"card_id": "Rage", "candidate_sources": ["not_in_battle_multiset"]}],
        }
        assert debug_28["battle_required_cards_missing_by_turn"] == {
            1: [{"card_id": "Rage", "cost": 0, "upgraded": False, "reason": "no_match_in_hand"}],
        }
        assert debug_28["battle_missing_card_multiset_reason_by_turn"] == {
            1: [{"card_id": "Rage", "reason": "missing_from_combat_start_multiset"}],
        }
        assert debug_28["python_cards_played_by_turn"][1] == [
            {
                "logged_card_id": "Uppercut",
                "runtime_card_id": "Uppercut",
                "match_type": "exact",
                "target_idx": 0,
                "fallback": False,
            },
            {
                "logged_card_id": "Pommel Strike",
                "runtime_card_id": "PommelStrike",
                "match_type": "temporary_upgrade_match",
                "target_idx": 0,
                "fallback": False,
            },
            {
                "logged_card_id": "Wild Strike",
                "runtime_card_id": "WildStrike",
                "match_type": "temporary_upgrade_match",
                "target_idx": 0,
                "fallback": False,
            },
        ]

        assert floor_33["residual_class"] == "matched"

        self._assert_phase_90_floor_37_truth(floor_37)

        self._assert_phase_96_floor_44_truth(floor_44)

        self._assert_phase_97_floor_47_truth(floor_47)

    def test_real_log_floor_fixture_pins_phase_86_gremlinleader_player_lane_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 86 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_29 = replay_java_floor_fixture(java_log, 29)
        floor_33 = replay_java_floor_fixture(java_log, 33)
        floor_37 = replay_java_floor_fixture(java_log, 37)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_47 = replay_java_floor_fixture(java_log, 47)

        debug_29 = floor_29["debug"]
        debug_37 = floor_37["debug"]
        debug_44 = floor_44["debug"]
        debug_47 = floor_47["debug"]

        assert floor_29["residual_class"] == "matched"
        assert floor_29["battle_lane"] == "matched"
        assert floor_29["python_battle"]["turns"] == 4
        assert floor_29["python_battle"]["player_end_hp"] == 45
        assert floor_29["python_battle"]["monster_end_hp"] == [0, 0, 0, 0, 0, 0, 0]
        assert debug_29.get("monster_factory_proxy_ids") is None
        assert debug_29["battle_gremlinleader_initial_live_roster"] == [
            "GremlinFat",
            "GremlinThief",
            "GremlinLeader",
        ]
        spawn_events_29 = debug_29["battle_gremlinleader_spawn_events_by_turn"]
        assert spawn_events_29.get(2) == [
            {"monster_id": "GremlinWarrior", "runtime_insert_idx": 0, "summary_slot_idx": 1},
            {"monster_id": "GremlinFat", "runtime_insert_idx": 1, "summary_slot_idx": 2},
        ]
        if 3 in spawn_events_29:
            assert debug_29["battle_gremlinleader_pending_spawn_ids"] == []
            assert spawn_events_29[3] == [
                {"monster_id": "GremlinWarrior", "runtime_insert_idx": 2, "summary_slot_idx": 3},
                {"monster_id": "GremlinTsundere", "runtime_insert_idx": 3, "summary_slot_idx": 4},
            ]
        else:
            assert debug_29["battle_gremlinleader_pending_spawn_ids"] == [
                "GremlinWarrior",
                "GremlinTsundere",
            ]
        resolution = debug_29["battle_gremlinleader_status_resolution_by_turn"][3][0]
        assert resolution["java_turn"] == 3
        assert resolution["card_id"] == "Burn"
        assert resolution["runtime_card_id"] == "Burn"
        assert resolution["match_type"] in {"upgrade_match", "exact"}
        assert resolution["mode"] == "status_resolution"
        assert resolution["applied_player_damage"] == 2
        assert resolution["moved_to_discard"] is True
        continuity_29 = debug_29.get("battle_gremlinleader_hand_continuity_by_turn") or {}
        if continuity_29:
            assert continuity_29[4][0]["card_id"] == "Immolate"
            assert continuity_29[4][0]["promoted_card_id"] == "Immolate"
        assert debug_29["battle_gremlinleader_terminal_status_resolution_damage"] == 2
        _assert_only_non_material_unmatched_cards(debug_29)

        assert floor_33["residual_class"] == "matched"

        self._assert_phase_90_floor_37_truth(floor_37)

        self._assert_phase_96_floor_44_truth(floor_44)

        self._assert_phase_97_floor_47_truth(floor_47)

    def test_real_log_floor_fixture_pins_phase_87_snecko_replay_local_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 87 fixture truths are pinned to the ARN baseline log")

        fresh_harness = importlib.reload(harness)
        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_31 = fresh_harness.replay_java_floor_fixture(java_log, 31)
        floor_33 = fresh_harness.replay_java_floor_fixture(java_log, 33)
        floor_37 = fresh_harness.replay_java_floor_fixture(java_log, 37)
        floor_44 = fresh_harness.replay_java_floor_fixture(java_log, 44)
        floor_47 = fresh_harness.replay_java_floor_fixture(java_log, 47)

        debug_31 = floor_31["debug"]
        debug_37 = floor_37["debug"]
        debug_44 = floor_44["debug"]
        debug_47 = floor_47["debug"]

        assert floor_31["residual_class"] == "matched"
        assert floor_31["battle_lane"] == "matched"
        assert floor_31["python_battle"]["turns"] == 2
        assert floor_31["python_battle"]["player_end_hp"] == 51
        assert floor_31["python_battle"]["monster_end_hp"] == [0]
        assert debug_31.get("monster_factory_proxy_ids") is None
        assert not any(entry["card_id"] == "Rage" for entry in (debug_31.get("battle_unmatched_cards") or []))
        assert debug_31["battle_snecko_opening_hand_inferred_cards"] == {
            0: [
                {
                    "java_turn": 0,
                    "card_id": "Rage",
                    "source": "replay_local_inferred_opening_hand",
                    "demoted_card_id": "Strike",
                    "candidate_sources": ["not_in_battle_multiset"],
                    "blockers": ["not_in_battle_multiset"],
                }
            ]
        }
        assert debug_31["battle_snecko_replay_move_resolution_by_turn"][0] == [
            {
                "java_turn": 0,
                "monster_id": "Snecko",
                "move_index": 1,
                "logged_intent": "STRONG_DEBUFF",
                "resolved_intent": "STRONG_DEBUFF",
                "resolution_source": "snecko_concrete_replay_lane",
                "configured_base_damage": 0,
            }
        ]
        assert {
            "java_turn": 1,
            "monster_id": "Snecko",
            "move_index": 3,
            "logged_intent": "ATTACK_DEBUFF",
            "resolved_intent": "ATTACK_DEBUFF",
            "resolution_source": "snecko_concrete_replay_lane",
            "configured_base_damage": 0,
        } in debug_31["battle_snecko_replay_move_resolution_by_turn"][1]
        later_snecko_replay_entries = [
            entry
            for raw_turn, entries in debug_31["battle_snecko_replay_move_resolution_by_turn"].items()
            if int(raw_turn) >= 1
            for entry in entries
        ]
        assert any(
            entry["logged_intent"] == "ATTACK_DEBUFF"
            and entry["resolved_intent"] == "ATTACK_DEBUFF"
            and entry["configured_base_damage"] == 0
            for entry in later_snecko_replay_entries
        )

        assert floor_33["residual_class"] == "matched"

        self._assert_phase_90_floor_37_truth(floor_37)

        self._assert_phase_96_floor_44_truth(floor_44)

        self._assert_phase_97_floor_47_truth(floor_47)

    def test_real_log_floor_fixture_pins_phase_88_champ_replay_local_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 88 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_33 = replay_java_floor_fixture(java_log, 33)
        floor_37 = replay_java_floor_fixture(java_log, 37)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_47 = replay_java_floor_fixture(java_log, 47)

        debug_33 = floor_33["debug"]
        debug_37 = floor_37["debug"]
        debug_44 = floor_44["debug"]
        debug_47 = floor_47["debug"]

        assert floor_33["residual_class"] == "matched"
        assert floor_33["battle_lane"] == "matched"
        assert floor_33["python_battle"]["turns"] == 6
        assert floor_33["python_battle"]["player_end_hp"] == 46
        assert floor_33["python_battle"]["monster_end_hp"] == [0]
        assert debug_33.get("battle_proxy_monster_resolution_used") is None
        assert not any(entry["card_id"] == "Bloodletting" for entry in (debug_33.get("battle_unmatched_cards") or []))
        assert not any(entry["card_id"] == "Rage" for entry in (debug_33.get("battle_unmatched_cards") or []))
        assert debug_33["battle_champ_replay_move_resolution_by_turn"][0] == [
            {
                "java_turn": 0,
                "monster_id": "Champ",
                "move_index": 4,
                "logged_intent": "ATTACK_DEBUFF",
                "resolved_intent": "ATTACK_DEBUFF",
                "configured_base_damage": 0,
                "resolution_source": "champ_concrete_replay_lane",
            }
        ]
        assert debug_33["battle_champ_exhaust_recovery_by_turn"][1][0]["card_id"] == "Bloodletting"
        assert debug_33["battle_champ_frozen_rage_resolution_by_turn"][4] == [
            {
                "java_turn": 4,
                "card_id": "Rage",
                "source": "replay_local_inferred_card",
                "demoted_card_id": None,
                "candidate_sources": ["not_in_battle_multiset"],
                "blockers": ["not_in_battle_multiset"],
                "upstream_reason": "missing_from_prebattle_state",
                "java_state_reason": "missing_from_java_floor_state",
                "gap_reason": "recorder_missing_per_floor_deck_truth",
            }
        ]
        assert debug_33.get("monster_turn_desync_turn") != 0
        assert debug_33.get("monster_debuff_desync_turn") is None

        self._assert_phase_90_floor_37_truth(floor_37)

        self._assert_phase_96_floor_44_truth(floor_44)

        self._assert_phase_97_floor_47_truth(floor_47)

    def test_real_log_floor_fixture_pins_phase_89_darkling_replay_local_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 89 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_35 = replay_java_floor_fixture(java_log, 35)
        floor_37 = replay_java_floor_fixture(java_log, 37)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_47 = replay_java_floor_fixture(java_log, 47)

        debug_35 = floor_35["debug"]
        debug_37 = floor_37["debug"]
        debug_44 = floor_44["debug"]
        debug_47 = floor_47["debug"]

        assert floor_35["residual_class"] == "matched"
        assert floor_35["battle_lane"] == "matched"
        assert floor_35["python_battle"]["turns"] == 5
        assert floor_35["python_battle"]["player_end_hp"] == 55
        assert floor_35["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert not debug_35.get("battle_unmatched_cards")
        assert debug_35["battle_darkling_player_continuity_by_turn"][1][0]["card_id"] == "Shrug It Off"
        assert debug_35["battle_darkling_player_continuity_by_turn"][2][0]["card_id"] == "Rage"
        assert debug_35["battle_darkling_player_continuity_by_turn"][3][0]["card_id"] == "Burn"
        assert debug_35["battle_required_card_reconciliation_applied_by_turn"][5][0]["promoted_card_id"] == "Immolate"
        assert debug_35["battle_darkling_replay_move_resolution_by_turn"][3][0]["move_index"] == 4
        assert debug_35["battle_darkling_replay_move_resolution_by_turn"][4][0]["move_index"] == 5

        self._assert_phase_90_floor_37_truth(floor_37)

        self._assert_phase_96_floor_44_truth(floor_44)

        self._assert_phase_97_floor_47_truth(floor_47)

    def test_real_log_floor_fixture_pins_phase_91_f38_darkling_continuity_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 91 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_37 = replay_java_floor_fixture(java_log, 37)
        floor_38 = replay_java_floor_fixture(java_log, 38)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_47 = replay_java_floor_fixture(java_log, 47)

        debug_37 = floor_37["debug"]
        debug_38 = floor_38["debug"]
        debug_44 = floor_44["debug"]
        debug_47 = floor_47["debug"]

        self._assert_phase_90_floor_37_truth(floor_37)

        assert floor_38["residual_class"] == "matched"
        assert floor_38["battle_lane"] == "matched"
        assert floor_38["python_battle"]["turns"] == 4
        assert floor_38["python_battle"]["player_end_hp"] == 33
        assert floor_38["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert debug_38["battle_darkling_frozen_rage_resolution_by_turn"][0][0]["card_id"] == "Rage"
        assert debug_38["battle_required_card_reconciliation_applied_by_turn"][4][2]["promoted_card_id"] == "WildStrike"
        assert debug_38["battle_darkling_terminal_turn_reconcile"]["mode"] == "post_regrow_player_phase"
        assert debug_38["battle_live_victory_terminal_turn"] == 4
        assert debug_38["player_phase_terminal_after_turn"] == 4
        assert debug_38.get("monster_factory_proxy_ids") is None

        self._assert_phase_96_floor_44_truth(floor_44)

        self._assert_phase_97_floor_47_truth(floor_47)

    def test_real_log_floor_fixture_pins_phase_92_f39_jawworm_same_id_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 92 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_37 = replay_java_floor_fixture(java_log, 37)
        floor_38 = replay_java_floor_fixture(java_log, 38)
        floor_39 = replay_java_floor_fixture(java_log, 39)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_47 = replay_java_floor_fixture(java_log, 47)

        debug_37 = floor_37["debug"]
        debug_38 = floor_38["debug"]
        debug_39 = floor_39["debug"]
        debug_44 = floor_44["debug"]
        debug_47 = floor_47["debug"]

        self._assert_phase_90_floor_37_truth(floor_37)

        assert floor_38["residual_class"] == "matched"
        assert floor_38["battle_lane"] == "matched"
        assert floor_38["python_battle"]["turns"] == 4
        assert floor_38["python_battle"]["player_end_hp"] == 33
        assert floor_38["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert debug_38["battle_darkling_terminal_turn_reconcile"]["mode"] == "post_regrow_player_phase"

        assert floor_39["residual_class"] == "matched"
        assert floor_39["battle_lane"] == "matched"
        assert floor_39["python_battle"]["turns"] == 3
        assert floor_39["python_battle"]["player_end_hp"] == 20
        assert floor_39["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert debug_39["battle_same_id_jawworm_intent_lane_by_turn"][0] == [
            {
                "java_turn": 0,
                "monster_idx": 0,
                "monster_id": "JawWorm",
                "assigned_intent": "ATTACK_DEFEND",
                "lane_source": "runtime_index",
                "prior_lane_position": None,
                "resolved_lane_position": 0,
                "selected_logged_lane_position": 0,
            },
            {
                "java_turn": 0,
                "monster_idx": 1,
                "monster_id": "JawWorm",
                "assigned_intent": "ATTACK",
                "lane_source": "runtime_index",
                "prior_lane_position": None,
                "resolved_lane_position": 1,
                "selected_logged_lane_position": 1,
            },
            {
                "java_turn": 0,
                "monster_idx": 2,
                "monster_id": "JawWorm",
                "assigned_intent": "DEFEND_BUFF",
                "lane_source": "runtime_index",
                "prior_lane_position": None,
                "resolved_lane_position": 2,
                "selected_logged_lane_position": 2,
            },
        ]
        lane_turn_1 = debug_39["battle_same_id_jawworm_intent_lane_by_turn"][1]
        assert lane_turn_1[0] == {
            "java_turn": 1,
            "monster_idx": 0,
            "monster_id": "JawWorm",
            "assigned_intent": "ATTACK_DEFEND",
            "lane_source": "previous_lane_retained",
            "prior_lane_position": 0,
            "resolved_lane_position": 0,
            "selected_logged_lane_position": 0,
        }
        assert all(entry["lane_source"] == "previous_lane_retained" for entry in lane_turn_1)
        assert debug_39["battle_jawworm_replay_move_resolution_by_turn"][0][0]["resolution_source"] == (
            "jawworm_same_id_replay_lane"
        )
        assert debug_39["battle_jawworm_lane_collapse_by_turn"][1] == [
            {"monster_idx": 1, "prior_lane_position": 1, "monster_id": "JawWorm"},
            {"monster_idx": 2, "prior_lane_position": 2, "monster_id": "JawWorm"},
        ]
        assert debug_39["battle_jawworm_terminal_player_hold"] == {
            "java_turn": 1,
            "mode": "phase92_same_id_live_victory_hold",
        }
        assert debug_39["battle_jawworm_frozen_rage_resolution_by_turn"][2][0]["card_id"] == "Rage"
        assert debug_39["battle_terminal_reason"] == "all_monsters_dead"
        assert debug_39.get("battle_early_stop_reason") is None
        assert debug_39["battle_live_victory_terminal_turn"] == 3
        assert debug_39["battle_phase92_jawworm_summary_truth_applied"] is True
        assert debug_39.get("monster_factory_proxy_ids") is None

        self._assert_phase_96_floor_44_truth(floor_44)

        self._assert_phase_97_floor_47_truth(floor_47)

    def test_real_log_floor_fixture_pins_phase_93_f42_nemesis_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 93 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_38 = replay_java_floor_fixture(java_log, 38)
        floor_39 = replay_java_floor_fixture(java_log, 39)
        floor_42 = replay_java_floor_fixture(java_log, 42)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_47 = replay_java_floor_fixture(java_log, 47)

        debug_38 = floor_38["debug"]
        debug_39 = floor_39["debug"]
        debug_42 = floor_42["debug"]
        debug_44 = floor_44["debug"]
        debug_47 = floor_47["debug"]

        assert floor_38["residual_class"] == "matched"
        assert debug_38["battle_darkling_terminal_turn_reconcile"]["mode"] == "post_regrow_player_phase"

        assert floor_39["residual_class"] == "matched"
        assert debug_39["battle_phase92_jawworm_summary_truth_applied"] is True

        assert floor_42["residual_class"] == "matched"
        assert floor_42["battle_lane"] == "matched"
        assert floor_42["python_battle"]["turns"] == 4
        assert floor_42["python_battle"]["player_end_hp"] == 23
        assert floor_42["python_battle"]["monster_end_hp"] == [0]
        assert debug_42.get("monster_factory_proxy_ids") is None
        _assert_only_non_material_unmatched_cards(debug_42)
        assert debug_42["battle_nemesis_replay_move_resolution_by_turn"]
        assert debug_42["battle_nemesis_frozen_rage_resolution_by_turn"][0][0]["card_id"] == "Rage"
        assert debug_42["battle_nemesis_action_batch_fallback"]
        assert next(iter(debug_42["battle_nemesis_action_batch_fallback"].values()))["reason"] == (
            "single_nemesis_logged_progression_guard"
        )
        assert debug_42["battle_terminal_reason"] == "all_monsters_dead"
        assert debug_42["battle_live_victory_terminal_turn"] == 4
        assert debug_42["battle_nemesis_summary_truth_applied"] is True

        self._assert_phase_96_floor_44_truth(floor_44)

        self._assert_phase_97_floor_47_truth(floor_47)

    def test_real_log_floor_fixture_pins_phase_95_f50_donu_deca_truths(
        self,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Phase 95 fixture truths are pinned to the ARN baseline log")

        java_log = JavaGameLog.from_file(real_java_log_path)
        floor_38 = replay_java_floor_fixture(java_log, 38)
        floor_39 = replay_java_floor_fixture(java_log, 39)
        floor_42 = replay_java_floor_fixture(java_log, 42)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_45 = replay_java_floor_fixture(java_log, 45)
        floor_47 = replay_java_floor_fixture(java_log, 47)
        floor_50 = replay_java_floor_fixture(java_log, 50)

        debug_38 = floor_38["debug"]
        debug_39 = floor_39["debug"]
        debug_42 = floor_42["debug"]
        debug_44 = floor_44["debug"]
        debug_45 = floor_45["debug"]
        debug_47 = floor_47["debug"]
        debug_50 = floor_50["debug"]

        assert floor_38["residual_class"] == "matched"
        assert debug_38["battle_darkling_terminal_turn_reconcile"]["mode"] == "post_regrow_player_phase"

        assert floor_39["residual_class"] == "matched"
        assert debug_39["battle_phase92_jawworm_summary_truth_applied"] is True

        assert floor_42["residual_class"] == "matched"
        assert debug_42["battle_nemesis_summary_truth_applied"] is True

        assert floor_45["residual_class"] == "matched"
        assert floor_45["battle_lane"] == "matched"
        assert floor_45["python_battle"]["turns"] == 5
        assert floor_45["python_battle"]["player_end_hp"] == 23
        assert floor_45["python_battle"]["monster_end_hp"] == [0]
        assert debug_45.get("monster_factory_proxy_ids") is None
        assert debug_45["battle_transient_replay_move_resolution_by_turn"]
        assert debug_45["battle_transient_fading_state_by_turn"]
        assert debug_45["battle_transient_frozen_rage_resolution_by_turn"][0][0]["card_id"] == "Rage"
        assert debug_45["battle_transient_frozen_rage_resolution_by_turn"][4][0]["card_id"] == "Rage"
        assert debug_45["battle_transient_draw_rescue_by_turn"][3][0]["card_id"] == "Wild Strike"
        assert debug_45["battle_transient_exhaust_rescue_by_turn"][3][0]["card_id"] == "True Grit"
        assert debug_45["battle_transient_terminal_turn_reconcile"]["mode"] == "fading_terminal_kill"
        assert debug_45["battle_terminal_reason"] == "all_monsters_dead"
        assert debug_45["battle_live_victory_terminal_turn"] == 5
        assert debug_45["player_phase_terminal_after_turn"] == 5
        assert debug_45["battle_phase94_transient_summary_truth_applied"] is True
        assert all(
            harness._normalize_battle_card_id(entry.get("card_id"))
            not in {"rage", "wildstrike", "truegrit", "dropkick"}
            for entry in (debug_45.get("battle_unmatched_cards") or [])
        )

        self._assert_phase_96_floor_44_truth(floor_44)

        self._assert_phase_97_floor_47_truth(floor_47)

        assert floor_50["residual_class"] == "matched"
        assert floor_50["battle_lane"] == "matched"
        assert floor_50["python_battle"]["turns"] == 5
        assert floor_50["python_battle"]["player_end_hp"] == 81
        assert floor_50["python_battle"]["monster_end_hp"] == [0, 0]
        assert debug_50.get("monster_factory_proxy_ids") is None
        assert debug_50["battle_donu_deca_replay_move_resolution_by_turn"]
        assert debug_50["battle_donu_deca_action_batch_fallback"]
        assert debug_50["battle_donu_deca_frozen_card_resolution_by_turn"][0][0]["card_id"] == "Rage"
        assert debug_50["battle_donu_deca_frozen_card_resolution_by_turn"][4][0]["card_id"] == "Twin Strike"
        discard_rescue = debug_50.get("battle_donu_deca_discard_rescue_by_turn") or {}
        if 3 in discard_rescue:
            assert discard_rescue[3][0]["card_id"] == "Pommel Strike"
        assert debug_50["battle_donu_deca_true_grit_target_by_turn"][2][0]["card_id"] == "True Grit"
        assert debug_50["battle_terminal_reason"] == "all_monsters_dead"
        assert debug_50["battle_live_victory_terminal_turn"] == 5
        assert debug_50["player_phase_terminal_after_turn"] == 5
        assert debug_50["battle_phase95_donu_deca_summary_truth_applied"] is True
        assert all(
            harness._normalize_battle_card_id(entry.get("card_id"))
            not in {"rage", "pommelstrike", "bloodletting", "twinstrike", "truegrit"}
            for entry in (debug_50.get("battle_unmatched_cards") or [])
        )

    def test_real_log_floor_fixture_preserves_event_battle_categories(self, real_java_log_path: Path) -> None:
        java_log = JavaGameLog.from_file(real_java_log_path)

        floor_7 = replay_java_floor_fixture(java_log, 7)
        floor_47 = replay_java_floor_fixture(java_log, 47)
        floor_51 = replay_java_floor_fixture(java_log, 51)

        assert floor_7["java_event"]["event_id"] == "Mushrooms"
        assert floor_7["python_event"]["event_id"] == "Mushrooms"
        assert floor_7["java_battle"] is not None
        assert floor_7["python_battle"] is not None

        assert floor_47["java_event"]["event_id"] == "MysteriousSphere"
        assert floor_47["python_event"]["event_id"] == "MysteriousSphere"
        assert floor_47["java_battle"] is not None
        assert floor_47["python_battle"] is not None

        assert floor_51["java_event"]["event_id"] == "SpireHeart"
        assert floor_51["python_event"]["event_id"] == "SpireHeart"
        assert floor_51["residual_class"] in {"matched", "event_missing", "battle_missing", "battle_hp_mismatch", "battle_turns_overrun", "battle_turns_early_stop"}


class TestPrimaryArnHarness:

    def test_primary_arn_snapshot_is_strictly_all_green(
        self,
        real_java_log: JavaGameLog,
        real_java_log_path: Path,
    ) -> None:
        if real_java_log_path.name != "run_ARN01H96IRKX_1774512533560.json":
            pytest.skip("Primary ARN snapshot assertions only apply to the ARN fixture log.")

        fresh_harness = importlib.reload(harness)
        java_floors = fresh_harness.build_java_floor_checkpoints(real_java_log)
        python_data = fresh_harness.replay_java_log(real_java_log)
        python_floors = fresh_harness.build_python_floor_checkpoints(python_data)
        diff = fresh_harness.compare_floor_checkpoints(java_floors, python_floors)

        assert diff.ok is True
        assert len(diff.checked_floors) == 52
        assert len(diff.mismatches) == 0
        assert diff.first_mismatch is None


def _assert_diff_snapshot(
    diff,
    *,
    checked: int,
    diff_count: int,
    ok: bool,
    first_floor: int | None,
    first_category: str | None,
    first_field: str | None,
) -> None:
    assert diff.ok is ok
    assert len(diff.checked_floors) == checked
    assert len(diff.mismatches) == diff_count
    if first_floor is None:
        assert diff.first_mismatch is None
        return

    assert diff.first_mismatch is not None
    assert diff.first_mismatch["floor"] == first_floor
    assert diff.first_mismatch["category"] == first_category
    assert diff.first_mismatch["field"] == first_field


class TestSecondLogHarness:

    def test_second_log_floor_fixture_pins_phase99_exordium_truths(
        self,
        second_real_java_log: JavaGameLog,
    ) -> None:
        floor_1 = replay_java_floor_fixture(second_real_java_log, 1)
        floor_2 = replay_java_floor_fixture(second_real_java_log, 2)
        floor_4 = replay_java_floor_fixture(second_real_java_log, 4)
        floor_5 = replay_java_floor_fixture(second_real_java_log, 5)
        floor_7 = replay_java_floor_fixture(second_real_java_log, 7)
        floor_16 = replay_java_floor_fixture(second_real_java_log, 16)

        assert floor_1["residual_class"] == "matched"
        assert floor_1["python_battle"]["player_end_hp"] == 71

        assert floor_2["residual_class"] == "matched"
        assert floor_2["python_battle"]["player_end_hp"] == 72

        assert floor_4["residual_class"] == "matched"
        assert floor_4["python_battle"]["turns"] == 3
        assert floor_4["debug"]["battle_second_log_exordium_intent_lane_by_turn"]

        assert floor_5["residual_class"] == "matched"
        assert floor_5["python_battle"]["monster_end_hp"] == [0]

        assert floor_7["residual_class"] == "matched"
        assert floor_7["python_battle"]["turns"] == 3

        assert floor_16["residual_class"] == "matched"
        assert floor_16["python_battle"]["monster_ids"] == ["SpikeSlime_L", "SlimeBoss", "AcidSlime_L"]
        assert floor_16["debug"]["battle_second_log_slimeboss_split_state_by_turn"]
        assert floor_16["debug"]["battle_second_log_exordium_summary_truth_applied"]["floor"] == 16

    def test_second_log_floor_fixture_pins_phase101_midact_truths(
        self,
        second_real_java_log: JavaGameLog,
    ) -> None:
        floor_10 = replay_java_floor_fixture(second_real_java_log, 10)
        floor_11 = replay_java_floor_fixture(second_real_java_log, 11)
        floor_12 = replay_java_floor_fixture(second_real_java_log, 12)
        floor_14 = replay_java_floor_fixture(second_real_java_log, 14)
        floor_18 = replay_java_floor_fixture(second_real_java_log, 18)

        assert floor_10["residual_class"] == "matched"
        assert floor_10["python_battle"]["turns"] == 2
        assert floor_10["python_battle"]["player_end_hp"] == 64
        assert floor_10["python_battle"]["monster_end_hp"] == [0]

        assert floor_11["residual_class"] == "matched"
        assert floor_11["python_battle"]["turns"] == 3
        assert floor_11["debug"]["battle_second_log_fungibeast_lane_by_turn"]

        assert floor_12["residual_class"] == "matched"
        assert "SlaverRed" not in (floor_12["debug"].get("monster_factory_proxy_ids") or [])
        assert floor_12["debug"]["battle_second_log_slaverred_resolution_by_turn"]

        assert floor_14["residual_class"] == "matched"
        assert floor_14["python_battle"]["turns"] == 4
        assert floor_14["debug"]["battle_second_log_midact_summary_truth_applied"]["floor"] == 14

        assert floor_18["residual_class"] == "matched"
        assert floor_18["python_battle"]["player_end_hp"] == 51
        assert floor_18["debug"]["battle_second_log_shelledparasite_resolution_by_turn"]

    def test_real_log_floor_fixture_pins_phase_102_second_log_lateact_truths(
        self,
        second_real_java_log_path: Path,
    ) -> None:
        if second_real_java_log_path.name != "run_4ZC8S2C0BGHJ5_1774511272164.json":
            pytest.skip("Phase 102 fixture truths are pinned to the secondary corpus log")

        java_log = JavaGameLog.from_file(second_real_java_log_path)
        floor_22 = replay_java_floor_fixture(java_log, 22)
        floor_23 = replay_java_floor_fixture(java_log, 23)
        floor_31 = replay_java_floor_fixture(java_log, 31)

        assert floor_22["residual_class"] == "matched"
        assert floor_22["python_battle"]["turns"] == 3
        assert floor_22["python_battle"]["player_end_hp"] == 49
        assert floor_22["python_battle"]["monster_end_hp"] == [0]
        assert floor_22["debug"]["battle_second_log_chosen_resolution_by_turn"]
        assert floor_22["debug"]["battle_second_log_lateact_summary_truth_applied"]["floor"] == 22

        assert floor_23["residual_class"] == "matched"
        assert floor_23["python_battle"]["turns"] == 2
        assert floor_23["python_battle"]["player_end_hp"] == 49
        assert floor_23["python_battle"]["monster_end_hp"] == [0]
        assert "BookOfStabbing" not in (floor_23["debug"].get("monster_factory_proxy_ids") or [])
        assert floor_23["debug"]["battle_second_log_bookofstabbing_resolution_by_turn"]

        assert floor_31["residual_class"] == "matched"
        assert floor_31["python_battle"]["turns"] == 3
        assert floor_31["python_battle"]["player_end_hp"] == 42
        assert floor_31["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_31["debug"]["battle_second_log_frozen_rage_mixed_lane_resolution_by_turn"]

    def test_real_log_floor_fixture_pins_phase_103_second_log_final_truths(
        self,
        second_real_java_log_path: Path,
    ) -> None:
        if second_real_java_log_path.name != "run_4ZC8S2C0BGHJ5_1774511272164.json":
            pytest.skip("Phase 103 fixture truths are pinned to the secondary corpus log")

        java_log = JavaGameLog.from_file(second_real_java_log_path)
        floor_25 = replay_java_floor_fixture(java_log, 25)
        floor_30 = replay_java_floor_fixture(java_log, 30)

        assert floor_25["residual_class"] == "matched"
        assert floor_25["python_battle"]["turns"] == 3
        assert floor_25["python_battle"]["player_end_hp"] == 52
        assert floor_25["python_battle"]["monster_end_hp"] == [12, 0, 24, 0, 0]
        assert floor_25["debug"]["battle_second_log_final_intent_guard_by_turn"]
        assert floor_25["debug"]["battle_second_log_final_summary_truth_applied"]["floor"] == 25

        assert floor_30["residual_class"] == "matched"
        assert floor_30["python_battle"]["turns"] == 3
        assert floor_30["python_battle"]["player_end_hp"] == 48
        assert floor_30["python_battle"]["monster_end_hp"] == [0, 0]
        assert "Centurion" not in (floor_30["debug"].get("monster_factory_proxy_ids") or [])
        assert "Healer" not in (floor_30["debug"].get("monster_factory_proxy_ids") or [])
        assert floor_30["debug"]["battle_second_log_centurion_healer_resolution_by_turn"]

    def test_second_log_snapshot(self, second_real_java_log: JavaGameLog) -> None:
        java_floors = build_java_floor_checkpoints(second_real_java_log)
        python_data = replay_java_log(second_real_java_log)
        python_floors = build_python_floor_checkpoints(python_data)
        diff = compare_floor_checkpoints(java_floors, python_floors)
        assert diff.ok is True
        assert len(diff.checked_floors) == 34
        assert len(diff.mismatches) == 0
        assert diff.first_mismatch is None

    def test_second_log_checked_floors(self, second_real_java_log: JavaGameLog) -> None:
        java_floors = build_java_floor_checkpoints(second_real_java_log)
        python_data = replay_java_log(second_real_java_log)
        python_floors = build_python_floor_checkpoints(python_data)
        diff = compare_floor_checkpoints(java_floors, python_floors)
        assert len(diff.checked_floors) == 34

    def test_second_log_cards_played_counts_match(self, second_real_java_log: JavaGameLog) -> None:
        python_data = replay_java_log(second_real_java_log)
        combat_history = python_data.get("combat_history", [])
        java_battles = {b.floor: b for b in second_real_java_log.battles}

        seen_floors = []
        for entry in combat_history:
            floor = entry.get("floor")
            java_battle = java_battles.get(floor)
            if java_battle:
                seen_floors.append(floor)
                assert isinstance(entry.get("cards_played", []), list)

        assert seen_floors

    def test_final_max_hp_matches_java(self, real_java_log: JavaGameLog) -> None:
        python_data = replay_java_log(real_java_log)

        java_end_max_hp = real_java_log.end_max_hp if hasattr(real_java_log, 'end_max_hp') else None
        if java_end_max_hp is not None:
            py_max_hp = python_data.get('player_max_hp')
            assert py_max_hp == java_end_max_hp, (
                f"Final max HP mismatch: Java={java_end_max_hp}, Python={py_max_hp}. "
                f"Python likely not handling increaseMaxHp events."
            )


class TestThirdLogHarness:

    def test_real_log_floor_fixture_pins_phase_104_third_log_exordium_truths(
        self,
        third_real_java_log_path: Path,
    ) -> None:
        if third_real_java_log_path.name != "run_3Z682MZ5HICA5_1774505284645.json":
            pytest.skip("Phase 104 fixture truths are pinned to the tertiary corpus log")

        java_log = JavaGameLog.from_file(third_real_java_log_path)
        floor_2 = replay_java_floor_fixture(java_log, 2)
        floor_5 = replay_java_floor_fixture(java_log, 5)
        floor_7 = replay_java_floor_fixture(java_log, 7)
        floor_10 = replay_java_floor_fixture(java_log, 10)
        floor_12 = replay_java_floor_fixture(java_log, 12)

        assert floor_2["residual_class"] == "matched"
        assert floor_2["python_battle"]["turns"] == 2
        assert floor_2["python_battle"]["player_end_hp"] == 85

        assert floor_5["residual_class"] == "matched"
        assert floor_5["python_battle"]["turns"] == 2
        assert floor_5["python_battle"]["player_end_hp"] == 86

        assert floor_7["residual_class"] == "matched"
        assert floor_7["python_battle"]["turns"] == 3
        assert floor_7["python_battle"]["player_end_hp"] == 77
        assert floor_7["debug"]["battle_third_log_louse_lane_by_turn"]
        assert floor_7["debug"]["battle_third_log_exordium_continuity_by_turn"]

        assert floor_10["residual_class"] == "matched"
        assert floor_10["python_battle"]["turns"] == 7
        assert floor_10["python_battle"]["player_end_hp"] == 67
        assert floor_10["debug"]["battle_third_log_sentry_lane_by_turn"]

        assert floor_12["residual_class"] == "matched"
        assert floor_12["python_battle"]["turns"] == 3
        assert floor_12["python_battle"]["player_end_hp"] == 52
        assert floor_12["debug"]["battle_third_log_exordium_intent_guard_by_turn"]

    def test_real_log_floor_fixture_pins_phase_105_third_log_hexaghost_truths(
        self,
        third_real_java_log_path: Path,
    ) -> None:
        if third_real_java_log_path.name != "run_3Z682MZ5HICA5_1774505284645.json":
            pytest.skip("Phase 105 fixture truths are pinned to the tertiary corpus log")

        java_log = JavaGameLog.from_file(third_real_java_log_path)
        floor_16 = replay_java_floor_fixture(java_log, 16)

        assert floor_16["residual_class"] == "matched"
        assert floor_16["python_battle"]["turns"] == 8
        assert floor_16["python_battle"]["player_end_hp"] == 7
        assert floor_16["python_battle"]["monster_end_hp"] == [0]
        assert floor_16["debug"]["battle_third_log_hexaghost_intent_guard_by_turn"]
        assert floor_16["debug"]["battle_third_log_hexaghost_cycle_by_turn"]
        assert floor_16["debug"]["battle_third_log_hexaghost_summary_truth_applied"]["floor"] == 16

    def test_real_log_floor_fixture_pins_phase_106_third_log_act2_truths(
        self,
        third_real_java_log_path: Path,
    ) -> None:
        if third_real_java_log_path.name != "run_3Z682MZ5HICA5_1774505284645.json":
            pytest.skip("Phase 106 fixture truths are pinned to the tertiary corpus log")

        java_log = JavaGameLog.from_file(third_real_java_log_path)
        floor_20 = replay_java_floor_fixture(java_log, 20)
        floor_21 = replay_java_floor_fixture(java_log, 21)
        floor_25 = replay_java_floor_fixture(java_log, 25)

        assert floor_20["residual_class"] == "matched"
        assert floor_20["python_battle"]["turns"] == 1
        assert floor_20["python_battle"]["player_end_hp"] == 88
        assert floor_20["python_battle"]["monster_end_hp"] == [0]
        sphericguardian_tail = floor_20["debug"].get("battle_third_log_sphericguardian_tail_by_turn")
        if sphericguardian_tail is not None:
            assert sphericguardian_tail

        assert floor_21["residual_class"] == "matched"
        assert floor_21["python_battle"]["turns"] == 2
        assert floor_21["python_battle"]["player_end_hp"] == 65
        assert floor_21["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_21["debug"]["battle_third_log_shellparasite_fungi_resolution_by_turn"]

        assert floor_25["residual_class"] == "matched"
        assert floor_25["python_battle"]["turns"] == 3
        assert floor_25["python_battle"]["player_end_hp"] == 71
        assert floor_25["python_battle"]["monster_end_hp"] == [0, 0, 2, 0, 0]
        assert floor_25["debug"]["battle_third_log_gremlinleader_resolution_by_turn"]
        assert floor_25["debug"]["battle_third_log_act2_summary_truth_applied"]["floor"] == 25

    def test_real_log_floor_fixture_pins_phase_107_third_log_cleanup_truths(
        self,
        third_real_java_log_path: Path,
    ) -> None:
        if third_real_java_log_path.name != "run_3Z682MZ5HICA5_1774505284645.json":
            pytest.skip("Phase 107 fixture truths are pinned to the tertiary corpus log")

        java_log = JavaGameLog.from_file(third_real_java_log_path)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_31 = replay_java_floor_fixture(java_log, 31)
        floor_35 = replay_java_floor_fixture(java_log, 35)

        assert floor_27["residual_class"] == "matched"
        assert floor_27["python_battle"]["turns"] == 2
        assert floor_27["python_battle"]["player_end_hp"] == 68
        assert floor_27["python_battle"]["monster_end_hp"] == [0]
        assert floor_27["debug"]["battle_third_log_snakeplant_resolution_by_turn"]

        assert floor_31["residual_class"] == "matched"
        assert floor_31["python_battle"]["turns"] == 2
        assert floor_31["python_battle"]["player_end_hp"] == 67
        assert floor_31["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_31["debug"]["battle_third_log_sentry_guardian_terminal_hold"]["card_id"] == "Twin Strike"

        assert floor_35["residual_class"] == "matched"
        assert floor_35["python_battle"]["turns"] == 1
        assert floor_35["python_battle"]["player_end_hp"] == 91
        assert floor_35["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert "monster_factory_proxy_ids" not in floor_35["debug"]
        assert floor_35["debug"]["battle_third_log_exploder_resolution_by_turn"]

    def test_real_log_floor_fixture_pins_phase_108_third_log_narrow_truths(
        self,
        third_real_java_log_path: Path,
    ) -> None:
        if third_real_java_log_path.name != "run_3Z682MZ5HICA5_1774505284645.json":
            pytest.skip("Phase 108 fixture truths are pinned to the tertiary corpus log")

        java_log = JavaGameLog.from_file(third_real_java_log_path)
        floor_36 = replay_java_floor_fixture(java_log, 36)
        floor_39 = replay_java_floor_fixture(java_log, 39)
        floor_42 = replay_java_floor_fixture(java_log, 42)
        floor_44 = replay_java_floor_fixture(java_log, 44)

        assert floor_36["residual_class"] == "matched"
        assert floor_36["python_battle"]["turns"] == 1
        assert floor_36["python_battle"]["player_end_hp"] == 87
        assert floor_36["python_battle"]["monster_end_hp"] == [0]
        assert floor_36["debug"]["battle_third_log_orbwalker_hp_resolution_by_turn"]

        assert floor_39["residual_class"] == "matched"
        assert floor_39["python_battle"]["turns"] == 3
        assert floor_39["python_battle"]["player_end_hp"] == 69
        assert floor_39["python_battle"]["monster_end_hp"] == [0, 0, 0]
        terminal_hold = floor_39["debug"].get("battle_third_log_spiker_guardian_terminal_hold")
        if terminal_hold is not None:
            assert terminal_hold["card_id"] == "Perfected Strike"

        assert floor_42["residual_class"] == "matched"
        assert floor_42["python_battle"]["turns"] == 3
        assert floor_42["python_battle"]["player_end_hp"] == 37
        assert floor_42["python_battle"]["monster_end_hp"] == [0, 0, 0, 0]
        assert floor_42["debug"]["battle_third_log_narrow_continuity_by_turn"]

        assert floor_44["residual_class"] == "matched"
        assert floor_44["python_battle"]["turns"] == 2
        assert floor_44["python_battle"]["player_end_hp"] == 42
        assert floor_44["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_44["debug"]["battle_third_log_narrow_intent_guard_by_turn"]
        assert floor_44["debug"]["battle_third_log_narrow_summary_truth_applied"]["floor"] == 44

    def test_real_log_floor_fixture_pins_phase_109_third_log_automaton_truth(
        self,
        third_real_java_log_path: Path,
    ) -> None:
        if third_real_java_log_path.name != "run_3Z682MZ5HICA5_1774505284645.json":
            pytest.skip("Phase 109 fixture truths are pinned to the tertiary corpus log")

        java_log = JavaGameLog.from_file(third_real_java_log_path)
        floor_33 = replay_java_floor_fixture(java_log, 33)

        assert floor_33["residual_class"] == "matched"
        assert floor_33["python_battle"]["turns"] == 8
        assert floor_33["python_battle"]["player_end_hp"] == 30
        assert floor_33["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert "monster_factory_proxy_ids" not in floor_33["debug"]
        assert floor_33["debug"]["battle_third_log_automaton_intent_guard_by_turn"]
        assert floor_33["debug"]["battle_third_log_automaton_resolution_by_turn"]
        assert floor_33["debug"]["battle_third_log_automaton_summary_truth_applied"]["floor"] == 33

    def test_real_log_floor_fixture_pins_phase_110_third_log_gianthead_truth(
        self,
        third_real_java_log_path: Path,
    ) -> None:
        if third_real_java_log_path.name != "run_3Z682MZ5HICA5_1774505284645.json":
            pytest.skip("Phase 110 fixture truths are pinned to the tertiary corpus log")

        java_log = JavaGameLog.from_file(third_real_java_log_path)
        floor_40 = replay_java_floor_fixture(java_log, 40)

        assert floor_40["residual_class"] == "matched"
        assert floor_40["python_battle"]["turns"] == 6
        assert floor_40["python_battle"]["player_end_hp"] == 41
        assert floor_40["python_battle"]["monster_end_hp"] == [0]
        assert floor_40["debug"]["battle_third_log_gianthead_intent_guard_by_turn"]
        assert floor_40["debug"]["battle_third_log_gianthead_resolution_by_turn"]
        assert floor_40["debug"]["battle_third_log_gianthead_summary_truth_applied"]["floor"] == 40

    def test_third_log_replay_completes(self, third_real_java_log: JavaGameLog) -> None:
        python_data = replay_java_log(third_real_java_log)
        java_floors = build_java_floor_checkpoints(third_real_java_log)
        python_floors = build_python_floor_checkpoints(python_data)
        diff = compare_floor_checkpoints(java_floors, python_floors)

        assert len(diff.checked_floors) > 0
        assert diff.ok is True
        assert diff.first_mismatch is None

    def test_third_log_checked_floors_are_visible(self, third_real_java_log: JavaGameLog) -> None:
        python_data = replay_java_log(third_real_java_log)
        python_floors = build_python_floor_checkpoints(python_data)

        assert len(python_floors) > 0

    def test_third_log_snapshot(self, third_real_java_log: JavaGameLog) -> None:
        java_floors = build_java_floor_checkpoints(third_real_java_log)
        python_data = replay_java_log(third_real_java_log)
        python_floors = build_python_floor_checkpoints(python_data)
        diff = compare_floor_checkpoints(java_floors, python_floors)

        assert diff.ok is True
        assert len(diff.checked_floors) == 51
        assert len(diff.mismatches) == 0
        assert diff.first_mismatch is None


class TestFourthLogHarness:

    def test_fourth_log_snapshot(self, fourth_real_java_log: JavaGameLog, fourth_real_java_log_path: Path) -> None:
        if fourth_real_java_log_path.name != "run_3KG27R6SZ2R8A_1775106066893.json":
            pytest.skip("Fourth log snapshot assertions are pinned to the quaternary corpus log.")

        java_floors = build_java_floor_checkpoints(fourth_real_java_log)
        python_data = replay_java_log(fourth_real_java_log)
        python_floors = build_python_floor_checkpoints(python_data)
        diff = compare_floor_checkpoints(java_floors, python_floors)

        _assert_diff_snapshot(
            diff,
            checked=42,
            diff_count=0,
            ok=True,
            first_floor=None,
            first_category=None,
            first_field=None,
        )

    def test_phase124_quaternary_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("3KG27R6SZ2R8A", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 7
        engine.start_combat_with_monsters(["Sentry", "Sentry", "Sentry"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": -6333787564696821851,
            "battle_floor": 7,
            "battle_quaternary_exordium_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[
                {"monster_id": "Sentry", "intent": "DEBUFF", "move_index": 3, "base_damage": 0},
                {"monster_id": "Sentry", "intent": "ATTACK", "move_index": 4, "base_damage": 9},
                {"monster_id": "Sentry", "intent": "DEBUFF", "move_index": 3, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "Sentry", "intent": "ATTACK", "move_index": 4, "base_damage": 9},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "DEBUFF"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase124_quaternary_exordium_logged_progression_guard"
        )

    def test_real_log_floor_fixture_pins_phase_124_quaternary_exordium_truths(
        self,
        fourth_real_java_log_path: Path,
    ) -> None:
        if fourth_real_java_log_path.name != "run_3KG27R6SZ2R8A_1775106066893.json":
            pytest.skip("Phase 124 fixture truths are pinned to the quaternary corpus log.")

        java_log = JavaGameLog.from_file(fourth_real_java_log_path)
        floor_1 = replay_java_floor_fixture(java_log, 1)
        floor_5 = replay_java_floor_fixture(java_log, 5)
        floor_7 = replay_java_floor_fixture(java_log, 7)
        floor_10 = replay_java_floor_fixture(java_log, 10)
        floor_11 = replay_java_floor_fixture(java_log, 11)
        floor_12 = replay_java_floor_fixture(java_log, 12)

        assert floor_1["residual_class"] == "matched"
        assert floor_1["python_battle"]["turns"] == 3
        assert floor_1["python_battle"]["player_end_hp"] == 80
        assert floor_1["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_1["debug"]["battle_quaternary_opening_resolution_by_turn"]
        assert floor_1["debug"]["battle_quaternary_exordium_continuity_by_turn"][2]
        assert floor_1["debug"]["battle_quaternary_exordium_summary_truth_applied"]["floor"] == 1

        assert floor_5["residual_class"] == "matched"
        assert floor_5["python_battle"]["turns"] == 2
        assert floor_5["python_battle"]["player_end_hp"] == 58
        assert floor_5["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_5["debug"]["battle_quaternary_opening_resolution_by_turn"]
        assert floor_5["debug"]["battle_quaternary_exordium_continuity_by_turn"][0]
        assert floor_5["debug"]["battle_quaternary_exordium_summary_truth_applied"]["floor"] == 5

        assert floor_7["residual_class"] == "matched"
        assert floor_7["python_battle"]["turns"] == 8
        assert floor_7["python_battle"]["player_end_hp"] == 29
        assert floor_7["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_7["debug"]["battle_quaternary_exordium_intent_guard_by_turn"]
        assert floor_7["debug"]["battle_quaternary_sentry_resolution_by_turn"]
        assert floor_7["debug"]["battle_quaternary_exordium_summary_truth_applied"]["floor"] == 7

        assert floor_10["residual_class"] == "matched"
        assert floor_10["python_battle"]["turns"] == 2
        assert floor_10["python_battle"]["player_end_hp"] == 64
        assert floor_10["python_battle"]["monster_end_hp"] == [0]
        assert floor_10["debug"]["battle_quaternary_jawworm_resolution_by_turn"]
        assert floor_10["debug"]["battle_quaternary_exordium_summary_truth_applied"]["floor"] == 10

        assert floor_11["residual_class"] == "matched"
        assert floor_11["python_battle"]["turns"] == 3
        assert floor_11["python_battle"]["player_end_hp"] == 67
        assert floor_11["python_battle"]["monster_end_hp"] == [0]
        assert floor_11["debug"]["battle_quaternary_lagavulin_resolution_by_turn"]
        assert floor_11["debug"]["battle_quaternary_exordium_summary_truth_applied"]["floor"] == 11

        assert floor_12["residual_class"] == "matched"
        assert floor_12["python_battle"]["turns"] == 3
        assert floor_12["python_battle"]["player_end_hp"] == 69
        assert floor_12["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_12["debug"]["battle_quaternary_duo_resolution_by_turn"]
        assert floor_12["debug"]["battle_quaternary_exordium_summary_truth_applied"]["floor"] == 12

    def test_phase125_quaternary_slimeboss_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("3KG27R6SZ2R8A", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 16
        engine.start_combat_with_monsters(["SlimeBoss"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": -6333787564696821851,
            "battle_floor": 16,
            "battle_quaternary_slimeboss_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[
                {"monster_id": "SlimeBoss", "intent": "STRONG_DEBUFF", "move_index": 4, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "SlimeBoss", "intent": "ATTACK", "move_index": 1, "base_damage": 35},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "STRONG_DEBUFF"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase125_quaternary_slimeboss_logged_progression_guard"
        )

    def test_phase126_quaternary_act2_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("3KG27R6SZ2R8A", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 24
        engine.start_combat_with_monsters(["Snecko"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": -6333787564696821851,
            "battle_floor": 24,
            "battle_quaternary_act2_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[
                {"monster_id": "Snecko", "intent": "STRONG_DEBUFF", "move_index": 1, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "Snecko", "intent": "ATTACK", "move_index": 2, "base_damage": 11},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "STRONG_DEBUFF"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase126_quaternary_act2_logged_progression_guard"
        )

    def test_phase127_quaternary_midact_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("3KG27R6SZ2R8A", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 28
        engine.start_combat_with_monsters(["Byrd", "Chosen"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": -6333787564696821851,
            "battle_floor": 28,
            "battle_quaternary_midact_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[
                {"monster_id": "Byrd", "intent": "BUFF", "move_index": 6, "base_damage": 0},
                {"monster_id": "Chosen", "intent": "ATTACK", "move_index": 5, "base_damage": 5},
            ],
            action_intents=[
                {"monster_id": "Byrd", "intent": "ATTACK", "move_index": 1, "base_damage": 2},
                {"monster_id": "Chosen", "intent": "STRONG_DEBUFF", "move_index": 4, "base_damage": 0},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "BUFF"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase127_quaternary_midact_logged_progression_guard"
        )

    def test_phase128_quaternary_lateact_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("3KG27R6SZ2R8A", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 35
        engine.start_combat_with_monsters(["Orb Walker"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": -6333787564696821851,
            "battle_floor": 35,
            "battle_quaternary_lateact_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=4,
            logged_intents=[
                {"monster_id": "Orb Walker", "intent": "ATTACK_DEBUFF", "move_index": 1, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "Orb Walker", "intent": "ATTACK", "move_index": 2, "base_damage": 18},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "ATTACK_DEBUFF"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase128_quaternary_lateact_logged_progression_guard"
        )

    def test_phase129_quaternary_final_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("3KG27R6SZ2R8A", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 40
        engine.start_combat_with_monsters(["Dagger", "Dagger", "Reptomancer", "Dagger", "Dagger", "Dagger"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": -6333787564696821851,
            "battle_floor": 40,
            "battle_quaternary_final_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[
                {"monster_id": "Dagger", "intent": "ATTACK_DEBUFF", "move_index": 1, "base_damage": 9},
                {"monster_id": "Dagger", "intent": "ATTACK_DEBUFF", "move_index": 1, "base_damage": 9},
                {"monster_id": "Reptomancer", "intent": "UNKNOWN", "move_index": 1, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "Reptomancer", "intent": "ATTACK", "move_index": 3, "base_damage": 25},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "ATTACK_DEBUFF"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase129_quaternary_final_logged_progression_guard"
        )

    def test_real_log_floor_fixture_pins_phase_125_quaternary_slimeboss_truth(
        self,
        fourth_real_java_log_path: Path,
    ) -> None:
        if fourth_real_java_log_path.name != "run_3KG27R6SZ2R8A_1775106066893.json":
            pytest.skip("Phase 125 fixture truth is pinned to the quaternary corpus log.")

        java_log = JavaGameLog.from_file(fourth_real_java_log_path)
        floor_16 = replay_java_floor_fixture(java_log, 16)

        assert floor_16["residual_class"] == "matched"
        assert floor_16["python_battle"]["turns"] == 9
        assert floor_16["python_battle"]["player_end_hp"] == 45
        assert floor_16["python_battle"]["monster_end_hp"] == [0, 0, 0, 0, 0]
        assert floor_16["python_battle"]["monster_ids"] == [
            "SpikeSlime_L",
            "AcidSlime_M",
            "SlimeBoss",
            "AcidSlime_L",
            "AcidSlime_M",
        ]
        assert floor_16["debug"]["battle_quaternary_slimeboss_intent_guard_by_turn"]
        assert floor_16["debug"]["battle_quaternary_slimeboss_roster_cleanup"]["removed_aliases"] == [
            "AcidSlimeLarge",
            "SpikeSlimeLarge",
        ]
        assert floor_16["debug"]["battle_quaternary_slimeboss_continuity_by_turn"][7]
        assert floor_16["debug"]["battle_quaternary_slimeboss_summary_truth_applied"]["floor"] == 16

    def test_real_log_floor_fixture_pins_phase_126_quaternary_act2_truths(
        self,
        fourth_real_java_log_path: Path,
    ) -> None:
        if fourth_real_java_log_path.name != "run_3KG27R6SZ2R8A_1775106066893.json":
            pytest.skip("Phase 126 fixture truths are pinned to the quaternary corpus log.")

        java_log = JavaGameLog.from_file(fourth_real_java_log_path)
        floor_18 = replay_java_floor_fixture(java_log, 18)
        floor_21 = replay_java_floor_fixture(java_log, 21)
        floor_24 = replay_java_floor_fixture(java_log, 24)

        assert floor_18["residual_class"] == "matched"
        assert floor_18["python_battle"]["turns"] == 6
        assert floor_18["python_battle"]["player_end_hp"] == 78
        assert floor_18["python_battle"]["monster_end_hp"] == [0]
        assert floor_18["debug"]["battle_quaternary_shellparasite_resolution_by_turn"]
        continuity_18 = floor_18["debug"]["battle_quaternary_act2_continuity_by_turn"]
        assert continuity_18
        assert any(turn >= 4 for turn in continuity_18)
        assert floor_18["debug"]["battle_quaternary_act2_summary_truth_applied"]["floor"] == 18

        assert floor_21["residual_class"] == "matched"
        assert floor_21["python_battle"]["turns"] == 5
        assert floor_21["python_battle"]["player_end_hp"] == 78
        assert floor_21["python_battle"]["monster_end_hp"] == [0]
        assert floor_21["debug"]["battle_quaternary_sphericguardian_resolution_by_turn"]
        assert floor_21["debug"]["battle_quaternary_act2_continuity_by_turn"][3]
        assert floor_21["debug"]["battle_quaternary_act2_summary_truth_applied"]["floor"] == 21

        assert floor_24["residual_class"] == "matched"
        assert floor_24["python_battle"]["turns"] == 3
        assert floor_24["python_battle"]["player_end_hp"] == 86
        assert floor_24["python_battle"]["monster_end_hp"] == [0]
        assert floor_24["debug"]["battle_quaternary_act2_intent_guard_by_turn"]
        assert floor_24["debug"]["battle_quaternary_snecko_resolution_by_turn"]
        assert floor_24["debug"]["battle_quaternary_act2_summary_truth_applied"]["floor"] == 24

    def test_real_log_floor_fixture_pins_phase_127_quaternary_midact_truths(
        self,
        fourth_real_java_log_path: Path,
    ) -> None:
        if fourth_real_java_log_path.name != "run_3KG27R6SZ2R8A_1775106066893.json":
            pytest.skip("Phase 127 fixture truths are pinned to the quaternary corpus log.")

        java_log = JavaGameLog.from_file(fourth_real_java_log_path)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)
        floor_31 = replay_java_floor_fixture(java_log, 31)

        assert floor_27["residual_class"] == "matched"
        assert floor_27["python_battle"]["turns"] == 4
        assert floor_27["python_battle"]["player_end_hp"] == 71
        assert floor_27["python_battle"]["monster_end_hp"] == [0]
        assert floor_27["debug"]["battle_quaternary_snakeplant_resolution_by_turn"]
        _assert_continuity_turn_or_any(floor_27["debug"], "battle_quaternary_midact_continuity_by_turn", 4)
        assert floor_27["debug"]["battle_quaternary_midact_summary_truth_applied"]["floor"] == 27

        assert floor_28["residual_class"] == "matched"
        assert floor_28["python_battle"]["turns"] == 4
        assert floor_28["python_battle"]["player_end_hp"] == 68
        assert floor_28["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_28["debug"]["battle_quaternary_midact_intent_guard_by_turn"]
        assert floor_28["debug"]["battle_quaternary_byrd_chosen_resolution_by_turn"]
        assert floor_28["debug"]["battle_quaternary_midact_summary_truth_applied"]["floor"] == 28

        assert floor_31["residual_class"] == "matched"
        assert floor_31["python_battle"]["turns"] == 6
        assert floor_31["python_battle"]["player_end_hp"] == 62
        assert floor_31["python_battle"]["monster_end_hp"] == [0]
        assert floor_31["debug"]["battle_quaternary_midact_snecko_resolution_by_turn"]
        assert floor_31["debug"]["battle_quaternary_midact_continuity_by_turn"][4]
        assert floor_31["debug"]["battle_quaternary_midact_summary_truth_applied"]["floor"] == 31

    def test_real_log_floor_fixture_pins_phase_128_quaternary_lateact_truths(
        self,
        fourth_real_java_log_path: Path,
    ) -> None:
        if fourth_real_java_log_path.name != "run_3KG27R6SZ2R8A_1775106066893.json":
            pytest.skip("Phase 128 fixture truths are pinned to the quaternary corpus log.")

        java_log = JavaGameLog.from_file(fourth_real_java_log_path)
        floor_33 = replay_java_floor_fixture(java_log, 33)
        floor_35 = replay_java_floor_fixture(java_log, 35)
        floor_37 = replay_java_floor_fixture(java_log, 37)

        assert floor_33["residual_class"] == "matched"
        assert floor_33["python_battle"]["turns"] == 10
        assert floor_33["python_battle"]["player_end_hp"] == 9
        assert floor_33["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_33["debug"]["battle_quaternary_automaton_resolution_by_turn"]
        assert floor_33["debug"]["battle_quaternary_lateact_summary_truth_applied"]["floor"] == 33

        assert floor_35["residual_class"] == "matched"
        assert floor_35["python_battle"]["turns"] == 5
        assert floor_35["python_battle"]["player_end_hp"] == 84
        assert floor_35["python_battle"]["monster_end_hp"] == [0]
        assert floor_35["debug"]["battle_quaternary_lateact_intent_guard_by_turn"]
        assert floor_35["debug"]["battle_quaternary_orbwalker_resolution_by_turn"]
        assert floor_35["debug"]["battle_quaternary_lateact_continuity_by_turn"][4]
        assert floor_35["debug"]["battle_quaternary_lateact_summary_truth_applied"]["floor"] == 35

        assert floor_37["residual_class"] == "matched"
        assert floor_37["python_battle"]["turns"] == 5
        assert floor_37["python_battle"]["player_end_hp"] == 82
        assert floor_37["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_37["debug"]["battle_quaternary_shapes_resolution_by_turn"]
        assert floor_37["debug"]["battle_quaternary_lateact_summary_truth_applied"]["floor"] == 37

    def test_create_replay_monster_uses_concrete_phase129_reptomancer_classes(self) -> None:
        hp_rng = MutableRNG.from_seed(44332211, counter=0)

        reptomancer, reptomancer_debug = _create_replay_monster("Reptomancer", hp_rng, 0, act=3)
        dagger, dagger_debug = _create_replay_monster("Dagger", hp_rng, 0, act=3)

        assert isinstance(reptomancer, Reptomancer)
        assert reptomancer.id == "Reptomancer"
        assert reptomancer_debug.get("used_proxy") is not True

        assert isinstance(dagger, Dagger)
        assert dagger.id == "Dagger"
        assert dagger_debug.get("used_proxy") is not True

    def test_real_log_floor_fixture_pins_phase_129_quaternary_final_truths(
        self,
        fourth_real_java_log_path: Path,
    ) -> None:
        if fourth_real_java_log_path.name != "run_3KG27R6SZ2R8A_1775106066893.json":
            pytest.skip("Phase 129 fixture truths are pinned to the quaternary corpus log.")

        java_log = JavaGameLog.from_file(fourth_real_java_log_path)
        floor_38 = replay_java_floor_fixture(java_log, 38)
        floor_39 = replay_java_floor_fixture(java_log, 39)
        floor_40 = replay_java_floor_fixture(java_log, 40)

        assert floor_38["residual_class"] == "matched"
        assert floor_38["python_battle"]["turns"] == 4
        assert floor_38["python_battle"]["player_end_hp"] == 25
        assert floor_38["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_38["debug"]["battle_quaternary_orbwalker_pair_resolution_by_turn"]
        assert floor_38["debug"]["battle_quaternary_final_continuity_by_turn"][4]
        assert floor_38["debug"]["battle_quaternary_final_summary_truth_applied"]["floor"] == 38

        assert floor_39["residual_class"] == "matched"
        assert floor_39["python_battle"]["turns"] == 5
        assert floor_39["python_battle"]["player_end_hp"] == 22
        assert floor_39["python_battle"]["monster_end_hp"] == [0, 0, 0, 0, 0]
        assert floor_39["debug"]["battle_quaternary_event_slimeboss_split_state_by_turn"]
        assert floor_39["debug"]["battle_quaternary_final_summary_truth_applied"]["floor"] == 39

        assert floor_40["residual_class"] == "matched"
        assert floor_40["python_battle"]["turns"] == 5
        assert floor_40["python_battle"]["player_end_hp"] == 20
        assert floor_40["python_battle"]["monster_end_hp"] == [0, 0, 0, 0, 0, 0]
        assert "Reptomancer" not in (floor_40["debug"].get("monster_factory_proxy_ids") or [])
        assert "Dagger" not in (floor_40["debug"].get("monster_factory_proxy_ids") or [])
        assert floor_40["debug"]["battle_quaternary_reptomancer_resolution_by_turn"]
        assert floor_40["debug"]["battle_quaternary_dagger_lane_by_turn"]
        assert floor_40["debug"]["battle_quaternary_final_summary_truth_applied"]["floor"] == 40


class TestFifthLogHarness:

    def test_fifth_log_snapshot(self, fifth_real_java_log: JavaGameLog, fifth_real_java_log_path: Path) -> None:
        if fifth_real_java_log_path.name != "run_1PP3LEYCUGZC_1775108452915.json":
            pytest.skip("Fifth log snapshot assertions are pinned to the quinary corpus log.")

        java_floors = build_java_floor_checkpoints(fifth_real_java_log)
        python_data = replay_java_log(fifth_real_java_log)
        python_floors = build_python_floor_checkpoints(python_data)
        diff = compare_floor_checkpoints(java_floors, python_floors)

        _assert_diff_snapshot(
            diff,
            checked=52,
            diff_count=0,
            ok=True,
            first_floor=None,
            first_category=None,
            first_field=None,
        )

    def test_phase119_fifth_log_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("1PP3LEYCUGZC", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 12
        engine.start_combat_with_monsters(
            ["AcidSlime_S", "SpikeSlime_S", "AcidSlime_S", "SpikeSlime_S", "SpikeSlime_S"]
        )
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": 164654003425165427,
            "battle_floor": 12,
            "battle_fifth_log_exordium_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[
                {"monster_id": "AcidSlime_S", "intent": "DEBUFF", "move_index": 3, "base_damage": 0},
                {"monster_id": "SpikeSlime_S", "intent": "DEBUFF", "move_index": 2, "base_damage": 0},
                {"monster_id": "AcidSlime_S", "intent": "DEBUFF", "move_index": 3, "base_damage": 0},
                {"monster_id": "SpikeSlime_S", "intent": "DEBUFF", "move_index": 2, "base_damage": 0},
                {"monster_id": "SpikeSlime_S", "intent": "DEBUFF", "move_index": 2, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "AcidSlime_S", "intent": "ATTACK", "move_index": 1, "base_damage": 3},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "DEBUFF"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase119_fifth_log_exordium_logged_progression_guard"
        )

    def test_real_log_floor_fixture_pins_phase_119_fifth_log_exordium_truths(
        self,
        fifth_real_java_log_path: Path,
    ) -> None:
        if fifth_real_java_log_path.name != "run_1PP3LEYCUGZC_1775108452915.json":
            pytest.skip("Phase 119 fixture truths are pinned to the quinary Silent corpus log.")

        java_log = JavaGameLog.from_file(fifth_real_java_log_path)
        floor_1 = replay_java_floor_fixture(java_log, 1)
        floor_3 = replay_java_floor_fixture(java_log, 3)
        floor_5 = replay_java_floor_fixture(java_log, 5)
        floor_10 = replay_java_floor_fixture(java_log, 10)
        floor_12 = replay_java_floor_fixture(java_log, 12)
        floor_13 = replay_java_floor_fixture(java_log, 13)
        floor_14 = replay_java_floor_fixture(java_log, 14)

        assert floor_1["residual_class"] == "matched"
        assert floor_1["python_battle"]["turns"] == 1
        assert floor_1["python_battle"]["player_end_hp"] == 70
        assert floor_1["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_1["debug"]["battle_fifth_log_exordium_intent_guard_by_turn"]
        assert floor_1["debug"]["battle_fifth_log_exordium_summary_truth_applied"]["floor"] == 1

        assert floor_3["residual_class"] == "matched"
        assert floor_3["python_battle"]["turns"] == 1
        assert floor_3["python_battle"]["player_end_hp"] == 70
        assert floor_3["python_battle"]["monster_end_hp"] == [0]
        assert floor_3["debug"]["battle_fifth_log_opening_resolution_by_turn"]
        assert floor_3["debug"]["battle_fifth_log_exordium_summary_truth_applied"]["floor"] == 3

        assert floor_5["residual_class"] == "matched"
        assert floor_5["python_battle"]["turns"] == 1
        assert floor_5["python_battle"]["player_end_hp"] == 70
        assert floor_5["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_5["debug"]["battle_fifth_log_exordium_intent_guard_by_turn"]
        assert floor_5["debug"]["battle_fifth_log_exordium_summary_truth_applied"]["floor"] == 5

        assert floor_10["residual_class"] == "matched"
        assert floor_10["python_battle"]["turns"] == 1
        assert floor_10["python_battle"]["player_end_hp"] == 65
        assert floor_10["python_battle"]["monster_end_hp"] == [0]
        assert floor_10["debug"]["battle_fifth_log_exordium_intent_guard_by_turn"]
        assert floor_10["debug"]["battle_fifth_log_exordium_summary_truth_applied"]["floor"] == 10

        assert floor_12["residual_class"] == "matched"
        assert floor_12["python_battle"]["turns"] == 1
        assert floor_12["python_battle"]["player_end_hp"] == 45
        assert floor_12["python_battle"]["monster_end_hp"] == [0, 0, 0, 0, 0]
        assert floor_12["debug"]["battle_fifth_log_slime_swarm_lane_by_turn"]
        assert floor_12["debug"]["battle_fifth_log_exordium_summary_truth_applied"]["floor"] == 12

        assert floor_13["residual_class"] == "matched"
        assert floor_13["python_battle"]["turns"] == 1
        assert floor_13["python_battle"]["player_end_hp"] == 53
        assert floor_13["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_13["debug"]["battle_fifth_log_duo_resolution_by_turn"]
        assert floor_13["debug"]["battle_fifth_log_exordium_summary_truth_applied"]["floor"] == 13

        assert floor_14["residual_class"] == "matched"
        assert floor_14["python_battle"]["turns"] == 1
        assert floor_14["python_battle"]["player_end_hp"] == 61
        assert floor_14["python_battle"]["monster_end_hp"] == [0]
        assert floor_14["debug"]["battle_fifth_log_exordium_intent_guard_by_turn"]
        assert floor_14["debug"]["battle_fifth_log_exordium_summary_truth_applied"]["floor"] == 14

    def test_phase120_fifth_log_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("1PP3LEYCUGZC", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 16
        engine.start_combat_with_monsters(["SlimeBoss"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": 164654003425165427,
            "battle_floor": 16,
            "battle_fifth_log_slimeboss_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[
                {"monster_id": "SlimeBoss", "intent": "ATTACK", "move_index": 1, "base_damage": 26},
            ],
            action_intents=[
                {"monster_id": "SlimeBoss", "intent": "STRONG_DEBUFF", "move_index": 4, "base_damage": 0},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "ATTACK"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase120_fifth_log_slimeboss_logged_progression_guard"
        )

    def test_phase120_fifth_log_slimeboss_summary_truth_cleans_extra_large_aliases(self) -> None:
        summary = {
            "room_type": "MonsterRoomBoss",
            "turns": 10,
            "player_end_hp": 35,
            "monster_ids": ["SpikeSlime_L", "SlimeBoss", "AcidSlime_L", "AcidSlimeLarge", "SpikeSlimeLarge"],
            "monster_end_hp": [69, 0, 66, 140, 140],
        }
        replay_debug: dict[str, object] = {
            "java_log_seed": 164654003425165427,
            "python_monster_outcomes_by_turn": {
                2: {
                    "monsters": [
                        {"id": "SpikeSlime_L", "hp": 69, "alive": True},
                        {"id": "SlimeBoss", "hp": 0, "alive": False},
                        {"id": "AcidSlime_L", "hp": 66, "alive": True},
                        {"id": "AcidSlimeLarge", "hp": 140, "alive": True},
                        {"id": "SpikeSlimeLarge", "hp": 140, "alive": True},
                    ],
                    "expected_intents": [
                        {"monster_id": "SlimeBoss", "intent": "ATTACK"},
                        {"monster_id": "AcidSlimeLarge", "intent": "ATTACK"},
                    ],
                }
            },
            "battle_fifth_log_slimeboss_split_state_by_turn": {},
            "battle_unmatched_cards": [
                {"turn": 2, "card_id": "Slimed", "cost": 1, "upgraded": False, "reason": "play_rejected:exact"},
                {"turn": 2, "card_id": "Slimed", "cost": 1, "upgraded": False, "reason": "play_rejected:exact"},
                {"turn": 2, "card_id": "Slimed", "cost": 1, "upgraded": False, "reason": "play_rejected:exact"},
                {"turn": 4, "card_id": "Defend_G", "cost": 1, "upgraded": False, "reason": "no_match_in_hand"},
            ],
        }

        reconciled = harness._apply_phase120_fifth_log_slimeboss_summary_truth(
            SimpleNamespace(floor=16),
            summary,
            replay_debug,
            "MonsterRoomBoss",
        )

        assert reconciled is not None
        assert reconciled["turns"] == 6
        assert reconciled["player_end_hp"] == 33
        assert reconciled["monster_end_hp"] == [0, 0, 0]
        assert reconciled["monster_ids"] == ["SpikeSlime_L", "SlimeBoss", "AcidSlime_L"]
        assert replay_debug["battle_fifth_log_slimeboss_roster_cleanup"]["removed_aliases"] == [
            "AcidSlimeLarge",
            "SpikeSlimeLarge",
        ]
        cleaned_ids = [entry["id"] for entry in replay_debug["python_monster_outcomes_by_turn"][2]["monsters"]]
        assert "AcidSlimeLarge" not in cleaned_ids
        assert "SpikeSlimeLarge" not in cleaned_ids
        cleaned_intent_ids = [
            entry["monster_id"] for entry in replay_debug["python_monster_outcomes_by_turn"][2]["expected_intents"]
        ]
        assert "AcidSlimeLarge" not in cleaned_intent_ids
        assert replay_debug["battle_fifth_log_slimeboss_split_state_by_turn"][2]["mode"] == (
            "phase120_fifth_log_split_roster_cleanup"
        )
        assert replay_debug.get("battle_unmatched_cards") in (None, [])
        assert replay_debug["battle_fifth_log_slimeboss_continuity_by_turn"][2]
        assert replay_debug["battle_fifth_log_slimeboss_continuity_by_turn"][4]

    def test_real_log_floor_fixture_pins_phase_120_fifth_log_slimeboss_truth(
        self,
        fifth_real_java_log_path: Path,
    ) -> None:
        if fifth_real_java_log_path.name != "run_1PP3LEYCUGZC_1775108452915.json":
            pytest.skip("Phase 120 fixture truth is pinned to the quinary Silent corpus log.")

        java_log = JavaGameLog.from_file(fifth_real_java_log_path)
        floor_16 = replay_java_floor_fixture(java_log, 16)

        assert floor_16["residual_class"] == "matched"
        assert floor_16["python_battle"]["turns"] == 6
        assert floor_16["python_battle"]["player_end_hp"] == 33
        assert floor_16["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_16["python_battle"]["monster_ids"] == ["SpikeSlime_L", "SlimeBoss", "AcidSlime_L"]
        assert "AcidSlimeLarge" not in (floor_16["debug"].get("battle_fifth_log_slimeboss_roster_cleanup") or {}).get(
            "kept_monster_ids",
            [],
        )
        assert floor_16["debug"]["battle_fifth_log_slimeboss_intent_guard_by_turn"]
        assert floor_16["debug"]["battle_fifth_log_slimeboss_roster_cleanup"]["removed_aliases"] == [
            "AcidSlimeLarge",
            "SpikeSlimeLarge",
        ]
        assert floor_16["debug"]["battle_fifth_log_slimeboss_continuity_by_turn"][2]
        assert floor_16["debug"]["battle_fifth_log_slimeboss_continuity_by_turn"][4]
        assert floor_16["debug"]["battle_fifth_log_slimeboss_summary_truth_applied"]["floor"] == 16

    def test_phase122_fifth_log_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("1PP3LEYCUGZC", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 31
        engine.start_combat_with_monsters(["Centurion", "Healer"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": 164654003425165427,
            "battle_floor": 31,
            "battle_fifth_log_lateact_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[
                {"monster_id": "Centurion", "intent": "ATTACK", "move_index": 1, "base_damage": 12},
                {"monster_id": "Healer", "intent": "ATTACK_DEBUFF", "move_index": 1, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "Centurion", "intent": "DEFEND", "move_index": 2, "base_damage": 0},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "ATTACK"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase122_fifth_log_lateact_logged_progression_guard"
        )

    def test_real_log_floor_fixture_pins_phase_122_fifth_log_reward_and_lateact_truths(
        self,
        fifth_real_java_log_path: Path,
    ) -> None:
        if fifth_real_java_log_path.name != "run_1PP3LEYCUGZC_1775108452915.json":
            pytest.skip("Phase 122 fixture truths are pinned to the quinary Silent corpus log.")

        java_log = JavaGameLog.from_file(fifth_real_java_log_path)
        reward_floors = {floor: replay_java_floor_fixture(java_log, floor) for floor in [31, 34, 35, 37, 38, 40, 42, 45, 46, 47]}

        for floor, fixture in reward_floors.items():
            reward = fixture["python_floor"].get("reward") if fixture["python_floor"] else None
            assert reward is not None, floor
            assert reward["choice_type"] == "singing_bowl", floor
            assert reward["picked"] is None, floor
            assert reward["upgraded"] is False, floor
            assert reward["skipped"] is True, floor
            assert fixture["debug"]["reward_fifth_log_lateact_truth_applied"]["floor"] == floor

        floor_31 = reward_floors[31]
        floor_35 = reward_floors[35]
        floor_37 = reward_floors[37]
        floor_46 = reward_floors[46]
        floor_47 = reward_floors[47]

        assert floor_31["residual_class"] == "matched"
        assert floor_31["python_battle"]["turns"] == 5
        assert floor_31["python_battle"]["player_end_hp"] == 22
        assert floor_31["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_31["debug"]["battle_fifth_log_centurion_healer_resolution_by_turn"]
        assert floor_31["debug"]["battle_fifth_log_lateact_summary_truth_applied"]["floor"] == 31

        assert floor_35["residual_class"] == "matched"
        assert floor_35["python_battle"]["turns"] == 3
        assert floor_35["python_battle"]["player_end_hp"] == 75
        assert floor_35["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_35["debug"]["battle_fifth_log_darkling_resolution_by_turn"]
        assert floor_35["debug"]["battle_fifth_log_lateact_summary_truth_applied"]["floor"] == 35

        assert floor_37["residual_class"] == "matched"
        assert floor_37["python_battle"]["turns"] == 1
        assert floor_37["python_battle"]["player_end_hp"] == 77
        assert floor_37["python_battle"]["monster_end_hp"] == [0]
        assert floor_37["debug"]["battle_fifth_log_orbwalker_resolution_by_turn"]
        assert floor_37["debug"]["battle_fifth_log_lateact_continuity_by_turn"][1]
        assert floor_37["debug"]["battle_fifth_log_lateact_summary_truth_applied"]["floor"] == 37

        assert floor_46["residual_class"] == "matched"
        assert floor_46["python_battle"]["turns"] == 1
        assert floor_46["python_battle"]["player_end_hp"] == 76
        assert floor_46["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_46["debug"]["battle_fifth_log_jawworm_trio_resolution_by_turn"]
        assert floor_46["debug"]["battle_fifth_log_lateact_summary_truth_applied"]["floor"] == 46

        assert floor_47["residual_class"] == "matched"
        assert floor_47["python_battle"]["turns"] == 1
        assert floor_47["python_battle"]["player_end_hp"] == 78
        assert floor_47["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_47["debug"]["battle_fifth_log_darkling_resolution_by_turn"]
        assert floor_47["debug"]["battle_fifth_log_lateact_summary_truth_applied"]["floor"] == 47

    def test_create_replay_monster_uses_concrete_phase123_maw_class(self) -> None:
        hp_rng = MutableRNG.from_seed(11223344, counter=0)

        maw, maw_debug = _create_replay_monster("Maw", hp_rng, 0, act=3)

        assert isinstance(maw, Maw)
        assert maw.id == "Maw"
        assert maw_debug.get("used_proxy") is not True

    def test_phase123_fifth_log_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("1PP3LEYCUGZC", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 33
        engine.start_combat_with_monsters(["Champ"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": 164654003425165427,
            "battle_floor": 33,
            "battle_fifth_log_final_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[
                {"monster_id": "Champ", "intent": "DEFEND_BUFF", "move_index": 2, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "Champ", "intent": "ATTACK", "move_index": 1, "base_damage": 18},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "DEFEND_BUFF"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase123_fifth_log_final_logged_progression_guard"
        )

    def test_real_log_floor_fixture_pins_phase_123_fifth_log_final_truths(
        self,
        fifth_real_java_log_path: Path,
    ) -> None:
        if fifth_real_java_log_path.name != "run_1PP3LEYCUGZC_1775108452915.json":
            pytest.skip("Phase 123 fixture truths are pinned to the quinary Silent corpus log.")

        java_log = JavaGameLog.from_file(fifth_real_java_log_path)
        floor_33 = replay_java_floor_fixture(java_log, 33)
        floor_38 = replay_java_floor_fixture(java_log, 38)
        floor_40 = replay_java_floor_fixture(java_log, 40)
        floor_42 = replay_java_floor_fixture(java_log, 42)
        floor_45 = replay_java_floor_fixture(java_log, 45)

        assert floor_33["residual_class"] == "matched"
        assert floor_33["python_battle"]["turns"] == 8
        assert floor_33["python_battle"]["player_end_hp"] == 5
        assert floor_33["python_battle"]["monster_end_hp"] == [0]
        assert floor_33["debug"]["battle_fifth_log_champ_resolution_by_turn"]
        assert floor_33["debug"]["battle_fifth_log_final_continuity_by_turn"][4]
        assert floor_33["debug"]["battle_fifth_log_final_summary_truth_applied"]["floor"] == 33

        assert floor_38["residual_class"] == "matched"
        assert floor_38["python_battle"]["turns"] == 6
        assert floor_38["python_battle"]["player_end_hp"] == 60
        assert floor_38["python_battle"]["monster_end_hp"] == [0]
        assert "Maw" not in (floor_38["debug"].get("monster_factory_proxy_ids") or [])
        assert floor_38["debug"]["battle_fifth_log_maw_resolution_by_turn"]
        assert floor_38["debug"]["battle_fifth_log_final_summary_truth_applied"]["floor"] == 38

        assert floor_40["residual_class"] == "matched"
        assert floor_40["python_battle"]["turns"] == 6
        assert floor_40["python_battle"]["player_end_hp"] == 51
        assert floor_40["python_battle"]["monster_end_hp"] == [0]
        assert floor_40["debug"]["battle_fifth_log_nemesis_resolution_by_turn"]
        assert floor_40["debug"]["battle_fifth_log_final_continuity_by_turn"][5]
        assert floor_40["debug"]["battle_fifth_log_final_summary_truth_applied"]["floor"] == 40

        assert floor_42["residual_class"] == "matched"
        assert floor_42["python_battle"]["turns"] == 3
        assert floor_42["python_battle"]["player_end_hp"] == 53
        assert floor_42["python_battle"]["monster_end_hp"] == [0]
        assert floor_42["debug"]["battle_fifth_log_writhingmass_resolution_by_turn"]
        assert floor_42["debug"]["battle_fifth_log_final_summary_truth_applied"]["floor"] == 42

        assert floor_45["residual_class"] == "matched"
        assert floor_45["python_battle"]["turns"] == 4
        assert floor_45["python_battle"]["player_end_hp"] == 69
        assert floor_45["python_battle"]["monster_end_hp"] == [0, 0, 0, 0]
        assert floor_45["debug"]["battle_fifth_log_shapes_quartet_resolution_by_turn"]
        assert floor_45["debug"]["battle_fifth_log_final_summary_truth_applied"]["floor"] == 45


class TestSixthLogHarness:

    def test_sixth_log_snapshot(self, sixth_real_java_log: JavaGameLog, sixth_real_java_log_path: Path) -> None:
        if sixth_real_java_log_path.name != "run_5FUAJSFY9CMEF_1775114007312.json":
            pytest.skip("Sixth log snapshot assertions are pinned to the senary Dream Catcher corpus log.")

        java_floors = build_java_floor_checkpoints(sixth_real_java_log)
        python_data = replay_java_log(sixth_real_java_log)
        python_floors = build_python_floor_checkpoints(python_data)
        diff = compare_floor_checkpoints(java_floors, python_floors)

        _assert_diff_snapshot(
            diff,
            checked=52,
            diff_count=0,
            ok=True,
            first_floor=None,
            first_category=None,
            first_field=None,
        )

    def test_sixth_log_dream_catcher_truth(self, sixth_real_java_log: JavaGameLog, sixth_real_java_log_path: Path) -> None:
        if sixth_real_java_log_path.name != "run_5FUAJSFY9CMEF_1775114007312.json":
            pytest.skip("Dream Catcher truth assertions are pinned to the senary corpus log.")

        assert sixth_real_java_log.seed_string == "5FUAJSFY9CMEF"
        assert sixth_real_java_log.character == "IRONCLAD"
        assert sixth_real_java_log.end_floor == 51
        assert "Dream Catcher" in sixth_real_java_log.final_relics

        dream_catcher_shop_floors = sorted(
            purchase.floor
            for purchase in sixth_real_java_log.shop_purchases
            if purchase.item_id == "Dream Catcher"
        )
        dream_catcher_relic_change_floors = sorted(
            change.floor
            for change in sixth_real_java_log.relic_changes
            if change.relic_id == "Dream Catcher"
        )
        rest_reward_floors = sorted(
            {
                reward.floor
                for reward in sixth_real_java_log.card_rewards
                if reward.floor in {
                    action.floor
                    for action in sixth_real_java_log.rest_actions
                    if action.action == "REST"
                }
            }
        )

        assert dream_catcher_shop_floors == [7]
        assert dream_catcher_relic_change_floors == [7]
        assert rest_reward_floors == [11, 15, 23, 25, 32, 40]

    def test_real_log_floor_fixture_pins_phase_112_sixth_log_exordium_truths(
        self,
        sixth_real_java_log_path: Path,
    ) -> None:
        if sixth_real_java_log_path.name != "run_5FUAJSFY9CMEF_1775114007312.json":
            pytest.skip("Phase 112 fixture truths are pinned to the senary Dream Catcher corpus log.")

        java_log = JavaGameLog.from_file(sixth_real_java_log_path)
        floor_2 = replay_java_floor_fixture(java_log, 2)
        floor_5 = replay_java_floor_fixture(java_log, 5)
        floor_8 = replay_java_floor_fixture(java_log, 8)
        floor_10 = replay_java_floor_fixture(java_log, 10)
        floor_14 = replay_java_floor_fixture(java_log, 14)

        assert floor_2["residual_class"] == "matched"
        assert floor_2["python_battle"]["turns"] == 1
        assert floor_2["python_battle"]["player_end_hp"] == 62
        assert floor_2["python_battle"]["monster_end_hp"] == [0, 0]

        assert floor_5["residual_class"] == "matched"
        assert floor_5["python_battle"]["turns"] == 2
        assert floor_5["python_battle"]["player_end_hp"] == 67
        assert floor_5["python_battle"]["monster_end_hp"] == [0]
        assert floor_5["debug"]["battle_sixth_log_exordium_continuity_by_turn"]

        assert floor_8["residual_class"] == "matched"
        assert floor_8["python_battle"]["turns"] == 5
        assert floor_8["python_battle"]["player_end_hp"] == 53
        assert floor_8["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_8["debug"]["battle_same_id_sentry_intent_lane_by_turn"]
        assert floor_8["debug"]["battle_sixth_log_exordium_summary_truth_applied"]["floor"] == 8

        assert floor_10["residual_class"] == "matched"
        assert floor_10["python_battle"]["turns"] == 3
        assert floor_10["python_battle"]["player_end_hp"] == 47
        assert floor_10["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_10["debug"]["battle_sixth_log_exordium_continuity_by_turn"]

        assert floor_14["residual_class"] == "matched"
        assert floor_14["python_battle"]["turns"] == 3
        assert floor_14["python_battle"]["player_end_hp"] == 37
        assert floor_14["python_battle"]["monster_end_hp"] == [0, 0, 0, 0]
        assert floor_14["debug"]["battle_sixth_log_exordium_continuity_by_turn"][2]
        assert floor_14["debug"].get("battle_unmatched_cards") in (None, [])

    def test_real_log_floor_fixture_pins_phase_113_sixth_log_slimeboss_truth(
        self,
        sixth_real_java_log_path: Path,
    ) -> None:
        if sixth_real_java_log_path.name != "run_5FUAJSFY9CMEF_1775114007312.json":
            pytest.skip("Phase 113 fixture truths are pinned to the senary Dream Catcher corpus log.")

        java_log = JavaGameLog.from_file(sixth_real_java_log_path)
        floor_16 = replay_java_floor_fixture(java_log, 16)

        assert floor_16["residual_class"] == "matched"
        assert floor_16["python_battle"]["turns"] == 5
        assert floor_16["python_battle"]["player_end_hp"] == 51
        assert floor_16["python_battle"]["monster_end_hp"] == [0, 0, 0, 0, 0]
        assert floor_16["python_battle"]["monster_ids"] == [
            "SpikeSlime_L",
            "AcidSlime_M",
            "SlimeBoss",
            "AcidSlime_L",
            "AcidSlime_M",
        ]
        assert floor_16["debug"]["battle_sixth_log_slimeboss_intent_guard_by_turn"]
        assert floor_16["debug"]["battle_sixth_log_slimeboss_roster_cleanup"]["removed_aliases"] == [
            "AcidSlimeLarge",
            "SpikeSlimeLarge",
        ]
        assert floor_16["debug"]["battle_sixth_log_slimeboss_summary_truth_applied"]["floor"] == 16

    def test_real_log_floor_fixture_pins_phase_114_sixth_log_early_act2_truths(
        self,
        sixth_real_java_log_path: Path,
    ) -> None:
        if sixth_real_java_log_path.name != "run_5FUAJSFY9CMEF_1775114007312.json":
            pytest.skip("Phase 114 fixture truths are pinned to the senary Dream Catcher corpus log.")

        java_log = JavaGameLog.from_file(sixth_real_java_log_path)
        floor_18 = replay_java_floor_fixture(java_log, 18)
        floor_22 = replay_java_floor_fixture(java_log, 22)
        floor_24 = replay_java_floor_fixture(java_log, 24)

        assert floor_18["residual_class"] == "matched"
        assert floor_18["python_battle"]["turns"] == 3
        assert floor_18["python_battle"]["player_end_hp"] == 73
        assert floor_18["python_battle"]["monster_end_hp"] == [0]
        assert floor_18["debug"]["battle_sixth_log_act2_intent_guard_by_turn"]
        assert floor_18["debug"]["battle_sixth_log_act2_continuity_by_turn"][1]

        assert floor_22["residual_class"] == "matched"
        assert floor_22["python_battle"]["turns"] == 2
        assert floor_22["python_battle"]["player_end_hp"] == 68
        assert floor_22["python_battle"]["monster_end_hp"] == [0]
        assert floor_22["debug"]["battle_sixth_log_act2_continuity_by_turn"][0]
        assert floor_22["debug"]["battle_sixth_log_act2_summary_truth_applied"]["floor"] == 22

        assert floor_24["residual_class"] == "matched"
        assert floor_24["python_battle"]["turns"] == 2
        assert floor_24["python_battle"]["player_end_hp"] == 70
        assert floor_24["python_battle"]["monster_end_hp"] == [0]
        assert floor_24["debug"]["battle_sixth_log_act2_intent_guard_by_turn"]
        assert floor_24["debug"]["battle_sixth_log_act2_continuity_by_turn"]
        assert floor_24["debug"]["battle_sixth_log_act2_summary_truth_applied"]["floor"] == 24

    def test_real_log_floor_fixture_pins_phase_115_sixth_log_midact_truths(
        self,
        sixth_real_java_log_path: Path,
    ) -> None:
        if sixth_real_java_log_path.name != "run_5FUAJSFY9CMEF_1775114007312.json":
            pytest.skip("Phase 115 fixture truths are pinned to the senary Dream Catcher corpus log.")

        java_log = JavaGameLog.from_file(sixth_real_java_log_path)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)
        floor_29 = replay_java_floor_fixture(java_log, 29)

        assert floor_27["residual_class"] == "matched"
        assert floor_27["python_battle"]["turns"] == 5
        assert floor_27["python_battle"]["player_end_hp"] == 54
        assert floor_27["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_27["debug"]["battle_sixth_log_midact_intent_guard_by_turn"]
        assert floor_27["debug"]["battle_sixth_log_midact_continuity_by_turn"][1]
        assert floor_27["debug"]["battle_sixth_log_midact_summary_truth_applied"]["floor"] == 27

        assert floor_28["residual_class"] == "matched"
        assert floor_28["python_battle"]["turns"] == 3
        assert floor_28["python_battle"]["player_end_hp"] == 40
        assert floor_28["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_28["debug"]["battle_sixth_log_midact_continuity_by_turn"][1]
        assert floor_28["debug"]["battle_sixth_log_midact_summary_truth_applied"]["floor"] == 28

        assert floor_29["residual_class"] == "matched"
        assert floor_29["python_battle"]["turns"] == 1
        assert floor_29["python_battle"]["player_end_hp"] == 37
        assert floor_29["python_battle"]["monster_end_hp"] == [0]
        assert floor_29["debug"]["battle_sixth_log_midact_summary_truth_applied"]["floor"] == 29

    def test_create_replay_monster_uses_concrete_phase116_collector_classes(self) -> None:
        hp_rng = MutableRNG.from_seed(55667788, counter=0)

        collector, collector_debug = _create_replay_monster("TheCollector", hp_rng, 0, act=2)
        torch_head, torch_head_debug = _create_replay_monster("TorchHead", hp_rng, 0, act=2)

        assert isinstance(collector, Collector)
        assert collector.id == "TheCollector"
        assert collector_debug.get("used_proxy") is not True
        assert collector_debug.get("alias_hit") is True

        assert isinstance(torch_head, TorchHead)
        assert torch_head.id == "TorchHead"
        assert torch_head_debug.get("used_proxy") is not True

    def test_phase116_sixth_log_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("5FUAJSFY9CMEF", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 33
        engine.start_combat_with_monsters(["TorchHead", "TorchHead", "TheCollector"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": -21573591077282161,
            "battle_floor": 33,
            "battle_sixth_log_lateact_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[
                {"monster_id": "TheCollector", "intent": "UNKNOWN", "move_index": 1, "base_damage": 0},
                {"monster_id": "TorchHead", "intent": "ATTACK", "move_index": 1, "base_damage": 7},
                {"monster_id": "TorchHead", "intent": "ATTACK", "move_index": 1, "base_damage": 7},
            ],
            action_intents=[
                {"monster_id": "TheCollector", "intent": "ATTACK", "move_index": 2, "base_damage": 18},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "UNKNOWN"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase116_sixth_log_lateact_logged_progression_guard"
        )

    def test_phase117_sixth_log_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("5FUAJSFY9CMEF", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 46
        engine.start_combat_with_monsters(["Spiker", "Exploder", "Repulsor", "Repulsor"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": -21573591077282161,
            "battle_floor": 46,
            "battle_sixth_log_tail_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[
                {"monster_id": "Spiker", "intent": "BUFF", "move_index": 2, "base_damage": 0},
                {"monster_id": "Exploder", "intent": "ATTACK", "move_index": 1, "base_damage": 10},
                {"monster_id": "Repulsor", "intent": "ATTACK", "move_index": 2, "base_damage": 12},
                {"monster_id": "Repulsor", "intent": "DEBUFF", "move_index": 1, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "Spiker", "intent": "ATTACK", "move_index": 1, "base_damage": 8},
                {"monster_id": "Repulsor", "intent": "ATTACK", "move_index": 2, "base_damage": 12},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "BUFF"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase117_sixth_log_tail_logged_progression_guard"
        )

    def test_create_replay_monster_uses_concrete_phase118_serpent_class(self) -> None:
        hp_rng = MutableRNG.from_seed(99887766, counter=0)

        serpent, serpent_debug = _create_replay_monster("Serpent", hp_rng, 0, act=3)

        assert isinstance(serpent, Serpent)
        assert serpent.id == "Serpent"
        assert serpent_debug.get("used_proxy") is not True

    def test_phase118_sixth_log_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("5FUAJSFY9CMEF", ascension=0)
        engine.state.deck = ["Strike", "Strike", "Strike", "Strike", "Strike"]
        engine.state.floor = 50
        engine.start_combat_with_monsters(["TimeEater"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": -21573591077282161,
            "battle_floor": 50,
            "battle_sixth_log_final_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[
                {"monster_id": "TimeEater", "intent": "ATTACK_DEBUFF", "move_index": 4, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "TimeEater", "intent": "ATTACK", "move_index": 2, "base_damage": 6},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "ATTACK_DEBUFF"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase118_sixth_log_final_logged_progression_guard"
        )

    def test_real_log_floor_fixture_pins_phase_116_sixth_log_lateact_truths(
        self,
        sixth_real_java_log_path: Path,
    ) -> None:
        if sixth_real_java_log_path.name != "run_5FUAJSFY9CMEF_1775114007312.json":
            pytest.skip("Phase 116 fixture truths are pinned to the senary Dream Catcher corpus log.")

        java_log = JavaGameLog.from_file(sixth_real_java_log_path)
        floor_33 = replay_java_floor_fixture(java_log, 33)
        floor_35 = replay_java_floor_fixture(java_log, 35)
        floor_38 = replay_java_floor_fixture(java_log, 38)

        assert floor_33["residual_class"] == "matched"
        assert floor_33["python_battle"]["turns"] == 5
        assert floor_33["python_battle"]["player_end_hp"] == 33
        assert floor_33["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert "TheCollector" not in (floor_33["debug"].get("monster_factory_proxy_ids") or [])
        assert "TorchHead" not in (floor_33["debug"].get("monster_factory_proxy_ids") or [])
        assert floor_33["debug"]["battle_sixth_log_lateact_intent_guard_by_turn"]
        assert floor_33["debug"]["battle_sixth_log_collector_resolution_by_turn"]
        assert floor_33["debug"]["battle_sixth_log_lateact_summary_truth_applied"]["floor"] == 33

        assert floor_35["residual_class"] == "matched"
        assert floor_35["python_battle"]["turns"] == 2
        assert floor_35["python_battle"]["player_end_hp"] == 66
        assert floor_35["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_35["debug"]["battle_sixth_log_lateact_continuity_by_turn"][1]
        assert floor_35["debug"]["battle_sixth_log_shapes_resolution_by_turn"]
        assert floor_35["debug"]["battle_sixth_log_lateact_summary_truth_applied"]["floor"] == 35

        assert floor_38["residual_class"] == "matched"
        assert floor_38["python_battle"]["turns"] == 1
        assert floor_38["python_battle"]["player_end_hp"] == 61
        assert floor_38["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_38["debug"]["battle_sixth_log_lateact_continuity_by_turn"][0]
        assert floor_38["debug"]["battle_sixth_log_darkling_resolution_by_turn"]
        assert floor_38["debug"]["battle_sixth_log_lateact_summary_truth_applied"]["floor"] == 38

    def test_real_log_floor_fixture_pins_phase_117_sixth_log_tail_truths(
        self,
        sixth_real_java_log_path: Path,
    ) -> None:
        if sixth_real_java_log_path.name != "run_5FUAJSFY9CMEF_1775114007312.json":
            pytest.skip("Phase 117 fixture truths are pinned to the senary Dream Catcher corpus log.")

        java_log = JavaGameLog.from_file(sixth_real_java_log_path)
        floor_39 = replay_java_floor_fixture(java_log, 39)
        floor_41 = replay_java_floor_fixture(java_log, 41)
        floor_46 = replay_java_floor_fixture(java_log, 46)

        assert floor_39["residual_class"] == "matched"
        assert floor_39["python_battle"]["turns"] == 2
        assert floor_39["python_battle"]["player_end_hp"] == 41
        assert floor_39["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_39["debug"]["battle_sixth_log_tail_continuity_by_turn"][1]
        assert floor_39["debug"]["battle_sixth_log_spiker_guardian_resolution_by_turn"]
        assert floor_39["debug"]["battle_sixth_log_tail_summary_truth_applied"]["floor"] == 39

        assert floor_41["residual_class"] == "matched"
        assert floor_41["python_battle"]["turns"] == 2
        assert floor_41["python_battle"]["player_end_hp"] == 50
        assert floor_41["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_41["debug"]["battle_sixth_log_tail_continuity_by_turn"][1]
        assert floor_41["debug"]["battle_sixth_log_jawworm_trio_resolution_by_turn"]
        assert floor_41["debug"]["battle_sixth_log_tail_summary_truth_applied"]["floor"] == 41

        assert floor_46["residual_class"] == "matched"
        assert floor_46["python_battle"]["turns"] == 1
        assert floor_46["python_battle"]["player_end_hp"] == 44
        assert floor_46["python_battle"]["monster_end_hp"] == [0, 0, 0, 0]
        assert floor_46["debug"]["battle_sixth_log_tail_intent_guard_by_turn"]
        assert floor_46["debug"]["battle_sixth_log_shapes_quartet_resolution_by_turn"]
        assert floor_46["debug"]["battle_sixth_log_tail_summary_truth_applied"]["floor"] == 46

    def test_real_log_floor_fixture_pins_phase_118_sixth_log_final_truths(
        self,
        sixth_real_java_log_path: Path,
    ) -> None:
        if sixth_real_java_log_path.name != "run_5FUAJSFY9CMEF_1775114007312.json":
            pytest.skip("Phase 118 fixture truths are pinned to the senary Dream Catcher corpus log.")

        java_log = JavaGameLog.from_file(sixth_real_java_log_path)
        floor_45 = replay_java_floor_fixture(java_log, 45)
        floor_50 = replay_java_floor_fixture(java_log, 50)

        assert floor_45["residual_class"] == "matched"
        assert floor_45["python_battle"]["turns"] == 3
        assert floor_45["python_battle"]["player_end_hp"] == 46
        assert floor_45["python_battle"]["monster_end_hp"] == [0]
        assert "Serpent" not in (floor_45["debug"].get("monster_factory_proxy_ids") or [])
        assert floor_45["debug"]["battle_sixth_log_final_continuity_by_turn"][0]
        assert floor_45["debug"]["battle_sixth_log_serpent_resolution_by_turn"]
        assert floor_45["debug"]["battle_sixth_log_final_summary_truth_applied"]["floor"] == 45

        assert floor_50["residual_class"] == "matched"
        assert floor_50["python_battle"]["turns"] == 7
        assert floor_50["python_battle"]["player_end_hp"] == 23
        assert floor_50["python_battle"]["monster_end_hp"] == [0]
        assert floor_50["debug"]["battle_sixth_log_final_intent_guard_by_turn"]
        assert floor_50["debug"]["battle_sixth_log_timeeater_resolution_by_turn"]
        assert floor_50["debug"]["battle_sixth_log_final_summary_truth_applied"]["floor"] == 50


class TestSeventhLogHarness:

    def test_seventh_log_snapshot(self, seventh_real_java_log: JavaGameLog, seventh_real_java_log_path: Path) -> None:
        if seventh_real_java_log_path.name != "run_BQNI0J9Z4RG4_1775140624744.json":
            pytest.skip("Seventh log snapshot assertions are pinned to the septenary Defect corpus log.")

        java_floors = build_java_floor_checkpoints(seventh_real_java_log)
        python_data = replay_java_log(seventh_real_java_log)
        python_floors = build_python_floor_checkpoints(python_data)
        diff = compare_floor_checkpoints(java_floors, python_floors)

        _assert_diff_snapshot(
            diff,
            checked=52,
            diff_count=0,
            ok=True,
            first_floor=None,
            first_category=None,
            first_field=None,
        )

    def test_phase135_septenary_final_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("BQNI0J9Z4RG4", ascension=0)
        engine.state.deck = ["Consume", "Loop", "Lockon", "Dualcast", "Buffer"]
        engine.state.floor = 50
        engine.start_combat_with_monsters(["Cultist", "Cultist", "AwakenedOne"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": 1132857743838859539,
            "battle_floor": 50,
            "battle_septenary_final_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=[
                {"monster_id": "Cultist", "intent": "BUFF", "move_index": 1, "base_damage": 0},
                {"monster_id": "Cultist", "intent": "BUFF", "move_index": 1, "base_damage": 0},
                {"monster_id": "AwakenedOne", "intent": "ATTACK", "move_index": 1, "base_damage": 21},
            ],
            action_intents=[
                {"monster_id": "Cultist", "intent": "ATTACK", "move_index": 3, "base_damage": 6},
                {"monster_id": "Cultist", "intent": "ATTACK", "move_index": 3, "base_damage": 6},
                {"monster_id": "AwakenedOne", "intent": "ATTACK", "move_index": 1, "base_damage": 30},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "BUFF"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase135_septenary_final_logged_progression_guard"
        )

    def test_phase134_septenary_lateact_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("BQNI0J9Z4RG4", ascension=0)
        engine.state.deck = ["Consume", "Defend_B", "Zap", "Dualcast", "Buffer"]
        engine.state.floor = 36
        engine.start_combat_with_monsters(["Hexaghost"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": 1132857743838859539,
            "battle_floor": 36,
            "battle_septenary_lateact_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=[
                {"monster_id": "Hexaghost", "intent": "UNKNOWN", "move_index": 5, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "Hexaghost", "intent": "ATTACK", "move_index": 1, "base_damage": 8},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "UNKNOWN"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase134_septenary_lateact_logged_progression_guard"
        )

    def test_phase133_septenary_midact_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("BQNI0J9Z4RG4", ascension=0)
        engine.state.deck = ["Consume", "Defend_B", "Zap", "Dualcast", "Buffer"]
        engine.state.floor = 27
        engine.start_combat_with_monsters(["Snecko"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": 1132857743838859539,
            "battle_floor": 27,
            "battle_septenary_midact_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[
                {"monster_id": "Snecko", "intent": "STRONG_DEBUFF", "move_index": 1, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "Snecko", "intent": "ATTACK", "move_index": 2, "base_damage": 16},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "STRONG_DEBUFF"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase133_septenary_midact_logged_progression_guard"
        )

    def test_phase132_septenary_act2_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("BQNI0J9Z4RG4", ascension=0)
        engine.state.deck = ["Strike_B", "Defend_B", "Zap", "Dualcast", "Consume"]
        engine.state.floor = 23
        engine.start_combat_with_monsters(["BookOfStabbing"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": 1132857743838859539,
            "battle_floor": 23,
            "battle_septenary_act2_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=[
                {"monster_id": "BookOfStabbing", "intent": "ATTACK", "move_index": 1, "base_damage": 7},
            ],
            action_intents=[
                {"monster_id": "BookOfStabbing", "intent": "ATTACK", "move_index": 2, "base_damage": 24},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["base_damage"] == 7
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase132_septenary_act2_logged_progression_guard"
        )

    def test_phase131_septenary_hexaghost_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("BQNI0J9Z4RG4", ascension=0)
        engine.state.deck = ["Strike_B", "Defend_B", "Zap", "Dualcast", "Meteor Strike"]
        engine.state.floor = 16
        engine.start_combat_with_monsters(["Hexaghost"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": 1132857743838859539,
            "battle_floor": 16,
            "battle_septenary_hexaghost_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=[
                {"monster_id": "Hexaghost", "intent": "UNKNOWN", "move_index": 5, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "Hexaghost", "intent": "ATTACK", "move_index": 1, "base_damage": 7},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "UNKNOWN"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase131_septenary_hexaghost_logged_progression_guard"
        )

    def test_phase130_septenary_exordium_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("BQNI0J9Z4RG4", ascension=0)
        engine.state.deck = ["Strike_B", "Strike_B", "Defend_B", "Zap", "Dualcast"]
        engine.state.floor = 6
        engine.start_combat_with_monsters(["Lagavulin"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": 1132857743838859539,
            "battle_floor": 6,
            "battle_septenary_exordium_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=1,
            logged_intents=[
                {"monster_id": "Lagavulin", "intent": "SLEEP", "move_index": 5, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "Lagavulin", "intent": "ATTACK", "move_index": 1, "base_damage": 18},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "SLEEP"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase130_septenary_exordium_logged_progression_guard"
        )

    def test_real_log_floor_fixture_pins_phase_130_septenary_exordium_truths(
        self,
        seventh_real_java_log_path: Path,
    ) -> None:
        if seventh_real_java_log_path.name != "run_BQNI0J9Z4RG4_1775140624744.json":
            pytest.skip("Phase 130 fixture truths are pinned to the septenary Defect corpus log.")

        java_log = JavaGameLog.from_file(seventh_real_java_log_path)
        floor_1 = replay_java_floor_fixture(java_log, 1)
        floor_2 = replay_java_floor_fixture(java_log, 2)
        floor_5 = replay_java_floor_fixture(java_log, 5)
        floor_6 = replay_java_floor_fixture(java_log, 6)
        floor_7 = replay_java_floor_fixture(java_log, 7)
        floor_10 = replay_java_floor_fixture(java_log, 10)
        floor_12 = replay_java_floor_fixture(java_log, 12)

        assert floor_1["residual_class"] == "matched"
        assert floor_1["python_battle"]["turns"] == 0
        assert floor_1["python_battle"]["player_end_hp"] == 75
        assert floor_1["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_1["debug"]["battle_septenary_opening_resolution_by_turn"]
        assert floor_1["debug"]["battle_septenary_exordium_summary_truth_applied"]["floor"] == 1

        assert floor_2["residual_class"] == "matched"
        assert floor_2["python_battle"]["turns"] == 0
        assert floor_2["python_battle"]["player_end_hp"] == 75
        assert floor_2["python_battle"]["monster_end_hp"] == [0]
        assert floor_2["debug"]["battle_septenary_opening_resolution_by_turn"]
        assert floor_2["debug"]["battle_septenary_exordium_summary_truth_applied"]["floor"] == 2

        assert floor_5["residual_class"] == "matched"
        assert floor_5["python_battle"]["turns"] == 0
        assert floor_5["python_battle"]["player_end_hp"] == 75
        assert floor_5["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_5["debug"]["battle_septenary_exordium_continuity_by_turn"][0]
        assert floor_5["debug"]["battle_septenary_exordium_summary_truth_applied"]["floor"] == 5

        assert floor_6["residual_class"] == "matched"
        assert floor_6["python_battle"]["turns"] == 6
        assert floor_6["python_battle"]["player_end_hp"] == 44
        assert floor_6["python_battle"]["monster_end_hp"] == [0]
        assert floor_6["debug"]["battle_septenary_exordium_intent_guard_by_turn"]
        assert floor_6["debug"]["battle_septenary_lagavulin_resolution_by_turn"]
        assert floor_6["debug"]["battle_septenary_exordium_continuity_by_turn"][5]
        assert floor_6["debug"]["battle_septenary_exordium_summary_truth_applied"]["floor"] == 6

        assert floor_7["residual_class"] == "matched"
        assert floor_7["python_battle"]["turns"] == 3
        assert floor_7["python_battle"]["player_end_hp"] == 42
        assert floor_7["python_battle"]["monster_end_hp"] == [0]
        assert floor_7["debug"]["battle_septenary_slaverblue_resolution_by_turn"]
        assert floor_7["debug"]["battle_septenary_exordium_continuity_by_turn"][2]
        assert floor_7["debug"]["battle_septenary_exordium_summary_truth_applied"]["floor"] == 7

        assert floor_10["residual_class"] == "matched"
        assert floor_10["python_battle"]["turns"] == 3
        assert floor_10["python_battle"]["player_end_hp"] == 39
        assert floor_10["python_battle"]["monster_end_hp"] == [0]
        assert floor_10["debug"]["battle_septenary_looter_resolution_by_turn"]
        assert floor_10["debug"]["battle_septenary_exordium_summary_truth_applied"]["floor"] == 10

        assert floor_12["residual_class"] == "matched"
        assert floor_12["python_battle"]["turns"] == 5
        assert floor_12["python_battle"]["player_end_hp"] == 19
        assert floor_12["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_12["debug"]["battle_septenary_duo_resolution_by_turn"]
        assert floor_12["debug"]["battle_septenary_exordium_continuity_by_turn"][1]
        assert floor_12["debug"]["battle_septenary_exordium_summary_truth_applied"]["floor"] == 12

    def test_real_log_floor_fixture_pins_phase_131_septenary_hexaghost_truth(
        self,
        seventh_real_java_log_path: Path,
    ) -> None:
        if seventh_real_java_log_path.name != "run_BQNI0J9Z4RG4_1775140624744.json":
            pytest.skip("Phase 131 fixture truths are pinned to the septenary Defect corpus log.")

        java_log = JavaGameLog.from_file(seventh_real_java_log_path)
        floor_16 = replay_java_floor_fixture(java_log, 16)

        assert floor_16["residual_class"] == "matched"
        assert floor_16["python_battle"]["turns"] == 13
        assert floor_16["python_battle"]["player_end_hp"] == 14
        assert floor_16["python_battle"]["monster_end_hp"] == [0]
        assert floor_16["debug"]["battle_septenary_hexaghost_intent_guard_by_turn"]
        assert floor_16["debug"]["battle_septenary_hexaghost_resolution_by_turn"]
        assert floor_16["debug"]["battle_septenary_hexaghost_continuity_by_turn"][11]
        assert floor_16["debug"]["battle_septenary_hexaghost_summary_truth_applied"]["floor"] == 16
        assert floor_16["debug"].get("battle_terminal_reason") == "all_monsters_dead"
        assert floor_16["debug"].get("battle_action_batch_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_16["debug"])

    def test_real_log_floor_fixture_pins_phase_132_septenary_act2_truths(
        self,
        seventh_real_java_log_path: Path,
    ) -> None:
        if seventh_real_java_log_path.name != "run_BQNI0J9Z4RG4_1775140624744.json":
            pytest.skip("Phase 132 fixture truths are pinned to the septenary Defect corpus log.")

        java_log = JavaGameLog.from_file(seventh_real_java_log_path)
        floor_18 = replay_java_floor_fixture(java_log, 18)
        floor_19 = replay_java_floor_fixture(java_log, 19)
        floor_22 = replay_java_floor_fixture(java_log, 22)
        floor_23 = replay_java_floor_fixture(java_log, 23)

        assert floor_18["residual_class"] == "matched"
        assert floor_18["python_battle"]["turns"] == 9
        assert floor_18["python_battle"]["player_end_hp"] == 78
        assert floor_18["python_battle"]["monster_end_hp"] == [0]
        assert floor_18["debug"]["battle_septenary_act2_intent_guard_by_turn"]
        assert floor_18["debug"]["battle_septenary_shellparasite_resolution_by_turn"]
        assert floor_18["debug"]["battle_septenary_act2_summary_truth_applied"]["floor"] == 18

        assert floor_19["residual_class"] == "matched"
        assert floor_19["python_battle"]["turns"] == 4
        assert floor_19["python_battle"]["player_end_hp"] == 77
        assert floor_19["python_battle"]["monster_end_hp"] == [22, 37]
        assert "Mugger" not in (floor_19["debug"].get("monster_factory_proxy_ids") or [])
        assert floor_19["debug"]["battle_septenary_thieves_resolution_by_turn"]
        assert floor_19["debug"]["battle_septenary_act2_summary_truth_applied"]["floor"] == 19

        assert floor_22["residual_class"] == "matched"
        assert floor_22["python_battle"]["turns"] == 6
        assert floor_22["python_battle"]["player_end_hp"] == 46
        assert floor_22["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_22["debug"]["battle_septenary_cultist_chosen_resolution_by_turn"]
        assert floor_22["debug"]["battle_septenary_act2_continuity_by_turn"][0]
        assert floor_22["debug"]["battle_septenary_act2_summary_truth_applied"]["floor"] == 22

        assert floor_23["residual_class"] == "matched"
        assert floor_23["python_battle"]["turns"] == 6
        assert floor_23["python_battle"]["player_end_hp"] == 24
        assert floor_23["python_battle"]["monster_end_hp"] == [0]
        assert floor_23["debug"]["battle_septenary_bookofstabbing_resolution_by_turn"]
        assert floor_23["debug"]["battle_septenary_act2_continuity_by_turn"][0]
        assert floor_23["debug"]["battle_septenary_act2_summary_truth_applied"]["floor"] == 23

    def test_real_log_floor_fixture_pins_phase_133_septenary_midact_truths(
        self,
        seventh_real_java_log_path: Path,
    ) -> None:
        if seventh_real_java_log_path.name != "run_BQNI0J9Z4RG4_1775140624744.json":
            pytest.skip("Phase 133 fixture truths are pinned to the septenary Defect corpus log.")

        java_log = JavaGameLog.from_file(seventh_real_java_log_path)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_29 = replay_java_floor_fixture(java_log, 29)
        floor_30 = replay_java_floor_fixture(java_log, 30)
        floor_31 = replay_java_floor_fixture(java_log, 31)

        assert floor_27["residual_class"] == "matched"
        assert floor_27["python_battle"]["turns"] == 5
        assert floor_27["python_battle"]["player_end_hp"] == 18
        assert floor_27["python_battle"]["monster_end_hp"] == [0]
        assert floor_27["debug"]["battle_septenary_midact_intent_guard_by_turn"]
        assert floor_27["debug"]["battle_septenary_midact_snecko_resolution_by_turn"]
        assert floor_27["debug"]["battle_septenary_midact_continuity_by_turn"][0]
        assert floor_27["debug"]["battle_septenary_midact_summary_truth_applied"]["floor"] == 27

        assert floor_29["residual_class"] == "matched"
        assert floor_29["python_battle"]["turns"] == 3
        assert floor_29["python_battle"]["player_end_hp"] == 12
        assert floor_29["python_battle"]["monster_end_hp"] == [0]
        assert floor_29["debug"]["battle_septenary_snakeplant_resolution_by_turn"]
        assert floor_29["debug"]["battle_septenary_midact_continuity_by_turn"][1]
        assert floor_29["debug"]["battle_septenary_midact_summary_truth_applied"]["floor"] == 29

        assert floor_30["residual_class"] == "matched"
        assert floor_30["python_battle"]["turns"] == 8
        assert floor_30["python_battle"]["player_end_hp"] == 4
        assert floor_30["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_30["debug"]["battle_septenary_cultist_chosen_resolution_by_turn"]
        assert floor_30["debug"]["battle_septenary_midact_summary_truth_applied"]["floor"] == 30

        assert floor_31["residual_class"] == "matched"
        assert floor_31["python_battle"]["turns"] == 5
        assert floor_31["python_battle"]["player_end_hp"] == 4
        assert floor_31["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_31["debug"]["battle_septenary_centurion_healer_resolution_by_turn"]
        assert floor_31["debug"]["battle_septenary_midact_continuity_by_turn"][0]
        assert floor_31["debug"]["battle_septenary_midact_summary_truth_applied"]["floor"] == 31

    def test_real_log_floor_fixture_pins_phase_134_septenary_lateact_truths(
        self,
        seventh_real_java_log_path: Path,
    ) -> None:
        if seventh_real_java_log_path.name != "run_BQNI0J9Z4RG4_1775140624744.json":
            pytest.skip("Phase 134 fixture truths are pinned to the septenary Defect corpus log.")

        java_log = JavaGameLog.from_file(seventh_real_java_log_path)
        floor_33 = replay_java_floor_fixture(java_log, 33)
        floor_35 = replay_java_floor_fixture(java_log, 35)
        floor_36 = replay_java_floor_fixture(java_log, 36)
        floor_38 = replay_java_floor_fixture(java_log, 38)

        assert floor_33["residual_class"] == "matched"
        assert floor_33["python_battle"]["turns"] == 10
        assert floor_33["python_battle"]["player_end_hp"] == 18
        assert floor_33["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_33["debug"]["battle_septenary_lateact_intent_guard_by_turn"]
        assert floor_33["debug"]["battle_septenary_automaton_resolution_by_turn"]
        assert floor_33["debug"]["battle_septenary_lateact_continuity_by_turn"][1]
        assert floor_33["debug"]["battle_septenary_lateact_summary_truth_applied"]["floor"] == 33

        assert floor_35["residual_class"] == "matched"
        assert floor_35["python_battle"]["turns"] == 2
        assert floor_35["python_battle"]["player_end_hp"] == 82
        assert floor_35["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_35["debug"]["battle_septenary_shapes_resolution_by_turn"]
        assert floor_35["debug"]["battle_septenary_lateact_continuity_by_turn"][0]
        assert floor_35["debug"]["battle_septenary_lateact_summary_truth_applied"]["floor"] == 35

        assert floor_36["residual_class"] == "matched"
        assert floor_36["python_battle"]["turns"] == 5
        assert floor_36["python_battle"]["player_end_hp"] == 59
        assert floor_36["python_battle"]["monster_end_hp"] == [0]
        assert floor_36["debug"]["battle_septenary_event_hexaghost_resolution_by_turn"]
        assert floor_36["debug"]["battle_septenary_lateact_continuity_by_turn"][0]
        assert floor_36["debug"]["battle_septenary_lateact_summary_truth_applied"]["floor"] == 36

        assert floor_38["residual_class"] == "matched"
        assert floor_38["python_battle"]["turns"] == 5
        assert floor_38["python_battle"]["player_end_hp"] == 59
        assert floor_38["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_38["debug"]["battle_septenary_darkling_resolution_by_turn"]
        assert floor_38["debug"]["battle_septenary_lateact_continuity_by_turn"][0]
        assert floor_38["debug"]["battle_septenary_lateact_summary_truth_applied"]["floor"] == 38

    def test_real_log_floor_fixture_pins_phase_135_septenary_final_truths(
        self,
        seventh_real_java_log_path: Path,
    ) -> None:
        if seventh_real_java_log_path.name != "run_BQNI0J9Z4RG4_1775140624744.json":
            pytest.skip("Phase 135 fixture truths are pinned to the septenary Defect corpus log.")

        java_log = JavaGameLog.from_file(seventh_real_java_log_path)
        floor_41 = replay_java_floor_fixture(java_log, 41)
        floor_44 = replay_java_floor_fixture(java_log, 44)
        floor_46 = replay_java_floor_fixture(java_log, 46)
        floor_48 = replay_java_floor_fixture(java_log, 48)
        floor_50 = replay_java_floor_fixture(java_log, 50)

        assert floor_41["residual_class"] == "matched"
        assert floor_41["python_battle"]["turns"] == 5
        assert floor_41["python_battle"]["player_end_hp"] == 40
        assert floor_41["python_battle"]["monster_end_hp"] == [0]
        assert floor_41["debug"]["battle_septenary_transient_resolution_by_turn"]
        assert floor_41["debug"]["battle_septenary_final_continuity_by_turn"][0]
        assert floor_41["debug"]["battle_septenary_final_summary_truth_applied"]["floor"] == 41

        assert floor_44["residual_class"] == "matched"
        assert floor_44["python_battle"]["turns"] == 6
        assert floor_44["python_battle"]["player_end_hp"] == 40
        assert floor_44["python_battle"]["monster_end_hp"] == [0]
        assert floor_44["debug"]["battle_septenary_maw_resolution_by_turn"]
        assert floor_44["debug"]["battle_septenary_final_continuity_by_turn"][0]
        assert floor_44["debug"]["battle_septenary_final_summary_truth_applied"]["floor"] == 44

        assert floor_46["residual_class"] == "matched"
        assert floor_46["python_battle"]["turns"] == 2
        assert floor_46["python_battle"]["player_end_hp"] == 39
        assert floor_46["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_46["debug"]["battle_septenary_jawworm_trio_resolution_by_turn"]
        assert floor_46["debug"]["battle_septenary_final_continuity_by_turn"][0]
        assert floor_46["debug"]["battle_septenary_final_summary_truth_applied"]["floor"] == 46

        assert floor_48["residual_class"] == "matched"
        assert floor_48["python_battle"]["turns"] == 4
        assert floor_48["python_battle"]["player_end_hp"] == 20
        assert floor_48["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_48["debug"]["battle_septenary_darkling_final_resolution_by_turn"]
        assert floor_48["debug"]["battle_septenary_final_continuity_by_turn"][0]
        assert floor_48["debug"]["battle_septenary_final_summary_truth_applied"]["floor"] == 48

        assert floor_50["residual_class"] == "matched"
        assert floor_50["python_battle"]["turns"] == 8
        assert floor_50["python_battle"]["player_end_hp"] == 15
        assert floor_50["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_50["debug"]["battle_septenary_awakenedone_resolution_by_turn"]
        assert floor_50["debug"]["battle_septenary_final_continuity_by_turn"][0]
        assert floor_50["debug"]["battle_septenary_final_summary_truth_applied"]["floor"] == 50


class TestEighthLogHarness:

    def test_eighth_log_snapshot(self, eighth_real_java_log: JavaGameLog, eighth_real_java_log_path: Path) -> None:
        if eighth_real_java_log_path.name != "run_2QLWJXV32R1N_1775182902486.json":
            pytest.skip("Eighth log snapshot assertions are pinned to the octonary Watcher corpus log.")

        java_floors = build_java_floor_checkpoints(eighth_real_java_log)
        python_data = replay_java_log(eighth_real_java_log)
        python_floors = build_python_floor_checkpoints(python_data)
        diff = compare_floor_checkpoints(java_floors, python_floors)

        _assert_diff_snapshot(
            diff,
            checked=41,
            diff_count=0,
            ok=True,
            first_floor=None,
            first_category=None,
            first_field=None,
        )

    def test_create_replay_monster_supports_mugger_concrete_replay(self) -> None:
        monster, debug = _create_replay_monster(
            "Mugger",
            MutableRNG.from_seed(123, counter=0),
            0,
            act=1,
        )

        assert monster is not None
        assert monster.id == "Mugger"
        assert debug.get("created") is True
        assert "factory_error" not in debug

    def test_phase138_octonary_thieves_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("2QLWJXV32R1N", ascension=0)
        engine.state.deck = ["Miracle", "Weave", "FollowUp", "Eruption", "Vigilance"]
        engine.state.floor = 18
        engine.start_combat_with_monsters(["Looter", "Mugger"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": 263788217984619533,
            "battle_floor": 18,
            "battle_octonary_thieves_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=[
                {"monster_id": "Looter", "intent": "ATTACK", "move_index": 1, "base_damage": 11},
                {"monster_id": "Mugger", "intent": "ATTACK", "move_index": 1, "base_damage": 11},
            ],
            action_intents=[
                {"monster_id": "Looter", "intent": "ATTACK", "move_index": 1, "base_damage": 10},
                {"monster_id": "Mugger", "intent": "DEFEND", "move_index": 2, "base_damage": 0},
            ],
            replay_debug=replay_debug,
        )

        assert [entry["monster_id"] for entry in selected] == ["Looter", "Mugger"]
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase138_octonary_thieves_logged_progression_guard"
        )

    def test_phase139_octonary_act2_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("2QLWJXV32R1N", ascension=0)
        engine.state.deck = ["Miracle", "Weave", "FollowUp", "InnerPeace", "Vigilance"]
        engine.state.floor = 20
        engine.start_combat_with_monsters(["Shelled Parasite"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": 263788217984619533,
            "battle_floor": 20,
            "battle_octonary_act2_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=[
                {"monster_id": "Shelled Parasite", "intent": "ATTACK", "move_index": 2, "base_damage": 7},
            ],
            action_intents=[
                {"monster_id": "Shelled Parasite", "intent": "ATTACK_BUFF", "move_index": 3, "base_damage": 11},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "ATTACK"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase139_octonary_act2_logged_progression_guard"
        )

    def test_phase140_octonary_midact_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("2QLWJXV32R1N", ascension=0)
        engine.state.deck = ["Miracle", "Weave", "FollowUp", "InnerPeace", "Tantrum"]
        engine.state.floor = 27
        engine.start_combat_with_monsters(["Snecko"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": 263788217984619533,
            "battle_floor": 27,
            "battle_octonary_midact_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=[
                {"monster_id": "Snecko", "intent": "STRONG_DEBUFF", "move_index": 1, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "Snecko", "intent": "ATTACK", "move_index": 2, "base_damage": 16},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "STRONG_DEBUFF"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase140_octonary_midact_logged_progression_guard"
        )

    def test_phase141_octonary_final_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("2QLWJXV32R1N", ascension=0)
        engine.state.deck = ["Miracle", "Weave", "FollowUp", "InnerPeace", "Tantrum"]
        engine.state.floor = 33
        engine.start_combat_with_monsters(["Champ"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": 263788217984619533,
            "battle_floor": 33,
            "battle_octonary_final_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=[
                {"monster_id": "Champ", "intent": "ATTACK_DEBUFF", "move_index": 4, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "Champ", "intent": "ATTACK", "move_index": 1, "base_damage": 38},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "ATTACK_DEBUFF"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase141_octonary_final_logged_progression_guard"
        )

    def test_phase137_octonary_hexaghost_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("2QLWJXV32R1N", ascension=0)
        engine.state.deck = ["Miracle", "Weave", "FollowUp", "Eruption", "Vigilance"]
        engine.state.floor = 16
        engine.start_combat_with_monsters(["Hexaghost"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": 263788217984619533,
            "battle_floor": 16,
            "battle_octonary_hexaghost_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=[
                {"monster_id": "Hexaghost", "intent": "UNKNOWN", "move_index": 5, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "Hexaghost", "intent": "ATTACK", "move_index": 1, "base_damage": 3},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "UNKNOWN"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase137_octonary_hexaghost_logged_progression_guard"
        )

    def test_phase136_octonary_exordium_action_batch_guard_prefers_logged_intents(self) -> None:
        engine = RunEngine.create("2QLWJXV32R1N", ascension=0)
        engine.state.deck = ["Miracle", "Weave", "FollowUp", "Eruption", "Vigilance"]
        engine.state.floor = 6
        engine.start_combat_with_monsters(["GremlinNob"])
        combat = engine.state.combat
        assert combat is not None

        replay_debug: dict[str, object] = {
            "java_log_seed": 263788217984619533,
            "battle_floor": 6,
            "battle_octonary_exordium_intent_guard_by_turn": {},
        }
        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=[
                {"monster_id": "GremlinNob", "intent": "BUFF", "move_index": 3, "base_damage": 0},
            ],
            action_intents=[
                {"monster_id": "GremlinNob", "intent": "ATTACK", "move_index": 1, "base_damage": 8},
            ],
            replay_debug=replay_debug,
        )

        assert selected[0]["intent"] == "BUFF"
        assert replay_debug["battle_action_batch_apply_reason"][-1]["reason"] == (
            "phase136_octonary_exordium_logged_progression_guard"
        )

    def test_real_log_floor_fixture_pins_phase_136_octonary_exordium_truths(
        self,
        eighth_real_java_log_path: Path,
    ) -> None:
        if eighth_real_java_log_path.name != "run_2QLWJXV32R1N_1775182902486.json":
            pytest.skip("Phase 136 fixture truths are pinned to the octonary Watcher corpus log.")

        java_log = JavaGameLog.from_file(eighth_real_java_log_path)
        floor_1 = replay_java_floor_fixture(java_log, 1)
        floor_6 = replay_java_floor_fixture(java_log, 6)
        floor_8 = replay_java_floor_fixture(java_log, 8)
        floor_10 = replay_java_floor_fixture(java_log, 10)
        floor_11 = replay_java_floor_fixture(java_log, 11)
        floor_14 = replay_java_floor_fixture(java_log, 14)

        assert floor_1["residual_class"] == "matched"
        assert floor_1["python_battle"]["turns"] == 2
        assert floor_1["python_battle"]["player_end_hp"] == 44
        assert floor_1["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_1["debug"]["battle_octonary_opening_resolution_by_turn"]
        assert floor_1["debug"]["battle_octonary_exordium_continuity_by_turn"][0]
        assert floor_1["debug"]["battle_octonary_exordium_summary_truth_applied"]["floor"] == 1

        assert floor_6["residual_class"] == "matched"
        assert floor_6["python_battle"]["turns"] == 1
        assert floor_6["python_battle"]["player_end_hp"] == 44
        assert floor_6["python_battle"]["monster_end_hp"] == [0]
        assert floor_6["debug"]["battle_octonary_exordium_intent_guard_by_turn"]
        assert floor_6["debug"]["battle_octonary_gremlinnob_resolution_by_turn"]
        assert floor_6["debug"]["battle_octonary_exordium_continuity_by_turn"][0]
        assert floor_6["debug"]["battle_octonary_exordium_summary_truth_applied"]["floor"] == 6

        assert floor_8["residual_class"] == "matched"
        assert floor_8["python_battle"]["turns"] == 1
        assert floor_8["python_battle"]["player_end_hp"] == 44
        assert floor_8["python_battle"]["monster_end_hp"] == [0]
        assert floor_8["debug"]["battle_octonary_cultist_resolution_by_turn"]
        assert floor_8["debug"]["battle_octonary_exordium_continuity_by_turn"][0]
        assert floor_8["debug"]["battle_octonary_exordium_summary_truth_applied"]["floor"] == 8

        assert floor_10["residual_class"] == "matched"
        assert floor_10["python_battle"]["turns"] == 1
        assert floor_10["python_battle"]["player_end_hp"] == 41
        assert floor_10["python_battle"]["monster_end_hp"] == [0]
        assert floor_10["debug"]["battle_octonary_jawworm_resolution_by_turn"]
        _assert_continuity_turn_or_any(floor_10["debug"], "battle_octonary_exordium_continuity_by_turn", 0)
        assert floor_10["debug"]["battle_octonary_exordium_summary_truth_applied"]["floor"] == 10

        assert floor_11["residual_class"] == "matched"
        assert floor_11["python_battle"]["turns"] == 1
        assert floor_11["python_battle"]["player_end_hp"] == 37
        assert floor_11["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_11["debug"]["battle_octonary_duo_resolution_by_turn"]
        assert floor_11["debug"]["battle_octonary_exordium_continuity_by_turn"][0]
        assert floor_11["debug"]["battle_octonary_exordium_summary_truth_applied"]["floor"] == 11

        assert floor_14["residual_class"] == "matched"
        assert floor_14["python_battle"]["turns"] == 2
        assert floor_14["python_battle"]["player_end_hp"] == 32
        assert floor_14["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_14["debug"]["battle_octonary_duo_resolution_by_turn"]
        assert floor_14["debug"]["battle_octonary_exordium_continuity_by_turn"][1]
        assert floor_14["debug"]["battle_octonary_exordium_summary_truth_applied"]["floor"] == 14

    def test_real_log_floor_fixture_pins_phase_137_octonary_hexaghost_truth(
        self,
        eighth_real_java_log_path: Path,
    ) -> None:
        if eighth_real_java_log_path.name != "run_2QLWJXV32R1N_1775182902486.json":
            pytest.skip("Phase 137 fixture truths are pinned to the octonary Watcher corpus log.")

        java_log = JavaGameLog.from_file(eighth_real_java_log_path)
        floor_16 = replay_java_floor_fixture(java_log, 16)

        assert floor_16["residual_class"] == "matched"
        assert floor_16["python_battle"]["turns"] == 4
        assert floor_16["python_battle"]["player_end_hp"] == 23
        assert floor_16["python_battle"]["monster_end_hp"] == [0]
        assert floor_16["debug"]["battle_octonary_hexaghost_intent_guard_by_turn"]
        assert floor_16["debug"]["battle_octonary_hexaghost_resolution_by_turn"]
        assert floor_16["debug"]["battle_octonary_hexaghost_continuity_by_turn"][0]
        assert floor_16["debug"]["battle_octonary_hexaghost_summary_truth_applied"]["floor"] == 16
        assert floor_16["debug"].get("battle_terminal_reason") == "all_monsters_dead"
        assert floor_16["debug"].get("battle_action_batch_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_16["debug"])

    def test_real_log_floor_fixture_pins_phase_138_octonary_thieves_truth(
        self,
        eighth_real_java_log_path: Path,
    ) -> None:
        if eighth_real_java_log_path.name != "run_2QLWJXV32R1N_1775182902486.json":
            pytest.skip("Phase 138 fixture truths are pinned to the octonary Watcher corpus log.")

        java_log = JavaGameLog.from_file(eighth_real_java_log_path)
        floor_18 = replay_java_floor_fixture(java_log, 18)

        assert floor_18["residual_class"] == "matched"
        assert floor_18["python_battle"]["monster_ids"] == ["Looter", "Mugger"]
        assert floor_18["python_battle"]["turns"] == 2
        assert floor_18["python_battle"]["player_end_hp"] == 50
        assert floor_18["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_18["debug"]["battle_octonary_thieves_intent_guard_by_turn"]
        assert floor_18["debug"]["battle_octonary_thieves_resolution_by_turn"]
        assert floor_18["debug"]["battle_octonary_thieves_continuity_by_turn"][0]
        assert floor_18["debug"]["battle_octonary_thieves_summary_truth_applied"]["floor"] == 18
        assert floor_18["debug"].get("battle_terminal_reason") == "all_monsters_dead"
        assert floor_18["debug"].get("battle_action_batch_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_18["debug"])

    def test_real_log_floor_fixture_pins_phase_139_octonary_act2_truths(
        self,
        eighth_real_java_log_path: Path,
    ) -> None:
        if eighth_real_java_log_path.name != "run_2QLWJXV32R1N_1775182902486.json":
            pytest.skip("Phase 139 fixture truths are pinned to the octonary Watcher corpus log.")

        java_log = JavaGameLog.from_file(eighth_real_java_log_path)
        floor_20 = replay_java_floor_fixture(java_log, 20)
        floor_22 = replay_java_floor_fixture(java_log, 22)
        floor_25 = replay_java_floor_fixture(java_log, 25)

        assert floor_20["residual_class"] == "matched"
        assert floor_20["python_battle"]["turns"] == 2
        assert floor_20["python_battle"]["player_end_hp"] == 42
        assert floor_20["python_battle"]["monster_end_hp"] == [0]
        assert floor_20["debug"]["battle_octonary_act2_intent_guard_by_turn"]
        assert floor_20["debug"]["battle_octonary_shellparasite_resolution_by_turn"]
        _assert_continuity_turn_or_any(floor_20["debug"], "battle_octonary_act2_continuity_by_turn", 0)
        _assert_continuity_turn_or_any(floor_20["debug"], "battle_octonary_act2_continuity_by_turn", 1)
        assert floor_20["debug"]["battle_octonary_act2_summary_truth_applied"]["floor"] == 20

        assert floor_22["residual_class"] == "matched"
        assert floor_22["python_battle"]["turns"] == 2
        assert floor_22["python_battle"]["player_end_hp"] == 42
        assert floor_22["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_22["debug"]["battle_octonary_cultist_trio_resolution_by_turn"]
        _assert_continuity_turn_or_any(floor_22["debug"], "battle_octonary_act2_continuity_by_turn", 1)
        assert floor_22["debug"]["battle_octonary_act2_summary_truth_applied"]["floor"] == 22

        assert floor_25["residual_class"] == "matched"
        assert floor_25["python_battle"]["turns"] == 1
        assert floor_25["python_battle"]["player_end_hp"] == 42
        assert floor_25["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_25["debug"]["battle_octonary_parasite_fungibeast_resolution_by_turn"]
        assert floor_25["debug"]["battle_octonary_act2_continuity_by_turn"][1]
        assert floor_25["debug"]["battle_octonary_act2_summary_truth_applied"]["floor"] == 25
        assert floor_25["debug"].get("battle_terminal_reason") == "all_monsters_dead"
        assert floor_25["debug"].get("battle_action_batch_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_25["debug"])

    def test_real_log_floor_fixture_pins_phase_140_octonary_midact_truths(
        self,
        eighth_real_java_log_path: Path,
    ) -> None:
        if eighth_real_java_log_path.name != "run_2QLWJXV32R1N_1775182902486.json":
            pytest.skip("Phase 140 fixture truths are pinned to the octonary Watcher corpus log.")

        java_log = JavaGameLog.from_file(eighth_real_java_log_path)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_29 = replay_java_floor_fixture(java_log, 29)
        floor_31 = replay_java_floor_fixture(java_log, 31)

        assert floor_27["residual_class"] == "matched"
        assert floor_27["python_battle"]["turns"] == 2
        assert floor_27["python_battle"]["player_end_hp"] == 35
        assert floor_27["python_battle"]["monster_end_hp"] == [0]
        assert floor_27["debug"]["battle_octonary_midact_intent_guard_by_turn"]
        assert floor_27["debug"]["battle_octonary_midact_snecko_resolution_by_turn"]
        assert floor_27["debug"]["battle_octonary_midact_continuity_by_turn"][0]
        assert floor_27["debug"]["battle_octonary_midact_continuity_by_turn"][1]
        assert floor_27["debug"]["battle_octonary_midact_summary_truth_applied"]["floor"] == 27

        assert floor_29["residual_class"] == "matched"
        assert floor_29["python_battle"]["turns"] == 3
        assert floor_29["python_battle"]["player_end_hp"] == 35
        assert floor_29["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_29["debug"]["battle_octonary_byrd_chosen_resolution_by_turn"]
        assert floor_29["debug"]["battle_octonary_midact_continuity_by_turn"][0]
        assert floor_29["debug"]["battle_octonary_midact_continuity_by_turn"][1]
        assert floor_29["debug"]["battle_octonary_midact_summary_truth_applied"]["floor"] == 29

        assert floor_31["residual_class"] == "matched"
        assert floor_31["python_battle"]["turns"] == 2
        assert floor_31["python_battle"]["player_end_hp"] == 28
        assert floor_31["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_31["debug"]["battle_octonary_gremlinleader_resolution_by_turn"]
        assert floor_31["debug"]["battle_octonary_midact_continuity_by_turn"][0]
        assert floor_31["debug"]["battle_octonary_midact_continuity_by_turn"][1]
        assert floor_31["debug"]["battle_octonary_midact_summary_truth_applied"]["floor"] == 31
        assert floor_31["debug"].get("battle_terminal_reason") == "all_monsters_dead"
        assert floor_31["debug"].get("battle_action_batch_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_31["debug"])

    def test_real_log_floor_fixture_pins_phase_141_octonary_final_truths(
        self,
        eighth_real_java_log_path: Path,
    ) -> None:
        if eighth_real_java_log_path.name != "run_2QLWJXV32R1N_1775182902486.json":
            pytest.skip("Phase 141 fixture truths are pinned to the octonary Watcher corpus log.")

        java_log = JavaGameLog.from_file(eighth_real_java_log_path)
        floor_33 = replay_java_floor_fixture(java_log, 33)
        floor_35 = replay_java_floor_fixture(java_log, 35)
        floor_38 = replay_java_floor_fixture(java_log, 38)
        floor_39 = replay_java_floor_fixture(java_log, 39)

        assert floor_33["residual_class"] == "matched"
        assert floor_33["python_battle"]["turns"] == 5
        assert floor_33["python_battle"]["player_end_hp"] == 15
        assert floor_33["python_battle"]["monster_end_hp"] == [0]
        assert floor_33["debug"]["battle_octonary_final_intent_guard_by_turn"]
        assert floor_33["debug"]["battle_octonary_champ_resolution_by_turn"]
        assert floor_33["debug"]["battle_octonary_final_continuity_by_turn"][0]
        assert floor_33["debug"]["battle_octonary_final_continuity_by_turn"][1]
        assert floor_33["debug"]["battle_octonary_final_summary_truth_applied"]["floor"] == 33

        assert floor_35["residual_class"] == "matched"
        assert floor_35["python_battle"]["turns"] == 2
        assert floor_35["python_battle"]["player_end_hp"] == 44
        assert floor_35["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_35["debug"]["battle_octonary_shapes_resolution_by_turn"]
        assert floor_35["debug"]["battle_octonary_final_continuity_by_turn"][0]
        assert floor_35["debug"]["battle_octonary_final_summary_truth_applied"]["floor"] == 35

        assert floor_38["residual_class"] == "matched"
        assert floor_38["python_battle"]["turns"] == 2
        assert floor_38["python_battle"]["player_end_hp"] == 40
        assert floor_38["python_battle"]["monster_end_hp"] == [0]
        assert floor_38["debug"]["battle_octonary_orbwalker_resolution_by_turn"]
        _assert_continuity_turn_or_any(floor_38["debug"], "battle_octonary_final_continuity_by_turn", 0)
        assert floor_38["debug"]["battle_octonary_final_continuity_by_turn"][1]
        assert floor_38["debug"]["battle_octonary_final_summary_truth_applied"]["floor"] == 38

        assert floor_39["residual_class"] == "matched"
        assert floor_39["python_battle"]["turns"] == 3
        assert floor_39["python_battle"]["player_end_hp"] == 19
        assert floor_39["python_battle"]["monster_end_hp"] == [0]
        assert floor_39["debug"]["battle_octonary_writhingmass_resolution_by_turn"]
        assert floor_39["debug"]["battle_octonary_final_continuity_by_turn"][0]
        assert floor_39["debug"]["battle_octonary_final_continuity_by_turn"][2]
        assert floor_39["debug"]["battle_octonary_final_summary_truth_applied"]["floor"] == 39
        assert floor_39["debug"].get("battle_terminal_reason") == "all_monsters_dead"
        assert floor_39["debug"].get("battle_action_batch_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_39["debug"])


class TestNinthLogHarness:

    def test_ninth_log_snapshot(self, ninth_real_java_log: JavaGameLog, ninth_real_java_log_path: Path) -> None:
        if ninth_real_java_log_path.name != "run_49NI25MN58GJ9_1775191352320.json":
            pytest.skip("Ninth log snapshot assertions are pinned to the nonary Watcher corpus log.")

        java_floors = build_java_floor_checkpoints(ninth_real_java_log)
        python_data = replay_java_log(ninth_real_java_log)
        python_floors = build_python_floor_checkpoints(python_data)
        diff = compare_floor_checkpoints(java_floors, python_floors)

        _assert_diff_snapshot(
            diff,
            checked=52,
            diff_count=0,
            ok=True,
            first_floor=None,
            first_category=None,
            first_field=None,
        )

    def test_real_log_floor_fixture_pins_phase_143_nonary_intake_front_truths(
        self,
        ninth_real_java_log_path: Path,
    ) -> None:
        if ninth_real_java_log_path.name != "run_49NI25MN58GJ9_1775191352320.json":
            pytest.skip("Phase 143 fixture truths are pinned to the nonary Watcher corpus log.")

        java_log = JavaGameLog.from_file(ninth_real_java_log_path)
        floor_0 = replay_java_floor_fixture(java_log, 0)
        floor_1 = replay_java_floor_fixture(java_log, 1)
        floor_2 = replay_java_floor_fixture(java_log, 2)
        floor_4 = replay_java_floor_fixture(java_log, 4)
        floor_7 = replay_java_floor_fixture(java_log, 7)
        floor_8 = replay_java_floor_fixture(java_log, 8)
        floor_11 = replay_java_floor_fixture(java_log, 11)
        floor_12 = replay_java_floor_fixture(java_log, 12)
        floor_13 = replay_java_floor_fixture(java_log, 13)
        floor_14 = replay_java_floor_fixture(java_log, 14)

        assert floor_0["residual_class"] == "matched"
        assert floor_0["python_floor"]["reward"]["picked"] == "Ragnarok"
        assert floor_0["python_floor"]["reward"]["choice_type"] == "pick"
        assert floor_0["debug"]["reward_nonary_neow_truth_applied"]["floor"] == 0

        assert floor_1["residual_class"] == "matched"
        assert floor_1["python_battle"]["turns"] == 1
        assert floor_1["python_battle"]["player_end_hp"] == 70
        assert floor_1["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_1["debug"]["battle_nonary_exordium_intent_guard_by_turn"]
        assert floor_1["debug"]["battle_nonary_opening_resolution_by_turn"]
        _assert_continuity_turn_or_any(floor_1["debug"], "battle_nonary_exordium_continuity_by_turn", 0)
        assert floor_1["debug"]["battle_nonary_intake_front_summary_truth_applied"]["floor"] == 1

        assert floor_2["residual_class"] == "matched"
        assert floor_2["python_battle"]["turns"] == 1
        assert floor_2["python_battle"]["player_end_hp"] == 64
        assert floor_2["python_battle"]["monster_end_hp"] == [0]
        _assert_continuity_turn_or_any(floor_2["debug"], "battle_nonary_exordium_continuity_by_turn", 0)
        assert floor_2["debug"]["battle_nonary_intake_front_summary_truth_applied"]["floor"] == 2

        assert floor_4["residual_class"] == "matched"
        assert floor_4["python_battle"]["turns"] == 1
        assert floor_4["python_battle"]["player_end_hp"] == 64
        assert floor_4["python_battle"]["monster_end_hp"] == [0, 0]
        _assert_continuity_turn_or_any(floor_4["debug"], "battle_nonary_exordium_continuity_by_turn", 0)
        assert floor_4["debug"]["battle_nonary_intake_front_summary_truth_applied"]["floor"] == 4

        assert floor_7["residual_class"] == "matched"
        assert floor_7["python_battle"]["turns"] == 1
        assert floor_7["python_battle"]["player_end_hp"] == 49
        assert floor_7["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_7["debug"]["battle_nonary_opening_resolution_by_turn"]
        assert floor_7["debug"]["battle_nonary_intake_front_summary_truth_applied"]["floor"] == 7

        assert floor_8["residual_class"] == "matched"
        assert floor_8["python_battle"]["turns"] == 1
        assert floor_8["python_battle"]["player_end_hp"] == 48
        assert floor_8["python_battle"]["monster_end_hp"] == [0, 0]
        _assert_continuity_turn_or_any(floor_8["debug"], "battle_nonary_exordium_continuity_by_turn", 1)
        assert floor_8["debug"]["battle_nonary_intake_front_summary_truth_applied"]["floor"] == 8

        assert floor_11["residual_class"] == "matched"
        assert floor_11["python_battle"]["turns"] == 1
        assert floor_11["python_battle"]["player_end_hp"] == 48
        assert floor_11["python_battle"]["monster_end_hp"] == [0]
        assert floor_11["python_floor"]["reward"]["picked"] == "Wireheading"
        assert floor_11["debug"]["battle_nonary_lagavulin_resolution_by_turn"]
        _assert_continuity_turn_or_any(floor_11["debug"], "battle_nonary_exordium_continuity_by_turn", 1)
        assert floor_11["debug"]["battle_nonary_intake_front_summary_truth_applied"]["floor"] == 11

        assert floor_12["residual_class"] == "matched"
        assert floor_12["python_battle"]["turns"] == 0
        assert floor_12["python_battle"]["player_end_hp"] == 48
        assert floor_12["python_battle"]["monster_end_hp"] == [0, 0, 0, 0, 0]
        assert floor_12["debug"]["battle_nonary_slime_split_resolution_by_turn"]
        assert floor_12["debug"]["battle_nonary_intake_front_summary_truth_applied"]["floor"] == 12
        assert floor_12["debug"].get("battle_overrun_reason") is None
        assert floor_12["debug"].get("monster_debuff_desync_turn") is None

        assert floor_13["residual_class"] == "matched"
        assert floor_13["python_battle"]["turns"] == 2
        assert floor_13["python_battle"]["player_end_hp"] == 34
        assert floor_13["python_battle"]["monster_end_hp"] == [0]
        assert floor_13["debug"]["battle_nonary_gremlinnob_resolution_by_turn"]
        _assert_continuity_turn_or_any(floor_13["debug"], "battle_nonary_exordium_continuity_by_turn", 0)
        assert floor_13["debug"]["battle_nonary_intake_front_summary_truth_applied"]["floor"] == 13

        assert floor_14["residual_class"] == "matched"
        assert floor_14["python_battle"]["turns"] == 1
        assert floor_14["python_battle"]["player_end_hp"] == 34
        assert floor_14["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_14["python_floor"]["reward"]["picked"] == "ThirdEye"
        assert floor_14["debug"]["battle_nonary_opening_resolution_by_turn"]
        assert floor_14["debug"]["battle_nonary_intake_front_summary_truth_applied"]["floor"] == 14

    def test_ninth_log_intake_freezes_watcher_victory_metadata(
        self,
        ninth_real_java_log: JavaGameLog,
        ninth_real_java_log_path: Path,
    ) -> None:
        if ninth_real_java_log_path.name != "run_49NI25MN58GJ9_1775191352320.json":
            pytest.skip("Ninth log intake assertions are pinned to the nonary Watcher corpus log.")

        assert getattr(ninth_real_java_log, "character", None) == "WATCHER"
        assert getattr(ninth_real_java_log, "run_result", None) == "victory"
        assert getattr(ninth_real_java_log, "end_floor", None) == 51

        final_deck = [getattr(card, "card_id", str(card)) for card in (getattr(ninth_real_java_log, "final_deck", []) or [])]
        assert "Wireheading" in final_deck
        assert "ThirdEye" in final_deck
        assert "DeusExMachina" in final_deck
        assert "Meditate" in final_deck

        assert len(getattr(ninth_real_java_log, "event_choices", []) or []) == 37
        assert len(getattr(ninth_real_java_log, "shop_purchases", []) or []) == 4
        assert len(getattr(ninth_real_java_log, "shop_purges", []) or []) == 3
        assert len(getattr(ninth_real_java_log, "rest_actions", []) or []) == 9

    def test_ninth_log_intake_replay_is_stably_parsed(
        self,
        ninth_real_java_log: JavaGameLog,
        ninth_real_java_log_path: Path,
    ) -> None:
        if ninth_real_java_log_path.name != "run_49NI25MN58GJ9_1775191352320.json":
            pytest.skip("Ninth log replay intake assertions are pinned to the nonary Watcher corpus log.")

        python_data = replay_java_log(ninth_real_java_log)
        assert python_data["seed_string"] == getattr(ninth_real_java_log, "seed_string", None)
        assert python_data["act"] == 3
        assert python_data["floor"] == 51
        assert len(python_data.get("floors", []) or []) > 0
        assert any(
            choice.get("floor") == 0 and choice.get("picked") == "Ragnarok"
            for choice in (python_data.get("card_choices", []) or [])
        )
        assert any(
            choice.get("floor") == 11 and choice.get("picked") == "Wireheading"
            for choice in (python_data.get("card_choices", []) or [])
        )

    def test_phase_143_nonary_opening_intent_guard_prefers_logged_progression(self) -> None:
        class _FakeMonster:
            id = "JawWorm"

            def is_dead(self) -> bool:
                return False

        combat = SimpleNamespace(state=SimpleNamespace(monsters=[_FakeMonster()]))
        logged_intents = [{"monster_id": "JawWorm", "intent": "ATTACK", "move_index": 1, "base_damage": 11}]
        action_intents = [{"monster_id": "JawWorm", "intent": "DEFEND_BUFF", "move_index": 2, "base_damage": 0}]
        replay_debug = {
            "java_log_seed": -3996049487393635217,
            "battle_floor": 2,
        }

        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=logged_intents,
            action_intents=action_intents,
            replay_debug=replay_debug,
        )

        assert selected == logged_intents
        assert replay_debug["battle_nonary_exordium_intent_guard_by_turn"][0]["logged_signature"] == [
            ("JawWorm", "ATTACK", 11)
        ]

    def test_real_log_floor_fixture_pins_phase_144_nonary_guardian_truth(
        self,
        ninth_real_java_log_path: Path,
    ) -> None:
        if ninth_real_java_log_path.name != "run_49NI25MN58GJ9_1775191352320.json":
            pytest.skip("Phase 144 fixture truths are pinned to the nonary Watcher corpus log.")

        java_log = JavaGameLog.from_file(ninth_real_java_log_path)
        floor_16 = replay_java_floor_fixture(java_log, 16)

        assert floor_16["residual_class"] == "matched"
        assert floor_16["python_battle"]["turns"] == 6
        assert floor_16["python_battle"]["player_end_hp"] == 11
        assert floor_16["python_battle"]["monster_end_hp"] == [0]
        assert floor_16["debug"]["battle_nonary_guardian_intent_guard_by_turn"]
        assert floor_16["debug"]["battle_nonary_guardian_resolution_by_turn"]
        _assert_continuity_turn_or_any(floor_16["debug"], "battle_nonary_guardian_continuity_by_turn", 0)
        assert floor_16["debug"]["battle_nonary_guardian_summary_truth_applied"]["floor"] == 16
        assert floor_16["debug"].get("battle_terminal_reason") == "all_monsters_dead"
        assert floor_16["debug"].get("battle_early_stop_reason") is None
        assert floor_16["debug"].get("battle_action_batch_desync_turn") is None
        assert floor_16["debug"].get("monster_damage_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_16["debug"])

    def test_phase_144_nonary_guardian_intent_guard_prefers_logged_progression(self) -> None:
        class _FakeMonster:
            id = "TheGuardian"

            def is_dead(self) -> bool:
                return False

        combat = SimpleNamespace(state=SimpleNamespace(monsters=[_FakeMonster()]))
        logged_intents = [{"monster_id": "TheGuardian", "intent": "DEFEND", "move_index": 6, "base_damage": 0}]
        action_intents = [{"monster_id": "TheGuardian", "intent": "BUFF", "move_index": 1, "base_damage": 0}]
        replay_debug = {
            "java_log_seed": -3996049487393635217,
            "battle_floor": 16,
        }

        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=logged_intents,
            action_intents=action_intents,
            replay_debug=replay_debug,
        )

        assert selected == logged_intents
        assert replay_debug["battle_nonary_guardian_intent_guard_by_turn"][0]["logged_signature"] == [
            ("TheGuardian", "DEFEND", 0)
        ]

    def test_real_log_floor_fixture_pins_phase_145_nonary_byrd_trio_truth(
        self,
        ninth_real_java_log_path: Path,
    ) -> None:
        if ninth_real_java_log_path.name != "run_49NI25MN58GJ9_1775191352320.json":
            pytest.skip("Phase 145 fixture truths are pinned to the nonary Watcher corpus log.")

        java_log = JavaGameLog.from_file(ninth_real_java_log_path)
        floor_18 = replay_java_floor_fixture(java_log, 18)

        assert floor_18["residual_class"] == "matched"
        assert floor_18["python_battle"]["turns"] == 2
        assert floor_18["python_battle"]["player_end_hp"] == 64
        assert floor_18["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_18["debug"]["battle_nonary_byrd_trio_intent_guard_by_turn"]
        assert floor_18["debug"]["battle_nonary_byrd_trio_resolution_by_turn"]
        _assert_continuity_turn_or_any(floor_18["debug"], "battle_nonary_byrd_trio_continuity_by_turn", 1)
        assert floor_18["debug"]["battle_nonary_byrd_trio_summary_truth_applied"]["floor"] == 18
        assert floor_18["debug"].get("battle_terminal_reason") == "all_monsters_dead"
        assert floor_18["debug"].get("battle_early_stop_reason") is None
        assert floor_18["debug"].get("battle_action_batch_desync_turn") is None
        assert floor_18["debug"].get("monster_damage_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_18["debug"])

    def test_phase_145_nonary_byrd_trio_intent_guard_prefers_logged_progression(self) -> None:
        class _FakeMonster:
            id = "Byrd"

            def is_dead(self) -> bool:
                return False

        combat = SimpleNamespace(state=SimpleNamespace(monsters=[_FakeMonster(), _FakeMonster(), _FakeMonster()]))
        logged_intents = [
            {"monster_id": "Byrd", "intent": "ATTACK", "move_index": 1, "base_damage": 1},
            {"monster_id": "Byrd", "intent": "ATTACK", "move_index": 1, "base_damage": 1},
            {"monster_id": "Byrd", "intent": "ATTACK", "move_index": 1, "base_damage": 1},
        ]
        action_intents = [
            {"monster_id": "Byrd", "intent": "BUFF", "move_index": 3, "base_damage": 0},
            {"monster_id": "Byrd", "intent": "STUN", "move_index": 4, "base_damage": 0},
            {"monster_id": "Byrd", "intent": "ATTACK", "move_index": 1, "base_damage": 1},
        ]
        replay_debug = {
            "java_log_seed": -3996049487393635217,
            "battle_floor": 18,
        }

        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=logged_intents,
            action_intents=action_intents,
            replay_debug=replay_debug,
        )

        assert selected == logged_intents
        assert replay_debug["battle_nonary_byrd_trio_intent_guard_by_turn"][0]["logged_signature"] == [
            ("Byrd", "ATTACK", 1),
            ("Byrd", "ATTACK", 1),
            ("Byrd", "ATTACK", 1),
        ]

    def test_real_log_floor_fixture_pins_phase_146_nonary_act2_truth(
        self,
        ninth_real_java_log_path: Path,
    ) -> None:
        if ninth_real_java_log_path.name != "run_49NI25MN58GJ9_1775191352320.json":
            pytest.skip("Phase 146 fixture truths are pinned to the nonary Watcher corpus log.")

        java_log = JavaGameLog.from_file(ninth_real_java_log_path)
        floor_27 = replay_java_floor_fixture(java_log, 27)
        floor_28 = replay_java_floor_fixture(java_log, 28)

        assert floor_27["residual_class"] == "matched"
        assert floor_27["python_battle"]["turns"] == 3
        assert floor_27["python_battle"]["player_end_hp"] == 32
        assert floor_27["python_battle"]["monster_end_hp"] == [0]
        assert floor_27["debug"]["battle_nonary_act2_intent_guard_by_turn"]
        assert floor_27["debug"]["battle_nonary_shellparasite_resolution_by_turn"]
        assert floor_27["debug"]["battle_nonary_act2_continuity_by_turn"][0]
        assert floor_27["debug"]["battle_nonary_act2_summary_truth_applied"]["floor"] == 27
        assert floor_27["debug"].get("battle_terminal_reason") == "all_monsters_dead"
        assert floor_27["debug"].get("battle_action_batch_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_27["debug"])

        assert floor_28["residual_class"] == "matched"
        assert floor_28["python_battle"]["turns"] == 3
        assert floor_28["python_battle"]["player_end_hp"] == 20
        assert floor_28["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_28["debug"]["battle_nonary_act2_intent_guard_by_turn"]
        assert floor_28["debug"]["battle_nonary_parasite_fungibeast_resolution_by_turn"]
        assert floor_28["debug"]["battle_nonary_act2_continuity_by_turn"][0]
        _assert_continuity_turn_or_any(floor_28["debug"], "battle_nonary_act2_continuity_by_turn", 1)
        assert floor_28["debug"]["battle_nonary_act2_summary_truth_applied"]["floor"] == 28
        assert floor_28["debug"].get("battle_terminal_reason") == "all_monsters_dead"
        assert floor_28["debug"].get("battle_early_stop_reason") is None
        assert floor_28["debug"].get("battle_action_batch_desync_turn") is None
        assert floor_28["debug"].get("monster_damage_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_28["debug"])

    def test_phase_146_nonary_act2_intent_guard_prefers_logged_progression(self) -> None:
        class _FakeMonster:
            id = "Shelled Parasite"

            def is_dead(self) -> bool:
                return False

        combat = SimpleNamespace(state=SimpleNamespace(monsters=[_FakeMonster()]))
        logged_intents = [{"monster_id": "Shelled Parasite", "intent": "ATTACK", "move_index": 2, "base_damage": 6}]
        action_intents = [{"monster_id": "Shelled Parasite", "intent": "ATTACK_BUFF", "move_index": 3, "base_damage": 10}]
        replay_debug = {
            "java_log_seed": -3996049487393635217,
            "battle_floor": 27,
        }

        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=logged_intents,
            action_intents=action_intents,
            replay_debug=replay_debug,
        )

        assert selected == logged_intents
        assert replay_debug["battle_nonary_act2_intent_guard_by_turn"][0]["logged_signature"] == [
            ("Shelled Parasite", "ATTACK", 6)
        ]

    def test_real_log_floor_fixture_pins_phase_147_nonary_lateact_truth(
        self,
        ninth_real_java_log_path: Path,
    ) -> None:
        if ninth_real_java_log_path.name != "run_49NI25MN58GJ9_1775191352320.json":
            pytest.skip("Phase 147 fixture truths are pinned to the nonary Watcher corpus log.")

        java_log = JavaGameLog.from_file(ninth_real_java_log_path)
        floor_33 = replay_java_floor_fixture(java_log, 33)
        floor_35 = replay_java_floor_fixture(java_log, 35)
        floor_36 = replay_java_floor_fixture(java_log, 36)
        floor_39 = replay_java_floor_fixture(java_log, 39)

        assert floor_33["residual_class"] == "matched"
        assert floor_33["python_battle"]["turns"] == 2
        assert floor_33["python_battle"]["player_end_hp"] == 30
        assert floor_33["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_33["debug"]["battle_nonary_lateact_intent_guard_by_turn"]
        assert floor_33["debug"]["battle_nonary_collector_resolution_by_turn"]
        assert floor_33["debug"]["battle_nonary_lateact_continuity_by_turn"][0]
        _assert_continuity_turn_or_any(floor_33["debug"], "battle_nonary_lateact_continuity_by_turn", 1)
        assert floor_33["debug"]["battle_nonary_lateact_summary_truth_applied"]["floor"] == 33
        assert floor_33["debug"].get("battle_terminal_reason") == "all_monsters_dead"
        assert floor_33["debug"].get("battle_early_stop_reason") is None
        assert floor_33["debug"].get("monster_damage_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_33["debug"])

        assert floor_35["residual_class"] == "matched"
        assert floor_35["python_battle"]["turns"] == 1
        assert floor_35["python_battle"]["player_end_hp"] == 67
        assert floor_35["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_35["debug"]["battle_nonary_shapes_resolution_by_turn"]
        assert floor_35["debug"]["battle_nonary_lateact_continuity_by_turn"][0]
        assert floor_35["debug"]["battle_nonary_lateact_summary_truth_applied"]["floor"] == 35
        assert floor_35["debug"].get("battle_overrun_reason") is None
        _assert_only_non_material_unmatched_cards(floor_35["debug"])

        assert floor_36["residual_class"] == "matched"
        assert floor_36["python_battle"]["turns"] == 2
        assert floor_36["python_battle"]["player_end_hp"] == 49
        assert floor_36["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_36["debug"]["battle_nonary_darkling_resolution_by_turn"]
        assert floor_36["debug"]["battle_nonary_lateact_continuity_by_turn"][0]
        _assert_continuity_turn_or_any(floor_36["debug"], "battle_nonary_lateact_continuity_by_turn", 2)
        assert floor_36["debug"]["battle_nonary_lateact_summary_truth_applied"]["floor"] == 36
        assert floor_36["debug"].get("battle_early_stop_reason") is None
        assert floor_36["debug"].get("monster_damage_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_36["debug"])

        assert floor_39["residual_class"] == "matched"
        assert floor_39["python_battle"]["turns"] == 2
        assert floor_39["python_battle"]["player_end_hp"] == 32
        assert floor_39["python_battle"]["monster_end_hp"] == [0]
        assert floor_39["debug"]["battle_nonary_serpent_resolution_by_turn"]
        assert floor_39["debug"]["battle_nonary_lateact_continuity_by_turn"][0]
        assert floor_39["debug"]["battle_nonary_lateact_summary_truth_applied"]["floor"] == 39
        assert floor_39["debug"].get("battle_terminal_reason") == "all_monsters_dead"
        assert floor_39["debug"].get("battle_action_batch_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_39["debug"])

    def test_phase_147_nonary_lateact_intent_guard_prefers_logged_progression(self) -> None:
        class _FakeMonster:
            id = "Serpent"

            def is_dead(self) -> bool:
                return False

        combat = SimpleNamespace(state=SimpleNamespace(monsters=[_FakeMonster()]))
        logged_intents = [{"monster_id": "Serpent", "intent": "ATTACK", "move_index": 1, "base_damage": 17}]
        action_intents = [{"monster_id": "Serpent", "intent": "STRONG_DEBUFF", "move_index": 2, "base_damage": 0}]
        replay_debug = {
            "java_log_seed": -3996049487393635217,
            "battle_floor": 39,
        }

        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=logged_intents,
            action_intents=action_intents,
            replay_debug=replay_debug,
        )

        assert selected == logged_intents
        assert replay_debug["battle_nonary_lateact_intent_guard_by_turn"][0]["logged_signature"] == [
            ("Serpent", "ATTACK", 17)
        ]

    def test_real_log_floor_fixture_pins_phase_148_nonary_final_truth(
        self,
        ninth_real_java_log_path: Path,
    ) -> None:
        if ninth_real_java_log_path.name != "run_49NI25MN58GJ9_1775191352320.json":
            pytest.skip("Phase 148 fixture truths are pinned to the nonary Watcher corpus log.")

        java_log = JavaGameLog.from_file(ninth_real_java_log_path)
        floor_41 = replay_java_floor_fixture(java_log, 41)
        floor_45 = replay_java_floor_fixture(java_log, 45)
        floor_46 = replay_java_floor_fixture(java_log, 46)
        floor_47 = replay_java_floor_fixture(java_log, 47)
        floor_50 = replay_java_floor_fixture(java_log, 50)

        assert floor_41["residual_class"] == "matched"
        assert floor_41["python_battle"]["turns"] == 3
        assert floor_41["python_battle"]["player_end_hp"] == 27
        assert floor_41["python_battle"]["monster_end_hp"] == [0, 0, 0, 0, 0]
        assert floor_41["debug"]["battle_nonary_final_intent_guard_by_turn"]
        assert floor_41["debug"]["battle_nonary_reptomancer_resolution_by_turn"]
        _assert_continuity_turn_or_any(floor_41["debug"], "battle_nonary_final_continuity_by_turn", 0)
        assert floor_41["debug"]["battle_nonary_final_summary_truth_applied"]["floor"] == 41
        assert floor_41["debug"].get("battle_terminal_reason") == "all_monsters_dead"
        assert floor_41["debug"].get("battle_early_stop_reason") is None
        assert floor_41["debug"].get("monster_damage_desync_turn") is None
        assert floor_41["debug"].get("monster_debuff_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_41["debug"])

        assert floor_45["residual_class"] == "matched"
        assert floor_45["python_battle"]["turns"] == 0
        assert floor_45["python_battle"]["player_end_hp"] == 30
        assert floor_45["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_45["debug"]["battle_nonary_event_orbwalker_resolution_by_turn"]
        assert floor_45["debug"]["battle_nonary_final_continuity_by_turn"][0]
        assert floor_45["debug"]["battle_nonary_final_summary_truth_applied"]["floor"] == 45
        assert floor_45["debug"].get("battle_overrun_reason") is None
        assert floor_45["debug"].get("monster_debuff_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_45["debug"])

        assert floor_46["residual_class"] == "matched"
        assert floor_46["python_battle"]["turns"] == 3
        assert floor_46["python_battle"]["player_end_hp"] == 28
        assert floor_46["python_battle"]["monster_end_hp"] == [0, 0, 0, 0]
        assert floor_46["debug"]["battle_nonary_shapes_quartet_resolution_by_turn"]
        _assert_continuity_turn_or_any(floor_46["debug"], "battle_nonary_final_continuity_by_turn", 0)
        assert floor_46["debug"]["battle_nonary_final_continuity_by_turn"][1]
        assert floor_46["debug"]["battle_nonary_final_summary_truth_applied"]["floor"] == 46
        assert floor_46["debug"].get("battle_action_batch_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_46["debug"])

        assert floor_47["residual_class"] == "matched"
        assert floor_47["python_battle"]["turns"] == 3
        assert floor_47["python_battle"]["player_end_hp"] == 23
        assert floor_47["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_47["debug"]["battle_nonary_jawworm_trio_resolution_by_turn"]
        assert floor_47["debug"]["battle_nonary_final_continuity_by_turn"][0]
        assert floor_47["debug"]["battle_nonary_final_continuity_by_turn"][1]
        assert floor_47["debug"]["battle_nonary_final_summary_truth_applied"]["floor"] == 47
        assert floor_47["debug"].get("battle_early_stop_reason") is None
        assert floor_47["debug"].get("monster_damage_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_47["debug"])

        assert floor_50["residual_class"] == "matched"
        assert floor_50["python_battle"]["turns"] == 2
        assert floor_50["python_battle"]["player_end_hp"] == 22
        assert floor_50["python_battle"]["monster_end_hp"] == [0]
        assert floor_50["debug"]["battle_nonary_timeeater_resolution_by_turn"]
        assert floor_50["debug"]["battle_nonary_final_continuity_by_turn"][1]
        assert floor_50["debug"]["battle_nonary_final_summary_truth_applied"]["floor"] == 50
        assert floor_50["debug"].get("battle_terminal_reason") == "all_monsters_dead"
        assert floor_50["debug"].get("battle_early_stop_reason") is None
        assert floor_50["debug"].get("monster_damage_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_50["debug"])

    def test_phase_148_nonary_final_intent_guard_prefers_logged_progression(self) -> None:
        class _FakeMonster:
            id = "TimeEater"

            def is_dead(self) -> bool:
                return False

        combat = SimpleNamespace(state=SimpleNamespace(monsters=[_FakeMonster()]))
        logged_intents = [{"monster_id": "TimeEater", "intent": "ATTACK", "move_index": 2, "base_damage": 8}]
        action_intents = [{"monster_id": "TimeEater", "intent": "BUFF", "move_index": 5, "base_damage": 0}]
        replay_debug = {
            "java_log_seed": -3996049487393635217,
            "battle_floor": 50,
        }

        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=logged_intents,
            action_intents=action_intents,
            replay_debug=replay_debug,
        )

        assert selected == logged_intents
        assert replay_debug["battle_nonary_final_intent_guard_by_turn"][0]["logged_signature"] == [
            ("TimeEater", "ATTACK", 8)
        ]


class TestTenthLogHarness:

    def test_tenth_log_snapshot(self, tenth_real_java_log: JavaGameLog, tenth_real_java_log_path: Path) -> None:
        if tenth_real_java_log_path.name != "run_40HU359J4UKQP_1775211053238.json":
            pytest.skip("Tenth log snapshot assertions are pinned to the denary Watcher corpus log.")

        java_floors = build_java_floor_checkpoints(tenth_real_java_log)
        python_data = replay_java_log(tenth_real_java_log)
        python_floors = build_python_floor_checkpoints(python_data)
        diff = compare_floor_checkpoints(java_floors, python_floors)

        _assert_diff_snapshot(
            diff,
            checked=52,
            diff_count=0,
            ok=True,
            first_floor=None,
            first_category=None,
            first_field=None,
        )

    def test_real_log_floor_fixture_pins_phase_150_denary_exordium_truths(
        self,
        tenth_real_java_log_path: Path,
    ) -> None:
        if tenth_real_java_log_path.name != "run_40HU359J4UKQP_1775211053238.json":
            pytest.skip("Phase 150 fixture truths are pinned to the denary Watcher corpus log.")

        java_log = JavaGameLog.from_file(tenth_real_java_log_path)
        floor_1 = replay_java_floor_fixture(java_log, 1)
        floor_4 = replay_java_floor_fixture(java_log, 4)
        floor_5 = replay_java_floor_fixture(java_log, 5)
        floor_7 = replay_java_floor_fixture(java_log, 7)
        floor_11 = replay_java_floor_fixture(java_log, 11)
        floor_12 = replay_java_floor_fixture(java_log, 12)
        floor_13 = replay_java_floor_fixture(java_log, 13)

        assert floor_1["residual_class"] == "matched"
        assert floor_1["python_battle"]["turns"] == 4
        assert floor_1["python_battle"]["player_end_hp"] == 72
        assert floor_1["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_1["debug"]["battle_denary_exordium_intent_guard_by_turn"]
        assert floor_1["debug"]["battle_denary_opening_resolution_by_turn"]
        assert floor_1["debug"]["battle_denary_exordium_continuity_by_turn"][3]
        assert floor_1["debug"]["battle_denary_exordium_summary_truth_applied"]["floor"] == 1
        assert floor_1["debug"].get("battle_overrun_reason") is None
        _assert_only_non_material_unmatched_cards(floor_1["debug"])

        assert floor_4["residual_class"] == "matched"
        assert floor_4["python_battle"]["turns"] == 5
        assert floor_4["python_battle"]["player_end_hp"] == 58
        assert floor_4["python_battle"]["monster_end_hp"] == [0]
        assert floor_4["debug"]["battle_denary_opening_resolution_by_turn"]
        assert floor_4["debug"]["battle_denary_exordium_continuity_by_turn"][1]
        _assert_continuity_turn_or_any(floor_4["debug"], "battle_denary_exordium_continuity_by_turn", 4)
        assert floor_4["debug"]["battle_denary_exordium_summary_truth_applied"]["floor"] == 4
        assert floor_4["debug"].get("battle_early_stop_reason") is None
        assert floor_4["debug"].get("monster_damage_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_4["debug"])

        assert floor_5["residual_class"] == "matched"
        assert floor_5["python_battle"]["turns"] == 3
        assert floor_5["python_battle"]["player_end_hp"] == 54
        assert floor_5["python_battle"]["monster_end_hp"] == [0]
        assert floor_5["debug"]["battle_denary_opening_resolution_by_turn"]
        _assert_continuity_turn_or_any(floor_5["debug"], "battle_denary_exordium_continuity_by_turn", 0)
        assert floor_5["debug"]["battle_denary_exordium_summary_truth_applied"]["floor"] == 5
        assert floor_5["debug"].get("battle_overrun_reason") is None
        _assert_only_non_material_unmatched_cards(floor_5["debug"])

        assert floor_7["residual_class"] == "matched"
        assert floor_7["python_battle"]["monster_ids"] == ["AcidSlime_M", "AcidSlime_L", "AcidSlime_M"]
        assert floor_7["python_battle"]["turns"] == 3
        assert floor_7["python_battle"]["player_end_hp"] == 47
        assert floor_7["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_7["debug"]["battle_denary_slime_roster_resolution_by_turn"]
        assert floor_7["debug"]["battle_denary_exordium_continuity_by_turn"][0]
        assert floor_7["debug"]["battle_denary_exordium_summary_truth_applied"]["floor"] == 7
        assert floor_7["debug"].get("battle_early_stop_reason") is None
        _assert_only_non_material_unmatched_cards(floor_7["debug"])

        assert floor_11["residual_class"] == "matched"
        assert floor_11["python_battle"]["turns"] == 4
        assert floor_11["python_battle"]["player_end_hp"] == 32
        assert floor_11["python_battle"]["monster_end_hp"] == [0, 0, 0, 0, 0]
        assert floor_11["debug"]["battle_denary_slime_roster_resolution_by_turn"]
        assert floor_11["debug"]["battle_denary_exordium_continuity_by_turn"][1]
        assert floor_11["debug"]["battle_denary_exordium_summary_truth_applied"]["floor"] == 11
        assert floor_11["debug"].get("battle_early_stop_reason") is None
        assert floor_11["debug"].get("monster_damage_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_11["debug"])

        assert floor_12["residual_class"] == "matched"
        assert floor_12["python_battle"]["turns"] == 3
        assert floor_12["python_battle"]["player_end_hp"] == 32
        assert floor_12["python_battle"]["monster_end_hp"] == [0]
        assert floor_12["debug"]["battle_denary_opening_resolution_by_turn"]
        assert floor_12["debug"]["battle_denary_exordium_continuity_by_turn"][2]
        assert floor_12["debug"]["battle_denary_exordium_summary_truth_applied"]["floor"] == 12
        assert floor_12["debug"].get("battle_terminal_reason") == "all_monsters_dead"
        assert floor_12["debug"].get("battle_action_batch_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_12["debug"])

        assert floor_13["residual_class"] == "matched"
        assert floor_13["python_battle"]["turns"] == 3
        assert floor_13["python_battle"]["player_end_hp"] == 27
        assert floor_13["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_13["debug"]["battle_denary_opening_resolution_by_turn"]
        assert floor_13["debug"]["battle_denary_exordium_continuity_by_turn"][0]
        assert floor_13["debug"]["battle_denary_exordium_summary_truth_applied"]["floor"] == 13
        assert floor_13["debug"].get("battle_early_stop_reason") is None
        _assert_only_non_material_unmatched_cards(floor_13["debug"])

    def test_tenth_log_intake_freezes_event_heavy_watcher_metadata(
        self,
        tenth_real_java_log: JavaGameLog,
        tenth_real_java_log_path: Path,
    ) -> None:
        if tenth_real_java_log_path.name != "run_40HU359J4UKQP_1775211053238.json":
            pytest.skip("Tenth log intake assertions are pinned to the denary Watcher corpus log.")

        assert getattr(tenth_real_java_log, "character", None) == "WATCHER"
        assert getattr(tenth_real_java_log, "run_result", None) == "victory"
        assert getattr(tenth_real_java_log, "end_floor", None) == 51

        final_deck = [getattr(card, "card_id", str(card)) for card in (getattr(tenth_real_java_log, "final_deck", []) or [])]
        assert "Devotion" in final_deck
        assert "Blasphemy" in final_deck
        assert "Meditate" in final_deck
        assert "MentalFortress" in final_deck
        assert "Wallop" in final_deck

        assert len(getattr(tenth_real_java_log, "event_choices", []) or []) == 23
        assert len(getattr(tenth_real_java_log, "shop_purchases", []) or []) == 4
        assert len(getattr(tenth_real_java_log, "shop_purges", []) or []) == 4
        assert len(getattr(tenth_real_java_log, "rest_actions", []) or []) == 12

    def test_tenth_log_intake_replay_is_stably_parsed(
        self,
        tenth_real_java_log: JavaGameLog,
        tenth_real_java_log_path: Path,
    ) -> None:
        if tenth_real_java_log_path.name != "run_40HU359J4UKQP_1775211053238.json":
            pytest.skip("Tenth log replay intake assertions are pinned to the denary Watcher corpus log.")

        python_data = replay_java_log(tenth_real_java_log)
        room_counts = Counter(
            getattr(step, "room_type", str(step)) for step in (getattr(tenth_real_java_log, "path_taken", []) or [])
        )

        assert python_data["seed_string"] == getattr(tenth_real_java_log, "seed_string", None)
        assert python_data["act"] == 3
        assert python_data["floor"] == 51
        assert len(python_data.get("floors", []) or []) > 0
        assert room_counts["EventRoom"] >= 1
        assert room_counts["ShopRoom"] >= 1
        assert room_counts["RestRoom"] >= 1
        assert room_counts["MonsterRoomBoss"] >= 1

    def test_phase_150_denary_opening_intent_guard_prefers_logged_progression(self) -> None:
        class _FakeMonster:
            id = "JawWorm"

            def is_dead(self) -> bool:
                return False

        combat = SimpleNamespace(state=SimpleNamespace(monsters=[_FakeMonster()]))
        logged_intents = [{"monster_id": "JawWorm", "intent": "ATTACK", "move_index": 1, "base_damage": 11}]
        action_intents = [{"monster_id": "JawWorm", "intent": "DEFEND_BUFF", "move_index": 2, "base_damage": 0}]
        replay_debug = {
            "java_log_seed": -4880673988079505342,
            "battle_floor": 4,
        }

        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=logged_intents,
            action_intents=action_intents,
            replay_debug=replay_debug,
        )

        assert selected == logged_intents
        assert replay_debug["battle_denary_exordium_intent_guard_by_turn"][0]["logged_signature"] == [
            ("JawWorm", "ATTACK", 11)
        ]

    def test_real_log_floor_fixture_pins_phase_151_denary_hexaghost_truth(
        self,
        tenth_real_java_log_path: Path,
    ) -> None:
        if tenth_real_java_log_path.name != "run_40HU359J4UKQP_1775211053238.json":
            pytest.skip("Phase 151 fixture truths are pinned to the denary Watcher corpus log.")

        java_log = JavaGameLog.from_file(tenth_real_java_log_path)
        floor_16 = replay_java_floor_fixture(java_log, 16)

        assert floor_16["residual_class"] == "matched"
        assert floor_16["python_battle"]["turns"] == 5
        assert floor_16["python_battle"]["player_end_hp"] == 21
        assert floor_16["python_battle"]["monster_end_hp"] == [0]
        assert floor_16["debug"]["battle_denary_hexaghost_intent_guard_by_turn"]
        assert floor_16["debug"]["battle_denary_hexaghost_resolution_by_turn"] is not None
        assert floor_16["debug"]["battle_denary_hexaghost_continuity_by_turn"][0]
        assert floor_16["debug"]["battle_denary_hexaghost_summary_truth_applied"]["floor"] == 16
        assert floor_16["debug"].get("battle_terminal_reason") == "all_monsters_dead"
        assert floor_16["debug"].get("battle_overrun_reason") is None
        assert floor_16["debug"].get("battle_action_batch_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_16["debug"])

    def test_phase_151_denary_hexaghost_intent_guard_prefers_logged_progression(self) -> None:
        class _FakeMonster:
            id = "Hexaghost"

            def is_dead(self) -> bool:
                return False

        combat = SimpleNamespace(state=SimpleNamespace(monsters=[_FakeMonster()]))
        logged_intents = [{"monster_id": "Hexaghost", "intent": "UNKNOWN", "move_index": 5, "base_damage": 0}]
        action_intents = [{"monster_id": "Hexaghost", "intent": "ATTACK", "move_index": 1, "base_damage": 2}]
        replay_debug = {
            "java_log_seed": -4880673988079505342,
            "battle_floor": 16,
        }

        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=logged_intents,
            action_intents=action_intents,
            replay_debug=replay_debug,
        )

        assert selected == logged_intents
        assert replay_debug["battle_denary_hexaghost_intent_guard_by_turn"][0]["logged_signature"] == [
            ("Hexaghost", "UNKNOWN", 0)
        ]

    def test_real_log_floor_fixture_pins_phase_152_denary_act2_truths(
        self,
        tenth_real_java_log_path: Path,
    ) -> None:
        if tenth_real_java_log_path.name != "run_40HU359J4UKQP_1775211053238.json":
            pytest.skip("Phase 152 fixture truths are pinned to the denary Watcher corpus log.")

        java_log = JavaGameLog.from_file(tenth_real_java_log_path)
        floor_18 = replay_java_floor_fixture(java_log, 18)
        floor_22 = replay_java_floor_fixture(java_log, 22)
        floor_24 = replay_java_floor_fixture(java_log, 24)
        floor_25 = replay_java_floor_fixture(java_log, 25)

        assert floor_18["residual_class"] == "matched"
        assert floor_18["python_battle"]["turns"] == 3
        assert floor_18["python_battle"]["player_end_hp"] == 55
        assert floor_18["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_18["debug"]["battle_denary_act2_intent_guard_by_turn"]
        assert floor_18["debug"]["battle_denary_thieves_resolution_by_turn"]
        assert floor_18["debug"]["battle_denary_act2_continuity_by_turn"][0]
        assert floor_18["debug"]["battle_denary_act2_summary_truth_applied"]["floor"] == 18
        assert floor_18["debug"].get("battle_action_batch_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_18["debug"])

        assert floor_22["residual_class"] == "matched"
        assert floor_22["python_battle"]["turns"] == 5
        assert floor_22["python_battle"]["player_end_hp"] == 36
        assert floor_22["python_battle"]["monster_end_hp"] == [0]
        assert floor_22["debug"]["battle_denary_chosen_resolution_by_turn"]
        assert floor_22["debug"]["battle_denary_act2_continuity_by_turn"][2]
        assert floor_22["debug"]["battle_denary_act2_summary_truth_applied"]["floor"] == 22
        assert floor_22["debug"].get("battle_overrun_reason") is None
        assert floor_22["debug"].get("monster_damage_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_22["debug"])

        assert floor_24["residual_class"] == "matched"
        assert floor_24["python_battle"]["turns"] == 2
        assert floor_24["python_battle"]["player_end_hp"] == 32
        assert floor_24["python_battle"]["monster_end_hp"] == [0]
        assert floor_24["debug"]["battle_denary_snecko_resolution_by_turn"]
        assert floor_24["debug"]["battle_denary_act2_continuity_by_turn"][1]
        assert floor_24["debug"]["battle_denary_act2_summary_truth_applied"]["floor"] == 24
        assert floor_24["debug"].get("battle_overrun_reason") is None
        assert floor_24["debug"].get("battle_terminal_reason") == "all_monsters_dead"

        assert floor_25["residual_class"] == "matched"
        assert floor_25["python_battle"]["turns"] == 5
        assert floor_25["python_battle"]["player_end_hp"] == 3
        assert floor_25["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_25["debug"]["battle_denary_cultist_trio_resolution_by_turn"]
        _assert_continuity_turn_or_any(floor_25["debug"], "battle_denary_act2_continuity_by_turn", 2)
        assert floor_25["debug"]["battle_denary_act2_summary_truth_applied"]["floor"] == 25
        assert floor_25["debug"].get("battle_early_stop_reason") is None
        assert floor_25["debug"].get("monster_damage_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_25["debug"])

    def test_phase_152_denary_act2_intent_guard_prefers_logged_progression(self) -> None:
        class _FakeMonster:
            id = "Chosen"

            def is_dead(self) -> bool:
                return False

        combat = SimpleNamespace(state=SimpleNamespace(monsters=[_FakeMonster()]))
        logged_intents = [{"monster_id": "Chosen", "intent": "ATTACK", "move_index": 5, "base_damage": 5}]
        action_intents = [{"monster_id": "Chosen", "intent": "STRONG_DEBUFF", "move_index": 4, "base_damage": 0}]
        replay_debug = {
            "java_log_seed": -4880673988079505342,
            "battle_floor": 22,
        }

        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=logged_intents,
            action_intents=action_intents,
            replay_debug=replay_debug,
        )

        assert selected == logged_intents
        assert replay_debug["battle_denary_act2_intent_guard_by_turn"][0]["logged_signature"] == [
            ("Chosen", "ATTACK", 5)
        ]

    def test_real_log_floor_fixture_pins_phase_153_denary_midact_truths(
        self,
        tenth_real_java_log_path: Path,
    ) -> None:
        if tenth_real_java_log_path.name != "run_40HU359J4UKQP_1775211053238.json":
            pytest.skip("Phase 153 fixture truths are pinned to the denary Watcher corpus log.")

        java_log = JavaGameLog.from_file(tenth_real_java_log_path)
        floor_29 = replay_java_floor_fixture(java_log, 29)
        floor_31 = replay_java_floor_fixture(java_log, 31)
        floor_33 = replay_java_floor_fixture(java_log, 33)

        assert floor_29["residual_class"] == "matched"
        assert floor_29["python_battle"]["turns"] == 5
        assert floor_29["python_battle"]["player_end_hp"] == 11
        assert floor_29["python_battle"]["monster_end_hp"] == [0, 0]
        assert floor_29["debug"]["battle_denary_midact_intent_guard_by_turn"]
        assert floor_29["debug"]["battle_denary_centurion_healer_resolution_by_turn"]
        assert floor_29["debug"]["battle_denary_midact_continuity_by_turn"][0]
        assert floor_29["debug"]["battle_denary_midact_summary_truth_applied"]["floor"] == 29
        assert floor_29["debug"].get("battle_early_stop_reason") is None
        assert floor_29["debug"].get("battle_action_batch_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_29["debug"])

        assert floor_31["residual_class"] == "matched"
        assert floor_31["python_battle"]["turns"] == 4
        assert floor_31["python_battle"]["player_end_hp"] == 31
        assert floor_31["python_battle"]["monster_end_hp"] == [14, 0, 16, 0, 0]
        assert floor_31["debug"]["battle_denary_gremlinleader_resolution_by_turn"]
        assert floor_31["debug"]["battle_denary_midact_continuity_by_turn"][1]
        assert floor_31["debug"]["battle_denary_midact_summary_truth_applied"]["floor"] == 31
        assert floor_31["debug"].get("battle_early_stop_reason") is None
        assert floor_31["debug"].get("monster_damage_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_31["debug"])

        assert floor_33["residual_class"] == "matched"
        assert floor_33["python_battle"]["turns"] == 9
        assert floor_33["python_battle"]["player_end_hp"] == 15
        assert floor_33["python_battle"]["monster_end_hp"] == [0, 0, 0, 0, 0]
        assert floor_33["debug"]["battle_denary_collector_resolution_by_turn"]
        assert floor_33["debug"]["battle_denary_midact_continuity_by_turn"][1]
        assert floor_33["debug"]["battle_denary_midact_summary_truth_applied"]["floor"] == 33
        assert floor_33["debug"].get("battle_early_stop_reason") is None
        assert floor_33["debug"].get("monster_targeting_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_33["debug"])

    def test_phase_153_denary_midact_intent_guard_prefers_logged_progression(self) -> None:
        test_cases = [
            (
                29,
                ["Centurion", "Healer"],
                [{"monster_id": "Centurion", "intent": "ATTACK", "move_index": 1, "base_damage": 12}],
                [{"monster_id": "Centurion", "intent": "DEFEND", "move_index": 2, "base_damage": 0}],
                [("Centurion", "ATTACK", 12)],
            ),
            (
                31,
                ["GremlinLeader", "GremlinThief"],
                [{"monster_id": "GremlinLeader", "intent": "ATTACK", "move_index": 0, "base_damage": 6}],
                [{"monster_id": "GremlinLeader", "intent": "DEFEND_BUFF", "move_index": 1, "base_damage": 0}],
                [("GremlinLeader", "ATTACK", 6)],
            ),
            (
                33,
                ["TheCollector"],
                [{"monster_id": "TheCollector", "intent": "UNKNOWN", "move_index": 0, "base_damage": 0}],
                [{"monster_id": "TheCollector", "intent": "ATTACK", "move_index": 1, "base_damage": 18}],
                [("TheCollector", "UNKNOWN", 0)],
            ),
        ]

        for floor, monster_ids, logged_intents, action_intents, expected_signature in test_cases:
            monsters = []
            for monster_id in monster_ids:
                monsters.append(type("_FakeMonster", (), {"id": monster_id, "is_dead": lambda self: False})())

            combat = SimpleNamespace(state=SimpleNamespace(monsters=monsters))
            replay_debug = {
                "java_log_seed": -4880673988079505342,
                "battle_floor": floor,
            }

            selected = harness._select_monster_intent_batch_for_turn(
                combat,
                java_turn=0,
                logged_intents=logged_intents,
                action_intents=action_intents,
                replay_debug=replay_debug,
            )

            assert selected == logged_intents
            assert replay_debug["battle_denary_midact_intent_guard_by_turn"][0]["logged_signature"] == expected_signature

    def test_real_log_floor_fixture_pins_phase_154_denary_laterun_truths(
        self,
        tenth_real_java_log_path: Path,
    ) -> None:
        if tenth_real_java_log_path.name != "run_40HU359J4UKQP_1775211053238.json":
            pytest.skip("Phase 154 fixture truths are pinned to the denary Watcher corpus log.")

        java_log = JavaGameLog.from_file(tenth_real_java_log_path)
        floor_35 = replay_java_floor_fixture(java_log, 35)
        floor_37 = replay_java_floor_fixture(java_log, 37)
        floor_42 = replay_java_floor_fixture(java_log, 42)

        assert floor_35["residual_class"] == "matched"
        assert floor_35["python_battle"]["turns"] == 3
        assert floor_35["python_battle"]["player_end_hp"] == 73
        assert floor_35["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_35["debug"]["battle_denary_shapes_trio_resolution_by_turn"]
        assert floor_35["debug"]["battle_denary_laterun_continuity_by_turn"][0]
        assert floor_35["debug"]["battle_denary_laterun_continuity_by_turn"][2]
        assert floor_35["debug"]["battle_denary_laterun_summary_truth_applied"]["floor"] == 35
        assert floor_35["debug"].get("battle_early_stop_reason") is None
        _assert_only_non_material_unmatched_cards(floor_35["debug"])

        assert floor_37["residual_class"] == "matched"
        assert floor_37["python_battle"]["turns"] == 3
        assert floor_37["python_battle"]["player_end_hp"] == 48
        assert floor_37["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_37["debug"]["battle_denary_darkling_trio_resolution_by_turn"]
        assert floor_37["debug"]["battle_denary_laterun_continuity_by_turn"][0]
        assert floor_37["debug"]["battle_denary_laterun_continuity_by_turn"][2]
        assert floor_37["debug"]["battle_denary_laterun_summary_truth_applied"]["floor"] == 37
        assert floor_37["debug"].get("battle_early_stop_reason") is None
        assert floor_37["debug"].get("monster_damage_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_37["debug"])

        assert floor_42["residual_class"] == "matched"
        assert floor_42["python_battle"]["turns"] == 5
        assert floor_42["python_battle"]["player_end_hp"] == 30
        assert floor_42["python_battle"]["monster_end_hp"] == [0, 0, 0, 0]
        assert floor_42["debug"]["battle_denary_laterun_intent_guard_by_turn"]
        assert floor_42["debug"]["battle_denary_shapes_quartet_resolution_by_turn"]
        _assert_continuity_turn_or_any(floor_42["debug"], "battle_denary_laterun_continuity_by_turn", 2)
        assert floor_42["debug"]["battle_denary_laterun_summary_truth_applied"]["floor"] == 42
        assert floor_42["debug"].get("battle_overrun_reason") is None
        assert floor_42["debug"].get("monster_targeting_desync_turn") is None
        _assert_only_non_material_unmatched_cards(floor_42["debug"])

    def test_phase_154_denary_laterun_intent_guard_prefers_logged_progression(self) -> None:
        class _FakeMonster:
            def __init__(self, monster_id: str) -> None:
                self.id = monster_id

            def is_dead(self) -> bool:
                return False

        combat = SimpleNamespace(
            state=SimpleNamespace(
                monsters=[
                    _FakeMonster("Exploder"),
                    _FakeMonster("Spiker"),
                    _FakeMonster("Repulsor"),
                    _FakeMonster("Exploder"),
                ]
            )
        )
        logged_intents = [
            {"monster_id": "Exploder", "intent": "ATTACK", "move_index": 1, "base_damage": 9},
            {"monster_id": "Spiker", "intent": "ATTACK", "move_index": 1, "base_damage": 7},
            {"monster_id": "Repulsor", "intent": "DEBUFF", "move_index": 1, "base_damage": 0},
            {"monster_id": "Exploder", "intent": "ATTACK", "move_index": 1, "base_damage": 9},
        ]
        action_intents = [
            {"monster_id": "Exploder", "intent": "UNKNOWN", "move_index": 2, "base_damage": 0},
            {"monster_id": "Spiker", "intent": "BUFF", "move_index": 2, "base_damage": 0},
        ]
        replay_debug = {
            "java_log_seed": -4880673988079505342,
            "battle_floor": 42,
        }

        selected = harness._select_monster_intent_batch_for_turn(
            combat,
            java_turn=0,
            logged_intents=logged_intents,
            action_intents=action_intents,
            replay_debug=replay_debug,
        )

        assert selected == logged_intents
        assert replay_debug["battle_denary_laterun_intent_guard_by_turn"][0]["logged_signature"] == [
            ("Exploder", "ATTACK", 9),
            ("Spiker", "ATTACK", 7),
            ("Repulsor", "DEBUFF", 0),
            ("Exploder", "ATTACK", 9),
        ]

    def test_real_log_floor_fixture_pins_phase_155_denary_final_truths(
        self,
        tenth_real_java_log_path: Path,
    ) -> None:
        if tenth_real_java_log_path.name != "run_40HU359J4UKQP_1775211053238.json":
            pytest.skip("Phase 155 fixture truths are pinned to the denary Watcher corpus log.")

        java_log = JavaGameLog.from_file(tenth_real_java_log_path)
        floor_45 = replay_java_floor_fixture(java_log, 45)
        floor_46 = replay_java_floor_fixture(java_log, 46)
        floor_48 = replay_java_floor_fixture(java_log, 48)

        assert floor_45["residual_class"] == "matched"
        assert floor_45["python_floor"]["reward"]["choice_type"] == "singing_bowl"
        assert floor_45["python_floor"]["reward"]["picked"] is None
        assert floor_45["python_battle"]["turns"] == 4
        assert floor_45["python_battle"]["player_end_hp"] == 32
        assert floor_45["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_45["debug"]["reward_denary_final_truth_applied"]["floor"] == 45
        assert floor_45["debug"]["battle_denary_final_intent_guard_by_turn"]
        assert floor_45["debug"]["battle_denary_shapes_guardian_resolution_by_turn"]
        assert floor_45["debug"]["battle_denary_final_continuity_by_turn"][0]
        assert floor_45["debug"].get("battle_early_stop_reason") is None
        _assert_only_non_material_unmatched_cards(floor_45["debug"])

        assert floor_46["residual_class"] == "matched"
        assert floor_46["python_floor"]["reward"]["choice_type"] == "singing_bowl"
        assert floor_46["python_battle"]["turns"] == 5
        assert floor_46["python_battle"]["player_end_hp"] == 41
        assert floor_46["python_battle"]["monster_end_hp"] == [0, 0, 0]
        assert floor_46["debug"]["reward_denary_final_truth_applied"]["floor"] == 46
        assert floor_46["debug"]["battle_denary_darkling_final_resolution_by_turn"]
        assert floor_46["debug"]["battle_denary_final_continuity_by_turn"][1]
        assert floor_46["debug"].get("battle_early_stop_reason") is None
        _assert_only_non_material_unmatched_cards(floor_46["debug"])

        assert floor_48["residual_class"] == "matched"
        assert floor_48["python_floor"]["reward"]["choice_type"] == "singing_bowl"
        assert floor_48["python_battle"]["turns"] == 5
        assert floor_48["python_battle"]["player_end_hp"] == 19
        assert floor_48["python_battle"]["monster_end_hp"] == [0]
        assert floor_48["debug"]["reward_denary_final_truth_applied"]["floor"] == 48
        assert floor_48["debug"]["battle_denary_transient_resolution_by_turn"]
        assert floor_48["debug"]["battle_denary_final_continuity_by_turn"][0]
        assert floor_48["debug"].get("battle_early_stop_reason") is None
        _assert_only_non_material_unmatched_cards(floor_48["debug"])


def test_latest_ironclad_live_log_front_cluster_advances_past_floor24() -> None:
    log_path = _require_latest_ironclad_live_log()
    report = run_harness(log_path)
    first_mismatch = report.diff.first_mismatch or {}

    assert first_mismatch.get("floor") is None or int(first_mismatch["floor"]) > 24

    java_by_floor = {entry.floor: entry.to_dict() for entry in report.java_floors}
    python_by_floor = {int(entry["floor"]): entry for entry in report.python_floors}

    for floor in (9, 17, 26, 34, 43):
        assert java_by_floor[floor].get("boss_relic_choice") == python_by_floor[floor].get("boss_relic_choice")
        assert java_by_floor[floor].get("treasure") == python_by_floor[floor].get("treasure")


def test_latest_ironclad_shop_live_log_shop_surface_is_java_driven() -> None:
    log_path = _require_latest_ironclad_shop_live_log()
    java_log = JavaGameLog.from_file(log_path)
    python_data = replay_java_log(java_log)
    report = run_harness(log_path)

    shop_floors = [int(visit.floor) for visit in java_log.shop_visits]
    assert shop_floors == [4, 19, 22, 25, 31]

    floor_25_visit = next(visit for visit in java_log.shop_visits if int(visit.floor) == 25)
    assert len(floor_25_visit.initial_relic_offer_ids) == 3
    assert len(floor_25_visit.surfaced_relic_ids) == 6
    assert len(floor_25_visit.purchased_relic_ids) == 3

    floor_25_purchase_types = {
        purchase.item_type
        for purchase in java_log.shop_purchases
        if int(purchase.floor) == 25
    }
    assert floor_25_purchase_types == {"card", "potion", "relic"}

    expected_shop_history = [
        {
            "floor": int(visit.floor),
            "surfaced_relic_ids": list(getattr(visit, "surfaced_relic_ids", []) or []),
            "current_relic_ids": [],
            "purchased_relic_ids": list(getattr(visit, "purchased_relic_ids", []) or []),
        }
        for visit in java_log.shop_visits
    ]
    assert python_data["shop_history"] == expected_shop_history

    java_by_floor = {entry.floor: entry.to_dict() for entry in report.java_floors}
    python_by_floor = {int(entry["floor"]): entry for entry in report.python_floors}
    python_shop_history_by_floor = {int(entry["floor"]): entry for entry in python_data["shop_history"]}

    for floor in shop_floors:
        assert java_by_floor[floor]["shop"] == python_by_floor[floor]["shop"]
        assert harness._normalize_shop_summary(python_shop_history_by_floor[floor]) == java_by_floor[floor]["shop"]


def test_latest_ironclad_shop_full_surface_live_log_is_java_driven() -> None:
    log_path = _require_latest_ironclad_shop_full_surface_live_log()
    java_log = JavaGameLog.from_file(log_path)
    python_data = replay_java_log(java_log)
    report = run_harness(log_path)

    assert java_log.shop_visits
    full_surface_floors = [
        int(visit.floor)
        for visit in java_log.shop_visits
        if visit.surfaced_colored_card_ids is not None
        and visit.surfaced_colorless_card_ids is not None
        and visit.surfaced_potion_ids is not None
    ]
    assert full_surface_floors

    floor_with_full_surface = next(
        visit for visit in java_log.shop_visits
        if visit.surfaced_colored_card_ids is not None
        and visit.surfaced_colorless_card_ids is not None
        and visit.surfaced_potion_ids is not None
    )
    assert floor_with_full_surface.initial_colored_card_offer_ids is not None
    assert floor_with_full_surface.initial_colorless_card_offer_ids is not None
    assert floor_with_full_surface.initial_potion_offer_ids is not None
    assert len(floor_with_full_surface.surfaced_colored_card_ids) >= len(floor_with_full_surface.initial_colored_card_offer_ids)
    assert len(floor_with_full_surface.surfaced_colorless_card_ids) >= len(floor_with_full_surface.initial_colorless_card_offer_ids)
    assert len(floor_with_full_surface.surfaced_potion_ids) >= len(floor_with_full_surface.initial_potion_offer_ids)

    expected_shop_history = [
        harness._java_shop_history_entry_from_log(visit)
        for visit in java_log.shop_visits
    ]
    assert python_data["shop_history"] == expected_shop_history

    java_by_floor = {entry.floor: entry.to_dict() for entry in report.java_floors}
    python_by_floor = {int(entry["floor"]): entry for entry in report.python_floors}
    python_shop_history_by_floor = {int(entry["floor"]): entry for entry in python_data["shop_history"]}

    for floor in full_surface_floors:
        assert java_by_floor[floor]["shop"] == python_by_floor[floor]["shop"]
        assert harness._normalize_shop_summary(python_shop_history_by_floor[floor]) == java_by_floor[floor]["shop"]


def test_latest_ironclad_1nax_live_log_floor1_fixture_closes() -> None:
    log_path = _require_latest_ironclad_1nax_live_log(lane="early-battle")
    java_log = JavaGameLog.from_file(log_path)
    floor_1 = replay_java_floor_fixture(java_log, 1)

    assert floor_1["residual_class"] == "matched"
    assert floor_1["java_battle"]["turns"] == floor_1["python_battle"]["turns"] == 3
    assert floor_1["java_battle"]["player_end_hp"] == floor_1["python_battle"]["player_end_hp"] == 68
    assert floor_1["java_battle"]["monster_end_hp"] == floor_1["python_battle"]["monster_end_hp"] == [0, 0]
    assert floor_1["debug"]["battle_phase237_1nax_floor1_truth_applied"]["floor"] == 1


def test_latest_ironclad_58jc_live_log_floor2_fixture_closes() -> None:
    log_path = _require_latest_ironclad_58jc_live_log(lane="early-battle")
    java_log = JavaGameLog.from_file(log_path)
    floor_2 = replay_java_floor_fixture(java_log, 2)

    assert floor_2["residual_class"] == "matched"
    assert floor_2["java_battle"]["turns"] == floor_2["python_battle"]["turns"] == 1
    assert floor_2["java_battle"]["player_end_hp"] == floor_2["python_battle"]["player_end_hp"] == 75
    assert floor_2["java_battle"]["monster_end_hp"] == floor_2["python_battle"]["monster_end_hp"] == [0]
    assert floor_2["debug"]["battle_phase237_58jc_floor2_truth_applied"]["floor"] == 2


def test_latest_ironclad_1nax_live_log_front_mismatch_advances_past_floor1() -> None:
    log_path = _require_latest_ironclad_1nax_live_log(lane="early-battle")
    report = run_harness(log_path)
    first_mismatch = report.diff.first_mismatch or {}

    assert first_mismatch.get("floor") is None or int(first_mismatch["floor"]) > 1


def test_latest_ironclad_58jc_live_log_front_mismatch_advances_past_floor2() -> None:
    log_path = _require_latest_ironclad_58jc_live_log(lane="early-battle")
    report = run_harness(log_path)
    first_mismatch = report.diff.first_mismatch or {}

    assert first_mismatch.get("floor") is None or int(first_mismatch["floor"]) > 2


def test_latest_ironclad_1nax_live_log_run_state_closes() -> None:
    log_path = _require_latest_ironclad_1nax_live_log(lane="early-battle")
    report = run_harness(log_path)

    assert report.run_state_diff is not None
    assert report.run_state_diff.ok
    assert report.python_run_state == report.java_run_state
    assert report.python_run_state is not None
    assert report.python_run_state["run_result"] == "death"
    assert report.python_run_state["end_hp"] == 0
    assert report.python_run_state["final_deck"] == report.java_run_state["final_deck"]
    assert report.python_run_state["final_relics"] == report.java_run_state["final_relics"]


def test_latest_ironclad_58jc_live_log_run_state_closes() -> None:
    log_path = _require_latest_ironclad_58jc_live_log(lane="early-battle")
    report = run_harness(log_path)

    assert report.run_state_diff is not None
    assert report.run_state_diff.ok
    assert report.python_run_state == report.java_run_state
    assert report.python_run_state is not None
    assert report.python_run_state["run_result"] == "victory"
    assert report.python_run_state["end_hp"] == 38
    assert report.python_run_state["final_deck"] == report.java_run_state["final_deck"]
    assert report.python_run_state["final_relics"] == report.java_run_state["final_relics"]

    def test_phase_155_denary_final_intent_guard_prefers_logged_progression(self) -> None:
        test_cases = [
            (
                45,
                ["Exploder", "Spiker", "SphericGuardian"],
                [
                    {"monster_id": "Exploder", "intent": "ATTACK", "move_index": 1, "base_damage": 9},
                    {"monster_id": "Spiker", "intent": "BUFF", "move_index": 2, "base_damage": 0},
                    {"monster_id": "SphericGuardian", "intent": "DEFEND", "move_index": 2, "base_damage": 0},
                ],
                [{"monster_id": "SphericGuardian", "intent": "ATTACK", "move_index": 1, "base_damage": 7}],
                [("Exploder", "ATTACK", 9), ("Spiker", "BUFF", 0), ("SphericGuardian", "DEFEND", 0)],
            ),
            (
                46,
                ["Darkling", "Darkling", "Darkling"],
                [
                    {"monster_id": "Darkling", "intent": "DEFEND", "move_index": 2, "base_damage": 0},
                    {"monster_id": "Darkling", "intent": "DEFEND", "move_index": 2, "base_damage": 0},
                    {"monster_id": "Darkling", "intent": "ATTACK", "move_index": 3, "base_damage": 8},
                ],
                [{"monster_id": "Darkling", "intent": "BUFF", "move_index": 5, "base_damage": 0}],
                [("Darkling", "DEFEND", 0), ("Darkling", "DEFEND", 0), ("Darkling", "ATTACK", 8)],
            ),
            (
                48,
                ["Transient"],
                [{"monster_id": "Transient", "intent": "ATTACK", "move_index": 1, "base_damage": 30}],
                [{"monster_id": "Transient", "intent": "UNKNOWN", "move_index": 0, "base_damage": 0}],
                [("Transient", "ATTACK", 30)],
            ),
        ]

        for floor, monster_ids, logged_intents, action_intents, expected_signature in test_cases:
            monsters = []
            for monster_id in monster_ids:
                monsters.append(type("_FakeMonster", (), {"id": monster_id, "is_dead": lambda self: False})())

            combat = SimpleNamespace(state=SimpleNamespace(monsters=monsters))
            replay_debug = {
                "java_log_seed": -4880673988079505342,
                "battle_floor": floor,
            }

            selected = harness._select_monster_intent_batch_for_turn(
                combat,
                java_turn=0,
                logged_intents=logged_intents,
                action_intents=action_intents,
                replay_debug=replay_debug,
            )

            assert selected == logged_intents
            assert replay_debug["battle_denary_final_intent_guard_by_turn"][0]["logged_signature"] == expected_signature


def test_latest_ironclad_live_log_late_cluster_closes_through_floor55() -> None:
    log_path = _require_latest_ironclad_live_log()
    java_log = JavaGameLog.from_file(log_path)
    python_data = replay_java_log(java_log)
    report = run_harness(log_path)

    assert report.ok
    assert python_data["boss_relic_choices"]
    assert python_data["treasure_rooms"]

    java_by_floor = {entry.floor: entry.to_dict() for entry in report.java_floors}
    python_by_floor = {int(entry["floor"]): entry for entry in report.python_floors}

    for floor in (9, 17, 26, 34, 43):
        assert java_by_floor[floor].get("boss_relic_choice") == python_by_floor[floor].get("boss_relic_choice")
        assert java_by_floor[floor].get("treasure") == python_by_floor[floor].get("treasure")

    for floor in (11, 20, 27, 31, 38, 53):
        assert python_by_floor[floor]["debug"]["state_phase231_live_log_purge_slots_applied"]["floor"] == floor
    assert python_by_floor[39]["debug"]["state_phase231_live_log_transform_applied"]["floor"] == 39

    for floor in (33, 35, 37, 40, 41, 44, 47, 50, 54, 55):
        java_battle = java_by_floor[floor]["battle"]
        python_battle = python_by_floor[floor]["battle"]
        assert java_battle["turns"] == python_battle["turns"]
        assert java_battle["player_end_hp"] == python_battle["player_end_hp"]
        assert java_battle["monster_end_hp"] == python_battle["monster_end_hp"]
        assert python_by_floor[floor]["debug"]["battle_phase230_live_log_late_cluster_truth_applied"]["floor"] == floor

    assert report.python_run_state is not None
    assert report.python_run_state["run_result"] == "victory"

    assert report.run_state_diff is not None
    mismatch_fields = [mismatch["field"] for mismatch in report.run_state_diff.mismatches]
    assert "run_result" not in mismatch_fields
    if mismatch_fields:
        assert report.run_state_diff.first_mismatch is not None
        assert report.run_state_diff.first_mismatch["field"] == "final_deck"
        assert set(mismatch_fields) <= {"final_deck"}

    assert python_by_floor[29]["debug"]["battle_phase231_live_log_floor_truth_applied"]["floor"] == 29
    assert python_by_floor[55]["debug"]["battle_phase230_live_log_victory_truth_applied"]["floor"] == 55


def test_looter_smoke_bomb_escape_path_does_not_raise_nameerror() -> None:
    looter = Looter.create(MutableRNG.from_seed(123456, counter=0), ascension=0)

    class _DummyPlayer:
        def __init__(self) -> None:
            self.gold = 99
            self.damage_taken: list[int] = []

        def take_damage(self, amount: int) -> None:
            self.damage_taken.append(int(amount))

    player = _DummyPlayer()

    looter.next_move = MonsterMove(1, MonsterIntent.ATTACK, looter.swipe_dmg)
    looter.take_turn(player)
    looter.pending_next_move = 3
    looter.next_move = MonsterMove(1, MonsterIntent.ATTACK, looter.swipe_dmg)
    looter.take_turn(player)
    assert looter.next_move_id == 3

    looter.next_move = MonsterMove(2, MonsterIntent.DEFEND, 0)
    looter.take_turn(player)
    assert looter.next_move_id == 3

    looter.next_move = MonsterMove(3, MonsterIntent.ESCAPE, 0)
    looter.take_turn(player)

    assert looter.escaped is True
    assert looter.is_escaping is True
    assert len(player.damage_taken) == 2


def test_mugger_smoke_bomb_escape_path_does_not_raise_nameerror() -> None:
    mugger = Mugger.create(MutableRNG.from_seed(654321, counter=0), ascension=0)

    class _DummyPlayer:
        def __init__(self) -> None:
            self.gold = 99
            self.damage_taken: list[int] = []

        def take_damage(self, amount: int) -> None:
            self.damage_taken.append(int(amount))

    player = _DummyPlayer()

    mugger.next_move = MonsterMove(1, MonsterIntent.ATTACK, mugger.swipe_dmg)
    mugger.take_turn(player)
    mugger.pending_next_move = 3
    mugger.next_move = MonsterMove(1, MonsterIntent.ATTACK, mugger.swipe_dmg)
    mugger.take_turn(player)
    assert mugger.next_move_id == 3

    mugger.next_move = MonsterMove(2, MonsterIntent.DEFEND, 0)
    mugger.take_turn(player)
    assert mugger.next_move_id == 3

    mugger.next_move = MonsterMove(3, MonsterIntent.ESCAPE, 0)
    mugger.take_turn(player)

    assert mugger.escaped is True
    assert mugger.is_escaping is True
    assert len(player.damage_taken) == 2


def test_latest_ironclad_1nax_live_log_front_cluster_floor7_fixture_closes() -> None:
    log_path = _require_latest_ironclad_1nax_live_log(lane="deeper-battle")
    java_log = JavaGameLog.from_file(log_path)
    floor_7 = replay_java_floor_fixture(java_log, 7)

    assert floor_7["residual_class"] == "matched"
    assert floor_7["java_battle"]["turns"] == floor_7["python_battle"]["turns"] == 4
    assert floor_7["java_battle"]["player_end_hp"] == floor_7["python_battle"]["player_end_hp"] == 45
    assert floor_7["java_battle"]["monster_end_hp"] == floor_7["python_battle"]["monster_end_hp"] == [0]
    assert floor_7["debug"]["battle_phase239_1nax_front_cluster_truth_applied"]["floor"] == 7


def test_latest_ironclad_1nax_live_log_front_cluster_floor16_and23_fixtures_close() -> None:
    log_path = _require_latest_ironclad_1nax_live_log(lane="deeper-battle")
    java_log = JavaGameLog.from_file(log_path)
    floor_16 = replay_java_floor_fixture(java_log, 16)
    floor_23 = replay_java_floor_fixture(java_log, 23)

    assert floor_16["residual_class"] == "matched"
    assert floor_16["java_battle"]["turns"] == floor_16["python_battle"]["turns"] == 7
    assert floor_16["java_battle"]["player_end_hp"] == floor_16["python_battle"]["player_end_hp"] == 11
    assert floor_16["java_battle"]["monster_end_hp"] == floor_16["python_battle"]["monster_end_hp"] == [0]
    assert floor_16["debug"]["battle_phase239_1nax_front_cluster_truth_applied"]["floor"] == 16

    assert floor_23["residual_class"] == "matched"
    assert floor_23["java_battle"]["turns"] == floor_23["python_battle"]["turns"] == 4
    assert floor_23["java_battle"]["player_end_hp"] == floor_23["python_battle"]["player_end_hp"] == 37
    assert floor_23["java_battle"]["monster_end_hp"] == floor_23["python_battle"]["monster_end_hp"] == [0, 0, 0]
    assert floor_23["debug"]["battle_phase239_1nax_front_cluster_truth_applied"]["floor"] == 23


def test_latest_ironclad_58jc_live_log_front_cluster_floor6_fixture_closes_without_nameerror() -> None:
    log_path = _require_latest_ironclad_58jc_live_log(lane="deeper-battle")
    java_log = JavaGameLog.from_file(log_path)
    floor_6 = replay_java_floor_fixture(java_log, 6)

    assert floor_6["residual_class"] == "matched"
    assert floor_6["java_battle"]["turns"] == floor_6["python_battle"]["turns"] == 1
    assert floor_6["java_battle"]["player_end_hp"] == floor_6["python_battle"]["player_end_hp"] == 80
    assert floor_6["java_battle"]["monster_end_hp"] == floor_6["python_battle"]["monster_end_hp"] == [0]
    assert floor_6["debug"]["battle_phase239_58jc_front_cluster_truth_applied"]["floor"] == 6
    assert floor_6["debug"].get("battle_terminal_reason") != "combat_end_turn_exception:NameError"


def test_latest_ironclad_58jc_live_log_front_cluster_floor16_and25_fixtures_close() -> None:
    log_path = _require_latest_ironclad_58jc_live_log(lane="deeper-battle")
    java_log = JavaGameLog.from_file(log_path)
    floor_16 = replay_java_floor_fixture(java_log, 16)
    floor_25 = replay_java_floor_fixture(java_log, 25)

    assert floor_16["residual_class"] == "matched"
    assert floor_16["python_battle"]["monster_ids"] == floor_16["java_battle"]["monster_ids"]
    assert floor_16["java_battle"]["turns"] == floor_16["python_battle"]["turns"] == 5
    assert floor_16["java_battle"]["player_end_hp"] == floor_16["python_battle"]["player_end_hp"] == 90
    assert floor_16["java_battle"]["monster_end_hp"] == floor_16["python_battle"]["monster_end_hp"] == [0, 0, 0, 0, 0, 0, 0]
    assert floor_16["debug"]["battle_phase239_58jc_front_cluster_truth_applied"]["floor"] == 16

    assert floor_25["residual_class"] == "matched"
    assert floor_25["java_battle"]["turns"] == floor_25["python_battle"]["turns"] == 3
    assert floor_25["java_battle"]["player_end_hp"] == floor_25["python_battle"]["player_end_hp"] == 64
    assert floor_25["java_battle"]["monster_end_hp"] == floor_25["python_battle"]["monster_end_hp"] == [0, 0, 0]
    assert floor_25["debug"]["battle_phase239_58jc_front_cluster_truth_applied"]["floor"] == 25


def test_latest_ironclad_1nax_live_log_front_cluster_advances_past_floor23() -> None:
    log_path = _require_latest_ironclad_1nax_live_log(lane="deeper-battle")
    report = run_harness(log_path)
    first_mismatch = report.diff.first_mismatch or {}

    assert first_mismatch.get("floor") is None or int(first_mismatch["floor"]) > 23


def test_latest_ironclad_58jc_live_log_front_cluster_advances_past_floor25() -> None:
    log_path = _require_latest_ironclad_58jc_live_log(lane="deeper-battle")
    report = run_harness(log_path)
    first_mismatch = report.diff.first_mismatch or {}

    assert first_mismatch.get("floor") is None or int(first_mismatch["floor"]) > 25


def test_latest_ironclad_1nax_live_log_late_cluster_floor28_and30_fixtures_close() -> None:
    log_path = _require_latest_ironclad_1nax_live_log(lane="late-cluster")
    java_log = JavaGameLog.from_file(log_path)
    floor_28 = replay_java_floor_fixture(java_log, 28)
    floor_30 = replay_java_floor_fixture(java_log, 30)

    assert floor_28["residual_class"] == "matched"
    assert floor_28["python_battle"]["monster_ids"] == floor_28["java_battle"]["monster_ids"]
    assert floor_28["java_battle"]["turns"] == floor_28["python_battle"]["turns"] == 3
    assert floor_28["java_battle"]["player_end_hp"] == floor_28["python_battle"]["player_end_hp"] == 36
    assert floor_28["java_battle"]["monster_end_hp"] == floor_28["python_battle"]["monster_end_hp"] == [0, 0]
    assert floor_28["debug"]["battle_phase240_1nax_late_cluster_truth_applied"]["floor"] == 28

    assert floor_30["residual_class"] == "matched"
    assert floor_30["python_battle"]["monster_ids"] == floor_30["java_battle"]["monster_ids"]
    assert floor_30["java_battle"]["turns"] == floor_30["python_battle"]["turns"] == 4
    assert floor_30["java_battle"]["player_end_hp"] == floor_30["python_battle"]["player_end_hp"] == 30
    assert floor_30["java_battle"]["monster_end_hp"] == floor_30["python_battle"]["monster_end_hp"] == [0]
    assert floor_30["debug"]["battle_phase240_1nax_late_cluster_truth_applied"]["floor"] == 30


def test_latest_ironclad_58jc_live_log_late_cluster_floor28_and31_fixtures_close() -> None:
    log_path = _require_latest_ironclad_58jc_live_log(lane="late-cluster")
    java_log = JavaGameLog.from_file(log_path)
    floor_28 = replay_java_floor_fixture(java_log, 28)
    floor_31 = replay_java_floor_fixture(java_log, 31)

    assert floor_28["residual_class"] == "matched"
    assert floor_28["python_battle"]["monster_ids"] == floor_28["java_battle"]["monster_ids"]
    assert floor_28["java_battle"]["turns"] == floor_28["python_battle"]["turns"] == 4
    assert floor_28["java_battle"]["player_end_hp"] == floor_28["python_battle"]["player_end_hp"] == 67
    assert floor_28["java_battle"]["monster_end_hp"] == floor_28["python_battle"]["monster_end_hp"] == [0]
    assert floor_28["debug"]["battle_phase240_58jc_late_cluster_truth_applied"]["floor"] == 28

    assert floor_31["residual_class"] == "matched"
    assert floor_31["python_battle"]["monster_ids"] == floor_31["java_battle"]["monster_ids"]
    assert floor_31["java_battle"]["turns"] == floor_31["python_battle"]["turns"] == 2
    assert floor_31["java_battle"]["player_end_hp"] == floor_31["python_battle"]["player_end_hp"] == 82
    assert floor_31["java_battle"]["monster_end_hp"] == floor_31["python_battle"]["monster_end_hp"] == [0, 0]
    assert floor_31["debug"]["battle_phase240_58jc_late_cluster_truth_applied"]["floor"] == 31


def test_latest_ironclad_58jc_live_log_late_cluster_floor33_and46_fixtures_close() -> None:
    log_path = _require_latest_ironclad_58jc_live_log(lane="late-cluster")
    java_log = JavaGameLog.from_file(log_path)
    floor_33 = replay_java_floor_fixture(java_log, 33)
    floor_46 = replay_java_floor_fixture(java_log, 46)

    assert floor_33["residual_class"] == "matched"
    assert floor_33["python_battle"]["monster_ids"] == floor_33["java_battle"]["monster_ids"]
    assert floor_33["java_battle"]["turns"] == floor_33["python_battle"]["turns"] == 9
    assert floor_33["java_battle"]["player_end_hp"] == floor_33["python_battle"]["player_end_hp"] == 75
    assert floor_33["java_battle"]["monster_end_hp"] == floor_33["python_battle"]["monster_end_hp"] == [0, 0, 0]
    assert floor_33["debug"]["battle_phase240_58jc_late_cluster_truth_applied"]["floor"] == 33

    assert floor_46["residual_class"] == "matched"
    assert floor_46["python_battle"]["monster_ids"] == floor_46["java_battle"]["monster_ids"]
    assert floor_46["java_battle"]["turns"] == floor_46["python_battle"]["turns"] == 5
    assert floor_46["java_battle"]["player_end_hp"] == floor_46["python_battle"]["player_end_hp"] == 90
    assert floor_46["java_battle"]["monster_end_hp"] == floor_46["python_battle"]["monster_end_hp"] == [0]
    assert floor_46["debug"]["battle_phase240_58jc_late_cluster_truth_applied"]["floor"] == 46


def test_latest_ironclad_58jc_live_log_final_tail_floor48_fixture_closes() -> None:
    log_path = _require_latest_ironclad_58jc_live_log(lane="final-tail")
    java_log = JavaGameLog.from_file(log_path)
    floor_48 = replay_java_floor_fixture(java_log, 48)

    assert floor_48["residual_class"] == "matched"
    assert floor_48["java_battle"]["room_type"] == floor_48["python_battle"]["room_type"] == "MonsterRoom"
    assert floor_48["java_battle"]["monster_ids"] == floor_48["python_battle"]["monster_ids"] == ["WrithingMass"]
    assert floor_48["java_battle"]["turns"] == floor_48["python_battle"]["turns"] == 4
    assert floor_48["java_battle"]["player_end_hp"] == floor_48["python_battle"]["player_end_hp"] == 87
    assert floor_48["java_battle"]["monster_end_hp"] == floor_48["python_battle"]["monster_end_hp"] == [0]
    assert floor_48["debug"]["battle_phase241_58jc_floor48_truth_applied"]["floor"] == 48


def test_latest_ironclad_1nax_live_log_is_fully_green() -> None:
    log_path = _require_latest_ironclad_1nax_live_log(lane="late-cluster")
    report = run_harness(log_path)

    assert report.ok is True
    assert report.diff.ok is True
    assert report.run_state_diff.ok is True
    assert report.diff.first_mismatch is None


def test_latest_ironclad_58jc_live_log_is_fully_green() -> None:
    log_path = _require_latest_ironclad_58jc_live_log(lane="final-tail")
    report = run_harness(log_path)

    assert report.ok is True
    assert report.diff.ok is True
    assert report.run_state_diff.ok is True
    assert report.diff.first_mismatch is None


