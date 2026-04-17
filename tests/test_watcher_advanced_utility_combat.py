from __future__ import annotations

from sts_py.engine.combat.card_effects import (
    ApplyPowerEffect,
    ChangeStanceEffect,
    EndTurnEffect,
    SkipEnemyTurnEffect,
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


class TestWatcherAdvancedUtilityCardEffects:
    def test_blasphemy_effects_enter_divinity_and_apply_end_turn_death(self):
        effects = get_card_effects(CardInstance("Blasphemy"))

        assert len(effects) == 2
        assert isinstance(effects[0], ChangeStanceEffect)
        assert effects[0].stance_type == StanceType.DIVINITY
        assert isinstance(effects[1], ApplyPowerEffect)
        assert effects[1].power_type == "EndTurnDeath"

    def test_vault_effects_skip_enemy_turn_and_end_turn(self):
        effects = get_card_effects(CardInstance("Vault"))

        assert len(effects) == 2
        assert isinstance(effects[0], SkipEnemyTurnEffect)
        assert isinstance(effects[1], EndTurnEffect)

    def test_blasphemy_plus_has_self_retain_metadata(self):
        card = CardInstance("Blasphemy", upgraded=True)

        assert card.upgraded is True
        assert card.self_retain is True
        assert card.retain is True

    def test_deus_ex_machina_is_unplayable(self):
        card = CardInstance("DeusExMachina")

        assert card.is_unplayable is True
        assert get_card_effects(card) == []


class TestWatcherAdvancedUtilityCombatIntegration:
    def test_blasphemy_enters_divinity_immediately(self):
        combat = _make_combat(attack_damage=0)
        _set_piles(combat, hand_ids=["Blasphemy"])

        assert combat.play_card(0)
        assert combat.state.player.stance is not None
        assert combat.state.player.stance.stance_type == StanceType.DIVINITY
        assert combat.state.player.powers.has_power("EndTurnDeath")

    def test_blasphemy_kills_player_at_next_start_of_turn(self):
        combat = _make_combat(attack_damage=0)
        _set_piles(combat, hand_ids=["Blasphemy"], draw_ids=["Strike"])

        assert combat.play_card(0)
        combat.end_player_turn()

        assert combat.state.phase.name == "PLAYER_TURN"
        assert combat.state.player.hp == 0
        assert combat.state.player.is_dead()
        assert combat.state.player.powers.has_power("EndTurnDeath") is False

    def test_deus_ex_machina_triggers_on_draw_and_generates_miracles(self):
        combat = _make_combat()
        _set_piles(combat, draw_ids=["DeusExMachina"])

        drawn = combat.state.card_manager.draw_card(combat.ai_rng)

        assert drawn is not None
        assert drawn.card_id == "DeusExMachina"
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Miracle", "Miracle"]
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["DeusExMachina"]

    def test_generated_miracle_can_be_played_same_turn(self):
        combat = _make_combat()
        _set_piles(combat, draw_ids=["DeusExMachina"])
        combat.state.player.energy = 0
        combat.state.card_manager.set_energy(0)

        combat.state.card_manager.draw_card(combat.ai_rng)

        assert combat.play_card(0)
        assert combat.state.player.energy == 1
        assert combat.state.card_manager.energy == 1
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Miracle"]

    def test_deus_ex_machina_cannot_be_played_from_hand(self):
        combat = _make_combat()
        _set_piles(combat, hand_ids=["DeusExMachina"])

        assert combat.play_card(0) is False
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["DeusExMachina"]

    def test_vault_skips_enemy_turn_and_starts_next_player_turn(self):
        combat = _make_combat(attack_damage=9)
        _set_piles(combat, hand_ids=["Vault"], draw_ids=["Strike", "Defend"])
        combat.state.player.add_power(create_power("Devotion", 2, "player"))

        assert combat.play_card(0)

        assert combat.state.phase.name == "PLAYER_TURN"
        assert combat.state.player.hp == 72
        assert combat.state.player.energy == combat.state.player.max_energy
        assert combat.state.player.get_power_amount("Mantra") == 2
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Defend", "Strike"]
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Vault"]
