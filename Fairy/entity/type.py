from enum import Enum

class EventChannel:
    APP_CHANNEL = "app_channel"
    GLOBAL_CHANNEL = "global_channel"

class EventType(Enum):
    INIT = "INIT" # 适用于拉起应用
    Task = "Task"
    Plan = "Plan"
    ActionDecision = "ActionDecision"
    ActionExecution = "ActionExecution"
    ScreenPerception = "ScreenPerception"
    Reflection = "Reflection"
    KeyInfoExtraction = "KeyInfoExtraction"
    UserInteraction = "UserInteraction"
    UserChat = "UserChat"

class EventStatus(Enum):
    CREATED = "CREATED"
    DONE = "DONE"
    FAILED = "FAILED"

class CallType(Enum):
    Memory_GET = 1
    Memory_SWITCH = 2
    App_Info_GET = 3
    Action_EXECUTE = 4