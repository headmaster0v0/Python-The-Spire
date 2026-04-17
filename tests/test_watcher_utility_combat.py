from __future__ import annotations

from sts_py.engine.combat.card_effects import (
    ApplyPowerEffect,
    ChangeStanceEffect,
    EndTurnEffect,
    InnerPeaceEffect,
    RecoverFromDiscardEffect,
    get_card_effects,
)
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
from sts_py.engine.combat.stance import StanceType
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


class TestWatcherUtilityCardEffects:
    def test_meditate_effects_recover_stance_and_end_turn(self):
        effects = get_card_effects(CardInstance("Meditate"))

        assert len(effects) == 3
        assert isinstance(effects[0], RecoverFromDiscardEffect)
        assert isinstance(effects[1], ChangeStanceEffect)
        assert isinstance(effects[2], EndTurnEffect)

    def test_inner_peace_effects_are_conditional(self):
        effects = get_card_effects(CardInstance("InnerPeace"))

        assert len(effects) == 1
        assert isinstance(effects[0], InnerPeaceEffect)

    def test_like_water_nirvana_and_rushdown_apply_powers(self):
        for card_id in ["LikeWater", "Nirvana", "Rushdown"]:
            effects = get_card_effects(CardInstance(card_id))
            assert len(effects) == 1
            assert isinstance(effects[0], ApplyPowerEffect)
            assert effects[0].power_type == card_id


class TestWatcherUtilityCombatIntegration:
    def test_meditate_recovers_cards_enters_calm_and_ends_turn(self):
        combat = _make_combat(attack_damage=0)
        recovered = CardInstance("Wallop")
        _set_piles(combat, hand_ids=["Meditate"], discard_cards=[recovered, "Burn"])

        assert combat.play_card(0)

        hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
        assert combat.state.phase.name == "PLAYER_TURN"
        assert combat.state.player.stance is not None
        assert combat.state.player.stance.stance_type == StanceType.CALM
        assert "Wallop" in hand_ids
        assert recovered in combat.state.card_manager.hand.cards
        assert recovered.retain is False

    def test_inner_peace_enters_calm_when_not_already_in_calm(self):
        combat = _make_combat()
        _set_piles(combat, hand_ids=["InnerPeace"])

        assert combat.play_card(0)
        assert combat.state.player.stance is not None
        assert combat.state.player.stance.stance_type == StanceType.CALM

    def test_inner_peace_draws_when_already_in_calm(self):
        combat = _make_combat()
        _set_piles(combat, hand_ids=["Vigilance", "InnerPeace"], draw_ids=["Strike", "Defend", "Wallop"])

        assert combat.play_card(0)
        assert combat.state.player.stance is not None
        assert combat.state.player.stance.stance_type == StanceType.CALM

        assert combat.play_card(0)
        hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
        assert hand_ids == ["Wallop", "Defend", "Strike"]

    def test_nirvana_grants_block_after_scry(self):
        combat = _make_combat()
        _set_piles(combat, hand_ids=["Nirvana", "ThirdEye"], draw_ids=["Strike", "Burn", "Defend"])

        assert combat.play_card(0)
        assert combat.play_card(0)

        assert combat.state.player.block == 10

    def test_rushdown_draws_when_entering_wrath(self):
        combat = _make_combat(monster_hp=80)
        _set_piles(combat, hand_ids=["Rushdown", "Eruption"], draw_ids=["Strike", "Wallop"])

        assert combat.play_card(0)
        assert combat.play_card(0, 0)

        hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
        assert hand_ids == ["Wallop", "Strike"]
        assert combat.state.player.stance is not None
        assert combat.state.player.stance.stance_type == StanceType.WRATH

    def test_rushdown_does_not_retrigger_when_already_in_wrath(self):
        combat = _make_combat()
        _set_piles(combat, draw_ids=["Strike", "Wallop"])
        combat.state.player.add_power(create_power("Rushdown", 2, "player"))

        combat._change_player_stance(StanceType.WRATH)
        first_hand = [card.card_id for card in combat.state.card_manager.hand.cards]
        combat._change_player_stance(StanceType.WRATH)
        second_hand = [card.card_id for card in combat.state.card_manager.hand.cards]

        assert first_hand == ["Wallop", "Strike"]
        assert second_hand == first_hand

    def test_like_water_grants_block_before_monster_attack(self):
        combat = _make_combat(attack_damage=4)
        _set_piles(combat, hand_ids=["LikeWater", "Vigilance"])

        assert combat.play_card(0)
        assert combat.play_card(0)
        combat.end_player_turn()

        assert combat.state.phase.name == "PLAYER_TURN"
        assert combat.state.player.hp == 72
