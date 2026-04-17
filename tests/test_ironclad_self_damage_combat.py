from __future__ import annotations

from sts_py.engine.combat.card_effects import BrutalityEffect, ReaperEffect, get_card_effects
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


class TestIroncladSelfDamageEffects:
    def test_brutality_effect_and_upgrade_metadata(self):
        effects = get_card_effects(CardInstance("Brutality"))
        base = CardInstance("Brutality")
        upgraded = CardInstance("Brutality", upgraded=True)

        assert len(effects) == 1
        assert isinstance(effects[0], BrutalityEffect)
        assert base.cost == 0
        assert base.is_innate is True
        assert upgraded.is_innate is True

    def test_reaper_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("Reaper"))

        assert len(effects) == 1
        assert isinstance(effects[0], ReaperEffect)


class TestIroncladSelfDamageIntegration:
    def test_brutality_applies_power(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Brutality")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Brutality") == 1

    def test_brutality_power_draws_after_start_turn_and_loses_hp(self):
        combat = _make_combat(attack_damage=0)
        combat.state.player.add_power(create_power("Brutality", 1, "player"))
        _set_piles(
            combat,
            hand_cards=[],
            draw_cards=[
                CardInstance("Strike"),
                CardInstance("Defend"),
                CardInstance("Bash"),
                CardInstance("ShrugItOff"),
                CardInstance("PommelStrike"),
                CardInstance("TrueGrit"),
            ],
            discard_cards=[],
        )

        combat.end_player_turn()

        assert combat.state.player.hp == 79
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == [
            "TrueGrit",
            "PommelStrike",
            "ShrugItOff",
            "Bash",
            "Defend",
            "Strike",
        ]

    def test_rupture_triggers_from_hemokinesis_self_damage(self):
        combat = _make_combat(monster_hp=80, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Hemokinesis")], draw_cards=[])
        combat.state.player.add_power(create_power("Rupture", 1, "player"))

        assert combat.play_card(0, 0)

        assert combat.state.player.hp == 78
        assert combat.state.player.strength == 1
        assert combat.state.player.get_power_amount("Strength") == 1
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == []

    def test_rupture_triggers_from_brutality_hp_loss(self):
        combat = _make_combat(attack_damage=0)
        combat.state.player.add_power(create_power("Rupture", 1, "player"))
        combat.state.player.add_power(create_power("Brutality", 1, "player"))
        _set_piles(
            combat,
            hand_cards=[],
            draw_cards=[
                CardInstance("Strike"),
                CardInstance("Defend"),
                CardInstance("Bash"),
                CardInstance("ShrugItOff"),
                CardInstance("PommelStrike"),
                CardInstance("TrueGrit"),
            ],
            discard_cards=[],
        )

        combat.end_player_turn()

        assert combat.state.player.hp == 79
        assert combat.state.player.strength == 1
        assert combat.state.player.get_power_amount("Strength") == 1

    def test_rupture_ignores_zero_hp_loss(self):
        combat = _make_combat(attack_damage=0)
        combat.state.player.add_power(create_power("Rupture", 1, "player"))

        lost = combat.state.player.lose_hp(0, source_owner=combat.state.player)

        assert lost == 0
        assert combat.state.player.strength == 0
        assert combat.state.player.get_power_amount("Strength") == 0

    def test_reaper_heals_only_for_actual_hp_damage(self):
        combat = _make_multi_monster_combat(monster_hps=[30, 30])
        combat.state.player.hp = 60
        _set_piles(combat, hand_cards=[CardInstance("Reaper", upgraded=True)], draw_cards=[])
        combat.state.monsters[0].block = 3
        combat.state.monsters[1].block = 10

        assert combat.play_card(0)

        assert combat.state.player.hp == 62
        assert combat.state.monsters[0].hp == 28
        assert combat.state.monsters[1].hp == 30
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Reaper"]
