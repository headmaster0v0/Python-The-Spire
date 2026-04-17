from __future__ import annotations

from sts_py.engine.run.replay_io import write_replay
from sts_py.tools.autosave_decode import load_autosave_json
from sts_py.tools.replay_skeleton import build_replay_skeleton
from sts_py.tools.run_snapshot import RunSnapshot


def test_build_replay_skeleton_from_autosave(workspace_tmp_path):
    # Use a synthetic autosave dict via RunSnapshot test would be ideal, but here we
    # just validate structure from a minimal dict.
    d = {
        "seed": 1,
        "seed_set": True,
        "floor_num": 3,
        "act_num": 1,
        "current_room": "room",
        "current_health": 10,
        "max_health": 18,
        "gold": 99,
        "neow_bonus": "TEN_PERCENT_HP_BONUS",
        "neow_cost": "NONE",
        "cards": [{"id": "Strike"}],
        "relics": [],
        "metric_path_taken": ["M", "M"],
        "metric_card_choices": [
            {"floor": 1, "picked": "Flame Barrier", "not_picked": ["A", "B"]},
        ],
        "metric_damage_taken": [],
    }
    snap = RunSnapshot.from_autosave(d)
    sk = build_replay_skeleton(snap)
    rep = sk.to_replay()

    p = workspace_tmp_path / "rep.json"
    write_replay(p, rep)
    assert p.read_text(encoding="utf-8")
    assert rep.decisions[0].spec_id == "neow.choose_bonus"
