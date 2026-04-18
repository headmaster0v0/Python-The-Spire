"""Encounter generation for Slay The Spire.

This module implements encounter generation aligned with Java's
AbstractDungeon.generateMonsters(), generateWeakEnemies(), etc.

ACT 1 (Exordium): Early game monsters
ACT 2 (TheCity): Mid game monsters
ACT 3 (TheBeyond): Late game monsters
"""

from __future__ import annotations

from dataclasses import dataclass

from sts_py.engine.core.rng import MutableRNG


@dataclass
class MonsterInfo:
    name: str
    weight: float


@dataclass
class EncounterPool:
    """Pool of encounters with weights for a specific category."""
    encounters: list[MonsterInfo]

    def roll(self, rng: MutableRNG) -> str:
        """Roll for a random encounter based on weights (normalized)."""
        total_weight = sum(e.weight for e in self.encounters)
        r = rng.random_float() * total_weight
        cumulative = 0.0
        for encounter in self.encounters:
            cumulative += encounter.weight
            if r < cumulative:
                return encounter.name
        return self.encounters[-1].name

    def roll_no_repeat(self, rng: MutableRNG, last_encounter: str | None, second_last: str | None = None) -> str:
        """Roll for an encounter, avoiding repeating the last one or second last."""
        attempts = 0
        max_attempts = 10
        while attempts < max_attempts:
            result = self.roll(rng)
            if result != last_encounter:
                if result == second_last and second_last is not None:
                    continue
                return result
            attempts += 1
        return result


def _normalize_weights(monsters: list[MonsterInfo]) -> None:
    """Normalize weights so they sum to 1.0."""
    total = sum(m.weight for m in monsters)
    if total > 0:
        for m in monsters:
            m.weight /= total


# =============================================================================
# ACT 1 (Exordium) Monsters
# =============================================================================

WEAK_MONSTERS_ACT1 = EncounterPool([
    MonsterInfo("Cultist", 2.0),
    MonsterInfo("Jaw Worm", 2.0),
    MonsterInfo("2 Louse", 2.0),
    MonsterInfo("AcidM + SpikeS", 1.0),
    MonsterInfo("SpikeM + AcidS", 1.0),
])

STRONG_MONSTERS_ACT1 = EncounterPool([
    MonsterInfo("Blue Slaver", 2.0),
    MonsterInfo("Gremlin Gang", 1.0),
    MonsterInfo("Looter", 2.0),
    MonsterInfo("Large Slime", 2.0),
    MonsterInfo("Lots of Slimes", 1.0),
    MonsterInfo("Exordium Thugs", 1.5),
    MonsterInfo("Exordium Wildlife", 1.5),
    MonsterInfo("Red Slaver", 1.0),
    MonsterInfo("3 Louse", 2.0),
    MonsterInfo("2 Fungi Beasts", 2.0),
])

ELITE_MONSTERS_ACT1 = EncounterPool([
    MonsterInfo("Gremlin Nob", 1.0),
    MonsterInfo("Lagavulin", 1.0),
    MonsterInfo("3 Sentries", 1.0),
])

BOSS_MONSTERS_ACT1 = EncounterPool([
    MonsterInfo("The Guardian", 1.0),
    MonsterInfo("Hexaghost", 1.0),
    MonsterInfo("Slime Boss", 1.0),
])


# =============================================================================
# ACT 2 (TheCity) Monsters
# =============================================================================

WEAK_MONSTERS_ACT2 = EncounterPool([
    MonsterInfo("Spheric Guardian", 2.0),
    MonsterInfo("Chosen", 2.0),
    MonsterInfo("Shell Parasite", 2.0),
    MonsterInfo("3 Byrds", 2.0),
    MonsterInfo("2 Thieves", 2.0),
])

STRONG_MONSTERS_ACT2 = EncounterPool([
    MonsterInfo("Chosen and Byrds", 2.0),
    MonsterInfo("Sentry and Sphere", 2.0),
    MonsterInfo("Snake Plant", 6.0),
    MonsterInfo("Snecko", 4.0),
    MonsterInfo("Centurion and Healer", 6.0),
    MonsterInfo("Cultist and Chosen", 3.0),
    MonsterInfo("3 Cultists", 3.0),
    MonsterInfo("Shelled Parasite and Fungi", 3.0),
])

ELITE_MONSTERS_ACT2 = EncounterPool([
    MonsterInfo("Gremlin Leader", 1.0),
    MonsterInfo("Slavers", 1.0),
    MonsterInfo("Book of Stabbing", 1.0),
])

BOSS_MONSTERS_ACT2 = EncounterPool([
    MonsterInfo("Automaton", 2.0),
    MonsterInfo("Collector", 2.0),
    MonsterInfo("Champ", 2.0),
])


# =============================================================================
# ACT 3 (TheBeyond) Monsters
# =============================================================================

WEAK_MONSTERS_ACT3 = EncounterPool([
    MonsterInfo("3 Darklings", 2.0),
    MonsterInfo("Orb Walker", 2.0),
    MonsterInfo("3 Shapes", 2.0),
])

