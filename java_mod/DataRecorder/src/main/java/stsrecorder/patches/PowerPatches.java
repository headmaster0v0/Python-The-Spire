package stsrecorder.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.characters.AbstractPlayer;
import com.megacrit.cardcrawl.core.AbstractCreature;
import com.megacrit.cardcrawl.powers.AbstractPower;
import stsrecorder.DataRecorder;

@SpirePatch(
        clz = AbstractCreature.class,
        method = "addPower",
        paramtypez = {AbstractPower.class}
)
class PowerApplyPatch {

    @SpirePostfixPatch
    public static void Postfix(AbstractCreature __instance, AbstractPower power) {
        if (DataRecorder.instance != null && power != null) {
            String targetType = __instance instanceof AbstractPlayer ? "player" : "monster";
            DataRecorder.instance.recordPowerApplied(
                power.ID,
                power.amount,
                targetType,
                __instance.id
            );
        }
    }
}
