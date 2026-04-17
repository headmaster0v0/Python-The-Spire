from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import ALL_CARD_DEFS, COLORLESS_ALL_DEFS, CardRarity, CardType
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.run.run_engine import RunEngine, RunPhase
from sts_py.engine.run.shop import COLORLESS_RARE_POOL, COLORLESS_UNCOMMON_POOL


SEED_LONG = 4452322743548530140
DISCOVERY_HEALING_EXCLUDED_IDS = {"Feed", "Reaper", "SelfRepair"}


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, hp: int = 80, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))

    def take_turn(self, player) -> None:
        if self.attack_damage > 0:
            player.take_damage(self.attack_damage)


def _make_combat(*, monster_hp: int = 80, attack_damage: int = 0, monster_count: int = 1, energy: int = 3) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyAttackMonster(f"DummyAttack{index}", hp=monster_hp, attack_damage=attack_damage)
        for index in range(monster_count)
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=80,
        player_max_hp=80,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Strike", "Strike", "Strike", "Defend", "Defend", "Defend", "Defend", "Bash", "PommelStrike"],
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
    exhaust_cards: list[CardInstance] | None = None,
) -> None:
    card_manager = combat.state.card_manager
    card_manager.hand.cards = _bind_cards(combat, hand_cards or [])
    card_manager.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    card_manager.discard_pile.cards = _bind_cards(combat, discard_cards or [])
    card_manager.exhaust_pile.cards = _bind_cards(combat, exhaust_cards or [])


def _choice_index_by_label(combat: CombatEngine, label: str) -> int:
    for index, option in enumerate(combat.get_pending_choices()):
        if option.get("label") == label:
            return index
    raise AssertionError(f"pending choice with label {label!r} not found")


def _choice_index_by_card_id(combat: CombatEngine, card_id: str) -> int:
    for index, option in enumerate(combat.get_pending_choices()):
        if option.get("card_id") == card_id:
            return index
    raise AssertionError(f"pending choice with card_id {card_id!r} not found")


def test_phase251_aliases_and_shop_pools_surface_new_cards() -> None:
    assert CardInstance("Secret Technique").card_id == "SecretTechnique"
    assert CardInstance("Secret Weapon").card_id == "SecretWeapon"
    assert CardInstance("Thinking Ahead").card_id == "ThinkingAhead"

    for card_id in {"Discovery", "Forethought", "Purity"}:
        assert card_id in COLORLESS_UNCOMMON_POOL
    for card_id in {"SecretTechnique", "SecretWeapon", "ThinkingAhead"}:
        assert card_id in COLORLESS_RARE_POOL


def test_discovery_opens_three_unique_runtime_colored_choices() -> None:
    combat = _make_combat()
    _set_piles(combat, hand_cards=[CardInstance("Discovery")], draw_cards=[])

    assert combat.play_card(0)

    choices = combat.get_pending_choices()
    assert len(choices) == 3
    assert len({choice["card_id"] for choice in choices}) == 3
    assert all(choice["card_id"] not in COLORLESS_ALL_DEFS for choice in choices)
    assert all(ALL_CARD_DEFS[choice["card_id"]].rarity in {CardRarity.COMMON, CardRarity.UNCOMMON, CardRarity.RARE} for choice in choices)
    assert all(ALL_CARD_DEFS[choice["card_id"]].card_type in {CardType.ATTACK, CardType.SKILL, CardType.POWER} for choice in choices)
    assert all(choice["card_id"] not in DISCOVERY_HEALING_EXCLUDED_IDS for choice in choices)


def test_discovery_selection_adds_zero_cost_copy_to_hand() -> None:
    combat = _make_combat()
    _set_piles(combat, hand_cards=[CardInstance("Discovery")], draw_cards=[])

    assert combat.play_card(0)
    chosen_card_id = combat.get_pending_choices()[0]["card_id"]

    assert combat.choose_combat_option(0) is True

    hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
    assert hand_ids == [chosen_card_id]
    assert combat.state.card_manager.hand.cards[0].cost_for_turn == 0
    assert combat.state.card_manager.hand.cards[0].is_cost_modified_for_turn is True
    assert any(card.card_id == "Discovery" for card in combat.state.card_manager.exhaust_pile.cards)
    assert combat.state.pending_combat_choice is None


