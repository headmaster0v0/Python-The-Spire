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
            self.remove_power("Sharp Hide")
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

        defensive_roll = 30 if self.str_amt >= 4 else 15
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
    rake_dmg: int = 18
    str_amt: int = 3
    block_amt: int = 15
    mega_debuff_amt: int = 3
    turns_taken: int = 0
    ult_used: bool = False
    initial_spawn: bool = True
    ascension_level: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Collector":
        hp = 300 if ascension >= 9 else 282
        if ascension >= 19:
            rake_dmg = 21
            str_amt = 5
            mega_debuff_amt = 5
        elif ascension >= 4:
            rake_dmg = 21
            str_amt = 4
            mega_debuff_amt = 3
        else:
            rake_dmg = 18
            str_amt = 3
            mega_debuff_amt = 3
        block_amt = 18 if ascension >= 9 else 15
        return cls(
            id="Collector",
            name="Collector",
            hp=hp,
            max_hp=hp,
            rake_dmg=rake_dmg,
            str_amt=str_amt,
            block_amt=block_amt,
            mega_debuff_amt=mega_debuff_amt,
            ascension_level=ascension,
        )

    def _dead_torch_heads(self) -> list[MonsterBase]:
        state = getattr(self, "state", None)
        return [
            monster
            for monster in getattr(state, "monsters", []) or []
            if getattr(monster, "id", "") == "TorchHead" and monster.is_dead()
        ]

    def get_move(self, roll: int) -> None:
        if self.initial_spawn:
            self.set_move(MonsterMove(1, MonsterIntent.UNKNOWN, name="Summon"))
            return
        if self.turns_taken >= 3 and not self.ult_used:
            self.set_move(MonsterMove(4, MonsterIntent.STRONG_DEBUFF, name="Mega Debuff"))
            return
        if roll <= 25 and self._dead_torch_heads() and not self.last_move(5):
            self.set_move(MonsterMove(5, MonsterIntent.UNKNOWN, name="Revive"))
            return
        if roll <= 70 and not self.last_two_moves(2):
            self.set_move(MonsterMove(2, MonsterIntent.ATTACK, self.rake_dmg, name="Fireball"))
            return
        if not self.last_move(3):
            self.set_move(MonsterMove(3, MonsterIntent.DEFEND_BUFF, name="Buff"))
            return
        self.set_move(MonsterMove(2, MonsterIntent.ATTACK, self.rake_dmg, name="Fireball"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        state = getattr(self, "state", None)
        move_id = int(getattr(self.next_move, "move_id", -1) or -1)
        if move_id == 1 and state is not None:
            for _ in range(2):
                state.add_monster(TorchHead.create(getattr(state, "rng", MutableRNG.from_seed(1, rng_type="monsterHpRng")), self.ascension_level))
            self.initial_spawn = False
        elif move_id == 2:
            damage = self.get_intent_damage()
            if damage > 0:
                player.take_damage(damage)
        elif move_id == 3:
            self.gain_block(self.block_amt + (5 if self.ascension_level >= 19 else 0))
            for monster in getattr(state, "monsters", []) or []:
                if not monster.is_dead():
                    monster.gain_strength(self.str_amt)
        elif move_id == 4:
            self.ult_used = True
            player.add_power(create_power("Weak", self.mega_debuff_amt, player.id, is_source_monster=True))
            player.add_power(create_power("Vulnerable", self.mega_debuff_amt, player.id, is_source_monster=True))
            player.add_power(create_power("Frail", self.mega_debuff_amt, player.id, is_source_monster=True))
        elif move_id == 5 and state is not None:
            for _ in self._dead_torch_heads():
                state.add_monster(TorchHead.create(getattr(state, "rng", MutableRNG.from_seed(1, rng_type="monsterHpRng")), self.ascension_level))
        self.turns_taken += 1


@dataclass
class TorchHead(MonsterBase):
    attack_dmg: int = 7

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "TorchHead":
        hp = hp_rng.random_int_between(40, 45) if ascension >= 9 else hp_rng.random_int_between(38, 40)
        return cls(
            id="TorchHead",
            name="Torch Head",
            hp=hp,
            max_hp=hp,
            attack_dmg=7,
        )

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, self.attack_dmg, name="Tackle"))


