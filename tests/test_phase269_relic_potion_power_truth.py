from __future__ import annotations

from types import SimpleNamespace

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.potion_effects import use_potion
from sts_py.engine.combat.powers import create_power
from sts_py.engine.combat.stance import StanceType
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.potions import create_potion
from sts_py.engine.content.relics import ALL_RELICS
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.run.run_engine import RunEngine, RunPhase
from sts_py.engine.run.shop import ShopEngine, ShopItem, ShopItemType, ShopState
from sts_py.tools.wiki_audit import build_relic_source_facts


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 60):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=6, name="Attack"))


def _make_combat(*, monster_hps: list[int] | None = None, energy: int = 3, relics: list[str] | None = None) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [DummyAttackMonster(f"Dummy{index}", hp=hp) for index, hp in enumerate(monster_hps or [60])]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=70,
        player_max_hp=70,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Defend", "Bash", "Burn"],
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


def _force_win_current_combat(engine: RunEngine) -> None:
    assert engine.state.combat is not None
    for monster in engine.state.combat.state.monsters:
        monster.hp = 0
        monster.is_dying = True
    engine.end_combat()


def test_phase269_relic_family_battle_turn_and_resource_truth() -> None:
    combat_engine = RunEngine.create("PHASE269RELICBATTLE", ascension=0)
    combat_engine.state.relics.extend(["Lantern", "Anchor"])
    combat_engine.start_combat_with_monsters(["Cultist"])

    combat = combat_engine.state.combat
    assert combat is not None
    assert combat.state.player.block == 10
    assert combat.state.player.energy == 4

    combat.state.player.hp = 40
    combat_engine.state.player_hp = 40
    _force_win_current_combat(combat_engine)
    assert combat_engine.state.player_hp == 46

    shop_engine = RunEngine.create("PHASE269RELICSHOPENTER", ascension=0)
    shop_engine.state.player_hp = 50
    shop_engine.state.relics.append("MealTicket")
    shop_engine._enter_shop()
    assert shop_engine.state.player_hp == 65


def test_phase269_relic_family_reward_shop_rest_and_pickup_truth() -> None:
    engine = RunEngine.create("PHASE269RELICPICKUP", ascension=0)
    engine.state.player_gold = 999
    engine.state.deck = ["Defend", "ShrugItOff", "Strike", "Bash"]
    shop = ShopState(
        relics=[
            ShopItem(ShopItemType.RELIC, "Strawberry", 150),
            ShopItem(ShopItemType.RELIC, "WarPaint", 150),
            ShopItem(ShopItemType.RELIC, "Whetstone", 150),
        ]
    )
    shop_engine = ShopEngine(engine, shop)

    max_hp_before = engine.state.player_max_hp
    assert shop_engine.buy_relic(0)["success"] is True
    assert engine.state.player_max_hp == max_hp_before + 7

    assert shop_engine.buy_relic(1)["success"] is True
    assert "Defend+" in engine.state.deck
    assert "ShrugItOff+" in engine.state.deck

    assert shop_engine.buy_relic(2)["success"] is True
    assert "Strike+" in engine.state.deck
    assert "Bash+" in engine.state.deck

    boss_engine = RunEngine.create("PHASE269STARTERSWAP", ascension=0)
    boss_engine.state.phase = RunPhase.VICTORY
    boss_engine.state.pending_boss_relic_choices = ["BlackBlood", "TinyHouse", "CallingBell"]
    result = boss_engine.choose_boss_relic(0)
    assert result["success"] is True
    assert "BurningBlood" not in boss_engine.state.relics
    assert "BlackBlood" in boss_engine.state.relics

    assert "relic:rest_site_strength" in build_relic_source_facts(ALL_RELICS["Girya"])["effect_signatures"]
    assert "relic:rest_site_remove" in build_relic_source_facts(ALL_RELICS["PeacePipe"])["effect_signatures"]
    assert "relic:rest_site_dig" in build_relic_source_facts(ALL_RELICS["Shovel"])["effect_signatures"]


def test_phase269_relic_family_cardplay_deck_and_status_truth() -> None:
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

    assert "relic:on_poison_applied" in build_relic_source_facts(ALL_RELICS["SneckoSkull"])["effect_signatures"]
    assert "relic:replace_starter_relic" in build_relic_source_facts(ALL_RELICS["HolyWater"])["effect_signatures"]


