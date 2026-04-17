from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.run.run_engine import RunEngine, RunPhase
from sts_py.engine.simulation import ImprovedAI


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 50, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(
    *,
    monster_hps: list[int] | None = None,
    energy: int = 3,
    attack_damage: int = 0,
    relics: list[str] | None = None,
) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyAttackMonster(f"Dummy{index}", hp=hp, attack_damage=attack_damage)
        for index, hp in enumerate(monster_hps or [50])
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=70,
        player_max_hp=70,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["WellLaidPlans", "Equilibrium", "Safety", "Strike", "Defend", "Neutralize", "Dazed"],
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
    card_manager = combat.state.card_manager
    card_manager.hand.cards = _bind_cards(combat, hand_cards or [])
    card_manager.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    card_manager.discard_pile.cards = _bind_cards(combat, discard_cards or [])
    card_manager.exhaust_pile.cards = []


def test_well_laid_plans_opens_end_turn_retain_choice_and_auto_resumes_after_selection() -> None:
    combat = _make_combat(energy=1, attack_damage=0)
    _set_piles(combat, hand_cards=[CardInstance("WellLaidPlans", upgraded=True)], draw_cards=[])

    assert combat.play_card(0)
    _set_piles(
        combat,
        hand_cards=[CardInstance("Safety"), CardInstance("Strike"), CardInstance("Defend"), CardInstance("Neutralize"), CardInstance("Dazed")],
        draw_cards=[CardInstance("Survivor"), CardInstance("Backflip"), CardInstance("Slice"), CardInstance("Prepared"), CardInstance("Deflect")],
        discard_cards=combat.state.card_manager.discard_pile.cards,
    )

    combat.end_player_turn()

    pending = combat.state.pending_combat_choice
    assert pending is not None
    assert pending["selection_action"] == "retain_for_end_turn"
    assert pending["max_picks"] == 2
    assert [choice["card_id"] for choice in combat.get_pending_choices() if "card_id" in choice] == ["Strike", "Defend", "Neutralize"]

    assert combat.choose_combat_option(0) is True
    assert combat.state.pending_combat_choice is not None

    assert combat.choose_combat_option(0) is True
    assert combat.state.pending_combat_choice is None
    hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
    assert "Safety" in hand_ids
    assert "Strike" in hand_ids
    assert "Defend" in hand_ids
    assert "Neutralize" not in hand_ids
    assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["WellLaidPlans", "Neutralize"]
    assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Dazed"]


def test_well_laid_plans_auto_retains_when_candidate_count_does_not_exceed_amount() -> None:
    combat = _make_combat(energy=1, attack_damage=0)
    _set_piles(combat, hand_cards=[CardInstance("WellLaidPlans", upgraded=True)], draw_cards=[])

    assert combat.play_card(0)
    _set_piles(
        combat,
        hand_cards=[CardInstance("Strike"), CardInstance("Defend"), CardInstance("Dazed")],
        draw_cards=[CardInstance("Survivor"), CardInstance("Backflip"), CardInstance("Slice"), CardInstance("Prepared"), CardInstance("Deflect")],
        discard_cards=combat.state.card_manager.discard_pile.cards,
    )

    combat.end_player_turn()

    assert combat.state.pending_combat_choice is None
    hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
    assert "Strike" in hand_ids
    assert "Defend" in hand_ids
    assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Dazed"]


def test_runic_pyramid_retains_all_non_ethereal_and_suppresses_retain_choice() -> None:
    combat = _make_combat(energy=1, attack_damage=0, relics=["RunicPyramid"])
    combat.state.player.add_power(create_power("Retain Cards", 2, "player"))
    _set_piles(
        combat,
        hand_cards=[CardInstance("Safety"), CardInstance("Strike"), CardInstance("Defend"), CardInstance("Dazed")],
        draw_cards=[],
    )

    combat.end_player_turn()

    assert combat.state.pending_combat_choice is None
    assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Safety", "Strike", "Defend"]
    assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Dazed"]


def test_equilibrium_retains_non_ethereal_without_opening_choice() -> None:
    combat = _make_combat(energy=2, attack_damage=0)
    _set_piles(
        combat,
        hand_cards=[CardInstance("Equilibrium"), CardInstance("Strike"), CardInstance("Carnage")],
        draw_cards=[CardInstance("Survivor"), CardInstance("Backflip"), CardInstance("Slice"), CardInstance("Prepared"), CardInstance("Deflect")],
    )

    assert combat.play_card(0)

    combat.end_player_turn()

    assert combat.state.pending_combat_choice is None
    assert "Strike" in [card.card_id for card in combat.state.card_manager.hand.cards]
    assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Carnage"]


def test_run_engine_end_turn_choice_resolves_without_second_end_turn_call() -> None:
    engine = RunEngine.create("TURNBOUNDARY", ascension=0, character_class="SILENT")
    combat = _make_combat(energy=1, attack_damage=0)
    combat.state.player.add_power(create_power("Retain Cards", 1, "player"))
    _set_piles(
        combat,
        hand_cards=[CardInstance("Strike"), CardInstance("Defend")],
        draw_cards=[CardInstance("Survivor"), CardInstance("Backflip"), CardInstance("Slice"), CardInstance("Prepared"), CardInstance("Deflect")],
    )
    engine.state.combat = combat
    engine.state.phase = RunPhase.COMBAT

    engine.combat_end_turn()

    assert [choice["card_id"] for choice in engine.get_combat_choices() if "card_id" in choice] == ["Strike", "Defend"]
    assert engine.choose_combat_option(0) is True
    assert engine.get_combat_choices() == []
    assert "Strike" in [card.card_id for card in combat.state.card_manager.hand.cards]


def test_simulation_helper_consumes_end_turn_retain_choice_deterministically() -> None:
    engine = RunEngine.create("TURNBOUNDARYSIM", ascension=0, character_class="SILENT")
    combat = _make_combat(energy=1, attack_damage=0)
    combat.state.player.add_power(create_power("Retain Cards", 2, "player"))
    _set_piles(
        combat,
        hand_cards=[CardInstance("Safety"), CardInstance("Strike"), CardInstance("Defend"), CardInstance("Neutralize")],
        draw_cards=[CardInstance("Survivor"), CardInstance("Backflip"), CardInstance("Slice"), CardInstance("Prepared"), CardInstance("Deflect")],
    )
    engine.state.combat = combat
    engine.state.phase = RunPhase.COMBAT

    engine.combat_end_turn()
    assert combat.state.pending_combat_choice is not None

    ai = ImprovedAI(engine)
    ai._resolve_pending_end_turn_choices()

    assert combat.state.pending_combat_choice is None
    hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
    assert "Safety" in hand_ids
    assert "Strike" in hand_ids
    assert "Defend" in hand_ids
    assert "Neutralize" not in hand_ids
