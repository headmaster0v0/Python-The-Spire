from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import CARD_DEFS_BY_CHARACTER, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestDefectContentFoundation:
    def test_run_engine_create_uses_defect_starter_deck_and_relic(self):
        engine = RunEngine.create("DEFECTFOUNDATION", ascension=0, character_class="DEFECT")

        assert engine.state.character_class == "DEFECT"
        assert engine.state.player_hp == 75
        assert engine.state.player_max_hp == 75
        assert engine.state.deck == [
            "Strike_B", "Strike_B", "Strike_B", "Strike_B",
            "Defend_B", "Defend_B", "Defend_B", "Defend_B",
            "Zap", "Dualcast",
        ]
        assert engine.state.relics == ["CrackedCore"]

    def test_defect_reward_pools_are_non_empty(self):
        pools = build_reward_pools("DEFECT")

        assert len(pools[CardRarity.COMMON]) > 0
        assert len(pools[CardRarity.UNCOMMON]) > 0
        assert len(pools[CardRarity.RARE]) > 0

    def test_reward_generation_can_surface_defect_cards(self):
        engine = RunEngine.create("DEFECTREWARDS", ascension=0, character_class="DEFECT")
        targets = {"BallLightning", "ColdSnap", "Coolheaded", "GoForTheEyes", "BeamCell", "SweepingBeam", "Defragment", "CoreSurge"}
        seen = False
        for _ in range(30):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in CARD_DEFS_BY_CHARACTER["DEFECT"] for card_id in engine.state.pending_card_reward_cards)

    def test_defect_cards_instantiate_with_expected_metadata(self):
        strike = CardInstance("Strike_B")
        defend = CardInstance("Defend_B")
        zap = CardInstance("Zap")
        dualcast = CardInstance("Dualcast")
        defragment = CardInstance("Defragment")
        core_surge = CardInstance("CoreSurge")

        assert strike.card_type == CardType.ATTACK
        assert strike.rarity == CardRarity.BASIC
        assert strike.damage == 6

        assert defend.card_type == CardType.SKILL
        assert defend.rarity == CardRarity.BASIC
        assert defend.block == 5

        assert zap.card_type == CardType.SKILL
        assert zap.cost == 1
        assert zap.magic_number == 1
        assert CardInstance("Zap+").cost == 0

        assert dualcast.card_type == CardType.SKILL
        assert dualcast.cost == 1
        assert CardInstance("Dualcast+").cost == 0

        assert defragment.card_type == CardType.POWER
        assert defragment.magic_number == 1
        assert CardInstance("Defragment+").magic_number == 2

        assert core_surge.card_type == CardType.ATTACK
        assert core_surge.rarity == CardRarity.RARE
        assert core_surge.exhaust is True
        assert core_surge.damage == 11

