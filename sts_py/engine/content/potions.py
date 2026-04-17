from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto

class PotionRarity(Enum):
    COMMON = auto()
    UNCOMMON = auto()
    RARE = auto()

class PotionColor(Enum):
    FIRE = auto()
    TEAL = auto()
    PURPLE = auto()
    GREEN = auto()
    BLUE = auto()
    RED = auto()
    WHITE = auto()
    GOLD = auto()
    PINK = auto()
    ORANGE = auto()
    GRAY = auto()
    YELLOW = auto()

class PotionSize(Enum):
    CAN = auto()
    BOTTLE = auto()
    TONGUE = auto()
    HEART = auto()
    EYE = auto()
    SPHERE = auto()
    FLASK = auto()
    UI = auto()
    CARD = auto()

class CharacterClass(Enum):
    IRONCLAD = auto()
    SILENT = auto()
    DEFECT = auto()
    WATCHER = auto()
    UNIVERSAL = auto()

@dataclass
class AbstractPotion:
    potion_id: str
    name: str
    rarity: PotionRarity
    size: PotionSize
    color: PotionColor
    description: str
    character_class: CharacterClass = CharacterClass.UNIVERSAL
    is_Thrown: bool = False
    potency: int = 1
    sacred_bark_potency: int | None = None

    def make_copy(self) -> AbstractPotion:
        return AbstractPotion(
            potion_id=self.potion_id,
            name=self.name,
            rarity=self.rarity,
            size=self.size,
            color=self.color,
            description=self.description,
            character_class=self.character_class,
            is_Thrown=self.is_Thrown,
            potency=self.potency,
            sacred_bark_potency=self.sacred_bark_potency
        )


class PotionSlot:
    def __init__(self):
        self.potion: AbstractPotion | None = None

    def has_potion(self) -> bool:
        return self.potion is not None

    def get_potion(self) -> AbstractPotion | None:
        return self.potion

    def set_potion(self, potion: AbstractPotion) -> None:
        self.potion = potion

    def remove_potion(self) -> None:
        self.potion = None


SACRED_BARK_DOUBLES = [
    "Ambrosia",
    "BlessingOfTheForge",
    "EntropicBrew",
    "Elixir",
    "GamblersBrew",
    "SmokeBomb",
    "StancePotion",
]

POTION_DEFINITIONS: dict = {}


def register_potion(cls):
    POTION_DEFINITIONS[cls.POTION_ID] = cls
    return cls


@register_potion
class AttackPotionData:
    POTION_ID = "AttackPotion"
    NAME = "攻击药水"
    DESCRIPTION = "从 3 张随机攻击牌中选择 1 张加入你的手牌，这张牌在本回合耗能变为 0 。（神圣树皮则将该牌的2张复制加入手牌）"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.FIRE
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=AttackPotionData.POTION_ID,
            name=AttackPotionData.NAME,
            rarity=AttackPotionData.RARITY,
            size=PotionSize.CARD,
            color=AttackPotionData.COLOR,
            description=AttackPotionData.DESCRIPTION,
            character_class=AttackPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=1,
            sacred_bark_potency=2
        )


@register_potion
class BlessingOfTheForgeData:
    POTION_ID = "BlessingOfTheForge"
    NAME = "熔炉的祝福"
    DESCRIPTION = "在本场战斗中升级手牌中的所有牌。"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.GOLD
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=BlessingOfTheForgeData.POTION_ID,
            name=BlessingOfTheForgeData.NAME,
            rarity=BlessingOfTheForgeData.RARITY,
            size=PotionSize.CARD,
            color=BlessingOfTheForgeData.COLOR,
            description=BlessingOfTheForgeData.DESCRIPTION,
            character_class=BlessingOfTheForgeData.CHAR_CLASS,
            is_Thrown=False,
            potency=1,
            sacred_bark_potency=None
        )


@register_potion
class BlockPotionData:
    POTION_ID = "BlockPotion"
    NAME = "格挡药水"
    DESCRIPTION = "获得 12 点格挡。（神圣树皮则是24）"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.BLUE
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=BlockPotionData.POTION_ID,
            name=BlockPotionData.NAME,
            rarity=BlockPotionData.RARITY,
            size=PotionSize.CARD,
            color=BlockPotionData.COLOR,
            description=BlockPotionData.DESCRIPTION,
            character_class=BlockPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=12,
            sacred_bark_potency=24
        )


