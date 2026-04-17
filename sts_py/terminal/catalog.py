from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from sts_py.engine.combat.card_effects import get_card_effects
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import ALL_CARD_DEFS
from sts_py.engine.content.potions import POTION_DEFINITIONS
from sts_py.engine.content.relics import get_relic_by_id
from sts_py.engine.run.run_engine import RoomType
from sts_py.terminal.translation_policy import get_translation_policy_entry

CARD_NAME_OVERRIDES: dict[str, str] = {
    "Strike": "打击",
    "Defend": "防御",
    "Strike_B": "打击",
    "Defend_B": "防御",
    "Bash": "痛击",
    "Anger": "愤怒",
    "Cleave": "顺劈斩",
    "PommelStrike": "剑柄打击",
    "ShrugItOff": "耸肩无视",
    "Thunderclap": "雷鸣",
    "IronWave": "铁斩波",
    "Armaments": "武装",
    "BattleTrance": "战斗专注",
    "Carnage": "残杀",
    "Disarm": "缴械",
    "FireBreathing": "火焰吐息",
    "Inflame": "燃烧",
    "Metallicize": "金属化",
    "Shockwave": "震荡波",
    "DemonForm": "恶魔形态",
    "Whirlwind": "旋风斩",
    "Uppercut": "上勾拳",
    "Neutralize": "中和",
    "Survivor": "幸存者",
    "Backflip": "后空翻",
    "Blur": "残影",
    "CloakAndDagger": "斗篷与匕首",
    "BladeDance": "刀刃之舞",
    "DaggerThrow": "匕首投掷",
    "DaggerSpray": "匕首风暴",
    "LegSweep": "扫腿",
    "PiercingWail": "尖啸",
    "Zap": "电击",
    "Dualcast": "双重施放",
    "BallLightning": "闪电球",
    "ColdSnap": "寒霜打击",
    "GoForTheEyes": "戳眼",
    "BeamCell": "光束核心",
    "Hologram": "全息影像",
    "Defragment": "碎片整理",
    "Buffer": "缓冲",
    "EchoForm": "回响形态",
    "Eruption": "爆发",
    "Vigilance": "警惕",
    "Crescendo": "渐强",
    "Tranquility": "宁静",
    "TalkToTheHand": "有话直说",
    "Wallop": "猛击",
    "LessonLearned": "吸取教训",
}

CARD_NAME_OVERRIDES.update(
    {
        "Clothesline": "晾衣绳",
        "TrueGrit": "坚毅",
        "TwinStrike": "双重打击",
        "Warcry": "战吼",
        "WildStrike": "狂野打击",
    }
)

