from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import CARD_DEFS_BY_CHARACTER, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestDefectCommonAttackContinuationFoundation:
    def test_cards_instantiate_with_expected_metadata(self):
        claw = CardInstance("Claw")
        ftl = CardInstance("FTL")
        melter = CardInstance("Melter")
        rip_and_tear = CardInstance("RipAndTear")
        sunder = CardInstance("Sunder")
        scrape = CardInstance("Scrape")

        assert claw.rarity == CardRarity.COMMON
        assert claw.card_type == CardType.ATTACK
        assert claw.cost == 0
        assert claw.damage == 3
        assert claw.magic_number == 2

        assert ftl.rarity == CardRarity.UNCOMMON
        assert ftl.card_type == CardType.ATTACK
        assert ftl.cost == 0
        assert ftl.damage == 5
        assert ftl.magic_number == 3

        assert melter.rarity == CardRarity.UNCOMMON
        assert melter.card_type == CardType.ATTACK
        assert melter.cost == 1
        assert melter.damage == 10

        assert rip_and_tear.rarity == CardRarity.UNCOMMON
        assert rip_and_tear.card_type == CardType.ATTACK
        assert rip_and_tear.cost == 1
        assert rip_and_tear.damage == 7
        assert rip_and_tear.magic_number == 2

        assert sunder.rarity == CardRarity.UNCOMMON
        assert sunder.card_type == CardType.ATTACK
        assert sunder.cost == 3
        assert sunder.damage == 24

        assert scrape.rarity == CardRarity.UNCOMMON
        assert scrape.card_type == CardType.ATTACK
        assert scrape.cost == 1
        assert scrape.damage == 7
        assert scrape.magic_number == 4

    def test_upgraded_entries_and_aliases_work(self):
        assert CardInstance("Claw", upgraded=True).damage == 5
        assert CardInstance("FTL", upgraded=True).damage == 6
        assert CardInstance("FTL", upgraded=True).magic_number == 4
        assert CardInstance("Melter", upgraded=True).damage == 14
        assert CardInstance("RipAndTear", upgraded=True).damage == 9
        assert CardInstance("Sunder", upgraded=True).damage == 32
        assert CardInstance("Scrape", upgraded=True).damage == 10
        assert CardInstance("Scrape", upgraded=True).magic_number == 5
        assert CardInstance("Gash").card_id == "Claw"
        assert CardInstance("Rip and Tear").card_id == "RipAndTear"

    def test_reward_pools_include_common_attack_continuation_cards(self):
        pools = build_reward_pools("DEFECT")
        common_ids = {card.id for card in pools[CardRarity.COMMON]}
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}

        assert {"Claw"} <= common_ids
        assert {"FTL", "Melter", "RipAndTear", "Sunder", "Scrape"} <= uncommon_ids

    def test_reward_generation_can_surface_common_attack_continuation_cards(self):
        engine = RunEngine.create("DEFECTCOMMONATTACKS", ascension=0, character_class="DEFECT")
        targets = {"Claw", "FTL", "Melter", "RipAndTear", "Sunder", "Scrape"}
        seen = False
        for _ in range(80):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in CARD_DEFS_BY_CHARACTER["DEFECT"] for card_id in engine.state.pending_card_reward_cards)
