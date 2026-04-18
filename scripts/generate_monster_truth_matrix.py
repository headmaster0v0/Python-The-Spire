from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sts_py.engine.monsters.monster_truth import build_monster_truth_matrix_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate normalized monster truth matrix for runtime, audit, and CLI rendering")
    parser.add_argument("--output", type=Path, default=Path("sts_py/data/monster_truth_matrix.json"))
    args = parser.parse_args()

    snapshot = build_monster_truth_matrix_snapshot()
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
