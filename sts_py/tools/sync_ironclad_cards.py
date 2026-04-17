"""
Sync Ironclad cards - Generate full report.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sts_py.engine.content.cards_min import IRONCLAD_ALL_DEFS
from sts_py.tools.wiki_bilingual_scraper import BilingualWikiScraper


IRONCLAD_CN_NAMES = {
    "Strike": "打击",
    "Defend": "防御",
    "Bash": "痛击",
    "Anger": "愤怒",
    "Armaments": "武装",
    "BodySlam": "躯体打击",
    "Clash": "冲突",
    "Cleave": "斩击",
    "Clothesline": "晾衣绳",
    "Flex": "全力挥击",
    "Havoc": "浩劫",
    "Headbutt": "头槌",
    "HeavyBlade": "重刃",
    "IronWave": "铁斩波",
    "PerfectedStrike": "完美打击",
    "PommelStrike": "剑柄打击",
    "ShrugItOff": "耸肩无视",
    "SwordBoomerang": "飞剑回旋镖",
    "Thunderclap": "闪电霹雳",
    "TrueGrit": "真硬",
    "TwinStrike": "双重打击",
    "Warcry": "战吼",
    "WildStrike": "狂野打击",
    "BattleTrance": "战斗专注",
    "BloodforBlood": "以血还血",
    "Bloodletting": "放血",
    "BurningPact": "燃烧契约",
    "Carnage": "残杀",
    "Combust": "燃烧",
    "DarkEmbrace": "黑暗之拥",
    "Disarm": "缴械",
    "Dropkick": "飞身踢",
    "DualWield": "双持",
    "Entrench": "筑墙",
    "Evolve": "进化",
    "FeelNoPain": "无痛",
    "FireBreathing": "火焰呼吸",
    "FlameBarrier": "火焰屏障",
    "GhostlyArmor": "幽灵铠甲",
    "Hemokinesis": "御血术",
    "InfernalBlade": "地狱刀刃",
    "Inflame": "烈火",
    "Intimidate": "恐吓",
    "Metallicize": "金属化",
    "PowerThrough": "硬撑",
    "Pummel": "连续拳",
    "Rage": "狂怒",
    "Rampage": "暴走",
    "RecklessCharge": "无谋冲锋",
    "Rupture": "撕裂",
    "SearingBlow": "灼热攻击",
    "SecondWind": "重振精神",
    "SeeingRed": "观察弱点",
    "Sentinel": "哨卫",
    "SeverSoul": "断魂斩",
    "Shockwave": "震荡波",
    "SpotWeakness": "弱点感知",
    "Barricade": "壁垒",
    "Berserk": "狂宴",
    "Bludgeon": "重锤",
    "Brutality": "暴行",
    "Corruption": "腐化",
    "DemonForm": "恶魔形态",
    "DoubleTap": "双发",
    "Exhume": "发掘",
    "Feed": "死亡收割",
    "FiendFire": "恶魔之焰",
    "Immolate": "燔祭",
    "Impervious": "巍然不动",
    "Juggernaut": "势不可挡",
    "LimitBreak": "突破极限",
    "Offering": "祭品",
    "Reaper": "死亡收割",
    "Uppercut": "上勾拳",
    "Whirlwind": "旋风斩",
}


def sync():
    scraper = BilingualWikiScraper(use_cache=True)

    found = []
    not_found = []
    errors = []

    for card_id in sorted(IRONCLAD_ALL_DEFS.keys()):
        card = IRONCLAD_ALL_DEFS[card_id]
        cn_name = IRONCLAD_CN_NAMES.get(card_id, "")

        wiki_data = scraper.fetch_card_cn(cn_name)
        if wiki_data and not wiki_data.get("error"):
            desc = wiki_data.get("description", "")
            if desc:
                found.append({
                    "id": card_id,
                    "cn": cn_name,
                    "en": wiki_data.get("name_en", ""),
                    "desc": desc,
                    "rarity": card.rarity.value,
                })
            else:
                errors.append({
                    "id": card_id,
                    "cn": cn_name,
                    "en": wiki_data.get("name_en", ""),
                    "reason": "empty description",
                })
        else:
            not_found.append({
                "id": card_id,
                "cn": cn_name,
            })

    print(f"=== Ironclad Cards Report ===\n")
    print(f"Total: {len(IRONCLAD_ALL_DEFS)}")
    print(f"With descriptions: {len(found)}")
    print(f"Empty descriptions: {len(errors)}")
    print(f"Not found: {len(not_found)}\n")

    print("=" * 80)
    print("CARDS WITH DESCRIPTIONS:")
    print("=" * 80)
    for f in found:
        print(f"\n[{f['rarity']}] {f['id']} ({f['cn']})")
        print(f"  EN: {f['en']}")
        print(f"  DESC: {f['desc'][:100]}...")

    if errors:
        print("\n" + "=" * 80)
        print("EMPTY DESCRIPTIONS:")
        print("=" * 80)
        for e in errors:
            print(f"  {e['id']}: {e['cn']} (EN: {e['en']})")

    if not_found:
        print("\n" + "=" * 80)
        print("NOT FOUND:")
        print("=" * 80)
        for nf in not_found:
            print(f"  {nf['id']}: {nf['cn']}")

    return found, not_found, errors


if __name__ == "__main__":
    sync()
