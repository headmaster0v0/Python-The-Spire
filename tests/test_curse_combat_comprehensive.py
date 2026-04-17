"""Comprehensive combat tests for curse card effects.

This test file validates all curse card effects in actual combat scenarios,
testing interactions with powers, relics, and game mechanics.
"""
import pytest
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import IRONCLAD_CURSE_DEFS, CurseEffectType, CardType
from sts_py.engine.content.relics import get_relic_by_id
from sts_py.engine.combat.powers import FrailPower, VulnerablePower, WeakPower


class TestCurseCombatIntegration:
    """Test curse effects in actual combat scenarios."""

    def test_decay_damage_per_turn(self):
        """Decay: Take 2 damage at end of each turn."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
        )

        decay = CardInstance("Decay")
        combat.state.card_manager.hand.cards.append(decay)

        print(f"\n=== Decay Damage Per Turn Test ===")
        print(f"HP before: {combat.state.player.hp}")

        combat.state.phase = combat.state.phase.__class__.MONSTER_TURN
        combat._process_curse_effects_end_of_turn()

        print(f"HP after 1st turn: {combat.state.player.hp}")

        combat._process_curse_effects_end_of_turn()
        print(f"HP after 2nd turn: {combat.state.player.hp}")

        assert combat.state.player.hp == 76, f"Expected 76 HP (80 - 4), got {combat.state.player.hp}"

    def test_doubt_weak_effect(self):
        """Doubt: Gain 1 Weak at end of turn."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
        )

        doubt = CardInstance("Doubt")
        combat.state.card_manager.hand.cards.append(doubt)

        print(f"\n=== Doubt Weak Effect Test ===")
        print(f"Weak before: {combat.state.player.powers.get_power_amount('Weak')}")

        combat.state.phase = combat.state.phase.__class__.MONSTER_TURN
        combat._process_curse_effects_end_of_turn()

        print(f"Weak after 1st turn: {combat.state.player.powers.get_power_amount('Weak')}")
        assert combat.state.player.powers.get_power_amount('Weak') == 1

        combat._process_curse_effects_end_of_turn()
        print(f"Weak after 2nd turn: {combat.state.player.powers.get_power_amount('Weak')}")
        assert combat.state.player.powers.get_power_amount('Weak') == 2

    def test_shame_frail_effect(self):
        """Shame: Gain 1 Frail at end of turn (reduces block by 25%)."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
        )

        shame = CardInstance("Shame")
        combat.state.card_manager.hand.cards.append(shame)

        print(f"\n=== Shame Frail Effect Test ===")
        print(f"Frail before: {combat.state.player.powers.get_power_amount('Frail')}")

        combat.state.phase = combat.state.phase.__class__.MONSTER_TURN
        combat._process_curse_effects_end_of_turn()

        print(f"Frail after 1st turn: {combat.state.player.powers.get_power_amount('Frail')}")
        assert combat.state.player.powers.get_power_amount('Frail') == 1

    def test_frail_reduces_block(self):
        """Frail reduces block gained from cards by 25%."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
        )

        combat.state.player.powers.add_power(FrailPower(amount=1))

        print(f"\n=== Frail Reduces Block Test ===")
        print(f"Frail: {combat.state.player.powers.get_power_amount('Frail')}")

        defend = CardInstance("Defend")
        combat.state.card_manager.hand.cards.append(defend)

        print(f"Defend base_block: {defend.base_block}")

        defend.apply_powers(combat.state)

        print(f"Defend after apply_powers (with Frail): {defend.block}")
        print(f"Expected: 5 * 0.75 = 3.75 -> 3")

        assert defend.block == 3, f"Expected 3 block with Frail, got {defend.block}"

    def test_regret_scaling_damage(self):
        """Regret: Lose 1 HP per card in hand at end of turn."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
        )

        regret = CardInstance("Regret")
        combat.state.card_manager.hand.cards.append(regret)

        hand_size = len(combat.state.card_manager.hand.cards)
        print(f"\n=== Regret Scaling Damage Test ===")
        print(f"Hand size: {hand_size}")
        print(f"HP before: {combat.state.player.hp}")

        combat.state.phase = combat.state.phase.__class__.MONSTER_TURN
        combat._process_curse_effects_end_of_turn()

        expected_hp = 80 - hand_size
        print(f"HP after: {combat.state.player.hp}")
        print(f"Expected: 80 - {hand_size} = {expected_hp}")

        assert combat.state.player.hp == expected_hp

    def test_pain_on_card_play(self):
        """Pain: Lose 1 HP when playing other cards."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
        )

        pain = CardInstance("Pain")
        combat.state.card_manager.hand.cards.append(pain)

        combat.state.player.energy = 3

        print(f"\n=== Pain On Card Play Test ===")
        print(f"HP before: {combat.state.player.hp}")

        strike_idx = None
        for i, card in enumerate(combat.state.card_manager.hand.cards):
            if "Strike" in card.card_id:
                strike_idx = i
                break

        if strike_idx is not None:
            combat.play_card(strike_idx, target_idx=0)
            print(f"HP after playing Strike: {combat.state.player.hp}")
            assert combat.state.player.hp == 79

            combat.state.player.energy = 3
            strike_idx = None
            for i, card in enumerate(combat.state.card_manager.hand.cards):
                if "Strike" in card.card_id:
                    strike_idx = i
                    break

            if strike_idx is not None:
                combat.play_card(strike_idx, target_idx=0)
                print(f"HP after playing 2nd Strike: {combat.state.player.hp}")
                assert combat.state.player.hp == 78

    def test_normality_limit_cards(self):
        """Normality: When drawn, locks player from playing more cards this turn."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
        )

        combat.state.player.energy = 10
        combat.state.phase = combat.state.phase.__class__.PLAYER_TURN

        print(f"\n=== Normality Limit Cards Test ===")

        normality_card = CardInstance("Normality")
        normality_card._combat_state = combat.state
        normality_card.on_draw()
        combat.state.card_manager.hand.cards.append(normality_card)

        print(f"Normality in hand, locked: {getattr(combat.state.player, '_normality_locked', False)}")
        assert getattr(combat.state.player, '_normality_locked', False) == True

        strike_idx = None
        for j, card in enumerate(combat.state.card_manager.hand.cards):
            if "Strike" in card.card_id:
                strike_idx = j
                break

        result = combat.play_card(strike_idx, target_idx=0)
        print(f"Play Strike result: {result}")
        assert result == False, "Should not be able to play any cards after Normality is drawn"

    def test_pride_copy_at_end(self):
        """Pride: Add copy to draw pile at end of turn."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
        )

        pride = CardInstance("Pride")
        combat.state.card_manager.hand.cards.append(pride)

        draw_pile_size_before = len(combat.state.card_manager.draw_pile.cards)

        print(f"\n=== Pride Copy At End Test ===")
        print(f"Pride in hand: {pride.card_id}")
        print(f"Draw pile before: {draw_pile_size_before}")

        combat.state.phase = combat.state.phase.__class__.MONSTER_TURN
        combat._process_curse_effects_end_of_turn()

        draw_pile_size_after = len(combat.state.card_manager.draw_pile.cards)
        print(f"Draw pile after: {draw_pile_size_after}")

        pride_in_draw = any(card.card_id == "Pride" for card in combat.state.card_manager.draw_pile.cards)
        print(f"Pride in draw pile: {pride_in_draw}")

        assert pride_in_draw, "Pride copy should be added to draw pile"

    def test_vacuous_exhaust_at_end(self):
        """Vacuous curses (AscendersBane, Clumsy) exhaust at end of turn if still in hand."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
        )

        ascending = CardInstance("AscendersBane")
        clumsy = CardInstance("Clumsy")
        combat.state.card_manager.hand.cards.append(ascending)
        combat.state.card_manager.hand.cards.append(clumsy)

        hand_size_before = len(combat.state.card_manager.hand.cards)

        print(f"\n=== Vacuous Exhaust Test ===")
        print(f"Hand before: {hand_size_before}")
        print(f"AscendersBane effect: {ascending.curse_effect_type}")
        print(f"Clumsy effect: {clumsy.curse_effect_type}")

        combat.state.phase = combat.state.phase.__class__.MONSTER_TURN
        combat._process_curse_effects_end_of_turn()

        hand_size_after = len(combat.state.card_manager.hand.cards)
        print(f"Hand after: {hand_size_after}")

        assert hand_size_after == hand_size_before - 2, f"Both vacuous curses should be exhausted"
        assert len(combat.state.card_manager.exhaust_pile.cards) == 2, "Both should be in exhaust pile"

    def test_blue_candle_curse_play(self):
        """Blue Candle: Play curses for 1 HP cost."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["蓝蜡烛"],
        )

        decay = CardInstance("Decay")
        combat.state.card_manager.hand.cards.append(decay)

        print(f"\n=== Blue Candle Curse Play Test ===")
        print(f"Has Blue Candle: {combat._has_curse_playable_relic()}")
        print(f"HP before: {combat.state.player.hp}")

        decay_idx = len(combat.state.card_manager.hand.cards) - 1
        result = combat.play_card(decay_idx, target_idx=0)

        print(f"Play result: {result}")
        print(f"HP after: {combat.state.player.hp}")

        assert result == True
        assert combat.state.player.hp == 79, f"Should lose 1 HP playing curse with Blue Candle"

    def test_multiple_curses_same_turn(self):
        """Multiple curses with end-of-turn effects all trigger."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
        )

        decay = CardInstance("Decay")
        doubt = CardInstance("Doubt")
        shame = CardInstance("Shame")

        combat.state.card_manager.hand.cards.extend([decay, doubt, shame])

        print(f"\n=== Multiple Curses Test ===")
        print(f"Curses in hand: {[c.card_id for c in combat.state.card_manager.hand.cards]}")

        initial_hp = combat.state.player.hp
        combat.state.phase = combat.state.phase.__class__.MONSTER_TURN
        combat._process_curse_effects_end_of_turn()

        print(f"HP: {initial_hp} -> {combat.state.player.hp} (loss: {initial_hp - combat.state.player.hp})")
        print(f"Weak: {combat.state.player.powers.get_power_amount('Weak')}")
        print(f"Frail: {combat.state.player.powers.get_power_amount('Frail')}")

        assert combat.state.player.hp == initial_hp - 2, "Decay should deal 2 damage"
        assert combat.state.player.powers.get_power_amount('Weak') == 1, "Doubt should give 1 Weak"
        assert combat.state.player.powers.get_power_amount('Frail') == 1, "Shame should give 1 Frail"

    def test_curse_unplayable_without_relic(self):
        """Curses cannot be played without Blue Candle."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=[],
        )

        decay = CardInstance("Decay")
        combat.state.card_manager.hand.cards.append(decay)

        print(f"\n=== Curse Unplayable Test ===")
        print(f"Has Blue Candle: {combat._has_curse_playable_relic()}")

        decay_idx = len(combat.state.card_manager.hand.cards) - 1
        result = combat.play_card(decay_idx, target_idx=0)

        print(f"Play result: {result}")
        assert result == False, "Curse should not be playable without Blue Candle"

    def test_parasite_penalty_on_removal(self):
        """Parasite: If removed from deck, lose 3 max HP."""
        from sts_py.engine.run.events import _apply_parasite_penalty
        from unittest.mock import MagicMock

        print(f"\n=== Parasite Penalty Test ===")

        mock_state = MagicMock()
        mock_state.deck = ["Strike", "Defend", "Parasite"]
        mock_state.player_max_hp = 80
        mock_state.player_hp = 80

        print(f"Before removal: max_hp={mock_state.player_max_hp}, hp={mock_state.player_hp}")

        _apply_parasite_penalty(mock_state, "Parasite")

        print(f"After removal: max_hp={mock_state.player_max_hp}, hp={mock_state.player_hp}")

        assert mock_state.player_max_hp == 77, f"Should lose 3 max HP, got {mock_state.player_max_hp}"
        assert mock_state.player_hp == 77, f"HP should be capped at new max, got {mock_state.player_hp}"

    def test_parasite_no_penalty_for_normal_card(self):
        """Removing non-Parasite card should not trigger penalty."""
        from sts_py.engine.run.events import _apply_parasite_penalty
        from unittest.mock import MagicMock

        print(f"\n=== Parasite No Penalty Test ===")

        mock_state = MagicMock()
        mock_state.deck = ["Strike", "Defend"]
        mock_state.player_max_hp = 80
        mock_state.player_hp = 80

        print(f"Before removal: max_hp={mock_state.player_max_hp}")

        _apply_parasite_penalty(mock_state, "Strike")

        print(f"After removal: max_hp={mock_state.player_max_hp}")

        assert mock_state.player_max_hp == 80, f"Should not lose max HP, got {mock_state.player_max_hp}"


