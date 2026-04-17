"""
Comprehensive Chinese Name Sync for all relics.
Fuzzy search: Try 2-char and 1-char substrings from the start.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sts_py.engine.content.relics import ALL_RELICS
from sts_py.tools.wiki_bilingual_scraper import BilingualWikiScraper


def get_wiki_cn_name(current: str, scraper: BilingualWikiScraper) -> tuple[str | None, str]:
    data = scraper.fetch_relic_cn(current)
    if data and not data.get("error") and data.get("name"):
        return data.get("name"), "exact"

    if len(current) >= 2:
        for end in range(2, len(current) + 1):
            part = current[:end]
            results = scraper._search_cn_wiki(part)
            if results:
                data = scraper.fetch_relic_cn(results[0])
                if data and not data.get("error") and data.get("name"):
                    return data.get("name"), f"fuzzy({part})"

    for char in current:
        if char.strip():
            results = scraper._search_cn_wiki(char)
            if results:
                data = scraper.fetch_relic_cn(results[0])
                if data and not data.get("error") and data.get("name"):
                    return data.get("name"), f"char({char})"

    return None, "not_found"


def sync_all():
    print("=== Chinese Name Sync ===\n")

    scraper = BilingualWikiScraper(use_cache=False)

    changes = []
    not_found = []

    for project_id in sorted(ALL_RELICS.keys()):
        relic = ALL_RELICS[project_id]
        current = relic.name

        wiki_cn, method = get_wiki_cn_name(current, scraper)

        if wiki_cn and wiki_cn != current:
            changes.append({
                "id": project_id,
                "from": current,
                "to": wiki_cn,
                "method": method,
            })
        elif not wiki_cn:
            not_found.append({
                "id": project_id,
                "current": current,
            })

    print(f"Total: {len(ALL_RELICS)}")
    print(f"Changes: {len(changes)}")
    print(f"Not found: {len(not_found)}\n")

    if changes:
        print(f"{'='*80}")
        print(f"{'ID':<25} {'Current':<14} {'Wiki CN':<14} {'Method'}")
        print(f"{'='*80}")
        for c in sorted(changes, key=lambda x: x["method"]):
            print(f"{c['id']:<25} {c['from'][:12]:<14} {c['to'][:12]:<14} {c['method']}")

    if not_found:
        print(f"\nNot found ({len(not_found)}):")
        for nf in not_found:
            print(f"  {nf['id']}: {nf['current']}")

    return changes


if __name__ == "__main__":
    sync_all()
