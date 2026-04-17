from __future__ import annotations

from sts_py.engine.combat.card_effects import (
    ApplyPowerEffect,
    DealDamageEffect,
    DrawCardsEffect,
    GainBlockEffect,
    ScryEffect,
    get_card_effects,
)
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, hp: int = 80, attack_damage: int = 0):
        super().__init__(id="DummyAttack", name="Dummy Attack", hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hp: int = 80, attack_damage: int = 0) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monster = DummyAttackMonster(hp=monster_hp, attack_damage=attack_damage)
    return CombatEngine.create_with_monsters(
        monsters=[monster],
        player_hp=72,
        player_max_hp=72,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Strike", "Strike", "Strike", "Defend", "Defend", "Defend", "Defend", "Eruption", "Vigilance"],
        relics=[],
    )


def _bind_cards(combat: CombatEngine, cards: list[CardInstance]) -> list[CardInstance]:
    for card in cards:
        card._combat_state = combat.state
    return cards


def _set_piles(
    combat: CombatEngine,
    *,
    hand_ids: list[str] | None = None,
    draw_ids: list[str] | None = None,
    discard_cards: list[str | CardInstance] | None = None,
) -> None:
    combat.state.card_manager.hand.cards = _bind_cards(
        combat,
        [CardInstance(card_id) for card_id in (hand_ids or [])],
    )
    combat.state.card_manager.draw_pile.cards = _bind_cards(
        combat,
        [CardInstance(card_id) for card_id in (draw_ids or [])],
    )

    discard_instances: list[CardInstance] = []
    for card in discard_cards or []:
        instance = card if isinstance(card, CardInstance) else CardInstance(card)
        discard_instances.append(instance)
    combat.state.card_manager.discard_pile.cards = _bind_cards(combat, discard_instances)
    combat.state.card_manager.exhaust_pile.cards = []


class TestWatcherScryCardEffects:
    def test_third_eye_effects_block_then_scry(self):
        effects = get_card_effects(CardInstance("ThirdEye"))

        assert len(effects) == 2
        assert isinstance(effects[0], GainBlockEffect)
        assert isinstance(effects[1], ScryEffect)

    def test_just_lucky_effects_damage_block_then_scry(self):
        effects = get_card_effects(CardInstance("JustLucky"), target_idx=0)

        assert len(effects) == 3
        assert isinstance(effects[0], DealDamageEffect)
        assert isinstance(effects[1], GainBlockEffect)
        assert isinstance(effects[2], ScryEffect)

    def test_cut_through_fate_effects_damage_scry_then_draw(self):
        effects = get_card_effects(CardInstance("CutThroughFate"), target_idx=0)

        assert len(effects) == 3
        assert isinstance(effects[0], DealDamageEffect)
        assert isinstance(effects[1], ScryEffect)
        assert isinstance(effects[2], DrawCardsEffect)

    def test_foresight_effects_apply_power(self):
        effects = get_card_effects(CardInstance("Foresight"))

        assert len(effects) == 1
        assert isinstance(effects[0], ApplyPowerEffect)
        assert effects[0].power_type == "Foresight"

    def test_weave_remains_plain_attack(self):
        effects = get_card_effects(CardInstance("Weave"), target_idx=0)

        assert len(effects) == 1
        assert isinstance(effects[0], DealDamageEffect)


