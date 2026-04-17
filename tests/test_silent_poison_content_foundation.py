from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import SILENT_ALL_DEFS, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestSilentPoisonContentFoundation:
    def test_silent_poison_cards_instantiate_with_static_metadata(self):
        deadly_poison = CardInstance("DeadlyPoison")
        poisoned_stab = CardInstance("PoisonedStab")
        bouncing_flask = CardInstance("BouncingFlask")
        noxious_fumes = CardInstance("NoxiousFumes")

        assert deadly_poison.rarity == CardRarity.COMMON
        assert deadly_poison.card_type == CardType.SKILL
        assert deadly_poison.cost == 1
        assert deadly_poison.base_magic_number == 5

        assert poisoned_stab.rarity == CardRarity.COMMON
        assert poisoned_stab.card_type == CardType.ATTACK
        assert poisoned_stab.cost == 1
        assert poisoned_stab.base_damage == 6
        assert poisoned_stab.base_magic_number == 3

        assert bouncing_flask.rarity == CardRarity.UNCOMMON
        assert bouncing_flask.card_type == CardType.SKILL
        assert bouncing_flask.cost == 2
        assert bouncing_flask.base_magic_number == 3

        assert noxious_fumes.rarity == CardRarity.UNCOMMON
        assert noxious_fumes.card_type == CardType.POWER
        assert noxious_fumes.cost == 1
        assert noxious_fumes.base_magic_number == 2

    def test_silent_poison_upgraded_card_entries_work(self):
        assert CardInstance("DeadlyPoison+").magic_number == 7
        assert CardInstance("PoisonedStab+").damage == 8
        assert CardInstance("PoisonedStab+").magic_number == 4
        assert CardInstance("BouncingFlask+").magic_number == 4
        assert CardInstance("NoxiousFumes+").magic_number == 3

    def test_silent_reward_pools_include_poison_cards(self):
        pools = build_reward_pools("SILENT")

        common_ids = {card.id for card in pools[CardRarity.COMMON]}
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}

        assert {"DeadlyPoison", "PoisonedStab"} <= common_ids
        assert {"BouncingFlask", "NoxiousFumes"} <= uncommon_ids

    def test_silent_reward_generation_can_return_poison_cards(self):
        engine = RunEngine.create("SILENTPOISONFOUNDATION", ascension=0, character_class="SILENT")

        saw_poison_card = False
        for _ in range(20):
            engine._add_card_reward()
            if any(card_id in {"DeadlyPoison", "PoisonedStab", "BouncingFlask", "NoxiousFumes"} for card_id in engine.state.pending_card_reward_cards):
                saw_poison_card = True
                break

        assert saw_poison_card is True
        assert all(card_id in SILENT_ALL_DEFS for card_id in engine.state.pending_card_reward_cards)
