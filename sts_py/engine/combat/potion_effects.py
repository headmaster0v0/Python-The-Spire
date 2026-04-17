from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING
import random

from sts_py.engine.combat.stance import StanceType, change_stance

if TYPE_CHECKING:
    from sts_py.engine.content.potions import AbstractPotion, CharacterClass, SACRED_BARK_DOUBLES
    from sts_py.engine.content.card_instance import CardInstance
    from sts_py.engine.combat.combat_state import CombatState

POTION_RARITY_CHANCES = {
    "COMMON": 0.65,
    "UNCOMMON": 0.25,
    "RARE": 0.10,
}


@dataclass
class PotionEffect:
    """Base class for potion effects."""
    potion_id: str

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        return []


def get_effective_potency(potion: AbstractPotion, combat_state: CombatState) -> int:
    """Get the effective potency considering Sacred Bark."""
    from sts_py.engine.content.potions import SACRED_BARK_DOUBLES

    if potion.sacred_bark_potency is not None:
        if hasattr(combat_state, 'player') and combat_state.player:
            has_sacred_bark = any(
                getattr(r, "id", r) == "SacredBark"
                for r in getattr(combat_state.player, "relics", [])
            )
            if has_sacred_bark and potion.potion_id not in SACRED_BARK_DOUBLES:
                return potion.sacred_bark_potency
    return potion.potency


@dataclass
class AttackPotionEffect(PotionEffect):
    """从3张随机攻击牌中选择1张加入手牌，本回合耗能变为0。（SB:将该牌的2张复制加入）"""
    potion_id: str = "AttackPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.content.card_instance import CardInstance

        attack_cards = [
            "Strike", "Anger", "Cleave", "Clothesline", "HeavyBlade",
            "IronWave", "PerfectedStrike", "PommelStrike", "TwinStrike",
            "WildStrike", "BodySlam", "Bash", "Carnage", "Clash",
            "Dropkick", "Headbutt", "Hemokinesis", "Pummel", "RecklessCharge",
            "SearingBlow", "SeverSoul", "SwordBoomerang", "Thunderclap",
            "TrueGrit", "Whirlwind", "Feed", "Bludgeon", "Reaper",
        ]

        potency = get_effective_potency(potion, combat_state)
        chosen_cards = random.sample(attack_cards, min(3, len(attack_cards)))
        chosen_card_id = random.choice(chosen_cards)

        copies_to_add = 2 if potency == 2 else 1
        for _ in range(copies_to_add):
            card = CardInstance(card_id=chosen_card_id, upgraded=False)
            card.cost = 0
            card.cost_for_turn = 0
            combat_state.card_manager.hand.add(card)

        return []


@dataclass
class SkillPotionEffect(PotionEffect):
    """从3张随机技能牌中选择1张加入手牌，本回合耗能为0。（SB:将该牌的2张复制加入）"""
    potion_id: str = "SkillPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.content.card_instance import CardInstance

        skill_cards = [
            "Defend", "Armaments", "ShrugItOff", "TrueGrit",
            "FlameBarrier", "GhostlyArmor", "Impervious", "Sentinel",
            "SecondWind", "PowerThrough", "Rage", "Entrench",
        ]

        potency = get_effective_potency(potion, combat_state)
        chosen_cards = random.sample(skill_cards, min(3, len(skill_cards)))
        chosen_card_id = random.choice(chosen_cards)

        copies_to_add = 2 if potency == 2 else 1
        for _ in range(copies_to_add):
            card = CardInstance(card_id=chosen_card_id, upgraded=False)
            card.cost = 0
            card.cost_for_turn = 0
            combat_state.card_manager.hand.add(card)

        return []


