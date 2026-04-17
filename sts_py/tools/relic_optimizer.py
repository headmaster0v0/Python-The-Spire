"""
Relic Optimizer - Batch enhance all relics with wiki data.

Usage:
    python relic_optimizer.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sts_py.engine.content.relics import ALL_RELICS
from sts_py.tools.relic_enhancer import RelicEnhancer


def optimize_all_relics(dry_run: bool = False) -> dict:
    print("=== Relic Optimizer ===\n")

    enhancer = RelicEnhancer(use_cache=True)

    stats = {
        "total": len(ALL_RELICS),
        "enriched_name_en": 0,
        "enriched_flavor": 0,
        "enriched_rarity": 0,
        "enriched_wiki_url": 0,
        "enriched_related_links": 0,
        "errors": [],
    }

    enhanced_data = {}
    failed_relics = []

    print(f"Processing {stats['total']} relics...")

    for i, relic_id in enumerate(sorted(ALL_RELICS.keys()), 1):
        try:
            relic = ALL_RELICS[relic_id]
            wiki_data_en = enhancer.fetch_wiki_data_en(relic_id)
            wiki_data_cn = enhancer.fetch_wiki_data_cn(relic.name)

            enhanced = {
                "id": relic_id,
                "name_cn": relic.name,
                "name_en": wiki_data_en.get("name_en", "") or wiki_data_cn.get("name_en", ""),
                "description": wiki_data_en.get("description", "") or wiki_data_cn.get("description", ""),
                "flavor": wiki_data_en.get("flavor", "") or wiki_data_cn.get("flavor", ""),
                "rarity": wiki_data_en.get("rarity", "") or wiki_data_cn.get("rarity", ""),
                "class": wiki_data_en.get("class", "") or wiki_data_cn.get("class", ""),
                "wiki_url_en": wiki_data_en.get("url", ""),
                "wiki_url_cn": wiki_data_cn.get("url", ""),
                "related_links": wiki_data_en.get("related_links", []) + wiki_data_cn.get("related_links", []),
            }

            if enhanced["name_en"]:
                stats["enriched_name_en"] += 1
            if enhanced["flavor"]:
                stats["enriched_flavor"] += 1
            if enhanced["rarity"]:
                stats["enriched_rarity"] += 1
            if enhanced["wiki_url_en"] or enhanced["wiki_url_cn"]:
                stats["enriched_wiki_url"] += 1
            if enhanced["related_links"]:
                stats["enriched_related_links"] += 1

            enhanced_data[relic_id] = enhanced

            if i % 20 == 0:
                print(f"  Processed {i}/{stats['total']}...")

        except Exception as e:
            stats["errors"].append({"relic_id": relic_id, "error": str(e)})
            failed_relics.append(relic_id)

    print(f"\n=== Enhancement Stats ===")
    print(f"Total relics: {stats['total']}")
    print(f"Name EN enriched: {stats['enriched_name_en']} ({100*stats['enriched_name_en']//stats['total']}%)")
    print(f"Flavor enriched: {stats['enriched_flavor']} ({100*stats['enriched_flavor']//stats['total']}%)")
    print(f"Rarity enriched: {stats['enriched_rarity']} ({100*stats['enriched_rarity']//stats['total']}%)")
    print(f"Wiki URL enriched: {stats['enriched_wiki_url']} ({100*stats['enriched_wiki_url']//stats['total']}%)")
    print(f"Related Links enriched: {stats['enriched_related_links']} ({100*stats['enriched_related_links']//stats['total']}%)")

    if stats["errors"]:
        print(f"\nErrors: {len(stats['errors'])}")
        for err in stats["errors"][:5]:
            print(f"  - {err['relic_id']}: {err['error']}")

    if not dry_run:
        output_file = Path(__file__).parent.parent / "data" / "enhanced_relics.json"
        output_file.parent.mkdir(exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "generated_at": datetime.now().isoformat(),
                "stats": {k: v for k, v in stats.items() if k != "errors"},
                "relics": enhanced_data
            }, f, ensure_ascii=False, indent=2)

        print(f"\nSaved to: {output_file}")

    return stats


def show_sample_enhanced():
    enhancer = RelicEnhancer(use_cache=True)

    print("\n=== Sample Enhanced Relics ===\n")

    samples = ["BurningBlood", "Akabeko", "RingOfTheSnake", "NilysCode"]

    for relic_id in samples:
        if relic_id not in ALL_RELICS:
            continue

        relic = ALL_RELICS[relic_id]
        wiki_data = enhancer.fetch_wiki_data_en(relic_id)

        print(f"--- {relic.name} ({relic_id}) ---")
        print(f"  Name EN: {wiki_data.get('name_en', 'N/A')}")
        print(f"  Rarity: {wiki_data.get('rarity', 'N/A')}")
        print(f"  Class: {wiki_data.get('class', 'N/A')}")
        print(f"  Flavor: {wiki_data.get('flavor', 'N/A')[:60]}...")
        print(f"  Wiki URL: {wiki_data.get('url', 'N/A')}")
        print(f"  Related Links: {len(wiki_data.get('related_links', []))}")
        print()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv

    if "--sample" in sys.argv:
        show_sample_enhanced()
    else:
        optimize_all_relics(dry_run=dry_run)