def test_phase269_relic_and_potion_dedicated_bespoke_truth() -> None:
    sacred_bark_combat = _make_combat(monster_hps=[40], relics=["SacredBark"])
    block_potion = create_potion("BlockPotion")
    assert block_potion is not None
    use_potion(block_potion, sacred_bark_combat.state)
    assert sacred_bark_combat.state.player.block == 24

    smoke_combat = _make_combat(monster_hps=[40])
    smoke_bomb = create_potion("SmokeBomb")
    assert smoke_bomb is not None
    use_potion(smoke_bomb, smoke_combat.state)
    assert smoke_combat.state.escape_combat is True

    fairy_combat = _make_combat(monster_hps=[40])
    fairy = create_potion("FairyInABottle")
    assert fairy is not None
    use_potion(fairy, fairy_combat.state)
    assert fairy_combat.state.player.fairy_in_a_bottle is True
    assert fairy_combat.state.player.fairy_heal_percent == 30

    memories_combat = _make_combat(monster_hps=[40])
    liquid_memories = create_potion("LiquidMemories")
    assert liquid_memories is not None
    strike = CardInstance("Strike")
    bash = CardInstance("Bash")
    _set_piles(memories_combat, hand_cards=[], draw_cards=[], discard_cards=[strike, bash])
    use_potion(liquid_memories, memories_combat.state)
    assert [card.card_id for card in memories_combat.state.card_manager.hand.cards] == ["Bash"]
    assert memories_combat.state.card_manager.hand.cards[0].cost == 0

    gamblers_combat = _make_combat(monster_hps=[40])
    gamblers = create_potion("GamblersBrew")
    assert gamblers is not None
    _set_piles(
        gamblers_combat,
        hand_cards=[CardInstance("Strike"), CardInstance("Defend")],
        draw_cards=[CardInstance("Bash"), CardInstance("Anger")],
    )
    use_potion(gamblers, gamblers_combat.state)
    assert sorted(card.card_id for card in gamblers_combat.state.card_manager.hand.cards) == ["Anger", "Bash"]
    assert sorted(card.card_id for card in gamblers_combat.state.card_manager.discard_pile.cards) == ["Defend", "Strike"]


def test_phase269_potion_family_resource_and_power_truth() -> None:
    resource_combat = _make_combat(monster_hps=[40])
    block_potion = create_potion("BlockPotion")
    assert block_potion is not None
    use_potion(block_potion, resource_combat.state)
    assert resource_combat.state.player.block == 12

    heal_combat = _make_combat(monster_hps=[40])
    heal_combat.state.player.hp = 40
    blood_potion = create_potion("BloodPotion")
    assert blood_potion is not None
    use_potion(blood_potion, heal_combat.state)
    assert heal_combat.state.player.hp == 54

    buff_combat = _make_combat(monster_hps=[40])
    strength_potion = create_potion("StrengthPotion")
    assert strength_potion is not None
    use_potion(strength_potion, buff_combat.state)
    assert buff_combat.state.player.get_power_amount("Strength") == 2

    debuff_combat = _make_combat(monster_hps=[40])
    weak_potion = create_potion("WeakPotion")
    assert weak_potion is not None
    use_potion(weak_potion, debuff_combat.state, target_idx=0)
    assert debuff_combat.state.monsters[0].get_power_amount("Weak") == 3


def test_phase269_potion_family_card_and_special_truth() -> None:
    card_combat = _make_combat(monster_hps=[40])
    attack_potion = create_potion("AttackPotion")
    assert attack_potion is not None
    _set_piles(card_combat, hand_cards=[], draw_cards=[], discard_cards=[])
    use_potion(attack_potion, card_combat.state)
    assert len(card_combat.state.card_manager.hand.cards) == 1
    assert card_combat.state.card_manager.hand.cards[0].cost == 0

    miracle_combat = _make_combat(monster_hps=[40])
    bottled_miracle = create_potion("BottledMiracle")
    assert bottled_miracle is not None
    _set_piles(miracle_combat, hand_cards=[], draw_cards=[], discard_cards=[])
    use_potion(bottled_miracle, miracle_combat.state)
    assert [card.card_id for card in miracle_combat.state.card_manager.hand.cards] == ["Miracle", "Miracle"]
    assert all(card.retain for card in miracle_combat.state.card_manager.hand.cards)

    orb_combat = _make_combat(monster_hps=[40])
    capacity = create_potion("PotionofCapacity")
    assert capacity is not None
    slots_before = orb_combat.state.player.orbs.slots
    use_potion(capacity, orb_combat.state)
    assert orb_combat.state.player.orbs.slots == slots_before + 2


