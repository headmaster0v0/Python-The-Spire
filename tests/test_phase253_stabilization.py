from __future__ import annotations

from sts_py.engine.combat.card_effects import _implemented_colorless_combat_card_ids
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.orbs import PlasmaOrb
from sts_py.engine.combat.potion_effects import use_potion
from sts_py.engine.combat.powers import create_power
from sts_py.engine.combat.stance import StanceType
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import ALL_CARD_DEFS
from sts_py.engine.content.potions import create_potion
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.run.events import Event, EventChoice
from sts_py.engine.run.run_engine import RunEngine, RunPhase, _deck_card_base_id
from sts_py.terminal.render import render_card_detail_lines


SEED_LONG = 4452322743548530140
SEED_STRING = "PHASE253STABILIZE"


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, hp: int = 80, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))

    def take_turn(self, player) -> None:
        if self.attack_damage > 0:
            player.take_damage(self.attack_damage)


def _make_combat(
    *,
    monster_hps: list[int] | None = None,
    energy: int = 3,
    relics: list[str] | None = None,
) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    hp_list = monster_hps or [80]
    monsters = [DummyAttackMonster(f"DummyAttack{index}", hp=hp) for index, hp in enumerate(hp_list)]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=80,
        player_max_hp=80,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Strike", "Defend", "Defend", "Bash", "PommelStrike"],
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
) -> None:
    card_manager = combat.state.card_manager
    card_manager.hand.cards = _bind_cards(combat, hand_cards or [])
    card_manager.draw_pile.cards = _bind_cards(combat, draw_cards or [])
    card_manager.discard_pile.cards = _bind_cards(combat, discard_cards or [])
    card_manager.exhaust_pile.cards = []


def test_phase253_whirlwind_chemical_x_uses_effect_hits_but_spends_only_actual_energy() -> None:
    combat = _make_combat(monster_hps=[40, 40], energy=2, relics=["ChemicalX"])
    _set_piles(combat, hand_cards=[CardInstance("Whirlwind")], draw_cards=[])

    assert combat.play_card(0)

    assert [monster.hp for monster in combat.state.monsters] == [20, 20]
    assert combat.state.player.energy == 0


def test_phase253_malaise_chemical_x_and_upgrade_apply_to_effect_value_only() -> None:
    combat = _make_combat(monster_hps=[80], energy=1, relics=["ChemicalX"])
    _set_piles(combat, hand_cards=[CardInstance("Malaise", upgraded=True)], draw_cards=[])

    assert combat.play_card(0, 0)

    target = combat.state.monsters[0]
    assert combat.state.player.energy == 0
    assert target.get_power_amount("Weak") == 4
    assert target.strength == -4
    assert target.get_power_amount("Lose Strength") == 4


def test_phase253_conjure_blade_chemical_x_and_upgrade_flow_into_expunger_x() -> None:
    combat = _make_combat(monster_hps=[120], energy=2, relics=["ChemicalX"])
    _set_piles(combat, hand_cards=[CardInstance("ConjureBlade", upgraded=True)], draw_cards=[])

    assert combat.play_card(0)

    generated = combat.state.card_manager.draw_pile.cards
    assert len(generated) == 1
    expunger = generated[0]
    assert expunger.card_id == "Expunger"
    assert expunger.misc == 5
    assert expunger.base_magic_number == 5
    assert expunger.magic_number == 5
    assert expunger.base_damage == 9
    assert expunger.damage == 9
    assert combat.state.player.energy == 0


def test_phase253_tempest_reinforced_body_and_multicast_share_effect_x_rules() -> None:
    tempest = _make_combat(energy=1, relics=["ChemicalX"])
    _set_piles(tempest, hand_cards=[CardInstance("Tempest", upgraded=True)], draw_cards=[])
    assert tempest.play_card(0)
    assert len(tempest.state.player.orbs.channels) == 3
    assert tempest.state.monsters[0].hp == 72
    assert tempest.state.player.energy == 0

    reinforced = _make_combat(energy=2, relics=["ChemicalX"])
    _set_piles(reinforced, hand_cards=[CardInstance("ReinforcedBody")], draw_cards=[])
    assert reinforced.play_card(0)
    assert reinforced.state.player.block == 28
    assert reinforced.state.player.energy == 0

    multicast = _make_combat(energy=1, relics=["ChemicalX"])
    multicast.state.player.orbs.channels = [PlasmaOrb()]
    multicast.state.player.orbs.owner = multicast.state.player
    multicast.state.player.orbs.combat_state = multicast.state
    _set_piles(multicast, hand_cards=[CardInstance("MultiCast", upgraded=True)], draw_cards=[])
    assert multicast.play_card(0)
    assert multicast.state.player.energy == 8
    assert multicast.state.player.orbs.filled_count() == 0


