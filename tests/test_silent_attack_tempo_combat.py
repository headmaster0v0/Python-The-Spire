from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 40, attack_damage: int = 8):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(
    *,
    monster_hps: list[int] | None = None,
    energy: int = 3,
    attack_damage: int = 8,
    deck: list[str] | None = None,
) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyAttackMonster(f"Dummy{index}", hp=hp, attack_damage=attack_damage)
        for index, hp in enumerate(monster_hps or [40])
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=70,
        player_max_hp=70,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=deck or ["Backstab", "Bane", "Caltrops", "DaggerSpray", "Deflect", "DodgeAndRoll", "FlyingKnee", "AllOutAttack", "Predator"],
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


class TestSilentAttackTempoCombat:
    def test_backstab_enters_opening_hand_and_exhausts_after_play(self):
        combat = _make_combat(deck=["Backstab", "Strike", "Strike", "Defend", "Defend"], energy=1, attack_damage=0)

        hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
        assert "Backstab" in hand_ids

        backstab_index = hand_ids.index("Backstab")
        assert combat.play_card(backstab_index, 0)

        assert combat.state.monsters[0].hp == 29
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Backstab"]

    def test_bane_hits_once_without_poison_and_twice_with_poison(self):
        plain = _make_combat(energy=1, attack_damage=0)
        _set_piles(plain, hand_cards=[CardInstance("Bane")], draw_cards=[])

        assert plain.play_card(0, 0)
        assert plain.state.monsters[0].hp == 33

        poisoned = _make_combat(energy=1, attack_damage=0)
        poisoned.state.monsters[0].add_power(create_power("Poison", 2, poisoned.state.monsters[0].id))
        _set_piles(poisoned, hand_cards=[CardInstance("Bane")], draw_cards=[])

        assert poisoned.play_card(0, 0)
        assert poisoned.state.monsters[0].hp == 26

        upgraded = _make_combat(energy=1, attack_damage=0)
        upgraded.state.monsters[0].add_power(create_power("Poison", 2, upgraded.state.monsters[0].id))
        _set_piles(upgraded, hand_cards=[CardInstance("Bane", upgraded=True)], draw_cards=[])

        assert upgraded.play_card(0, 0)
        assert upgraded.state.monsters[0].hp == 20

    def test_caltrops_retaliates_on_normal_attacks_only(self):
        combat = _make_combat(energy=1)
        _set_piles(combat, hand_cards=[CardInstance("Caltrops", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Thorns") == 5

        monster = combat.state.monsters[0]
        assert combat.state.player.take_damage(3, source_owner=monster) == 3
        assert monster.hp == 35

        assert combat.state.player.take_damage(3, damage_type="THORNS", source_owner=monster) == 3
        assert monster.hp == 35

        assert combat.state.player.lose_hp(2, source_owner=monster) == 2
        assert monster.hp == 35

    def test_dagger_spray_hits_all_enemies_twice(self):
        combat = _make_combat(energy=1, monster_hps=[30, 30], attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("DaggerSpray")], draw_cards=[])

        assert combat.play_card(0)
        assert [monster.hp for monster in combat.state.monsters] == [22, 22]

        upgraded = _make_combat(energy=1, monster_hps=[30, 30], attack_damage=0)
        _set_piles(upgraded, hand_cards=[CardInstance("DaggerSpray", upgraded=True)], draw_cards=[])

        assert upgraded.play_card(0)
        assert [monster.hp for monster in upgraded.state.monsters] == [18, 18]

    def test_deflect_gains_zero_cost_block(self):
        combat = _make_combat(energy=0, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Deflect", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.block == 7

    def test_dodge_and_roll_gains_block_now_and_next_turn(self):
        combat = _make_combat(energy=1, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("DodgeAndRoll", upgraded=True)], draw_cards=[CardInstance("Strike") for _ in range(5)])

        assert combat.play_card(0)
        assert combat.state.player.block == 6
        assert combat.state.player.get_power_amount("Next Turn Block") == 6

        combat.end_player_turn()

        assert combat.state.player.block == 6
        assert combat.state.player.get_power_amount("Next Turn Block") == 0

    def test_flying_knee_grants_next_turn_energy(self):
        combat = _make_combat(energy=3, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("FlyingKnee", upgraded=True)], draw_cards=[CardInstance("Strike") for _ in range(5)])

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 29
        assert combat.state.player.get_power_amount("Energized") == 1

        combat.end_player_turn()

        assert combat.state.player.energy == 4
        assert combat.state.player.get_power_amount("Energized") == 0

    def test_all_out_attack_deals_aoe_then_discards_first_other_card(self):
        combat = _make_combat(energy=1, monster_hps=[30, 30], attack_damage=0)
        _set_piles(
            combat,
            hand_cards=[CardInstance("AllOutAttack"), CardInstance("Strike"), CardInstance("Defend")],
            draw_cards=[],
        )

        assert combat.play_card(0)
        assert [monster.hp for monster in combat.state.monsters] == [20, 20]
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Defend"]
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Strike", "AllOutAttack"]

        empty_other = _make_combat(energy=1, monster_hps=[30, 30], attack_damage=0)
        _set_piles(empty_other, hand_cards=[CardInstance("AllOutAttack")], draw_cards=[])
        assert empty_other.play_card(0)
        assert [monster.hp for monster in empty_other.state.monsters] == [20, 20]

    def test_predator_draws_two_next_turn_and_upgrade_only_changes_damage(self):
        combat = _make_combat(energy=2, attack_damage=0)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Predator")],
            draw_cards=[CardInstance("Strike") for _ in range(7)],
        )

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 25
        assert combat.state.player.get_power_amount("Draw Card") == 2

        combat.end_player_turn()

        assert combat.state.card_manager.get_hand_size() == 7
        assert combat.state.player.get_power_amount("Draw Card") == 0

        upgraded = _make_combat(energy=2, attack_damage=0)
        _set_piles(upgraded, hand_cards=[CardInstance("Predator", upgraded=True)], draw_cards=[CardInstance("Strike") for _ in range(7)])
        assert upgraded.play_card(0, 0)
        assert upgraded.state.monsters[0].hp == 20
