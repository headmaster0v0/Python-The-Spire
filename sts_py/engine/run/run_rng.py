from __future__ import annotations

from dataclasses import dataclass, field

from sts_py.engine.core.rng import RNG, MutableRNG


@dataclass
class RunRngState:
    seed_long: int

    _monster_rng: MutableRNG = field(default=None, repr=False)  # type: ignore
    _event_rng: MutableRNG = field(default=None, repr=False)  # type: ignore
    _merchant_rng: MutableRNG = field(default=None, repr=False)  # type: ignore
    _card_rng: MutableRNG = field(default=None, repr=False)  # type: ignore
    _treasure_rng: MutableRNG = field(default=None, repr=False)  # type: ignore
    _relic_rng: MutableRNG = field(default=None, repr=False)  # type: ignore
    _monster_hp_rng: MutableRNG = field(default=None, repr=False)  # type: ignore
    _potion_rng: MutableRNG = field(default=None, repr=False)  # type: ignore
    _ai_rng: MutableRNG = field(default=None, repr=False)  # type: ignore
    _shuffle_rng: MutableRNG = field(default=None, repr=False)  # type: ignore
    _card_random_rng: MutableRNG = field(default=None, repr=False)  # type: ignore
    _misc_rng: MutableRNG = field(default=None, repr=False)  # type: ignore
    _map_rng: MutableRNG = field(default=None, repr=False)  # type: ignore

    @staticmethod
    def generate_seeds(seed_long: int) -> "RunRngState":
        s = int(seed_long)
        return RunRngState(
            seed_long=s,
            _monster_rng=MutableRNG.from_seed(s, rng_type="monsterRng"),
            _event_rng=MutableRNG.from_seed(s, rng_type="eventRng"),
            _merchant_rng=MutableRNG.from_seed(s, rng_type="merchantRng"),
            _card_rng=MutableRNG.from_seed(s, rng_type="cardRng"),
            _treasure_rng=MutableRNG.from_seed(s, rng_type="treasureRng"),
            _relic_rng=MutableRNG.from_seed(s, rng_type="relicRng"),
            _monster_hp_rng=MutableRNG.from_seed(s, rng_type="monsterHpRng"),
            _potion_rng=MutableRNG.from_seed(s, rng_type="potionRng"),
            _ai_rng=MutableRNG.from_seed(s, rng_type="aiRng"),
            _shuffle_rng=MutableRNG.from_seed(s, rng_type="shuffleRng"),
            _card_random_rng=MutableRNG.from_seed(s, rng_type="cardRandomRng"),
            _misc_rng=MutableRNG.from_seed(s, rng_type="miscRng"),
            _map_rng=MutableRNG.from_seed(s + 1, rng_type="mapRng", use_java_random=True),  # Java: mapRng = new Random(Settings.seed + actNum)
        )
    
    @property
    def monster_rng(self) -> MutableRNG:
        return self._monster_rng
    
    @property
    def event_rng(self) -> MutableRNG:
        return self._event_rng
    
    @property
    def merchant_rng(self) -> MutableRNG:
        return self._merchant_rng
    
    @property
    def card_rng(self) -> MutableRNG:
        return self._card_rng
    
    @property
    def treasure_rng(self) -> MutableRNG:
        return self._treasure_rng
    
    @property
    def relic_rng(self) -> MutableRNG:
        return self._relic_rng
    
    @property
    def monster_hp_rng(self) -> MutableRNG:
        return self._monster_hp_rng
    
    @property
    def potion_rng(self) -> MutableRNG:
        return self._potion_rng
    
    @property
    def ai_rng(self) -> MutableRNG:
        return self._ai_rng
    
    @property
    def shuffle_rng(self) -> MutableRNG:
        return self._shuffle_rng
    
    @property
    def card_random_rng(self) -> MutableRNG:
        return self._card_random_rng
    
    @property
    def misc_rng(self) -> MutableRNG:
        return self._misc_rng

    @property
    def map_rng(self) -> MutableRNG:
        return self._map_rng


@dataclass(frozen=True)
class SettingsSeed:
    seed_set: bool
    seed_long: int | None

    @staticmethod
    def from_seed_string(seed_str: str) -> "SettingsSeed":
        from sts_py.engine.core.seed import sterilize_seed_string, seed_string_to_long

        ss = sterilize_seed_string(seed_str)
        if ss == "":
            return SettingsSeed(seed_set=False, seed_long=None)
        return SettingsSeed(seed_set=True, seed_long=seed_string_to_long(ss))
