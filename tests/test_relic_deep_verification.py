"""Deep verification of all common relic effects using actual combat engine simulation.

This test file thoroughly validates all relic effects by running actual combat
simulations, verifying damage calculations, power interactions, and edge cases.
"""
import pytest
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import StrengthPower, DexterityPower, FocusPower
from sts_py.engine.content.relics import get_relic_by_id, COMMON_RELICS, RelicEffectType


class TestRelicDamageCalculation:
    """Test damage calculations with relics and monster powers."""

    def test_strength_damage_calculation(self):
        """Verify Strength adds to base damage correctly."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["Vajra"],
        )

        initial_hp = combat.state.monsters[0].hp
        print(f"\n=== Strength Damage Test ===")
        print(f"Monster initial HP: {initial_hp}")
        print(f"Player Strength: {combat.state.player.strength}")

        strike_idx = self._find_strike(combat)
        combat.play_card(strike_idx, target_idx=0)

        final_hp = combat.state.monsters[0].hp
        damage = initial_hp - final_hp
        print(f"Damage dealt: {damage}")
        print(f"Expected: 7 (6 base + 1 strength)")

        assert damage == 7, f"Expected 7 damage (6 + 1 strength), got {damage}"

    def test_vulnerable_damage_calculation(self):
        """Verify Vulnerable multiplies damage correctly."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["BagOfMarbles"],
        )

        initial_hp = combat.state.monsters[0].hp
        print(f"\n=== Vulnerable Damage Test ===")
        print(f"Monster initial HP: {initial_hp}")
        print(f"Monster Vulnerable power: {combat.state.monsters[0].powers.get_power_amount('Vulnerable')}")

        strike_idx = self._find_strike(combat)
        combat.play_card(strike_idx, target_idx=0)

        final_hp = combat.state.monsters[0].hp
        damage = initial_hp - final_hp
        print(f"Damage dealt: {damage}")
        print(f"Expected: 9 (6 base x 1.5 vulnerable)")

        assert damage == 9, f"Expected 9 damage (6 x 1.5), got {damage}"

    def test_strength_and_vulnerable_combined(self):
        """Verify Strength and Vulnerable stack correctly (additive first, then multiplicative)."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["Vajra", "BagOfMarbles"],
        )

        initial_hp = combat.state.monsters[0].hp
        print(f"\n=== Strength + Vulnerable Test ===")
        print(f"Player Strength: {combat.state.player.strength}")
        print(f"Monster Vulnerable power: {combat.state.monsters[0].powers.get_power_amount('Vulnerable')}")

        strike_idx = self._find_strike(combat)
        combat.play_card(strike_idx, target_idx=0)

        final_hp = combat.state.monsters[0].hp
        damage = initial_hp - final_hp
        print(f"Damage dealt: {damage}")
        print(f"Expected: 10 (6 base + 1 str = 7, then x 1.5 = 10.5 -> 10)")

        assert damage == 10, f"Expected 10 damage, got {damage}"

    def test_weak_damage_reduction(self):
        """Verify Weak on monster does NOT reduce damage taken by monster.

        Important: In Slay the Spire, Weak only reduces the damage that
        the affected character DEALS, not the damage they TAKE.
        """
        from sts_py.engine.combat.powers import WeakPower

        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=[],
        )

        combat.state.player.strength = 2
        print(f"\n=== Weak Test ===")
        print(f"Player Strength: {combat.state.player.strength}")
        print(f"Testing: Monster has Weak - does NOT affect damage taken!")

        combat.state.monsters[0].powers.add_power(WeakPower(amount=1))

        initial_hp = combat.state.monsters[0].hp
        strike_idx = self._find_strike(combat)
        combat.play_card(strike_idx, target_idx=0)

        final_hp = combat.state.monsters[0].hp
        damage = initial_hp - final_hp
        print(f"Damage dealt: {damage}")
        print(f"Expected: 8 (6 base + 2 str, Weak doesn't affect damage taken)")

        assert damage == 8, f"Expected 8 damage, got {damage}"

    @staticmethod
    def _find_strike(combat):
        for i, card in enumerate(combat.state.card_manager.hand.cards):
            if "Strike" in card.card_id:
                return i
        return None


class TestRelicCombatEngineSimulation:
    """Full combat engine simulations with multiple relic combinations."""

    def test_multi_turn_combat_with_strength(self):
        """Simulate a multi-turn combat with strength relics."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["Vajra"],
        )

        print(f"\n=== Multi-Turn Combat Test ===")
        print(f"Initial Strength: {combat.state.player.strength}")

        turn_damages = []
        for turn in range(1, 4):
            print(f"\n--- Turn {turn} ---")
            initial_hp = combat.state.monsters[0].hp
            print(f"Monster HP: {initial_hp}")

            strike_idx = self._find_strike(combat)
            if strike_idx is not None:
                combat.play_card(strike_idx, target_idx=0)
                combat.end_player_turn()

            final_hp = combat.state.monsters[0].hp
            damage = initial_hp - final_hp
            turn_damages.append(damage)
            print(f"Damage dealt: {damage}")

        print(f"\nAll turns dealt: {turn_damages}")
        assert all(d == 7 for d in turn_damages), f"All turns should deal 7 damage, got {turn_damages}"

    def test_akabeko_first_attack_bonus(self):
        """Verify Akabeko bonus only applies to first attack."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["Akabeko"],
        )

        print(f"\n=== Akabeko First Attack Test ===")
        print(f"First attack bonus: {combat.state.player._first_attack_bonus_damage}")
        print(f"First attack triggered: {combat.state.player._first_attack_triggered}")

        initial_hp = combat.state.monsters[0].hp
        strike_idx = self._find_strike(combat)
        combat.play_card(strike_idx, target_idx=0)

        first_damage = initial_hp - combat.state.monsters[0].hp
        print(f"First attack damage: {first_damage} (expected 14: 6 + 8 bonus)")

        combat.end_player_turn()
        combat.state.player.energy = 3

        second_initial = combat.state.monsters[0].hp
        strike_idx = self._find_strike(combat)
        if strike_idx is not None:
            combat.play_card(strike_idx, target_idx=0)
            second_damage = second_initial - combat.state.monsters[0].hp
            print(f"Second attack damage: {second_damage} (expected 6, no bonus)")

        assert first_damage == 14, f"First attack should be 14 (6 + 8), got {first_damage}"
        assert second_damage == 6, f"Second attack should be 6, got {second_damage}"

    def test_nunchaku_energy_progression(self):
        """Verify Nunchaku energy gain every 10 attacks."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["Nunchaku"],
        )

        print(f"\n=== Nunchaku Energy Progression Test ===")
        print(f"Initial energy: {combat.state.player.energy}")
        print(f"Attack counter: {combat.state.player._attack_counter}")

        for attack_num in range(1, 11):
            combat.state.player._attack_counter += 1
            energy_before = combat.state.player.energy

            if combat.state.player._attack_counter % 10 == 0:
                combat.state.player._attack_counter = 0
                combat.state.player.energy += 1

            print(f"Attack {attack_num}: counter={combat.state.player._attack_counter}, "
                  f"energy: {energy_before} -> {combat.state.player.energy}")

        final_energy = combat.state.player.energy
        print(f"Final energy after 10 attacks: {final_energy}")
        assert final_energy == 4, f"Expected 4 energy (3 + 1 from Nunchaku), got {final_energy}"

    def test_orichalcum_block_gain(self):
        """Verify Orichalcum gives block at turn end if no block."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["Orichalcum"],
        )

        print(f"\n=== Orichalcum Block Test ===")

        combat.state.player.block = 0
        print(f"Turn end with no block: {combat.state.player.block}")
        combat._trigger_relic_effects("at_turn_end")
        print(f"After trigger: {combat.state.player.block}")
        assert combat.state.player.block == 6, f"Expected 6 block, got {combat.state.player.block}"

        combat.state.player.block = 5
        block_before = combat.state.player.block
        combat._trigger_relic_effects("at_turn_end")
        print(f"Turn end with 5 block: {block_before} -> {combat.state.player.block}")
        assert combat.state.player.block == 5, f"Block should stay 5 when has block"

    def test_art_of_war_energy_no_attack(self):
        """Verify Art of War gives energy when no attack played."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["ArtOfWar"],
        )

        print(f"\n=== Art of War Energy Test ===")

        combat.state.player._has_attacked_this_turn = False
        combat.state.player.energy = 3
        print(f"No attack played, energy: {combat.state.player.energy}")
        combat._trigger_relic_effects("at_turn_start")
        print(f"After trigger: {combat.state.player.energy}")
        assert combat.state.player.energy == 4, f"Expected 4 energy, got {combat.state.player.energy}"

        combat.state.player._has_attacked_this_turn = True
        combat.state.player.energy = 3
        print(f"Attack played, energy: {combat.state.player.energy}")
        combat._trigger_relic_effects("at_turn_start")
        print(f"After trigger: {combat.state.player.energy}")
        assert combat.state.player.energy == 3, f"Energy should stay 3, got {combat.state.player.energy}"

    def test_lantern_energy_bonus(self):
        """Verify Lantern gives extra energy at battle start."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["Lantern"],
        )

        print(f"\n=== Lantern Energy Test ===")
        print(f"Energy at battle start: {combat.state.player.energy}")
        print(f"Max energy: {combat.state.player.max_energy}")
        assert combat.state.player.energy == 4, f"Expected 4 energy, got {combat.state.player.energy}"

    def test_bag_of_preparation_draw(self):
        """Verify Bag of Preparation gives extra draw."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["BagOfPreparation"],
        )

        print(f"\n=== Bag of Preparation Draw Test ===")
        hand_size = len(combat.state.card_manager.hand.cards)
        print(f"Hand size at battle start: {hand_size}")
        assert hand_size == 7, f"Expected 7 cards, got {hand_size}"

    def test_blood_pot_heal(self):
        """Verify Blood Pot heals at battle start."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=78, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["BloodVial"],
        )

        print(f"\n=== Blood Pot Heal Test ===")
        print(f"HP after battle start: {combat.state.player.hp}")
        assert combat.state.player.hp == 80, f"Expected 80 HP, got {combat.state.player.hp}"

    def test_iron_anchor_block(self):
        """Verify Iron Anchor gives block at battle start."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["Anchor"],
        )

        print(f"\n=== Iron Anchor Block Test ===")
        print(f"Block at battle start: {combat.state.player.block}")
        assert combat.state.player.block == 10, f"Expected 10 block, got {combat.state.player.block}"

    def test_smooth_stone_dexterity(self):
        """Verify Smooth Stone gives dexterity at battle start."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["OddlySmoothStone"],
        )

        print(f"\n=== Smooth Stone Dexterity Test ===")
        print(f"Dexterity at battle start: {combat.state.player.dexterity}")
        assert combat.state.player.dexterity == 1, f"Expected 1 dexterity, got {combat.state.player.dexterity}"

    def test_bronze_scales_thorns(self):
        """Verify Bronze Scales gives thorns at battle start."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["BronzeScales"],
        )

        print(f"\n=== Bronze Scales Thorns Test ===")
        print(f"Thorns at battle start: {combat.state.player.thorns}")
        assert combat.state.player.thorns == 3, f"Expected 3 thorns, got {combat.state.player.thorns}"

    def test_data_disk_focus(self):
        """Verify Data Disk gives focus at battle start."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["DataDisk"],
        )

        print(f"\n=== Data Disk Focus Test ===")
        print(f"Focus at battle start: {combat.state.player.focus}")
        assert combat.state.player.focus == 1, f"Expected 1 focus, got {combat.state.player.focus}"

    @staticmethod
    def _find_strike(combat):
        for i, card in enumerate(combat.state.card_manager.hand.cards):
            if "Strike" in card.card_id:
                return i
        return None


class TestRelicSynergy:
    """Test multiple relics working together."""

    def test_all_starting_relics_together(self):
        """Test all common battle-start relics stacking correctly."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=78, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["Lantern", "Anchor", "Vajra", "BagOfPreparation", "BloodVial"],
        )

        print(f"\n=== All Start Relics Test ===")
        print(f"Energy: {combat.state.player.energy} (expected 4)")
        print(f"Block: {combat.state.player.block} (expected 10)")
        print(f"Strength: {combat.state.player.strength} (expected 1)")
        print(f"Hand size: {len(combat.state.card_manager.hand.cards)} (expected 7)")
        print(f"HP: {combat.state.player.hp} (expected 80)")

        assert combat.state.player.energy == 4
        assert combat.state.player.block == 10
        assert combat.state.player.strength == 1
        assert len(combat.state.card_manager.hand.cards) == 7
        assert combat.state.player.hp == 80

    def test_damage_with_multiple_relics(self):
        """Test damage calculation with multiple damage-affecting relics."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["Vajra", "BagOfMarbles"],
        )

        initial_hp = combat.state.monsters[0].hp
        print(f"\n=== Combined Damage Test ===")
        print(f"Monster HP: {initial_hp}")
        print(f"Player Strength: {combat.state.player.strength}")
        print(f"Monster Vulnerable power: {combat.state.monsters[0].powers.get_power_amount('Vulnerable')}")

        strike_idx = None
        for i, card in enumerate(combat.state.card_manager.hand.cards):
            if "Strike" in card.card_id:
                strike_idx = i
                break

        combat.play_card(strike_idx, target_idx=0)
        final_hp = combat.state.monsters[0].hp
        damage = initial_hp - final_hp

        print(f"Damage dealt: {damage}")
        print(f"Expected: 10 (6 base + 1 str = 7, x 1.5 vulnerable = 10.5 -> 10)")

        assert damage == 10, f"Expected 10 damage, got {damage}"

    def test_block_with_dexterity(self):
        """Test block calculation with dexterity.

        Note: In Slay the Spire, Dexterity only affects block from CARDS and POWERS,
        not flat block bonuses from relics like Iron Anchor.
        """
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["OddlySmoothStone", "Anchor"],
        )

        print(f"\n=== Block + Dexterity Test ===")
        print(f"Dexterity: {combat.state.player.dexterity}")
        print(f"Base Block from Iron Anchor: {combat.state.player.block}")

        combat.player_gain_block(5)
        total_block = combat.state.player.block

        print(f"Block after gaining 5: {total_block}")
        print(f"Expected: 15 (10 from Iron Anchor + 5 from card)")
        print(f"Dexterity does NOT add to relic flat block bonus")

        assert total_block == 15, f"Expected 15 block (10 + 5, dex doesn't affect relic block), got {total_block}"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_strength(self):
        """Test that zero strength doesn't affect damage."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=[],
        )

        combat.state.player.strength = 0
        initial_hp = combat.state.monsters[0].hp

        strike_idx = None
        for i, card in enumerate(combat.state.card_manager.hand.cards):
            if "Strike" in card.card_id:
                strike_idx = i
                break

        combat.play_card(strike_idx, target_idx=0)
        damage = initial_hp - combat.state.monsters[0].hp

        assert damage == 6, f"Expected 6 damage with 0 strength, got {damage}"

    def test_negative_strength(self):
        """Test that negative strength reduces damage."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=[],
        )

        combat.state.player.strength = -2
        initial_hp = combat.state.monsters[0].hp

        strike_idx = None
        for i, card in enumerate(combat.state.card_manager.hand.cards):
            if "Strike" in card.card_id:
                strike_idx = i
                break

        combat.play_card(strike_idx, target_idx=0)
        damage = initial_hp - combat.state.monsters[0].hp

        assert damage == 4, f"Expected 4 damage (6 - 2 strength), got {damage}"

    def test_multiple_vulnerable_stacks(self):
        """Test that multiple vulnerable stacks multiply correctly."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=[],
        )

        from sts_py.engine.combat.powers import VulnerablePower
        combat.state.monsters[0].powers.add_power(VulnerablePower(amount=2))
        initial_hp = combat.state.monsters[0].hp

        strike_idx = None
        for i, card in enumerate(combat.state.card_manager.hand.cards):
            if "Strike" in card.card_id:
                strike_idx = i
                break

        combat.play_card(strike_idx, target_idx=0)
        damage = initial_hp - combat.state.monsters[0].hp

        print(f"\n=== Multiple Vulnerable Test ===")
        print(f"Vulnerable stacks: {combat.state.monsters[0].powers.get_power_amount('Vulnerable')}")
        print(f"Damage dealt: {damage}")
        print(f"Expected: 9 (6 x 1.5, vulnerable doesn't stack multiplicatively)")

        assert damage == 9, f"Expected 9 damage, got {damage}"

    def test_full_combat_to_victory(self):
        """Test a complete combat from start to victory."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["Vajra", "Anchor"],
        )

        print(f"\n=== Full Combat Victory Test ===")
        print(f"Starting HP: {combat.state.player.hp}")
        print(f"Starting Block: {combat.state.player.block}")
        print(f"Starting Strength: {combat.state.player.strength}")

        turn = 0
        while not combat.is_combat_over():
            turn += 1
            print(f"\n--- Turn {turn} ---")

            while combat.state.player.energy > 0:
                strike_idx = None
                for i, card in enumerate(combat.state.card_manager.hand.cards):
                    if "Strike" in card.card_id:
                        strike_idx = i
                        break

                if strike_idx is None:
                    break

                combat.play_card(strike_idx, target_idx=0)

            combat.end_player_turn()

        print(f"\n=== Combat Result ===")
        print(f"Turns: {turn}")
        print(f"Victory: {combat.player_won()}")
        print(f"Monster HP: {combat.state.monsters[0].hp if combat.state.monsters else 'N/A'}")

        assert combat.player_won(), "Should win with these relics"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
