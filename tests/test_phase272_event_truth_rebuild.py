from __future__ import annotations

from sts_py.engine.run.events import build_event
from sts_py.engine.run.official_event_strings import get_official_event_strings
from sts_py.engine.run.run_engine import RunEngine, RunPhase
from sts_py.terminal.catalog import translate_event_name
from sts_py.tools.wiki_audit import build_cli_raw_snapshot


def test_phase272_official_event_snapshot_drives_runtime_event_translation() -> None:
    addict = get_official_event_strings("Addict")

    assert addict is not None
    assert addict.name_en == "Pleading Vagrant"
    assert addict.name_zhs == "流浪汉的恳求"
    assert translate_event_name(build_event("Designer")) == "“尖端”设计师"


def test_phase272_wiki_audit_event_inventory_uses_canonical_runtime_keys() -> None:
    snapshot = build_cli_raw_snapshot(".", enable_network=False)

    event_ids = set(snapshot["runtime_inventory"]["event"])

    assert "Big Fish" in event_ids
    assert "SpireHeart" in event_ids
    assert "The Woman in Blue" in event_ids


def test_phase272_addict_rob_path_grants_random_relic_and_shame() -> None:
    engine = RunEngine.create("PHASE272ADDICT", ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine._set_current_event(build_event("Addict"))

    result = engine.choose_event_option(1)

    assert result["success"] is True
    assert result["action"] == "robbed"
    assert "Shame" in engine.state.deck
    assert result["relic_id"] in engine.state.relics


def test_phase272_drug_dealer_transforms_two_selected_cards() -> None:
    engine = RunEngine.create("PHASE272DRUG", ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine.state.deck = ["Strike", "Defend", "Bash"]
    engine._set_current_event(build_event("Drug Dealer"))

    first = engine.choose_event_option(1)
    second = engine.choose_card_for_event(0)
    third = engine.choose_card_for_event(0)

    assert first["requires_card_choice"] is True
    assert second["action"] == "select_next_card"
    assert third["action"] == "cards_transformed"
    assert third["transformed"][0]["old_card"] == "Strike"
    assert third["transformed"][1]["old_card"] == "Defend"
    assert engine.state.phase == RunPhase.MAP
    assert engine.state.deck[2] == "Bash"


def test_phase272_golden_shrine_pray_and_desecrate_follow_java_rewards() -> None:
    pray_engine = RunEngine.create("PHASE272SHRINEPRAY", ascension=0)
    pray_engine.state.phase = RunPhase.EVENT
    pray_engine._set_current_event(build_event("Golden Shrine"))

    pray_result = pray_engine.choose_event_option(0)

    assert pray_result["gold_gained"] == 100
    assert pray_engine.get_pending_reward_state()["gold"] == 100

    desecrate_engine = RunEngine.create("PHASE272SHRINEDESECRATE", ascension=0)
    desecrate_engine.state.phase = RunPhase.EVENT
    desecrate_engine._set_current_event(build_event("Golden Shrine"))

    desecrate_result = desecrate_engine.choose_event_option(1)

    assert desecrate_result["gold_gained"] == 275
    assert "Regret" in desecrate_engine.state.deck


def test_phase272_nloth_trades_one_of_two_offered_relics_for_gift() -> None:
    engine = RunEngine.create("PHASE272NLOTH", ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine.state.relics = ["BurningBlood", "Anchor", "Lantern"]
    engine._set_current_event(build_event("N'loth"))

    choice_texts = [choice.description for choice in engine.get_current_event().choices]
    result = engine.choose_event_option(0)

    assert len(choice_texts) == 3
    assert result["action"] == "traded_relic"
    assert result["lost_relic"] not in engine.state.relics
    assert result["relic_id"] == "NlothsGift"
    assert "NlothsGift" in engine.state.relics


def test_phase272_we_meet_again_consumes_requested_good_and_grants_relic() -> None:
    engine = RunEngine.create("PHASE272WMA", ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine.state.potions = ["FirePotion", "EmptyPotionSlot", "EmptyPotionSlot"]
    engine.state.deck = ["Strike", "Bash", "Anger"]
    engine._set_current_event(build_event("WeMeetAgain"))

    result = engine.choose_event_option(0)

    assert result["action"] == "gave_potion"
    assert engine.state.potions == ["EmptyPotionSlot", "EmptyPotionSlot", "EmptyPotionSlot"]
    assert result["relic_id"] in engine.state.relics


def test_phase272_woman_in_blue_buy_and_leave_branches_match_runtime_penalties() -> None:
    buy_engine = RunEngine.create("PHASE272BLUEBUY", ascension=0)
    buy_engine.state.phase = RunPhase.EVENT
    buy_engine._set_current_event(build_event("The Woman in Blue"))

    buy_result = buy_engine.choose_event_option(2)

    assert buy_result["action"] == "bought_potions"
    assert len(buy_result["potions"]) == 3
    assert buy_engine.state.player_gold == 59

    leave_engine = RunEngine.create("PHASE272BLUELEAVE", ascension=15)
    leave_engine.state.phase = RunPhase.EVENT
    leave_engine._set_current_event(build_event("The Woman in Blue"))

    leave_result = leave_engine.choose_event_option(3)

    assert leave_result["hp_loss"] == 4
    assert leave_engine.state.player_hp == 76


def test_phase272_joust_stage_flow_and_payout_resolve_from_random_winner(monkeypatch) -> None:
    engine = RunEngine.create("PHASE272JOUST", ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine._set_current_event(build_event("The Joust"))
    monkeypatch.setattr(engine.state.rng.event_rng, "random_boolean_chance", lambda chance: False)

    first = engine.choose_event_option(0)
    second = engine.choose_event_option(0)

    assert first["event_continues"] is True
    assert second["action"] == "resolved_bet"
    assert second["owner_wins"] is False
    assert second["gold_gained"] == 100
    assert engine.state.player_gold == 149


def test_phase272_falling_builds_random_type_choices_then_removes_selected_card(monkeypatch) -> None:
    engine = RunEngine.create("PHASE272FALLING", ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine.state.deck = ["Strike", "Defend", "Inflame"]
    engine._set_current_event(build_event("Falling"))
    monkeypatch.setattr(engine.state.rng.event_rng, "random_int", lambda upper: 0)

    first = engine.choose_event_option(0)
    second = engine.choose_event_option(1)

    assert first["event_continues"] is True
    assert second["action"] == "removed_card"
    assert second["card_id"] == "Inflame"
    assert engine.state.deck == ["Strike", "Defend"]


def test_phase272_mysterious_sphere_sets_event_combat_with_random_rare_relic() -> None:
    engine = RunEngine.create("PHASE272SPHERE", ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine._set_current_event(build_event("Mysterious Sphere"))

    first = engine.choose_event_option(0)
    second = engine.choose_event_option(0)

    assert first["event_continues"] is True
    assert second["action"] == "combat"
    assert second["relic_id"] is not None
    assert engine.state.phase == RunPhase.COMBAT
    assert engine.state.current_event_combat["bonus_reward"] == second["relic_id"]


def test_phase272_bonfire_offers_card_and_applies_rarity_reward() -> None:
    engine = RunEngine.create("PHASE272BONFIRE", ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine.state.deck = ["Strike", "Bash"]
    engine._set_current_event(build_event("Bonfire Elementals"))

    first = engine.choose_event_option(0)
    second = engine.choose_event_option(0)
    third = engine.choose_card_for_event(1)

    assert first["event_continues"] is True
    assert second["requires_card_choice"] is True
    assert third["action"] == "bonfire_offer"
    assert third["card_id"] == "Bash"
    assert third["rarity"] in {"BASIC", "COMMON", "UNCOMMON", "RARE", "SPECIAL", "CURSE"}


def test_phase272_secret_portal_builds_a_direct_boss_node_jump() -> None:
    engine = RunEngine.create("PHASE272PORTAL", ascension=0)
    engine.transition_to_act_for_replay(3, floor=40)
    engine.state.phase = RunPhase.EVENT
    engine._set_current_event(build_event("SecretPortal"))

    first = engine.choose_event_option(0)
    second = engine.choose_event_option(0)

    assert first["event_continues"] is True
    assert second["action"] == "took_portal"
    assert second["target_floor"] == 50
    assert engine.state.phase == RunPhase.MAP
    assert len(engine.state.map_nodes) == 1
    assert engine.state.map_nodes[0].room_type.value == "B"


def test_phase272_mind_bloom_uses_floor_branch_and_real_rewards() -> None:
    rich_engine = RunEngine.create("PHASE272MINDBLOOMRICH", ascension=0)
    rich_engine.transition_to_act_for_replay(3, floor=39)
    rich_engine.state.phase = RunPhase.EVENT
    rich_engine._set_current_event(build_event("MindBloom"))

    rich_result = rich_engine.choose_event_option(2)

    assert rich_result["action"] == "gain_gold"
    assert rich_result["gold_gained"] == 999
    assert rich_engine.state.deck.count("Normality") == 2

    war_engine = RunEngine.create("PHASE272MINDBLOOMWAR", ascension=13)
    war_engine.transition_to_act_for_replay(3, floor=39)
    war_engine.state.phase = RunPhase.EVENT
    war_engine._set_current_event(build_event("MindBloom"))

    war_result = war_engine.choose_event_option(0)

    assert war_result["action"] == "boss_combat"
    assert war_result["gold_reward"] == 25
    assert war_engine.state.phase == RunPhase.COMBAT
    assert war_engine.state.current_event_combat["bonus_reward"] == war_result["relic_id"]


def test_phase272_designer_uses_runtime_random_flags_and_full_service_branch(monkeypatch) -> None:
    engine = RunEngine.create("PHASE272DESIGNER", ascension=0)
    engine.state.phase = RunPhase.EVENT
    engine.state.deck = ["Strike", "Bash", "Defend"]
    monkeypatch.setattr(engine.state.rng.event_rng, "random_boolean", lambda: True)
    engine._set_current_event(build_event("Designer"))

    first = engine.choose_event_option(0)
    second = engine.choose_event_option(2)
    third = engine.choose_card_for_event(1)

    assert first["event_continues"] is True
    assert second["requires_card_choice"] is True
    assert third["action"] == "designer_full_service"
    assert third["removed_card"] == "Bash"
    assert engine.state.player_gold == 9
