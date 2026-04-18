"""Act 2 & Act 3 monster implementations for Slay The Spire.

Contains all monster classes needed for City and Beyond encounters.
"""
from __future__ import annotations

from dataclasses import dataclass

from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.monsters.intent import MonsterIntent


# =============================================================================
# Generic Proxy for truly missing monsters
# =============================================================================

class GenericMonsterProxy(MonsterBase):
    """Fallback for encounters with no dedicated class."""

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int, act: int = 1,
               is_elite: bool = False, is_boss: bool = False,
               name_proxy: str = "Unknown") -> GenericMonsterProxy:
        base_hp = 30 + (act * 40)
        hp_var = 10 + (act * 10)
        hp = base_hp + hp_rng.random_int(hp_var)
        if is_elite:
            hp = int(hp * 1.5)
        if is_boss:
            hp = int(hp * 4.0)
        m = cls(id=name_proxy.replace(" ", ""), name=name_proxy, hp=hp, max_hp=hp)
        m._act = act
        m._is_elite = is_elite
        m._is_boss = is_boss
        return m

    def get_move(self, roll: int) -> None:
        act = getattr(self, '_act', 1)
        base_dmg = 5 + (act * 5)
        if getattr(self, '_is_elite', False):
            base_dmg += 5
        if getattr(self, '_is_boss', False):
            base_dmg += 10
        if roll < 80:
            self.set_move(MonsterMove(move_id=1, intent=MonsterIntent.ATTACK, base_damage=base_dmg))
        else:
            self.set_move(MonsterMove(move_id=2, intent=MonsterIntent.DEFEND))
            self.gain_block(base_dmg)


def _is_gremlin_monster_id(monster_id: str | None) -> bool:
    normalized = str(monster_id or "").replace(" ", "").replace("_", "").replace("-", "").lower()
    return normalized.startswith("gremlin")


def _create_gremlinleader_spawn(monster_id: str, hp_rng: MutableRNG, ascension: int) -> MonsterBase:
    from sts_py.engine.monsters.exordium import GremlinFat, GremlinSneaky, GremlinTsundere, GremlinWar

    if monster_id == "GremlinFat":
        monster = GremlinFat.create(hp_rng, ascension)
    elif monster_id == "GremlinWarrior":
        monster = GremlinWar.create(hp_rng, ascension)
    elif monster_id == "GremlinThief":
        monster = GremlinSneaky.create(hp_rng, ascension)
    elif monster_id == "GremlinTsundere":
        monster = GremlinTsundere.create(hp_rng, ascension)
    else:
        raise ValueError(f"Unsupported Gremlin Leader spawn id: {monster_id}")

    monster.id = monster_id
    return monster


@dataclass
class GremlinLeader(MonsterBase):
    str_amt: int = 3
    block_amt: int = 6
    stab_dmg: int = 6
    stab_hits: int = 3
    ascension_level: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "GremlinLeader":
        hp = hp_rng.random_int_between(145, 155) if ascension >= 8 else hp_rng.random_int_between(140, 148)
        if ascension >= 18:
            str_amt, block_amt = 5, 10
        elif ascension >= 3:
            str_amt, block_amt = 4, 6
        else:
            str_amt, block_amt = 3, 6

        return cls(
            id="GremlinLeader",
            name="Gremlin Leader",
            hp=hp,
            max_hp=hp,
            str_amt=str_amt,
            block_amt=block_amt,
            stab_dmg=6,
            stab_hits=3,
            ascension_level=ascension,
        )

    def _num_alive_gremlins(self) -> int:
        return sum(
            1
            for monster in getattr(self.state, "monsters", [])
            if monster is not self and not monster.is_dead() and _is_gremlin_monster_id(getattr(monster, "id", None))
        )

    def _reroll(self, minimum: int, maximum: int) -> int:
        ai_rng = getattr(self, "ai_rng", None)
        if ai_rng is None:
            return minimum
        return ai_rng.random_int_between(minimum, maximum)

    def get_move(self, roll: int) -> None:
        alive_gremlins = self._num_alive_gremlins()
        if alive_gremlins <= 0:
            if roll < 75:
                if not self.last_move(2):
                    self.set_move(MonsterMove(2, MonsterIntent.UNKNOWN, name="Rally"))
                    return
                self.set_move(
                    MonsterMove(
                        4,
                        MonsterIntent.ATTACK,
                        self.stab_dmg,
                        multiplier=self.stab_hits,
                        is_multi_damage=True,
                        name="Stab",
                    )
                )
                return
            if not self.last_move(4):
                self.set_move(
                    MonsterMove(
                        4,
                        MonsterIntent.ATTACK,
                        self.stab_dmg,
                        multiplier=self.stab_hits,
                        is_multi_damage=True,
                        name="Stab",
                    )
                )
                return
            self.set_move(MonsterMove(2, MonsterIntent.UNKNOWN, name="Rally"))
            return

        if alive_gremlins < 2:
            if roll < 50:
                if not self.last_move(2):
                    self.set_move(MonsterMove(2, MonsterIntent.UNKNOWN, name="Rally"))
                else:
                    self.get_move(self._reroll(50, 99))
                return
            if roll < 80:
                if not self.last_move(3):
                    self.set_move(MonsterMove(3, MonsterIntent.DEFEND_BUFF, name="Encourage"))
                else:
                    self.set_move(
                        MonsterMove(
                            4,
                            MonsterIntent.ATTACK,
                            self.stab_dmg,
                            multiplier=self.stab_hits,
                            is_multi_damage=True,
                            name="Stab",
                        )
                    )
                return
            if not self.last_move(4):
                self.set_move(
                    MonsterMove(
                        4,
                        MonsterIntent.ATTACK,
                        self.stab_dmg,
                        multiplier=self.stab_hits,
                        is_multi_damage=True,
                        name="Stab",
                    )
                )
            else:
                self.get_move(self._reroll(0, 80))
            return

        if roll < 66:
            if not self.last_move(3):
                self.set_move(MonsterMove(3, MonsterIntent.DEFEND_BUFF, name="Encourage"))
            else:
                self.set_move(
                    MonsterMove(
                        4,
                        MonsterIntent.ATTACK,
                        self.stab_dmg,
                        multiplier=self.stab_hits,
                        is_multi_damage=True,
                        name="Stab",
                    )
                )
            return

        if not self.last_move(4):
            self.set_move(
                MonsterMove(
                    4,
                    MonsterIntent.ATTACK,
                    self.stab_dmg,
                    multiplier=self.stab_hits,
                    is_multi_damage=True,
                    name="Stab",
                )
            )
            return
        self.set_move(MonsterMove(3, MonsterIntent.DEFEND_BUFF, name="Encourage"))

    def _record_spawn_event(self, event: dict[str, object]) -> None:
        java_turn = int(getattr(self.state, "_replay_java_turn", -1) or -1)
        spawn_events_by_turn = getattr(self.state, "_replay_gremlinleader_spawn_events_by_turn", None)
        if not isinstance(spawn_events_by_turn, dict):
            return
        spawn_events_by_turn.setdefault(java_turn, []).append(event)

    def _runtime_spawn_insert_index(self) -> int:
        monsters = list(getattr(self.state, "monsters", []))
        for idx, monster in enumerate(monsters):
            if monster is self:
                continue
            if monster.is_dead() and _is_gremlin_monster_id(getattr(monster, "id", None)):
                return idx
        for idx, monster in enumerate(monsters):
            if monster is self:
                return idx
        return len(monsters)

    def _assign_spawn_summary_slot(self, monster: MonsterBase) -> int | None:
        summary_slots = getattr(self.state, "_replay_gremlinleader_summary_slots", None)
        pending_slot_indices = getattr(self.state, "_replay_gremlinleader_pending_summary_slot_indices", None)
        if not isinstance(summary_slots, list) or not isinstance(pending_slot_indices, list) or not pending_slot_indices:
            return None
        slot_idx = int(pending_slot_indices.pop(0))
        if 0 <= slot_idx < len(summary_slots):
            summary_slots[slot_idx] = monster
            return slot_idx
        return None

    def _summon_pending_gremlins(self) -> None:
        pending_spawn_ids = getattr(self.state, "_replay_gremlinleader_pending_spawn_ids", None)
        hp_rng = getattr(self.state, "rng", None)
        if not isinstance(pending_spawn_ids, list) or hp_rng is None:
            return

        for _ in range(min(2, len(pending_spawn_ids))):
            spawn_id = str(pending_spawn_ids.pop(0))
            spawned = _create_gremlinleader_spawn(spawn_id, hp_rng, self.ascension_level)
            spawned.state = self.state
            spawned.powers.set_context("monster", spawned.id)
            spawned.next_move = None
            insert_idx = self._runtime_spawn_insert_index()
            self.state.monsters.insert(insert_idx, spawned)
            summary_slot_idx = self._assign_spawn_summary_slot(spawned)
            self._record_spawn_event(
                {
                    "monster_id": spawn_id,
                    "runtime_insert_idx": insert_idx,
                    "summary_slot_idx": summary_slot_idx,
                }
            )

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return

        if self.next_move.move_id == 2:
            self._summon_pending_gremlins()
            return

        if self.next_move.move_id == 3:
            for monster in self.state.monsters:
                if monster.is_dead() or not _is_gremlin_monster_id(getattr(monster, "id", None)):
                    continue
                monster.gain_strength(self.str_amt)
                if monster is not self:
                    monster.gain_block(self.block_amt)
            return

        if self.next_move.move_id == 4:
            damage = self.get_intent_damage()
            for _ in range(self.stab_hits):
                player.take_damage(damage)


