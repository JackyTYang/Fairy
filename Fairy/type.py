from enum import Enum


class EventType(Enum):
    Plan = 1
    ActionExecution = 2
    ScreenPerception = 3
    Reflection = 4
    NextAction = 5
    KeyInfoExtraction = 6
    UserInteraction = 7
    UserChat = 8

class EventStatus(Enum):
    CREATED = 0
    DONE = 1
    FAILED = -1

class CallType(Enum):
    Memory_GET = 1