from __future__ import annotations

from sts_py.engine.combat.card_effects import ApplyPowerEffect, MakeTempCardInDrawPileEffect, get_card_effects
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, hp: int = 120, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hps: list[int], attack_damage: int = 0) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyAttackMonster(monster_id=f"Dummy{index}", hp=hp, attack_damage=attack_damage)
        for index, hp in enumerate(monster_hps)
    ]
    return CombatEngine.create_with_monsters(
        monsters=monsters,
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
    hand_cards: list[CardInstance] | None = None,
    draw_cards: list[CardInstance] | None = None,
) -> None:
    combat.state.card_manager.hand.cards = _bind_cards(combat, hand_cards or [])
    combat.state.card_manager.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    combat.state.card_manager.discard_pile.cards = []
    combat.state.card_manager.exhaust_pile.cards = []


class TestWatcherAlphaOmegaEffects:
    def test_beta_metadata_and_upgrade(self):
        card = CardInstance("Beta")
        upgraded = CardInstance("Beta", upgraded=True)

        assert card.exhaust is True
        assert card.cost == 2
        assert upgraded.cost == 1

    def test_omega_metadata_and_upgrade(self):
        card = CardInstance("Omega")
        upgraded = CardInstance("Omega", upgraded=True)

        assert card.magic_number == 50
        assert upgraded.magic_number == 60

    def test_alpha_effect_generates_beta(self):
        effects = get_card_effects(CardInstance("Alpha"))

        assert len(effects) == 1
        assert isinstance(effects[0], MakeTempCardInDrawPileEffect)
        assert effects[0].card_id == "Beta"

    def test_beta_effect_generates_omega(self):
        effects = get_card_effects(CardInstance("Beta"))

        assert len(effects) == 1
        assert isinstance(effects[0], MakeTempCardInDrawPileEffect)
        assert effects[0].card_id == "Omega"

    def test_omega_effect_applies_omega_power(self):
        effects = get_card_effects(CardInstance("Omega"))

        assert len(effects) == 1
        assert isinstance(effects[0], ApplyPowerEffect)
        assert effects[0].power_type == "OmegaPower"
        assert effects[0].amount == 50

    def test_alpha_upgrade_is_innate(self):
        upgraded = CardInstance("Alpha", upgraded=True)

        assert upgraded.is_innate is True


class TestWatcherAlphaOmegaIntegration:
    def test_alpha_generates_beta_into_draw_pile(self):
        combat = _make_combat(monster_hps=[120])
        _set_piles(combat, hand_cards=[CardInstance("Alpha")], draw_cards=[])

        assert combat.play_card(0)

        generated = combat.state.card_manager.draw_pile.cards
        assert len(generated) == 1
        assert generated[0].card_id == "Beta"

    def test_beta_generates_omega_into_draw_pile(self):
        combat = _make_combat(monster_hps=[120])
        _set_piles(combat, hand_cards=[CardInstance("Beta")], draw_cards=[])

        assert combat.play_card(0)

        generated = combat.state.card_manager.draw_pile.cards
        assert len(generated) == 1
        assert generated[0].card_id == "Omega"

    def test_generated_beta_and_omega_can_be_drawn_and_played(self):
        combat = _make_combat(monster_hps=[120], attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Alpha")], draw_cards=[])

        assert combat.play_card(0)
        combat.end_player_turn()
        beta_index = next(index for index, card in enumerate(combat.state.card_manager.hand.cards) if card.card_id == "Beta")
        assert combat.play_card(beta_index)
        combat.end_player_turn()
        assert any(card.card_id == "Omega" for card in combat.state.card_manager.hand.cards)

    def test_master_reality_upgrades_generated_beta_and_omega(self):
        combat = _make_combat(monster_hps=[120], attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("MasterReality"), CardInstance("Alpha")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.play_card(0)

        generated_beta = next(card for card in combat.state.card_manager.draw_pile.cards if card.card_id == "Beta")
        assert generated_beta.upgraded is True
        assert generated_beta.cost == 1

        combat.end_player_turn()
        beta_index = next(index for index, card in enumerate(combat.state.card_manager.hand.cards) if card.card_id == "Beta")
        assert combat.play_card(beta_index)

        generated_omega = next(card for card in combat.state.card_manager.draw_pile.cards if card.card_id == "Omega")
        assert generated_omega.upgraded is True
        assert generated_omega.magic_number == 60

    def test_omega_applies_power_and_hits_all_monsters_each_player_end_turn(self):
        combat = _make_combat(monster_hps=[120, 130], attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Omega")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("OmegaPower") == 50

        combat.end_player_turn()
        first_hps = [monster.hp for monster in combat.state.monsters]
        assert first_hps == [70, 80]

        combat.end_player_turn()
        second_hps = [monster.hp for monster in combat.state.monsters]
        assert second_hps == [20, 30]

    def test_direct_omega_power_stack_hits_all_monsters(self):
        combat = _make_combat(monster_hps=[90, 90], attack_damage=0)
        combat.state.player.add_power(create_power("OmegaPower", 30, "player"))

        combat.end_player_turn()

        assert [monster.hp for monster in combat.state.monsters] == [60, 60]
