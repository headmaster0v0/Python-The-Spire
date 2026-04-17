from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any


def _effective_orb_amount(base: int, focus: int) -> int:
    return max(0, int(base) + int(focus))


def _choose_living_monster(combat_state: Any) -> Any | None:
    monsters = [monster for monster in getattr(combat_state, "monsters", []) if not monster.is_dead()]
    if not monsters:
        return None
    rng = None
    card_manager = getattr(combat_state, "card_manager", None)
    if card_manager is not None:
        rng = getattr(card_manager, "rng", None)
    if rng is None:
        rng = getattr(combat_state, "rng", None)
    if rng is not None and len(monsters) > 1:
        return monsters[rng.random_int(len(monsters) - 1)]
    return monsters[0]


def _apply_orb_damage_to_monster(monster: Any, amount: int) -> int:
    if monster is None or monster.is_dead():
        return 0
    final_amount = max(0, int(amount))
    if final_amount <= 0:
        return 0
    lockon_amount = 0
    if hasattr(monster, "get_power_amount"):
        lockon_amount = max(0, int(monster.get_power_amount("Lockon") or 0))
    if lockon_amount > 0:
        final_amount = int(final_amount * 1.5)
    monster.take_damage(final_amount)
    return final_amount


@dataclass
class BaseOrb:
    orb_id: str
    name: str
    passive_amount: int
    evoke_amount: int

    def passive(self, owner: Any, combat_state: Any) -> int:
        return 0

    def start_of_turn(self, owner: Any, combat_state: Any) -> int:
        return 0

    def evoke(self, owner: Any, combat_state: Any) -> int:
        return 0

    def _focus(self, owner: Any) -> int:
        return int(getattr(owner, "focus", 0) or 0)

    def make_copy(self):
        return copy.deepcopy(self)


@dataclass
class LightningOrb(BaseOrb):
    orb_id: str = "Lightning"
    name: str = "Lightning"
    passive_amount: int = 3
    evoke_amount: int = 8

    def passive(self, owner: Any, combat_state: Any) -> int:
        amount = _effective_orb_amount(self.passive_amount, self._focus(owner))
        if hasattr(owner, "powers") and owner.powers.has_power("Electro"):
            total_damage = 0
            for monster in getattr(combat_state, "monsters", []):
                if monster.is_dead():
                    continue
                total_damage += _apply_orb_damage_to_monster(monster, amount)
            return total_damage
        target = _choose_living_monster(combat_state)
        return _apply_orb_damage_to_monster(target, amount)

    def evoke(self, owner: Any, combat_state: Any) -> int:
        amount = _effective_orb_amount(self.evoke_amount, self._focus(owner))
        if hasattr(owner, "powers") and owner.powers.has_power("Electro"):
            total_damage = 0
            for monster in getattr(combat_state, "monsters", []):
                if monster.is_dead():
                    continue
                total_damage += _apply_orb_damage_to_monster(monster, amount)
            return total_damage
        target = _choose_living_monster(combat_state)
        return _apply_orb_damage_to_monster(target, amount)


@dataclass
class FrostOrb(BaseOrb):
    orb_id: str = "Frost"
    name: str = "Frost"
    passive_amount: int = 2
    evoke_amount: int = 5

    def passive(self, owner: Any, combat_state: Any) -> int:
        amount = _effective_orb_amount(self.passive_amount, self._focus(owner))
        if amount > 0 and hasattr(owner, "gain_block"):
            owner.gain_block(amount)
        return amount

    def evoke(self, owner: Any, combat_state: Any) -> int:
        amount = _effective_orb_amount(self.evoke_amount, self._focus(owner))
        if amount > 0 and hasattr(owner, "gain_block"):
            owner.gain_block(amount)
        return amount


@dataclass
class DarkOrb(BaseOrb):
    orb_id: str = "Dark"
    name: str = "Dark"
    passive_amount: int = 6
    evoke_amount: int = 6
    stored_damage: int = 6

    def passive(self, owner: Any, combat_state: Any) -> int:
        focus = self._focus(owner)
        self.stored_damage = max(0, self.stored_damage + _effective_orb_amount(self.passive_amount, focus))
        return self.stored_damage

    def evoke(self, owner: Any, combat_state: Any) -> int:
        target = _choose_living_monster(combat_state)
        if target is None:
            return 0
        amount = max(0, self.stored_damage)
        return _apply_orb_damage_to_monster(target, amount)


@dataclass
class PlasmaOrb(BaseOrb):
    orb_id: str = "Plasma"
    name: str = "Plasma"
    passive_amount: int = 1
    evoke_amount: int = 2

    def passive(self, owner: Any, combat_state: Any) -> int:
        return 0

    def start_of_turn(self, owner: Any, combat_state: Any) -> int:
        if hasattr(owner, "energy"):
            owner.energy += self.passive_amount
            card_manager = getattr(combat_state, "card_manager", None)
            if card_manager is not None:
                card_manager.set_energy(owner.energy)
        return self.passive_amount

    def evoke(self, owner: Any, combat_state: Any) -> int:
        if hasattr(owner, "energy"):
            owner.energy += self.evoke_amount
            card_manager = getattr(combat_state, "card_manager", None)
            if card_manager is not None:
                card_manager.set_energy(owner.energy)
        return self.evoke_amount


