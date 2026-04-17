from __future__ import annotations

from sts_py.engine.run.events import EVENTS_BY_KEY, build_event
from sts_py.engine.run.run_engine import RunEngine, RunPhase
from sts_py.tools.wiki_audit import build_event_source_facts


def test_phase271_golden_idol_runtime_uses_canonical_event_id_and_trap_flow() -> None:
    engine = RunEngine.create("PHASE271GOLDENIDOL", ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine._set_current_event(build_event("Golden Idol"))

    result = engine.choose_event_option(0)

    assert result["action"] == "trap_triggered"
    assert engine.get_current_event() is not None
    assert engine.get_current_event().event_id == "Golden Shrine Trap"
    assert "GoldenIdol" in engine.state.relics


def test_phase271_force_enter_node_accepts_canonical_event_id() -> None:
    engine = RunEngine.create("PHASE271FORCEEVENT", ascension=0)

    engine.force_enter_node(14, 0, 0, "EventRoom", event_id="GoopPuddle")

    event = engine.get_current_event()
    assert event is not None
    assert event.event_key == "World of Goop"
    assert event.event_id == "GoopPuddle"


def test_phase271_event_source_facts_expose_key_id_bucket_and_gating() -> None:
    facts = build_event_source_facts(EVENTS_BY_KEY["SecretPortal"])

    assert facts["event_key"] == "SecretPortal"
    assert facts["event_id"] == "SecretPortal"
    assert facts["pool_bucket"] == "special_one_time"
    assert "playtime_seconds_gte_800" in facts["gating_flags"]
