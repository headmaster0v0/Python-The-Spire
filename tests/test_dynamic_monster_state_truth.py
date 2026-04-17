from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.potion_effects import use_potion
from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.potions import create_potion
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.city_beyond import Darkling, Nemesis
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 20):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=0, name="Attack"))


class DummyMinionMonster(DummyAttackMonster):
    def __init__(self, monster_id: str = "DummyMinion", *, hp: int = 10):
        super().__init__(monster_id, hp=hp)
        self.is_minion = True


def _make_combat(*, monsters: list[MonsterBase], energy: int = 2) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=80,
        player_max_hp=80,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Feed", "HandOfGreed", "SuckerPunch", "Strike"],
        relics=[],
    )
    combat.state.player.energy = energy
    combat.state.player.max_energy = energy
    combat.state.card_manager.set_energy(energy)
    combat.state.card_manager.set_max_energy(energy)
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
    card_manager = combat.state.card_manager
    card_manager.hand.cards = _bind_cards(combat, hand_cards or [])
    card_manager.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    card_manager.discard_pile.cards = _bind_cards(combat, discard_cards or [])
    card_manager.exhaust_pile.cards = []


def test_feed_does_not_grant_max_hp_when_killing_a_minion() -> None:
    combat = _make_combat(monsters=[DummyMinionMonster()], energy=1)
    combat.state.player.hp = 70
    _set_piles(combat, hand_cards=[CardInstance("Feed")], draw_cards=[])

    assert combat.play_card(0, 0)

    assert combat.state.monsters[0].is_dead() is True
    assert combat.state.player.max_hp == 80
    assert combat.state.player.hp == 70


def test_hand_of_greed_does_not_grant_bonus_gold_when_killing_a_minion() -> None:
    combat = _make_combat(monsters=[DummyMinionMonster()], energy=2)
    _set_piles(combat, hand_cards=[CardInstance("HandOfGreed")], draw_cards=[])

    assert combat.play_card(0, 0)

    assert combat.state.monsters[0].is_dead() is True
    assert combat.state.pending_bonus_gold == 0


def test_feed_and_hand_of_greed_do_not_reward_darkling_half_dead_transition() -> None:
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    darklings = [Darkling.create(hp_rng, ascension=0) for _ in range(3)]
    darklings[0].hp = 5
    darklings[1].hp = 10
    darklings[2].hp = 10

    feed_combat = _make_combat(monsters=darklings, energy=1)
    feed_combat.state.player.hp = 70
    _set_piles(feed_combat, hand_cards=[CardInstance("Feed")], draw_cards=[])

    assert feed_combat.play_card(0, 0)

    target = feed_combat.state.monsters[0]
    assert target.half_dead is True
    assert target.is_dead() is False
    assert feed_combat.state.player.max_hp == 80
    assert feed_combat.state.player.hp == 70

    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    darklings = [Darkling.create(hp_rng, ascension=0) for _ in range(3)]
    darklings[0].hp = 5
    darklings[1].hp = 10
    darklings[2].hp = 10

    greed_combat = _make_combat(monsters=darklings, energy=2)
    _set_piles(greed_combat, hand_cards=[CardInstance("HandOfGreed")], draw_cards=[])

    assert greed_combat.play_card(0, 0)

    target = greed_combat.state.monsters[0]
    assert target.half_dead is True
    assert target.is_dead() is False
    assert greed_combat.state.pending_bonus_gold == 0


def test_nemesis_intangible_clamps_incoming_damage_on_real_runtime_monster() -> None:
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    nemesis = Nemesis.create(hp_rng, ascension=0)
    combat = _make_combat(monsters=[nemesis], energy=1)

    nemesis.add_power(create_power("Intangible", 1, nemesis.id))
    hp_before = nemesis.hp

    dealt = nemesis.take_damage(20)

    assert dealt == 1
    assert hp_before - nemesis.hp == 1
    assert nemesis.get_power_amount("Intangible") == 1
    assert combat.state.pending_combat_choice is None


def test_distilled_chaos_targeted_card_with_no_alive_target_discards_cleanly() -> None:
    monster = DummyAttackMonster("AlreadyDead", hp=0)
    monster.is_dying = True
    combat = _make_combat(monsters=[monster], energy=3)
    potion = create_potion("DistilledChaos")
    assert potion is not None

    _set_piles(
        combat,
        hand_cards=[],
        draw_cards=[CardInstance("Strike")],
        discard_cards=[],
    )

    use_potion(potion, combat.state)

    assert combat.state.card_manager.draw_pile.cards == []
    assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Strike"]
    assert combat.state.card_manager.hand.cards == []
    assert combat.state.pending_combat_choice is None


def test_sucker_punch_damage_still_lands_through_artifact_while_debuff_is_blocked() -> None:
    combat = _make_combat(monsters=[DummyAttackMonster("ArtifactDummy", hp=20)], energy=1)
    combat.state.monsters[0].add_power(create_power("Artifact", 1, combat.state.monsters[0].id))
    _set_piles(combat, hand_cards=[CardInstance("SuckerPunch")], draw_cards=[])

    assert combat.play_card(0, 0)

    monster = combat.state.monsters[0]
    assert monster.hp == 13
    assert monster.get_power_amount("Artifact") == 0
    assert monster.get_power_amount("Weak") == 0
