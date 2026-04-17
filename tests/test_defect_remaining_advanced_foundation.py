from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import CARD_DEFS_BY_CHARACTER, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestDefectRemainingAdvancedFoundation:
    def test_cards_instantiate_with_expected_metadata(self):
        bullseye = CardInstance("Bullseye")
        chill = CardInstance("Chill")
        doom_and_gloom = CardInstance("DoomAndGloom")
        genetic_algorithm = CardInstance("GeneticAlgorithm")
        hello_world = CardInstance("HelloWorld")
        hyperbeam = CardInstance("Hyperbeam")

        assert bullseye.rarity == CardRarity.UNCOMMON
        assert bullseye.card_type == CardType.ATTACK
        assert bullseye.cost == 1
        assert bullseye.damage == 8
        assert bullseye.magic_number == 2

        assert chill.rarity == CardRarity.UNCOMMON
        assert chill.card_type == CardType.SKILL
        assert chill.cost == 0
        assert chill.exhaust is True

        assert doom_and_gloom.rarity == CardRarity.UNCOMMON
        assert doom_and_gloom.card_type == CardType.ATTACK
        assert doom_and_gloom.cost == 2
        assert doom_and_gloom.damage == 10
        assert doom_and_gloom.magic_number == 1

        assert genetic_algorithm.rarity == CardRarity.UNCOMMON
        assert genetic_algorithm.card_type == CardType.SKILL
        assert genetic_algorithm.cost == 1
        assert genetic_algorithm.block == 1
        assert genetic_algorithm.magic_number == 2
        assert genetic_algorithm.exhaust is True

        assert hello_world.rarity == CardRarity.UNCOMMON
        assert hello_world.card_type == CardType.POWER
        assert hello_world.cost == 1

        assert hyperbeam.rarity == CardRarity.RARE
        assert hyperbeam.card_type == CardType.ATTACK
        assert hyperbeam.cost == 2
        assert hyperbeam.damage == 26
        assert hyperbeam.magic_number == 3

    def test_upgraded_entries_and_aliases_work(self):
        assert CardInstance("Bullseye", upgraded=True).damage == 11
        assert CardInstance("Bullseye", upgraded=True).magic_number == 3
        assert CardInstance("Chill", upgraded=True).is_innate is True
        assert CardInstance("DoomAndGloom", upgraded=True).damage == 14
        assert CardInstance("GeneticAlgorithm", upgraded=True).magic_number == 3
        assert CardInstance("HelloWorld", upgraded=True).is_innate is True
        assert CardInstance("Hyperbeam", upgraded=True).damage == 34
        assert CardInstance("Doom and Gloom").card_id == "DoomAndGloom"
        assert CardInstance("Genetic Algorithm").card_id == "GeneticAlgorithm"
        assert CardInstance("Hello World").card_id == "HelloWorld"
        assert CardInstance("Hyper Beam").card_id == "Hyperbeam"

    def test_reward_pools_include_remaining_advanced_cards(self):
        pools = build_reward_pools("DEFECT")
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}
        rare_ids = {card.id for card in pools[CardRarity.RARE]}

        assert {"Bullseye", "Chill", "DoomAndGloom", "GeneticAlgorithm", "HelloWorld"} <= uncommon_ids
        assert {"Hyperbeam"} <= rare_ids

    def test_reward_generation_can_surface_remaining_advanced_cards(self):
        engine = RunEngine.create("DEFECTREMAININGADVANCED", ascension=0, character_class="DEFECT")
        targets = {"Bullseye", "Chill", "DoomAndGloom", "GeneticAlgorithm", "HelloWorld", "Hyperbeam"}
        seen = False
        for _ in range(60):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in CARD_DEFS_BY_CHARACTER["DEFECT"] for card_id in engine.state.pending_card_reward_cards)
