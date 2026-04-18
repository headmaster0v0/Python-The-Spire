from __future__ import annotations

import json
from pathlib import Path

import pytest

from sts_py.engine.combat.card_effects import get_card_effects
from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.stance import StanceType
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import ALL_CARD_DEFS
from sts_py.engine.content.official_card_strings import OFFICIAL_CARD_TRANSLATION_SOURCE, get_official_card_strings
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.terminal.translation_policy import get_translation_policy_entry
from sts_py.tools import wiki_audit
from sts_py.tools.card_truth_matrix import (
    CARD_DATA_TRUTH_KINDS,
    CARD_RUNTIME_TRUTH_KINDS,
    CARD_TRUTH_MATRIX_PATH,
    HIGH_RISK_CARD_IDS,
    build_card_truth_matrix,
)
from tests.log_helpers import require_checked_in_fixture


SEED_LONG = 4452322743548530140


class DummyAttackMonster(MonsterBase):
    def __init__(self, monster_id: str, *, hp: int = 80, attack_damage: int = 0):
        super().__init__(id=monster_id, name=monster_id, hp=hp, max_hp=hp)
        self.attack_damage = attack_damage

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=self.attack_damage, name="Attack"))


def _split_nodeid(nodeid: str) -> tuple[Path, str]:
    path_text, function_name = nodeid.split("::", maxsplit=1)
    return Path.cwd() / path_text, function_name


def _assert_nodeid_exists(nodeid: str) -> None:
    path, function_name = _split_nodeid(nodeid)
    contents = require_checked_in_fixture(path, label=f"card truth target {nodeid}").read_text(encoding="utf-8")
    assert f"def {function_name}(" in contents


def _make_combat(
    *,
    hand_ids: list[str] | None = None,
    draw_ids: list[str] | None = None,
    discard_ids: list[str] | None = None,
    monster_hps: list[int] | None = None,
    attack_damage: int = 0,
    energy: int = 3,
) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    monsters = [
        DummyAttackMonster(f"Dummy{index}", hp=hp, attack_damage=attack_damage)
        for index, hp in enumerate(monster_hps or [80])
    ]
    combat = CombatEngine.create_with_monsters(
        monsters=monsters,
        player_hp=72,
        player_max_hp=72,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=draw_ids or ["Strike", "Defend", "Bash", "Vigilance", "Eruption"],
        relics=[],
    )
    combat.state.player.max_energy = energy
    combat.state.player.energy = energy
    combat.state.card_manager.set_max_energy(energy)
    combat.state.card_manager.set_energy(energy)

    def _bind(cards: list[str]) -> list[CardInstance]:
        instances = [CardInstance(card_id) for card_id in cards]
        for card in instances:
            card._combat_state = combat.state
        return instances

    combat.state.card_manager.hand.cards = _bind(hand_ids or [])
    combat.state.card_manager.draw_pile.cards = _bind(draw_ids or [])
    combat.state.card_manager.discard_pile.cards = _bind(discard_ids or [])
    combat.state.card_manager.exhaust_pile.cards = []
    return combat


@pytest.fixture(scope="module")
def generated_matrix() -> dict[str, object]:
    return build_card_truth_matrix(Path.cwd())


def test_card_truth_matrix_checked_in_file_matches_generated_inventory(generated_matrix: dict[str, object]) -> None:
    path = require_checked_in_fixture(CARD_TRUTH_MATRIX_PATH, label="card truth matrix")
    checked_in = json.loads(path.read_text(encoding="utf-8"))

    assert checked_in == generated_matrix


