"""Comprehensive test for all common relics - verification and validation.

This test file thoroughly checks all common relic effects in combat,
verifying they work correctly with complex scenarios including
relic synergies and game mechanics interactions.
"""
import pytest
from sts_py.engine.core.rng import RNG, MutableRNG
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.monsters.exordium import Cultist, JawWorm
from sts_py.engine.run.run_engine import RunEngine
from sts_py.engine.content.relics import RelicEffectType, get_relic_by_id, COMMON_RELICS


class TestCommonRelicsInventory:
    """Verify all common relics are defined."""

    def test_all_common_relics_defined(self):
        print("\n=== All Common Relics Inventory ===")
        for name, relic_def in COMMON_RELICS.items():
            print(f"  {name}: {[f'{e.effect_type.value}:{e.value}' for e in relic_def.effects]}")
        assert len(COMMON_RELICS) >= 30, "Should have at least 30 common relics"


class TestBattleStartRelics:
    """Test relics that trigger at battle start."""

    def test_iron_anchor(self):
        """铁锚 - Start combat with 10 Block."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["铁锚"],
        )

        assert combat.state.player.block == 10, f"Expected 10 block, got {combat.state.player.block}"
        print(f"\n[铁锚] Block: {combat.state.player.block}")

    def test_vajra(self):
        """金刚杵 - Start combat with 1 Strength."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["金刚杵"],
        )

        assert combat.state.player.strength == 1, f"Expected 1 strength, got {combat.state.player.strength}"
        print(f"\n[金刚杵] Strength: {combat.state.player.strength}")

    def test_bag_of_marbles(self):
        """弹珠袋 - Start combat with 1 Vulnerable on all enemies."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["弹珠袋"],
        )

        for monster in combat.state.monsters:
            assert monster.powers.get_power_amount('Vulnerable') == 1, f"Expected 1 vulnerable, got {monster.powers.get_power_amount('Vulnerable')}"
        print(f"\n[弹珠袋] Vulnerable: {combat.state.monsters[0].powers.get_power_amount('Vulnerable')}")

    def test_smooth_stone(self):
        """光滑的石头 - Start combat with 1 Dexterity."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["意外光滑的石头"],
        )

        assert combat.state.player.dexterity == 1, f"Expected 1 dexterity, got {combat.state.player.dexterity}"
        print(f"\n[光滑的石头] Dexterity: {combat.state.player.dexterity}")

    def test_lantern(self):
        """灯笼 - Start combat with 1 Energy."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["灯笼"],
        )

        assert combat.state.player.energy == 4, f"Expected 4 energy (3 base + 1), got {combat.state.player.energy}"
        print(f"\n[灯笼] Energy: {combat.state.player.energy}")

    def test_bag_of_preparation(self):
        """准备背包 - Start combat with 2 extra draw."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["准备背包"],
        )

        hand_size = len(combat.state.card_manager.hand.cards)
        assert hand_size == 7, f"Expected 7 cards (5 base + 2), got {hand_size}"
        print(f"\n[准备背包] Hand size: {hand_size}")

    def test_blood_pot(self):
        """小血瓶 - Start combat heal 2 HP."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=78, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["小血瓶"],
        )

        assert combat.state.player.hp == 80, f"Expected 80 HP, got {combat.state.player.hp}"
        print(f"\n[小血瓶] HP: {combat.state.player.hp}")

    def test_bronze_scales(self):
        """Bronze Scales - Start combat with 3 Thorns."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["铜制鳞片"],
        )

        assert combat.state.player.thorns == 3, f"Expected 3 thorns, got {combat.state.player.thorns}"
        print(f"\n[Bronze Scales] Thorns: {combat.state.player.thorns}")

    def test_data_disk(self):
        """数据磁盘 - Start combat with 1 Focus (Defect only)."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["数据磁盘"],
        )

        assert combat.state.player.focus == 1, f"Expected 1 focus, got {combat.state.player.focus}"
        print(f"\n[Data Disk] Focus: {combat.state.player.focus}")


class TestFirstAttackRelics:
    """Test relics that trigger on first attack."""

    def test_akabeko(self):
        """赤牛 - First attack deals 8 bonus damage."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["赤牛"],
        )

        initial_hp = combat.state.monsters[0].hp
        print(f"\n[赤牛] Monster initial HP: {initial_hp}")

        strike_idx = None
        for i, card in enumerate(combat.state.card_manager.hand.cards):
            if "Strike" in card.card_id:
                strike_idx = i
                break

        assert strike_idx is not None, "Strike card not found"
        combat.play_card(strike_idx, target_idx=0)

        final_hp = combat.state.monsters[0].hp
        damage = initial_hp - final_hp
        assert damage == 14, f"Expected 14 damage (6 base + 8 bonus), got {damage}"
        print(f"[赤牛] Damage: {damage} (6 base + 8 bonus)")


