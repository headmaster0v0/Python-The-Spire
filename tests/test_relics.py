"""Verify relic implementations."""
from __future__ import annotations

import pytest
from sts_py.engine.content.relics import (
    RelicDef, RelicTier, RelicEffect, RelicEffectType,
    IRONCLAD_STARTER_RELICS, COMMON_RELICS, UNCOMMON_RELICS,
    RARE_RELICS, BOSS_RELICS, ALL_RELICS
)


class TestRelicDefinitions:
    """Test that all relics are properly defined."""

    def test_all_relics_have_id(self):
        """All relics should have a valid id."""
        for relic_id, relic in ALL_RELICS.items():
            assert relic.id == relic_id, f"Relic id mismatch: {relic.id} != {relic_id}"
            assert isinstance(relic.id, str), f"Relic id should be string: {relic_id}"
            assert len(relic.id) > 0, f"Relic id should not be empty"

    def test_all_relics_have_tier(self):
        """All relics should have a valid tier."""
        for relic_id, relic in ALL_RELICS.items():
            assert isinstance(relic.tier, RelicTier), f"Relic {relic_id} should have RelicTier"

    def test_starter_relics_correct_tier(self):
        """Starter relics should have STARTER tier."""
        for relic_id, relic in IRONCLAD_STARTER_RELICS.items():
            assert relic.tier == RelicTier.STARTER, f"{relic_id} should be STARTER tier"

    def test_common_relics_correct_tier(self):
        """Common relics should have COMMON tier."""
        for relic_id, relic in COMMON_RELICS.items():
            assert relic.tier == RelicTier.COMMON, f"{relic_id} should be COMMON tier"

    def test_uncommon_relics_correct_tier(self):
        """Uncommon relics should have UNCOMMON tier."""
        for relic_id, relic in UNCOMMON_RELICS.items():
            assert relic.tier == RelicTier.UNCOMMON, f"{relic_id} should be UNCOMMON tier"

    def test_rare_relics_correct_tier(self):
        """Rare relics should have RARE tier."""
        for relic_id, relic in RARE_RELICS.items():
            assert relic.tier == RelicTier.RARE, f"{relic_id} should be RARE tier"

    def test_boss_relics_correct_tier(self):
        """Boss relics should have BOSS tier."""
        for relic_id, relic in BOSS_RELICS.items():
            assert relic.tier == RelicTier.BOSS, f"{relic_id} should be BOSS tier"


class TestRelicEffects:
    """Test relic effects are properly defined."""

    def test_relic_effect_types_valid(self):
        """All relic effects should use valid effect types."""
        for relic_id, relic in ALL_RELICS.items():
            for effect in relic.effects:
                assert isinstance(effect, RelicEffect), f"Effect in {relic_id} should be RelicEffect"
                assert isinstance(effect.effect_type, RelicEffectType), (
                    f"Effect type in {relic_id} should be RelicEffectType"
                )

    def test_burning_blood_effect(self):
        """Burning Blood should heal 6 HP on victory."""
        relic = IRONCLAD_STARTER_RELICS.get("BurningBlood")
        assert relic is not None, "Burning Blood should exist"
        assert len(relic.effects) > 0, "Burning Blood should have effects"

        victory_effect = relic.effects[0]
        assert victory_effect.effect_type == RelicEffectType.ON_VICTORY
        assert victory_effect.value == 6

    def test_anchor_effect(self):
        """Anchor should give 10 block at battle start."""
        relic = COMMON_RELICS.get("Anchor")
        assert relic is not None, "Anchor should exist"
        assert relic.name == "锚", "Chinese name should use the official localization"
        assert len(relic.effects) > 0, "Anchor should have effects"

        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.AT_BATTLE_START
        assert effect.value == 10


class TestRelicCounts:
    """Test that we have the expected number of relics."""

    def test_starter_relic_count(self):
        """Should have 1 starter relic (Burning Blood for Ironclad)."""
        assert len(IRONCLAD_STARTER_RELICS) >= 1, "Should have at least 1 starter relic"

    def test_burning_blood_exists(self):
        """Burning Blood (Ironclad starter) should exist."""
        assert "BurningBlood" in IRONCLAD_STARTER_RELICS, "Burning Blood should exist"

    def test_total_relics_reasonable(self):
        """Total relics should be in reasonable range."""
        total = (
            len(IRONCLAD_STARTER_RELICS) +
            len(COMMON_RELICS) +
            len(UNCOMMON_RELICS) +
            len(RARE_RELICS) +
            len(BOSS_RELICS)
        )
        assert total >= 50, f"Should have at least 50 relics, got {total}"


class TestRelicWithEffects:
    """Test relics that have implemented effects."""

    def test_relics_with_battle_start_effects(self):
        """Relics with AT_BATTLE_START should have value > 0 unless it's a status effect."""
        for relic_id, relic in ALL_RELICS.items():
            for effect in relic.effects:
                if effect.effect_type == RelicEffectType.AT_BATTLE_START:
                    if effect.value == 0:
                        assert effect.extra.get("type"), f"{relic_id} has AT_BATTLE_START with value=0, should have type in extra"
                    else:
                        assert effect.value > 0, f"{relic_id} should have value > 0 for battle start"

    def test_relics_with_victory_effects(self):
        """Relics with ON_VICTORY should have value > 0."""
        for relic_id, relic in ALL_RELICS.items():
            for effect in relic.effects:
                if effect.effect_type == RelicEffectType.ON_VICTORY:
                    assert effect.value > 0, f"{relic_id} should have value > 0 for victory"


class TestRelicPrice:
    """Test relic pricing."""

    def test_starter_relic_price(self):
        """Starter relics should have fixed price of 300."""
        for relic_id, relic in IRONCLAD_STARTER_RELICS.items():
            assert relic.get_price() == 300, f"{relic_id} should cost 300"

    def test_common_relic_price(self):
        """Common relics should have fixed price of 150."""
        for relic_id, relic in COMMON_RELICS.items():
            assert relic.get_price() == 150, f"{relic_id} should cost 150"

    def test_boss_relic_price(self):
        """Boss relics should have price 999."""
        for relic_id, relic in BOSS_RELICS.items():
            assert relic.get_price() == 999, f"{relic_id} should cost 999 (non-purchasable)"
