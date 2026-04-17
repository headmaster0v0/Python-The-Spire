package stsrecorder.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.random.Random;
import stsrecorder.DataRecorder;

public class RngLoggingPatches {

    private static String getRngType(Random rng) {
        if (AbstractDungeon.cardRng == rng) return "cardRng";
        if (AbstractDungeon.monsterRng == rng) return "monsterRng";
        if (AbstractDungeon.aiRng == rng) return "aiRng";
        if (AbstractDungeon.eventRng == rng) return "eventRng";
        if (AbstractDungeon.merchantRng == rng) return "merchantRng";
        if (AbstractDungeon.treasureRng == rng) return "treasureRng";
        if (AbstractDungeon.relicRng == rng) return "relicRng";
        if (AbstractDungeon.potionRng == rng) return "potionRng";
        if (AbstractDungeon.shuffleRng == rng) return "shuffleRng";
        if (AbstractDungeon.cardRandomRng == rng) return "cardRandomRng";
        if (AbstractDungeon.mapRng == rng) return "mapRng";
        if (AbstractDungeon.miscRng == rng) return "miscRng";
        if (AbstractDungeon.monsterHpRng == rng) return "monsterHpRng";
        return "unknown";
    }

    @SpirePatch(
            clz = Random.class,
            method = "random",
            paramtypez = {int.class}
    )
    public static class RandomIntPatch {
        @SpirePostfixPatch
        public static int Postfix(int __result, Random __instance, int range) {
            if (DataRecorder.instance != null) {
                DataRecorder.instance.recordRngCall(getRngType(__instance), __instance.counter, "random(int)", __result, range, null);
            }
            return __result;
        }
    }

    @SpirePatch(
            clz = Random.class,
            method = "random",
            paramtypez = {int.class, int.class}
    )
    public static class RandomIntRangePatch {
        @SpirePostfixPatch
        public static int Postfix(int __result, Random __instance, int start, int end) {
            if (DataRecorder.instance != null) {
                DataRecorder.instance.recordRngCall(getRngType(__instance), __instance.counter, "random(int,int)", __result, start, end);
            }
            return __result;
        }
    }

    @SpirePatch(
            clz = Random.class,
            method = "random",
            paramtypez = {long.class}
    )
    public static class RandomLongPatch {
        @SpirePostfixPatch
        public static long Postfix(long __result, Random __instance, long range) {
            if (DataRecorder.instance != null) {
                DataRecorder.instance.recordRngCall(getRngType(__instance), __instance.counter, "random(long)", __result, range, null);
            }
            return __result;
        }
    }

    @SpirePatch(
            clz = Random.class,
            method = "random",
            paramtypez = {long.class, long.class}
    )
    public static class RandomLongRangePatch {
        @SpirePostfixPatch
        public static long Postfix(long __result, Random __instance, long start, long end) {
            if (DataRecorder.instance != null) {
                DataRecorder.instance.recordRngCall(getRngType(__instance), __instance.counter, "random(long,long)", __result, start, end);
            }
            return __result;
        }
    }

    @SpirePatch(
            clz = Random.class,
            method = "randomLong",
            paramtypez = {}
    )
    public static class RandomLongNoArgPatch {
        @SpirePostfixPatch
        public static long Postfix(long __result, Random __instance) {
            if (DataRecorder.instance != null) {
                DataRecorder.instance.recordRngCall(getRngType(__instance), __instance.counter, "randomLong()", __result);
            }
            return __result;
        }
    }

    @SpirePatch(
            clz = Random.class,
            method = "randomBoolean",
            paramtypez = {}
    )
    public static class RandomBooleanPatch {
        @SpirePostfixPatch
        public static boolean Postfix(boolean __result, Random __instance) {
            if (DataRecorder.instance != null) {
                DataRecorder.instance.recordRngCall(getRngType(__instance), __instance.counter, "randomBoolean()", __result);
            }
            return __result;
        }
    }

    @SpirePatch(
            clz = Random.class,
            method = "randomBoolean",
            paramtypez = {float.class}
    )
    public static class RandomBooleanChancePatch {
        @SpirePostfixPatch
        public static boolean Postfix(boolean __result, Random __instance, float chance) {
            if (DataRecorder.instance != null) {
                DataRecorder.instance.recordRngCall(getRngType(__instance), __instance.counter, "randomBoolean(float)", __result, chance, null);
            }
            return __result;
        }
    }

    @SpirePatch(
            clz = Random.class,
            method = "random",
            paramtypez = {}
    )
    public static class RandomFloatPatch {
        @SpirePostfixPatch
        public static float Postfix(float __result, Random __instance) {
            if (DataRecorder.instance != null) {
                DataRecorder.instance.recordRngCall(getRngType(__instance), __instance.counter, "random()", __result);
            }
            return __result;
        }
    }

    @SpirePatch(
            clz = Random.class,
            method = "random",
            paramtypez = {float.class}
    )
    public static class RandomFloatRangePatch {
        @SpirePostfixPatch
        public static float Postfix(float __result, Random __instance, float range) {
            if (DataRecorder.instance != null) {
                DataRecorder.instance.recordRngCall(getRngType(__instance), __instance.counter, "random(float)", __result, range, null);
            }
            return __result;
        }
    }

    @SpirePatch(
            clz = Random.class,
            method = "random",
            paramtypez = {float.class, float.class}
    )
    public static class RandomFloatRange2Patch {
        @SpirePostfixPatch
        public static float Postfix(float __result, Random __instance, float start, float end) {
            if (DataRecorder.instance != null) {
                DataRecorder.instance.recordRngCall(getRngType(__instance), __instance.counter, "random(float,float)", __result, start, end);
            }
            return __result;
        }
    }
}
