from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance, create_starter_deck
from sts_py.engine.content.cards_min import IRONCLAD_ALL_DEFS, SILENT_ALL_DEFS, WATCHER_ALL_DEFS, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestSilentCardInstanceFoundation:
    def test_silent_cards_instantiate_with_static_metadata(self):
        neutralize = CardInstance("Neutralize")
        survivor = CardInstance("Survivor")
        backflip = CardInstance("Backflip")
        adrenaline = CardInstance("Adrenaline")

        assert neutralize.rarity == CardRarity.BASIC
        assert neutralize.card_type == CardType.ATTACK
        assert neutralize.cost == 0
        assert neutralize.base_damage == 3
        assert neutralize.base_magic_number == 1

        assert survivor.rarity == CardRarity.BASIC
        assert survivor.card_type == CardType.SKILL
        assert survivor.cost == 1
        assert survivor.base_block == 8

        assert backflip.rarity == CardRarity.COMMON
        assert backflip.card_type == CardType.SKILL
        assert backflip.cost == 1
        assert backflip.base_block == 5
        assert backflip.base_magic_number == 2

        assert adrenaline.rarity == CardRarity.RARE
        assert adrenaline.card_type == CardType.SKILL
        assert adrenaline.cost == 0
        assert adrenaline.base_magic_number == 1
        assert adrenaline.exhaust is True

    def test_silent_upgraded_card_id_entry_still_works(self):
        neutralize = CardInstance("Neutralize+")
        die_die_die = CardInstance("DieDieDie+")

        assert neutralize.upgraded
        assert neutralize.base_damage == 4
        assert neutralize.base_magic_number == 2

        assert die_die_die.upgraded
        assert die_die_die.base_damage == 17

    def test_silent_starter_deck_builder(self):
        deck = create_starter_deck("SILENT")
        ids = [card.card_id for card in deck]

        assert len(ids) == 12
        assert ids.count("Strike") == 5
        assert ids.count("Defend") == 5
        assert "Neutralize" in ids
        assert "Survivor" in ids
        assert "Bash" not in ids


class TestSilentRewardPools:
    def test_reward_pools_build_by_character(self):
        ironclad_pools = build_reward_pools("IRONCLAD")
        silent_pools = build_reward_pools("SILENT")
        watcher_pools = build_reward_pools("WATCHER")

        assert ironclad_pools[CardRarity.COMMON]
        assert silent_pools[CardRarity.COMMON]
        assert silent_pools[CardRarity.UNCOMMON]
        assert silent_pools[CardRarity.RARE]
        assert watcher_pools[CardRarity.COMMON]

        assert {card.id for card in silent_pools[CardRarity.COMMON]} != {
            card.id for card in ironclad_pools[CardRarity.COMMON]
        }
        assert all(card.id in SILENT_ALL_DEFS for card in silent_pools[CardRarity.COMMON])
        assert all(card.id in SILENT_ALL_DEFS for card in silent_pools[CardRarity.UNCOMMON])
        assert all(card.id in SILENT_ALL_DEFS for card in silent_pools[CardRarity.RARE])
        assert all(card.id not in IRONCLAD_ALL_DEFS for card in silent_pools[CardRarity.COMMON])
        assert all(card.id not in WATCHER_ALL_DEFS for card in silent_pools[CardRarity.COMMON])


class TestSilentRunContentFlow:
    def test_run_engine_create_silent_uses_silent_content(self):
        engine = RunEngine.create("SILENTFOUNDATION1", ascension=0, character_class="SILENT")

        assert engine.state.character_class == "SILENT"
        assert engine.state.player_hp == 70
        assert engine.state.player_max_hp == 70
        assert engine.state.relics == ["RingOfTheSnake"]
        assert "Neutralize" in engine.state.deck
        assert "Survivor" in engine.state.deck
        assert "Bash" not in engine.state.deck

    def test_silent_reward_generation_path_returns_silent_cards(self):
        engine = RunEngine.create("SILENTFOUNDATION2", ascension=0, character_class="SILENT")

        engine._add_card_reward()

        assert len(engine.state.pending_card_reward_cards) == 3
        assert all(card_id in SILENT_ALL_DEFS for card_id in engine.state.pending_card_reward_cards)
        assert all(card_id not in IRONCLAD_ALL_DEFS for card_id in engine.state.pending_card_reward_cards)
        assert all(card_id not in WATCHER_ALL_DEFS for card_id in engine.state.pending_card_reward_cards)

    def test_ring_of_the_snake_draws_two_extra_on_battle_start(self):
        engine = RunEngine.create("SILENTFOUNDATION3", ascension=0, character_class="SILENT")

        engine.start_combat_with_monsters(["JawWorm"])

        assert engine.state.combat is not None
        assert len(engine.state.combat.state.card_manager.hand.cards) == 7
