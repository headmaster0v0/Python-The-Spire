package stsrecorder.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePrefixPatch;
import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.potions.AbstractPotion;
import com.megacrit.cardcrawl.shop.ShopScreen;
import com.megacrit.cardcrawl.shop.StorePotion;
import com.megacrit.cardcrawl.shop.StoreRelic;
import stsrecorder.DataRecorder;

import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.List;

class ShopPatchUtils {
    @SuppressWarnings("unchecked")
    private static ArrayList<StoreRelic> readStoreRelics(ShopScreen shopScreen) throws Exception {
        Field relicsField = ShopScreen.class.getDeclaredField("relics");
        relicsField.setAccessible(true);
        return (ArrayList<StoreRelic>) relicsField.get(shopScreen);
    }

    @SuppressWarnings("unchecked")
    private static ArrayList<AbstractCard> readCardListField(ShopScreen shopScreen, String fieldName) throws Exception {
        Field cardsField = ShopScreen.class.getDeclaredField(fieldName);
        cardsField.setAccessible(true);
        return (ArrayList<AbstractCard>) cardsField.get(shopScreen);
    }

    @SuppressWarnings("unchecked")
    private static ArrayList<StorePotion> readStorePotions(ShopScreen shopScreen) throws Exception {
        Field potionsField = ShopScreen.class.getDeclaredField("potions");
        potionsField.setAccessible(true);
        return (ArrayList<StorePotion>) potionsField.get(shopScreen);
    }

    static List<String> readShopRelicOfferIds(ShopScreen shopScreen) {
        List<String> relicIds = new ArrayList<>();
        if (shopScreen == null) {
            return relicIds;
        }
        try {
            ArrayList<StoreRelic> relics = readStoreRelics(shopScreen);
            if (relics == null) {
                return relicIds;
            }
            for (StoreRelic relic : relics) {
                if (relic != null && relic.relic != null) {
                    relicIds.add(relic.relic.relicId);
                }
            }
        } catch (Exception e) {
            DataRecorder.logger.error("Error reading shop relic offers: " + e.getMessage());
        }
        return relicIds;
    }

    static List<String> readShopColoredCardOfferIds(ShopScreen shopScreen) {
        List<String> cardIds = new ArrayList<>();
        if (shopScreen == null) {
            return cardIds;
        }
        try {
            ArrayList<AbstractCard> cards = readCardListField(shopScreen, "coloredCards");
            if (cards == null) {
                return cardIds;
            }
            for (AbstractCard card : cards) {
                if (card != null) {
                    cardIds.add(card.cardID);
                }
            }
        } catch (Exception e) {
            DataRecorder.logger.error("Error reading shop colored cards: " + e.getMessage());
        }
        return cardIds;
    }

    static List<String> readShopColorlessCardOfferIds(ShopScreen shopScreen) {
        List<String> cardIds = new ArrayList<>();
        if (shopScreen == null) {
            return cardIds;
        }
        try {
            ArrayList<AbstractCard> cards = readCardListField(shopScreen, "colorlessCards");
            if (cards == null) {
                return cardIds;
            }
            for (AbstractCard card : cards) {
                if (card != null) {
                    cardIds.add(card.cardID);
                }
            }
        } catch (Exception e) {
            DataRecorder.logger.error("Error reading shop colorless cards: " + e.getMessage());
        }
        return cardIds;
    }

    static List<String> readShopPotionOfferIds(ShopScreen shopScreen) {
        List<String> potionIds = new ArrayList<>();
        if (shopScreen == null) {
            return potionIds;
        }
        try {
            ArrayList<StorePotion> potions = readStorePotions(shopScreen);
            if (potions == null) {
                return potionIds;
            }
            for (StorePotion potion : potions) {
                if (potion != null && potion.potion != null) {
                    potionIds.add(potion.potion.ID);
                }
            }
        } catch (Exception e) {
            DataRecorder.logger.error("Error reading shop potions: " + e.getMessage());
        }
        return potionIds;
    }

    static int findCardIndex(ShopScreen shopScreen, AbstractCard card, boolean isColorless) {
        if (shopScreen == null || card == null) {
            return -1;
        }
        try {
            ArrayList<AbstractCard> cards = readCardListField(shopScreen, isColorless ? "colorlessCards" : "coloredCards");
            return cards == null ? -1 : cards.indexOf(card);
        } catch (Exception e) {
            DataRecorder.logger.error("Error finding shop card index: " + e.getMessage());
            return -1;
        }
    }

    static String readCardIdAt(ShopScreen shopScreen, int index, boolean isColorless) {
        if (shopScreen == null || index < 0) {
            return null;
        }
        try {
            ArrayList<AbstractCard> cards = readCardListField(shopScreen, isColorless ? "colorlessCards" : "coloredCards");
            if (cards == null || index >= cards.size()) {
                return null;
            }
            AbstractCard card = cards.get(index);
            return card != null ? card.cardID : null;
        } catch (Exception e) {
            DataRecorder.logger.error("Error reading shop card at index: " + e.getMessage());
            return null;
        }
    }
}

@SpirePatch(
        clz = ShopScreen.class,
        method = "init"
)
class ShopInitPatch {

    @SpirePostfixPatch
    public static void Postfix(ShopScreen __instance) {
        if (DataRecorder.instance == null) {
            return;
        }
        DataRecorder.instance.recordShopVisit(
                ShopPatchUtils.readShopRelicOfferIds(__instance),
                ShopPatchUtils.readShopColoredCardOfferIds(__instance),
                ShopPatchUtils.readShopColorlessCardOfferIds(__instance),
                ShopPatchUtils.readShopPotionOfferIds(__instance)
        );
    }
}

