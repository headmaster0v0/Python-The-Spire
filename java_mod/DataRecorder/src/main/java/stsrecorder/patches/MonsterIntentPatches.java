package stsrecorder.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.monsters.AbstractMonster;
import stsrecorder.DataRecorder;

@SpirePatch(
        clz = AbstractMonster.class,
        method = "rollMove"
)
public class MonsterIntentPatches {

    public static class IntentRecord {
        public int floor;
        public String monsterId;
        public String monsterName;
        public String intent;
        public byte moveIndex;
        public int baseDamage;
        public int aiRngCounter;
        public long timestamp;

        public IntentRecord(AbstractMonster monster) {
            this.floor = AbstractDungeon.floorNum;
            this.monsterId = monster.id;
            this.monsterName = monster.name;
            this.intent = monster.intent != null ? monster.intent.name() : "UNKNOWN";
            this.moveIndex = monster.nextMove;
            this.baseDamage = getBaseDamage(monster);
            this.aiRngCounter = AbstractDungeon.aiRng != null ? AbstractDungeon.aiRng.counter : 0;
            this.timestamp = System.currentTimeMillis();
        }

        private int getBaseDamage(AbstractMonster monster) {
            try {
                if (monster.intent == AbstractMonster.Intent.ATTACK ||
                    monster.intent == AbstractMonster.Intent.ATTACK_BUFF ||
                    monster.intent == AbstractMonster.Intent.ATTACK_DEFEND) {
                    return monster.getIntentDmg();
                }
            } catch (Exception e) {
            }
            return 0;
        }
    }

    @SpirePostfixPatch
    public static void Postfix(AbstractMonster __instance) {
        IntentRecord record = new IntentRecord(__instance);
        
        if (DataRecorder.instance != null) {
            DataRecorder.instance.recordMonsterIntent(record);
        }
        
        if (DataRecorder.logger != null) {
            DataRecorder.logger.info("Monster intent: " + record.monsterName + " -> " + record.intent +
                    " (move=" + record.moveIndex + ", dmg=" + record.baseDamage + ", aiRng=" + record.aiRngCounter + ")");
        }
    }

    @SpirePatch(
            clz = AbstractMonster.class,
            method = "createIntent"
    )
    public static class CreateIntentPatch {
        @SpirePostfixPatch
        public static void Postfix(AbstractMonster __instance) {
            IntentRecord record = new IntentRecord(__instance);
            
            if (DataRecorder.instance != null) {
                DataRecorder.instance.recordMonsterIntent(record);
            }
        
            if (DataRecorder.logger != null) {
                DataRecorder.logger.debug("Monster createIntent: " + record.monsterName + " -> " + record.intent);
            }
        }
    }
}