@dataclass
class PowerPotionEffect(PotionEffect):
    """从3张随机能力牌中选择1张加入手牌，本回合耗能为0。（SB:将该牌的2张复制加入）"""
    potion_id: str = "PowerPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.content.card_instance import CardInstance

        power_cards = [
            "Inflame", "DemonForm", "Corruption", "DarkEmbrace",
            "Combust", "Metallicize", "Evolve", "FeelNoPain",
            "Barricade", "Berserk", "Juggernaut", "Brutality",
        ]

        potency = get_effective_potency(potion, combat_state)
        chosen_cards = random.sample(power_cards, min(3, len(power_cards)))
        chosen_card_id = random.choice(chosen_cards)

        copies_to_add = 2 if potency == 2 else 1
        for _ in range(copies_to_add):
            card = CardInstance(card_id=chosen_card_id, upgraded=False)
            card.cost = 0
            card.cost_for_turn = 0
            combat_state.card_manager.hand.add(card)

        return []


@dataclass
class BlessingOfTheForgeEffect(PotionEffect):
    """在本场战斗中升级手牌中的所有牌。"""
    potion_id: str = "BlessingOfTheForge"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        for card in combat_state.card_manager.hand.cards:
            card.upgrade()
        return []


@dataclass
class BlockPotionEffect(PotionEffect):
    """获得格挡。"""
    potion_id: str = "BlockPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        block_amount = get_effective_potency(potion, combat_state)
        combat_state.player.gain_block(block_amount)
        return []


@dataclass
class BloodPotionEffect(PotionEffect):
    """回复最大生命值的百分比。"""
    potion_id: str = "BloodPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        potency = get_effective_potency(potion, combat_state)
        heal_amount = int(combat_state.player.max_hp * potency / 100)
        combat_state.player.heal(heal_amount)
        return []


@dataclass
class BottledMiracleEffect(PotionEffect):
    """增加2张奇迹到你的手牌。（SB:增加4张）"""
    potion_id: str = "BottledMiracle"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.content.card_instance import CardInstance

        potency = get_effective_potency(potion, combat_state)
        for _ in range(potency):
            miracle_card = CardInstance(card_id="Miracle", upgraded=False)
            miracle_card.retain = True
            miracle_card.cost = 0
            combat_state.card_manager.hand.add(miracle_card)
        return []


@dataclass
class ColorlessPotionEffect(PotionEffect):
    """从3张随机无色牌中选择1张加入手牌，本回合耗能为0。（SB:将该牌的2张复制加入）"""
    potion_id: str = "ColorlessPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.content.card_instance import CardInstance

        colorless_cards = [
            "Blind", "Deceive", "Empower", "Empty Mind", "Enlightenment",
            "Finesse", "Focus", "Forethought", "Indignation", "Innovation",
            "Intention", "Madness", "Master of Strategy", "Meditation",
            "Panic", "Purity", "Rashness", "Secret Technique", "Secret Weapon",
            "Shockwave", "Swift", "Thinking", "Trip",
        ]

        potency = get_effective_potency(potion, combat_state)
        chosen_cards = random.sample(colorless_cards, min(3, len(colorless_cards)))
        chosen_card_id = random.choice(chosen_cards)

        copies_to_add = 2 if potency == 2 else 1
        for _ in range(copies_to_add):
            card = CardInstance(card_id=chosen_card_id, upgraded=False)
            card.cost = 0
            card.cost_for_turn = 0
            combat_state.card_manager.hand.add(card)

        return []


@dataclass
class DexterityPotionEffect(PotionEffect):
    """获得敏捷。"""
    potion_id: str = "DexterityPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.combat.powers import create_power
        amount = get_effective_potency(potion, combat_state)
        combat_state.player.add_power(create_power("Dexterity", amount, "player"))
        return []


@dataclass
class DistilledChaosEffect(PotionEffect):
    """打出抽牌堆顶的牌（不消耗能量，随机合法目标）。"""
    potion_id: str = "DistilledChaos"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        potency = get_effective_potency(potion, combat_state)
        engine = getattr(combat_state, "engine", None)
        for _ in range(potency):
            if not combat_state.card_manager.draw_pile.cards:
                continue
            card = combat_state.card_manager.draw_pile.cards.pop()
            card._combat_state = combat_state
            card.free_to_play_once = True
            if engine is not None and hasattr(engine, "autoplay_card_instance"):
                if not engine.autoplay_card_instance(card):
                    combat_state.card_manager.discard_pile.add(card)
        return []


