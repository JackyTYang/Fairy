from enum import Enum
from re import escape


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


ATOMIC_ACTION_SIGNITURES = {
    AtomicActionType.Tap: {
        "arguments": ["x", "y"],
        "description": "Tap the position (x, y) in current screen."
                       "You can use it to click on a button (with an icon or text), a link or to check an option, an input box (for typing) in general.",
    },
    AtomicActionType.Swipe: {
        "arguments": ["x1", "y1", "x2", "y2", "duration"],
        "description": "Swipe from position (x1, y1) to position (x2, y2)."
                       "You can use it to swipe up / down (x does not move to adjust y) or left / right (y does not move to adjust x) to see more content if a scrolling list exists."
                       "Swipe up/down usually moves half the height of the screen, and left/right passes move half the width of the screen."
                       "Duration can generally be set to 500."
                       "In a collection of operations, No other actions can be executed after swiping, otherwise it may cause problems.",
    },
    AtomicActionType.LongPress: {
        "arguments": ["x", "y", "duration"],
        "description": "Long Press position (x,y)  in current screen."
                       "You can use it to long-press to select an element (e.g. an image, a file, etc.), especially when explicit checkboxes don't exist or the Tap can't select an element."
                       "Duration generally needs to be greater than 1000. "
    },
    AtomicActionType.Input: {
        "arguments": ["text"],
        "description": "Input the \"text\" in an input box.",
    },
    AtomicActionType.ClearInput: {
        "arguments": [],
        "description": "Clear all existing input in an input box.",
    },
    AtomicActionType.KeyEvent: {
        "arguments": ["type"],
        "description": "Sends keystroke events, which are of the following types:"
                       "- KEYCODE_BACK : Return to the previous state, in a collection of operations, no other actions can be executed after send KEYCODE_BACK, otherwise it may cause problems."
                       "- KEYCODE_HOME : Return to home page;",
    },
    AtomicActionType.Wait: {
        "arguments": ["wait_time"],
        "description": "Wait for \"wait_time\" seconds to give more time for loading."
    },
    AtomicActionType.Finish: {
        "arguments": [],
        "description": "Called after completing all the requirements in the user's Instruction"
    }
}