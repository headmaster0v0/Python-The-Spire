from __future__ import annotations

from sts_py.tools.run_snapshot import RunSnapshot


def test_run_snapshot_parses_metrics_and_deck():
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
        "cards": [{"id": "Strike"}, {"id": "Bash"}],
        "relics": ["BurningBlood"],
        "metric_path_taken": ["M", "M"],
        "metric_card_choices": [
            {"floor": 1, "picked": "A", "not_picked": ["B", "C"]},
        ],
        "metric_damage_taken": [{"damage": 1, "floor": 1, "enemies": "X", "turns": 1}],
    }
    snap = RunSnapshot.from_autosave(d)
    assert snap.seed == 1
    assert snap.deck_ids == ("Strike", "Bash")
    assert snap.path_taken == ("M", "M")
    assert snap.card_choices[0].picked == "A"
