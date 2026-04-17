"""Comprehensive test for curse cards and curse-related mechanics.

This test file validates all 15 curse cards from Slay the Spire,
their effects, and interactions with relics like Blue Candle.
"""
import pytest
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import (
    IRONCLAD_CURSE_DEFS, CurseEffectType, CardType
)
from sts_py.engine.content.relics import get_relic_by_id


class TestCurseCardDefinitions:
    """Verify all 15 curse cards are properly defined."""

    def test_curse_cards_count(self):
        """Verify we have 14 curse cards (as provided by user)."""
        print(f"\n=== Curse Cards Count ===")
        print(f"Total curse cards: {len(IRONCLAD_CURSE_DEFS)}")
        for name in sorted(IRONCLAD_CURSE_DEFS.keys()):
            print(f"  - {name}")
        assert len(IRONCLAD_CURSE_DEFS) == 14, f"Expected 14 curse cards, got {len(IRONCLAD_CURSE_DEFS)}"

    def test_all_curses_have_curse_type(self):
        """Verify all curses have CURSE card type."""
        for name, card_def in IRONCLAD_CURSE_DEFS.items():
            assert card_def.card_type == CardType.CURSE, f"{name} should be CURSE type"

    def test_curse_card_instances(self):
        """Test creating curse card instances."""
        print(f"\n=== Curse Card Instances ===")
        for card_id in IRONCLAD_CURSE_DEFS.keys():
            card = CardInstance(card_id)
            print(f"{card_id}: type={card.card_type}, is_unplayable={card.is_unplayable}")
            assert card.card_type == "CURSE"