@dataclass
class ElixirEffect(PotionEffect):
    """消耗手牌中任意张牌。"""
    potion_id: str = "Elixir"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        for card in list(combat_state.card_manager.hand.cards):
            combat_state.card_manager.exhaust_pile.add(card)
            combat_state.card_manager.hand.remove(card)
        return []


@dataclass
class EnergyPotionEffect(PotionEffect):
    """获得能量。"""
    potion_id: str = "EnergyPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        amount = get_effective_potency(potion, combat_state)
        combat_state.player.energy += amount
        return []


@dataclass
class ExplosivePotionEffect(PotionEffect):
    """对所有敌人造成伤害。"""
    potion_id: str = "ExplosivePotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        amount = get_effective_potency(potion, combat_state)
        for monster in combat_state.monsters:
            if not monster.is_dead():
                monster.take_damage(amount)
        return []


@dataclass
class FearPotionEffect(PotionEffect):
    """给予1个敌人3层易伤。"""
    potion_id: str = "FearPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.combat.powers import create_power
        amount = get_effective_potency(potion, combat_state)
        if target_idx is not None and target_idx < len(combat_state.monsters):
            monster = combat_state.monsters[target_idx]
            if not monster.is_dead():
                monster.add_power(create_power("Vulnerable", amount, monster.id))
        return []


@dataclass
class FirePotionEffect(PotionEffect):
    """对目标敌人造成伤害。"""
    potion_id: str = "FirePotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        amount = get_effective_potency(potion, combat_state)
        if target_idx is not None and target_idx < len(combat_state.monsters):
            monster = combat_state.monsters[target_idx]
            if not monster.is_dead():
                monster.take_damage(amount)
        return []


@dataclass
class FlexPotionEffect(PotionEffect):
    """获得力量，回合结束时失去。"""
    potion_id: str = "FlexPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.combat.powers import create_power
        amount = get_effective_potency(potion, combat_state)
        combat_state.player.add_power(create_power("Strength", amount, "player"))
        combat_state.player.add_power(create_power("Lose Strength", amount, "player"))
        return []


@dataclass
class FocusPotionEffect(PotionEffect):
    """获得专注。"""
    potion_id: str = "FocusPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.combat.powers import create_power
        amount = get_effective_potency(potion, combat_state)
        combat_state.player.add_power(create_power("Focus", amount, "player"))
        return []


@dataclass
class FruitJuiceEffect(PotionEffect):
    """获得最大生命值。"""
    potion_id: str = "FruitJuice"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        amount = get_effective_potency(potion, combat_state)
        combat_state.player.max_hp += amount
        combat_state.player.hp += amount
        return []


@dataclass
class PoisonPotionEffect(PotionEffect):
    """给予目标敌人6层中毒。"""
    potion_id: str = "PoisonPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.combat.powers import create_power
        amount = get_effective_potency(potion, combat_state)
        if target_idx is not None and target_idx < len(combat_state.monsters):
            monster = combat_state.monsters[target_idx]
            if not monster.is_dead():
                monster.add_power(create_power("Poison", amount, monster.id))
        return []


@dataclass
class RegenPotionEffect(PotionEffect):
    """获得再生。"""
    potion_id: str = "RegenPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.combat.powers import create_power
        amount = get_effective_potency(potion, combat_state)
        combat_state.player.add_power(create_power("Regen", amount, "player"))
        return []


@dataclass
class SmokeBombEffect(PotionEffect):
    """从非首领战斗中逃跑。"""
    potion_id: str = "SmokeBomb"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        combat_state.escape_combat = True
        return []


@dataclass
class SpeedPotionEffect(PotionEffect):
    """获得敏捷，回合结束时失去。"""
    potion_id: str = "SpeedPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.combat.powers import create_power
        amount = get_effective_potency(potion, combat_state)
        combat_state.player.add_power(create_power("Dexterity", amount, "player"))
        combat_state.player.add_power(create_power("Lose Dexterity", amount, "player"))
        return []


@dataclass
class StrengthPotionEffect(PotionEffect):
    """获得力量。"""
    potion_id: str = "StrengthPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.combat.powers import create_power
        amount = get_effective_potency(potion, combat_state)
        combat_state.player.add_power(create_power("Strength", amount, "player"))
        return []


