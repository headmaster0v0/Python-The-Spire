"""Wiki source adapter for Slay the Spire reference data.

This module is intentionally a reference-data fetcher only. It should not be
treated as gameplay truth. Runtime/CLI paths must not depend on live network
fetches; callers are expected to use this only for explicit snapshot refresh
workflows or ad-hoc audit scripts.
"""
from __future__ import annotations

import re
import urllib.parse
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import cloudscraper  # type: ignore
except ImportError:  # pragma: no cover - optional network dependency
    cloudscraper = None


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _humanize_identifier(identifier: str) -> str:
    if not identifier:
        return ""
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", identifier.replace("_", " "))
    return re.sub(r"\s+", " ", spaced).strip()


def _normalize_lookup_key(value: str) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        return ""
    candidate = re.sub(r"\+\d*$", "", candidate)
    candidate = candidate.rstrip("+")
    candidate = re.sub(r"[ _-]+", "", candidate)
    candidate = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", candidate)
    return candidate.lower()


class BilingualWikiScraper:
    EN_WIKIGG_API_URL = "https://slaythespire.wiki.gg/api.php"
    EN_WIKIGG_WIKI_URL = "https://slaythespire.wiki.gg/wiki"
    EN_API_URL = "https://slay-the-spire.fandom.com/api.php"
    EN_WIKI_URL = "https://slay-the-spire.fandom.com/wiki"
    CN_API_URL = "https://sts.huijiwiki.com/api.php"
    CN_WIKI_URL = "https://sts.huijiwiki.com"

    SOURCE_EN_WIKIGG = "en_wikigg"
    SOURCE_EN_FANDOM = "en_fandom"
    SOURCE_CN_HUIJI = "cn_huiji"

    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
        self._cache: dict[str, Any] = {}
        self._en_session = self._create_en_session()
        self._wiki_gg_session = self._create_en_session()
        self._cn_session = cloudscraper.create_scraper() if cloudscraper is not None else self._create_en_session()

        # Legacy script compatibility maps are derived from checked-in runtime
        # catalog/content instead of static scraped dictionaries.
        self.RELIC_NAME_MAP = self._build_relic_name_map()
        self.RELIC_NAME_MAP_CN_TO_EN = {v: k for k, v in self.RELIC_NAME_MAP.items()}
        self.CARD_NAME_MAP = self._build_card_name_map()
        self.CARD_NAME_MAP_CN_TO_EN = {v: k for k, v in self.CARD_NAME_MAP.items()}
        self.MONSTER_NAME_MAP = self._build_monster_name_map()
        self.MONSTER_NAME_MAP_CN_TO_EN = {v: k for k, v in self.MONSTER_NAME_MAP.items()}
        self.POTION_NAME_MAP = self._build_potion_name_map()
        self.POTION_NAME_MAP_CN_TO_EN = {v: k for k, v in self.POTION_NAME_MAP.items()}
        self.KEYWORD_NAME_MAP = self._build_keyword_name_map()
        self.KEYWORD_NAME_MAP_CN_TO_EN = {v: k for k, v in self.KEYWORD_NAME_MAP.items()}

    def _create_en_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.headers.update({"User-Agent": "STS-Wiki-Audit/1.0", "Accept": "application/json"})
        return session

    def _source_config(self, source: str) -> tuple[Any, str, str]:
        if source == self.SOURCE_EN_WIKIGG:
            return self._wiki_gg_session, self.EN_WIKIGG_API_URL, self.EN_WIKIGG_WIKI_URL
        if source == self.SOURCE_EN_FANDOM:
            return self._en_session, self.EN_API_URL, self.EN_WIKI_URL
        if source == self.SOURCE_CN_HUIJI:
            return self._cn_session, self.CN_API_URL, self.CN_WIKI_URL
        raise ValueError(f"unknown wiki source: {source}")

    def _build_relic_name_map(self) -> dict[str, str]:
        from sts_py.engine.content.relics import ALL_RELICS
        from sts_py.terminal.catalog import translate_relic

        return {_humanize_identifier(relic_id): translate_relic(relic_id) for relic_id in sorted(ALL_RELICS)}

    def _build_card_name_map(self) -> dict[str, str]:
        from sts_py.engine.content.cards_min import ALL_CARD_DEFS
        from sts_py.terminal.catalog import translate_card_name

        return {_humanize_identifier(card_id): translate_card_name(card_id) for card_id in sorted(ALL_CARD_DEFS)}

    def _build_monster_name_map(self) -> dict[str, str]:
        from sts_py.engine.core.rng import MutableRNG
        from sts_py.engine.run.run_engine import _monster_factory_registry
        from sts_py.terminal.catalog import translate_monster

        mapping: dict[str, str] = {}
        hp_rng = MutableRNG.from_seed(1, rng_type="monsterHpRng")
        for _, monster_cls in sorted(_monster_factory_registry().items()):
            if monster_cls.__name__ == "GenericMonsterProxy":
                continue
            monster = monster_cls.create(hp_rng, 0)
            monster_id = str(getattr(monster, "id", "") or "")
            if monster_id:
                mapping[str(getattr(monster, "name", _humanize_identifier(monster_id)))] = translate_monster(monster_id)
        return mapping

    def _build_potion_name_map(self) -> dict[str, str]:
        from sts_py.engine.content.potions import POTION_DEFINITIONS
        from sts_py.terminal.catalog import translate_potion

        return {_humanize_identifier(potion_id): translate_potion(potion_id) for potion_id in sorted(POTION_DEFINITIONS)}

    def _build_keyword_name_map(self) -> dict[str, str]:
        from sts_py.terminal.catalog import POWER_NAME_OVERRIDES

        return {_humanize_identifier(power_id): label for power_id, label in sorted(POWER_NAME_OVERRIDES.items())}

    def build_page_url(self, source: str, page: str) -> str:
        _, _, wiki_url = self._source_config(source)
        return f"{wiki_url}/{urllib.parse.quote(page.replace(' ', '_'))}"

    def clean_wiki_text(self, text: str) -> str:
        return self._clean_wiki_text(text)

    def _clean_wiki_text(self, text: str) -> str:
        text = re.sub(r"\[\[([^|\]]+?)\|([^|\]]+?)\]\]", r"\2", text)
        text = re.sub(r"\[\[([^|\]]+?)\]\]", r"\1", text)
        text = re.sub(r"\{\{[^{}]+\}\}", "", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _extract_field(self, wikitext: str, field_names: list[str]) -> str:
        for field_name in field_names:
            match = re.search(rf"^\|\s*{re.escape(field_name)}\s*=\s*(.+)$", wikitext, re.M)
            if match:
                return self._clean_wiki_text(match.group(1))
        return ""

    def fetch_wikitext_page(self, source: str, page: str) -> dict[str, Any]:
        cache_key = f"generic_page::{source}::{page}"
        if self.use_cache and cache_key in self._cache:
            return dict(self._cache[cache_key])

        session, api_url, _ = self._source_config(source)
        params = {"action": "parse", "page": page, "format": "json", "prop": "wikitext"}
        result: dict[str, Any] = {
            "source": source,
            "requested_title": page,
            "resolved_title": None,
            "wikitext": "",
            "url": self.build_page_url(source, page),
            "status_code": None,
            "error": None,
        }
        try:
            resp = session.get(api_url, params=params, timeout=20)
            result["status_code"] = resp.status_code
            if resp.status_code != 200:
                result["error"] = f"http_{resp.status_code}"
                result["raw_response"] = resp.text[:400]
                return result

            data = resp.json()
            if "parse" not in data:
                error_info = data.get("error", {})
                result["error"] = error_info.get("code") or "missing_parse"
                result["error_info"] = error_info.get("info", "")
                return result

            parse_block = data["parse"]
            result["resolved_title"] = parse_block.get("title", page)
            result["wikitext"] = parse_block.get("wikitext", {}).get("*", "")
            result["url"] = self.build_page_url(source, result["resolved_title"])
            if self.use_cache:
                self._cache[cache_key] = dict(result)
            return result
        except Exception as exc:
            result["error"] = str(exc)
            return result

    def _generic_summary_from_wikitext(self, wikitext: str) -> str:
        cleaned = self._clean_wiki_text(wikitext)
        if not cleaned:
            return ""
        summary = cleaned.split("==", 1)[0].strip()
        if len(summary) > 280:
            return summary[:277].rstrip() + "..."
        return summary

    def fetch_page_with_fallback(self, source_order: list[str], page_candidates: list[str]) -> dict[str, Any]:
        attempts: list[dict[str, Any]] = []
        for source in source_order:
            for page in page_candidates:
                candidate = str(page or "").strip()
                if not candidate:
                    continue
                page_result = self.fetch_wikitext_page(source, candidate)
                attempts.append(
                    {
                        "source": source,
                        "requested_title": candidate,
                        "resolved_title": page_result.get("resolved_title"),
                        "status_code": page_result.get("status_code"),
                        "error": page_result.get("error"),
                    }
                )
                if page_result.get("error") or not page_result.get("wikitext"):
                    continue
                return {
                    "source": source,
                    "requested_title": candidate,
                    "resolved_title": page_result.get("resolved_title") or candidate,
                    "url": page_result.get("url") or self.build_page_url(source, candidate),
                    "summary": self._generic_summary_from_wikitext(page_result.get("wikitext", "")),
                    "payload": page_result,
                    "attempts": attempts,
                    "error": None,
                }
        return {
            "source": None,
            "requested_title": page_candidates[0] if page_candidates else "",
            "resolved_title": None,
            "url": None,
            "summary": "",
            "payload": {},
            "attempts": attempts,
            "error": "all_sources_failed",
        }

    def _search_cn_wiki(self, query: str, limit: int = 5) -> list[str]:
        params = {"action": "query", "format": "json", "list": "search", "srsearch": query, "srlimit": limit}
        try:
            resp = self._cn_session.get(self.CN_API_URL, params=params, timeout=20)
            if resp.status_code != 200:
                return []
            data = resp.json()
            return [str(item.get("title", "")).strip() for item in data.get("query", {}).get("search", []) if str(item.get("title", "")).strip()]
        except Exception:
            return []

    def _build_en_result(self, result: dict[str, Any], *, name_en: str, name_cn: str = "") -> dict[str, Any]:
        if result.get("error"):
            return {"error": result["error"], "name_en": name_en, "name_cn": name_cn}
        payload = dict(result.get("payload") or {})
        wikitext = str(payload.get("wikitext", "") or "")
        resolved_title = str(result.get("resolved_title") or name_en)
        return {
            "name": resolved_title,
            "name_en": resolved_title,
            "name_cn": name_cn,
            "description": self._extract_field(wikitext, ["description", "card_text", "text", "effect"]) or result.get("summary", ""),
            "upgrade_description": self._extract_field(wikitext, ["upgraded", "upgrade_description"]),
            "rarity": self._extract_field(wikitext, ["rarity"]),
            "class": self._extract_field(wikitext, ["class", "character"]),
            "type": self._extract_field(wikitext, ["type"]),
            "flavor": self._extract_field(wikitext, ["flavor"]),
            "url": result.get("url"),
            "summary": result.get("summary", ""),
            "payload": payload,
            "source": result.get("source"),
            "attempts": list(result.get("attempts") or []),
            "lang": "en",
        }

    def _build_cn_result(self, result: dict[str, Any], *, name_cn: str, name_en: str = "") -> dict[str, Any]:
        if result.get("error"):
            return {"error": result["error"], "name": name_cn, "name_en": name_en}
        payload = dict(result.get("payload") or {})
        wikitext = str(payload.get("wikitext", "") or "")
        resolved_title = str(result.get("resolved_title") or name_cn)
        return {
            "name": resolved_title,
            "name_en": name_en,
            "description": self._extract_field(wikitext, ["description", "card_text", "text", "effect"]) or result.get("summary", ""),
            "url": result.get("url"),
            "summary": result.get("summary", ""),
            "payload": payload,
            "source": result.get("source"),
            "attempts": list(result.get("attempts") or []),
            "lang": "cn",
        }

    def fetch_relic_en(self, name: str) -> dict[str, Any]:
        result = self.fetch_page_with_fallback([self.SOURCE_EN_WIKIGG, self.SOURCE_EN_FANDOM], [name])
        cn_name = self.RELIC_NAME_MAP.get(name) or self.RELIC_NAME_MAP.get(str(result.get("resolved_title") or ""))
        return self._build_en_result(result, name_en=name, name_cn=cn_name or "")

    def fetch_relic_cn(self, cn_name: str) -> dict[str, Any]:
        page_candidates = [cn_name]
        if not _contains_cjk(cn_name):
            page_candidates.extend(self._search_cn_wiki(cn_name))
        result = self.fetch_page_with_fallback([self.SOURCE_CN_HUIJI], page_candidates)
        name_en = self.RELIC_NAME_MAP_CN_TO_EN.get(cn_name) or self.RELIC_NAME_MAP_CN_TO_EN.get(str(result.get("resolved_title") or ""))
        return self._build_cn_result(result, name_cn=cn_name, name_en=name_en or "")

    def fetch_card_en(self, name: str) -> dict[str, Any]:
        result = self.fetch_page_with_fallback([self.SOURCE_EN_WIKIGG, self.SOURCE_EN_FANDOM], [name])
        cn_name = self.CARD_NAME_MAP.get(name) or self.CARD_NAME_MAP.get(str(result.get("resolved_title") or ""))
        return self._build_en_result(result, name_en=name, name_cn=cn_name or "")

    def fetch_card_cn(self, cn_name: str) -> dict[str, Any]:
        page_candidates = [cn_name]
        if not _contains_cjk(cn_name):
            page_candidates.extend(self._search_cn_wiki(cn_name))
        result = self.fetch_page_with_fallback([self.SOURCE_CN_HUIJI], page_candidates)
        name_en = self.CARD_NAME_MAP_CN_TO_EN.get(cn_name) or self.CARD_NAME_MAP_CN_TO_EN.get(str(result.get("resolved_title") or ""))
        return self._build_cn_result(result, name_cn=cn_name, name_en=name_en or "")

    def fetch_keyword_cn(self, cn_name: str) -> dict[str, Any]:
        result = self.fetch_page_with_fallback([self.SOURCE_CN_HUIJI], [cn_name, *self._search_cn_wiki(cn_name)])
        name_en = self.KEYWORD_NAME_MAP_CN_TO_EN.get(cn_name) or self.KEYWORD_NAME_MAP_CN_TO_EN.get(str(result.get("resolved_title") or ""))
        return self._build_cn_result(result, name_cn=cn_name, name_en=name_en or "")

    def fetch_buff_cn(self, cn_name: str) -> dict[str, Any]:
        return self.fetch_keyword_cn(cn_name)

    def fetch_monster_cn(self, cn_name: str) -> dict[str, Any]:
        result = self.fetch_page_with_fallback([self.SOURCE_CN_HUIJI], [cn_name, *self._search_cn_wiki(cn_name)])
        name_en = self.MONSTER_NAME_MAP_CN_TO_EN.get(cn_name) or self.MONSTER_NAME_MAP_CN_TO_EN.get(str(result.get("resolved_title") or ""))
        return self._build_cn_result(result, name_cn=cn_name, name_en=name_en or "")

    def fetch_event_cn(self, cn_name: str) -> dict[str, Any]:
        result = self.fetch_page_with_fallback([self.SOURCE_CN_HUIJI], [cn_name, *self._search_cn_wiki(cn_name)])
        return self._build_cn_result(result, name_cn=cn_name, name_en="")

    def fetch_potion_cn(self, cn_name: str) -> dict[str, Any]:
        result = self.fetch_page_with_fallback([self.SOURCE_CN_HUIJI], [cn_name, *self._search_cn_wiki(cn_name)])
        name_en = self.POTION_NAME_MAP_CN_TO_EN.get(cn_name) or self.POTION_NAME_MAP_CN_TO_EN.get(str(result.get("resolved_title") or ""))
        return self._build_cn_result(result, name_cn=cn_name, name_en=name_en or "")

    def fetch_relic(self, name: str) -> dict[str, Any]:
        return self.fetch_relic_en(name)

    def fetch_card(self, name: str) -> dict[str, Any]:
        return self.fetch_card_en(name)

    def fetch_item(self, item_name: str, item_type: str) -> dict[str, Any]:
        if item_type == "card":
            return self.fetch_card_en(item_name)
        if item_type == "relic":
            return self.fetch_relic_en(item_name)
        raise ValueError(f"unsupported item_type: {item_type}")

    def get_all_relic_names_en(self) -> list[str]:
        return list(self.RELIC_NAME_MAP.keys())

    def get_all_relic_names_cn(self) -> list[str]:
        return list(self.RELIC_NAME_MAP.values())


def main() -> None:
    scraper = BilingualWikiScraper(use_cache=True)
    sample = scraper.fetch_page_with_fallback(
        [BilingualWikiScraper.SOURCE_EN_WIKIGG, BilingualWikiScraper.SOURCE_EN_FANDOM],
        ["Burning Blood"],
    )
    print(sample)


if __name__ == "__main__":
    main()
