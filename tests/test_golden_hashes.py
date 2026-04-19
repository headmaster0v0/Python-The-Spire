from __future__ import annotations

from sts_py.engine.combat.combat_state import CombatState, Entity
from sts_py.engine.combat.actions import DealDamage, EndTurn, GainBlock
from sts_py.engine.core.actions import ActionQueue
from sts_py.engine.core.builtin_actions import SetValue
from sts_py.engine.run.engine import Engine
from sts_py.engine.run.replay_io import read_replay, write_replay
from sts_py.engine.run.types import EngineState, Replay
from sts_py.engine.core.decisions import Decision


def test_golden_replay_hash_sequence(workspace_tmp_path):
    # "Golden" here just means we pin expected hashes for regression.
    # We keep it tiny for now.
    s = EngineState(version="0", data={}, action_queue=ActionQueue(pending=[]))
    e = Engine(s)

    h0 = e.compute_hash()
    s.action_queue.push(SetValue(path="a", value=1))
    r1 = e.step_until_blocked()

    # Save a replay file (structure) for future use.
    replay = Replay(
        engine_version="0.0.1",
        content_hash="dev",
        game_version="unknown",
        seed="123",
        decisions=[Decision(spec_id="noop", params={})],
    )
    p = workspace_tmp_path / "golden.json"
    write_replay(p, replay)
    _ = read_replay(p)

    assert h0 == "94eab03ce89fd5e4c88f574ed036d65f2bd4482f3e3cc3b278cb3f3438029e38"
    assert r1.state_hash == "63d19ed4e420a365f190db5700fb6c0c00258188316783bc46b39c9c5042b91e"


def test_golden_combat_hash(workspace_tmp_path):
    cs = CombatState(player=Entity(id="p", hp=80, max_hp=80), monster=Entity(id="m", hp=40, max_hp=40))
    s = EngineState(version="0", data={"combat": cs}, action_queue=ActionQueue(pending=[]))
    e = Engine(s)

    s.action_queue.push(GainBlock(target="player", amount=5))
    s.action_queue.push(DealDamage(source="player", target="monster_0", amount=6))
    s.action_queue.push(EndTurn())
    r = e.step_until_blocked()

    # Updated hash due to new CombatState structure with powers/card manager fields
    # Also updated for PowerContainer.change_log field addition
    # Updated 2026-03-25: Player.id field addition
    # Updated 2026-04-04: CombatState dataclass expanded with internal choice/reward state
    # Updated 2026-04-19: hash now follows explicit nested to_dict() contracts
    # instead of drifting with raw dataclass field expansion.
    assert r.state_hash == "52c64e1b00ad877c07479f0644b7f2ad184c1f74850e87cf6754740d8a036a93"
