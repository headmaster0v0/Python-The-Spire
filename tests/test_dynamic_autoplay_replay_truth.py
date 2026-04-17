from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.potion_effects import use_potion
from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.potions import create_potion
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


def _make_combat(
    *,
    monster_hps: list[int] | None = None,
    energy: int = 4,
    relics: list[str] | None = None,
) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [DummyAttackMonster(f"Dummy{index}", hp=hp) for index, hp in enumerate(monster_hps or [40])]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=75,
        player_max_hp=75,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=[
            "AfterImage",
            "DoubleTap",
            "Whirlwind",
            "Burst",
            "LegSweep",
            "Defend",
            "Nightmare",
            "RitualDagger#18+",
            "Rebound",
            "EchoForm",
            "Strike",
            "Havoc",
            "Omniscience",
        ],
        relics=relics or [],
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


def _start_fresh_player_turn(combat: CombatEngine, *, energy: int) -> None:
    combat.state.cards_played_this_turn.clear()
    combat.state.player.energy = energy
    combat.state.card_manager.set_energy(energy)
    combat.state.player.powers.at_start_of_turn(combat.state.player)


def test_burst_replays_targeted_skill_on_same_target_without_reopening_choice() -> None:
    combat = _make_combat(monster_hps=[50, 50], energy=4)
    _set_piles(
        combat,
        hand_cards=[CardInstance("Burst"), CardInstance("LegSweep")],
        draw_cards=[],
    )

    assert combat.play_card(0)
    assert combat.play_card(0, 1)

    assert combat.state.player.block == 22
    assert combat.state.monsters[0].get_power_amount("Weak") == 0
    assert combat.state.monsters[1].get_power_amount("Weak") == 4
    assert combat.state.pending_combat_choice is None


def test_burst_plus_consumes_two_skills_without_recursive_replay() -> None:
    combat = _make_combat(monster_hps=[40], energy=4)
    _set_piles(
        combat,
        hand_cards=[CardInstance("Burst", upgraded=True), CardInstance("Defend"), CardInstance("Defend")],
        draw_cards=[],
    )

    assert combat.play_card(0)
    assert combat.state.player.get_power_amount("Burst") == 2

    assert combat.play_card(0)
    assert combat.state.player.block == 10
    assert combat.state.player.get_power_amount("Burst") == 1

    assert combat.play_card(0)
    assert combat.state.player.block == 20
    assert combat.state.player.get_power_amount("Burst") == 0


def test_double_tap_replayed_attack_triggers_normal_card_play_callbacks() -> None:
    combat = _make_combat(monster_hps=[40], energy=4)
    _set_piles(
        combat,
        hand_cards=[CardInstance("AfterImage"), CardInstance("DoubleTap"), CardInstance("Strike")],
        draw_cards=[],
    )

    assert combat.play_card(0)
    assert combat.play_card(0)
    assert combat.play_card(0, 0)

    assert combat.state.player.block == 4
    assert combat.state.monsters[0].hp == 28
    assert combat.state.pending_combat_choice is None


def test_double_tap_preserves_original_x_value_for_replayed_attack() -> None:
    combat = _make_combat(monster_hps=[40], energy=4)
    _set_piles(
        combat,
        hand_cards=[CardInstance("DoubleTap"), CardInstance("Whirlwind")],
        draw_cards=[],
    )

    assert combat.play_card(0)
    assert combat.play_card(0, 0)

    assert combat.state.player.energy == 0
    assert combat.state.monsters[0].hp == 10


def test_echo_form_only_duplicates_the_first_original_card_each_turn() -> None:
    combat = _make_combat(monster_hps=[40], energy=3)
    combat.state.player.add_power(create_power("EchoForm", 1, "player"))
    _start_fresh_player_turn(combat, energy=2)
    _set_piles(combat, hand_cards=[CardInstance("Strike"), CardInstance("Strike")], draw_cards=[])

    assert combat.play_card(0, 0)
    assert combat.state.monsters[0].hp == 28

    assert combat.play_card(0, 0)
    assert combat.state.monsters[0].hp == 22


