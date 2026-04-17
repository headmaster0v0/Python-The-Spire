from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sts_py.engine.core.decisions import Decision
from sts_py.engine.run.types import Replay
from sts_py.tools.run_snapshot import RunSnapshot


@dataclass(frozen=True)
class ReplaySkeleton:
    seed: int
    decisions: tuple[Decision, ...]

    def to_replay(self) -> Replay:
        # content_hash/game_version will be filled later when we lock content packs.
        return Replay(
            engine_version="0.0.1",
            content_hash="dev",
            game_version="unknown",
            seed=str(self.seed),
            decisions=list(self.decisions),
        )


def build_replay_skeleton(snap: RunSnapshot) -> ReplaySkeleton:
    """Create a minimal replay skeleton from autosave metrics.

    For now we only encode:
    - Neow bonus choice
    - path taken (M/M/..)
    - card reward picks (picked card id)

    Combat card plays are not available from autosave; those require a trace.
    """

    decisions: list[Decision] = []

    if snap.neow_bonus:
        decisions.append(Decision(spec_id="neow.choose_bonus", params={"bonus": snap.neow_bonus, "cost": snap.neow_cost}))

    for i, node in enumerate(snap.path_taken, start=1):
        decisions.append(Decision(spec_id="map.choose_node", params={"step": i, "node": node}))

    for cc in snap.card_choices:
        decisions.append(
            Decision(
                spec_id="reward.pick_card",
                params={
                    "floor": cc.floor,
                    "picked": cc.picked,
                    "not_picked": list(cc.not_picked),
                },
            )
        )

    return ReplaySkeleton(seed=snap.seed, decisions=tuple(decisions))
