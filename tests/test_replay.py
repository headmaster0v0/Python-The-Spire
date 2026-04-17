from __future__ import annotations

from sts_py.engine.core.actions import ActionQueue
from sts_py.engine.core.builtin_actions import SetValue
from sts_py.engine.core.decisions import Decision
from sts_py.engine.run.engine import Engine
from sts_py.engine.run.replay_io import read_replay, write_replay
from sts_py.engine.run.types import EngineState, Replay


def test_replay_roundtrip(workspace_tmp_path):
    replay = Replay(
        engine_version="0.0.1",
        content_hash="dev",
        game_version="unknown",
        seed="123",
        decisions=[Decision(spec_id="noop", params={"x": 1})],
    )
    p = workspace_tmp_path / "r.json"
    write_replay(p, replay)
    replay2 = read_replay(p)
    assert replay2.to_dict() == replay.to_dict()


def test_replay_produces_same_final_hash(workspace_tmp_path):
    # A trivial deterministic "run" driven by a replay.
    s1 = EngineState(version="0", data={}, action_queue=ActionQueue(pending=[]))
    e1 = Engine(s1)
    s1.action_queue.push(SetValue(path="a", value=1))
    h1 = e1.step_until_blocked().state_hash

    # Persist decisions even though engine ignores them today; this is scaffolding.
    replay = Replay(
        engine_version="0.0.1",
        content_hash="dev",
        game_version="unknown",
        seed="123",
        decisions=[Decision(spec_id="ignored", params={})],
    )
    p = workspace_tmp_path / "r.json"
    write_replay(p, replay)
    _ = read_replay(p)

    s2 = EngineState(version="0", data={}, action_queue=ActionQueue(pending=[]))
    e2 = Engine(s2)
    s2.action_queue.push(SetValue(path="a", value=1))
    h2 = e2.step_until_blocked().state_hash

    assert h1 == h2
