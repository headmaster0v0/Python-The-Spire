from __future__ import annotations

from pathlib import Path

from sts_py.engine.run.events import EVENTS_BY_KEY, build_event
from sts_py.tools import wiki_audit
from sts_py.tools.wiki_audit import EVENT_FLOW_FACTS_BY_KEY, build_cli_raw_snapshot, build_event_source_facts


def test_phase275_event_flow_facts_cover_all_runtime_events() -> None:
    assert set(EVENT_FLOW_FACTS_BY_KEY) == set(EVENTS_BY_KEY)


def test_phase275_event_source_facts_expose_rng_stream_truth() -> None:
    goop = build_event_source_facts(build_event("World of Goop"))
    tome = build_event_source_facts(build_event("Cursed Tome"))
    trader = build_event_source_facts(build_event("FaceTrader"))
    transmog = build_event_source_facts(build_event("Transmorgrifier"))

    assert "misc_rng" in goop["rng_streams"]
    assert "misc_rng" in tome["rng_streams"]
    assert "misc_rng" in trader["rng_streams"]
    assert "card_random_rng" in transmog["rng_streams"]


def test_phase275_cli_raw_snapshot_includes_neow_truth_entity() -> None:
    snapshot = build_cli_raw_snapshot(Path.cwd(), enable_network=False)

    assert "neow" in snapshot["runtime_inventory"]
    assert snapshot["runtime_inventory"]["neow"] == ["NeowEvent"]

    record = next(
        item for item in snapshot["records"]
        if item["entity_type"] == "neow" and item["entity_id"] == "NeowEvent"
    )

    assert record["runtime_name_en"] == "Neow"
    assert record["runtime_facts"]["screen_count"] == 4
    assert record["runtime_facts"]["reward_option_groups"] == {"mini": 2, "full": 4}
    assert record["runtime_facts"]["rng_streams"] == ["neow_rng"]
