from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 40, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hps: list[int] | None = None, energy: int = 3, relics: list[str] | None = None, attack_damage: int = 0) -> CombatEngine:
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
        deck=["Prepared", "Acrobatics", "Reflex", "Tactician", "Survivor"],
        relics=relics or [],
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


class TestSilentDiscardUtilityCombat:
    def test_prepared_draws_then_discards(self):
        combat = _make_combat()
        _set_piles(
            combat,
            hand_cards=[CardInstance("Prepared"), CardInstance("Strike"), CardInstance("Defend")],
            draw_cards=[CardInstance("Backflip")],
        )

        assert combat.play_card(0)

        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Defend", "Backflip"]
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Strike", "Prepared"]

    def test_prepared_plus_draws_two_discards_two(self):
        combat = _make_combat()
        _set_piles(
            combat,
            hand_cards=[CardInstance("Prepared", upgraded=True), CardInstance("Strike"), CardInstance("Defend")],
            draw_cards=[CardInstance("Backflip"), CardInstance("Slice")],
        )

        assert combat.play_card(0)

        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Slice", "Backflip"]
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Strike", "Defend", "Prepared"]

    def test_acrobatics_draws_then_discards_one(self):
        combat = _make_combat()
        _set_piles(
            combat,
            hand_cards=[CardInstance("Acrobatics"), CardInstance("Strike")],
            draw_cards=[CardInstance("Defend"), CardInstance("Slice"), CardInstance("Neutralize")],
        )

        assert combat.play_card(0)

        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Neutralize", "Slice", "Defend"]
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Strike", "Acrobatics"]

    def test_reflex_triggers_when_discarded_from_hand(self):
        combat = _make_combat(attack_damage=0)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Prepared"), CardInstance("Reflex")],
            draw_cards=[CardInstance("Strike"), CardInstance("Defend"), CardInstance("Slice")],
        )

        assert combat.play_card(0)

        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Slice", "Defend", "Strike"]

    def test_tactician_triggers_when_discarded_from_hand_and_syncs_energy(self):
        combat = _make_combat(attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Survivor"), CardInstance("Tactician")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.energy == 3
        assert combat.state.card_manager.energy == 3

    def test_tingsha_and_tough_bandages_trigger_on_survivor_discard(self):
        combat = _make_combat(monster_hps=[30], relics=["Tingsha", "ToughBandages"])
        _set_piles(
            combat,
            hand_cards=[CardInstance("Survivor"), CardInstance("Strike")],
            draw_cards=[],
        )

        assert combat.play_card(0)

        assert combat.state.player.block == 11
        assert combat.state.monsters[0].hp == 27

    def test_hovering_kite_only_triggers_first_discard_per_turn_once(self):
        combat = _make_combat(relics=["HoveringKite"])
        _set_piles(
            combat,
            hand_cards=[CardInstance("Prepared", upgraded=True), CardInstance("Strike"), CardInstance("Defend")],
            draw_cards=[CardInstance("Slice"), CardInstance("Backflip")],
        )

        assert combat.play_card(0)

        assert combat.state.player.energy == 4
        assert combat.state.card_manager.energy == 4

    def test_end_turn_hand_discard_uses_unified_discard_hook(self):
        combat = _make_combat(monster_hps=[30], relics=["Tingsha", "ToughBandages"], attack_damage=0)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Reflex")],
            draw_cards=[CardInstance("Strike"), CardInstance("Defend"), CardInstance("Slice")],
        )

        combat.end_player_turn()

        assert combat.state.monsters[0].hp == 27
        hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
        assert "Defend" in hand_ids
        assert "Strike" in hand_ids
        assert len(hand_ids) >= 2