@dataclass
class OrbSlots:
    owner: Any | None = None
    combat_state: Any | None = None
    slots: int = 3
    channels: list[BaseOrb] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.channels)

    def __iter__(self):
        return iter(self.channels)

    def __getitem__(self, index: int) -> BaseOrb:
        return self.channels[index]

    def append(self, orb: BaseOrb) -> None:
        self.channel(orb)

    def channel(self, orb: BaseOrb) -> None:
        if self.slots <= 0:
            return
        while len(self.channels) >= self.slots:
            self.evoke_first()
        self.channels.append(orb)
        if isinstance(orb, FrostOrb) and self.owner is not None:
            current = max(0, int(getattr(self.owner, "_frost_orbs_channeled_this_combat", 0) or 0))
            self.owner._frost_orbs_channeled_this_combat = current + 1

    def evoke_first(self) -> int:
        if not self.channels:
            return 0
        orb = self.channels.pop(0)
        if self.owner is None or self.combat_state is None:
            return 0
        return orb.evoke(self.owner, self.combat_state)

    def evoke_first_twice(self) -> tuple[int, int]:
        if not self.channels or self.owner is None or self.combat_state is None:
            return (0, 0)
        orb = self.channels[0]
        first = orb.evoke(self.owner, self.combat_state)
        second = orb.evoke(self.owner, self.combat_state)
        self.channels.pop(0)
        return (first, second)

    def evoke_and_channel_copy_leftmost(self) -> int:
        if not self.channels or self.owner is None or self.combat_state is None:
            return 0
        original = self.channels[0]
        orb_copy = original.make_copy()
        damage_or_value = self.evoke_first()
        self.channel(orb_copy)
        return damage_or_value

    def filled_count(self) -> int:
        return len(self.channels)

    def decrease_slots(self, amount: int) -> int:
        lost_slots = max(0, int(amount))
        if lost_slots <= 0:
            return 0
        self.slots = max(0, self.slots - lost_slots)
        while len(self.channels) > self.slots:
            self.evoke_first()
        if self.owner is not None and hasattr(self.owner, "max_orbs"):
            self.owner.max_orbs = self.slots
        return self.slots

    def increase_slots(self, amount: int) -> int:
        gained_slots = max(0, int(amount))
        if gained_slots <= 0:
            return self.slots
        self.slots += gained_slots
        if self.owner is not None and hasattr(self.owner, "max_orbs"):
            self.owner.max_orbs = self.slots
        return self.slots

    def remove_all_orbs(self) -> int:
        removed = len(self.channels)
        self.channels.clear()
        return removed

    def evoke_all_orbs(self) -> list[int]:
        results: list[int] = []
        while self.channels:
            results.append(self.evoke_first())
        return results

    def dark_impulse(self, amount: int = 1) -> list[int]:
        if self.owner is None or self.combat_state is None:
            return []
        trigger_count = max(0, int(amount))
        results: list[int] = []
        if trigger_count <= 0:
            return results
        for _ in range(trigger_count):
            for orb in list(self.channels):
                if isinstance(orb, DarkOrb):
                    results.append(orb.passive(self.owner, self.combat_state))
        return results

    def trigger_leftmost_passive(self, amount: int = 1) -> list[int]:
        if self.owner is None or self.combat_state is None or not self.channels:
            return []
        trigger_count = max(0, int(amount))
        results: list[int] = []
        if trigger_count <= 0:
            return results
        leftmost = self.channels[0]
        for _ in range(trigger_count):
            results.append(leftmost.passive(self.owner, self.combat_state))
        return results

    def evoke_leftmost_n_times(self, count: int) -> list[int]:
        if self.owner is None or self.combat_state is None or not self.channels:
            return []
        evoke_count = max(0, int(count))
        if evoke_count <= 0:
            return []
        orb = self.channels[0]
        results: list[int] = []
        for _ in range(max(0, evoke_count - 1)):
            results.append(orb.evoke(self.owner, self.combat_state))
        results.append(self.evoke_first())
        return results

    def trigger_start_of_turn_effects(self) -> list[int]:
        results: list[int] = []
        if self.owner is None or self.combat_state is None:
            return results
        for orb in list(self.channels):
            results.append(orb.start_of_turn(self.owner, self.combat_state))
        return results

    def trigger_passives(self) -> list[int]:
        results: list[int] = []
        if self.owner is None or self.combat_state is None:
            return results
        for orb in list(self.channels):
            results.append(orb.passive(self.owner, self.combat_state))
        extra_rightmost = max(0, int(getattr(self.owner, "_orb_passive_multiply", 0) or 0))
        if extra_rightmost > 0 and self.channels:
            rightmost = self.channels[-1]
            for _ in range(extra_rightmost):
                results.append(rightmost.passive(self.owner, self.combat_state))
        return results