@SpirePatch(
        clz = StoreRelic.class,
        method = "purchaseRelic"
)
class ShopPurchaseRelicPatch {
    private static int goldBefore = 0;
    private static String purchasedRelicId = null;

    @SpirePrefixPatch
    public static void Prefix(StoreRelic __instance) {
        goldBefore = AbstractDungeon.player != null ? AbstractDungeon.player.gold : 0;
        purchasedRelicId = (__instance != null && __instance.relic != null) ? __instance.relic.relicId : null;
    }

    @SpirePostfixPatch
    public static void Postfix(StoreRelic __instance) {
        if (
                DataRecorder.instance != null
                        && AbstractDungeon.player != null
                        && purchasedRelicId != null
                        && goldBefore > AbstractDungeon.player.gold
        ) {
            int goldSpent = goldBefore - AbstractDungeon.player.gold;
            DataRecorder.instance.recordShopPurchase("relic", purchasedRelicId, goldSpent);
            DataRecorder.instance.recordShopRelicPurchase(purchasedRelicId);
            if (__instance != null && !__instance.isPurchased && __instance.relic != null) {
                DataRecorder.instance.recordShopSurfacedRelic(__instance.relic.relicId);
            }
            DataRecorder.instance.logger.info("Purchased relic: " + purchasedRelicId + " for " + goldSpent + " gold");
        }
    }
}

@SpirePatch(
        clz = StorePotion.class,
        method = "purchasePotion"
)
class ShopPurchasePotionPatch {
    private static int goldBefore = 0;
    private static String purchasedPotionId = null;

    @SpirePrefixPatch
    public static void Prefix(StorePotion __instance) {
        goldBefore = AbstractDungeon.player != null ? AbstractDungeon.player.gold : 0;
        purchasedPotionId = (__instance != null && __instance.potion != null) ? __instance.potion.ID : null;
    }

    @SpirePostfixPatch
    public static void Postfix(StorePotion __instance) {
        if (
                DataRecorder.instance != null
                        && AbstractDungeon.player != null
                        && purchasedPotionId != null
                        && goldBefore > AbstractDungeon.player.gold
        ) {
            int goldSpent = goldBefore - AbstractDungeon.player.gold;
            DataRecorder.instance.recordShopPurchase("potion", purchasedPotionId, goldSpent);
            if (__instance != null && !__instance.isPurchased && __instance.potion != null) {
                DataRecorder.instance.recordShopSurfacedPotion(__instance.potion.ID);
            }
            DataRecorder.instance.logger.info("Purchased potion: " + purchasedPotionId + " for " + goldSpent + " gold");
        }
    }
}

@SpirePatch(
        clz = ShopScreen.class,
        method = "purchaseCard",
        paramtypez = {AbstractCard.class}
)
class ShopPurchaseCardPatch {
    private static int goldBefore = 0;
    private static String purchasedCardId = null;
    private static boolean purchasedWasColorless = false;
    private static int purchasedCardIndex = -1;

    @SpirePrefixPatch
    public static void Prefix(ShopScreen __instance, AbstractCard hoveredCard) {
        goldBefore = AbstractDungeon.player != null ? AbstractDungeon.player.gold : 0;
        purchasedCardId = hoveredCard != null ? hoveredCard.cardID : null;
        purchasedWasColorless = hoveredCard != null && hoveredCard.color == AbstractCard.CardColor.COLORLESS;
        purchasedCardIndex = ShopPatchUtils.findCardIndex(__instance, hoveredCard, purchasedWasColorless);
    }

    @SpirePostfixPatch
    public static void Postfix(ShopScreen __instance, AbstractCard hoveredCard) {
        if (
                DataRecorder.instance != null
                        && AbstractDungeon.player != null
                        && purchasedCardId != null
                        && goldBefore > AbstractDungeon.player.gold
        ) {
            int goldSpent = goldBefore - AbstractDungeon.player.gold;
            DataRecorder.instance.recordShopPurchase("card", purchasedCardId, goldSpent);
            if (hoveredCard != null) {
                DataRecorder.instance.recordCardObtain(hoveredCard, "shop");
            }
            if (AbstractDungeon.player.hasRelic("The Courier") && purchasedCardIndex >= 0) {
                String replacementCardId = ShopPatchUtils.readCardIdAt(__instance, purchasedCardIndex, purchasedWasColorless);
                if (replacementCardId != null) {
                    if (purchasedWasColorless) {
                        DataRecorder.instance.recordShopSurfacedColorlessCard(replacementCardId);
                    } else {
                        DataRecorder.instance.recordShopSurfacedColoredCard(replacementCardId);
                    }
                }
            }
            DataRecorder.instance.logger.info("Purchased card from shop: " + purchasedCardId + " for " + goldSpent + " gold");
        }
    }
}

@SpirePatch(
        clz = ShopScreen.class,
        method = "purgeCard"
)
class ShopScreenPurgeCardPatch {

    @SpirePostfixPatch
    public static void Postfix() {
        if (DataRecorder.instance != null) {
            try {
                Field purgeCostField = ShopScreen.class.getDeclaredField("actualPurgeCost");
                purgeCostField.setAccessible(true);
                int goldSpent = purgeCostField.getInt(null);
                DataRecorder.instance.recordShopPurge(goldSpent);
                DataRecorder.instance.logger.info("Purged card at shop for " + goldSpent + " gold on floor " + AbstractDungeon.floorNum);
            } catch (Exception e) {
                DataRecorder.logger.error("Error getting purge cost: " + e.getMessage());
                DataRecorder.instance.recordShopPurge(75);
            }
        }
    }
}
