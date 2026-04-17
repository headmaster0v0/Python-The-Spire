from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import ALL_CARD_DEFS, COLORLESS_ALL_DEFS, CardRarity, CardType
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.run.shop import COLORLESS_RARE_POOL, COLORLESS_UNCOMMON_POOL


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, hp: int = 80, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))

    def take_turn(self, player) -> None:
        if self.attack_damage > 0:
            player.take_damage(self.attack_damage)


def _make_combat(*, monster_hp: int = 80, attack_damage: int = 0, monster_count: int = 1) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyAttackMonster(f"DummyAttack{index}", hp=monster_hp, attack_damage=attack_damage)
        for index in range(monster_count)
    ]
    return CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=80,
        player_max_hp=80,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Strike", "Strike", "Strike", "Defend", "Defend", "Defend", "Defend", "Bash", "PommelStrike"],
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
    exhaust_cards: list[CardInstance] | None = None,
) -> None:
    card_manager = combat.state.card_manager
    card_manager.hand.cards = _bind_cards(combat, hand_cards or [])
    card_manager.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    card_manager.discard_pile.cards = _bind_cards(combat, discard_cards or [])
    card_manager.exhaust_pile.cards = _bind_cards(combat, exhaust_cards or [])


def test_phase250_alias_cleanup_and_colorless_shop_pools_surface_runtime_cards() -> None:
    assert CardInstance("Bandage Up").card_id == "BandageUp"
    assert CardInstance("Dramatic Entrance").card_id == "DramaticEntrance"
    assert CardInstance("Jack Of All Trades").card_id == "JackOfAllTrades"
    assert CardInstance("J.A.X.").card_id == "JAX"
    assert CardInstance("Mind Blast").card_id == "MindBlast"
    assert CardInstance("VoidCard").card_id == "Void"

    for card_id in {
        "BandageUp",
        "DramaticEntrance",
        "Enlightenment",
        "Impatience",
        "JackOfAllTrades",
        "MindBlast",
    }:
        assert card_id in COLORLESS_UNCOMMON_POOL

    for card_id in {"Chrysalis", "Metamorphosis", "Violence"}:
        assert card_id in COLORLESS_RARE_POOL


def test_bandage_up_heals_and_exhausts() -> None:
    combat = _make_combat()
    combat.state.player.hp = 60
    _set_piles(combat, hand_cards=[CardInstance("BandageUp")], draw_cards=[])

    assert combat.play_card(0)

    assert combat.state.player.hp == 64
    assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["BandageUp"]


def test_dramatic_entrance_is_innate_aoe_and_exhausts() -> None:
    combat = _make_combat(monster_hp=20, monster_count=2)
    dramatic_entrance = CardInstance("DramaticEntrance")
    _set_piles(combat, hand_cards=[dramatic_entrance], draw_cards=[])

    assert dramatic_entrance.is_innate is True
    assert combat.play_card(0)

    assert [monster.hp for monster in combat.state.monsters] == [12, 12]
    assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["DramaticEntrance"]


def test_enlightenment_only_changes_current_hand_cost_for_turn_when_not_upgraded() -> None:
    combat = _make_combat()
    bash = CardInstance("Bash")
    bludgeon = CardInstance("Bludgeon")
    defend = CardInstance("Defend")
    _set_piles(combat, hand_cards=[CardInstance("Enlightenment"), bash, bludgeon, defend], draw_cards=[])

    assert combat.play_card(0)

    assert bash.cost == 2
    assert bash.cost_for_turn == 1
    assert bash.is_cost_modified_for_turn is True
    assert bludgeon.cost == 3
    assert bludgeon.cost_for_turn == 1
    assert bludgeon.is_cost_modified_for_turn is True
    assert defend.cost == 1
    assert defend.cost_for_turn == 1


def test_enlightenment_upgrade_changes_base_cost_for_current_hand_cards_too() -> None:
    combat = _make_combat()
    bash = CardInstance("Bash")
    bludgeon = CardInstance("Bludgeon")
    _set_piles(combat, hand_cards=[CardInstance("Enlightenment", upgraded=True), bash, bludgeon], draw_cards=[])

    assert combat.play_card(0)

    assert bash.cost == 1
    assert bash.cost_for_turn == 1
    assert bash.is_cost_modified is True
    assert bludgeon.cost == 1
    assert bludgeon.cost_for_turn == 1
    assert bludgeon.is_cost_modified is True


def test_impatience_draws_only_when_no_attack_remains_in_hand() -> None:
    combat = _make_combat()
    _set_piles(
        combat,
        hand_cards=[CardInstance("Impatience"), CardInstance("Defend")],
        draw_cards=[CardInstance("Strike"), CardInstance("Bash")],
    )

    assert combat.play_card(0)
    hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
    assert hand_ids[0] == "Defend"
    assert set(hand_ids[1:]) == {"Strike", "Bash"}

    combat = _make_combat()
    _set_piles(
        combat,
        hand_cards=[CardInstance("Impatience"), CardInstance("Strike")],
        draw_cards=[CardInstance("Defend"), CardInstance("Bash")],
    )

    assert combat.play_card(0)
    assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Strike"]
    assert [card.card_id for card in combat.state.card_manager.draw_pile.cards] == ["Defend", "Bash"]