@register_potion
class BloodPotionData:
    POTION_ID = "BloodPotion"
    NAME = "鲜血药水"
    DESCRIPTION = "回复最大生命值的 20% 。（神圣树皮则是40%）"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.RED
    CHAR_CLASS = CharacterClass.IRONCLAD

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=BloodPotionData.POTION_ID,
            name=BloodPotionData.NAME,
            rarity=BloodPotionData.RARITY,
            size=PotionSize.CARD,
            color=BloodPotionData.COLOR,
            description=BloodPotionData.DESCRIPTION,
            character_class=BloodPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=20,
            sacred_bark_potency=40
        )


@register_potion
class BottledMiracleData:
    POTION_ID = "BottledMiracle"
    NAME = "瓶装奇迹"
    DESCRIPTION = "增加 2 张奇迹到你的手牌。（神圣树皮则增加4张）"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.TEAL
    CHAR_CLASS = CharacterClass.WATCHER

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=BottledMiracleData.POTION_ID,
            name=BottledMiracleData.NAME,
            rarity=BottledMiracleData.RARITY,
            size=PotionSize.CARD,
            color=BottledMiracleData.COLOR,
            description=BottledMiracleData.DESCRIPTION,
            character_class=BottledMiracleData.CHAR_CLASS,
            is_Thrown=False,
            potency=2,
            sacred_bark_potency=4
        )


@register_potion
class ColorlessPotionData:
    POTION_ID = "ColorlessPotion"
    NAME = "无色药水"
    DESCRIPTION = "从 3 张随机无色牌中选择 1 张加入你的手牌，这张牌在本回合耗能变为 0 。（神圣树皮则将该牌的2张复制加入手牌）"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.GRAY
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=ColorlessPotionData.POTION_ID,
            name=ColorlessPotionData.NAME,
            rarity=ColorlessPotionData.RARITY,
            size=PotionSize.CARD,
            color=ColorlessPotionData.COLOR,
            description=ColorlessPotionData.DESCRIPTION,
            character_class=ColorlessPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=1,
            sacred_bark_potency=2
        )


@register_potion
class DexterityPotionData:
    POTION_ID = "DexterityPotion"
    NAME = "敏捷药水"
    DESCRIPTION = "获得 2 点敏捷。（神圣树皮则是4）"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.GREEN
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=DexterityPotionData.POTION_ID,
            name=DexterityPotionData.NAME,
            rarity=DexterityPotionData.RARITY,
            size=PotionSize.CARD,
            color=DexterityPotionData.COLOR,
            description=DexterityPotionData.DESCRIPTION,
            character_class=DexterityPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=2,
            sacred_bark_potency=4
        )


@register_potion
class DistilledChaosData:
    POTION_ID = "DistilledChaos"
    NAME = "精炼混沌"
    DESCRIPTION = "打出抽牌堆顶的 3 张牌。（神圣树皮则是6张）"
    RARITY = PotionRarity.UNCOMMON
    COLOR = PotionColor.PURPLE
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=DistilledChaosData.POTION_ID,
            name=DistilledChaosData.NAME,
            rarity=DistilledChaosData.RARITY,
            size=PotionSize.CARD,
            color=DistilledChaosData.COLOR,
            description=DistilledChaosData.DESCRIPTION,
            character_class=DistilledChaosData.CHAR_CLASS,
            is_Thrown=False,
            potency=3,
            sacred_bark_potency=6
        )


@register_potion
class ElixirData:
    POTION_ID = "Elixir"
    NAME = "万灵药水"
    DESCRIPTION = "消耗你手牌中的任意张牌。"
    RARITY = PotionRarity.UNCOMMON
    COLOR = PotionColor.GREEN
    CHAR_CLASS = CharacterClass.IRONCLAD

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=ElixirData.POTION_ID,
            name=ElixirData.NAME,
            rarity=ElixirData.RARITY,
            size=PotionSize.CARD,
            color=ElixirData.COLOR,
            description=ElixirData.DESCRIPTION,
            character_class=ElixirData.CHAR_CLASS,
            is_Thrown=False,
            potency=0,
            sacred_bark_potency=None
        )


