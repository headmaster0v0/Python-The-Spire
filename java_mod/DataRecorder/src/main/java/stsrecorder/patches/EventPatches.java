package stsrecorder.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.megacrit.cardcrawl.events.AbstractEvent;
import com.megacrit.cardcrawl.events.RoomEventDialog;
import com.megacrit.cardcrawl.events.GenericEventDialog;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.rooms.AbstractRoom;
import stsrecorder.DataRecorder;

import java.lang.reflect.Field;

@SpirePatch(
        clz = RoomEventDialog.class,
        method = "getSelectedOption"
)
class RoomEventDialogSelectedPatch {
    
    @SpirePostfixPatch
    public static void Postfix(RoomEventDialog __instance) {
        if (DataRecorder.instance != null) {
            try {
                Field selectedOptionField = RoomEventDialog.class.getDeclaredField("selectedOption");
                selectedOptionField.setAccessible(true);
                int selectedOption = selectedOptionField.getInt(null);
                
                if (selectedOption >= 0) {
                    AbstractRoom room = AbstractDungeon.getCurrRoom();
                    if (room != null && room.event != null) {
                        AbstractEvent event = room.event;
                        
                        String eventId = event.getClass().getSimpleName();
                        String eventName = eventId;
                        
                        try {
                            Field nameField = AbstractEvent.class.getDeclaredField("NAME");
                            nameField.setAccessible(true);
                            Object name = nameField.get(event);
                            if (name != null) {
                                eventName = name.toString();
                            }
                        } catch (Exception e) {
                        }
                        
                        String optionText = "";
                        try {
                            Field optionListField = RoomEventDialog.class.getDeclaredField("optionList");
                            optionListField.setAccessible(true);
                            java.util.ArrayList<?> optionList = (java.util.ArrayList<?>) optionListField.get(__instance);
                            if (optionList != null && selectedOption < optionList.size()) {
                                Object button = optionList.get(selectedOption);
                                Field msgField = button.getClass().getDeclaredField("msg");
                                msgField.setAccessible(true);
                                Object msg = msgField.get(button);
                                if (msg != null) {
                                    optionText = msg.toString();
                                }
                            }
                        } catch (Exception e) {
                        }
                        
                        DataRecorder.instance.recordEventChoice(
                            eventId,
                            eventName,
                            selectedOption,
                            optionText
                        );
                        DataRecorder.instance.logger.info("Event choice (RoomEventDialog): " + eventName + " option " + selectedOption + " - " + optionText + " on floor " + AbstractDungeon.floorNum);
                    }
                }
            } catch (Exception e) {
                DataRecorder.logger.error("Error in RoomEventDialogSelectedPatch: " + e.getMessage());
            }
        }
    }
}

@SpirePatch(
        clz = GenericEventDialog.class,
        method = "getSelectedOption"
)
class GenericEventDialogSelectedPatch {
    
    @SpirePostfixPatch
    public static void Postfix() {
        if (DataRecorder.instance != null) {
            try {
                Field selectedOptionField = GenericEventDialog.class.getDeclaredField("selectedOption");
                selectedOptionField.setAccessible(true);
                int selectedOption = selectedOptionField.getInt(null);
                
                if (selectedOption >= 0) {
                    AbstractRoom room = AbstractDungeon.getCurrRoom();
                    if (room != null && room.event != null) {
                        AbstractEvent event = room.event;
                        
                        String eventId = event.getClass().getSimpleName();
                        String eventName = eventId;
                        
                        try {
                            Field nameField = AbstractEvent.class.getDeclaredField("NAME");
                            nameField.setAccessible(true);
                            Object name = nameField.get(event);
                            if (name != null) {
                                eventName = name.toString();
                            }
                        } catch (Exception e) {
                        }
                        
                        String optionText = "";
                        try {
                            Field imageEventTextField = AbstractEvent.class.getDeclaredField("imageEventText");
                            imageEventTextField.setAccessible(true);
                            GenericEventDialog dialog = (GenericEventDialog) imageEventTextField.get(event);
                            if (dialog != null) {
                                Field optionListField = GenericEventDialog.class.getDeclaredField("optionList");
                                optionListField.setAccessible(true);
                                java.util.ArrayList<?> optionList = (java.util.ArrayList<?>) optionListField.get(dialog);
                                if (optionList != null && selectedOption < optionList.size()) {
                                    Object button = optionList.get(selectedOption);
                                    Field msgField = button.getClass().getDeclaredField("msg");
                                    msgField.setAccessible(true);
                                    Object msg = msgField.get(button);
                                    if (msg != null) {
                                        optionText = msg.toString();
                                    }
                                }
                            }
                        } catch (Exception e) {
                        }
                        
                        DataRecorder.instance.recordEventChoice(
                            eventId,
                            eventName,
                            selectedOption,
                            optionText
                        );
                        DataRecorder.instance.logger.info("Event choice (GenericEventDialog): " + eventName + " option " + selectedOption + " - " + optionText + " on floor " + AbstractDungeon.floorNum);
                    }
                }
            } catch (Exception e) {
                DataRecorder.logger.error("Error in GenericEventDialogSelectedPatch: " + e.getMessage());
            }
        }
    }
}