def test_phase269_power_callback_family_turn_and_damage_truth() -> None:
    combat = _make_combat(monster_hps=[40])
    player = combat.state.player

    strength = create_power("Strength", 2, "player")
    dexterity = create_power("Dexterity", 2, "player")
    vulnerable = create_power("Vulnerable", 2, "player")
    assert strength is not None and dexterity is not None and vulnerable is not None
    assert strength.at_damage_give(7) == 9
    assert dexterity.modify_block(5) == 7
    assert vulnerable.at_damage_receive(10) == 15

    battle_hymn = create_power("BattleHymn", 1, "player")
    assert battle_hymn is not None
    _set_piles(combat, hand_cards=[], draw_cards=[], discard_cards=[])
    result = battle_hymn.at_start_of_turn(player)
    assert result == {"type": "battle_hymn_generate", "count": 1}
    assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Smite"]

    energized = create_power("Energized", 2, "player")
    assert energized is not None
    player.energy = 0
    player.add_power(energized)
    result = energized.on_energy_recharge(player)
    assert result == {"type": "energized", "amount": 2}
    assert player.energy == 2

    equilibrium = create_power("Equilibrium", 1, "player")
    assert equilibrium is not None
    retained = CardInstance("Strike")
    ethereal = CardInstance("Dazed")
    _set_piles(combat, hand_cards=[retained, ethereal], draw_cards=[], discard_cards=[])
    result = equilibrium.at_end_of_turn_pre_end_turn_cards(player, True)
    assert result == {"type": "equilibrium_retain", "count": 1}
    assert retained.retain is True
    assert ethereal.retain is False


def test_phase269_power_callback_family_play_and_reaction_truth() -> None:
    combat = _make_combat(monster_hps=[40])
    player = combat.state.player
    monster = combat.state.monsters[0]

    after_image = create_power("AfterImage", 1, "player")
    assert after_image is not None
    assert after_image.on_player_card_played(player, CardInstance("Strike")) == {
        "type": "gain_block_on_card_played",
        "amount": 1,
    }
    assert player.block == 1

    _set_piles(combat, hand_cards=[], draw_cards=[CardInstance("Strike")], discard_cards=[])
    evolve = create_power("Evolve", 1, "player")
    assert evolve is not None
    assert evolve.on_card_draw(player, CardInstance("Burn")) == {"type": "draw_on_status", "amount": 1}
    assert [card.card_id for card in combat.state.card_manager.hand.cards] == ["Strike"]

    juggernaut = create_power("Juggernaut", 5, "player")
    assert juggernaut is not None
    result = juggernaut.on_gain_block(player, 5)
    assert result == {"type": "damage_random_enemy", "amount": 5}
    assert monster.hp == 35

    from sts_py.engine.combat.powers import ThieveryPower

    thievery = ThieveryPower()
    thievery.amount = 15
    assert thievery.on_steal_gold(12) == 12

    nirvana = create_power("Nirvana", 3, "player")
    assert nirvana is not None
    assert nirvana.on_scry(player) == {"block_gain": 3}
    assert player.block == 4


def test_phase269_power_dedicated_bespoke_truth() -> None:
    combat = _make_combat(monster_hps=[40])
    player = combat.state.player

    rupture = create_power("Rupture", 1, "player")
    assert rupture is not None
    result = rupture.on_hp_lost(player, 6, source_owner=player)
    assert result == {"type": "strength", "amount": 1}
    assert player.get_power_amount("Strength") == 1
    assert player.strength == 1

    rushdown = create_power("Rushdown", 2, "player")
    assert rushdown is not None
    _set_piles(combat, hand_cards=[], draw_cards=[CardInstance("Strike"), CardInstance("Defend")], discard_cards=[])
    result = rushdown.on_change_stance(
        player,
        SimpleNamespace(stance_type=StanceType.CALM),
        SimpleNamespace(stance_type=StanceType.WRATH),
    )
    assert result == {"draw_amount": 2}
    assert sorted(card.card_id for card in combat.state.card_manager.hand.cards) == ["Defend", "Strike"]

    static_discharge = create_power("StaticDischarge", 1, "player")
    assert static_discharge is not None
    result = static_discharge.on_player_attacked(player, 3)
    assert result == {"type": "static_discharge_channel", "count": 1}
    assert len(player.orbs.channels) == 1

    repair = create_power("Repair", 7, "player")
    assert repair is not None
    assert repair.on_victory(player) == 7
