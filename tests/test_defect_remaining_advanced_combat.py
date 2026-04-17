from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.orbs import LightningOrb
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.content.cards_min import CardRarity
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


def _make_combat(*, energy: int = 3, monster_hps: list[int] | None = None) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyMonster(f"Dummy{i}", hp=hp)
        for i, hp in enumerate(monster_hps or [40])
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=75,
        player_max_hp=75,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Bullseye", "Chill", "DoomAndGloom", "GeneticAlgorithm", "HelloWorld", "Hyperbeam", "BallLightning"],
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


class TestDefectRemainingAdvancedCombat:
    def test_bullseye_deals_damage_and_applies_lockon(self):
        combat = _make_combat(energy=1)
        _set_piles(combat, hand_cards=[CardInstance("Bullseye")], draw_cards=[])

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 32
        assert combat.state.monsters[0].get_power_amount("Lockon") == 2

        upgraded = _make_combat(energy=1)
        _set_piles(upgraded, hand_cards=[CardInstance("Bullseye", upgraded=True)], draw_cards=[])
        assert upgraded.play_card(0, 0)
        assert upgraded.state.monsters[0].hp == 29
        assert upgraded.state.monsters[0].get_power_amount("Lockon") == 3

    def test_chill_channels_frost_for_each_live_enemy(self):
        combat = _make_combat(energy=0, monster_hps=[40, 40, 40])
        _set_piles(combat, hand_cards=[CardInstance("Chill")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.orbs.filled_count() == 3
        assert [orb.orb_id for orb in combat.state.player.orbs.channels] == ["Frost", "Frost", "Frost"]
        assert CardInstance("Chill", upgraded=True).is_innate is True

    def test_doom_and_gloom_deals_aoe_and_channels_dark(self):
        combat = _make_combat(energy=2, monster_hps=[40, 40])
        _set_piles(combat, hand_cards=[CardInstance("DoomAndGloom")], draw_cards=[])

        assert combat.play_card(0)
        assert [monster.hp for monster in combat.state.monsters] == [30, 30]
        assert combat.state.player.orbs.filled_count() == 1
        assert combat.state.player.orbs.channels[0].orb_id == "Dark"

        upgraded = _make_combat(energy=2, monster_hps=[40, 40])
        _set_piles(upgraded, hand_cards=[CardInstance("DoomAndGloom", upgraded=True)], draw_cards=[])
        assert upgraded.play_card(0)
        assert [monster.hp for monster in upgraded.state.monsters] == [26, 26]

    def test_genetic_algorithm_gains_block_and_grows_current_instance(self):
        combat = _make_combat(energy=1)
        genetic_algorithm = CardInstance("GeneticAlgorithm")
        _set_piles(combat, hand_cards=[genetic_algorithm], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.block == 1
        played_copy = combat.state.card_manager.exhaust_pile.cards[-1]
        assert played_copy.card_id == "GeneticAlgorithm"
        assert played_copy.misc == 3
        assert played_copy.base_block == 3

        upgraded = _make_combat(energy=1)
        upgraded_card = CardInstance("GeneticAlgorithm", upgraded=True)
        _set_piles(upgraded, hand_cards=[upgraded_card], draw_cards=[])
        assert upgraded.play_card(0)
        upgraded_copy = upgraded.state.card_manager.exhaust_pile.cards[-1]
        assert upgraded_copy.misc == 4
        assert upgraded_copy.base_block == 4

    def test_hello_world_generates_random_defect_common_card_at_start_of_turn(self):
        combat = _make_combat(energy=1)
        _set_piles(combat, hand_cards=[CardInstance("HelloWorld")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Hello") == 1

        common_ids = {card.id for card in build_reward_pools("DEFECT")[CardRarity.COMMON]}
        combat.state.card_manager.hand.cards = []
        combat.state.player.powers.at_start_of_turn(combat.state.player)
        assert len(combat.state.card_manager.hand.cards) == 1
        generated = combat.state.card_manager.hand.cards[0]
        assert generated.card_id in common_ids
        assert generated.rarity == CardRarity.COMMON

        overflow = _make_combat(energy=1)
        _set_piles(
            overflow,
            hand_cards=[CardInstance("HelloWorld")] + [CardInstance("Strike_B") for _ in range(9)],
            draw_cards=[],
        )
        assert overflow.play_card(0)
        overflow.state.card_manager.hand.add(CardInstance("Defend_B"))
        overflow.state.player.powers.at_start_of_turn(overflow.state.player)
        assert len(overflow.state.card_manager.hand.cards) == 10
        assert len(overflow.state.card_manager.discard_pile.cards) == 2

    def test_hyperbeam_deals_aoe_and_reduces_focus(self):
        combat = _make_combat(energy=2, monster_hps=[50, 50])
        combat.state.player.orbs.channels = [LightningOrb()]
        combat.state.player.orbs.owner = combat.state.player
        combat.state.player.orbs.combat_state = combat.state
        _set_piles(combat, hand_cards=[CardInstance("Hyperbeam")], draw_cards=[])

        assert combat.play_card(0)
        assert [monster.hp for monster in combat.state.monsters] == [24, 24]
        assert combat.state.player.focus == -3
        assert combat.state.player.get_power_amount("Focus") == -3

        upgraded = _make_combat(energy=2, monster_hps=[50, 50])
        _set_piles(upgraded, hand_cards=[CardInstance("Hyperbeam", upgraded=True)], draw_cards=[])
        assert upgraded.play_card(0)
        assert [monster.hp for monster in upgraded.state.monsters] == [16, 16]
