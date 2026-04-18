from __future__ import annotations

import json
from pathlib import Path

import pytest

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.potion_effects import use_potion
from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.potions import create_potion
from sts_py.engine.content.relics import ALL_RELICS, get_relic_by_id, relic_can_spawn
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.run.run_engine import MapNode, RoomType, RunEngine, RunPhase
from sts_py.tools.relic_truth_matrix import (
    DATA_TRUTH_KINDS,
    HIGH_RISK_RUNTIME_RELIC_IDS,
    PICKUP_RNG_RELIC_IDS,
    RELIC_TRUTH_MATRIX_PATH,
    RUNTIME_TRUTH_KINDS,
    SCENARIO_NODEIDS,
    build_relic_truth_matrix,
)
from sts_py.terminal.translation_policy import get_translation_policy_entry
from sts_py.tools.wiki_audit import build_relic_source_facts
from tests.log_helpers import require_checked_in_fixture


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 60):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=6, name="Attack"))


def _split_nodeid(nodeid: str) -> tuple[Path, str]:
    path_text, function_name = nodeid.split("::", maxsplit=1)
    return Path.cwd() / path_text, function_name


def _assert_nodeid_exists(nodeid: str) -> None:
    path, function_name = _split_nodeid(nodeid)
    contents = require_checked_in_fixture(path, label=f"relic truth target {nodeid}").read_text(encoding="utf-8")
    assert f"def {function_name}(" in contents


def _make_combat(
    *,
    monster_hps: list[int] | None = None,
    energy: int = 3,
    relics: list[str] | None = None,
    card_random_counter: int = 200,
) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    card_random_rng = MutableRNG.from_seed(SEED_LONG, counter=card_random_counter)
    monsters = [DummyAttackMonster(f"Dummy{index}", hp=hp) for index, hp in enumerate(monster_hps or [60])]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=70,
        player_max_hp=70,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        card_random_rng=card_random_rng,
        deck=["Strike", "Defend", "Bash", "Inflame"],
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


def _set_hand(combat: CombatEngine, cards: list[str]) -> None:
    combat.state.card_manager.hand.cards = _bind_cards(combat, [CardInstance(card_id) for card_id in cards])


def _start_room_combat(engine: RunEngine, room_type: RoomType, encounter: str) -> None:
    engine.state.map_nodes = [MapNode(floor=1, room_type=room_type, node_id=0)]
    engine.state.current_node_idx = 0
    engine._start_combat(encounter)


def _force_win_current_combat(engine: RunEngine) -> None:
    assert engine.state.combat is not None
    for monster in engine.state.combat.state.monsters:
        monster.hp = 0
        monster.is_dying = True
    engine.end_combat()


def _sample_deck_for_type(card_type: str) -> list[str]:
    if card_type == "ATTACK":
        return ["Anger", "Defend", "ShrugItOff"]
    if card_type == "SKILL":
        return ["ShrugItOff", "Defend", "Bash"]
    if card_type == "POWER":
        return ["Inflame", "Strike", "Defend"]
    raise ValueError(f"unsupported spawn test card type: {card_type}")


