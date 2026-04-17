from __future__ import annotations

from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.run.run_engine import RunEngine, RoomType, RunPhase


SEED_STRING = "1B40C4J3IIYDA"
SEED_LONG = 4452322743548530140


class TestEliteAndBossCombatEngine:
    def test_create_gremlin_nob_encounter(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Gremlin Nob",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        assert len(combat.state.monsters) == 1
        assert combat.state.monsters[0].id == "GremlinNob"

    def test_create_lagavulin_encounter(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Lagavulin",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        assert len(combat.state.monsters) == 1
        assert combat.state.monsters[0].id == "Lagavulin"

    def test_create_three_sentries_encounter(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="3 Sentries",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        assert len(combat.state.monsters) == 3
        assert all(monster.id == "Sentry" for monster in combat.state.monsters)

    def test_create_hexaghost_encounter(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Hexaghost",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        assert len(combat.state.monsters) == 1
        assert combat.state.monsters[0].id == "Hexaghost"

    def test_create_slime_boss_encounter(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Slime Boss",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        assert len(combat.state.monsters) == 1
        assert combat.state.monsters[0].id == "SlimeBoss"

    def test_create_guardian_encounter(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="The Guardian",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        assert len(combat.state.monsters) == 1
        assert combat.state.monsters[0].id == "TheGuardian"


class TestEliteAndBossRunEngine:
    def test_elite_encounter_selection_returns_real_elite(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        encounter = engine._get_elite_encounter()
        assert encounter in {"Gremlin Nob", "Lagavulin", "3 Sentries"}

    def test_boss_encounter_selection_returns_real_boss(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        encounter = engine._get_boss_encounter()
        assert encounter in {"Hexaghost", "Slime Boss", "The Guardian"}

    def test_enter_elite_room_starts_elite_combat(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        elite_node = next(node for node in engine.state.map_nodes if node.room_type == RoomType.ELITE)
        engine._enter_room(elite_node)
        assert engine.state.phase == RunPhase.COMBAT
        assert engine.state.combat is not None
        assert engine.state.combat.state.monsters[0].id in {"GremlinNob", "Lagavulin", "Sentry"}

    def test_enter_boss_room_starts_boss_combat(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        boss_node = next(node for node in engine.state.map_nodes if node.room_type == RoomType.BOSS)
        engine._enter_room(boss_node)
        assert engine.state.phase == RunPhase.COMBAT
        assert engine.state.combat is not None
        assert engine.state.combat.state.monsters[0].id in {"Hexaghost", "SlimeBoss", "TheGuardian"}