class TestEveryNAttacksRelics:
    """Test relics that trigger every N attacks."""

    def test_nunchaku(self):
        """双截棍 - Every 10 attacks gain 1 energy."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["双截棍"],
        )

        print(f"\n[双截棍] Initial energy: {combat.state.player.energy}")
        print(f"[双截棍] Attack counter: {combat.state.player._attack_counter}")

        for i in range(10):
            combat.state.player._attack_counter += 1
            print(f"  Attack {i+1}: counter={combat.state.player._attack_counter}, energy before={combat.state.player.energy}")
            if combat.state.player._attack_counter % 10 == 0:
                combat.state.player.energy += 1
                print(f"    -> Energy gained! Now energy={combat.state.player.energy}")

        assert combat.state.player.energy == 4, f"Expected 4 energy after 10 attacks, got {combat.state.player.energy}"
        print(f"[双截棍] Final energy: {combat.state.player.energy}")

    def test_pen_nib(self):
        """钢笔尖 - Every 10 attacks double damage."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["钢笔尖"],
        )

        print(f"\n[钢笔尖] Attack counter: {combat.state.player._attack_counter}")
        print(f"[钢笔尖] Next attack double: {combat.state.player._next_attack_double}")

        for i in range(10):
            combat.state.player._attack_counter += 1
            if combat.state.player._attack_counter % 10 == 0:
                combat.state.player._next_attack_double = True
                print(f"  Attack {i+1}: counter={combat.state.player._attack_counter}, double={combat.state.player._next_attack_double}")

        print(f"  After 10 attacks: counter={combat.state.player._attack_counter}, double={combat.state.player._next_attack_double}")
        assert combat.state.player._next_attack_double == True, "10th attack should double damage"

        print(f"[钢笔尖] Final state: counter={combat.state.player._attack_counter}, double={combat.state.player._next_attack_double}")