class TestCurseCardEffects:
    """Verify curse card effect types."""

    def test_decay_effect(self):
        """Decay: End of turn damage 2."""
        card = CardInstance("Decay")
        print(f"\n=== Decay Test ===")
        print(f"Effect type: {card.curse_effect_type}")
        print(f"Effect value: {card.curse_effect_value}")
        assert card.curse_effect_type == CurseEffectType.END_OF_TURN_DAMAGE
        assert card.curse_effect_value == 2

    def test_doubt_effect(self):
        """Doubt: End of turn gain 1 Weak."""
        card = CardInstance("Doubt")
        print(f"\n=== Doubt Test ===")
        print(f"Effect type: {card.curse_effect_type}")
        print(f"Effect value: {card.curse_effect_value}")
        assert card.curse_effect_type == CurseEffectType.END_OF_TURN_WEAK
        assert card.curse_effect_value == 1

    def test_shame_effect(self):
        """Shame: End of turn gain 1 Frail (reduces block by 25%)."""
        card = CardInstance("Shame")
        print(f"\n=== Shame Test ===")
        print(f"Effect type: {card.curse_effect_type}")
        print(f"Effect value: {card.curse_effect_value}")
        assert card.curse_effect_type == CurseEffectType.END_OF_TURN_FRAIL
        assert card.curse_effect_value == 1

    def test_regret_effect(self):
        """Regret: End of turn lose 1 HP per card in hand."""
        card = CardInstance("Regret")
        print(f"\n=== Regret Test ===")
        print(f"Effect type: {card.curse_effect_type}")
        print(f"Effect value: {card.curse_effect_value}")
        assert card.curse_effect_type == CurseEffectType.REGRET_EFFECT
        assert card.curse_effect_value == 1

    def test_pain_effect(self):
        """Pain: When in hand, lose 1 HP per other card played."""
        card = CardInstance("Pain")
        print(f"\n=== Pain Test ===")
        print(f"Effect type: {card.curse_effect_type}")
        print(f"Effect value: {card.curse_effect_value}")
        assert card.curse_effect_type == CurseEffectType.ON_CARD_PLAYED_LOSE_HP
        assert card.curse_effect_value == 1

    def test_normality_effect(self):
        """Normality: Limit 3 cards per turn."""
        card = CardInstance("Normality")
        print(f"\n=== Normality Test ===")
        print(f"Effect type: {card.curse_effect_type}")
        print(f"Effect value: {card.curse_effect_value}")
        assert card.curse_effect_type == CurseEffectType.LIMIT_CARDS_PER_TURN
        assert card.curse_effect_value == 3

    def test_parasite_effect(self):
        """Parasite: If removed, lose 3 max HP."""
        card = CardInstance("Parasite")
        print(f"\n=== Parasite Test ===")
        print(f"Effect type: {card.curse_effect_type}")
        print(f"Effect value: {card.curse_effect_value}")
        assert card.curse_effect_type == CurseEffectType.IF_REMOVED_LOSE_MAX_HP
        assert card.curse_effect_value == 3

    def test_pride_effect(self):
        """Pride: Innate, Exhaust, at end of turn add copy to draw pile."""
        card = CardInstance("Pride")
        print(f"\n=== Pride Test ===")
        print(f"Effect type: {card.curse_effect_type}")
        print(f"Effect value: {card.curse_effect_value}")
        print(f"Is innate: {card.is_innate}")
        print(f"Exhaust: {card.exhaust}")
        assert card.curse_effect_type == CurseEffectType.INNATE_COPY_AT_END
        assert card.curse_effect_value == 1
        assert card.is_innate == True
        assert card.exhaust == True

    def test_curse_of_bell_effect(self):
        """CurseOfTheBell: Cannot be removed from deck, and does not exhaust."""
        card = CardInstance("CurseOfTheBell")
        print(f"\n=== Curse of the Bell Test ===")
        print(f"Effect type: {card.curse_effect_type}")
        print(f"Is exhaust: {card.exhaust}")
        assert card.curse_effect_type == CurseEffectType.CANNOT_REMOVE_FROM_DECK
        assert card.exhaust == False

    def test_necronomicurse_effect(self):
        """Necronomicurse: Returns to hand on exhaust."""
        card = CardInstance("Necronomicurse")
        print(f"\n=== Necronomicurse Test ===")
        print(f"Effect type: {card.curse_effect_type}")
        assert card.curse_effect_type == CurseEffectType.RETURN_TO_HAND_ON_EXHAUST

    def test_no_active_effect_curses(self):
        """Curses with no active combat effect (except vacuous): Injury, Writhe."""
        no_effect_curses = ["Injury", "Writhe"]
        print(f"\n=== No Active Effect Curses Test ===")
        for card_id in no_effect_curses:
            card = CardInstance(card_id)
            print(f"{card_id}: effect={card.curse_effect_type}")
            assert card.curse_effect_type == CurseEffectType.NONE

    def test_vacuous_curses(self):
        """Curses with vacuous effect (exhaust at end of turn if still in hand): AscendersBane, Clumsy."""
        vacuous_curses = ["AscendersBane", "Clumsy"]
        print(f"\n=== Vacuous Curses Test ===")
        for card_id in vacuous_curses:
            card = CardInstance(card_id)
            print(f"{card_id}: effect={card.curse_effect_type}")
            assert card.curse_effect_type == CurseEffectType.VACUOUS


class TestBlueCandleRelic:
    """Test Blue Candle relic effect."""

    def test_blue_candle_definition(self):
        """Blue Candle: Curse cards can be played."""
        relic = get_relic_by_id("蓝蜡烛")
        print(f"\n=== Blue Candle Definition ===")
        print(f"Effect type: {relic.effects[0].effect_type}")
        from sts_py.engine.content.relics import RelicEffectType
        assert relic.effects[0].effect_type == RelicEffectType.CURSE_PLAYABLE

    def test_curse_unplayable_without_relic(self):
        """Without Blue Candle, curses cannot be played."""
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
        print(f"Blue Candle check: {combat._has_curse_playable_relic()}")

        decay_idx = len(combat.state.card_manager.hand.cards) - 1
        result = combat.play_card(decay_idx, target_idx=0)
        print(f"Play Decay result: {result}")

        assert result == False, "Curse should not be playable without Blue Candle"

    def test_curse_playable_with_blue_candle(self):
        """With Blue Candle, curses can be played."""
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

        print(f"\n=== Curse Playable with Blue Candle Test ===")
        print(f"Blue Candle check: {combat._has_curse_playable_relic()}")

        initial_hp = combat.state.player.hp
        print(f"Player HP before: {initial_hp}")

        decay_idx = len(combat.state.card_manager.hand.cards) - 1
        result = combat.play_card(decay_idx, target_idx=0)
        print(f"Play Decay result: {result}")

        final_hp = combat.state.player.hp
        print(f"Player HP after: {final_hp}")
        print(f"HP lost: {initial_hp - final_hp}")

        assert result == True, "Curse should be playable with Blue Candle"
        assert initial_hp - final_hp == 1, "Should lose 1 HP when playing curse with Blue Candle"


