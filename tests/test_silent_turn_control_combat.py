from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.combat.powers import create_power


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 50, attack_damage: int = 10):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hps: list[int] | None = None, energy: int = 3, attack_damage: int = 10) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyAttackMonster(f"Dummy{index}", hp=hp, attack_damage=attack_damage)
        for index, hp in enumerate(monster_hps or [50])
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=70,
        player_max_hp=70,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=[
            "Burst",
            "Expertise",
            "Outmaneuver",
            "ToolsOfTheTrade",
            "WellLaidPlans",
            "WraithForm",
            "Backflip",
            "LegSweep",
        ],
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


class TestSilentTurnControlCombat:
    def test_burst_duplicates_next_skill_with_same_target_and_no_recursion(self):
        combat = _make_combat(energy=3)
        _set_piles(combat, hand_cards=[CardInstance("Burst"), CardInstance("LegSweep")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Burst") == 1

        assert combat.play_card(0, 0)

        assert combat.state.player.block == 22
        assert combat.state.monsters[0].get_power_amount("Weak") == 4
        assert combat.state.player.get_power_amount("Burst") == 0

    def test_burst_plus_duplicates_two_skills_then_expires(self):
        combat = _make_combat(energy=3, attack_damage=0)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Burst", upgraded=True), CardInstance("Backflip"), CardInstance("Outmaneuver")],
            draw_cards=[CardInstance("Strike"), CardInstance("Defend"), CardInstance("Neutralize"), CardInstance("Slice")],
        )

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Burst") == 2

        assert combat.play_card(0)
        assert combat.state.player.block == 10
        assert combat.state.player.get_power_amount("Burst") == 1

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Energized") == 4
        assert combat.state.player.get_power_amount("Burst") == 0

    def test_expertise_draws_up_to_target_hand_size(self):
        combat = _make_combat(energy=1, attack_damage=0)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Expertise"), CardInstance("Strike"), CardInstance("Defend")],
            draw_cards=[
                CardInstance("Neutralize"),
                CardInstance("Survivor"),
                CardInstance("Slice"),
                CardInstance("Prepared"),
                CardInstance("Backflip"),
            ],
        )

        assert combat.play_card(0)

        assert combat.state.card_manager.get_hand_size() == 6

    def test_expertise_respects_existing_hand_count_no_draw_and_limit(self):
        capped = _make_combat(energy=1, attack_damage=0)
        _set_piles(
            capped,
            hand_cards=[CardInstance("Expertise", upgraded=True)] + [CardInstance("Strike") for _ in range(6)],
            draw_cards=[CardInstance("Defend"), CardInstance("Neutralize")],
        )

        assert capped.play_card(0)
        assert capped.state.card_manager.get_hand_size() == 7
        assert len(capped.state.card_manager.draw_pile.cards) == 1

        no_draw = _make_combat(energy=1, attack_damage=0)
        no_draw.state.player.add_power(create_power("No Draw", 1, "player"))
        _set_piles(no_draw, hand_cards=[CardInstance("Expertise")], draw_cards=[CardInstance("Strike") for _ in range(5)])

        assert no_draw.play_card(0)
        assert no_draw.state.card_manager.get_hand_size() == 0

    def test_outmaneuver_grants_next_turn_energy_and_then_clears(self):
        combat = _make_combat(energy=3, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Outmaneuver")], draw_cards=[CardInstance("Strike") for _ in range(5)])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Energized") == 2

        combat.end_player_turn()

        assert combat.state.player.energy == 5
        assert combat.state.card_manager.energy == 5
        assert combat.state.player.get_power_amount("Energized") == 0

    def test_tools_of_the_trade_draws_then_discards_deterministically(self):
        combat = _make_combat(energy=1, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("ToolsOfTheTrade")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Tools Of The Trade") == 1

        _set_piles(
            combat,
            hand_cards=[CardInstance("Strike"), CardInstance("Defend")],
            draw_cards=[CardInstance("Neutralize")],
            discard_cards=combat.state.card_manager.discard_pile.cards,
        )

        combat.state.player.powers.at_start_of_turn_post_draw(combat.state.player)

        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Defend", "Neutralize"]
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards][-2:] == ["ToolsOfTheTrade", "Strike"]

    def test_well_laid_plans_opens_retain_choice_and_only_keeps_selected_non_ethereal_cards(self):
        combat = _make_combat(energy=1, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("WellLaidPlans", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Retain Cards") == 2

        dazed = CardInstance("Dazed")
        dazed._combat_state = combat.state
        strike = CardInstance("Strike")
        defend = CardInstance("Defend")
        neutralize = CardInstance("Neutralize")
        _set_piles(
            combat,
            hand_cards=[dazed, strike, defend, neutralize],
            draw_cards=[CardInstance("Survivor"), CardInstance("Backflip"), CardInstance("Slice"), CardInstance("Prepared"), CardInstance("Deflect")],
            discard_cards=combat.state.card_manager.discard_pile.cards,
        )

        combat.end_player_turn()
        assert combat.state.pending_combat_choice is not None
        assert combat.choose_combat_option(0) is True
        assert combat.choose_combat_option(0) is True

        hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
        assert "Strike" in hand_ids
        assert "Defend" in hand_ids
        assert "Neutralize" not in hand_ids
        discard_ids = [card.card_id for card in combat.state.card_manager.discard_pile.cards]
        assert "Neutralize" in discard_ids
        assert "Dazed" not in discard_ids
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Dazed"]

    def test_wraith_form_grants_intangible_and_loses_dexterity_each_turn(self):
        combat = _make_combat(energy=3, attack_damage=10)
        _set_piles(combat, hand_cards=[CardInstance("WraithForm")], draw_cards=[CardInstance("Strike") for _ in range(5)])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Intangible") == 2
        assert combat.state.player.get_power_amount("WraithForm") == -1

        combat.end_player_turn()

        assert combat.state.player.hp == 69
        assert combat.state.player.dexterity == -1
        assert combat.state.player.get_power_amount("Intangible") == 1

        combat.end_player_turn()

        assert combat.state.player.hp == 68
        assert combat.state.player.dexterity == -2
        assert combat.state.player.get_power_amount("Intangible") == 0

    def test_wraith_form_plus_grants_three_intangible(self):
        combat = _make_combat(energy=3, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("WraithForm", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.get_power_amount("Intangible") == 3