# =============================================================================
# ACT 2 — The City
# =============================================================================

@dataclass
class SphericGuardian(MonsterBase):
    slam_dmg: int = 10
    activate_block: int = 25
    harden_block: int = 15
    frail_amount: int = 5
    second_move: bool = True

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "SphericGuardian":
        slam_dmg = 11 if ascension >= 2 else 10
        activate_block = 35 if ascension >= 17 else 25
        return cls(
            id="SphericGuardian",
            name="Spheric Guardian",
            hp=20,
            max_hp=20,
            slam_dmg=slam_dmg,
            activate_block=activate_block,
        )

    def use_pre_battle_action(self) -> None:
        self.gain_block(40)
        self.add_power(create_power("Artifact", 3, self.id))

    def get_move(self, roll: int) -> None:
        if self.first_move:
            self.first_move = False
            self.set_move(MonsterMove(2, MonsterIntent.DEFEND, name="Activate"))
            return
        if self.second_move:
            self.second_move = False
            self.set_move(MonsterMove(4, MonsterIntent.ATTACK_DEBUFF, self.slam_dmg, name="Slam"))
            return
        if self.last_move(1):
            self.set_move(MonsterMove(3, MonsterIntent.ATTACK_DEFEND, self.slam_dmg, name="Harden"))
            return
        self.set_move(
            MonsterMove(
                1,
                MonsterIntent.ATTACK,
                self.slam_dmg,
                multiplier=2,
                is_multi_damage=True,
                name="Slam",
            )
        )

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move_id = int(getattr(self.next_move, "move_id", -1) or -1)
        if move_id == 1:
            damage = self.get_intent_damage()
            if damage > 0:
                player.take_damage(damage)
                player.take_damage(damage)
            return
        if move_id == 2:
            self.gain_block(self.activate_block)
            return
        if move_id == 3:
            self.gain_block(self.harden_block)
            damage = self.get_intent_damage()
            if damage > 0:
                player.take_damage(damage)
            return
        if move_id == 4:
            damage = self.get_intent_damage()
            if damage > 0:
                player.take_damage(damage)
            player.add_power(create_power("Frail", self.frail_amount, player.id, is_source_monster=True))


