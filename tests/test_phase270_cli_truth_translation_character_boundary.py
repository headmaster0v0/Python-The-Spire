from __future__ import annotations

from pathlib import Path

import pytest

from sts_py.engine.combat.potion_effects import get_random_potion_by_rarity
from sts_py.engine.combat.powers import gain_mantra
from sts_py.engine.content.potions import (
    CharacterClass,
    get_common_potions,
    get_rare_potions,
    get_uncommon_potions,
)
from sts_py.engine.content.pool_order import build_reward_pools
from sts_py.engine.content.relics import get_relic_by_id, get_starter_relic_pool
from sts_py.engine.run.run_engine import RunEngine
from sts_py.terminal import render
from sts_py.tools.fidelity_audit import run_fidelity_audit


def _allowed_potion_classes(character_class: str) -> set[CharacterClass]:
    return {CharacterClass.UNIVERSAL, CharacterClass[character_class]}


def _assert_potions_match_character(character_class: str, potion_ids: list[str]) -> None:
    allowed = _allowed_potion_classes(character_class)
    all_potions = {
        potion.potion_id: potion
        for potion in (
            get_common_potions(character_class)
            + get_uncommon_potions(character_class)
            + get_rare_potions(character_class)
        )
    }
    assert potion_ids
    assert all_potions
    for potion_id in potion_ids:
        potion = all_potions.get(potion_id)
        assert potion is not None
        assert potion.character_class in allowed


def _assert_relic_matches_character(character_class: str, relic_id: str) -> None:
    relic_def = get_relic_by_id(relic_id)
    assert relic_def is not None
    assert getattr(relic_def, "character_class", "UNIVERSAL") in {"UNIVERSAL", character_class}


@pytest.mark.parametrize(
    ("character_class", "must_include", "must_exclude"),
    [
        ("IRONCLAD", "BloodPotion", {"PoisonPotion", "FocusPotion", "BottledMiracle", "StancePotion"}),
        ("SILENT", "PoisonPotion", {"BloodPotion", "FocusPotion", "BottledMiracle", "StancePotion"}),
        ("DEFECT", "FocusPotion", {"BloodPotion", "PoisonPotion", "BottledMiracle", "StancePotion"}),
        ("WATCHER", "BottledMiracle", {"BloodPotion", "PoisonPotion", "FocusPotion"}),
    ],
)
def test_phase270_potion_generation_is_character_scoped_across_entry_points(
    character_class: str,
    must_include: str,
    must_exclude: set[str],
) -> None:
    pool = get_common_potions(character_class) + get_uncommon_potions(character_class) + get_rare_potions(character_class)
    pool_ids = {potion.potion_id for potion in pool}

    assert must_include in pool_ids
    assert must_exclude.isdisjoint(pool_ids)

    engine = RunEngine.create(f"PHASE270POTION{character_class}", ascension=0, character_class=character_class)
    neow_potions = engine._grant_neow_potions(3)
    _assert_potions_match_character(character_class, neow_potions)

    engine = RunEngine.create(f"PHASE270SHOPPOTION{character_class}", ascension=0, character_class=character_class)
    engine._enter_shop()
    shop = engine.get_shop()
    assert shop is not None
    _assert_potions_match_character(character_class, [item.item_id for item in shop.shop.potions])

    for rarity in ("COMMON", "UNCOMMON", "RARE"):
        potion = get_random_potion_by_rarity(rarity, character_class)
        assert potion is not None
        assert potion.character_class in _allowed_potion_classes(character_class)


@pytest.mark.parametrize("character_class", ["IRONCLAD", "SILENT", "DEFECT", "WATCHER"])
def test_phase270_relic_and_colored_card_offers_respect_character_boundaries(character_class: str) -> None:
    engine = RunEngine.create(f"PHASE270SURFACE{character_class}", ascension=0, character_class=character_class)

    starter_relics = get_starter_relic_pool(character_class)
    assert [relic.id for relic in starter_relics] == engine.state.relics
    for relic_id in engine.state.relics:
        _assert_relic_matches_character(character_class, relic_id)

    engine._enter_shop()
    shop = engine.get_shop()
    assert shop is not None

    reward_pool_ids = {card.id for pool in build_reward_pools(character_class).values() for card in pool}
    colored_card_ids = [item.item_id for item in shop.shop.colored_cards]
    assert colored_card_ids
    assert set(colored_card_ids).issubset(reward_pool_ids)

    for relic_id in [item.item_id for item in shop.shop.relics]:
        _assert_relic_matches_character(character_class, relic_id)

    boss_relic_choices = engine._generate_boss_relic_choices(5)
    assert boss_relic_choices
    for relic_id in boss_relic_choices:
        _assert_relic_matches_character(character_class, relic_id)

    reward_engine = RunEngine.create(f"PHASE270REWARD{character_class}", ascension=0, character_class=character_class)
    reward_engine._add_card_reward(current_room=None, is_event_combat=False)
    assert reward_engine.state.pending_card_reward_cards
    assert set(reward_engine.state.pending_card_reward_cards).issubset(reward_pool_ids)


def test_phase270_status_surfaces_are_character_aware() -> None:
    ironclad = RunEngine.create("PHASE270IRONCLAD", ascension=0, character_class="IRONCLAD")
    ironclad.start_combat_with_monsters(["FungiBeast"])
    ironclad_lines = render.render_status_detail_lines(ironclad)
    ironclad_header = render.render_combat_player_lines(ironclad.state.combat.state.player)
    ironclad_joined = "\n".join(ironclad_lines + ironclad_header)
    assert "姿态" not in ironclad_joined
    assert "集中" not in ironclad_joined
    assert "充能球" not in ironclad_joined

    defect = RunEngine.create("PHASE270DEFECT", ascension=0, character_class="DEFECT")
    defect.start_combat_with_monsters(["FungiBeast"])
    defect_lines = render.render_status_detail_lines(defect)
    defect_header = render.render_combat_player_lines(defect.state.combat.state.player)
    defect_joined = "\n".join(defect_lines + defect_header)
    assert "姿态" not in defect_joined
    assert "集中 0" in defect_joined
    assert "充能球:" in defect_joined

    watcher = RunEngine.create("PHASE270WATCHER", ascension=0, character_class="WATCHER")
    watcher.start_combat_with_monsters(["FungiBeast"])
    gain_mantra(watcher.state.combat.state.player, 2)
    watcher_lines = render.render_status_detail_lines(watcher)
    watcher_header = render.render_combat_player_lines(watcher.state.combat.state.player)
    watcher_joined = "\n".join(watcher_lines + watcher_header)
    assert "姿态: 中立" in watcher_joined
    assert "真言 2" in watcher_joined
    assert "充能球:" not in watcher_joined
    assert "集中" not in watcher_joined


def test_phase270_translation_truth_gate_is_green() -> None:
    bundle = run_fidelity_audit(Path.cwd())
    summary = bundle["summary"]
    translation_summary = bundle["translation_truth_audit"]["summary"]

    assert summary["translation_truth_blocker_count"] == 0
    assert translation_summary["blocker_count"] == 0
    assert translation_summary["exact_match_count"] > 0
    assert translation_summary["approved_alias_count"] >= 0
    assert translation_summary["local_fallback_count"] >= 0