def _assert_spawn_rule_truth(row: dict[str, object]) -> None:
    relic_def = ALL_RELICS[row["runtime_id"]]
    rules = dict(row["spawn_rules"] or {})
    assert rules

    good_act = int(rules.get("act_max", 2) or 2)
    good_floor = int(rules.get("floor_limit", 20) or 20)
    good_context = "shop_offer" if rules.get("disallow_reward_in_shop_room") else "reward"
    good_owned = list(rules.get("required_relics") or [])
    good_deck = _sample_deck_for_type(str(rules.get("required_deck_card_type") or "ATTACK")) if rules.get("required_deck_card_type") else ["Strike", "ShrugItOff", "Inflame"]

    assert relic_can_spawn(
        relic_def,
        floor=good_floor,
        act=good_act,
        context=good_context,
        owned_relics=good_owned,
        deck=good_deck,
    ) is True

    if "required_relics" in rules:
        assert relic_can_spawn(
            relic_def,
            floor=good_floor,
            act=good_act,
            context=good_context,
            owned_relics=[],
            deck=good_deck,
        ) is False

    if "required_deck_card_type" in rules:
        bad_deck = ["Defend", "Defend_B", "Strike"] if rules["required_deck_card_type"] == "SKILL" else ["Defend", "ShrugItOff", "Inflame"]
        if rules["required_deck_card_type"] == "ATTACK":
            bad_deck = ["Defend", "ShrugItOff", "Inflame"]
        elif rules["required_deck_card_type"] == "POWER":
            bad_deck = ["Strike", "Defend", "Bash"]
        assert relic_can_spawn(
            relic_def,
            floor=good_floor,
            act=good_act,
            context=good_context,
            owned_relics=good_owned,
            deck=bad_deck,
        ) is False

    if "act_max" in rules:
        assert relic_can_spawn(
            relic_def,
            floor=good_floor,
            act=int(rules["act_max"]) + 1,
            context=good_context,
            owned_relics=good_owned,
            deck=good_deck,
        ) is False

    if "floor_limit" in rules:
        assert relic_can_spawn(
            relic_def,
            floor=int(rules["floor_limit"]) + 1,
            act=good_act,
            context=good_context,
            owned_relics=good_owned,
            deck=good_deck,
        ) is False

    if rules.get("disallow_reward_in_shop_room"):
        assert relic_can_spawn(
            relic_def,
            floor=good_floor,
            act=good_act,
            context="reward",
            owned_relics=good_owned,
            deck=good_deck,
        ) is False

    if "exclusive_with_relics" in rules and "exclusive_relic_limit" in rules:
        owned = list(rules["exclusive_with_relics"])[: int(rules["exclusive_relic_limit"])]
        assert relic_can_spawn(
            relic_def,
            floor=good_floor,
            act=good_act,
            context=good_context,
            owned_relics=owned,
            deck=good_deck,
        ) is False


@pytest.fixture(scope="module")
def generated_matrix() -> dict[str, object]:
    return build_relic_truth_matrix(Path.cwd())


def test_relic_truth_matrix_checked_in_file_matches_generated_inventory(generated_matrix: dict[str, object]) -> None:
    path = require_checked_in_fixture(RELIC_TRUTH_MATRIX_PATH, label="relic truth matrix")
    checked_in = json.loads(path.read_text(encoding="utf-8"))

    assert checked_in == generated_matrix


def test_relic_truth_matrix_is_complete_and_decision_filled(generated_matrix: dict[str, object]) -> None:
    entities = list(generated_matrix["entities"])
    matrix_ids = {row["runtime_id"] for row in entities}

    assert len(entities) == 179
    assert matrix_ids == set(ALL_RELICS)
    assert set(generated_matrix["summary"]["data_truth_kind_counts"]).issubset(set(DATA_TRUTH_KINDS))
    assert set(generated_matrix["summary"]["runtime_truth_kind_counts"]).issubset(set(RUNTIME_TRUTH_KINDS))

    for row in entities:
        assert row["runtime_id"] in ALL_RELICS
        assert row["official_id"]
        assert row["class_name"] or row["runtime_id"] == "Circlet"
        assert row["tier"]
        assert row["character_class"]
        assert row["official_name_en"]
        assert row["official_name_zhs"]
        assert row["official_desc_en"]
        assert row["official_desc_zhs"]
        assert row["wiki_en_url"]
        assert row["wiki_cn_url"]
        assert isinstance(row["wiki_status"], str)
        assert isinstance(row["wiki_conflict_fields"], list)
        assert isinstance(row["spawn_rules"], dict)
        assert isinstance(row["rng_streams"], list)
        assert row["effect_signatures"]
        assert row["data_truth_kind"] in DATA_TRUTH_KINDS
        assert row["runtime_truth_kind"] in RUNTIME_TRUTH_KINDS
        assert row["data_proof_nodeids"]
        assert isinstance(row["runtime_proof_nodeids"], list)
        assert isinstance(row["resolution_notes"], str)