class TestWatcherScryHeuristics:
    def test_scry_discards_status_and_preserves_kept_order(self):
        combat = _make_combat()
        _set_piles(combat, draw_ids=["Defend", "Burn", "Strike", "Weave"])

        result = combat.state.card_manager.resolve_scry(3)

        assert [card.card_id for card in result["viewed"]] == ["Burn", "Strike", "Weave"]
        assert [card.card_id for card in result["discarded"]] == ["Burn"]
        assert [card.card_id for card in result["kept"]] == ["Strike", "Weave"]
        assert [card.card_id for card in combat.state.card_manager.draw_pile.cards] == ["Defend", "Strike", "Weave"]

    def test_scry_is_deterministic_and_keeps_weave(self):
        combat_a = _make_combat()
        combat_b = _make_combat()
        for combat in (combat_a, combat_b):
            combat.state.player.energy = 0
            combat.state.card_manager.set_energy(0)
            _set_piles(combat, draw_ids=["Defend", "Strike", "Weave", "Devotion"])

        result_a = combat_a.state.card_manager.resolve_scry(4)
        result_b = combat_b.state.card_manager.resolve_scry(4)

        assert [card.card_id for card in result_a["discarded"]] == [card.card_id for card in result_b["discarded"]]
        assert [card.card_id for card in result_a["kept"]] == [card.card_id for card in result_b["kept"]]
        assert "Weave" in [card.card_id for card in result_a["kept"]]


class TestWatcherScryCombatIntegration:
    def test_third_eye_gains_block_and_discards_bad_top_cards(self):
        combat = _make_combat()
        _set_piles(combat, hand_ids=["ThirdEye"], draw_ids=["Defend", "Burn", "Strike"])

        assert combat.play_card(0)

        assert combat.state.player.block == 7
        assert [card.card_id for card in combat.state.card_manager.draw_pile.cards] == ["Defend", "Strike"]
        assert "Burn" in [card.card_id for card in combat.state.card_manager.discard_pile.cards]

    def test_just_lucky_deals_damage_blocks_and_scry_discards_top_status(self):
        combat = _make_combat(monster_hp=20)
        _set_piles(combat, hand_ids=["JustLucky"], draw_ids=["Defend", "Strike", "Burn"])
        monster = combat.state.monsters[0]

        assert combat.play_card(0, 0)

        assert monster.hp == 17
        assert combat.state.player.block == 2
        assert [card.card_id for card in combat.state.card_manager.draw_pile.cards] == ["Defend", "Strike"]
        assert "Burn" in [card.card_id for card in combat.state.card_manager.discard_pile.cards]

    def test_cut_through_fate_scries_then_draws(self):
        combat = _make_combat(monster_hp=20)
        _set_piles(combat, hand_ids=["CutThroughFate"], draw_ids=["Defend", "Burn", "Strike"])
        monster = combat.state.monsters[0]

        assert combat.play_card(0, 0)

        hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
        assert monster.hp == 13
        assert hand_ids == ["Strike"]
        assert [card.card_id for card in combat.state.card_manager.draw_pile.cards] == ["Defend"]
        assert "Burn" in [card.card_id for card in combat.state.card_manager.discard_pile.cards]

    def test_foresight_triggers_scry_at_start_of_turn(self):
        combat = _make_combat()
        _set_piles(combat, draw_ids=["Strike", "Burn"])
        combat.state.player.add_power(create_power("Foresight", 3, "player"))

        combat.state.player.powers.at_start_of_turn(combat.state.player)

        assert [card.card_id for card in combat.state.card_manager.draw_pile.cards] == ["Strike"]
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Burn"]

    def test_foresight_shuffles_discard_into_draw_when_needed(self):
        combat = _make_combat()
        _set_piles(combat, discard_cards=["Burn"])
        combat.state.player.add_power(create_power("Foresight", 3, "player"))

        result = combat.state.player.powers.at_start_of_turn(combat.state.player)

        assert result[0]["discarded_count"] == 1
        assert combat.state.card_manager.get_draw_pile_size() == 0
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Burn"]

    def test_weave_returns_from_discard_on_scry_without_copying(self):
        combat = _make_combat()
        weave = CardInstance("Weave")
        _set_piles(combat, draw_ids=["Burn"], discard_cards=[weave])

        combat.state.card_manager.resolve_scry(1)

        assert combat.state.card_manager.hand.cards[0] is weave
        assert combat.state.card_manager.get_discard_pile_size() == 1
        assert combat.state.card_manager.discard_pile.cards[0].card_id == "Burn"
