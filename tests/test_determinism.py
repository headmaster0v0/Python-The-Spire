from __future__ import annotations

from sts_py.engine.core.actions import ActionQueue
from sts_py.engine.core.builtin_actions import SetValue
from sts_py.engine.run.engine import Engine, EngineState


def test_deterministic_hash_same_actions_same_hash():
    s1 = EngineState(version="0", data={}, action_queue=ActionQueue(pending=[]))
    e1 = Engine(s1)
    s1.action_queue.push(SetValue(path="a", value=1))
    r1 = e1.step_until_blocked()

    s2 = EngineState(version="0", data={}, action_queue=ActionQueue(pending=[]))
    e2 = Engine(s2)
    s2.action_queue.push(SetValue(path="a", value=1))
    r2 = e2.step_until_blocked()

    assert r1.state_hash == r2.state_hash


def test_hash_changes_when_state_changes():
    s = EngineState(version="0", data={}, action_queue=ActionQueue(pending=[]))
    e = Engine(s)
    h0 = e.compute_hash()
    s.action_queue.push(SetValue(path="a", value=1))
    r = e.step_until_blocked()
    assert r.state_hash != h0
