package stsrecorder;

import basemod.BaseMod;
import basemod.interfaces.*;
import com.badlogic.gdx.graphics.g2d.SpriteBatch;
import com.evacipated.cardcrawl.modthespire.lib.SpireInitializer;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.core.Settings;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.helpers.SeedHelper;
import com.megacrit.cardcrawl.map.MapEdge;
import com.megacrit.cardcrawl.map.MapRoomNode;
import com.megacrit.cardcrawl.monsters.AbstractMonster;
import com.megacrit.cardcrawl.potions.AbstractPotion;
import com.megacrit.cardcrawl.relics.AbstractRelic;
import com.megacrit.cardcrawl.rooms.AbstractRoom;
import com.megacrit.cardcrawl.rooms.RestRoom;
import com.megacrit.cardcrawl.vfx.cardManip.ShowCardAndObtainEffect;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import stsrecorder.patches.MonsterIntentPatches;

import java.io.File;
import java.io.OutputStreamWriter;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.LinkedHashSet;

@SpireInitializer
public class DataRecorder implements
        PostInitializeSubscriber,
        PostDungeonInitializeSubscriber,
        PostBattleSubscriber,
        PostRenderSubscriber,
        PreStartGameSubscriber,
        PostPotionUseSubscriber,
        PostExhaustSubscriber {

    public static final Logger logger = LogManager.getLogger(DataRecorder.class.getName());
    public static DataRecorder instance;
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    private GameDataLog currentLog;
    private String outputDir;
    private final Set<String> recordedPathKeys = new LinkedHashSet<>();
    private final Set<String> recordedRelicObtainKeys = new LinkedHashSet<>();

    public static void initialize() {
        instance = new DataRecorder();
    }

    public DataRecorder() {
        BaseMod.subscribe(this);
        outputDir = System.getProperty("user.home") + "/sts_data_logs";
        new File(outputDir).mkdirs();
        logger.info("DataRecorder initialized. Output dir: " + outputDir);
    }

    @Override
    public void receivePostInitialize() {
        logger.info("DataRecorder post-initialize complete");
    }

    @Override
    public void receivePreStartGame() {
        currentLog = new GameDataLog();
        currentLog.seed = Settings.seed != null ? Settings.seed : 0L;
        currentLog.seedString = SeedHelper.getUserFacingSeedString();
        recordedPathKeys.clear();
        recordedRelicObtainKeys.clear();

        logger.info("New run started. Seed: " + currentLog.seedString);

        captureRngState("dungeon_init");
    }

    @Override
    public void receivePostDungeonInitialize() {
        if (currentLog != null) {
            if (AbstractDungeon.player != null) {
                currentLog.character = AbstractDungeon.player.chosenClass.name();
            }
            captureMapState();
            captureInitialDeck();
            captureInitialRelics();
        }
    }

    public void captureInitialDeck() {
        if (currentLog == null || AbstractDungeon.player == null) return;
        
        currentLog.initialDeck.clear();
        for (AbstractCard card : AbstractDungeon.player.masterDeck.group) {
            CardInfo info = new CardInfo();
            info.cardId = card.cardID;
            info.upgraded = card.upgraded;
            currentLog.initialDeck.add(info);
        }
        logger.info("Initial deck captured: " + currentLog.initialDeck.size() + " cards");
    }

    public void captureInitialRelics() {
        if (currentLog == null || AbstractDungeon.player == null) return;
        
        currentLog.initialRelics.clear();
        for (AbstractRelic relic : AbstractDungeon.player.relics) {
            currentLog.initialRelics.add(relic.relicId);
        }
        logger.info("Initial relics captured: " + currentLog.initialRelics.size() + " relics");
    }

    public void captureMapState() {
        if (currentLog == null || AbstractDungeon.map == null) return;

        int actNum = AbstractDungeon.actNum;
        currentLog.mapNodes.clear();
        
        for (int y = 0; y < AbstractDungeon.map.size(); y++) {
            List<MapNodeLog> row = new ArrayList<>();
            for (int x = 0; x < AbstractDungeon.map.get(y).size(); x++) {
                MapRoomNode node = AbstractDungeon.map.get(y).get(x);
                MapNodeLog nodeLog = new MapNodeLog();
                nodeLog.x = x;
                nodeLog.y = y;
                
                if (node.getRoom() != null) {
                    nodeLog.roomType = node.getRoom().getClass().getSimpleName();
                }
                
                nodeLog.hasEmeraldKey = node.hasEmeraldKey;
                
                if (node.getEdges() != null) {
                    for (MapEdge edge : node.getEdges()) {
                        MapEdgeLog edgeLog = new MapEdgeLog();
                        edgeLog.dstX = edge.dstX;
                        edgeLog.dstY = edge.dstY;
                        nodeLog.edges.add(edgeLog);
                    }
                }
                
                row.add(nodeLog);
            }
            currentLog.mapNodes.add(row);
        }
        
        // Save per-act map (preserves Act 1 map when later acts overwrite mapNodes)
        currentLog.mapNodesByAct.put(String.valueOf(actNum), new ArrayList<>(currentLog.mapNodes));
        
        // Debug: log row 0 edges and actNum for verification
        currentLog.mapDebugActNum = actNum;
        currentLog.mapDebugRow0Edges.clear();
        for (int x = 0; x < AbstractDungeon.map.get(0).size(); x++) {
            MapRoomNode node = AbstractDungeon.map.get(0).get(x);
            if (node.hasEdges()) {
                StringBuilder sb = new StringBuilder();
                sb.append("(").append(x).append(",0):[");
                boolean first = true;
                for (MapEdge edge : node.getEdges()) {
                    if (!first) sb.append(",");
                    sb.append("(").append(edge.dstX).append(",").append(edge.dstY).append(")");
                    first = false;
                }
                sb.append("]");
                currentLog.mapDebugRow0Edges.add(sb.toString());
            }
        }
        
        // Also log total edges per row
        currentLog.mapDebugEdgesPerRow.clear();
        for (int y = 0; y < AbstractDungeon.map.size(); y++) {
            int count = 0;
            for (MapRoomNode node : AbstractDungeon.map.get(y)) {
                count += node.getEdges().size();
            }
            currentLog.mapDebugEdgesPerRow.add(count);
        }
        
        logger.info("Map state captured for act " + actNum + ": " + currentLog.mapNodes.size() + " rows");
    }

    public void recordPathTaken() {
        if (currentLog == null) return;
        if (AbstractDungeon.floorNum <= 0) return;
        if (AbstractDungeon.currMapNode == null) return;

        PathStepLog step = new PathStepLog();
        step.floor = AbstractDungeon.floorNum;
        step.act = AbstractDungeon.actNum;
        MapRoomNode node = AbstractDungeon.currMapNode;
        step.x = node.x;
        step.y = node.y;

        if (step.y < 0) return;
        if (node.getRoom() != null) {
            step.roomType = node.getRoom().getClass().getSimpleName();
        }

        String key = step.floor + ":" + step.act + ":" + step.x + ":" + step.y + ":" + step.roomType;
        if (recordedPathKeys.contains(key)) {
            logger.debug("Skipping duplicate path step: " + key);
            return;
        }

        recordedPathKeys.add(key);
        currentLog.pathTaken.add(step);

        logger.info("Path step recorded: floor=" + step.floor + " x=" + step.x + " y=" + step.y);
    }

    @Override
    public void receivePostBattle(AbstractRoom room) {
        if (currentLog == null) return;

        BattleLog battleLog = new BattleLog();
        battleLog.floor = AbstractDungeon.floorNum;
        battleLog.roomType = room.getClass().getSimpleName();

        if (AbstractDungeon.getCurrRoom() != null && AbstractDungeon.getCurrRoom().monsters != null) {
            for (AbstractMonster m : AbstractDungeon.getCurrRoom().monsters.monsters) {
                MonsterLog ml = new MonsterLog();
                ml.id = m.id;
                ml.name = m.name;
                ml.startingHp = m.maxHealth;
                ml.endingHp = m.currentHealth;
                ml.isDead = m.isDead || m.isDying;
                battleLog.monsters.add(ml);
            }
        }

        battleLog.playerEndHp = AbstractDungeon.player.currentHealth;
        battleLog.turnCount = currentLog.currentTurn;
        battleLog.cardsPlayedThisBattle = new ArrayList<>(currentLog.currentBattleCards);
        battleLog.rngStateEnd = captureRngStateSnapshot();

        currentLog.battles.add(battleLog);
        currentLog.currentBattleCards.clear();
        currentLog.currentTurn = 0;

        captureRngState("post_battle_floor_" + AbstractDungeon.floorNum);
    }

    public void recordCardPlay(AbstractCard card) {
        if (currentLog == null) return;

        CardPlayLog cp = new CardPlayLog();
        cp.cardId = card.cardID;
        cp.cost = card.costForTurn;
        cp.upgraded = card.upgraded;
        cp.floor = AbstractDungeon.floorNum;
        cp.turn = currentLog.currentTurn;
        cp.timestamp = System.currentTimeMillis();

        currentLog.currentBattleCards.add(cp);
        currentLog.allCardPlays.add(cp);

        logger.debug("Card played: " + card.cardID + " on floor " + cp.floor);
    }

    public void incrementTurn() {
        if (currentLog != null) {
            currentLog.currentTurn++;
        }
    }

    public void recordRngCall(String rngType, int counter, String method, Object returnValue) {
        recordRngCall(rngType, counter, method, returnValue, null, null);
    }

    public void recordRngCall(String rngType, int counter, String method, Object returnValue, Object param1, Object param2) {
        if (currentLog == null) return;

        RngCallLog call = new RngCallLog();
        call.rngType = rngType;
        call.counter = counter;
        call.method = method;
        call.returnValue = returnValue;
        call.param1 = param1;
        call.param2 = param2;
        call.floor = AbstractDungeon.floorNum;
        call.turn = currentLog.currentTurn;
        call.timestamp = System.currentTimeMillis();

        currentLog.rngCalls.add(call);
    }

    public void recordCardReward(String cardId, boolean upgraded, boolean skipped) {
        recordCardReward(cardId, upgraded, skipped, skipped ? "skip" : "pick", null);
    }

    public void recordCardReward(
            String cardId,
            boolean upgraded,
            boolean skipped,
            String choiceType,
            List<String> notPickedCardIds
    ) {
        if (currentLog == null) return;

        CardRewardLog reward = new CardRewardLog();
        reward.cardId = cardId;
        reward.upgraded = upgraded;
        reward.skipped = skipped;
        reward.choiceType = choiceType;
        if (notPickedCardIds != null) {
            reward.notPickedCardIds.addAll(notPickedCardIds);
        }
        reward.floor = AbstractDungeon.floorNum;
        reward.timestamp = System.currentTimeMillis();

        currentLog.cardRewards.add(reward);
        logger.info("Card reward: " + cardId + " (skipped=" + skipped + ") on floor " + reward.floor);
    }

    public void recordPotionUse(AbstractPotion potion) {
        if (currentLog == null) return;

        PotionUseLog use = new PotionUseLog();
        use.potionId = potion.ID;
        use.potionName = potion.name;
        use.floor = AbstractDungeon.floorNum;
        use.turn = currentLog.currentTurn;
        use.timestamp = System.currentTimeMillis();

        currentLog.potionUses.add(use);
        logger.info("Potion used: " + potion.name + " on floor " + use.floor);
    }

    public void recordRelicObtained(AbstractRelic relic) {
        if (currentLog == null || relic == null) return;
        if (!markRelicObtainedRecorded(relic)) {
            logger.debug("Skipping duplicate relic obtain log for " + relic.relicId + " on floor " + AbstractDungeon.floorNum);
            return;
        }

        String source = determineRelicSource(relic);
        if (source == null || source.isEmpty()) {
            source = "unknown";
        }

        RelicLog log = new RelicLog();
        log.relicId = relic.relicId;
        log.relicName = relic.name;
        log.floor = AbstractDungeon.floorNum;
        log.action = "obtained";
        log.source = source;
        log.timestamp = System.currentTimeMillis();

        currentLog.relicChanges.add(log);
        logger.info("Relic obtained: " + relic.name + " from " + source + " on floor " + log.floor);
    }

    private boolean markRelicObtainedRecorded(AbstractRelic relic) {
        String key = AbstractDungeon.floorNum + ":" + System.identityHashCode(relic);
        return recordedRelicObtainKeys.add(key);
    }

    private AbstractRoom safeGetCurrentRoom() {
        try {
            return AbstractDungeon.getCurrRoom();
        } catch (Exception e) {
            return null;
        }
    }

    private String determineRelicSource(AbstractRelic relic) {
        if (AbstractDungeon.screen == AbstractDungeon.CurrentScreen.SHOP) {
            return "shop";
        }

        AbstractRoom currentRoom = safeGetCurrentRoom();
        if (currentRoom == null) {
            if (AbstractDungeon.floorNum <= 0) {
                return "starter";
            }
            return "unknown";
        }

        if (
                relic != null
                        && !"Calling Bell".equals(relic.relicId)
                        && AbstractDungeon.player != null
                        && AbstractDungeon.player.hasRelic("Calling Bell")
                        && currentRoom instanceof com.megacrit.cardcrawl.rooms.MonsterRoomBoss
        ) {
            return "calling_bell";
        }

        if (currentRoom instanceof com.megacrit.cardcrawl.rooms.TreasureRoom) {
            return "treasure";
        }
        if (currentRoom instanceof com.megacrit.cardcrawl.rooms.RestRoom) {
            return "rest";
        }
        if (currentRoom.event != null) {
            return "event";
        }
        if (currentRoom instanceof com.megacrit.cardcrawl.rooms.MonsterRoomElite) {
            return "elite";
        }
        if (currentRoom instanceof com.megacrit.cardcrawl.rooms.MonsterRoomBoss) {
            return "boss";
        }
        if (currentRoom instanceof com.megacrit.cardcrawl.rooms.MonsterRoom) {
            return "combat";
        }

        return "unknown";
    }

    public void recordPotionSlotChange(int amount, String source) {
        if (currentLog == null) return;

        PotionSlotChangeLog log = new PotionSlotChangeLog();
        log.amount = amount;
        log.source = source;
        log.floor = AbstractDungeon.floorNum;
        log.slotsAfter = AbstractDungeon.player.potionSlots;
        log.timestamp = System.currentTimeMillis();

        currentLog.potionSlotChanges.add(log);
        logger.info("Potion slot change: " + amount + " from " + source + " on floor " + log.floor + " (total: " + log.slotsAfter + ")");
    }

    public void recordRelicTrigger(AbstractRelic relic, String triggerType) {
        if (currentLog == null) return;

        RelicLog log = new RelicLog();
        log.relicId = relic.relicId;
        log.relicName = relic.name;
        log.floor = AbstractDungeon.floorNum;
        log.action = "triggered:" + triggerType;
        log.turn = currentLog.currentTurn;
        log.timestamp = System.currentTimeMillis();

        currentLog.relicChanges.add(log);
        logger.debug("Relic triggered: " + relic.name + " (" + triggerType + ") on floor " + log.floor);
    }

    public void recordEventChoice(String eventId, String eventName, int choiceIndex, String choiceText) {
        if (currentLog == null) return;

        EventChoiceLog log = new EventChoiceLog();
        log.eventId = eventId;
        log.eventName = eventName;
        log.choiceIndex = choiceIndex;
        log.choiceText = choiceText;
        log.floor = AbstractDungeon.floorNum;
        log.timestamp = System.currentTimeMillis();

        currentLog.eventChoices.add(log);
        rebuildEventSummaryForFloor(log.floor);
        logger.info("Event choice: " + eventName + " choice=" + choiceIndex + " on floor " + log.floor);
    }

    private void rebuildEventSummaries() {
        if (currentLog == null) return;

        currentLog.eventSummaries.clear();
        LinkedHashSet<Integer> floors = new LinkedHashSet<>();
        for (EventChoiceLog eventChoice : currentLog.eventChoices) {
            floors.add(eventChoice.floor);
        }
        for (Integer floor : floors) {
            EventChoiceLog summary = selectPrimaryEventChoiceForFloor(floor);
            if (summary != null) {
                currentLog.eventSummaries.add(copyEventChoice(summary));
            }
        }
    }

    private void rebuildEventSummaryForFloor(int floor) {
        if (currentLog == null) return;

        EventChoiceLog summary = selectPrimaryEventChoiceForFloor(floor);
        currentLog.eventSummaries.removeIf(event -> event.floor == floor);
        if (summary != null) {
            currentLog.eventSummaries.add(copyEventChoice(summary));
        }
    }

    private EventChoiceLog selectPrimaryEventChoiceForFloor(int floor) {
        if (currentLog == null) return null;

        List<EventChoiceLog> eventsOnFloor = new ArrayList<>();
        for (EventChoiceLog eventChoice : currentLog.eventChoices) {
            if (eventChoice.floor == floor) {
                eventsOnFloor.add(eventChoice);
            }
        }
        if (eventsOnFloor.isEmpty()) {
            return null;
        }
        if (floor == 0 && "NeowEvent".equals(eventsOnFloor.get(0).eventId) && eventsOnFloor.size() > 1) {
            for (EventChoiceLog eventChoice : eventsOnFloor) {
                if (eventChoice.choiceText != null && eventChoice.choiceText.contains("#g")) {
                    return eventChoice;
                }
            }
            return eventsOnFloor.get(eventsOnFloor.size() - 1);
        }
        return eventsOnFloor.get(0);
    }

    private EventChoiceLog copyEventChoice(EventChoiceLog source) {
        EventChoiceLog copy = new EventChoiceLog();
        copy.eventId = source.eventId;
        copy.eventName = source.eventName;
        copy.choiceIndex = source.choiceIndex;
        copy.choiceText = source.choiceText;
        copy.floor = source.floor;
        copy.timestamp = source.timestamp;
        return copy;
    }

    public void recordRestAction(String action) {
        if (currentLog == null) return;

        RestActionLog log = new RestActionLog();
        log.action = action;
        log.floor = AbstractDungeon.floorNum;
        log.hpBefore = AbstractDungeon.player.currentHealth;
        log.maxHp = AbstractDungeon.player.maxHealth;
        log.timestamp = System.currentTimeMillis();

        currentLog.restActions.add(log);
        logger.info("Rest action: " + action + " on floor " + log.floor);
    }

    public void recordNeowChoice(int choiceIndex, String rewardType, String description) {
        if (currentLog == null) return;

        NeowChoiceLog log = new NeowChoiceLog();
        log.choiceIndex = choiceIndex;
        log.rewardType = rewardType;
        log.description = description;
        log.timestamp = System.currentTimeMillis();

        currentLog.neowChoice = log;
        logger.info("Neow choice: " + rewardType + " - " + description);
    }

    public void recordShopPurchase(String itemType, String itemId, int goldSpent) {
        if (currentLog == null) return;

        ShopPurchaseLog log = new ShopPurchaseLog();
        log.itemType = itemType;
        log.itemId = itemId;
        log.floor = AbstractDungeon.floorNum;
        log.gold = AbstractDungeon.player.gold;
        log.goldSpent = goldSpent;
        log.timestamp = System.currentTimeMillis();

        currentLog.shopPurchases.add(log);
        logger.info("Shop purchase: " + itemType + " - " + itemId + " for " + goldSpent + " gold on floor " + log.floor);
    }

    private ShopVisitLog latestShopVisitLog() {
        if (currentLog == null || currentLog.shopVisits.isEmpty()) return null;
        ShopVisitLog latest = currentLog.shopVisits.get(currentLog.shopVisits.size() - 1);
        if (latest.floor != AbstractDungeon.floorNum) return null;
        return latest;
    }

    private ShopVisitLog ensureCurrentShopVisitLog() {
        ShopVisitLog log = latestShopVisitLog();
        if (log == null) {
            log = new ShopVisitLog();
            log.floor = AbstractDungeon.floorNum;
            log.timestamp = System.currentTimeMillis();
            currentLog.shopVisits.add(log);
        }
        return log;
    }

    private void appendUnique(List<String> target, String value) {
        if (value != null && !target.contains(value)) {
            target.add(value);
        }
    }

    private void appendUnique(List<String> target, List<String> values) {
        if (values == null) return;
        for (String value : values) {
            appendUnique(target, value);
        }
    }

    private void appendAll(List<String> target, List<String> values) {
        if (values == null) return;
        for (String value : values) {
            if (value != null) {
                target.add(value);
            }
        }
    }

    public void recordShopVisit(
            List<String> initialRelicOfferIds,
            List<String> initialColoredCardOfferIds,
            List<String> initialColorlessCardOfferIds,
            List<String> initialPotionOfferIds
    ) {
        if (currentLog == null) return;
        boolean hasAnyOffers =
                (initialRelicOfferIds != null && !initialRelicOfferIds.isEmpty())
                        || (initialColoredCardOfferIds != null && !initialColoredCardOfferIds.isEmpty())
                        || (initialColorlessCardOfferIds != null && !initialColorlessCardOfferIds.isEmpty())
                        || (initialPotionOfferIds != null && !initialPotionOfferIds.isEmpty());
        if (!hasAnyOffers) return;

        ShopVisitLog log = ensureCurrentShopVisitLog();
        if (log.initialRelicOfferIds.isEmpty()) {
            appendAll(log.initialRelicOfferIds, initialRelicOfferIds);
        }
        if (log.initialColoredCardOfferIds.isEmpty()) {
            appendAll(log.initialColoredCardOfferIds, initialColoredCardOfferIds);
        }
        if (log.initialColorlessCardOfferIds.isEmpty()) {
            appendAll(log.initialColorlessCardOfferIds, initialColorlessCardOfferIds);
        }
        if (log.initialPotionOfferIds.isEmpty()) {
            appendAll(log.initialPotionOfferIds, initialPotionOfferIds);
        }
        if (log.surfacedRelicIds.isEmpty()) {
            appendUnique(log.surfacedRelicIds, initialRelicOfferIds);
        }
        if (log.surfacedColoredCardIds.isEmpty()) {
            appendAll(log.surfacedColoredCardIds, initialColoredCardOfferIds);
        }
        if (log.surfacedColorlessCardIds.isEmpty()) {
            appendAll(log.surfacedColorlessCardIds, initialColorlessCardOfferIds);
        }
        if (log.surfacedPotionIds.isEmpty()) {
            appendAll(log.surfacedPotionIds, initialPotionOfferIds);
        }
        logger.info("Shop visit recorded on floor " + log.floor + " with full merchant surface");
    }

    public void recordShopRelicPurchase(String relicId) {
        if (currentLog == null || relicId == null) return;
        ShopVisitLog log = ensureCurrentShopVisitLog();
        log.purchasedRelicIds.add(relicId);
    }

    public void recordShopSurfacedRelic(String relicId) {
        if (currentLog == null || relicId == null) return;
        ShopVisitLog log = ensureCurrentShopVisitLog();
        appendUnique(log.surfacedRelicIds, relicId);
    }

    public void recordShopSurfacedColoredCard(String cardId) {
        if (currentLog == null || cardId == null) return;
        ShopVisitLog log = ensureCurrentShopVisitLog();
        log.surfacedColoredCardIds.add(cardId);
    }

    public void recordShopSurfacedColorlessCard(String cardId) {
        if (currentLog == null || cardId == null) return;
        ShopVisitLog log = ensureCurrentShopVisitLog();
        log.surfacedColorlessCardIds.add(cardId);
    }

    public void recordShopSurfacedPotion(String potionId) {
        if (currentLog == null || potionId == null) return;
        ShopVisitLog log = ensureCurrentShopVisitLog();
        log.surfacedPotionIds.add(potionId);
    }

    public void recordShopPurge(int goldSpent) {
        if (currentLog == null) return;

        ShopPurgeLog log = new ShopPurgeLog();
        log.floor = AbstractDungeon.floorNum;
        log.gold = AbstractDungeon.player.gold;
        log.goldSpent = goldSpent;
        log.timestamp = System.currentTimeMillis();

        currentLog.shopPurges.add(log);
        logger.info("Shop purge (card removal) on floor " + log.floor);
    }

    public void recordGoldGain(int amount, String source) {
        if (currentLog == null) return;

        GoldChangeLog log = new GoldChangeLog();
        log.amount = amount;
        log.source = source;
        log.floor = AbstractDungeon.floorNum;
        log.goldAfter = AbstractDungeon.player.gold;
        log.timestamp = System.currentTimeMillis();

        currentLog.goldChanges.add(log);
        logger.info("Gold gain: +" + amount + " from " + source + " on floor " + log.floor);
    }

    public void recordHpChange(int amount, String source) {
        if (currentLog == null) return;

        HpChangeLog log = new HpChangeLog();
        log.amount = amount;
        log.source = source;
        log.floor = AbstractDungeon.floorNum;
        log.hpAfter = AbstractDungeon.player.currentHealth;
        log.maxHp = AbstractDungeon.player.maxHealth;
        log.timestamp = System.currentTimeMillis();

        currentLog.hpChanges.add(log);
        logger.info("HP change: " + amount + " from " + source + " on floor " + log.floor);
    }

    public void recordTreasureRoom(String roomType) {
        if (currentLog == null) return;

        TreasureRoomLog log = new TreasureRoomLog();
        log.floor = AbstractDungeon.floorNum;
        log.goldBefore = AbstractDungeon.player.gold;
        log.roomType = roomType;
        log.timestamp = System.currentTimeMillis();

        currentLog.treasureRooms.add(log);
        logger.info("Treasure room entered on floor " + log.floor);
    }

    private TreasureRoomLog latestTreasureRoomLog() {
        if (currentLog == null || currentLog.treasureRooms.isEmpty()) return null;
        return currentLog.treasureRooms.get(currentLog.treasureRooms.size() - 1);
    }

    public void recordTreasureRoomRelicObtained(AbstractRelic relic, boolean isMainRelic) {
        TreasureRoomLog log = latestTreasureRoomLog();
        if (log == null || relic == null) return;

        if (!log.obtainedRelicIds.contains(relic.relicId)) {
            log.obtainedRelicIds.add(relic.relicId);
        }
        if (isMainRelic || log.mainRelicId == null) {
            log.mainRelicId = relic.relicId;
            log.relicId = relic.relicId;
            log.relicName = relic.name;
        }
        log.goldAfter = AbstractDungeon.player.gold;
        logger.info("Treasure room relic recorded: " + relic.name + " (main=" + isMainRelic + ")");
    }

    public void recordTreasureRoomSapphireKey(String skippedMainRelicId) {
        TreasureRoomLog log = latestTreasureRoomLog();
        if (log == null) return;

        log.tookSapphireKey = true;
        log.skippedMainRelicId = skippedMainRelicId;
        if (log.mainRelicId == null) {
            log.mainRelicId = skippedMainRelicId;
        }
        if (log.relicId == null) {
            log.relicId = skippedMainRelicId;
        }
        log.goldAfter = AbstractDungeon.player.gold;
        logger.info("Treasure room Sapphire Key recorded on floor " + log.floor + " (skipped=" + skippedMainRelicId + ")");
    }

    public void recordBossRelicChoice(String pickedRelicId, List<String> notPickedRelicIds, boolean skipped) {
        if (currentLog == null) return;

        BossRelicChoiceLog choice = new BossRelicChoiceLog();
        choice.floor = AbstractDungeon.floorNum;
        choice.act = AbstractDungeon.actNum;
        choice.pickedRelicId = pickedRelicId;
        if (notPickedRelicIds != null) {
            choice.notPickedRelicIds.addAll(notPickedRelicIds);
        }
        choice.skipped = skipped;
        choice.timestamp = System.currentTimeMillis();

        if (!currentLog.bossRelicChoices.isEmpty()) {
            BossRelicChoiceLog last = currentLog.bossRelicChoices.get(currentLog.bossRelicChoices.size() - 1);
            if (last.floor == choice.floor && last.act == choice.act) {
                currentLog.bossRelicChoices.remove(currentLog.bossRelicChoices.size() - 1);
            }
        }

        currentLog.bossRelicChoices.add(choice);
        logger.info(
                "Boss relic choice recorded: floor=" + choice.floor
                        + " act=" + choice.act
                        + " picked=" + choice.pickedRelicId
                        + " skipped=" + choice.skipped
        );
    }

    public void recordCardRemove(String cardId, String source) {
        if (currentLog == null) return;

        CardRemoveLog log = new CardRemoveLog();
        log.cardId = cardId;
        log.source = source;
        log.floor = AbstractDungeon.floorNum;
        log.timestamp = System.currentTimeMillis();

        currentLog.cardRemovals.add(log);
        logger.info("Card removed: " + cardId + " from " + source + " on floor " + log.floor);
    }

    public void recordCardTransform(String oldCardId, String newCardId) {
        if (currentLog == null) return;

        CardTransformLog log = new CardTransformLog();
        log.oldCardId = oldCardId;
        log.newCardId = newCardId;
        log.floor = AbstractDungeon.floorNum;
        log.timestamp = System.currentTimeMillis();

        currentLog.cardTransforms.add(log);
        logger.info("Card transformed: " + oldCardId + " -> " + newCardId + " on floor " + log.floor);
    }

    public void recordEliteFight() {
        if (currentLog == null) return;

        EliteFightLog log = new EliteFightLog();
        log.floor = AbstractDungeon.floorNum;
        log.timestamp = System.currentTimeMillis();

        currentLog.eliteFights.add(log);
        logger.info("Elite fight on floor " + log.floor);
    }

    public void recordBossFight(String bossId) {
        if (currentLog == null) return;

        BossFightLog log = new BossFightLog();
        log.bossId = bossId;
        log.floor = AbstractDungeon.floorNum;
        log.timestamp = System.currentTimeMillis();

        currentLog.bossFights.add(log);
        logger.info("Boss fight: " + bossId + " on floor " + log.floor);
    }

    public void recordPotionObtain(AbstractPotion potion, String source) {
        if (currentLog == null) return;

        PotionObtainLog log = new PotionObtainLog();
        log.potionId = potion.ID;
        log.potionName = potion.name;
        log.source = source;
        log.floor = AbstractDungeon.floorNum;
        log.timestamp = System.currentTimeMillis();

        currentLog.potionObtains.add(log);
        logger.info("Potion obtained: " + potion.name + " from " + source + " on floor " + log.floor);
    }

    public void recordCardObtain(AbstractCard card, String source) {
        if (currentLog == null) return;

        CardObtainLog log = new CardObtainLog();
        log.cardId = card.cardID;
        log.upgraded = card.upgraded;
        log.source = source;
        log.floor = AbstractDungeon.floorNum;
        log.timestamp = System.currentTimeMillis();

        currentLog.cardObtains.add(log);
        logger.info("Card obtained: " + card.cardID + " from " + source + " on floor " + log.floor);
    }

    public void recordPowerApplied(String powerId, int amount, String targetType, String targetId) {
        if (currentLog == null) return;

        PowerChangeLog log = new PowerChangeLog();
        log.powerId = powerId;
        log.amount = amount;
        log.targetType = targetType;
        log.targetId = targetId;
        log.action = "applied";
        log.floor = AbstractDungeon.floorNum;
        log.turn = currentLog.currentTurn;
        log.timestamp = System.currentTimeMillis();

        currentLog.powerChanges.add(log);
        logger.info("Power applied: " + powerId + " (" + amount + ") on " + targetType + " floor " + log.floor);
    }

    public void recordPowerRemoved(String powerId) {
        if (currentLog == null) return;

        PowerChangeLog log = new PowerChangeLog();
        log.powerId = powerId;
        log.action = "removed";
        log.floor = AbstractDungeon.floorNum;
        log.turn = currentLog.currentTurn;
        log.timestamp = System.currentTimeMillis();

        currentLog.powerChanges.add(log);
        logger.info("Power removed: " + powerId + " on floor " + log.floor);
    }

    public void recordPowerEffect(String powerId, String effectType, int value) {
        if (currentLog == null) return;

        PowerChangeLog log = new PowerChangeLog();
        log.powerId = powerId;
        log.effectType = effectType;
        log.effectValue = value;
        log.action = "effect";
        log.floor = AbstractDungeon.floorNum;
        log.turn = currentLog.currentTurn;
        log.timestamp = System.currentTimeMillis();

        currentLog.powerChanges.add(log);
        logger.debug("Power effect: " + powerId + " " + effectType + " = " + value + " floor " + log.floor);
    }

    public void recordMonsterDamage(String monsterId, String monsterName, int damage, boolean isBlocking, String damageSource, String damageType) {
        if (currentLog == null) return;

        MonsterDamageLog log = new MonsterDamageLog();
        log.monsterId = monsterId;
        log.monsterName = monsterName;
        log.damage = damage;
        log.isBlocking = isBlocking;
        log.damageSource = damageSource;
        log.damageType = damageType;
        log.floor = AbstractDungeon.floorNum;
        log.turn = currentLog.currentTurn;
        log.timestamp = System.currentTimeMillis();

        currentLog.monsterDamages.add(log);
        logger.info("Damage: " + monsterName + " took " + damage + " from " + damageSource + " (" + damageType + ") floor " + log.floor);
    }

    public void recordMonsterDamage(String monsterId, int damage, boolean isBlocking) {
        recordMonsterDamage(monsterId, monsterId, damage, isBlocking, "unknown", "unknown");
    }

    public void recordCardDraw(int numCards) {
        if (currentLog == null) return;

        CardDrawLog log = new CardDrawLog();
        log.numCards = numCards;
        log.floor = AbstractDungeon.floorNum;
        log.turn = currentLog.currentTurn;
        log.timestamp = System.currentTimeMillis();

        currentLog.cardDraws.add(log);
        logger.info("Card draw: " + numCards + " cards on floor " + log.floor);
    }

    public void recordCardExhaust(String cardId) {
        if (currentLog == null) return;

        CardExhaustLog log = new CardExhaustLog();
        log.cardId = cardId;
        log.floor = AbstractDungeon.floorNum;
        log.turn = currentLog.currentTurn;
        log.timestamp = System.currentTimeMillis();

        currentLog.cardExhausts.add(log);
        logger.info("Card exhaust: " + cardId + " on floor " + log.floor);
    }

    @Override
    public void receivePostPotionUse(AbstractPotion potion) {
        recordPotionUse(potion);
    }

    @Override
    public void receivePostExhaust(AbstractCard card) {
        // Track exhausted cards if needed
    }

    @Override
    public void receivePostRender(SpriteBatch sb) {
        if (currentLog != null && AbstractDungeon.player != null) {
            if (AbstractDungeon.player.isDead || AbstractDungeon.player.isEscaping) {
                if (!currentLog.saved) {
                    String result = AbstractDungeon.player.isEscaping ? "escape" : "death";
                    finishRunAndSave(result, "PostRenderFallback");
                    currentLog.saved = true;
                }
            }
        }
    }

    public void finishRunAndSave(String runResult, String runResultSource) {
        if (currentLog == null || currentLog.saved) return;

        currentLog.runResult = runResult;
        currentLog.runResultSource = runResultSource;
        saveLog();
        currentLog.saved = true;
    }

    private RngStateSnapshot captureRngStateSnapshot() {
        RngStateSnapshot snap = new RngStateSnapshot();
        try {
            snap.cardRngCounter = AbstractDungeon.cardRng != null ? AbstractDungeon.cardRng.counter : 0;
            snap.monsterRngCounter = AbstractDungeon.monsterRng != null ? AbstractDungeon.monsterRng.counter : 0;
            snap.aiRngCounter = AbstractDungeon.aiRng != null ? AbstractDungeon.aiRng.counter : 0;
            snap.eventRngCounter = AbstractDungeon.eventRng != null ? AbstractDungeon.eventRng.counter : 0;
            snap.merchantRngCounter = AbstractDungeon.merchantRng != null ? AbstractDungeon.merchantRng.counter : 0;
            snap.treasureRngCounter = AbstractDungeon.treasureRng != null ? AbstractDungeon.treasureRng.counter : 0;
            snap.relicRngCounter = AbstractDungeon.relicRng != null ? AbstractDungeon.relicRng.counter : 0;
            snap.potionRngCounter = AbstractDungeon.potionRng != null ? AbstractDungeon.potionRng.counter : 0;
            snap.shuffleRngCounter = AbstractDungeon.shuffleRng != null ? AbstractDungeon.shuffleRng.counter : 0;
            snap.cardRandomRngCounter = AbstractDungeon.cardRandomRng != null ? AbstractDungeon.cardRandomRng.counter : 0;
            snap.mapRngCounter = AbstractDungeon.mapRng != null ? AbstractDungeon.mapRng.counter : 0;
            snap.miscRngCounter = AbstractDungeon.miscRng != null ? AbstractDungeon.miscRng.counter : 0;
            snap.monsterHpRngCounter = AbstractDungeon.monsterHpRng != null ? AbstractDungeon.monsterHpRng.counter : 0;
        } catch (Exception e) {
            logger.error("Error capturing RNG state: " + e.getMessage());
        }
        return snap;
    }

    private void captureRngState(String label) {
        if (currentLog == null) return;

        RngSnapshot snap = new RngSnapshot();
        snap.label = label;
        snap.floor = AbstractDungeon.floorNum;
        snap.state = captureRngStateSnapshot();
        currentLog.rngSnapshots.add(snap);

        logger.debug("RNG snapshot captured: " + label + " at floor " + snap.floor);
    }

    public void saveLog() {
        if (currentLog == null) return;
        if (AbstractDungeon.player == null) return;

        currentLog.currentAct = AbstractDungeon.actNum;
        currentLog.endAct = AbstractDungeon.actNum;
        currentLog.endFloor = AbstractDungeon.floorNum;
        currentLog.endHp = AbstractDungeon.player.currentHealth;
        currentLog.endGold = AbstractDungeon.player.gold;
        currentLog.endMaxHp = AbstractDungeon.player.maxHealth;
        rebuildEventSummaries();

        // Capture final deck
        currentLog.finalDeck.clear();
        for (AbstractCard card : AbstractDungeon.player.masterDeck.group) {
            CardInfo info = new CardInfo();
            info.cardId = card.cardID;
            info.upgraded = card.upgraded;
            currentLog.finalDeck.add(info);
        }

        // Capture final relics
        currentLog.finalRelics.clear();
        for (AbstractRelic relic : AbstractDungeon.player.relics) {
            currentLog.finalRelics.add(relic.relicId);
        }

        String filename = "run_" + currentLog.seedString + "_" + System.currentTimeMillis() + ".json";
        Path filepath = Paths.get(outputDir, filename);

        try (OutputStreamWriter writer = new OutputStreamWriter(
                new FileOutputStream(filepath.toFile()), StandardCharsets.UTF_8)) {
            GSON.toJson(currentLog, writer);
            logger.info("Game log saved to: " + filepath);
        } catch (Exception e) {
            logger.error("Failed to save game log: " + e.getMessage());
        }
    }

    // Data classes
    public static class GameDataLog {
        public long seed;
        public String seedString;
        public String character;
        public int currentAct = 1;
        public int currentTurn = 0;
        public String runResult = "unknown";
        public String runResultSource = "unknown";
        public int endAct;
        public int endFloor;
        public int endHp;
        public int endMaxHp;
        public int endGold;
        public boolean saved = false;

        public List<CardInfo> initialDeck = new ArrayList<>();
        public List<String> initialRelics = new ArrayList<>();
        public List<CardInfo> finalDeck = new ArrayList<>();
        public List<String> finalRelics = new ArrayList<>();

        public NeowChoiceLog neowChoice;
        public List<CardPlayLog> allCardPlays = new ArrayList<>();
        public List<CardPlayLog> currentBattleCards = new ArrayList<>();
        public List<BattleLog> battles = new ArrayList<>();
        public List<RngSnapshot> rngSnapshots = new ArrayList<>();
        public List<RngCallLog> rngCalls = new ArrayList<>();
        public List<List<MapNodeLog>> mapNodes = new ArrayList<>();
        public java.util.Map<String, List<List<MapNodeLog>>> mapNodesByAct = new java.util.LinkedHashMap<>();
        public int mapDebugActNum = -1;
        public List<String> mapDebugRow0Edges = new ArrayList<>();
        public List<Integer> mapDebugEdgesPerRow = new ArrayList<>();
        public List<PathStepLog> pathTaken = new ArrayList<>();
        public List<CardRewardLog> cardRewards = new ArrayList<>();
        public List<PotionUseLog> potionUses = new ArrayList<>();
        public List<RelicLog> relicChanges = new ArrayList<>();
        public List<PotionSlotChangeLog> potionSlotChanges = new ArrayList<>();
        public List<EventChoiceLog> eventChoices = new ArrayList<>();
        public List<EventChoiceLog> eventSummaries = new ArrayList<>();
        public List<RestActionLog> restActions = new ArrayList<>();
        public List<ShopVisitLog> shopVisits = new ArrayList<>();
        public List<ShopPurchaseLog> shopPurchases = new ArrayList<>();
        public List<ShopPurgeLog> shopPurges = new ArrayList<>();
        public List<GoldChangeLog> goldChanges = new ArrayList<>();
        public List<HpChangeLog> hpChanges = new ArrayList<>();
        public List<TreasureRoomLog> treasureRooms = new ArrayList<>();
        public List<BossRelicChoiceLog> bossRelicChoices = new ArrayList<>();
        public List<CardRemoveLog> cardRemovals = new ArrayList<>();
        public List<CardTransformLog> cardTransforms = new ArrayList<>();
        public List<EliteFightLog> eliteFights = new ArrayList<>();
        public List<BossFightLog> bossFights = new ArrayList<>();
        public List<PotionObtainLog> potionObtains = new ArrayList<>();
        public List<CardObtainLog> cardObtains = new ArrayList<>();
        public List<PowerChangeLog> powerChanges = new ArrayList<>();
        public List<MonsterDamageLog> monsterDamages = new ArrayList<>();
        public List<CardDrawLog> cardDraws = new ArrayList<>();
        public List<CardExhaustLog> cardExhausts = new ArrayList<>();
        public List<MonsterIntentLog> monsterIntents = new ArrayList<>();
    }

    public static class CardInfo {
        public String cardId;
        public boolean upgraded;
    }

    public static class NeowChoiceLog {
        public int choiceIndex;
        public String rewardType;
        public String description;
        public long timestamp;
    }

    public static class CardPlayLog {
        public String cardId;
        public int cost;
        public boolean upgraded;
        public int floor;
        public int turn;
        public long timestamp;
    }

    public static class BattleLog {
        public int floor;
        public String roomType;
        public List<MonsterLog> monsters = new ArrayList<>();
        public int playerEndHp;
        public int turnCount;
        public List<CardPlayLog> cardsPlayedThisBattle;
        public RngStateSnapshot rngStateEnd;
    }

    public static class MonsterLog {
        public String id;
        public String name;
        public int startingHp;
        public int endingHp;
        public boolean isDead;
    }

    public static class RngSnapshot {
        public String label;
        public int floor;
        public RngStateSnapshot state;
    }

    public static class RngStateSnapshot {
        public int cardRngCounter;
        public int monsterRngCounter;
        public int aiRngCounter;
        public int eventRngCounter;
        public int merchantRngCounter;
        public int treasureRngCounter;
        public int relicRngCounter;
        public int potionRngCounter;
        public int shuffleRngCounter;
        public int cardRandomRngCounter;
        public int mapRngCounter;
        public int miscRngCounter;
        public int monsterHpRngCounter;
    }

    public static class RngCallLog {
        public String rngType;
        public int counter;
        public String method;
        public Object returnValue;
        public Object param1;
        public Object param2;
        public int floor;
        public long timestamp;
        public int turn;
    }

    public static class MapNodeLog {
        public int x;
        public int y;
        public String roomType;
        public boolean hasEmeraldKey;
        public List<MapEdgeLog> edges = new ArrayList<>();
    }

    public static class MapEdgeLog {
        public int dstX;
        public int dstY;
    }

    public static class PathStepLog {
        public int floor;
        public int act;
        public int x;
        public int y;
        public String roomType;
    }

    public static class CardRewardLog {
        public String cardId;
        public boolean upgraded;
        public boolean skipped;
        public String choiceType;
        public List<String> notPickedCardIds = new ArrayList<>();
        public int floor;
        public long timestamp;
    }

    public static class PotionUseLog {
        public String potionId;
        public String potionName;
        public int floor;
        public int turn;
        public long timestamp;
    }

    public static class RelicLog {
        public String relicId;
        public String relicName;
        public int floor;
        public int turn;
        public String action;
        public String source;
        public long timestamp;
    }

    public static class PotionSlotChangeLog {
        public int amount;
        public String source;
        public int floor;
        public int slotsAfter;
        public long timestamp;
    }

    public static class EventChoiceLog {
        public String eventId;
        public String eventName;
        public int choiceIndex;
        public String choiceText;
        public int floor;
        public long timestamp;
    }

    public static class RestActionLog {
        public String action;
        public int floor;
        public int hpBefore;
        public int maxHp;
        public long timestamp;
    }

    public static class ShopPurchaseLog {
        public String itemType;
        public String itemId;
        public int floor;
        public int gold;
        public int goldSpent;
        public long timestamp;
    }

    public static class ShopVisitLog {
        public int floor;
        public List<String> initialRelicOfferIds = new ArrayList<>();
        public List<String> initialColoredCardOfferIds = new ArrayList<>();
        public List<String> initialColorlessCardOfferIds = new ArrayList<>();
        public List<String> initialPotionOfferIds = new ArrayList<>();
        public List<String> surfacedRelicIds = new ArrayList<>();
        public List<String> surfacedColoredCardIds = new ArrayList<>();
        public List<String> surfacedColorlessCardIds = new ArrayList<>();
        public List<String> surfacedPotionIds = new ArrayList<>();
        public List<String> purchasedRelicIds = new ArrayList<>();
        public long timestamp;
    }

    public static class ShopPurgeLog {
        public int floor;
        public int gold;
        public int goldSpent;
        public long timestamp;
    }

    public static class GoldChangeLog {
        public int amount;
        public String source;
        public int floor;
        public int goldAfter;
        public long timestamp;
    }

    public static class HpChangeLog {
        public int amount;
        public String source;
        public int floor;
        public int hpAfter;
        public int maxHp;
        public long timestamp;
    }

    public static class TreasureRoomLog {
        public int floor;
        public String roomType;
        public int goldBefore;
        public int goldAfter;
        public String relicId;
        public String relicName;
        public String mainRelicId;
        public List<String> obtainedRelicIds = new ArrayList<>();
        public String skippedMainRelicId;
        public boolean tookSapphireKey;
        public long timestamp;
    }

    public static class BossRelicChoiceLog {
        public int floor;
        public int act;
        public String pickedRelicId;
        public List<String> notPickedRelicIds = new ArrayList<>();
        public boolean skipped;
        public long timestamp;
    }

    public static class CardRemoveLog {
        public String cardId;
        public String source;
        public int floor;
        public long timestamp;
    }

    public static class CardTransformLog {
        public String oldCardId;
        public String newCardId;
        public int floor;
        public long timestamp;
    }

    public static class EliteFightLog {
        public int floor;
        public long timestamp;
    }

    public static class BossFightLog {
        public String bossId;
        public int floor;
        public long timestamp;
    }

    public static class PotionObtainLog {
        public String potionId;
        public String potionName;
        public String source;
        public int floor;
        public long timestamp;
    }

    public static class CardObtainLog {
        public String cardId;
        public boolean upgraded;
        public String source;
        public int floor;
        public long timestamp;
    }

    public static class PowerChangeLog {
        public String powerId;
        public int amount;
        public String targetType;
        public String targetId;
        public String action;
        public String effectType;
        public int effectValue;
        public int floor;
        public int turn;
        public long timestamp;
    }

    public static class MonsterDamageLog {
        public String monsterId;
        public String monsterName;
        public int damage;
        public boolean isBlocking;
        public String damageSource;
        public String damageType;
        public int floor;
        public int turn;
        public long timestamp;
    }

    public static class CardDrawLog {
        public int numCards;
        public int floor;
        public int turn;
        public long timestamp;
    }

    public static class CardExhaustLog {
        public String cardId;
        public int floor;
        public int turn;
        public long timestamp;
    }

    public static class MonsterIntentLog {
        public int floor;
        public String monsterId;
        public String monsterName;
        public String intent;
        public byte moveIndex;
        public int baseDamage;
        public int aiRngCounter;
        public long timestamp;
    }

    public void recordMonsterIntent(MonsterIntentPatches.IntentRecord record) {
        if (currentLog == null) return;

        MonsterIntentLog log = new MonsterIntentLog();
        log.floor = record.floor;
        log.monsterId = record.monsterId;
        log.monsterName = record.monsterName;
        log.intent = record.intent;
        log.moveIndex = record.moveIndex;
        log.baseDamage = record.baseDamage;
        log.aiRngCounter = record.aiRngCounter;
        log.timestamp = record.timestamp;

        currentLog.monsterIntents.add(log);
    }
}
