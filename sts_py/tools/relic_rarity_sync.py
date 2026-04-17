"""
Relic Rarity Sync - Update project relic tiers based on wiki data.

Wiki Rarity → Project RelicTier mapping:
  - Starter → STARTER
  - Common → COMMON
  - Uncommon → UNCOMMON
  - Rare → RARE
  - Boss → BOSS
  - (Shop items in wiki are marked as COMMON/UNCOMMON/RARE)
"""
from __future__ import annotations

import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sts_py.engine.content.relics import ALL_RELICS, RelicTier
from sts_py.tools.wiki_bilingual_scraper import BilingualWikiScraper

RELIC_WIKI_TO_PROJECT = {
    "Burning Blood": "BurningBlood",
    "Ring of the Snake": "RingOfTheSnake",
    "Ring of the Serpent": "RingOfTheSerpent",
    "Akabeko": "Akabeko",
    "Cracked Core": "CrackedCore",
    "Pure Water": "PureWater",
    "Strange Spoon": "StrangeSpoon",
    "Smiling Mask": "SmilingMask",
    "War Paint": "WarPaint",
    "Centennial Puzzle": "CentennialPuzzle",
    "Singing Bowl": "SingingBowl",
    "The Specimen": "TheSpecimen",
    "The Courier": "TheCourier",
    "Mummified Hand": "MummifiedHand",
    "Lantern": "Lantern",
    "Dolly's Mirror": "DollysMirror",
    "Spirit Shield": "SpiritShield",
    "Pen Nib": "PenNib",
    "Brimstone": "Brimstone",
    "Tungsten Rod": "TungstenRod",
    "Nuclear Battery": "NuclearBattery",
    "Electric Blood": "ElectricBlood",
    "Juzu Armband": "JuzuArmband",
    "Gremlin Visage": "GremlinVisage",
    "Shining Necklace": "ShiningNecklace",
    "Bottled Flame": "BottledFlame",
    "Bottled Lightning": "BottledLightning",
    "Bottled Tornado": "BottledTornado",
    "Duality": "Duality",
    "Snecko Skull": "SneckoSkull",
    "Calipers": "Calipers",
    "Membership Card": "MembershipCard",
    "The Arbitger": "TheArbiter",
    "Face of Cleric": "FaceOfCleric",
    "Strike Dummy": "StrikeDummy",
    "Frozen Egg 2": "FrozenEgg2",
    "Frozen Egg 3": "FrozenEgg3",
    "Singing Bowl 2": "SingingBowl2",
    "War Paint 2": "WarPaint2",
    "War Paint 3": "WarPaint3",
    "Prayer Wheel": "PrayerWheel",
    "Bond of Pain": "BondOfPain",
    "Bird Faced Urn": "BirdFacedUrn",
    "Strange Spoon 2": "StrangeSpoon2",
    "NeowsBlessing": "NeowsBlessing",
    "Bottled Flame 2": "BottledFlame2",
    "Bottled Lightning 2": "BottledLightning2",
    "Bottled Tornado 2": "BottledTornado2",
    "Empty Cage 2": "EmptyCage2",
    "Ancient Tea Set": "AncientTeaSet",
    "The Specimen 2": "TheSpecimen2",
    "Gambling Chip": "GamblingChip",
    "Charon": "Charon",
    "Social熵": "Social熵",
    "Spirit Shield 2": "SpiritShield2",
    "Spirit Shield 3": "SpiritShield3",
    "Bottled Flame 3": "BottledFlame3",
    "Bottled Lightning 3": "BottledLightning3",
    "Bottled Tornado 3": "BottledTornado3",
    "Cultist Mask": "CultistMask",
    "Green Mask": "GreenMask",
    "Red Mask": "RedMask",
    "Blue Mask": "BlueMask",
    "Snecko Eye": "SneckoEye",
    "Philosopher's Stone": "PhilosophersStone",
    "Pandora's Box": "PandorasBox",
    "Cursed Key": "CursedKey",
    "Prayer Wheel 2": "PrayerWheel2",
    "Frozen Egg": "FrozenEgg",
    "Ancient Tea Set 2": "AncientTeaSet2",
    "Ancient Tea Set 3": "AncientTeaSet3",
    "Mummified Hand 2": "MummifiedHand2",
    "Mummified Hand 3": "MummifiedHand3",
    "The Courier 2": "TheCourier2",
    "The Courier 3": "TheCourier3",
    "Dolly's Mirror 2": "DollysMirror2",
    "Dolly's Mirror 3": "DollysMirror3",
    "Snecko Skull 2": "SneckoSkull2",
    "Snecko Skull 3": "SneckoSkull3",
    "N'loth's Gift": "NlothsGift",
    "N'loth's Mask": "NlothsMask",
    "N'loth's Hungry Face": "NlothsHungryFace",
    "N'loth": "Nloth",
    "Slavers Cross": "SlaversCross",
    "Blue Candle": "BlueCandle",
    "Burning Blood 2": "BurningBlood2",
    "Ring of the Snake 2": "RingOfTheSnake2",
    "Ring of the Serpent 2": "RingOfTheSerpent2",
    "Orichalcum": "Orichalcum",
    "Turnip": "Turnip",
    "Ginger": "Ginger",
    "Meat on the Bone": "MeatOnTheBone",
    "Lead Stone": "LeadStone",
    "Miracle": "Miracle",
    "Glow": "Glow",
    "Egg": "Egg",
    "Toxic Egg 2": "ToxicEgg2",
    "Toxic Egg 3": "ToxicEgg3",
    "Reprogram": "Reprogram",
    "Dark Core": "DarkCore",
    "Dark Core 2": "DarkCore2",
    "Dark Core 3": "DarkCore3",
    "Cracked Core 2": "CrackedCore2",
    "Cracked Core 3": "CrackedCore3",
    "Battery": "Battery",
    "Battery 2": "Battery2",
    "CaptainsWheel": "CaptainsWheel",
    "Captain's Wheel": "CaptainWheel",
    "Ice Cream": "IceCream",
    "Shovel": "Shovel",
    "Shovel 2": "Shovel2",
    "Shovel 3": "Shovel3",
    "Greed": "Greed",
    "Gold Plated Cables": "GoldPlatedCables",
    "Nilry's Code": "NilysCode",
    "Dark Stone": "DarkStone",
    "Emotion Chip": "EmotionChip",
    "Iron Coin": "IronCoin",
    "Old Coin": "OldCoin",
    "Medical Kit": "MedicalKit",
    "Medicinal Herb": "MedicinalHerb",
    "Shield": "Shield",
    "Armaments": "Armaments",
    "Armaments 2": "Armaments2",
    "Armaments 3": "Armaments3",
    "Regal Pillow": "RegalPillow",
    "Duffel Bag": "DuffelBag",
    "Inserter": "Inserter",
    "Teleportation Card": "TeleportationCard",
    "Nunchaku": "Nunchaku",
    "Soundstone": "Soundstone",
    "Whale": "Whale",
    "Prayer Wheel 3": "PrayerWheel3",
    "Ritual Dagger": "RitualDagger",
    "Orichalcum 2": "Orichalcum2",
    "Orichalcum 3": "Orichalcum3",
    "Puppet": "Puppet",
    "Puppet 2": "Puppet2",
    "Puppet 3": "Puppet3",
    "Dead Adventurer": "DeadAdventurer",
    "Lizard Skull": "LizardSkull",
    "Warped Tongs": "WarpedTongs",
    "Chameleon Ring": "ChameleonRing",
    "Molten Egg 2": "MoltenEgg2",
    "Molten Egg 3": "MoltenEgg3",
    "Molten Egg": "MoltenEgg",
    "Toxic Egg": "ToxicEgg",
    "Golden Idol": "GoldenIdol",
    "Enchiridion": "Enchiridion",
    "Lee's Ear": "LeesEar",
    "Lee's Cup": "LeesCup",
    "Lee's Waffle": "Lee'sWaffle",
    "Fruit": "Fruit",
    "Flower": "Flower",
    "Flower 2": "Flower2",
    "Flower 3": "Flower3",
    "Small": "Small",
    "The Bomb": "TheBomb",
    "Dark Tags": "DarkTags",
    "Rusted Key": "RustedKey",
    "The Clock": "TheClock",
    "Red Circlet": "RedCirclet",
    "Blue Circlet": "BlueCirclet",
    "Ancient Power": "AncientPower",
    "Ancient Power 2": "AncientPower2",
    "Ancient Power 3": "AncientPower3",
    "Ceramic Fish": "CeramicFish",
    "Pinchy": "Pinchy",
    "Mark of Pain": "MarkOfPain",
    "Mark of the Bloom": "MarkOfTheBloom",
    "Kunai": "Kunai",
    "Fan": "Fan",
    "Shuriken": "Shuriken",
    "Chrysalis": "Chrysalis",
    "Sash": "Sash",
    "Ring of the Serpent": "RingOfTheSerpent",
}


