from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence

from sts_py.engine.core.rng import RNG
from sts_py.engine.content.cards_min import CARD_DEFS_BY_CHARACTER, CardDef, CardRarity
from sts_py.engine.content.pool_order import build_reward_pools as build_character_reward_pools


# ---------------------------------------------------------------------------
# RewardGenState — tracks mutable dungeon fields across reward calls
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RewardGenState:
    """Subset of AbstractDungeon fields needed for getRewardCards parity."""

    card_blizz_start_offset: int = 5
    card_blizz_growth: int = 1
    card_blizz_max_offset: int = -40
    card_blizz_randomizer: int = 5

    # Per-dungeon: Exordium=0.0, TheCity=0.25 (A12+=0.125), TheBeyond/Ending=0.5 (A12+=0.25)
    card_upgraded_chance: float = 0.0


# ---------------------------------------------------------------------------
# Room rarity — port of AbstractRoom.getCardRarity(roll, useAlternation)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RoomRarityState:
    """Per-room rarity probability bands.

    Java fields: baseRareCardChance=3, baseUncommonCardChance=37.
    rareCardChance / uncommonCardChance are reset each call then modified by relics.
    """
    base_rare_chance: int = 3
    base_uncommon_chance: int = 37
    rare_chance: int = 3
    uncommon_chance: int = 37


def room_get_card_rarity(roll: int, use_alternation: bool = True,
                         relic_rare_mod: int = 0,
                         relic_uncommon_mod: int = 0) -> CardRarity:
    """Port of AbstractRoom.getCardRarity(roll, useAlternation).

    Java logic:
      rareCardChance = baseRareCardChance (3)
      uncommonCardChance = baseUncommonCardChance (37)
      if useAlternation: alterCardRarityProbabilities() — applies relic mods
      if roll < rareCardChance: RARE
      elif roll < rareCardChance + uncommonCardChance: UNCOMMON
      else: COMMON

    relic_rare_mod / relic_uncommon_mod: additive changes from relics
    (e.g. Nloth's Gift adds +3 to rare chance). For vanilla Act1 start = 0.
    """
    rare_chance = 3
    uncommon_chance = 37
    if use_alternation:
        rare_chance += relic_rare_mod
        uncommon_chance += relic_uncommon_mod
    if roll < rare_chance:
        return CardRarity.RARE
    if roll < rare_chance + uncommon_chance:
        return CardRarity.UNCOMMON
    return CardRarity.COMMON


def card_rarity_fallback(roll: int) -> CardRarity:
    """AbstractDungeon.getCardRarityFallback — used when currMapNode is null."""
    if roll < 3:
        return CardRarity.RARE
    if roll < 40:
        return CardRarity.UNCOMMON
    return CardRarity.COMMON


# ---------------------------------------------------------------------------
# cardBlizzRandomizer adjustment
# ---------------------------------------------------------------------------

def adjust_card_blizz(st: RewardGenState, rarity: CardRarity) -> RewardGenState:
    """Mutate cardBlizzRandomizer based on rolled rarity (pity timer)."""
    if rarity == CardRarity.RARE:
        return replace(st, card_blizz_randomizer=st.card_blizz_start_offset)
    if rarity == CardRarity.COMMON:
        new_val = st.card_blizz_randomizer - st.card_blizz_growth
        if new_val <= st.card_blizz_max_offset:
            new_val = st.card_blizz_max_offset
        return replace(st, card_blizz_randomizer=new_val)
    return st


# ---------------------------------------------------------------------------
# rollRarity — port of AbstractDungeon.rollRarity()
# ---------------------------------------------------------------------------

def roll_rarity(card_rng: RNG, st: RewardGenState,
                has_map_node: bool = True,
                relic_rare_mod: int = 0,
                relic_uncommon_mod: int = 0,
                ) -> tuple[RNG, RewardGenState, CardRarity]:
    """Port of AbstractDungeon.rollRarity(Random rng).

    Java:
      int roll = cardRng.random(99);
      roll += cardBlizzRandomizer;
      if (currMapNode == null) return fallback(roll);
      return getCurrRoom().getCardRarity(roll);
    """
    # Immutable RNG uses exclusive bounds; Java random(99) is inclusive 0..99.
    rng2, roll = card_rng.random_int(100)
    roll += st.card_blizz_randomizer
    if not has_map_node:
        rarity = card_rarity_fallback(roll)
    else:
        rarity = room_get_card_rarity(roll, use_alternation=True,
                                      relic_rare_mod=relic_rare_mod,
                                      relic_uncommon_mod=relic_uncommon_mod)
    return rng2, st, rarity


# ---------------------------------------------------------------------------
# Card pool helpers
# ---------------------------------------------------------------------------

