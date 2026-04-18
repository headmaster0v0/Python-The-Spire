from __future__ import annotations

from sts_py.engine.run.events import build_event
from sts_py.terminal.catalog import translate_event_name
from sts_py.terminal.render import render_event_choice_lines


def test_phase271_translate_event_name_uses_event_key_for_canonical_runtime_ids() -> None:
    assert translate_event_name(build_event("Big Fish")) == "大鱼"


def test_phase271_event_surface_uses_official_chinese_when_snapshot_is_available() -> None:
    lines = render_event_choice_lines(build_event("The Woman in Blue"))

    assert lines
    assert "药水" in lines[0]
    assert all("�" not in line for line in lines)
    assert any("20" in line or "30" in line or "40" in line for line in lines[1:])


def test_phase271_placeholder_like_stagewide_surface_is_replaced_with_official_copy() -> None:
    lines = render_event_choice_lines(build_event("MindBloom"))

    assert lines
    assert "真实" in lines[0]
    assert any("无法再回复生命" in line for line in lines[1:])
    assert not any("Nothing happens" in line for line in lines)