def normalize_wiki_rarity(rarity_str: str) -> str:
    rarity_str = rarity_str.replace("[[", "").replace("]]", "").replace("Relics#", "").replace("relics#", "")
    rarity_lower = rarity_str.lower()
    if "starter" in rarity_lower:
        return "STARTER"
    elif "common" in rarity_lower:
        return "COMMON"
    elif "uncommon" in rarity_lower:
        return "UNCOMMON"
    elif "rare" in rarity_lower:
        return "RARE"
    elif "boss" in rarity_lower:
        return "BOSS"
    elif "shop" in rarity_lower:
        return "SHOP"
    elif "event" in rarity_lower:
        return "EVENT"
    return "UNKNOWN"


def sync_relic_rarity(dry_run: bool = False) -> dict:
    print("=== Relic Rarity Sync ===\n")

    scraper = BilingualWikiScraper(use_cache=True)

    wiki_stats_before = Counter()
    wiki_stats_after = Counter()
    project_stats = Counter()
    changes = []
    errors = []

    for relic_id in sorted(ALL_RELICS.keys()):
        project_stats[ALL_RELICS[relic_id].tier.value] += 1

    print("Project tier distribution (before):")
    for tier, count in sorted(project_stats.items()):
        print(f"  {tier}: {count}")

    print("\nFetching wiki rarity data...")

    rarity_map = {}
    for wiki_name, project_id in RELIC_WIKI_TO_PROJECT.items():
        try:
            wiki_data = scraper.fetch_relic_en(wiki_name)
            if wiki_data and not wiki_data.get("error"):
                rarity = wiki_data.get("rarity", "")
                tier = normalize_wiki_rarity(rarity)
                rarity_map[project_id] = tier
                wiki_stats_before[tier] += 1
        except Exception as e:
            errors.append({"relic_id": project_id, "error": str(e)})

    print("\nWiki rarity distribution:")
    for tier, count in sorted(wiki_stats_before.items()):
        print(f"  {tier}: {count}")

    if dry_run:
        print("\n=== DRY RUN - No changes made ===")
        return {
            "project_before": dict(project_stats),
            "wiki_distribution": dict(wiki_stats_before),
            "changes": [],
        }

    tier_mapping = {
        "STARTER": RelicTier.STARTER,
        "COMMON": RelicTier.COMMON,
        "UNCOMMON": RelicTier.UNCOMMON,
        "RARE": RelicTier.RARE,
        "BOSS": RelicTier.BOSS,
        "UNKNOWN": RelicTier.SPECIAL,
    }

    for relic_id, wiki_tier in rarity_map.items():
        if relic_id not in ALL_RELICS:
            continue
        relic = ALL_RELICS[relic_id]
        new_tier = tier_mapping.get(wiki_tier, RelicTier.SPECIAL)
        if relic.tier != new_tier:
            old_tier = relic.tier.value
            changes.append({
                "relic_id": relic_id,
                "name": relic.name,
                "old_tier": old_tier,
                "new_tier": new_tier.value,
            })
            relic.tier = new_tier

    project_stats_after = Counter()
    for relic_id in ALL_RELICS.keys():
        project_stats_after[ALL_RELICS[relic_id].tier.value] += 1

    print("\nProject tier distribution (after):")
    for tier, count in sorted(project_stats_after.items()):
        print(f"  {tier}: {count}")

    print(f"\nTotal changes: {len(changes)}")

    if errors:
        print(f"Errors: {len(errors)}")

    return {
        "project_before": dict(project_stats),
        "project_after": dict(project_stats_after),
        "wiki_distribution": dict(wiki_stats_before),
        "changes": changes,
        "errors": errors,
    }


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    sync_relic_rarity(dry_run=dry_run)
