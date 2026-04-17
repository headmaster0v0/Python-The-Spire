from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import CARD_DEFS_BY_CHARACTER, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestDefectOrbDamageContinuationFoundation:
    def test_cards_instantiate_with_expected_metadata(self):
        lockon = CardInstance("Lockon")
        recursion = CardInstance("Recursion")
        rainbow = CardInstance("Rainbow")
        electrodynamics = CardInstance("Electrodynamics")
        biased = CardInstance("BiasedCognition")

        assert lockon.rarity == CardRarity.UNCOMMON
        assert lockon.card_type == CardType.ATTACK
        assert lockon.cost == 1
        assert lockon.damage == 8
        assert lockon.magic_number == 2

        assert recursion.rarity == CardRarity.COMMON
        assert recursion.card_type == CardType.SKILL
        assert recursion.cost == 1

        assert rainbow.rarity == CardRarity.RARE
        assert rainbow.card_type == CardType.SKILL
        assert rainbow.cost == 2
        assert rainbow.exhaust is True

        assert electrodynamics.rarity == CardRarity.RARE
        assert electrodynamics.card_type == CardType.POWER
        assert electrodynamics.cost == 2
        assert electrodynamics.magic_number == 2

        assert biased.rarity == CardRarity.RARE
        assert biased.card_type == CardType.POWER
        assert biased.cost == 1
        assert biased.magic_number == 4

    def test_upgraded_entries_and_aliases_work(self):
        assert CardInstance("Lockon+").damage == 11
        assert CardInstance("Lockon+").magic_number == 3
        assert CardInstance("Recursion+").cost == 0
        assert CardInstance("Rainbow+").exhaust is False
        assert CardInstance("Electrodynamics+").magic_number == 3
        assert CardInstance("BiasedCognition+").magic_number == 5
        assert CardInstance("Redo").card_id == "Recursion"

    def test_reward_pools_include_orb_damage_cards(self):
        pools = build_reward_pools("DEFECT")
        common_ids = {card.id for card in pools[CardRarity.COMMON]}
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}
        rare_ids = {card.id for card in pools[CardRarity.RARE]}

        assert {"Recursion"} <= common_ids
        assert {"Lockon"} <= uncommon_ids
        assert {"Rainbow", "Electrodynamics", "BiasedCognition"} <= rare_ids

    def test_reward_generation_can_surface_orb_damage_cards(self):
        engine = RunEngine.create("DEFECTORBDAMAGE", ascension=0, character_class="DEFECT")
        targets = {"Lockon", "Recursion", "Rainbow", "Electrodynamics", "BiasedCognition"}
        seen = False
        for _ in range(80):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in CARD_DEFS_BY_CHARACTER["DEFECT"] for card_id in engine.state.pending_card_reward_cards)
