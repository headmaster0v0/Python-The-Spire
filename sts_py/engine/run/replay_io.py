from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sts_py.engine.core.canon import to_canonical_json
from sts_py.engine.core.decisions import Decision
from sts_py.engine.run.types import Replay


def write_replay(path: str | Path, replay: Replay) -> None:
    p = Path(path)
    p.write_text(to_canonical_json(replay.to_dict()), encoding="utf-8")


def read_replay(path: str | Path) -> Replay:
    p = Path(path)
    d = json.loads(p.read_text(encoding="utf-8"))
    decisions = [Decision(spec_id=x["spec_id"], params=x.get("params", {})) for x in d["decisions"]]
    return Replay(
        engine_version=d["engine_version"],
        content_hash=d["content_hash"],
        game_version=d["game_version"],
        seed=d["seed"],
        decisions=decisions,
    )