def build_pools(cards: Sequence[CardDef]) -> dict[CardRarity, list[CardDef]]:
    """Split cards into rarity pools (excluding BASIC/CURSE)."""
    pools: dict[CardRarity, list[CardDef]] = {
        CardRarity.COMMON: [],
        CardRarity.UNCOMMON: [],
        CardRarity.RARE: [],
    }
    for c in cards:
        if c.rarity in pools:
            pools[c.rarity].append(c)
    return pools


def pick_card_from_pool(card_rng: RNG, pool: list[CardDef],
                        ) -> tuple[RNG, CardDef]:
    """Port of CardGroup.getRandomCard(boolean useRng=true).

    Java (simple overload, NO sort):
      return group.get(AbstractDungeon.cardRng.random(group.size() - 1));

    The pool order must match Java's HashMap iteration order.
    """
    # Immutable RNG uses exclusive bounds; Java pool random(size - 1) is inclusive.
    rng2, idx = card_rng.random_int(len(pool))
    return rng2, pool[idx]


# ---------------------------------------------------------------------------
# getRewardCards — main entry point
# ---------------------------------------------------------------------------

def get_reward_cards(
    card_rng: RNG,
    state: RewardGenState,
    pools: dict[CardRarity, list[CardDef]],
    n: int = 3,
    has_map_node: bool = True,
    relic_rare_mod: int = 0,
    relic_uncommon_mod: int = 0,
) -> tuple[RNG, RewardGenState, list[CardDef]]:
    """Port of AbstractDungeon.getRewardCards().

    Java flow per card:
      1) rarity = rollRarity()          — consumes cardRng once
      2) adjust cardBlizzRandomizer
      3) card = getCard(rarity)          — consumes cardRng once
         which calls pool.getRandomCard(true)
      4) if duplicate cardID in result, re-roll card (step 3 again)
      5) after all cards: makeCopy, then upgrade check

    Upgrade check (step 5):
      for each non-RARE card: cardRng.randomBoolean(cardUpgradedChance)
      This consumes cardRng even if chance is 0.0 (returns false).
      Actually in Java, randomBoolean calls nextFloat which always advances RNG.
      BUT: Java only calls randomBoolean when cardUpgradedChance > 0 implicitly
      — actually it always calls it for non-rare. Let's match exactly.

    NOTE: Java calls randomBoolean for EVERY non-rare card regardless of chance
    value. The RNG is consumed. We must do the same for counter parity.
    """
    rng = card_rng
    st = state
    picked: list[CardDef] = []

    for _ in range(n):
        # 1) roll rarity
        rng, st, rarity = roll_rarity(rng, st, has_map_node=has_map_node,
                                      relic_rare_mod=relic_rare_mod,
                                      relic_uncommon_mod=relic_uncommon_mod)
        # 2) adjust blizz
        st = adjust_card_blizz(st, rarity)

        # 3-4) pick card, re-roll on dupe
        pool = pools.get(rarity) or pools[CardRarity.COMMON]
        available_unique_cards = [candidate for candidate in pool if all(candidate.id != p.id for p in picked)]
        if len(available_unique_cards) == 1:
            picked.append(available_unique_cards[0])
            continue
        if not available_unique_cards:
            rng, card = pick_card_from_pool(rng, pool)
            picked.append(card)
            continue
        while True:
            rng, card = pick_card_from_pool(rng, pool)
            if all(card.id != p.id for p in picked):
                picked.append(card)
                break

    # 5) upgrade check — consumes cardRng for each non-rare
    upgraded: list[bool] = []
    for card in picked:
        if card.rarity != CardRarity.RARE:
            rng, do_upgrade = rng.random_boolean_chance(st.card_upgraded_chance)
            upgraded.append(do_upgrade)
        else:
            upgraded.append(False)

    return rng, st, picked


# ---------------------------------------------------------------------------
# Convenience: build Ironclad pools
# ---------------------------------------------------------------------------

def ironclad_pools() -> dict[CardRarity, list[CardDef]]:
    """Build reward pools from the full Ironclad card table."""
    return build_character_reward_pools("IRONCLAD")


def watcher_pools() -> dict[CardRarity, list[CardDef]]:
    """Build reward pools for Watcher."""
    return build_character_reward_pools("WATCHER")


def character_pools(character_class: str) -> dict[CardRarity, list[CardDef]]:
    """Build reward pools for the requested character class."""
    return build_character_reward_pools(character_class)


def ironclad_min_available() -> list[CardDef]:
    """Backwards-compat helper."""
    return [c for c in CARD_DEFS_BY_CHARACTER["IRONCLAD"].values() if c.rarity != CardRarity.BASIC]


def color_min_available(character_class: str) -> list[CardDef]:
    """Return non-basic cards for the requested character class."""
    defs = CARD_DEFS_BY_CHARACTER.get(character_class.upper(), CARD_DEFS_BY_CHARACTER["IRONCLAD"])
    return [c for c in defs.values() if c.rarity != CardRarity.BASIC]
