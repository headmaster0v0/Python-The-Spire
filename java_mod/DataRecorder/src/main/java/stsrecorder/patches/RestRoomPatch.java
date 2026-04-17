package stsrecorder.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.megacrit.cardcrawl.ui.campfire.*;
import stsrecorder.DataRecorder;

@SpirePatch(
        clz = RestOption.class,
        method = "useOption"
)
class RestOptionPatch {
    
    @SpirePostfixPatch
    public static void Postfix(RestOption __instance) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.recordRestAction("REST");
        }
    }
}

@SpirePatch(
        clz = SmithOption.class,
        method = "useOption"
)
class SmithOptionPatch {
    
    @SpirePostfixPatch
    public static void Postfix(SmithOption __instance) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.recordRestAction("SMITH");
        }
    }
}

@SpirePatch(
        clz = LiftOption.class,
        method = "useOption"
)
class LiftOptionPatch {
    
    @SpirePostfixPatch
    public static void Postfix(LiftOption __instance) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.recordRestAction("LIFT");
        }
    }
}

@SpirePatch(
        clz = DigOption.class,
        method = "useOption"
)
class DigOptionPatch {
    
    @SpirePostfixPatch
    public static void Postfix(DigOption __instance) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.recordRestAction("DIG");
        }
    }
}

@SpirePatch(
        clz = RecallOption.class,
        method = "useOption"
)
class RecallOptionPatch {
    
    @SpirePostfixPatch
    public static void Postfix(RecallOption __instance) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.recordRestAction("RECALL");
        }
    }
}

@SpirePatch(
        clz = TokeOption.class,
        method = "useOption"
)
class TokeOptionPatch {
    
    @SpirePostfixPatch
    public static void Postfix(TokeOption __instance) {
        if (DataRecorder.instance != null) {
            DataRecorder.instance.recordRestAction("TOKE");
        }
    }
}