PHASE247_CARD_NAME_OVERRIDES = {
    "Accuracy": "\u7cbe\u51c6",
    "Acrobatics": "\u6742\u6280",
    "AfterImage": "\u4f59\u50cf",
    "Aggregate": "\u6c47\u96c6",
    "Alchemize": "\u70bc\u91d1\u672f",
    "AllForOne": "\u4e07\u7269\u4e00\u5fc3",
    "AllOutAttack": "\u5168\u529b\u653b\u51fb",
    "Alpha": "\u963f\u5c14\u6cd5",
    "Amplify": "\u589e\u5e45",
    "AscendersBane": "\u8bc5\u5492\u724c",
    "AutoShields": "\u81ea\u52a8\u62a4\u76fe",
    "Backstab": "\u80cc\u523a",
    "Bane": "\u707e\u7978",
    "Barrage": "\u5f39\u5e55\u9f50\u5c04",
    "BattleHymn": "\u6218\u6b4c",
    "Beta": "\u8d1d\u5854",
    "BiasedCognition": "\u504f\u5dee\u8ba4\u77e5",
    "Blasphemy": "\u6e0e\u795e",
    "Blizzard": "\u66b4\u96ea",
    "BloodforBlood": "\u4ee5\u8840\u8fd8\u8840",
    "Bloodletting": "\u653e\u8840",
    "BootSequence": "\u542f\u52a8\u6d41\u7a0b",
    "BouncingFlask": "\u5f39\u8df3\u836f\u74f6",
    "BowlingBash": "\u78b0\u649e\u8fde\u51fb",
    "Brilliance": "\u5149\u8f89",
    "BulletTime": "\u5b50\u5f39\u65f6\u95f4",
    "Bullseye": "\u7784\u51c6\u9776\u5fc3",
    "Burn": "\u707c\u4f24",
    "Burn+": "\u707c\u4f24",
    "Burst": "\u7206\u53d1",
    "CalculatedGamble": "\u8ba1\u7b97\u4e0b\u6ce8",
    "Caltrops": "\u94c1\u84ba\u85dc",
    "Capacitor": "\u6269\u5bb9",
    "CarveReality": "\u6539\u9020\u73b0\u5b9e",
    "Catalyst": "\u50ac\u5316\u5242",
    "Chaos": "\u6df7\u6c8c",
    "Chill": "\u51b0\u5bd2",
    "Choke": "\u52d2\u8116",
    "Claw": "\u722a\u51fb",
    "Clumsy": "\u7b28\u62d9",
    "Collect": "\u6536\u96c6",
    "CompileDriver": "\u7f16\u8bd1\u51b2\u51fb",
    "Concentrate": "\u5168\u795e\u8d2f\u6ce8",
    "Conclude": "\u7ed3\u672b",
    "ConjureBlade": "\u805a\u80fd\u6210\u5203",
    "Consecrate": "\u4f9b\u5949",
    "ConserveBattery": "\u8282\u80fd",
    "Consume": "\u8017\u5c3d",
    "Coolheaded": "\u51b7\u9759\u5934\u8111",
    "CoreSurge": "\u6838\u5fc3\u7535\u6d8c",
    "CorpseExplosion": "\u5c38\u7206\u672f",
    "CreativeAI": "\u521b\u9020\u6027AI",
    "CrushJoints": "\u7c89\u788e\u5173\u8282",
    "CurseOfTheBell": "\u94c3\u94db\u7684\u8bc5\u5492",
    "CutThroughFate": "\u65a9\u7834\u547d\u8fd0",
    "Darkness": "\u6f06\u9ed1",
    "Dazed": "\u6655\u7729",
    "Decay": "\u8150\u673d",
    "DeceiveReality": "\u6b3a\u7792\u73b0\u5b9e",
    "Defend_P": "\u9632\u5fa1",
    "Deflect": "\u504f\u6298",
    "DeusExMachina": "\u673a\u68b0\u964d\u795e",
    "DevaForm": "\u5929\u4eba\u5f62\u6001",
    "Devotion": "\u8654\u4fe1",
    "DieDieDie": "\u6b7b\u5427\u6b7b\u5427\u6b7b\u5427",
    "Discipline": "\u6212\u5f8b",
    "Distraction": "\u58f0\u4e1c\u51fb\u897f",
    "DodgeAndRoll": "\u95ea\u8eb2\u7ffb\u6eda",
    "DoomAndGloom": "\u6101\u4e91\u60e8\u6de1",
    "Doppelganger": "\u53cc\u91cd\u5b58\u5728",
    "DoubleEnergy": "\u53cc\u500d\u80fd\u91cf",
    "Doubt": "\u7591\u8651",
    "Dropkick": "\u98de\u8eab\u8e22",
    "Electrodynamics": "\u7535\u52a8\u529b\u5b66",
    "EmptyBody": "\u5316\u4f53\u4e3a\u7a7a",
    "EmptyFist": "\u5316\u62f3\u4e3a\u7a7a",
    "EmptyMind": "\u5316\u667a\u4e3a\u7a7a",
    "EndlessAgony": "\u65e0\u5c3d\u82e6\u75db",
    "Envenom": "\u6d82\u6bd2",
    "Equilibrium": "\u5747\u8861",
    "EscapePlan": "\u9003\u8131\u8ba1\u5212",
    "Establishment": "\u786e\u7acb\u57fa\u7840",
    "Evaluate": "\u8bc4\u4f30",
    "Eviscerate": "\u5185\u810f\u5207\u9664",
    "Expertise": "\u72ec\u95e8\u6280\u672f",
    "Expunger": "\u706d\u9664\u4e4b\u5203",
    "FTL": "\u8d85\u5149\u901f",
    "Fasting": "\u658b\u6212",
    "FearNoEvil": "\u4e0d\u60e7\u5996\u90aa",
    "Feed": "\u72c2\u5bb4",
    "Finisher": "\u7ec8\u7ed3\u6280",
    "Fission": "\u88c2\u53d8",
    "FlameBarrier": "\u706b\u7130\u5c4f\u969c",
    "Flechettes": "\u98de\u9556",
    "FlurryOfBlows": "\u75be\u98ce\u8fde\u51fb",
    "FlyingKnee": "\u98de\u819d",
    "FlyingSleeves": "\u6d41\u4e91\u98de\u8896",
    "FollowUp": "\u8ffd\u51fb",
    "Footwork": "\u7075\u52a8\u6b65\u6cd5",
    "ForceField": "\u529b\u573a",
    "ForeignInfluence": "\u4ed6\u5c71\u4e4b\u77f3",
    "Foresight": "\u5148\u89c1\u4e4b\u660e",
    "Fusion": "\u805a\u53d8",
    "GeneticAlgorithm": "\u9057\u4f20\u7b97\u6cd5",
    "Glacier": "\u51b0\u5ddd",
    "GlassKnife": "\u73bb\u7483\u5200\u5203",
    "GrandFinale": "\u534e\u4e3d\u6536\u573a",
    "Halt": "\u505c\u987f",
    "Headbutt": "\u5934\u69cc",
    "Heatsinks": "\u6563\u70ed\u7247",
    "HeelHook": "\u8db3\u8ddf\u52fe",
    "HelloWorld": "\u4f60\u597d\uff0c\u4e16\u754c",
    "Hemokinesis": "\u5fa1\u8840\u672f",
    "Hyperbeam": "\u8d85\u5149\u675f",
    "Indignation": "\u4e49\u6124\u586b\u81ba",
    "InfiniteBlades": "\u65e0\u9650\u5200\u5203",
    "InnerPeace": "\u5185\u5fc3\u5e73\u9759",
    "Insight": "\u6d1e\u89c1",
    "Judgement": "\u5ba1\u5224",
    "Juggernaut": "\u52bf\u4e0d\u53ef\u5f53",
    "JustLucky": "\u4fa5\u5e78",
    "Leap": "\u98de\u8dc3",
    "LikeWater": "\u5982\u6c34",
    "Lockon": "\u9501\u5b9a",
    "Loop": "\u5faa\u73af",
    "MachineLearning": "\u673a\u5668\u5b66\u4e60",
    "Malaise": "\u840e\u9761",
    "MasterReality": "\u64cd\u63a7\u73b0\u5b9e",
    "MasterfulStab": "\u7cbe\u5999\u523a\u51fb",
    "Meditate": "\u51a5\u60f3",
    "Melter": "\u7194\u6bc1",
    "MentalFortress": "\u5fc3\u7075\u5821\u5792",
    "MeteorStrike": "\u6d41\u661f\u6253\u51fb",
    "Miracle": "\u5947\u8ff9",
    "MultiCast": "\u591a\u91cd\u91ca\u653e",
    "Necronomicurse": "\u6b7b\u7075\u8bc5\u5492",
    "Nightmare": "\u5669\u68a6",
    "Nirvana": "\u6d85\u69c3",
    "Normality": "\u51e1\u5eb8",
    "NoxiousFumes": "\u6bd2\u96fe",
    "Offering": "\u796d\u54c1",
    "Omega": "\u6b27\u7c73\u4f3d",
    "Omniscience": "\u5168\u77e5",
    "Outmaneuver": "\u62a2\u5360\u5148\u673a",
    "Overclock": "\u8d85\u9891",
    "Pain": "\u75bc\u75db",
    "Parasite": "\u5bc4\u751f",
    "Perseverance": "\u6bc5\u529b",
    "PhantasmalKiller": "\u5e7b\u5f71\u6740\u624b",
    "PowerThrough": "\u786c\u6491",
    "Pray": "\u7948\u7977",
    "Predator": "\u6389\u98df",
    "Prepared": "\u65e9\u6709\u51c6\u5907",
    "PressurePoints": "\u538b\u529b\u70b9",
    "Pride": "\u50b2\u6162",
    "Prostrate": "\u4e94\u4f53\u6295\u5730",
    "Protect": "\u62a4\u8eab",
    "Pummel": "\u8fde\u7eed\u62f3",
    "Rage": "\u72c2\u6012",
    "Ragnarok": "\u8bf8\u795e\u4e4b\u9ec4\u660f",
    "Rainbow": "\u5f69\u8679",
    "ReachHeaven": "\u7acb\u5730\u5347\u5929",
    "Reboot": "\u91cd\u542f",
    "Rebound": "\u5f39\u56de",
    "Recursion": "\u9012\u5f52",
    "Recycle": "\u56de\u6536",
    "Reflex": "\u672c\u80fd\u53cd\u5e94",
    "Regret": "\u6094\u6068",
    "ReinforcedBody": "\u786c\u5316\u673a\u4f53",
    "Reprogram": "\u91cd\u7f16\u7a0b",
    "RiddleWithHoles": "\u5343\u75ae\u767e\u5b54",
    "RipAndTear": "\u6495\u88c2",
    "Rupture": "\u7834\u88c2",
    "Rushdown": "\u731b\u864e\u4e0b\u5c71",
    "Sanctity": "\u5723\u6d01",
    "SandsOfTime": "\u65f6\u4e4b\u6c99",
    "SashWhip": "\u7f0e\u5e26\u62bd\u51fb",
    "Scrape": "\u522e\u524a",
    "Scrawl": "\u6f66\u8349\u6025\u5c31",
    "SecondWind": "\u4e8c\u6b21\u547c\u5438",
    "SeeingRed": "\u89c1\u7ea2",
    "Seek": "\u641c\u5bfb",
    "SelfRepair": "\u81ea\u6211\u4fee\u590d",
    "Setup": "\u5e03\u7f6e",
    "SeverSoul": "\u65ad\u9b42\u65a9",
    "Shame": "\u7f9e\u803b",
    "Shiv": "\u5c0f\u5200",
    "SignatureMove": "\u62db\u724c\u52a8\u4f5c",
    "SimmeringFury": "\u6cb8\u817e\u6012\u706b",
    "Skewer": "\u7a7f\u523a",
    "Skim": "\u7565\u8bfb",
    "Slimed": "\u9ecf\u6db2",
    "SneakyStrike": "\u9690\u79d8\u6253\u51fb",
    "SpiritShield": "\u7cbe\u795e\u62a4\u76fe",
    "Stack": "\u5806\u53e0",
    "StaticDischarge": "\u9759\u7535\u91ca\u653e",
    "SteamBarrier": "\u84b8\u6c7d\u5c4f\u969c",
    "Storm": "\u98ce\u66b4",
    "StormOfSteel": "\u94a2\u94c1\u98ce\u66b4",
    "Streamline": "\u7ebf\u6027\u52a0\u901f",
    "Strike_P": "\u6253\u51fb",
    "Study": "\u5b66\u4e60",
    "SuckerPunch": "\u7a81\u7136\u4e00\u62f3",
    "Sunder": "\u5288\u88c2",
    "SweepingBeam": "\u6a2a\u626b\u5149\u675f",
    "Swivel": "\u56de\u65cb",
    "SwordBoomerang": "\u98de\u5251\u56de\u65cb\u9556",
    "Tactician": "\u6218\u672f\u5bb6",
    "Tantrum": "\u53d1\u813e\u6c14",
    "Tempest": "\u96f7\u9706\u6253\u51fb",
    "Terror": "\u6050\u60e7",
    "ThirdEye": "\u7b2c\u4e09\u53ea\u773c",
    "ThousandCuts": "\u51cc\u8fdf",
    "ToolsOfTheTrade": "\u5fc5\u5907\u5de5\u5177",
    "Turbo": "\u6da1\u8f6e\u589e\u538b",
    "Unload": "\u4e7e\u5764\u4e00\u63b7",
    "Unraveling": "\u89e3\u7f20",
    "Vault": "\u817e\u8dc3",
    "Void": "\u865a\u7a7a",
    "WaveOfTheHand": "\u624b\u4e4b\u6ce2\u52a8",
    "Weave": "\u7f16\u7ec7",
    "WellLaidPlans": "\u8ba1\u5212\u59a5\u5f53",
    "WheelKick": "\u56de\u65cb\u8e22",
    "WhiteNoise": "\u767d\u566a\u58f0",
    "WindmillStrike": "\u65cb\u8f6c\u6253\u51fb",
    "Wish": "\u8bb8\u613f",
    "Worship": "\u5d07\u62dc",
    "WraithForm": "\u5e7d\u9b42\u5f62\u6001",
    "WreathOfFlame": "\u706b\u7130\u7eb9",
    "Writhe": "\u8815\u52a8",
}

