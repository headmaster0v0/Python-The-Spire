"""Run state machine for Slay The Spire.

This module implements the complete run flow including:
- Map generation and navigation
- Room types and transitions
- Combat, events, shops, rest sites
- Card rewards and deck management
"""
from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sts_py.engine.combat.combat_engine import CombatEngine
from sts_py.engine.combat.combat_state import Player
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.content.cards_min import STARTER_DECK_CARD_IDS
from sts_py.engine.content.relics import RelicSource, get_starter_relic_pool
from sts_py.engine.run.official_neow_strings import (
    get_official_neow_event_strings,
    get_official_neow_reward_strings,
)
from sts_py.engine.run.player_profile import (
    LEGACY_NOTE_FOR_YOURSELF_PATH,
    PLAYER_PROFILE_PATH,
    CharacterProgress,
    NoteForYourselfProfile,
    PlayerProfile,
    load_player_profile,
    save_player_profile,
)
from sts_py.engine.run.run_rng import RunRngState

if TYPE_CHECKING:
    from sts_py.engine.combat.combat_engine import CombatEngine
    from sts_py.engine.rewards.card_rewards_min import RewardGenState
    from sts_py.engine.run.events import Event, EventChoice
    from sts_py.engine.run.shop import ShopState, ShopEngine


class RoomType(str, Enum):
    MONSTER = "M"
    ELITE = "E"
    BOSS = "B"
    EVENT = "?"
    SHOP = "$"
    REST = "R"
    TREASURE = "T"
    EMPTY = " "


class RunPhase(str, Enum):
    INIT = "init"
    NEOW = "neow"
    MAP = "map"
    COMBAT = "combat"
    REWARD = "reward"
    EVENT = "event"
    SHOP = "shop"
    REST = "rest"
    TREASURE = "treasure"
    GAME_OVER = "game_over"
    VICTORY = "victory"


CHARACTER_STARTING_STATS: dict[str, dict[str, int]] = {
    "IRONCLAD": {"hp": 80, "max_hp": 80, "gold": 99},
    "SILENT": {"hp": 70, "max_hp": 70, "gold": 99},
    "DEFECT": {"hp": 75, "max_hp": 75, "gold": 99},
    "WATCHER": {"hp": 72, "max_hp": 72, "gold": 99},
}

NOTE_FOR_YOURSELF_PREFS_PATH = LEGACY_NOTE_FOR_YOURSELF_PATH


def _new_relic_pool_consumed() -> dict[str, list[str]]:
    return {
        "boss": [],
        "common": [],
        "uncommon": [],
        "rare": [],
        "shop": [],
    }


def _deck_card_base_id(card_id: str) -> str:
    from sts_py.engine.content.card_instance import get_runtime_card_base_id

    return get_runtime_card_base_id(card_id)


@dataclass
class MapNode:
    floor: int
    room_type: RoomType
    x: int = 0
    y: int = 0
    node_id: int = -1
    connections: list[int] = field(default_factory=list)
    parent_indices: list[int] = field(default_factory=list)
    encounter: str | None = None
    burning_elite: bool = False


@dataclass
class RunState:
    """Complete run state for headless simulation."""

    seed: int
    seed_string: str
    ascension: int = 0
    character_class: str = "IRONCLAD"

    player_hp: int = 80
    player_max_hp: int = 80
    player_gold: int = 99

    floor: int = 0
    act: int = 1
    phase: RunPhase = RunPhase.INIT

    neow_blessing: bool = False
    neow_blessing_remaining: int = 0
    player_pending_tea_energy: int = 0
    player_relic_attack_counters: dict[str, int] = field(default_factory=dict)
    relic_counters: dict[str, int] = field(default_factory=dict)
    relic_pool_consumed: dict[str, list[str]] = field(default_factory=_new_relic_pool_consumed)
    relic_history: list[dict[str, Any]] = field(default_factory=list)
    shop_history: list[dict[str, Any]] = field(default_factory=list)

    deck: list[str] = field(default_factory=lambda: [
        "Strike", "Strike", "Strike", "Strike", "Strike",
        "Defend", "Defend", "Defend", "Defend",
        "Bash"
    ])
    relics: list[str] = field(default_factory=lambda: ["BurningBlood"])
    potions: list[str] = field(default_factory=lambda: ["EmptyPotionSlot", "EmptyPotionSlot", "EmptyPotionSlot"])
    potion_drop_chance: int = 40
    relic_drop_chance: int = 0

    map_nodes: list[MapNode] = field(default_factory=list)
    current_node_idx: int = -1
    path_taken: list[str] = field(default_factory=list)
    path_trace: list[dict[str, Any]] = field(default_factory=list)

    # Encounter pools generated at act start (SHARED monsterList like Java)
    # Java: 3 weak + 12 strong = 15 MonsterRoom encounters in a shared list
    monster_list: list[str] = field(default_factory=list)
    elite_list: list[str] = field(default_factory=list)

    # Encounter consumption index (by VISIT ORDER, not floor number)
    monster_list_idx: int = 0
    elite_list_idx: int = 0

    # Question room tracking (for trap monster encounters)
    question_room_count: int = 0
    question_room_monster_chance: float = 0.10  # 10% base, +10% each failed roll
    question_room_treasure_chance: float = 0.02  # 2% base, +2% each failed roll
    question_room_shop_chance: float = 0.03  # 3% base, +3% each failed roll (deadly events only, floor 6+)
    question_room_elite_chance: float = 0.0  # Java base/reset when DeadlyEvents is disabled
    question_room_last_encounter: str = ""
    previous_room_type_for_event_roll: str = ""
    event_list: list[str] = field(default_factory=list)
    shrine_list: list[str] = field(default_factory=list)
    special_one_time_event_list: list[str] = field(default_factory=list)
    playtime_seconds: float = 0.0

    combat: CombatEngine | None = None
    combat_history: list[dict[str, Any]] = field(default_factory=list)

    card_choices: list[dict[str, Any]] = field(default_factory=list)
    boss_relic_choices: list[dict[str, Any]] = field(default_factory=list)
    treasure_rooms: list[dict[str, Any]] = field(default_factory=list)
    event_choices: list[dict[str, Any]] = field(default_factory=list)

    current_event_id: str | None = None
    current_event_key: str | None = None
    current_event_state: dict[str, Any] = field(default_factory=dict)
    pending_card_choice: dict[str, Any] | None = None
    dead_adventurer_state: dict[str, Any] = field(default_factory=dict)
    current_event_combat: dict[str, Any] | None = None
    note_for_yourself_payload: dict[str, Any] = field(default_factory=dict)
    character_spirits: int = 0
    highest_unlocked_ascension: int = 1
    last_ascension_level: int = 1
    neow_intro_seen: bool = False
    neow_screen: str = ""
    neow_body: str = ""
    neow_body_cn: str = ""
    spire_heart_meta: dict[str, Any] = field(default_factory=dict)
    neow_options: list[dict[str, Any]] = field(default_factory=list)
    pending_neow_choice: dict[str, Any] | None = None

    rng: RunRngState | None = None
    reward_state: "RewardGenState | None" = None
    pending_card_reward_cards: list[str] = field(default_factory=list)
    pending_treasure_relic: str | None = None
    pending_chest_relic_choices: list[str] = field(default_factory=list)
    pending_boss_relic_choices: list[str] = field(default_factory=list)
    ruby_key_obtained: bool = False
    emerald_key_obtained: bool = False
    sapphire_key_obtained: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "seed_string": self.seed_string,
            "ascension": self.ascension,
            "character_class": self.character_class,
            "player_hp": self.player_hp,
            "player_max_hp": self.player_max_hp,
            "player_gold": self.player_gold,
            "floor": self.floor,
            "act": self.act,
            "phase": self.phase.value,
            "deck": self.deck,
            "relics": self.relics,
            "path_taken": self.path_taken,
            "path_trace": self.path_trace,
            "combat_history": self.combat_history,
            "card_choices": self.card_choices,
            "boss_relic_choices": self.boss_relic_choices,
            "treasure_rooms": self.treasure_rooms,
            "event_choices": self.event_choices,
            "event_list": self.event_list,
            "shrine_list": self.shrine_list,
            "special_one_time_event_list": self.special_one_time_event_list,
            "question_room_monster_chance": self.question_room_monster_chance,
            "question_room_shop_chance": self.question_room_shop_chance,
            "question_room_treasure_chance": self.question_room_treasure_chance,
            "question_room_elite_chance": self.question_room_elite_chance,
            "previous_room_type_for_event_roll": self.previous_room_type_for_event_roll,
            "playtime_seconds": self.playtime_seconds,
            "current_event_id": self.current_event_id,
            "current_event_key": self.current_event_key,
            "current_event_state": self.current_event_state,
            "pending_card_choice": self.pending_card_choice,
            "current_event_combat": self.current_event_combat,
            "note_for_yourself_payload": self.note_for_yourself_payload,
            "character_spirits": self.character_spirits,
            "highest_unlocked_ascension": self.highest_unlocked_ascension,
            "last_ascension_level": self.last_ascension_level,
            "neow_intro_seen": self.neow_intro_seen,
            "neow_screen": self.neow_screen,
            "neow_body": self.neow_body,
            "neow_body_cn": self.neow_body_cn,
            "spire_heart_meta": self.spire_heart_meta,
            "neow_options": self.neow_options,
            "pending_neow_choice": self.pending_neow_choice,
            "relic_counters": self.relic_counters,
            "relic_pool_consumed": self.relic_pool_consumed,
            "relic_history": self.relic_history,
            "shop_history": self.shop_history,
            "pending_chest_relic_choices": self.pending_chest_relic_choices,
            "pending_boss_relic_choices": self.pending_boss_relic_choices,
            "ruby_key_obtained": self.ruby_key_obtained,
            "emerald_key_obtained": self.emerald_key_obtained,
            "sapphire_key_obtained": self.sapphire_key_obtained,
        }


def _normalize_monster_lookup_id(monster_id: str) -> str:
    return monster_id.replace(" ", "").replace("_", "").replace("-", "").lower()


def _combat_summary_monster_view(combat: Any) -> tuple[list[str], list[int]] | None:
    state = getattr(combat, "state", None)
    if state is None:
        return None
    full_roster_ids = getattr(state, "_replay_gremlinleader_full_roster_ids", None)
    summary_slots = getattr(state, "_replay_gremlinleader_summary_slots", None)
    if not isinstance(full_roster_ids, list) or not isinstance(summary_slots, list):
        return None
    if len(full_roster_ids) != len(summary_slots):
        return None
    return (
        [str(monster_id) for monster_id in full_roster_ids],
        [int(getattr(monster, "hp", 0) or 0) if monster is not None else 0 for monster in summary_slots],
    )


def _monster_factory_registry() -> dict[str, type[Any]]:
    from sts_py.engine.monsters.bosses import (
        Automaton,
        AwakenedOne,
        BronzeOrb,
        Champ,
        Collector,
        Deca,
        Donu,
        DonuAndDeca,
        Hexaghost,
        SlimeBoss,
        TheGuardian,
        TimeEater,
        TorchHead,
    )
    from sts_py.engine.monsters.city_beyond import (
        BookOfStabbing,
        Byrd,
        Centurion,
        Chosen,
        Darkling,
        Dagger,
        Exploder,
        GremlinLeader,
        GiantHead,
        GenericMonsterProxy,
        Healer,
        Maw,
        Nemesis,
        OrbWalker,
        Reptomancer,
        Repulsor,
        Serpent,
        ShellParasite,
        SlaverBoss,
        Snecko,
        SnakePlant,
        Spiker,
        SphericGuardian,
        Transient,
        WrithingMass,
    )
    from sts_py.engine.monsters.ending import CorruptHeart, SpireShield, SpireSpear
    from sts_py.engine.monsters.exordium import (
        AcidSlimeSmall,
        AcidSlimeLarge,
        AcidSlimeMedium,
        Cultist,
        FungiBeast,
        GremlinFat,
        GremlinNob,
        GremlinSneaky,
        GremlinTsundere,
        GremlinWar,
        Hexaghost as ExordiumHexaghost,
        JawWorm,
        Lagavulin,
        Looter,
        LouseDefensive,
        LouseNormal,
        Mugger,
        Sentry,
        SlaverRed,
        SlaverBlue,
        SpikeSlimeLarge,
        SpikeSlimeMedium,
        SpikeSlimeSmall,
    )

    monster_types: dict[str, type[Any]] = {
        "jawworm": JawWorm,
        "cultist": Cultist,
        "fungibeast": FungiBeast,
        "gremlinfat": GremlinFat,
        "gremlinleader": GremlinLeader,
        "gremlinnob": GremlinNob,
        "gremlinsneaky": GremlinSneaky,
        "gremlintsundere": GremlinTsundere,
        "gremlinwar": GremlinWar,
        "lagavulin": Lagavulin,
        "sentry": Sentry,
        "slaverred": SlaverRed,
        "slaverblue": SlaverBlue,
        "hexaghost": ExordiumHexaghost,
        "fuzzylousenormal": LouseNormal,
        "fuzzylousedefensive": LouseDefensive,
        "looter": Looter,
        "mugger": Mugger,
        "spikeslimelarge": SpikeSlimeLarge,
        "spikeslimemedium": SpikeSlimeMedium,
        "spikeslimesmall": SpikeSlimeSmall,
        "acidslimesmall": AcidSlimeSmall,
        "acidslimelarge": AcidSlimeLarge,
        "acidslimemedium": AcidSlimeMedium,
        "byrd": Byrd,
        "chosen": Chosen,
        "bookofstabbing": BookOfStabbing,
        "centurion": Centurion,
        "darkling": Darkling,
        "dagger": Dagger,
        "exploder": Exploder,
        "gianthead": GiantHead,
        "healer": Healer,
        "maw": Maw,
        "nemesis": Nemesis,
        "orbwalker": OrbWalker,
        "reptomancer": Reptomancer,
        "repulsor": Repulsor,
        "serpent": Serpent,
        "shellparasite": ShellParasite,
        "slaverboss": SlaverBoss,
        "snecko": Snecko,
        "snakeplant": SnakePlant,
        "spiker": Spiker,
        "sphericguardian": SphericGuardian,
        "transient": Transient,
        "writhingmass": WrithingMass,
        "slimeboss": SlimeBoss,
        "theguardian": TheGuardian,
        "champ": Champ,
        "collector": Collector,
        "torchhead": TorchHead,
        "automaton": Automaton,
        "bronzeorb": BronzeOrb,
        "awakenedone": AwakenedOne,
        "timeeater": TimeEater,
        "deca": Deca,
        "donu": Donu,
        "donuanddeca": DonuAndDeca,
        "spireshield": SpireShield,
        "spirespear": SpireSpear,
        "corruptheart": CorruptHeart,
    }
    monster_types["genericmonsterproxy"] = GenericMonsterProxy
    return monster_types


JAVA_MONSTER_ID_ALIASES = {
    "Louse": "FuzzyLouseNormal",
    "LagavulinEvent": "Lagavulin",
    "SpikeSlimeL": "SpikeSlimeLarge",
    "SpikeSlimeM": "SpikeSlimeMedium",
    "SpikeSlimeS": "SpikeSlimeSmall",
    "AcidSlimeS": "AcidSlimeSmall",
    "AcidSlimeL": "AcidSlimeLarge",
    "AcidSlimeM": "AcidSlimeMedium",
    "GremlinThief": "GremlinSneaky",
    "GremlinWarrior": "GremlinWar",
    "ShelledParasite": "ShellParasite",
    "Shelled Parasite": "ShellParasite",
    "BronzeOrb": "Bronze Orb",
    "BronzeAutomaton": "Automaton",
    "Bronze Automaton": "Automaton",
    "TheCollector": "Collector",
    "AwakenedOne": "Awakened One",
    "Orb Walker": "OrbWalker",
}


def _runtime_monster_id_for_logged_id(monster_id: str) -> str:
    alias_key = _normalize_monster_lookup_id(monster_id)
    for source, target in JAVA_MONSTER_ID_ALIASES.items():
        if alias_key == _normalize_monster_lookup_id(source):
            return target
    return monster_id


def _create_replay_monster(
    monster_id: str,
    hp_rng: MutableRNG,
    ascension: int,
    *,
    act: int,
) -> tuple[Any | None, dict[str, Any]]:
    from sts_py.engine.monsters.city_beyond import GenericMonsterProxy

    debug: dict[str, Any] = {"logged_id": monster_id}
    runtime_monster_id = _runtime_monster_id_for_logged_id(monster_id)
    debug["runtime_id"] = runtime_monster_id
    if runtime_monster_id != monster_id:
        debug["alias_hit"] = True

    registry = _monster_factory_registry()
    monster_cls = registry.get(_normalize_monster_lookup_id(runtime_monster_id))
    if monster_cls is None:
        monster_cls = GenericMonsterProxy
        debug["used_proxy"] = True

    kwargs: dict[str, Any] = {}
    if monster_id == "Lagavulin Event":
        kwargs["asleep"] = False
    elif monster_id == "Lagavulin":
        kwargs["asleep"] = True

    if monster_cls is GenericMonsterProxy:
        kwargs.update({
            "act": act,
            "is_elite": False,
            "is_boss": False,
            "name_proxy": monster_id,
        })

    try:
        sig = inspect.signature(monster_cls.create)
        valid_kwargs = {key: value for key, value in kwargs.items() if key in sig.parameters}
        monster = monster_cls.create(hp_rng, ascension, **valid_kwargs)
    except Exception as exc:
        debug["factory_error"] = type(exc).__name__
        return None, debug

    monster.id = monster_id
    debug["created"] = True
    return monster, debug


