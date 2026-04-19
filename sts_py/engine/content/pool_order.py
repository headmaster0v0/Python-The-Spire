"""Java CardLibrary card pool iteration order.

These lists represent the order cards appear when calling
CardGroup.getRandomCard(boolean useRng) - the pool used by getRewardCards().

The pools are built by iterating CardLibrary.cards (HashMap) and adding each card
to the appropriate pool via addToTop(), which appends to the list. So the pool
order is the HashMap iteration order.

IMPORTANT: The actual pool order depends on:
1. CardLibrary.cards HashMap iteration order
2. UnlockTracker locked cards (locked cards are skipped)

The current Ironclad ordering is pinned against:
- the decompiled vanilla rarity surface (`Uppercut` / `Whirlwind` are uncommon)
- a deterministic synthetic seed regression
- the current primary Java recorder log front (`Pommel Strike / True Grit / Spot Weakness`, etc.)

Useful pinned indices on the current full Ironclad uncommon pool:
- idx=0 Spot Weakness
- idx=7 Intimidate
- idx=9 Flame Barrier
- idx=12 Metallicize
- idx=26 Fire Breathing
- idx=30 Sentinel
- idx=33 Entrench
"""
from __future__ import annotations

from sts_py.engine.content.cards_min import CardDef, CardRarity, DEFECT_ALL_DEFS, IRONCLAD_ALL_DEFS, SILENT_ALL_DEFS, WATCHER_ALL_DEFS


RED_COMMON_POOL_ORDER: list[str] = [
    "Anger", "Cleave", "Warcry", "Flex", "IronWave", "BodySlam",
    "TrueGrit", "ShrugItOff", "Clash", "Thunderclap", "PommelStrike",
    "TwinStrike", "Clothesline", "Armaments", "Havoc", "Headbutt",
    "WildStrike", "HeavyBlade", "PerfectedStrike", "SwordBoomerang",
]

RED_UNCOMMON_POOL_ORDER: list[str] = [
    "SpotWeakness", "Inflame", "PowerThrough", "DualWield", "InfernalBlade",
    "RecklessCharge", "Hemokinesis", "Intimidate", "BloodforBlood",
    "FlameBarrier", "BurningPact", "Shockwave", "Metallicize",
    "Rampage", "SeverSoul", "Combust", "DarkEmbrace", "SeeingRed",
    "Dropkick", "Disarm", "FeelNoPain", "Rage", "Evolve", "BattleTrance",
    "SearingBlow", "Rupture", "FireBreathing", "Bloodletting", "Carnage",
    "Pummel", "Sentinel", "SecondWind", "GhostlyArmor", "Entrench",
    "Uppercut", "Whirlwind",
]

RED_RARE_POOL_ORDER: list[str] = [
    "Immolate", "Offering", "Exhume", "Reaper", "Brutality", "Juggernaut",
    "Impervious", "Berserk", "FiendFire", "Barricade",
    "Corruption", "LimitBreak", "Feed", "Bludgeon", "DemonForm",
    "DoubleTap",
]

PURPLE_COMMON_POOL_ORDER: list[str] = [
    "BowlingBash", "Consecrate", "Crescendo", "CrushJoints", "CutThroughFate",
    "EmptyBody", "EmptyFist", "Evaluate", "FlurryOfBlows", "FlyingSleeves",
    "FollowUp", "Halt", "JustLucky", "PressurePoints", "Prostrate", "Protect",
    "SashWhip", "ThirdEye", "Tranquility",
]

PURPLE_UNCOMMON_POOL_ORDER: list[str] = [
    "BattleHymn", "CarveReality", "Collect", "Conclude", "DeceiveReality",
    "EmptyMind", "Fasting", "FearNoEvil", "ForeignInfluence", "Foresight",
    "Indignation", "InnerPeace", "LikeWater", "Meditate", "MentalFortress",
    "Nirvana", "Perseverance", "Pray", "ReachHeaven", "Rushdown", "Sanctity",
    "SandsOfTime", "SignatureMove", "SimmeringFury", "Study", "Swivel",
    "TalkToTheHand", "Tantrum", "Wallop", "WaveOfTheHand", "Weave",
    "WheelKick", "WindmillStrike", "Worship", "WreathOfFlame",
]

PURPLE_RARE_POOL_ORDER: list[str] = [
    "Alpha", "Blasphemy", "Brilliance", "ConjureBlade", "DeusExMachina",
    "DevaForm", "Devotion", "Discipline", "Establishment", "Judgement",
    "LessonLearned", "MasterReality", "Omniscience", "Ragnarok", "Scrawl",
    "SpiritShield", "Unraveling", "Vault", "Wish",
]

GREEN_COMMON_POOL_ORDER: list[str] = [
    "Slice",
    "QuickSlash",
    "SuckerPunch",
    "Backflip",
    "Bane",
    "PiercingWail",
    "Outmaneuver",
    "Deflect",
    "DodgeAndRoll",
    "DeadlyPoison",
    "PoisonedStab",
    "CloakAndDagger",
    "BladeDance",
    "Prepared",
    "Acrobatics",
    "DaggerSpray",
    "DaggerThrow",
    "FlyingKnee",
    "SneakyStrike",
]