CARD_NAME_OVERRIDES.update(PHASE247_CARD_NAME_OVERRIDES)

PHASE248_CARD_NAME_OVERRIDES = {
    "Apotheosis": "登峰造极",
    "Apparition": "幻影",
    "Bite": "咬噬",
    "Blind": "致盲",
    "DarkShackles": "黑暗镣铐",
    "DeepBreath": "深呼吸",
    "Finesse": "灵巧",
    "FlashOfSteel": "钢铁闪击",
    "GoodInstincts": "良好本能",
    "HandOfGreed": "贪婪之手",
    "Madness": "疯狂",
    "MasterOfStrategy": "运筹帷幄",
    "Panacea": "万灵药",
    "PanicButton": "紧急按钮",
    "Safety": "安全",
    "Smite": "惩击",
    "SwiftStrike": "迅捷打击",
    "ThroughViolence": "暴力突围",
    "Trip": "绊倒",
}

CARD_NAME_OVERRIDES.update(PHASE248_CARD_NAME_OVERRIDES)

CARD_DESCRIPTION_OVERRIDES: dict[str, str] = {
    "Strike": "造成 6 点伤害。",
    "Defend": "获得 5 点格挡。",
    "Strike_B": "造成 6 点伤害。",
    "Defend_B": "获得 5 点格挡。",
    "Bash": "造成 8 点伤害并施加 2 层易伤。",
    "Anger": "造成 6 点伤害，并将 1 张愤怒洗入弃牌堆。",
    "Cleave": "对所有敌人造成 8 点伤害。",
    "PommelStrike": "造成 9 点伤害并抽 1 张牌。",
    "ShrugItOff": "获得 8 点格挡并抽 1 张牌。",
    "Thunderclap": "对所有敌人造成 4 点伤害并施加 1 层易伤。",
    "Neutralize": "造成 3 点伤害并施加 1 层虚弱。",
    "Survivor": "获得 8 点格挡，然后弃 1 张牌。",
    "Zap": "生成 1 个闪电充能球。",
    "Dualcast": "立刻激发你最前方的充能球 2 次。",
    "Eruption": "造成 9 点伤害并进入愤怒。",
    "Vigilance": "获得 8 点格挡并进入平静。",
    "Shockwave": "对所有敌人施加 3 层虚弱和 3 层易伤。消耗。",
    "FireBreathing": "每当你抽到状态牌或诅咒牌时，对所有敌人造成伤害。",
    "DemonForm": "每回合开始时获得力量。",
    "Apotheosis": "将你手牌、抽牌堆、弃牌堆和消耗堆中的所有可升级牌升级。消耗。",
    "Apparition": "获得 1 层无实体。消耗。虚无。",
    "BattleHymn": "获得战歌。每回合开始时将 1 张惩击加入手牌。",
    "Bite": "造成 7 点伤害并回复 2 点生命。",
    "Blind": "施加 2 层虚弱。升级后改为对所有敌人生效。",
    "CarveReality": "造成 6 点伤害，并将 1 张惩击加入手牌。",
    "DarkShackles": "敌人本回合力量 -9。消耗。",
    "DeepBreath": "将弃牌堆洗回抽牌堆，然后抽 1 张牌。",
    "DeceiveReality": "获得 4 点格挡，并将 1 张安全加入手牌。",
    "Finesse": "获得 2 点格挡并抽 1 张牌。",
    "FlashOfSteel": "造成 3 点伤害并抽 1 张牌。",
    "GoodInstincts": "获得 6 点格挡。",
    "HandOfGreed": "造成 20 点伤害。若击杀目标，额外获得 20 金币。",
    "Madness": "将你手牌中 1 张随机牌的费用永久变为 0。消耗。",
    "MasterOfStrategy": "抽 3 张牌。消耗。",
    "Panacea": "获得 1 层人工制品。消耗。",
    "PanicButton": "获得 30 点格挡。本回合剩余时间与接下来 1 回合内不能获得格挡。消耗。",
    "ReachHeaven": "造成 10 点伤害，并将 1 张暴力突围洗入抽牌堆。",
    "Safety": "获得 12 点格挡。消耗。保留。",
    "Smite": "造成 12 点伤害。消耗。保留。",
    "SwiftStrike": "造成 7 点伤害。",
    "ThroughViolence": "造成 20 点伤害。消耗。保留。",
    "Trip": "施加 2 层易伤。",
}

