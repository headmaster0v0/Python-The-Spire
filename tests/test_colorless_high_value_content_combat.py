from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


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


def _hand_index(combat: CombatEngine, card_id: str) -> int:
    for index, card in enumerate(combat.state.card_manager.hand.cards):
        if card.card_id == card_id:
            return index
    raise AssertionError(f"{card_id} not found in hand")


def test_colorless_aliases_resolve_to_runtime_ids() -> None:
    assert CardInstance("Master of Strategy").card_id == "MasterOfStrategy"
    assert CardInstance("Deep Breath").card_id == "DeepBreath"
    assert CardInstance("Flash of Steel").card_id == "FlashOfSteel"
    assert CardInstance("Ghostly").card_id == "Apparition"


def test_madness_sets_only_other_positive_cost_card_to_zero() -> None:
    combat = _make_combat()
    bash = CardInstance("Bash")
    _set_piles(combat, hand_cards=[CardInstance("Madness"), bash, CardInstance("Miracle")], draw_cards=[])

    assert combat.play_card(0)

    assert bash.cost == 0
    assert bash.cost_for_turn == 0
    assert bash.is_cost_modified is True


def test_apotheosis_upgrades_all_other_cards_across_piles() -> None:
    combat = _make_combat()
    strike = CardInstance("Strike")
    defend = CardInstance("Defend")
    bash = CardInstance("Bash")
    good_instincts = CardInstance("GoodInstincts")
    apotheosis = CardInstance("Apotheosis")
    _set_piles(
        combat,
        hand_cards=[apotheosis, strike],
        draw_cards=[defend],
        discard_cards=[bash],
        exhaust_cards=[good_instincts],
    )

    assert combat.play_card(0)

    assert strike.upgraded is True
    assert defend.upgraded is True
    assert bash.upgraded is True
    assert good_instincts.upgraded is True
    assert apotheosis.upgraded is False


def test_deep_breath_shuffles_discard_into_draw_then_draws() -> None:
    combat = _make_combat()
    _set_piles(
        combat,
        hand_cards=[CardInstance("DeepBreath")],
        draw_cards=[],
        discard_cards=[CardInstance("Strike"), CardInstance("Defend")],
    )

    assert combat.play_card(0)

    hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
    draw_ids = [card.card_id for card in combat.state.card_manager.draw_pile.cards]
    discard_ids = [card.card_id for card in combat.state.card_manager.discard_pile.cards]

    assert hand_ids[0] in {"Strike", "Defend"}
    assert draw_ids[0] in {"Strike", "Defend"}
    assert set(hand_ids + draw_ids) == {"Strike", "Defend"}
    assert discard_ids == ["DeepBreath"]


def test_hand_of_greed_grants_bonus_gold_on_kill() -> None:
    combat = _make_combat(monster_hp=15)
    _set_piles(combat, hand_cards=[CardInstance("HandOfGreed")], draw_cards=[])

    assert combat.play_card(0, 0)

    assert combat.state.monsters[0].is_dead() is True
    assert combat.state.pending_bonus_gold == 20


def test_blind_upgrade_becomes_aoe_weak() -> None:
    combat = _make_combat(monster_count=2)
    _set_piles(combat, hand_cards=[CardInstance("Blind", upgraded=True)], draw_cards=[])

    assert combat.play_card(0)

    assert [monster.get_power_amount("Weak") for monster in combat.state.monsters] == [2, 2]


def test_dark_shackles_consumes_artifact_before_strength_loss() -> None:
    combat = _make_combat()
    combat.state.monsters[0].add_power(create_power("Artifact", 1, combat.state.monsters[0].id))
    _set_piles(combat, hand_cards=[CardInstance("DarkShackles")], draw_cards=[])

    assert combat.play_card(0, 0)

    assert combat.state.monsters[0].get_power_amount("Artifact") == 0
    assert combat.state.monsters[0].strength == 0
    assert combat.state.monsters[0].get_power_amount("Lose Strength") == 0


def test_panic_button_blocks_now_and_prevents_future_block_gain() -> None:
    combat = _make_combat(attack_damage=0)
    _set_piles(combat, hand_cards=[CardInstance("PanicButton"), CardInstance("Defend")], draw_cards=[])

    assert combat.play_card(0)
    assert combat.state.player.block == 30
    assert combat.play_card(0)
    assert combat.state.player.block == 30

    combat.end_player_turn()
    _set_piles(combat, hand_cards=[CardInstance("Defend")], draw_cards=[])

    assert combat.play_card(0)
    assert combat.state.player.block == 0
    assert combat.state.player.get_power_amount("NoBlock") == 1


def test_simple_colorless_cards_resolve_real_runtime_effects() -> None:
    combat = _make_combat(monster_hp=40)
    _set_piles(
        combat,
        hand_cards=[
            CardInstance("Finesse"),
            CardInstance("FlashOfSteel"),
            CardInstance("GoodInstincts"),
            CardInstance("Panacea"),
            CardInstance("Trip"),
            CardInstance("SwiftStrike"),
            CardInstance("Bite"),
            CardInstance("Apparition"),
        ],
        draw_cards=[CardInstance("Strike"), CardInstance("Defend")],
    )

    assert combat.play_card(_hand_index(combat, "Finesse"))
    assert combat.state.player.block == 2
    assert len(combat.state.card_manager.hand.cards) == 8

    assert combat.play_card(_hand_index(combat, "FlashOfSteel"), 0)
    assert combat.state.monsters[0].hp == 37

    assert combat.play_card(_hand_index(combat, "GoodInstincts"))
    assert combat.state.player.block == 8

    assert combat.play_card(_hand_index(combat, "Panacea"))
    assert combat.state.player.get_power_amount("Artifact") == 1

    assert combat.play_card(_hand_index(combat, "Trip"), 0)
    assert combat.state.monsters[0].get_power_amount("Vulnerable") == 2

    assert combat.play_card(_hand_index(combat, "SwiftStrike"), 0)
    assert combat.state.monsters[0].hp == 27

    combat.state.player.hp = 60
    assert combat.play_card(_hand_index(combat, "Bite"), 0)
    assert combat.state.player.hp == 62

    assert combat.play_card(_hand_index(combat, "Apparition"))
    assert combat.state.player.get_power_amount("Intangible") == 1