@dataclass
class RunEngine:
    """Main run engine for headless STS simulation."""

    state: RunState
    ai_rng: MutableRNG
    hp_rng: MutableRNG
    _neow_rng: MutableRNG | None = None
    _player_profile: PlayerProfile | None = None
    _pending_gold_reward: int = 0
    _pending_potion_reward: str | None = None
    _pending_relic_reward: str | None = None
    _pending_relic_rewards: list[str] = field(default_factory=list)
    _resume_victory_after_reward: bool = False

    @classmethod
    def create(cls, seed_string: str, ascension: int = 0, character_class: str = "IRONCLAD") -> "RunEngine":
        from sts_py.engine.core.seed import seed_string_to_long

        seed = seed_string_to_long(seed_string)
        rng = RunRngState.generate_seeds(seed)
        character_key = character_class.upper()
        player_profile = load_player_profile(path=PLAYER_PROFILE_PATH, legacy_note_path=NOTE_FOR_YOURSELF_PREFS_PATH)
        character_progress = player_profile.character_progress(character_key)
        starting_stats = CHARACTER_STARTING_STATS.get(character_key, CHARACTER_STARTING_STATS["IRONCLAD"])
        starter_deck = list(STARTER_DECK_CARD_IDS.get(character_key, STARTER_DECK_CARD_IDS["IRONCLAD"]))
        starter_relic_pool = get_starter_relic_pool(character_key)
        starter_relics = [starter_relic_pool[0].id] if starter_relic_pool else ["BurningBlood"]

        state = RunState(
            seed=seed,
            seed_string=seed_string,
            ascension=ascension,
            character_class=character_key,
            player_hp=starting_stats["hp"],
            player_max_hp=starting_stats["max_hp"],
            player_gold=starting_stats["gold"],
            deck=starter_deck,
            relics=starter_relics,
            note_for_yourself_payload={
                "card_id": player_profile.note_for_yourself.card_id,
                "upgrades": player_profile.note_for_yourself.upgrades,
            },
            character_spirits=character_progress.spirits,
            highest_unlocked_ascension=character_progress.highest_unlocked_ascension,
            last_ascension_level=character_progress.last_ascension_level,
            neow_intro_seen=player_profile.neow_intro_seen,
        )
        state.rng = rng

        ai_rng = MutableRNG.from_seed(seed, counter=0, rng_type="aiRng")
        hp_rng = MutableRNG.from_seed(seed, counter=100, rng_type="monsterHpRng")

        engine = cls(
            state=state,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
            _neow_rng=MutableRNG.from_seed(seed, rng_type="neowRng"),
            _player_profile=player_profile,
        )
        engine._init_run()
        return engine

    def _init_run(self) -> None:
        self._initialize_special_one_time_event_pool()
        self._initialize_event_pools_for_act()
        self._reset_question_room_probabilities()
        self._generate_encounters_for_act()
        self._generate_map()
        self._init_neow()
        self.state.phase = RunPhase.NEOW

    def _initialize_special_one_time_event_pool(self) -> None:
        from sts_py.engine.run.events import SPECIAL_ONE_TIME_EVENT_KEYS

        if self.state.special_one_time_event_list:
            return
        self.state.special_one_time_event_list = [
            key for key in SPECIAL_ONE_TIME_EVENT_KEYS
            if key != "NoteForYourself" or self._is_note_for_yourself_available()
        ]

    def _is_note_for_yourself_available(self) -> bool:
        ascension_level = int(getattr(self.state, "ascension", 0) or 0)
        if ascension_level >= 15:
            return False
        if ascension_level == 0:
            return True
        highest_unlocked = max(1, int(getattr(self.state, "highest_unlocked_ascension", 1) or 1))
        return ascension_level < highest_unlocked

    def _initialize_event_pools_for_act(self) -> None:
        from sts_py.engine.run.events import ACT_EVENT_KEYS_BY_ACT, SHRINE_EVENT_KEYS_BY_ACT

        self.state.event_list = list(ACT_EVENT_KEYS_BY_ACT.get(self.state.act, []))
        self.state.shrine_list = list(SHRINE_EVENT_KEYS_BY_ACT.get(self.state.act, []))

    def _reset_question_room_probabilities(self) -> None:
        self.state.question_room_count = 0
        self.state.question_room_elite_chance = 0.0
        self.state.question_room_monster_chance = 0.10
        self.state.question_room_shop_chance = 0.03
        self.state.question_room_treasure_chance = 0.02
        self.state.question_room_last_encounter = ""

    def _event_state(self) -> dict[str, Any]:
        current = self.state.current_event_state
        if isinstance(current, dict):
            return current
        self.state.current_event_state = {}
        return self.state.current_event_state

    def _event_handler_key(self, event: "Event") -> str:
        from sts_py.engine.run.events import _resolve_event_key

        event_key = str(getattr(event, "event_key", "") or "")
        event_id = str(getattr(event, "event_id", getattr(event, "id", "")) or "")
        if event_key == "Golden Shrine Trap" or event_id == "Golden Shrine Trap":
            return "Golden Shrine Trap"
        return (
            _resolve_event_key(event_key)
            or _resolve_event_key(event_id)
            or event_key
            or event_id
        )

    def _event_rng(self) -> MutableRNG | None:
        rng_state = getattr(self.state, "rng", None)
        return getattr(rng_state, "event_rng", None)

    def _misc_rng(self) -> MutableRNG | None:
        rng_state = getattr(self.state, "rng", None)
        return getattr(rng_state, "misc_rng", None)

    def _normalize_note_for_yourself_payload(self, payload: Any) -> dict[str, Any]:
        raw = payload if isinstance(payload, dict) else {}
        card_id = str(raw.get("card_id", "IronWave") or "IronWave")
        upgrades = max(0, int(raw.get("upgrades", 0) or 0))
        return {"card_id": card_id, "upgrades": upgrades}

    def _normalize_character_progress(self, progress: Any) -> CharacterProgress:
        if isinstance(progress, CharacterProgress):
            return progress
        return CharacterProgress.from_raw(progress)

    def _load_player_profile(self) -> PlayerProfile:
        if self._player_profile is None:
            self._player_profile = load_player_profile(
                path=PLAYER_PROFILE_PATH,
                legacy_note_path=NOTE_FOR_YOURSELF_PREFS_PATH,
            )
        return self._player_profile

    def _current_character_progress(self) -> CharacterProgress:
        profile = self._load_player_profile()
        progress = self._normalize_character_progress(profile.character_progress(self.state.character_class))
        profile.characters[self.state.character_class] = progress
        self.state.character_spirits = progress.spirits
        self.state.highest_unlocked_ascension = progress.highest_unlocked_ascension
        self.state.last_ascension_level = progress.last_ascension_level
        return progress

    def _save_player_profile(self) -> None:
        profile = self._load_player_profile()
        profile.neow_intro_seen = bool(self.state.neow_intro_seen)
        note_payload = self._normalize_note_for_yourself_payload(self.state.note_for_yourself_payload)
        profile.note_for_yourself = NoteForYourselfProfile(
            card_id=note_payload["card_id"],
            upgrades=int(note_payload["upgrades"]),
        )
        progress = profile.character_progress(self.state.character_class)
        progress.spirits = max(0, int(self.state.character_spirits or 0))
        progress.highest_unlocked_ascension = max(1, int(self.state.highest_unlocked_ascension or 1))
        progress.last_ascension_level = max(1, int(self.state.last_ascension_level or progress.highest_unlocked_ascension))
        try:
            save_player_profile(profile, path=PLAYER_PROFILE_PATH)
        except Exception:
            pass

    def _record_standard_run_profile_outcome(self, *, victory: bool) -> None:
        progress = self._current_character_progress()
        ascension_level = max(0, int(getattr(self.state, "ascension", 0) or 0))
        if victory:
            progress.spirits = 1
            if ascension_level > 0 and ascension_level == progress.highest_unlocked_ascension:
                progress.highest_unlocked_ascension = min(20, ascension_level + 1)
                progress.last_ascension_level = progress.highest_unlocked_ascension
            elif ascension_level > 0:
                progress.last_ascension_level = ascension_level
        else:
            progress.spirits = 1 if int(getattr(self.state, "floor", 0) or 0) >= 16 else 0
            if ascension_level > 0:
                progress.last_ascension_level = ascension_level

        self.state.character_spirits = progress.spirits
        self.state.highest_unlocked_ascension = progress.highest_unlocked_ascension
        self.state.last_ascension_level = progress.last_ascension_level
        self._save_player_profile()

    def _load_note_for_yourself_payload(self) -> dict[str, Any]:
        profile = self._load_player_profile()
        return self._normalize_note_for_yourself_payload({
            "card_id": profile.note_for_yourself.card_id,
            "upgrades": profile.note_for_yourself.upgrades,
        })

    def _save_note_for_yourself_payload(self, *, card_id: str, upgrades: int = 0) -> None:
        payload = self._normalize_note_for_yourself_payload({"card_id": card_id, "upgrades": upgrades})
        self.state.note_for_yourself_payload = payload
        try:
            profile = self._load_player_profile()
            profile.note_for_yourself.card_id = payload["card_id"]
            profile.note_for_yourself.upgrades = int(payload["upgrades"])
            self._save_player_profile()
        except Exception:
            pass
        path = NOTE_FOR_YOURSELF_PREFS_PATH
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _event_random_choice(self, values: list[Any], *, rng: MutableRNG | None = None) -> Any | None:
        if not values:
            return None
        picker = rng if rng is not None else self._event_rng()
        if picker is None:
            return values[0]
        return values[picker.random_int(len(values) - 1)]

    def _draw_unique_colorless_event_cards(
        self,
        count: int,
        *,
        allowed_rarities: set[str] | None = None,
    ) -> list[str]:
        from sts_py.engine.combat.card_effects import _implemented_colorless_combat_card_ids
        from sts_py.engine.content.cards_min import COLORLESS_ALL_DEFS

        allowed = {str(rarity).upper() for rarity in (allowed_rarities or {"COMMON", "UNCOMMON", "RARE"})}
        pool = [
            card_id
            for card_id in _implemented_colorless_combat_card_ids()
            if COLORLESS_ALL_DEFS.get(card_id) is not None
            and str(COLORLESS_ALL_DEFS[card_id].rarity).rsplit(".", 1)[-1].upper() in allowed
        ]
        chosen: list[str] = []
        rng = self._misc_rng()
        while pool and len(chosen) < count:
            idx = rng.random_int(len(pool) - 1) if rng is not None else 0
            chosen.append(pool.pop(idx))
        return chosen

    def _draw_unique_character_event_cards(self, count: int) -> list[str]:
        from sts_py.engine.rewards.card_rewards_min import RewardGenState, character_pools, roll_rarity

        if self.state.rng is None:
            return []

        reward_state = self.state.reward_state or RewardGenState()
        reward_rng = self.state.rng.card_rng.to_immutable()
        pools = character_pools(self.state.character_class)
        chosen: list[str] = []
        while len(chosen) < count:
            reward_rng, reward_state, rarity = roll_rarity(reward_rng, reward_state)
            available = [card_def.id for card_def in pools.get(rarity, []) if card_def.id not in chosen]
            if not available:
                available = [
                    card_def.id
                    for pool in pools.values()
                    for card_def in pool
                    if card_def.id not in chosen
                ]
            if not available:
                break
            reward_rng, pick_idx = reward_rng.random_int(len(available))
            chosen.append(available[pick_idx])
        self.state.rng.card_rng._rng = reward_rng
        self.state.reward_state = reward_state
        return chosen

    def _resume_event_from_state(self, event_key: str, event_state: dict[str, Any] | None = None) -> None:
        from sts_py.engine.run.events import build_event

        self.state.current_event_state = dict(event_state or {})
        event_rng = getattr(getattr(self.state, "rng", None), "event_rng", None)
        self._set_current_event(build_event(event_key, event_rng))

    def _event_desc(self, event: "Event", idx: int, *, cn: bool = False) -> str:
        values = getattr(event, "source_descriptions_cn" if cn else "source_descriptions", []) or []
        if 0 <= idx < len(values):
            return str(values[idx] or "")
        return str(getattr(event, "description_cn" if cn else "description", "") or "")

    def _event_opt(self, event: "Event", idx: int, *, cn: bool = False) -> str:
        values = getattr(event, "source_options_cn" if cn else "source_options", []) or []
        if 0 <= idx < len(values):
            return str(values[idx] or "")
        return ""

    def _make_event_choice(
        self,
        *,
        description: str,
        description_cn: str = "",
        enabled: bool = True,
        disabled_reason: str = "",
        disabled_reason_cn: str = "",
        **kwargs: Any,
    ) -> "EventChoice":
        from sts_py.engine.run.events import EventChoice

        return EventChoice(
            description=description,
            description_cn=description_cn,
            enabled=enabled,
            disabled_reason=disabled_reason,
            disabled_reason_cn=disabled_reason_cn,
            **kwargs,
        )

    def _set_pending_event_card_choice(
        self,
        *,
        choice_index: int,
        custom_action: str,
        cards: list[str],
        prompt: str,
        prompt_cn: str = "",
        deck_indexes: list[int] | None = None,
        can_cancel: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.state.pending_card_choice = {
            "choice_index": choice_index,
            "custom_action": custom_action,
            "cards": list(cards),
            "deck_indexes": list(deck_indexes or []),
            "prompt": prompt,
            "prompt_cn": prompt_cn,
            "can_cancel": can_cancel,
            **dict(extra or {}),
        }
        return {
            "success": True,
            "requires_card_choice": True,
            "choice_index": choice_index,
            "custom_action": custom_action,
        }

    def _prepare_event_for_runtime(self, event: "Event") -> None:
        handler_key = self._event_handler_key(event)
        if handler_key == "Dead Adventurer":
            self._configure_dead_adventurer_event(event)
        elif handler_key == "Golden Idol":
            self._configure_golden_idol_event(event)
        elif handler_key == "Golden Wing":
            self._configure_golden_wing_event(event)
        elif handler_key == "World of Goop":
            self._configure_world_of_goop_event(event)
        elif handler_key == "Living Wall":
            self._configure_living_wall_event(event)
        elif handler_key == "Mushrooms":
            self._configure_mushrooms_event(event)
        elif handler_key == "Scrap Ooze":
            self._configure_scrap_ooze_event(event)
        elif handler_key == "Shining Light":
            self._configure_shining_light_event(event)
        elif handler_key == "Big Fish":
            self._configure_big_fish_event(event)
        elif handler_key == "The Cleric":
            self._configure_cleric_event(event)
        elif handler_key == "Beggar":
            self._configure_beggar_event(event)
        elif handler_key == "Liars Game":
            self._configure_liars_game_event(event)
        elif handler_key == "Addict":
            self._configure_addict_event(event)
        elif handler_key == "Back to Basics":
            self._configure_back_to_basics_event(event)
        elif handler_key == "Cursed Tome":
            self._configure_cursed_tome_event(event)
        elif handler_key == "Drug Dealer":
            self._configure_drug_dealer_event(event)
        elif handler_key == "Forgotten Altar":
            self._configure_forgotten_altar_event(event)
        elif handler_key == "Designer":
            self._configure_designer_event(event)
        elif handler_key == "Ghosts":
            self._configure_ghosts_event(event)
        elif handler_key == "Masked Bandits":
            self._configure_masked_bandits_event(event)
        elif handler_key == "Nest":
            self._configure_nest_event(event)
        elif handler_key == "The Library":
            self._configure_library_event(event)
        elif handler_key == "The Mausoleum":
            self._configure_mausoleum_event(event)
        elif handler_key == "Vampires":
            self._configure_vampires_event(event)
        elif handler_key == "Colosseum":
            self._configure_colosseum_event(event)
        elif handler_key == "Golden Shrine":
            self._configure_golden_shrine_event(event)
        elif handler_key == "FaceTrader":
            self._configure_face_trader_event(event)
        elif handler_key == "Fountain of Cleansing":
            self._configure_fountain_event(event)
        elif handler_key == "Knowing Skull":
            self._configure_knowing_skull_event(event)
        elif handler_key == "Duplicator":
            self._configure_duplicator_event(event)
        elif handler_key == "Purifier":
            self._configure_purifier_event(event)
        elif handler_key == "Upgrade Shrine":
            self._configure_upgrade_shrine_event(event)
        elif handler_key == "Transmorgrifier":
            self._configure_transmorgrifier_event(event)
        elif handler_key == "Accursed Blacksmith":
            self._configure_accursed_blacksmith_event(event)
        elif handler_key == "Lab":
            self._configure_lab_event(event)
        elif handler_key == "Match and Keep!":
            self._configure_match_and_keep_event(event)
        elif handler_key == "N'loth":
            self._configure_nloth_event(event)
        elif handler_key == "NoteForYourself":
            self._configure_note_for_yourself_event(event)
        elif handler_key == "SecretPortal":
            self._configure_secret_portal_event(event)
        elif handler_key == "WeMeetAgain":
            self._configure_we_meet_again_event(event)
        elif handler_key == "The Woman in Blue":
            self._configure_woman_in_blue_event(event)
        elif handler_key == "The Joust":
            self._configure_the_joust_event(event)
        elif handler_key == "Falling":
            self._configure_falling_event(event)
        elif handler_key == "MindBloom":
            self._configure_mind_bloom_event(event)
        elif handler_key == "The Moai Head":
            self._configure_moai_head_event(event)
        elif handler_key == "Mysterious Sphere":
            self._configure_mysterious_sphere_event(event)
        elif handler_key == "SensoryStone":
            self._configure_sensory_stone_event(event)
        elif handler_key == "Tomb of Lord Red Mask":
            self._configure_tomb_red_mask_event(event)
        elif handler_key == "Wheel of Change":
            self._configure_wheel_of_change_event(event)
        elif handler_key == "Winding Halls":
            self._configure_winding_halls_event(event)
        elif handler_key == "Bonfire Elementals":
            self._configure_bonfire_event(event)
        elif handler_key == "SpireHeart":
            self._configure_spire_heart_event(event)

    def _configure_dead_adventurer_event(self, event: "Event") -> None:
        if not getattr(self.state, "dead_adventurer_state", None):
            self.state.dead_adventurer_state = {
                "searches_done": 0,
                "rewards_given": {"gold": False, "nothing": False, "relic": False},
                "encounter_triggered": False,
                "monster_type": None,
                "enemy_index": None,
                "continuation_mode": False,
            }
        da_state = self.state.dead_adventurer_state
        if da_state.get("enemy_index") is None:
            rng = self._misc_rng()
            da_state["enemy_index"] = rng.random_int(2) if rng is not None else 0

        enemy_index = int(da_state.get("enemy_index", 0) or 0)
        if not da_state.get("monster_type"):
            da_state["monster_type"] = ["3 Sentries", "Gremlin Nob", "Lagavulin Event"][enemy_index]

        if da_state.get("continuation_mode"):
            self._update_dead_adventurer_choices(event, da_state)
            return

        encounter_chance = (35 if self.state.ascension >= 15 else 25) + (25 * int(da_state.get("searches_done", 0) or 0))
        encounter_chance = min(100, encounter_chance)
        event.description = self._event_desc(event, 2) + self._event_desc(event, 3 + enemy_index) + self._event_desc(event, 6)
        event.description_cn = self._event_desc(event, 2, cn=True) + self._event_desc(event, 3 + enemy_index, cn=True) + self._event_desc(event, 6, cn=True)
        event.choices = [
            self._make_event_choice(
                description=self._event_opt(event, 0) + str(encounter_chance) + self._event_opt(event, 4),
                description_cn=self._event_opt(event, 0, cn=True) + str(encounter_chance) + self._event_opt(event, 4, cn=True),
                encounter_chance=encounter_chance,
                search_level=1,
            ),
            self._make_event_choice(
                description=self._event_opt(event, 1),
                description_cn=self._event_opt(event, 1, cn=True),
            ),
        ]

    def _configure_golden_idol_event(self, event: "Event") -> None:
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True)),
            self._make_event_choice(description=self._event_opt(event, 1), description_cn=self._event_opt(event, 1, cn=True)),
        ]

    def _configure_golden_wing_event(self, event: "Event") -> None:
        from sts_py.engine.content.card_instance import CardInstance

        can_attack = False
        for card_id in self.state.deck:
            try:
                card = CardInstance(card_id)
            except Exception:
                continue
            if card.card_type.value == "ATTACK" and int(getattr(card, "base_damage", 0) or 0) >= 10:
                can_attack = True
                break

        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(
                description=self._event_opt(event, 0) + "7" + self._event_opt(event, 1),
                description_cn=self._event_opt(event, 0, cn=True) + "7" + self._event_opt(event, 1, cn=True),
                requires_card_removal=True,
            ),
            self._make_event_choice(
                description=(self._event_opt(event, 2) + "50" + self._event_opt(event, 3) + "80" + self._event_opt(event, 4)) if can_attack else (self._event_opt(event, 5) + "10" + self._event_opt(event, 6)),
                description_cn=(self._event_opt(event, 2, cn=True) + "50" + self._event_opt(event, 3, cn=True) + "80" + self._event_opt(event, 4, cn=True)) if can_attack else (self._event_opt(event, 5, cn=True) + "10" + self._event_opt(event, 6, cn=True)),
                enabled=can_attack,
                requires_attack_card=can_attack,
            ),
            self._make_event_choice(description=self._event_opt(event, 7), description_cn=self._event_opt(event, 7, cn=True)),
        ]

    def _configure_world_of_goop_event(self, event: "Event") -> None:
        state = self._event_state()
        gold_loss = int(state.get("gold_loss", 0) or 0)
        if gold_loss <= 0:
            gold_min, gold_max = (35, 75) if self.state.ascension >= 15 else (20, 50)
            rng = self._misc_rng()
            gold_loss = rng.random_int(gold_max - gold_min) + gold_min if rng is not None else gold_min
            gold_loss = min(gold_loss, self.state.player_gold)
            state["gold_loss"] = gold_loss
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(
                description=self._event_opt(event, 0) + "75" + self._event_opt(event, 1) + "11" + self._event_opt(event, 2),
                description_cn=self._event_opt(event, 0, cn=True) + "75" + self._event_opt(event, 1, cn=True) + "11" + self._event_opt(event, 2, cn=True),
                gain_gold=75,
            ),
            self._make_event_choice(
                description=self._event_opt(event, 3) + str(gold_loss) + self._event_opt(event, 4),
                description_cn=self._event_opt(event, 3, cn=True) + str(gold_loss) + self._event_opt(event, 4, cn=True),
            ),
        ]

    def _configure_living_wall_event(self, event: "Event") -> None:
        purgeable_cards = [
            card_id for card_id in self.state.deck
            if self._canonical_card_id(card_id) not in {"AscendersBane", "CurseOfTheBell", "Necronomicurse"}
        ]
        has_upgradable = any(self._upgrade_card(card_id) is not None for card_id in self.state.deck)
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(
                description=self._event_opt(event, 0),
                description_cn=self._event_opt(event, 0, cn=True),
                enabled=bool(purgeable_cards),
                requires_card_removal=bool(purgeable_cards),
            ),
            self._make_event_choice(
                description=self._event_opt(event, 1),
                description_cn=self._event_opt(event, 1, cn=True),
                enabled=bool(purgeable_cards),
                requires_card_transform=bool(purgeable_cards),
            ),
            self._make_event_choice(
                description=self._event_opt(event, 2) if has_upgradable else self._event_opt(event, 7),
                description_cn=self._event_opt(event, 2, cn=True) if has_upgradable else self._event_opt(event, 7, cn=True),
                enabled=has_upgradable,
                requires_card_upgrade=has_upgradable,
            ),
        ]

    def _configure_mushrooms_event(self, event: "Event") -> None:
        heal_amt = max(1, self.state.player_max_hp // 4)
        event.description = self._event_desc(event, 2)
        event.description_cn = self._event_desc(event, 2, cn=True)
        event.choices = [
            self._make_event_choice(
                description=self._event_opt(event, 0),
                description_cn=self._event_opt(event, 0, cn=True),
                trigger_combat=True,
                combat_enemies=["FungiBeast", "FungiBeast", "FungiBeast"],
            ),
            self._make_event_choice(
                description=self._event_opt(event, 1) + str(heal_amt) + self._event_opt(event, 2),
                description_cn=self._event_opt(event, 1, cn=True) + str(heal_amt) + self._event_opt(event, 2, cn=True),
            ),
        ]

    def _configure_scrap_ooze_event(self, event: "Event") -> None:
        if not getattr(self.state, "scrap_ooze_state", None):
            self.state.scrap_ooze_state = {"attempts": 0}
        self._update_scrap_ooze_choices(event, self.state.scrap_ooze_state)

    def _configure_shining_light_event(self, event: "Event") -> None:
        import math

        damage = int(math.floor(self.state.player_max_hp * (0.3 if self.state.ascension >= 15 else 0.2) + 0.5))
        has_upgradable = any(self._upgrade_card(card_id) is not None for card_id in self.state.deck)
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(
                description=self._event_opt(event, 0) + str(damage) + self._event_opt(event, 1) if has_upgradable else self._event_opt(event, 3),
                description_cn=self._event_opt(event, 0, cn=True) + str(damage) + self._event_opt(event, 1, cn=True) if has_upgradable else self._event_opt(event, 3, cn=True),
                enabled=has_upgradable,
            ),
            self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True)),
        ]

    def _configure_addict_event(self, event: "Event") -> None:
        gold_required = 85
        has_gold = self.state.player_gold >= gold_required
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(
                description=(self._event_opt(event, 0) + str(gold_required) + self._event_opt(event, 1)) if has_gold else (self._event_opt(event, 2) + str(gold_required) + self._event_opt(event, 3)),
                description_cn=(self._event_opt(event, 0, cn=True) + str(gold_required) + self._event_opt(event, 1, cn=True)) if has_gold else (self._event_opt(event, 2, cn=True) + str(gold_required) + self._event_opt(event, 3, cn=True)),
                enabled=has_gold,
                disabled_reason="Requires 85 Gold.",
                disabled_reason_cn="需要：85金币。",
            ),
            self._make_event_choice(
                description=self._event_opt(event, 4),
                description_cn=self._event_opt(event, 4, cn=True),
            ),
            self._make_event_choice(
                description=self._event_opt(event, 5),
                description_cn=self._event_opt(event, 5, cn=True),
            ),
        ]

    def _configure_back_to_basics_event(self, event: "Event") -> None:
        from sts_py.engine.run.events import EventChoice

        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            EventChoice(
                description=self._event_opt(event, 0),
                description_cn=self._event_opt(event, 0, cn=True),
                requires_card_removal=True,
            ),
            EventChoice(
                description=self._event_opt(event, 1),
                description_cn=self._event_opt(event, 1, cn=True),
            ),
        ]

    def _configure_drug_dealer_event(self, event: "Event") -> None:
        purgeable_cards = [card_id for card_id in self.state.deck if card_id not in {"AscendersBane", "CurseOfTheBell", "Necronomicurse"}]
        can_transform = len(purgeable_cards) >= 2
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True)),
            self._make_event_choice(
                description=self._event_opt(event, 1) if can_transform else self._event_opt(event, 4),
                description_cn=self._event_opt(event, 1, cn=True) if can_transform else self._event_opt(event, 4, cn=True),
                enabled=can_transform,
                disabled_reason="Requires: 2 or more cards in deck.",
                disabled_reason_cn="需要：牌组中至少有2张牌。",
            ),
            self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True)),
        ]

    def _configure_big_fish_event(self, event: "Event") -> None:
        heal_amt = max(1, self.state.player_max_hp // 3)
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(
                description=self._event_opt(event, 0) + str(heal_amt) + self._event_opt(event, 1),
                description_cn=self._event_opt(event, 0, cn=True) + str(heal_amt) + self._event_opt(event, 1, cn=True),
            ),
            self._make_event_choice(
                description=self._event_opt(event, 2) + "5" + self._event_opt(event, 3),
                description_cn=self._event_opt(event, 2, cn=True) + "5" + self._event_opt(event, 3, cn=True),
            ),
            self._make_event_choice(description=self._event_opt(event, 4), description_cn=self._event_opt(event, 4, cn=True)),
        ]

    def _configure_cleric_event(self, event: "Event") -> None:
        heal_amt = int(self.state.player_max_hp * 0.25)
        purify_cost = 75 if self.state.ascension >= 15 else 50
        has_purgeable = any(self._canonical_card_id(card_id) not in {"AscendersBane", "CurseOfTheBell", "Necronomicurse"} for card_id in self.state.deck)
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        heal_enabled = self.state.player_gold >= 35
        purify_enabled = self.state.player_gold >= purify_cost and has_purgeable
        event.choices = [
            self._make_event_choice(
                description=(self._event_opt(event, 0) + str(heal_amt) + self._event_opt(event, 8)) if heal_enabled else (self._event_opt(event, 1) + "35" + self._event_opt(event, 2)),
                description_cn=(self._event_opt(event, 0, cn=True) + str(heal_amt) + self._event_opt(event, 8, cn=True)) if heal_enabled else (self._event_opt(event, 1, cn=True) + "35" + self._event_opt(event, 2, cn=True)),
                enabled=heal_enabled,
            ),
            self._make_event_choice(
                description=(self._event_opt(event, 3) + str(purify_cost) + self._event_opt(event, 4)) if self.state.player_gold >= 50 else self._event_opt(event, 5),
                description_cn=(self._event_opt(event, 3, cn=True) + str(purify_cost) + self._event_opt(event, 4, cn=True)) if self.state.player_gold >= 50 else self._event_opt(event, 5, cn=True),
                enabled=purify_enabled,
            ),
            self._make_event_choice(description=self._event_opt(event, 6), description_cn=self._event_opt(event, 6, cn=True)),
        ]

    def _configure_beggar_event(self, event: "Event") -> None:
        has_gold = self.state.player_gold >= 75
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(
                description=(self._event_opt(event, 0) + "75" + self._event_opt(event, 1)) if has_gold else (self._event_opt(event, 2) + "75" + self._event_opt(event, 3)),
                description_cn=(self._event_opt(event, 0, cn=True) + "75" + self._event_opt(event, 1, cn=True)) if has_gold else (self._event_opt(event, 2, cn=True) + "75" + self._event_opt(event, 3, cn=True)),
                enabled=has_gold,
            ),
            self._make_event_choice(description=self._event_opt(event, 5), description_cn=self._event_opt(event, 5, cn=True)),
        ]

    def _configure_liars_game_event(self, event: "Event") -> None:
        gold_reward = 150 if self.state.ascension >= 15 else 175
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(
                description=self._event_opt(event, 0) + str(gold_reward) + self._event_opt(event, 1),
                description_cn=self._event_opt(event, 0, cn=True) + str(gold_reward) + self._event_opt(event, 1, cn=True),
            ),
            self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True)),
        ]

    def _configure_cursed_tome_event(self, event: "Event") -> None:
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True)),
            self._make_event_choice(description=self._event_opt(event, 7), description_cn=self._event_opt(event, 7, cn=True)),
        ]

    def _configure_forgotten_altar_event(self, event: "Event") -> None:
        hp_loss = max(1, round(self.state.player_max_hp * (0.35 if self.state.ascension >= 15 else 0.25)))
        has_idol = self._has_relic("GoldenIdol")
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(
                description=self._event_opt(event, 0 if has_idol else 1),
                description_cn=self._event_opt(event, 0 if has_idol else 1, cn=True),
            ),
            self._make_event_choice(
                description=self._event_opt(event, 2) + "5" + self._event_opt(event, 3) + str(hp_loss) + self._event_opt(event, 4),
                description_cn=self._event_opt(event, 2, cn=True) + "5" + self._event_opt(event, 3, cn=True) + str(hp_loss) + self._event_opt(event, 4, cn=True),
            ),
            self._make_event_choice(description=self._event_opt(event, 6), description_cn=self._event_opt(event, 6, cn=True)),
        ]

    def _configure_masked_bandits_event(self, event: "Event") -> None:
        event.description = self._event_desc(event, 4)
        event.description_cn = self._event_desc(event, 4, cn=True)
        event.choices = [
            self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True)),
            self._make_event_choice(description=self._event_opt(event, 1), description_cn=self._event_opt(event, 1, cn=True)),
        ]

    def _configure_nest_event(self, event: "Event") -> None:
        event_state = self._event_state()
        if event_state.get("stage") == "choice":
            gold_gain = 50 if self.state.ascension >= 15 else 99
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
            event.choices = [
                self._make_event_choice(
                    description=self._event_opt(event, 2) + str(gold_gain) + self._event_opt(event, 3),
                    description_cn=self._event_opt(event, 2, cn=True) + str(gold_gain) + self._event_opt(event, 3, cn=True),
                ),
                self._make_event_choice(
                    description=self._event_opt(event, 0) + "6" + self._event_opt(event, 1),
                    description_cn=self._event_opt(event, 0, cn=True) + "6" + self._event_opt(event, 1, cn=True),
                ),
            ]
            return
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [self._make_event_choice(description=self._event_opt(event, 5), description_cn=self._event_opt(event, 5, cn=True))]

    def _configure_library_event(self, event: "Event") -> None:
        heal_amt = round(self.state.player_max_hp * (0.2 if self.state.ascension >= 15 else 0.33))
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True)),
            self._make_event_choice(
                description=self._event_opt(event, 1) + str(heal_amt) + self._event_opt(event, 2),
                description_cn=self._event_opt(event, 1, cn=True) + str(heal_amt) + self._event_opt(event, 2, cn=True),
            ),
        ]

    def _configure_mausoleum_event(self, event: "Event") -> None:
        percent = 100 if self.state.ascension >= 15 else 50
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(
                description=self._event_opt(event, 0) + str(percent) + self._event_opt(event, 1),
                description_cn=self._event_opt(event, 0, cn=True) + str(percent) + self._event_opt(event, 1, cn=True),
            ),
            self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True)),
        ]

    def _configure_colosseum_event(self, event: "Event") -> None:
        event_state = self._event_state()
        stage = str(event_state.get("stage", "intro"))
        if stage == "post_slavers":
            event.description = self._event_desc(event, 4)
            event.description_cn = self._event_desc(event, 4, cn=True)
            event.choices = [
                self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True)),
                self._make_event_choice(description=self._event_opt(event, 3), description_cn=self._event_opt(event, 3, cn=True)),
            ]
            return
        if stage == "fight":
            event.description = self._event_desc(event, 1) + self._event_desc(event, 2) + "4200" + self._event_desc(event, 3)
            event.description_cn = self._event_desc(event, 1, cn=True) + self._event_desc(event, 2, cn=True) + "4200" + self._event_desc(event, 3, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 1), description_cn=self._event_opt(event, 1, cn=True))]
            return
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True))]

    def _configure_designer_event(self, event: "Event") -> None:
        rng = self._misc_rng()
        adjustment_upgrades_one = bool(rng.random_boolean() if rng is not None else True)
        clean_up_removes_cards = bool(rng.random_boolean() if rng is not None else True)
        if self.state.ascension >= 15:
            adjust_cost, clean_up_cost, full_service_cost, hp_loss = 50, 75, 110, 5
        else:
            adjust_cost, clean_up_cost, full_service_cost, hp_loss = 40, 60, 90, 3
        state = self._event_state()
        state["designer"] = {
            "stage": "intro",
            "adjustment_upgrades_one": adjustment_upgrades_one,
            "clean_up_removes_cards": clean_up_removes_cards,
            "adjust_cost": adjust_cost,
            "clean_up_cost": clean_up_cost,
            "full_service_cost": full_service_cost,
            "hp_loss": hp_loss,
        }
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True))]

    def _configure_ghosts_event(self, event: "Event") -> None:
        hp_loss = min(self.state.player_max_hp - 1, int((self.state.player_max_hp + 1) / 2))
        accept_en = (self._event_opt(event, 3) if self.state.ascension >= 15 else self._event_opt(event, 0)) + str(hp_loss) + self._event_opt(event, 1)
        accept_cn = (self._event_opt(event, 3, cn=True) if self.state.ascension >= 15 else self._event_opt(event, 0, cn=True)) + str(hp_loss) + self._event_opt(event, 1, cn=True)
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices[0].description = accept_en
        event.choices[0].description_cn = accept_cn
        if len(event.choices) > 1:
            event.choices[1].description = self._event_opt(event, 2)
            event.choices[1].description_cn = self._event_opt(event, 2, cn=True)

    def _configure_vampires_event(self, event: "Event") -> None:
        max_hp_loss = min(self.state.player_max_hp - 1, int((self.state.player_max_hp * 0.3) + 0.999999))
        has_vial = self._has_relic("BloodVial")
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(
                description=self._event_opt(event, 0) + str(max_hp_loss) + self._event_opt(event, 1),
                description_cn=self._event_opt(event, 0, cn=True) + str(max_hp_loss) + self._event_opt(event, 1, cn=True),
            ),
        ]
        if has_vial:
            event.choices.append(
                self._make_event_choice(
                    description=self._event_opt(event, 3) + "Blood Vial" + self._event_opt(event, 4),
                    description_cn=self._event_opt(event, 3, cn=True) + "Blood Vial" + self._event_opt(event, 4, cn=True),
                )
            )
        event.choices.append(
            self._make_event_choice(
                description=self._event_opt(event, 2),
                description_cn=self._event_opt(event, 2, cn=True),
            )
        )

    def _configure_golden_shrine_event(self, event: "Event") -> None:
        gold_amount = 50 if self.state.ascension >= 15 else 100
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(
                description=self._event_opt(event, 0) + str(gold_amount) + self._event_opt(event, 1),
                description_cn=self._event_opt(event, 0, cn=True) + str(gold_amount) + self._event_opt(event, 1, cn=True),
            ),
            self._make_event_choice(
                description=self._event_opt(event, 2),
                description_cn=self._event_opt(event, 2, cn=True),
            ),
            self._make_event_choice(
                description=self._event_opt(event, 3),
                description_cn=self._event_opt(event, 3, cn=True),
            ),
        ]

    def _configure_duplicator_event(self, event: "Event") -> None:
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True)),
            self._make_event_choice(description=self._event_opt(event, 1), description_cn=self._event_opt(event, 1, cn=True)),
        ]

    def _configure_purifier_event(self, event: "Event") -> None:
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True)),
            self._make_event_choice(description=self._event_opt(event, 1), description_cn=self._event_opt(event, 1, cn=True)),
        ]

    def _configure_upgrade_shrine_event(self, event: "Event") -> None:
        has_upgrades = any(self._upgrade_card(card_id) is not None for card_id in self.state.deck)
        first_desc = self._event_opt(event, 0) if has_upgrades else self._event_opt(event, 3)
        first_desc_cn = self._event_opt(event, 0, cn=True) if has_upgrades else self._event_opt(event, 3, cn=True)
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(
                description=first_desc,
                description_cn=first_desc_cn,
                enabled=has_upgrades,
                disabled_reason="Requires: Upgradeable Cards",
                disabled_reason_cn="需要：可以升级的牌",
            ),
            self._make_event_choice(description=self._event_opt(event, 1), description_cn=self._event_opt(event, 1, cn=True)),
        ]

    def _configure_transmorgrifier_event(self, event: "Event") -> None:
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True)),
            self._make_event_choice(description=self._event_opt(event, 1), description_cn=self._event_opt(event, 1, cn=True)),
        ]

    def _configure_lab_event(self, event: "Event") -> None:
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True))]

    def _configure_nloth_event(self, event: "Event") -> None:
        rng = self._misc_rng()
        relics = list(self.state.relics)
        if rng is not None:
            for idx in range(len(relics) - 1, 0, -1):
                swap_idx = rng.random_int(idx)
                relics[idx], relics[swap_idx] = relics[swap_idx], relics[idx]
        choices = relics[:2]
        state = self._event_state()
        state["nloth_choices"] = list(choices)
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(
                description=self._event_opt(event, 0) + choices[0] + self._event_opt(event, 1),
                description_cn=self._event_opt(event, 0, cn=True) + choices[0] + self._event_opt(event, 1, cn=True),
            ),
            self._make_event_choice(
                description=self._event_opt(event, 0) + choices[1] + self._event_opt(event, 1),
                description_cn=self._event_opt(event, 0, cn=True) + choices[1] + self._event_opt(event, 1, cn=True),
            ),
            self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True)),
        ]

    def _configure_secret_portal_event(self, event: "Event") -> None:
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True)),
            self._make_event_choice(description=self._event_opt(event, 1), description_cn=self._event_opt(event, 1, cn=True)),
        ]

    def _configure_we_meet_again_event(self, event: "Event") -> None:
        rng = self._misc_rng()
        potion_ids = [p for p in self.state.potions if p != "EmptyPotionSlot"]
        potion_id = None
        if potion_ids:
            potion_id = potion_ids[(rng.random_int(len(potion_ids) - 1) if rng is not None else 0)]
        non_basic_cards = [
            card_id for card_id in self.state.deck
            if not self._canonical_card_id(card_id).startswith(("Strike", "Defend"))
            and self._canonical_card_id(card_id) not in {"AscendersBane", "CurseOfTheBell", "Necronomicurse"}
            and self._canonical_card_id(card_id) not in {"Curse", "Doubt", "Regret", "Shame", "Pain", "Normality", "Parasite", "Clumsy", "Writhe", "Decay", "Injury"}
        ]
        card_id = None
        if non_basic_cards:
            card_id = non_basic_cards[(rng.random_int(len(non_basic_cards) - 1) if rng is not None else 0)]
        gold_amount = 0
        if self.state.player_gold >= 50:
            upper = min(150, self.state.player_gold)
            gold_amount = (rng.random_int(upper - 50) + 50) if (rng is not None and upper > 50) else upper
        state = self._event_state()
        state["we_meet_again"] = {"potion_id": potion_id, "card_id": card_id, "gold_amount": gold_amount}
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(
                description=(self._event_opt(event, 0) + str(potion_id) + self._event_opt(event, 6)) if potion_id else self._event_opt(event, 1),
                description_cn=(self._event_opt(event, 0, cn=True) + str(potion_id) + self._event_opt(event, 6, cn=True)) if potion_id else self._event_opt(event, 1, cn=True),
                enabled=potion_id is not None,
                disabled_reason="Requires: Potion.",
                disabled_reason_cn="需要：药水。",
            ),
            self._make_event_choice(
                description=(self._event_opt(event, 2) + str(gold_amount) + self._event_opt(event, 9) + self._event_opt(event, 6)) if gold_amount else self._event_opt(event, 3),
                description_cn=(self._event_opt(event, 2, cn=True) + str(gold_amount) + self._event_opt(event, 9, cn=True) + self._event_opt(event, 6, cn=True)) if gold_amount else self._event_opt(event, 3, cn=True),
                enabled=gold_amount > 0,
                disabled_reason="Requires: At least 50 Gold.",
                disabled_reason_cn="需要：至少50金币。",
            ),
            self._make_event_choice(
                description=(self._event_opt(event, 4) + str(card_id) + self._event_opt(event, 6)) if card_id else self._event_opt(event, 5),
                description_cn=(self._event_opt(event, 4, cn=True) + str(card_id) + self._event_opt(event, 6, cn=True)) if card_id else self._event_opt(event, 5, cn=True),
                enabled=card_id is not None,
                disabled_reason="Requires: Card.",
                disabled_reason_cn="需要：卡牌。",
            ),
            self._make_event_choice(description=self._event_opt(event, 7), description_cn=self._event_opt(event, 7, cn=True)),
        ]

    def _configure_woman_in_blue_event(self, event: "Event") -> None:
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        leave_desc = self._event_opt(event, 4) if self.state.ascension < 15 else (self._event_opt(event, 5) + str(max(1, int((self.state.player_max_hp * 0.05) + 0.999999))) + self._event_opt(event, 6))
        leave_desc_cn = self._event_opt(event, 4, cn=True) if self.state.ascension < 15 else (self._event_opt(event, 5, cn=True) + str(max(1, int((self.state.player_max_hp * 0.05) + 0.999999))) + self._event_opt(event, 6, cn=True))
        event.choices = [
            self._make_event_choice(description=self._event_opt(event, 0) + "20" + self._event_opt(event, 3), description_cn=self._event_opt(event, 0, cn=True) + "20" + self._event_opt(event, 3, cn=True)),
            self._make_event_choice(description=self._event_opt(event, 1) + "30" + self._event_opt(event, 3), description_cn=self._event_opt(event, 1, cn=True) + "30" + self._event_opt(event, 3, cn=True)),
            self._make_event_choice(description=self._event_opt(event, 2) + "40" + self._event_opt(event, 3), description_cn=self._event_opt(event, 2, cn=True) + "40" + self._event_opt(event, 3, cn=True)),
            self._make_event_choice(description=leave_desc, description_cn=leave_desc_cn),
        ]

    def _configure_the_joust_event(self, event: "Event") -> None:
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True))]

    def _configure_mind_bloom_event(self, event: "Event") -> None:
        rich_branch = (self.state.floor % 50) <= 40
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True)),
            self._make_event_choice(description=self._event_opt(event, 3), description_cn=self._event_opt(event, 3, cn=True)),
            self._make_event_choice(
                description=self._event_opt(event, 1 if rich_branch else 2),
                description_cn=self._event_opt(event, 1 if rich_branch else 2, cn=True),
            ),
        ]

    def _configure_falling_event(self, event: "Event") -> None:
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True))]

    def _configure_mysterious_sphere_event(self, event: "Event") -> None:
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True)),
            self._make_event_choice(description=self._event_opt(event, 1), description_cn=self._event_opt(event, 1, cn=True)),
        ]

    def _configure_bonfire_event(self, event: "Event") -> None:
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True))]

    def _configure_face_trader_event(self, event: "Event") -> None:
        damage = max(1, self.state.player_max_hp // 10)
        gold_reward = 50 if self.state.ascension >= 15 else 75
        event_state = self._event_state()
        if str(event_state.get("stage", "intro")) == "main":
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
            event.choices = [
                self._make_event_choice(
                    description=self._event_opt(event, 0) + str(damage) + self._event_opt(event, 5) + str(gold_reward) + self._event_opt(event, 1),
                    description_cn=self._event_opt(event, 0, cn=True) + str(damage) + self._event_opt(event, 5, cn=True) + str(gold_reward) + self._event_opt(event, 1, cn=True),
                ),
                self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True)),
                self._make_event_choice(description=self._event_opt(event, 3), description_cn=self._event_opt(event, 3, cn=True)),
            ]
            return
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [self._make_event_choice(description=self._event_opt(event, 4), description_cn=self._event_opt(event, 4, cn=True))]

    def _configure_fountain_event(self, event: "Event") -> None:
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True)),
            self._make_event_choice(description=self._event_opt(event, 1), description_cn=self._event_opt(event, 1, cn=True)),
        ]

    def _configure_knowing_skull_event(self, event: "Event") -> None:
        event_state = self._event_state()
        if str(event_state.get("stage", "intro")) == "ask":
            costs = event_state.setdefault("costs", {"potion": 6, "gold": 6, "card": 6, "leave": 6})
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
            event.choices = [
                self._make_event_choice(
                    description=self._event_opt(event, 4) + str(costs["potion"]) + self._event_opt(event, 1),
                    description_cn=self._event_opt(event, 4, cn=True) + str(costs["potion"]) + self._event_opt(event, 1, cn=True),
                ),
                self._make_event_choice(
                    description=self._event_opt(event, 5) + "90" + self._event_opt(event, 6) + str(costs["gold"]) + self._event_opt(event, 1),
                    description_cn=self._event_opt(event, 5, cn=True) + "90" + self._event_opt(event, 6, cn=True) + str(costs["gold"]) + self._event_opt(event, 1, cn=True),
                ),
                self._make_event_choice(
                    description=self._event_opt(event, 3) + str(costs["card"]) + self._event_opt(event, 1),
                    description_cn=self._event_opt(event, 3, cn=True) + str(costs["card"]) + self._event_opt(event, 1, cn=True),
                ),
                self._make_event_choice(
                    description=self._event_opt(event, 7) + str(costs["leave"]) + self._event_opt(event, 1),
                    description_cn=self._event_opt(event, 7, cn=True) + str(costs["leave"]) + self._event_opt(event, 1, cn=True),
                ),
            ]
            return
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True))]

    def _configure_accursed_blacksmith_event(self, event: "Event") -> None:
        has_upgrades = any(self._upgrade_card(card_id) is not None for card_id in self.state.deck)
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(
                description=self._event_opt(event, 0) if has_upgrades else self._event_opt(event, 4),
                description_cn=self._event_opt(event, 0, cn=True) if has_upgrades else self._event_opt(event, 4, cn=True),
                enabled=has_upgrades,
            ),
            self._make_event_choice(description=self._event_opt(event, 1), description_cn=self._event_opt(event, 1, cn=True)),
            self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True)),
        ]

    def _configure_match_and_keep_event(self, event: "Event") -> None:
        event_state = self._event_state()
        stage = str(event_state.get("stage", "intro"))
        if stage == "rules":
            event.description = self._event_desc(event, 0)
            event.description_cn = self._event_desc(event, 0, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True))]
            return
        if stage == "complete":
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 1), description_cn=self._event_opt(event, 1, cn=True))]
            return
        event.description = self._event_desc(event, 2)
        event.description_cn = self._event_desc(event, 2, cn=True)
        event.choices = [self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True))]

    def _configure_note_for_yourself_event(self, event: "Event") -> None:
        payload = self._normalize_note_for_yourself_payload(self.state.note_for_yourself_payload)
        from sts_py.engine.content.card_instance import format_runtime_card_id

        card_runtime_id = format_runtime_card_id(payload["card_id"], times_upgraded=int(payload["upgrades"]))
        event_state = self._event_state()
        if str(event_state.get("stage", "intro")) == "choose":
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
            event.choices = [
                self._make_event_choice(
                    description=self._event_opt(event, 1) + card_runtime_id + self._event_opt(event, 2),
                    description_cn=self._event_opt(event, 1, cn=True) + card_runtime_id + self._event_opt(event, 2, cn=True),
                ),
                self._make_event_choice(description=self._event_opt(event, 3), description_cn=self._event_opt(event, 3, cn=True)),
            ]
            return
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True))]

    def _configure_moai_head_event(self, event: "Event") -> None:
        hp_loss = max(1, round(self.state.player_max_hp * (0.18 if self.state.ascension >= 15 else 0.125)))
        has_idol = self._has_relic("GoldenIdol")
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [
            self._make_event_choice(
                description=self._event_opt(event, 0) + str(hp_loss) + self._event_opt(event, 1),
                description_cn=self._event_opt(event, 0, cn=True) + str(hp_loss) + self._event_opt(event, 1, cn=True),
            ),
            self._make_event_choice(
                description=self._event_opt(event, 2) if has_idol else self._event_opt(event, 3),
                description_cn=self._event_opt(event, 2, cn=True) if has_idol else self._event_opt(event, 3, cn=True),
                enabled=has_idol,
            ),
            self._make_event_choice(description=self._event_opt(event, 4), description_cn=self._event_opt(event, 4, cn=True)),
        ]

    def _configure_sensory_stone_event(self, event: "Event") -> None:
        event_state = self._event_state()
        if str(event_state.get("stage", "intro")) == "choice":
            event.description = str(event_state.get("memory_description", "") or self._event_desc(event, 2))
            event.description_cn = str(event_state.get("memory_description_cn", "") or "")
            event.choices = [
                self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True)),
                self._make_event_choice(
                    description=self._event_opt(event, 1) + "5" + self._event_opt(event, 3),
                    description_cn=self._event_opt(event, 1, cn=True) + "5" + self._event_opt(event, 3, cn=True),
                ),
                self._make_event_choice(
                    description=self._event_opt(event, 2) + "10" + self._event_opt(event, 3),
                    description_cn=self._event_opt(event, 2, cn=True) + "10" + self._event_opt(event, 3, cn=True),
                ),
            ]
            return
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [self._make_event_choice(description=self._event_opt(event, 5), description_cn=self._event_opt(event, 5, cn=True))]

    def _configure_tomb_red_mask_event(self, event: "Event") -> None:
        has_mask = self._has_relic("RedMask")
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        if has_mask:
            event.choices = [
                self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True)),
                self._make_event_choice(description=self._event_opt(event, 4), description_cn=self._event_opt(event, 4, cn=True)),
            ]
            return
        event.choices = [
            self._make_event_choice(description=self._event_opt(event, 1), description_cn=self._event_opt(event, 1, cn=True), enabled=False),
            self._make_event_choice(
                description=self._event_opt(event, 2) + str(self.state.player_gold) + self._event_opt(event, 3),
                description_cn=self._event_opt(event, 2, cn=True) + str(self.state.player_gold) + self._event_opt(event, 3, cn=True),
            ),
            self._make_event_choice(description=self._event_opt(event, 4), description_cn=self._event_opt(event, 4, cn=True)),
        ]

    def _configure_wheel_of_change_event(self, event: "Event") -> None:
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True))]

    def _configure_winding_halls_event(self, event: "Event") -> None:
        event_state = self._event_state()
        if str(event_state.get("stage", "intro")) == "choice":
            hp_amt = max(1, round(self.state.player_max_hp * (0.18 if self.state.ascension >= 15 else 0.125)))
            heal_amt = max(1, round(self.state.player_max_hp * (0.2 if self.state.ascension >= 15 else 0.25)))
            max_hp_amt = max(1, round(self.state.player_max_hp * 0.05))
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
            event.choices = [
                self._make_event_choice(
                    description=self._event_opt(event, 1) + str(hp_amt) + self._event_opt(event, 2),
                    description_cn=self._event_opt(event, 1, cn=True) + str(hp_amt) + self._event_opt(event, 2, cn=True),
                ),
                self._make_event_choice(
                    description=self._event_opt(event, 3) + str(heal_amt) + self._event_opt(event, 5),
                    description_cn=self._event_opt(event, 3, cn=True) + str(heal_amt) + self._event_opt(event, 5, cn=True),
                ),
                self._make_event_choice(
                    description=self._event_opt(event, 6) + str(max_hp_amt) + self._event_opt(event, 7),
                    description_cn=self._event_opt(event, 6, cn=True) + str(max_hp_amt) + self._event_opt(event, 7, cn=True),
                ),
            ]
            return
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True))]

    def _configure_spire_heart_event(self, event: "Event") -> None:
        self.state.spire_heart_meta = {
            "can_enter_final_act": bool(self.has_all_act4_keys()),
            "damage_dealt": int(self.state.spire_heart_meta.get("damage_dealt", 0) or 0),
            "total_damage_dealt": int(self.state.spire_heart_meta.get("total_damage_dealt", 0) or 0),
        }
        event.description = self._event_desc(event, 0)
        event.description_cn = self._event_desc(event, 0, cn=True)
        event.choices = [self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True))]

    def _set_current_event(self, event: "Event") -> None:
        self._current_event = event
        self.state.current_event_id = str(getattr(event, "event_id", getattr(event, "id", "")) or "")
        self.state.current_event_key = str(getattr(event, "event_key", "") or "")
        self._prepare_event_for_runtime(event)
        self.state.phase = RunPhase.EVENT

    def _clear_current_event(self) -> None:
        self._current_event = None
        self.state.current_event_id = None
        self.state.current_event_key = None
        self.state.current_event_state = {}
        self.state.pending_card_choice = None

    def _has_event_relic(self, relic_id: str) -> bool:
        return relic_id in set(getattr(self.state, "relics", []) or [])

    def _is_event_key_available(self, event_key: str, *, shrine: bool) -> bool:
        if event_key == "Dead Adventurer" and self.state.floor <= 6:
            return False
        if event_key == "Mushrooms" and self.state.floor <= 6:
            return False
        if event_key == "The Cleric" and self.state.player_gold < 35:
            return False
        if event_key == "Beggar" and self.state.player_gold < 75:
            return False
        if event_key == "Colosseum":
            room = self.get_current_room()
            total_rows = max(1, len({node.y for node in self.state.map_nodes}) or 1)
            room_depth = int(getattr(room, "y", 0) or 0)
            return room is not None and room_depth > (total_rows // 2)
        if event_key == "The Moai Head":
            has_idol = self._has_event_relic("GoldenIdol")
            hp_ratio = float(self.state.player_hp) / float(max(1, self.state.player_max_hp))
            return has_idol or hp_ratio <= 0.5
        if not shrine:
            return True
        if event_key == "Fountain of Cleansing":
            from sts_py.engine.run.events import _is_curse_card

            return any(_is_curse_card(card_id) for card_id in self.state.deck)
        if event_key == "Designer":
            return self.state.act in {2, 3} and self.state.player_gold >= 75
        if event_key == "Duplicator":
            return self.state.act in {2, 3}
        if event_key == "FaceTrader":
            return self.state.act in {1, 2}
        if event_key == "Knowing Skull":
            return self.state.act == 2 and self.state.player_hp > 12
        if event_key == "N'loth":
            return self.state.act == 2 and len(self.state.relics) >= 2
        if event_key == "The Joust":
            return self.state.act == 2 and self.state.player_gold >= 50
        if event_key == "The Woman in Blue":
            return self.state.player_gold >= 50
        if event_key == "SecretPortal":
            return self.state.act == 3 and float(getattr(self.state, "playtime_seconds", 0.0) or 0.0) >= 800.0
        if event_key == "NoteForYourself":
            return self._is_note_for_yourself_available()
        return True

    def _draw_event_key_from_pool(self, *, shrine: bool) -> str | None:
        if self.state.rng is None:
            return None
        pool = list(self.state.shrine_list if shrine else self.state.event_list)
        if shrine:
            for event_key in self.state.special_one_time_event_list:
                if self._is_event_key_available(event_key, shrine=True):
                    pool.append(event_key)
        else:
            pool = [event_key for event_key in pool if self._is_event_key_available(event_key, shrine=False)]

        if not pool:
            return None

        event_key = pool[self.state.rng.event_rng.random_int(len(pool) - 1)]
        if shrine:
            if event_key in self.state.shrine_list:
                self.state.shrine_list.remove(event_key)
            elif event_key in self.state.special_one_time_event_list:
                self.state.special_one_time_event_list.remove(event_key)
        else:
            if event_key in self.state.event_list:
                self.state.event_list.remove(event_key)
        return event_key

    def _generate_event_key(self) -> str | None:
        from sts_py.engine.run.events import SHRINE_CHANCE

        if self.state.rng is None:
            return None
        if self.state.rng.event_rng.random_float() < SHRINE_CHANCE:
            if self.state.shrine_list or self.state.special_one_time_event_list:
                event_key = self._draw_event_key_from_pool(shrine=True)
                if event_key is not None:
                    return event_key
            return self._draw_event_key_from_pool(shrine=False)
        event_key = self._draw_event_key_from_pool(shrine=False)
        if event_key is None:
            event_key = self._draw_event_key_from_pool(shrine=True)
        return event_key

    def _legacy_init_neow_unused(self) -> None:
        self.state.pending_neow_choice = None
        self.state.neow_options = [self._build_neow_option(category) for category in range(4)]

    def _neow_random_index(self, size: int) -> int:
        if size <= 1:
            return 0
        if self._neow_rng is None:
            self._neow_rng = MutableRNG.from_seed(self.state.seed, rng_type="neowRng")
        return self._neow_rng.random_int(size - 1)

    def _neow_random_boolean(self, chance: float) -> bool:
        if self._neow_rng is None:
            self._neow_rng = MutableRNG.from_seed(self.state.seed, rng_type="neowRng")
        return self._neow_rng.random_boolean_chance(chance)

    def _neow_hp_bonus(self, percent: int) -> int:
        return int(self.state.player_max_hp * (percent / 100.0))

    def _neow_percent_damage(self) -> int:
        return int(self.state.player_hp / 10) * 3

    def _legacy_neow_reward_text_unused(self, reward_type: str, reward_value: int) -> str:
        if reward_type == "THREE_CARDS":
            return "从 3 张牌中选择 1 张"
        if reward_type == "ONE_RANDOM_RARE_CARD":
            return "获得 1 张随机稀有牌"
        if reward_type == "REMOVE_CARD":
            return "移除 1 张牌"
        if reward_type == "UPGRADE_CARD":
            return "升级 1 张牌"
        if reward_type == "TRANSFORM_CARD":
            return "变形 1 张牌"
        if reward_type == "RANDOM_COLORLESS":
            return "从 3 张随机无色牌中选择 1 张"
        if reward_type == "THREE_SMALL_POTIONS":
            return "获得 3 瓶药水"
        if reward_type == "RANDOM_COMMON_RELIC":
            return "获得 1 件随机普通遗物"
        if reward_type == "TEN_PERCENT_HP_BONUS":
            return f"最大生命 +{reward_value}"
        if reward_type == "THREE_ENEMY_KILL":
            return "获得涅奥的悲恸"
        if reward_type == "HUNDRED_GOLD":
            return "获得 100 金币"
        if reward_type == "RANDOM_COLORLESS_2":
            return "从 3 张随机稀有无色牌中选择 1 张"
        if reward_type == "REMOVE_TWO":
            return "移除 2 张牌"
        if reward_type == "ONE_RARE_RELIC":
            return "获得 1 件随机稀有遗物"
        if reward_type == "THREE_RARE_CARDS":
            return "从 3 张稀有牌中选择 1 张"
        if reward_type == "TWO_FIFTY_GOLD":
            return "获得 250 金币"
        if reward_type == "TRANSFORM_TWO_CARDS":
            return "变形 2 张牌"
        if reward_type == "TWENTY_PERCENT_HP_BONUS":
            return f"最大生命 +{reward_value}"
        if reward_type == "BOSS_RELIC":
            return "将起始遗物替换为 1 件首领遗物"
        return reward_type

    def _legacy_neow_drawback_text_unused(self, drawback: str, drawback_value: int) -> str:
        if drawback == "NONE":
            return ""
        if drawback == "TEN_PERCENT_HP_LOSS":
            return f"代价：失去 {drawback_value} 点最大生命"
        if drawback == "NO_GOLD":
            return "代价：失去全部金币"
        if drawback == "CURSE":
            return "代价：获得 1 张诅咒"
        if drawback == "PERCENT_DAMAGE":
            return f"代价：失去 {drawback_value} 点生命"
        return drawback

    def _legacy_build_neow_option_unused(self, category: int) -> dict[str, Any]:
        reward_value = 0
        drawback = "NONE"
        drawback_value = 0

        if category == 0:
            reward_types = [
                "THREE_CARDS",
                "ONE_RANDOM_RARE_CARD",
                "REMOVE_CARD",
                "UPGRADE_CARD",
                "TRANSFORM_CARD",
                "RANDOM_COLORLESS",
            ]
        elif category == 1:
            reward_types = [
                "THREE_SMALL_POTIONS",
                "RANDOM_COMMON_RELIC",
                "TEN_PERCENT_HP_BONUS",
                "THREE_ENEMY_KILL",
                "HUNDRED_GOLD",
            ]
        elif category == 2:
            drawback_defs = [
                ("TEN_PERCENT_HP_LOSS", self._neow_hp_bonus(10)),
                ("NO_GOLD", 0),
                ("CURSE", 0),
                ("PERCENT_DAMAGE", self._neow_percent_damage()),
            ]
            drawback, drawback_value = drawback_defs[self._neow_random_index(len(drawback_defs))]
            reward_types = ["RANDOM_COLORLESS_2", "ONE_RARE_RELIC", "THREE_RARE_CARDS", "TRANSFORM_TWO_CARDS"]
            if drawback != "CURSE":
                reward_types.append("REMOVE_TWO")
            if drawback != "NO_GOLD":
                reward_types.append("TWO_FIFTY_GOLD")
            if drawback != "TEN_PERCENT_HP_LOSS":
                reward_types.append("TWENTY_PERCENT_HP_BONUS")
        else:
            reward_types = ["BOSS_RELIC"]

        reward_type = reward_types[self._neow_random_index(len(reward_types))]
        if reward_type == "TEN_PERCENT_HP_BONUS":
            reward_value = self._neow_hp_bonus(10)
        elif reward_type == "TWENTY_PERCENT_HP_BONUS":
            reward_value = self._neow_hp_bonus(20)
        elif reward_type == "HUNDRED_GOLD":
            reward_value = 100
        elif reward_type == "TWO_FIFTY_GOLD":
            reward_value = 250

        reward_text = self._neow_reward_text(reward_type, reward_value)
        drawback_text = self._neow_drawback_text(drawback, drawback_value)
        label = reward_text if not drawback_text else f"{drawback_text}；{reward_text}"
        return {
            "category": category,
            "reward_type": reward_type,
            "reward_value": reward_value,
            "drawback": drawback,
            "drawback_value": drawback_value,
            "label": label,
        }

    def _legacy_get_neow_options_unused(self) -> list[dict[str, Any]]:
        return [dict(option) for option in list(getattr(self.state, "neow_options", []) or [])]

    def _neow_reward_card_pool(self, *, rare_only: bool) -> list[str]:
        from sts_py.engine.content.cards_min import CardRarity
        from sts_py.engine.rewards.card_rewards_min import character_pools

        pools = character_pools(self.state.character_class)
        if rare_only:
            return [card_def.id for card_def in pools.get(CardRarity.RARE, [])]

        rarity = CardRarity.UNCOMMON if self._neow_random_boolean(0.33) else CardRarity.COMMON
        return [card_def.id for card_def in pools.get(rarity, [])]

    def _neow_colorless_reward_pool(self, *, rare_only: bool) -> list[str]:
        from sts_py.engine.combat.card_effects import _implemented_colorless_combat_card_ids
        from sts_py.engine.content.cards_min import COLORLESS_ALL_DEFS, CardRarity

        allowed_rarity = CardRarity.RARE if rare_only else CardRarity.UNCOMMON
        return [
            card_id
            for card_id in _implemented_colorless_combat_card_ids()
            if COLORLESS_ALL_DEFS.get(card_id) is not None and COLORLESS_ALL_DEFS[card_id].rarity == allowed_rarity
        ]

    def _draw_unique_neow_cards(self, count: int, *, rare_only: bool = False, colorless: bool = False) -> list[str]:
        chosen: list[str] = []
        while len(chosen) < count:
            pool = (
                self._neow_colorless_reward_pool(rare_only=rare_only)
                if colorless
                else self._neow_reward_card_pool(rare_only=rare_only)
            )
            available = [card_id for card_id in pool if card_id not in chosen]
            if not available:
                break
            chosen.append(available[self._neow_random_index(len(available))])
        return chosen

    def _grant_neow_random_relic(self, tier_name: str) -> str | None:
        from sts_py.engine.content.relics import RelicTier, get_relic_pool

        tier = RelicTier(tier_name)
        exclude = self._current_relic_ids()
        exclude.update(self._consumed_relic_ids([tier_name.lower()]))
        chosen = self._choose_random_relic_offer(
            get_relic_pool(
                tier,
                floor=self.state.floor,
                act=self.state.act,
                context="reward",
                owned_relics=self.state.relics,
                deck=self.state.deck,
            ),
            exclude=exclude,
            rng=self._neow_rng,
        )
        if chosen is None:
            return None
        self._mark_relic_consumed(chosen.id, tier_name.lower())
        return self._acquire_relic(chosen.id, source=RelicSource.NEOW, record_pending=False)

    def _grant_neow_potions(self, count: int) -> list[str]:
        from sts_py.engine.content.potions import get_common_potions

        common_potions = get_common_potions(self.state.character_class)
        granted: list[str] = []
        if not common_potions:
            return granted
        for _ in range(count):
            potion = common_potions[self._neow_random_index(len(common_potions))]
            if self.gain_potion(potion.potion_id):
                granted.append(potion.potion_id)
        return granted

    def _grant_neow_curse(self) -> str | None:
        from sts_py.engine.content.cards_min import ALL_CURSE_DEFS

        curse_ids = list(ALL_CURSE_DEFS.keys())
        if not curse_ids:
            return None
        curse_id = curse_ids[self._neow_random_index(len(curse_ids))]
        self.state.deck.append(curse_id)
        return curse_id

    def _apply_neow_drawback(self, option: dict[str, Any]) -> dict[str, Any]:
        drawback = str(option.get("drawback", "NONE"))
        drawback_value = int(option.get("drawback_value", 0) or 0)
        result: dict[str, Any] = {"drawback": drawback}
        if drawback == "NO_GOLD":
            result["gold_lost"] = self.state.player_gold
            self.state.player_gold = 0
        elif drawback == "TEN_PERCENT_HP_LOSS":
            self.state.player_max_hp = max(1, self.state.player_max_hp - drawback_value)
            self.state.player_hp = min(self.state.player_hp, self.state.player_max_hp)
            result["max_hp_lost"] = drawback_value
        elif drawback == "PERCENT_DAMAGE":
            self.state.player_hp = max(0, self.state.player_hp - drawback_value)
            result["hp_lost"] = drawback_value
        elif drawback == "CURSE":
            result["curse_id"] = self._grant_neow_curse()
        if self.state.player_hp <= 0:
            self.state.phase = RunPhase.GAME_OVER
        return result

    def _record_neow_choice(self, *, option_index: int, option: dict[str, Any], details: dict[str, Any] | None = None) -> None:
        entry: dict[str, Any] = {
            "floor": int(self.state.floor),
            "event_id": "NeowEvent",
            "choice_index": int(option_index),
            "choice_text": str(option.get("label", "")),
            "reward_type": str(option.get("reward_type", "")),
            "drawback": str(option.get("drawback", "NONE")),
        }
        if details:
            entry.update(details)
        self.state.event_choices.append(entry)

    def get_neow_choice_cards(self) -> list[str]:
        pending = getattr(self.state, "pending_neow_choice", None)
        if not isinstance(pending, dict):
            return []
        action = str(pending.get("action", ""))
        if action == "reward_pick":
            return list(pending.get("cards") or [])

        from sts_py.engine.run.events import _can_remove_card

        candidates: list[str] = []
        for card_id in self.state.deck:
            if action == "remove" and _can_remove_card(self.state, card_id):
                candidates.append(card_id)
            elif action == "transform" and _can_remove_card(self.state, card_id):
                candidates.append(card_id)
            elif action == "upgrade":
                upgraded = self._upgrade_card(card_id)
                if upgraded is not None and upgraded != card_id:
                    candidates.append(card_id)
        return candidates

    def _legacy_choose_card_for_neow_unused(self, card_index: int) -> dict[str, Any]:
        if self.state.phase != RunPhase.NEOW:
            return {"success": False, "reason": "not_in_neow"}
        pending = getattr(self.state, "pending_neow_choice", None)
        if not isinstance(pending, dict):
            return {"success": False, "reason": "no_pending_neow_choice"}

        candidates = self.get_neow_choice_cards()
        if card_index < 0 or card_index >= len(candidates):
            return {"success": False, "reason": "invalid_card_index"}
        selected_card = candidates[card_index]
        action = str(pending.get("action", ""))
        option = dict(pending.get("option") or {})
        option_index = int(pending.get("option_index", 0) or 0)
        drawback_result = dict(pending.get("drawback_result") or {})
        details: dict[str, Any] = {}

        if action == "reward_pick":
            not_picked = [card_id for idx, card_id in enumerate(candidates) if idx != card_index]
            self.state.deck.append(selected_card)
            self.state.card_choices.append({
                "floor": self.state.floor,
                "picked": selected_card,
                "upgraded": selected_card.endswith("+"),
                "skipped": False,
                "not_picked": not_picked,
            })
            details = {"picked_card": selected_card, "not_picked": not_picked}
            self._record_neow_choice(option_index=option_index, option=option, details={**drawback_result, **details})
            self._finish_neow()
            return {"success": True, "action": action, **details}

        if action == "remove":
            from sts_py.engine.run.events import _apply_parasite_penalty

            _apply_parasite_penalty(self.state, selected_card)
            self.state.deck.remove(selected_card)
            details = {"removed_card": selected_card}
        elif action == "transform":
            deck_idx = self.state.deck.index(selected_card)
            new_card = self._transform_deck_card(selected_card)
            self.state.deck[deck_idx] = new_card
            details = {"old_card": selected_card, "new_card": new_card}
        elif action == "upgrade":
            deck_idx = self.state.deck.index(selected_card)
            upgraded_card = self._upgrade_card(selected_card)
            if upgraded_card is None or upgraded_card == selected_card:
                return {"success": False, "reason": "card_cannot_be_upgraded", "card_id": selected_card}
            self.state.deck[deck_idx] = upgraded_card
            details = {"old_card": selected_card, "new_card": upgraded_card}
        else:
            return {"success": False, "reason": "unknown_pending_neow_action"}

        remaining = max(0, int(pending.get("remaining", 1) or 1) - 1)
        if remaining > 0:
            pending["remaining"] = remaining
            self.state.pending_neow_choice = pending
            return {"success": True, "action": action, "remaining": remaining, **details}

        self._record_neow_choice(option_index=option_index, option=option, details={**drawback_result, **details})
        self._finish_neow()
        return {"success": True, "action": action, **details}

    def _init_neow(self) -> None:
        self.state.pending_neow_choice = None
        greeting_idx = 1 + (abs(int(self.state.seed or 0)) % 3)
        if self.state.neow_intro_seen:
            self._set_neow_surface(
                screen="greeting",
                body_en=self._neow_event_text(greeting_idx),
                body_cn=self._neow_event_text(greeting_idx, cn=True),
                options=[self._make_neow_dialog_option(1)],
            )
            return
        self._set_neow_surface(
            screen="intro",
            body_en=self._neow_event_text(0),
            body_cn=self._neow_event_text(0, cn=True),
            options=[self._make_neow_dialog_option(1)],
        )

    def _neow_event_text(self, idx: int, *, cn: bool = False) -> str:
        entry = get_official_neow_event_strings()
        values = entry.text_zhs if cn else entry.text_en
        if 0 <= idx < len(values):
            return str(values[idx] or "")
        return ""

    def _neow_event_option(self, idx: int, *, cn: bool = False) -> str:
        entry = get_official_neow_event_strings()
        values = entry.options_zhs if cn else entry.options_en
        if 0 <= idx < len(values):
            return str(values[idx] or "")
        return ""

    def _neow_reward_text_piece(self, idx: int, *, cn: bool = False) -> str:
        entry = get_official_neow_reward_strings()
        values = entry.text_zhs if cn else entry.text_en
        if 0 <= idx < len(values):
            return str(values[idx] or "")
        return ""

    def _neow_unique_reward_text(self, idx: int, *, cn: bool = False) -> str:
        entry = get_official_neow_reward_strings()
        values = entry.unique_rewards_zhs if cn else entry.unique_rewards_en
        if 0 <= idx < len(values):
            return str(values[idx] or "")
        return ""

    def _compose_neow_reward_text(self, reward_type: str, reward_value: int, *, cn: bool = False) -> str:
        if reward_type == "THREE_CARDS":
            return self._neow_reward_text_piece(0, cn=cn)
        if reward_type == "ONE_RANDOM_RARE_CARD":
            return self._neow_reward_text_piece(1, cn=cn)
        if reward_type == "REMOVE_CARD":
            return self._neow_reward_text_piece(2, cn=cn)
        if reward_type == "UPGRADE_CARD":
            return self._neow_reward_text_piece(3, cn=cn)
        if reward_type == "TRANSFORM_CARD":
            return self._neow_reward_text_piece(4, cn=cn)
        if reward_type == "THREE_SMALL_POTIONS":
            return self._neow_reward_text_piece(5, cn=cn)
        if reward_type == "RANDOM_COMMON_RELIC":
            return self._neow_reward_text_piece(6, cn=cn)
        if reward_type == "TEN_PERCENT_HP_BONUS":
            return f"{self._neow_reward_text_piece(7, cn=cn)}{reward_value} ]"
        if reward_type == "THREE_ENEMY_KILL":
            return self._neow_reward_text_piece(28, cn=cn)
        if reward_type == "HUNDRED_GOLD":
            return f"{self._neow_reward_text_piece(8, cn=cn)}100{self._neow_reward_text_piece(9, cn=cn)}"
        if reward_type == "RANDOM_COLORLESS":
            return self._neow_reward_text_piece(30, cn=cn)
        if reward_type == "RANDOM_COLORLESS_2":
            return self._neow_reward_text_piece(31, cn=cn)
        if reward_type == "REMOVE_TWO":
            return self._neow_reward_text_piece(10, cn=cn)
        if reward_type == "ONE_RARE_RELIC":
            return self._neow_reward_text_piece(11, cn=cn)
        if reward_type == "THREE_RARE_CARDS":
            return self._neow_reward_text_piece(12, cn=cn)
        if reward_type == "TWO_FIFTY_GOLD":
            return f"{self._neow_reward_text_piece(13, cn=cn)}250{self._neow_reward_text_piece(14, cn=cn)}"
        if reward_type == "TRANSFORM_TWO_CARDS":
            return self._neow_reward_text_piece(15, cn=cn)
        if reward_type == "TWENTY_PERCENT_HP_BONUS":
            return f"{self._neow_reward_text_piece(16, cn=cn)}{reward_value} ]"
        if reward_type == "BOSS_RELIC":
            return self._neow_unique_reward_text(0, cn=cn)
        return reward_type

    def _compose_neow_drawback_text(self, drawback: str, drawback_value: int, *, cn: bool = False) -> str:
        if drawback == "NONE":
            return ""
        if drawback == "TEN_PERCENT_HP_LOSS":
            return f"{self._neow_reward_text_piece(17, cn=cn)}{drawback_value}{self._neow_reward_text_piece(18, cn=cn)}"
        if drawback == "NO_GOLD":
            return self._neow_reward_text_piece(19, cn=cn)
        if drawback == "CURSE":
            return self._neow_reward_text_piece(20, cn=cn)
        if drawback == "PERCENT_DAMAGE":
            return f"{self._neow_reward_text_piece(21, cn=cn)}{drawback_value}{self._neow_reward_text_piece(29, cn=cn)} "
        return drawback

    def _make_neow_dialog_option(self, option_idx: int) -> dict[str, Any]:
        label_en = self._neow_event_option(option_idx)
        label_cn = self._neow_event_option(option_idx, cn=True)
        return {
            "label": label_cn or label_en,
            "label_en": label_en,
            "label_cn": label_cn,
            "dialog_option_index": option_idx,
        }

    def _set_neow_surface(
        self,
        *,
        screen: str,
        body_en: str,
        body_cn: str,
        options: list[dict[str, Any]],
    ) -> None:
        self.state.neow_screen = screen
        self.state.neow_body = body_en
        self.state.neow_body_cn = body_cn
        self.state.neow_options = [dict(option) for option in options]

    def _prepare_neow_leave_screen(self, option: dict[str, Any]) -> None:
        text_index = int(option.get("completion_text_index", 8) or 8)
        self._set_neow_surface(
            screen="complete",
            body_en=self._neow_event_text(text_index),
            body_cn=self._neow_event_text(text_index, cn=True),
            options=[self._make_neow_dialog_option(3)],
        )

    def _leave_neow(self) -> None:
        self.state.pending_neow_choice = None
        self.state.neow_options = []
        self.state.neow_screen = ""
        self.state.neow_body = ""
        self.state.neow_body_cn = ""
        if self.state.phase != RunPhase.GAME_OVER:
            self.state.phase = RunPhase.MAP

    def _begin_mini_neow_blessing(self) -> None:
        hp_bonus = self._neow_hp_bonus(10)
        choices = [
            {
                "category": 1,
                "reward_type": "THREE_ENEMY_KILL",
                "reward_value": 0,
                "drawback": "NONE",
                "drawback_value": 0,
                "completion_text_index": 8,
            },
            {
                "category": 1,
                "reward_type": "TEN_PERCENT_HP_BONUS",
                "reward_value": hp_bonus,
                "drawback": "NONE",
                "drawback_value": 0,
                "completion_text_index": 8,
            },
        ]
        for option in choices:
            option["label_en"] = self._compose_neow_reward_text(str(option["reward_type"]), int(option["reward_value"]), cn=False)
            option["label_cn"] = self._compose_neow_reward_text(str(option["reward_type"]), int(option["reward_value"]), cn=True)
            option["label"] = option["label_cn"] or option["label_en"]
        prompt_idx = 4 + (abs(int(self.state.seed or 0)) % 3)
        self._set_neow_surface(
            screen="reward_select",
            body_en=self._neow_event_text(prompt_idx),
            body_cn=self._neow_event_text(prompt_idx, cn=True),
            options=choices,
        )

    def _begin_full_neow_blessing(self) -> None:
        self._neow_rng = MutableRNG.from_seed(self.state.seed, rng_type="neowRng")
        self._set_neow_surface(
            screen="reward_select",
            body_en=self._neow_event_text(7),
            body_cn=self._neow_event_text(7, cn=True),
            options=[self._build_neow_option(category) for category in range(4)],
        )

    def _build_neow_option(self, category: int) -> dict[str, Any]:
        reward_value = 0
        drawback = "NONE"
        drawback_value = 0

        if category == 0:
            reward_types = [
                "THREE_CARDS",
                "ONE_RANDOM_RARE_CARD",
                "REMOVE_CARD",
                "UPGRADE_CARD",
                "TRANSFORM_CARD",
                "RANDOM_COLORLESS",
            ]
        elif category == 1:
            reward_types = [
                "THREE_SMALL_POTIONS",
                "RANDOM_COMMON_RELIC",
                "TEN_PERCENT_HP_BONUS",
                "THREE_ENEMY_KILL",
                "HUNDRED_GOLD",
            ]
        elif category == 2:
            drawback_defs = [
                ("TEN_PERCENT_HP_LOSS", self._neow_hp_bonus(10)),
                ("NO_GOLD", 0),
                ("CURSE", 0),
                ("PERCENT_DAMAGE", self._neow_percent_damage()),
            ]
            drawback, drawback_value = drawback_defs[self._neow_random_index(len(drawback_defs))]
            reward_types = ["RANDOM_COLORLESS_2", "ONE_RARE_RELIC", "THREE_RARE_CARDS", "TRANSFORM_TWO_CARDS"]
            if drawback != "CURSE":
                reward_types.append("REMOVE_TWO")
            if drawback != "NO_GOLD":
                reward_types.append("TWO_FIFTY_GOLD")
            if drawback != "TEN_PERCENT_HP_LOSS":
                reward_types.append("TWENTY_PERCENT_HP_BONUS")
        else:
            reward_types = ["BOSS_RELIC"]

        reward_type = reward_types[self._neow_random_index(len(reward_types))]
        if reward_type == "TEN_PERCENT_HP_BONUS":
            reward_value = self._neow_hp_bonus(10)
        elif reward_type == "TWENTY_PERCENT_HP_BONUS":
            reward_value = self._neow_hp_bonus(20)
        elif reward_type == "HUNDRED_GOLD":
            reward_value = 100
        elif reward_type == "TWO_FIFTY_GOLD":
            reward_value = 250

        reward_text_en = self._compose_neow_reward_text(reward_type, reward_value, cn=False)
        reward_text_cn = self._compose_neow_reward_text(reward_type, reward_value, cn=True)
        drawback_text_en = self._compose_neow_drawback_text(drawback, drawback_value, cn=False)
        drawback_text_cn = self._compose_neow_drawback_text(drawback, drawback_value, cn=True)
        label_en = reward_text_en if not drawback_text_en else f"{drawback_text_en}{reward_text_en}"
        label_cn = reward_text_cn if not drawback_text_cn else f"{drawback_text_cn}{reward_text_cn}"
        return {
            "category": category,
            "reward_type": reward_type,
            "reward_value": reward_value,
            "drawback": drawback,
            "drawback_value": drawback_value,
            "label": label_cn or label_en,
            "label_en": label_en,
            "label_cn": label_cn,
            "completion_text_index": 8 if category in {0, 1} else 9,
        }

    def get_neow_options(self) -> list[dict[str, Any]]:
        return [dict(option) for option in list(getattr(self.state, "neow_options", []) or [])]

    def choose_neow_option(self, index: int) -> dict[str, Any]:
        if self.state.phase != RunPhase.NEOW:
            return {"success": False, "reason": "not_in_neow"}
        if self.state.pending_neow_choice is not None:
            return {"success": False, "reason": "pending_neow_choice"}

        options = list(getattr(self.state, "neow_options", []) or [])
        if index < 0 or index >= len(options):
            return {"success": False, "reason": "invalid_neow_option"}

        screen = str(getattr(self.state, "neow_screen", "") or "")
        option = dict(options[index])

        if screen in {"intro", "greeting"} and not option.get("reward_type"):
            self.state.neow_intro_seen = True
            self._save_player_profile()
            if int(getattr(self.state, "character_spirits", 0) or 0) > 0:
                self._begin_full_neow_blessing()
            else:
                self._begin_mini_neow_blessing()
            return {"success": True, "action": "dialog_advance", "event_continues": True}

        if screen == "complete":
            self._leave_neow()
            return {"success": True, "action": "leave"}

        drawback_result = self._apply_neow_drawback(option)
        if self.state.phase == RunPhase.GAME_OVER:
            self._record_neow_choice(option_index=index, option=option, details=drawback_result)
            return {"success": True, "game_over": True, "option": option, "drawback_result": drawback_result}

        reward_type = str(option.get("reward_type", ""))
        if reward_type == "THREE_CARDS":
            cards = self._draw_unique_neow_cards(3, rare_only=False, colorless=False)
            self.state.pending_neow_choice = {
                "action": "reward_pick",
                "cards": cards,
                "option": option,
                "option_index": index,
                "drawback_result": drawback_result,
            }
            return {"success": True, "requires_card_choice": True, "action": "reward_pick", "cards": cards}
        if reward_type == "THREE_RARE_CARDS":
            cards = self._draw_unique_neow_cards(3, rare_only=True, colorless=False)
            self.state.pending_neow_choice = {
                "action": "reward_pick",
                "cards": cards,
                "option": option,
                "option_index": index,
                "drawback_result": drawback_result,
            }
            return {"success": True, "requires_card_choice": True, "action": "reward_pick", "cards": cards}
        if reward_type == "RANDOM_COLORLESS":
            cards = self._draw_unique_neow_cards(3, rare_only=False, colorless=True)
            self.state.pending_neow_choice = {
                "action": "reward_pick",
                "cards": cards,
                "option": option,
                "option_index": index,
                "drawback_result": drawback_result,
            }
            return {"success": True, "requires_card_choice": True, "action": "reward_pick", "cards": cards}
        if reward_type == "RANDOM_COLORLESS_2":
            cards = self._draw_unique_neow_cards(3, rare_only=True, colorless=True)
            self.state.pending_neow_choice = {
                "action": "reward_pick",
                "cards": cards,
                "option": option,
                "option_index": index,
                "drawback_result": drawback_result,
            }
            return {"success": True, "requires_card_choice": True, "action": "reward_pick", "cards": cards}
        if reward_type == "REMOVE_CARD":
            self.state.pending_neow_choice = {
                "action": "remove",
                "remaining": 1,
                "option": option,
                "option_index": index,
                "drawback_result": drawback_result,
            }
            return {"success": True, "requires_card_choice": True, "action": "remove", "remaining": 1}
        if reward_type == "REMOVE_TWO":
            self.state.pending_neow_choice = {
                "action": "remove",
                "remaining": 2,
                "option": option,
                "option_index": index,
                "drawback_result": drawback_result,
            }
            return {"success": True, "requires_card_choice": True, "action": "remove", "remaining": 2}
        if reward_type == "UPGRADE_CARD":
            self.state.pending_neow_choice = {
                "action": "upgrade",
                "remaining": 1,
                "option": option,
                "option_index": index,
                "drawback_result": drawback_result,
            }
            return {"success": True, "requires_card_choice": True, "action": "upgrade", "remaining": 1}
        if reward_type == "TRANSFORM_CARD":
            self.state.pending_neow_choice = {
                "action": "transform",
                "remaining": 1,
                "option": option,
                "option_index": index,
                "drawback_result": drawback_result,
            }
            return {"success": True, "requires_card_choice": True, "action": "transform", "remaining": 1}
        if reward_type == "TRANSFORM_TWO_CARDS":
            self.state.pending_neow_choice = {
                "action": "transform",
                "remaining": 2,
                "option": option,
                "option_index": index,
                "drawback_result": drawback_result,
            }
            return {"success": True, "requires_card_choice": True, "action": "transform", "remaining": 2}

        details: dict[str, Any] = {}
        if reward_type == "ONE_RANDOM_RARE_CARD":
            cards = self._draw_unique_neow_cards(1, rare_only=True, colorless=False)
            if cards:
                self.state.deck.append(cards[0])
                details["card_id"] = cards[0]
        elif reward_type == "THREE_SMALL_POTIONS":
            details["potions"] = self._grant_neow_potions(3)
        elif reward_type == "RANDOM_COMMON_RELIC":
            details["relic_id"] = self._grant_neow_random_relic("COMMON")
        elif reward_type == "ONE_RARE_RELIC":
            details["relic_id"] = self._grant_neow_random_relic("RARE")
        elif reward_type == "TEN_PERCENT_HP_BONUS":
            bonus = int(option.get("reward_value", 0) or 0)
            self.state.player_max_hp += bonus
            self.state.player_hp += bonus
            details["max_hp_gained"] = bonus
        elif reward_type == "TWENTY_PERCENT_HP_BONUS":
            bonus = int(option.get("reward_value", 0) or 0)
            self.state.player_max_hp += bonus
            self.state.player_hp += bonus
            details["max_hp_gained"] = bonus
        elif reward_type == "THREE_ENEMY_KILL":
            self.state.neow_blessing = True
            self.state.neow_blessing_remaining = 3
            if "NeowsLament" not in self.state.relics:
                self.state.relics.append("NeowsLament")
                self._record_relic_history("NeowsLament", source=RelicSource.NEOW)
            details["relic_id"] = "NeowsLament"
        elif reward_type == "HUNDRED_GOLD":
            self.state.player_gold += 100
            details["gold_gained"] = 100
        elif reward_type == "TWO_FIFTY_GOLD":
            self.state.player_gold += 250
            details["gold_gained"] = 250
        elif reward_type == "BOSS_RELIC":
            from sts_py.engine.content.relics import RelicTier, get_relic_pool

            replaced = self.state.relics.pop(0) if self.state.relics else None
            if replaced is not None:
                details["replaced_relic"] = replaced
            exclude = self._current_relic_ids()
            exclude.update(self._consumed_relic_ids(["boss"]))
            chosen = self._choose_random_relic_offer(
                get_relic_pool(
                    RelicTier.BOSS,
                    floor=self.state.floor,
                    act=self.state.act,
                    context="reward",
                    owned_relics=self.state.relics,
                    deck=self.state.deck,
                ),
                exclude=exclude,
                rng=self._neow_rng,
            )
            if chosen is not None:
                self._mark_relic_consumed(chosen.id, "boss")
                details["relic_id"] = self._acquire_relic(chosen.id, source=RelicSource.NEOW, record_pending=False)

        self._record_neow_choice(option_index=index, option=option, details={**drawback_result, **details})
        self._prepare_neow_leave_screen(option)
        return {"success": True, "option": option, "drawback_result": drawback_result, "details": details, "event_continues": True}

    def choose_card_for_neow(self, card_index: int) -> dict[str, Any]:
        if self.state.phase != RunPhase.NEOW:
            return {"success": False, "reason": "not_in_neow"}
        pending = getattr(self.state, "pending_neow_choice", None)
        if not isinstance(pending, dict):
            return {"success": False, "reason": "no_pending_neow_choice"}

        candidates = self.get_neow_choice_cards()
        if card_index < 0 or card_index >= len(candidates):
            return {"success": False, "reason": "invalid_card_index"}
        selected_card = candidates[card_index]
        action = str(pending.get("action", ""))
        option = dict(pending.get("option") or {})
        option_index = int(pending.get("option_index", 0) or 0)
        drawback_result = dict(pending.get("drawback_result") or {})
        details: dict[str, Any] = {}

        if action == "reward_pick":
            not_picked = [card_id for idx, card_id in enumerate(candidates) if idx != card_index]
            self.state.deck.append(selected_card)
            self.state.card_choices.append({
                "floor": self.state.floor,
                "picked": selected_card,
                "upgraded": selected_card.endswith("+"),
                "skipped": False,
                "not_picked": not_picked,
            })
            details = {"picked_card": selected_card, "not_picked": not_picked}
            self._record_neow_choice(option_index=option_index, option=option, details={**drawback_result, **details})
            self.state.pending_neow_choice = None
            self._prepare_neow_leave_screen(option)
            return {"success": True, "action": action, "event_continues": True, **details}

        if action == "remove":
            from sts_py.engine.run.events import _apply_parasite_penalty

            _apply_parasite_penalty(self.state, selected_card)
            self.state.deck.remove(selected_card)
            details = {"removed_card": selected_card}
        elif action == "transform":
            deck_idx = self.state.deck.index(selected_card)
            new_card = self._transform_deck_card(selected_card)
            self.state.deck[deck_idx] = new_card
            details = {"old_card": selected_card, "new_card": new_card}
        elif action == "upgrade":
            deck_idx = self.state.deck.index(selected_card)
            upgraded_card = self._upgrade_card(selected_card)
            if upgraded_card is None or upgraded_card == selected_card:
                return {"success": False, "reason": "card_cannot_be_upgraded", "card_id": selected_card}
            self.state.deck[deck_idx] = upgraded_card
            details = {"old_card": selected_card, "new_card": upgraded_card}
        else:
            return {"success": False, "reason": "unknown_pending_neow_action"}

        remaining = max(0, int(pending.get("remaining", 1) or 1) - 1)
        if remaining > 0:
            pending["remaining"] = remaining
            self.state.pending_neow_choice = pending
            return {"success": True, "action": action, "remaining": remaining, **details}

        self._record_neow_choice(option_index=option_index, option=option, details={**drawback_result, **details})
        self.state.pending_neow_choice = None
        self._prepare_neow_leave_screen(option)
        return {"success": True, "action": action, "event_continues": True, **details}

    def _normalize_room_type(self, symbol: str) -> RoomType:
        mapping = {
            "M": RoomType.MONSTER,
            "E": RoomType.ELITE,
            "B": RoomType.BOSS,
            "?": RoomType.EVENT,
            "$": RoomType.SHOP,
            "R": RoomType.REST,
            "T": RoomType.TREASURE,
        }
        return mapping.get(symbol, RoomType.EMPTY)

    def _generate_map(self) -> None:
        if self.state.act == 4:
            self._generate_special_act4_map()
            return

        from sts_py.engine.run.map_generator import generate_map

        if self.state.rng is None:
            self.state.map_nodes = []
            return

        generated_nodes = generate_map(
            height=15,  # Java: 13层普通 + Rest + Boss = 15节点 (y=0到y=14)
            width=7,
            path_density=6,  # Java: mapPathDensity = 6
            rng=self.state.rng.map_rng,  # Java uses mapRng = new Random(Settings.seed + act_num)
            act=self.state.act,
        )

        self.state.map_nodes = []
        coord_to_idx: dict[tuple[int, int], int] = {}

        for y, row in enumerate(generated_nodes):
            for x, node in enumerate(row):
                if not node.has_edges() and not node.parents:
                    continue
                runtime_node = MapNode(
                    floor=y + 1,
                    room_type=self._normalize_room_type(node.room_type),
                    x=x,
                    y=y,
                    node_id=len(self.state.map_nodes),
                )
                coord_to_idx[(x, y)] = runtime_node.node_id
                self.state.map_nodes.append(runtime_node)

        for y, row in enumerate(generated_nodes):
            for x, node in enumerate(row):
                src_idx = coord_to_idx.get((x, y))
                if src_idx is None:
                    continue
                runtime_node = self.state.map_nodes[src_idx]
                for edge in node.edges:
                    dst_idx = coord_to_idx.get((edge.dst_x, edge.dst_y))
                    if dst_idx is None:
                        continue
                    runtime_node.connections.append(dst_idx)
                    self.state.map_nodes[dst_idx].parent_indices.append(src_idx)

        for node in self.state.map_nodes:
            node.connections.sort(key=lambda idx: (self.state.map_nodes[idx].x, idx))
            node.parent_indices.sort()

        self._mark_burning_elite()

    def _generate_special_act4_map(self) -> None:
        floor_base = 51
        rooms = [
            RoomType.REST,
            RoomType.SHOP,
            RoomType.ELITE,
            RoomType.BOSS,
        ]
        self.state.map_nodes = []
        for idx, room_type in enumerate(rooms):
            self.state.map_nodes.append(
                MapNode(
                    floor=floor_base + idx + 1,
                    room_type=room_type,
                    x=3,
                    y=idx,
                    node_id=idx,
                )
            )
        for idx in range(len(self.state.map_nodes) - 1):
            self.state.map_nodes[idx].connections.append(self.state.map_nodes[idx + 1].node_id)
            self.state.map_nodes[idx + 1].parent_indices.append(self.state.map_nodes[idx].node_id)

    def _mark_burning_elite(self) -> None:
        for node in self.state.map_nodes:
            node.burning_elite = False

        if self.state.act >= 4 or self.state.emerald_key_obtained or self.state.rng is None:
            return

        elite_nodes = [node for node in self.state.map_nodes if node.room_type == RoomType.ELITE]
        if not elite_nodes:
            return

        chosen_idx = self.state.rng.map_rng.random_int(len(elite_nodes) - 1)
        elite_nodes[chosen_idx].burning_elite = True

    def get_current_room(self) -> MapNode | None:
        if self.state.current_node_idx < 0:
            return None
        if self.state.current_node_idx >= len(self.state.map_nodes):
            return None
        return self.state.map_nodes[self.state.current_node_idx]

    def get_available_paths(self) -> list[MapNode]:
        if not self.state.map_nodes:
            return []

        if self.state.current_node_idx < 0:
            starts = [
                node for node in self.state.map_nodes
                if not node.parent_indices and node.floor == min(n.floor for n in self.state.map_nodes)
            ]
            return sorted(starts, key=lambda node: (node.x, node.node_id))

        current_node = self.state.map_nodes[self.state.current_node_idx]
        next_nodes = [self.state.map_nodes[idx] for idx in current_node.connections]
        return sorted(next_nodes, key=lambda node: (node.x, node.node_id))

    def choose_path(self, node_idx: int) -> bool:
        available = self.get_available_paths()
        if not available:
            return False

        target_node = None
        for node in available:
            if node.node_id == node_idx:
                target_node = node
                break

        if target_node is None:
            return False

        previous_room = self.get_current_room()
        self.state.previous_room_type_for_event_roll = (
            previous_room.room_type.value if previous_room is not None else ""
        )
        self.state.current_node_idx = target_node.node_id
        self.state.floor = target_node.floor
        self.state.path_taken.append(target_node.room_type.value)
        self.state.path_trace.append({
            "floor": target_node.floor,
            "x": target_node.x,
            "y": target_node.y,
            "room_type": target_node.room_type.value,
            "burning_elite": target_node.burning_elite,
        })

        self._enter_room(target_node)
        return True

    def force_enter_node(self, floor: int, x: int, y: int, room_type_str: str, event_id: str | None = None) -> None:
        from sts_py.engine.run.events import build_event, EVENT_KEY_BY_ID, EVENT_KEY_ALIASES

        JAVA_TO_PYTHON_ROOM_TYPE = {
            "MonsterRoom": "M",
            "MonsterRoomElite": "E",
            "MonsterRoomBoss": "B",
            "EventRoom": "?",
            "ShopRoom": "$",
            "RestRoom": "R",
            "TreasureRoom": "T",
            "TreasureRoomBoss": "T",
            "EmptyRoom": " ",
        }
        py_room_type = JAVA_TO_PYTHON_ROOM_TYPE.get(room_type_str, room_type_str)

        if floor != self.state.floor:
            self.state.floor = floor
            self._reseed_rng_for_floor(floor)

        previous_room = self.get_current_room()
        self.state.previous_room_type_for_event_roll = (
            previous_room.room_type.value if previous_room is not None else ""
        )
        self.state.current_node_idx = -1
        self.state.path_taken.append(py_room_type)
        self.state.path_trace.append({
            "floor": floor,
            "x": x,
            "y": y,
            "room_type": py_room_type,
        })

        if room_type_str == "EventRoom":
            if event_id:
                canonical_key = EVENT_KEY_BY_ID.get(event_id) or EVENT_KEY_ALIASES.get(event_id)
                if canonical_key:
                    self._set_current_event(build_event(canonical_key, getattr(getattr(self.state, "rng", None), "event_rng", None)))
                    if canonical_key in self.state.event_list:
                        self.state.event_list.remove(canonical_key)
                    if canonical_key in self.state.shrine_list:
                        self.state.shrine_list.remove(canonical_key)
                    if canonical_key in self.state.special_one_time_event_list:
                        self.state.special_one_time_event_list.remove(canonical_key)
                    return
            self._enter_event()
        else:
            dummy_node = MapNode(floor=floor, room_type=RoomType(py_room_type), x=x, y=y)
            self._enter_room(dummy_node)

    def _reseed_rng_for_floor(self, floor: int) -> None:
        seed = self.state.rng.seed_long
        floor_seed = seed + floor
        self.state.rng = RunRngState.generate_seeds(floor_seed)
        self.ai_rng = self.state.rng._ai_rng
        self.hp_rng = self.state.rng._monster_hp_rng

    def _reseed_rng_for_act(self, act: int) -> None:
        seed = self.state.rng.seed_long
        act_seed = seed + act
        self.state.rng = RunRngState.generate_seeds(act_seed)
        self.ai_rng = self.state.rng._ai_rng
        self.hp_rng = self.state.rng._monster_hp_rng
        self.state.rng._map_rng = MutableRNG.from_seed(
            seed + act, rng_type="mapRng", use_java_random=True
        )

    def _generate_encounters_for_act(self) -> None:
        """Generate encounter lists at act start using base seed monsterRng.

        Java stores weak and strong encounters in a SHARED monsterList.
        MonsterRoom encounters are assigned by visit order from this shared list.
        """
        from sts_py.engine.run.encounter_generator import generate_all_encounters, generate_monsters

        base_seed = self.state.rng.seed_long
        base_rng = RunRngState.generate_seeds(base_seed)

        # Java: weak + strong in shared monsterList
        self.state.monster_list = generate_all_encounters(
            base_rng._monster_rng,
            act=self.state.act
        )

        # Elite encounters in separate list
        _, _, elite = generate_monsters(
            base_rng._monster_rng,
            act=self.state.act
        )
        self.state.elite_list = elite

    def _enter_room(self, node: MapNode) -> None:
        if node.room_type == RoomType.MONSTER:
            self._start_combat(self._get_encounter_for_floor(node.floor))
        elif node.room_type == RoomType.ELITE:
            self._start_combat(self._get_elite_encounter())
        elif node.room_type == RoomType.BOSS:
            self._start_combat(self._get_boss_encounter())
        elif node.room_type == RoomType.EVENT:
            self._enter_question_room(node.floor)
        elif node.room_type == RoomType.SHOP:
            self._enter_shop()
        elif node.room_type == RoomType.REST:
            self.state.phase = RunPhase.REST
        elif node.room_type == RoomType.TREASURE:
            self._enter_treasure()

    def _enter_question_room(self, floor: int) -> None:
        """Resolve question rooms using Java EventHelper.roll semantics."""
        self.state.question_room_count += 1

        force_treasure = False
        if self._has_relic("TinyChest"):
            tiny_chest_counter = int(self.state.relic_counters.get("TinyChest", 0) or 0) + 1
            if tiny_chest_counter >= 4:
                tiny_chest_counter = 0
                force_treasure = True
            self.state.relic_counters["TinyChest"] = tiny_chest_counter

        roll_value = self.state.rng.event_rng.random_float() if self.state.rng is not None else 0.5
        monster_size = int(self.state.question_room_monster_chance * 100.0)
        shop_size = int(self.state.question_room_shop_chance * 100.0)
        treasure_size = int(self.state.question_room_treasure_chance * 100.0)
        if self.state.previous_room_type_for_event_roll == RoomType.SHOP.value:
            shop_size = 0

        possible_results = ["EVENT"] * 100
        fill_index = 0
        for idx in range(fill_index, min(100, fill_index + monster_size)):
            possible_results[idx] = "MONSTER"
        fill_index += monster_size
        for idx in range(fill_index, min(100, fill_index + shop_size)):
            possible_results[idx] = "SHOP"
        fill_index += shop_size
        for idx in range(fill_index, min(100, fill_index + treasure_size)):
            possible_results[idx] = "TREASURE"

        choice = possible_results[min(99, int(roll_value * 100.0))]
        if force_treasure:
            choice = "TREASURE"

        if choice == "ELITE":
            self.state.question_room_elite_chance = 0.0
        else:
            self.state.question_room_elite_chance += 0.1

        if choice == "MONSTER":
            if self._has_relic("JuzuBracelet"):
                choice = "EVENT"
            self.state.question_room_monster_chance = 0.10
        else:
            self.state.question_room_monster_chance += 0.10

        self.state.question_room_shop_chance = 0.03 if choice == "SHOP" else self.state.question_room_shop_chance + 0.03
        self.state.question_room_treasure_chance = 0.02 if choice == "TREASURE" else self.state.question_room_treasure_chance + 0.02
        self.state.question_room_last_encounter = choice.lower()

        if choice == "MONSTER":
            self._start_combat(self._get_encounter_for_floor(floor))
            return
        if choice == "TREASURE":
            self._enter_treasure()
            return
        if choice == "SHOP":
            self._enter_shop()
            return
        self._enter_event()

    def _get_encounter_for_floor(self, floor: int) -> str:
        """Get encounter by VISIT ORDER, not floor number (Java semantics)."""
        if not self.state.monster_list:
            return "Cultist"
        idx = self.state.monster_list_idx % len(self.state.monster_list)
        self.state.monster_list_idx += 1
        return self.state.monster_list[idx]

    def _get_elite_encounter(self) -> str:
        if self.state.act == 4:
            return "Shield and Spear"
        if not self.state.elite_list:
            return "Gremlin Nob"
        idx = self.state.elite_list_idx % len(self.state.elite_list)
        self.state.elite_list_idx += 1
        return self.state.elite_list[idx]

    def _get_boss_encounter(self) -> str:
        if self.state.rng is None:
            return "Hexaghost"
        if self.state.act == 1:
            boss_encounters = ["Hexaghost", "Slime Boss", "The Guardian"]
        elif self.state.act == 2:
            boss_encounters = ["Champ", "Collector", "Automaton"]
        elif self.state.act == 4:
            boss_encounters = ["The Heart"]
        else:
            boss_encounters = ["Awakened One", "Time Eater", "Donu and Deca"]
        idx = self.state.rng.monster_rng.random_int(len(boss_encounters) - 1)
        return boss_encounters[idx]

    def _start_combat(self, encounter_name: str) -> None:
        neow_active = self.state.neow_blessing and self.state.neow_blessing_remaining > 0
        consume_neow_relic = False
        if neow_active:
            self.state.neow_blessing_remaining -= 1
            if self.state.neow_blessing_remaining <= 0:
                self.state.neow_blessing = False
                consume_neow_relic = True

        self.state.combat = CombatEngine.create(
            encounter_name=encounter_name,
            player_hp=self.state.player_hp,
            player_max_hp=self.state.player_max_hp,
            ai_rng=self.ai_rng,
            hp_rng=self.hp_rng,
            card_random_rng=self.state.rng.card_random_rng if self.state.rng is not None else None,
            ascension=self.state.ascension,
            deck=self.state.deck,
            relics=self.state.relics,
            neow_blessing=neow_active,
            persistent_relic_attack_counters=self.state.player_relic_attack_counters,
        )
        if consume_neow_relic and "NeowsLament" in self.state.relics:
            self.state.relics.remove("NeowsLament")
        self.state.combat.state.run_engine = self
        self.state.phase = RunPhase.COMBAT

    def start_combat_with_monsters(self, monster_ids: list[str]) -> None:
        from sts_py.engine.monsters.exordium import create_monster

        monsters = []
        setup_debug: dict[str, Any] = {
            "requested_monster_ids": list(monster_ids),
            "alias_hits": [],
            "proxy_monster_ids": [],
            "failed_monster_ids": [],
        }
        for monster_id in monster_ids:
            monster, monster_debug = _create_replay_monster(
                monster_id,
                self.hp_rng,
                self.state.ascension,
                act=self.state.act,
            )
            if monster_debug.get("alias_hit"):
                setup_debug["alias_hits"].append({
                    "logged_id": monster_debug["logged_id"],
                    "runtime_id": monster_debug["runtime_id"],
                })
            if monster_debug.get("used_proxy"):
                setup_debug["proxy_monster_ids"].append(monster_id)
            if monster is None:
                setup_debug["failed_monster_ids"].append({
                    "logged_id": monster_id,
                    "runtime_id": monster_debug.get("runtime_id"),
                    "error": monster_debug.get("factory_error"),
                })
                continue
            monsters.append(monster)

        if not monsters:
            setup_debug["fallback_monster_id"] = "JawWorm"
            fallback = create_monster("Jaw Worm", self.hp_rng, self.state.ascension)
            if fallback is not None:
                monsters.append(fallback)

        self.state._last_combat_setup_debug = setup_debug

        combat = CombatEngine.create_with_monsters(
            monsters=monsters,
            player_hp=self.state.player_hp,
            player_max_hp=self.state.player_max_hp,
            ai_rng=self.ai_rng,
            hp_rng=self.hp_rng,
            card_random_rng=self.state.rng.card_random_rng if self.state.rng is not None else None,
            ascension=self.state.ascension,
            deck=self.state.deck,
            relics=self.state.relics,
            pending_tea_energy=self.state.player_pending_tea_energy,
            persistent_relic_attack_counters=self.state.player_relic_attack_counters,
        )
        self.state.player_pending_tea_energy = 0
        self.state.combat = combat
        self.state.combat.state.player.character_class = self.state.character_class
        self.state.combat.state.run_engine = self
        self.state.phase = RunPhase.COMBAT

    def combat_play_card(self, card_index: int, target_idx: int | None = None) -> bool:
        if self.state.combat is None:
            return False
        return self.state.combat.play_card(card_index, target_idx)

    def combat_attack(self, monster_idx: int, damage: int) -> int:
        if self.state.combat is None:
            return 0
        return self.state.combat.player_attack(monster_idx, damage)

    def combat_gain_block(self, amount: int) -> None:
        if self.state.combat is None:
            return
        self.state.combat.player_gain_block(amount)

    def combat_end_turn(self) -> None:
        if self.state.combat is None:
            return
        self.state.combat.end_player_turn()

    def get_combat_choices(self) -> list[dict[str, Any]]:
        if self.state.combat is None:
            return []
        return self.state.combat.get_pending_choices()

    def choose_combat_option(self, index: int) -> bool:
        if self.state.combat is None:
            return False
        return self.state.combat.choose_combat_option(index)

    def is_combat_over(self) -> bool:
        if self.state.combat is None:
            return True
        return self.state.combat.is_combat_over()

    def player_won_combat(self) -> bool:
        if self.state.combat is None:
            return False
        return self.state.combat.player_won()

    def choose_card_reward(self, card_id: str, not_picked: list[str], upgraded: bool | None = None) -> None:
        pending_rewards = list(getattr(self.state, "pending_card_reward_cards", []) or [])
        if not not_picked and pending_rewards:
            normalized_pick = card_id[:-1] if card_id.endswith("+") else card_id
            remaining_rewards: list[str] = []
            removed_picked = False
            for candidate in pending_rewards:
                normalized_candidate = candidate[:-1] if candidate.endswith("+") else candidate
                if not removed_picked and normalized_candidate == normalized_pick:
                    removed_picked = True
                    continue
                remaining_rewards.append(candidate)
            not_picked = remaining_rewards
        is_upgraded = upgraded if upgraded is not None else card_id.endswith("+")
        actual_id = card_id if card_id.endswith("+") else (f"{card_id}+" if is_upgraded else card_id)
        self.state.deck.append(actual_id)
        self.state.card_choices.append({
            "floor": self.state.floor,
            "picked": card_id,
            "upgraded": is_upgraded,
            "skipped": False,
            "not_picked": not_picked,
        })
        self.state.pending_card_reward_cards = []
        self._resolve_post_reward_phase()

    def skip_card_reward(self) -> None:
        self.state.pending_card_reward_cards = []
        self._resolve_post_reward_phase()

    def _has_pending_reward_surface(self) -> bool:
        pending = self.get_pending_reward_state()
        return bool(
            pending["cards"]
            or pending["gold"]
            or pending["potion"]
            or pending["relic"]
            or pending["relics"]
        )

    def _resolve_post_reward_phase(self) -> None:
        if self._has_pending_reward_surface():
            self.state.phase = RunPhase.REWARD
            return
        if self._resume_victory_after_reward:
            self._resume_victory_after_reward = False
            self.state.phase = RunPhase.VICTORY
            return
        self.state.phase = RunPhase.MAP

    def get_pending_reward_state(self) -> dict[str, Any]:
        pending_relics = list(getattr(self, "_pending_relic_rewards", []) or [])
        return {
            "cards": list(getattr(self.state, "pending_card_reward_cards", []) or []),
            "gold": int(getattr(self, "_pending_gold_reward", 0) or 0),
            "potion": getattr(self, "_pending_potion_reward", None),
            "relic": pending_relics[0] if pending_relics else getattr(self, "_pending_relic_reward", None),
            "relics": pending_relics,
        }

    def clear_pending_reward_notifications(
        self,
        *,
        gold: bool = True,
        potion: bool = True,
        relic: bool = True,
    ) -> None:
        if gold:
            self._pending_gold_reward = 0
        if potion:
            self._pending_potion_reward = None
        if relic:
            self._pending_relic_rewards = []
            self._pending_relic_reward = None
        if self.state.phase == RunPhase.REWARD:
            self._resolve_post_reward_phase()

    def _get_current_event_combat(self) -> dict[str, Any] | None:
        current = self.state.current_event_combat
        return current if isinstance(current, dict) else None

    def _set_current_event_combat(
        self,
        *,
        enemies: list[str],
        bonus_reward: str | None = None,
        pending_event_rewards: list[str] | None = None,
        is_elite_combat: bool = False,
        grant_standard_rewards: bool = False,
        reopen_event: dict[str, Any] | None = None,
    ) -> None:
        self.state.current_event_combat = {
            "enemies": list(enemies),
            "bonus_reward": bonus_reward,
            "is_event_combat": True,
            "is_elite_combat": bool(is_elite_combat),
            "grant_standard_rewards": bool(grant_standard_rewards),
            "pending_event_rewards": list(pending_event_rewards or []),
            "reopen_event": dict(reopen_event or {}),
            "rewards_resolved": False,
        }

    def _clear_current_event_combat(self) -> None:
        self.state.current_event_combat = None

    def _clear_pending_campaign_state(self) -> None:
        self.state.pending_card_reward_cards = []
        self.state.pending_treasure_relic = None
        self.state.pending_chest_relic_choices = []
        self.state.pending_boss_relic_choices = []
        self.state.pending_neow_choice = None
        self.state.neow_options = []
        self._pending_gold_reward = 0
        self._pending_potion_reward = None
        self._pending_relic_rewards = []
        self._pending_relic_reward = None
        self._resume_victory_after_reward = False
        self._clear_current_event()
        self._clear_current_event_combat()

    def _queue_pending_relic_reward(self, relic_id: str) -> None:
        canonical = str(relic_id)
        self._pending_relic_rewards = list(getattr(self, "_pending_relic_rewards", []) or [])
        self._pending_relic_rewards.append(canonical)
        self._pending_relic_reward = self._pending_relic_rewards[0] if self._pending_relic_rewards else None

    def _canonical_relic_id(self, relic_id: str) -> str:
        from sts_py.engine.content.relics import normalize_relic_id

        return str(normalize_relic_id(relic_id) or relic_id)

    def _canonical_card_id(self, card_id: str) -> str:
        from sts_py.engine.content.card_instance import _canonicalize_runtime_card_id

        return _canonicalize_runtime_card_id(str(card_id))

    def _canonical_potion_id(self, potion_id: str | None) -> str:
        from sts_py.engine.content.potions import POTION_DEFINITIONS

        if potion_id is None:
            return ""
        canonical = str(potion_id)
        if canonical in POTION_DEFINITIONS:
            return canonical
        collapsed = canonical.replace(" ", "").replace("_", "")
        if collapsed in POTION_DEFINITIONS:
            return collapsed
        for known_id in POTION_DEFINITIONS:
            if known_id.replace(" ", "").replace("_", "") == collapsed:
                return known_id
        return canonical

    def _normalize_relic_source(self, source: RelicSource | str) -> RelicSource:
        if isinstance(source, RelicSource):
            return source
        try:
            return RelicSource(str(source))
        except ValueError:
            return RelicSource.UNKNOWN

    def _record_relic_history(self, relic_id: str, *, source: RelicSource | str) -> None:
        history = getattr(self.state, "relic_history", None)
        if not isinstance(history, list):
            history = []
        history.append(
            {
                "floor": int(self.state.floor),
                "relic_id": self._canonical_relic_id(relic_id),
                "source": self._normalize_relic_source(source).value,
            }
        )
        self.state.relic_history = history

    def _ensure_current_shop_history(
        self,
        *,
        initial_relic_ids: list[str] | None = None,
        initial_colored_card_ids: list[str] | None = None,
        initial_colorless_card_ids: list[str] | None = None,
        initial_potion_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        history = getattr(self.state, "shop_history", None)
        if not isinstance(history, list):
            history = []
        if history and int(history[-1].get("floor", -1)) == int(self.state.floor):
            entry = history[-1]
        else:
            entry = {
                "floor": int(self.state.floor),
                "surfaced_relic_ids": [],
                "current_relic_ids": [],
                "purchased_relic_ids": [],
                "initial_colored_card_ids": [],
                "current_colored_card_ids": [],
                "surfaced_colored_card_ids": [],
                "initial_colorless_card_ids": [],
                "current_colorless_card_ids": [],
                "surfaced_colorless_card_ids": [],
                "initial_potion_ids": [],
                "current_potion_ids": [],
                "surfaced_potion_ids": [],
            }
            history.append(entry)
        if initial_relic_ids is not None and not entry.get("surfaced_relic_ids"):
            canonical_initial = [self._canonical_relic_id(relic_id) for relic_id in initial_relic_ids]
            entry["surfaced_relic_ids"] = canonical_initial
            entry["current_relic_ids"] = list(canonical_initial)
        if initial_colored_card_ids is not None and not entry.get("initial_colored_card_ids"):
            canonical_initial = [self._canonical_card_id(card_id) for card_id in initial_colored_card_ids]
            entry["initial_colored_card_ids"] = list(canonical_initial)
            entry["current_colored_card_ids"] = list(canonical_initial)
            entry["surfaced_colored_card_ids"] = list(canonical_initial)
        if initial_colorless_card_ids is not None and not entry.get("initial_colorless_card_ids"):
            canonical_initial = [self._canonical_card_id(card_id) for card_id in initial_colorless_card_ids]
            entry["initial_colorless_card_ids"] = list(canonical_initial)
            entry["current_colorless_card_ids"] = list(canonical_initial)
            entry["surfaced_colorless_card_ids"] = list(canonical_initial)
        if initial_potion_ids is not None and not entry.get("initial_potion_ids"):
            canonical_initial = [self._canonical_potion_id(potion_id) for potion_id in initial_potion_ids]
            entry["initial_potion_ids"] = list(canonical_initial)
            entry["current_potion_ids"] = list(canonical_initial)
            entry["surfaced_potion_ids"] = list(canonical_initial)
        self.state.shop_history = history
        return entry

    def _set_current_shop_relic_ids(self, current_relic_ids: list[str]) -> None:
        entry = self._ensure_current_shop_history()
        entry["current_relic_ids"] = [self._canonical_relic_id(relic_id) for relic_id in current_relic_ids]

    def _set_current_shop_colored_card_ids(self, current_card_ids: list[str]) -> None:
        entry = self._ensure_current_shop_history()
        entry["current_colored_card_ids"] = [self._canonical_card_id(card_id) for card_id in current_card_ids]

    def _set_current_shop_colorless_card_ids(self, current_card_ids: list[str]) -> None:
        entry = self._ensure_current_shop_history()
        entry["current_colorless_card_ids"] = [self._canonical_card_id(card_id) for card_id in current_card_ids]

    def _set_current_shop_potion_ids(self, current_potion_ids: list[str]) -> None:
        entry = self._ensure_current_shop_history()
        entry["current_potion_ids"] = [self._canonical_potion_id(potion_id) for potion_id in current_potion_ids]

    def _record_shop_surfaced_relic(self, relic_id: str, *, current_relic_ids: list[str] | None = None) -> None:
        entry = self._ensure_current_shop_history()
        surfaced = entry.setdefault("surfaced_relic_ids", [])
        surfaced.append(self._canonical_relic_id(relic_id))
        if current_relic_ids is not None:
            self._set_current_shop_relic_ids(current_relic_ids)

    def _record_shop_purchased_relic(self, relic_id: str, *, current_relic_ids: list[str] | None = None) -> None:
        entry = self._ensure_current_shop_history()
        purchased = entry.setdefault("purchased_relic_ids", [])
        purchased.append(self._canonical_relic_id(relic_id))
        if current_relic_ids is not None:
            self._set_current_shop_relic_ids(current_relic_ids)

    def _record_shop_surfaced_colored_card(self, card_id: str, *, current_card_ids: list[str] | None = None) -> None:
        entry = self._ensure_current_shop_history()
        surfaced = entry.setdefault("surfaced_colored_card_ids", [])
        surfaced.append(self._canonical_card_id(card_id))
        if current_card_ids is not None:
            self._set_current_shop_colored_card_ids(current_card_ids)

    def _record_shop_surfaced_colorless_card(self, card_id: str, *, current_card_ids: list[str] | None = None) -> None:
        entry = self._ensure_current_shop_history()
        surfaced = entry.setdefault("surfaced_colorless_card_ids", [])
        surfaced.append(self._canonical_card_id(card_id))
        if current_card_ids is not None:
            self._set_current_shop_colorless_card_ids(current_card_ids)

    def _record_shop_surfaced_potion(self, potion_id: str, *, current_potion_ids: list[str] | None = None) -> None:
        entry = self._ensure_current_shop_history()
        surfaced = entry.setdefault("surfaced_potion_ids", [])
        surfaced.append(self._canonical_potion_id(potion_id))
        if current_potion_ids is not None:
            self._set_current_shop_potion_ids(current_potion_ids)

    def _upgrade_random_deck_card(self) -> str | None:
        if self.state.rng is None:
            return None
        upgradeable_indices: list[int] = []
        for idx, card_id in enumerate(self.state.deck):
            upgraded = self._upgrade_card(card_id)
            if upgraded is not None and upgraded != card_id:
                upgradeable_indices.append(idx)
        if not upgradeable_indices:
            return None
        chosen = upgradeable_indices[self.state.rng.relic_rng.random_int(len(upgradeable_indices) - 1)]
        old_card = self.state.deck[chosen]
        upgraded_card = self._upgrade_card(old_card)
        if upgraded_card is None:
            return None
        self.state.deck[chosen] = upgraded_card
        return upgraded_card

    def _upgrade_first_n_cards(self, count: int, *, card_type: str) -> list[str]:
        from sts_py.engine.content.cards_min import ALL_CARD_DEFS, CardType

        upgraded_cards: list[str] = []
        target_type = CardType.ATTACK if card_type == "attack" else CardType.SKILL
        for idx, card_id in enumerate(list(self.state.deck)):
            if len(upgraded_cards) >= count:
                break
            base_id = _deck_card_base_id(card_id)
            card_def = ALL_CARD_DEFS.get(base_id)
            if card_def is None or card_def.card_type != target_type:
                continue
            upgraded_card = self._upgrade_card(card_id)
            if upgraded_card is None or upgraded_card == card_id:
                continue
            self.state.deck[idx] = upgraded_card
            upgraded_cards.append(upgraded_card)
        return upgraded_cards

    def _remove_first_n_cards(self, count: int, *, exclude_unremovable: bool = False) -> list[str]:
        from sts_py.engine.run.events import _apply_parasite_penalty, _can_remove_card

        removed_cards: list[str] = []
        remaining_deck: list[str] = []
        removed_needed = max(0, int(count))
        for card_id in self.state.deck:
            can_remove = _can_remove_card(self.state, card_id)
            if removed_needed > 0 and can_remove and (not exclude_unremovable or can_remove):
                _apply_parasite_penalty(self.state, card_id)
                removed_cards.append(card_id)
                removed_needed -= 1
            else:
                remaining_deck.append(card_id)
        self.state.deck = remaining_deck
        return removed_cards

    def _apply_shop_enter_effects(self) -> list[dict[str, Any]]:
        from sts_py.engine.content.relics import RelicEffectType, get_relic_by_id

        applied: list[dict[str, Any]] = []
        for relic_id in self.state.relics:
            relic_def = get_relic_by_id(relic_id)
            if relic_def is None:
                continue
            for effect in relic_def.effects:
                if effect.effect_type != RelicEffectType.ON_SHOP_ENTER:
                    continue
                extra_type = str(effect.extra.get("type", "") or "")
                if extra_type == "heal":
                    heal = min(int(effect.value or 0), self.state.player_max_hp - self.state.player_hp)
                    self.state.player_hp += heal
                    applied.append({"type": "heal", "amount": heal, "relic_id": relic_def.id})
        return applied

    def _apply_chest_open_effects(self) -> list[dict[str, Any]]:
        from sts_py.engine.content.cards_min import ALL_CURSE_DEFS
        from sts_py.engine.content.relics import RelicEffectType, get_relic_by_id

        applied: list[dict[str, Any]] = []
        for relic_id in self.state.relics:
            relic_def = get_relic_by_id(relic_id)
            if relic_def is None:
                continue
            for effect in relic_def.effects:
                if effect.effect_type != RelicEffectType.ON_CHEST_OPEN:
                    continue
                extra_type = str(effect.extra.get("type", "") or "")
                if extra_type == "add_curse":
                    excluded = {str(card_id) for card_id in (effect.extra.get("exclude_curse") or [])}
                    candidates = [card_id for card_id in ALL_CURSE_DEFS if card_id not in excluded]
                    if not candidates:
                        continue
                    if self.state.rng is not None:
                        curse_id = candidates[self.state.rng.relic_rng.random_int(len(candidates) - 1)]
                    else:
                        curse_id = candidates[0]
                    self.state.deck.append(curse_id)
                    applied.append({"type": "add_curse", "card_id": curse_id, "relic_id": relic_def.id})
        return applied

    def _transform_card_candidates_for_character(self) -> list[str]:
        from sts_py.engine.rewards.card_rewards_min import character_pools

        pools = character_pools(self.state.character_class)
        candidates: list[str] = []
        for pool in pools.values():
            for card_def in pool:
                if card_def.id not in candidates:
                    candidates.append(card_def.id)
        return candidates

    def _transform_deck_card(self, card_id: str, *, upgrade: bool = False) -> str:
        candidates = [candidate for candidate in self._transform_card_candidates_for_character() if candidate != card_id]
        if not candidates:
            return card_id
        if self.state.rng is not None:
            chosen = candidates[self.state.rng.relic_rng.random_int(len(candidates) - 1)]
        else:
            chosen = candidates[0]
        if upgrade:
            upgraded = self._upgrade_card(chosen)
            if upgraded is not None:
                return upgraded
        return chosen

    def _transform_first_n_cards(self, count: int, *, upgrade: bool = False) -> list[dict[str, str]]:
        from sts_py.engine.run.events import _can_remove_card

        transformed: list[dict[str, str]] = []
        remaining = max(0, int(count))
        for idx, deck_card in enumerate(list(self.state.deck)):
            if remaining <= 0:
                break
            if not _can_remove_card(self.state, deck_card):
                continue
            new_card = self._transform_deck_card(deck_card, upgrade=upgrade)
            self.state.deck[idx] = new_card
            transformed.append({"old_card": deck_card, "new_card": new_card})
            remaining -= 1
        return transformed

    def _apply_relic_pickup_effect(self, relic_id: str, effect: Any) -> dict[str, Any] | None:
        extra_type = str(effect.extra.get("type", "") or "")
        value = int(effect.value or 0)

        if extra_type == "potion_slots":
            for _ in range(value):
                self.state.potions.append("EmptyPotionSlot")
            return {"type": "potion_slots", "count": value}
        if extra_type == "max_hp":
            self.state.player_max_hp += value
            self.state.player_hp += value
            return {"type": "max_hp", "amount": value}
        if extra_type == "max_hp_and_heal":
            self.state.player_max_hp += value
            self.state.player_hp = self.state.player_max_hp
            return {"type": "max_hp_and_heal", "amount": value}
        if extra_type == "upgrade_skills":
            upgraded = self._upgrade_first_n_cards(value, card_type="skill")
            return {"type": "upgrade_skills", "cards": upgraded}
        if extra_type == "upgrade_attacks":
            upgraded = self._upgrade_first_n_cards(value, card_type="attack")
            return {"type": "upgrade_attacks", "cards": upgraded}
        if extra_type == "transform_all_strikes_defends":
            transformed: list[dict[str, str]] = []
            for idx, deck_card in enumerate(list(self.state.deck)):
                base_id = re.sub(r"\+\d+$", "", deck_card).rstrip("+")
                if base_id not in {"Strike", "Defend", "Strike_B", "Defend_B"}:
                    continue
                new_card = self._transform_deck_card(base_id)
                self.state.deck[idx] = new_card
                transformed.append({"old_card": deck_card, "new_card": new_card})
            return {"type": "transform_all_strikes_defends", "cards": transformed}
        if extra_type == "transform_3_cards":
            transformed = self._transform_first_n_cards(3, upgrade=bool(effect.extra.get("upgrade")))
            return {"type": "transform_3_cards", "cards": transformed}
        if extra_type == "gain_curse_and_relics":
            curse_id = str(effect.extra.get("curse") or "CurseOfTheBell")
            curse_id = "CurseOfTheBell" if curse_id == "Curse" else curse_id
            self.state.deck.append(curse_id)
            gained_relics: list[str] = []
            for _ in range(int(effect.extra.get("relic_count") or 0)):
                gained = self._grant_random_relic(
                    source=RelicSource.CALLING_BELL,
                    record_pending=True,
                )
                if gained is not None:
                    gained_relics.append(gained)
            return {"type": "gain_curse_and_relics", "curse": curse_id, "relics": gained_relics}
        if extra_type == "full_restore":
            self.state.player_hp = self.state.player_max_hp
            return {"type": "full_restore"}
        return None

    def _apply_relic_acquisition_effects(self, relic_id: str) -> list[dict[str, Any]]:
        from sts_py.engine.content.relics import RelicEffectType, get_relic_by_id

        relic_def = get_relic_by_id(relic_id)
        if relic_def is None:
            return []

        applied: list[dict[str, Any]] = []
        for effect in relic_def.effects:
            if effect.effect_type == RelicEffectType.REPLACE_STARTER_RELIC:
                replaced = self._canonical_relic_id(str(effect.extra.get("replaced") or ""))
                if replaced:
                    self.state.relics = [
                        owned_relic
                        for owned_relic in self.state.relics
                        if self._canonical_relic_id(owned_relic) != replaced
                    ]
                    applied.append({"type": "replace_starter_relic", "replaced": replaced})
            elif effect.effect_type == RelicEffectType.ON_PICKUP:
                pickup_result = self._apply_relic_pickup_effect(relic_def.id, effect)
                if pickup_result is not None:
                    applied.append(pickup_result)
            elif effect.effect_type == RelicEffectType.GAIN_GOLD:
                self.state.player_gold += int(effect.value)
                applied.append({"type": "gain_gold", "amount": int(effect.value)})
            elif effect.effect_type == RelicEffectType.GAIN_MAX_HP:
                self.state.player_max_hp += int(effect.value)
                self.state.player_hp += int(effect.value)
                applied.append({"type": "gain_max_hp", "amount": int(effect.value)})
            elif effect.effect_type == RelicEffectType.GAIN_POTION:
                from sts_py.engine.combat.potion_effects import get_random_potion_by_rarity, roll_potion_rarity

                gained: list[str] = []
                for _ in range(int(effect.value or 0)):
                    rarity = roll_potion_rarity()
                    potion = get_random_potion_by_rarity(rarity, self.state.character_class)
                    if potion and self.gain_potion(potion.potion_id):
                        gained.append(potion.potion_id)
                applied.append({"type": "gain_potion", "potions": gained})
            elif effect.effect_type == RelicEffectType.UPGRADE_RANDOM:
                upgraded = self._upgrade_random_deck_card()
                applied.append({"type": "upgrade_random", "card": upgraded})
            elif effect.effect_type == RelicEffectType.REMOVE_CARDS_FROM_DECK:
                removed = self._remove_first_n_cards(int(effect.value or 0), exclude_unremovable=bool(effect.extra.get("exclude_unremovable")))
                applied.append({"type": "remove_cards_from_deck", "cards": removed})
            elif effect.effect_type == RelicEffectType.CHEST_RELICS:
                self.state.relic_counters[relic_def.id] = int(effect.extra.get("chests") or effect.value or 0)
                applied.append({"type": "chest_relics", "count": self.state.relic_counters[relic_def.id]})
            elif effect.effect_type == RelicEffectType.CARD_REWARD and relic_def.id == "TinyHouse":
                self._add_card_reward(current_room=None, is_event_combat=False)
                applied.append({"type": "card_reward", "count": len(self.state.pending_card_reward_cards)})
        return applied

    def _acquire_relic(
        self,
        relic_id: str,
        *,
        source: RelicSource | str = RelicSource.UNKNOWN,
        record_pending: bool = True,
    ) -> str | None:
        from sts_py.engine.content.relics import get_relic_by_id

        relic_def = get_relic_by_id(relic_id)
        canonical_id = relic_def.id if relic_def is not None else str(relic_id)
        self.state.relics.append(canonical_id)
        self._record_relic_history(canonical_id, source=source)
        if record_pending:
            self._queue_pending_relic_reward(canonical_id)
        self._apply_relic_acquisition_effects(canonical_id)
        return canonical_id

    def _grant_random_relic(
        self,
        *,
        source: RelicSource | str = RelicSource.UNKNOWN,
        record_pending: bool = True,
    ) -> str | None:
        from sts_py.engine.content.relics import get_random_relic_by_tier, roll_relic_rarity

        rng = self.state.rng.relic_rng if self.state.rng is not None else None
        rarity = roll_relic_rarity(rng)
        relic_id = get_random_relic_by_tier(rarity.value, rng)
        if relic_id:
            return self._acquire_relic(relic_id, source=source, record_pending=record_pending)
        return None

    def _add_card_reward(
        self,
        *,
        current_room: MapNode | None = None,
        is_event_combat: bool = False,
    ) -> None:
        from sts_py.engine.rewards.card_rewards_min import RewardGenState, character_pools, get_reward_cards

        if self.state.rng is None:
            self.state.pending_card_reward_cards = []
            self.state.phase = RunPhase.REWARD
            return

        reward_state = self.state.reward_state
        if reward_state is None:
            reward_state = RewardGenState()

        reward_count = 3
        if self._has_relic("QuestionCard"):
            reward_count += 1
        if self._has_relic("BustedCrown"):
            reward_count -= 2
        if (
            current_room is not None
            and current_room.room_type == RoomType.MONSTER
            and not is_event_combat
            and self._has_relic("PrayerWheel")
        ):
            reward_count += 1
        reward_count = max(1, reward_count)

        reward_rng = self.state.rng.card_rng.to_immutable()
        next_rng, next_reward_state, reward_cards = get_reward_cards(
            reward_rng,
            reward_state,
            character_pools(self.state.character_class),
            n=reward_count,
        )
        self.state.rng.card_rng._rng = next_rng
        self.state.reward_state = next_reward_state
        self.state.pending_card_reward_cards = [card.id for card in reward_cards]
        self.state.phase = RunPhase.REWARD

    def rest(self, heal_percent: float = 0.3) -> int:
        heal_amount = int(self.state.player_max_hp * heal_percent)
        heal_bonus = self._get_rest_heal_bonus()
        heal_amount += heal_bonus
        actual_heal = min(heal_amount, self.state.player_max_hp - self.state.player_hp)
        self.state.player_hp += actual_heal
        self._trigger_relic_effects("on_rest")
        if self.state.phase != RunPhase.REWARD:
            self.state.phase = RunPhase.MAP
        return actual_heal

    def _get_rest_heal_bonus(self) -> int:
        from sts_py.engine.content.relics import RelicEffectType, get_relic_by_id
        bonus = 0
        for relic_id in self.state.relics:
            relic_def = get_relic_by_id(relic_id)
            if relic_def is None:
                continue
            for effect in relic_def.effects:
                if effect.effect_type == RelicEffectType.REST_HEAL_BONUS:
                    bonus += effect.value
        return bonus

    def _trigger_relic_effects(self, trigger_type: str) -> None:
        from sts_py.engine.content.relics import RelicEffectType, get_relic_by_id
        for relic_id in self.state.relics:
            relic_def = get_relic_by_id(relic_id)
            if relic_def is None:
                continue
            for effect in relic_def.effects:
                if effect.effect_type == RelicEffectType.ON_REST:
                    extra_type = effect.extra.get("type", "")
                    if extra_type == "tea_set_pending":
                        self.state.player_pending_tea_energy = 2
                    elif extra_type == "bonus_energy":
                        self.state.player_energy += effect.value
                    elif extra_type == "card_reward":
                        self._add_card_reward()
                    elif extra_type == "heal":
                        heal = min(effect.value, self.state.player_max_hp - self.state.player_hp)
                        self.state.player_hp += heal

    def _apply_post_combat_relic_effects(self) -> list[dict[str, Any]]:
        from sts_py.engine.content.relics import RelicEffectType, get_relic_by_id

        applied: list[dict[str, Any]] = []
        for relic_id in self.state.relics:
            relic_def = get_relic_by_id(relic_id)
            if relic_def is None:
                continue
            for effect in relic_def.effects:
                if effect.effect_type != RelicEffectType.ON_COMBAT_END:
                    continue
                extra_type = str(effect.extra.get("type", "") or "")
                condition = str(effect.extra.get("condition", "") or "")
                if extra_type != "heal":
                    continue
                if condition == "hp_below_50" and not (
                    self.state.player_hp > 0 and self.state.player_hp <= (self.state.player_max_hp / 2)
                ):
                    continue
                heal = min(int(effect.value or 0), self.state.player_max_hp - self.state.player_hp)
                if heal <= 0:
                    continue
                self.state.player_hp += heal
                applied.append({"type": "heal", "amount": heal, "relic_id": self._canonical_relic_id(relic_def.id)})
        return applied

    def is_run_over(self) -> bool:
        return self.state.phase in (RunPhase.GAME_OVER, RunPhase.VICTORY)

    def has_all_act4_keys(self) -> bool:
        return (
            self.state.ruby_key_obtained
            and self.state.emerald_key_obtained
            and self.state.sapphire_key_obtained
        )

    def _enter_act4(self) -> None:
        self.state.act = 4
        self.state.floor = 51
        self.state.current_node_idx = -1
        self.state.monster_list_idx = 0
        self.state.elite_list_idx = 0
        self.state.path_taken = []
        self.state.path_trace = []
        self.state.combat_history = []
        self.state.card_choices = []
        self.state.combat = None
        self._shop_engine = None
        self._current_event = None
        self._clear_pending_campaign_state()
        self.state.event_list = []
        self.state.shrine_list = []

        self._reseed_rng_for_act(4)
        self._generate_map()
        self.state.phase = RunPhase.MAP

    def transition_to_next_act(self) -> None:
        if self.state.phase != RunPhase.VICTORY:
            return
        if self.state.pending_boss_relic_choices:
            return

        if self.state.act == 3:
            if self.has_all_act4_keys():
                self._enter_act4()
            return

        if self.state.act >= 4:
            return

        self.state.act += 1
        self.state.player_hp = self.state.player_max_hp
        self.state.floor = 17 * (self.state.act - 1)  # Act 1: F00-F17, Act 2: F18-F34, Act 3: F35-F51
        self.state.current_node_idx = -1
        self.state.monster_list_idx = 0
        self.state.elite_list_idx = 0
        self.state.path_taken = []
        self.state.path_trace = []
        self.state.combat_history = []
        self.state.card_choices = []
        self._clear_pending_campaign_state()
        self._initialize_event_pools_for_act()
        self._reset_question_room_probabilities()

        self._reseed_rng_for_act(self.state.act)
        self._generate_encounters_for_act()
        self._generate_map()

        self.state.phase = RunPhase.MAP

    def transition_to_act_for_replay(self, act: int, floor: int | None = None) -> None:
        """Advance replay state to a later act without clearing accumulated history."""
        if act <= self.state.act:
            return

        self.state.act = act
        self.state.current_node_idx = -1
        self.state.monster_list_idx = 0
        self.state.elite_list_idx = 0
        self.state.combat = None
        self._shop_engine = None
        self._current_event = None
        self._clear_pending_campaign_state()
        self._initialize_event_pools_for_act()
        self._reset_question_room_probabilities()

        self._reseed_rng_for_act(act)
        self._generate_encounters_for_act()
        self._generate_map()

        self.state.floor = floor if floor is not None else 17 * (act - 1)
        self.state.phase = RunPhase.MAP

    def get_state_hash(self) -> str:
        from sts_py.engine.core.canon import state_hash, asdict
        return state_hash(asdict(self.state.to_dict()))

    _current_event: "Event | None" = None
    _shop_engine: "ShopEngine | None" = None

    def _enter_event(self) -> None:
        from sts_py.engine.run.events import build_event
        if self.state.rng is None:
            return
        event_key = self._generate_event_key()
        if event_key is None:
            return
        self._set_current_event(build_event(event_key, self.state.rng.event_rng))

    def get_current_event(self) -> "Event | None":
        return self._current_event

    def get_event_choices(self) -> list[str]:
        if self._current_event is None:
            return []
        return [c.description for c in self._current_event.choices]

    def choose_event_option(self, choice_index: int) -> dict[str, Any]:
        if self._current_event is None:
            return {"success": False, "reason": "no_event"}

        event = self._current_event
        choice = event.get_choice(choice_index)
        if choice is None:
            return {"success": False, "reason": "invalid_choice"}
        if not getattr(choice, "enabled", True):
            return {"success": False, "reason": "choice_disabled"}

        event_id = str(getattr(event, "event_id", getattr(event, "id", "")) or "")
        event_key = str(getattr(event, "event_key", "") or "")
        handler_key = self._event_handler_key(event)

        custom_result = self._dispatch_event_handler(handler_key, choice_index)
        if custom_result is not None:
            if self.state.phase == RunPhase.GAME_OVER:
                self._record_standard_run_profile_outcome(victory=False)
            return custom_result

        if event_id in {"DeadAdventurer", "Dead Adventurer"} or event_key == "Dead Adventurer":
            return self._handle_dead_adventurer(choice_index)
        if event_id in {"GoldenIdolEvent", "Golden Shrine"} or event_key == "Golden Idol":
            return self._handle_golden_shrine(choice_index)
        if event_id == "Golden Shrine Trap" or event_key == "Golden Shrine Trap":
            return self._handle_golden_shrine_trap(choice_index)
        if event_id in {"GoopPuddle", "World of Goop"} or event_key == "World of Goop":
            return self._handle_world_of_goop(choice_index)
        if event_id in {"GoldenWing", "Wing Statuette"} or event_key == "Golden Wing":
            return self._handle_wing_statuette(choice_index)
        if event_id in {"LivingWall", "Living Wall"} or event_key == "Living Wall":
            return self._handle_living_wall(choice_index)
        if event_id == "Mushrooms" or event_key == "Mushrooms":
            return self._handle_mushrooms(choice_index)
        if event_id in {"ScrapOoze", "Scrap Ooze"} or event_key == "Scrap Ooze":
            return self._handle_scrap_ooze(choice_index)
        if event_id in {"ShiningLight", "Shining Light"} or event_key == "Shining Light":
            return self._handle_shining_light(choice_index)
        if event_id in {"FaceTrader", "Face Trader"} or event_key == "FaceTrader":
            return self._handle_face_trader(choice_index)

        from sts_py.engine.run.events import EventEffectType
        if choice.requires_card_removal or choice.requires_card_transform or choice.requires_card_upgrade:
            if not self.state.deck:
                return {"success": False, "reason": "no_cards_in_deck"}

            if choice.requires_card_removal:
                effect_type = EventEffectType.CHOOSE_CARD_TO_REMOVE.value
            elif choice.requires_card_transform:
                effect_type = EventEffectType.CHOOSE_CARD_TO_TRANSFORM.value
            else:
                effect_type = EventEffectType.CHOOSE_CARD_TO_UPGRADE.value

            self.state.pending_card_choice = {
                "choice_index": choice_index,
                "effect_type": effect_type,
            }
            return {
                "success": True,
                "requires_card_choice": True,
                "effect_type": effect_type,
                "choice_index": choice_index,
            }

        for effect in choice.effects:
            if effect.effect_type in (EventEffectType.CHOOSE_CARD_TO_REMOVE, EventEffectType.CHOOSE_CARD_TO_TRANSFORM, EventEffectType.CHOOSE_CARD_TO_UPGRADE):
                if not self.state.deck:
                    return {"success": False, "reason": "no_cards_in_deck"}
                self.state.pending_card_choice = {
                    "choice_index": choice_index,
                    "effect_type": effect.effect_type.value,
                }
                return {
                    "success": True,
                    "requires_card_choice": True,
                    "effect_type": effect.effect_type.value,
                    "choice_index": choice_index,
                }

        result = choice.apply(self)
        self.state.event_choices.append({
            "floor": self.state.floor,
            "event_id": event.id,
            "event_key": getattr(event, "event_key", None),
            "choice_index": choice_index,
            "choice_text": choice.description,
        })
        self._clear_current_event()
        self.state.phase = RunPhase.MAP

        if self.state.player_hp <= 0:
            self.state.phase = RunPhase.GAME_OVER
            self._record_standard_run_profile_outcome(victory=False)

        return result

    def choose_card_for_event(self, card_index: int) -> dict[str, Any]:
        """Handle player choosing a card for events like card remove/transform/upgrade."""
        if self._current_event is None:
            return {"success": False, "reason": "no_event"}

        if self.state.pending_card_choice is None:
            return {"success": False, "reason": "no_pending_card_choice"}

        pending = self.state.pending_card_choice
        if pending.get("custom_action"):
            return self._resolve_custom_event_card_choice(card_index)
        choice_index = pending["choice_index"]
        effect_type = pending["effect_type"]

        event = self._current_event
        choice = event.get_choice(choice_index)
        if choice is None:
            return {"success": False, "reason": "invalid_choice"}

        pending_deck_indexes = list(pending.get("deck_indexes") or [])
        if pending_deck_indexes:
            if card_index < 0 or card_index >= len(pending_deck_indexes):
                return {"success": False, "reason": "invalid_card_index"}
            deck_index = pending_deck_indexes[card_index]
            if deck_index < 0 or deck_index >= len(self.state.deck):
                return {"success": False, "reason": "invalid_card_index"}
            card_id = self.state.deck[deck_index]
        else:
            if card_index < 0 or card_index >= len(self.state.deck):
                return {"success": False, "reason": "invalid_card_index"}
            deck_index = card_index
            card_id = self.state.deck[deck_index]

        from sts_py.engine.run.events import EventEffectType, _apply_parasite_penalty, _get_transformed_card

        if effect_type == EventEffectType.CHOOSE_CARD_TO_REMOVE.value:
            _apply_parasite_penalty(self.state, card_id)
            self.state.deck.pop(deck_index)
            result = {"success": True, "action": "card_removed", "card_id": card_id}
        elif effect_type == EventEffectType.CHOOSE_CARD_TO_TRANSFORM.value:
            _apply_parasite_penalty(self.state, card_id)
            handler_key = self._event_handler_key(event)
            if handler_key in {"Living Wall", "Transmorgrifier"}:
                rng = self._misc_rng()
            else:
                rng = getattr(getattr(self.state, "rng", None), "card_random_rng", None)
                if rng is None:
                    rng = getattr(getattr(self.state, "rng", None), "event_rng", None)
            transformed_card = _get_transformed_card(card_id, rng)
            self.state.deck[deck_index] = transformed_card
            result = {
                "success": True,
                "action": "card_transformed",
                "old_card": card_id,
                "new_card": transformed_card,
            }
        elif effect_type == EventEffectType.CHOOSE_CARD_TO_UPGRADE.value:
            upgraded_card = self._upgrade_card(card_id)
            if not upgraded_card or upgraded_card == card_id:
                return {"success": False, "reason": "card_cannot_be_upgraded", "card_id": card_id}
            self.state.deck[deck_index] = upgraded_card
            result = {
                "success": True,
                "action": "card_upgraded",
                "old_card": card_id,
                "new_card": upgraded_card,
            }
        else:
            return {"success": False, "reason": "unknown_effect_type"}

        self.state.event_choices.append({
            "floor": self.state.floor,
            "event_id": event.id,
            "event_key": getattr(event, "event_key", None),
            "choice_index": choice_index,
            "choice_text": choice.description,
            "card_id": card_id,
        })

        self._clear_current_event()
        self.state.pending_card_choice = None
        self.state.phase = RunPhase.MAP

        if self.state.player_hp <= 0:
            self.state.phase = RunPhase.GAME_OVER

        return result

    def _record_current_event_choice(
        self,
        event: "Event",
        *,
        choice_index: int,
        choice_text: str,
        **extra: Any,
    ) -> None:
        entry = {
            "floor": self.state.floor,
            "event_id": getattr(event, "event_id", getattr(event, "id", "")),
            "event_key": getattr(event, "event_key", None),
            "choice_index": choice_index,
            "choice_text": choice_text,
        }
        entry.update(extra)
        self.state.event_choices.append(entry)

    def _finish_event(self, *, next_phase: RunPhase = RunPhase.MAP) -> None:
        self._clear_current_event()
        self.state.phase = next_phase
        if self.state.player_hp <= 0:
            self.state.phase = RunPhase.GAME_OVER

    def _draw_random_relic_of_tier(self, tier_name: str) -> str | None:
        from sts_py.engine.content.relics import get_random_relic_by_tier

        rng = getattr(getattr(self.state, "rng", None), "relic_rng", None)
        return get_random_relic_by_tier(str(tier_name).upper(), rng)

    def _remove_potion_id(self, potion_id: str) -> bool:
        for idx, candidate in enumerate(self.state.potions):
            if candidate == potion_id:
                self.state.potions[idx] = "EmptyPotionSlot"
                return True
        return False

    def _gain_random_event_potions(self, count: int) -> list[str]:
        from sts_py.engine.combat.potion_effects import get_random_potion_by_rarity, roll_potion_rarity

        gained: list[str] = []
        for _ in range(max(0, int(count))):
            rarity = roll_potion_rarity()
            potion = get_random_potion_by_rarity(rarity, self.state.character_class)
            if potion and self.gain_potion(potion.potion_id):
                gained.append(potion.potion_id)
        if gained:
            self._pending_potion_reward = gained[0]
        return gained

    def _dispatch_event_handler(self, handler_key: str, choice_index: int) -> dict[str, Any] | None:
        handlers = {
            "Big Fish": self._handle_big_fish_event,
            "The Cleric": self._handle_cleric_event,
            "Beggar": self._handle_beggar_event,
            "Liars Game": self._handle_liars_game_event,
            "Addict": self._handle_addict_event,
            "Back to Basics": self._handle_back_to_basics_event,
            "Cursed Tome": self._handle_cursed_tome_event,
            "Drug Dealer": self._handle_drug_dealer_event,
            "Forgotten Altar": self._handle_forgotten_altar_event,
            "Designer": self._handle_designer_event,
            "Ghosts": self._handle_ghosts_event,
            "Masked Bandits": self._handle_masked_bandits_event,
            "Nest": self._handle_nest_event,
            "The Library": self._handle_library_event,
            "The Mausoleum": self._handle_mausoleum_event,
            "Vampires": self._handle_vampires_event,
            "Golden Shrine": self._handle_golden_shrine_event,
            "FaceTrader": self._handle_face_trader,
            "Fountain of Cleansing": self._handle_fountain_event,
            "Knowing Skull": self._handle_knowing_skull_event,
            "Duplicator": self._handle_duplicator_event,
            "Purifier": self._handle_purifier_event,
            "Upgrade Shrine": self._handle_upgrade_shrine_event,
            "Transmorgrifier": self._handle_transmorgrifier_event,
            "Accursed Blacksmith": self._handle_accursed_blacksmith_event,
            "Lab": self._handle_lab_event,
            "Match and Keep!": self._handle_match_and_keep_event,
            "N'loth": self._handle_nloth_event,
            "NoteForYourself": self._handle_note_for_yourself_event,
            "SecretPortal": self._handle_secret_portal_event,
            "WeMeetAgain": self._handle_we_meet_again_event,
            "The Woman in Blue": self._handle_woman_in_blue_event,
            "The Joust": self._handle_the_joust_event,
            "Falling": self._handle_falling_event,
            "MindBloom": self._handle_mind_bloom_event,
            "The Moai Head": self._handle_moai_head_event,
            "Mysterious Sphere": self._handle_mysterious_sphere_event,
            "SensoryStone": self._handle_sensory_stone_event,
            "Tomb of Lord Red Mask": self._handle_tomb_red_mask_event,
            "Wheel of Change": self._handle_wheel_of_change_event,
            "Winding Halls": self._handle_winding_halls_event,
            "Colosseum": self._handle_colosseum_event,
            "Bonfire Elementals": self._handle_bonfire_event,
            "SpireHeart": self._handle_spire_heart_event,
        }
        handler = handlers.get(handler_key)
        if handler is None:
            return None
        return handler(choice_index)

    def _resolve_custom_event_card_choice(self, card_index: int) -> dict[str, Any]:
        event = self._current_event
        pending = self.state.pending_card_choice or {}
        if event is None:
            return {"success": False, "reason": "no_event"}

        cards = list(pending.get("cards") or [])
        if card_index < 0 or card_index >= len(cards):
            return {"success": False, "reason": "invalid_card_index"}

        action = str(pending.get("custom_action", "") or "")
        if action == "duplicate_card":
            card_id = cards[card_index]
            self.state.deck.append(card_id)
            self._record_current_event_choice(event, choice_index=int(pending.get("choice_index", 0)), choice_text=f"Duplicate {card_id}", card_id=card_id)
            self._finish_event()
            return {"success": True, "action": "card_duplicated", "card_id": card_id}
        if action == "drug_dealer_transform":
            deck_indexes = list(pending.get("deck_indexes") or [])
            selected = list(pending.get("selected", []) or [])
            selected.append(deck_indexes[card_index] if deck_indexes else card_index)
            remaining_indexes = [idx for i, idx in enumerate(deck_indexes) if i != card_index]
            remaining_cards = [card for i, card in enumerate(cards) if i != card_index]
            if len(selected) < 2:
                pending["selected"] = selected
                pending["deck_indexes"] = remaining_indexes
                pending["cards"] = remaining_cards
                self.state.pending_card_choice = pending
                return {"success": True, "action": "select_next_card", "remaining": 2 - len(selected)}
            from sts_py.engine.run.events import _get_transformed_card

            rng = self._misc_rng()
            transformed: list[dict[str, str]] = []
            for deck_index in sorted(selected):
                old_card = self.state.deck[deck_index]
                new_card = _get_transformed_card(old_card, rng)
                self.state.deck[deck_index] = new_card
                transformed.append({"old_card": old_card, "new_card": new_card})
            self._record_current_event_choice(
                event,
                choice_index=int(pending.get("choice_index", 0)),
                choice_text="Transform 2 cards",
                transformed=transformed,
            )
            self._finish_event()
            return {"success": True, "action": "cards_transformed", "transformed": transformed}
        if action == "bonfire_offer":
            deck_indexes = list(pending.get("deck_indexes") or [])
            deck_index = deck_indexes[card_index] if deck_indexes else card_index
            card_id = self.state.deck.pop(deck_index)
            rarity = "COMMON"
            try:
                from sts_py.engine.content.card_instance import get_runtime_card_base_id
                from sts_py.engine.content.cards_min import ALL_CARD_DEFS

                base_id = get_runtime_card_base_id(card_id)
                rarity = str(getattr(ALL_CARD_DEFS.get(base_id), "rarity", "COMMON"))
                if "." in rarity:
                    rarity = rarity.rsplit(".", 1)[-1]
            except Exception:
                rarity = "COMMON"
            result: dict[str, Any] = {"success": True, "action": "bonfire_offer", "card_id": card_id, "rarity": rarity}
            if rarity == "CURSE":
                relic_id = "SpiritPoop" if not self._has_relic("SpiritPoop") else "Circlet"
                self._acquire_relic(relic_id, source=RelicSource.EVENT, record_pending=True)
                result["relic_id"] = relic_id
            elif rarity in {"COMMON", "SPECIAL"}:
                healed = min(5, self.state.player_max_hp - self.state.player_hp)
                self.state.player_hp += healed
                result["heal"] = healed
            elif rarity == "UNCOMMON":
                healed = self.state.player_max_hp - self.state.player_hp
                self.state.player_hp = self.state.player_max_hp
                result["heal"] = healed
            elif rarity == "RARE":
                self.state.player_max_hp += 10
                self.state.player_hp = self.state.player_max_hp
                result["max_hp_gain"] = 10
            self._record_current_event_choice(
                event,
                choice_index=int(pending.get("choice_index", 0)),
                choice_text=f"Offered {card_id}",
                offered_card=card_id,
                rarity=rarity,
            )
            self._finish_event()
            return result
        if action == "designer_remove_and_upgrade":
            deck_indexes = list(pending.get("deck_indexes") or [])
            deck_index = deck_indexes[card_index] if deck_indexes else card_index
            removed_card = self.state.deck.pop(deck_index)
            upgraded_card = self._upgrade_random_deck_card()
            self._record_current_event_choice(
                event,
                choice_index=int(pending.get("choice_index", 0)),
                choice_text="Designer full service",
                removed_card=removed_card,
                upgraded_card=upgraded_card,
            )
            self._finish_event()
            return {"success": True, "action": "designer_full_service", "removed_card": removed_card, "upgraded_card": upgraded_card}
        if action == "library_take_card":
            card_id = str(pending.get("offered_cards", cards)[card_index])
            self.state.deck.append(card_id)
            self._record_current_event_choice(
                event,
                choice_index=int(pending.get("choice_index", 0)),
                choice_text="Read",
                card_id=card_id,
            )
            self._finish_event()
            return {"success": True, "action": "obtained_card", "card_id": card_id}
        if action == "note_for_yourself_store":
            from sts_py.engine.content.card_instance import CardInstance

            deck_indexes = list(pending.get("deck_indexes") or [])
            deck_index = deck_indexes[card_index] if deck_indexes else card_index
            removed_card = self.state.deck.pop(deck_index)
            stored_card = str(pending.get("stored_card", "") or "")
            removed_instance = CardInstance(removed_card)
            self._save_note_for_yourself_payload(card_id=removed_instance.card_id, upgrades=int(removed_instance.times_upgraded))
            self._record_current_event_choice(
                event,
                choice_index=int(pending.get("choice_index", 0)),
                choice_text="Took stored card",
                obtained_card=stored_card,
                stored_card=removed_card,
            )
            self._finish_event()
            return {"success": True, "action": "stored_card", "obtained_card": stored_card, "stored_card": removed_card}
        if action == "match_and_keep_pick":
            board = list(pending.get("board") or [])
            matched = {int(idx) for idx in (pending.get("matched") or [])}
            if card_index in matched or card_index < 0 or card_index >= len(board):
                return {"success": False, "reason": "invalid_card_index"}
            first_pick = pending.get("first_pick")
            if first_pick is None:
                pending["first_pick"] = int(card_index)
                self.state.pending_card_choice = pending
                return {
                    "success": True,
                    "action": "first_reveal",
                    "card_id": board[card_index],
                    "attempts_remaining": int(pending.get("attempts_remaining", 0) or 0),
                }
            if int(first_pick) == int(card_index):
                return {"success": False, "reason": "same_card_selected"}
            attempts_remaining = max(0, int(pending.get("attempts_remaining", 0) or 0) - 1)
            pending["attempts_remaining"] = attempts_remaining
            pending["first_pick"] = None
            matched_cards = list(pending.get("matched_cards") or [])
            if board[int(first_pick)] == board[card_index]:
                matched.update({int(first_pick), int(card_index)})
                pending["matched"] = sorted(matched)
                matched_cards.append(board[card_index])
                pending["matched_cards"] = matched_cards
                self.state.deck.append(board[card_index])
                result: dict[str, Any] = {
                    "success": True,
                    "action": "match",
                    "card_id": board[card_index],
                    "attempts_remaining": attempts_remaining,
                    "cards_matched": len(matched_cards),
                }
            else:
                result = {
                    "success": True,
                    "action": "mismatch",
                    "first_card": board[int(first_pick)],
                    "second_card": board[card_index],
                    "attempts_remaining": attempts_remaining,
                }
            if attempts_remaining <= 0 or len(matched) >= len(board):
                event.description = self._event_desc(event, 1)
                event.description_cn = self._event_desc(event, 1, cn=True)
                event.choices = [self._make_event_choice(description=self._event_opt(event, 1), description_cn=self._event_opt(event, 1, cn=True))]
                self._event_state()["stage"] = "complete"
                self.state.pending_card_choice = None
                self._record_current_event_choice(
                    event,
                    choice_index=int(pending.get("choice_index", 0)),
                    choice_text="Match and Keep complete",
                    matched_cards=matched_cards,
                )
                result["game_complete"] = True
                return result
            self.state.pending_card_choice = pending
            return result
        return {"success": False, "reason": "unknown_custom_action"}

    def _handle_big_fish_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        if str(state.get("stage", "intro")) == "result":
            self._finish_event()
            return {"success": True, "action": "left"}
        if choice_index == 0:
            heal_amt = max(1, self.state.player_max_hp // 3)
            healed = min(heal_amt, self.state.player_max_hp - self.state.player_hp)
            self.state.player_hp += healed
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, healed=healed)
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
        elif choice_index == 1:
            self.state.player_max_hp += 5
            self.state.player_hp += 5
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, max_hp_gained=5)
            event.description = self._event_desc(event, 2)
            event.description_cn = self._event_desc(event, 2, cn=True)
        elif choice_index == 2:
            relic_id = self._grant_random_relic(source=RelicSource.EVENT, record_pending=True)
            self.state.deck.append("Regret")
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, relic_id=relic_id, curse="Regret")
            event.description = self._event_desc(event, 4) + self._event_desc(event, 5)
            event.description_cn = self._event_desc(event, 4, cn=True) + self._event_desc(event, 5, cn=True)
        else:
            return {"success": False, "reason": "invalid_choice"}
        state["stage"] = "result"
        event.choices = [self._make_event_choice(description=self._event_opt(event, 5), description_cn=self._event_opt(event, 5, cn=True))]
        return {"success": True, "action": "resolved", "event_continues": True}

    def _handle_cleric_event(self, choice_index: int) -> dict[str, Any]:
        from sts_py.engine.run.events import _can_remove_card

        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        if choice_index == 0:
            heal_amt = int(self.state.player_max_hp * 0.25)
            healed = min(heal_amt, self.state.player_max_hp - self.state.player_hp)
            self.state.player_gold -= 35
            self.state.player_hp += healed
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, gold_paid=35, healed=healed)
            self._finish_event()
            return {"success": True, "action": "healed", "gold_paid": 35, "healed": healed}
        if choice_index == 1:
            purify_cost = 75 if self.state.ascension >= 15 else 50
            deck_indexes = [idx for idx, card_id in enumerate(self.state.deck) if _can_remove_card(self.state, card_id)]
            cards = [self.state.deck[idx] for idx in deck_indexes]
            self.state.player_gold -= purify_cost
            event.description = self._event_desc(event, 2)
            event.description_cn = self._event_desc(event, 2, cn=True)
            self.state.pending_card_choice = {
                "choice_index": choice_index,
                "effect_type": "choose_card_to_remove",
                "cards": cards,
                "deck_indexes": deck_indexes,
                "prompt": self._event_opt(event, 7),
                "prompt_cn": self._event_opt(event, 7, cn=True),
            }
            return {"success": True, "requires_card_choice": True, "choice_index": choice_index, "gold_paid": purify_cost}
        if choice_index == 2:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            self._finish_event()
            return {"success": True, "action": "left"}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_beggar_event(self, choice_index: int) -> dict[str, Any]:
        from sts_py.engine.run.events import _can_remove_card

        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        stage = str(state.get("stage", "intro"))
        if stage == "give_money":
            deck_indexes = [idx for idx, card_id in enumerate(self.state.deck) if _can_remove_card(self.state, card_id)]
            cards = [self.state.deck[idx] for idx in deck_indexes]
            event.description = self._event_desc(event, 3)
            event.description_cn = self._event_desc(event, 3, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 5), description_cn=self._event_opt(event, 5, cn=True))]
            self.state.pending_card_choice = {
                "choice_index": 0,
                "effect_type": "choose_card_to_remove",
                "cards": cards,
                "deck_indexes": deck_indexes,
                "prompt": self._event_opt(event, 6),
                "prompt_cn": self._event_opt(event, 6, cn=True),
            }
            state["stage"] = "leave"
            return {"success": True, "requires_card_choice": True, "choice_index": 0}
        if stage == "leave":
            self._finish_event()
            return {"success": True, "action": "left"}
        if choice_index == 0:
            self.state.player_gold -= 75
            event.description = self._event_desc(event, 2)
            event.description_cn = self._event_desc(event, 2, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 4), description_cn=self._event_opt(event, 4, cn=True))]
            state["stage"] = "give_money"
            return {"success": True, "action": "paid_gold", "gold_paid": 75, "event_continues": True}
        if choice_index == 1:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            self._finish_event()
            return {"success": True, "action": "left"}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_liars_game_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        stage = str(state.get("stage", "intro"))
        gold_reward = 150 if self.state.ascension >= 15 else 175
        if stage == "agree":
            self.state.deck.append("Doubt")
            self.state.player_gold += gold_reward
            self._pending_gold_reward += gold_reward
            self._record_current_event_choice(event, choice_index=0, choice_text=event.choices[0].description, gold_gained=gold_reward, curse="Doubt")
            event.description = self._event_desc(event, 3)
            event.description_cn = self._event_desc(event, 3, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 4), description_cn=self._event_opt(event, 4, cn=True))]
            state["stage"] = "complete"
            return {"success": True, "action": "accepted", "gold_gained": gold_reward, "event_continues": True}
        if stage == "complete":
            self._finish_event()
            return {"success": True, "action": "left"}
        if choice_index == 0:
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 3), description_cn=self._event_opt(event, 3, cn=True))]
            state["stage"] = "agree"
            return {"success": True, "action": "agree_prompt", "event_continues": True}
        if choice_index == 1:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            event.description = self._event_desc(event, 2)
            event.description_cn = self._event_desc(event, 2, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 4), description_cn=self._event_opt(event, 4, cn=True))]
            state["stage"] = "complete"
            return {"success": True, "action": "declined", "event_continues": True}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_cursed_tome_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        stage = str(state.get("stage", "intro"))
        final_damage = 15 if self.state.ascension >= 15 else 10
        if stage == "end":
            self._finish_event()
            return {"success": True, "action": "left"}
        if stage == "page_1":
            self.state.player_hp = max(0, self.state.player_hp - 1)
            event.description = self._event_desc(event, 2)
            event.description_cn = self._event_desc(event, 2, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True))]
            state["damage_taken"] = int(state.get("damage_taken", 0) or 0) + 1
            state["stage"] = "page_2"
            return {"success": True, "action": "continue", "event_continues": True}
        if stage == "page_2":
            self.state.player_hp = max(0, self.state.player_hp - 2)
            event.description = self._event_desc(event, 3)
            event.description_cn = self._event_desc(event, 3, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 3), description_cn=self._event_opt(event, 3, cn=True))]
            state["damage_taken"] = int(state.get("damage_taken", 0) or 0) + 2
            state["stage"] = "page_3"
            return {"success": True, "action": "continue", "event_continues": True}
        if stage == "page_3":
            self.state.player_hp = max(0, self.state.player_hp - 3)
            event.description = self._event_desc(event, 4)
            event.description_cn = self._event_desc(event, 4, cn=True)
            event.choices = [
                self._make_event_choice(
                    description=self._event_opt(event, 5) + str(final_damage) + self._event_opt(event, 6),
                    description_cn=self._event_opt(event, 5, cn=True) + str(final_damage) + self._event_opt(event, 6, cn=True),
                ),
                self._make_event_choice(description=self._event_opt(event, 4), description_cn=self._event_opt(event, 4, cn=True)),
            ]
            state["damage_taken"] = int(state.get("damage_taken", 0) or 0) + 3
            state["stage"] = "last_page"
            return {"success": True, "action": "continue", "event_continues": True}
        if stage == "last_page":
            if choice_index == 0:
                self.state.player_hp = max(0, self.state.player_hp - final_damage)
                book_pool = [relic_id for relic_id in ["Necronomicon", "Enchiridion", "NilrysCodex"] if not self._has_relic(relic_id)]
                if not book_pool:
                    book_pool = ["Circlet"]
                relic_id = str(self._event_random_choice(book_pool, rng=self._misc_rng()) or book_pool[0])
                self._acquire_relic(relic_id, source=RelicSource.EVENT, record_pending=True)
                state["damage_taken"] = int(state.get("damage_taken", 0) or 0) + final_damage
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, relic_id=relic_id, damage_taken=state["damage_taken"])
                event.description = self._event_desc(event, 5)
                event.description_cn = self._event_desc(event, 5, cn=True)
            elif choice_index == 1:
                self.state.player_hp = max(0, self.state.player_hp - 3)
                state["damage_taken"] = int(state.get("damage_taken", 0) or 0) + 3
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, damage_taken=state["damage_taken"])
                event.description = self._event_desc(event, 7)
                event.description_cn = self._event_desc(event, 7, cn=True)
            else:
                return {"success": False, "reason": "invalid_choice"}
            event.choices = [self._make_event_choice(description=self._event_opt(event, 7), description_cn=self._event_opt(event, 7, cn=True))]
            state["stage"] = "end"
            return {"success": True, "action": "resolved", "event_continues": True}
        if choice_index == 0:
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 1), description_cn=self._event_opt(event, 1, cn=True))]
            state["damage_taken"] = 0
            state["stage"] = "page_1"
            return {"success": True, "action": "read", "event_continues": True}
        if choice_index == 1:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            event.description = self._event_desc(event, 6)
            event.description_cn = self._event_desc(event, 6, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 7), description_cn=self._event_opt(event, 7, cn=True))]
            state["stage"] = "end"
            return {"success": True, "action": "left", "event_continues": True}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_forgotten_altar_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        if str(state.get("stage", "intro")) == "result":
            self._finish_event()
            return {"success": True, "action": "left"}
        if choice_index == 0:
            if self._has_relic("GoldenIdol"):
                if self._has_relic("BloodyIdol"):
                    relic_id = "Circlet"
                    self._acquire_relic(relic_id, source=RelicSource.EVENT, record_pending=True)
                else:
                    self.state.relics = [relic for relic in self.state.relics if self._canonical_relic_id(relic) != "GoldenIdol"]
                    relic_id = self._acquire_relic("BloodyIdol", source=RelicSource.EVENT, record_pending=True)
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, relic_id=relic_id)
            else:
                relic_id = self._acquire_relic("BloodyIdol" if not self._has_relic("BloodyIdol") else "Circlet", source=RelicSource.EVENT, record_pending=True)
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, relic_id=relic_id)
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
        elif choice_index == 1:
            hp_loss = max(1, round(self.state.player_max_hp * (0.35 if self.state.ascension >= 15 else 0.25)))
            self.state.player_max_hp += 5
            self.state.player_hp += 5
            self.state.player_hp = max(0, self.state.player_hp - hp_loss)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, hp_loss=hp_loss, max_hp_gained=5)
            event.description = self._event_desc(event, 2)
            event.description_cn = self._event_desc(event, 2, cn=True)
        elif choice_index == 2:
            self.state.deck.append("Decay")
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, curse="Decay")
            event.description = self._event_desc(event, 3)
            event.description_cn = self._event_desc(event, 3, cn=True)
        else:
            return {"success": False, "reason": "invalid_choice"}
        state["stage"] = "result"
        event.choices = [self._make_event_choice(description=self._event_opt(event, 6), description_cn=self._event_opt(event, 6, cn=True))]
        return {"success": True, "action": "resolved", "event_continues": True}

    def _handle_ghosts_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        if str(state.get("stage", "intro")) == "result":
            self._finish_event()
            return {"success": True, "action": "left"}
        if choice_index == 0:
            hp_loss = min(self.state.player_max_hp - 1, int((self.state.player_max_hp + 1) / 2))
            self.state.player_max_hp = max(1, self.state.player_max_hp - hp_loss)
            self.state.player_hp = min(self.state.player_hp, self.state.player_max_hp)
            amount = 3 if self.state.ascension >= 15 else 5
            self.state.deck.extend(["Apparition"] * amount)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, max_hp_lost=hp_loss, cards=["Apparition"] * amount)
            event.description = self._event_desc(event, 2)
            event.description_cn = self._event_desc(event, 2, cn=True)
        elif choice_index == 1:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            event.description = self._event_desc(event, 3)
            event.description_cn = self._event_desc(event, 3, cn=True)
        else:
            return {"success": False, "reason": "invalid_choice"}
        event.choices = [self._make_event_choice(description=self._event_opt(event, 5), description_cn=self._event_opt(event, 5, cn=True))]
        state["stage"] = "result"
        return {"success": True, "action": "resolved", "event_continues": True}

    def _handle_vampires_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        if str(state.get("stage", "intro")) == "result":
            self._finish_event()
            return {"success": True, "action": "left"}
        if choice_index == 0:
            max_hp_loss = min(self.state.player_max_hp - 1, int((self.state.player_max_hp * 0.3) + 0.999999))
            self.state.player_max_hp = max(1, self.state.player_max_hp - max_hp_loss)
            self.state.player_hp = min(self.state.player_hp, self.state.player_max_hp)
            self.state.deck = [card_id for card_id in self.state.deck if self._canonical_card_id(card_id) not in {"Strike", "Strike_B", "Strike_P"}]
            self.state.deck.extend(["Bite"] * 5)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, max_hp_lost=max_hp_loss, cards=["Bite"] * 5)
            event.description = self._event_desc(event, 2)
            event.description_cn = self._event_desc(event, 2, cn=True)
        elif choice_index == 1 and self._has_relic("BloodVial"):
            self.state.relics = [relic for relic in self.state.relics if self._canonical_relic_id(relic) != "BloodVial"]
            self.state.deck = [card_id for card_id in self.state.deck if self._canonical_card_id(card_id) not in {"Strike", "Strike_B", "Strike_P"}]
            self.state.deck.extend(["Bite"] * 5)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, lost_relic="BloodVial", cards=["Bite"] * 5)
            event.description = self._event_desc(event, 4)
            event.description_cn = self._event_desc(event, 4, cn=True)
        else:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            event.description = self._event_desc(event, 3)
            event.description_cn = self._event_desc(event, 3, cn=True)
        event.choices = [self._make_event_choice(description=self._event_opt(event, 5), description_cn=self._event_opt(event, 5, cn=True))]
        state["stage"] = "result"
        return {"success": True, "action": "resolved", "event_continues": True}

    def _handle_masked_bandits_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        stage = str(state.get("stage", "intro"))
        if stage == "paid_1":
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True))]
            state["stage"] = "paid_2"
            return {"success": True, "action": "continue", "event_continues": True}
        if stage == "paid_2":
            event.description = self._event_desc(event, 2)
            event.description_cn = self._event_desc(event, 2, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 3), description_cn=self._event_opt(event, 3, cn=True))]
            state["stage"] = "paid_3"
            return {"success": True, "action": "continue", "event_continues": True}
        if stage == "paid_3":
            event.description = self._event_desc(event, 3)
            event.description_cn = self._event_desc(event, 3, cn=True)
            self._finish_event()
            return {"success": True, "action": "left"}
        if choice_index == 0:
            gold_lost = int(self.state.player_gold)
            self.state.player_gold = 0
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, gold_lost=gold_lost)
            event.description = self._event_desc(event, 0)
            event.description_cn = self._event_desc(event, 0, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True))]
            state["stage"] = "paid_1"
            return {"success": True, "action": "paid_gold", "gold_lost": gold_lost, "event_continues": True}
        if choice_index == 1:
            relic_id = "Circlet" if self._has_relic("RedMask") else "RedMask"
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            self._clear_current_event()
            self._set_current_event_combat(
                enemies=["Pointy", "Romeo", "Bear"],
                pending_event_rewards=[f"gold_range:{25}:{35}", f"relic_id:{relic_id}"],
                is_elite_combat=False,
            )
            self.start_combat_with_monsters(["Pointy", "Romeo", "Bear"])
            return {"success": True, "action": "combat", "is_event_combat": True, "pending_relic": relic_id}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_nest_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        stage = str(state.get("stage", "intro"))
        if stage == "result":
            self._finish_event()
            return {"success": True, "action": "left"}
        if stage == "choice":
            if choice_index == 0:
                gold_gain = 50 if self.state.ascension >= 15 else 99
                self.state.player_gold += gold_gain
                self._pending_gold_reward += gold_gain
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, gold_gained=gold_gain)
                event.description = self._event_desc(event, 3)
                event.description_cn = self._event_desc(event, 3, cn=True)
            elif choice_index == 1:
                self.state.player_hp = max(0, self.state.player_hp - 6)
                self.state.deck.append("RitualDagger")
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, hp_loss=6, card_id="RitualDagger")
                event.description = self._event_desc(event, 2)
                event.description_cn = self._event_desc(event, 2, cn=True)
            else:
                return {"success": False, "reason": "invalid_choice"}
            event.choices = [self._make_event_choice(description=self._event_opt(event, 4), description_cn=self._event_opt(event, 4, cn=True))]
            state["stage"] = "result"
            return {"success": True, "action": "resolved", "event_continues": True}
        event_state = self._event_state()
        event_state["stage"] = "choice"
        self._configure_nest_event(event)
        return {"success": True, "action": "prompt_choice", "event_continues": True}

    def _handle_library_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        if str(state.get("stage", "intro")) == "result":
            self._finish_event()
            return {"success": True, "action": "left"}
        if choice_index == 0:
            from sts_py.engine.content.cards_min import ALL_CARD_DEFS

            offered_cards = self._draw_unique_character_event_cards(20)
            lore_descriptions = [self._event_desc(event, 2), self._event_desc(event, 3), self._event_desc(event, 4)]
            event.description = str(self._event_random_choice(lore_descriptions) or lore_descriptions[0])
            event.description_cn = ""
            event.choices = [self._make_event_choice(description=self._event_opt(event, 3), description_cn=self._event_opt(event, 3, cn=True))]
            state["stage"] = "result"
            return self._set_pending_event_card_choice(
                choice_index=0,
                custom_action="library_take_card",
                cards=[f"{ALL_CARD_DEFS.get(card_id).name_cn or card_id}" if ALL_CARD_DEFS.get(card_id) is not None else card_id for card_id in offered_cards],
                prompt=self._event_opt(event, 4),
                prompt_cn=self._event_opt(event, 4, cn=True),
                extra={"offered_cards": offered_cards},
            )
        if choice_index == 1:
            heal_amt = round(self.state.player_max_hp * (0.2 if self.state.ascension >= 15 else 0.33))
            healed = min(heal_amt, self.state.player_max_hp - self.state.player_hp)
            self.state.player_hp += healed
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, healed=healed)
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 3), description_cn=self._event_opt(event, 3, cn=True))]
            state["stage"] = "result"
            return {"success": True, "action": "slept", "healed": healed, "event_continues": True}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_mausoleum_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        if str(state.get("stage", "intro")) == "result":
            self._finish_event()
            return {"success": True, "action": "left"}
        if choice_index == 0:
            cursed = True if self.state.ascension >= 15 else bool(self._misc_rng().random_boolean() if self._misc_rng() is not None else False)
            relic_id = self._grant_random_relic(source=RelicSource.EVENT, record_pending=True)
            if cursed:
                self.state.deck.append("Writhe")
                event.description = self._event_desc(event, 1)
                event.description_cn = self._event_desc(event, 1, cn=True)
            else:
                event.description = self._event_desc(event, 2)
                event.description_cn = self._event_desc(event, 2, cn=True)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, relic_id=relic_id, cursed=cursed)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True))]
            state["stage"] = "result"
            return {"success": True, "action": "opened", "relic_id": relic_id, "cursed": cursed, "event_continues": True}
        if choice_index == 1:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            event.description = self._event_desc(event, 3)
            event.description_cn = self._event_desc(event, 3, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True))]
            state["stage"] = "result"
            return {"success": True, "action": "left", "event_continues": True}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_colosseum_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        stage = str(state.get("stage", "intro"))
        if stage == "post_slavers":
            if choice_index == 0:
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
                self._clear_current_event()
                self._set_current_event_combat(
                    enemies=["Taskmaster", "GremlinNob"],
                    pending_event_rewards=["gold:100", "relic_tier:RARE", "relic_tier:UNCOMMON"],
                    is_elite_combat=False,
                )
                self.start_combat_with_monsters(["Taskmaster", "GremlinNob"])
                return {"success": True, "action": "combat", "is_event_combat": True}
            if choice_index == 1:
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
                self._finish_event()
                return {"success": True, "action": "escaped"}
            return {"success": False, "reason": "invalid_choice"}
        if stage == "fight":
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            self._clear_current_event()
            self._set_current_event_combat(
                enemies=["SlaverBlue", "SlaverRed"],
                pending_event_rewards=[],
                is_elite_combat=False,
                reopen_event={"event_key": "Colosseum", "event_state": {"stage": "post_slavers"}},
            )
            self.start_combat_with_monsters(["SlaverBlue", "SlaverRed"])
            return {"success": True, "action": "combat", "is_event_combat": True}
        state["stage"] = "fight"
        self._configure_colosseum_event(event)
        return {"success": True, "action": "wake_up", "event_continues": True}

    def _handle_fountain_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        if str(state.get("stage", "intro")) == "result":
            self._finish_event()
            return {"success": True, "action": "left"}
        if choice_index == 0:
            from sts_py.engine.run.events import _can_remove_card, _is_curse_card

            removed: list[str] = []
            remaining: list[str] = []
            for card_id in self.state.deck:
                if _is_curse_card(card_id) and _can_remove_card(self.state, card_id):
                    removed.append(card_id)
                else:
                    remaining.append(card_id)
            self.state.deck = remaining
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, removed_cards=removed)
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
        elif choice_index == 1:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            event.description = self._event_desc(event, 2)
            event.description_cn = self._event_desc(event, 2, cn=True)
        else:
            return {"success": False, "reason": "invalid_choice"}
        event.choices = [self._make_event_choice(description=self._event_opt(event, 1), description_cn=self._event_opt(event, 1, cn=True))]
        state["stage"] = "result"
        return {"success": True, "action": "resolved", "event_continues": True}

    def _handle_knowing_skull_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        stage = str(state.get("stage", "intro"))
        costs = state.setdefault("costs", {"potion": 6, "gold": 6, "card": 6, "leave": 6})
        if stage == "complete":
            self._finish_event()
            return {"success": True, "action": "left"}
        if stage != "ask":
            state["stage"] = "ask"
            self._configure_knowing_skull_event(event)
            return {"success": True, "action": "question_prompt", "event_continues": True}
        if choice_index == 0:
            cost = int(costs["potion"])
            self.state.player_hp = max(0, self.state.player_hp - cost)
            costs["potion"] += 1
            potion_id = None
            if not self._has_relic("Sozu"):
                from sts_py.engine.combat.potion_effects import get_random_potion_by_rarity, roll_potion_rarity

                rarity = roll_potion_rarity()
                potion = get_random_potion_by_rarity(rarity, self.state.character_class)
                if potion and self.gain_potion(potion.potion_id):
                    potion_id = potion.potion_id
                    self._pending_potion_reward = potion_id
            event.description = self._event_desc(event, 4) + self._event_desc(event, 2)
            event.description_cn = self._event_desc(event, 4, cn=True) + self._event_desc(event, 2, cn=True)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, hp_loss=cost, potion_id=potion_id)
            self._configure_knowing_skull_event(event)
            return {"success": True, "action": "gain_potion", "hp_loss": cost, "potion_id": potion_id, "event_continues": True}
        if choice_index == 1:
            cost = int(costs["gold"])
            self.state.player_hp = max(0, self.state.player_hp - cost)
            self.state.player_gold += 90
            self._pending_gold_reward += 90
            costs["gold"] += 1
            event.description = self._event_desc(event, 6) + self._event_desc(event, 2)
            event.description_cn = self._event_desc(event, 6, cn=True) + self._event_desc(event, 2, cn=True)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, hp_loss=cost, gold_gained=90)
            self._configure_knowing_skull_event(event)
            return {"success": True, "action": "gain_gold", "hp_loss": cost, "gold_gained": 90, "event_continues": True}
        if choice_index == 2:
            cost = int(costs["card"])
            self.state.player_hp = max(0, self.state.player_hp - cost)
            costs["card"] += 1
            gained = self._draw_unique_colorless_event_cards(1, allowed_rarities={"UNCOMMON"})
            card_id = gained[0] if gained else None
            if card_id:
                self.state.deck.append(card_id)
            event.description = self._event_desc(event, 5) + self._event_desc(event, 2)
            event.description_cn = self._event_desc(event, 5, cn=True) + self._event_desc(event, 2, cn=True)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, hp_loss=cost, card_id=card_id)
            self._configure_knowing_skull_event(event)
            return {"success": True, "action": "gain_card", "hp_loss": cost, "card_id": card_id, "event_continues": True}
        if choice_index == 3:
            cost = int(costs["leave"])
            self.state.player_hp = max(0, self.state.player_hp - cost)
            event.description = self._event_desc(event, 7)
            event.description_cn = self._event_desc(event, 7, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 8), description_cn=self._event_opt(event, 8, cn=True))]
            state["stage"] = "complete"
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, hp_loss=cost)
            return {"success": True, "action": "leave_prompt", "hp_loss": cost, "event_continues": True}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_accursed_blacksmith_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        if str(state.get("stage", "intro")) == "result":
            self._finish_event()
            return {"success": True, "action": "left"}
        if choice_index == 0:
            deck_indexes = [idx for idx, card_id in enumerate(self.state.deck) if self._upgrade_card(card_id) is not None]
            cards = [self.state.deck[idx] for idx in deck_indexes]
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True))]
            state["stage"] = "result"
            self.state.pending_card_choice = {
                "choice_index": 0,
                "effect_type": "choose_card_to_upgrade",
                "cards": cards,
                "deck_indexes": deck_indexes,
                "prompt": self._event_opt(event, 3),
                "prompt_cn": self._event_opt(event, 3, cn=True),
            }
            return {"success": True, "requires_card_choice": True, "choice_index": 0}
        if choice_index == 1:
            relic_id = "Circlet" if self._has_relic("WarpedTongs") else "WarpedTongs"
            self.state.deck.append("Pain")
            self._acquire_relic(relic_id, source=RelicSource.EVENT, record_pending=True)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, relic_id=relic_id, curse="Pain")
            event.description = self._event_desc(event, 2) + self._event_desc(event, 4)
            event.description_cn = self._event_desc(event, 2, cn=True) + self._event_desc(event, 4, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True))]
            state["stage"] = "result"
            return {"success": True, "action": "rummaged", "relic_id": relic_id, "event_continues": True}
        if choice_index == 2:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            event.description = self._event_desc(event, 5)
            event.description_cn = self._event_desc(event, 5, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True))]
            state["stage"] = "result"
            return {"success": True, "action": "left", "event_continues": True}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_match_and_keep_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        stage = str(state.get("stage", "intro"))
        if stage == "complete":
            self._finish_event()
            return {"success": True, "action": "left"}
        if stage == "rules":
            from sts_py.engine.content.cards_min import ALL_CURSE_DEFS, CardRarity
            from sts_py.engine.rewards.card_rewards_min import character_pools

            pools = character_pools(self.state.character_class)
            rare_pool = [card.id for card in pools.get(CardRarity.RARE, [])]
            uncommon_pool = [card.id for card in pools.get(CardRarity.UNCOMMON, [])]
            common_pool = [card.id for card in pools.get(CardRarity.COMMON, [])]
            start_card = {"IRONCLAD": "Bash", "SILENT": "Neutralize", "DEFECT": "Zap", "WATCHER": "Eruption"}.get(self.state.character_class, "Bash")
            unique_cards: list[str] = [
                str(self._event_random_choice(rare_pool, rng=self._misc_rng()) or rare_pool[0]),
                str(self._event_random_choice(uncommon_pool, rng=self._misc_rng()) or uncommon_pool[0]),
                str(self._event_random_choice(common_pool, rng=self._misc_rng()) or common_pool[0]),
            ]
            curse_pool = [card_id for card_id in ALL_CURSE_DEFS if card_id not in {"AscendersBane", "CurseOfTheBell", "Necronomicurse"}]
            if self.state.ascension >= 15:
                first_curse = str(self._event_random_choice(curse_pool, rng=self._misc_rng()) or curse_pool[0])
                second_pool = [card_id for card_id in curse_pool if card_id != first_curse] or curse_pool
                unique_cards.extend([first_curse, str(self._event_random_choice(second_pool, rng=self._misc_rng()) or second_pool[0])])
            else:
                colorless = self._draw_unique_colorless_event_cards(1, allowed_rarities={"UNCOMMON"})
                unique_cards.append(colorless[0] if colorless else "Madness")
                unique_cards.append(str(self._event_random_choice(curse_pool, rng=self._misc_rng()) or curse_pool[0]))
            unique_cards = unique_cards[:5]
            unique_cards.append(start_card)
            board = unique_cards + list(unique_cards)
            rng = self._misc_rng()
            if rng is not None:
                for idx in range(len(board) - 1, 0, -1):
                    swap_idx = rng.random_int(idx)
                    board[idx], board[swap_idx] = board[swap_idx], board[idx]
            state["stage"] = "play"
            return self._set_pending_event_card_choice(
                choice_index=0,
                custom_action="match_and_keep_pick",
                cards=[f"Card {idx}" for idx in range(len(board))],
                prompt=self._event_opt(event, 3) + str(5),
                prompt_cn=self._event_opt(event, 3, cn=True) + str(5),
                extra={"board": board, "matched": [], "matched_cards": [], "attempts_remaining": 5, "first_pick": None},
            )
        if stage == "play":
            return {"success": False, "reason": "pending_card_choice_required"}
        state["stage"] = "rules"
        self._configure_match_and_keep_event(event)
        return {"success": True, "action": "rules", "event_continues": True}

    def _handle_note_for_yourself_event(self, choice_index: int) -> dict[str, Any]:
        from sts_py.engine.content.card_instance import format_runtime_card_id
        from sts_py.engine.run.events import _can_remove_card

        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        payload = self._normalize_note_for_yourself_payload(self.state.note_for_yourself_payload)
        stored_card = format_runtime_card_id(payload["card_id"], times_upgraded=int(payload["upgrades"]))
        stage = str(state.get("stage", "intro"))
        if stage == "complete":
            self._finish_event()
            return {"success": True, "action": "left"}
        if stage == "choose":
            if choice_index == 0:
                self.state.deck.append(stored_card)
                deck_indexes = [idx for idx, card_id in enumerate(self.state.deck) if _can_remove_card(self.state, card_id)]
                cards = [self.state.deck[idx] for idx in deck_indexes]
                event.description = self._event_desc(event, 3)
                event.description_cn = self._event_desc(event, 3, cn=True)
                event.choices = [self._make_event_choice(description=self._event_opt(event, 4), description_cn=self._event_opt(event, 4, cn=True))]
                state["stage"] = "complete"
                return self._set_pending_event_card_choice(
                    choice_index=0,
                    custom_action="note_for_yourself_store",
                    cards=cards,
                    deck_indexes=deck_indexes,
                    prompt=self._event_desc(event, 2),
                    prompt_cn=self._event_desc(event, 2, cn=True),
                    extra={"stored_card": stored_card},
                )
            if choice_index == 1:
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
                event.description = self._event_desc(event, 3)
                event.description_cn = self._event_desc(event, 3, cn=True)
                event.choices = [self._make_event_choice(description=self._event_opt(event, 4), description_cn=self._event_opt(event, 4, cn=True))]
                state["stage"] = "complete"
                return {"success": True, "action": "ignored", "event_continues": True}
            return {"success": False, "reason": "invalid_choice"}
        state["stage"] = "choose"
        self._configure_note_for_yourself_event(event)
        return {"success": True, "action": "read_note", "event_continues": True}

    def _handle_moai_head_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        if str(state.get("stage", "intro")) == "result":
            self._finish_event()
            return {"success": True, "action": "left"}
        if choice_index == 0:
            hp_amt = max(1, round(self.state.player_max_hp * (0.18 if self.state.ascension >= 15 else 0.125)))
            self.state.player_max_hp = max(1, self.state.player_max_hp - hp_amt)
            self.state.player_hp = self.state.player_max_hp
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, max_hp_lost=hp_amt, healed=self.state.player_hp)
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
        elif choice_index == 1:
            if not self._has_relic("GoldenIdol"):
                return {"success": False, "reason": "choice_disabled"}
            self.state.relics = [relic for relic in self.state.relics if self._canonical_relic_id(relic) != "GoldenIdol"]
            self.state.player_gold += 333
            self._pending_gold_reward += 333
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, gold_gained=333, lost_relic="GoldenIdol")
            event.description = self._event_desc(event, 2)
            event.description_cn = self._event_desc(event, 2, cn=True)
        elif choice_index == 2:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            event.description = self._event_desc(event, 3)
            event.description_cn = self._event_desc(event, 3, cn=True)
        else:
            return {"success": False, "reason": "invalid_choice"}
        event.choices = [self._make_event_choice(description=self._event_opt(event, 4), description_cn=self._event_opt(event, 4, cn=True))]
        state["stage"] = "result"
        return {"success": True, "action": "resolved", "event_continues": True}

    def _handle_sensory_stone_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        stage = str(state.get("stage", "intro"))
        if stage == "complete":
            self._finish_event()
            return {"success": True, "action": "left"}
        if stage == "choice":
            reward_count = choice_index + 1
            hp_loss = 5 if choice_index == 1 else 10 if choice_index == 2 else 0
            gained_cards = self._draw_unique_colorless_event_cards(reward_count)
            self.state.deck.extend(gained_cards)
            if hp_loss:
                self.state.player_hp = max(0, self.state.player_hp - hp_loss)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, cards=gained_cards, hp_loss=hp_loss)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 4), description_cn=self._event_opt(event, 4, cn=True))]
            state["stage"] = "complete"
            return {"success": True, "action": "recalled", "cards": gained_cards, "hp_loss": hp_loss, "event_continues": True}
        memories_en = [self._event_desc(event, idx) for idx in range(2, 6)]
        memories_cn = [self._event_desc(event, idx, cn=True) for idx in range(2, 6)]
        pick_idx = self._misc_rng().random_int(len(memories_en) - 1) if self._misc_rng() is not None else 0
        state["memory_description"] = memories_en[pick_idx]
        state["memory_description_cn"] = memories_cn[pick_idx]
        state["stage"] = "choice"
        self._configure_sensory_stone_event(event)
        return {"success": True, "action": "memory_revealed", "event_continues": True}

    def _handle_tomb_red_mask_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        has_mask = self._has_relic("RedMask")
        if str(state.get("stage", "intro")) == "result":
            self._finish_event()
            return {"success": True, "action": "left"}
        if has_mask and choice_index == 0:
            self.state.player_gold += 222
            self._pending_gold_reward += 222
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, gold_gained=222)
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
        elif (not has_mask) and choice_index == 1:
            gold_paid = int(self.state.player_gold)
            self.state.player_gold = 0
            relic_id = self._acquire_relic("RedMask", source=RelicSource.EVENT, record_pending=True)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, gold_paid=gold_paid, relic_id=relic_id)
            event.description = self._event_desc(event, 2)
            event.description_cn = self._event_desc(event, 2, cn=True)
        else:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            self._finish_event()
            return {"success": True, "action": "left"}
        event.choices = [self._make_event_choice(description=self._event_opt(event, 4), description_cn=self._event_opt(event, 4, cn=True))]
        state["stage"] = "result"
        return {"success": True, "action": "resolved", "event_continues": True}

    def _handle_wheel_of_change_event(self, choice_index: int) -> dict[str, Any]:
        from sts_py.engine.run.events import _can_remove_card

        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        stage = str(state.get("stage", "intro"))
        if stage == "leave":
            self._finish_event()
            return {"success": True, "action": "left"}
        if stage == "resolve":
            result = int(state.get("wheel_result", 0) or 0)
            if result == 0:
                gold_amount = {1: 100, 2: 200, 3: 300}.get(self.state.act, 300)
                self.state.player_gold += gold_amount
                self._pending_gold_reward += gold_amount
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, gold_gained=gold_amount)
            elif result == 1:
                relic_id = self._grant_random_relic(source=RelicSource.EVENT, record_pending=True)
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, relic_id=relic_id)
            elif result == 2:
                healed = self.state.player_max_hp - self.state.player_hp
                self.state.player_hp = self.state.player_max_hp
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, healed=healed)
            elif result == 3:
                self.state.deck.append("Decay")
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, curse="Decay")
            elif result == 4:
                deck_indexes = [idx for idx, card_id in enumerate(self.state.deck) if _can_remove_card(self.state, card_id)]
                cards = [self.state.deck[idx] for idx in deck_indexes]
                if not cards:
                    event.choices = [self._make_event_choice(description=self._event_opt(event, 8), description_cn=self._event_opt(event, 8, cn=True))]
                    state["stage"] = "leave"
                    return {"success": True, "action": "no_card_to_remove", "event_continues": True}
                event.choices = [self._make_event_choice(description=self._event_opt(event, 8), description_cn=self._event_opt(event, 8, cn=True))]
                state["stage"] = "leave"
                self.state.pending_card_choice = {
                    "choice_index": 0,
                    "effect_type": "choose_card_to_remove",
                    "cards": cards,
                    "deck_indexes": deck_indexes,
                    "prompt": self._event_opt(event, 9),
                    "prompt_cn": self._event_opt(event, 9, cn=True),
                }
                return {"success": True, "requires_card_choice": True, "choice_index": 0}
            else:
                hp_loss = int(self.state.player_max_hp * (0.15 if self.state.ascension >= 15 else 0.10))
                self.state.player_hp = max(0, self.state.player_hp - hp_loss)
                event.description = self._event_desc(event, 7)
                event.description_cn = self._event_desc(event, 7, cn=True)
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, hp_loss=hp_loss)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 8), description_cn=self._event_opt(event, 8, cn=True))]
            state["stage"] = "leave"
            return {"success": True, "action": "resolved", "event_continues": True}
        wheel_result = self._misc_rng().random_int(5) if self._misc_rng() is not None else 0
        state["wheel_result"] = wheel_result
        descriptions = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6}
        event.description = self._event_desc(event, descriptions[wheel_result])
        event.description_cn = self._event_desc(event, descriptions[wheel_result], cn=True)
        if wheel_result == 5:
            hp_loss = int(self.state.player_max_hp * (0.15 if self.state.ascension >= 15 else 0.10))
            option_desc = self._event_opt(event, 6) + str(hp_loss) + self._event_opt(event, 7)
            option_desc_cn = self._event_opt(event, 6, cn=True) + str(hp_loss) + self._event_opt(event, 7, cn=True)
        else:
            option_idx = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5}[wheel_result]
            option_desc = self._event_opt(event, option_idx)
            option_desc_cn = self._event_opt(event, option_idx, cn=True)
        event.choices = [self._make_event_choice(description=option_desc, description_cn=option_desc_cn)]
        state["stage"] = "resolve"
        return {"success": True, "action": "spin", "result": wheel_result, "event_continues": True}

    def _handle_winding_halls_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        stage = str(state.get("stage", "intro"))
        if stage == "result":
            self._finish_event()
            return {"success": True, "action": "left"}
        if stage == "choice":
            if choice_index == 0:
                hp_amt = max(1, round(self.state.player_max_hp * (0.18 if self.state.ascension >= 15 else 0.125)))
                self.state.player_hp = max(0, self.state.player_hp - hp_amt)
                self.state.deck.extend(["Madness", "Madness"])
                event.description = self._event_desc(event, 2)
                event.description_cn = self._event_desc(event, 2, cn=True)
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, hp_loss=hp_amt, cards=["Madness", "Madness"])
            elif choice_index == 1:
                heal_amt = max(1, round(self.state.player_max_hp * (0.2 if self.state.ascension >= 15 else 0.25)))
                healed = min(heal_amt, self.state.player_max_hp - self.state.player_hp)
                self.state.player_hp += healed
                self.state.deck.append("Writhe")
                event.description = self._event_desc(event, 3)
                event.description_cn = self._event_desc(event, 3, cn=True)
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, healed=healed, curse="Writhe")
            elif choice_index == 2:
                max_hp_amt = max(1, round(self.state.player_max_hp * 0.05))
                self.state.player_max_hp = max(1, self.state.player_max_hp - max_hp_amt)
                self.state.player_hp = min(self.state.player_hp, self.state.player_max_hp)
                event.description = self._event_desc(event, 4)
                event.description_cn = self._event_desc(event, 4, cn=True)
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, max_hp_lost=max_hp_amt)
            else:
                return {"success": False, "reason": "invalid_choice"}
            event.choices = [self._make_event_choice(description=self._event_opt(event, 4), description_cn=self._event_opt(event, 4, cn=True))]
            state["stage"] = "result"
            return {"success": True, "action": "resolved", "event_continues": True}
        state["stage"] = "choice"
        self._configure_winding_halls_event(event)
        return {"success": True, "action": "revealed", "event_continues": True}

    def _handle_spire_heart_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        meta = dict(self.state.spire_heart_meta or {})
        stage = str(meta.get("stage", "intro"))
        damage_dealt = int(meta.get("damage_dealt", 0) or 0)
        total_damage = int(meta.get("total_damage_dealt", damage_dealt) or damage_dealt)
        if stage == "death":
            self._clear_current_event()
            self.state.phase = RunPhase.GAME_OVER
            return {"success": True, "action": "game_over"}
        if stage == "door":
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, enter_act4=True)
            self._clear_current_event()
            self._enter_act4()
            return {"success": True, "action": "enter_act4"}
        if stage == "middle_2":
            if self.has_all_act4_keys():
                event.description = self._event_desc(event, 11) + self._event_desc(event, 12) + self._event_desc(event, 13) + self._event_desc(event, 14)
                event.description_cn = self._event_desc(event, 11, cn=True) + self._event_desc(event, 12, cn=True) + self._event_desc(event, 13, cn=True) + self._event_desc(event, 14, cn=True)
                event.choices = [self._make_event_choice(description=self._event_opt(event, 3), description_cn=self._event_opt(event, 3, cn=True))]
                meta["stage"] = "door"
            else:
                event.description = self._event_desc(event, 3) + str(total_damage) + self._event_desc(event, 4) + self._event_desc(event, 7)
                event.description_cn = self._event_desc(event, 3, cn=True) + str(total_damage) + self._event_desc(event, 4, cn=True) + self._event_desc(event, 7, cn=True)
                event.choices = [self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True))]
                meta["stage"] = "death"
            self.state.spire_heart_meta = meta
            return {"success": True, "action": "heart_outcome", "event_continues": True}
        if stage == "middle":
            event.description = self._event_desc(event, 1) + str(damage_dealt) + self._event_desc(event, 2)
            event.description_cn = self._event_desc(event, 1, cn=True) + str(damage_dealt) + self._event_desc(event, 2, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 0), description_cn=self._event_opt(event, 0, cn=True))]
            meta["stage"] = "middle_2"
            self.state.spire_heart_meta = meta
            return {"success": True, "action": "attack_heart", "event_continues": True}
        character_desc_idx = {"IRONCLAD": 8, "SILENT": 9, "DEFECT": 10, "WATCHER": 15}.get(self.state.character_class, 8)
        event.description = self._event_desc(event, character_desc_idx)
        event.description_cn = self._event_desc(event, character_desc_idx, cn=True)
        event.choices = [self._make_event_choice(description=self._event_opt(event, 1), description_cn=self._event_opt(event, 1, cn=True))]
        meta["stage"] = "middle"
        self.state.spire_heart_meta = meta
        return {"success": True, "action": "approach_heart", "event_continues": True}

    def _handle_addict_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        if choice_index == 0:
            relic_id = self._grant_random_relic(source=RelicSource.EVENT, record_pending=True)
            self.state.player_gold -= 85
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, relic_id=relic_id, gold_paid=85)
            self._finish_event()
            return {"success": True, "action": "paid_gold", "relic_id": relic_id}
        if choice_index == 1:
            relic_id = self._grant_random_relic(source=RelicSource.EVENT, record_pending=True)
            self.state.deck.append("Shame")
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, relic_id=relic_id, curse="Shame")
            self._finish_event()
            return {"success": True, "action": "robbed", "relic_id": relic_id, "curse": "Shame"}
        if choice_index == 2:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            self._finish_event()
            return {"success": True, "action": "left"}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_back_to_basics_event(self, choice_index: int) -> dict[str, Any]:
        from sts_py.engine.run.events import _can_remove_card

        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        if choice_index == 0:
            deck_indexes = [idx for idx, card_id in enumerate(self.state.deck) if _can_remove_card(self.state, card_id)]
            cards = [self.state.deck[idx] for idx in deck_indexes]
            if not cards:
                self._finish_event()
                return {"success": True, "action": "no_purgeable_cards"}
            self.state.pending_card_choice = {
                "choice_index": choice_index,
                "effect_type": "choose_card_to_remove",
                "cards": cards,
                "deck_indexes": deck_indexes,
                "prompt": self._event_opt(event, 2),
                "prompt_cn": self._event_opt(event, 2, cn=True),
            }
            return {"success": True, "requires_card_choice": True, "choice_index": choice_index}
        if choice_index == 1:
            upgraded: list[str] = []
            for idx, card_id in enumerate(list(self.state.deck)):
                base = self._canonical_card_id(card_id)
                if base not in {"Strike", "Defend", "Strike_B", "Defend_B", "Strike_P", "Defend_P"}:
                    continue
                upgraded_card = self._upgrade_card(card_id)
                if upgraded_card and upgraded_card != card_id:
                    self.state.deck[idx] = upgraded_card
                    upgraded.append(base)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, upgraded_cards=upgraded)
            self._finish_event()
            return {"success": True, "action": "upgraded_starters", "upgraded_cards": upgraded}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_drug_dealer_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        if choice_index == 0:
            self.state.deck.append("JAX")
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, card_id="JAX")
            self._finish_event()
            return {"success": True, "action": "obtained_jax", "card_id": "JAX"}
        if choice_index == 1:
            deck_indexes = [idx for idx, card_id in enumerate(self.state.deck) if self._canonical_card_id(card_id) not in {"AscendersBane", "CurseOfTheBell", "Necronomicurse"}]
            cards = [self.state.deck[idx] for idx in deck_indexes]
            return self._set_pending_event_card_choice(
                choice_index=choice_index,
                custom_action="drug_dealer_transform",
                cards=cards,
                deck_indexes=deck_indexes,
                prompt=self._event_opt(event, 5),
                prompt_cn=self._event_opt(event, 5, cn=True),
                extra={"selected": []},
            )
        if choice_index == 2:
            relic_id = "Circlet" if self._has_relic("MutagenicStrength") else "MutagenicStrength"
            self._acquire_relic(relic_id, source=RelicSource.EVENT, record_pending=True)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, relic_id=relic_id)
            self._finish_event()
            return {"success": True, "action": "obtained_relic", "relic_id": relic_id}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_designer_event(self, choice_index: int) -> dict[str, Any]:
        from sts_py.engine.run.events import _can_remove_card

        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = dict(self._event_state().get("designer") or {})
        stage = str(state.get("stage", "intro"))
        if stage == "intro":
            state["stage"] = "main"
            self._event_state()["designer"] = state
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
            adjustment_upgrades_one = bool(state.get("adjustment_upgrades_one", True))
            clean_up_removes_cards = bool(state.get("clean_up_removes_cards", True))
            adjust_cost = int(state.get("adjust_cost", 40))
            clean_up_cost = int(state.get("clean_up_cost", 60))
            full_service_cost = int(state.get("full_service_cost", 90))
            hp_loss = int(state.get("hp_loss", 3))
            has_upgrades = any(self._upgrade_card(card_id) is not None for card_id in self.state.deck)
            removable_indexes = [idx for idx, card_id in enumerate(self.state.deck) if _can_remove_card(self.state, card_id)]
            event.choices = [
                self._make_event_choice(
                    description=self._event_opt(event, 1) + str(adjust_cost) + self._event_opt(event, 6) + (self._event_opt(event, 9) if adjustment_upgrades_one else self._event_opt(event, 7) + "2" + self._event_opt(event, 8)),
                    description_cn=self._event_opt(event, 1, cn=True) + str(adjust_cost) + self._event_opt(event, 6, cn=True) + (self._event_opt(event, 9, cn=True) if adjustment_upgrades_one else self._event_opt(event, 7, cn=True) + "2" + self._event_opt(event, 8, cn=True)),
                    enabled=self.state.player_gold >= adjust_cost and has_upgrades,
                ),
                self._make_event_choice(
                    description=self._event_opt(event, 2) + str(clean_up_cost) + self._event_opt(event, 6) + (self._event_opt(event, 10) if clean_up_removes_cards else self._event_opt(event, 11) + "2" + self._event_opt(event, 12)),
                    description_cn=self._event_opt(event, 2, cn=True) + str(clean_up_cost) + self._event_opt(event, 6, cn=True) + (self._event_opt(event, 10, cn=True) if clean_up_removes_cards else self._event_opt(event, 11, cn=True) + "2" + self._event_opt(event, 12, cn=True)),
                    enabled=self.state.player_gold >= clean_up_cost and len(removable_indexes) >= (1 if clean_up_removes_cards else 2),
                ),
                self._make_event_choice(
                    description=self._event_opt(event, 3) + str(full_service_cost) + self._event_opt(event, 6) + self._event_opt(event, 13),
                    description_cn=self._event_opt(event, 3, cn=True) + str(full_service_cost) + self._event_opt(event, 6, cn=True) + self._event_opt(event, 13, cn=True),
                    enabled=self.state.player_gold >= full_service_cost and len(removable_indexes) >= 1,
                ),
                self._make_event_choice(
                    description=self._event_opt(event, 4) + str(hp_loss) + self._event_opt(event, 5),
                    description_cn=self._event_opt(event, 4, cn=True) + str(hp_loss) + self._event_opt(event, 5, cn=True),
                ),
            ]
            return {"success": True, "action": "main_menu", "event_continues": True}

        adjustment_upgrades_one = bool(state.get("adjustment_upgrades_one", True))
        clean_up_removes_cards = bool(state.get("clean_up_removes_cards", True))
        adjust_cost = int(state.get("adjust_cost", 40))
        clean_up_cost = int(state.get("clean_up_cost", 60))
        full_service_cost = int(state.get("full_service_cost", 90))
        hp_loss = int(state.get("hp_loss", 3))

        if choice_index == 0:
            self.state.player_gold -= adjust_cost
            if adjustment_upgrades_one:
                deck_indexes = [idx for idx, card_id in enumerate(self.state.deck) if self._upgrade_card(card_id) is not None]
                cards = [self.state.deck[idx] for idx in deck_indexes]
                self.state.pending_card_choice = {
                    "choice_index": choice_index,
                    "effect_type": "choose_card_to_upgrade",
                    "cards": cards,
                    "deck_indexes": deck_indexes,
                    "prompt": self._event_opt(event, 15),
                    "prompt_cn": self._event_opt(event, 15, cn=True),
                }
                return {"success": True, "requires_card_choice": True, "choice_index": choice_index}
            upgraded_cards: list[str] = []
            candidates = [idx for idx, card_id in enumerate(self.state.deck) if self._upgrade_card(card_id) is not None]
            rng = self._misc_rng()
            while candidates and len(upgraded_cards) < 2:
                pick = rng.random_int(len(candidates) - 1) if rng is not None else 0
                deck_index = candidates.pop(pick)
                old_card = self.state.deck[deck_index]
                upgraded = self._upgrade_card(old_card)
                if upgraded and upgraded != old_card:
                    self.state.deck[deck_index] = upgraded
                    upgraded_cards.append(self._canonical_card_id(old_card))
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, gold_paid=adjust_cost, upgraded_cards=upgraded_cards)
            self._finish_event()
            return {"success": True, "action": "designer_upgrade_two", "upgraded_cards": upgraded_cards}

        if choice_index == 1:
            self.state.player_gold -= clean_up_cost
            deck_indexes = [idx for idx, card_id in enumerate(self.state.deck) if _can_remove_card(self.state, card_id)]
            cards = [self.state.deck[idx] for idx in deck_indexes]
            if clean_up_removes_cards:
                self.state.pending_card_choice = {
                    "choice_index": choice_index,
                    "effect_type": "choose_card_to_remove",
                    "cards": cards,
                    "deck_indexes": deck_indexes,
                    "prompt": self._event_opt(event, 17),
                    "prompt_cn": self._event_opt(event, 17, cn=True),
                }
                return {"success": True, "requires_card_choice": True, "choice_index": choice_index}
            return self._set_pending_event_card_choice(
                choice_index=choice_index,
                custom_action="drug_dealer_transform",
                cards=cards,
                deck_indexes=deck_indexes,
                prompt=self._event_opt(event, 16),
                prompt_cn=self._event_opt(event, 16, cn=True),
                extra={"selected": []},
            )

        if choice_index == 2:
            self.state.player_gold -= full_service_cost
            deck_indexes = [idx for idx, card_id in enumerate(self.state.deck) if _can_remove_card(self.state, card_id)]
            cards = [self.state.deck[idx] for idx in deck_indexes]
            return self._set_pending_event_card_choice(
                choice_index=choice_index,
                custom_action="designer_remove_and_upgrade",
                cards=cards,
                deck_indexes=deck_indexes,
                prompt=self._event_opt(event, 17),
                prompt_cn=self._event_opt(event, 17, cn=True),
            )

        if choice_index == 3:
            self.state.player_hp = max(0, self.state.player_hp - hp_loss)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, hp_loss=hp_loss)
            self._finish_event()
            return {"success": True, "action": "designer_punch", "hp_loss": hp_loss}

        return {"success": False, "reason": "invalid_choice"}

    def _handle_golden_shrine_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        if choice_index == 0:
            gold_amount = 50 if self.state.ascension >= 15 else 100
            self.state.player_gold += gold_amount
            self._pending_gold_reward += gold_amount
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, gold=gold_amount)
            self._finish_event()
            return {"success": True, "action": "prayed", "gold_gained": gold_amount}
        if choice_index == 1:
            self.state.player_gold += 275
            self._pending_gold_reward += 275
            self.state.deck.append("Regret")
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, gold=275, curse="Regret")
            self._finish_event()
            return {"success": True, "action": "desecrated", "gold_gained": 275, "curse": "Regret"}
        if choice_index == 2:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            self._finish_event()
            return {"success": True, "action": "left"}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_duplicator_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        if choice_index == 0:
            return self._set_pending_event_card_choice(
                choice_index=choice_index,
                custom_action="duplicate_card",
                cards=list(self.state.deck),
                deck_indexes=list(range(len(self.state.deck))),
                prompt=self._event_opt(event, 2),
                prompt_cn=self._event_opt(event, 2, cn=True),
            )
        if choice_index == 1:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            self._finish_event()
            return {"success": True, "action": "left"}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_purifier_event(self, choice_index: int) -> dict[str, Any]:
        from sts_py.engine.run.events import _can_remove_card

        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        if choice_index == 0:
            deck_indexes = [idx for idx, card_id in enumerate(self.state.deck) if _can_remove_card(self.state, card_id)]
            cards = [self.state.deck[idx] for idx in deck_indexes]
            self.state.pending_card_choice = {
                "choice_index": choice_index,
                "effect_type": "choose_card_to_remove",
                "cards": cards,
                "deck_indexes": deck_indexes,
                "prompt": self._event_opt(event, 2),
                "prompt_cn": self._event_opt(event, 2, cn=True),
            }
            return {"success": True, "requires_card_choice": True, "choice_index": choice_index}
        if choice_index == 1:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            self._finish_event()
            return {"success": True, "action": "left"}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_upgrade_shrine_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        if choice_index == 0:
            deck_indexes = [idx for idx, card_id in enumerate(self.state.deck) if self._upgrade_card(card_id) is not None]
            cards = [self.state.deck[idx] for idx in deck_indexes]
            self.state.pending_card_choice = {
                "choice_index": choice_index,
                "effect_type": "choose_card_to_upgrade",
                "cards": cards,
                "deck_indexes": deck_indexes,
                "prompt": self._event_opt(event, 2),
                "prompt_cn": self._event_opt(event, 2, cn=True),
            }
            return {"success": True, "requires_card_choice": True, "choice_index": choice_index}
        if choice_index == 1:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            self._finish_event()
            return {"success": True, "action": "left"}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_transmorgrifier_event(self, choice_index: int) -> dict[str, Any]:
        from sts_py.engine.run.events import _can_remove_card

        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        if choice_index == 0:
            deck_indexes = [idx for idx, card_id in enumerate(self.state.deck) if _can_remove_card(self.state, card_id)]
            cards = [self.state.deck[idx] for idx in deck_indexes]
            self.state.pending_card_choice = {
                "choice_index": choice_index,
                "effect_type": "choose_card_to_transform",
                "cards": cards,
                "deck_indexes": deck_indexes,
                "prompt": self._event_opt(event, 2),
                "prompt_cn": self._event_opt(event, 2, cn=True),
            }
            return {"success": True, "requires_card_choice": True, "choice_index": choice_index}
        if choice_index == 1:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            self._finish_event()
            return {"success": True, "action": "left"}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_lab_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        if choice_index != 0:
            return {"success": False, "reason": "invalid_choice"}
        count = 2 if self.state.ascension >= 15 else 3
        potions = self._gain_random_event_potions(count)
        self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, potions=potions)
        self._finish_event()
        return {"success": True, "action": "gain_potions", "potions": potions}

    def _handle_nloth_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state().get("nloth_choices", [])
        if choice_index in {0, 1}:
            if choice_index >= len(state):
                return {"success": False, "reason": "invalid_choice"}
            relic_to_lose = state[choice_index]
            relic_id = "Circlet" if self._has_relic("NlothsGift") else "NlothsGift"
            if relic_id != "Circlet" and relic_to_lose in self.state.relics:
                self.state.relics.remove(relic_to_lose)
            self._acquire_relic(relic_id, source=RelicSource.EVENT, record_pending=True)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, lost_relic=relic_to_lose, gained_relic=relic_id)
            self._finish_event()
            return {"success": True, "action": "traded_relic", "lost_relic": relic_to_lose, "relic_id": relic_id}
        if choice_index == 2:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            self._finish_event()
            return {"success": True, "action": "left"}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_secret_portal_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        event_state = self._event_state()
        stage = str(event_state.get("stage", "intro"))
        if stage == "intro":
            if choice_index == 0:
                event_state["stage"] = "accept"
                event.description = self._event_desc(event, 1)
                event.description_cn = self._event_desc(event, 1, cn=True)
                event.choices = [self._make_event_choice(description=self._event_opt(event, 1), description_cn=self._event_opt(event, 1, cn=True))]
                return {"success": True, "action": "accept_portal", "event_continues": True}
            if choice_index == 1:
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
                self._finish_event()
                return {"success": True, "action": "left"}
            return {"success": False, "reason": "invalid_choice"}
        if stage == "accept":
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, target_floor=50)
            self._clear_current_event()
            self.state.floor = 50
            self.state.current_node_idx = -1
            self.state.map_nodes = [MapNode(floor=50, room_type=RoomType.BOSS, node_id=0, x=0, y=0)]
            self.state.phase = RunPhase.MAP
            return {"success": True, "action": "took_portal", "target_floor": 50}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_we_meet_again_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = dict(self._event_state().get("we_meet_again") or {})
        if choice_index == 0 and state.get("potion_id"):
            self._remove_potion_id(str(state["potion_id"]))
            relic_id = self._grant_random_relic(source=RelicSource.EVENT, record_pending=True)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, potion_id=state["potion_id"], relic_id=relic_id)
            self._finish_event()
            return {"success": True, "action": "gave_potion", "relic_id": relic_id}
        if choice_index == 1 and state.get("gold_amount"):
            self.state.player_gold -= int(state["gold_amount"])
            relic_id = self._grant_random_relic(source=RelicSource.EVENT, record_pending=True)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, gold_paid=state["gold_amount"], relic_id=relic_id)
            self._finish_event()
            return {"success": True, "action": "gave_gold", "relic_id": relic_id}
        if choice_index == 2 and state.get("card_id"):
            card_id = str(state["card_id"])
            if card_id in self.state.deck:
                self.state.deck.remove(card_id)
            relic_id = self._grant_random_relic(source=RelicSource.EVENT, record_pending=True)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, card_id=card_id, relic_id=relic_id)
            self._finish_event()
            return {"success": True, "action": "gave_card", "relic_id": relic_id}
        if choice_index == 3:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            self._finish_event()
            return {"success": True, "action": "attacked"}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_woman_in_blue_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        if choice_index in {0, 1, 2}:
            prices = {0: 20, 1: 30, 2: 40}
            counts = {0: 1, 1: 2, 2: 3}
            self.state.player_gold -= prices[choice_index]
            potions = self._gain_random_event_potions(counts[choice_index])
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, potions=potions, gold_paid=prices[choice_index])
            self._finish_event()
            return {"success": True, "action": "bought_potions", "potions": potions}
        if choice_index == 3:
            hp_loss = 0
            if self.state.ascension >= 15:
                hp_loss = max(1, int((self.state.player_max_hp * 0.05) + 0.999999))
                self.state.player_hp = max(0, self.state.player_hp - hp_loss)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, hp_loss=hp_loss)
            self._finish_event()
            return {"success": True, "action": "left", "hp_loss": hp_loss}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_the_joust_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        event_state = self._event_state()
        stage = str(event_state.get("stage", "intro"))
        rng = self._misc_rng()
        if stage == "intro":
            event_state["stage"] = "bet"
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
            event.choices = [
                self._make_event_choice(
                    description=self._event_opt(event, 1) + "50" + self._event_opt(event, 2) + "100" + self._event_opt(event, 3),
                    description_cn=self._event_opt(event, 1, cn=True) + "50" + self._event_opt(event, 2, cn=True) + "100" + self._event_opt(event, 3, cn=True),
                ),
                self._make_event_choice(
                    description=self._event_opt(event, 4) + "50" + self._event_opt(event, 5) + "250" + self._event_opt(event, 3),
                    description_cn=self._event_opt(event, 4, cn=True) + "50" + self._event_opt(event, 5, cn=True) + "250" + self._event_opt(event, 3, cn=True),
                ),
            ]
            return {"success": True, "action": "bet_choice", "event_continues": True}
        if stage == "bet":
            self.state.player_gold -= 50
            owner_wins = bool(rng.random_boolean_chance(0.3) if rng is not None else False)
            bet_for_owner = choice_index == 1
            gold_gained = 0
            if owner_wins and bet_for_owner:
                gold_gained = 250
            elif not owner_wins and not bet_for_owner:
                gold_gained = 100
            self.state.player_gold += gold_gained
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, gold_paid=50, gold_gained=gold_gained, owner_wins=owner_wins)
            self._finish_event()
            return {"success": True, "action": "resolved_bet", "owner_wins": owner_wins, "gold_gained": gold_gained}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_mind_bloom_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        rich_branch = (self.state.floor % 50) <= 40
        if choice_index == 0:
            rng = self._misc_rng()
            bosses = ["The Guardian", "Hexaghost", "Slime Boss"]
            boss_encounter = bosses[rng.random_int(len(bosses) - 1)] if rng is not None else bosses[0]
            rare_relic = self._draw_random_relic_of_tier("RARE")
            gold_amount = 25 if self.state.ascension >= 13 else 50
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, boss_encounter=boss_encounter, relic_id=rare_relic, gold_reward=gold_amount)
            self._clear_current_event()
            self._set_current_event_combat(
                enemies=[boss_encounter],
                bonus_reward=rare_relic,
                pending_event_rewards=[f"gold:{gold_amount}"],
                is_elite_combat=False,
            )
            self.start_combat_with_monsters([boss_encounter])
            return {"success": True, "action": "boss_combat", "boss_encounter": boss_encounter, "relic_id": rare_relic, "gold_reward": gold_amount}
        if choice_index == 1:
            upgraded_cards: list[str] = []
            for idx, card_id in enumerate(list(self.state.deck)):
                upgraded = self._upgrade_card(card_id)
                if upgraded is None or upgraded == card_id:
                    continue
                self.state.deck[idx] = upgraded
                upgraded_cards.append(self._canonical_card_id(card_id))
            self._acquire_relic("MarkOfTheBloom", source=RelicSource.EVENT, record_pending=True)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, upgraded_cards=upgraded_cards, relic_id="MarkOfTheBloom")
            self._finish_event()
            return {"success": True, "action": "upgrade_all", "upgraded_cards": upgraded_cards, "relic_id": "MarkOfTheBloom"}
        if choice_index == 2:
            if rich_branch:
                self.state.player_gold += 999
                self._pending_gold_reward += 999
                self.state.deck.extend(["Normality", "Normality"])
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, gold=999, curses=["Normality", "Normality"])
                self._finish_event()
                return {"success": True, "action": "gain_gold", "gold_gained": 999, "curses": ["Normality", "Normality"]}
            healed = self.state.player_max_hp - self.state.player_hp
            self.state.player_hp = self.state.player_max_hp
            self.state.deck.append("Doubt")
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, healed=healed, curse="Doubt")
            self._finish_event()
            return {"success": True, "action": "heal_to_full", "healed": healed, "curse": "Doubt"}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_falling_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        event_state = self._event_state()
        stage = str(event_state.get("stage", "intro"))
        rng = self._misc_rng()
        if stage == "intro":
            from sts_py.engine.content.cards_min import ALL_CARD_DEFS

            buckets = {"ATTACK": [], "SKILL": [], "POWER": []}
            for deck_index, card_id in enumerate(self.state.deck):
                base = self._canonical_card_id(card_id)
                card_def = ALL_CARD_DEFS.get(base)
                if card_def is None:
                    continue
                card_type = str(getattr(card_def, "card_type", "")).rsplit(".", 1)[-1]
                if card_type in buckets:
                    buckets[card_type].append((deck_index, card_id))
            picks: dict[str, tuple[int, str] | None] = {}
            for card_type, options in buckets.items():
                if not options:
                    picks[card_type] = None
                    continue
                pick_idx = rng.random_int(len(options) - 1) if rng is not None else 0
                picks[card_type] = options[pick_idx]
            event_state["stage"] = "choice"
            event_state["falling_picks"] = picks
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
            if not any(picks.values()):
                event.choices = [self._make_event_choice(description=self._event_opt(event, 8), description_cn=self._event_opt(event, 8, cn=True))]
                return {"success": True, "action": "no_cards", "event_continues": True}
            event.choices = []
            if picks["SKILL"] is not None:
                event.choices.append(self._make_event_choice(description=self._event_opt(event, 1) + str(picks["SKILL"][1]), description_cn=self._event_opt(event, 1, cn=True) + str(picks["SKILL"][1])))
            else:
                event.choices.append(self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True), enabled=False))
            if picks["POWER"] is not None:
                event.choices.append(self._make_event_choice(description=self._event_opt(event, 3) + str(picks["POWER"][1]), description_cn=self._event_opt(event, 3, cn=True) + str(picks["POWER"][1])))
            else:
                event.choices.append(self._make_event_choice(description=self._event_opt(event, 4), description_cn=self._event_opt(event, 4, cn=True), enabled=False))
            if picks["ATTACK"] is not None:
                event.choices.append(self._make_event_choice(description=self._event_opt(event, 5) + str(picks["ATTACK"][1]), description_cn=self._event_opt(event, 5, cn=True) + str(picks["ATTACK"][1])))
            else:
                event.choices.append(self._make_event_choice(description=self._event_opt(event, 6), description_cn=self._event_opt(event, 6, cn=True), enabled=False))
            return {"success": True, "action": "choice", "event_continues": True}
        if stage == "choice":
            picks = dict(event_state.get("falling_picks") or {})
            choice_map = [picks.get("SKILL"), picks.get("POWER"), picks.get("ATTACK")]
            target = choice_map[choice_index] if 0 <= choice_index < len(choice_map) else None
            if target is None:
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
                self._finish_event()
                return {"success": True, "action": "nothing_to_remove"}
            deck_index, card_id = target
            if 0 <= deck_index < len(self.state.deck):
                self.state.deck.pop(deck_index)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, card_id=card_id)
            self._finish_event()
            return {"success": True, "action": "removed_card", "card_id": card_id}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_mysterious_sphere_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        event_state = self._event_state()
        stage = str(event_state.get("stage", "intro"))
        if stage == "intro":
            if choice_index == 0:
                event_state["stage"] = "pre_combat"
                event.description = self._event_desc(event, 1)
                event.description_cn = self._event_desc(event, 1, cn=True)
                event.choices = [self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True))]
                return {"success": True, "action": "pre_combat", "event_continues": True}
            if choice_index == 1:
                self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
                self._finish_event()
                return {"success": True, "action": "left"}
            return {"success": False, "reason": "invalid_choice"}
        if stage == "pre_combat":
            relic_id = self._draw_random_relic_of_tier("rare")
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, relic_id=relic_id)
            self._clear_current_event()
            self._set_current_event_combat(
                enemies=["OrbWalker", "OrbWalker"],
                bonus_reward=relic_id,
                pending_event_rewards=[],
                is_elite_combat=False,
            )
            self.start_combat_with_monsters(["OrbWalker", "OrbWalker"])
            return {"success": True, "action": "combat", "relic_id": relic_id, "is_event_combat": True}
        return {"success": False, "reason": "invalid_choice"}

    def _handle_bonfire_event(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        event_state = self._event_state()
        stage = str(event_state.get("stage", "intro"))
        if stage == "intro":
            event_state["stage"] = "offer"
            event.description = self._event_desc(event, 1)
            event.description_cn = self._event_desc(event, 1, cn=True)
            event.choices = [self._make_event_choice(description=self._event_opt(event, 2), description_cn=self._event_opt(event, 2, cn=True))]
            return {"success": True, "action": "offer_prompt", "event_continues": True}
        if stage == "offer":
            from sts_py.engine.run.events import _can_remove_card

            deck_indexes = [idx for idx, card_id in enumerate(self.state.deck) if _can_remove_card(self.state, card_id)]
            cards = [self.state.deck[idx] for idx in deck_indexes]
            if not cards:
                self._finish_event()
                return {"success": True, "action": "no_offerable_cards"}
            return self._set_pending_event_card_choice(
                choice_index=choice_index,
                custom_action="bonfire_offer",
                cards=cards,
                deck_indexes=deck_indexes,
                prompt=self._event_opt(event, 3),
                prompt_cn=self._event_opt(event, 3, cn=True),
            )
        return {"success": False, "reason": "invalid_choice"}

    def _handle_dead_adventurer(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}

        if not hasattr(self.state, 'dead_adventurer_state') or not self.state.dead_adventurer_state:
            self.state.dead_adventurer_state = {
                "searches_done": 0,
                "rewards_given": {"gold": False, "nothing": False, "relic": False},
                "encounter_triggered": False,
                "monster_type": None,
                "enemy_index": None,
                "continuation_mode": False,
            }

        da_state = self.state.dead_adventurer_state

        if da_state.get("encounter_triggered"):
            return {"success": False, "reason": "encounter_in_progress"}

        if choice_index == 1:
            self.state.event_choices.append({
                "floor": self.state.floor,
                "event_id": event.id,
                "choice_index": choice_index,
                "choice_text": "Leave",
            })
            self._current_event = None
            self.state.dead_adventurer_state = {}
            self.state.phase = RunPhase.MAP
            return {"success": True, "action": "left", "rewards_obtained": da_state["rewards_given"]}

        if choice_index != 0:
            return {"success": False, "reason": "invalid_choice"}

        return self._do_dead_adventurer_search(event, da_state)

    def _do_dead_adventurer_search(self, event: "Event", da_state: dict) -> dict[str, Any]:
        choice = event.get_choice(0)
        if choice is None:
            return {"success": False, "reason": "invalid_choice"}

        encounter_chance = int(choice.encounter_chance or ((35 if self.state.ascension >= 15 else 25) + 25 * int(da_state.get("searches_done", 0) or 0)))

        roll = self._misc_rng().random_int(99) if self._misc_rng() is not None else 0
        if roll < encounter_chance:
            da_state["encounter_triggered"] = True
            da_state["searches_done"] += 1
            enemy_index = int(da_state.get("enemy_index", 0) or 0)
            encounter_names = ["3 Sentries", "Gremlin Nob", "Lagavulin Event"]
            encounter_monsters = [
                ["Sentry", "Sentry", "Sentry"],
                ["GremlinNob"],
                ["Lagavulin Event"],
            ]
            da_state["monster_type"] = encounter_names[enemy_index]
            self.state.event_choices.append({
                "floor": self.state.floor,
                "event_id": event.id,
                "choice_index": 0,
                "choice_text": f"Search (encounter: {da_state['monster_type']})",
            })
            self._current_event = None
            self.state.dead_adventurer_state = {}
            missing_rewards = [k for k, v in da_state["rewards_given"].items() if not v]
            self._set_current_event_combat(
                enemies=encounter_monsters[enemy_index],
                bonus_reward=None,
                pending_event_rewards=missing_rewards,
                is_elite_combat=True,
            )
            self.start_combat_with_monsters(encounter_monsters[enemy_index])
            return {
                "success": True,
                "action": "encounter",
                "monster": da_state["monster_type"],
                "searches_done": da_state["searches_done"],
                "is_event_combat": True,
                "is_elite_combat": True,
            }
        else:
            available_rewards = [k for k, v in da_state["rewards_given"].items() if not v]
            if not available_rewards:
                self.state.event_choices.append({
                    "floor": self.state.floor,
                    "event_id": event.id,
                    "choice_index": 0,
                    "choice_text": "Search (all rewards taken)",
                })
                self._current_event = None
                self.state.dead_adventurer_state = {}
                self.state.phase = RunPhase.MAP
                return {"success": True, "action": "all_rewards_taken"}
            reward = available_rewards[self._misc_rng().random_int(len(available_rewards) - 1) if self._misc_rng() is not None else 0]
            da_state["rewards_given"][reward] = True
            reward_result = {}
            description_idx = 8
            if reward == "gold":
                self.state.player_gold += 30
                self._pending_gold_reward += 30
                reward_result = {"type": "gold", "amount": 30}
                description_idx = 7
            elif reward == "relic":
                relic_id = self._grant_random_relic(source=RelicSource.EVENT)
                reward_result = {"type": "relic", "id": relic_id}
                description_idx = 9
            else:
                reward_result = {"type": "nothing"}
            da_state["searches_done"] += 1
            event.description = self._event_desc(event, description_idx)
            event.description_cn = self._event_desc(event, description_idx, cn=True)
            self.state.event_choices.append({
                "floor": self.state.floor,
                "event_id": event.id,
                "choice_index": 0,
                "choice_text": f"Search (got: {reward})",
            })

            if da_state["searches_done"] >= 3:
                event.description = self._event_desc(event, 10)
                event.description_cn = self._event_desc(event, 10, cn=True)
                self._current_event = None
                self.state.dead_adventurer_state = {}
                self.state.phase = RunPhase.MAP
                return {
                    "success": True,
                    "action": "max_searches_reached",
                    "reward": reward_result,
                    "searches_done": da_state["searches_done"],
                }

            da_state["continuation_mode"] = True
            self._update_dead_adventurer_choices(event, da_state)
            return {
                "success": True,
                "action": "search_success",
                "reward": reward_result,
                "searches_done": da_state["searches_done"],
                "can_continue": da_state["searches_done"] < 3,
                "event_continues": True,
            }

    def _update_dead_adventurer_choices(self, event: "Event", da_state: dict) -> None:
        from sts_py.engine.run.events import EventChoice

        searches_done = da_state["searches_done"]
        encounter_chance = min(100, (35 if self.state.ascension >= 15 else 25) + searches_done * 25)
        event.choices = [
            EventChoice(
                description=self._event_opt(event, 3) + str(encounter_chance) + self._event_opt(event, 4),
                description_cn=self._event_opt(event, 3, cn=True) + str(encounter_chance) + self._event_opt(event, 4, cn=True),
                effects=[],
                encounter_chance=encounter_chance,
                search_level=searches_done + 1,
            ),
            EventChoice(
                description=self._event_opt(event, 1),
                description_cn=self._event_opt(event, 1, cn=True),
                effects=[]
            ),
        ]

    def _handle_golden_shrine(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}

        if choice_index == 1:
            self.state.event_choices.append({
                "floor": self.state.floor,
                "event_id": event.id,
                "event_key": getattr(event, "event_key", None),
                "choice_index": choice_index,
                "choice_text": "Leave",
            })
            self._clear_current_event()
            self.state.phase = RunPhase.MAP
            return {"success": True, "action": "left"}

        if choice_index != 0:
            return {"success": False, "reason": "invalid_choice"}

        choice = event.get_choice(choice_index)
        if choice is None:
            return {"success": False, "reason": "invalid_choice"}

        self._acquire_relic("GoldenIdol", source=RelicSource.EVENT, record_pending=True)
        self._set_current_event(self._create_golden_shrine_trap_event())
        self.state.event_choices.append({
            "floor": self.state.floor,
            "event_id": event.id,
            "event_key": getattr(event, "event_key", None),
            "choice_index": choice_index,
            "choice_text": "Take Golden Idol",
        })
        return {"success": True, "action": "trap_triggered", "relic_obtained": "GoldenIdol"}

    def _create_golden_shrine_trap_event(self) -> "Event":
        from sts_py.engine.run.events import Event, EventChoice, EventEffect, EventEffectType
        from sts_py.engine.run.official_event_strings import get_official_event_strings

        official = get_official_event_strings("Golden Idol")
        descriptions_en = list(official.descriptions_en) if official is not None else []
        descriptions_cn = list(official.descriptions_zhs) if official is not None else []
        options_en = list(official.options_en) if official is not None else []
        options_cn = list(official.options_zhs) if official is not None else []
        damage_pct = 35 if self.state.ascension >= 15 else 25
        max_hp_pct = 10 if self.state.ascension >= 15 else 8

        trap_event = Event(
            id="Golden Shrine Trap",
            name="Golden Idol",
            name_cn=str(getattr(official, "name_zhs", "") or "Golden Idol"),
            event_key="Golden Shrine Trap",
            pool_bucket="special",
            description=descriptions_en[1] if len(descriptions_en) > 1 else "A massive boulder rolls toward you!",
            description_cn=descriptions_cn[1] if len(descriptions_cn) > 1 else "",
            source_descriptions=descriptions_en,
            source_descriptions_cn=descriptions_cn,
            source_options=options_en,
            source_options_cn=options_cn,
            choices=[
                EventChoice(
                    description=options_en[2] if len(options_en) > 2 else "[Run] Get cursed with Injury. Run away!",
                    description_cn="[逃跑] 被诅咒——受伤。快跑！",
                    effects=[],
                ),
                EventChoice(
                    description=(options_en[3] + str(damage_pct) + options_en[4]) if len(options_en) > 4 else f"[Smash] Lose {damage_pct}% HP. Attack the boulder!",
                    description_cn="[砸烂] 失去25%生命。你用尽全力向巨石发起了攻击。",
                    effects=[
                        EventEffect(EventEffectType.LOSE_HP_PERCENT, amount=damage_pct),
                    ],
                ),
                EventChoice(
                    description=(options_en[5] + str(max_hp_pct) + options_en[6]) if len(options_en) > 6 else f"[Hide] Lose {max_hp_pct}% Max HP. The boulder grazes you.",
                    description_cn="[躲藏] 失去8%最大生命。咕叽！巨石滚过时压到了你一点。",
                    effects=[
                        EventEffect(EventEffectType.LOSE_MAX_HP_PERCENT, amount=max_hp_pct),
                    ],
                ),
            ],
            act=self.state.act,
        )
        return trap_event

    def _handle_golden_shrine_trap(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}

        choice = event.get_choice(choice_index)
        if choice is None:
            return {"success": False, "reason": "invalid_choice"}

        if choice_index == 0:
            self.state.deck.append("Injury")
            result = {"action": "run", "curse_added": "Injury"}
        else:
            result = choice.apply(self)

        self.state.event_choices.append({
            "floor": self.state.floor,
            "event_id": event.id,
            "choice_index": choice_index,
            "choice_text": choice.description,
        })
        self._current_event = None
        self.state.phase = RunPhase.MAP

        if self.state.player_hp <= 0:
            self.state.phase = RunPhase.GAME_OVER

        return result

    def _handle_world_of_goop(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}

        choice = event.get_choice(choice_index)
        if choice is None:
            return {"success": False, "reason": "invalid_choice"}

        if choice_index == 1:
            state = self._event_state()
            gold_lost = int(state.get("gold_loss", 20) or 20)
            gold_lost = min(gold_lost, self.state.player_gold)
            self.state.player_gold -= gold_lost
            result = {"action": "leave", "gold_lost": gold_lost}
        else:
            result = choice.apply(self)

        self.state.event_choices.append({
            "floor": self.state.floor,
            "event_id": event.id,
            "choice_index": choice_index,
            "choice_text": choice.description,
        })
        self._current_event = None
        self.state.phase = RunPhase.MAP

        if self.state.player_hp <= 0:
            self.state.phase = RunPhase.GAME_OVER

        return result

    def _handle_wing_statuette(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}

        if not hasattr(self.state, 'wing_statuette_state') or not self.state.wing_statuette_state:
            self.state.wing_statuette_state = {"phase": "initial"}

        ws_state = self.state.wing_statuette_state

        if ws_state.get("phase") == "selecting_card":
            if choice_index == len(self.state.deck):
                self.state.wing_statuette_state = {}
                self._current_event = None
                self.state.phase = RunPhase.MAP
                return {"success": True, "action": "cancelled"}
            card_id = self.state.deck[choice_index]
            from sts_py.engine.run.events import _apply_parasite_penalty
            _apply_parasite_penalty(self.state, card_id)
            self.state.deck.remove(card_id)
            self.state.wing_statuette_state = {}
            self._current_event = None
            self.state.phase = RunPhase.MAP
            return {"success": True, "action": "card_removed", "card_id": card_id}

        choice = event.get_choice(choice_index)
        if choice is None:
            return {"success": False, "reason": "invalid_choice"}

        if choice_index == 2:
            result = choice.apply(self)
            self._current_event = None
            self.state.wing_statuette_state = {}
        elif choice_index == 0:
            self.state.player_hp -= 7
            survival_result = self._check_survival_relics(7)
            ws_state["phase"] = "selecting_card"
            return {
                "success": True,
                "action": "select_card",
                "message": "Choose a card to remove",
                "cards": self.state.deck,
                "can_cancel": True,
                "survival_check": survival_result,
            }
        elif choice_index == 1:
            gold_min, gold_max = 50, 80
            gold_gained = self._misc_rng().random_int(gold_max - gold_min) + gold_min if self._misc_rng() is not None else gold_min
            self.state.player_gold += gold_gained
            result = {"action": "destroy", "gold_gained": gold_gained}
            self._current_event = None
            self.state.wing_statuette_state = {}
        else:
            return {"success": False, "reason": "invalid_choice"}

        self.state.event_choices.append({
            "floor": self.state.floor,
            "event_id": event.id,
            "choice_index": choice_index,
            "choice_text": choice.description,
        })

        if self.state.player_hp <= 0:
            self.state.phase = RunPhase.GAME_OVER

        return result

    def _handle_living_wall(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}

        if not hasattr(self.state, 'living_wall_state') or not self.state.living_wall_state:
            self.state.living_wall_state = {"phase": "initial"}

        lw_state = self.state.living_wall_state

        if lw_state.get("phase") == "selecting_card":
            if choice_index == len(self.state.deck):
                self.state.living_wall_state = {}
                self._current_event = None
                self.state.phase = RunPhase.MAP
                return {"success": True, "action": "cancelled"}

            card_id = self.state.deck[choice_index]
            action = lw_state.get("action_type")

            if action == "remove":
                from sts_py.engine.run.events import _can_remove_card, _apply_parasite_penalty
                if not _can_remove_card(self.state, card_id):
                    return {"success": False, "reason": "card_cannot_be_removed"}
                _apply_parasite_penalty(self.state, card_id)
                self.state.deck.remove(card_id)
            elif action == "transform":
                from sts_py.engine.run.events import _apply_parasite_penalty
                _apply_parasite_penalty(self.state, card_id)
                self.state.deck.remove(card_id)
            elif action == "upgrade":
                upgraded_card = self._upgrade_card(card_id)
                if upgraded_card and upgraded_card != card_id:
                    idx = self.state.deck.index(card_id)
                    self.state.deck[idx] = upgraded_card
                    return {"success": True, "action": "card_upgraded", "old_card": card_id, "new_card": upgraded_card}
                return {"success": False, "reason": "card_cannot_be_upgraded", "card_id": card_id}

            self.state.living_wall_state = {}
            self._current_event = None
            self.state.phase = RunPhase.MAP
            return {"success": True, "action": f"card_{action}", "card_id": card_id}

        choice = event.get_choice(choice_index)
        if choice is None:
            return {"success": False, "reason": "invalid_choice"}

        if choice_index == 0:
            lw_state["phase"] = "selecting_card"
            lw_state["action_type"] = "remove"
            return {
                "success": True,
                "action": "select_card",
                "message": "Choose a card to remove",
                "cards": self.state.deck,
                "can_cancel": True,
            }
        elif choice_index == 1:
            lw_state["phase"] = "selecting_card"
            lw_state["action_type"] = "transform"
            return {
                "success": True,
                "action": "select_card",
                "message": "Choose a card to transform",
                "cards": self.state.deck,
                "can_cancel": True,
            }
        elif choice_index == 2:
            lw_state["phase"] = "selecting_card"
            lw_state["action_type"] = "upgrade"
            return {
                "success": True,
                "action": "select_card",
                "message": "Choose a card to upgrade",
                "cards": self.state.deck,
                "can_cancel": True,
            }
        else:
            return {"success": False, "reason": "invalid_choice"}

    def _handle_mushrooms(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}

        choice = event.get_choice(choice_index)
        if choice is None:
            return {"success": False, "reason": "invalid_choice"}

        if choice_index == 0:
            reward_relic = "Circlet" if self._has_relic("OddMushroom") else "OddMushroom"
            self.state.event_choices.append({
                "floor": self.state.floor,
                "event_id": event.id,
                "choice_index": choice_index,
                "choice_text": choice.description,
            })
            self._current_event = None
            self._set_current_event_combat(
                enemies=choice.combat_enemies,
                bonus_reward=reward_relic,
                pending_event_rewards=["gold_range:20:30"],
                is_elite_combat=False,
            )
            self.start_combat_with_monsters(choice.combat_enemies)
            return {
                "success": True,
                "action": "combat",
                "enemies": choice.combat_enemies,
                "bonus_reward": reward_relic,
                "is_event_combat": True,
            }
        elif choice_index == 1:
            result = choice.apply(self)
            self.state.event_choices.append({
                "floor": self.state.floor,
                "event_id": event.id,
                "choice_index": choice_index,
                "choice_text": choice.description,
            })
            self._current_event = None
            self.state.phase = RunPhase.MAP
            if self.state.player_hp <= 0:
                self.state.phase = RunPhase.GAME_OVER
            return result
        else:
            return {"success": False, "reason": "invalid_choice"}

    def _handle_scrap_ooze(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}

        if not hasattr(self.state, 'scrap_ooze_state') or not self.state.scrap_ooze_state:
            self.state.scrap_ooze_state = {"attempts": 0}

        so_state = self.state.scrap_ooze_state

        if choice_index == 1:
            self.state.event_choices.append({
                "floor": self.state.floor,
                "event_id": event.id,
                "choice_index": choice_index,
                "choice_text": "Leave",
            })
            self._current_event = None
            self.state.scrap_ooze_state = {}
            self.state.phase = RunPhase.MAP
            return {"success": True, "action": "left"}

        if choice_index != 0:
            return {"success": False, "reason": "invalid_choice"}

        attempts = so_state["attempts"]
        base_damage = 5 if self.state.ascension >= 15 else 3
        base_chance = 25

        damage = base_damage + attempts
        chance = base_chance + (10 * attempts)

        self.state.player_hp -= damage
        survival_result = self._check_survival_relics(damage)

        roll = self._misc_rng().random_int(99) if self._misc_rng() is not None else 0
        found_relic = roll < chance

        if found_relic:
            from sts_py.engine.content.relics import roll_relic_rarity, get_random_relic_by_tier
            rarity = roll_relic_rarity(self.state.rng.treasure_rng if self.state.rng else None)
            tier_str = rarity.value
            relic_id = get_random_relic_by_tier(tier_str, self.state.rng.treasure_rng if self.state.rng else None)
            if relic_id:
                self._acquire_relic(relic_id, source=RelicSource.EVENT, record_pending=True)
            self.state.event_choices.append({
                "floor": self.state.floor,
                "event_id": event.id,
                "choice_index": choice_index,
                "choice_text": f"Reach in (found: {relic_id})",
            })
            self._current_event = None
            self.state.scrap_ooze_state = {}
            self.state.phase = RunPhase.MAP
            return {"success": True, "action": "found_relic", "relic_id": relic_id}

        if survival_result["survived"]:
            self._current_event = None
            self.state.scrap_ooze_state = {}
            self.state.phase = RunPhase.MAP
            return {
                "success": True,
                "action": "died_but_survived",
                "survival_check": survival_result,
            }

        so_state["attempts"] += 1

        self._update_scrap_ooze_choices(event, so_state)

        return {
            "success": True,
            "action": "continue",
            "damage_taken": damage,
            "new_chance": base_chance + (10 * so_state["attempts"]),
            "event_continues": True,
        }

    def _update_scrap_ooze_choices(self, event: "Event", so_state: dict) -> None:
        from sts_py.engine.run.events import EventChoice

        attempts = so_state["attempts"]
        base_damage = 5 if self.state.ascension >= 15 else 3
        new_damage = base_damage + attempts
        new_chance = 25 + (10 * attempts)
        description_idx = 0 if attempts == 0 else 1
        option_idx = 0 if attempts == 0 else 4
        event.description = self._event_desc(event, description_idx)
        event.description_cn = self._event_desc(event, description_idx, cn=True)
        event.choices = [
            EventChoice(
                description=self._event_opt(event, option_idx) + str(new_damage) + self._event_opt(event, 1) + str(new_chance) + self._event_opt(event, 2),
                description_cn=self._event_opt(event, option_idx, cn=True) + str(new_damage) + self._event_opt(event, 1, cn=True) + str(new_chance) + self._event_opt(event, 2, cn=True),
                effects=[],
                base_damage=base_damage,
                base_chance=25,
            ),
            EventChoice(
                description=self._event_opt(event, 3),
                description_cn=self._event_opt(event, 3, cn=True),
                effects=[]
            ),
        ]

    def _handle_shining_light(self, choice_index: int) -> dict[str, Any]:
        import math

        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}

        choice = event.get_choice(choice_index)
        if choice is None:
            return {"success": False, "reason": "invalid_choice"}

        if choice_index == 1:
            self.state.event_choices.append({
                "floor": self.state.floor,
                "event_id": event.id,
                "choice_index": choice_index,
                "choice_text": "Leave",
            })
            self._current_event = None
            self.state.phase = RunPhase.MAP
            return {"success": True, "action": "left"}

        if choice_index != 0:
            return {"success": False, "reason": "invalid_choice"}

        upgradeable_cards = [
            i for i, card_id in enumerate(self.state.deck)
            if self._upgrade_card(card_id) is not None
        ]
        if not upgradeable_cards:
            self._current_event = None
            self.state.phase = RunPhase.MAP
            return {"success": True, "action": "no_upgradeable_cards"}

        if len(upgradeable_cards) == 1:
            card_idx = upgradeable_cards[0]
            card_id = self.state.deck[card_idx]
            upgraded_card = self._upgrade_card(card_id)
            if upgraded_card is not None:
                self.state.deck[card_idx] = upgraded_card
            upgraded_cards = [card_id]
        else:
            rng = self._misc_rng()
            candidate_indexes = list(upgradeable_cards)
            to_upgrade: list[int] = []
            while candidate_indexes and len(to_upgrade) < min(2, len(upgradeable_cards)):
                pick_idx = rng.random_int(len(candidate_indexes) - 1) if rng is not None else 0
                to_upgrade.append(candidate_indexes.pop(pick_idx))
            upgraded_cards = []
            for card_idx in to_upgrade:
                card_id = self.state.deck[card_idx]
                upgraded_card = self._upgrade_card(card_id)
                if upgraded_card is not None:
                    self.state.deck[card_idx] = upgraded_card
                    upgraded_cards.append(card_id)

        lose_hp_percent = 30 if self.state.ascension >= 15 else 20
        lose_hp = int(math.floor(self.state.player_max_hp * (lose_hp_percent / 100.0) + 0.5))
        self.state.player_hp -= lose_hp
        survival_result = self._check_survival_relics(lose_hp)

        self.state.event_choices.append({
            "floor": self.state.floor,
            "event_id": event.id,
            "choice_index": choice_index,
            "choice_text": f"Enter (upgraded: {upgraded_cards})",
        })
        self._current_event = None
        self.state.phase = RunPhase.MAP

        result = {
            "success": True,
            "action": "upgraded",
            "upgraded_cards": upgraded_cards,
            "hp_lost": lose_hp,
            "survival_check": survival_result,
        }

        return result

    def _check_survival_relics(self, damage_amount: int, in_combat: bool = False) -> dict[str, Any]:
        """Check and apply survival relic effects after taking damage.

        Lizard Tail: When taking fatal damage, heal to 50% (75% with Magic Flower in combat)
        Fairy in a Bottle: Heal 30% (60% with Sacred Bark)

        Returns dict with 'survived' and 'healed_by' info.
        """
        result = {"survived": False, "healed_by": None, "damage_amount": damage_amount}

        if self.state.player_hp > 0:
            return result

        if self._has_relic("LizardTail"):
            heal_percent = 0.75 if (in_combat and self._has_relic("MagicFlower")) else 0.50
            heal_amount = round(self.state.player_max_hp * heal_percent)
            self.state.player_hp = heal_amount
            result["survived"] = True
            result["healed_by"] = "Lizard Tail"
            return result

        if self._has_relic("FairyPotion"):
            heal_percent = 0.60 if self._has_relic("SacredBark") else 0.30
            heal_amount = round(self.state.player_max_hp * heal_percent)
            self.state.player_hp = heal_amount
            result["survived"] = True
            result["healed_by"] = "Fairy in a Bottle"
            return result

        return result

    def _apply_magic_flower_amplification(self, heal_amount: int, in_combat: bool = True) -> int:
        """Apply Magic Flower amplification to a heal amount.

        Magic Flower: +50% healing in combat (1.5x), round half up.
        Only works during combat, not outside.
        """
        if not self._has_relic("MagicFlower"):
            return heal_amount
        if not in_combat:
            return heal_amount
        amplified = heal_amount * 1.5
        return round(amplified)

    def _has_relic(self, canonical_id: str) -> bool:
        from sts_py.engine.content.relics import normalize_relic_id

        target = str(normalize_relic_id(canonical_id) or canonical_id)
        for relic_id in self.state.relics:
            if str(normalize_relic_id(relic_id) or relic_id) == target:
                return True
        return False

    def _handle_face_trader(self, choice_index: int) -> dict[str, Any]:
        event = self._current_event
        if event is None:
            return {"success": False, "reason": "no_event"}
        state = self._event_state()
        stage = str(state.get("stage", "intro"))
        if stage == "result":
            self._finish_event()
            return {"success": True, "action": "left"}
        if stage != "main":
            state["stage"] = "main"
            self._configure_face_trader_event(event)
            return {"success": True, "action": "main_menu", "event_continues": True}

        if choice_index == 0:
            lose_hp = max(1, self.state.player_max_hp // 10)
            gold_gained = 50 if self.state.ascension >= 15 else 75
            self.state.player_hp = max(0, self.state.player_hp - lose_hp)
            self.state.player_gold += gold_gained
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, hp_lost=lose_hp, gold_gained=gold_gained)
            event.description = self._event_desc(event, 2)
            event.description_cn = self._event_desc(event, 2, cn=True)
        elif choice_index == 1:
            mask_ids = ["CultistMask", "FaceOfCleric", "GremlinMask", "NlothsMask", "SsserpentHead"]
            available = [mask_id for mask_id in mask_ids if not self._has_relic(mask_id)] or ["Circlet"]
            relic_id = str(self._event_random_choice(available, rng=self._misc_rng()) or available[0])
            self._acquire_relic(relic_id, source=RelicSource.EVENT, record_pending=True)
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description, relic_id=relic_id)
            event.description = self._event_desc(event, 3)
            event.description_cn = self._event_desc(event, 3, cn=True)
        elif choice_index == 2:
            self._record_current_event_choice(event, choice_index=choice_index, choice_text=event.choices[choice_index].description)
            event.description = self._event_desc(event, 4)
            event.description_cn = self._event_desc(event, 4, cn=True)
        else:
            return {"success": False, "reason": "invalid_choice"}
        event.choices = [self._make_event_choice(description=self._event_opt(event, 3), description_cn=self._event_opt(event, 3, cn=True))]
        state["stage"] = "result"
        return {"success": True, "action": "resolved", "event_continues": True}

    def _enter_shop(self) -> None:
        from sts_py.engine.run.shop import generate_shop, ShopEngine
        if self.state.rng is None:
            return
        shop_relics = self._generate_shop_relics()
        shop_state = generate_shop(
            self.state.rng.merchant_rng,
            act=self.state.act,
            character_class=self.state.character_class,
            ascension_level=self.state.ascension,
            has_courier=self._has_relic("TheCourier"),
            has_membership=self._has_relic("MembershipCard"),
            relics=shop_relics,
        )
        self._shop_engine = ShopEngine(self, shop_state)
        self._apply_shop_enter_effects()
        self.state.phase = RunPhase.SHOP

    def get_shop(self) -> "ShopEngine | None":
        return self._shop_engine

    def buy_card(self, card_index: int) -> dict[str, Any]:
        if self._shop_engine is None:
            return {"success": False, "reason": "no_shop"}
        return self._shop_engine.buy_card(card_index)

    def buy_relic(self, relic_index: int) -> dict[str, Any]:
        if self._shop_engine is None:
            return {"success": False, "reason": "no_shop"}
        return self._shop_engine.buy_relic(relic_index)

    def remove_card_from_deck(self, card_id: str) -> dict[str, Any]:
        if self._shop_engine is None:
            return {"success": False, "reason": "no_shop"}
        return self._shop_engine.remove_card(card_id)

    def leave_shop(self) -> None:
        self._shop_engine = None
        self.state.phase = RunPhase.MAP

    def _relic_matches_character(self, relic_def: Any) -> bool:
        character_class = str(getattr(relic_def, "character_class", "") or "")
        return (
            not character_class
            or character_class == "UNIVERSAL"
            or character_class == self.state.character_class
        )

    def _current_relic_ids(self) -> set[str]:
        return {self._canonical_relic_id(relic_id) for relic_id in self.state.relics}

    def _ensure_relic_pool_consumed(self) -> dict[str, list[str]]:
        pools = getattr(self.state, "relic_pool_consumed", None)
        if not isinstance(pools, dict):
            pools = _new_relic_pool_consumed()
        for tier_key in ("boss", "common", "uncommon", "rare", "shop"):
            bucket = pools.get(tier_key)
            if not isinstance(bucket, list):
                pools[tier_key] = []
        self.state.relic_pool_consumed = pools
        return pools

    def _consumed_relic_ids(self, tier_keys: list[str]) -> set[str]:
        pools = self._ensure_relic_pool_consumed()
        consumed: set[str] = set()
        for tier_key in tier_keys:
            consumed.update(str(relic_id) for relic_id in pools.get(tier_key, []))
        return consumed

    def _mark_relic_consumed(self, relic_id: str, tier_key: str) -> None:
        pools = self._ensure_relic_pool_consumed()
        bucket = pools.setdefault(tier_key, [])
        canonical_id = self._canonical_relic_id(relic_id)
        if canonical_id not in bucket:
            bucket.append(canonical_id)

    def _generate_shop_relic_item(self, *, tier_key: str, exclude: set[str]) -> Any | None:
        from sts_py.engine.content.relics import RelicTier, get_relic_pool
        from sts_py.engine.run.shop import ShopItem, ShopItemType, get_relic_price

        tier = {
            "common": RelicTier.COMMON,
            "uncommon": RelicTier.UNCOMMON,
            "rare": RelicTier.RARE,
            "shop": RelicTier.SHOP,
        }.get(tier_key)
        if tier is None:
            return None
        rng = self.state.rng.merchant_rng if self.state.rng is not None else None
        chosen = self._choose_random_relic_offer(
            get_relic_pool(
                tier,
                floor=self.state.floor,
                act=self.state.act,
                context="shop_offer",
                owned_relics=self.state.relics,
                deck=self.state.deck,
            ),
            exclude=exclude,
            rng=rng,
        )
        if chosen is None:
            return None
        self._mark_relic_consumed(chosen.id, tier_key)
        price = get_relic_price(tier_key, rng)
        return ShopItem(
            item_type=ShopItemType.RELIC,
            item_id=chosen.id,
            price=price,
            original_price=price,
            tier=tier_key,
        )

    def _generate_shop_relics(self) -> list[Any]:
        from sts_py.engine.run.shop import roll_relic_tier

        if self.state.rng is None:
            return []
        rng = self.state.rng.merchant_rng
        exclude = self._current_relic_ids()
        exclude.update(self._consumed_relic_ids(["common", "uncommon", "rare", "shop"]))
        relics: list[Any] = []
        for slot_idx in range(3):
            tier_key = "shop" if slot_idx == 2 else roll_relic_tier(rng)
            item = self._generate_shop_relic_item(tier_key=tier_key, exclude=exclude)
            if item is None:
                continue
            relics.append(item)
            exclude.add(str(item.item_id))
        return relics

    def _generate_courier_replacement_relic(self, *, exclude: set[str]) -> Any | None:
        from sts_py.engine.run.shop import roll_relic_tier

        if self.state.rng is None:
            return None
        replacement_exclude = {self._canonical_relic_id(relic_id) for relic_id in exclude}
        replacement_exclude.update(self._consumed_relic_ids(["common", "uncommon", "rare", "shop"]))
        replacement_exclude.update(
            {
                self._canonical_relic_id("OldCoin"),
                self._canonical_relic_id("SmilingMask"),
                self._canonical_relic_id("MawBank"),
                self._canonical_relic_id("TheCourier"),
            }
        )
        tier_key = roll_relic_tier(self.state.rng.merchant_rng)
        return self._generate_shop_relic_item(tier_key=tier_key, exclude=replacement_exclude)

    def _choose_random_relic_offer(self, relic_defs: list[Any], *, exclude: set[str], rng: MutableRNG | None) -> Any | None:
        candidates = [
            relic_def
            for relic_def in relic_defs
            if self._relic_matches_character(relic_def) and self._canonical_relic_id(relic_def.id) not in exclude
        ]
        if not candidates:
            return None
        if rng is not None:
            return candidates[rng.random_int(len(candidates) - 1)]
        return candidates[0]

    def _current_treasure_room_type(self) -> str:
        current = self.get_current_room()
        if current is not None and current.room_type == RoomType.TREASURE:
            return "TreasureRoom"
        return "TreasureRoom"

    def _ensure_current_treasure_room_history(self, *, main_relic_id: str | None) -> dict[str, Any]:
        history = getattr(self.state, "treasure_rooms", None)
        if not isinstance(history, list):
            history = []
        if history:
            latest = history[-1]
            if (
                int(latest.get("floor", -1)) == int(self.state.floor)
                and str(latest.get("room_type", "")) == self._current_treasure_room_type()
            ):
                if latest.get("main_relic_id") is None and main_relic_id is not None:
                    latest["main_relic_id"] = main_relic_id
                self.state.treasure_rooms = history
                return latest
        entry = {
            "floor": int(self.state.floor),
            "room_type": self._current_treasure_room_type(),
            "main_relic_id": main_relic_id,
            "obtained_relic_ids": [],
            "skipped_main_relic_id": None,
            "took_sapphire_key": False,
        }
        history.append(entry)
        self.state.treasure_rooms = history
        return entry

    def _roll_matryoshka_bonus_tiers(self) -> list[str]:
        rng = self.state.rng.relic_rng if self.state.rng is not None else None
        roll = rng.random_int(99) if rng is not None else 0
        if roll < 75:
            return ["COMMON", "UNCOMMON"]
        return ["UNCOMMON", "COMMON"]

    def _generate_boss_relic_choices(self, count: int = 3) -> list[str]:
        from sts_py.engine.content.relics import RelicTier, get_relic_pool

        rng = self.state.rng.relic_rng if self.state.rng is not None else None
        current_ids = self._current_relic_ids()
        consumed_ids = self._consumed_relic_ids(["boss"])
        pool = [
            relic_def
            for relic_def in get_relic_pool(
                RelicTier.BOSS,
                floor=self.state.floor,
                act=self.state.act,
                context="reward",
                owned_relics=self.state.relics,
                deck=self.state.deck,
            )
            if (
                self._relic_matches_character(relic_def)
                and self._canonical_relic_id(relic_def.id) not in current_ids
                and self._canonical_relic_id(relic_def.id) not in consumed_ids
            )
        ]
        choices: list[str] = []
        while pool and len(choices) < count:
            idx = rng.random_int(len(pool) - 1) if rng is not None else 0
            relic_def = pool.pop(idx)
            if relic_def.id in choices:
                continue
            choices.append(relic_def.id)
            self._mark_relic_consumed(relic_def.id, "boss")
        return choices

    def _generate_main_chest_relic(self, *, exclude: set[str]) -> str | None:
        from sts_py.engine.content.relics import RelicTier, get_relic_pool, roll_relic_rarity

        treasure_rng = self.state.rng.treasure_rng if self.state.rng is not None else None
        rarity = roll_relic_rarity(treasure_rng, source="chest").value
        ordered_tiers = [rarity, "COMMON", "UNCOMMON", "RARE"]
        seen: set[str] = set()
        for tier_name in ordered_tiers:
            if tier_name in seen:
                continue
            seen.add(tier_name)
            tier = RelicTier(tier_name)
            chosen = self._choose_random_relic_offer(
                get_relic_pool(
                    tier,
                    floor=self.state.floor,
                    act=self.state.act,
                    context="reward",
                    owned_relics=self.state.relics,
                    deck=self.state.deck,
                ),
                exclude=exclude,
                rng=treasure_rng,
            )
            if chosen is not None:
                self._mark_relic_consumed(chosen.id, tier_name.lower())
                return chosen.id
        return None

    def _generate_matryoshka_bonus_relics(self, *, exclude: set[str]) -> list[str]:
        from sts_py.engine.content.relics import RelicTier, get_relic_pool

        remaining_chests = int(self.state.relic_counters.get("Matryoshka", 0) or 0)
        if remaining_chests <= 0 or not self._has_relic("Matryoshka"):
            return []

        relic_rng = self.state.rng.relic_rng if self.state.rng is not None else None
        for tier_name in self._roll_matryoshka_bonus_tiers():
            tier = RelicTier(tier_name)
            chosen = self._choose_random_relic_offer(
                get_relic_pool(
                    tier,
                    floor=self.state.floor,
                    act=self.state.act,
                    context="reward",
                    owned_relics=self.state.relics,
                    deck=self.state.deck,
                ),
                exclude=exclude,
                rng=relic_rng,
            )
            if chosen is None:
                continue
            self.state.relic_counters["Matryoshka"] = max(0, remaining_chests - 1)
            self._mark_relic_consumed(chosen.id, tier_name.lower())
            return [chosen.id]
        return []

    def _set_post_treasure_phase(self) -> None:
        if self.state.pending_chest_relic_choices:
            self.state.phase = RunPhase.TREASURE
        else:
            self.state.phase = RunPhase.MAP

    def _enter_treasure(self) -> None:
        """Enter a treasure room and populate the pending chest reward surface."""
        self.state.pending_chest_relic_choices = []
        self.state.pending_treasure_relic = None
        self._apply_chest_open_effects()
        exclude = self._current_relic_ids()
        exclude.update(self._consumed_relic_ids(["common", "uncommon", "rare"]))
        bonus_relics = self._generate_matryoshka_bonus_relics(exclude=exclude)
        exclude.update(
            self._canonical_relic_id(relic_id) or str(relic_id)
            for relic_id in bonus_relics
        )
        main_relic = self._generate_main_chest_relic(exclude=exclude)
        self.state.pending_chest_relic_choices = [*bonus_relics]
        if main_relic is not None:
            self.state.pending_chest_relic_choices.append(main_relic)
            self.state.pending_treasure_relic = main_relic
        self._ensure_current_treasure_room_history(main_relic_id=main_relic)
        self.state.phase = RunPhase.TREASURE

    def take_treasure_relic(self, index: int | None = None) -> dict[str, Any]:
        if self.state.phase != RunPhase.TREASURE:
            return {"success": False, "reason": "not_in_treasure_room"}
        choices = list(self.state.pending_chest_relic_choices)
        if not choices:
            return {"success": False, "reason": "no_pending_treasure_relic"}
        if index is None:
            if len(choices) != 1:
                return {"success": False, "reason": "multiple_pending_treasure_relics"}
            index = 0
        if index < 0 or index >= len(choices):
            return {"success": False, "reason": "invalid_treasure_relic_index"}
        relic = choices.pop(index)
        treasure_entry = self._ensure_current_treasure_room_history(main_relic_id=self.state.pending_treasure_relic)
        self.state.pending_chest_relic_choices = choices
        acquired = self._acquire_relic(relic, source=RelicSource.TREASURE, record_pending=True)
        obtained_relic_ids = treasure_entry.setdefault("obtained_relic_ids", [])
        obtained_relic_ids.append(acquired)
        if relic == self.state.pending_treasure_relic:
            self.state.pending_treasure_relic = None
        self._set_post_treasure_phase()
        return {
            "success": True,
            "action": "took_relic",
            "relic_id": acquired,
            "remaining_relics": list(self.state.pending_chest_relic_choices),
        }

    def take_sapphire_key(self) -> dict[str, Any]:
        if self.state.phase != RunPhase.TREASURE:
            return {"success": False, "reason": "not_in_treasure_room"}
        if self.state.sapphire_key_obtained:
            return {"success": False, "reason": "sapphire_key_already_obtained"}
        if not self.state.pending_treasure_relic:
            return {"success": False, "reason": "no_pending_treasure_relic"}
        skipped_relic = self.state.pending_treasure_relic
        treasure_entry = self._ensure_current_treasure_room_history(main_relic_id=skipped_relic)
        self.state.sapphire_key_obtained = True
        self.state.pending_chest_relic_choices = [
            relic_id for relic_id in self.state.pending_chest_relic_choices if relic_id != skipped_relic
        ]
        self.state.pending_treasure_relic = None
        treasure_entry["skipped_main_relic_id"] = skipped_relic
        treasure_entry["took_sapphire_key"] = True
        self._set_post_treasure_phase()
        return {
            "success": True,
            "action": "took_sapphire_key",
            "skipped_relic": skipped_relic,
            "remaining_relics": list(self.state.pending_chest_relic_choices),
        }

    def choose_boss_relic(self, index: int) -> dict[str, Any]:
        if self.state.phase != RunPhase.VICTORY:
            return {"success": False, "reason": "not_in_boss_relic_phase"}
        choices = list(self.state.pending_boss_relic_choices)
        if not choices:
            return {"success": False, "reason": "no_pending_boss_relic_choices"}
        if index < 0 or index >= len(choices):
            return {"success": False, "reason": "invalid_boss_relic_index"}

        relic_id = choices[index]
        not_picked = [candidate for idx, candidate in enumerate(choices) if idx != index]
        self.state.pending_boss_relic_choices = []
        self.state.boss_relic_choices.append({
            "floor": int(self.state.floor),
            "picked_relic_id": relic_id,
            "not_picked_relic_ids": not_picked,
            "skipped": False,
        })
        self._acquire_relic(relic_id, source=RelicSource.BOSS, record_pending=False)

        if self._has_pending_reward_surface():
            self._resume_victory_after_reward = True
            self.state.phase = RunPhase.REWARD
        else:
            self.state.phase = RunPhase.VICTORY

        return {
            "success": True,
            "action": "picked_boss_relic",
            "relic_id": relic_id,
            "not_picked": not_picked,
        }

    def skip_boss_relic_choice(self) -> dict[str, Any]:
        if self.state.phase != RunPhase.VICTORY:
            return {"success": False, "reason": "not_in_boss_relic_phase"}
        if not self.state.pending_boss_relic_choices:
            return {"success": False, "reason": "no_pending_boss_relic_choices"}
        skipped = list(self.state.pending_boss_relic_choices)
        self.state.pending_boss_relic_choices = []
        self.state.boss_relic_choices.append({
            "floor": int(self.state.floor),
            "picked_relic_id": None,
            "not_picked_relic_ids": skipped,
            "skipped": True,
        })
        self.state.phase = RunPhase.VICTORY
        return {"success": True, "action": "skipped_boss_relic", "skipped_choices": skipped}

    def end_combat(self) -> None:
        if self.state.combat is None:
            return

        combat = self.state.combat
        self.state.player_hp = combat.state.player.hp
        self.state.player_max_hp = combat.state.player.max_hp
        self.state.player_relic_attack_counters = dict(
            getattr(combat.state.player, "_relic_attack_counters", {}) or {}
        )
        if self.state.player_hp > self.state.player_max_hp:
            self.state.player_hp = self.state.player_max_hp

        if self.player_won_combat():
            heal_from_relics = combat.trigger_victory_effects()
            if heal_from_relics > 0:
                self.state.player_hp = min(self.state.player_max_hp, self.state.player_hp + heal_from_relics)
            self._apply_post_combat_relic_effects()

            current = self.get_current_room()
            room_type_str = None
            if current is not None:
                room_type_map = {
                    RoomType.MONSTER: "MonsterRoom",
                    RoomType.ELITE: "MonsterRoomElite",
                    RoomType.BOSS: "MonsterRoomBoss",
                }
                room_type_str = room_type_map.get(current.room_type)
            summary_monster_view = _combat_summary_monster_view(combat)
            if summary_monster_view is None:
                monster_ids = [m.id for m in combat.state.monsters]
                monster_end_hp = [m.hp for m in combat.state.monsters]
            else:
                monster_ids, monster_end_hp = summary_monster_view

            self.state.combat_history.append({
                "floor": self.state.floor,
                "room_type": room_type_str,
                "monster_ids": monster_ids,
                "turns": combat.state.turn,
                "player_end_hp": self.state.player_hp,
                "monster_end_hp": monster_end_hp,
                "rng": None,
                "enemies": monster_ids,
                "damage": combat.get_total_damage_taken(),
            })
            event_combat = self._get_current_event_combat()
            grant_standard_rewards = event_combat is None or bool(event_combat.get("grant_standard_rewards"))

            if grant_standard_rewards:
                self._generate_gold_reward(current)
                if combat.state.pending_bonus_gold > 0:
                    self.state.player_gold += combat.state.pending_bonus_gold
                    self._pending_gold_reward += combat.state.pending_bonus_gold
                self._try_potion_drop()
                if current is None or current.room_type != RoomType.BOSS:
                    self._add_card_reward(
                        current_room=current,
                        is_event_combat=event_combat is not None,
                    )
                self._try_relic_drop(current)

            self._resolve_event_combat_rewards()

            if current is not None and current.room_type == RoomType.ELITE and current.burning_elite:
                self.state.emerald_key_obtained = True

            if current is not None and current.room_type == RoomType.BOSS:
                self.state.phase = RunPhase.VICTORY
                if self.state.act == 4:
                    self._clear_pending_campaign_state()
                    self._record_standard_run_profile_outcome(victory=True)
                elif self.state.act == 3 and not self.has_all_act4_keys():
                    self._clear_pending_campaign_state()
                    self._record_standard_run_profile_outcome(victory=True)
                else:
                    self.state.pending_boss_relic_choices = self._generate_boss_relic_choices(3)
                if self.state.act == 3 and self.has_all_act4_keys() and not self.state.pending_boss_relic_choices:
                    self._clear_pending_campaign_state()
                    self.transition_to_next_act()
            elif event_combat is not None and event_combat.get("reopen_event"):
                reopen_event = dict(event_combat.get("reopen_event") or {})
                self.state.combat = None
                self._clear_current_event_combat()
                self._resume_event_from_state(
                    str(reopen_event.get("event_key", "") or ""),
                    dict(reopen_event.get("event_state") or {}),
                )
                return
            else:
                self.state.phase = RunPhase.REWARD if self._has_pending_reward_surface() else RunPhase.MAP
        else:
            self.state.phase = RunPhase.GAME_OVER
            self._record_standard_run_profile_outcome(victory=False)

        self.state.combat = None
        self._clear_current_event_combat()

    def _generate_gold_reward(self, current_room: MapNode | None) -> None:
        """Generate gold reward after combat victory."""
        if self.state.rng is None:
            base_gold = 15
        else:
            base_gold = self.state.rng.treasure_rng.random_int_between(10, 20)

        is_elite_combat = False
        if current_room is not None:
            if current_room.room_type == RoomType.ELITE:
                is_elite_combat = True
            elif current_room.room_type == RoomType.BOSS:
                base_gold += 50

        event_combat = self._get_current_event_combat()
        if event_combat is not None and event_combat.get("is_elite_combat"):
            is_elite_combat = True

        if is_elite_combat:
            base_gold += self.state.rng.treasure_rng.random_int_between(15, 20) if self.state.rng else 25

        self.state.player_gold += base_gold
        self._pending_gold_reward = base_gold

    def _try_potion_drop(self) -> None:
        """Try to drop a potion after combat based on current drop chance.

        Default 40% chance. If potion drops, chance decreases by 10%.
        If no potion drops, chance increases by 10%.
        Potion rarity: 65% COMMON, 25% UNCOMMON, 10% RARE.
        """
        if self.state.rng is None:
            return

        roll = self.state.rng.potion_rng.random_int(99)
        if roll < self.state.potion_drop_chance:
            from sts_py.engine.combat.potion_effects import roll_potion_rarity, get_random_potion_by_rarity
            rarity = roll_potion_rarity()
            potion = get_random_potion_by_rarity(rarity, self.state.character_class)
            if potion and self.gain_potion(potion.potion_id):
                self._pending_potion_reward = potion.potion_id
                self.state.potion_drop_chance = max(0, self.state.potion_drop_chance - 10)
        else:
            self.state.potion_drop_chance = min(100, self.state.potion_drop_chance + 10)

    def _try_relic_drop(self, current_room) -> None:
        """Try to drop a relic after combat.

        Relic drop chance varies by room type:
        - Monster (普通战斗): No relic drop
        - Elite (精英战斗): 10% chance
        - Boss (Boss战斗): 100% guaranteed
        - Event combat (事件战斗): No random drop, but bonus relic may be granted

        Relic rarity (3:2:1 ratio):
        - COMMON: 50%
        - UNCOMMON: 33%
        - RARE: 17%
        """
        if current_room is None:
            return

        if current_room.room_type == RoomType.MONSTER:
            return

        if current_room.room_type == RoomType.ELITE:
            drop_count = 2 if self._has_relic("BlackStar") else 1
        else:
            return

        for _ in range(drop_count):
            self._grant_random_relic(source=RelicSource.ELITE, record_pending=True)

    def _resolve_event_combat_rewards(self) -> None:
        event_combat = self._get_current_event_combat()
        if event_combat is None or event_combat.get("rewards_resolved"):
            return

        bonus_reward = event_combat.get("bonus_reward")
        if bonus_reward and bonus_reward not in self.state.relics:
            self._acquire_relic(bonus_reward, source=RelicSource.EVENT, record_pending=True)

        pending_rewards = list(event_combat.get("pending_event_rewards") or [])
        for reward_type in pending_rewards:
            if reward_type == "gold":
                self.state.player_gold += 30
                self._pending_gold_reward += 30
            elif isinstance(reward_type, str) and reward_type.startswith("gold:"):
                amount = int(str(reward_type).split(":", 1)[1] or 0)
                self.state.player_gold += amount
                self._pending_gold_reward += amount
            elif isinstance(reward_type, str) and reward_type.startswith("gold_range:"):
                _, low, high = str(reward_type).split(":", 2)
                low_int = int(low or 0)
                high_int = int(high or low_int)
                amount = self._misc_rng().random_int_between(low_int, high_int) if self._misc_rng() is not None else low_int
                self.state.player_gold += amount
                self._pending_gold_reward += amount
            elif reward_type == "relic":
                self._grant_random_relic(source=RelicSource.EVENT)
            elif isinstance(reward_type, str) and reward_type.startswith("relic_id:"):
                relic_id = str(reward_type).split(":", 1)[1]
                self._acquire_relic(relic_id, source=RelicSource.EVENT, record_pending=True)
            elif isinstance(reward_type, str) and reward_type.startswith("relic_tier:"):
                tier_name = str(reward_type).split(":", 1)[1]
                relic_id = self._draw_random_relic_of_tier(tier_name)
                if relic_id is not None:
                    self._acquire_relic(relic_id, source=RelicSource.EVENT, record_pending=True)

        event_combat["bonus_reward"] = None
        event_combat["pending_event_rewards"] = []
        event_combat["rewards_resolved"] = True

    def smith(self, card_idx: int) -> bool:
        if self.state.phase != RunPhase.REST:
            return False
            
        if 0 <= card_idx < len(self.state.deck):
            card_id = self.state.deck[card_idx]
            upgraded_card = self._upgrade_card(card_id)
            if upgraded_card is not None:
                self.state.deck[card_idx] = upgraded_card
                
        self.state.phase = RunPhase.MAP
        return True

    def recall(self) -> bool:
        if self.state.phase != RunPhase.REST:
            return False
        if self.state.ruby_key_obtained:
            return False
        self.state.ruby_key_obtained = True
        self.state.phase = RunPhase.MAP
        return True

    def lift(self) -> int:
        if self.state.phase != RunPhase.REST:
            return 0
        return self.rest(heal_percent=0.3)

    def gain_potion(self, potion_id: str) -> bool:
        if self._has_relic("Sozu"):
            return False
        for i in range(len(self.state.potions)):
            if self.state.potions[i] == "EmptyPotionSlot":
                self.state.potions[i] = potion_id
                return True
        return False

    def use_potion(self, potion_idx: int, target_idx: int = 0) -> bool:
        if potion_idx < 0 or potion_idx >= len(self.state.potions):
            return False

        potion_id = self.state.potions[potion_idx]
        if potion_id == "EmptyPotionSlot":
            return False

        from sts_py.engine.content.potions import POTION_DEFINITIONS
        from sts_py.engine.combat.potion_effects import use_potion as execute_potion_effect

        potion_def = POTION_DEFINITIONS.get(potion_id)
        if potion_def is None:
            return False

        combat = self.state.combat

        if combat is None:
            if potion_id == "FruitJuice":
                self.state.player_max_hp += 5
                self.state.player_hp += 5
                self.state.potions[potion_idx] = "EmptyPotionSlot"
                return True
            return False

        potion = potion_def.create_potion()
        execute_potion_effect(potion, combat.state, target_idx)
        self.state.potions[potion_idx] = "EmptyPotionSlot"
        return True

    def _upgrade_card(self, card_id: str) -> str | None:
        from sts_py.engine.content.card_instance import CardInstance, format_runtime_card_id
        from sts_py.engine.content.cards_min import ALL_CARD_DEFS, CardType

        card = CardInstance(card_id)
        if card.card_id == "SearingBlow":
            return format_runtime_card_id("SearingBlow", times_upgraded=card.times_upgraded + 1)
        if card.card_id == "RitualDagger":
            if card.upgraded:
                return None
            return format_runtime_card_id("RitualDagger", upgraded=True, misc=card.misc)
        if card.card_id == "GeneticAlgorithm":
            if card.upgraded:
                return None
            return format_runtime_card_id("GeneticAlgorithm", upgraded=True, misc=card.misc)

        base_id = card.card_id
        if base_id not in ALL_CARD_DEFS:
            return None
        card_def = ALL_CARD_DEFS[base_id]
        if card_def.card_type in (CardType.STATUS, CardType.CURSE):
            return None
        if card.upgraded:
            return None
        return base_id + "+"
