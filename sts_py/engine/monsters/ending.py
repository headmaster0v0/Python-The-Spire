from __future__ import annotations

from dataclasses import dataclass

from sts_py.engine.combat.powers import create_power
from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.monster_base import MonsterBase, MonsterMove


def _consume_player_artifact(player) -> bool:
    if not hasattr(player, "powers") or not player.powers.has_power("Artifact"):
        return False
    player.powers.reduce_power("Artifact", 1)
    return True


def _apply_player_debuff(player, power_id: str, amount: int) -> bool:
    if amount <= 0:
        return False
    if _consume_player_artifact(player):
        return False
    player.add_power(create_power(power_id, amount, "player"))
    if power_id == "Strength":
        player.strength += amount
    elif power_id == "Focus":
        player.focus += amount
    return True


def _add_status_to_discard(monster: MonsterBase, card_id: str, count: int) -> None:
    combat_state = getattr(monster, "_combat_state", None) or getattr(monster, "state", None)
    card_manager = getattr(combat_state, "card_manager", None)
    if card_manager is None:
        return
    for _ in range(max(0, int(count))):
        card_manager.discard_pile.add(CardInstance(card_id=card_id))


def _add_status_to_draw_pile(monster: MonsterBase, card_id: str, count: int) -> None:
    combat_state = getattr(monster, "_combat_state", None) or getattr(monster, "state", None)
    card_manager = getattr(combat_state, "card_manager", None)
    if card_manager is None:
        return
    for _ in range(max(0, int(count))):
        card_manager.draw_pile.add(CardInstance(card_id=card_id))
    if card_manager.rng is not None:
        card_manager.draw_pile.shuffle(card_manager.rng)


def _clear_surrounded(monster: MonsterBase) -> None:
    combat_state = getattr(monster, "_combat_state", None) or getattr(monster, "state", None)
    player = getattr(combat_state, "player", None)
    monsters = getattr(combat_state, "monsters", []) if combat_state is not None else []
    if player is not None and hasattr(player, "powers") and player.powers.has_power("Surrounded"):
        player.powers.remove_power("Surrounded")
    for other in monsters:
        if other is monster or other.is_dead():
            continue
        if other.has_power("BackAttack"):
            other.powers.remove_power("BackAttack")


@dataclass
class SpireShield(MonsterBase):
    bash_dmg: int = 12
    smash_dmg: int = 34
    move_count: int = 0
    ascension: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "SpireShield":
        hp = 125 if ascension >= 8 else 110
        return cls(
            id="SpireShield",
            name="Spire Shield",
            hp=hp,
            max_hp=hp,
            bash_dmg=14 if ascension >= 3 else 12,
            smash_dmg=38 if ascension >= 3 else 34,
            ascension=ascension,
        )

    def use_pre_battle_action(self) -> None:
        combat_state = getattr(self, "state", None)
        player = getattr(combat_state, "player", None)
        if player is not None:
            player.add_power(create_power("Surrounded", -1, "player"))
        self.add_power(create_power("Artifact", 2 if self.ascension >= 18 else 1, self.id))

    def get_move(self, roll: int) -> None:
        move_id = self.move_count % 3
        if move_id == 0:
            if self.ai_rng is not None and self.ai_rng.random_boolean():
                self.set_move(MonsterMove(2, MonsterIntent.DEFEND, name="Fortify"))
            else:
                self.set_move(MonsterMove(1, MonsterIntent.ATTACK_DEBUFF, self.bash_dmg, name="Bash"))
        elif move_id == 1:
            if not self.last_move(1):
                self.set_move(MonsterMove(1, MonsterIntent.ATTACK_DEBUFF, self.bash_dmg, name="Bash"))
            else:
                self.set_move(MonsterMove(2, MonsterIntent.DEFEND, name="Fortify"))
        else:
            self.set_move(MonsterMove(3, MonsterIntent.ATTACK_DEFEND, self.smash_dmg, name="Smash"))
        self.move_count += 1

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move_id = int(getattr(self.next_move, "move_id", -1) or -1)
        if move_id == 1:
            player.take_damage(self.get_intent_damage(), source_owner=self)
            if hasattr(player, "orbs") and getattr(player.orbs, "slots", []):
                if self.ai_rng is not None and self.ai_rng.random_boolean():
                    _apply_player_debuff(player, "Focus", -1)
                else:
                    _apply_player_debuff(player, "Strength", -1)
            else:
                _apply_player_debuff(player, "Strength", -1)
        elif move_id == 2:
            combat_state = getattr(self, "_combat_state", None) or getattr(self, "state", None)
            for monster in getattr(combat_state, "monsters", []) if combat_state is not None else []:
                if not monster.is_dead():
                    monster.gain_block(30)
        elif move_id == 3:
            player.take_damage(self.get_intent_damage(), source_owner=self)
            if self.ascension >= 18:
                self.gain_block(99)
            else:
                self.gain_block(max(0, self.get_intent_damage()))

    def on_death(self) -> None:
        _clear_surrounded(self)


