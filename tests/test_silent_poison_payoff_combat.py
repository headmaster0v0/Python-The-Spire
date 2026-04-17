from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 40):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=0, name="Attack"))


def _make_combat(*, monster_hps: list[int] | None = None, relics: list[str] | None = None) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [DummyAttackMonster(f"Dummy{idx}", hp=hp) for idx, hp in enumerate(monster_hps or [40])]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=70,
        player_max_hp=70,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Catalyst", "CripplingCloud", "CorpseExplosion", "DeadlyPoison"],
        relics=relics or [],
    )
    combat.state.player.max_energy = 3
    combat.state.player.energy = 3
    combat.state.card_manager.set_max_energy(3)
    combat.state.card_manager.set_energy(3)
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


class TestSilentPoisonPayoffCombatIntegration:
    def test_catalyst_doubles_existing_poison(self):
        combat = _make_combat()
        target = combat.state.monsters[0]
        target.add_power(__import__("sts_py.engine.combat.powers", fromlist=["create_power"]).create_power("Poison", 5, target.id))
        _set_piles(combat, hand_cards=[CardInstance("Catalyst")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert target.get_power_amount("Poison") == 10

    def test_catalyst_plus_triples_existing_poison(self):
        combat = _make_combat()
        target = combat.state.monsters[0]
        target.add_power(__import__("sts_py.engine.combat.powers", fromlist=["create_power"]).create_power("Poison", 5, target.id))
        _set_piles(combat, hand_cards=[CardInstance("Catalyst", upgraded=True)], draw_cards=[])

        assert combat.play_card(0, 0)

        assert target.get_power_amount("Poison") == 15

    def test_catalyst_is_stable_no_op_without_poison(self):
        combat = _make_combat()
        _set_piles(combat, hand_cards=[CardInstance("Catalyst")], draw_cards=[])

        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].get_power_amount("Poison") == 0

    def test_crippling_cloud_applies_weak_and_poison_to_all(self):
        combat = _make_combat(monster_hps=[30, 30], relics=[])
        _set_piles(combat, hand_cards=[CardInstance("CripplingCloud")], draw_cards=[])

        assert combat.play_card(0)

        assert [monster.get_power_amount("Weak") for monster in combat.state.monsters] == [2, 2]
        assert [monster.get_power_amount("Poison") for monster in combat.state.monsters] == [4, 4]
        assert [card.card_id for card in combat.state.card_manager.exhaust_pile.cards] == ["CripplingCloud"]

    def test_crippling_cloud_plus_poison_upgrades_to_seven(self):
        combat = _make_combat(monster_hps=[30, 30], relics=[])
        _set_piles(combat, hand_cards=[CardInstance("CripplingCloud", upgraded=True)], draw_cards=[])

        assert combat.play_card(0)

        assert [monster.get_power_amount("Poison") for monster in combat.state.monsters] == [7, 7]

    def test_corpse_explosion_applies_poison_and_marker(self):
        combat = _make_combat(monster_hps=[20, 20])
        _set_piles(combat, hand_cards=[CardInstance("CorpseExplosion")], draw_cards=[])

        assert combat.play_card(0, 0)

        target = combat.state.monsters[0]
        assert target.get_power_amount("Poison") == 6
        assert target.get_power_amount("CorpseExplosion") == 1

    def test_corpse_explosion_death_blast_uses_dead_monster_max_hp(self):
        combat = _make_combat(monster_hps=[6, 30])
        _set_piles(combat, hand_cards=[CardInstance("CorpseExplosion"), CardInstance("Strike")], draw_cards=[])

        assert combat.play_card(0, 0)
        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].is_dead()
        assert combat.state.monsters[1].hp == 24

    def test_corpse_explosion_does_not_hit_already_dead_monsters(self):
        combat = _make_combat(monster_hps=[6, 0, 30])
        _set_piles(combat, hand_cards=[CardInstance("CorpseExplosion"), CardInstance("Strike")], draw_cards=[])

        assert combat.play_card(0, 0)
        assert combat.play_card(0, 0)

        assert combat.state.monsters[1].hp == 0
        assert combat.state.monsters[2].hp == 24

    def test_corpse_explosion_chain_kills_continue_through_formal_death_hook(self):
        combat = _make_combat(monster_hps=[6, 6, 30])
        _set_piles(combat, hand_cards=[CardInstance("CorpseExplosion"), CardInstance("Strike")], draw_cards=[])

        assert combat.play_card(0, 0)
        assert combat.play_card(0, 0)

        assert combat.state.monsters[0].is_dead()
        assert combat.state.monsters[1].is_dead()
        assert combat.state.monsters[2].hp == 24

    def test_specimen_and_corpse_explosion_order_is_explosion_then_transfer(self):
        combat = _make_combat(monster_hps=[6, 20, 20], relics=["The Specimen"])
        _set_piles(combat, hand_cards=[CardInstance("CorpseExplosion"), CardInstance("Strike")], draw_cards=[])

        assert combat.play_card(0, 0)
        assert combat.play_card(0, 0)

        assert combat.state.monsters[1].hp == 14
        assert combat.state.monsters[2].hp == 14
        assert sorted(monster.get_power_amount("Poison") for monster in combat.state.monsters[1:]) == [0, 6]

    def test_snecko_skull_adds_extra_poison_on_apply_cards(self):
        combat = _make_combat(monster_hps=[30], relics=["SneckoSkull"])
        _set_piles(combat, hand_cards=[CardInstance("DeadlyPoison"), CardInstance("PoisonedStab")], draw_cards=[])

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].get_power_amount("Poison") == 6

        assert combat.play_card(0, 0)
        assert combat.state.monsters[0].get_power_amount("Poison") == 10

    def test_snecko_skull_affects_bouncing_flask_and_crippling_cloud_and_noxious_fumes(self):
        combat = _make_combat(monster_hps=[30, 30], relics=["SneckoSkull"])
        combat.state.player.max_energy = 5
        combat.state.player.energy = 5
        combat.state.card_manager.set_max_energy(5)
        combat.state.card_manager.set_energy(5)
        _set_piles(
            combat,
            hand_cards=[CardInstance("BouncingFlask"), CardInstance("CripplingCloud"), CardInstance("NoxiousFumes")],
            draw_cards=[CardInstance("Strike")] * 5,
        )

        assert combat.play_card(0)
        assert sum(monster.get_power_amount("Poison") for monster in combat.state.monsters) == 12

        assert combat.play_card(0)
        assert [monster.get_power_amount("Weak") for monster in combat.state.monsters] == [2, 2]
        assert sum(monster.get_power_amount("Poison") for monster in combat.state.monsters) == 22

        assert combat.play_card(0)
        combat.end_player_turn()
        assert sum(monster.get_power_amount("Poison") for monster in combat.state.monsters) == 26