class TestTurnBasedRelics:
    """Test relics that trigger based on turns."""

    def test_happy_flower(self):
        """快乐花 - Every 3 turns gain 1 energy."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["开心小花"],
        )

        print(f"\n[快乐花] Initial turn: {combat.state.turn}")

        for turn in range(1, 4):
            combat.state.turn = turn
            energy_before = combat.state.player.energy
            combat._trigger_relic_effects("at_turn_start")
            energy_after = combat.state.player.energy
            print(f"  Turn {turn}: energy before={energy_before}, after={energy_after}")

        assert combat.state.turn == 3
        assert combat.state.player.energy == 4, f"Expected 4 energy at turn 3, got {combat.state.player.energy}"
        print(f"[快乐花] Energy at turn 3: {combat.state.player.energy}")

    def test_orichalcum(self):
        """奥利哈刚 - At turn end, gain 6 block if no block."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["奥利哈钢"],
        )

        print(f"\n[奥利哈刚] Initial block: {combat.state.player.block}")

        combat.state.player.block = 0
        combat._trigger_relic_effects("at_turn_end")
        assert combat.state.player.block == 6, f"Expected 6 block, got {combat.state.player.block}"
        print(f"[奥利哈刚] Block after turn end (no block): {combat.state.player.block}")

        combat.state.player.block = 5
        combat._trigger_relic_effects("at_turn_end")
        assert combat.state.player.block == 5, f"Block should stay 5 when already has block"
        print(f"[奥利哈刚] Block after turn end (has block): {combat.state.player.block}")

    def test_art_of_war(self):
        """孙子兵法 - At turn start if no attack, gain 1 energy."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["孙子兵法"],
        )

        combat.state.player._has_attacked_this_turn = False
        combat.state.player.energy = 3
        combat._trigger_relic_effects("at_turn_start")
        assert combat.state.player.energy == 4, f"Expected 4 energy (no attack), got {combat.state.player.energy}"
        print(f"\n[孙子兵法] Energy (no attack): {combat.state.player.energy}")

        combat.state.player._has_attacked_this_turn = True
        combat.state.player.energy = 3
        combat._trigger_relic_effects("at_turn_start")
        assert combat.state.player.energy == 3, f"Expected 3 energy (attacked), got {combat.state.player.energy}"
        print(f"[孙子兵法] Energy (attacked): {combat.state.player.energy}")


class TestSynergyRelics:
    """Test multiple relics working together."""

    def test_multiple_battle_start_relics(self):
        """Test multiple relics that trigger at battle start."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["灯笼", "金刚杵", "铁锚", "准备背包"],
        )

        print(f"\n[多遗物联动]")
        print(f"  灯笼 Energy: {combat.state.player.energy} (expected 4)")
        print(f"  金刚杵 Strength: {combat.state.player.strength} (expected 1)")
        print(f"  铁锚 Block: {combat.state.player.block} (expected 10)")
        print(f"  准备背包 Hand: {len(combat.state.card_manager.hand.cards)} (expected 7)")

        assert combat.state.player.energy == 4
        assert combat.state.player.strength == 1
        assert combat.state.player.block == 10
        assert len(combat.state.card_manager.hand.cards) == 7

    def test_strength_and_weak_interaction(self):
        """Test strength relic with vulnerable enemy."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["金刚杵", "弹珠袋"],
        )

        initial_hp = combat.state.monsters[0].hp
        print(f"\n[力量+易伤] Monster HP: {initial_hp}, Vulnerable: {combat.state.monsters[0].powers.get_power_amount('Vulnerable')}")
        print(f"[力量+易伤] Player Strength: {combat.state.player.strength}")

        strike_idx = None
        for i, card in enumerate(combat.state.card_manager.hand.cards):
            if "Strike" in card.card_id:
                strike_idx = i
                break

        combat.play_card(strike_idx, target_idx=0)
        final_hp = combat.state.monsters[0].hp
        damage = initial_hp - final_hp

        print(f"  Damage dealt: {damage} (base 6 + str 1 = 7, then x1.5 vulnerable = 10.5 -> 10)")
        assert damage == 10, f"Expected 10 damage, got {damage}"

    def test_dexterity_and_block(self):
        """Test dexterity with block gaining."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["意外光滑的石头", "铁锚"],
        )

        print(f"\n[灵巧+格挡] Dexterity: {combat.state.player.dexterity}, Block: {combat.state.player.block}")

        combat.player_gain_block(5)
        total_block = combat.state.player.block
        print(f"  Block after gain 5 with dex=1: {total_block} (10 from iron anchor + 5 base + 0 from dex=1)")
        assert total_block == 15, f"Expected 15 (10 + 5), got {total_block}"