def test_nightmare_preserves_special_runtime_identity_and_respects_hand_limit() -> None:
    combat = _make_combat(monster_hps=[40], energy=3)
    ritual = CardInstance("RitualDagger#18+")
    filler = [CardInstance("Defend") for _ in range(8)]
    _set_piles(combat, hand_cards=[CardInstance("Nightmare"), ritual], draw_cards=[])

    assert combat.play_card(0)
    combat.state.card_manager.hand.cards = _bind_cards(combat, [ritual] + filler)

    results = combat.state.player.powers.at_start_of_turn(combat.state.player)

    hand_runtime_ids = [card.runtime_card_id for card in combat.state.card_manager.hand.cards]
    discard_runtime_ids = [card.runtime_card_id for card in combat.state.card_manager.discard_pile.cards]

    assert results == [{"type": "nightmare_generate", "count": 3}]
    assert hand_runtime_ids.count("RitualDagger#18+") == 2
    assert discard_runtime_ids.count("RitualDagger#18+") == 2
    assert combat.state.player.get_power_amount("Nightmare") == 0


def test_rebound_moves_the_next_non_power_played_card_to_the_top_of_draw_pile() -> None:
    combat = _make_combat(monster_hps=[40], energy=2)
    _set_piles(
        combat,
        hand_cards=[CardInstance("Rebound"), CardInstance("Strike")],
        draw_cards=[CardInstance("Defend")],
    )

    assert combat.play_card(0, 0)
    assert combat.state.player.get_power_amount("Rebound") == 1

    assert combat.play_card(0, 0)

    assert combat.state.player.get_power_amount("Rebound") == 0
    assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Rebound"]
    assert combat.state.card_manager.draw_pile.cards[-1].card_id == "Strike"


def test_rebound_expires_cleanly_at_end_of_turn_if_unused() -> None:
    combat = _make_combat(monster_hps=[40], energy=1)
    _set_piles(combat, hand_cards=[CardInstance("Rebound")], draw_cards=[CardInstance("Strike")])

    assert combat.play_card(0, 0)
    assert combat.state.player.get_power_amount("Rebound") == 1

    combat.end_player_turn()

    assert combat.state.player.get_power_amount("Rebound") == 0


def test_omniscience_reuses_the_first_autoplay_target_for_replayed_copies() -> None:
    combat = _make_combat(monster_hps=[20, 20], energy=4)
    _set_piles(
        combat,
        hand_cards=[CardInstance("Omniscience")],
        draw_cards=[CardInstance("Strike")],
    )

    assert combat.play_card(0)
    assert combat.choose_combat_option(0) is True

    hp_values = [monster.hp for monster in combat.state.monsters]
    assert sorted(hp_values) == [8, 20]
    assert combat.state.pending_combat_choice is None


def test_havoc_mayhem_and_distilled_chaos_leave_no_residual_choice_when_no_targets_exist() -> None:
    havoc = _make_combat(monster_hps=[1], energy=1)
    havoc_dead = DummyAttackMonster("AlreadyDead", hp=0)
    havoc_dead.is_dying = True
    havoc.state.monsters = [havoc_dead]
    _set_piles(havoc, hand_cards=[CardInstance("Havoc")], draw_cards=[CardInstance("Strike")])
    assert havoc.play_card(0)
    assert [card.card_id for card in havoc.state.card_manager.exhaust_pile.cards] == ["Strike"]
    assert [card.card_id for card in havoc.state.card_manager.discard_pile.cards] == ["Havoc"]
    assert havoc.state.pending_combat_choice is None

    mayhem = _make_combat(monster_hps=[1], energy=1)
    mayhem_dead = DummyAttackMonster("AlreadyDead", hp=0)
    mayhem_dead.is_dying = True
    mayhem.state.monsters = [mayhem_dead]
    mayhem.state.player.add_power(create_power("Mayhem", 1, "player"))
    _set_piles(mayhem, hand_cards=[], draw_cards=[CardInstance("Strike")])
    mayhem.state.player.powers.at_start_of_turn(mayhem.state.player)
    assert [card.card_id for card in mayhem.state.card_manager.discard_pile.cards] == ["Strike"]
    assert mayhem.state.pending_combat_choice is None

    chaos = _make_combat(monster_hps=[1], energy=1)
    chaos_dead = DummyAttackMonster("AlreadyDead", hp=0)
    chaos_dead.is_dying = True
    chaos.state.monsters = [chaos_dead]
    _set_piles(chaos, hand_cards=[], draw_cards=[CardInstance("Strike")])
    potion = create_potion("DistilledChaos")
    assert potion is not None
    use_potion(potion, chaos.state)
    assert [card.card_id for card in chaos.state.card_manager.discard_pile.cards] == ["Strike"]
    assert chaos.state.pending_combat_choice is None
