from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import SILENT_ALL_DEFS, CardRarity
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestSilentDiscardPayoffContentFoundation:
    def test_discard_payoff_cards_instantiate_with_metadata(self):
        dagger_throw = CardInstance("DaggerThrow")
        sneaky_strike = CardInstance("SneakyStrike")
        eviscerate = CardInstance("Eviscerate")
        concentrate = CardInstance("Concentrate")
        calculated_gamble = CardInstance("CalculatedGamble")

        assert dagger_throw.cost == 1
        assert dagger_throw.damage == 9

        assert sneaky_strike.cost == 2
        assert sneaky_strike.damage == 12

        assert eviscerate.cost == 3
        assert eviscerate.damage == 7
        assert eviscerate.magic_number == 3

        assert concentrate.cost == 0
        assert concentrate.magic_number == 3

        assert calculated_gamble.cost == 0
        assert calculated_gamble.exhaust is True

    def test_discard_payoff_upgrade_entries_work(self):
        assert CardInstance("DaggerThrow+").damage == 12
        assert CardInstance("SneakyStrike+").damage == 16
        assert CardInstance("Eviscerate+").damage == 8
        assert CardInstance("Concentrate+").magic_number == 2

    def test_silent_reward_pools_include_discard_payoff_cards(self):
        pools = build_reward_pools("SILENT")
        common_ids = {card.id for card in pools[CardRarity.COMMON]}
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}

        assert {"DaggerThrow", "SneakyStrike"} <= common_ids
        assert {"Eviscerate", "Concentrate", "CalculatedGamble"} <= uncommon_ids

    def test_reward_generation_can_surface_discard_payoff_cards(self):
        engine = RunEngine.create("SILENTDISCARDPAYOFFFOUNDATION", ascension=0, character_class="SILENT")
        targets = {"DaggerThrow", "SneakyStrike", "Eviscerate", "Concentrate", "CalculatedGamble"}
        seen = False
        for _ in range(30):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in SILENT_ALL_DEFS for card_id in engine.state.pending_card_reward_cards)
