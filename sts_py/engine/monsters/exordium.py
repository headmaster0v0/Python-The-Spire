from __future__ import annotations

from dataclasses import dataclass

from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.combat.powers import CurlUpPower, RitualPower, StrengthPower, VulnerablePower, AngerPower, create_power


@dataclass
class JawWorm(MonsterBase):
    chomp_dmg: int = 11
    thrash_dmg: int = 7
    thrash_block: int = 5
    bellow_str: int = 3
    bellow_block: int = 6

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "JawWorm":
        if ascension >= 7:
            hp = hp_rng.random_int_between(42, 46)
        else:
            hp = hp_rng.random_int_between(40, 44)

        if ascension >= 17:
            bellow_str = 5
            bellow_block = 9
            chomp_dmg = 12
            thrash_dmg = 7
            thrash_block = 5
        elif ascension >= 2:
            bellow_str = 4
            bellow_block = 6
            chomp_dmg = 12
            thrash_dmg = 7
            thrash_block = 5
        else:
            bellow_str = 3
            bellow_block = 6
            chomp_dmg = 11
            thrash_dmg = 7
            thrash_block = 5

        return cls(
            id="JawWorm",
            name="Jaw Worm",
            hp=hp,
            max_hp=hp,
            chomp_dmg=chomp_dmg,
            thrash_dmg=thrash_dmg,
            thrash_block=thrash_block,
            bellow_str=bellow_str,
            bellow_block=bellow_block,
        )

    def get_move(self, roll: int) -> None:
        MOVE_CHOMP = 1
        MOVE_BELLOW = 2
        MOVE_THRASH = 3

        if self.first_move:
            self.first_move = False
            self.set_move(MonsterMove(MOVE_CHOMP, MonsterIntent.ATTACK, self.chomp_dmg))
            return

        if roll < 25:
            if self.last_move(MOVE_CHOMP):
                bellow_chance = 0.5625
                if self.ai_rng.random_float() < bellow_chance:
                    self.set_move(MonsterMove(MOVE_BELLOW, MonsterIntent.DEFEND_BUFF, name="Bellow"))
                else:
                    self.set_move(MonsterMove(MOVE_THRASH, MonsterIntent.ATTACK_DEFEND, self.thrash_dmg))
            else:
                self.set_move(MonsterMove(MOVE_CHOMP, MonsterIntent.ATTACK, self.chomp_dmg))
        elif roll < 55:
            if self.last_two_moves(MOVE_THRASH):
                thrash_chance = 0.357
                if self.ai_rng.random_float() < thrash_chance:
                    self.set_move(MonsterMove(MOVE_CHOMP, MonsterIntent.ATTACK, self.chomp_dmg))
                else:
                    self.set_move(MonsterMove(MOVE_BELLOW, MonsterIntent.DEFEND_BUFF, name="Bellow"))
            else:
                self.set_move(MonsterMove(MOVE_THRASH, MonsterIntent.ATTACK_DEFEND, self.thrash_dmg))
        elif self.last_move(MOVE_BELLOW):
            bellow_chance = 0.416
            if self.ai_rng.random_float() < bellow_chance:
                self.set_move(MonsterMove(MOVE_CHOMP, MonsterIntent.ATTACK, self.chomp_dmg))
            else:
                self.set_move(MonsterMove(MOVE_THRASH, MonsterIntent.ATTACK_DEFEND, self.thrash_dmg))
        else:
            self.set_move(MonsterMove(MOVE_BELLOW, MonsterIntent.DEFEND_BUFF, name="Bellow"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.move_id == 1:  # Chomp
            damage = self.get_intent_damage()
            player.take_damage(damage)
        elif move.move_id == 2:  # Bellow
            self.gain_block(self.bellow_block)
            self.gain_strength(self.bellow_str)
        elif move.move_id == 3:  # Thrash
            damage = self.get_intent_damage()
            player.take_damage(damage)
            self.gain_block(self.thrash_block)

    def get_move_with_ai_rng(self, ai_rng: MutableRNG) -> None:
        MOVE_CHOMP = 1
        MOVE_BELLOW = 2
        MOVE_THRASH = 3

        if self.first_move:
            self.first_move = False
            self.set_move(MonsterMove(MOVE_CHOMP, MonsterIntent.ATTACK, self.chomp_dmg))
            return

        roll = ai_rng.random_int(99)

        if self.last_move(MOVE_CHOMP):
            if roll < 40:
                self.set_move(MonsterMove(MOVE_THRASH, MonsterIntent.ATTACK_DEFEND, self.thrash_dmg))
            else:
                self.set_move(MonsterMove(MOVE_BELLOW, MonsterIntent.DEFEND_BUFF, name="Bellow"))

        elif self.last_move(MOVE_BELLOW):
            if roll < 45:
                self.set_move(MonsterMove(MOVE_CHOMP, MonsterIntent.ATTACK, self.chomp_dmg))
            elif roll < 75:
                self.set_move(MonsterMove(MOVE_THRASH, MonsterIntent.ATTACK_DEFEND, self.thrash_dmg))
            else:
                self.set_move(MonsterMove(MOVE_BELLOW, MonsterIntent.DEFEND_BUFF, name="Bellow"))

        elif self.last_two_moves(MOVE_THRASH):
            if roll < 36:
                self.set_move(MonsterMove(MOVE_CHOMP, MonsterIntent.ATTACK, self.chomp_dmg))
            else:
                self.set_move(MonsterMove(MOVE_BELLOW, MonsterIntent.DEFEND_BUFF, name="Bellow"))

        else:
            if roll < 25:
                self.set_move(MonsterMove(MOVE_CHOMP, MonsterIntent.ATTACK, self.chomp_dmg))
            elif roll < 55:
                self.set_move(MonsterMove(MOVE_THRASH, MonsterIntent.ATTACK_DEFEND, self.thrash_dmg))
            else:
                self.set_move(MonsterMove(MOVE_BELLOW, MonsterIntent.DEFEND_BUFF, name="Bellow"))


@dataclass
class LouseRed(MonsterBase):
    bite_damage: int = 5
    curl_up: int = 0
    grow_str: int = 3

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "LouseRed":
        if ascension >= 7:
            hp = hp_rng.random_int_between(11, 16)
        else:
            hp = hp_rng.random_int_between(10, 15)

        if ascension >= 2:
            bite_damage = hp_rng.random_int_between(6, 8)
        else:
            bite_damage = hp_rng.random_int_between(5, 7)

        if ascension >= 17:
            curl_up = hp_rng.random_int_between(9, 12)
            grow_str = 4
        elif ascension >= 7:
            curl_up = hp_rng.random_int_between(4, 8)
            grow_str = 3
        else:
            curl_up = hp_rng.random_int_between(3, 7)
            grow_str = 3

        louse = cls(
            id="LouseRed",
            name="Red Louse",
            hp=hp,
            max_hp=hp,
            bite_damage=bite_damage,
            curl_up=curl_up,
            grow_str=grow_str,
        )
        louse.add_power(CurlUpPower(amount=curl_up, owner=louse.id))
        return louse

    def get_move(self, roll: int) -> None:
        MOVE_BITE = 3
        MOVE_GROW = 4

        if getattr(self, 'ascension_level', 0) >= 17:
            if roll < 25:
                if self.last_move(MOVE_GROW):
                    self.set_move(MonsterMove(MOVE_BITE, MonsterIntent.ATTACK, self.bite_damage))
                else:
                    self.set_move(MonsterMove(MOVE_GROW, MonsterIntent.BUFF, name="Grow"))
            elif self.last_two_moves(MOVE_BITE):
                self.set_move(MonsterMove(MOVE_GROW, MonsterIntent.BUFF, name="Grow"))
            else:
                self.set_move(MonsterMove(MOVE_BITE, MonsterIntent.ATTACK, self.bite_damage))
        else:
            if roll < 25:
                if self.last_two_moves(MOVE_GROW):
                    self.set_move(MonsterMove(MOVE_BITE, MonsterIntent.ATTACK, self.bite_damage))
                else:
                    self.set_move(MonsterMove(MOVE_GROW, MonsterIntent.BUFF, name="Grow"))
            elif self.last_two_moves(MOVE_BITE):
                self.set_move(MonsterMove(MOVE_GROW, MonsterIntent.BUFF, name="Grow"))
            else:
                self.set_move(MonsterMove(MOVE_BITE, MonsterIntent.ATTACK, self.bite_damage))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.move_id == 3:
            damage = self.get_intent_damage()
            player.take_damage(damage)
        elif move.move_id == 4:
            self.gain_strength(self.grow_str)


@dataclass
class LouseGreen(MonsterBase):
    bite_damage: int = 5
    curl_up: int = 0
    weak_amount: int = 2

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "LouseGreen":
        if ascension >= 7:
            hp = hp_rng.random_int_between(12, 18)
        else:
            hp = hp_rng.random_int_between(11, 17)

        if ascension >= 2:
            bite_damage = hp_rng.random_int_between(6, 8)
        else:
            bite_damage = hp_rng.random_int_between(5, 7)

        if ascension >= 17:
            curl_up = hp_rng.random_int_between(9, 12)
        elif ascension >= 7:
            curl_up = hp_rng.random_int_between(4, 8)
        else:
            curl_up = hp_rng.random_int_between(3, 7)

        louse = cls(
            id="LouseGreen",
            name="Green Louse",
            hp=hp,
            max_hp=hp,
            bite_damage=bite_damage,
            curl_up=curl_up,
            weak_amount=2,
        )
        louse.add_power(CurlUpPower(amount=curl_up, owner=louse.id))
        return louse

    def get_move(self, roll: int) -> None:
        MOVE_BITE = 3
        MOVE_WEAKEN = 4

        if getattr(self, 'ascension_level', 0) >= 17:
            if roll < 25:
                if self.last_move(MOVE_WEAKEN):
                    self.set_move(MonsterMove(MOVE_BITE, MonsterIntent.ATTACK, self.bite_damage))
                else:
                    self.set_move(MonsterMove(MOVE_WEAKEN, MonsterIntent.DEBUFF, name="Spit Web"))
            elif self.last_two_moves(MOVE_BITE):
                self.set_move(MonsterMove(MOVE_WEAKEN, MonsterIntent.DEBUFF, name="Spit Web"))
            else:
                self.set_move(MonsterMove(MOVE_BITE, MonsterIntent.ATTACK, self.bite_damage))
        else:
            if roll < 25:
                if self.last_two_moves(MOVE_WEAKEN):
                    self.set_move(MonsterMove(MOVE_BITE, MonsterIntent.ATTACK, self.bite_damage))
                else:
                    self.set_move(MonsterMove(MOVE_WEAKEN, MonsterIntent.DEBUFF, name="Spit Web"))
            elif self.last_two_moves(MOVE_BITE):
                self.set_move(MonsterMove(MOVE_WEAKEN, MonsterIntent.DEBUFF, name="Spit Web"))
            else:
                self.set_move(MonsterMove(MOVE_BITE, MonsterIntent.ATTACK, self.bite_damage))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.intent.is_attack():
            damage = self.get_intent_damage()
            player.take_damage(damage)
        elif move.intent.is_debuff():
            from sts_py.engine.combat.powers import WeakPower
            player.add_power(WeakPower(amount=self.weak_amount, owner=player.id))


@dataclass
class ApologySlime(MonsterBase):
    tackle_dmg: int = 3
    weak_amount: int = 1

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "ApologySlime":
        hp = hp_rng.random_int_between(8, 12)
        return cls(
            id="Apology Slime",
            name="Apology Slime",
            hp=hp,
            max_hp=hp,
            tackle_dmg=3,
            weak_amount=1,
        )

    def get_move(self, roll: int) -> None:
        MOVE_TACKLE = 1
        MOVE_DEBUFF = 2

        if self.ai_rng.random_bool():
            self.set_move(MonsterMove(MOVE_TACKLE, MonsterIntent.ATTACK, self.tackle_dmg))
        else:
            self.set_move(MonsterMove(MOVE_DEBUFF, MonsterIntent.DEBUFF, name="Apology"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.move_id == 1:
            damage = self.get_intent_damage()
            player.take_damage(damage)
            self.set_move(MonsterMove(MOVE_DEBUFF, MonsterIntent.DEBUFF, name="Apology"))
        elif move.move_id == 2:
            from sts_py.engine.combat.powers import WeakPower
            player.add_power(WeakPower(amount=self.weak_amount, owner=player.id))
            self.set_move(MonsterMove(MOVE_TACKLE, MonsterIntent.ATTACK, self.tackle_dmg))


@dataclass
class AcidSlimeSmall(MonsterBase):
    attack_dmg: int = 3

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "AcidSlimeSmall":
        if ascension >= 7:
            hp = hp_rng.random_int_between(9, 13)
        else:
            hp = hp_rng.random_int_between(8, 12)

        if ascension >= 2:
            attack_dmg = 4
        else:
            attack_dmg = 3

        slime = cls(
            id="AcidSlimeSmall",
            name="Acid Slime (S)",
            hp=hp,
            max_hp=hp,
            attack_dmg=attack_dmg,
        )
        return slime

    def get_move(self, roll: int) -> None:
        MOVE_ATTACK = 1
        MOVE_LICK = 2

        if getattr(self, 'ascension_level', 0) >= 17:
            if self.last_two_moves(MOVE_ATTACK):
                self.set_move(MonsterMove(MOVE_ATTACK, MonsterIntent.ATTACK, self.attack_dmg))
            else:
                self.set_move(MonsterMove(MOVE_LICK, MonsterIntent.DEBUFF, name="Lick"))
        else:
            if roll < 50:
                self.set_move(MonsterMove(MOVE_ATTACK, MonsterIntent.ATTACK, self.attack_dmg))
            else:
                self.set_move(MonsterMove(MOVE_LICK, MonsterIntent.DEBUFF, name="Lick"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.move_id == 1:
            damage = self.get_intent_damage()
            player.take_damage(damage)
        elif move.move_id == 2:
            from sts_py.engine.combat.powers import WeakPower
            player.add_power(WeakPower(amount=1, owner=player.id))


@dataclass
class SpikeSlimeSmall(MonsterBase):
    attack_dmg: int = 5

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "SpikeSlimeSmall":
        if ascension >= 7:
            hp = hp_rng.random_int_between(11, 15)
        else:
            hp = hp_rng.random_int_between(10, 14)

        if ascension >= 2:
            attack_dmg = 6
        else:
            attack_dmg = 5

        return cls(
            id="SpikeSlimeSmall",
            name="Spike Slime (S)",
            hp=hp,
            max_hp=hp,
            attack_dmg=attack_dmg,
        )

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, self.attack_dmg))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        if self.next_move.intent.is_attack():
            damage = self.get_intent_damage()
            player.take_damage(damage)


@dataclass
class SpikeSlimeMedium(MonsterBase):
    spit_dmg: int = 8
    frail_amount: int = 1

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "SpikeSlimeMedium":
        if ascension >= 7:
            hp = hp_rng.random_int_between(29, 34)
        else:
            hp = hp_rng.random_int_between(28, 32)

        if ascension >= 2:
            spit_dmg = 10
        else:
            spit_dmg = 8

        return cls(
            id="SpikeSlimeMedium",
            name="Spike Slime (M)",
            hp=hp,
            max_hp=hp,
            spit_dmg=spit_dmg,
            frail_amount=1,
        )

    def get_move(self, roll: int) -> None:
        MOVE_SPIT = 1
        MOVE_FRAIL = 4

        if getattr(self, 'ascension_level', 0) >= 17:
            if roll < 30:
                if self.last_two_moves(MOVE_SPIT):
                    self.set_move(MonsterMove(MOVE_FRAIL, MonsterIntent.DEBUFF, name="Lick"))
                else:
                    self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK, self.spit_dmg))
            elif self.last_move(MOVE_FRAIL):
                self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK, self.spit_dmg))
            else:
                self.set_move(MonsterMove(MOVE_FRAIL, MonsterIntent.DEBUFF, name="Lick"))
        else:
            if roll < 30:
                if self.last_two_moves(MOVE_SPIT):
                    self.set_move(MonsterMove(MOVE_FRAIL, MonsterIntent.DEBUFF, name="Lick"))
                else:
                    self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK, self.spit_dmg))
            elif self.last_two_moves(MOVE_FRAIL):
                self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK, self.spit_dmg))
            else:
                self.set_move(MonsterMove(MOVE_FRAIL, MonsterIntent.DEBUFF, name="Lick"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.move_id == 1:
            damage = self.get_intent_damage()
            player.take_damage(damage)
            from sts_py.engine.content.card_instance import CardInstance
            slimed = CardInstance(card_id="Slimed", upgraded=False)
            self.state.card_manager.discard_pile.add(slimed)
        elif move.move_id == 4:
            from sts_py.engine.combat.powers import FrailPower
            player.add_power(FrailPower(amount=self.frail_amount, owner=player.id))


@dataclass
class SpikeSlimeLarge(MonsterBase):
    spit_dmg: int = 16
    frail_amount: int = 2
    has_split: bool = True
    has_split_triggered: bool = False

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0, hp: int = None) -> "SpikeSlimeLarge":
        if hp is None:
            if ascension >= 7:
                hp = hp_rng.random_int_between(67, 73)
            else:
                hp = hp_rng.random_int_between(64, 70)

        if ascension >= 2:
            spit_dmg = 18
        else:
            spit_dmg = 16

        if ascension >= 17:
            frail_amount = 3
        else:
            frail_amount = 2

        return cls(
            id="SpikeSlimeLarge",
            name="Spike Slime (L)",
            hp=hp,
            max_hp=hp,
            spit_dmg=spit_dmg,
            frail_amount=frail_amount,
        )

    def get_move(self, roll: int) -> None:
        MOVE_SPIT = 1
        MOVE_FRAIL = 4
        MOVE_SPLIT = 3

        if self.has_split_triggered:
            self.set_move(MonsterMove(MOVE_SPLIT, MonsterIntent.UNKNOWN, name="Split"))
            return

        if getattr(self, 'ascension_level', 0) >= 17:
            if roll < 30:
                if self.last_two_moves(MOVE_SPIT):
                    self.set_move(MonsterMove(MOVE_FRAIL, MonsterIntent.DEBUFF, name="Lick"))
                else:
                    self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK, self.spit_dmg))
            elif self.last_move(MOVE_FRAIL):
                self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK, self.spit_dmg))
            else:
                self.set_move(MonsterMove(MOVE_FRAIL, MonsterIntent.DEBUFF, name="Lick"))
        else:
            if roll < 30:
                if self.last_two_moves(MOVE_SPIT):
                    self.set_move(MonsterMove(MOVE_FRAIL, MonsterIntent.DEBUFF, name="Lick"))
                else:
                    self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK, self.spit_dmg))
            elif self.last_two_moves(MOVE_FRAIL):
                self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK, self.spit_dmg))
            else:
                self.set_move(MonsterMove(MOVE_FRAIL, MonsterIntent.DEBUFF, name="Lick"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return

        move = self.next_move

        if move.move_id == 3:
            self.has_split_triggered = True
            from sts_py.engine.monsters.exordium import SpikeSlimeMedium
            split_hp = self.hp
            for _ in range(2):
                new_slime = SpikeSlimeMedium(
                    id="SpikeSlimeMedium",
                    name="Spike Slime (M)",
                    hp=split_hp,
                    max_hp=split_hp,
                    spit_dmg=self.spit_dmg,
                    frail_amount=self.frail_amount,
                )
                if hasattr(self, 'state') and self.state:
                    self.state.add_monster(new_slime)
            return

        if move.move_id == 1:
            damage = self.get_intent_damage()
            player.take_damage(damage)
            from sts_py.engine.content.card_instance import CardInstance
            for _ in range(2):
                slimed = CardInstance(card_id="Slimed", upgraded=False)
                self.state.card_manager.discard_pile.add(slimed)
        elif move.move_id == 4:
            from sts_py.engine.combat.powers import FrailPower
            player.add_power(FrailPower(amount=self.frail_amount, owner=player.id))

    def take_damage(self, amount: int) -> int:
        actual = super().take_damage(amount)
        if not self.is_dying and self.hp <= self.max_hp // 2 and self.next_move and self.next_move.move_id != 3 and not self.has_split_triggered:
            self.has_split_triggered = True
            self.set_move(MonsterMove(3, MonsterIntent.UNKNOWN, name="Split"))
        return actual


@dataclass
class GremlinFat(MonsterBase):
    smash_dmg: int = 4
    ascension_level: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "GremlinFat":
        if ascension >= 7:
            hp = hp_rng.random_int_between(14, 18)
        else:
            hp = hp_rng.random_int_between(13, 17)

        if ascension >= 2:
            smash_dmg = 5
        else:
            smash_dmg = 4

        return cls(
            id="GremlinFat",
            name="Gremlin (Fat)",
            hp=hp,
            max_hp=hp,
            smash_dmg=smash_dmg,
            ascension_level=ascension,
        )

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(2, MonsterIntent.ATTACK_DEBUFF, self.smash_dmg, name="Smash"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        if self.next_move.move_id == 2:
            damage = self.get_intent_damage()
            player.take_damage(damage)
            from sts_py.engine.combat.powers import WeakPower
            player.add_power(WeakPower(amount=1, owner=player.id))
            if getattr(self, 'ascension_level', 0) >= 17:
                from sts_py.engine.combat.powers import FrailPower
                player.add_power(FrailPower(amount=1, owner=player.id))


@dataclass
class GremlinShield(MonsterBase):
    defend_dmg: int = 7
    attack_dmg: int = 6
    solo_attack_mode: bool = False

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "GremlinShield":
        hp = hp_rng.random_int_between(12, 15)
        return cls(
            id="GremlinShield",
            name="Gremlin (Shield)",
            hp=hp,
            max_hp=hp,
            defend_dmg=7,
            attack_dmg=6,
            solo_attack_mode=False,
        )

    def get_move(self, roll: int) -> None:
        MOVE_DEFEND = 1
        MOVE_ATTACK = 2

        other_monsters = [m for m in self.state.monsters if m != self and not m.is_dead()]

        if not other_monsters and not self.solo_attack_mode:
            self.set_move(MonsterMove(MOVE_DEFEND, MonsterIntent.DEFEND, 0))
            self.solo_attack_mode = True
        elif not other_monsters and self.solo_attack_mode:
            self.set_move(MonsterMove(MOVE_ATTACK, MonsterIntent.ATTACK, self.attack_dmg))
        else:
            self.set_move(MonsterMove(MOVE_DEFEND, MonsterIntent.DEFEND, 0))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return

        if self.next_move.move_id == 1:
            other_monsters = [m for m in self.state.monsters if m != self and not m.is_dead()]
            if other_monsters:
                target = other_monsters[0]
                target.gain_block(self.defend_dmg)
            else:
                self.gain_block(self.defend_dmg)
        elif self.next_move.move_id == 2:
            damage = self.get_intent_damage()
            player.take_damage(damage)


@dataclass
class GremlinTsundere(MonsterBase):
    block_amt: int = 7
    bash_dmg: int = 6
    ascension_level: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "GremlinTsundere":
        if ascension >= 17:
            hp = hp_rng.random_int_between(13, 17)
            block_amt = 11
        elif ascension >= 7:
            hp = hp_rng.random_int_between(13, 17)
            block_amt = 8
        else:
            hp = hp_rng.random_int_between(12, 15)
            block_amt = 7

        bash_dmg = 8 if ascension >= 2 else 6
        return cls(
            id="GremlinTsundere",
            name="Gremlin (Tsundere)",
            hp=hp,
            max_hp=hp,
            block_amt=block_amt,
            bash_dmg=bash_dmg,
            ascension_level=ascension,
        )

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.DEFEND, name="Protect"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return

        if self.next_move.move_id == 1:
            other_monsters = [m for m in self.state.monsters if m != self and not m.is_dead()]
            if other_monsters:
                other_monsters[0].gain_block(self.block_amt)
            else:
                player.take_damage(max(0, self.bash_dmg + self.get_effective_strength()))
        elif self.next_move.move_id == 2:
            player.take_damage(self.get_intent_damage())


@dataclass
class GremlinSneaky(MonsterBase):
    attack_dmg: int = 9

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "GremlinSneaky":
        hp = hp_rng.random_int_between(10, 14)
        return cls(
            id="GremlinSneaky",
            name="Gremlin (Sneaky)",
            hp=hp,
            max_hp=hp,
            attack_dmg=9,
        )

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, self.attack_dmg))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        if self.next_move.move_id == 1:
            damage = self.get_intent_damage()
            player.take_damage(damage)


@dataclass
class GremlinWizard(MonsterBase):
    attack_dmg: int = 25
    charge_count: int = 0
    first_explosion_done: bool = False

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "GremlinWizard":
        hp = hp_rng.random_int_between(21, 25)
        return cls(
            id="GremlinWizard",
            name="Gremlin Wizard",
            hp=hp,
            max_hp=hp,
            attack_dmg=25,
        )

    def get_move(self, roll: int) -> None:
        MOVE_CHARGE = 1
        MOVE_EXPLOSION = 2

        if self.first_explosion_done:
            min_charge = 3
        else:
            min_charge = 2

        if self.charge_count < min_charge:
            self.charge_count += 1
            self.set_move(MonsterMove(MOVE_CHARGE, MonsterIntent.BUFF, name="Charge"))
        else:
            self.charge_count = 0
            self.first_explosion_done = True
            self.set_move(MonsterMove(MOVE_EXPLOSION, MonsterIntent.ATTACK, self.attack_dmg, name="Big Explosion"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return

        if self.next_move.move_id == 1:
            pass
        elif self.next_move.move_id == 2:
            damage = self.get_intent_damage()
            player.take_damage(damage)


@dataclass
class GremlinWar(MonsterBase):
    attack_dmg: int = 4

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "GremlinWar":
        hp = hp_rng.random_int_between(20, 24)
        gremlin = cls(
            id="GremlinWar",
            name="Gremlin War",
            hp=hp,
            max_hp=hp,
            attack_dmg=4,
        )
        from sts_py.engine.combat.powers import AngryPower
        gremlin.add_power(AngryPower(amount=1, owner="monster_0"))
        return gremlin

    def get_move(self, roll: int) -> None:
        self.set_move(MonsterMove(1, MonsterIntent.ATTACK, self.attack_dmg))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        if self.next_move.move_id == 1:
            damage = self.get_intent_damage()
            player.take_damage(damage)


@dataclass
class Cultist(MonsterBase):
    ritual_amount: int = 3
    first_move: bool = True
    ascension_level: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Cultist":
        if ascension >= 7:
            hp = hp_rng.random_int_between(50, 56)
        else:
            hp = hp_rng.random_int_between(48, 54)

        ritual = 4 if ascension >= 2 else 3
        ascension_level = ascension

        cultist = cls(
            id="Cultist",
            name="Cultist",
            hp=hp,
            max_hp=hp,
            ritual_amount=ritual,
            ascension_level=ascension_level,
        )
        return cultist

    def get_move(self, roll: int) -> None:
        MOVE_DARK_STRIKE = 1
        MOVE_INCANTATION = 3

        if self.first_move:
            self.first_move = False
            self.set_move(MonsterMove(MOVE_INCANTATION, MonsterIntent.BUFF, name="Incantation"))
            return

        self.set_move(MonsterMove(MOVE_DARK_STRIKE, MonsterIntent.ATTACK, 6))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move

        if move.intent.is_attack():
            damage = self.get_intent_damage()
            player.take_damage(damage)
        elif move.intent.is_buff():
            from sts_py.engine.combat.powers import RitualPower
            ritual_amt = self.ritual_amount + 1 if getattr(self, 'ascension_level', 0) >= 17 else self.ritual_amount
            self.add_power(RitualPower(amount=ritual_amt, owner=self.id))


@dataclass
class FungiBeast(MonsterBase):
    bite_dmg: int = 6
    grow_str: int = 3
    vuln_amt: int = 2
    last_move_1: int = 0
    last_move_2: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "FungiBeast":
        from sts_py.engine.combat.powers import SporeCloudPower
        hp = hp_rng.random_int_between(22, 28)
        fungi = cls(
            id="FungiBeast",
            name="Fungi Beast",
            hp=hp,
            max_hp=hp,
            bite_dmg=6,
            grow_str=3,
            vuln_amt=2,
            last_move_1=0,
            last_move_2=0,
        )
        fungi.add_power(SporeCloudPower(amount=2, owner="monster"))
        return fungi

    def _update_last_moves(self, move_id: int) -> None:
        self.last_move_2 = self.last_move_1
        self.last_move_1 = move_id

    def _last_two_moves(self, move_id: int) -> bool:
        return self.last_move_1 == move_id and self.last_move_2 == move_id

    def _last_move(self, move_id: int) -> bool:
        return self.last_move_1 == move_id

    def get_move(self, roll: int) -> None:
        MOVE_BITE = 1
        MOVE_GROW = 2

        if roll < 60:
            if self._last_two_moves(MOVE_BITE):
                self._update_last_moves(MOVE_GROW)
                self.set_move(MonsterMove(MOVE_GROW, MonsterIntent.BUFF, name="Grow"))
            else:
                self._update_last_moves(MOVE_BITE)
                self.set_move(MonsterMove(MOVE_BITE, MonsterIntent.ATTACK, self.bite_dmg))
        elif self._last_move(MOVE_GROW):
            self._update_last_moves(MOVE_BITE)
            self.set_move(MonsterMove(MOVE_BITE, MonsterIntent.ATTACK, self.bite_dmg))
        else:
            self._update_last_moves(MOVE_GROW)
            self.set_move(MonsterMove(MOVE_GROW, MonsterIntent.BUFF, name="Grow"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.move_id == 1:
            damage = self.get_intent_damage()
            player.take_damage(damage)
        elif move.move_id == 2:
            self.gain_strength(self.grow_str)

    def on_death(self) -> None:
        from sts_py.engine.combat.powers import create_power
        for power in self.powers.powers:
            if power.id == "Spore Cloud":
                turn_has_ended = getattr(self.state, 'turn_has_ended', False)
                self.state.player.add_power(create_power("Vulnerable", power.amount, "player", is_source_monster=True, turn_has_ended=turn_has_ended))


@dataclass
class SlaverRed(MonsterBase):
    stab_dmg: int = 13
    scrape_dmg: int = 8
    vuln_amt: int = 1
    entangle_used: bool = False
    first_move: bool = True
    last_move_1: int = 0
    last_move_2: int = 0
    ascension_level: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "SlaverRed":
        if ascension >= 7:
            hp = hp_rng.random_int_between(48, 52)
        else:
            hp = hp_rng.random_int_between(46, 50)

        if ascension >= 2:
            stab_dmg = 14
            scrape_dmg = 9
        else:
            stab_dmg = 13
            scrape_dmg = 8

        if ascension >= 17:
            vuln_amt = 2
        else:
            vuln_amt = 1

        return cls(
            id="SlaverRed",
            name="Red Slaver",
            hp=hp,
            max_hp=hp,
            stab_dmg=stab_dmg,
            scrape_dmg=scrape_dmg,
            vuln_amt=vuln_amt,
            entangle_used=False,
            first_move=True,
            last_move_1=0,
            last_move_2=0,
            ascension_level=ascension,
        )

    def _update_last_moves(self, move_id: int) -> None:
        self.last_move_2 = self.last_move_1
        self.last_move_1 = move_id

    def _last_two_moves(self, move_id: int) -> bool:
        return self.last_move_1 == move_id and self.last_move_2 == move_id

    def get_move(self, roll: int) -> None:
        MOVE_STAB = 1
        MOVE_ENTANGLE = 2
        MOVE_SCRAPE = 3

        if self.first_move:
            self.first_move = False
            self.set_move(MonsterMove(MOVE_STAB, MonsterIntent.ATTACK, self.stab_dmg))
            return

        if roll < 75 and not self.entangle_used:
            self.set_move(MonsterMove(MOVE_ENTANGLE, MonsterIntent.STRONG_DEBUFF, name="Entangle"))
            return

        if roll < 55 and self.entangle_used and not self._last_two_moves(MOVE_STAB):
            self.set_move(MonsterMove(MOVE_STAB, MonsterIntent.ATTACK, self.stab_dmg))
            return

        if getattr(self, 'ascension_level', 0) >= 17:
            if not self.last_move(MOVE_SCRAPE):
                self.set_move(MonsterMove(MOVE_SCRAPE, MonsterIntent.ATTACK_DEBUFF, self.scrape_dmg, name="Scrape"))
                return
            self.set_move(MonsterMove(MOVE_STAB, MonsterIntent.ATTACK, self.stab_dmg))
            return

        if not self._last_two_moves(MOVE_SCRAPE):
            self.set_move(MonsterMove(MOVE_SCRAPE, MonsterIntent.ATTACK_DEBUFF, self.scrape_dmg, name="Scrape"))
            return

        self.set_move(MonsterMove(MOVE_STAB, MonsterIntent.ATTACK, self.stab_dmg))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.move_id == 1:
            damage = self.get_intent_damage()
            player.take_damage(damage)
        elif move.move_id == 2:
            self.entangle_used = True
            from sts_py.engine.combat.powers import create_power
            player.add_power(create_power("Entangled", 1, "player"))
        elif move.move_id == 3:
            damage = self.get_intent_damage()
            player.take_damage(damage)
            from sts_py.engine.combat.powers import create_power
            combat_state = getattr(self, '_combat_state', None)
            turn_has_ended = getattr(combat_state, 'turn_has_ended', False) if combat_state else False
            player.add_power(create_power("Vulnerable", self.vuln_amt, "player", is_source_monster=True, turn_has_ended=turn_has_ended))


@dataclass
class SlaverBlue(MonsterBase):
    stab_dmg: int = 12
    rake_dmg: int = 7
    weak_amt: int = 1
    last_move_1: int = 0
    last_move_2: int = 0
    ascension_level: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "SlaverBlue":
        if ascension >= 7:
            hp = hp_rng.random_int_between(48, 52)
        else:
            hp = hp_rng.random_int_between(46, 50)

        if ascension >= 2:
            stab_dmg = 13
            rake_dmg = 8
        else:
            stab_dmg = 12
            rake_dmg = 7

        if ascension >= 17:
            weak_amt = 2
        else:
            weak_amt = 1

        return cls(
            id="SlaverBlue",
            name="Blue Slaver",
            hp=hp,
            max_hp=hp,
            stab_dmg=stab_dmg,
            rake_dmg=rake_dmg,
            weak_amt=weak_amt,
            last_move_1=0,
            last_move_2=0,
            ascension_level=ascension,
        )

    def _last_two_moves(self, move_id: int) -> bool:
        return self.last_move_1 == move_id and self.last_move_2 == move_id

    def _last_move(self, move_id: int) -> bool:
        return self.last_move_1 == move_id

    def get_move(self, roll: int) -> None:
        MOVE_STAB = 1
        MOVE_RAKE = 4

        if roll >= 40 and not self._last_two_moves(MOVE_STAB):
            self.set_move(MonsterMove(MOVE_STAB, MonsterIntent.ATTACK, self.stab_dmg))
            return

        if getattr(self, 'ascension_level', 0) >= 17:
            if not self._last_move(MOVE_RAKE):
                self.set_move(MonsterMove(MOVE_RAKE, MonsterIntent.ATTACK_DEBUFF, self.rake_dmg, name="Rake"))
                return
            self.set_move(MonsterMove(MOVE_STAB, MonsterIntent.ATTACK, self.stab_dmg))
            return

        if not self._last_two_moves(MOVE_RAKE):
            self.set_move(MonsterMove(MOVE_RAKE, MonsterIntent.ATTACK_DEBUFF, self.rake_dmg, name="Rake"))
            return

        self.set_move(MonsterMove(MOVE_STAB, MonsterIntent.ATTACK, self.stab_dmg))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.move_id == 1:
            damage = self.get_intent_damage()
            player.take_damage(damage)
        elif move.move_id == 4:
            damage = self.get_intent_damage()
            player.take_damage(damage)
            from sts_py.engine.combat.powers import create_power
            turn_has_ended = getattr(self.state, 'turn_has_ended', False)
            player.add_power(create_power("Weak", self.weak_amt, "player", is_source_monster=True, turn_has_ended=turn_has_ended))


@dataclass
class Looter(MonsterBase):
    swipe_dmg: int = 10
    lunge_dmg: int = 12
    escape_def: int = 6
    gold_amt: int = 15
    slash_count: int = 0
    stolen_gold: int = 0
    next_move_id: int = 0
    pending_next_move: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Looter":
        from sts_py.engine.combat.powers import ThieveryPower
        hp = hp_rng.random_int_between(44, 48)
        looter = cls(
            id="Looter",
            name="Looter",
            hp=hp,
            max_hp=hp,
            swipe_dmg=10,
            lunge_dmg=12,
            escape_def=6,
            gold_amt=15,
            slash_count=0,
            stolen_gold=0,
            next_move_id=0,
            pending_next_move=0,
        )
        thievery = ThieveryPower()
        thievery.amount = 15
        thievery.owner = "monster"
        looter.add_power(thievery)
        return looter

    def get_move(self, roll: int) -> None:
        MOVE_MUG = 1
        MOVE_SMOKE_BOMB = 2
        MOVE_ESCAPE = 3
        MOVE_LUNGE = 4

        if self.slash_count < 2:
            self._update_last_moves(MOVE_MUG)
            self.set_move(MonsterMove(MOVE_MUG, MonsterIntent.ATTACK, self.swipe_dmg))
        elif self.next_move_id == MOVE_SMOKE_BOMB:
            self.set_move(MonsterMove(MOVE_SMOKE_BOMB, MonsterIntent.DEFEND, 0))
        elif self.next_move_id == MOVE_ESCAPE:
            self.set_move(MonsterMove(MOVE_ESCAPE, MonsterIntent.ESCAPE, 0))
        else:
            if roll < 50:
                self.pending_next_move = MOVE_SMOKE_BOMB
                self._update_last_moves(MOVE_LUNGE)
                self.set_move(MonsterMove(MOVE_LUNGE, MonsterIntent.ATTACK, self.lunge_dmg))
            else:
                self.pending_next_move = MOVE_ESCAPE
                self._update_last_moves(MOVE_SMOKE_BOMB)
                self.set_move(MonsterMove(MOVE_SMOKE_BOMB, MonsterIntent.DEFEND, 0))

    def _update_last_moves(self, move_id: int) -> None:
        self.last_move_2 = getattr(self, 'last_move_2', 0)
        self.last_move_1 = getattr(self, 'last_move_1', 0)
        self.last_move_2 = self.last_move_1
        self.last_move_1 = move_id

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        MOVE_MUG = 1
        MOVE_SMOKE_BOMB = 2
        MOVE_ESCAPE = 3
        MOVE_LUNGE = 4
        move = self.next_move

        if move.move_id == MOVE_MUG:
            damage = self.get_intent_damage()
            player.take_damage(damage)
            gold_stolen = min(self.gold_amt, getattr(player, 'gold', 0))
            self.stolen_gold += gold_stolen
            if hasattr(player, 'gold'):
                player.gold -= gold_stolen
            self.slash_count += 1
            if self.slash_count == 2:
                if self.pending_next_move == MOVE_SMOKE_BOMB:
                    self.next_move_id = MOVE_SMOKE_BOMB
                elif self.pending_next_move == MOVE_ESCAPE:
                    self.next_move_id = MOVE_ESCAPE
                else:
                    self.next_move_id = MOVE_SMOKE_BOMB
        elif move.move_id == MOVE_LUNGE:
            damage = self.get_intent_damage()
            player.take_damage(damage)
            gold_stolen = min(self.gold_amt, getattr(player, 'gold', 0))
            self.stolen_gold += gold_stolen
            if hasattr(player, 'gold'):
                player.gold -= gold_stolen
            self.slash_count += 1
            self.next_move_id = MOVE_SMOKE_BOMB
        elif move.move_id == MOVE_SMOKE_BOMB:
            self.gain_block(self.escape_def)
            self.next_move_id = MOVE_ESCAPE
        elif move.move_id == MOVE_ESCAPE:
            self.escape()

    def escape(self) -> None:
        self.escaped = True
        self.is_escaping = True


@dataclass
class GremlinNob(MonsterBase):
    skull_bash_dmg: int = 6
    rush_dmg: int = 14
    angry_amt: int = 2
    vuln_amt: int = 2
    used_bellow: bool = False
    can_vuln: bool = True
    last_move_1: int = 0
    last_move_2: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "GremlinNob":
        if ascension >= 2:
            hp = hp_rng.random_int_between(85, 90)
        else:
            hp = hp_rng.random_int_between(82, 86)

        bash_dmg = 8 if ascension >= 3 else 6
        rush_dmg = 16 if ascension >= 3 else 14

        return cls(
            id="GremlinNob",
            name="Gremlin Nob",
            hp=hp,
            max_hp=hp,
            skull_bash_dmg=bash_dmg,
            rush_dmg=rush_dmg,
            angry_amt=2,
            vuln_amt=2,
            used_bellow=False,
            can_vuln=True,
            last_move_1=0,
            last_move_2=0,
        )

    def _update_last_moves(self, move_id: int) -> None:
        self.last_move_2 = self.last_move_1
        self.last_move_1 = move_id

    def _last_two_moves(self, move_id: int) -> bool:
        return self.last_move_1 == move_id and self.last_move_2 == move_id

    def get_move(self, roll: int) -> None:
        MOVE_RUSH = 1
        MOVE_SKULL_BASH = 2
        MOVE_BELLOW = 3

        if not self.used_bellow:
            self.used_bellow = True
            self._update_last_moves(MOVE_BELLOW)
            self.set_move(MonsterMove(MOVE_BELLOW, MonsterIntent.BUFF, name="Bellow"))
            return

        if roll < 33:
            self._update_last_moves(MOVE_SKULL_BASH)
            if self.can_vuln:
                self.set_move(MonsterMove(MOVE_SKULL_BASH, MonsterIntent.ATTACK_DEBUFF, self.skull_bash_dmg, name="Skull Bash"))
            else:
                self.set_move(MonsterMove(MOVE_SKULL_BASH, MonsterIntent.ATTACK, self.skull_bash_dmg, name="Skull Bash"))
            return

        if self._last_two_moves(MOVE_RUSH):
            self._update_last_moves(MOVE_SKULL_BASH)
            if self.can_vuln:
                self.set_move(MonsterMove(MOVE_SKULL_BASH, MonsterIntent.ATTACK_DEBUFF, self.skull_bash_dmg, name="Skull Bash"))
            else:
                self.set_move(MonsterMove(MOVE_SKULL_BASH, MonsterIntent.ATTACK, self.skull_bash_dmg, name="Skull Bash"))
        else:
            self._update_last_moves(MOVE_RUSH)
            self.set_move(MonsterMove(MOVE_RUSH, MonsterIntent.ATTACK, self.rush_dmg, name="Rush"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move

        if move.intent.is_buff():
            self.gain_strength(self.angry_amt)
        elif move.intent == MonsterIntent.ATTACK_DEBUFF:
            damage = self.get_intent_damage()
            player.take_damage(damage)
            if self.can_vuln:
                from sts_py.engine.combat.powers import create_power
                player.add_power(create_power("Vulnerable", self.vuln_amt, "player"))
        elif move.intent.is_attack():
            damage = self.get_intent_damage()
            player.take_damage(damage)


@dataclass
class Mugger(MonsterBase):
    swipe_dmg: int = 10
    lunge_dmg: int = 16
    escape_def: int = 11
    gold_amt: int = 15
    slash_count: int = 0
    stolen_gold: int = 0
    next_move_id: int = 0
    pending_next_move: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Mugger":
        from sts_py.engine.combat.powers import ThieveryPower
        hp = hp_rng.random_int_between(48, 52)
        mugger = cls(
            id="Mugger",
            name="Mugger",
            hp=hp,
            max_hp=hp,
            swipe_dmg=10,
            lunge_dmg=16,
            escape_def=11,
            gold_amt=15,
            slash_count=0,
            stolen_gold=0,
            next_move_id=0,
            pending_next_move=0,
        )
        thievery = ThieveryPower()
        thievery.amount = 15
        thievery.owner = "monster"
        mugger.add_power(thievery)
        return mugger

    def get_move(self, roll: int) -> None:
        MOVE_MUG = 1
        MOVE_SMOKE_BOMB = 2
        MOVE_ESCAPE = 3
        MOVE_LUNGE = 4

        if self.slash_count < 2:
            self._update_last_moves(MOVE_MUG)
            self.set_move(MonsterMove(MOVE_MUG, MonsterIntent.ATTACK, self.swipe_dmg))
        elif self.next_move_id == MOVE_SMOKE_BOMB:
            self.set_move(MonsterMove(MOVE_SMOKE_BOMB, MonsterIntent.DEFEND, 0))
        elif self.next_move_id == MOVE_ESCAPE:
            self.set_move(MonsterMove(MOVE_ESCAPE, MonsterIntent.ESCAPE, 0))
        else:
            if roll < 50:
                self.pending_next_move = MOVE_SMOKE_BOMB
                self._update_last_moves(MOVE_LUNGE)
                self.set_move(MonsterMove(MOVE_LUNGE, MonsterIntent.ATTACK, self.lunge_dmg))
            else:
                self.pending_next_move = MOVE_ESCAPE
                self._update_last_moves(MOVE_SMOKE_BOMB)
                self.set_move(MonsterMove(MOVE_SMOKE_BOMB, MonsterIntent.DEFEND, 0))

    def _update_last_moves(self, move_id: int) -> None:
        self.last_move_2 = getattr(self, 'last_move_2', 0)
        self.last_move_1 = getattr(self, 'last_move_1', 0)
        self.last_move_2 = self.last_move_1
        self.last_move_1 = move_id

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        MOVE_MUG = 1
        MOVE_SMOKE_BOMB = 2
        MOVE_ESCAPE = 3
        MOVE_LUNGE = 4
        move = self.next_move

        if move.move_id == MOVE_MUG:
            damage = self.get_intent_damage()
            player.take_damage(damage)
            gold_stolen = min(self.gold_amt, getattr(player, 'gold', 0))
            self.stolen_gold += gold_stolen
            if hasattr(player, 'gold'):
                player.gold -= gold_stolen
            self.slash_count += 1
            if self.slash_count == 2:
                if self.pending_next_move == MOVE_SMOKE_BOMB:
                    self.next_move_id = MOVE_SMOKE_BOMB
                elif self.pending_next_move == MOVE_ESCAPE:
                    self.next_move_id = MOVE_ESCAPE
                else:
                    self.next_move_id = MOVE_SMOKE_BOMB
        elif move.move_id == MOVE_LUNGE:
            damage = self.get_intent_damage()
            player.take_damage(damage)
            gold_stolen = min(self.gold_amt, getattr(player, 'gold', 0))
            self.stolen_gold += gold_stolen
            if hasattr(player, 'gold'):
                player.gold -= gold_stolen
            self.slash_count += 1
            self.next_move_id = MOVE_SMOKE_BOMB
        elif move.move_id == MOVE_SMOKE_BOMB:
            self.gain_block(self.escape_def)
            self.next_move_id = MOVE_ESCAPE
        elif move.move_id == MOVE_ESCAPE:
            self.escape()

    def escape(self) -> None:
        self.escaped = True
        self.is_escaping = True


@dataclass
class AcidSlimeMedium(MonsterBase):
    spit_dmg: int = 7
    slam_dmg: int = 10
    weak_amount: int = 1

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "AcidSlimeMedium":
        if ascension >= 7:
            hp = hp_rng.random_int_between(29, 34)
        else:
            hp = hp_rng.random_int_between(28, 32)

        if ascension >= 2:
            spit_dmg = 8
            slam_dmg = 12
        else:
            spit_dmg = 7
            slam_dmg = 10

        return cls(
            id="AcidSlimeMedium",
            name="Acid Slime (M)",
            hp=hp,
            max_hp=hp,
            spit_dmg=spit_dmg,
            slam_dmg=slam_dmg,
            weak_amount=1,
        )

    def get_move(self, roll: int) -> None:
        MOVE_SPIT = 1
        MOVE_SLAM = 2
        MOVE_LICK = 4

        if getattr(self, 'ascension_level', 0) >= 17:
            if roll < 40:
                if self.last_two_moves(MOVE_SPIT):
                    if roll < 50:
                        self.set_move(MonsterMove(MOVE_SLAM, MonsterIntent.ATTACK, self.slam_dmg))
                    else:
                        self.set_move(MonsterMove(MOVE_LICK, MonsterIntent.DEBUFF, name="Lick"))
                else:
                    self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK_DEBUFF, self.spit_dmg))
            elif roll < 80:
                if self.last_two_moves(MOVE_SLAM):
                    if roll < 50:
                        self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK_DEBUFF, self.spit_dmg))
                    else:
                        self.set_move(MonsterMove(MOVE_LICK, MonsterIntent.DEBUFF, name="Lick"))
                else:
                    self.set_move(MonsterMove(MOVE_SLAM, MonsterIntent.ATTACK, self.slam_dmg))
            elif self.last_move(MOVE_LICK):
                if roll < 40:
                    self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK_DEBUFF, self.spit_dmg))
                else:
                    self.set_move(MonsterMove(MOVE_SLAM, MonsterIntent.ATTACK, self.slam_dmg))
            else:
                self.set_move(MonsterMove(MOVE_LICK, MonsterIntent.DEBUFF, name="Lick"))
        else:
            if roll < 30:
                if self.last_two_moves(MOVE_SPIT):
                    if roll < 50:
                        self.set_move(MonsterMove(MOVE_SLAM, MonsterIntent.ATTACK, self.slam_dmg))
                    else:
                        self.set_move(MonsterMove(MOVE_LICK, MonsterIntent.DEBUFF, name="Lick"))
                else:
                    self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK_DEBUFF, self.spit_dmg))
            elif roll < 70:
                if self.last_move(MOVE_SLAM):
                    if roll < 40:
                        self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK_DEBUFF, self.spit_dmg))
                    else:
                        self.set_move(MonsterMove(MOVE_LICK, MonsterIntent.DEBUFF, name="Lick"))
                else:
                    self.set_move(MonsterMove(MOVE_SLAM, MonsterIntent.ATTACK, self.slam_dmg))
            elif self.last_two_moves(MOVE_LICK):
                if roll < 40:
                    self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK_DEBUFF, self.spit_dmg))
                else:
                    self.set_move(MonsterMove(MOVE_SLAM, MonsterIntent.ATTACK, self.slam_dmg))
            else:
                self.set_move(MonsterMove(MOVE_LICK, MonsterIntent.DEBUFF, name="Lick"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.intent == MonsterIntent.ATTACK_DEBUFF:
            damage = self.get_intent_damage()
            player.take_damage(damage)
            from sts_py.engine.content.card_instance import CardInstance
            slimed = CardInstance(card_id="Slimed", upgraded=False)
            self.state.card_manager.discard_pile.add(slimed)
        elif move.intent.is_attack():
            damage = self.get_intent_damage()
            player.take_damage(damage)
        elif move.intent.is_debuff():
            from sts_py.engine.combat.powers import WeakPower
            player.add_power(WeakPower(amount=self.weak_amount, owner=player.id))


@dataclass
class AcidSlimeLarge(MonsterBase):
    spit_dmg: int = 11
    slam_dmg: int = 16
    weak_amount: int = 2
    has_split: bool = True
    has_split_triggered: bool = False

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0, hp: int = None) -> "AcidSlimeLarge":
        if hp is None:
            if ascension >= 7:
                hp = hp_rng.random_int_between(68, 72)
            else:
                hp = hp_rng.random_int_between(65, 69)

        if ascension >= 2:
            spit_dmg = 12
            slam_dmg = 18
        else:
            spit_dmg = 11
            slam_dmg = 16

        slime = cls(
            id="AcidSlimeLarge",
            name="Acid Slime (L)",
            hp=hp,
            max_hp=hp,
            spit_dmg=spit_dmg,
            slam_dmg=slam_dmg,
            weak_amount=2,
        )
        return slime

    def get_move(self, roll: int) -> None:
        MOVE_SPIT = 1
        MOVE_SLAM = 2
        MOVE_SPLIT = 3
        MOVE_LICK = 4

        if self.has_split_triggered:
            self.set_move(MonsterMove(MOVE_SPLIT, MonsterIntent.UNKNOWN, name="Split"))
            return

        if getattr(self, 'ascension_level', 0) >= 17:
            if roll < 30:
                if self.last_two_moves(MOVE_SPIT):
                    if roll < 50:
                        self.set_move(MonsterMove(MOVE_SLAM, MonsterIntent.ATTACK, self.slam_dmg))
                    else:
                        self.set_move(MonsterMove(MOVE_LICK, MonsterIntent.DEBUFF, name="Lick"))
                else:
                    self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK_DEBUFF, self.spit_dmg))
            elif roll < 70:
                if self.last_two_moves(MOVE_SLAM):
                    if roll < 50:
                        self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK_DEBUFF, self.spit_dmg))
                    else:
                        self.set_move(MonsterMove(MOVE_LICK, MonsterIntent.DEBUFF, name="Lick"))
                else:
                    self.set_move(MonsterMove(MOVE_SLAM, MonsterIntent.ATTACK, self.slam_dmg))
            elif self.last_two_moves(MOVE_LICK):
                if roll < 50:
                    self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK_DEBUFF, self.spit_dmg))
                else:
                    self.set_move(MonsterMove(MOVE_SLAM, MonsterIntent.ATTACK, self.slam_dmg))
            else:
                self.set_move(MonsterMove(MOVE_LICK, MonsterIntent.DEBUFF, name="Lick"))
        else:
            if roll < 30:
                if self.last_two_moves(MOVE_SPIT):
                    if roll < 50:
                        self.set_move(MonsterMove(MOVE_SLAM, MonsterIntent.ATTACK, self.slam_dmg))
                    else:
                        self.set_move(MonsterMove(MOVE_LICK, MonsterIntent.DEBUFF, name="Lick"))
                else:
                    self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK_DEBUFF, self.spit_dmg))
            elif roll < 70:
                if self.last_move(MOVE_SLAM):
                    if roll < 40:
                        self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK_DEBUFF, self.spit_dmg))
                    else:
                        self.set_move(MonsterMove(MOVE_LICK, MonsterIntent.DEBUFF, name="Lick"))
                else:
                    self.set_move(MonsterMove(MOVE_SLAM, MonsterIntent.ATTACK, self.slam_dmg))
            elif self.last_two_moves(MOVE_LICK):
                if roll < 40:
                    self.set_move(MonsterMove(MOVE_SPIT, MonsterIntent.ATTACK_DEBUFF, self.spit_dmg))
                else:
                    self.set_move(MonsterMove(MOVE_SLAM, MonsterIntent.ATTACK, self.slam_dmg))
            else:
                self.set_move(MonsterMove(MOVE_LICK, MonsterIntent.DEBUFF, name="Lick"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return

        move = self.next_move

        if move.move_id == 3:
            self.has_split_triggered = True
            from sts_py.engine.monsters.exordium import AcidSlimeMedium
            split_hp = self.hp
            ascension = getattr(self, 'ascension_level', 0)
            for _ in range(2):
                new_slime = AcidSlimeMedium(
                    id="AcidSlimeMedium",
                    name="Acid Slime (M)",
                    hp=split_hp,
                    max_hp=split_hp,
                    spit_dmg=self.spit_dmg,
                    slam_dmg=self.slam_dmg,
                    weak_amount=self.weak_amount,
                )
                if hasattr(self, 'state') and self.state:
                    self.state.add_monster(new_slime)
            return

        if move.move_id == 1:
            damage = self.get_intent_damage()
            player.take_damage(damage)
            from sts_py.engine.content.card_instance import CardInstance
            for _ in range(2):
                slimed = CardInstance(card_id="Slimed", upgraded=False)
                self.state.card_manager.discard_pile.add(slimed)
        elif move.move_id == 2:
            damage = self.get_intent_damage()
            player.take_damage(damage)
        elif move.move_id == 4:
            from sts_py.engine.combat.powers import WeakPower
            player.add_power(WeakPower(amount=self.weak_amount, owner=player.id))

    def take_damage(self, amount: int) -> int:
        actual = super().take_damage(amount)
        if not self.is_dying and self.hp <= self.max_hp // 2 and self.next_move and self.next_move.move_id != 3 and not self.has_split_triggered:
            self.has_split_triggered = True
            self.set_move(MonsterMove(3, MonsterIntent.UNKNOWN, name="Split"))
        return actual


@dataclass
class GremlinNob(MonsterBase):
    rush_dmg: int = 14
    bash_dmg: int = 6
    anger_amount: int = 2
    used_bellow: bool = False
    ascension_level: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "GremlinNob":
        if ascension >= 8:
            hp = hp_rng.random_int_between(85, 90)
        else:
            hp = hp_rng.random_int_between(82, 86)

        if ascension >= 3:
            rush_dmg = 16
            bash_dmg = 8
        else:
            rush_dmg = 14
            bash_dmg = 6

        if ascension >= 18:
            anger_amount = 3
        else:
            anger_amount = 2

        return cls(
            id="GremlinNob",
            name="Gremlin Nob",
            hp=hp,
            max_hp=hp,
            rush_dmg=rush_dmg,
            bash_dmg=bash_dmg,
            anger_amount=anger_amount,
            ascension_level=ascension,
        )

    def get_move(self, roll: int) -> None:
        MOVE_RUSH = 1
        MOVE_SKULL_BASH = 2
        MOVE_BELLOW = 3

        if not self.used_bellow:
            self.used_bellow = True
            self.set_move(MonsterMove(MOVE_BELLOW, MonsterIntent.BUFF, name="Bellow"))
            return

        if getattr(self, 'ascension_level', 0) >= 18:
            if not self.last_move(MOVE_SKULL_BASH) and not self.last_move_before(MOVE_SKULL_BASH):
                self.set_move(MonsterMove(MOVE_SKULL_BASH, MonsterIntent.ATTACK_DEBUFF, self.bash_dmg, name="Skull Bash"))
            elif self.last_two_moves(MOVE_RUSH):
                self.set_move(MonsterMove(MOVE_SKULL_BASH, MonsterIntent.ATTACK_DEBUFF, self.bash_dmg, name="Skull Bash"))
            else:
                self.set_move(MonsterMove(MOVE_RUSH, MonsterIntent.ATTACK, self.rush_dmg, name="Bull Rush"))
        else:
            if roll < 33:
                self.set_move(MonsterMove(MOVE_SKULL_BASH, MonsterIntent.ATTACK_DEBUFF, self.bash_dmg, name="Skull Bash"))
            elif self.last_two_moves(MOVE_RUSH):
                self.set_move(MonsterMove(MOVE_SKULL_BASH, MonsterIntent.ATTACK_DEBUFF, self.bash_dmg, name="Skull Bash"))
            else:
                self.set_move(MonsterMove(MOVE_RUSH, MonsterIntent.ATTACK, self.rush_dmg, name="Bull Rush"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.move_id == 1:  # Rush
            damage = self.get_intent_damage()
            player.take_damage(damage)
        elif move.move_id == 2:  # Skull Bash
            damage = self.get_intent_damage()
            player.take_damage(damage)
            from sts_py.engine.combat.powers import create_power
            turn_has_ended = getattr(self.state, 'turn_has_ended', False)
            player.add_power(create_power("Vulnerable", 2, "player", is_source_monster=True, turn_has_ended=turn_has_ended))
        elif move.move_id == 3:  # Bellow — gain Anger power + strength
            self.gain_strength(self.anger_amount)
            self.add_power(AngerPower(amount=self.anger_amount, owner=self.id))


@dataclass
class Lagavulin(MonsterBase):
    attack_dmg: int = 18
    debuff_amount: int = -1
    metallicize_amount: int = 8
    asleep: bool = True
    is_out_triggered: bool = False
    idle_count: int = 0
    debuff_turn_count: int = 0
    last_move_1: int = 0
    last_move_2: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0, asleep: bool = True) -> "Lagavulin":
        from sts_py.engine.combat.powers import MetallicizePower

        if ascension >= 8:
            hp = hp_rng.random_int_between(112, 115)
        else:
            hp = hp_rng.random_int_between(109, 111)

        attack_dmg = 20 if ascension >= 3 else 18
        debuff = -2 if ascension >= 18 else -1

        instance = cls(
            id="Lagavulin",
            name="Lagavulin",
            hp=hp,
            max_hp=hp,
            attack_dmg=attack_dmg,
            debuff_amount=debuff,
            metallicize_amount=8,
            asleep=asleep,
            is_out_triggered=not asleep,
            idle_count=0,
            debuff_turn_count=0,
            last_move_1=0,
            last_move_2=0,
        )

        if asleep:
            instance.add_power(MetallicizePower(amount=8, owner=instance.id))

        return instance

    def _update_last_moves(self, move_id: int) -> None:
        self.last_move_2 = self.last_move_1
        self.last_move_1 = move_id

    def _last_two_moves(self, move_id: int) -> bool:
        return self.last_move_1 == move_id and self.last_move_2 == move_id

    def _last_move(self, move_id: int) -> bool:
        return self.last_move_1 == move_id

    def get_move(self, roll: int) -> None:
        MOVE_DEBUFF = 1
        MOVE_STUN = 4
        MOVE_ATTACK = 3
        MOVE_IDLE = 5
        MOVE_OPEN_NATURAL = 6

        if self.asleep:
            if self.idle_count >= 3:
                self.is_out_triggered = True
                self.asleep = False
                self._update_last_moves(MOVE_OPEN_NATURAL)
                self.set_move(MonsterMove(MOVE_ATTACK, MonsterIntent.ATTACK, self.attack_dmg))
            else:
                self._update_last_moves(MOVE_IDLE)
                self.set_move(MonsterMove(MOVE_IDLE, MonsterIntent.SLEEP, name="Sleep"))
            return

        if self.is_out_triggered and not self.asleep:
            if self.debuff_turn_count < 2:
                if self._last_two_moves(MOVE_ATTACK):
                    self._update_last_moves(MOVE_DEBUFF)
                    self.set_move(MonsterMove(MOVE_DEBUFF, MonsterIntent.STRONG_DEBUFF, name="Soul Strike"))
                else:
                    self._update_last_moves(MOVE_ATTACK)
                    self.set_move(MonsterMove(MOVE_ATTACK, MonsterIntent.ATTACK, self.attack_dmg))
            else:
                self._update_last_moves(MOVE_DEBUFF)
                self.set_move(MonsterMove(MOVE_DEBUFF, MonsterIntent.STRONG_DEBUFF, name="Soul Strike"))
            return

        self._update_last_moves(MOVE_STUN)
        self.set_move(MonsterMove(MOVE_STUN, MonsterIntent.STUN, name="Stunned"))

    def on_damage_taken(self, damage: int) -> None:
        if self.asleep and not self.is_out_triggered and damage > 0:
            self.asleep = False
            self.is_out_triggered = True

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move

        if move.move_id == 1:
            self.debuff_turn_count += 1
            player.add_power(create_power("Strength", self.debuff_amount, "player"))
            player.strength += self.debuff_amount
            player.add_power(create_power("Dexterity", self.debuff_amount, "player"))
            player.dexterity += self.debuff_amount
        elif move.move_id == 3:
            damage = self.get_intent_damage()
            player.take_damage(damage)
        elif move.move_id == 5:
            self.idle_count += 1
            if self.idle_count >= 3:
                self.is_out_triggered = True
                self.asleep = False
        elif move.move_id == 6:
            self.asleep = False
            self.is_out_triggered = True
            for power in list(self.powers.powers):
                if power.id == "Metallicize":
                    power.amount -= 8
                    if power.amount <= 0:
                        self.powers.remove_power("Metallicize")
            damage = self.get_intent_damage()
            player.take_damage(damage)


@dataclass
class Sentry(MonsterBase):
    beam_dmg: int = 9
    dazed_amount: int = 2
    first_move: bool = True
    position_index: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0, position: int = 0) -> "Sentry":
        from sts_py.engine.combat.powers import ArtifactPower

        if ascension >= 8:
            hp = hp_rng.random_int_between(39, 45)
        else:
            hp = hp_rng.random_int_between(38, 42)

        beam_dmg = 10 if ascension >= 3 else 9
        dazed = 3 if ascension >= 18 else 2

        instance = cls(
            id="Sentry",
            name="Sentry",
            hp=hp,
            max_hp=hp,
            beam_dmg=beam_dmg,
            dazed_amount=dazed,
            first_move=True,
            position_index=position,
        )

        instance.add_power(ArtifactPower(amount=1, owner=instance.id))

        return instance

    def get_move(self, roll: int) -> None:
        MOVE_BOLT = 3
        MOVE_BEAM = 4

        if self.first_move:
            self.first_move = False
            if self.position_index % 2 == 0:
                self.set_move(MonsterMove(MOVE_BOLT, MonsterIntent.DEBUFF, name="Dazed"))
            else:
                self.set_move(MonsterMove(MOVE_BEAM, MonsterIntent.ATTACK, self.beam_dmg, name="Beam"))
            return

        if self.last_move(MOVE_BEAM):
            self.set_move(MonsterMove(MOVE_BOLT, MonsterIntent.DEBUFF, name="Dazed"))
        else:
            self.set_move(MonsterMove(MOVE_BEAM, MonsterIntent.ATTACK, self.beam_dmg, name="Beam"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.intent.is_attack():
            damage = self.get_intent_damage()
            hits = max(1, int(getattr(move, "multiplier", 0) or 1))
            for _ in range(hits):
                player.take_damage(damage)
        elif move.intent.is_debuff():
            from sts_py.engine.content.card_instance import CardInstance
            combat_state = getattr(self, '_combat_state', None)
            if combat_state is not None:
                for _ in range(self.dazed_amount):
                    dazed_card = CardInstance(card_id="Dazed", upgraded=False)
                    combat_state.card_manager.discard_pile.add(dazed_card)


@dataclass
class Hexaghost(MonsterBase):
    sear_dmg: int = 6
    tackle_dmg: int = 5
    inferno_dmg: int = 2
    tackle_count: int = 2
    inferno_hits: int = 6
    str_amt: int = 2
    block_amt: int = 12
    burn_count: int = 1
    burn_upgraded: bool = False
    orb_active_count: int = 0
    activated: bool = False

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "Hexaghost":
        if ascension >= 9:
            hp = 264
        else:
            hp = 250

        tackle_dmg = 6 if ascension >= 4 else 5
        inferno_dmg = 3 if ascension >= 4 else 2
        str_amt = 3 if ascension >= 19 else 2
        burn_count = 2 if ascension >= 19 else 1

        return cls(
            id="Hexaghost",
            name="Hexaghost",
            hp=hp,
            max_hp=hp,
            sear_dmg=6,
            tackle_dmg=tackle_dmg,
            inferno_dmg=inferno_dmg,
            tackle_count=2,
            inferno_hits=6,
            str_amt=str_amt,
            block_amt=12,
            burn_count=burn_count,
            burn_upgraded=False,
            orb_active_count=0,
            activated=False,
        )

    def get_move(self, roll: int) -> None:
        MOVE_ACTIVATE = 5
        MOVE_DIVIDER = 1
        MOVE_TACKLE = 2
        MOVE_INFLAME = 3
        MOVE_SEAR = 4
        MOVE_INFERNO = 6

        if not self.activated:
            self.activated = True
            self.set_move(MonsterMove(MOVE_ACTIVATE, MonsterIntent.UNKNOWN, name="Activate"))
            return

        if self.orb_active_count == 0:
            self.set_move(MonsterMove(MOVE_SEAR, MonsterIntent.ATTACK_DEBUFF, base_damage=self.sear_dmg, name="Sear"))
        elif self.orb_active_count == 1:
            self.set_move(MonsterMove(MOVE_TACKLE, MonsterIntent.ATTACK, base_damage=self.tackle_dmg, is_multi_damage=True, multiplier=self.tackle_count, name="Tackle"))
        elif self.orb_active_count == 2:
            self.set_move(MonsterMove(MOVE_SEAR, MonsterIntent.ATTACK_DEBUFF, base_damage=self.sear_dmg, name="Sear"))
        elif self.orb_active_count == 3:
            self.set_move(MonsterMove(MOVE_INFLAME, MonsterIntent.DEFEND_BUFF, name="Inflame"))
        elif self.orb_active_count == 4:
            self.set_move(MonsterMove(MOVE_TACKLE, MonsterIntent.ATTACK, base_damage=self.tackle_dmg, is_multi_damage=True, multiplier=self.tackle_count, name="Tackle"))
        elif self.orb_active_count == 5:
            self.set_move(MonsterMove(MOVE_SEAR, MonsterIntent.ATTACK_DEBUFF, base_damage=self.sear_dmg, name="Sear"))
        elif self.orb_active_count == 6:
            self.set_move(MonsterMove(MOVE_INFERNO, MonsterIntent.ATTACK, base_damage=self.inferno_dmg, is_multi_damage=True, multiplier=self.inferno_hits, name="Inferno"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move

        from sts_py.engine.content.card_instance import CardInstance

        if move.intent == MonsterIntent.UNKNOWN:
            self.orb_active_count = 0
        elif move.intent == MonsterIntent.ATTACK_DEBUFF:
            damage = self.get_intent_damage()
            player.take_damage(damage)
            for _ in range(self.burn_count):
                burn_card = CardInstance(card_id="Burn", upgraded=self.burn_upgraded)
                self.state.card_manager.discard_pile.add(burn_card)
            self.orb_active_count += 1
        elif move.intent == MonsterIntent.DEFEND_BUFF:
            self.gain_strength(self.str_amt)
            self.gain_block(self.block_amt)
            self.orb_active_count += 1
        elif move.intent.is_attack():
            damage = self.get_intent_damage()
            hits = max(1, int(getattr(move, "multiplier", 0) or 1))
            for _ in range(hits):
                player.take_damage(damage)
            if hits >= self.inferno_hits:
                for _ in range(3):
                    burn_card = CardInstance(card_id="Burn", upgraded=False)
                    self.state.card_manager.discard_pile.add(burn_card)
                for card in self.state.card_manager.discard_pile.cards:
                    if card.card_id == "Burn" and not card.upgraded:
                        card.upgrade()
                for card in self.state.card_manager.draw_pile.cards:
                    if card.card_id == "Burn" and not card.upgraded:
                        card.upgrade()
                for card in self.state.card_manager.hand.cards:
                    if card.card_id == "Burn" and not card.upgraded:
                        card.upgrade()
                self.burn_upgraded = True
                self.orb_active_count = 0
            else:
                self.orb_active_count += 1


@dataclass
class FungiBeast(MonsterBase):
    bite_dmg: int = 6
    grow_str: int = 3

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "FungiBeast":
        hp = hp_rng.random_int_between(22, 28)
        return cls(
            id="FungiBeast",
            name="Fungi Beast",
            hp=hp,
            max_hp=hp,
            bite_dmg=6,
            grow_str=3,
        )

    def get_move(self, roll: int) -> None:
        MOVE_BITE = 1
        MOVE_GROW = 2

        if roll < 60:
            if self.last_two_moves(MOVE_BITE):
                self.set_move(MonsterMove(MOVE_GROW, MonsterIntent.BUFF, name="Grow"))
            else:
                self.set_move(MonsterMove(MOVE_BITE, MonsterIntent.ATTACK, self.bite_dmg))
        else:
            if self.last_move(MOVE_GROW):
                self.set_move(MonsterMove(MOVE_BITE, MonsterIntent.ATTACK, self.bite_dmg))
            else:
                self.set_move(MonsterMove(MOVE_GROW, MonsterIntent.BUFF, name="Grow"))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.move_id == 1:  # Bite
            damage = self.get_intent_damage()
            player.take_damage(damage)
        elif move.move_id == 2:  # Grow
            self.gain_strength(self.grow_str)


@dataclass
class LouseDefensive(MonsterBase):
    bite_damage: int = 5
    curl_up: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "LouseDefensive":
        hp = hp_rng.random_int_between(10, 15)
        bite_damage = hp_rng.random_int_between(5, 7)
        curl_up = hp_rng.random_int_between(3, 7)

        louse = cls(
            id="LouseDefensive",
            name="Louse",
            hp=hp,
            max_hp=hp,
            bite_damage=bite_damage,
            curl_up=curl_up,
        )
        louse.add_power(CurlUpPower(amount=curl_up, owner="monster_0"))
        return louse

    def get_move(self, roll: int) -> None:
        MOVE_BITE = 3
        MOVE_SPIT_WEB = 4

        if roll < 25:
            if self.last_two_moves(MOVE_SPIT_WEB):
                self.set_move(MonsterMove(MOVE_BITE, MonsterIntent.ATTACK, self.bite_damage))
            else:
                self.set_move(MonsterMove(MOVE_SPIT_WEB, MonsterIntent.DEBUFF, name="Spit Web"))
        elif self.last_two_moves(MOVE_BITE):
            self.set_move(MonsterMove(MOVE_SPIT_WEB, MonsterIntent.DEBUFF, name="Spit Web"))
        else:
            self.set_move(MonsterMove(MOVE_BITE, MonsterIntent.ATTACK, self.bite_damage))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.intent.is_attack():  # Bite
            damage = self.get_intent_damage()
            player.take_damage(damage)
        elif move.intent.is_debuff():  # Spit Web — apply Weak to player
            from sts_py.engine.combat.powers import create_power
            player.add_power(create_power("Weak", 2, "player"))


@dataclass
class SlaverBlue(MonsterBase):
    stab_dmg: int = 9
    slash_dmg: int = 8

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "SlaverBlue":
        hp = hp_rng.random_int_between(46, 50)
        return cls(
            id="SlaverBlue",
            name="Blue Slaver",
            hp=hp,
            max_hp=hp,
            stab_dmg=9,
            slash_dmg=8,
        )

    def get_move(self, roll: int) -> None:
        MOVE_STAB = 1
        MOVE_SLASH = 2
        MOVE_RAKE = 3

        if self.first_move:
            self.first_move = False
            self.set_move(MonsterMove(MOVE_STAB, MonsterIntent.ATTACK, self.stab_dmg))
            return

        if roll < 40:
            if self.last_two_moves(MOVE_SLASH):
                self.set_move(MonsterMove(MOVE_STAB, MonsterIntent.ATTACK, self.stab_dmg))
            else:
                self.set_move(MonsterMove(MOVE_SLASH, MonsterIntent.ATTACK_DEBUFF, self.slash_dmg, name="Slash"))
        else:
            if self.last_move(MOVE_STAB):
                self.set_move(MonsterMove(MOVE_SLASH, MonsterIntent.ATTACK_DEBUFF, self.slash_dmg, name="Slash"))
            else:
                self.set_move(MonsterMove(MOVE_STAB, MonsterIntent.ATTACK, self.stab_dmg))

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move = self.next_move
        if move.move_id == 1:  # Stab
            damage = self.get_intent_damage()
            player.take_damage(damage)
        elif move.move_id == 2:  # Slash — attack + apply Weak
            damage = self.get_intent_damage()
            player.take_damage(damage)
            from sts_py.engine.combat.powers import create_power
            player.add_power(create_power("Weak", 1, "player"))


EXORDIUM_MONSTERS = {
    "Jaw Worm": JawWorm,
    "Louse": LouseRed,
    "LouseRed": LouseRed,
    "LouseGreen": LouseGreen,
    "Cultist": Cultist,
    "Red Slaver": SlaverRed,
    "Blue Slaver": SlaverBlue,
    "Fungi Beast": FungiBeast,
    "Gremlin Nob": GremlinNob,
    "Lagavulin": Lagavulin,
    "Sentry": Sentry,
}


def create_monster(monster_id: str, hp_rng: MutableRNG, ascension: int = 0, misc_rng: MutableRNG | None = None, **kwargs) -> MonsterBase | None:
    if monster_id == "Louse" and misc_rng is not None:
        if misc_rng.random_boolean():
            monster_id = "LouseRed"
        else:
            monster_id = "LouseGreen"
    monster_class = EXORDIUM_MONSTERS.get(monster_id)
    if monster_class is None:
        return None
    import inspect
    sig = inspect.signature(monster_class.create)
    valid_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return monster_class.create(hp_rng, ascension, **valid_kwargs)


@dataclass
class LouseNormal(LouseRed):
    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "LouseNormal":
        louse = super().create(hp_rng, ascension)
        louse.id = "FuzzyLouseNormal"
        louse.name = "Louse"
        return louse