@dataclass
class SwiftPotionEffect(PotionEffect):
    """抽牌。"""
    potion_id: str = "SwiftPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        amount = get_effective_potency(potion, combat_state)
        combat_state.card_manager.draw_cards(amount)
        return []


@dataclass
class WeakPotionEffect(PotionEffect):
    """给予目标敌人3层虚弱。"""
    potion_id: str = "WeakPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.combat.powers import create_power
        amount = get_effective_potency(potion, combat_state)
        if target_idx is not None and target_idx < len(combat_state.monsters):
            monster = combat_state.monsters[target_idx]
            if not monster.is_dead():
                monster.add_power(create_power("Weak", amount, monster.id))
        return []


@dataclass
class AncientPotionEffect(PotionEffect):
    """获得人工制品。"""
    potion_id: str = "AncientPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.combat.powers import create_power
        amount = get_effective_potency(potion, combat_state)
        combat_state.player.add_power(create_power("Artifact", amount, "player"))
        return []


@dataclass
class CultistPotionEffect(PotionEffect):
    """获得仪式。"""
    potion_id: str = "CultistPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.combat.powers import create_power
        amount = get_effective_potency(potion, combat_state)
        combat_state.player.add_power(create_power("Ritual", amount, "player"))
        return []


@dataclass
class CunningPotionEffect(PotionEffect):
    """将3张升级的飞刀加入手牌。"""
    potion_id: str = "CunningPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.content.card_instance import CardInstance
        potency = get_effective_potency(potion, combat_state)
        for _ in range(potency):
            shiv = CardInstance(card_id="Shiv", upgraded=True)
            shiv.cost = 0
            combat_state.card_manager.hand.add(shiv)
        return []


@dataclass
class DuplicationPotionEffect(PotionEffect):
    """下次牌被打出两次。"""
    potion_id: str = "DuplicationPotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.combat.powers import create_power
        amount = get_effective_potency(potion, combat_state)
        combat_state.player.add_power(create_power("Duplication", amount, "player"))
        return []


@dataclass
class EssenceOfSteelEffect(PotionEffect):
    """获得护甲。"""
    potion_id: str = "EssenceOfSteel"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.combat.powers import create_power
        amount = get_effective_potency(potion, combat_state)
        combat_state.player.add_power(create_power("Plated Armor", amount, "player"))
        return []


@dataclass
class GhostInAJarEffect(PotionEffect):
    """获得无形。"""
    potion_id: str = "GhostInAJar"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.combat.powers import create_power
        amount = get_effective_potency(potion, combat_state)
        combat_state.player.add_power(create_power("Intangible", amount, "player"))
        return []


@dataclass
class HeartofIronEffect(PotionEffect):
    """获得金属化。"""
    potion_id: str = "HeartofIron"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.combat.powers import create_power
        amount = get_effective_potency(potion, combat_state)
        combat_state.player.add_power(create_power("Metallicize", amount, "player"))
        return []


@dataclass
class LiquidBronzeEffect(PotionEffect):
    """获得荆棘。"""
    potion_id: str = "LiquidBronze"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.combat.powers import create_power
        amount = get_effective_potency(potion, combat_state)
        combat_state.player.add_power(create_power("Thorns", amount, "player"))
        return []


@dataclass
class LiquidMemoriesEffect(PotionEffect):
    """从弃牌堆中选择1张牌加入手牌，本回合耗能为0。"""
    potion_id: str = "LiquidMemories"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.content.card_instance import CardInstance
        potency = get_effective_potency(potion, combat_state)
        discard_pile = list(combat_state.card_manager.discard_pile.cards)
        for _ in range(potency):
            if discard_pile:
                card = discard_pile.pop()
                card.cost = 0
                card.cost_for_turn = 0
                combat_state.card_manager.hand.add(card)
        return []


@dataclass
class PotionofCapacityEffect(PotionEffect):
    """获得充能球槽位。"""
    potion_id: str = "PotionofCapacity"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        amount = get_effective_potency(potion, combat_state)
        combat_state.player.orbs.slots += amount
        return []


