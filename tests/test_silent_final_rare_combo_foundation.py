from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import SILENT_ALL_DEFS, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestSilentFinalRareComboFoundation:
    def test_final_rare_combo_cards_instantiate_with_expected_metadata(self):
        bullet_time = CardInstance("BulletTime")
        choke = CardInstance("Choke")
        envenom = CardInstance("Envenom")
        grand_finale = CardInstance("GrandFinale")
        phantasmal_killer = CardInstance("PhantasmalKiller")
        skewer = CardInstance("Skewer")
        storm_of_steel = CardInstance("StormOfSteel")
        alchemize = CardInstance("Alchemize")

        assert bullet_time.rarity == CardRarity.RARE
        assert bullet_time.card_type == CardType.SKILL
        assert bullet_time.cost == 3

        assert choke.rarity == CardRarity.UNCOMMON
        assert choke.card_type == CardType.ATTACK
        assert choke.cost == 2
        assert choke.damage == 12
        assert choke.magic_number == 3

        assert envenom.rarity == CardRarity.RARE
        assert envenom.card_type == CardType.POWER
        assert envenom.cost == 2

        assert grand_finale.rarity == CardRarity.RARE
        assert grand_finale.card_type == CardType.ATTACK
        assert grand_finale.cost == 0
        assert grand_finale.damage == 50

        assert phantasmal_killer.rarity == CardRarity.RARE
        assert phantasmal_killer.card_type == CardType.SKILL
        assert phantasmal_killer.cost == 1

        assert skewer.rarity == CardRarity.UNCOMMON
        assert skewer.card_type == CardType.ATTACK
        assert skewer.cost == -1
        assert skewer.damage == 7

        assert storm_of_steel.rarity == CardRarity.RARE
        assert storm_of_steel.card_type == CardType.SKILL
        assert storm_of_steel.cost == 1

        assert alchemize.rarity == CardRarity.RARE
        assert alchemize.card_type == CardType.SKILL
        assert alchemize.cost == 1
        assert alchemize.exhaust is True

    def test_final_rare_combo_upgrades_and_aliases_work(self):
        assert CardInstance("BulletTime+").cost == 2
        assert CardInstance("Choke+").magic_number == 5
        assert CardInstance("Envenom+").cost == 1
        assert CardInstance("GrandFinale+").damage == 60
        assert CardInstance("PhantasmalKiller+").cost == 0
        assert CardInstance("Skewer+").damage == 10
        assert CardInstance("Alchemize+").cost == 0

        assert CardInstance("Bullet Time").card_id == "BulletTime"
        assert CardInstance("Grand Finale").card_id == "GrandFinale"
        assert CardInstance("Phantasmal Killer").card_id == "PhantasmalKiller"
        assert CardInstance("Storm of Steel").card_id == "StormOfSteel"
        assert CardInstance("Venomology").card_id == "Alchemize"
        assert CardInstance("Strike_Green").card_id == "Strike"
        assert CardInstance("Defend_Green").card_id == "Defend"

    def test_reward_pools_include_final_rare_combo_cards(self):
        pools = build_reward_pools("SILENT")
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}
        rare_ids = {card.id for card in pools[CardRarity.RARE]}

        assert {"Choke", "Skewer"} <= uncommon_ids
        assert {"BulletTime", "Envenom", "GrandFinale", "PhantasmalKiller", "StormOfSteel", "Alchemize"} <= rare_ids

    def test_reward_generation_can_surface_final_rare_combo_cards(self):
        engine = RunEngine.create("SILENTFINALRARECOMBO", ascension=0, character_class="SILENT")
        targets = {"BulletTime", "Choke", "Envenom", "GrandFinale", "PhantasmalKiller", "Skewer", "StormOfSteel", "Alchemize"}
        seen = False
        for _ in range(120):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in SILENT_ALL_DEFS for card_id in engine.state.pending_card_reward_cards)
