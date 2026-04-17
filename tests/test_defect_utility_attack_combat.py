from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.orbs import FrostOrb, LightningOrb
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 40, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hps: list[int] | None = None, energy: int = 3, attack_damage: int = 0) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyMonster(f"Dummy{index}", hp=hp, attack_damage=attack_damage)
        for index, hp in enumerate(monster_hps or [40])
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=75,
        player_max_hp=75,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["CompileDriver", "Hologram", "Rebound", "Streamline", "Leap", "Glacier"],
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


class TestDefectUtilityAttackCombat:
    def test_compile_driver_draws_only_on_kill(self):
        combat = _make_combat(monster_hps=[7], energy=1)
        _set_piles(combat, hand_cards=[CardInstance("CompileDriver")], draw_cards=[CardInstance("Strike_B")])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].is_dead()
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Strike_B"]

        non_kill = _make_combat(monster_hps=[20], energy=1)
        _set_piles(non_kill, hand_cards=[CardInstance("CompileDriver")], draw_cards=[CardInstance("Strike_B")])
        assert non_kill.play_card(0, 0)
        assert non_kill.state.monsters[0].hp == 13
        assert non_kill.state.card_manager.hand.cards == []

    def test_hologram_gains_block_and_recovers_without_retain(self):
        combat = _make_combat(energy=1)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Hologram")],
            draw_cards=[],
            discard_cards=[CardInstance("Strike_B")],
        )

        assert combat.play_card(0)

        assert combat.state.player.block == 3
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Strike_B"]
        assert combat.state.card_manager.hand.cards[0].retain is False
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Hologram"]

    def test_hologram_plus_no_longer_exhausts(self):
        combat = _make_combat(energy=1)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Hologram", upgraded=True)],
            draw_cards=[],
            discard_cards=[CardInstance("Strike_B")],
        )

        assert combat.play_card(0)

        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == []
        assert any(card.card_id == "Hologram" for card in combat.state.card_manager.discard_pile.cards)

    def test_rebound_moves_the_next_non_power_played_card_to_the_top_of_draw_pile(self):
        combat = _make_combat(energy=2)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Rebound"), CardInstance("Strike_B")],
            draw_cards=[CardInstance("Strike_B"), CardInstance("Defend_B")],
        )

        assert combat.play_card(0, 0)
        assert combat.state.player.get_power_amount("Rebound") == 1

        assert combat.play_card(0, 0)

        assert combat.state.player.get_power_amount("Rebound") == 0
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Rebound"]
        assert combat.state.card_manager.draw_pile.cards[-1].card_id == "Strike_B"

    def test_streamline_reduces_same_instance_cost_across_piles(self):
        combat = _make_combat(energy=2)
        streamline = CardInstance("Streamline")
        _set_piles(combat, hand_cards=[streamline], draw_cards=[])

        assert combat.play_card(0, 0)

        stored = combat.state.card_manager.discard_pile.cards[-1]
        assert stored.card_id == "Streamline"
        assert stored.combat_cost_reduction == 1
        assert stored.cost_for_turn == 1

        combat.state.player.energy = 2
        combat.state.card_manager.set_energy(2)
        combat.state.card_manager.discard_pile.remove(stored)
        combat.state.card_manager.hand.add(stored)

        assert combat.play_card(0, 0)
        stored = combat.state.card_manager.discard_pile.cards[-1]
        assert stored.cost_for_turn == 0

        combat.state.player.energy = 2
        combat.state.card_manager.set_energy(2)
        combat.state.card_manager.discard_pile.remove(stored)
        combat.state.card_manager.hand.add(stored)

        assert combat.play_card(0, 0)
        stored = combat.state.card_manager.discard_pile.cards[-1]
        assert stored.cost_for_turn == 0

    def test_leap_gains_block(self):
        combat = _make_combat(energy=1)
        _set_piles(combat, hand_cards=[CardInstance("Leap")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.block == 9

    def test_glacier_gains_block_and_channels_frost_with_focus_and_overflow(self):
        combat = _make_combat(monster_hps=[40], energy=2, attack_damage=0)
        combat.state.player.focus = 1
        combat.state.player.orbs.channels = [LightningOrb(), LightningOrb(), LightningOrb()]
        combat.state.player.orbs.owner = combat.state.player
        combat.state.player.orbs.combat_state = combat.state
        combat.state.player.orbs.slots = combat.state.player.max_orbs
        _set_piles(combat, hand_cards=[CardInstance("Glacier")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.block == 7
        assert combat.state.monsters[0].hp == 22
        assert len(combat.state.player.orbs) == 3
        assert isinstance(combat.state.player.orbs.channels[-1], FrostOrb)
        assert isinstance(combat.state.player.orbs.channels[-2], FrostOrb)

        combat.end_player_turn()

        assert combat.state.monsters[0].hp == 18
        assert combat.state.player.hp == 75

    def test_glacier_plus_only_increases_block(self):
        combat = _make_combat(energy=2)
        _set_piles(combat, hand_cards=[CardInstance("Glacier", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.block == 10
        assert len(combat.state.player.orbs) == 2
