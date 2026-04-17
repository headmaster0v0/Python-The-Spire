package stsrecorder.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.megacrit.cardcrawl.actions.GameActionManager;
import stsrecorder.DataRecorder;

@SpirePatch(
        clz = GameActionManager.class,
        method = "endTurn"
)
public class TurnEndPatch {
    @SpirePostfixPatch
    public static void Postfix(GameActionManager __instance) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.incrementTurn();
        }
    }
}
