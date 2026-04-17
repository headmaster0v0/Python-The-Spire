from __future__ import annotations

from sts_py.engine.combat.card_effects import (
    ApplyPowerEffect,
    DrawCardsEffect,
    GenerateCardsToHandEffect,
    GainBlockEffect,
    GainMantraEffect,
    MakeTempCardInDrawPileEffect,
    get_card_effects,
)
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, hp: int = 80, attack_damage: int = 0):
        super().__init__(id="DummyAttack", name="Dummy Attack", hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hp: int = 80, attack_damage: int = 0) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monster = DummyAttackMonster(hp=monster_hp, attack_damage=attack_damage)
    return CombatEngine.create_with_monsters(
        monsters=[monster],
        player_hp=72,
        player_max_hp=72,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Strike", "Strike", "Strike", "Defend", "Defend", "Defend", "Defend", "Eruption", "Vigilance"],
        relics=[],
    )


def _bind_cards(combat: CombatEngine, cards: list[CardInstance]) -> list[CardInstance]:
    for card in cards:
        card._combat_state = combat.state
    return cards


def _set_piles(
    combat: CombatEngine,
    *,
    hand_ids: list[str] | None = None,
    draw_ids: list[str] | None = None,
    discard_cards: list[str | CardInstance] | None = None,
) -> None:
    combat.state.card_manager.hand.cards = _bind_cards(
        combat,
        [CardInstance(card_id) for card_id in (hand_ids or [])],
    )
    combat.state.card_manager.draw_pile.cards = _bind_cards(
        combat,
        [CardInstance(card_id) for card_id in (draw_ids or [])],
    )

    discard_instances: list[CardInstance] = []
    for card in discard_cards or []:
        instance = card if isinstance(card, CardInstance) else CardInstance(card)
        discard_instances.append(instance)
    combat.state.card_manager.discard_pile.cards = _bind_cards(combat, discard_instances)
    combat.state.card_manager.exhaust_pile.cards = []


class TestWatcherGeneratedCardEffects:
    def test_insight_metadata_and_upgrade(self):
        card = CardInstance("Insight")
        upgraded = CardInstance("Insight", upgraded=True)

        assert card.retain is True
        assert card.self_retain is True
        assert card.exhaust is True
        assert card.magic_number == 2
        assert upgraded.magic_number == 3

    def test_insight_effect_draws_cards(self):
        effects = get_card_effects(CardInstance("Insight"))

        assert len(effects) == 1
        assert isinstance(effects[0], DrawCardsEffect)
        assert effects[0].count == 2

    def test_study_effect_applies_study_power(self):
        effects = get_card_effects(CardInstance("Study"))

        assert len(effects) == 1
        assert isinstance(effects[0], ApplyPowerEffect)
        assert effects[0].power_type == "Study"

    def test_master_reality_effect_applies_power(self):
        effects = get_card_effects(CardInstance("MasterReality"))

        assert len(effects) == 1
        assert isinstance(effects[0], ApplyPowerEffect)
        assert effects[0].power_type == "MasterReality"

    def test_pray_effects_gain_mantra_and_generate_insight(self):
        effects = get_card_effects(CardInstance("Pray"))

        assert len(effects) == 2
        assert isinstance(effects[0], GainMantraEffect)
        assert effects[0].amount == 3
        assert isinstance(effects[1], MakeTempCardInDrawPileEffect)
        assert effects[1].card_id == "Insight"

    def test_evaluate_effects_gain_block_and_generate_insight(self):
        effects = get_card_effects(CardInstance("Evaluate"))

        assert len(effects) == 2
        assert isinstance(effects[0], GainBlockEffect)
        assert effects[0].amount == 6
        assert isinstance(effects[1], MakeTempCardInDrawPileEffect)
        assert effects[1].card_id == "Insight"

    def test_generated_temp_card_metadata_and_generator_effects_exist(self):
        safety = CardInstance("Safety")
        smite = CardInstance("Smite")
        through_violence = CardInstance("ThroughViolence")

        assert safety.retain is True
        assert safety.exhaust is True
        assert safety.block == 12
        assert smite.retain is True
        assert smite.exhaust is True
        assert smite.damage == 12
        assert through_violence.retain is True
        assert through_violence.cost == 0
        assert through_violence.damage == 20

        battle_hymn_effects = get_card_effects(CardInstance("BattleHymn"))
        carve_effects = get_card_effects(CardInstance("CarveReality"), target_idx=0)
        deceive_effects = get_card_effects(CardInstance("DeceiveReality"))
        reach_effects = get_card_effects(CardInstance("ReachHeaven"), target_idx=0)

        assert isinstance(battle_hymn_effects[0], ApplyPowerEffect)
        assert battle_hymn_effects[0].power_type == "BattleHymn"
        assert isinstance(carve_effects[1], GenerateCardsToHandEffect)
        assert carve_effects[1].card_id == "Smite"
        assert isinstance(deceive_effects[1], GenerateCardsToHandEffect)
        assert deceive_effects[1].card_id == "Safety"
        assert isinstance(reach_effects[1], MakeTempCardInDrawPileEffect)
        assert reach_effects[1].card_id == "ThroughViolence"


