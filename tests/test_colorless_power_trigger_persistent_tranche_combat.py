from __future__ import annotations

from types import SimpleNamespace

from sts_py.engine.combat.card_effects import (
    ApplyPowerEffect,
    _apply_poison_to_monster,
    _implemented_colorless_combat_card_ids,
)
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import PowerType, create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import ALL_CARD_DEFS
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.run.run_engine import RunEngine
from sts_py.engine.run.shop import COLORLESS_RARE_POOL


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


class DummyMinionMonster(DummyAttackMonster):
    def __init__(self, monster_id: str, hp: int = 10, attack_damage: int = 0):
        super().__init__(monster_id, hp=hp, attack_damage=attack_damage)
        self.is_minion = True


def _make_combat(
    *,
    monster_hp: int = 80,
    attack_damage: int = 0,
    monster_count: int = 1,
    energy: int = 3,
    relics: list[str] | None = None,
    monsters: list[MonsterBase] | None = None,
) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    encounter_monsters = monsters or [
        DummyAttackMonster(f"DummyAttack{index}", hp=monster_hp, attack_damage=attack_damage)
        for index in range(monster_count)
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=encounter_monsters,
        player_hp=80,
        player_max_hp=80,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Strike", "Strike", "Strike", "Defend", "Defend", "Defend", "Defend", "Bash", "PommelStrike"],
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
    exhaust_cards: list[CardInstance] | None = None,
) -> None:
    card_manager = combat.state.card_manager
    card_manager.hand.cards = _bind_cards(combat, hand_cards or [])
    card_manager.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    card_manager.discard_pile.cards = _bind_cards(combat, discard_cards or [])
    card_manager.exhaust_pile.cards = _bind_cards(combat, exhaust_cards or [])


def _bomb_amounts(combat: CombatEngine) -> list[int]:
    return [power.amount for power in combat.state.player.powers.powers if power.id == "TheBomb"]


def test_phase252_surface_adds_runtime_cards_and_keeps_ritual_dagger_out_of_random_colorless_pool() -> None:
    assert CardInstance("Ritual Dagger").card_id == "RitualDagger"
    assert CardInstance("The Bomb").card_id == "TheBomb"
    assert CardInstance("Sadistic Nature").card_id == "SadisticNature"

    for card_id in {"Magnetism", "Mayhem", "Panache", "SadisticNature", "TheBomb", "Transmutation"}:
        assert card_id in COLORLESS_RARE_POOL
        assert card_id in ALL_CARD_DEFS

    colorless_pool = set(_implemented_colorless_combat_card_ids())
    assert "RitualDagger" not in colorless_pool
    assert "BandageUp" not in colorless_pool


def test_magnetism_generates_legal_non_healing_cards_and_overflows_to_discard_when_hand_is_full() -> None:
    combat = _make_combat()
    existing_hand_size = len(combat.state.card_manager.hand.cards)
    combat.state.player.add_power(create_power("Magnetism", 1, "player"))

    combat.state.player.powers.at_start_of_turn(combat.state.player)

    assert len(combat.state.card_manager.hand.cards) == existing_hand_size + 1
    generated_id = combat.state.card_manager.hand.cards[-1].card_id
    assert generated_id in set(_implemented_colorless_combat_card_ids())
    assert generated_id != "BandageUp"

    combat = _make_combat()
    combat.state.player.add_power(create_power("Magnetism", 1, "player"))
    _set_piles(combat, hand_cards=[CardInstance("Defend") for _ in range(10)], draw_cards=[], discard_cards=[])

    combat.state.player.powers.at_start_of_turn(combat.state.player)

    assert len(combat.state.card_manager.hand.cards) == 10
    assert len(combat.state.card_manager.discard_pile.cards) == 1
    assert combat.state.card_manager.discard_pile.cards[0].card_id in set(_implemented_colorless_combat_card_ids())


def test_mayhem_shuffles_discard_and_autoplays_top_card_without_opening_choice() -> None:
    combat = _make_combat(monster_hp=20, energy=3)
    combat.state.player.add_power(create_power("Mayhem", 1, "player"))
    _set_piles(combat, hand_cards=[], draw_cards=[], discard_cards=[CardInstance("Strike")])

    combat.state.player.powers.at_start_of_turn(combat.state.player)

    assert combat.state.monsters[0].hp == 14
    assert combat.state.player.energy == 3
    assert combat.state.pending_combat_choice is None
    assert combat.state.card_manager.draw_pile.cards == []


def test_panache_counts_cards_resets_each_turn_and_stacks_damage() -> None:
    combat = _make_combat(monster_hp=120, energy=10)
    combat.state.player.add_power(create_power("Panache", 10, "player"))
    combat.state.player.add_power(create_power("Panache", 4, "player"))
    panache = combat.state.player.powers.get_power("Panache")
    assert panache is not None

    _set_piles(combat, hand_cards=[CardInstance("Strike") for _ in range(5)], draw_cards=[])

    for _ in range(4):
        assert combat.play_card(0, 0)

    assert combat.state.monsters[0].hp == 96
    assert panache.amount == 14
    assert panache.cards_until_trigger == 1

    assert combat.play_card(0, 0)

    assert combat.state.monsters[0].hp == 76
    assert panache.cards_until_trigger == 5

    panache.cards_until_trigger = 2
    combat.state.player.powers.at_start_of_turn(combat.state.player)
    assert panache.cards_until_trigger == 5


