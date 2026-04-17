from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance, create_starter_deck
from sts_py.engine.content.cards_min import (
    IRONCLAD_ALL_DEFS,
    WATCHER_ALL_DEFS,
    CardRarity,
    CardType,
)
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestWatcherCardInstanceFoundation:
    def test_watcher_cards_instantiate_with_static_metadata(self):
        devotion = CardInstance("Devotion")
        wallop = CardInstance("Wallop")
        third_eye = CardInstance("ThirdEye")
        foresight = CardInstance("Foresight")

        assert devotion.rarity == CardRarity.RARE
        assert devotion.card_type == CardType.POWER
        assert devotion.cost == 1
        assert devotion.base_magic_number == 2

        assert wallop.rarity == CardRarity.UNCOMMON
        assert wallop.card_type == CardType.ATTACK
        assert wallop.cost == 2
        assert wallop.base_damage == 9

        assert third_eye.rarity == CardRarity.COMMON
        assert third_eye.card_type == CardType.SKILL
        assert third_eye.cost == 1
        assert third_eye.base_block == 7
        assert third_eye.base_magic_number == 3

        assert foresight.rarity == CardRarity.UNCOMMON
        assert foresight.card_type == CardType.POWER
        assert foresight.cost == 1
        assert foresight.base_magic_number == 3

    def test_watcher_upgraded_card_id_entry_still_works(self):
        wallop = CardInstance("Wallop+")
        assert wallop.upgraded
        assert wallop.base_damage == 12
        assert wallop.damage == 12

    def test_official_old_name_alias_resolves_to_foresight(self):
        wireheading = CardInstance("Wireheading")
        assert wireheading.card_id == "Foresight"
        assert wireheading.base_magic_number == 3

    def test_watcher_starter_deck_builder(self):
        deck = create_starter_deck("WATCHER")
        ids = [card.card_id for card in deck]

        assert len(ids) == 10
        assert ids.count("Strike") == 4
        assert ids.count("Defend") == 4
        assert "Eruption" in ids
        assert "Vigilance" in ids
        assert "Bash" not in ids


class TestWatcherRewardPools:
    def test_reward_pools_build_by_character(self):
        ironclad_pools = build_reward_pools("IRONCLAD")
        watcher_pools = build_reward_pools("WATCHER")

        assert ironclad_pools[CardRarity.COMMON]
        assert ironclad_pools[CardRarity.UNCOMMON]
        assert ironclad_pools[CardRarity.RARE]
        assert watcher_pools[CardRarity.COMMON]
        assert watcher_pools[CardRarity.UNCOMMON]
        assert watcher_pools[CardRarity.RARE]

        assert {card.id for card in watcher_pools[CardRarity.COMMON]} != {
            card.id for card in ironclad_pools[CardRarity.COMMON]
        }
        assert all(card.id in WATCHER_ALL_DEFS for card in watcher_pools[CardRarity.COMMON])
        assert all(card.id in WATCHER_ALL_DEFS for card in watcher_pools[CardRarity.UNCOMMON])
        assert all(card.id in WATCHER_ALL_DEFS for card in watcher_pools[CardRarity.RARE])


class TestWatcherRunContentFlow:
    def test_run_engine_create_watcher_uses_watcher_content(self):
        engine = RunEngine.create("WATCHERFOUNDATION1", ascension=0, character_class="WATCHER")

        assert engine.state.character_class == "WATCHER"
        assert engine.state.player_hp == 72
        assert engine.state.player_max_hp == 72
        assert engine.state.relics == ["PureWater"]
        assert "Eruption" in engine.state.deck
        assert "Vigilance" in engine.state.deck
        assert "Bash" not in engine.state.deck

    def test_watcher_reward_generation_path_returns_watcher_cards(self):
        engine = RunEngine.create("WATCHERFOUNDATION2", ascension=0, character_class="WATCHER")

        engine._add_card_reward()

        assert len(engine.state.pending_card_reward_cards) == 3
        assert all(card_id in WATCHER_ALL_DEFS for card_id in engine.state.pending_card_reward_cards)
        assert all(card_id not in IRONCLAD_ALL_DEFS for card_id in engine.state.pending_card_reward_cards)