def test_card_truth_matrix_is_complete_and_decision_filled(generated_matrix: dict[str, object]) -> None:
    rows = list(generated_matrix["entities"])
    rows_by_id = {row["runtime_id"]: row for row in rows}

    assert len(rows) == 368
    assert set(rows_by_id) == set(ALL_CARD_DEFS)
    assert generated_matrix["summary"]["missing_in_runtime"] == 0
    assert set(generated_matrix["summary"]["data_truth_kind_counts"]).issubset(set(CARD_DATA_TRUTH_KINDS))
    assert set(generated_matrix["summary"]["runtime_truth_kind_counts"]).issubset(set(CARD_RUNTIME_TRUTH_KINDS))
    assert sorted(generated_matrix["high_risk_card_ids"]) == sorted(HIGH_RISK_CARD_IDS)

    for row in rows:
        assert row["official_key"]
        assert row["java_class"]
        assert row["java_path"]
        assert row["official_name_en"]
        assert row["official_name_zhs"]
        assert row["official_desc_en"]
        assert row["official_desc_zhs"]
        assert row["translation_source"] == OFFICIAL_CARD_TRANSLATION_SOURCE
        assert row["translation_status"] == "exact_match"
        assert row["data_truth_kind"] in CARD_DATA_TRUTH_KINDS
        assert row["runtime_truth_kind"] in CARD_RUNTIME_TRUTH_KINDS
        assert row["data_proof_nodeids"]
        assert row["family_ids"]
        assert row["wiki_en_url"]
        assert row["wiki_cn_url"]
        assert isinstance(row["wiki_conflict_fields"], list)
        assert isinstance(row["truth_sources"], dict)
        assert isinstance(row["risk_flags"], list)
        if row["runtime_truth_kind"] != "none":
            assert row["runtime_proof_nodeids"]

    assert rows_by_id["Bullseye"]["java_class"] == "LockOn"
    assert rows_by_id["Bullseye"]["official_key"] == "Lockon"
    assert rows_by_id["Burn+"]["official_key"] == "Burn"
    assert rows_by_id["Burn+"]["official_upgrade_desc_zhs"]
    assert rows_by_id["RitualDagger"]["data_truth_kind"] == "runtime_variant"
    assert rows_by_id["Expunger"]["data_truth_kind"] == "generated_variant"
    assert "misc_stateful" in rows_by_id["GeneticAlgorithm"]["risk_flags"]
    assert "x_cost" in rows_by_id["Whirlwind"]["risk_flags"]
    assert "draw_hook" in rows_by_id["DeusExMachina"]["risk_flags"]
    assert "discard_hook" in rows_by_id["Reflex"]["risk_flags"]
    assert "retain_hook" in rows_by_id["Perseverance"]["risk_flags"]
    assert "stance_hook" in rows_by_id["FlurryOfBlows"]["risk_flags"]
    assert "run_hook" in rows_by_id["Parasite"]["risk_flags"]
    assert "target_gate" in rows_by_id["SignatureMove"]["risk_flags"]
    assert "upgrade_toggle" in rows_by_id["Blasphemy"]["risk_flags"]


def test_card_truth_matrix_registry_references_real_tests(generated_matrix: dict[str, object]) -> None:
    for nodeid in generated_matrix["scenario_nodeids"].values():
        _assert_nodeid_exists(str(nodeid))

    for nodeid in generated_matrix["family_tests"].values():
        _assert_nodeid_exists(str(nodeid))

    for nodeid in generated_matrix["dedicated_tests"].values():
        _assert_nodeid_exists(str(nodeid))

    for row in generated_matrix["entities"]:
        for nodeid in row["data_proof_nodeids"]:
            _assert_nodeid_exists(str(nodeid))
        for nodeid in row["runtime_proof_nodeids"]:
            _assert_nodeid_exists(str(nodeid))


def test_card_truth_matrix_high_risk_cards_have_dedicated_runtime_proof(generated_matrix: dict[str, object]) -> None:
    rows = {row["runtime_id"]: row for row in generated_matrix["entities"]}

    for card_id in HIGH_RISK_CARD_IDS:
        row = rows[card_id]
        assert row["runtime_truth_kind"] in {"dispatch_runtime", "hook_runtime", "run_runtime"}
        dedicated = generated_matrix["dedicated_tests"][f"card:{card_id}"]
        assert dedicated in row["runtime_proof_nodeids"]


