"""Card pile management for Slay The Spire combat.

This module implements the card pile system:
- Draw pile: Cards available to draw
- Hand: Cards currently in hand
- Discard pile: Cards that have been played or exhausted
- Exhaust pile: Cards that are exhausted (removed from combat)

Key concepts from Java:
- CardGroup class manages each pile
- Cards can be moved between piles
- Shuffle uses cardRng
- Exhaust moves cards to exhaust pile
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.content.card_instance import CardInstance

MAX_HAND_SIZE = 10


_SCRY_KEEP_CARD_IDS = {
    "Weave",
    "Eruption",
    "Vigilance",
    "Wallop",
    "Prostrate",
    "Devotion",
    "ThirdEye",
    "CutThroughFate",
}

_RECOVER_KEEP_CARD_IDS = {
    "Weave",
    "Eruption",
    "Vigilance",
    "Wallop",
    "Prostrate",
    "Devotion",
    "ThirdEye",
    "CutThroughFate",
    "Meditate",
    "InnerPeace",
}


@dataclass
class CardPile:
    cards: list[CardInstance] = field(default_factory=list)

    def add(self, card: CardInstance) -> None:
        self.cards.append(card)

    def add_multiple(self, cards: list[CardInstance]) -> None:
        self.cards.extend(cards)

    def remove(self, card: CardInstance) -> bool:
        if card in self.cards:
            self.cards.remove(card)
            return True
        return False

    def pop(self, index: int = -1) -> CardInstance | None:
        if not self.cards:
            return None
        return self.cards.pop(index)

    def peek(self, index: int = 0) -> CardInstance | None:
        if index >= len(self.cards):
            return None
        return self.cards[index]

    def size(self) -> int:
        return len(self.cards)

    def is_empty(self) -> bool:
        return len(self.cards) == 0

    def clear(self) -> None:
        self.cards.clear()

    def shuffle(self, rng: MutableRNG) -> None:
        for i in range(len(self.cards) - 1, 0, -1):
            j = rng.random_int(i)
            self.cards[i], self.cards[j] = self.cards[j], self.cards[i]

    def to_list(self) -> list[CardInstance]:
        return self.cards.copy()

    @classmethod
    def from_list(cls, cards: list[str] | list[CardInstance]) -> "CardPile":
        instances: list[CardInstance] = []
        for card in cards:
            if isinstance(card, CardInstance):
                instances.append(card)
            else:
                instances.append(CardInstance(card_id=card))
        return cls(cards=instances)


@dataclass
class CardManager:
    draw_pile: CardPile = field(default_factory=CardPile)
    hand: CardPile = field(default_factory=CardPile)
    discard_pile: CardPile = field(default_factory=CardPile)
    exhaust_pile: CardPile = field(default_factory=CardPile)
    limbo_pile: CardPile = field(default_factory=CardPile)

    _cards_drawn_this_turn: int = 0
    _energy: int = 3
    _max_energy: int = 3
    _combat_state: "CombatState | None" = None
    rng: MutableRNG | None = None

    @classmethod
    def create(cls, deck: list[str] | list[CardInstance], rng: MutableRNG) -> "CardManager":
        manager = cls()
        if deck and all(isinstance(card, str) for card in deck):
            instances: list[CardInstance] = []
            for index, card_id in enumerate(deck):
                card = CardInstance(card_id=card_id)
                setattr(card, "_master_deck_index", index)
                instances.append(card)
            manager.draw_pile = CardPile(cards=instances)
        else:
            manager.draw_pile = CardPile.from_list(deck)
        manager.draw_pile.shuffle(rng)
        manager.rng = rng
        return manager

    @property
    def energy(self) -> int:
        return self._energy

    @property
    def max_energy(self) -> int:
        return self._max_energy

    def use_energy(self, amount: int) -> bool:
        if self._energy >= amount:
            self._energy -= amount
            return True
        return False

    def set_energy(self, amount: int) -> None:
        self._energy = amount

    def set_max_energy(self, amount: int) -> None:
        self._max_energy = amount

    def gain_energy(self, amount: int) -> None:
        self._energy += amount

    def _can_add_to_hand(self, *, hand_limit_offset: int = 0) -> bool:
        return self.hand.size() < (MAX_HAND_SIZE + max(0, hand_limit_offset))

    def _add_card_to_hand_with_limit(self, card: CardInstance, *, hand_limit_offset: int = 0) -> bool:
        if self._combat_state is not None:
            card._combat_state = self._combat_state
        if hasattr(card, "apply_combat_cost_modifiers"):
            card.apply_combat_cost_modifiers()
        if self._can_add_to_hand(hand_limit_offset=hand_limit_offset):
            self.hand.add(card)
            return True
        self.discard_pile.add(card)
        return False

    def _should_upgrade_generated_card(self, card: CardInstance) -> bool:
        combat_state = getattr(self, "_combat_state", None)
        player = getattr(combat_state, "player", None)
        if player is None or not hasattr(player, "powers"):
            return False
        if card.card_type.value in {"CURSE", "STATUS"}:
            return False
        return player.powers.has_power("MasterReality")

    def _make_generated_card(
        self,
        card_id: str,
        *,
        configure_card: Callable[[CardInstance], None] | None = None,
    ) -> CardInstance:
        card = CardInstance(card_id=card_id)
        if self._combat_state is not None:
            card._combat_state = self._combat_state
        if self._should_upgrade_generated_card(card):
            card.upgrade()
        if configure_card is not None:
            configure_card(card)
        return card

    def generate_cards_to_hand(
        self,
        card_id: str,
        count: int,
        *,
        hand_limit_offset: int = 0,
        configure_card: Callable[[CardInstance], None] | None = None,
    ) -> list[CardInstance]:
        if count <= 0:
            return []
        generated_cards: list[CardInstance] = []
        for _ in range(count):
            card = self._make_generated_card(card_id, configure_card=configure_card)
            self._add_card_to_hand_with_limit(card, hand_limit_offset=hand_limit_offset)
            generated_cards.append(card)
        self._check_normality_in_hand()
        return generated_cards

    def generate_cards_to_draw_pile(
        self,
        card_id: str,
        count: int,
        *,
        shuffle_into: bool = True,
        configure_card: Callable[[CardInstance], None] | None = None,
    ) -> list[CardInstance]:
        if count <= 0:
            return []
        generated_cards: list[CardInstance] = []
        for _ in range(count):
            card = self._make_generated_card(card_id, configure_card=configure_card)
            self.draw_pile.add(card)
            generated_cards.append(card)
        if shuffle_into and self.rng is not None:
            self.draw_pile.shuffle(self.rng)
        return generated_cards

    def move_draw_pile_top_to_hand(
        self,
        count: int,
        *,
        hand_limit_offset: int = 0,
    ) -> list[CardInstance]:
        if count <= 0:
            return []
        moved_cards: list[CardInstance] = []
        for _ in range(count):
            if self.draw_pile.is_empty():
                break
            if not self._can_add_to_hand(hand_limit_offset=hand_limit_offset):
                break
            card = self.draw_pile.pop()
            if card is None:
                break
            if hasattr(self, "_combat_state") and self._combat_state:
                card._combat_state = self._combat_state
            self.hand.add(card)
            moved_cards.append(card)
        if moved_cards:
            self._check_normality_in_hand()
        return moved_cards

    def shuffle_hand_and_discard_into_draw_excluding(self, excluded_card: CardInstance | None = None) -> list[CardInstance]:
        moved_cards: list[CardInstance] = []
        remaining_hand: list[CardInstance] = []
        for card in list(self.hand.cards):
            if card is excluded_card:
                remaining_hand.append(card)
                continue
            self.draw_pile.add(card)
            moved_cards.append(card)
        self.hand.cards = remaining_hand

        discard_cards = list(self.discard_pile.cards)
        self.discard_pile.clear()
        for card in discard_cards:
            self.draw_pile.add(card)
            moved_cards.append(card)

        if self.rng is not None:
            self.draw_pile.shuffle(self.rng)
        self._check_normality_in_hand()
        return moved_cards

    def exhaust_card_instance(self, card: CardInstance, *, source: Any | None = None) -> bool:
        if source is None and self._combat_state is not None:
            source = getattr(self._combat_state, "player", None)
        for pile in (self.hand, self.draw_pile, self.discard_pile):
            if pile.remove(card):
                card.on_exhaust()
                if source is not None and hasattr(source, "powers"):
                    block_gain, draw_amount = source.powers.on_exhaust(card)
                    if block_gain > 0:
                        source.gain_block(block_gain)
                    if draw_amount > 0:
                        self.draw_cards(draw_amount)
                self.exhaust_pile.add(card)
                self._check_normality_in_hand()
                return True
        return False

    def _handle_special_on_draw(self, card: CardInstance) -> None:
        if card.card_id == "DeusExMachina":
            self.generate_cards_to_hand("Miracle", card.magic_number)
            self.exhaust_card_instance(card)
            return
        if card.card_id == "EndlessAgony":
            generated = card.make_stat_equivalent_copy()
            if self._combat_state is not None:
                generated._combat_state = self._combat_state
            self._add_card_to_hand_with_limit(generated)

    def refresh_hand_costs_for_current_state(self) -> None:
        for card in self.hand.cards:
            if self._combat_state is not None:
                card._combat_state = self._combat_state
            if hasattr(card, "apply_combat_cost_modifiers"):
                card.apply_combat_cost_modifiers()

    def on_player_hp_loss(self, amount: int) -> None:
        if amount <= 0:
            return

        for pile in (self.hand, self.draw_pile, self.discard_pile, self.exhaust_pile, self.limbo_pile):
            for card in pile.cards:
                if self._combat_state is not None:
                    card._combat_state = self._combat_state
                if card.card_id == "BloodforBlood":
                    max_reduction = max(0, int(getattr(card, "cost", 0)))
                    card.combat_cost_reduction = min(
                        max_reduction,
                        max(0, int(getattr(card, "combat_cost_reduction", 0))) + amount,
                    )
                    if hasattr(card, "apply_combat_cost_modifiers"):
                        card.apply_combat_cost_modifiers()
                elif card.card_id == "MasterfulStab":
                    card.combat_cost_increase = min(
                        99,
                        max(0, int(getattr(card, "combat_cost_increase", 0))) + 1,
                    )
                    if hasattr(card, "apply_combat_cost_modifiers"):
                        card.apply_combat_cost_modifiers()

    def on_player_discard_from_hand(self, amount: int) -> None:
        if amount <= 0:
            return

        for pile in (self.hand, self.draw_pile, self.discard_pile, self.exhaust_pile, self.limbo_pile):
            for card in pile.cards:
                if card.card_id != "Eviscerate":
                    continue
                if self._combat_state is not None:
                    card._combat_state = self._combat_state
                max_reduction = max(0, int(getattr(card, "cost", 0)))
                card.combat_cost_reduction = min(
                    max_reduction,
                    max(0, int(getattr(card, "combat_cost_reduction", 0))) + amount,
                )
                if hasattr(card, "apply_combat_cost_modifiers"):
                    card.apply_combat_cost_modifiers()

    def on_player_power_played_in_combat(self) -> None:
        combat_state = getattr(self, "_combat_state", None)
        player = getattr(combat_state, "player", None)
        if player is None:
            return
        power_count = max(0, int(getattr(player, "_power_cards_played_this_combat", 0) or 0))
        for pile in (self.hand, self.draw_pile, self.discard_pile, self.exhaust_pile, self.limbo_pile):
            for card in pile.cards:
                if card.card_id != "ForceField":
                    continue
                if self._combat_state is not None:
                    card._combat_state = self._combat_state
                max_reduction = max(0, int(getattr(card, "cost", 0)))
                card.combat_cost_reduction = min(max_reduction, power_count)
                if hasattr(card, "apply_combat_cost_modifiers"):
                    card.apply_combat_cost_modifiers()

    def start_turn(self, draw_count: int = 5, rng: MutableRNG | None = None) -> list[CardInstance]:
        self._prepare_innate_cards()
        drawn = []
        for _ in range(draw_count):
            card = self.draw_card(rng)
            if card:
                drawn.append(card)
        self._cards_drawn_this_turn = len(drawn)
        return drawn

    def _prepare_innate_cards(self) -> None:
        """Prepare innate cards at the top of the draw pile.

        From wiki: Innate works as if the card was placed on top of your draw pile
        before your first draw. Each innate card occupies one draw slot.
        First turn draw = min(max(5, innate_count) + bonus_draws, 10)

        Innate cards are moved to the TOP of the draw pile.
        """
        innate_cards: list[CardInstance] = []

        for pile in [self.draw_pile, self.discard_pile, self.hand]:
            remaining: list[CardInstance] = []
            for card in pile.cards:
                if getattr(card, 'is_innate', False):
                    innate_cards.append(card)
                else:
                    remaining.append(card)
            pile.cards = remaining

        for card in innate_cards:
            self.draw_pile.cards.append(card)

    def end_turn(self, *, no_discard: bool = False) -> None:
        starting_hand = self.hand.to_list()
        retained_cards: list[CardInstance] = []
        combat = getattr(self, "_combat_state", None)
        engine = getattr(combat, "engine", None)
        for card in self.hand.to_list():
            temporary_retain = bool(getattr(card, "retain", False) and not getattr(card, "self_retain", False))
            if getattr(card, "is_ethereal", False):
                self.exhaust_card_instance(card)
            elif no_discard or card.retain or card.self_retain:
                retained_cards.append(card)
                card.on_retain()
            else:
                if engine is not None and hasattr(engine, "_handle_player_discard_from_hand"):
                    engine._handle_player_discard_from_hand(card)
                else:
                    self.discard_pile.add(card)
            if temporary_retain:
                card.retain = False
        extra_cards = [card for card in self.hand.cards if card not in starting_hand]
        self.hand.cards = retained_cards + extra_cards

    def _check_normality_in_hand(self) -> None:
        """Check if Normality is in hand and update lock accordingly.

        Normality only restricts when it's in hand. If it leaves hand, restriction is lifted.
        """
        from sts_py.engine.content.cards_min import CurseEffectType

        combat = getattr(self, '_combat_state', None)
        if not combat or not hasattr(combat, 'player'):
            return

        has_normality = False
        normality_limit = 3

        for card in self.hand.cards:
            if card.card_type.value in ("CURSE", "STATUS") and card.curse_effect_type == CurseEffectType.LIMIT_CARDS_PER_TURN:
                has_normality = True
                normality_limit = card.curse_effect_value
                break

        if has_normality:
            cards_played = len(getattr(combat, 'cards_played_this_turn', []))
            if cards_played >= normality_limit:
                combat.player._normality_locked = True
                combat.player._normality_limit = normality_limit
            else:
                combat.player._normality_locked = False
        else:
            combat.player._normality_locked = False
            combat.player._normality_limit = 0

    def draw_card(self, rng: MutableRNG | None = None, *, hand_limit_offset: int = 0) -> CardInstance | None:
        combat_state = getattr(self, "_combat_state", None)
        player = getattr(combat_state, "player", None)
        if player is not None and hasattr(player, "powers"):
            no_draw_amount = 0
            try:
                no_draw_amount = player.powers.get_power_amount("No Draw")
            except Exception:
                no_draw_amount = 0
            if no_draw_amount > 0:
                return None

        if not self._can_add_to_hand(hand_limit_offset=hand_limit_offset):
            return None

        if self.draw_pile.is_empty():
            if self.discard_pile.is_empty():
                return None
            self._shuffle_discard_into_draw(rng)

        card = self.draw_pile.pop()
        if card is None:
            return None
        if hasattr(self, '_combat_state') and self._combat_state:
            card._combat_state = self._combat_state
        else:
            card._combat_state = self
        card.on_draw()

        self.hand.add(card)
        self._cards_drawn_this_turn += 1
        self._handle_special_on_draw(card)
        if player is not None and hasattr(player, "powers"):
            player.powers.on_card_draw(player, card)
        self._check_normality_in_hand()
        return card

    def draw_cards(self, count: int, *, hand_limit_offset: int = 0) -> None:
        for _ in range(count):
            if self.draw_card(self.rng, hand_limit_offset=hand_limit_offset) is None:
                break

    def draw_to_hand_limit(self, *, hand_limit_offset: int = 0) -> list[CardInstance]:
        drawn_cards: list[CardInstance] = []
        while self._can_add_to_hand(hand_limit_offset=hand_limit_offset):
            card = self.draw_card(self.rng, hand_limit_offset=hand_limit_offset)
            if card is None:
                break
            drawn_cards.append(card)
        return drawn_cards

    def draw_to_hand_count(self, target_count: int, *, hand_limit_offset: int = 0) -> list[CardInstance]:
        drawn_cards: list[CardInstance] = []
        desired_size = min(MAX_HAND_SIZE + max(0, hand_limit_offset), max(0, int(target_count)) + max(0, hand_limit_offset))
        while self.hand.size() < desired_size and self._can_add_to_hand(hand_limit_offset=hand_limit_offset):
            card = self.draw_card(self.rng, hand_limit_offset=hand_limit_offset)
            if card is None:
                break
            drawn_cards.append(card)
        return drawn_cards

    def _shuffle_discard_into_draw(self, rng: MutableRNG | None = None) -> None:
        self.draw_pile.add_multiple(self.discard_pile.to_list())
        self.discard_pile.clear()
        active_rng = rng or self.rng
        if active_rng:
            self.draw_pile.shuffle(active_rng)

    def _scry_discard_priority(self, card: CardInstance, available_energy: int) -> tuple[int, int]:
        card_type = card.card_type.value
        cost_for_turn = getattr(card, "cost_for_turn", getattr(card, "cost", -1))
        is_over_costed = cost_for_turn > available_energy and card.card_id not in _SCRY_KEEP_CARD_IDS
        is_effectively_unplayable = cost_for_turn < 0

        if card_type in {"CURSE", "STATUS"}:
            return (0, -max(cost_for_turn, 0))
        if is_effectively_unplayable:
            return (1, -max(cost_for_turn, 0))
        if is_over_costed:
            return (2, -max(cost_for_turn, 0))
        return (99, -max(cost_for_turn, 0))

    def _should_discard_on_scry(self, card: CardInstance, available_energy: int) -> bool:
        if card.card_id == "Weave":
            return False
        if card.card_id in _SCRY_KEEP_CARD_IDS:
            return False
        if getattr(card, "cost_for_turn", getattr(card, "cost", -1)) == 0:
            return False

        priority, _ = self._scry_discard_priority(card, available_energy)
        return priority < 99

    def _trigger_on_scry(self, *, hand_limit_offset: int = 0) -> list[CardInstance]:
        returned_to_hand: list[CardInstance] = []
        for card in list(self.discard_pile.cards):
            if card.card_id != "Weave":
                continue
            if not self._can_add_to_hand(hand_limit_offset=hand_limit_offset):
                continue
            if self.discard_pile.remove(card):
                self.hand.add(card)
                returned_to_hand.append(card)
        if returned_to_hand:
            self._check_normality_in_hand()
        return returned_to_hand

    def _notify_player_on_scry(self) -> None:
        combat_state = getattr(self, "_combat_state", None)
        player = getattr(combat_state, "player", None)
        if player is not None and hasattr(player, "powers"):
            player.powers.on_scry(player)

    def _recover_discard_priority(self, card: CardInstance, available_energy: int) -> tuple[int, int]:
        card_type = card.card_type.value
        cost_for_turn = getattr(card, "cost_for_turn", getattr(card, "cost", -1))
        is_effectively_unplayable = cost_for_turn < 0
        is_over_costed = cost_for_turn > available_energy and card.card_id not in _RECOVER_KEEP_CARD_IDS
        is_immediate_value = card.card_id in _RECOVER_KEEP_CARD_IDS or cost_for_turn == 0

        if card.card_id == "Weave":
            return (0, cost_for_turn)
        if is_immediate_value:
            return (1, cost_for_turn)
        if card_type in {"CURSE", "STATUS"}:
            return (5, cost_for_turn)
        if is_effectively_unplayable:
            return (4, cost_for_turn)
        if is_over_costed:
            return (3, cost_for_turn)
        return (2, cost_for_turn)

    def recover_from_discard(
        self,
        count: int,
        *,
        hand_limit_offset: int = 0,
        temporary_retain: bool = True,
    ) -> list[CardInstance]:
        if count <= 0 or self.discard_pile.is_empty() or not self._can_add_to_hand(hand_limit_offset=hand_limit_offset):
            return []

        available_energy = self.energy
        selected = sorted(
            enumerate(self.discard_pile.cards),
            key=lambda item: (self._recover_discard_priority(item[1], available_energy), item[0]),
        )[:count]
        selected_indices = {index for index, _ in selected}
        selected_cards = [card for index, card in enumerate(self.discard_pile.cards) if index in selected_indices]
        recovered_cards: list[CardInstance] = []

        for card in selected_cards:
            if not self._can_add_to_hand(hand_limit_offset=hand_limit_offset):
                break
            if self.discard_pile.remove(card):
                if temporary_retain:
                    card.retain = True
                self.hand.add(card)
                recovered_cards.append(card)

        if recovered_cards:
            self._check_normality_in_hand()
        return recovered_cards

    def recover_all_zero_cost_from_discard(
        self,
        *,
        hand_limit_offset: int = 0,
    ) -> list[CardInstance]:
        if self.discard_pile.is_empty() or not self._can_add_to_hand(hand_limit_offset=hand_limit_offset):
            return []

        recovered_cards: list[CardInstance] = []
        for card in list(self.discard_pile.cards):
            if not self._can_add_to_hand(hand_limit_offset=hand_limit_offset):
                break
            card_cost = getattr(card, "cost", -1)
            is_zero_cost = int(card_cost if card_cost is not None else -1) == 0
            if not (is_zero_cost or bool(getattr(card, "free_to_play_once", False))):
                continue
            if self.discard_pile.remove(card):
                self._add_card_to_hand_with_limit(card, hand_limit_offset=hand_limit_offset)
                if card in self.hand.cards:
                    recovered_cards.append(card)

        if recovered_cards:
            self._check_normality_in_hand()
        return recovered_cards

    def resolve_scry(self, count: int, *, shuffle_if_empty: bool = False, hand_limit_offset: int = 0) -> dict[str, list[CardInstance]]:
        result = {"viewed": [], "discarded": [], "kept": [], "returned_to_hand": []}
        if count <= 0:
            return result

        if self.draw_pile.is_empty():
            if shuffle_if_empty and not self.discard_pile.is_empty():
                self._shuffle_discard_into_draw(self.rng)
            else:
                return result

        if self.draw_pile.is_empty():
            return result

        view_count = min(count, len(self.draw_pile.cards))
        start_idx = len(self.draw_pile.cards) - view_count
        viewed_cards = list(self.draw_pile.cards[start_idx:])
        available_energy = self.energy

        discard_offsets = {
            offset
            for _, offset, _ in sorted(
                (
                    (self._scry_discard_priority(card, available_energy), offset, card)
                    for offset, card in enumerate(viewed_cards)
                    if self._should_discard_on_scry(card, available_energy)
                ),
                key=lambda item: (item[0], item[1]),
            )
        }

        kept_cards = [card for offset, card in enumerate(viewed_cards) if offset not in discard_offsets]
        discarded_cards = [card for offset, card in enumerate(viewed_cards) if offset in discard_offsets]

        self.draw_pile.cards = self.draw_pile.cards[:start_idx] + kept_cards
        for card in discarded_cards:
            self.discard_pile.add(card)

        returned_to_hand = self._trigger_on_scry(hand_limit_offset=hand_limit_offset)
        self._notify_player_on_scry()

        result["viewed"] = viewed_cards
        result["discarded"] = discarded_cards
        result["kept"] = kept_cards
        result["returned_to_hand"] = returned_to_hand
        return result

    def play_card(self, card_index: int, exhaust: bool = False) -> CardInstance | None:
        card = self.hand.pop(card_index)
        if card is None:
            return None

        from sts_py.engine.content.cards_min import CurseEffectType
        if exhaust or card.exhaust or card.exhaust_on_use_once:
            if card.card_type.value in ("CURSE", "STATUS") and card.curse_effect_type == CurseEffectType.RETURN_TO_HAND_ON_EXHAUST:
                self.hand.add(card)
            else:
                self.exhaust_pile.add(card)
        elif card.purge_on_use:
            pass
        elif card.return_to_hand:
            self.hand.add(card)
        elif card.shuffle_back_into_draw_pile:
            self.draw_pile.add(card)
        else:
            self.discard_pile.add(card)

        self._check_normality_in_hand()

        return card

    def exhaust_card(self, card_index: int) -> CardInstance | None:
        card = self.hand.pop(card_index)
        if card is None:
            return None
        card.on_exhaust()
        self.exhaust_pile.add(card)
        return card

    def discard_card(self, card_index: int) -> CardInstance | None:
        card = self.hand.pop(card_index)
        if card is None:
            return None
        combat = getattr(self, "_combat_state", None)
        engine = getattr(combat, "engine", None)
        if engine is not None and hasattr(engine, "_handle_player_discard_from_hand"):
            engine._handle_player_discard_from_hand(card)
        else:
            self.discard_pile.add(card)
        return card

    def add_to_hand(self, card: str | CardInstance) -> None:
        self.hand.add(card if isinstance(card, CardInstance) else CardInstance(card_id=card))

    def add_to_draw(self, card: str | CardInstance) -> None:
        self.draw_pile.add(card if isinstance(card, CardInstance) else CardInstance(card_id=card))

    def add_to_discard(self, card: str | CardInstance) -> None:
        self.discard_pile.add(card if isinstance(card, CardInstance) else CardInstance(card_id=card))

    def add_to_exhaust(self, card: str | CardInstance) -> None:
        instance = card if isinstance(card, CardInstance) else CardInstance(card_id=card)
        instance.on_exhaust()
        self.exhaust_pile.add(instance)

    def get_hand_size(self) -> int:
        return self.hand.size()

    def get_draw_pile_size(self) -> int:
        return self.draw_pile.size()

    def get_discard_pile_size(self) -> int:
        return self.discard_pile.size()

    def get_exhaust_pile_size(self) -> int:
        return self.exhaust_pile.size()

    def get_card_in_hand(self, index: int) -> CardInstance | None:
        return self.hand.peek(index)

    def get_hand(self) -> list[CardInstance]:
        return self.hand.to_list()

    def to_dict(self) -> dict[str, Any]:
        return {
            "draw_pile": [card.to_dict() for card in self.draw_pile.to_list()],
            "hand": [card.to_dict() for card in self.hand.to_list()],
            "discard_pile": [card.to_dict() for card in self.discard_pile.to_list()],
            "exhaust_pile": [card.to_dict() for card in self.exhaust_pile.to_list()],
            "energy": self._energy,
            "max_energy": self._max_energy,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CardManager":
        manager = cls()
        manager.draw_pile = CardPile.from_list([CardInstance.from_dict(card) for card in data.get("draw_pile", [])])
        manager.hand = CardPile.from_list([CardInstance.from_dict(card) for card in data.get("hand", [])])
        manager.discard_pile = CardPile.from_list([CardInstance.from_dict(card) for card in data.get("discard_pile", [])])
        manager.exhaust_pile = CardPile.from_list([CardInstance.from_dict(card) for card in data.get("exhaust_pile", [])])
        manager._energy = data.get("energy", 3)
        manager._max_energy = data.get("max_energy", 3)
        return manager
