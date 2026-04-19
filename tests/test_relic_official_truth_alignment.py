from __future__ import annotations

from sts_py.engine.content.official_relic_manifest import get_runtime_relic_manifest
from sts_py.engine.content.relics import (
    ALL_RELICS,
    RelicTier,
    get_relic_pool,
    relic_can_spawn,
)
from sts_py.engine.run.run_engine import RunEngine
from sts_py.tools.wiki_audit import build_relic_source_facts


def test_manifest_tracks_default_stateful_and_ui_text_truth_for_key_relics() -> None:
    manifest = get_runtime_relic_manifest()

    assert len(manifest) == 179

    ring = manifest["RingOfTheSerpent"]
    assert ring.default_description_zhs == "替换蛇之戒指。在你的每个回合开始时，额外抽1张牌。"
    assert ring.description_slots_used == (0, 1)

    cauldron = manifest["Cauldron"]
    assert cauldron.default_description_zhs == "拾起时，制作5瓶随机药水。"
    assert cauldron.ui_prompt_slots == (1,)

    dolly = manifest["DollysMirror"]
    assert dolly.default_description_zhs == "拾起时，从你的牌组中选择一张牌进行复制。"
    assert dolly.ui_prompt_slots == (1,)

    omamori = manifest["Omamori"]
    stateful_texts = {variant.description_zhs for variant in omamori.stateful_description_variants}
    assert "抵消你下一次获得的诅咒。" in stateful_texts
    assert "这件遗物已经耗尽。" in stateful_texts

    bottled_flame = manifest["BottledFlame"]
    assert any(
        variant.description_zhs == "在每场战斗开始时，将 {selected_card_name} 放入你的手牌。"
        for variant in bottled_flame.stateful_description_variants
    )

    busted_crown = manifest["BustedCrown"]
    assert busted_crown.default_description_zhs == "在每回合开始时获得1点能量。在卡牌奖励画面，可供选择的牌数减少2张。"


def test_runtime_relic_overlay_uses_official_text_and_reference_metadata() -> None:
    ring = ALL_RELICS["RingOfTheSerpent"]
    assert ring.description_zhs == "替换蛇之戒指。在你的每个回合开始时，额外抽1张牌。"
    assert ring.description == ring.description_zhs
    assert ring.description_source == "java:getUpdatedDescription"
    assert ring.translation_source.endswith("localization/zhs/relics.json")

    cauldron = ALL_RELICS["Cauldron"]
    assert cauldron.description_zhs == "拾起时，制作5瓶随机药水。"
    assert cauldron.ui_prompt_slots == (1,)
    assert cauldron.wiki_url_en.endswith("/Cauldron")
    assert "sts.huijiwiki.com" in cauldron.wiki_url_cn

    omamori = ALL_RELICS["Omamori"]
    assert any(item["description_zhs"] == "这件遗物已经耗尽。" for item in omamori.stateful_description_variants)


def test_manifest_spawn_rules_capture_required_relic_act_and_deck_constraints() -> None:
    manifest = get_runtime_relic_manifest()

    assert manifest["BlackBlood"].spawn_rules["required_relics"] == ("Burning Blood",)
    assert manifest["HolyWater"].spawn_rules["required_relics"] == ("PureWater",)
    assert manifest["FrozenCore"].spawn_rules["required_relics"] == ("Cracked Core",)
    assert manifest["Ectoplasm"].spawn_rules["act_max"] == 1
    assert manifest["BottledFlame"].spawn_rules["required_deck_card_type"] == "ATTACK"
    assert manifest["BottledFlame"].spawn_rules["exclude_basic_cards"] is True
    assert manifest["BottledLightning"].spawn_rules["required_deck_card_type"] == "SKILL"
    assert set(manifest["Girya"].spawn_rules["exclusive_with_relics"]) == {"Girya", "PeacePipe", "Shovel"}
    assert manifest["Girya"].spawn_rules["exclusive_relic_limit"] == 2


