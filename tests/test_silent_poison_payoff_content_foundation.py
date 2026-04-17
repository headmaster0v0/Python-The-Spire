from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import SILENT_ALL_DEFS, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.combat.powers import create_power


class TestSilentPoisonPayoffContentFoundation:
    def test_silent_poison_payoff_cards_instantiate_with_static_metadata(self):
        catalyst = CardInstance("Catalyst")
        crippling_cloud = CardInstance("CripplingCloud")
        corpse_explosion = CardInstance("CorpseExplosion")

        assert catalyst.rarity == CardRarity.UNCOMMON
        assert catalyst.card_type == CardType.SKILL
        assert catalyst.cost == 1
        assert catalyst.exhaust is True

        assert crippling_cloud.rarity == CardRarity.UNCOMMON
        assert crippling_cloud.card_type == CardType.SKILL
        assert crippling_cloud.cost == 2
        assert crippling_cloud.magic_number == 4
        assert crippling_cloud.exhaust is True

        assert corpse_explosion.rarity == CardRarity.RARE
        assert corpse_explosion.card_type == CardType.SKILL
        assert corpse_explosion.cost == 2
        assert corpse_explosion.magic_number == 6

    def test_silent_poison_payoff_upgraded_entries_work(self):
        assert CardInstance("CripplingCloud+").magic_number == 7
        assert CardInstance("CorpseExplosion+").magic_number == 9

    def test_silent_reward_pools_include_poison_payoff_cards(self):
        pools = build_reward_pools("SILENT")

        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}
        rare_ids = {card.id for card in pools[CardRarity.RARE]}

        assert {"Catalyst", "CripplingCloud"} <= uncommon_ids
        assert {"CorpseExplosion"} <= rare_ids

    def test_create_power_builds_corpse_explosion_marker(self):
        power = create_power("CorpseExplosion", 1, "monster_0")

        assert power.id == "CorpseExplosion"
        assert power.amount == 1
        assert power.owner == "monster_0"

    def test_reward_generation_can_surface_poison_payoff_cards(self):
        uncommon_ids = {card.id for card in build_reward_pools("SILENT")[CardRarity.UNCOMMON]}
        rare_ids = {card.id for card in build_reward_pools("SILENT")[CardRarity.RARE]}

        assert "Catalyst" in uncommon_ids
        assert "CripplingCloud" in uncommon_ids
        assert "CorpseExplosion" in rare_ids
        assert all(card_id in SILENT_ALL_DEFS for card_id in uncommon_ids | rare_ids)