@register_potion
class EnergyPotionData:
    POTION_ID = "EnergyPotion"
    NAME = "能量药水"
    DESCRIPTION = "获得 2 点能量。（神圣树皮则是4）"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.YELLOW
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=EnergyPotionData.POTION_ID,
            name=EnergyPotionData.NAME,
            rarity=EnergyPotionData.RARITY,
            size=PotionSize.CARD,
            color=EnergyPotionData.COLOR,
            description=EnergyPotionData.DESCRIPTION,
            character_class=EnergyPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=2,
            sacred_bark_potency=4
        )


@register_potion
class ExplosivePotionData:
    POTION_ID = "ExplosivePotion"
    NAME = "爆炸药水"
    DESCRIPTION = "对所有敌人造成 10 点伤害。（神圣树皮则是20）"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.ORANGE
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=ExplosivePotionData.POTION_ID,
            name=ExplosivePotionData.NAME,
            rarity=ExplosivePotionData.RARITY,
            size=PotionSize.CARD,
            color=ExplosivePotionData.COLOR,
            description=ExplosivePotionData.DESCRIPTION,
            character_class=ExplosivePotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=10,
            sacred_bark_potency=20
        )


@register_potion
class FearPotionData:
    POTION_ID = "FearPotion"
    NAME = "恐惧药水"
    DESCRIPTION = "给予 3 层易伤。（神圣树皮则是6）"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.PURPLE
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=FearPotionData.POTION_ID,
            name=FearPotionData.NAME,
            rarity=FearPotionData.RARITY,
            size=PotionSize.CARD,
            color=FearPotionData.COLOR,
            description=FearPotionData.DESCRIPTION,
            character_class=FearPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=3,
            sacred_bark_potency=6
        )


@register_potion
class FirePotionData:
    POTION_ID = "FirePotion"
    NAME = "火焰药水"
    DESCRIPTION = "对目标敌人造成 20 点伤害。（神圣树皮则是40）"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.ORANGE
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=FirePotionData.POTION_ID,
            name=FirePotionData.NAME,
            rarity=FirePotionData.RARITY,
            size=PotionSize.CARD,
            color=FirePotionData.COLOR,
            description=FirePotionData.DESCRIPTION,
            character_class=FirePotionData.CHAR_CLASS,
            is_Thrown=True,
            potency=20,
            sacred_bark_potency=40
        )


@register_potion
class FlexPotionData:
    POTION_ID = "FlexPotion"
    NAME = "类固醇药水"
    DESCRIPTION = "获得 5 点力量，在回合结束时失去这些力量。（神圣树皮则是10）"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.ORANGE
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=FlexPotionData.POTION_ID,
            name=FlexPotionData.NAME,
            rarity=FlexPotionData.RARITY,
            size=PotionSize.CARD,
            color=FlexPotionData.COLOR,
            description=FlexPotionData.DESCRIPTION,
            character_class=FlexPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=5,
            sacred_bark_potency=10
        )


@register_potion
class FocusPotionData:
    POTION_ID = "FocusPotion"
    NAME = "集中药水"
    DESCRIPTION = "获得 2 点专注。（神圣树皮则是4）"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.BLUE
    CHAR_CLASS = CharacterClass.DEFECT

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=FocusPotionData.POTION_ID,
            name=FocusPotionData.NAME,
            rarity=FocusPotionData.RARITY,
            size=PotionSize.CARD,
            color=FocusPotionData.COLOR,
            description=FocusPotionData.DESCRIPTION,
            character_class=FocusPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=2,
            sacred_bark_potency=4
        )


@register_potion
class FruitJuiceData:
    POTION_ID = "FruitJuice"
    NAME = "果汁"
    DESCRIPTION = "获得 5 点最大生命值。（神圣树皮则是10）"
    RARITY = PotionRarity.RARE
    COLOR = PotionColor.PINK
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=FruitJuiceData.POTION_ID,
            name=FruitJuiceData.NAME,
            rarity=FruitJuiceData.RARITY,
            size=PotionSize.CARD,
            color=FruitJuiceData.COLOR,
            description=FruitJuiceData.DESCRIPTION,
            character_class=FruitJuiceData.CHAR_CLASS,
            is_Thrown=False,
            potency=5,
            sacred_bark_potency=10
        )