def test_relic_can_spawn_applies_contextual_filters() -> None:
    assert relic_can_spawn(ALL_RELICS["BlackBlood"], act=1, owned_relics=["BurningBlood"]) is True
    assert relic_can_spawn(ALL_RELICS["BlackBlood"], act=1, owned_relics=["CrackedCore"]) is False
    assert relic_can_spawn(ALL_RELICS["RingOfTheSerpent"], act=1, owned_relics=["RingOfTheSnake"]) is True
    assert relic_can_spawn(ALL_RELICS["RingOfTheSerpent"], act=1, owned_relics=["BurningBlood"]) is False

    assert relic_can_spawn(ALL_RELICS["Ectoplasm"], act=1) is True
    assert relic_can_spawn(ALL_RELICS["Ectoplasm"], act=2) is False

    assert relic_can_spawn(ALL_RELICS["BottledFlame"], deck=["Strike", "Defend"]) is False
    assert relic_can_spawn(ALL_RELICS["BottledFlame"], deck=["Anger", "Defend"]) is True
    assert relic_can_spawn(ALL_RELICS["BottledLightning"], deck=["Strike", "Defend"]) is False
    assert relic_can_spawn(ALL_RELICS["BottledLightning"], deck=["ShrugItOff", "Strike"]) is True

    assert relic_can_spawn(ALL_RELICS["Girya"], floor=20, owned_relics=["PeacePipe", "Shovel"]) is False
    assert relic_can_spawn(ALL_RELICS["Girya"], floor=20, owned_relics=["PeacePipe"]) is True


def test_get_relic_pool_respects_runtime_context_for_boss_and_bottled_relics() -> None:
    boss_pool_with_blood = {
        relic.id
        for relic in get_relic_pool(
            RelicTier.BOSS,
            act=1,
            owned_relics=["BurningBlood"],
            deck=["Bash", "Defend", "Strike"],
        )
    }
    boss_pool_without_blood = {
        relic.id
        for relic in get_relic_pool(
            RelicTier.BOSS,
            act=1,
            owned_relics=["CrackedCore"],
            deck=["Bash", "Defend", "Strike"],
        )
    }
    act2_boss_pool = {
        relic.id
        for relic in get_relic_pool(
            RelicTier.BOSS,
            act=2,
            owned_relics=["BurningBlood"],
            deck=["Bash", "Defend", "Strike"],
        )
    }
    uncommon_skill_pool = {
        relic.id
        for relic in get_relic_pool(
            RelicTier.UNCOMMON,
            act=1,
            owned_relics=[],
            deck=["Prepared", "Backflip", "Defend"],
        )
    }

    assert "BlackBlood" in boss_pool_with_blood
    assert "BlackBlood" not in boss_pool_without_blood
    assert "Ectoplasm" not in act2_boss_pool
    assert "BottledFlame" not in uncommon_skill_pool
    assert "BottledLightning" in uncommon_skill_pool


def test_relic_rng_truth_samples_are_stable_under_fixed_seed() -> None:
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
    assert astrolabe_engine.state.deck == ["ShrugItOff", "Havoc+", "ShrugItOff+", "Armaments+"]

    tiny_house_engine = RunEngine.create("ALIGN_TINYHOUSE", ascension=0)
    tiny_house_engine.state.deck = ["Strike", "Defend", "Bash", "ShrugItOff"]
    tiny_house_engine.state.player_gold = 0
    tiny_house_engine.state.player_hp = 50
    tiny_house_engine.state.player_max_hp = 70
    tiny_house_engine._acquire_relic("TinyHouse", record_pending=False)
    assert tiny_house_engine.state.deck == ["Strike", "Defend", "Bash+", "ShrugItOff"]
    assert tiny_house_engine.state.player_gold == 50
    assert tiny_house_engine.state.player_max_hp == 75
    assert tiny_house_engine.state.player_hp == 75


def test_relic_source_facts_include_manifest_and_reference_provenance() -> None:
    facts = build_relic_source_facts(ALL_RELICS["Cauldron"])

    assert facts["official_id"] == "Cauldron"
    assert facts["description_source"] == "java:getUpdatedDescription"
    assert facts["translation_source"].endswith("localization/zhs/relics.json")
    assert facts["default_description_zhs"] == "拾起时，制作5瓶随机药水。"
    assert facts["ui_prompt_slots"] == [1]
    assert facts["wiki_url_en"].endswith("/Cauldron")
    assert facts["truth_sources"]["default_description_source"] == "java:getUpdatedDescription"
    assert facts["truth_sources"]["java_class"] == "Cauldron"


def test_rng_provenance_notes_cover_key_randomized_relics() -> None:
    assert ALL_RELICS["WarPaint"].rng_notes == ("miscRng",)
    assert ALL_RELICS["Whetstone"].rng_notes == ("miscRng",)
    assert ALL_RELICS["Astrolabe"].rng_notes == ("miscRng",)
    assert ALL_RELICS["TinyHouse"].rng_notes == ("miscRng",)
    assert ALL_RELICS["Matryoshka"].rng_notes == ("relicRng",)
    assert ALL_RELICS["MummifiedHand"].rng_notes == ("cardRandomRng",)
