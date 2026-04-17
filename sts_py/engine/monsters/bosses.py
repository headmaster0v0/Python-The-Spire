"""Boss monsters for Slay The Spire Act 1.

This module implements the three Act 1 bosses:
- Hexaghost: Multi-phase boss with orb mechanics
- Slime Boss: Splits into smaller slimes
- The Guardian: Mode-shifting boss with defensive/offensive phases
"""
from __future__ import annotations

from dataclasses import dataclass

from sts_py.engine.combat.powers import create_power
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.core.rng import MutableRNG


@dataclass
class Hexaghost(MonsterBase):
    sear_dmg: int = 6
    inferno_dmg: int = 2
    fire_tackle_dmg: int = 5
    str_amount: int = 2
    sear_burn_count: int = 1
    activated: bool = False
    orb_active_count: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Hexaghost":
        if ascension >= 9:
            hp = 264
        else:
            hp = 250

        if ascension >= 19:
            str_amount = 3
            sear_burn_count = 2
            fire_tackle_dmg = 6
            inferno_dmg = 3
        elif ascension >= 4:
            str_amount = 2
            sear_burn_count = 1
            fire_tackle_dmg = 6
            inferno_dmg = 3
        else:
            str_amount = 2
            sear_burn_count = 1
            fire_tackle_dmg = 5
            inferno_dmg = 2

        return cls(
            id="Hexaghost",
            name="Hexaghost",
            hp=hp,
            max_hp=hp,
            sear_dmg=6,
            inferno_dmg=inferno_dmg,
            fire_tackle_dmg=fire_tackle_dmg,
            str_amount=str_amount,
            sear_burn_count=sear_burn_count,
        )

    def get_move(self, roll: int) -> None:
        MOVE_DIVIDER = 1
        MOVE_TACKLE = 2
        MOVE_INFLAME = 3
        MOVE_SEAR = 4
        MOVE_ACTIVATE = 5
        MOVE_INFERNO = 6

        if not self.activated:
            self.activated = True
            self.set_move(MonsterMove(MOVE_ACTIVATE, MonsterIntent.UNKNOWN, name="Activate"))
            return

        if self.last_move(MOVE_ACTIVATE):
            divider_dmg = 6
            self.set_move(MonsterMove(MOVE_DIVIDER, MonsterIntent.ATTACK, divider_dmg, name="Divider"))
            return

        if roll < 20:
            if self.last_two_moves(MOVE_INFLAME):
                self.set_move(MonsterMove(MOVE_TACKLE, MonsterIntent.ATTACK, self.fire_tackle_dmg, name="Fire Tackle"))
            else:
                self.set_move(MonsterMove(MOVE_INFLAME, MonsterIntent.BUFF, name="Inflame"))
        elif roll < 40:
            self.set_move(MonsterMove(MOVE_SEAR, MonsterIntent.ATTACK, self.sear_dmg, name="Sear"))
        elif roll < 70:
            self.set_move(MonsterMove(MOVE_TACKLE, MonsterIntent.ATTACK, self.fire_tackle_dmg, name="Fire Tackle"))
        else:
            self.set_move(MonsterMove(MOVE_INFERNO, MonsterIntent.ATTACK, self.inferno_dmg, name="Inferno"))


