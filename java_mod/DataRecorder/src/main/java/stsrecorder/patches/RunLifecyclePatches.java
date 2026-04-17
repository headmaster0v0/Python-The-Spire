package stsrecorder.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.monsters.MonsterGroup;
import com.megacrit.cardcrawl.saveAndContinue.SaveFile;
import com.megacrit.cardcrawl.screens.DeathScreen;
import com.megacrit.cardcrawl.screens.GameOverScreen;
import com.megacrit.cardcrawl.screens.VictoryScreen;
import stsrecorder.DataRecorder;

@SpirePatch(
        clz = VictoryScreen.class,
        method = SpirePatch.CONSTRUCTOR,
        paramtypez = {MonsterGroup.class}
)
class VictoryScreenSavePatch {

    @SpirePostfixPatch
    public static void Postfix(VictoryScreen __instance, MonsterGroup m) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.finishRunAndSave("victory", "VictoryScreen");
        }
    }
}

@SpirePatch(
        clz = DeathScreen.class,
        method = SpirePatch.CONSTRUCTOR,
        paramtypez = {MonsterGroup.class}
)
class DeathScreenSavePatch {

    @SpirePostfixPatch
    public static void Postfix(DeathScreen __instance, MonsterGroup m) {
        if (DataRecorder.instance != null) {
            String runResult = GameOverScreen.isVictory ? "victory" : "death";
            DataRecorder.instance.finishRunAndSave(runResult, "DeathScreen");
        }
    }
}

@SpirePatch(
        clz = AbstractDungeon.class,
        method = "nextRoomTransition",
        paramtypez = {SaveFile.class}
)
class NextRoomTransitionPathPatch {

    @SpirePostfixPatch
    public static void Postfix(AbstractDungeon __instance, SaveFile saveFile) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.recordPathTaken();
        }
    }
}
