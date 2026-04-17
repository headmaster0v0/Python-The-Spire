from __future__ import annotations

import copy
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from sts_py.engine.combat.powers import create_power
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.bosses import SlimeBoss
from sts_py.engine.monsters.city_beyond import Darkling, GremlinLeader, Nemesis
from sts_py.engine.monsters.exordium import Looter, Mugger, Sentry
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.run.events import (
    ACT1_EVENTS,
    ACT2_EVENTS,
    Event,
    EventChoice,
    EventEffect,
    EventEffectType,
)
from sts_py.engine.run.run_engine import RunEngine, RunPhase
from sts_py.tools.wiki_audit import build_event_source_facts


SEED_LONG = 4452322743548530140


@dataclass
class _MonsterHarnessState:
    rng: MutableRNG
    monsters: list[MonsterBase] = field(default_factory=list)
    _replay_gremlinleader_pending_spawn_ids: list[str] = field(default_factory=list)
    _replay_gremlinleader_spawn_events_by_turn: dict[int, list[dict[str, object]]] = field(default_factory=dict)
    _replay_java_turn: int = 1

    def add_monster(self, monster: MonsterBase) -> None:
        monster.state = self
        self.monsters.append(monster)


@dataclass
class _DummyPlayer:
    gold: int = 60
    damage_taken: list[int] = field(default_factory=list)

    def take_damage(self, amount: int) -> None:
        self.damage_taken.append(amount)


def test_phase269_monster_state_family_truth() -> None:
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)

    sentry = Sentry.create(hp_rng, ascension=0)
    assert sentry.get_power_amount("Artifact") == 1

    slime_boss = SlimeBoss.create(hp_rng, ascension=0)
    slime_state = _MonsterHarnessState(rng=MutableRNG.from_seed(SEED_LONG, counter=200))
    slime_state.monsters = [slime_boss]
    slime_boss.state = slime_state
    slime_boss.get_move(0)
    slime_boss.take_damage(slime_boss.max_hp // 2 + 1)
    assert slime_boss.next_move is not None
    assert slime_boss.next_move.move_id == 3
    slime_boss.take_turn(_DummyPlayer())
    spawned_ids = [monster.id for monster in slime_state.monsters if monster is not slime_boss]
    assert any("AcidSlime" in monster_id for monster_id in spawned_ids)
    assert any("SpikeSlime" in monster_id for monster_id in spawned_ids)

    looter = Looter.create(hp_rng, ascension=0)
    looter.state = _MonsterHarnessState(rng=MutableRNG.from_seed(SEED_LONG, counter=300), monsters=[looter])
    player = _DummyPlayer(gold=40)
    looter.set_move(MonsterMove(2, MonsterIntent.DEFEND, 0))
    looter.take_turn(player)
    assert looter.block == looter.escape_def
    looter.set_move(MonsterMove(3, MonsterIntent.ESCAPE, 0))
    looter.take_turn(player)
    assert looter.escaped is True

    leader = GremlinLeader.create(hp_rng, ascension=0)
    leader_state = _MonsterHarnessState(
        rng=MutableRNG.from_seed(SEED_LONG, counter=400),
        monsters=[leader],
        _replay_gremlinleader_pending_spawn_ids=["GremlinWarrior", "GremlinTsundere"],
    )
    leader.state = leader_state
    leader.set_move(MonsterMove(2, MonsterIntent.UNKNOWN, name="Rally"))
    leader.take_turn(_DummyPlayer())
    assert [monster.id for monster in leader_state.monsters] == ["GremlinWarrior", "GremlinTsundere", "GremlinLeader"]


def test_phase269_monster_dedicated_bespoke_truth() -> None:
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=500)
    darklings = [Darkling.create(hp_rng, ascension=0) for _ in range(3)]
    darkling_state = _MonsterHarnessState(rng=MutableRNG.from_seed(SEED_LONG, counter=600), monsters=darklings)
    for darkling in darklings:
        darkling.state = darkling_state
    darklings[0].take_damage(darklings[0].max_hp + 5)
    assert darklings[0].half_dead is True
    assert darklings[0].is_dying is False
    assert darklings[0].hp == 1

    nemesis = Nemesis.create(hp_rng, ascension=0)
    nemesis.add_power(create_power("Intangible", 1, nemesis.id))
    hp_before = nemesis.hp
    dealt = nemesis.take_damage(20)
    assert dealt == 1
    assert hp_before - nemesis.hp == 1

    mugger = Mugger.create(hp_rng, ascension=0)
    mugger.state = _MonsterHarnessState(rng=MutableRNG.from_seed(SEED_LONG, counter=700), monsters=[mugger])
    player = _DummyPlayer(gold=40)
    mugger.set_move(MonsterMove(1, MonsterIntent.ATTACK, mugger.swipe_dmg))
    mugger.take_turn(player)
    assert player.gold == 25
    assert mugger.stolen_gold == 15
    mugger.set_move(MonsterMove(3, MonsterIntent.ESCAPE, 0))
    mugger.take_turn(player)
    assert mugger.escaped is True