@register_potion
class PoisonPotionData:
    POTION_ID = "PoisonPotion"
    NAME = "毒药水"
    DESCRIPTION = "给予目标敌人 6 层中毒。（神圣树皮则是12）"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.GREEN
    CHAR_CLASS = CharacterClass.SILENT

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=PoisonPotionData.POTION_ID,
            name=PoisonPotionData.NAME,
            rarity=PoisonPotionData.RARITY,
            size=PotionSize.CARD,
            color=PoisonPotionData.COLOR,
            description=PoisonPotionData.DESCRIPTION,
            character_class=PoisonPotionData.CHAR_CLASS,
            is_Thrown=True,
            potency=6,
            sacred_bark_potency=12
        )


@register_potion
class PowerPotionData:
    POTION_ID = "PowerPotion"
    NAME = "能力药水"
    DESCRIPTION = "从 3 张随机能力牌中选择 1 张加入你的手牌，这张牌在本回合耗能变为 0 。（神圣树皮则将该牌的2张复制加入手牌）"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.PURPLE
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=PowerPotionData.POTION_ID,
            name=PowerPotionData.NAME,
            rarity=PowerPotionData.RARITY,
            size=PotionSize.CARD,
            color=PowerPotionData.COLOR,
            description=PowerPotionData.DESCRIPTION,
            character_class=PowerPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=1,
            sacred_bark_potency=2
        )


@register_potion
class RegenPotionData:
    POTION_ID = "RegenPotion"
    NAME = "再生药水"
    DESCRIPTION = "获得 5 层再生。（神圣树皮则是10）"
    RARITY = PotionRarity.UNCOMMON
    COLOR = PotionColor.GREEN
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=RegenPotionData.POTION_ID,
            name=RegenPotionData.NAME,
            rarity=RegenPotionData.RARITY,
            size=PotionSize.CARD,
            color=RegenPotionData.COLOR,
            description=RegenPotionData.DESCRIPTION,
            character_class=RegenPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=5,
            sacred_bark_potency=10
        )


@register_potion
class SkillPotionData:
    POTION_ID = "SkillPotion"
    NAME = "技能药水"
    DESCRIPTION = "从 3 张随机技能牌中选择 1 张加入你的手牌，这张牌在本回合耗能变为 0 。（神圣树皮则将该牌的2张复制加入手牌）"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.BLUE
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=SkillPotionData.POTION_ID,
            name=SkillPotionData.NAME,
            rarity=SkillPotionData.RARITY,
            size=PotionSize.CARD,
            color=SkillPotionData.COLOR,
            description=SkillPotionData.DESCRIPTION,
            character_class=SkillPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=1,
            sacred_bark_potency=2
        )


@register_potion
class SmokeBombData:
    POTION_ID = "SmokeBomb"
    NAME = "烟雾弹"
    DESCRIPTION = "从非首领战斗中逃跑。不获得奖励。"
    RARITY = PotionRarity.RARE
    COLOR = PotionColor.GRAY
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=SmokeBombData.POTION_ID,
            name=SmokeBombData.NAME,
            rarity=SmokeBombData.RARITY,
            size=PotionSize.CARD,
            color=SmokeBombData.COLOR,
            description=SmokeBombData.DESCRIPTION,
            character_class=SmokeBombData.CHAR_CLASS,
            is_Thrown=False,
            potency=0,
            sacred_bark_potency=None
        )


@register_potion
class SpeedPotionData:
    POTION_ID = "SpeedPotion"
    NAME = "速度药水"
    DESCRIPTION = "获得 5 点敏捷，在回合结束时失去这些敏捷。（神圣树皮则是10）"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.YELLOW
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=SpeedPotionData.POTION_ID,
            name=SpeedPotionData.NAME,
            rarity=SpeedPotionData.RARITY,
            size=PotionSize.CARD,
            color=SpeedPotionData.COLOR,
            description=SpeedPotionData.DESCRIPTION,
            character_class=SpeedPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=5,
            sacred_bark_potency=10
        )


