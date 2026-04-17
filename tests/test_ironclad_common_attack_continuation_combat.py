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
        deck=[
            "Strike",
            "Strike",
            "Strike_P",
            "Clash",
            "TwinStrike",
            "Headbutt",
            "IronWave",
            "PerfectedStrike",
            "WildStrike",
            "RecklessCharge",
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
    exhaust_cards: list[CardInstance] | None = None,
) -> None:
    cm = combat.state.card_manager
    cm.hand.cards = _bind_cards(combat, hand_cards or [])
    cm.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    cm.discard_pile.cards = _bind_cards(combat, discard_cards or [])
    cm.exhaust_pile.cards = _bind_cards(combat, exhaust_cards or [])


class TestIroncladCommonAttackContinuationIntegration:
    def test_clash_is_playable_when_hand_contains_only_attacks(self):
        combat = _make_combat(monster_hps=[40])
        _set_piles(
            combat,
            hand_cards=[CardInstance("Clash"), CardInstance("Strike")],
            draw_cards=[],
        )

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 26

    def test_clash_is_not_playable_when_hand_contains_non_attack(self):
        combat = _make_combat(monster_hps=[40])
        _set_piles(
            combat,
            hand_cards=[CardInstance("Clash"), CardInstance("Defend")],
            draw_cards=[],
        )

        assert combat.play_card(0, 0) is False
        assert combat.state.monsters[0].hp == 40

    def test_twin_strike_hits_same_target_twice(self):
        combat = _make_combat(monster_hps=[30])
        _set_piles(combat, hand_cards=[CardInstance("TwinStrike")], draw_cards=[])

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 20

    def test_headbutt_moves_first_discard_card_to_draw_pile_top(self):
        combat = _make_combat(monster_hps=[40])
        strike = CardInstance("Strike")
        defend = CardInstance("Defend")
        _set_piles(
            combat,
            hand_cards=[CardInstance("Headbutt")],
            draw_cards=[CardInstance("Bash")],
            discard_cards=[strike, defend],
        )

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 31
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Defend", "Headbutt"]
        assert combat.state.card_manager.draw_pile.cards[-1] is strike

    def test_iron_wave_gains_block_then_deals_damage(self):
        combat = _make_combat(monster_hps=[30])
        _set_piles(combat, hand_cards=[CardInstance("IronWave")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.player.block == 5
        assert combat.state.monsters[0].hp == 25

    def test_perfected_strike_counts_strikes_across_combat_piles_and_self(self):
        combat = _make_combat(monster_hps=[50])
        perfected = CardInstance("PerfectedStrike")
        _set_piles(
            combat,
            hand_cards=[perfected, CardInstance("Strike")],
            draw_cards=[CardInstance("Strike_P")],
            discard_cards=[CardInstance("Strike")],
            exhaust_cards=[CardInstance("Strike_P")],
        )

        assert combat.play_card(0, 0)

        # Base 6 + 4 strike cards * 2 bonus = 14 damage.
        assert combat.state.monsters[0].hp == 36

    def test_wild_strike_adds_real_wound_to_draw_pile(self):
        combat = _make_combat(monster_hps=[30])
        _set_piles(combat, hand_cards=[CardInstance("WildStrike")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 18
        assert any(card.card_id == "Wound" for card in combat.state.card_manager.draw_pile.cards)

    def test_reckless_charge_adds_real_dazed_to_draw_pile(self):
        combat = _make_combat(monster_hps=[30])
        _set_piles(combat, hand_cards=[CardInstance("RecklessCharge")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 23
        assert any(card.card_id == "Dazed" for card in combat.state.card_manager.draw_pile.cards)

    def test_wild_strike_generated_wound_triggers_fire_breathing(self):
        combat = _make_combat(monster_hps=[40, 40])
        combat.state.player.add_power(create_power("FireBreathing", 6, "player"))
        wound = CardInstance("Wound")
        _set_piles(
            combat,
            hand_cards=[CardInstance("WildStrike")],
            draw_cards=[wound],
        )

        assert combat.play_card(0, 0)
        drawn = combat.state.card_manager.draw_card(combat.state.card_manager.rng)

        assert drawn is not None
        assert drawn.card_id == "Wound"
        assert [monster.hp for monster in combat.state.monsters] == [22, 34]

    def test_reckless_charge_generated_dazed_triggers_evolve(self):
        combat = _make_combat(monster_hps=[40])
        combat.state.player.add_power(create_power("Evolve", 1, "player"))
        dazed = CardInstance("Dazed")
        _set_piles(
            combat,
            hand_cards=[CardInstance("RecklessCharge")],
            draw_cards=[dazed, CardInstance("Strike")],
        )

        assert combat.play_card(0, 0)
        drawn = combat.state.card_manager.draw_card(combat.state.card_manager.rng)

        assert drawn is not None
        assert drawn.card_id == "Dazed"
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Dazed", "Strike"]
