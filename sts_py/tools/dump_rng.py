from __future__ import annotations

import argparse
import json
from pathlib import Path

from sts_py.engine.core.seed import sterilize_seed_string, seed_string_to_long
from sts_py.engine.run.run_rng import RunRngState


def dump_seed(seed_str: str, n: int) -> dict:
    ss = sterilize_seed_string(seed_str)
    if ss == "":
        raise ValueError("Invalid seed string")
    seed_long = seed_string_to_long(ss)

    rr = RunRngState.generate_seeds(seed_long)

    streams = {
        "monster_rng": rr.monster_rng,
        "event_rng": rr.event_rng,
        "merchant_rng": rr.merchant_rng,
        "card_rng": rr.card_rng,
        "treasure_rng": rr.treasure_rng,
        "relic_rng": rr.relic_rng,
        "monster_hp_rng": rr.monster_hp_rng,
        "potion_rng": rr.potion_rng,
        "ai_rng": rr.ai_rng,
        "shuffle_rng": rr.shuffle_rng,
        "card_random_rng": rr.card_random_rng,
        "misc_rng": rr.misc_rng,
    }

    out = {
        "seed_string": seed_str,
        "seed_string_sterilized": ss,
        "seed_long_unsigned": seed_long,
        "streams": {},
    }

    # Provide a small comparable dump: first N random(999) values and counters.
    for name, rng in streams.items():
        vals = []
        r = rng
        for _ in range(n):
            r, v = r.random_int(999)
            vals.append(v)
        out["streams"][name] = {"counter_after": r.counter, "first_random_999": vals}

    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("seed", help="User-facing seed string")
    ap.add_argument("-n", type=int, default=10)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    data = dump_seed(args.seed, args.n)

    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        print(str(p))
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