@register_potion
class StrengthPotionData:
    POTION_ID = "StrengthPotion"
    NAME = "力量药水"
    DESCRIPTION = "获得 2 点力量。（神圣树皮则是4）"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.RED
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=StrengthPotionData.POTION_ID,
            name=StrengthPotionData.NAME,
            rarity=StrengthPotionData.RARITY,
            size=PotionSize.CARD,
            color=StrengthPotionData.COLOR,
            description=StrengthPotionData.DESCRIPTION,
            character_class=StrengthPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=2,
            sacred_bark_potency=4
        )


@register_potion
class SwiftPotionData:
    POTION_ID = "SwiftPotion"
    NAME = "迅捷药水"
    DESCRIPTION = "抽 3 张牌。（神圣树皮则是6）"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.WHITE
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=SwiftPotionData.POTION_ID,
            name=SwiftPotionData.NAME,
            rarity=SwiftPotionData.RARITY,
            size=PotionSize.CARD,
            color=SwiftPotionData.COLOR,
            description=SwiftPotionData.DESCRIPTION,
            character_class=SwiftPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=3,
            sacred_bark_potency=6
        )


@register_potion
class WeakPotionData:
    POTION_ID = "WeakPotion"
    NAME = "虚弱药水"
    DESCRIPTION = "给予 3 层虚弱。（神圣树皮则是6）"
    RARITY = PotionRarity.COMMON
    COLOR = PotionColor.BLUE
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=WeakPotionData.POTION_ID,
            name=WeakPotionData.NAME,
            rarity=WeakPotionData.RARITY,
            size=PotionSize.CARD,
            color=WeakPotionData.COLOR,
            description=WeakPotionData.DESCRIPTION,
            character_class=WeakPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=3,
            sacred_bark_potency=6
        )


@register_potion
class AncientPotionData:
    POTION_ID = "AncientPotion"
    NAME = "远古药水"
    DESCRIPTION = "获得 1 层人工制品。（神圣树皮则是2）"
    RARITY = PotionRarity.UNCOMMON
    COLOR = PotionColor.TEAL
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=AncientPotionData.POTION_ID,
            name=AncientPotionData.NAME,
            rarity=AncientPotionData.RARITY,
            size=PotionSize.CARD,
            color=AncientPotionData.COLOR,
            description=AncientPotionData.DESCRIPTION,
            character_class=AncientPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=1,
            sacred_bark_potency=2
        )


@register_potion
class CultistPotionData:
    POTION_ID = "CultistPotion"
    NAME = "教徒药水"
    DESCRIPTION = "获得 1 层仪式。（神圣树皮则是2）"
    RARITY = PotionRarity.RARE
    COLOR = PotionColor.PURPLE
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=CultistPotionData.POTION_ID,
            name=CultistPotionData.NAME,
            rarity=CultistPotionData.RARITY,
            size=PotionSize.CARD,
            color=CultistPotionData.COLOR,
            description=CultistPotionData.DESCRIPTION,
            character_class=CultistPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=1,
            sacred_bark_potency=2
        )


@register_potion
class CunningPotionData:
    POTION_ID = "CunningPotion"
    NAME = "狡诈药水"
    DESCRIPTION = "将 3 张升级的飞刀加入你的手牌。（神圣树皮则是6）"
    RARITY = PotionRarity.UNCOMMON
    COLOR = PotionColor.GREEN
    CHAR_CLASS = CharacterClass.SILENT

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=CunningPotionData.POTION_ID,
            name=CunningPotionData.NAME,
            rarity=CunningPotionData.RARITY,
            size=PotionSize.CARD,
            color=CunningPotionData.COLOR,
            description=CunningPotionData.DESCRIPTION,
            character_class=CunningPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=3,
            sacred_bark_potency=6
        )


