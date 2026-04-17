from __future__ import annotations

from pathlib import Path

from sts_py.tools import wiki_audit
from sts_py.tools.wiki_bilingual_scraper import BilingualWikiScraper


def test_fetch_page_with_fallback_uses_fandom_when_wikigg_fails(monkeypatch) -> None:
    scraper = BilingualWikiScraper(use_cache=False)

    def _fake_fetch(source: str, page: str) -> dict[str, object]:
        if source == scraper.SOURCE_EN_WIKIGG:
            return {
                "source": source,
                "requested_title": page,
                "resolved_title": None,
                "wikitext": "",
                "url": scraper.build_page_url(source, page),
                "status_code": 403,
                "error": "http_403",
            }
        return {
            "source": source,
            "requested_title": page,
            "resolved_title": "Burning Blood",
            "wikitext": "Heal 6 HP after combat. == Details ==",
            "url": scraper.build_page_url(source, "Burning Blood"),
            "status_code": 200,
            "error": None,
        }

    monkeypatch.setattr(scraper, "fetch_wikitext_page", _fake_fetch)

    result = scraper.fetch_page_with_fallback(
        [scraper.SOURCE_EN_WIKIGG, scraper.SOURCE_EN_FANDOM],
        ["Burning Blood"],
    )

    assert result["source"] == scraper.SOURCE_EN_FANDOM
    assert result["resolved_title"] == "Burning Blood"
    assert result["summary"] == "Heal 6 HP after combat."
    assert result["attempts"][0]["source"] == scraper.SOURCE_EN_WIKIGG
    assert result["attempts"][1]["source"] == scraper.SOURCE_EN_FANDOM


def test_fetch_relic_cn_preserves_huiji_title_and_summary(monkeypatch) -> None:
    scraper = BilingualWikiScraper(use_cache=False)

    def _fake_fetch_page_with_fallback(source_order: list[str], page_candidates: list[str]) -> dict[str, object]:
        assert source_order == [scraper.SOURCE_CN_HUIJI]
        assert "燃烧之血" in page_candidates
        return {
            "source": scraper.SOURCE_CN_HUIJI,
            "requested_title": "燃烧之血",
            "resolved_title": "燃烧之血",
            "url": scraper.build_page_url(scraper.SOURCE_CN_HUIJI, "燃烧之血"),
            "summary": "每场战斗结束后，回复 6 点生命。",
            "payload": {"wikitext": ""},
            "attempts": [],
            "error": None,
        }

    monkeypatch.setattr(scraper, "fetch_page_with_fallback", _fake_fetch_page_with_fallback)

    result = scraper.fetch_relic_cn("燃烧之血")

    assert result["name"] == "燃烧之血"
    assert result["description"] == "每场战斗结束后，回复 6 点生命。"
    assert result["source"] == scraper.SOURCE_CN_HUIJI
    assert result["lang"] == "cn"


def test_build_cli_raw_snapshot_offline_skips_scraper_fetch(monkeypatch) -> None:
    scraper = BilingualWikiScraper(use_cache=False)

    def _unexpected_fetch(*args, **kwargs):
        raise AssertionError("offline snapshot should not fetch wiki pages")

    monkeypatch.setattr(scraper, "fetch_page_with_fallback", _unexpected_fetch)

    snapshot = wiki_audit.build_cli_raw_snapshot(Path.cwd(), enable_network=False, scraper=scraper)

    assert snapshot["network_enabled"] is False
    assert snapshot["records"]