def test_discovery_master_reality_upgrades_selected_copy_and_full_hand_discards_choice() -> None:
    combat = _make_combat()
    combat.state.player.add_power(create_power("MasterReality", 1, "player"))
    _set_piles(combat, hand_cards=[CardInstance("Discovery")], draw_cards=[])

    assert combat.play_card(0)
    chosen_card_id = combat.get_pending_choices()[0]["card_id"]
    for _ in range(10):
        combat.state.card_manager.hand.add(CardInstance("Defend"))

    assert combat.choose_combat_option(0) is True

    assert all(card.card_id != chosen_card_id for card in combat.state.card_manager.hand.cards)
    discarded_cards = [card for card in combat.state.card_manager.discard_pile.cards if card.card_id == chosen_card_id]
    assert len(discarded_cards) == 1
    assert discarded_cards[0].upgraded is True
    assert discarded_cards[0].cost_for_turn == 0


def test_forethought_unupgraded_moves_selected_card_to_draw_pile_bottom_and_sets_free_play() -> None:
    combat = _make_combat()
    bash = CardInstance("Bash")
    defend = CardInstance("Defend")
    _set_piles(combat, hand_cards=[CardInstance("Forethought"), bash, defend], draw_cards=[CardInstance("Strike")])

    assert combat.play_card(0)
    assert [choice["card_id"] for choice in combat.get_pending_choices()] == ["Bash", "Defend"]
    assert combat.choose_combat_option(_choice_index_by_card_id(combat, "Bash")) is True

    hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
    draw_ids = [card.card_id for card in combat.state.card_manager.draw_pile.cards]

    assert hand_ids == ["Defend"]
    assert draw_ids[0] == "Bash"
    assert combat.state.card_manager.draw_pile.cards[0].free_to_play_once is True


def test_forethought_upgraded_allows_skip_or_multiple_picks() -> None:
    combat = _make_combat()
    _set_piles(
        combat,
        hand_cards=[CardInstance("Forethought", upgraded=True), CardInstance("Bash"), CardInstance("Bludgeon"), CardInstance("Defend")],
        draw_cards=[CardInstance("Strike")],
    )

    assert combat.play_card(0)
    assert combat.choose_combat_option(_choice_index_by_label(combat, "跳过")) is True
    assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Bash", "Bludgeon", "Defend"]

    combat = _make_combat()
    _set_piles(
        combat,
        hand_cards=[CardInstance("Forethought", upgraded=True), CardInstance("Bash"), CardInstance("Bludgeon"), CardInstance("Defend")],
        draw_cards=[CardInstance("Strike")],
    )

    assert combat.play_card(0)
    assert combat.choose_combat_option(_choice_index_by_card_id(combat, "Bash")) is True
    assert combat.state.pending_combat_choice is not None
    assert combat.choose_combat_option(_choice_index_by_card_id(combat, "Bludgeon")) is True
    assert combat.state.pending_combat_choice is not None
    assert combat.choose_combat_option(_choice_index_by_label(combat, "完成")) is True

    draw_ids = [card.card_id for card in combat.state.card_manager.draw_pile.cards]
    assert draw_ids[:3] == ["Bludgeon", "Bash", "Strike"]
    assert combat.state.card_manager.draw_pile.cards[0].free_to_play_once is True
    assert combat.state.card_manager.draw_pile.cards[1].free_to_play_once is True
    assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Defend"]


def test_purity_allows_zero_pick_and_respects_max_exhaust_count() -> None:
    combat = _make_combat()
    _set_piles(combat, hand_cards=[CardInstance("Purity"), CardInstance("Bash"), CardInstance("Defend")], draw_cards=[])

    assert combat.play_card(0)
    assert combat.choose_combat_option(_choice_index_by_label(combat, "跳过")) is True
    assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Bash", "Defend"]
    assert combat.state.card_manager.exhaust_pile.cards[-1].card_id == "Purity"

    combat = _make_combat()
    _set_piles(
        combat,
        hand_cards=[CardInstance("Purity"), CardInstance("Bash"), CardInstance("Defend"), CardInstance("Strike"), CardInstance("PommelStrike")],
        draw_cards=[],
    )

    assert combat.play_card(0)
    assert combat.choose_combat_option(_choice_index_by_card_id(combat, "Bash")) is True
    assert combat.choose_combat_option(_choice_index_by_card_id(combat, "Strike")) is True
    assert combat.choose_combat_option(_choice_index_by_card_id(combat, "PommelStrike")) is True
    assert combat.state.pending_combat_choice is None

    exhaust_ids = [card.card_id for card in combat.state.card_manager.exhaust_pile.cards]
    assert exhaust_ids.count("Purity") == 1
    assert exhaust_ids.count("Bash") == 1
    assert exhaust_ids.count("Strike") == 1
    assert exhaust_ids.count("PommelStrike") == 1
    assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Defend"]