def test_card_truth_matrix_data_rows_match_runtime_source_and_official_truth(generated_matrix: dict[str, object]) -> None:
    row_map = {row["runtime_id"]: row for row in generated_matrix["entities"]}
    repo_root = Path.cwd()

    for card_id in sorted(ALL_CARD_DEFS):
        row = row_map[card_id]
        runtime_facts = wiki_audit.build_card_runtime_facts(card_id)
        java_facts = wiki_audit.build_card_java_facts(repo_root, card_id)
        official = get_official_card_strings(card_id)

        assert row["official_key"] == str(getattr(official, "official_key", "") or java_facts.get("official_key", ""))
        assert row["java_class"] == str(java_facts.get("java_class", "") or "")
        assert row["java_path"] == str(java_facts.get("java_path", "") or "")
        assert row["type"] == runtime_facts["type"]
        assert row["rarity"] == runtime_facts["rarity"]
        assert row["cost"] == runtime_facts["cost"]
        assert row["target_required"] == runtime_facts["target_required"]
        assert row["damage"] == runtime_facts["damage"]
        assert row["block"] == runtime_facts["block"]
        assert row["magic_number"] == runtime_facts["magic_number"]
        assert row["exhaust"] == runtime_facts["exhaust"]
        assert row["ethereal"] == runtime_facts["ethereal"]
        assert row["retain"] == runtime_facts["retain"]
        assert row["innate"] == runtime_facts["innate"]
        assert row["official_name_en"] == str(getattr(official, "name_en", "") or "")
        assert row["official_name_zhs"] == str(getattr(official, "name_zhs", "") or "")
        assert row["official_desc_en"] == str(getattr(official, "description_en", "") or "")
        assert row["official_desc_zhs"] == str(getattr(official, "description_zhs", "") or "")
        assert row["official_upgrade_desc_en"] == str(getattr(official, "upgrade_description_en", "") or "")
        assert row["official_upgrade_desc_zhs"] == str(getattr(official, "upgrade_description_zhs", "") or "")
        assert row["translation_source"] == str(runtime_facts.get("translation_source", "") or "")
        assert row["description_source"] == str(runtime_facts.get("description_source", "") or "")
        assert row["truth_sources"]["mechanics_source"] == str(java_facts.get("source_kind", "") or "decompiled_java_card")
        assert row["truth_sources"]["java_source_path"] == str(java_facts.get("java_path", "") or "")
        assert row["truth_sources"]["runtime_source"] == str(runtime_facts.get("source_kind", "") or "runtime_card_def")
        assert row["truth_sources"]["official_translation_source"] == str(runtime_facts.get("translation_source", "") or "")
        assert row["truth_sources"]["official_description_source"] == str(runtime_facts.get("description_source", "") or "")


def test_card_truth_matrix_wiki_status_and_resolution_notes_follow_translation_policy(generated_matrix: dict[str, object]) -> None:
    for row in generated_matrix["entities"]:
        policy = get_translation_policy_entry("card", row["runtime_id"])
        if policy is None:
            assert row["wiki_status"] == row["translation_status"]
            assert row["truth_sources"]["translation_policy_alignment_status"] == ""
            assert row["wiki_conflict_fields"] == []
            continue

        assert row["wiki_status"] == policy.alignment_status
        assert row["truth_sources"]["translation_policy_alignment_status"] == policy.alignment_status
        if policy.alignment_status == "wiki_missing":
            assert row["wiki_conflict_fields"] == ["page_missing"]
            assert row["resolution_notes"]
        elif policy.alignment_status == "approved_alias":
            assert "approved_alias" in row["wiki_conflict_fields"]
        else:
            assert row["wiki_conflict_fields"] == []


