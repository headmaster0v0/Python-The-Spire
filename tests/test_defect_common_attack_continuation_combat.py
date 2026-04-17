from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 40, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hps: list[int] | None = None, energy: int = 3) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyMonster(f"Dummy{index}", hp=hp)
        for index, hp in enumerate(monster_hps or [40])
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=75,
        player_max_hp=75,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Claw", "FTL", "Melter", "RipAndTear", "Sunder", "Scrape", "Turbo", "Tempest"],
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


class TestDefectCommonAttackContinuationCombat:
    def test_claw_grows_across_hand_draw_discard_and_current_instance(self):
        combat = _make_combat(energy=1)
        current = CardInstance("Claw")
        hand_claw = CardInstance("Claw")
        draw_claw = CardInstance("Claw")
        discard_claw = CardInstance("Claw")
        _set_piles(combat, hand_cards=[current, hand_claw], draw_cards=[draw_claw], discard_cards=[discard_claw])

        assert combat.play_card(0, 0)

        assert hand_claw.combat_damage_bonus == 2
        assert draw_claw.combat_damage_bonus == 2
        assert discard_claw.combat_damage_bonus == 2
        played_copy = next(card for card in combat.state.card_manager.discard_pile.cards if card.card_id == "Claw")
        assert played_copy.combat_damage_bonus == 2

    def test_ftl_draws_below_threshold_and_stops_at_threshold(self):
        draw_case = _make_combat(energy=2)
        _set_piles(
            draw_case,
            hand_cards=[CardInstance("FTL"), CardInstance("Claw")],
            draw_cards=[CardInstance("Strike_B")],
        )
        assert draw_case.play_card(0, 0)
        assert [card.card_id for card in draw_case.state.card_manager.hand.cards] == ["Claw", "Strike_B"]

        stop_case = _make_combat(energy=4)
        _set_piles(
            stop_case,
            hand_cards=[CardInstance("Claw"), CardInstance("Claw"), CardInstance("Claw"), CardInstance("FTL")],
            draw_cards=[CardInstance("Strike_B")],
        )
        assert stop_case.play_card(0, 0)
        assert stop_case.play_card(0, 0)
        assert stop_case.play_card(0, 0)
        assert stop_case.play_card(0, 0)
        assert [card.card_id for card in stop_case.state.card_manager.hand.cards] == []

        upgraded = _make_combat(energy=4)
        _set_piles(
            upgraded,
            hand_cards=[CardInstance("Claw"), CardInstance("Claw"), CardInstance("Claw"), CardInstance("FTL", upgraded=True)],
            draw_cards=[CardInstance("Strike_B")],
        )
        assert upgraded.play_card(0, 0)
        assert upgraded.play_card(0, 0)
        assert upgraded.play_card(0, 0)
        assert upgraded.play_card(0, 0)
        assert [card.card_id for card in upgraded.state.card_manager.hand.cards] == ["Strike_B"]

    def test_melter_clears_block_before_damage(self):
        combat = _make_combat(energy=1)
        combat.state.monsters[0].block = 12
        _set_piles(combat, hand_cards=[CardInstance("Melter")], draw_cards=[])

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].block == 0
        assert combat.state.monsters[0].hp == 30

    def test_rip_and_tear_is_deterministic_and_hits_single_survivor_twice(self):
        first = _make_combat(monster_hps=[20, 20], energy=1)
        _set_piles(first, hand_cards=[CardInstance("RipAndTear")], draw_cards=[])
        assert first.play_card(0)
        hp_first = [m.hp for m in first.state.monsters]

        second = _make_combat(monster_hps=[20, 20], energy=1)
        _set_piles(second, hand_cards=[CardInstance("RipAndTear")], draw_cards=[])
        assert second.play_card(0)
        hp_second = [m.hp for m in second.state.monsters]
        assert hp_first == hp_second

        single = _make_combat(monster_hps=[20], energy=1)
        _set_piles(single, hand_cards=[CardInstance("RipAndTear")], draw_cards=[])
        assert single.play_card(0)
        assert single.state.monsters[0].hp == 6

    def test_sunder_refunds_energy_on_kill_only(self):
        kill = _make_combat(monster_hps=[24], energy=3)
        _set_piles(kill, hand_cards=[CardInstance("Sunder")], draw_cards=[])
        assert kill.play_card(0, 0)
        assert kill.state.player.energy == 3
        assert kill.state.card_manager.energy == 3

        no_kill = _make_combat(monster_hps=[40], energy=3)
        _set_piles(no_kill, hand_cards=[CardInstance("Sunder")], draw_cards=[])
        assert no_kill.play_card(0, 0)
        assert no_kill.state.player.energy == 0
        assert no_kill.state.card_manager.energy == 0

    def test_scrape_discards_newly_drawn_nonzero_cards_but_keeps_zero_and_x_cost(self):
        combat = _make_combat(energy=1)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Scrape")],
            draw_cards=[CardInstance("Strike_B"), CardInstance("Turbo"), CardInstance("Tempest"), CardInstance("DoubleEnergy")],
        )
        assert combat.play_card(0, 0)
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Tempest", "Turbo"]
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["DoubleEnergy", "Strike_B", "Scrape"]

        upgraded = _make_combat(energy=1)
        _set_piles(
            upgraded,
            hand_cards=[CardInstance("Scrape", upgraded=True)],
            draw_cards=[CardInstance("Strike_B"), CardInstance("Turbo"), CardInstance("Tempest"), CardInstance("DoubleEnergy"), CardInstance("Zap")],
        )
        assert upgraded.play_card(0, 0)
        assert [card.card_id for card in upgraded.state.card_manager.hand.cards] == ["Tempest", "Turbo"]
        assert "Zap" in [card.card_id for card in upgraded.state.card_manager.discard_pile.cards]

    def test_scrape_under_no_draw_only_deals_damage(self):
        combat = _make_combat(energy=1)
        combat.state.player.add_power(__import__("sts_py.engine.combat.powers", fromlist=["create_power"]).create_power("No Draw", 1, "player"))
        _set_piles(combat, hand_cards=[CardInstance("Scrape")], draw_cards=[CardInstance("Strike_B"), CardInstance("Turbo")])
        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 33
        assert combat.state.card_manager.hand.cards == []