@dataclass
class SlimeBoss(MonsterBase):
    tackle_dmg: int = 9
    slam_dmg: int = 35
    slimed_count: int = 3
    first_turn: bool = True
    split_triggered: bool = False
    last_move_id: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "SlimeBoss":
        if ascension >= 9:
            hp = 150
        else:
            hp = 140

        if ascension >= 4:
            tackle_dmg = 10
            slam_dmg = 38
        else:
            tackle_dmg = 9
            slam_dmg = 35

        slimed_count = 5 if ascension >= 19 else 3

        return cls(
            id="SlimeBoss",
            name="Slime Boss",
            hp=hp,
            max_hp=hp,
            tackle_dmg=tackle_dmg,
            slam_dmg=slam_dmg,
            slimed_count=slimed_count,
        )

    def get_move(self, roll: int) -> None:
        MOVE_SLAM = 1
        MOVE_PREP = 2
        MOVE_SPLIT = 3
        MOVE_STICKY = 4

        if self.first_turn:
            self.first_turn = False
            self.set_move(MonsterMove(MOVE_STICKY, MonsterIntent.STRONG_DEBUFF, name="Sticky"))
            return

        if self.hp <= self.max_hp // 2 and not self.split_triggered:
            self.split_triggered = True
            self.set_move(MonsterMove(MOVE_SPLIT, MonsterIntent.UNKNOWN, name="Split"))
            return

        if self.last_move_id == MOVE_STICKY:
            self.set_move(MonsterMove(MOVE_SLAM, MonsterIntent.ATTACK, base_damage=self.slam_dmg, name="Slam"))
        elif self.last_move_id == MOVE_SLAM:
            self.set_move(MonsterMove(MOVE_PREP, MonsterIntent.UNKNOWN, name="Prepare"))
        elif self.last_move_id == MOVE_PREP:
            self.set_move(MonsterMove(MOVE_SLAM, MonsterIntent.ATTACK, base_damage=self.slam_dmg, name="Slam"))
        else:
            self.set_move(MonsterMove(MOVE_STICKY, MonsterIntent.STRONG_DEBUFF, name="Sticky"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        self.last_move_id = move.move_id

        MOVE_SLAM = 1
        MOVE_PREP = 2
        MOVE_SPLIT = 3
        MOVE_STICKY = 4

        if move.move_id == MOVE_STICKY:
            from sts_py.engine.content.card_instance import CardInstance
            if hasattr(self, 'state') and self.state and self.state.card_manager:
                for _ in range(self.slimed_count):
                    slimed_card = CardInstance(card_id="Slimed")
                    self.state.card_manager.discard_pile.add(slimed_card)
            self.set_move(MonsterMove(MOVE_PREP, MonsterIntent.UNKNOWN, name="Prepare"))
            self._skip_next_roll = True
        elif move.move_id == MOVE_PREP:
            self.set_move(MonsterMove(MOVE_SLAM, MonsterIntent.ATTACK, base_damage=self.slam_dmg, name="Slam"))
            self._skip_next_roll = True
        elif move.move_id == MOVE_SLAM:
            damage = self.get_intent_damage()
            player.take_damage(damage)
            self.set_move(MonsterMove(MOVE_STICKY, MonsterIntent.STRONG_DEBUFF, name="Sticky"))
            self._skip_next_roll = True
        elif move.move_id == MOVE_SPLIT:
            from sts_py.engine.monsters.exordium import AcidSlimeLarge, SpikeSlimeLarge
            current_hp = self.hp
            self.is_dying = True
            self.hp = 0
            if hasattr(self, 'state') and self.state:
                self.state.add_monster(AcidSlimeLarge.create(self.state.rng, ascension=0, hp=current_hp))
                self.state.add_monster(SpikeSlimeLarge.create(self.state.rng, ascension=0, hp=current_hp))
            self._skip_next_roll = True

    def take_damage(self, amount: int) -> int:
        actual = super().take_damage(amount)
        if not self.is_dying and self.hp <= self.max_hp // 2 and self.next_move and self.next_move.move_id != 3:
            self.split_triggered = True
            self.set_move(MonsterMove(3, MonsterIntent.UNKNOWN, name="Split"))
        return actual


@dataclass
class TheGuardian(MonsterBase):
    fierce_bash_dmg: int = 32
    roll_dmg: int = 9
    whirlwind_dmg: int = 5
    whirlwind_count: int = 4
    twin_slam_dmg: int = 8
    dmg_threshold: int = 30
    dmg_threshold_increase: int = 10
    dmg_taken: int = 0
    is_open: bool = True
    defensive_block: int = 20
    thorns_dmg: int = 3
    vent_debuff: int = 2
    charge_up_block: int = 9
    close_up_triggered: bool = False
    last_move_id: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "TheGuardian":
        if ascension >= 19:
            hp = 250
            dmg_threshold = 40
        elif ascension >= 9:
            hp = 250
            dmg_threshold = 35
        else:
            hp = 240
            dmg_threshold = 30

        if ascension >= 4:
            fierce_bash_dmg = 36
            roll_dmg = 10
        else:
            fierce_bash_dmg = 32
            roll_dmg = 9

        thorns = 4 if ascension >= 19 else 3

        guardian = cls(
            id="TheGuardian",
            name="The Guardian",
            hp=hp,
            max_hp=hp,
            fierce_bash_dmg=fierce_bash_dmg,
            roll_dmg=roll_dmg,
            dmg_threshold=dmg_threshold,
            thorns_dmg=thorns,
        )
        guardian.dmg_taken = 0
        return guardian

    def get_move(self, roll: int) -> None:
        MOVE_CHARGE_UP = 1
        MOVE_FIERCE_BASH = 2
        MOVE_VENT_STEAM = 3
        MOVE_WHIRLWIND = 4
        MOVE_CLOSE_UP = 5
        MOVE_ROLL_ATTACK = 6
        MOVE_TWIN_SLAM = 7

        if self.next_move is not None:
            return

        if self.is_open:
            self.set_move(MonsterMove(MOVE_CHARGE_UP, MonsterIntent.DEFEND, name="Charge Up"))
        else:
            self.set_move(MonsterMove(MOVE_ROLL_ATTACK, MonsterIntent.ATTACK, base_damage=self.roll_dmg, name="Roll Attack"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        self.last_move_id = move.move_id

        MOVE_CHARGE_UP = 1
        MOVE_FIERCE_BASH = 2
        MOVE_VENT_STEAM = 3
        MOVE_WHIRLWIND = 4
        MOVE_CLOSE_UP = 5
        MOVE_ROLL_ATTACK = 6
        MOVE_TWIN_SLAM = 7

        if move.move_id == MOVE_CHARGE_UP:
            self.gain_block(self.charge_up_block)
            self.set_move(MonsterMove(MOVE_FIERCE_BASH, MonsterIntent.ATTACK, base_damage=self.fierce_bash_dmg, name="Fierce Bash"))
            self._skip_next_roll = True
        elif move.move_id == MOVE_FIERCE_BASH:
            damage = self.get_intent_damage()
            player.take_damage(damage)
            self.set_move(MonsterMove(MOVE_VENT_STEAM, MonsterIntent.STRONG_DEBUFF, name="Vent Steam"))
            self._skip_next_roll = True
        elif move.move_id == MOVE_VENT_STEAM:
            from sts_py.engine.combat.powers import WeakPower, VulnerablePower
            player.add_power(WeakPower(amount=self.vent_debuff, owner=player.id))
            player.add_power(VulnerablePower(amount=self.vent_debuff, owner=player.id))
            self.set_move(MonsterMove(MOVE_WHIRLWIND, MonsterIntent.ATTACK, base_damage=self.whirlwind_dmg, is_multi_damage=True, multiplier=self.whirlwind_count, name="Whirlwind"))
            self._skip_next_roll = True
        elif move.move_id == MOVE_WHIRLWIND:
            damage = self.get_intent_damage()
            for _ in range(self.whirlwind_count):
                player.take_damage(damage)
            self.set_move(MonsterMove(MOVE_CHARGE_UP, MonsterIntent.DEFEND, name="Charge Up"))
            self._skip_next_roll = True
        elif move.move_id == MOVE_CLOSE_UP:
            from sts_py.engine.combat.powers import SharpHidePower
            self.gain_block(self.defensive_block)
            self.add_power(SharpHidePower(amount=self.thorns_dmg, owner=self.id))
            self.set_move(MonsterMove(MOVE_ROLL_ATTACK, MonsterIntent.ATTACK, base_damage=self.roll_dmg, name="Roll Attack"))
            self._skip_next_roll = True
        elif move.move_id == MOVE_ROLL_ATTACK:
            damage = self.get_intent_damage()
            player.take_damage(damage)
            self.set_move(MonsterMove(MOVE_TWIN_SLAM, MonsterIntent.ATTACK_BUFF, base_damage=self.twin_slam_dmg, is_multi_damage=True, multiplier=2, name="Twin Slam"))
            self._skip_next_roll = True
        elif move.move_id == MOVE_TWIN_SLAM:
            damage = self.get_intent_damage()
            for _ in range(2):
                player.take_damage(damage)
            self.powers = [p for p in self.powers if p.id != "Sharp Hide"]
            self.change_to_offensive_mode()
            self.set_move(MonsterMove(MOVE_WHIRLWIND, MonsterIntent.ATTACK, base_damage=self.whirlwind_dmg, is_multi_damage=True, multiplier=self.whirlwind_count, name="Whirlwind"))
            self._skip_next_roll = True

    def change_to_defensive_mode(self) -> None:
        self.is_open = False
        self.dmg_threshold += self.dmg_threshold_increase
        self.dmg_taken = 0
        self.close_up_triggered = True

    def change_to_offensive_mode(self) -> None:
        self.is_open = True
        self.dmg_taken = 0
        self.close_up_triggered = False

    def take_damage(self, amount: int) -> int:
        actual = super().take_damage(amount)
        if self.is_open and not self.close_up_triggered and actual > 0:
            self.dmg_taken += actual
            if self.dmg_taken >= self.dmg_threshold:
                self.change_to_defensive_mode()
                self.set_move(MonsterMove(5, MonsterIntent.BUFF, name="Defensive Mode"))
        return actual


@dataclass
class Champ(MonsterBase):
    """Act 2 boss with a two-phase move script close to Java Champ."""
    slash_dmg: int = 16
    execute_dmg: int = 10
    slap_dmg: int = 12
    str_amt: int = 2
    forge_amt: int = 5
    block_amt: int = 15
    num_turns: int = 0
    forge_times: int = 0
    forge_threshold: int = 2
    threshold_reached: bool = False
    phase: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Champ":
        if ascension >= 9:
            hp = 440
        else:
            hp = 420

        if ascension >= 19:
            slash_dmg = 18
            execute_dmg = 10
            slap_dmg = 14
            str_amt = 4
            forge_amt = 7
            block_amt = 20
        elif ascension >= 9:
            slash_dmg = 18
            execute_dmg = 10
            slap_dmg = 14
            str_amt = 3
            forge_amt = 6
            block_amt = 18
        elif ascension >= 4:
            slash_dmg = 18
            execute_dmg = 10
            slap_dmg = 14
            str_amt = 3
            forge_amt = 5
            block_amt = 15
        else:
            slash_dmg = 16
            execute_dmg = 10
            slap_dmg = 12
            str_amt = 2
            forge_amt = 5
            block_amt = 15

        return cls(
            id="Champ",
            name="Champ",
            hp=hp,
            max_hp=hp,
            slash_dmg=slash_dmg,
            execute_dmg=execute_dmg,
            slap_dmg=slap_dmg,
            str_amt=str_amt,
            forge_amt=forge_amt,
            block_amt=block_amt,
        )

    def get_move(self, roll: int) -> None:
        move_heavy_slash = 1
        move_defensive_stance = 2
        move_execute = 3
        move_face_slap = 4
        move_gloat = 5
        move_taunt = 6
        move_anger = 7

        self.num_turns += 1
        if self.hp <= self.max_hp // 2 and not self.threshold_reached:
            self.threshold_reached = True
            self.phase = 1
            self.set_move(MonsterMove(move_anger, MonsterIntent.BUFF, name="Anger"))
            return

        if self.threshold_reached and not self.last_move(move_execute) and not self.last_move_before(move_execute):
            self.set_move(
                MonsterMove(
                    move_execute,
                    MonsterIntent.ATTACK,
                    self.execute_dmg,
                    multiplier=2,
                    is_multi_damage=True,
                    name="Execute",
                )
            )
            return

        if self.num_turns == 4 and not self.threshold_reached:
            self.num_turns = 0
            self.set_move(MonsterMove(move_taunt, MonsterIntent.DEBUFF, name="Taunt"))
            return

        defensive_roll = 30 if self.max_hp >= 440 else 15
        if not self.last_move(move_defensive_stance) and self.forge_times < self.forge_threshold and roll <= defensive_roll:
            self.forge_times += 1
            self.set_move(MonsterMove(move_defensive_stance, MonsterIntent.DEFEND_BUFF, name="Defensive Stance"))
            return

        if not self.last_move(move_gloat) and not self.last_move(move_defensive_stance) and roll <= 30:
            self.set_move(MonsterMove(move_gloat, MonsterIntent.BUFF, name="Gloat"))
            return

        if not self.last_move(move_face_slap) and roll <= 55:
            self.set_move(MonsterMove(move_face_slap, MonsterIntent.ATTACK_DEBUFF, self.slap_dmg, name="Face Slap"))
            return

        if not self.last_move(move_heavy_slash):
            self.set_move(MonsterMove(move_heavy_slash, MonsterIntent.ATTACK, self.slash_dmg, name="Heavy Slash"))
        else:
            self.set_move(MonsterMove(move_face_slap, MonsterIntent.ATTACK_DEBUFF, self.slap_dmg, name="Face Slap"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return

        move = self.next_move
        damage = max(0, self.get_intent_damage())
        move_id = int(move.move_id)

        if move_id == 1:
            if damage > 0:
                player.take_damage(damage)
            return

        if move_id == 2:
            self.gain_block(self.block_amt)
            self.add_power(create_power("Metallicize", self.forge_amt, self.id))
            return

        if move_id == 3:
            if damage > 0:
                player.take_damage(damage)
                player.take_damage(damage)
            return

        if move_id == 4:
            if damage > 0:
                player.take_damage(damage)
            player.add_power(create_power("Frail", 2, "player", is_source_monster=True))
            player.add_power(create_power("Vulnerable", 2, "player", is_source_monster=True))
            return

        if move_id == 5:
            self.add_power(create_power("Strength", self.str_amt, self.id))
            return

        if move_id == 6:
            player.add_power(create_power("Weak", 2, "player", is_source_monster=True))
            player.add_power(create_power("Vulnerable", 2, "player", is_source_monster=True))
            return

        if move_id == 7:
            for power_id in ("Weak", "Vulnerable", "Frail", "Shackled"):
                self.remove_power(power_id)
            self.add_power(create_power("Strength", self.str_amt * 3, self.id))


@dataclass
class Collector(MonsterBase):
    """ACT 2 Boss - Summons minions and debuffs."""
    attack_dmg: int = 11
    debuff_dmg: int = 6
    summon_count: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Collector":
        if ascension >= 19:
            hp = 280
        elif ascension >= 9:
            hp = 270
        else:
            hp = 260

        return cls(
            id="Collector",
            name="Collector",
            hp=hp,
            max_hp=hp,
        )

    def get_move(self, roll: int) -> None:
        MOVE_ATTACK = 1
        MOVE_DEBUFF = 2
        MOVE_SUMMON = 3

        if self.summon_count < 2 and roll < 40:
            self.summon_count += 1
            self.set_move(MonsterMove(MOVE_SUMMON, MonsterIntent.UNKNOWN, name="Summon"))
        elif roll < 70:
            self.set_move(MonsterMove(MOVE_ATTACK, MonsterIntent.ATTACK, self.attack_dmg, name="Strike"))
        else:
            self.set_move(MonsterMove(MOVE_DEBUFF, MonsterIntent.DEBUFF, name="Debuff"))


@dataclass
class TorchHead(MonsterBase):
    """Collector summon used by replay floor fixtures."""
    attack_dmg: int = 7

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "TorchHead":
        if ascension >= 19:
            hp = 45
            attack_dmg = 8
        elif ascension >= 9:
            hp = 42
            attack_dmg = 7
        else:
            hp = 40
            attack_dmg = 7

        return cls(
            id="TorchHead",
            name="Torch Head",
            hp=hp,
            max_hp=hp,
            attack_dmg=attack_dmg,
        )

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, self.attack_dmg, name="Tackle"))


@dataclass
class Automaton(MonsterBase):
    """ACT 2 Boss - Orb mechanics and mode shifting."""
    beam_dmg: int = 12
    bolt_dmg: int = 8
    buff_dmg: int = 6

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Automaton":
        if ascension >= 19:
            hp = 360
        elif ascension >= 9:
            hp = 340
        else:
            hp = 320

        return cls(
            id="Automaton",
            name="Automaton",
            hp=hp,
            max_hp=hp,
        )

    def get_move(self, roll: int) -> None:
        MOVE_BEAM = 1
        MOVE_BOLT = 2
        MOVE_BUFF = 3

        if roll < 50:
            self.set_move(MonsterMove(MOVE_BEAM, MonsterIntent.ATTACK, self.beam_dmg, name="Beam"))
        elif roll < 80:
            self.set_move(MonsterMove(MOVE_BOLT, MonsterIntent.ATTACK, self.bolt_dmg, name="Bolt"))
        else:
            self.set_move(MonsterMove(MOVE_BUFF, MonsterIntent.BUFF, name="Buff"))


@dataclass
class BronzeOrb(MonsterBase):
    """Bronze Automaton summon used by replay floor fixtures."""
    beam_dmg: int = 8
    block_amt: int = 12

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "BronzeOrb":
        hp = 58 if ascension >= 9 else 54
        beam_dmg = 9 if ascension >= 4 else 8
        return cls(
            id="BronzeOrb",
            name="Bronze Orb",
            hp=hp,
            max_hp=hp,
            beam_dmg=beam_dmg,
            block_amt=12,
        )

    def get_move(self, roll: int) -> None:
        if self.last_move(1):
            self.set_move(MonsterMove(3, MonsterIntent.STRONG_DEBUFF, name="Stasis"))
        else:
            self.set_move(MonsterMove(1, MonsterIntent.ATTACK, self.beam_dmg, name="Beam"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move_id = int(getattr(self.next_move, "move_id", 0) or 0)
        damage = max(0, int(self.get_intent_damage() or 0))
        if move_id == 1 and damage > 0:
            player.take_damage(damage)
            return
        if move_id == 3:
            self.gain_block(self.block_amt)


@dataclass
class AwakenedOne(MonsterBase):
    """ACT 3 Boss - Grows stronger with each kill, gains weak."""
    hit1_dmg: int = 22
    hit2_dmg: int = 18
    reflect_dmg: int = 6
    stack_gained: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "AwakenedOne":
        if ascension >= 19:
            hp = 400
        elif ascension >= 9:
            hp = 380
        else:
            hp = 360

        return cls(
            id="AwakenedOne",
            name="Awakened One",
            hp=hp,
            max_hp=hp,
        )

    def get_move(self, roll: int) -> None:
        MOVE_HIT1 = 1
        MOVE_HIT2 = 2
        MOVE_DEBUFF = 3

        if roll < 45:
            self.set_move(MonsterMove(MOVE_HIT1, MonsterIntent.ATTACK, self.hit1_dmg + self.stack_gained * 2, name="Hit"))
        elif roll < 80:
            self.set_move(MonsterMove(MOVE_HIT2, MonsterIntent.ATTACK, self.hit2_dmg + self.stack_gained * 2, name="Double Hit"))
        else:
            self.set_move(MonsterMove(MOVE_DEBUFF, MonsterIntent.WEAK, name="Weaken"))


@dataclass
class TimeEater(MonsterBase):
    """ACT 3 Boss - Speeds up and slows down, gains strength when slowed."""
    hit_dmg: int = 30
    debuff_dmg: int = 12
    haste_turns: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "TimeEater":
        if ascension >= 19:
            hp = 380
        elif ascension >= 9:
            hp = 360
        else:
            hp = 340

        return cls(
            id="TimeEater",
            name="Time Eater",
            hp=hp,
            max_hp=hp,
        )

    def get_move(self, roll: int) -> None:
        MOVE_HIT = 1
        MOVE_DEBUFF = 2

        if self.haste_turns > 0:
            self.haste_turns -= 1
            self.set_move(MonsterMove(MOVE_HIT, MonsterIntent.ATTACK, self.hit_dmg, name="Quick Hit"))
        else:
            if roll < 60:
                self.set_move(MonsterMove(MOVE_HIT, MonsterIntent.ATTACK, self.hit_dmg, name="Hit"))
            else:
                self.haste_turns = 2
                self.set_move(MonsterMove(MOVE_DEBUFF, MonsterIntent.DEBUFF, name="Slow"))


@dataclass
class DonuAndDeca(MonsterBase):
    """ACT 3 Boss - Two enemies that buff each other."""
    donu_hit_dmg: int = 18
    deca_hit_dmg: int = 16
    buff_amount: int = 2
    turn_count: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "DonuAndDeca":
        if ascension >= 19:
            hp = 320
        elif ascension >= 9:
            hp = 300
        else:
            hp = 280

        return cls(
            id="DonuAndDeca",
            name="Donu and Deca",
            hp=hp,
            max_hp=hp,
        )

    def get_move(self, roll: int) -> None:
        MOVE_DONU_HIT = 1
        MOVE_DECA_HIT = 2
        MOVE_BUFF = 3

        self.turn_count += 1
        if self.turn_count % 3 == 0:
            self.set_move(MonsterMove(MOVE_BUFF, MonsterIntent.BUFF, name="Buff"))
        elif roll < 50:
            self.set_move(MonsterMove(MOVE_DONU_HIT, MonsterIntent.ATTACK, self.donu_hit_dmg, name="Donu Hit"))
        else:
            self.set_move(MonsterMove(MOVE_DECA_HIT, MonsterIntent.ATTACK, self.deca_hit_dmg, name="Deca Hit"))


@dataclass
class Deca(MonsterBase):
    beam_dmg: int = 10
    dazed_amount: int = 2
    is_attacking: bool = True
    plated_armor_amount: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Deca":
        from sts_py.engine.combat.powers import ArtifactPower

        hp = 265 if ascension >= 9 else 250
        instance = cls(
            id="Deca",
            name="Deca",
            hp=hp,
            max_hp=hp,
            beam_dmg=12 if ascension >= 4 else 10,
            dazed_amount=2,
            is_attacking=True,
            plated_armor_amount=3 if ascension >= 19 else 0,
        )
        instance.add_power(ArtifactPower(amount=3 if ascension >= 19 else 2, owner=instance.id))
        return instance

    def get_move(self, roll: int) -> None:
        if self.is_attacking:
            self.set_move(
                MonsterMove(
                    0,
                    MonsterIntent.ATTACK_DEBUFF,
                    self.beam_dmg,
                    multiplier=2,
                    is_multi_damage=True,
                    name="Beam",
                )
            )
        else:
            intent = MonsterIntent.DEFEND_BUFF if self.plated_armor_amount > 0 else MonsterIntent.DEFEND
            self.set_move(MonsterMove(2, intent, name="Square of Protection"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        combat_state = getattr(self, "_combat_state", None)
        if combat_state is None:
            combat_state = getattr(self, "state", None)
        if self.next_move.move_id == 0:
            damage = self.get_intent_damage()
            if damage > 0:
                player.take_damage(damage)
                player.take_damage(damage)
            if combat_state is not None and getattr(combat_state, "card_manager", None) is not None:
                from sts_py.engine.content.card_instance import CardInstance

                for _ in range(max(0, int(self.dazed_amount))):
                    combat_state.card_manager.discard_pile.add(CardInstance(card_id="Dazed"))
            self.is_attacking = False
            return

        for monster in getattr(combat_state, "monsters", []) or []:
            if monster.is_dead():
                continue
            monster.gain_block(16)
            if self.plated_armor_amount > 0:
                monster.add_power(create_power("PlatedArmor", self.plated_armor_amount, monster.id))
        self.is_attacking = True


@dataclass
class Donu(MonsterBase):
    beam_dmg: int = 10
    buff_amount: int = 3
    is_attacking: bool = False

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Donu":
        from sts_py.engine.combat.powers import ArtifactPower

        hp = 265 if ascension >= 9 else 250
        instance = cls(
            id="Donu",
            name="Donu",
            hp=hp,
            max_hp=hp,
            beam_dmg=12 if ascension >= 4 else 10,
            buff_amount=3,
            is_attacking=False,
        )
        instance.add_power(ArtifactPower(amount=3 if ascension >= 19 else 2, owner=instance.id))
        return instance

    def get_move(self, roll: int) -> None:
        if self.is_attacking:
            self.set_move(
                MonsterMove(
                    0,
                    MonsterIntent.ATTACK,
                    self.beam_dmg,
                    multiplier=2,
                    is_multi_damage=True,
                    name="Beam",
                )
            )
        else:
            self.set_move(MonsterMove(2, MonsterIntent.BUFF, name="Circle of Power"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        combat_state = getattr(self, "_combat_state", None)
        if combat_state is None:
            combat_state = getattr(self, "state", None)
        if self.next_move.move_id == 0:
            damage = self.get_intent_damage()
            if damage > 0:
                player.take_damage(damage)
                player.take_damage(damage)
            self.is_attacking = False
            return

        for monster in getattr(combat_state, "monsters", []) or []:
            if monster.is_dead():
                continue
            monster.gain_strength(self.buff_amount)
        self.is_attacking = True


BOSS_MONSTERS = {
    "Hexaghost": Hexaghost,
    "Slime Boss": SlimeBoss,
    "The Guardian": TheGuardian,
    "Champ": Champ,
    "Collector": Collector,
    "Automaton": Automaton,
    "Bronze Orb": BronzeOrb,
    "Awakened One": AwakenedOne,
    "Time Eater": TimeEater,
    "Deca": Deca,
    "Donu": Donu,
    "Donu and Deca": DonuAndDeca,
}