MONSTER_NAME_OVERRIDES: dict[str, str] = {
    "Cultist": "邪教徒",
    "JawWorm": "颚虫",
    "FuzzyLouseNormal": "大头虫(攻击)",
    "FuzzyLouseDefensive": "大头虫(防御)",
    "SlaverRed": "红色奴仆",
    "SlaverBlue": "蓝色奴仆",
    "GremlinNob": "地精大块头",
    "Lagavulin": "乐加维林",
    "Sentry": "哨卫",
    "FungiBeast": "真菌兽",
    "Looter": "小偷",
    "Mugger": "强盗",
    "Hexaghost": "六火幽魂",
    "SlimeBoss": "史莱姆老大",
    "TheGuardian": "守护者",
    "Champ": "冠军",
    "Collector": "收藏家",
    "BronzeAutomaton": "青铜自动机",
    "BronzeOrb": "青铜球",
    "Chosen": "天选者",
    "Byrd": "伯德",
    "SphericGuardian": "球形守护者",
    "ShellParasite": "壳寄生虫",
    "SnakePlant": "蛇草",
    "Snecko": "蛇蜥怪",
    "Centurion": "百夫长",
    "Healer": "治疗师",
    "Darkling": "黑暗生物",
    "OrbWalker": "球行者",
    "SpireGrowth": "尖塔之花",
    "Transient": "短暂者",
    "Maw": "巨口",
    "WrithingMass": "蠕动之块",
    "GiantHead": "巨型头颅",
    "Nemesis": "复仇女神",
    "Reptomancer": "蜥蜴法师",
    "BookOfStabbing": "穿刺之书",
    "AwakenedOne": "觉醒者",
    "TimeEater": "吞时者",
    "Donu": "多努",
    "Deca": "德卡",
    "CorruptHeart": "腐化之心",
    "SpireShield": "尖塔护盾",
    "SpireSpear": "尖塔长矛",
}

