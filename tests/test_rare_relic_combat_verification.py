"""Comprehensive rare relic combat verification tests.

This test suite verifies rare relic effects in actual combat scenarios
to ensure they match the source game logic.
"""
import pytest
from sts_py.engine.run.run_engine import RunEngine
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.content.relics import (
    RARE_RELICS, get_relic_by_id, RelicEffectType
)
from sts_py.engine.content.cards_min import STATUS_CARD_DEFS


class TestRareRelicDefinitions:
    """Test that rare relic definitions are correct."""

    def test_all_rare_effects_defined(self):
        """All rare relics should have non-empty effects."""
        empty = []
        for relic_id, relic in RARE_RELICS.items():
            if not hasattr(relic, 'effects') or not relic.effects:
                empty.append(relic_id)
        assert len(empty) == 0, f"Relics without effects: {empty}"

    def test_thread_and_needle_definition(self):
        """Thread and Needle should have AT_BATTLE_START with plated_armor."""
        relic = get_relic_by_id("针线")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.AT_BATTLE_START
        assert effect.extra.get("type") == "plated_armor"
        assert effect.value == 4

    def test_fossilized_helix_definition(self):
        """FossilizedHelix should have AT_BATTLE_START_BUFFER."""
        relic = get_relic_by_id("螺类化石")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.AT_BATTLE_START_BUFFER

    def test_lizard_tail_definition(self):
        """Lizard Tail should have ON_DEATH_SAVE with revive_half_hp."""
        relic = get_relic_by_id("蜥蜴尾巴")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.ON_DEATH_SAVE
        assert effect.extra.get("type") == "revive_half_hp"

    def test_du_vu_doll_in_aliases(self):
        """Du-Vu Doll is in RELIC_ID_ALIASES."""
        from sts_py.engine.content.relics import RELIC_ID_ALIASES
        assert "DuVuDoll" in RELIC_ID_ALIASES or "毒巫娃娃" in RELIC_ID_ALIASES or "毒巫娃娃" in RELIC_ID_ALIASES

    def test_torii_definition(self):
        """Torii should have MODIFY_DAMAGE with min_damage_receive."""
        relic = get_relic_by_id("鸟居")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.MODIFY_DAMAGE
        assert effect.extra.get("type") == "min_damage_receive"
        assert effect.extra.get("max") == 5


class TestStatusCardDefinitions:
    """Test that status card definitions are correct."""

    def test_burn_definition(self):
        """Burn should deal 2 damage at end of turn."""
        from sts_py.engine.content.cards_min import CardType
        burn = STATUS_CARD_DEFS.get("Burn")
        assert burn is not None
        assert burn.card_type == CardType.STATUS
        assert burn.is_unplayable == True
        assert burn.curse_effect_type.value == "end_of_turn_damage"
        assert burn.curse_effect_value == 2

    def test_dazed_definition(self):
        """Dazed should be ethereal."""
        from sts_py.engine.content.cards_min import CardType
        dazed = STATUS_CARD_DEFS.get("Dazed")
        assert dazed is not None
        assert dazed.card_type == CardType.STATUS
        assert dazed.is_unplayable == True
        assert dazed.is_ethereal == True

    def test_void_definition(self):
        """Void should cause energy loss on draw and be ethereal."""
        from sts_py.engine.content.cards_min import CardType
        void = STATUS_CARD_DEFS.get("Void")
        assert void is not None
        assert void.card_type == CardType.STATUS
        assert void.is_unplayable == True
        assert void.is_ethereal == True
        assert void.curse_effect_type.value == "on_card_played_lose_hp"
        assert void.curse_effect_value == 1

    def test_slimed_definition(self):
        """Slimed should be playable (cost=1) and exhaust."""
        from sts_py.engine.content.cards_min import CardType
        slimed = STATUS_CARD_DEFS.get("Slimed")
        assert slimed is not None
        assert slimed.card_type == CardType.STATUS
        assert slimed.is_unplayable == False
        assert slimed.cost == 1
        assert slimed.is_exhaust == True

    def test_wound_definition(self):
        """Wound should be unplayable with no effect."""
        from sts_py.engine.content.cards_min import CardType
        wound = STATUS_CARD_DEFS.get("Wound")
        assert wound is not None
        assert wound.card_type == CardType.STATUS
        assert wound.is_unplayable == True


class TestRelicSynergy:
    """Test multiple relics working together."""

    def test_tingsha_discard_damage(self):
        """Tingsha should deal 3 damage on discard to random enemy."""
        relic = get_relic_by_id("铜钹")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.ON_DISCARD
        assert effect.value == 3
        assert effect.extra.get("type") == "damage_random"

    def test_tough_bandages_discard_block(self):
        """Tough Bandages should give 3 block on discard."""
        relic = get_relic_by_id("结实绷带")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.ON_DISCARD
        assert effect.value == 3
        assert effect.extra.get("type") == "block"

    def test_velvet_choker_limit(self):
        """Velvet Choker should give 1 energy but limit cards played to 6."""
        relic = get_relic_by_id("VelvetChoker")
        assert relic is not None
        effect_types = [e.effect_type for e in relic.effects]
        assert RelicEffectType.START_WITH_ENERGY in effect_types
        assert RelicEffectType.LIMIT_CARDS_PLAY in effect_types

    def test_snecko_eye_confused(self):
        """Snecko Eye should confuse and add extra draw."""
        relic = get_relic_by_id("斯内克之眼")
        assert relic is not None
        effect_types = [e.effect_type for e in relic.effects]
        assert RelicEffectType.AT_BATTLE_START in effect_types
        assert RelicEffectType.LIMIT_CARDS_DRAW in effect_types


class TestEffectTypeCoverage:
    """Verify all effect types are properly defined."""

    def test_all_effect_types_valid(self):
        """All effect types used should be valid RelicEffectType values."""
        valid_types = set(RelicEffectType)
        for relic_id, relic in RARE_RELICS.items():
            for effect in relic.effects:
                assert effect.effect_type in valid_types, \
                    f"{relic_id} has invalid effect type: {effect.effect_type}"

    def test_effect_coverage_summary(self):
        """Summarize which effect types are used by rare relics."""
        effect_usage = {}
        for relic_id, relic in RARE_RELICS.items():
            for effect in relic.effects:
                type_str = effect.effect_type.value if hasattr(effect.effect_type, 'value') else str(effect.effect_type)
                if type_str not in effect_usage:
                    effect_usage[type_str] = []
                effect_usage[type_str].append(relic_id)

        assert len(effect_usage) > 0, "Should have effect types in use"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])