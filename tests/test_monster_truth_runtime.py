from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.monster_truth import canonicalize_monster_id, get_monster_truth
from sts_py.engine.monsters.official_monster_strings import load_official_monster_strings
from sts_py.engine.run.encounter_generator import WEAK_MONSTERS_ACT1
from sts_py.engine.run.run_engine import RunEngine


def _make_combat(encounter_name: str) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(4452322743548530140, counter=0)
    hp_rng = MutableRNG.from_seed(4452322743548530140, counter=100)
    return CombatEngine.create(
        encounter_name=encounter_name,
        player_hp=80,
        player_max_hp=80,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        ascension=0,
        deck=["Strike", "Defend", "Strike", "Defend", "Bash"],
        relics=[],
    )


def test_official_monster_strings_load_from_jar_snapshot() -> None:
    records = load_official_monster_strings()

    assert len(records) == 72
    assert records["JawWorm"].name_zhs == "大颚虫"
    assert records["BronzeAutomaton"].name_zhs == "铜制机械人偶"
    assert records["Serpent"].java_class == "SpireGrowth"
    assert records["BanditChild"].java_class == "BanditPointy"


def test_monster_truth_canonicalizes_runtime_and_official_aliases() -> None:
    assert canonicalize_monster_id("BronzeAutomaton") == "Automaton"
    assert canonicalize_monster_id("SlaverBoss") == "Taskmaster"
    assert canonicalize_monster_id("BanditChild") == "BanditPointy"
    assert canonicalize_monster_id("Orb Walker") == "OrbWalker"
    assert canonicalize_monster_id("Serpent") == "SpireGrowth"
    assert get_monster_truth("Serpent").official_name_zhs == "塔内增生组织"


def test_summoned_monster_truth_tracks_boss_encounter_membership() -> None:
    bronze_orb = get_monster_truth("BronzeOrb")
    torch_head = get_monster_truth("TorchHead")

    assert bronze_orb is not None
    assert bronze_orb.category == "SUMMON"
    assert bronze_orb.encounters == ("Automaton",)
    assert bronze_orb.pool_buckets == ("pool:act2:boss",)

    assert torch_head is not None
    assert torch_head.category == "SUMMON"
    assert torch_head.encounters == ("Collector",)
    assert torch_head.pool_buckets == ("pool:act2:boss",)


def test_act1_weak_pool_uses_official_small_slimes_entry() -> None:
    assert [(item.name, item.weight) for item in WEAK_MONSTERS_ACT1.encounters] == [
        ("Cultist", 2.0),
        ("Jaw Worm", 2.0),
        ("2 Louse", 2.0),
        ("Small Slimes", 2.0),
    ]


def test_combat_engine_uses_explicit_official_rosters_for_key_encounters() -> None:
    slavers = _make_combat("Slavers")
    assert [monster.id for monster in slavers.state.monsters] == ["SlaverBlue", "Taskmaster", "SlaverRed"]

    bandits = _make_combat("Masked Bandits")
    assert [monster.id for monster in bandits.state.monsters] == ["BanditPointy", "BanditLeader", "BanditBear"]

    donuts = _make_combat("Donu and Deca")
    assert [monster.id for monster in donuts.state.monsters] == ["Deca", "Donu"]

    sphere = _make_combat("Mysterious Sphere")
    sphere_ids = [monster.id for monster in sphere.state.monsters]
    assert sphere_ids.count("OrbWalker") == 1
    assert len(sphere_ids) == 3
    assert set(sphere_ids).issubset({"OrbWalker", "Repulsor", "Exploder", "Spiker"})


def test_run_engine_start_combat_normalizes_official_alias_ids_without_proxy() -> None:
    engine = RunEngine.create("MONSTERTRUTH", ascension=0)

    engine.start_combat_with_monsters(["SlaverBoss", "BanditChild", "Orb Walker"])

    assert [monster.id for monster in engine.state.combat.state.monsters] == ["SlaverBoss", "BanditChild", "Orb Walker"]
    assert engine.state._last_combat_setup_debug["proxy_monster_ids"] == []
    assert engine.state._last_combat_setup_debug["alias_hits"] == [
        {"logged_id": "SlaverBoss", "runtime_id": "Taskmaster"},
        {"logged_id": "BanditChild", "runtime_id": "BanditPointy"},
        {"logged_id": "Orb Walker", "runtime_id": "OrbWalker"},
    ]