STRONG_MONSTERS_ACT3 = EncounterPool([
    MonsterInfo("Spire Growth", 1.0),
    MonsterInfo("Transient", 1.0),
    MonsterInfo("4 Shapes", 1.0),
    MonsterInfo("Maw", 1.0),
    MonsterInfo("Sphere and 2 Shapes", 1.0),
    MonsterInfo("Jaw Worm Horde", 1.0),
    MonsterInfo("3 Darklings", 1.0),
    MonsterInfo("Writhing Mass", 1.0),
])

ELITE_MONSTERS_ACT3 = EncounterPool([
    MonsterInfo("Giant Head", 2.0),
    MonsterInfo("Nemesis", 2.0),
    MonsterInfo("Reptomancer", 2.0),
])

BOSS_MONSTERS_ACT3 = EncounterPool([
    MonsterInfo("Awakened One", 2.0),
    MonsterInfo("Time Eater", 2.0),
    MonsterInfo("Donu and Deca", 2.0),
])


# =============================================================================
# Helper functions
# =============================================================================

def get_weak_pool(act: int) -> EncounterPool:
    if act == 1:
        return WEAK_MONSTERS_ACT1
    elif act == 2:
        return WEAK_MONSTERS_ACT2
    else:
        return WEAK_MONSTERS_ACT3


def get_strong_pool(act: int) -> EncounterPool:
    if act == 1:
        return STRONG_MONSTERS_ACT1
    elif act == 2:
        return STRONG_MONSTERS_ACT2
    else:
        return STRONG_MONSTERS_ACT3


def get_elite_pool(act: int) -> EncounterPool:
    if act == 1:
        return ELITE_MONSTERS_ACT1
    elif act == 2:
        return ELITE_MONSTERS_ACT2
    else:
        return ELITE_MONSTERS_ACT3


def get_boss_pool(act: int) -> EncounterPool:
    if act == 1:
        return BOSS_MONSTERS_ACT1
    elif act == 2:
        return BOSS_MONSTERS_ACT2
    else:
        return BOSS_MONSTERS_ACT3


def generate_monsters(
    monster_rng: MutableRNG,
    act: int = 1
) -> tuple[list[str], list[str], list[str]]:
    """Generate monster lists for the map.

    Java generates:
    - ACT 1: 3 weak + 12 strong + 10 elite
    - ACT 2: 2 weak + 12 strong + 10 elite
    - ACT 3: 2 weak + 12 strong + 10 elite

    All encounters are stored in a SHARED monsterList and assigned by visit order.

    Returns:
        Tuple of (weak_encounters, strong_encounters, elite_encounters)
    """
    weak_count = 3 if act == 1 else 2
    strong_count = 12
    elite_count = 10

    weak_pool = get_weak_pool(act)
    strong_pool = get_strong_pool(act)
    elite_pool = get_elite_pool(act)

    weak_encounters: list[str] = []
    strong_encounters: list[str] = []
    elite_encounters: list[str] = []

    for i in range(weak_count):
        if not weak_encounters:
            encounter = weak_pool.roll(monster_rng)
        else:
            encounter = weak_pool.roll_no_repeat(
                monster_rng,
                weak_encounters[-1],
                weak_encounters[-2] if len(weak_encounters) >= 2 else None
            )
        weak_encounters.append(encounter)

    first_strong = strong_pool.roll_no_repeat(monster_rng, weak_encounters[0])
    strong_encounters.append(first_strong)

    for i in range(1, strong_count):
        encounter = strong_pool.roll_no_repeat(
            monster_rng,
            strong_encounters[-1],
            strong_encounters[-2] if len(strong_encounters) >= 2 else None
        )
        strong_encounters.append(encounter)

    for i in range(elite_count):
        if not elite_encounters:
            encounter = elite_pool.roll(monster_rng)
        else:
            encounter = elite_pool.roll_no_repeat(
                monster_rng,
                elite_encounters[-1]
            )
        elite_encounters.append(encounter)

    return weak_encounters, strong_encounters, elite_encounters


def generate_all_encounters(
    monster_rng: MutableRNG,
    act: int = 1
) -> list[str]:
    """Generate all encounters for the act.

    Java stores weak and strong encounters in a SHARED monsterList.
    When a player visits a MonsterRoom, they get the next encounter from monsterList.
    """
    weak_count = 3 if act == 1 else 2
    strong_count = 12

    weak_pool = get_weak_pool(act)
    strong_pool = get_strong_pool(act)

    weak_encounters: list[str] = []
    strong_encounters: list[str] = []

    for i in range(weak_count):
        if not weak_encounters:
            encounter = weak_pool.roll(monster_rng)
        else:
            encounter = weak_pool.roll_no_repeat(
                monster_rng,
                weak_encounters[-1],
                weak_encounters[-2] if len(weak_encounters) >= 2 else None
            )
        weak_encounters.append(encounter)

    first_strong = strong_pool.roll_no_repeat(monster_rng, weak_encounters[0])
    strong_encounters.append(first_strong)

    for i in range(1, strong_count):
        encounter = strong_pool.roll_no_repeat(
            monster_rng,
            strong_encounters[-1],
            strong_encounters[-2] if len(strong_encounters) >= 2 else None
        )
        strong_encounters.append(encounter)

    return weak_encounters + strong_encounters


def roll_boss(monster_rng: MutableRNG, act: int) -> str:
    """Roll for a boss encounter."""
    boss_pool = get_boss_pool(act)
    return boss_pool.roll(monster_rng)