def test_relic_truth_matrix_registry_references_real_tests(generated_matrix: dict[str, object]) -> None:
    for nodeid in generated_matrix["scenario_nodeids"].values():
        _assert_nodeid_exists(str(nodeid))

    for row in generated_matrix["entities"]:
        for nodeid in row["data_proof_nodeids"]:
            _assert_nodeid_exists(str(nodeid))
        for nodeid in row["runtime_proof_nodeids"]:
            _assert_nodeid_exists(str(nodeid))


def test_relic_truth_matrix_high_risk_runtime_rows_are_not_static_only(generated_matrix: dict[str, object]) -> None:
    rows = {row["runtime_id"]: row for row in generated_matrix["entities"]}

    for relic_id in HIGH_RISK_RUNTIME_RELIC_IDS:
        row = rows[relic_id]
        assert row["runtime_truth_kind"] in {"combat_runtime", "run_runtime"}
        assert row["runtime_proof_nodeids"]


def test_relic_truth_matrix_dual_track_proofs_have_real_backing(generated_matrix: dict[str, object]) -> None:
    for row in generated_matrix["entities"]:
        data_truth_kind = str(row["data_truth_kind"])
        runtime_truth_kind = str(row["runtime_truth_kind"])

        if data_truth_kind == "pickup_rng":
            assert row["rng_streams"] or row["runtime_id"] in PICKUP_RNG_RELIC_IDS
        elif data_truth_kind == "stateful_text_ui":
            assert row["stateful_description_variants"] or row["ui_prompt_slots"]
        elif data_truth_kind == "spawn_rule_static":
            assert row["spawn_rules"]
        elif data_truth_kind == "manifest_overlay":
            assert row["truth_sources"]
        else:
            raise AssertionError(f"unexpected data truth kind {data_truth_kind}")

        if row["effect_signatures"]:
            assert runtime_truth_kind != "none"
            assert row["runtime_proof_nodeids"]
        else:
            assert runtime_truth_kind == "none"


def test_relic_truth_matrix_data_truth_rows_match_runtime_source_facts(generated_matrix: dict[str, object]) -> None:
    row_map = {row["runtime_id"]: row for row in generated_matrix["entities"]}

    for relic_id, relic_def in ALL_RELICS.items():
        row = row_map[relic_id]
        source_facts = build_relic_source_facts(relic_def)

        assert row["official_id"] == str(source_facts.get("official_id", "") or relic_id)
        assert row["class_name"] == str(source_facts.get("class_name", "") or "")
        assert row["tier"] == str(source_facts.get("tier", "") or "")
        assert row["character_class"] == str(source_facts.get("character_class", "") or "")
        assert row["official_name_en"] == str(source_facts.get("display_name_en", "") or "")
        assert row["official_name_zhs"] == str(getattr(relic_def, "name_zhs", "") or getattr(relic_def, "name", "") or "")
        assert row["official_desc_en"] == str(source_facts.get("default_description_en", "") or "")
        assert row["official_desc_zhs"] == str(source_facts.get("default_description_zhs", "") or "")
        assert row["spawn_rules"] == json.loads(json.dumps(dict(source_facts.get("spawn_rules") or {}), ensure_ascii=False))
        assert row["rng_streams"] == list(source_facts.get("rng_notes") or [])
        assert row["effect_signatures"] == list(source_facts.get("effect_signatures") or [])
        assert row["truth_sources"] == json.loads(json.dumps(dict(source_facts.get("truth_sources") or {}), ensure_ascii=False))


