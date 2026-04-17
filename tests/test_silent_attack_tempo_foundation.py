from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import SILENT_ALL_DEFS, CardRarity, CardType
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.run.run_engine import RunEngine


class TestSilentAttackTempoFoundation:
    def test_attack_tempo_cards_instantiate_with_expected_metadata(self):
        backstab = CardInstance("Backstab")
        bane = CardInstance("Bane")
        caltrops = CardInstance("Caltrops")
        dagger_spray = CardInstance("DaggerSpray")
        deflect = CardInstance("Deflect")
        dodge_and_roll = CardInstance("DodgeAndRoll")
        flying_knee = CardInstance("FlyingKnee")
        all_out_attack = CardInstance("AllOutAttack")
        predator = CardInstance("Predator")

        assert backstab.rarity == CardRarity.UNCOMMON
        assert backstab.card_type == CardType.ATTACK
        assert backstab.cost == 0
        assert backstab.damage == 11
        assert backstab.is_innate is True
        assert backstab.exhaust is True

        assert bane.rarity == CardRarity.COMMON
        assert bane.card_type == CardType.ATTACK
        assert bane.cost == 1
        assert bane.damage == 7

        assert caltrops.rarity == CardRarity.UNCOMMON
        assert caltrops.card_type == CardType.POWER
        assert caltrops.cost == 1
        assert caltrops.magic_number == 3

        assert dagger_spray.rarity == CardRarity.COMMON
        assert dagger_spray.card_type == CardType.ATTACK
        assert dagger_spray.cost == 1
        assert dagger_spray.damage == 4

        assert deflect.rarity == CardRarity.COMMON
        assert deflect.card_type == CardType.SKILL
        assert deflect.cost == 0
        assert deflect.block == 4

        assert dodge_and_roll.rarity == CardRarity.COMMON
        assert dodge_and_roll.card_type == CardType.SKILL
        assert dodge_and_roll.cost == 1
        assert dodge_and_roll.block == 4

        assert flying_knee.rarity == CardRarity.COMMON
        assert flying_knee.card_type == CardType.ATTACK
        assert flying_knee.cost == 1
        assert flying_knee.damage == 8

        assert all_out_attack.rarity == CardRarity.UNCOMMON
        assert all_out_attack.card_type == CardType.ATTACK
        assert all_out_attack.cost == 1
        assert all_out_attack.damage == 10

        assert predator.rarity == CardRarity.UNCOMMON
        assert predator.card_type == CardType.ATTACK
        assert predator.cost == 2
        assert predator.damage == 15
        assert predator.magic_number == 2

    def test_attack_tempo_upgrade_entries_and_aliases_work(self):
        assert CardInstance("Backstab+").damage == 15
        assert CardInstance("Bane+").damage == 10
        assert CardInstance("Caltrops+").magic_number == 5
        assert CardInstance("DaggerSpray+").damage == 6
        assert CardInstance("Deflect+").block == 7
        assert CardInstance("DodgeAndRoll+").block == 6
        assert CardInstance("FlyingKnee+").damage == 11
        assert CardInstance("AllOutAttack+").damage == 14
        assert CardInstance("Predator+").damage == 20

        assert CardInstance("Dagger Spray").card_id == "DaggerSpray"
        assert CardInstance("Dodge and Roll").card_id == "DodgeAndRoll"
        assert CardInstance("Flying Knee").card_id == "FlyingKnee"
        assert CardInstance("All Out Attack").card_id == "AllOutAttack"

    def test_reward_pools_include_attack_tempo_cards(self):
        pools = build_reward_pools("SILENT")
        common_ids = {card.id for card in pools[CardRarity.COMMON]}
        uncommon_ids = {card.id for card in pools[CardRarity.UNCOMMON]}

        assert {"Bane", "DaggerSpray", "Deflect", "DodgeAndRoll", "FlyingKnee"} <= common_ids
        assert {"Backstab", "Caltrops", "AllOutAttack", "Predator"} <= uncommon_ids

    def test_reward_generation_can_surface_attack_tempo_cards(self):
        engine = RunEngine.create("SILENTATTACKTEMPO", ascension=0, character_class="SILENT")
        targets = {"Backstab", "Bane", "Caltrops", "DaggerSpray", "Deflect", "DodgeAndRoll", "FlyingKnee", "AllOutAttack", "Predator"}
        seen = False
        for _ in range(100):
            engine._add_card_reward()
            if any(card_id in targets for card_id in engine.state.pending_card_reward_cards):
                seen = True
                break

        assert seen is True
        assert all(card_id in SILENT_ALL_DEFS for card_id in engine.state.pending_card_reward_cards)
