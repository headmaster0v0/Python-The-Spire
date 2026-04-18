from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


def build_snapshot(jar_path: Path) -> dict[str, object]:
    with zipfile.ZipFile(jar_path) as jar:
        eng = json.loads(jar.read("localization/eng/characters.json").decode("utf-8"))
        zhs = json.loads(jar.read("localization/zhs/characters.json").decode("utf-8-sig"))

    records: dict[str, object] = {}
    for key in ("Neow Event", "Neow Reward"):
        eng_record = dict(eng[key])
        zhs_record = dict(zhs[key])
        records[key] = {
            "eng": {
                "names": list(eng_record.get("NAMES", []) or []),
                "text": list(eng_record.get("TEXT", []) or []),
                "options": list(eng_record.get("OPTIONS", []) or []),
                "unique_rewards": list(eng_record.get("UNIQUE_REWARDS", []) or []),
            },
            "zhs": {
                "names": list(zhs_record.get("NAMES", []) or []),
                "text": list(zhs_record.get("TEXT", []) or []),
                "options": list(zhs_record.get("OPTIONS", []) or []),
                "unique_rewards": list(zhs_record.get("UNIQUE_REWARDS", []) or []),
            },
        }

    return {
        "schema_version": 1,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract official Slay the Spire Neow strings from desktop-1.0.jar")
    parser.add_argument(
        "--jar",
        type=Path,
        default=Path("desktop-1.0.jar"),
        help="Path to the Slay the Spire desktop jar",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("sts_py/data/official_neow_strings.json"),
        help="Path to write the normalized official Neow snapshot",
    )
    args = parser.parse_args()

    snapshot = build_snapshot(args.jar)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