GREEN_UNCOMMON_POOL_ORDER: list[str] = [
    "Backstab",
    "AllOutAttack",
    "Blur",
    "Caltrops",
    "Choke",
    "Dash",
    "Distraction",
    "EndlessAgony",
    "EscapePlan",
    "Flechettes",
    "Footwork",
    "HeelHook",
    "LegSweep",
    "MasterfulStab",
    "BouncingFlask",
    "NoxiousFumes",
    "Terror",
    "Catalyst",
    "CripplingCloud",
    "RiddleWithHoles",
    "Reflex",
    "Tactician",
    "Eviscerate",
    "Expertise",
    "Concentrate",
    "CalculatedGamble",
    "InfiniteBlades",
    "Accuracy",
    "Finisher",
    "Setup",
    "WellLaidPlans",
    "Predator",
    "Skewer",
]

GREEN_RARE_POOL_ORDER: list[str] = [
    "Alchemize",
    "Adrenaline",
    "BulletTime",
    "Burst",
    "DieDieDie",
    "CorpseExplosion",
    "Doppelganger",
    "Envenom",
    "GlassKnife",
    "GrandFinale",
    "Nightmare",
    "PhantasmalKiller",
    "StormOfSteel",
    "ToolsOfTheTrade",
    "ThousandCuts",
    "AfterImage",
    "Malaise",
    "Unload",
    "WraithForm",
]

BLUE_COMMON_POOL_ORDER: list[str] = [
    "BallLightning",
    "Claw",
    "ConserveBattery",
    "ColdSnap",
    "Coolheaded",
    "CompileDriver",
    "GoForTheEyes",
    "BeamCell",
    "Recursion",
    "Stack",
    "Turbo",
    "SweepingBeam",
    "Barrage",
    "Hologram",
    "Rebound",
    "Streamline",
    "Leap",
    "SteamBarrier",
]

BLUE_UNCOMMON_POOL_ORDER: list[str] = [
    "Defragment",
    "Lockon",
    "Bullseye",
    "Darkness",
    "Blizzard",
    "Chill",
    "DoomAndGloom",
    "Loop",
    "Consume",
    "Equilibrium",
    "Tempest",
    "DoubleEnergy",
    "ForceField",
    "Recycle",
    "Fusion",
    "Capacitor",
    "Storm",
    "StaticDischarge",
    "Heatsinks",
    "FTL",
    "Glacier",
    "GeneticAlgorithm",
    "HelloWorld",
    "Melter",
    "Reprogram",
    "RipAndTear",
    "ReinforcedBody",
    "Skim",
    "Aggregate",
    "AutoShields",
    "BootSequence",
    "Sunder",
    "SelfRepair",
    "WhiteNoise",
    "Chaos",
    "Overclock",
    "Scrape",
]

BLUE_RARE_POOL_ORDER: list[str] = [
    "CoreSurge",
    "Buffer",
    "Hyperbeam",
    "AllForOne",
    "Amplify",
    "EchoForm",
    "MachineLearning",
    "Fission",
    "MultiCast",
    "Reboot",
    "Seek",
    "CreativeAI",
    "Rainbow",
    "MeteorStrike",
    "Electrodynamics",
    "BiasedCognition",
]


def build_reward_pools(character_class: str = "IRONCLAD") -> dict[CardRarity, list[CardDef]]:
    """Build reward pools for the requested character class."""
    pools = {CardRarity.COMMON: [], CardRarity.UNCOMMON: [], CardRarity.RARE: []}

    character_key = character_class.upper()
    if character_key == "WATCHER":
        defs = WATCHER_ALL_DEFS
        common_order = PURPLE_COMMON_POOL_ORDER
        uncommon_order = PURPLE_UNCOMMON_POOL_ORDER
        rare_order = PURPLE_RARE_POOL_ORDER
    elif character_key == "SILENT":
        defs = SILENT_ALL_DEFS
        common_order = GREEN_COMMON_POOL_ORDER
        uncommon_order = GREEN_UNCOMMON_POOL_ORDER
        rare_order = GREEN_RARE_POOL_ORDER
    elif character_key == "DEFECT":
        defs = DEFECT_ALL_DEFS
        common_order = BLUE_COMMON_POOL_ORDER
        uncommon_order = BLUE_UNCOMMON_POOL_ORDER
        rare_order = BLUE_RARE_POOL_ORDER
    else:
        defs = IRONCLAD_ALL_DEFS
        common_order = RED_COMMON_POOL_ORDER
        uncommon_order = RED_UNCOMMON_POOL_ORDER
        rare_order = RED_RARE_POOL_ORDER

    for card_id in common_order:
        if card_id in defs:
            pools[CardRarity.COMMON].append(defs[card_id])

    for card_id in uncommon_order:
        if card_id in defs:
            pools[CardRarity.UNCOMMON].append(defs[card_id])

    for card_id in rare_order:
        if card_id in defs:
            pools[CardRarity.RARE].append(defs[card_id])

    return pools