@dataclass
class Chosen(MonsterBase):
    poke_dmg: int = 6
    zap_dmg: int = 18
    drain_amount: int = 2

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Chosen":
        hp = hp_rng.random_int_between(98, 103) if ascension >= 7 else hp_rng.random_int_between(95, 100)
        return cls(id="Chosen", name="Chosen", hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        MOVE_POKE = 1
        MOVE_ZAP = 2
        MOVE_DRAIN = 3
        MOVE_HEX = 4
        if self.first_move:
            self.first_move = False
            self.set_move(MonsterMove(MOVE_HEX, MonsterIntent.DEBUFF, name="Hex"))
            return
        if roll < 40:
            if self.last_two_moves(MOVE_POKE):
                self.set_move(MonsterMove(MOVE_ZAP, MonsterIntent.ATTACK, self.zap_dmg, name="Zap"))
            else:
                self.set_move(MonsterMove(MOVE_POKE, MonsterIntent.ATTACK, self.poke_dmg, name="Poke"))
        elif roll < 70:
            self.set_move(MonsterMove(MOVE_ZAP, MonsterIntent.ATTACK, self.zap_dmg, name="Zap"))
        else:
            self.set_move(MonsterMove(MOVE_DRAIN, MonsterIntent.BUFF, name="Drain"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.intent.is_attack():
            player.take_damage(self.get_intent_damage())
        elif move.intent.is_buff():
            self.gain_strength(self.drain_amount)
        elif move.intent.is_debuff():
            combat_state = getattr(self, "_combat_state", None)
            if combat_state is not None and combat_state.card_manager is not None:
                combat_state.card_manager.discard_pile.add(CardInstance(card_id="Dazed"))


@dataclass
class BookOfStabbing(MonsterBase):
    multi_stab_dmg: int = 6
    heavy_stab_dmg: int = 15
    stab_count: int = 2

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "BookOfStabbing":
        hp = hp_rng.random_int_between(168, 172) if ascension >= 8 else hp_rng.random_int_between(160, 168)
        return cls(
            id="BookOfStabbing",
            name="Book of Stabbing",
            hp=hp,
            max_hp=hp,
            multi_stab_dmg=7 if ascension >= 3 else 6,
            heavy_stab_dmg=16 if ascension >= 3 else 15,
            stab_count=2,
        )

    def get_move(self, roll: int) -> None:
        move_multi_stab = 1
        move_heavy_stab = 2
        if self.first_move:
            self.first_move = False
            self.set_move(
                MonsterMove(
                    move_multi_stab,
                    MonsterIntent.ATTACK,
                    self.multi_stab_dmg,
                    multiplier=max(2, int(self.stab_count)),
                    is_multi_damage=True,
                    name="Multi-Stab",
                )
            )
            return
        if roll < 15:
            self.set_move(MonsterMove(move_heavy_stab, MonsterIntent.ATTACK, self.heavy_stab_dmg, name="Single Stab"))
            return
        self.stab_count = max(2, int(self.stab_count) + 1)
        self.set_move(
            MonsterMove(
                move_multi_stab,
                MonsterIntent.ATTACK,
                self.multi_stab_dmg,
                multiplier=max(2, int(self.stab_count)),
                is_multi_damage=True,
                name="Multi-Stab",
            )
        )

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.is_multi_damage and int(move.multiplier or 0) > 0:
            damage = self.get_intent_damage()
            for _ in range(int(move.multiplier)):
                player.take_damage(damage)
            return
        if move.intent.is_attack():
            player.take_damage(self.get_intent_damage())


@dataclass
class ShellParasite(MonsterBase):
    fell_dmg: int = 6
    suck_dmg: int = 18
    double_strike_dmg: int = 7

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "ShellParasite":
        hp = hp_rng.random_int_between(74, 78) if ascension >= 7 else hp_rng.random_int_between(68, 72)
        return cls(id="ShellParasite", name="Shell Parasite", hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        MOVE_FELL = 1
        MOVE_SUCK = 2
        MOVE_DOUBLE = 3
        if roll < 30:
            self.set_move(MonsterMove(MOVE_SUCK, MonsterIntent.ATTACK_BUFF, self.suck_dmg, name="Suck"))
        elif roll < 70:
            self.set_move(MonsterMove(MOVE_DOUBLE, MonsterIntent.ATTACK, self.double_strike_dmg, name="Double Strike"))
        else:
            self.set_move(MonsterMove(MOVE_FELL, MonsterIntent.ATTACK_DEBUFF, self.fell_dmg, name="Fell"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.intent == MonsterIntent.ATTACK_DEBUFF:  # Fell
            player.take_damage(self.get_intent_damage())
            player.add_power(create_power("Weak", 2, player.id))
        elif move.intent == MonsterIntent.ATTACK_BUFF:  # Suck
            player.take_damage(self.get_intent_damage())
            self.gain_strength(2)
        elif move.intent.is_attack():  # Double Strike
            damage = self.get_intent_damage()
            hits = max(1, int(getattr(move, "multiplier", 0) or 2))
            for _ in range(hits):
                player.take_damage(damage)


@dataclass
class Byrd(MonsterBase):
    peck_dmg: int = 1
    peck_count: int = 5
    swoop_dmg: int = 12
    headbutt_dmg: int = 3
    flight_amt: int = 3
    first_move: bool = True
    is_flying: bool = True

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Byrd":
        hp = hp_rng.random_int_between(26, 33) if ascension >= 7 else hp_rng.random_int_between(25, 31)
        peck_count = 6 if ascension >= 2 else 5
        swoop_dmg = 14 if ascension >= 2 else 12
        flight_amt = 4 if ascension >= 17 else 3
        return cls(
            id="Byrd",
            name="Byrd",
            hp=hp,
            max_hp=hp,
            peck_count=peck_count,
            swoop_dmg=swoop_dmg,
            headbutt_dmg=3,
            flight_amt=flight_amt,
        )

    def get_move(self, roll: int) -> None:
        MOVE_PECK = 1
        MOVE_GO_AIRBORNE = 2
        MOVE_SWOOP = 3
        MOVE_STUN = 4
        MOVE_HEADBUTT = 5
        MOVE_CAW = 6
        if self.first_move:
            self.first_move = False
            if self.ai_rng is not None and self.ai_rng.random_boolean_chance(0.375):
                self.set_move(MonsterMove(MOVE_CAW, MonsterIntent.BUFF, name="Caw"))
            else:
                self.set_move(
                    MonsterMove(
                        MOVE_PECK,
                        MonsterIntent.ATTACK,
                        self.peck_dmg,
                        multiplier=self.peck_count,
                        is_multi_damage=True,
                        name="Peck",
                    )
                )
            return
        if self.is_flying:
            if roll < 50:
                if self.last_two_moves(MOVE_PECK):
                    if self.ai_rng is not None and self.ai_rng.random_boolean_chance(0.4):
                        self.set_move(MonsterMove(MOVE_SWOOP, MonsterIntent.ATTACK, self.swoop_dmg, name="Swoop"))
                    else:
                        self.set_move(MonsterMove(MOVE_CAW, MonsterIntent.BUFF, name="Caw"))
                else:
                    self.set_move(
                        MonsterMove(
                            MOVE_PECK,
                            MonsterIntent.ATTACK,
                            self.peck_dmg,
                            multiplier=self.peck_count,
                            is_multi_damage=True,
                            name="Peck",
                        )
                    )
            elif roll < 70:
                if self.last_move(MOVE_SWOOP):
                    if self.ai_rng is not None and self.ai_rng.random_boolean_chance(0.375):
                        self.set_move(MonsterMove(MOVE_CAW, MonsterIntent.BUFF, name="Caw"))
                    else:
                        self.set_move(
                            MonsterMove(
                                MOVE_PECK,
                                MonsterIntent.ATTACK,
                                self.peck_dmg,
                                multiplier=self.peck_count,
                                is_multi_damage=True,
                                name="Peck",
                            )
                        )
                else:
                    self.set_move(MonsterMove(MOVE_SWOOP, MonsterIntent.ATTACK, self.swoop_dmg, name="Swoop"))
            elif self.last_move(MOVE_CAW):
                if self.ai_rng is not None and self.ai_rng.random_boolean_chance(0.2857):
                    self.set_move(MonsterMove(MOVE_SWOOP, MonsterIntent.ATTACK, self.swoop_dmg, name="Swoop"))
                else:
                    self.set_move(
                        MonsterMove(
                            MOVE_PECK,
                            MonsterIntent.ATTACK,
                            self.peck_dmg,
                            multiplier=self.peck_count,
                            is_multi_damage=True,
                            name="Peck",
                        )
                    )
            else:
                self.set_move(MonsterMove(MOVE_CAW, MonsterIntent.BUFF, name="Caw"))
        else:
            self.set_move(MonsterMove(MOVE_HEADBUTT, MonsterIntent.ATTACK, self.headbutt_dmg, name="Headbutt"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move_id = int(getattr(self.next_move, "move_id", -1) or -1)
        if move_id == 1:
            damage = self.get_intent_damage()
            for _ in range(max(1, int(self.peck_count or 1))):
                player.take_damage(damage)
            return
        if move_id == 3:
            player.take_damage(self.get_intent_damage())
            return
        if move_id == 5:
            player.take_damage(self.get_intent_damage())
            self.set_move(MonsterMove(2, MonsterIntent.UNKNOWN, name="Go Airborne"))
            return
        if move_id == 2:
            self.is_flying = True
            return
        if move_id == 6:
            self.gain_strength(1)
            return
        if move_id == 4:
            return

    def take_damage(self, amount: int) -> int:
        actual_damage = super().take_damage(amount)
        airborne_hits = int(getattr(self, "_byrd_airborne_hits", 0) or 0)
        if self.is_flying and actual_damage > 0:
            airborne_hits += 1
            if airborne_hits >= self.flight_amt:
                self.is_flying = False
                self._byrd_airborne_hits = 0
                self.set_move(MonsterMove(4, MonsterIntent.STUN, name="Stunned"))
                return actual_damage
        self._byrd_airborne_hits = airborne_hits
        return actual_damage


@dataclass
class SnakePlant(MonsterBase):
    chomp_dmg: int = 7
    vine_dmg: int = 3

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "SnakePlant":
        hp = hp_rng.random_int_between(78, 82) if ascension >= 7 else hp_rng.random_int_between(75, 79)
        return cls(id="SnakePlant", name="Snake Plant", hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        MOVE_CHOMP = 1
        MOVE_VINE = 2
        if roll < 65:
            if self.last_two_moves(MOVE_CHOMP):
                self.set_move(MonsterMove(MOVE_VINE, MonsterIntent.ATTACK_DEBUFF, self.vine_dmg, name="Vine Strike"))
            else:
                self.set_move(MonsterMove(MOVE_CHOMP, MonsterIntent.ATTACK, self.chomp_dmg, multiplier=3, is_multi_damage=True, name="Chomp"))
        else:
            if self.last_move(MOVE_VINE):
                self.set_move(MonsterMove(MOVE_CHOMP, MonsterIntent.ATTACK, self.chomp_dmg, multiplier=3, is_multi_damage=True, name="Chomp"))
            else:
                self.set_move(MonsterMove(MOVE_VINE, MonsterIntent.ATTACK_DEBUFF, self.vine_dmg, name="Vine Strike"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.intent == MonsterIntent.ATTACK_DEBUFF:  # Vine Strike
            player.take_damage(self.get_intent_damage())
            player.add_power(create_power("Frail", 2, player.id))
        elif move.intent.is_attack():  # Chomp
            damage = self.get_intent_damage()
            hits = max(1, int(getattr(move, "multiplier", 0) or 3))
            for _ in range(hits):
                player.take_damage(damage)


@dataclass
class Snecko(MonsterBase):
    bite_dmg: int = 15
    tail_whip_dmg: int = 8

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Snecko":
        hp = hp_rng.random_int_between(120, 125) if ascension >= 7 else hp_rng.random_int_between(114, 119)
        return cls(id="Snecko", name="Snecko", hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        MOVE_BITE = 1
        MOVE_TAIL = 2
        MOVE_GLARE = 3
        if roll < 40:
            self.set_move(MonsterMove(MOVE_BITE, MonsterIntent.ATTACK, self.bite_dmg, name="Bite"))
        elif roll < 70:
            self.set_move(MonsterMove(MOVE_TAIL, MonsterIntent.ATTACK_DEBUFF, self.tail_whip_dmg, name="Tail Whip"))
        else:
            self.set_move(MonsterMove(MOVE_GLARE, MonsterIntent.DEBUFF, name="Glare"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        move_id = int(getattr(move, "move_id", 0) or 0)

        if move_id == 1 or move.intent == MonsterIntent.STRONG_DEBUFF:
            try:
                from sts_py.engine.combat.powers import ConfusedPower
                player.add_power(ConfusedPower())
            except Exception:
                pass
            return

        if move_id == 2 or move.intent == MonsterIntent.ATTACK:
            damage = self.get_intent_damage()
            if damage > 0:
                player.take_damage(damage)
            return

        if move_id == 3 or move.intent == MonsterIntent.ATTACK_DEBUFF:
            damage = self.get_intent_damage()
            if damage > 0:
                player.take_damage(damage)
            try:
                player.add_power(create_power("Vulnerable", 2, "player", is_source_monster=True))
            except Exception:
                pass


@dataclass
class Centurion(MonsterBase):
    fury_dmg: int = 6
    slam_dmg: int = 12
    fury_hits: int = 3
    defend_block: int = 15

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Centurion":
        hp = hp_rng.random_int_between(78, 82) if ascension >= 7 else hp_rng.random_int_between(76, 80)
        defend_block = 20 if ascension >= 17 else 15
        fury_dmg = 7 if ascension >= 2 else 6
        slam_dmg = 14 if ascension >= 2 else 12
        return cls(
            id="Centurion",
            name="Centurion",
            hp=hp,
            max_hp=hp,
            fury_dmg=fury_dmg,
            slam_dmg=slam_dmg,
            fury_hits=3,
            defend_block=defend_block,
        )

    def get_move(self, roll: int) -> None:
        MOVE_FURY = 1
        MOVE_DEFEND = 2
        MOVE_SLAM = 3
        alive_count = sum(1 for monster in getattr(getattr(self, "state", None), "monsters", []) if not monster.is_dead())
        if roll >= 65 and not self.last_two_moves(MOVE_DEFEND) and not self.last_two_moves(MOVE_SLAM):
            if alive_count > 1:
                self.set_move(MonsterMove(MOVE_DEFEND, MonsterIntent.DEFEND, name="Protect"))
                return
            self.set_move(MonsterMove(MOVE_SLAM, MonsterIntent.ATTACK, self.fury_dmg, multiplier=self.fury_hits, is_multi_damage=True, name="Fury"))
            return
        if not self.last_two_moves(MOVE_FURY):
            self.set_move(MonsterMove(MOVE_FURY, MonsterIntent.ATTACK, self.slam_dmg, name="Slash"))
            return
        if alive_count > 1:
            self.set_move(MonsterMove(MOVE_DEFEND, MonsterIntent.DEFEND, name="Defend"))
            return
        self.set_move(MonsterMove(MOVE_SLAM, MonsterIntent.ATTACK, self.fury_dmg, multiplier=self.fury_hits, is_multi_damage=True, name="Fury"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move_id = int(getattr(self.next_move, "move_id", -1) or -1)
        if move_id == 1:
            player.take_damage(self.get_intent_damage())
            return
        if move_id == 2:
            combat_state = getattr(self, "state", None)
            targets = [monster for monster in getattr(combat_state, "monsters", []) if not monster.is_dead()]
            if targets:
                target = next((monster for monster in targets if monster is not self), self)
                target.gain_block(self.defend_block)
            return
        if move_id == 3:
            damage = max(0, int(getattr(self.next_move, "base_damage", 0) or self.fury_dmg))
            for _ in range(max(1, int(self.fury_hits or 1))):
                player.take_damage(damage)


@dataclass
class Healer(MonsterBase):
    attack_dmg: int = 8
    heal_amount: int = 16
    str_amount: int = 2

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Healer":
        hp = hp_rng.random_int_between(50, 56) if ascension >= 7 else hp_rng.random_int_between(48, 54)
        if ascension >= 17:
            attack_dmg = 9
            str_amount = 4
            heal_amount = 20
        elif ascension >= 2:
            attack_dmg = 9
            str_amount = 3
            heal_amount = 16
        else:
            attack_dmg = 8
            str_amount = 2
            heal_amount = 16
        return cls(
            id="Healer",
            name="Healer",
            hp=hp,
            max_hp=hp,
            attack_dmg=attack_dmg,
            heal_amount=heal_amount,
            str_amount=str_amount,
        )

    def get_move(self, roll: int) -> None:
        MOVE_ATTACK = 1
        MOVE_HEAL = 2
        MOVE_BUFF = 3
        combat_state = getattr(self, "state", None)
        monsters = [monster for monster in getattr(combat_state, "monsters", []) if not monster.is_dead()]
        need_to_heal = sum(max(0, int(getattr(monster, "max_hp", 0) or 0) - int(getattr(monster, "hp", 0) or 0)) for monster in monsters)
        heal_threshold = 20 if self.str_amount >= 4 else 15
        if need_to_heal > heal_threshold and not self.last_two_moves(MOVE_HEAL):
            self.set_move(MonsterMove(MOVE_HEAL, MonsterIntent.BUFF, name="Heal"))
            return
        if self.str_amount >= 4:
            if roll >= 40 and not self.last_move(MOVE_ATTACK):
                self.set_move(MonsterMove(MOVE_ATTACK, MonsterIntent.ATTACK_DEBUFF, self.attack_dmg, name="Attack"))
                return
        elif roll >= 40 and not self.last_two_moves(MOVE_ATTACK):
            self.set_move(MonsterMove(MOVE_ATTACK, MonsterIntent.ATTACK_DEBUFF, self.attack_dmg, name="Attack"))
            return
        if not self.last_two_moves(MOVE_BUFF):
            self.set_move(MonsterMove(MOVE_BUFF, MonsterIntent.BUFF, name="Buff"))
            return
        self.set_move(MonsterMove(MOVE_ATTACK, MonsterIntent.ATTACK_DEBUFF, self.attack_dmg, name="Attack"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move_id = int(getattr(self.next_move, "move_id", -1) or -1)
        combat_state = getattr(self, "state", None)
        monsters = [monster for monster in getattr(combat_state, "monsters", []) if not monster.is_dead()]
        if move_id == 1:
            player.take_damage(self.get_intent_damage())
            player.add_power(create_power("Frail", 2, player.id))
            return
        if move_id == 2:
            for monster in monsters:
                monster.hp = min(monster.max_hp, monster.hp + self.heal_amount)
            return
        if move_id == 3:
            for monster in monsters:
                monster.gain_strength(self.str_amount)
            return


# =============================================================================
# ACT 3 — The Beyond
# =============================================================================

@dataclass
class Darkling(MonsterBase):
    nip_dmg: int = 7
    chomp_dmg: int = 8
    block_amt: int = 12
    harden_str_amt: int = 0
    can_revive: bool = True
    half_dead: bool = False

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Darkling":
        hp = hp_rng.random_int_between(50, 59) if ascension >= 7 else hp_rng.random_int_between(48, 56)
        chomp_dmg = 9 if ascension >= 2 else 8
        nip_dmg = hp_rng.random_int_between(9, 13) if ascension >= 2 else hp_rng.random_int_between(7, 11)
        harden_str_amt = 2 if ascension >= 17 else 0
        return cls(
            id="Darkling",
            name="Darkling",
            hp=hp,
            max_hp=hp,
            chomp_dmg=chomp_dmg,
            nip_dmg=nip_dmg,
            harden_str_amt=harden_str_amt,
        )

    def get_move(self, roll: int) -> None:
        MOVE_CHOMP = 1
        MOVE_HARDEN = 2
        MOVE_NIP = 3
        MOVE_COUNT = 4
        MOVE_REINCARNATE = 5
        if self.half_dead:
            self.set_move(MonsterMove(MOVE_REINCARNATE, MonsterIntent.BUFF, name="Reincarnate"))
            return
        if self.first_move:
            self.first_move = False
            if roll < 50:
                intent = MonsterIntent.DEFEND_BUFF if self.harden_str_amt > 0 else MonsterIntent.DEFEND
                self.set_move(MonsterMove(MOVE_HARDEN, intent, name="Harden"))
            else:
                self.set_move(MonsterMove(MOVE_NIP, MonsterIntent.ATTACK, self.nip_dmg, name="Nip"))
            return
        if roll < 40:
            if not self.last_move(MOVE_CHOMP):
                self.set_move(
                    MonsterMove(
                        MOVE_CHOMP,
                        MonsterIntent.ATTACK,
                        self.chomp_dmg,
                        multiplier=2,
                        is_multi_damage=True,
                        name="Chomp",
                    )
                )
            else:
                self.get_move(70)
        elif roll < 70:
            if not self.last_move(MOVE_HARDEN):
                intent = MonsterIntent.DEFEND_BUFF if self.harden_str_amt > 0 else MonsterIntent.DEFEND
                self.set_move(MonsterMove(MOVE_HARDEN, intent, name="Harden"))
            else:
                self.set_move(MonsterMove(MOVE_NIP, MonsterIntent.ATTACK, self.nip_dmg, name="Nip"))
        elif not self.last_two_moves(MOVE_NIP):
            self.set_move(MonsterMove(MOVE_NIP, MonsterIntent.ATTACK, self.nip_dmg, name="Nip"))
        else:
            self.get_move(10)

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.move_id == 1:
            damage = self.get_intent_damage()
            if damage > 0:
                player.take_damage(damage)
                player.take_damage(damage)
            return
        if move.move_id == 2:
            self.gain_block(self.block_amt)
            if self.harden_str_amt > 0 and move.intent == MonsterIntent.DEFEND_BUFF:
                self.gain_strength(self.harden_str_amt)
            return
        if move.move_id == 3:
            damage = self.get_intent_damage()
            if damage > 0:
                player.take_damage(damage)
            return
        if move.move_id == 4:
            self.half_dead = True
            self.block = 0
            self.hp = max(1, int(self.hp or 1))
            self.is_dying = False
            return
        if move.move_id == 5:
            self.half_dead = False
            self.block = 0
            self.is_dying = False
            self.hp = max(1, self.max_hp // 2)

    def take_damage(self, amount: int) -> int:
        actual_damage = super().take_damage(amount)
        if self.hp > 0:
            return actual_damage
        if not self.can_revive:
            return actual_damage

        state = getattr(self, "state", None)
        monsters = list(getattr(state, "monsters", [])) if state is not None else []
        other_live_darklings = [
            monster
            for monster in monsters
            if monster is not self
            and getattr(monster, "id", None) == "Darkling"
            and not getattr(monster, "half_dead", False)
            and int(getattr(monster, "hp", 0) or 0) > 0
            and not bool(getattr(monster, "is_dying", False))
        ]
        if other_live_darklings:
            self.half_dead = True
            self.is_dying = False
            self.block = 0
            self.hp = 1
            return actual_damage

        for monster in monsters:
            if getattr(monster, "id", None) != "Darkling":
                continue
            monster.half_dead = False
            monster.block = 0
            monster.hp = 0
            monster.is_dying = True
        return actual_damage


@dataclass
class Exploder(MonsterBase):
    attack_dmg: int = 9

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Exploder":
        hp = hp_rng.random_int_between(30, 35) if ascension >= 7 else hp_rng.random_int_between(30, 34)
        attack_dmg = 11 if ascension >= 2 else 9
        return cls(id="Exploder", name="Exploder", hp=hp, max_hp=hp, attack_dmg=attack_dmg)

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, self.attack_dmg, name="Slam"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.intent.is_attack():
            damage = self.get_intent_damage()
            if damage > 0:
                player.take_damage(damage)
            self.hp = 0
            self.is_dying = True


@dataclass
class Spiker(MonsterBase):
    attack_dmg: int = 7
    starting_thorns: int = 3
    thorns_buff_amt: int = 2
    thorns_count: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Spiker":
        hp = hp_rng.random_int_between(44, 60) if ascension >= 7 else hp_rng.random_int_between(42, 56)
        attack_dmg = 9 if ascension >= 2 else 7
        starting_thorns = 4 if ascension >= 2 else 3
        monster = cls(
            id="Spiker",
            name="Spiker",
            hp=hp,
            max_hp=hp,
            attack_dmg=attack_dmg,
            starting_thorns=starting_thorns,
            thorns_count=starting_thorns,
        )
        monster.add_power(create_power("Thorns", starting_thorns + (3 if ascension >= 17 else 0), monster.id))
        return monster

    def get_move(self, roll: int) -> None:
        MOVE_ATTACK = 1
        MOVE_BUFF = 2
        current_thorns = self.get_power_amount("Thorns")
        if current_thorns > 5:
            self.set_move(MonsterMove(MOVE_ATTACK, MonsterIntent.ATTACK, self.attack_dmg, name="Cut"))
            return
        if roll < 50 and not self.last_move(MOVE_ATTACK):
            self.set_move(MonsterMove(MOVE_ATTACK, MonsterIntent.ATTACK, self.attack_dmg, name="Cut"))
            return
        self.set_move(MonsterMove(MOVE_BUFF, MonsterIntent.BUFF, name="Spike"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.move_id == 1 or move.intent.is_attack():
            damage = self.get_intent_damage()
            if damage > 0:
                player.take_damage(damage)
            return
        if move.move_id == 2 or move.intent.is_buff():
            self.add_power(create_power("Thorns", self.thorns_buff_amt, self.id))
            self.thorns_count += self.thorns_buff_amt


@dataclass
class Repulsor(MonsterBase):
    attack_dmg: int = 11
    daze_amt: int = 2

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Repulsor":
        hp = hp_rng.random_int_between(31, 38) if ascension >= 7 else hp_rng.random_int_between(29, 35)
        attack_dmg = 13 if ascension >= 2 else 11
        return cls(id="Repulsor", name="Repulsor", hp=hp, max_hp=hp, attack_dmg=attack_dmg)

    def get_move(self, roll: int) -> None:
        MOVE_DEBUFF = 1
        MOVE_ATTACK = 2
        if roll < 20 and not self.last_move(MOVE_ATTACK):
            self.set_move(MonsterMove(MOVE_ATTACK, MonsterIntent.ATTACK, self.attack_dmg, name="Bash"))
            return
        self.set_move(MonsterMove(MOVE_DEBUFF, MonsterIntent.DEBUFF, name="Repulse"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.move_id == 1 or move.intent.is_debuff():
            combat_state = getattr(self, "_combat_state", None)
            if combat_state is None:
                combat_state = getattr(self, "state", None)
            if combat_state is None or combat_state.card_manager is None:
                return
            for _ in range(max(0, int(self.daze_amt))):
                combat_state.card_manager.draw_pile.add(CardInstance(card_id="Dazed"))
            return
        if move.move_id == 2 or move.intent.is_attack():
            damage = self.get_intent_damage()
            if damage > 0:
                player.take_damage(damage)


@dataclass
class OrbWalker(MonsterBase):
    laser_dmg: int = 11
    claw_dmg: int = 15

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "OrbWalker":
        hp = hp_rng.random_int_between(95, 103) if ascension >= 7 else hp_rng.random_int_between(90, 98)
        return cls(id="OrbWalker", name="Orb Walker", hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        MOVE_LASER = 1
        MOVE_CLAW = 2
        if self.first_move:
            self.first_move = False
            self.set_move(MonsterMove(MOVE_LASER, MonsterIntent.ATTACK, self.laser_dmg, name="Laser"))
            return
        if roll < 60:
            if self.last_two_moves(MOVE_LASER):
                self.set_move(MonsterMove(MOVE_CLAW, MonsterIntent.ATTACK, self.claw_dmg, name="Claw"))
            else:
                self.set_move(MonsterMove(MOVE_LASER, MonsterIntent.ATTACK, self.laser_dmg, name="Laser"))
        else:
            if self.last_move(MOVE_CLAW):
                self.set_move(MonsterMove(MOVE_LASER, MonsterIntent.ATTACK, self.laser_dmg, name="Laser"))
            else:
                self.set_move(MonsterMove(MOVE_CLAW, MonsterIntent.ATTACK, self.claw_dmg, name="Claw"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        if self.next_move.intent.is_attack():
            player.take_damage(self.get_intent_damage())


@dataclass
class Maw(MonsterBase):
    roar_dmg: int = 5
    slam_dmg: int = 25
    nom_dmg: int = 5

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Maw":
        hp = hp_rng.random_int_between(300, 310) if ascension >= 7 else hp_rng.random_int_between(280, 300)
        return cls(id="Maw", name="Maw", hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        MOVE_ROAR = 1
        MOVE_SLAM = 2
        MOVE_NOM = 3
        MOVE_DROOL = 4
        if self.first_move:
            self.first_move = False
            self.set_move(MonsterMove(MOVE_ROAR, MonsterIntent.DEBUFF, name="Roar"))
            return
        if roll < 40:
            self.set_move(MonsterMove(MOVE_SLAM, MonsterIntent.ATTACK, self.slam_dmg, name="Slam"))
        elif roll < 70:
            self.set_move(MonsterMove(MOVE_NOM, MonsterIntent.ATTACK_BUFF, self.nom_dmg, multiplier=3, is_multi_damage=True, name="Nom"))
        else:
            self.set_move(MonsterMove(MOVE_DROOL, MonsterIntent.DEBUFF, name="Drool"))


@dataclass
class GiantHead(MonsterBase):
    count_dmg: int = 13
    glare_turns: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "GiantHead":
        hp = 500 if ascension >= 8 else 480
        return cls(id="GiantHead", name="Giant Head", hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        MOVE_COUNT = 1
        MOVE_GLARE = 2
        MOVE_GROWING = 3
        self.glare_turns += 1
        if self.glare_turns <= 3:
            self.set_move(MonsterMove(MOVE_COUNT, MonsterIntent.ATTACK, self.count_dmg, name="Count"))
        elif roll < 50:
            self.set_move(MonsterMove(MOVE_GLARE, MonsterIntent.DEBUFF, name="Glare"))
        else:
            self.set_move(MonsterMove(MOVE_GROWING, MonsterIntent.ATTACK, self.count_dmg + self.glare_turns, name="It's Growing"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.intent.is_attack():  # Count / It's Growing
            player.take_damage(self.get_intent_damage())
        elif move.intent.is_debuff():  # Glare
            player.add_power(create_power("Weak", 1, player.id))


@dataclass
class Serpent(MonsterBase):
    tackle_dmg: int = 16
    smash_dmg: int = 22
    constrict_dmg: int = 10

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Serpent":
        hp = 190 if ascension >= 7 else 170
        return cls(
            id="Serpent",
            name="Spire Growth",
            hp=hp,
            max_hp=hp,
            tackle_dmg=18 if ascension >= 2 else 16,
            smash_dmg=25 if ascension >= 2 else 22,
            constrict_dmg=12 if ascension >= 17 else 10,
        )

    def get_move(self, roll: int) -> None:
        MOVE_TACKLE = 1
        MOVE_CONSTRICT = 2
        MOVE_SMASH = 3
        if self.first_move:
            self.first_move = False
            self.set_move(MonsterMove(MOVE_CONSTRICT, MonsterIntent.STRONG_DEBUFF, name="Constrict"))
            return
        if roll < 50 and not self.last_two_moves(MOVE_TACKLE):
            self.set_move(MonsterMove(MOVE_TACKLE, MonsterIntent.ATTACK, self.tackle_dmg, name="Quick Tackle"))
            return
        if not self.last_move(MOVE_CONSTRICT):
            self.set_move(MonsterMove(MOVE_CONSTRICT, MonsterIntent.STRONG_DEBUFF, name="Constrict"))
            return
        if not self.last_two_moves(MOVE_SMASH):
            self.set_move(MonsterMove(MOVE_SMASH, MonsterIntent.ATTACK, self.smash_dmg, name="Smash"))
            return
        self.set_move(MonsterMove(MOVE_TACKLE, MonsterIntent.ATTACK, self.tackle_dmg, name="Quick Tackle"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        move_id = int(getattr(move, "move_id", -1) or -1)
        if move_id == 1:
            player.take_damage(max(0, int(getattr(move, "base_damage", 0) or self.tackle_dmg)))
            return
        if move_id == 2:
            player.add_power(create_power("Constricted", self.constrict_dmg, player.id))
            return
        if move_id == 3:
            player.take_damage(max(0, int(getattr(move, "base_damage", 0) or self.smash_dmg)))
            return


@dataclass
class SlaverBoss(MonsterBase):
    whip_dmg: int = 7
    wound_count: int = 1
    gain_strength_after_attack: bool = False

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "SlaverBoss":
        hp = hp_rng.random_int_between(57, 64) if ascension >= 7 else hp_rng.random_int_between(54, 60)
        wound_count = 3 if ascension >= 18 else (2 if ascension >= 3 else 1)
        return cls(
            id="SlaverBoss",
            name="Taskmaster",
            hp=hp,
            max_hp=hp,
            whip_dmg=7,
            wound_count=wound_count,
            gain_strength_after_attack=ascension >= 18,
        )

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(2, MonsterIntent.ATTACK_DEBUFF, base_damage=self.whip_dmg, name="Scouring Whip"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        player.take_damage(self.get_intent_damage())
        card_manager = getattr(getattr(self, "state", None), "card_manager", None)
        if card_manager is not None:
            for _ in range(max(1, int(self.wound_count or 1))):
                card_manager.discard_pile.add(CardInstance(card_id="Wound"))
        if self.gain_strength_after_attack:
            self.gain_strength(1)


@dataclass
class WrithingMass(MonsterBase):
    attack_dmg: int = 32
    multi_attack_dmg: int = 7
    attack_defend_dmg: int = 15
    attack_debuff_dmg: int = 10
    weak_amount: int = 2
    vulnerable_amount: int = 2
    reactive_amount: int = 0
    malleable_amount: int = 0
    used_mega_debuff: bool = False

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "WrithingMass":
        hp = hp_rng.random_int_between(175, 190) if ascension >= 8 else hp_rng.random_int_between(160, 175)
        return cls(
            id="WrithingMass",
            name="Writhing Mass",
            hp=hp,
            max_hp=hp,
            attack_dmg=38 if ascension >= 2 else 32,
            multi_attack_dmg=9 if ascension >= 2 else 7,
            attack_defend_dmg=16 if ascension >= 2 else 15,
            attack_debuff_dmg=12 if ascension >= 2 else 10,
            weak_amount=2,
            vulnerable_amount=2,
            reactive_amount=3,
            malleable_amount=3,
        )

    def get_move(self, roll: int) -> None:
        if self.first_move:
            self.first_move = False
            if roll < 33:
                self.set_move(
                    MonsterMove(
                        1,
                        MonsterIntent.ATTACK,
                        self.multi_attack_dmg,
                        multiplier=3,
                        is_multi_damage=True,
                        name="Multi-Strike",
                    )
                )
            elif roll < 66:
                self.set_move(MonsterMove(2, MonsterIntent.ATTACK_DEFEND, self.attack_defend_dmg, name="Wither"))
            else:
                self.set_move(MonsterMove(3, MonsterIntent.ATTACK_DEBUFF, self.attack_debuff_dmg, name="Implant"))
            return

        if roll < 10:
            if not self.last_move(0):
                self.set_move(MonsterMove(0, MonsterIntent.ATTACK, self.attack_dmg, name="Flail"))
            elif self.ai_rng is not None:
                self.get_move(self.ai_rng.random_int_between(10, 99))
            else:
                self.set_move(MonsterMove(2, MonsterIntent.ATTACK_DEFEND, self.attack_defend_dmg, name="Wither"))
            return

        if roll < 20:
            if not self.used_mega_debuff and not self.last_move(4):
                self.set_move(MonsterMove(4, MonsterIntent.STRONG_DEBUFF, name="Parasite"))
            elif self.ai_rng is not None and self.ai_rng.random_boolean_chance(0.1):
                self.set_move(MonsterMove(0, MonsterIntent.ATTACK, self.attack_dmg, name="Flail"))
            elif self.ai_rng is not None:
                self.get_move(self.ai_rng.random_int_between(20, 99))
            else:
                self.set_move(MonsterMove(3, MonsterIntent.ATTACK_DEBUFF, self.attack_debuff_dmg, name="Implant"))
            return

        if roll < 40:
            if not self.last_move(3):
                self.set_move(MonsterMove(3, MonsterIntent.ATTACK_DEBUFF, self.attack_debuff_dmg, name="Implant"))
            elif self.ai_rng is not None and self.ai_rng.random_boolean_chance(0.4):
                self.get_move(self.ai_rng.random_int(19))
            elif self.ai_rng is not None:
                self.get_move(self.ai_rng.random_int_between(40, 99))
            else:
                self.set_move(
                    MonsterMove(
                        1,
                        MonsterIntent.ATTACK,
                        self.multi_attack_dmg,
                        multiplier=3,
                        is_multi_damage=True,
                        name="Multi-Strike",
                    )
                )
            return

        if roll < 70:
            if not self.last_move(1):
                self.set_move(
                    MonsterMove(
                        1,
                        MonsterIntent.ATTACK,
                        self.multi_attack_dmg,
                        multiplier=3,
                        is_multi_damage=True,
                        name="Multi-Strike",
                    )
                )
            elif self.ai_rng is not None and self.ai_rng.random_boolean_chance(0.3):
                self.set_move(MonsterMove(2, MonsterIntent.ATTACK_DEFEND, self.attack_defend_dmg, name="Wither"))
            elif self.ai_rng is not None:
                self.get_move(self.ai_rng.random_int(39))
            else:
                self.set_move(MonsterMove(0, MonsterIntent.ATTACK, self.attack_dmg, name="Flail"))
            return

        if not self.last_move(2):
            self.set_move(MonsterMove(2, MonsterIntent.ATTACK_DEFEND, self.attack_defend_dmg, name="Wither"))
        elif self.ai_rng is not None:
            self.get_move(self.ai_rng.random_int(69))
        else:
            self.set_move(MonsterMove(3, MonsterIntent.ATTACK_DEBUFF, self.attack_debuff_dmg, name="Implant"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        move_id = int(getattr(move, "move_id", -1) or -1)

        if move_id == 2 or move.intent == MonsterIntent.ATTACK_DEFEND:
            damage = max(0, int(getattr(move, "base_damage", 0) or self.attack_defend_dmg))
            if damage > 0:
                player.take_damage(damage)
                self.gain_block(damage)
            return

        if move_id == 3 or move.intent == MonsterIntent.ATTACK_DEBUFF:
            damage = max(0, int(getattr(move, "base_damage", 0) or self.attack_debuff_dmg))
            if damage > 0:
                player.take_damage(damage)
            player.add_power(create_power("Weak", self.weak_amount, player.id))
            player.add_power(create_power("Vulnerable", self.vulnerable_amount, player.id))
            return

        if move_id == 1 and getattr(move, "multiplier", 0):
            hits = max(1, int(getattr(move, "multiplier", 1) or 1))
            damage = max(0, int(getattr(move, "base_damage", 0) or self.multi_attack_dmg))
            for _ in range(hits):
                if damage > 0:
                    player.take_damage(damage)
            return

        if move_id == 0 or move.intent == MonsterIntent.ATTACK:
            damage = max(0, int(getattr(move, "base_damage", 0) or self.attack_dmg))
            if damage > 0:
                player.take_damage(damage)
            return

        if move_id == 4 or move.intent == MonsterIntent.STRONG_DEBUFF:
            self.used_mega_debuff = True
            combat_state = getattr(self, "_combat_state", None)
            if combat_state is not None and getattr(combat_state, "card_manager", None) is not None:
                combat_state.card_manager.discard_pile.add(CardInstance(card_id="Parasite"))
            return


@dataclass
class Transient(MonsterBase):
    starting_death_dmg: int = 30
    attack_count: int = 0
    fading_turns: int = 5

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Transient":
        return cls(
            id="Transient",
            name="Transient",
            hp=999,
            max_hp=999,
            starting_death_dmg=40 if ascension >= 2 else 30,
            fading_turns=6 if ascension >= 17 else 5,
        )

    def get_move(self, roll: int) -> None:
        self.set_move(
            MonsterMove(
                1,
                MonsterIntent.ATTACK,
                self.starting_death_dmg + self.attack_count * 10,
                name="Attack",
            )
        )

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        player.take_damage(self.get_intent_damage())
        self.attack_count += 1


@dataclass
class Nemesis(MonsterBase):
    tri_attack_dmg: int = 6
    scythe_dmg: int = 45
    burn_count: int = 3
    scythe_cooldown: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Nemesis":
        hp = 200 if ascension >= 8 else 185
        tri_attack_dmg = 7 if ascension >= 3 else 6
        burn_count = 5 if ascension >= 18 else 3
        return cls(
            id="Nemesis",
            name="Nemesis",
            hp=hp,
            max_hp=hp,
            tri_attack_dmg=tri_attack_dmg,
            scythe_dmg=45,
            burn_count=burn_count,
        )

    def get_move(self, roll: int) -> None:
        MOVE_TRI_ATTACK = 2
        MOVE_SCYTHE = 3
        MOVE_DEBUFF = 4

        self.scythe_cooldown = max(0, int(self.scythe_cooldown) - 1)
        if self.first_move:
            self.first_move = False
            if roll < 50:
                self.set_move(
                    MonsterMove(
                        MOVE_TRI_ATTACK,
                        MonsterIntent.ATTACK,
                        self.tri_attack_dmg,
                        multiplier=3,
                        is_multi_damage=True,
                        name="Attack",
                    )
                )
            else:
                self.set_move(MonsterMove(MOVE_DEBUFF, MonsterIntent.DEBUFF, name="Debuff"))
            return

        if roll < 30:
            if not self.last_move(MOVE_SCYTHE) and self.scythe_cooldown <= 0:
                self.set_move(MonsterMove(MOVE_SCYTHE, MonsterIntent.ATTACK, self.scythe_dmg, name="Scythe"))
                self.scythe_cooldown = 2
            elif self.ai_rng is not None and self.ai_rng.random_int(1) == 0:
                if not self.last_two_moves(MOVE_TRI_ATTACK):
                    self.set_move(
                        MonsterMove(
                            MOVE_TRI_ATTACK,
                            MonsterIntent.ATTACK,
                            self.tri_attack_dmg,
                            multiplier=3,
                            is_multi_damage=True,
                            name="Attack",
                        )
                    )
                else:
                    self.set_move(MonsterMove(MOVE_DEBUFF, MonsterIntent.DEBUFF, name="Debuff"))
            elif not self.last_move(MOVE_DEBUFF):
                self.set_move(MonsterMove(MOVE_DEBUFF, MonsterIntent.DEBUFF, name="Debuff"))
            else:
                self.set_move(
                    MonsterMove(
                        MOVE_TRI_ATTACK,
                        MonsterIntent.ATTACK,
                        self.tri_attack_dmg,
                        multiplier=3,
                        is_multi_damage=True,
                        name="Attack",
                    )
                )
            return

        if roll < 65:
            if not self.last_two_moves(MOVE_TRI_ATTACK):
                self.set_move(
                    MonsterMove(
                        MOVE_TRI_ATTACK,
                        MonsterIntent.ATTACK,
                        self.tri_attack_dmg,
                        multiplier=3,
                        is_multi_damage=True,
                        name="Attack",
                    )
                )
            elif self.ai_rng is not None and self.ai_rng.random_int(1) == 0:
                if self.scythe_cooldown > 0:
                    self.set_move(MonsterMove(MOVE_DEBUFF, MonsterIntent.DEBUFF, name="Debuff"))
                else:
                    self.set_move(MonsterMove(MOVE_SCYTHE, MonsterIntent.ATTACK, self.scythe_dmg, name="Scythe"))
                    self.scythe_cooldown = 2
            else:
                self.set_move(MonsterMove(MOVE_DEBUFF, MonsterIntent.DEBUFF, name="Debuff"))
            return

        if not self.last_move(MOVE_DEBUFF):
            self.set_move(MonsterMove(MOVE_DEBUFF, MonsterIntent.DEBUFF, name="Debuff"))
        elif self.ai_rng is not None and self.ai_rng.random_int(1) == 0 and self.scythe_cooldown <= 0:
            self.set_move(MonsterMove(MOVE_SCYTHE, MonsterIntent.ATTACK, self.scythe_dmg, name="Scythe"))
            self.scythe_cooldown = 2
        else:
            self.set_move(
                MonsterMove(
                    MOVE_TRI_ATTACK,
                    MonsterIntent.ATTACK,
                    self.tri_attack_dmg,
                    multiplier=3,
                    is_multi_damage=True,
                    name="Attack",
                )
            )

    def _expire_intangible_for_new_turn(self) -> None:
        if not self.has_power("Intangible"):
            return
        self.remove_power("Intangible")
        setattr(self, "_nemesis_intangible_ready", False)

    def _apply_end_turn_intangible(self) -> None:
        if not self.has_power("Intangible"):
            self.add_power(create_power("Intangible", 1, self.id))
        setattr(self, "_nemesis_intangible_ready", True)

    def take_damage(self, amount: int) -> int:
        adjusted_amount = int(amount)
        if adjusted_amount > 1 and self.has_power("Intangible"):
            adjusted_amount = 1
        return super().take_damage(adjusted_amount)

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return

        self._expire_intangible_for_new_turn()
        move = self.next_move
        if move.move_id == 2:
            damage = self.get_intent_damage()
            for _ in range(3):
                player.take_damage(damage)
        elif move.move_id == 3:
            player.take_damage(self.get_intent_damage())
        elif move.move_id == 4:
            combat_state = getattr(self, "_combat_state", None)
            if combat_state is None:
                combat_state = getattr(self, "state", None)
            if combat_state is not None and getattr(combat_state, "card_manager", None) is not None:
                for _ in range(max(0, int(self.burn_count))):
                    combat_state.card_manager.discard_pile.add(CardInstance(card_id="Burn"))

        self._apply_end_turn_intangible()


@dataclass
class Reptomancer(MonsterBase):
    snake_strike_dmg: int = 13
    big_bite_dmg: int = 30
    summon_count: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Reptomancer":
        hp = 200 if ascension >= 8 else 180
        return cls(id="Reptomancer", name="Reptomancer", hp=hp, max_hp=hp)

    def get_move(self, roll: int) -> None:
        MOVE_SNAKE_STRIKE = 1
        MOVE_BIG_BITE = 2
        MOVE_SUMMON = 3
        if self.summon_count < 2 and roll < 30:
            self.summon_count += 1
            self.set_move(MonsterMove(MOVE_SUMMON, MonsterIntent.UNKNOWN, name="Summon"))
        elif roll < 65:
            self.set_move(MonsterMove(MOVE_SNAKE_STRIKE, MonsterIntent.ATTACK, self.snake_strike_dmg, multiplier=2, is_multi_damage=True, name="Snake Strike"))
        else:
            self.set_move(MonsterMove(MOVE_BIG_BITE, MonsterIntent.ATTACK, self.big_bite_dmg, name="Big Bite"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move_id = int(getattr(self.next_move, "move_id", -1) or -1)
        if move_id == 1:
            damage = self.get_intent_damage()
            for _ in range(2):
                player.take_damage(damage)
            return
        if move_id == 2:
            player.take_damage(self.get_intent_damage())
            return
        if move_id == 3:
            combat_state = getattr(self, "state", None)
            alive_daggers = [
                monster
                for monster in getattr(combat_state, "monsters", [])
                if not monster.is_dead() and getattr(monster, "id", "") in {"Dagger", "SnakeDagger"}
            ]
            if len(alive_daggers) >= 2 or combat_state is None:
                return
            for _ in range(2 - len(alive_daggers)):
                combat_state.add_monster(SnakeDagger.create(getattr(combat_state, "rng", MutableRNG.from_seed(1, rng_type="monsterHpRng")), 0))


@dataclass
class Dagger(MonsterBase):
    stab_dmg: int = 9
    sacrifice_dmg: int = 25

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Dagger":
        hp = 25
        return cls(id="Dagger", name="Dagger", hp=hp, max_hp=hp, stab_dmg=9, sacrifice_dmg=25)

    def get_move(self, roll: int) -> None:
        MOVE_WOUND = 1
        MOVE_EXPLODE = 2
        if self.first_move:
            self.first_move = False
            self.set_move(MonsterMove(MOVE_WOUND, MonsterIntent.ATTACK_DEBUFF, self.stab_dmg, name="Wound"))
            return
        self.set_move(MonsterMove(MOVE_EXPLODE, MonsterIntent.ATTACK, self.sacrifice_dmg, name="Explode"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move_id = int(getattr(self.next_move, "move_id", -1) or -1)
        if move_id == 1:
            player.take_damage(self.stab_dmg)
            card_manager = getattr(getattr(self, "state", None), "card_manager", None)
            if card_manager is not None:
                card_manager.discard_pile.add(CardInstance(card_id="Wound"))
            return
        if move_id == 2:
            player.take_damage(self.sacrifice_dmg)
            self.hp = 0
            self.is_dying = True


@dataclass
class Taskmaster(SlaverBoss):
    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Taskmaster":
        monster = super().create(hp_rng, ascension)
        monster.id = "Taskmaster"
        monster.name = "Taskmaster"
        return monster


@dataclass
class SpireGrowth(Serpent):
    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "SpireGrowth":
        monster = super().create(hp_rng, ascension)
        monster.id = "SpireGrowth"
        monster.name = "Spire Growth"
        return monster


@dataclass
class SnakeDagger(Dagger):
    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "SnakeDagger":
        monster = super().create(hp_rng, ascension)
        monster.id = "SnakeDagger"
        monster.name = "Dagger"
        return monster


@dataclass
class BanditPointy(MonsterBase):
    attack_dmg: int = 5

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "BanditPointy":
        hp = 34 if ascension >= 7 else 30
        attack_dmg = 6 if ascension >= 2 else 5
        return cls(id="BanditPointy", name="Pointy", hp=hp, max_hp=hp, attack_dmg=attack_dmg)

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, self.attack_dmg, multiplier=2, is_multi_damage=True, name="Pointy Special"))

    def take_turn(self, player) -> None:
        damage = self.get_intent_damage()
        for _ in range(2):
            player.take_damage(damage)


@dataclass
class BanditLeader(MonsterBase):
    slash_dmg: int = 15
    agonize_dmg: int = 10
    weak_amount: int = 2

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "BanditLeader":
        hp = hp_rng.random_int_between(37, 41) if ascension >= 7 else hp_rng.random_int_between(35, 39)
        slash_dmg = 17 if ascension >= 2 else 15
        agonize_dmg = 12 if ascension >= 2 else 10
        weak_amount = 3 if ascension >= 17 else 2
        return cls(id="BanditLeader", name="Romeo", hp=hp, max_hp=hp, slash_dmg=slash_dmg, agonize_dmg=agonize_dmg, weak_amount=weak_amount)

    def get_move(self, roll: int) -> None:
        if self.first_move:
            self.first_move = False
            self.set_move(MonsterMove(2, MonsterIntent.UNKNOWN, name="Mock"))
            return
        if self.last_move(2):
            self.set_move(MonsterMove(3, MonsterIntent.ATTACK_DEBUFF, self.agonize_dmg, name="Agonizing Slash"))
            return
        if self.last_move(3):
            if int(getattr(self, "_bandit_leader_attack_chain", 0) or 0) < (2 if self.weak_amount >= 3 else 1):
                self._bandit_leader_attack_chain = int(getattr(self, "_bandit_leader_attack_chain", 0) or 0) + 1
                self.set_move(MonsterMove(1, MonsterIntent.ATTACK, self.slash_dmg, name="Cross Slash"))
            else:
                self._bandit_leader_attack_chain = 0
                self.set_move(MonsterMove(3, MonsterIntent.ATTACK_DEBUFF, self.agonize_dmg, name="Agonizing Slash"))
            return
        self._bandit_leader_attack_chain = int(getattr(self, "_bandit_leader_attack_chain", 0) or 0)
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, self.slash_dmg, name="Cross Slash"))

    def take_turn(self, player) -> None:
        move_id = int(getattr(getattr(self, "next_move", None), "move_id", -1) or -1)
        if move_id == 1:
            player.take_damage(self.get_intent_damage())
            return
        if move_id == 2:
            return
        if move_id == 3:
            player.take_damage(self.get_intent_damage())
            player.add_power(create_power("Weak", self.weak_amount, player.id))


@dataclass
class BanditBear(MonsterBase):
    maul_dmg: int = 18
    lunge_dmg: int = 9
    lunge_block: int = 9
    dex_reduction: int = -2

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "BanditBear":
        hp = hp_rng.random_int_between(40, 44) if ascension >= 7 else hp_rng.random_int_between(38, 42)
        maul_dmg = 20 if ascension >= 2 else 18
        lunge_dmg = 10 if ascension >= 2 else 9
        dex_reduction = -4 if ascension >= 17 else -2
        return cls(id="BanditBear", name="Bear", hp=hp, max_hp=hp, maul_dmg=maul_dmg, lunge_dmg=lunge_dmg, lunge_block=9, dex_reduction=dex_reduction)

    def get_move(self, roll: int) -> None:
        if self.first_move:
            self.first_move = False
            self.set_move(MonsterMove(2, MonsterIntent.STRONG_DEBUFF, name="Bear Hug"))
            return
        if self.last_move(2) or self.last_move(1):
            self.set_move(MonsterMove(3, MonsterIntent.ATTACK_DEFEND, self.lunge_dmg, name="Lunge"))
            return
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, self.maul_dmg, name="Maul"))

    def take_turn(self, player) -> None:
        move_id = int(getattr(getattr(self, "next_move", None), "move_id", -1) or -1)
        if move_id == 1:
            player.take_damage(self.get_intent_damage())
            return
        if move_id == 2:
            player.add_power(create_power("Dexterity", self.dex_reduction, player.id))
            return
        if move_id == 3:
            player.take_damage(self.get_intent_damage())
            self.gain_block(self.lunge_block)
