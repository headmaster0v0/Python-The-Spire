from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.run.run_engine import RunEngine


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 80, attack_damage: int = 6):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(
    *,
    monster_hps: list[int] | None = None,
    energy: int = 3,
    attack_damage: int = 6,
) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyAttackMonster(f"Dummy{index}", hp=hp, attack_damage=attack_damage)
        for index, hp in enumerate(monster_hps or [80])
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=70,
        player_max_hp=70,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["BulletTime", "Choke", "Envenom", "GrandFinale", "PhantasmalKiller", "Skewer", "StormOfSteel", "Alchemize", "Strike", "Deflect"],
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


class TestSilentFinalRareComboCombat:
    def test_bullet_time_zeroes_other_hand_costs_and_applies_no_draw(self):
        combat = _make_combat(energy=4, attack_damage=0)
        strike = CardInstance("Strike")
        deflect = CardInstance("Deflect")
        skewer = CardInstance("Skewer")
        _set_piles(combat, hand_cards=[CardInstance("BulletTime"), strike, deflect, skewer], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.get_power_amount("No Draw") == 1
        assert strike.cost_for_turn == 0
        assert deflect.cost_for_turn == 0
        assert skewer.cost_for_turn == -1

    def test_choke_applies_debuff_and_later_card_plays_cause_hp_loss(self):
        combat = _make_combat(energy=4, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Choke"), CardInstance("Deflect"), CardInstance("Strike")], draw_cards=[])

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 68
        assert combat.state.monsters[0].get_power_amount("Choked") == 3

        assert combat.play_card(0)
        assert combat.state.monsters[0].hp == 65

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 56

        combat.end_player_turn()
        assert combat.state.monsters[0].get_power_amount("Choked") == 0

    def test_envenom_applies_poison_only_on_actual_normal_attack_damage(self):
        combat = _make_combat(energy=3, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Envenom"), CardInstance("Strike")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].get_power_amount("Poison") == 1

        blocked = _make_combat(energy=3, attack_damage=0)
        blocked.state.monsters[0].block = 99
        _set_piles(blocked, hand_cards=[CardInstance("Envenom"), CardInstance("Strike")], draw_cards=[])
        assert blocked.play_card(0)
        assert blocked.play_card(0, 0)
        assert blocked.state.monsters[0].get_power_amount("Poison") == 0

    def test_grand_finale_requires_empty_draw_pile(self):
        blocked = _make_combat(energy=0, monster_hps=[70, 70], attack_damage=0)
        _set_piles(blocked, hand_cards=[CardInstance("GrandFinale")], draw_cards=[CardInstance("Strike")])
        assert blocked.play_card(0) is False

        ready = _make_combat(energy=0, monster_hps=[70, 70], attack_damage=0)
        _set_piles(ready, hand_cards=[CardInstance("GrandFinale", upgraded=True)], draw_cards=[])
        assert ready.play_card(0) is True
        assert [monster.hp for monster in ready.state.monsters] == [10, 10]

    def test_phantasmal_killer_doubles_all_attacks_next_turn_only(self):
        combat = _make_combat(energy=2, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("PhantasmalKiller"), CardInstance("Strike"), CardInstance("Strike")], draw_cards=[CardInstance("Strike") for _ in range(5)])

        assert combat.play_card(0)
        combat.end_player_turn()

        first_strike = next(i for i, c in enumerate(combat.state.card_manager.hand.cards) if c.card_id == "Strike")
        assert combat.play_card(first_strike, 0)
        second_strike = next(i for i, c in enumerate(combat.state.card_manager.hand.cards) if c.card_id == "Strike")
        assert combat.play_card(second_strike, 0)
        assert combat.state.monsters[0].hp == 56

        combat.end_player_turn()
        next_strike = next(i for i, c in enumerate(combat.state.card_manager.hand.cards) if c.card_id == "Strike")
        assert combat.play_card(next_strike, 0)
        assert combat.state.monsters[0].hp == 50

    def test_skewer_hits_target_x_times(self):
        combat = _make_combat(energy=3, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Skewer")], draw_cards=[])
        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 59

        upgraded = _make_combat(energy=2, attack_damage=0)
        _set_piles(upgraded, hand_cards=[CardInstance("Skewer", upgraded=True)], draw_cards=[])
        assert upgraded.play_card(0, 0)
        assert upgraded.state.monsters[0].hp == 60

    def test_storm_of_steel_discards_hand_and_generates_shivs(self):
        combat = _make_combat(energy=1, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("StormOfSteel"), CardInstance("Strike"), CardInstance("Deflect")], draw_cards=[])
        assert combat.play_card(0)
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Shiv", "Shiv"]
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Strike", "Deflect", "StormOfSteel"]

        upgraded = _make_combat(energy=1, attack_damage=0)
        _set_piles(upgraded, hand_cards=[CardInstance("StormOfSteel", upgraded=True), CardInstance("Strike")], draw_cards=[])
        assert upgraded.play_card(0)
        assert len(upgraded.state.card_manager.hand.cards) == 1
        assert upgraded.state.card_manager.hand.cards[0].upgraded is True

    def test_alchemize_fills_empty_potion_slot_and_noops_when_full(self):
        engine = RunEngine.create("ALCHEMIZETEST", ascension=0, character_class="SILENT")
        engine.start_combat_with_monsters(["JawWorm"])
        combat = engine.state.combat
        assert combat is not None
        _set_piles(combat, hand_cards=[CardInstance("Alchemize")], draw_cards=[])

        assert engine.combat_play_card(0)
        assert any(slot != "EmptyPotionSlot" for slot in engine.state.potions)

        full = RunEngine.create("ALCHEMIZEFULL", ascension=0, character_class="SILENT")
        full.state.potions = ["AttackPotion", "BlockPotion", "SkillPotion"]
        full.start_combat_with_monsters(["JawWorm"])
        full_combat = full.state.combat
        assert full_combat is not None
        _set_piles(full_combat, hand_cards=[CardInstance("Alchemize")], draw_cards=[])

        assert full.combat_play_card(0)
        assert full.state.potions == ["AttackPotion", "BlockPotion", "SkillPotion"]