MONSTER_NAME_OVERRIDES.update(
    {
        "AcidSlimeLarge": "大型酸液史莱姆",
        "AcidSlimeMedium": "中型酸液史莱姆",
        "AcidSlimeSmall": "小型酸液史莱姆",
        "GremlinFat": "胖地精",
        "GremlinSneaky": "狡诈地精",
        "LouseDefensive": "大头虫（防御）",
        "LouseRed": "红虱虫",
        "SpikeSlimeLarge": "大型尖刺史莱姆",
        "SpikeSlimeMedium": "中型尖刺史莱姆",
        "SpikeSlimeSmall": "小型尖刺史莱姆",
    }
)

PHASE247_MONSTER_NAME_OVERRIDES = {
    "Automaton": "\u9752\u94dc\u81ea\u52a8\u673a",
    "Dagger": "\u5315\u9996",
    "DonuAndDeca": "\u591a\u52aa\u4e0e\u5fb7\u5361",
    "Exploder": "\u7206\u70b8\u8005",
    "GremlinLeader": "\u5730\u7cbe\u9996\u9886",
    "GremlinTsundere": "\u62a4\u76fe\u5730\u7cbe",
    "GremlinWar": "\u75af\u72c2\u5730\u7cbe",
    "Repulsor": "\u6392\u65a5\u8005",
    "Serpent": "\u5c16\u5854\u4e4b\u82b1",
    "SlaverBoss": "\u5974\u96b6\u5934\u5b50",
    "Spiker": "\u5c16\u523a\u8005",
    "TorchHead": "\u706b\u628a\u5934",
}

MONSTER_NAME_OVERRIDES.update(PHASE247_MONSTER_NAME_OVERRIDES)

POWER_NAME_OVERRIDES: dict[str, str] = {
    "Vulnerable": "易伤",
    "Weak": "虚弱",
    "Frail": "脆弱",
    "Strength": "力量",
    "Dexterity": "敏捷",
    "Artifact": "人工制品",
    "Ritual": "仪式",
    "Metallicize": "金属化",
    "DemonForm": "恶魔形态",
    "Thorns": "荆棘",
    "CurlUp": "卷曲",
    "Intangible": "无实体",
    "Buffer": "缓冲",
    "PlatedArmor": "金属护甲",
    "Poison": "中毒",
    "Focus": "集中",
    "Regenerate": "再生",
    "BackAttack": "背刺",
}

