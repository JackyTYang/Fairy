from enum import Enum
from re import escape


class AtomicActionType(Enum):
    Tap = "Tap"
    ClearInput = "ClearInput"
    Swipe = "Swipe"
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
        "command": lambda args: f"shell input tap {args['x']} {args['y']}"
    },
    AtomicActionType.Swipe: {
        "arguments": ["x1", "y1", "x2", "y2", "duration"],
        "description": "Swipe from position (x1, y1) to position (x2, y2) OR Long Press position (x,y) when x1 = x2 = x, y1 = y2 = y. "
                       "You can use it to swipe up / down (x does not move to adjust y) or left / right (y does not move to adjust x) to see more content if a scrolling list exists."
                       "Swipe up/down usually moves half the height of the screen, and left/right passes move half the width of the screen."
                       "You can use it to long-press to select an element (e.g. an image, a file, etc.), especially when explicit checkboxes don't exist or the Tap can't select an element."
                       "In light sweeps, duration can generally be set to 500, while in long presses, duration generally needs to be greater than 2500. "
                       "In a collection of operations, No other actions can be executed after swiping, otherwise it may cause problems.",
        "command": lambda args: f"shell input swipe {args['x1']} {args['y1']} {args['x2']} {args['y2']} {args['duration']}"
    },
    AtomicActionType.Input: {
        "arguments": ["text"],
        "description": "Input the \"text\" in an input box.",
        "command": lambda args: " shell am broadcast -a ADB_INPUT_TEXT --es msg " + str(escape(args['text']).replace("\'","\\'"))
    },
    AtomicActionType.ClearInput: {
        "arguments": [],
        "description": "Clear all existing input in an input box.",
        "command": lambda args: f" shell am broadcast -a ADB_CLEAR_TEXT"
    },
    AtomicActionType.KeyEvent: {
        "arguments": ["type"],
        "description": "Sends keystroke events, which are of the following types:"
                       "- KEYCODE_BACK : Return to the previous state, in a collection of operations, no other actions can be executed after send KEYCODE_BACK, otherwise it may cause problems."
                       "- KEYCODE_HOME : Return to home page;",
        "command": lambda args: f"shell input keyevent {args['type']}"
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