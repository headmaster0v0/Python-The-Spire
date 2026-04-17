from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, hp: int = 120, attack_damage: int = 0):
        super().__init__(id="DummyAttack", name="Dummy Attack", hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hp: int = 120, attack_damage: int = 0) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monster = DummyAttackMonster(hp=monster_hp, attack_damage=attack_damage)
    return CombatEngine.create_with_monsters(
        monsters=[monster],
        player_hp=80,
        player_max_hp=80,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Strike", "Strike", "Strike", "Defend", "Defend", "Bash", "ShrugItOff", "PommelStrike", "TrueGrit"],
        relics=[],
    )


def _make_multi_monster_combat(*, monster_hps: list[int]) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [DummyAttackMonster(hp=hp, attack_damage=0) for hp in monster_hps]
    return CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=80,
        player_max_hp=80,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Strike", "Strike", "Strike", "Defend", "Defend", "Bash", "ShrugItOff", "PommelStrike", "TrueGrit"],
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
    discard_cards: list[CardInstance] | None = None,
) -> None:
    cm = combat.state.card_manager
    cm.hand.cards = _bind_cards(combat, hand_cards or [])
    cm.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    cm.discard_pile.cards = _bind_cards(combat, discard_cards or [])
    cm.exhaust_pile.cards = []


class TestIroncladStatusReactionEffects:
    def test_fire_breathing_applies_power(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("FireBreathing")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("FireBreathing") == 6

    def test_evolve_applies_power(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Evolve")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Evolve") == 1


class TestIroncladStatusReactionIntegration:
    def test_fire_breathing_triggers_on_wound_draw(self):
        combat = _make_multi_monster_combat(monster_hps=[30, 30])
        combat.state.player.add_power(create_power("FireBreathing", 6, "player"))
        _set_piles(combat, hand_cards=[], draw_cards=[CardInstance("Wound")], discard_cards=[])

        drawn = combat.state.card_manager.draw_card(combat.ai_rng)

        assert drawn is not None
        assert [monster.hp for monster in combat.state.monsters] == [24, 24]

    def test_fire_breathing_triggers_on_dazed_draw(self):
        combat = _make_multi_monster_combat(monster_hps=[30, 30])
        combat.state.player.add_power(create_power("FireBreathing", 6, "player"))
        _set_piles(combat, hand_cards=[], draw_cards=[CardInstance("Dazed")], discard_cards=[])

        combat.state.card_manager.draw_card(combat.ai_rng)

        assert [monster.hp for monster in combat.state.monsters] == [24, 24]

    def test_fire_breathing_triggers_on_burn_draw(self):
        combat = _make_multi_monster_combat(monster_hps=[30, 30])
        combat.state.player.add_power(create_power("FireBreathing", 6, "player"))
        _set_piles(combat, hand_cards=[], draw_cards=[CardInstance("Burn")], discard_cards=[])

        combat.state.card_manager.draw_card(combat.ai_rng)

        assert [monster.hp for monster in combat.state.monsters] == [24, 24]

    def test_evolve_draws_on_status_draw(self):
        combat = _make_combat()
        combat.state.player.add_power(create_power("Evolve", 1, "player"))
        _set_piles(
            combat,
            hand_cards=[],
            draw_cards=[CardInstance("Strike"), CardInstance("Wound")],
            discard_cards=[],
        )

        combat.state.card_manager.draw_card(combat.ai_rng)

        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Wound", "Strike"]

    def test_evolve_does_not_trigger_on_curse_draw(self):
        combat = _make_combat()
        combat.state.player.add_power(create_power("Evolve", 1, "player"))
        _set_piles(
            combat,
            hand_cards=[],
            draw_cards=[CardInstance("Strike"), CardInstance("Doubt")],
            discard_cards=[],
        )

        combat.state.card_manager.draw_card(combat.ai_rng)

        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Doubt"]

    def test_wild_strike_generated_wound_triggers_reactions_when_drawn(self):
        combat = _make_combat(monster_hp=30)
        combat.state.player.add_power(create_power("FireBreathing", 6, "player"))
        combat.state.player.add_power(create_power("Evolve", 1, "player"))
        _set_piles(
            combat,
            hand_cards=[CardInstance("WildStrike")],
            draw_cards=[CardInstance("Strike")],
            discard_cards=[],
        )

        assert combat.play_card(0, 0)
        combat.state.card_manager.draw_card(combat.ai_rng)

        assert combat.state.monsters[0].hp == 12
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Wound", "Strike"]

    def test_reckless_charge_generated_dazed_triggers_reactions_when_drawn(self):
        combat = _make_combat(monster_hp=30)
        combat.state.player.add_power(create_power("FireBreathing", 6, "player"))
        combat.state.player.add_power(create_power("Evolve", 1, "player"))
        _set_piles(
            combat,
            hand_cards=[CardInstance("RecklessCharge")],
            draw_cards=[CardInstance("Strike")],
            discard_cards=[],
        )

        assert combat.play_card(0, 0)
        combat.state.card_manager.draw_card(combat.ai_rng)

        assert combat.state.monsters[0].hp == 17
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Dazed", "Strike"]

    def test_immolate_burn_from_discard_shuffle_triggers_reactions_when_drawn(self):
        combat = _make_combat(monster_hp=40)
        combat.state.player.add_power(create_power("FireBreathing", 6, "player"))
        combat.state.player.add_power(create_power("Evolve", 1, "player"))
        _set_piles(combat, hand_cards=[CardInstance("Immolate")], draw_cards=[], discard_cards=[])

        assert combat.play_card(0)
        combat.state.card_manager.draw_card(combat.ai_rng)

        assert combat.state.monsters[0].hp == 13
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Burn", "Immolate"]