PHASE247_POWER_NAME_OVERRIDES = {
    "Accuracy": "\u7cbe\u51c6",
    "AfterImage": "\u4f59\u50cf",
    "Amplify": "\u589e\u5e45",
    "Anger": "\u6124\u6012",
    "Angry": "\u66b4\u6012",
    "BeatOfDeath": "\u6b7b\u4ea1\u9f13\u70b9",
    "Bias": "\u504f\u5dee",
    "Blur": "\u6b8b\u5f71",
    "Brutality": "\u6b8b\u66b4",
    "Burst": "\u7206\u53d1",
    "Choked": "\u7a92\u606f",
    "Combust": "\u71c3\u70e7",
    "Confused": "\u6df7\u4e71",
    "CorpseExplosion": "\u5c38\u7206\u672f",
    "Corruption": "\u8150\u5316",
    "CreativeAI": "\u521b\u9020\u6027AI",
    "Curl Up": "\u8737\u8eab",
    "DarkEmbrace": "\u9ed1\u6697\u62e5\u62b1",
    "DevaPower": "\u5929\u4eba\u4e4b\u529b",
    "Devotion": "\u8654\u4fe1",
    "Doppelganger": "\u53cc\u91cd\u5b58\u5728",
    "DoubleTap": "\u53cc\u53d1",
    "Draw Card": "\u62bd\u724c",
    "Duplication": "\u590d\u5236",
    "EchoForm": "\u56de\u54cd\u5f62\u6001",
    "Electro": "\u611f\u7535",
    "EndTurnDeath": "\u56de\u5408\u7ed3\u675f\u6b7b\u4ea1",
    "Energized": "\u80fd\u91cf\u63d0\u5347",
    "EnergizedBlue": "\u5145\u80fd",
    "Enrage": "\u6fc0\u6012",
    "Entangled": "\u7f20\u8eab",
    "Envenom": "\u6d82\u6bd2",
    "Equilibrium": "\u5747\u8861",
    "Evolve": "\u8fdb\u5316",
    "FeelNoPain": "\u65e0\u60e7\u75bc\u75db",
    "FireBreathing": "\u706b\u7130\u5410\u606f",
    "FlameBarrier": "\u706b\u7130\u5c4f\u969c",
    "Flex": "\u6d3b\u52a8\u808c\u8089",
    "Foresight": "\u5148\u89c1\u4e4b\u660e",
    "Heatsinks": "\u6563\u70ed\u7247",
    "Hello": "\u4f60\u597d\uff0c\u4e16\u754c",
    "InfiniteBlades": "\u65e0\u9650\u5200\u5203",
    "Invincible": "\u575a\u4e0d\u53ef\u6467",
    "Juggernaut": "\u52bf\u4e0d\u53ef\u5f53",
    "LikeWater": "\u5982\u6c34",
    "Lockon": "\u9501\u5b9a",
    "Loop": "\u5faa\u73af",
    "Lose Dexterity": "\u5931\u53bb\u654f\u6377",
    "Lose Strength": "\u5931\u53bb\u529b\u91cf",
    "MachineLearning": "\u673a\u5668\u5b66\u4e60",
    "Magnetism": "\u78c1\u529b",
    "Mantra": "\u771f\u8a00",
    "MasterReality": "\u64cd\u63a7\u73b0\u5b9e",
    "Mayhem": "\u6df7\u6c8c",
    "Next Turn Block": "\u4e0b\u56de\u5408\u683c\u6321",
    "Nightmare": "\u5669\u68a6",
    "Nirvana": "\u6d85\u69c3",
    "No Draw": "\u4e0d\u80fd\u62bd\u724c",
    "NoxiousFumes": "\u6bd2\u96fe",
    "OmegaPower": "\u6b27\u7c73\u4f3d",
    "Painful Stabs": "\u75bc\u75db\u6233\u523a",
    "Panache": "\u8f89\u8000",
    "Phantasmal": "\u5e7b\u5f71\u6740\u624b",
    "Plated Armor": "\u91d1\u5c5e\u62a4\u7532",
    "Rage": "\u72c2\u6012",
    "Rebound": "\u5f39\u56de",
    "Regen": "\u518d\u751f\uff08\u73a9\u5bb6\uff09",
    "Repair": "\u81ea\u6211\u4fee\u590d",
    "Retain Cards": "\u4fdd\u7559\u624b\u724c",
    "Rupture": "\u7834\u88c2",
    "Rushdown": "\u731b\u864e\u4e0b\u5c71",
    "Sadistic": "\u65bd\u8650\u6210\u6027",
    "Sharp Hide": "\u950b\u5229\u5916\u7532",
    "Speed": "\u901f\u5ea6",
    "StaticDischarge": "\u9759\u7535\u91ca\u653e",
    "Storm": "\u98ce\u66b4",
    "Study": "\u5b66\u4e60",
    "Surrounded": "\u88ab\u5305\u56f4",
    "TheBomb": "\u70b8\u5f39",
    "ThousandCuts": "\u51cc\u8fdf",
    "Tools Of The Trade": "\u5fc5\u5907\u5de5\u5177",
    "WraithForm": "\u5e7d\u9b42\u5f62\u6001",
}

POWER_NAME_OVERRIDES.update(PHASE247_POWER_NAME_OVERRIDES)

POWER_NAME_OVERRIDES.update(
    {
        "BattleHymn": "战歌",
        "NoBlock": "不能获得格挡",
        "NoBlockPower": "不能获得格挡",
    }
)

