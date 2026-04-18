from __future__ import annotations

import argparse
from pathlib import Path

from sts_py.engine.run.events import build_event
from sts_py.terminal.catalog import translate_event_name
from sts_py.tools.wiki_audit import (
    CN_SOURCE_ORDER,
    EN_SOURCE_ORDER,
    _generic_cn_page_candidates,
    _generic_en_page_candidates,
)
from sts_py.tools.wiki_bilingual_scraper import BilingualWikiScraper


TARGET_EVENT_KEYS = (
    "Designer",
    "Match and Keep!",
    "Mushrooms",
    "SpireHeart",
)


def validate_event_wiki_aliases(repo_root: Path) -> int:
    scraper = BilingualWikiScraper(use_cache=False)
    failures: list[str] = []

    for event_key in TARGET_EVENT_KEYS:
        event = build_event(event_key)
        runtime_name_en = str(getattr(event, "name", "") or getattr(event, "event_key", "") or event_key)
        runtime_name_cn = translate_event_name(event)
        en_candidates = _generic_en_page_candidates("event", event_key, runtime_name_en)
        cn_candidates = _generic_cn_page_candidates("event", event_key, runtime_name_cn, runtime_name_en)
        en_page = scraper.fetch_page_with_fallback(EN_SOURCE_ORDER, en_candidates)
        cn_page = scraper.fetch_page_with_fallback(CN_SOURCE_ORDER, cn_candidates)

        print(f"[event] {event_key}")
        print(f"  en: {en_page.get('resolved_title') or '-'} | error={en_page.get('error') or 'ok'}")
        print(f"  cn: {cn_page.get('resolved_title') or '-'} | error={cn_page.get('error') or 'ok'}")

        if en_page.get("error") is not None:
            failures.append(f"{event_key}: english wiki lookup failed")
        if cn_page.get("error") is not None:
            failures.append(f"{event_key}: chinese wiki lookup failed")

    if failures:
        print("\nFailures:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate targeted event wiki alias candidates.")
    parser.add_argument("--repo-root", default=".", help="Repository root used for local context.")
    args = parser.parse_args(argv)
    return validate_event_wiki_aliases(Path(args.repo_root).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
