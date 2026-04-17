from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import SILENT_ALL_DEFS, CardRarity
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestSilentShivDiscardContentFoundation:
    def test_silent_reward_pools_include_shiv_and_discard_cards(self):
        pools = build_reward_pools("SILENT")

        common_ids = {card.id for card in pools[CardRarity.COMMON]}
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}
        rare_ids = {card.id for card in pools[CardRarity.RARE]}

        assert {"CloakAndDagger", "BladeDance", "Prepared", "Acrobatics"} <= common_ids
        assert {"Reflex", "Tactician"} <= uncommon_ids
        assert {"InfiniteBlades"} <= rare_ids

    def test_silent_reward_generation_can_surface_shiv_discard_cards(self):
        engine = RunEngine.create("SILENTSHIVFOUNDATION", ascension=0, character_class="SILENT")

        seen = False
        targets = {"CloakAndDagger", "BladeDance", "Prepared", "Acrobatics", "Reflex", "Tactician", "InfiniteBlades"}
        for _ in range(30):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in SILENT_ALL_DEFS for card_id in engine.state.pending_card_reward_cards)

    def test_ninja_scroll_battle_start_flag_is_consumed_into_real_shivs(self):
        engine = RunEngine.create("SILENTSHIVSTART", ascension=0, character_class="SILENT")
        engine.state.relics = ["NinjaScroll"]

        engine.start_combat_with_monsters(["JawWorm"])

        assert engine.state.combat is not None
        hand_ids = [card.card_id for card in engine.state.combat.state.card_manager.hand.cards]
        assert hand_ids.count("Shiv") == 3
        assert len(hand_ids) == 8

    def test_shiv_runtime_card_is_available_through_all_card_defs(self):
        shiv = CardInstance("Shiv")

        assert shiv.card_id == "Shiv"
        assert shiv.damage == 4