@dataclass
class SneckoOilEffect(PotionEffect):
    """抽牌并随机化当前手牌的耗能为本场战斗中随机的耗能值。"""
    potion_id: str = "SneckoOil"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        potency = get_effective_potency(potion, combat_state)
        combat_state.card_manager.draw_cards(potency)
        for card in combat_state.card_manager.hand.cards:
            card.cost = random.randint(0, 3)
        return []


@dataclass
class StancePotionEffect(PotionEffect):
    """进入冷静或愤怒姿态。"""
    potion_id: str = "StancePotion"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        stance = random.choice([StanceType.CALM, StanceType.WRATH])
        change_stance(combat_state.player, stance)
        return []


@dataclass
class AmbrosiaEffect(PotionEffect):
    """进入神性姿态。"""
    potion_id: str = "Ambrosia"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        change_stance(combat_state.player, StanceType.DIVINITY)
        return []


@dataclass
class EntropicBrewEffect(PotionEffect):
    """用随机药水填满空的药水槽位。"""
    potion_id: str = "EntropicBrew"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.content.potions import get_common_potions, get_uncommon_potions, get_rare_potions

        run_state = getattr(getattr(combat_state, "run_engine", None), "state", None)
        if run_state is None:
            run_state = getattr(getattr(combat_state, "engine", None), "state", None)
        potion_slots = getattr(run_state, "potions", None)
        if not isinstance(potion_slots, list):
            return []

        character_class = getattr(run_state, "character_class", getattr(getattr(combat_state, "player", None), "character_class", None))
        all_potions = (
            get_common_potions(character_class)
            + get_uncommon_potions(character_class)
            + get_rare_potions(character_class)
        )
        for index, slot in enumerate(potion_slots):
            if slot != "EmptyPotionSlot":
                continue
            random_potion = random.choice(all_potions)
            potion_slots[index] = random_potion.potion_id
        return []


@dataclass
class EssenceOfDarknessEffect(PotionEffect):
    """引导暗黑充能球。"""
    potion_id: str = "EssenceOfDarkness"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        from sts_py.engine.orbs import DarkOrb
        amount = get_effective_potency(potion, combat_state)
        for _ in range(amount):
            if combat_state.player.orbs.slots > len(combat_state.player.orbs.channels):
                combat_state.player.orbs.channel(DarkOrb())
        return []


@dataclass
class FairyInABottleEffect(PotionEffect):
    """濒死时回复生命。"""
    potion_id: str = "FairyInABottle"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        combat_state.player.fairy_in_a_bottle = True
        combat_state.player.fairy_heal_percent = get_effective_potency(potion, combat_state)
        return []


@dataclass
class GamblersBrewEffect(PotionEffect):
    """丢弃任意数量的牌并抽等量的牌。"""
    potion_id: str = "GamblersBrew"

    def execute(self, combat_state: CombatState, potion: AbstractPotion, target_idx: int | None = None) -> list:
        hand_size = len(combat_state.card_manager.hand.cards)
        for card in list(combat_state.card_manager.hand.cards):
            combat_state.card_manager.discard_pile.add(card)
        combat_state.card_manager.hand.cards.clear()
        combat_state.card_manager.draw_cards(hand_size)
        return []


