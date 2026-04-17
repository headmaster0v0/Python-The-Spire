from __future__ import annotations

from sts_py.engine.combat.card_effects import ApplyPowerEffect, BludgeonEffect, DealDamageEffect, get_card_effects
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


def _make_combat(*, monster_hps: list[int] | None = None, energy: int = 3, attack_damage: int = 0) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyAttackMonster(f"Dummy{index}", hp=hp, attack_damage=attack_damage)
        for index, hp in enumerate(monster_hps or [80])
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=80,
        player_max_hp=80,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Defend", "Bash", "Carnage", "Bludgeon"],
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


class TestIroncladDirectAttackFidelityEffects:
    def test_bash_effect_mapping_matches_damage_then_vulnerable(self):
        effects = get_card_effects(CardInstance("Bash"), target_idx=0)

        assert [type(effect) for effect in effects] == [DealDamageEffect, ApplyPowerEffect]
        assert effects[1].power_type == "Vulnerable"
        assert effects[1].amount == 2

    def test_bludgeon_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("Bludgeon"), target_idx=0)

        assert len(effects) == 1
        assert isinstance(effects[0], BludgeonEffect)


class TestIroncladDirectAttackFidelityIntegration:
    def test_bash_deals_damage_then_applies_two_vulnerable(self):
        combat = _make_combat(monster_hps=[50])
        _set_piles(combat, hand_cards=[CardInstance("Bash")], draw_cards=[])

        assert combat.play_card(0, 0)

        monster = combat.state.monsters[0]
        assert monster.hp == 42
        assert monster.get_power_amount("Vulnerable") == 2

    def test_bash_plus_applies_three_vulnerable(self):
        combat = _make_combat(monster_hps=[50])
        _set_piles(combat, hand_cards=[CardInstance("Bash", upgraded=True)], draw_cards=[])

        assert combat.play_card(0, 0)

        monster = combat.state.monsters[0]
        assert monster.hp == 40
        assert monster.get_power_amount("Vulnerable") == 3

    def test_carnage_deals_heavy_damage(self):
        combat = _make_combat(monster_hps=[50], energy=2)
        _set_piles(combat, hand_cards=[CardInstance("Carnage")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 30

    def test_carnage_plus_deals_more_damage(self):
        combat = _make_combat(monster_hps=[50], energy=2)
        _set_piles(combat, hand_cards=[CardInstance("Carnage", upgraded=True)], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 22

    def test_carnage_exhausts_if_unplayed_at_end_of_turn(self):
        combat = _make_combat(energy=2)
        carnage = CardInstance("Carnage")
        _set_piles(combat, hand_cards=[carnage], draw_cards=[])

        combat.end_player_turn()

        assert combat.state.card_manager.hand.cards == []
        assert combat.state.card_manager.exhaust_pile.cards == [carnage]

    def test_bludgeon_deals_correct_damage(self):
        combat = _make_combat(monster_hps=[50], energy=3)
        _set_piles(combat, hand_cards=[CardInstance("Bludgeon")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 18

    def test_bludgeon_plus_deals_higher_damage(self):
        combat = _make_combat(monster_hps=[50], energy=3)
        _set_piles(combat, hand_cards=[CardInstance("Bludgeon", upgraded=True)], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 8
