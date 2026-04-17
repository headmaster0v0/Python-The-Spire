package stsrecorder.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePrefixPatch;
import com.megacrit.cardcrawl.neow.NeowEvent;
import com.megacrit.cardcrawl.neow.NeowReward;
import stsrecorder.DataRecorder;

import java.lang.reflect.Field;
import java.util.ArrayList;

@SpirePatch(
        clz = NeowEvent.class,
        method = "buttonEffect"
)
public class NeowEventPatch {
    
    @SpirePrefixPatch
    public static void Prefix(NeowEvent __instance, int buttonPressed) {
        if (DataRecorder.instance != null) {
            try {
                Field screenNumField = NeowEvent.class.getDeclaredField("screenNum");
                screenNumField.setAccessible(true);
                int screenNum = screenNumField.getInt(__instance);
                
                if (screenNum == 0) {
                    Field rewardsField = NeowEvent.class.getDeclaredField("rewards");
                    rewardsField.setAccessible(true);
                    ArrayList<NeowReward> rewards = (ArrayList<NeowReward>) rewardsField.get(__instance);
                    
                    if (rewards != null && buttonPressed >= 0 && buttonPressed < rewards.size()) {
                        NeowReward reward = rewards.get(buttonPressed);
                        String rewardType = reward.type != null ? reward.type.name() : "unknown";
                        DataRecorder.instance.recordNeowChoice(buttonPressed, rewardType, reward.optionLabel);
                    }
                }
            } catch (Exception e) {
                DataRecorder.logger.error("Error recording Neow choice: " + e.getMessage());
            }
        }
    }
}