POTION_NAME_OVERRIDES: dict[str, str] = {
    "EmptyPotionSlot": "空药水槽",
    "AttackPotion": "攻击药水",
    "BlockPotion": "格挡药水",
    "BloodPotion": "鲜血药水",
    "ColorlessPotion": "无色药水",
    "DexterityPotion": "敏捷药水",
    "EnergyPotion": "能量药水",
    "ExplosivePotion": "爆炸药水",
    "FearPotion": "恐惧药水",
    "FirePotion": "火焰药水",
    "FruitJuice": "果汁",
    "PowerPotion": "能力药水",
    "SkillPotion": "技能药水",
    "SmokeBomb": "烟雾弹",
    "StrengthPotion": "力量药水",
    "SwiftPotion": "迅捷药水",
    "WeakPotion": "虚弱药水",
    "AncientPotion": "古老药水",
    "BlessingOfTheForge": "锻造祝福",
    "CunningPotion": "狡诈药水",
    "DuplicationPotion": "复制药水",
    "EssenceOfSteel": "钢铁精华",
    "GamblersBrew": "赌徒酿剂",
    "LiquidBronze": "液态青铜",
    "LiquidMemories": "液态记忆",
    "StancePotion": "姿态药水",
    "Ambrosia": "仙馔密酒",
    "CultistPotion": "信徒药水",
    "EntropicBrew": "熵增酿剂",
    "EssenceOfDarkness": "黑暗精华",
    "FairyInABottle": "瓶中精灵",
    "GhostInAJar": "罐中幽灵",
    "HeartOfIron": "钢铁之心",
    "SneckoOil": "蛇油",
}

RELIC_NAME_OVERRIDES: dict[str, str] = {
    "TheCourier": "送货员",
    "MembershipCard": "会员卡",
    "SmilingMask": "微笑面具",
}

EVENT_NAME_OVERRIDES: dict[str, str] = {
    "Big Fish": "大鱼",
    "Cleric": "牧师",
    "The Cleric": "牧师",
    "Dead Adventurer": "已故冒险者",
    "Golden Idol": "黄金神像",
    "Golden Shrine": "黄金神龛",
    "Living Wall": "活墙壁",
    "Mushrooms": "蘑菇",
    "Scrap Ooze": "废料软泥",
    "Shining Light": "闪耀之光",
    "Face Trader": "换脸商",
    "The Library": "图书馆",
    "Masked Bandits": "蒙面强盗",
    "Mind Bloom": "心灵绽放",
    "World of Goop": "软泥世界",
    "Wing Statue": "有翼雕像",
}

ROOM_TYPE_NAMES: dict[RoomType, str] = {
    RoomType.MONSTER: "普通怪物房间",
    RoomType.ELITE: "精英怪物房间",
    RoomType.BOSS: "首领房间",
    RoomType.EVENT: "事件房间",
    RoomType.SHOP: "商店",
    RoomType.REST: "篝火",
    RoomType.TREASURE: "宝箱房间",
    RoomType.EMPTY: "空房间",
}

CARD_TYPE_NAMES = {
    "ATTACK": "攻击",
    "SKILL": "技能",
    "POWER": "能力",
    "STATUS": "状态",
    "CURSE": "诅咒",
}


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _contains_private_use(text: str) -> bool:
    return any("\ue000" <= ch <= "\uf8ff" for ch in text)


def _looks_sane_translation(text: str | None) -> bool:
    if not text:
        return False
    candidate = str(text).strip()
    if not candidate:
        return False
    if "\ufffd" in candidate or _contains_private_use(candidate):
        return False
    return _contains_cjk(candidate)


def _looks_presentable_text(text: str | None) -> bool:
    if not text:
        return False
    candidate = str(text).strip()
    if not candidate:
        return False
    return "\ufffd" not in candidate and not _contains_private_use(candidate)


def _humanize_identifier(identifier: str) -> str:
    if not identifier:
        return ""
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", identifier.replace("_", " "))
    return re.sub(r"\s+", " ", spaced).strip()


def _canonical_card(card_id: str) -> CardInstance:
    return CardInstance(card_id)


def _format_upgrade_suffix(card: CardInstance) -> str:
    if card.card_id == "SearingBlow" and card.times_upgraded > 0:
        return f"+{card.times_upgraded}"
    if card.upgraded and not card.card_id.endswith("+"):
        return "+"
    return ""


def _definition_card_name(card: CardInstance) -> str | None:
    definition = getattr(card, "_def", None)
    name_cn = getattr(definition, "name_cn", None)
    if _looks_sane_translation(name_cn):
        return str(name_cn)
    return None


def _policy_translation(entity_type: str, entity_id: str) -> str | None:
    entry = get_translation_policy_entry(entity_type, entity_id)
    if entry is None:
        return None
    if entry.alignment_status not in {"exact_match", "approved_alias"}:
        return None
    if not _looks_sane_translation(entry.runtime_name_cn):
        return None
    return entry.runtime_name_cn


def translate_card_name(card_id: str) -> str:
    card = _canonical_card(card_id)
    base_id = card.card_id
    name = _policy_translation("card", base_id) or CARD_NAME_OVERRIDES.get(base_id) or _definition_card_name(card)
    if name is None:
        name = _humanize_identifier(base_id)
    return f"{name}{_format_upgrade_suffix(card)}"