@dataclass
class SpireSpear(MonsterBase):
    burn_strike_dmg: int = 5
    skewer_dmg: int = 10
    skewer_count: int = 3
    move_count: int = 0
    ascension: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "SpireSpear":
        hp = 180 if ascension >= 8 else 160
        return cls(
            id="SpireSpear",
            name="Spire Spear",
            hp=hp,
            max_hp=hp,
            burn_strike_dmg=6 if ascension >= 3 else 5,
            skewer_dmg=10,
            skewer_count=4 if ascension >= 3 else 3,
            ascension=ascension,
        )

    def use_pre_battle_action(self) -> None:
        self.add_power(create_power("Artifact", 2 if self.ascension >= 18 else 1, self.id))

    def get_move(self, roll: int) -> None:
        move_id = self.move_count % 3
        if move_id == 0:
            if not self.last_move(1):
                self.set_move(MonsterMove(1, MonsterIntent.ATTACK_DEBUFF, self.burn_strike_dmg, multiplier=2, is_multi_damage=True, name="Burn Strike"))
            else:
                self.set_move(MonsterMove(2, MonsterIntent.BUFF, name="Piercer"))
        elif move_id == 1:
            self.set_move(MonsterMove(3, MonsterIntent.ATTACK, self.skewer_dmg, multiplier=self.skewer_count, is_multi_damage=True, name="Skewer"))
        else:
            if self.ai_rng is not None and self.ai_rng.random_boolean():
                self.set_move(MonsterMove(2, MonsterIntent.BUFF, name="Piercer"))
            else:
                self.set_move(MonsterMove(1, MonsterIntent.ATTACK_DEBUFF, self.burn_strike_dmg, multiplier=2, is_multi_damage=True, name="Burn Strike"))
        self.move_count += 1

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move_id = int(getattr(self.next_move, "move_id", -1) or -1)
        if move_id == 1:
            for _ in range(2):
                player.take_damage(self.get_intent_damage(), source_owner=self)
            if self.ascension >= 18:
                _add_status_to_draw_pile(self, "Burn", 2)
            else:
                _add_status_to_discard(self, "Burn", 2)
        elif move_id == 2:
            combat_state = getattr(self, "_combat_state", None) or getattr(self, "state", None)
            for monster in getattr(combat_state, "monsters", []) if combat_state is not None else []:
                if not monster.is_dead():
                    monster.gain_strength(2)
        elif move_id == 3:
            for _ in range(max(1, int(self.skewer_count))):
                player.take_damage(self.get_intent_damage(), source_owner=self)

    def on_death(self) -> None:
        _clear_surrounded(self)