@pytest.mark.parametrize(
    ("card_id", "expected_effects"),
    [
        ("BowlingBash", ["BowlingBashEffect"]),
        ("Brilliance", ["DealDamageEffect"]),
        ("Collect", ["CollectEffect"]),
        ("Conclude", ["DealDamageAllEffect", "EndTurnEffect"]),
        ("Consecrate", ["DealDamageAllEffect"]),
        ("Crescendo", ["ChangeStanceEffect"]),
        ("CrushJoints", ["DealDamageEffect", "ConditionalLastCardTypeApplyMonsterPowerEffect"]),
        ("Discipline", ["ApplyPowerEffect"]),
        ("EmptyBody", ["GainBlockEffect", "ChangeStanceEffect"]),
        ("EmptyFist", ["DealDamageEffect", "ChangeStanceEffect"]),
        ("EmptyMind", ["DrawCardsEffect", "ChangeStanceEffect"]),
        ("Establishment", ["ApplyPowerEffect"]),
        ("Fasting", ["ApplyPowerEffect", "ApplyPowerEffect", "ApplyPowerEffect"]),
        ("FearNoEvil", ["DealDamageEffect", "ConditionalAttackIntentChangeStanceEffect"]),
        ("FlurryOfBlows", ["DealDamageEffect"]),
        ("FlyingSleeves", ["DealDamageRepeatedEffect"]),
        ("FollowUp", ["DealDamageEffect", "ConditionalLastCardTypeGainEnergyEffect"]),
        ("ForeignInfluence", ["ForeignInfluenceEffect"]),
        ("Halt", ["HaltEffect"]),
        ("Indignation", ["IndignationEffect"]),
        ("Judgement", ["JudgementEffect"]),
        ("LessonLearned", ["LessonLearnedEffect"]),
        ("MentalFortress", ["ApplyPowerEffect"]),
        ("Perseverance", ["GainBlockEffect"]),
        ("PressurePoints", ["PressurePointsEffect"]),
        ("Protect", ["GainBlockEffect"]),
        ("Ragnarok", ["DealDamageRandomEnemyRepeatedEffect"]),
        ("Sanctity", ["GainBlockEffect", "ConditionalLastCardTypeDrawEffect"]),
        ("SandsOfTime", ["DealDamageEffect"]),
        ("SashWhip", ["DealDamageEffect", "ConditionalLastCardTypeApplyMonsterPowerEffect"]),
        ("SignatureMove", ["DealDamageEffect"]),
        ("SimmeringFury", ["ApplyPowerEffect"]),
        ("Slimed", ["NoOpEffect"]),
        ("SpiritShield", ["SpiritShieldEffect"]),
        ("Swivel", ["GainBlockEffect", "ApplyPowerEffect"]),
        ("TalkToTheHand", ["DealDamageEffect", "ApplyPowerEffect"]),
        ("Tantrum", ["DealDamageRepeatedEffect", "ChangeStanceEffect"]),
        ("Tranquility", ["ChangeStanceEffect"]),
        ("Unraveling", ["UnravelingEffect"]),
        ("WaveOfTheHand", ["ApplyPowerEffect"]),
        ("WheelKick", ["DealDamageEffect", "DrawCardsEffect"]),
        ("WindmillStrike", ["DealDamageEffect"]),
        ("Worship", ["GainMantraEffect"]),
        ("WreathOfFlame", ["ApplyPowerEffect"]),
        ("Pride", ["NoOpEffect"]),
    ],
)
def test_truth_closure_cards_have_explicit_runtime_effect_signatures(card_id: str, expected_effects: list[str]) -> None:
    effects = get_card_effects(CardInstance(card_id), 0) or get_card_effects(CardInstance(card_id), None)

    assert [type(effect).__name__ for effect in effects] == expected_effects


def test_retain_hook_cards_and_establishment_apply_real_runtime_mutations() -> None:
    combat = _make_combat(hand_ids=["Establishment", "Perseverance", "WindmillStrike", "SandsOfTime"], draw_ids=[])

    assert combat.play_card(0)
    combat.state.card_manager.end_turn()

    retained = {card.card_id: card for card in combat.state.card_manager.hand.cards}
    assert retained["Perseverance"].base_block == 7
    assert retained["WindmillStrike"].base_damage == 11
    assert retained["SandsOfTime"].cost_for_turn == 2


def test_follow_up_sanctity_crush_joints_sash_whip_and_signature_move_conditions_hold() -> None:
    combat = _make_combat(hand_ids=["Strike", "FollowUp", "Sanctity", "CrushJoints", "SashWhip"], draw_ids=["Defend", "Defend"])

    assert combat.play_card(0, 0)
    assert combat.play_card(0, 0)
    assert combat.state.player.energy == 2

    combat.state._last_card_played_type = "SKILL"
    start_hand_size = combat.state.card_manager.get_hand_size()
    assert combat.play_card(0)
    assert combat.state.card_manager.get_hand_size() > start_hand_size - 1

    combat.state._last_card_played_type = "SKILL"
    assert combat.play_card(0, 0)
    assert combat.state.monsters[0].vulnerable == 1

    combat.state._last_card_played_type = "ATTACK"
    combat.state.player.energy = 5
    combat.state.card_manager.set_energy(5)
    assert combat.play_card(0, 0)
    assert combat.state.monsters[0].weak == 1

    signature_move_only = CardInstance("SignatureMove")
    signature_move_only._combat_state = combat.state
    combat.state.card_manager.hand.cards = [signature_move_only]
    assert signature_move_only.can_use(3) is True

    signature_move_blocked = CardInstance("SignatureMove")
    other_attack = CardInstance("Strike")
    signature_move_blocked._combat_state = combat.state
    other_attack._combat_state = combat.state
    combat.state.card_manager.hand.cards = [signature_move_blocked, other_attack]
    assert signature_move_blocked.can_use(3) is False


