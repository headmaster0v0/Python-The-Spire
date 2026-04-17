from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.orbs import FrostOrb
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 60, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _make_combat(*, monster_hps: list[int] | None = None, energy: int = 3, attack_damage: int = 0) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyMonster(f"Dummy{index}", hp=hp, attack_damage=attack_damage)
        for index, hp in enumerate(monster_hps or [60])
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=75,
        player_max_hp=75,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=[
            "AllForOne",
            "Amplify",
            "Blizzard",
            "EchoForm",
            "StaticDischarge",
            "Defragment",
            "Streamline",
            "Strike_B",
            "BootSequence",
            "Claw",
        ],
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


def _start_fresh_player_turn(combat: CombatEngine, *, energy: int) -> None:
    combat.state.cards_played_this_turn.clear()
    combat.state.player.energy = energy
    combat.state.card_manager.set_energy(energy)
    combat.state.player.powers.at_start_of_turn(combat.state.player)


class TestDefectFinalCompletionCombat:
    def test_all_for_one_recovers_zero_base_cost_and_free_to_play_discards_in_order(self):
        combat = _make_combat(energy=2, monster_hps=[50])
        cost_zero_for_turn_only = CardInstance("Bullseye")
        cost_zero_for_turn_only.cost_for_turn = 0
        free_once = CardInstance("DoomAndGloom")
        free_once.free_to_play_once = True
        _set_piles(
            combat,
            hand_cards=[CardInstance("AllForOne")],
            draw_cards=[],
            discard_cards=[cost_zero_for_turn_only, CardInstance("Claw"), free_once, CardInstance("BootSequence")],
        )

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 40
        assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Claw", "DoomAndGloom", "BootSequence"]
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["Bullseye", "AllForOne"]

    def test_all_for_one_respects_hand_limit_while_preserving_discard_order(self):
        combat = _make_combat(energy=2, monster_hps=[50])
        free_once = CardInstance("DoomAndGloom")
        free_once.free_to_play_once = True
        filler = [CardInstance("Strike_B") for _ in range(9)]
        _set_piles(
            combat,
            hand_cards=[CardInstance("AllForOne")] + filler,
            draw_cards=[],
            discard_cards=[CardInstance("Claw"), CardInstance("BootSequence"), free_once],
        )

        assert combat.play_card(0, 0)

        assert combat.state.card_manager.get_hand_size() == 10
        assert combat.state.card_manager.hand.cards[-1].card_id == "Claw"
        assert [card.card_id for card in combat.state.card_manager.discard_pile.cards] == ["BootSequence", "DoomAndGloom", "AllForOne"]

    def test_amplify_repeats_next_power_without_recursing_on_purge_copy(self):
        combat = _make_combat(energy=4)
        _set_piles(combat, hand_cards=[CardInstance("Amplify"), CardInstance("EchoForm")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Amplify") == 1

        assert combat.play_card(0)

        assert combat.state.player.get_power_amount("EchoForm") == 2
        assert combat.state.player.get_power_amount("Amplify") == 0

    def test_amplify_plus_consumes_two_power_cards_then_expires(self):
        combat = _make_combat(energy=3)
        _set_piles(
            combat,
            hand_cards=[CardInstance("Amplify", upgraded=True), CardInstance("Defragment"), CardInstance("StaticDischarge")],
            draw_cards=[],
        )

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Amplify") == 2

        assert combat.play_card(0)
        assert combat.state.player.focus == 2
        assert combat.state.player.get_power_amount("Amplify") == 1

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("StaticDischarge") == 2
        assert combat.state.player.get_power_amount("Amplify") == 0

    def test_amplify_expires_at_end_of_round_if_unused(self):
        combat = _make_combat(energy=1, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Amplify")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("Amplify") == 1

        combat.end_player_turn()

        assert combat.state.player.get_power_amount("Amplify") == 0

    def test_blizzard_uses_frost_channeled_this_combat(self):
        empty = _make_combat(energy=1, monster_hps=[20, 20])
        _set_piles(empty, hand_cards=[CardInstance("Blizzard")], draw_cards=[])

        assert empty.play_card(0)
        assert [monster.hp for monster in empty.state.monsters] == [20, 20]

        scaled = _make_combat(energy=1, monster_hps=[20, 20])
        scaled.state.player.max_orbs = 6
        scaled.state.player.orbs.slots = 6
        for _ in range(3):
            scaled._channel_orb(FrostOrb())
        _set_piles(scaled, hand_cards=[CardInstance("Blizzard")], draw_cards=[])

        assert scaled.play_card(0)
        assert [monster.hp for monster in scaled.state.monsters] == [14, 14]

        upgraded = _make_combat(energy=1, monster_hps=[20, 20])
        upgraded.state.player.max_orbs = 6
        upgraded.state.player.orbs.slots = 6
        for _ in range(2):
            upgraded._channel_orb(FrostOrb())
        _set_piles(upgraded, hand_cards=[CardInstance("Blizzard", upgraded=True)], draw_cards=[])

        assert upgraded.play_card(0)
        assert [monster.hp for monster in upgraded.state.monsters] == [14, 14]

    def test_echo_form_duplicates_first_card_each_turn_and_resets(self):
        combat = _make_combat(energy=3, monster_hps=[40])
        _set_piles(combat, hand_cards=[CardInstance("EchoForm")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("EchoForm") == 1

        _start_fresh_player_turn(combat, energy=2)
        _set_piles(combat, hand_cards=[CardInstance("Strike_B"), CardInstance("Strike_B")], draw_cards=[])

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 28

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 22

        _start_fresh_player_turn(combat, energy=1)
        _set_piles(combat, hand_cards=[CardInstance("Strike_B")], draw_cards=[])

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 10

    def test_echo_form_repeats_same_target_and_syncs_streamline_growth(self):
        combat = _make_combat(energy=4, monster_hps=[40, 40])
        _set_piles(combat, hand_cards=[CardInstance("EchoForm")], draw_cards=[])

        assert combat.play_card(0)
        _start_fresh_player_turn(combat, energy=2)
        streamline = CardInstance("Streamline")
        _set_piles(combat, hand_cards=[streamline], draw_cards=[])

        assert combat.play_card(0, 1)

        assert [monster.hp for monster in combat.state.monsters] == [40, 10]
        stored = combat.state.card_manager.discard_pile.cards[-1]
        assert stored.card_id == "Streamline"
        assert stored.combat_cost_reduction == 2
        assert stored.cost_for_turn == 0

    def test_static_discharge_triggers_on_normal_damage_per_hit(self):
        combat = _make_combat(energy=1)
        combat.state.player.max_orbs = 6
        combat.state.player.orbs.slots = 6
        _set_piles(combat, hand_cards=[CardInstance("StaticDischarge", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.get_power_amount("StaticDischarge") == 2

        assert combat.state.player.take_damage(3) == 3
        assert assert_orb_ids(combat) == ["Lightning", "Lightning"]

        assert combat.state.player.take_damage(2) == 2
        assert assert_orb_ids(combat) == ["Lightning", "Lightning", "Lightning", "Lightning"]

    def test_static_discharge_does_not_trigger_on_blocked_thorns_or_hp_loss(self):
        combat = _make_combat(energy=1)
        combat.state.player.max_orbs = 6
        combat.state.player.orbs.slots = 6
        _set_piles(combat, hand_cards=[CardInstance("StaticDischarge")], draw_cards=[])

        assert combat.play_card(0)

        combat.state.player.block = 5
        assert combat.state.player.take_damage(3) == 0
        assert assert_orb_ids(combat) == []

        combat.state.player.block = 0
        assert combat.state.player.take_damage(3, damage_type="THORNS") == 3
        assert assert_orb_ids(combat) == []

        assert combat.state.player.lose_hp(2) == 2
        assert assert_orb_ids(combat) == []


def assert_orb_ids(combat: CombatEngine) -> list[str]:
    return [orb.orb_id for orb in combat.state.player.orbs.channels]
