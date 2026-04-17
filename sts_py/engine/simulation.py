"""Complete run simulation with improved AI decisions"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sts_py.engine.run.run_engine import RunEngine, RoomType, RunPhase
from sts_py.engine.run.shop import ShopEngine
from sts_py.engine.combat.combat_log import CombatLogger, CombatLog


@dataclass
class SimulationResult:
    seed: str
    ascension: int
    final_floor: int
    victory: bool
    player_hp: int
    player_max_hp: int
    gold: int
    damage_dealt: int = 0
    damage_taken: int = 0
    floors_completed: int = 0
    combat_count: int = 0
    card_reward_count: int = 0
    event_count: int = 0
    shop_count: int = 0
    potion_used: int = 0
    errors: list[str] = field(default_factory=list)
    combat_logs: list[CombatLog] = field(default_factory=list)


CARD_PRIORITY = {
    "Strike": 1,
    "Defend": 2,
    "Bash": 3,
    "Cleave": 4,
    "Thunderclap": 5,
    "TwinStrike": 6,
    "Anger": 7,
    "ShrugItOff": 8,
    "Armaments": 9,
    "PommelStrike": 10,
    "IronWave": 11,
    "BodySlam": 12,
    "Clash": 13,
    "Clothesline": 14,
    "Headbutt": 15,
    "WildStrike": 16,
    "Flex": 17,
    "Havoc": 18,
    "TrueGrit": 19,
    "Warcry": 20,
    "HeavyBlade": 21,
    "PerfectedStrike": 22,
    "SwordBoomerang": 23,
    "Carnage": 24,
    "Bloodletting": 25,
    "Disarm": 26,
    "FlameBarrier": 27,
    "Inflame": 28,
    "Combust": 29,
    "Metallicize": 30,
    "DemonForm": 35,
    "Impervious": 32,
    "LimitBreak": 33,
    "Offering": 34,
}

ATTACK_CARDS = {
    "Strike", "Bash", "Cleave", "Thunderclap", "TwinStrike", "Anger",
    "PommelStrike", "IronWave", "BodySlam", "Clash", "Clothesline",
    "Headbutt", "WildStrike", "HeavyBlade", "PerfectedStrike", "SwordBoomerang",
    "Carnage",
}

DEFEND_CARDS = {
    "Defend", "ShrugItOff", "Armaments", "TrueGrit", "Flex", "Warcry", "FlameBarrier"
}

POWER_CARDS = {
    "Inflame", "Combust", "Metallicize", "DarkEmbrace", "Evolve", "FeelNoPain",
    "FireBreathing", "GhostlyArmor", "Rupture", "DemonForm", "Berserk", "Barricade",
    "Blur", "Bloodletting", "Disarm", "FlameBarrier", "Impervious", "LimitBreak",
    "Uppercut", "Offering", "SpotWeakness"
}


class ImprovedAI:
    """Improved AI with strategic thinking."""

    def __init__(self, engine: RunEngine):
        self.engine = engine
        self.potions_saved = {}
        self.next_elite_floor = None
        self.next_boss_floor = None
        self.buffs_active = 0
        self.current_logger: CombatLogger | None = None

    def _start_combat_log(self, floor: int, encounter: str) -> CombatLogger:
        """Start a new combat log for the current combat."""
        self.current_logger = CombatLogger(floor=floor, encounter=encounter)
        return self.current_logger

    def _analyze_map(self) -> None:
        """Analyze upcoming map to plan potion usage."""
        path = self.engine.state.path_taken
        current_floor = self.engine.state.floor

        self.next_elite_floor = None
        self.next_boss_floor = None

        for node in self.engine.state.map_nodes:
            if node.floor > current_floor:
                if node.room_type == RoomType.ELITE and self.next_elite_floor is None:
                    self.next_elite_floor = node.floor
                if node.room_type == RoomType.BOSS and self.next_boss_floor is None:
                    self.next_boss_floor = node.floor

    def _should_use_potion(self) -> bool:
        """Decide if should use a potion now."""
        hp = self.engine.state.player_hp
        max_hp = self.engine.state.player_max_hp
        hp_pct = hp / max_hp

        current_room = self.engine.get_current_room()
        if current_room and current_room.room_type in [RoomType.ELITE, RoomType.BOSS]:
            return hp_pct < 0.6

        if hp_pct < 0.4:
            return True

        if self.next_elite_floor and self.engine.state.floor + 2 >= self.next_elite_floor:
            if hp_pct < 0.5:
                return True

        if self.next_boss_floor and self.engine.state.floor + 3 >= self.next_boss_floor:
            if hp_pct < 0.5:
                return True

        return False

    def _use_potion_if_needed(self) -> bool:
        """Use a potion if it makes sense."""
        if not self._should_use_potion():
            return False

        potions = self.engine.state.potions
        if not potions:
            return False

        hp_pct = self.engine.state.player_hp / self.engine.state.player_max_hp

        for i, potion in enumerate(potions):
            if "Healing" in potion or "Fire" in potion or "Regen" in potion:
                if hp_pct < 0.6:
                    self.engine.use_potion(i)
                    return True

        if hp_pct < 0.3 and potions:
            self.engine.use_potion(0)
            return True

        return False

    def choose_path(self) -> bool:
        """Choose best path considering long-term strategy."""
        available = self.engine.get_available_paths()
        if not available:
            return False

        self._analyze_map()

        monster_rooms = [n for n in available if n.room_type == RoomType.MONSTER]
        elite_rooms = [n for n in available if n.room_type == RoomType.ELITE]
        rest_rooms = [n for n in available if n.room_type == RoomType.REST]
        shop_rooms = [n for n in available if n.room_type == RoomType.SHOP]
        event_rooms = [n for n in available if n.room_type == RoomType.EVENT]
        boss_rooms = [n for n in available if n.room_type == RoomType.BOSS]

        current_hp_pct = self.engine.state.player_hp / self.engine.state.player_max_hp
        current_floor = self.engine.state.floor
        choice = None

        if boss_rooms and current_floor >= 14:
            choice = boss_rooms[0]
        if choice is None and not getattr(self.engine.state, "emerald_key_obtained", False):
            burning_elites = [n for n in elite_rooms if getattr(n, "burning_elite", False)]
            if burning_elites and current_hp_pct > 0.45:
                choice = burning_elites[0]
        if choice is None and current_hp_pct < 0.25 and rest_rooms:
            choice = rest_rooms[0]
        elif choice is None and current_hp_pct < 0.5 and rest_rooms and current_floor < 10:
            choice = rest_rooms[0]
        elif choice is None and shop_rooms and current_floor in [6, 7, 8]:
            choice = shop_rooms[0]
        elif choice is None and elite_rooms and current_floor > 5 and current_hp_pct > 0.5:
            choice = elite_rooms[0]
        elif choice is None and monster_rooms:
            choice = monster_rooms[0]
        elif choice is None and event_rooms:
            choice = event_rooms[0]
        elif choice is None and rest_rooms:
            choice = rest_rooms[0]
        elif choice is None and shop_rooms:
            choice = shop_rooms[0]
        elif choice is None and elite_rooms:
            choice = elite_rooms[0]
        elif choice is None:
            choice = available[0]

        return self.engine.choose_path(choice.node_id)

    def _get_enemy_intent_danger(self, combat) -> int:
        """Calculate danger of enemy intents."""
        danger = 0
        for monster in combat.state.monsters:
            if monster.is_dead():
                continue
            if monster.next_move and monster.next_move.intent.is_attack():
                base_damage = monster.get_intent_damage()
                modified_damage = combat.state.player.powers.apply_damage_receive_modifiers(float(base_damage), "NORMAL")
                final_damage = int(modified_damage)
                danger += final_damage
        return danger

    def _select_target(self, combat) -> int:
        """Select best target for attacks considering HP and threat."""
        monsters = combat.state.monsters
        if len(monsters) == 1:
            return 0

        best_score = -float('inf')
        target_idx = 0
        
        for i, m in enumerate(monsters):
            if m.is_dead():
                continue
                
            score = -m.hp * 0.1
            
            if m.next_move and m.next_move.intent.is_attack():
                damage = m.get_intent_damage()
                modified = combat.state.player.powers.apply_damage_receive_modifiers(float(damage), "NORMAL")
                score += int(modified) * 2
                
            if hasattr(m, 'vulnerable') and m.vulnerable > 0:
                score += 5
                
            if score > best_score:
                best_score = score
                target_idx = i
                
        return target_idx

    def _get_player_strength(self, combat) -> int:
        """Get player's effective strength."""
        strength = combat.state.player.strength
        strength_power = combat.state.player.powers.get_power_amount("Strength")
        return strength + strength_power

    def _resolve_pending_end_turn_choices(self) -> None:
        combat = self.engine.state.combat
        if combat is None:
            return
        while combat.state.pending_combat_choice is not None:
            pending = combat.state.pending_combat_choice
            if str(pending.get("selection_action", "")) != "retain_for_end_turn":
                break
            choices = self.engine.get_combat_choices()
            if not choices:
                break
            pick_index = next(
                (index for index, choice in enumerate(choices) if choice.get("action") not in {"complete", "skip"}),
                None,
            )
            if pick_index is None:
                pick_index = next(
                    (index for index, choice in enumerate(choices) if choice.get("action") == "complete"),
                    0,
                )
            self.engine.choose_combat_option(pick_index)

    def execute_combat(self) -> bool:
        """Execute combat with improved strategy."""
        if self.engine.state.combat is None:
            return False

        self._use_potion_if_needed()

        combat = self.engine.state.combat
        max_turns = 50
        turn = 0

        logger = self._start_combat_log(self.engine.state.floor, str(combat.state.monsters[0].id) if combat.state.monsters else "Unknown")
        logger.log_combat_start(combat)

        while turn < max_turns and not combat.is_combat_over():
            turn += 1
            energy = 3
            player_strength = self._get_player_strength(combat)

            logger.log_turn_start(combat, turn)

            while energy > 0:
                hand = combat.state.card_manager.get_hand() if combat.state.card_manager else []
                if not hand:
                    break

                best_card_played = False
                best_card_idx = -1
                best_score = -1

                for card_idx, card in enumerate(hand):
                    card_name = card.card_id

                    base_name = card_name.replace("_R", "").replace("_U", "").replace("_B", "")

                    score = 0
                    card_energy = getattr(card, 'cost', 1)
                    if card_energy > energy:
                        continue

                    if base_name in ATTACK_CARDS:
                        score = 50
                        if hasattr(card, 'damage'):
                            base_damage = card.damage
                            if player_strength > 0:
                                base_damage += player_strength
                            score += base_damage * 2
                        enemy_hp = sum(m.hp for m in combat.state.monsters if m.hp > 0)
                        if enemy_hp <= getattr(card, 'damage', 6) + player_strength:
                            score += 100
                    elif base_name in DEFEND_CARDS:
                        intent_danger = self._get_enemy_intent_danger(combat)
                        score = 30
                        if intent_danger > 10:
                            score += intent_danger * 2
                        if hasattr(card, 'block'):
                            score += card.block
                    elif base_name in POWER_CARDS:
                        power_on_stack = combat.state.player.powers.get_power_amount(base_name.replace(" ", ""))
                        if base_name == "Inflame" and not combat.state.player.powers.has_power("Strength"):
                            score = 80
                        elif base_name == "Metallicize" and not combat.state.player.powers.has_power("Thorns"):
                            score = 45
                        elif base_name == "DemonForm":
                            score = 70 if self.buffs_active == 0 else 40
                        elif base_name == "Combust" or base_name == "FireBreathing":
                            score = 50
                        elif power_on_stack > 0:
                            score = 10
                        else:
                            score = 35
                        self.buffs_active += 1
                    else:
                        score = 5

                    if base_name in CARD_PRIORITY:
                        score += CARD_PRIORITY.get(base_name, 0)

                    if score > best_score:
                        best_score = score
                        best_card_idx = card_idx

                if best_card_idx >= 0:
                    target = self._select_target(combat)
                    card_played = hand[best_card_idx]
                    success = self.engine.combat_play_card(best_card_idx, target)
                    logger.log_card_played(card_played.card_id, best_card_idx, target, getattr(card_played, 'cost', 1), success)
                    if success:
                        energy -= 1
                        best_card_played = True
                    else:
                        break
                else:
                    break

                if not best_card_played:
                    break

            logger.log_turn_end(turn)
            self.engine.combat_end_turn()
            self._resolve_pending_end_turn_choices()

        victory = combat.player_won()
        logger.log_combat_end(victory, turn, combat.state.player.hp)

        self.engine.end_combat()
        return True

    def execute_rest(self) -> bool:
        """Execute rest: heal if low HP, else smith high-priority cards."""
        current_hp = self.engine.state.player_hp
        max_hp = self.engine.state.player_max_hp

        if not getattr(self.engine.state, "ruby_key_obtained", False) and current_hp >= max_hp * 0.5:
            if self.engine.recall():
                return True

        if current_hp < max_hp * 0.5:
            self.engine.rest()
            return True
            
        upgradable = [(i, c) for i, c in enumerate(self.engine.state.deck) if not c.endswith("+")]
        if not upgradable:
            if current_hp < max_hp:
                self.engine.rest()
            else:
                self.engine.state.phase = RunPhase.MAP
            return True
            
        priority_map = {
            "DemonForm": 100,
            "SpotWeakness": 90,
            "BodySlam": 80,
            "Bash": 70,
            "Uppercut": 65,
            "PommelStrike": 60,
            "TrueGrit": 60,
            "Armaments": 55,
            "ShrugItOff": 50,
            "FlameBarrier": 50,
            "Strike": -10,
            "Defend": -10,
        }
        
        best_idx = upgradable[0][0]
        best_score = -9999
        
        for idx, card in upgradable:
            score = priority_map.get(card, 0)
            if score > best_score:
                best_score = score
                best_idx = idx
                
        self.engine.smith(best_idx)
        return True

    def execute_treasure(self) -> bool:
        """Choose Sapphire Key first, otherwise take the relic."""
        if self.engine.state.phase != RunPhase.TREASURE:
            return False
        acted = False
        while self.engine.state.phase == RunPhase.TREASURE:
            if (
                not getattr(self.engine.state, "sapphire_key_obtained", False)
                and getattr(self.engine.state, "pending_treasure_relic", None)
            ):
                result = self.engine.take_sapphire_key()
                if result.get("success"):
                    acted = True
                    continue
            pending_relics = list(getattr(self.engine.state, "pending_chest_relic_choices", []) or [])
            if not pending_relics:
                break
            result = self.engine.take_treasure_relic(0)
            if not result.get("success"):
                return acted
            acted = True
        return acted

    def choose_boss_relic(self) -> bool:
        """Pick the first available boss relic choice deterministically."""
        if self.engine.state.phase != RunPhase.VICTORY:
            return False
        choices = list(getattr(self.engine.state, "pending_boss_relic_choices", []) or [])
        if not choices:
            return False
        result = self.engine.choose_boss_relic(0)
        return bool(result.get("success"))

    def choose_card_reward(self) -> bool:
        """Choose best card reward with long-term thinking."""
        if self.engine.state.phase != RunPhase.REWARD:
            return False

        preferred_cards = [
            "Cleave", "Thunderclap", "ShrugItOff", "Armaments",
            "PommelStrike", "TwinStrike", "IronWave", "BodySlam",
            "Inflame", "Combust", "FlameBarrier", "Disarm"
        ]

        best_card = None
        best_score = -1

        pending_cards = list(getattr(self.engine.state, "pending_card_reward_cards", []) or [])
        if pending_cards:
            for card in pending_cards:
                base_name = card.replace("_R", "").replace("_U", "").replace("_B", "")
                score = 0

                if base_name in preferred_cards:
                    score += 10
                if base_name in ATTACK_CARDS:
                    score += 5
                if base_name in DEFEND_CARDS:
                    score += 3
                if base_name in POWER_CARDS:
                    score += 8

                if score > best_score:
                    best_score = score
                    best_card = card

        if best_card:
            self.engine.choose_card_reward(best_card, [], upgraded=best_card.endswith("+"))
        elif pending_cards:
            self.engine.choose_card_reward(pending_cards[0], pending_cards[1:], upgraded=pending_cards[0].endswith("+"))
        else:
            self.engine.clear_pending_reward_notifications()

        return True

    def execute_shop(self) -> bool:
        """Execute shop with smart purchasing."""
        shop_engine = self.engine.get_shop()
        if shop_engine is None:
            return False
        gold = self.engine.state.player_gold

        hp_pct = self.engine.state.player_hp / self.engine.state.player_max_hp
        if hp_pct < 0.5:
            for relic in shop_engine.get_available_relics():
                if "Fire" in relic["relic_id"] or "Healing" in relic["relic_id"]:
                    if relic["price"] <= gold * 0.3:
                        i = int(relic["index"])
                        shop_engine.buy_relic(i)
                        gold -= relic["price"]
                        break

        attack_count = sum(1 for c in self.engine.state.deck if any(a in c for a in ATTACK_CARDS))
        defend_count = sum(1 for c in self.engine.state.deck if any(d in c for d in DEFEND_CARDS))
        available_cards = shop_engine.get_available_cards()

        if defend_count < attack_count:
            for card in available_cards:
                base_name = card["card_id"].replace("_R", "").replace("_U", "").replace("_B", "")
                if base_name in DEFEND_CARDS and card["price"] <= gold * 0.4:
                    shop_engine.buy_card(int(card["index"]), is_colored=bool(card.get("is_colored", True)))
                    gold -= card["price"]
                    break
        else:
            for card in available_cards:
                base_name = card["card_id"].replace("_R", "").replace("_U", "").replace("_B", "")
                if base_name in ATTACK_CARDS and card["price"] <= gold * 0.4:
                    shop_engine.buy_card(int(card["index"]), is_colored=bool(card.get("is_colored", True)))
                    gold -= card["price"]
                    break

        if gold > 100:
            for relic in shop_engine.get_available_relics():
                if relic["price"] <= gold * 0.5:
                    i = int(relic["index"])
                    shop_engine.buy_relic(i)
                    gold -= relic["price"]
                    break

        self.engine.leave_shop()
        return True

    def choose_event_option(self) -> bool:
        """Choose best event option."""
        choices = self.engine.get_event_choices()
        if not choices:
            self.engine.choose_event_option(0)
            return True

        event = self.engine._current_event
        if event and event.id == "NeowEvent":
            for i, choice in enumerate(choices):
                desc = choice.description.upper()
                if "BONUS" in desc or "MAX HP" in desc or "CARD" in desc:
                    self.engine.choose_event_option(i)
                    return True

        self.engine.choose_event_option(0)
        return True

    def execute_neow(self) -> bool:
        """Resolve the startup Neow phase deterministically for non-interactive flows."""
        if self.engine.state.phase != RunPhase.NEOW:
            return False

        acted = False
        while self.engine.state.phase == RunPhase.NEOW:
            pending_cards = self.engine.get_neow_choice_cards()
            if pending_cards:
                result = self.engine.choose_card_for_neow(0)
            else:
                options = self.engine.get_neow_options()
                if not options:
                    self.engine.state.phase = RunPhase.MAP
                    return True
                result = self.engine.choose_neow_option(0)
            if not result.get("success"):
                return acted
            acted = True
        return acted


