"""Performance benchmarks for the STS engine"""
from __future__ import annotations

import time
import pytest
from sts_py.engine.run.run_engine import RunEngine, RoomType, RunPhase


class TestPerformance:
    def test_map_generation_speed(self):
        """Benchmark map generation time"""
        iterations = 100
        start = time.perf_counter()

        for _ in range(iterations):
            RunEngine.create("PERFTEST", ascension=0)

        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / iterations) * 1000

        print(f"\nMap Generation: {avg_ms:.2f}ms avg ({iterations} iterations)")
        assert avg_ms < 100, f"Map generation too slow: {avg_ms:.2f}ms"

    def test_combat_speed(self):
        """Benchmark single combat time"""
        engine = RunEngine.create("PERFTEST", ascension=0)

        monster_room = next(
            n for n in engine.state.map_nodes
            if n.room_type == RoomType.MONSTER
        )
        engine.choose_path(monster_room.node_id)

        iterations = 50
        start = time.perf_counter()

        for _ in range(iterations):
            engine._start_combat("Slime Boss")
            engine.state.combat.state.turn = 3
            for monster in engine.state.combat.state.monsters:
                monster.hp = 0
                monster.current_hp = 0
            engine.end_combat()
            engine.state.phase = RunPhase.MAP

        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / iterations) * 1000

        print(f"\nCombat: {avg_ms:.2f}ms avg ({iterations} iterations)")
        assert avg_ms < 50, f"Combat too slow: {avg_ms:.2f}ms"

    def test_full_run_simulation_speed(self):
        """Benchmark simulating a partial run through the map"""
        iterations = 10
        start = time.perf_counter()

        for _ in range(iterations):
            engine = RunEngine.create("PERFTEST", ascension=0)

            for _ in range(5):
                current = engine.get_current_room()
                if current is None:
                    break

                if current.room_type in (RoomType.MONSTER, RoomType.ELITE, RoomType.BOSS):
                    engine._start_combat("Slime Boss")
                    engine.state.combat.state.turn = 3
                    for monster in engine.state.combat.state.monsters:
                        monster.hp = 0
                        monster.current_hp = 0
                    engine.end_combat()

                    if engine.state.phase == RunPhase.VICTORY:
                        break

                elif current.room_type == RoomType.REST:
                    engine._rest()

                next_node_id = engine.get_next_available_node()
                if next_node_id is None:
                    break
                engine.choose_path(next_node_id)

        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / iterations) * 1000

        print(f"\nPartial Run (5 steps): {avg_ms:.2f}ms avg ({iterations} iterations)")
        assert avg_ms < 500, f"Run simulation too slow: {avg_ms:.2f}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
