from __future__ import annotations

from sts_py.engine.combat.combat_state import CombatState, Entity
from sts_py.engine.core.actions import ActionQueue
from sts_py.engine.combat.actions import DealDamage, EndTurn, GainBlock
from sts_py.engine.run.engine import Engine
from sts_py.engine.run.types import EngineState


def test_combat_actions_progress_state_and_remain_deterministic():
    cs = CombatState(player=Entity(id="p", hp=80, max_hp=80), monster=Entity(id="m", hp=40, max_hp=40))
    s1 = EngineState(version="0", data={"combat": cs}, action_queue=ActionQueue(pending=[]))
    e1 = Engine(s1)

    s1.action_queue.push(GainBlock(target="player", amount=5))
    s1.action_queue.push(DealDamage(source="player", target="monster_0", amount=6))
    s1.action_queue.push(EndTurn())
    h1 = e1.step_until_blocked().state_hash

    # replay same sequence
    cs2 = CombatState(player=Entity(id="p", hp=80, max_hp=80), monster=Entity(id="m", hp=40, max_hp=40))
    s2 = EngineState(version="0", data={"combat": cs2}, action_queue=ActionQueue(pending=[]))
    e2 = Engine(s2)
    s2.action_queue.push(GainBlock(target="player", amount=5))
    s2.action_queue.push(DealDamage(source="player", target="monster_0", amount=6))
    s2.action_queue.push(EndTurn())
    h2 = e2.step_until_blocked().state_hash

    assert h1 == h2
    assert cs2.turn == 2
