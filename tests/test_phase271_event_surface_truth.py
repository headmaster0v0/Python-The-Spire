from __future__ import annotations

from sts_py.engine.run.events import build_event
from sts_py.terminal.catalog import translate_event_name
from sts_py.terminal.render import render_event_choice_lines


def test_phase271_translate_event_name_uses_event_key_for_canonical_runtime_ids() -> None:
    assert translate_event_name(build_event("Big Fish")) == "大鱼"


def test_phase271_event_surface_falls_back_to_presentable_english_when_cn_is_broken() -> None:
    lines = render_event_choice_lines(build_event("The Woman in Blue"))

    assert lines
    assert "woman in blue" in lines[0].lower()
    assert all("�" not in line for line in lines)
    assert any("20" in line or "30" in line or "40" in line for line in lines[1:])


def test_phase271_placeholder_like_stagewide_surface_is_replaced_with_canonical_copy() -> None:
    lines = render_event_choice_lines(build_event("MindBloom"))

    assert lines
    assert "strange bloom" in lines[0].lower()
    assert any("mark of the bloom" in line.lower() for line in lines[1:])
    assert not any("Nothing happens" in line for line in lines)
