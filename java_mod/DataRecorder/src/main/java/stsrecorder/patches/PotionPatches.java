package stsrecorder.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.megacrit.cardcrawl.characters.AbstractPlayer;
import com.megacrit.cardcrawl.potions.AbstractPotion;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import stsrecorder.DataRecorder;

@SpirePatch(
        clz = AbstractPlayer.class,
        method = "obtainPotion",
        paramtypez = {AbstractPotion.class}
)
class PlayerObtainPotionPatch {
    
    @SpirePostfixPatch
    public static void Postfix(AbstractPlayer __instance, AbstractPotion potionToObtain) {
        if (DataRecorder.instance != null && potionToObtain != null) {
            String source = "unknown";
            
            if (AbstractDungeon.screen == AbstractDungeon.CurrentScreen.SHOP) {
                source = "shop";
            } else if (AbstractDungeon.getCurrRoom() != null && AbstractDungeon.getCurrRoom().event != null) {
                source = "event";
            } else if (AbstractDungeon.getCurrRoom() != null) {
                source = "reward";
            }
            
            DataRecorder.instance.recordPotionObtain(potionToObtain, source);
            DataRecorder.instance.logger.info("Obtained potion: " + potionToObtain.name + " from " + source + " on floor " + AbstractDungeon.floorNum);
        }
    }
}
