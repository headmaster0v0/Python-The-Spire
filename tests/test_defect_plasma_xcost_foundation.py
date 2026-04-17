from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import CARD_DEFS_BY_CHARACTER, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestDefectPlasmaXCostFoundation:
    def test_cards_instantiate_with_expected_metadata(self):
        fusion = CardInstance("Fusion")
        capacitor = CardInstance("Capacitor")
        tempest = CardInstance("Tempest")
        reinforced_body = CardInstance("ReinforcedBody")
        meteor_strike = CardInstance("MeteorStrike")

        assert fusion.rarity == CardRarity.UNCOMMON
        assert fusion.card_type == CardType.SKILL
        assert fusion.cost == 2
        assert fusion.magic_number == 1

        assert capacitor.rarity == CardRarity.UNCOMMON
        assert capacitor.card_type == CardType.POWER
        assert capacitor.cost == 1
        assert capacitor.magic_number == 2

        assert tempest.rarity == CardRarity.UNCOMMON
        assert tempest.card_type == CardType.SKILL
        assert tempest.cost == -1
        assert tempest.exhaust is True

        assert reinforced_body.rarity == CardRarity.UNCOMMON
        assert reinforced_body.card_type == CardType.SKILL
        assert reinforced_body.cost == -1
        assert reinforced_body.block == 7

        assert meteor_strike.rarity == CardRarity.RARE
        assert meteor_strike.card_type == CardType.ATTACK
        assert meteor_strike.cost == 5
        assert meteor_strike.damage == 24
        assert meteor_strike.magic_number == 3

    def test_upgraded_entries_and_aliases_work(self):
        assert CardInstance("Fusion+").cost == 1
        assert CardInstance("Capacitor+").magic_number == 3
        assert CardInstance("ReinforcedBody+").block == 9
        assert CardInstance("MeteorStrike+").damage == 30
        assert CardInstance("Meteor Strike").card_id == "MeteorStrike"
        assert CardInstance("Reinforced Body").card_id == "ReinforcedBody"

    def test_reward_pools_include_plasma_xcost_cards(self):
        pools = build_reward_pools("DEFECT")
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}
        rare_ids = {card.id for card in pools[CardRarity.RARE]}

        assert {"Fusion", "Capacitor", "Tempest", "ReinforcedBody"} <= uncommon_ids
        assert {"MeteorStrike"} <= rare_ids

    def test_reward_generation_can_surface_plasma_xcost_cards(self):
        engine = RunEngine.create("DEFECTPLASMAX", ascension=0, character_class="DEFECT")
        targets = {"Fusion", "Capacitor", "Tempest", "ReinforcedBody", "MeteorStrike"}
        seen = False
        for _ in range(80):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in CARD_DEFS_BY_CHARACTER["DEFECT"] for card_id in engine.state.pending_card_reward_cards)
