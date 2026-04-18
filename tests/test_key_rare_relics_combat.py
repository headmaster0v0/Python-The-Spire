"""Comprehensive combat verification tests for key rare relics."""
import pytest
from sts_py.engine.combat.card_effects import _trigger_exhaust_hooks
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.content.relics import get_relic_by_id, RelicEffectType


class TestLizardTailRelic:
    """Test Lizard Tail: Revives at 50% max HP when dying."""

    def test_lizard_tail_definition(self):
        """Lizard Tail should have ON_DEATH_SAVE effect."""
        relic = get_relic_by_id("LizardTail")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.ON_DEATH_SAVE
        assert effect.extra.get("type") == "revive_half_hp"

    def test_lizard_tail_revive_at_half_hp(self):
        """Lizard Tail should revive player at 50% max HP when dying."""
        ai_rng = MutableRNG.from_seed(12345, counter=50)
        hp_rng = MutableRNG.from_seed(67890, counter=100)

        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80, player_max_hp=80,
            ai_rng=ai_rng, hp_rng=hp_rng,
            relics=["LizardTail"],
        )

        player = combat.state.player
        player.hp = 0

        combat._trigger_relic_effects("on_death_save")

        assert player.hp == 40, f"Expected 40 HP (50% of 80), got {player.hp}"


class TestTheSpecimenRelic:
    """Test The Specimen: Poison transfers to random enemy on death."""

    def test_the_specimen_definition(self):
        """The Specimen should have ON_ENEMY_DEATH_POISON_TRANSFER effect."""
        relic = get_relic_by_id("生物样本")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.ON_ENEMY_DEATH_POISON_TRANSFER


class TestThreadAndNeedle:
    """Test Thread and Needle: Battle start gives 4 plated armor."""

    def test_thread_and_needle_definition(self):
        """Thread and Needle should have AT_BATTLE_START with plated_armor."""
        relic = get_relic_by_id("针线")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.AT_BATTLE_START
        assert effect.value == 4
        assert effect.extra.get("type") == "plated_armor"

    def test_thread_and_needle_plated_armor_effect(self):
        """Thread and Needle effect should add 4 plated armor."""
        relic = get_relic_by_id("针线")
        effect = relic.effects[0]
        assert effect.extra.get("type") == "plated_armor"
        assert effect.value == 4


class TestFossilizedHelix:
    """Test FossilizedHelix: Battle start gives 1 buffer."""

    def test_fossilized_helix_definition(self):
        """FossilizedHelix should have AT_BATTLE_START_BUFFER effect."""
        relic = get_relic_by_id("螺类化石")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.AT_BATTLE_START_BUFFER


class TestTorii:
    """Test Torii: Damage <= 5 is reduced to 1."""

    def test_torii_definition(self):
        """Torii should have MODIFY_DAMAGE with min_damage_receive."""
        relic = get_relic_by_id("鸟居")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.MODIFY_DAMAGE
        assert effect.extra.get("type") == "min_damage_receive"
        assert effect.extra.get("max") == 5


class TestTingshaAndToughBandages:
    """Test Tingsha (3 damage on discard) and Tough Bandages (3 block on discard)."""

    def test_tingsha_definition(self):
        """Tingsha should deal 3 damage to random enemy on discard."""
        relic = get_relic_by_id("铜钹")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.ON_DISCARD
        assert effect.value == 3
        assert effect.extra.get("type") == "damage_random"

    def test_tough_bandages_definition(self):
        """Tough Bandages should give 3 block on discard."""
        relic = get_relic_by_id("结实绷带")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.ON_DISCARD
        assert effect.value == 3
        assert effect.extra.get("type") == "block"


class TestDuVuDoll:
    """Test Du-Vu Doll: +1 strength per curse in deck."""

    def test_du_vu_doll_definition(self):
        """Du-Vu Doll should have START_WITH_STRENGTH_PER_CURSE effect."""
        relic = get_relic_by_id("毒巫娃娃")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.START_WITH_STRENGTH_PER_CURSE
        assert effect.value == 1


class TestMagicFlower:
    """Test Magic Flower: Heal multiplier x2."""

    def test_magic_flower_definition(self):
        """Magic Flower should have HEAL_MULTIPLY effect."""
        relic = get_relic_by_id("魔法花")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.HEAL_MULTIPLY
        assert effect.value == 2