def test_jax_loses_hp_and_gains_strength() -> None:
    combat = _make_combat()
    _set_piles(combat, hand_cards=[CardInstance("JAX")], draw_cards=[])

    assert combat.play_card(0)

    assert combat.state.player.hp == 77
    assert combat.state.player.strength == 2
    assert combat.state.player.get_power_amount("Strength") == 2


def test_mind_blast_tracks_draw_pile_size_and_upgrade_cost() -> None:
    combat = _make_combat(monster_hp=50)
    mind_blast = CardInstance("MindBlast", upgraded=True)
    _set_piles(
        combat,
        hand_cards=[mind_blast],
        draw_cards=[CardInstance("Strike"), CardInstance("Defend"), CardInstance("Bash"), CardInstance("PommelStrike")],
    )

    assert mind_blast.cost == 1
    mind_blast.apply_powers(combat.state)
    assert mind_blast.damage == 4

    extra_card = CardInstance("Defend")
    extra_card._combat_state = combat.state
    combat.state.card_manager.draw_pile.add(extra_card)
    mind_blast.apply_powers(combat.state)
    mind_blast.calculate_card_damage(combat.state, combat.state.monsters[0])
    assert mind_blast.damage == 5

    assert combat.play_card(0, 0)
    assert combat.state.monsters[0].hp == 45


def test_violence_randomly_moves_attack_cards_from_draw_pile_and_overflows_to_discard() -> None:
    combat = _make_combat()
    filler_hand = [CardInstance("Defend") for _ in range(9)]
    _set_piles(
        combat,
        hand_cards=[CardInstance("Violence")] + filler_hand,
        draw_cards=[CardInstance("Strike"), CardInstance("Defend"), CardInstance("Bash"), CardInstance("SwiftStrike")],
    )

    assert combat.play_card(0)

    hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
    discard_ids = [card.card_id for card in combat.state.card_manager.discard_pile.cards]
    draw_ids = [card.card_id for card in combat.state.card_manager.draw_pile.cards]

    hand_attack_ids = [card_id for card_id in hand_ids if ALL_CARD_DEFS[card_id].card_type == CardType.ATTACK]
    discard_attack_ids = [
        card_id
        for card_id in discard_ids
        if card_id != "Violence" and ALL_CARD_DEFS[card_id].card_type == CardType.ATTACK
    ]

    assert len(hand_attack_ids) == 1
    assert len(discard_attack_ids) == 2
    assert draw_ids == ["Defend"]


def test_jack_of_all_trades_only_generates_implemented_runtime_colorless_cards() -> None:
    combat = _make_combat()
    _set_piles(combat, hand_cards=[CardInstance("JackOfAllTrades", upgraded=True)], draw_cards=[])

    assert combat.play_card(0)

    generated_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
    allowed_ids = {
        card_id
        for card_id, card_def in COLORLESS_ALL_DEFS.items()
        if card_def.rarity in {CardRarity.COMMON, CardRarity.UNCOMMON, CardRarity.RARE}
        and card_def.card_type in {CardType.ATTACK, CardType.SKILL, CardType.POWER}
        and not getattr(card_def, "is_unplayable", False)
        and card_id != "BandageUp"
    }

    assert len(generated_ids) == 2
    assert set(generated_ids).issubset(allowed_ids)


def test_chrysalis_only_generates_implemented_skill_cards_with_zeroed_positive_costs() -> None:
    combat = _make_combat()
    _set_piles(combat, hand_cards=[CardInstance("Chrysalis")], draw_cards=[])

    assert combat.play_card(0)

    generated_cards = combat.state.card_manager.draw_pile.cards
    generated_ids = {card.card_id for card in generated_cards}

    assert len(generated_cards) == 3
    assert all(card.card_type == CardType.SKILL for card in generated_cards)
    assert all(card.card_id != "Chrysalis" for card in generated_cards)
    assert all(card.cost in {0, -1} for card in generated_cards)
    assert generated_ids.isdisjoint({"Discovery", "Forethought", "Purity", "SecretTechnique", "ThinkingAhead"})


def test_metamorphosis_only_generates_implemented_attack_cards_with_zeroed_positive_costs() -> None:
    combat = _make_combat()
    _set_piles(combat, hand_cards=[CardInstance("Metamorphosis")], draw_cards=[])

    assert combat.play_card(0)

    generated_cards = combat.state.card_manager.draw_pile.cards
    generated_ids = {card.card_id for card in generated_cards}

    assert len(generated_cards) == 3
    assert all(card.card_type == CardType.ATTACK for card in generated_cards)
    assert all(card.cost in {0, -1} for card in generated_cards)
    assert generated_ids.isdisjoint({"RitualDagger"})