class TestCurseDefinitionVerification:
    """Verify all curse card definitions match game source."""

    def test_all_curses_defined(self):
        """Verify all 14 curses are defined."""
        print(f"\n=== All Curses Defined ===")
        print(f"Total curses: {len(IRONCLAD_CURSE_DEFS)}")
        for name in sorted(IRONCLAD_CURSE_DEFS.keys()):
            print(f"  - {name}")

        expected_curses = [
            "AscendersBane", "Clumsy", "CurseOfTheBell", "Decay", "Doubt",
            "Injury", "Necronomicurse", "Pain", "Normality", "Parasite",
            "Pride", "Regret", "Shame", "Writhe"
        ]

        for curse in expected_curses:
            assert curse in IRONCLAD_CURSE_DEFS, f"{curse} not found in definitions"

    def test_curse_card_types(self):
        """All curses should have CURSE card type."""
        print(f"\n=== Curse Card Types ===")
        for name, card_def in IRONCLAD_CURSE_DEFS.items():
            print(f"{name}: {card_def.card_type}")
            assert card_def.card_type == CardType.CURSE

    def test_curse_effect_types(self):
        """Verify curse effect types are correctly assigned."""
        print(f"\n=== Curse Effect Types ===")

        expected_effects = {
            "Decay": CurseEffectType.END_OF_TURN_DAMAGE,
            "Doubt": CurseEffectType.END_OF_TURN_WEAK,
            "Shame": CurseEffectType.END_OF_TURN_FRAIL,
            "Regret": CurseEffectType.REGRET_EFFECT,
            "Pain": CurseEffectType.ON_CARD_PLAYED_LOSE_HP,
            "Normality": CurseEffectType.LIMIT_CARDS_PER_TURN,
            "Parasite": CurseEffectType.IF_REMOVED_LOSE_MAX_HP,
            "Pride": CurseEffectType.INNATE_COPY_AT_END,
            "AscendersBane": CurseEffectType.VACUOUS,
            "Clumsy": CurseEffectType.VACUOUS,
            "CurseOfTheBell": CurseEffectType.CANNOT_REMOVE_FROM_DECK,
            "Necronomicurse": CurseEffectType.RETURN_TO_HAND_ON_EXHAUST,
            "Injury": CurseEffectType.NONE,
            "Writhe": CurseEffectType.NONE,
        }

        for name, expected_effect in expected_effects.items():
            actual = IRONCLAD_CURSE_DEFS[name].curse_effect_type
            print(f"{name}: {actual} (expected: {expected_effect})")
            assert actual == expected_effect, f"{name}: expected {expected_effect}, got {actual}"

    def test_curse_is_unplayable(self):
        """Most curses should be unplayable."""
        print(f"\n=== Curse Unplayable Status ===")

        playable_curses = ["Pride"]
        unplayable_curses = [
            "AscendersBane", "Clumsy", "CurseOfTheBell", "Decay", "Doubt",
            "Injury", "Necronomicurse", "Pain", "Normality", "Parasite",
            "Regret", "Shame", "Writhe"
        ]

        for name in playable_curses:
            assert IRONCLAD_CURSE_DEFS[name].is_unplayable == False, f"{name} should be playable"

        for name in unplayable_curses:
            assert IRONCLAD_CURSE_DEFS[name].is_unplayable == True, f"{name} should be unplayable"

    def test_curse_exhaust_status(self):
        """Verify exhaust status for curses."""
        print(f"\n=== Curse Exhaust Status ===")

        exhaust_curses = ["Pride"]
        non_exhaust_curses = [
            "AscendersBane", "Clumsy", "CurseOfTheBell", "Decay", "Doubt",
            "Injury", "Necronomicurse", "Pain", "Normality", "Parasite",
            "Regret", "Shame", "Writhe"
        ]

        for name in exhaust_curses:
            assert IRONCLAD_CURSE_DEFS[name].is_exhaust == True, f"{name} should exhaust"

        for name in non_exhaust_curses:
            assert IRONCLAD_CURSE_DEFS[name].is_exhaust == False, f"{name} should not exhaust"

    def test_curse_innate_status(self):
        """Verify innate status for curses."""
        print(f"\n=== Curse Innate Status ===")

        innate_curses = ["Pride", "Writhe"]

        for name in innate_curses:
            assert IRONCLAD_CURSE_DEFS[name].is_innate == True, f"{name} should be innate"

        for name, card_def in IRONCLAD_CURSE_DEFS.items():
            if name not in innate_curses:
                assert card_def.is_innate == False, f"{name} should not be innate"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
