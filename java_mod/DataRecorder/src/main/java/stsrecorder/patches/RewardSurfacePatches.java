package stsrecorder.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.relics.AbstractRelic;
import com.megacrit.cardcrawl.rewards.RewardItem;
import com.megacrit.cardcrawl.rooms.TreasureRoom;
import com.megacrit.cardcrawl.rooms.TreasureRoomBoss;
import com.megacrit.cardcrawl.screens.select.BossRelicSelectScreen;
import stsrecorder.DataRecorder;

import java.util.ArrayList;
import java.util.List;

@SpirePatch(
        clz = RewardItem.class,
        method = "claimReward"
)
class TreasureRewardClaimPatch {

    @SpirePostfixPatch
    public static boolean Postfix(boolean __result, RewardItem __instance) {
        if (!__result || DataRecorder.instance == null || AbstractDungeon.getCurrRoom() == null) {
            return __result;
        }
        if (!(AbstractDungeon.getCurrRoom() instanceof TreasureRoom)) {
            return __result;
        }

        if (__instance.type == RewardItem.RewardType.RELIC && __instance.relic != null) {
            boolean isMainRelic = __instance.relicLink != null && __instance.relicLink.type == RewardItem.RewardType.SAPPHIRE_KEY;
            DataRecorder.instance.recordTreasureRoomRelicObtained(__instance.relic, isMainRelic);
        } else if (__instance.type == RewardItem.RewardType.SAPPHIRE_KEY && __instance.relicLink != null && __instance.relicLink.relic != null) {
            DataRecorder.instance.recordTreasureRoomSapphireKey(__instance.relicLink.relic.relicId);
        }
        return __result;
    }
}

@SpirePatch(
        clz = BossRelicSelectScreen.class,
        method = "relicObtainLogic"
)
class BossRelicPickPatch {

    @SpirePostfixPatch
    public static void Postfix(BossRelicSelectScreen __instance, AbstractRelic r) {
        if (DataRecorder.instance == null || r == null || !(AbstractDungeon.getCurrRoom() instanceof TreasureRoomBoss)) {
            return;
        }
        List<String> notPicked = new ArrayList<>();
        for (AbstractRelic otherRelic : __instance.relics) {
            if (otherRelic == null || otherRelic == r) {
                continue;
            }
            notPicked.add(otherRelic.relicId);
        }
        DataRecorder.instance.recordBossRelicChoice(r.relicId, notPicked, false);
    }
}

@SpirePatch(
        clz = BossRelicSelectScreen.class,
        method = "noPick"
)
class BossRelicSkipPatch {

    @SpirePostfixPatch
    public static void Postfix(BossRelicSelectScreen __instance) {
        if (DataRecorder.instance == null || !(AbstractDungeon.getCurrRoom() instanceof TreasureRoomBoss)) {
            return;
        }
        List<String> notPicked = new ArrayList<>();
        for (AbstractRelic otherRelic : __instance.relics) {
            if (otherRelic == null) {
                continue;
            }
            notPicked.add(otherRelic.relicId);
        }
        DataRecorder.instance.recordBossRelicChoice(null, notPicked, true);
    }
}