def translate_monster(monster_id: str) -> str:
    return _policy_translation("monster", monster_id) or MONSTER_NAME_OVERRIDES.get(monster_id, _humanize_identifier(monster_id))


def translate_potion(potion_id: str) -> str:
    policy_name = _policy_translation("potion", potion_id)
    if policy_name is not None:
        return policy_name
    override = POTION_NAME_OVERRIDES.get(potion_id)
    if override is not None:
        return override
    potion_def = POTION_DEFINITIONS.get(potion_id)
    if potion_def is not None:
        name = getattr(potion_def, "NAME", None)
        if _looks_sane_translation(name):
            return str(name)
        name_cn = getattr(potion_def, "NAME_CN", None)
        if _looks_sane_translation(name_cn):
            return str(name_cn)
    return _humanize_identifier(potion_id)


def get_potion_info(potion_id: str) -> tuple[str, str]:
    name = translate_potion(potion_id)
    potion_def = POTION_DEFINITIONS.get(potion_id)
    description = getattr(potion_def, "DESCRIPTION", None) if potion_def is not None else None
    if not _looks_presentable_text(description):
        description = getattr(potion_def, "description", None) if potion_def is not None else None
    return name, str(description).strip() if _looks_presentable_text(description) else ""


def translate_relic(relic_id: str) -> str:
    policy_name = _policy_translation("relic", relic_id)
    if policy_name is not None:
        return policy_name
    override = RELIC_NAME_OVERRIDES.get(relic_id)
    if override is not None:
        return override
    relic_def = get_relic_by_id(relic_id)
    if relic_def is not None:
        localized = getattr(relic_def, "name_cn", None)
        if _looks_sane_translation(localized):
            return str(localized)
        name = getattr(relic_def, "name", None)
        if _looks_sane_translation(name):
            return str(name)
    return _humanize_identifier(relic_id)


def get_relic_info(relic_id: str) -> tuple[str, str]:
    name = translate_relic(relic_id)
    relic_def = get_relic_by_id(relic_id)
    description = getattr(relic_def, "description", None) if relic_def is not None else None
    return name, str(description).strip() if _looks_presentable_text(description) else ""


def translate_power(power_id: str) -> str:
    return _policy_translation("power", power_id) or POWER_NAME_OVERRIDES.get(power_id, _humanize_identifier(power_id))


def translate_room_type(room_type: RoomType) -> str:
    return _policy_translation("room_type", room_type.name) or ROOM_TYPE_NAMES.get(room_type, room_type.value)


def translate_event_name(event: Any) -> str:
    if isinstance(event, str):
        event_id = event
        name_cn = None
    else:
        event_id = getattr(event, "id", str(event))
        name_cn = getattr(event, "name_cn", None)
    policy_name = _policy_translation("event", event_id)
    if policy_name is not None:
        return policy_name
    if event_id in EVENT_NAME_OVERRIDES:
        return EVENT_NAME_OVERRIDES[event_id]
    if _looks_sane_translation(name_cn):
        return str(name_cn)
    return _humanize_identifier(event_id)


def _generic_card_summary(card: CardInstance) -> str:
    parts: list[str] = [CARD_TYPE_NAMES.get(card.card_type.value, card.card_type.value)]
    if card.is_unplayable or card.cost_for_turn == -2:
        parts.append("无法打出")
    else:
        cost = "X" if card.cost_for_turn < 0 else str(card.cost_for_turn)
        parts.append(f"费用 {cost}")
    if card.base_damage > 0:
        parts.append(f"伤害 {card.base_damage}")
    if card.base_block > 0:
        parts.append(f"格挡 {card.base_block}")
    if card.base_magic_number > 0:
        parts.append(f"关键值 {card.base_magic_number}")
    if card.exhaust or card.exhaust_on_use_once:
        parts.append("消耗")
    if card.is_ethereal:
        parts.append("虚无")
    if card.retain or card.self_retain:
        parts.append("保留")
    if card.is_innate:
        parts.append("固有")
    return " | ".join(parts)


def get_card_info(card_id: str) -> tuple[str, str]:
    card = _canonical_card(card_id)
    name = translate_card_name(card_id)
    description = CARD_DESCRIPTION_OVERRIDES.get(card.card_id)
    if description is None:
        description = _generic_card_summary(card)
    return name, description


def get_power_str(power_id: str, amount: int) -> str:
    label = translate_power(power_id)
    return f"{label} {amount}" if amount else label


def _effect_signature(card_id: str, target_idx: int | None) -> list[tuple[str, Any, Any]]:
    card = _canonical_card(card_id)
    signature: list[tuple[str, Any, Any]] = []
    for effect in get_card_effects(card, target_idx):
        signature.append(
            (
                type(effect).__name__,
                getattr(effect, "target_idx", None),
                getattr(effect, "target_type", None),
            )
        )
    return signature


@lru_cache(maxsize=None)
def card_requires_target(card_id: str) -> bool:
    card = _canonical_card(card_id)
    definition = ALL_CARD_DEFS.get(card.card_id)
    explicit = getattr(definition, "target_required", None)
    if explicit is not None:
        return bool(explicit)
    target_signature = _effect_signature(card.runtime_card_id, 0)
    if not target_signature:
        return False
    return target_signature != _effect_signature(card.runtime_card_id, None)
