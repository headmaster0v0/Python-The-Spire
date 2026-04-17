package stsrecorder.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.megacrit.cardcrawl.relics.AbstractRelic;
import com.megacrit.cardcrawl.rooms.TreasureRoom;
import com.megacrit.cardcrawl.rooms.TreasureRoomBoss;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import stsrecorder.DataRecorder;

@SpirePatch(
        clz = TreasureRoom.class,
        method = "onPlayerEntry"
)
class TreasureRoomEntryPatch {
    
    @SpirePostfixPatch
    public static void Postfix(TreasureRoom __instance) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.recordTreasureRoom("TreasureRoom");
            DataRecorder.instance.logger.info("Entered treasure room on floor " + AbstractDungeon.floorNum);
        }
    }
}

@SpirePatch(
        clz = TreasureRoomBoss.class,
        method = "onPlayerEntry"
)
class TreasureRoomBossEntryPatch {
    
    @SpirePostfixPatch
    public static void Postfix(TreasureRoomBoss __instance) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.recordTreasureRoom("TreasureRoomBoss");
            DataRecorder.instance.logger.info("Entered boss treasure room on floor " + AbstractDungeon.floorNum);
        }
    }
}
