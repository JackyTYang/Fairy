from enum import Enum


class EventType(Enum):
    Plan = 1
    ActionExecution = 2
    ScreenPerception = 3
    Reflection = 4

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