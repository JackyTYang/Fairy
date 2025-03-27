from enum import Enum


class EventType(Enum):
    Plan = 1
    ActionExecution = 2
    ScreenPerception = 3
    Reflection = 4
    KeyInfoExtraction = 5
    UserInteraction = 6
    UserChat = 7

class EventStatus(Enum):
    CREATED = 0
    DONE = 1
    FAILED = -1

class CallType(Enum):
    Memory_GET = 1

class MemoryType(Enum):
    Instruction = 0
    Plan = 1
    Action = 2
    ActionResult = 3
    ScreenPerception = 4
    KeyInfo = 5
    UserInteraction = 6