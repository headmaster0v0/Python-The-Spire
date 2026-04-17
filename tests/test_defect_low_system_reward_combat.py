from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 40, attack_damage: int = 0, attack_intent: bool = True):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage
        self.attack_intent = attack_intent

    def get_move(self, roll: int) -> None:
        if self.attack_intent:
            self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))
        else:
            self.set_move(MonsterMove(2, MonsterIntent.BUFF, base_damage=-1, name="Buff"))


def _make_combat(
    *,
    monster_hps: list[int] | None = None,
    energy: int = 3,
    attack_damage: int = 0,
    attack_intent: bool = True,
) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyMonster(f"Dummy{index}", hp=hp, attack_damage=attack_damage, attack_intent=attack_intent)
        for index, hp in enumerate(monster_hps or [40])
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=75,
        player_max_hp=75,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["BallLightning", "ColdSnap", "Coolheaded", "GoForTheEyes", "BeamCell", "SweepingBeam", "Defragment", "CoreSurge"],
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


class TestDefectLowSystemRewardCombat:
    def test_ball_lightning_deals_damage_and_channels_lightning(self):
        combat = _make_combat(energy=1)
        _set_piles(combat, hand_cards=[CardInstance("BallLightning")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 33
        assert len(combat.state.player.orbs) == 1
        assert combat.state.player.orbs.channels[0].orb_id == "Lightning"

    def test_cold_snap_deals_damage_and_channels_frost(self):
        combat = _make_combat(energy=1)
        _set_piles(combat, hand_cards=[CardInstance("ColdSnap")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 34
        assert len(combat.state.player.orbs) == 1
        assert combat.state.player.orbs.channels[0].orb_id == "Frost"

    def test_coolheaded_channels_frost_and_draws_one_or_two(self):
        combat = _make_combat(energy=1)
        _set_piles(combat, hand_cards=[CardInstance("Coolheaded")], draw_cards=[CardInstance("Strike_B"), CardInstance("Defend_B")])

        assert combat.play_card(0)

        assert len(combat.state.player.orbs) == 1
        assert combat.state.player.orbs.channels[0].orb_id == "Frost"
        assert len(combat.state.card_manager.hand.cards) == 1

        upgraded = _make_combat(energy=1)
        _set_piles(upgraded, hand_cards=[CardInstance("Coolheaded", upgraded=True)], draw_cards=[CardInstance("Strike_B"), CardInstance("Defend_B")])
        assert upgraded.play_card(0)
        assert len(upgraded.state.card_manager.hand.cards) == 2

    def test_go_for_the_eyes_only_applies_weak_if_target_intends_to_attack(self):
        combat = _make_combat(energy=1, attack_intent=True)
        _set_piles(combat, hand_cards=[CardInstance("GoForTheEyes")], draw_cards=[])

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].hp == 37
        assert combat.state.monsters[0].get_power_amount("Weak") == 1

        non_attack = _make_combat(energy=1, attack_intent=False)
        _set_piles(non_attack, hand_cards=[CardInstance("GoForTheEyes")], draw_cards=[])
        assert non_attack.play_card(0, 0)
        assert non_attack.state.monsters[0].get_power_amount("Weak") == 0

    def test_beam_cell_applies_vulnerable(self):
        combat = _make_combat(energy=1)
        _set_piles(combat, hand_cards=[CardInstance("BeamCell")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 37
        assert combat.state.monsters[0].get_power_amount("Vulnerable") == 1

    def test_sweeping_beam_deals_all_enemy_damage_and_draws(self):
        combat = _make_combat(monster_hps=[30, 30], energy=1)
        _set_piles(combat, hand_cards=[CardInstance("SweepingBeam")], draw_cards=[CardInstance("Strike_B")])

        assert combat.play_card(0)

        assert [monster.hp for monster in combat.state.monsters] == [24, 24]
        assert len(combat.state.card_manager.hand.cards) == 1

    def test_defragment_applies_focus_and_focus_improves_orb_values(self):
        combat = _make_combat(energy=2, attack_damage=0)
        _set_piles(combat, hand_cards=[CardInstance("Defragment"), CardInstance("Zap")], draw_cards=[])

        assert combat.play_card(0)
        assert combat.state.player.focus == 1
        assert combat.state.player.get_power_amount("Focus") == 1

        assert combat.play_card(0)
        combat.end_player_turn()

        assert combat.state.monsters[0].hp == 36

    def test_core_surge_deals_damage_and_applies_artifact(self):
        combat = _make_combat(energy=1)
        _set_piles(combat, hand_cards=[CardInstance("CoreSurge")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].hp == 29
        assert combat.state.player.get_power_amount("Artifact") == 1
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["CoreSurge"]
