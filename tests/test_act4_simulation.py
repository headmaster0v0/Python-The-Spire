from __future__ import annotations

from play_cli import _is_final_victory as cli_is_final_victory
from sts_py.engine.run.run_engine import MapNode, RoomType, RunEngine, RunPhase
from sts_py.engine.simulation import ImprovedAI, _is_final_victory as simulation_is_final_victory


def test_simulation_final_victory_helper_distinguishes_act3_and_act4() -> None:
    engine = RunEngine.create("TESTSIMVICTORY", ascension=0)

    engine.state.act = 3
    engine.state.phase = RunPhase.VICTORY
    engine.state.ruby_key_obtained = False
    engine.state.emerald_key_obtained = False
    engine.state.sapphire_key_obtained = False
    assert simulation_is_final_victory(engine) is True
    assert cli_is_final_victory(engine) is True

    engine.state.ruby_key_obtained = True
    engine.state.emerald_key_obtained = True
    engine.state.sapphire_key_obtained = True
    assert simulation_is_final_victory(engine) is False
    assert cli_is_final_victory(engine) is False

    engine.state.act = 4
    assert simulation_is_final_victory(engine) is True
    assert cli_is_final_victory(engine) is True


def test_simulation_ai_recalls_for_ruby_key_when_healthy() -> None:
    engine = RunEngine.create("TESTSIMRECALL", ascension=0)
    engine.state.phase = RunPhase.REST
    ai = ImprovedAI(engine)

    assert ai.execute_rest() is True
    assert engine.state.ruby_key_obtained is True
    assert engine.state.phase == RunPhase.MAP


def test_simulation_ai_takes_sapphire_key_before_relic() -> None:
    engine = RunEngine.create("TESTSIMTREASURE", ascension=0)
    engine._enter_treasure()
    relic = engine.state.pending_treasure_relic
    ai = ImprovedAI(engine)

    assert ai.execute_treasure() is True
    assert engine.state.sapphire_key_obtained is True
    assert relic not in engine.state.relics
    assert engine.state.phase == RunPhase.MAP


def test_simulation_ai_collects_remaining_chest_relics_after_sapphire_key() -> None:
    engine = RunEngine.create("TESTSIMTREASUREEXTRA", ascension=0)
    engine.state.phase = RunPhase.TREASURE
    engine.state.pending_chest_relic_choices = ["Anchor", "Strawberry"]
    engine.state.pending_treasure_relic = "Strawberry"
    ai = ImprovedAI(engine)

    assert ai.execute_treasure() is True
    assert engine.state.sapphire_key_obtained is True
    assert "Strawberry" not in engine.state.relics
    assert "Anchor" in engine.state.relics
    assert engine.state.phase == RunPhase.MAP


def test_simulation_ai_chooses_first_pending_boss_relic() -> None:
    engine = RunEngine.create("TESTSIMBOSSRELIC", ascension=0)
    engine.state.phase = RunPhase.VICTORY
    engine.state.pending_boss_relic_choices = ["TinyHouse", "CallingBell", "PandoraBox"]
    ai = ImprovedAI(engine)

    assert ai.choose_boss_relic() is True
    assert "TinyHouse" in engine.state.relics
    assert engine.state.pending_boss_relic_choices == []


def test_simulation_ai_prefers_burning_elite_when_emerald_key_missing(monkeypatch) -> None:
    engine = RunEngine.create("TESTSIMBURNING", ascension=0)
    ai = ImprovedAI(engine)
    monster = MapNode(floor=8, room_type=RoomType.MONSTER, node_id=1)
    burning_elite = MapNode(floor=8, room_type=RoomType.ELITE, node_id=2, burning_elite=True)

    monkeypatch.setattr(engine, "get_available_paths", lambda: [monster, burning_elite])
    chosen: dict[str, int] = {}

    def _choose(node_id: int) -> bool:
        chosen["node_id"] = node_id
        return True

    monkeypatch.setattr(engine, "choose_path", _choose)

    assert ai.choose_path() is True
    assert chosen["node_id"] == burning_elite.node_id


def test_simulation_execute_shop_uses_current_shop_engine_interface() -> None:
    engine = RunEngine.create("TESTSIMSHOP", ascension=0)
    engine._enter_shop()
    ai = ImprovedAI(engine)

    assert ai.execute_shop() is True
    assert engine.state.phase == RunPhase.MAP