def test_relic_truth_matrix_wiki_status_and_resolution_notes_follow_translation_policy(generated_matrix: dict[str, object]) -> None:
    for row in generated_matrix["entities"]:
        policy = get_translation_policy_entry("relic", row["runtime_id"])
        assert policy is not None
        assert row["wiki_status"] == policy.alignment_status
        if policy.alignment_status == "wiki_missing":
            assert row["wiki_conflict_fields"] == ["page_missing"]
            assert row["resolution_notes"]
        elif policy.alignment_status == "approved_alias":
            assert "approved_alias" in row["wiki_conflict_fields"]
        else:
            assert row["wiki_conflict_fields"] == []


def test_relic_truth_matrix_stateful_text_and_ui_rows_match_manifest_truth(generated_matrix: dict[str, object]) -> None:
    entities = list(generated_matrix["entities"])
    assert generated_matrix["summary"]["stateful_text_relic_count"] == 10
    assert generated_matrix["summary"]["ui_prompt_relic_count"] == 11

    for row in entities:
        if row["data_truth_kind"] != "stateful_text_ui":
            continue
        relic_def = ALL_RELICS[row["runtime_id"]]
        assert row["stateful_description_variants"] == json.loads(json.dumps(list(relic_def.stateful_description_variants), ensure_ascii=False))
        assert row["ui_prompt_slots"] == list(relic_def.ui_prompt_slots)


def test_relic_truth_matrix_spawn_rule_static_rows_match_manifest_filters(generated_matrix: dict[str, object]) -> None:
    rows = [row for row in generated_matrix["entities"] if row["data_truth_kind"] == "spawn_rule_static"]

    assert rows
    for row in rows:
        _assert_spawn_rule_truth(dict(row))


def test_relic_truth_matrix_rng_relics_match_fixed_seed_truth() -> None:
    warpaint_engine = RunEngine.create("ALIGN_WARPAINT", ascension=0)
    warpaint_engine.state.deck = ["Defend", "ShrugItOff", "Bash", "Strike"]
    warpaint_engine._acquire_relic("WarPaint", record_pending=False)
    assert warpaint_engine.state.deck == ["Defend+", "ShrugItOff+", "Bash", "Strike"]

    whetstone_engine = RunEngine.create("ALIGN_WHETSTONE", ascension=0)
    whetstone_engine.state.deck = ["Strike", "Bash", "Defend", "ShrugItOff"]
    whetstone_engine._acquire_relic("Whetstone", record_pending=False)
    assert whetstone_engine.state.deck == ["Strike+", "Bash+", "Defend", "ShrugItOff"]

    astrolabe_engine = RunEngine.create("ALIGN_ASTROLABE", ascension=0)
    astrolabe_engine.state.deck = ["Strike", "Defend", "Bash", "ShrugItOff"]
    astrolabe_engine._acquire_relic("Astrolabe", record_pending=False)
    assert astrolabe_engine.state.deck == ["Havoc+", "ShrugItOff+", "Armaments+", "ShrugItOff"]

    tiny_house_engine = RunEngine.create("ALIGN_TINYHOUSE", ascension=0)
    tiny_house_engine.state.deck = ["Strike", "Defend", "Bash", "ShrugItOff"]
    tiny_house_engine.state.player_gold = 0
    tiny_house_engine.state.player_hp = 50
    tiny_house_engine.state.player_max_hp = 70
    tiny_house_engine._acquire_relic("TinyHouse", record_pending=False)
    assert tiny_house_engine.state.deck == ["Strike", "Defend", "Bash", "ShrugItOff+"]
    assert tiny_house_engine.state.player_gold == 50
    assert tiny_house_engine.state.player_max_hp == 75
    assert tiny_house_engine.state.player_hp == 75

    matryoshka_engine = RunEngine.create("TRUTH_MATRYOSHKA", ascension=0)
    matryoshka_engine.state.floor = 1
    matryoshka_engine.state.relics.append("Matryoshka")
    matryoshka_engine.state.relic_counters["Matryoshka"] = 2
    matryoshka_engine._enter_treasure()
    assert matryoshka_engine.state.pending_chest_relic_choices == ["Pantograph", "HornCleat"]
    assert matryoshka_engine.state.pending_treasure_relic == "HornCleat"
    assert matryoshka_engine.state.relic_counters["Matryoshka"] == 1
    matryoshka_engine.state.phase = RunPhase.MAP
    matryoshka_engine.state.floor = 2
    matryoshka_engine._enter_treasure()
    assert matryoshka_engine.state.pending_chest_relic_choices == ["RedSkull", "StrikeDummy"]
    assert matryoshka_engine.state.pending_treasure_relic == "StrikeDummy"
    assert matryoshka_engine.state.relic_counters["Matryoshka"] == 0

    mummified_hand_combat = _make_combat(monster_hps=[40], relics=["MummifiedHand"])
    mummified_hand_combat.state.card_manager.hand.cards = _bind_cards(
        mummified_hand_combat,
        [CardInstance("Inflame"), CardInstance("Strike"), CardInstance("Bash"), CardInstance("Defend")],
    )
    assert mummified_hand_combat.play_card(0)
    hand_by_id = {card.card_id: card for card in mummified_hand_combat.state.card_manager.hand.cards}
    assert hand_by_id["Bash"].cost_for_turn == 0
    assert hand_by_id["Bash"].is_cost_modified_for_turn is True
    assert hand_by_id["Strike"].cost_for_turn == 1
    assert hand_by_id["Defend"].cost_for_turn == 1


