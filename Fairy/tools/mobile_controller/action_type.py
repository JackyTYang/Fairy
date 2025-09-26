from enum import Enum


class AtomicActionType(Enum):
    Tap = "Tap"
    ClearInput = "ClearInput"
    Swipe = "Swipe"
    LongPress = "LongPress"
    Input = "Input"
    KeyEvent = "KeyEvent"
    Wait = "Wait"
    Finish = "Finish"
    UserInstruction = "UserInstruction"
    NeedInteraction = "NeedInteraction"

    ListApps = "ListApps"
    StartApp = "StartApp"


ATOMIC_ACTION_SIGNITURES = {
    AtomicActionType.Tap: {
        "arguments": ["x", "y"],
        "SoM_arguments": ["mark_number"],
        "description": lambda is_SoM_mode: f"Tap the position {'tagged with {mark_number} (Only mark_number with red background can be selected)' if is_SoM_mode else '({x}, {y})'} in current screen."
                       "You can use it to click on a button (with an icon or text), a link or to check an option, an input box (for typing) in general.",
    },
    AtomicActionType.Swipe: {
        "arguments": ["x1", "y1", "x2", "y2", "duration"],
        "SoM_arguments": ["mark_number", "distance", "direction", "duration"],
        "description": lambda is_SoM_mode: f"{('Swipe on the area tagged with {mark_number} (Only mark_number with green background can be selected). You can use it to scroll the list up and down ({direction} for H) or left and right ({direction} for W) to see more content. For {distance}, please enter a decimal number in the range of [-1,0),(0,1], a positive value means in the default direction (up/left), a negative value is the opposite (down/right), the value indicates the sliding ratio, for example when it is 0.75 it will slide 3/4 of the area height or width.' if is_SoM_mode else 'Swipe from position ({x1}, {y1}) to position ({x2}, {y2}). You can use it to swipe up / down (x does not move to adjust y) or left / right (y does not move to adjust x) to see more content if a scrolling list exists. Swipe up/down usually moves half the height of the screen, and left/right passes move half the width of the screen.')+'{duration} can generally be set to 500. In a collection of operations, No other actions can be executed after swiping, otherwise it may cause problems.' }",
    },
    AtomicActionType.LongPress: {
        "arguments": ["x", "y", "duration"],
        "SoM_arguments": ["mark_number", "duration"],
        "description": lambda is_SoM_mode: f"Long Press position {'tagged with {mark_number} (Only mark_number with red background can be selected)' if is_SoM_mode else '({x}, {y})'} in current screen."
                       "You can use it to long-press to select an element (e.g. an image, a file, etc.), especially when explicit checkboxes don't exist or the Tap can't select an element."
                       "Duration generally needs to be greater than 1000. "
    },
    AtomicActionType.Input: {
        "arguments": ["text"],
        "SoM_arguments": ["text"],
        "description": lambda is_SoM_mode: "Input the {text} in an input box.",
    },
    AtomicActionType.ClearInput: {
        "arguments": [],
        "SoM_arguments": [],
        "description": lambda is_SoM_mode: "Clear all existing input in an input box.",
    },
    AtomicActionType.KeyEvent: {
        "arguments": ["type"],
        "SoM_arguments": ["type"],
        "description": lambda is_SoM_mode: "Sends keystroke events, which are of the following types:"
                       "- KEYCODE_BACK : Return to the previous state, in a collection of operations, no other actions can be executed after send KEYCODE_BACK, otherwise it may cause problems."
                       "- KEYCODE_HOME : Return to home page;",
    },
    AtomicActionType.Wait: {
        "arguments": ["wait_time"],
        "SoM_arguments": ["wait_time"],
        "description": lambda is_SoM_mode: "Wait for {wait_time} seconds to give more time for loading."
    },
    AtomicActionType.NeedInteraction: {
        "arguments": [],
        "SoM_arguments": [],
        "description": lambda is_SoM_mode: "When you are faced with multiple eligible options to make any choice, carefully consider whether this has been explicitly prompted or confirmed by user interaction. If the instructions are ambiguous, choose to perform a 'NeedInteraction', this will require the planner to rethink."
    },
    AtomicActionType.Finish: {
        "arguments": [],
        "SoM_arguments": [],
        "description": lambda is_SoM_mode: "Called after completing all the requirements in the user's Instruction"
    }
}