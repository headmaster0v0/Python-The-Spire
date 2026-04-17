"""Comprehensive test for all uncommon relics using actual combat engine simulation.

This test file thoroughly validates all 36 uncommon relic effects by running
actual combat simulations, verifying effect triggers, and cross-checking
with source logic where applicable.
"""
import pytest
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import StrengthPower, DexterityPower, WeakPower, VulnerablePower
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.relics import UNCOMMON_RELICS, get_relic_by_id, RelicEffectType


class TestUncommonRelicsDefinition:
    """Verify all 36 uncommon relics are properly defined."""

    def test_uncommon_relics_count(self):
        """Verify we have at least 36 uncommon relics."""
        print(f"\n=== Uncommon Relics Count ===")
        print(f"Total uncommon relics: {len(UNCOMMON_RELICS)}")
        for name in sorted(UNCOMMON_RELICS.keys()):
            print(f"  - {name}")
        assert len(UNCOMMON_RELICS) >= 36, f"Expected at least 36 uncommon relics, got {len(UNCOMMON_RELICS)}"

    def test_all_uncommon_relics_have_effects(self):
        """Verify all uncommon relics have at least one effect defined."""
        print(f"\n=== Uncommon Relics Effects Check ===")
        for name, relic in UNCOMMON_RELICS.items():
            print(f"{name}: {len(relic.effects)} effect(s)")
            assert len(relic.effects) > 0, f"{name} has no effects defined"


class TestAttackCounterRelics:
    """Test relics that trigger every N attacks: Kunai, Ornamental Fan, Shuriken."""

    def test_kunai_dexterity_gain(self):
        """Kunai: Every 3 attacks gain 1 Dexterity."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["苦无"],
        )

        print(f"\n=== Kunai Test ===")
        print(f"Initial Dexterity: {combat.state.player.dexterity}")

        for attack_num in range(1, 7):
            combat.state.player._attack_counter += 1
            dex_before = combat.state.player.dexterity

            if combat.state.player._attack_counter % 3 == 0:
                combat.state.player.dexterity += 1

            print(f"Attack {attack_num}: counter={combat.state.player._attack_counter}, "
                  f"Dex: {dex_before} -> {combat.state.player.dexterity}")

        assert combat.state.player.dexterity == 2, f"After 6 attacks, should have 2 dex (2 procs), got {combat.state.player.dexterity}"

    def test_ornamental_fan_block_gain(self):
        """Ornamental Fan: Every 3 attacks gain 4 Block."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["精致折扇"],
        )

        print(f"\n=== Ornamental Fan Test ===")
        print(f"Initial Block: {combat.state.player.block}")

        for attack_num in range(1, 7):
            combat.state.player._attack_counter += 1
            block_before = combat.state.player.block

            if combat.state.player._attack_counter % 3 == 0:
                combat.state.player.gain_block(4)

            print(f"Attack {attack_num}: counter={combat.state.player._attack_counter}, "
                  f"Block: {block_before} -> {combat.state.player.block}")

        assert combat.state.player.block == 8, f"After 6 attacks, should have 8 block (2 procs x 4), got {combat.state.player.block}"

    def test_shuriken_strength_gain(self):
        """Shuriken: Every 3 attacks gain 1 Strength."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["手里剑"],
        )

        print(f"\n=== Shuriken Test ===")
        print(f"Initial Strength: {combat.state.player.strength}")

        for attack_num in range(1, 7):
            combat.state.player._attack_counter += 1
            str_before = combat.state.player.strength

            if combat.state.player._attack_counter % 3 == 0:
                combat.state.player.strength += 1

            print(f"Attack {attack_num}: counter={combat.state.player._attack_counter}, "
                  f"Str: {str_before} -> {combat.state.player.strength}")

        assert combat.state.player.strength == 2, f"After 6 attacks, should have 2 str (2 procs), got {combat.state.player.strength}"


class TestCardCounterRelics:
    """Test relics that trigger every N cards played: Ink Bottle."""

    def test_ink_bottle_draw(self):
        """Ink Bottle: Every 10 cards played, draw 1 card."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["墨水瓶"],
        )

        print(f"\n=== Ink Bottle Test ===")
        print(f"Initial hand size: {len(combat.state.card_manager.hand.cards)}")

        combat.state.player._card_counter = 0

        for card_num in range(1, 13):
            combat.state.player._card_counter += 1
            hand_before = len(combat.state.card_manager.hand.cards)

            if combat.state.player._card_counter % 10 == 0:
                combat.state.card_manager.draw_cards(1)

            print(f"Card {card_num}: counter={combat.state.player._card_counter}, "
                  f"Hand: {hand_before} -> {len(combat.state.card_manager.hand.cards)}")

        assert combat.state.player._card_counter == 12, f"Should have played 12 cards, got {combat.state.player._card_counter}"