@register_potion
class DuplicationPotionData:
    POTION_ID = "DuplicationPotion"
    NAME = "复制药水"
    DESCRIPTION = "本回合，你打出的下一张牌会被打出两次。（神圣树皮则是下2张）"
    RARITY = PotionRarity.UNCOMMON
    COLOR = PotionColor.PINK
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=DuplicationPotionData.POTION_ID,
            name=DuplicationPotionData.NAME,
            rarity=DuplicationPotionData.RARITY,
            size=PotionSize.CARD,
            color=DuplicationPotionData.COLOR,
            description=DuplicationPotionData.DESCRIPTION,
            character_class=DuplicationPotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=1,
            sacred_bark_potency=2
        )


@register_potion
class EssenceOfSteelData:
    POTION_ID = "EssenceOfSteel"
    NAME = "钢铁精华"
    DESCRIPTION = "获得 4 层多层护甲。（神圣树皮则是8）"
    RARITY = PotionRarity.UNCOMMON
    COLOR = PotionColor.BLUE
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=EssenceOfSteelData.POTION_ID,
            name=EssenceOfSteelData.NAME,
            rarity=EssenceOfSteelData.RARITY,
            size=PotionSize.CARD,
            color=EssenceOfSteelData.COLOR,
            description=EssenceOfSteelData.DESCRIPTION,
            character_class=EssenceOfSteelData.CHAR_CLASS,
            is_Thrown=False,
            potency=4,
            sacred_bark_potency=8
        )


@register_potion
class GhostInAJarData:
    POTION_ID = "GhostInAJar"
    NAME = "瓶中幽灵"
    DESCRIPTION = "获得 1 层无实体。（神圣树皮则是2层）"
    RARITY = PotionRarity.RARE
    COLOR = PotionColor.WHITE
    CHAR_CLASS = CharacterClass.SILENT

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=GhostInAJarData.POTION_ID,
            name=GhostInAJarData.NAME,
            rarity=GhostInAJarData.RARITY,
            size=PotionSize.CARD,
            color=GhostInAJarData.COLOR,
            description=GhostInAJarData.DESCRIPTION,
            character_class=GhostInAJarData.CHAR_CLASS,
            is_Thrown=False,
            potency=1,
            sacred_bark_potency=2
        )


@register_potion
class HeartofIronData:
    POTION_ID = "HeartofIron"
    NAME = "钢铁之心"
    DESCRIPTION = "获得 6 层金属化。（神圣树皮则是12）"
    RARITY = PotionRarity.RARE
    COLOR = PotionColor.ORANGE
    CHAR_CLASS = CharacterClass.IRONCLAD

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=HeartofIronData.POTION_ID,
            name=HeartofIronData.NAME,
            rarity=HeartofIronData.RARITY,
            size=PotionSize.CARD,
            color=HeartofIronData.COLOR,
            description=HeartofIronData.DESCRIPTION,
            character_class=HeartofIronData.CHAR_CLASS,
            is_Thrown=False,
            potency=6,
            sacred_bark_potency=12
        )


@register_potion
class LiquidBronzeData:
    POTION_ID = "LiquidBronze"
    NAME = "流动铜液"
    DESCRIPTION = "获得 3 层荆棘。（神圣树皮则是6）"
    RARITY = PotionRarity.UNCOMMON
    COLOR = PotionColor.ORANGE
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=LiquidBronzeData.POTION_ID,
            name=LiquidBronzeData.NAME,
            rarity=LiquidBronzeData.RARITY,
            size=PotionSize.CARD,
            color=LiquidBronzeData.COLOR,
            description=LiquidBronzeData.DESCRIPTION,
            character_class=LiquidBronzeData.CHAR_CLASS,
            is_Thrown=False,
            potency=3,
            sacred_bark_potency=6
        )


@register_potion
class LiquidMemoriesData:
    POTION_ID = "LiquidMemories"
    NAME = "液态记忆"
    DESCRIPTION = "从弃牌堆中选择 1 张牌，将其加入你的手牌，这张牌在本回合耗能变为 0 。（神圣树皮则是2张）"
    RARITY = PotionRarity.UNCOMMON
    COLOR = PotionColor.BLUE
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=LiquidMemoriesData.POTION_ID,
            name=LiquidMemoriesData.NAME,
            rarity=LiquidMemoriesData.RARITY,
            size=PotionSize.CARD,
            color=LiquidMemoriesData.COLOR,
            description=LiquidMemoriesData.DESCRIPTION,
            character_class=LiquidMemoriesData.CHAR_CLASS,
            is_Thrown=False,
            potency=1,
            sacred_bark_potency=2
        )


