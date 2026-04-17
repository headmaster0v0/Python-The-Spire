"""Shop system for Slay The Spire.

Implements the merchant shop where players can:
- Buy cards (5 colored class cards + 2 colorless cards)
- Remove cards
- Buy relics (3 relics including 1 shop relic)
- Buy potions (3 potions)

Reference: Java ShopScreen.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from sts_py.engine.content.relics import RelicSource

if TYPE_CHECKING:
    from sts_py.engine.run.run_engine import RunEngine


class ShopItemType(str, Enum):
    CARD = "card"
    RELIC = "relic"
    POTION = "potion"
    CARD_REMOVE = "card_remove"


@dataclass
class ShopItem:
    item_type: ShopItemType
    item_id: str
    price: int
    original_price: int = 0
    on_sale: bool = False
    tier: str | None = None

    def __post_init__(self):
        if self.original_price == 0:
            self.original_price = self.price


@dataclass
class ShopState:
    colored_cards: list[ShopItem] = field(default_factory=list)
    colorless_cards: list[ShopItem] = field(default_factory=list)
    relics: list[ShopItem] = field(default_factory=list)
    potions: list[ShopItem] = field(default_factory=list)
    card_remove_cost: int = 75
    card_remove_used: bool = False
    sale_card_index: int = -1

    def get_all_cards(self) -> list[ShopItem]:
        return self.colored_cards + self.colorless_cards

    def to_dict(self) -> dict[str, Any]:
        return {
            "colored_cards": [
                {"id": c.item_id, "price": c.price, "original_price": c.original_price, "on_sale": c.on_sale}
                for c in self.colored_cards
            ],
            "colorless_cards": [
                {"id": c.item_id, "price": c.price, "original_price": c.original_price}
                for c in self.colorless_cards
            ],
            "relics": [
                {"id": r.item_id, "price": r.price, "original_price": r.original_price}
                for r in self.relics
            ],
            "potions": [
                {"id": p.item_id, "price": p.price, "original_price": p.original_price}
                for p in self.potions
            ],
            "card_remove_cost": self.card_remove_cost,
            "sale_card_index": self.sale_card_index,
        }


CARD_POOL_COMMON = [
    "Anger", "Armaments", "BodySlam", "Clash", "Cleave",
    "Clothesline", "Flex", "Havoc", "Headbutt", "HeavyBlade",
    "IronWave", "PerfectedStrike", "PommelStrike", "ShrugItOff",
    "SwordBoomerang", "Thunderclap", "TrueGrit", "TwinStrike",
    "Warcry", "WildStrike",
]

CARD_POOL_UNCOMMON = [
    "BattleTrance", "BloodforBlood", "Bloodletting", "BurningPact",
    "Carnage", "Combust", "DarkEmbrace", "Disarm", "Dropkick",
    "DualWield", "Entrench", "Evolve", "FeelNoPain", "FireBreathing",
    "FlameBarrier", "GhostlyArmor", "Hemokinesis", "InfernalBlade",
    "Inflame", "Intimidate", "Metallicize", "PowerThrough", "Pummel",
    "Rage", "Rampage", "RecklessCharge", "Rupture", "SearingBlow",
    "SecondWind", "SeeingRed", "Sentinel", "SeverSoul", "Shockwave",
    "SpotWeakness",
]

CARD_POOL_RARE = [
    "Barricade", "Berserk", "Bludgeon", "Brutality", "Corruption",
    "DemonForm", "DoubleTap", "Exhume", "FiendFire", "Immolate",
    "Impervious", "Juggernaut", "LimitBreak", "Offering", "Reaper",
    "Reckless Charge+", "Sword Boomerang+", "Thunderclap+", "True Grit+",
]

COLORLESS_UNCOMMON_POOL = [
    "Blind",
    "DarkShackles",
    "DeepBreath",
    "Finesse",
    "FlashOfSteel",
    "GoodInstincts",
    "Madness",
    "Panacea",
    "PanicButton",
    "SwiftStrike",
    "Trip",
    "BandageUp",
    "Discovery",
    "DramaticEntrance",
    "Enlightenment",
    "Forethought",
    "Impatience",
    "JackOfAllTrades",
    "MindBlast",
    "Purity",
]

COLORLESS_RARE_POOL = [
    "Apotheosis",
    "HandOfGreed",
    "MasterOfStrategy",
    "Chrysalis",
    "Magnetism",
    "Mayhem",
    "Metamorphosis",
    "Panache",
    "SadisticNature",
    "SecretTechnique",
    "SecretWeapon",
    "TheBomb",
    "ThinkingAhead",
    "Transmutation",
    "Violence",
]

RELIC_POOL_COMMON = [
    "Anchor", "AncientTeaSet", "ArtOfWar", "BagOfPreparation",
    "BagOfMarbles", "BloodVial", "BronzeScales", "CentennialPuzzle",
    "CeramicFish", "Cleric", "DeadBug", "Dodecahedron", "DreamCatcher",
    "FrozenEgg", "HappyFlower", "JuzuBracelet", "Lantern", "MawBank",
    "MealTicket", "Nunchaku", "OddlySmoothStone", "Omamori", "Orichalcum",
    "Pantograph", "Pear", "PotionBelt", "PrayerWheel", "Shuriken",
    "SmilingMask", "Sundial", "TheBoot", "TinyChest", "Tingsha",
    "Torii", "ToughBandages", "ToyOrnithopter", "Vajra", "WarPaint",
    "Whetstone",
]

RELIC_POOL_UNCOMMON = [
    "BirdFacedUrn", "Calipers", "Cerberus", "ChampionBelt", "CloakClasp",
    "DollysMirror", "EatYourBrain", "Enchiridions", "EternalFeather",
    "FrozenEgg2", "GremlinHorn", "HappyFlower2", "IceCream", "Inserter",
    "JuzuBracelet2", "Lantern2", "LeadStone", "MeatOnTheBone",
    "MidasBlood", "MoltenEgg2", "MonkeyPaw", "Mug", "Necronomicon",
    "NilrysCodex", "NinjaScroll", "OddMushroom", "OldCoin", "Orrery",
    "PandorasBox", "PaperCrane", "Pearl", "Pocketwatch", "PrismaticShard",
    "RunicCube", "RunicDodecahedron", "SacredBark", "SelfFormingClay",
    "Shovel", "TheSpecimen", "Toolbox", "ToughBandages2", "TwistedFunnel",
    " Velasco", "WristBursary",
]

RELIC_POOL_RARE = [
    "BlackBlood", "BlackStar", "BottledFlame", "BottledFlame",
    "Bottled Tornado", "BurningBlood", "Champion Belt", "CrackedCore",
    "CursedKey", "DarkPeace", "Disciple", "Dualidad", "EmptyCage",
    "Enlightenment", "Fusion", "Girya", "Glasses", "HolyWater",
    "Injustice", "JeweledCard", "KeyExtender", "LizardB",
    "MarkOfPain", "Matriarch", "MawBank2", "NuclearBattery", "OddMushroom2",
    "Pale", "Pandora Box", "PotionBelt2", "RingOfSerpent", "SneckoEye",
    "Stance", "The Courier", "Tingsha2", "UnceasingTop", "VelvetChoker",
    "Violet", "VoidCore", "Vow",
]

RELIC_POOL_SHOP = [
    "The Courier", "Membership Card", "Smiling Mask", "Meal Ticket", "Maw Bank",
]
COLORLESS_RARE_CHANCE = 0.3


def get_card_price(rarity: str, rng: Any) -> int:
    """Get card price based on rarity with jitter (0.9-1.1 multiplier)."""
    base_prices = {
        "common": 50,
        "uncommon": 75,
        "rare": 150,
    }
    base = base_prices.get(rarity, 50)
    if rng is None:
        return int(base)
    jitter = rng.random_float() * 0.2 + 0.9  # 0.9 to 1.1
    return int(base * jitter)


def get_relic_price(tier: str, rng: Any) -> int:
    """Get relic price based on tier with jitter (0.95-1.05 multiplier)."""
    base_prices = {
        "common": 150,
        "uncommon": 250,
        "rare": 300,
        "shop": 150,
    }
    base = base_prices.get(tier, 150)
    if rng is None:
        return int(base)
    jitter = rng.random_float() * 0.1 + 0.95  # 0.95 to 1.05
    return int(base * jitter)


def get_potion_price(rarity: str, rng: Any) -> int:
    """Get potion price based on rarity with jitter (0.95-1.05 multiplier)."""
    base_prices = {
        "common": 50,
        "uncommon": 75,
        "rare": 100,
    }
    base = base_prices.get(rarity, 50)
    if rng is None:
        return int(base)
    jitter = rng.random_float() * 0.1 + 0.95  # 0.95 to 1.05
    return int(base * jitter)


def roll_relic_tier(rng: Any) -> str:
    """Roll for relic tier: 48% common, 34% uncommon, 18% rare."""
    roll = rng.random_int(99)
    if roll < 48:
        return "common"
    elif roll < 82:
        return "uncommon"
    else:
        return "rare"


def generate_colored_cards(rng: Any, character_class: str = "IRONCLAD") -> list[ShopItem]:
    """Generate 5 colored cards: 2 Attack, 2 Skill, 1 Power (all same class)."""
    from sts_py.engine.content.cards_min import CardType
    from sts_py.engine.content.pool_order import build_reward_pools

    reward_pools = build_reward_pools(character_class)
    cards_by_type: dict[CardType, list[Any]] = {
        CardType.ATTACK: [],
        CardType.SKILL: [],
        CardType.POWER: [],
    }
    for card_defs in reward_pools.values():
        for card_def in card_defs:
            card_type = getattr(card_def, "card_type", getattr(card_def, "type", None))
            if card_type in cards_by_type:
                cards_by_type[card_type].append(card_def)

    cards: list[ShopItem] = []
    chosen_ids: set[str] = set()
    for requested_type in (
        CardType.ATTACK,
        CardType.ATTACK,
        CardType.SKILL,
        CardType.SKILL,
        CardType.POWER,
    ):
        pool = [card_def for card_def in cards_by_type.get(requested_type, []) if card_def.id not in chosen_ids]
        if not pool:
            pool = [
                card_def
                for candidate_type, candidate_defs in cards_by_type.items()
                if candidate_type != requested_type
                for card_def in candidate_defs
                if card_def.id not in chosen_ids
            ]
        if not pool:
            continue
        idx = rng.random_int(len(pool) - 1) if rng is not None else 0
        card_def = pool[idx]
        chosen_ids.add(card_def.id)
        rarity_name = str(getattr(getattr(card_def, "rarity", None), "value", "COMMON") or "COMMON").lower()
        if rarity_name not in {"common", "uncommon", "rare"}:
            rarity_name = "common"
        price = get_card_price(rarity_name, rng)
        cards.append(
            ShopItem(
                item_type=ShopItemType.CARD,
                item_id=card_def.id,
                price=price,
                original_price=price,
            )
        )

    return cards


def generate_colorless_cards(rng: Any) -> list[ShopItem]:
    """Generate 2 colorless cards: 1 Uncommon on left, 1 Rare on right."""
    cards = []

    uncommon_pool = COLORLESS_UNCOMMON_POOL[:]
    rare_pool = COLORLESS_RARE_POOL[:]

    if uncommon_pool:
        idx = rng.random_int(len(uncommon_pool) - 1)
        card_id = uncommon_pool[idx]
        price = get_card_price("uncommon", rng)
        price = int(price * 1.2)  # Colorless cards are 20% more expensive
        cards.append(ShopItem(
            item_type=ShopItemType.CARD,
            item_id=card_id,
            price=price,
            original_price=price,
        ))

    if rare_pool:
        idx = rng.random_int(len(rare_pool) - 1)
        card_id = rare_pool[idx]
        price = get_card_price("rare", rng)
        price = int(price * 1.2)  # Colorless cards are 20% more expensive
        cards.append(ShopItem(
            item_type=ShopItemType.CARD,
            item_id=card_id,
            price=price,
            original_price=price,
        ))

    return cards


def generate_relics(rng: Any) -> list[ShopItem]:
    """Generate 3 relics: first 2 random tier, last one is always Shop Relic."""
    relics = []

    for i in range(3):
        if i == 2:
            tier = "shop"
            pool = RELIC_POOL_SHOP
        else:
            tier = roll_relic_tier(rng)
            if tier == "common":
                pool = RELIC_POOL_COMMON
            elif tier == "uncommon":
                pool = RELIC_POOL_UNCOMMON
            else:
                pool = RELIC_POOL_RARE

        if pool:
            idx = rng.random_int(len(pool) - 1)
            relic_id = pool[idx]
            price = get_relic_price(tier, rng)
            relics.append(ShopItem(
                item_type=ShopItemType.RELIC,
                item_id=relic_id,
                price=price,
                original_price=price,
            ))

    return relics


def generate_potions(rng: Any, character_class: str = "IRONCLAD") -> list[ShopItem]:
    """Generate 3 potions with rarity chances: 65% common, 25% uncommon, 10% rare."""
    from sts_py.engine.content.potions import get_common_potions, get_uncommon_potions, get_rare_potions

    common_potions = get_common_potions(character_class)
    uncommon_potions = get_uncommon_potions(character_class)
    rare_potions = get_rare_potions(character_class)

    potions = []
    for _ in range(3):
        roll = rng.random_int(99)
        if roll < 65 and common_potions:
            potion_idx = rng.random_int(len(common_potions) - 1)
            potion = common_potions[potion_idx]
            rarity = "common"
        elif roll < 90 and uncommon_potions:
            potion_idx = rng.random_int(len(uncommon_potions) - 1)
            potion = uncommon_potions[potion_idx]
            rarity = "uncommon"
        elif rare_potions:
            potion_idx = rng.random_int(len(rare_potions) - 1)
            potion = rare_potions[potion_idx]
            rarity = "rare"
        else:
            continue

        price = get_potion_price(rarity, rng)
        potions.append(ShopItem(
            item_type=ShopItemType.POTION,
            item_id=potion.potion_id,
            price=price,
            original_price=price,
        ))

    return potions


def apply_sale_card(shop: ShopState, rng: Any) -> None:
    """Apply 50% sale to one random colored card."""
    if shop.colored_cards:
        sale_idx = rng.random_int(4)  # 0-4
        shop.sale_card_index = sale_idx
        card = shop.colored_cards[sale_idx]
        card.price = card.price // 2
        card.on_sale = True


def apply_ascension_discount(shop: ShopState, ascension_level: int) -> None:
    """Apply 10% price increase on Ascension 16+."""
    if ascension_level >= 16:
        multiplier = 1.1
        for card in shop.colored_cards + shop.colorless_cards:
            card.price = int(card.price * multiplier)
        for relic in shop.relics:
            relic.price = int(relic.price * multiplier)
        for potion in shop.potions:
            potion.price = int(potion.price * multiplier)


def apply_courier_discount(shop: ShopState, has_courier: bool) -> None:
    """Apply 20% discount if player has The Courier."""
    if has_courier:
        for card in shop.colored_cards + shop.colorless_cards:
            card.price = int(card.price * 0.8)
        for relic in shop.relics:
            relic.price = int(relic.price * 0.8)
        for potion in shop.potions:
            potion.price = int(potion.price * 0.8)


def apply_membership_discount(shop: ShopState, has_membership: bool) -> None:
    """Apply 50% discount if player has Membership Card."""
    if has_membership:
        for card in shop.colored_cards + shop.colorless_cards:
            card.price = int(card.price * 0.5)
        for relic in shop.relics:
            relic.price = int(relic.price * 0.5)
        for potion in shop.potions:
            potion.price = int(potion.price * 0.5)


def generate_shop(
    rng: Any,
    act: int = 1,
    character_class: str = "IRONCLAD",
    ascension_level: int = 0,
    has_courier: bool = False,
    has_membership: bool = False,
    relics: list[ShopItem] | None = None,
) -> ShopState:
    """Generate complete shop state matching Java ShopScreen.java logic."""
    shop = ShopState()

    shop.colored_cards = generate_colored_cards(rng, character_class)
    shop.colorless_cards = generate_colorless_cards(rng)
    shop.relics = list(relics) if relics is not None else generate_relics(rng)
    shop.potions = generate_potions(rng, character_class)

    apply_sale_card(shop, rng)
    apply_ascension_discount(shop, ascension_level)
    apply_courier_discount(shop, has_courier)
    apply_membership_discount(shop, has_membership)

    shop.card_remove_cost = 75

    return shop


class ShopEngine:
    def __init__(self, run_engine: "RunEngine", shop_state: ShopState):
        self.run_engine = run_engine
        self.shop = shop_state
        self.purchased_cards: list[str] = []
        self.purchased_relics: list[str] = []
        self.purchased_potions: list[str] = []
        self.removed_cards: list[str] = []
        self._sold_out_colored_cards: set[int] = set()
        self._sold_out_colorless_cards: set[int] = set()
        self._sold_out_relics: set[int] = set()
        self._sold_out_potions: set[int] = set()
        self.run_engine._ensure_current_shop_history(
            initial_relic_ids=self._current_relic_ids(),
            initial_colored_card_ids=self._current_colored_card_ids(),
            initial_colorless_card_ids=self._current_colorless_card_ids(),
            initial_potion_ids=self._current_potion_ids(),
        )

    def can_afford(self, price: int) -> bool:
        return self.run_engine.state.player_gold >= price

    def _get_card_price(self, card_index: int, is_colored: bool = True) -> int:
        if is_colored and 0 <= card_index < len(self.shop.colored_cards):
            return self.shop.colored_cards[card_index].price
        elif not is_colored and 0 <= card_index < len(self.shop.colorless_cards):
            return self.shop.colorless_cards[card_index].price
        return 0

    def buy_card(self, card_index: int, is_colored: bool = True) -> dict[str, Any]:
        sold_out_cards = self._sold_out_colored_cards if is_colored else self._sold_out_colorless_cards
        if is_colored:
            if card_index in sold_out_cards:
                return {"success": False, "reason": "already_sold"}
            if card_index >= len(self.shop.colored_cards):
                return {"success": False, "reason": "invalid_index"}
            item = self.shop.colored_cards[card_index]
        else:
            if card_index in sold_out_cards:
                return {"success": False, "reason": "already_sold"}
            if card_index >= len(self.shop.colorless_cards):
                return {"success": False, "reason": "invalid_index"}
            item = self.shop.colorless_cards[card_index]

        if not self.can_afford(item.price):
            return {"success": False, "reason": "not_enough_gold"}

        self.run_engine.state.player_gold -= item.price
        self.run_engine.state.deck.append(item.item_id)
        self.purchased_cards.append(item.item_id)

        if self._has_courier():
            new_card = self._replace_card(item.item_id, card_index, is_colored)
            if is_colored:
                current_card_ids = self._current_colored_card_ids()
                self.run_engine._set_current_shop_colored_card_ids(current_card_ids)
                if new_card is not None:
                    self.run_engine._record_shop_surfaced_colored_card(new_card, current_card_ids=current_card_ids)
            else:
                current_card_ids = self._current_colorless_card_ids()
                self.run_engine._set_current_shop_colorless_card_ids(current_card_ids)
                if new_card is not None:
                    self.run_engine._record_shop_surfaced_colorless_card(new_card, current_card_ids=current_card_ids)
            return {
                "success": True,
                "card_id": item.item_id,
                "price_paid": item.price,
                "replacement_card": new_card,
            }

        sold_out_cards.add(card_index)
        if is_colored:
            self.run_engine._set_current_shop_colored_card_ids(self._current_colored_card_ids())
        else:
            self.run_engine._set_current_shop_colorless_card_ids(self._current_colorless_card_ids())

        return {
            "success": True,
            "card_id": item.item_id,
            "price_paid": item.price,
        }

    def _has_courier(self) -> bool:
        return self.run_engine._has_relic("TheCourier")

    def _roll_card_rarity(self, rng: Any) -> str:
        if rng is None:
            return "common"
        roll = rng.random_int(99)
        if roll < 3:
            return "rare"
        if roll < 40:
            return "uncommon"
        return "common"

    def _choose_colored_replacement_card(self, purchased_card_id: str, rng: Any) -> tuple[str | None, str]:
        from sts_py.engine.content.cards_min import ALL_CARD_DEFS, CardRarity
        from sts_py.engine.content.pool_order import build_reward_pools

        canonical_card_id = self.run_engine._canonical_card_id(purchased_card_id)
        purchased_def = ALL_CARD_DEFS.get(canonical_card_id)
        if purchased_def is None:
            pool = CARD_POOL_COMMON + CARD_POOL_UNCOMMON + CARD_POOL_RARE
            if not pool:
                return None, "common"
            card_id = pool[rng.random_int(len(pool) - 1)] if rng is not None else pool[0]
            return card_id, "common"

        reward_pools = build_reward_pools(self.run_engine.state.character_class)
        rarity_order = [self._roll_card_rarity(rng), "common", "uncommon", "rare"]
        seen_rarities: list[str] = []
        for rarity_name in rarity_order:
            if rarity_name in seen_rarities:
                continue
            seen_rarities.append(rarity_name)
            candidate_defs = [
                card_def
                for card_def in reward_pools.get(CardRarity[rarity_name.upper()], [])
                if card_def.type == purchased_def.type
            ]
            if candidate_defs:
                index = rng.random_int(len(candidate_defs) - 1) if rng is not None else 0
                return candidate_defs[index].id, rarity_name

        fallback_candidates = [
            card_def
            for pool in reward_pools.values()
            for card_def in pool
            if card_def.type == purchased_def.type
        ]
        if fallback_candidates:
            index = rng.random_int(len(fallback_candidates) - 1) if rng is not None else 0
            fallback_def = fallback_candidates[index]
            return fallback_def.id, str(getattr(fallback_def.rarity, "value", "common")).lower()
        return canonical_card_id, "common"

    def _choose_colorless_replacement_card(self, rng: Any) -> tuple[str | None, str]:
        rarity_name = "rare" if rng is not None and rng.random_float() < COLORLESS_RARE_CHANCE else "uncommon"
        pool = COLORLESS_RARE_POOL if rarity_name == "rare" else COLORLESS_UNCOMMON_POOL
        if not pool:
            return None, rarity_name
        card_id = pool[rng.random_int(len(pool) - 1)] if rng is not None else pool[0]
        return card_id, rarity_name

    def _replace_card(self, purchased_card_id: str, card_index: int, is_colored: bool) -> str | None:
        rng_state = getattr(self.run_engine.state, 'rng', None)
        rng = getattr(rng_state, "merchant_rng", None)
        if is_colored:
            new_card_id, rarity_name = self._choose_colored_replacement_card(purchased_card_id, rng)
            if new_card_id is None:
                return None
            new_price = get_card_price(rarity_name, rng)
            if self._has_courier():
                new_price = int(new_price * 0.8)
            if self.run_engine._has_relic("MembershipCard"):
                new_price = int(new_price * 0.5)
            self.shop.colored_cards[card_index] = ShopItem(
                item_type=ShopItemType.CARD,
                item_id=self.run_engine._canonical_card_id(new_card_id),
                price=new_price,
                original_price=new_price,
            )
            return self.shop.colored_cards[card_index].item_id
        else:
            new_card_id, rarity_name = self._choose_colorless_replacement_card(rng)
            if new_card_id is None:
                return None
            new_price = get_card_price(rarity_name, rng)
            new_price = int(new_price * 1.2)
            if self._has_courier():
                new_price = int(new_price * 0.8)
            if self.run_engine._has_relic("MembershipCard"):
                new_price = int(new_price * 0.5)
            self.shop.colorless_cards[card_index] = ShopItem(
                item_type=ShopItemType.CARD,
                item_id=self.run_engine._canonical_card_id(new_card_id),
                price=new_price,
                original_price=new_price,
            )
            return self.shop.colorless_cards[card_index].item_id

    def _current_colored_card_ids(self) -> list[str]:
        return [
            self.run_engine._canonical_card_id(item.item_id)
            for idx, item in enumerate(self.shop.colored_cards)
            if idx not in self._sold_out_colored_cards
        ]

    def _current_colorless_card_ids(self) -> list[str]:
        return [
            self.run_engine._canonical_card_id(item.item_id)
            for idx, item in enumerate(self.shop.colorless_cards)
            if idx not in self._sold_out_colorless_cards
        ]

    def _current_relic_ids(self) -> list[str]:
        return [
            item.item_id
            for idx, item in enumerate(self.shop.relics)
            if idx not in self._sold_out_relics
        ]

    def _current_potion_ids(self) -> list[str]:
        return [
            self.run_engine._canonical_potion_id(item.item_id)
            for idx, item in enumerate(self.shop.potions)
            if idx not in self._sold_out_potions
        ]

    def _replace_relic(self, relic_index: int) -> str | None:
        current_ids = set(self._current_relic_ids())
        current_ids.discard(self.shop.relics[relic_index].item_id)
        replacement = self.run_engine._generate_courier_replacement_relic(exclude=current_ids)
        if replacement is None:
            return None
        price = replacement.price
        if self._has_courier():
            price = int(price * 0.8)
        if self.run_engine._has_relic("MembershipCard"):
            price = int(price * 0.5)
        replacement.price = price
        replacement.original_price = price
        self.shop.relics[relic_index] = replacement
        return replacement.item_id

    def _replace_potion(self, potion_index: int) -> str | None:
        from sts_py.engine.content.potions import get_common_potions, get_uncommon_potions, get_rare_potions

        rng_state = getattr(self.run_engine.state, "rng", None)
        rng = getattr(rng_state, "merchant_rng", None)
        if rng is None:
            return None

        character_class = getattr(self.run_engine.state, "character_class", "IRONCLAD")
        common_potions = get_common_potions(character_class)
        uncommon_potions = get_uncommon_potions(character_class)
        rare_potions = get_rare_potions(character_class)
        roll = rng.random_int(99)
        if roll < 65 and common_potions:
            potion = common_potions[rng.random_int(len(common_potions) - 1)]
            rarity = "common"
        elif roll < 90 and uncommon_potions:
            potion = uncommon_potions[rng.random_int(len(uncommon_potions) - 1)]
            rarity = "uncommon"
        elif rare_potions:
            potion = rare_potions[rng.random_int(len(rare_potions) - 1)]
            rarity = "rare"
        else:
            return None

        price = get_potion_price(rarity, rng)
        if self._has_courier():
            price = int(price * 0.8)
        if self.run_engine._has_relic("MembershipCard"):
            price = int(price * 0.5)
        self.shop.potions[potion_index] = ShopItem(
            item_type=ShopItemType.POTION,
            item_id=potion.potion_id,
            price=price,
            original_price=price,
            tier=rarity,
        )
        return potion.potion_id

    def buy_relic(self, relic_index: int) -> dict[str, Any]:
        if relic_index in self._sold_out_relics:
            return {"success": False, "reason": "already_sold"}

        if relic_index >= len(self.shop.relics):
            return {"success": False, "reason": "invalid_index"}

        item = self.shop.relics[relic_index]
        if not self.can_afford(item.price):
            return {"success": False, "reason": "not_enough_gold"}

        self.run_engine.state.player_gold -= item.price
        acquired = self.run_engine._acquire_relic(
            item.item_id,
            source=RelicSource.SHOP,
            record_pending=True,
        )
        self.purchased_relics.append(str(acquired or item.item_id))
        replacement_relic = None
        if self._has_courier():
            replacement_relic = self._replace_relic(relic_index)
            if replacement_relic is None:
                self._sold_out_relics.add(relic_index)
            current_relic_ids = self._current_relic_ids()
        else:
            self._sold_out_relics.add(relic_index)
            current_relic_ids = self._current_relic_ids()
        self.run_engine._record_shop_purchased_relic(acquired or item.item_id, current_relic_ids=current_relic_ids)
        if replacement_relic is not None:
            self.run_engine._record_shop_surfaced_relic(replacement_relic, current_relic_ids=current_relic_ids)

        result = {
            "success": True,
            "relic_id": acquired or item.item_id,
            "price_paid": item.price,
        }
        if replacement_relic is not None:
            result["replacement_relic"] = replacement_relic
        return result

    def remove_card(self, card_id: str) -> dict[str, Any]:
        if card_id not in self.run_engine.state.deck:
            return {"success": False, "reason": "card_not_in_deck"}

        price = self._get_card_remove_price()
        if not self.can_afford(price):
            return {"success": False, "reason": "not_enough_gold"}

        self.run_engine.state.player_gold -= price
        from sts_py.engine.run.events import _apply_parasite_penalty
        _apply_parasite_penalty(self.run_engine.state, card_id)
        self.run_engine.state.deck.remove(card_id)
        self.removed_cards.append(card_id)
        self.shop.card_remove_cost += 25
        self.shop.card_remove_used = True

        return {
            "success": True,
            "card_id": card_id,
            "price_paid": price,
        }

    def _get_card_remove_price(self) -> int:
        base_price = self.shop.card_remove_cost
        has_smiling = self.run_engine._has_relic("SmilingMask")
        has_courier = self._has_courier()
        has_membership = self.run_engine._has_relic("MembershipCard")

        if has_smiling:
            return 50
        elif has_courier and has_membership:
            return int(base_price * 0.8 * 0.5)
        elif has_courier:
            return int(base_price * 0.8)
        elif has_membership:
            return int(base_price * 0.5)
        return base_price

    def buy_potion(self, potion_index: int) -> dict[str, Any]:
        if potion_index in self._sold_out_potions:
            return {"success": False, "reason": "already_sold"}

        if potion_index >= len(self.shop.potions):
            return {"success": False, "reason": "invalid_index"}

        item = self.shop.potions[potion_index]
        if not self.can_afford(item.price):
            return {"success": False, "reason": "not_enough_gold"}

        self.run_engine.state.player_gold -= item.price
        if self.run_engine.gain_potion(item.item_id):
            self.purchased_potions.append(item.item_id)
            replacement_potion = None
            if self._has_courier():
                replacement_potion = self._replace_potion(potion_index)
                if replacement_potion is None:
                    self._sold_out_potions.add(potion_index)
                current_potion_ids = self._current_potion_ids()
                self.run_engine._set_current_shop_potion_ids(current_potion_ids)
                if replacement_potion is not None:
                    self.run_engine._record_shop_surfaced_potion(replacement_potion, current_potion_ids=current_potion_ids)
            else:
                self._sold_out_potions.add(potion_index)
                self.run_engine._set_current_shop_potion_ids(self._current_potion_ids())
            result = {
                "success": True,
                "potion_id": item.item_id,
                "price_paid": item.price,
            }
            if replacement_potion is not None:
                result["replacement_potion"] = replacement_potion
            return result
        else:
            return {"success": False, "reason": "no_potion_slots"}

    def leave(self) -> None:
        pass

    def get_available_cards(self) -> list[dict[str, Any]]:
        result = []
        for i, item in enumerate(self.shop.colored_cards):
            if i not in self._sold_out_colored_cards:
                result.append({
                    "index": i,
                    "card_id": item.item_id,
                    "price": item.price,
                    "original_price": item.original_price,
                    "on_sale": item.on_sale,
                    "affordable": self.can_afford(item.price),
                    "is_colored": True,
                })
        for i, item in enumerate(self.shop.colorless_cards):
            if i not in self._sold_out_colorless_cards:
                result.append({
                    "index": i,
                    "card_id": item.item_id,
                    "price": item.price,
                    "original_price": item.original_price,
                    "affordable": self.can_afford(item.price),
                    "is_colored": False,
                })
        return result

    def get_available_relics(self) -> list[dict[str, Any]]:
        result = []
        for i, item in enumerate(self.shop.relics):
            if i not in self._sold_out_relics:
                result.append({
                    "index": i,
                    "relic_id": item.item_id,
                    "price": item.price,
                    "original_price": item.original_price,
                    "affordable": self.can_afford(item.price),
                })
        return result

    def get_available_potions(self) -> list[dict[str, Any]]:
        result = []
        for i, item in enumerate(self.shop.potions):
            if i not in self._sold_out_potions:
                result.append({
                    "index": i,
                    "potion_id": item.item_id,
                    "price": item.price,
                    "original_price": item.original_price,
                    "affordable": self.can_afford(item.price),
                })
        return result

    def get_card_remove_price(self) -> int:
        return self._get_card_remove_price()

    def is_card_remove_available(self) -> bool:
        return not self.shop.card_remove_used
