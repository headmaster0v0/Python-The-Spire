from __future__ import annotations

from sts_py.engine.combat.card_effects import BattleTranceEffect, DualWieldEffect, HavocEffect, WarcryEffect, get_card_effects
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 80, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hps: list[int] | None = None, energy: int = 3) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyAttackMonster(f"Dummy{index}", hp=hp, attack_damage=6)
        for index, hp in enumerate(monster_hps or [80])
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=80,
        player_max_hp=80,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Defend", "BattleTrance", "Bloodletting", "SeeingRed", "Warcry", "Havoc", "DualWield"],
        relics=[],
    )
    combat.state.player.max_energy = energy
    combat.state.player.energy = energy
    combat.state.card_manager.set_max_energy(energy)
    combat.state.card_manager.set_energy(energy)
    return combat


def _bind_cards(combat: CombatEngine, cards: list[CardInstance]) -> list[CardInstance]:
    for card in cards:
        card._combat_state = combat.state
    return cards


def _set_piles(
    combat: CombatEngine,
    *,
    hand_cards: list[CardInstance] | None = None,
    draw_cards: list[CardInstance] | None = None,
    discard_cards: list[CardInstance] | None = None,
) -> None:
    cm = combat.state.card_manager
    cm.hand.cards = _bind_cards(combat, hand_cards or [])
    cm.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    cm.discard_pile.cards = _bind_cards(combat, discard_cards or [])
    cm.exhaust_pile.cards = []


class TestIroncladDrawEnergyUtilityEffects:
    def test_battle_trance_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("BattleTrance"))

        assert len(effects) == 1
        assert isinstance(effects[0], BattleTranceEffect)

    def test_warcry_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("Warcry"))

        assert len(effects) == 1
        assert isinstance(effects[0], WarcryEffect)

    def test_havoc_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("Havoc"))

        assert len(effects) == 1
        assert isinstance(effects[0], HavocEffect)

    def test_dual_wield_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("DualWield"))

        assert len(effects) == 1
        assert isinstance(effects[0], DualWieldEffect)

    def test_seeing_red_and_warcry_use_formal_exhaust_metadata(self):
        assert CardInstance("SeeingRed").exhaust is True
        assert CardInstance("Warcry").exhaust is True

    def test_seeing_red_plus_costs_zero(self):
        assert CardInstance("SeeingRed", upgraded=True).cost == 0


class TestIroncladDrawEnergyUtilityIntegration:
    def test_battle_trance_draws_then_applies_no_draw(self):
        combat = _make_combat()
        _set_piles(
            combat,
            hand_cards=[CardInstance("BattleTrance")],
            draw_cards=[CardInstance("Strike"), CardInstance("Strike"), CardInstance("Defend"), CardInstance("Defend")],
        )

        assert combat.play_card(0)

        assert len(combat.state.card_manager.hand.cards) == 3
        assert combat.state.player.get_power_amount("No Draw") == 1

        combat.state.card_manager.draw_cards(1)

        assert len(combat.state.card_manager.hand.cards) == 3

    def test_battle_trance_plus_draws_four(self):
        combat = _make_combat()
        _set_piles(
            combat,
            hand_cards=[CardInstance("BattleTrance", upgraded=True)],
            draw_cards=[CardInstance("Strike"), CardInstance("Strike"), CardInstance("Defend"), CardInstance("Defend")],
        )

        assert combat.play_card(0)

        assert len(combat.state.card_manager.hand.cards) == 4

    def test_bloodletting_uses_unified_hp_loss_and_grants_energy(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Bloodletting")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.hp == 77
        assert combat.state.player.energy == 5
        assert combat.state.card_manager.energy == 5

    def test_bloodletting_plus_grants_three_energy(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Bloodletting", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.energy == 6

    def test_bloodletting_triggers_rupture(self):
        combat = _make_combat(energy=4)
        _set_piles(combat, hand_cards=[CardInstance("Rupture"), CardInstance("Bloodletting")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.play_card(0)

        assert combat.state.player.strength == 1

    def test_seeing_red_gains_energy_and_exhausts(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("SeeingRed")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.energy == 4
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["SeeingRed"]

    def test_warcry_draws_and_puts_first_non_played_card_on_top_of_draw_pile(self):
        combat = _make_combat()
        _set_piles(
            combat,
            hand_cards=[CardInstance("Warcry"), CardInstance("Strike")],
            draw_cards=[CardInstance("Defend")],
        )

        assert combat.play_card(0)

        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Defend"]
        assert combat.state.card_manager.draw_pile.cards[-1].card_id == "Strike"
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Warcry"]

    def test_havoc_autoplays_top_card_for_free_and_forces_exhaust(self):
        combat = _make_combat(monster_hps=[30])
        strike = CardInstance("Strike")
        _set_piles(combat, hand_cards=[CardInstance("Havoc")], draw_cards=[strike])

        assert combat.play_card(0)

        assert combat.state.player.energy == 2
        assert combat.state.monsters[0].hp == 24
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Strike"]
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Havoc"]
        assert strike in combat.state.card_manager.exhaust_pile.cards

    def test_havoc_targeted_attack_uses_deterministic_combat_rng(self):
        first = _make_combat(monster_hps=[20, 20])
        second = _make_combat(monster_hps=[20, 20])
        _set_piles(first, hand_cards=[CardInstance("Havoc")], draw_cards=[CardInstance("Strike")])
        _set_piles(second, hand_cards=[CardInstance("Havoc")], draw_cards=[CardInstance("Strike")])

        assert first.play_card(0)
        assert second.play_card(0)

        assert [monster.hp for monster in first.state.monsters] == [monster.hp for monster in second.state.monsters]

    def test_dual_wield_copies_first_real_attack_or_power(self):
        combat = _make_combat()
        target = CardInstance("Inflame", upgraded=True)
        _set_piles(combat, hand_cards=[CardInstance("DualWield"), target], draw_cards=[])

        assert combat.play_card(0)

        hand_cards = combat.state.card_manager.hand.cards
        assert [card.card_id for card in hand_cards] == ["Inflame", "Inflame"]
        assert all(card.upgraded for card in hand_cards)
        assert hand_cards[0].uuid != hand_cards[1].uuid

    def test_dual_wield_plus_creates_two_copies(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("DualWield", upgraded=True), CardInstance("Inflame")], draw_cards=[])

        assert combat.play_card(0)

        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Inflame", "Inflame", "Inflame"]

    def test_dual_wield_no_valid_target_is_stable_no_op(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("DualWield"), CardInstance("Defend")], draw_cards=[])

        assert combat.play_card(0)

        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Defend"]

    def test_dual_wield_respects_hand_limit_rules(self):
        combat = _make_combat()
        hand_cards = [CardInstance("DualWield", upgraded=True)] + [CardInstance("Strike") for _ in range(9)]
        _set_piles(combat, hand_cards=hand_cards, draw_cards=[], discard_cards=[])

        assert combat.play_card(0)

        assert len(combat.state.card_manager.hand.cards) == 10
        assert sorted(card.card_id for card in combat.state.card_manager.discard_pile.cards) == ["DualWield", "Strike"]