POTION_EFFECTS: dict = {
    "AttackPotion": AttackPotionEffect(potion_id="AttackPotion"),
    "SkillPotion": SkillPotionEffect(potion_id="SkillPotion"),
    "PowerPotion": PowerPotionEffect(potion_id="PowerPotion"),
    "BlessingOfTheForge": BlessingOfTheForgeEffect(potion_id="BlessingOfTheForge"),
    "BlockPotion": BlockPotionEffect(potion_id="BlockPotion"),
    "BloodPotion": BloodPotionEffect(potion_id="BloodPotion"),
    "BottledMiracle": BottledMiracleEffect(potion_id="BottledMiracle"),
    "ColorlessPotion": ColorlessPotionEffect(potion_id="ColorlessPotion"),
    "DexterityPotion": DexterityPotionEffect(potion_id="DexterityPotion"),
    "DistilledChaos": DistilledChaosEffect(potion_id="DistilledChaos"),
    "Elixir": ElixirEffect(potion_id="Elixir"),
    "EnergyPotion": EnergyPotionEffect(potion_id="EnergyPotion"),
    "ExplosivePotion": ExplosivePotionEffect(potion_id="ExplosivePotion"),
    "FearPotion": FearPotionEffect(potion_id="FearPotion"),
    "FirePotion": FirePotionEffect(potion_id="FirePotion"),
    "FlexPotion": FlexPotionEffect(potion_id="FlexPotion"),
    "FocusPotion": FocusPotionEffect(potion_id="FocusPotion"),
    "FruitJuice": FruitJuiceEffect(potion_id="FruitJuice"),
    "PoisonPotion": PoisonPotionEffect(potion_id="PoisonPotion"),
    "RegenPotion": RegenPotionEffect(potion_id="RegenPotion"),
    "SmokeBomb": SmokeBombEffect(potion_id="SmokeBomb"),
    "SpeedPotion": SpeedPotionEffect(potion_id="SpeedPotion"),
    "StrengthPotion": StrengthPotionEffect(potion_id="StrengthPotion"),
    "SwiftPotion": SwiftPotionEffect(potion_id="SwiftPotion"),
    "WeakPotion": WeakPotionEffect(potion_id="WeakPotion"),
    "AncientPotion": AncientPotionEffect(potion_id="AncientPotion"),
    "CultistPotion": CultistPotionEffect(potion_id="CultistPotion"),
    "CunningPotion": CunningPotionEffect(potion_id="CunningPotion"),
    "DuplicationPotion": DuplicationPotionEffect(potion_id="DuplicationPotion"),
    "EssenceOfSteel": EssenceOfSteelEffect(potion_id="EssenceOfSteel"),
    "GhostInAJar": GhostInAJarEffect(potion_id="GhostInAJar"),
    "HeartofIron": HeartofIronEffect(potion_id="HeartofIron"),
    "LiquidBronze": LiquidBronzeEffect(potion_id="LiquidBronze"),
    "LiquidMemories": LiquidMemoriesEffect(potion_id="LiquidMemories"),
    "PotionofCapacity": PotionofCapacityEffect(potion_id="PotionofCapacity"),
    "SneckoOil": SneckoOilEffect(potion_id="SneckoOil"),
    "StancePotion": StancePotionEffect(potion_id="StancePotion"),
    "Ambrosia": AmbrosiaEffect(potion_id="Ambrosia"),
    "EntropicBrew": EntropicBrewEffect(potion_id="EntropicBrew"),
    "EssenceOfDarkness": EssenceOfDarknessEffect(potion_id="EssenceOfDarkness"),
    "FairyInABottle": FairyInABottleEffect(potion_id="FairyInABottle"),
    "GamblersBrew": GamblersBrewEffect(potion_id="GamblersBrew"),
}


def use_potion(potion: AbstractPotion, combat_state: CombatState, target_idx: int | None = None) -> list:
    """Use a potion and return any resulting effects."""
    effect = POTION_EFFECTS.get(potion.potion_id)
    if effect:
        return effect.execute(combat_state, potion, target_idx)
    return []


def get_random_potion_by_rarity(
    rarity: str,
    character_class: str | None = None,
) -> AbstractPotion | None:
    """Get a random potion by rarity (COMMON, UNCOMMON, RARE)."""
    from sts_py.engine.content.potions import get_common_potions, get_uncommon_potions, get_rare_potions

    if rarity == "COMMON":
        potions = get_common_potions(character_class)
    elif rarity == "UNCOMMON":
        potions = get_uncommon_potions(character_class)
    elif rarity == "RARE":
        potions = get_rare_potions(character_class)
    else:
        return None

    if potions:
        return random.choice(potions).make_copy()
    return None


def roll_potion_rarity() -> str:
    """Roll for potion rarity based on chances (65% COMMON, 25% UNCOMMON, 10% RARE)."""
    roll = random.random()
    if roll < 0.65:
        return "COMMON"
    elif roll < 0.90:
        return "UNCOMMON"
    else:
        return "RARE"
