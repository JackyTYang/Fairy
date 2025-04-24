from enum import Enum


class EventType(Enum):
    GlobalPlan = 10
    Task = 0
    Plan = 1
    ActionExecution = 2
    ScreenPerception = 3
    Reflection = 4
    KeyInfoExtraction = 5
    UserInteraction = 6
    UserChat = 7
    TaskFinish = 8

class EventStatus(Enum):
    CREATED = 0
    DONE = 1
    FAILED = -1

class CallType(Enum):
    Memory_GET = 1
    Memory_SWITCH = 2
    App_Info_GET = 3
    Action_EXECUTE = 4