def test_secret_technique_requires_skill_in_draw_pile_and_supports_auto_and_explicit_pick() -> None:
    combat = _make_combat()
    _set_piles(combat, hand_cards=[CardInstance("SecretTechnique")], draw_cards=[CardInstance("Strike")])
    assert combat.play_card(0) is False

    combat = _make_combat()
    _set_piles(combat, hand_cards=[CardInstance("SecretTechnique"), CardInstance("Bash")], draw_cards=[CardInstance("Defend")])
    assert combat.play_card(0) is True
    assert combat.state.pending_combat_choice is None
    assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Bash", "Defend"]

    combat = _make_combat()
    _set_piles(
        combat,
        hand_cards=[CardInstance("SecretTechnique"), CardInstance("Defend")],
        draw_cards=[CardInstance("Bash"), CardInstance("Defend"), CardInstance("ShrugItOff")],
    )
    assert combat.play_card(0) is True
    assert {choice["card_id"] for choice in combat.get_pending_choices()} == {"Defend", "ShrugItOff"}
    assert combat.choose_combat_option(_choice_index_by_card_id(combat, "ShrugItOff")) is True
    assert "ShrugItOff" in [card.card_id for card in combat.state.card_manager.hand.cards]


def test_secret_weapon_requires_attack_in_draw_pile_and_full_hand_discards_selected_attack() -> None:
    combat = _make_combat()
    _set_piles(combat, hand_cards=[CardInstance("SecretWeapon")], draw_cards=[CardInstance("Defend")])
    assert combat.play_card(0) is False

    combat = _make_combat()
    _set_piles(
        combat,
        hand_cards=[CardInstance("SecretWeapon")] + [CardInstance("Defend") for _ in range(9)],
        draw_cards=[CardInstance("Bash"), CardInstance("Strike"), CardInstance("ShrugItOff")],
    )
    assert combat.play_card(0) is True
    assert combat.state.pending_combat_choice is not None
    chosen_card_id = combat.get_pending_choices()[0]["card_id"]
    combat.state.card_manager.hand.add(CardInstance("Defend"))

    assert combat.choose_combat_option(0) is True

    assert all(card.card_id != chosen_card_id for card in combat.state.card_manager.hand.cards)
    assert any(card.card_id == chosen_card_id for card in combat.state.card_manager.discard_pile.cards)


def test_thinking_ahead_auto_and_explicit_topdeck_behaviour() -> None:
    combat = _make_combat()
    _set_piles(combat, hand_cards=[CardInstance("ThinkingAhead")], draw_cards=[CardInstance("Strike")])

    assert combat.play_card(0) is True
    assert combat.state.pending_combat_choice is None
    assert [card.card_id for card in combat.state.card_manager.hand.cards] == []
    assert [card.card_id for card in combat.state.card_manager.draw_pile.cards] == ["Strike"]

    combat = _make_combat()
    _set_piles(
        combat,
        hand_cards=[CardInstance("ThinkingAhead"), CardInstance("Bash")],
        draw_cards=[CardInstance("Strike"), CardInstance("Defend")],
    )

    assert combat.play_card(0) is True
    assert {choice["card_id"] for choice in combat.get_pending_choices()} == {"Bash", "Strike", "Defend"}
    assert combat.choose_combat_option(_choice_index_by_card_id(combat, "Strike")) is True
    assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Bash", "Defend"]
    assert combat.state.card_manager.draw_pile.cards[-1].card_id == "Strike"


def test_run_engine_bridges_new_combat_choice_flow() -> None:
    engine = RunEngine.create("PHASE251DISCOVERY", ascension=0)
    combat = _make_combat()
    _set_piles(combat, hand_cards=[CardInstance("Discovery")], draw_cards=[])
    engine.state.combat = combat
    engine.state.phase = RunPhase.COMBAT

    assert engine.combat_play_card(0) is True
    choices = engine.get_combat_choices()
    assert len(choices) == 3
    assert engine.choose_combat_option(0) is True
    assert engine.state.combat.state.pending_combat_choice is None
