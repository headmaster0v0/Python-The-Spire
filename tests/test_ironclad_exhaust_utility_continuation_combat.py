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
            "Defend",
            "TrueGrit",
            "SeverSoul",
            "Sentinel",
            "BloodforBlood",
            "Bash",
            "Anger",
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


class TestIroncladExhaustUtilityContinuationIntegration:
    def test_true_grit_gains_block_and_exhausts_first_other_hand_card(self):
        combat = _make_combat(monster_hps=[40])
        _set_piles(
            combat,
            hand_cards=[CardInstance("TrueGrit"), CardInstance("Defend"), CardInstance("Strike")],
            draw_cards=[],
        )

        assert combat.play_card(0)

        assert combat.state.player.block == 7
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Defend"]
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Strike"]

    def test_true_grit_exhaust_triggers_feel_no_pain_and_dark_embrace(self):
        combat = _make_combat(monster_hps=[40])
        combat.state.player.add_power(create_power("FeelNoPain", 3, "player"))
        combat.state.player.add_power(create_power("DarkEmbrace", 1, "player"))
        _set_piles(
            combat,
            hand_cards=[CardInstance("TrueGrit"), CardInstance("Defend"), CardInstance("Strike")],
            draw_cards=[CardInstance("Bash")],
        )

        assert combat.play_card(0)

        assert combat.state.player.block == 10
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Defend"]
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Strike", "Bash"]

    def test_sever_soul_exhausts_other_non_attacks_and_triggers_exhaust_powers(self):
        combat = _make_combat(monster_hps=[50], energy=3)
        combat.state.player.add_power(create_power("FeelNoPain", 3, "player"))
        combat.state.player.add_power(create_power("DarkEmbrace", 1, "player"))
        _set_piles(
            combat,
            hand_cards=[CardInstance("SeverSoul"), CardInstance("Defend"), CardInstance("Sentinel"), CardInstance("Strike")],
            draw_cards=[CardInstance("Anger"), CardInstance("Bash")],
        )

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 34
        assert combat.state.player.block == 6
        assert combat.state.player.energy == 3
        assert combat.state.card_manager.energy == 3
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Strike", "Bash", "Anger"]
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Defend", "Sentinel"]
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["SeverSoul"]

    def test_sentinel_play_grants_block_and_energy_on_exhaust(self):
        combat = _make_combat(monster_hps=[40], energy=3)
        _set_piles(combat, hand_cards=[CardInstance("Sentinel")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.block == 5
        assert combat.state.player.energy == 2
        assert combat.state.card_manager.energy == 2
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == []
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Sentinel"]

    def test_sentinel_exhausted_by_true_grit_grants_energy(self):
        combat = _make_combat(monster_hps=[40], energy=3)
        _set_piles(
            combat,
            hand_cards=[CardInstance("TrueGrit"), CardInstance("Sentinel")],
            draw_cards=[],
        )

        assert combat.play_card(0)

        assert combat.state.player.energy == 4
        assert combat.state.card_manager.energy == 4
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Sentinel"]

    def test_blood_for_blood_initial_cost_and_damage_are_correct(self):
        combat = _make_combat(monster_hps=[40], energy=4)
        blood_for_blood = CardInstance("BloodforBlood")
        _set_piles(combat, hand_cards=[blood_for_blood], draw_cards=[])

        assert blood_for_blood.cost == 4
        assert blood_for_blood.cost_for_turn == 4
        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 22

    def test_blood_for_blood_cost_reduces_after_actual_hp_loss(self):
        combat = _make_combat(monster_hps=[40], energy=4)
        blood_for_blood = CardInstance("BloodforBlood")
        _set_piles(combat, hand_cards=[blood_for_blood], draw_cards=[])

        combat.state.player.lose_hp(2, source_owner=combat.state.player)

        assert blood_for_blood.cost_for_turn == 2
        assert blood_for_blood.is_cost_modified_for_turn is True

    def test_blood_for_blood_cost_reduction_persists_across_piles(self):
        combat = _make_combat(monster_hps=[40], energy=4)
        blood_for_blood = CardInstance("BloodforBlood")
        _set_piles(combat, hand_cards=[], draw_cards=[], discard_cards=[blood_for_blood])

        combat.state.player.lose_hp(2, source_owner=combat.state.player)
        assert blood_for_blood.cost_for_turn == 2

        _set_piles(combat, hand_cards=[], draw_cards=[blood_for_blood], discard_cards=[])
        drawn = combat.state.card_manager.draw_card(combat.state.card_manager.rng)

        assert drawn is blood_for_blood
        assert drawn.cost_for_turn == 2

    def test_blood_for_blood_cost_never_goes_below_zero(self):
        combat = _make_combat(monster_hps=[40], energy=4)
        blood_for_blood = CardInstance("BloodforBlood")
        _set_piles(combat, hand_cards=[blood_for_blood], draw_cards=[])

        combat.state.player.lose_hp(99, source_owner=combat.state.player)

        assert blood_for_blood.cost_for_turn == 0
        assert blood_for_blood.combat_cost_reduction == 4
