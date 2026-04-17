from __future__ import annotations

from sts_py.engine.combat.powers import create_power
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterMove
from sts_py.engine.run.run_engine import MapNode, RoomType, RunEngine, RunPhase


def test_map_marks_a_single_burning_elite_before_emerald_key() -> None:
    engine = RunEngine.create("TESTBURNINGELITE", ascension=0)
    burning_elites = [node for node in engine.state.map_nodes if node.burning_elite]

    assert len(burning_elites) == 1
    assert burning_elites[0].room_type == RoomType.ELITE


def test_map_skips_burning_elite_after_emerald_key_obtained() -> None:
    engine = RunEngine.create("TESTNOBURNINGELITE", ascension=0)
    engine.state.emerald_key_obtained = True
    engine._generate_map()

    assert all(not node.burning_elite for node in engine.state.map_nodes)


def test_recall_grants_ruby_key_and_returns_to_map() -> None:
    engine = RunEngine.create("TESTRECALLKEY", ascension=0)
    engine.state.phase = RunPhase.REST

    assert engine.recall() is True
    assert engine.state.ruby_key_obtained is True
    assert engine.state.phase == RunPhase.MAP


def test_treasure_room_offers_relic_or_sapphire_key() -> None:
    engine = RunEngine.create("TESTTREASUREKEY", ascension=0)

    engine._enter_treasure()
    relic = engine.state.pending_treasure_relic
    assert engine.state.phase == RunPhase.TREASURE
    assert relic is not None

    result = engine.take_sapphire_key()

    assert result["success"] is True
    assert result["action"] == "took_sapphire_key"
    assert result["skipped_relic"] == relic
    assert engine.state.sapphire_key_obtained is True
    assert relic not in engine.state.relics
    assert engine.state.phase == RunPhase.MAP


def test_treasure_room_can_take_relic_instead_of_key() -> None:
    engine = RunEngine.create("TESTTREASURERELIC", ascension=0)

    engine._enter_treasure()
    relic = engine.state.pending_treasure_relic
    result = engine.take_treasure_relic()

    assert result["success"] is True
    assert result["relic_id"] == relic
    assert relic in engine.state.relics
    assert engine.state.sapphire_key_obtained is False
    assert engine.state.phase == RunPhase.MAP


def test_burning_elite_victory_grants_emerald_key() -> None:
    engine = RunEngine.create("TESTEMERALDKEY", ascension=0)
    engine.state.map_nodes = [MapNode(floor=10, room_type=RoomType.ELITE, node_id=0, burning_elite=True)]
    engine.state.current_node_idx = 0
    engine._start_combat("Gremlin Nob")
    for monster in engine.state.combat.state.monsters:
        monster.hp = 0
        monster.is_dying = True

    engine.end_combat()

    assert engine.state.emerald_key_obtained is True
    assert engine.state.phase == RunPhase.REWARD


def test_act3_boss_victory_with_all_keys_waits_for_boss_relic_choice() -> None:
    engine = RunEngine.create("TESTACT4ENTRY", ascension=0)
    engine.state.act = 3
    engine.state.ruby_key_obtained = True
    engine.state.emerald_key_obtained = True
    engine.state.sapphire_key_obtained = True
    engine.state.map_nodes = [MapNode(floor=51, room_type=RoomType.BOSS, node_id=0)]
    engine.state.current_node_idx = 0
    engine._start_combat("Awakened One")
    for monster in engine.state.combat.state.monsters:
        monster.hp = 0
        monster.is_dying = True

    engine.end_combat()

    assert engine.state.act == 3
    assert engine.state.phase == RunPhase.VICTORY
    assert len(engine.state.pending_boss_relic_choices) == 3

    engine.choose_boss_relic(0)
    engine.clear_pending_reward_notifications()
    engine.transition_to_next_act()

    assert engine.state.act == 4
    assert engine.state.phase == RunPhase.MAP
    assert [node.room_type for node in engine.state.map_nodes] == [
        RoomType.REST,
        RoomType.SHOP,
        RoomType.ELITE,
        RoomType.BOSS,
    ]


