package stsrecorder.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.megacrit.cardcrawl.actions.AbstractGameAction;
import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.cards.DamageInfo;
import com.megacrit.cardcrawl.characters.AbstractPlayer;
import com.megacrit.cardcrawl.core.AbstractCreature;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.monsters.AbstractMonster;
import stsrecorder.DataRecorder;

@SpirePatch(
        clz = AbstractMonster.class,
        method = "damage",
        paramtypez = {DamageInfo.class}
)
class MonsterDamagePatch {

    @SpirePostfixPatch
    public static void Postfix(AbstractMonster __instance, DamageInfo info) {
        if (DataRecorder.instance != null && __instance != null) {
            String sourceName = "unknown";
            String sourceType = info.type != null ? info.type.name() : "UNKNOWN";
            
            if (info.name != null && !info.name.isEmpty()) {
                sourceName = info.name;
            } else if (info.owner != null) {
                if (info.owner.isPlayer) {
                    sourceName = "player";
                } else if (info.owner instanceof AbstractMonster) {
                    sourceName = ((AbstractMonster) info.owner).name;
                }
            }
            
            DataRecorder.instance.recordMonsterDamage(
                __instance.id,
                __instance.name,
                __instance.lastDamageTaken,
                false,
                sourceName,
                sourceType
            );
        }
    }
}

@SpirePatch(
        clz = AbstractPlayer.class,
        method = "damage",
        paramtypez = {DamageInfo.class}
)
class PlayerDamagePatch {

    @SpirePostfixPatch
    public static void Postfix(AbstractPlayer __instance, DamageInfo info) {
        if (DataRecorder.instance != null && __instance != null) {
            String sourceName = "unknown";
            String sourceType = info.type != null ? info.type.name() : "UNKNOWN";
            
            if (info.name != null && !info.name.isEmpty()) {
                sourceName = info.name;
            } else if (info.owner != null) {
                if (info.owner.isPlayer) {
                    sourceName = "player";
                } else if (info.owner instanceof AbstractMonster) {
                    sourceName = ((AbstractMonster) info.owner).name;
                }
            }
            
            DataRecorder.instance.recordMonsterDamage(
                "player",
                "Player",
                __instance.lastDamageTaken,
                false,
                sourceName,
                sourceType
            );
        }
    }
}

@SpirePatch(
        clz = AbstractPlayer.class,
        method = "draw",
        paramtypez = {int.class}
)
class PlayerDrawPatch {

    @SpirePostfixPatch
    public static void Postfix(AbstractPlayer __instance, int count) {
        if (DataRecorder.instance != null && count > 0) {
            DataRecorder.instance.recordCardDraw(count);
        }
    }
}
