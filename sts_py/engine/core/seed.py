from __future__ import annotations

"""Seed encoding/decoding/parity helpers.

Ported from:
- com.megacrit.cardcrawl.helpers.SeedHelper
- com.megacrit.cardcrawl.helpers.BadWordChecker
- com.megacrit.cardcrawl.helpers.TrialHelper

This is used to support option B: user-facing string seeds.
"""

from dataclasses import dataclass

from sts_py.engine.core.rng import RNG


_CHARACTERS = "0123456789ABCDEFGHIJKLMNPQRSTUVWXYZ"


def sterilize_seed_string(raw: str) -> str:
    raw = raw.strip().upper()
    # Java checks pattern "([A-Z]*[0-9]*)*" and replaces O->0.
    # We'll implement equivalently.
    import re

    if re.fullmatch(r"([A-Z]*[0-9]*)*", raw) is None:
        return ""
    return raw.replace("O", "0")


def seed_string_to_long(seed_str: str) -> int:
    s = seed_str.upper().replace("O", "0")
    total = 0
    base = len(_CHARACTERS)
    for ch in s:
        rem = _CHARACTERS.find(ch)
        if rem == -1:
            # Java prints a warning but still proceeds.
            rem = -1
        total = total * base + rem
    return int(total)


def seed_long_to_string(seed: int) -> str:
    # Java uses BigInteger(Long.toUnsignedString(seed)) and converts base-N.
    # We'll mirror with unsigned 64-bit representation.
    seed_u = seed & 0xFFFFFFFFFFFFFFFF
    if seed_u == 0:
        return ""

    base = len(_CHARACTERS)
    out = []
    while seed_u != 0:
        seed_u, rem = divmod(seed_u, base)
        out.append(_CHARACTERS[rem])
    return "".join(reversed(out))


# NOTE: BadWordChecker contains a huge list; for now we keep a minimal subset.
# If you want perfect parity, we can import the full list from decompiled source.
_BAD_WORDS_MIN = {"fuck"}


def contains_bad_word(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in _BAD_WORDS_MIN)


_TRIAL_KEYS = {
    # from TrialHelper.initialize(), formatted by SeedHelper.sterilizeString
    sterilize_seed_string("RandomMods"): "RANDOM_MODS",
    sterilize_seed_string("DailyMods"): "RANDOM_MODS",
    sterilize_seed_string("StarterDeck"): "NO_CARD_DROPS",
    sterilize_seed_string("Inception"): "UNCEASING_TOP",
    sterilize_seed_string("FadeAway"): "LOSE_MAX_HP",
    sterilize_seed_string("PraiseSnecko"): "SNECKO",
    sterilize_seed_string("YoureTooSlow"): "SLOW",
    sterilize_seed_string("MyTrueForm"): "FORMS",
    sterilize_seed_string("Draft"): "DRAFT",
    sterilize_seed_string("MegaDraft"): "MEGA_DRAFT",
    sterilize_seed_string("1HitWonder"): "ONE_HP",
    sterilize_seed_string("MoreCards"): "MORE_CARDS",
    sterilize_seed_string("Cursed"): "CURSED",
}


def is_trial_seed(seed_str: str) -> bool:
    return seed_str in _TRIAL_KEYS


def generate_unoffensive_seed(rng: RNG) -> tuple[RNG, int]:
    # Java:
    # safeString = "fuck";
    # while (BadWordChecker.containsBadWord(safeString) || TrialHelper.isTrialSeed(safeString)) {
    #   long possible = rng.randomLong();
    #   safeString = SeedHelper.getString(possible);
    # }
    safe = "fuck"
    r = rng
    while contains_bad_word(safe) or is_trial_seed(safe):
        r, possible = r.random_long_between(-(1 << 63), (1 << 63) - 1)
        safe = seed_long_to_string(possible)
    return r, seed_string_to_long(safe)
