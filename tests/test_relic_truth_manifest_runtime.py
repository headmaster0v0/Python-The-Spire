from __future__ import annotations

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.official_relic_manifest import get_localization_only_relic_manifest, get_runtime_relic_manifest
from sts_py.engine.content.relics import get_relic_by_id, normalize_relic_id
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.run.run_engine import RunEngine


SEED_LONG = 4452322743548530140


class DummySkillTarget(MonsterBase):
    def __init__(self, *, hp: int = 50):
        super().__init__(id="DummySkillTarget", name="DummySkillTarget", hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, base_damage=5, name="Attack"))


def _make_combat(*, relics: list[str]) -> CombatEngine:
    ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
    hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
    combat = CombatEngine.create_with_monsters(
        monsters=[DummySkillTarget()],
        player_hp=70,
        player_max_hp=70,
        ai_rng=ai_rng,
        hp_rng=hp_rng,
        deck=["Strike", "Defend", "Defend", "Defend"],
        relics=relics,
    )
    combat.state.player.max_energy = 3
    combat.state.player.energy = 3
    combat.state.card_manager.set_max_energy(3)
    combat.state.card_manager.set_energy(3)
    return combat


def _set_hand(combat: CombatEngine, card_ids: list[str]) -> None:
    cards = [CardInstance(card_id) for card_id in card_ids]
    for card in cards:
        card._combat_state = combat.state
    combat.state.card_manager.hand.cards = cards


def test_official_relic_manifest_matches_runtime_scope() -> None:
    manifest = get_runtime_relic_manifest()
    localization_only = get_localization_only_relic_manifest()

    assert len(manifest) == 179
    assert len(localization_only) == 16
    assert "Circlet" in manifest
    assert "Red Circlet" in localization_only
    assert all(entry.loadable for entry in manifest.values())


def test_relic_normalization_accepts_legacy_runtime_and_official_ids() -> None:
    assert normalize_relic_id("TheBoot") == "Boot"
    assert normalize_relic_id("Boot") == "Boot"
    assert normalize_relic_id("PandoraBox") == "Pandora's Box"
    assert normalize_relic_id("Pandora's Box") == "Pandora's Box"
    assert normalize_relic_id("WhiteBeastStatue") == "White Beast Statue"
    assert normalize_relic_id("RingOfTheSnake") == "Ring of the Snake"


def test_get_relic_by_id_accepts_legacy_runtime_class_and_official_ids() -> None:
    legacy = get_relic_by_id("PandoraBox")
    class_name = get_relic_by_id("PandorasBox")
    official = get_relic_by_id("Pandora's Box")

    assert legacy is not None
    assert class_name is not None
    assert official is not None
    assert legacy.official_id == "Pandora's Box"
    assert class_name.official_id == "Pandora's Box"
    assert official.official_id == "Pandora's Box"
    assert legacy.name_zhs == "潘多拉的魔盒"


def test_damaru_grants_one_mantra_at_turn_start() -> None:
    combat = _make_combat(relics=["Damaru"])

    assert combat.state.player.get_power_amount("Mantra") == 0

    combat.end_player_turn()

    assert combat.state.player.get_power_amount("Mantra") == 1


def test_letter_opener_deals_five_damage_after_third_skill_each_turn() -> None:
    combat = _make_combat(relics=["LetterOpener"])
    _set_hand(combat, ["Defend", "Defend", "Defend"])

    monster = combat.state.monsters[0]
    hp_before = monster.hp

    assert combat.play_card(0) is True
    assert combat.play_card(0) is True
    assert combat.play_card(0) is True

    assert monster.hp == hp_before - 5


def test_meat_on_the_bone_heals_after_victory_below_half_hp() -> None:
    engine = RunEngine.create("TRUTHMEATONTHEBONE", ascension=0)
    engine.state.relics.append("MeatOnTheBone")
    engine.start_combat_with_monsters(["Cultist"])
    assert engine.state.combat is not None
    engine.state.combat.state.player.hp = 30
    engine.state.player_hp = 30

    for monster in engine.state.combat.state.monsters:
        monster.hp = 0
        monster.is_dying = True

    engine.end_combat()

    assert engine.state.player_hp == 48