def test_collect_discipline_and_simmering_fury_delayed_turn_hooks_fire_for_real() -> None:
    combat = _make_combat(hand_ids=["Collect", "SimmeringFury"], draw_ids=["Strike", "Defend"], energy=4)

    assert combat.play_card(1)
    assert combat.play_card(0)
    combat.end_player_turn()

    hand_ids = [card.card_id for card in combat.state.card_manager.hand.cards]
    assert "Miracle" in hand_ids
    assert combat.state.player.stance is not None
    assert combat.state.player.stance.stance_type == StanceType.WRATH

    discipline = _make_combat(
        hand_ids=["Discipline"],
        draw_ids=["Strike", "Defend", "Bash", "Vigilance", "Eruption", "Strike", "Defend"],
        energy=4,
    )
    assert discipline.play_card(0)
    discipline.end_player_turn()
    assert discipline.state.card_manager.get_hand_size() >= 6


def test_pressure_points_talk_to_the_hand_wave_of_the_hand_and_wreath_of_flame_hooks_fire() -> None:
    combat = _make_combat(
        hand_ids=["PressurePoints", "TalkToTheHand", "WaveOfTheHand", "WreathOfFlame", "Strike", "Defend"],
        draw_ids=[],
        monster_hps=[60, 60],
        energy=6,
    )

    assert combat.play_card(0, 0)
    assert combat.state.monsters[0].hp == 52

    assert combat.play_card(0, 0)
    assert combat.play_card(0)
    assert combat.play_card(0)
    before_hp = combat.state.monsters[0].hp
    assert combat.play_card(0, 0)
    assert combat.state.monsters[0].hp < before_hp
    assert combat.state.player.block >= 2

    defend_index = next(index for index, card in enumerate(combat.state.card_manager.hand.cards) if card.card_id == "Defend")
    assert combat.play_card(defend_index)
    assert combat.state.monsters[0].weak >= 1
    assert combat.state.monsters[1].weak >= 1


def test_foreign_influence_and_unraveling_use_real_choice_and_autoplay_paths() -> None:
    combat = _make_combat(hand_ids=["ForeignInfluence"], draw_ids=[])

    assert combat.play_card(0)
    pending = combat.get_pending_choices()
    assert len(pending) == 3
    assert combat.choose_combat_option(0) is True
    assert any(card.card_type.value == "ATTACK" for card in combat.state.card_manager.hand.cards)

    autoplay = _make_combat(hand_ids=["Unraveling", "Defend", "Strike"], draw_ids=[], energy=2, monster_hps=[40])
    assert autoplay.play_card(0)
    assert autoplay.state.player.block >= 5
    assert autoplay.state.monsters[0].hp < 40


def test_judgement_lesson_learned_tantrum_and_flurry_of_blows_change_real_combat_state() -> None:
    combat = _make_combat(hand_ids=["Judgement"], draw_ids=[], monster_hps=[20], energy=5)
    assert combat.play_card(0, 0)
    assert combat.state.monsters[0].hp == 0

    combat = _make_combat(hand_ids=["LessonLearned"], draw_ids=["Defend"], monster_hps=[10], energy=5)
    assert combat.play_card(0, 0)
    lesson_card = combat.state.card_manager.exhaust_pile.cards[0]
    assert getattr(lesson_card, "_upgraded_card_from_lesson_learned", "")

    combat = _make_combat(hand_ids=["Tantrum"], discard_ids=["FlurryOfBlows"], monster_hps=[40], energy=5)
    assert combat.play_card(0, 0)
    assert combat.state.player.stance is not None
    assert combat.state.player.stance.stance_type == StanceType.WRATH
    assert any(card.card_id == "Tantrum" for card in combat.state.card_manager.draw_pile.cards)
    assert any(card.card_id == "FlurryOfBlows" for card in combat.state.card_manager.hand.cards)


def test_fasting_mental_fortress_and_spirit_shield_use_real_runtime_state() -> None:
    combat = _make_combat(hand_ids=["Fasting", "MentalFortress", "SpiritShield", "Eruption"], draw_ids=[], energy=5)

    assert combat.play_card(0)
    assert combat.state.player.strength == 3
    assert combat.state.player.dexterity == 3

    assert combat.play_card(0)
    assert combat.play_card(1, 0)
    assert combat.state.player.stance is not None
    assert combat.state.player.stance.stance_type == StanceType.WRATH
    assert combat.state.player.block >= 4

    combat.end_player_turn()
    assert combat.state.player.energy == 4