class TestOddMushroom:
    """Test Odd Mushroom: +25% damage when Vulnerable."""

    def test_odd_mushroom_definition(self):
        """Odd Mushroom should increase damage when Vulnerable."""
        relic = get_relic_by_id("奇怪蘑菇")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.MODIFY_VULNERABLE
        assert effect.value == 25
        assert effect.extra.get("type") == "extra_damage_percent"


class TestDeadBranch:
    """Test Dead Branch: Add random card on exhaust."""

    def test_dead_branch_definition(self):
        """Dead Branch should have ON_EXHAUST_ADD_RANDOM effect."""
        relic = get_relic_by_id("枯木树枝")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.ON_EXHAUST_ADD_RANDOM


class TestSneckoEyeAndVelvetChoker:
    """Test Snecko Eye and Velvet Choker: Card draw limits."""

    def test_snecko_eye_definition(self):
        """Snecko Eye should give confused + extra draw."""
        relic = get_relic_by_id("斯内克之眼")
        assert relic is not None
        effect_types = [e.effect_type for e in relic.effects]
        assert RelicEffectType.AT_BATTLE_START in effect_types
        assert RelicEffectType.LIMIT_CARDS_DRAW in effect_types

    def test_velvet_choker_definition(self):
        """Velvet Choker should give 1 energy + 6 card limit."""
        relic = get_relic_by_id("VelvetChoker")
        assert relic is not None
        effect_types = [e.effect_type for e in relic.effects]
        assert RelicEffectType.START_WITH_ENERGY in effect_types
        assert RelicEffectType.LIMIT_CARDS_PLAY in effect_types


class TestRunicPyramid:
    """Test Runic Pyramid: Cards not discarded at end of turn."""

    def test_runic_pyramid_definition(self):
        """Runic Pyramid should have AT_TURN_END_NO_DISCARD effect."""
        relic = get_relic_by_id("RunicPyramid")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.AT_TURN_END_NO_DISCARD

    def test_runic_pyramid_keeps_non_ethereal_cards_without_opening_retain_choice(self):
        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(12345, counter=50),
            hp_rng=MutableRNG.from_seed(67890, counter=100),
            relics=["RunicPyramid"],
        )

        cm = combat.state.card_manager
        assert cm is not None
        dazed = CardInstance("Dazed")
        strike = CardInstance("Strike")
        defend = CardInstance("Defend")
        for card in (dazed, strike, defend):
            card._combat_state = combat.state
        cm.hand.cards = [dazed, strike, defend]
        cm.draw_pile.cards = []
        cm.discard_pile.cards = []
        cm.exhaust_pile.cards = []

        combat.end_player_turn()

        assert combat.state.pending_combat_choice is None
        assert [card.card_id for card in cm.hand.cards] == ["Strike", "Defend"]
        assert [card.card_id for card in cm.exhaust_pile.cards] == ["Dazed"]


class TestSneckoEyeConfused:
    """Test Snecko Eye confused state implementation."""

    def test_snecko_eye_confused_effect(self):
        """Snecko Eye should apply confused status at battle start."""
        relic = get_relic_by_id("斯内克之眼")
        assert relic is not None

        at_battle_effects = [e for e in relic.effects if e.effect_type == RelicEffectType.AT_BATTLE_START]
        assert len(at_battle_effects) > 0
        assert at_battle_effects[0].extra.get("type") == "confused"


class TestIncenseBurner:
    """Test Incense Burner: Every 6 turns, gain Intangible."""

    def test_incense_burner_definition(self):
        """Incense Burner should have EVERY_N_TURNS with intangible."""
        relic = get_relic_by_id("香炉")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.EVERY_N_TURNS
        assert effect.value == 6
        assert effect.extra.get("type") == "intangible"


class TestNuclearBattery:
    """Test Nuclear Battery: Start battle with 1 Plasma Orb."""

    def test_nuclear_battery_definition(self):
        """Nuclear Battery should have AT_BATTLE_START with plasma_orb."""
        relic = get_relic_by_id("核电池")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.AT_BATTLE_START
        assert effect.extra.get("type") == "plasma_orb"
        assert effect.value == 1


