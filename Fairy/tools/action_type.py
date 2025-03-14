from enum import Enum

class AtomicActionType(Enum):
    # Open_App = "Open_App"
    Tap = "Tap"
    Swipe = "Swipe"
    Type = "Type"
    Enter = "Enter"
    Switch_App = "Switch_App"
    Back = "Back"
    Home = "Home"
    Wait = "Wait"
    Stop = "Stop"


ATOMIC_ACTION_SIGNITURES = {
    # AtomicActionType.Open_App: {
    #     "arguments": ["app_name"],
    #     "description": lambda info: "If the current screen is Home or App screen, you can use this action to open the app named \"app_name\" on the visible on the current screen."
    # },
    AtomicActionType.Tap: {
        "arguments": ["x", "y"],
        "description": lambda info: "Tap the position (x, y) in current screen."
    },
    AtomicActionType.Swipe: {
        "arguments": ["x1", "y1", "x2", "y2"],
        "description": lambda info: f"Swipe from position (x1, y1) to position (x2, y2). To swipe up or down to review more content, you can adjust the y-coordinate offset based on the desired scroll distance. For example, setting x1 = x2 = {int(0.5 * info['width'])}, y1 = {int(0.5 * info['height'])}, and y2 = {int(0.1 * info['height'])} will swipe upwards to review additional content below. To swipe left or right in the App switcher screen to choose between open apps, set the x-coordinate offset to at least {int(0.5 * info['width'])}."
    },
    AtomicActionType.Type: {
        "arguments": ["text"],
        "description": lambda info: "Type the \"text\" in an input box."
    },
    AtomicActionType.Enter: {
        "arguments": [],
        "description": lambda info: "Press the Enter key after typing (useful for searching)."
    },
    AtomicActionType.Switch_App: {
        "arguments": [],
        "description": lambda info: "Show the App switcher for switching between opened apps."
    },
    AtomicActionType.Back: {
        "arguments": [],
        "description": lambda info: "Return to the previous state."
    },
    AtomicActionType.Home: {
        "arguments": [],
        "description": lambda info: "Return to home page."
    },
    AtomicActionType.Wait: {
        "arguments": [],
        "description": lambda info: "Wait for 10 seconds to give more time for a page loading."
    }
}