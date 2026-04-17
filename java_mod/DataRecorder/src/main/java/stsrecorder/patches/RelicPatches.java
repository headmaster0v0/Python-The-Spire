package stsrecorder.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePrefixPatch;
import com.megacrit.cardcrawl.core.AbstractCreature;
import com.megacrit.cardcrawl.characters.AbstractPlayer;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.relics.AbstractRelic;
import stsrecorder.DataRecorder;

@SpirePatch(
        clz = AbstractRelic.class,
        method = "obtain"
)
class RelicObtainPatch {
    
    @SpirePostfixPatch
    public static void Postfix(AbstractRelic __instance) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.recordRelicObtained(__instance);
        }
    }
}

@SpirePatch(
        clz = AbstractRelic.class,
        method = "instantObtain",
        paramtypez = {AbstractPlayer.class, int.class, boolean.class}
)
class RelicInstantObtainWithSlotPatch {

    @SpirePostfixPatch
    public static void Postfix(AbstractRelic __instance, AbstractPlayer player, int slot, boolean callOnEquip) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.recordRelicObtained(__instance);
        }
    }
}

@SpirePatch(
        clz = AbstractRelic.class,
        method = "instantObtain",
        paramtypez = {}
)
class RelicInstantObtainPatch {

    @SpirePostfixPatch
    public static void Postfix(AbstractRelic __instance) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.recordRelicObtained(__instance);
        }
    }
}

@SpirePatch(
        clz = AbstractRelic.class,
        method = "onEquip"
)
class RelicEquipPatch {
    
    private static int potionSlotsBefore = 0;
    
    @SpirePrefixPatch
    public static void Prefix(AbstractRelic __instance) {
        if (AbstractDungeon.player != null) {
            potionSlotsBefore = AbstractDungeon.player.potionSlots;
        }
    }
    
    @SpirePostfixPatch
    public static void Postfix(AbstractRelic __instance) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.recordRelicTrigger(__instance, "onEquip");
            
            if (AbstractDungeon.player != null) {
                int currentSlots = AbstractDungeon.player.potionSlots;
                if (currentSlots > potionSlotsBefore) {
                    int increase = currentSlots - potionSlotsBefore;
                    String source = __instance.relicId;
                    DataRecorder.instance.recordPotionSlotChange(increase, source);
                }
            }
        }
    }
}

@SpirePatch(
        clz = AbstractRelic.class,
        method = "onTrigger",
        paramtypez = {}
)
class RelicTriggerPatch {
    
    @SpirePostfixPatch
    public static void Postfix(AbstractRelic __instance) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.recordRelicTrigger(__instance, "onTrigger");
        }
    }
}

@SpirePatch(
        clz = AbstractRelic.class,
        method = "onTrigger",
        paramtypez = {AbstractCreature.class}
)
class RelicTriggerWithTargetPatch {
    
    @SpirePostfixPatch
    public static void Postfix(AbstractRelic __instance, AbstractCreature target) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.recordRelicTrigger(__instance, "onTrigger(target)");
        }
    }
}

@SpirePatch(
        clz = AbstractRelic.class,
        method = "flash"
)
class RelicFlashPatch {
    
    @SpirePostfixPatch
    public static void Postfix(AbstractRelic __instance) {
        if (DataRecorder.instance == null) {
            return;
        }
        try {
            if (
                    AbstractDungeon.getCurrRoom() != null
                            && AbstractDungeon.getCurrRoom().phase != null
                            && AbstractDungeon.getCurrRoom().phase.name().equals("COMBAT")
            ) {
                DataRecorder.instance.recordRelicTrigger(__instance, "flash");
            }
        } catch (Exception e) {
            // Ignore pre-room flash events during startup and screen transitions.
        }
    }
}
