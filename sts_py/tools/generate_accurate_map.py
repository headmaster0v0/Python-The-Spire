"""
Generate accurate Chinese name mapping for all relics.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sts_py.engine.content.relics import ALL_RELICS
from sts_py.tools.wiki_bilingual_scraper import BilingualWikiScraper


def get_wiki_cn_name(project_id: str, current_cn: str, scraper: BilingualWikiScraper) -> str | None:
    wiki_en = scraper.RELIC_NAME_MAP.get(project_id, project_id)

    wiki_data = scraper.fetch_relic_en(wiki_en)
    if wiki_data and not wiki_data.get("error"):
        cn_from_en = wiki_data.get("name_cn", "")
        if cn_from_en:
            return cn_from_en

    wiki_data_cn = scraper.fetch_relic_cn(current_cn)
    if wiki_data_cn and not wiki_data_cn.get("error"):
        return wiki_data_cn.get("name", "")

    return None


def generate_accurate_map():
    print("=== Generating Accurate Chinese Name Map ===\n")

    scraper = BilingualWikiScraper(use_cache=True)

    all_changes = {}

    for project_id in sorted(ALL_RELICS.keys()):
        relic = ALL_RELICS[project_id]
        current_cn = relic.name

        wiki_cn = get_wiki_cn_name(project_id, current_cn, scraper)

        if wiki_cn and wiki_cn != current_cn:
            all_changes[project_id] = {
                "from": current_cn,
                "to": wiki_cn,
            }

    print(f"Total relics: {len(ALL_RELICS)}")
    print(f"Changes needed: {len(all_changes)}\n")

    if all_changes:
        print(f"{'='*80}")
        print(f"{'ID':<25} {'Current':<12} {'Wiki CN':<12}")
        print(f"{'='*80}")
        for pid, change in sorted(all_changes.items()):
            print(f"{pid:<25} {change['from'][:10]:<12} {change['to'][:10]:<12}")

    return all_changes


if __name__ == "__main__":
    changes = generate_accurate_map()
    print(f"\n\nJSON format for updates:")
    import json
    update_dict = {k: v["to"] for k, v in changes.items()}
    print(json.dumps(update_dict, ensure_ascii=False, indent=2))