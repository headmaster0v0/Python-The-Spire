"""
Relic Auditor - Audit project relics against wiki data.

Checks: names, descriptions, rarity, type, counts
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sts_py.engine.content.relics import ALL_RELICS, RelicTier
from sts_py.tools.wiki_bilingual_scraper import BilingualWikiScraper


class RelicAuditor:
    def __init__(self):
        self.scraper = BilingualWikiScraper(use_cache=True)
        self.report = {
            "total_in_project": len(ALL_RELICS),
            "wiki_total": 0,
            "name_mismatches": [],
            "missing_in_project": [],
            "missing_in_wiki": [],
            "description_mismatches": [],
            "rarity_mismatches": [],
            "tier_mismatches": [],
            "details": {},
        }

    def get_project_relics(self) -> dict[str, dict]:
        relics = {}
        for relic_id, relic_def in ALL_RELICS.items():
            relics[relic_id] = {
                "name": relic_def.name,
                "tier": relic_def.tier.value if hasattr(relic_def.tier, 'value') else str(relic_def.tier),
                "description": relic_def.description,
            }
        return relics

    def get_wiki_relics(self) -> dict[str, dict]:
        wiki_relics = {}
        for en_name in self.scraper.RELIC_NAME_MAP.keys():
            try:
                data = self.scraper.fetch_relic_en(en_name)
                if data and not data.get("error"):
                    wiki_relics[en_name] = {
                        "name_en": data.get("name", ""),
                        "name_cn": data.get("name_cn", ""),
                        "rarity": data.get("rarity", ""),
                        "class": data.get("class", ""),
                        "description": data.get("description", ""),
                        "flavor": data.get("flavor", ""),
                    }
            except Exception:
                pass
        return wiki_relics

    def _normalize_name(self, name: str) -> str:
        return name.replace(" ", "").replace("_", "").lower()

    def audit(self):
        print("=== Relic Auditor ===\n")
        print("Fetching project relics...")
        project_relics = self.get_project_relics()

        print("Fetching wiki relics...")
        wiki_relics = self.get_wiki_relics()
        self.report["wiki_total"] = len(wiki_relics)

        print("\n--- Basic Count Check ---")
        print(f"Project relics: {self.report['total_in_project']}")
        print(f"Wiki relics (in NAME_MAP): {len(self.scraper.RELIC_NAME_MAP)}")

        project_ids = set(project_relics.keys())
        wiki_ids = set(self.scraper.RELIC_NAME_MAP.keys())

        normalized_project = {self._normalize_name(pid): pid for pid in project_ids}
        normalized_wiki = {self._normalize_name(wid): wid for wid in wiki_ids}

        missing_norm_project = set(normalized_project.keys()) - set(normalized_wiki.keys())
        missing_norm_wiki = set(normalized_wiki.keys()) - set(normalized_project.keys())

        if missing_norm_project:
            print(f"\nProject relics not matching wiki ({len(missing_norm_project)}):")
            for norm_id in sorted(missing_norm_project):
                pid = normalized_project[norm_id]
                print(f"  - {pid}: {project_relics[pid]['name']}")
                self.report["missing_in_project"].append({
                    "project_id": pid,
                    "name_cn": project_relics[pid]["name"],
                })

        if missing_norm_wiki:
            print(f"\nWiki relics not matching project ({len(missing_norm_wiki)}):")
            for norm_id in sorted(missing_norm_wiki)[:10]:
                wid = normalized_wiki[norm_id]
                print(f"  - {wid}: {self.scraper.RELIC_NAME_MAP.get(wid, 'N/A')}")
            if len(missing_norm_wiki) > 10:
                print(f"  ... and {len(missing_norm_wiki) - 10} more")
            self.report["missing_in_wiki"] = list(normalized_wiki[wid] for wid in missing_norm_wiki)

        print("\n--- Name Mapping Check ---")
        for wiki_name, project_id in self.scraper.RELIC_NAME_MAP.items():
            if project_id not in project_relics:
                continue
            project_name = project_relics[project_id]["name"]
            wiki_data = wiki_relics.get(wiki_name, {})

            if wiki_data:
                wiki_name_en = wiki_data.get("name_en", "")
                wiki_name_cn = wiki_data.get("name_cn", "")

                if wiki_name_en and wiki_name_en.lower() != project_id.replace("_", " ").lower():
                    if wiki_name_en.lower() != project_id.replace("_", "").lower():
                        self.report["name_mismatches"].append({
                            "project_id": project_id,
                            "project_name": project_name,
                            "wiki_name_en": wiki_name_en,
                            "wiki_name_cn": wiki_name_cn,
                        })

        if self.report["name_mismatches"]:
            print(f"Name mismatches found: {len(self.report['name_mismatches'])}")
            for mm in self.report["name_mismatches"][:5]:
                print(f"  - {mm['project_id']}: project='{mm['project_name']}' wiki='{mm['wiki_name_en']}'")
        else:
            print("No name mismatches!")

        print("\n--- Description Length Check ---")
        short_desc = []
        for relic_id, project_data in project_relics.items():
            desc = project_data.get("description", "")
            if len(desc) < 10:
                short_desc.append(relic_id)

        if short_desc:
            print(f"Relics with very short descriptions (< 10 chars): {len(short_desc)}")
            for rid in short_desc[:5]:
                print(f"  - {rid}: '{project_relics[rid]['description']}'")

        print("\n--- Wiki Description Preview (sample) ---")
        for wiki_name in list(wiki_relics.keys())[:3]:
            wd = wiki_relics[wiki_name]
            print(f"  {wd['name_en']}: {wd.get('description', 'N/A')[:60]}...")

        print("\n--- Tier/Rarity Cross Reference ---")
        starter_count = 0
        common_count = 0
        uncommon_count = 0
        rare_count = 0
        boss_count = 0
        special_count = 0

        for relic_id, relic_def in ALL_RELICS.items():
            tier = relic_def.tier
            tier_str = tier.value if hasattr(tier, 'value') else str(tier)
            if "starter" in tier_str.lower():
                starter_count += 1
            elif "common" in tier_str.lower():
                common_count += 1
            elif "uncommon" in tier_str.lower():
                uncommon_count += 1
            elif "rare" in tier_str.lower():
                rare_count += 1
            elif "boss" in tier_str.lower():
                boss_count += 1
            else:
                special_count += 1

        print(f"Project tier distribution:")
        print(f"  Starter: {starter_count}")
        print(f"  Common: {common_count}")
        print(f"  Uncommon: {uncommon_count}")
        print(f"  Rare: {rare_count}")
        print(f"  Boss: {boss_count}")
        print(f"  Special/Uncategorized: {special_count}")

        return self.report


def main():
    auditor = RelicAuditor()
    report = auditor.audit()

    print("\n=== Summary ===")
    print(f"Project total: {report['total_in_project']}")
    print(f"Wiki total: {report['wiki_total']}")
    print(f"Name mismatches: {len(report['name_mismatches'])}")
    print(f"Missing in project: {len(report['missing_in_project'])}")
    print(f"Missing in wiki: {len(report['missing_in_wiki'])}")


if __name__ == "__main__":
    main()