class TestInserter:
    """Test Inserter: Start of turn, gain 1 orb slot."""

    def test_inserter_definition(self):
        """Inserter should have EVERY_2_TURNS with orb_slot."""
        relic = get_relic_by_id("机械臂")
        assert relic is not None
        effect = relic.effects[0]
        assert effect.effect_type == RelicEffectType.EVERY_2_TURNS
        assert effect.extra.get("type") == "orb_slot"
        assert effect.value == 1


class TestRareRelicBehaviorTruth:
    def test_thread_and_needle_applies_plated_armor_at_battle_start(self):
        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(12345, counter=50),
            hp_rng=MutableRNG.from_seed(67890, counter=100),
            relics=["ThreadAndNeedle"],
        )

        assert getattr(combat.state.player, "plated_armor", 0) == 4

    def test_fossilized_helix_prevents_first_hit_and_consumes_buffer(self):
        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(12345, counter=50),
            hp_rng=MutableRNG.from_seed(67890, counter=100),
            relics=["FossilizedHelix"],
        )

        player = combat.state.player
        assert player.get_power_amount("Buffer") == 1
        dealt = player.take_damage(10)
        assert dealt == 0
        assert player.hp == 80
        assert player.get_power_amount("Buffer") == 0

    def test_snecko_eye_applies_confused_and_extra_draw(self):
        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(12345, counter=50),
            hp_rng=MutableRNG.from_seed(67890, counter=100),
            relics=["SneckoEye"],
        )

        assert combat.state.player.has_power("Confused")
        assert combat.state.card_manager is not None
        assert len(combat.state.card_manager.hand.cards) == 7

    def test_velvet_choker_blocks_seventh_card_play(self):
        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(12345, counter=50),
            hp_rng=MutableRNG.from_seed(67890, counter=100),
            relics=["VelvetChoker"],
        )

        combat.state.player.energy = 10
        cm = combat.state.card_manager
        assert cm is not None
        cm.hand.cards = [CardInstance("Shiv") for _ in range(7)]

        for _ in range(6):
            assert combat.play_card(0, target_idx=0) is True

        assert combat.play_card(0, target_idx=0) is False

    def test_tingsha_and_tough_bandages_trigger_on_discard(self):
        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(12345, counter=50),
            hp_rng=MutableRNG.from_seed(67890, counter=100),
            relics=["Tingsha", "ToughBandages"],
        )

        monster = combat.state.monsters[0]
        hp_before = monster.hp
        combat._handle_player_discard_from_hand(CardInstance("Defend"))

        assert hp_before - monster.hp == 3
        assert combat.state.player.block == 3

    def test_dead_branch_adds_generated_card_on_exhaust(self):
        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(12345, counter=50),
            hp_rng=MutableRNG.from_seed(67890, counter=100),
            relics=["DeadBranch"],
        )

        cm = combat.state.card_manager
        assert cm is not None
        cm.hand.cards = [CardInstance("Strike")]
        hand_before = len(cm.hand.cards)
        _trigger_exhaust_hooks(cm, combat.state.player, CardInstance("Defend"))

        assert len(cm.hand.cards) == hand_before + 1

    def test_magic_flower_amplifies_burning_blood_victory_heal(self):
        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=60,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(12345, counter=50),
            hp_rng=MutableRNG.from_seed(67890, counter=100),
            relics=["BurningBlood", "MagicFlower"],
        )

        assert combat.trigger_victory_effects() == 9

    def test_torii_reduces_small_damage_to_one(self):
        combat = CombatEngine.create(
            encounter_name="Cultist",
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(12345, counter=50),
            hp_rng=MutableRNG.from_seed(67890, counter=100),
            relics=["Torii"],
        )

        dealt = combat.state.player.take_damage(5)
        assert dealt == 1
        assert combat.state.player.hp == 79

    def test_stone_calendar_hits_all_enemies_on_seventh_turn_end(self):
        combat = CombatEngine.create(
            encounter_name="Donu and Deca",
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(12345, counter=50),
            hp_rng=MutableRNG.from_seed(67890, counter=100),
            relics=["StoneCalendar"],
        )

        hp_before = [monster.hp for monster in combat.state.monsters]
        for _ in range(6):
            combat._trigger_relic_effects("at_turn_end")
        assert [monster.hp for monster in combat.state.monsters] == hp_before

        combat._trigger_relic_effects("at_turn_end")
        assert [before - monster.hp for before, monster in zip(hp_before, combat.state.monsters)] == [52]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
