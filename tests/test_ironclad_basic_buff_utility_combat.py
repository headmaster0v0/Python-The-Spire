from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
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
        deck=["Strike", "Defend", "Armaments", "Flex", "Anger", "Cleave", "ShrugItOff"],
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


class TestIroncladBasicBuffUtilityIntegration:
    def test_armaments_grants_block_then_upgrades_first_other_hand_card(self):
        combat = _make_combat()
        _set_piles(
            combat,
            hand_cards=[CardInstance("Armaments"), CardInstance("Strike"), CardInstance("Defend")],
            draw_cards=[],
        )

        assert combat.play_card(0)

        assert combat.state.player.block == 5
        hand_cards = combat.state.card_manager.hand.cards
        assert [card.card_id for card in hand_cards] == ["Strike", "Defend"]
        assert hand_cards[0].upgraded is True
        assert hand_cards[1].upgraded is False

    def test_armaments_plus_upgrades_all_other_hand_cards(self):
        combat = _make_combat()
        _set_piles(
            combat,
            hand_cards=[CardInstance("Armaments", upgraded=True), CardInstance("Strike"), CardInstance("Defend")],
            draw_cards=[],
        )

        assert combat.play_card(0)

        assert combat.state.player.block == 8
        assert all(card.upgraded for card in combat.state.card_manager.hand.cards)

    def test_flex_grants_strength_for_turn_and_boosts_attack_damage(self):
        combat = _make_combat(monster_hps=[30])
        _set_piles(
            combat,
            hand_cards=[CardInstance("Flex"), CardInstance("Strike")],
            draw_cards=[],
        )

        assert combat.play_card(0)

        assert combat.state.player.strength == 2

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp < 24

    def test_flex_plus_grants_four_strength_and_removes_it_at_end_of_turn(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Flex", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.strength == 4

        combat.end_player_turn()

        assert combat.state.player.strength == 0
        assert combat.state.player.get_power_amount("Strength") == 0

    def test_anger_deals_damage_and_adds_stat_equivalent_copy_to_discard(self):
        combat = _make_combat(monster_hps=[30])
        _set_piles(combat, hand_cards=[CardInstance("Anger", upgraded=True)], draw_cards=[])

        assert combat.play_card(0, 0)

        discard_cards = combat.state.card_manager.discard_pile.cards
        assert combat.state.monsters[0].hp == 22
        assert len(discard_cards) == 2
        assert all(card.card_id == "Anger" for card in discard_cards)
        assert all(card.upgraded for card in discard_cards)
        assert discard_cards[0].uuid != discard_cards[1].uuid
        assert all(getattr(card, "_combat_state", None) is combat.state for card in discard_cards)

    def test_cleave_hits_all_living_monsters(self):
        combat = _make_combat(monster_hps=[30, 30])
        _set_piles(combat, hand_cards=[CardInstance("Cleave")], draw_cards=[])

        assert combat.play_card(0)

        assert [monster.hp for monster in combat.state.monsters] == [22, 22]

    def test_shrug_it_off_gains_block_then_draws(self):
        combat = _make_combat()
        _set_piles(
            combat,
            hand_cards=[CardInstance("ShrugItOff")],
            draw_cards=[CardInstance("Strike")],
        )

        assert combat.play_card(0)

        assert combat.state.player.block == 8
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Strike"]

    def test_shrug_it_off_draw_respects_no_draw(self):
        combat = _make_combat()
        combat.state.player.add_power(create_power("No Draw", 1, "player"))
        _set_piles(
            combat,
            hand_cards=[CardInstance("ShrugItOff")],
            draw_cards=[CardInstance("Strike")],
        )

        assert combat.play_card(0)

        assert combat.state.player.block == 8
        assert combat.state.card_manager.hand.cards == []
