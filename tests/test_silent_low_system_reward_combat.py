from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 50):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=6, name="Attack"))


def _make_combat(*, monster_hps: list[int] | None = None, energy: int = 3) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [DummyAttackMonster(f"Dummy{idx}", hp=hp) for idx, hp in enumerate(monster_hps or [50])]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=70,
        player_max_hp=70,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Slice", "QuickSlash", "SuckerPunch", "Backflip", "Dash", "Adrenaline", "DieDieDie"],
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


class TestSilentLowSystemRewardCombatIntegration:
    def test_slice_deals_single_target_damage(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Slice")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 44

    def test_quick_slash_deals_damage_and_draws(self):
        combat = _make_combat()
        _set_piles(
            combat,
            hand_cards=[CardInstance("QuickSlash")],
            draw_cards=[CardInstance("Strike")],
        )

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 42
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Strike"]

    def test_sucker_punch_deals_damage_and_applies_weak(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("SuckerPunch")], draw_cards=[])

        assert combat.play_card(0, 0)

        monster = combat.state.monsters[0]
        assert monster.hp == 43
        assert monster.get_power_amount("Weak") == 1

    def test_backflip_gains_block_and_draws(self):
        combat = _make_combat()
        _set_piles(
            combat,
            hand_cards=[CardInstance("Backflip")],
            draw_cards=[CardInstance("Strike"), CardInstance("Defend")],
        )

        assert combat.play_card(0)

        assert combat.state.player.block == 5
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Defend", "Strike"]

    def test_dash_gains_block_and_deals_damage(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Dash")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.player.block == 10
        assert combat.state.monsters[0].hp == 40

    def test_adrenaline_draws_gains_energy_and_exhausts(self):
        combat = _make_combat()
        _set_piles(
            combat,
            hand_cards=[CardInstance("Adrenaline")],
            draw_cards=[CardInstance("Strike"), CardInstance("Defend")],
        )

        assert combat.play_card(0)

        assert combat.state.player.energy == 4
        assert combat.state.card_manager.energy == 4
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Defend", "Strike"]
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Adrenaline"]

    def test_die_die_die_hits_all_living_monsters_and_exhausts(self):
        combat = _make_combat(monster_hps=[40, 40], energy=1)
        _set_piles(combat, hand_cards=[CardInstance("DieDieDie")], draw_cards=[])

        assert combat.play_card(0)

        assert [monster.hp for monster in combat.state.monsters] == [27, 27]
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["DieDieDie"]

    def test_quick_slash_draw_respects_no_draw(self):
        combat = _make_combat()
        combat.state.player.add_power(create_power("No Draw", 1, "player"))
        _set_piles(
            combat,
            hand_cards=[CardInstance("QuickSlash")],
            draw_cards=[CardInstance("Strike")],
        )

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 42
        assert combat.state.card_manager.hand.cards == []