class TestWatcherGeneratedCardIntegration:
    def test_insight_draws_two_and_upgraded_draws_three(self):
        combat = _make_combat()
        _set_piles(combat, hand_ids=["Insight", "Insight+"], draw_ids=["Strike", "Defend", "Wallop", "Vigilance", "Eruption"])

        assert combat.play_card(0)
        hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
        assert hand_ids == ["Insight", "Eruption", "Vigilance"]

        assert combat.play_card(0)
        hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
        assert hand_ids == ["Eruption", "Vigilance", "Wallop", "Defend", "Strike"]

    def test_study_generates_insight_into_draw_pile_at_end_turn_hook(self):
        combat = _make_combat()
        _set_piles(combat, hand_ids=["Study"], draw_ids=[])

        assert combat.play_card(0)
        combat.state.card_manager.end_turn()
        combat.state.player.powers.at_end_of_turn(combat.state.player, True)

        draw_ids = [card.card_id for card in combat.state.card_manager.draw_pile.cards]
        assert draw_ids == ["Insight"]
        assert isinstance(combat.state.card_manager.draw_pile.cards[0], CardInstance)

    def test_study_generated_insight_can_be_drawn_next_turn_and_played(self):
        combat = _make_combat(attack_damage=0)
        _set_piles(combat, hand_ids=["Study"], draw_ids=[])

        assert combat.play_card(0)
        combat.end_player_turn()

        hand = combat.state.card_manager.hand.cards
        assert combat.state.phase.name == "PLAYER_TURN"
        insight_index = next(index for index, card in enumerate(hand) if card.card_id == "Insight")
        assert isinstance(hand[insight_index], CardInstance)
        assert hand[insight_index].retain is True
        assert combat.play_card(insight_index)

    def test_master_reality_upgrades_study_generated_insight(self):
        combat = _make_combat(attack_damage=0)
        _set_piles(combat, hand_ids=["MasterReality", "Study"], draw_ids=[])

        assert combat.play_card(0)
        assert combat.play_card(0)
        combat.end_player_turn()

        hand = combat.state.card_manager.hand.cards
        generated_insight = next(card for card in hand if card.card_id == "Insight")
        assert generated_insight.upgraded is True
        assert generated_insight.magic_number == 3

    def test_master_reality_upgrades_deus_ex_machina_miracles(self):
        combat = _make_combat()
        _set_piles(combat, draw_ids=["DeusExMachina"])
        combat.state.player.add_power(create_power("MasterReality", 1, "player"))
        combat.state.player.energy = 0
        combat.state.card_manager.set_energy(0)

        combat.state.card_manager.draw_card(combat.ai_rng)

        miracles = combat.state.card_manager.hand.cards
        assert len(miracles) == 2
        assert all(card.card_id == "Miracle" for card in miracles)
        assert all(card.upgraded for card in miracles)

        assert combat.play_card(0)
        assert combat.state.player.energy == 2

    def test_master_reality_does_not_upgrade_status_cards(self):
        combat = _make_combat()
        combat.state.player.add_power(create_power("MasterReality", 1, "player"))

        generated = combat.state.card_manager.generate_cards_to_hand("Burn", 1)

        assert len(generated) == 1
        assert generated[0].card_id == "Burn"
        assert generated[0].upgraded is False

    def test_pray_adds_mantra_and_generates_insight_to_draw_pile(self):
        combat = _make_combat()
        _set_piles(combat, hand_ids=["Pray"], draw_ids=["Strike"])

        assert combat.play_card(0)

        draw_ids = [card.card_id for card in combat.state.card_manager.draw_pile.cards]
        assert combat.state.player.get_power_amount("Mantra") == 3
        assert "Insight" in draw_ids
        assert "Strike" in draw_ids

    def test_evaluate_gains_block_and_generates_insight_to_draw_pile(self):
        combat = _make_combat()
        _set_piles(combat, hand_ids=["Evaluate"], draw_ids=["Strike"])

        assert combat.play_card(0)

        draw_ids = [card.card_id for card in combat.state.card_manager.draw_pile.cards]
        assert combat.state.player.block == 6
        assert "Insight" in draw_ids
        assert "Strike" in draw_ids

    def test_master_reality_upgrades_pray_and_evaluate_generated_insight(self):
        for card_id in ["Pray", "Evaluate"]:
            combat = _make_combat()
            _set_piles(combat, hand_ids=["MasterReality", card_id], draw_ids=[])

            assert combat.play_card(0)
            assert combat.play_card(0)

            draw_cards = combat.state.card_manager.draw_pile.cards
            generated_insight = next(card for card in draw_cards if card.card_id == "Insight")
            assert generated_insight.upgraded is True
            assert generated_insight.magic_number == 3

    def test_pray_divinity_transition_does_not_block_insight_generation(self):
        combat = _make_combat()
        _set_piles(combat, hand_ids=["Pray"], draw_ids=[])
        combat.state.player.add_power(create_power("Mantra", 7, "player"))

        assert combat.play_card(0)

        assert combat.state.player.stance is not None
        assert combat.state.player.stance.stance_type.name == "DIVINITY"
        assert any(card.card_id == "Insight" for card in combat.state.card_manager.draw_pile.cards)

    def test_battle_hymn_generates_smite_at_start_of_turn(self):
        combat = _make_combat(attack_damage=0)
        _set_piles(combat, hand_ids=["BattleHymn"], draw_ids=[])

        assert combat.play_card(0)
        combat.end_player_turn()

        assert any(card.card_id == "Smite" for card in combat.state.card_manager.hand.cards)

    def test_carve_reality_deceive_reality_and_reach_heaven_generate_real_cards(self):
        combat = _make_combat(attack_damage=0)
        _set_piles(combat, hand_ids=["CarveReality", "DeceiveReality", "ReachHeaven"], draw_ids=[])

        assert combat.play_card(0, 0)
        assert any(card.card_id == "Smite" for card in combat.state.card_manager.hand.cards)

        deceive_index = next(index for index, card in enumerate(combat.state.card_manager.hand.cards) if card.card_id == "DeceiveReality")
        assert combat.play_card(deceive_index)
        assert any(card.card_id == "Safety" for card in combat.state.card_manager.hand.cards)

        combat.state.player.energy = 10
        combat.state.card_manager.set_energy(10)
        reach_index = next(index for index, card in enumerate(combat.state.card_manager.hand.cards) if card.card_id == "ReachHeaven")
        assert combat.play_card(reach_index, 0)
        assert any(card.card_id == "ThroughViolence" for card in combat.state.card_manager.draw_pile.cards)

    def test_master_reality_upgrades_new_watcher_generated_cards(self):
        combat = _make_combat(attack_damage=0)
        _set_piles(combat, hand_ids=["MasterReality", "DeceiveReality", "ReachHeaven"], draw_ids=[])

        assert combat.play_card(0)
        assert combat.play_card(0)

        safety = next(card for card in combat.state.card_manager.hand.cards if card.card_id == "Safety")
        assert safety.upgraded is True
        assert safety.block == 16

        combat.state.player.energy = 10
        combat.state.card_manager.set_energy(10)
        reach_index = next(index for index, card in enumerate(combat.state.card_manager.hand.cards) if card.card_id == "ReachHeaven")
        assert combat.play_card(reach_index, 0)

        through_violence = next(card for card in combat.state.card_manager.draw_pile.cards if card.card_id == "ThroughViolence")
        assert through_violence.upgraded is True
