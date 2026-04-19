from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
try:
    from typing import Dict, List, Tuple, Type, Union
except ImportError:
    Dict = dict
    List = list
    Tuple = tuple
    Type = type
    Union = object

from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.combat.card_effects import (
    _apply_poison_to_monster,
    _find_card_by_uuid,
    get_card_effects,
    _move_hand_card_to_exhaust,
    _resolve_generated_choice_to_hand,
    _move_selected_hand_card_to_draw_pile,
    _refresh_hand_multi_pick_options,
    _resolve_discovery_choice,
    _resolve_draw_pile_card_to_hand_or_discard,
    _trigger_exhaust_hooks,
    execute_card,
)
from sts_py.engine.combat.card_piles import CardManager
from sts_py.engine.combat.combat_state import CombatState, CombatPhase, Player
from sts_py.engine.combat.stance import NEUTRAL_STANCE, StanceType, change_stance
from sts_py.engine.content.card_instance import CardInstance, create_starter_deck
from sts_py.engine.monsters.monster_base import MonsterBase

UNREMOVABLE_CARDS = {"Necronomicurse", "CurseOfTheBell"}
UNTRANSFORMABLE_CARDS = {"Necronomicurse", "CurseOfTheBell"}
BOTTLED_CARDS = set()
from sts_py.engine.monsters.exordium import (
    JawWorm,
    LouseRed,
    LouseGreen,
    AcidSlimeSmall,
    AcidSlimeMedium,
    AcidSlimeLarge,
    SpikeSlimeSmall,
    SpikeSlimeMedium,
    SpikeSlimeLarge,
    GremlinFat,
    GremlinWar,
    GremlinShield,
    GremlinSneaky,
    GremlinWizard,
    LouseDefensive,
    Cultist,
    SlaverRed,
    SlaverBlue,
    Looter,
    Mugger,
    GremlinNob,
    Lagavulin,
    Sentry,
    FungiBeast,
)
from sts_py.engine.monsters.bosses import (
    Hexaghost, SlimeBoss, TheGuardian,
    Champ, Collector, Automaton,
    AwakenedOne, TimeEater, DonuAndDeca, Deca, Donu, BronzeOrb, TorchHead,
)
from sts_py.engine.monsters.city_beyond import (
    BanditBear,
    BanditLeader,
    BanditPointy,
    BookOfStabbing,
    Byrd,
    Centurion,
    Chosen,
    Darkling,
    Exploder,
    GremlinLeader,
    GiantHead,
    Healer,
    Maw,
    Nemesis,
    OrbWalker,
    Reptomancer,
    Repulsor,
    ShellParasite,
    SnakeDagger,
    SnakePlant,
    Snecko,
    Spiker,
    SpireGrowth,
    SphericGuardian,
    Taskmaster,
    Transient,
    WrithingMass,
)
from sts_py.engine.monsters.ending import CorruptHeart, SpireShield, SpireSpear

if TYPE_CHECKING:
    pass


EncounterSpec = Tuple[Type[MonsterBase], Dict[str, Any]]

WeakEncounterType = Tuple[str, Union[List[EncounterSpec], str], int]

WEAK_ENCOUNTER_TEMPLATES_ACT1: list[WeakEncounterType] = [
    ("Cultist", [(Cultist, {})], 1),
    ("Jaw Worm", [(JawWorm, {})], 1),
    ("2 Louse", "TWO_LOUSE", 1),
    ("Slimes", [(AcidSlimeMedium, {}), (SpikeSlimeSmall, {})], 1),
]

SLIME_ENCOUNTERS: list[EncounterSpec] = [
    [(AcidSlimeMedium, {}), (SpikeSlimeSmall, {})],
    [(AcidSlimeSmall, {}), (SpikeSlimeMedium, {})],
]

LARGE_SLIME_ENCOUNTERS: list[EncounterSpec] = [
    [(AcidSlimeLarge, {})],
    [(SpikeSlimeLarge, {})],
]

GREMLIN_POOL: list[Type[MonsterBase]] = [
    GremlinWar, GremlinWar,
    GremlinSneaky, GremlinSneaky,
    GremlinFat, GremlinFat,
    GremlinShield,
    GremlinWizard,
]

def generate_gremlin_gang(rng) -> list[EncounterSpec]:
    """Generate 4 random gremlins from pool without replacement."""
    pool = GREMLIN_POOL.copy()
    result = []
    for _ in range(4):
        idx = rng.random_int(len(pool) - 1)
        result.append((pool[idx], {}))
        pool.pop(idx)
    return result

LOUSE_POOL: list[Type[MonsterBase]] = [LouseRed, LouseDefensive]

def generate_three_louse(rng) -> list[EncounterSpec]:
    """Generate 3 random louse (red or green) from pool."""
    result = []
    for _ in range(3):
        idx = rng.random_int(len(LOUSE_POOL) - 1)
        result.append((LOUSE_POOL[idx], {}))
    return result

def generate_two_louse(rng) -> list[EncounterSpec]:
    """Generate 2 random louse (red or green) from pool."""
    result = []
    for _ in range(2):
        idx = rng.random_int(len(LOUSE_POOL) - 1)
        result.append((LOUSE_POOL[idx], {}))
    return result

WEAK_WILDLIFE_POOL: list[Type[MonsterBase]] = [
    LouseRed, LouseDefensive,
    SpikeSlimeMedium, AcidSlimeMedium,
]

STRONG_WILDLIFE_POOL: list[Type[MonsterBase]] = [
    FungiBeast, JawWorm,
]

STRONG_HUMANOID_POOL: list[Type[MonsterBase]] = [
    Cultist, SlaverRed, SlaverBlue, Looter,
]

def generate_exordium_thugs(rng) -> list[EncounterSpec]:
    """Generate Exordium Thugs: 1 weak wildlife + 1 strong humanoid."""
    weak_idx = rng.random_int(len(WEAK_WILDLIFE_POOL) - 1)
    strong_idx = rng.random_int(len(STRONG_HUMANOID_POOL) - 1)
    return [(WEAK_WILDLIFE_POOL[weak_idx], {}), (STRONG_HUMANOID_POOL[strong_idx], {})]

def generate_exordium_wildlife(rng) -> list[EncounterSpec]:
    """Generate Exordium Wildlife: 1 strong wildlife + 1 weak wildlife."""
    strong_idx = rng.random_int(len(STRONG_WILDLIFE_POOL) - 1)
    weak_idx = rng.random_int(len(WEAK_WILDLIFE_POOL) - 1)
    return [(STRONG_WILDLIFE_POOL[strong_idx], {}), (WEAK_WILDLIFE_POOL[weak_idx], {})]


def generate_small_slimes(rng: MutableRNG) -> list[EncounterSpec]:
    if rng.random_boolean():
        return [(SpikeSlimeSmall, {}), (AcidSlimeMedium, {})]
    return [(AcidSlimeSmall, {}), (SpikeSlimeMedium, {})]


def generate_large_slime(rng: MutableRNG) -> list[EncounterSpec]:
    if rng.random_boolean():
        return [(AcidSlimeLarge, {})]
    return [(SpikeSlimeLarge, {})]


def generate_lots_of_slimes(rng: MutableRNG) -> list[EncounterSpec]:
    pool: list[Type[MonsterBase]] = [SpikeSlimeSmall, SpikeSlimeSmall, SpikeSlimeSmall, AcidSlimeSmall, AcidSlimeSmall]
    result: list[EncounterSpec] = []
    while pool:
        idx = rng.random_int(len(pool) - 1)
        result.append((pool.pop(idx), {}))
    return result


def generate_three_byrds(_: MutableRNG) -> list[EncounterSpec]:
    return [(Byrd, {}), (Byrd, {}), (Byrd, {})]


def generate_four_byrds(_: MutableRNG) -> list[EncounterSpec]:
    return [(Byrd, {}), (Byrd, {}), (Byrd, {}), (Byrd, {})]


def generate_gremlin_leader(rng: MutableRNG) -> list[EncounterSpec]:
    return generate_gremlin_gang(rng)[:2] + [(GremlinLeader, {})]


def generate_shapes(rng: MutableRNG, count: int) -> list[EncounterSpec]:
    pool: list[Type[MonsterBase]] = [Repulsor, Repulsor, Exploder, Exploder, Spiker, Spiker]
    result: list[EncounterSpec] = []
    for _ in range(count):
        idx = rng.random_int(len(pool) - 1)
        result.append((pool.pop(idx), {}))
    return result


def generate_sphere_and_shapes(rng: MutableRNG) -> list[EncounterSpec]:
    return generate_shapes(rng, 2) + [(SphericGuardian, {})]


def generate_mysterious_sphere(rng: MutableRNG) -> list[EncounterSpec]:
    return generate_shapes(rng, 2) + [(OrbWalker, {})]


def generate_reptomancer_roster(_: MutableRNG) -> list[EncounterSpec]:
    return [(SnakeDagger, {}), (Reptomancer, {}), (SnakeDagger, {})]


def generate_flame_bruiser_one_orb(_: MutableRNG) -> list[EncounterSpec]:
    return [(Reptomancer, {}), (SnakeDagger, {})]

STRONG_ENCOUNTER_TEMPLATES_ACT1: list[tuple[str, list[EncounterSpec] | str, int]] = [
    ("Gremlin Gang", "GREMLIN_GANG", 2),
    ("Large Slime", [(AcidSlimeLarge, {})], 4),
    ("Lots of Slimes", [(AcidSlimeSmall, {}), (AcidSlimeSmall, {}), (SpikeSlimeSmall, {}), (SpikeSlimeSmall, {}), (SpikeSlimeSmall, {})], 2),
    ("Blue Slaver", [(SlaverBlue, {})], 4),
    ("Red Slaver", [(SlaverRed, {})], 2),
    ("3 Louse", "THREE_LOUSE", 4),
    ("2 Fungi Beasts", [(FungiBeast, {}), (FungiBeast, {})], 4),
    ("Exordium Thugs", "EXORDIUM_THUGS", 3),
    ("Exordium Wildlife", "EXORDIUM_WILDLIFE", 3),
    ("Looter", [(Looter, {})], 4),
]


WEAK_MONSTER_POOLS: dict[int, list[WeakEncounterType]] = {
    1: WEAK_ENCOUNTER_TEMPLATES_ACT1,
    2: [
        ("Spheric Guardian", [(SphericGuardian, {})], 2),
        ("Chosen", [(Chosen, {})], 2),
        ("Shell Parasite", [(ShellParasite, {})], 2),
        ("3 Byrds", "THREE_BYRDS", 2),
        ("2 Thieves", [(Looter, {}), (Mugger, {})], 2),
    ],
    3: [
        ("3 Darklings", [(Darkling, {}), (Darkling, {}), (Darkling, {})], 2),
        ("Orb Walker", [(OrbWalker, {})], 2),
        ("3 Shapes", "THREE_SHAPES", 2),
    ],
}

STRONG_MONSTER_POOLS: dict[int, list[tuple[str, list[EncounterSpec], int]]] = {
    1: STRONG_ENCOUNTER_TEMPLATES_ACT1,
    2: [
        ("Chosen and Byrds", [(Byrd, {}), (Chosen, {})], 2),
        ("Sentry and Sphere", [(Sentry, {}), (SphericGuardian, {})], 2),
        ("Snake Plant", [(SnakePlant, {})], 6),
        ("Snecko", [(Snecko, {})], 4),
        ("Centurion and Healer", [(Centurion, {}), (Healer, {})], 6),
        ("Cultist and Chosen", [(Cultist, {}), (Chosen, {})], 3),
        ("3 Cultists", [(Cultist, {}), (Cultist, {}), (Cultist, {})], 3),
        ("Shelled Parasite and Fungi", [(ShellParasite, {}), (FungiBeast, {})], 3),
    ],
    3: [
        ("Spire Growth", [(SpireGrowth, {})], 1),
        ("Transient", [(Transient, {})], 1),
        ("4 Shapes", "FOUR_SHAPES", 1),
        ("Maw", [(Maw, {})], 1),
        ("Sphere and 2 Shapes", "SPHERE_AND_TWO_SHAPES", 1),
        ("Jaw Worm Horde", [(JawWorm, {}), (JawWorm, {}), (JawWorm, {})], 1),
        ("3 Darklings", [(Darkling, {}), (Darkling, {}), (Darkling, {})], 1),
        ("Writhing Mass", [(WrithingMass, {})], 1),
    ],
}


def generate_random_encounter(
    act: int,
    is_elite: bool,
    hp_rng: "MutableRNG",
    ascension: int = 0,
) -> list[EncounterSpec]:
    """Generate a random monster encounter from pools.

    Args:
        act: Act number (1, 2, or 3)
        is_elite: If True, use strong pool; if False, use weak pool
        hp_rng: Random number generator for monster HP
        ascension: Ascension level (default 0)

    Returns:
        List of (monster_class, kwargs) tuples
    """
    pool = STRONG_MONSTER_POOLS.get(act, STRONG_MONSTER_POOLS[1]) if is_elite else WEAK_MONSTER_POOLS.get(act, WEAK_MONSTER_POOLS[1])

    total_weight = sum(item[2] for item in pool)
    roll = hp_rng.random_int(total_weight - 1)
    cumulative = 0
    for name, specs, weight in pool:
        cumulative += weight
        if roll < cumulative:
            encounter_name = name
            encounter_specs = specs
            break

    if encounter_name == "Large Slime":
        return generate_large_slime(hp_rng)
    if encounter_name == "Gremlin Gang":
        return generate_gremlin_gang(hp_rng)
    if encounter_name == "3 Louse":
        return generate_three_louse(hp_rng)
    if encounter_name in {"Slimes", "Small Slimes"}:
        return generate_small_slimes(hp_rng)
    if encounter_name == "2 Louse":
        return generate_two_louse(hp_rng)
    if encounter_name == "3 Byrds" or encounter_name == "THREE_BYRDS":
        return generate_three_byrds(hp_rng)
    if encounter_name == "3 Shapes" or encounter_name == "THREE_SHAPES":
        return generate_shapes(hp_rng, 3)
    if encounter_name == "4 Shapes" or encounter_name == "FOUR_SHAPES":
        return generate_shapes(hp_rng, 4)
    if encounter_name == "Sphere and 2 Shapes" or encounter_name == "SPHERE_AND_TWO_SHAPES":
        return generate_sphere_and_shapes(hp_rng)
    if encounter_name == "Exordium Thugs":
        return generate_exordium_thugs(hp_rng)
    if encounter_name == "Exordium Wildlife":
        return generate_exordium_wildlife(hp_rng)
    if encounter_name == "Lots of Slimes":
        return generate_lots_of_slimes(hp_rng)
    return encounter_specs


GENERATED_ENCOUNTER_BUILDERS: dict[str, callable] = {
    "2 Louse": generate_two_louse,
    "3 Louse": generate_three_louse,
    "Small Slimes": generate_small_slimes,
    "Large Slime": generate_large_slime,
    "Lots of Slimes": generate_lots_of_slimes,
    "Gremlin Gang": generate_gremlin_gang,
    "Exordium Thugs": generate_exordium_thugs,
    "Exordium Wildlife": generate_exordium_wildlife,
    "3 Byrds": generate_three_byrds,
    "4 Byrds": generate_four_byrds,
    "Gremlin Leader": generate_gremlin_leader,
    "Flame Bruiser 1 Orb": generate_flame_bruiser_one_orb,
    "Flame Bruiser 2 Orb": generate_reptomancer_roster,
    "Reptomancer": generate_reptomancer_roster,
    "3 Shapes": lambda rng: generate_shapes(rng, 3),
    "4 Shapes": lambda rng: generate_shapes(rng, 4),
    "Sphere and 2 Shapes": generate_sphere_and_shapes,
    "Mysterious Sphere": generate_mysterious_sphere,
}


MONSTER_ENCOUNTERS: dict[str, list[EncounterSpec]] = {
    "Cultist": [(Cultist, {})],
    "Jaw Worm": [(JawWorm, {})],
    "Blue Slaver": [(SlaverBlue, {})],
    "Red Slaver": [(SlaverRed, {})],
    "Looter": [(Looter, {})],
    "2 Fungi Beasts": [(FungiBeast, {}), (FungiBeast, {})],
    "Gremlin Nob": [(GremlinNob, {})],
    "Lagavulin": [(Lagavulin, {})],
    "3 Sentries": [(Sentry, {}), (Sentry, {}), (Sentry, {})],
    "Lagavulin Event": [(Lagavulin, {"asleep": False})],
    "The Mushroom Lair": [(FungiBeast, {}), (FungiBeast, {}), (FungiBeast, {})],
    "The Guardian": [(TheGuardian, {})],
    "Hexaghost": [(Hexaghost, {})],
    "Slime Boss": [(SlimeBoss, {})],
    "2 Thieves": [(Looter, {}), (Mugger, {})],
    "Chosen": [(Chosen, {})],
    "Shell Parasite": [(ShellParasite, {})],
    "Spheric Guardian": [(SphericGuardian, {})],
    "Cultist and Chosen": [(Cultist, {}), (Chosen, {})],
    "3 Cultists": [(Cultist, {}), (Cultist, {}), (Cultist, {})],
    "Chosen and Byrds": [(Byrd, {}), (Chosen, {})],
    "Sentry and Sphere": [(Sentry, {}), (SphericGuardian, {})],
    "Snake Plant": [(SnakePlant, {})],
    "Snecko": [(Snecko, {})],
    "Centurion and Healer": [(Centurion, {}), (Healer, {})],
    "Shelled Parasite and Fungi": [(ShellParasite, {}), (FungiBeast, {})],
    "Book of Stabbing": [(BookOfStabbing, {})],
    "Slavers": [(SlaverBlue, {}), (Taskmaster, {}), (SlaverRed, {})],
    "Masked Bandits": [(BanditPointy, {}), (BanditLeader, {}), (BanditBear, {})],
    "Colosseum Nobs": [(Taskmaster, {}), (GremlinNob, {})],
    "Colosseum Slavers": [(SlaverBlue, {}), (SlaverRed, {})],
    "Automaton": [(Automaton, {})],
    "Champ": [(Champ, {})],
    "Collector": [(Collector, {})],
    "Transient": [(Transient, {})],
    "3 Darklings": [(Darkling, {}), (Darkling, {}), (Darkling, {})],
    "Jaw Worm Horde": [(JawWorm, {}), (JawWorm, {}), (JawWorm, {})],
    "Snecko and Mystics": [(Healer, {}), (Snecko, {}), (Healer, {})],
    "Orb Walker": [(OrbWalker, {})],
    "Spire Growth": [(SpireGrowth, {})],
    "Maw": [(Maw, {})],
    "2 Orb Walkers": [(OrbWalker, {}), (OrbWalker, {})],
    "Nemesis": [(Nemesis, {})],
    "Writhing Mass": [(WrithingMass, {})],
    "Giant Head": [(GiantHead, {})],
    "Time Eater": [(TimeEater, {})],
    "Awakened One": [(Cultist, {}), (Cultist, {}), (AwakenedOne, {})],
    "Donu and Deca": [(Deca, {}), (Donu, {})],
    "Shield and Spear": [(SpireShield, {}), (SpireSpear, {})],
    "The Heart": [(CorruptHeart, {})],
    # Direct monster ids used by replay/event setup
    "Taskmaster": [(Taskmaster, {})],
    "BanditPointy": [(BanditPointy, {})],
    "BanditLeader": [(BanditLeader, {})],
    "BanditBear": [(BanditBear, {})],
    "SnakeDagger": [(SnakeDagger, {})],
    "SpireGrowth": [(SpireGrowth, {})],
}