@dataclass
class CorruptHeart(MonsterBase):
    echo_attack_dmg: int = 40
    blood_shot_dmg: int = 2
    blood_hit_count: int = 12
    is_first_move: bool = True
    move_count: int = 0
    buff_count: int = 0
    ascension: int = 0

    @classmethod
    def create(cls, hp_rng: MutableRNG, ascension: int = 0) -> "CorruptHeart":
        hp = 800 if ascension >= 9 else 750
        return cls(
            id="CorruptHeart",
            name="Corrupt Heart",
            hp=hp,
            max_hp=hp,
            echo_attack_dmg=45 if ascension >= 4 else 40,
            blood_shot_dmg=2,
            blood_hit_count=15 if ascension >= 4 else 12,
            ascension=ascension,
        )

    def use_pre_battle_action(self) -> None:
        invincible_amount = 200 if self.ascension >= 19 else 300
        beat_amount = 2 if self.ascension >= 19 else 1
        self.add_power(create_power("Invincible", invincible_amount, self.id))
        self.add_power(create_power("BeatOfDeath", beat_amount, self.id))

    def get_move(self, roll: int) -> None:
        if self.is_first_move:
            self.set_move(MonsterMove(3, MonsterIntent.STRONG_DEBUFF, name="Debilitate"))
            self.is_first_move = False
            return
        move_id = self.move_count % 3
        if move_id == 0:
            if self.ai_rng is not None and self.ai_rng.random_boolean():
                self.set_move(MonsterMove(1, MonsterIntent.ATTACK, self.blood_shot_dmg, multiplier=self.blood_hit_count, is_multi_damage=True, name="Blood Shots"))
            else:
                self.set_move(MonsterMove(2, MonsterIntent.ATTACK, self.echo_attack_dmg, name="Echo"))
        elif move_id == 1:
            if not self.last_move(2):
                self.set_move(MonsterMove(2, MonsterIntent.ATTACK, self.echo_attack_dmg, name="Echo"))
            else:
                self.set_move(MonsterMove(1, MonsterIntent.ATTACK, self.blood_shot_dmg, multiplier=self.blood_hit_count, is_multi_damage=True, name="Blood Shots"))
        else:
            self.set_move(MonsterMove(4, MonsterIntent.BUFF, name="Buff"))
        self.move_count += 1

    def take_damage(self, amount: int) -> int:
        invincible = self.powers.get_power("Invincible")
        if invincible is not None:
            damage = max(0, min(int(amount), int(getattr(invincible, "amount", 0) or 0)))
            invincible.amount = max(0, int(getattr(invincible, "amount", 0) or 0) - damage)
            return super().take_damage(damage)
        return super().take_damage(amount)

    def take_turn(self, player) -> None:
        if self.next_move is None:
            return
        move_id = int(getattr(self.next_move, "move_id", -1) or -1)
        if move_id == 3:
            _apply_player_debuff(player, "Vulnerable", 2)
            _apply_player_debuff(player, "Weak", 2)
            _apply_player_debuff(player, "Frail", 2)
            _add_status_to_draw_pile(self, "Dazed", 1)
            _add_status_to_draw_pile(self, "Slimed", 1)
            _add_status_to_draw_pile(self, "Wound", 1)
            _add_status_to_draw_pile(self, "Burn", 1)
            _add_status_to_draw_pile(self, "Void", 1)
            return
        if move_id == 4:
            current_negative_strength = min(0, int(self.powers.get_power_amount("Strength") or 0))
            self.gain_strength(abs(current_negative_strength) + 2)
            if self.buff_count == 0:
                self.add_power(create_power("Artifact", 2, self.id))
            elif self.buff_count == 1:
                self.add_power(create_power("BeatOfDeath", 1, self.id))
            elif self.buff_count == 2:
                self.add_power(create_power("Painful Stabs", -1, self.id))
            elif self.buff_count == 3:
                self.gain_strength(10)
            else:
                self.gain_strength(50)
            self.buff_count += 1
            return
        if move_id == 1:
            for _ in range(max(1, int(self.blood_hit_count))):
                player.take_damage(self.blood_shot_dmg + max(0, self.get_effective_strength()), source_owner=self)
            return
        if move_id == 2:
            player.take_damage(self.get_intent_damage(), source_owner=self)