def test_phase253_transmutation_free_to_play_keeps_energy_and_still_gets_chemical_x_bonus() -> None:
    combat = _make_combat(energy=3, relics=["ChemicalX"])
    transmutation = CardInstance("Transmutation", upgraded=True)
    transmutation.free_to_play_once = True
    _set_piles(combat, hand_cards=[transmutation], draw_cards=[])

    assert combat.play_card(0)

    legal_pool = set(_implemented_colorless_combat_card_ids())
    generated = combat.state.card_manager.hand.cards
    assert combat.state.player.energy == 3
    assert len(generated) == 2
    assert all(card.card_id in legal_pool for card in generated)
    assert all(card.upgraded for card in generated)
    assert all(card.cost_for_turn == 0 for card in generated)


def test_phase253_shared_random_colorless_pool_stays_consistent_across_generators() -> None:
    legal_pool = set(_implemented_colorless_combat_card_ids())
    assert "BandageUp" not in legal_pool
    assert "RitualDagger" not in legal_pool

    jack = _make_combat()
    _set_piles(jack, hand_cards=[CardInstance("JackOfAllTrades", upgraded=True)], draw_cards=[])
    assert jack.play_card(0)
    assert {card.card_id for card in jack.state.card_manager.hand.cards} <= legal_pool

    magnetism = _make_combat()
    magnetism.state.player.add_power(create_power("Magnetism", 1, "player"))
    magnetism.state.player.powers.at_start_of_turn(magnetism.state.player)
    assert magnetism.state.card_manager.hand.cards[-1].card_id in legal_pool

    transmutation = _make_combat(relics=["ChemicalX"])
    card = CardInstance("Transmutation")
    card.free_to_play_once = True
    _set_piles(transmutation, hand_cards=[card], draw_cards=[])
    assert transmutation.play_card(0)
    assert {generated.card_id for generated in transmutation.state.card_manager.hand.cards} <= legal_pool


def test_phase253_allow_parallel_instances_remains_opt_in_only_for_the_bomb() -> None:
    combat = _make_combat()
    player = combat.state.player
    player.add_power(create_power("Strength", 2, "player"))
    player.add_power(create_power("Strength", 3, "player"))
    strength_powers = [power for power in player.powers.powers if power.id == "Strength"]
    assert len(strength_powers) == 1
    assert strength_powers[0].amount == 5

    player.add_power(create_power("TheBomb", 3, "player"))
    player.add_power(create_power("TheBomb", 3, "player"))
    bomb_powers = [power for power in player.powers.powers if power.id == "TheBomb"]
    assert len(bomb_powers) == 2
    assert sorted(power.amount for power in bomb_powers) == [3, 3]


def test_phase253_havoc_and_mayhem_autoplay_leave_no_pending_choice() -> None:
    havoc = _make_combat(monster_hps=[30], energy=2)
    _set_piles(havoc, hand_cards=[CardInstance("Havoc")], draw_cards=[CardInstance("Strike")])
    assert havoc.play_card(0)
    assert havoc.state.player.energy == 1
    assert havoc.state.pending_combat_choice is None
    assert havoc.state.monsters[0].hp == 24

    mayhem = _make_combat(monster_hps=[20], energy=3)
    mayhem.state.player.add_power(create_power("Mayhem", 1, "player"))
    _set_piles(mayhem, hand_cards=[], draw_cards=[], discard_cards=[CardInstance("Strike")])
    mayhem.state.player.powers.at_start_of_turn(mayhem.state.player)
    assert mayhem.state.player.energy == 3
    assert mayhem.state.pending_combat_choice is None
    assert mayhem.state.monsters[0].hp == 14