def test_shield_and_spear_encounter_creates_act4_elite_pair() -> None:
    combat = CombatEngine.create(
        encounter_name="Shield and Spear",
        player_hp=80,
        player_max_hp=80,
        ai_rng=RunEngine.create("TESTACT4COMBAT1").ai_rng,
        hp_rng=RunEngine.create("TESTACT4COMBAT1").hp_rng,
        ascension=0,
        deck=["Strike", "Defend", "Bash"],
        relics=[],
    )

    monster_ids = [monster.id for monster in combat.state.monsters]
    assert monster_ids == ["SpireShield", "SpireSpear"]
    assert combat.state.player.powers.has_power("Surrounded")
    assert combat.state.monsters[0].powers.has_power("Artifact")
    assert combat.state.monsters[1].powers.has_power("Artifact")


def test_surrounded_assigns_and_switches_backattack_between_act4_elites() -> None:
    engine = RunEngine.create("TESTACT4BACKATTACK", ascension=0)
    combat = CombatEngine.create(
        encounter_name="Shield and Spear",
        player_hp=80,
        player_max_hp=80,
        ai_rng=engine.ai_rng,
        hp_rng=engine.hp_rng,
        ascension=0,
        deck=["Strike", "Defend", "Bash"],
        relics=[],
    )

    assert combat.state.monsters[0].powers.has_power("BackAttack") is False
    assert combat.state.monsters[1].powers.has_power("BackAttack") is True

    combat.player_attack(1, 1)

    assert combat.state.monsters[0].powers.has_power("BackAttack") is True
    assert combat.state.monsters[1].powers.has_power("BackAttack") is False


def test_surrounded_and_backattack_clear_when_one_elite_dies() -> None:
    engine = RunEngine.create("TESTACT4BACKATTACKCLEAR", ascension=0)
    combat = CombatEngine.create(
        encounter_name="Shield and Spear",
        player_hp=80,
        player_max_hp=80,
        ai_rng=engine.ai_rng,
        hp_rng=engine.hp_rng,
        ascension=0,
        deck=["Strike", "Defend", "Bash"],
        relics=[],
    )

    shield = combat.state.monsters[0]
    shield.hp = 0
    shield.is_dying = True
    combat._on_monster_death(shield)

    assert combat.state.player.powers.has_power("Surrounded") is False
    assert all(not monster.powers.has_power("BackAttack") for monster in combat.state.monsters[1:] if not monster.is_dead())


def test_corrupt_heart_encounter_starts_with_invincible_and_beat_of_death() -> None:
    combat = CombatEngine.create(
        encounter_name="The Heart",
        player_hp=80,
        player_max_hp=80,
        ai_rng=RunEngine.create("TESTACT4COMBAT2").ai_rng,
        hp_rng=RunEngine.create("TESTACT4COMBAT2").hp_rng,
        ascension=0,
        deck=["Strike", "Defend", "Bash"],
        relics=[],
    )

    heart = combat.state.monsters[0]
    assert heart.id == "CorruptHeart"
    assert heart.powers.has_power("Invincible")
    assert heart.powers.get_power_amount("Invincible") == 300
    assert heart.powers.has_power("BeatOfDeath")
    assert heart.next_move is not None
    assert heart.next_move.intent.name == "STRONG_DEBUFF"


def test_beat_of_death_triggers_after_player_card_play() -> None:
    engine = RunEngine.create("TESTBEATOFDEATH", ascension=0)
    combat = CombatEngine.create(
        encounter_name="The Heart",
        player_hp=80,
        player_max_hp=80,
        ai_rng=engine.ai_rng,
        hp_rng=engine.hp_rng,
        ascension=0,
        deck=["Strike"],
        relics=[],
    )

    initial_hp = combat.state.player.hp
    assert combat.play_card(0, 0) is True

    assert combat.state.player.hp == initial_hp - 1