@register_potion
class PotionofCapacityData:
    POTION_ID = "PotionofCapacity"
    NAME = "扩容药水"
    DESCRIPTION = "获得 2 个充能球槽位。（神圣树皮则是4）"
    RARITY = PotionRarity.UNCOMMON
    COLOR = PotionColor.BLUE
    CHAR_CLASS = CharacterClass.DEFECT

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=PotionofCapacityData.POTION_ID,
            name=PotionofCapacityData.NAME,
            rarity=PotionofCapacityData.RARITY,
            size=PotionSize.CARD,
            color=PotionofCapacityData.COLOR,
            description=PotionofCapacityData.DESCRIPTION,
            character_class=PotionofCapacityData.CHAR_CLASS,
            is_Thrown=False,
            potency=2,
            sacred_bark_potency=4
        )


@register_potion
class SneckoOilData:
    POTION_ID = "SneckoOil"
    NAME = "异蛇之油"
    DESCRIPTION = "抽 5 张牌，然后随机化你当前手牌中所有牌的耗能，每张牌为 0 到 3 之间的随机值（在本场战斗中生效）。（神圣树皮则是抽10张）"
    RARITY = PotionRarity.RARE
    COLOR = PotionColor.GREEN
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=SneckoOilData.POTION_ID,
            name=SneckoOilData.NAME,
            rarity=SneckoOilData.RARITY,
            size=PotionSize.CARD,
            color=SneckoOilData.COLOR,
            description=SneckoOilData.DESCRIPTION,
            character_class=SneckoOilData.CHAR_CLASS,
            is_Thrown=False,
            potency=5,
            sacred_bark_potency=10
        )


@register_potion
class StancePotionData:
    POTION_ID = "StancePotion"
    NAME = "姿态药水"
    DESCRIPTION = "进入冷静或愤怒姿态。"
    RARITY = PotionRarity.UNCOMMON
    COLOR = PotionColor.WHITE
    CHAR_CLASS = CharacterClass.WATCHER

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=StancePotionData.POTION_ID,
            name=StancePotionData.NAME,
            rarity=StancePotionData.RARITY,
            size=PotionSize.CARD,
            color=StancePotionData.COLOR,
            description=StancePotionData.DESCRIPTION,
            character_class=StancePotionData.CHAR_CLASS,
            is_Thrown=False,
            potency=0,
            sacred_bark_potency=None
        )


@register_potion
class AmbrosiaData:
    POTION_ID = "Ambrosia"
    NAME = "仙馔密酒"
    DESCRIPTION = "进入神性姿态。"
    RARITY = PotionRarity.RARE
    COLOR = PotionColor.GOLD
    CHAR_CLASS = CharacterClass.WATCHER

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=AmbrosiaData.POTION_ID,
            name=AmbrosiaData.NAME,
            rarity=AmbrosiaData.RARITY,
            size=PotionSize.CARD,
            color=AmbrosiaData.COLOR,
            description=AmbrosiaData.DESCRIPTION,
            character_class=AmbrosiaData.CHAR_CLASS,
            is_Thrown=False,
            potency=1,
            sacred_bark_potency=None
        )


@register_potion
class EntropicBrewData:
    POTION_ID = "EntropicBrew"
    NAME = "混沌药水"
    DESCRIPTION = "用随机药水填满所有空的药水槽位。"
    RARITY = PotionRarity.RARE
    COLOR = PotionColor.PURPLE
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=EntropicBrewData.POTION_ID,
            name=EntropicBrewData.NAME,
            rarity=EntropicBrewData.RARITY,
            size=PotionSize.CARD,
            color=EntropicBrewData.COLOR,
            description=EntropicBrewData.DESCRIPTION,
            character_class=EntropicBrewData.CHAR_CLASS,
            is_Thrown=False,
            potency=0,
            sacred_bark_potency=None
        )


