"""普通遗物效果全面审查测试."""
from __future__ import annotations

import pytest
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.run.run_engine import RunEngine
from sts_py.engine.content.relics import (
    COMMON_RELICS, RelicEffectType, get_relic_by_id
)


class TestCommonRelicInventory:
    """盘点所有普通遗物."""

    def test_all_common_relics_defined(self):
        """验证普通遗物数量和定义."""
        print(f"\n{'='*60}")
        print("COMMON RELICS INVENTORY")
        print(f"{'='*60}")
        print(f"Total: {len(COMMON_RELICS)}")

        for relic_id in sorted(COMMON_RELICS.keys()):
            relic = COMMON_RELICS[relic_id]
            effects_str = ", ".join([e.effect_type.value for e in relic.effects])
            char_limit = f" ({relic.character_class})" if relic.character_class else ""
            print(f"  {relic_id}{char_limit}: [{effects_str}]")

        assert len(COMMON_RELICS) >= 35, f"Should have at least 35 common relics"


class TestBattleStartRelics:
    """测试战斗开始时触发的遗物."""

    def test_iron_anchor(self):
        """Iron Anchor: Battle start gain 10 block."""
        ai_rng = MutableRNG.from_seed(12345, counter=0)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
            relics=["铁锚"],
        )

        print(f"\n[Iron Anchor] Block after battle start: {combat.state.player.block}")
        assert combat.state.player.block == 10, f"Expected 10 block, got {combat.state.player.block}"

    def test_vajra(self):
        """Vajra: Battle start gain 1 strength."""
        ai_rng = MutableRNG.from_seed(12345, counter=0)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
            relics=["金刚杵"],
        )

        print(f"\n[Vajra] Strength after battle start: {combat.state.player.strength}")
        assert combat.state.player.strength == 1, f"Expected 1 strength, got {combat.state.player.strength}"

    def test_bag_of_marbles(self):
        """Bag of Marbles: Battle start apply 1 vulnerable to all enemies."""
        ai_rng = MutableRNG.from_seed(12345, counter=0)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="2 Louse",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
            relics=["弹珠袋"],
        )

        for i, monster in enumerate(combat.state.monsters):
            vuln = monster.powers.get_power_amount('Vulnerable')
            print(f"\n[Bag of Marbles] Monster {i} ({monster.id}) vulnerable: {vuln}")
            assert vuln == 1, f"Monster should have 1 vulnerable, got {vuln}"

    def test_smooth_stone(self):
        """Smooth Stone: Battle start gain 1 dexterity."""
        ai_rng = MutableRNG.from_seed(12345, counter=0)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
            relics=["意外光滑的石头"],
        )

        print(f"\n[Smooth Stone] Dexterity after battle start: {combat.state.player.dexterity}")
        assert combat.state.player.dexterity == 1, f"Expected 1 dexterity, got {combat.state.player.dexterity}"

    def test_lantern(self):
        """Lantern: Battle first turn gain 1 energy."""
        ai_rng = MutableRNG.from_seed(12345, counter=0)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
            relics=["灯笼"],
        )

        print(f"\n[Lantern] Energy after battle start: {combat.state.player.energy}")
        print(f"[Lantern] Max energy: {combat.state.player.max_energy}")
        assert combat.state.player.energy == combat.state.player.max_energy + 1, \
            f"Expected {combat.state.player.max_energy + 1} energy, got {combat.state.player.energy}"

    def test_bag_of_preparation(self):
        """Bag of Preparation: Battle start draw 2 extra cards."""
        ai_rng = MutableRNG.from_seed(12345, counter=0)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
            relics=["准备背包"],
        )

        hand_size = len(combat.state.card_manager.hand.cards)
        print(f"\n[Bag of Preparation] Hand size after battle start: {hand_size}")
        assert hand_size == 7, f"Expected 7 cards, got {hand_size}"


class TestFirstAttackRelics:
    """测试第一张攻击牌触发的遗物."""

    def test_akabeko(self):
        """Akabeko: First attack deals extra 8 damage."""
        ai_rng = MutableRNG.from_seed(12345, counter=0)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
            relics=["赤牛"],
        )

        initial_hp = combat.state.monsters[0].hp
        print(f"\n[Akabeko] Monster initial HP: {initial_hp}")

        # Find and play Strike
        strike_idx = None
        for i, card in enumerate(combat.state.card_manager.hand.cards):
            if "Strike" in card.card_id:
                strike_idx = i
                break

        assert strike_idx is not None, "Strike card not found"

        combat.play_card(strike_idx, target_idx=0)
        combat.end_player_turn()

        final_hp = combat.state.monsters[0].hp
        damage = initial_hp - final_hp
        print(f"[Akabeko] Damage dealt: {damage}")
        assert damage == 14, f"Expected 14 damage (6 base + 8 bonus), got {damage}"


class TestRelicImplementationStatus:
    """遗物效果实现状态报告."""

    def test_generate_implementation_report(self):
        """生成遗物效果实现状态报告."""
        print(f"\n{'='*60}")
        print("RELIC IMPLEMENTATION STATUS REPORT")
        print(f"{'='*60}")

        # Implemented extra types for AT_BATTLE_START
        implemented_battle_start_types = [
            "block", "strength", "draw", "vulnerable", "weak", "energy", "dexterity"
        ]

        implemented_count = 0
        unimplemented_count = 0

        for relic_id in sorted(COMMON_RELICS.keys()):
            relic = COMMON_RELICS[relic_id]
            if not relic.effects:
                print(f"\n[WARN] {relic_id}: No effects defined")
                unimplemented_count += 1
                continue

            effect = relic.effects[0]
            effect_type = effect.effect_type.value
            extra_type = effect.extra.get("type", "") if effect.extra else ""

            # Check if implemented
            is_implemented = False
            if effect_type == "at_battle_start":
                if extra_type in implemented_battle_start_types:
                    is_implemented = True

            if is_implemented:
                status = "[OK]"
                implemented_count += 1
            else:
                status = "[X]"
                unimplemented_count += 1

            char_info = f" ({relic.character_class})" if relic.character_class else ""
            print(f"\n{status} {relic_id}{char_info}")
            print(f"    Effect type: {effect_type}")
            print(f"    Extra type: {extra_type}")
            print(f"    Value: {effect.value}")

        print(f"\n{'='*60}")
        print(f"SUMMARY: [OK] {implemented_count}, [X] {unimplemented_count}")
        print(f"{'='*60}")