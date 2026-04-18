from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sts_py.engine.monsters.official_monster_strings import build_official_monster_strings_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract normalized official Slay the Spire monster strings from desktop-1.0.jar")
    parser.add_argument("--jar", type=Path, default=Path("desktop-1.0.jar"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("sts_py/data/official_monster_strings.json"))
    args = parser.parse_args()

    snapshot = build_official_monster_strings_snapshot(args.jar, repo_root=args.repo_root.resolve())
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