def test_phase253_ritual_dagger_smith_event_upgrade_and_remove_preserve_runtime_wire_shape() -> None:
    smith_engine = RunEngine.create(SEED_STRING, ascension=0)
    smith_engine.state.phase = RunPhase.REST
    smith_engine.state.deck = ["RitualDagger#15"]
    assert smith_engine.smith(0) is True
    assert smith_engine.state.deck == ["RitualDagger#15+"]

    upgrade_engine = RunEngine.create(SEED_STRING, ascension=0)
    upgrade_engine.state.phase = RunPhase.EVENT
    upgrade_engine.state.deck = ["RitualDagger#18"]
    upgrade_engine._current_event = Event(
        id="Test Upgrade",
        name="Test Upgrade",
        choices=[EventChoice(description="upgrade", requires_card_upgrade=True)],
    )
    assert upgrade_engine.choose_event_option(0)["requires_card_choice"] is True
    upgrade_result = upgrade_engine.choose_card_for_event(0)
    assert upgrade_result["success"] is True
    assert upgrade_result["old_card"] == "RitualDagger#18"
    assert upgrade_result["new_card"] == "RitualDagger#18+"
    assert upgrade_engine.state.deck == ["RitualDagger#18+"]

    remove_engine = RunEngine.create(SEED_STRING, ascension=0)
    remove_engine.state.phase = RunPhase.EVENT
    remove_engine.state.deck = ["RitualDagger#18+"]
    remove_engine._current_event = Event(
        id="Test Remove",
        name="Test Remove",
        choices=[EventChoice(description="remove", requires_card_removal=True)],
    )
    assert remove_engine.choose_event_option(0)["requires_card_choice"] is True
    remove_result = remove_engine.choose_card_for_event(0)
    assert remove_result == {"success": True, "action": "card_removed", "card_id": "RitualDagger#18+"}
    assert remove_engine.state.deck == []


def test_phase253_ritual_dagger_transform_and_cli_detail_lines_use_base_card_metadata() -> None:
    engine = RunEngine.create(SEED_STRING, ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine.state.deck = ["RitualDagger#18+"]
    engine._current_event = Event(
        id="Test Transform",
        name="Test Transform",
        choices=[EventChoice(description="transform", requires_card_transform=True)],
    )

    assert engine.choose_event_option(0)["requires_card_choice"] is True
    transform_result = engine.choose_card_for_event(0)

    assert transform_result["success"] is True
    assert transform_result["old_card"] == "RitualDagger#18+"
    transformed_base = CardInstance(transform_result["new_card"]).card_id
    assert ALL_CARD_DEFS[transformed_base].cost == 1
    assert _deck_card_base_id("RitualDagger#18+") == "RitualDagger"

    detail_lines = render_card_detail_lines("RitualDagger#18+", index=2)
    assert detail_lines[0] == "序号: 2"
    assert any(line == "ID: RitualDagger#18+" for line in detail_lines)
    assert any("伤害 18" in line for line in detail_lines)
    assert all("\ufffd" not in line for line in detail_lines)


def test_phase253_potion_effects_use_runtime_heal_and_stance_helpers() -> None:
    combat = _make_combat(monster_hps=[40], energy=3, relics=["MagicFlower"])
    combat.state.player.hp = 50
    blood_potion = create_potion("BloodPotion")
    assert blood_potion is not None
    use_potion(blood_potion, combat.state)
    assert combat.state.player.hp == 74

    stance_potion = create_potion("StancePotion")
    assert stance_potion is not None
    use_potion(stance_potion, combat.state)
    assert getattr(combat.state.player.stance, "stance_type", None) in {StanceType.CALM, StanceType.WRATH}

    ambrosia = create_potion("Ambrosia")
    assert ambrosia is not None
    use_potion(ambrosia, combat.state)
    assert getattr(combat.state.player.stance, "stance_type", None) == StanceType.DIVINITY

    combat.state.engine.state.potions = ["BlockPotion", "EmptyPotionSlot", "EmptyPotionSlot"]
    entropic_brew = create_potion("EntropicBrew")
    assert entropic_brew is not None
    use_potion(entropic_brew, combat.state)
    assert combat.state.engine.state.potions[0] == "BlockPotion"
    assert all(slot != "EmptyPotionSlot" for slot in combat.state.engine.state.potions[1:])