@dataclass
class Automaton(MonsterBase):
    flail_dmg: int = 7
    hyper_beam_dmg: int = 45
    str_amt: int = 3
    block_amt: int = 9
    num_turns: int = 0
    first_turn: bool = True
    ascension_level: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Automaton":
        hp = 320 if ascension >= 9 else 300
        return cls(
            id="Automaton",
            name="Automaton",
            hp=hp,
            max_hp=hp,
            flail_dmg=8 if ascension >= 4 else 7,
            hyper_beam_dmg=50 if ascension >= 4 else 45,
            str_amt=4 if ascension >= 4 else 3,
            block_amt=12 if ascension >= 9 else 9,
            ascension_level=ascension,
        )

    def use_pre_battle_action(self) -> None:
        self.add_power(create_power("Artifact", 3, self.id))

    def get_move(self, roll: int) -> None:
        if self.first_turn:
            self.first_turn = False
            self.set_move(MonsterMove(4, MonsterIntent.UNKNOWN, name="Spawn Orbs"))
            return
        if self.num_turns == 4:
            self.num_turns = 0
            self.set_move(MonsterMove(2, MonsterIntent.ATTACK, self.hyper_beam_dmg, name="Hyper Beam"))
            return
        if self.last_move(2):
            if self.ascension_level >= 19:
                self.set_move(MonsterMove(5, MonsterIntent.DEFEND_BUFF, name="Boost"))
            else:
                self.set_move(MonsterMove(3, MonsterIntent.STUN, name="Stunned"))
            return
        if self.last_move(3) or self.last_move(5) or self.last_move(4):
            self.set_move(MonsterMove(1, MonsterIntent.ATTACK, self.flail_dmg, multiplier=2, is_multi_damage=True, name="Flail"))
        else:
            self.set_move(MonsterMove(5, MonsterIntent.DEFEND_BUFF, name="Boost"))
        self.num_turns += 1

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        state = getattr(self, "state", None)
        move_id = int(getattr(self.next_move, "move_id", -1) or -1)
        if move_id == 4 and state is not None:
            state.add_monster(BronzeOrb.create(getattr(state, "rng", MutableRNG.from_seed(1, rng_type="monsterHpRng")), self.ascension_level, count=0))
            state.add_monster(BronzeOrb.create(getattr(state, "rng", MutableRNG.from_seed(1, rng_type="monsterHpRng")), self.ascension_level, count=1))
            return
        if move_id == 1:
            damage = self.get_intent_damage()
            if damage > 0:
                player.take_damage(damage)
                player.take_damage(damage)
            return
        if move_id == 5:
            self.gain_block(self.block_amt)
            self.gain_strength(self.str_amt)
            return
        if move_id == 2:
            damage = self.get_intent_damage()
            if damage > 0:
                player.take_damage(damage)


@dataclass
class BronzeOrb(MonsterBase):
    beam_dmg: int = 8
    block_amt: int = 12
    used_stasis: bool = False
    count: int = 0
    stasis_card: object | None = None

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0, count: int = 0) -> "BronzeOrb":
        hp = hp_rng.random_int_between(54, 60) if ascension >= 9 else hp_rng.random_int_between(52, 58)
        return cls(id="BronzeOrb", name="Bronze Orb", hp=hp, max_hp=hp, beam_dmg=8, block_amt=12, count=count)

    def get_move(self, roll: int) -> None:
        if not self.used_stasis and roll >= 25:
            self.used_stasis = True
            self.set_move(MonsterMove(3, MonsterIntent.STRONG_DEBUFF, name="Stasis"))
            return
        if roll >= 70 and not self.last_two_moves(2):
            self.set_move(MonsterMove(2, MonsterIntent.DEFEND, name="Support Beam"))
            return
        if not self.last_two_moves(1):
            self.set_move(MonsterMove(1, MonsterIntent.ATTACK, self.beam_dmg, name="Beam"))
            return
        self.set_move(MonsterMove(2, MonsterIntent.DEFEND, name="Support Beam"))

    def _select_stasis_card(self):
        from sts_py.engine.content.card_instance import get_runtime_card_base_id
        from sts_py.engine.content.cards_min import ALL_CARD_DEFS

        state = getattr(self, "state", None)
        card_manager = getattr(state, "card_manager", None)
        if card_manager is None:
            return None
        source_pile = card_manager.draw_pile if not card_manager.draw_pile.is_empty() else card_manager.discard_pile
        if source_pile.is_empty():
            return None
        rarity_priority = {"RARE": 3, "UNCOMMON": 2, "COMMON": 1}
        top_score = -1
        candidates: list[object] = []
        for card in list(source_pile.cards):
            base_id = get_runtime_card_base_id(getattr(card, "card_id", ""))
            card_def = ALL_CARD_DEFS.get(base_id)
            rarity_name = str(getattr(getattr(card_def, "rarity", None), "name", "") or "")
            score = rarity_priority.get(rarity_name, 0)
            if score > top_score:
                top_score = score
                candidates = [card]
            elif score == top_score:
                candidates.append(card)
        rng = getattr(state, "card_random_rng", None) or getattr(state, "rng", None)
        selected = candidates[0] if rng is None or len(candidates) == 1 else candidates[rng.random_int(len(candidates) - 1)]
        source_pile.remove(selected)
        return selected

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        state = getattr(self, "state", None)
        move_id = int(getattr(self.next_move, "move_id", 0) or 0)
        damage = max(0, int(self.get_intent_damage() or 0))
        if move_id == 1 and damage > 0:
            player.take_damage(damage)
            return
        if move_id == 2 and state is not None:
            for monster in getattr(state, "monsters", []) or []:
                if getattr(monster, "id", "") == "Automaton" and not monster.is_dead():
                    monster.gain_block(self.block_amt)
                    break
            return
        if move_id == 3:
            self.stasis_card = self._select_stasis_card()

    def on_death(self) -> None:
        state = getattr(self, "state", None)
        card_manager = getattr(state, "card_manager", None)
        if card_manager is None or self.stasis_card is None:
            return
        if card_manager.hand.size() < 10:
            card_manager.hand.add(self.stasis_card)
        else:
            card_manager.discard_pile.add(self.stasis_card)
        self.stasis_card = None


