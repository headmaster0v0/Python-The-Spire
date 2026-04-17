package stsrecorder.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.megacrit.cardcrawl.actions.utility.UseCardAction;
import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.core.AbstractCreature;
import stsrecorder.DataRecorder;

@SpirePatch(
        clz = UseCardAction.class,
        method = SpirePatch.CONSTRUCTOR,
        paramtypez = {AbstractCard.class, AbstractCreature.class}
)
public class CardUsePatch {
    @SpirePostfixPatch
    public static void Postfix(UseCardAction __instance, AbstractCard card, AbstractCreature target) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.recordCardPlay(card);
        }
    }
}
