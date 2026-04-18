from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


OFFICIAL_KEY_BY_CANONICAL_EVENT_KEY = {
    "SpireHeart": "Spire Heart",
}

EVENT_ID_BY_KEY = {
    "Big Fish": "BigFish",
    "The Cleric": "Cleric",
    "Dead Adventurer": "DeadAdventurer",
    "Golden Idol": "GoldenIdolEvent",
    "Golden Wing": "GoldenWing",
    "World of Goop": "GoopPuddle",
    "Liars Game": "Sssserpent",
    "Living Wall": "LivingWall",
    "Mushrooms": "Mushrooms",
    "Scrap Ooze": "ScrapOoze",
    "Shining Light": "ShiningLight",
    "Addict": "Addict",
    "Back to Basics": "BackToBasics",
    "Beggar": "Beggar",
    "Colosseum": "Colosseum",
    "Cursed Tome": "CursedTome",
    "Drug Dealer": "DrugDealer",
    "Forgotten Altar": "ForgottenAltar",
    "Ghosts": "Ghosts",
    "Masked Bandits": "MaskedBandits",
    "Nest": "Nest",
    "The Library": "TheLibrary",
    "The Mausoleum": "TheMausoleum",
    "Vampires": "Vampires",
    "Falling": "Falling",
    "MindBloom": "MindBloom",
    "The Moai Head": "MoaiHead",
    "Mysterious Sphere": "MysteriousSphere",
    "SensoryStone": "SensoryStone",
    "Tomb of Lord Red Mask": "TombRedMask",
    "Winding Halls": "WindingHalls",
    "Match and Keep!": "GremlinMatchGame",
    "Golden Shrine": "GoldShrine",
    "Transmorgrifier": "Transmogrifier",
    "Purifier": "PurificationShrine",
    "Upgrade Shrine": "UpgradeShrine",
    "Wheel of Change": "GremlinWheelGame",
    "Accursed Blacksmith": "AccursedBlacksmith",
    "Bonfire Elementals": "Bonfire",
    "Designer": "Designer",
    "Duplicator": "Duplicator",
    "FaceTrader": "FaceTrader",
    "Fountain of Cleansing": "FountainOfCurseRemoval",
    "Knowing Skull": "KnowingSkull",
    "Lab": "Lab",
    "N'loth": "Nloth",
    "NoteForYourself": "NoteForYourself",
    "SecretPortal": "SecretPortal",
    "The Joust": "TheJoust",
    "WeMeetAgain": "WeMeetAgain",
    "The Woman in Blue": "WomanInBlue",
    "SpireHeart": "SpireHeart",
}


CANONICAL_EVENT_KEYS = list(EVENT_ID_BY_KEY)


def build_snapshot(jar_path: Path) -> dict[str, object]:
    with zipfile.ZipFile(jar_path) as jar:
        eng = json.loads(jar.read("localization/eng/events.json").decode("utf-8"))
        zhs = json.loads(jar.read("localization/zhs/events.json").decode("utf-8-sig"))

    records: dict[str, object] = {}
    for event_key in CANONICAL_EVENT_KEYS:
        official_key = OFFICIAL_KEY_BY_CANONICAL_EVENT_KEY.get(event_key, event_key)
        eng_record = dict(eng[official_key])
        zhs_record = dict(zhs[official_key])
        records[event_key] = {
            "official_key": official_key,
            "event_id": EVENT_ID_BY_KEY[event_key],
            "eng": {
                "name": str(eng_record.get("NAME", "") or ""),
                "descriptions": list(eng_record.get("DESCRIPTIONS", []) or []),
                "options": list(eng_record.get("OPTIONS", []) or []),
            },
            "zhs": {
                "name": str(zhs_record.get("NAME", "") or ""),
                "descriptions": list(zhs_record.get("DESCRIPTIONS", []) or []),
                "options": list(zhs_record.get("OPTIONS", []) or []),
            },
        }

    return {
        "schema_version": 1,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract official Slay the Spire event strings from desktop-1.0.jar")
    parser.add_argument(
        "--jar",
        type=Path,
        default=Path("desktop-1.0.jar"),
        help="Path to the Slay the Spire desktop jar",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("sts_py/data/official_event_strings.json"),
        help="Path to write the normalized official event snapshot",
    )
    args = parser.parse_args()

    snapshot = build_snapshot(args.jar)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
