package stsrecorder.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.cards.CardGroup;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import stsrecorder.DataRecorder;

@SpirePatch(
        clz = CardGroup.class,
        method = "moveToExhaustPile",
        paramtypez = {AbstractCard.class}
)
class CardExhaustPatch {
    
    @SpirePostfixPatch
    public static void Postfix(CardGroup __instance, AbstractCard c) {
        if (DataRecorder.instance != null && c != null) {
            DataRecorder.instance.recordCardExhaust(c.cardID);
            DataRecorder.instance.logger.info("Card exhausted: " + c.cardID + " on floor " + AbstractDungeon.floorNum);
        }
    }
}
