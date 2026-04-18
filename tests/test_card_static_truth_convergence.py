from __future__ import annotations

from pathlib import Path

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import ALL_CARD_DEFS, CardRarity
from sts_py.terminal.catalog import card_requires_target
from sts_py.tools import wiki_audit


def test_representative_ironclad_defs_hold_static_truth() -> None:
    bash = ALL_CARD_DEFS["Bash"]
    anger = ALL_CARD_DEFS["Anger"]
    armaments = ALL_CARD_DEFS["Armaments"]
    carnage = ALL_CARD_DEFS["Carnage"]
    shockwave = ALL_CARD_DEFS["Shockwave"]
    whirlwind = ALL_CARD_DEFS["Whirlwind"]
    searing_blow = ALL_CARD_DEFS["SearingBlow"]
    ghostly_armor = ALL_CARD_DEFS["GhostlyArmor"]

    assert (bash.cost, bash.base_damage, bash.base_magic_number, bash.target_required) == (2, 8, 2, True)
    assert (anger.cost, anger.base_damage, anger.upgrade_damage, anger.target_required) == (0, 6, 2, True)
    assert (armaments.cost, armaments.base_block, armaments.base_magic_number) == (1, 5, 0)
    assert carnage.cost == 2
    assert carnage.base_damage == 20
    assert carnage.is_ethereal is True
    assert carnage.is_exhaust is False
    assert carnage.target_required is True
    assert shockwave.cost == 2
    assert shockwave.base_magic_number == 3
    assert shockwave.is_exhaust is True
    assert (whirlwind.cost, whirlwind.base_damage) == (-1, 5)
    assert whirlwind.rarity == CardRarity.UNCOMMON
    assert (searing_blow.cost, searing_blow.target_required) == (2, True)
    assert (ghostly_armor.cost, ghostly_armor.base_block, ghostly_armor.is_ethereal) == (1, 10, True)


def test_card_instance_uses_definition_truth_for_base_and_upgrade() -> None:
    defend = CardInstance("Defend")
    flex = CardInstance("Flex")
    blood_for_blood = CardInstance("BloodforBlood")
    ghostly_armor = CardInstance("GhostlyArmor")

    defend.upgrade()
    flex.upgrade()
    blood_for_blood.upgrade()
    ghostly_armor.upgrade()

    assert defend.base_block == 8
    assert flex.base_magic_number == 4
    assert blood_for_blood.cost == 3
    assert blood_for_blood.base_damage == 22
    assert ghostly_armor.cost == 1
    assert ghostly_armor.base_block == 13


def test_target_requirement_overrides_cover_known_mismatch_lane() -> None:
    assert card_requires_target("BloodforBlood") is True
    assert card_requires_target("Rampage") is True
    assert card_requires_target("BowlingBash") is True
    assert card_requires_target("FearNoEvil") is True
    assert card_requires_target("PressurePoints") is True
    assert card_requires_target("Expunger") is True
    assert card_requires_target("Eviscerate") is True
    assert card_requires_target("Havoc") is False


def test_cross_character_flag_and_rarity_corrections_are_pinned() -> None:
    assert ALL_CARD_DEFS["AfterImage"].is_innate is False
    assert ALL_CARD_DEFS["AfterImage"].upgrade_innate is True
    assert ALL_CARD_DEFS["Alpha"].is_innate is True
    assert ALL_CARD_DEFS["BattleHymn"].is_innate is True
    assert ALL_CARD_DEFS["Brutality"].is_innate is True
    assert ALL_CARD_DEFS["InfiniteBlades"].is_innate is True
    assert ALL_CARD_DEFS["Chill"].is_innate is True
    assert ALL_CARD_DEFS["MachineLearning"].is_innate is True
    assert ALL_CARD_DEFS["Storm"].is_innate is True
    assert ALL_CARD_DEFS["Intimidate"].is_exhaust is True
    assert ALL_CARD_DEFS["Pummel"].is_exhaust is True
    assert ALL_CARD_DEFS["LimitBreak"].is_exhaust is True
    assert ALL_CARD_DEFS["AscendersBane"].is_ethereal is True
    assert ALL_CARD_DEFS["Clumsy"].is_ethereal is True
    assert ALL_CARD_DEFS["Blasphemy"].is_retain is True
    assert ALL_CARD_DEFS["Miracle"].is_retain is True
    assert ALL_CARD_DEFS["Worship"].is_retain is True
    assert ALL_CARD_DEFS["Backflip"].rarity == CardRarity.COMMON
    assert ALL_CARD_DEFS["Malaise"].rarity == CardRarity.RARE
    assert ALL_CARD_DEFS["InfiniteBlades"].rarity == CardRarity.UNCOMMON


def test_java_card_fact_extraction_normalizes_special_and_dynamic_cards() -> None:
    repo_root = Path.cwd()

    tempest = wiki_audit.build_card_java_facts(repo_root, "Tempest")
    ascenders_bane = wiki_audit.build_card_java_facts(repo_root, "AscendersBane")
    burn = wiki_audit.build_card_java_facts(repo_root, "Burn")
    burn_plus = wiki_audit.build_card_java_facts(repo_root, "Burn+")
    bullseye = wiki_audit.build_card_java_facts(repo_root, "Bullseye")
    genetic_algorithm = wiki_audit.build_card_java_facts(repo_root, "GeneticAlgorithm")
    ritual_dagger = wiki_audit.build_card_java_facts(repo_root, "RitualDagger")
    shiv = wiki_audit.build_card_java_facts(repo_root, "Shiv")

    assert tempest["type"] == "SKILL"
    assert tempest["rarity"] == "UNCOMMON"
    assert tempest["exhaust"] is True
    assert ascenders_bane["cost"] == -2
    assert ascenders_bane["rarity"] == "CURSE"
    assert ascenders_bane["ethereal"] is True
    assert burn["rarity"] == "SPECIAL"
    assert burn["magic_number"] == 2
    assert burn_plus["java_class"] == "Burn"
    assert burn_plus["java_class"] == "Burn"
    assert bullseye["java_class"] == "LockOn"
    assert bullseye["official_key"] == "Lockon"
    assert genetic_algorithm["block"] == 1
    assert ritual_dagger["damage"] == 15
    assert shiv["damage"] == 4
