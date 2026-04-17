package stsrecorder.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.megacrit.cardcrawl.rewards.RewardItem;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import stsrecorder.DataRecorder;

@SpirePatch(
        clz = RewardItem.class,
        method = "claimReward"
)
class GoldRewardPatch {
    
    @SpirePostfixPatch
    public static void Postfix(RewardItem __instance) {
        if (DataRecorder.instance != null && __instance.type == RewardItem.RewardType.GOLD) {
            DataRecorder.instance.recordGoldGain(__instance.goldAmt, "reward");
        }
    }
}