def simulate_run(
    seed: str,
    ascension: int = 0,
    max_floors: int = 100,
    verbose: bool = False
) -> SimulationResult:
    """Simulate a complete run with improved AI."""
    engine = RunEngine.create(seed, ascension=ascension)
    ai = ImprovedAI(engine)
    result = SimulationResult(
        seed=seed,
        ascension=ascension,
        final_floor=0,
        victory=False,
        player_hp=engine.state.player_hp,
        player_max_hp=engine.state.player_max_hp,
        gold=engine.state.player_gold
    )

    if verbose:
        print(f"Starting run: seed={seed}, ascension={ascension}")
        print(f"Initial HP: {engine.state.player_hp}/{engine.state.player_max_hp}")

    while result.floors_completed < max_floors:
        if engine.state.phase == RunPhase.GAME_OVER:
            if verbose:
                print(f"Game Over at floor {engine.state.floor}")
            break

        if engine.state.phase == RunPhase.VICTORY:
            if _is_final_victory(engine):
                if verbose:
                    print(f"Victory at floor {engine.state.floor}!")
                result.victory = True
                break
            if getattr(engine.state, "pending_boss_relic_choices", []):
                ai.choose_boss_relic()
                continue
            engine.transition_to_next_act()
            continue

        if engine.state.phase == RunPhase.NEOW:
            ai.execute_neow()
            continue

        current_room = engine.get_current_room()

        if current_room is None:
            ai.choose_path()

        elif engine.state.phase == RunPhase.MAP:
            ai.choose_path()

        elif engine.state.phase == RunPhase.COMBAT:
            try:
                ai.execute_combat()
                result.combat_count += 1
                if ai.current_logger is not None:
                    result.combat_logs.append(ai.current_logger.get_log())
            except Exception as e:
                result.errors.append(f"Combat error at floor {engine.state.floor}: {e}")
                break

        elif engine.state.phase == RunPhase.REST:
            ai.execute_rest()

        elif engine.state.phase == RunPhase.TREASURE:
            ai.execute_treasure()

        elif engine.state.phase == RunPhase.REWARD:
            ai.choose_card_reward()
            result.card_reward_count += 1

        elif engine.state.phase == RunPhase.EVENT:
            ai.choose_event_option()
            result.event_count += 1

        elif engine.state.phase == RunPhase.SHOP:
            ai.execute_shop()
            result.shop_count += 1

        result.final_floor = engine.state.floor
        result.player_hp = engine.state.player_hp
        result.gold = engine.state.player_gold
        result.damage_taken = result.player_max_hp - result.player_hp

        if verbose and result.final_floor % 3 == 0:
            print(f"Floor {result.final_floor}: HP={engine.state.player_hp}/{engine.state.player_max_hp}, Gold={engine.state.player_gold}")

    result.floors_completed = result.final_floor
    return result


