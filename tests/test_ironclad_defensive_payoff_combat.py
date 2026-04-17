from __future__ import annotations

from sts_py.engine.combat.card_effects import FlameBarrierEffect, PowerThroughEffect, RageEffect, get_card_effects
from sts_py.engine.combat.combat_engine import CombatEngine
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


class DummyMultiHitMonster(MonsterBase):
    def __init__(self, hp: int = 120, attack_damage: int = 0, hit_count: int = 2):
        super().__init__(id="DummyMultiHit", name="Dummy Multi Hit", hp=hp, max_hp=hp)
        self.attack_damage = attack_damage
        self.hit_count = hit_count

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, multiplier=self.hit_count, name="Multi Attack"))

    def take_turn(self, player) -> None:
        damage = self.get_intent_damage()
        for _ in range(self.hit_count):
            player.take_damage(damage)


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


def _make_multi_hit_combat(*, monster_hp: int = 120, attack_damage: int = 0, hit_count: int = 2) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monster = DummyMultiHitMonster(hp=monster_hp, attack_damage=attack_damage, hit_count=hit_count)
    return CombatEngine.create_with_monsters(
        monsters=[monster],
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


class TestIroncladDefensivePayoffEffects:
    def test_rage_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("Rage"))

        assert len(effects) == 1
        assert isinstance(effects[0], RageEffect)

    def test_flame_barrier_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("FlameBarrier"))

        assert len(effects) == 1
        assert isinstance(effects[0], FlameBarrierEffect)

    def test_power_through_effect_mapping_exists(self):
        effects = get_card_effects(CardInstance("PowerThrough"))

        assert len(effects) == 1
        assert isinstance(effects[0], PowerThroughEffect)

    def test_ghostly_armor_is_ethereal_metadata(self):
        card = CardInstance("GhostlyArmor")

        assert card.is_ethereal is True
        assert card.exhaust is False


class TestIroncladDefensivePayoffIntegration:
    def test_metallicize_gives_block_before_monster_attack(self):
        combat = _make_combat(attack_damage=3)
        _set_piles(combat, hand_cards=[CardInstance("Metallicize")], draw_cards=[])

        assert combat.play_card(0)
        combat.end_player_turn()

        assert combat.state.player.hp == 80
        assert combat.state.player.block == 0
        assert combat.state.player.get_power_amount("Metallicize") == 3

    def test_rage_triggers_on_attack_only(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Rage"), CardInstance("Strike"), CardInstance("Defend")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Rage") == 3

        assert combat.play_card(0, 0)
        assert combat.state.player.block == 3

        block_before_defend = combat.state.player.block
        assert combat.play_card(0)
        assert combat.state.player.block == block_before_defend + 5

    def test_rage_expires_after_turn_end(self):
        combat = _make_combat(attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Rage")], draw_cards=[])

        assert combat.play_card(0)
        combat.end_player_turn()

        assert combat.state.player.get_power_amount("Rage") == 0

    def test_flame_barrier_blocks_and_reflects_attack(self):
        combat = _make_combat(monster_hp=30, attack_damage=10)
        _set_piles(combat, hand_cards=[CardInstance("FlameBarrier")], draw_cards=[])

        assert combat.play_card(0)
        combat.end_player_turn()

        assert combat.state.player.hp == 80
        assert combat.state.monsters[0].hp == 26
        assert combat.state.player.get_power_amount("FlameBarrier") == 0

    def test_flame_barrier_reflects_each_hit_of_multi_attack(self):
        combat = _make_multi_hit_combat(monster_hp=30, attack_damage=3, hit_count=2)
        _set_piles(combat, hand_cards=[CardInstance("FlameBarrier")], draw_cards=[])

        assert combat.play_card(0)
        combat.end_player_turn()

        assert combat.state.player.hp == 80
        assert combat.state.monsters[0].hp == 22
        assert combat.state.player.get_power_amount("FlameBarrier") == 0

    def test_ghostly_armor_exhausts_if_unplayed_at_end_of_turn(self):
        combat = _make_combat(attack_damage=0)
        ghostly_armor = CardInstance("GhostlyArmor")
        _set_piles(combat, hand_cards=[ghostly_armor], draw_cards=[])

        combat.end_player_turn()

        assert combat.state.card_manager.hand.cards == []
        assert combat.state.card_manager.exhaust_pile.cards == [ghostly_armor]

    def test_power_through_gives_block_and_creates_two_real_wounds(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("PowerThrough")], draw_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.block == 15
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Wound", "Wound"]
        assert all(card._combat_state is combat.state for card in combat.state.card_manager.hand.cards)

    def test_power_through_respects_hand_limit(self):
        combat = _make_combat()
        hand_cards = [CardInstance("PowerThrough")] + [CardInstance("Strike") for _ in range(9)]
        _set_piles(combat, hand_cards=hand_cards, draw_cards=[], discard_cards=[])

        assert combat.play_card(0)

        assert combat.state.player.block == 15
        assert len(combat.state.card_manager.hand.cards) == 10
        assert [card.card_id for card in combat.state.card_manager.hand.cards].count("Wound") == 1
        assert sorted(card.card_id for card in combat.state.card_manager.discard_pile.cards) == ["PowerThrough", "Wound"]