@dataclass
class AwakenedOne(MonsterBase):
    slash_dmg: int = 20
    soul_strike_dmg: int = 6
    dark_echo_dmg: int = 40
    sludge_dmg: int = 18
    tackle_dmg: int = 10
    form1: bool = True
    first_turn: bool = True
    half_dead: bool = False
    regen_amt: int = 10
    curiosity_amt: int = 1
    ascension_level: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "AwakenedOne":
        hp = 320 if ascension >= 9 else 300
        return cls(
            id="AwakenedOne",
            name="Awakened One",
            hp=hp,
            max_hp=hp,
            regen_amt=15 if ascension >= 19 else 10,
            curiosity_amt=2 if ascension >= 19 else 1,
            ascension_level=ascension,
        )

    def use_pre_battle_action(self) -> None:
        if self.ascension_level >= 4:
            self.gain_strength(2)

    def on_player_power_played(self, card=None) -> None:
        if self.form1 and not self.half_dead and not self.is_dead():
            self.gain_strength(self.curiosity_amt)

    def on_end_of_round(self) -> None:
        if not self.half_dead and not self.is_dead():
            self.hp = min(self.max_hp, self.hp + self.regen_amt)

    def get_move(self, roll: int) -> None:
        if self.half_dead:
            self.set_move(MonsterMove(3, MonsterIntent.UNKNOWN, name="Rebirth"))
            return
        if self.form1:
            if self.first_turn:
                self.first_turn = False
                self.set_move(MonsterMove(1, MonsterIntent.ATTACK, self.slash_dmg, name="Slash"))
                return
            if roll < 25:
                if not self.last_move(2):
                    self.set_move(MonsterMove(2, MonsterIntent.ATTACK, self.soul_strike_dmg, multiplier=4, is_multi_damage=True, name="Soul Strike"))
                else:
                    self.set_move(MonsterMove(1, MonsterIntent.ATTACK, self.slash_dmg, name="Slash"))
                return
            if not self.last_two_moves(1):
                self.set_move(MonsterMove(1, MonsterIntent.ATTACK, self.slash_dmg, name="Slash"))
            else:
                self.set_move(MonsterMove(2, MonsterIntent.ATTACK, self.soul_strike_dmg, multiplier=4, is_multi_damage=True, name="Soul Strike"))
            return
        if self.first_turn:
            self.set_move(MonsterMove(5, MonsterIntent.ATTACK, self.dark_echo_dmg, name="Dark Echo"))
            return
        if roll < 50:
            if not self.last_two_moves(6):
                self.set_move(MonsterMove(6, MonsterIntent.ATTACK_DEBUFF, self.sludge_dmg, name="Sludge"))
            else:
                self.set_move(MonsterMove(8, MonsterIntent.ATTACK, self.tackle_dmg, multiplier=3, is_multi_damage=True, name="Tackle"))
            return
        if not self.last_two_moves(8):
            self.set_move(MonsterMove(8, MonsterIntent.ATTACK, self.tackle_dmg, multiplier=3, is_multi_damage=True, name="Tackle"))
            return
        self.set_move(MonsterMove(6, MonsterIntent.ATTACK_DEBUFF, self.sludge_dmg, name="Sludge"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        state = getattr(self, "state", None)
        move_id = int(getattr(self.next_move, "move_id", -1) or -1)
        if move_id == 1:
            damage = self.get_intent_damage()
            if damage > 0:
                player.take_damage(damage)
            return
        if move_id == 2:
            damage = self.get_intent_damage()
            if damage > 0:
                for _ in range(4):
                    player.take_damage(damage)
            return
        if move_id == 3:
            from sts_py.engine.combat.powers import PowerType

            self.half_dead = False
            self.form1 = False
            self.hp = self.max_hp
            self.powers.powers = [
                power
                for power in self.powers.powers
                if getattr(power, "power_type", None) != PowerType.DEBUFF and getattr(power, "id", "") != "Shackled"
            ]
            return
        if move_id == 5:
            self.first_turn = False
            damage = self.get_intent_damage()
            if damage > 0:
                player.take_damage(damage)
            return
        if move_id == 6:
            damage = self.get_intent_damage()
            if damage > 0:
                player.take_damage(damage)
            if state is not None and getattr(state, "card_manager", None) is not None:
                from sts_py.engine.content.card_instance import CardInstance

                state.card_manager.draw_pile.add(CardInstance(card_id="Void"))
            return
        if move_id == 8:
            damage = self.get_intent_damage()
            if damage > 0:
                for _ in range(3):
                    player.take_damage(damage)

    def take_damage(self, amount: int) -> int:
        actual = super().take_damage(amount)
        if self.form1 and self.hp <= 0 and not self.half_dead:
            self.form1 = False
            self.half_dead = True
            self.is_dying = False
            self.hp = 1
            self.first_turn = True
            self.set_move(MonsterMove(3, MonsterIntent.UNKNOWN, name="Rebirth"))
        return actual


@dataclass
class TimeEater(MonsterBase):
    reverb_dmg: int = 7
    head_slam_dmg: int = 26
    used_haste: bool = False
    first_turn: bool = True
    ascension_level: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "TimeEater":
        hp = 480 if ascension >= 9 else 456
        return cls(
            id="TimeEater",
            name="Time Eater",
            hp=hp,
            max_hp=hp,
            reverb_dmg=8 if ascension >= 4 else 7,
            head_slam_dmg=32 if ascension >= 4 else 26,
            ascension_level=ascension,
        )

    def use_pre_battle_action(self) -> None:
        state = getattr(self, "state", None)
        player = getattr(state, "player", None)
        if player is not None:
            player._cards_play_limit = max(int(getattr(player, "_cards_play_limit", 0) or 0), 12)

    def get_move(self, roll: int) -> None:
        if self.hp < self.max_hp // 2 and not self.used_haste:
            self.used_haste = True
            self.set_move(MonsterMove(5, MonsterIntent.BUFF, name="Haste"))
            return
        if roll < 45:
            if not self.last_two_moves(2):
                self.set_move(MonsterMove(2, MonsterIntent.ATTACK, self.reverb_dmg, multiplier=3, is_multi_damage=True, name="Reverberate"))
                return
            self.get_move(50)
            return
        if roll < 80:
            if not self.last_move(4):
                self.set_move(MonsterMove(4, MonsterIntent.ATTACK_DEBUFF, self.head_slam_dmg, name="Head Slam"))
                return
            ai_rng = getattr(self, "ai_rng", None)
            if ai_rng is not None and ai_rng.random_int(99) < 66:
                self.set_move(MonsterMove(2, MonsterIntent.ATTACK, self.reverb_dmg, multiplier=3, is_multi_damage=True, name="Reverberate"))
            else:
                self.set_move(MonsterMove(3, MonsterIntent.DEFEND_DEBUFF, name="Ripple"))
            return
        if not self.last_move(3):
            self.set_move(MonsterMove(3, MonsterIntent.DEFEND_DEBUFF, name="Ripple"))
            return
        self.get_move(0)

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        state = getattr(self, "state", None)
        move_id = int(getattr(self.next_move, "move_id", -1) or -1)
        if move_id == 2:
            damage = self.get_intent_damage()
            if damage > 0:
                for _ in range(3):
                    player.take_damage(damage)
            return
        if move_id == 3:
            self.gain_block(20)
            player.add_power(create_power("Vulnerable", 1, player.id, is_source_monster=True))
            player.add_power(create_power("Weak", 1, player.id, is_source_monster=True))
            if self.ascension_level >= 19:
                player.add_power(create_power("Frail", 1, player.id, is_source_monster=True))
            return
        if move_id == 4:
            damage = self.get_intent_damage()
            if damage > 0:
                player.take_damage(damage)
            player._draw_reduction_next_turn = max(int(getattr(player, "_draw_reduction_next_turn", 0) or 0), 1)
            if self.ascension_level >= 19 and state is not None and getattr(state, "card_manager", None) is not None:
                from sts_py.engine.content.card_instance import CardInstance

                state.card_manager.discard_pile.add(CardInstance(card_id="Slimed"))
                state.card_manager.discard_pile.add(CardInstance(card_id="Slimed"))
            return
        if move_id == 5:
            self.remove_power("Weak")
            self.remove_power("Vulnerable")
            self.remove_power("Frail")
            self.remove_power("Shackled")
            self.hp = max(self.hp, self.max_hp // 2)
            if self.ascension_level >= 19:
                self.gain_block(self.head_slam_dmg)


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