def test_corrupt_heart_invincible_caps_single_hit_damage() -> None:
    combat = CombatEngine.create(
        encounter_name="The Heart",
        player_hp=80,
        player_max_hp=80,
        ai_rng=RunEngine.create("TESTACT4COMBAT3").ai_rng,
        hp_rng=RunEngine.create("TESTACT4COMBAT3").hp_rng,
        ascension=0,
        deck=["Strike", "Defend", "Bash"],
        relics=[],
    )

    heart = combat.state.monsters[0]
    initial_hp = heart.hp
    dealt = heart.take_damage(999)

    assert dealt == 300
    assert heart.hp == initial_hp - 300
    assert heart.powers.get_power_amount("Invincible") == 0


def test_corrupt_heart_invincible_resets_each_heart_turn() -> None:
    engine = RunEngine.create("TESTINVINCIBLERESET", ascension=0)
    combat = CombatEngine.create(
        encounter_name="The Heart",
        player_hp=80,
        player_max_hp=80,
        ai_rng=engine.ai_rng,
        hp_rng=engine.hp_rng,
        ascension=0,
        deck=["Strike"],
        relics=[],
    )

    heart = combat.state.monsters[0]
    heart.take_damage(999)
    assert heart.powers.get_power_amount("Invincible") == 0

    combat.end_player_turn()

    assert heart.powers.get_power_amount("Invincible") == 300


def test_corrupt_heart_attack_turn_handles_take_damage_kwargs() -> None:
    engine = RunEngine.create("TESTHEARTKWARGS", ascension=0)
    combat = CombatEngine.create(
        encounter_name="The Heart",
        player_hp=80,
        player_max_hp=80,
        ai_rng=engine.ai_rng,
        hp_rng=engine.hp_rng,
        ascension=0,
        deck=["Strike"],
        relics=[],
    )

    heart = combat.state.monsters[0]
    heart.next_move = MonsterMove(move_id=1, intent=MonsterIntent.ATTACK, base_damage=2)
    heart.blood_hit_count = 2
    heart.blood_shot_dmg = 2

    initial_hp = combat.state.player.hp
    combat._execute_monster_move(0, heart)

    assert combat.state.player.hp < initial_hp


def test_painful_stabs_only_adds_wound_on_actual_non_thorns_damage() -> None:
    engine = RunEngine.create("TESTPAINFULSTABS", ascension=0)
    combat = CombatEngine.create(
        encounter_name="Shield and Spear",
        player_hp=80,
        player_max_hp=80,
        ai_rng=engine.ai_rng,
        hp_rng=engine.hp_rng,
        ascension=0,
        deck=["Strike"],
        relics=[],
    )

    shield = combat.state.monsters[0]
    shield.add_power(create_power("Painful Stabs", -1, shield.id))
    shield.set_move(MonsterMove(1, MonsterIntent.ATTACK_DEBUFF, shield.bash_dmg, name="Bash"))

    combat.state.player.block = 999
    shield.take_turn(combat.state.player)
    assert [card.card_id for card in combat.state.card_manager.discard_pile.cards].count("Wound") == 0

    combat.state.player.block = 0
    shield.take_turn(combat.state.player)
    assert [card.card_id for card in combat.state.card_manager.discard_pile.cards].count("Wound") == 1


def test_corrupt_heart_buff_cycle_stacks_key_powers_stably() -> None:
    engine = RunEngine.create("TESTHEARTBUFFCYCLE", ascension=0)
    combat = CombatEngine.create(
        encounter_name="The Heart",
        player_hp=80,
        player_max_hp=80,
        ai_rng=engine.ai_rng,
        hp_rng=engine.hp_rng,
        ascension=0,
        deck=["Strike"],
        relics=[],
    )

    heart = combat.state.monsters[0]
    for _ in range(4):
        heart.set_move(MonsterMove(4, MonsterIntent.BUFF, name="Buff"))
        heart.take_turn(combat.state.player)

    assert heart.powers.has_power("Artifact")
    assert heart.powers.get_power_amount("BeatOfDeath") == 2
    assert heart.powers.has_power("Painful Stabs")
    assert heart.get_effective_strength() >= 18
