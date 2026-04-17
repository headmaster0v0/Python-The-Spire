package stsrecorder.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.screens.CardRewardScreen;
import stsrecorder.DataRecorder;

import java.util.ArrayList;
import java.util.List;

@SpirePatch(
        clz = CardRewardScreen.class,
        method = "acquireCard",
        paramtypez = {AbstractCard.class}
)
class CardRewardAcquirePatch {
    
    @SpirePostfixPatch
    public static void Postfix(CardRewardScreen __instance, AbstractCard hoveredCard) {
        if (DataRecorder.instance != null && hoveredCard != null) {
            DataRecorder.instance.recordCardObtain(hoveredCard, "reward");
            DataRecorder.instance.recordCardReward(
                hoveredCard.cardID,
                hoveredCard.upgraded,
                false,
                "pick",
                CardRewardPatchSupport.collectNotPickedCardIds(__instance, hoveredCard)
            );
            DataRecorder.instance.logger.info("Card chosen from reward: " + hoveredCard.cardID);
        }
    }
}

@SpirePatch(
        clz = CardRewardScreen.class,
        method = "skippedCards"
)
class CardRewardSkippedPatch {

    @SpirePostfixPatch
    public static void Postfix(CardRewardScreen __instance) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.recordCardReward(
                "SKIP",
                false,
                true,
                "skip",
                CardRewardPatchSupport.collectNotPickedCardIds(__instance, null)
            );
        }
    }
}

@SpirePatch(
        clz = CardRewardScreen.class,
        method = "closeFromBowlButton"
)
class CardRewardSingingBowlPatch {

    @SpirePostfixPatch
    public static void Postfix(CardRewardScreen __instance) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.recordCardReward(
                "Singing Bowl",
                false,
                true,
                "singing_bowl",
                CardRewardPatchSupport.collectNotPickedCardIds(__instance, null)
            );
        }
    }
}

class CardRewardPatchSupport {
    private CardRewardPatchSupport() {
    }

    static List<String> collectNotPickedCardIds(CardRewardScreen screen, AbstractCard pickedCard) {
        List<String> cardIds = new ArrayList<>();
        if (screen == null || screen.rewardGroup == null) {
            return cardIds;
        }
        for (AbstractCard card : screen.rewardGroup) {
            if (card == null || card == pickedCard) {
                continue;
            }
            cardIds.add(card.cardID);
        }
        return cardIds;
    }
}
