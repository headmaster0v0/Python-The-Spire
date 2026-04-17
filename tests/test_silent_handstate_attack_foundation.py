from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import SILENT_ALL_DEFS, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestSilentHandStateAttackFoundation:
    def test_handstate_attack_cards_instantiate_with_expected_metadata(self):
        blur = CardInstance("Blur")
        endless_agony = CardInstance("EndlessAgony")
        flechettes = CardInstance("Flechettes")
        glass_knife = CardInstance("GlassKnife")
        heel_hook = CardInstance("HeelHook")
        masterful_stab = CardInstance("MasterfulStab")
        riddle = CardInstance("RiddleWithHoles")
        unload = CardInstance("Unload")

        assert blur.rarity == CardRarity.UNCOMMON
        assert blur.card_type == CardType.SKILL
        assert blur.cost == 1
        assert blur.block == 5

        assert endless_agony.rarity == CardRarity.UNCOMMON
        assert endless_agony.card_type == CardType.ATTACK
        assert endless_agony.cost == 0
        assert endless_agony.damage == 4
        assert endless_agony.exhaust is True

        assert flechettes.rarity == CardRarity.UNCOMMON
        assert flechettes.card_type == CardType.ATTACK
        assert flechettes.cost == 1
        assert flechettes.damage == 4

        assert glass_knife.rarity == CardRarity.RARE
        assert glass_knife.card_type == CardType.ATTACK
        assert glass_knife.cost == 1
        assert glass_knife.damage == 8

        assert heel_hook.rarity == CardRarity.UNCOMMON
        assert heel_hook.card_type == CardType.ATTACK
        assert heel_hook.cost == 1
        assert heel_hook.damage == 5

        assert masterful_stab.rarity == CardRarity.UNCOMMON
        assert masterful_stab.card_type == CardType.ATTACK
        assert masterful_stab.cost == 0
        assert masterful_stab.damage == 12

        assert riddle.rarity == CardRarity.UNCOMMON
        assert riddle.card_type == CardType.ATTACK
        assert riddle.cost == 2
        assert riddle.damage == 3

        assert unload.rarity == CardRarity.RARE
        assert unload.card_type == CardType.ATTACK
        assert unload.cost == 1
        assert unload.damage == 14

    def test_handstate_attack_upgrade_entries_and_aliases_work(self):
        assert CardInstance("Blur+").block == 8
        assert CardInstance("EndlessAgony+").damage == 6
        assert CardInstance("Flechettes+").damage == 6
        assert CardInstance("GlassKnife+").damage == 12
        assert CardInstance("HeelHook+").damage == 8
        assert CardInstance("MasterfulStab+").damage == 16
        assert CardInstance("RiddleWithHoles+").damage == 4
        assert CardInstance("Unload+").damage == 18

        assert CardInstance("Endless Agony").card_id == "EndlessAgony"
        assert CardInstance("Glass Knife").card_id == "GlassKnife"
        assert CardInstance("Heel Hook").card_id == "HeelHook"
        assert CardInstance("Masterful Stab").card_id == "MasterfulStab"
        assert CardInstance("Riddle With Holes").card_id == "RiddleWithHoles"

    def test_reward_pools_include_handstate_attack_cards(self):
        pools = build_reward_pools("SILENT")
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}
        rare_ids = {card.id for card in pools[CardRarity.RARE]}

        assert {"Blur", "EndlessAgony", "Flechettes", "HeelHook", "MasterfulStab", "RiddleWithHoles"} <= uncommon_ids
        assert {"GlassKnife", "Unload"} <= rare_ids

    def test_reward_generation_can_surface_handstate_attack_cards(self):
        engine = RunEngine.create("SILENTHANDSTATEATTACK", ascension=0, character_class="SILENT")
        targets = {"Blur", "EndlessAgony", "Flechettes", "GlassKnife", "HeelHook", "MasterfulStab", "RiddleWithHoles", "Unload"}
        seen = False
        for _ in range(100):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in SILENT_ALL_DEFS for card_id in engine.state.pending_card_reward_cards)
