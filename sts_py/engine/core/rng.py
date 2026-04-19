"""Slay the Spire parity RNG.

Implements `com.megacrit.cardcrawl.random.Random` which wraps libGDX
`com.badlogic.gdx.math.RandomXS128`.

Key details from decompiled Java:
- `Random(Long seed)` constructs `RandomXS128(seed)`
- The wrapper maintains a public `counter` incremented on each call
- `random(int range)` returns `nextInt(range + 1)` (inclusive range)
- `random(int start, int end)` returns `start + nextInt(end-start+1)` (inclusive)
- `random(long range)` returns `(long)(nextDouble() * range)`
- `random(long start, long end)` returns `start + (long)(nextDouble() * (end-start))`
  (NOTE: end is effectively exclusive)
- `randomBoolean(float chance)` uses `nextFloat() < chance`

We keep this implementation self-contained for cross-platform determinism.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


def _u64(x: int) -> int:
    return x & 0xFFFFFFFFFFFFFFFF


def _rotl_u64(x: int, s: int) -> int:
    return _u64((x << s) | (x >> (64 - s)))


@dataclass
class JavaRandom:
    """Simulates java.util.Random (LCG algorithm)."""
    seed: int
    MULT = 0x5DEECE66D
    ADD = 0xB
    MASK48 = (1 << 48) - 1

    def __post_init__(self):
        self._seed = (self.seed ^ self.MULT) & self.MASK48

    def next(self, bits: int) -> int:
        self._seed = (self._seed * self.MULT + self.ADD) & self.MASK48
        return int(self._seed >> (48 - bits))

    def next_int(self, bound: int) -> int:
        """Simulates java.util.Random.nextInt(bound) using rejection sampling."""
        if bound <= 0:
            raise ValueError("bound must be positive")
        while True:
            bits = self.next(31)
            val = bits % bound
            if bits - val + (bound - 1) >= 0:
                return val

    def next_float(self) -> float:
        return float(self.next(24)) / float(1 << 24)

    def next_long(self, n: int) -> int:
        """Returns (nextLong() >>> 1) % n using rejection sampling (RandomXS128 algorithm)."""
        while True:
            bits = _u64(self.next_long_raw()) >> 1  # unsigned right shift after converting to unsigned
            val = bits % n
            if bits - val + (n - 1) >= 0:
                return val

    def next_long_raw(self) -> int:
        """Returns raw next long value."""
        hi = self.next(32)
        lo = self.next(32)
        return (hi << 32) | lo

    def _u64_to_signed(self, x: int) -> int:
        return x if x < (1 << 31) else x - (1 << 32)


@dataclass
class JavaRNG:
    """Wrapper for JavaRandom with parity API."""
    seed: int
    _jr: JavaRandom = field(default=None)

    def __post_init__(self):
        self._jr = JavaRandom(self.seed)

    def random_int(self, n: int) -> tuple["JavaRNG", int]:
        v = self._jr.next_int(n)
        return self, v

    def random_long(self, n: int) -> tuple["JavaRNG", int]:
        v = self._jr.next_long(n)
        return self, v

    def random_float(self) -> tuple["JavaRNG", float]:
        v = self._jr.next_float()
        return self, v


class MutableRNGJavaWrapper:
    """Wrapper for RNG (RandomXS128) to provide MutableRNG-like interface.

    Used for mapRng which is com.megacrit.cardcrawl.random.Random wrapping RandomXS128.
    """

    def __init__(self, rng: RNG, rng_type: str = "unknown"):
        self._rng = rng
        self.rng_type = rng_type
        self._call_history: list[dict] = []

    def random_int(self, range_exclusive: int) -> int:
        # Returns a random int in range [0, range_exclusive]
        # Matches java.util.Random.nextInt(int) behavior
        self._rng, v = self._rng.random_int(range_exclusive + 1)
        self._record("random(int)", v)
        return v

    def random_float(self) -> float:
        v = self._rng.next_float()
        self._record("random_float", v)
        return v

    def random_boolean(self) -> bool:
        return self.random_int(1) == 0

    def _record(self, method: str, value) -> None:
        self._call_history.append({
            "rng_type": self.rng_type,
            "method": method,
            "return_value": value,
        })

    def next_int(self, n: int) -> int:
        self._rng, v = self._rng.random_int(n)
        self._record("nextInt(int)", v)
        return v

    def random_int_between(self, start: int, end: int) -> int:
        self._rng, v = self._rng.random_int_between(start, end)
        self._record("random(int)", v)
        return v

    def random_boolean_chance(self, chance: float) -> bool:
        self._rng, v = self._rng.random_boolean_chance(chance)
        self._record("randomBoolean(float)", v)
        return v

    def to_immutable(self) -> "RNG":
        return self._rng


def _to_signed64(x: int) -> int:
    x = _u64(x)
    return x if x < (1 << 63) else x - (1 << 64)


def _murmurhash3_64(x: int) -> int:
    # Java's murmurHash3: natural long overflow (masked to 64-bit after each operation)
    # x is a 64-bit signed long, multiplication overflows automatically
    x = x ^ (x >> 33)
    x = _u64(x * -49064778989728563)  # mask after multiply
    x = x ^ (x >> 33)
    x = _u64(x * -4265267296055464877)  # mask after multiply
    x = x ^ (x >> 33)
    return x


@dataclass(frozen=True)
class RandomXS128:
    seed0: int
    seed1: int

    @staticmethod
    def from_seed(seed: int, use_murmurhash3: bool = True) -> "RandomXS128":
        # Java: RandomXS128(seed) uses setSeed(seed) which applies murmurHash3
        # Java: RandomXS128(seed0, seed1) uses setState(seed0, seed1) NO murmurHash3
        # mapRng is Random(seed, seed) -> RandomXS128(seed, seed) -> setState -> NO murmurHash3
        # Other RNGs use new RandomXS128(seed) -> setSeed -> murmurHash3
        s = seed
        if s == 0:
            s = -(1 << 63)
        if use_murmurhash3:
            seed0 = _murmurhash3_64(s)
            seed1 = _murmurhash3_64(seed0)
        else:
            seed0 = s
            seed1 = s
        return RandomXS128(seed0=seed0, seed1=seed1)

    def get_state(self, idx: int) -> int:
        return self.seed0 if idx == 0 else self.seed1

    def next_long(self) -> tuple["RandomXS128", int]:
        # Java nextLong:
        # long s0;
        # long s1 = this.seed0;
        # this.seed0 = s0 = this.seed1;
        # s1 ^= s1 << 23;  // Long overflow wraps to 64 bits
        # this.seed1 = s1 ^ s0 ^ s1 >>> 17 ^ s0 >>> 26;
        # return this.seed1 + s0;
        old_seed0 = self.seed0
        old_seed1 = self.seed1
        s1 = old_seed0
        s0 = old_seed1
        # Java: s1 ^= s1 << 23 (both s1 and result are masked to 64 bits)
        s1 = _u64(_u64(s1) ^ (_u64(s1) << 23))
        # Java uses >>> (unsigned right shift on 64-bit values)
        new_seed1 = _u64(_u64(s1) ^ _u64(s0) ^ (_u64(s1) >> 17) ^ (_u64(s0) >> 26))
        new_seed0 = s0
        # Java: return this.seed1 + s0 (signed 64-bit overflow)
        result = _to_signed64(_u64(new_seed1) + _u64(s0))
        return RandomXS128(seed0=new_seed0, seed1=new_seed1), result

    def next_int(self) -> tuple["RandomXS128", int]:
        rng, x = self.next_long()
        low32 = x & 0xFFFFFFFF
        return rng, low32 if low32 < 0x80000000 else low32 - 0x100000000

    def next_boolean(self) -> tuple["RandomXS128", bool]:
        rng, x = self.next_long()
        return rng, bool(x & 1)

    def next_float(self) -> tuple["RandomXS128", float]:
        # Java: (float)((double)(nextLong() >>> 40) * 2^-24)
        rng, x = self.next_long()
        return rng, float((_u64(x) >> 40) * 5.9604644775390625e-8)

    def next_double(self) -> tuple["RandomXS128", float]:
        # Java: (double)(nextLong() >>> 11) * 2^-53
        rng, x = self.next_long()
        return rng, float((_u64(x) >> 11) * 1.110223e-16)

    def next_long_bounded(self, n: int) -> tuple["RandomXS128", int]:
        # Java nextLong(long n): rejection sampling
        # bits = nextLong() >>> 1 (unsigned right shift)
        # while ((bits = nextLong() >>> 1) - (value = bits % n) + (n - 1) < 0) {}
        if n <= 0:
            raise ValueError("n must be positive")
        rng = self
        while True:
            rng, bits = rng.next_long()
            bits = _u64(bits) >> 1  # unsigned >>>1
            value = bits % n
            # Java uses signed comparison, so we need to convert to signed
            diff = _to_signed64(bits - value + (n - 1))
            if diff >= 0:
                return rng, value

    def next_int_bounded(self, n: int) -> tuple["RandomXS128", int]:
        # Java: (int)nextLong(n)
        rng, v = self.next_long_bounded(n)
        return rng, int(v)


@dataclass(frozen=True)
class RNG:
    """Parity wrapper for com.megacrit.cardcrawl.random.Random"""

    seed: int
    counter: int
    xs128: RandomXS128

    @staticmethod
    def from_seed(seed: int, counter: int = 0, use_murmurhash3: bool = True) -> "RNG":
        xs = RandomXS128.from_seed(int(seed), use_murmurhash3=use_murmurhash3)
        rng = RNG(seed=int(seed), counter=0, xs128=xs)
        # Java: for i in 0..counter-1: this.random(999)
        for _ in range(counter):
            rng, _ = rng.random_int(999)
        return rng

    def copy(self) -> "RNG":
        return RNG(seed=self.seed, counter=self.counter, xs128=self.xs128)

    def set_counter(self, target_counter: int) -> "RNG":
        if self.counter > target_counter:
            raise ValueError("Counter is already higher than target counter")
        rng = self
        for _ in range(target_counter - rng.counter):
            rng, _ = rng.random_boolean()
        return rng

    # --- parity APIs ---
    def random_int(self, range_exclusive: int) -> tuple["RNG", int]:
        xs, v = self.xs128.next_int_bounded(range_exclusive)
        return RNG(seed=self.seed, counter=self.counter + 1, xs128=xs), int(v)

    def random_int_between(self, start: int, end: int) -> tuple["RNG", int]:
        n = end - start + 1
        xs, v = self.xs128.next_int_bounded(n)
        return RNG(seed=self.seed, counter=self.counter + 1, xs128=xs), start + int(v)

    def random_long(self, range_exclusive: int) -> tuple["RNG", int]:
        xs, d = self.xs128.next_double()
        v = int(d * float(range_exclusive))
        return RNG(seed=self.seed, counter=self.counter + 1, xs128=xs), v

    def random_long_raw(self) -> tuple["RNG", int]:
        xs, v = self.xs128.next_long()
        return RNG(seed=self.seed, counter=self.counter + 1, xs128=xs), int(v)

    def random_long_between(self, start: int, end: int) -> tuple["RNG", int]:
        xs, d = self.xs128.next_double()
        v = start + int(d * float(end - start))
        return RNG(seed=self.seed, counter=self.counter + 1, xs128=xs), v

    def random_boolean(self) -> tuple["RNG", bool]:
        xs, b = self.xs128.next_boolean()
        return RNG(seed=self.seed, counter=self.counter + 1, xs128=xs), bool(b)

    def random_boolean_chance(self, chance: float) -> tuple["RNG", bool]:
        xs, f = self.xs128.next_float()
        return RNG(seed=self.seed, counter=self.counter + 1, xs128=xs), (f < chance)

    def random_float(self) -> tuple["RNG", float]:
        xs, f = self.xs128.next_float()
        return RNG(seed=self.seed, counter=self.counter + 1, xs128=xs), float(f)

    def random_float_range(self, range_: float) -> tuple["RNG", float]:
        xs, f = self.xs128.next_float()
        return RNG(seed=self.seed, counter=self.counter + 1, xs128=xs), float(f * range_)

    def random_float_between(self, start: float, end: float) -> tuple["RNG", float]:
        xs, f = self.xs128.next_float()
        return RNG(seed=self.seed, counter=self.counter + 1, xs128=xs), float(start + f * (end - start))

    # Convenience helpers for our engine (stable)
    def randint(self, a: int, b: int) -> tuple["RNG", int]:
        return self.random_int_between(a, b)

    def randbelow(self, n: int) -> tuple["RNG", int]:
        if n <= 0:
            raise ValueError("n must be positive")
        rng, v = self.random_int(n - 1)
        return rng, v


@dataclass
class MutableRNG:
    """Mutable wrapper for RNG for convenience in game logic."""
    _rng: RNG
    rng_type: str = "unknown"
    _call_history: list[dict] | None = None

    def __post_init__(self):
        object.__setattr__(self, '_call_history', [])

    @staticmethod
    def from_seed(seed: int, counter: int = 0, rng_type: str = "unknown", use_java_random: bool = False) -> "MutableRNG":
        if use_java_random:
            # mapRng = new Random(Settings.seed + actNum)
            # Random(long seed) calls super(seed) = RandomXS128(seed)
            # RandomXS128(long seed) calls setSeed(seed) which applies murmurHash3
            # So mapRng DOES use murmurHash3!
            rng = RNG.from_seed(int(seed), counter, use_murmurhash3=True)
            return MutableRNGJavaWrapper(rng, rng_type=rng_type)
        return MutableRNG(RNG.from_seed(seed, counter), rng_type=rng_type)

    @property
    def counter(self) -> int:
        return self._rng.counter

    @property
    def call_history(self) -> list[dict]:
        return self._call_history

    def _record(self, method: str, value) -> None:
        if self._call_history is not None:
            self._call_history.append({
                "rng_type": self.rng_type,
                "counter": self._rng.counter,
                "method": method,
                "return_value": value,
            })

    def random_int(self, range_inclusive: int) -> int:
        # Java: random(int range) = nextInt(range + 1) = [0, range]
        # Python random_int(n) = nextInt(n) = [0, n)
        # So we need to call random_int(range + 1)
        self._rng, v = self._rng.random_int(range_inclusive + 1)
        self._record("random(int)", v)
        return v

    def next_int(self, n: int) -> int:
        # Java: nextInt(n) returns [0, n)
        # This is different from random(int) which returns [0, n]
        self._rng, v = self._rng.random_int(n)
        self._record("nextInt(int)", v)
        return v

    def random_int_between(self, start: int, end: int) -> int:
        self._rng, v = self._rng.random_int_between(start, end)
        self._record("random(int)", v)
        return v

    def random_boolean(self) -> bool:
        self._rng, v = self._rng.random_boolean()
        self._record("randomBoolean()", v)
        return v

    def random_boolean_chance(self, chance: float) -> bool:
        self._rng, v = self._rng.random_boolean_chance(chance)
        self._record("randomBoolean(float)", v)
        return v

    def random_float(self) -> float:
        self._rng, v = self._rng.random_float()
        self._record("random()", v)
        return v

    def random_long_raw(self) -> int:
        self._rng, v = self._rng.random_long_raw()
        self._record("randomLong()", v)
        return v

    def to_immutable(self) -> RNG:
        return self._rng


RNG_TYPE_NAMES = [
    "cardRng",
    "monsterRng", 
    "aiRng",
    "eventRng",
    "merchantRng",
    "treasureRng",
    "relicRng",
    "potionRng",
    "shuffleRng",
    "cardRandomRng",
    "mapRng",
    "miscRng",
    "monsterHpRng",
]


@dataclass
class RunRNGs:
    """Container for all 13 independent RNG instances used by Slay The Spire.
    
    From Java AbstractDungeon:
    - cardRng: Card rewards, card generation
    - monsterRng: Monster encounter selection
    - aiRng: Monster AI decisions (move selection)
    - eventRng: Event selection and outcomes
    - merchantRng: Shop contents and prices
    - treasureRng: Chest contents
    - relicRng: Relic generation and selection
    - potionRng: Potion drops and effects
    - shuffleRng: Card deck shuffling
    - cardRandomRng: Random card effects (e.g. Madness)
    - mapRng: Map generation
    - miscRng: Miscellaneous random events
    - monsterHpRng: Monster HP rolls
    """
    card_rng: MutableRNG
    monster_rng: MutableRNG
    ai_rng: MutableRNG
    event_rng: MutableRNG
    merchant_rng: MutableRNG
    treasure_rng: MutableRNG
    relic_rng: MutableRNG
    potion_rng: MutableRNG
    shuffle_rng: MutableRNG
    card_random_rng: MutableRNG
    map_rng: MutableRNG
    misc_rng: MutableRNG
    monster_hp_rng: MutableRNG
    
    _seed: int = 0
    _rng_log: list = field(default_factory=list)
    
    @staticmethod
    def from_seed(seed: int) -> "RunRNGs":
        """Create all RNG instances from a single seed.
        
        Java uses Settings.seed as base, then each RNG gets:
        - mapRng: seed + actNum (different per act)
        - Others: derived from seed via RandomXS128
        """
        return RunRNGs(
            card_rng=MutableRNG.from_seed(seed, rng_type="cardRng"),
            monster_rng=MutableRNG.from_seed(seed, rng_type="monsterRng"),
            ai_rng=MutableRNG.from_seed(seed, rng_type="aiRng"),
            event_rng=MutableRNG.from_seed(seed, rng_type="eventRng"),
            merchant_rng=MutableRNG.from_seed(seed, rng_type="merchantRng"),
            treasure_rng=MutableRNG.from_seed(seed, rng_type="treasureRng"),
            relic_rng=MutableRNG.from_seed(seed, rng_type="relicRng"),
            potion_rng=MutableRNG.from_seed(seed, rng_type="potionRng"),
            shuffle_rng=MutableRNG.from_seed(seed, rng_type="shuffleRng"),
            card_random_rng=MutableRNG.from_seed(seed, rng_type="cardRandomRng"),
            map_rng=MutableRNG.from_seed(seed, rng_type="mapRng"),
            misc_rng=MutableRNG.from_seed(seed, rng_type="miscRng"),
            monster_hp_rng=MutableRNG.from_seed(seed, rng_type="monsterHpRng"),
            _seed=seed,
        )
    
    def get_all_counters(self) -> dict[str, int]:
        """Get current counter values for all RNGs."""
        return {
            "cardRng": self.card_rng.counter,
            "monsterRng": self.monster_rng.counter,
            "aiRng": self.ai_rng.counter,
            "eventRng": self.event_rng.counter,
            "merchantRng": self.merchant_rng.counter,
            "treasureRng": self.treasure_rng.counter,
            "relicRng": self.relic_rng.counter,
            "potionRng": self.potion_rng.counter,
            "shuffleRng": self.shuffle_rng.counter,
            "cardRandomRng": self.card_random_rng.counter,
            "mapRng": self.map_rng.counter,
            "miscRng": self.misc_rng.counter,
            "monsterHpRng": self.monster_hp_rng.counter,
        }
    
    def log_rng_call(self, rng_type: str, method: str, result, params: dict = None) -> None:
        """Log an RNG call for debugging/replay."""
        self._rng_log.append({
            "rng_type": rng_type,
            "method": method,
            "result": result,
            "params": params or {},
            "counters": self.get_all_counters(),
        })
    
    def create_snapshot(self, label: str, floor: int = 0) -> dict:
        """Create a snapshot of all RNG states."""
        return {
            "label": label,
            "floor": floor,
            "seed": self._seed,
            "counters": self.get_all_counters(),
        }