def test_relic_truth_matrix_question_card_busted_crown_and_prayer_wheel_stack() -> None:
    engine = RunEngine.create("TRUTH_QCBCPW", ascension=0)
    engine.state.relics.extend(["QuestionCard", "BustedCrown", "PrayerWheel"])
    _start_room_combat(engine, RoomType.MONSTER, "Cultist")

    _force_win_current_combat(engine)

    assert len(engine.state.pending_card_reward_cards) == 3


def test_relic_truth_matrix_black_star_grants_double_elite_relic_reward() -> None:
    engine = RunEngine.create("TRUTH_BLACKSTAR", ascension=0)
    engine.state.relics.append("BlackStar")
    _start_room_combat(engine, RoomType.ELITE, "Gremlin Nob")

    _force_win_current_combat(engine)

    pending = engine.get_pending_reward_state()
    assert pending["relic"] == pending["relics"][0]
    assert len(pending["relics"]) == 2
    assert len({*pending["relics"]}) == 2


def test_relic_truth_matrix_cursed_key_and_matryoshka_preserve_bonus_relics_when_taking_sapphire_key() -> None:
    engine = RunEngine.create("TRUTH_CURSED_MATRY", ascension=0)
    engine.state.relics.extend(["CursedKey", "Matryoshka"])
    engine.state.relic_counters["Matryoshka"] = 2
    deck_before = len(engine.state.deck)

    engine._enter_treasure()

    first_rewards = list(engine.state.pending_chest_relic_choices)
    main_relic = engine.state.pending_treasure_relic
    assert len(engine.state.deck) == deck_before + 1
    assert len(first_rewards) == 2
    assert main_relic == first_rewards[-1]
    assert engine.state.relic_counters["Matryoshka"] == 1

    result = engine.take_sapphire_key()

    assert result["success"] is True
    assert len(engine.state.pending_chest_relic_choices) == 1
    assert engine.state.pending_chest_relic_choices[0] != main_relic

    take_result = engine.take_treasure_relic(0)

    assert take_result["success"] is True
    assert engine.state.phase == RunPhase.MAP
    assert engine.state.treasure_rooms[-1]["skipped_main_relic_id"] == main_relic
    assert engine.state.treasure_rooms[-1]["obtained_relic_ids"] == [take_result["relic_id"]]


