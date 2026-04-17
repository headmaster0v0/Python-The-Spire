package stsrecorder.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.megacrit.cardcrawl.characters.AbstractPlayer;
import com.megacrit.cardcrawl.core.AbstractCreature;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import stsrecorder.DataRecorder;

@SpirePatch(
        clz = AbstractPlayer.class,
        method = "heal",
        paramtypez = {int.class}
)
class PlayerHealPatch {
    
    @SpirePostfixPatch
    public static void Postfix(AbstractPlayer __instance, int healAmount) {
        if (DataRecorder.instance != null && healAmount > 0) {
            DataRecorder.instance.recordHpChange(healAmount, "heal");
        }
    }
}

@SpirePatch(
        clz = AbstractCreature.class,
        method = "decreaseMaxHealth",
        paramtypez = {int.class}
)
class PlayerDecreaseMaxHpPatch {
    
    @SpirePostfixPatch
    public static void Postfix(AbstractCreature __instance, int amount) {
        if (DataRecorder.instance != null && amount > 0 && __instance.isPlayer) {
            DataRecorder.instance.recordHpChange(-amount, "decreaseMaxHp");
            DataRecorder.instance.logger.info("Max HP decreased by " + amount + " on floor " + AbstractDungeon.floorNum);
        }
    }
}

@SpirePatch(
        clz = AbstractCreature.class,
        method = "increaseMaxHp",
        paramtypez = {int.class, boolean.class}
)
class PlayerIncreaseMaxHpPatch {
    
    @SpirePostfixPatch
    public static void Postfix(AbstractCreature __instance, int amount, boolean showEffect) {
        if (DataRecorder.instance != null && amount > 0 && __instance.isPlayer) {
            DataRecorder.instance.recordHpChange(amount, "increaseMaxHp");
            DataRecorder.instance.logger.info("Max HP increased by " + amount + " on floor " + AbstractDungeon.floorNum);
        }
    }
}