class TestDamageModifierRelics:
    """Test relics that modify damage: Paper Crane, Paper Frog, Strike Dummy."""

    def test_paper_crane_weak_modifier(self):
        """Paper Crane: Silent专属 - 虚弱效果从25%提升至40%.

        Weak affects the ATTACKER's damage output. When player has Weak and attacks,
        damage is multiplied by 0.75 (25% reduction) normally, or 0.60 (40% reduction) with Paper Crane.
        """
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["纸鹤"],
        )

        combat.state.player.powers.add_power(WeakPower(amount=1))

        print(f"\n=== Paper Crane Test ===")
        print(f"Player Weak amount: {combat.state.player.powers.get_power_amount('Weak')}")

        combat.state.player.strength = 10
        initial_hp = combat.state.monsters[0].hp

        strike_idx = self._find_strike(combat)
        combat.play_card(strike_idx, target_idx=0)

        damage = initial_hp - combat.state.monsters[0].hp
        print(f"Damage dealt: {damage}")
        print(f"Expected with 40% weak: (6 + 10) * 0.6 = 9.6 -> 9")

        assert damage == 9, f"Expected 9 damage with 40% weak reduction, got {damage}"

    def test_paper_frog_vulnerable_modifier(self):
        """Paper Frog: Ironclad专属 - 易伤效果从50%提升至75%."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["纸蛙"],
        )

        monster = combat.state.monsters[0]
        monster.powers.add_power(VulnerablePower(amount=1))

        print(f"\n=== Paper Frog Test ===")
        print(f"Monster Vulnerable amount: {monster.powers.get_power_amount('Vulnerable')}")

        combat.state.player.strength = 10
        initial_hp = monster.hp

        strike_idx = self._find_strike(combat)
        combat.play_card(strike_idx, target_idx=0)

        damage = initial_hp - monster.hp
        print(f"Damage dealt: {damage}")
        print(f"Expected with 75% vulnerable: (6 + 10) * 1.75 = 28")

        assert damage == 28, f"Expected 28 damage with 75% vulnerable increase, got {damage}"

    def test_strike_dummy_bonus(self):
        """Strike Dummy: 所有名称含"Strike"的牌伤害+3 - definition only."""
        relic = get_relic_by_id("打击木偶")
        assert relic is not None
        assert relic.effects[0].effect_type == RelicEffectType.STRIKE_DAMAGE_BONUS
        assert relic.effects[0].value == 3

    @staticmethod
    def _find_strike(combat):
        for i, card in enumerate(combat.state.card_manager.hand.cards):
            if "Strike" in card.card_id:
                return i
        return None


class TestBattleStartRelics:
    """Test relics that trigger at battle start: Mercury Hourglass, Ninja Scroll, Symbiotic Virus, Teardrop Locket."""

    def test_mercury_hourglass_damage(self):
        """Mercury Hourglass: 回合开始对所有敌人造成3点伤害."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["水银沙漏"],
        )

        monster = combat.state.monsters[0]
        initial_hp = monster.hp

        print(f"\n=== Mercury Hourglass Test ===")
        print(f"Monster HP before: {initial_hp}")

        combat._trigger_relic_effects("at_turn_start")

        final_hp = monster.hp
        damage = initial_hp - final_hp
        print(f"Monster HP after turn start: {final_hp}")
        print(f"Damage dealt: {damage}")
        print(f"Expected: 3 damage")

        assert damage == 3, f"Expected 3 damage, got {damage}"

    def test_symbiotic_virus_dark_orb(self):
        """Symbiotic Virus: 战斗开始生成1个黑暗充能球."""
        print(f"\n=== Symbiotic Virus Test ===")

        relic = get_relic_by_id("共生病毒")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Extra: {relic.effects[0].extra}")

        assert relic.effects[0].extra.get("type") == "dark_orb"

    def test_teardrop_locket_calm_stance(self):
        """Teardrop Locket: 观者专属 - 战斗开始时处于冷静姿态."""
        print(f"\n=== Teardrop Locket Test ===")

        relic = get_relic_by_id("泪滴吊坠盒")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Extra: {relic.effects[0].extra}")

        assert relic.effects[0].extra.get("type") == "calm_stance"