def test_relic_truth_matrix_sozu_blocks_potion_gain_from_relic_rewards() -> None:
    engine = RunEngine.create("TRUTH_SOZU_TINYHOUSE", ascension=0)
    before = list(engine.state.potions)
    engine.state.relics.append("Sozu")

    engine._acquire_relic("TinyHouse", record_pending=False)

    assert engine.state.potions == before


def test_relic_truth_matrix_cross_relic_callbacks_and_modifiers_remain_live() -> None:
    sacred_bark_combat = _make_combat(monster_hps=[40], relics=["SacredBark"])
    block_potion = create_potion("BlockPotion")
    assert block_potion is not None
    use_potion(block_potion, sacred_bark_combat.state)
    assert sacred_bark_combat.state.player.block == 24

    magic_flower_engine = RunEngine.create("TRUTH_MAGICFLOWER", ascension=0)
    magic_flower_engine.state.relics.append("MagicFlower")
    _start_room_combat(magic_flower_engine, RoomType.MONSTER, "Cultist")
    assert magic_flower_engine.state.combat is not None
    magic_flower_engine.state.combat.state.player.hp = 40
    magic_flower_engine.state.player_hp = 40
    _force_win_current_combat(magic_flower_engine)
    assert magic_flower_engine.state.player_hp == 49

    lizard_tail_combat = CombatEngine.create(
        encounter_name="Cultist",
        player_hp=80,
        player_max_hp=80,
        ai_rng=MutableRNG.from_seed(12345, counter=50),
        hp_rng=MutableRNG.from_seed(67890, counter=100),
        relics=["LizardTail", "MagicFlower"],
    )
    lizard_tail_combat.state.player.hp = 1
    lizard_tail_combat._deal_damage_to_player(2)
    assert lizard_tail_combat.state.player.hp == 60

    snecko_skull_combat = _make_combat(monster_hps=[30], relics=["SneckoSkull"])
    _set_hand(snecko_skull_combat, ["DeadlyPoison", "PoisonedStab"])
    assert snecko_skull_combat.play_card(0, 0)
    assert snecko_skull_combat.state.monsters[0].get_power_amount("Poison") == 6
    assert snecko_skull_combat.play_card(0, 0)
    assert snecko_skull_combat.state.monsters[0].get_power_amount("Poison") == 10

    specimen_combat = _make_combat(monster_hps=[6, 20], relics=["TheSpecimen", "SneckoSkull"])
    _set_hand(specimen_combat, ["DeadlyPoison"])
    assert specimen_combat.play_card(0, 0)
    specimen_combat.end_player_turn()
    assert specimen_combat.state.monsters[0].is_dead()
    assert specimen_combat.state.monsters[1].get_power_amount("Poison") > 0

    paper_crane_combat = _make_combat(monster_hps=[50], relics=["PaperCrane"])
    paper_crane_combat.state.player.strength = 10
    weak = create_power("Weak", 1, "player")
    assert weak is not None
    paper_crane_combat.state.player.powers.add_power(weak)
    _set_hand(paper_crane_combat, ["Strike"])
    initial_hp = paper_crane_combat.state.monsters[0].hp
    assert paper_crane_combat.play_card(0, 0)
    assert initial_hp - paper_crane_combat.state.monsters[0].hp == 9

    paper_frog_combat = _make_combat(monster_hps=[50], relics=["PaperFrog"])
    paper_frog_combat.state.player.strength = 10
    vulnerable = create_power("Vulnerable", 1, "monster")
    assert vulnerable is not None
    paper_frog_combat.state.monsters[0].powers.add_power(vulnerable)
    _set_hand(paper_frog_combat, ["Strike"])
    initial_hp = paper_frog_combat.state.monsters[0].hp
    assert paper_frog_combat.play_card(0, 0)
    assert initial_hp - paper_frog_combat.state.monsters[0].hp == 28