@dataclass
class CombatEngine:
    state: CombatState
    ai_rng: MutableRNG
    hp_rng: MutableRNG
    relics: list[str] = field(default_factory=list)
    neow_blessing: bool = False

    @classmethod
    def create(
        cls,
        encounter_name: str,
        player_hp: int,
        player_max_hp: int,
        ai_rng: MutableRNG,
        hp_rng: MutableRNG,
        card_random_rng: MutableRNG | None = None,
        ascension: int = 0,
        deck: list[str] | None = None,
        relics: list[str] | None = None,
        neow_blessing: bool = False,
        persistent_relic_attack_counters: dict[str, int] | None = None,
        bottled_cards: dict[str, int] | None = None,
    ) -> "CombatEngine":
        encounter_specs = MONSTER_ENCOUNTERS.get(encounter_name)
        monsters: list[MonsterBase] = []

        if encounter_specs is not None:
            for monster_cls, kwargs in encounter_specs:
                monster = monster_cls.create(hp_rng, ascension, **kwargs)
                monsters.append(monster)
        elif encounter_name in GENERATED_ENCOUNTER_BUILDERS:
            encounter_specs = GENERATED_ENCOUNTER_BUILDERS[encounter_name](hp_rng)
            for monster_cls, kwargs in encounter_specs:
                monster = monster_cls.create(hp_rng, ascension, **kwargs)
                monsters.append(monster)
        else:
            from sts_py.engine.monsters.city_beyond import GenericMonsterProxy
            from sts_py.engine.monsters.monster_truth import get_monster_truth

            truth = get_monster_truth(encounter_name)
            if truth is not None and truth.combat_capable:
                raise ValueError(f"Missing explicit combat encounter mapping for official monster or encounter: {encounter_name}")
            
            act = 1
            if encounter_name in ["Automaton", "Collector", "Champ", "Chosen", "3 Byrds", "Spheric Guardian", "Shell Parasite", "2 Thieves", "Chosen and Byrds", "Sentry and Sphere", "Snake Plant", "Snecko", "Centurion and Healer", "Cultist and Chosen", "3 Cultists", "Shelled Parasite and Fungi", "Gremlin Leader", "Slavers", "Book of Stabbing"]: act = 2
            if encounter_name in ["Awakened One", "Time Eater", "Donu and Deca", "Bronze Automaton", "3 Darklings", "Orb Walker", "3 Shapes", "Spire Growth", "Transient", "4 Shapes", "Maw", "Sphere and 2 Shapes", "Jaw Worm Horde", "Writhing Mass", "Giant Head", "Nemesis", "Reptomancer"]: act = 3
                
            is_boss = encounter_name in ["Automaton", "Collector", "Champ", "Awakened One", "Time Eater", "Donu and Deca", "Bronze Automaton"]
            is_elite = encounter_name in ["Gremlin Leader", "Slavers", "Book of Stabbing", "Giant Head", "Nemesis", "Reptomancer"]
            
            monster = GenericMonsterProxy.create(hp_rng, ascension, act=act, is_elite=is_elite, is_boss=is_boss, name_proxy=encounter_name)
            monsters.append(monster)

        player = Player(hp=player_hp, max_hp=player_max_hp)
        player.stance = NEUTRAL_STANCE
        player._stance = None
        player.relics = list(relics or [])
        player._relic_attack_counters = {
            str(relic_id): max(0, int(counter))
            for relic_id, counter in (persistent_relic_attack_counters or {}).items()
        }
        combat_deck = deck if deck is not None else [card.card_id for card in create_starter_deck()]
        card_manager = CardManager.create(combat_deck, ai_rng)
        card_manager.set_energy(player.energy)
        card_manager.set_max_energy(player.max_energy)
        state = CombatState(player=player, monsters=monsters, card_manager=card_manager)
        state.card_random_rng = card_random_rng
        state.bottled_cards = dict(bottled_cards or {})
        player._combat_state = state
        card_manager._combat_state = state
        state.rng = hp_rng
        for monster in monsters:
            monster.state = state
            monster._combat_state = state

        engine = cls(state=state, ai_rng=ai_rng, hp_rng=hp_rng, relics=relics or [], neow_blessing=neow_blessing)
        state.engine = engine
        engine._init_combat()
        return engine

    @classmethod
    def create_with_monsters(
        cls,
        monsters: list["MonsterBase"],
        player_hp: int,
        player_max_hp: int,
        ai_rng: "MutableRNG",
        hp_rng: "MutableRNG",
        card_random_rng: MutableRNG | None = None,
        ascension: int = 0,
        deck: list[str] | None = None,
        relics: list[str] | None = None,
        pending_tea_energy: int = 0,
        persistent_relic_attack_counters: dict[str, int] | None = None,
        bottled_cards: dict[str, int] | None = None,
    ) -> "CombatEngine":
        from sts_py.engine.combat.card_piles import CardManager
        from sts_py.engine.combat.combat_state import Player
        from sts_py.engine.content.card_instance import create_starter_deck

        player = Player(hp=player_hp, max_hp=player_max_hp)
        player.stance = NEUTRAL_STANCE
        player._stance = None
        player.relics = list(relics or [])
        player.pending_tea_energy = pending_tea_energy
        player._relic_attack_counters = {
            str(relic_id): max(0, int(counter))
            for relic_id, counter in (persistent_relic_attack_counters or {}).items()
        }
        combat_deck = deck if deck is not None else [card.card_id for card in create_starter_deck()]
        card_manager = CardManager.create(combat_deck, ai_rng)
        card_manager.set_energy(player.energy)
        card_manager.set_max_energy(player.max_energy)
        state = CombatState(player=player, monsters=monsters, card_manager=card_manager)
        state.card_random_rng = card_random_rng
        state.bottled_cards = dict(bottled_cards or {})
        player._combat_state = state
        card_manager._combat_state = state
        state.rng = hp_rng
        for monster in monsters:
            monster.state = state
            monster._combat_state = state

        engine = cls(state=state, ai_rng=ai_rng, hp_rng=hp_rng, relics=relics or [])
        state.engine = engine
        engine._init_combat()
        return engine

    def _init_combat(self) -> None:
        from sts_py.engine.combat.powers import VulnerablePower, WeakPower
        VulnerablePower.EFFECTIVENESS = 1.5
        WeakPower.EFFECTIVENESS = 0.75

        self._bind_player_orbs()
        self._prepare_bottled_cards_for_opening_hand()

        start_with_energy_bonus = self._get_start_with_energy_bonus()
        if start_with_energy_bonus > 0:
            self.state.player.max_energy += start_with_energy_bonus
            self.state.player.energy = self.state.player.max_energy

        self.state.player.powers.set_context("player", getattr(self.state.player, "id", "player"))

        for monster in self.state.monsters:
            monster.state = self.state
            monster.powers.set_context("monster", monster.id)
            if hasattr(monster, "use_pre_battle_action"):
                monster.use_pre_battle_action()
            monster.roll_move(self.ai_rng)
        self._sync_surrounded_back_attack_state()

        if self.neow_blessing:
            for monster in self.state.monsters:
                monster.hp = 1
                monster.max_hp = 1

        self._trigger_relic_effects("at_battle_start")

        if self.state.card_manager is not None:
            self.state.card_manager.set_max_energy(self.state.player.max_energy)
            draw_count = 5 + int(getattr(self.state.player, "_draw_per_turn_bonus", 0) or 0)
            self.state.card_manager.start_turn(draw_count=draw_count, rng=self.ai_rng)
            self.state.player.energy = self.state.player.max_energy
            self.state.card_manager.set_energy(self.state.player.energy)

        self._trigger_relic_effects("at_battle_start_energy")

        start_shivs = int(getattr(self.state.player, "_start_shivs", 0) or 0)
        if start_shivs > 0 and self.state.card_manager is not None:
            self.state.card_manager.generate_cards_to_hand("Shiv", start_shivs)
            self.state.player._start_shivs = 0

        self.state.player._first_attack_triggered = False
        self.state.player._first_attack_bonus_damage = 0
        if not hasattr(self.state.player, "_relic_attack_counters"):
            self.state.player._relic_attack_counters = {}
        if not hasattr(self.state.player, "_attack_counter"):
            self.state.player._attack_counter = 0
        self.state.player._has_attacked_this_turn = False
        self.state.player._first_discard_triggered_this_turn = False
        self.state.player._discards_this_turn = 0
        self.state.player._discards_this_combat = 0
        self.state.player._power_cards_played_this_combat = 0
        self.state.player._next_attack_double = False
        self.state.player._double_attack_damage_turns = 0
        self.state.player._normality_locked = False

        self._trigger_relic_effects("first_attack_combat")

        self._apply_vulnerable_weak_modifiers()
        self._apply_strike_modifiers()

        if self.state.player.pending_tea_energy > 0:
            self.state.player.energy += self.state.player.pending_tea_energy
            self.state.player.pending_tea_energy = 0
            if self.state.card_manager is not None:
                self.state.card_manager.set_energy(self.state.player.energy)

        self.state.phase = CombatPhase.PLAYER_TURN

    def _prepare_bottled_cards_for_opening_hand(self) -> None:
        card_manager = self.state.card_manager
        if card_manager is None:
            return
        bottled_cards = getattr(self.state, "bottled_cards", None)
        if not isinstance(bottled_cards, dict) or not bottled_cards:
            return
        bottled_indexes: set[int] = set()
        for raw_index in bottled_cards.values():
            try:
                bottled_indexes.add(int(raw_index))
            except (TypeError, ValueError):
                continue
        if not bottled_indexes:
            return
        for card in card_manager.draw_pile.cards:
            master_index = getattr(card, "_master_deck_index", None)
            if master_index in bottled_indexes:
                card.is_innate = True

    def _bind_player_orbs(self) -> None:
        player = self.state.player
        if not hasattr(player, "orbs") or player.orbs is None:
            from sts_py.engine.combat.orbs import OrbSlots

            player.orbs = OrbSlots()
        if not hasattr(player, "max_orbs"):
            player.max_orbs = 3
        if not hasattr(player, "_frost_orbs_channeled_this_combat"):
            player._frost_orbs_channeled_this_combat = 0
        player.orbs.owner = player
        player.orbs.combat_state = self.state
        player.orbs.slots = int(getattr(player, "max_orbs", 3) or 0)

    def _channel_orb(self, orb: Any) -> None:
        self._bind_player_orbs()
        self.state.player.orbs.channel(orb)
        self._process_monster_deaths_after_card_resolution()

    def _trigger_player_orb_passives(self) -> None:
        self._bind_player_orbs()
        self.state.player.orbs.trigger_passives()
        self._process_monster_deaths_after_card_resolution()

    def _trigger_player_start_of_turn_orbs(self) -> None:
        self._bind_player_orbs()
        self.state.player.orbs.trigger_start_of_turn_effects()
        if self.state.card_manager is not None:
            self.state.card_manager.set_energy(self.state.player.energy)
        self._process_monster_deaths_after_card_resolution()

    def _get_start_with_energy_bonus(self) -> int:
        from sts_py.engine.content.relics import RelicEffectType, get_relic_by_id

        bonus = 0
        for relic_id in self.relics:
            relic_def = get_relic_by_id(relic_id)
            if relic_def is None:
                continue
            for effect in relic_def.effects:
                if effect.effect_type == RelicEffectType.START_WITH_ENERGY:
                    bonus += int(effect.value)
        return bonus

    def _has_relic(self, canonical_id: str) -> bool:
        from sts_py.engine.content.relics import get_relic_by_id

        for relic_id in self.relics:
            relic_def = get_relic_by_id(relic_id)
            if relic_def is not None and relic_def.id == canonical_id:
                return True
        return False

    def _single_every_n_attacks_self_relic_id(self) -> str | None:
        from sts_py.engine.content.relics import RelicEffectType, get_relic_by_id

        matching_ids: list[str] = []
        for relic_id in self.relics:
            relic_def = get_relic_by_id(relic_id)
            if relic_def is None:
                continue
            if any(effect.effect_type == RelicEffectType.EVERY_N_ATTACKS_SELF for effect in relic_def.effects):
                matching_ids.append(str(relic_id))
        if len(matching_ids) == 1:
            return matching_ids[0]
        return None

    def _spawn_innate_curses(self) -> None:
        """Spawn innate curse cards at battle start.

        Pride and Writhe are innate curses that start in hand IF they are in the player's deck.
        Only adds one copy if not already in hand.
        Also handles INNATE_COPY_AT_END for Pride.
        """
        from sts_py.engine.content.card_instance import CardInstance
        from sts_py.engine.content.cards_min import IRONCLAD_CURSE_DEFS

        hand_ids = [card.card_id for card in self.state.card_manager.hand.cards]

        for card_id, card_def in IRONCLAD_CURSE_DEFS.items():
            if card_def.is_innate and card_def.card_type.value == "CURSE":
                if card_id not in hand_ids:
                    card = CardInstance(card_id)
                    self.state.card_manager.hand.cards.append(card)

    def _apply_vulnerable_weak_modifiers(self) -> None:
        """Apply relic modifiers to Vulnerable and Weak power effectiveness.

        Paper Crane: Silent relic - Weak effect from 25% reduction to 40% reduction
          - Default Weak effectiveness = 0.75 (25% reduction)
          - Paper Crane makes it 0.60 (40% reduction)

        Paper Frog: Ironclad relic - Vulnerable effect from 50% increase to 75% increase
          - Default Vulnerable effectiveness = 1.5 (50% increase)
          - Paper Frog makes it 1.75 (75% increase)
        """
        from sts_py.engine.content.relics import get_relic_by_id
        from sts_py.engine.combat.powers import VulnerablePower, WeakPower

        player_vulnerable_mod = 1.5
        monster_vulnerable_mod = 1.5
        player_weak_mod = 0.75
        monster_weak_mod = 0.75
        paper_crane_keys = {"papercrane", "纸鹤", "绾搁工"}
        paper_frog_keys = {"paperfrog", "纸蛙", "绾歌洐"}
        odd_mushroom_keys = {"oddmushroom", "奇怪蘑菇", "鍓囨瘨鑻戣弴"}

        for relic_id in self.relics:
            raw_relic_key = str(relic_id or "").strip().replace(" ", "").replace("_", "").lower()
            relic_def = get_relic_by_id(relic_id)
            relic_key = str(getattr(relic_def, "id", relic_id) or "").strip().replace(" ", "").replace("_", "").lower()
            relic_name_key = str(getattr(relic_def, "name", "") or "").strip().replace(" ", "").replace("_", "").lower()
            relic_keys = {raw_relic_key, relic_key, relic_name_key}

            if relic_def is None:
                if relic_keys & paper_crane_keys:
                    player_weak_mod = 0.60
                elif relic_keys & paper_frog_keys:
                    monster_vulnerable_mod = 1.75
                elif relic_keys & odd_mushroom_keys:
                    player_vulnerable_mod = 1.25
                continue

            for effect in relic_def.effects:
                if effect.effect_type.value == "modify_weak":
                    if relic_keys & paper_crane_keys:
                        player_weak_mod = 1.0 - (effect.value / 100.0)
                elif effect.effect_type.value == "modify_vulnerable":
                    if relic_keys & paper_frog_keys:
                        monster_vulnerable_mod = 1.0 + (effect.value / 100.0)
                    elif relic_keys & odd_mushroom_keys:
                        player_vulnerable_mod = 1.0 + (effect.value / 100.0)

        VulnerablePower.PLAYER_EFFECTIVENESS = player_vulnerable_mod
        VulnerablePower.MONSTER_EFFECTIVENESS = monster_vulnerable_mod
        WeakPower.PLAYER_EFFECTIVENESS = player_weak_mod
        WeakPower.MONSTER_EFFECTIVENESS = monster_weak_mod

    def _apply_strike_modifiers(self) -> None:
        """Apply Strike card damage modifiers from relics.

        Strike Dummy: All cards with 'Strike' in the name deal +3 damage.
        """
        from sts_py.engine.content.relics import get_relic_by_id

        strike_bonus = 0
        for relic_id in self.relics:
            relic_def = get_relic_by_id(relic_id)
            if relic_def is None:
                continue

            for effect in relic_def.effects:
                if effect.effect_type.value == "modify_strike":
                    strike_bonus += effect.value

        self.state.player._strike_bonus_damage = strike_bonus

    def play_card(self, card_index: int, target_idx: int | None = None) -> bool:
        if self.state.phase != CombatPhase.PLAYER_TURN:
            return False
        if self.state.card_manager is None:
            return False
        if self.state.pending_combat_choice is not None:
            return False

        card = self.state.card_manager.get_card_in_hand(card_index)
        if card is None:
            return False
        if card.is_attack() and self.state.player.powers.has_power("Entangled"):
            return False
        self._apply_runtime_card_play_modifiers(card)
        active_player_powers = list(self.state.player.powers.powers) if card.is_power() else None
        card._existing_power_ids_before_play = {power.id for power in self.state.player.powers.powers}

        if getattr(self.state.player, '_normality_locked', False):
            cards_played = len(self.state.cards_played_this_turn)
            normality_limit = getattr(self.state.player, '_normality_limit', 3)
            if cards_played >= normality_limit:
                return False
        cards_play_limit = int(getattr(self.state.player, "_cards_play_limit", 0) or 0)
        if cards_play_limit > 0 and len(self.state.cards_played_this_turn) >= cards_play_limit:
            return False

        if card.is_unplayable and card.card_type.value in ("CURSE", "STATUS"):
            if not self._has_curse_playable_relic():
                return False
            energy_cost = self._execute_curse_card(card, target_idx)
        elif card.is_unplayable and getattr(card, "cost_for_turn", getattr(card, "cost", 0)) < 0:
            return False
        elif not card.can_use(self.state.player.energy):
            return False
        else:
            card._last_target_idx = target_idx
            self._set_player_facing_target(target_idx)
            energy_cost = self._execute_normal_card(card, target_idx)

        self.state.player.energy = max(0, self.state.player.energy - energy_cost)
        self.state.card_manager.set_energy(self.state.player.energy)
        self.state.cards_played_this_turn.append(card.card_id)
        self.state._last_card_played_type = card.card_type.value
        self.state._last_card_played_id = card.card_id
        self._trigger_relic_effects("on_card_played")
        if card.is_skill():
            self._trigger_relic_effects("on_skill_played")
        self.state.player.powers.on_player_card_played(self.state.player, card)
        for monster in self.state.monsters:
            if monster.is_dead():
                continue
            monster.powers.on_player_card_played(monster, card)
        if card.is_power():
            self.state.player.powers.on_player_power_played(
                self.state.player,
                card,
                active_powers=active_player_powers,
            )
            for monster in self.state.monsters:
                if monster.is_dead():
                    continue
                monster.powers.on_player_power_played(monster, card)
                if hasattr(monster, "on_player_power_played"):
                    monster.on_player_power_played(card)
            self.state.player._power_cards_played_this_combat = int(
                getattr(self.state.player, "_power_cards_played_this_combat", 0) or 0
            ) + 1
            if self.state.card_manager is not None and hasattr(self.state.card_manager, "on_player_power_played_in_combat"):
                self.state.card_manager.on_player_power_played_in_combat()
        self._process_monster_deaths_after_card_resolution()

        if card.is_attack():
            rage_block = self.state.player.powers.get_rage_block()
            if rage_block > 0:
                self.player_gain_block(rage_block)

        if card.is_skill():
            self.state.player.powers.on_player_skill_played(self.state.player, card)

        # Trigger Anger power on monsters when player plays a Skill
        if card.is_skill():
            for monster in self.state.monsters:
                if monster.is_dead():
                    continue
                for p in list(monster.powers.powers):
                    if hasattr(p, 'on_player_skill_played'):
                        str_gain = p.on_player_skill_played()
                        if str_gain > 0:
                            monster.gain_strength(str_gain)

        self._process_pain_curse_effect()

        is_exhaust = card.exhaust or card.exhaust_on_use_once
        # Some cards mutate hand contents before the played card is moved out of hand.
        # Re-locate the exact instance instead of trusting the original index.
        resolved_card_index = next(
            (idx for idx, hand_card in enumerate(self.state.card_manager.hand.cards) if hand_card is card),
            None,
        )
        if resolved_card_index is None:
            return False
        self.state.card_manager.play_card(resolved_card_index, exhaust=is_exhaust)

        if card.is_power():
            self._trigger_relic_effects("on_power_played")

        if is_exhaust:
            _trigger_exhaust_hooks(self.state.card_manager, self.state.player, card)

        if card.card_id == "Corruption" and self.state.card_manager is not None:
            self.state.card_manager.refresh_hand_costs_for_current_state()

        if getattr(self.state, "_end_player_turn_requested", False):
            self.state._end_player_turn_requested = False
            if self.state.phase == CombatPhase.PLAYER_TURN:
                self.end_player_turn()
        if hasattr(card, "_resolved_x_cost"):
            delattr(card, "_resolved_x_cost")
        if hasattr(card, "_actual_x_cost"):
            delattr(card, "_actual_x_cost")
                
        return True

    def get_pending_choices(self) -> list[dict[str, object]]:
        pending = self.state.pending_combat_choice
        if pending is None:
            return []
        return [dict(option) for option in pending.get("options", [])]

    def _resolve_pending_generated_single_pick(self, pending: dict[str, Any], option: dict[str, Any]) -> bool:
        selected_card = _find_card_by_uuid(pending.get("generated_cards", []) or [], option.get("uuid"))
        if selected_card is None:
            return False
        selection_action = str(pending.get("selection_action", "") or "")
        if selection_action == "discovery":
            _resolve_discovery_choice(self.state, selected_card)
        elif selection_action in {"foreign_influence", "foreign_influence_upgraded"}:
            _resolve_generated_choice_to_hand(
                self.state,
                selected_card,
                zero_cost_this_turn=selection_action.endswith("_upgraded"),
            )
        else:
            return False
        self.state.pending_combat_choice = None
        pending["resolved"] = True
        return True

    def _resolve_pending_draw_pile_single_pick(self, pending: dict[str, Any], option: dict[str, Any]) -> bool:
        card_manager = self.state.card_manager
        if card_manager is None:
            return False
        selected_card = _find_card_by_uuid(getattr(card_manager.draw_pile, "cards", []) or [], option.get("uuid"))
        if selected_card is None:
            return False
        _resolve_draw_pile_card_to_hand_or_discard(self.state, selected_card)
        self.state.pending_combat_choice = None
        pending["resolved"] = True
        return True

    def _resolve_pending_hand_single_pick(self, pending: dict[str, Any], option: dict[str, Any]) -> bool:
        card_manager = self.state.card_manager
        if card_manager is None:
            return False
        selected_card = _find_card_by_uuid(getattr(card_manager.hand, "cards", []) or [], option.get("uuid"))
        if selected_card is None:
            return False
        selection_action = str(pending.get("selection_action", ""))
        if selection_action == "forethought":
            _move_selected_hand_card_to_draw_pile(
                self.state,
                selected_card,
                to_top=False,
                grant_free_to_play_once=True,
            )
        elif selection_action == "thinking_ahead":
            _move_selected_hand_card_to_draw_pile(
                self.state,
                selected_card,
                to_top=True,
                grant_free_to_play_once=False,
            )
        else:
            return False
        self.state.pending_combat_choice = None
        pending["resolved"] = True
        return True

    def _resolve_pending_hand_multi_pick(self, pending: dict[str, Any], option: dict[str, Any]) -> bool:
        action = str(option.get("action", ""))
        if action in {"complete", "skip"}:
            self.state.pending_combat_choice = None
            pending["resolved"] = True
            return self._resume_end_turn_after_choice_if_needed()

        card_manager = self.state.card_manager
        if card_manager is None:
            return False
        selected_card = _find_card_by_uuid(getattr(card_manager.hand, "cards", []) or [], option.get("uuid"))
        if selected_card is None:
            return False

        selection_action = str(pending.get("selection_action", ""))
        if selection_action == "forethought":
            _move_selected_hand_card_to_draw_pile(
                self.state,
                selected_card,
                to_top=False,
                grant_free_to_play_once=True,
            )
        elif selection_action == "purity":
            hand_index = next(
                (idx for idx, hand_card in enumerate(card_manager.hand.cards) if hand_card is selected_card),
                None,
            )
            if hand_index is None:
                return False
            _move_hand_card_to_exhaust(card_manager, self.state.player, hand_index=hand_index)
        elif selection_action == "retain_for_end_turn":
            selected_card.retain = True
        else:
            return False

        pending["selected_count"] = int(pending.get("selected_count", 0) or 0) + 1
        pending["candidate_uuids"] = [
            candidate_uuid
            for candidate_uuid in pending.get("candidate_uuids", []) or []
            if str(candidate_uuid) != str(option.get("uuid"))
        ]

        if int(pending.get("selected_count", 0) or 0) >= int(pending.get("max_picks", 0) or 0):
            self.state.pending_combat_choice = None
            pending["resolved"] = True
            return self._resume_end_turn_after_choice_if_needed()

        options = _refresh_hand_multi_pick_options(self.state, pending)
        remaining_pick_options = [item for item in options if item.get("action") not in {"complete", "skip"}]
        if not remaining_pick_options:
            self.state.pending_combat_choice = None
            pending["resolved"] = True
            return self._resume_end_turn_after_choice_if_needed()
        return True

    def _player_has_end_turn_no_discard(self) -> bool:
        from sts_py.engine.content.relics import RelicEffectType, get_relic_by_id

        for relic_id in self.relics:
            relic_def = get_relic_by_id(relic_id)
            if relic_def is None:
                continue
            if any(effect.effect_type == RelicEffectType.AT_TURN_END_NO_DISCARD for effect in relic_def.effects):
                return True
        return False

    def _get_end_turn_retain_choice_candidates(self) -> list[CardInstance]:
        if self.state.card_manager is None:
            return []
        return [
            card
            for card in self.state.card_manager.hand.cards
            if not getattr(card, "is_ethereal", False)
            and not getattr(card, "self_retain", False)
            and not getattr(card, "retain", False)
        ]

    def _maybe_open_end_turn_retain_choice(self) -> bool:
        if self.state.card_manager is None:
            return False
        if self._player_has_end_turn_no_discard():
            return False
        if self.state.player.powers.has_power("Equilibrium"):
            return False

        retain_amount = max(0, int(self.state.player.powers.get_power_amount("Retain Cards") or 0))
        if retain_amount <= 0:
            return False

        candidate_cards = self._get_end_turn_retain_choice_candidates()
        if len(candidate_cards) <= retain_amount:
            return False

        self.state.pending_combat_choice = {
            "source_card_id": "END_TURN",
            "choice_type": "hand_multi_pick_up_to_n",
            "selection_action": "retain_for_end_turn",
            "resolved": False,
            "candidate_uuids": [str(card.uuid) for card in candidate_cards],
            "selected_count": 0,
            "max_picks": min(retain_amount, len(candidate_cards)),
        }
        _refresh_hand_multi_pick_options(self.state, self.state.pending_combat_choice)
        self.state._resume_end_turn_after_choice = True
        self.state._skip_retain_cards_pre_end_turn = True
        return True

    def _complete_end_player_turn(self) -> None:
        no_discard = self._player_has_end_turn_no_discard()
        skip_retain_cards = bool(getattr(self.state, "_skip_retain_cards_pre_end_turn", False)) or no_discard
        self.state._skip_retain_cards_pre_end_turn = skip_retain_cards
        self.state.player.powers.at_end_of_turn_pre_end_turn_cards(self.state.player, True)
        if self.state.card_manager is not None:
            self.state.card_manager.end_turn(no_discard=no_discard)
        self.state._skip_retain_cards_pre_end_turn = False
        self.state._resume_end_turn_after_choice = False
        self.state.player.powers.at_end_of_turn(self.state.player, True)
        noxious_fumes_amount = self.state.player.get_power_amount("NoxiousFumes")
        if noxious_fumes_amount > 0:
            for monster in self.state.monsters:
                if monster.is_dead():
                    continue
                _apply_poison_to_monster(self.state.player, monster, noxious_fumes_amount)
        metallicize_block = self.state.player.powers.get_metallicize_block()
        if metallicize_block > 0:
            self.state.player.gain_block(metallicize_block)
        self._trigger_player_orb_passives()
        self.state.turn_has_ended = True
        self.state.phase = CombatPhase.MONSTER_TURN

        self._check_split_on_damage()
        if self.state.all_monsters_dead():
            self.state.phase = CombatPhase.END_COMBAT
            return
        if getattr(self.state, "_skip_next_enemy_turn", False):
            self.state._skip_next_enemy_turn = False
            self._end_monster_turn()
            return
        self._execute_monster_turns()

    def _resume_end_turn_after_choice_if_needed(self) -> bool:
        if not bool(getattr(self.state, "_resume_end_turn_after_choice", False)):
            return True
        if self.state.pending_combat_choice is not None:
            return True
        if self.state.phase == CombatPhase.PLAYER_TURN:
            self._complete_end_player_turn()
        return True

    def _autoplay_needs_target(self, card: CardInstance) -> bool:
        definition = getattr(card, "_def", None)
        explicit_target_required = getattr(definition, "target_required", None)
        if explicit_target_required is not None:
            return bool(explicit_target_required)
        try:
            return len(get_card_effects(card, 0)) > len(get_card_effects(card, None))
        except Exception:
            if not card.is_attack():
                return False
            return card.card_id not in {"Cleave", "Whirlwind", "Thunderclap", "Immolate"}

    def _resolve_autoplay_target_idx(self, card: CardInstance, preferred_target_idx: int | None = None) -> int | None:
        if not self._autoplay_needs_target(card):
            return None
        alive_indices = [
            index for index, monster in enumerate(self.state.monsters) if not monster.is_dead()
        ]
        if not alive_indices:
            return None
        if preferred_target_idx in alive_indices:
            return preferred_target_idx
        if len(alive_indices) == 1:
            return alive_indices[0]
        return alive_indices[self.ai_rng.random_int(len(alive_indices) - 1)]

    def _apply_runtime_card_play_modifiers(self, card: CardInstance) -> None:
        if hasattr(card, "apply_combat_cost_modifiers"):
            card.apply_combat_cost_modifiers()
        if card.is_skill() and self.state.player.powers.has_power("Corruption"):
            card.exhaust_on_use_once = True

    def _set_player_facing_target(self, target_idx: int | None) -> None:
        if target_idx is None:
            return
        if target_idx < 0 or target_idx >= len(self.state.monsters):
            return
        if self.state.monsters[target_idx].is_dead():
            return
        self.state.player._facing_monster_idx = target_idx
        self._sync_surrounded_back_attack_state()

    def _sync_surrounded_back_attack_state(self) -> None:
        from sts_py.engine.combat.powers import create_power

        player = self.state.player
        alive_indices = [idx for idx, monster in enumerate(self.state.monsters) if not monster.is_dead()]
        if not player.powers.has_power("Surrounded") or len(alive_indices) <= 1:
            for monster in self.state.monsters:
                if monster.has_power("BackAttack"):
                    monster.powers.remove_power("BackAttack")
            return

        facing_idx = getattr(player, "_facing_monster_idx", None)
        if facing_idx not in alive_indices:
            facing_idx = alive_indices[0]
            player._facing_monster_idx = facing_idx

        for idx, monster in enumerate(self.state.monsters):
            if monster.is_dead():
                continue
            if idx == facing_idx:
                if monster.has_power("BackAttack"):
                    monster.powers.remove_power("BackAttack")
            elif not monster.has_power("BackAttack"):
                monster.add_power(create_power("BackAttack", -1, monster.id))

    def _sync_same_instance_card_state(self, source_card: CardInstance, played_copy: CardInstance) -> None:
        persistent_fields = (
            "upgraded",
            "times_upgraded",
            "cost",
            "cost_for_turn",
            "is_cost_modified",
            "is_cost_modified_for_turn",
            "base_damage",
            "damage",
            "is_damage_modified",
            "base_block",
            "block",
            "is_block_modified",
            "base_magic_number",
            "magic_number",
            "is_magic_number_modified",
            "misc",
            "combat_damage_bonus",
            "combat_cost_reduction",
            "combat_cost_increase",
            "exhaust",
            "is_ethereal",
            "retain",
            "self_retain",
            "is_innate",
            "is_unplayable",
            "return_to_hand",
            "shuffle_back_into_draw_pile",
        )
        for field_name in persistent_fields:
            if hasattr(played_copy, field_name):
                setattr(source_card, field_name, getattr(played_copy, field_name))
        if hasattr(source_card, "apply_combat_cost_modifiers"):
            source_card.apply_combat_cost_modifiers()

    def _prepare_replayed_card_copy(
        self,
        card: CardInstance,
        *,
        target_idx: int | None = None,
        same_instance: bool,
    ) -> CardInstance:
        copied_card = card.make_same_instance() if same_instance else card.make_stat_equivalent_copy()
        copied_card._combat_state = self.state
        copied_card.purge_on_use = True
        copied_card.free_to_play_once = True
        copied_card._last_target_idx = target_idx
        if hasattr(card, "_resolved_x_cost"):
            copied_card._resolved_x_cost = max(0, int(getattr(card, "_resolved_x_cost", 0) or 0))
        if hasattr(card, "_actual_x_cost"):
            copied_card._actual_x_cost = max(0, int(getattr(card, "_actual_x_cost", 0) or 0))
        return copied_card

    def _repeat_same_instance_card(self, card: CardInstance, *, target_idx: int | None = None) -> bool:
        copied_card = self._prepare_replayed_card_copy(card, target_idx=target_idx, same_instance=True)
        if not self.autoplay_card_instance(copied_card, target_idx):
            return False
        self._sync_same_instance_card_state(card, copied_card)
        return True

    def _finish_autoplay_card(self, card: CardInstance) -> None:
        if self.state.card_manager is None:
            return
        if hasattr(card, "_resolved_x_cost"):
            delattr(card, "_resolved_x_cost")
        if hasattr(card, "_actual_x_cost"):
            delattr(card, "_actual_x_cost")
        if card.purge_on_use:
            return

        is_exhaust = card.exhaust or card.exhaust_on_use_once
        if is_exhaust:
            self.state.card_manager.exhaust_pile.add(card)
            _trigger_exhaust_hooks(self.state.card_manager, self.state.player, card)
        elif card.return_to_hand:
            self.state.card_manager._add_card_to_hand_with_limit(card)
        elif card.shuffle_back_into_draw_pile:
            self.state.card_manager.draw_pile.add(card)
        else:
            self.state.card_manager.discard_pile.add(card)
        self.state.card_manager._check_normality_in_hand()

    def autoplay_card_instance(self, card: CardInstance, target_idx: int | None = None) -> bool:
        if self.state.phase != CombatPhase.PLAYER_TURN:
            return False
        if self.state.card_manager is None:
            return False
        self._apply_runtime_card_play_modifiers(card)
        active_player_powers = list(self.state.player.powers.powers) if card.is_power() else None
        card._existing_power_ids_before_play = {power.id for power in self.state.player.powers.powers}

        chosen_target_idx = self._resolve_autoplay_target_idx(card, preferred_target_idx=target_idx)
        card._last_target_idx = chosen_target_idx
        self._set_player_facing_target(chosen_target_idx)

        if card.is_attack():
            self._trigger_relic_effects("on_attack")

        _, energy_cost = execute_card(card, self.state, self.state.player, chosen_target_idx)
        self._process_monster_deaths_after_card_resolution()
        self.state.player.energy = max(0, self.state.player.energy - energy_cost)
        self.state.card_manager.set_energy(self.state.player.energy)
        self.state.cards_played_this_turn.append(card.card_id)
        self.state._last_card_played_type = card.card_type.value
        self.state._last_card_played_id = card.card_id
        self._trigger_relic_effects("on_card_played")
        if card.is_skill():
            self._trigger_relic_effects("on_skill_played")
        self.state.player.powers.on_player_card_played(self.state.player, card)
        for monster in self.state.monsters:
            if monster.is_dead():
                continue
            monster.powers.on_player_card_played(monster, card)
        if card.is_power():
            self.state.player.powers.on_player_power_played(
                self.state.player,
                card,
                active_powers=active_player_powers,
            )
            for monster in self.state.monsters:
                if monster.is_dead():
                    continue
                monster.powers.on_player_power_played(monster, card)
                if hasattr(monster, "on_player_power_played"):
                    monster.on_player_power_played(card)
            self.state.player._power_cards_played_this_combat = int(
                getattr(self.state.player, "_power_cards_played_this_combat", 0) or 0
            ) + 1
            if self.state.card_manager is not None and hasattr(self.state.card_manager, "on_player_power_played_in_combat"):
                self.state.card_manager.on_player_power_played_in_combat()
        self._process_monster_deaths_after_card_resolution()

        if card.is_attack():
            rage_block = self.state.player.powers.get_rage_block()
            if rage_block > 0:
                self.player_gain_block(rage_block)

        if card.is_skill():
            for monster in self.state.monsters:
                if monster.is_dead():
                    continue
                for p in list(monster.powers.powers):
                    if hasattr(p, "on_player_skill_played"):
                        str_gain = p.on_player_skill_played()
                        if str_gain > 0:
                            monster.gain_strength(str_gain)

        self._process_pain_curse_effect()
        self._finish_autoplay_card(card)
        if card.card_id == "Corruption" and self.state.card_manager is not None:
            self.state.card_manager.refresh_hand_costs_for_current_state()
        if hasattr(card, "_resolved_x_cost"):
            delattr(card, "_resolved_x_cost")
        if hasattr(card, "_actual_x_cost"):
            delattr(card, "_actual_x_cost")
        return True

    def choose_combat_option(self, index: int) -> bool:
        pending = self.state.pending_combat_choice
        if pending is None:
            return False
        options = pending.get("options", [])
        if index < 0 or index >= len(options):
            return False

        option = options[index]
        choice_type = str(pending.get("choice_type", ""))
        if choice_type == "generated_single_pick":
            return self._resolve_pending_generated_single_pick(pending, option)
        if choice_type == "draw_pile_single_pick":
            return self._resolve_pending_draw_pile_single_pick(pending, option)
        if choice_type == "hand_single_pick":
            return self._resolve_pending_hand_single_pick(pending, option)
        if choice_type == "hand_multi_pick_up_to_n":
            return self._resolve_pending_hand_multi_pick(pending, option)

        effect = option.get("effect")
        amount = int(option.get("amount", 0))

        if effect == "strength":
            from sts_py.engine.combat.powers import create_power

            self.state.player.add_power(create_power("Strength", amount, "player"))
            self.state.player.strength += amount
        elif effect == "plated_armor":
            from sts_py.engine.combat.powers import create_power

            self.state.player.add_power(create_power("Plated Armor", amount, "player"))
        elif effect == "gold":
            self.state.pending_bonus_gold += amount
        elif effect == "play_draw_pile_card":
            if self.state.card_manager is None:
                return False
            target_uuid = str(option.get("uuid", ""))
            original_card = next(
                (
                    draw_card
                    for draw_card in self.state.card_manager.draw_pile.cards
                    if str(draw_card.uuid) == target_uuid
                ),
                None,
            )
            if original_card is None:
                return False
            play_count = max(1, int(pending.get("play_count", 1)))
            self.state.pending_combat_choice = None
            pending["resolved"] = True
            self.state.card_manager.draw_pile.remove(original_card)
            original_card.exhaust = True
            original_card.free_to_play_once = True
            self.autoplay_card_instance(original_card)
            preferred_target_idx = getattr(original_card, "_last_target_idx", None)
            for _ in range(play_count - 1):
                copied_card = self._prepare_replayed_card_copy(
                    original_card,
                    target_idx=preferred_target_idx,
                    same_instance=False,
                )
                self.autoplay_card_instance(copied_card, preferred_target_idx)
                preferred_target_idx = getattr(copied_card, "_last_target_idx", preferred_target_idx)
            return True
        else:
            return False

        pending["resolved"] = True
        self.state.pending_combat_choice = None
        return True

    def player_attack(self, monster_idx: int, damage: int) -> int:
        if self.state.phase != CombatPhase.PLAYER_TURN:
            return 0
        if monster_idx >= len(self.state.monsters):
            return 0

        self._set_player_facing_target(monster_idx)

        monster = self.state.monsters[monster_idx]

        modified_damage = monster.powers.apply_damage_receive_modifiers(float(damage), "NORMAL")
        final_damage = int(modified_damage)

        actual = monster.take_damage(final_damage)

        if actual > 0:
            block_gain = monster.powers.on_attacked(actual, monster)
            if block_gain > 0:
                monster.gain_block(block_gain)

            thorns = monster.powers.get_power_amount("Thorns")
            if thorns > 0:
                self.state.player.take_damage(thorns, damage_type="THORNS", source_owner=monster)

        if hasattr(monster, 'has_split') and monster.has_split and not getattr(monster, 'has_split_triggered', False):
            if monster.hp <= monster.max_hp // 2:
                monster.has_split_triggered = True
                monster.set_move(MonsterMove(4, MonsterIntent.UNKNOWN, name="Split"))

        if monster.is_dead() and not getattr(monster, 'just_died', False):
            monster.just_died = True
            self._on_monster_death(monster)

        return actual

    def _on_monster_death(self, monster) -> None:
        """Handle effects when a monster dies, including The Specimen poison transfer and Spore Cloud."""
        if hasattr(monster, 'on_death'):
            monster.on_death()
        for power in list(getattr(monster.powers, "powers", []) or []):
            if hasattr(power, "on_death"):
                power.on_death()

        corpse_explosion = monster.powers.get_power_amount("CorpseExplosion")
        if corpse_explosion > 0:
            explosion_damage = max(0, int(getattr(monster, "max_hp", 0) or 0))
            for other_monster in self.state.monsters:
                if other_monster is monster or other_monster.is_dead():
                    continue
                other_monster.take_damage(explosion_damage)

        if not self._has_relic("TheSpecimen"):
            return

        poison_amount = monster.powers.get_power_amount("Poison")
        if poison_amount <= 0:
            return

        living_enemies = [m for m in self.state.monsters if not m.is_dead() and m != monster]
        if not living_enemies:
            return

        import random
        from sts_py.engine.combat.powers import create_power
        target = random.choice(living_enemies)
        target.add_power(create_power("Poison", poison_amount, target.id))

    def _process_monster_deaths_after_card_resolution(self) -> None:
        changed = True
        while changed:
            changed = False
            for monster in self.state.monsters:
                if monster.is_dead() and not getattr(monster, "just_died", False):
                    monster.just_died = True
                    self._on_monster_death(monster)
                    changed = True

    def _transform_strikes_and_defends(self) -> None:
        """Transform all Strikes and Defends in the deck.

        Rules:
        - Cannot transform a card into the same card
        - Cannot transform into Basic cards
        - Curse -> Curse only
        - Colored card -> Same color only
        - Colorless -> Colorless only
        """
        from sts_py.engine.content.cards_min import CardRarity, CardType
        from sts_py.engine.content.card_instance import CardInstance

        if self.state.card_manager is None:
            return

        deck = list(self.state.card_manager.draw_pile.cards)
        deck.extend(self.state.card_manager.discard_pile.cards)
        deck.extend(self.state.card_manager.hand.cards)

        strikes_to_transform = [c for c in deck if c.card_id in ("Strike", "Strike+") and c.card_id not in UNTRANSFORMABLE_CARDS and c.card_id not in BOTTLED_CARDS]
        defends_to_transform = [c for c in deck if c.card_id in ("Defend", "Defend+") and c.card_id not in UNTRANSFORMABLE_CARDS and c.card_id not in BOTTLED_CARDS]

        all_to_transform = strikes_to_transform + defends_to_transform
        for card in all_to_transform:
            new_card_id = self._get_transform_target(card)
            if new_card_id:
                self._replace_card(card, new_card_id)

    def _transform_cards_pickup(self, upgrade: bool = False) -> None:
        """Handle card transform on relic pickup (e.g., Astrolabe).

        Player selects cards to transform. For now, transforms Strikes and Defends.
        """
        from sts_py.engine.content.card_instance import CardInstance

        if self.state.card_manager is None:
            return

        deck = list(self.state.card_manager.draw_pile.cards)
        deck.extend(self.state.card_manager.discard_pile.cards)
        deck.extend(self.state.card_manager.hand.cards)

        strikes = [c for c in deck if c.card_id in ("Strike", "Strike+") and c.card_id not in UNTRANSFORMABLE_CARDS and c.card_id not in BOTTLED_CARDS]
        defends = [c for c in deck if c.card_id in ("Defend", "Defend+") and c.card_id not in UNTRANSFORMABLE_CARDS and c.card_id not in BOTTLED_CARDS]

        to_transform = strikes[:3] + defends[:3]
        to_transform = to_transform[:3]

        for card in to_transform:
            new_card_id = self._get_transform_target(card)
            if new_card_id:
                self._replace_card(card, new_card_id, upgrade=upgrade)

    def _remove_cards_from_deck(self, count: int, exclude_unremovable: bool = False) -> None:
        """Remove cards from the player's deck.

        Args:
            count: Number of cards to remove
            exclude_unremovable: If True, exclude cards that cannot be removed
                               (Bottled cards, Necronomicurse, Curse of the Bell)
        """
        if self.state.card_manager is None:
            return

        deck = list(self.state.card_manager.draw_pile.cards)
        deck.extend(self.state.card_manager.discard_pile.cards)

        removable = []
        for card in deck:
            if exclude_unremovable and (card.card_id in UNREMOVABLE_CARDS or card.card_id in BOTTLED_CARDS):
                continue
            removable.append(card)

        import random
        to_remove = random.sample(removable, min(count, len(removable)))

        for card in to_remove:
            for pile in [self.state.card_manager.draw_pile,
                         self.state.card_manager.discard_pile]:
                if card in pile.cards:
                    pile.cards.remove(card)
                    break

    def _get_transform_target(self, card: CardInstance) -> str | None:
        """Get a valid transform target for the given card.

        Rules:
        - Cannot transform into the same card
        - Cannot transform into Basic cards (except for curses)
        - Curse -> Curse only
        - Colored card -> Same color only (Ironclad, Silent, Defect, Watcher cards)
        - Colorless -> Colorless only
        """
        import random

        if self.state.card_manager is None:
            return None

        character_class = getattr(self.state.player, 'character_class', 'IRONCLAD')

        transform_pools = self._get_transform_pool(character_class)

        current_id = card.card_id.replace("+", "")

        same_color_pool = transform_pools.get('colored', [])
        colorless_pool = transform_pools.get('colorless', [])
        curse_pool = transform_pools.get('curse', [])

        if card.card_type.value == "CURSE":
            valid_pool = curse_pool
        elif current_id in ("Strike", "Defend", "Bash"):
            valid_pool = same_color_pool
        else:
            valid_pool = colorless_pool

        valid_pool = [c for c in valid_pool if c != current_id and c != current_id + "+"]
        valid_pool = [c for c in valid_pool if c not in UNTRANSFORMABLE_CARDS and c not in BOTTLED_CARDS]

        if not valid_pool:
            return None

        return random.choice(valid_pool)

    def _get_transform_pool(self, character_class: str) -> dict:
        """Get card pools for transformation based on character class.

        Returns dict with 'colored', 'colorless', and 'curse' pools.
        """
        from sts_py.engine.content.cards_min import CardRarity, CardType

        colored_cards = []
        if character_class == "IRONCLAD":
            colored_cards = [
                "Anger", "Armaments", "BodySlam", "BurningPact", "Carnage",
                "Clothesline", "Combust", "DarkEmbrace", "Disarm", "Dropkick",
                "DualWield", "Entrench", "Evolve", "FeelNoPain", "FiendFire",
                "FireBreathing", "FlameBarrier", "Flex", "GhostlyArmor",
                "Havoc", "Headbutt", "HeavyBlade", "Hemokinesis", "Immolate",
                "Impervious", "Inflame", "Intimidate", "IronWave", "Juggernaut",
                "LimitBreak", "Metallicize", "Offering", "PerfectedStrike",
                "PommelStrike", "PowerThrough", "Pummel", "Rage", "Rampage",
                "RecklessCharge", "Reaper", "Rupture", "SecondWind", "SearingBlow",
                "SeeingRed", "Sentinel", "SeverSoul", "Shockwave", "SpotWeakness",
                "SwordBoomerang", "Thunderclap", "TrueGrit", "TwinStrike",
                "Uppercut", "Warcry", "WildStrike", "Bludgeon", "Brutality",
                "Corruption", "DemonForm", "Exhume", "Barricade", "Berserk", "Bludgeon",
            ]
        elif character_class == "SILENT":
            colored_cards = [
                "Acid Splitter", "Adrenaline", "After Image", "Alchemize",
                "Amplify", "Backflip", "Bane", "Blur", "Bouncing Flask",
                "Bullet Time", "Caltrops", "Choke", "Cloak and Dagger",
                "Cluster Bomb", "Concentrate", "Corpse Explosion", "Crippling Poison",
                "Dash", "Deadly Poison", "Deflect", "Die Die Die", "Dodge and Roll",
                "Doppelganger", "Endless Agony", "Envenom", "Escape Plan", "Eviscerate",
                "Evoke", "Exit", "Expert", "Finisher", "Flechettes", "Flying Knee",
                "Footwork", "Glass Knife", "Grand Finale", "Heel", "Hex",
                "Hide", "Impervious", "Infinite Blades", "Insect", "Jack King",
                "Killer", "Leg Sweep", "Lacerate", "Madness", "Metalize",
                "Mind", "Necronomicurse", "Noxious Fumes", "Outmaneuver", "Pain",
                "Panic", "Parasite", "Patron", "Perfect Strike", "Phantasmal",
                "Piercing", "Poisoned Blade", "Predator", "Prepared", "Pride",
                "Quick Slash", "Quicksand", "Rage", "Rainbow", "Ritual",
                "Schadenfreude", "Sword", "Sword Barrage", "Terror", "Thief",
                "Thinking", "Through", "Thunderclap", "Tools", "Toxic", "Trap",
                "Trick", "Trip", "Underhanded", "Veiled", "Venom", "Viper",
                "Warcry", "Well Laid Plans", "Whirlwind", "Wraith", "X",
            ]
        elif character_class == "DEFECT":
            colored_cards = [
                "Ball Lightning", "Barrage", "Beam Cell", "Bias", "Buffer",
                "Burn", "Capacitor", "Chaos", "Chill", "Claw", "Compile Driver",
                "Coolheaded", "Core Surge", "Creative AI", "Darkness", "Defragment",
                "Discharge", "Double", "Doppelganger", "Draft", "Dramatic Entrance",
                "Echo", "Electrodynamics", "Endless", "Energy", "Equilibrium",
                "Exhale", "Fathon", "Force Field", "Forearm", "Fragments",
                "Free", "Frost", "Gash", "Genetic", "Grip", "Halt",
                "Heatsink", "Hell", "Hemokinesis", "Impulse", "Infuser",
                "J.A.X.", "Leap", "Lock", "Looper", "Machine", "Magnetism",
                "Melter", "Metamorphosis", "Meteor", "Multicast", "Nerves",
                "Neural", "Nuclear", "Ocupied", "Overclock", "Panacea",
                "PandoraBox", "Path", "Plasma", "Power", "Prestidigitation",
                "Recursion", "Recycle", "Reinforced", "Reprogram", "Ritual",
                "Rock", "Screen", "Seek", "Self", "Sentinel", "Set",
                "Shuffle", "Shutterbug", "Skim", "Skill", "Stack",
                "Static", "Storm", "Streamline", "Sunder", "Sweep",
                "Tempest", "Thunder Strike", "Turbo", "Twintone", "Undo",
                "Universal", "Void", "Wave", "Weave", "Wind", "Zap",
            ]
        elif character_class == "WATCHER":
            colored_cards = [
                "Alpha", "Assume", "Auto", "Blasphemy", "Brahmin",
                "Breath", "Brutality", "Bullet", "Carve", "Catch",
                "Chrysalis", "Clarity", "Collect", "Conjure", "Consecration",
                "Contemplation", "Crackdown", "Crescendo", "Cros", "Crush",
                "Cut", "Damage", "Deceive", "Deflect", "Depression",
                "Desperation", "Devotion", "Devour", "Disarm", "Dodge",
                "Dominate", "Empty", "Empty Body", "Empty Fist", "Empty Mind",
                "Empty Wraith", "Enflame", "Eruption", "Evaluate", "Exhale",
                "Fame", "Fasting", "Fearsome", "Flail", "Flame",
                "Float", "Follow", "Foresight", "Fury", "Gash",
                "Good", "Grace", "Halt", "Harm", "Haste",
                "Hourglass", "Impatience", "Indignation", "Inhale", "Inner",
                "Just", "Lesson", "Light", "Like", "Lingering",
                "Lith", "Live", "Long", "Mantra", "Master",
                "Mental", "Metamorphosis", "Midnight", "Mount", "Nirvana",
                "Normality", "Obeisance", "Observation", "Omniscience", "Perseverance",
                "Power", "Pressure", "Protect", "Prostrate", "Providence",
                "Rage", "Ragnarok", "Reach", "Real", "Reroll",
                "Sands", "Satisfaction", "Scrawl", "Script", "Scry",
                "Sculpt", "Sedentary", "Shattering", "Shifting", "Shock",
                "Shrine", "Smite", "Spire", "Spirit", "Squeaky",
                "Stance", "Steady", "Stimulation", "Stone", "Strike",
                "Study", "Surrender", "Swivel", "Talk", "Tantrum",
                "Tear", "Temple", "Third", "Thor", "Thought",
                "Thread", "Three", "Tib", "Tone", "Trance",
                "Transcend", "Trash", "Tremor", "Tribal", "Trick",
                "Truce", "Turn", "Two", "Unload", "V",
                "Vengeance", "Vital", "Waltz", "Ward", "Wave",
                "Way", "We", "Weary", "Wheel", "Wind",
                "Wish", "Witch", "Wraith", "Wrath", "Wreath",
            ]
        else:
            colored_cards = []

        colorless_cards = [
            "Impervious", "Thunderclap", "Shimmering", "Bouncing Flask",
            "Gamble", "Master of Strategy", "Magnetism", "Encyclopedia",
            "Dream Compressor", "The Bomb", "Expenses", "Fission",
            "Immolate", "SearingBlow", "Ritual", "Sadistic Nature",
            "Charon", "Omniscience", "Scry", "Tier", "Transmute",
            "Mayhem", "Corruption", "DemonForm", "Juggernaut", "Bludgeon",
        ]

        curse_cards = [
            "AscendersBane", "CurseOfTheBell", "Necronomicurse", "Pride",
            "Parasite", "Regret", "Shame", "Pain", "Doubt", "Decay", "Injury", "Clumsy", "Writhe",
        ]

        return {
            'colored': colored_cards,
            'colorless': colorless_cards,
            'curse': curse_cards
        }

    def _replace_card(self, old_card: CardInstance, new_card_id: str, upgrade: bool = False) -> None:
        """Replace old_card with new_card_id in the game state."""
        from sts_py.engine.content.card_instance import CardInstance

        new_card = CardInstance(card_id=new_card_id)
        if upgrade:
            new_card.upgraded = True
            new_card.times_upgraded = 1

        removed = False
        for pile in [self.state.card_manager.draw_pile,
                     self.state.card_manager.discard_pile,
                     self.state.card_manager.hand,
                     self.state.card_manager.exhaust_pile]:
            if old_card in pile.cards:
                pile.cards.remove(old_card)
                pile.cards.append(new_card)
                removed = True
                break

        return

    def player_gain_block(self, amount: int) -> None:
        if self.state.phase != CombatPhase.PLAYER_TURN:
            return
        self.state.player.gain_block(amount)

    def _change_player_stance(self, stance_type: StanceType | None) -> None:
        old_stance = getattr(self.state.player, "stance", None)
        exit_effects = change_stance(self.state.player, stance_type)
        new_stance = getattr(self.state.player, "stance", None)
        if exit_effects.get("energy"):
            self.state.player.energy += int(exit_effects["energy"])
            if self.state.card_manager is not None:
                self.state.card_manager.set_energy(self.state.player.energy)
        if old_stance is not None and new_stance is not None and old_stance.stance_type != new_stance.stance_type:
            self.state.player.powers.on_change_stance(self.state.player, old_stance, new_stance)

    def _apply_player_attack_damage_receive_modifiers(self, base_damage: int) -> int:
        modified_damage = float(base_damage)
        if getattr(self.state.player, "stance", None) is not None:
            modified_damage = self.state.player.stance.at_damage_receive(modified_damage, "NORMAL")
        modified_damage = self.state.player.powers.apply_damage_receive_modifiers(modified_damage, "NORMAL")
        modified_damage = self.state.player.powers.apply_damage_final_receive_modifiers(modified_damage, "NORMAL")
        return max(0, int(modified_damage))

    def _process_player_start_of_turn_powers(self) -> None:
        self.state.player.powers.at_start_of_turn(self.state.player)
        self._trigger_player_start_of_turn_orbs()
        if self.state.card_manager is not None:
            self.state.card_manager.set_energy(self.state.player.energy)
        self._process_monster_deaths_after_card_resolution()

    def _process_player_start_of_turn_post_draw_powers(self) -> None:
        self.state.player.powers.at_start_of_turn_post_draw(self.state.player)
        if self.state.card_manager is not None:
            self.state.card_manager.set_energy(self.state.player.energy)

    def end_player_turn(self) -> None:
        if self.state.phase != CombatPhase.PLAYER_TURN:
            return
        if self.state.pending_combat_choice is not None:
            return
        self.state._resume_end_turn_after_choice = False
        self.state._skip_retain_cards_pre_end_turn = False
        if self._maybe_open_end_turn_retain_choice():
            return
        self._complete_end_player_turn()

    def _check_split_on_damage(self) -> None:
        """Check all monsters for split trigger after end-of-turn damage."""
        for monster in self.state.monsters:
            if monster.is_dead():
                continue
            if hasattr(monster, 'has_split') and monster.has_split and not getattr(monster, 'has_split_triggered', False):
                if monster.hp <= monster.max_hp // 2:
                    monster.has_split_triggered = True
                    monster.set_move(MonsterMove(4, MonsterIntent.UNKNOWN, name="Split"))

    def _execute_monster_turns(self) -> None:
        for monster in self.state.monsters:
            if not monster.is_dead():
                monster.block = 0

        for i, monster in enumerate(self.state.monsters):
            if monster.is_dead():
                continue

            monster.powers.at_start_of_turn(monster)
            self._process_monster_poison(monster)
            self._execute_monster_move(i, monster)

        self._end_monster_turn()

    def _process_monster_poison(self, monster) -> None:
        """Process poison damage at start of monster's turn.

        At the start of monster's turn, deal poison damage equal to poison stack,
        then reduce poison stack by 1.
        """
        poison_amount = monster.powers.get_power_amount("Poison")
        if poison_amount <= 0:
            return

        monster.take_damage(poison_amount)
        monster.powers.reduce_power("Poison", 1)

        if monster.is_dead() and not getattr(monster, 'just_died', False):
            monster.just_died = True
            self._on_monster_death(monster)

    def _execute_monster_move(self, idx: int, monster: MonsterBase) -> None:
        if monster.next_move is None:
            return

        move = monster.next_move
        intent = move.intent

        monster._combat_state = self.state

        # Apply player's damage-receive modifiers for attack intents
        if intent.is_attack():
            base_damage = monster.get_intent_damage()
            final_damage = self._apply_player_attack_damage_receive_modifiers(base_damage)
            # Temporarily override intent damage for take_turn
            original_get_intent = monster.get_intent_damage
            original_take_damage = self.state.player.take_damage

            def retaliating_take_damage(amount: int, *args, **kwargs) -> int:
                if monster.is_dead():
                    return 0
                actual = original_take_damage(amount, *args, **kwargs)
                retaliation = getattr(self.state.player, "thorns", 0)
                retaliation += self.state.player.powers.get_power_amount("Thorns")
                retaliation += self.state.player.powers.get_power_amount("FlameBarrier")
                if retaliation > 0 and not monster.is_dead():
                    monster.take_damage(retaliation)
                return actual

            monster.get_intent_damage = lambda: final_damage
            self.state.player.take_damage = retaliating_take_damage
            try:
                monster.take_turn(self.state.player)
            finally:
                self.state.player.take_damage = original_take_damage
                monster.get_intent_damage = original_get_intent
        else:
            monster.take_turn(self.state.player)

        if hasattr(monster, '_combat_state'):
            delattr(monster, '_combat_state')

        # Check if monster take_turn set a custom next move directly
        skip_roll = getattr(monster, '_skip_next_roll', False)
        if skip_roll:
            monster._skip_next_roll = False
        else:
            monster.next_move = None
            monster.roll_move(self.ai_rng)

    def _trigger_relic_effects(self, trigger_type: str) -> None:
        from sts_py.engine.content.relics import get_relic_by_id, RelicEffectType

        for relic_id in self.relics:
            relic_def = get_relic_by_id(relic_id)
            if relic_def is None:
                continue

            for effect in relic_def.effects:
                effect_value = effect.effect_type.value
                should_trigger = False

                if effect_value == trigger_type:
                    should_trigger = True
                elif trigger_type == "at_battle_start":
                    if effect_value in (
                        "start_with_shivs",
                        "at_battle_start_buffer",
                        "on_death_save",
                        "modify_damage",
                        "limit_cards_play",
                        "limit_cards_draw",
                        "heal_multiply",
                    ):
                        should_trigger = True
                elif trigger_type == "at_turn_start":
                    if effect_value in ("at_turn_start", "every_n_turns_self", "at_turn_start_no_attack", "at_turn_start_specific", "gain_mantra_per_turn"):
                        should_trigger = True
                elif trigger_type == "at_turn_end":
                    if effect_value in ("at_turn_end", "at_turn_end_hand_block", "at_turn_end_empty_orb", "at_turn_end_no_discard", "every_n_turns"):
                        should_trigger = True
                elif trigger_type == "on_attack":
                    if effect_value in ("on_attack", "every_n_attacks", "every_n_attacks_self"):
                        should_trigger = True
                elif trigger_type == "on_skill_played":
                    if effect_value in ("every_n_skills",):
                        should_trigger = True
                elif trigger_type == "on_card_played":
                    if effect_value in ("on_card_played", "every_n_cards"):
                        should_trigger = True
                elif trigger_type == "on_power_played":
                    if effect_value in ("on_power_played",):
                        should_trigger = True
                elif trigger_type == "on_exhaust":
                    if effect_value in ("on_exhaust", "on_exhaust_damage_all", "on_exhaust_add_random"):
                        should_trigger = True
                elif trigger_type == "on_discard":
                    if effect_value in ("on_discard", "on_first_discard_per_turn"):
                        should_trigger = True

                if should_trigger:
                    self._apply_relic_effect(relic_id, effect)

    def _get_magic_flower_multiplier(self) -> float:
        """Returns Magic Flower heal multiplier if available in combat.

        Magic Flower: +50% healing in combat (1.5x), round half up.
        Only works during combat, not outside.
        """
        if not self._has_relic("MagicFlower"):
            return 1.0
        return 1.5

    def _apply_heal_amplification(self, heal_amount: int) -> int:
        """Apply Magic Flower amplification to a heal amount.

        Uses round half up (四舍五入) for rounding.
        """
        multiplier = self._get_magic_flower_multiplier()
        if multiplier == 1.0:
            return heal_amount
        amplified = heal_amount * multiplier
        return round(amplified)

    def _apply_relic_effect(self, relic_id: str, effect) -> None:
        from sts_py.engine.content.relics import RelicEffectType

        effect_type = effect.effect_type
        value = effect.value
        extra = effect.extra
        target = effect.target

        if effect_type == RelicEffectType.AT_BATTLE_START:
            extra_type = extra.get("type", "")
            if extra_type == "block":
                self.state.player.gain_block(value)
            elif extra_type == "plated_armor":
                self.state.player.plated_armor = getattr(self.state.player, 'plated_armor', 0) + value
            elif extra_type == "strength":
                self.state.player.strength += value
            elif extra_type == "draw":
                if self.state.card_manager is not None:
                    self.state.card_manager.draw_cards(value)
            elif extra_type == "draw_extra":
                if self.state.card_manager is not None:
                    self.state.card_manager.draw_cards(value)
            elif extra_type == "vulnerable":
                from sts_py.engine.combat.powers import VulnerablePower
                for monster in self.state.monsters:
                    monster.powers.add_power(VulnerablePower(amount=value))
            elif extra_type == "weak":
                from sts_py.engine.combat.powers import WeakPower
                for monster in self.state.monsters:
                    monster.powers.add_power(WeakPower(amount=value))
            elif extra_type == "energy":
                self.state.player.energy += value
            elif extra_type == "dexterity":
                self.state.player.dexterity += value
            elif extra_type == "heal":
                heal_amount = min(value, self.state.player.max_hp - self.state.player.hp)
                self.state.player.hp += heal_amount
            elif extra_type == "thorns":
                if hasattr(self.state.player, 'thorns'):
                    self.state.player.thorns += value
                else:
                    self.state.player.thorns = value
            elif extra_type == "focus":
                self.state.player.focus += value
            elif extra_type == "lightning_orb":
                from sts_py.engine.combat.orbs import LightningOrb

                for _ in range(value):
                    self._channel_orb(LightningOrb())
            elif extra_type == "dark_orb":
                from sts_py.engine.combat.orbs import DarkOrb

                for _ in range(value):
                    self._channel_orb(DarkOrb())
            elif extra_type == "orb_slots":
                self.state.player.max_orbs += value
                self._bind_player_orbs()
            elif extra_type == "frost_orbs":
                from sts_py.engine.combat.orbs import FrostOrb

                for _ in range(value):
                    self._channel_orb(FrostOrb())
            elif extra_type == "plasma_orbs":
                from sts_py.engine.combat.orbs import PlasmaOrb

                for _ in range(value):
                    self._channel_orb(PlasmaOrb())
            elif extra_type == "plasma_orb":
                from sts_py.engine.combat.orbs import PlasmaOrb

                self._channel_orb(PlasmaOrb())
            elif extra_type == "channel_plasma":
                from sts_py.engine.combat.orbs import PlasmaOrb
                self._channel_orb(PlasmaOrb())
            elif extra_type in {"apply_confused", "confused"}:
                from sts_py.engine.combat.powers import ConfusedPower
                self.state.player.powers.add_power(ConfusedPower())
            elif extra_type == "miracle":
                from sts_py.engine.content.card_instance import CardInstance
                for _ in range(value):
                    miracle = CardInstance(card_id="Miracle")
                    self.state.card_manager.hand.add(miracle)
            elif extra_type == "add_miracle_to_hand":
                from sts_py.engine.content.card_instance import CardInstance
                miracle = CardInstance(card_id="Miracle")
                self.state.card_manager.hand.add(miracle)

        elif effect_type == RelicEffectType.AT_BATTLE_START_BUFFER:
            from sts_py.engine.combat.powers import create_power

            self.state.player.add_power(create_power("Buffer", value, "player"))

        elif effect_type == RelicEffectType.AT_BATTLE_START_ENERGY:
            self.state.player.energy += value

        elif effect_type == RelicEffectType.FIRST_ATTACK_COMBAT:
            if not hasattr(self.state.player, '_first_attack_triggered'):
                self.state.player._first_attack_triggered = False
            if not self.state.player._first_attack_triggered:
                extra_type = extra.get("type", "")
                if extra_type == "bonus_damage":
                    self.state.player._first_attack_bonus_damage = value

        elif effect_type == RelicEffectType.EVERY_N_ATTACKS_SELF:
            if not hasattr(self.state.player, '_relic_attack_counters'):
                self.state.player._relic_attack_counters = {}
            stored_counter = int(self.state.player._relic_attack_counters.get(relic_id, 0) or 0)
            legacy_relic_id = self._single_every_n_attacks_self_relic_id()
            if legacy_relic_id == relic_id and hasattr(self.state.player, "_attack_counter"):
                legacy_counter = int(getattr(self.state.player, "_attack_counter", 0) or 0)
                if legacy_counter != stored_counter:
                    stored_counter = legacy_counter
            relic_counter = stored_counter + 1
            self.state.player._relic_attack_counters[relic_id] = relic_counter
            if legacy_relic_id == relic_id:
                self.state.player._attack_counter = relic_counter
            extra_type = extra.get("type", "")
            if relic_counter % value == 0:
                if extra_type == "energy":
                    self.state.player.energy += extra.get("amount", 1)
                elif extra_type == "double_damage":
                    self.state.player._next_attack_double = True

        elif effect_type == RelicEffectType.AT_TURN_END:
            extra_type = extra.get("type", "")
            if extra_type == "block":
                condition = extra.get("condition", "")
                if condition == "no_block" and self.state.player.block > 0:
                    return
                self.state.player.gain_block(value)

        elif effect_type == RelicEffectType.AT_TURN_START_NO_ATTACK:
            extra_type = extra.get("type", "")
            if extra_type == "energy":
                if not self.state.player._has_attacked_this_turn:
                    self.state.player.energy += value

        elif effect_type == RelicEffectType.AT_TURN_START:
            extra_type = extra.get("type", "")
            if extra_type == "damage":
                for monster in self.state.monsters:
                    if not monster.is_dead():
                        monster.take_damage(value)

        elif effect_type == RelicEffectType.ON_DAMAGE:
            extra_type = extra.get("type", "")
            if extra_type == "extra_poison":
                condition = extra.get("condition", "")
                if condition == "poison_applied" or condition == "":
                    self.state.player._extra_poison_on_damage = value

        elif effect_type == RelicEffectType.ON_POISON_APPLIED:
            extra_type = extra.get("type", "")
            if extra_type == "extra_poison":
                self.state.player._extra_poison_on_applied = value

        elif effect_type == RelicEffectType.ON_HP_LOSS:
            extra_type = extra.get("type", "")
            if extra_type == "block_next_turn":
                if not hasattr(self.state.player, '_delayed_block_count'):
                    self.state.player._delayed_block_count = 0
                self.state.player._delayed_block_count += value

        elif effect_type == RelicEffectType.AT_TURN_START_DELAYED:
            extra_type = extra.get("type", "")
            target_turn = extra.get("turn", 2)
            if extra_type == "block":
                if self.state.turn >= target_turn:
                    self.state.player.gain_block(value)
                    self.state.turn = 0

        elif effect_type == RelicEffectType.EVERY_N_TURNS_SELF:
            extra_type = extra.get("type", "")
            if self.state.turn > 0 and self.state.turn % value == 0:
                if extra_type == "energy":
                    self.state.player.energy += extra.get("amount", 1)

        elif effect_type == RelicEffectType.ON_CARD_PLAYED:
            extra_type = extra.get("type", "")
            if extra_type == "counter":
                if not hasattr(self.state.player, '_card_counter'):
                    self.state.player._card_counter = 0
                self.state.player._card_counter += 1

        elif effect_type == RelicEffectType.EVERY_N_CARDS:
            if not hasattr(self.state.player, '_card_counter'):
                self.state.player._card_counter = 0
            self.state.player._card_counter += 1
            extra_type = extra.get("type", "")
            if self.state.player._card_counter % value == 0:
                if extra_type == "draw":
                    if self.state.card_manager is not None:
                        self.state.card_manager.draw_cards(extra.get("amount", 1))

        elif effect_type == RelicEffectType.EVERY_N_ATTACKS:
            if not hasattr(self.state.player, '_relic_attack_counters'):
                self.state.player._relic_attack_counters = {}
            relic_counter = int(self.state.player._relic_attack_counters.get(relic_id, 0) or 0) + 1
            self.state.player._relic_attack_counters[relic_id] = relic_counter
            extra_type = extra.get("type", "")
            if relic_counter % value == 0:
                if extra_type == "dexterity":
                    self.state.player.dexterity += extra.get("amount", 1)
                elif extra_type == "strength":
                    self.state.player.strength += extra.get("amount", 1)
                elif extra_type == "block":
                    self.state.player.gain_block(extra.get("amount", 4))

        elif effect_type == RelicEffectType.EVERY_N_SKILLS:
            if not hasattr(self.state.player, '_relic_skill_counters'):
                self.state.player._relic_skill_counters = {}
            relic_counter = int(self.state.player._relic_skill_counters.get(relic_id, 0) or 0) + 1
            self.state.player._relic_skill_counters[relic_id] = relic_counter
            extra_type = extra.get("type", "")
            if relic_counter % value == 0 and extra_type == "damage_all":
                damage = int(extra.get("amount", value) or value)
                for monster in self.state.monsters:
                    if not monster.is_dead():
                        monster.take_damage(damage)

        elif effect_type == RelicEffectType.ON_ENEMY_DEATH:
            extra_type = extra.get("type", "")
            if extra_type == "energy_draw":
                self.state.player.energy += extra.get("energy", 1)
                if self.state.card_manager is not None:
                    self.state.card_manager.draw_cards(extra.get("draw", 1))

        elif effect_type == RelicEffectType.ON_EXHAUST_ADD_RANDOM:
            if self.state.card_manager is None:
                return
            from sts_py.engine.content.cards_min import CARD_DEFS_BY_CHARACTER, CardRarity

            character_class = str(getattr(self.state.player, "character_class", "IRONCLAD") or "IRONCLAD").upper()
            defs = CARD_DEFS_BY_CHARACTER.get(character_class, CARD_DEFS_BY_CHARACTER["IRONCLAD"])
            candidates = [
                card_def.id
                for card_def in defs.values()
                if card_def.rarity in {CardRarity.COMMON, CardRarity.UNCOMMON, CardRarity.RARE}
            ]
            if not candidates:
                return
            if self.ai_rng is not None and len(candidates) > 1:
                card_id = candidates[self.ai_rng.random_int(len(candidates) - 1)]
            else:
                card_id = candidates[0]
            self.state.card_manager.generate_cards_to_hand(card_id, 1)

        elif effect_type == RelicEffectType.ON_DEATH_SAVE:
            extra_type = extra.get("type", "")
            if extra_type == "revive_half_hp":
                if self.state.player.hp <= 0:
                    max_hp = self.state.player.max_hp
                    self.state.player.hp = max_hp // 2
                if not hasattr(self.state.player, "_lizard_tail_available"):
                    self.state.player._lizard_tail_available = True

        elif effect_type == RelicEffectType.EMPTY_HAND_DRAW:
            if self.state.card_manager is not None and len(self.state.card_manager.hand.cards) == 0:
                self.state.card_manager.draw_cards(value)

        elif effect_type == RelicEffectType.ON_DISCARD:
            extra_type = extra.get("type", "")
            if extra_type == "damage_random":
                if self.state.monsters:
                    import random
                    target = random.choice([m for m in self.state.monsters if not m.is_dead()])
                    if target:
                        target.take_damage(value)
            elif extra_type == "block":
                self.state.player.gain_block(value)

        elif effect_type == RelicEffectType.MODIFY_DAMAGE:
            extra_type = extra.get("type", "")
            if extra_type == "min_damage_receive":
                max_damage = extra.get("max", 5)
                if not hasattr(self.state.player, '_torii_active'):
                    self.state.player._torii_active = True
                    self.state.player._torii_max_damage = max_damage

        elif effect_type == RelicEffectType.MODIFY_VULNERABLE:
            extra_type = extra.get("type", "")
            if extra_type == "extra_damage_percent":
                if not hasattr(self.state.player, '_odd_mushroom_vulnerable_damage'):
                    self.state.player._odd_mushroom_vulnerable_damage = 0
                self.state.player._odd_mushroom_vulnerable_damage += value

        elif effect_type == RelicEffectType.HEAL_MULTIPLY:
            if not hasattr(self.state.player, '_heal_multiplier'):
                self.state.player._heal_multiplier = 1
            self.state.player._heal_multiplier = max(self.state.player._heal_multiplier, value)

        elif effect_type == RelicEffectType.ON_HP_LOSS:
            extra_type = extra.get("type", "")
            if extra_type == "draw_card":
                if self.state.card_manager is not None:
                    self.state.card_manager.draw_cards(value)

        elif effect_type == RelicEffectType.ON_POISON_APPLIED:
            extra_type = extra.get("type", "")
            if extra_type == "extra_poison":
                if not hasattr(self.state.player, '_extra_poison_on_applied'):
                    self.state.player._extra_poison_on_applied = 0
                self.state.player._extra_poison_on_applied += value

        elif effect_type == RelicEffectType.ON_ENEMY_DEATH_POISON_TRANSFER:
            if not hasattr(self.state.player, '_specimen_poison_transfer'):
                self.state.player._specimen_poison_transfer = True

        elif effect_type == RelicEffectType.AT_TURN_END:
            extra_type = extra.get("type", "")
            if extra_type == "choose_3_shuffle_1":
                pass
            elif extra_type == "lose_1_instead_of_all":
                if not hasattr(self.state.player, '_calipers_active'):
                    self.state.player._calipers_active = True

        elif effect_type == RelicEffectType.ON_REST:
            extra_type = extra.get("type", "")
            if extra_type == "heal":
                heal_amt = min(value, self.state.player.max_hp - self.state.player.hp)
                self.state.player.hp += heal_amt

        elif effect_type == RelicEffectType.CONSERVE_ENERGY:
            if not hasattr(self.state.player, '_conserve_energy'):
                self.state.player._conserve_energy = True

        elif effect_type == RelicEffectType.GAIN_GOLD:
            self.state.player.gold = getattr(self.state.player, 'gold', 0) + value

        elif effect_type == RelicEffectType.GAIN_MAX_HP:
            self.state.player.max_hp += value
            amplified_heal = self._apply_heal_amplification(value)
            self.state.player.hp += amplified_heal

        elif effect_type == RelicEffectType.SHOP_PRICE_MODIFIER:
            if not hasattr(self.state.player, '_shop_discount'):
                self.state.player._shop_discount = 0
            self.state.player._shop_discount += abs(value)

        elif effect_type == RelicEffectType.EXTRA_CARD_REWARD:
            extra_type = extra.get("type", "")
            if extra_type == "elite_boss":
                if not hasattr(self.state.player, '_extra_card_rewards'):
                    self.state.player._extra_card_rewards = 0
                self.state.player._extra_card_rewards += value

        elif effect_type == RelicEffectType.ON_PICKUP:
            extra_type = extra.get("type", "")
            if extra_type == "full_restore":
                self.state.player.hp = self.state.player.max_hp
            elif extra_type == "remove_curses":
                pass
            elif extra_type == "remove_cards_from_deck":
                count = extra.get("count", 1)
                exclude_unremovable = extra.get("exclude_unremovable", False)
                self._remove_cards_from_deck(count, exclude_unremovable)
            elif extra_type == "transform_strikes_defends":
                self._transform_strikes_and_defends()
            elif extra_type == "transform_3_cards":
                upgrade = extra.get("upgrade", False)
                self._transform_cards_pickup(upgrade=upgrade)

        elif effect_type == RelicEffectType.AT_TURN_START:
            extra_type = extra.get("type", "")
            if extra_type == "calm":
                self._change_player_stance(StanceType.CALM)
            elif extra_type == "mantra":
                if not hasattr(self.state.player, '_mantra'):
                    self.state.player._mantra = 0
                self.state.player._mantra += value

        elif effect_type == RelicEffectType.AT_BOSS_START:
            extra_type = extra.get("type", "")
            if extra_type == "energy":
                self.state.player.energy += value

        elif effect_type == RelicEffectType.BOTTLED:
            card_type = extra.get("card_type", "")
            if card_type and self.state.card_manager:
                hand = list(self.state.card_manager.hand.cards)
                for card in hand:
                    if card_type == "attack" and card.card_type.value == "ATTACK":
                        BOTTLED_CARDS.add(card.card_id)
                    elif card_type == "skill" and card.card_type.value == "SKILL":
                        BOTTLED_CARDS.add(card.card_id)
                    elif card_type == "power" and card.card_type.value == "POWER":
                        BOTTLED_CARDS.add(card.card_id)

        elif effect_type == RelicEffectType.CARD_REWARD_MODIFIER:
            extra_type = extra.get("type", "")
            if extra_type == "add_other_class_cards":
                if not hasattr(self.state.player, '_add_other_class_cards'):
                    self.state.player._add_other_class_cards = True

        elif effect_type == RelicEffectType.CHANGE_RARE_CHANCE:
            pass

        elif effect_type == RelicEffectType.LIMIT_CARDS_DRAW:
            if not hasattr(self.state.player, '_draw_per_turn_bonus'):
                self.state.player._draw_per_turn_bonus = 0
            self.state.player._draw_per_turn_bonus = max(self.state.player._draw_per_turn_bonus, value)

        elif effect_type == RelicEffectType.POTION_ALWAYS_DROP:
            extra_type = extra.get("type", "")
            if extra_type == "no_potions":
                if not hasattr(self.state.player, '_no_potion_drops'):
                    self.state.player._no_potion_drops = True

        elif effect_type == RelicEffectType.START_WITH_ENERGY:
            self.state.player.energy += value

        elif effect_type == RelicEffectType.ON_REST:
            extra_type = extra.get("type", "")
            if extra_type == "heal":
                heal_amt = min(value, self.state.player.max_hp - self.state.player.hp)
                self.state.player.hp += heal_amt
            elif extra_type == "card_reward":
                pass

        elif effect_type == RelicEffectType.ON_CARD_ADDED:
            extra_type = extra.get("type", "")
            if extra_type == "gold":
                gold_amount = value
                self.state.player.gold = getattr(self.state.player, 'gold', 0) + gold_amount
            elif extra_type == "upgrade_attack":
                pass
            elif extra_type == "upgrade_skill":
                pass
            elif extra_type == "upgrade_power":
                pass

        elif effect_type == RelicEffectType.MODIFY_STRENGTH:
            condition = extra.get("condition", "")
            if condition == "hp_below_50" and self.state.player.hp <= self.state.player.max_hp // 2:
                if not hasattr(self.state.player, '_red_skull_strength'):
                    self.state.player._red_skull_strength = 0
                self.state.player._red_skull_strength = value
                self.state.player.strength += value

        elif effect_type == RelicEffectType.GAIN_THORNS:
            if not hasattr(self.state.player, 'thorns'):
                self.state.player.thorns = 0
            self.state.player.thorns += value

        elif effect_type == RelicEffectType.GAIN_INTANGIBLE:
            if not hasattr(self.state.player, 'intangible'):
                self.state.player.intangible = 0
            self.state.player.intangible += value

        elif effect_type == RelicEffectType.ON_POWER_PLAYED:
            extra_type = extra.get("type", "")
            if extra_type == "random_zero_cost":
                if self.state.card_manager:
                    hand = list(self.state.card_manager.hand.cards)
                    if hand:
                        rng = getattr(self.state, "card_random_rng", None) or self.ai_rng
                        pick = rng.random_int(len(hand) - 1) if rng is not None and len(hand) > 1 else 0
                        card = hand[pick]
                        card.cost_for_turn = 0
                        card.is_cost_modified_for_turn = True

        elif effect_type == RelicEffectType.MODIFY_WEAK:
            if not hasattr(self.state.player, '_paper_crane_weak_mod'):
                self.state.player._paper_crane_weak_mod = True

        elif effect_type == RelicEffectType.ON_EXHAUST_DAMAGE_ALL:
            damage = value
            if self.state.monsters:
                for monster in self.state.monsters:
                    if not monster.is_dead():
                        monster.take_damage(damage)

        elif effect_type == RelicEffectType.IMMUNE_WEAK:
            if not hasattr(self.state.player, '_immune_weak'):
                self.state.player._immune_weak = True

        elif effect_type == RelicEffectType.IMMUNE_FRAIL:
            if not hasattr(self.state.player, '_immune_frail'):
                self.state.player._immune_frail = True

        elif effect_type == RelicEffectType.SCRY_BONUS:
            if not hasattr(self.state.player, '_scry_bonus'):
                self.state.player._scry_bonus = 0
            self.state.player._scry_bonus += value

        elif effect_type == RelicEffectType.ON_DEATH_SAVE:
            extra_type = extra.get("type", "")
            if extra_type == "revive_half_hp":
                if not hasattr(self.state.player, '_lizard_tail_available'):
                    self.state.player._lizard_tail_available = True

        elif effect_type == RelicEffectType.HEAL_PER_POWER:
            if not hasattr(self.state.player, '_heal_per_power'):
                self.state.player._heal_per_power = value

        elif effect_type == RelicEffectType.LIMIT_CARDS_PLAY:
            if not hasattr(self.state.player, '_cards_play_limit'):
                self.state.player._cards_play_limit = 0
            self.state.player._cards_play_limit = max(self.state.player._cards_play_limit, value)

        elif effect_type == RelicEffectType.LIMIT_CARDS_DRAW:
            if not hasattr(self.state.player, '_draw_per_turn_bonus'):
                self.state.player._draw_per_turn_bonus = 0
            self.state.player._draw_per_turn_bonus = max(self.state.player._draw_per_turn_bonus, value)

        elif effect_type == RelicEffectType.ON_VULNERABLE_APPLY:
            extra_type = extra.get("type", "")
            if extra_type == "apply_weak":
                if not hasattr(self.state.player, '_champion_belt_active'):
                    self.state.player._champion_belt_active = True

        elif effect_type == RelicEffectType.FREE_MOVEMENT:
            if not hasattr(self.state.player, '_free_movement'):
                self.state.player._free_movement = 0
            self.state.player._free_movement += value

        elif effect_type == RelicEffectType.ON_CHEST_OPEN:
            extra_type = extra.get("type", "")
            if extra_type == "add_curse":
                if not hasattr(self.state.player, '_cursed_key_curse'):
                    self.state.player._cursed_key_curse = True

        elif effect_type == RelicEffectType.BLOCK_INTENT:
            if not hasattr(self.state.player, '_block_intent'):
                self.state.player._block_intent = True

        elif effect_type == RelicEffectType.ON_EXIT_CALM_ENERGY:
            if not hasattr(self.state.player, '_exit_calm_energy'):
                self.state.player._exit_calm_energy = value

        elif effect_type == RelicEffectType.CARD_REWARD_MAX_HP:
            if not hasattr(self.state.player, '_singing_bowl_hp'):
                self.state.player._singing_bowl_hp = value
            else:
                self.state.player._singing_bowl_hp += value

        elif effect_type == RelicEffectType.REST_HEAL_BONUS:
            heal_bonus = min(value, self.state.player.max_hp - self.state.player.hp)
            self.state.player.hp += heal_bonus

        elif effect_type == RelicEffectType.REST_SITE_STRENGTH:
            if not hasattr(self.state.player, '_rest_site_strength'):
                self.state.player._rest_site_strength = value
            else:
                self.state.player._rest_site_strength += value

        elif effect_type == RelicEffectType.REST_SITE_REMOVE:
            if not hasattr(self.state.player, '_rest_site_remove'):
                self.state.player._rest_site_remove = value

        elif effect_type == RelicEffectType.REST_SITE_DIG:
            if not hasattr(self.state.player, '_rest_site_dig'):
                self.state.player._rest_site_dig = True

        elif effect_type == RelicEffectType.ON_FLOOR_CLIMB:
            gold_amount = value
            self.state.player.gold = getattr(self.state.player, 'gold', 0) + gold_amount

        elif effect_type == RelicEffectType.ON_SHOP_ENTER:
            heal_amount = value
            self.state.player.hp = min(self.state.player.max_hp, self.state.player.hp + heal_amount)

        elif effect_type == RelicEffectType.ON_GAIN_GOLD:
            extra_type = extra.get("type", "")
            if extra_type == "heal":
                heal_amount = value
                self.state.player.hp = min(self.state.player.max_hp, self.state.player.hp + heal_amount)

        elif effect_type == RelicEffectType.ON_POTION_USE:
            heal_amount = value
            self.state.player.hp = min(self.state.player.max_hp, self.state.player.hp + heal_amount)

        elif effect_type == RelicEffectType.GOLD_MULTIPLY:
            if not hasattr(self.state.player, '_gold_multiplier'):
                self.state.player._gold_multiplier = 0
            self.state.player._gold_multiplier += value

        elif effect_type == RelicEffectType.CARD_REMOVE_DISCOUNT:
            if not hasattr(self.state.player, '_card_remove_discount'):
                self.state.player._card_remove_discount = value

        elif effect_type == RelicEffectType.SHOP_NO_SELL_OUT:
            if not hasattr(self.state.player, '_shop_no_sell_out'):
                self.state.player._shop_no_sell_out = True

        elif effect_type == RelicEffectType.POTION_GAIN_DISABLED:
            if not hasattr(self.state.player, '_potion_gain_disabled'):
                self.state.player._potion_gain_disabled = True

        elif effect_type == RelicEffectType.GOLD_DISABLED:
            if not hasattr(self.state.player, '_gold_disabled'):
                self.state.player._gold_disabled = True

        elif effect_type == RelicEffectType.REST_HEAL_DISABLED:
            if not hasattr(self.state.player, '_rest_heal_disabled'):
                self.state.player._rest_heal_disabled = True

        elif effect_type == RelicEffectType.REST_SITE_FORGE_DISABLED:
            if not hasattr(self.state.player, '_rest_site_forge_disabled'):
                self.state.player._rest_site_forge_disabled = True

        elif effect_type == RelicEffectType.CANT_HEAL:
            if not hasattr(self.state.player, '_cant_heal'):
                self.state.player._cant_heal = True

        elif effect_type == RelicEffectType.AT_BOSS_ELITE_START:
            extra_type = extra.get("type", "")
            if extra_type == "energy":
                self.state.player.energy += value
            elif extra_type == "strength":
                self.state.player.strength += value

        elif effect_type == RelicEffectType.AT_TURN_START_SPECIFIC:
            extra_type = extra.get("type", "")
            if extra_type == "energy":
                self.state.player.energy += value

        elif effect_type == RelicEffectType.AT_TURN_END_HAND_BLOCK:
            if self.state.card_manager:
                hand_size = len(self.state.card_manager.hand.cards)
                if hand_size > 0:
                    self.state.player.gain_block(hand_size)

        elif effect_type == RelicEffectType.AT_TURN_END_EMPTY_ORB:
            self._bind_player_orbs()
            if len(self.state.player.orbs) == 0:
                from sts_py.engine.combat.orbs import FrostOrb
                self._channel_orb(FrostOrb())

        elif effect_type == RelicEffectType.AT_TURN_END_NO_DISCARD:
            return

        elif effect_type == RelicEffectType.ORB_PASSIVE_MULTIPLY:
            if not hasattr(self.state.player, '_orb_passive_multiply'):
                self.state.player._orb_passive_multiply = 0
            self.state.player._orb_passive_multiply += value

        elif effect_type == RelicEffectType.ELITE_REWARD_RELICS:
            if not hasattr(self.state.player, '_elite_reward_relics'):
                self.state.player._elite_reward_relics = 0
            self.state.player._elite_reward_relics += value

        elif effect_type == RelicEffectType.AT_FIRST_TURN_DRAW:
            if not hasattr(self.state.player, '_first_turn_draw'):
                self.state.player._first_turn_draw = 0
            self.state.player._first_turn_draw += value

        elif effect_type == RelicEffectType.ON_FIRST_DISCARD_PER_TURN:
            if not getattr(self.state.player, "_first_discard_triggered_this_turn", False):
                self.state.player.energy += value
                if self.state.card_manager is not None:
                    self.state.card_manager.set_energy(self.state.player.energy)
                self.state.player._first_discard_triggered_this_turn = True

        elif effect_type == RelicEffectType.START_WITH_SHIVS:
            if not hasattr(self.state.player, '_start_shivs'):
                self.state.player._start_shivs = 0
            self.state.player._start_shivs += value

        elif effect_type == RelicEffectType.ARTIFACT_START:
            if not hasattr(self.state.player, '_artifact_stacks'):
                self.state.player._artifact_stacks = 0
            self.state.player._artifact_stacks += value

        elif effect_type == RelicEffectType.FIRST_ATTACK_TWICE:
            if not hasattr(self.state.player, '_first_attack_twice'):
                self.state.player._first_attack_twice = True

        elif effect_type == RelicEffectType.ZERO_COST_ATTACK_BONUS_DAMAGE:
            if not hasattr(self.state.player, '_zero_cost_attack_bonus'):
                self.state.player._zero_cost_attack_bonus = 0
            self.state.player._zero_cost_attack_bonus += value

        elif effect_type == RelicEffectType.ZERO_COST_BONUS_DAMAGE:
            if not hasattr(self.state.player, '_zero_cost_bonus'):
                self.state.player._zero_cost_bonus = 0
            self.state.player._zero_cost_bonus += value

        elif effect_type == RelicEffectType.STRIKE_DAMAGE_BONUS:
            if not hasattr(self.state.player, '_strike_damage_bonus'):
                self.state.player._strike_damage_bonus = 0
            self.state.player._strike_damage_bonus += value

        elif effect_type == RelicEffectType.EVERY_N_TURNS:
            if not hasattr(self.state.player, '_turn_counter'):
                self.state.player._turn_counter = 0
            self.state.player._turn_counter += 1
            extra_type = extra.get("type", "")
            if self.state.player._turn_counter % value == 0:
                if extra_type == "damage_all":
                    damage_amount = extra.get("amount", 0)
                    for monster in self.state.monsters:
                        if not monster.is_dead():
                            monster.take_damage(damage_amount)
                elif extra_type == "intangible":
                    intangible_amount = extra.get("amount", 1)
                    self.state.player.intangible += intangible_amount
                elif extra_type == "block":
                    block_amount = extra.get("amount", 18)
                    self.state.player.gain_block(block_amount)

        elif effect_type == RelicEffectType.EVERY_2_TURNS:
            if not hasattr(self.state.player, '_every_2_turn_counter'):
                self.state.player._every_2_turn_counter = 0
            self.state.player._every_2_turn_counter += 1
            if self.state.player._every_2_turn_counter % 2 == 0:
                extra_type = extra.get("type", "")
                if extra_type == "orb_slot":
                    self.state.player.max_orbs += 1
                    self._bind_player_orbs()

        elif effect_type == RelicEffectType.ON_SHUFFLE:
            extra_type = extra.get("type", "")
            if extra_type == "energy":
                if not hasattr(self.state.player, '_sundial_energy'):
                    self.state.player._sundial_energy = 0
                self.state.player._sundial_energy += 1
                if self.state.player._sundial_energy % value == 0:
                    amount = extra.get("amount", 2)
                    self.state.player.energy += amount
            elif extra_type == "block":
                if not hasattr(self.state.player, '_abacus_block'):
                    self.state.player._abacus_block = 0
                self.state.player._abacus_block += value

        elif effect_type == RelicEffectType.ON_EXHAUST:
            extra_type = extra.get("type", "")
            if extra_type == "damage_all":
                if not hasattr(self.state.player, '_charons_ashes_damage'):
                    self.state.player._charons_ashes_damage = value

        elif effect_type == RelicEffectType.CARD_COPY:
            if not hasattr(self.state.player, '_card_copy_available'):
                self.state.player._card_copy_available = True

        elif effect_type == RelicEffectType.UPGRADE_RANDOM:
            if not hasattr(self.state.player, '_upgrade_random_count'):
                self.state.player._upgrade_random_count = 0
            self.state.player._upgrade_random_count += value

        elif effect_type == RelicEffectType.GAIN_POTION:
            if not hasattr(self.state.player, '_potion_slots'):
                self.state.player._potion_slots = 0
            self.state.player._potion_slots += value

        elif effect_type == RelicEffectType.ELITE_HP_MODIFIER:
            if not hasattr(self.state.player, '_elite_hp_modifier'):
                self.state.player._elite_hp_modifier = 0
            self.state.player._elite_hp_modifier += value

        elif effect_type == RelicEffectType.CHANGE_RARE_CHANCE:
            if not hasattr(self.state.player, '_rare_chance_multiplier'):
                self.state.player._rare_chance_multiplier = 1
            self.state.player._rare_chance_multiplier *= value

        elif effect_type == RelicEffectType.ON_QUESTION_ROOM:
            gold_amount = value
            self.state.player.gold = getattr(self.state.player, 'gold', 0) + gold_amount

        elif effect_type == RelicEffectType.TREASURE_ROOM_EVERY_N_QUESTION:
            if not hasattr(self.state.player, '_treasure_every_n_question'):
                self.state.player._treasure_every_n_question = value

        elif effect_type == RelicEffectType.STACKABLE_DEBUFF:
            if not hasattr(self.state.player, '_stackable_debuff'):
                self.state.player._stackable_debuff = True

        elif effect_type == RelicEffectType.START_WITH_CURSE:
            if not hasattr(self.state.player, '_start_with_curse'):
                self.state.player._start_with_curse = True

        elif effect_type == RelicEffectType.FIRST_COMBAT_HP_ONE:
            if not hasattr(self.state.player, '_first_combat_hp_one'):
                self.state.player._first_combat_hp_one = value

        elif effect_type == RelicEffectType.CARD_CHOICE_THREE:
            if not hasattr(self.state.player, '_card_choice_three'):
                self.state.player._card_choice_three = True

        elif effect_type == RelicEffectType.APPLY_WEAK_START:
            if not hasattr(self.state.player, '_apply_weak_start'):
                self.state.player._apply_weak_start = True

        elif effect_type == RelicEffectType.GAIN_MAX_HP:
            self.state.player.max_hp += value
            amplified_heal = self._apply_heal_amplification(value)
            self.state.player.hp += amplified_heal

        elif effect_type == RelicEffectType.GAIN_GOLD:
            self.state.player.gold = getattr(self.state.player, 'gold', 0) + value

        elif effect_type == RelicEffectType.START_WITH_BLOCK:
            self.state.player.gain_block(value)

        elif effect_type == RelicEffectType.REPLACE_STARTER_RELIC:
            replaced = extra.get("replaced", "")
            if not hasattr(self.state.player, '_replaced_relics'):
                self.state.player._replaced_relics = []
            self.state.player._replaced_relics.append(replaced)

        elif effect_type == RelicEffectType.ON_VICTORY:
            extra_type = extra.get("type", "")
            if extra_type == "heal" or target == "player":
                heal_amount = min(value, self.state.player.max_hp - self.state.player.hp)
                self.state.player.hp += heal_amount

        elif effect_type == RelicEffectType.BOTTLED:
            card_type = extra.get("card_type", "")
            if card_type and self.state.card_manager:
                hand = list(self.state.card_manager.hand.cards)
                for card in hand:
                    if card_type == "attack" and card.card_type.value == "ATTACK":
                        BOTTLED_CARDS.add(card.card_id)
                    elif card_type == "skill" and card.card_type.value == "SKILL":
                        BOTTLED_CARDS.add(card.card_id)
                    elif card_type == "power" and card.card_type.value == "POWER":
                        BOTTLED_CARDS.add(card.card_id)

        elif effect_type == RelicEffectType.CURSE_PLAYABLE:
            if not hasattr(self.state.player, '_curse_playable'):
                self.state.player._curse_playable = True

        elif effect_type == RelicEffectType.CURSE_NEGATE:
            if not hasattr(self.state.player, '_curse_negate_count'):
                self.state.player._curse_negate_count = 0
            self.state.player._curse_negate_count += value

        elif effect_type == RelicEffectType.CURSE_NEGATE_TRIGGER:
            if not hasattr(self.state.player, '_curse_negate_triggers'):
                self.state.player._curse_negate_triggers = value

        elif effect_type == RelicEffectType.ON_TRAP_COMBAT:
            if not hasattr(self.state.player, '_avoid_trap'):
                self.state.player._avoid_trap = True

        elif effect_type == RelicEffectType.AT_BATTLE_START_ENERGY:
            self.state.player.energy += value

        elif effect_type == RelicEffectType.FIRST_ATTACK_COMBAT:
            if not hasattr(self.state.player, '_first_attack_triggered'):
                self.state.player._first_attack_triggered = False
            if not self.state.player._first_attack_triggered:
                extra_type = extra.get("type", "")
                if extra_type == "bonus_damage":
                    self.state.player._first_attack_bonus_damage = value

        elif effect_type == RelicEffectType.AT_TURN_START_NO_ATTACK:
            extra_type = extra.get("type", "")
            if extra_type == "energy":
                if not self.state.player._has_attacked_this_turn:
                    self.state.player.energy += value

        elif effect_type == RelicEffectType.ON_HP_LOSS:
            extra_type = extra.get("type", "")
            if extra_type == "draw":
                if self.state.card_manager is not None:
                    self.state.card_manager.draw_cards(value)
            elif extra_type == "block_next_turn":
                if not hasattr(self.state.player, '_delayed_block'):
                    self.state.player._delayed_block = 0
                self.state.player._delayed_block += value

        elif effect_type == RelicEffectType.ON_POISON_APPLIED:
            extra_type = extra.get("type", "")
            if extra_type == "extra_poison":
                if not hasattr(self.state.player, '_extra_poison'):
                    self.state.player._extra_poison = 0
                self.state.player._extra_poison += value

        elif effect_type == RelicEffectType.MODIFY_MIN_DAMAGE:
            extra_type = extra.get("type", "")
            if extra_type == "min_damage_receive":
                max_damage = extra.get("max", 5)
                if not hasattr(self.state.player, '_torii_active'):
                    self.state.player._torii_active = True
                    self.state.player._torii_max_damage = max_damage

        elif effect_type == RelicEffectType.EXTRA_CARD_REWARD:
            extra_type = extra.get("type", "")
            if extra_type == "elite_boss":
                if not hasattr(self.state.player, '_extra_card_rewards'):
                    self.state.player._extra_card_rewards = 0
                self.state.player._extra_card_rewards += value
            else:
                if not hasattr(self.state.player, '_extra_card_rewards'):
                    self.state.player._extra_card_rewards = 0
                self.state.player._extra_card_rewards += value

        elif effect_type == RelicEffectType.CHEST_RELICS:
            if not hasattr(self.state.player, '_chest_extra_relics'):
                self.state.player._chest_extra_relics = 0
            self.state.player._chest_extra_relics += value

        elif effect_type == RelicEffectType.CARD_REWARD_REDUCE:
            if not hasattr(self.state.player, '_card_reward_reduce'):
                self.state.player._card_reward_reduce = 0
            self.state.player._card_reward_reduce += value

        elif effect_type == RelicEffectType.AT_BOSS_START:
            extra_type = extra.get("type", "")
            if extra_type == "heal":
                heal_amount = min(value, self.state.player.max_hp - self.state.player.hp)
                self.state.player.hp += heal_amount
            elif extra_type == "energy":
                self.state.player.energy += value

        elif effect_type == RelicEffectType.AT_BOSS_ELITE_START:
            extra_type = extra.get("type", "")
            if extra_type == "energy":
                self.state.player.energy += value
            elif extra_type == "strength":
                self.state.player.strength += value

        elif effect_type == RelicEffectType.ON_CARD_ADDED:
            extra_type = extra.get("type", "")
            if extra_type == "upgrade_attack":
                if not hasattr(self.state.player, '_upgrade_attack_on_add'):
                    self.state.player._upgrade_attack_on_add = True
            elif extra_type == "upgrade_skill":
                if not hasattr(self.state.player, '_upgrade_skill_on_add'):
                    self.state.player._upgrade_skill_on_add = True
            elif extra_type == "upgrade_power":
                if not hasattr(self.state.player, '_upgrade_power_on_add'):
                    self.state.player._upgrade_power_on_add = True
            elif extra_type == "gold":
                gold_amount = value
                self.state.player.gold = getattr(self.state.player, 'gold', 0) + gold_amount

        elif effect_type == RelicEffectType.ON_DAMAGE:
            extra_type = extra.get("type", "")
            if extra_type == "extra_poison":
                if not hasattr(self.state.player, '_extra_poison_on_damage'):
                    self.state.player._extra_poison_on_damage = 0
                self.state.player._extra_poison_on_damage += value

        elif effect_type == RelicEffectType.MODIFY_DAMAGE:
            extra_type = extra.get("type", "")
            if extra_type == "min_damage_receive":
                if not hasattr(self.state.player, '_torii_active'):
                    self.state.player._torii_active = True
                    self.state.player._torii_max_damage = extra.get("max", 5)

        elif effect_type == RelicEffectType.ON_ENEMY_DEATH:
            extra_type = extra.get("type", "")
            if extra_type == "energy_draw":
                self.state.player.energy += extra.get("energy", 1)
                if self.state.card_manager:
                    self.state.card_manager.draw_cards(extra.get("draw", 1))

        elif effect_type == RelicEffectType.ON_EXHAUST_ADD_RANDOM:
            if self.state.card_manager is None:
                return
            from sts_py.engine.content.cards_min import CARD_DEFS_BY_CHARACTER, CardRarity

            character_class = str(getattr(self.state.player, "character_class", "IRONCLAD") or "IRONCLAD").upper()
            defs = CARD_DEFS_BY_CHARACTER.get(character_class, CARD_DEFS_BY_CHARACTER["IRONCLAD"])
            candidates = [
                card_def.id
                for card_def in defs.values()
                if card_def.rarity in {CardRarity.COMMON, CardRarity.UNCOMMON, CardRarity.RARE}
            ]
            if not candidates:
                return
            if self.ai_rng is not None and len(candidates) > 1:
                card_id = candidates[self.ai_rng.random_int(len(candidates) - 1)]
            else:
                card_id = candidates[0]
            self.state.card_manager.generate_cards_to_hand(card_id, 1)

        elif effect_type == RelicEffectType.AT_BATTLE_START_BUFFER:
            from sts_py.engine.combat.powers import create_power

            self.state.player.add_power(create_power("Buffer", value, "player"))

        elif effect_type == RelicEffectType.AT_BATTLE_START_DISCARD_DRAW:
            if not hasattr(self.state.player, '_battle_start_discard_draw'):
                self.state.player._battle_start_discard_draw = True

        elif effect_type == RelicEffectType.MANA_GAIN_DISABLED:
            if not hasattr(self.state.player, '_mana_gain_disabled'):
                self.state.player._mana_gain_disabled = True

        elif effect_type == RelicEffectType.CONSERVE_ENERGY:
            if not hasattr(self.state.player, '_conserve_energy'):
                self.state.player._conserve_energy = True

        elif effect_type == RelicEffectType.HEAL_MULTIPLY:
            if not hasattr(self.state.player, '_heal_multiplier'):
                self.state.player._heal_multiplier = 1
            self.state.player._heal_multiplier = max(self.state.player._heal_multiplier, value)

        elif effect_type == RelicEffectType.ON_DEATH_SAVE:
            extra_type = extra.get("type", "")
            if extra_type == "revive_half_hp":
                if not hasattr(self.state.player, '_lizard_tail'):
                    self.state.player._lizard_tail = True

        elif effect_type == RelicEffectType.EMPTY_HAND_DRAW:
            if self.state.card_manager and len(self.state.card_manager.hand.cards) == 0:
                self.state.card_manager.draw_cards(value)

        elif effect_type == RelicEffectType.ON_DISCARD:
            extra_type = extra.get("type", "")
            if extra_type == "damage_random":
                if self.state.monsters:
                    import random
                    living = [m for m in self.state.monsters if not m.is_dead()]
                    if living:
                        target = random.choice(living)
                        target.take_damage(value)
            elif extra_type == "block":
                self.state.player.gain_block(value)
            elif extra_type == "energy":
                self.state.player.energy += value

        elif effect_type == RelicEffectType.ON_SHUFFLE:
            extra_type = extra.get("type", "")
            if extra_type == "scry":
                if not hasattr(self.state.player, '_scry_on_shuffle'):
                    self.state.player._scry_on_shuffle = 0
                self.state.player._scry_on_shuffle += value

        elif effect_type == RelicEffectType.SCRY_ON_SHUFFLE:
            if not hasattr(self.state.player, '_scry_on_shuffle'):
                self.state.player._scry_on_shuffle = 0
            self.state.player._scry_on_shuffle += value

        elif effect_type == RelicEffectType.MANA_GAIN_DISABLED:
            if not hasattr(self.state.player, '_mana_gain_disabled'):
                self.state.player._mana_gain_disabled = True

        elif effect_type == RelicEffectType.DEBUFF_CLEAR:
            if not hasattr(self.state.player, '_debuff_clear'):
                self.state.player._debuff_clear = True

        elif effect_type == RelicEffectType.ON_CURSE_RECEIVED:
            extra_type = extra.get("type", "")
            if extra_type == "max_hp":
                if not hasattr(self.state.player, '_curse_max_hp'):
                    self.state.player._curse_max_hp = 0
                self.state.player._curse_max_hp += value

        elif effect_type == RelicEffectType.CURSE_STRENGTH:
            if not hasattr(self.state.player, '_curse_strength'):
                self.state.player._curse_strength = 0
            self.state.player._curse_strength += value

        elif effect_type == RelicEffectType.START_WITH_STRENGTH_PER_CURSE:
            if not hasattr(self.state.player, '_strength_per_curse'):
                self.state.player._strength_per_curse = value

        elif effect_type == RelicEffectType.AT_TURN_START:
            extra_type = extra.get("type", "")
            if extra_type == "damage":
                for monster in self.state.monsters:
                    if not monster.is_dead():
                        monster.take_damage(value)
            elif extra_type == "calm":
                self._change_player_stance(StanceType.CALM)
            elif extra_type == "wrath":
                self._change_player_stance(StanceType.WRATH)
            elif extra_type == "mantra":
                if not hasattr(self.state.player, '_mantra'):
                    self.state.player._mantra = 0
                self.state.player._mantra += value
            elif extra_type == "draw":
                if self.state.card_manager:
                    self.state.card_manager.draw_cards(value)
            elif extra_type == "weak":
                from sts_py.engine.combat.powers import WeakPower
                for monster in self.state.monsters:
                    monster.powers.add_power(WeakPower(amount=value))
            elif extra_type == "vulnerable":
                from sts_py.engine.combat.powers import VulnerablePower
                for monster in self.state.monsters:
                    monster.powers.add_power(VulnerablePower(amount=value))

        elif effect_type == RelicEffectType.AT_TURN_END:
            extra_type = extra.get("type", "")
            if extra_type == "block":
                condition = extra.get("condition", "")
                if condition == "no_block":
                    if self.state.player.block > 0:
                        return
                self.state.player.gain_block(value)
            elif extra_type == "damage_all_specific":
                for monster in self.state.monsters:
                    if not monster.is_dead():
                        monster.take_damage(value)
            elif extra_type == "choose_3_shuffle_1":
                if not hasattr(self.state.player, '_card_choice_3'):
                    self.state.player._card_choice_3 = True
            elif extra_type == "lose_1_instead_of_all":
                if not hasattr(self.state.player, '_calipers'):
                    self.state.player._calipers = True

        elif effect_type == RelicEffectType.ON_ATTACK:
            extra_type = extra.get("type", "")
            if extra_type == "temp_dexterity":
                if not hasattr(self.state.player, '_temp_dex'):
                    self.state.player._temp_dex = 0
                self.state.player._temp_dex += value

        elif effect_type == RelicEffectType.MIRACLE:
            if not hasattr(self.state.player, '_miracle'):
                self.state.player._miracle = True

        elif effect_type == RelicEffectType.CARD_REWARD:
            if not hasattr(self.state.player, '_card_reward_extra'):
                self.state.player._card_reward_extra = 0
            self.state.player._card_reward_extra += value

        elif effect_type == RelicEffectType.GOLD_PER_FLOOR:
            if not hasattr(self.state.player, '_gold_per_floor'):
                self.state.player._gold_per_floor = 0
            self.state.player._gold_per_floor += value

        elif effect_type == RelicEffectType.SCYTHE:
            if not hasattr(self.state.player, '_scythe'):
                self.state.player._scythe = True

        elif effect_type == RelicEffectType.CHANCE_FOR_FREE_ATTACK:
            if not hasattr(self.state.player, '_free_attack_chance'):
                self.state.player._free_attack_chance = 0
            self.state.player._free_attack_chance += value

        elif effect_type == RelicEffectType.CHANCE_FOR_FREE_SKILL:
            if not hasattr(self.state.player, '_free_skill_chance'):
                self.state.player._free_skill_chance = 0
            self.state.player._free_skill_chance += value

        elif effect_type == RelicEffectType.HEAL_PER_POWER:
            if not hasattr(self.state.player, '_heal_per_power'):
                self.state.player._heal_per_power = 0
            self.state.player._heal_per_power += value

        elif effect_type == RelicEffectType.DEBUFF_CLEAR:
            if not hasattr(self.state.player, '_debuff_clear_available'):
                self.state.player._debuff_clear_available = True

        elif effect_type == RelicEffectType.ON_REST_ADD_CARD:
            if not hasattr(self.state.player, '_rest_add_card'):
                self.state.player._rest_add_card = True

        elif effect_type == RelicEffectType.REST_SITE_TRANSFORM:
            if not hasattr(self.state.player, '_rest_transform'):
                self.state.player._rest_transform = True

        elif effect_type == RelicEffectType.REST_SITE_UPGRADE:
            if not hasattr(self.state.player, '_rest_upgrade'):
                self.state.player._rest_upgrade = True

        elif effect_type == RelicEffectType.GAIN_MANTRA_PER_TURN:
            from sts_py.engine.combat.powers import create_power

            self.state.player.add_power(create_power("Mantra", value, "player"))

        elif effect_type == RelicEffectType.REMOVE_CARDS_FROM_DECK:
            if not hasattr(self.state.player, '_remove_cards'):
                self.state.player._remove_cards = 0
            self.state.player._remove_cards += value

        elif effect_type == RelicEffectType.DECK_TRANSFORM:
            if not hasattr(self.state.player, '_deck_transform'):
                self.state.player._deck_transform = True

        elif effect_type == RelicEffectType.DECK_TRANSFORM_AND_UPGRADE:
            if not hasattr(self.state.player, '_deck_transform_upgrade'):
                self.state.player._deck_transform_upgrade = True

        elif effect_type == RelicEffectType.END_OF_TURN_DAMAGE_ALL_SPECIFIC:
            if not hasattr(self.state.player, '_end_turn_damage_all'):
                self.state.player._end_turn_damage_all = 0
            self.state.player._end_turn_damage_all += value

        elif effect_type == RelicEffectType.ON_EXIT_CALM:
            if not hasattr(self.state.player, '_exit_calm_bonus'):
                self.state.player._exit_calm_bonus = True

        elif effect_type == RelicEffectType.ON_ATTACK_DAMAGE_DEALT:
            extra_type = extra.get("type", "")
            if extra_type == "bonus":
                if not hasattr(self.state.player, '_attack_damage_bonus'):
                    self.state.player._attack_damage_bonus = 0
                self.state.player._attack_damage_bonus += value

    def _process_curse_effects_end_of_turn(self) -> None:
        """Process curse card effects at end of turn.

        Decay: 回合结束时受到2点伤害
        Doubt: 回合结束时获得1层虚弱
        Shame: 回合结束时获得1层易伤
        Regret: 回合结束时每有一张手牌就失去1点生命
        """
        from sts_py.engine.content.cards_min import CurseEffectType
        from sts_py.engine.combat.powers import create_power

        if self.state.card_manager is None:
            return

        hand = self.state.card_manager.hand.cards
        hand_size = len(hand)
        cards_to_discard = []

        for card in hand:
            if card.card_type.value not in ("CURSE", "STATUS"):
                continue

            effect_type = card.curse_effect_type
            effect_value = card.curse_effect_value

            if effect_type == CurseEffectType.END_OF_TURN_DAMAGE:
                self._deal_damage_to_player(effect_value)
            elif effect_type == CurseEffectType.END_OF_TURN_WEAK:
                self.state.player.add_power(create_power("Weak", effect_value, "player"))
            elif effect_type == CurseEffectType.END_OF_TURN_VULNERABLE:
                self.state.player.add_power(create_power("Vulnerable", effect_value, "player"))
            elif effect_type == CurseEffectType.END_OF_TURN_FRAIL:
                self.state.player.add_power(create_power("Frail", effect_value, "player"))
            elif effect_type == CurseEffectType.REGRET_EFFECT:
                self._deal_damage_to_player(hand_size * effect_value)
            elif effect_type == CurseEffectType.INNATE_COPY_AT_END:
                from sts_py.engine.content.card_instance import CardInstance
                copy_card = CardInstance(card.card_id)
                self.state.card_manager.draw_pile.cards.insert(0, copy_card)

        for card in cards_to_discard:
            if card in self.state.card_manager.hand.cards:
                self.state.card_manager.hand.cards.remove(card)
                self.state.card_manager.discard_pile.cards.append(card)

        vacuous_to_remove = []
        for card in hand:
            if card.card_type.value in ("CURSE", "STATUS") and card.curse_effect_type == CurseEffectType.VACUOUS:
                vacuous_to_remove.append(card)

        for card in vacuous_to_remove:
            self.state.card_manager.hand.cards.remove(card)
            self.state.card_manager.exhaust_pile.cards.append(card)

    def _deal_damage_to_player(self, damage: int) -> None:
        """Deal damage to player, applying thorns etc."""
        if self.state.player.block > 0:
            blocked_damage = min(self.state.player.block, damage)
            self.state.player.block -= blocked_damage
            damage -= blocked_damage

        if damage > 0:
            self.state.player.hp -= damage
            self._trigger_relic_effects("on_hp_loss")

            if self.state.player.hp <= 0:
                self.state.player.hp = 0
                self._try_lizard_tail_revive()

    def _try_lizard_tail_revive(self) -> None:
        """Try to revive player with Lizard Tail relic.

        Lizard Tail: When taking fatal damage, heal to 50% (75% with Magic Flower in combat).
        """
        if not hasattr(self.state.player, '_lizard_tail_available') or not self.state.player._lizard_tail_available:
            return

        if not self._has_relic("LizardTail"):
            return

        heal_percent = self._get_magic_flower_multiplier()
        heal_percent = 0.75 if heal_percent == 1.5 else 0.50
        heal_amount = int(self.state.player.max_hp * heal_percent)
        self.state.player.hp = heal_amount
        self.state.player._lizard_tail_available = False

    def _has_curse_playable_relic(self) -> bool:
        """Check if player has a relic that allows playing curses."""
        for relic_id in self.relics:
            from sts_py.engine.content.relics import get_relic_by_id, RelicEffectType
            relic_def = get_relic_by_id(relic_id)
            if relic_def and relic_def.effects:
                for effect in relic_def.effects:
                    if effect.effect_type == RelicEffectType.CURSE_PLAYABLE:
                        return True
        return False

    def _execute_curse_card(self, card, target_idx) -> int:
        """Execute a curse card (e.g., Blue Candle effect).

        Blue Candle: 打出诅咒失去1HP并消耗诅咒。
        """
        self._deal_damage_to_player(1)
        return 1

    def _execute_normal_card(self, card, target_idx) -> int:
        """Execute a normal (non-curse) card."""
        akabeko_bonus = 0
        if card.is_attack() and not self.state.player._first_attack_triggered:
            self.state.player._first_attack_triggered = True
            akabeko_bonus = getattr(self.state.player, '_first_attack_bonus_damage', 0)

        if card.is_attack():
            self._trigger_relic_effects("on_attack")

        _, energy_cost = execute_card(card, self.state, self.state.player, target_idx)
        self._process_monster_deaths_after_card_resolution()

        if akabeko_bonus > 0 and target_idx is not None:
            monster = self.state.monsters[target_idx]
            if not monster.is_dead():
                monster.take_damage(akabeko_bonus)
        self._process_monster_deaths_after_card_resolution()

        return energy_cost

    def _handle_player_discard_from_hand(self, discarded_card) -> None:
        if self.state.card_manager is None:
            return

        self.state.card_manager.discard_pile.add(discarded_card)

        if discarded_card.card_id == "Reflex":
            self.state.card_manager.draw_cards(discarded_card.magic_number)
        elif discarded_card.card_id == "Tactician":
            self.state.player.energy += discarded_card.magic_number
            self.state.card_manager.set_energy(self.state.player.energy)

        self.state.player._discards_this_turn = int(getattr(self.state.player, "_discards_this_turn", 0) or 0) + 1
        self.state.player._discards_this_combat = int(getattr(self.state.player, "_discards_this_combat", 0) or 0) + 1
        if hasattr(self.state.card_manager, "on_player_discard_from_hand"):
            self.state.card_manager.on_player_discard_from_hand(1)

        self._trigger_relic_effects("on_discard")
        self._process_monster_deaths_after_card_resolution()

    def _apply_normality_limit(self) -> None:
        """Apply Normality curse effect at start of turn.

        Normality: 限制每回合只能打出3张牌。
        """
        from sts_py.engine.content.cards_min import CurseEffectType

        if self.state.card_manager is None:
            return

        hand = self.state.card_manager.hand.cards
        has_normality = False
        normality_limit = 0

        for card in hand:
            if card.card_type.value in ("CURSE", "STATUS") and card.curse_effect_type == CurseEffectType.LIMIT_CARDS_PER_TURN:
                has_normality = True
                normality_limit = card.curse_effect_value
                break

        if has_normality:
            self.state.player._normality_locked = True
            self.state.player._normality_limit = normality_limit
        else:
            self.state.player._normality_locked = False
            self.state.player._normality_limit = 0

    def _process_pain_curse_effect(self) -> None:
        """Process Pain curse effect when other cards are played.

        Pain: 当在手牌中时，每打出一张其他牌，失去1生命。
        """
        from sts_py.engine.content.cards_min import CurseEffectType

        if self.state.card_manager is None:
            return

        hand = self.state.card_manager.hand.cards
        for card in hand:
            if card.card_type.value in ("CURSE", "STATUS") and card.curse_effect_type == CurseEffectType.ON_CARD_PLAYED_LOSE_HP:
                self._deal_damage_to_player(card.curse_effect_value)

    def _end_monster_turn(self) -> None:
        for monster in self.state.monsters:
            if not monster.is_dead():
                monster.powers.at_end_of_turn(monster, is_player=False)
                ritual_gain = monster.powers.get_ritual_strength_gain()
                if ritual_gain > 0:
                    from sts_py.engine.combat.powers import RitualPower
                    monster.gain_strength(ritual_gain)
                    for power in monster.powers.powers:
                        if isinstance(power, RitualPower):
                            power.skip_first = False

                monster.powers.at_end_of_round()
                if hasattr(monster, "on_end_of_round"):
                    monster.on_end_of_round()

                monster.roll_move(self.ai_rng)

        if not (self.state.player.barricade_active or self.state.player.blur_active):
            self.state.player.block = 0

        player_powers = self.state.player.powers
        demon_form_str = player_powers.get_demon_form_strength()
        if demon_form_str > 0:
            from sts_py.engine.combat.powers import create_power
            self.state.player.add_power(create_power("Strength", demon_form_str, "player"))
            self.state.player.strength += demon_form_str
            
        regen_heal = player_powers.get_regen_heal()
        if regen_heal > 0:
            self.state.player.hp = min(self.state.player.max_hp, self.state.player.hp + regen_heal)

        # Remove Flex temporary strength at end of turn
        flex_amount = getattr(self.state.player, '_flex_amount', 0)
        if flex_amount > 0:
            self.state.player.strength -= flex_amount
            from sts_py.engine.combat.powers import create_power
            self.state.player.add_power(create_power("Strength", -flex_amount, "player"))
            self.state.player._flex_amount = 0

        self.state.player.powers.at_end_of_round()
        self.state.player.blur_active = self.state.player.powers.has_power("Blur")
        self._trigger_relic_effects("at_turn_end")
        self._process_curse_effects_end_of_turn()

        if int(getattr(self.state.player, "_double_attack_damage_turns", 0) or 0) > 0:
            self.state.player._double_attack_damage_turns = max(
                0,
                int(getattr(self.state.player, "_double_attack_damage_turns", 0) or 0) - 1,
            )

        self.state.turn += 1
        self.state.turn_has_ended = False
        self.state.player.energy = self.state.player.max_energy
        self.state.player._first_discard_triggered_this_turn = False
        self.state.player._discards_this_turn = 0
        self.state.player._relic_skill_counters = {}
        if self.state.card_manager is not None:
            self.state.card_manager.set_energy(self.state.player.energy)
        self.state.player.powers.on_energy_recharge(self.state.player)
        if self.state.card_manager is not None:
            self.state.card_manager.set_energy(self.state.player.energy)
            self.state.card_manager.set_max_energy(self.state.player.max_energy)
            draw_count = 5 + int(getattr(self.state.player, "_draw_per_turn_bonus", 0) or 0)
            draw_count -= int(getattr(self.state.player, "_draw_reduction_next_turn", 0) or 0)
            draw_count = max(0, draw_count)
            self.state.player._draw_reduction_next_turn = 0
            self.state.card_manager.start_turn(draw_count=draw_count, rng=self.ai_rng)
        self._process_player_start_of_turn_post_draw_powers()
        self._apply_normality_limit()
        self._trigger_relic_effects("at_turn_start")
        self._process_player_start_of_turn_powers()
        self.state.cards_played_this_turn.clear()
        self.state.phase = CombatPhase.PLAYER_TURN

    def is_combat_over(self) -> bool:
        return self.state.player.is_dead() or self.state.all_monsters_dead()

    def player_won(self) -> bool:
        return self.state.all_monsters_dead() and not self.state.player.is_dead()

    def trigger_victory_effects(self) -> int:
        heal_amount = 0
        from sts_py.engine.content.relics import get_relic_by_id, RelicEffectType

        for relic_id in self.relics:
            relic_def = get_relic_by_id(relic_id)
            if relic_def is None:
                continue

            for effect in relic_def.effects:
                if effect.effect_type == RelicEffectType.ON_VICTORY:
                    if effect.target == "player":
                        heal_amount += effect.value

        heal_amount += self.state.player.powers.on_victory(self.state.player)

        amplified = self._apply_heal_amplification(heal_amount)
        return amplified

    def get_total_damage_taken(self) -> int:
        return self.state.player.max_hp - self.state.player.hp

    def simulate_combat(self, player_actions: list[tuple[str, int, int]]) -> int:
        for action_type, target_idx, value in player_actions:
            if self.is_combat_over():
                break

            if action_type == "attack":
                self.player_attack(target_idx, value)
            elif action_type == "block":
                self.player_gain_block(value)
            elif action_type == "play_card":
                self.play_card(target_idx, value)
            elif action_type == "end_turn":
                self.end_player_turn()

        return self.get_total_damage_taken()