def test_sadistic_nature_triggers_for_poison_weak_vulnerable_and_lockon() -> None:
    combat = _make_combat(monster_hp=100)
    player = combat.state.player
    monster = combat.state.monsters[0]
    player.add_power(create_power("Sadistic", 5, "player"))

    _apply_poison_to_monster(player, monster, 2)
    assert monster.hp == 95
    assert monster.get_power_amount("Poison") == 2

    for power_type in ("Weak", "Vulnerable", "Lockon"):
        starting_hp = monster.hp
        ApplyPowerEffect(power_type=power_type, amount=1, target_type="monster", target_idx=0).execute(
            combat.state,
            CardInstance("Strike"),
            player,
            monster,
        )
        assert monster.hp == starting_hp - 5
        assert monster.get_power_amount(power_type) >= 1


def test_sadistic_nature_does_not_trigger_through_artifact_or_shackled() -> None:
    combat = _make_combat(monster_hp=100)
    player = combat.state.player
    monster = combat.state.monsters[0]
    player.add_power(create_power("Sadistic", 5, "player"))
    monster.add_power(create_power("Artifact", 1, monster.id))

    ApplyPowerEffect(power_type="Weak", amount=1, target_type="monster", target_idx=0).execute(
        combat.state,
        CardInstance("Strike"),
        player,
        monster,
    )
    assert monster.hp == 100
    assert monster.get_power_amount("Artifact") == 0

    player.powers.on_player_apply_power_to_enemy(
        player,
        monster,
        SimpleNamespace(id="Shackled", power_type=PowerType.DEBUFF),
    )
    assert monster.hp == 100


def test_the_bomb_instances_count_down_independently() -> None:
    combat = _make_combat(monster_hp=200, energy=10)
    _set_piles(combat, hand_cards=[CardInstance("TheBomb")], draw_cards=[])

    assert combat.play_card(0)
    assert _bomb_amounts(combat) == [3]

    combat.end_player_turn()
    assert _bomb_amounts(combat) == [2]

    _set_piles(combat, hand_cards=[CardInstance("TheBomb")], draw_cards=[])
    assert combat.play_card(0)
    assert sorted(_bomb_amounts(combat)) == [2, 3]

    combat.end_player_turn()
    assert sorted(_bomb_amounts(combat)) == [1, 2]

    combat.end_player_turn()
    assert _bomb_amounts(combat) == [1]
    assert combat.state.monsters[0].hp == 160

    combat.end_player_turn()
    assert _bomb_amounts(combat) == []
    assert combat.state.monsters[0].hp == 120


def test_ritual_dagger_kill_updates_battle_instance_and_master_deck_string() -> None:
    combat = _make_combat(monster_hp=10, energy=3)
    run_engine = RunEngine.create("PHASE252RITUAL", ascension=0)
    run_engine.state.deck = ["RitualDagger#15"]
    combat.state.run_engine = run_engine

    ritual_dagger = CardInstance("RitualDagger#15")
    ritual_dagger._master_deck_index = 0
    _set_piles(combat, hand_cards=[ritual_dagger], draw_cards=[])

    assert combat.play_card(0, 0)

    exhausted = combat.state.card_manager.exhaust_pile.cards[0]
    assert exhausted.card_id == "RitualDagger"
    assert exhausted.misc == 18
    assert exhausted.base_damage == 18
    assert run_engine.state.deck == ["RitualDagger#18"]


def test_ritual_dagger_does_not_grow_without_kill_or_when_killing_a_minion() -> None:
    combat = _make_combat(monster_hp=40, energy=3)
    _set_piles(combat, hand_cards=[CardInstance("RitualDagger#15")], draw_cards=[])

    assert combat.play_card(0, 0)
    assert combat.state.card_manager.exhaust_pile.cards[0].misc == 15

    minion_combat = _make_combat(monsters=[DummyMinionMonster("DummyMinion", hp=10)], energy=3)
    _set_piles(minion_combat, hand_cards=[CardInstance("RitualDagger#15")], draw_cards=[])

    assert minion_combat.play_card(0, 0)
    assert minion_combat.state.card_manager.exhaust_pile.cards[0].misc == 15


def test_transmutation_uses_chemical_x_and_generates_upgraded_zero_cost_runtime_colorless_cards() -> None:
    combat = _make_combat(relics=["ChemicalX"], energy=3)
    _set_piles(combat, hand_cards=[CardInstance("Transmutation", upgraded=True)], draw_cards=[])

    assert combat.play_card(0)

    generated_cards = combat.state.card_manager.hand.cards
    legal_pool = set(_implemented_colorless_combat_card_ids())

    assert combat.state.player.energy == 0
    assert len(generated_cards) == 5
    assert all(card.card_id in legal_pool for card in generated_cards)
    assert all(card.card_id != "BandageUp" for card in generated_cards)
    assert all(card.upgraded is True for card in generated_cards)
    assert all(card.cost_for_turn == 0 for card in generated_cards)
