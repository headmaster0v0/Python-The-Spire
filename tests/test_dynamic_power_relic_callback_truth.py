from __future__ import annotations

from types import SimpleNamespace

from sts_py.engine.combat.card_effects import ApplyPowerEffect, _apply_poison_to_monster
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.potion_effects import use_potion
from sts_py.engine.combat.powers import PowerType, create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.potions import create_potion
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 60):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=0, name="Attack"))


def _make_combat(
    *,
    monster_hps: list[int] | None = None,
    energy: int = 3,
    relics: list[str] | None = None,
) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [DummyAttackMonster(f"Dummy{index}", hp=hp) for index, hp in enumerate(monster_hps or [60])]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=70,
        player_max_hp=70,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Prepared", "ToolsOfTheTrade", "AfterImage", "Havoc"],
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


def test_prepared_plus_discarding_reflex_and_tactician_uses_shared_discard_and_relic_callbacks() -> None:
    combat = _make_combat(monster_hps=[50], energy=3, relics=["Tingsha", "ToughBandages"])
    _set_piles(
        combat,
        hand_cards=[CardInstance("Prepared", upgraded=True), CardInstance("Reflex"), CardInstance("Tactician")],
        draw_cards=[CardInstance("Strike"), CardInstance("Defend"), CardInstance("Slice"), CardInstance("Backflip")],
    )

    assert combat.play_card(0)

    assert combat.state.monsters[0].hp == 44
    assert combat.state.player.block == 6
    assert combat.state.player.energy == 4
    assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Backflip", "Slice", "Defend", "Strike"]
    assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Reflex", "Tactician", "Prepared"]


def test_tools_of_the_trade_post_draw_discard_uses_same_reflex_and_relic_hook_path() -> None:
    combat = _make_combat(monster_hps=[50], energy=3, relics=["Tingsha", "ToughBandages"])
    _set_piles(combat, hand_cards=[CardInstance("ToolsOfTheTrade")], draw_cards=[])

    assert combat.play_card(0)
    assert combat.state.player.get_power_amount("Tools Of The Trade") == 1

    _set_piles(
        combat,
        hand_cards=[CardInstance("Reflex"), CardInstance("Defend")],
        draw_cards=[CardInstance("Strike"), CardInstance("Neutralize"), CardInstance("Backflip")],
        discard_cards=combat.state.card_manager.discard_pile.cards,
    )

    combat.state.player.powers.at_start_of_turn_post_draw(combat.state.player)

    assert combat.state.monsters[0].hp == 47
    assert combat.state.player.block == 3
    assert combat.state.player.energy == 2
    assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Defend", "Backflip", "Neutralize", "Strike"]
    assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["ToolsOfTheTrade", "Reflex"]


def test_after_image_triggers_on_generated_cards_and_havoc_autoplay_without_leaving_pending_choice() -> None:
    combat = _make_combat(monster_hps=[60], energy=4)
    _set_piles(
        combat,
        hand_cards=[CardInstance("AfterImage"), CardInstance("BladeDance"), CardInstance("Havoc")],
        draw_cards=[CardInstance("Strike")],
    )

    assert combat.play_card(0)
    assert combat.play_card(0)

    shiv_index = next(index for index, card in enumerate(combat.state.card_manager.hand.cards) if card.card_id == "Shiv")
    assert combat.play_card(shiv_index, 0)

    havoc_index = next(index for index, card in enumerate(combat.state.card_manager.hand.cards) if card.card_id == "Havoc")
    assert combat.play_card(havoc_index)

    assert combat.state.player.block == 5
    assert combat.state.monsters[0].hp == 50
    assert combat.state.pending_combat_choice is None


def test_sadistic_nature_only_triggers_for_successful_enemy_debuff_application() -> None:
    combat = _make_combat(monster_hps=[100], energy=3)
    player = combat.state.player
    monster = combat.state.monsters[0]
    player.add_power(create_power("Sadistic", 5, "player"))

    _apply_poison_to_monster(player, monster, 2)
    assert monster.hp == 95
    assert monster.get_power_amount("Poison") == 2

    monster.add_power(create_power("Artifact", 1, monster.id))
    ApplyPowerEffect(power_type="Weak", amount=1, target_type="monster", target_idx=0).execute(
        combat.state,
        CardInstance("Strike"),
        player,
        monster,
    )
    assert monster.hp == 95
    assert monster.get_power_amount("Artifact") == 0

    player.powers.on_player_apply_power_to_enemy(
        player,
        monster,
        SimpleNamespace(id="Shackled", power_type=PowerType.DEBUFF),
    )
    assert monster.hp == 95


def test_distilled_chaos_reuses_existing_autoplay_target_resolution() -> None:
    combat = _make_combat(monster_hps=[40], energy=3)
    potion = create_potion("DistilledChaos")
    assert potion is not None

    _set_piles(
        combat,
        hand_cards=[],
        draw_cards=[CardInstance("Defend"), CardInstance("Strike")],
        discard_cards=[],
    )

    use_potion(potion, combat.state)

    assert combat.state.monsters[0].hp == 34
    assert combat.state.player.energy == 3
    assert combat.state.pending_combat_choice is None
