"""
Sync Chinese relic names from Chinese wiki - Output changes for manual update.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sts_py.engine.content.relics import ALL_RELICS
from sts_py.tools.wiki_bilingual_scraper import BilingualWikiScraper


def generate_name_map():
    print("=== Generating Chinese Name Update Map ===\n")

    scraper = BilingualWikiScraper(use_cache=True)

    name_changes = {}

    for project_id in sorted(ALL_RELICS.keys()):
        relic = ALL_RELICS[project_id]
        current_cn = relic.name

        wiki_data_cn = scraper.fetch_relic_cn(current_cn)
        if wiki_data_cn and not wiki_data_cn.get("error"):
            wiki_cn = wiki_data_cn.get("name", "")
            if wiki_cn and wiki_cn != current_cn:
                name_changes[project_id] = {
                    "from": current_cn,
                    "to": wiki_cn,
                    "en": wiki_data_cn.get("name_en", ""),
                }

    print(f"Name changes needed: {len(name_changes)}\n")
    for pid, change in sorted(name_changes.items()):
        print(f'  "{pid}": ("{change["from"]}", "{change["to"]}"),  # EN: {change["en"]}')

    return name_changes


if __name__ == "__main__":
    generate_name_map()