class TestCurseEndOfTurnEffects:
    """Test curse effects that trigger at end of turn."""

    def test_decay_end_of_turn_damage(self):
        """Decay: End of turn take 2 damage."""
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

        print(f"\n=== Decay End of Turn Test ===")
        print(f"Player HP before: {combat.state.player.hp}")
        print(f"Player block before: {combat.state.player.block}")

        combat.state.phase = combat.state.phase.__class__.MONSTER_TURN
        combat._process_curse_effects_end_of_turn()

        print(f"Player HP after: {combat.state.player.hp}")
        print(f"HP lost: {80 - combat.state.player.hp}")

        assert combat.state.player.hp == 78, f"Should take 2 damage, HP should be 78, got {combat.state.player.hp}"

    def test_doubt_end_of_turn_weak(self):
        """Doubt: End of turn gain 1 Weak."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=[],
        )

        doubt = CardInstance("Doubt")
        combat.state.card_manager.hand.cards.append(doubt)

        print(f"\n=== Doubt End of Turn Test ===")
        print(f"Weak before: {combat.state.player.powers.get_power_amount('Weak')}")

        combat.state.phase = combat.state.phase.__class__.MONSTER_TURN
        combat._process_curse_effects_end_of_turn()

        print(f"Weak after: {combat.state.player.powers.get_power_amount('Weak')}")

        assert combat.state.player.powers.get_power_amount('Weak') == 1, "Should have 1 Weak"

    def test_regret_end_of_turn(self):
        """Regret: End of turn lose 1 HP per card in hand."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=[],
        )

        regret = CardInstance("Regret")
        combat.state.card_manager.hand.cards.append(regret)

        print(f"\n=== Regret End of Turn Test ===")
        print(f"Hand size: {len(combat.state.card_manager.hand.cards)}")
        print(f"Player HP before: {combat.state.player.hp}")

        combat.state.phase = combat.state.phase.__class__.MONSTER_TURN
        combat._process_curse_effects_end_of_turn()

        print(f"Player HP after: {combat.state.player.hp}")
        print(f"HP lost: {80 - combat.state.player.hp}")

        assert combat.state.player.hp == 80 - len(combat.state.card_manager.hand.cards), \
            f"Should lose {len(combat.state.card_manager.hand.cards)} HP (1 per card)"


class TestPainCurse:
    """Test Pain curse effect when other cards are played."""

    def test_pain_on_card_played(self):
        """Pain: When in hand, lose 1 HP per other card played."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(12345, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=[],
        )

        pain = CardInstance("Pain")
        combat.state.card_manager.hand.cards.append(pain)

        print(f"\n=== Pain Curse Test ===")
        print(f"Player HP before: {combat.state.player.hp}")

        combat.state.player.energy = 3

        strike_idx = None
        for i, card in enumerate(combat.state.card_manager.hand.cards):
            if "Strike" in card.card_id:
                strike_idx = i
                break

        if strike_idx is not None:
            combat.play_card(strike_idx, target_idx=0)
            print(f"After playing Strike, HP: {combat.state.player.hp}")

        assert combat.state.player.hp == 79, f"Should lose 1 HP when playing other cards with Pain in hand"


class TestDarkstonePeriapt:
    """Test Darkstone Periapt relic - gain max HP when curse received."""

    def test_darkstone_periapt_definition(self):
        """Darkstone Periapt: When receiving a curse, gain 6 max HP."""
        relic = get_relic_by_id("黑石护符")
        print(f"\n=== Darkstone Periapt Definition ===")
        print(f"Effect type: {relic.effects[0].effect_type}")
        print(f"Effect value: {relic.effects[0].value}")
        from sts_py.engine.content.relics import RelicEffectType
        assert relic.effects[0].effect_type == RelicEffectType.ON_CURSE_RECEIVED
        assert relic.effects[0].value == 6


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
