from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 40):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=6, name="Attack"))


def _make_combat(*, monster_hps: list[int] | None = None, energy: int = 3) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [DummyAttackMonster(f"Dummy{idx}", hp=hp) for idx, hp in enumerate(monster_hps or [40])]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=70,
        player_max_hp=70,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Defend", "Neutralize", "Survivor"],
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


class TestSilentStarterCombatIntegration:
    def test_neutralize_deals_damage_and_applies_weak(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Neutralize")], draw_cards=[])

        assert combat.play_card(0, 0)

        monster = combat.state.monsters[0]
        assert monster.hp == 37
        assert monster.get_power_amount("Weak") == 1

    def test_neutralize_plus_upgrades_weak_amount(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Neutralize", upgraded=True)], draw_cards=[])

        assert combat.play_card(0, 0)

        monster = combat.state.monsters[0]
        assert monster.hp == 36
        assert monster.get_power_amount("Weak") == 2

    def test_survivor_gains_block_then_discards_first_other_card(self):
        combat = _make_combat()
        _set_piles(
            combat,
            hand_cards=[CardInstance("Survivor"), CardInstance("Strike")],
            draw_cards=[],
        )

        assert combat.play_card(0)

        assert combat.state.player.block == 8
        assert combat.state.card_manager.hand.cards == []
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Strike", "Survivor"]

    def test_survivor_does_not_discard_itself(self):
        combat = _make_combat()
        _set_piles(
            combat,
            hand_cards=[CardInstance("Survivor"), CardInstance("Neutralize")],
            draw_cards=[],
        )

        assert combat.play_card(0)

        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Neutralize", "Survivor"]