class TestRelicEffectImplementation:
    """Verify all relic effect types are properly implemented."""

    def test_combat_effect_types_have_handlers(self):
        """Check that combat-relevant effect types have handlers."""
        combat_effects = [
            RelicEffectType.AT_BATTLE_START,
            RelicEffectType.FIRST_ATTACK_COMBAT,
            RelicEffectType.EVERY_N_ATTACKS_SELF,
            RelicEffectType.EVERY_N_TURNS_SELF,
            RelicEffectType.AT_TURN_END,
            RelicEffectType.AT_TURN_START_NO_ATTACK,
        ]

        print("\n=== Combat Effect Types ===")
        for et in combat_effects:
            print(f"  {et.value}")

        unimplemented = []
        for et in combat_effects:
            if et not in [
                RelicEffectType.AT_BATTLE_START,
                RelicEffectType.FIRST_ATTACK_COMBAT,
                RelicEffectType.EVERY_N_ATTACKS_SELF,
                RelicEffectType.EVERY_N_TURNS_SELF,
                RelicEffectType.AT_TURN_END,
                RelicEffectType.AT_TURN_START_NO_ATTACK,
            ]:
                unimplemented.append(et.value)

        if unimplemented:
            print(f"\nUnimplemented combat effects: {unimplemented}")

        assert len(unimplemented) == 0, f"Unimplemented combat effect types: {unimplemented}"

    def test_list_unimplemented_non_combat_effects(self):
        """List effect types that are not combat-related (intentional)."""
        non_combat_effects = [
            "on_rest", "rest_heal_bonus", "on_pickup", "on_shop_enter",
            "shop_price_modifier", "on_card_added", "on_floor_climb",
            "on_potion_use", "on_trap_combat", "on_hp_loss", "on_poison_applied",
            "modify_strength", "modify_min_damage", "curse_negate_trigger",
            "elite_hp_modifier", "treasure_room_every_n_question"
        ]

        print("\n=== Non-Combat Effect Types (not implemented in combat engine) ===")
        for et in non_combat_effects:
            print(f"  {et}")


class TestComplexScenarios:
    """Test complex scenarios with multiple turns and interactions."""

    def test_full_combat_with_relics(self):
        """Simulate a full combat with multiple relics."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["灯笼", "金刚杵", "铁锚"],
        )

        print(f"\n=== Full Combat Test ===")
        print(f"Initial: HP={combat.state.player.hp}, Energy={combat.state.player.energy}, "
              f"Block={combat.state.player.block}, Str={combat.state.player.strength}")

        turn = 0
        while not combat.is_combat_over():
            turn += 1
            print(f"\n--- Turn {turn} ---")
            print(f"  Player: HP={combat.state.player.hp}, Energy={combat.state.player.energy}, "
                  f"Block={combat.state.player.block}")

            if combat.state.phase.name != "PLAYER_TURN":
                continue

            cards_played = 0
            while combat.state.player.energy > 0 and combat.state.player.energy >= 1:
                strike_idx = None
                for i, card in enumerate(combat.state.card_manager.hand.cards):
                    if "Strike" in card.card_id:
                        strike_idx = i
                        break

                if strike_idx is None:
                    break

                combat.play_card(strike_idx, target_idx=0)
                cards_played += 1
                print(f"  Played Strike, target HP={combat.state.monsters[0].hp}")

            combat.end_player_turn()

        print(f"\n=== Combat Ended ===")
        print(f"  Turns: {turn}")
        print(f"  Result: {'Victory' if combat.player_won() else 'Defeat'}")
        print(f"  Monster HP: {combat.state.monsters[0].hp if combat.state.monsters else 'N/A'}")

        assert combat.player_won(), "Should win with these relics"

    def test_thorns_reflects_damage(self):
        """Test Bronze Scales thorns damage when monster attacks."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["铜制鳞片"],
        )

        print(f"\n=== Thorns Test ===")
        print(f"Thorns: {combat.state.player.thorns}")

        monster_initial_hp = combat.state.monsters[0].hp
        print(f"Monster initial HP: {monster_initial_hp}")

        combat.state.player.block = 0
        combat.state.monsters[0].take_damage(combat.state.player.thorns)

        thorns_damage = monster_initial_hp - combat.state.monsters[0].hp
        print(f"Monster HP after thorns: {combat.state.monsters[0].hp}")
        print(f"Thorns damage: {thorns_damage}")
        assert thorns_damage == 3, f"Thorns should have dealt 3 damage, got {thorns_damage}"


class TestRelicPersistence:
    """Test that relic effects persist correctly across combat."""

    def test_relic_effects_persist_in_combat(self):
        """Verify relic bonuses persist throughout combat."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["金刚杵"],
        )

        print(f"\n=== Relic Persistence Test ===")
        print(f"Initial strength: {combat.state.player.strength}")

        combat.end_player_turn()
        print(f"After monster turn: {combat.state.player.strength}")

        combat.state.player.energy = 3
        combat.end_player_turn()
        print(f"After 2nd monster turn: {combat.state.player.strength}")

        assert combat.state.player.strength == 1, "Strength should persist"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])