from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.run.run_engine import RunEngine


SEED_LONG = 4452322743548530140


class DummyMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 40, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, deck: list[str] | None = None, energy: int = 3, attack_damage: int = 0) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [DummyMonster("Dummy0", hp=40, attack_damage=attack_damage)]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=75,
        player_max_hp=75,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=deck or ["Storm", "Heatsinks", "MachineLearning", "SelfRepair", "Reboot", "Loop"],
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


def _set_piles(
    combat: CombatEngine,
    *,
    hand_cards: list[CardInstance] | None = None,
    draw_cards: list[CardInstance] | None = None,
    discard_cards: list[CardInstance] | None = None,
) -> None:
    cm = combat.state.card_manager
    cm.hand.cards = _bind_cards(combat, hand_cards or [])
    cm.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    cm.discard_pile.cards = _bind_cards(combat, discard_cards or [])
    cm.exhaust_pile.cards = []


class TestDefectPersistentPowerRebootCombat:
    def test_storm_does_not_self_trigger_but_triggers_on_later_power(self):
        combat = _make_combat(energy=2)
        _set_piles(combat, hand_cards=[CardInstance("Storm"), CardInstance("Loop")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Storm") == 1
        assert len(combat.state.player.orbs.channels) == 0

        assert combat.play_card(0)
        assert len(combat.state.player.orbs.channels) == 1
        assert combat.state.player.orbs.channels[0].orb_id == "Lightning"

    def test_heatsinks_does_not_self_trigger_and_draws_on_later_power(self):
        combat = _make_combat(energy=2)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Heatsinks"), CardInstance("Loop")],
            draw_cards=[CardInstance("Strike_B"), CardInstance("Defend_B")],
        )

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Heatsinks") == 1
        assert combat.state.card_manager.hand.cards[0].card_id == "Loop"

        assert combat.play_card(0)
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Defend_B"]

        upgraded = _make_combat(energy=2)
        _set_piles(
            upgraded,
            hand_cards=[CardInstance("Heatsinks", upgraded=True), CardInstance("Loop")],
            draw_cards=[CardInstance("Strike_B"), CardInstance("Defend_B"), CardInstance("Zap")],
        )
        assert upgraded.play_card(0)
        assert upgraded.play_card(0)
        assert [card.card_id for card in upgraded.state.card_manager.hand.cards] == ["Zap", "Defend_B"]

    def test_machine_learning_draws_post_draw_and_plus_is_innate(self):
        combat = _make_combat(deck=["Strike_B", "Strike_B", "Strike_B", "Strike_B", "Strike_B", "MachineLearning"], energy=1, attack_damage=0)
        _set_piles(
            combat,
            hand_cards=[CardInstance("MachineLearning")],
            draw_cards=[CardInstance("Strike_B") for _ in range(6)],
        )

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("MachineLearning") == 1

        combat.end_player_turn()
        assert len(combat.state.card_manager.hand.cards) == 6

        assert CardInstance("MachineLearning", upgraded=True).is_innate is True

    def test_self_repair_heals_on_victory(self):
        engine = RunEngine.create("SELFREPAIRRUN", ascension=0, character_class="DEFECT")
        engine.start_combat_with_monsters(["Cultist"])
        combat = engine.state.combat
        assert combat is not None
        combat.state.player.hp = 50
        combat.state.player.max_hp = 75
        _set_piles(
            combat,
            hand_cards=[CardInstance("SelfRepair"), CardInstance("Strike_B")],
            draw_cards=[],
        )
        combat.state.monsters[0].hp = 6
        combat.state.monsters[0].max_hp = 6

        assert combat.play_card(0)
        assert combat.play_card(0, 0)
        assert combat.player_won() is True

        engine.end_combat()
        assert engine.state.player_hp == 57

        upgraded = _make_combat()
        upgraded.state.player.hp = 40
        upgraded.state.player.max_hp = 75
        _set_piles(upgraded, hand_cards=[CardInstance("SelfRepair", upgraded=True)], draw_cards=[])
        assert upgraded.play_card(0)
        assert upgraded.trigger_victory_effects() == 10

    def test_reboot_shuffles_hand_and_discard_into_draw_then_draws_and_respects_no_draw(self):
        combat = _make_combat(energy=0)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Reboot"), CardInstance("Strike_B"), CardInstance("Defend_B")],
            draw_cards=[CardInstance("Zap")],
            discard_cards=[CardInstance("Loop"), CardInstance("BallLightning")],
        )

        assert combat.play_card(0)

        assert len(combat.state.card_manager.hand.cards) == 4
        assert combat.state.card_manager.get_discard_pile_size() == 0
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["Reboot"]

        no_draw = _make_combat(energy=0)
        no_draw.state.player.add_power(__import__("sts_py.engine.combat.powers", fromlist=["create_power"]).create_power("No Draw", 1, "player"))
        _set_piles(
            no_draw,
            hand_cards=[CardInstance("Reboot"), CardInstance("Strike_B")],
            draw_cards=[CardInstance("Zap")],
            discard_cards=[CardInstance("Loop")],
        )
        assert no_draw.play_card(0)
        assert no_draw.state.card_manager.hand.cards == []
        assert no_draw.state.card_manager.get_discard_pile_size() == 0
        assert len(no_draw.state.card_manager.draw_pile.cards) == 3