def test_phase269_event_choice_family_card_and_resource_truth() -> None:
    engine = RunEngine.create("PHASE269EVENTRESOURCE", ascension=0)
    engine.state.player_hp = 70
    engine.state.player_gold = 100
    choice = EventChoice(
        description="resource bundle",
        effects=[
            EventEffect(EventEffectType.GAIN_GOLD, amount=50),
            EventEffect(EventEffectType.LOSE_HP, amount=7),
            EventEffect(EventEffectType.GAIN_CARD, card_id="Doubt"),
            EventEffect(EventEffectType.GAIN_RANDOM_RELIC),
        ],
        cost=25,
    )

    result = choice.apply(engine)

    assert result["cost_paid"] == 25
    assert engine.state.player_gold == 125
    assert engine.state.player_hp == 63
    assert "Doubt" in engine.state.deck
    assert engine.get_pending_reward_state()["relic"] is not None

    living_wall = copy.deepcopy(ACT1_EVENTS["Living Wall"])

    remove_engine = RunEngine.create("PHASE269LIVINGWALLREMOVE", ascension=0)
    remove_engine.state.phase = RunPhase.EVENT
    remove_engine.state.deck = ["Strike", "Defend", "Bash"]
    remove_engine._current_event = living_wall
    remove_result = remove_engine.choose_event_option(0)
    assert remove_result["success"] is True
    assert remove_result["action"] == "select_card"
    assert remove_engine.choose_event_option(1)["success"] is True
    assert remove_engine.state.deck == ["Strike", "Bash"]

    transform_engine = RunEngine.create("PHASE269LIVINGWALLTRANSFORM", ascension=0)
    transform_engine.state.phase = RunPhase.EVENT
    transform_engine.state.deck = ["Strike"]
    transform_engine._current_event = copy.deepcopy(ACT1_EVENTS["Living Wall"])
    assert transform_engine.choose_event_option(1)["action"] == "select_card"
    transform_result = transform_engine.choose_event_option(0)
    assert transform_result["success"] is True
    assert transform_result["action"] == "card_transform"
    assert transform_result["card_id"] == "Strike"

    upgrade_engine = RunEngine.create("PHASE269LIVINGWALLUPGRADE", ascension=0)
    upgrade_engine.state.phase = RunPhase.EVENT
    upgrade_engine.state.deck = ["Bash"]
    upgrade_engine._current_event = copy.deepcopy(ACT1_EVENTS["Living Wall"])
    assert upgrade_engine.choose_event_option(2)["action"] == "select_card"
    assert upgrade_engine.choose_event_option(0)["success"] is True
    assert upgrade_engine.state.deck == ["Bash+"]


def test_phase269_event_choice_family_branching_truth() -> None:
    wing_statuette_signatures = build_event_source_facts(ACT1_EVENTS["Wing Statuette"])["choice_effect_signatures"]
    assert "event_gating:requires_attack_card" in wing_statuette_signatures

    dead_adventurer_signatures = build_event_source_facts(ACT1_EVENTS["Dead Adventurer"])["choice_effect_signatures"]
    assert "event:search" in dead_adventurer_signatures

    custom_trigger = Event(
        id="Phase269 Trigger",
        name="Phase269 Trigger",
        choices=[EventChoice(description="fight", trigger_combat=True, combat_enemies=["Cultist"])],
    )
    trigger_engine = RunEngine.create("PHASE269EVENTTRIGGER", ascension=0)
    trigger_engine.state.phase = RunPhase.EVENT
    trigger_engine._current_event = custom_trigger
    result = trigger_engine.choose_event_option(0)
    assert result["effects_applied"][0]["type"] == "trigger_combat"
    assert trigger_engine.state.pending_combat["enemies"] == ["Cultist"]

    no_effect_signatures = build_event_source_facts(ACT1_EVENTS["Golden Shrine"])["choice_effect_signatures"]
    assert "event:no_effect_choices" in no_effect_signatures


def test_phase269_event_dedicated_bespoke_truth(monkeypatch: pytest.MonkeyPatch) -> None:
    dead_engine = RunEngine.create("PHASE269DEADADVENTURER", ascension=0)
    event = copy.deepcopy(ACT1_EVENTS["Dead Adventurer"])
    da_state = {
        "searches_done": 0,
        "rewards_given": {"gold": True, "nothing": True, "relic": False},
        "encounter_triggered": False,
        "monster_type": None,
        "continuation_mode": False,
    }
    monkeypatch.setattr(dead_engine.state.rng.event_rng, "random_int", lambda upper: upper)
    result = dead_engine._do_dead_adventurer_search(event, da_state)
    assert result["reward"]["type"] == "relic"
    assert result["reward"]["id"] in dead_engine.state.relics

    living_wall_engine = RunEngine.create("PHASE269LIVINGWALLDEDICATED", ascension=0)
    living_wall_engine.state.phase = RunPhase.EVENT
    living_wall_engine.state.deck = ["Strike", "Defend"]
    living_wall_engine._current_event = copy.deepcopy(ACT1_EVENTS["Living Wall"])
    assert living_wall_engine.choose_event_option(0)["action"] == "select_card"
    assert living_wall_engine.choose_event_option(1)["success"] is True
    assert living_wall_engine.state.deck == ["Strike"]

    face_trader_engine = RunEngine.create("PHASE269FACETRADER", ascension=0)
    face_choice = ACT2_EVENTS["Face Trader"].choices[1]
    monkeypatch.setattr(face_trader_engine.state.rng.event_rng, "random_int", lambda upper: 0)
    result = face_choice.apply(face_trader_engine)
    trade_face_result = next(effect for effect in result["effects_applied"] if effect.get("type") == "trade_faces")
    assert trade_face_result["relic_obtained"] in {"CultistMask", "FaceOfCleric", "GremlinMask", "NlothsMask", "SsserpentHead", "Circlet"}
