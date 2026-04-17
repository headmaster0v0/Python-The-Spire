"""
Relic Data Enhancer - Syncs relic data with wiki for enrichment.

Usage:
    from sts_py.tools.relic_enhancer import RelicEnhancer

    enhancer = RelicEnhancer()
    enhanced = enhancer.enrich_relic("Burning Blood")
    print(f"EN: {enhanced.name_en}, Flavor: {enhanced.flavor}")

    all_enhanced = enhancer.enrich_all_relics()
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sts_py.engine.content.relics import (
    ALL_RELICS,
    RelicDef,
)
from sts_py.tools.wiki_bilingual_scraper import BilingualWikiScraper


class RelicEnhancer:
    RELIC_ID_ALIASES = {
        "BurningBlood": "Burning Blood",
        "RingOfTheSnake": "Ring of the Snake",
        "RingOfTheSerpent": "Ring of the Serpent",
        "DualWield": "Dual Wield",
        "PaperCrane": "Paper Crane",
        "SwordBoomerang": "Sword Boomerang",
        "ThunderStrike": "Thunder Strike",
        "UpperCut": "Uppercut",
        "Impervious": "Impervious",
        "Inflame": "Inflame",
        "Bloodletting": "Bloodletting",
        "DemonForm": "Demon Form",
        "Dropkick": "Dropkick",
        "Pummel": "Pummel",
        "ShrugItOff": "Shrug It Off",
        "IronWave": "Iron Wave",
        "Carnage": "Carnage",
        "Cleave": "Cleave",
        "BodySlame": "Body Slam",
        "Sentinel": "Sentinel",
        "Bash": "Bash",
        "Clothesline": "Clothesline",
        "Combus": "Combust",
        "DarkEmbrace": "Dark Embrace",
        "Disciplin": "Discipline",
        "Rage": "Rage",
        "BloodforBlood": "Blood for Blood",
        "Bludgeon": "Bludgeon",
        "FIre": "Fire Breathing",
        "Corruption": "Corruption",
        "DemonCrone": "Demon Crone",
        "Expoder": "Exploder",
        "GremlinGuise": "Gremlin Guise",
        "Infernla": "Infernal",
        "NecromicIon": "Necronomicurse",
        "NlG": "NLG",
        "Permanent": "Permanent",
        "ProjGraph": "Projection",
        "ShockWave": "Shockwave",
        "SingingBowl": "Singing Bowl",
        "SpiritShield": "Spirit Shield",
        "StoneCal": "Stone Calendar",
        "Strange Spoon": "Strange Spoon",
        "TechCal": "Techniques",
        "TheSpec": "The Spec",
        "ThroughViolence": "Through Violence",
        "Tungsten": "Tungsten",
        "WalkingFolk": "Walking Folk",
        "FaceOfCleric": "Face of Cleric",
    }

    def __init__(self, use_cache: bool = True):
        self.scraper = BilingualWikiScraper(use_cache=use_cache)
        self._en_cache: dict[str, dict[str, Any]] = {}
        self._cn_cache: dict[str, dict[str, Any]] = {}

    def _get_wiki_name(self, relic_id: str) -> str:
        if relic_id in self.scraper.RELIC_NAME_MAP:
            return relic_id
        return self.RELIC_ID_ALIASES.get(relic_id, relic_id)

    def fetch_wiki_data_en(self, relic_id: str) -> dict[str, Any]:
        if relic_id in self._en_cache:
            return self._en_cache[relic_id]

        wiki_name = self._get_wiki_name(relic_id)
        data = self.scraper.fetch_relic_en(wiki_name)
        self._en_cache[relic_id] = data
        return data

    def fetch_wiki_data_cn(self, cn_name: str) -> dict[str, Any]:
        if cn_name in self._cn_cache:
            return self._cn_cache[cn_name]

        data = self.scraper.fetch_relic_cn(cn_name)
        self._cn_cache[cn_name] = data
        return data

    def enrich_relic(self, relic_id: str, lang: str = "both") -> RelicDef:
        relic = ALL_RELICS.get(relic_id)
        if not relic:
            raise ValueError(f"Relic not found: {relic_id}")

        if lang in ("en", "both"):
            wiki_en = self.fetch_wiki_data_en(relic_id)
            if wiki_en and not wiki_en.get("error"):
                self._apply_wiki_data(relic, wiki_en, "en")

        if lang in ("cn", "both"):
            wiki_cn = self.fetch_wiki_data_cn(relic.name)
            if wiki_cn and not wiki_cn.get("error"):
                self._apply_wiki_data(relic, wiki_cn, "cn")

        return relic

    def _apply_wiki_data(self, relic: RelicDef, wiki_data: dict[str, Any], lang: str) -> None:
        prefix = f"name_{lang}" if lang == "en" else ""
        if prefix:
            setattr(relic, prefix, wiki_data.get("name_en", ""))

        if not getattr(relic, "flavor", ""):
            flavor = wiki_data.get("flavor", "")
            if flavor:
                relic.flavor = flavor

        wiki_url = wiki_data.get("url", "")
        if wiki_url and not getattr(relic, "wiki_url", ""):
            relic.wiki_url = wiki_url

        related = wiki_data.get("related_links", [])
        if related and not getattr(relic, "related_links", []):
            relic.related_links = related

        if not getattr(relic, "rarity", ""):
            rarity = wiki_data.get("rarity", "")
            if rarity:
                relic.rarity = rarity

    def enrich_all_relics(self, lang: str = "both") -> dict[str, RelicDef]:
        for relic_id in ALL_RELICS:
            try:
                self.enrich_relic(relic_id, lang)
            except Exception as e:
                print(f"Error enriching {relic_id}: {e}")
        return ALL_RELICS

    def get_relic_stats(self, relic_id: str) -> dict[str, Any]:
        wiki_en = self.fetch_wiki_data_en(relic_id)
        wiki_cn = self.fetch_wiki_data_cn(ALL_RELICS[relic_id].name)

        return {
            "id": relic_id,
            "name_cn": ALL_RELICS[relic_id].name,
            "name_en": wiki_en.get("name", ""),
            "has_flavor": bool(wiki_en.get("flavor") or wiki_cn.get("description")),
            "has_related": bool(wiki_en.get("related_links") or wiki_cn.get("related_links")),
            "related_count": len(wiki_en.get("related_links", [])) + len(wiki_cn.get("related_links", [])),
        }

    def print_relic_summary(self) -> None:
        print(f"{'ID':<20} {'CN Name':<10} {'EN Name':<20} {'Flavor':<30} {'Links'}")
        print("-" * 100)
        for relic_id in sorted(ALL_RELICS.keys())[:20]:
            stats = self.get_relic_stats(relic_id)
            flavor = (stats.get("flavor") or "")[:28]
            print(f"{relic_id:<20} {ALL_RELICS[relic_id].name[:8]:<10} {stats['name_en'][:18]:<20} {flavor:<30} {stats['related_count']}")


def main():
    print("=== Relic Enhancer Demo ===\n")

    enhancer = RelicEnhancer(use_cache=True)

    print("--- Single Relic Enrichment ---")
    relic = enhancer.enrich_relic("BurningBlood")
    print(f"ID: {relic.id}")
    print(f"Name: {relic.name}")
    print(f"Name EN: {relic.name_en}")
    print(f"Flavor: {relic.flavor}")
    print(f"Wiki URL: {getattr(relic, 'wiki_url', 'N/A')}")
    print(f"Rarity: {relic.rarity}")
    print(f"Related Links: {len(getattr(relic, 'related_links', []))}")

    print("\n--- Relic Stats ---")
    enhancer.print_relic_summary()

    print("\n--- Wiki Data for Akabeko ---")
    wiki_data = enhancer.fetch_wiki_data_en("Akabeko")
    print(f"Name: {wiki_data.get('name')}")
    print(f"Description: {wiki_data.get('description')}")
    print(f"Rarity: {wiki_data.get('rarity')}")
    print(f"Flavor: {wiki_data.get('flavor')}")
    print(f"Related Links: {wiki_data.get('related_links', [])[:3]}")


if __name__ == "__main__":
    main()
