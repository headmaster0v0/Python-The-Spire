from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.run.events import Event, EventChoice
from sts_py.engine.run.run_engine import RunEngine, RunPhase


SEED_LONG = 4452322743548530140
SEED_STRING = "CARDTRUTHDEDICATED"


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 80):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=6, name="Attack"))


def _make_combat(*, monster_hps: list[int] | None = None, energy: int = 3) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyAttackMonster(f"Dummy{index}", hp=hp)
        for index, hp in enumerate(monster_hps or [80])
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=72,
        player_max_hp=72,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Brilliance", "Defend_P", "Eruption"],
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


def _set_hand(combat: CombatEngine, card_ids: list[str]) -> None:
    combat.state.card_manager.hand.cards = _bind_cards(combat, [CardInstance(card_id) for card_id in card_ids])
    combat.state.card_manager.draw_pile.cards = []
    combat.state.card_manager.discard_pile.cards = []
    combat.state.card_manager.exhaust_pile.cards = []


def test_brilliance_scales_from_mantra_gained_this_combat() -> None:
    combat = _make_combat(monster_hps=[40], energy=2)
    _set_hand(combat, ["Brilliance+"])
    combat.state.player._mantra_gained_this_combat = 5

    brilliance = combat.state.card_manager.hand.cards[0]
    brilliance.apply_powers(combat.state)
    brilliance.calculate_card_damage(combat.state, combat.state.monsters[0])

    assert brilliance.base_damage == 21
    assert brilliance.damage == 21
    assert combat.play_card(0, 0)
    assert combat.state.monsters[0].hp == 19


def test_necronomicurse_returns_to_hand_when_exhausted() -> None:
    combat = _make_combat(monster_hps=[40], energy=3)
    necronomicurse = CardInstance("Necronomicurse")
    _set_hand(combat, [])
    combat.state.card_manager.hand.cards = _bind_cards(combat, [necronomicurse])

    played = combat.state.card_manager.play_card(0, exhaust=True)

    assert played is necronomicurse
    assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Necronomicurse"]
    assert combat.state.card_manager.exhaust_pile.cards == []


def test_unremovable_curses_and_parasite_penalty_follow_event_rules() -> None:
    remove_engine = RunEngine.create(SEED_STRING, ascension=0)
    remove_engine.state.phase = RunPhase.EVENT
    remove_engine.state.deck = ["CurseOfTheBell"]
    remove_engine._current_event = Event(
        id="Remove Curse",
        name="Remove Curse",
        choices=[EventChoice(description="remove", requires_card_removal=True)],
    )

    assert remove_engine.choose_event_option(0) == {"success": False, "reason": "no_removable_cards"}

    transform_engine = RunEngine.create(SEED_STRING, ascension=0)
    transform_engine.state.phase = RunPhase.EVENT
    transform_engine.state.deck = ["Necronomicurse"]
    transform_engine._current_event = Event(
        id="Transform Curse",
        name="Transform Curse",
        choices=[EventChoice(description="transform", requires_card_transform=True)],
    )

    assert transform_engine.choose_event_option(0) == {"success": False, "reason": "no_removable_cards"}

    parasite_engine = RunEngine.create(SEED_STRING, ascension=0)
    parasite_engine.state.phase = RunPhase.EVENT
    parasite_engine.state.player_hp = 80
    parasite_engine.state.player_max_hp = 80
    parasite_engine.state.deck = ["Parasite"]
    parasite_engine._current_event = Event(
        id="Remove Parasite",
        name="Remove Parasite",
        choices=[EventChoice(description="remove", requires_card_removal=True)],
    )

    choice_result = parasite_engine.choose_event_option(0)
    assert choice_result["success"] is True
    assert choice_result["requires_card_choice"] is True

    remove_result = parasite_engine.choose_card_for_event(0)
    assert remove_result == {"success": True, "action": "card_removed", "card_id": "Parasite"}
    assert parasite_engine.state.deck == []
    assert parasite_engine.state.player_max_hp == 77
    assert parasite_engine.state.player_hp == 77


def test_astrolabe_transform_respects_curse_hooks_for_omamori_and_darkstone() -> None:
    omamori_engine = RunEngine.create(SEED_STRING, ascension=0)
    omamori_engine.state.player_hp = 80
    omamori_engine.state.player_max_hp = 80
    omamori_engine.state.deck = ["Parasite"]
    omamori_engine.state.relics.append("Omamori")
    omamori_engine.state.relic_counters["Omamori"] = 1

    omamori_engine._acquire_relic("Astrolabe", record_pending=False)

    assert omamori_engine.state.deck == []
    assert omamori_engine.state.player_max_hp == 77
    assert omamori_engine.state.player_hp == 77
    assert omamori_engine.state.relic_counters["Omamori"] == 0

    darkstone_engine = RunEngine.create(SEED_STRING, ascension=0)
    darkstone_engine.state.player_hp = 80
    darkstone_engine.state.player_max_hp = 80
    darkstone_engine.state.deck = ["Parasite"]
    darkstone_engine.state.relics.append("DarkstonePeriapt")

    darkstone_engine._acquire_relic("Astrolabe", record_pending=False)

    assert len(darkstone_engine.state.deck) == 1
    assert darkstone_engine.state.player_max_hp == 83
    assert darkstone_engine.state.player_hp == 83