if __name__ == "__main__":
    result = simulate_run("LOG_TEST", verbose=True, enable_combat_logs=True)
    print(f"\n=== Run Complete ===")
    print(f"Seed: {result.seed}")
    print(f"Final Floor: {result.final_floor}")
    print(f"Victory: {result.victory}")
    print(f"HP: {result.player_hp}/{result.player_max_hp}")
    print(f"Combats: {result.combat_count}")
    print(f"Errors: {result.errors}")

    if result.combat_logs:
        print(f"\n{'='*70}")
        print("战斗日志详情")
        print(f"{'='*70}")
        for i, log in enumerate(result.combat_logs):
            print(log.format_summary())
            print()


def simulate_run_with_logs(
    seed: str,
    ascension: int = 0,
    max_floors: int = 100,
    verbose: bool = False,
    enable_combat_logs: bool = False
) -> SimulationResult:
    """Simulate a run with optional detailed combat logs."""
    engine = RunEngine.create(seed, ascension=ascension)
    ai = ImprovedAI(engine)
    result = SimulationResult(
        seed=seed,
        ascension=ascension,
        final_floor=0,
        victory=False,
        player_hp=engine.state.player_hp,
        player_max_hp=engine.state.player_max_hp,
        gold=engine.state.player_gold
    )

    if verbose:
        print(f"Starting run: seed={seed}, ascension={ascension}")
        print(f"Initial HP: {engine.state.player_hp}/{engine.state.player_max_hp}")

    while result.floors_completed < max_floors:
        if engine.state.phase == RunPhase.GAME_OVER:
            if verbose:
                print(f"Game Over at floor {engine.state.floor}")
            break

        if engine.state.phase == RunPhase.VICTORY:
            if _is_final_victory(engine):
                if verbose:
                    print(f"Victory at floor {engine.state.floor}!")
                result.victory = True
                break
            if getattr(engine.state, "pending_boss_relic_choices", []):
                ai.choose_boss_relic()
                continue
            engine.transition_to_next_act()
            continue

        if engine.state.phase == RunPhase.NEOW:
            ai.execute_neow()
            continue

        current_room = engine.get_current_room()

        if current_room is None:
            ai.choose_path()

        elif engine.state.phase == RunPhase.MAP:
            ai.choose_path()

        elif engine.state.phase == RunPhase.COMBAT:
            try:
                ai.execute_combat()
                result.combat_count += 1
                if enable_combat_logs and ai.current_logger is not None:
                    result.combat_logs.append(ai.current_logger.get_log())
            except Exception as e:
                result.errors.append(f"Combat error at floor {engine.state.floor}: {e}")
                break

        elif engine.state.phase == RunPhase.REST:
            ai.execute_rest()

        elif engine.state.phase == RunPhase.TREASURE:
            ai.execute_treasure()

        elif engine.state.phase == RunPhase.REWARD:
            ai.choose_card_reward()
            result.card_reward_count += 1

        elif engine.state.phase == RunPhase.EVENT:
            ai.choose_event_option()
            result.event_count += 1

        elif engine.state.phase == RunPhase.SHOP:
            ai.execute_shop()
            result.shop_count += 1

        result.final_floor = engine.state.floor
        result.player_hp = engine.state.player_hp
        result.gold = engine.state.player_gold
        result.damage_taken = result.player_max_hp - result.player_hp

        if verbose and result.final_floor % 3 == 0:
            print(f"Floor {result.final_floor}: HP={engine.state.player_hp}/{engine.state.player_max_hp}, Gold={engine.state.player_gold}")

    result.floors_completed = result.final_floor
    return result


def _is_final_victory(engine: RunEngine) -> bool:
    if engine.state.act >= 4:
        return True
    if engine.state.act == 3 and not engine.has_all_act4_keys():
        return True
    return False