@register_potion
class EssenceOfDarknessData:
    POTION_ID = "EssenceOfDarkness"
    NAME = "黑暗精华"
    DESCRIPTION = "每有个充能球栏位就生成1个黑暗充能球。（神圣树皮则是2个）"
    RARITY = PotionRarity.RARE
    COLOR = PotionColor.PURPLE
    CHAR_CLASS = CharacterClass.DEFECT

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=EssenceOfDarknessData.POTION_ID,
            name=EssenceOfDarknessData.NAME,
            rarity=EssenceOfDarknessData.RARITY,
            size=PotionSize.CARD,
            color=EssenceOfDarknessData.COLOR,
            description=EssenceOfDarknessData.DESCRIPTION,
            character_class=EssenceOfDarknessData.CHAR_CLASS,
            is_Thrown=False,
            potency=1,
            sacred_bark_potency=2
        )


@register_potion
class FairyInABottleData:
    POTION_ID = "FairyInABottle"
    NAME = "瓶中精灵"
    DESCRIPTION = "当你即将死亡时，改为回复到最大生命值的 30% 并消耗此药水。（神圣树皮则是60%）"
    RARITY = PotionRarity.RARE
    COLOR = PotionColor.PINK
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=FairyInABottleData.POTION_ID,
            name=FairyInABottleData.NAME,
            rarity=FairyInABottleData.RARITY,
            size=PotionSize.CARD,
            color=FairyInABottleData.COLOR,
            description=FairyInABottleData.DESCRIPTION,
            character_class=FairyInABottleData.CHAR_CLASS,
            is_Thrown=False,
            potency=30,
            sacred_bark_potency=60
        )


@register_potion
class GamblersBrewData:
    POTION_ID = "GamblersBrew"
    NAME = "赌徒特酿"
    DESCRIPTION = "丢弃任意张牌，然后抽等量牌。"
    RARITY = PotionRarity.UNCOMMON
    COLOR = PotionColor.ORANGE
    CHAR_CLASS = CharacterClass.UNIVERSAL

    @staticmethod
    def create_potion() -> AbstractPotion:
        return AbstractPotion(
            potion_id=GamblersBrewData.POTION_ID,
            name=GamblersBrewData.NAME,
            rarity=GamblersBrewData.RARITY,
            size=PotionSize.CARD,
            color=GamblersBrewData.COLOR,
            description=GamblersBrewData.DESCRIPTION,
            character_class=GamblersBrewData.CHAR_CLASS,
            is_Thrown=False,
            potency=0,
            sacred_bark_potency=None
        )


def get_potion_data(potion_id: str):
    return POTION_DEFINITIONS.get(potion_id)


def create_potion(potion_id: str) -> AbstractPotion | None:
    data = get_potion_data(potion_id)
    if data:
        return data.create_potion()
    return None


def _normalize_character_class(character_class: CharacterClass | str | None) -> CharacterClass | None:
    if character_class is None:
        return None
    if isinstance(character_class, CharacterClass):
        return character_class
    return CharacterClass.__members__.get(str(character_class).strip().upper())


def _potion_matches_character(data: object, character_class: CharacterClass | str | None) -> bool:
    normalized = _normalize_character_class(character_class)
    if normalized is None:
        return True
    potion_character_class = getattr(data, "CHAR_CLASS", CharacterClass.UNIVERSAL)
    return potion_character_class in {CharacterClass.UNIVERSAL, normalized}


def get_potions_by_rarity(
    rarity: PotionRarity,
    character_class: CharacterClass | str | None = None,
) -> list:
    return [
        data.create_potion()
        for data in POTION_DEFINITIONS.values()
        if data.RARITY == rarity and _potion_matches_character(data, character_class)
    ]


def get_common_potions(character_class: CharacterClass | str | None = None) -> list:
    return get_potions_by_rarity(PotionRarity.COMMON, character_class)


def get_uncommon_potions(character_class: CharacterClass | str | None = None) -> list:
    return get_potions_by_rarity(PotionRarity.UNCOMMON, character_class)


def get_rare_potions(character_class: CharacterClass | str | None = None) -> list:
    return get_potions_by_rarity(PotionRarity.RARE, character_class)