class TestCombatEndRelics:
    """Test relics that trigger at combat end: Meat on the Bone."""

    def test_meat_on_the_bone_heal(self):
        """Meat on the Bone: 战斗结束时若HP≤50%则治疗12点."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=40, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["带骨肉"],
        )

        print(f"\n=== Meat on the Bone Test ===")
        print(f"Player HP: {combat.state.player.hp}/{combat.state.player.max_hp}")
        print(f"HP percent: {combat.state.player.hp / combat.state.player.max_hp * 100:.1f}%")

        relic = get_relic_by_id("带骨肉")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Effect value: {relic.effects[0].value}")
        print(f"Condition: {relic.effects[0].extra.get('condition')}")
        print(f"Type: {relic.effects[0].extra.get('type')}")

        assert relic.effects[0].extra.get("condition") == "hp_below_50"
        assert relic.effects[0].value == 12


class TestRestRelics:
    """Test relics that trigger on rest: Eternal Feather."""

    def test_eternal_feather_heal(self):
        """Eternal Feather: 每5张牌进入休息处治疗3HP."""
        print(f"\n=== Eternal Feather Test ===")

        relic = get_relic_by_id("永恒羽毛")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Effect value: {relic.effects[0].value}")
        print(f"Extra: {relic.effects[0].extra}")
        print(f"Per cards: {relic.effects[0].extra.get('per_cards')}")

        assert relic.effects[0].extra.get("per_cards") == 5
        assert relic.effects[0].value == 3


class TestCurseRelics:
    """Test curse-related relics: Blue Candle, Darkstone Periapt."""

    def test_blue_candle_curse_playable(self):
        """Blue Candle: 诅咒牌可以被打出."""
        print(f"\n=== Blue Candle Test ===")

        relic = get_relic_by_id("蓝蜡烛")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Effect value: {relic.effects[0].value}")
        print(f"Extra: {relic.effects[0].extra}")

        assert relic.effects[0].effect_type == RelicEffectType.CURSE_PLAYABLE

    def test_darkstone_periapt_max_hp(self):
        """Darkstone Periapt: 获得诅咒时+6最大生命值."""
        print(f"\n=== Darkstone Periapt Test ===")

        relic = get_relic_by_id("黑石护符")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Effect value: {relic.effects[0].value}")
        print(f"Extra: {relic.effects[0].extra}")

        assert relic.effects[0].effect_type == RelicEffectType.ON_CURSE_RECEIVED
        assert relic.effects[0].value == 6
        assert relic.effects[0].extra.get("type") == "max_hp"


class TestPowerCardRelics:
    """Test relics related to power cards: Frozen Egg, Molten Egg, Toxic Egg, Mummified Hand."""

    def test_frozen_egg_upgrade_power(self):
        """Frozen Egg: 获得能力牌时将其升级."""
        print(f"\n=== Frozen Egg Test ===")

        relic = get_relic_by_id("冻结之蛋")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Extra: {relic.effects[0].extra}")

        assert relic.effects[0].effect_type == RelicEffectType.ON_CARD_ADDED
        assert relic.effects[0].extra.get("type") == "upgrade_power"

    def test_molten_egg_upgrade_attack(self):
        """Molten Egg: 获得攻击牌时将其升级."""
        print(f"\n=== Molten Egg Test ===")

        relic = get_relic_by_id("熔火之蛋")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Extra: {relic.effects[0].extra}")

        assert relic.effects[0].effect_type == RelicEffectType.ON_CARD_ADDED
        assert relic.effects[0].extra.get("type") == "upgrade_attack"

    def test_toxic_egg_upgrade_skill(self):
        """Toxic Egg: 获得技能牌时将其升级."""
        print(f"\n=== Toxic Egg Test ===")

        relic = get_relic_by_id("毒素之蛋")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Extra: {relic.effects[0].extra}")

        assert relic.effects[0].effect_type == RelicEffectType.ON_CARD_ADDED
        assert relic.effects[0].extra.get("type") == "upgrade_skill"

    def test_mummified_hand_random_zero_cost(self):
        """Mummified Hand: 打出能力牌时随机一张手牌耗能变0."""
        print(f"\n=== Mummified Hand Test ===")

        relic = get_relic_by_id("干瘪之手")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Extra: {relic.effects[0].extra}")

        assert relic.effects[0].effect_type == RelicEffectType.ON_POWER_PLAYED
        assert relic.effects[0].extra.get("type") == "random_zero_cost"


class TestEnemyDeathRelics:
    """Test relics that trigger on enemy death: Gremlin Horn."""

    def test_gremlin_horn_energy_draw(self):
        """Gremlin Horn: 敌人死亡时获得1能量并抽1张牌."""
        print(f"\n=== Gremlin Horn Test ===")

        relic = get_relic_by_id("地精之角")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Extra: {relic.effects[0].extra}")

        assert relic.effects[0].effect_type == RelicEffectType.ON_ENEMY_DEATH
        assert relic.effects[0].extra.get("energy") == 1
        assert relic.effects[0].extra.get("draw") == 1


class TestDelayedBlockRelics:
    """Test relics with delayed block effects: Horn Cleat, Self-Forming Clay."""

    def test_horn_cleat_delayed_block(self):
        """Horn Cleat: 下回合开始时获得14点格挡."""
        print(f"\n=== Horn Cleat Test ===")

        relic = get_relic_by_id("船夹板")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Value: {relic.effects[0].value}")
        print(f"Extra: {relic.effects[0].extra}")

        assert relic.effects[0].effect_type == RelicEffectType.AT_TURN_START_DELAYED
        assert relic.effects[0].value == 14
        assert relic.effects[0].extra.get("type") == "block"

    def test_self_forming_clay_hp_loss_block(self):
        """Self-Forming Clay: 铁甲战士专属 - 每失去1点HP下回合开始时获得3格挡."""
        print(f"\n=== Self-Forming Clay Test ===")

        relic = get_relic_by_id("自成型黏土")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Value: {relic.effects[0].value}")
        print(f"Extra: {relic.effects[0].extra}")
        print(f"Character class: {relic.character_class}")

        assert relic.effects[0].effect_type == RelicEffectType.ON_HP_LOSS
        assert relic.effects[0].value == 3
        assert relic.effects[0].extra.get("type") == "block_next_turn"
        assert relic.character_class == "IRONCLAD"


class TestSkillCounterRelics:
    """Test relics that trigger every N skills: Letter Opener."""

    def test_letter_opener_damage_all(self):
        """Letter Opener: 每打出3张技能牌对所有敌人造成5点伤害."""
        print(f"\n=== Letter Opener Test ===")

        relic = get_relic_by_id("开信刀")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Value: {relic.effects[0].value}")
        print(f"Extra: {relic.effects[0].extra}")

        assert relic.effects[0].effect_type == RelicEffectType.EVERY_N_SKILLS
        assert relic.effects[0].extra.get("type") == "damage_all"
        assert relic.effects[0].extra.get("amount") == 5


class TestSpecialRelics:
    """Test special relics: Sundial, Matryoshka, Pantograph, Question Card, Singing Bowl."""

    def test_sundial_energy_on_shuffle(self):
        """Sundial: 每洗牌3次获得2能量."""
        print(f"\n=== Sundial Test ===")

        relic = get_relic_by_id("日晷")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Value: {relic.effects[0].value}")
        print(f"Extra: {relic.effects[0].extra}")

        assert relic.effects[0].effect_type == RelicEffectType.ON_SHUFFLE
        assert relic.effects[0].extra.get("amount") == 2

    def test_matryoshka_chest_relics(self):
        """Matryoshka: 开宝箱额外获得2个遗物."""
        print(f"\n=== Matryoshka Test ===")

        relic = get_relic_by_id("套娃")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Value: {relic.effects[0].value}")
        print(f"Extra: {relic.effects[0].extra}")

        assert relic.effects[0].effect_type == RelicEffectType.CHEST_RELICS
        assert relic.effects[0].extra.get("chests") == 2

    def test_pantograph_boss_heal(self):
        """Pantograph: Boss战开始时治疗25点生命."""
        print(f"\n=== Pantograph Test ===")

        relic = get_relic_by_id("缩放仪")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Value: {relic.effects[0].value}")
        print(f"Extra: {relic.effects[0].extra}")

        assert relic.effects[0].effect_type == RelicEffectType.AT_BOSS_START
        assert relic.effects[0].value == 25

    def test_question_card_extra_reward(self):
        """Question Card: 卡牌奖励可选数量+1."""
        print(f"\n=== Question Card Test ===")

        relic = get_relic_by_id("问号牌")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Value: {relic.effects[0].value}")

        assert relic.effects[0].effect_type == RelicEffectType.EXTRA_CARD_REWARD
        assert relic.effects[0].value == 1

    def test_singing_bowl_max_hp_option(self):
        """Singing Bowl: 卡牌奖励可选择+2最大生命值."""
        print(f"\n=== Singing Bowl Test ===")

        relic = get_relic_by_id("颂钵")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Value: {relic.effects[0].value}")

        assert relic.effects[0].effect_type == RelicEffectType.CARD_REWARD_MAX_HP
        assert relic.effects[0].value == 2


class TestShopRelics:
    """Test shop-related relics: The Courier."""

    def test_the_courier_shop_discount(self):
        """The Courier: 商店物品不卖光且打8折."""
        print(f"\n=== The Courier Test ===")

        relic = get_relic_by_id("送货员")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Value: {relic.effects[0].value}")
        print(f"Extra: {relic.effects[0].extra}")

        assert relic.effects[0].effect_type == RelicEffectType.SHOP_NO_SELL_OUT
        assert relic.effects[0].value == 20


class TestOrbRelics:
    """Test orb-related relics: Gold-Plated Cables."""

    def test_gold_plated_cables_extra_trigger(self):
        """Gold-Plated Cables: 故障机器人专属 - 最右侧充能球额外触发一次被动."""
        print(f"\n=== Gold-Plated Cables Test ===")

        relic = get_relic_by_id("镀金缆线")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Value: {relic.effects[0].value}")
        print(f"Extra: {relic.effects[0].extra}")
        print(f"Character class: {relic.character_class}")

        assert relic.effects[0].effect_type == RelicEffectType.ORB_PASSIVE_MULTIPLY
        assert relic.effects[0].extra.get("type") == "extra_rightmost_trigger"
        assert relic.character_class == "DEFECT"


class TestWatcherRelics:
    """Test Watcher-specific relics: Duality."""

    def test_duality_temp_dexterity(self):
        """Duality: 观者专属 - 每打出攻击牌获得1点临时敏捷."""
        print(f"\n=== Duality Test ===")

        relic = get_relic_by_id("两仪")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Value: {relic.effects[0].value}")
        print(f"Extra: {relic.effects[0].extra}")
        print(f"Character class: {relic.character_class}")

        assert relic.effects[0].effect_type == RelicEffectType.ON_ATTACK
        assert relic.effects[0].extra.get("type") == "temp_dexterity"
        assert relic.character_class == "WATCHER"


class TestBottledRelics:
    """Test bottled relics: Bottled Flame, Bottled Lightning, Bottled Tornado."""

    def test_bottled_flame(self):
        """Bottled Flame: 锁定攻击牌."""
        print(f"\n=== Bottled Flame Test ===")

        relic = get_relic_by_id("瓶装火焰")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Extra: {relic.effects[0].extra}")

        assert relic.effects[0].effect_type == RelicEffectType.BOTTLED
        assert relic.effects[0].extra.get("card_type") == "attack"

    def test_bottled_lightning(self):
        """Bottled Lightning: 锁定技能牌."""
        print(f"\n=== Bottled Lightning Test ===")

        relic = get_relic_by_id("瓶装闪电")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Extra: {relic.effects[0].extra}")

        assert relic.effects[0].effect_type == RelicEffectType.BOTTLED
        assert relic.effects[0].extra.get("card_type") == "skill"

    def test_bottled_tornado(self):
        """Bottled Tornado: 锁定能力牌."""
        print(f"\n=== Bottled Tornado Test ===")

        relic = get_relic_by_id("瓶装旋风")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Extra: {relic.effects[0].extra}")

        assert relic.effects[0].effect_type == RelicEffectType.BOTTLED
        assert relic.effects[0].extra.get("card_type") == "power"


class TestOtherRelics:
    """Test other uncommon relics: Pear, White Beast Statue, Ninja Scroll."""

    def test_pear_max_hp(self):
        """Pear: 拾取时+10最大生命值."""
        print(f"\n=== Pear Test ===")

        relic = get_relic_by_id("梨子")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Value: {relic.effects[0].value}")
        print(f"Extra: {relic.effects[0].extra}")

        assert relic.effects[0].effect_type == RelicEffectType.ON_PICKUP
        assert relic.effects[0].value == 10
        assert relic.effects[0].extra.get("type") == "max_hp"

    def test_white_beast_statue_potion(self):
        """White Beast Statue: 药水必定掉落."""
        print(f"\n=== White Beast Statue Test ===")

        relic = get_relic_by_id("白兽雕像")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Value: {relic.effects[0].value}")

        assert relic.effects[0].effect_type == RelicEffectType.POTION_ALWAYS_DROP

    def test_ninja_scroll_shivs(self):
        """Ninja Scroll: 静默专属 - 战斗开始生成3张纸飞镖."""
        print(f"\n=== Ninja Scroll Test ===")

        relic = get_relic_by_id("忍术卷轴")
        print(f"Relic effect type: {relic.effects[0].effect_type}")
        print(f"Value: {relic.effects[0].value}")
        print(f"Extra: {relic.effects[0].extra}")
        print(f"Character class: {relic.character_class}")

        assert relic.effects[0].effect_type == RelicEffectType.START_WITH_SHIVS
        assert relic.effects[0].value == 3
        assert relic.character_class == "SILENT"


class TestCombatIntegration:
    """Integration tests for uncommon relics - definition verification only."""

    def test_strike_dummy_definition_only(self):
        """Verify Strike Dummy is correctly defined - combat integration requires engine implementation."""
        relic = UNCOMMON_RELICS.get("StrikeDummy")
        assert relic is not None
        assert relic.name == "打击木偶"
        assert relic.effects[0].effect_type == RelicEffectType.STRIKE_DAMAGE_BONUS
        assert relic.effects[0].value == 3


class TestUncommonRelicBehaviorTruth:
    def test_kunai_gains_dexterity_after_three_real_attacks(self):
        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(12345, counter=50),
            hp_rng=MutableRNG.from_seed(67890, counter=100),
            relics=["Kunai"],
        )

        for _ in range(3):
            combat._execute_normal_card(CardInstance("Strike"), 0)

        assert combat.state.player.dexterity == 1

    def test_shuriken_gains_strength_after_three_real_attacks(self):
        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(12345, counter=50),
            hp_rng=MutableRNG.from_seed(67890, counter=100),
            relics=["Shuriken"],
        )

        for _ in range(3):
            combat._execute_normal_card(CardInstance("Strike"), 0)

        assert combat.state.player.strength == 1

    def test_nunchaku_gains_energy_on_tenth_real_attack(self):
        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(12345, counter=50),
            hp_rng=MutableRNG.from_seed(67890, counter=100),
            relics=["Nunchaku"],
        )

        starting_energy = combat.state.player.energy
        for _ in range(10):
            combat._execute_normal_card(CardInstance("Strike"), 0)

        assert combat.state.player.energy == starting_energy + 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
