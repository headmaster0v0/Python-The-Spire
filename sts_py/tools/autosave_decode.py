from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def decode_autosave_text(obfuscated_text: str, key: str = "key") -> bytes:
    """Decode STS autosave text into raw JSON bytes.

    Java SaveFileObfuscator:
      decode(s, key) = xorWithKey(base64Decode(s), key.getBytes())
    """

    b = base64.b64decode(obfuscated_text)
    k = key.encode("utf-8")
    out = bytes([b[i] ^ k[i % len(k)] for i in range(len(b))])
    return out


def load_autosave_json(path: str | Path) -> dict[str, Any]:
    """Load IRONCLAD.autosave and return parsed JSON dict.

    The decoded bytes are expected to be UTF-8 JSON, but player name may contain
    bytes that don't decode cleanly under UTF-8 in some environments. We parse
    using latin-1 to preserve byte values (keys and numbers remain correct).
    """

    text = Path(path).read_text(encoding="utf-8")
    decoded = decode_autosave_text(text, key="key")
    return json.loads(decoded.decode("latin-1"))


@dataclass(frozen=True)
class SaveSeedCounters:
    seed: int
    seed_set: bool

    monster_seed_count: int
    event_seed_count: int
    merchant_seed_count: int
    card_seed_count: int
    treasure_seed_count: int
    relic_seed_count: int
    potion_seed_count: int
    ai_seed_count: int
    shuffle_seed_count: int
    card_random_seed_count: int
    card_random_seed_randomizer: int

    @staticmethod
    def from_save(d: dict[str, Any]) -> "SaveSeedCounters":
        return SaveSeedCounters(
            seed=int(d.get("seed")),
            seed_set=bool(d.get("seed_set")),
            monster_seed_count=int(d.get("monster_seed_count", 0)),
            event_seed_count=int(d.get("event_seed_count", 0)),
            merchant_seed_count=int(d.get("merchant_seed_count", 0)),
            card_seed_count=int(d.get("card_seed_count", 0)),
            treasure_seed_count=int(d.get("treasure_seed_count", 0)),
            relic_seed_count=int(d.get("relic_seed_count", 0)),
            potion_seed_count=int(d.get("potion_seed_count", 0)),
            ai_seed_count=int(d.get("ai_seed_count", 0)),
            shuffle_seed_count=int(d.get("shuffle_seed_count", 0)),
            card_random_seed_count=int(d.get("card_random_seed_count", 0)),
            card_random_seed_randomizer=int(d.get("card_random_seed_randomizer", 0)),
        )
